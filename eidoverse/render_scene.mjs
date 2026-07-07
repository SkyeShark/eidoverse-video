/**
 * Eidoverse render engine — Deno + WebGPU (wgpu-rs + Mesa-D3D12 on WSL2) +
 * three.js / TSL. Offline video renderer: eval a scene script, install
 * globals, call its setup(), run a renderFrame(t) loop, pipe GPU readback
 * to ffmpeg-nvenc.
 *
 * Pipeline:
 *   - Asset loading (local files + HTTPS URLs → Uint8Array on globalThis.ASSETS)
 *   - Asset usage pre-flight check
 *   - Helper module injection: pure-JS modules that register globals
 *     (procedural_materials, sdf_raymarch_loader, the
 *      character controllers + IK, robot_*, camera_safety, the effects_tsl/*
 *      registry exposed as CustomEffectsDeno, scene_placement, ...)
 *   - VRMA defaults injection
 *   - Scene script eval + setup() + post-setup placement audit + renderFrame(t) loop
 *   - Auto-enhance TSL post stack (GTAO / SSR / bloom / FXAA)
 *   - GPU→CPU readback → ffmpeg-nvenc pipe
 *   - Three.js WebGPURenderer with FakeGPUCanvasContext + browser shims
 *
 * Placement QA is native: checkClipping / checkHovering / checkDensity run
 * post-setup (the engine pipes straight to ffmpeg with no on-disk frames).
 * UI/motion-graphics go through the Satori UI path (satori_ui.mjs) and
 * the makeScreen/makeOverlayLayer helpers; see AGENTS.md "Motion graphics".
 *
 * Usage: deno run --allow-all --unstable-webgpu --node-modules-dir=auto \
 *          eidoverse/render_scene.mjs <config.json>
 */

import {
    loadConfig, setupRenderer, getCameraAtTime, logProgress,
    startFfmpegPipe, readbackFrame, drainReadback, shutdown, loadAssets,
} from './render_common.mjs';

const config = loadConfig(Deno.args[0]);
const width = config.width || 1280;
const height = config.height || 720;
const fps = config.fps || 30;
const duration = config.duration || 5.0;
const totalFrames = Math.ceil(duration * fps);
const dt = 1.0 / fps;
const outputVideo = config.outputVideo || config.composedOutput
    || (config.outputDir || './scene') + '.mp4';

// --- Read scene script ---
let sceneScript;
if (config.script) {
    sceneScript = await Deno.readTextFile(config.script);
} else if (config.inlineScript) {
    sceneScript = config.inlineScript;
} else {
    console.error('[render_scene] Config must have "script" or "inlineScript"');
    Deno.exit(1);
}

// --- Renderer + globals setup (does deno-dom, FakeGPUCanvasContext, THREE import) ---
const harness = await setupRenderer(width, height);
const { THREE, canvas, adapter, device } = harness;

// Constants the scene script expects
globalThis.WIDTH = width;
globalThis.HEIGHT = height;
globalThis.FPS = fps;
globalThis.DURATION = duration;
globalThis.TOTAL_FRAMES = totalFrames;
globalThis.canvas = canvas;
// CRITICAL for WebGPU: scene scripts MUST pass these to new WebGPURenderer.
// Without them, Three.js auto-requests its own GPUAdapter+GPUDevice, which
// then re-configures fakeCtx with a texture owned by that foreign device.
// Subsequent readbacks (owned by harness's device) silently fail → black mp4.
globalThis.GPU_ADAPTER = adapter;
globalThis.GPU_DEVICE = device;
// Directory of the engine as a file:// URL — the mode-agnostic base for
// dynamically importing the sim toolkit from scene scripts:
//   await import(globalThis.EIDOVERSE_DIR + 'cloth_sim.js')
globalThis.EIDOVERSE_DIR = new URL('./', import.meta.url).href;

// Helper that scene scripts use to decode base64 assets.
//
// Historical: production render_scene runs in Playwright/Chromium where
// CDP can't pass binary buffers cleanly, so assets were base64-encoded
// across the wire and scene scripts decoded them with this helper.
//
// In deno we store the asset as a Uint8Array directly on
// globalThis.ASSETS — no base64 round-trip — but a lot of existing
// scene scripts still call `b64toArrayBuffer(globalThis.ASSETS.car)`
// expecting a string in. We accept either: a string runs the original
// atob path, a Uint8Array passes its underlying ArrayBuffer through.
globalThis.b64toArrayBuffer = (input) => {
    if (input instanceof Uint8Array) return input.buffer;
    if (input instanceof ArrayBuffer) return input;
    if (typeof input !== 'string') {
        throw new Error(`b64toArrayBuffer: unsupported input type ${typeof input}`);
    }
    const binary = atob(input);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes.buffer;
};

// Scene composition primitives (placeOn, placeAgainst, snapToGround,
// alignToSurface, scatterOn, findClearSpot, checkClipping). Also provides
// a fixed `placeRelativeTo` alias that no longer ignores obj's own bbox.
// See `eidoverse/scene_placement.js` for the full API + caveats.
{
    const { installScenePlacement } = await import('./scene_placement.js');
    installScenePlacement(THREE);
}

// Silhouette Parallax Occlusion Mapping material factory
// (globalThis.createParallaxMaterial). See eidoverse/parallax_material.js.
{
    const { installParallaxMaterial } = await import('./parallax_material.js');
    installParallaxMaterial(THREE);
}

// --- Asset loading (local files + HTTPS) ---
async function fetchUrl(url) {
    const r = await fetch(url, { headers: { 'User-Agent': 'eidoverse-render/1.0' }});
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return new Uint8Array(await r.arrayBuffer());
}

const assetsConfig = config.assets || {};
const assetsBin = {};
const assetErrors = [];
for (const [key, assetPath] of Object.entries(assetsConfig)) {
    const isUrl = typeof assetPath === 'string' && /^https?:\/\//i.test(assetPath);
    try {
        const data = isUrl ? await fetchUrl(assetPath) : await Deno.readFile(assetPath);
        if (data.length === 0) {
            assetErrors.push(`  - "${key}" at "${assetPath}" is EMPTY (0 bytes)`);
            continue;
        }
        // Store the raw Uint8Array — no base64 round-trip needed in deno.
        // b64toArrayBuffer() above accepts Uint8Array directly so existing
        // scene scripts that call it on globalThis.ASSETS.foo still work.
        assetsBin[key] = data;
        console.log(`[render_scene] Loaded asset "${key}" (${(data.length/1024/1024).toFixed(1)}MB)`);
    } catch (e) {
        assetErrors.push(`  - "${key}" at "${assetPath}": ${e.message}`);
    }
}
if (assetErrors.length) {
    console.error(`[render_scene] FATAL: ${assetErrors.length} asset(s) failed:`);
    for (const line of assetErrors) console.error(line);
    Deno.exit(1);
}

// Pre-flight: each declared asset must be referenced in the scene script
// OR in an injected helper module that consumes config.assets keys itself
// (list helper paths here if a helper reads asset keys the scene script
// never names individually).
const _ASSET_REF_HELPERS = [];
if (Object.keys(assetsConfig).length > 0) {
    let assetRefCorpus = sceneScript;
    for (const fname of _ASSET_REF_HELPERS) {
        try { assetRefCorpus += await Deno.readTextFile(fname); }
        catch { try { assetRefCorpus += await Deno.readTextFile(`/workspace/${fname}`); } catch {} }
    }
    const missingKeys = Object.keys(assetsConfig).filter(k => {
        const escaped = k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        // .key | ["key"] | key: (object-literal form — the lock ASSET_PATHS
        // tables define keys that are then read dynamically via Object.keys)
        const pat = new RegExp(`(?:\\.${escaped}\\b|\\[\\s*["'\`]${escaped}["'\`]\\s*\\]|\\b${escaped}\\s*:)`);
        return !pat.test(assetRefCorpus);
    });
    if (missingKeys.length > 0) {
        console.error(`[render_scene] FATAL: scene never references assets: ${missingKeys.join(', ')}`);
        Deno.exit(1);
    }
}

// Orphan check: warn loudly about model files in the work dir that the
// agent fetched but never registered in `assets` and never referenced
// in the scene script. Most common cause of empty/void scenes — the
// agent planned an environment via fetch_model.py, decided "nah," but
// never replaced it with anything, leaving the GLB orphaned on disk
// while the scene fell back to a flat backdrop. Not fatal; the scene
// still renders. But the warning is the agent's signal to either wire
// the model in or delete it before considering the scene done.
try {
    const scriptDir = config.script ? config.script.substring(0, config.script.lastIndexOf('/')) : null;
    if (!scriptDir) throw new Error('no script path');
    const declaredPaths = new Set(
        Object.values(assetsConfig).map(p => typeof p === 'string' ? p : '')
    );
    const orphans = [];
    for await (const entry of Deno.readDir(scriptDir)) {
        if (!entry.isFile) continue;
        if (!/\.(glb|gltf)$/i.test(entry.name)) continue;
        const full = `${scriptDir}/${entry.name}`;
        if (declaredPaths.has(full)) continue;
        orphans.push(entry.name);
    }
    if (orphans.length > 0) {
        console.error(
            `[render_scene] WARNING: ${orphans.length} fetched model(s) NOT used by this scene:`,
        );
        for (const name of orphans) console.error(`  - ${name}`);
        console.error(
            `[render_scene] Either wire them into scene.json's "assets" + use them in setup(), or delete them. See AGENTS.md "Every fetched model must end up used OR deleted".`,
        );
    }
} catch (_) { /* non-fatal */ }

// Track asset reads via Proxy (catches "declared but never accessed" downstream)
const _assetStore = {};
globalThis.__assetReads = new Set();
globalThis.ASSETS = new Proxy(_assetStore, {
    get(t, p) { if (typeof p === 'string') globalThis.__assetReads.add(p); return t[p]; },
    set(t, p, v) { t[p] = v; return true; },
});
for (const [key, bin] of Object.entries(assetsBin)) globalThis.ASSETS[key] = bin;

// --- Inject helper modules ---
// These are pure JS that install themselves on globalThis. They access
// THREE and other globals we've already set.
const HELPER_MODULES = [
    'eidoverse/rhombic_dodecahedron.js',
    'eidoverse/robot_sensors.js', 'eidoverse/robot_memory.js', 'eidoverse/robot_planner.js',
    'eidoverse/robot_body.js', 'eidoverse/robot_debug.js',
    'eidoverse/mech_parts.js',            // globalThis.MechParts — procedural mechanical part generators (chamfered boxes, lathe housings, cables, treads, wheels, greebles); robotics_kit builds from these
    'eidoverse/robotics_kit.js',          // globalThis.makeRobot / RoboticsKit — industrial robots (arm/delta/stewart/turret/agv/gantry/scara/printer), contraption connect(), applyTextures()
    'eidoverse/iso_field.js',             // globalThis.makeIsoField — GPU-raymarched isosurface over a CPU-written voxel field (fast path for the MarchingCubes pattern; fab_sim renders through it)
    'eidoverse/fab_sim.js',               // globalThis.FabSim — additive print() (printer/delta, molten goo + true mesh) + subtractive carve() (gantry mill); PrintSim/CNCSim alias here
    'eidoverse/camera_safety.js',
    'eidoverse/sdf_raymarch_loader.js',
    'eidoverse/procedural_materials.js',  // canvas-2d unblocked via @napi-rs/canvas shim
    'eidoverse/particles.js',             // globalThis.makeParticles — GPU textured sprite particles (sparks/smoke/dust/…)
    'eidoverse/grass.js',                 // globalThis.makeGrass — GPU wind grass field (tapered blades, height-gradient color, adjustable wind/density/height/color)
    'eidoverse/seedthree_api.js',         // globalThis.makeSeedTree — SeedThree procedural trees/plants via its headless agent API (seed-first design; identical to the SeedThree app; local checkout or GitHub import)
    // RETIRED (unfinished stub bridge over SeedThree core internals — superseded by seedthree_api.js):
    // 'eidoverse/seed_three.js',
    'eidoverse/screen.js',              // globalThis.makeScreen — animated canvas-2D screen/display panel (self-updating CanvasTexture, unlit emissive, exact UI colors)
    'eidoverse/creature_builder.js',    // globalThis.makeCreature — universal procedural creature builder (spine+limbs auto-rig, morphology-adaptive gait, makeCreature.random)
    'eidoverse/model_kit.js',             // globalThis.loadKit — named, origin-centered parts for modular-kit / asset-library GLTFs (don't drop the whole gltf.scene; assemble from parts). fetch_model.py flags kits with [KIT_INFO].
    'eidoverse/loft.js',                  // globalThis.Loft + LoftGeometry — loft modeling: cross-section skinning, sweep with taper/twist/profile-morph
    'eidoverse/particle_morph.js',       // globalThis.makeParticleMorph + ParticleMorph.fromMesh/fromText/fromPoints/neuronGraph — GPU cloud that dissolves→reforms between shapes (incl. text + ASCII art via fromText)
    'eidoverse/terrain.js',              // globalThis.makeTerrain — procedural heightfield + vertex-painted multi-texture blend
    // VRM character controller + IK. Loading them here means scene scripts
    // can call `new VRMCharacterController(...)` / `new VRMFootControllerIK(...)`
    // directly without manually readTextFile-eval'ing.
    'eidoverse/foot_ik.js',
    'eidoverse/character_controller.js',
    // Robot adapter — VRMRobotBody→character-controller bridge with turning
    // (enableTurning). Must load AFTER character_controller.js.
    'eidoverse/robot_controller.js',
    'eidoverse/effects_tsl/underwater.js',     // underwater refraction/tint
    'eidoverse/effects_tsl/vhs_tape.js',       // VHS look (NTSC chroma bleed)
    'eidoverse/effects_tsl/crt.js',            // CRT look (curve+scanlines+grille)
    'eidoverse/effects_tsl/old_bw_film.js',    // 12fps b&w film with dirt
    'eidoverse/effects_tsl/volumetric_clouds.js',  // 3D cloud volumes via VolumeNodeMaterial
    'eidoverse/effects_tsl/chromatic_aberration_alpha.js',  // alpha-aware RGB shift
    'eidoverse/effects_tsl/wavy.js',           // sinusoidal horizontal row shift
    'eidoverse/effects_tsl/jitter.js',         // hash-driven RGB-shift bursts
    'eidoverse/effects_tsl/melt.js',           // HSV-driven swirl
    'eidoverse/effects_tsl/kaleidoscope.js',   // radial mirror symmetry
    'eidoverse/effects_tsl/neon_edges.js',     // Sobel edges with neon glow
    'eidoverse/effects_tsl/glitch_bars.js',    // scrolling RGB-split bars
    'eidoverse/effects_tsl/bw_halftone.js',    // 45° newspaper-print halftone
    'eidoverse/effects_tsl/focus_blur.js',     // dof depth-of-field via three/addons DepthOfFieldNode
    'eidoverse/effects_tsl/depth_fog.js',      // exponential fog via three/addons depthAwareBlend (silhouette-aware)
    'eidoverse/effects_tsl/dithering.js',      // Bayer ordered dither + quantise via three/addons Bayer
    'eidoverse/effects_tsl/blueprint.js',      // engineering-blueprint look — depth+normal edges on blue grid paper
    'eidoverse/effects_tsl/full_toon.js',      // cel shading + 3-stop palette tint + sobel outline
    'eidoverse/effects_tsl/cross_hatch.js',    // crosshatch shading — three/addons sobel + rotated hatch lines
    'eidoverse/effects_tsl/retro_wireframe.js',  // pseudo-wireframe retro display (faceted outline + triplanar tri-mesh fill)
    'eidoverse/effects_tsl/nuclear_explosion.js',  // SDF mushroom-cloud raymarched, same hook scaffold as volumetric_clouds
    'eidoverse/effects_tsl/anamorphic_flare.js',  // wraps three's anamorphic() — horizontal flares from bright pixels
    'eidoverse/effects_tsl/sepia.js',             // wraps three's sepia() Fn
    'eidoverse/effects_tsl/bleach_bypass.js',     // wraps three's bleach() Fn — cinema bleach bypass look
    'eidoverse/effects_tsl/after_image.js',       // wraps three's afterImage() — frame feedback trail
    'eidoverse/effects_tsl/rgb_shift.js',         // wraps three's rgbShift() — directional channel split
    'eidoverse/effects_tsl/rain_on_camera.js',    // rain-on-the-lens — screen-locked refraction + wet blur
    'eidoverse/effects_tsl/depth_rain.js',     // worldspace weather: streaks+puddles+splashes+cover occlusion
    'eidoverse/effects_tsl/radial_blur.js',       // wraps three's radialBlur() — light-shaft / zoom blur
    'eidoverse/effects_tsl/box_blur.js',          // wraps three's boxBlur() — cheap blocky blur
    'eidoverse/effects_tsl/hash_blur.js',         // wraps three's hashBlur() — random-pattern blur
    'eidoverse/effects_tsl/godrays.js',           // wraps three's godrays() — light-shaft volumetric rays
    'eidoverse/effects_tsl/lensflare.js',         // wraps three's lensflare() — ghost-spot lens flares
    'eidoverse/effects_tsl/custom_effects_deno.js',  // unified registry; depends on the per-effect modules above
];

// WebGPU-only addon imports. The WebGL post-processing addons
// (`EffectComposer`, `RenderPass`, `ShaderPass`, `*Pass`, `FXAAShader`, etc.)
// were removed when this pipeline migrated to TSL postprocessing
// (`three/tsl` + `effects_tsl/*`). What remains: WebGPU-friendly TSL
// utility nodes and the NodeMaterial-based sky.
async function loadAddons() {
    const tryImport = async (path, names) => {
        try {
            const mod = await import(path);
            for (const n of names) {
                if (mod[n] !== undefined && globalThis[n] === undefined) globalThis[n] = mod[n];
            }
        } catch (e) {
            console.log(`[render_scene] addon skipped (${path}): ${e.message}`);
        }
    };
    await tryImport('npm:three@0.184.0/addons/tsl/utils/Raymarching.js', ['RaymarchingBox']);
    await tryImport('npm:three@0.184.0/addons/objects/SkyMesh.js', ['SkyMesh']);
}
await loadAddons();
console.log('[render_scene] WebGPU addons loaded');

// three-mesh-bvh: accelerated raycasting. robot_sensors' lidar (and any
// raycast-heavy helper) detects these prototypes and builds boundsTrees —
// without them every sensor ray brute-forces the full triangle list and
// autonomous nav costs ~700ms/frame (the "kitchen-sink scenes render at
// 1fps" bug). acceleratedRaycast is a safe global swap: meshes without a
// boundsTree fall through to the stock raycast path.
try {
    const { computeBoundsTree, disposeBoundsTree, acceleratedRaycast, MeshBVH } =
        await import('npm:three-mesh-bvh@0.9.10');
    THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
    THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
    THREE.Mesh.prototype.raycast = acceleratedRaycast;
    globalThis.MeshBVH = MeshBVH;
    console.log('[render_scene] three-mesh-bvh wired (accelerated raycast + boundsTree)');
} catch (e) {
    console.warn('[render_scene] three-mesh-bvh unavailable — raycast-heavy helpers (robot nav lidar) will be SLOW:', e.message);
}

