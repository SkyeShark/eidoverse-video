/**
 * Shared engine helpers (RenderKit) for the render_*.mjs tools:
 *   loadConfig, setupRenderer, setupScene, getCameraAtTime, logProgress,
 *   startFfmpegPipe, readbackFrame, rasterizeUI, alphaComposite, shutdown.
 *
 * Architecture notes:
 *   - No browser process. Three.js + scene scripts run in the same Deno VM.
 *   - WebGPURenderer — backed by wgpu-rs in Deno.
 *   - rawvideo→ffmpeg-nvenc pipe by default (no PNG-per-frame disk writes).
 *   - UI overlays rasterized via Satori (HTML+CSS → SVG → resvg → RGBA).
 *
 * Y-orientation rules (don't touch unless you've read the POC notes):
 *   - WebGPU copyTextureToBuffer: top-down (texel 0,0 = top-left).
 *   - resvg pixels: top-down.
 *   - ffmpeg -pix_fmt rgba rawvideo stdin: top-down.
 *   All three align natively. NO row-reverse, NO -vf vflip.
 *   Exception: a THREE.RenderTarget.texture sampled by a mesh in another
 *   scene needs UV flip: `mesh.material.map.repeat.set(1,-1); .offset.set(0,1)`.
 *   (No flipY anywhere — keep all textures in their default orientation.)
 */

import { DOMParser } from "jsr:@b-fuze/deno-dom";

// --- Config ---

export function loadConfig(configPath) {
    if (!configPath) {
        console.error('Usage: deno run --allow-all --unstable-webgpu <tool>.mjs <config.json>');
        Deno.exit(1);
    }
    return JSON.parse(Deno.readTextFileSync(configPath));
}

// --- Camera path interpolation ---

export function getCameraAtTime(t, cameraPath, defaultPos, defaultTarget) {
    if (!cameraPath || cameraPath.length === 0) {
        return { position: defaultPos, target: defaultTarget };
    }
    if (cameraPath.length === 1) {
        return {
            position: cameraPath[0].position || defaultPos,
            target: cameraPath[0].target || defaultTarget,
        };
    }
    // Find segment containing t
    let i = 0;
    for (; i < cameraPath.length - 1; i++) {
        if (cameraPath[i + 1].time > t) break;
    }
    const a = cameraPath[i];
    const b = cameraPath[Math.min(i + 1, cameraPath.length - 1)];
    if (a === b) return { position: a.position || defaultPos, target: a.target || defaultTarget };
    const span = (b.time - a.time) || 1;
    const u = Math.max(0, Math.min(1, (t - a.time) / span));
    // Smoothstep
    const s = u * u * (3 - 2 * u);
    const lerp = (p, q) => [p[0] + (q[0] - p[0]) * s, p[1] + (q[1] - p[1]) * s, p[2] + (q[2] - p[2]) * s];
    return {
        position: lerp(a.position || defaultPos, b.position || defaultPos),
        target: lerp(a.target || defaultTarget, b.target || defaultTarget),
    };
}

// --- Logging ---

export function logProgress(toolName, i, total, t) {
    if (i % 15 === 0 || i === total - 1) {
        console.log(`[${toolName}] frame ${i + 1}/${total} at t=${t.toFixed(2)}s`);
    }
}

// --- Renderer setup ---

class FakeGPUCanvasContext {
    constructor(canvas) {
        this.canvas = canvas;
        this._texture = null;
        this._configureCount = 0;
        this._getTextureCount = 0;
    }
    configure(opts) {
        if (this._texture) try { this._texture.destroy(); } catch {}
        this._texture = opts.device.createTexture({
            size: [this.canvas.width, this.canvas.height, 1],
            format: opts.format,
            usage: opts.usage | GPUTextureUsage.COPY_SRC,
        });
        this._configureCount++;
        if (this._configureCount <= 5 || this._configureCount % 30 === 0) {
            console.log(`[FakeGPUCanvasContext] configure #${this._configureCount} (format=${opts.format})`);
        }
    }
    unconfigure() { if (this._texture) try { this._texture.destroy(); } catch {}; this._texture = null; }
    getCurrentTexture() {
        this._getTextureCount++;
        if (this._getTextureCount === 1 || this._getTextureCount === 30 || this._getTextureCount === 100) {
            console.log(`[FakeGPUCanvasContext] getCurrentTexture #${this._getTextureCount} (configures so far: ${this._configureCount})`);
        }
        return this._texture;
    }
}

