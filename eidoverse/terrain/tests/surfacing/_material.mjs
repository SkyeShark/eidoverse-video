// What the material package's tests share (PORT_PLAN.md 8.2 row P17): a bake case's terrain with its ring mesh, the
// port's surface data of it, a headless renderer on the runner's device, and the render and readback helpers. Paths
// come from tests/_where.mjs (through the surface data package's tests/surface_data/_surface.mjs, used as it is).
//
//     import * as M from './_material.mjs';
//     const G = await M.gpu();                              // { THREE, TSL, renderer, R, device }
//     const { t, sd } = await M.caseData('canyon', G, { palette: true });
//     const px = await M.renderTop(G, t.mesh, material, { cx, cy, side, n, top });   // Float32Array rows, n x n x 4
//     const T = new M.C.Checks('surfacing: ...');  ...  Deno.exit(M.finish(T, 'reader_test'));
//
// The cases are the surface data package's (surface_data/_surface.mjs CASES): Blender's snapshots of them
// ($EIDO_BLENDER_EDITION's blender/tests/terrain/out/surface_data/snap/<case>.npz), their bake options from Blender's
// bake record, baked here by the port into tests/out/surfacing/bakes/<case> (cached). The packed scans are read from
// $EIDO_SURFACE_SETS when it is set, else this package's own packs, tests/out/surfacing/sets (pack_test.mjs makes
// them from the CC0 library). JavaScript per pixel here is test code.

import * as S from '../surface_data/_surface.mjs';

export { S };
export const C = S.C;
export const W = S.W;

/** tests/out/surfacing/<sub>: made on first use. */
export function out(sub = '') {
    const d = `${W.out('surfacing')}${sub ? '/' + sub : ''}`;
    Deno.mkdirSync(d, { recursive: true });
    return d;
}

/** Point $EIDO_SURFACE_SETS at the packed scans the tests read (its own value when set, else tests/out/surfacing/sets). */
export function useSets() {
    if (!Deno.env.get('EIDO_SURFACE_SETS')) Deno.env.set('EIDO_SURFACE_SETS', out('sets'));
    return Deno.env.get('EIDO_SURFACE_SETS');
}

let GPU = null;

/** The renderer and the terrain runner on one device (the scene's arrangement: GPU_DEVICE). */
export async function gpu(width = 64, height = 64) {
    if (GPU) return GPU;
    const { setupRenderer } = await import('../../../render_common.mjs');
    const RS = await setupRenderer(width, height);
    globalThis.GPU_DEVICE = RS.device;
    const G = await import('../../core/gpu.js');
    const R = await G.init();
    const THREE = RS.THREE;
    const TSL = await import('three/tsl');
    const renderer = new THREE.WebGPURenderer({ canvas: RS.canvas, adapter: RS.adapter, device: RS.device, antialias: false });
    await renderer.init();
    GPU = { THREE, TSL, renderer, R, device: RS.device, G, RS };
    return GPU;
}

/** A bake case's Terrain (Blender's snapshot, its ring mesh built: t.mesh) and the port's SurfaceData of it, baked
 * with Blender's recorded bake options; with palette, its palette bake too ('auto', provenance always). { t, sd } or
 * null (a line says why). */
export async function caseData(name, G, { palette = false, log = null } = {}) {
    const snap = W.blenderEdition() ? `${W.blenderTests()}/out/surface_data/snap/${name}.npz` : null;
    const bb = S.blenderBake(name);
    if (!snap || !W.exists(snap) || !bb) {
        console.log(`[skip] ${name}: no snapshot or Blender bake (EIDO_BLENDER_EDITION; tests/surface_data/blender_bakes.py)`);
        return null;
    }
    useSets();
    const SI = await import('../../surface/index.js');
    const B = await import('../../surface/bake.js');
    const { Terrain } = await import('../../api.js');
    const t = await Terrain.load(snap, { build: true, renderer: G.renderer, THREE: G.THREE, log: () => {} });
    const dir = out(`bakes/${name}`);
    const sd = await SI.bakeSurface(t, { palette: null, options: { ...bb.info.options }, cache: dir, log });
    if (palette) {
        let p = 'auto';
        if (t.info?.palette && t.info.palette !== 'auto') p = t.info.palette;
        const pal = await B.resolvePalette(t, p);
        sd.palette = pal;
        sd._palettes = await B.palettesModule();
        await sd.bakePalette(pal, { cache: dir, log, provenance: true });
    }
    return { t, sd };
}

