// Port of blender/eidoblend/terrain/solvers/fluvial.py at f90c6fc.
//
// The fluvial backbone (design section 4.1): uplift, stream-power incision, creep, threshold failure and sediment
// deposition, run as compute kernels on a level's fields.
//
//     stage ops (OPS; called by run.js as op(fields, level, params, seed, ctx)):
//       'uplift'    the uplift U (m/yr) from a core/compose.js shape in world space, and on a fresh level the rough
//                   start surface (the shape scaled to start_m, roughened): a flat start makes corduroy for millions
//                   of years. Optional 'regional' (a background of lower ranges or hills over the whole window) and
//                   'tilt' (the uplift rising toward an azimuth): see compositeUplift
//       'valley_floor'  alluvial valley floors (the fill a river lays where it carries more than it can move): every
//                   channel's valley filled flat to the level at which it is as wide as its river's floor, the width
//                   growing with drainage area, tributary mouths backfilled to the trunk's floor (opValleyFloor)
//       'fluvial'   the backbone. On the coarsest level (and its coarse-to-fine pre-passes) it GROWS the range: full
//                   physics for the recipe's age, the relief controller steering U. On every finer level it REFINES:
//                   the level starts as its parent upsampled, its border band is pinned to the parent and fed the
//                   parent's drainage area and sediment flux, and a low-pass lock holds the mean of blocks a few of
//                   the parent's valley spacings wide at their start, so the level adds valleys, ridges, gullies and
//                   rock without moving the landform. Down to the main level the real uplift runs (the lock only
//                   corrects drift); on hero levels the lock is the uplift: it raises exactly what the rivers cut.
//       'incise'    a base-level fall along a river course, run once on the finest growing level (opIncise)
//
// Per step (dt years), as in the design probe: flow_weights -> route_incise -> creep (sub-stepped) -> threshold (2
// iterations) [-> lock]. The kernels are kernels/flow_weights.wgsl (the hydrology package's), route_incise.wgsl,
// creep.wgsl, threshold.wgsl and threshold_excess.wgsl, and the inline kernels of fluvial.py as files of their names
// (PORT_PLAN.md 3.3): h_keep.wgsl, creep_layers.wgsl, lock_restrict.wgsl, lock_apply.wgsl. Their numpy twins stay in
// Python (the oracles, tests/parity/fixtures.py); Blender's twin device has no counterpart here.
//
// Parameters of the 'fluvial' stage: as fluvial.py's (DEFAULTS below, the same names, units and meanings): K, m, n,
// p, slope, valley_spacing_m, D, gullies, threshold_deg, threshold_noise, threshold_scale_m, threshold_gain, breakup,
// k_breakup, breakup_scales_m, outcrops, outcrop_scale_m, roughness, roughness_scales_m, k_contrast,
// k_contrast_scales_m, faults, context_spacing_factor, relief_over, U_factor_max, control_levels, uplift_scale,
// lock_max_frac, deposition, age_myr, later_frac, relief_m, relief_calib, dt_ref_yr, refine_steps, lock,
// threshold_mode, threshold_rate, threshold_iters, fill_pits, pit_eps_m, creep_cap, max_creep_sub, mode, min_steps,
// max_steps, and steps (a fixed count). Fields read: h, bed, U, K_factor, Sc_factor, Sc, A, qs, incised. Fields
// written: h, bed, A (one-step lagged; run.js routes it to convergence after the level), qs, wear, deposit, talus, and
// U, K, Sc, G for the masks and later stages.
//
// The dispatch log (PORT_PLAN.md 5.7): every Blender kernel above is dispatched in fluvial.py's order with its
// uniforms computed in doubles as numpy computes them; the relief controller's update (every 100 steps) is the first
// uniform computed from a readback (its U factor reaches route_incise through the par pack, a field, so the uniforms
// themselves stay equal). None of the Blender kernels here runs in a loop that stops on a convergence test.
//
// Where this differs from fluvial.py, and why (PORT_PLAN.md 2.4, 3.2: every per-cell step runs on the GPU):
//   - Fields are core/gpu.js fields; the ops are async (the relief controller reads two order statistics back every
//     100 steps, numpy's percentiles of the whole state; a convergence test reads a count).
//   - The numpy code over whole levels is the port's own kernels in kernels/fluvial/, each naming the numpy lines it
//     replaces: the inputs (erodibility.wgsl, threshold_field.wgsl, fault.wgsl, composite.wgsl), the state and the
//     forcing packs (state.wgsl, par.wgsl), the pins and the rigid mask (pins.wgsl), the element-wise steps (ew.wgsl),
//     the lock's targets (block_mean.wgsl: numpy's float64 block means rounded once to float32, from exact sums), the
//     valley floors (vf_*.wgsl). numpy evaluates the inputs in float64 from the GPU's float32 noise; here they are
//     float32 in numpy's order. They are not Blender kernels, so the dispatch-log comparison sets them aside.
//   - The noise fields are core/world_noise.js fieldGpu's (Blender's _field calls field_gpu on the GPU device: the
//     same evaluation).
//   - window_relief and _main_window are run.js's (windowRelief, mainWindow): numpy's float64 percentiles of the main
//     window's float32 heights from exact order statistics. StageContext is run.js's too (the runner makes it), and is
//     re-exported here, as fluvial.py defines it.
//   - asContext(): an op given a plain object (a dumped context, tests/parity/replay.mjs) works on a StageContext of
//     it; the members it sets (evolved, the shared record) reach the caller's object.
//   - Blender's device('gpu' | 'twin') and its Pair / Inline / dummy plumbing are core/gpu.js's runner, pairs and
//     kernels (the twin device is a test device and stays in Python).
//   - Python's round() is core/levels.js pyRound (half to even); its f'{x:g}' formatting is pyFormat.

import * as C from '../core/compose.js';
import * as Gd from '../core/grid.js';
import { pyFormat, pyRound } from '../core/levels.js';
import { prims } from '../core/prims.js';
import * as N from '../core/world_noise.js';
import * as RUN from '../run.js';
import * as HS from './hillslope.js';
import * as HY from './hydro.js';

export { StageContext, windowRelief, mainWindow } from '../run.js';

export const OPEN = 0, PERIODIC = 1, PINNED = 2;
export const CELL_REF_M = 78.0;                    // dt = dt_ref (cell / 78 m): the research's 78 m cells at 1000 yr steps
export const SPACING_RATIO = 26.0;                 // valley spacing / sqrt(D / K), calibrated by the Blender package
export const MIN_SPACING_CELLS = 5.0;              // a level resolves valleys at least this many cells apart
export const LOCK_SCALE = 2.0;                     // the lock's blocks: 2 of the parent's valley spacings
export const LOCK_PHASES = Object.freeze([[0, 0], [1, 0], [1, 1], [0, 1]]);   // the block grid's offsets by step, half blocks
export const CONTROL_EVERY = 100;                  // the relief controller: every 100 steps U x (target / relief)^0.7,
export const CONTROL_POWER = 0.7;                  // clamped
export const CONTROL_CLAMP = Object.freeze([0.75, 1.33]);

export const DEFAULTS = Object.freeze({
    K: 1.5e-5, m: 0.5, n: 1.0, p: 1.0, slope: 'dinf', valley_spacing_m: 400.0, D: null, gullies: false,
    threshold_deg: 35.0, threshold_noise: 0.15, threshold_scale_m: 400.0, threshold_gain: 0.0,
    breakup: 0.0, k_breakup: 0.0, breakup_scales_m: [60.0, 20.0, 7.0], outcrops: 0.0, outcrop_scale_m: 120.0,
    roughness: 0.6, roughness_scales_m: [2000.0, 300.0, 50.0], deposition: 0.5,
    k_contrast: 0.0, k_contrast_scales_m: [3000.0, 1500.0],
    age_myr: 2.0, later_frac: 0.25, relief_m: null, relief_calib: 1.0, dt_ref_yr: 1000.0, refine_steps: 1500,
    lock: true, creep_cap: 5.0, threshold_iters: 2, threshold_mode: 'iso', threshold_rate: null, max_creep_sub: 32,
    fill_pits: true, pit_eps_m: 1e-3, mode: 'evolve', min_steps: 100, max_steps: 6000,
    faults: null, context_spacing_factor: 1.0, relief_over: 'main', U_factor_max: null,
    uplift_scale: 1.0, control_levels: 'grow', lock_max_frac: 8,
});
export const THRESHOLD_RATE = Object.freeze({ iso: 0.12, pair: 0.06 });

const DEG = Math.PI / 180.0;
const now = () => performance.now() / 1000;
const has = (o, k) => o !== null && o !== undefined && Object.prototype.hasOwnProperty.call(o, k);

/** Python's truth value of a parameter (None, False, 0, '', [] and {} are false). */
export function truthy(v) {
    if (v === null || v === undefined || v === false || v === 0 || v === '') return false;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === 'object') return Object.keys(v).length > 0;
    return true;
}

/** fluvial.py _p: the parameter, or its default when it is missing or None (and the default is not None). */
export function _p(params, key) {
    const d = DEFAULTS[key];
    const v = has(params, key) ? params[key] : d;
    return (v === null || v === undefined) && d !== null ? d : v;
}

/** f'{x:g}' and f'{x:.<d>g}' (the log lines). */
export const pyG = (x) => pyFormat(Number(x), 'g');
export const fmtG = (x, d) => pyFormat(Number(x), `.${d}g`);
/** Python's round(x, n): the exact decimal value rounded half to even (pyFormat's .nf is exact), as the records
 * fluvial.py writes carry it. */