/**
 * Initialise WebGPU + deno-dom + browser shims. Returns a harness containing
 * the device, canvas, fake context, and the loaded THREE module.
 *
 * Call once per process. Subsequent setupScene() calls reuse the same
 * adapter/device/canvas (multi-scene scripts can render to different scenes
 * with the same renderer).
 */
export async function setupRenderer(width, height) {
    if (!navigator.gpu) throw new Error('navigator.gpu missing — run with --unstable-webgpu');

    const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
    if (!adapter) throw new Error('No WebGPU adapter found');
    // Request 'core-features-and-limits' so Three.js's WebGPU backend doesn't
    // fall into compatibilityMode. Compat mode downgrades MRT (kills the
    // depth/normal channels GTAO/SSR need), restricts shader features, and
    // limits buffer/texture sizes. Without this feature flag, Three sets
    // backend.compatibilityMode = true and we get "Multiple Render Targets
    // (MRT) blending configuration is not fully supported" warnings on every
    // render. Only include features the adapter actually supports — wgpu-rs
    // throws if you request an unavailable feature.
    const requiredFeatures = [];
    for (const f of ['core-features-and-limits']) {
        if (adapter.features.has(f)) requiredFeatures.push(f);
        else console.warn(`[render_common] adapter missing WebGPU feature: ${f} — Three may run in compatibility mode`);
    }
    // Raise buffer/limit caps to the adapter maximum so large GPU sims
    // (multi-million-particle fluids, big grids) can allocate storage buffers
    // bigger than the 128MB spec-default binding cap. Requesting exactly the
    // adapter's reported max is always valid; it just unlocks the headroom the
    // 4090 already has.
    const requiredLimits = {};
    for (const k of ['maxStorageBufferBindingSize', 'maxBufferSize', 'maxUniformBufferBindingSize']) {
        const v = adapter.limits?.[k];
        if (v != null) requiredLimits[k] = v;
    }
    const device = await adapter.requestDevice({ requiredFeatures, requiredLimits });
    console.log(`[render_common] device buffer limits: storageBinding=${device.limits.maxStorageBufferBindingSize}, maxBuffer=${device.limits.maxBufferSize}`);

    // PATCH: deno 2.8.x's wgpu stopped ADVERTISING 'core-features-and-limits'
    // even though its core D3D12/Vulkan path has the full capabilities (deno
    // 2.7 reports it, and the production stack runs Three's FULL mode on the
    // same wgpu family + GPU daily). Three r184 keys compatibilityMode off
    // device.features.has('core-features-and-limits'); compat mode serializes
    // MRT + downgrades the whole pipeline — measured ~30x slower on real
    // scenes (kitchen-sink reel: 1.1fps vs near-realtime). Shim the set-like
    // so Three sees full mode.
    if (!device.features.has('core-features-and-limits')) {
        const orig = device.features;
        const shim = {
            has: (f) => f === 'core-features-and-limits' || orig.has(f),
            [Symbol.iterator]: function* () { yield 'core-features-and-limits'; yield* orig; },
            get size() { return orig.size + 1; },
            forEach(cb, thisArg) { for (const f of this) cb.call(thisArg, f, f, this); },
        };
        try {
            Object.defineProperty(device, 'features', { value: shim, configurable: true });
            console.log("[render_common] features shim active: reporting 'core-features-and-limits' so Three runs FULL mode (deno 2.8 wgpu omits the flag; capabilities are present)");
        } catch (e) {
            console.warn('[render_common] features shim failed (staying in compat mode):', e.message);
        }
    }

    // PATCH: WGSL u32 LOD literals → signed-int LOD before Naga sees them.
    // Three's TSL (SSRNode, GTAONode, etc) emits `u32( 0 )` as the LOD arg of
    // textureLoad / textureDimensions. Naga's GLSL backend preserves uint and
    // emits `textureSize(sampler, 0u)` in GLSL — Mesa Gallium D3D12's GLSL
    // frontend (the only path Deno+wgpu-rs uses in our WSL2 docker) only has
    // `textureSize(sampler, int)` overloads, so the shader fails to compile and
    // the entire pass silently produces zero output. Stripping the u32() wrap
    // makes Naga emit signed int and Mesa accepts it.
    // Matches u32(0), u32(0u) AND u32( 0.0 ): the equirect-HDRI env sampler
    // emits the FLOAT-zero form `textureDimensions( env, u32( 0.0 ) )`, which
    // only surfaces once a transparent material forces the env shader to
    // recompile (e.g. a transparent fluid surface in front of an HDRI scene).
    const _origCSM = device.createShaderModule.bind(device);
    device.createShaderModule = function(desc) {
        const orig = desc.code || '';
        const code = orig.replace(/\bu32\s*\(\s*0(?:\.0+)?u?\s*\)/g, '0');
        return code !== orig ? _origCSM({ ...desc, code }) : _origCSM(desc);
    };

    // PATCH: rgba32float as RENDER_ATTACHMENT → downgrade to rgba16float.
    // wgpu-rs+Mesa-Gallium-D3D12 has a downlevel restriction:
    //   "Texture usages TextureUsages(RENDER_ATTACHMENT) are not allowed
    //    on a texture of type Rgba32Float due to downlevel restrictions"
    // Three.js's WebGPU backend allocates rgba32float RTs in some scene
    // configurations (observed at multi-GLB scenes when material count
    // pushes some autoenhance/MRT precision heuristic over a threshold).
    // Those creates fail and cascade to "Texture invalid" → "BindGroup
    // invalid" → 100+ errors per frame → all-black output.
    //
    // rgba16float (half-precision float) IS renderable on this backend
    // and provides enough precision for HDR scene/normals/SSR/MRT use.
    // Quietly downgrade — three.js's RT allocation logic doesn't have to
    // know about the backend limit.
    const RENDER_ATTACHMENT = 0x10;  // GPUTextureUsage.RENDER_ATTACHMENT
    const _origCreateTex = device.createTexture.bind(device);
    let _downgradeCount = 0;
    let _stripRACount = 0;
    device.createTexture = function(desc) {
        if (desc.format === 'rgba32float' && (desc.usage & RENDER_ATTACHMENT) !== 0) {
            const w = desc.size?.width || desc.size?.[0];
            const h = desc.size?.height || desc.size?.[1] || 1;
            const arr = (desc.size?.depthOrArrayLayers ?? desc.size?.[2] ?? 1);
            // PATCH (morph fix): Three.js's WebGPU backend sets RENDER_ATTACHMENT in
            // the default usage mask of every texture. For rgba32float DataArrayTextures
            // used as sampled morph/skinning buffers (height=1, 1D-like data), this
            // RENDER_ATTACHMENT bit is spurious AND breaks the texture on Mesa Gallium
            // D3D12 — Mesa rejects rgba32float + RENDER_ATTACHMENT under downlevel
            // restrictions, and our format-downgrade path corrupts Float32 source
            // data when reinterpreted as f16.
            // For these 1D-like sampled buffers, strip the RENDER_ATTACHMENT bit and
            // keep rgba32float (Mesa allows rgba32float as a sampled texture).
            if (h === 1) {
                _stripRACount++;
                if (_stripRACount <= 3) {
                    console.log(`[render_common] stripping RENDER_ATTACHMENT from morph-like rgba32float texture (${w}x${h}x${arr})`);
                }
                return _origCreateTex({ ...desc, usage: desc.usage & ~RENDER_ATTACHMENT });
            }
            // Standard render-target case (HDR FB, MRT, etc): downgrade format to
            // rgba16float (renderable on this backend, half-precision is enough for
            // HDR scene/normal/SSR buffers).
            _downgradeCount++;
            if (_downgradeCount <= 3) {
                console.log(`[render_common] downgrading rgba32float→rgba16float for RENDER_ATTACHMENT texture (${desc.label || '?'} ${w}x${h})`);
            }
            return _origCreateTex({ ...desc, format: 'rgba16float' });
        }
        return _origCreateTex(desc);
    };

    // deno-dom document + canvas — Three.js's WebGPURenderer needs a real
    // HTMLCanvasElement with .getContext('webgpu') returning a configurable
    // GPUCanvasContext. We back that with our fake one.
    // Also pre-install a #ui-overlay div so scene scripts that write into
    // `document.getElementById('ui-overlay')` (production convention) get a
    // real element back — actual rasterization to a 3D mesh comes later via
    // the Satori-HTMLMesh path.
    const doc = new DOMParser().parseFromString(
        '<html><head></head><body><canvas id="renderCanvas"></canvas><div id="ui-overlay"></div></body></html>',
        'text/html'
    );
    const canvas = doc.getElementById('renderCanvas');

    // --- Canvas 2D shim via @napi-rs/canvas ---
    // Several helpers (sdf_raymarch_loader, procedural_materials)
    // and many agent scenes call `document.createElement('canvas')` then draw
    // 2D content for use as a CanvasTexture. deno-dom's canvas has no 2D
    // context, so we shim it: createElement('canvas') returns an
    // HTMLCanvasShim wrapping a real Skia-backed canvas from @napi-rs/canvas.
    let _napiCanvasMod = null;
    try {
        _napiCanvasMod = await import('npm:@napi-rs/canvas@0.1.69');
    } catch (e) {
        console.warn('[render_common] @napi-rs/canvas unavailable; canvas-2d use will fail:', e.message);
    }
    if (_napiCanvasMod) {
        const { createCanvas } = _napiCanvasMod;
        // Symbol-capable fallback fonts, registered ONCE for every scene.
        // @napi-rs/canvas falls back to other registered families for glyphs
        // the ctx.font family lacks — so this gives all canvas-2d text
        // automatic coverage of ™ • → ∞ × ★ ♡ ° etc. WITHOUT overriding any
        // scene's chosen display font (fallback is per-missing-glyph, not
        // per-element). Scenes that register their own Latin-only display
        // fonts (BlackOps/Rajdhani/…) no longer tofu on symbols. DejaVu Sans
        // has broad symbol coverage; Noto fills CJK/emoji if present.
        try {
            const GF = _napiCanvasMod.GlobalFonts;
            if (GF && typeof GF.registerFromPath === 'function') {
                const _fallbacks = [
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                    '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
                    '/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf',
                    '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',   // color emoji (😀🎉🔥) — Skia renders the bitmaps
                ];
                let _n = 0;
                for (const p of _fallbacks) { try { if (GF.registerFromPath(p)) _n++; } catch (_) {} }
                console.log(`[render_common] registered ${_n} canvas-2d symbol fallback font(s) — text auto-fills missing glyphs (™ • → ∞ ★ …)`);
            }
        } catch (e) {
            console.warn('[render_common] canvas-2d fallback-font registration failed:', e.message);
        }
        class HTMLCanvasShim {
            constructor(w = 300, h = 150) {
                this._napi = createCanvas(w, h);
                // Mark for downstream identification (Three.js CanvasTexture interception)
                this._isShimCanvas = true;
                this.tagName = 'CANVAS';
                this.nodeName = 'CANVAS';
                this.style = {};
            }
            get width()  { return this._napi.width; }
            set width(v) { this._napi.width = v; }
            get height()  { return this._napi.height; }
            set height(v) { this._napi.height = v; }
            getContext(type, attrs) {
                if (type === '2d') return this._napi.getContext('2d', attrs);
                // Anything else (webgl, webgl2, bitmaprenderer) intentionally returns null —
                // we are WebGPU-only and 2D is the only fallback for legacy canvas use.
                return null;
            }
            toDataURL(mime = 'image/png', quality) {
                return this._napi.toDataURL(mime, quality);
            }
            toBuffer(mime = 'image/png') {
                return this._napi.toBuffer(mime);
            }
            // For Three.js CanvasTexture path that reads pixel data:
            getImageDataRGBA() {
                const ctx = this._napi.getContext('2d');
                return ctx.getImageData(0, 0, this._napi.width, this._napi.height);
            }
            addEventListener() {} removeEventListener() {} setAttribute() {} getAttribute() { return null; }
        }
        // Patch document.createElement to return our shim for canvas elements.
        const origCreateElement = doc.createElement.bind(doc);
        doc.createElement = (tag) => {
            if (typeof tag === 'string' && tag.toLowerCase() === 'canvas') {
                return new HTMLCanvasShim();
            }
            return origCreateElement(tag);
        };
        // Also expose so downstream code (Three.js CanvasTexture interception
        // in render_scene.mjs) can recognise instances.
        globalThis.HTMLCanvasShim = HTMLCanvasShim;
    }
    canvas.width = width;
    canvas.height = height;
    canvas.style = {};  // setSize touches it
    const fakeCtx = new FakeGPUCanvasContext(canvas);
    canvas.getContext = (t) => t === 'webgpu' ? fakeCtx : null;

    globalThis.window ??= globalThis;
    globalThis.self ??= globalThis;
    globalThis.document = doc;
    globalThis.HTMLCanvasElement = canvas.constructor;
    globalThis.GPUCanvasContext ??= FakeGPUCanvasContext;
    globalThis.requestAnimationFrame ??= (cb) => setTimeout(() => cb(performance.now()), 16);
    globalThis.cancelAnimationFrame ??= (id) => clearTimeout(id);

    // Load three/webgpu after globals are installed (its module init reads document).
    // Wrap in a mutable shallow copy so render_scene.mjs can monkey-patch
    // exports like WebGLRenderer (the raw module namespace is frozen — direct
    // assignment throws "Cannot assign to property 'X' of [object Module]").
    // Three 0.184: TSL display addons (GTAO/SSR/Bloom/SMAA/etc) correctly
    // import PostProcessingUtils from 'three/webgpu'. r170's addons import
    // from bare 'three' which doesn't expose it — silent addon load failures.
    //
    // 0.184 also splits exports: three/webgpu has node CLASSES (AONode,
    // PostProcessing, etc), three/tsl has TSL FUNCTIONS (pass, mrt,
    // directionToColor, normalView, builtinAOContext, renderOutput, etc).
    // r170 had everything in /webgpu. Merge both into a single mutable
    // THREE namespace so scene scripts and helpers find the names where
    // production conventionally puts them.
    const _THREE_MOD = await import('npm:three@0.184.0/webgpu');
    const _TSL_MOD   = await import('npm:three@0.184.0/tsl');
    // TSL display addons aren't in three/tsl — pull them in by name and
    // surface them on the merged THREE namespace so effects can use the
    // built-ins instead of hand-rolling (e.g. gaussianBlur for proper
    // separable Gaussian on cloud reflection blur).
    const _GAUSS_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/GaussianBlurNode.js');
    const _DOF_MOD   = await import('npm:three@0.184.0/examples/jsm/tsl/display/DepthOfFieldNode.js');
    const _SOBEL_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/SobelOperatorNode.js');
    const _DAB_MOD   = await import('npm:three@0.184.0/examples/jsm/tsl/display/depthAwareBlend.js');
    const _BAYER_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/math/Bayer.js');
    const _ANA_MOD   = await import('npm:three@0.184.0/examples/jsm/tsl/display/AnamorphicNode.js');
    const _SEPIA_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/Sepia.js');
    const _BLEACH_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/BleachBypass.js');
    const _AFTIMG_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/AfterImageNode.js');
    const _RGBSH_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/RGBShiftNode.js');
    const _RADBLUR_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/radialBlur.js');
    const _BOXBLUR_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/boxBlur.js');
    const _HASHBLUR_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/hashBlur.js');
    const _GODRAYS_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/GodraysNode.js');
    const _DENOISE_MOD = await import('npm:three@0.184.0/examples/jsm/tsl/display/DenoiseNode.js');
    const _LENSFL_MOD  = await import('npm:three@0.184.0/examples/jsm/tsl/display/LensflareNode.js');
    // BufferGeometryUtils — setup-time geometry merging for detailed procedural
    // parts (robotics_kit castings/greebles merge per rigid link to keep draw
    // calls flat). Not a TSL addon; same surfacing pattern.
    const _BGU_MOD = await import('npm:three@0.184.0/examples/jsm/utils/BufferGeometryUtils.js');
    const THREE = {
        ..._THREE_MOD, ..._TSL_MOD,
        mergeGeometries: _BGU_MOD.mergeGeometries,
        mergeVertices: _BGU_MOD.mergeVertices,
        gaussianBlur: _GAUSS_MOD.gaussianBlur,
        GaussianBlurNode: _GAUSS_MOD.default,
        dof: _DOF_MOD.dof,
        DepthOfFieldNode: _DOF_MOD.default,
        sobel: _SOBEL_MOD.sobel,
        SobelOperatorNode: _SOBEL_MOD.default,
        depthAwareBlend: _DAB_MOD.depthAwareBlend,
        bayer16: _BAYER_MOD.bayer16,
        bayerDither: _BAYER_MOD.bayerDither,
        anamorphic: _ANA_MOD.anamorphic,
        AnamorphicNode: _ANA_MOD.default,
        sepia: _SEPIA_MOD.sepia,
        bleach: _BLEACH_MOD.bleach,
        afterImage: _AFTIMG_MOD.afterImage,
        AfterImageNode: _AFTIMG_MOD.default,
        rgbShift: _RGBSH_MOD.rgbShift,
        RGBShiftNode: _RGBSH_MOD.default,
        radialBlur: _RADBLUR_MOD.radialBlur,
        boxBlur: _BOXBLUR_MOD.boxBlur,
        hashBlur: _HASHBLUR_MOD.hashBlur,
        godrays: _GODRAYS_MOD.godrays,
        GodraysNode: _GODRAYS_MOD.default,
        denoise: _DENOISE_MOD.denoise,
        DenoiseNode: _DENOISE_MOD.default,
        lensflare: _LENSFL_MOD.lensflare,
        LensflareNode: _LENSFL_MOD.default,
    };
    globalThis.THREE = THREE;  // scene scripts expect THREE on globalThis (matches /opt/render3d shell)

    // Two staging buffers + two scene-frame buffers so readback can
    // pipeline: while frame N's GPU→CPU map is in flight on slot 0,
    // we render+submit frame N+1 to slot 1, then read slot 0 once it's
    // ready. Without this the CPU stalls every frame waiting for
    // mapAsync to resolve before the next render can start.
    const bytesPerRow = Math.ceil((width * 4) / 256) * 256;
    const stageBufs = [0, 1].map(() => device.createBuffer({
        size: bytesPerRow * height,
        usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
    }));
    const sceneFrames = [
        new Uint8Array(width * height * 4),
        new Uint8Array(width * height * 4),
    ];

    return {
        adapter, device, canvas, fakeCtx, doc, THREE,
        width, height, bytesPerRow,
        // Single-buffer aliases kept for back-compat with any callers
        // that still touch .stageBuf / .sceneFrame directly.
        stageBuf: stageBufs[0], sceneFrame: sceneFrames[0],
        stageBufs, sceneFrames,
        _readbackSlot: 0,
        _pendingReadback: null,  // { slot, mapPromise } from prev frame
    };
}

