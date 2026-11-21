// Port of blender/eidoblend/terrain/solvers/coast.py at f90c6fc.
//
// Coasts (design section 4.11): sea cliffs cut back into the land, a wave-cut platform at their foot, beaches in
// sheltered bays, stacks where the retreat isolates a strong knob of rock.
//
//     stage ops (OPS; called by run.js as op(fields, level, params, seed, ctx)):
//       'coast_land'  the land the sea will cut into, as a function of s0 (metres inland of an original coastline:
//                     a line facing azimuth_deg, offset_m + retreat_m seaward of the main tile's centre, bent into
//                     headlands and bays by wiggle noise): the shape (landShape) rises inland from coast_frac at that
//                     line to the uplands and falls seaward to base level kilometres out (the coastal plain of the
//                     low sea levels the land was carved under, drowned and planed since). It writes U (U_m_per_yr x
//                     the shape; sea_cliffs uses none: an old surface the rivers cut into), the start surface on a
//                     fresh level, and coast_s0. The fluvial backbone then carves the land toward that distant base
//                     level, so its valleys reach the present cliff line high above the beach and are cut across:
//                     the Seven Sisters' hanging dry valleys, Moher's plateau streams. Run on 'all' levels with
//                     `refine` (a fluvial stage's parameters), it refines the land on each finer level down to the
//                     main one before the coast stage cuts it (refineLand: the uncut land restored, the band pinned
//                     to it, the backbone in refine mode, the runner's pins put back), so no level's downland is its
//                     parent's upsampled
//       'coast'       the sea's work, on every level (the cliff is rebuilt sharp at each level's own cells):
//         1. sea level: cells at or below it are sea;
//         2. on the first level it runs on, the shore plan from the original shoreline: coast_land's s0 = 0 line
//            where the land stage made one, else the surface's sea-level line, counting as sea only the water that
//            reaches the window's edge (a hollow below sea level inland is land to the coast: seaPhi). The open-water
//            fetch over 16 directions from every shore cell (the fetch kernel: an exact grid traversal over the sea
//            mask up to fetch_max_m, 20 km) is normalised to the exposure 0..1 (0.5 on a straight open coast) and
//            carried to every cell by jump flooding (JFA) from the shoreline at sub-cell precision together with the
//            signed distance to that shoreline; both are fields (coast_E, coast_d0) that every finer level inherits,
//            so all levels cut the same cliff line;
//         3. the retreat distance R = retreat_m (E / 0.5)^exposure_power w(x): exposure times rock weakness (w =
//            exp(weakness n), world-space noise: weak rock retreats into coves, strong rock stands as headlands; a
//            strong knob on a headland cut from both sides stays as a stack, its walls at stack_face_deg, near
//            vertical, so a narrow one stands as a column, not a pyramid) plus a few metres of crenellation (the
//            cliff line's buttresses and recesses) plus the collapse scars' bites (scarField: a world lattice of
//            scars, each recessing the cliff line 3-12 m over a 20-90 m scallop, a fresh face). Land closer than R
//            to the original shore is cut away; cut regions that do not reach the sea or the window edge are filled
//            back (the sea cannot get there);
//         4. the cliff foot is the zero line of d0 - R; the signed distance s to it (JFA again, sub-cell) shapes the
//            ground: inland the face, Z(s) = foot + s tan(face) (chalk 74-82 degrees, the angle of the nearest point
//            of the foot line, so a face profile never turns down), or a rock column's stepped face (Moher:
//            sandstone ledges at 84 degrees over siltstone at 58), meeting the land at a rounded edge, so the cliff
//            stands as high as the land is there; seaward the wave-cut platform (platform_top_m at the foot, falling
//            at platform_slope_deg to the sea floor sea_floor_m down, rough by a few decimetres), with a talus apron
//            at 35 degrees under the face (its height a share of the cliff's), a lobe of fallen blocks under each
//            scar (scar_debris of its bite high, falling seaward at debris_deg), a shingle beach on exposed coast (a
//            berm at shingle_m against the foot, then the beach face down to the platform at -0.6 m shingle_w_m out,
//            the width changing along the shore by shingle_var), and in sheltered bays (low exposure) a sand beach:
//            a berm, the beach face, and the Dean profile h = -A y^(2/3) below the waterline (A 0.1). A rock column
//            (Moher's beds, the chalk's beds and flint bands) steps the face, and its stratigraphic height is written
//            as zs;
//         5. wear (the rock cut away), talus (the apron), deposit (beach and shingle), bed (the rock surface) and Sc
//            (the face's angle, for the detail package's breakup on the hero levels) are written; a child level's
//            border band blends to its parent's surface.
//
// Every input is a function of world position (metres) or a field inherited from the level that made the plan, so a
// level's cliff line lies where its parent's does, at sub-cell precision.
//
// Kernels (Blender's inline GLSL, transcribed: kernels/coast_fetch.wgsl, coast_seed.wgsl, coast_jfa.wgsl; their
// numpy twins stay in Python, the oracles of tests/parity/fixtures.py --kernels):
//     coast_fetch  exposure of every shore sea cell (the 16-direction fetch, normalised; each ray walks every cell it
//                  passes, so it cannot slip between two land cells meeting at a corner); -1 elsewhere. One source
//                  per ray count, named coast_fetch_<n> as Blender names it
//     coast_seed   the jump-flood seeds of a level set phi (< 0 seaward): every cell next to a sign change gets the
//                  nearest zero crossing on its 8 neighbour segments (sub-cell), and the payload of the crossing's
//                  seaward cell
//     coast_jfa    one jump-flooding pass at a step: each cell keeps the nearest of the seeds its 9 probes see
//
// Frames and units (design 2.1): arrays [row j, column i], row 0 south, cell centres at x0 + (i + 0.5) cell;
// metres, degrees, years. Exposure is dimensionless (0..1).
//
// Where this differs from coast.py, and why (PORT_PLAN.md 2.4, 3.2: every per-cell step runs on the GPU):
//   - Fields are core/gpu.js fields (a level's Fields); the ops are async. Ops get the runner from ctx.device, else
//     from the fields. Blender's numpy over whole levels (the land shape, the retreat, the scars, the face, the
//     platform and the beaches, the band, the writes) runs as the port's own kernels, in this package's kernel
//     folder kernels/karst/ (coast_*.wgsl: PORT_PLAN.md 3.1 and 8.2 give the karst-and-coast package one folder,
//     the one the field hash covers, C8); each names the numpy lines it replaces. They are not Blender kernels, so
//     the dispatch-log comparison sets them aside (plan 5.7). numpy's float64 there is float32 here.
//   - nearest_crossing's hypot and its callers' sign and scale are a kernel (kernels/karst/coast_crossing.wgsl).
//   - Labels (seaPhi, connected, the stacks) are core/prims.js label (numpy's numbering, exact); the per-label
//     decisions are kernels over the labels; the maximum filter is core/prims.js dilate (a square dilation: on 0 / 1
//     masks its edge padding is the twin's open fill); hillslope's gaussian_blur is core/prims.js gaussianBlur, mode
//     'reflect' (solvers/hillslope.js).
//   - The rock column's table (columnTable) is built in JavaScript in float64 as numpy builds it (a 1D table of 2,641
//     rows), and read on the GPU by a binary search (np.interp's).
// The convergence loops this module names for the dispatch-log comparison (PORT_PLAN.md 5.7): none of its own (the
// jump flood's steps are a function of the level's size); coast_land's refine runs solvers/fluvial.js, whose loops
// that module names.