for (const fname of HELPER_MODULES) {
    try {
        let code;
        try { code = await Deno.readTextFile(fname); }
        catch { code = await Deno.readTextFile(`/workspace/${fname}`); }
        // eval in global scope so `var X` and `window.X = ...` install on globalThis
        (0, eval)(code);
        console.log(`[render_scene] Injected ${fname}`);
    } catch (e) {
        console.log(`[render_scene] ${fname} skipped: ${e.message}`);
        if (e.stack) console.log(`  stack: ${String(e.stack).split('\n').slice(0, 5).join('\n  ')}`);
    }
}

// VRMA defaults — exposed on globalThis.VRMA_DEFAULTS_B64 keyed by slot.
// Slot names are the stable agent-facing API; on-disk filenames vary
// per environment. Each slot has a list of candidate paths; the first
// readable one wins. Missing slots are silently dropped.
//
// Production sandbox bakes locomotion VRMAs into /opt/render3d/vrma_defaults
// (slot-named, e.g. walk.vrma). The deno-webgpu sandbox has them mounted
// from the host workspace at /workspace/vrma_defaults. Expressive VRMAs
// live under per-project workspace dirs with their original filenames.
// Canonical animation library lives in the release-contained
// eidoverse/assets/animations/ (slot-named, e.g. walk.vrma, sit.vrma).
// The legacy dirs are kept as fallbacks so older sandboxes still resolve.
// Slot name === filename stem, so the table derives from a slot list.
const ANIM_DIRS = [
    'eidoverse/assets/animations',             // canonical (cwd-relative — works in-container AND host-local)
    '/workspace/eidoverse/assets/animations',  // container-absolute fallback
    '/workspace/vrma_defaults',                // legacy host locomotion fallback
    '/opt/render3d/vrma_defaults',             // baked-image locomotion fallback
];
const VRMA_SLOTS = [
    // Locomotion (driven by VRMCharacterController)
    'walk', 'run', 'idle', 'turnLeft', 'turnRight', 'jump', 'vault',
    'climbLedge', 'climbWallUp', 'climbWallDown', 'climbLadder',
    'fallIdle', 'fallLand', 'stairsUp', 'stairsDown', 'stairsRunUp', 'stairsRunDown',
    // Expressive — for a STATIONARY VRM only (no active controller waypoints).
    // See AGENTS.md "Emotes + sitting on a stationary character".
    'talk', 'salute', 'cheer', 'fist', 'raise', 'reach', 'crazy', 'dance',
    // Sitting clips — slot name == the .vrma filename in assets/animations/.
    //   CHAIR:  'sitting_normal_chair' (seatOn default), 'sitting_nervous_arm_rub_chair'
    //   FLOOR:  'sitting_on_ground' (cross-legged; sitOnGround default), 'sit_laying_on_ground' (lying down)
    // Each loads only if its .vrma exists (missing = silently skipped).
    'sitting_normal_chair', 'sitting_nervous_arm_rub_chair', 'sitting_on_ground', 'sit_laying_on_ground',
    // Stand<->sit TRANSITIONS (Mixamo, hips translation baked in metres: the clip
    // itself lowers/raises the body). Played via seatOn({transition:true}) /
    // standUp. stand_to_sit: hips Y 0.96->0.52, Z 0->-0.47 (sits down and back).
    'stand_to_sit', 'sit_to_stand',
];
const vrmaSlotPaths = {};
for (const slot of VRMA_SLOTS) {
    vrmaSlotPaths[slot] = ANIM_DIRS.map((d) => `${d}/${slot}.vrma`);
}
const vrmaDefaultsB64 = {};
for (const [slot, paths] of Object.entries(vrmaSlotPaths)) {
    for (const p of paths) {
        try {
            const buf = await Deno.readFile(p);
            let bin = '';
            for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]);
            vrmaDefaultsB64[slot] = btoa(bin);
            break;
        } catch { /* try next path */ }
    }
}
if (Object.keys(vrmaDefaultsB64).length > 0) {
    globalThis.VRMA_DEFAULTS_B64 = vrmaDefaultsB64;
    console.log(`[render_scene] Loaded ${Object.keys(vrmaDefaultsB64).length} VRMA defaults: ${Object.keys(vrmaDefaultsB64).join(', ')}`);
}

// Auto-wire DRACOLoader on every GLTFLoader (matches production)
// Three.js webgpu bundle exposes GLTFLoader and DRACOLoader as named exports.
//
// DRACO compressed GLBs (NASA, Smithsonian, some Poly Haven) need two
// fixes to load under Deno:
//
//   1. Module workers — DRACOLoader does `new Worker(blobUrl)` with no
//      type option which defaults to a classic worker; Deno only
//      supports `{ type: 'module' }`. Otherwise: "Classic workers are
//      not supported." at parse time, every Draco GLB silently fails.
//
//   2. CommonJS-style globals in the worker scope — the gstatic DRACO
//      decoder JS (emscripten UMD output) references `require`,
//      `module`, `exports`, and `__dirname`. Browser classic workers
//      have those undefined-but-not-throwing. Module workers throw on
//      first reference. Inject no-op shims so the UMD detection sees
//      them and falls through to its global-window branch.
const _OrigWorker = globalThis.Worker;
if (_OrigWorker) {
    globalThis.Worker = class extends _OrigWorker {
        constructor(url, opts) {
            const merged = { ...(opts || {}) };
            if (!merged.type) merged.type = 'module';
            super(url, merged);
        }
    };
}
const _DRACO_CJS_SHIM =
    "// injected — CommonJS shim for emscripten UMD detection\n" +
    "globalThis.require = globalThis.require || (() => ({}));\n" +
    "globalThis.module  = globalThis.module  || { exports: {} };\n" +
    "globalThis.exports = globalThis.exports || globalThis.module.exports;\n" +
    "globalThis.__dirname = globalThis.__dirname || '/';\n" +
    "globalThis.__filename = globalThis.__filename || '/draco_worker.js';\n";

const { GLTFLoader: _OrigGLTF } = await import('npm:three@0.184.0/addons/loaders/GLTFLoader.js');
const { DRACOLoader } = await import('npm:three@0.184.0/addons/loaders/DRACOLoader.js');
const _draco = new DRACOLoader();

// Clone a loaded model SAFELY. `Object3D.clone()` on a rigged/skinned GLB
// shares the ORIGINAL's skeleton — so the clone renders fine while static but
// EXPLODES into disconnected pieces the moment the original's animation plays
// (the clone's vertices skin against bones in the wrong space). SkeletonUtils
// rebinds each clone to its own skeleton. Use `cloneModel(gltf)` (or any
// Object3D) for every duplicate of a fetched model — never `.clone()` on a
// model you also animate.
const { clone: _skeletonClone } = await import('npm:three@0.184.0/addons/utils/SkeletonUtils.js');
globalThis.cloneModel = (objOrGltf) => _skeletonClone(objOrGltf?.scene || objOrGltf);
try { _draco.setDecoderPath('https://www.gstatic.com/draco/v1/decoders/'); } catch {}

// Prepend the CommonJS shim to the first library DRACOLoader loads (the
// emscripten JS wrapper). DRACOLoader concatenates [jsContent,
// workerFnBody] into the worker source, so anything we prefix to
// jsContent ends up at the top of the worker's global scope BEFORE the
// emscripten code runs and trips over missing `require`/`module`.
const _OrigLoadLibrary = _draco._loadLibrary.bind(_draco);
let _dracoLibCallCount = 0;
_draco._loadLibrary = function patchedLoadLibrary(url, responseType) {
    const promise = _OrigLoadLibrary(url, responseType);
    const isJs = responseType === 'text';
    const isFirst = (++_dracoLibCallCount === 1);
    if (isJs && isFirst) {
        return promise.then((jsText) => _DRACO_CJS_SHIM + '\n' + jsText);
    }
    return promise;
};

globalThis.__DRACO_LOADER__ = _draco;
// Convert a Texture(ImageBitmap) → DataTexture by pulling decoded pixels
// directly from Deno's native ImageBitmap via the Deno_bitmapData
// symbol. This is the cheapest viable path on the deno+wgpu-rs+Mesa-
// Gallium-D3D12 backend:
//
//   - `device.queue.copyExternalImageToTexture` is missing entirely from
//     Deno's WebGPU bindings (three.js's call is silently swallowed by
//     `try {} catch (_) {}` at three.webgpu.js:73743 → uploads produce
//     zero pixel data → solid-black silhouettes for GLB materials).
//
//   - Deno's ImageBitmap (ext/image/bitmap.rs) has *already* decoded the
//     PNG/JPEG bytes into a Rust-side `RefCell<DynamicImage>` and exposes
//     them to JS via `Symbol.for("Deno_bitmapData")` → returns a
//     Uint8Array of RGBA pixels. So we let Deno's native createImageBitmap
//     run normally (one decode), and at GLB-load time we pull the bytes
//     via the symbol and build a DataTexture. No second @napi-rs/canvas
//     decode, no fake-IB wrapper, no createImageBitmap override.
//
//   - The DataTexture upload path (writeTexture for mip 0, no auto-mipmap)
//     is the only image upload that works on this stack; the auto-mipmap
//     compute pass produces zero-sampled output at non-base mips (same
//     class of failure as GTAO/SSR's Naga incompat). We set
//     generateMipmaps=false and minFilter=LinearFilter as a result —
//     trade-off is minor aliasing at far distance vs. textures that
//     actually render.
const _DENO_BITMAP_DATA = Symbol.for('Deno_bitmapData');
const _imageBitmapTexCache = new WeakMap();
function _convertGLBTextureToDataTexture(tex) {
    if (!tex || !tex.image || tex.isDataTexture) return tex;
    const img = tex.image;
    // Cache check FIRST — shared images (e.g. metalnessMap+roughnessMap
    // pointing at the same packed PNG, or alpha-packed emissive sharing
    // the diffuse PNG) reuse the same DataTexture without re-pulling
    // pixels via the symbol.
    if (_imageBitmapTexCache.has(img)) {
        return _imageBitmapTexCache.get(img);
    }
    if (typeof img[_DENO_BITMAP_DATA] !== 'function') return tex;
    const raw = img[_DENO_BITMAP_DATA]();
    const w = img.width, h = img.height;
    // Deno's ImageBitmap stores data in the source image's native colour
    // type (DynamicImage::as_bytes()). Need to normalise to RGBA8 for the
    // GPU upload — the wgpu backend doesn't have an RGB8 sized format
    // and three.js's MeshStandardNodeMaterial expects 4-channel maps.
    const total = raw?.length || 0;
    const expectedPixels = w * h;
    let bytesPerPixel;
    if (total === expectedPixels * 4) bytesPerPixel = 4;          // RGBA8 (PNG with alpha)
    else if (total === expectedPixels * 3) bytesPerPixel = 3;      // RGB8 (JPEG / PNG no-alpha)
    else if (total === expectedPixels * 2) bytesPerPixel = 2;      // LA8 (greyscale + alpha)
    else if (total === expectedPixels) bytesPerPixel = 1;          // L8 (greyscale)
    else {
        console.warn(`[GLB migrate] unexpected bitmap data length: ${total} for ${w}x${h} (no clean bpp match)`);
        return tex;
    }
    let data;
    if (bytesPerPixel === 4) {
        data = raw;
    } else {
        // Expand to RGBA8 (alpha=255 for opaque-source formats).
        data = new Uint8Array(expectedPixels * 4);
        if (bytesPerPixel === 3) {
            for (let i = 0, j = 0; i < total; i += 3, j += 4) {
                data[j] = raw[i]; data[j + 1] = raw[i + 1]; data[j + 2] = raw[i + 2]; data[j + 3] = 255;
            }
        } else if (bytesPerPixel === 2) {
            for (let i = 0, j = 0; i < total; i += 2, j += 4) {
                const l = raw[i]; data[j] = l; data[j + 1] = l; data[j + 2] = l; data[j + 3] = raw[i + 1];
            }
        } else {  // L8
            for (let i = 0, j = 0; i < total; i++, j += 4) {
                const l = raw[i]; data[j] = l; data[j + 1] = l; data[j + 2] = l; data[j + 3] = 255;
            }
        }
    }
    const dt = new THREE.DataTexture(
        data, w, h, THREE.RGBAFormat, THREE.UnsignedByteType,
    );
    // Preserve all GLB-authored texture metadata so the material reads
    // exactly what the artist set up. Don't force "expected shapes" onto
    // textures the GLB has already configured (KHR_texture_transform
    // matrices, non-default centers/rotations, premultiplyAlpha, etc.).
    dt.colorSpace = tex.colorSpace;
    dt.wrapS = tex.wrapS; dt.wrapT = tex.wrapT;
    dt.repeat.copy(tex.repeat);
    dt.offset.copy(tex.offset);
    if (tex.center) dt.center.copy(tex.center);
    dt.rotation = tex.rotation;
    if (tex.matrix && dt.matrix) dt.matrix.copy(tex.matrix);
    dt.matrixAutoUpdate = tex.matrixAutoUpdate;
    dt.magFilter = tex.magFilter;
    dt.anisotropy = tex.anisotropy;
    dt.premultiplyAlpha = tex.premultiplyAlpha;
    dt.unpackAlignment = tex.unpackAlignment;
    dt.channel = tex.channel;            // KHR_texture_transform texCoord set
    dt.flipY = false;                    // glTF convention; native flipY is also false
    dt.generateMipmaps = false;          // AUTO-mipmap pass broken on wgpu-rs+Mesa (see header)
    dt.minFilter = THREE.LinearFilter;
    _applyCpuMips(dt);                   // ...but EXPLICIT mip uploads work — see helper
    dt.name = tex.name;
    if (tex.userData) Object.assign(dt.userData, tex.userData);
    dt.needsUpdate = true;
    _imageBitmapTexCache.set(img, dt);
    return dt;
}

// ── Canvas text that FITS ───────────────────────────────────────────────────
// Agents keep drawing fixed-size fillText into fixed-size canvases — long
// labels overflow the box and render cut off. This helper measures, word-wraps,
// and SHRINKS the font until the whole block fits the given box, then draws it.
//
//   drawTextFit(ctx, 'BREAKING: POPE FORKS CHURCH', {
//       x: 256, y: 60, maxWidth: 480, maxHeight: 200,
//       font: 'bold 48px monospace', align: 'center' });
//
// Returns { fontPx, lines } (fontPx < requested = it had to shrink — if it
// shrank a lot, shorten the copy or enlarge the canvas). Respects explicit
// '\n'. align: 'center' (x = box center) | 'left' (x = left edge).
globalThis.drawTextFit = (ctx, text, opts = {}) => {
    const { x = 0, y = 0, maxWidth = 512, maxHeight = Infinity,
            font = 'bold 48px monospace', minPx = 10, lineHeight = 1.25,
            align = 'center', fill } = opts;
    const m = font.match(/(\d+(?:\.\d+)?)px/);
    let px = m ? parseFloat(m[1]) : 48;
    const fontAt = (s) => font.replace(/\d+(?:\.\d+)?px/, `${s}px`);
    let lines = [];
    for (; px >= minPx; px -= Math.max(1, Math.round(px * 0.08))) {
        ctx.font = fontAt(px);
        lines = [];
        let ok = true;
        for (const para of String(text).split('\n')) {
            let cur = '';
            for (const word of para.split(/\s+/)) {
                const test = cur ? cur + ' ' + word : word;
                if (ctx.measureText(test).width <= maxWidth) { cur = test; continue; }
                if (!cur) { ok = false; break; }       // single word too wide at this size
                lines.push(cur); cur = word;
            }
            if (!ok) break;
            lines.push(cur);
        }
        if (ok && lines.length * px * lineHeight <= maxHeight) break;
    }
    ctx.font = fontAt(px);
    if (fill) ctx.fillStyle = fill;
    const prevAlign = ctx.textAlign, prevBase = ctx.textBaseline;
    ctx.textAlign = align === 'center' ? 'center' : 'left';
    ctx.textBaseline = 'top';
    lines.forEach((ln, i) => ctx.fillText(ln, x, y + i * px * lineHeight));
    ctx.textAlign = prevAlign; ctx.textBaseline = prevBase;
    return { fontPx: px, lines };
};

// ── CPU mip chains ──────────────────────────────────────────────────────────
// The stack's AUTO-mipmap compute pass is broken (zero-sampled non-base mips),
// which is why every texture path here historically ran mip-less — the cost
// was crawling dark shimmer on every busy texture at minification, pipeline
// wide (diagnosed + fixed on "the library at the end of context", 2026-06-10).
// EXPLICIT mip uploads work fine: build the chain on the CPU (2×2 box average)
// and hand three.js the levels. Trilinear + anisotropy then behave normally.
// Opt out per-render with NO_CPU_MIPS=1 (or per-texture: tex.userData.noMips).
function _buildCpuMips(data, w, h) {
    const levels = [{ data, width: w, height: h }];
    let sw = w, sh = h, src = data;
    while (sw > 1 || sh > 1) {
        const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1);
        const dst = new Uint8Array(dw * dh * 4);
        for (let y = 0; y < dh; y++) {
            const y0 = Math.min(sh - 1, y * 2), y1 = Math.min(sh - 1, y * 2 + 1);
            for (let x = 0; x < dw; x++) {
                const x0 = Math.min(sw - 1, x * 2), x1 = Math.min(sw - 1, x * 2 + 1);
                for (let c = 0; c < 4; c++) {
                    dst[(y * dw + x) * 4 + c] = (
                        src[(y0 * sw + x0) * 4 + c] + src[(y0 * sw + x1) * 4 + c] +
                        src[(y1 * sw + x0) * 4 + c] + src[(y1 * sw + x1) * 4 + c]) >> 2;
                }
            }
        }
        levels.push({ data: dst, width: dw, height: dh });
        sw = dw; sh = dh; src = dst;
    }
    return levels;
}
function _applyCpuMips(tex) {
    if (Deno.env.get('NO_CPU_MIPS') === '1' || tex.userData?.noMips) return false;
    const img = tex.image;
    if (!img || !(img.data instanceof Uint8Array) || img.data.length !== img.width * img.height * 4) return false;
    if (img.width < 4 && img.height < 4) return false;   // nothing to gain
    tex.mipmaps = _buildCpuMips(img.data, img.width, img.height);
    tex.minFilter = THREE.LinearMipmapLinearFilter;
    tex.generateMipmaps = false;
    if (tex.anisotropy < 8) tex.anisotropy = 8;
    tex.needsUpdate = true;
    return true;
}

