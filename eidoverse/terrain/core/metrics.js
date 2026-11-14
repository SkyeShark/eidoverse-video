// Port of blender/eidoblend/terrain/core/metrics.py at f90c6fc.
//
// The judge's generic numbers for a heightfield in metres (design section 10, item 2), for t.metrics(). The Python
// judge stays the authority on a terrain (PORT_PLAN.md 6.3: the port's saves are judged by the Blender judge); this
// module gives a scene the same numbers without Python, every per-cell operation on the GPU (kernels/metrics/,
// core/prims.js, core/grid.js).
//
//     import * as M from './core/metrics.js';
//     const h8 = M.toPixel(h, cell, 8.0);           // box-average to the reference's pixel first (slope depends on it)
//     const m = await M.metrics(h8, 8.0);           // the object below: Python's keys, Python's units
//     await M.slopeStats(h, cell);                  // the reference JSONs' shape_stats keys
//
// h is a core/gpu.js field of one float channel, row 0 south. metrics() keys (degrees, metres, fractions of the area),
// as metrics.py's: pixel_m, extent_m, relief_m, relief_robust_m, mean_m, hypsometric_integral, slope_p10 / p50 / p90 /
// p99 / mean, frac_slope_lt5 / gt30 / gt40 / gt50, depression_area_frac, depression_count, depressions_per_100km2,
// depression_threshold_m, spectrum_slope, spectrum_knee_m, spectrum_slope_long / _short, spectrum_peak_m,
// anisotropy_2 / _4 / _8, anisotropy, cliff_pair_frac.
//
// Where this differs from metrics.py, and why (tests/parity/metrics_test.mjs checks each against metrics.py on
// reference DEMs):
//   - numpy holds the field in float64; here it is the float32 field itself. Minimum, maximum, relief and the
//     height percentiles are exact (order statistics of the same float32 values, numpy 2.3.4's float64 arithmetic for
//     the call form: core/prims.js percentile with dtype 'float64'). Slopes are float32 (core/grid.js), so their
//     percentiles are numpy's rule on float32 slopes, and a count against a limit (the slope fractions, the cliff
//     pairs, a depression at the threshold) can differ by the cells that sit within a rounding of the limit.
//   - Means are sums of (value - a first estimate of the mean), float32 in a fixed tree: the rounding then applies
//     to the small residual, not to the sum of large numbers.
//   - The plane radial_spectrum takes off comes from three sums over centred coordinates (on a regular grid the
//     same least-squares plane as numpy's lstsq of [i, j, 1]); the transform is core/prims.js rfft2 (float32).
//   - A coefficient's band is decided in integers (kernels/metrics/spectrum_bands.wgsl), so none changes band by a
//     float32 rounding. The first and the last band edges are exactly a coefficient's wavenumber (1 / extent and the
//     Nyquist frequency), where numpy's own choice turns on the last bit of 10 ** log10(k); here it turns on V8's.
//     Neither band is inside the wavelengths the summary reads (4 pixels to a quarter of the extent).
//   - aspect_harmonics: orders 2, 4 and 8 (the ones metrics.py uses), from double-angle identities instead of
//     cos(m arctan2(gy, gx)) (kernels/metrics/aspect_terms.wgsl).
//   - polyfit and lstsq of the spectrum's summary (at most 48 points) are a regression and a QR in doubles; numpy's
//     are LAPACK's. The same least-squares solutions to rounding.
//   - label() and fillDepressions() are core/prims.js's (the GPU forms of metrics.py label and solvers/hydro.py
//     fill_depressions), exported here under metrics.py's names.

import * as grid from './grid.js';
import { f32AtOrBelow, listShape, prims } from './prims.js';

const RAD = Math.PI / 180.0;
const cover = (f) => [Math.ceil(f.w / 16), Math.ceil(f.h / 16), 1];
const gcd = (a, b) => (b ? gcd(b, a % b) : a);

function field(h, what) {
    if (!h || !h.runner || h.kind !== 'f32') throw new TypeError(`${what}: a float GPU field (core/gpu.js) is needed`);
    return h.runner;
}

// The mean of one channel as z0 + sum(value - z0) / n, z0 a first float32 estimate: { mean, min, max, n }.
async function meanOf(f, channel = 0) {
    const R = f.runner, P = prims(R);
    const s = await P.stats(f, { channel });
    const z0 = Math.fround(s.mean);
    let src = f;
    if (channel !== 0 || f.channels !== 1) throw new Error('metrics: a one-channel field is needed');
    const d = grid.arith(R, 'affine', src, null, { amp: 1.0, off: -z0 });
    const r = await P.stats(d);
    d.destroy();
    return { mean: z0 + r.sum / s.count, min: s.min, max: s.max, n: s.count };
}