import { kernelUrl } from '../core/gpu.js';
import * as Gd from '../core/grid.js';
import { KeyError, closeMatches, pyFormat, pyRound } from '../core/levels.js';
import { prims } from '../core/prims.js';
import * as N from '../core/world_noise.js';
import * as FL from './fluvial.js';
import * as HS from './hillslope.js';
import { pairwiseSum } from './karst.js';

export const E_REF = 0.5;                       // the exposure of a straight open coast: half the rays run out to sea


// ------------------------------------------------------------------------------------------------ parameters ---

export const DEFAULTS = Object.freeze({
    sea_level: null,            // metres; null: the run's sea level (makeTerrain's seaLevel), else 0
    retreat_m: 300.0,           // the retreat of a straight open coast (exposure 0.5) in average rock: about the
                                // wave-cut platform's width (Seven Sisters: 200-400 m)
    exposure_power: 1.0,        // R ~ (E / 0.5)^power: headlands (high fetch) retreat faster than bays
    exposure_clamp: [0.25, 1.6],    // the exposure factor's range
    fetch_max_m: 20000.0,       // the longest fetch the rays look along
    fetch_dirs: 16,
    exposure_smooth_m: 250.0,   // the exposure is smoothed along the shore (a cell's own fetch is noisy)
    weakness: 0.15,             // ln-standard deviation of the rock weakness (chalk 0.15: a straight cliff line;
                                // layered shale and sandstone 0.45: coves, headlands, stacks)
    weakness_scales_m: [900.0, 300.0, 100.0],
    stacks: 0.0,                // strong knobs (0..1): where a headland is cut from both sides around one, a stack
    stack_scale_m: 140.0,
    stack_face_deg: 86.0,       // a knob stands because its rock is strong: its walls near vertical (with the
                                // coast's 74 degree bedded face a narrow knob converged to a pyramid, not a column)
    crenel_m: 3.0,              // the cliff line's buttresses and recesses, metres (std)
    crenel_scales_m: [45.0, 15.0],
    face_deg: 78.0,             // the cliff face (a single rock: chalk 74-82 degrees)
    face_spread_deg: 4.0,       // +- by world noise at face_scale_m
    face_scale_m: 70.0,
    column: null,               // null (one face angle), 'moher', or [[thickness_m, angle_deg], ...] repeating from
                                // column_base_m up: each bed stands at its own angle (the stepped face)
    column_base_m: 0.0,         // the column's first bed starts at this stratigraphic height (m above sea level)
    column_dip_deg: 0.0,        // the beds' dip and the compass direction they dip toward
    column_dip_azimuth_deg: 180.0,
    top_round_m: 2.5,           // the cliff top's rounding (a smooth minimum this many metres wide)
    talus_frac: 0.07,           // the apron under the face: this share of the cliff's height, by noise 0.3-1.7 x
    talus_max_m: 14.0,
    talus_deg: 35.0,
    platform_top_m: -0.2,       // the wave-cut platform at the cliff foot, metres above sea level (intertidal: under
                                // the 0.3 m the references count as sea, so its runnels do not speckle the shore)
    platform_slope_deg: 0.7,    // it falls seaward at this angle ...
    sea_floor_m: 15.0,          // ... down to the sea floor this deep, which it meets in a smooth curve
    platform_rough_m: 0.15,     // its runnels and steps (std, metres; 20 m and 6 m)
    shingle_m: 1.3,             // the shingle beach at the foot of an exposed cliff: its crest above sea level ...
    shingle_w_m: 14.0,          // ... and its width from the foot to where it meets the platform (-0.6 m)
    shingle_berm: 0.35,         // the berm: the flat crest's share of the width (then the beach face)
    shingle_var: 0.0,           // the width's change along the shore (ln std; world noise at shingle_scales_m)
    shingle_scales_m: [700.0, 220.0],
    scars: 0.0,                 // collapse scars (0..1: the share of lattice cells holding one): bites out of the
    scar_spacing_m: 140.0,      // cliff line, fresh faces recessed scar_depth_m over a scar_radius_m disc ...
    scar_radius_m: [18.0, 45.0],
    scar_depth_m: [3.0, 12.0],
    scar_debris: 0.6,           // ... with a lobe of fallen blocks at the foot: its height, a share of the bite ...
    debris_deg: 24.0,           // ... falling seaward at this angle
    beach_exposure: [0.30, 0.42],   // exposure where sand beaches take over (full beach below the first)
    beach_berm_m: 2.2,          // the berm's height above sea level
    beach_backshore_m: 35.0,    // the dry beach between the foot and the berm crest (full beach)
    beach_face_deg: 6.0,        // the beach face from the berm crest to the waterline
    dean_A: 0.1,                // the Dean profile below the waterline: depth = A y^(2/3), m^(1/3) (fine sand)
    connect: true,              // cut regions must reach the sea (or the window edge)
    seed: 0,
});

export const LAND_DEFAULTS = Object.freeze({
    azimuth_deg: 200.0,         // the compass direction the coast faces (toward the sea): Seven Sisters 200
    offset_m: 390.0,            // the cliff line passes this far from the main tile's centre, toward the sea
    retreat_m: 300.0,           // (the coast stage's): the original coastline lies this much further seaward
    wiggle_m: 120.0,            // the original coastline's headlands and bays (std, metres) ...
    wiggle_scale_m: 2500.0,     // ... and their wavelength
    coast_frac: 0.5,            // the land's height at the original coast, as a share of the uplands'
    rise_m: 1500.0,             // inland of the original coast the land rises to the uplands over this distance ...
    inland_gain: 0.35,          // ... then changes by this share toward tilt_m inland (negative: a dip slope, Moher)
    tilt_m: 5000.0,
    texture: 0.3,               // multi-scale texture of the uplift and the start (share)
    texture_scales_m: [3000.0, 1200.0],
    U_m_per_yr: 0.0,            // uplift, m/yr x the shape (0: an old surface the rivers cut into, sea_cliffs' land)
    start_m: 150.0,             // the start surface: the shape scaled to this height ...
    start_roughness: 0.25,      // ... with this much noise (keep its gradients under the regional slope when U = 0,
    start_scales_m: [2400.0, 900.0],    // or its hollows outlast a short run)
    refine: null,               // child levels: a fluvial stage's parameters to refine the land with before the sea
                                // cuts it (refineLand); null leaves a child's land its parent's, upsampled
    refine_min_cell_m: null,    // ... on levels with cells of at least this (null: the main level's cell)
    refine_creep_m2: 0.0,       // ... then linear creep (kappa t, m^2) of the refined land: its crests and valley
                                // sides rounded at the level's own cells (the downs' broad convex interfluves; the
                                // refine alone left knife-edged crests and V notches, a mountain range in miniature)
    seed: 0,
});
// Seaward of the original coast the land goes on down to base level (landShape): the coastal plain of the low sea
// levels the downs were carved under, drowned since and planed by the waves. So the rivers' base level lies km out,
// and the valleys reach the present cliff line high above the beach, cut across: the Seven Sisters' hanging dry
// valleys (a sea pinned at the original coast instead graded every valley to it, 300 m from the cliff, and left the
// cliff tops 16 m high where the reference's stand 63 m).