// Scene-facing image-to-texture loader. The three.js TextureLoader path
// (ImageLoader → blob URL → fetch) HANGS on this deno+wgpu-rs stack —
// scene scripts that tried it fell back to flat-color materials and
// never used the PBR textures they fetched. This is the working path:
// Deno's native createImageBitmap decodes the PNG/JPEG once, then we
// pull the RGBA bytes via the Deno_bitmapData symbol into a DataTexture
// (same mechanism the GLB migrate hook uses). Accepts raw bytes
// (Uint8Array / ArrayBuffer — e.g. globalThis.ASSETS.foo) and returns a
// ready-to-use texture.
//
//   const albedo = await globalThis.loadImageTexture(ASSETS.concrete_albedo, { srgb: true });
//   const nor    = await globalThis.loadImageTexture(ASSETS.concrete_nor);   // linear (default)
//   albedo.repeat.set(8, 8); albedo.wrapS = albedo.wrapT = THREE.RepeatWrapping;
//   const mat = new THREE.MeshStandardNodeMaterial({ map: albedo, normalMap: nor });
globalThis.loadImageTexture = async (bytes, opts = {}) => {
    const u8 = bytes instanceof Uint8Array ? bytes
             : bytes instanceof ArrayBuffer ? new Uint8Array(bytes)
             : new Uint8Array(globalThis.b64toArrayBuffer(bytes));
    const blob = new Blob([u8]);
    const bitmap = await createImageBitmap(blob);  // Deno native, single decode

    const w = bitmap.width, h = bitmap.height;
    let data;
    if (typeof bitmap[_DENO_BITMAP_DATA] === 'function') {
        const raw = bitmap[_DENO_BITMAP_DATA]();
        const total = raw?.length || 0;
        const px = w * h;
        if (total === px * 4) {
            data = raw;
        } else if (total === px * 3) {
            data = new Uint8Array(px * 4);
            for (let i = 0, j = 0; i < total; i += 3, j += 4) {
                data[j] = raw[i]; data[j+1] = raw[i+1]; data[j+2] = raw[i+2]; data[j+3] = 255;
            }
        } else if (total === px * 2) {
            data = new Uint8Array(px * 4);
            for (let i = 0, j = 0; i < total; i += 2, j += 4) {
                const l = raw[i]; data[j] = l; data[j+1] = l; data[j+2] = l; data[j+3] = raw[i+1];
            }
        } else if (total === px) {
            data = new Uint8Array(px * 4);
            for (let i = 0, j = 0; i < total; i++, j += 4) {
                const l = raw[i]; data[j] = l; data[j+1] = l; data[j+2] = l; data[j+3] = 255;
            }
        } else {
            throw new Error(`loadImageTexture: unexpected bitmap data length ${total} for ${w}x${h}`);
        }
    } else {
        throw new Error('loadImageTexture: Deno_bitmapData symbol unavailable — cannot decode image on this stack');
    }

    // flipY is IGNORED by the DataTexture upload path on this stack (same
    // as GLB textures). Browser convention is flipY=true (image top → UV
    // top), so we bake the vertical flip into the pixel rows by default.
    // Baking (vs repeat/offset V-flip) means it composes cleanly with
    // `repeat.set(n,n)` tiling for PBR maps. Pass { flipY: false } to skip
    // (e.g. glTF-convention textures that already expect no flip).
    if (opts.flipY !== false) {
        const flipped = new Uint8Array(data.length);
        const rowBytes = w * 4;
        for (let row = 0; row < h; row++) {
            const src = row * rowBytes;
            const dst = (h - 1 - row) * rowBytes;
            flipped.set(data.subarray(src, src + rowBytes), dst);
        }
        data = flipped;
    }

    const tex = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
    tex.colorSpace = opts.srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    tex.wrapS = tex.wrapT = opts.wrap ?? THREE.RepeatWrapping;
    tex.magFilter = THREE.LinearFilter;
    tex.minFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;          // AUTO pass broken; explicit chain below
    tex.flipY = false;
    _applyCpuMips(tex);
    tex.needsUpdate = true;
    return tex;
};

