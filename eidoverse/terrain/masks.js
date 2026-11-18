// Port of blender/eidoblend/terrain/masks.py at f90c6fc.
//
// Terrain masks (design section 6): the arrays the material, the rock scatter, the flora and the scene script read
// off a finished terrain, one set per level.
//
//     import * as M from './masks.js';
//     const stack = await M.computeStack(levelFields, levels);    // every level: a Masks {name: Float32Array (ny, nx)},
//                                                                 // each level padded from its parents, normalised by
//                                                                 // the main level, its border band pinned to its
//                                                                 // parent's masks
//     const m = await M.compute(fields, { cell, x0, y0 });        // one level on its own (a DEM, a test): GPU fields
//     M.MASKS.slope                                               // each mask's unit and meaning; M.attributeName('slope')
//
// Units are the design's (section 2.1): metres, degrees, m^2. Every mask is defined in them, never in cells or tile
// fractions, so a mask means the same on every level and at any resolution (the tests hold each to that on fields
// resampled 2 x). Two kinds are level-of-detail on purpose and say so: the signed curvatures and convex / concave
// without a scale suffix are measured at 2 x the level's cell (each level's own finest bends), and `channels`' default
// threshold area shrinks with the cell (rivers on the main level, rills on the hero levels). In a stack every child's
// outer 16 cells are pinned to its parent's masks (pinBand, as the runner pins its heights), so even those meet the
// ring next to them exactly.
//
// Frames: arrays are [row j, column i], row 0 the south edge, cell centres at x0 + (i + 0.5) cell, y0 + (j + 0.5) cell
// (Blender's frame: PORT_PLAN.md 2.2; the scene-facing Mask.at of api.js converts).
//
// Inputs: `fields` is a mapping of one level's GPU fields (core/fields.js Fields, or a plain object of core/gpu.js
// fields of one float channel); only `h` is required.
//     h        surface height, metres above base; altitude = h + base_elevation_m (the snowline and treeline use it)
//     A        converged drainage area, m^2 (the route pass to convergence): flow, channels, wetness, vegetation
//     wear, deposit, talus, sand, lava, water   the processes' accumulated outputs, passed through (metres; lava as its
//              solver writes it). A mask whose input is absent is skipped and Masks.skipped says why; the material
//              reads a missing mask as 0, which is what an absent process means.
//     zs       stratigraphic height, metres (or params.strata, from which it is computed with the design's formula)
//
// How each mask is made is masks.py's module doc, unchanged: slope and aspect by central differences of the padded
// height; curvature on the height Gaussian-smoothed with sigma = scale on the window padded by 4 sigma of its parents'
// terrain (box-averaged to sigma / 3 cells when sigma is wide), profile = -d2h/ds2 and plan = -d2h/dn2, convex /
// concave = smoothstep(bend) of (profile + plan) x scale; peaks: Ekigar's "high AND convex" in metres (Wilson &
// Gallant's DEV at peaks_scales_m); flow and wetness from the specific catchment area a = A / cell (Beven & Kirkby's
// ln(a / tan slope)); occlusion the sky-view factor within occlusion_radius_m over 16 azimuths (Zaksek et al. 2011),
// the first 6 cells at full resolution and the rest over the window box-averaged by 2 or more; rock, rock_toe, snow,
// vegetation smoothstep rules in metres and degrees (MaskParams), rock_toe by the rockfall shadow angle (Evans &
// Hungr 1993) from the foot of each rock face (rockBase).
//
// Where this differs from masks.py, and why (each checked against masks.py itself, tests/masks/):
//   - Every per-cell step is a GPU kernel (kernels/masks/, PORT_PLAN.md 3.2): the padding and the parents' terrain
//     beyond a window, the box averages, the gradient, the curvatures, the marches, every smoothstep rule, the norms'
//     wetness index, the border pin. Kernels are float32; where numpy computes in float64 and rounds to float32 once,
//     the kernels evaluate in an order that keeps the digits that matter: a padded value is a pair (a tap, an offset
//     from it), so the central difference across a level's edge is numpy's own to an ulp of the slope; StackSampler's
//     Catmull-Rom and bilinear sums run over differences from the tap at the point's cell; a box average sums
//     differences from the block's first cell. The tables those kernels read (per padded row and column: the parent's
//     tap index and weights; per kept row and column: to_kept's index and fraction; per azimuth: the march's shifts
//     and 1 / distance) are numpy's float64 numbers, computed in JavaScript doubles as numpy computes them (Python's
//     round() and floor division included): a few thousand numbers per level, never a loop over its cells.
//   - gaussianBlur is core/prims.js's (P1): the circular convolution with the FFT's own kernel, summed over
//     differences from the cell's own value, where masks.py multiplies a float32 FFT (numpy 2.3.4 transforms float32
//     data in single precision). Measured on the reference stacks, that FFT's round-off alone moves convex / concave
//     by up to 3e-3 of their range and peaks and snow by up to 1.4e-3, while the curvature itself stays within 1e-4:
//     so tests/masks/ grades every mask against masks.py with its FFT in float64 (within 1e-4 of the range), and
//     against masks.py as it is within that FFT's own spread.
//   - NaN, masks.py's "no terrain" (beyond every level in the occlusion march; not a rock foot in rockShadow), is the
//     sentinel NOH of kernels/masks/lib.wgsl: WGSL lets an implementation assume no NaN reaches a shader, and fmax's
//     NaN skipping is then a comparison with the sentinel. The masks never hold it.
//   - h.mean() (the curvature's and the peaks' centre) is core/prims.js stats' float32 tree sum: both are invariant to
//     the centre but for float32 rounding.
//   - compute is async and returns GPU fields (run.js's `where` evaluates them on the GPU); computeStack reads each
//     level's masks back into Float32Arrays once its child is pinned to them and releases the GPU fields (PORT_PLAN.md
//     4.9: masks are made level by level and read back), unless opts.keep. Masks.seconds are the wall times of
//     recording the work (the GPU runs it asynchronously); 'total' and computeStack's 'border_pin' include the wait.
//   - params.strata.warp, masks.py's callable(x, y) -> metres over numpy arrays, is a callable(X, Y) over GPU fields
//     of the cells' world x and y (it may be async) returning a GPU field or a number: the per-cell work stays on the
//     GPU. MaskParams.toDict() writes it as '<callable>', as masks.py's to_dict does.
//   - rockBase returns a float field of 1 and 0 (numpy's boolean array); StackSampler fills a padded grid's ring on
//     the GPU (fill()) instead of answering arrays of points: what pad_level asks of it.
//   - MaskParams takes masks.py's field names (snake_case: the recipes' mask_params are shared JSON) and refuses an
//     unknown one naming the nearest, as the dataclass refuses an unexpected keyword.

import { KeyError, ValueError, pyFormat, pyRepr, pyReprValue, pyRound } from './core/levels.js';
import { prims } from './core/prims.js';

export const ATTRIBUTE_PREFIX = 'eido_';
export const SCALED = Object.freeze(['curv_profile', 'curv_plan', 'convex', 'concave']);   // the masks that take a scale suffix: convex_20m
export const PASS_THROUGH = Object.freeze(['wear', 'deposit', 'talus', 'sand', 'lava']);

