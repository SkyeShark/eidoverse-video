// Port of blender/eidoblend/terrain/build/dressing.py at f9fba8c (the terrain design's dressing; SURFACING_DESIGN.md
// 4.6 for the toe bias; PORT_PLAN.md 3.5 row dressing.js, 8.2 row P15).
//
// Rocks and boulders on the terrain: CC0 rock models (Poly Haven, fetch_model.py <id> --cache --res 1k) scattered where
// fallen rock gathers (the palette's dressing spec: a density over the masks), one InstancedMesh per model, so tens of
// thousands of stones cost one mesh each in memory.
//
//     import * as D from './build/dressing.js';
//     const rocks = await D.scatterRocks(pal.dressing, { terrain: t, data: sd, focus: [x, y], seed: 7, renderer });
//     world.add(rocks.group);            // in the terrain's frame: three.js (x, z, -y) of Blender's (x, y, z)
//     rocks.count, rocks.sizes, rocks.seconds
//
// How a rock is placed (dressing.py's rules, on the GPU: kernels/plants/rock_cand, rock_place):
//   - density: the spec's mask expression (the palettes' language, compiled as the plants' densities are) gives the
//     rocks per m^2 at least size_m[0] across, everywhere in the disc of radius_m round the focus; the candidates are a
//     Poisson count at the density's maximum over the disc (a 96 x 96 probe grid, x 1.25), uniform in the disc, kept
//     with probability density / maximum, none over water above 0.05, none in an excluded disc;
//   - size: the power law N(>s) ~ s^-alpha between size_m[0] and size_m[1]; with toe_bias > 0 and the surface bake's
//     grain map, the smallest size s0 (1 + toe_bias grain) (the toe's blocks); kept while at least lod_m_per_m x its
//     distance from the focus; at most max_rocks (a random subset);
//   - each stands on the rendered ground (the ring mesh's height_at and normal_at), `bury` of its height under it,
//     its up axis turned `align` of the way from world up to the normal, a random turn about it and a few degrees of
//     random tilt, its proportions jittered (squash);
//   - models: each glTF mesh centred on its bounding box and measured, `size` its longest horizontal side; a model
//     entry (id, min, max) stands only for rocks of those sizes; with `colour`, each model's albedo is rescaled from its
//     own mean to that colour (target x (1 + 0.55 (scan / mean - 1))) and its roughness held at 0.6 or more.
//
// Where this differs from dressing.py, and why (each a forced deviation; the rocks' distribution is Blender's):
//   - The random numbers: dressing.py draws them in turn from numpy's generator (seeded by the terrain's seed), a
//     sequence no parallel pass can reproduce (its normal draws take a variable number of steps); here each
//     candidate's numbers are hashes of (the scatter's key, its index) (PORT_PLAN.md 3.5: "a hash per candidate"),
//     the candidates' count an exact Poisson draw from one such hash; the max_rocks subset the rocks of the smallest
//     hashed keys (numpy's choice without replacement). The same distributions, other stones.
//   - The probe grid's points outside the disc read the focus' density (numpy leaves them out; the maximum is the
//     same unless the density peaks at the focus itself, which the 1.25 margin covers).
//   - The normal tilt: Box-Muller from two hashed uniforms (numpy's ziggurat).
//   - Models are read by three.js' GLTFLoader (the scene's, which hands Deno's decoded textures to WebGPU) and
//     instanced per model; their materials become NodeMaterials with the recolour and the matte in their nodes.

import * as PL from './plants.js';
import * as P from './palettes.js';
import { prims, lineGroups } from '../core/prims.js';

export const DEFAULT_SPEC = Object.freeze({
    models: ['boulder_01', 'rock_07', 'rock_09'], colour: null, density: '0.0', size_m: [0.12, 2.5], alpha: 2.4, bury: 0.35,
    align: 0.6, tilt_deg: 8.0, squash: [0.7, 1.05], radius_m: 150.0, lod_m_per_m: 0.01, max_rocks: 400000, model_res: '1k',
    toe_bias: 0.0,
});
export const SOURCE_COLLECTION = 'eido_rock_models';
const RECOLOUR_CONTRAST = 0.55, ROUGH_MIN = 0.6;

