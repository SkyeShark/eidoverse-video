// Port of blender/eidoblend/terrain/solvers/hillslope.py at f90c6fc.
//
// Hillslopes on their own (design sections 4.1-4.2): creep and threshold failure, the passes the fluvial backbone
// runs every step, as standalone stages.
//
//     stage ops (OPS; op(fields, level, params, seed, ctx)):
//       'creep'      age a surface. Linear diffusion by kappa_t_m2 (kappa t, m^2: cinder cones, craters; done
//                    exactly as a Gaussian of sigma^2 = 2 kappa t), or nonlinear creep (Roering 1999) with D (m^2/yr)
//                    for years, on the GPU (kernels/creep.wgsl)
//       'talus'      debris at repose: the threshold pass at repose_deg (default 35) on loose material only (h - bed),
//                    so rock walls keep their own angle. On a level with no bed (a real DEM), the threshold is never
//                    below the inherited surface's own slope, so only new detail relaxes and the landform stands
//       'threshold'  slopes failing at their angle: the threshold pass at threshold_deg (or the level's Sc field, an
//                    earlier stage's: karst's limestone 75 degrees), every cell
//       'soil_hills' soil-mantled hillslopes at steady state between the channels the level's erosion cut: linear
//                    creep with uplift, div(D grad h) = -U, so every hill is a smooth convex dome (Culling's parabola),
//                    with lee slopes steeper than stoss slopes when asked (aspect-dependent creep), and rill lines
//                    cut along the channels on fine levels (opSoilHills)
//
// The kernels are kernels/creep.wgsl, threshold.wgsl, threshold_excess.wgsl and soil_jacobi.wgsl (the last two the
// inline kernels EXCESS and SOIL of hillslope.py, PORT_PLAN.md 3.3); their numpy twins stay in Python (the oracles,
// tests/parity/fixtures.py). Both creep and threshold exchange material symmetrically between every neighbour pair, so
// the sum of h is conserved in the open and periodic modes (tests/fluvial/kernels_test.mjs checks it to 1e-5). Talus
// thickness accumulates in `talus` (the scree mask and the rock scatter read it); losses take talus, then deposit,
// then other loose cover, then rock (`wear`).
//
// Where this differs from hillslope.py, and why (PORT_PLAN.md 2.4, 3.2: every per-cell step runs on the GPU):
//   - Fields are core/gpu.js fields (fields.h, a level's Fields); the ops are async (a readback decides a solve's
//     last change, a percentile, a relaxation's end). Ops get the runner from ctx.device (the level runner's), else
//     from the fields.
//   - The numpy expressions over whole levels are the port's own kernels in kernels/fluvial/ (each names the numpy
//     line it replaces): the state packs (state.wgsl), the element-wise steps (ew.wgsl), soil_solve's coarse grids
//     (soil_block2.wgsl: numpy's float64 2 x 2 means, here float32, the means of four values rounded once), the
//     channel masks (soil_chan.wgsl, with numpy's exact float64 comparisons), _downstream (soil_down.wgsl: the same
//     fixed point, reached as a gather relaxation with a convergence count every chunk instead of numpy's scatter
//     passes), the hold weights (soil_hold.wgsl) and the rills (soil_rill.wgsl). They are not Blender kernels, so
//     the dispatch-log comparison sets them aside (PORT_PLAN.md 5.7).
//   - gaussian_blur is core/prims.js gaussianBlur (mode 'reflect': numpy's FFT blur of the field padded by reflection
//     ceil(4 sigma), as a direct convolution with the FFT's own kernel).
//   - soil_solve's last change, max |cur - prev|, is a GPU reduction read back (4 bytes) instead of two whole fields.
//   - op_soil_hills' seeded surface h + seed_m nz free is float64 in numpy and float32 here (its depressions are then
//     filled as float32 values); numpy's np.gradient and np.hypot of the routing surface are float32 central
//     differences (core/grid.js gradient) and a float32 hypot, and the 90th percentile of that hypot is numpy's
//     float64 interpolation of the exact order statistics (core/prims.js).
//   - Blender's _Pass and threshold_pass keep their names (Pass, thresholdPass); snake_case aliases are exported.
//   - The convergence loop this module names for the dispatch-log comparison (PORT_PLAN.md 5.7): none of its Blender
//     kernels runs in one (soil_solve's iterations are a function of the level, the stages' loops are counted);
//     opSoilHills' drainage area is hydro.js routeToConvergence's (route_area, every 128 iterations).

import * as Gd from '../core/grid.js';
import { prims } from '../core/prims.js';
import * as N from '../core/world_noise.js';
import * as FL from './fluvial.js';
import * as HY from './hydro.js';