export const pyRoundN = (x, n) => Number(pyFormat(Number(x), `.${n}f`));

function runnerOf(fields, ctx) {
    const R = (ctx && ctx.device) || fields.h?.runner || fields.R;
    if (!R) throw new Error('fluvial: no GPU runner (give the stage context a device, or fields on the GPU)');
    return R;
}


// ======================================================================================== the stage context ===

/** fluvial.py standalone_context: a context for an op called on its own (a test): grow from a fresh level unless h
 * holds something, the level's outer ring pinned to base level. */
export async function standaloneContext(fields, level, R = null) {
    R = R ?? runnerOf(fields, null);
    let fresh = !('h' in fields);
    if (!fresh) fresh = (await prims(R).stats(fields.h)).nonzero === 0;
    return new RUN.StageContext({ plan: [level], index: 0, level, fresh, role: 'grow', device: R,
        pins: edgePins(R, level.n, 'h' in fields ? fields.h : null) });
}

/** A StageContext for an op: ctx itself, a standalone one (null), or one made from a plain object (a dumped context:
 * tests/parity/replay.mjs). For a plain object, the members the op sets (evolved, and its shared record, which is
 * the same object) reach the caller's object when the op sets them through markEvolved(). */
export async function asContext(ctx, fields, level) {
    if (ctx instanceof RUN.StageContext) return ctx;
    if (ctx === null || ctx === undefined) return standaloneContext(fields, level);
    const c = new RUN.StageContext({ ...ctx, shared: ctx.shared ?? (ctx.shared = {}) });
    c.device = ctx.device ?? fields.h?.runner ?? null;
    Object.defineProperty(c, 'evolved', { get: () => ctx.evolved ?? false, set: (v) => { ctx.evolved = v; }, configurable: true });
    return c;
}

/** The coarsest level's pins (fluvial.py edge_pins): its outer ring held at base level (the start's own edge
 * height, normally 0 m), and sea cells (h <= sea_level) held at their height. A_in = qs_in = 0. GPU fields. */
export function edgePins(R, n, h = null, seaLevel = null) {
    const D = Gd.dummies(R);
    const pin_w = R.field(n, n, 1), pin_h = R.field(n, n, 1);
    const sea = seaLevel !== null && seaLevel !== undefined && h !== null;
    R.run('fluvial/pins', { h: h ?? D.f1, a: D.f1, pw: D.f1, ph: D.f1 }, { outW: pin_w, outH: pin_h },
        { uMode: 0, uHasH: h ? 1 : 0, uSea: sea ? 1 : 0, uSea32: sea ? Math.fround(seaLevel) : 0.0, uFlat: 0 });
    return { pin_w, pin_h, A_in: R.field(n, n, 1), qs_in: R.field(n, n, 1) };
}


// ========================================================================= world-space inputs (metres) ===

/** A core/world_noise.js field spec at the level's cell centres, on the GPU (fluvial.py _field). A new field. */
export function field(spec, level, seed, R) {
    return N.fieldGpu(R, spec, level, Math.trunc(seed));
}

/** The scales a level resolves: those at least min_cells cells long. */
export function scales(list, cell, minCells = 4.0) {
    return (list ?? []).map(Number).filter((s) => s >= minCells * cell);
}

/** Unit-variance noise (about N(0, 1)): fbm fields at the given scales, summed with equal weight. A new field. */
export function unitNoise(sc, level, seed, R, baseSeed) {
    const spec = { kind: 'sum', terms: sc.map((s, i) => ({ kind: 'fbm', wavelength_m: s, octaves: 2, seed: baseSeed + i,
        amp: 3.0 / Math.sqrt(sc.length) })) };
    return field(spec, level, seed, R);
}

/** The erodibility factor (>= 1) of fault zones: bands of crushed, weak rock along faults (fluvial.py fault_zones:
 * 1 + (k_factor - 1) exp(-d^2 / 2 width^2) along a sinuous trace, ended by length_m). A new field. */
export function faultZones(faults, level, seed, R) {
    let out = Gd.fill(R, [level.n, level.n], 1.0);
    const D = Gd.dummies(R);
    faults.forEach((f, i) => {
        const az = Number(f.azimuth_deg ?? 90.0) * DEG;
        const [cx, cy] = (f.centre ?? [0.0, 0.0]).map(Number);
        const wan = Number(f.wander_m ?? 0.0);
        const n = wan > 0 ? field({ kind: 'fbm', wavelength_m: Number(f.wander_wavelength_m ?? 8000.0), octaves: 3, amp: 3.0 },
            level, Math.trunc(seed) + 701 + 13 * i, R) : null;
        const next = R.field(level.n, level.n, 1);
        R.run('fluvial/fault', { prev: out, wan: n ?? D.f1 }, { outF: next },
            { uOrigin: [level.x0 - cx, level.y0 - cy], uCell: level.cell, uAxis: [Math.sin(az), Math.cos(az)],
                uOff: Number(f.offset_m ?? 0.0), uWan: wan, uWidth: Math.max(Number(f.width_m ?? 400.0), 1e-6),
                uHalfLen: truthy(f.length_m) ? 0.5 * Number(f.length_m) : 0.0, uK1: Number(f.k_factor ?? 3.0) - 1.0 });
        if (n) n.destroy();
        out.destroy();
        out = next;
    });
    return out;
}

/** K (fluvial.py erodibility, then op_fluvial's K_factor and rigid cells): K0 (1 + roughness n1 / 3) (1 + k_breakup
 * n2 / 3) exp(k_contrast n3) x the fault zones, clamped at 0.2 K0; opts.kFactor and opts.rigid (fields) as op_fluvial
 * applies them. A new field. */
export function erodibility(level, params, seed, R, opts = {}) {
    const D = Gd.dummies(R);
    const K0 = Number(_p(params, 'K'));
    const own = [];
    const a = Number(_p(params, 'roughness'));
    const sc = scales(_p(params, 'roughness_scales_m'), level.cell, 3.0);
    const n1 = a > 0 && sc.length ? unitNoise(sc, level, seed, R, 101) : null;
    const kb = Number(_p(params, 'k_breakup'));
    const sb = scales(_p(params, 'breakup_scales_m'), level.cell);
    const n2 = kb > 0 && sb.length ? unitNoise(sb, level, seed, R, 151) : null;
    const kc = Number(_p(params, 'k_contrast'));
    const scs = scales(_p(params, 'k_contrast_scales_m'), level.cell, 3.0);
    const n3 = kc > 0 && scs.length ? unitNoise(scs, level, seed, R, 181) : null;
    const fz = _p(params, 'faults');
    const fzf = truthy(fz) ? faultZones(fz, level, seed, R) : null;
    for (const f of [n1, n2, n3, fzf]) if (f) own.push(f);
    const out = R.field(level.n, level.n, 1);
    R.run('fluvial/erodibility', { n1: n1 ?? D.f1, n2: n2 ?? D.f1, n3: n3 ?? D.f1, fz: fzf ?? D.f1, kf: opts.kFactor ?? D.f1,
        rig: opts.rigid ?? D.f1 }, { outK: out },
    { uK0: K0, uA3: a / 3.0, uKb3: kb / 3.0, uKc: kc, uHas: [n1 ? 1 : 0, n2 ? 1 : 0, n3 ? 1 : 0, fzf ? 1 : 0],
        uMore: [opts.kFactor ? 1 : 0, opts.rigid ? 1 : 0] });
    for (const f of own) f.destroy();
    return out;
}

/** Sc, tangents (fluvial.py threshold, then op_fluvial's choices): lognormal tan(threshold_deg) exp(threshold_noise
 * n400 + breakup nb), times (1 + outcrops smoothstep(ridged)), times (1 + threshold_gain)^belowMain. opts.from (an
 * earlier stage's Sc field, replacing it), opts.factor (Sc_factor), opts.refineH (mode 'refine': never below 1.1 x the
 * slope of this height field). A new field. */
export function threshold(level, params, seed, R, belowMain = 0, opts = {}) {
    const D = Gd.dummies(R);
    const own = [];
    let nt = null, nb = null, nr = null;
    if (!opts.from) {
        const tn = Number(_p(params, 'threshold_noise')), s0 = Number(_p(params, 'threshold_scale_m'));
        if (tn > 0 && s0 >= 3.0 * level.cell) nt = unitNoise([s0], level, seed, R, 211);
        const b = Number(_p(params, 'breakup')), sc = scales(_p(params, 'breakup_scales_m'), level.cell);
        if (b > 0 && sc.length) nb = unitNoise(sc, level, seed, R, 307);
        const o = Number(_p(params, 'outcrops')), so = Number(_p(params, 'outcrop_scale_m'));
        if (o > 0 && so >= 3.0 * level.cell) nr = field({ kind: 'ridged', wavelength_m: so, octaves: 3, seed: 401 }, level, seed, R);
    }
    let gx = null, gy = null;
    if (opts.refineH) ({ gx, gy } = Gd.gradient(opts.refineH, level.cell));
    for (const f of [nt, nb, nr, gx, gy]) if (f) own.push(f);
    const g = Number(_p(params, 'threshold_gain'));
    const gain = truthy(g) && belowMain > 0;
    const out = R.field(level.n, level.n, 1);
    R.run('fluvial/threshold_field', { nt: nt ?? D.f1, nb: nb ?? D.f1, nr: nr ?? D.f1, sc0: opts.from ?? D.f1,
        scf: opts.factor ?? D.f1, gx: gx ?? D.f1, gy: gy ?? D.f1 }, { outS: out },
    { uLnT: Math.log(Math.tan(Number(_p(params, 'threshold_deg')) * DEG)), uTn: Number(_p(params, 'threshold_noise')),
        uB: Number(_p(params, 'breakup')), uO: Number(_p(params, 'outcrops')), uGain: gain ? (1.0 + g) ** belowMain : 1.0,
        uHas: [nt ? 1 : 0, nb ? 1 : 0, nr ? 1 : 0, gain ? 1 : 0],
        uMode: [opts.from ? 1 : 0, opts.factor ? 1 : 0, opts.refineH ? 1 : 0, 0] });
    for (const f of own) f.destroy();
    return out;
}