// Some GLBs use a "alpha-of-diffuse-as-emissive-mask" packing: the
// baseColorTexture and emissiveTexture point at the same image, the
// artist intends the diffuse RGB to colour the surface and the alpha
// channel to gate where it's emissive (e.g. car body neon strips,
// window edges, tail lights). Three.js's MeshPhysicalNodeMaterial
// reads emissiveMap.rgb for the emissive contribution, so naive
// migration ends up pumping the entire diffuse colour set into the
// emissive output — sci-fi car bodies "glow" with all their paint
// colours, including the matte body. Detect the shared-image case and
// produce a separate emissive DataTexture whose RGB = original alpha,
// so Three's `.rgb` sample returns the alpha mask.
function _alphaToRgbEmissive(THREE, sourceData, w, h) {
    const out = new Uint8Array(w * h * 4);
    for (let i = 0, j = 0; i < w * h; i++, j += 4) {
        const a = sourceData[j + 3];
        out[j] = a; out[j + 1] = a; out[j + 2] = a; out[j + 3] = 255;
    }
    return out;
}
function _alphaPackedEmissiveFixup(mat) {
    if (!mat || !mat.map || !mat.emissiveMap) return false;
    if (mat.map !== mat.emissiveMap) return false;  // not the shared-image case
    if (!mat.map.isDataTexture) return false;        // shouldn't happen post-migrate
    const srcData = mat.map.image?.data;
    const w = mat.map.image?.width, h = mat.map.image?.height;
    if (!srcData || !w || !h) return false;
    const alphaRgb = _alphaToRgbEmissive(THREE, srcData, w, h);
    const dt = new THREE.DataTexture(alphaRgb, w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
    dt.colorSpace = THREE.SRGBColorSpace;  // emissive is in sRGB color space (matches diffuse colorSpace convention)
    dt.wrapS = mat.map.wrapS; dt.wrapT = mat.map.wrapT;
    dt.repeat.copy(mat.map.repeat); dt.offset.copy(mat.map.offset);
    if (mat.map.center) dt.center.copy(mat.map.center);
    dt.rotation = mat.map.rotation;
    if (mat.map.matrix && dt.matrix) dt.matrix.copy(mat.map.matrix);
    dt.matrixAutoUpdate = mat.map.matrixAutoUpdate;
    dt.magFilter = mat.map.magFilter;
    dt.anisotropy = mat.map.anisotropy;
    dt.flipY = false;
    dt.generateMipmaps = false;
    dt.minFilter = THREE.LinearFilter;
    _applyCpuMips(dt);
    dt.name = (mat.map.name || '') + '_alphaEmissive';
    dt.needsUpdate = true;
    mat.emissiveMap = dt;
    mat.needsUpdate = true;
    return true;
}

function _migrateMaterialTextures(mat, log = false) {
    if (!mat) return 0;
    // Iterate every property on the material. Any value that's a Three
    // Texture (or subclass like CompressedTexture) is a candidate for
    // migration — this catches texture slots from glTF extensions we
    // don't have hardcoded (KHR_materials_anisotropy.anisotropyMap,
    // KHR_materials_diffuse_transmission, future ones) without knowing
    // about them ahead of time. We DO NOT enumerate a fixed slot list:
    // GLB authors can use any slot the Three material exposes, and the
    // migration must respect that.
    let migrated = 0;
    let unhandled = 0;
    for (const slot of Object.keys(mat)) {
        const t = mat[slot];
        if (!t || typeof t !== 'object') continue;
        // Skip non-Texture values
        if (!t.isTexture) continue;
        // Already a DataTexture (e.g. cached migration result) — no work
        if (t.isDataTexture) continue;
        if (!t.image) continue;
        // Compressed (KTX2 / Basis) textures don't have a decoded RGBA
        // ImageBitmap — they need a separate path. Track and warn.
        if (t.isCompressedTexture) {
            if (log) console.log(`[GLB migrate] ${mat.type}.${slot}: compressed texture (KTX2/Basis) — not yet supported`);
            unhandled++;
            continue;
        }
        const hasSymbol = typeof t.image[_DENO_BITMAP_DATA] === 'function';
        const cached = _imageBitmapTexCache.has(t.image);
        if (log) console.log(`[GLB migrate] ${mat.type}.${slot}: ib=${hasSymbol} cached=${cached}`);
        if (hasSymbol || cached) {
            mat[slot] = _convertGLBTextureToDataTexture(t);
            migrated++;
        } else {
            // Texture present but not from a Deno ImageBitmap and not in
            // the cache — could be a CanvasTexture, RT, or shim source.
            // Leave it alone; it's the scene script's responsibility.
            if (log) console.log(`[GLB migrate] ${mat.type}.${slot}: image is ${t.image?.constructor?.name} — leaving as-is`);
        }
    }
    if (unhandled > 0) {
        console.warn(`[GLB migrate] ${mat.type}: ${unhandled} unhandled texture(s) (compressed/KTX2 not yet supported on this stack)`);
    }
    return migrated;
}
function _migrateGltfTextures(gltf) {
    if (!gltf?.scene) return;
    let totalSlots = 0, totalMats = 0, firstMat = true;
    gltf.scene.traverse((o) => {
        if (o.isMesh) {
            const mats = Array.isArray(o.material) ? o.material : [o.material];
            for (const m of mats) {
                if (!m) continue;
                totalMats++;
                totalSlots += _migrateMaterialTextures(m, firstMat);
                firstMat = false;
            }
        }
    });
    console.log(`[GLB texture migrate] visited ${totalMats} material(s), migrated ${totalSlots} texture slot(s) → DataTexture`);
}

globalThis.GLTFLoader = class extends _OrigGLTF {
    constructor(...args) {
        super(...args);
        try { this.setDRACOLoader(_draco); } catch {}
    }
    parse(...args) {
        const origOnLoad = args[2];
        args[2] = (gltf) => {
            try {
                _migrateGltfTextures(gltf);
                if (gltf?.userData?.vrm) {
                    if (!globalThis._vrm) {
                        globalThis._vrm = gltf.userData.vrm;
                        console.log('[render_scene] auto-captured globalThis._vrm');
                    }
                    if (gltf.userData.vrm.scene) gltf.userData.vrm.scene.userData.vrm = gltf.userData.vrm;
                }
            } catch (e) { console.warn('[GLB texture migrate] failed:', e.message); }
            if (origOnLoad) origOnLoad(gltf);
        };
        return super.parse(...args);
    }
};

// === LEGACY-COMPAT SHIM (not part of the WebGPU pipeline) ===
// Existing scene scripts authored against production render_scene.mjs (the
// Playwright/WebGL pipeline) construct `new THREE.WebGLRenderer(...)`.
// We auto-upgrade those constructions to `WebGPURenderer` with the
// harness adapter/device so unmodified WebGL-era scenes can still run.
// Loud warning per construction — never silent. The post-setup() assertion
// below confirms the resulting renderer instance IS in fact WebGPU.
//
// New scene scripts authored against this deno pipeline should construct
// `new THREE.WebGPURenderer({ adapter: GPU_ADAPTER, device: GPU_DEVICE })`
// directly and not rely on this shim.
const _OrigWebGPURenderer = THREE.WebGPURenderer;
let _webglUpgradeCount = 0;
THREE.WebGLRenderer = class extends _OrigWebGPURenderer {
    constructor(opts = {}) {
        _webglUpgradeCount++;
        if (_webglUpgradeCount === 1) {
            console.warn('[render_scene] WARNING: scene used new THREE.WebGLRenderer() — auto-upgrading to WebGPURenderer with harness adapter/device. Future warnings suppressed.');
        }
        // Force antialias OFF: with our FakeGPUCanvasContext, Three's MSAA
        // path renders to an internal multisample target that never resolves
        // to the swap-chain texture our readback reads → black mp4. Real MSAA
        // would need a renderer-managed RenderTarget + manual resolve.
        // preserveDrawingBuffer is a WebGL-only knob; harmless on WebGPU but
        // strip it to avoid surprising warnings.
        const { antialias: _drop_aa, preserveDrawingBuffer: _drop_pdb, ...rest } = opts;
        super({ ...rest, antialias: false, adapter: GPU_ADAPTER, device: GPU_DEVICE });
        // WebGL-era scene scripts don't `await renderer.init()` because WebGL
        // doesn't need it. WebGPU does — and 0.184 throws hard if render() is
        // called before init completes. Eagerly start init and expose the
        // promise so the render loop can await it before the first frame.
        try { this._initPromise = this.init(); } catch {}
    }
};
if (THREE.WebGL1Renderer) THREE.WebGL1Renderer = THREE.WebGLRenderer;

// (No createImageBitmap override needed — Deno's native createImageBitmap
// decodes once into a Rust-side DynamicImage, and the GLTFLoader migrate
// hook above pulls pixels via the Deno_bitmapData symbol when wrapping
// the texture as a DataTexture. Single decode per image, no
// @napi-rs/canvas dependency for this path.)

// === @napi-rs/canvas COMPAT SHIM (not part of the WebGPU pipeline) ===
// Deno's `@napi-rs/canvas` is the only canvas implementation usable in
// the headless harness, but its canvas instances are not valid texture
// sources for `WebGPURenderer` (which expects HTMLCanvasElement /
// OffscreenCanvas / ImageBitmap). When a scene script creates a
// `THREE.CanvasTexture(canvas)` against a shim canvas, we snapshot the
// pixels via getImageData, build a DataTexture, and re-expose the
// CanvasTexture-shaped surface area scenes use (`.image = newCanvas;
// tex.needsUpdate = true`) via the same shim so refresh works.
//
// In a real browser environment with HTMLCanvasElement / OffscreenCanvas
// this shim would be a no-op delegate to the original CanvasTexture.
const _OrigCanvasTexture = THREE.CanvasTexture;
class _ShimAwareCanvasTexture extends THREE.DataTexture {
    constructor(canvas, ...rest) {
        if (canvas && canvas._isShimCanvas) {
            const img = canvas.getImageDataRGBA();
            super(new Uint8Array(img.data.buffer.slice(0)), img.width, img.height, THREE.RGBAFormat, THREE.UnsignedByteType);
            this.colorSpace = THREE.SRGBColorSpace;
            this.wrapS = this.wrapT = THREE.ClampToEdgeWrapping;
            this.minFilter = THREE.LinearFilter;
            this.magFilter = THREE.LinearFilter;
            this.generateMipmaps = false;
            // Canvas-2D pixel data is row-major top-down — row 0 is the
            // canvas's TOP. Three.js samplers on this stack treat V=0 as
            // the texture's BOTTOM, so without compensation the canvas
            // renders upside-down. The texture's `flipY` flag is ignored
            // by the DataTexture upload path here, so we apply a
            // UV-transform reflection (V → 1-V) via repeat/offset; this
            // travels with the texture regardless of which mesh / sprite
            // material samples it.
            this.repeat.set(1, -1);
            this.offset.set(0, 1);
            this._isShimCanvasTexture = true;
            this._sourceCanvas = canvas;
            // Auto-re-snapshot on `tex.needsUpdate = true`. Without this,
            // scenes that draw new canvas-2D content per frame and set
            // needsUpdate (the documented three.js pattern) would just
            // re-upload the stale frame-0 pixel snapshot and the panel
            // would freeze on its first drawn state.
            Object.defineProperty(this, 'needsUpdate', {
                configurable: true,
                get() { return false; },
                set(v) {
                    if (v === true) {
                        this.refresh();
                    }
                },
            });
            this.refresh();
        } else {
            // Non-shim source — use the original CanvasTexture by delegating.
            const real = new _OrigCanvasTexture(canvas, ...rest);
            super(null, real.image?.width || 1, real.image?.height || 1);
            this.image = real.image;
            this.needsUpdate = true;
        }
    }
    /** Re-snapshot from the source shim canvas (call when canvas content has changed). */
    refresh() {
        if (this._sourceCanvas && this._sourceCanvas._isShimCanvas) {
            const img = this._sourceCanvas.getImageDataRGBA();
            this.image = { data: new Uint8Array(img.data.buffer.slice(0)), width: img.width, height: img.height };
            // Bump the version directly — `this.needsUpdate = true` would
            // recurse into the property setter above.
            this.version++;
            if (this.source) this.source.needsUpdate = true;
        }
    }
}
THREE.CanvasTexture = _ShimAwareCanvasTexture;

// VRM addons — WebGPU-native wiring.
//
// @pixiv/three-vrm 3.4+ ships a NodeMaterial-based MToon (`MToonNodeMaterial`)
// at `@pixiv/three-vrm-materials-mtoon/nodes`. The default
// `MToonMaterialLoaderPlugin` constructs the WebGL `MToonMaterial`
// (`ShaderMaterial`-based) which can't be auto-converted into a WebGPU
// node material. We wrap the upstream `VRMLoaderPlugin` so every
// scene-script `new VRMLoaderPlugin(parser)` call automatically gets a
// MToon plugin configured with `materialType: MToonNodeMaterial` —
// scene scripts don't have to know about the WebGPU plumbing.
try {
    const vrmMod  = await import('npm:@pixiv/three-vrm@3.5.2');
    const mtoonMod = await import('npm:@pixiv/three-vrm-materials-mtoon@3.5.2');
    const mtoonNodeMod = await import('npm:@pixiv/three-vrm-materials-mtoon@3.5.2/nodes');
    const _OrigVRMLoaderPlugin = vrmMod.VRMLoaderPlugin;
    const { MToonMaterialLoaderPlugin } = mtoonMod;
    const { MToonNodeMaterial } = mtoonNodeMod;

    globalThis.VRMLoaderPlugin = class extends _OrigVRMLoaderPlugin {
        constructor(parser, options = {}) {
            // Build a MToon plugin with WebGPU NodeMaterial unless the
            // caller already supplied their own mtoonMaterialPlugin.
            if (!options.mtoonMaterialPlugin) {
                options = {
                    ...options,
                    mtoonMaterialPlugin: new MToonMaterialLoaderPlugin(parser, {
                        materialType: MToonNodeMaterial,
                    }),
                };
            }
            super(parser, options);
        }
    };
    globalThis.VRMUtils = vrmMod.VRMUtils;
    globalThis.MToonNodeMaterial = MToonNodeMaterial;
    globalThis.MToonMaterialLoaderPlugin = MToonMaterialLoaderPlugin;

    const vrmaMod = await import('npm:@pixiv/three-vrm-animation@3.5.2');
    globalThis.VRMAnimationLoaderPlugin = vrmaMod.VRMAnimationLoaderPlugin;
    globalThis.createVRMAnimationClip = vrmaMod.createVRMAnimationClip;

    // One-call helper for scene scripts. Parses a base64-encoded .vrma,
    // builds an AnimationClip retargeted to `vrm`, creates an
    // AnimationMixer on the VRM scene root, plays it, and assigns to
    // `globalThis._mixer` so the render loop's per-frame
    // `_mixer.update(dt)` (further down in this file) auto-steps it.
    // Returns { mixer, action, clip } for callers that need to chain
    // crossfades or stop playback. opts.loop=false → LoopOnce + clamp.
    // opts.fade=<seconds> → EASE from the VRM's current clip into this one
    // (crossfade on a shared mixer) instead of hard-cutting. This is the fix for
    // the pose POP between emotes (walk→salute→cheer→sit). Without a prior clip
    // (or fade=0) it hard-cuts as before.
    globalThis.playVRMAFromBase64 = async (vrm, b64, opts = {}) => {
        if (!vrm)  throw new Error('playVRMAFromBase64: vrm is required');
        if (!b64)  throw new Error('playVRMAFromBase64: b64 is required');
        const THREE = globalThis.THREE;
        const aLoader = new globalThis.GLTFLoader();
        aLoader.register((p) => new globalThis.VRMAnimationLoaderPlugin(p));
        const buf = globalThis.b64toArrayBuffer(b64);
        const animGltf = await new Promise((res, rej) => aLoader.parse(buf, '', res, rej));
        const vrmAnim = animGltf?.userData?.vrmAnimations?.[0];
        if (!vrmAnim) throw new Error('playVRMAFromBase64: parsed VRMA contained no animation');
        const clip = globalThis.createVRMAnimationClip(vrmAnim, vrm);
        // Per-VRM mixer registry so MULTIPLE characters each animate every frame.
        // The render loop drives every registered (vrm → mixer); without this only
        // the single globalThis._mixer/_vrm advanced, so a 2nd VRM froze or
        // mis-posed (stood in its chair / sank through the seat).
        const _reg = globalThis._vrmMixers || (globalThis._vrmMixers = new Map());
        const _prev = _reg.get(vrm);
        const fade = Math.max(0, opts.fade || 0);
        // CROSSFADE PATH: reuse the SAME mixer so the previous action can ease into
        // the new one (crossFadeFrom needs both actions on one mixer). A new mixer
        // per call (the hard-cut path below) cannot crossfade — that was the pop.
        if (_prev && _prev.mixer && _prev.action && fade > 0) {
            const mixer = _prev.mixer;
            const action = mixer.clipAction(clip);
            action.reset();
            if (opts.loop === false) { action.setLoop(THREE.LoopOnce); action.clampWhenFinished = true; }
            action.enabled = true; action.setEffectiveWeight(1); action.play();
            action.crossFadeFrom(_prev.action, fade, false);
            _reg.set(vrm, { mixer, action });
            globalThis._mixer = mixer;
            return { mixer, action, clip };
        }
        // HARD-CUT PATH (no prior clip, or fade=0): fresh mixer, stop the old.
        if (_prev && _prev.mixer) { try { _prev.mixer.stopAllAction(); } catch (e) {} }
        const mixer = new THREE.AnimationMixer(vrm.scene);
        const action = mixer.clipAction(clip);
        if (opts.loop === false) {
            action.setLoop(THREE.LoopOnce);
            action.clampWhenFinished = true;
        }
        action.play();
        _reg.set(vrm, { mixer, action });   // store action so the NEXT call can crossFadeFrom it
        globalThis._mixer = mixer;   // backcompat: latest
        return { mixer, action, clip };
    };

    // Locomotion clips TRANSLATE the body by design. Played directly via this
    // wrapper they cycle the legs while the VRM stays bolted in place — the
    // "walking in place" treadmill. Locomotion is OWNED by VRMCharacterController
    // (it couples stride to real travel + grounds the feet with IK). So this
    // door is closed: the illegal state is unrepresentable, not merely detected
    // after the render. Stationary clips (idle, dance, wave, raise, salute,
    // cheer, sit…) pass freely. The one legitimate exception — a VRM genuinely
    // standing on a treadmill / carried by a vehicle — opts in with
    // { force: true } or globalThis._allowManualLocomotion = true (the same flag
    // the foot-slide detector honors).
    const _LOCOMOTION_SLOTS = new Set(['walk', 'run', 'fastRun', 'slowRun',
        'sneak', 'walkBackward', 'stairsUp', 'stairsDown', 'stairsRunUp', 'stairsRunDown']);

    // Convenience wrapper for the slot-keyed defaults loaded above.
    globalThis.playVRMADefault = async (vrm, slot, opts = {}) => {
        if (_LOCOMOTION_SLOTS.has(slot) && !opts.force && !globalThis._allowManualLocomotion) {
            throw new Error(`playVRMADefault: "${slot}" is a LOCOMOTION clip — playing it directly leaves the VRM walking in place (the treadmill bug). Route locomotion through VRMCharacterController (walkTo(x,z), or a waypoint with action:'${slot}'); it moves the body AND grounds the feet. Stationary clips (idle, dance, wave, raise, salute, cheer, sit…) are fine here. If the VRM is genuinely on a treadmill or carried by a vehicle, pass { force: true } or set globalThis._allowManualLocomotion = true.`);
        }
        const b64 = globalThis.VRMA_DEFAULTS_B64?.[slot];
        if (!b64) throw new Error(`playVRMADefault: no VRMA loaded for slot "${slot}". Available: ${Object.keys(globalThis.VRMA_DEFAULTS_B64 || {}).join(', ') || '(none)'}`);
        return globalThis.playVRMAFromBase64(vrm, b64, opts);
    };

    // Play a fetched GLB/glTF model's OWN embedded animations (gltf.animations).
    // Many fetched models (robot arms, machines, doors, rigged props) SHIP with
    // their animation — but agents kept faking motion (rotating a static arm into
    // the ground, bolting on cylinder geo) because there was no easy way to play
    // it. This builds a mixer, plays the requested clip(s), and REGISTERS the
    // mixer for automatic per-frame update (a forgotten mixer.update() is the
    // usual reason "the model's animation doesn't play"). ALWAYS check for and
    // play a model's embedded animation before hand-animating it.
    //   gltf:  the GLTFLoader result ({ scene, animations }) or any object with those
    //   opts.clip: clip name (string) or index (number) to play. DEFAULT: the
    //     FIRST clip only. Pass 'all' ONLY if the model is authored for its
    //     clips to layer — playing multiple clips that each drive the same
    //     joints stacks conflicting transforms and EXPLODES the model into
    //     disconnected pieces.
    //   opts.loop: THREE.LoopRepeat (default) | THREE.LoopOnce
    //   opts.timeScale: playback rate (default 1)
    // returns { mixer, actions } (mixer auto-updates; you don't need to call it).
    globalThis.playModelAnimations = (gltf, opts = {}) => {
        const THREE = globalThis.THREE;
        const root = gltf.scene || gltf;
        const clips = (gltf.animations && gltf.animations.length ? gltf.animations
            : (root && root.animations) || []);
        if (!clips || !clips.length) {
            console.warn('[playModelAnimations] model has no embedded animations (gltf.animations empty) — nothing to play');
            return { mixer: null, actions: [] };
        }
        const mixer = new THREE.AnimationMixer(root);
        const loop = opts.loop ?? THREE.LoopRepeat;
        // Default to the FIRST clip. Stacking all clips on the same nodes is the
        // usual cause of a model exploding into disconnected pieces.
        let chosen;
        if (opts.clip === 'all') {
            chosen = clips;
        } else if (opts.clip !== undefined) {
            const c = (typeof opts.clip === 'number') ? clips[opts.clip]
                : clips.find((cl) => cl.name === opts.clip);
            chosen = c ? [c] : [clips[0]];
        } else {
            chosen = [clips[0]];
            if (clips.length > 1) {
                console.log(`[playModelAnimations] ${clips.length} clips present (${clips.map(c=>c.name||'?').join(', ')}); playing the first ('${clips[0].name||'0'}'). Pass {clip:'<name>'} to choose, or {clip:'all'} only if they're meant to layer.`);
            }
        }
        const actions = chosen.map((cl) => {
            const a = mixer.clipAction(cl);
            a.setLoop(loop, Infinity);
            if (loop === THREE.LoopOnce) a.clampWhenFinished = true;
            a.timeScale = opts.timeScale ?? 1;
            a.play();
            return a;
        });
        (globalThis._autoMixers = globalThis._autoMixers || []).push(mixer);
        console.log(`[playModelAnimations] playing ${actions.length}/${clips.length} embedded clip(s): ${chosen.map(c=>c.name||'(unnamed)').join(', ')}`);
        return { mixer, actions };
    };

    console.log('[render_scene] VRM modules loaded — VRMLoaderPlugin auto-wires MToonNodeMaterial for WebGPU; playVRMAFromBase64/playVRMADefault helpers installed');
} catch (e) {
    console.log('[render_scene] VRM modules skipped:', e.message);
}

// --- Run scene script ---
console.log('[render_scene] Executing scene script...');
try {
    (0, eval)(sceneScript);
    console.log('[render_scene] Scene script executed OK');
} catch (e) {
    console.error('[render_scene] Scene script FAILED:', e.message, e.stack);
    Deno.exit(1);
}

// Screen-space overlay layer — HUD / lower-thirds / motion-graphics that must
// sit ABOVE the world (incl. depth-keyed effects like volumetric_clouds) yet
// still receive screen-space effects (vhs/glitch). Creates a transparent
// overlay scene + a STATIC camera at the origin matching the main camera's FOV
// (so meshes parented to it at z=-1 are screen-locked), and registers the
// globals the auto-enhance graph composites between the depth-keyed and
// screen-space effect stages (a second pass() node, NOT a 2nd renderer.render
// — that ghosts). Position overlay meshes in camera-local space at z=-1, sized
// to the frustum: halfH = tan(fovRad/2), halfW = halfH * (WIDTH/HEIGHT).
globalThis.makeOverlayLayer = (opts = {}) => {
    const ovScene = new THREE.Scene();
    ovScene.background = null;                                  // transparent → only your meshes composite
    const aspect = (globalThis.WIDTH || 1280) / (globalThis.HEIGHT || 720);
    const cam = new THREE.PerspectiveCamera(opts.fov ?? 50, aspect, opts.near ?? 0.01, opts.far ?? 10);
    ovScene.add(cam);
    globalThis._overlayScene = ovScene;
    globalThis._overlayCamera = cam;
    return {
        scene: ovScene,
        camera: cam,
        // add(mesh) parents to the static cam so it's screen-locked. Give
        // overlay materials transparent:true + depthTest:false; set
        // renderOrder for internal sort. depthWrite is irrelevant (own pass).
        add: (obj) => { cam.add(obj); return obj; },
    };
};

console.log('[render_scene] Calling setup()...');
try {
    if (typeof globalThis.setup !== 'function') throw new Error('Scene must define globalThis.setup() (or window.setup())');
    await globalThis.setup();
    console.log('[render_scene] setup() completed OK');

    // Post-setup placement audit. Runs once after the scene is fully built but
    // before any frames render — fixes placement mistakes (model placed inside
    // another model; prop hovering just above a surface). AUTO-FIX IS ON BY
    // DEFAULT now (clipping pairs get pushed apart, near-surface hovering objects
    // get snapped down) because advisory-only warnings were routinely ignored by
    // weaker subagents → shipped videos full of clipping/floating props. It runs
    // ONCE post-setup (not per-frame), so no jitter, and it's a no-op on scenes
    // already placed correctly. Truly-floating "void/far" objects (nothing
    // beneath) still HARD-WARN (can't be safely snapped). Opt OUT of auto-fix
    // with `_noAutoFixPlacement = true` (revert to warn-only); opt out of the
    // whole audit with `_noAutoPlacementCheck = true` (e.g. a VRM intentionally
    // in a cockpit, or a deliberate floating-objects scene). Per-object opt-outs:
    // `userData.noSupportCheck` (hovering) / `userData.noClippingCheck` (clipping).
    if (!globalThis._noAutoPlacementCheck) {
        const sceneRoot = globalThis._scene || globalThis._s;
        if (sceneRoot) {
            const autoFix = globalThis._noAutoFixPlacement !== true;   // default ON
            if (typeof globalThis.checkClipping === 'function') globalThis.checkClipping(sceneRoot, { autoFix });
            const _hover = (typeof globalThis.checkHovering === 'function')
                ? (globalThis.checkHovering(sceneRoot, { autoFix }) || []) : [];
            if (typeof globalThis.checkDensity === 'function') globalThis.checkDensity(sceneRoot);
            // Coplanar surfaces placed at the EXACT same depth (decal/panel flush on
            // a wall/floor) flicker — auto-nudge the thin one a few mm proud.
            if (typeof globalThis.checkZFighting === 'function') globalThis.checkZFighting(sceneRoot, { autoFix });
            // A tall object planted IN a conveyor/belt/line (robot arm standing in
            // the middle of its own conveyor) — semantic placement audit.
            if (typeof globalThis.checkLineIntrusion === 'function') globalThis.checkLineIntrusion(sceneRoot);
            // OPT-OUT TRANSPARENCY: every audit opt-out is honored, but NONE are
            // silent. An opt-out is a declaration of intent ("this crab slides
            // sideways on purpose") — slapping one on to make a warning go away
            // is the warning, unfixed. Surface them all so the muzzle itself is
            // visible in the log.
            try {
                const optOuts = {};
                sceneRoot.traverse(o => {
                    for (const flag of ['noSupportCheck', 'noClippingCheck', 'noMotionCheck', 'noIntrusionCheck', 'noZFightCheck']) {
                        if (o.userData?.[flag]) (optOuts[flag] = optOuts[flag] || []).push(o.name || '(unnamed)');
                    }
                });
                for (const [flag, names] of Object.entries(optOuts)) {
                    const shown = names.slice(0, 8).join(', ') + (names.length > 8 ? ` …+${names.length - 8}` : '');
                    console.log(`[audit-optout] ${flag} on ${names.length} object(s): ${shown} — each must be a DELIBERATE choice (a real floater / intentional slide / planned overlap). If any was added to silence a warning, the warning was the bug: remove the flag and fix the placement/heading instead.`);
                }
            } catch (e) { /* transparency must never break the render */ }
            // Vociferous escalation. 'void' (no surface beneath) and 'far'
            // (floating >1m above the nearest surface) are almost always a prop
            // dumped in mid-air by hand-coords instead of placeOn — and autoFix
            // can't snap them (no/uncertain target). Flag as a hard re-render.
            const _floaters = _hover.filter((h) => h.kind === 'void' || h.kind === 'far');
            if (_floaters.length) {
                const names = _floaters.slice(0, 6).map((h) => h.obj.name || '(unnamed)').join(', ');
                console.warn(`[placement] ⚠ RE-RENDER REQUIRED — ${_floaters.length} object(s) floating with no/far support: ${names}. Rest props on their surface with placeOn(obj, surface) — hand-set coordinates don't express what sits on what, so props end up hovering in mid-air far from where they belong. If a floater is genuinely meant to fly, mark obj.userData.noSupportCheck = true. Treat this as a hard fail like a black frame.`);
            } else {
                console.log('[placement] OK — every solid prop rests on a surface (or is marked noSupportCheck).');
            }
        }
    }
} catch (e) {
    console.error('[render_scene] setup() FAILED:', e.message);
    if (e.stack) console.error(e.stack.split('\n').slice(0, 8).join('\n'));
    Deno.exit(1);
}

// Default environment fallback — installed when the scene script didn't
// set its own scene.environment in setup(). Synthesizes a procedural
// sky-gradient equirect tinted from scene.background and assigns it as
// scene.environment with a low intensity (0.3) so direct lighting and
// SSR contribute the dominant lit appearance.
//
// Limitations of this fallback:
//   - No PMREM filtering — roughness sampling on metals doesn't blur
//     across mip levels; reflections look "all the same".
//   - Low intensity (0.3) — fully-metallic materials (metalness=1)
//     reflect at ~30% of the sky colour, not enough for a chrome look.
//
// Scene scripts that load PBR-heavy GLBs (especially fully-metallic
// painted bodies from the assets4videoagent kit) should override:
//   - scene.environment = <real HDRI> via fetch_hdri.py output, OR
//   - bump scene.environmentIntensity (e.g. 1.0+) for the procedural one.
//
// PMREM-the-fallback is left as future work — the WebGPU
// PMREMGenerator throws "Texture already initialized" when invoked
// between renderer.init() and the first frame, and the right fix is
// either a different timing or a fresh-RT workaround that hasn't been
// validated yet.
//
// SKIPPED when volumetric_clouds is in 'outdoor' mode — its cloud-reflect
// hook is the metal-reflection source there, and stacking an env-map on
// top drowns out the SSR/cloud contributions on chrome surfaces.
{
    const scene = globalThis._scene || globalThis._s;
    const renderer = globalThis._renderer || globalThis._r;
    // Always install the env-fallback if the scene didn't set its own. The
    // cloud-reflect hook handles metal SPECULAR reflection, but transmission
    // and refraction (MeshPhysicalMaterial.transmission > 0) still need an
    // env to sample for the refracted color. Without env, transmissive
    // surfaces (glass, transparent plastic) render as black voids. The
    // env-fallback's intensity is 0.3 so its contribution to metal specular
    // is minimal relative to the cloud-reflect's bright cloud detail.
    const cloudReflectActive = typeof globalThis._autoEnhanceCloudReflectHook === 'function';
    // Skip the fallback when the scene set EITHER env slot — the documented
    // HDRI recipe uses scene.environmentNode (pmremTexture), and installing
    // the gradient on top of it double-lights the scene.
    if (scene && renderer && !scene.environment && !scene.environmentNode) {
        try {
            const THREE_NS = globalThis.THREE;
            const W = 256, H = 128;
            const data = new Uint8Array(W * H * 4);
            const bgColor = (scene.background && scene.background.isColor)
                ? scene.background : new THREE_NS.Color(0x6090b0);
            const horizonRGB = [bgColor.r, bgColor.g, bgColor.b];
            const zenithRGB  = [
                Math.min(horizonRGB[0] * 1.20, 1.0),
                Math.min(horizonRGB[1] * 1.20, 1.0),
                Math.min(horizonRGB[2] * 1.20, 1.0),
            ];
            const groundRGB = [
                horizonRGB[0] * 0.55,
                horizonRGB[1] * 0.55,
                horizonRGB[2] * 0.55,
            ];
            for (let y = 0; y < H; y++) {
                const v = y / (H - 1);
                let r, g, b;
                if (v < 0.5) {
                    const t = v * 2;
                    r = zenithRGB[0] * (1 - t) + horizonRGB[0] * t;
                    g = zenithRGB[1] * (1 - t) + horizonRGB[1] * t;
                    b = zenithRGB[2] * (1 - t) + horizonRGB[2] * t;
                } else {
                    const t = (v - 0.5) * 2;
                    r = horizonRGB[0] * (1 - t) + groundRGB[0] * t;
                    g = horizonRGB[1] * (1 - t) + groundRGB[1] * t;
                    b = horizonRGB[2] * (1 - t) + groundRGB[2] * t;
                }
                const r8 = (r * 255) | 0;
                const g8 = (g * 255) | 0;
                const b8 = (b * 255) | 0;
                for (let x = 0; x < W; x++) {
                    const idx = (y * W + x) * 4;
                    data[idx + 0] = r8;
                    data[idx + 1] = g8;
                    data[idx + 2] = b8;
                    data[idx + 3] = 255;
                }
            }
            const equiTex = new THREE_NS.DataTexture(data, W, H, THREE_NS.RGBAFormat);
            equiTex.mapping = THREE_NS.EquirectangularReflectionMapping;
            equiTex.minFilter = THREE_NS.LinearFilter;
            equiTex.magFilter = THREE_NS.LinearFilter;
            equiTex.colorSpace = THREE_NS.SRGBColorSpace;
            equiTex.needsUpdate = true;
            // Try PMREM-prefiltering the equirect so transmissive
            // BSDFs / NodeMaterial env-IBL can sample it as a proper
            // cubemap. Raw equirect DataTextures sampled as scene.environment
            // produce visible env contribution on opaque PBR but DON'T
            // satisfy the transmission BSDF which expects a prefiltered
            // env (transmission samples the ENV at the refracted
            // direction). Without PMREM, transmissive materials render
            // as black voids.
            //
            // NOTE: do not dispose() the PMREMGenerator after — the render
            // target's GPU texture is what scene.environment binds, and
            // disposing the generator can race with the renderer setting
            // it up for sampling on the first frame ("WebGPUTextureUtils:
            // Texture already initialized" — see reference_cloud_reflection_indoor_limitation.md).
            // Stash the generator on the texture so the GC can't collect.
            // Two PMREM input paths to try, in order:
            //   1) `fromScene(throwawayBackgroundScene)` — builds a tiny scene
            //      with the equiTex as background and lets PMREM render+
            //      prefilter that. Avoids re-binding the equiTex GPU
            //      resource directly into the prefilter pipeline (which
            //      throws "Texture already initialized" on three's WebGPU
            //      PMREM when the same equirect is later sampled by the
            //      transmission BSDF).
            //   2) `fromEquirectangular(equiTex)` — direct path. May throw
            //      the texture-conflict error.
            // Falls back to the raw equirect if both PMREM paths fail.
            // Install a one-shot textureUtils.createTexture monkey-patch
            // BEFORE running PMREM. Three's WebGPU renderer will later call
            // backend.createTexture on every texture used during the first
            // frame — including the PMREM-output cube texture that PMREM
            // already initialized. The internal check
            // `if (textureData.initialized) throw new Error('… already
            // initialized.')` doesn't account for PMREM-pre-initialized
            // textures, so the first frame throws and the entire render
            // path dies. Make createTexture idempotent: if the texture is
            // tagged with `_pmremPreInit` and already has a backend
            // texture, treat the call as a no-op instead of throwing.
            try {
                const tu = renderer.backend?.textureUtils;
                if (tu && !tu._patchedForPMREM) {
                    const origCreateTexture = tu.createTexture.bind(tu);
                    tu.createTexture = function(texture, options) {
                        try {
                            const td = this.backend.get(texture);
                            // Make createTexture IDEMPOTENT for already-
                            // initialized textures. Three's WebGPU renderer
                            // calls backend.createTexture from within
                            // updateTexture even when the texture is already
                            // initialized (versioning is incomplete — see
                            // updateTexture line 33755 where the early-return
                            // requires textureData.version === texture.version
                            // but textureData.version is never set, only
                            // textureData.generation is). This is mostly
                            // harmless: hitting the throw kills our render.
                            // Skipping the redundant create call is safe —
                            // the GPU resource is already valid.
                            if (td?.initialized) {
                                return;
                            }
                        } catch {}
                        return origCreateTexture(texture, options);
                    };
                    tu._patchedForPMREM = true;
                }
            } catch (e) {
                console.warn(`[render_scene] env-fallback: textureUtils patch failed (${e.message})`);
            }

            let envForScene = equiTex;
            try {
                if (THREE_NS.PMREMGenerator) {
                    const pmrem = new THREE_NS.PMREMGenerator(renderer);
                    let target = null;
                    try {
                        const bgScene = new THREE_NS.Scene();
                        bgScene.background = equiTex;
                        target = pmrem.fromScene(bgScene, 0);
                        console.log('[render_scene] env-fallback: PMREM fromScene OK');
                    } catch (e1) {
                        console.warn(`[render_scene] env-fallback: PMREM fromScene failed (${e1.message}); trying fromEquirectangular`);
                        try {
                            pmrem.compileEquirectangularShader?.();
                            target = pmrem.fromEquirectangular(equiTex);
                            console.log('[render_scene] env-fallback: PMREM fromEquirectangular OK');
                        } catch (e2) {
                            console.warn(`[render_scene] env-fallback: PMREM fromEquirectangular also failed (${e2.message})`);
                        }
                    }
                    if (target) {
                        envForScene = target.texture;
                        envForScene.userData = envForScene.userData || {};
                        envForScene.userData._pmremKeepalive = pmrem;
                        envForScene.userData._pmremTarget = target;
                        envForScene.userData._pmremPreInit = true;  // tells the patched createTexture to skip
                    }
                } else {
                    console.log('[render_scene] env-fallback: PMREMGenerator unavailable, using raw equirect');
                }
            } catch (e) {
                console.warn(`[render_scene] env-fallback: PMREM setup failed (${e.message}); using raw equirect`);
            }
            scene.environment = envForScene;
            if (scene.environmentIntensity === undefined ||
                scene.environmentIntensity === 1.0) {
                scene.environmentIntensity = 0.3;
            }
            console.log('[render_scene] No scene.environment set — installed sky-gradient equirect fallback @ intensity 0.3 (use fetch_hdri for production quality)');
        } catch (e) {
            console.warn('[render_scene] default env fallback failed:', e.message);
        }
    }

    // When volumetric_clouds is active, cloud-reflect handles SPECULAR
    // env-IBL on opaque metals — letting scene.environment also contribute
    // double-counts those reflections (the env-fallback equirect IS the same
    // sky the cloud-reflect raymarches). But transmissive surfaces
    // (transmission > 0): glass / refractive plastic still need env for the
    // refracted-through colour, which cloud-reflect doesn't cover. Without
    // this, glass balls render as black voids.
    //
    // Strategy (TSL-native): keep scene.environmentIntensity at its full
    // value so transmissive materials get the env via the normal NodeMaterial
    // path, and override `material.envNode = vec3(0)` on every NON-
    // transmissive material to suppress env contribution there. This works
    // because MeshPhysicalNodeMaterial (WebGPU) reads `envNode` (a TSL node)
    // for env-IBL — setting it to a constant zero overrides the global env
    // for that material only. The legacy `material.envMap` / `envMapIntensity`
    // fields don't work for NodeMaterial (verified empirically).
    // When volumetric_clouds is active, replace the basic gradient env-
    // fallback with a baked cloud-sky equirect — same skyRay raymarch the
    // cloud-reflect hook uses, but rendered to a texture once at setup.
    // This makes scene.environment the actual cloud sky, so transmissive
    // materials (glass) refract/reflect cloud sky consistent with the
    // cloud-reflect that opaque metals get. Without this, transmissive
    // materials see only the basic gradient (or whatever fallback) which
    // visually conflicts with the cloud-reflect cloud detail on metals.
    if (cloudReflectActive && globalThis._fx?.bakeEnvEquirect) {
        try {
            const renderer2 = globalThis._renderer || globalThis._r;
            if (renderer2) {
                const baked = await globalThis._fx.bakeEnvEquirect(renderer2, { width: 512, height: 256 });
                // Mark the baked texture as "GPU-pre-init by render-target"
                // so the patched textureUtils.createTexture skips re-init.
                baked.userData = baked.userData || {};
                baked.userData._pmremPreInit = true;
                if (scene) {
                    scene.environment = baked;
                    console.log('[render_scene] volumetric_clouds active — scene.environment = baked cloud-sky equirect (transmissive refraction will sample real cloud sky)');
                }
            }
        } catch (e) {
            console.warn(`[render_scene] cloud-sky env bake failed (${e.message}); leaving scene.environment as previous`);
            if (e.stack) console.warn(e.stack.split('\n').slice(0, 6).join('\n'));
        }
    }

    if (scene && scene.environment && cloudReflectActive && globalThis.THREE?.vec3) {
        const zeroEnv = globalThis.THREE.vec3(0, 0, 0);
        // Boost env to default so the transmissive path actually sees it.
        if (scene.environmentIntensity !== undefined && scene.environmentIntensity < 1.0) {
            scene.environmentIntensity = 1.0;
        }
        let opaqueSuppressed = 0, transmissiveKept = 0;
        scene.traverse((obj) => {
            if (!obj.isMesh) return;
            const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
            for (const mat of mats) {
                if (!mat) continue;
                const transmission = mat.transmission ?? 0;
                if (transmission > 0) {
                    transmissiveKept++;  // leave env default → samples scene.environment
                } else {
                    // Suppress env on opaque via BOTH knobs:
                    //   - `envNode = vec3(0)`: TSL-native NodeMaterial path
                    //     (MeshStandardNodeMaterial / MeshPhysicalNodeMaterial)
                    //   - `envMapIntensity = 0`: legacy path used by
                    //     MeshStandardMaterial that GLTFLoader produces by
                    //     default. Three's WebGPU bundle auto-converts these
                    //     to NodeMaterial at render time, but the conversion
                    //     reads `envMapIntensity` to populate the env scaling
                    //     uniform. Setting both covers every conversion path.
                    if ('envNode' in mat) mat.envNode = zeroEnv;
                    if (mat.envMapIntensity !== undefined) mat.envMapIntensity = 0;
                    opaqueSuppressed++;
                }
            }
        });
        console.log(`[render_scene] cloud-reflect active → opaque env suppressed on ${opaqueSuppressed} material(s); ${transmissiveKept} transmissive material(s) keep scene.environment (note: transmission backbuffer wiring is task #30)`);
    }
}

// If the scene auto-upgraded a WebGLRenderer (and didn't await init itself),
// finish init now before autoenhance/render-loop. WebGPURenderer in 0.184
// throws if .render() is called before init completes.
{
    const r = globalThis._renderer || globalThis._r;
    if (r && r._initPromise) {
        try { await r._initPromise; r._initPromise = null; } catch (e) {
            console.error('[render_scene] auto-upgrade renderer init failed:', e.message);
            Deno.exit(1);
        }
    }
}

// Pre-render once to force shadow-map creation. Three.js creates each
// directional light's shadow.map (the depth render-target the lit shader
// samples for shadow visibility) lazily on the first scene render that
// has shadowMap.enabled and a light with castShadow=true. The auto-
// enhance graph below wants to sample that shadow map (for cloud-reflect
// specular occlusion etc.) at TSL-graph-build time — if .map is null
// at build time, the texture binding can't be wired and the shadow path
// silently no-ops. One throwaway frame populates the maps without any
// other side effects (autoenhance hasn't installed itself yet so the
// renderer.render here goes through the bare scenePass).
{
    const r = globalThis._renderer || globalThis._r;
    const s = globalThis._scene    || globalThis._s;
    const c = globalThis._camera   || globalThis._c;
    if (r && s && c && r.shadowMap && r.shadowMap.enabled) {
        try {
            await r.renderAsync(s, c);
        } catch (e) {
            console.warn('[render_scene] shadow-map pre-render failed:', e.message);
        }
    }
}

// Auto-enhance — production cinematic stack. ON by default (production parity).
// Disable per-scene with `globalThis._noAutoEnhance = true` in setup().
await applyAutoEnhance();

// --- TSL postprocessing nodes (lazy-load) ---
// These are the WebGPU-native equivalents of the EffectComposer Pass classes.
// Functions return TSL nodes that we compose into a single output graph.
var _tslPostNodes = null;  // var so loadTslPostprocessingNodes (called via the
                           // hoisted applyAutoEnhance above) doesn't hit TDZ.
async function loadTslPostprocessingNodes() {
    if (_tslPostNodes) return _tslPostNodes;
    const out = {};
    const tryFn = async (path, exportName) => {
        try {
            const m = await import(path);
            if (m[exportName]) out[exportName] = m[exportName];
        } catch (e) { console.log(`[tsl-post] ${path} skipped: ${e.message}`); }
    };
    const base = 'npm:three@0.184.0/addons/tsl/display/';
    await tryFn(base + 'GTAONode.js', 'ao');
    await tryFn(base + 'SSRNode.js', 'ssr');
    await tryFn(base + 'FXAANode.js', 'fxaa');
    await tryFn(base + 'BloomNode.js', 'bloom');
    await tryFn(base + 'SMAANode.js', 'smaa');
    await tryFn(base + 'AfterImageNode.js', 'afterImage');
    _tslPostNodes = out;
    return out;
}

// --- Auto-enhance: the production cinematic post-process stack ---
// REWRITTEN FOR WEBGPU using TSL postprocessing. The original render_scene
// uses EffectComposer + Pass classes (WebGL-era API); on Three's WebGPU
// renderer those passes use ShaderMaterial which the WebGPU backend can't
// compile (must be NodeMaterial). Three r170 ships TSL-native equivalents:
//   ao(depth, normal, camera)              — GTAO
//   ssr(color, depth, normal, metal, camera) — SSR (selects-style mesh
//                                              exclusion not directly
//                                              supported, applies globally)
//   fxaa(color)                            — FXAA
//   bloom(color, strength, radius, threshold) — UnrealBloom
// They're composed into a TSL node graph and set as PostProcessing.outputNode.
// PostProcessing handles canvas writes itself, so we don't need RT readback.
//
// Set globalThis._noAutoEnhance = true in setup() to bypass.
//   - Defensive material setup (alpha-to-coverage on alpha-tested materials,
//     disable depthWrite on transparent/sprite/points so they don't pollute
//     the depth buffer that GTAO/SSR sample)
//   - VRM mesh detection (used to exclude VRMs from SSR — MToon doesn't expose
//     metalness/roughness in a way SSR understands)
//   - GTAO ambient occlusion with sprite/UI hide patch
//   - SSR screen-space reflections, VRMs excluded
//   - FXAA final post-process AA
//   - MSAA-4x HalfFloat composer if scene didn't build one
//   - renderer.render() patched to route through the composer
//
// Set globalThis._noAutoEnhance = true in scene script to bypass entirely.
async function applyAutoEnhance() {
    if (globalThis._noAutoEnhance || Deno.env.get('NO_AUTOENHANCE') === '1') {
        console.log('[auto-enhance] skipped: NO_AUTOENHANCE / _noAutoEnhance flag set');
        return;
    }
    const renderer = globalThis._r || globalThis._renderer;
    const scene = globalThis._s || globalThis._scene;
    const camera = globalThis._c || globalThis._camera;
    if (!renderer || !scene || !camera) {
        console.log('[auto-enhance] skipped: no renderer/scene/camera globals');
        return;
    }

    // Shadows
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // TSL postprocessing — only path. The WebGL EffectComposer/GTAOPass/
    // SSRPass/FXAAShader fallback was deleted; we're WebGPU-only here.
    if (!THREE.PostProcessing || !THREE.pass) {
        console.error('[auto-enhance] FATAL: three.js bundle missing PostProcessing/pass — required for WebGPU TSL postprocessing');
        Deno.exit(1);
    }
    return await applyAutoEnhanceTSL(renderer, scene, camera);
}

async function applyAutoEnhanceTSL(renderer, scene, camera) {
    // TSL primitives. Names match three.js's webgpu_postprocessing_ao /
    // _ssr canonical examples. directionToColor packs view-space normals
    // into a colour channel; vec2 packs metalness+roughness for SSR.
    const {
        pass, output: outputNode_, mrt, normalView, directionToColor,
        colorToDirection, colorSpaceToWorking, SRGBColorSpace,
        metalness, roughness, vec2, screenUV, sample,
        builtinAOContext, renderOutput, UnsignedByteType, mix,
    } = THREE;
    const tsl = await loadTslPostprocessingNodes();

    // Defensive material setup — same as production
    let a2cCount = 0, depthFixCount = 0;
    scene.traverse(child => {
        if (child.isSprite && child.material) { child.material.depthWrite = false; depthFixCount++; }
        if (child.isPoints && child.material) { child.material.depthWrite = false; depthFixCount++; }
        if (child.isMesh && child.material) {
            const mats = Array.isArray(child.material) ? child.material : [child.material];
            mats.forEach(mat => {
                if (mat.alphaTest > 0.0001) { mat.alphaToCoverage = true; mat.needsUpdate = true; a2cCount++; }
                if (mat.transparent && mat.alphaTest < 0.0001) { mat.depthWrite = false; depthFixCount++; }
            });
        }
    });
    if (a2cCount) console.log(`[auto-enhance] alphaToCoverage on ${a2cCount} materials`);
    if (depthFixCount) console.log(`[auto-enhance] depthWrite=false on ${depthFixCount} transparent/sprite/points`);

    try {
        const scenePass = pass(scene, camera);
        const added = [];

        // MRT setup: pack normals (encoded via directionToColor) and
        // metalness+roughness (vec2 packed) into separate channels.
        // Pattern matches webgpu_postprocessing_ssr.html.
        if (mrt && directionToColor && normalView && metalness && roughness && vec2 && scenePass.setMRT) {
            const sceneMRT = mrt({
                output: outputNode_,
                normal: directionToColor(normalView),
                metalrough: vec2(metalness, roughness),
            });
            // G-buffer attachments default to NoBlending: a transparent quad
            // REPLACES the normal/metalrough underneath over its full
            // footprint, alpha ignored — GTAO then reads billboard normals as
            // geometry and stamps hard dark rectangles behind smoke.
            // MaterialBlending makes these attachments follow each material's
            // own blend state: opaques still hard-write (no blend configured),
            // transparents blend by their attachment alpha — so materials that
            // override mrtNode with vec4(0) (particles) contribute nothing and
            // the opaque G-buffer under them stays intact.
            if (sceneMRT.setBlendMode && THREE.MaterialBlending !== undefined) {
                sceneMRT.setBlendMode('normal', { blending: THREE.MaterialBlending });
                sceneMRT.setBlendMode('metalrough', { blending: THREE.MaterialBlending });
            }
            scenePass.setMRT(sceneMRT);
        }
        const sceneColor = scenePass.getTextureNode('output');
        const sceneDepth = scenePass.getTextureNode('depth');
        const scenePassNormal = scenePass.getTextureNode('normal');
        const sceneMetalRough = scenePass.getTextureNode('metalrough');

        // Optional bandwidth-saving precision reduction on aux channels.
        if (UnsignedByteType && scenePass.getTexture) {
            try {
                for (const ch of ['normal', 'metalrough']) {
                    try {
                        const t = scenePass.getTexture(ch);
                        if (t) t.type = UnsignedByteType;
                    } catch {}
                }
            } catch {}
        }

        // Sampleable normal node — the canonical SSR pattern wraps the
        // colorToDirection decode inside a sample(uv => ...) factory so SSR
        // can call .sample(uv) on it just like a regular texture node.
        // Direct colorToDirection(textureNode) returns a non-sampleable math
        // node and SSR fails with "this.normalNode.sample is not a function".
        const sceneNormal = (sample && colorToDirection)
            ? sample((uv) => colorToDirection(scenePassNormal.sample(uv)))
            : scenePassNormal;

        let colorOut = sceneColor;

        // GTAO via builtinAOContext — production AO example pattern.
        // The AO node feeds back into the scene's lighting context rather
        // than multiplying after the fact.
        // GTAO — kept in the pipeline; user verifies it visually (they can
        // see it on a bright scene; I as an AI struggle with that subtle
        // shading even with before/after). SSR is my primary self-verify
        // target because reflections create an obvious "duplicated geometry"
        // pattern I can pattern-match in a single frame.
        // GTAO. We capture the AO texture node out of this scope so the
        // cloud-reflect compose step below can also modulate by it — env-
        // IBL contributions (cloud reflections on metallic surfaces) need
        // to be attenuated by ambient occlusion the same way the diffuse
        // lighting context is, otherwise rough metal in a concavity
        // appears unnaturally bright (the AO darkens the base scene
        // shading but a raw `colorOut + cloudReflTex` add would put full-
        // brightness sky reflection on top, blowing past the tonemap).
        let aoTexNode = null;
        // Scene-tunable: globalThis._aoParams = { enabled, resolutionScale }.
        const _aop = globalThis._aoParams || {};
        if (tsl.ao && builtinAOContext && _aop.enabled !== false) {
            try {
                const aoPass = tsl.ao(sceneDepth, sceneNormal, camera);
                aoPass.resolutionScale = _aop.resolutionScale ?? 0.5;
                if ('useTemporalFiltering' in aoPass) aoPass.useTemporalFiltering = true;
                aoTexNode = aoPass.getTextureNode();
                scenePass.contextNode = builtinAOContext(aoTexNode.sample(screenUV).r);
                added.push('GTAO');
            } catch (e) { console.warn('[auto-enhance] GTAO failed:', e.message); }
        }

        // Pre-SSR hook: lets effects that should be REFLECTED (volumetric
        // clouds, atmospheric haze) modify colorOut and optionally depthOut
        // before SSR samples them. Hook can return either:
        //   - a vec4 node (color only), or
        //   - { color, depth } (both nodes)
        // SSR needs TextureNodes for both, so we RTT-wrap each.
        let depthForSSR = sceneDepth;
        if (typeof globalThis._autoEnhancePreSSRHook === 'function') {
            try {
                const hooked = globalThis._autoEnhancePreSSRHook(
                    colorOut, sceneDepth, sceneNormal, sceneMetalRough,
                );
                if (hooked) {
                    if (hooked.color !== undefined) {
                        colorOut = THREE.convertToTexture
                            ? THREE.convertToTexture(hooked.color)
                            : hooked.color;
                        if (hooked.depth !== undefined) {
                            depthForSSR = THREE.convertToTexture
                                ? THREE.convertToTexture(hooked.depth)
                                : hooked.depth;
                        }
                    } else {
                        colorOut = THREE.convertToTexture
                            ? THREE.convertToTexture(hooked)
                            : hooked;
                    }
                    added.push('preSSR-hook');
                }
            } catch (e) {
                console.warn('[auto-enhance] pre-SSR-hook failed:', e.message);
                if (e.stack) console.warn(e.stack.split('\n').slice(0, 5).join('\n'));
            }
        }

        // Cloud-reflect hook: runs BEFORE SSR. This is the critical
        // ordering — SSR samples colorOut for its reflection-ray hit
        // colours, so any post-process effect that adds reflection
        // colour to metallic surfaces MUST run before SSR for SSR's
        // reflections-of-those-surfaces to be consistent. Otherwise the
        // floor reflection of a chrome rock would look duller than the
        // rock itself.
        // Hook returns JUST the cloud reflection contribution as vec4;
        // we RTT, optionally blur, and ADD into colorOut so SSR sees
        // cloud-tinted metallic surfaces.
        // cloudReflTex is hoisted so the SSR-gated compose below can see it.
        // The reflectHook builds the per-pixel HDR cloud contribution; we hold
        // it out of colorOut so SSR runs on a cloud-free colorOut and its hit
        // alpha can gate cloud as a fallback (see deferred compose below SSR).
        let cloudReflTex = null;
        if (typeof globalThis._autoEnhanceCloudReflectHook === 'function') {
            try {
                const contrib = globalThis._autoEnhanceCloudReflectHook(
                    colorOut, sceneDepth, sceneNormal, sceneMetalRough,
                );
                if (contrib) {
                    cloudReflTex = THREE.convertToTexture
                        ? THREE.convertToTexture(contrib)
                        : contrib;
                    if (typeof globalThis._autoEnhanceCloudReflectBlurHook === 'function') {
                        try {
                            const blurred = globalThis._autoEnhanceCloudReflectBlurHook(
                                cloudReflTex, sceneDepth, sceneNormal, sceneMetalRough,
                            );
                            if (blurred) {
                                cloudReflTex = THREE.convertToTexture
                                    ? THREE.convertToTexture(blurred)
                                    : blurred;
                                added.push('cloudReflectBlur');
                            }
                        } catch (e) {
                            console.warn('[auto-enhance] cloudReflectBlur-hook failed:', e.message);
                        }
                    }
                    // Modulate by AO so concavities don't get full-brightness
                    // sky reflection on top of their AO-darkened base shading.
                    // This matches how Three's MeshPhysicalMaterial multiplies
                    // env-IBL contributions by ambient occlusion.
                    if (aoTexNode) {
                        const aoSample = aoTexNode.sample(screenUV).r;
                        cloudReflTex = THREE.convertToTexture
                            ? THREE.convertToTexture(cloudReflTex.mul(aoSample))
                            : cloudReflTex.mul(aoSample);
                    }
                    // Specular shadow occlusion — multiply cloud-reflect by
                    // directional-light shadow visibility at each pixel's
                    // world position. Strict PBR env-IBL doesn't do this
                    // (env reflection is supposed to be independent of
                    // direct light shadow), but visually it produces the
                    // "metal in shade glows from sky reflection" artifact:
                    // a metallic brainstem inside a deep shadow still
                    // reflects bright HDR cloud values because nothing
                    // attenuates the env contribution. The same physical
                    // occluder that creates the shadow ALSO blocks parts
                    // of the sky from reaching the surface, so multiplying
                    // by shadow visibility approximates the missing
                    // specular occlusion. Read directly from the scene's
                    // primary shadow light if exposed.
                    // NORMAL-UP gate: cheap, principled approximation
                    // of "this surface faces the sky." Brainstem normals
                    // point sideways/down → 0 cloud contribution. Floor
                    // normals point up → full. Brain top → partial. This
                    // is exactly the artist-intuition "metal in shade
                    // shouldn't glow" shape: surfaces oriented away from
                    // the sky shouldn't reflect the sky regardless of
                    // whether the reflection ray exits to sky in screen
                    // space. Doesn't require shadow-map sampling at all.
                    try {
                        const sceneNormalTex = (typeof sample === 'function' && colorToDirection)
                            ? null  // sceneNormal already a direction node
                            : null;
                        // sceneNormal is already a per-pixel decoded direction
                        // (view-space). Don't re-sample — that'd return garbage
                        // since it's not a raw texture node. Use directly.
                        const upGate = THREE.Fn(() => {
                            const worldN = THREE.normalize(
                                THREE.cameraWorldMatrix.mul(THREE.vec4(sceneNormal, 0)).xyz,
                            );
                            return THREE.clamp(worldN.y, 0, 1);
                        })();
                        cloudReflTex = THREE.convertToTexture
                            ? THREE.convertToTexture(cloudReflTex.mul(upGate))
                            : cloudReflTex.mul(upGate);
                        added.push('cloudReflect-upGate');
                    } catch (e) {
                        console.warn('[auto-enhance] up-gate failed:', e.message);
                    }
                    // Hold cloudReflTex OUT of colorOut for now. The SSR pass below
                    // runs on the bare (cloud-free) colorOut, so its hit-mask alpha
                    // can be used to gate cloud-reflect as a FALLBACK for SSR
                    // misses rather than a layer added on top. This is the
                    // physically-correct compose: a single reflection direction
                    // hits EITHER geometry (SSR) OR sky (cloud-reflect), never
                    // both. The previous additive compose double-counted, making
                    // SSR-reflected objects look washed out by cloud overlay (e.g.
                    // mirror floor reflecting a chrome car shows car + cloud
                    // instead of just car).
                    //
                    // Trade-off: SSR no longer sees cloud contribution baked into
                    // metallic surfaces, so 2nd-bounce cloud (e.g. mirror floor
                    // reflecting a chrome ball that itself reflects clouds) is
                    // lost. First-order reflections take priority — most scenes
                    // care about the main reflection, and a chrome-of-chrome
                    // edge case can be added back later if needed (sample the
                    // pre-cloud-reflect colorOut + cloud contribution in SSR's
                    // hit-color readback).
                    added.push('cloudReflect-hook(deferred)');
                }
            } catch (e) {
                console.warn('[auto-enhance] cloudReflect-hook failed:', e.message);
                if (e.stack) console.warn(e.stack.split('\n').slice(0, 5).join('\n'));
            }
        }

        // SSR — runs on bare colorOut (without cloud-reflect baked in). Returns
        // vec4 where alpha=1 on hit, alpha=0 on miss. The hit alpha gates the
        // deferred cloud-reflect compose immediately below.
        //
        // Screen-edge fade: three.js SSR has internal distance + fresnel
        // attenuation but no screen-edge fade — when the reflection ray exits
        // the visible screen, SSR `Break()`s with alpha=1 instead of fading to
        // 0. We multiply SSR's output by a smoothstep on min(uv,1-uv) to fade
        // contributions within 5–15% of any screen edge (the same approach
        // UE/Unity SSR use). Compose the fade inline (no extra convertToTexture
        // wrap — wrapping the multiplied node trips a TSL recursion in the
        // VarNode/StackNode graph).
        let ssrHitAlpha = null;
        if (tsl.ssr && sceneMetalRough) {
            try {
                const ssrNode = tsl.ssr(
                    colorOut, depthForSSR, sceneNormal,
                    sceneMetalRough.r, sceneMetalRough.g, camera
                );
                const ssrTex = THREE.convertToTexture
                    ? THREE.convertToTexture(ssrNode)
                    : ssrNode;
                let ssrRGB = ssrTex.rgb;
                let ssrA = ssrTex.a;
                if (THREE.uv && THREE.smoothstep && THREE.min && THREE.float) {
                    try {
                        const u = THREE.uv();
                        const edgeDist = THREE.min(
                            THREE.min(u.x, THREE.float(1).sub(u.x)),
                            THREE.min(u.y, THREE.float(1).sub(u.y)),
                        );
                        const fade = THREE.smoothstep(0.05, 0.15, edgeDist);
                        ssrRGB = ssrRGB.mul(fade);
                        ssrA = ssrA.mul(fade);
                        added.push('SSR-edgefade');
                    } catch (e) { console.warn('[auto-enhance] SSR edge-fade failed:', e.message); }
                }
                colorOut = colorOut.add(ssrRGB);
                ssrHitAlpha = ssrA;
                added.push('SSR');
            } catch (e) { console.warn('[auto-enhance] SSR failed:', e.message); }
        }

        // Pre-bloom hook slot (anamorphic_flare and similar highlight-
        // extraction effects). Runs on the post-SSR colorOut BEFORE bloom
        // so:
        //   - the hook sees clean raw HDR (no double-extraction-from-
        //     already-bloomed bright pixels)
        //   - bloom then sees the (scene + flare-streak) result and
        //     softens edges of both, which matches real lens behaviour
        //     (anamorphic streaks aren't pin-sharp on real glass)
        // Hook contract: takes colorNode, returns modified colorNode.
        if (typeof globalThis._autoEnhancePreBloomHook === 'function') {
            try {
                const flared = globalThis._autoEnhancePreBloomHook(
                    colorOut, sceneDepth, sceneNormal, sceneMetalRough,
                );
                if (flared) {
                    colorOut = THREE.convertToTexture
                        ? THREE.convertToTexture(flared)
                        : flared;
                    added.push('preBloom-hook');
                }
            } catch (e) {
                console.warn('[auto-enhance] preBloom-hook failed:', e.message);
            }
        }

        // UnrealBloom — runs on the post-SSR colorOut but BEFORE the cloud-
        // reflect-fallback compose. This is deliberate: the cloud-reflect
        // contribution is HDR cloud sky added to metallic surfaces; if bloom
        // saw it, the HDR cloud values would bloom outward and create halos
        // around dark shaded objects sitting next to cloud-reflected metals
        // ("the unreal bloom is creating a halo around even the shaded parts
        // as if they are still reflecting sky when they arent" — earlier
        // user feedback). By running bloom on (scene + sky-replace + SSR)
        // and adding cloud-reflect AFTER bloom, bloom blooms emissives,
        // sun-lit surfaces, and SSR reflections of bright objects but NOT
        // the unoccluded cloud sky reflection on metals.
        //
        // Three's tsl.bloom returns the bloom CONTRIBUTION (to be added to
        // the source). Tuning: strength=0.25 lets emissives glow without
        // halo-washing the surrounding scene; radius=0.4 spreads softly;
        // threshold=0.85 catches perceptually-near-white pixels (low enough
        // to catch HDR post-tonemap, high enough to spare mid-bright surfaces).
        let bloomContribNode = null;
        // Scene-tunable: globalThis._bloomParams = { strength, radius,
        // threshold } (strength 0 disables). Defaults preserved.
        const _bp = globalThis._bloomParams || {};
        const _bStrength = _bp.strength ?? 0.25;
        if (tsl.bloom && _bStrength > 0) {
            try {
                const bloomNode = tsl.bloom(colorOut, _bStrength, _bp.radius ?? 0.4, _bp.threshold ?? 0.85);
                bloomContribNode = bloomNode;
                added.push('UnrealBloom');
            } catch (e) { console.warn('[auto-enhance] bloom failed:', e.message); }
        }

        // Deferred cloud-reflect compose: add cloudReflTex.rgb gated by
        // (1 - ssrHitAlpha). Where SSR found geometry, cloud contribution is
        // killed (no double-counting). Where SSR missed (open sky direction),
        // cloud-reflect supplies the env color.
        if (cloudReflTex) {
            try {
                const gatedCloud = ssrHitAlpha
                    ? cloudReflTex.rgb.mul(ssrHitAlpha.oneMinus())
                    : cloudReflTex.rgb;
                colorOut = colorOut.add(gatedCloud);
                colorOut = THREE.convertToTexture
                    ? THREE.convertToTexture(colorOut)
                    : colorOut;
                added.push(ssrHitAlpha ? 'cloudReflect-fallback' : 'cloudReflect-add');
            } catch (e) {
                console.warn('[auto-enhance] cloudReflect compose failed:', e.message);
                if (e.stack) console.warn(e.stack.split('\n').slice(0, 5).join('\n'));
            }
        }

        // Add bloom contribution AFTER cloud-reflect so bloom glows on top of
        // the final lit scene without itself being smeared by the cloud-reflect
        // sample. Bloom is sampled from the pre-cloud colorOut snapshot
        // captured above; the values it produces are added unmodified here.
        if (bloomContribNode) {
            try {
                colorOut = colorOut.add(bloomContribNode);
                colorOut = THREE.convertToTexture
                    ? THREE.convertToTexture(colorOut)
                    : colorOut;
            } catch (e) {
                console.warn('[auto-enhance] bloom compose failed:', e.message);
            }
        }

        // Scene-script hook: lets a setup() inject extra TSL nodes between
        // SSR and renderOutput/FXAA. The hook receives the current colour
        // node + scene depth + scene normal nodes and returns a new colour
        // node. Used by underwater + similar effects that need to operate on
        // the lit scene before tone-mapping.
        if (typeof globalThis._autoEnhanceColorHook === 'function') {
            try {
                const hooked = globalThis._autoEnhanceColorHook(colorOut, sceneDepth, sceneNormal, sceneMetalRough);
                if (hooked) { colorOut = hooked; added.push('hook'); }
            } catch (e) {
                console.warn('[auto-enhance] color-hook failed:', e.message);
                if (e.stack) console.warn(e.stack.split('\n').slice(0, 5).join('\n'));
            }
        }

        // Screen-space overlay pass — HUD / lower-thirds / motion-graphics.
        // Composited as a SECOND pass() node in THIS PostProcessing graph (the
        // canonical WebGPU way; a second renderer.render() to the canvas ghosts
        // — see three.js #32535). Placed AFTER the effect hook so depth-keyed
        // screenspace effects (volumetric_clouds etc.) can't paint over it, and
        // BEFORE renderOutput so it shares the scene's tone-map. Source-over
        // alpha via mix(base, overlay, overlay.a) keeps smooth transparency.
        // Opt-in: scene sets globalThis._overlayScene (+ optional _overlayCamera).
        if (globalThis._overlayScene && typeof pass === 'function' && mix) {
            try {
                const ovCam = globalThis._overlayCamera || camera;
                const ovColor = pass(globalThis._overlayScene, ovCam).getTextureNode('output');
                colorOut = mix(colorOut, ovColor, ovColor.a);
                added.push('overlay');
            } catch (e) { console.warn('[auto-enhance] overlay pass failed:', e.message); }
        }

        // Screen-space effect hook — vhs / glitch / grain / rgb-shift etc.
        // Applied AFTER the overlay composite so these non-depth effects process
        // the finished frame INCLUDING the HUD (the overlay should look like
        // part of the broadcast signal, not float above it). With no overlay
        // this runs right after the depth-keyed colorHook → same as before.
        if (typeof globalThis._autoEnhanceScreenHook === 'function') {
            try {
                const hooked = globalThis._autoEnhanceScreenHook(colorOut, sceneDepth, sceneNormal, sceneMetalRough);
                if (hooked) { colorOut = hooked; added.push('screenHook'); }
            } catch (e) {
                console.warn('[auto-enhance] screen-hook failed:', e.message);
                if (e.stack) console.warn(e.stack.split('\n').slice(0, 5).join('\n'));
            }
        }

        // Tone mapping + output color space. renderOutput is the TSL function
        // that applies these correctly for the output node graph.
        let finalNode = renderOutput ? renderOutput(colorOut) : colorOut;

        if (tsl.fxaa) {
            try {
                finalNode = tsl.fxaa(finalNode);
                added.push('FXAA');
            } catch (e) { console.warn('[auto-enhance] FXAA failed:', e.message); }
        }

        // RenderPipeline is the r183+ name for PostProcessing — alias-fallback
        // keeps backwards compat if we ever roll Three back.
        const PipelineCls = THREE.RenderPipeline || THREE.PostProcessing;
        const postProcessing = new PipelineCls(renderer);
        postProcessing.outputNode = finalNode;
        // renderOutput already applied color-space conversion
        postProcessing.outputColorTransform = false;

        // Patch renderer.renderAsync (and .render) to route through PostProcessing.
        const origRenderAsync = renderer.renderAsync.bind(renderer);
        const origRender = renderer.render.bind(renderer);
        let _insidePost = false;
        let _ppCallCount = 0;
        renderer.renderAsync = async function(s, c) {
            if (_insidePost) return origRenderAsync(s, c);
            _insidePost = true;
            try {
                await postProcessing.renderAsync();
                _ppCallCount++;
                if (_ppCallCount === 1 || _ppCallCount === 30) {
                    console.log(`[auto-enhance] postProcessing.renderAsync fired #${_ppCallCount}`);
                }
            } finally { _insidePost = false; }
        };
        renderer.render = function(s, c) {
            if (_insidePost) return origRender(s, c);
            _insidePost = true;
            try {
                postProcessing.render();
            } finally { _insidePost = false; }
        };

        globalThis._postProcessing = postProcessing;
        globalThis.__autoEnhanceActive = true;
        console.log(`[auto-enhance] TSL pipeline: scenePass${added.length ? ' + ' + added.join(' + ') : ''} + renderOutput (renderer.renderAsync patched)`);
        return;
    } catch (e) {
        console.warn('[auto-enhance] TSL pipeline construction failed:', e.message);
        if (e.stack) console.warn(e.stack.split('\n').slice(0, 6).join('\n'));
    }
}

// REMOVED: WebGL-era legacy auto-enhance (lines 818-1024) — used EffectComposer/GTAOPass/SSRPass/FXAAShader. The TSL path always runs on three r170+, so this code was unreachable. Strip rather than carry as dead weight.


// Post-setup guard — confirm the renderer the scene built is actually WebGPU
// AND that its backend is the wgpu-rs WebGPUBackend (not some WebGL fallback).
// Logs the renderer class + backend class explicitly so each run prints the
// smoking-gun evidence into the log. Falls fatal if either looks wrong.
{
    const candidates = [
        globalThis._renderer, globalThis._r, globalThis._webgpu, globalThis._gpu,
    ].filter(Boolean);
    if (candidates.length === 0) {
        console.warn('[render_scene] WARNING: no _renderer / _r global found after setup() — skipping WebGPU-renderer assertion');
    } else {
        for (const r of candidates) {
            const rendererClass = r.constructor?.name || '?';
            const backendClass = r.backend?.constructor?.name || '?';
            console.log(`[render_scene] renderer=${rendererClass} backend=${backendClass}`);
            const isWebGPURenderer = !!r.isWebGPURenderer || /WebGPU/.test(rendererClass);
            const isWebGPUBackend = backendClass === '?' || /WebGPU/.test(backendClass);  // ? = backend not yet exposed in this Three.js version
            if (!isWebGPURenderer || !isWebGPUBackend) {
                console.error(`[render_scene] FATAL: NOT on WebGPU. renderer=${rendererClass} backend=${backendClass}`);
                Deno.exit(1);
            }
        }
        console.log(`[render_scene] WebGPU pipeline confirmed (${candidates.length} renderer global${candidates.length === 1 ? '' : 's'}).`);
    }
}

// (Removed the per-frame camera-clip DETECTOR: it raycast every visible mesh on
// every frame — a real, scaling cost on heavy/close subjects — yet only logged a
// post-hoc warning it never acted on, tripped on every legitimate close-up, and
// in practice never stopped agents parking the camera inside a VRM. Net cost,
// ~zero benefit. Camera-in-solid is better prevented proactively at shot-setup
// via CameraSafety, not by a per-frame detector.)

// --- Per-frame render guarantee (anti-frozen-frame) ------------------------
// A renderFrame() MUST land exactly one scene render on the swap-chain each
// frame, or the readback copies the previous (warm-up) texture every time →
// a static-frame-with-audio video. The classic miswire:
//
//     if (globalThis._fx?.update) await globalThis._fx.update(t);
//     else await globalThis._r.renderAsync(scene, camera);   // ← else!
//
// CustomEffectsDeno's _fx.update(t) ONLY updates effect uniforms (it splices a
// color hook into the auto-enhance pipeline); the render still has to go
// through renderer.renderAsync/render. Behind that `else`, no render ever
// fires and the whole video freezes. Rather than rely on every agent writing
// renderFrame perfectly, the harness GUARANTEES a render per frame: we count
// scene render calls during renderFrame and, if zero, render the scene
// ourselves before the readback. (Whether a frame rendered is decidable and
// exception-free — no legit scene wants a frozen swap-chain — so this is a
// prevent, not a detect.)
const _guardRenderer = globalThis._r || globalThis._renderer;
let _frameRenderCount = 0;
let _warnedNoRender = false;
if (_guardRenderer && typeof _guardRenderer.renderAsync === 'function') {
    const _origGuardRA = _guardRenderer.renderAsync.bind(_guardRenderer);
    _guardRenderer.renderAsync = async function (s, c) { _frameRenderCount++; return await _origGuardRA(s, c); };
}
if (_guardRenderer && typeof _guardRenderer.render === 'function') {
    const _origGuardR = _guardRenderer.render.bind(_guardRenderer);
    _guardRenderer.render = function (s, c) { _frameRenderCount++; return _origGuardR(s, c); };
}

// --- Render loop ---
console.log(`[render_scene] Rendering ${totalFrames} frames at ${width}x${height} @ ${fps}fps → ${outputVideo}`);
const ffmpeg = startFfmpegPipe(width, height, fps, outputVideo);
const tStart = performance.now();

for (let i = 0; i < totalFrames; i++) {
    const t = i * dt;
    globalThis._sceneTime = t;
    _frameRenderCount = 0;

    // Auto-advance any GLB/model animation mixers registered via
    // playModelAnimations() — so a fetched model's OWN embedded animation
    // plays every frame without the scene remembering mixer.update().
    if (globalThis._autoMixers) {
        for (const mx of globalThis._autoMixers) { try { mx.update(dt); } catch (e) {} }
    }

    // Keep makeParticles() systems billboarded to the camera (motion itself is
    // GPU; this just refreshes the camera-right/up uniforms — O(1) per system).
    if (globalThis._autoParticleSystems) {
        for (const up of globalThis._autoParticleSystems) { try { up(t); } catch (e) {} }
    }
    // Self-updating makeScreen panels (see eidoverse/screen.js) — same
    // contract as the particle drain: each entry is an update(t) callback.
    if (globalThis._autoScreens) {
        for (const up of globalThis._autoScreens) { try { up(t); } catch (e) {} }
    }
    // Self-animating makeCreature rigs (see eidoverse/creature_builder.js).
    if (globalThis._autoCreatures) {
        for (const up of globalThis._autoCreatures) { try { up(t); } catch (e) {} }
    }
    // Self-animating makeRobot assemblies (see eidoverse/robotics_kit.js).
    if (globalThis._autoRobots) {
        // one broken bot must not kill the render — but a SILENT swallow
        // makes its sim invisibly half-dead, so log the first throw
        for (const up of globalThis._autoRobots) {
            try { up(t, dt); } catch (e) {
                if (!up._errLogged) { up._errLogged = true; console.warn('[robots] update threw (suppressed hereafter):', e.message); }
            }
        }
    }

    // Snapshot every registered VRM mixer's time before renderFrame, so we
    // don't double-advance one the scene drives itself.
    const _reg = globalThis._vrmMixers;
    if (_reg && _reg.size) for (const rec of _reg.values()) rec._tBefore = rec.mixer ? rec.mixer.time : 0;
    const mixerTimeBefore = globalThis._mixer ? globalThis._mixer.time : -1;
    if (typeof globalThis.renderFrame === 'function') {
        await globalThis.renderFrame(t, i);
    }
    if (_reg && _reg.size) {
        // Multi-VRM safe: drive EVERY registered character's mixer + VRM update,
        // not just the single globalThis._mixer/_vrm. This is what lets a 2nd (or
        // 3rd…) VRM actually animate — seated, walking, emoting — instead of
        // freezing/mis-posing.
        for (const [vrm, rec] of _reg) {
            try {
                if (rec.mixer && rec.mixer.time === rec._tBefore) rec.mixer.update(dt);
                if (typeof vrm.update === 'function') vrm.update(dt);
            } catch (e) { /* one bad VRM must not kill the frame */ }
        }
        // A captured _vrm with no VRMA mixer (loaded but never played a clip)
        // still needs its per-frame update.
        if (globalThis._vrm && !_reg.has(globalThis._vrm) && typeof globalThis._vrm.update === 'function') {
            try { globalThis._vrm.update(dt); } catch (e) {}
        }
    } else {
        // Legacy single-mixer path (no VRMA played yet).
        if (globalThis._mixer && globalThis._mixer.time === mixerTimeBefore) {
            globalThis._mixer.update(dt);
        }
        if (globalThis._vrm && typeof globalThis._vrm.update === 'function') {
            globalThis._vrm.update(dt);
        }
    }

    // ── Tie-blade swing limiter (installed as a wrapper on vrm.update) ──
    // VRM spring bones have NO angular limit, so a lively tie spring can fly or
    // swing past "down" into/through the body or forward at the camera. A clamp
    // placed HERE (after renderFrame) is too late — the scene already rendered
    // and will re-spring the tie before the next render, overwriting it. So
    // instead we WRAP each VRM's update() once: the limiter then runs at the end
    // of every spring update, i.e. right before whoever-it-is renders. It clamps
    // tie_2's deviation from its rest (draped-down) to a cone — gentle sway, but
    // it cannot fly, stick forward, or sink backward into the chest. Tune with
    // globalThis._tieSwingMaxDeg (default 9°); 0 pins it rigid.
    try {
        const seen = new Set(), list = [];
        const add = (v) => { if (v && v.scene && !seen.has(v)) { seen.add(v); list.push(v); } };
        add(globalThis._vrm); add(globalThis._v);
        if (_reg) for (const [v] of _reg) add(v);
        if (Array.isArray(globalThis._vrms)) for (const v of globalThis._vrms) add(v);
        for (const v of list) {
            if (v.__tieLimiterPatched || typeof v.update !== 'function') continue;
            const tie1 = v.scene.getObjectByName ? v.scene.getObjectByName('tie_1') : null;
            const tie2 = v.scene.getObjectByName ? v.scene.getObjectByName('tie_2') : null;
            v.__tieLimiterPatched = true;
            if (!tie1 || !tie2) continue;            // no tie → nothing to wrap
            // WORLD-SPACE clamp (a local clamp can't help — when the body yaws or
            // the chest leans, the tie rides it forward/sideways in WORLD even at
            // 0° local deviation). Take the actual blade direction = the world
            // vector tie_1→tie_2 (sidesteps the bone's arbitrary roll), and keep
            // it within a cone of straight-DOWN by rotating tie_1. So the tie
            // hangs down regardless of turn/lean/sit — it can't fly, stick
            // forward, or swing into the jacket. tie_2's tip bend gets a small
            // local cone on top. globalThis._tieSwingMaxDeg = cone° (default 10);
            // 0 pins it straight down.
            if (globalThis._tieDebug) console.log('[tie] world-down limiter on', (v.scene && v.scene.name) || 'vrm');
            const orig = v.update.bind(v);
            const TH = globalThis.THREE;
            const DOWN = new TH.Vector3(0, -1, 0);
            let rest2 = null, _dbgMax = 0, _dbgN = 0;
            v.update = function (dt2) {
                orig(dt2);
                try {
                    const maxRad = ((globalThis._tieSwingMaxDeg ?? 10)) * Math.PI / 180;
                    tie1.updateWorldMatrix(true, false); tie2.updateWorldMatrix(true, false);
                    const p1 = tie1.getWorldPosition(new TH.Vector3());
                    const p2 = tie2.getWorldPosition(new TH.Vector3());
                    const d = p2.sub(p1);
                    if (d.lengthSq() > 1e-9) {
                        d.normalize();
                        const ang = d.angleTo(DOWN);
                        if (globalThis._tieDebug) { if (ang > _dbgMax) _dbgMax = ang; if (++_dbgN % 30 === 0) { console.log('[tie] blade angle off-down, max last 30 =', (_dbgMax * 180 / Math.PI).toFixed(0) + '°'); _dbgMax = 0; } }
                        const lim = (globalThis._tieSwingMaxDeg === 0) ? 0 : maxRad;
                        if (ang > lim + 1e-4) {
                            // target = DOWN rotated toward d by `lim` (unit dir at lim° off-down, on d's side)
                            const full = new TH.Quaternion().setFromUnitVectors(DOWN, d);
                            const partial = new TH.Quaternion().slerp(full, lim / ang);   // identity→full by lim/ang
                            const target = DOWN.clone().applyQuaternion(partial);
                            const corr = new TH.Quaternion().setFromUnitVectors(d, target); // rotate blade d→target
                            const wq = tie1.getWorldQuaternion(new TH.Quaternion()).premultiply(corr);
                            const pInv = tie1.parent.getWorldQuaternion(new TH.Quaternion()).invert();
                            tie1.quaternion.copy(pInv.multiply(wq));
                            tie1.updateWorldMatrix(false, true);   // propagate to tie_2
                        }
                    }
                    // tip bend: keep tie_2 near its own local rest (small)
                    if (!rest2) { rest2 = tie2.quaternion.clone(); }
                    else {
                        const tipMax = Math.min(maxRad, 8 * Math.PI / 180);
                        const a2 = rest2.angleTo(tie2.quaternion);
                        if (a2 > tipMax) { tie2.quaternion.copy(rest2.clone().slerp(tie2.quaternion, tipMax / a2)); tie2.updateWorldMatrix(false, false); }
                    }
                } catch (e) { /* never break the render */ }
            };
        }
    } catch (e) { /* limiter install must never break the render */ }

    // ── Lipsync usage tracker ── per frame, note whether any VRM's mouth moved
    // (any viseme aa/ih/ou/ee/oh driven > ~0). At end-of-render we hard-flag any
    // VRM whose mouth NEVER moved — the #1 "character speaks with a frozen mouth"
    // miss. (Advisory: a deliberately-silent VRM also never moves its mouth, so
    // the warning says "if it speaks, you forgot lipsync; if silent, ignore".)
    try {
        const vs = [];
        if (globalThis._vrm) vs.push(globalThis._vrm); if (globalThis._v) vs.push(globalThis._v);
        if (_reg) for (const [vv] of _reg) vs.push(vv);
        if (Array.isArray(globalThis._vrms)) for (const vv of globalThis._vrms) vs.push(vv);
        const track = (globalThis.__lipsyncVrms ||= new Set());
        for (const vv of vs) {
            const em = vv && vv.expressionManager;
            if (!em || typeof em.getValue !== 'function') continue;
            track.add(vv);
            if (!vv.__mouthMoved) {
                for (const k of ['aa', 'ih', 'ou', 'ee', 'oh']) { const val = em.getValue(k); if (val && val > 0.06) { vv.__mouthMoved = true; break; } }
            }
        }
    } catch (e) { /* never break the render */ }

    // ── Frozen-pose tracker ── per frame, note whether any VRM's skeleton ever
    // moved (marker bones vs their frame-1 pose). At end-of-render we hard-flag
    // a VRM that spent the WHOLE render in its load pose — a T-pose statue means
    // no animation was ever played AND no controller was ever stepped (a
    // VRMRobotBody/controller you forgot to update(t, dt) each frame, or a
    // playVRMADefault call that never happened). The lipsync tracker can't catch
    // this: a frozen body with a silent mouth passes both unless we check bones.
    try {
        const vs = [];
        if (globalThis._vrm) vs.push(globalThis._vrm); if (globalThis._v) vs.push(globalThis._v);
        if (_reg) for (const [vv] of _reg) vs.push(vv);
        if (Array.isArray(globalThis._vrms)) for (const vv of globalThis._vrms) vs.push(vv);
        const track = (globalThis.__poseVrms ||= new Set());
        for (const vv of vs) {
            if (!vv || !vv.humanoid || vv.__poseMoved) continue;
            track.add(vv);
            const bones = vv.__poseBones ||= ['leftUpperArm', 'rightUpperLeg', 'hips']
                .map((b) => (vv.humanoid.getNormalizedBoneNode ? vv.humanoid.getNormalizedBoneNode(b) : null))
                .filter(Boolean);
            if (!bones.length) continue;
            if (!vv.__poseBase) {
                vv.__poseBase = bones.map((b) => b.quaternion.toArray().concat(b.position.y));
            } else {
                for (let bi = 0; bi < bones.length; bi++) {
                    const b = bones[bi], base = vv.__poseBase[bi];
                    const dq = Math.abs(b.quaternion.x - base[0]) + Math.abs(b.quaternion.y - base[1])
                        + Math.abs(b.quaternion.z - base[2]) + Math.abs(b.quaternion.w - base[3]);
                    if (dq > 0.01 || Math.abs(b.position.y - base[4]) > 0.01) { vv.__poseMoved = true; break; }
                }
            }
        }
    } catch (e) { /* never break the render */ }

    // ── Camera-motion tracker ── record the camera world position + fov each frame
    // (cheap: 4 numbers, no allocation). Analysed once at end-of-render to flag a
    // rapid "bouncing zoom"/jitter — the camera lurching in-and-out over a few
    // frames instead of one smooth move (a recurring codex pattern: high-frequency
    // sin() on the dolly/fov, or re-triggering a zoom every few frames).
    try {
        const cam = globalThis._camera || globalThis._c;
        if (cam && cam.isCamera) {
            cam.updateWorldMatrix(true, false);
            const e = cam.matrixWorld.elements;
            (globalThis.__camTrack ||= []).push([e[12], e[13], e[14], cam.isPerspectiveCamera ? (cam.fov || 0) : 0]);
        }
    } catch (e) { /* never break the render */ }

    // Seat settles (seatOn transition mode), processed AFTER this frame's
    // mixer.update so the descending/seated pose is applied:
    //   • per-frame CLAMP from clampFrom → keeps the lowering butt from clipping
    //     through the seat DURING the descent (raycast affects the descent, not
    //     just the end);
    //   • one-shot final SETTLE at finalAt → precise mesh-to-mesh butt-on-seat.
    // The clamp ONLY runs during the descent window [clampFrom, finalAt) — once
    // finalDone is set it STOPS. (It was running every frame forever, so the
    // per-frame grid raycast kept firing through the whole seated phase and
    // dragged 1080p renders down to ~0.5fps — the descent is the only time the
    // butt is moving toward the seat; after the final settle the pose is static.)
    if (globalThis._seatSettles && globalThis._seatSettles.length) {
        for (const s of globalThis._seatSettles) {
            if (s.clamp && s.clampFrom != null && t >= s.clampFrom && !s.finalDone) { try { s.clamp(); } catch (e) { /* keep rendering */ } }
            if (!s.finalDone && s.finalAt != null && t >= s.finalAt) { s.finalDone = true; try { s.apply(); } catch (e) { /* keep rendering */ } }
            // legacy one-shot shape (back-compat)
            if (!s.done && s.atTime != null && t >= s.atTime) { s.done = true; try { s.apply && s.apply(); } catch (e) {} }
        }
    }

    // ── Foot-slide / hand-rolled-locomotion detector ──
    // Locomotion must go through VRMCharacterController, which syncs stride to
    // travel speed and grounds the feet with IK. The recurring bug is a scene
    // that translates the VRM by hand (`vrm.scene.position.set(lerp(...))`)
    // while playing a STATIONARY VRMA clip ('walk'/'run') — she slides sideways
    // with no real stride. We can't fix the rig from here, so we DETECT it:
    // measure each VRM's horizontal travel; any VRM that moves a real distance
    // without being registered by a controller (see _controllerVrms) gets
    // flagged + summarised as RE-RENDER REQUIRED. Opt out (a VRM riding a
    // vehicle, intentional teleport) with globalThis._allowManualLocomotion=true.
    if (!globalThis._noLocomotionCheck) try {
        const THREE = globalThis.THREE;
        const vrms = [];
        if (globalThis._vrm?.scene) vrms.push(globalThis._vrm);
        if (Array.isArray(globalThis._vrms)) for (const v of globalThis._vrms) if (v?.scene) vrms.push(v);
        const L = globalThis._locoStats || (globalThis._locoStats = new Map());
        for (const vrm of vrms) {
            const root = vrm.scene;
            const p = new THREE.Vector3(); root.getWorldPosition(p);
            let rec = L.get(root);
            if (!rec) { rec = { path: 0, last: p.clone(), peak: 0, name: root.name || '(vrm)' }; L.set(root, rec); continue; }
            const dx = p.x - rec.last.x, dz = p.z - rec.last.z;
            const step = Math.hypot(dx, dz);
            if (step > 0.004) {            // ignore sub-mm jitter
                rec.path += step;
                const sp = step / dt;
                if (sp > rec.peak) rec.peak = sp;
            }
            rec.last.copy(p);
        }
    } catch (e) { /* detection must never break the render */ }

    // Sideways-traveler tracking: an elongated prop (vehicle, train, boat,
    // creature) animated by raw position writes travels PERPENDICULAR to its
    // own length when the agent never couples heading to travel (the
    // popemobile bug: built nose-along-Z, animated along X, yaw never set).
    // Sample root objects every 10 frames; summary after the loop.
    if (!globalThis._noMotionCheck && i % 10 === 0) try {
        const THREE = globalThis.THREE;
        const scene = globalThis._s || globalThis._scene;
        const M = globalThis._motionStats || (globalThis._motionStats = new Map());
        const vrmRoots = new Set();
        if (globalThis._vrm?.scene) vrmRoots.add(globalThis._vrm.scene);
        if (Array.isArray(globalThis._vrms)) for (const v of globalThis._vrms) if (v?.scene) vrmRoots.add(v.scene);
        for (const root of scene?.children || []) {
            if (!root.visible || root.isLight || root.isCamera) continue;
            if (vrmRoots.has(root) || root.userData?.vrm || root.userData?.noMotionCheck) continue;
            if (!(root.isGroup || root.isMesh)) continue;
            let rec = M.get(root);
            if (!rec) {
                const box = new THREE.Box3().setFromObject(root);
                if (box.isEmpty()) continue;
                const sx = box.max.x - box.min.x, sz = box.max.z - box.min.z;
                const elong = Math.max(sx, sz) / Math.max(0.001, Math.min(sx, sz));
                // local long axis ≈ the world long axis at first sight, un-rotated
                const wq = root.getWorldQuaternion(new THREE.Quaternion());
                const axisW = sx >= sz ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 0, 1);
                const axisL = axisW.clone().applyQuaternion(wq.clone().invert());
                rec = { name: root.name || '(unnamed)', elong, axisL, last: root.getWorldPosition(new THREE.Vector3()), path: 0, moveSegs: 0, sideSegs: 0 };
                M.set(root, rec);
                continue;
            }
            const p = root.getWorldPosition(new THREE.Vector3());
            const dx = p.x - rec.last.x, dz = p.z - rec.last.z;
            const seg = Math.hypot(dx, dz);
            if (seg > 0.05) {
                rec.path += seg;
                rec.moveSegs++;
                const wq = root.getWorldQuaternion(new THREE.Quaternion());
                const ax = rec.axisL.clone().applyQuaternion(wq); ax.y = 0;
                if (ax.lengthSq() > 1e-6) {
                    ax.normalize();
                    const cos = Math.abs((ax.x * dx + ax.z * dz) / seg);
                    if (cos < 0.5) rec.sideSegs++;             // >60° off its own length
                }
            }
            rec.last.copy(p);
        }
    } catch (e) { /* detection must never break the render */ }

    // NodeMaterial .opacity misuse: on this stack a NodeMaterial's `.opacity`
    // number does NOT bind — fades written to it silently do nothing (or the
    // plane renders fully opaque). Detect once mid-render, warn loudly.
    if (i === 30 && !globalThis._noOpacityCheck) try {
        const scene = globalThis._s || globalThis._scene;
        const seen = new Set();
        scene?.traverse(o => {
            if (!o.isMesh) return;
            for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
                if (!m || seen.has(m)) continue;
                seen.add(m);
                if (m.isNodeMaterial && m.transparent && m.opacity < 0.999 && !m.opacityNode) {
                    console.warn(`[materials] ⚠ NodeMaterial '.opacity' DOES NOT BIND on this stack — mesh '${o.name || m.name || m.type}' sets opacity=${m.opacity.toFixed(2)} with no opacityNode, so the fade silently does nothing (or renders opaque). Use an opacityNode uniform (const op = uniform(1); mat.opacityNode = op; op.value = ... per frame) or do fades/cards in ffmpeg post.`);
                }
            }
        });
    } catch (e) { /* detection must never break the render */ }

    // Anti-frozen-frame guarantee: if renderFrame() updated state but never
    // landed a scene render on the swap-chain (the CustomEffectsDeno `else`
    // miswire — _fx.update only sets uniforms), render it now so the readback
    // copies THIS frame, not the warm-up texture. Warn once so the log shows
    // the scene's renderFrame is mis-wired.
    if (_frameRenderCount === 0) {
        if (!_warnedNoRender) {
            _warnedNoRender = true;
            console.warn('[render_scene] ⚠ renderFrame() did NOT call renderer.renderAsync/render this frame — the harness is rendering for you to avoid a frozen video. If you use CustomEffectsDeno, call BOTH `await _fx.update(t)` AND `await renderer.renderAsync(scene, camera)` every frame: update() only sets effect uniforms, it does NOT render. An `else` between them freezes the swap-chain.');
        }
        try {
            const _gs = globalThis._s || globalThis._scene;
            const _gc = globalThis._c || globalThis._camera;
            if (_guardRenderer && _gs && _gc) await _guardRenderer.renderAsync(_gs, _gc);
        } catch (e) { console.warn('[render_scene] fallback render failed:', e.message); }
    }

    // Pipelined readback: returns the PREVIOUS frame's data while the
    // current frame's GPU copy starts in parallel. First call returns
    // null (no prev). drainReadback() after the loop flushes the last.
    const prevData = await readbackFrame(harness);
    if (prevData) await ffmpeg.write(prevData);
    if (i % 15 === 0 || i === totalFrames - 1) {
        const elapsed = (performance.now() - tStart) / 1000;
        console.log(`[render_scene] frame ${i+1}/${totalFrames} — ${elapsed.toFixed(2)}s, ${((i+1)/elapsed).toFixed(1)} fps`);
    }
}