// Rock columns for the stepped face: [thickness_m, face angle in degrees], from column_base_m up, repeated.
// Moher (Gull Island Formation over the Clare shales): sandstone beds standing near vertical, siltstone and shale
// partings cut back into ledges; the overall face about 74 degrees.
export const COLUMNS = Object.freeze({
    moher: [[9.0, 84.0], [5.0, 58.0], [6.0, 82.0], [3.5, 55.0], [11.0, 85.0], [4.0, 60.0]],
    // the Seaford and Newhaven chalk of the Seven Sisters: thick beds standing at 79-82 degrees, each topped by a
    // band of flint nodules the face weathers back a little (a nick at 70-73 degrees): the face's horizontal lines
    // (the material reads the flint bands from the same stratigraphic height, `zs`); overall about 79 degrees
    chalk: [[3.2, 80.0], [0.6, 71.0], [2.4, 82.0], [0.6, 72.0], [4.1, 79.0], [0.6, 70.0], [1.8, 81.0],
        [0.6, 73.0]],
});

/** The full parameter dict: DEFAULTS (or `table`), then the caller's values (an unknown key names the nearest). */
export function paramsFor(params = null, table = null) {
    table = table ?? DEFAULTS;
    const out = structuredClone({ ...table });
    for (const [k, v] of Object.entries(params ?? {})) {
        if (k === 'enabled') continue;
        if (!(k in table)) {
            const near = closeMatches(k, Object.keys(table), 3);
            throw new KeyError(`coast: no parameter '${k}'` + (near.length ? `; nearest: ${near.join(', ')}` : ''));
        }
        out[k] = v;
    }
    return out;
}


// =================================================================================================== kernels ===

/** The fetch directions as exact float32 pairs [x0, y0, x1, y1, ...] (written into the kernel source, so the twin
 * uses the same): n directions offset half a step from the grid axes, so no ray runs along an axis-aligned shore
 * row. */
export function dirs(n) {
    const out = new Float32Array(2 * n);
    for (let k = 0; k < n; k++) {
        const a = (2.0 * Math.PI * (k + 0.5)) / n;
        out[2 * k] = Math.cos(a);
        out[2 * k + 1] = Math.sin(a);
    }
    return out;
}

/** 1 / |direction| per axis, float32 (the ray parameter between two grid lines on that axis, in cells). */
export function invDirs(n) {
    const d = dirs(n);
    return Float32Array.from(d, (v) => 1.0 / Math.abs(v));
}

// a float32 value as a WGSL literal that parses back to the same float32 (the shortest double that equals it)
const lit = (v) => {
    const s = String(v);
    return /[.eE]/.test(s) || !Number.isFinite(v) ? s : `${s}.0`;
};
const table = (a) => `array<vec2<f32>, ${a.length / 2}>(` +
    Array.from({ length: a.length / 2 }, (_, k) => `vec2<f32>(${lit(a[2 * k])}, ${lit(a[2 * k + 1])})`).join(', ') + ')';

const KERNELS = new WeakMap();
function kernelOf(R, key, make) {
    let m = KERNELS.get(R);
    if (!m) KERNELS.set(R, (m = new Map()));
    let k = m.get(key);
    if (!k) m.set(key, (k = make()));
    return k;
}

/** The fetch kernel for `ndirs` directions: kernels/coast_fetch.wgsl with the direction tables as consts, named
 * coast_fetch_<ndirs> as Blender names its source (coast.py fetch_kernel). */
export function fetchKernel(R, ndirs = 16) {
    const n = Math.trunc(ndirs);
    return kernelOf(R, `coast_fetch_${n}`, () => R.kernel(`coast_fetch_${n}`, { url: kernelUrl('coast_fetch').href,
        blender: true, defines: { NDIR: String(n), DIRS: table(dirs(n)), INV: table(invDirs(n)) } }));
}

/** coast.py SEED and JFA: the Blender kernels kernels/coast_seed.wgsl and coast_jfa.wgsl. */
export const seedKernel = (R) => kernelOf(R, 'coast_seed', () => R.kernel('coast_seed'));
export const jfaKernel = (R) => kernelOf(R, 'coast_jfa', () => R.kernel('coast_jfa'));
const own = (R, name) => kernelOf(R, `karst/${name}`, () => R.kernel(`karst/${name}`));

/** The jump-flooding schedule for an n-cell grid: n/2, n/4, ..., 1, then 2 and 1 again (JFA+2: the few cells plain
 * JFA leaves on a wrong seed pick the right one). */
export function jfaSteps(n) {
    const steps = [];
    let k = 1;
    while (k < n) k *= 2;
    k = Math.floor(k / 2);
    while (k >= 1) {
        steps.push(k);
        k = Math.floor(k / 2);
    }
    return [...steps, 2, 1];
}

/** Jump flooding from the zero line of `phi` (an (n, n) field, < 0 seaward). Returns the field of
 * kernels/karst/coast_crossing.wgsl: x the unsigned distance of every cell centre to the nearest zero crossing (cell
 * units, sub-cell precise; +inf where there is no crossing anywhere), y that crossing's payload (0 when none is
 * given), z 1 where a crossing was found. opts.signed: { neg (a field, > 0.5 where the distance takes the minus
 * sign), cell (metres), far (metres for a cell with no crossing) } gives x as signed metres instead. A new field. */
export function nearestCrossing(R, phi, payload = null, opts = {}) {
    const [H, W] = [phi.h, phi.w];
    const zero = payload ? null : R.field(H, W, 1);
    const A = R.pair(H, W, 4);
    R.run(seedKernel(R), { phiT: phi, payT: payload ?? zero }, { outS: A.src }, {});
    const jfa = jfaKernel(R);
    for (const st of jfaSteps(Math.max(H, W))) {
        R.run(jfa, { st: A.src }, { outS: A.dst }, { uStep: Math.trunc(st) });
        A.swap();
    }
    const out = R.field(H, W, 4);
    const sg = opts.signed ?? null;
    R.run(own(R, 'coast_crossing'), { st: A.src, neg: sg?.neg ?? phi }, { outD: out },
        { uSign: sg ? 1 : 0, uCell: sg ? Number(sg.cell) : 1.0, uFar: sg ? Number(sg.far) : 0.0 });
    A.destroy();
    if (zero) zero.destroy();
    return out;
}

/** The exposure of every shore sea cell (mean open-water fetch over ndirs directions / fetch_max_m, 0..1; rays
 * leaving the grid over water count as open sea); -1 on every other cell. `sea`: a field, 1 at sea. A new field. */
