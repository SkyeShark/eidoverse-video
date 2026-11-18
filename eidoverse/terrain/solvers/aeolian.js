// Port of blender/eidoblend/terrain/solvers/aeolian.py at f90c6fc.
//
// Wind and sand: dunes from Werner's slab model on the GPU (design section 4.6).
//
// The model (Werner 1995, with the numbers of Paris et al. 2019's Desertscapes code), on two layers: `bed` (rock, which
// the wind does not touch here) and `sand` (thickness, metres); the surface is h = bed + sand. One iteration:
//
//   1. shadow     every cell's wind shadow: the steepest angle up to the ground upwind of it within `shadow_reach`
//                 cells, ramped from 0 at shadow_lo_deg to 1 at shadow_deg (Werner's 15-degree line); and its `rise`
//                 for the speed-up (the sand's thickness)                             kernels/dune_shadow.wgsl
//   2. activate   a random share of the cells with sand (a PCG hash of cell, iteration and seed) lift one slab, none in
//                 a shadow: p_lift x (1 + lift_boost x f), f growing with the sand's thickness from speed_from_m to
//                 speed_ref_m (the wind speeds up over a dune toward its crest, Momiji et al. 2000; without it Werner's
//                 dunes stand steep on both sides); each picks an integer hop vector by stochastic rounding of the
//                 real one (any wind direction on average, no grid-locked crests) and follows it for up to `max_hops`
//                 hops, depositing with probability shadow + (1 - shadow) x (p_sand on sand, p_rock on bare rock),
//                 always at the last                                                  kernels/dune_activate.wgsl
//   3. transport  the same move as a GATHER: a cell adds every slab whose recorded path ends on it (no atomics, so
//                 deterministic and exactly mass-conserving)                          kernels/dune_transport.wgsl
//   4. avalanche  sand steeper than the angle of repose (tan 0.60, 31 degrees, the Desertscapes value) slides to the
//                 lower neighbour, a symmetric pair exchange over 16 neighbours (the 8 and the knight's moves, so slip
//                 faces stand at one angle whichever way they face) limited by the upper cell's own sand, so bare rock
//                 never moves and mass is conserved; `aval_passes` per iteration      kernels/dune_avalanche.wgsl
// The slab noise (single slabs arriving and leaving: a cell-scale speckle the shadow rule bounds at about 0.15 cells; a
// creep strong enough to clear it during the run flattens the dunes too) is cleared at the end of a run by reading the
// sand time-averaged over the run's last `average_iters` iterations (SandSim.runAveraged: the speckle decorrelates in
// tens of iterations while a dune moves a fraction of a cell in hundreds, so crests and brinks stay as sharp as the
// cells draw them), then a Gaussian of `smooth_cells` (alone, without the average, it rounds a crest by a cell).
//
// The avalanche is a fourth kernel (Blender keeps it as source text in its module, AVALANCHE_SRC; here it is
// kernels/dune_avalanche.wgsl, of the same name): the design names "the threshold kernel" (package 3's threshold.glsl),
// but that limit is the pair's mean Sc, which would hold sand against bare rock at the mean of 31 and 68 degrees; on
// the sand layer the limit is the upper cell's material and only its sand can move. Rock never moves in this solver
// (no abrasion), so the design's rock limit (tan 2.5) has nothing to act on.
//
// Frames and units (design 2.1): arrays [row j, column i], row 0 the south edge, x east and y north; metres, degrees;
// winds are compass degrees the wind blows FROM (meteorological: 225 is a south-westerly, the sand moves north-east).
// Numerical lengths of the slab model are in cells (the hop, the shadow reach) or fractions of a cell (the slab), so
// every level runs the same model at its own scale: a coarse level grows the big dunes, a fine level sharpens their
// crests and grows the small dunes on their flanks.
//
// The wind regime is a list of [from_deg, weight], cycled in blocks of `block` iterations per wind (a wind's block is
// weighted by its share, its direction jittered by up to `jitter_deg`), each run ending on a whole cycle. With `gust`
// and `spread_deg` a block blows as gusts of `gust` iterations, each from its wind's direction plus a normal scatter of
// spread_deg: a season's wind wanders, and one direction held for a whole block builds planar slip faces meeting in
// straight arms at the regime's fixed angles, where a wandering one curves the faces and the crests. Which dunes
// form is the regime and the sand supply, not a shape parameter (Rubin & Hunter 1987, Courrech du Pont et al. 2014,
// Zhang et al. 2012): one wind and thin sand make barchans; one wind and a sand sheet transverse ridges; two winds more
// than 90 degrees apart linear dunes; three or more of similar weight star dunes. KINDS holds each with its sand,
// spacing, bed and its calibration of the model (barchans and linear dunes run Werner's original rule without the
// speed-up, which would spread their thin sheets; star dunes blow each wind 1000 iterations at a time and grow 90 cells
// across, calibrated on the Namib).
//
// A dune field over a level stack (op 'dune_field', design 4.6 "Scale"): Werner dunes need dozens of cells across a
// dune, and the time to grow them goes as 1 / cell^2, so the field is grown ONCE, periodic, on the coarsest level that
// resolves the target spacing with `cells_per_spacing` cells (the growth level; the recipe's prepare hook records the
// level stack so every level's op finds it). Its start is world-space noise: a gently rolling bed, the sand supply
// (thinner and thicker sheets, `supply_var`; drawn out along `supply_axis_deg` by `supply_stretch_m` so the bare floor
// where it runs out is a long pan, and capped at `supply_cap` x the mean), and a seed at `seed_scale` x the target
// spacing (`seed_frac` of the target height), all periodic over the growth window. It runs `grow_iters` iterations (the
// model is scale-free in cells, so one count is one maturity; `grow_phases` can run model changes in turn). Coarser
// levels average the periodic field over their cells (a context window larger than the growth window repeats it);
// finer levels start from their parent (the level runner's inherit) and run `refine_iters` more iterations at their
// own cell with their border band pinned to the parent, which sharpens the crests and slip faces and grows small dunes
// on the big ones: under the whole regime (`refine_winds` 'cycle') or its last season only ('last': the big dunes keep
// the forms the whole regime built, and the finer cells show the latest season's fresh slip faces and brinks on them).
//
//     import * as A from './solvers/aeolian.js';
//     const sim = new A.SandSim(bed, sand, 5.0, { bound: A.BOUND_PERIODIC, params: { hop_cells: 3 }, seed: 1 });
//     await sim.run(A.KINDS.transverse.winds, 4000);       // bed, sand: r32f GPU fields (core/gpu.js), row 0 south
//     const { bed: b, sand: s } = sim.fields();            // the state as new GPU fields; await sim.read(): host arrays
//
// The convergence loop (PORT_PLAN.md 5.7: each solver's port names the loops that stop on a test): grow_tile's growth
// run checks the dunes every `grow_check` iterations and, from grow_min_iters on, stops once they stand at the target
// height with slip faces, at the end of the current whole cycle of the regime. Its iteration count may therefore
// differ by whole cycles (cycleBlocks' sum: 2,999 iterations for the star regime); with every kind's defaults
// grow_min_iters equals grow_iters, so the stop falls on the schedule's own end and the count cannot move.
//
// Where this differs from aeolian.py, and why (PORT_PLAN.md 2.3, 2.4, 3.2: every per-cell step is a GPU kernel; plans
// over objects and the small schedules stay JavaScript, in doubles as numpy computes them):
//   - Fields are core/gpu.js GPU fields, never host arrays: SandSim takes bed and sand as r32f fields, fields() gives
//     the state as fields and read() (a readback) the host arrays the Blender read() returns, for tests. The numpy
//     whole-array steps run as kernels written in this file (the port's own: the dispatch log marks them
//     blender_kernel false, plan 5.2), as Blender writes some of its own inline; this file is in the field hash
//     (core/cache.js, C8), so an edit to them invalidates cached terrains.
//   - Arithmetic numpy does in float64 and rounds once to float32 (start_fields, the steering's turn, denoise,
//     smooth_sheet, sample_periodic, stretch_periodic) is float32 here, in numpy's order of operations, with the
//     float64 constants (the products of parameters) rounded once to float32 uniforms.
//   - run_averaged's sum of the sand samples (float64 in numpy, read back every `average_every` iterations) stays on
//     the GPU, as the first sample plus the sum of each later one's difference from it, in float32: the slab noise
//     moves a cell by a few metres, so the float32 sum carries those metres, not the dunes' tens. No readback.
//   - stretch_periodic's Gaussian along one compass direction (np.fft.rfft2, the gain, np.fft.irfft2) is the same
//     filter through core/prims.js's full complex FFT: the gain on numpy's frequencies (rfftfreq along x, fftfreq along
//     y), completed to the Hermitian spectrum irfft2 implies (the Nyquist column's gain symmetrised over +-ky, the
//     mirrored half's Nyquist row taken at +0.5 / cell, as irfft2 reads them), inverted as conj(fft2(conj(Y))) / N.
//     Its mean and standard deviations are float32 tree sums (core/prims.js stats).
//   - The steering's cos and sin are the GPU's float32 built-ins of the float32 angle (numpy: float64, rounded once);
//     its least and most turn are the exact min and max of that float32 angle (hop_box adds 1e-3 cells either way).
//   - The growth check reads no field back: the dunes' height, spacing and slip faces are measured on the GPU
//     (core/prims.js percentiles, numpy 2.3.4's float64 rule; core/metrics.js radial_spectrum; core/grid.js
//     slope_deg), and only their numbers come back.
//   - The per-process memo of grown tiles (_TILES) holds GPU fields per runner; an op hands a level its own copies.
//     clearTiles() empties it (the chaos floor's protocol clears every solver memo between samples, plan 5.4).
//   - The numpy twins (twin_shadow, twin_activate, twin_transport, twin_avalanche), TwinSim and scatter_step are the
//     oracles and stay in Python (PORT_PLAN.md 0, item 4): tests/wind_sand/ reads their fixtures.
//   - Ops and the sim's run loops are async (their checks and the steering's turn range wait for the GPU); run.js
//     awaits an op.

import { createHash } from 'node:crypto';
import * as Ch from '../core/cache.js';
import * as Gd from '../core/grid.js';
import * as M from '../core/metrics.js';
import * as N from '../core/world_noise.js';
import { KeyError, ValueError, closeMatches, pyFormat, pyInt, pyRepr, pyReprValue, pyRound, pyStr } from '../core/levels.js';
import { defaultRng } from '../core/np_random.js';
import { prims } from '../core/prims.js';

// common.wgsl's boundary modes (core/twins.py BOUND_OPEN / PERIODIC / PINNED in Blender)
export const BOUND_OPEN = 0;
export const BOUND_PERIODIC = 1;
export const BOUND_PINNED = 2;

const DEG = Math.PI / 180.0;                            // math.radians' factor: x * (pi / 180)
const radians = (d) => Number(d) * DEG;
const now = () => performance.now() / 1000;
const round2 = (x) => Number(pyFormat(x, '.2f'));


// --------------------------------------------------------------------------------------------- Python's ways ---

/** Python's float % (the result takes the divisor's sign; fmod, then one step): x % y for doubles. */
export function pyMod(x, y) {
    let m = x % y;
    if (m) {
        if ((y < 0) !== (m < 0)) m += y;
    } else {
        m = y < 0 ? -0.0 : 0.0;
    }
    return m;
}

/** Python's truthiness of a parameter value: None, False, 0, '', [] and {} are false (NaN is true). */
export function truthy(v) {
    if (v === null || v === undefined || v === false || v === '') return false;
    if (typeof v === 'number') return v !== 0;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === 'object') return Object.keys(v).length > 0;
    return true;
}

const or = (v, d) => (truthy(v) ? v : d);              // Python's `v or d`
const roundKey = (x) => Number(pyFormat(x, '.6f'));     // round(x, 6), correctly rounded as CPython's

/** np.linspace(lo, hi, num) in doubles: i * step + lo, the last point hi itself. */
function linspace(lo, hi, num) {
    const div = num - 1, delta = hi - lo, step = delta / div;
    const out = [];
    for (let i = 0; i < num; i++) out.push(step === 0 ? (i / div) * delta + lo : i * step + lo);
    if (num > 1) out[num - 1] = hi;
    return out;
}