/**
 * Build renderer + scene + camera + lights from a config object — same shape
 * as the production setupScene in render_common.mjs. Returns
 * { renderer, scene, camera } AND assigns them to globalThis._renderer/
 * _scene/_camera so scene scripts that expect those globals still work.
 */
export async function setupScene(harness, config) {
    const { THREE, canvas, adapter, device, width, height } = harness;

    // antialias defaults to FALSE — with WebGPU + canvas-context backed by our
    // FakeGPUCanvasContext stub, MSAA renders into Three's internal MSAA target
    // and we never see the resolved pixels in the swap-chain texture (= black
    // mp4). For real MSAA we'd need to configure a renderer-managed RenderTarget
    // and resolve manually. For now, trade smoothness for correctness.
    const renderer = new THREE.WebGPURenderer({
        canvas, antialias: config.antialias === true, adapter, device,
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    await renderer.init();

    const scene = new THREE.Scene();

    // Background
    const bg = config.background;
    if (bg === 'transparent' || bg === undefined) {
        scene.background = null;
    } else if (typeof bg === 'string') {
        scene.background = new THREE.Color(bg);
    } else if (Array.isArray(bg)) {
        scene.background = new THREE.Color(bg[0], bg[1], bg[2]);
    }

    // Lights — same defaults as production setupScene
    if (config.lights && config.lights.length > 0) {
        for (const def of config.lights) {
            let light;
            const color = new THREE.Color(def.color || '#ffffff');
            const intensity = def.intensity ?? 1;
            if (def.type === 'directional') {
                light = new THREE.DirectionalLight(color, intensity);
                if (def.position) light.position.set(...def.position);
            } else if (def.type === 'point') {
                light = new THREE.PointLight(color, intensity, def.distance || 0);
                if (def.position) light.position.set(...def.position);
            } else if (def.type === 'ambient') {
                light = new THREE.AmbientLight(color, intensity);
            } else if (def.type === 'spot') {
                light = new THREE.SpotLight(color, intensity);
                if (def.position) light.position.set(...def.position);
                if (def.target) light.target.position.set(...def.target);
            }
            if (light) scene.add(light);
        }
    } else {
        scene.add(new THREE.AmbientLight(0x404040, 1.0));
        const key = new THREE.DirectionalLight(0xffffff, 2.5);
        key.position.set(3, 5, 4);
        scene.add(key);
        const fill = new THREE.PointLight(0x8888ff, 1.5);
        fill.position.set(-2, 2, 1);
        scene.add(fill);
        const rim = new THREE.PointLight(0xff2d95, 1.0);
        rim.position.set(0, 2, -3);
        scene.add(rim);
    }

    // Camera
    const cam = config.camera || {};
    const fov = cam.fov || 45;
    const defaultPos = cam.position || [0, 1.2, 3.0];
    const defaultTarget = cam.target || [0, 0, 0];
    const camera = new THREE.PerspectiveCamera(fov, width / height, 0.01, 1000);
    camera.position.set(...defaultPos);
    camera.lookAt(new THREE.Vector3(...defaultTarget));

    // Globals for compat with scene scripts that access window._scene etc.
    globalThis._renderer = renderer;
    globalThis._scene = scene;
    globalThis._camera = camera;
    globalThis._defaultPos = defaultPos;
    globalThis._defaultTarget = defaultTarget;

    return { renderer, scene, camera, defaultPos, defaultTarget };
}

// --- ffmpeg pipe (rawvideo RGBA → h264_nvenc mp4) ---

export function startFfmpegPipe(width, height, fps, outputPath, opts = {}) {
    // Three's WebGPU canvas uses navigator.gpu.getPreferredCanvasFormat()
    // which is bgra8unorm on Linux/wgpu-rs. Our FakeGPUCanvasContext stores
    // pixels in BGRA, our readback delivers BGRA bytes. Tell ffmpeg that's
    // what the input is — without this the channels look swapped (pure red
    // renders as solid blue, etc.).
    const args = [
        '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgra', '-s', `${width}x${height}`, '-r', String(fps),
        '-i', '-',
        '-c:v', opts.codec || (typeof Deno !== 'undefined' && Deno.env.get('RENDER_CODEC')) || 'h264_nvenc',
        '-preset', opts.preset || 'fast',
        '-pix_fmt', 'yuv420p',
    ];
    // Rate control. RENDER_CQ=19 → visually near-lossless (lower = better,
    // bigger); RENDER_BITRATE=20M → explicit target. DEFAULT (neither set):
    // 8000k average / 10000k peak — nvenc's own default (~2-3 Mbps at 1080p)
    // macroblocks on high-frequency content (fluid, particles, dense motion).
    const _cq = opts.cq || (typeof Deno !== 'undefined' && Deno.env.get('RENDER_CQ'));
    const _bv = opts.bitrate || (typeof Deno !== 'undefined' && Deno.env.get('RENDER_BITRATE'));
    if (_cq) args.push('-rc', 'vbr', '-cq', String(_cq), '-b:v', '0');
    else if (_bv) args.push('-b:v', String(_bv), '-maxrate', String(_bv));
    else args.push('-b:v', '8000k', '-maxrate', '10000k', '-bufsize', '16000k');
    if (opts.audio) args.push('-i', opts.audio, '-c:a', 'aac', '-shortest');
    args.push(outputPath);

    // stderr: 'inherit' so ffmpeg's diagnostics flow straight to our stderr.
    // 'piped' would require us to drain the stream or Deno keeps the subprocess
    // handle open after exit, hanging the script indefinitely.
    const proc = new Deno.Command('ffmpeg', {
        args, stdin: 'piped', stdout: 'inherit', stderr: 'inherit',
    }).spawn();
    const writer = proc.stdin.getWriter();

    return {
        write: (rgba) => writer.write(rgba),
        async close() {
            await writer.close();
            return await proc.status;
        },
    };
}

// --- Frame readback (GPU swap-chain texture → CPU RGBA buffer) ---

// Helper used by the pipelined path — copies a finished mapped staging
// buffer's contents into its sibling sceneFrame (de-aligned), unmaps,
// returns the tight RGBA buffer.
function _drainSlot(harness, slot) {
    const { stageBufs, sceneFrames, bytesPerRow, width, height } = harness;
    const padded = new Uint8Array(stageBufs[slot].getMappedRange());
    const sceneFrame = sceneFrames[slot];
    const tightBytesPerRow = width * 4;
    if (bytesPerRow === tightBytesPerRow) {
        sceneFrame.set(padded.subarray(0, tightBytesPerRow * height));
    } else {
        for (let y = 0; y < height; y++) {
            sceneFrame.set(
                padded.subarray(y * bytesPerRow, y * bytesPerRow + tightBytesPerRow),
                y * tightBytesPerRow
            );
        }
    }
    stageBufs[slot].unmap();
    return sceneFrame;
}

export async function readbackFrame(harness) {
    // Source-texture / buffer-level override — used by EffectComposer-based
    // autoenhance to read from its internal RT. Bypasses pipelining.
    if (typeof globalThis._readbackOverride === 'function') {
        return await globalThis._readbackOverride(harness);
    }
    // PIPELINED READBACK
    // Each call submits a copy for the current frame on the current slot,
    // starts mapAsync (no await), and AWAITS the previous frame's slot
    // (already in flight from the previous call). This overlaps frame N's
    // GPU work with frame N-1's CPU readback, eliminating per-frame stalls.
    // Returns the previous frame's data, or null on the very first call.
    // Use `drainReadback(harness)` after the loop to flush the last frame.
    const { device, fakeCtx, bytesPerRow, stageBufs, width, height } = harness;
    const slot = harness._readbackSlot;
    const otherSlot = 1 - slot;

    const tex = fakeCtx.getCurrentTexture();
    const enc = device.createCommandEncoder();
    enc.copyTextureToBuffer(
        { texture: tex },
        { buffer: stageBufs[slot], bytesPerRow, rowsPerImage: height },
        [width, height, 1],
    );
    device.queue.submit([enc.finish()]);
    const thisMap = stageBufs[slot].mapAsync(GPUMapMode.READ);

    let result = null;
    const pending = harness._pendingReadback;
    if (pending) {
        await pending.mapPromise;
        result = _drainSlot(harness, pending.slot);
    }

    harness._pendingReadback = { slot, mapPromise: thisMap };
    harness._readbackSlot = otherSlot;
    return result;
}

// Drains the last in-flight readback after the render loop ends.
// Returns the final frame's data, or null if there's nothing pending.
export async function drainReadback(harness) {
    if (typeof globalThis._readbackOverride === 'function') {
        // Override path is synchronous-per-frame, nothing to drain.
        return null;
    }
    const pending = harness._pendingReadback;
    if (!pending) return null;
    harness._pendingReadback = null;
    await pending.mapPromise;
    return _drainSlot(harness, pending.slot);
}

// --- UI overlay via Satori (HTML+CSS → SVG → resvg → RGBA) ---

let _satoriCache = null;
async function loadSatori() {
    if (_satoriCache) return _satoriCache;
    const [{ default: satori }, { Resvg }] = await Promise.all([
        import('npm:satori@0.10.13'),
        import('npm:@resvg/resvg-js@2.6.2'),
    ]);
    _satoriCache = { satori, Resvg };
    return _satoriCache;
}

let _defaultFonts = null;
async function loadDefaultFonts() {
    if (_defaultFonts) return _defaultFonts;
    const [reg, bold] = await Promise.all([
        Deno.readFile('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Deno.readFile('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    ]);
    _defaultFonts = [
        { name: 'DejaVu Sans', data: reg.buffer, weight: 400, style: 'normal' },
        { name: 'DejaVu Sans', data: bold.buffer, weight: 900, style: 'normal' },
    ];
    return _defaultFonts;
}

/**
 * Rasterize a JSX-like tree (or HTML string via satori-html if needed) to RGBA.
 * Returns a Uint8Array of RGBA pixels (premultiplied), top-down, length = w*h*4.
 *
 * Pass `fonts` to override the default DejaVu pair.
 */
export async function rasterizeUI(jsxTree, width, height, fonts = null) {
    const { satori, Resvg } = await loadSatori();
    const _fonts = fonts || await loadDefaultFonts();
    const svg = await satori(jsxTree, { width, height, fonts: _fonts });
    const pixmap = new Resvg(svg, { fitTo: { mode: 'width', value: width } }).render();
    return pixmap.pixels;
}

/**
 * Alpha-blend a Satori-rasterized UI buffer over a 3D scene buffer.
 * Both are top-down RGBA. UI is premultiplied (resvg's output convention).
 * Writes into `dest` (or sceneFrame if dest === null), returns dest.
 */
export function alphaComposite(sceneFrame, uiPixels, dest) {
    const out = dest || sceneFrame;
    const len = sceneFrame.length;
    for (let p = 0; p < len; p += 4) {
        const ua = uiPixels[p + 3];
        if (ua === 0) {
            if (out !== sceneFrame) {
                out[p]   = sceneFrame[p];
                out[p+1] = sceneFrame[p+1];
                out[p+2] = sceneFrame[p+2];
                out[p+3] = sceneFrame[p+3];
            }
        } else {
            const inv = 1 - ua / 255;
            out[p]   = (uiPixels[p]   + sceneFrame[p]   * inv) | 0;
            out[p+1] = (uiPixels[p+1] + sceneFrame[p+1] * inv) | 0;
            out[p+2] = (uiPixels[p+2] + sceneFrame[p+2] * inv) | 0;
            out[p+3] = 255;
        }
    }
    return out;
}

// --- Asset loader (window.ASSETS pattern) ---

/**
 * Read each path in `assets` (dict {key: path}), base64-encode, and install
 * onto globalThis.ASSETS. Scene scripts call b64toArrayBuffer(window.ASSETS.key)
 * to get an ArrayBuffer for VRMs/HDRIs/textures.
 */
export async function loadAssets(assets) {
    const out = {};
    for (const [key, path] of Object.entries(assets || {})) {
        const bytes = await Deno.readFile(path);
        // Base64 encode
        let bin = '';
        for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
        out[key] = btoa(bin);
    }
    globalThis.ASSETS = out;
    globalThis.b64toArrayBuffer ??= (b64) => {
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        return bytes.buffer;
    };
    return out;
}

// --- Shutdown (currently a no-op; placeholder for future GPU cleanup) ---

export async function shutdown(harness) {
    try { harness.stageBuf?.destroy(); } catch {}
    try { harness.fakeCtx?.unconfigure(); } catch {}
}