// name -> [unit, what it is]. The material reads every one (the last wave: per-level data textures; meshMasks, a
// debug option of api.js, as the FLOAT point attribute eido_<name>).
export const MASKS = Object.freeze({
    height: ['m', 'height above base (the h field); altitude = height + base_elevation_m'],
    height_norm: ['0-1', 'height normalised over the main tile (0 its lowest cell, 1 its highest), clipped'],
    slope: ['deg', 'slope, central differences on the final surface, never clipped'],
    aspect: ['deg', 'compass bearing the slope faces (0 north-facing, 90 east); 0 on flats. Interpolating it across ' +
        'a triangle tears at north: materials read northness / eastness'],
    northness: ['-1..1', 'cos(aspect), faded to 0 on ground under 3 degrees: north-facing +1'],
    eastness: ['-1..1', 'sin(aspect), faded to 0 on ground under 3 degrees: east-facing +1'],
    curv_profile: ['1/m', 'profile curvature -d2h/ds2 down the slope at 2 x the level cell (+ convex: shoulders, cliff ' +
        'tops; - concave: foot slopes, cliff feet); curv_profile_<s>m at s metres'],
    curv_plan: ['1/m', 'plan curvature -d2h/dn2 along the contour at 2 x the level cell (+ ridges and spurs, - valleys ' +
        'and hollows); curv_plan_<s>m at s metres'],
    convex: ['0-1', 'convex ground at 2 x the level cell: smoothstep of (profile + plan) x scale; convex_<s>m at s m'],
    concave: ['0-1', 'concave ground at 2 x the level cell; concave_<s>m at s metres'],
    peaks: ['0-1', 'high and convex: summits and ridgelines standing above their surroundings within 150 m by ' +
        'standard deviations and metres, in the upper height band of the main tile'],
    flow: ['0-1', 'log10 of the drainage area per metre of contour (A / cell), normalised over the main tile: on ' +
        'the main level, log10 drainage area normalised'],
    channels: ['0-1', 'drainage area above the level threshold (1 km^2 at cells of 7.6 m and coarser, down to ' +
        '1,000 m^2 at 0.5 m: rills), fading in from a fifth of it'],
    wetness: ['0-1', 'topographic wetness ln(a / tan slope) normalised over the main tile; 1 on water'],
    wear: ['m', 'eroded depth (fresh rock)'],
    deposit: ['m', 'sediment thickness'],
    talus: ['m', 'talus thickness'],
    sand: ['m', 'sand thickness'],
    lava: ['as written', 'lava-flow footprint, with age, as the volcanic solver writes it'],
    water: ['m', 'lake or sea depth'],
    rock: ['0-1', 'exposed rock: slope above the rock angle, or deep wear with a thin cover; not under loose cover ' +
        'or water'],
    rock_toe: ['0-1', 'the ground below exposed rock where fallen rock gathers: the foot of a rock face within ' +
        '300 m stands above it at 25-33 degrees or steeper (the rockfall shadow angle); concave feet ' +
        'highest'],
    snow: ['0-1', 'altitude above the snowline (north faces and hollows hold it lower, ridges shed it), on slopes ' +
        'under 45 degrees'],
    strata: ['m', 'stratigraphic height zs: the material reads its rock column at it'],
    occlusion: ['0-1', 'sky-view factor within occlusion_radius_m: 1 open sky, lower in valleys and gorges'],
    vegetation: ['0-1', 'suitability for plants from moisture, slope, altitude band, aspect, light, and bare ' +
        'ground (rock, snow, water, sand, scree): a density for the flora family'],
});
export const DEFAULT_NAMES = Object.freeze(['height', 'height_norm', 'slope', 'aspect', 'northness', 'eastness',
    'curv_profile', 'curv_plan', 'convex', 'concave',
    'curv_profile_20m', 'curv_plan_20m', 'convex_20m', 'concave_20m',
    'peaks', 'flow', 'channels', 'wetness', 'wear', 'deposit', 'talus', 'sand', 'lava', 'water',
    'rock', 'rock_toe', 'snow', 'strata', 'occlusion', 'vegetation']);

/** The mesh point attribute of a mask: eido_<name>. */
export function attributeName(name) {
    return ATTRIBUTE_PREFIX + name;
}

const now = () => performance.now() / 1000;
const f32 = Math.fround;
const isField = (v) => v !== null && typeof v === 'object' && typeof v.h === 'number' && typeof v.w === 'number' &&
    v.runner !== undefined && v.buffer !== undefined;
const clone = (v) => (Array.isArray(v) ? v.map(clone) : (v && typeof v === 'object' && !isField(v) && typeof v !== 'function'
    ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, clone(x)])) : v));


// ---------------------------------------------------------------------------------------------- parameters ---

// masks.py MaskParams' fields and defaults, in its order (pairs are smoothstep edges (from, to))
const PARAM_DEFAULTS = Object.freeze({
    base_elevation_m: 0.0,              // altitude = h + base_elevation_m
    sea_level: null,                    // in h's frame: cells at or below it are sea when there is no water field
    wrap: [false, false],               // periodic level along x, y (dune tiles)
    // curvature
    curvature_scales_m: [null, 20.0],   // the default curvature masks: null = 2 x the level cell
    bend: [0.03, 0.30],                 // convex / concave over (profile + plan) x scale
    flat_slope_deg: 1.0,                // under it profile and plan curvature share the Laplacian
    // peaks
    peaks_scales_m: [150.0],            // crests, ridgelines and summits (a volcano recipe may add 600 m)
    peaks_dev: [0.3, 1.3],              // the deviation from the local mean, in local standard deviations
    peaks_rise: [0.05, 0.2],            // and the height above that mean, as a fraction of the scale
    peaks_height_norm: [0.2, 0.5],      // and the main tile's normalised height
    peaks_std_floor_m: 2.0,
    // drainage
    channel_area_m2: null,              // null: channelAreaForCell(level cell)
    // occlusion
    occlusion_radius_m: 500.0,
    occlusion_directions: 16,
    occlusion_step_ratio: 1.4,          // march distances: radius, radius / 1.4, ... down to one cell
    // rock and its foot
    rock_deg: [34.0, 46.0],
    rock_wear_m: [2.0, 20.0],
    cover_m: [0.1, 1.0],                // deposit + talus + sand that hides the rock
    rock_toe_reach_m: 300.0,            // how far from exposed rock its fall can reach
    rock_toe_shadow_deg: [25.0, 33.0],  // the rock above at this angle or steeper: inside the rockfall shadow
    rock_toe_directions: 12,
    // snow
    snowline_m: null,                   // altitude; null: no snow mask
    snow_band_m: 150.0,                 // half-width of the snowline's fade
    snow_aspect_m: 200.0,               // north faces hold snow this much lower (southern hemisphere: negative)
    snow_concave_m: 150.0,              // hollows hold it this much lower, convex ridges this much higher
    snow_slope_deg: [40.0, 50.0],
    // vegetation
    treeline_m: null,                   // altitude; null: no altitude limit
    treeline_band_m: 120.0,
    alpine_density: 0.3,                // above the treeline: alpine grass and dwarf shrubs, not bare ground
    veg_slope_deg: [32.0, 48.0],
    sand_swallows_m: [0.5, 3.0],        // sand this thick takes the runoff in: no channels on it
    // strata: { dip_deg, azimuth_deg (counter-clockwise from +x, the design's x cos az + y sin az), warp: callable(X, Y)
    // over GPU fields -> a GPU field or metres, or null }
    strata: null,
});

/** Every threshold of the masks, in metres, degrees and m^2 (masks.py MaskParams; its field names). */
export class MaskParams {
    constructor(opts = {}) {
        opts = opts ?? {};
        const known = Object.keys(PARAM_DEFAULTS);
        for (const k of Object.keys(opts)) {
            if (!known.includes(k)) {
                const near = nearest(k, known);
                throw new TypeError(`MaskParams.__init__() got an unexpected keyword argument ${pyReprValue(k)}; nearest: ${near.join(', ')}`);
            }
        }
        for (const [k, v] of Object.entries(PARAM_DEFAULTS)) this[k] = clone(opts[k] !== undefined ? opts[k] : v);
    }

    /** dataclasses.asdict(), with a callable strata warp written as '<callable>'. */
    toDict() {
        const d = {};
        for (const k of Object.keys(PARAM_DEFAULTS)) d[k] = clone(this[k]);
        if (d.strata && typeof this.strata?.warp === 'function') d.strata = { ...d.strata, warp: '<callable>' };
        return d;
    }
}
MaskParams.prototype.to_dict = MaskParams.prototype.toDict;

function asParams(p) {
    if (p == null) return new MaskParams();
    return p instanceof MaskParams ? p : new MaskParams(p);
}

/** The normalisations the main tile sets for every level (so a normalised mask means the same everywhere). */
export class Norms {
    constructor({ cell_m, h_lo, h_hi, flow_lo = 0.0, flow_hi = 1.0, twi_lo = 0.0, twi_hi = 1.0 }) {
        this.cell_m = cell_m;           // the main level's cell
        this.h_lo = h_lo;
        this.h_hi = h_hi;
        this.flow_lo = flow_lo;         // log10 metres of specific catchment area: a divide cell of the main level
        this.flow_hi = flow_hi;         // the largest on the main tile
        this.twi_lo = twi_lo;
        this.twi_hi = twi_hi;
    }
}

function hidden(obj, key, value) {
    Object.defineProperty(obj, key, { value, writable: true, configurable: true, enumerable: false });
}

/** { name: array (ny, nx) } of one level, plus where it is and what was left out. An array is a GPU field (compute)
 * or a Float32Array (computeStack, once read back: toHost()). Only the masks are enumerable: Object.entries(m) lists
 * them (api.js stores them so). */
export class Masks {
    constructor(cell, x0, y0, shape) {
        hidden(this, 'cell', Number(cell));
        hidden(this, 'x0', Number(x0));
        hidden(this, 'y0', Number(y0));
        hidden(this, 'shape', [...shape]);
        hidden(this, 'skipped', {});        // name -> why
        hidden(this, 'seconds', {});        // stage -> seconds (geometry, curvature, occlusion, drainage, ...)
        hidden(this, 'norms', null);
        hidden(this, 'params', null);
    }

    names() { return Object.keys(this); }
    has(name) { return Object.prototype.hasOwnProperty.call(this, name); }
    get(name) { return this.has(name) ? this[name] : undefined; }
    items() { return Object.entries(this); }

    /** [attribute name, array] pairs for the mesh: eido_<name>. */
    attributes() { return Object.entries(this).map(([k, v]) => [attributeName(k), v]); }