let THREE = null, T = null;
async function three(opts = {}) {
    if (!THREE || (opts.THREE && opts.THREE !== THREE)) {
        THREE = opts.THREE ?? globalThis.THREE ?? await import('three/webgpu');
        T = opts.TSL ?? THREE.TSL ?? await import('three/tsl');
    }
    return THREE;
}

const fsPath = (u) => decodeURIComponent(u.pathname).replace(/^\/([A-Za-z]:)/, '$1');
const exists = (p) => {
    try { Deno.statSync(p); return true; } catch (_e) { return false; }
};

// ------------------------------------------------------------------------------------------- the models ---

/** Where cached models are looked for (dressing.py model_roots): this checkout's eidoverse/assets/cache/models,
 * $EIDO_ASSET_CACHE/models, then the main checkout's when this one is a git worktree. */
export function modelRoots() {
    const repo = fsPath(new URL('../../../', import.meta.url)).replace(/\/$/, '');
    const roots = [`${repo}/eidoverse/assets/cache/models`];
    try {
        const env = Deno.env.get('EIDO_ASSET_CACHE');
        if (env) roots.push(`${env.replace(/\\/g, '/')}/models`);
    } catch (_e) { /* no env access */ }
    try {
        const g = Deno.readTextFileSync(`${repo}/.git`).trim();           // a worktree's .git is a file: gitdir: <main>/.git/worktrees/<name>
        const m = /^gitdir:\s*(.+)$/m.exec(g);
        if (m) {
            const main = m[1].replace(/\\/g, '/').replace(/\/\.git\/worktrees\/[^/]+\/?$/, '');
            roots.push(`${main}/eidoverse/assets/cache/models`);
        }
    } catch (_e) { /* a plain checkout */ }
    return roots.filter((r) => exists(r));
}

/** The cached glTF of a Poly Haven model id, or an error naming how to fetch it (dressing.py find_model). */
export function findModel(id, res = '1k') {
    for (const r of modelRoots()) {
        const dirs = [`${r}/${id}_${res}`];
        try {
            for (const e of [...Deno.readDirSync(r)].map((x) => x.name).sort()) if (e.startsWith(`${id}_`)) dirs.push(`${r}/${e}`);
        } catch (_e) { /* unreadable */ }
        for (const d of dirs) {
            if (!exists(d)) continue;
            const hit = [...Deno.readDirSync(d)].map((x) => x.name).filter((n) => n.endsWith('.gltf') || n.endsWith('.glb')).sort();
            if (hit.length) return `${d}/${hit[0]}`;
        }
    }
    throw new Error(`[dressing] rock model ${JSON.stringify(id)} is not in ${JSON.stringify(modelRoots())}: ` +
        `python fetch_model.py ${id} --cache --res ${res}`);
}

/** [[id, min_size_m, max_size_m]] from a spec's models: ids, or [id, min, max] (dressing.py model_entries). */
export function modelEntries(models) {
    return models.map((m) => (typeof m === 'string' ? [m, 0.0, Infinity]
        : [String(m[0]), Number(m[1]), m.length > 2 ? Number(m[2]) : Infinity]));
}

// the mean linear colour of a texture's pixels (dressing.py _image_mean_linear), on the GPU; null without pixel data
async function meanLinear(tex, R) {
    const img = tex?.image;
    const data = img?.data;
    if (!data || !img.width || !img.height || data.length < img.width * img.height * 4) return null;
    const n = img.width * img.height;
    const P = prims(R);
    const u8 = data instanceof Uint8Array || data instanceof Uint8ClampedArray ? data : null;
    if (!u8) return null;
    const px = P.list(n, 'u32', new Uint32Array(u8.buffer.slice(u8.byteOffset, u8.byteOffset + 4 * n)));
    const out = [];
    for (let c = 0; c < 3; c++) {
        const l = P.list(n, 'f32');
        R.run(R.kernel('plants/albedo_linear'), { px }, { outL: l }, { uChannel: c, uCount: n }, lineGroups(n));
        out.push((await P.stats(l, { count: n })).mean);
        l.destroy();
    }
    px.destroy();
    return out;
}

