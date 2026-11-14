// Port of blender/eidoblend/terrain/recipes/real_place.py at f90c6fc.
//
// real_place: real elevation data as the main tile (design section 5), refined below its pixel by the detail stages
// on the hero levels. Its test is that the hero levels add detail without moving the landform.
//
//     const t = await makeTerrain({ recipe: 'real_place', params: { dem: 'lauterbrunnen' }, focus: [480, -1640] });
//     const t = await makeTerrain({ recipe: 'real_place', params: { dem: '<dir>/my_place.json' } });   // a DEM of your own
//
// The DEM. A name is one of the references: a 16-bit PNG and a JSON with the grid (a north-up square, pixel_size_m,
// centred on the place), the height range, the source and its licence. The references are not in this repository:
// they are looked for in the folders of the EIDO_TERRAIN_DEMS environment variable (separated by the platform's
// path separator), then in the Blender edition's blender/tests/terrain/reference/data (blender/ beside eidoverse/ in
// a merged checkout, else under $EIDO_BLENDER_EDITION). A path names such a JSON (or its PNG) and always works; a
// .npy of metres (row 0 north) needs pixel_m. Its _context files, where they exist, are the wider surround.
//
// Levels. By default the main tile is the DEM: its extent and pixel count are the size and resolution
// (Lauterbrunnen: 8000 m at 1000 cells of 8 m), so the main level holds the DEM's own pixels. Context levels (as
// many as the surround covers: context 4 for Lauterbrunnen's 32 km, 2 for Fuji's 120 km around 40) come from the
// surround harmonised to the main DEM: inside the DEM's extent a level is the main DEM averaged to its cell;
// outside, the surround plus the main-minus-surround difference along the DEM's edge, carried outward by a push-pull
// fill (long wavelengths travel far, detail fades within a few cells) and faded to nothing over blend_m. So the
// rings meet without a step where the two datasets disagree (resolution, vertical datum). The bed is the surface: a
// DEM does not tell rock from debris, so the inherited ground counts as rock and only what the detail stages add is
// loose. The hero levels start from their parent upsampled (Catmull-Rom) and then get the detail stages: fluvial
// refinement (mode 'refine'), talus, rock breakup and hydraulic rills; the level runner skips a stage whose op is
// not registered yet.
//
// Drainage. The masks read the drainage area A; the level runner routes it to convergence on every level after its
// stages, the parent's catchment entering each child at its edge.
//
// Heights. y (Blender z) is metres above the main DEM's lowest point (base 'min'), or above sea level (base 'sea',
// the default when the place has sea); base_elevation_m is the datum height of y = 0. Water: a DEM carries a lake as
// its flat surface. Under each lake the ground is lowered into a bowl (lake_depth_m at its deepest, reached
// lake_depth_m / 0.15 metres from the shore), the `water` field holds the depth, and the lake meshes sit at the
// lake's level. The sea's floor drops the same way below sea level.
//
// Where this differs from real_place.py, and why (PORT_PLAN.md 2.4, 3.2):
//   - The op runs on the GPU: the resampling (per-axis tap tables made in doubles as _axis_weights makes its weight
//     matrices, applied by a kernel), the push-pull pyramid, the fade, the water codes, the shore distance (the same
//     chamfer relaxation, the same number of sweeps) and the bowls. The kernels are written in this file, as
//     Blender writes some of its own inline: a recipe module is hashed into the terrain's cache key, so an edit to
//     them invalidates cached terrains (PORT_PLAN.md C8).
//   - Heights are float32 where numpy's are float64 rounded once. A DEM's samples are kept as integers and turned
//     into metres ABOVE THE BASE through a table computed in doubles, float32((lo + v scale) - base): so a level that
//     holds the DEM's own pixels is Blender's float32 field to the bit, and the sums of the other levels run on
//     numbers a few thousand metres smaller. (Resampling is linear with weights that sum to 1, so subtracting the
//     base before it is the same ground.)
//   - push_pull's early return when every weight is 1 is left out: the recursion then gives v back exactly.
//   - np.any(mask) of a water body is not asked (a readback): a body with no cell on a level changes nothing.
//   - The DEM is loaded once per GPU runner and kept on the GPU (Blender: once per process, in numpy); the op and the
//     hooks are async (file reading and readbacks are): run.js awaits an op. clearCache() releases them (the chaos
//     floor's protocol clears this memo between samples, PORT_PLAN.md 5.4).
//   - A bare .npy's lowest point (base 'min') is read from its float32 copy on the GPU: float64 data loses half a
//     float32 step there.
//   - The place's palette, mask parameters and strata (build/palettes.js PLACES) come with the surfacing wave: until
//     that module is in the checkout defaultsFor leaves them out, as real_place.py does when palettes fails to import.

import * as Gd from '../core/grid.js';
import * as Io from '../core/io.js';
import { KeyError, ValueError, closeMatches, pyReprValue } from '../core/levels.js';
import { prims } from '../core/prims.js';
import { Knob, Recipe, Stage } from '../core/recipe.js';