const DEG = Math.PI / 180.0;
const tanDeg = (d) => Math.tan(Number(d) * DEG);
/** The convergence loops of this module's ops, by op and kernel (PORT_PLAN.md 5.7): their counts may differ by whole
 * intervals. soil_hills routes its channel test's drainage area to convergence (hydro.js routeToConvergence). */
export const CONVERGENCE_LOOPS = Object.freeze({ 'soil_hills|route_area': 128 });
const runnerOf = (fields, ctx) => (ctx && ctx.device) || fields.h?.runner || fields.R;
const round3 = (s) => Math.round(s * 1000) / 1000;
const now = () => performance.now() / 1000;


// ==================================================================================================== helpers ===

const KERNELS = new WeakMap();
/** The runner's Kernel of a kernel's name, looked up once per runner: R.run given a name reads the kernel's file and
 * parses its `//!` header on every call (core/gpu.js kernel(): about 0.15 ms a dispatch on the benchmark's machine,
 * more than the GPU's own time of a 1024^2 step's whole nine passes), so every loop here passes the Kernel. */
export function kernelOf(R, name) {
    let m = KERNELS.get(R);
    if (!m) KERNELS.set(R, (m = new Map()));
    let k = m.get(name);
    if (!k) m.set(name, (k = R.kernel(name)));
    return k;
}

/** One element-wise step (kernels/fluvial/ew.wgsl): a new r32f field of `shape` (default a's). */
export function ew(R, mode, a = null, b = null, c = null, k0 = 0.0, k1 = 0.0, shape = null) {
    const D = Gd.dummies(R);
    const ref = a ?? b ?? c;
    const [h, w] = shape ?? [ref.h, ref.w];
    const out = R.field(h, w, 1);
    R.run(kernelOf(R, 'fluvial/ew'), { a: a ?? D.f1, b: b ?? D.f1, c: c ?? D.f1 }, { outF: out },
        { uMode: mode, uK0: Number(k0), uK1: Number(k1) });
    return out;
}
export const EW = Object.freeze({ ADD_FREE: 0, SHIFT_SCALE: 1, HYPOT: 2, MAX_K_HYPOT: 3, MAX_A_HYPOT: 4, PIN: 5, MIN: 6,
    MIN_DIFF: 7, SUB: 8, CAP_BLEND: 9, LAKE: 11, SCALE_DIV: 12, MAX_K: 13, SCALE: 14, MAX: 15, MASK_ZERO: 16,
    BED_MIN: 17, CLAMP_POS: 18 });

/** The two state packs of a fields set (kernels/fluvial/state.wgsl): S = (h, A, qs, 0), M = (wear, deposit, talus,
 * max(h - bed, 0)) as pairs. area: what a missing A is (FluvialRun cell^2, _Pass 0). */
export function statePairs(R, fields, area = 0.0) {
    const D = Gd.dummies(R);
    const h = fields.h, n = [h.h, h.w];
    const S = R.pair(n[0], n[1], 4), M = R.pair(n[0], n[1], 4);
    const has = (k) => (k in fields && fields[k] ? 1 : 0);
    R.run('fluvial/state', { h, A: fields.A ?? D.f1, qs: fields.qs ?? D.f1, bed: fields.bed ?? D.f1, wear: fields.wear ?? D.f1,
        dep: fields.deposit ?? D.f1, tal: fields.talus ?? D.f1 }, { outS: S.src, outM: M.src },
    { uHas: [has('A'), has('qs'), has('bed'), has('wear') | (has('deposit') << 1) | (has('talus') << 2)], uArea: Math.fround(area) });
    return { S, M };
}

/** The pins pack (pin_w, pin_h, A_in, qs_in) of a pins object of fields. */
export function pinsPack(R, pins) {
    return R.pack(pins, ['pin_w', 'pin_h', 'A_in', 'qs_in']);
}


// ================================================================================================= the passes ===

/** One threshold iteration on the GPU (hillslope.py threshold_pass): (isotropic) the excess pass into `phi` (made
 * when null), then the exchange; S and M are ping-pong pairs, swapped. Returns the phi field for the next call (in
 * pair mode the 1 x 1 stand-in Blender binds). */
export function thresholdPass(R, S, M, P, Q, cell, rate, looseOnly, bound, iso = 1, phi = null) {
    let phis;
    if (iso) {
        if (phi === null || phi.h !== S.src.h || phi.w !== S.src.w) phi = R.field(S.src.h, S.src.w, 1);
        R.run(kernelOf(R, 'threshold_excess'), { st: S.src, par: P }, { outP: phi }, { uDx: Number(cell), uBound: Math.trunc(bound) });
        phis = phi;
    } else {
        phis = phi ?? Gd.dummies(R).f1;
    }
    R.run(kernelOf(R, 'threshold'), { st: S.src, par: P, pin: Q, mk: M.src, phiT: phis }, { outS: S.dst, outM: M.dst },
        { uDx: Number(cell), uRate: Number(rate), uLoose: looseOnly ? 1 : 0, uIso: Math.trunc(iso), uBound: Math.trunc(bound) });
    S.swap();
    M.swap();
    return phis;
}