    /** Read every GPU mask back into a Float32Array (one wait) and release the GPU fields. */
    async toHost() {
        const keys = Object.keys(this).filter((k) => isField(this[k]));
        if (!keys.length) return this;
        const fields = [...new Set(keys.map((k) => this[k]))];
        const got = await fields[0].runner.readAll(fields);
        const host = new Map(fields.map((f, i) => [f, got[i]]));
        for (const k of keys) this[k] = host.get(this[k]);
        for (const f of fields) f.destroy();
        return this;
    }

    /** Release the GPU fields. */
    dispose() {
        for (const f of new Set(Object.values(this))) if (isField(f) && !f.destroyed) f.destroy();
    }
}


// --------------------------------------------------------------------------------------------- small helpers ---

/** masks.py smoothstep(e0, e1, x) for numbers, in its float32 arithmetic (the kernels' ss() in kernels/masks/lib.wgsl
 * is the same steps per cell). */
export function smoothstep(e0, e1, x) {
    const one = (v) => {
        let t = f32(f32(v) - f32(e0));
        t = f32(t * f32(1.0 / (e1 - e0)));
        t = Math.min(Math.max(t, 0.0), 1.0);
        const u = f32(t * t);
        t = f32(f32(t * -2.0) + 3.0);
        return f32(t * u);
    };
    return Array.isArray(x) ? x.map(one) : one(x);
}

// the (e0, k) pair a kernel's ss() takes: float32(e0) and float32(1 / (e1 - e0)) of the doubles masks.py gives numpy
const ssPair = (e0, e1) => [f32(e0), f32(1.0 / (e1 - e0))];

/** The default channel threshold area of a level, m^2: 1,000 m^2 at 0.5 m cells (rills), growing as cell^2.5 to
 * 1 km^2 at 7.6 m cells and staying there (DESIGN.md section 6: 1 km^2 on the main level, 1,000 m^2 on the hero
 * levels). */
export function channelAreaForCell(cell) {
    return Math.min(Math.max(1000.0 * (cell / 0.5) ** 2.5, 1000.0), 1.0e6);
}

/** '20m' for 20.0, '2p5m' for 2.5: the name suffix of a curvature scale. */
export function scaleSuffix(scaleM) {
    return `${pyFormat(Number(scaleM), 'g').replace('.', 'p')}m`;
}

const SCALED_RE = /^(curv_profile|curv_plan|convex|concave)(?:_(\d+(?:p\d+)?)m)?$/;

/** [base, scale_m or null] of a mask name: ['convex', 20.0] for convex_20m, ['slope', null] for slope. */
export function parseName(name) {
    const m = SCALED_RE.exec(name);
    if (m) return [m[1], m[2] !== undefined ? parseFloat(m[2].replace('p', '.')) : null];
    if (!(name in MASKS)) {
        const near = nearest(name, [...Object.keys(MASKS), ...SCALED.map((b) => `${b}_20m`)]);
        throw new KeyError(`unknown mask ${pyReprValue(name)}; nearest: ${near.join(', ')}`);
    }
    return [name, null];
}

// masks.py _nearest: the k options nearest by edit distance (a stable sort, as Python's sorted)
function nearest(name, options, k = 3) {
    const dist = (a, b) => {
        let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
        for (let i = 1; i <= a.length; i++) {
            const cur = [i];
            for (let j = 1; j <= b.length; j++) {
                cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
            }
            prev = cur;
        }
        return prev[prev.length - 1];
    };
    return options.map((o, i) => [dist(String(name), o), i, o]).sort((p, q) => p[0] - q[0] || p[1] - q[1])
        .slice(0, k).map((t) => t[2]);
}

function lvOf(level, key, dflt = undefined) {
    if (level == null) return dflt;
    const v = level instanceof Map ? level.get(key) : level[key];
    return v === undefined ? dflt : v;
}

function number(v, what) {
    if (v === undefined || v === null || Number.isNaN(Number(v))) {
        throw new TypeError(`${what}: a number is needed (pass it, or give fields a .level that has it)`);
    }
    return Number(v);
}

// Python's float floor division (CPython float_floor_div): a // b of two doubles, as a double
function floorDiv(a, b) {
    let mod = a % b;
    let div = (a - mod) / b;
    if (mod) {
        if ((b < 0) !== (mod < 0)) {
            mod += b;
            div -= 1.0;
        }
    }
    if (div) {
        let fd = Math.floor(div);
        if (div - fd > 0.5) fd += 1.0;
        return fd;
    }
    return 0.0 * Math.sign(a / b);
}

/** masks.py _good_size: the smallest m >= n whose prime factors are 2, 3 and 5 (a fast FFT length). */
export function goodSize(n) {
    for (let m = n; ; m++) {
        let k = m;
        for (const p of [2, 3, 5]) while (k % p === 0) k /= p;
        if (k === 1) return m;
    }
}

/** Gaussian blur (sigma in cells) of a GPU field treated as periodic and extended to a fast FFT length by holding
 * its last row and column (masks.py gaussian_blur): core/prims.js's circular convolution with the FFT's own kernel.
 * The caller pads it (a margin of 4 sigma keeps the wrap-around out of the cells it keeps). A new r32f field. */
export function gaussianBlur(a, sigmaCells) {
    return prims(a.runner).gaussianBlur(a, sigmaCells, { mode: 'periodic', size: 'good' });
}


// ------------------------------------------------------------------------------------------------- dummies ---

const DUMMY = new WeakMap();

// 1 x 1 stand-ins for the bindings a dispatch does not use: one set for samplers, one per image slot (an image is
// written, and a field may not be two images, or a sampler and an image, of one dispatch)
function dummies(R) {
    let d = DUMMY.get(R);
    if (!d) {
        d = { in1: R.field(1, 1, 1), in2: R.field(1, 1, 2), in4: R.field(1, 1, 4), inI: R.field(1, 1, 1, null, 'i32'),
            out: [0, 1, 2, 3].map(() => R.field(1, 1, 1)), out2: R.field(1, 1, 2), out4: R.field(1, 1, 4) };
        DUMMY.set(R, d);
    }
    return d;
}

const cover = (h, w) => [Math.ceil(w / 16), Math.ceil(h / 16), 1];
const fieldOf = (fields, k) => {
    const v = fields instanceof Map ? fields.get(k) : fields[k];
    if (v === undefined || v === null) return null;
    if (!isField(v)) throw new TypeError(`mask input ${pyReprValue(k)}: a GPU field (core/gpu.js) is needed`);
    if (v.channels !== 1 || v.kind !== 'f32') throw new TypeError(`mask input ${pyReprValue(k)}: one float channel is needed, got ${v.format}`);
    return v;
};


// -------------------------------------------------------------------------------------- sampling the stack ---

/** A field at world points from the finest of several levels that holds them: what lies beyond a level's window
 * (its parents' terrain). Points outside every level have none. layers: [{ x0, y0, cell, field }] (or [x0, y0,
 * cell, field]), any order; sorted by cell, finest first, as masks.py sorts them (stable for equal cells).
 * fill() puts the values into a padded grid's ring on the GPU, which is what pad_level asks of masks.py's callable. */
export class StackSampler {
    constructor(layers) {
        this.layers = layers.map((l, i) => (Array.isArray(l) ? { x0: l[0], y0: l[1], cell: l[2], field: l[3], i }
            : { ...l, i })).map((l) => ({ x0: Number(l.x0), y0: Number(l.y0), cell: Number(l.cell), field: l.field, i: l.i }))
            .sort((a, b) => a.cell - b.cell || a.i - b.i);
    }

    // the per-row or per-column table of one layer for a padded axis: index (-1 outside the layer) and weights, from
    // numpy's float64 arithmetic: fx = (x - x0) / c - 0.5 with x = origin + (k - m + 0.5) * cell
    static axisTable(len, m, origin, cell, lo, lc, ln, cubic) {
        const idx = new Int32Array(len), w = new Float32Array(4 * len);
        let any = false;
        for (let k = 0; k < len; k++) {
            const x = origin + ((k - m) + 0.5) * cell;
            const fx = (x - lo) / lc - 0.5;
            if (!(fx >= 0 && fx <= ln - 1)) {
                idx[k] = -1;
                continue;
            }
            any = true;
            if (cubic) {
                const ix = Math.floor(fx), t = fx - ix, t2 = t * t, t3 = t * t * t;
                idx[k] = ix;
                w[4 * k] = (-t3 + 2 * t2 - t) * 0.5;
                w[4 * k + 1] = (3 * t3 - 5 * t2 + 2) * 0.5;
                w[4 * k + 2] = (-3 * t3 + 4 * t2 + t) * 0.5;
                w[4 * k + 3] = (t3 - t2) * 0.5;
            } else {
                const x0 = Math.min(Math.max(Math.floor(fx), 0), ln - 2), t = fx - x0;
                idx[k] = x0;
                w[4 * k] = 1 - t;
                w[4 * k + 1] = t;
            }
        }
        return { idx, w, any };
    }