export const LAKE_SLOPE = 0.15;                         // the lake bowl's side: depth rises 0.15 m per metre from the shore
const REPO = new URL('../../../', import.meta.url);
const CACHE = new WeakMap();                            // runner -> Map('<dem>|<pixel_m>' -> Dem)
const IS_WIN = Deno.build.os === 'windows';


// ------------------------------------------------------------------------------------------------ the data ---

const urlPath = (u) => decodeURIComponent(new URL(u).pathname).replace(/^\/([A-Za-z]:)/, '$1').replace(/\/+$/, '');
const norm = (p) => String(p).replace(/\\/g, '/');
const dirOf = (p) => { const q = norm(p), k = q.lastIndexOf('/'); return k < 0 ? '.' : q.slice(0, k) || '/'; };
const baseOf = (p) => norm(p).split('/').pop();
const stemOf = (p) => { const b = baseOf(p), k = b.lastIndexOf('.'); return k > 0 ? b.slice(0, k) : b; };
const noExt = (p) => { const q = norm(p), k = q.lastIndexOf('.'); return k > q.lastIndexOf('/') + 1 ? q.slice(0, k) : q; };

function stat(p) {
    try {
        return Deno.statSync(p);
    } catch (_e) {
        return null;
    }
}
const isFile = (p) => stat(p)?.isFile === true;
const isDir = (p) => stat(p)?.isDirectory === true;

/** The Blender edition's reference data folder (blender/ in this checkout, else under $EIDO_BLENDER_EDITION), or
 * null when there is none. */
export function blenderReferenceData() {
    for (const root of [urlPath(REPO), Deno.env.get('EIDO_BLENDER_EDITION') ?? '']) {
        if (!root) continue;
        const d = `${norm(root).replace(/\/+$/, '')}/blender/tests/terrain/reference/data`;
        if (isDir(d)) return d;
    }
    return null;
}

/** The folders a reference DEM is looked for in: $EIDO_TERRAIN_DEMS's, then the Blender edition's reference data. */
export function demDirs() {
    const extra = (Deno.env.get('EIDO_TERRAIN_DEMS') ?? '').split(IS_WIN ? ';' : ':').filter(Boolean).map(norm);
    const b = blenderReferenceData();
    return [...extra, ...(b ? [b] : [])];
}

/** The reference DEMs on this machine. */
export function demNames() {
    const out = new Set();
    for (const d of demDirs()) {
        if (!isDir(d)) continue;
        for (const e of Deno.readDirSync(d)) {
            if (e.isFile && e.name.endsWith('.json') && !e.name.endsWith('_context.json')) out.add(e.name.slice(0, -5));
        }
    }
    return [...out].sort();
}

// where the references are looked for, for an error: the two places and how to fill them
function whereText() {
    const env = Deno.env.get('EIDO_TERRAIN_DEMS');
    const b = blenderReferenceData();
    const there = b ?? ('no Blender edition here: blender/ is not beside eidoverse/ and $EIDO_BLENDER_EDITION does not name a ' +
        'checkout of the blender branch');
    return 'A reference name is looked for in the folders of $EIDO_TERRAIN_DEMS (' + (env ? env : 'not set') + ') and in the ' +
        "Blender edition's blender/tests/terrain/reference/data (" + there + '); the references are fetched there with ' +
        "<Blender's python> -I blender/tests/terrain/reference/fetch_references.py --downloads <an empty folder>. The path of a " +
        'reference-style DEM (its .json, or its 16-bit .png with the .json beside it) always works';
}

/** The JSON path of a DEM name or path (real_place.py _find). */
export function find(dem) {
    const s = String(dem);
    if (isFile(s)) {
        if (s.toLowerCase().endsWith('.png')) {
            const js = noExt(s) + '.json';
            if (isFile(js)) return js;
        }
        return norm(s);
    }
    for (const d of demDirs()) {
        const p = `${d}/${s}.json`;
        if (isFile(p)) return p;
    }
    const names = demNames();
    const near = closeMatches(s, names, 3, 0.4);
    throw new KeyError(`no DEM ${pyReprValue(dem)}` + (near.length ? `; nearest: ${near.join(', ')}` :
        `; the references here: ${names.join(', ') || '(none)'}`) + `. ${whereText()}`);
}

const K_MASK = `
// real_place.py _read_json_dem: a water-mask PNG's first channel with its rows flipped to row 0 south
// (read_png(...)[..., 0][::-1]). Exact.
//! sampler src r32ui     the PNG's samples, h rows of w x channels, row 0 top
//! image   outM r32ui    h x w, row 0 south
//! uniform int uChannels

fn kmain(p: vec2<i32>) {
  let n = outM_size();
  if (!inside(p, n)) { return; }
  let w = src_size().x;
  outM_b[p.y * n.x + p.x] = src_b[(n.y - 1 - p.y) * w + p.x * u.uChannels];
}
`;