/** The uplift shape (core/compose.js uplift, about 0..1) at the level's cells, divided by `peak` (the shape's maximum
 * on the coarsest level, so every level scales alike), times k (fluvial.py uplift_field; U0 x it in op_fluvial). A
 * new field. */
export async function upliftField(spec, level, seed, R, peak = null, k = 1.0) {
    const u = C.uplift(R, spec, level, seed);
    const pk = peak !== null && peak !== undefined ? Number(peak) : (await prims(R).stats(u)).max;
    const out = HS.ew(R, HS.EW.SCALE_DIV, u, null, null, k, Math.max(pk, 1e-12));
    u.destroy();
    return out;
}

export const COMPOSITE_KEYS = Object.freeze(['shape', 'regional', 'tilt']);

/** The uplift (about 0..1, before the peak normalisation) of an 'uplift' stage with a regional background or a tilt
 * (fluvial.py composite_uplift: the shape joined by a smooth maximum to fraction x max(1 + texture n - cut, 0), n
 * noise at wavelength_m; then x max(1 + per_km (metres along azimuth_deg) / 1000, 0.05)). A new field. */
export function compositeUplift(params, level, seed, R) {
    const D = Gd.dummies(R);
    const spec = params.shape;
    const u = truthy(spec) ? C.uplift(R, { ...spec }, level, seed) : null;
    const reg = params.regional;
    let n = null;
    if (truthy(reg)) {
        const kind = reg.kind ?? 'fbm';
        if (kind !== 'fbm' && kind !== 'ridged') throw new Error(`uplift regional kind '${kind}' is 'fbm' or 'ridged'`);
        n = field({ kind, wavelength_m: Number(reg.wavelength_m ?? 12000.0), octaves: Math.trunc(Number(reg.octaves ?? 3)),
            amp: kind === 'fbm' ? 3.0 : 1.0 }, level, Math.trunc(seed) + 61, R);
    }
    if (!u && !n) throw new Error("stage 'uplift': give a 'shape' or a 'regional' background");
    const tl = params.tilt;
    const tilt = truthy(tl);
    const [cx, cy] = tilt ? (tl.centre ?? [0.0, 0.0]).map(Number) : [0, 0];
    const az = tilt ? Number(tl.azimuth_deg ?? 90.0) * DEG : 0;
    const out = R.field(level.n, level.n, 1);
    R.run('fluvial/composite', { us: u ?? D.f1, nr: n ?? D.f1 }, { outU: out },
        { uHas: [u ? 1 : 0, n ? 1 : 0, tilt ? 1 : 0, 0], uFrac: n ? Number(reg.fraction ?? 0.4) : 0.0,
            uTex: n ? Number(reg.texture ?? 0.6) : 0.0, uCut: n ? Number(reg.cut ?? 0.0) : 0.0, uBlend: n ? Number(reg.blend ?? 0.1) : 0.0,
            uOrigin: [level.x0 - cx, level.y0 - cy], uCell: level.cell, uDir: [Math.sin(az), Math.cos(az)],
            uPerKm: tilt ? Number(tl.per_km ?? 0.0) : 0.0 });
    if (u) u.destroy();
    if (n) n.destroy();
    return out;
}

/** core/compose.py start_surface's rough start for a composite uplift u (fluvial.py composite_start): heightM u /
 * peak ((1 - r) + r (0.5 + 1.5 n)), n its fbm at 0.3 of the shape's size (5 octaves). A new field. */
export function compositeStart(params, u, level, seed, R, heightM, roughness, peak) {
    const spec = params.shape || {};
    const reg = params.regional || {};
    const size = Number(spec.radius_m ?? (Number(spec.length_m ?? 2.0 * Number(reg.wavelength_m ?? 10000.0)) * 0.5));
    // compose.py _Noise.fbm(size * 0.3, 5, seed + 31): the plain fbm, as Blender dispatches it (an amp or offset in
    // the spec would change world_noise_field's uniforms in the dispatch log), then 0.5 + 1.5 nz
    const nz = field({ kind: 'fbm', wavelength_m: size * 0.3, octaves: 5 }, level, Math.trunc(seed) + 31, R);
    const n = Gd.arith(R, 'affine', nz, null, { amp: 1.5, off: 0.5 });
    nz.destroy();
    const out = R.field(level.n, level.n, 1);
    R.run('compose/start', { shape: u, rough: n }, { outF: out },
        { uHeight: Number(heightM), uPeak: Math.max(Number(peak), 1e-9), uRough: Number(roughness) });
    n.destroy();
    return out;
}

/** The creep diffusivity of a level (m^2/yr) and the valley spacing it stands for: D = K (spacing / 26)^2, spacing at
 * least 5 cells (fluvial.py diffusivity). [D, spacing]. */
export function diffusivity(params, cell, depth, mainCell) {
    const K = Number(_p(params, 'K'));
    if (has(params, 'D') && params.D !== null && params.D !== undefined) {
        return [Number(params.D), SPACING_RATIO * Math.sqrt(Number(params.D) / K)];
    }
    let sp = levelSpacing(params, depth);
    sp = Math.max(sp, MIN_SPACING_CELLS * cell);
    return [K * (sp / SPACING_RATIO) ** 2, sp];
}

/** The valley spacing (m) a level of this depth is asked for, before its cell's minimum (fluvial.py level_spacing):
 * the knob, halved per hero level with gullies, grown by context_spacing_factor per context level. */
export function levelSpacing(params, depth) {
    let sp = Number(_p(params, 'valley_spacing_m'));
    if (truthy(_p(params, 'gullies')) && depth < 0) sp = sp / 2.0 ** (-depth);
    const g = Number(_p(params, 'context_spacing_factor'));
    if (depth > 0 && g !== 1.0) sp = sp * g ** depth;
    return sp;
}

/** The lock's block in cells: the power of two nearest targetM / cell, at least 2, at most n / maxFrac, and dividing
 * n (fluvial.py lock_block). */
export function lockBlock(targetM, cell, n, maxFrac = 8) {
    let b = 2 ** pyRound(Math.log2(Math.max(Number(targetM) / Number(cell), 2.0)));
    b = Math.trunc(Math.min(Math.max(b, 2), Math.max(Math.floor(n / maxFrac), 2)));
    while (n % b) b = Math.floor(b / 2);
    return Math.max(b, 1);
}

/** Each block's mean over its cells inside the grid (fluvial.py offset_block_means: block (J, I) covers cells b (J,
 * I) - off .. + b, clipped; 0 where it holds none), as numpy's float64 mean rounded to float32
 * (kernels/fluvial/block_mean.wgsl). A new field of `shape` [rows, columns]. */
export function offsetBlockMeans(R, h, b, off, shape) {
    const out = R.field(shape[0], shape[1], 1);
    R.run('fluvial/block_mean', { h }, { outT: out }, { uB: Math.trunc(b), uOff: [Math.trunc(off[0]), Math.trunc(off[1])] });
    return out;
}


// =============================================================================================== the driver ===

/** (sub-steps, D used): dt_sub <= 0.9 cell^2 / (3.4 D cap); past maxSub the diffusivity is lowered instead
 * (fluvial.py creep_substeps). */
export function creepSubsteps(dt, cell, D, cap, maxSub) {
    if (D <= 0) return [0, 0.0];
    const need = Math.trunc(Math.ceil(dt / ((0.9 * cell * cell) / (3.4 * D * cap))));
    if (need <= maxSub) return [Math.max(need, 1), D];
    return [Math.trunc(maxSub), (D * maxSub) / need];
}

/** One level's backbone on the GPU (fluvial.py FluvialRun): the state and accumulator fields, and step().
 * fields: a level's Fields (h, and A, qs, bed, wear, deposit, talus when present); par: the forcing pack (an rgba32f
 * field the run keeps, U K Sc G); pins: { pin_w, pin_h, A_in, qs_in } fields; column: { k_factor (Float32Array),
 * zoff (a field), z0, dz } or null; lockH0: the lock's start height (a field) or null; lockB: its block. */
