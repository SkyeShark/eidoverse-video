// Port of blender/eidoblend/terrain/solvers/rivers.py at f90c6fc.
//
// River courses (design section 4.13, `river_path`): a river given as a polyline, or generated (a Kinoshita meander
// train for incised meanders, or a smoothed random walk), carved as a base-level line: its channel is pinned low with
// a slope along it, so the erosion stages build the valley around it.
//
//     stage op (OPS; run.js calls op(fields, level, params, seed, ctx)):
//       'river_path'   the course (world metres, deterministic per seed) into ctx.shared.river, and the level's pins
//                      (ctx.pins) with the channel held at its final bed: the stock 'fluvial' stage then cuts its valley
//                      around it. The layered-rock stage (solvers/strata.js 'strata_fluvial') reads the same course and
//                      lowers the channel over time instead (the base-level fall), following `schedule`.
//
//     import * as RV from './solvers/rivers.js';
//     const pts = RV.kinoshita([0, 0], 270.0, 20000.0, 1100.0, 3.0, null, 0.03, 0.0, 0.15, 4);   // [[x, y], ...] metres
//     RV.metrics(pts)                 // arc length, chord, sinuosity, bend wavelengths, the closest approach of two parts
//     const ch = await RV.channel(level, pts, 60.0, RV.MIN_CELLS, R);   // GPU fields: the channel's cells, the
//                                     // nearest segment and the parameter along it, the distance to the course
//
// Parameters of 'river_path' (metres, degrees, m/m): as rivers.py's (DEFAULTS below, the same names and meanings):
//     kind 'walk'                  'walk' (a smoothed random walk), 'kinoshita' (meanders), 'polyline' (points)
//     points null                  [[x, y], ...] for 'polyline' (extended straight past its ends to cross every level)
//     through [0, 0]               a point on the course (its arc-length origin)
//     centre 'course'              'kinoshita': 'course' puts the course itself through `through`; 'axis' puts the
//                                  meander belt's centre line there
//     flow_azimuth_deg 90          the down-valley direction, compass degrees (clockwise from north: 90 flows east)
//     length_m null                the course's length (default: three times the coarsest level's side)
//     wiggle_deg 12, wiggle_wavelength_m 3000     'walk': the direction's spread and the scale of its bends
//     wavelength_m 1200            'kinoshita': the arc length of one meander (two bends)
//     sinuosity 2.5 (or theta0_deg)  'kinoshita': arc length / down-valley length (theta0 is solved for it)
//     skew 0.03, flat 0.0          'kinoshita': Js (bends lean downstream) and Jf (flattened, boxy bends)
//     vary 0.15, vary_scale 3.0, vary_skew 0      'kinoshita': the variation of the amplitude and wavelength along the
//                                  course, its scale in meander wavelengths, and the skew's variation
//     min_neck_m 0                 'kinoshita': a loop whose limbs would pass closer than this is shrunk until they
//                                  do not (0: no check)
//     growth 1.0, growth_stages 6  'kinoshita': the bends' amplitude when the base-level fall starts, as a fraction
//                                  of the final; it grows to 1 over the fall; 1: a fixed course
//     width_m 60                   the channel's width (at least 1.5 cells, so it is connected on every level)
//     bed_m 0, gradient 0.0015     the final bed's height (relative h) at `through`, and its fall per metre downstream
//     schedule [[0, 0], [1, 1]]    the base-level fall over the run (strata_fluvial): time fraction -> fraction of the
//                                  way from the starting surface down to the final bed (piecewise linear)
//     pool_spacing_m 0, pool_depth_m 0, pool_riffle 0.12, pool_jitter 0.35    pool and riffle (0: a smooth bed)
// The Kinoshita curve (Kinoshita 1961; Parker et al. 1983): the channel direction along arc length s is
//     theta(s) = theta0 sin(k s) + theta0^3 (Js cos(3 k s) - Jf sin(3 k s)),   k = 2 pi / wavelength
// whose sinuosity is 1 / mean(cos theta) (Langbein & Leopold's sine-generated curve when Js = Jf = 0).
//
// Where this differs from rivers.py, and why (PORT_PLAN.md 2.4, 3.2: per-cell work on the GPU; plans over objects in
// JavaScript doubles, numpy's arithmetic):
//   - The courses (walk, kinoshita, polyline), their metrics, the crests and the schedule stay JavaScript over the
//     course's points (plan 2.4: river courses), in doubles, with numpy's own arithmetic where it decides a result:
//     linspace's (i step + start, the end set exactly), the pairwise sum of np.mean, np.interp's slope form, the
//     float64 percentile of numpy 2.3.4 ('linear', _lerp), Python's float floor division, and numpy's Generator
//     (core/np_random.js). A course is an array of [x, y] pairs (numpy's (N, 2)); arc lengths a Float64Array.
//     np.sin, np.cos, np.exp, C's pow and hypot are V8's Math functions: a last-ulp difference at most (plan 5.3's
//     plan grade, 1e-12 relative), and matmul's sums of two products are rounded twice (BLAS may fuse them).
//   - channel() is GPU kernels (kernels/strata/river_channel.wgsl): the segments near the window are binned per 16 x
//     16 tile of cells (each segment's box exactly as numpy computes it, in doubles), and every cell visits its tile's
//     segments in course order with numpy's rule (the nearest by a strict `<`, inside each segment's own box), in
//     float32 on local offsets. The channel's cells are an exact decision: a cell whose float32 distance lies within
//     the arithmetic's bound of the half width (a few in a level, often none) is read back and decided again in
//     doubles exactly as numpy does (kernels/strata/river_fix.wgsl writes the result). Instead of numpy's float64 arc
//     length the GPU keeps each cell's nearest segment k and the parameter t along it (s = s_k + t L_k), which the
//     bed kernel needs in that form to stay well conditioned (arc lengths reach 1e5 m).
//   - River.pins() evaluates the bed per channel cell on the GPU (kernels/strata/river_pins.wgsl): bed(s, f) from the
//     course's per-point table (top(s) is np.interp along the course, so linear along each segment; the bed line
//     line_k - t gradient L_k; the pools' scour with each segment's crest and its offset from it in doubles). A
//     final(s) replaced on the River (solvers/fluvial.js opIncise does it, as fluvial.py op_incise does) is evaluated
//     at the course's points and interpolated along each segment: exact for op_incise's graded bed, which is
//     piecewise linear with its breakpoints at course points. The pools' scour takes max(sin, 0) before the power
//     0.6: float32's pi exceeds pi, so sin(pi v^0.75) is -8.7e-8 where numpy's is +1.2e-16, and a negative base would
//     give NaN.
//   - sample_top() reads the level's height back once (a GPU field) and samples it on the CPU along the course
//     (core/grid.js sampleBilinear: plan 2.4's per-query sampling).
//   - Python's dict equality (op_river_path's rv.spec != params) is pyEqual() below on JSON values.
//   - pins(level, basePins, f, { cache, hold }) takes its options as an object, the port's convention; a cache
//     ({}) keeps the level's channel fields between calls (releaseChannel(cache) frees them). The fields are GPU
//     fields; pins returns [pins, mask]: the pins object holds new pin_w and pin_h fields and the base's A_in and
//     qs_in, and the mask (r32f, 1 on the channel) is the cache's when a cache is given, else the caller's.
//   - op_river_path is async; it releases the pins its previous call on the same River made (Blender's are numpy
//     arrays the collector frees; here GPU buffers): those served the previous pass's later stages only.