// a reference-style DEM's files: { meta, samples (u32 field, row 0 top), lo, scale, water (u32 field, row 0 south, or null) }
async function readJsonDem(R, path) {
    const meta = JSON.parse(await Deno.readTextFile(path));
    const img = await Io.readPng(R, `${dirOf(path)}/${meta.height_png}`);
    if (img.bitDepth !== 16 || img.channels !== 1) {
        img.field.destroy();
        throw new ValueError(`${path}: the height PNG must be 16-bit greyscale`);
    }
    const lo = Number(meta.height_min_m), hi = Number(meta.height_max_m);
    let water = null;
    if (meta.water_mask_png) {
        const w = await Io.readPng(R, `${dirOf(path)}/${meta.water_mask_png}`);
        water = R.field(w.height, w.width, 1, null, 'u32');
        R.run(R.kernel('real_place_mask', K_MASK), { src: w.field }, { outM: water }, { uChannels: w.channels });
        w.field.destroy();
    }
    return { meta, samples: img.field, rows: img.height, cols: img.width, lo, scale: (hi - lo) / 65535.0, water };
}

/** A DEM loaded once per runner: its samples and grid, the surround, the water. Heights are made per base
 * (heights(base)): metres above it, row 0 south, float32 of numpy's float64 value. */
export class Dem {
    constructor(o) {
        Object.assign(this, o);
        this._heights = new Map();
    }

    /** The datum height of y = 0: the main DEM's lowest point ('min'), sea level ('sea'), or a number. */
    base(mode) {
        if (mode === 'auto') mode = this.sea.length ? 'sea' : 'min';
        if (mode === 'min') return this.hMin;
        if (mode === 'sea') return 0.0;
        return Number(mode);
    }

    // a source's heights above `base` as a float32 field, row 0 south
    _field(R, src, base) {
        if (src.samples) {
            // numpy: h = lo + v.astype(float64) * ((hi - lo) / 65535.0); then h - base, rounded once to float32
            const table = new Float32Array(65536);
            for (let v = 0; v < 65536; v++) table[v] = (src.lo + v * src.scale) - base;
            return Io.dequantise(src.samples, table, { flip: true });
        }
        return Gd.arith(R, 'affine', src.metres, null, { amp: 1.0, off: -base });
    }

    /** { h, ctx } GPU fields of the main DEM and of its surround (or null), metres above `base`. Kept. */
    heights(R, base) {
        let e = this._heights.get(base);
        if (!e) {
            e = { h: this._field(R, this.main, base), ctx: this.ctx ? this._field(R, this.ctx, base) : null };
            this._heights.set(base, e);
        }
        return e;
    }

    dispose() {
        for (const e of this._heights.values()) {
            e.h.destroy();
            e.ctx?.destroy();
        }
        this._heights.clear();
        for (const s of [this.main, this.ctx]) {
            s?.samples?.destroy();
            s?.metres?.destroy();
        }
        this.waterMask?.destroy();
    }
}

async function makeDem(R, dem, pixelM) {
    const path = find(dem);
    const P = prims(R);
    let main, meta, waterMask = null, hMin;
    if (path.toLowerCase().endsWith('.npy')) {
        if (!pixelM) throw new ValueError(`real_place: ${path} is a bare array: give its pixel_m`);
        const a = Io.readNpySync(path);
        if (a.shape.length !== 2) throw new ValueError(`real_place: ${path} holds a ${a.shape.length}-d array; a 2-d grid of metres is needed`);
        const top = R.field(a.shape[0], a.shape[1], 1, a.data instanceof Float32Array ? a.data : new Float32Array(a.data));
        const metres = Gd.fromNorthUp(top);
        top.destroy();
        main = { metres, rows: a.shape[0], cols: a.shape[1] };
        meta = { name: stemOf(path), pixel_size_m: Number(pixelM), rows: a.shape[0], cols: a.shape[1], landform: '', title: path, water: [] };
        hMin = (await P.stats(metres)).min;
    } else {
        const d = await readJsonDem(R, path);
        main = d;
        meta = d.meta;
        waterMask = d.water;
        // float(self.h.min()): the lowest sample's height, in numpy's float64 arithmetic
        hMin = d.lo + (await P.statsU32(d.samples)).min * d.scale;
    }
    const name = meta.name || stemOf(path);
    if (main.rows !== main.cols) throw new ValueError(`real_place: ${name} is ${main.cols} x ${main.rows}; the levels are square`);
    const pixel = Number(meta.pixel_size_m);
    const n = main.rows, side = n * pixel;
    let ctx = null;
    const cpath = noExt(path) + '_context.json';
    if (isFile(cpath)) {
        const c = await readJsonDem(R, cpath);
        c.water?.destroy();
        const pc = Number(c.meta.pixel_size_m);
        ctx = { ...c, pixel: pc, c0: -c.cols * pc / 2.0, n: c.rows };
    }
    const water = meta.water || [];
    return new Dem({ path, meta, name, pixel, n, side, x0: -side / 2.0, y0: -side / 2.0,     // the reference grid: centred on the place
        main, ctx, waterMask, water, sea: water.filter((w) => w.kind === 'sea'), hMin });
}

/** The Dem of a name or path, loaded once per runner. */
export async function load(R, dem, pixelM = 0.0) {
    let m = CACHE.get(R);
    if (!m) CACHE.set(R, m = new Map());
    const key = `${String(dem)}|${Number(pixelM || 0.0)}`;
    if (!m.has(key)) m.set(key, makeDem(R, dem, pixelM));
    try {
        return await m.get(key);
    } catch (e) {
        m.delete(key);
        throw e;
    }
}

