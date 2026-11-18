// Port of blender/eidoblend/terrain/solvers/detail.py at f90c6fc.
//
// Detail (design section 4.12): rock breakup, the flow-steered gully octave, and planation. Every input is a
// function of world metres, so a place gets the same rock at every level and on every run.
//
//     op 'breakup'    Stage('breakup', {...}, levels='hero')    rock strength -> K, Sc, relief, failure, talus
//     op 'gully'      Stage('gully', {...}, levels='hero')      Phacelle gullies down the flow on soil slopes
//     op 'planation'  Stage('planation', {...}, levels='all')   a pediment plain with residual knobs (desert recipes)
//
// Rock breakup. One GPU dispatch (kernels/breakup.wgsl, Ekigar's lattice noise in world metres) gives the rock
// strength R: three isotropic scales (50, 15 and 5 m by default), two joint sets (weak lines 4-5 m wide, the
// weathered expression of a fracture, along their strikes and broken into segments) and, when asked, bedding planes
// (weak beds every few metres of height, with dip; off by default). From R come
//     kfac = 2^(-k_octaves R)            the erodibility factor: K *= kfac and K_factor (the fluvial stage reads it),
//                                        and the hydraulic pass erodes rock at `rock` x kfac
//     Sc   = tan(theta)                  the rock threshold, theta = the current slope + margin + spread R
//                                        ('relative', for real data), or rock_deg + spread R ('absolute'), or the Sc
//                                        field's angle + spread R ('field', synthetic recipes); Sc_factor is its
//                                        ratio to what the level had
// Then, on exposed rock (rock_slope_deg), the process: differential weathering in closed form (weak rock has worn
// back, strong rock stands proud: the relief D, about 8 % of each scale RMS, along the surface normal), and the
// threshold relaxation (kernels/pipes_thermal.wgsl): rock steeper than its own threshold fails, no deeper than
// max_fail_m, and the debris slides at its repose angle and gathers as talus at the foot of walls and in couloirs.
// Scales by level: the strength sees every feature the level resolves (r(size / cell), r = smoothstep(1.5, 3)); the
// relief adds only the band the parent level cannot resolve (r(size / cell) - r(size / (2 cell))), so a feature's
// relief is applied once across the levels that inherit it, and nothing the DEM pixel already holds is added to a
// real place.
//
// Gully octave. Ekigar's Phacelle filter (src/nodes/phacelle.js; kernels/detail/phacelle.wgsl): stripe noise whose
// stripes run along a direction, each octave steered by the one before so the finer gullies run into the coarser.
// Here the direction is the flow (the routed MFD direction where a flow vector is given, else down the surface
// smoothed at the octave's scale), the stripes are world-space, the amplitude is metres, and it is masked to soil
// slopes between 10 and 35 degrees.
//
// Planation. Ekigar's planationSurface rebuilt in metres: the ground is cut down to a gently tilted datum where the
// rock is weak and keeps its relief where it is resistant (world-space noise), with an abrupt piedmont foot.
//
// All three write h (blended to the pins at the end, like the hydraulic op: the border band fades from the detail
// to the parent's surface), and breakup also bed, talus, wear, deposit, kfac, K_factor, Sc and Sc_factor (and K when
// the level has one). Run by the level runner (run.js), the ops take its StageContext (pins, log) as ctx.
//
// Order. In real_place and fluvial_range the breakup runs after the fluvial stage on each hero level, so its K_factor
// and Sc_factor reach only the stages after it on that level (the hydraulic pass).
//
// Exports beside the ops (detail.py's names in camelCase; what later packages read: the glacial package's
// flowDirection, the surface bake's paramsOf, breakupTerms, breakupUniforms, strength, relax and the Phacelle
// kernel kernels/detail/phacelle.wgsl): BREAKUP, GULLY, PLANATION, paramsOf (_params), resolvable, band,
// breakupTerms, breakupUniforms, strength, relax, flowDirection, gullyTable, gullyRelief, opBreakup, opGully,
// opPlanation, OPS.
//
// The dispatch log (PORT_PLAN.md 5.7): Blender's kernels are breakup (once) and pipes_thermal (`iterations` times)
// for op_breakup, world_noise_field (twice) for op_planation, none for op_gully (numpy in Blender); every other
// dispatch is the port's own (kernels/detail/, core/prims.js, core/grid.js), marked as such. No loop here stops on a
// convergence test.
//
// Where this differs from detail.py, and why (PORT_PLAN.md 2.4, 3.2: every per-cell step runs on the GPU; each is
// checked against the numpy function it replaces, tests/detail/):
//   - The numpy twin of breakup.glsl is not ported (it is the oracle, run in Blender's Python); there is no CPU path
//     and no `backend` argument. breakup_terms and breakup_uniforms stay JavaScript in doubles, as numpy computes
//     them (a few rows per level); the term table is float32 as numpy stores it.
//   - op_breakup's slope, rock mask, weathering and thresholds are one kernel (kernels/detail/breakup_surface.wgsl);
//     to_c, the start state, relax's packs and the way back to metres are kernels/detail/to_cells, pipe_start and
//     pipe_out, finish is solvers/hydraulic.js finish (changes added to h_in once), in float32 where numpy is float64.
//   - The gradient of the smoothed surface (op_breakup's, flow_direction's, the gully mask's slope) is the box mean of
//     height differences (kernels/detail/box_gradient.wgsl), the same quantity as np.gradient(_box(h, r)) in the
//     better-conditioned form plan 2.3 asks for (smoothing first rounds every smoothed float32 height, and the
//     difference divides that by the cell: 1e-5 of the slope, measured).
//   - gully_relief, which Blender runs in numpy, is one kernel (kernels/detail/gully.wgsl: every octave per cell,
//     the Phacelle noise of kernels/detail/phacelle.wgsl on lattice coordinates kept as an integer cell and a float32
//     fraction, built in doubles here: gullyTable), and flow_direction another (kernels/detail/flow_dir.wgsl).
//   - op_planation's arithmetic is kernels/detail/planation.wgsl; its two noise fields are core/world_noise.js
//     fieldGpu, as Blender's field_gpu.
//   - relax takes and returns GPU fields (b0 as T.rgba(b0), bed in cell units) and leaves its result on the GPU.
//   - The ops are async, take ctx as their fifth argument (run.js passes it), and return the fields.