// Drain the last in-flight readback so the final frame is written.
const finalData = await drainReadback(harness);
if (finalData) await ffmpeg.write(finalData);

if (typeof globalThis.cleanup === 'function') {
    try { await globalThis.cleanup(); } catch (e) { console.warn('cleanup threw:', e.message); }
}

// Foot-slide / hand-rolled-locomotion summary — a VRM that travelled a real
// distance without a VRMCharacterController is sliding (stationary clip +
// position lerp). The engine can't fix the rig; it flags it as a re-render.
if (globalThis._locoStats && !globalThis._allowManualLocomotion) {
    const ctrl = globalThis._controllerVrms;
    const slid = [];
    for (const [root, rec] of globalThis._locoStats) {
        const driven = ctrl && ctrl.has(root);
        if (!driven && rec.path > 1.5) slid.push(rec);   // > 1.5m of travel = walking, not a sway
    }
    if (slid.length) {
        for (const r of slid) {
            console.warn(`[locomotion] ⚠ RE-RENDER REQUIRED — VRM '${r.name}' travelled ${r.path.toFixed(1)}m (peak ${r.peak.toFixed(1)} m/s) WITHOUT a VRMCharacterController — it slides while playing a stationary clip. Route locomotion through the controller (it syncs stride to speed + grounds feet with IK); never move a VRM by position.set()/lerp while playing 'walk'/'run'. If this VRM is intentionally carried (vehicle/teleport), set globalThis._allowManualLocomotion = true.`);
        }
    } else if (globalThis._locoStats.size) {
        console.log(`[locomotion] OK — no hand-rolled VRM travel detected.`);
    }
}