    /** Fill the ring of padded grid g (margin m around a window of ny x nx cells of `cell` metres from (x0, y0)) with
     * the layers' values (Catmull-Rom, or bilinear with cubic false) where some layer holds the point, finest first.
     * ring: [columns, rows] whether the margin columns / rows are ring (an axis that wraps is not). centre: a number
     * subtracted from every value (the blur's centring). pair: g is rg32f and takes (tap, offset) pairs. */
    fill(g, { m, ny, nx, cell, x0, y0, ring = [true, true], cubic = true, centre = 0.0, pair = false }) {
        const R = g.runner, D = dummies(R);
        const done = R.field(g.h, g.w, 1, null, 'u32');
        const made = [done];
        for (const L of this.layers) {
            const [lny, lnx] = [L.field.h, L.field.w];
            const c = StackSampler.axisTable(g.w, m, x0, cell, L.x0, L.cell, lnx, cubic);
            const r = StackSampler.axisTable(g.h, m, y0, cell, L.y0, L.cell, lny, cubic);
            if (!c.any || !r.any) continue;
            const colI = R.field(1, g.w, 1, c.idx, 'i32'), colW = R.field(1, g.w, 4, c.w);
            const rowI = R.field(1, g.h, 1, r.idx, 'i32'), rowW = R.field(1, g.h, 4, r.w);
            made.push(colI, colW, rowI, rowW);
            R.run('masks/outside', { lay: L.field, colI, colW, rowI, rowW },
                { outS: pair ? D.out[0] : g, outP: pair ? g : D.out2, done },
                { uM: m, uRing: [ring[0] ? 1 : 0, ring[1] ? 1 : 0], uN: [nx, ny], uCubic: cubic ? 1 : 0, uPair: pair ? 1 : 0,
                    uCentre: f32(centre) }, cover(g.h, g.w));
        }
        for (const f of made) f.destroy();
        return g;
    }
}

const PAD_MODES = { odd: 0, nan: 1, edge: 2, wrap: 3 };

/** h (a GPU field) padded by m cells on every side (masks.py pad_level). Along a periodic axis it wraps. Elsewhere
 * the margin holds the parents' terrain from `outside` (a StackSampler) where it has some, and beyond that: 'odd', a
 * linear extrapolation through the edge (2 h[edge] - h[edge + k]: it keeps the edge slope and adds no curvature, so
 * np.gradient's one-sided edge falls out of a central difference); 'nan', no terrain (the occlusion march's open sky:
 * kernels/masks/lib.wgsl NOH); or 'edge', the edge held. opts: x0, y0, wrap, outside, fill, cubic, centre (subtracted
 * from the parents' values: the caller has subtracted it from h), pair (an rg32f grid of (tap, offset) pairs, for the
 * gradient). A new field of (ny + 2m) x (nx + 2m). */
export function padLevel(h, m, cell, opts = {}) {
    const { x0 = 0.0, y0 = 0.0, wrap = [false, false], outside = null, fill = 'odd', cubic = true, centre = 0.0,
        pair = false } = opts;
    if (!(fill in PAD_MODES) || fill === 'wrap') throw new ValueError(`pad_level: fill ${pyReprValue(fill)} is 'odd', 'nan' or 'edge'`);
    const R = h.runner, D = dummies(R);
    const ny = h.h, nx = h.w;
    const g = R.field(ny + 2 * m, nx + 2 * m, pair ? 2 : 1);
    R.run('masks/pad', { src: h }, { outS: pair ? D.out[0] : g, outP: pair ? g : D.out2 },
        { uM: m, uMode: [PAD_MODES[wrap[0] ? 'wrap' : fill], PAD_MODES[wrap[1] ? 'wrap' : fill]], uPair: pair ? 1 : 0 },
        cover(g.h, g.w));
    if (m > 0 && outside && !(wrap[0] && wrap[1])) {
        outside.fill(g, { m, ny, nx, cell, x0, y0, ring: [!wrap[0], !wrap[1]], cubic, centre, pair });
    }
    return g;
}

/** The level window box-averaged by f (f = 1: as is) and padded by mc of those cells with the parents' terrain
 * (sampled at their centres) or `fill` (masks.py window_grid). Coarse cell (J, I) covers the window's cells
 * [(J - mc) f, (J - mc + 1) f); a partial last block holds the window's last row and column. opts as padLevel's
 * (centre: subtracted from h and from the parents' values). A new field. */
export function windowGrid(h, f, mc, cell, opts = {}) {
    const R = h.runner;
    const src = R.field(Math.ceil(h.h / f), Math.ceil(h.w / f), 1);
    R.run('masks/block_mean', { src: h }, { outF: src }, { uF: f, uCentre: f32(opts.centre ?? 0.0) });
    const g = padLevel(src, mc, cell * f, opts);
    src.destroy();
    return g;
}

// to_kept's per-row or per-column table: (floor index, fraction as float32), fy = (j + 0.5) / f - 0.5 + mc
function keptTable(R, n, f, mc) {
    const t = new Float32Array(2 * n);
    for (let j = 0; j < n; j++) {
        const fy = (j + 0.5) / f - 0.5 + mc;
        const y0 = Math.floor(fy);
        t[2 * j] = y0;
        t[2 * j + 1] = fy - y0;
    }
    return R.field(1, n, 2, t);
}

/** A field on a window grid (factor f, margin mc) at the level's own cells: a crop at f = 1, else bilinear
 * (masks.py to_kept). A new r32f field of ny x nx. */
export function toKept(b, f, mc, ny, nx) {
    const R = b.runner, D = dummies(R);
    const out = R.field(ny, nx, 1);
    const ct = f === 1 ? D.in2 : keptTable(R, nx, f, mc), rt = f === 1 ? D.in2 : keptTable(R, ny, f, mc);
    R.run('masks/to_kept', { b, colT: ct, rowT: rt }, { outF: out }, { uF: f, uMc: mc });
    if (f !== 1) {
        ct.destroy();
        rt.destroy();
    }
    return out;
}


// ------------------------------------------------------------------------------------------------ geometry ---

/** (dh/dx, dh/dy) at the kept cells of a padded GPU grid (margin m; an r32f grid or padLevel's rg32f pairs) by
 * central differences (x east = columns, y north = rows), with their hypot and the slope in degrees: one rgba32f
 * field (p, q, g, slope) of ny x nx (masks.py gradient, with compute's hypot and arctan). */
export function gradient(hp, m, ny, nx, cell) {
    const R = hp.runner;
    const geo = R.field(ny, nx, 4);
    R.run('masks/gradient', { hp }, { outG: geo }, { uM: m, uK: f32(0.5 / cell) });
    return geo;
}

/** { prof, plan }: the profile and plan curvature in 1/m of a (smoothed) GPU grid, the same shape (its outer ring
 * copies the next one): -d2h/ds2 down the slope and -d2h/dn2 along the contour (positive = convex); under
 * flatSlopeDeg both take half the Laplacian (masks.py curvatures). */
export function curvatures(hb, cell, flatSlopeDeg = 1.0) {
    const R = hb.runner;
    const prof = R.field(hb.h, hb.w, 1), plan = R.field(hb.h, hb.w, 1);
    R.run('masks/curvatures', { hb }, { outP: prof, outT: plan },
        { uK1: f32(0.5 / cell), uK2: f32(1.0 / (cell * cell)), uKxy: f32(0.25 / (cell * cell)),
            uTan2: f32(Math.tan(flatSlopeDeg * Math.PI / 180.0) ** 2) });
    return { prof, plan };
}

// the distances of a march: radius, radius / ratio, ... down to one cell, ascending (sky_view, rock_shadow)
function marchDistances(radius, cell, ratio) {
    const d = [];
    let x = Number(radius);
    while (x >= cell * 0.999) {
        d.push(x);
        x /= ratio;
    }
    return d.sort((a, b) => a - b);
}

/** The shifts masks.py _march takes at distances `dists` (metres) over a grid of `cell` metres with margin m, per
 * azimuth k of `directions`: [k, di, dj, float32(1 / (hypot(di, dj) cell))], k ascending, in the order _march visits
 * them. A shift is a whole-cell offset round(cos a d / cell), round(sin a d / cell) (Python's round: half to even);
 * one already taken, (0, 0), one beyond the margin, or one whose direction lies more than half a sector off its
 * azimuth is skipped. */
export function marchShifts(dists, cell, m, directions) {
    const out = [];
    const tol = Math.PI / directions + 1e-9;
    const twoPi = 2.0 * Math.PI;
    for (let k = 0; k < directions; k++) {
        const a = 2.0 * Math.PI * k / directions;
        const ca = Math.cos(a), sa = Math.sin(a);
        const seen = new Set();
        for (const d of dists) {
            const di = pyRound(ca * d / cell), dj = pyRound(sa * d / cell);
            const key = `${di},${dj}`;
            if (seen.has(key) || (di === 0 && dj === 0) || Math.max(Math.abs(di), Math.abs(dj)) > m) continue;
            const x = Math.atan2(dj, di) - a + Math.PI;
            const r = ((x % twoPi) + twoPi) % twoPi;                 // Python's % of a float: the divisor's sign
            if (Math.abs(r - Math.PI) > tol) continue;
            seen.add(key);
            out.push([k, di, dj, f32(1.0 / (Math.hypot(di, dj) * cell))]);
        }
    }
    return out;
}