import * as Gd from '../core/grid.js';
import { KeyError, ValueError, closeMatches, pyFormat, pyReprValue, pyRound, pyStr } from '../core/levels.js';
import { prims } from '../core/prims.js';
import * as N from '../core/world_noise.js';
import * as HY from './hydraulic.js';

const TAU = 6.28318530717959;
const DEG = Math.PI / 180.0;                            // math.radians' factor

export const BREAKUP = {
    scales_m: [[50.0, 15.0, 5.0], 'm', 'wavelengths of the strength noise'],
    scale_amps: [[1.0, 0.75, 0.55], '', 'their relative amplitudes'],
    // joints and beds as their weathered expression: a couloir along a fracture is metres wide, a weak interval
    // between massive beds several metres thick (narrower ones only resolve below 0.5 m and belong to the material)
    joints: [[{ strike_deg: 15.0, spacing_m: 25.0, width_m: 5.0, stretch: 2.5, strength: 0.9, depth_m: 1.0 },
        { strike_deg: 105.0, spacing_m: 35.0, width_m: 4.0, stretch: 2.0, strength: 0.7, depth_m: 0.8 }], 'list',
    "joint sets: strike (degrees from +x, counter-clockwise), mean spacing, the weak line's width, " +
    'how much longer than wide its lattice is, strength lost on the line, relief cut on the line (m)'],
    bedding: [null, 'dict',
        "weak beds, e.g. {'spacing_m': 20, 'width_m': 6, 'strength': 1, 'depth_m': 2, 'dip_deg': 0, " +
        "'azimuth_deg': 0, 'z0_m': 0}: every spacing_m metres of stratigraphic height, width_m thick, they fail " +
        'back into ledges while the strong rock between them stands. Off by default: as level planes they ' +
        "terrace every moderately steep rock slope along its contours (the design's strata failure mode); " +
        "layered rock is the strata column's job (package 10)"],
    k_octaves: [1.0, '', 'kfac = 2^(-k_octaves R): R of +-0.33 gives x0.8-1.26'],
    threshold: ['auto', 'choice', "'relative' (the current slope + spread R), 'absolute' (rock_deg + spread R), " +
        "'field' (the Sc field x tan-ratio of spread R); 'auto': field when the level has " +
        'an Sc field, else relative'],
    rock_deg: [70.0, 'deg', "the mean rock threshold ('absolute')"],
    spread_deg: [14.0, 'deg', 'the threshold change per unit of strength'],
    margin_deg: [4.0, 'deg', "'relative': the threshold stands this much above the current slope, so only rock " +
        'weaker than -margin / spread fails (a wall exactly at its threshold would fail all ' +
        'the way up once one cell gives)'],
    max_fail_m: [2.0, 'm', 'the deepest rock fails below the breakup surface: scars stay local (deeper ones leave ' +
        'planar failure faces at the threshold angle)'],
    min_deg: [40.0, 'deg', 'the lowest rock threshold'],
    max_deg: [88.0, 'deg', 'the highest rock threshold'],
    relief: [0.25, '', 'the weathered relief of each isotropic scale, as a fraction of its wavelength (0.25: about ' +
        "8 % of it RMS, rock's roughness)"],
    normal_cap: [4.0, '', 'the largest vertical stretch of a normal displacement (walls steeper than ~76 deg)'],
    rock_slope_deg: [[38.0, 52.0], 'deg', 'exposed rock: a smoothstep of the slope'],
    iterations: [400, '', 'threshold-relaxation passes'],
    anchor: [true, 'bool', 'keep only the change narrower than anchor_m (hydraulic.anchor)'],
    anchor_m: [null, 'm', "the anchor's scale (None: 1.5 x the main level's cell)"],
    rate: [0.06, '', 'relaxation rate (<= 1/8)'],
    repose_deg: [35.0, 'deg', 'the repose angle of the debris'],
    soil_deg: [38.0, 'deg', 'the threshold written into Sc on soil when the level has none'],
};