// Production-palette report: what this render actually used, as a single
// informational line — agents get a mirror of their own scene richness, plus
// (for full-length productions only) a one-line pointer to the unused
// showpiece menu. INFO ONLY — never a re-render demand; creative choice is
// the agent's. Tools self-register in globalThis._eidoToolUsage.
try {
    const scene = globalThis._s || globalThis._scene;
    if (scene) {
        let meshes = 0, lights = 0;
        const geoSet = new Set();
        scene.traverse(o => {
            if (o.isMesh && o.visible) { meshes++; if (o.geometry) geoSet.add(o.geometry.uuid); }
            if (o.isLight) lights++;
        });
        const tools = [...(globalThis._eidoToolUsage || [])];
        if ((globalThis._autoParticleSystems?.length || 0) > 0 && !tools.includes('makeParticles')) tools.push('makeParticles');
        if ((globalThis._autoScreens?.length || 0) > 0 && !tools.includes('makeScreen')) tools.push('makeScreen');
        if ((globalThis._autoCreatures?.length || 0) > 0 && !tools.includes('makeCreature')) tools.push('makeCreature');
        if ((globalThis._autoRobots?.length || 0) > 0 && !tools.includes('robotics_kit')) tools.push('robotics_kit');
        // auto-enhance state comes from the TSL-pipeline install flag —
        // _fx is the scene's CustomEffectsDeno handle, a different thing
        // (the old check reported 'off' on every auto-enhanced render)
        const fx = globalThis.__autoEnhanceActive ? 'on' : 'off';
        console.log(`[palette] ${meshes} visible meshes (${geoSet.size} distinct geometries), ${lights} lights, auto-enhance ${fx}, toolkit used: ${tools.length ? tools.join(', ') : 'none'}`);
        if (!tools.length && duration >= 15) {
            // Genre-aware nudge: scan the scene's object/material names + the
            // brief for trigger words, and name the SPECIFIC showpiece that fits
            // this content. Still a creative nudge, never a re-render demand
            // (a scene may legitimately want none) — but a pointed "your bar
            // scene used no pour sim" lands far harder than a generic menu.
            let blob = '';
            try { scene.traverse(o => { if (o.name) blob += ' ' + o.name; if (o.material && o.material.name) blob += ' ' + o.material.name; }); } catch (_) {}
            try { blob += ' ' + Deno.readTextFileSync('_brief.txt'); }
            catch (_) { try { blob += ' ' + Deno.readTextFileSync('/workspace/_brief.txt'); } catch (__) {} }
            blob = blob.toLowerCase();
            const TRIGGERS = [
                ['fluid_3d (real 3D liquid that pours + collides)', ['water', 'liquid', 'pour', 'drink', 'coffee', 'tea', 'juice', 'potion', 'beer', 'wine', 'cocktail', ' bar ', 'kitchen', ' lab', 'chemical', 'fountain', 'splash', 'flood', 'blood', ' oil', 'milk', 'soup', 'elixir', 'serum']],
                ['cloth_sim (flags / banners / capes / curtains / fabric — with collision + text-on-cloth)', ['flag', 'banner', 'cape', 'curtain', 'fabric', 'cloth', ' sail', 'tapestry', 'drape', 'tablecloth', ' robe', 'scarf', ' veil', 'awning']],
                ['Loft.sweep (vases / horns / pipes / ducts / columns / ornament / ribbons)', ['vase', ' horn', ' pipe', ' duct', 'column', 'pillar', 'ornament', 'spiral', 'ribbon', 'bottle', 'goblet', 'trumpet', 'vessel', ' urn', 'chalice', 'tentacle', 'archway']],
                ['makeParticleMorph (dissolve / reform ANY mesh, text, or a VRM mid-pose)', ['dissolve', 'transform', 'materializ', 'reform', 'shatter', 'disintegrat', ' morph', 'assemble', 'teleport', 'reveal', 'manifest', 'emerge']],
                ['makeParticles (smoke / fire / sparks / dust / embers / magic)', ['smoke', ' fire', 'spark', 'ember', ' dust', 'magic', 'flame', 'explos', ' glow', 'firefly', ' ash', 'steam', 'incense']],
            ];
            const hits = TRIGGERS.filter(([, kws]) => kws.some(k => blob.includes(k)));
            if (hits.length) {
                console.log(`[palette] ⚠ This scene's content reads like it WANTS a showpiece and used none. Strong fit for what's in it: ${hits.map(h => h[0]).join('  •  ')}. These are the engine's flagships and almost no production reaches for them — weaving the matching one in is usually the line between "fine" and "memorable". (Creative call, not a hard gate — but a pointed one.)`);
            } else {
                console.log(`[palette] note — no simulation/particle showpiece in this production. The under-used flagships (see AGENTS.md "Pick a SHOWPIECE"): fluid_3d (3D liquid), cloth_sim (fabric), Loft.sweep (lofted forms), makeParticles, makeParticleMorph (dissolve/reform any mesh). One showpiece is often the difference between fine and memorable. Your call.`);
            }
        }
    }
} catch (e) { /* report must never break the render */ }

