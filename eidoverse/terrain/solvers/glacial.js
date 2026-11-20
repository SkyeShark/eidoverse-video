// Port of blender/eidoblend/terrain/solvers/glacial.py at f90c6fc.
//
// The glacial carve (design section 4.5): troughs, hanging valleys, cirques and talus carved where ice would flow,
// guided by the fluvial network. A procedural carve, not ice physics: the shallow-ice approximation carves narrow
// defiles, not U-valleys (the research's finding).
//
//     stage ops (OPS; run.js calls op(fields, level, params, seed, ctx)):
//       'valley_uplift'  the uplift of a glaciated range around one main valley: a crest across its head and two side
//                        ridges along it ('horseshoe', the default: Lauterbrunnen's setting), or a core/compose.js
//                        uplift shape (ridge, dome, plateau, massif). U on the coarsest level's passes, the rough start
//                        surface on its first; the fields 'trough' etc. start at 0 so a `where` can read them. A
//                        horseshoe with a 'trunk' holds the pre-glacial trunk river along the valley's axis as base
//                        level on every pass of the coarsest level (trunkCourse, trunkPins): one river from the valley
//                        head out past the grid's edge, so the range's drainage gathers into ONE main valley and the
//                        ice that later fills it is the trunk glacier, its tributaries hanging above it
//       'glacial'        on the coarsest level, once it is fully grown: the ice discharge, the glaciated centrelines,
//                        the cirques, the jump flood, the U-carve, the fresh walls' threshold and lateral moraines. On
//                        every finer level: the walls it inherits are sharpened to the level's own resolution
//                        (sharpenWalls, from the cross-section the carve left per cell: PROFILE_FIELDS), keep their
//                        steep threshold, and fail at it at the level's own scale where the rock is weak, with
//                        fall-line couloirs and ribs (wallFlutes) on the levels that resolve them
//
// The carve, step by step (glacial.py's module doc has the reasons; the numbers below are its):
//   1. Ice discharge (kernels/ice_flux.wgsl, iterated to convergence): b(z) = clamp(beta (z - ELA), -b_abl, b_acc)
//      routed down the D8 receivers of the lake-filled surface, flats crossed toward their outlets
//      (drainageReceivers), Q = max(0, Q_in + a), a = b cell^2 accumulating, b cell L ablating (L = 2 W(Q_in)).
//      The same kernel with b = 1 gives the D8 drainage area.
//   2. Centrelines: cells with ice, a drainage area of a channel, and a trough at least min_width_cells wide;
//      streams by main stem; positions and parameters smoothed along each stream; per seed f, W, H, the floor
//      zf = z_c - d, the wobble, the fans' rise, the head taper, the graded valley fill.
//   3. Cirques at glacier heads near the ELA, spaced by blue-noise rejection, backed onto the divide above the head.
//   4. Jump flood (kernels/jump_flood.wgsl): each cell's four best seeds of different streams, by the target height.
//   5. U-carve (kernels/u_carve.wgsl): the target per seed joined by a smooth minimum, cut into the surface.
//   6. Fresh walls: the threshold pass with Sc = tan(wall_deg) x lognormal noise in the trough.
//   7. Lateral moraines (u_carve.wgsl, moraine_m).
//
// Fields written: h, bed, wear, valley_fill, deposit, talus, Sc, ice, trough, trough_floor, trough_wall, carve,
// trough_rho, PROFILE_FIELDS (trough_zf, trough_H, trough_ff, trough_fill, trough_rise, trough_sharp), and on the
// coarsest level ice_q, glacial_streams and trunk. Parameters: as glacial.py's (DEFAULTS below: the same names, units
// and meanings; glacial.py's module doc explains each).
//
// The dispatch log (PORT_PLAN.md 5.7): the Blender kernels here are ice_flux (in loops of `check` = 128 iterations
// that stop on a convergence test: CONVERGENCE_LOOPS), jump_flood, u_carve, world_noise_field (through
// core/world_noise.js fieldGpu, where glacial.py calls field_gpu: the walls' unit noise, the flutes, the uplift) and
// the threshold pass's kernels (solvers/hillslope.js Pass), in glacial.py's order with its uniforms.
//
// Where this differs from glacial.py, and why (PORT_PLAN.md 2.4, 3.2: every per-cell and per-seed step runs on the
// GPU; the plans over objects stay JavaScript):
//   - Fields are core/gpu.js fields; the ops are async (convergence tests, the cirque plan's inputs, reductions).
//   - The numpy code over whole levels and over the seeds is the port's own kernels in kernels/glacial/, each naming
//     the numpy lines it replaces: the receivers' k (recv_k: the receivers themselves are solvers/hydro.js's,
//     hydro.py flow_receivers' rule, which is drainage_receivers' own: the same D8 rule and flat step; glacial's
//     d8_receivers divides the slopes by LEN x cell where fluvial's divides by LEN, a common positive factor, so the
//     order differs only on float64 near-ties, and the kernel compares exactly up to one float32 rounding), the mass
//     balance, the discharge's convergence test (a reduction: 8 bytes a test instead of the field), the channel
//     and seed masks, the streams (seed_pos, seed_links: numpy's lexsort of each receiver's donors and its first of
//     each segment is a gather over the eight neighbours here, which keeps the same donor: the largest discharge,
//     then the lowest position; the pointer jumping and np.unique are core/prims.js pathSteps and cumsum),
//     smooth_along, head_distance and graded_fill (numpy's own relaxations, one sweep a dispatch, until nothing
//     changes), the per-seed troughs, seed_textures, best_donor (a gather that keeps numpy's tie rule), the
//     hollow walk of the cirque plan, the layers after the carve, profile_fields, the walls' threshold, the flutes,
//     sharpen_walls and lip_open (the opening is core/prims.js dilate). numpy evaluates them in float64 and rounds to
//     float32 once; here they are float32, in numpy's order.
//   - Two of numpy's float64 loops run in a better-conditioned form of the same quantity (PORT_PLAN.md risk 2), as
//     float32 would otherwise round at the values' own size on every sweep: smooth_along keeps each seed's offset from
//     its start (the cell's centre, its h, its f) and smooths the offsets with the neighbours' exact start
//     differences (positions of tens of kilometres, 288 passes: millimetres of drift otherwise, which a trough wall at
//     80 degrees turns into centimetres of target height); graded_fill relaxes the fill (top - zf) instead of the top.
//     Both have numpy's fixed point; tests/glacial/functions_test.mjs grades them against it.
//   - The seeds' world noise (numpy's world_noise.fbm at the seeds) is kernels/glacial/point_noise.wgsl, the
//     world-noise evaluation of core/world_noise.js's term tables at a list of points: Blender dispatches no kernel
//     there, so the port's is its own (world_noise_field is a Blender kernel the dispatch log compares).
//   - The seeds' x and y are kept from the level's corner (seedA's frame) instead of world metres: the same
//     smoothing (it is affine), one rounding less; the cirque plan adds the corner back in doubles.
//   - seeds = chan & (W_t f >= min_width_cells cell): numpy's float64 test is made a float32 threshold on the
//     discharge, found with numpy's own arithmetic in doubles (seedQmin), so the seed cells are numpy's.
//   - The cirque plan (its draws, order, walks and spacing test) is glacial.py's, in JavaScript doubles over the
//     seeds read back once; its walk up each hollow runs for every head at once on the GPU (hollow_walk).
//   - flux_budget, brute_force and decode_best (glacial.py's checks and the jump flood's oracle) live in the tests
//     (tests/glacial/), in doubles as numpy has them; the numpy twins of the kernels stay in Python.
//   - trunkCourse and trunkPins call solvers/rivers.js (arc length, the 1D noise, the channel), as glacial.py calls
//     solvers/rivers.py; they import it when they run, so this module loads without it. rivers.js keeps a channel
//     cell's arc length as its nearest segment and the parameter along it, and its bed kernel
//     (kernels/strata/river_pins.wgsl) evaluates a bed given at the course's points linearly along each segment:
//     trunk_pins' np.interp(s, course s, course bed) is exactly that, so the trunk's pins are that kernel.
//   - The pins the trunk adds (valley_uplift's ctx.pins) are released by the next pass's valley_uplift (fields of
//     the GPU are not collected).
//   - Python's round() is core/levels.js pyRound (half to even); f'{x:.3g}' is pyFormat.
//
// The convergence loop this module names for the dispatch-log comparison (PORT_PLAN.md 5.7): ice_flux, tested every
// `check` (128) iterations (CONVERGENCE_LOOPS).

import * as C from '../core/compose.js';
import * as Gd from '../core/grid.js';
import { pyFormat, pyRound } from '../core/levels.js';
import { defaultRng } from '../core/np_random.js';
import { f32AtOrBelow, prims } from '../core/prims.js';
import * as N from '../core/world_noise.js';
import * as RUN from '../run.js';
import * as DT from './detail.js';
import * as FL from './fluvial.js';
import * as HS from './hillslope.js';
import * as HY from './hydro.js';

export const OPEN = 0, PERIODIC = 1, PINNED = 2;
export const CONVERGENCE_LOOPS = Object.freeze({ 'glacial|ice_flux': 128 });

export const DEFAULTS = Object.freeze({
    ela_m: 2400.0, beta: 0.005, b_acc_m: 2.0, b_abl_m: 6.0, p_ice: 0.0,
    ice_width_m: 750.0, ice_width_q: 5.0e7, ice_width_exp: 0.4, ice_width_max_m: 3000.0,
    trough_width_m: 1200.0, trough_depth_m: 600.0, floor_frac: null, wall_toe: 0.35, wall_lip: 0.2, floor_rise: 0.02,
    floor_exp: 0.0, rise_noise: 0.0, rise_scale_m: 900.0, head_taper: 0.0,
    overdeepen: 0.6, overdeepen_exp: 1.0, cirque_ela_m: null,
    f_max: 1.6, shoulder_width: 0.0, shoulder_rise: 0.25, shoulder_exp: 2.0, upper_wall: 1.5, cut: 0.6, cut_width: 2.0,
    shoulder_cut: 0.0, shoulder_cut_width: 2.0, lip_open_m: 0.0,
    floor_grade: 0.012,
    wobble_m: 700.0, wobble_w: 0.12, wobble_h: 0.1,
    channel_area_m2: 1.5e6, min_width_cells: 2.0, smooth_cells: 6.0, join_m: 60.0, trim_m: 20.0,
    cirques: true, cirque_band_m: 300.0, cirque_radius_m: [400.0, 800.0], cirque_elong: 1.35, cirque_depth_m: 350.0,
    cirque_floor_m: 50.0, cirque_floor_frac: 0.35, cirque_exp: 2.0, cirque_spacing: 1.5, cirque_headroom_m: 0.0,
    cirque_headwall_m: 500.0, cirque_open: 2.5, cirque_tarn_m: 40.0, cirque_lobes: 0.15, cirque_tilt_deg: 8.0,
    wall_deg: 65.0, wall_noise: 0.15, wall_scales_m: [400.0, 120.0], wall_iters: 64, wall_rate: 0.12,
    flute_weak: 0.9, flute_strong: 0.35, flute_scales_m: [80.0, 40.0, 20.0], flute_stretch: 5.0, cap_join_m: 40.0,
    rock_flutes: 0.0, rock_flute_deg: 38.0,
    moraine_m: 25.0, moraine_at: null, moraine_width: 0.07,
    refine_wall_iters: 160, seed: 0,
});
export const MAX_CIRQUES = 512;
export const HEAD_TAPER_MIN = 0.1;
export const SEED_C_DEFAULT = Object.freeze([1.0, 1.0, 0.0, 0.0]);
export const FLUTE_ORIENTATIONS = 8;

