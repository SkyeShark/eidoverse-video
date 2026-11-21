// surface/layers.js, the data textures (PORT_PLAN.md 3.5; 10.3: "sampling a DataArrayTexture layer with .depth(level)
// in TSL in a headless Deno render"), on a bake case: Blender's stored bake of it and Blender's palette bake
// (tests/surface_data/blender_bakes.py's fixture folder), so every family is there.
//   1. the data region of every level's tile in every family equals the stored maps as the family encodes them: the
//      E and M bytes the bake stored, the D and F halves (F less its level's reference), C and P the sRGB bytes of
//      the stored linear values (atlas.py's _linear_to_srgb, in doubles here), within one step;
//   2. the gutter equals SurfaceData._gutter's search (the finest level below holding each texel centre, bilinear
//      there, clamped to its outermost centres; level 0 edge-extended), evaluated here per texel in doubles on every
//      third gutter texel, within one step (a byte, or two half steps);
//   3. a headless three.js WebGPURenderer samples each family's layers with TSL texture(tex, uv).depth(layer) at the
//      texel centres of the tile (a full-screen quad into a float render target, one readback): the RGBA8 families
//      read back as their bytes / 255 (C and P sRGB-decoded by the GPU), the RGBA16F ones as their halves.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surface_data/layers_test.mjs
//         [--case toroweap]
//     (on a shared machine, behind $EIDO_GPU_WRAP; $EIDO_BLENDER_EDITION: the Blender edition, for the snapshot)
//
// Writes tests/out/surface_data/layers_test.json. JavaScript per texel here is test code.

import { setupRenderer } from '../../../render_common.mjs';
import * as SI from '../../surface/index.js';
import * as B from '../../surface/bake.js';
import * as MP from '../../surface/maps.js';
import * as G from '../../core/gpu.js';
import * as S from './_surface.mjs';

const A = S.argsOf();
const T = new S.C.Checks('surface_data: the data textures (layers.js)');
const name = A.opt('--case', 'toroweap');
const edition = S.W.needBlenderEdition('the bake case\'s snapshot');
const root = S.fixtureRoot();
const recFile = root ? `${root}/bakes/palette_bake.json` : null;
const rec = recFile && S.W.exists(recFile) ? JSON.parse(Deno.readTextFileSync(recFile)).cases[name] : null;
const snap = edition ? `${S.W.blenderTests()}/out/surface_data/snap/${name}.npz` : null;
if (!rec || rec.error || !snap || !S.W.exists(snap)) {
    T.ok(`${name}: Blender's bake, palette bake and snapshot present`, false, 'make them: tests/surface_data/blender_bakes.py');
    Deno.exit(S.finish(T, 'layers_test'));
}

const RS = await setupRenderer(64, 64);
globalThis.GPU_DEVICE = RS.device;                         // the runner and the renderer on one device
const R = await G.init();
const THREE = RS.THREE;
const TSL = await import('three/tsl');
const dir = `${root}/bakes/${name}`;
const { Terrain } = await import('../../api.js');
const t = await Terrain.load(snap, { build: false, log: null });
const [baked, info] = await SI.loadCached(dir, rec.key, t.levels.length);
const pal = await B.resolvePalette(t, rec.palette);
const { NpzFile } = await import('../../api.js');
const colour = [];
for (let i = 0; i < t.levels.length; i++) {
    const z = await NpzFile.open(`${dir}/surface_${rec.key}_${rec.tag}_L${i}.npz`);
    colour.push(new Map(z.names.map((k) => [k, z.read(k)])));
}
const sd = new SI.SurfaceData(t, baked, { ...info, cache_hit: true }, info.options, rec.key, pal, colour, null);
sd._palettes = await B.palettesModule();
const t0 = performance.now();
const tex = await sd.textures(null, { THREE, R });
const seconds = (performance.now() - t0) / 1000;
const fams = Object.keys(tex);
T.ok(`textures of every family the bake holds (${fams.join(', ')}), one layer per level`,
    fams.length >= 6 && fams.every((f) => tex[f].image.depth === t.levels.length),
    `${seconds.toFixed(2)} s; ` + fams.map((f) => `${f} ${tex[f].image.width}^2 x ${tex[f].image.depth} ${tex[f].type === THREE.HalfFloatType ? '16F' : '8'}`).join(', '));