export class FluvialRun {
    constructor(R, cell, fields, par, pins, bound = PINNED, column = null, lockH0 = null, lockB = 2) {
        this.R = R;
        this.cell = Number(cell);
        const h = fields.h;
        const [n0, n1] = [h.h, h.w];
        this.shape = [n0, n1];
        const { S, M } = HS.statePairs(R, fields, this.cell * this.cell);
        this.S = S;
        this.M = M;
        this.W = R.field(n0, n1, 1);
        this.P = par;
        this.Q = HS.pinsPack(R, pins);
        this.bound = bound;
        this._own = [];
        if (column) {
            const kc = Float32Array.from(column.k_factor);
            this.kcol = R.field(1, kc.length, 1, kc);
            this.zoff = column.zoff;
            this.col = [Number(column.z0), Number(column.dz), kc.length];
            this._own.push(this.kcol);
        } else {
            // a 1 x 1 stand-in bound as both, as Blender binds one dummy texture to both samplers
            this.kcol = R.field(1, 1, 1);
            this.zoff = this.kcol;
            this.col = [0.0, 1.0, 0];
            this._own.push(this.kcol);
        }
        this.phi = null;                                  // the isotropic threshold's excess field (made on first use)
        this.lock = null;
        this.lockB = Math.trunc(lockB);
        if (lockH0) {
            const b = this.lockB;
            const half = Math.max(Math.floor(b / 2), 1);
            // large blocks reduce in two stages (b1 x b1 partial means first): one work group summing 128^2 cells
            // serially cost 4 ms a step at 2048^2. b1 divides the half block, so the offsets stay whole partials
            let b1 = 1;
            if (b >= 32 && half % 16 === 0) {
                b1 = 16;
                while (Math.floor(b / b1) > 64 && half % (2 * b1) === 0) b1 *= 2;
            }
            let stage1 = null;
            if (b1 > 1) {
                const m0 = Math.floor(n0 / b1), m1 = Math.floor(n1 / b1);
                stage1 = [b1, R.field(m0, m1, 1), R.field(m0, m1, 1)];
            }
            const mb = [Math.floor(n0 / b) + 1, Math.floor(n1 / b) + 1];
            // the block grid cycles through four half-block offsets, one per step: a fixed square grid's box means
            // and tensor-product spread printed a 4-fold aspect bias (0.06-0.08) on the refined levels' slopes
            const phases = LOCK_PHASES.map(([px, py]) => {
                const off = [px * half, py * half];
                return [off, offsetBlockMeans(R, lockH0, b, off, mb)];
            });
            this.lock = [phases, R.field(mb[0], mb[1], 1), stage1];
        }
        this.steps = 0;
    }

    setPar(par) {
        if (this.P && this.P !== par) this.P.destroy();
        this.P = par;
    }

    step(dt, D, nSub, iters, rate, cap, m = 0.5, nexp = 1.0, p = 1.0, lockGain = 1.0, slope = 1, iso = 1,
        pitFill = 1, pitEps = 1e-3) {
        const R = this.R, S = this.S, M = this.M, cell = this.cell, b = this.bound;
        R.run('flow_weights', { st: S.src }, { outW: this.W }, { uDx: cell, uP: p, uBound: b });
        const [z0, dz, nc] = this.col;
        R.run('route_incise', { st: S.src, wsumT: this.W, par: this.P, pin: this.Q, mk: M.src, kcol: this.kcol, zoff: this.zoff },
            { outS: S.dst, outM: M.dst },
            { uDx: cell, uDt: dt, uM: m, uN: nexp, uP: p, uColZ0: z0, uColDz: dz, uColN: nc, uSlope: Math.trunc(slope),
                uPitFill: Math.trunc(pitFill), uPitEps: pitEps, uBound: b });
        S.swap();
        M.swap();
        if (D > 0 && nSub > 0) {
            R.run('h_keep', { st: S.src }, { outH: this.W }, {});          // the flow weights are used by now
            for (let k = 0; k < nSub; k++) {
                R.run('creep', { st: S.src, par: this.P, pin: this.Q }, { outS: S.dst },
                    { uDx: cell, uDtSub: dt / nSub, uD: D, uCap: cap, uBound: b });
                S.swap();
            }
            R.run('creep_layers', { st: S.src, h0: this.W, mk: M.src }, { outM: M.dst }, {});
            M.swap();
        }
        for (let k = 0; k < iters; k++) this.phi = HS.thresholdPass(R, S, M, this.P, this.Q, cell, rate, false, b, iso, this.phi);
        if (this.lock !== null) {
            const [phases, Rf, stage1] = this.lock;
            const [off, tgt] = phases[this.steps % phases.length];
            if (stage1 !== null) {
                const [b1, zero, R1] = stage1;
                R.run('lock_restrict', { st: S.src, tgt: zero }, { outR: R1 }, { uB: b1, uOff: [0, 0] });
                R.run('lock_restrict', { st: R1, tgt }, { outR: Rf },
                    { uB: Math.floor(this.lockB / b1), uOff: [Math.floor(off[0] / b1), Math.floor(off[1] / b1)] });
            } else {
                R.run('lock_restrict', { st: S.src, tgt }, { outR: Rf }, { uB: this.lockB, uOff: off });
            }
            R.run('lock_apply', { st: S.src, res: Rf, pin: this.Q, mk: M.src }, { outS: S.dst, outM: M.dst },
                { uGain: lockGain, uB: this.lockB, uOff: off });
            S.swap();
            M.swap();
        }
        this.steps += 1;
    }

    /** The state field (its channel 0 is h): what the relief controller measures. */
    height() { return this.S.src; }

    /** { h, A, qs, wear, deposit, talus, loose }: new r32f fields from the state. */
    readback() {
        const s = this.R.unpack(this.S.src, ['h', 'A', 'qs', null]);
        const m = this.R.unpack(this.M.src, ['wear', 'deposit', 'talus', 'loose']);
        return { ...s, ...m };
    }

    destroy() {
        for (const f of [this.S, this.M, this.W, this.P, this.Q, ...this._own]) if (f && !f.destroyed) f.destroy?.();
        if (this.phi && !this.phi.destroyed && this.phi.h > 1) this.phi.destroy();
        if (this.lock) {
            const [phases, Rf, stage1] = this.lock;
            for (const [, t] of phases) t.destroy();
            Rf.destroy();
            if (stage1) { stage1[1].destroy(); stage1[2].destroy(); }
        }
    }
}


// =================================================================================================== the ops ===

/** Stage 'uplift' (fluvial.py op_uplift): the uplift shape (params 'shape': a core/compose.js uplift spec - ridge
 * with spurs, dome, plateau, massif - in world metres) times U_m_per_yr (default 3e-3 m/yr) as the field U,
 * normalised by the shape's peak on the coarsest level. With 'regional' and/or 'tilt' the uplift is compositeUplift's.
 * On a fresh level, h = the start surface: the uplift scaled to start_m (default 600 m) with start_roughness (0.4) of
 * multi-scale texture. Its shape is remembered for the fluvial stage of every level (ctx.shared.uplift). */
export async function opUplift(fields, level, params, seed = 0, ctx = null) {
    ctx = await asContext(ctx, fields, level);
    const R = runnerOf(fields, ctx);
    const spec = truthy(params.shape) ? { ...params.shape } : null;
    const s = Math.trunc(seed) + Math.trunc(Number(params.seed ?? 0));
    const comp = truthy(params.regional) || truthy(params.tilt)
        ? Object.fromEntries(COMPOSITE_KEYS.filter((k) => truthy(params[k])).map((k) => [k, params[k]])) : null;
    const first = !('uplift' in ctx.shared);
    let u = null;
    if (first || ctx.fresh) {
        u = comp ? compositeUplift(comp, level, s, R) : C.uplift(R, spec, level, s);
        if (first) {
            ctx.shared.uplift = { spec, seed: s, peak: (await prims(R).stats(u)).max, U: Number(params.U_m_per_yr ?? 3e-3) };
            if (comp) ctx.shared.uplift.composite = comp;
        }
    }
    const sh = ctx.shared.uplift;
    if (ctx.role === 'grow') {
        if (u === null) u = comp ? compositeUplift(comp, level, s, R) : await upliftField(spec, level, s, R, 1.0);
        fields.U = HS.ew(R, HS.EW.SCALE_DIV, u, null, null, sh.U, Math.max(sh.peak, 1e-12));
    }
    if (ctx.fresh) {
        let h0;
        if (comp) {
            h0 = compositeStart(comp, u, level, s, R, Number(params.start_m ?? 600.0), Number(params.start_roughness ?? 0.4), sh.peak);
        } else {
            h0 = await C.startSurface(R, spec, level, s, { heightM: Number(params.start_m ?? 600.0),
                roughness: Number(params.start_roughness ?? 0.4), peak: sh.peak });
        }
        const bed = R.like(h0);
        R.copy(h0, bed);
        fields.h = h0;
        fields.bed = bed;
    }
    if (u && !u.destroyed) u.destroy();
    return fields;
}

/** 1 on sea cells and inside flatten areas (rigid: no uplift, no incision): fluvial.py _sea_flat. A new field, or
 * null when nothing is rigid (numpy's rigid.any() is then false). */
export async function seaFlat(fields, ctx, level, R) {
    const sea = ctx.sea_level ?? null;
    const areas = (ctx.flatten ?? []).filter((f) => f.radius !== null && f.radius !== undefined)
        .map((f) => ({ at: f.at, radius: f.radius ?? 10.0, falloff: f.falloff ?? 0.0 }));
    if (sea === null && !areas.length) return null;
    const D = Gd.dummies(R);
    const fm = areas.length ? C.flattenMask(R, areas, level) : null;
    const rig = R.field(level.n, level.n, 1), scratch = R.field(1, 1, 1);
    R.run('fluvial/pins', { h: fields.h, a: fm ?? D.f1, pw: D.f1, ph: D.f1 }, { outW: rig, outH: scratch },
        { uMode: 2, uHasH: 1, uSea: sea !== null ? 1 : 0, uSea32: sea !== null ? Math.fround(sea) : 0.0, uFlat: fm ? 1 : 0 });
    scratch.destroy();
    if (fm) fm.destroy();
    if ((await prims(R).stats(rig)).nonzero === 0) {
        rig.destroy();
        return null;
    }
    return rig;
}