export function exposure(R, sea, cell, fetchMaxM = 20000.0, ndirs = 16) {
    const out = R.field(sea.h, sea.w, 1);
    R.run(fetchKernel(R, ndirs), { seaT: sea }, { outE: out },
        { uMaxCells: Math.max(1, pyRound(Number(fetchMaxM) / Number(cell))) });
    return out;
}

/** One of the port's own coast kernels by its path under kernels/ ('karst/coast_ew'). */
const kernel = (R, name) => kernelOf(R, name, () => R.kernel(name));
const groups = (h, w) => [Math.ceil(w / 16), Math.ceil(h / 16), 1];
const RGBA = new WeakMap();
const rgba1 = (R) => { let f = RGBA.get(R); if (!f) RGBA.set(R, (f = R.field(1, 1, 4))); return f; };
// 1 x 1 targets for a kernel's outputs a call does not use: never a field another binding of the dispatch reads or
// writes (the runner refuses one field bound twice), so each unused output takes its own
const SINKS = new WeakMap();
function sinks(R) {
    let s = SINKS.get(R);
    if (!s) {
        s = { f1: R.field(1, 1, 1), f1b: R.field(1, 1, 1), u1: R.field(1, 1, 1, null, 'u32'), u1b: R.field(1, 1, 1, null, 'u32') };
        SINKS.set(R, s);
    }
    return s;
}

/** One cell-by-cell step of kernels/karst/coast_ew.wgsl (its modes are numpy lines of coast.py): { F, G, U } new
 * fields (G and U only when asked: outs 'G', 'U'). */
function ew(R, mode, ins = {}, k = [0, 0, 0], outs = '', flags = [0, 0], shape = null) {
    const D = Gd.dummies(R);
    const ref = ins.a ?? ins.b ?? ins.c;
    const [h, w] = shape ?? [ref.h, ref.w];
    const F = R.field(h, w, 1);
    const G = outs.includes('G') ? R.field(h, w, 1) : null;
    const U = outs.includes('U') ? R.field(h, w, 1, null, 'u32') : null;
    R.run(kernel(R, 'karst/coast_ew'), { a: ins.a ?? D.f1, b: ins.b ?? D.f1, c: ins.c ?? D.f1, d: ins.d ?? rgba1(R) },
        { outF: F, outG: G ?? sinks(R).f1, outU: U ?? sinks(R).u1 }, { uMode: mode, uHas: flags[0], uHas2: flags[1], uK0: k[0], uK1: k[1], uK2: k[2] },
        groups(h, w));
    return { F, G, U };
}


// ========================================================================================== world-space inputs ===

/** A world_noise field spec at the level's cells (coast.py _field: field_gpu in production): a new GPU field. */
function field(R, spec, level, seed) {
    return N.fieldGpu(R, spec, level, Math.trunc(seed));
}

/** Noise of standard deviation 1 (fbm's 1/3, times 3): fbm at each scale the level resolves (minCells cells and up),
 * equal weights unless `amps` are given (normalised over ALL the scales) (coast.py _unit_noise). A new field, or null
 * where the level resolves none of the scales (numpy's zeros). */
export function unitNoise(R, scales, level, seed, baseSeed, minCells = 3.0, amps = null) {
    const sc = (scales ?? []).map(Number);
    const am = amps === null ? sc.map(() => 1.0) : amps.map(Number);
    let norm = 0;
    for (const a of am) norm += a * a;
    norm = Math.sqrt(norm) || 1.0;
    const terms = [];
    sc.forEach((s, i) => {
        if (s >= minCells * level.cell) terms.push({ kind: 'fbm', wavelength_m: s, octaves: 2, seed: baseSeed + i, amp: (3.0 * am[i]) / norm });
    });
    if (!terms.length) return null;
    return field(R, { kind: 'sum', terms }, level, seed);
}

/** The unit vector toward the sea, world (x east, y north), from the compass direction the coast faces. */
export function seaVector(azimuthDeg) {
    const a = (Number(azimuthDeg) * Math.PI) / 180.0;
    return [Math.sin(a), Math.cos(a)];
}

const centreOf = (ctx, level) => {
    const lv = ctx?.main ?? level;
    return [lv.x0 + lv.side / 2.0, lv.y0 + lv.side / 2.0];
};

// per-axis (x - cx) and (y - cy) of a level's cell centres, doubles rounded once: an rg32f (2, n) field
function axesField(R, level, cx, cy, sx = 1.0, sy = 1.0) {
    const n = level.n, a = new Float32Array(4 * n);
    for (let i = 0; i < n; i++) {
        a[2 * i] = (level.x0 + (i + 0.5) * level.cell - cx) * sx;
        a[2 * (n + i)] = (level.y0 + (i + 0.5) * level.cell - cy) * sy;
    }
    return R.field(2, n, 2, a);
}


// ===================================================================================================== land ===

/** The land the sea cuts on a level (coast.py shore_coordinate, land_shape and op_coast_land's arithmetic):
 * kernels/karst/coast_land.wgsl's (s0, U, h0, shape) pack. tex / rough: the texture and start noise fields or null. */
function landPack(R, level, P, seed, centre) {
    const [ux, uy] = seaVector(P.azimuth_deg);
    const wig = Number(P.wiggle_m) > 0 ? field(R, { kind: 'fbm', wavelength_m: Number(P.wiggle_scale_m), octaves: 3, seed: 911, amp: 3.0 }, level, seed) : null;
    return { wig, run: (t, r) => {
        const c = clip(Number(P.coast_frac), 0.02, 0.98);
        const rise = Math.max(Number(P.rise_m), 1.0);
        const axes = axesField(R, level, centre[0], centre[1]);
        const out = R.field(level.n, level.n, 4);
        const D = Gd.dummies(R);
        R.run(kernel(R, 'karst/coast_land'), { axes, wig: wig ?? D.f1, tex: t ?? D.f1, rough: r ?? D.f1 }, { outL: out },
            { uUx: ux, uUy: uy, uOffset: Number(P.offset_m), uRetreat: Number(P.retreat_m), uWiggle: Number(P.wiggle_m),
                uC: c, uRise: rise, uGain: Number(P.inland_gain), uTilt: Math.max(Number(P.tilt_m), 1.0), uL: (c * rise) / (1.0 - c),
                uTexture: Number(P.texture), uURate: Number(P.U_m_per_yr), uStart: Number(P.start_m), uRoughK: Number(P.start_roughness),
                uFlags: (t ? 1 : 0) | (r ? 2 : 0) | (wig ? 4 : 0) });
        axes.destroy();
        return out;
    } };
}

/** A child's border band weights without the runner's sea hold: 1 on the outer 2 cells, easing to 0 at band cells
 * in (coast.py _band_pins and _band_weight, the same ramp). A new field. */
export function bandPins(R, level) {
    const d = Gd.edgeDistance(R, level.n);
    const { F } = ew(R, 6, { a: d }, [Math.max(level.band - 2, 1), 0, 0]);
    d.destroy();
    return F;
}

