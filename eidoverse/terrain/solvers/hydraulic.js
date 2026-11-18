// Port of blender/eidoblend/terrain/solvers/hydraulic.py at f90c6fc.
//
// Hydraulic detail: the virtual-pipe shallow-water erosion model (design section 4.4), run on the hero levels for a
// few thousand steps. It gives rain rills, small sediment fans and loose material settled at its repose angle; it is
// not the backbone (it cannot build a valley network in any affordable time).
//
//     op 'hydraulic'   Stage('hydraulic', {...}, levels='hero')     await opHydraulic(fields, level, params, seed, ctx)
//
// The model (Mei, Decaudin & Hu 2007; Jako 2011), one step = four GPU passes (kernels/pipes_*.wgsl, transcribed from
// the Blender GLSL):
//     pipes_flux       rain falls; the 8 pipes' outflow fluxes grow with the water-surface drop (isotropic weights,
//                      so rills do not comb along the grid axes) and are scaled so no cell sends more than it holds
//     pipes_water      the water update, the velocity, and erosion / deposition against the capacity
//                      C = Kc max(max(sin a, sin_min) min(|q|, q_cap) - qc, 0) depth_ramp: excess stream power
//                      (|q| = discharge per unit width) over a critical value, so sheet flow leaves a planar slope
//                      alone and flow gathered by the ground's micro-relief cuts rills; q_cap (rain x catchment_cells)
//                      keeps the parent's rivers from being cut again, and max_depth bounds the cut below the start
//     pipes_transport  suspended sediment moves with the water's own pipe fluxes (donor cell: what a cell sends its
//                      neighbour receives, bit for bit), then the water evaporates
//     pipes_thermal    loose debris above its repose angle slides to lower neighbours, mass-conserving; cohesive
//                      ground fails only above its own threshold (rock breakup's Sc), no deeper than a floor
// Everything runs in CELL UNITS (heights and lengths in cells), so Jako's numbers (dt 0.02, rain 0.012, Ks 0.5, Kd 1,
// Ke 0.015, pipe area 20, g 9.81) apply unchanged at every cell size. A rill is then a few cells wide and a fraction
// of a cell deep at any level, and each hero level adds its own octave of rills on top of the ones it inherits.
//
// Precision. The ground is held as the run's start surface b0 (a constant field) plus the change since (the state):
// a step's erosion of 1e-6 cells is kept in full where b0 is hundreds of cells. The water pass moves exactly what the
// rounded ground lost into suspension, the transport pass's sender and receivers share one exact expression, and the
// thermal pass carries its rounding into the next pass (Kahan): the GLSL's `precise` lines, kept as written by
// kernels/detail/exact.wgsl (WGSL has no `precise`; this machine's compiler folds them otherwise, measured).
//
// Loose and cohesive. `bed`, the top of the cohesive ground (rock, or soil in place), splits the ground: loose debris
// above it (deposits, talus) erodes at the full rate and slides at its repose angle; the cohesive ground erodes at
// `soil` on gentle ground and `rock` x the rock breakup's erodibility factor (`kfac`) on steep ground
// (soil_slope_deg), and never slides (unless rock_fail). A level without a bed field starts with no debris.
//
// The seed. Rills need something to gather the water: the op seeds world-space micro-relief (roughness x the cell,
// at 3 cells, on soil slopes, 40 % of it on flats), runs the water on it, and keeps the seed in the result only on
// levels of 0.5 m and finer (hummocks); on coarser levels only what the water did stays.
//
// Fields read: h (required), bed, kfac (rock breakup), Sc (the cohesive ground's threshold, with rock_fail), and the
// pins (the level runner's StageContext, or pin_w / pin_h fields; without them, on a level with a parent, the border
// ramp of core/grid.js holds the ground at its start value within 16 cells of the edge). Fields written: h, bed,
// wear (+= eroded depth, m), deposit (+= settled thickness, m), talus (+= what the cohesive ground shed, net, m; only
// with rock_fail), wet (water standing plus water passing in the last 20 % of the steps: depth + discharge x dt, m).
// The loop runs with open, draining edges; the pins are blended in once at the end (finish), so the border band
// fades from the detail to the parent's surface.
//
// Exports beside the op (what solvers/detail.js and later packages read, under hydraulic.py's names in camelCase):
// PARAMS, defaults, uniforms, PipeRun (PipeRunGPU), startFields (initial_state with par), rockness, microRelief, box,
// pinsFor, bandFade, anchor, anchorScaleM, finish, logOf, BIG_TAN, RUNNER_KEYS, OPS.
//
// The dispatch log (PORT_PLAN.md 5.7): Blender's kernels are world_noise_field (the micro-relief, once) and the four
// pipe passes `steps` times, in that order; every other dispatch is the port's own (kernels/detail/, core/prims.js
// and core/grid.js: the numpy code the Blender op runs on the CPU), marked as such in the log. No loop here stops on
// a convergence test.
//
// Where this differs from hydraulic.py, and why (PORT_PLAN.md 2.4, 3.2: every per-cell step runs on the GPU; each is
// checked against the numpy function it replaces, tests/detail/):
//   - The numpy twins (pipes_flux ... pipes_thermal, step_numpy, run_numpy, mass) are not ported: they are the
//     oracles, run in Blender's Python (tests/detail/blender_detail_fixtures.py). There is no CPU path, and no
//     `backend` argument.
//   - rockness, erodibility, the micro-relief's slope share, to_c, initial_state and the packs, back to metres, the
//     anchor and finish are kernels (kernels/detail/ramp, hydraulic_seed, to_cells, pipe_start, pipe_out, finish_h,
//     finish_add; core/prims.js boxBlur, which is _box; core/grid.js slopeDeg), in float32 where numpy is float64.
//     The smoothed slope is computed once (numpy computes the same array twice, for rockness and on_slope).
//   - The surfaces are carried as h_in plus changes, never as float32 sums until the last one (numpy holds h_new in
//     float64): finish() takes the change h_new - h_base and adds it to h_in once, after the anchor.
//   - The wet field's samples are summed on the GPU (kernels/detail/wet_acc.wgsl) instead of read back every 100
//     steps (PORT_PLAN.md 4.5: a solver loop never waits inside a step), so the port's readback log has none of the
//     run.state() / run.velocity() reads of Blender's.
//   - PipeRun's state(), talus(), accum() and velocity() return the GPU fields (read them with R.read); mass() is
//     async.
//   - The op is async, takes ctx as its fifth argument (run.js passes it), and returns the fields.