function shiftTable(R, shifts) {
    const t = new Float32Array(4 * Math.max(shifts.length, 1));
    shifts.forEach(([k, di, dj, inv], i) => {
        t[4 * i] = di;
        t[4 * i + 1] = dj;
        t[4 * i + 2] = inv;
        t[4 * i + 3] = k;
    });
    return R.field(1, Math.max(shifts.length, 1), 4, t);
}

// the march over a padded grid src (margin m) of shift table `shifts` from observer heights obs (ny x nx): per
// direction ((dirs x ny) x nx, mode 1) or the largest over all of them (ny x nx, mode 0)
function march(src, obs, shifts, m, dirs, mode) {
    const R = src.runner;
    const out = R.field(mode ? dirs * obs.h : obs.h, obs.w, 1);
    const t = shiftTable(R, shifts);
    R.run('masks/march', { src, obs, shifts: t }, { outB: out },
        { uM: m, uCount: shifts.length, uDirs: dirs, uMode: mode }, cover(obs.h, obs.w));
    t.destroy();
    return out;
}

/** The sky-view factor 1 - mean(sin horizon) of a level (masks.py sky_view): a march along `directions` azimuths at
 * distances radius, radius / ratio, ... down to one cell, over the window padded with its parents' terrain (open
 * sky beyond every level). The first nearCells cells read the level itself (a crevice's own walls); the steps beyond
 * read the window box-averaged by 2 (or by radius / 256 cells when that is more), observer included, and the far
 * horizon is taken per block. A new r32f field. */
export function skyView(h, cell, radiusM, opts = {}) {
    const { x0 = 0.0, y0 = 0.0, wrap = [false, false], outside = null, directions = 16, ratio = 1.4, nearCells = 6 } = opts;
    if (directions > 64) throw new ValueError(`sky_view: at most 64 directions, got ${directions}`);
    const R = h.runner, D = dummies(R);
    const ny = h.h, nx = h.w;
    const dists = marchDistances(radiusM, cell, ratio);
    const mAll = Math.ceil(radiusM / cell) + 1;
    const mNear = Math.min(mAll, nearCells);
    const near = dists.filter((d) => d <= mNear * cell);
    const far = dists.filter((d) => d > mNear * cell);
    let grid = null, m = mNear, shifts = marchShifts(near, cell, mNear, directions);
    let farB = null, f = 0, farH = 1;
    if (far.length) {
        f = Math.max(2, Math.ceil(radiusM / cell / 256.0));
        if (wrap[0]) while (nx % f) f -= 1;
        if (f > 1) {
            const mc = Math.ceil(radiusM / (cell * f)) + 2;
            const g = windowGrid(h, f, mc, cell, { x0, y0, wrap, outside, fill: 'nan', cubic: false });
            const gy = g.h - 2 * mc, gx = g.w - 2 * mc;
            const obs = R.field(gy, gx, 1);
            R.run('masks/block_mean', { src: h }, { outF: obs }, { uF: f, uCentre: 0.0 });
            farB = march(g, obs, marchShifts(far, cell * f, mc, directions), mc, directions, 1);
            farH = gy;
            g.destroy();
            obs.destroy();
        } else {
            // one cell per block: the whole march at full resolution over the window padded by the full radius
            // (its first mNear cells are the near grid's own: the same points, the same layers)
            m = mAll;
            shifts = [...shifts, ...marchShifts(far, cell, mAll, directions)].sort((a, b) => a[0] - b[0]);
        }
    }
    grid = padLevel(h, m, cell, { x0, y0, wrap, outside, fill: 'nan', cubic: false });
    const out = R.field(ny, nx, 1);
    const t = shiftTable(R, shifts);
    R.run('masks/sky_view', { src: grid, obs: h, shifts: t, far: farB ?? D.in1 }, { outF: out },
        { uM: m, uCount: shifts.length, uDirs: directions, uF: farB ? f : 0, uFarH: farH, uInvDirs: f32(-1.0 / directions) });
    for (const x of [grid, t, farB]) x?.destroy();
    return out;
}

/** Exposed rock (rock > 0.5) with a lower neighbour that is not rock: the cliff's foot, where its talus starts
 * (masks.py rock_base). A float field of 1 and 0. */
export function rockBase(h, rock, wrap = [false, false]) {
    const R = h.runner;
    const out = R.field(h.h, h.w, 1);
    R.run('masks/rock_base', { h, rock }, { outZ: out }, { uWrap: [wrap[0] ? 1 : 0, wrap[1] ? 1 : 0], uHeights: 0 });
    return out;
}

/** The steepest tangent from each cell up to the foot of exposed rock (rockBase) within reachM, over `directions`
 * azimuths: the rockfall shadow-angle test (Evans & Hungr 1993: fallen rock stops near a line about 28 degrees from
 * the talus apex, the cliff's foot). The first nearCells cells march at full resolution, the rest over the window
 * box-reduced by 2 (rock feet: the highest in the box; ground: the mean), its maximum over the azimuths upsampled
 * bilinearly. Rock beyond the window is not seen (masks.py rock_shadow). A new r32f field. */
export function rockShadow(h, rock, cell, reachM, opts = {}) {
    const { wrap = [false, false], directions = 12, ratio = 1.4, nearCells = 8 } = opts;
    const R = h.runner;
    const ny = h.h, nx = h.w;
    const zr = R.field(ny, nx, 1);                                   // h on a rock foot, NOH elsewhere
    R.run('masks/rock_base', { h, rock }, { outZ: zr }, { uWrap: [wrap[0] ? 1 : 0, wrap[1] ? 1 : 0], uHeights: 1 });
    const dists = marchDistances(reachM, cell, ratio);
    const mAll = Math.ceil(reachM / cell) + 1;
    const mNear = Math.min(mAll, nearCells);
    const fill = (a, m) => {                                         // wrap or no terrain beyond the window
        const g = R.field(a.h + 2 * m, a.w + 2 * m, 1);
        R.run('masks/pad', { src: a }, { outS: g, outP: dummies(R).out2 },
            { uM: m, uMode: [wrap[0] ? 3 : 1, wrap[1] ? 3 : 1], uPair: 0 }, cover(g.h, g.w));
        return g;
    };
    const zp = fill(zr, mNear);
    let out = march(zp, h, marchShifts(dists.filter((d) => d <= mNear * cell), cell, mNear, directions), mNear, directions, 0);
    zp.destroy();
    const far = dists.filter((d) => d > mNear * cell);
    if (far.length) {
        const f = (wrap[0] && nx % 2) || (wrap[1] && ny % 2) ? 1 : 2;
        const Ny = Math.ceil(ny / f), Nx = Math.ceil(nx / f);
        const zc = R.field(Ny, Nx, 1), hc = R.field(Ny, Nx, 1);
        R.run('masks/shadow_coarse', { zr, h }, { outZ: zc, outH: hc }, { uF: f });
        const mc = Math.ceil(reachM / (cell * f)) + 2;
        const zcp = fill(zc, mc);
        const fm = march(zcp, hc, marchShifts(far, cell * f, mc, directions), mc, directions, 0);
        const fmp = R.field(Ny + 2 * mc, Nx + 2 * mc, 1);           // np.pad(fm, mc, mode='edge')
        R.run('masks/pad', { src: fm }, { outS: fmp, outP: dummies(R).out2 }, { uM: mc, uMode: [2, 2], uPair: 0 },
            cover(fmp.h, fmp.w));
        const up = toKept(fmp, f, mc, ny, nx);
        const both = R.field(ny, nx, 1);
        R.run('masks/fmax', { a: out, b: up }, { outF: both }, {});
        for (const x of [zc, hc, zcp, fm, fmp, up, out]) x.destroy();
        out = both;
    }
    zr.destroy();
    return out;
}


// ------------------------------------------------------------------------------------------- normalisations ---

// masks.py _water_depth's kind: 1 a water field, 2 the sea level, 0 neither
function waterKind(fields, P) {
    if (fieldOf(fields, 'water')) return 1;
    if (P.sea_level !== null && P.sea_level !== undefined) return 2;
    return 0;
}

/** The Norms the main level sets: its height range, the range of log10 specific catchment area from a divide cell
 * (a = cell) to its largest, and its wetness index's 5th-95th percentiles over land (masks.py norms_from). opts:
 * cell (default fields.level.cell), params. Async: it reads a few numbers back. */