/** numpy's pairwise sum of a float64 list (np.add.reduce): sequential under 8, eight accumulators to 128. */
function pairwiseSum(a, i0 = 0, n = a.length) {
    if (n < 8) {
        let s = 0.0;
        for (let i = 0; i < n; i++) s += a[i0 + i];
        return s;
    }
    if (n <= 128) {
        const r = a.slice(i0, i0 + 8);
        let i = 8;
        for (; i < n - (n % 8); i += 8) for (let j = 0; j < 8; j++) r[j] += a[i0 + i + j];
        let s = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for (; i < n; i++) s += a[i0 + i];
        return s;
    }
    let n2 = Math.floor(n / 2);
    n2 -= n2 % 8;
    return pairwiseSum(a, i0, n2) + pairwiseSum(a, i0 + n2, n - n2);
}

/** np.convolve(x, v, mode='same') of short float64 lists. */
function convolveSame(x, v) {
    let a = x, b = v;
    if (b.length > a.length) [a, b] = [b, a];
    const n = a.length, m = b.length;
    const full = new Array(n + m - 1).fill(0.0);
    for (let k = 0; k < n + m - 1; k++) {
        let s = 0.0;
        for (let j = 0; j < m; j++) if (k - j >= 0 && k - j < n) s += a[k - j] * b[j];
        full[k] = s;
    }
    const start = Math.floor((m - 1) / 2);
    return full.slice(start, start + n);
}

const shapeText = (s) => `(${s.join(', ')})`;


// ------------------------------------------------------------------------------------------------ parameters ---

export const DEFAULTS = Object.freeze({
    slab_cells: 0.1,         // slab thickness as a fraction of the cell: one slab step is a 5.7-degree slope
    hop_cells: 3.0,          // saltation hop, cells (the smallest dunes are some ten hops long)
    lift_boost: 15.0,        // the wind's speed-up over a dune: lifting grows to p_lift x (1 + lift_boost) between
                             // speed_from_m and speed_ref_m of sand, so the flux grows all the way up the stoss and
                             // the stoss stays gentle (Momiji et al. 2000); 0: Werner's original, steep both sides
    rise: 'sand',            // what the speed-up grows with: 'sand' (the sand's thickness, Momiji's height) or
                             // 'upwind' (height above the lowest ground within the shadow's reach; saturates there)
    speed_from_m: 5.0,       // 'sand': the speed-up starts at this thickness (a thinner sheet is not a dune) ...
    speed_ref_m: 40.0,       // ... and is full at this one (a dune field derives both from its target height)
    speed_ref_deg: 10.0,     // 'upwind': the full rise is a stoss of this angle over the shadow's reach
    speed_pow: 1,            // the speed-up grows as f^speed_pow (an integer): 2 or 3 make it grow faster toward the
                             // crest, so a dune's top outruns its base and its flanks stretch into broad aprons
    long_factor: 1.0,        // the speed-up as a longer hop as well: the long hop, a multiple of the short (1: off;
                             // long hops overshoot a small dune's shadow, so barchans and linear ridges dissolve)
    speedup: 0.0,            // the long hop's chance at full speed-up
    max_hops: 3,             // hops before a slab must deposit (design 4.6)
    p_lift: 0.02,            // chance a sand cell lifts a slab per iteration where the wind has no speed-up (on a
                             // dune's upper stoss it rises to p_lift x (1 + lift_boost): the design's 5-10 % and more)
    p_sand: 0.6,             // deposition chance on sand (Desertscapes)
    p_rock: 0.4,             // deposition chance on bare rock (Desertscapes)
    min_sand_slabs: 0.25,    // sand thinner than this many slabs is bare rock
    shadow_deg: 15.0,        // Werner's shadow line
    shadow_lo_deg: 10.0,     // where the shadow ramp starts (equal to shadow_deg: Werner's step)
    shadow_reach: 20,        // cells upwind the shadow looks (design: 20)
    repose_deg: 31.0,        // sand's angle of repose: tan 0.60 (Desertscapes)
    aval_rate: 0.06,         // pair exchange per avalanche pass: a share of the excess height over the pair's length
                             // in cells (16 neighbours: their rates sum to about 0.6, below the overshoot of a spike)
    creep: 0.0,              // linear creep per avalanche pass, a share of each height difference (isotropic
                             // weights). Off: any rate that clears the slab noise also flattens the dunes
    aval_passes: 4,          // avalanche passes per iteration
    smooth_cells: 1.0,       // after a run, the slab noise (a cell-scale speckle the shadow rule bounds at ~0.15
                             // cells) is cleared by a Gaussian of this many cells on the sand (0: none)
    block: 200,              // iterations per wind block (design 4.6)
    jitter_deg: 8.0,         // each block's direction varies by up to this much (real winds wander; it also keeps
                             // crests from locking to a lattice direction)
    gust: 0,                 // > 0: a block blows as gusts of this many iterations ...
    spread_deg: 0.0,         // ... each from the block's direction plus a normal scatter of this many degrees
    steer_deg: 0.0,          // the regional relief steers each wind (Steering): the local turn's standard deviation,
                             // degrees, a different pattern per wind direction (a wind and its reverse alike) ...
    steer_turn_deg: 0.0,     // ... plus one turn every wind shares (the whole regime turns across the field), degrees
});

// The dune kinds (design 4.6's table): the wind regime as [from_deg, weight], and the sand and spacing they want.
// The regimes are absolute compass directions; a recipe rotates them with wind_rotate_deg.
export const KINDS = Object.freeze({
    star: {
        winds: [[28.0, 1.0], [148.0, 0.75], [268.0, 0.55]], sand_m: 45.0, spacing_m: 1400.0, bed_m: 20.0,
        model: { cells_per_spacing: 60.0, lift_boost: 25.0, p_lift: 0.02, speed_from_frac: 0.06,
            speed_ref_frac: 1.0, speed_pow: 2, aval_passes: 14, grow_iters: 24000, grow_min_iters: 24000,
            grow_check: 6000, block: 1000, seed_scale: 1.5, gust: 100, spread_deg: 30.0,
            steer_deg: 35.0, steer_wavelength_m: 2000.0, supply_var: 0.6, supply_wavelength_m: 4000.0,
            supply_stretch_m: 1500.0, supply_axis_deg: 90.0, supply_cap: 1.3, average_iters: 400,
            smooth_cells: 0.5, sheet_smooth_cells: 2.0, refine_winds: 'last', refine_iters: 400,
            refine_block: 400, refine_average_iters: 200, hero_winds: 'last2', hero_iters: 1200,
            hero_block: 150, hero_average_iters: 100 },
        doc: 'three winds 120 degrees apart of unequal weight: star dunes with curving arms in masses of ' +
            'sand, long bare pans between the masses (calibrated on the Namib at Sossusvlei: spacing 1.4 km, ' +
            '45 m of sand on a gently rolling plain; the winds off the grid axes, as real winds are). The ' +
            'arms: each wind is a season of 1000 iterations blowing as gusts of 100 that wander 30 degrees ' +
            'about its direction, and the regional relief steers every wind by a smooth turn (35 degrees ' +
            'standard deviation over 2 km) that differs from wind to wind (Steering), so each dune sees its ' +
            'own regime and its arms curve and meet at varying angles (one direction held for a season ' +
            'everywhere built planar faces meeting in three straight arms at a fixed 120 degrees: the 11-12 ' +
            'review; the slopes\' 3-fold aspect harmonic falls from 0.3-0.6 to the Namib\'s 0.06-0.08). The ' +
            'flanks: the speed-up grows as the square of its ramp (speed_pow 2) between 21 m of sand and the ' +
            'target height, at 0.02 x (1 + 25 f^2) a slab an iteration, so a dune\'s top outruns its base and ' +
            'its flanks stretch into broad aprons under a sharp crest zone, the Namib\'s 5-20 degree ground ' +
            '(a linear speed-up only carries each face along at its angle: pyramids at repose, every dune ' +
            '400 m tall). The pans: the supply varies 60 % over 4 km, drawn out east-west by 1.5 km ' +
            '(stretch_periodic) and capped at 1.3 x the mean, so where the sand runs out the floor is a long ' +
            'smooth pan, as Sossusvlei\'s are, and no mass grows a dune above the Namib\'s; the thin sand is ' +
            'smoothed and its margins thin out onto the floor (smooth_sheet: kept as it stood, it was a ' +
            'speckled table with a step at its edge, the review\'s straight-edged plates and pitted sand). ' +
            '14 avalanche passes an iteration hold the slip faces at 31-33 degrees (8 left them at 34-37). ' +
            'The sand is read time-averaged over each run\'s last iterations (the slab speckle goes, crests ' +
            'stay sharp). The main level blows the last season only, 400 iterations: every crest a sharp brink ' +
            'above a fresh slip face (longer, every face turns to that one wind). The hero levels around a ' +
            'camera blow the last two seasons in turns of 150 iterations (refine_winds \'last2\'), which ' +
            'reverses the crest zone: arms steep on both sides, knife-edges above the broad flanks, ribs and ' +
            'small dunes on the flanks (one season left a brink over a gentle stoss, a rounded shoulder at ' +
            '1.7 m; a whole cycle re-planes each big dune into a pyramid of straight-edged facets). The dunes ' +
            'grow 90 cells across',
    },
    barchan: {
        winds: [[225.0, 1.0]], sand_m: 2.5, spacing_m: 250.0, bed_m: 1.5,
        model: { lift_boost: 0.0, p_lift: 0.075 },
        doc: 'one wind, thin sand on a bare plain: crescents with horns downwind. The thin sheet must ' +
            'gather into dunes before any speed-up, so barchans run Werner\'s original rule',
    },
    transverse: {
        winds: [[225.0, 1.0]], sand_m: 5.0, spacing_m: 120.0, bed_m: 1.5,
        model: { speed_from_frac: 0.0, speed_ref_frac: 4.0 },
        doc: 'one wind, a continuous sand sheet: ridges across the wind, slip faces downwind (White ' +
            'Sands: 5 m of sand on a flat plain)',
    },
    linear: {
        winds: [[120.0, 1.0], [240.0, 1.0]], sand_m: 45.0, spacing_m: 2000.0,
        model: { lift_boost: 0.0, p_lift: 0.075 },
        doc: 'two winds 120 degrees apart: long ridges along their resultant, slip faces flipping side ' +
            'to side (the Namib south of Gobabeb); symmetric in section, so Werner\'s original rule',
    },
});
// Each kind's `model` is its calibration of the slab model (DEFAULTS and FIELD_DEFAULTS keys), applied unless the
// caller gives the key. The speed-up's proxy (sand thickness) cannot tell a sheet that is gathering into dunes from a
// dune: under it a thin sheet spreads instead of heaping into barchans, and two crossing winds leave a sheet with a
// few dunes on it instead of ridges, so barchans and linear dunes run Werner's original rule (linear dunes are
// symmetric in section anyway: their slip faces flip side to side); transverse ridges start the speed-up at the toe.

export const LOG_PREFIX = '[terrain.aeolian]';

/** DEFAULTS with `params` over them (unknown keys are kept for the dune field's own use). */
export function paramsFor(params = null) {
    return { ...DEFAULTS, ...(params ?? {}) };
}


// ---------------------------------------------------------------------------------------------- the wind ---

/** The unit [x east, y north] direction sand moves in a wind blowing FROM compass `fromDeg`. */
export function transportDir(fromDeg) {
    const a = radians(fromDeg);
    return [-Math.sin(a), -Math.cos(a)];
}

/** [[from_deg, weight], ...] with positive weights, from pairs, objects { from_deg, weight } or bare angles. */
export function normaliseWinds(winds) {
    const out = [];
    for (const w of winds) {
        let d, wt;
        if (w !== null && typeof w === 'object' && !Array.isArray(w)) {
            if (!('from_deg' in w)) throw new KeyError("'from_deg'");
            d = Number(w.from_deg);
            wt = 'weight' in w ? Number(w.weight) : 1.0;
        } else if (typeof w === 'number') {
            d = w;
            wt = 1.0;
        } else {
            d = Number(w[0]);
            wt = w.length > 1 ? Number(w[1]) : 1.0;
        }
        if (wt < 0) throw new ValueError(`wind weight ${pyRepr(wt)} is negative`);
        if (wt > 0) out.push([pyMod(d, 360.0), wt]);
    }
    if (!out.length) throw new ValueError('a wind regime needs at least one wind with a positive weight');
    return out;
}