// a model material as a NodeMaterial: its albedo rescaled from its mean to the target (dressing.py _recolour), its
// roughness held at ROUGH_MIN or more (_matte)
async function rockMaterial(src, target, R) {
    const m = new THREE.MeshStandardNodeMaterial();
    for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'side']) if (src[k] !== undefined) m[k] = src[k];
    if (src.normalScale) m.normalScale = src.normalScale.clone();
    m.roughness = src.roughness ?? 1.0;
    m.metalness = src.metalness ?? 0.0;
    m.color = src.color?.clone() ?? new THREE.Color(1, 1, 1);
    if (target) {
        const t = target.map((v) => Math.min(Math.max(v, 0.0), 0.95));
        const mean = src.map ? await meanLinear(src.map, R) : null;
        if (!src.map) m.color = new THREE.Color().setRGB(t[0], t[1], t[2]);
        else if (mean) {
            const c = RECOLOUR_CONTRAST;
            const inv = T.vec3(...mean.map((v) => 1.0 / Math.max(v, 1e-4)));
            m.colorNode = T.texture(src.map).rgb.mul(inv).mul(c).add(1.0 - c).mul(T.vec3(t[0], t[1], t[2]));
        }
    }
    const rough = src.roughnessMap ? T.texture(src.roughnessMap).g.mul(m.roughness) : T.float(m.roughness);
    m.roughnessNode = T.max(rough, ROUGH_MIN);
    m.name = `${src.name || 'rock'}_eido`;
    return m;
}

const MODELS = new Map();

/** The rock models (dressing.py load_models): per model id and colour once, each mesh baked to the model's frame and
 * centred on its bounding box: [{ id, sizes: [min, max], geometry, material, dims (Blender axes: dx, dy, dz) }]. */
export async function loadModels(models, colour = null, res = '1k', { R, log = console.log } = {}) {
    await three();
    const entries = modelEntries(models);
    const target = colour ? P.hexLinear(colour) : null;
    const out = [];
    const t0 = performance.now();
    // the scene's loader (render_scene.mjs: it hands Deno's decoded textures to WebGPU), else three's own (the
    // version deno.json pins; the import map's three/addons/ prefix does not resolve a subpath under Deno)
    const Loader = globalThis.GLTFLoader ?? (await import('npm:three@0.184.0/addons/loaders/GLTFLoader.js')).GLTFLoader;
    for (const [id, lo, hi] of entries) {
        const key = `${id}|${res}|${colour ?? 'scan'}`;
        if (!MODELS.has(key)) {
            const path = findModel(id, res);
            const base = path.slice(0, path.lastIndexOf('/') + 1);
            const bytes = await Deno.readFile(path);
            const body = path.endsWith('.glb') ? bytes.buffer : new TextDecoder().decode(bytes);
            const gltf = await new Promise((ok, bad) => new Loader().parse(body, base, ok, bad));
            gltf.scene.updateMatrixWorld(true);
            const parts = [];
            const meshes = [];
            gltf.scene.traverse((o) => { if (o.isMesh) meshes.push(o); });
            for (const o of meshes) {
                const g = o.geometry.clone();
                g.applyMatrix4(o.matrixWorld);
                g.computeBoundingBox();
                const c = g.boundingBox.getCenter(new THREE.Vector3());
                g.translate(-c.x, -c.y, -c.z);
                const s = g.boundingBox.getSize(new THREE.Vector3());
                const mats = Array.isArray(o.material) ? o.material : [o.material];
                const mm = [];
                for (const mt of mats) mm.push(await rockMaterial(mt, target, R));
                // Blender's glTF import turns the model y-up into z-up: its dims (x, z, y) of three.js'
                parts.push({ geometry: g, material: Array.isArray(o.material) ? mm : mm[0], dims: [s.x, s.z, s.y] });
            }
            MODELS.set(key, parts);
        }
        for (const p of MODELS.get(key)) out.push({ id, sizes: [lo, hi], ...p });
    }
    if (log) log(`[dressing] ${out.length} rock meshes from ${entries.length} models (${colour ?? 'scan'}) in ` +
        `${((performance.now() - t0) / 1000).toFixed(1)} s`);
    return out;
}