import * as Gd from '../core/grid.js';
import { pyFormat } from '../core/levels.js';
import { defaultRng } from '../core/np_random.js';
import { prims } from '../core/prims.js';

const DEG = Math.PI / 180.0;                        // math.radians(x) is x * (pi / 180) in CPython
const RAD = 180.0 / Math.PI;                        // math.degrees(x) is x * (180 / pi)
const NONE = 0xFFFFFFFF;

export const DEFAULTS = Object.freeze({ kind: 'walk', points: null, through: Object.freeze([0.0, 0.0]), centre: 'course',
    flow_azimuth_deg: 90.0, length_m: null, wiggle_deg: 12.0, wiggle_wavelength_m: 3000.0, wavelength_m: 1200.0,
    sinuosity: 2.5, theta0_deg: null, skew: 0.03, flat: 0.0, vary: 0.15, vary_scale: 3.0, vary_skew: 0.0,
    min_neck_m: 0.0, width_m: 60.0, bed_m: 0.0, gradient: 0.0015,
    schedule: Object.freeze([Object.freeze([0.0, 0.0]), Object.freeze([1.0, 1.0])]), step_m: null, seed: 0, growth: 1.0,
    growth_stages: 6, pool_spacing_m: 0.0, pool_depth_m: 0.0, pool_riffle: 0.12, pool_jitter: 0.35 });
export const MIN_CELLS = 1.5;                       // the channel is at least this many cells wide (8-connected on every level)

const has = (o, k) => o !== null && o !== undefined && Object.prototype.hasOwnProperty.call(o, k);

/** rivers.py _p: params.get(key, DEFAULTS[key]), the default where it is None and the default is not. */
export function _p(params, key) {
    const d = DEFAULTS[key];
    const v = has(params, key) ? params[key] : d;
    return (v === null || v === undefined) && d !== null ? d : v;
}

/** Python's truth value of a number or None (`x or 0.0`). */
const orZero = (v) => (v === null || v === undefined || v === 0 || v === false ? 0.0 : Number(v));


// ------------------------------------------------------------------------------- numpy's arithmetic in doubles ---

/** np.linspace(start, stop, num, endpoint): i * step + start, the end set to stop exactly (numpy 2.3.4). */
export function linspace(start, stop, num, endpoint = true) {
    const div = endpoint ? num - 1 : num;
    const out = new Float64Array(num);
    const delta = stop - start;
    if (div > 0) {
        const step = delta / div;
        if (step === 0) for (let i = 0; i < num; i++) out[i] = ((i / div) * delta) + start;
        else for (let i = 0; i < num; i++) out[i] = i * step + start;
    } else {
        for (let i = 0; i < num; i++) out[i] = i * delta + start;
    }
    if (endpoint && num > 1) out[num - 1] = stop;
    return out;
}

/** numpy's pairwise sum of a float64 array (np.add.reduce on a contiguous array: under 8 in order, to 128 with eight
 * accumulators, else split at a multiple of 8). */