/** One cycle of the regime: [[from_deg, iterations], ...], each wind's block its weighted share of
 * block x (number of winds) iterations, at least 1. */
export function cycleBlocks(winds, block) {
    winds = normaliseWinds(winds);
    let tot = 0;
    for (const [, w] of winds) tot += w;
    const n = winds.length;
    return winds.map(([d, w]) => [d, Math.max(1, pyRound(block * n * w / tot))]);
}

/** [[from_deg, iterations], ...] covering at least `iterations`, in whole cycles of the regime. Each block's
 * direction varies by up to jitterDeg (deterministic per seed: numpy's default_rng((seed * 7919 + 17) & 0xFFFFFFFF),
 * core/np_random.js). With gust > 0 and spreadDeg > 0 a block blows as gusts of `gust` iterations, each from the
 * block's direction plus a normal scatter of spreadDeg (a real wind wanders continuously around its season's
 * direction: one direction held for a whole block builds planar slip faces meeting in straight arms; a wandering one
 * curves the faces and the crests). withWind: triples [from_deg, iterations, the regime's own direction for that
 * wind], the direction the steering is keyed on. */
export function schedule(winds, iterations, block, jitterDeg = 0.0, seed = 0, gust = 0, spreadDeg = 0.0, withWind = false) {
    const blocks = cycleBlocks(winds, block);
    let per = 0;
    for (const [, b] of blocks) per += b;
    const cycles = Math.max(1, Math.ceil(pyInt(iterations) / per));
    const rng = defaultRng((BigInt(pyInt(seed)) * 7919n + 17n) & 0xFFFFFFFFn);
    const out = [];
    for (let c = 0; c < cycles; c++) {
        for (const [d, b] of blocks) {
            const j = truthy(jitterDeg) ? rng.uniform(-1.0, 1.0) * Number(jitterDeg) : 0.0;
            if (truthy(gust) && truthy(spreadDeg) && pyInt(gust) < b) {
                let left = b;
                while (left > 0) {
                    const g = Math.min(pyInt(gust), left);
                    out.push([pyMod(d + j + rng.normal(0.0, Number(spreadDeg)), 360.0), g, d]);
                    left -= g;
                }
            } else {
                out.push([pyMod(d + j, 360.0), b, d]);
            }
        }
    }
    return withWind ? out : out.map(([d, b]) => [d, b]);
}

export function scheduleLength(sched) {
    let n = 0;
    for (const s of sched) n += s[1];
    return n;
}

/** The integer hop vectors any source can pick (dune_activate's stochastic rounding of its hop, turned by its
 * cell's local angle): [[vx_min, vy_min], [vx_max, vy_max]], the box dune_transport gathers over. hop: the short hop
 * (cells, float32 as the kernels see it); longF: the long hop's multiple (> 1: long hops too); turn: the least and
 * the most the steering turns this wind anywhere on the grid, radians. */
export function hopBox(hop, longF = 1.0, turn = [0.0, 0.0]) {
    const hx = Math.fround(hop[0]), hy = Math.fround(hop[1]);
    const r0 = Math.hypot(hx, hy), phi = Math.atan2(hy, hx);
    const lo = Number(turn[0]), hi = Number(turn[1]);
    const ang = hi <= lo ? [0.0] : [...linspace(lo, hi, 129), lo, hi];
    for (const ax of [0.0, 0.5 * Math.PI, Math.PI, 1.5 * Math.PI, 2.0 * Math.PI, -0.5 * Math.PI, -Math.PI]) {
        const a = ax - phi;                            // an axis crossing inside the range sets that component's extreme
        if (lo < a && a < hi) ang.push(a);
    }
    const lens = [1.0, ...(Number(longF) > 1.0 ? [Number(longF)] : [])];
    let xs = [], ys = [];
    for (const m of lens) for (const a of ang) xs.push(r0 * m * Math.cos(phi + a));
    for (const m of lens) for (const a of ang) ys.push(r0 * m * Math.sin(phi + a));
    if (hi <= lo) {                                    // no steering: exactly the kernels' own float32 hops
        xs = [hx, ...(longF > 1.0 ? [Math.fround(Math.fround(hx) * Math.fround(longF))] : [])];
        ys = [hy, ...(longF > 1.0 ? [Math.fround(Math.fround(hy) * Math.fround(longF))] : [])];
    }
    const eps = 1.0e-3;                                // float32 rounding of the turned hop in the kernel
    let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
    for (const x of xs) { xmin = Math.min(xmin, x); xmax = Math.max(xmax, x); }
    for (const y of ys) { ymin = Math.min(ymin, y); ymax = Math.max(ymax, y); }
    return [[Math.floor(xmin - eps), Math.floor(ymin - eps)], [Math.floor(xmax + eps) + 1, Math.floor(ymax + eps) + 1]];
}


// ------------------------------------------------------------------------------------------ the kernels ---
// The numpy whole-array steps of aeolian.py, as kernels (the port's own; PORT_PLAN.md 2.4, 3.2). Each names the
// numpy code it replaces; float32 in numpy's order of operations, float64 products of parameters as uniforms.

const K_START = `
// aeolian.py start_fields: bed = (bed_m 3) n_bed; sand = max(sand_m min(max(0, 1 + (supply_var 3) n_supply), cap)
// + (seed_m 3) n_seed, 0) (numpy: float64, rounded once to float32)
//! sampler bedN r32f
//! sampler supN r32f
//! sampler seedN r32f
//! image   outBed r32f
//! image   outSand r32f
//! uniform float uBed3
//! uniform float uVar3
//! uniform int uCapOn
//! uniform float uCap
//! uniform float uSandM
//! uniform int uSeedOn
//! uniform float uSeed3

fn kmain(p: vec2<i32>) {
  if (!inside(p, outBed_size())) { return; }
  outBed_store(p, vec4<f32>(u.uBed3 * bedN_at(p).x, 0.0, 0.0, 0.0));
  var supply = max(0.0, 1.0 + u.uVar3 * supN_at(p).x);
  if (u.uCapOn == 1) { supply = min(supply, u.uCap); }
  var sand = u.uSandM * supply;
  if (u.uSeedOn == 1) { sand = sand + u.uSeed3 * seedN_at(p).x; }
  outSand_store(p, vec4<f32>(max(sand, 0.0), 0.0, 0.0, 0.0));
}
`;

const K_STEER_N = `
// aeolian.py steering_for: n_k = clip(3 fbm_k, -2, 2), the three steering fields packed (n1, n2, n3, 0)
//! sampler f0 r32f
//! sampler f1 r32f
//! sampler f2 r32f
//! image   outN rgba32f

fn kmain(p: vec2<i32>) {
  if (!inside(p, outN_size())) { return; }
  outN_store(p, vec4<f32>(clamp(3.0 * f0_at(p).x, -2.0, 2.0), clamp(3.0 * f1_at(p).x, -2.0, 2.0),
                          clamp(3.0 * f2_at(p).x, -2.0, 2.0), 0.0));
}
`;

const K_STEER_WIND = `
// aeolian.py Steering.angle and for_wind: delta = steer (n1 cos 2 theta + n2 sin 2 theta) + turn n3, radians, and the
// kernels' wind input (cos delta, sin delta)
//! sampler nf rgba32f
//! image   outCs rg32f
//! image   outD r32f
//! uniform float uSteer
//! uniform float uTurn
//! uniform float uCos2
//! uniform float uSin2

fn kmain(p: vec2<i32>) {
  if (!inside(p, outCs_size())) { return; }
  let v = nf_at(p);
  let d = u.uSteer * (v.x * u.uCos2 + v.y * u.uSin2) + u.uTurn * v.z;
  outCs_store(p, vec4<f32>(cos(d), sin(d), 0.0, 0.0));
  outD_store(p, vec4<f32>(d, 0.0, 0.0, 0.0));
}
`;

const K_UNTURNED = `
// aeolian.py unturned: the wind input of a grid where the wind is not turned, (1, 0) everywhere
//! image   outW rg32f

fn kmain(p: vec2<i32>) {
  if (!inside(p, outW_size())) { return; }
  outW_store(p, vec4<f32>(1.0, 0.0, 0.0, 0.0));
}
`;

const K_PACK = `
// SandSim._setup's np.stack([bed, sand], -1) (sand = np.maximum(sand, 0.0) when uClampB is 1) and its pins
// (pin_w, pin_sand)
//! sampler a r32f
//! sampler b r32f
//! image   outP rg32f
//! uniform int uClampB

fn kmain(p: vec2<i32>) {
  if (!inside(p, outP_size())) { return; }
  var bv = b_at(p).x;
  if (u.uClampB == 1) { bv = max(bv, 0.0); }
  outP_store(p, vec4<f32>(a_at(p).x, bv, 0.0, 0.0));
}
`;

const K_SPLIT = `
// SandSim.read's a[..., 0], a[..., 1]: a two-channel field as two
//! sampler src rg32f
//! image   outA r32f
//! image   outB r32f

fn kmain(p: vec2<i32>) {
  if (!inside(p, outA_size())) { return; }
  let s = src_at(p);
  outA_store(p, vec4<f32>(s.r, 0.0, 0.0, 0.0));
  outB_store(p, vec4<f32>(s.g, 0.0, 0.0, 0.0));
}
`;

const K_ACC = `
// SandSim.run_averaged's acc = s if acc is None else acc + s (numpy: float64): the first sample kept (uFirst 1), each
// later one added as its difference from the first, so the float32 sum carries the slab noise's metres
//! sampler st rg32f
//! image   base r32f
//! image   acc r32f
//! uniform int uFirst

fn kmain(p: vec2<i32>) {
  if (!inside(p, base_size())) { return; }
  let s = st_at(p).g;
  if (u.uFirst == 1) {
    base_store(p, vec4<f32>(s, 0.0, 0.0, 0.0));
    acc_store(p, vec4<f32>(0.0, 0.0, 0.0, 0.0));
  } else {
    acc_store(p, vec4<f32>(acc_load(p).x + (s - base_load(p).x), 0.0, 0.0, 0.0));
  }
}
`;

const K_MEAN = `
// SandSim.run_averaged's (acc / k).astype(np.float32): the first sample plus the mean difference
//! sampler base r32f
//! sampler acc r32f
//! image   outF r32f
//! uniform float uK

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  outF_store(p, vec4<f32>(base_at(p).x + acc_at(p).x / u.uK, 0.0, 0.0, 0.0));
}
`;

const K_GAUSS = `
// aeolian.py denoise: one axis of the separable Gaussian, sum_i k[i] s[t + i - r] in numpy's order (i = 0 .. 2r),
// wrapped (np.roll, uPeriodic 1) or mirrored (np.pad 'symmetric': ... s1 s0 | s0 s1 ... sn-1 | sn-1 sn-2 ...)
//! sampler src r32f
//! sampler taps r32f
//! image   outF r32f
//! uniform int uAxis
//! uniform int uR
//! uniform int uPeriodic

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var len = n.x;
  var t = p.x;
  if (u.uAxis == 0) { len = n.y; t = p.y; }            // numpy's axis 0: along the rows (y)
  let span = 2 * len;
  let lift = span * (u.uR / span + 1);                 // a whole number of periods above any reach: % of a positive
  var acc = 0.0;
  for (var i = 0; i <= 2 * u.uR; i++) {
    var e = t + i - u.uR;
    if (u.uPeriodic == 1) {
      e = (e + lift) % len;
    } else {
      e = (e + lift) % span;
      if (e >= len) { e = span - 1 - e; }
    }
    var q = p;
    if (u.uAxis == 0) { q.y = e; } else { q.x = e; }
    acc = acc + taps_b[i] * src_at(q).x;
  }
  outF_store(p, vec4<f32>(acc, 0.0, 0.0, 0.0));
}
`;