const DEG = Math.PI / 180.0;                       // CPython's math.radians: x * (pi / 180)
const RAD = 180.0 / Math.PI;                       // math.degrees: x * (180 / pi)
const now = () => performance.now() / 1000;
const has = (o, k) => o !== null && o !== undefined && Object.prototype.hasOwnProperty.call(o, k);
const round2 = (s) => Math.round(s * 100) / 100;

/** glacial.py _p: the parameter, or its default when it is missing or None. */
export function _p(params, key) {
    const d = DEFAULTS[key];
    const v = has(params, key) ? params[key] : d;
    return v === null || v === undefined ? d : v;
}

/** Where the lateral moraine stands, a share of the half-width: given, or just past the flat floor's edge. */
export function moraineAt(params) {
    const v = params?.moraine_at;
    return v !== null && v !== undefined ? Number(v) : floorFrac(params) + 0.1;
}

/** The cliff's core slope over its mean slope (cliff()): 1 / (1 - (wall_toe + wall_lip) / 2). */
export function coreFactor(params) {
    const toe = Number(_p(params, 'wall_toe')), lip = Number(_p(params, 'wall_lip'));
    return 1.0 / Math.max(1.0 - 0.5 * (toe + lip), 0.5);
}

/** The flat floor's share of the trough's half-width: floor_frac when given, else what the wall leaves when its core
 * stands at wall_deg. Clamped to 0-0.9. */
export function floorFrac(params) {
    let v = params?.floor_frac;
    if (v === null || v === undefined) {
        const W = 0.5 * Number(_p(params, 'trough_width_m'));
        const H = Number(_p(params, 'trough_depth_m'));
        const run = (coreFactor(params) * H) / Math.tan(Math.min(Math.max(Number(_p(params, 'wall_deg')), 5.0), 89.0) * DEG);
        v = 1.0 - run / Math.max(W, 1e-6);
    }
    return Math.min(Math.max(Number(v), 0.0), 0.9);
}

/** The cross-section's uniforms (jump_flood.wgsl, u_carve.wgsl). */
export function profileUniforms(params) {
    const toe = Math.min(Math.max(Number(_p(params, 'wall_toe')), 0.0), 1.0);
    const lip = Math.min(Math.max(Number(_p(params, 'wall_lip')), 0.0), 1.0 - toe);
    return { uFloorFrac: floorFrac(params), uToe: toe, uLip: lip, uFloorRise: Number(_p(params, 'floor_rise')),
        uShW: Number(_p(params, 'shoulder_width')), uShH: Number(_p(params, 'shoulder_rise')),
        uShB: Number(_p(params, 'shoulder_exp')), uOut: Number(_p(params, 'upper_wall')) };
}

/** profileUniforms() plus u_carve.wgsl's cap beyond the lip and the shoulder cut's reach. */
export function carveUniforms(params) {
    return { ...profileUniforms(params), uCut: Number(_p(params, 'cut')), uCutW: Number(_p(params, 'cut_width')),
        uCapJoin: Number(_p(params, 'cap_join_m')), uShCutW: Number(_p(params, 'shoulder_cut_width')) };
}

/** The jump flood's steps: powers of two from the one covering reachCells down to 1, then 1 again. */
export function jfaSteps(reachCells, n) {
    let k = 1;
    while (k < Math.min(Math.max(reachCells, 1.0), n)) k *= 2;
    const out = [];
    while (k >= 1) {
        out.push(k);
        k = Math.floor(k / 2);
    }
    return [...out, 1];
}

/** head_taper_factor for one seed (doubles; the seeds' own run in kernels/glacial/seed_params.wgsl). */
export function headTaperFactor(dist, W, headTaper) {
    const q = Math.min(Math.max(Number(dist) / Math.max(Number(headTaper) * Number(W), 1e-6), 0.0), 1.0);
    return HEAD_TAPER_MIN + (1.0 - HEAD_TAPER_MIN) * q * q * (3.0 - 2.0 * q);
}


// =========================================================================================== small GPU helpers ===

const KERNELS = new WeakMap();
function kernelOf(R, name) {
    let m = KERNELS.get(R);
    if (!m) KERNELS.set(R, (m = new Map()));
    let k = m.get(name);
    if (!k) m.set(name, (k = R.kernel(name)));
    return k;
}

// distinct stand-ins per runner (a dispatch may not bind one field as a sampler and an image)
const STANDINS = new WeakMap();
function standins(R) {
    let d = STANDINS.get(R);
    if (!d) {
        d = { i1: R.field(1, 1, 1, null, 'i32'), i2: R.field(1, 1, 1, null, 'i32'), u1: R.field(1, 1, 1, null, 'u32'),
            u2: R.field(1, 1, 1, null, 'u32'), u3: R.field(1, 1, 1, null, 'u32'), u4: R.field(1, 1, 1, null, 'u32'),
            f1: R.field(1, 1, 1), f2: R.field(1, 1, 1), f3: R.field(1, 1, 1), f4: R.field(1, 1, 1), f5: R.field(1, 1, 1),
            f6: R.field(1, 1, 1), f7: R.field(1, 1, 1), f8: R.field(1, 1, 1), g2: R.field(1, 1, 2), g4: R.field(1, 1, 4) };
        STANDINS.set(R, d);
    }
    return d;
}

const cover = (f) => [Math.ceil(f.w / 16), Math.ceil(f.h / 16), 1];
const F32 = new Float32Array(1), U32 = new Uint32Array(F32.buffer);
const bitsToF32 = (b) => { U32[0] = b; return F32[0]; };

/** The largest float32 strictly below x (a float32 v satisfies v < x exactly when v <= this). */
export function f32Below(x) {
    const f = f32AtOrBelow(x);
    if (f < x) return f;
    F32[0] = f;
    if (f > 0) U32[0] -= 1;
    else if (f < 0) U32[0] += 1;
    else U32[0] = 0x80000001;
    return F32[0];
}
/** The smallest float32 at or above x (v >= x exactly when v >= this). */
export const f32AtOrAbove = (x) => -f32AtOrBelow(-x);
/** The smallest float32 strictly above x (v > x exactly when v >= this). */
export const f32Above = (x) => -f32Below(-x);

// dispatch step(src, dst, counted, counter) in chunks until a chunk's counted sweep changes nothing (numpy's loops
// that stop at the first sweep equal to the last); returns the sweeps
async function relaxList(R, pair, step, what, maxSweeps = 1 << 20) {
    const counter = R.field(1, 1, 1, null, 'u32');
    let done = 0, chunk = 8;
    try {
        for (;;) {
            R.clear(counter);
            for (let i = 0; i < chunk; i++) {
                step(pair.src, pair.dst, i === chunk - 1, counter);
                pair.swap();
            }
            done += chunk;
            const got = await R.readRange(counter, 0, 1);
            if (got[0] === 0) return done;
            if (done >= maxSweeps) throw new Error(`glacial: ${what} not settled after ${done} sweeps`);
            chunk = Math.min(chunk * 2, 64);
        }
    } finally {
        counter.destroy();
    }
}

function destroyAll(...fs) {
    for (const f of fs) if (f && typeof f.destroy === 'function' && !f.destroyed) f.destroy();
}


// ======================================================================================== the receivers ===

/** The receivers as glacial.py keeps them: each cell's neighbour k (0..7, -1 none) as an r32f field, from a
 * row-major receiver field (solvers/hydro.js). */
export function receiverK(R, rec) {
    const out = R.field(rec.h, rec.w, 1);
    R.run(kernelOf(R, 'glacial/recv_k'), { rec }, { outK: out }, {});
    return out;
}

/** glacial.py d8_receivers(h, cell): each cell's steepest-descent neighbour k as float32, -1 where none is lower (the
 * open edges only: the production carve's receivers are drainageReceivers'). An r32f field. */
export function d8Receivers(h, cell, bound = OPEN) {
    if (bound !== OPEN) throw new Error('glacial d8Receivers: only the open boundary is ported (the carve routes on OPEN)');
    const R = h.runner;
    const rec = HY.d8Receivers(h);
    const out = receiverK(R, rec);
    rec.destroy();
    return out;
}

/** glacial.py drainage_receivers(h, cell, sea_level): the ice's (and the drainage area's) D8 receivers on the
 * depression-filled surface, across a flat the equal neighbour one breadth-first step nearer its outlet.
 * { recv (r32f k), filled (r32f) }. */
export async function drainageReceivers(h, cell, seaLevel = null) {
    const R = h.runner;
    const { filled } = await HY.fillDepressions(h, { seaLevel });
    const rec = await HY.flowReceivers(filled, { seaLevel });
    const recv = receiverK(R, rec);
    rec.destroy();
    return { recv, filled };
}


// ========================================================================================= mass balance ===

/** b (m/yr of ice) at every cell: clamp(beta (altitude - ELA), -b_abl, b_acc); seaLevel: cells at or below it
 * ablate at b_abl (carve_level's override). An r32f field. */
export function massBalance(h, baseElevationM, params, seaLevel = null) {
    const R = h.runner;
    const out = R.field(h.h, h.w, 1);
    const sea = seaLevel !== null && seaLevel !== undefined;
    R.run(kernelOf(R, 'glacial/mass_balance'), { h }, { outB: out },
        { uBeta: Number(_p(params, 'beta')), uOff: Number(baseElevationM) - Number(_p(params, 'ela_m')),
            uAbl: Number(_p(params, 'b_abl_m')), uAcc: Number(_p(params, 'b_acc_m')), uSea: sea ? 1 : 0,
            uSeaLevel: sea ? f32AtOrBelow(Number(seaLevel)) : 0.0 });
    return out;
}

/** The ice discharge Q (m^3/yr) on a fixed routing surface: ice_flux.wgsl iterated from Q = 0 until the largest change
 * over `check` iterations is under tol x the largest Q (glacial.py ice_flux_converge). opts: recv (the D8 receivers'
 * k; made from the surface when null), pIce, Qin (a field), params, bound, tol, check, maxIter. { Q, iterations }. */