/** The state of a standalone hillslope stage on the GPU (hillslope.py _Pass): h and the accumulators, the threshold
 * field (Sc: a field, or null for a par of z = 1), the pins. */
export class Pass {
    constructor(R, fields, Sc, pins) {
        this.R = R;
        const { S, M } = statePairs(R, fields, 0.0);
        this.S = S;
        this.M = M;
        if (Sc) {
            this.P = R.pack({ Sc }, [null, null, 'Sc', null]);
        } else {
            const one = Gd.fill(R, [fields.h.h, fields.h.w], 1.0);
            this.P = R.pack({ one }, [null, null, 'one', null]);
            one.destroy();
        }
        this.Q = pinsPack(R, pins);
        this._phi = null;
    }

    threshold(cell, rate, looseOnly, bound, iso = 1) {
        this._phi = thresholdPass(this.R, this.S, this.M, this.P, this.Q, cell, rate, looseOnly, bound, iso, this._phi);
    }

    creep(cell, dtSub, D, cap, bound) {
        this.R.run(kernelOf(this.R, 'creep'), { st: this.S.src, par: this.P, pin: this.Q }, { outS: this.S.dst },
            { uDx: Number(cell), uDtSub: Number(dtSub), uD: Number(D), uCap: Number(cap), uBound: Math.trunc(bound) });
        this.S.swap();
    }

    /** fields.h, wear, deposit, talus from the state (bed = h - loose when the level had a bed); releases the state. */
    write(fields, hadBed) {
        const R = this.R;
        const s = R.unpack(this.S.src, ['h', null, null, null]);
        const m = R.unpack(this.M.src, ['wear', 'deposit', 'talus', hadBed ? 'loose' : null]);
        fields.h = s.h;
        fields.wear = m.wear;
        fields.deposit = m.deposit;
        fields.talus = m.talus;
        if (hadBed) {
            fields.bed = ew(R, EW.SUB, s.h, m.loose);
            m.loose.destroy();
        }
        this.destroy();
    }

    destroy() {
        for (const f of [this.S, this.M, this.P, this.Q]) f.destroy();
        if (this._phi && this._phi.h > 1) this._phi.destroy();
        this._phi = null;
    }
}

/** The level's pins: the stage context's, else the coarsest level's (the outer ring at base level). */
async function pinsOf(fields, level, ctx) {
    if (ctx && ctx.pins) return { pins: ctx.pins, own: false };
    return { pins: FL.edgePins(runnerOf(fields, ctx), level.n, fields.h), own: true };
}

function release(p) {
    if (p.own) for (const f of Object.values(p.pins)) f.destroy();
}

/** A Gaussian blur of sigma_cells (numpy's FFT blur of the field padded by reflection 4 sigma each side): core/prims.js
 * gaussianBlur, mode 'reflect'. A new field. */
export function gaussianBlur(a, sigmaCells) {
    return prims(a.runner).gaussianBlur(a, Number(sigmaCells), { mode: 'reflect' });
}


// ==================================================================================================== the ops ===

/** Stage 'creep' (module doc). params: kappa_t_m2 (linear: kappa t in m^2), or D (m^2/yr) and years (nonlinear,
 * with threshold_deg 35 and cap 5). The border band stays pinned to the parent. */
export async function opCreep(fields, level, params, seed = 0, ctx = null) {
    const R = runnerOf(fields, ctx);
    const pp = await pinsOf(fields, level, ctx);
    const pins = pp.pins;
    if (params.kappa_t_m2 !== undefined && params.kappa_t_m2 !== null) {
        const kt = Number(params.kappa_t_m2);
        const sig = Math.sqrt(2.0 * kt) / level.cell;
        const hb = gaussianBlur(fields.h, sig);
        fields.h = ew(R, EW.PIN, hb, pins.pin_w, pins.pin_h);
        hb.destroy();
        if ('bed' in fields) fields.bed = ew(R, EW.MIN, fields.bed, fields.h);
        release(pp);
        return fields;
    }
    const D = Number(params.D);
    const years = Number(params.years);
    const cap = Number(params.cap ?? 5.0);
    const Sc = Gd.fill(R, [level.n, level.n], Math.fround(tanDeg(params.threshold_deg ?? 35.0)));
    const run = new Pass(R, fields, Sc, pins);
    Sc.destroy();
    const dtMax = (0.9 * level.cell ** 2) / (3.4 * D * cap);
    const nSub = Math.max(1, Math.trunc(Math.ceil(years / dtMax)));
    for (let i = 0; i < nSub; i++) run.creep(level.cell, years / nSub, D, cap, FL.PINNED);
    run.write(fields, 'bed' in fields);
    release(pp);
    return fields;
}