// the number of cells where f OP value
async function countWhere(f, op, value, channel = 0) {
    const P = prims(f.runner);
    const flags = P.where(f, op, value, { channel });
    const c = (await P.statsU32(flags)).nonzero;
    flags.destroy();
    return c;
}


// -------------------------------------------------------------------------------------------- pixel matching ---

/** h box-averaged to `pixelM` pixels (exact area weights; core/grid.js resampleBox). A new field. */
export function toPixel(h, cell, pixelM, nOut = null) {
    return grid.resampleBox(h, cell, pixelM, nOut);
}


// ----------------------------------------------------------------------------------------------- slopes ---

/** The reference JSONs' shape_stats over a field, same definitions and rounding-free: relief_m, mean_m,
 * hypsometric_integral, slope_deg_p10 / p50 / p90 / p99, slope_deg_mean. */
export async function slopeStats(h, cell) {
    const P = prims(field(h, 'slope_stats'));
    const s = grid.slopeDeg(h, cell);
    const hm = await meanOf(h), sm = await meanOf(s);
    const p = await P.percentile(s, [10, 50, 90, 99], { dtype: 'float64' });
    s.destroy();
    const lo = hm.min, hi = hm.max, mean = hm.mean;
    return { relief_m: hi - lo, mean_m: mean, hypsometric_integral: (mean - lo) / Math.max(hi - lo, 1e-6),
        slope_deg_p10: p[0], slope_deg_p50: p[1], slope_deg_p90: p[2], slope_deg_p99: p[3], slope_deg_mean: sm.mean };
}


// ------------------------------------------------------------------------------------ closed depressions ---

/** { filled, outlet }: every cell's spill level (the priority flood's result) with the open edge as the outlet
 * (solvers/hydro.py fill_depressions, as core/prims.js computes it: bit for bit). */
export async function fillDepressions(h, wrap = [false, false], seaLevel = null) {
    return await prims(field(h, 'fill_depressions')).fillDepressions(h, { wrap, seaLevel });
}

/** The 8-connected components of the nonzero cells of a u32 mask: { labels (0 the background, 1..n), count },
 * numbered as metrics.py label numbers them (core/prims.js label). */
export async function label(mask) {
    return await prims(mask.runner).label(mask);
}

/** Closed depressions deeper than max(1 m, 0.2 % of relief): { frac (area fraction), count, thr (m), depth (the
 * field filled - h; the caller's to destroy) }. */
export async function depressions(h, cell, relief = null, wrap = [false, false]) {
    const R = field(h, 'depressions'), P = prims(R);
    if (relief == null) {
        const s = await P.stats(h);
        relief = s.max - s.min;
    }
    const thr = Math.max(1.0, 0.002 * relief);
    const { filled } = await P.fillDepressions(h, { wrap });
    const depth = grid.arith(R, 'sub', filled, h);
    filled.destroy();
    const mask = P.where(depth, '>', f32AtOrBelow(1e-6));
    const { labels, count } = await P.label(mask);
    mask.destroy();
    if (count === 0) {
        labels.destroy();
        return { frac: 0.0, count: 0, thr, depth };
    }
    const D = grid.dummies(R);
    const acc = P.list(count + 1, 'u32');
    const un = { uThr: f32AtOrBelow(thr), uCount: count };
    R.run('metrics/label_depth', { lab: labels, depth }, { acc, outF: D.u1 }, { uMode: 0, ...un }, cover(h));
    const cells = R.field(h.h, h.w, 1, null, 'u32');
    R.run('metrics/label_depth', { lab: labels, depth }, { acc, outF: cells }, { uMode: 1, ...un }, cover(h));
    const [lh, lw] = listShape(count + 1);
    const kept = R.field(lh, lw, 1, null, 'u32');
    R.run('metrics/label_depth', { lab: labels, depth }, { acc, outF: kept }, { uMode: 2, ...un }, cover(kept));
    const nCells = (await P.statsU32(cells)).nonzero, nKept = (await P.statsU32(kept)).nonzero;
    for (const f of [labels, acc, cells, kept]) f.destroy();
    return { frac: nCells / (h.h * h.w), count: nKept, thr, depth };
}


// -------------------------------------------------------------------------------------------- the spectrum ---