export async function iceFluxConverge(R, surface, b, cell, opts = {}) {
    const pIce = opts.pIce ?? 0.0, params = opts.params ?? null, bound = opts.bound ?? OPEN;
    const tol = opts.tol ?? 1e-6, check = opts.check ?? 128;
    const ny = surface.h, nx = surface.w;
    const d8 = pIce === null || Number(pIce) <= 0.0;
    let wT = opts.recv ?? null, ownW = false;
    if (d8 && !wT) {
        wT = d8Receivers(surface, cell, bound);
        ownW = true;
    } else if (!d8) {
        wT = R.field(ny, nx, 1);
        ownW = true;
        R.run('flow_weights', { st: surface }, { outW: wT }, { uDx: Number(cell), uP: Number(pIce), uBound: bound });
    }
    const mb = R.field(ny, nx, 2);
    R.run(kernelOf(R, 'glacial/mb'), { b, qin: opts.Qin ?? standins(R).f1 }, { outM: mb }, { uHasIn: opts.Qin ? 1 : 0 });
    const Qp = R.pair(ny, nx, 1), prev = R.field(ny, nx, 1), cnt = R.field(1, 2, 1, null, 'u32');
    const uni = { uDx: Number(cell), uP: Number(pIce || 0.0), uWref: Number(_p(params, 'ice_width_m')),
        uQw: Number(_p(params, 'ice_width_q')), uWexp: Number(_p(params, 'ice_width_exp')),
        uLmax: Number(_p(params, 'ice_width_max_m')), uD8: d8 ? 1 : 0, uBound: bound };
    const maxIter = Math.trunc(opts.maxIter || 8 * Math.max(ny, nx));
    const k = kernelOf(R, 'ice_flux'), kc = kernelOf(R, 'glacial/ice_change');
    let it = 0;
    while (it < maxIter) {
        for (let i = 0; i < check; i++) {
            R.run(k, { st: surface, wT, qT: Qp.src, mb }, { outQ: Qp.dst }, uni);
            Qp.swap();
        }
        it += check;
        R.clear(cnt);
        R.run(kc, { cur: Qp.src, prev }, { outC: cnt }, {}, cover(Qp.src));
        const got = await R.readRange(cnt, 0, 2);
        const change = bitsToF32(got[0]) / Math.max(bitsToF32(got[1]), 1e-30);
        R.copy(Qp.src, prev);
        if (change <= tol) break;
    }
    destroyAll(Qp.dst, prev, cnt, mb);
    if (ownW) wT.destroy();
    return { Q: Qp.src, iterations: it };
}


// ====================================================================================== the centrelines ===

/** The smallest float32 discharge q for which numpy's seed test holds: W_t min((q / Q_ref)^0.4, f_max) >=
 * min_width_cells cell, in doubles as numpy evaluates it (the test rises with q); Infinity when no q up to qmax does. */
export function seedQmin(qref, Wt, minWidthCells, cell, fMax, qmax) {
    const test = (q) => Wt * Math.min((Math.max(q, 0.0) / Math.max(qref, 1e-30)) ** 0.4, fMax) >= minWidthCells * cell;
    if (!test(qmax)) return Infinity;
    if (test(0.0)) return 0.0;
    F32[0] = qmax;
    let hi = U32[0], lo = 0;                           // test(bits lo) false, test(bits hi) true
    while (hi - lo > 1) {
        const mid = lo + Math.floor((hi - lo) / 2);
        if (test(bitsToF32(mid))) hi = mid; else lo = mid;
    }
    return bitsToF32(hi);
}

/** glacial.py streams(seed_mask, recv, Q) on the GPU: the seeds' lists. idx (u32, the cells in order), S, pos (per
 * cell: its seed's position, -1 none), rcv, main, sid (i32 lists), flags (u32 list: bit 0 cont, bit 1 head),
 * nstreams. The caller owns the fields (disposeStreams). */
export async function streams(R, flags, recv, Q) {
    const P = prims(R), D = standins(R);
    const { index: idx, n: S } = await P.nonzero(flags);
    if (!S) {
        idx.destroy();
        return null;
    }
    const n = [recv.h, recv.w];
    const pos = R.field(n[0], n[1], 1, null, 'i32');
    const kp = kernelOf(R, 'glacial/seed_pos'), kl = kernelOf(R, 'glacial/seed_links');
    R.run(kp, { idx: D.u1 }, { outPos: pos }, { uMode: 0, uCount: 0 });
    R.run(kp, { idx }, { outPos: pos }, { uMode: 1, uCount: S }, cover(idx));
    const rcv = P.list(S, 'i32'), main = P.list(S, 'i32'), next = P.list(S, 'i32'), sid = P.list(S, 'i32');
    const fl = P.list(S, 'u32'), ends = P.list(S, 'u32');
    const base = { idx, recv, pos, Q };
    R.run(kl, { ...base, la: D.i1, lb: D.i2, ua: D.u1, ub: D.u2 }, { outL: rcv, outF: D.u3, outT: D.u4 }, { uMode: 0, uCount: S });
    R.run(kl, { ...base, la: rcv, lb: D.i2, ua: D.u1, ub: D.u2 }, { outL: main, outF: D.u3, outT: D.u4 }, { uMode: 1, uCount: S });
    R.run(kl, { ...base, la: rcv, lb: main, ua: D.u1, ub: D.u2 }, { outL: next, outF: fl, outT: ends }, { uMode: 2, uCount: S });
    // the pointer jumping to each stream's downstream end, and np.unique's inverse: the ends' ranks in position order
    const { steps, terminal } = await P.pathSteps(next);
    steps.destroy();
    const rank = P.cumsum(ends, { count: S, exclusive: true });
    R.run(kl, { ...base, la: D.i1, lb: D.i2, ua: terminal, ub: rank }, { outL: sid, outF: D.u3, outT: D.u4 }, { uMode: 3, uCount: S });
    const [rl, el] = await R.readParts([{ field: rank, first: S - 1, count: 1 }, { field: ends, first: S - 1, count: 1 }]);
    const nstreams = rl[0] + el[0];
    destroyAll(next, terminal, rank, ends);
    return { idx, S, pos, rcv, main, sid, flags: fl, nstreams };
}

/** Release a streams() record's fields. */
export function disposeStreams(st) {
    if (st) destroyAll(st.idx, st.pos, st.rcv, st.main, st.sid, st.flags);
}

/** glacial.py smooth_along over a seeds' rgba32f list V (x, y with link_tributaries, zc, f without), n = round(2
 * sigma^2) passes, as each seed's offset from its start (kernels/glacial/smooth_along.wgsl: the same sums, rounded at
 * the offsets' size). A new field (V is not changed). */
export function smoothAlong(R, V, st, sigmaCells) {
    const n = pyRound(2.0 * Number(sigmaCells) ** 2);
    const pair = R.pair(V.h, V.w, 4);
    const k = kernelOf(R, 'glacial/smooth_along');
    const links = { main: st.main, rcv: st.rcv, flags: st.flags };
    for (let i = 0; i < n; i++) {
        R.run(k, { V, E: pair.src, ...links }, { outV: pair.dst }, { uMode: 0, uCount: st.S });
        pair.swap();
    }
    R.run(k, { V, E: pair.src, ...links }, { outV: pair.dst }, { uMode: 1, uCount: st.S });
    pair.src.destroy();
    return pair.dst;
}

/** glacial.py head_distance: each seed's distance (m) up its main stem to its stream's head, numpy's relaxation.
 * { dist (r32f list), sweeps }. */
export async function headDistance(R, st, V) {
    const pair = R.pair(V.h, V.w, 1);
    const k = kernelOf(R, 'glacial/head_dist');
    const sweeps = await relaxList(R, pair, (src, dst, counted, changed) => {
        R.run(k, { D: src, V, main: st.main }, { outD: dst, changed }, { uCount: st.S, uCounted: counted ? 1 : 0 });
    }, 'head_distance');
    pair.dst.destroy();
    return { dist: pair.src, sweeps };
}

/** glacial.py graded_fill(zf, 0, x, y, st, grade, outlet=zc): the valley fill above each seed's floor, numpy's
 * relaxation, run on the fill itself (kernels/glacial/graded_fill.wgsl: the same fixed point, rounded at the fill's
 * size). V: (x, y, zc, f); Pz: (W, H, d, zf). { fill (r32f list), sweeps }. */
export async function gradedFill(R, st, V, Pz, grade) {
    const pair = R.pair(V.h, V.w, 1);
    const k = kernelOf(R, 'glacial/graded_fill');
    const un = { uGrade: Number(grade), uCount: st.S };
    R.run(k, { T: standins(R).f1, V, P: Pz, rcv: st.rcv }, { outT: pair.src, changed: standins(R).u1 }, { ...un, uMode: 0, uCounted: 0 });
    const sweeps = await relaxList(R, pair, (src, dst, counted, changed) => {
        R.run(k, { T: src, V, P: Pz, rcv: st.rcv }, { outT: dst, changed }, { ...un, uMode: 1, uCounted: counted ? 1 : 0 });
    }, 'graded_fill');
    pair.dst.destroy();
    return { fill: pair.src, sweeps };
}

/** world_noise.fbm (a field spec of one leaf kind) at a list of points (the xy of an rgba32f or rg32f list, metres
 * from the level's corner): kernels/glacial/point_noise.wgsl with core/world_noise.js's term table. An r32f list. */
export function pointNoise(R, spec, level, seed, pts, count) {
    const [terms, constant] = N.leafTerms(spec, Math.trunc(seed), level.x0, level.y0);
    const tt = new Float32Array(Math.max(2 * terms.length, 2) * 4);
    terms.forEach(([mode, iw, c, pc, bx, by, fx, fy], t) => {
        tt.set([mode, iw, c, pc], 8 * t);
        tt.set([bx, by, fx, fy], 8 * t + 4);
    });
    const table = R.field(1, Math.max(2 * terms.length, 2), 4, tt);
    const out = R.field(pts.h, pts.w, 1);
    R.run(kernelOf(R, 'glacial/point_noise'), { terms: table, pts }, { outF: out },
        { uTerms: terms.length, uConst: constant, uCount: count });
    table.destroy();
    return out;
}

/** glacial.py centrelines(h, Q, A, recv, level, main, params, base_elevation_m, seed): the seeds of the U-carve, on
 * the GPU. null when no cell qualifies. The record: { st (streams), S, V (x, y from the level's corner, zc, f: the
 * smoothed seeds), q, Pz (W, H, d, zf), E (moraine, floor_f, rise_f, taper), fill, Q_ref, Wt, Ht, dt, wmax,
 * dispose() }. */