const K_PINBLEND = `
// aeolian.py denoise's end: s (1 - w) + pin_sand w with w = clip(pin_w, 0, 1) (uPins 1), then np.maximum(s, 0)
//! sampler s r32f
//! sampler w r32f
//! sampler ps r32f
//! image   outF r32f
//! uniform int uPins

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  var v = s_at(p).x;
  if (u.uPins == 1) {
    let a = clamp(w_at(p).x, 0.0, 1.0);
    v = v * (1.0 - a) + ps_at(p).x * a;
  }
  outF_store(p, vec4<f32>(max(v, 0.0), 0.0, 0.0, 0.0));
}
`;

const K_SHEET = `
// aeolian.py smooth_sheet: t = clip((s - 1.5 top) / (1.5 top), 0, 1), w = 1 - t^2 (3 - 2 t), max(s (1 - w) + blur w, 0)
//! sampler s r32f
//! sampler blur r32f
//! image   outF r32f
//! uniform float uTop15

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let s = s_at(p).x;
  let t = clamp((s - u.uTop15) / u.uTop15, 0.0, 1.0);
  let w = 1.0 - t * t * (3.0 - 2.0 * t);
  outF_store(p, vec4<f32>(max(s * (1.0 - w) + blur_at(p).x * w, 0.0), 0.0, 0.0, 0.0));
}
`;

const K_SAMPLE = `
// aeolian.py sample_periodic: a periodic field averaged over a coarser level's m x m cells, rows first then columns
// (a[rows, :].reshape(n, m, N).mean(axis=1), then [:, cols].reshape(n, n, m).mean(axis=2)), wrapped over the period
//! sampler src r32f
//! image   outF r32f
//! uniform int uI0
//! uniform int uJ0
//! uniform int uM

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let n = src_size();
  let fm = f32(u.uM);
  var acc = 0.0;
  for (var c = 0; c < u.uM; c++) {
    let col = (u.uI0 + p.x * u.uM + c) % n.x;
    var cs = 0.0;
    for (var r = 0; r < u.uM; r++) {
      let row = (u.uJ0 + p.y * u.uM + r) % n.y;
      cs = cs + src_at(vec2<i32>(col, row)).x;
    }
    acc = acc + cs / fm;
  }
  outF_store(p, vec4<f32>(acc / fm, 0.0, 0.0, 0.0));
}
`;

const K_REFINE_START = `
// aeolian.py refine / op_aeolian: bed = min(bed or h - sand or h, h), sand = max(h - bed, 0)
//! sampler h r32f
//! sampler b r32f
//! image   outBed r32f
//! image   outSand r32f
//! uniform int uMode

fn kmain(p: vec2<i32>) {
  if (!inside(p, outBed_size())) { return; }
  let hv = h_at(p).x;
  var bed = hv;
  if (u.uMode == 0) { bed = b_at(p).x; } else if (u.uMode == 1) { bed = hv - b_at(p).x; }
  bed = min(bed, hv);
  outBed_store(p, vec4<f32>(bed, 0.0, 0.0, 0.0));
  outSand_store(p, vec4<f32>(max(hv - bed, 0.0), 0.0, 0.0, 0.0));
}
`;

const K_GAIN = `
// aeolian.py stretch_periodic's gain exp(-2 (pi sigma k_along)^2), k_along = kx sin t + ky cos t on numpy's
// frequencies (np.fft.rfftfreq along x, fftfreq along y), on the full spectrum fft2(a - mean) that irfft2 reads: the
// Nyquist column (even width) symmetrised over +-ky (irfft keeps that column's real part), the mirrored half's Nyquist
// row (even height) at ky = +0.5 / cell (the mirror of rfftfreq's bins). Writes conj(F gain): the inverse is
// conj(fft2(conj(Y))) / N. pi sigma k_along = uA i + uB j for the signed bin indices (i, j).
//! sampler src rg32f
//! image   outF rg32f
//! uniform float uA
//! uniform float uB

fn gain(x: f32) -> f32 { return exp(-2.0 * x * x); }

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var ix = p.x;
  if (ix > (n.x - 1) / 2) { ix = ix - n.x; }
  var iy = p.y;
  if (iy > (n.y - 1) / 2) { iy = iy - n.y; }
  let evenX = (n.x % 2) == 0;
  let evenY = (n.y % 2) == 0;
  var g: f32;
  if (evenX && p.x == n.x / 2) {
    let kx = f32(n.x / 2) * u.uA;
    var iy2 = -iy;
    if (evenY && p.y == n.y / 2) { iy2 = iy; }
    g = 0.5 * (gain(kx + f32(iy) * u.uB) + gain(kx + f32(iy2) * u.uB));
  } else {
    var jy = iy;
    if (evenY && p.y == n.y / 2 && ix < 0) { jy = -iy; }
    g = gain(f32(ix) * u.uA + f32(jy) * u.uB);
  }
  let v = src_at(p).xy * g;
  outF_store(p, vec4<f32>(v.x, -v.y, 0.0, 0.0));
}
`;

const K_REAL = `
// aeolian.py stretch_periodic's np.fft.irfft2: the real part of conj(fft2(conj(Y))) / N
//! sampler src rg32f
//! image   outF r32f
//! uniform float uScale

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  outF_store(p, vec4<f32>(src_at(p).x * u.uScale, 0.0, 0.0, 0.0));
}
`;

const KERNELS = { start: K_START, steer_n: K_STEER_N, steer_wind: K_STEER_WIND, unturned: K_UNTURNED, pack: K_PACK,
    split: K_SPLIT, acc: K_ACC, mean: K_MEAN, gauss: K_GAUSS, pinblend: K_PINBLEND, sheet: K_SHEET, sample: K_SAMPLE,
    refine_start: K_REFINE_START, gain: K_GAIN, real: K_REAL };

/** One of this module's own kernels on runner R (cached by the runner per source). */
const kern = (R, name) => R.kernel(`aeolian_${name}`, KERNELS[name]);

function isField(v) {
    return v !== null && typeof v === 'object' && typeof v.h === 'number' && v.runner !== undefined && v.buffer !== undefined;
}

function copyOf(f) {
    const c = f.runner.like(f);
    f.runner.copy(f, c);
    return c;
}


// ------------------------------------------------------------------------------------------ the steering ---

/** The regional relief's steering of the wind: the turn of its direction at every cell of a grid. A wind the
 * regime gives from compass theta is turned by
 *
 *     delta(x, y, theta) = steer x (n1 cos 2 theta + n2 sin 2 theta) + turn x n3        (radians)
 *
 * with n1, n2, n3 smooth world-space fields of unit variance clipped at +-2 (steeringFor). The 2 theta turns a wind
 * and its reverse alike, as flow steered round relief is; winds from other directions are turned in other
 * patterns, so the regime's shape (the angles between its winds) varies across the field as well as its
 * orientation: each dune sees its own regime, and a long arm curves as the regime turns along it. turn x n3 turns
 * every wind together (the whole regime rotates across the field). forWind(theta) gives the kernels' `wind` input,
 * (cos, sin) of delta as an rg32f field, and the least and the most turn on the grid (for hopBox).
 *
 * n: an rgba32f GPU field holding (n1, n2, n3, unused) (Steering.fromFields packs three r32f fields). The Steering
 * owns it and the fields forWind makes; dispose() releases them. */
export class Steering {
    constructor(n, steerDeg, turnDeg = 0.0) {
        if (!isField(n) || n.channels !== 4 || n.kind !== 'f32') {
            throw new ValueError(`steering fields must be (3, H, W), got ${isField(n) ? shapeText([n.h, n.w, n.channels]) : typeof n}`);
        }
        this.n = n;
        this.R = n.runner;
        this.shape = [n.h, n.w];
        this.steer = radians(steerDeg);
        this.turn = radians(turnDeg);
        this._cache = new Map();
    }

    /** A Steering from three r32f fields of one shape (packed on the GPU; the inputs stay the caller's). */
    static fromFields(n1, n2, n3, steerDeg, turnDeg = 0.0) {
        const R = n1.runner;
        return new Steering(R.pack({ n1, n2, n3 }, ['n1', 'n2', 'n3', null]), steerDeg, turnDeg);
    }

    // delta for a wind from compass thetaDeg: [d (r32f), cs (rg32f)], new fields
    _evaluate(thetaDeg) {
        const R = this.R;
        const a = radians(2.0 * Number(thetaDeg));
        const d = R.field(this.shape[0], this.shape[1], 1), cs = R.field(this.shape[0], this.shape[1], 2);
        R.run(kern(R, 'steer_wind'), { nf: this.n }, { outCs: cs, outD: d },
            { uSteer: this.steer, uTurn: this.turn, uCos2: Math.cos(a), uSin2: Math.sin(a) });
        return [d, cs];
    }

    /** delta at every cell for a wind from compass thetaDeg, radians: a new r32f field the caller owns. */
    angle(thetaDeg) {
        const [d, cs] = this._evaluate(thetaDeg);
        cs.destroy();
        return d;
    }

    /** { cs: (cos, sin) of delta as an rg32f field (the Steering's: do not destroy it), turn: [least, most] delta in
     * radians }, cached per direction (eight at most). */
    async forWind(thetaDeg) {
        const key = roundKey(pyMod(Number(thetaDeg), 360.0));
        if (!this._cache.has(key)) {
            const [d, cs] = this._evaluate(key);
            const st = await prims(this.R).stats(d);
            d.destroy();
            if (this._cache.size >= 8) {
                const first = this._cache.keys().next().value;
                this._cache.get(first).cs.destroy();
                this._cache.delete(first);
            }
            this._cache.set(key, { cs, turn: [st.min, st.max] });
        }
        return this._cache.get(key);
    }

    dispose() {
        for (const e of this._cache.values()) if (!e.cs.destroyed) e.cs.destroy();
        this._cache.clear();
        if (!this.n.destroyed) this.n.destroy();
    }
}


// ----------------------------------------------------------------------------------------- the uniforms ---

/** The uniforms of the four kernels for one iteration: { kernel: { uniform: value } }. turn: the least and the most
 * the steering turns this wind on the grid, radians (Steering.forWind), for the transport's box of hops. */
export function uniformsFor(params, cell, fromDeg, it, seed, bound, turn = [0.0, 0.0]) {
    const p = params;
    const d = transportDir(fromDeg);
    const hc = Number(p.hop_cells);
    const hop = [d[0] * hc, d[1] * hc];
    const slab = Number(p.slab_cells) * Number(cell);
    const tanHi = Math.tan(radians(Number(p.shadow_deg)));
    const tanLo = Math.tan(radians(Math.min(Number(p.shadow_lo_deg), Number(p.shadow_deg))));
    const longF = Math.max(1.0, Number(p.long_factor));
    const riseMode = p.rise === 'sand' ? 1 : 0;
    let speedFrom, speedRef;
    if (riseMode === 1) {
        speedFrom = Number(p.speed_from_m);
        speedRef = Math.max(speedFrom + 1e-6, Number(p.speed_ref_m));
    } else {
        speedFrom = 0.0;
        speedRef = Math.max(1e-6, pyInt(p.shadow_reach) * Number(cell) * Math.tan(radians(Number(p.speed_ref_deg))));
    }
    const [vmin, vmax] = hopBox(hop, longF, turn);
    return {
        dune_shadow: { uDir: [d[0], d[1]], uTanLo: tanLo, uTanHi: tanHi, uReach: pyInt(p.shadow_reach), uCell: Number(cell),
            uRiseMode: riseMode, uBound: pyInt(bound) },
        dune_activate: { uHop: [hop[0], hop[1]], uLong: longF, uSpeedup: longF > 1.0 ? Number(p.speedup) : 0.0,
            uLiftBoost: Number(p.lift_boost), uSpeedFrom: speedFrom, uSpeedRef: speedRef,
            uSpeedPow: Math.max(1, pyInt(or(p.speed_pow, 1))), uSlab: slab, uMinSand: Number(p.min_sand_slabs) * slab,
            uPLift: Number(p.p_lift), uPSand: Number(p.p_sand), uPRock: Number(p.p_rock), uMaxHops: pyInt(p.max_hops),
            uIter: pyInt(it), uSeed: pyInt(seed), uBound: pyInt(bound) },
        dune_transport: { uVMin: vmin, uVMax: vmax, uMaxHops: pyInt(p.max_hops), uBound: pyInt(bound) },
        dune_avalanche: { uTanRepose: Math.tan(radians(Number(p.repose_deg))), uRate: Number(p.aval_rate),
            uCreep: Number(p.creep), uCell: Number(cell), uBound: pyInt(bound) },
    };
}