// ------------------------------------------------------------------------------------------- placement ---

// an exact Poisson draw by inversion from a hashed 53-bit uniform (the planner's tables); the normal approximation
// past a mean of 10^7 (a table that long is not worth building for a count)
function poissonCount(mean, h) {
    if (!(mean > 0)) return 0;
    const u = Number(PL.u53(h, 99)) / 9007199254740992.0;
    if (mean > 1e7) {
        const v = Number(PL.u53(h, 98)) / 9007199254740992.0;
        return Math.max(0, Math.round(mean + Math.sqrt(mean) * Math.sqrt(-2 * Math.log(Math.max(u, 1e-300))) * Math.cos(2 * Math.PI * v)));
    }
    const th = PL.poissonThresholds(mean);
    const k53 = Number(PL.u53(h, 99));
    let lo = 0, hi = th.length - 1;                          // the first k with u < cdf_k (searchsorted, side right)
    while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (k53 < th[mid]) hi = mid; else lo = mid + 1;
    }
    return lo;
}

const i32 = (b) => Number(BigInt.asIntN(32, b));

/** The rock instances (dressing.py place_rocks), on the GPU: { matrices (Float32Array, 16 a rock, three.js' frame,
 * the rocks of each model together), counts (per model), sizes [min, max], n }. models: loadModels' entries (their
 * dims and size ranges). */