export const GULLY = {
    wavelength_m: [null, 'm', "the first octave's gully spacing (None: 12 cells)"],
    octaves: [3, '', 'octaves, each half the wavelength'],
    amp_m: [null, 'm', "the first octave's depth (None: 0.08 x the wavelength)"],
    gain: [0.5, '', 'amplitude ratio between octaves'],
    steer: [0.6, '', 'how much each octave turns the next one into its own gullies'],
    slope_deg: [[10.0, 18.0, 30.0, 38.0], 'deg', 'the mask: fades in between the first two, out between the last two'],
    flow_smooth_m: [null, 'm', "the surface is smoothed this much before its downhill direction is taken (None: " +
        'the first wavelength)'],
    normalization: [0.5, '', "Phacelle's amplitude normalisation"],
    anchor: [true, 'bool', 'keep only the change narrower than anchor_m (hydraulic.anchor)'],
    anchor_m: [null, 'm', "the anchor's scale (None: 1.5 x the main level's cell)"],
};

export const PLANATION = {
    datum_m: [null, 'm', "the plain's height at the level centre (None: the 15th percentile of h)"],
    tilt_deg: [0.8, 'deg', "the pediment's slope"],
    azimuth_deg: [0.0, 'deg', 'the direction the plain falls toward (from +x, counter-clockwise)'],
    resist_wavelength_m: [900.0, 'm', 'the size of the resistant patches'],
    coverage: [0.6, '', 'the fraction of the ground planed flat'],
    selectivity: [2.5, '', 'higher leaves fewer, sharper residuals'],
    residual: [0.9, '', 'the original relief kept on resistant ground'],
    piedmont_m: [40.0, 'm', "the width of a residual's foot (the break of slope)"],
    plain_relief_m: [1.5, 'm', 'relief left on the plain (noise at 60 m)'],
};

/** A table's defaults overridden by `params`; an unknown name raises naming the nearest (detail.py _params). */
export function paramsOf(table, params, op) {
    const out = Object.fromEntries(Object.entries(table).map(([k, v]) => [k, v[0]]));
    for (const [k, v] of Object.entries(params ?? {})) {
        if (HY.RUNNER_KEYS.includes(k)) continue;
        if (!(k in table)) {
            const near = closeMatches(k, Object.keys(table), 3);
            throw new KeyError(`${op}: no parameter ${pyReprValue(k)}` + (near.length ? `; did you mean ${pyStr(near)}?` :
                `; valid: ${pyStr(Object.keys(table).sort())}`));
        }
        out[k] = v;
    }
    return out;
}

// detail.py _smoothstep on one number (doubles)
function smoothstep1(e0, e1, x) {
    const t = Math.min(Math.max((Number(x) - e0) / Math.max(e1 - e0, 1e-12), 0.0), 1.0);
    return t * t * (3.0 - 2.0 * t);
}

/** How much of a feature `sizeM` across a grid of `cell` resolves: 0 under 1.5 cells, 1 over 3. */
export function resolvable(sizeM, cell) {
    return smoothstep1(1.5, 3.0, Number(sizeM) / Number(cell));
}

/** The share of a feature's relief a level adds: what it resolves minus what its parent (2 x cell) resolved. */
export function band(sizeM, cell) {
    return resolvable(sizeM, cell) - resolvable(sizeM, 2.0 * cell);
}


// ------------------------------------------------------------------------------------------ the term table ---

export const JOINT_ZERO_SPACING = 0.6;     // gradient noise crosses zero about every 0.6 lattice cells along a line
export const JOINT_SLOPE = 1.6;            // |dn/d(lattice)| at a zero crossing, about (measured: tests/terrain/detail)

const get = (o, k, d) => (o && o[k] !== undefined && o[k] !== null ? Number(o[k]) : d);

