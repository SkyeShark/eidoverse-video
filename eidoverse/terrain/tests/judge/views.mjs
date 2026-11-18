// The judge's views in the three.js edition (PORT_PLAN.md 6.3): a saved terrain drawn by the port's own mesh (P4's
// build/mesh.js and build/water.js, through api.js Terrain.load) and rendered by this edition's renderer
// (eidoverse/render_scene.mjs) from the cameras of a views JSON that the Blender edition wrote for its own renders:
// a reference's blender/tests/terrain/reference/renders/<name>_views.json (render_references.py), or a judged
// terrain's <label>_views.json (judge/views.py render_field, which frames a generated terrain alike). The same rig,
// in this renderer, so a port render sits beside a Blender render of the same view.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/judge/views.mjs <save> --reference <name>
//          [--views top,aerial,eye] [--views-json <json>] [--label L] [--out <dir>]
//                  <out>/<label>_top_hillshade.png, _aerial_45deg.png, _eye_1p7m.png (the names the Blender judge's
//                  sheet reads, tests/judge/sheets.mjs) and <out>/<label>_views.json (each camera as used, in both
//                  frames). Each view is a Deno WebGPU job of its own, behind $EIDO_GPU_WRAP
//     deno run ... views.mjs --bake <dir> --places lauterbrunnen,mount_fuji,...
//                  the Blender edition's real_place save of each place (bake.py --recipe real_place --param
//                  dem=<place> --quality film --no-cache --save): the DEM's own pixels on the main level and its
//                  surround on the context levels, no focus, so no hero level; a Blender job each, behind
//                  $EIDO_GPU_WRAP, <dir>/<place>.npz + .json
//     deno run ... views.mjs --places a,b --saves <dir> [--out <dir>]
//                  each place's save rendered from its reference's views, labelled <place>_port
//
// The rig (render_references.py, as it is): grey clay of albedo 0.18, roughness 0.9 and no specular (api.js
// clayMaterial is that material, on the mesh Terrain.load builds), water of (0.02, 0.05, 0.07) at roughness 0.15,
// the Earth sky at 15:30 with cumulus and no cloud shadow on the ground (eidoverse/sky_worlds.js makeSky; the
// terrain is not wrapped into its cloud shadows), lit by the sky's sun and its baked environment alone (the rig's
// sun and world; no hemisphere light), the sun at the view's sun_dir (37.7 degrees up), AgX at +0.5 EV,
// the camera at the JSON's position, target and lens (a 36 mm sensor fitted to the frame's wider side, as Blender's
// AUTO fit), its clip planes as the rig sets them, the top view north up; the top and aerial views draw the main
// tile alone (only the main and hero rings' geometry groups, the sea the rig's plane over the tile), the eye view
// the whole ring mesh with its lakes and sea. Positions are Blender tile-local metres,
// z above the tile's lowest point (z_origin_m), turned into three.js axes as (x, z, -y) (plan 2.2); the ground is
// lifted into that frame by the save's datum (a reference's views: base_elevation_m - z_origin_m, the DEM's
// absolute metres; a judged terrain's own views: -z_origin_m). The eye view stands in the context surround (the
// save's context rings) and every vertex drops by d^2 / 2 R_eff, d its horizontal distance from the camera, as the
// rig drops its grids: in the materials' positionNode, so the mesh is P4's as it is.
//
// Where this differs from the Blender rig, and why:
//   - The sun's azimuth. The sky facade takes no azimuth (makeSky does not pass opts.azimuth on to
//     makeSkySystem), so its 15:30 sun stands where the facade puts it, and the ground and the camera are turned
//     together about the vertical by the angle between that sun and the view's. The light then falls from the same
//     direction relative to the ground and the camera, which is what the picture shows (exact for the sun and the
//     sky's lighting; the clouds stand elsewhere in the sky). The elevations agree (checked, within 0.5 degrees).
//   - The tone curve: three's AgX has no 'Medium High Contrast' look; the exposure is the rig's.
//   - Shadows: one 4096^2 map over 1.5 times the main tile (about 3 m a texel over 8 km), where EEVEE renders
//     virtual shadow maps; the context rings beyond it are unshadowed. Depth: a reversed depth buffer for the eye
//     view's 1 m to 80 km.
//   - The frames pass through the renderer's film encode (yuv420p; run here with libx264 at CRF 0) before the PNG.
//   - The post stack is off (_noAutoEnhance), as the rig has none; so the sky's domes are made without the post
//     stack's G-buffer outputs (globalThis.EANPA_NO_MRT, sky_system.js's own switch for a forward render).
//   - The sky's domes (3.2 km spheres under the camera, for cameras near the ground) are scaled to just inside the
//     far plane, so the aerial camera kilometres up sees the sky behind the tile as the rig's world shows it.
// JavaScript per view (cameras, angles, files); every pixel is the renderer's.