import * as Gd from '../core/grid.js';
import { KeyError, closeMatches, pyFormat, pyReprValue, pyRound, pyStr } from '../core/levels.js';
import { prims } from '../core/prims.js';
import * as N from '../core/world_noise.js';

export const BIG_TAN = Math.fround(1.0e6);             // a threshold no pair exceeds: rock that never fails in a pass
export const BOUND_OPEN = 0, BOUND_PERIODIC = 1, BOUND_PINNED = 2;   // common.wgsl

// name -> [default, unit, what it is]. Cell units are heights and lengths divided by the level's cell.
export const PARAMS = {
    steps: [3000, '', 'pipe-model steps per level (the design: 2,000-5,000)'],
    dt: [0.02, 's', 'model seconds per step (Jako)'],
    rain: [0.012, 'cells/s', "rain depth per model second (Jako's Kr)"],
    rain_cover: [1.0, '', 'the fraction of cells rained on each step (below 1: random cells, the same mean)'],
    pipe: [196.2, '', 'pipe cross-section x gravity / pipe length (Jako: 20 x 9.81 / 1)'],
    damp: [0.5, '1/s', 'flux friction: a terminal speed on long slopes, and standing water settles'],
    Kc: [0.04, 's/cell', 'transport capacity per unit of excess stream power'],
    Ks: [0.5, '1/s', 'erosion (dissolving) rate (Jako)'],
    Kd: [1.0, '1/s', 'deposition rate (Jako)'],
    Ke: [0.015, '1/s', 'evaporation (Jako)'],
    sin_min: [0.02, '', 'the smallest tilt the capacity sees'],
    qc: [0.3, 'cells^2/s', 'critical stream power (tilt x discharge per unit width): sheet flow under it does ' +
                           'not erode, gathered flow over it cuts rills'],
    catchment_cells: [150.0, 'cells', 'the capacity sees at most the discharge of this much slope length upstream ' +
                                      "(rain x cells): rills and gullies, not the parent's rivers cut again"],
    max_depth: [0.5, 'cells', 'the deepest the pass cuts below the surface it started from'],
    dmax: [0.5, 'cells', 'water deeper than this carries nothing (ponds and lakes drop their load)'],
    soil: [0.5, '', 'erodibility of soil in place, relative to loose debris'],
    rock: [0.05, '', 'erodibility of rock relative to loose debris (x the rock breakup factor kfac)'],
    soil_slope_deg: [[35.0, 50.0], 'deg', 'ground is soil below the first slope, rock above the second'],
    max_step: [0.01, 'cells', 'the most a cell is lowered in one step'],
    thermal_rate: [0.06, '', 'the thermal pass rate (<= 1/8)'],
    repose_deg: [35.0, 'deg', 'repose angle of loose debris (talus, deposits)'],
    rock_fail: [false, 'bool', 'the cohesive ground also fails in the thermal pass at its threshold (the Sc ' +
                               'field); else only loose debris moves'],
    roughness: [0.12, 'cells', 'micro-relief seeded on soil slopes before the rain (standard deviation): the ' +
                               'clods, stones and roots a DEM cannot hold, which the water gathers into rills'],
    roughness_cells: [3.0, 'cells', 'the micro-relief wavelength'],
    roughness_slope_deg: [[8.0, 20.0], 'deg', 'the micro-relief grows to full between these slopes, where water ' +
                                              'gathers it into rills'],
    roughness_flat: [0.4, '', 'its share on gentle ground: soil hummocks, no rills (the swissALTI3D 0.5 m truth ' +
                              'around the Lauterbrunnen eye spot holds about 5 cm of relief within 2 m on the floor)'],
    roughness_keep_m: [[0.5, 2.0], 'm', 'the micro-relief is a seed that steers the water; the result keeps it on ' +
                                        'levels with cells up to the first size (sub-metre hummocks) and drops it ' +
                                        'from the second up (a 12 m stipple on a 4 m level reads as orange peel, ' +
                                        'not ground): there only what the water did stays'],
    outflow: [true, 'bool', 'water leaves through the level edge where the ground runs downhill'],
    anchor: [true, 'bool', 'keep only the change narrower than anchor_m (anchor): detail without moving the ' +
                           'landform the levels above hold'],
    anchor_m: [null, 'm', "the anchor's scale (None: 1.5 x the main level's cell, 12 m at Lauterbrunnen)"],
    wet_tail: [0.2, '', 'the last fraction of the steps averaged into the wet field'],
};