export function pairwiseSum(a, i0 = 0, n = a.length - i0) {
    if (n < 8) {
        let s = 0.0;
        for (let i = 0; i < n; i++) s += a[i0 + i];
        return s;
    }
    if (n <= 128) {
        const r = [a[i0], a[i0 + 1], a[i0 + 2], a[i0 + 3], a[i0 + 4], a[i0 + 5], a[i0 + 6], a[i0 + 7]];
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

/** np.searchsorted(a, v, side) on an ascending array. */
export function searchsorted(a, v, side = 'left') {
    let lo = 0, hi = a.length;
    if (side === 'right') {
        while (lo < hi) {
            const m = (lo + hi) >> 1;
            if (a[m] <= v) lo = m + 1; else hi = m;
        }
    } else {
        while (lo < hi) {
            const m = (lo + hi) >> 1;
            if (a[m] < v) lo = m + 1; else hi = m;
        }
    }
    return lo;
}

/** np.interp(x, xp, fp) for one x, numpy's own arithmetic (compiled_base.c arr_interp): the end values outside, a
 * node's own value at a node, else slope (x - xp[j]) + fp[j]. */
export function npInterp(x, xp, fp) {
    const n = xp.length;
    if (Number.isNaN(x)) return x;
    if (x > xp[n - 1]) return fp[n - 1];
    if (x < xp[0]) return fp[0];
    const j = searchsorted(xp, x, 'right') - 1;
    if (j === n - 1) return fp[j];
    if (xp[j] === x) return fp[j];
    const slope = (fp[j + 1] - fp[j]) / (xp[j + 1] - xp[j]);
    let r = slope * (x - xp[j]) + fp[j];
    if (Number.isNaN(r)) {
        r = slope * (x - xp[j + 1]) + fp[j + 1];
        if (Number.isNaN(r) && fp[j] === fp[j + 1]) r = fp[j];
    }
    return r;
}

/** np.percentile(a, q) of float64 data with a Python-number q (numpy 2.3.4, method 'linear', float64 throughout):
 * the order statistics around (n - 1) q / 100 and _lerp. */
export function percentile64(a, q) {
    const s = Float64Array.from(a).sort();
    const n = s.length;
    const virt = (n - 1) * (q / 100);
    let prev = Math.floor(virt), next = prev + 1;
    if (virt >= n - 1) prev = next = n - 1;
    if (virt < 0) prev = next = 0;
    const gamma = virt - (virt >= n - 1 ? -1 : prev);
    const lo = s[prev], hi = s[next];
    const diff = hi - lo;
    return gamma >= 0.5 ? hi - diff * (1 - gamma) : lo + diff * gamma;
}

/** Python's float floor division a // b (CPython float_floor_div: fmod, then the quotient snapped to an integer). */
export function pyFloorDiv(a, b) {
    let mod = a % b;
    let div = (a - mod) / b;
    if (mod) {
        if ((b < 0) !== (mod < 0)) {
            mod += b;
            div -= 1.0;
        }
    }
    if (div) {
        let f = Math.floor(div);
        if (div - f > 0.5) f += 1.0;
        return f;
    }
    return Math.sign(a / b) < 0 || Object.is(a / b, -0) ? -0.0 : 0.0;
}

/** np.convolve(x, v, mode='same') of float64 arrays (numpy's direct sum over the overlap, v reversed). */
export function convolveSame(x, v) {
    const n = x.length, m = v.length;
    const full = new Float64Array(n + m - 1);
    for (let k = 0; k < full.length; k++) {
        let s = 0.0;
        const j0 = Math.max(0, k - n + 1), j1 = Math.min(k, m - 1);
        for (let j = j0; j <= j1; j++) s += x[k - j] * v[j];
        full[k] = s;
    }
    const off = Math.floor((m - 1) / 2);
    return full.slice(off, off + n);
}

/** Python's == on JSON values (dicts by keys and values, lists element by element, numbers by value). */
export function pyEqual(a, b) {
    if (a === b) return true;
    if (a === null || b === null || a === undefined || b === undefined) return a == b;     // eslint-disable-line eqeqeq
    if (Array.isArray(a) || ArrayBuffer.isView(a)) {
        if (!(Array.isArray(b) || ArrayBuffer.isView(b)) || a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) if (!pyEqual(a[i], b[i])) return false;
        return true;
    }
    if (typeof a === 'object' && typeof b === 'object') {
        const ka = Object.keys(a), kb = Object.keys(b);
        if (ka.length !== kb.length) return false;
        for (const k of ka) if (!has(b, k) || !pyEqual(a[k], b[k])) return false;
        return true;
    }
    return typeof a === 'number' && typeof b === 'number' ? a === b : false;
}


// ---------------------------------------------------------------------------------------------- the courses ---

/** A smooth 1D noise of unit standard deviation along s: sines at random phases, wavelengths halving. */
export function _smoothNoise1d(s, wavelength, seed, octaves = 3) {
    const rng = defaultRng(Math.trunc(seed) * 7919 + 101);
    const out = new Float64Array(s.length);
    let norm = 0.0;
    for (let o = 0; o < octaves; o++) {
        const a = 0.5 ** o;
        for (let r = 0; r < 2; r++) {
            const lam = (wavelength / (2.0 ** o)) * rng.uniform(0.7, 1.4);
            const ph = rng.uniform(0.0, 2.0 * Math.PI);
            const c = 2.0 * Math.PI;
            for (let i = 0; i < s.length; i++) out[i] += a * Math.sin((c * s[i]) / lam + ph);
            norm += a * a * 0.5;
        }
    }
    const k = Math.sqrt(norm);
    for (let i = 0; i < s.length; i++) out[i] /= k;
    return out;
}

/** Points of a curve from its direction angle theta (radians, from +x) at arc steps ds. */
export function _integrate(theta, ds) {
    const n = theta.length;
    const dx = new Float64Array(n), dy = new Float64Array(n);
    for (let i = 0; i < n; i++) {
        dx[i] = Math.cos(theta[i]) * ds;
        dy[i] = Math.sin(theta[i]) * ds;
    }
    const out = new Array(n);
    out[0] = [0.0, 0.0];
    let x = 0.0, y = 0.0;
    for (let i = 1; i < n; i++) {
        x += 0.5 * (dx[i] + dx[i - 1]);
        y += 0.5 * (dy[i] + dy[i - 1]);
        out[i] = [x, y];
    }
    return out;
}

/** Rotate a course built along +x (down-valley) to the compass azimuth and move its arc-length origin s0 (or the local
 * point `anchor`) onto `through`. */
export function _place(local, through, flowAzimuthDeg, s, s0 = 0.0, anchor = null) {
    const az = Number(flowAzimuthDeg) * DEG;
    const ux = Math.sin(az), uy = Math.cos(az);
    const vx = -uy, vy = ux;
    let k = 0;
    for (let i = 1; i < s.length; i++) if (Math.abs(s[i] - s0) < Math.abs(s[k] - s0)) k = i;
    const [ox, oy] = anchor === null ? local[k] : [Number(anchor[0]), Number(anchor[1])];
    const tx = Number(through[0]), ty = Number(through[1]);
    return local.map(([lx, ly]) => {
        const px = lx - ox, py = ly - oy;
        return [(px * ux + py * vx) + tx, (px * uy + py * vy) + ty];
    });
}

/** A smoothed random walk: the direction wanders around the flow azimuth by a smooth noise of `wiggleDeg` standard
 * deviation at `wiggleWavelengthM`. [[x, y], ...] world metres, upstream first. */
export function walk(through, flowAzimuthDeg, lengthM, wiggleDeg = 12.0, wiggleWavelengthM = 3000.0, seed = 0, stepM = 10.0) {
    const n = Math.max(Math.trunc(Math.ceil(lengthM / stepM)) + 1, 3);
    const s = linspace(-0.5 * lengthM, 0.5 * lengthM, n);
    const nz = _smoothNoise1d(s, Number(wiggleWavelengthM), seed);
    const w = Number(wiggleDeg) * DEG;
    const theta = Float64Array.from(nz, (v) => w * v);
    const local = _integrate(theta, s[1] - s[0]);
    return _place(local, through, flowAzimuthDeg, s, 0.0);
}

/** The Kinoshita direction angle (radians) at phases (a number or an array), with theta0 and skew numbers or arrays. */
export function kinoshitaTheta(phase, theta0, skew = 0.0, flat = 0.0) {
    const at = (v, i) => (typeof v === 'number' ? v : v[i]);
    if (typeof phase === 'number') {
        return theta0 * Math.sin(phase) + theta0 ** 3 * (skew * Math.cos(3.0 * phase) - flat * Math.sin(3.0 * phase));
    }
    const out = new Float64Array(phase.length);
    for (let i = 0; i < phase.length; i++) {
        const th = at(theta0, i), sk = at(skew, i), ph = phase[i];
        out[i] = th * Math.sin(ph) + th ** 3 * (sk * Math.cos(3.0 * ph) - flat * Math.sin(3.0 * ph));
    }
    return out;
}

/** Arc length over down-valley length of the Kinoshita curve (one wavelength, exact up to sampling). */
export function kinoshitaSinuosity(theta0, skew = 0.0, flat = 0.0, samples = 4096) {
    const ph = linspace(0.0, 2.0 * Math.PI, samples, false);
    const th = kinoshitaTheta(ph, theta0, skew, flat);
    const c = pairwiseSum(Float64Array.from(th, Math.cos)) / samples;
    return c <= 1e-9 ? Infinity : 1.0 / c;
}

/** theta0 (radians) giving a Kinoshita curve of the given sinuosity (bisection; sinuosity rises with theta0). */
export function theta0For(sinuosity, skew = 0.0, flat = 0.0) {
    const target = Number(sinuosity);
    if (target <= 1.0) return 0.0;
    let lo = 0.0, hi = 2.6;
    if (kinoshitaSinuosity(hi, skew, flat) < target) {
        throw new Error(`sinuosity ${pyFormat(target, 'g')} is beyond what the Kinoshita curve reaches before its bends close ` +
            `(${pyFormat(kinoshitaSinuosity(hi, skew, flat), '.2f')} at theta0 ${pyFormat(hi * RAD, '.0f')} degrees)`);
    }
    for (let i = 0; i < 60; i++) {
        const mid = 0.5 * (lo + hi);
        if (kinoshitaSinuosity(mid, skew, flat) < target) lo = mid;
        else hi = mid;
    }
    return 0.5 * (lo + hi);
}

/** Index pairs [a, b], a < b, of course points closer than minD whose arc lengths differ by more than minSep (the two
 * limbs of a loop or two loops), one pair (the closest) per 0.5 minSep stretch of the arc. Points are binned on a
 * minD grid, so only neighbouring bins are compared (rivers.py _close_pairs, its dict orders kept as Map orders). */
export function _closePairs(local, s, minD, minSep) {
    const stride = Math.max(1, Math.trunc(minD / Math.max(Number(s[1] - s[0]), 1e-9) / 3.0));
    const idx = [];
    for (let i = 0; i < local.length; i += stride) idx.push(i);
    const bins = new Map();
    idx.forEach((ip, k) => {
        const kx = Math.floor(local[ip][0] / minD), ky = Math.floor(local[ip][1] / minD);
        const key = `${kx},${ky}`;
        if (!bins.has(key)) bins.set(key, { kx, ky, members: [] });
        bins.get(key).members.push(k);
    });
    const best = new Map();
    for (const { kx, ky, members } of bins.values()) {
        const near = [];
        for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) near.push(...(bins.get(`${kx + dx},${ky + dy}`)?.members ?? []));
        for (const k of members) {
            const ia = idx[k];
            let m = -1, dm = Infinity, any = false;
            for (const o of near) {
                if (!(o > k)) continue;
                const ib = idx[o];
                if (!((s[ib] - s[ia]) > minSep)) continue;
                any = true;
                const d = Math.hypot(local[ib][0] - local[ia][0], local[ib][1] - local[ia][1]);
                if (d < dm) { dm = d; m = ib; }
            }
            if (!any) continue;
            if (dm < minD) {
                const slot = pyFloorDiv(s[ia], 0.5 * minSep);
                const cur = best.get(slot);
                if (cur === undefined || dm < cur[0]) best.set(slot, [dm, ia, m]);
            }
        }
    }
    return [...best.values()].map(([, a, b]) => [a, b]);
}

/** A meander train (rivers.py kinoshita; see the module doc): [[x, y], ...] world metres, upstream first. */
export function kinoshita(through, flowAzimuthDeg, lengthM, wavelengthM = 1200.0, sinuosity = 2.5, theta0Deg = null,
    skew = 0.03, flat = 0.0, vary = 0.15, seed = 0, stepM = null, varyScale = 3.0, varySkew = 0.0, minNeckM = 0.0,
    centre = 'course') {
    const th0 = theta0Deg !== null && theta0Deg !== undefined ? Number(theta0Deg) * DEG : theta0For(sinuosity, skew, flat);
    const sig = kinoshitaSinuosity(th0, skew, flat);
    const arc = Number(lengthM) * sig;
    const step = stepM ? Number(stepM) : Math.max(1.0, Number(wavelengthM) / 160.0);
    const n = Math.max(Math.trunc(Math.ceil(arc / step)) + 1, 3);
    const s = linspace(-0.5 * arc, 0.5 * arc, n);
    const v = Number(vary);
    const sc = Number(varyScale);
    const wl = Number(wavelengthM);
    const nl = _smoothNoise1d(s, 1.1 * sc * wl, Math.trunc(seed) + 17, 2);
    const na = _smoothNoise1d(s, 0.9 * sc * wl, Math.trunc(seed) + 29, 2);
    const lam = Float64Array.from(nl, (x) => wl * Math.min(Math.max(1.0 + v * x, 0.5), 1.6));
    const phase = new Float64Array(n);
    const c2 = 2.0 * Math.PI;
    for (let i = 1; i < n; i++) phase[i] = phase[i - 1] + (c2 / (0.5 * (lam[i] + lam[i - 1]))) * (s[i] - s[i - 1]);
    const ph0 = defaultRng(Math.trunc(seed) * 31 + 7).uniform(0.0, 2.0 * Math.PI);
    for (let i = 0; i < n; i++) phase[i] += ph0;
    // amplitude variation, kept under the closing angle: past about 125 degrees the bends touch
    const vk = 0.6 * v;
    const amp = Float64Array.from(na, (x) => Math.min(Math.max(th0 * (1.0 + vk * x), 0.0), 125.0 * DEG));
    let sk = Number(skew);
    if (Number(varySkew)) {
        const ns = _smoothNoise1d(s, 1.3 * sc * wl, Math.trunc(seed) + 41, 1);
        const base = sk;
        sk = Float64Array.from(ns, (x) => base + Number(varySkew) * x);
    }
    const ds = s[1] - s[0];
    let mult = new Float64Array(n).fill(1.0);
    const neck = orZero(minNeckM);
    let local = null;
    for (let it = 0; it < 60; it++) {
        const am = Float64Array.from(amp, (x, i) => x * mult[i]);
        const theta = kinoshitaTheta(phase, am, sk, Number(flat));
        local = _integrate(theta, ds);
        if (neck <= 0.0) break;
        const pairs = _closePairs(local, s, neck, 3.0 * neck);
        if (!pairs.length) break;
        // a loop whose limbs come closer than the neck: its amplitude shrinks a little (a smooth dip over the arc
        // between the two points), until every neck is at least min_neck_m wide
        for (const [a, b] of pairs) {
            const lo = s[a], hi = s[b];
            const pad = 0.25 * (hi - lo) + 2.0 * ds;
            const pd = Math.max(pad, 1e-9);
            const next = new Float64Array(n);
            for (let i = 0; i < n; i++) {
                const t = Math.min(Math.max(Math.min(s[i] - (lo - pad), (hi + pad) - s[i]) / pd, 0.0), 1.0);
                next[i] = mult[i] * (1.0 - 0.05 * t * t * (3.0 - 2.0 * t));
            }
            mult = next;
        }
    }
    // the mean direction of a varying train drifts a little: turn it back onto +x
    const d0 = local[n - 1][0] - local[0][0], d1 = local[n - 1][1] - local[0][1];
    const a = -Math.atan2(d1, d0);
    const ca = Math.cos(a), sa = Math.sin(a);
    local = local.map(([x, y]) => [x * ca + y * -sa, x * sa + y * ca]);
    let anchor = null;
    if (centre === 'axis') {
        let k0 = 0;
        for (let i = 1; i < n; i++) if (Math.abs(s[i]) < Math.abs(s[k0])) k0 = i;
        const lim = (2.0 * wl) / sig;
        const lat = [];
        for (let i = 0; i < n; i++) if (Math.abs(local[i][0] - local[k0][0]) <= lim) lat.push(local[i][1]);
        anchor = [local[k0][0], 0.5 * (percentile64(lat, 5) + percentile64(lat, 95))];
    } else if (centre !== 'course') {
        throw new Error(`river_path centre '${centre}' is 'course' or 'axis'`);
    }
    return _place(local, through, flowAzimuthDeg, s, 0.0, anchor);
}

/** A polyline extended straight past both ends (along its end segments) by lengthM. */
export function extend(points, lengthM) {
    const p = points.map(([x, y]) => [Number(x), Number(y)]);
    if (p.length < 2) throw new Error('a river polyline needs at least two points');
    let a = [p[0][0] - p[1][0], p[0][1] - p[1][1]];
    let b = [p[p.length - 1][0] - p[p.length - 2][0], p[p.length - 1][1] - p[p.length - 2][1]];
    const la = Math.max(Math.hypot(a[0], a[1]), 1e-9), lb = Math.max(Math.hypot(b[0], b[1]), 1e-9);
    a = [a[0] / la, a[1] / la];
    b = [b[0] / lb, b[1] / lb];
    return [[p[0][0] + a[0] * lengthM, p[0][1] + a[1] * lengthM], ...p,
        [p[p.length - 1][0] + b[0] * lengthM, p[p.length - 1][1] + b[1] * lengthM]];
}

/** Cumulative arc length of a course (Float64Array, 0 at its first point). */
export function arcLength(points) {
    const out = new Float64Array(points.length);
    for (let i = 1; i < points.length; i++) {
        out[i] = out[i - 1] + Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
    }
    return out;
}

/** The polyline at (about) equal arc steps. */
export function resample(points, stepM) {
    const s = arcLength(points);
    const n = Math.max(Math.trunc(Math.ceil(s[s.length - 1] / stepM)) + 1, 2);
    const t = linspace(0.0, s[s.length - 1], n);
    const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]);
    return Array.from(t, (v) => [npInterp(v, s, xs), npInterp(v, s, ys)]);
}