export async function centrelines(R, h, Q, A, recv, level, main, params, baseElevationM, seed = 0) {
    const P = prims(R);
    const cell = Number(level.cell), n = level.n;
    const Wt = 0.5 * Number(_p(params, 'trough_width_m'));
    const Ht = Number(_p(params, 'trough_depth_m'));
    const dt = Number(_p(params, 'overdeepen')) * Ht;
    const [j0, j1, i0, i1] = RUN.mainWindow(level, main);
    const chan = R.field(n, n, 1), chanW = R.field(n, n, 1);
    R.run(kernelOf(R, 'glacial/chan_mask'), { Q, A }, { outC: chan, outW: chanW },
        { uArea: f32AtOrAbove(Number(_p(params, 'channel_area_m2'))), uWin: [j0, j1, i0, i1] });
    const sc = await P.stats(Q, { mask: chan });
    if (!sc.count) {
        destroyAll(chan, chanW);
        return null;
    }
    const sw = await P.stats(Q, { mask: chanW });
    chanW.destroy();
    const qref = sw.count ? sw.max : sc.max;
    const fMax = Number(_p(params, 'f_max'));
    const qmin = seedQmin(qref, Wt, Number(_p(params, 'min_width_cells')), cell, fMax, sc.max);
    if (!Number.isFinite(qmin)) {
        chan.destroy();
        return null;
    }
    const flags = R.field(n, n, 1, null, 'u32');
    R.run(kernelOf(R, 'glacial/seed_mask'), { chan, Q }, { outS: flags }, { uQmin: qmin });
    chan.destroy();
    const st = await streams(R, flags, recv, Q);
    flags.destroy();
    if (!st) return null;
    const S = st.S;
    // the seeds' cells, h and f there, smoothed along the streams
    const V0 = R.field(st.idx.h, st.idx.w, 4), q = R.field(st.idx.h, st.idx.w, 1);
    R.run(kernelOf(R, 'glacial/seed_init'), { idx: st.idx, h, Q }, { outV: V0, outQ: q },
        { uCell: cell, uQref: qref, uFmax: fMax, uCount: S }, cover(st.idx));
    const V = smoothAlong(R, V0, st, Number(_p(params, 'smooth_cells')));
    V0.destroy();
    // the head distance (the taper), the wobble's and the fans' noise at the smoothed seeds
    const ht = Number(_p(params, 'head_taper'));
    const hd = ht > 0 ? await headDistance(R, st, V) : null;
    const wl = Number(_p(params, 'wobble_m')), aw = Number(_p(params, 'wobble_w')), ah = Number(_p(params, 'wobble_h'));
    const wob = wl > 0 && (aw > 0 || ah > 0);
    const s = Math.trunc(seed);
    const n1 = wob ? pointNoise(R, { kind: 'fbm', wavelength_m: wl, octaves: 3 }, level, s * 31 + 801, V, S) : null;
    const n2 = wob ? pointNoise(R, { kind: 'fbm', wavelength_m: wl, octaves: 3 }, level, s * 31 + 802, V, S) : null;
    const rv = Number(_p(params, 'rise_noise')), rl = Number(_p(params, 'rise_scale_m'));
    const riseOn = rv > 0 && rl > 0;
    const n3 = riseOn ? pointNoise(R, { kind: 'fbm', wavelength_m: rl, octaves: 3 }, level, s * 31 + 803, V, S) : null;
    const Nz = R.pack({ n1, n2, n3, dist: hd?.dist ?? null }, ['n1', 'n2', 'n3', 'dist'], [V.h, V.w]);
    destroyAll(n1, n2, n3, hd?.dist);
    const Pz = R.field(V.h, V.w, 4), E = R.field(V.h, V.w, 4);
    const sc_ = Number(_p(params, 'shoulder_cut'));
    R.run(kernelOf(R, 'glacial/seed_params'), { V, N: Nz }, { outP: Pz, outE: E }, {
        uWt: Wt, uHt: Ht, uDt: dt, uOdExp: Number(_p(params, 'overdeepen_exp')), uWobW: aw, uWobH: ah, uWobble: wob ? 1 : 0,
        uRise: rv, uRiseOn: riseOn ? 1 : 0, uTaper: ht, uShCut: sc_,
        uElaF: Number(_p(params, 'ela_m')) - Number(baseElevationM), uMoraine: Number(_p(params, 'moraine_m')),
        uFloorExp: Number(_p(params, 'floor_exp')), uCount: S }, cover(V));
    Nz.destroy();
    const gf = await gradedFill(R, st, V, Pz, _p(params, 'floor_grade'));
    const wmax = (await P.stats(Pz, { channel: 0, count: S })).max;
    const cl = { st, S, V, q, Pz, E, fill: gf.fill, Q_ref: qref, Wt, Ht, dt, wmax, sweeps: { head: hd?.sweeps ?? 0, fill: gf.sweeps },
        dispose() { disposeStreams(st); destroyAll(V, q, Pz, E, gf.fill); } };
    return cl;
}

/** The seeds' arrays on the host, in doubles (the cirque plan's inputs, and the tests'): idx, rcv, main, sid (Int32 /
 * Uint32 arrays), head, cont (0 / 1), x, y (world metres), zc, f, q, W, H, d, zf, fill, moraine, floor_f, rise_f. */
export async function centrelinesToHost(R, cl, level) {
    const st = cl.st, S = cl.S;
    const parts = [st.idx, st.rcv, st.main, st.sid, st.flags, cl.V, cl.q, cl.Pz, cl.E, cl.fill];
    const got = await R.readAll(parts);
    const [idx, rcv, main, sid, fl, V, q, Pz, E, fill] = got;
    const out = { S, idx: idx.slice(0, S), rcv: rcv.slice(0, S), main: main.slice(0, S), sid: sid.slice(0, S),
        cont: new Uint8Array(S), head: new Uint8Array(S) };
    for (const k of ['x', 'y', 'zc', 'f', 'q', 'W', 'H', 'd', 'zf', 'fill', 'moraine', 'floor_f', 'rise_f']) out[k] = new Float64Array(S);
    for (let i = 0; i < S; i++) {
        out.cont[i] = fl[i] & 1;
        out.head[i] = (fl[i] >> 1) & 1;
        out.x[i] = level.x0 + V[4 * i];
        out.y[i] = level.y0 + V[4 * i + 1];
        out.zc[i] = V[4 * i + 2];
        out.f[i] = V[4 * i + 3];
        out.q[i] = q[i];
        out.W[i] = Pz[4 * i];
        out.H[i] = Pz[4 * i + 1];
        out.d[i] = Pz[4 * i + 2];
        out.zf[i] = Pz[4 * i + 3];
        out.moraine[i] = E[4 * i];
        out.floor_f[i] = E[4 * i + 1];
        out.rise_f[i] = E[4 * i + 2];
        out.fill[i] = fill[i];
    }
    return out;
}

/** glacial.py best_donor(recv, A): each cell's largest-area donor as a row-major index, -1 none. An r32i field. */
export function bestDonor(recv, A) {
    const R = recv.runner;
    const out = R.field(recv.h, recv.w, 1, null, 'i32');
    R.run(kernelOf(R, 'glacial/best_donor'), { recv, A }, { outU: out }, {});
    return out;
}


// =========================================================================================== the cirques ===

/** glacial.py cirques(cl, params, base_elevation_m, level, h, up, seed): (N, 11) rows (cx, cy, z_floor, H_c, dir_x,
 * dir_y, R_across, R_along, the rim's 3- and 5-lobed phases, their amplitude), world metres, as arrays of doubles. cl:
 * centrelines()'s record (on the GPU) or its centrelinesToHost() arrays with `host: true`; h and up: fields (the
 * hollows are walked on the GPU), or null (each bowl centred on its head). */
export async function cirques(R, cl, params, baseElevationM, level, h = null, up = null, seed = 0, host = null) {
    if (!cl || !FL.truthy(_p(params, 'cirques'))) return [];
    const cell = Number(level.cell);
    const c = host ?? await centrelinesToHost(R, cl, level);
    const cela = _p(params, 'cirque_ela_m');
    const elaF = Number(cela || _p(params, 'ela_m')) - Number(baseElevationM);
    const band = Number(_p(params, 'cirque_band_m'));
    const heads = [];
    for (let i = 0; i < c.S; i++) if (c.head[i] && c.zc[i] >= elaF - band) heads.push(i);
    if (!heads.length) return [];
    const tarn = Number(_p(params, 'cirque_tarn_m')), lobes = Number(_p(params, 'cirque_lobes'));
    const rng = defaultRng(Math.trunc(seed) * 7919 + 4243);
    const jit = rng.uniform(0.7, 1.3, heads.length);
    const key = heads.map((hd, i) => -(c.q[hd] * jit[i]));
    const order = heads.map((hd, i) => i).sort((a, b) => key[a] - key[b] || a - b).map((i) => heads[i]);
    const [rLo, rHi] = _p(params, 'cirque_radius_m').map(Number);
    const elong = Number(_p(params, 'cirque_elong')), spacing = Number(_p(params, 'cirque_spacing'));
    const depthMax = Number(_p(params, 'cirque_depth_m')), below = Number(_p(params, 'cirque_floor_m'));
    const headwall = Number(_p(params, 'cirque_headwall_m'));
    const cf = Math.min(Math.max(Number(_p(params, 'cirque_floor_frac')), 0.0), 0.95);
    const cexp = Number(_p(params, 'cirque_exp'));
    const t85 = Math.max((0.85 - cf) / (1.0 - cf), 1e-3) ** cexp;
    const room = Number(_p(params, 'cirque_headroom_m'));
    const n1 = level.n;
    // the walk up every head's hollow, on the GPU: the cell and its height after 0 .. K steps
    let chain = null, chainZ = null, K = 0;
    if (up && h) {
        K = Math.trunc((3.0 * rHi * elong) / cell);
        const hl = prims(R).list(heads.length, 'i32', Int32Array.from(heads, (i) => c.idx[i]));
        const oc = prims(R).list(heads.length * (K + 1), 'i32'), oz = R.field(oc.h, oc.w, 1);
        R.run(kernelOf(R, 'glacial/hollow_walk'), { heads: hl, up, h }, { outC: oc, outZ: oz }, { uK: K, uCount: heads.length }, cover(hl));
        [chain, chainZ] = await R.readAll([oc, oz]);
        destroyAll(hl, oc, oz);
    }
    const slot = new Map(heads.map((hd, t) => [hd, t]));
    const down = c.rcv;                                  // where(cont | (rcv >= 0), rcv, -1) is rcv
    const out = [];
    for (const hd of order) {
        const Rr = rng.uniform(rLo, rHi);
        const Ra = Rr * elong;
        let k = hd, steps = 0;
        while (steps < Math.max(3, Math.trunc((0.5 * Rr) / cell)) && down[k] >= 0) {
            k = down[k];
            steps += 1;
        }
        const zh = c.zc[hd];
        let zfl = Math.max(elaF - below, zh - depthMax);
        let lip = hd;
        steps = 0;
        while (steps < Math.max(3, Math.trunc((1.5 * Ra) / cell)) && down[lip] >= 0) {
            lip = down[lip];
            steps += 1;
        }
        zfl = Math.max(zfl, c.zf[lip] + c.fill[lip] - tarn);
        if (zfl > zh - 20.0) continue;
        let ox, oy, zCrest;
        if (chain) {
            const t = slot.get(hd), m = Math.min(Math.trunc((3.0 * Ra) / cell), K);
            const cc = chain[t * (K + 1) + m];
            const dj = Math.floor(cc / n1), di = cc - dj * n1;
            ox = level.x0 + (di + 0.5) * cell;
            oy = level.y0 + (dj + 0.5) * cell;
            zCrest = chainZ[t * (K + 1) + m];
        } else {
            ox = c.x[hd];
            oy = c.y[hd];
            zCrest = null;
        }
        let vx = c.x[k] - ox, vy = c.y[k] - oy;
        const L = Math.hypot(vx, vy);
        if (L < 1e-6) continue;
        vx /= L;
        vy /= L;
        let cx, cy, Hc;
        if (zCrest !== null && zCrest > zh) {
            cx = ox + 0.85 * Ra * vx;
            cy = oy + 0.85 * Ra * vy;
            Hc = Math.max((zCrest + room - zfl) / t85, headwall);
        } else {
            cx = ox + 0.35 * Rr * vx;
            cy = oy + 0.35 * Rr * vy;
            Hc = headwall + (zh - zfl);
        }
        if (out.some((o) => Math.hypot(cx - o[0], cy - o[1]) < spacing * 0.5 * (Rr + o[6]))) continue;
        const p3 = rng.uniform(0, 2 * Math.PI), p5 = rng.uniform(0, 2 * Math.PI), amp = lobes * rng.uniform(0.6, 1.4);
        out.push([cx, cy, zfl, Hc, vx, vy, Rr, Ra, p3, p5, amp]);
        if (out.length >= MAX_CIRQUES) break;
    }
    return out;
}