export const RUNNER_KEYS = ['enabled'];                 // stage parameters the level runner reads itself (run.js)

/** The op's parameters: PARAMS defaults overridden by `params`; an unknown name raises naming the nearest. */
export function defaults(params = null) {
    const out = Object.fromEntries(Object.entries(PARAMS).map(([k, v]) => [k, v[0]]));
    for (const [k, v] of Object.entries(params ?? {})) {
        if (RUNNER_KEYS.includes(k)) continue;
        if (!(k in PARAMS)) {
            const near = closeMatches(k, Object.keys(PARAMS), 3);
            throw new KeyError(`hydraulic: no parameter ${pyReprValue(k)}` + (near.length ? `; did you mean ${pyStr(near)}?` :
                `; valid: ${pyStr(Object.keys(PARAMS).sort())}`));
        }
        out[k] = v;
    }
    return out;
}


// --------------------------------------------------------------------------------------------- the stepping ---

/** The kernels' uniforms for step `step` (one object; each pass takes the ones it declares). */
export function uniforms(p, step, seed, mode, outflow = true) {
    return { uDt: p.dt, uRain: p.rain, uRainP: p.rain_cover, uPipe: p.pipe, uDamp: p.damp, uKc: p.Kc, uKs: p.Ks,
        uKd: p.Kd, uKe: p.Ke, uSinMin: p.sin_min, uQc: p.qc, uQcap: p.rain * p.catchment_cells, uMaxDepth: p.max_depth,
        uDmax: p.dmax, uRock: 1.0, uMaxStep: p.max_step, uRate: p.thermal_rate, uStep: Math.trunc(step),
        uSeed: Math.trunc(seed), uBound: Math.trunc(mode), uOutflow: outflow ? 1 : 0 };
}

function pick(kernel, u) {
    const out = {};
    for (const n of kernel.uniformNames) out[n] = u[n];
    return out;
}

// a runner's 1 x 1 rgba32f stand-in, for the samplers a kernel's mode does not read (core/grid.js dummies has the
// 1- and 2-channel ones)
const DUMMY4 = new WeakMap();
export function dummy4(R) {
    let d = DUMMY4.get(R);
    if (!d) {
        d = R.field(1, 1, 4);
        DUMMY4.set(R, d);
    }
    return d;
}