/** Forget (and release) the DEMs loaded on a runner. */
export async function clearCache(R) {
    const m = CACHE.get(R);
    if (!m) return;
    for (const p of m.values()) {
        try {
            (await p).dispose();
        } catch (_e) { /* it never loaded */ }
    }
    m.clear();
}


// --------------------------------------------------------------------------------------------- resampling ---

/** The taps taking a source axis (pixels from src0, srcCell wide) to an output axis (real_place.py _axis_weights,
 * its rows as lists): the exact area-weighted average where the output cell is at least the source pixel,
 * Catmull-Rom at the output centres where it is finer; edges clamp. { first (Int32Array nOut + 1), idx, wt }: output
 * k reads taps first[k] .. first[k + 1]. Weights in doubles, as numpy's, rounded to float32 at the end. */
export function axisTaps(out0, outCell, nOut, src0, srcCell, nSrc) {
    const first = new Int32Array(nOut + 1);
    const idx = [], wt = [];
    const clampI = (i) => Math.min(Math.max(i, 0), nSrc - 1);
    for (let k = 0; k < nOut; k++) {
        first[k] = idx.length;
        const row = new Map();                           // source index -> weight (np.add.at / += accumulate)
        const add = (i, w) => row.set(i, (row.get(i) ?? 0) + w);
        if (outCell >= srcCell * (1 - 1e-9)) {
            const lo = (out0 + k * outCell - src0) / srcCell;     // output cell k covers source [lo, hi)
            const hi = lo + outCell / srcCell;
            for (let i = Math.floor(lo); i < Math.ceil(hi); i++) {
                const ov = Math.min(hi, i + 1) - Math.max(lo, i);
                if (ov > 0) add(clampI(i), ov);
            }
            let sum = 0;
            for (const i of [...row.keys()].sort((a, b) => a - b)) sum += row.get(i);
            for (const i of row.keys()) row.set(i, row.get(i) / sum);
        } else {
            const t = (out0 + (k + 0.5) * outCell - src0) / srcCell - 0.5;     // fractional source index of the centre
            const i = Math.floor(t), f = t - i;
            const w = [((-0.5 * f + 1.0) * f - 0.5) * f, (1.5 * f - 2.5) * f * f + 1.0, ((-1.5 * f + 2.0) * f + 0.5) * f,
                (0.5 * f - 0.5) * f * f];
            [-1, 0, 1, 2].forEach((o, q) => add(clampI(i + o), w[q]));
        }
        for (const i of [...row.keys()].sort((a, b) => a - b)) {
            idx.push(i);
            wt.push(row.get(i));
        }
    }
    first[nOut] = idx.length;
    return { first, idx: Int32Array.from(idx), wt: Float32Array.from(wt) };
}

const K_RESAMPLE = `
// real_place.py resample along one axis: out[k] = the sum over output k's taps of weight x source (the rows of
// _axis_weights' matrix, as a list). float32 sums where numpy's matrix product is float64.
//! sampler src r32f
//! sampler first r32i     n_out + 1 entries: each output's first tap
//! sampler idx r32i       the taps' source indices
//! sampler wt r32f        the taps' weights
//! image   outF r32f
//! uniform int uAxis      0 along the rows (numpy's axis 0), 1 along the columns

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let ns = src_size();
  var k = p.y;
  if (u.uAxis == 1) { k = p.x; }
  var s = 0.0;
  for (var t = first_b[k]; t < first_b[k + 1]; t++) {
    var v: f32;
    if (u.uAxis == 0) { v = src_b[idx_b[t] * ns.x + p.x]; } else { v = src_b[p.y * ns.x + idx_b[t]]; }
    s += wt_b[t] * v;
  }
  outF_b[p.y * n.x + p.x] = s;
}
`;

/** A square source grid (a GPU field, row 0 south, corner (src0, src0)) on a level's n x n cell grid: box-averaged to
 * coarser cells, Catmull-Rom to finer ones (real_place.py resample: Wy @ src @ Wx.T, the rows first). A new field. */
export function resample(R, src, src0, srcCell, x0, y0, cell, n) {
    const P = prims(R);
    const k = R.kernel('real_place_resample', K_RESAMPLE);
    const ty = axisTaps(y0, cell, n, src0, srcCell, src.h), tx = axisTaps(x0, cell, n, src0, srcCell, src.w);
    const up = (t) => [P.list(t.first.length, 'i32', t.first), P.list(Math.max(t.idx.length, 1), 'i32', t.idx),
        P.list(Math.max(t.wt.length, 1), 'f32', t.wt)];
    const fy = up(ty), fx = up(tx);
    const mid = R.field(n, src.w, 1), out = R.field(n, n, 1);
    R.run(k, { src, first: fy[0], idx: fy[1], wt: fy[2] }, { outF: mid }, { uAxis: 0 });
    R.run(k, { src: mid, first: fx[0], idx: fx[1], wt: fx[2] }, { outF: out }, { uAxis: 1 });
    for (const f of [...fy, ...fx, mid]) f.destroy();
    return out;
}