/** glacial.py cirque_texture(cq, level): (3, max(N, 1)) rgba32f: row 0 (cx, cy, z_floor, H_c) from the level's
 * corner, row 1 (dir_x, dir_y, R_across, R_along), row 2 (the phases, the amplitude, 0). */
export function cirqueTexture(R, cq, level) {
    const n = Math.max(cq.length, 1);
    const a = new Float32Array(3 * n * 4);
    for (let k = 0; k < n; k++) {
        a[4 * (n + k)] = 1.0;
        a[4 * (n + k) + 2] = 1.0;
        a[4 * (n + k) + 3] = 1.0;
    }
    cq.forEach((r, k) => {
        a.set([r[0] - level.x0, r[1] - level.y0, r[2], r[3]], 4 * k);
        a.set([r[4], r[5], r[6], r[7]], 4 * (n + k));
        a.set([r[8], r[9], r[10], 0.0], 4 * (2 * n + k));
    });
    return R.field(3, n, 4, a);
}


// ============================================================================================ the textures ===

/** glacial.py seed_textures(cl, level): { cand0, seedA, seedB, seedC, streams (glacial_streams: each seed cell's
 * stream id, -1 elsewhere) }, rgba32f fields of the level's grid (r32f streams). */
export function seedTextures(R, cl, level, shoulderCut) {
    const n = level.n;
    const out = { cand0: R.field(n, n, 4), seedA: R.field(n, n, 4), seedB: R.field(n, n, 4), seedC: R.field(n, n, 4),
        streams: R.field(n, n, 1) };
    R.run(kernelOf(R, 'glacial/seed_tex'), { pos: cl.st.pos, V: cl.V, P: cl.Pz, E: cl.E, fill: cl.fill, sid: cl.st.sid },
        { cand0: out.cand0, seedA: out.seedA, seedB: out.seedB, seedC: out.seedC, outG: out.streams }, { uShCut: Number(shoulderCut) });
    return out;
}

/** Every jump-flooding pass (glacial.py jump_flood_run): the final candidates' field (a new one; the inputs are
 * kept). profU: profileUniforms(). */
export function jumpFloodRun(R, cand0, seedA, seedB, cell, profU, steps, metric = 0, seedC = null) {
    const own = seedC ? null : defaultSeedC(R, cand0.h, cand0.w);
    const sc = seedC ?? own;
    const pair = R.pair(cand0.h, cand0.w, 4);
    R.copy(cand0, pair.src);
    const k = kernelOf(R, 'jump_flood');
    for (const step of steps) {
        R.run(k, { candT: pair.src, seedA, seedB, seedC: sc }, { outC: pair.dst },
            { ...profU, uStep: Math.trunc(step), uDx: Number(cell), uMetric: Math.trunc(metric) });
        pair.swap();
    }
    pair.dst.destroy();
    if (own) own.destroy();
    return pair.src;
}

/** default_seed_c: (1, 1, 0, 0) everywhere. */
export function defaultSeedC(R, h, w) {
    const a = new Float32Array(h * w * 4);
    for (let i = 0; i < h * w; i++) {
        a[4 * i] = 1.0;
        a[4 * i + 1] = 1.0;
    }
    return R.field(h, w, 4, a);
}


// ================================================================================================ the uplift ===

export const HORSESHOE = Object.freeze({ kind: 'horseshoe', centre: [0.0, 0.0], azimuth_deg: 0.0, crest_offset_m: 7500.0,
    crest_length_m: 26000.0, crest_width_m: 9000.0, side_offset_m: 5200.0, side_shift_m: 1500.0,
    side_length_m: 17000.0, side_width_m: 5200.0, side_height: 0.8, join: 0.12, texture: 0.3 });

/** A crest across a valley's head and two side ridges along it (core/compose.js ridges, joined by smooth maximum),
 * about 0..1 (glacial.py horseshoe). A new field of the level's cells. */
export function horseshoe(R, spec, level, seed) {
    const s = { ...HORSESHOE, ...spec };
    const [cx, cy] = s.centre.map(Number);
    const az = Number(s.azimuth_deg) * DEG;
    const dn = [Math.sin(az), Math.cos(az)];           // down the valley
    const ac = [Math.cos(az), -Math.sin(az)];          // across it (to the right looking down-valley)
    const co = Number(s.crest_offset_m);
    const crest = { kind: 'ridge', centre: [cx - co * dn[0], cy - co * dn[1]], azimuth_deg: az * RAD + 90.0,
        length_m: Number(s.crest_length_m), width_m: Number(s.crest_width_m), spurs: 0, texture: Number(s.texture), seed: 1 };
    let f = C.uplift(R, crest, level, seed);
    const so = Number(s.side_offset_m), sh = Number(s.side_shift_m);
    [-1.0, 1.0].forEach((side, k) => {
        const ridge = { kind: 'ridge', centre: [cx + side * so * ac[0] - sh * dn[0], cy + side * so * ac[1] - sh * dn[1]],
            azimuth_deg: az * RAD, length_m: Number(s.side_length_m), width_m: Number(s.side_width_m), spurs: 0,
            texture: Number(s.texture), seed: 2 + k };
        const r = C.uplift(R, ridge, level, seed);
        const rs = Gd.arith(R, 'scale', r, null, { amp: Number(s.side_height) });
        const g = C.smoothMax(f, rs, Number(s.join));
        destroyAll(r, rs, f);
        f = g;
    });
    const out = HS.ew(R, HS.EW.MAX_K, f, null, null, 0.0);
    f.destroy();
    return out;
}

/** The valley's uplift shape (glacial.py uplift_shape): a horseshoe, or a core/compose.js uplift. A new field. */
export function upliftShape(R, spec, level, seed) {
    if (spec.kind === 'horseshoe') return horseshoe(R, spec, level, seed);
    return C.uplift(R, spec, level, seed);
}

// the pre-glacial trunk river of a horseshoe (its 'trunk' entry): glacial.py's TRUNK (see trunkCourse)
export const TRUNK = Object.freeze({ head: 0.85, width_m: 60.0, wiggle_m: 300.0, wiggle_wavelength_m: 6000.0, grade: 0.012,
    bench_m: 550.0, taper_m: 8000.0, head_rise_m: 500.0, head_length_m: 1000.0, outlet_m: 0.0, step_m: 20.0 });

async function rivers() {
    try {
        return await import('./rivers.js');
    } catch (e) {
        throw new Error("glacial: the horseshoe's trunk river needs solvers/rivers.js (the layered-rock and rivers " +
            `package's port of rivers.py: arc_length, _smooth_noise_1d, channel), which did not load: ${e.message}`);
    }
}

const pick = (mod, ...names) => {
    for (const n of names) if (typeof mod[n] === 'function') return mod[n];
    throw new Error(`glacial: solvers/rivers.js has none of ${names.join(', ')}`);
};

/** glacial.py trunk_course(spec, window, seed): the trunk river of a horseshoe spec with a 'trunk' entry: { points
 * (N x [x, y], world metres from the head down the valley past the window's edge), s (arc length), bed (the channel's
 * height there, relative h), width_m, spec } in doubles; null without a trunk. window: the coarsest level's
 * [x0, y0, side]. */
export async function trunkCourse(spec, window, seed) {
    const s_ = { ...HORSESHOE, ...spec };
    if (!FL.truthy(s_.trunk)) return null;
    const RV = await rivers();
    const arcLength = pick(RV, 'arcLength', 'arc_length');
    const smooth1d = pick(RV, '_smooth_noise_1d', 'smoothNoise1d', 'smoothNoise1D');
    const tr = { ...TRUNK, ...(s_.trunk && typeof s_.trunk === 'object' ? s_.trunk : {}) };
    const [cx, cy] = s_.centre.map(Number);
    const az = Number(s_.azimuth_deg) * DEG;
    const dn = [Math.sin(az), Math.cos(az)], ac = [Math.cos(az), -Math.sin(az)];
    const [x0, y0, side] = window.map(Number);
    // the distance from the centre down-valley to the window's edge
    const tx = Math.abs(dn[0]) > 1e-9 ? (dn[0] > 0 ? x0 + side - cx : x0 - cx) / dn[0] : Infinity;
    const ty = Math.abs(dn[1]) > 1e-9 ? (dn[1] > 0 ? y0 + side - cy : y0 - cy) / dn[1] : Infinity;
    const tEdge = Math.min(tx, ty);
    const head = Number(tr.head) * Number(s_.crest_offset_m);
    const stop = head + tEdge + 0.1 * side, step = Number(tr.step_m);
    const count = Math.max(Math.ceil(stop / step), 0);                  // np.arange(0, stop, step)
    const u = Float64Array.from({ length: count }, (_, i) => i * step);
    const lat = smooth1d(u, Number(tr.wiggle_wavelength_m), Math.trunc(seed) * 13 + 77);
    const pts = [];
    for (let i = 0; i < count; i++) {
        const l = Number(tr.wiggle_m) * lat[i];
        pts.push([cx - head * dn[0] + u[i] * dn[0] + l * ac[0], cy - head * dn[1] + u[i] * dn[1] + l * ac[1]]);
    }
    const s = arcLength(pts);
    const uEdge = head + tEdge;
    const bed = new Float64Array(count);
    for (let i = 0; i < count; i++) {
        const left = Math.max(uEdge - u[i], 0.0);
        const q = Math.min(Math.max(left / Math.max(Number(tr.taper_m), 1.0), 0.0), 1.0);
        bed[i] = Number(tr.outlet_m) + Number(tr.grade) * left + Number(tr.bench_m) * q * q * (3.0 - 2.0 * q) +
            Number(tr.head_rise_m) * Math.exp(-u[i] / Math.max(Number(tr.head_length_m), 1.0));
    }
    return { points: pts, s: Float64Array.from(s), bed, width_m: Number(tr.width_m), spec: tr };
}

/** glacial.py trunk_pins(course, level, base_pins): basePins ({ pin_w, pin_h, A_in, qs_in } fields) with the trunk's
 * channel cells (rivers.channel) held at its bed, np.interp(s, course s, course bed). [pins (new pin_w and pin_h;
 * A_in and qs_in the base's), m (the channel, r32f 1 / 0)].
 * solvers/rivers.js keeps each channel cell's arc length as its nearest segment k and the parameter t along it
 * (s = s_k + t L_k), and its bed kernel (kernels/strata/river_pins.wgsl) evaluates a bed given at the course's points
 * linearly along each segment (its table mode, the replaced final bed): np.interp of a table at the course's own arc
 * lengths is exactly that, so the trunk's bed is that kernel with the course's bed as the table (no top, no pools). */