/** The course's geometry (rivers.py metrics): arc length, chord, sinuosity (arc / chord), the bends (local extremes
 * of the lateral offset from the chord), the down-valley spacing of every second apex (the meander wavelength), the
 * amplitude, and the closest approach of two parts of the course more than 1.5 local wavelengths of arc apart. */
export function metrics(points, wavelengthHint = null) {
    const p = points;
    const s = arcLength(p);
    const N = p.length;
    const cx = p[N - 1][0] - p[0][0], cy = p[N - 1][1] - p[0][1];
    const chord = Math.hypot(cx, cy);
    const ux = cx / Math.max(chord, 1e-9), uy = cy / Math.max(chord, 1e-9);
    const vx = -uy, vy = ux;
    const lat = Float64Array.from(p, ([x, y]) => (x - p[0][0]) * vx + (y - p[0][1]) * vy);
    const along = Float64Array.from(p, ([x, y]) => (x - p[0][0]) * ux + (y - p[0][1]) * uy);
    const sm = convolveSame(lat, new Float64Array(9).fill(1.0 / 9.0));
    const d = new Float64Array(sm.length - 1);
    for (let i = 0; i < d.length; i++) d[i] = sm[i + 1] - sm[i];
    let ext = [];
    for (let i = 0; i + 1 < d.length; i++) {
        if ((d[i] > 0 && d[i + 1] <= 0) || (d[i] < 0 && d[i + 1] >= 0)) ext.push(i + 1);
    }
    ext = ext.filter((e) => e > 5 && e < N - 6);
    let wl = [];
    if (ext.length > 3) {
        const ap = ext.filter((_e, i) => i % 2 === 0).map((e) => along[e]);
        for (let i = 1; i < ap.length; i++) wl.push(ap[i] - ap[i - 1]);
    }
    const absMedian = (xs) => {
        const a = Float64Array.from(xs, Math.abs).sort();
        const n = a.length;
        return n % 2 ? a[(n - 1) / 2] : (a[n / 2 - 1] + a[n / 2]) / 2;
    };
    const send = s[N - 1];
    const q = resample(p, Math.max(send / 4000.0, 1.0));
    const sq = arcLength(q);
    const gap = 1.5 * (wavelengthHint ? wavelengthHint
        : (wl.length ? absMedian(wl) * Math.max(send / Math.max(chord, 1e-9), 1.0) : send / 4.0));
    let neck = Infinity;
    const step = Math.max(1, Math.floor(q.length / 1500));
    const qq = q.filter((_x, i) => i % step === 0), ss = Array.from(sq).filter((_x, i) => i % step === 0);
    for (let i = 0; i < qq.length; i++) {
        for (let j = 0; j < qq.length; j++) {
            if (Math.abs(ss[j] - ss[i]) > gap) neck = Math.min(neck, Math.hypot(qq[j][0] - qq[i][0], qq[j][1] - qq[i][1]));
        }
    }
    return { arc_m: send, chord_m: chord, sinuosity: send / Math.max(chord, 1e-9), bends: ext.length,
        wavelength_m: wl.length ? absMedian(wl) : NaN, amplitude_m: 0.5 * (percentile64(lat, 95) - percentile64(lat, 5)),
        neck_m: neck };
}