/** The pipe model's start state and the thermal pass's parameters (initial_state with d = s = 0, and
 * T.rgba(sc, rep, floor)), from b0 (T.rgba(b0), detail/to_cells' output) and the cohesive top `bed` (cell units, a
 * field or null: no debris). sc: a field, or a number everywhere. { state, par }: rgba32f fields the caller owns. */
export function startFields(R, b0, { bed = null, sc = BIG_TAN, rep, floor = -1.0e6 } = {}) {
    const D = Gd.dummies(R);
    const state = R.field(b0.h, b0.w, 4), par = R.field(b0.h, b0.w, 4);
    const scField = typeof sc === 'number' ? null : sc;
    R.run('detail/pipe_start', { b0, bed: bed ?? D.f1, sc: scField ?? D.f1 }, { outState: state, outPar: par },
        { uSc: scField ? 0.0 : sc, uRep: rep, uFloor: floor, uHasBed: bed ? 1 : 0, uHasSc: scField ? 1 : 0 });
    return { state, par };
}

/** The pipe model's fields on the GPU and its step loop (hydraulic.py PipeRunGPU, production). base: T.rgba(b0)
 * (cell units); state: the start state (the run owns it from here); src, par, pin: rgba32f fields the caller owns
 * (pin as (pin_w, pin_h - b0)). */
export class PipeRun {
    constructor(R, base, state, src, par, pin) {
        this.R = R;
        const [h, w] = [base.h, base.w];
        const f4 = () => R.field(h, w, 4);
        this.S = [state, f4(), f4()];
        this.base = base;
        this.FA = [f4(), f4()];
        this.FB = [f4(), f4()];
        this.V = f4();
        this.TA = [f4(), f4()];
        Object.assign(this, { src, par, pin });
        this.k = { flux: R.kernel('pipes_flux'), water: R.kernel('pipes_water'), transport: R.kernel('pipes_transport'),
            thermal: R.kernel('pipes_thermal') };
    }

    step(p, i, seed, mode, outflow = true, thermal = true) {
        const R = this.R, k = this.k;
        const u = uniforms(p, i, seed, mode, outflow);
        const [S0, S1, S2] = this.S;
        R.run(k.flux, { st: S0, base: this.base, fa: this.FA[0], fb: this.FB[0], src: this.src },
            { outA: this.FA[1], outB: this.FB[1] }, pick(k.flux, u));
        R.run(k.water, { st: S0, base: this.base, fa: this.FA[1], fb: this.FB[1], src: this.src, pin: this.pin },
            { outS: S1, outV: this.V }, pick(k.water, u));
        R.run(k.transport, { st2: S1, st0: S0, fa: this.FA[1], fb: this.FB[1], src: this.src },
            { outS: S2 }, pick(k.transport, u));
        if (thermal) {
            R.run(k.thermal, { st: S2, base: this.base, par: this.par, pin: this.pin, tacc: this.TA[0] },
                { outS: S0, outT: this.TA[1] }, pick(k.thermal, u));
            this.TA.reverse();
        } else {
            this.S = [S2, S0, S1];
        }
        this.FA.reverse();
        this.FB.reverse();
    }

    /** The state field: (delta, d, s, bed - base), cell units. */
    state() { return this.S[0]; }

    /** The thermal accumulator (x: net change by sliding, y: the rounding carried). */
    accum() { return this.TA[0]; }

    talus() { return this.TA[0]; }

    /** The last water pass's (vx, vy, discharge per unit width, capacity). */
    velocity() { return this.V; }

    /** The conserved total, cell units: the ground's change + the suspended sediment + the rounding the thermal pass
     * still carries (hydraulic.py mass), summed in float64 on the CPU after one readback (tests). */
    async mass() {
        const [st, ta] = await this.R.readAll([this.S[0], this.TA[0]]);
        let s = 0;
        for (let i = 0; i < st.length; i += 4) s += st[i] + st[i + 2] + ta[i + 1];
        return s;
    }

    /** Release the run's own fields (not base, src, par or pin). */
    destroy() {
        for (const f of [...this.S, ...this.FA, ...this.FB, this.V, ...this.TA]) if (!f.destroyed) f.destroy();
    }
}


// ------------------------------------------------------------------------------------------------ helpers ---

/** Separable box blur of radius r cells, edges clamped (hydraulic.py _box: y then x; core/prims.js boxBlur). A new
 * field. */
export function box(a, r) {
    return prims(a.runner).boxBlur(a, r, { axes: 'yx' });
}