// np.hanning(M)
function hanning(M) {
    const w = new Float64Array(M);
    if (M === 1) {
        w[0] = 1.0;
        return w;
    }
    for (let k = 0; k < M; k++) w[k] = 0.5 + 0.5 * Math.cos((Math.PI * (2 * k + 1 - M)) / (M - 1));
    return w;
}

/** The radially averaged power spectrum: [wavelength_m, power] (two Float64Arrays) per log-spaced band of
 * wavenumber, from the extent down to two pixels. The field is detrended (least-squares plane) and Hann-windowed
 * first. */
export async function radialSpectrum(h, cell, nbins = 48) {
    const R = field(h, 'radial_spectrum'), P = prims(R);
    const ny = h.h, nx = h.w, n = nx * ny;
    const D = grid.dummies(R);
    const z0 = Math.fround((await P.stats(h)).mean);
    const ic = (nx - 1) / 2, jc = (ny - 1) / 2;
    const terms = R.field(ny, nx, 4);
    const un = { uZ0: z0, uIc: ic, uJc: jc };
    R.run('metrics/detrend', { z: h, wx: D.f1, wy: D.f1 }, { outF: terms }, { uMode: 0, ...un, uA: 0, uB: 0, uD: 0 });
    const s0 = await P.stats(terms, { channel: 0 }), s1 = await P.stats(terms, { channel: 1 }),
        s2 = await P.stats(terms, { channel: 2 });
    terms.destroy();
    // the centred regressors are orthogonal: sum (i - ic)^2 over the grid = ny nx (nx^2 - 1) / 12
    const a = nx > 1 ? s1.sum / ((ny * nx * (nx * nx - 1)) / 12) : 0.0;
    const b = ny > 1 ? s2.sum / ((nx * ny * (ny * ny - 1)) / 12) : 0.0;
    const d = s0.sum / n;
    const wx64 = hanning(nx), wy64 = hanning(ny);
    const wx = R.field(1, nx, 1, Float32Array.from(wx64)), wy = R.field(1, ny, 1, Float32Array.from(wy64));
    const win = R.field(ny, nx, 4);
    R.run('metrics/detrend', { z: h, wx, wy }, { outF: win }, { uMode: 1, ...un, uA: a, uB: b, uD: d });
    const F = P.rfft2(win);
    let sx = 0.0, sy = 0.0;
    for (const v of wx64) sx += v * v;
    for (const v of wy64) sy += v * v;
    const w2 = sx * sy;
    // np.logspace(log10(kmin), log10(kmax), nbins + 1): 10 ** linspace, the last point the stop itself
    const kmin = 1.0 / (Math.max(nx, ny) * cell), kmax = 0.5 / cell;
    const l0 = Math.log10(kmin), l1 = Math.log10(kmax), step = (l1 - l0) / nbins;
    const edges = new Float64Array(nbins + 1);
    for (let t = 0; t <= nbins; t++) edges[t] = Math.pow(10.0, t === nbins ? l1 : t * step + l0);
    // a coefficient's k^2 times (cell nx ny / g)^2 is the integer m = jj^2 (nx / g)^2 + i^2 (ny / g)^2
    const g = gcd(nx, ny), scale = (cell * nx * ny) / g;
    const words = new Uint32Array(2 * (nbins + 1));
    for (let t = 0; t <= nbins; t++) {
        const M = BigInt(Math.ceil((edges[t] * scale) ** 2));
        words[2 * t] = Number(M >> 32n);
        words[2 * t + 1] = Number(M & 0xFFFFFFFFn);
    }
    const [eh, ew] = listShape(words.length);
    const pad = new Uint32Array(eh * ew);
    pad.set(words);
    const edgeList = R.field(eh, ew, 1, pad, 'u32');
    const ub = { uNy: ny, uA: (nx / g) ** 2, uB: (ny / g) ** 2 };
    const rows = R.field(ny, nbins, 2);
    R.run('metrics/spectrum_bands', { src: F, edges: edgeList }, { outF: rows }, { uMode: 0, ...ub });
    const bands = R.field(1, nbins, 2);
    R.run('metrics/spectrum_bands', { src: rows, edges: edgeList }, { outF: bands }, { uMode: 1, ...ub });
    const got = await R.read(bands);
    for (const f of [wx, wy, win, F, edgeList, rows, bands]) f.destroy();
    const wl = [], pw = [];
    for (let t = 0; t < nbins; t++) {
        const tot = got[2 * t], cnt = got[2 * t + 1];
        if (cnt > 0) {
            wl.push(1.0 / Math.sqrt(edges[t + 1] * edges[t]));
            pw.push(((tot / cnt) * (cell * cell)) / Math.max(w2, 1e-12));
        }
    }
    return [Float64Array.from(wl), Float64Array.from(pw)];
}