const K_PP_DOWN = `
// real_place.py push_pull, down a level: the weighted 2 x 2 sums (cells past an odd edge count nothing),
// vc = vs / ws where ws > 0 else 0, and the weight min(ws, 1).
//! sampler v r32f
//! sampler w r32f
//! image   outV r32f
//! image   outW r32f

fn kmain(p: vec2<i32>) {
  let n = outV_size();
  if (!inside(p, n)) { return; }
  let nf = v_size();
  var vs = 0.0;
  var ws = 0.0;
  for (var dj = 0; dj < 2; dj++) {
    for (var di = 0; di < 2; di++) {
      let q = 2 * p + vec2<i32>(di, dj);
      if (inside(q, nf)) {
        let ww = w_b[q.y * nf.x + q.x];
        vs += v_b[q.y * nf.x + q.x] * ww;
        ws += ww;
      }
    }
  }
  var vc = 0.0;
  if (ws > 0.0) { vc = vs / ws; }
  outV_b[p.y * n.x + p.x] = vc;
  outW_b[p.y * n.x + p.x] = min(ws, 1.0);
}
`;

const K_PP_BASE = `
// real_place.py push_pull, its coarsest level (two rows or two columns at most): the cells with data keep it, the
// others take the weighted mean (0 with no data at all).
//! sampler v r32f
//! sampler w r32f
//! image   outF r32f

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var tot = 0.0;
  var s = 0.0;
  for (var q = 0; q < n.x * n.y; q++) {
    tot += w_b[q];
    s += v_b[q] * w_b[q];
  }
  var mean = 0.0;
  if (tot > 0.0) { mean = s / tot; }
  let c = p.y * n.x + p.x;
  var o = mean;
  if (w_b[c] > 0.0) { o = v_b[c]; }
  outF_b[c] = o;
}
`;

const K_PP_UP = `
// real_place.py push_pull, back up a level: the coarser level's fill doubled bilinearly at the cell centres (rows
// first, then columns, the edge repeated) and laid under the data: v w + up (1 - w).
//! sampler fc r32f       the coarser level, filled
//! sampler v r32f
//! sampler w r32f
//! image   outF r32f

fn cf(i: i32, j: i32) -> f32 {
  let n = fc_size();
  return fc_b[clamp(j, 0, n.y - 1) * n.x + clamp(i, 0, n.x - 1)];
}

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  // an even fine row is 0.25 of the coarse row before and 0.75 of its own; an odd one 0.75 of its own, 0.25 of the next
  var j0 = p.y / 2 - 1;
  var j1 = p.y / 2;
  var a0 = 0.25;
  var a1 = 0.75;
  if ((p.y & 1) == 1) { j0 = p.y / 2; j1 = p.y / 2 + 1; a0 = 0.75; a1 = 0.25; }
  var i0 = p.x / 2 - 1;
  var i1 = p.x / 2;
  var b0 = 0.25;
  var b1 = 0.75;
  if ((p.x & 1) == 1) { i0 = p.x / 2; i1 = p.x / 2 + 1; b0 = 0.75; b1 = 0.25; }
  let r0 = a0 * cf(i0, j0) + a1 * cf(i0, j1);
  let r1 = a0 * cf(i1, j0) + a1 * cf(i1, j1);
  let up = b0 * r0 + b1 * r1;
  let c = p.y * n.x + p.x;
  let ww = w_b[c];
  outF_b[c] = v_b[c] * ww + up * (1.0 - ww);
}
`;

/** Fill the cells where w is 0 from those where it is 1, smoothly (real_place.py push_pull): a pyramid of weighted
 * 2 x 2 averages, then back down, each level filling its holes from the one above (bilinear). Long wavelengths
 * reach far, short ones fade within a few cells of the data. v and w are GPU fields (w in [0, 1]); a new field. */
export function pushPull(R, v, w) {
    const ny = v.h, nx = v.w;
    const out = R.field(ny, nx, 1);
    if (ny <= 2 || nx <= 2) {
        R.run(R.kernel('real_place_pp_base', K_PP_BASE), { v, w }, { outF: out }, {});
        return out;
    }
    const cy = (ny + (ny % 2)) / 2, cx = (nx + (nx % 2)) / 2;
    const vc = R.field(cy, cx, 1), wc = R.field(cy, cx, 1);
    R.run(R.kernel('real_place_pp_down', K_PP_DOWN), { v, w }, { outV: vc, outW: wc }, {});
    const fc = pushPull(R, vc, wc);
    R.run(R.kernel('real_place_pp_up', K_PP_UP), { fc, v, w }, { outF: out }, {});
    for (const f of [vc, wc, fc]) f.destroy();
    return out;
}