/** The smoothstep ramp of a field between lo and lo + den: a + b x smoothstep (kernels/detail/ramp.wgsl). */
export function ramp(src, lo, den, a = 0.0, b = 1.0) {
    const R = src.runner;
    const out = R.field(src.h, src.w, 1);
    R.run('detail/ramp', { src }, { outF: out }, { uLo: lo, uDen: den, uA: a, uB: b });
    return out;
}

/** The slope in degrees of the surface smoothed over `r` cells (core/grid.js slopeDeg of box(h, r)). A new field. */
export function smoothedSlope(h, cell, r) {
    const hs = box(h, r);
    const s = Gd.slopeDeg(hs, cell);
    hs.destroy();
    return s;
}

/** 0 on soil, 1 on rock: a smoothstep of the slope (degrees, on the surface smoothed over 2 cells, so a rill does
 * not flip it) between the two slopes. A new field (hydraulic.py rockness). */
export function rockness(h, cell, slopeDeg) {
    const s = smoothedSlope(h, cell, 2);
    const [lo, hi] = slopeDeg;
    const t = ramp(s, lo, Math.max(hi - lo, 1e-6));
    s.destroy();
    return t;
}

/** World-space micro-relief in metres (fbm of 2 octaves, standard deviation ampM): the same place gets the same bumps
 * on every run, and each level its own octave. A new field (hydraulic.py micro_relief, field_gpu). */
export function microRelief(R, level, seed, ampM, wavelengthM) {
    const spec = { kind: 'fbm', wavelength_m: Number(wavelengthM), octaves: 2, amp: 3.0 * Number(ampM) };
    return N.fieldGpu(R, spec, level, seed);
}

/** { pin_w, pin_h, made }: the level runner's pins (its StageContext, or pin fields) when it has them; else, on a
 * level with a parent, the border band of core/grid.js (weight 1 on the edge to 0 at `band` cells in) holding the
 * ground at its value when the stage started (hStart); on the coarsest level (no parent) no weights (pin_w null)
 * and pin_h hStart. `made`: the fields made here, for the caller to release (hydraulic.py pins_for). */
export function pinsFor(fields, level, hStart, ctx = null) {
    const pins = ctx?.pins ?? null;
    if (pins && pins.pin_w && pins.pin_h) return { pin_w: pins.pin_w, pin_h: pins.pin_h, made: [] };
    if ('pin_w' in fields && 'pin_h' in fields) return { pin_w: fields.pin_w, pin_h: fields.pin_h, made: [] };
    if (level.parent === null || level.parent === undefined) return { pin_w: null, pin_h: hStart, made: [] };
    const w = Gd.borderRamp(hStart.runner, level.n, level.band ?? 16);
    return { pin_w: w, pin_h: hStart, made: [w] };
}

/** 1 - the pin weight: where a detail op may put its relief at full strength. A new field (hydraulic.py band_fade;
 * the ops themselves fold it into their kernels). */
export function bandFade(fields, level, ctx = null) {
    const R = fields.R, D = Gd.dummies(R);
    const { pin_w, made } = pinsFor(fields, level, D.f1, ctx);
    const one = Gd.fill(R, [level.n, level.n], 1.0);
    if (!pin_w) return one;
    // finish_add's wet mode is x (1 - clip(pin_w, 0, 1)): with x = 1, the fade itself
    const out = R.field(level.n, level.n, 1);
    R.run('detail/finish_add', { old: D.f1, x: one, pw: pin_w }, { outF: out }, { uMode: 3, uHasOld: 0, uHasPin: 1 });
    one.destroy();
    for (const f of made) f.destroy();
    return out;
}

/** The low-pass anchor() removes: three box passes of radius max(1, round(0.4 scale)) cells (a near-Gaussian of
 * sigma about scale / 2). A new field. */
export function anchorLowpass(change, scaleCells) {
    const r = Math.max(1, Math.trunc(pyRound(0.4 * Number(scaleCells))));
    return prims(change.runner).boxBlur(change, r, { axes: 'yx', passes: 3 });
}

/** The part of a level's change narrower than `scaleCells`: the change minus its low-pass (hydraulic.py anchor). A
 * detail op that keeps only this adds rills, couloirs and hummocks but leaves broad change to the levels above, which
 * hold the landform: on a real place, the DEM. A new field. */
export function anchor(change, scaleCells) {
    const lp = anchorLowpass(change, scaleCells);
    const out = Gd.arith(change.runner, 'sub', change, lp);
    lp.destroy();
    return out;
}