import * as W from '../_where.mjs';
import * as C from '../parity/_common.mjs';

export const FILES = Object.freeze({ top: 'top_hillshade', aerial: 'aerial_45deg', eye: 'eye_1p7m' });
export const RIG = Object.freeze({ exposureEv: 0.5, hours: 15.5, clouds: 'cumulus', sensorMm: 36.0, shadowMap: 4096,
    shadowCover: 1.5, water: [0.02, 0.05, 0.07], waterRoughness: 0.15 });
export const PLACES = ['lauterbrunnen', 'mount_fuji', 'grand_canyon_toroweap', 'namib_star_dunes', 'seven_sisters'];

/** The reference renders' folder of the Blender edition (blender/tests/terrain/reference/renders), or null. */
export function referenceRenders() {
    const t = W.blenderTests();
    return t && W.isDir(`${t}/reference/renders`) ? `${t}/reference/renders` : null;
}

/** A views JSON: the reference's (datum 'absolute') or a judged terrain's own (datum 'save'). */
export function loadViews(reference, viewsJson = null) {
    if (viewsJson) return { file: W.absPath(viewsJson), datum: 'save', views: C.readJson(W.absPath(viewsJson)) };
    const dir = referenceRenders();
    const file = dir ? `${dir}/${reference}_views.json` : null;
    const views = file ? C.readJson(file) : null;
    return views ? { file, datum: 'absolute', views } : null;
}

const toThree = ([x, y, z]) => [x, z, -y];

/** What the scene needs for one view (three.js axes, degrees, metres): the camera, its field of view and clip
 * planes, the sun, the ground's datum offset, the shadow box, the curvature. */
export function viewSpec(kind, view, info, plan, datum) {
    const [w, h] = view.resolution;
    const fovH = 2 * Math.atan(RIG.sensorMm / 2 / view.lens_mm);           // the sensor on the wider side (AUTO fit)
    const fovV = w >= h ? 2 * Math.atan(Math.tan(fovH / 2) * h / w) : fovH;
    const main = plan.find((l) => l.role === 'main') ?? plan[plan.length - 1];
    const outer = plan[0];
    const cam = view.camera, tgt = view.target;
    const dist = Math.hypot(cam[0] - tgt[0], cam[1] - tgt[1], cam[2] - tgt[2]);
    const dy = datum === 'absolute' ? Number(info.base_elevation_m ?? 0) - Number(view.z_origin_m) : -Number(view.z_origin_m);
    const spec = { kind, width: w, height: h, fovV: fovV * 180 / Math.PI, camera: toThree(cam), target: toThree(tgt),
        up: kind === 'top' ? [0, 0, -1] : [0, 1, 0], sun: toThree(view.sun_dir), sunElevationDeg: view.sun_elevation_deg,
        dy, hours: view.sky?.hours ?? RIG.hours, clouds: view.sky?.clouds ?? RIG.clouds, exposureEv: RIG.exposureEv,
        shadowMap: RIG.shadowMap, shadowHalf: 0.5 * RIG.shadowCover * main.side, shadowDepth: 4 * main.side,
        water: RIG.water, waterRoughness: RIG.waterRoughness };
    if (kind === 'top') {
        spec.clip = { near: 'top', alt: cam[2] };                              // max(alt - zmax - 50, 1) .. alt + 50
    } else if (kind === 'aerial') {
        spec.clip = { near: dist * 0.02, far: dist * 6 };
    } else {
        spec.clip = { near: 1.0, far: 2.5 * outer.side };
        spec.curvatureR = view.earth_curvature_R_eff_m ?? null;
        spec.eye = [cam[0], -cam[1]];                                          // the camera's ground point, three.js (x, z)
    }
    return spec;
}