// ---- the oracle: a family's channel values at a level's texels, physical, from the maps (doubles)
const half2num = (h) => {
    const s = h >> 15 ? -1 : 1, e = (h >> 10) & 31, m = h & 1023;
    return e === 0 ? s * m * 2 ** -24 : e === 31 ? (m ? NaN : s * Infinity) : s * (1 + m / 1024) * 2 ** (e - 15);
};
const srgb = (c) => {
    const x = Math.min(Math.max(c, 0), 1);
    return x <= 0.0031308 ? x * 12.92 : 1.055 * x ** (1 / 2.4) - 0.055;
};
const mapsOf = [];
for (let i = 0; i < t.levels.length; i++) mapsOf.push(await sd.maps(i));
function chanSource(fam, c) {
    if (fam === 'C' || fam === 'P') {
        const key = fam === 'C' ? 'far_colour' : 'down_colour', alpha = fam === 'C' ? 'far_roughness' : 'down_share';
        return c < 3 ? [key, c] : [alpha, null];
    }
    const nm = sd.familyMaps(fam)[c];
    if (nm === null) return [null, null];
    return [fam === 'F' ? (nm === 'src_strata' ? 'src_dz' : 'strata_dz') : nm, null];
}
// a map of level k as [values (Float64Array, its own grid), m texels] or null
function arr(k, src, ch) {
    const m = mapsOf[k];
    let a = m[src];
    if (src === 'strata_dz' && !a && m.strata) {
        const h = t.fields(k).h;
        a = Float32Array.from(m.strata, (v, q) => Math.fround(v - h[q]));
    }
    if (!a) return null;
    if (ch !== null) {
        const n = a.shape3[0];
        const out = new Float64Array(n * n);
        for (let q = 0; q < n * n; q++) out[q] = a[3 * q + ch];
        return [out, n];
    }
    return [a, Math.round(Math.sqrt(a.length))];
}
function bilinear([a, m], lv, x, y) {
    const texel = Number(lv.side) / m;
    const fi = Math.min(Math.max((x - Number(lv.x0)) / texel - 0.5, 0), m - 1), fj = Math.min(Math.max((y - Number(lv.y0)) / texel - 0.5, 0), m - 1);
    const i0 = Math.min(Math.floor(fi), Math.max(m - 2, 0)), j0 = Math.min(Math.floor(fj), Math.max(m - 2, 0));
    const ti = Math.fround(fi - i0), tj = Math.fround(fj - j0), i1 = Math.min(i0 + 1, m - 1), j1 = Math.min(j0 + 1, m - 1);
    const top = a[j0 * m + i0] * (1 - ti) + a[j0 * m + i1] * ti, bot = a[j1 * m + i0] * (1 - ti) + a[j1 * m + i1] * ti;
    return top * (1 - tj) + bot * tj;
}
function encode(fam, c, i, v) {
    if (fam === 'C' || fam === 'P') return c < 3 ? srgb(v) : v;
    const nm = sd.familyMaps(fam)[c];
    if (fam === 'F') return v - (sd.refs[nm]?.[i] ?? 0);
    const s = MP.spec(nm);
    return s.encoding === 'float' ? v : MP.encode1(s, v, Number(sd.levels[i].cell));
}

// ---- 1 and 2: the layers' data region and gutter against the oracle
const report = {};
let worstData = 0, worstGut = 0, whereData = '', whereGut = '';
for (const fam of fams) {
    const L = tex[fam];
    const Sz = L.image.width, half = L.type === THREE.HalfFloatType;
    const data = L.image.data;
    const lay = sd.layouts[fam];
    const step = half ? null : 1 / 255;
    report[fam] = [];
    for (const tile of lay.tiles) {
        const i = tile.level, g = tile.gutter, n = tile.n, size = tile.size;
        const base = i * Sz * Sz * 4;
        let dmax = 0, gmax = 0;
        for (let c = 0; c < 4; c++) {
            const [src, ch] = chanSource(fam, c);
            if (src === null) continue;
            const own = arr(i, src, ch);
            const got = (x, y) => (half ? half2num(data[base + (y * Sz + x) * 4 + c]) : data[base + (y * Sz + x) * 4 + c] / 255);
            const tol = (v) => (half ? Math.max(2 * 2 ** (Math.floor(Math.log2(Math.max(Math.abs(v), 6.1e-5))) - 10), 1e-4) : 1.0001 / 255);
            // the data region: the level's own map resampled to n texels (the tests' cases sit on equal or x2 grids)
            if (own && own[1] === n) {
                for (let y = 0; y < n; y += 1) {
                    for (let x = 0; x < n; x += 1) {
                        const want = encode(fam, c, i, own[0][y * n + x]);
                        const w8 = half ? want : Math.min(Math.max(Math.round(want * 255), 0), 255) / 255;
                        const d = Math.abs(got(g + x, g + y) - w8);
                        if (d > tol(want) && d > dmax) dmax = d;
                    }
                }
            }
            // the gutter, every third texel: _gutter's finest-first search over the levels below
            const src0 = i === 0 ? [0] : Array.from({ length: i }, (_x, k) => i - 1 - k);
            const arrays = src0.map((k) => arr(k, src, ch));
            for (let y = 0; y < size; y += 3) {
                for (let x = 0; x < size; x += 3) {
                    if (x >= g && x < g + n && y >= g && y < g + n) continue;
                    const wx = tile.x0 + (x - g + 0.5) * tile.texel, wy = tile.y0 + (y - g + 0.5) * tile.texel;
                    let v = null;
                    for (let q = 0; q < src0.length; q++) {
                        const k = src0[q], lv = sd.levels[k];
                        if (!arrays[q]) { v = SI.NEUTRAL[src] ?? 0.0; break; }
                        const inside = k === 0 || (wx >= lv.x0 && wx <= lv.x0 + lv.side && wy >= lv.y0 && wy <= lv.y0 + lv.side);
                        if (inside) { v = bilinear(arrays[q], lv, wx, wy); break; }
                    }
                    const want = encode(fam, c, i, v);
                    const w8 = half ? want : Math.min(Math.max(Math.round(want * 255), 0), 255) / 255;
                    const d = Math.abs(got(x, y) - w8);
                    if (d > tol(want) && d > gmax) gmax = d;
                }
            }
            void step;
        }
        report[fam].push({ level: i, data_past_one_step: dmax, gutter_past_one_step: gmax });
        if (dmax > worstData) { worstData = dmax; whereData = `${fam} L${i}`; }
        if (gmax > worstGut) { worstGut = gmax; whereGut = `${fam} L${i}`; }
    }
}
T.ok('every tile\'s data region equals the stored maps as its family encodes them, within one step', worstData === 0,
    worstData ? `worst ${S.sci(worstData, 2)} past one step at ${whereData}` : 'every texel within one step');