export async function placeRocks(spec, { terrain, data = null, focus = [0, 0], radiusM = null, seed = 0, models, exclude = null,
    R } = {}) {
    const sp = { ...DEFAULT_SPEC, ...(spec ?? {}) };
    const Rd = Number(radiusM ?? sp.radius_m);
    const fx = Number(focus[0]), fy = Number(focus[1]);
    const Pm = prims(R);
    const uF = [...PL.splitCoord(fx), ...PL.splitCoord(fy)];
    const h = PL.hashChain(PL.key64(Math.trunc(Number(seed))), PL.nameKey('eidoverse rocks'), PL.key64(Math.round(fx * 1000)),
        PL.key64(Math.round(fy * 1000)));
    const uKey = [i32(BigInt.asUintN(64, h) >> 32n), i32(BigInt.asUintN(64, h) & 0xFFFFFFFFn)];
    const empty = { matrices: new Float32Array(0), counts: models.map(() => 0), sizes: [0, 0], n: 0 };
    // the density's maximum over the disc
    const probe = Pm.list(96 * 96 * 16, 'u32');
    R.run(R.kernel('plants/rock_cand'), {}, { outC: probe }, { uF, uR: [Rd, 0, 0, 0], uKey, uMode: 1, uCount: 96 * 96 }, lineGroups(96 * 96));
    const pd = await PL.maskExpression(terrain, sp.density, probe, 96 * 96, { R, data });
    let dmax = (await Pm.stats(pd.values, { count: 96 * 96 })).max;
    for (const f of [probe, pd.values, pd.water].filter(Boolean)) f.destroy();
    if (!(dmax > 0.0)) return empty;
    dmax *= 1.25;
    const n = Math.min(poissonCount(Math.PI * Rd * Rd * dmax, h), 40 * Number(sp.max_rocks));
    if (!n) return empty;
    const cand = Pm.list(n * 16, 'u32');
    R.run(R.kernel('plants/rock_cand'), {}, { outC: cand }, { uF, uR: [Rd, 0, 0, 0], uKey, uMode: 0, uCount: n }, lineGroups(n));
    const dens = await PL.maskExpression(terrain, sp.density, cand, n, { R, data });
    const toe = Number(sp.toe_bias ?? 0.0);
    const grain = toe > 0.0 ? await PL.maskExpression(terrain, 'grain', cand, n, { R, data }) : null;
    const hasGrain = !!grain && grain.present.includes('grain');
    const ground = PL.groundAt(terrain, cand, n, R);
    const discs = (exclude ?? []).map((d) => [Number(d[0]), Number(d[1]), Number(d[2])]);
    const tab = new Float32Array(Math.max(3 * discs.length + 5 * models.length, 1));
    discs.forEach((d, k) => tab.set(d, 3 * k));
    models.forEach((m, k) => tab.set([...m.dims, Number.isFinite(m.sizes[0]) ? m.sizes[0] : -1,
        Number.isFinite(m.sizes[1]) ? m.sizes[1] : -1], 3 * discs.length + 5 * k));
    const tabL = Pm.list(tab.length, 'f32', tab);
    const dummy = Pm.list(1, 'f32');
    const res = Pm.list(20 * n, 'f32');
    const s0 = Number(sp.size_m[0]), s1 = Number(sp.size_m[1]);
    R.run(R.kernel('plants/rock_place'), { cand, dens: dens.values, water: dens.water ?? dummy, grain: hasGrain ? grain.values : dummy,
        zs: ground.z, nrm: ground.normal, tab: tabL }, { outR: res }, {
        uF, uA: [dmax, s0, s1, Number(sp.alpha)], uB: [toe, Number(sp.lod_m_per_m), Number(sp.align), Number(sp.tilt_deg) * Math.PI / 180],
        uC: [Number(sp.bury), Number(sp.squash[0]), Number(sp.squash[1]), 0], uN: [discs.length, models.length, dens.water ? 1 : 0, hasGrain ? 1 : 0],
        uCount: n }, lineGroups(n));
    for (const f of [cand, dens.values, dens.water, grain?.values, grain?.water, ground.z, ground.normal, tabL].filter(Boolean)) f.destroy();
    // the kept ones, at most max_rocks (the smallest keys), then grouped by model
    const flags = Pm.list(n, 'u32'), dumF = Pm.list(1, 'f32'), dumU = Pm.list(1, 'u32');
    R.run(R.kernel('plants/rock_column'), { src: res }, { outU: flags, outF: dumF }, { uCol: 0, uMode: 0, uCount: n }, lineGroups(n));
    const nz = await Pm.nonzero(flags, { count: n });
    flags.destroy();
    let index = nz.index, m = nz.n;
    if (!m) {
        for (const f of [res, index, dumF, dumU, dummy]) f.destroy();
        return empty;
    }
    if (m > Number(sp.max_rocks)) {
        const keysAll = Pm.list(n, 'f32');
        R.run(R.kernel('plants/rock_column'), { src: res }, { outU: dumU, outF: keysAll }, { uCol: 1, uMode: 1, uCount: n }, lineGroups(n));
        const kk = Pm.gather(keysAll, index, { count: m });
        const fk = Pm.floatKeys(kk, { count: m });
        const sorted = Pm.sortPairs(fk, index, { count: m });
        for (const f of [keysAll, kk, fk, sorted.keys, index]) f.destroy();
        index = sorted.vals;
        m = Number(sp.max_rocks);
    }
    const mats = Pm.list(16 * m, 'f32'), picks = Pm.list(m, 'u32'), sizes = Pm.list(m, 'f32');
    R.run(R.kernel('plants/rock_gather'), { src: res, index }, { outM: mats, outK: picks, outS: sizes }, { uCount: m }, lineGroups(m));
    const byModel = Pm.sortPairs(picks, index, { count: m, bits: Math.max(1, Math.ceil(Math.log2(models.length + 1))) });
    const mats2 = Pm.list(16 * m, 'f32'), picks2 = Pm.list(m, 'u32'), sizes2 = Pm.list(m, 'f32');
    R.run(R.kernel('plants/rock_gather'), { src: res, index: byModel.vals }, { outM: mats2, outK: picks2, outS: sizes2 }, { uCount: m },
        lineGroups(m));
    const counts = Pm.bincount(picks, Math.max(models.length, 1), { count: m });
    const st = await Pm.stats(sizes, { count: m });
    const [M, C] = await R.readAll([mats2, counts]);
    for (const f of [res, index, mats, picks, sizes, byModel.keys, byModel.vals, mats2, picks2, sizes2, counts, dumF, dumU, dummy]) f.destroy();
    return { matrices: new Float32Array(M.buffer, M.byteOffset, 16 * m), counts: Array.from(C.subarray(0, models.length)),
        sizes: [st.min, st.max], n: m };
}