export async function trunkPins(R, course, level, basePins) {
    const RV = await rivers();
    const channel = pick(RV, 'channel');
    const ch = await channel(level, course.points, course.width_m, RV.MIN_CELLS, R);
    const N = course.points.length;
    const tab = new Float32Array(8 * N);
    for (let k = 0; k < N; k++) {
        const p = course.points;
        const L = k + 1 < N ? Math.sqrt(Math.max((p[k + 1][0] - p[k][0]) ** 2 + (p[k + 1][1] - p[k][1]) ** 2, 1e-12)) : 0.0;
        tab.set([0.0, course.bed[k], 0.0, L, 0.0, 0.0, 0.0, 0.0], 8 * k);
    }
    const crs = R.field(1, 2 * N, 4, tab), D = standins(R);
    const w = R.field(level.n, level.n, 1), ph = R.field(level.n, level.n, 1);
    R.run(kernelOf(R, 'strata/river_pins'), { mask: ch.mask, segk: ch.seg, segt: ch.t, bw: basePins.pin_w, bh: basePins.pin_h,
        hold: D.f1, crs, cw: D.f2 }, { outW: w, outH: ph },
    { uF: 1.0, uDepth: 0.0, uRiffle: 0.0, uNc: 0, uMode: [1, 0, 0, 0] });
    destroyAll(crs, ch.seg, ch.t, ch.d);
    return [{ ...basePins, pin_w: w, pin_h: ph }, ch.mask];
}

export const MASK_FIELDS = Object.freeze(['ice', 'trough', 'trough_floor', 'trough_wall', 'carve', 'valley_fill', 'trough_rho']);
export const MASK_START = Object.freeze({ trough_rho: 10.0 });     // far from any trough until the carve writes it
// the trough's cross-section per cell, from the best seed there (profileFields): what every finer level evaluates
// the walls at its own cells from (sharpenWalls)
export const PROFILE_FIELDS = Object.freeze(['trough_zf', 'trough_H', 'trough_ff', 'trough_fill', 'trough_rise', 'trough_sharp']);

/** glacial.py profile_fields(cand, seedA, seedB, seedC, rho, cell, prof_u, join_m): { trough_zf, trough_H,
 * trough_ff, trough_fill, trough_rise, trough_sharp }, new r32f fields. */
export function profileFields(R, cand, seedA, seedB, seedC, rho, cell, profU, joinM) {
    const n = [cand.h, cand.w];
    const out = {};
    for (const k of PROFILE_FIELDS) out[k] = R.field(n[0], n[1], 1);
    R.run(kernelOf(R, 'glacial/profile_fields'), { cand, seedA, seedB, seedC, rho },
        { outZf: out.trough_zf, outH: out.trough_H, outFf: out.trough_ff, outFill: out.trough_fill,
            outRise: out.trough_rise, outSharp: out.trough_sharp }, { ...profU, uDx: Number(cell), uJoin: Number(joinM) });
    return out;
}

const PINS_MADE = new WeakMap();                       // ctx.shared -> the trunk pins valley_uplift made last

/** Stage 'valley_uplift' (glacial.py op_valley_uplift): U (m/yr) on the coarsest level's passes, normalised by the
 * shape's peak on its first pass; on a fresh level the start surface and zero glacial masks. */
export async function opValleyUplift(fields, level, params, seed = 0, ctx = null) {
    ctx = await FL.asContext(ctx, fields, level);
    const R = ctx.device ?? fields.R;
    const spec = { ...(params.shape ?? HORSESHOE) };
    const s = Math.trunc(seed) + Math.trunc(Number(params.seed ?? 0));
    for (const k of MASK_FIELDS) if (!(k in fields)) fields[k] = MASK_START[k] ?? 0.0;
    if (ctx.role !== 'grow') return fields;
    const u = upliftShape(R, spec, level, s);
    let course = null;
    if (spec.kind === 'horseshoe' && FL.truthy(spec.trunk)) {
        // the trunk river (the coarsest level's window decides where its bed reaches outlet_m; the pre-passes share
        // it, so every pass pins the same river)
        const top = ctx.plan && ctx.plan.length ? ctx.plan[0] : level;
        course = await trunkCourse(spec, [top.x0, top.y0, top.side], s);
    }
    const sh = (ctx.shared.valley_uplift ??= {});
    if (!('peak' in sh)) Object.assign(sh, { peak: (await prims(R).stats(u)).max, spec, seed: s, U: Number(params.U_m_per_yr ?? 3e-3) });
    fields.U = HS.ew(R, HS.EW.SCALE_DIV, u, null, null, sh.U, Math.max(sh.peak, 1e-12));
    if (ctx.fresh) {
        const size = Number(spec.crest_length_m ?? spec.radius_m ?? Number(spec.length_m ?? 10000.0) * 0.5);
        const nz = FL.field({ kind: 'fbm', wavelength_m: 0.3 * size, octaves: 5 }, level, s + 31, R);
        const n = Gd.arith(R, 'affine', nz, null, { amp: 1.5, off: 0.5 });
        nz.destroy();
        const r = Number(params.start_roughness ?? 0.4);
        const h0 = R.field(level.n, level.n, 1);
        R.run('compose/start', { shape: u, rough: n }, { outF: h0 },
            { uHeight: Number(params.start_m ?? 600.0), uPeak: Math.max(sh.peak, 1e-9), uRough: r });
        n.destroy();
        fields.h = h0;
        const b0 = R.like(h0);
        R.copy(h0, b0);
        fields.bed = b0;
    }
    u.destroy();
    if (course !== null) {
        // the trunk river as base level on this pass
        // the fields this op made for the previous pass's pins are released now (that pass's stages are done with
        // them); pins the runner gave (a child level's) stay the runner's
        const own = !ctx.pins;
        const base = ctx.pins ?? FL.edgePins(R, level.n, fields.h, ctx.sea_level);
        const made = PINS_MADE.get(ctx.shared);
        if (made) destroyAll(...made.filter((f) => !Object.values(base).includes(f)));
        const [pins, m] = await trunkPins(R, course, level, base);
        if (own) destroyAll(base.pin_w, base.pin_h);
        PINS_MADE.set(ctx.shared, own ? [pins.pin_w, pins.pin_h, pins.A_in, pins.qs_in] : [pins.pin_w, pins.pin_h]);
        ctx.pins = pins;
        fields.trunk = m;
        if ((ctx.prepass === null || ctx.prepass === 0) && ctx.fresh) {
            const cells = (await prims(R).stats(m)).nonzero;
            ctx.log(`[terrain.glacial] trunk river ${pyFormat(course.s[course.s.length - 1] / 1000, '.1f')} km from the valley ` +
                `head, bed ${pyFormat(course.bed[0], '.0f')} .. ${pyFormat(course.bed[course.bed.length - 1], '.0f')} m, ${cells} cells on ${level.n}^2`);
        }
    }
    return fields;
}
opValleyUplift.evolves = true;
opValleyUplift.takesCtx = true;


// =================================================================================================== the carve ===

/** The fresh walls' unit noise (glacial.py _wall_sc's ln without the flutes): wall_noise x the unit noise at the wall
 * scales the level resolves, or null. */
function wallNoise(level, params, seed, R) {
    const sc = FL.scales(_p(params, 'wall_scales_m'), level.cell, 3.0);
    const a = Number(_p(params, 'wall_noise'));
    return a > 0 && sc.length ? FL.unitNoise(sc, level, seed, R, 601) : null;
}

/** glacial.py wall_flutes(h, level, params, seed): ln-tangent offsets of the walls' threshold that run down the fall
 * line, at the flute scales the level resolves at 3 cells or more; 0 where none is resolved. opts.rock: { amp, deg,
 * slope } gives refine_level's range flutes (times rock_flutes smoothstep((slope - deg) / 8)). A new field. */
export async function wallFlutes(h, level, params, seed, R = null, opts = {}) {
    R = R ?? h.runner;
    const n = level.n, D = standins(R);
    const weak = Number(_p(params, 'flute_weak')), strong = Number(_p(params, 'flute_strong'));
    const scales = _p(params, 'flute_scales_m').map(Number).filter((x) => x >= 3.0 * level.cell);
    if (!scales.length || (weak <= 0 && strong <= 0)) return Gd.fill(R, [n, n], 0.0);
    const stretch = Number(_p(params, 'flute_stretch'));
    const { dx, dy } = DT.flowDirection(h, level.cell, Math.max(...scales));
    const k = kernelOf(R, 'glacial/flutes');
    const theta = R.field(n, n, 1), counts = R.field(1, 8, 1, null, 'u32');
    const base = { uK: 0, uOrigin: [level.x0, level.y0], uCell: Number(level.cell), uTa: [0, 0], uGa: [0, 0],
        uStretch: stretch, uNorm: 1.0, uWeak: weak, uStrong: strong, uRock: 0, uRockAmp: 0.0, uRockDeg: 0.0 };
    R.clear(counts);
    R.run(k, { dx, dy, theta: D.f1, nk: D.f2, acc: D.f3, slope: D.f4 }, { outA: theta, outD: D.g2, counts }, { ...base, uMode: 0 }, cover(theta));
    destroyAll(dx, dy);
    const any = await R.readRange(counts, 0, 8);
    counts.destroy();
    const spec = { kind: 'sum', terms: scales.map((lam, i) => ({ kind: 'ridged', wavelength_m: lam, octaves: 1, seed: 9100 + i,
        amp: 0.6 ** i })) };
    const norm = scales.reduce((t, _, i) => t + 0.6 ** i, 0);
    const step = Math.PI / FLUTE_ORIENTATIONS;
    const total = R.pair(n, n, 1);
    const disp = R.field(n, n, 2);
    for (let o = 0; o < FLUTE_ORIENTATIONS; o++) {
        if (!any[o]) continue;
        const a = o * step;
        const ga = [Math.cos(a), Math.sin(a)], ta = [-Math.sin(a), Math.cos(a)];
        R.run(k, { dx: D.f1, dy: D.f2, theta: D.f3, nk: D.f4, acc: D.f5, slope: D.f6 }, { outA: D.f7, outD: disp, counts: D.u1 },
            { ...base, uMode: 1, uK: o, uTa: ta, uGa: ga }, cover(disp));
        const nk = N.fieldGpu(R, spec, level, Math.trunc(seed) + 31 * o, { disp });
        R.run(k, { dx: D.f1, dy: D.f2, theta, nk, acc: total.src, slope: D.f6 }, { outA: total.dst, outD: D.g2, counts: D.u1 },
            { ...base, uMode: 2, uK: o }, cover(theta));
        total.swap();
        nk.destroy();
    }
    disp.destroy();
    theta.destroy();
    const out = total.dst;
    const rock = opts.rock ?? null;
    R.run(k, { dx: D.f1, dy: D.f2, theta: D.f3, nk: total.src, acc: D.f5, slope: rock ? rock.slope : D.f6 },
        { outA: out, outD: D.g2, counts: D.u1 },
        { ...base, uMode: 3, uNorm: norm, uRock: rock ? 1 : 0, uRockAmp: rock ? Number(rock.amp) : 0.0, uRockDeg: rock ? Number(rock.deg) : 0.0 },
        cover(out));
    total.src.destroy();
    return out;
}

/** glacial.py _walls: the threshold pass with Sc on the level (the layers counted: losses wear rock, gains are
 * talus), solvers/hillslope.js Pass. */
function walls(R, fields, level, Sc, pins, iters, rate) {
    const run = new HS.Pass(R, fields, Sc, pins);
    for (let i = 0; i < Math.trunc(iters); i++) run.threshold(level.cell, rate, false, PINNED);
    run.write(fields, 'bed' in fields);
}