export async function normsFrom(fields, opts = {}) {
    const P = asParams(opts.params);
    const cell = number(opts.cell ?? lvOf(fields?.level, 'cell'), 'norms_from: cell');
    const h = fieldOf(fields, 'h');
    if (!h) throw new KeyError("'h'");
    const R = h.runner, Pr = prims(R), D = dummies(R);
    const st = await Pr.stats(h);
    const n = new Norms({ cell_m: cell, h_lo: st.min, h_hi: st.max });
    const A = fieldOf(fields, 'A');
    if (A) {
        const sA = await Pr.stats(A);
        n.flow_lo = Math.log10(cell);
        n.flow_hi = Math.max(Math.log10(Math.max(sA.max, cell * cell) / cell), n.flow_lo + 1.0);
        // _slope_tan: the level alone (no parents), odd padding
        const hp = padLevel(h, 1, cell, { wrap: P.wrap, fill: 'odd', pair: true });
        const geo = gradient(hp, 1, h.h, h.w, cell);
        hp.destroy();
        const wk = waterKind(fields, P);
        const twi = R.field(h.h, h.w, 1), land = R.field(h.h, h.w, 1);
        R.run('masks/norms', { A, geo, h, water: fieldOf(fields, 'water') ?? D.in1 }, { outT: twi, outL: land },
            { uCell: f32(cell), uCell2: f32(cell * cell), uWater: wk, uSea: f32(P.sea_level ?? 0.0) });
        geo.destroy();
        let mask = null;
        if (wk) {
            const cnt = (await Pr.stats(land, { mask: land })).count;   // land.size (twi[wd <= 0])
            if (cnt >= 16) mask = land;
        }
        const [lo, hi] = await Pr.percentile(twi, [5.0, 95.0], { dtype: 'float64', ...(mask ? { mask } : {}) });
        n.twi_lo = lo;
        n.twi_hi = Math.max(hi, lo + 1.0);
        twi.destroy();
        land.destroy();
    }
    return n;
}


// ------------------------------------------------------------------------------------------------ one level ---

const NEEDS = {          // mask -> the masks it is built from (beyond h)
    rock_toe: ['rock', 'concave_20m'],
    snow: ['convex_20m', 'concave_20m'],
    vegetation: ['wetness', 'rock', 'snow', 'occlusion', 'rock_toe'],
    peaks: ['height_norm'],
};

// the requested names with what they are built from added (dependencies that cannot be made are skipped later,
// quietly, unless asked for by name)
function expand(names) {
    const order = [];
    const add = (nm) => {
        if (order.includes(nm)) return;
        const [base] = parseName(nm);
        for (const dep of NEEDS[base] ?? []) add(dep);
        order.push(nm);
    };
    for (const nm of names) add(nm);
    return order;
}

// { scale in metres: [names] } for the curvature masks among names (no suffix = 2 x cell), scales ascending
function scalesWanted(names, cell) {
    const out = new Map();
    for (const nm of names) {
        const [base, scale] = parseName(nm);
        if (SCALED.includes(base)) {
            const s = scale === null ? 2.0 * cell : scale;
            if (!out.has(s)) out.set(s, []);
            out.get(s).push(nm);
        }
    }
    return [...out.entries()].sort((a, b) => a[0] - b[0]);
}

// masks.py _decimation: the box factor for a blur of sigmaCells: 1 up to 6 cells, then sigma / 3 (the blurred field
// keeps 3 or more samples per sigma); on a periodic axis a divisor of n
function decimation(sigmaCells, n, wrapAxis = false) {
    if (sigmaCells <= 6.0) return 1;
    let f = Math.max(2, Math.trunc(floorDiv(sigmaCells, 3)));
    if (wrapAxis) while (n % f) f -= 1;
    return Math.max(f, 1);
}

// masks.py _blurred: { b, f, mc, g }: h - centre smoothed with sigmaM on its window grid (factor f, margin mc)
function blurred(h, sigmaM, cell, x0, y0, wrap, outside, centre) {
    const sc = sigmaM / cell;
    const ny = h.h, nx = h.w;
    const f = (wrap[0] || wrap[1]) ? Math.min(decimation(sc, nx, wrap[0]), decimation(sc, ny, wrap[1])) : decimation(sc, nx);
    const mc = Math.ceil(4.0 * sc / f) + 2;
    const g = windowGrid(h, f, mc, cell, { x0, y0, wrap, outside, fill: 'odd', cubic: true, centre });
    return { b: gaussianBlur(g, sc / f), f, mc, g, sigma: sc / f };
}

/** The masks of one level: a Masks of GPU fields {name: r32f (ny, nx)} (masks.py compute). Async.
 *
 *  fields    a mapping with 'h' (metres) and optionally 'A' (m^2) and the process fields (module doc); core's Fields
 *            carries its level, so cell, x0 and y0 may be left out
 *  opts      cell (the level's cell, metres); x0, y0 (the window's south-west corner in world metres, default 0);
 *            names (default DEFAULT_NAMES; a scaled curvature by suffix: 'concave_200m'); norms (the main level's
 *            Norms, normsFrom; null measures this level as if it were the main one); params (MaskParams);
 *            outside (a StackSampler over its parents; null: the level stands alone, linear extrapolation for the
 *            derivatives and blurs, open sky for the occlusion march); strict (a named mask whose input is absent
 *            throws KeyError when strict, else it is skipped and Masks.skipped says why; default: strict when names
 *            are given) */