/** The talus stage's threshold field: tan(repose), and where there is no bed, never below the inherited surface's
 * own slope (times margin). Returns [Sc field, loose (true with a bed)]. */
export function talusSc(fields, level, reposeDeg, margin = 1.1) {
    const R = fields.h.runner;
    const t = tanDeg(reposeDeg);
    if ('bed' in fields) return [Gd.fill(R, [level.n, level.n], Math.fround(t)), true];
    const { gx, gy } = Gd.gradient(fields.h, level.cell);
    const sc = ew(R, EW.MAX_K_HYPOT, null, gx, gy, t, margin);
    gx.destroy();
    gy.destroy();
    return [sc, false];
}

/** Stage 'talus' (module doc). params: repose_deg (35), iterations (64), rate (0.12, the isotropic threshold). */
export async function opTalus(fields, level, params, seed = 0, ctx = null) {
    const t0 = now();
    const R = runnerOf(fields, ctx);
    const [Sc, loose] = talusSc(fields, level, Number(params.repose_deg ?? 35.0));
    const pp = await pinsOf(fields, level, ctx);
    const run = new Pass(R, fields, Sc, pp.pins);
    Sc.destroy();
    const it = Math.trunc(Number(params.iterations ?? 64)), rate = Number(params.rate ?? 0.12);
    for (let i = 0; i < it; i++) run.threshold(level.cell, rate, loose, FL.PINNED);
    run.write(fields, 'bed' in fields);
    release(pp);
    if (ctx) {
        ctx.log(`[terrain.hillslope] talus at ${FL.pyG(params.repose_deg ?? 35.0)} deg on ${level.n}^2 @ ` +
            `${FL.fmtG(level.cell, 3)} m (${loose ? 'loose only' : 'new detail only'}), ${(now() - t0).toFixed(2)} s`);
    }
    return fields;
}

/** Stage 'threshold' (module doc). params: threshold_deg (or the level's Sc field), iterations (64), rate. */
export async function opThreshold(fields, level, params, seed = 0, ctx = null) {
    const R = runnerOf(fields, ctx);
    let Sc, own = true;
    if ('Sc' in fields && (params.threshold_deg === undefined || params.threshold_deg === null)) {
        Sc = fields.Sc;
        own = false;
    } else {
        Sc = Gd.fill(R, [level.n, level.n], Math.fround(tanDeg(params.threshold_deg ?? 35.0)));
    }
    const pp = await pinsOf(fields, level, ctx);
    const run = new Pass(R, fields, Sc, pp.pins);
    if (own) Sc.destroy();
    const it = Math.trunc(Number(params.iterations ?? 64)), rate = Number(params.rate ?? 0.12);
    for (let i = 0; i < it; i++) run.threshold(level.cell, rate, false, FL.PINNED);
    run.write(fields, 'bed' in fields);
    release(pp);
    return fields;
}


// ==================================================================== soil hillslopes at steady state ===
// Linear creep with uplift at steady state, with the channels held: div(D grad h) = -U on the hillslopes. With D
// uniform the Laplacian is -U / D everywhere off the channels: parabolic, convex hills whose relief is
// (U / D) L^2 / 2 for channels 2 L apart (Culling 1960; the Palouse's and Gabilan Mesa's hills). The diffusivity can
// depend on which way a slope faces the wind: D (1 - a cos theta), theta between the pair's downslope direction and
// the wind's, so a lee slope (facing downwind) carries the same soil flux at a steeper gradient: the crest moves
// toward the lee channel and the lee face stands steeper and shorter. One damped Jacobi step of the 9-point
// isotropic stencil per dispatch (kernels/soil_jacobi.wgsl).

export const SOIL_DEFAULTS = Object.freeze({ relief_m: 20.0, valley_spacing_m: 300.0, context_spacing_factor: 1.0,
    relief_scaling: 1.0, channel_frac: 0.25, asymmetry: 0.0, wind_from_deg: 225.0, rill_depth_m: 0.0, rill_max_cell_m: 1.0,
    rill_width_cells: 1.2, rill_width_m: null, rill_growth_max: 2.5, rise_cap: 0.5, flow_exponent: 4.0, omega: 0.9,
    coarse_levels: 3, iter_scale: 1.0, blend: 1.0, seed_m: 0.0, seed_max_cell_m: 1.0, head_soft: 1.0,
    hold_deposit_m: null });

/** C1 smooth minimum, blend width k (metres): numbers. */
export function smoothMin(a, b, k) {
    if (k <= 0) return Math.min(a, b);
    const hh = Math.max(k - Math.abs(a - b), 0.0) / k;
    return Math.min(a, b) - hh * hh * k * 0.25;
}