/** Stage 'fluvial' (fluvial.py op_fluvial; module doc): grow on the coarsest level, refine below it. */
export async function opFluvial(fields, level, params, seed = 0, ctx = null) {
    ctx = await asContext(ctx, fields, level);
    const R = runnerOf(fields, ctx);
    const t0 = now();
    const lv = level;
    const n = lv.n;
    const cell = Number(lv.cell);
    const mode = _p(params, 'mode');
    const refine = ctx.role === 'refine' || mode === 'refine';
    const main = ctx.main;
    const mainCell = main ? Number(main.cell) : cell;
    const depth = ctx.depth;
    const s = Math.trunc(seed) + Math.trunc(Number(params.seed ?? 0));
    if (!('h' in fields)) throw new Error(`stage 'fluvial' on ${lv}: no height yet (put an 'uplift' stage or a start before it)`);
    const h = fields.h;
    const own = [];

    // the inputs, all functions of world position (finding 2 of the design)
    const rigid = await seaFlat(fields, ctx, lv, R);
    if (rigid) own.push(rigid);
    // the sea and flatten areas are rigid (core/compose.js flattenMask): U = K = 0 there
    const K = erodibility(lv, params, s, R, { kFactor: 'K_factor' in fields ? fields.K_factor : null, rigid });
    const fromField = 'Sc' in fields && (params.Sc_from_fields ?? true) && !refine;
    const Sc = threshold(lv, params, s, R, Math.max(0, -depth), { from: fromField ? fields.Sc : null,
        factor: 'Sc_factor' in fields ? fields.Sc_factor : null, refineH: mode === 'refine' ? h : null });
    // uplift: the growing level runs the real uplift. Refining levels run none: the lock is their uplift, raising
    // exactly what their rivers cut
    let U;
    if (refine) {
        U = Gd.fill(R, [n, n], 0.0);
    } else if ('U' in fields) {
        U = R.like(fields.U);
        R.copy(fields.U, U);
    } else if ('uplift' in ctx.shared) {
        const sh = ctx.shared.uplift;
        if (truthy(sh.composite)) {
            const u = compositeUplift(sh.composite, lv, sh.seed, R);
            U = HS.ew(R, HS.EW.SCALE_DIV, u, null, null, sh.U, Math.max(sh.peak, 1e-12));
            u.destroy();
        } else {
            U = await upliftField(sh.spec, lv, sh.seed, R, sh.peak, sh.U);
        }
    } else {
        U = Gd.fill(R, [n, n], 0.0);
    }
    if (rigid) {
        const Uz = HS.ew(R, HS.EW.MASK_ZERO, U, rigid);     // U = where(rigid, 0, U)
        U.destroy();
        U = Uz;
    }
    let uf = Number(ctx.shared.U_factor ?? 1.0);
    const upliftScale = Number(_p(params, 'uplift_scale'));
    const G = Number(_p(params, 'deposition'));
    const parOf = (factor) => {
        const P = R.field(n, n, 4);
        R.run('fluvial/par', { U, K, Sc }, { outP: P }, { uScale: upliftScale, uFactor: Number(factor), uG: G });
        return P;
    };

    let pins = ctx.pins, ownPins = false;
    if (!pins) {
        pins = edgePins(R, n, h, ctx.sea_level ?? null);
        ownPins = true;
    }
    if (refine && 'incised' in fields) {
        // an incised river's channel (op_incise, inherited) is held where it arrives: its base-level fall made it
        const held = (await prims(R).stats(fields.incised, { mask: fields.incised })).count;   // cells > 0
        if (held > 0) {
            const pw = R.field(n, n, 1), ph = R.field(n, n, 1);
            R.run('fluvial/pins', { h, a: fields.incised, pw: pins.pin_w, ph: pins.pin_h }, { outW: pw, outH: ph },
                { uMode: 1, uHasH: 1, uSea: 0, uSea32: 0.0, uFlat: 0 });
            const p2 = { pin_w: pw, pin_h: ph, A_in: pins.A_in, qs_in: pins.qs_in };
            if (ownPins) { pins.pin_w.destroy(); pins.pin_h.destroy(); }
            own.push(pw, ph);
            pins = p2;
        }
    }
    const [D, spacing] = diffusivity(params, cell, depth, mainCell);
    let dt, steps;
    if (refine) {
        dt = (Number(_p(params, 'dt_ref_yr')) * Math.max(cell, mainCell)) / CELL_REF_M;
        steps = Math.trunc(Number(has(params, 'steps') ? params.steps : _p(params, 'refine_steps')));
    } else {
        dt = (Number(_p(params, 'dt_ref_yr')) * cell) / CELL_REF_M;
        const age = Number(_p(params, 'age_myr')) * 1e6;
        const first = ctx.fresh && (ctx.prepass === null || ctx.prepass === 0);
        const dur = first ? age : age * Number(_p(params, 'later_frac'));
        steps = Math.trunc(Number(has(params, 'steps') ? params.steps : pyRound(dur / dt)));
    }
    steps = Math.trunc(Math.min(Math.max(steps, Math.trunc(Number(_p(params, 'min_steps')))), Math.trunc(Number(_p(params, 'max_steps')))));
    const cap = Number(_p(params, 'creep_cap'));
    const [nSub, Dused] = creepSubsteps(dt, cell, D, cap, Math.trunc(Number(_p(params, 'max_creep_sub'))));
    let lockH0 = null, lockB = 2, lockM = null;
    if (refine && truthy(_p(params, 'lock'))) {
        // hold what the parent resolved: wavelengths from its valley spacing up (a real DEM: 8 of its cells)
        const pl = ctx.plan && ctx.plan[ctx.index]?.parent !== null && ctx.plan[ctx.index]?.parent !== undefined
            ? ctx.plan[ctx.plan[ctx.index].parent] : null;
        const pcell = pl ? Number(pl.cell) : 2.0 * cell;
        if (has(params, 'lock_m') && params.lock_m !== null) lockM = Number(params.lock_m);
        else if (mode === 'refine') lockM = 8.0 * pcell;
        else lockM = LOCK_SCALE * diffusivity(params, pcell, pl?.depth ?? depth + 1, mainCell)[1];
        lockB = lockBlock(lockM, cell, n, Math.trunc(Number(_p(params, 'lock_max_frac'))));
        lockH0 = h;                                         // the start: every phase's block means are held to it
    }
    const run = new FluvialRun(R, cell, fields, parOf(uf), pins, PINNED, params.column ?? null, lockH0, lockB);
    let target = params.relief_m ?? null;
    let control = !refine && target !== null;
    if (control && _p(params, 'control_levels') === 'first' && ctx.index > 0) control = false;
    target = control ? Number(target) * Number(_p(params, 'relief_calib')) : null;
    const over = _p(params, 'relief_over');
    if (over !== 'main' && over !== 'level') throw new Error(`stage 'fluvial': relief_over '${over}' is 'main' or 'level'`);
    const rwin = over === 'main' ? main : null;
    const iters = Math.trunc(Number(_p(params, 'threshold_iters')));
    const tmode = _p(params, 'threshold_mode');
    const rate = Number(truthy(params.threshold_rate) ? params.threshold_rate : THRESHOLD_RATE[tmode]);
    const mexp = Number(_p(params, 'm')), nexp = Number(_p(params, 'n')), pexp = Number(_p(params, 'p'));
    const slopeMode = { dinf: 1, d8: 0 }[_p(params, 'slope')];
    const pit = truthy(_p(params, 'fill_pits')) ? 1 : 0;
    const peps = Number(_p(params, 'pit_eps_m'));
    const history = [];
    const ufMax = _p(params, 'U_factor_max');
    for (let i = 0; i < steps; i++) {
        run.step(dt, Dused, nSub, iters, rate, cap, mexp, nexp, pexp, 1.0, slopeMode, tmode === 'iso' ? 1 : 0, pit, peps);
        if (control && (i + 1) % CONTROL_EVERY === 0 && i + 1 < steps) {
            const rel = await RUN.windowRelief(run.height(), lv, rwin);
            const f = Math.min(Math.max((target / Math.max(rel, 1e-6)) ** CONTROL_POWER, CONTROL_CLAMP[0]), CONTROL_CLAMP[1]);
            uf *= f;
            if (ufMax !== null && ufMax !== undefined) uf = Math.min(uf, Number(ufMax));
            run.setPar(parOf(uf));
            history.push([i + 1, pyRoundN(rel, 1), pyRoundN(uf, 4)]);
        }
    }
    const out = run.readback();
    if (control) ctx.shared.U_factor = uf;
    if (!params._incise) ctx.shared.fluvial_params = { ...params };   // the 'incise' stage runs the level's own physics
    for (const k of ['h', 'A', 'qs', 'wear', 'deposit', 'talus']) fields[k] = out[k];
    fields.bed = HS.ew(R, HS.EW.SUB, out.h, out.loose);
    out.loose.destroy();
    fields.U = HS.ew(R, HS.EW.SCALE, U, null, null, uf);
    fields.K = K;
    fields.Sc = Sc;
    fields.G = Gd.fill(R, [n, n], Math.fround(G));
    U.destroy();
    run.destroy();
    if (ownPins) for (const f of Object.values(pins)) if (!f.destroyed) f.destroy();
    for (const f of own) if (!f.destroyed) f.destroy();
    ctx.evolved = true;
    const rel = !refine ? await RUN.windowRelief(fields.h, lv, rwin) : null;
    const info = { level: String(lv), prepass: ctx.prepass, role: refine ? 'refine' : 'grow', steps,
        dt_yr: pyRoundN(dt, 2), years: pyRound(steps * dt), D: Dused, spacing_m: pyRoundN(spacing, 1),
        creep_sub: nSub, U_factor: pyRoundN(uf, 4), relief_main_window_m: rel === null ? null : pyRoundN(rel, 1),
        lock_block_cells: lockH0 !== null ? lockB : null, lock_m: lockM, seconds: pyRoundN(now() - t0, 3),
        controller: history.slice(-6) };
    (ctx.shared.fluvial_log ??= []).push(info);
    ctx.log(`[terrain.fluvial] ${info.role} ${lv.n}^2 @ ${fmtG(cell, 3)} m` +
        (ctx.prepass !== null && ctx.prepass !== undefined ? ` (pre-pass ${ctx.prepass})` : '') +
        `: ${steps} steps x ${dt.toFixed(0)} yr, D ${fmtG(Dused, 3)} m2/yr (valleys ${spacing.toFixed(0)} m), creep x${nSub}` +
        (rel !== null ? `, U x${uf.toFixed(3)}, relief ${rel.toFixed(0)} m` : '') +
        (lockH0 !== null ? `, locked above ${lockB} cells (${(lockB * cell).toFixed(0)} m)` : '') + `, ${info.seconds} s`);
    return fields;
}