// ------------------------------------------------------------------------------------------- the call ---

/** Scatter a palette's rocks (its 'dressing' spec, DEFAULT_SPEC filled in) round a focus (dressing.py scatter_rocks).
 *
 *   spec       the palette's dressing spec
 *   opts       terrain (with its ring mesh), data (its SurfaceData: the toe bias' grain), focus [x, y] (Blender frame),
 *              radiusM, seed, exclude [[x, y, r]] (flats, paths), name, renderer / R (the GPU), log
 *   returns    { group (one InstancedMesh per model mesh, the terrain's frame), count, sizes [min, max], seconds } */
export async function scatterRocks(spec = null, opts = {}) {
    await three(opts);
    const t0 = performance.now();
    const sp = { ...DEFAULT_SPEC, ...(spec ?? {}) };
    const log = opts.log === undefined ? console.log : opts.log;
    let R = opts.R;
    if (!R) {
        const G = await import('../core/gpu.js');
        R = await G.init(opts.renderer ? { renderer: opts.renderer } : {});
    }
    const models = await loadModels(sp.models, sp.colour ?? null, sp.model_res ?? '1k', { R, log });
    if (!models.length) throw new Error(`[dressing] no meshes in the rock models ${JSON.stringify(sp.models)}`);
    const res = await placeRocks(sp, { terrain: opts.terrain, data: opts.data ?? null, focus: opts.focus ?? [0, 0],
        radiusM: opts.radiusM ?? null, seed: opts.seed ?? 0, models, exclude: opts.exclude ?? null, R });
    const group = new THREE.Group();
    group.name = opts.name ?? 'terrain_rocks';
    let first = 0;
    models.forEach((mdl, k) => {
        const c = res.counts[k] ?? 0;
        if (!c) return;
        const mesh = new THREE.InstancedMesh(mdl.geometry, mdl.material, 1);
        mesh.instanceMatrix = new THREE.InstancedBufferAttribute(res.matrices.subarray(16 * first, 16 * (first + c)), 16);
        mesh.count = c;
        mesh.frustumCulled = false;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.name = `${group.name}_${mdl.id}_${k}`;
        mesh.userData.eidoRocks = { model: mdl.id, count: c };
        group.add(mesh);
        first += c;
    });
    group.userData.eidoRocks = { count: res.n, models: modelEntries(sp.models).map((e) => e[0]), colour: sp.colour ?? 'scan',
        focus: [Number(opts.focus?.[0] ?? 0), Number(opts.focus?.[1] ?? 0)], seed: Math.trunc(Number(opts.seed ?? 0)) };
    const seconds = (performance.now() - t0) / 1000;
    if (log) {
        log(`[dressing] ${res.n} rocks (${res.sizes[0].toFixed(2)}-${res.sizes[1].toFixed(2)} m) within ` +
            `${Number(opts.radiusM ?? sp.radius_m).toFixed(0)} m of (${Number(opts.focus?.[0] ?? 0).toFixed(0)}, ` +
            `${Number(opts.focus?.[1] ?? 0).toFixed(0)}) in ${seconds.toFixed(1)} s`);
    }
    return { group, count: res.n, sizes: res.sizes, seconds, models };
}

export { scatterRocks as scatter_rocks, placeRocks as place_rocks, loadModels as load_models, findModel as find_model,
    modelRoots as model_roots };