/** Render `object` top-down, orthographic, centred on Blender (cx, cy), `side` metres across in n x n pixels (one
 * texel a pixel when side = n texel), from `top` metres up, into a half-float target (render_common.mjs gives this
 * device's float targets half precision): { px (Float32Array, n rows of n RGBA, row 0 north), n }. */
export async function renderTop(G, object, { cx, cy, side, n, top }) {
    const { THREE, renderer } = G;
    const scene = new THREE.Scene();
    const parent = object.parent;
    scene.add(object);
    const h = side / 2;
    const cam = new THREE.OrthographicCamera(-h, h, h, -h, 1.0, 20000.0);
    cam.position.set(cx, top, -cy);
    cam.up.set(0, 0, -1);
    cam.lookAt(cx, 0, -cy);
    cam.updateMatrixWorld(true);
    const rt = new THREE.RenderTarget(n, n, { type: THREE.HalfFloatType, depthBuffer: true });
    renderer.setRenderTarget(rt);
    renderer.setClearColor(0x000000, 0);
    renderer.render(scene, cam);
    const raw = await renderer.readRenderTargetPixelsAsync(rt, 0, 0, n, n);
    renderer.setRenderTarget(null);
    rt.dispose();
    if (parent) parent.add(object);
    else scene.remove(object);
    const row = raw.length / n;
    const px = new Float32Array(n * n * 4);
    for (let j = 0; j < n; j++) {
        for (let i = 0; i < n * 4; i++) px[j * n * 4 + i] = THREE.DataUtils.fromHalfFloat(raw[j * row + i]);
    }
    return { px, n };
}

/** Render `object` from Blender eye (x, y, z) at Blender target (x, y, z), a lens of `lens` mm on a 36 mm sensor
 * fitted horizontally, w x h pixels, one sample, into a half-float target cleared to alpha 0: { px (Float32Array,
 * row 0 the top), w, h }. */
export async function renderPersp(G, object, { eye, target, lens = 35.0, w = 960, h = 540, near = null, far = null }) {
    const { THREE, renderer } = G;
    const scene = new THREE.Scene();
    const parent = object.parent;
    scene.add(object);
    const fovV = 2 * Math.atan(18.0 * (h / w) / lens) * 180 / Math.PI;
    const dist = Math.hypot(target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]);
    const cam = new THREE.PerspectiveCamera(fovV, w / h, near ?? Math.max(0.1, 0.002 * dist), far ?? 200000.0);
    cam.position.set(eye[0], eye[2], -eye[1]);
    cam.up.set(0, 1, 0);
    cam.lookAt(target[0], target[2], -target[1]);
    cam.updateMatrixWorld(true);
    const rt = new THREE.RenderTarget(w, h, { type: THREE.HalfFloatType, depthBuffer: true });
    renderer.setRenderTarget(rt);
    renderer.setClearColor(0x000000, 0);
    renderer.render(scene, cam);
    const raw = await renderer.readRenderTargetPixelsAsync(rt, 0, 0, w, h);
    renderer.setRenderTarget(null);
    rt.dispose();
    if (parent) parent.add(object);
    else scene.remove(object);
    const row = raw.length / h;
    const px = new Float32Array(w * h * 4);
    // the readback's row 0 is the image's top (WebGPU's texture origin; renderTop's north, the reader test's check)
    for (let j = 0; j < h; j++) for (let i = 0; i < w * 4; i++) px[j * w * 4 + i] = THREE.DataUtils.fromHalfFloat(raw[j * row + i]);
    return { px, w, h };
}

/** The p-th percentile of numbers (numpy's linear rule). */
export function percentile(vals, p) {
    const a = Float64Array.from(vals).sort();
    if (!a.length) return NaN;
    const x = (p / 100) * (a.length - 1);
    const lo = Math.floor(x), hi = Math.ceil(x);
    return a[lo] + (a[hi] - a[lo]) * (x - lo);
}

/** Write a test's result to tests/out/surfacing/<name>.json and return its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length, failed: failed.map((r) => r.check),
        ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${out()}/${name}.json`, JSON.stringify(res, null, 1));
    return code;
}

export const argsOf = S.argsOf;