// --------------------------------------------------------------------------------------------- on a level ---

const KERNELS = new WeakMap();
function kernelOf(R, name) {
    let m = KERNELS.get(R);
    if (!m) KERNELS.set(R, (m = new Map()));
    let k = m.get(name);
    if (!k) m.set(name, (k = R.kernel(name)));
    return k;
}

const F32 = new Float32Array(1), U32 = new Uint32Array(F32.buffer);
const ulp32 = (x) => {
    const f = Math.fround(Math.abs(x));
    F32[0] = f;
    U32[0] += 1;
    return F32[0] - f;
};

/** rivers.py channel(): the channel on a level, on the GPU. { mask (r32f: 1 on the channel's cells, those within
 * max(width_m, min_cells cell) / 2 of the course), seg (r32ui: the nearest segment k, 0xffffffff off every box), t
 * (r32f: the parameter along it, so the arc length there is s_k + t L_k), d (r32f: the distance, +inf off every box),
 * cells (the channel's cell count), decided (the cells decided again in doubles), half, points } (module doc). Only
 * the course's segments near the window are visited, each over its own box, as numpy visits them. */
export async function channel(level, points, widthM, minCells = MIN_CELLS, R = null) {
    if (!R) throw new Error('channel: the GPU runner is needed (the fifth argument)');
    const n = level.n, cell = Number(level.cell);
    const half = 0.5 * Math.max(Number(widthM), minCells * cell);
    const reach = half + cell;
    const s = arcLength(points);
    const x1 = level.x0 + level.side, y1 = level.y0 + level.side;
    const segs = [];
    let extent = 0.0;
    for (let k = 0; k + 1 < points.length; k++) {
        const [ax, ay] = points[k], [bx, by] = points[k + 1];
        const lox = Math.min(ax, bx) - reach, loy = Math.min(ay, by) - reach;
        const hix = Math.max(ax, bx) + reach, hiy = Math.max(ay, by) + reach;
        if (!(hix >= level.x0 && lox <= x1 && hiy >= level.y0 && loy <= y1)) continue;
        const i0 = Math.max(Math.trunc(Math.floor((lox - level.x0) / cell - 0.5)), 0);
        const i1 = Math.min(Math.trunc(Math.ceil((hix - level.x0) / cell - 0.5)) + 1, n);
        const j0 = Math.max(Math.trunc(Math.floor((loy - level.y0) / cell - 0.5)), 0);
        const j1 = Math.min(Math.trunc(Math.ceil((hiy - level.y0) / cell - 0.5)) + 1, n);
        if (i1 <= i0 || j1 <= j0) continue;
        const vx = bx - ax, vy = by - ay;
        const L2 = Math.max(vx * vx + vy * vy, 1e-12);
        // the box's first cell centre as numpy computes it, as an offset from the segment's start (small: exact
        // enough in float32), so the kernel's arithmetic stays on offsets of a few hundred metres
        const X0 = level.x0 + (i0 + 0.5) * cell, Y0 = level.y0 + (j0 + 0.5) * cell;
        segs.push({ k, i0, i1, j0, j1, ox: X0 - ax, oy: Y0 - ay, vx, vy, L2 });
        extent = Math.max(extent, (i1 - i0) * cell + Math.abs(X0 - ax), (j1 - j0) * cell + Math.abs(Y0 - ay));
    }
    const fields = { mask: R.field(n, n, 1), seg: R.field(n, n, 1, null, 'u32'), t: R.field(n, n, 1), d: R.field(n, n, 1) };
    const out = { ...fields, cells: 0, decided: 0, half, points, s };
    // the segments binned per 16 x 16 tile of cells, in course order (none near the window: every tile empty, so no
    // channel, numpy's d inf and s nan)
    const tx = Math.ceil(n / 16), ty = Math.ceil(n / 16);
    const counts = new Uint32Array(tx * ty + 1);
    for (const g of segs) {
        for (let b = g.j0 >> 4; b <= (g.j1 - 1) >> 4; b++) for (let a = g.i0 >> 4; a <= (g.i1 - 1) >> 4; a++) counts[b * tx + a + 1]++;
    }
    for (let i = 1; i < counts.length; i++) counts[i] += counts[i - 1];
    const fill = counts.slice(0, tx * ty);
    const list = new Uint32Array(Math.max(counts[tx * ty], 1));
    segs.forEach((g, q) => {
        for (let b = g.j0 >> 4; b <= (g.j1 - 1) >> 4; b++) for (let a = g.i0 >> 4; a <= (g.i1 - 1) >> 4; a++) list[fill[b * tx + a]++] = q;
    });
    const ns = Math.max(segs.length, 1);
    const segi = new Int32Array(8 * ns), segf = new Float32Array(8 * ns);
    segs.forEach((g, q) => {
        segi.set([g.k, g.i0, g.i1, g.j0, g.j1], 8 * q);
        segf.set([g.ox, g.oy, g.vx, g.vy, g.L2], 8 * q);
    });
    // the bound of the float32 distance's error on these offsets (a few roundings of values up to `extent` metres),
    // with a wide margin: the cells within it of the half width are decided again in doubles
    const eps = segs.length ? 64 * ulp32(extent + half) : 0.0;
    const own = [R.field(1, counts.length, 1, counts, 'u32'), R.field(1, list.length, 1, list, 'u32'),
        R.field(1, segi.length, 1, segi, 'i32'), R.field(1, 2 * ns, 4, segf)];
    const amb = R.field(n, n, 1, null, 'u32'), cnt = R.field(1, 2, 1, null, 'u32');
    R.run(kernelOf(R, 'strata/river_channel'), { tstart: own[0], tseg: own[1], segi: own[2], segf: own[3] },
        { outD: fields.d, outK: fields.seg, outT: fields.t, outM: fields.mask, outA: amb, cnt },
        { uCell: cell, uHalf: half, uEps: eps, uTilesX: tx });
    const [c] = await R.readAll([cnt]);
    out.cells = c[0];
    if (c[1] > 0) {
        // the few cells near the half width: numpy's own float64 decision (its boxes, its order, its strict `<`)
        const P = prims(R);
        const nz = await P.nonzero(amb);
        const idx = await R.readRange(nz.index, 0, nz.n);
        nz.index.destroy();
        const fixK = new Uint32Array(nz.n), fixI = new Uint32Array(nz.n), fixV = new Float32Array(4 * nz.n);
        for (let r = 0; r < nz.n; r++) {
            const cellIx = idx[r], i = cellIx % n, j = Math.floor(cellIx / n);
            const X = level.x0 + (i + 0.5) * cell, Y = level.y0 + (j + 0.5) * cell;
            let d = Infinity, kk = NONE, tt = 0.0;
            for (const g of segs) {
                if (i < g.i0 || i >= g.i1 || j < g.j0 || j >= g.j1) continue;
                const [ax, ay] = points[g.k];
                const t = Math.min(Math.max(((X - ax) * g.vx + (Y - ay) * g.vy) / g.L2, 0.0), 1.0);
                const dd = Math.hypot(X - (ax + t * g.vx), Y - (ay + t * g.vy));
                if (dd < d) { d = dd; kk = g.k; tt = t; }
            }
            fixI[r] = cellIx;
            fixK[r] = kk;
            fixV.set([tt, d, d <= half ? 1.0 : 0.0, 0.0], 4 * r);
            if (d <= half) out.cells++;
        }
        const fI = R.field(1, nz.n, 1, fixI, 'u32'), fK = R.field(1, nz.n, 1, fixK, 'u32'), fV = R.field(1, nz.n, 4, fixV);
        R.run(kernelOf(R, 'strata/river_fix'), { fidx: fI, fk: fK, fv: fV },
            { outD: fields.d, outK: fields.seg, outT: fields.t, outM: fields.mask }, { uCount: nz.n },
            [Math.ceil(nz.n / 64), 1, 1]);
        for (const f of [fI, fK, fV]) f.destroy();
        out.decided = nz.n;
    }
    for (const f of [...own, amb, cnt]) f.destroy();
    return out;
}