export const CHILD_ZONE = 6;                    // child cells (3 parent cells): the Catmull-Rom stencil reaches 2 parent cells

/** The uncut land on a child level, and the weight of the zone near the parent's cut (coast.py _child_land):
 * { land, w } new fields. */
export function childLand(R, fields, _level) {
    const h = fields.h;
    if (!('coast_land' in fields)) return { land: copyOf(R, h), w: Gd.fill(R, [h.h, h.w], 0.0) };
    const cut = 'coast_cut' in fields ? ew(R, 8, { a: fields.coast_cut }).F : Gd.fill(R, [h.h, h.w], 0.0);
    const P = prims(R);
    const r0 = P.dilate(cut, CHILD_ZONE), r1 = P.dilate(r0, 1), r2 = P.dilate(r1, 1), r3 = P.dilate(r2, 1);
    const out = R.field(h.h, h.w, 2);
    R.run(kernel(R, 'karst/coast_child'), { h, landBl: fields.coast_land, r0, r1, r2, r3 }, { outC: out });
    const land = takeChannel(R, out, 0), w = takeChannel(R, out, 1);
    for (const f of [cut, r0, r1, r2, r3, out]) f.destroy();
    return { land, w };
}

// one channel of a field as an r32f field (kernels/karst/coast_pick.wgsl; core/gpu.js unpack reads 4-channel packs)
function takeChannel(R, f2, c) {
    const out = R.field(f2.h, f2.w, 1);
    R.run(kernel(R, 'karst/coast_pick'), { src: f2 }, { outF: out }, { uChannel: c, uK: 0.0 });
    return out;
}

function copyOf(R, f) {
    const g = R.like(f);
    R.copy(f, g);
    return g;
}

/** On a child level: the land the sea will cut, refined at this level's cells (coast.py refine_land: its doc). */
export async function refineLand(fields, level, P, seed, ctx) {
    const R = ctx.device;
    const { land, w: zone } = childLand(R, fields, level);
    zone.destroy();
    const pins = ctx.pins;
    let keep = null, band = null, pinH = null;
    if (pins !== null && pins !== undefined) {
        keep = { pin_w: pins.pin_w, pin_h: pins.pin_h };
        band = bandPins(R, level);
        pinH = copyOf(R, land);
        pins.pin_w = band;
        pins.pin_h = pinH;
    }
    fields.h = copyOf(R, land);
    if ('bed' in fields) fields.bed = ew(R, 9, { a: fields.bed, b: fields.h }).F;
    try {
        await FL.opFluvial(fields, level, structuredClone(P.refine), seed, ctx);
    } finally {
        if (keep !== null) {
            Object.assign(pins, keep);
            band.destroy();
            pinH.destroy();
        }
    }
    const kt = Number(P.refine_creep_m2 || 0.0);
    if (kt > 0) {
        // linear creep (a Gaussian of sigma sqrt(2 kappa t)), the border band held to the restored land
        const hb = HS.gaussianBlur(fields.h, Math.sqrt(2.0 * kt) / Number(level.cell));
        const wb = bandPins(R, level);
        fields.h = ew(R, 7, { a: hb, b: land, c: wb }).F;
        hb.destroy();
        wb.destroy();
        if ('bed' in fields) fields.bed = ew(R, 9, { a: fields.bed, b: fields.h }).F;
    }
    land.destroy();
    (ctx.shared.coast_uncut ??= []).push(Math.trunc(ctx.index));
}

/** Stage 'coast_land' (coast.py op_coast_land: the module doc). */
export async function opCoastLand(fields, level, params, seed = 0, ctx = null) {
    ctx = await FL.asContext(ctx, fields, level);
    const R = ctx.device ?? fields.R;
    ctx.device = R;
    const P = paramsFor(params, LAND_DEFAULTS);
    const s = Math.trunc(seed) + Math.trunc(P.seed);
    if (ctx.role === 'refine') {
        if (P.refine && ctx.prepass === null && 'coast_d0' in fields) {
            const main = ctx.main;
            const lo = Number(P.refine_min_cell_m !== null && P.refine_min_cell_m !== undefined ? P.refine_min_cell_m :
                (main ? main.cell : level.cell));
            if (Number(level.cell) >= lo * (1.0 - 1e-6)) await refineLand(fields, level, P, s, ctx);
        }
        return fields;
    }
    const centre = centreOf(ctx, level);
    const lp = landPack(R, level, P, s, centre);
    const tex = unitNoise(R, P.texture_scales_m, level, s, 1201);
    const rough = ctx.fresh ? unitNoise(R, P.start_scales_m, level, s, 1301) : null;
    const pack = lp.run(tex, rough);
    const u = R.unpack(pack, ['s0', 'U', 'h0', null]);
    if (ctx.role === 'grow' || ctx.fresh) fields.U = u.U; else u.U.destroy();
    if (ctx.fresh) {
        fields.h = u.h0;
        fields.bed = copyOf(R, u.h0);
    } else {
        u.h0.destroy();
    }
    fields.coast_s0 = u.s0;
    for (const f of [lp.wig, tex, rough, pack]) f?.destroy();
    return fields;
}


// ===================================================================================================== cliffs ===

/** [zs, run]: the horizontal run of a rock column's face, run(zs) = integral of dz / tan(angle(z)) from zLo, tabulated
 * every dz metres of stratigraphic height (the beds repeat from baseM up; below it the first bed) (coast.py
 * column_table, in doubles). */
export function columnTable(column, baseM = 0.0, zLo = -60.0, zHi = 600.0, dz = 0.25) {
    const beds = typeof column === 'string' ? COLUMNS[column] : column.map((b) => [Number(b[0]), Number(b[1])]);
    const th = beds.map((b) => Number(b[0])), ang = beds.map((b) => Number(b[1]));
    // th.sum(): numpy's pairwise sum (the chalk's eight beds: 13.9, where a plain loop gives 13.899999999999999 and
    // moves the beds at the cycles' exact boundaries)
    const cyc = 0.0 + pairwiseSum(th);
    const edges = [0.0];
    for (const t of th) edges.push(edges[edges.length - 1] + t);
    const n = Math.trunc(Math.ceil((zHi + dz - zLo) / dz));
    const zs = new Float64Array(n), run = new Float64Array(n), inv = new Float64Array(n);
    for (let i = 0; i < n; i++) {
        zs[i] = zLo + i * dz;
        const rel = npModPos(Math.max(zs[i] - baseM, 0.0), cyc);
        let k = edges.filter((e) => e <= rel).length - 1;                    // searchsorted(side='right') - 1
        k = clip(k, 0, beds.length - 1);
        inv[i] = 1.0 / Math.tan((ang[k] * Math.PI) / 180.0);
    }
    for (let i = 1; i < n; i++) run[i] = run[i - 1] + 0.5 * (inv[i] + inv[i - 1]) * dz;
    return [zs, run];
}

// np.mod for a non-negative dividend
const npModPos = (a, b) => { const m = a % b; return m; };
const clip = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);

/** The original shoreline of a surface as a level set (< 0 at sea): land - seaLevel, where only the sea that reaches
 * the window's edge (or, when none does, the largest body) is sea (coast.py sea_phi). A new field. */