/** The scene script of one view (render_scene.mjs evaluates it; the spec is written into it). */
export function sceneScript(spec) {
    return `// A view of the terrain port's judge (eidoverse/terrain/tests/judge/views.mjs writes this file).
globalThis.setup = async function () {
    const V = ${JSON.stringify(spec)};
    const { Fn, positionGeometry, modelWorldMatrix, modelWorldMatrixInverse, vec3, vec4, float } = THREE;
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE,
        reversedDepthBuffer: true });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = Math.pow(2, V.exposureEv);
    renderer.shadowMap.enabled = true;
    await renderer.init();
    globalThis._r = renderer;
    globalThis._noAutoEnhance = true;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(V.fovV, WIDTH / HEIGHT, 1, 10);
    globalThis._s = scene;
    globalThis._c = camera;
    // the ground: the port's ring mesh and water, from the save (api.js Terrain.load)
    const T = await import(EIDOVERSE_DIR + 'terrain/index.js');
    const t = await T.Terrain.load(V.save, { renderer, THREE, log: () => {} });
    const world = new THREE.Group();
    world.add(t.mesh);
    const mainIdx = t.levels.findIndex((l) => l.role === 'main');
    let waters = [...t.water.lakes, t.water.sea].filter(Boolean);
    if (V.kind !== 'eye') {
        // the rig's top and aerial views draw the main tile alone: only the main and hero rings' geometry groups
        // are drawn (P4's mesh as it is, one group a ring and the skirt's last; three draws a grouped geometry group
        // by group), the context levels' lakes stay out, and the sea is the rig's own plane over the tile, 0.1 m
        // above sea level
        const table = t.ring.ringTable(), g = t.mesh.geometry;
        const keep = g.groups.filter((gr, k) => k < table.length && table[k].level >= mainIdx);
        g.clearGroups();
        for (const gr of keep) g.addGroup(gr.start, gr.count, gr.materialIndex);
        waters = t.water.lakes.filter((m) => (m.userData.eidoWater?.level ?? 0) >= mainIdx);
        if (t.water.sea) {
            const lv = t.levels[mainIdx];
            const plane = new THREE.Mesh(new THREE.PlaneGeometry(lv.side, lv.side));
            plane.rotation.x = -Math.PI / 2;
            plane.position.set(lv.x0 + lv.side / 2, Number(t.info.sea_level) + 0.1, -(lv.y0 + lv.side / 2));
            plane.name = 'rig_sea';
            waters.push(plane);
        }
    }
    for (const m of waters) {
        const mat = new THREE.MeshStandardNodeMaterial({ roughness: V.waterRoughness, metalness: 0.0 });
        mat.color.setRGB(V.water[0], V.water[1], V.water[2]);
        m.material = mat;
        m.receiveShadow = true;
        world.add(m);
    }
    world.position.y = V.dy;
    // the clip planes, as the rig sets them
    if (V.clip.near === 'top') {
        // the box build/mesh.js set from the GPU's height range (every ring: an upper bound of the tile's top)
        const zmax = (t.mesh.geometry.boundingBox?.max.y ?? 0) + V.dy;
        camera.near = Math.max(V.clip.alt - zmax - 50.0, 1.0);
        camera.far = V.clip.alt + 50.0;
    } else {
        camera.near = V.clip.near;
        camera.far = V.clip.far;
    }
    camera.updateProjectionMatrix();
    camera.position.set(...V.camera);
    // the sky (sky_worlds.js) and its sun; the fill is the sky's baked environment alone, as the rig's world
    // lighting is (no hemisphere light: the rig has none); the terrain is not in the sky's cloud shadows
    const sun = new THREE.DirectionalLight(0xffffff, 1.0);
    scene.add(sun, sun.target);
    // a forward render with no post stack: the sky's domes must not carry the post stack's G-buffer outputs
    // (sky_system.js noGBuffer: an mrt of only normal and metalrough compiles to a fragment with no output)
    globalThis.EANPA_NO_MRT = true;
    eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
    // weather null: a weather state carries a cloud preset of its own ('clear' empties the sky), the rig has none
    const sky = await makeSky({ scene, camera, renderer, world: 'earth', hours: V.hours, clouds: V.clouds, weather: null,
        sun, audio: false });
    // the sky's domes are spheres of a few km centred under the camera at ground level, made for a camera near the
    // ground; the rig's world surrounds every camera, so the domes are scaled to just inside the far plane (their
    // colour is a function of the view ray alone): the aerial camera, kilometres up, is inside them too
    for (const d of scene.children.filter((o) => o.isMesh && o.renderOrder <= -98 && o.material?.side === THREE.BackSide)) {
        const r0 = d.geometry?.parameters?.radius ?? 3200;
        d.scale.setScalar(0.9 * camera.far / r0);
    }
    sky.update(0);
    // the ground and the camera turned together so the sun falls on them as in the view (the facade has no azimuth)
    const s = sky.sunDir;
    const theta = Math.atan2(V.sun[2], V.sun[0]) - Math.atan2(s.z, s.x);
    const elSky = Math.asin(Math.max(-1, Math.min(1, s.y))) * 180 / Math.PI;
    if (Math.abs(elSky - V.sunElevationDeg) > 0.5) {
        throw new Error('views: the sky\\'s sun stands ' + elSky.toFixed(2) + ' degrees up, the view\\'s ' + V.sunElevationDeg.toFixed(2));
    }
    world.rotation.y = theta;
    world.updateMatrixWorld(true);
    const R = new THREE.Matrix4().makeRotationY(theta);
    const pos = new THREE.Vector3(...V.camera).applyMatrix4(R), tgt = new THREE.Vector3(...V.target).applyMatrix4(R);
    camera.up.copy(new THREE.Vector3(...V.up).applyMatrix4(R));
    camera.position.copy(pos);
    camera.lookAt(tgt);
    camera.updateMatrixWorld(true);
    // the eye view's horizon: every vertex dropped by d^2 / 2R from the camera's ground point (the rig's grids)
    if (V.curvatureR) {
        const e = new THREE.Vector3(V.eye[0], 0, V.eye[1]).applyMatrix4(R);
        const ex = float(e.x), ez = float(e.z), k = float(0.5 / V.curvatureR);
        const curve = Fn(() => {
            const wp = modelWorldMatrix.mul(vec4(positionGeometry, 1.0)).xyz;
            const dx = wp.x.sub(ex), dz = wp.z.sub(ez);
            const drop = dx.mul(dx).add(dz.mul(dz)).mul(k);
            return positionGeometry.sub(modelWorldMatrixInverse.mul(vec4(0.0, drop, 0.0, 0.0)).xyz);
        });
        for (const m of [t.mesh, ...waters]) {
            for (const mat of Array.isArray(m.material) ? m.material : [m.material]) {
                mat.positionNode = curve();
                mat.needsUpdate = true;
            }
        }
    }
    // shadows: one orthographic map over the main tile and its relief
    sun.castShadow = true;
    sun.shadow.mapSize.set(V.shadowMap, V.shadowMap);
    const sc = sun.shadow.camera;
    sc.left = -V.shadowHalf; sc.right = V.shadowHalf; sc.top = V.shadowHalf; sc.bottom = -V.shadowHalf;
    sc.near = -V.shadowDepth; sc.far = V.shadowDepth;
    sc.updateProjectionMatrix();
    sun.shadow.bias = -0.0002;
    sun.shadow.normalBias = 2.0 * (2 * V.shadowHalf / V.shadowMap);
    scene.add(world);
    await sky.bakeEnv();
    globalThis._sky = sky;
    Deno.writeTextFileSync(V.usedJson, JSON.stringify({ kind: V.kind, theta_deg: theta * 180 / Math.PI,
        sky_sun: [s.x, s.y, s.z], sky_sun_elevation_deg: elSky, view_sun: V.sun, camera_world: pos.toArray(),
        target_world: tgt.toArray(), up_world: camera.up.toArray(), near: camera.near, far: camera.far, fov_v_deg: camera.fov,
        dy: V.dy, lakes: t.water.lakes.length, sea: !!t.water.sea, triangles: t.ring.triangleCount ?? null,
        curvature_R: V.curvatureR ?? null }, null, 1));
};
globalThis.renderFrame = async function (t) {
    globalThis._sky.update(t);
    await globalThis._r.renderAsync(globalThis._s, globalThis._c);
};
`;
}