/** The breakup kernel's term table for a level: { terms (a Float32Array of 3 N texels x 4, N >= 1), n (the term
 * count), bed (the bedding uniforms) } (detail.py breakup_terms, in doubles; the table is float32 as numpy's). */
export function breakupTerms(p, level, seed) {
    const cell = Number(level.cell);
    const x0 = Number(level.x0), y0 = Number(level.y0);
    const rows = [];
    const term = (mode, aS, width, aD, M, octave) => {
        const [ox, oy] = N.latticeOffset(Math.trunc(seed) + 7919 * Math.floor(octave / 64), octave % 64);
        const o = [M[0][0] * x0 + M[0][1] * y0, M[1][0] * x0 + M[1][1] * y0];      // M @ (x0, y0)
        const bx = Math.floor(o[0]), by = Math.floor(o[1]);
        const fx = o[0] - bx, fy = o[1] - by;
        rows.push([[mode, aS, width, aD], [bx + ox, by + oy, fx, fy], [M[0][0], M[0][1], M[1][0], M[1][1]]]);
    };
    const amps = p.scale_amps.map(Number);
    let ss = 0.0;
    for (const a of amps) ss += a ** 2;
    const norm = ss > 0 ? (1.0 / 3.0) / (N.GRADIENT_STD * Math.sqrt(ss)) : 0.0;
    p.scales_m.forEach((lam0, i) => {
        if (i >= amps.length) return;                    // zip() stops at the shorter
        const lam = Number(lam0), a = amps[i];
        term(0, a * norm * resolvable(lam, cell), 0.0, p.relief * lam * a * norm * band(lam, cell),
            [[1.0 / lam, 0.0 / lam], [0.0 / lam, 1.0 / lam]], i);
    });
    (p.joints ?? []).forEach((js, j) => {
        const th = get(js, 'strike_deg', 0.0) * DEG;
        const uu = [Math.cos(th), Math.sin(th)];
        const vv = [-Math.sin(th), Math.cos(th)];
        const sp = get(js, 'spacing_m', 15.0);
        const lamX = sp * JOINT_ZERO_SPACING;
        const lamU = lamX * get(js, 'stretch', 5.0);
        const w = get(js, 'width_m', 1.5);
        const wEff = Math.max(w, 1.5 * cell);
        const wn = JOINT_SLOPE * 0.5 * wEff / lamX;                   // half the line's width, in noise units
        term(1, 0.0, wn, 0.0, [[uu[0] / lamU, uu[1] / lamU], [vv[0] / lamX, vv[1] / lamX]], 16 + 2 * j);
        const lamS = lamU * 0.7;
        term(2, get(js, 'strength', 0.8) * (w / wEff), 0.12, get(js, 'depth_m', 1.0) * band(w, cell),
            [[uu[0] / lamS, uu[1] / lamS], [vv[0] / lamS, vv[1] / lamS]], 17 + 2 * j);
    });
    const texels = Math.max(3 * rows.length, 3);
    const terms = new Float32Array(texels * 4);
    rows.forEach((r, t) => {
        for (let q = 0; q < 3; q++) terms.set(r[q], 4 * (3 * t + q));
    });
    const bed = p.bedding;
    let bu = { uBedSpacing: 1.0, uBedWidth: 1.0, uBedAmpS: 0.0, uBedAmpD: 0.0, uBedZ0: 0.0, uDipX: 0.0, uDipY: 0.0 };
    if (bed && Object.keys(bed).length) {
        const wz = get(bed, 'width_m', 2.0);
        const on = resolvable(wz / Math.tan(70.0 * DEG), cell);     // on a 70-degree wall a bed is wz / 2.75 wide
        const dip = Math.tan(get(bed, 'dip_deg', 0.0) * DEG);
        const az = get(bed, 'azimuth_deg', 0.0) * DEG;
        bu = { uBedSpacing: get(bed, 'spacing_m', 15.0), uBedWidth: wz, uBedAmpS: get(bed, 'strength', 0.5) * on,
            uBedAmpD: get(bed, 'depth_m', 0.6) * (on - resolvable(wz / Math.tan(70.0 * DEG), 2 * cell)),
            uBedZ0: get(bed, 'z0_m', 0.0), uDipX: dip * Math.cos(az), uDipY: dip * Math.sin(az) };
    }
    return { terms, n: rows.length, bed: bu, texels };
}

/** The breakup kernel's uniforms for a level (detail.py breakup_uniforms). */
export function breakupUniforms(p, level, nTerms, bedU) {
    return { uTerms: Math.trunc(nTerms), uCell: Number(level.cell), uX0: Number(level.x0), uY0: Number(level.y0),
        uKOct: Number(p.k_octaves), uRockDeg: Number(p.rock_deg), uSpreadDeg: Number(p.spread_deg),
        uMinDeg: Number(p.min_deg), uMaxDeg: Number(p.max_deg), ...bedU };
}