export async function compute(fields, opts = {}) {
    const lvl = fields?.level ?? null;
    const cell = number(opts.cell ?? lvOf(lvl, 'cell'), 'masks.compute: cell');
    const x0 = Number(opts.x0 ?? lvOf(lvl, 'x0', 0.0));
    const y0 = Number(opts.y0 ?? lvOf(lvl, 'y0', 0.0));
    const P = asParams(opts.params);
    const outside = opts.outside ?? null;
    const explicit = opts.strict === undefined || opts.strict === null ? (opts.names !== undefined && opts.names !== null)
        : Boolean(opts.strict);
    let names = opts.names ?? null;
    if (names === null) {
        names = [...DEFAULT_NAMES];
        for (const s of P.curvature_scales_m) if (s !== null && s !== 20.0) names.push(...SCALED.map((b) => `${b}_${scaleSuffix(s)}`));
    }
    names = [...names];
    const get = (k) => fieldOf(fields, k);
    const h = get('h');
    if (!h) throw new KeyError("'h'");
    const R = h.runner, D = dummies(R), Pr = prims(R);
    const ny = h.h, nx = h.w;
    const out = new Masks(cell, x0, y0, [ny, nx]);
    out.params = P;
    const t0 = now();
    const norms = opts.norms ?? await normsFrom(fields, { cell, params: P });
    out.norms = norms;
    const want = expand(names);
    const wants = (nm) => want.includes(nm);
    const res = new Map();
    const temp = [];
    const keep = (f) => (temp.push(f), f);
    const missing = (nm, why) => {
        if (explicit && names.includes(nm)) throw new KeyError(`mask ${pyReprValue(nm)}: ${why}`);
        if (names.includes(nm)) out.skipped[nm] = why;
    };
    const one = () => R.field(ny, nx, 1);
    const wrapI = [P.wrap[0] ? 1 : 0, P.wrap[1] ? 1 : 0];
    try {
        // ---- slope, aspect, height
        const hp = padLevel(h, 1, cell, { x0, y0, wrap: P.wrap, outside, fill: 'odd', pair: true });
        const geo = keep(gradient(hp, 1, ny, nx, cell));               // (p, q, g, slope): numpy's float64 differences
        hp.destroy();
        const slope = R.unpack(geo, [null, null, null, 'slope']).slope;
        res.set('slope', slope);
        const height = one();
        R.copy(h, height);
        res.set('height', height);
        const hn = one();
        R.run('masks/height_norm', { h }, { outF: hn },
            { uLo: f32(norms.h_lo), uInv: f32(1.0 / Math.max(norms.h_hi - norms.h_lo, 1e-6)) });
        res.set('height_norm', hn);
        if (['aspect', 'northness', 'eastness', 'snow', 'vegetation'].some(wants)) {
            const a = one(), nn = one(), e = one();
            R.run('masks/aspect', { geo }, { outA: a, outN: nn, outE: e }, { uFade: ssPair(1.0, 3.0) });
            res.set('aspect', a);
            res.set('northness', nn);
            res.set('eastness', e);
        }
        out.seconds.geometry = now() - t0;
        // ---- curvature at each scale
        let t1 = now();
        const scales = scalesWanted(want, cell);
        const mu = scales.length || wants('peaks') ? (await Pr.stats(h)).mean : 0.0;
        for (const [s, nms] of scales) {
            const { b, f, mc, g } = blurred(h, s, cell, x0, y0, P.wrap, outside, mu);
            g.destroy();
            const { prof, plan } = curvatures(b, cell * f, P.flat_slope_deg);
            b.destroy();
            const kp = toKept(prof, f, mc, ny, nx), kt = toKept(plan, f, mc, ny, nx);
            prof.destroy();
            plan.destroy();
            let convex = null, concave = null;
            if (nms.some((nm) => ['convex', 'concave'].includes(parseName(nm)[0]))) {
                convex = one();
                concave = one();
                R.run('masks/bend', { kp, kt }, { outV: convex, outC: concave }, { uS: f32(s), uBend: ssPair(P.bend[0], P.bend[1]) });
            }
            const used = new Set();
            for (const nm of nms) {
                const base = parseName(nm)[0];
                let v = { curv_profile: kp, curv_plan: kt, convex, concave }[base];
                if (used.has(v)) {                                     // two names of one scale: their own copies
                    const c = one();
                    R.copy(v, c);
                    v = c;
                }
                used.add(v);
                res.set(nm, v);
            }
            for (const v of [kp, kt, convex, concave]) if (v && !used.has(v)) v.destroy();
        }
        out.seconds.curvature = now() - t1;
        // ---- peaks: high and convex, at each scale: above the local mean by enough standard deviations and metres
        if (wants('peaks')) {
            t1 = now();
            let pk = null;
            P.peaks_scales_m.forEach((s, i) => {
                const { b, f, mc, g, sigma } = blurred(h, s, cell, x0, y0, P.wrap, outside, mu);
                const g2 = R.field(g.h, g.w, 1);
                R.run('masks/square', { a: g }, { outF: g2 }, {});
                g.destroy();
                const b2 = gaussianBlur(g2, sigma);
                g2.destroy();
                const bk = toKept(b, f, mc, ny, nx), b2k = toKept(b2, f, mc, ny, nx);
                b.destroy();
                b2.destroy();
                const next = one();
                R.run('masks/peaks', { h, b: bk, b2: b2k, pk: pk ?? D.in1, hn }, { outF: next },
                    { uMu: f32(mu), uFloor2: f32(P.peaks_std_floor_m ** 2), uDev: ssPair(P.peaks_dev[0], P.peaks_dev[1]),
                        uRise: ssPair(P.peaks_rise[0] * s, P.peaks_rise[1] * s), uFirst: pk ? 0 : 1,
                        uLast: i === P.peaks_scales_m.length - 1 ? 1 : 0, uHn: ssPair(P.peaks_height_norm[0], P.peaks_height_norm[1]) });
                for (const x of [bk, b2k, pk]) x?.destroy();
                pk = next;
            });
            if (pk === null) pk = one();                             // no scales: zeros (times the height band)
            res.set('peaks', pk);
            out.seconds.peaks = now() - t1;
        }
        // ---- water and the pass-through process fields
        const wk = waterKind(fields, P);
        if (!wk) missing('water', "no 'water' field and no sea_level");
        const surf = keep(R.field(ny, nx, 4));                          // (dry, cover_w, wet_cell, 0)
        const water = wk ? one() : null;
        const dep = get('deposit'), tal = get('talus'), sand = get('sand');
        R.run('masks/surface', { h, water: get('water') ?? D.in1, dep: dep ?? D.in1, tal: tal ?? D.in1, sand: sand ?? D.in1 },
            { outW: water ?? D.out[0], outS: surf },
            { uWater: wk, uSea: f32(P.sea_level ?? 0.0), uHas: [dep ? 1 : 0, tal ? 1 : 0, sand ? 1 : 0],
                uWet: ssPair(0.0, 0.3), uCover: ssPair(P.cover_m[0], P.cover_m[1]) }, cover(ny, nx));
        if (water) res.set('water', water);
        for (const nm of PASS_THROUGH) {
            if (!wants(nm)) continue;
            const v = get(nm);
            if (!v) {
                missing(nm, `no ${pyReprValue(nm)} field (that process did not run)`);
            } else {
                const o = one();
                if (nm === 'lava') R.copy(v, o);
                else R.run('masks/positive', { a: v }, { outF: o }, {});
                res.set(nm, o);
            }
        }
        // ---- occlusion
        if (wants('occlusion')) {
            t1 = now();
            res.set('occlusion', skyView(h, cell, P.occlusion_radius_m, { x0, y0, wrap: P.wrap, outside,
                directions: P.occlusion_directions, ratio: P.occlusion_step_ratio }));
            out.seconds.occlusion = now() - t1;
        }
        // ---- drainage: flow, channels, wetness
        t1 = now();
        const A = get('A');
        if (!A) {
            for (const nm of ['flow', 'channels', 'wetness']) {
                if (wants(nm)) missing(nm, "no drainage area 'A' (run the route stage to convergence first)");
            }
        } else if (['flow', 'channels', 'wetness'].some(wants)) {
            const thr = P.channel_area_m2 !== null && P.channel_area_m2 !== undefined ? P.channel_area_m2 : channelAreaForCell(cell);
            const lt = Math.log10(thr);
            const fl = one(), ch = one(), we = one();
            R.run('masks/drainage', { A, geo, surf, sand: sand ?? D.in1 }, { outF: fl, outC: ch, outW: we },
                { uCell2: f32(cell * cell), uLogCell: f32(Math.log10(cell)), uFlowLo: f32(norms.flow_lo),
                    uFlowInv: f32(1.0 / Math.max(norms.flow_hi - norms.flow_lo, 1e-6)), uCh: ssPair(lt - 0.7, lt + 0.3),
                    uHasSand: sand ? 1 : 0, uSand: ssPair(P.sand_swallows_m[0], P.sand_swallows_m[1]),
                    uTwiLo: f32(norms.twi_lo), uTwiInv: f32(1.0 / Math.max(norms.twi_hi - norms.twi_lo, 1e-6)),
                    uLn10: f32(Math.log(10.0)) });
            for (const [nm, v] of [['flow', fl], ['channels', ch], ['wetness', we]]) {
                if (wants(nm)) res.set(nm, v);
                else v.destroy();
            }
        }
        out.seconds.drainage = now() - t1;
        // ---- rock, its foot, snow, vegetation
        t1 = now();
        if (wants('rock')) {
            const wear = get('wear');
            const rk = one();
            R.run('masks/rock', { geo, surf, wear: wear ?? D.in1 }, { outF: rk },
                { uRock: ssPair(P.rock_deg[0], P.rock_deg[1]), uWear: ssPair(P.rock_wear_m[0], P.rock_wear_m[1]), uHasWear: wear ? 1 : 0 });
            res.set('rock', rk);
        }
        if (wants('rock_toe')) {
            const t2 = now();
            const tanUp = keep(rockShadow(h, res.get('rock'), cell, P.rock_toe_reach_m,
                { wrap: P.wrap, directions: P.rock_toe_directions }));
            const sh = P.rock_toe_shadow_deg.map((a) => Math.tan(a * Math.PI / 180.0));
            const rt = one();
            R.run('masks/rock_toe', { tan: tanUp, rock: res.get('rock'), concave: res.get('concave_20m'), surf }, { outF: rt },
                { uShadow: ssPair(sh[0], sh[1]) });
            res.set('rock_toe', rt);
            out.seconds.rock_toe = now() - t2;
        }
        if (wants('snow')) {
            if (P.snowline_m === null || P.snowline_m === undefined) {
                missing('snow', 'no snowline_m');
            } else {
                const sn = one();
                R.run('masks/snow', { h, geo, north: res.get('northness'), concave: res.get('concave_20m'),
                    convex: res.get('convex_20m'), surf }, { outF: sn },
                { uBase: f32(P.base_elevation_m), uAspect: f32(P.snow_aspect_m), uConcave: f32(P.snow_concave_m),
                    uLine: ssPair(P.snowline_m - P.snow_band_m, P.snowline_m + P.snow_band_m),
                    uSlope: ssPair(P.snow_slope_deg[0], P.snow_slope_deg[1]) });
                res.set('snow', sn);
            }
        }
        if (wants('vegetation')) {
            const tl = P.treeline_m !== null && P.treeline_m !== undefined;
            const has = (nm) => (res.has(nm) ? 1 : 0);
            const packA = keep(R.pack(Object.fromEntries(['wetness', 'occlusion', 'rock', 'snow'].filter((k) => res.has(k))
                .map((k) => [k, res.get(k)])), ['wetness', 'occlusion', 'rock', 'snow'], [ny, nx]));
            const packB = keep(R.pack({ rock_toe: res.get('rock_toe'), talus: tal, sand, northness: res.get('northness') },
                ['rock_toe', 'talus', 'sand', 'northness'], [ny, nx]));
            const vg = one();
            R.run('masks/vegetation', { h, geo, surf, packA, packB }, { outF: vg },
                { uSlope: ssPair(P.veg_slope_deg[0], P.veg_slope_deg[1]), uTree: tl ? 1 : 0, uBase: f32(P.base_elevation_m),
                    uHalfAspect: f32(0.5 * P.snow_aspect_m),
                    uTreeline: tl ? ssPair(P.treeline_m - P.treeline_band_m, P.treeline_m + P.treeline_band_m) : [0.0, 1.0],
                    uAlpine: f32(1.0 - P.alpine_density), uHasA: [has('wetness'), has('occlusion'), has('rock'), has('snow')],
                    uHasB: [has('rock_toe'), tal ? 1 : 0, sand ? 1 : 0, 0], uTalus: ssPair(0.2, 2.0), uSandV: ssPair(0.1, 1.0),
                    uOcc: ssPair(0.35, 0.75) });
            res.set('vegetation', vg);
        }
        out.seconds.surface = now() - t1;
        // ---- strata
        if (wants('strata')) {
            const zs = get('zs');
            if (zs) {
                const o = one();
                R.copy(zs, o);
                res.set('strata', o);
            } else if (P.strata) {
                res.set('strata', await strataField(h, cell, x0, y0, P));
            } else {
                missing('strata', "no 'zs' field and no params.strata");
            }
        }
        for (const nm of names) if (res.has(nm) && !(nm in out)) out[nm] = res.get(nm);
        const kept = new Set(Object.values(out));
        for (const v of new Set(res.values())) if (!kept.has(v)) v.destroy();
    } catch (e) {
        for (const v of new Set(res.values())) if (!v.destroyed) v.destroy();
        throw e;
    } finally {
        for (const v of temp) if (!v.destroyed) v.destroy();
    }
    out.seconds.total = now() - t0;
    return out;
}