// ================================================================================== alluvial valley floors ===

export const FLOOR = Object.freeze({ width_m: 120.0, area_ref_m2: 5.0e7, width_exp: 0.5, area_min_m2: 1.0e6,
    width_max_m: 600.0, depth_max_m: 80.0, cross_slope: 0.01, grade: 0.002, min_width_cells: 2.0, toe_cells: 1.0,
    along_smooth: 8 });

/** The smallest float32 at or above x. */
function f32AtOrAbove(x) {
    const f = Math.fround(x);
    if (f >= x) return f;
    const b = new Float32Array([f]), u = new Uint32Array(b.buffer);
    if (f > 0) u[0] += 1;
    else if (f < 0) u[0] -= 1;
    else u[0] = 1;
    return b[0];
}

/** Stage 'valley_floor' (fluvial.py op_valley_floor): alluvial floors in the valleys of the channels the level
 * resolves. A river carrying more sediment than it can move aggrades its valley: the floor fills flat between the
 * walls until it is as wide as the river's floodplain. Per channel cell (drainage area A >= area_min_m2), the floor's
 * width is W = width_m (A / area_ref_m2)^width_exp, at most width_max_m (a channel whose floor would be under
 * min_width_cells cells is left a V on this level). The cells that drain to it laterally (the first channel cell down
 * their D8 path, on the eroded surface or, where the river crosses a rounding pit, the lake-filled routing surface)
 * are its valley's cross-section; the floor's level is their mean height above the channel at half the floor's
 * width along their paths, at most depth_max_m above it; that depth is smoothed along the network (along_smooth
 * passes). Floors never drop going upstream (each channel cell's floor at least its receiver's plus `grade` per
 * metre). Cells under their floor fill to it, rising cross_slope per metre of path away from the channel, the fill's
 * edge softened over toe_cells. The fill is sediment: it adds to `deposit` (bed stays). Pins hold a child's border
 * band to its parent's surface. Every step is a GPU kernel (kernels/fluvial/vf_*.wgsl; the pointer jumping of numpy's
 * loop, its np.bincount sums as a stable sort and ordered runs, its sequential upstream pass as a path maximum). */
export async function opValleyFloor(fields, level, params, seed = 0, ctx = null) {
    ctx = await asContext(ctx, fields, level);
    const t0 = now();
    if (params.enabled === false) return fields;
    const p = { ...FLOOR };
    for (const [k, v] of Object.entries(params ?? {})) if (k in FLOOR && v !== null && v !== undefined) p[k] = v;
    if (Number(p.width_m) <= 0) return fields;
    const R = runnerOf(fields, ctx), P = prims(R), D = Gd.dummies(R);
    const h = fields.h, n = level.n, cell = Number(level.cell), N = n * n;
    const sea = ctx.sea_level ?? null;
    const own = [];
    let surf = null, A;
    if ('A' in fields) {
        A = fields.A;
    } else {
        const { filled } = await HY.fillDepressions(h, { seaLevel: sea });
        surf = await HY.routingSurface(filled, { seaLevel: sea });
        filled.destroy();
        A = (await HY.routeToConvergence(R, surf, cell)).A;
        own.push(A);
    }
    const W = R.field(n, n, 1), chan = R.field(n, n, 1), cnt = R.field(1, 1, 1, null, 'u32');
    cnt.name = 'valley_floor_count';
    own.push(W, chan, cnt);
    R.run('fluvial/vf_chan', { A, h }, { outW: W, outC: chan, count: cnt },
        { uWidth: Number(p.width_m), uAref: Number(p.area_ref_m2), uExp: Number(p.width_exp), uWmax: Number(p.width_max_m),
            uAmin: f32AtOrAbove(Number(p.area_min_m2)), uMinCells: Number(p.min_width_cells), uCell: cell,
            uSea: sea !== null ? 1 : 0, uSea32: sea !== null ? Math.fround(sea) : 0.0 });
    const [nch] = await R.readRange(cnt, 0, 1);
    const release = () => { for (const f of own) if (!f.destroyed) f.destroy(); if (surf && !surf.destroyed) surf.destroy(); };
    if (nch === 0) {
        ctx.log(`[terrain.fluvial] valley floors on ${level}: no channel wide enough at ${fmtG(cell, 3)} m cells`);
        release();
        return fields;
    }
    // D8 receivers on the eroded surface; when a channel cell inside the window has none (a rounding pit or flat on
    // the river), on the lake-filled surface tilted across its flats instead, with the channel cells breached
    const scratchU = R.field(1, 1, 1, null, 'u32'), scratchF = R.field(1, 1, 1);
    own.push(scratchU, scratchF);
    let rec = HY.d8Receivers(h);
    if (surf === null) {
        R.clear(cnt);
        R.run('fluvial/vf_init', { rec, chan }, { outT: scratchU, outD: scratchF, count: cnt }, { uMode: 0, uCell: cell },
            [Math.ceil(n / 16), Math.ceil(n / 16), 1]);
        const [pits] = await R.readRange(cnt, 0, 1);
        if (pits > 0) {
            const { filled } = await HY.fillDepressions(h, { seaLevel: sea });
            surf = await HY.routingSurface(filled, { seaLevel: sea });
            filled.destroy();
        }
    }
    if (surf !== null) {
        rec.destroy();
        rec = HY.d8Receivers(surf, { breach: chan });
    }
    own.push(rec);
    const order = surf ?? h;
    const rounds = Math.ceil(Math.log2(Math.max(2, N))) + 1;
    const cover = [Math.ceil(n / 16), Math.ceil(n / 16), 1];
    // every cell's first channel cell down its path (pointer jumping) and the path's length to it
    const Tp = R.pair(n, n, 1, null, 'u32'), Dp = R.pair(n, n, 1);
    own.push(Tp, Dp);
    R.run('fluvial/vf_init', { rec, chan }, { outT: Tp.src, outD: Dp.src, count: cnt }, { uMode: 1, uCell: cell }, cover);
    for (let r = 0; r < rounds; r++) {
        R.run('fluvial/vf_jump', { ptr: Tp.src, val: Dp.src }, { outP: Tp.dst, outV: Dp.dst }, {});
        Tp.swap();
        Dp.swap();
    }
    // the floor level of each channel cell: the mean height above it of the cells that drain to it from half the
    // floor's width away (np.bincount over the band cells: a stable sort by channel cell, then each run in order)
    const keys = R.field(n, n, 1, null, 'u32'), hand = R.field(n, n, 1);
    own.push(keys, hand);
    R.run('fluvial/vf_band', { t: Tp.src, dist: Dp.src, chan, h, W }, { outK: keys, outH: hand }, { uCell: cell });
    const sorted = P.sortPairs(keys, null, {});
    own.push(sorted.keys, sorted.vals);
    const L = R.pair(n, n, 1);
    own.push(L);
    R.run('fluvial/vf_sum', { sk: sorted.keys, sv: sorted.vals, hand }, { outL: L.src }, { uCount: N, uDepthMax: Number(p.depth_max_m) });
    // the fill depth smoothed along the network (each channel cell with its receiver and donors, along_smooth times)
    for (let k = 0; k < Math.trunc(Number(p.along_smooth)); k++) {
        R.run('fluvial/vf_smooth', { lvl: L.src, chan, rec }, { outL: L.dst }, {});
        L.swap();
    }
    // floors never drop going upstream: numpy's downstream-first pass, as a path maximum (vf_floor_init.wgsl)
    const Pf = R.pair(n, n, 1, null, 'u32'), Lf = R.pair(n, n, 1), F0 = R.field(n, n, 1);
    own.push(Pf, Lf, F0);
    R.run('fluvial/vf_floor_init', { rec, chan, surf: order, h, lvl: L.src }, { outP: Pf.src, outL: Lf.src, outF: F0 },
        { uGrade: Number(p.grade), uCell: cell });
    const Pa = R.pair(n, n, 1, null, 'u32'), K = R.pair(n, n, 1), Aa = R.pair(n, n, 1, null, 'u32');
    own.push(Pa, K, Aa);
    R.copy(Pf.src, Pa.src);
    for (let r = 0; r < rounds; r++) {
        R.run('fluvial/vf_jump', { ptr: Pf.src, val: Lf.src }, { outP: Pf.dst, outV: Lf.dst }, {});
        Pf.swap();
        Lf.swap();
    }
    const key = HS.ew(R, HS.EW.SUB, F0, Lf.src);
    R.copy(key, K.src);
    key.destroy();
    R.run('fluvial/vf_init', { rec, chan }, { outT: Aa.src, outD: scratchF, count: cnt }, { uMode: 2, uCell: cell }, cover);
    for (let r = 0; r < rounds; r++) {
        R.run('hydro/jump_argmax', { ptr: Pa.src, key: K.src, arg: Aa.src }, { outP: Pa.dst, outK: K.dst, outA: Aa.dst }, {});
        Pa.swap();
        K.swap();
        Aa.swap();
    }
    const Fr = R.field(n, n, 1);
    own.push(Fr);
    R.clear(cnt);
    R.run('fluvial/vf_floor_final', { chan, h, lvl: L.src, F0, L: Lf.src, arg: Aa.src }, { outF: Fr, count: cnt }, {});
    // cells under their floor fill to it, rising cross_slope away from the channel; the toe; the pins
    const fill = R.field(n, n, 1);
    own.push(fill);
    R.run('fluvial/vf_fill', { t: Tp.src, dist: Dp.src, chan, h, W, F: Fr, fb: D.f1, pins: D.f1 }, { outF: fill, outA: scratchF },
        { uMode: 0, uCross: Number(p.cross_slope), uToe: 0, uPins: 0 });
    const toe = Number(p.toe_cells) > 0;
    const fb = toe ? HS.gaussianBlur(fill, Number(p.toe_cells)) : null;
    if (fb) own.push(fb);
    const pins = ctx.pins ? R.pack(ctx.pins, ['pin_w', 'pin_h', null, null]) : null;
    if (pins) own.push(pins);
    const hn = R.field(n, n, 1), add = R.field(n, n, 1);
    R.run('fluvial/vf_fill', { t: Tp.src, dist: Dp.src, chan, h, W, F: fill, fb: fb ?? D.f1, pins: pins ?? D.f1 },
        { outF: hn, outA: add }, { uMode: 1, uCross: 0.0, uToe: toe ? 1 : 0, uPins: pins ? 1 : 0 });
    const [raised] = await R.readRange(cnt, 0, 1);
    const dep0 = 'deposit' in fields ? fields.deposit : null;
    fields.deposit = dep0 ? Gd.arith(R, 'add', dep0, add) : (() => { const c = R.like(add); R.copy(add, c); return c; })();
    if ('bed' in fields) fields.bed = HS.ew(R, HS.EW.MIN, fields.bed, hn);
    fields.h = hn;
    ctx.evolved = true;
    // the record: the cells filled over 5 cm, their median fill and the largest
    const on = HS.ew(R, HS.EW.LAKE, add, null, null, 0.05);
    const onCount = (await P.stats(on, { mask: on })).count;
    const p50 = onCount ? await P.median(add, { mask: on, dtype: 'float64' }) : 0.0;
    const mx = (await P.stats(add)).max;
    on.destroy();
    add.destroy();
    release();
    const info = { level: String(level), channel_cells: nch, raised_upstream: raised, floor_cells: onCount,
        fill_p50_m: Math.round(p50 * 100) / 100, fill_max_m: Math.round(mx * 100) / 100,
        seconds: Math.round((now() - t0) * 1000) / 1000 };
    (ctx.shared.floor_log ??= []).push(info);
    ctx.log(`[terrain.fluvial] valley floors ${level.n}^2 @ ${fmtG(cell, 3)} m: ${nch} channel cells (A >= ` +
        `${pyG(Number(p.area_min_m2) / 1e6)} km2), ${info.floor_cells} cells filled (p50 ${info.fill_p50_m} m, ` +
        `max ${info.fill_max_m} m), ${raised} backfilled upstream, ${info.seconds} s`);
    return fields;
}