/** The carve on the coarsest level (glacial.py carve_level, the module doc's steps 1-7). A record. */
export async function carveLevel(fields, level, params, seed, ctx, R) {
    const t0 = now();
    const P = prims(R), D = standins(R);
    const cell = Number(level.cell), n = level.n;
    const base = Number(ctx.base_elevation_m || 0.0);
    const h = fields.h;
    const hadBed = 'bed' in fields;
    // 1. the ice discharge and the D8 drainage area on the lake-filled surface, flats crossed toward their outlets
    const { recv, filled } = await drainageReceivers(h, cell, ctx.sea_level);
    const b = massBalance(h, base, params, ctx.sea_level);
    const pIce = Number(_p(params, 'p_ice'));
    const ones = Gd.fill(R, [n, n], 1.0);
    const Qr = await iceFluxConverge(R, filled, b, cell, { recv, pIce, params });
    const Ar = await iceFluxConverge(R, filled, ones, cell, { recv, pIce, params: { ...(params ?? {}), ice_width_m: 0.0 } });
    destroyAll(b, ones);
    const Q = Qr.Q, A = Ar.Q;
    const t1 = now();
    // 2-3. the centrelines and cirques
    const cl = await centrelines(R, h, Q, A, recv, level, ctx.main, params, base, seed);
    let cq = [];
    if (cl) {
        const up = bestDonor(recv, A);
        cq = await cirques(R, cl, params, base, level, h, up, seed);
        up.destroy();
    }
    const qs = await P.stats(Q);
    const rec = { level: String(level), ice_iterations: Qr.iterations, area_iterations: Ar.iterations,
        glaciated_frac: qs.nonzero / (n * n), Q_max: qs.max, Q_ref: cl ? cl.Q_ref : null, seeds: cl ? cl.S : 0,
        streams: cl ? cl.st.nstreams : 0, cirques: cq.length, trunk: cl ? { W: cl.Wt, H: cl.Ht, d: cl.dt } : null };
    destroyAll(recv, filled, A);
    fields.ice_q = Q;
    if (!cl && !cq.length) {
        fields.glacial_streams = -1.0;
        ctx.log(`[terrain.glacial] ${level}: no glaciated centreline (ELA ${pyFormat(Number(_p(params, 'ela_m')), 'g')} m, the ` +
            `range reaches ${pyFormat((await P.stats(h)).max + base, '.0f')} m): nothing carved`);
        Object.assign(rec, { seconds: round2(now() - t0), carved: false });
        return rec;
    }
    // 4. the jump flood
    const tex = seedTextures(R, cl, level, Number(_p(params, 'shoulder_cut')));
    fields.glacial_streams = tex.streams;
    const pu = profileUniforms(params), cu = carveUniforms(params);
    const wmax = cl.wmax;
    // the jump reaches past the shoulders: the target can lie under the surface out to the trimline, and the cap and
    // the shoulder cut reach their own widths beyond the lip
    const reach = 1.0 + Math.max(1.0 + 2.0 * pu.uShW, cu.uCutW, cu.uShCutW);
    const steps = jfaSteps((reach * wmax) / cell, n);
    const cT = jumpFloodRun(R, tex.cand0, tex.seedA, tex.seedB, cell, pu, steps, 0, tex.seedC);
    const t2 = now();
    // 5. the U-carve. Only the grid's edge (and the sea) is held: the trunk river's pins (valley_uplift) belong to
    // the river the ice replaces; held, they would stand its channel up as a ridge on the trough's floor
    const ownPins = ctx.role === 'grow' || !ctx.pins;
    const pins = ownPins ? FL.edgePins(R, n, h, ctx.sea_level) : ctx.pins;
    const bed0 = hadBed ? fields.bed : h;
    const st = R.pack({ h, bed: bed0 }, ['h', 'bed', null, null]);
    const cqT = cirqueTexture(R, cq, level);
    const pinT = R.pack(pins, ['pin_w', 'pin_h', null, null]);
    const oS = R.field(n, n, 4), oM = R.field(n, n, 4);
    R.run(kernelOf(R, 'u_carve'), { candT: cT, seedA: tex.seedA, seedB: tex.seedB, seedC: tex.seedC, st, cirq: cqT, pin: pinT },
        { outS: oS, outM: oM },
        { ...cu, uDx: cell, uJoin: Number(_p(params, 'join_m')), uTrim: Number(_p(params, 'trim_m')),
            uMorAt: moraineAt(params), uMorW: Number(_p(params, 'moraine_width')), uNCirq: cq.length,
            uCirqExp: Number(_p(params, 'cirque_exp')), uCirqFloor: Number(_p(params, 'cirque_floor_frac')),
            uCirqOpen: Number(_p(params, 'cirque_open')),
            uCirqTilt: Math.tan(Number(_p(params, 'cirque_tilt_deg')) * DEG), uBound: PINNED });
    destroyAll(st, cqT, pinT);
    // the layers: the carve takes the loose cover first, then rock; the fill on the floor is the old valley fill
    // (valley_fill, m), not `deposit` (today's river gravel); the rock the ice took counts as wear only where no fill
    // buries it
    const lay = { W: R.field(n, n, 1), D: R.field(n, n, 1), T: R.field(n, n, 1), V: R.field(n, n, 1) };
    const fl = (k, d) => (k in fields ? fields[k] : d);
    R.run(kernelOf(R, 'glacial/layers'), { h, bed: bed0, S: oS, M: oM, wear: fl('wear', D.f1), dep: fl('deposit', D.f2),
        tal: fl('talus', D.f3), vf: fl('valley_fill', D.f4) }, { outW: lay.W, outD: lay.D, outT: lay.T, outV: lay.V },
    { uHas: ['wear', 'deposit', 'talus', 'valley_fill'].map((k) => (k in fields ? 1 : 0)) });
    const s4 = R.unpack(oS, ['h', 'bed', 'trough_rho', 'ice']);
    const m4 = R.unpack(oM, ['carve', 'trough_floor', 'trough_wall', 'trough']);
    // the cross-section per cell, for the finer levels' walls (sharpenWalls): from the candidates and u_carve's rho
    const pf = profileFields(R, cT, tex.seedA, tex.seedB, tex.seedC, s4.trough_rho, cell, pu, Number(_p(params, 'join_m')));
    const carveMax = (await P.stats(oM, { channel: 0 })).max;
    const inT = Gd.arith(R, 'affine', m4.trough, null, { amp: 1.0, off: -0.5 });
    const cin = await P.stats(oM, { channel: 0, mask: inT });
    const tfrac = (await P.stats(m4.trough)).mean;
    inT.destroy();
    destroyAll(cT, tex.cand0, tex.seedA, tex.seedB, tex.seedC, oS, oM);
    cl.dispose();
    fields.h = s4.h;
    fields.bed = s4.bed;
    fields.wear = lay.W;
    fields.deposit = lay.D;
    fields.talus = lay.T;
    fields.valley_fill = lay.V;
    fields.ice = s4.ice;
    fields.trough_rho = s4.trough_rho;
    fields.trough_floor = m4.trough_floor;
    fields.trough_wall = m4.trough_wall;
    fields.trough = m4.trough;
    fields.carve = m4.carve;
    fields.update(pf);
    // 6. the fresh walls: steep in the trough and the cirques, the range's own threshold outside
    const noise = wallNoise(level, params, seed, R);
    const Sc = R.field(n, n, 1);
    R.run(kernelOf(R, 'glacial/sc_mix'), { wall: fields.trough_wall, trough: D.f1, sc: 'Sc' in fields ? fields.Sc : D.f2,
        noise: noise ?? D.f3, fl: D.f4, rf: D.f5, gx: D.f6, gy: D.f7 }, { outS: Sc },
    { uMode: 0, uTanWall: Math.tan(Number(_p(params, 'wall_deg')) * DEG), uNoiseAmp: Number(_p(params, 'wall_noise')),
        uHasNoise: noise ? 1 : 0, uHasSc: 'Sc' in fields ? 1 : 0, uTan35: Math.tan(35.0 * DEG), uMedian: 0.0, uIn: 0.0, uOut: 0.0 });
    if (noise) noise.destroy();
    walls(R, fields, level, Sc, pins, _p(params, 'wall_iters'), Number(_p(params, 'wall_rate')));
    fields.Sc = Sc;
    if (ownPins) destroyAll(pins.pin_w, pins.pin_h, pins.A_in, pins.qs_in);
    ctx.evolved = true;
    const t3 = now();
    Object.assign(rec, { carved: true, jfa_steps: steps, carve_max_m: carveMax, carve_mean_in_trough_m: cin.count ? cin.mean : 0.0,
        trough_frac: tfrac, seconds: { ice: round2(t1 - t0), jfa: round2(t2 - t1), carve_walls: round2(t3 - t2) } });
    return rec;
}

/** A finer level's walls at its own resolution (glacial.py sharpen_walls): h += w (T_own - upsample(T_parent)), the
 * bedrock likewise. Returns the largest change (m), 0 when the level has no cross-section. */
export async function sharpenWalls(fields, level, params, pinW = null) {
    if (PROFILE_FIELDS.some((k) => !(k in fields)) || !('trough_rho' in fields)) return 0.0;
    const n0 = fields.h.h, n1 = fields.h.w;
    if (n0 % 2 || n1 % 2) return 0.0;
    const R = fields.h.runner, D = standins(R);
    const pu = profileUniforms(params);
    const k = kernelOf(R, 'glacial/sharpen');
    const arg = ['trough_rho', 'trough_zf', 'trough_H', 'trough_ff', 'trough_fill', 'trough_rise'];
    const cp = arg.map((a) => Gd.boxDown(fields[a], 2));
    const target = (src, rows, cols) => {
        const t = R.field(rows, cols, 1), r = R.field(rows, cols, 1);
        R.run(k, { rho: src[0], zf: src[1], H: src[2], ff: src[3], fill: src[4], rise: src[5], to: D.f1, tp: D.f2, ro: D.f3, rp: D.f4 },
            { outA: t, outB: r, outC: D.f5 }, { ...pu, uMode: 0, uHasCarve: 0, uHasPin: 0, uHasBed: 0 });
        return [t, r];
    };
    const [tOwn, rOwn] = target(arg.map((a) => fields[a]), n0, n1);
    const [tc, rc] = target(cp, n0 / 2, n1 / 2);
    const tPar = Gd.cropUpsample2(tc, 0, 0, n1 / 2, 'catmull', n0 / 2);
    const rPar = Gd.cropUpsample2(rc, 0, 0, n1 / 2, 'catmull', n0 / 2);
    destroyAll(...cp, tc, rc);
    const hasBed = 'bed' in fields, hasCarve = 'carve' in fields;
    const h1 = R.field(n0, n1, 1), b1 = hasBed ? R.field(n0, n1, 1) : D.f6, adh = R.field(n0, n1, 1);
    R.run(k, { rho: fields.trough_rho, zf: fields.trough_sharp, H: hasCarve ? fields.carve : D.f1, ff: pinW ?? D.f2, fill: fields.h,
        rise: hasBed ? fields.bed : D.f3, to: tOwn, tp: tPar, ro: rOwn, rp: rPar }, { outA: h1, outB: b1, outC: adh },
    { ...pu, uMode: 1, uHasCarve: hasCarve ? 1 : 0, uHasPin: pinW ? 1 : 0, uHasBed: hasBed ? 1 : 0 });
    destroyAll(tOwn, rOwn, tPar, rPar);
    const mx = (await prims(R).stats(adh)).max;
    adh.destroy();
    fields.h = h1;
    if (hasBed) fields.bed = b1;
    return mx;
}