const K_GROUND = `
// real_place.py ground: mode 0, the residual the push-pull carries outward and its weight,
// where(inside, hm - hc, 0) and inside; mode 1, the level's ground, where(inside, hm, hc + resid fade), with
// fade = 1 - smoothstep(0, max(blend_m, cell), the distance outside the DEM's extent).
//! sampler hm r32f       the main DEM on the level's grid
//! sampler hc r32f       the surround on the level's grid
//! sampler resid r32f    mode 1: the filled residual
//! sampler axes r32f     4 n numbers: inside along x (1 / 0), inside along y, the distance outside along x, along y
//! image   outA r32f     mode 0: the residual; mode 1: the ground
//! image   outB r32f     mode 0: the weight
//! uniform int uMode
//! uniform float uBlend  max(blend_m, cell)

fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  let c = p.y * n.x + p.x;
  let inn = axes_b[p.x] > 0.5 && axes_b[n.x + p.y] > 0.5;
  if (u.uMode == 0) {
    var v = 0.0;
    var w = 0.0;
    if (inn) { v = hm_b[c] - hc_b[c]; w = 1.0; }
    outA_b[c] = v;
    outB_b[c] = w;
    return;
  }
  var h = hm_b[c];
  if (!inn) {
    let dx = axes_b[2 * n.x + p.x];
    let dy = axes_b[3 * n.x + p.y];
    let t = clamp(sqrt(dy * dy + dx * dx) / u.uBlend, 0.0, 1.0);
    let fade = 1.0 - t * t * (3.0 - 2.0 * t);
    h = hc_b[c] + resid_b[c] * fade;
  }
  outA_b[c] = h;
}
`;

const smoothFlags = (xs, lo, hi) => xs.map((x) => (x >= lo && x <= hi ? 1 : 0));

/** The real ground on a level's grid (metres above `base`, row 0 south): the main DEM inside its extent, the
 * harmonised surround outside it (module doc). A new field (real_place.py ground, without its `inside` array). */
export function ground(R, dem, base, x0, y0, cell, n, blendM = 2000.0) {
    const P = prims(R);
    const xs = Array.from({ length: n }, (_, i) => x0 + (i + 0.5) * cell), ys = Array.from({ length: n }, (_, j) => y0 + (j + 0.5) * cell);
    const ix = smoothFlags(xs, dem.x0, dem.x0 + dem.side), iy = smoothFlags(ys, dem.y0, dem.y0 + dem.side);
    const src = dem.heights(R, base);
    const hm = resample(R, src.h, dem.x0, dem.pixel, x0, y0, cell, n);
    if ((ix.every(Boolean) && iy.every(Boolean)) || !dem.ctx) return hm;
    const hc = resample(R, src.ctx, dem.ctx.c0, dem.ctx.pixel, x0, y0, cell, n);
    const axes = new Float32Array(4 * n);
    for (let q = 0; q < n; q++) {
        axes[q] = ix[q];
        axes[n + q] = iy[q];
        axes[2 * n + q] = Math.max(Math.abs(xs[q] - (dem.x0 + dem.side / 2)) - dem.side / 2, 0.0);
        axes[3 * n + q] = Math.max(Math.abs(ys[q] - (dem.y0 + dem.side / 2)) - dem.side / 2, 0.0);
    }
    const af = P.list(4 * n, 'f32', axes);
    const k = R.kernel('real_place_ground', K_GROUND);
    const v = R.field(n, n, 1), w = R.field(n, n, 1), out = R.field(n, n, 1);
    R.run(k, { hm, hc, resid: P.dummyF, axes: af }, { outA: v, outB: w }, { uMode: 0, uBlend: 1.0 });
    const resid = pushPull(R, v, w);
    R.run(k, { hm, hc, resid, axes: af }, { outA: out, outB: w }, { uMode: 1, uBlend: Math.max(blendM, cell) });
    for (const f of [hm, hc, af, v, w, resid]) f.destroy();
    return out;
}

const K_CODE = `
// real_place.py _water: each cell's water code, the DEM's water mask at the cell (nearest pixel), 0 outside the DEM's
// extent; and, where the place has sea and a surround, the surround at or under the sea's level (+ 0.3 m) is sea
// (255).
//! sampler mask r32ui    the DEM's water mask, row 0 south
//! sampler h r32f        the level's ground
//! sampler axes r32i     4 n numbers: the mask's column of each cell column, its row of each cell row, 1 where the
//                        column lies outside the DEM's extent, 1 where the row does
//! image   outC r32ui
//! uniform int uSea      1: the sea rule applies
//! uniform float uTop    the sea's level + 0.3 m, in h's frame

fn kmain(p: vec2<i32>) {
  let n = outC_size();
  if (!inside(p, n)) { return; }
  let c = p.y * n.x + p.x;
  let outside = axes_b[2 * n.x + p.x] != 0 || axes_b[3 * n.x + p.y] != 0;
  var code = 0u;
  if (!outside) {
    code = mask_b[axes_b[n.x + p.y] * mask_size().x + axes_b[p.x]];
  } else if (u.uSea != 0 && h_b[c] <= u.uTop) {
    code = 255u;
  }
  outC_b[c] = code;
}
`;