/** The breakup kernel on a level: an rgba32f field (R, kfac, Sc of the 'absolute' rule, D) the caller owns
 * (detail.py strength). h: the level's height (metres, a field; the bedding reads it). */
export function strength(p, level, h, seed) {
    const R = h.runner;
    const { terms, n, bed, texels } = breakupTerms(p, level, seed);
    const u = breakupUniforms(p, level, n, bed);
    const table = R.field(1, texels, 4, terms);
    const st = R.pack({ h }, ['h', null, null, null]);         // T.rgba(h): the kernel's st
    const out = R.field(h.h, h.w, 4);
    R.run('breakup', { terms: table, st }, { outB: out }, u);
    table.destroy();
    st.destroy();
    return out;
}


// --------------------------------------------------------------------------------------- relaxation ---

/** `iterations` thermal passes (kernels/pipes_thermal.wgsl) on ground b0 with cohesive top `bed` (cell units):
 * { state, accum } GPU fields (state: (delta, 0, 0, bed - b0), the ground b0 + delta; accum x: the net change by
 * sliding), the caller's to release (detail.py relax). b0: T.rgba(b0) (kernels/detail/to_cells' output, the pipe
 * model's base); bed: a field of cell units (x) or null (no debris); sc: a field (x) or a number; floor (cell units, a
 * number): the cohesive ground fails no deeper than this below b0. */
export function relax(b0, bed, sc, reposeTan, iterations, rate, mode = HY.BOUND_OPEN, floor = -1.0e6) {
    const R = b0.runner;
    const [h, w] = [b0.h, b0.w];
    const { state, par } = HY.startFields(R, b0, { bed, sc, rep: Math.fround(reposeTan), floor: Math.fround(floor) });
    const pin = R.field(h, w, 4);
    const u = { uRate: Number(rate), uBound: Math.trunc(mode) };
    const k = R.kernel('pipes_thermal');
    const S = [state, R.field(h, w, 4)];
    const TA = [R.field(h, w, 4), R.field(h, w, 4)];
    for (let i = 0; i < Math.trunc(iterations); i++) {
        R.run(k, { st: S[0], base: b0, par, pin, tacc: TA[0] }, { outS: S[1], outT: TA[1] }, u);
        S.reverse();
        TA.reverse();
    }
    par.destroy();
    pin.destroy();
    S[1].destroy();
    TA[1].destroy();
    return { state: S[0], accum: TA[0] };
}


// ------------------------------------------------------------------------------------------- breakup ---

const sign2 = (x) => {
    const s = pyFormat(x, '.2f');
    return s.startsWith('-') ? s : '+' + s;
};