/** The slab model's limits on a grid: a hop path and the shadow ray must stay within one period. */
export function checkGrid(shape, params, bound) {
    const [h, w] = shape;
    const p = params;
    const reach = (Math.abs(Number(p.hop_cells)) * Math.max(1.0, Number(p.long_factor)) + 1.0) * pyInt(p.max_hops);
    if (bound === BOUND_PERIODIC && reach >= Math.min(h, w)) {
        // hop_cells is a float parameter (Python prints 3.0), max_hops and shadow_reach integers
        throw new ValueError(`a periodic grid of ${w} x ${h} cells is too small for ${pyStr(p.max_hops)} hops of ` +
            `${pyRepr(Number(p.hop_cells))} cells`);
    }
    if (bound === BOUND_PERIODIC && pyInt(p.shadow_reach) + 2 >= Math.min(h, w)) {
        throw new ValueError(`a periodic grid of ${w} x ${h} cells is too small for a shadow reach of ` +
            `${pyStr(p.shadow_reach)} cells`);
    }
}


// -------------------------------------------------------------------------------------------- simulation ---

/** The `wind` input of a grid where the wind is not turned: (cos, sin) = (1, 0) everywhere, a new rg32f field. */
export function unturned(R, shape) {
    const out = R.field(shape[0], shape[1], 2);
    R.run(kern(R, 'unturned'), {}, { outW: out }, {});
    return out;
}

/** The slab model on the GPU (core/gpu.js): bed and sand (r32f fields of one shape, metres, row 0 south; copied in,
 * the caller keeps them) on a grid of `cell` metres. opts: bound (BOUND_PERIODIC, BOUND_OPEN or BOUND_PINNED with
 * pinW 0..1 and pinSand, r32f fields: the sand held there), params, seed, steer (a Steering on the same grid: the
 * wind turned cell by cell, or null). step(fromDeg, windDeg) runs one iteration (windDeg: the regime's own direction
 * for this wind, which the steering is keyed on; default fromDeg); run(winds, iterations) a regime; fields() the
 * state as new { bed, sand } fields; read() the host arrays. dispose() releases its fields (not the steering). */
export class SandSim {
    constructor(bed, sand, cell, opts = {}) {
        const bound = opts.bound ?? BOUND_PERIODIC;
        this.P = paramsFor(opts.params ?? null);
        if (!isField(bed) || !isField(sand) || bed.h !== sand.h || bed.w !== sand.w || bed.channels !== 1 || sand.channels !== 1) {
            const sh = (f) => (isField(f) ? shapeText(f.channels === 1 ? [f.h, f.w] : [f.h, f.w, f.channels]) : typeof f);
            throw new ValueError(`bed ${sh(bed)} and sand ${sh(sand)} must be one 2D shape`);
        }
        const R = this.R = bed.runner;
        const [h, w] = [bed.h, bed.w];
        checkGrid([h, w], this.P, pyInt(bound));
        const steer = opts.steer ?? null;
        if (steer !== null && (steer.shape[0] !== h || steer.shape[1] !== w)) {
            throw new ValueError(`the steering ${shapeText(steer.shape)} is not on the grid ${shapeText([h, w])}`);
        }
        this.steer = steer;
        this.shape = [h, w];
        this.cell = Number(cell);
        this.bound = pyInt(bound);
        this.seed = pyInt(opts.seed ?? 0);
        this.it = 0;
        const pack = kern(R, 'pack');
        this.st = R.pair(h, w, 2);
        R.run(pack, { a: bed, b: sand }, { outP: this.st.src }, { uClampB: 1 });       // np.maximum(sand, 0.0)
        this.pins = R.field(h, w, 2);
        if (opts.pinW) {
            if (opts.pinSand) {
                R.run(pack, { a: opts.pinW, b: opts.pinSand }, { outP: this.pins }, { uClampB: 0 });
            } else {                                    // pin_sand defaults to the (clamped) sand
                R.run(pack, { a: opts.pinW, b: sand }, { outP: this.pins }, { uClampB: 1 });
            }
        }
        this.k = { dune_shadow: R.kernel('dune_shadow'), dune_activate: R.kernel('dune_activate'),
            dune_transport: R.kernel('dune_transport'), dune_avalanche: R.kernel('dune_avalanche') };
        this.shadow = R.empty(this.shape, 2);
        this.plan = R.empty(this.shape, 4);
        this._windTex = new Map();
        this._u = null;
        this._uDir = null;
    }

    /** Change model parameters between runs (a growth phase): the next step builds its uniforms afresh. */
    setParams(overrides = {}) {
        Object.assign(this.P, overrides);
        checkGrid(this.shape, this.P, this.bound);
        this._u = null;
    }

    /** The `wind` field for a wind (the steering's turn, or none) and its range of turns, cached: { field, turn }. */
    async _wind(windDeg) {
        const key = this.steer === null ? null : roundKey(pyMod(Number(windDeg), 360.0));
        let e = this._windTex.get(key);
        if (!e) {
            if (key === null) {
                e = { field: unturned(this.R, this.shape), turn: [0.0, 0.0] };
            } else {
                const { cs, turn } = await this.steer.forWind(key);
                e = { field: copyOf(cs), turn };       // its own copy, as Blender's G.texture(cs)
            }
            this._windTex.set(key, e);
        }
        return e;
    }

    /** One iteration (dune_shadow, dune_activate, dune_transport, aval_passes x dune_avalanche). */
    async step(fromDeg, windDeg = null) {
        windDeg = windDeg ?? fromDeg;
        const e = await this._wind(windDeg);
        this._step(fromDeg, windDeg, e);
    }

    _step(fromDeg, windDeg, e) {
        const R = this.R, k = this.k;
        if (this._u === null || this._uDir === null || this._uDir[0] !== fromDeg || this._uDir[1] !== windDeg) {
            this._u = uniformsFor(this.P, this.cell, fromDeg, this.it, this.seed, this.bound, e.turn);
            this._uDir = [fromDeg, windDeg];
        }
        const u = this._u;
        u.dune_activate.uIter = this.it;
        R.run(k.dune_shadow, { st: this.st.src, wind: e.field }, { outShadow: this.shadow }, u.dune_shadow);
        R.run(k.dune_activate, { st: this.st.src, shadow: this.shadow, wind: e.field }, { outPlan: this.plan }, u.dune_activate);
        R.run(k.dune_transport, { st: this.st.src, plan: this.plan }, { outSt: this.st.dst }, u.dune_transport);
        this.st.swap();
        const passes = pyInt(this.P.aval_passes);
        for (let i = 0; i < passes; i++) {
            R.run(k.dune_avalanche, { st: this.st.src, pins: this.pins }, { outSt: this.st.dst }, u.dune_avalanche);
            this.st.swap();
        }
        this.it += 1;
    }

    /** Run the regime for at least `iterations`, in whole cycles. opts: block, jitterDeg, callback(sim, done) every
     * `every` iterations (it may be async; a true result stops the run at the end of the current cycle). Returns the
     * iterations run. */
    async run(winds, iterations, opts = {}) {
        const block = pyInt(or(opts.block, this.P.block));
        const jit = Number(opts.jitterDeg ?? this.P.jitter_deg);
        const sched = schedule(winds, iterations, block, jit, this.seed + this.it, pyInt(or(this.P.gust, 0)),
            Number(or(this.P.spread_deg, 0.0)), true);
        const per = scheduleLength(schedule(winds, 1, block, 0.0));
        const callback = opts.callback ?? null, every = opts.every ?? 0;
        let done = 0, stop = false;
        for (const [d, b, w] of sched) {
            const e = await this._wind(w);
            for (let i = 0; i < b; i++) {
                this._step(d, w, e);
                done += 1;
                if (callback !== null && every && done % every === 0) {
                    let r = callback(this, done);
                    if (r && typeof r.then === 'function') r = await r;
                    if (r) stop = true;
                }
            }
            if (stop && done % per === 0) break;
        }
        return done;
    }

    /** run() for at least `iterations` (whole cycles), and the sand time-averaged over the run's last
     * `averageIters` iterations (sampled every `every`): [iterations run, bed, mean sand] (new r32f fields). The slab
     * model's speckle (single slabs arriving and leaving, about 0.15 cells) decorrelates within tens of iterations
     * while a dune moves a fraction of a cell in hundreds, so the average clears the speckle and keeps the crests and
     * brinks as sharp as the cells draw them; a Gaussian of a cell rounds them by as much. Each sample holds the same
     * total, so the mean does too. */
    async runAveraged(winds, iterations, averageIters, every = 10, callback = null, checkEvery = 0) {
        const R = this.R;
        const block = pyInt(this.P.block);
        const per = scheduleLength(schedule(winds, 1, block, 0.0));
        const total = per * Math.max(1, Math.ceil(pyInt(iterations) / per));
        const start = Math.max(0, total - pyInt(averageIters));
        let base = null, acc = null, k = 0;
        every = Math.max(1, pyInt(every));
        const kAcc = kern(R, 'acc');
        const cb = (sim, done) => {
            if (averageIters && done > start && (done - start) % every === 0) {
                if (base === null) {
                    base = R.field(this.shape[0], this.shape[1], 1);
                    acc = R.field(this.shape[0], this.shape[1], 1);
                }
                R.run(kAcc, { st: this.st.src }, { base, acc }, { uFirst: k === 0 ? 1 : 0 });
                k += 1;
            }
            if (callback !== null && checkEvery && done % pyInt(checkEvery) === 0) return callback(sim, done);
            return false;
        };
        const done = await this.run(winds, iterations, { callback: cb, every: 1 });
        const { bed, sand } = this.fields();
        let out = sand;
        if (acc !== null && k > 1 && done === total) {
            out = R.field(this.shape[0], this.shape[1], 1);
            R.run(kern(R, 'mean'), { base, acc }, { outF: out }, { uK: k });
            sand.destroy();
        }
        if (base !== null) {
            base.destroy();
            acc.destroy();
        }
        return [done, bed, out];
    }

    /** The state as new r32f fields { bed, sand } (the caller owns them). */
    fields() {
        const R = this.R;
        const bed = R.field(this.shape[0], this.shape[1], 1), sand = R.field(this.shape[0], this.shape[1], 1);
        R.run(kern(R, 'split'), { src: this.st.src }, { outA: bed, outB: sand }, {});
        return { bed, sand };
    }

    /** [bed, sand] as host Float32Arrays (row 0 south): the Blender read(), a readback. */
    async read() {
        const { bed, sand } = this.fields();
        const got = await this.R.readAll([bed, sand]);
        bed.destroy();
        sand.destroy();
        return got;
    }

    /** The last shadow (its r channel) as a host Float32Array. */
    async readShadow() {
        const R = this.R;
        const a = R.field(this.shape[0], this.shape[1], 1), b = R.field(this.shape[0], this.shape[1], 1);
        R.run(kern(R, 'split'), { src: this.shadow }, { outA: a, outB: b }, {});
        const got = await R.read(a);
        a.destroy();
        b.destroy();
        return got;
    }

    dispose() {
        this.st.destroy();
        for (const f of [this.shadow, this.plan, this.pins]) if (!f.destroyed) f.destroy();
        for (const e of this._windTex.values()) if (!e.field.destroyed) e.field.destroy();
        this._windTex.clear();
    }
}


// ------------------------------------------------------------------------------------- smoothing and sheets ---