/** Release a channel's fields (a channel() result, or a cache that holds one). */
export function releaseChannel(ch) {
    const c = ch?.channel ?? ch;
    if (!c) return;
    for (const k of ['mask', 'seg', 't', 'd']) if (c[k] && !c[k].destroyed) c[k].destroy();
    if (ch?.channel) ch.channel = null;
}

/** The schedule's value (fraction of the fall done) at time fraction t (piecewise linear, clamped). */
export function scheduleAt(schedule, t) {
    const xs = schedule.map((r) => Number(r[0])), ys = schedule.map((r) => Number(r[1]));
    return npInterp(Number(t), xs, ys);
}


/** A course with its channel width, final bed profile and schedule (what 'river_path' keeps in ctx.shared). The bed
 * at arc length s, at the fraction f of the fall done:
 *     bed(s, f) = top(s) - f (top(s) - final(s)),   final(s) = bed_m - gradient (s - s_through) - pool(s)
 * top(s) is the starting surface along the course (sampled once, on the level where the run starts). pool(s) is the
 * pool-and-riffle scour (pool_spacing_m, pool_depth_m; 0 without pools): on the hero levels the full pool depth
 * everywhere (a smooth trench under the pools' water, never a closed basin). stages: [[f, points, s_through], ...] a
 * growing course (growth < 1): the course used at a fall fraction f is the last stage whose f is at most it; the
 * final course is `points`. */
export class River {
    constructor(points, widthM, bedM, gradient, schedule, sThrough, top = null, spec = null, stages = null, seed = 0) {
        this.width_m = Number(widthM);
        this.bed_m = Number(bedM);
        this.gradient = Number(gradient);
        this.schedule = schedule.map((r) => r.map(Number));
        this.spec = { ...(spec ?? {}) };
        this.pool = [orZero(_p(this.spec, 'pool_spacing_m')), orZero(_p(this.spec, 'pool_depth_m')),
            Number(_p(this.spec, 'pool_riffle')), Number(_p(this.spec, 'pool_jitter'))];
        this.pool_seed = Math.trunc(seed);
        this._crest_cache = null;
        this.final_course = [points, Number(sThrough)];
        this.stages = (stages ?? []).map(([f, p, s0]) => [Number(f), p, Number(s0)]);
        this.top_field = null;
        this._use(this.final_course[0], this.final_course[1]);
        this.top = top === null ? null : Float64Array.from(top);
        this._pinsMade = [];
    }

    /** The riffles' crests (the pools' downstream lips), arc lengths along the final course, ascending: one every
     * pool_spacing_m x exp(pool_jitter N(0, 1)) (clipped to 0.5-2 spacings), from the course's start to its end, the
     * same on every level (world arc length, a seeded draw). null without pools. */
    crests() {
        const sp = this.pool[0];
        if (sp <= 0.0) return null;
        if (this._crest_cache === null) {
            const sa = arcLength(this.final_course[0]);
            const sEnd = sa[sa.length - 1];
            const rng = defaultRng(this.pool_seed * 4421 + 613);
            const n = Math.trunc(sEnd / (0.5 * sp)) + 4;
            const z = rng.standard_normal(n);
            const steps = Float64Array.from(z, (v) => sp * Math.min(Math.max(Math.exp(this.pool[3] * v), 0.5), 2.0));
            const c0 = -sp * rng.uniform(0.0, 1.0);
            const c = [c0 + 0.0];
            let acc = 0.0;
            for (let i = 0; i < n; i++) {
                acc += steps[i];
                c.push(c0 + acc);
            }
            this._crest_cache = Float64Array.from(c.filter((v) => v <= sEnd + 2.0 * sp));
        }
        return this._crest_cache;
    }

    /** 0..1 along the final course (doubles, for a few points: the GPU evaluates it per cell in river_pins.wgsl). */
    poolScour(s) {
        const c = this.crests();
        const one = (x) => {
            if (c === null || c.length < 2) return 0.0;
            const k = Math.min(Math.max(searchsorted(c, x, 'right') - 1, 0), c.length - 2);
            const u = Math.min(Math.max((x - c[k]) / (c[k + 1] - c[k]), 0.0), 1.0);
            const r = Math.min(Math.max(this.pool[2], 0.0), 0.9);
            const v = Math.min(Math.max((u - r) / (1.0 - r), 0.0), 1.0);
            return u > r ? Math.sin(Math.PI * v ** 0.75) ** 0.6 : 0.0;
        };
        return typeof s === 'number' ? one(s) : Float64Array.from(s, one);
    }