const rel = (p) => {
    const a = W.norm(p), r = W.REPO + '/';
    return a.startsWith(r) ? a.slice(r.length) : a;
};

/** Render the views of one save (see the top). Returns { label, out, views: { kind: { png, ok, seconds } } }. */
export async function renderViews(save, opts = {}) {
    const base = W.absPath(save).replace(/\.(npz|json)$/, '');
    const info = C.readJson(`${base}.json`);
    if (!info) throw new Error(`views: no ${base}.json`);
    const loaded = loadViews(opts.reference, opts.viewsJson);
    if (!loaded) {
        W.skip(`the views of ${opts.reference}`, 'no views JSON: the Blender edition\'s reference/renders (EIDO_BLENDER_EDITION) or --views-json');
        return null;
    }
    const label = opts.label ?? `${opts.reference ?? info.place ?? 'terrain'}_port`;
    const out = W.absPath(opts.out ?? `${W.out('judge')}/views`);
    const work = `${out}/_scenes`;
    Deno.mkdirSync(work, { recursive: true });
    const kinds = (opts.views ?? ['top', 'aerial', 'eye']).filter((k) => loaded.views[k]);
    const used = { save: base, views_json: loaded.file, datum: loaded.datum, label, views: {} };
    const result = { label, out, views: {} };
    for (const kind of kinds) {
        const spec = viewSpec(kind, loaded.views[kind], info, info.plan, loaded.datum);
        spec.save = base;
        spec.usedJson = `${work}/${label}_${kind}_used.json`;
        const script = `${work}/${label}_${kind}.js`, config = `${work}/${label}_${kind}.json`;
        const video = `${work}/${label}_${kind}.mp4`;
        Deno.writeTextFileSync(script, sceneScript(spec));
        Deno.writeTextFileSync(config, JSON.stringify({ width: spec.width, height: spec.height, fps: 30, duration: 1 / 30,
            script: rel(script), outputVideo: rel(video), capture: { at: [0], jump: true } }, null, 1));
        const argv = W.gpuArgv([W.norm(Deno.execPath()), 'run', '--allow-all', '--unstable-webgpu', '--node-modules-dir=auto',
            'eidoverse/render_scene.mjs', rel(config)], { cwd: W.REPO });     // the engine runs from the repository's root
        const t0 = performance.now();
        const code = await W.run(argv, { cwd: W.REPO, log: `${work}/${label}_${kind}.log`,
            env: { ...Deno.env.toObject(), RENDER_CODEC: 'libx264', RENDER_CQ: '0' } });
        const shot = `${work}/${label}_${kind}_at0.00s.png`, png = `${out}/${label}_${FILES[kind]}.png`;
        const ok = code === 0 && W.exists(shot);
        if (ok) Deno.renameSync(shot, png);
        result.views[kind] = { png: ok ? png : null, ok, code, seconds: +((performance.now() - t0) / 1000).toFixed(1), log: `${work}/${label}_${kind}.log` };
        used.views[kind] = { spec, used: C.readJson(spec.usedJson), blender_view: loaded.views[kind] };
        console.log(`[views] ${label} ${kind}: ${ok ? png : `FAILED (exit ${code}): see ${work}/${label}_${kind}.log`} (${result.views[kind].seconds} s)`);
    }
    Deno.writeTextFileSync(`${out}/${label}_views.json`, JSON.stringify(used, null, 1));
    return result;
}