// least squares of y on the columns of X (a few columns, a few dozen rows) by modified Gram-Schmidt: the coefficients
function lstsq(X, y) {
    const m = y.length, k = X.length;
    const Q = X.map((c) => Float64Array.from(c));
    const Rm = Array.from({ length: k }, () => new Float64Array(k));
    for (let j = 0; j < k; j++) {
        for (let i = 0; i < j; i++) {
            let dot = 0.0;
            for (let r = 0; r < m; r++) dot += Q[i][r] * Q[j][r];
            Rm[i][j] = dot;
            for (let r = 0; r < m; r++) Q[j][r] -= dot * Q[i][r];
        }
        let nrm = 0.0;
        for (let r = 0; r < m; r++) nrm += Q[j][r] * Q[j][r];
        nrm = Math.sqrt(nrm);
        Rm[j][j] = nrm;
        if (nrm > 0) for (let r = 0; r < m; r++) Q[j][r] /= nrm;
    }
    const qty = new Float64Array(k);
    for (let j = 0; j < k; j++) for (let r = 0; r < m; r++) qty[j] += Q[j][r] * y[r];
    const c = new Float64Array(k);
    for (let j = k - 1; j >= 0; j--) {
        let v = qty[j];
        for (let i = j + 1; i < k; i++) v -= Rm[j][i] * c[i];
        c[j] = Rm[j][j] > 0 ? v / Rm[j][j] : 0.0;
    }
    return c;
}

/** [slope, knee_m, slope_long, slope_short, peak_m] of a radial spectrum over wavelengths from 4 pixels to a
 * quarter of the extent (at most 48 points: plain numbers, in doubles). */
export function spectrumSummary(wl, P, cell, extent) {
    const x = [], y = [];
    for (let i = 0; i < wl.length; i++) {
        if (wl[i] >= 4.0 * cell && wl[i] <= extent / 4.0 && P[i] > 0) {
            x.push(Math.log10(1.0 / wl[i]));
            y.push(Math.log10(P[i]));
        }
    }
    const n = x.length;
    if (n < 6) return [NaN, NaN, NaN, NaN, NaN];
    let mx = 0.0, my = 0.0;
    for (let i = 0; i < n; i++) { mx += x[i]; my += y[i]; }
    mx /= n;
    my /= n;
    let sxx = 0.0, sxy = 0.0;
    for (let i = 0; i < n; i++) { sxx += (x[i] - mx) * (x[i] - mx); sxy += (x[i] - mx) * (y[i] - my); }
    const slope = sxy / sxx, icept = my - slope * mx;
    let best = Infinity, knee = null;
    const ones = new Float64Array(n).fill(1.0);
    for (let i = 3; i < n - 3; i++) {                          // a broken power law, continuous at the knee
        const xk = x[i];
        const lo = x.map((v) => Math.min(v - xk, 0.0)), hi = x.map((v) => Math.max(v - xk, 0.0));
        const c = lstsq([ones, lo, hi], y);
        let r = 0.0;
        for (let q = 0; q < n; q++) r += (c[0] + c[1] * lo[q] + c[2] * hi[q] - y[q]) ** 2;
        if (r < best) {
            best = r;
            knee = [xk, c[1], c[2]];
        }
    }
    let arg = 1, top = -Infinity;
    for (let i = 1; i < n - 1; i++) {
        const resid = y[i] - (slope * x[i] + icept);
        if (resid > top) { top = resid; arg = i; }
    }
    return [slope, 1.0 / 10 ** knee[0], knee[1], knee[2], 1.0 / 10 ** x[arg]];
}


// --------------------------------------------------------------------------------------------- anisotropy ---

/** { m: |sum w e^(i m theta)| / sum w }: the m-fold Fourier amplitudes of the aspect histogram, theta the gradient
 * direction and w its magnitude (tan slope), over the cells steeper than minSlopeDeg. orders: of 2, 4 and 8. */