export async function seaPhi(R, land, seaLevel) {
    const { F: phi, U: wet } = ew(R, 0, { a: land }, [Number(seaLevel), 0, 0], 'U');
    const P = prims(R);
    const any = (await P.statsU32(wet)).max > 0;
    if (!any) {
        wet.destroy();
        const out = ew(R, 1, { a: Gd.fill(R, [land.h, land.w], 0.0), b: phi }).F;
        phi.destroy();
        return out;
    }
    const { labels, count } = await P.label(wet);
    wet.destroy();
    const keep = await labelKeep(R, labels, count, land.h, land.w, { edge: true, largestIfNone: true });
    const kept = gatherKeep(R, labels, keep, land.h, land.w);
    const out = ew(R, 1, { a: kept, b: phi }).F;
    for (const f of [labels, kept, phi]) f.destroy();
    return out;
}

// per label: keep the labels touching the edge (edge) or `a` (markA); when none, the largest (largestIfNone). The
// decision is the CPU's on the per-label flags and counts (one number per label): a Uint32Array keep list
async function labelKeep(R, labels, count, h, w, opts = {}) {
    const L = count + 1;
    const flag = R.field(1, L, 1, null, 'u32'), cnt = R.field(1, L, 1, null, 'u32');
    const D = Gd.dummies(R);
    R.run(kernel(R, 'karst/coast_labels'), { lab: labels, a: opts.markA ?? D.f1, keep: D.u1 }, { outK: sinks(R).f1, flag, cnt },
        { uPass: 0, uEdge: opts.edge ? 1 : 0, uMarkA: opts.markA ? 1 : 0, uLargest: 0, uW: w, uH: h }, groups(h, w));
    const [fl, cn] = await R.readAll([flag, cnt]);
    flag.destroy();
    cnt.destroy();
    const keep = new Uint32Array(L);
    let any = false;
    for (let l = 1; l < L; l++) if (fl[l]) { keep[l] = 1; any = true; }
    if (!any && opts.largestIfNone) {
        let best = 0, bi = 0;
        for (let l = 1; l < L; l++) if (cn[l] > best) { best = cn[l]; bi = l; }       // np.argmax: the first largest
        keep[bi] = bi > 0 ? 1 : 0;
    }
    keep.counts = cn;
    return keep;
}

function gatherKeep(R, labels, keep, h, w) {
    const k = R.field(1, keep.length, 1, keep, 'u32');
    const out = R.field(h, w, 1);
    const D = Gd.dummies(R);
    R.run(kernel(R, 'karst/coast_labels'), { lab: labels, a: D.f1, keep: k }, { outK: out, flag: sinks(R).u1, cnt: sinks(R).u1b },
        { uPass: 1, uEdge: 0, uMarkA: 0, uLargest: 0, uW: w, uH: h }, groups(h, w));
    k.destroy();
    return out;
}

/** The shore plan of a level (coast.py plan_shore): { d0 (metres, + inland), E (the exposure of the nearest shore,
 * smoothed along the shore by exposure_smooth_m), info } (d0 and E new fields). */
export async function planShore(R, phi, cell, P, smoothCells = null) {
    const { F: ph, G: sea } = ew(R, 2, { a: phi }, [0, 0, 0], 'G');
    const st = await prims(R).stats(sea);
    const n = phi.h * phi.w;
    if (st.nonzero === 0 || st.nonzero === n) {
        const far = st.nonzero === n ? -1e7 : 1e7;
        for (const f of [ph, sea]) f.destroy();
        return { d0: Gd.fill(R, [phi.h, phi.w], far), E: Gd.fill(R, [phi.h, phi.w], E_REF), info: { shore_cells: 0 } };
    }
    const Es = exposure(R, sea, cell, Number(P.fetch_max_m), Math.trunc(P.fetch_dirs));
    const { F: pay, G: shoreMask } = ew(R, 3, { a: Es }, [0, 0, 0], 'G');
    const cr = nearestCrossing(R, ph, pay, { signed: { neg: sea, cell, far: 0.0 } });
    const u = R.unpack(cr, ['d0', 'E', null, null]);
    const sm = smoothCells === null ? Number(P.exposure_smooth_m) / cell : smoothCells;
    let E = u.E;
    if (sm > 0.5) {
        E = HS.gaussianBlur(u.E, sm);
        u.E.destroy();
    }
    const Pm = prims(R);
    const ns = (await Pm.stats(shoreMask)).nonzero;
    const info = { shore_cells: ns };
    if (ns) {
        const [p10, p50, p90] = await Pm.percentile(Es, [10, 50, 90], { mask: shoreMask, dtype: 'float64' });
        Object.assign(info, { exposure_p10: p10, exposure_p50: p50, exposure_p90: p90 });
    } else {
        Object.assign(info, { exposure_p10: null, exposure_p50: null, exposure_p90: null });
    }
    for (const f of [ph, sea, Es, pay, shoreMask, cr]) f.destroy();
    return { d0: u.d0, E, info };
}

/** The level's scar lattice coordinates: per column and row, (cell, fraction) of X / spacing (doubles). */
function scarAxes(R, level, sp) {
    const n = level.n, a = new Float32Array(4 * n);
    for (let i = 0; i < n; i++) {
        const gx = (level.x0 + (i + 0.5) * level.cell) / sp, gy = (level.y0 + (i + 0.5) * level.cell) / sp;
        const ix = Math.floor(gx), iy = Math.floor(gy);
        a[2 * i] = ix;
        a[2 * i + 1] = gx - ix;
        a[2 * (n + i)] = iy;
        a[2 * (n + i) + 1] = gy - iy;
    }
    return R.field(2, n, 2, a);
}

/** R, phi = d0 - R, the scars' bite and the stacks' weight (coast.py stack_weight, scar_field, retreat_field and
 * op_coast's sum): kernels/karst/coast_retreat.wgsl's (R, phi, bite, stack_w) pack. The noise in Blender's order:
 * the stacks' ridged field, the weakness, the crenellation. */
function retreatPack(R, E, d0, level, P, seed) {
    const D = Gd.dummies(R);
    const sk = Number(P.stacks) > 0 ? field(R, { kind: 'ridged', wavelength_m: Number(P.stack_scale_m), octaves: 2, seed: 1451 }, level, seed) : null;
    const wk = Number(P.weakness) > 0 ? unitNoise(R, P.weakness_scales_m, level, seed, 1401) : null;
    const cr = Number(P.crenel_m) > 0 ? unitNoise(R, P.crenel_scales_m, level, seed, 1501) : null;
    const scars = Number(P.scars) > 0;
    const sp = Number(P.scar_spacing_m);
    const sx = scars ? scarAxes(R, level, sp) : null;
    const out = R.field(level.n, level.n, 4);
    const [rlo, rhi] = P.scar_radius_m.map(Number), [dlo, dhi] = P.scar_depth_m.map(Number);
    const [lo, hi] = P.exposure_clamp.map(Number);
    R.run(kernel(R, 'karst/coast_retreat'), { E, d0, wk: wk ?? D.f1, cr: cr ?? D.f1, sk: sk ?? D.f1, sx: sx ?? D.f2 }, { outR: out },
        { uFlags: (wk ? 1 : 0) | (cr ? 2 : 0) | (sk ? 4 : 0) | (scars ? 8 : 0), uRetreat: Number(P.retreat_m),
            uPower: Number(P.exposure_power), uLo: lo, uHi: hi, uWeak: Number(P.weakness), uStacks: Number(P.stacks),
            uCrenel: Number(P.crenel_m), uScars: Number(P.scars), uSp: sp, uRlo: rlo, uRhi: rhi, uDlo: dlo, uDhi: dhi,
            uSalt: (Math.trunc(seed) * 7919 + 1907) | 0, uSalt2: (Math.trunc(seed) * 7919 + 1913) | 0 });
    for (const f of [sk, wk, cr, sx]) f?.destroy();
    return out;
}