/** glacial.py lip_open(h, rho, cell, radius_m, lo, hi) and refine_level's use of it: on the lip band the rims come
 * down to the level's morphological opening (a square of radius_m), free of the pinned band. { rim (the largest
 * drop, m), changed } and the fields (h, bed) updated when a rim came down. */
export async function lipOpen(fields, level, radiusM, pinW, lo = 0.9, hi = 1.5) {
    const R = fields.h.runner, P = prims(R), D = standins(R);
    const n0 = fields.h.h, n1 = fields.h.w;
    const r = Math.max(1, Math.trunc(pyRound(Number(radiusM) / Number(level.cell))));
    const k = kernelOf(R, 'glacial/lip');
    const band = R.field(n0, n1, 1);
    R.run(k, { rho: fields.trough_rho, h: D.f1, op: D.f2, band: D.f3, pin: D.f4, bed: D.f5 }, { outA: band, outB: D.f6, outC: D.f7 },
        { uMode: 0, uLo: lo, uHi: hi, uHasBed: 0 });
    if (!(await P.stats(band)).nonzero) {
        band.destroy();
        return { rim: 0.0, changed: false };
    }
    const er = P.dilate(fields.h, r, { min: true });
    const op = P.dilate(er, r);
    er.destroy();
    const hasBed = 'bed' in fields;
    const h1 = R.field(n0, n1, 1), b1 = hasBed ? R.field(n0, n1, 1) : D.f6, fd = R.field(n0, n1, 1);
    R.run(k, { rho: fields.trough_rho, h: fields.h, op, band, pin: pinW ?? D.f4, bed: hasBed ? fields.bed : D.f5 },
        { outA: h1, outB: b1, outC: fd }, { uMode: 1, uLo: lo, uHi: hi, uHasBed: hasBed ? 1 : 0 });
    destroyAll(op, band);
    // numpy's drop.max() > 0 decides on the drop; with the pinned band free of it the drop that moved is free * drop
    const fs = await P.stats(fd);
    fd.destroy();
    if (!(fs.max > 0)) {
        destroyAll(h1, hasBed ? b1 : null);
        return { rim: 0.0, changed: false };
    }
    fields.h = h1;
    if (hasBed) fields.bed = b1;
    return { rim: fs.max, changed: true };
}

/** A finer level (glacial.py refine_level): the walls it inherits sharpened to this level's resolution, keeping their
 * steep threshold, failing at it at this level's scale where the rock is weak. A record. */
export async function refineLevel(fields, level, params, seed, ctx, R) {
    const n = level.n, P = prims(R), D = standins(R);
    if (!('trough' in fields) || !((await P.stats(fields.trough)).max > 0.0)) return { level: String(level), refined: false };
    const k = kernelOf(R, 'glacial/sc_mix');
    const un = { uTanWall: Math.tan(Number(_p(params, 'wall_deg')) * DEG), uNoiseAmp: Number(_p(params, 'wall_noise')),
        uHasNoise: 0, uHasSc: 0, uTan35: Math.tan(35.0 * DEG), uMedian: 0.0, uIn: f32Above(0.02), uOut: f32Below(0.02) };
    const mix = (mode, ins, extra = {}) => {
        const o = R.field(n, n, 1);
        R.run(k, { wall: D.f1, trough: D.f2, sc: D.f3, noise: D.f4, fl: D.f5, rf: D.f6, gx: D.f7, gy: D.f8, ...ins }, { outS: o },
            { ...un, ...extra, uMode: mode });
        return o;
    };
    const outM = mix(4, { trough: fields.trough });
    const nOut = (await P.stats(outM)).nonzero;
    for (const name of ['K', 'G']) {
        if (name in fields && nOut) {
            const med = await P.median(fields[name], { mask: outM, dtype: 'float64' });
            fields[name] = mix(3, { trough: fields.trough, sc: fields[name] }, { uMedian: med });
        }
    }
    let scRange;
    if ('Sc' in fields && nOut) {
        const med = await P.median(fields.Sc, { mask: outM, dtype: 'float64' });
        scRange = mix(3, { trough: fields.trough, sc: fields.Sc }, { uMedian: med });
    } else {
        scRange = Gd.fill(R, [n, n], Math.tan(35.0 * DEG));
    }
    outM.destroy();
    const wallSrc = 'trough_wall' in fields ? fields.trough_wall : fields.trough;
    const ownPins = !ctx.pins;
    const pins = ctx.pins ?? FL.edgePins(R, n, fields.h, ctx.sea_level);
    // the walls at this level's resolution (the upsampling smoothed the parent's cliffs over two of its cells), first:
    // the thresholds below read the surface's own slopes
    const sharp = await sharpenWalls(fields, level, params, pins.pin_w);
    if (sharp > 0.0) ctx.evolved = true;
    const hIn = fields.h;
    const rf = Number(_p(params, 'rock_flutes'));
    let range = null;
    if (rf > 0) {
        // the range's own rock faces carry couloirs and ribs too: the flutes, scaled, on ground steeper than
        // rock_flute_deg
        const slope = Gd.slopeDeg(hIn, level.cell);
        range = await wallFlutes(hIn, level, params, seed + 7, R, { rock: { amp: rf, deg: Number(_p(params, 'rock_flute_deg')), slope } });
        slope.destroy();
    }
    let Sc;
    const noise = wallNoise(level, params, seed, R);
    const base = { uHasNoise: noise ? 1 : 0, uHasSc: 1 };
    const rz = range ?? Gd.fill(R, [n, n], 0.0);
    if (ctx.depth < 0) {
        // a hero level refines without moving the landform: no threshold stands under the slope the level inherits
        // (its parent's walls, cliffs, truncated spurs and headwalls stand), so only the flutes' weak lines and new
        // detail fail
        const { gx, gy } = Gd.gradient(hIn, level.cell);
        const flw = await wallFlutes(hIn, level, params, seed, R);
        Sc = mix(2, { wall: wallSrc, sc: scRange, noise: noise ?? D.f4, fl: flw, rf: rz, gx, gy }, base);
        destroyAll(gx, gy, flw);
    } else {
        const flw = await wallFlutes(hIn, level, params, seed, R);
        Sc = mix(1, { wall: wallSrc, sc: scRange, noise: noise ?? D.f4, fl: flw, rf: rz }, base);
        flw.destroy();
    }
    destroyAll(noise, rz, scRange);
    const iters = Math.trunc(Number(_p(params, 'refine_wall_iters')));
    if (iters > 0) {
        walls(R, fields, level, Sc, pins, iters, Number(_p(params, 'wall_rate')));
        ctx.evolved = true;
    }
    fields.Sc = Sc;
    let rim = 0.0;
    const loM = Number(_p(params, 'lip_open_m'));
    if (loM > 0 && 'trough_rho' in fields) {
        const r = await lipOpen(fields, level, loM, pins.pin_w);
        if (r.changed) {
            rim = r.rim;
            ctx.evolved = true;
        }
    }
    const wcount = await wallCells(R, 'trough_wall' in fields ? fields.trough_wall : fields.trough);
    if (ownPins) destroyAll(pins.pin_w, pins.pin_h, pins.A_in, pins.qs_in);
    return { level: String(level), refined: true, wall_frac: wcount / (n * n), lip_rim_max_m: Number(pyFormat(rim, '.1f')),
        sharpened_max_m: Number(pyFormat(sharp, '.1f')) };
}

// the cells of (wall > 0.5), wall = clip(trough_wall 1.5, 0, 1): those where 1.5 trough_wall - 0.5 > 0 (the record's
// wall_frac)
async function wallCells(R, src) {
    const m = Gd.arith(R, 'affine', src, null, { amp: 1.5, off: -0.5 });
    const s = await prims(R).stats(m, { mask: m });
    m.destroy();
    return s.count;
}

/** Stage 'glacial' (glacial.py op_glacial): the carve on the coarsest level once it is fully grown (after its last
 * coarse-to-fine pass), the walls' refinement below it. */
export async function opGlacial(fields, level, params, seed = 0, ctx = null) {
    ctx = await FL.asContext(ctx, fields, level);
    if (ctx.prepass !== null && ctx.prepass !== undefined) return fields;
    const R = ctx.device ?? fields.R;
    const t0 = now();
    const s = Math.trunc(seed) + Math.trunc(Number(_p(params, 'seed')));
    let carve = ctx.role === 'grow';
    if (!carve && !('ice_q' in fields)) carve = !('trough' in fields) || !((await prims(R).stats(fields.trough)).max > 0.0);
    let rec;
    if (carve) {
        rec = await carveLevel(fields, level, params, s, ctx, R);
        rec.mode = 'carve';
    } else {
        rec = await refineLevel(fields, level, params, s, ctx, R);
        rec.mode = 'refine';
    }
    rec.seconds_total = round2(now() - t0);
    (ctx.shared.glacial_log ??= []).push(rec);
    if (rec.mode === 'carve' && rec.carved) {
        ctx.log(`[terrain.glacial] carve ${level.n}^2 @ ${pyFormat(level.cell, '.3g')} m: Q_ref ${pyFormat(rec.Q_ref, '.3g')} m3/yr, ` +
            `${rec.seeds} seeds in ${rec.streams} streams, ${rec.cirques} cirques, trough ${pyFormat(rec.trough_frac * 100, '.1f')} % of ` +
            `the level, carve max ${pyFormat(rec.carve_max_m, '.0f')} m, ${rec.seconds_total} s`);
    } else if (rec.mode === 'refine') {
        ctx.log(`[terrain.glacial] walls ${level.n}^2 @ ${pyFormat(level.cell, '.3g')} m: ${pyFormat((rec.wall_frac ?? 0) * 100, '.1f')} % ` +
            `wall, ${rec.seconds_total} s`);
    }
    return fields;
}
opGlacial.evolves = true;              // called on every pass of the coarsest level; it acts on the last one only
opGlacial.takesCtx = true;

export const OPS = { glacial: opGlacial, valley_uplift: opValleyUplift };

export {
    _p as p, moraineAt as moraine_at, coreFactor as core_factor, floorFrac as floor_frac, profileUniforms as profile_uniforms,
    carveUniforms as carve_uniforms, jfaSteps as jfa_steps, headTaperFactor as head_taper_factor, d8Receivers as d8_receivers,
    drainageReceivers as drainage_receivers, massBalance as mass_balance, iceFluxConverge as ice_flux_converge,
    smoothAlong as smooth_along, headDistance as head_distance, gradedFill as graded_fill, bestDonor as best_donor,
    cirqueTexture as cirque_texture, seedTextures as seed_textures, jumpFloodRun as jump_flood_run, upliftShape as uplift_shape,
    trunkCourse as trunk_course, trunkPins as trunk_pins, profileFields as profile_fields, sharpenWalls as sharpen_walls,
    wallFlutes as wall_flutes, carveLevel as carve_level, refineLevel as refine_level, lipOpen as lip_open,
    opGlacial as op_glacial, opValleyUplift as op_valley_uplift,
};