// the Gaussian's taps exp(-0.5 (i / sigma)^2), i = -r .. r, over their numpy sum, as a float32 list field
function gaussTaps(R, sigma, r) {
    const k = [];
    for (let i = -r; i <= r; i++) k.push(Math.exp(-0.5 * (i / sigma) ** 2));
    const s = pairwiseSum(k);
    return R.field(1, k.length, 1, Float32Array.from(k.map((v) => v / s)));
}

/** The slab noise cleared: a separable Gaussian of sigmaCells cells over the sand thickness (wrapped on a periodic
 * grid, mirrored at an open edge, so the total sand is kept), then the pins re-applied, then max(sand, 0). opts:
 * periodic, pinW, pinSand (r32f fields). A new r32f field; `sand` is the caller's. */
export function denoise(sand, sigmaCells, opts = {}) {
    const R = sand.runner;
    const D = Gd.dummies(R);
    let s = sand, owned = false;
    if (sigmaCells && sigmaCells > 0) {
        const r = Math.max(1, Math.ceil(3.0 * Number(sigmaCells)));
        const taps = gaussTaps(R, Number(sigmaCells), r);
        for (const axis of [0, 1]) {
            const out = R.field(sand.h, sand.w, 1);
            R.run(kern(R, 'gauss'), { src: s, taps }, { outF: out }, { uAxis: axis, uR: r, uPeriodic: opts.periodic ? 1 : 0 });
            if (owned) s.destroy();
            s = out;
            owned = true;
        }
        taps.destroy();
    }
    const pins = opts.pinW !== null && opts.pinW !== undefined;
    const out = R.field(sand.h, sand.w, 1);
    R.run(kern(R, 'pinblend'), { s, w: pins ? opts.pinW : D.f1, ps: pins ? opts.pinSand : D.f1 }, { outF: out },
        { uPins: pins ? 1 : 0 });
    if (owned) s.destroy();
    return out;
}

/** The low-mobility sand sheet smoothed: where the sand is thinner than 1.5 x the speed-up's start (speed_from_m:
 * sand the wind barely lifts, the plinth under the dunes and the interdune sheets) and on the bare floor, a Gaussian
 * of sheet_smooth_cells replaces it, easing to none at 3 x that thickness (the dunes' aprons). Slabs the dunes shed
 * land on such a sheet and stay, a speckle the time-averaged read-out cannot clear because the sheet hardly moves;
 * on real sheets reptation and migrating ripples keep the surface flat. The bare floor takes the Gaussian too, so a
 * sheet's margin thins out onto the floor over a few sigma as a real sand sheet's does (kept bare, the floor left
 * every sheet standing as a table with a step at its edge: the review's straight-edged plates), and single slabs
 * resting on the floor spread into a faint veneer. The dunes are untouched. A read-out blend, not a transport: the
 * total can rise by about a percent where the blur reaches up a dune's toe. A new r32f field (a copy of the sand when
 * the parameter is 0 or there is no threshold); opts as denoise's. */
export function smoothSheet(sand, p, opts = {}) {
    const R = sand.runner;
    const sig = Number(or(p.sheet_smooth_cells, 0.0));
    const top = Number(or(p.sheet_top_m, or(p.speed_from_m, 0.0)));
    const rise = 'rise' in p ? p.rise : 'sand';
    if (sig <= 0 || top <= 0 || rise !== 'sand') return copyOf(sand);
    const blur = denoise(sand, sig, opts);
    const out = R.field(sand.h, sand.w, 1);
    R.run(kern(R, 'sheet'), { s: sand, blur }, { outF: out }, { uTop15: 1.5 * top });
    blur.destroy();
    return out;
}


// ------------------------------------------------------------------------------------------ measurements ---

/** The dune spacing as the judge reads it: the wavelength carrying the most slope (the peak of k^2 P(k)),
 * between loCells pixels and a quarter of the extent, metres (core/metrics.js radial_spectrum, 64 bins). */
export async function spacingPeak(h, cell, loCells = 4.0) {
    const [wl, P] = await M.radialSpectrum(h, cell, 64);
    const sel = [];
    for (let i = 0; i < wl.length; i++) {
        if (wl[i] >= loCells * cell && wl[i] <= 0.25 * Math.min(h.h, h.w) * cell) sel.push(i);
    }
    if (!sel.length) return NaN;
    const sp = convolveSame(sel.map((i) => (1.0 / wl[i]) * (1.0 / wl[i]) * P[i]), [1 / 3, 1 / 3, 1 / 3]);
    let best = 0;
    for (let i = 1; i < sp.length; i++) if (sp[i] > sp[best]) best = i;
    if (best >= sel.length) throw new Error('index out of bounds');   // numpy's IndexError for fewer than 3 bins
    return wl[sel[best]];
}

/** How tall the dunes stand: p99.5 - p0.5 of the sand thickness, metres (the bed's own relief left out); numpy's
 * float64 percentiles from the exact order statistics. opts.channel: the sand's channel of a packed field. */
export async function duneHeight(sand, opts = {}) {
    const P = prims(sand.runner);
    const o = { dtype: 'float64', channel: opts.channel ?? 0 };
    return (await P.percentile(sand, 99.5, o)) - (await P.percentile(sand, 0.5, o));
}

/** The share of cells within `below` degrees of the angle of repose or steeper: standing slip faces. */
export async function slipFraction(h, cell, reposeDeg = 31.0, below = 4.0) {
    const P = prims(h.runner);
    const s = Gd.slopeDeg(h, cell);
    const flags = P.where(s, '>=', reposeDeg - below);
    const { nonzero } = await P.statsU32(flags);
    s.destroy();
    flags.destroy();
    return nonzero / (h.h * h.w);
}


// ------------------------------------------------------------------------------------- the start surface ---

function periodicWavelength(w, period) {
    return period ? N.snapWavelength(w, period) : Number(w);
}

/** World-space fbm at a level's cells (periodic over periodM when given, its wavelength snapped to it): a new r32f
 * field (world_noise.py field_gpu's evaluation). */
function fbmField(R, level, wavelengthM, octaves, seed, periodM = null) {
    const wl = periodicWavelength(wavelengthM, periodM);
    const spec = { kind: 'fbm', wavelength_m: wl, octaves: pyInt(octaves), period_m: periodM ?? null };
    return N.fieldGpu(R, spec, level, seed);
}

/** The Steering at a level's cells (world-space, periodic over periodM when given), or null when p asks for none
 * (steer_deg and steer_turn_deg 0). n1, n2, n3: 3 x fbm at steer_wavelength_m (2 octaves: unit variance), clipped at
 * +-2, so no cell turns more than twice the standard deviation. Every level evaluates the same functions of world
 * position, so a finer level's wind turns as its parent's did. */
export function steeringFor(R, level, p, seed, periodM = null) {
    const steer = Number(or(p.steer_deg, 0.0)), turn = Number(or(p.steer_turn_deg, 0.0));
    if (steer <= 0.0 && turn <= 0.0) return null;
    const wl = Number(or(p.steer_wavelength_m, 2.5 * Number(or(p.spacing_m, 1200.0))));
    const f = [0, 1, 2].map((k) => fbmField(R, level, wl, 2, pyInt(seed) * 7 + 11 + k, periodM));
    const n = R.field(level.n, level.n, 4);
    R.run(kern(R, 'steer_n'), { f0: f[0], f1: f[1], f2: f[2] }, { outN: n }, {});
    for (const x of f) x.destroy();
    return new Steering(n, steer, turn);
}

// numpy's a.mean() and a.std() of a float field (float64 there; float32 tree sums here)
async function meanStd(f) {
    const R = f.runner, P = prims(R);
    const n = f.h * f.w;
    const mean = (await P.stats(f)).sum / n;
    const dev = Gd.arith(R, 'affine', f, null, { amp: 1.0, off: -mean });
    const sq = Gd.arith(R, 'mul', dev, dev);
    const ss = (await P.stats(sq)).sum;
    dev.destroy();
    sq.destroy();
    return [mean, Math.sqrt(ss / n)];
}

/** A periodic field's features drawn out along one compass direction: a Gaussian of sigmaM metres along axisDeg
 * only (in Fourier space, so it wraps over the period exactly), then rescaled to the field's own mean and standard
 * deviation. A new r32f field (a copy when sigmaM is 0); `a` is the caller's. */
export async function stretchPeriodic(a, cell, sigmaM, axisDeg) {
    if (!sigmaM || sigmaM <= 0) return copyOf(a);
    const R = a.runner, P = prims(R);
    const ny = a.h, nx = a.w;
    const t = radians(axisDeg);
    const [m, sd0] = await meanStd(a);
    const b = Gd.arith(R, 'affine', a, null, { amp: 1.0, off: -m });
    const F = P.fft2(b, { real: true });
    b.destroy();
    const Y = R.field(ny, nx, 2);
    R.run(kern(R, 'gain'), { src: F }, { outF: Y },
        { uA: Math.PI * Number(sigmaM) * Math.sin(t) / (nx * Number(cell)), uB: Math.PI * Number(sigmaM) * Math.cos(t) / (ny * Number(cell)) });
    F.destroy();
    const Z = P.fft2(Y);
    Y.destroy();
    const out = R.field(ny, nx, 1);
    R.run(kern(R, 'real'), { src: Z }, { outF: out }, { uScale: 1.0 / (nx * ny) });
    Z.destroy();
    const [, sd1] = await meanStd(out);
    const res = Gd.arith(R, 'affine', out, null, { amp: sd1 > 0 ? sd0 / sd1 : 0.0, off: m });
    out.destroy();
    return res;
}

/** The growth start at a level's cells (world-space, periodic over periodM when given): { bed, sand }, new r32f
 * fields. bed: bed_m x 3 fbm at bed_wavelength_m (3 octaves). sand: sand_m x max(0, 1 + supply_var x 3 fbm) at
 * supply_wavelength_m, plus the seed: seed_m x 3 fbm at the target spacing (2 octaves). With supply_stretch_m (a
 * periodic start only) the supply's highs and lows are drawn out along supply_axis_deg (stretchPeriodic), so where
 * the sand runs out the floor is a long corridor between dune chains, as the Namib's interdune pans are, not a round
 * hole; supply_cap limits the supply's highs (a multiple of sand_m). */
export async function startFields(R, level, p, seed, periodM = null) {
    const per = periodM;
    const fbm = (w, octaves, s) => fbmField(R, level, w, octaves, s, per);
    const D = Gd.dummies(R);
    seed = pyInt(seed);
    const bedN = fbm(Number(p.bed_wavelength_m), 3, seed * 7 + 1);
    let sn = fbm(Number(p.supply_wavelength_m), 2, seed * 7 + 2);
    if (Number(or(p.supply_stretch_m, 0.0)) > 0.0 && per) {
        const s2 = await stretchPeriodic(sn, level.cell, Number(p.supply_stretch_m), Number(or(p.supply_axis_deg, 0.0)));
        sn.destroy();
        sn = s2;
    }
    const seedOn = Number(p.seed_m) > 0;
    const seedN = seedOn ? fbm(Number(p.spacing_m) * Number(p.seed_scale), 2, seed * 7 + 3) : null;
    const bed = R.field(level.n, level.n, 1), sand = R.field(level.n, level.n, 1);
    const capOn = truthy(p.supply_cap);
    R.run(kern(R, 'start'), { bedN, supN: sn, seedN: seedN ?? D.f1 }, { outBed: bed, outSand: sand },
        { uBed3: Number(p.bed_m) * 3.0, uVar3: Number(p.supply_var) * 3.0, uCapOn: capOn ? 1 : 0,
            uCap: capOn ? Number(p.supply_cap) : 0.0, uSandM: Number(p.sand_m), uSeedOn: seedOn ? 1 : 0,
            uSeed3: Number(p.seed_m) * 3.0 });
    bedN.destroy();
    sn.destroy();
    seedN?.destroy();
    return { bed, sand };
}


// ------------------------------------------------------------------------------------- the level stack ---