/** Stage op 'breakup' (module doc). ctx: the level runner's StageContext (pins, log). */
export async function opBreakup(fields, level, params = null, seed = 0, ctx = null) {
    const log = HY.logOf(null, ctx, '[terrain.detail] ');
    const p = paramsOf(BREAKUP, params, 'breakup');
    const t0 = performance.now();
    const R = fields.R, D = Gd.dummies(R), P = prims(R);
    const cell = Number(level.cell);
    const hIn = fields.h;
    const [nh, nw] = [hIn.h, hIn.w];
    const temp = [];
    const keep = (f) => { temp.push(f); return f; };
    try {
        const bk = keep(strength(p, level, hIn, seed));            // (R, kfac, sc_abs, D)
        const { gx, gy, s: slopeField } = HY.boxGradient(hIn, cell, 2);      // grid.gradient(HY._box(h_in, 2), cell)
        keep(gx);
        keep(gy);
        keep(slopeField);
        const { pin_w: pw, pin_h: ph, made } = HY.pinsFor(fields, level, hIn, ctx);
        temp.push(...made);
        let mode = p.threshold;
        if (mode === 'auto') mode = 'Sc' in fields ? 'field' : 'relative';
        const modes = { relative: 0, absolute: 1, field: 2 };
        if (!(mode in modes)) {
            throw new ValueError(`breakup: threshold ${pyReprValue(mode)} is not 'auto', 'relative', 'absolute' or 'field'`);
        }
        const [lo, hi] = p.rock_slope_deg.map(Number);
        const A = keep(R.field(nh, nw, 4)), scF = R.field(nh, nw, 1);
        const hasSc = 'Sc' in fields;
        R.run('detail/breakup_surface', { gx, gy, bk, pw: pw ?? D.f1, sc: hasSc ? fields.Sc : D.f1 }, { outA: A, outF: scF },
            { uLo: lo, uDen: Math.max(hi - lo, 1e-12), uCap: Number(p.normal_cap), uMargin: Number(p.margin_deg),
                uSpread: Number(p.spread_deg), uMin: Number(p.min_deg), uMax: Number(p.max_deg),
                uSoilTan: Gd.tanDeg(Number(p.soil_deg)), uMode: modes[mode], uHasPw: pw ? 1 : 0, uHasSc: hasSc ? 1 : 0 });
        const parts = R.unpack(A, ['w', 'rock', 'sc_eff', 'sc_new']);
        const { w: weather, rock, sc_eff: scEff, sc_new: scNew } = parts;
        keep(weather);
        keep(rock);
        keep(scEff);
        // the rock threshold's relaxation, in cell units from the weathered surface h1 = h_in + weathering
        const h1 = keep(Gd.arith(R, 'add', hIn, weather));
        const href = (await P.stats(h1)).min;                      // float(h1.min())
        const b0 = keep(R.field(nh, nw, 4));
        R.run('detail/to_cells', { h: hIn, add: weather, cap: D.f1, pw: D.f1 }, { outF: b0 },
            { uHref: href, uCell: cell, uHasAdd: 1, uHasCap: 0, uPin: 0 });
        let bedC = null;
        if ('bed' in fields) {
            bedC = keep(R.field(nh, nw, 4));
            R.run('detail/to_cells', { h: fields.bed, add: D.f1, cap: b0, pw: D.f1 }, { outF: bedC },
                { uHref: href, uCell: cell, uHasAdd: 0, uHasCap: 1, uPin: 0 });
        }
        const rep = Gd.tanDeg(Number(p.repose_deg));
        const { state, accum } = relax(b0, bedC, scEff, rep, p.iterations, p.rate, HY.BOUND_OPEN,
            -Number(p.max_fail_m) / cell);
        keep(state);
        keep(accum);
        const dH = keep(R.field(nh, nw, 1)), dBed = keep(R.field(nh, nw, 1)), talus = keep(R.field(nh, nw, 1));
        R.run('detail/pipe_out', { st: state, ta: accum, add: weather, wet: D.f1 },
            { outDH: dH, outDB: dBed, outTal: talus, outWet: keep(R.field(1, 1, 1)) },
            { uCell: cell, uNWet: 1.0, uHasAdd: 1, uTalus: 1, uWet: 0 });
        const res = HY.finish(fields, { hIn, change: dH, bed: dBed, bedMode: 0, pinW: pw, pinH: ph, talus, level,
            anchorM: p.anchor ? HY.anchorScaleM(level, p.anchor_m) : null });
        const L = keep(HY.logDh(res.h, hIn));                      // dh = fields['h'] - h_in
        const Dabs = keep(HY.logDh(keep(R.unpack(bk, [null, null, null, 'D']).D)));    // |D| in its channel 2
        res.apply();
        // the rock's numbers for the stages after this one: the erodibility factor (kfac, also as the fluvial stage's
        // K_factor) and the threshold (Sc; Sc_factor is its ratio to what the level had)
        const { kfac } = R.unpack(bk, [null, 'kfac', null, null]);
        fields.kfac = kfac;
        fields.K_factor = kfac;
        if ('K' in fields) fields.K = Gd.arith(R, 'mul', fields.K, kfac);
        fields.Sc_factor = scF;
        fields.Sc = scNew;
        const rockMean = (await P.stats(rock)).mean;
        const dP99 = await P.percentile(Dabs, 99, { channel: 2 });
        const [c1, c99] = await P.percentile(L, [1, 99], { channel: 3, dtype: 'float64' });
        const tmax = (await P.stats(fields.talus)).max;
        log(`level ${level.index} (${pyFormat(cell, '.3g')} m x${level.n}): breakup in ${pyFormat((performance.now() - t0) / 1000, '.1f')} s; ` +
            `rock ${pyFormat(rockMean * 100, '.0f')} % of the level, relief |D| p99 ${pyFormat(dP99, '.2f')} m, change ` +
            `p1/p99 ${sign2(c1)} / ${sign2(c99)} m, talus max ${pyFormat(tmax, '.2f')} m`);
        return fields;
    } finally {
        for (const f of temp) if (!f.destroyed) f.destroy();
    }
}
opBreakup.takesCtx = true;


// --------------------------------------------------------------------------------------------- gully ---

/** A unit downhill direction per cell: the given flow vector field ({ x, y } fields) where it is, else down the
 * surface box-smoothed over smoothM. { dx, dy }: two new fields (detail.py flow_direction). */
