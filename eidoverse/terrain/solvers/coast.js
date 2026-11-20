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
import { KeyError, closeMatches, pyRound } from '../core/levels.js';

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

export const OPS = {};
export { fetchKernel as fetch_kernel, jfaSteps as jfa_steps, nearestCrossing as nearest_crossing, paramsFor as params_for };