/** Stage 'coast' (coast.py op_coast: the module doc). */
export async function opCoast(fields, level, params, seed = 0, ctx = null) {
    ctx = await FL.asContext(ctx, fields, level);
    if (ctx.prepass !== null && ctx.prepass !== undefined) return fields;   // the coarsest level's coarse-to-fine passes
    const t0 = performance.now();
    const R = ctx.device ?? fields.R;
    ctx.device = R;
    const P = paramsFor(params);
    const s = Math.trunc(seed) + Math.trunc(P.seed);
    const seaLevel = Number(P.sea_level !== null && P.sea_level !== undefined ? P.sea_level :
        (ctx.sea_level !== null && ctx.sea_level !== undefined ? ctx.sea_level : 0.0));
    const lv = level, n = lv.n, cell = Number(lv.cell);
    if (!('h' in fields)) {
        throw new Error(`stage 'coast' on ${lv}: no height yet (the land comes first: 'coast_land' + 'fluvial', a DEM, or any start)`);
    }
    const child = 'coast_d0' in fields;
    const tmp = [];
    const T = (f) => { if (f) tmp.push(f); return f; };
    let info = {}, land, zone, d0, E;
    if (child) {
        if ((ctx.shared.coast_uncut ?? []).includes(Math.trunc(ctx.index))) {
            land = copyOf(R, fields.h);
            zone = T(Gd.fill(R, [n, n], 0.0));
        } else {
            ({ land, w: zone } = childLand(R, fields, lv));
            T(zone);
        }
        d0 = copyOf(R, fields.coast_d0);
        E = copyOf(R, fields.coast_E);
    } else {
        land = copyOf(R, fields.h);
        // the original shoreline: coast_land's, else the surface's sea level line; only the sea that reaches the edge
        const phi0 = T('coast_s0' in fields ? await seaPhi(R, fields.coast_s0, 0.0) : await seaPhi(R, land, seaLevel));
        ({ d0, E, info } = await planShore(R, phi0, cell, P));
    }
    const bedIn = 'bed' in fields ? fields.bed : land;

    // the retreat and the cliff foot line (with the collapse scars' bites)
    const rp = T(retreatPack(R, E, d0, lv, P, s));
    const rpu = R.unpack(rp, ['R', 'phi', 'bite', 'sw']);
    for (const f of Object.values(rpu)) T(f);
    const { U: cutU, G: sea0 } = ew(R, 4, { a: rpu.phi, b: d0 }, [0, 0, 0], 'GU');
    T(sea0);
    let cut;
    if (P.connect) {
        const { labels, count } = await prims(R).label(cutU);
        if (count) {
            const keep = await labelKeep(R, labels, count, n, n, { edge: true, markA: sea0 });
            cut = T(gatherKeep(R, labels, keep, n, n));
        } else {
            cut = T(Gd.fill(R, [n, n], 0.0));
        }
        labels.destroy();
    } else {
        cut = T(u32ToF32(R, cutU));
    }
    cutU.destroy();
    const { F: phi, U: landU } = ew(R, 5, { a: cut, b: rpu.phi }, [0, 0, 0], 'U');
    T(phi);
    T(landU);
    // the face angle belongs to the cliff line (every cell takes the angle at its nearest point of the foot line,
    // carried by the jump flood), clamped below 90 degrees
    const nf = T(unitNoise(R, [P.face_scale_m], lv, s, 1601));
    // stacks: land the cut has detached from the mainland (and a few cells of sea around it) take the knob's wall
    const Pm = prims(R);
    const cutN = (await Pm.stats(cut)).nonzero;
    let sw = null;
    if (Number(P.stacks) > 0 && cutN > 0) {
        const { labels, count } = await Pm.label(landU);
        if (count > 1) {
            const keep = await labelKeep(R, labels, count, n, n, {});
            let best = 0, bi = 0;
            for (let l = 1; l <= count; l++) if (keep.counts[l] > best) { best = keep.counts[l]; bi = l; }
            const det = R.field(n, n, 1);
            const D = Gd.dummies(R);
            R.run(kernel(R, 'karst/coast_labels'), { lab: labels, a: D.f1, keep: D.u1 }, { outK: det, flag: sinks(R).u1, cnt: sinks(R).u1b },
                { uPass: 2, uEdge: 0, uMarkA: 0, uLargest: bi, uW: n, uH: n }, groups(n, n));
            if ((await Pm.stats(det)).nonzero > 0) sw = T(Pm.dilate(det, 3));
            det.destroy();
        }
        labels.destroy();
    }
    let theta = T(ew(R, 10, { a: nf, b: sw }, [Number(P.face_deg), Number(P.face_spread_deg), Number(P.stack_face_deg)], '',
        [nf ? 1 : 0, sw ? 1 : 0], [n, n]).F);
    let sd;
    if (cutN > 0 && cutN < n * n) {
        const cr = T(nearestCrossing(R, phi, theta, { signed: { neg: cut, cell, far: 1e7 } }));
        sd = T(takeChannel4(R, cr, 0));
        theta = T(ew(R, 11, { a: theta, d: cr }).F);
    } else {
        sd = T(ew(R, 12, { a: cut }).F);
    }

    // the face, the platform, the deposits
    const tn = T(unitNoise(R, [180.0, 60.0], lv, s, 1651));
    let colRows = null, axes = null;
    if (P.column !== null && P.column !== undefined) {
        const [zs, run] = columnTable(P.column, Number(P.column_base_m));
        const a = new Float32Array(2 * zs.length);
        for (let i = 0; i < zs.length; i++) { a[2 * i] = zs[i]; a[2 * i + 1] = run[i]; }
        colRows = T(R.field(1, zs.length, 2, a));
        const [dxv, dyv] = seaVector(P.column_dip_azimuth_deg);
        axes = T(axesField(R, lv, 0.0, 0.0, dxv, dyv));
    }
    const nr = T(unitNoise(R, [20.0, 6.0], lv, s, 1701, 2.0));
    const nw = Number(P.shingle_var) > 0 ? T(unitNoise(R, P.shingle_scales_m, lv, s, 1801)) : null;
    const deg = (d) => Math.tan((Number(d) * Math.PI) / 180.0);
    const berm = Number(P.beach_berm_m), back = Number(P.beach_backshore_m), tanFace = deg(P.beach_face_deg);
    const D = Gd.dummies(R);
    const cA = T(R.field(n, n, 4)), cB = T(R.field(n, n, 4));
    R.run(kernel(R, 'karst/coast_cliff'), { land, sd, theta, sw: sw ?? D.f1, nt: tn ?? D.f1, nr: nr ?? D.f1, bite: rpu.bite, E,
        nw: nw ?? D.f1, col: colRows ?? D.f2, axes: axes ?? D.f2 }, { outA: cA, outB: cB },
    { uFlags: (sw ? 1 : 0) | (tn ? 2 : 0) | (nr ? 4 : 0) | (nw ? 8 : 0) | (colRows ? 16 : 0) | (Number(P.scars) > 0 ? 32 : 0),
        uNC: colRows ? colRows.w : 1, uSea: seaLevel, uTalusFrac: Number(P.talus_frac), uTalusMax: Number(P.talus_max_m),
        uPlatTop: Number(P.platform_top_m), uPlatTan: deg(P.platform_slope_deg), uSeaFloor: Number(P.sea_floor_m),
        uRoughM: Number(P.platform_rough_m), uTopRound: Number(P.top_round_m), uTanR: deg(P.talus_deg),
        uScarDebris: Number(P.scar_debris), uTanDebris: deg(P.debris_deg), uDip: deg(P.column_dip_deg), uZlo: -60.0, uDz: 0.25,
        uBe0: Number(P.beach_exposure[0]), uBe1: Number(P.beach_exposure[1]), uShW: Math.max(Number(P.shingle_w_m), 1e-3),
        uShVar: Number(P.shingle_var), uShCrest: Number(P.shingle_m), uShBerm: Number(P.shingle_berm), uBerm: berm, uBack: back,
        uYw: back + berm / tanFace, uTanFace: tanFace, uDeanA: Number(P.dean_A) });

    // band: a child's outer cells blend to its parent's surface; then the writes
    const band = child && ctx.pins && lv.parent !== null && lv.parent !== undefined;
    const bw = band ? T(bandPins(R, lv)) : null;
    const out = { h: R.field(n, n, 1), bed: R.field(n, n, 1), wear: R.field(n, n, 1), talus: R.field(n, n, 1),
        deposit: R.field(n, n, 1), Sc: R.field(n, n, 1), coast_cut: R.field(n, n, 1), zs: R.field(n, n, 1) };
    const has = ('wear' in fields ? 1 : 0) | ('talus' in fields ? 2 : 0) | ('deposit' in fields ? 4 : 0) | ('Sc' in fields ? 8 : 0);
    R.run(kernel(R, 'karst/coast_write'), { A: cA, B: cB, land, bedIn, zone: zone ?? D.f1, bw: bw ?? D.f1,
        pinH: band ? ctx.pins.pin_h : D.f1, wearIn: fields.wear ?? D.f1, talusIn: fields.talus ?? D.f1,
        depIn: fields.deposit ?? D.f1, scIn: fields.Sc ?? D.f1 },
    { outH: out.h, outBed: out.bed, outWear: out.wear, outTalus: out.talus, outDep: out.deposit, outSc: out.Sc,
        outCut: out.coast_cut, outZs: out.zs },
    { uChild: child ? 1 : 0, uBand: band ? 1 : 0, uHas: has });
    for (const k of ['h', 'bed', 'wear', 'talus', 'deposit', 'Sc']) fields[k] = out[k];
    fields.coast_d0 = d0;
    fields.coast_E = E;
    fields.coast_land = land;
    fields.coast_cut = out.coast_cut;
    if (P.column !== null && P.column !== undefined) fields.zs = out.zs; else out.zs.destroy();

    // the record (coast.py's rec, ctx.shared.coast_log and the log line)
    const cutFrac = cutN / (n * n);
    const near = T(nearMask(R, phi, 3 * cell + 50));
    const nn = (await Pm.stats(near)).nonzero;
    const pct = nn ? (await Pm.percentile(rpu.R, [10, 50, 90], { mask: near, dtype: 'float64' })).map((v) => pyRoundN(v, 1)) : null;
    for (const f of tmp) if (!f.destroyed && !Object.values(fields).includes(f)) f.destroy();
    const rec = { level: String(lv), plan: !child, cut_frac: pyRoundN(cutFrac, 4), retreat_p10_p50_p90: pct,
        seconds: pyRoundN((performance.now() - t0) / 1000, 3), ...info };
    (ctx.shared.coast_log ??= []).push(rec);
    const f2 = (v) => (v === null || v === undefined ? 0 : v).toFixed(2);
    ctx.log(`[terrain.coast] ${lv.n}^2 @ ${pyFormat(cell, '.3g')} m: ${child ? '' : 'shore plan + '}cut ${(100 * rec.cut_frac).toFixed(1)}%` +
        (pct ? `, retreat p10/50/90 ${JSON.stringify(pct)} m` : '') +
        (info.exposure_p50 !== null && info.exposure_p50 !== undefined ? `, exposure p10/50/90 ${f2(info.exposure_p10)}/${f2(info.exposure_p50)}/${f2(info.exposure_p90)}` : '') +
        `, ${rec.seconds} s`);
    return fields;
}