// Sideways-traveler summary — an elongated object that crossed the scene with
// its LENGTH perpendicular to its travel was animated without heading (the
// popemobile bug: position lerp on one axis, yaw never set).
if (globalThis._motionStats) {
    let flagged = 0;
    for (const [, rec] of globalThis._motionStats) {
        if (rec.path > 2.5 && rec.elong >= 1.35 && rec.moveSegs >= 4 && rec.sideSegs / rec.moveSegs > 0.6) {
            flagged++;
            console.warn(`[motion] ⚠ RE-RENDER REQUIRED — object '${rec.name}' travelled ${rec.path.toFixed(1)}m SIDEWAYS (its long axis stayed ~perpendicular to its travel direction for ${Math.round(100 * rec.sideSegs / rec.moveSegs)}% of the trip). A vehicle/creature must FACE where it goes: use driveAlong(obj, waypoints, { duration, forward }) for the whole move (it couples position to heading), or faceToward(obj, target, { forward }) before a straight-line lerp. Read the model's nose axis off its *_preview.jpg. If the sideways slide is intentional (conveyor, crab, drift), set obj.userData.noMotionCheck = true.`);
        }
    }
    if (!flagged && globalThis._motionStats.size) {
        console.log('[motion] OK — no sideways travelers.');
    }
}