/** The anchor's scale in metres: given, or 1.5 main-level cells (the main cell is cell x 2^-depth on a hero level;
 * 12 m at Lauterbrunnen's 8 m DEM), else three of the level's cells (hydraulic.py anchor_scale_m). */
export function anchorScaleM(level, pAnchorM = null) {
    if (pAnchorM) return Number(pAnchorM);
    const depth = Math.trunc(Number(level.depth ?? 0) || 0);
    if (depth < 0) return 1.5 * Number(level.cell) * 2.0 ** (-depth);
    return 3.0 * Number(level.cell);
}

/** A detail op's result, written into the fields (hydraulic.py finish): with anchorM (metres; on a level with a
 * parent), only the change narrower than that (anchor); h blended to the pins once (h = h_new keep + pin_h w: the
 * border band fades from the detail to its parent's surface), bed under it, and wear / deposit / talus added from the
 * process change h_new - h_base (faded the same way: where the processes acted, whatever the anchor kept).
 *
 * Where numpy takes the surfaces h_new, bed_new and h_base, this takes h_in and changes, so float32 keeps the
 * change's digits (kernels/detail/finish_h.wgsl):
 *     hIn      the height the op started from (a field)        seed, seedK   h_base = hIn + seedK seed (seed null: 0)
 *     change   h_new - h_base (a field); abs: true makes it h_new itself (op_planation's whole new surface), and
 *              absChange is then h_new - h_base for wear and deposit
 *     bed      bed_new - h_base (bedMode 0), bed_new (1) or null: bed_new = h_new (2)
 *     pinW, pinH, talus, wet, level, anchorM   as numpy's
 * Records the kernels and returns { h, bed, wear, deposit, talus, wet, apply() }: the new fields, and apply(), which
 * puts them into `fields` (releasing what those names held), so a caller can read the old h first. */
export function finish(fields, o) {
    const R = fields.R, D = Gd.dummies(R);
    const { hIn, seed = null, seedK = 0.0, change, abs = false, absChange = null, bed = null, bedMode = bed ? 0 : 2,
        pinW = null, pinH = null, talus = null, wet = null, level = null, anchorM = null } = o;
    const temp = [];
    let lp = null;
    if (anchorM && level && level.parent !== null && level.parent !== undefined) {
        lp = anchorLowpass(change, Number(anchorM) / Number(level.cell));
        temp.push(lp);
    }
    const h = R.like(hIn), bedOut = R.like(hIn);
    R.run('detail/finish_h', { hin: hIn, seed: seed ?? D.f1, x: change, lp: lp ?? D.f1, bed: bed ?? D.f1,
        pw: pinW ?? D.f1, ph: pinH ?? D.f1 }, { outH: h, outBed: bedOut },
    { uSeedK: seed ? seedK : 0.0, uAbs: abs ? 1 : 0, uHasLp: lp ? 1 : 0, uBedMode: bedMode, uHasPin: pinW ? 1 : 0 });
    const add = (mode, old, x) => {
        const out = R.like(hIn);
        R.run('detail/finish_add', { old: old ?? D.f1, x, pw: pinW ?? D.f1 }, { outF: out },
            { uMode: mode, uHasOld: old ? 1 : 0, uHasPin: pinW ? 1 : 0 });
        return out;
    };
    const dh = abs ? absChange : change;
    const res = { h, bed: bedOut, wear: add(0, 'wear' in fields ? fields.wear : null, dh),
        deposit: add(1, 'deposit' in fields ? fields.deposit : null, dh), talus: null, wet: null };
    if (talus) res.talus = add(2, 'talus' in fields ? fields.talus : null, talus);
    if (wet) res.wet = add(3, null, wet);
    for (const f of temp) f.destroy();
    res.apply = () => {
        fields.h = res.h;
        fields.bed = res.bed;
        fields.wear = res.wear;
        fields.deposit = res.deposit;
        if (res.talus) fields.talus = res.talus;
        if (res.wet) fields.wet = res.wet;
        return fields;
    };
    return res;
}

/** The op's log: `log` when given, the StageContext's with the prefix, else console.log with it (hydraulic.py
 * log_of). */
export function logOf(log, ctx, prefix) {
    if (log) return log;
    if (ctx && ctx.log) return (m) => ctx.log(prefix + m);
    return (m) => console.log(prefix + m);
}