/** r unchanged up to cap / 2, then easing (tanh, C1) to at most cap (hillslope.py soft_cap): a number. The fields'
 * form is kernels/fluvial/ew.wgsl mode CAP_BLEND. */
export function softCap(r, cap) {
    const half = 0.5 * Number(cap);
    return r <= half ? r : half + half * Math.tanh((r - half) / Math.max(half, 1e-12));
}

/** U / D (1/m) of parabolic hills relief_m high between channels spacing_m apart: relief = C (spacing / 2)^2 / 2. */
export function soilConvexity(reliefM, spacingM) {
    return (8.0 * Number(reliefM)) / Number(spacingM) ** 2;
}

/** mask (a u32 field of bits: bit 0 the mask) grown down the receiver paths rec (hydro.js flowReceivers: every path
 * ends at an outlet) until every cell downstream of a masked cell is masked (hillslope.py _downstream): the gather
 * relaxation kernels/fluvial/soil_down.wgsl to its fixed point. A new u32 field; the passes it took. */
export async function downstream(R, bits, rec, maxPasses = 1 << 16) {
    const P = R.pair(bits.h, bits.w, 1, null, 'u32');
    R.copy(bits, P.src);
    const counter = R.field(1, 1, 1, null, 'u32');
    counter.name = 'soil_downstream_changed';
    let done = 0, chunk = 8;
    for (;;) {
        R.clear(counter);
        for (let i = 0; i < chunk; i++) {
            R.run(kernelOf(R, 'fluvial/soil_down'), { bits: P.src, rec }, { outB: P.dst, changed: counter },
                { uCount: i === chunk - 1 ? 1 : 0 });
            P.swap();
        }
        done += chunk;
        const [c] = await R.readRange(counter, 0, 1);
        if (c === 0) break;
        if (done >= maxPasses) break;                       // numpy's own cap (max_iter) is 4096 passes
        chunk = Math.min(chunk * 2, 64);
    }
    counter.destroy();
    P.dst.destroy();
    return { bits: P.src, passes: done };
}

/** The steady soil hillslope on the GPU (hillslope.py soil_solve): damped Jacobi (soil_jacobi) coarse to fine. The
 * held cells (holdW 1) and the pins stay; every other cell relaxes toward div(D grad h) = -C. Coarser grids (2 x 2
 * block means; a coarse cell is held when any of its cells is, at their mean height) solve first, each upsampled into
 * the next as its start: Jacobi needs about (distance to a held cell)^2 iterations, which the coarse grids cut by 4
 * per level. halfCells: the largest distance to a channel expected, in cells of the finest grid. Fields in, of one
 * level's shape: h0, holdW, holdH, pinW, pinH. Returns { h (a new r32f field), change (the last iteration's largest
 * change, metres), iterations }. */
export async function soilSolve(R, h0, holdW, holdH, pinW, pinH, cell, Cv, opts = {}) {
    const { asym = 0.0, wind = [1.0, 0.0], halfCells = 20.0, omega = 0.9, coarseLevels = 3, iterScale = 1.0,
        bound = FL.PINNED } = opts;
    const P0 = R.pack({ holdW, holdH, pinW, pinH }, ['holdW', 'holdH', 'pinW', 'pinH']);
    const h00 = R.like(h0);
    R.copy(h0, h00);
    const pyr = [{ h: h00, con: P0, c: Number(cell) }];
    while (pyr.length <= coarseLevels && Math.min(pyr[pyr.length - 1].h.h, pyr[pyr.length - 1].h.w) >= 128 &&
        Math.min(pyr[pyr.length - 1].h.h, pyr[pyr.length - 1].h.w) % 2 === 0) {
        const top = pyr[pyr.length - 1];
        const m0 = Math.floor(top.h.h / 2), m1 = Math.floor(top.h.w / 2);
        const h2 = R.field(m0, m1, 1), c2 = R.field(m0, m1, 4);
        R.run(kernelOf(R, 'fluvial/soil_block2'), { h: top.h, con: top.con }, { outH: h2, outC: c2 });
        pyr.push({ h: h2, con: c2, c: 2.0 * top.c });
    }
    let total = 0, cur = null, change = 0.0;
    const diff = R.field(1, 1, 1);
    for (let li = pyr.length - 1; li >= 0; li--) {
        const { h, con, c } = pyr[li];
        let start = h;
        if (cur !== null) {
            start = Gd.upsample2(cur, 'nearest');           // np.repeat(np.repeat(cur, 2, 0), 2, 1): the whole grid
            cur.destroy();
        }
        const L = Math.max((Number(halfCells) * Number(cell)) / c, 1.0);
        const its = Math.trunc(Math.min(Math.max((li === pyr.length - 1 ? 2.0 : 0.6) * L * L * Number(iterScale), 40), 4000));
        const S = R.pair(h.h, h.w, 1);
        R.copy(start, S.src);
        if (start !== h) start.destroy();
        const un = { uDx: c, uC: Number(Cv), uAsym: Number(asym), uWind: [Number(wind[0]), Number(wind[1])],
            uOmega: Number(omega), uBound: Math.trunc(bound) };
        for (let k = 0; k < its - 1; k++) {
            R.run(kernelOf(R, 'soil_jacobi'), { st: S.src, con }, { outS: S.dst }, un);
            S.swap();
        }
        const prev = R.like(S.src);
        R.copy(S.src, prev);
        R.run(kernelOf(R, 'soil_jacobi'), { st: S.src, con }, { outS: S.dst }, un);
        S.swap();
        cur = S.src;
        S.dst.destroy();
        const d = ew(R, EW.SUB, cur, prev);
        const st = await prims(R).stats(d);
        change = Math.max(Math.abs(st.min), Math.abs(st.max));
        d.destroy();
        prev.destroy();
        total += its;
    }
    diff.destroy();
    for (const lv of pyr) {
        lv.h.destroy();
        lv.con.destroy();
    }
    return { h: cur, change, iterations: total };
}