// Lipsync summary — flag any VRM whose mouth never animated across the render.
if (globalThis.__lipsyncVrms && globalThis.__lipsyncVrms.size) {
    for (const vv of globalThis.__lipsyncVrms) {
        const nm = (vv.scene && vv.scene.name) || '(vrm)';
        if (!vv.__mouthMoved) {
            console.warn(`[lipsync] ⚠ VRM '${nm}' mouth NEVER moved across the render. If this character SPEAKS, you forgot to drive lipsync — lipsync.py get_viseme_timeline(vocals.wav, fps) → per frame set expressionManager visemes (aa/ih/ou/ee/oh) + em.update(). A talking head with a frozen mouth reads as broken; re-render with visemes. If the character is intentionally silent, ignore.`);
        } else {
            console.log(`[lipsync] OK — VRM '${nm}' mouth animated.`);
        }
    }
}

// Frozen-pose summary — hard-flag any VRM that never left its load pose.
if (globalThis.__poseVrms && globalThis.__poseVrms.size) {
    for (const vv of globalThis.__poseVrms) {
        const nm = (vv.scene && vv.scene.name) || '(vrm)';
        if (!vv.__poseMoved) {
            console.warn(`[vrm-pose] ⚠ RE-RENDER REQUIRED — VRM '${nm}' NEVER left its load pose (a T-pose statue for the whole render). No animation ever advanced its skeleton: either play a clip (playVRMADefault(vrm, 'idle')) + mixer.update(dt) per frame, or — if it has a controller/VRMRobotBody — call its update(t, dt) every frame in renderFrame. A frozen T-pose character is a broken shot, same class as a black frame.`);
        } else {
            console.log(`[vrm-pose] OK — VRM '${nm}' skeleton animated.`);
        }
    }
}

// Camera-motion summary — flag rapid "bouncing zoom" / jitter (camera lurching
// in-and-out repeatedly instead of one smooth move). Counts direction reversals
// in the camera's per-frame translation and fov; a smooth dolly/zoom reverses
// 0-2 times total, a bounce reverses many times per second. Amplitude-gated so
// subtle handheld micro-shake doesn't trip it — only large rapid oscillation.
try {
    const tr = globalThis.__camTrack;
    if (tr && tr.length > 8) {
        const n = tr.length, durS = Math.max(0.1, n / fps);
        let posRev = 0, fovRev = 0, maxPosSwing = 0, maxFovSwing = 0;
        let prevV = null, prevFovD = null;
        for (let k = 1; k < n; k++) {
            const vx = tr[k][0] - tr[k - 1][0], vy = tr[k][1] - tr[k - 1][1], vz = tr[k][2] - tr[k - 1][2];
            const vmag = Math.hypot(vx, vy, vz);
            if (prevV) {
                const pmag = Math.hypot(prevV[0], prevV[1], prevV[2]);
                if (vx * prevV[0] + vy * prevV[1] + vz * prevV[2] < 0 && vmag > 0.01 && pmag > 0.01) {
                    posRev++; maxPosSwing = Math.max(maxPosSwing, Math.min(vmag, pmag));
                }
            }
            prevV = [vx, vy, vz];
            const fd = tr[k][3] - tr[k - 1][3];
            if (prevFovD !== null && fd * prevFovD < 0 && Math.abs(fd) > 0.05) {
                fovRev++; maxFovSwing = Math.max(maxFovSwing, Math.min(Math.abs(fd), Math.abs(prevFovD)));
            }
            prevFovD = fd;
        }
        const posRate = posRev / durS, fovRate = fovRev / durS;
        const posBad = posRate > 5 && maxPosSwing > 0.02;     // >5 reversals/s, >2cm/frame swing
        const fovBad = fovRate > 5 && maxFovSwing > 0.3;      // >5 reversals/s, >0.3°/frame swing
        if (posBad || fovBad) {
            const parts = [];
            if (posBad) parts.push(`${posRev} position reversals (${posRate.toFixed(1)}/s)`);
            if (fovBad) parts.push(`${fovRev} fov/zoom reversals (${fovRate.toFixed(1)}/s)`);
            console.warn(`[camera] ⚠ RE-RENDER — camera BOUNCES: ${parts.join(', ')}. The camera lurches in-and-out repeatedly instead of moving smoothly. Use ONE eased move per shot (lerp position + fov across the WHOLE shot with smoothstep); never drive the dolly/fov with a high-frequency sin(), and never re-trigger a "zoom in" every few frames. Cut between shots, don't bounce within one. (Subtle handheld is fine — this is large rapid oscillation.)`);
        } else {
            console.log(`[camera] OK — smooth camera (${posRate.toFixed(1)} pos reversals/s).`);
        }
    }
} catch (e) { /* never break the render */ }

const status = await ffmpeg.close();
await shutdown(harness);
console.log(`[render_scene] DONE — ffmpeg exit ${status.code} — output: ${outputVideo}`);
Deno.exit(status.success ? 0 : 1);