/** The Blender edition's real_place save of each place (see the top): [{ place, save, ok }]. */
export async function bakePlaces(dir, places = PLACES) {
    const edition = W.needBlenderEdition('the places\' saves');
    if (!edition) return [];
    dir = W.absPath(dir);
    Deno.mkdirSync(dir, { recursive: true });
    const out = [];
    for (const p of places) {
        const argv = W.blenderCmd(`${W.blenderTerrain()}/bake.py`, '--recipe', 'real_place', '--param', `dem=${p}`, '--quality', 'film',
            '--no-cache', '--save', '--name', p, '--out', dir);
        const code = await W.run(argv, { cwd: edition, log: `${dir}/${p}_bake.log`,
            env: { ...Deno.env.toObject(), HEAVY_VRAM_GB: Deno.env.get('HEAVY_VRAM_GB') ?? '4', GPU_MEMCAP_GB: Deno.env.get('GPU_MEMCAP_GB') ?? '12' } });
        const ok = code === 0 && W.exists(`${dir}/${p}.npz`);
        out.push({ place: p, save: `${dir}/${p}`, ok, code });
        console.log(`[views] bake ${p}: ${ok ? `${dir}/${p}.npz` : `FAILED (exit ${code}): see ${dir}/${p}_bake.log`}`);
    }
    return out;
}