export function flowDirection(h, cell, smoothM, flow = null) {
    const R = h.runner;
    let fx, fy, neg = 0, own = [];
    if (flow) {
        [fx, fy] = [flow.x ?? flow[0], flow.y ?? flow[1]];
    } else {
        const r = Math.max(1, Math.trunc(pyRound(Number(smoothM) / Number(cell) / 2.0)));
        const g = HY.boxGradient(h, cell, r);                       // grid.gradient(HY._box(h, r), cell)
        g.s.destroy();
        [fx, fy, neg] = [g.gx, g.gy, 1];
        own = [g.gx, g.gy];
    }
    const dx = R.field(h.h, h.w, 1), dy = R.field(h.h, h.w, 1);
    R.run('detail/flow_dir', { fx, fy }, { outX: dx, outY: dy }, { uNeg: neg });
    for (const f of own) f.destroy();
    return { dx, dy };
}

/** The gully kernel's octave table for a level (two texels per octave: (lam, amp, frac x, frac y), (base x, base y,
 * num, lo)), in doubles: lattice coordinates as an integer cell and a fraction, with the lattice offset of each
 * octave in the base (kernels/detail/phacelle.wgsl phacelle_coord). { table: Float32Array, octaves, lam0, amp0 }:
 * the octaves gully_relief runs (it stops under 3 cells). */
export function gullyTable(p, level, seed) {
    const cell = Number(level.cell);
    const lam0 = Number(p.wavelength_m || 12.0 * cell);
    const amp0 = Number(p.amp_m !== null && p.amp_m !== undefined ? p.amp_m : 0.08 * lam0);
    const rows = [];
    let lam = lam0, amp = amp0;
    for (let o = 0; o < Math.trunc(p.octaves); o++) {
        if (lam < 3.0 * cell) break;
        const [ox, oy] = N.latticeOffset(Math.trunc(seed) + 4242, o);
        // cell (0, 0)'s centre in lattice units, X / lam with X = x0 + 0.5 cell (level.xy()), and the step per cell
        const ax = (Number(level.x0) + 0.5 * cell) / lam, ay = (Number(level.y0) + 0.5 * cell) / lam;
        const bx = Math.floor(ax), by = Math.floor(ay);
        const s = cell / lam;
        const num = Math.round(s * 4096);
        const lo = s - num / 4096;
        const base = [bx + ox, by + oy];
        if (Math.abs(base[0]) >= 1 << 24 || Math.abs(base[1]) >= 1 << 24) {
            throw new ValueError('gully: lattice base beyond float32 integers: world coordinates too large');
        }
        rows.push([lam, amp, ax - bx, ay - by, base[0], base[1], num, lo]);
        lam *= 0.5;
        amp *= Number(p.gain);
    }
    const table = new Float32Array(Math.max(2 * rows.length, 2) * 4);
    rows.forEach((r, o) => table.set(r, 8 * o));
    return { table, octaves: rows.length, lam0, amp0 };
}

/** The gully octaves' relief in metres (before the mask), the mask, and their product: { g, mask, gm }, new fields
 * (detail.py gully_relief; flow: { x, y } fields or null). */
export function gullyRelief(level, h, p, seed, flow = null) {
    const R = h.runner;
    const cell = Number(level.cell);
    const { table, octaves, lam0 } = gullyTable(p, level, seed);
    const { dx, dy } = flowDirection(h, cell, Number(p.flow_smooth_m || lam0), flow);
    const s = HY.smoothedSlope(h, cell, 1);
    const [a0, a1, a2, a3] = p.slope_deg.map(Number);
    const oct = R.field(1, Math.max(2 * octaves, 2), 4, table);
    const g = R.field(h.h, h.w, 1), mask = R.field(h.h, h.w, 1), gm = R.field(h.h, h.w, 1);
    R.run('detail/gully', { dx, dy, s, oct }, { outG: g, outM: mask, outGM: gm },
        { uOct: octaves, uSteer: Number(p.steer), uNorm: Number(p.normalization), uA0: a0, uD1: Math.max(a1 - a0, 1e-12),
            uA2: a2, uD2: Math.max(a3 - a2, 1e-12) });
    for (const f of [dx, dy, s, oct]) f.destroy();
    return { g, mask, gm };
}