const K_SHORE = `
// real_place.py _shore_distance: metres from each cell of a water body to the nearest cell outside it, an
// 8-neighbour chamfer distance, one sweep per dispatch (every cell from the sweep before, as numpy's). uInit starts
// it: a large number inside the body, 0 outside.
//! sampler code r32ui
//! sampler d r32f        the sweep before (any float field when uInit is 1)
//! image   outD r32f
//! uniform int uInit
//! uniform int uValue    the body's code
//! uniform vec2 uStep    the cell, and the cell's diagonal

fn kmain(p: vec2<i32>) {
  let n = outD_size();
  if (!inside(p, n)) { return; }
  let c = p.y * n.x + p.x;
  if (u.uInit != 0) {
    var d0 = 0.0;
    if (code_b[c] == u32(u.uValue)) { d0 = 1.0e30; }
    outD_b[c] = d0;
    return;
  }
  var best = d_b[c];
  for (var k = 0; k < 8; k++) {
    let q = p + OFF[k];
    if (!inside(q, n)) { continue; }
    var step = u.uStep.x;
    if (OFF[k].x != 0 && OFF[k].y != 0) { step = u.uStep.y; }
    best = min(best, d_b[q.y * n.x + q.x] + step);
  }
  outD_b[c] = best;
}
`;

const K_BOWL = `
// real_place.py _water: under a water body the ground drops into a bowl, min(0.5 + slope x the distance from the
// shore, the lake depth) below the body's level (or below the ground, where that is lower), and the depth is the
// level less the new ground. Other cells pass through.
//! sampler code r32ui
//! sampler d r32f        the shore distance (not yet limited to the reach)
//! sampler h r32f
//! sampler depth r32f
//! image   outH r32f
//! image   outW r32f
//! uniform int uValue    the body's code
//! uniform vec4 uP       the reach, the lake depth, the body's level, the bowl's slope

fn kmain(p: vec2<i32>) {
  let n = outH_size();
  if (!inside(p, n)) { return; }
  let c = p.y * n.x + p.x;
  var hn = h_b[c];
  var w = depth_b[c];
  if (code_b[c] == u32(u.uValue)) {
    let bowl = min(0.5 + u.uP.w * min(d_b[c], u.uP.x), u.uP.y);
    hn = min(hn, u.uP.z) - bowl;
    w = u.uP.z - hn;
  }
  outH_b[c] = hn;
  outW_b[c] = w;
}
`;

/** { h (the ground lowered under the water), depth (the water depth, or null) } on a level's grid, from the DEM's
 * water mask (real_place.py _water). `h` is the level's ground above `base`; it is released when water changes it. */
export function water(R, dem, base, h, x0, y0, cell, n, lakeDepthM) {
    if (!dem.waterMask || !dem.water.length) return { h, depth: null };
    const P = prims(R);
    const axes = new Int32Array(4 * n);
    for (let q = 0; q < n; q++) {
        const x = x0 + (q + 0.5) * cell, y = y0 + (q + 0.5) * cell;
        axes[q] = Math.min(Math.max(Math.floor((x - dem.x0) / dem.pixel), 0), dem.n - 1);
        axes[n + q] = Math.min(Math.max(Math.floor((y - dem.y0) / dem.pixel), 0), dem.n - 1);
        axes[2 * n + q] = x < dem.x0 || x > dem.x0 + dem.side ? 1 : 0;
        axes[3 * n + q] = y < dem.y0 || y > dem.y0 + dem.side ? 1 : 0;
    }
    const af = P.list(4 * n, 'i32', axes);
    const seaLevel = dem.sea.length ? Number(dem.sea[0].level_m) : null;
    const code = R.field(n, n, 1, null, 'u32');
    R.run(R.kernel('real_place_code', K_CODE), { mask: dem.waterMask, h, axes: af }, { outC: code },
        { uSea: seaLevel !== null && dem.ctx ? 1 : 0, uTop: seaLevel !== null ? seaLevel + 0.3 - base : 0.0 });
    af.destroy();
    const shore = R.kernel('real_place_shore', K_SHORE), bowl = R.kernel('real_place_bowl', K_BOWL);
    let depth = R.field(n, n, 1);
    const reach = lakeDepthM / LAKE_SLOPE;
    const steps = Math.trunc(Math.ceil(reach / cell)) + 1;
    const uStep = [cell, Math.sqrt(2.0) * cell];
    for (const wb of dem.water) {
        const value = Math.trunc(wb.mask_value ?? 255);
        const d = R.pair(n, n, 1);
        R.run(shore, { code, d: P.dummyF }, { outD: d.src }, { uInit: 1, uValue: value, uStep });
        for (let s = 0; s < steps; s++) {
            R.run(shore, { code, d: d.src }, { outD: d.dst }, { uInit: 0, uValue: value, uStep });
            d.swap();
        }
        const hn = R.field(n, n, 1), wn = R.field(n, n, 1);
        R.run(bowl, { code, d: d.src, h, depth }, { outH: hn, outW: wn }, { uValue: value, uP: [reach, lakeDepthM, Number(wb.level_m) - base, LAKE_SLOPE] });
        d.destroy();
        h.destroy();
        depth.destroy();
        h = hn;
        depth = wn;
    }
    code.destroy();
    return { h, depth };
}


// ------------------------------------------------------------------------------------------------ the op ---