if (import.meta.main) {
    const args = [...Deno.args];
    const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args.splice(i, 2)[1] : null; };
    const bake = opt('--bake'), places = opt('--places')?.split(',').filter(Boolean) ?? null, saves = opt('--saves');
    const reference = opt('--reference'), views = opt('--views')?.split(',') ?? null, viewsJson = opt('--views-json');
    const label = opt('--label'), out = opt('--out');
    if (bake) {
        const r = await bakePlaces(bake, places ?? PLACES);
        Deno.exit(r.length && r.every((x) => x.ok) ? 0 : 1);
    }
    if (saves) {
        let ok = true;
        for (const p of places ?? PLACES) {
            const r = await renderViews(`${W.absPath(saves)}/${p}`, { reference: p, views, out, label: `${p}_port` });
            ok = ok && !!r && Object.values(r.views).every((v) => v.ok);
        }
        Deno.exit(ok ? 0 : 1);
    }
    if (!args.length || !(reference || viewsJson)) {
        console.log('usage: views.mjs <save> --reference <name> [--views top,aerial,eye] [--views-json <json>] [--label L] [--out <dir>]\n' +
            '       views.mjs --bake <dir> [--places a,b]\n       views.mjs --places a,b --saves <dir> [--out <dir>]');
        Deno.exit(2);
    }
    const r = await renderViews(args[0], { reference, views, viewsJson, label, out });
    Deno.exit(r && Object.values(r.views).every((v) => v.ok) ? 0 : 1);
}