    /** The final bed at arc length s (a number or an array): the bed line minus the pool scour (smooth: minus the full
     * pool depth, the hero levels' trench). */
    final(s, smooth = false) {
        const depth = this.pool[0] > 0.0 ? this.pool[1] : 0.0;
        const one = (x) => {
            const line = this.bed_m - this.gradient * (x - this.s_through);
            if (depth <= 0.0) return line;
            return line - depth * (smooth ? 1.0 : this.poolScour(x));
        };
        return typeof s === 'number' ? one(s) : Float64Array.from(s, one);
    }

    _use(points, sThrough) {
        this.points = points;
        this.s = arcLength(points);
        this.s_through = sThrough;
        this.top = null;
        this._dropTable();
        if (this.top_field !== null) this._sample();
    }

    /** Switch to the course of fall fraction f (a growing river); true when it changed. */
    courseAt(f) {
        if (!this.stages.length) return false;
        let pick = this.final_course;
        if (f < 1.0 - 1e-9) for (const [fk, p, s0] of this.stages) if (fk <= f + 1e-9) pick = [p, s0];
        if (pick[0] === this.points) return false;
        this._use(pick[0], pick[1]);
        return true;
    }

    _sample() {
        const [h, shape, x0, y0, cell] = this.top_field;
        this.top = Float64Array.from(Gd.sampleBilinear(h, shape, x0, y0, cell, this.points.map((p) => p[0]),
            this.points.map((p) => p[1])));
        this._dropTable();
    }

    /** top(s): the surface h of `level` along the course (bilinear, clamped to the window), from the level's height
     * (a GPU field, read back once, or a host array of n * n values); kept, so a growing course's later stages sample
     * the same starting surface. */
    async sampleTop(level, h) {
        const host = ArrayBuffer.isView(h) ? h : await h.runner.read(h);
        this.top_field = [Float64Array.from(host), [level.n, level.n], level.x0, level.y0, level.cell];
        this._sample();
        return this.top;
    }

    /** bed(s, f) in doubles at a few arc lengths (the GPU evaluates it per cell in pins()). */
    bed(s, f, smooth = false) {
        const fin = this.final(s, smooth);
        if (this.top === null || f >= 1.0) return fin;
        const one = (x, fi) => {
            const top = Math.max(npInterp(x, this.s, this.top), fi);
            return top - f * (top - fi);
        };
        return typeof s === 'number' ? one(s, fin) : Float64Array.from(s, (x, i) => one(x, fin[i]));
    }

    // the course's per-point table for the bed kernel (river_pins.wgsl): [top_k, fin_k, gradient L_k, L_k],
    // [s_k - c[j_k], j_k, 0, 0] per point, and the crests' spacings; made in doubles, rounded once
    _bedTable(R, smooth) {
        const replaced = Object.prototype.hasOwnProperty.call(this, 'final');
        const key = `${smooth}|${replaced}`;
        if (this._table && this._table.key === key && this._table.top === this.top && this._table.final === this.final &&
            !this._table.f.destroyed) return this._table;
        if (this._table) this._dropTable();
        const p = this.points, s = this.s, N = p.length;
        const c = this.crests();
        const pools = !replaced && this.pool[0] > 0.0 && this.pool[1] > 0.0 && c !== null && c.length >= 2;
        const fin = replaced ? Float64Array.from(this.final(s, smooth)) : null;
        const tab = new Float32Array(8 * N);
        for (let k = 0; k < N; k++) {
            const L = k + 1 < N ? Math.sqrt(Math.max((p[k + 1][0] - p[k][0]) ** 2 + (p[k + 1][1] - p[k][1]) ** 2, 1e-12)) : 0.0;
            const top = this.top !== null ? this.top[k] : 0.0;
            const f0 = replaced ? fin[k] : this.bed_m - this.gradient * (s[k] - this.s_through);
            let dk = 0.0, jk = 0;
            if (pools) {
                jk = Math.min(Math.max(searchsorted(c, s[k], 'right') - 1, 0), c.length - 2);
                dk = s[k] - c[jk];
            }
            tab.set([top, f0, this.gradient * L, L, dk, jk, 0.0, 0.0], 8 * k);
        }
        const cw = new Float32Array(Math.max(pools ? c.length - 1 : 1, 1));
        if (pools) for (let j = 0; j + 1 < c.length; j++) cw[j] = c[j + 1] - c[j];
        this._table = { key, top: this.top, final: this.final, f: R.field(1, 2 * N, 4, tab), cw: R.field(1, cw.length, 1, cw),
            nc: pools ? c.length : 0, mode: replaced ? 1 : 0 };
        return this._table;
    }

    _dropTable() {
        if (this._table) for (const k of ['f', 'cw']) if (!this._table[k].destroyed) this._table[k].destroy();
        this._table = null;
    }

    /** base pins ({ pin_w, pin_h, A_in, qs_in } GPU fields) with the channel pinned at bed(s, f): [pins, mask] (module
     * doc). opts.cache ({}) keeps the level's channel between calls (releaseChannel(cache) frees it); opts.hold: a
     * child level's border-band weights (1 at its edge, 0 from 16 cells in): there the channel's pin eases from the
     * parent's surface (the base pin) to the bed, so the channel meets its parent's coarser channel at the seam. */
    async pins(level, basePins, f, opts = {}) {
        const cache = opts.cache ?? null, hold = opts.hold ?? null;
        const R = basePins.pin_w.runner;
        this.courseAt(f);
        const key = `${level.x0},${level.y0},${level.cell},${level.n}`;
        let ch;
        if (cache !== null && cache.key === key && cache.points === this.points && cache.channel) {
            ch = cache.channel;
        } else {
            ch = await channel(level, this.points, this.width_m, MIN_CELLS, R);
            if (cache !== null) {
                releaseChannel(cache);
                Object.assign(cache, { key, points: this.points, channel: ch });
            }
        }
        const smooth = level.role === 'hero';
        const tab = this._bedTable(R, smooth);
        const D = Gd.dummies(R);
        const pw = R.field(level.n, level.n, 1), ph = R.field(level.n, level.n, 1);
        const useTop = this.top !== null && f < 1.0;
        R.run(kernelOf(R, 'strata/river_pins'), { mask: ch.mask, segk: ch.seg, segt: ch.t, bw: basePins.pin_w,
            bh: basePins.pin_h, hold: hold ?? D.f1, crs: tab.f, cw: tab.cw }, { outW: pw, outH: ph },
        { uF: Number(f), uDepth: tab.nc ? this.pool[1] : (smooth && tab.mode === 0 && this.pool[0] > 0.0 ? this.pool[1] : 0.0),
            uRiffle: Math.min(Math.max(this.pool[2], 0.0), 0.9), uNc: tab.nc,
            uMode: [tab.mode, useTop ? 1 : 0, smooth ? 1 : 0, hold ? 1 : 0] });
        if (cache === null) for (const k of ['seg', 't', 'd']) ch[k].destroy();
        return [{ ...basePins, pin_w: pw, pin_h: ph }, ch.mask];
    }