/** Stage op 'dem': the level's h and water from the DEM, metres above the base (module doc). The bed is the surface
 * (a DEM is rock or what lies on it; nothing tells them apart), so the hero levels' talus and fluvial refinement
 * treat the inherited ground as rock and only what they add as loose. `fields` is the level's core/fields.js Fields. */
export async function opDem(fields, level, params, _seed = 0) {
    const R = fields.R;
    const cell = Number(level.cell);
    const dem = await load(R, params.dem, params.pixel_m ?? 0.0);
    const x0 = Number(level.x0), y0 = Number(level.y0), n = Math.trunc(level.n);
    const base = dem.base(params.base ?? 'auto');
    const g = ground(R, dem, base, x0, y0, cell, n, Number(params.blend_m ?? 2000.0));
    const { h, depth } = water(R, dem, base, g, x0, y0, cell, n, Number(params.lake_depth_m ?? 30.0));
    const bed = R.like(h);
    R.copy(h, bed);
    fields.h = h;
    fields.bed = bed;
    if (depth !== null) fields.water = depth;
}

export const OPS = { dem: opDem };


// ----------------------------------------------------------------------------------------------- the recipe ---

/** The defaults that follow from the DEM: size and resolution (its extent and pixels), context (4 when it has a
 * surround), the base elevation, the sea level, and (with the surfacing wave's build/palettes.js) the palette and the
 * mask parameters of a listed place. ctx: { R (the GPU runner), log }. */
export async function defaultsFor(values, ctx) {
    const dem = await load(ctx.R, values.dem, values.pixel_m ?? 0.0);
    const base = dem.base(values.base ?? 'auto');
    let context = null;
    if (dem.ctx) {                                       // the largest power of two the surround covers (Fuji's 3 x: 2)
        const ratio = dem.ctx.n * dem.ctx.pixel / dem.side;
        context = ratio >= 2 ? 2 ** Math.trunc(Math.floor(Math.log2(ratio) + 1e-9)) : null;
    }
    const out = { size: dem.side, resolution: dem.n, context, hero_cell: 0.5, base_elevation_m: base, centre: [0.0, 0.0],
        title: dem.meta.title ?? dem.name, landform: dem.meta.landform ?? '', attribution: dem.meta.attribution ?? '' };
    if (dem.sea.length) out.sea_level = Number(dem.sea[0].level_m) - base;
    let Pal = null;
    try {
        Deno.statSync(new URL('../build/palettes.js', import.meta.url));
        Pal = await import(new URL('../build/palettes.js', import.meta.url).href);
    } catch (_e) { /* the surfacing wave's module is not in the checkout */ }
    const place = Pal?.PLACES?.[dem.name];
    if (place) {
        out.palette = place.palette;
        out.place = dem.name;
        const mp = { ...(place.mask_params ?? {}) };
        delete mp.sea_level;                             // absolute there; the sea level above is in y's frame
        if (place.strata) mp.strata = { dip_deg: 0.0 };  // the strata mask as altitude: the material adds the place's
        out.mask_params = mp;                            // offset, faults and warp to it
    }
    return out;
}

export const REAL_PLACE = new Recipe(
    'real_place', 'Real elevation data as the main tile, refined by the detail stages below its pixel',
    ['the DEM itself'],
    { hero_cell: 0.5 },
    {
        dem: new Knob('lauterbrunnen', 'name', null, 'a reference name (dem_names()) or the path of a DEM file'),
        base: new Knob('auto', 'choice', ['auto', 'min', 'sea'],
            "z = 0 at the main DEM's lowest point ('min'), at sea level ('sea'); 'auto' is 'sea' where the " +
            'place has sea'),
        blend_m: new Knob(2000.0, 'm', [0.0, 1.0e6], 'how far outside the DEM its difference from the surround fades'),
        lake_depth_m: new Knob(30.0, 'm', [0.0, 2000.0], 'the deepest point of the bowl under each lake or the sea'),
        pixel_m: new Knob(0.0, 'm', [0.0, 1.0e4], 'the pixel of a bare .npy DEM (0 for the reference files)'),
    },
    [
        new Stage('dem', { dem: '$dem', base: '$base', blend_m: '$blend_m', lake_depth_m: '$lake_depth_m', pixel_m: '$pixel_m' },
            ['context', 'main']),
        new Stage('fluvial', { mode: 'refine' }, 'hero', null, 'fluvial_refine'),
        new Stage('talus', { repose_deg: 35.0 }, 'hero'),
        new Stage('breakup', {}, 'hero'),
        new Stage('hydraulic', {}, 'hero'),
    ],
    'The main tile is the DEM; context levels are its surround harmonised to it; hero levels refine it. The ' +
    'hero stages (fluvial refinement, talus, rock breakup, hydraulic) belong to the fluvial and detail packages: ' +
    'pass their parameters through a recipe dict until their defaults are set here.');
REAL_PLACE.defaultsFor = defaultsFor;
REAL_PLACE.defaults_for = defaultsFor;

export const RECIPES = [REAL_PLACE];
export { demNames as dem_names, demDirs as dem_dirs, opDem as op_dem, pushPull as push_pull };