T.ok('every tile\'s gutter equals _gutter\'s search over the coarser levels, within one step (every third texel)', worstGut === 0,
    worstGut ? `worst ${S.sci(worstGut, 2)} past one step at ${whereGut}` : 'every texel checked within one step');

// ---- 3: TSL .depth(layer) in a headless render, at the tile's texel centres
const renderer = new THREE.WebGPURenderer({ canvas: RS.canvas, adapter: RS.adapter, device: RS.device, antialias: false });
await renderer.init();
const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 2);
cam.position.set(0, 0, 1);
const renders = [];
let worstR = 0, whereR = '';
for (const fam of fams) {
    const L = tex[fam];
    const Sz = L.image.width, half = L.type === THREE.HalfFloatType, srgbFam = L.colorSpace === THREE.SRGBColorSpace;
    for (const i of [0, t.levels.length - 1]) {
        const tile = sd.layouts[fam].tiles[i];
        const size = tile.size;
        // a quad whose pixels are the tile's texels: uv = (x + 0.5) / S on the layer
        const geo = new THREE.PlaneGeometry(2, 2);
        const uvs = geo.attributes.uv;
        for (let k = 0; k < uvs.count; k++) uvs.setXY(k, uvs.getX(k) * size / Sz, uvs.getY(k) * size / Sz);
        const mat = new THREE.MeshBasicNodeMaterial();
        mat.colorNode = TSL.texture(L, TSL.uv()).depth(TSL.int(i));
        mat.toneMapped = false;
        const scene = new THREE.Scene();
        scene.add(new THREE.Mesh(geo, mat));
        const rt = new THREE.RenderTarget(size, size, { type: THREE.FloatType, depthBuffer: false });
        renderer.setRenderTarget(rt);
        renderer.render(scene, cam);
        const px = await renderer.readRenderTargetPixelsAsync(rt, 0, 0, size, size);
        renderer.setRenderTarget(null);
        let mx = 0;
        const base = i * Sz * Sz * 4;
        for (let y = 0; y < size; y++) {
            const row = size - 1 - y;                    // the render target's row 0 is the quad's top (v = 1)
            for (let x = 0; x < size; x++) {
                for (let c = 0; c < 4; c++) {
                    const raw = L.image.data[base + (y * Sz + x) * 4 + c];
                    let want = half ? half2num(raw) : raw / 255;
                    if (srgbFam && c < 3) want = want <= 0.04045 ? want / 12.92 : ((want + 0.055) / 1.055) ** 2.4;
                    const d = Math.abs(px[(row * size + x) * 4 + c] - want) / Math.max(1, Math.abs(want));
                    if (d > mx) mx = d;
                }
            }
        }
        renders.push({ family: fam, level: i, size, worst: mx });
        if (mx > worstR) { worstR = mx; whereR = `${fam} L${i}`; }
        rt.dispose();
        geo.dispose();
        mat.dispose();
    }
}
T.ok('TSL texture(tex, uv).depth(layer) in a headless WebGPURenderer reads every family\'s layers as their data (RGBA8 bytes, ' +
    'sRGB decoded, halves) at the texel centres, within 1e-3', worstR <= 1e-3, `worst ${S.sci(worstR, 2)}${whereR ? ' (' + whereR + ')' : ''}; ` +
    `${renders.length} renders`);
renderer.dispose();
for (const x of Object.values(tex)) x.dispose();
G.shutdown();
Deno.exit(S.finish(T, 'layers_test', { case: name, seconds: +seconds.toFixed(2), families: report, renders }));