// |phi| < k as a float mask (the record's percentile cells)
function nearMask(R, phi, k) {
    const out = R.field(phi.h, phi.w, 1);
    R.run(kernel(R, 'karst/coast_pick'), { src: phi }, { outF: out }, { uChannel: -1, uK: k });
    return out;
}

function u32ToF32(R, u) {
    const out = R.field(u.h, u.w, 1);
    const D = Gd.dummies(R);
    R.run(kernel(R, 'karst/coast_labels'), { lab: u, a: D.f1, keep: D.u1 }, { outK: out, flag: sinks(R).u1, cnt: sinks(R).u1b },
        { uPass: 2, uEdge: 0, uMarkA: 0, uLargest: -1, uW: u.w, uH: u.h }, groups(u.h, u.w));
    return out;
}

// one channel of a 4-channel field as an r32f field
function takeChannel4(R, f4, c) {
    const names = [null, null, null, null];
    names[c] = 'x';
    return R.unpack(f4, names).x;
}

const pyRoundN = (x, nd) => Number(pyFormat(Number(x), `.${nd}f`));

opCoastLand.evolves = true;             // run.js: U on every coarse-to-fine pass of the coarsest level
opCoast.evolves = true;                 // run.js runs it on the coarsest level's last pass too (it skips the pre-passes)

export const OPS = { coast_land: opCoastLand, coast: opCoast };
export {
    fetchKernel as fetch_kernel, jfaSteps as jfa_steps, nearestCrossing as nearest_crossing, paramsFor as params_for,
    unitNoise as _unit_noise, seaPhi as sea_phi, planShore as plan_shore, columnTable as column_table,
    refineLand as refine_land, opCoastLand as op_coast_land, opCoast as op_coast, childLand as _child_land,
};