    toDict() {
        return { points: this.points.map((p) => [...p]), width_m: this.width_m, bed_m: this.bed_m, gradient: this.gradient,
            schedule: this.schedule, s_through: this.s_through, top: this.top === null ? null : Array.from(this.top), spec: this.spec };
    }
}
River.prototype.course_at = River.prototype.courseAt;
River.prototype.sample_top = River.prototype.sampleTop;
River.prototype.pool_scour = River.prototype.poolScour;
River.prototype.to_dict = River.prototype.toDict;


/** The course of a 'river_path' stage's parameters: [points, s_through]. extentM is the coarsest level's side: a
 * generated course runs three times that, a polyline is extended that far past its ends. */
export function course(params, seed = 0, extentM = 10000.0) {
    const kind = _p(params, 'kind');
    const sSeed = Math.trunc(seed) + Math.trunc(Number(_p(params, 'seed')));
    const through = _p(params, 'through').map(Number);
    const az = Number(_p(params, 'flow_azimuth_deg'));
    const length = Number(_p(params, 'length_m') || 3.0 * Number(extentM));
    let pts;
    if (kind === 'polyline') {
        pts = extend(_p(params, 'points'), Number(extentM) * 1.5);
        pts = resample(pts, Number(_p(params, 'step_m') || 5.0));
    } else if (kind === 'walk') {
        pts = walk(through, az, length, Number(_p(params, 'wiggle_deg')), Number(_p(params, 'wiggle_wavelength_m')), sSeed,
            Number(_p(params, 'step_m') || 10.0));
    } else if (kind === 'kinoshita') {
        pts = kinoshita(through, az, length, Number(_p(params, 'wavelength_m')), Number(_p(params, 'sinuosity')),
            _p(params, 'theta0_deg'), Number(_p(params, 'skew')), Number(_p(params, 'flat')), Number(_p(params, 'vary')), sSeed,
            _p(params, 'step_m'), Number(_p(params, 'vary_scale')), Number(_p(params, 'vary_skew')),
            orZero(_p(params, 'min_neck_m')), String(_p(params, 'centre')));
    } else {
        throw new Error(`river_path kind '${kind}' is 'walk', 'kinoshita' or 'polyline'`);
    }
    const s = arcLength(pts);
    let k = 0, dk = Infinity;
    for (let i = 0; i < pts.length; i++) {
        const d = Math.hypot(pts[i][0] - through[0], pts[i][1] - through[1]);
        if (d < dk) { dk = d; k = i; }
    }
    return [pts, s[k]];
}

/** A growing Kinoshita course's stages [[f, points, s_through], ...]: the bend amplitude theta0 from growth x its
 * final value to the final, the arc wavelength scaled with the sinuosity so every bend keeps its down-valley place. */
export function growthCourses(params, seed = 0, extentM = 10000.0) {
    const g0 = Number(_p(params, 'growth'));
    const k = Math.max(Math.trunc(Number(_p(params, 'growth_stages'))), 2);
    if (_p(params, 'kind') !== 'kinoshita' || g0 >= 1.0) return [];
    const skew = Number(_p(params, 'skew')), flat = Number(_p(params, 'flat'));
    const t0 = _p(params, 'theta0_deg');
    const thF = t0 !== null && t0 !== undefined ? Number(t0) * DEG : theta0For(Number(_p(params, 'sinuosity')), skew, flat);
    const sigF = kinoshitaSinuosity(thF, skew, flat);
    const wlDv = Number(_p(params, 'wavelength_m')) / sigF;
    const out = [];
    for (let i = 0; i < k - 1; i++) {                          // the last stage is the final course itself
        const f = i / (k - 1);
        const th = thF * (g0 + (1.0 - g0) * f);
        const sig = kinoshitaSinuosity(th, skew, flat);
        const p = { ...(params ?? {}), theta0_deg: th * RAD, wavelength_m: wlDv * sig, growth: 1.0 };
        const [pts, s0] = course(p, seed, extentM);
        out.push([f, pts, s0]);
    }
    return out;
}

/** The River of a 'river_path' stage's parameters. */
export function makeRiver(params, seed = 0, extentM = 10000.0) {
    const [pts, s0] = course(params, seed, extentM);
    const sch = _p(params, 'schedule');
    return new River(pts, Number(_p(params, 'width_m')), Number(_p(params, 'bed_m')), Number(_p(params, 'gradient')), sch, s0,
        null, { ...(params ?? {}) }, growthCourses(params, seed, extentM), Math.trunc(seed) + Math.trunc(Number(_p(params, 'seed'))));
}


// -------------------------------------------------------------------------------------------------- the op ---

/** Stage 'river_path' (module doc): the course into ctx.shared.river (a River) and the level's pins with the channel
 * at its final bed. On the fresh start of a run (the coarsest level's first pass) it also samples the starting
 * surface along the course (the top the layered-rock stage lowers the bed from). */
export async function opRiverPath(fields, level, params, seed = 0, ctx = null) {
    const FL = await import('./fluvial.js');
    ctx = await FL.asContext(ctx, fields, level);
    const R = ctx.device ?? fields.h?.runner ?? fields.R;
    const extent = ctx.plan && ctx.plan.length ? Number(ctx.plan[0].side) : Number(level.side);
    let rv = ctx.shared.river;
    if (!(rv instanceof River) || !pyEqual(rv.spec, { ...(params ?? {}) }) || (rv.seed ?? null) !== Math.trunc(seed)) {
        rv = makeRiver({ ...(params ?? {}) }, seed, extent);
        rv.seed = Math.trunc(seed);
        ctx.shared.river = rv;
    }
    if (ctx.fresh && 'h' in fields) await rv.sampleTop(level, fields.h);
    // the pins this River made for the previous pass served only that pass's later stages
    for (const f of rv._pinsMade) if (!f.destroyed) f.destroy();
    rv._pinsMade = [];
    const own = ctx.pins === null || ctx.pins === undefined;
    const base = own ? FL.edgePins(R, level.n, 'h' in fields ? fields.h : null, ctx.sea_level ?? null) : ctx.pins;
    // a child level (its pins are its parent's border band): the channel eases into the parent's at the seam
    const [pins, m] = await rv.pins(level, base, 1.0, { hold: ctx.role === 'refine' ? base.pin_w : null });
    if (own) { base.pin_w.destroy(); base.pin_h.destroy(); }
    rv._pinsMade = [pins.pin_w, pins.pin_h];
    ctx.pins = pins;
    const cells = (await prims(R).stats(m)).nonzero;
    fields.river = m;
    ctx.log(`[terrain.rivers] ${params?.kind ?? DEFAULTS.kind} course, ${pyFormat(rv.s[rv.s.length - 1] / 1000, '.1f')} km, ` +
        `channel ${pyFormat(rv.width_m, 'g')} m: ${cells} cells on ${level.n}^2 @ ${pyFormat(level.cell, '.3g')} m`);
    return fields;
}

opRiverPath.evolves = true;             // run.js: on every coarse-to-fine pass, so each pass gets its pins
opRiverPath.takesCtx = true;

export const OPS = { river_path: opRiverPath };

export {
    _smoothNoise1d as _smooth_noise_1d, kinoshitaTheta as kinoshita_theta, kinoshitaSinuosity as kinoshita_sinuosity,
    theta0For as theta0_for, _closePairs as _close_pairs, arcLength as arc_length, scheduleAt as schedule_at,
    growthCourses as growth_courses, makeRiver as make_river, opRiverPath as op_river_path,
};