/** The smallest float32 at or above x (a float32 A >= x exactly when A >= this). */
function f32AtOrAbove(x) {
    const f = Math.fround(x);
    if (f >= x) return f;
    const b = new Float32Array([f]), u = new Uint32Array(b.buffer);
    if (f > 0) u[0] += 1;
    else if (f < 0) u[0] -= 1;
    else u[0] = 1;
    return b[0];
}

/** Stage 'soil_hills' (module doc and hillslope.py op_soil_hills): the level's hillslopes replaced by their steady
 * soil-mantled form between the channels its erosion cut.
 *
 * params (metres, degrees): valley_spacing_m 300, context_spacing_factor 1 (the channels' spacing on the main level
 * and its growth per context level); relief_m 20 (a hill's height over its channels at that spacing: U / D = 8 relief
 * / spacing^2; on a level of another spacing, relief x (spacing ratio)^relief_scaling); channel_frac 0.25 (channels:
 * drainage area >= channel_frac spacing^2); flow_exponent 4 (the area for that test routed with the slope weights to
 * this power, on the heights scaled so the steeper slopes are about 1); asymmetry 0, wind_from_deg 225 (lee slopes
 * steeper); rill_depth_m 0, rill_max_cell_m 1, rill_width_cells 1.2, rill_width_m, rill_growth_max 2.5 (rills cut
 * along the channels on fine levels); head_soft 1 (> 1: a channel's hold eases in along its head); hold_deposit_m
 * (cells with at least this much deposit held); rise_cap 0.5 (the steady form rises at most rise_cap x the hill
 * relief above the eroded surface); blend 1; seed_m 0, seed_max_cell_m 1 (an undulation added before the channels
 * are found on fine levels); omega 0.9, coarse_levels 3, iter_scale 1 (the solve). The border band stays pinned to
 * the parent; sea cells are held. */