export const FIELD_DEFAULTS = Object.freeze({
    kind: 'star',
    winds: null,                 // null: the kind's regime
    wind_rotate_deg: 0.0,        // turn the whole regime clockwise
    sand_m: null,                // mean sand thickness, metres (null: the kind's)
    spacing_m: null,             // target dune spacing, metres (null: the kind's)
    seed_frac: 0.15,             // seed amplitude, a share of the target height (design: 10-20 %)
    height_ratio: null,          // target height / spacing for the seed (null: from the kind)
    seed_scale: 1.0,             // the seed's lattice wavelength, a multiple of the spacing
    speed_from_frac: 0.25,       // the speed-up starts at this share of the target height of sand ...
    speed_ref_frac: 2.0,         // ... and is full at this multiple of it
    supply_var: 0.35,            // the sand supply's variation: 1 + supply_var x (unit-variance noise)
    patchiness: null,            // > 0: the recipe's sand_patchiness knob, which sets supply_var over the kind's own
    supply_wavelength_m: null,   // the supply's wavelength (null: 6 x the spacing)
    supply_stretch_m: 0.0,       // > 0: the supply's highs and lows drawn out along supply_axis_deg by a Gaussian of
    supply_axis_deg: 90.0,       // this many metres (stretchPeriodic: long interdune corridors); the axis is a compass
                                 // trend, turned with the winds by wind_rotate_deg
    supply_cap: null,            // the most the sand piles anywhere at the start, a multiple of sand_m (null: no cap): a
                                 // strong supply_var opens bare corridors, and uncapped its highs grow dunes far taller
                                 // than the place's
    bed_m: null,                 // the bed's undulation, metres (standard deviation; null: the kind's, else 6)
    bed_wavelength_m: null,      // its wavelength (null: 5 x the spacing)
    cells_per_spacing: 24.0,     // the growth level resolves the spacing with at least this many cells
    grow_iters: 12000,           // the growth run: the slab model is scale-free in cells, and the growth level always
                                 // holds cells_per_spacing or more cells per dune, so one count gives one maturity
    grow_min_iters: 12000,       // an early stop may come after this many (equal to grow_iters: no early stop) ...
    grow_check: 3000,            // (iterations between the growth checks, which log the dunes' height and spacing)
    height_reached: 1.0,         // ... once the dunes (p99.5 - p0.5 of the sand) stand this share of the target height
    slip_reached: 0.002,         // ... and this share of the cells stand at the slip-face angle
    refine_iters: 1200,          // iterations on each level finer than the growth level (whole cycles of its winds)
    refine_winds: 'cycle',       // the winds those levels blow: 'cycle' the whole regime, 'last' its last wind (refine)
    refine_hop_cells: null,      // the hop on refinement levels (null: hop_cells)
    refine_block: null,          // iterations per wind block on those levels (null: block)
    refine_average_iters: null,  // their time-averaged read-out (null: average_iters; 0: the last state, denoised)
    refine_smooth_cells: null,   // their read-out Gaussian, cells (null: smooth_cells)
    hero_winds: null,            // the hero levels' own winds, iterations, block, read-out and Gaussian (null: the
    hero_iters: null,            // refine_* values). The hero levels hold the last few hundred metres around a
    hero_block: null,            // camera: at their cells a season moves a big dune's body by metres, so the whole
    hero_average_iters: null,    // regime there re-cuts the crests (each arm's brink and slip face from the last
    hero_smooth_cells: null,     // wind that crossed it) and grows the small dunes on the flanks (refine)
    pin_band: 16,                // the border band pinned to the parent, cells
    steer_wavelength_m: null,    // the steering's wavelength (null: 2.5 x the spacing; steer_deg turns it on)
    sheet_smooth_cells: 0.0,     // > 0: sand thinner than the speed-up's start smoothed by this many cells (smoothSheet)
    sheet_top_m: null,           // the thickness smoothSheet calls a sheet (null: the speed-up's start, speed_from_m)
    average_iters: 0,            // > 0: each run's sand is its mean over its last this many iterations ...
    average_every: 10,           // ... read every this many (SandSim.runAveraged): the speckle goes, the crests stay
});
export const HEIGHT_RATIO = Object.freeze({ star: 0.25, linear: 0.06, transverse: 0.06, barchan: 0.08 });

const CURRENT = { plan: null };
const TILES = new WeakMap();                            // runner -> Map(tile key -> grown tile)
const RUNNERS = new Set();                              // the runners whose tiles TILES may hold (clearTiles walks them)

function tilesOf(R) {
    let m = TILES.get(R);
    if (!m) {
        m = new Map();
        TILES.set(R, m);
    }
    return m;
}

/** Empty the per-process memo of grown tiles (every runner's, or one runner's), releasing its fields: the chaos
 * floor's protocol clears every solver memo before a sample (PORT_PLAN.md 5.4). */
export function clearTiles(R = null) {
    const clear = (m) => {
        for (const t of m.values()) {
            if (!t.bed.destroyed) t.bed.destroy();
            if (!t.sand.destroyed) t.sand.destroy();
        }
        m.clear();
    };
    if (R) {
        const m = TILES.get(R);
        if (m) clear(m);
        return;
    }
    // a WeakMap cannot be walked: the runners this module has used are kept in a set for this
    for (const r of RUNNERS) {
        const m = TILES.get(r);
        if (m) clear(m);
    }
}

/** The dunes recipe's prepare hook: remember the level stack, so each level's op finds the growth level. */
export function prepare(values, plan) {
    CURRENT.plan = [...plan];
}

/** The dune field's parameters: FIELD_DEFAULTS and the slab model's DEFAULTS, the kind's winds, sand and spacing
 * filled in where null, the derived seed amplitude and noise wavelengths. Raises on an unknown kind. */
export function resolveParams(params = null) {
    const p = { ...DEFAULTS, ...FIELD_DEFAULTS };
    for (const [k, v] of Object.entries(params ?? {})) {
        if ((v !== null && v !== undefined) || !(k in p)) p[k] = v ?? null;
    }
    const kind = or(p.kind, 'star');
    if (!Object.prototype.hasOwnProperty.call(KINDS, kind)) {
        const near = closeMatches(String(kind), Object.keys(KINDS), 2);
        throw new KeyError(`dune kind ${pyReprValue(kind)}` + (near.length ? `; did you mean ${pyReprValue(near)}?` :
            `; one of ${pyReprValue(Object.keys(KINDS))}`));
    }
    const K = KINDS[kind];
    const given = new Set(Object.entries(params ?? {}).filter(([, v]) => v !== null && v !== undefined).map(([k]) => k));
    for (const [k, v] of Object.entries(K.model ?? {})) if (!given.has(k)) p[k] = v;
    if (truthy(p.patchiness)) p.supply_var = Number(p.patchiness);
    const winds = truthy(p.winds) ? p.winds : K.winds;
    const rot = Number(or(p.wind_rotate_deg, 0.0));
    p.winds = normaliseWinds(winds).map(([d, w]) => [pyMod(d + rot, 360.0), w]);
    p.supply_axis_deg = pyMod(Number(or(p.supply_axis_deg, 0.0)) + rot, 180.0);
    p.sand_m = Number(truthy(p.sand_m) ? p.sand_m : K.sand_m);
    p.spacing_m = Number(truthy(p.spacing_m) ? p.spacing_m : K.spacing_m);
    p.bed_m = Number(truthy(p.bed_m) ? p.bed_m : (K.bed_m ?? 6.0));
    const ratio = Number(truthy(p.height_ratio) ? p.height_ratio : HEIGHT_RATIO[kind]);
    const targetH = ratio * p.spacing_m;
    p.target_height_m = targetH;
    // the seed: a share of the target height, but no more than the sand there is can heap
    p.seed_m = Number(or(p.seed_m, p.seed_frac * Math.min(targetH, 3.0 * p.sand_m)));
    // the speed-up grows over the dune's height: by default from a quarter of the target height to twice it
    if (!truthy((params ?? {}).speed_from_m)) p.speed_from_m = Number(p.speed_from_frac) * targetH;
    if (!truthy((params ?? {}).speed_ref_m)) p.speed_ref_m = Math.max(Number(p.speed_ref_frac) * targetH, p.speed_from_m + 1e-3);
    if (!truthy(p.supply_wavelength_m)) p.supply_wavelength_m = 6.0 * p.spacing_m;
    if (!truthy(p.bed_wavelength_m)) p.bed_wavelength_m = 5.0 * p.spacing_m;
    return p;
}

/** [plan, index]: the stack prepare() recorded when it holds this level's window at the level's index, else the
 * level alone (a standalone run: it is its own growth level). */
function planHolding(level) {
    const plan = CURRENT.plan;
    if (plan && plan.length) {
        const i = pyInt(level.index ?? -1);
        if (i >= 0 && i < plan.length) {
            const q = plan[i];
            const same = ['x0', 'y0', 'cell'].every((a) => Math.abs(Number(q[a]) - Number(level[a])) <=
                1e-6 * Math.max(1.0, Math.abs(Number(q[a]))));
            if (same && pyInt(q.n) === pyInt(level.n)) return [plan, i];
        }
    }
    return [[level], 0];
}

/** The growth level: the coarsest context or main level whose cell resolves the spacing with cellsPerSpacing
 * cells (the main level, with a warning, when none does). */
export function growthIndex(plan, spacingM, cellsPerSpacing, warn = null) {
    for (let i = 0; i < plan.length; i++) {
        const lv = plan[i];
        if ((lv.role === 'context' || lv.role === 'main') && spacingM / lv.cell >= cellsPerSpacing * (1 - 1e-9)) return i;
    }
    const main = [];
    plan.forEach((lv, i) => { if (lv.role === 'main') main.push(i); });
    const i = main.length ? main[0] : plan.length - 1;
    if (warn) {
        warn(`no level resolves a ${pyFormat(spacingM, 'g')} m dune spacing with ${pyFormat(cellsPerSpacing, 'g')} cells; growing on ` +
            `${plan[i]} (${pyFormat(spacingM / plan[i].cell, '.1f')} cells per spacing)`);
    }
    return i;
}

function tileKey(lv, p, seed) {
    const keep = {};
    for (const [k, v] of Object.entries(p)) if (!k.startsWith('refine_') && !k.startsWith('hero_') && k !== 'pin_band') keep[k] = v;
    const blob = Ch.sortedJson(Ch.plain({ w: [lv.x0, lv.y0, lv.cell, lv.n], p: keep, seed: pyInt(seed) }));
    return createHash('sha1').update(blob).digest('hex');
}

/** The dune field grown on level lv's window, periodic over it (memoised per process and runner): { bed, sand (r32f
 * fields, the memo's: copy them), iters, spacing_m, slip_frac, seconds, history }. The last growth phase reads its
 * sand time-averaged when p.average_iters is set (SandSim.runAveraged), then the light Gaussian of smooth_cells. */