// ================================================================================ a base-level fall along a river ===

export const INCISE = Object.freeze({ drop_m: 80.0, years: 3.0e4, stages: 6, uplift_scale: 1.0, fluvial: null, head_m: null,
    taper_m: 0.0 });

/** The non-increasing sequence closest to z in least squares (pool adjacent violators), doubles (fluvial.py
 * monotone_fit). z: an array of numbers along a course (a few thousand, not a level's cells). */
export function monotoneFit(z) {
    const vals = [], wts = [], cnts = [];
    for (const v of z) {
        vals.push(Number(v));
        wts.push(1.0);
        cnts.push(1);
        while (vals.length > 1 && vals[vals.length - 2] < vals[vals.length - 1]) {
            const k = vals.length - 2;
            const w = wts[k] + wts[k + 1];
            vals[k] = (vals[k] * wts[k] + vals[k + 1] * wts[k + 1]) / w;
            wts[k] = w;
            cnts[k] += cnts[k + 1];
            vals.pop();
            wts.pop();
            cnts.pop();
        }
    }
    const out = [];
    vals.forEach((v, i) => { for (let c = 0; c < cnts[i]; c++) out.push(v); });
    return Float64Array.from(out);
}

// np.interp(x, xp, fp) for one x: xp ascending (a course's arc lengths)
function interp(x, xp, fp) {
    const n = xp.length;
    if (x <= xp[0]) return fp[0];
    if (x >= xp[n - 1]) return fp[n - 1];
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) {
        const m = (lo + hi) >> 1;
        if (xp[m] <= x) lo = m; else hi = m;
    }
    if (xp[hi] === xp[lo]) return fp[hi];
    return fp[lo] + ((x - xp[lo]) * (fp[hi] - fp[lo])) / (xp[hi] - xp[lo]);
}

// np.searchsorted(a, v) (side 'left') on an ascending array
function searchsorted(a, v) {
    let lo = 0, hi = a.length;
    while (lo < hi) {
        const m = (lo + hi) >> 1;
        if (a[m] < v) lo = m + 1; else hi = m;
    }
    return lo;
}

// the median of a few numbers (np.median, float64)
function median(xs) {
    const s = Float64Array.from(xs).sort();
    const n = s.length;
    return n % 2 ? s[(n - 1) / 2] : 0.5 * (s[n / 2 - 1] + s[n / 2]);
}

/** Stage 'incise' (fluvial.py op_incise): a base-level fall along a river course, run once, on the finest growing
 * level (the levels below inherit what it cut). A river along the course (the river module's course parameters, as
 * 'river_path' takes them) drops drop_m below the grown surface, lowered in `stages` steps over `years` while the
 * fluvial physics run with the recipe's own parameters (`fluvial`, the uplift x uplift_scale; no relief controller),
 * so its valley is cut and knickpoints climb its tributaries only as far as the time allows. params (metres, years):
 * the course keys (kind, through, flow_azimuth_deg, wiggle_deg, wiggle_wavelength_m, width_m, length_m, seed),
 * drop_m 80, years 3e4, stages 6, uplift_scale 1, fluvial (null: the level's own 'fluvial' stage's), head_m (the river
 * rises head_m of arc length upstream of `through`), taper_m 0 (the fall eases in over this arc length), grade_m 3000,
 * min_grade 5e-4. Writes the course's channel cells into fields.river and fields.incised and ctx.shared.incise.
 *
 * The course, its channel on a level and its pins are the river module's (blender/eidoblend/terrain/solvers/rivers.py,
 * ported as solvers/rivers.js by the layered-rock package): it is imported when this op runs, so the fluvial module
 * loads without it; until it is in the checkout the op raises, naming it. What this op asks of it is rivers.py's own
 * interface: DEFAULTS, makeRiver (make_river)(course, seed, extent) giving a River with s, s_through, points,
 * final_course, _use(points, s_through), sampleTop (sample_top)(level, h field) -> the surface along the course,
 * a replaceable final(s, smooth), bed_m, gradient, schedule, and pins(level, basePins, f, { cache, hold }) -> [pins,
 * the channel's mask], GPU fields. The arithmetic along the course (the smoothing, the monotone fit, the grades) is
 * over its points, in doubles, as numpy computes it. */