export async function opSoilHills(fields, level, params, seed = 0, ctx = null) {
    ctx = await FL.asContext(ctx, fields, level);
    const t0 = now();
    if (params.enabled === false) return fields;
    const p = { ...SOIL_DEFAULTS };
    for (const [k, v] of Object.entries(params ?? {})) if (k in SOIL_DEFAULTS && v !== null && v !== undefined) p[k] = v;
    const R = runnerOf(fields, ctx), P = prims(R), D = Gd.dummies(R);
    const cell = Number(level.cell);
    const depth = ctx.depth;
    const sp0 = Number(p.valley_spacing_m);
    let sp = FL.levelSpacing({ valley_spacing_m: sp0, context_spacing_factor: p.context_spacing_factor }, depth);
    sp = Math.max(sp, FL.MIN_SPACING_CELLS * cell);
    const relief = Number(p.relief_m) * (sp / sp0) ** Number(p.relief_scaling);
    const Cv = soilConvexity(relief, sp);
    const sea = ctx.sea_level ?? null;
    const own = [];                                         // fields this op made and releases
    let pinsOwn = false, pins = ctx.pins;
    if (!pins) {
        pins = FL.edgePins(R, level.n, fields.h, sea);
        pinsOwn = true;
    }
    let h = fields.h;
    const rill = Number(p.rill_depth_m);
    const cuts = rill > 0 && cell <= Number(p.rill_max_cell_m);
    if (cuts && 'rill_cut' in fields) {
        // the parent's rills come out before this level cuts its own (rill_cut, inherited)
        h = ew(R, EW.ADD_FREE, h, fields.rill_cut, pins.pin_w, 1.0);
        own.push(h);
    }
    const seedM = Number(p.seed_m);
    const seeded = seedM > 0 && cell <= Number(p.seed_max_cell_m);
    let hRoute = h, hollow = null;
    if (seeded) {
        const nz = N.fieldGpu(R, { kind: 'fbm', wavelength_m: sp, octaves: 3, amp: 3.0 }, level, Math.trunc(seed) + 907);
        const hSeed = ew(R, EW.ADD_FREE, h, nz, pins.pin_w, seedM);
        nz.destroy();
        const { filled } = await HY.fillDepressions(hSeed, { seaLevel: sea });
        h = filled;
        own.push(h);
        hollow = ew(R, EW.LAKE, h, hSeed, null, 1e-4);
        hSeed.destroy();
        hRoute = await HY.routingSurface(h, { seaLevel: sea });
        own.push(hRoute);
    }
    const pe = Number(p.flow_exponent);
    let A, ownA = false;
    if (pe > 1.0 || !('A' in fields) || seeded) {
        const { gx, gy } = Gd.gradient(hRoute, cell);
        const hyp = ew(R, EW.HYPOT, gx, gy);
        gx.destroy();
        gy.destroy();
        const p90 = await P.percentile(hyp, 90, { dtype: 'float64' });
        hyp.destroy();
        const lam = 1.0 / Math.max(p90, 1e-4);
        const mn = (await P.stats(hRoute)).min;
        const surf = ew(R, EW.SHIFT_SCALE, hRoute, null, null, mn, lam);
        const r = await HY.routeToConvergence(R, surf, cell, { A_in: pins.A_in, p: Math.max(pe, 1.0) });
        surf.destroy();
        A = r.A;
        ownA = true;
    } else {
        A = fields.A;
    }
    const aCh = Number(p.channel_frac) * sp * sp;
    const { filled } = await HY.fillDepressions(h, { seaLevel: sea });
    const epsHi = Math.fround(1e-4), epsLo = Math.fround(1e-4 - epsHi);
    const bits0 = R.field(level.n, level.n, 1, null, 'u32');
    R.run('fluvial/soil_chan', { A, h, filled, hollow: hollow ?? D.f1 }, { outB: bits0 },
        { uACh: f32AtOrAbove(aCh), uEpsHi: epsHi, uEpsLo: epsLo, uSea: sea !== null ? 1 : 0, uSea32: sea !== null ? Math.fround(sea) : 0.0,
            uHollow: hollow ? 1 : 0 });
    if (hollow) hollow.destroy();
    const rec = await HY.flowReceivers(filled, { seaLevel: sea });
    const { bits } = await downstream(R, bits0, rec);
    rec.destroy();
    bits0.destroy();
    const soft = Number(p.head_soft);
    // a river course (op_incise's, river_path's) is a base level: the solve never raises it (hold 1 where > 0.5)
    const kk = ['incised', 'river'].filter((k) => k in fields);
    const keep = kk.length === 2 ? ew(R, EW.MAX, fields.incised, fields.river) : (kk.length === 1 ? fields[kk[0]] : null);
    const hasDep = p.hold_deposit_m !== null && p.hold_deposit_m !== undefined && 'deposit' in fields;
    const hHeld = R.field(level.n, level.n, 1), hold = R.field(level.n, level.n, 1);
    R.run('fluvial/soil_hold', { bits, A, h, filled, dep: hasDep ? fields.deposit : D.f1, keep: keep ?? D.f1 },
        { outH: hHeld, outW: hold },
        { uSoft: soft > 1.0 ? 1 : 0, uLogLo: soft > 1.0 ? Math.log(aCh / soft) : 0.0, uLogSpan: soft > 1.0 ? 2.0 * Math.log(soft) : 1.0,
            uSea: sea !== null ? 1 : 0, uSea32: sea !== null ? Math.fround(sea) : 0.0, uDep: hasDep ? 1 : 0,
            uDepMin: hasDep ? Number(p.hold_deposit_m) : 0.0, uKeep: keep ? 1 : 0 });
    if (keep && kk.length === 2) keep.destroy();
    filled.destroy();
    const chanFlags = bitsToFloat(R, bits, 1);
    const chanCells = (await P.stats(chanFlags)).nonzero;
    chanFlags.destroy();
    const az = (Number(p.wind_from_deg) + 180.0) * DEG;
    const wind = [Math.sin(az), Math.cos(az)];
    const solved = await soilSolve(R, hHeld, hold, hHeld, pins.pin_w, pins.pin_h, cell, Cv, { asym: Number(p.asymmetry), wind,
        halfCells: (0.5 * sp) / cell, omega: Number(p.omega), coarseLevels: Math.trunc(Number(p.coarse_levels)),
        iterScale: Number(p.iter_scale) });
    hold.destroy();
    const cap = Number(p.rise_cap) * relief;
    let cut = null;
    if (cuts) {
        const gmax = Math.max(Number(p.rill_growth_max), 1.0);
        const d = R.field(level.n, level.n, 1);
        R.run('fluvial/soil_rill', { bits, A, src: D.f1, pinw: D.f1 }, { outF: d },
            { uMode: 0, uRill: rill, uACh: aCh, uGmax: gmax, uPeak: 1.0 });
        const sig = p.rill_width_m === null || p.rill_width_m === undefined ? Number(p.rill_width_cells) : Number(p.rill_width_m) / cell;
        const peak = sig > 0.4 ? 1.0 / (Math.sqrt(2.0 * Math.PI) * sig) : 1.0;
        // the blurred line, not the line itself (hillslope.py: max(cut, d) put the full depth back on the centre cells)
        const blurred = sig > 0.4 ? gaussianBlur(d, sig) : d;
        cut = R.field(level.n, level.n, 1);
        R.run('fluvial/soil_rill', { bits, A, src: blurred, pinw: pins.pin_w }, { outF: cut },
            { uMode: 1, uRill: rill, uACh: aCh, uGmax: gmax, uPeak: peak });
        if (blurred !== d) blurred.destroy();
        d.destroy();
    }
    // hs = h + soft_cap(hs - h, cap); hn = h + blend (hs - h) - cut; and hn - bed formed as numpy's float64 is
    const hasBed = 'bed' in fields;
    const hn = R.field(level.n, level.n, 1), diff = R.field(level.n, level.n, 1);
    R.run('fluvial/soil_final', { h: hHeld, hs: solved.h, cut: cut ?? D.f1, bed: hasBed ? fields.bed : D.f1 }, { outH: hn, outD: diff },
        { uCap: cap, uBlend: Number(p.blend), uCut: cut ? 1 : 0, uBed: hasBed ? 1 : 0 });
    solved.h.destroy();
    if (cut) fields.rill_cut = cut;
    hHeld.destroy();
    bits.destroy();
    if (ownA) A.destroy();
    if (hasBed) {
        // bed = min(bed, hn); deposit, talus = min(x, hn - bed)
        const bed = ew(R, EW.BED_MIN, fields.bed, hn, diff);
        for (const k of ['deposit', 'talus']) if (k in fields) fields[k] = ew(R, EW.CLAMP_POS, fields[k], diff);
        fields.bed = bed;
    }
    diff.destroy();
    fields.h = hn;
    for (const f of own) if (!f.destroyed) f.destroy();
    if (pinsOwn) for (const f of Object.values(pins)) f.destroy();
    ctx.evolved = true;
    const secs = round3(now() - t0);
    (ctx.shared.soil_log ??= []).push({ level: String(level), spacing_m: Math.round(sp * 10) / 10,
        relief_m: Math.round(relief * 100) / 100, convexity: Cv, channel_cells: chanCells, iterations: solved.iterations,
        last_change_m: solved.change, seconds: secs });
    ctx.log(`[terrain.hillslope] soil hills ${level.n}^2 @ ${FL.fmtG(cell, 3)} m: channels ${(100.0 * chanCells / (level.n * level.n)).toFixed(1)} % ` +
        `(A >= ${aCh.toFixed(0)} m2), spacing ${sp.toFixed(0)} m, relief ${relief.toFixed(2)} m (U/D ${FL.fmtG(Cv, 3)} /m), asymmetry ` +
        `${FL.pyG(Number(p.asymmetry))}, ${solved.iterations} iterations (last change ${FL.fmtG(solved.change, 2)} m), ${secs} s`);
    return fields;
}

// 1 where a u32 bit field has bit `bit` set, else 0 (a float field, for a count; kernels/fluvial/bit.wgsl): a new field
function bitsToFloat(R, bits, bit) {
    const out = R.field(bits.h, bits.w, 1);
    R.run('fluvial/bit', { b: bits }, { outF: out }, { uBit: bit });
    return out;
}


for (const op of [opCreep, opTalus, opThreshold]) op.evolves = true;   // run.js: on every coarse-to-fine pass
opSoilHills.post = true;                                                // run.js: once per level, after its last pass
for (const op of [opCreep, opTalus, opThreshold, opSoilHills]) op.takesCtx = true;

export const OPS = { creep: opCreep, talus: opTalus, threshold: opThreshold, soil_hills: opSoilHills };

export {
    thresholdPass as threshold_pass, gaussianBlur as gaussian_blur, opCreep as op_creep, opTalus as op_talus,
    opThreshold as op_threshold, opSoilHills as op_soil_hills, soilSolve as soil_solve, softCap as soft_cap,
    soilConvexity as soil_convexity, smoothMin as smooth_min, talusSc as _talus_sc, downstream as _downstream, Pass as _Pass,
};