export async function aspectHarmonics(h, cell, minSlopeDeg = 10.0, orders = [2, 4, 8]) {
    const R = field(h, 'aspect_harmonics'), P = prims(R);
    for (const m of orders) if (![2, 4, 8].includes(m)) throw new Error(`aspect_harmonics: orders of 2, 4 and 8, got ${m}`);
    const { gx, gy } = grid.gradient(h, cell);
    const A = R.field(h.h, h.w, 4), B = R.field(h.h, h.w, 4);
    R.run('metrics/aspect_terms', { gx, gy }, { outA: A, outB: B }, { uTan: f32AtOrBelow(Math.tan(minSlopeDeg * RAD)) });
    const sum = async (f, channel) => (await P.stats(f, { channel })).sum;
    const tot = await P.stats(A, { channel: 0 });
    const out = {};
    if (tot.nonzero === 0) {
        for (const m of orders) out[m] = 0.0;
    } else {
        const where = { 2: [[A, 1], [A, 2]], 4: [[A, 3], [B, 0]], 8: [[B, 1], [B, 2]] };
        for (const m of orders) {
            const [[fc, cc], [fs, cs]] = where[m];
            out[m] = Math.hypot(await sum(fc, cc), await sum(fs, cs)) / tot.sum;
        }
    }
    for (const f of [gx, gy, A, B]) f.destroy();
    return out;
}

/** [A4, A8]: the grid-direction anisotropy of the design (4-fold and 8-fold aspect harmonics). */
export async function aspectAnisotropy(h, cell, minSlopeDeg = 10.0) {
    const a = await aspectHarmonics(h, cell, minSlopeDeg, [4, 8]);
    return [a[4], a[8]];
}

/** The fraction of 8-neighbour pairs steeper than `deg` degrees. */
export async function cliffPairs(h, cell, deg = 80.0) {
    const R = field(h, 'cliff_pairs'), P = prims(R);
    const flags = R.field(h.h, h.w, 4);
    R.run('metrics/cliff_flags', { h }, { outF: flags },
        { uTan: f32AtOrBelow(Math.tan(deg * RAD)), uCell: cell, uDiag: Math.hypot(1, 1) * cell });
    let steep = 0;
    for (let c = 0; c < 4; c++) steep += (await P.stats(flags, { channel: c })).nonzero;
    flags.destroy();
    const H = h.h, W = h.w;
    const all = H * (W - 1) + (H - 1) * W + 2 * (H - 1) * (W - 1);
    return steep / Math.max(all, 1);
}


// --------------------------------------------------------------------------------------------- everything ---

/** The generic numbers of a heightfield in metres at `cell` metres per pixel (see the top of this file). opts:
 * withDepressions, withSpectrum (both true by default). */
export async function metrics(h, cell, opts = {}) {
    const P = prims(field(h, 'metrics'));
    const ny = h.h, nx = h.w, n = nx * ny;
    const s = grid.slopeDeg(h, cell);
    const hm = await meanOf(h), sm = await meanOf(s);
    const lo = hm.min, hi = hm.max, mean = hm.mean;
    const [p05, p995] = await P.percentile(h, [0.5, 99.5], { dtype: 'float64' });
    const p = await P.percentile(s, [10, 50, 90, 99], { dtype: 'float64' });
    const out = {
        pixel_m: cell, extent_m: [nx * cell, ny * cell],
        relief_m: hi - lo, relief_robust_m: p995 - p05, mean_m: mean,
        hypsometric_integral: (mean - lo) / Math.max(hi - lo, 1e-9),
        slope_p10: p[0], slope_p50: p[1], slope_p90: p[2], slope_p99: p[3], slope_mean: sm.mean,
        frac_slope_lt5: (await countWhere(s, '<', 5)) / n, frac_slope_gt30: (await countWhere(s, '>', 30)) / n,
        frac_slope_gt40: (await countWhere(s, '>', 40)) / n, frac_slope_gt50: (await countWhere(s, '>', 50)) / n,
    };
    s.destroy();
    if (opts.withDepressions ?? true) {
        const d = await depressions(h, cell, hi - lo);
        d.depth.destroy();
        const areaKm2 = (n * cell * cell) / 1e6;
        Object.assign(out, { depression_area_frac: d.frac, depression_count: d.count,
            depressions_per_100km2: (d.count / Math.max(areaKm2, 1e-12)) * 100.0, depression_threshold_m: d.thr });
    }
    if (opts.withSpectrum ?? true) {
        const [wl, pw] = await radialSpectrum(h, cell);
        const [sl, knee, sLong, sShort, peak] = spectrumSummary(wl, pw, cell, Math.min(nx, ny) * cell);
        Object.assign(out, { spectrum_slope: sl, spectrum_knee_m: knee, spectrum_slope_long: sLong,
            spectrum_slope_short: sShort, spectrum_peak_m: peak });
    }
    const a = await aspectHarmonics(h, cell);
    Object.assign(out, { anisotropy_2: a[2], anisotropy_4: a[4], anisotropy_8: a[8], anisotropy: Math.max(a[4], a[8]),
        cliff_pair_frac: await cliffPairs(h, cell) });
    return out;
}