export async function opIncise(fields, level, params, seed = 0, ctx = null) {
    ctx = await asContext(ctx, fields, level);
    if (params.enabled === false || !ctx.last_grow) return fields;
    const t0 = now();
    const p = { ...INCISE };
    for (const [k, v] of Object.entries(params ?? {})) if (v !== null && v !== undefined) p[k] = v;
    const drop = Number(p.drop_m);
    if (drop <= 0) return fields;
    let RV;
    try {
        RV = await import(new URL('./rivers.js', import.meta.url).href);
    } catch (e) {
        throw new Error(`stage 'incise': the river module (eidoverse/terrain/solvers/rivers.js, the port of ` +
            `blender/eidoblend/terrain/solvers/rivers.py) is not in this checkout yet (${e.message})`);
    }
    const R = runnerOf(fields, ctx), P = prims(R);
    const makeRiver = RV.makeRiver ?? RV.make_river;
    const course = Object.fromEntries(Object.entries(p).filter(([k]) => k in RV.DEFAULTS && !['bed_m', 'gradient', 'schedule'].includes(k)));
    const extent = ctx.plan && ctx.plan.length ? Number(ctx.plan[0].side) : Number(level.side);
    const rv = await makeRiver(course, seed, extent);
    if (p.head_m !== null && p.head_m !== undefined) {
        // the course starts head_m upstream of its through point (a source inside the window)
        let k0 = searchsorted(rv.s, Math.max(Number(rv.s_through) - Number(p.head_m), 0.0));
        k0 = Math.min(k0, Math.max(rv.s.length - 4, 0));
        const pts = rv.points.slice(k0);
        rv.final_course = [pts, Number(rv.s_through) - Number(rv.s[k0])];
        rv._use(...rv.final_course);
    }
    const h0 = R.like(fields.h);
    R.copy(fields.h, h0);
    const top = await (rv.sampleTop ?? rv.sample_top).call(rv, level, h0);
    const pts = rv.points;
    const inside = [];
    for (let i = 0; i < pts.length; i++) {
        const [x, y] = pts[i];
        inside.push(x > level.x0 && x < level.x0 + level.side && y > level.y0 && y < level.y0 + level.side);
    }
    if (inside.filter(Boolean).length < 4) {
        ctx.log(`[terrain.fluvial] incise on ${level}: the course does not cross the window; nothing to cut`);
        h0.destroy();
        return fields;
    }
    // the final bed: the surface along the course inside the window, smoothed over grade_m of arc length, made to fall
    // downstream at least min_grade (the least-squares non-increasing fit, then the grade), minus the drop; past the
    // window, straight on at the end grades
    const sIn = [], zIn = [];
    inside.forEach((v, i) => { if (v) { sIn.push(Number(rv.s[i])); zIn.push(Number(top[i])); } });
    const ds = sIn.length > 1 ? median(sIn.slice(1).map((v, i) => v - sIn[i])) : 1.0;
    const k = Math.max(pyRound(Number(p.grade_m ?? 3000.0) / Math.max(ds, 1e-6) / 2.0), 1);
    const zp = [...Array(k).fill(zIn[0]), ...zIn, ...Array(k).fill(zIn[zIn.length - 1])];
    const zs = [];
    for (let i = 0; i + 2 * k < zp.length; i++) {
        let s = 0;
        for (let j = 0; j <= 2 * k; j++) s += zp[i + j] * (1 / (2 * k + 1));
        zs.push(s);
    }
    const gMin = Number(p.min_grade ?? 5e-4);
    const zg = monotoneFit(zs);
    for (let i = 1; i < zg.length; i++) zg[i] = Math.min(zg[i], zg[i - 1] - gMin * (sIn[i] - sIn[i - 1]));
    const taper = Number(p.taper_m || 0.0);
    if (taper > 0) {
        // the fall eases in below the head (still never rising: an increasing drop under a falling grade)
        for (let i = 0; i < zg.length; i++) {
            const t = Math.min(Math.max((sIn[i] - Number(rv.s[0])) / taper, 0.0), 1.0);
            zg[i] = zg[i] - drop * t * t * (3.0 - 2.0 * t);
        }
    } else {
        for (let i = 0; i < zg.length; i++) zg[i] -= drop;
    }
    const L = zg.length, kk = Math.min(k, L - 1), kb = Math.max(L - k - 1, 0);
    const g0 = Math.max((zg[0] - zg[kk]) / Math.max(sIn[kk] - sIn[0], 1e-6), gMin);
    const g1 = Math.max((zg[kb] - zg[L - 1]) / Math.max(sIn[L - 1] - sIn[kb], 1e-6), gMin);
    const graded = (s) => {
        const one = (x) => {
            if (x < sIn[0]) return zg[0] + g0 * (sIn[0] - x);
            if (x > sIn[L - 1]) return zg[L - 1] - g1 * (x - sIn[L - 1]);
            return interp(x, sIn, zg);
        };
        return typeof s === 'number' ? one(s) : Float64Array.from(s, one);
    };
    rv.final = graded;                                   // the River's bed(s, f) falls from top(s) to final(s)
    let i0 = 0;
    for (let i = 1; i < sIn.length; i++) if (Math.abs(sIn[i] - rv.s_through) < Math.abs(sIn[i0] - rv.s_through)) i0 = i;
    rv.bed_m = zg[i0];
    const g = (zg[0] - zg[L - 1]) / Math.max(sIn[L - 1] - sIn[0], 1e-6);
    rv.gradient = g;
    rv.schedule = [[0.0, 0.0], [1.0, 1.0]];
    const base = ctx.pins ?? edgePins(R, level.n, fields.h, ctx.sea_level ?? null);
    const fl = { ...(p.fluvial ?? ctx.shared.fluvial_params ?? {}) };
    Object.assign(fl, { relief_m: null, uplift_scale: Number(p.uplift_scale), lock: false, _incise: true });
    delete fl.steps;
    const Ukeep = 'U' in fields ? (() => { const c = R.like(fields.U); R.copy(fields.U, c); return c; })() : null;
    const dt = (Number(_p(fl, 'dt_ref_yr')) * Number(level.cell)) / CELL_REF_M;
    const kSt = Math.max(Math.trunc(Number(p.stages)), 1);
    const stepsTotal = Math.max(pyRound(Number(p.years) / dt), kSt);
    const cache = {};
    let m = null;
    for (let s = 0; s <= kSt; s++) {                     // kSt steps of the fall, then the cutting at the final bed
        const f = Math.min((s + 1) / kSt, 1.0);
        const [pinsK, mk] = await rv.pins(level, base, f, { cache, hold: ctx.index > 0 ? base.pin_w : null });
        if (m && m !== mk && !m.destroyed) m.destroy();
        m = mk;
        const sub = new RUN.StageContext({ plan: ctx.plan, index: ctx.index, level, prepass: null, fresh: false, role: 'grow',
            pins: pinsK, shared: ctx.shared, seed: ctx.seed, sea_level: ctx.sea_level, base_elevation_m: ctx.base_elevation_m,
            flatten: ctx.flatten, device: R, log: () => {}, values: ctx.values, grow_levels: ctx.grow_levels });
        const nK = s < kSt ? Math.floor(stepsTotal / (2 * kSt)) : stepsTotal - Math.floor(stepsTotal / (2 * kSt)) * kSt;
        await opFluvial(fields, level, { ...fl, steps: Math.max(nK, 1), min_steps: 1 }, seed, sub);
        for (const [name, fld] of Object.entries(pinsK)) if (fld !== base[name] && !fld.destroyed) fld.destroy();
        if (Ukeep) {
            const c = R.like(Ukeep);
            R.copy(Ukeep, c);
            fields.U = c;                                 // op_fluvial writes U x the factor back: keep the growth's
        }
    }
    // the course's channel, inherited by the finer levels: their fluvial stage holds it at the height it arrives at
    // and the soil hillslopes never raise it, so it stays the base level the fall made
    fields.river = 'river' in fields ? HS.ew(R, HS.EW.MAX, fields.river, m) : (() => { const c = R.like(m); R.copy(m, c); return c; })();
    fields.incised = m;
    const cutF = HS.ew(R, HS.EW.SUB, h0, fields.h);
    const st = await P.stats(cutF);
    const pos = HS.ew(R, HS.EW.MAX_K, cutF, null, null, 0.0);
    const cutMean = (await P.stats(pos)).mean;
    for (const fld of [cutF, pos, h0]) fld.destroy();
    if (Ukeep) Ukeep.destroy();
    if (!ctx.pins) for (const fld of Object.values(base)) fld.destroy();
    ctx.evolved = true;
    ctx.shared.incise = { bed_m: rv.bed_m, gradient: g, drop_m: drop, years: Number(p.years), cut_mean_m: Math.round(cutMean * 100) / 100 };
    ctx.log(`[terrain.fluvial] incise ${level.n}^2 @ ${fmtG(level.cell, 3)} m: the course dropped ${pyG(drop)} m below the ` +
        `surface's grade (bed ${rv.bed_m.toFixed(1)} m at its origin, falling ${(1000 * g).toFixed(2)} m/km) over ` +
        `${pyG(Number(p.years) / 1000)} kyr in ${kSt} steps (${stepsTotal} steps of ${dt.toFixed(0)} yr): mean cut ` +
        `${ctx.shared.incise.cut_mean_m} m, max ${st.max.toFixed(1)} m, ${(now() - t0).toFixed(2)} s`);
    return fields;
}


for (const op of [opUplift, opFluvial]) {
    op.evolves = true;              // run.js runs evolving ops on every coarse-to-fine pass, the rest once
    op.takesCtx = true;
}
opValleyFloor.post = true;          // run.js runs post ops once per level, after its last coarse-to-fine pass
opIncise.post = true;               // (and only on the finest growing level: ctx.last_grow)
for (const op of [opValleyFloor, opIncise]) op.takesCtx = true;

export const OPS = { uplift: opUplift, fluvial: opFluvial, valley_floor: opValleyFloor, incise: opIncise };

export {
    standaloneContext as standalone_context, edgePins as edge_pins, unitNoise as _unit_noise, faultZones as fault_zones,
    upliftField as uplift_field, compositeUplift as composite_uplift, compositeStart as composite_start,
    levelSpacing as level_spacing, lockBlock as lock_block, offsetBlockMeans as offset_block_means,
    creepSubsteps as creep_substeps, opUplift as op_uplift, opFluvial as op_fluvial, seaFlat as _sea_flat,
};