export async function growTile(R, lv, p, seed, log = null) {
    RUNNERS.add(R);
    const memo = tilesOf(R);
    const key = tileKey(lv, p, seed);
    if (memo.has(key)) return memo.get(key);
    const t0 = now();
    const target = Number(p.spacing_m);
    const start = await startFields(R, lv, p, seed, lv.side);
    const steer = steeringFor(R, lv, p, seed, lv.side);
    const sim = new SandSim(start.bed, start.sand, lv.cell, { bound: BOUND_PERIODIC, params: p, seed: pyInt(seed) * 131 + 7, steer });
    start.bed.destroy();
    start.sand.destroy();
    const hist = [];
    const P = prims(R);

    const check = async (s, done) => {
        const { bed: b, sand: sd } = s.fields();
        const hh = Gd.arith(R, 'add', b, sd);
        const sp = await spacingPeak(hh, lv.cell), sf = await slipFraction(hh, lv.cell, Number(p.repose_deg));
        const tall = await duneHeight(sd);
        const st = await P.stats(hh);
        hist.push({ iters: done, spacing_m: Number(pyFormat(sp, '.1f')), slip_frac: Number(pyFormat(sf, '.5f')),
            dune_height_m: Number(pyFormat(tall, '.2f')), relief_m: Number(pyFormat(Math.fround(st.max - st.min), '.2f')) });
        b.destroy();
        sd.destroy();
        hh.destroy();
        if (log) {
            log(`${LOG_PREFIX}   growth ${done} it: dunes ${pyFormat(tall, '.0f')} m (target ${pyFormat(p.target_height_m, '.0f')}), spacing ` +
                `${pyFormat(sp, '.0f')} m (target ${pyFormat(target, 'g')}), slip faces ${pyFormat(100 * sf, '.2f')} %`);
        }
        return done >= pyInt(p.grow_min_iters) && tall >= Number(p.height_reached) * p.target_height_m &&
            sf >= Number(p.slip_reached);
    };
    const phases = truthy(p.grow_phases) ? p.grow_phases : [[pyInt(p.grow_iters), {}]];   // [[iterations, {model overrides}], ...]
    const avg = pyInt(or(p.average_iters, 0));
    let iters = 0, bed = null, sand = null;
    for (let k = 0; k < phases.length; k++) {
        const [nIt, over] = phases[k];
        sim.setParams(over ?? {});
        if (avg && k === phases.length - 1) {
            const [d, b, s] = await sim.runAveraged(p.winds, pyInt(nIt), avg, pyInt(or(p.average_every, 10)), check,
                pyInt(p.grow_check));
            iters += d;
            bed = b;
            sand = s;
        } else {
            iters += await sim.run(p.winds, pyInt(nIt), { callback: check, every: pyInt(p.grow_check) });
        }
    }
    if (sand === null) ({ bed, sand } = sim.fields());
    sim.dispose();
    steer?.dispose();
    const dn = denoise(sand, Number(p.smooth_cells), { periodic: true });
    sand.destroy();
    sand = smoothSheet(dn, p, { periodic: true });
    dn.destroy();
    const h = Gd.arith(R, 'add', bed, sand);
    const out = { bed, sand, iters, spacing_m: await spacingPeak(h, lv.cell),
        slip_frac: await slipFraction(h, lv.cell, Number(p.repose_deg)), seconds: round2(now() - t0), history: hist };
    h.destroy();
    if (memo.size >= 4) clearTiles(R);
    memo.set(key, out);
    if (log) {
        log(`${LOG_PREFIX} grew the dune field on ${lv}: ${iters} iterations, spacing ${pyFormat(out.spacing_m, '.0f')} m ` +
            `(target ${pyFormat(target, 'g')}), slip faces ${pyFormat(100 * out.slip_frac, '.2f')} % of cells, ${pyStr(out.seconds)} s`);
    }
    return out;
}

/** A periodic field on level `src`'s window, averaged over the (coarser, nested) cells of level lv: lv's cell must be
 * a power-of-two multiple of src's and its window on src's grid lines (planLevels makes them so). A new r32f field. */
export function samplePeriodic(a, src, lv) {
    const r = lv.cell / src.cell;
    const m = pyRound(r);
    if (Math.abs(r - m) > 1e-6 || m < 1 || (m & (m - 1))) throw new ValueError(`${lv} is not a power-of-two coarsening of ${src}`);
    const i0 = (lv.x0 - src.x0) / src.cell;
    const j0 = (lv.y0 - src.y0) / src.cell;
    if (Math.abs(i0 - pyRound(i0)) > 1e-6 || Math.abs(j0 - pyRound(j0)) > 1e-6) throw new ValueError(`${lv} is not on the grid lines of ${src}`);
    const R = a.runner;
    const n = src.n;
    const out = R.field(lv.n, lv.n, 1);
    R.run(kern(R, 'sample'), { src: a }, { outF: out }, { uI0: pyMod(pyRound(i0), n), uJ0: pyMod(pyRound(j0), n), uM: m });
    return out;
}

/** The winds a level finer than the growth level blows: the whole regime ('cycle'), its last wind alone ('last',
 * the season the growth run ended on), or its last two in turn ('last2'); mode null: p.refine_winds. The big dunes
 * are the whole regime's work, grown on the growth level; a finer level adds what its cells can draw. On the main
 * level a whole cycle re-planes every big dune into the faces of its winds (a star dune into a pyramid of
 * straight-edged facets), so there the latest season alone shows (fresh slip faces and brinks on the dunes the
 * regime built). On the hero levels two seasons in short turns reverse the crest zone: each builds its slip face on
 * its own lee and cuts back the other's, so a crest stands steep on both sides above the broad flanks, the
 * knife-edge arm of a star dune, where one season leaves a sharp brink over a gentle stoss. */
export function refineWinds(p, mode = null) {
    mode = or(mode, or(p.refine_winds, 'cycle'));
    if (mode === 'last') return [normaliseWinds(p.winds).slice(-1)[0]];
    if (mode === 'last2') return normaliseWinds(p.winds).slice(-2);
    return p.winds;
}

/** A refinement level's run: { winds, iters, block, average_iters, smooth_cells }. Hero levels take the hero_*
 * values where given; every level falls back on the refine_* values, then on the growth run's own (block,
 * average_iters, smooth_cells). */
export function refineSettings(p, lv) {
    const hero = (lv.role ?? '') === 'hero';
    const pick = (name, fallback) => {
        let v = hero ? (p['hero_' + name] ?? null) : null;
        if (v === null) v = p['refine_' + name] ?? null;
        return v === null ? fallback : v;
    };
    return { winds: refineWinds(p, pick('winds', p.refine_winds ?? null)), iters: pyInt(pick('iters', 1200)),
        block: pyInt(pick('block', p.block)), average_iters: pyInt(pick('average_iters', or(p.average_iters, 0))),
        smooth_cells: Number(pick('smooth_cells', p.smooth_cells)) };
}

// bed and sand of a level's fields as refine and op_aeolian start from them: bed = min(bed or h - sand or h, h),
// sand = max(h - bed, 0); new r32f fields
function levelStart(fields) {
    const R = fields.R, D = Gd.dummies(R);
    const h = fields.h;
    const mode = 'bed' in fields ? 0 : ('sand' in fields ? 1 : 2);
    const b = mode === 0 ? fields.bed : (mode === 1 ? fields.sand : D.f1);
    const bed = R.like(h), sand = R.like(h);
    R.run(kern(R, 'refine_start'), { h, b }, { outBed: bed, outSand: sand }, { uMode: mode });
    return { bed, sand };
}

/** Run the slab model on one level from its current fields (h and bed; sand = h - bed), its border band pinned to
 * that start (a child level is pinned to its parent), as refineSettings(p, lv) says. Writes bed, sand and h. */
export async function refine(fields, lv, p, seed, log = null) {
    const t0 = now();
    const R = fields.R;
    const { bed, sand } = levelStart(fields);
    const rs = refineSettings(p, lv);
    const q = { ...p, block: rs.block };
    if (truthy(p.refine_hop_cells)) q.hop_cells = Number(p.refine_hop_cells);
    const w = Gd.borderRamp(R, lv.n, pyInt(p.pin_band), 'smooth');
    const steer = steeringFor(R, lv, q, seed, p.growth_period_m ?? null);
    const sim = new SandSim(bed, sand, lv.cell, { bound: BOUND_PINNED, params: q, seed: pyInt(seed) * 131 + 11 + 977 * pyInt(lv.index),
        pinW: w, pinSand: sand, steer });
    let iters, bed2, sand2;
    if (rs.average_iters) {
        [iters, bed2, sand2] = await sim.runAveraged(rs.winds, rs.iters, rs.average_iters, pyInt(or(q.average_every, 10)));
    } else {
        iters = await sim.run(rs.winds, rs.iters);
        ({ bed: bed2, sand: sand2 } = sim.fields());
    }
    sim.dispose();
    steer?.dispose();
    const dn = denoise(sand2, rs.smooth_cells, { periodic: false, pinW: w, pinSand: sand });
    sand2.destroy();
    const sm = smoothSheet(dn, q, { periodic: false, pinW: w, pinSand: sand });
    dn.destroy();
    w.destroy();
    bed.destroy();
    sand.destroy();
    fields.bed = bed2;
    fields.sand = sm;
    fields.h = Gd.arith(R, 'add', bed2, sm);
    if (log) {
        log(`${LOG_PREFIX} refined ${lv}: ${iters} iterations (${rs.winds.length} winds, blocks of ${rs.block}), ` +
            `${pyFormat(now() - t0, '.2f')} s`);
    }
    return iters;
}

const defaultLog = (m) => console.log(m);

/** Stage op 'dune_field': the dune field on one level of the stack (module doc). Levels coarser than the growth
 * level average the grown field, the growth level is the grown field, finer levels refine their inherited surface.
 * Writes h, bed and sand. */
export async function opDuneField(fields, level, params, seed = 0, log = defaultLog) {
    if (typeof log !== 'function') log = defaultLog;
    const R = fields.R;
    const p = resolveParams(params);
    const [plan, i] = planHolding(level);
    const g = growthIndex(plan, p.spacing_m, Number(p.cells_per_spacing), (m) => log(`${LOG_PREFIX} ${m}`));
    p.growth_period_m = Number(plan[g].side);           // the steering is periodic over the growth window everywhere
    if (i <= g) {
        const src = plan[g];
        const tile = await growTile(R, src, p, seed, log);
        let bed, sand;
        if (i === g) {
            bed = copyOf(tile.bed);
            sand = copyOf(tile.sand);
        } else {
            bed = samplePeriodic(tile.bed, src, level);
            sand = samplePeriodic(tile.sand, src, level);
        }
        fields.bed = bed;
        fields.sand = sand;
        fields.h = Gd.arith(R, 'add', bed, sand);
        return fields;
    }
    if (!('h' in fields)) {
        throw new ValueError(`dune_field on ${level}: a level finer than the growth level starts from its parent ` +
            '(the level runner inherits h and bed); this one has no h');
    }
    await refine(fields, level, p, seed, log);
    return fields;
}

/** Stage op 'aeolian': the slab model on one level's own surface (h and bed, or h and sand), for recipes that blow
 * sand over ground another stage made. params: the slab model's (DEFAULTS), winds or kind, iterations, periodic
 * (false: the border band pinned to the start). */
export async function opAeolian(fields, level, params, seed = 0, log = defaultLog) {
    if (typeof log !== 'function') log = defaultLog;
    const R = fields.R;
    const p = resolveParams(params);
    const t0 = now();
    const { bed, sand } = levelStart(fields);
    const periodic = Boolean(p.periodic ?? false);
    const w = periodic ? null : Gd.borderRamp(R, level.n, pyInt(p.pin_band), 'smooth');
    const steer = steeringFor(R, level, p, seed, periodic ? level.side : null);
    const sim = new SandSim(bed, sand, level.cell, { bound: periodic ? BOUND_PERIODIC : BOUND_PINNED, params: p,
        seed: pyInt(seed) * 131 + 5 + 977 * pyInt(level.index ?? 0), pinW: w, pinSand: sand, steer });
    const iters = await sim.run(p.winds, pyInt('iterations' in p ? p.iterations : p.refine_iters));
    const { bed: b, sand: s0 } = sim.fields();
    sim.dispose();
    steer?.dispose();
    const s = denoise(s0, Number(p.smooth_cells), { periodic, pinW: w, pinSand: sand });
    s0.destroy();
    w?.destroy();
    bed.destroy();
    sand.destroy();
    fields.bed = b;
    fields.sand = s;
    fields.h = Gd.arith(R, 'add', b, s);
    log(`${LOG_PREFIX} aeolian on ${level}: ${iters} iterations, ${pyFormat(now() - t0, '.2f')} s`);
    return fields;
}

export const OPS = { dune_field: opDuneField, aeolian: opAeolian };

export {
    paramsFor as params_for, transportDir as transport_dir, normaliseWinds as normalise_winds, cycleBlocks as cycle_blocks,
    scheduleLength as schedule_length, hopBox as hop_box, uniformsFor as uniforms_for, checkGrid as check_grid,
    smoothSheet as smooth_sheet, spacingPeak as spacing_peak, duneHeight as dune_height, slipFraction as slip_fraction,
    steeringFor as steering_for, stretchPeriodic as stretch_periodic, startFields as start_fields,
    resolveParams as resolve_params, growthIndex as growth_index, growTile as grow_tile, samplePeriodic as sample_periodic,
    refineWinds as refine_winds, refineSettings as refine_settings, opDuneField as op_dune_field, opAeolian as op_aeolian,
    clearTiles as clear_tiles,
};