/** np.percentile(x, q) of one channel of a log_dh field and its float64 rule (a log line's numbers). */
export async function logPercentile(f, q, channel) {
    return prims(f.runner).percentile(f, [q], { channel, dtype: 'float64' }).then((v) => v[0]);
}

/** The log_dh field of a - b - seedK c (kernels/detail/log_dh.wgsl): (max(-d, 0), max(d, 0), |d|, d). */
export function logDh(a, b = null, c = null, seedK = 0.0) {
    const R = a.runner, D = Gd.dummies(R);
    const out = R.field(a.h, a.w, 4);
    R.run('detail/log_dh', { a, b: b ?? D.f1, c: c ?? D.f1 }, { outL: out }, { uSeedK: c ? seedK : 0.0, uHasB: b ? 1 : 0 });
    return out;
}


// ------------------------------------------------------------------------------------------------- the op ---

/** Stage op 'hydraulic' (module doc): runs the pipe model on this level's fields in place. ctx: the level runner's
 * StageContext (its pins and log), when run.js calls it. */
export async function opHydraulic(fields, level, params = null, seed = 0, ctx = null) {
    const log = logOf(null, ctx, '[terrain.hydraulic] ');
    const p = defaults(params);
    const t0 = performance.now();
    const R = fields.R, D = Gd.dummies(R), P = prims(R);
    const cell = Number(level.cell);
    const hIn = fields.h;
    const [nh, nw] = [hIn.h, hIn.w];
    const temp = [];
    const keep = (f) => { temp.push(f); return f; };
    const scratch = () => keep(R.field(1, 1, 1));
    try {
        const href = (await P.stats(hIn)).min;                       // float(h_in.min()): exact
        // the slope of the surface smoothed over 2 cells: rockness and the micro-relief's share both read it
        const sDeg = keep(smoothedSlope(hIn, cell, 2));
        const [lo, hi] = p.soil_slope_deg;
        const rk = keep(ramp(sDeg, lo, Math.max(hi - lo, 1e-6)));
        const kf = 'kfac' in fields ? fields.kfac : null;
        const { pin_w: pw, pin_h: ph, made } = pinsFor(fields, level, hIn, ctx);
        temp.push(...made);
        // in the border band the ground stops eroding (ramping with the pin weight): water still drains out through
        // the open edge, but cuts no channels along it for the pin blend to half-erase (they showed as streaks in
        // the band)
        let r = null, on = null;
        if (p.roughness > 0) {
            r = keep(microRelief(R, level, Math.trunc(seed) + 7001, p.roughness * cell, p.roughness_cells * cell));
            const [rlo, rhi] = p.roughness_slope_deg;
            const flat = Number(p.roughness_flat);
            on = keep(ramp(sDeg, rlo, Math.max(rhi - rlo, 1e-6), flat, 1.0 - flat));
        }
        const erod = keep(R.field(nh, nw, 1));
        const bump = r ? keep(R.field(nh, nw, 1)) : null;
        R.run('detail/hydraulic_seed', { rk, onslope: on ?? D.f1, r: r ?? D.f1, kf: kf ?? D.f1, pw: pw ?? D.f1 },
            { outE: erod, outB: bump ?? scratch() },
            { uSoil: p.soil, uRock: p.rock, uHasKf: kf ? 1 : 0, uHasR: r ? 1 : 0, uHasPw: pw ? 1 : 0 });
        const one = keep(Gd.fill(R, [nh, nw], 1.0));
        const src = keep(R.pack({ one, erod }, ['one', null, 'erod', null]));
        // the start in cell units: b0 = to_c(h0), the cohesive top, the pins
        const b0 = keep(R.field(nh, nw, 4));
        R.run('detail/to_cells', { h: hIn, add: bump ?? D.f1, cap: D.f1, pw: D.f1 }, { outF: b0 },
            { uHref: href, uCell: cell, uHasAdd: bump ? 1 : 0, uHasCap: 0, uPin: 0 });
        let bedC = null;
        if ('bed' in fields) {
            bedC = keep(R.field(nh, nw, 4));
            R.run('detail/to_cells', { h: fields.bed, add: D.f1, cap: b0, pw: D.f1 }, { outF: bedC },
                { uHref: href, uCell: cell, uHasAdd: 0, uHasCap: 1, uPin: 0 });
        }
        const pin = keep(R.field(nh, nw, 4));
        R.run('detail/to_cells', { h: ph, add: D.f1, cap: b0, pw: pw ?? D.f1 }, { outF: pin },
            { uHref: href, uCell: cell, uHasAdd: 0, uHasCap: 0, uPin: pw ? 1 : 2 });
        const rep = Math.fround(Gd.tanDeg(Number(p.repose_deg)));
        const sc = p.rock_fail && 'Sc' in fields ? fields.Sc : BIG_TAN;
        const { state, par } = startFields(R, b0, { bed: bedC, sc, rep, floor: -1.0e6 });
        keep(par);
        // the loop runs open (water leaves downhill edges) and the pins are blended in ONCE at the end: applied every
        // step, a pin of any weight above 0 wins over thousands of steps and the whole 16-cell band would lose its
        // detail
        const mode = BOUND_OPEN;
        const steps = Math.trunc(p.steps);
        const tail0 = Math.trunc(steps * (1.0 - Number(p.wet_tail)));
        const dt = Number(p.dt);
        const run = new PipeRun(R, b0, state, src, par, pin);
        let wet = null, nwet = 0;
        try {
            for (let i = 0; i < steps; i++) {
                run.step(p, i, seed, mode, p.outflow);
                // the wet field: water standing (depth) plus water passing (discharge per unit width x one step),
                // cell units, summed on the GPU (module doc)
                if (i >= tail0 && (i - tail0) % 100 === 0) {
                    const w2 = R.field(nh, nw, 1);
                    R.run('detail/wet_acc', { st: run.state(), vel: run.velocity(), old: wet ?? D.f1 }, { outW: w2 },
                        { uDt: dt, uHasOld: wet ? 1 : 0 });
                    if (wet) wet.destroy();
                    wet = w2;
                    nwet++;
                }
            }
            if (wet) keep(wet);
            // back to metres: the start surface + the change (+ what is still suspended, which settles where it is).
            // The seed stays only on fine levels (roughness_keep_m): elsewhere the change goes onto the unseeded
            // surface
            const [klo, khi] = p.roughness_keep_m;
            const t = Math.min(Math.max((cell - klo) / Math.max(khi - klo, 1e-9), 0.0), 1.0);
            const seedK = 1.0 - t * t * (3.0 - 2.0 * t);
            const dH = keep(R.field(nh, nw, 1)), dBed = keep(R.field(nh, nw, 1));
            const talus = p.rock_fail ? keep(R.field(nh, nw, 1)) : null;
            const wetM = keep(R.field(nh, nw, 1));
            R.run('detail/pipe_out', { st: run.state(), ta: run.accum(), add: D.f1, wet: wet ?? D.f1 },
                { outDH: dH, outDB: dBed, outTal: talus ?? scratch(), outWet: wetM },
                { uCell: cell, uNWet: Math.max(nwet, 1), uHasAdd: 0, uTalus: talus ? 1 : 0, uWet: wet ? 1 : 0 });
            // without rock_fail only deposits slide, so what the thermal pass moved stays in `deposit`; with it, what
            // the cohesive ground shed is talus
            const res = finish(fields, { hIn, seed: bump, seedK, change: dH, bed: dBed, bedMode: 0, pinW: pw, pinH: ph,
                talus, wet: wetM, level, anchorM: p.anchor ? anchorScaleM(level, p.anchor_m) : null });
            const L = keep(logDh(res.h, hIn, bump, seedK));             // dh = fields['h'] - h_base
            res.apply();
            const eroded = await logPercentile(L, 99, 0), deposited = await logPercentile(L, 99, 1);
            const mean = (await P.stats(L, { channel: 2 })).mean;
            const sec = (performance.now() - t0) / 1000;
            log(`level ${level.index} (${pyFormat(cell, '.3g')} m x${level.n}): ${steps} steps in ${pyFormat(sec, '.1f')} s; ` +
                `eroded ${pyFormat(eroded, '.3f')} m p99, deposited ${pyFormat(deposited, '.3f')} m p99, |dh| mean ` +
                `${pyFormat(mean, '.4f')} m`);
        } finally {
            run.destroy();
        }
        return fields;
    } finally {
        for (const f of temp) if (!f.destroyed) f.destroy();
    }
}
opHydraulic.takesCtx = true;

export const OPS = { hydraulic: opHydraulic };
export {
    opHydraulic as op_hydraulic, PipeRun as PipeRunGPU, anchorScaleM as anchor_scale_m, pinsFor as pins_for,
    bandFade as band_fade, logOf as log_of, microRelief as micro_relief, startFields as initial_state,
};