/** Stage op 'gully' (module doc): one evaluation per level. */
export async function opGully(fields, level, params = null, seed = 0, ctx = null) {
    const log = HY.logOf(null, ctx, '[terrain.detail] ');
    const p = paramsOf(GULLY, params, 'gully');
    const t0 = performance.now();
    const R = fields.R, P = prims(R);
    const hIn = fields.h;
    const flow = 'flow_x' in fields && 'flow_y' in fields ? { x: fields.flow_x, y: fields.flow_y } : null;
    const { g, mask, gm } = gullyRelief(level, hIn, p, seed, flow);
    const temp = [g, mask, gm];
    try {
        const { pin_w: pw, pin_h: ph, made } = HY.pinsFor(fields, level, hIn, ctx);
        temp.push(...made);
        const hasBed = 'bed' in fields;
        const res = HY.finish(fields, { hIn, change: gm, bed: hasBed ? fields.bed : null, bedMode: hasBed ? 1 : 2, pinW: pw,
            pinH: ph, level, anchorM: p.anchor ? HY.anchorScaleM(level, p.anchor_m) : null });
        res.apply();
        const L = HY.logDh(gm);
        temp.push(L);
        const on = (await P.stats(mask)).mean;
        const p99 = (await P.percentile(L, [99], { channel: 2, dtype: 'float64' }))[0];
        log(`level ${level.index} (${pyFormat(Number(level.cell), '.3g')} m x${level.n}): gully octave in ` +
            `${pyFormat((performance.now() - t0) / 1000, '.1f')} s, on ${pyFormat(on * 100, '.0f')} % of the level, |relief| p99 ` +
            `${pyFormat(p99, '.2f')} m`);
        return fields;
    } finally {
        for (const f of temp) if (!f.destroyed) f.destroy();
    }
}
opGully.takesCtx = true;


// ------------------------------------------------------------------------------------------ planation ---

/** Stage op 'planation' (module doc). */
export async function opPlanation(fields, level, params = null, seed = 0, ctx = null) {
    const log = HY.logOf(null, ctx, '[terrain.detail] ');
    const p = paramsOf(PLANATION, params, 'planation');
    const R = fields.R, P = prims(R);
    const hIn = fields.h;
    const [cx, cy] = level.centre;
    const az = Number(p.azimuth_deg) * DEG;
    const datum0 = p.datum_m !== null && p.datum_m !== undefined ? Number(p.datum_m) :
        await P.percentile(hIn, 15, { dtype: 'float64' });       // float(np.percentile(h_in, 15)), float64 data
    const spec = { kind: 'fbm', wavelength_m: Number(p.resist_wavelength_m), octaves: 4 };
    const res = N.fieldGpu(R, spec, level, Math.trunc(seed) + 6007);
    const small = { kind: 'fbm', wavelength_m: 60.0, octaves: 3, amp: 3.0 * Number(p.plain_relief_m) };
    const detail = N.fieldGpu(R, small, level, Math.trunc(seed) + 6011);
    const cov = Number(p.coverage);
    const h = R.like(hIn), change = R.like(hIn), hard = R.like(hIn);
    R.run('detail/planation', { h: hIn, res, det: detail }, { outH: h, outC: change, outHard: hard },
        { uDatum0: datum0, uTan: Gd.tanDeg(Number(p.tilt_deg)), uCos: Math.cos(az), uSin: Math.sin(az),
            uOx: Number(level.x0) - cx, uOy: Number(level.y0) - cy, uCell: Number(level.cell), uCovLo: cov - 0.04,
            uCovDen: Math.max((cov + 0.04) - (cov - 0.04), 1e-12), uSel: Number(p.selectivity), uResidual: Number(p.residual),
            uFootDen: Math.max(Number(p.piedmont_m) * Gd.tanDeg(25.0), 1e-6) });
    const temp = [res, detail, h, change, hard];
    try {
        const { pin_w: pw, pin_h: ph, made } = HY.pinsFor(fields, level, hIn, ctx);
        temp.push(...made);
        const hasBed = 'bed' in fields;
        // HY.finish(fields, h, minimum(fields.get('bed', h), h), h_in, pw, ph): no level, so no anchor
        const out = HY.finish(fields, { hIn, change: h, abs: true, absChange: change, bed: hasBed ? fields.bed : null,
            bedMode: hasBed ? 1 : 2, pinW: pw, pinH: ph });
        out.apply();
        const flags = P.where(hard, '>', 0.5);
        temp.push(flags);
        const { nonzero } = await P.statsU32(flags);
        log(`level ${level.index}: planation, residuals on ${pyFormat((nonzero / (hard.h * hard.w)) * 100, '.0f')} % of the level`);
        return fields;
    } finally {
        for (const f of temp) if (!f.destroyed) f.destroy();
    }
}
opPlanation.takesCtx = true;


export const OPS = { breakup: opBreakup, gully: opGully, planation: opPlanation };
export {
    paramsOf as _params, breakupTerms as breakup_terms, breakupUniforms as breakup_uniforms, flowDirection as flow_direction,
    gullyRelief as gully_relief, opBreakup as op_breakup, opGully as op_gully, opPlanation as op_planation,
};