// the strata mask from params.strata: zs = h + base - tan(dip) (x cos az + y sin az), minus the warp
async function strataField(h, cell, x0, y0, P) {
    const R = h.runner, D = dummies(R);
    const st = P.strata;
    const az = Number(st.azimuth_deg ?? 0.0) * Math.PI / 180.0;
    const tanDip = Math.tan(Number(st.dip_deg ?? 0.0) * Math.PI / 180.0);
    const ny = h.h, nx = h.w;
    // per column x cos az, per row y sin az: numpy's float64 products of the cell centres, rounded once
    const xc = new Float32Array(nx), ys = new Float32Array(ny), X = new Float32Array(nx), Y = new Float32Array(ny);
    for (let i = 0; i < nx; i++) {
        X[i] = x0 + (i + 0.5) * cell;
        xc[i] = (x0 + (i + 0.5) * cell) * Math.cos(az);
    }
    for (let j = 0; j < ny; j++) {
        Y[j] = y0 + (j + 0.5) * cell;
        ys[j] = (y0 + (j + 0.5) * cell) * Math.sin(az);
    }
    const ct = R.field(1, nx, 1, xc), rt = R.field(1, ny, 1, ys);
    let warp = null;
    let warpNum = 0.0;
    if (typeof st.warp === 'function') {
        const cx = R.field(1, nx, 1, X), ry = R.field(1, ny, 1, Y);
        const XX = R.field(ny, nx, 1), YY = R.field(ny, nx, 1);
        R.run('masks/world_xy', { colT: cx, rowT: ry }, { outX: XX, outY: YY }, {});
        cx.destroy();
        ry.destroy();
        const w = await st.warp(XX, YY);
        XX.destroy();
        YY.destroy();
        if (typeof w === 'number') warpNum = w;
        else if (isField(w)) warp = w;
        else if (w !== null && w !== undefined) throw new TypeError('params.strata.warp: a GPU field or a number is needed');
    }
    const o = R.field(ny, nx, 1);
    R.run('masks/strata', { h, colT: ct, rowT: rt, warp: warp ?? D.in1 }, { outF: o },
        { uBase: f32(P.base_elevation_m), uTan: f32(tanDip), uWarp: warp ? 1 : 0, uWarpNum: f32(warpNum) });
    ct.destroy();
    rt.destroy();
    if (warp) warp.destroy();
    return o;
}


// ----------------------------------------------------------------------------------------------- the stack ---

// pin_band's per-row or per-column table: (floor index clipped to n - 2, fraction as float32, inside 1 / 0), from
// numpy's float64 fx = (child.x0 + (I + 0.5) child.cell - parent.x0) / parent.cell - 0.5
function pinTable(R, n, c0, cc, p0, pc, pn) {
    const t = new Float32Array(4 * n);
    for (let k = 0; k < n; k++) {
        const fx = (c0 + (k + 0.5) * cc - p0) / pc - 0.5;
        const ok = fx >= 0 && fx <= pn - 1;
        const x0 = Math.min(Math.floor(fx), pn - 2);
        t[4 * k] = ok ? x0 : -1;
        t[4 * k + 1] = fx - x0;
        t[4 * k + 2] = ok ? 1 : 0;
    }
    return R.field(1, n, 4, t);
}

/** A child level's masks pinned to its parent's in its outer `band` cells, as the level runner pins its heights
 * (DESIGN.md 2.2): weight 1 at the edge falling smoothly to 0 at `band` cells in, the parent's masks read bilinearly
 * at the child's cells. So every mask meets the ring next to it exactly at the seam, the level-of-detail ones
 * (2 x cell curvature, channels) included, and fades to the child's own across the band. aspect is not blended
 * (degrees tear at north; materials read northness and eastness). In place, on GPU fields; returns child. */
export function pinBand(child, parent, band = 16, skip = ['aspect']) {
    const [ny, nx] = child.shape;
    if (!(band > 0)) return child;
    const [py, px] = parent.shape;
    let R = null;
    for (const v of Object.values(child)) if (isField(v)) R = v.runner;
    if (!R) return child;
    const ct = pinTable(R, nx, child.x0, child.cell, parent.x0, parent.cell, px);
    const rt = pinTable(R, ny, child.y0, child.cell, parent.y0, parent.cell, py);
    for (const [nm, v] of Object.entries(child)) {
        if (skip.includes(nm) || !parent.has(nm)) continue;
        const a = parent[nm];
        if (!isField(v) || !isField(a)) throw new TypeError(`pin_band: mask ${pyReprValue(nm)} must be a GPU field on both levels`);
        R.run('masks/pin_band', { par: a, colT: ct, rowT: rt }, { outV: v }, { uBand: ssPair(0.0, Number(band)) });
    }
    ct.destroy();
    rt.destroy();
    return child;
}

/** Masks for every level of a stack (coarsest first): each level padded with its parents' terrain beyond its
 * window (so a blur, a derivative or the occlusion march at its edge sees what the ring next to it shows),
 * normalised by the main level, and pinned to its parent's masks across its outer borderBand cells (pinBand; 0
 * turns that off). levels: each with x0, y0, cell (and role) as objects; null takes them from each Fields' .level.
 * opts: main (the main level's index; default the level whose role is 'main', else the finest level that is not
 * 'hero', else the last), names, params, strict, borderBand (16), keep (true: the masks stay GPU fields; default:
 * each level's are read back into Float32Arrays once its child is pinned to them). Returns [Masks]. */
export async function computeStack(levelFields, levels = null, opts = {}) {
    levels = levels ?? levelFields.map((f) => f.level);
    let main = opts.main ?? null;
    if (main === null) {
        const roles = levels.map((l) => lvOf(l, 'role'));
        if (roles.includes('main')) {
            main = roles.indexOf('main');
        } else {
            const nonHero = roles.map((r, i) => [r, i]).filter(([r]) => r !== 'hero').map(([, i]) => i);
            main = nonHero.length ? nonHero[nonHero.length - 1] : levels.length - 1;
        }
    }
    const P = asParams(opts.params);
    const band = opts.borderBand ?? opts.border_band ?? 16;
    const norms = await normsFrom(levelFields[main], { cell: lvOf(levels[main], 'cell'), params: P });
    const layers = [];
    const result = [];
    try {
        for (let i = 0; i < levelFields.length; i++) {
            const f = levelFields[i], lv = levels[i];
            const cell = Number(lvOf(lv, 'cell')), x0 = Number(lvOf(lv, 'x0')), y0 = Number(lvOf(lv, 'y0'));
            const outside = layers.length ? new StackSampler(layers) : null;
            const m = await compute(f, { cell, x0, y0, names: opts.names ?? null, norms, params: P, outside, strict: opts.strict ?? null });
            const prev = result.length ? result[result.length - 1] : null;
            if (prev && band) {
                const t0 = now();
                pinBand(m, prev, band);
                m.seconds.border_pin = now() - t0;
            }
            if (prev && !opts.keep) await prev.toHost();
            result.push(m);
            layers.push({ x0, y0, cell, field: fieldOf(f, 'h') });
        }
        if (result.length && !opts.keep) await result[result.length - 1].toHost();
    } catch (e) {
        for (const m of result) m.dispose();
        throw e;
    }
    return result;
}

/** One line per mask: name, unit, meaning. */
export function describeMasks() {
    return Object.entries(MASKS).map(([k, [u, d]]) => `${k.padEnd(14)} ${u.padEnd(10)} ${d}`).join('\n');
}

export {
    attributeName as attribute_name, channelAreaForCell as channel_area_for_cell, parseName as parse_name,
    scaleSuffix as scale_suffix, gaussianBlur as gaussian_blur, padLevel as pad_level, windowGrid as window_grid,
    toKept as to_kept, skyView as sky_view, rockBase as rock_base, rockShadow as rock_shadow, normsFrom as norms_from,
    pinBand as pin_band, computeStack as compute_stack, describeMasks as describe_masks, goodSize as good_size,
};
// (pyRepr and pyRound are used by the port's tests through this module's helpers' messages)
export const _internal = { expand, scalesWanted, decimation, marchDistances, floorDiv, nearest, pyRepr };
