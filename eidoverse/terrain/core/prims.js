// Port of the numpy code the Blender edition runs over whole levels (blender/eidoblend/terrain at f90c6fc), as GPU
// building blocks (PORT_PLAN.md section 3.4). No Blender file has this role: each primitive names the numpy function
// it replaces, and tests/core_runner/prims_test.mjs checks it against that function (tests/core_runner/
// prims_expected.py runs the Blender functions themselves).
//
//     import * as G from './core/gpu.js';
//     import { prims } from './core/prims.js';
//     const R = await G.init(), P = prims(R);
//     await P.stats(f)                         // { min, max, sum, count, nonzero, mean }: a.min(), a.max(), a.sum()
//     await P.percentile(f, [10, 50, 90])      // np.percentile (numpy 2.3.4's linear method), from exact order
//                                              // statistics; a number q is numpy's scalar call (float32 arithmetic)
//     await P.quantile(f, 0.25)                // np.quantile, its own scalar rule; P.median(f): np.median
//     P.cumsum(list, { exclusive })            // np.cumsum on integers; P.bincount(keys, n); await P.nonzero(flags)
//     P.argsort(f), P.lexsort([k0, k1])        // np.argsort(kind='stable'), np.lexsort: a stable radix sort
//     P.pathSteps(rec)                         // solvers/hydro.py path_steps and _terminal_of: pointer jumping
//     await P.label(mask)                      // core/metrics.py label: 8-connected components, numpy's numbering
//     await P.fillDepressions(h, { wrap, seaLevel })   // solvers/hydro.py fill_depressions: the spill surface
//     await P.flatDistance(w, { wrap, seaLevel })      // solvers/hydro.py flat_distance
//     P.gaussianBlur(f, sigma, { mode })       // solvers/hillslope.py ('reflect') / masks.py ('periodic') gaussian_blur
//     P.boxBlur(f, r, { wrap, passes, axes })  // solvers/hydro.py box_blur, solvers/hydraulic.py _box
//     P.dilate(f, r)                           // solvers/volcanic.py _dilate
//     P.rfft2(f), P.fft2(f)                    // np.fft.rfft2 / fft2 (core/metrics.py radial_spectrum): radix-2
//                                              // Stockham stages, Bluestein's chirp for other lengths
//
// Fields are core/gpu.js fields. A list (items in a row, not a grid) is any field read in row-major order with a
// count of items; list(n) makes one. Methods that only record GPU work return fields at once; methods that need a
// number from the GPU (a count, a convergence test) are async and wait once per test (about 16 ms, plan 4.5). A
// returned field belongs to the caller (destroy() it); inputs are never changed.
//
// What is exact (plan 2.3, 5.3): min, max, counts, order statistics, percentiles and medians (numpy's arithmetic on
// the exact order statistics), scans, histograms, compaction, sorts, pointer jumping, labels, the fill, the flat
// distance and the dilation, bit for bit. Sums are float32 sums in a fixed tree (the same number every run). The
// Gaussian and box blurs are float32 against numpy's float64 (within 1e-5 of the range), and so is the FFT (within
// 1e-5 of the largest coefficient). Jump flooding is not here: it is the Blender kernels jump_flood and coast_jfa,
// ported by their packages; the masks' decimated Gaussian is grid.js's box_down, this Gaussian and its upsample.
//
// Deviations from the Blender code (plan 3.4: per-texel work runs as GPU compute), each checked against the numpy
// function it replaces:
//   - fill_depressions' priority flood over the D8 basin graph is a min-max relaxation over the cells, whose fixed
//     point is the same spill surface (kernels/prims/fill_relax.wgsl); flat_distance's frontier loop and label's
//     union-find are relaxations to the same fixed points (bfs_relax, label_step).
//   - np.percentile partitions; here a radix select finds the same order statistics.
//   - The FFT blurs are direct circular convolutions with the FFT's own kernel (gauss_pass.wgsl); the running-sum
//     box blurs are direct window sums (box_pass.wgsl).
//   - info['basins'] of fill_depressions (the number of D8 basins) is not computed: nothing the port runs reads it.

export const LINE = 4096;                               // kernels/prims/lib.wgsl LINE
const SORT_BLOCK = 512;                                 // sort_count.wgsl BLOCK
const SCAN_BLOCK = 256;                                 // scan_up.wgsl BLOCK
const SELECT_RANKS = 16;                                // select_hist.wgsl: statistics per pass
const NONE = 0xFFFFFFFF;
const OPS = { '<': 0, '<=': 1, '==': 2, '>=': 3, '>': 4, '!=': 5 };

/** Work groups for one invocation per block, `blocks` blocks laid out in rows of LINE (lib.wgsl line_index). */
export function lineGroups(blocks) {
    const rows = Math.ceil(Math.max(blocks, 1) / LINE);
    return [Math.ceil(Math.min(Math.max(blocks, 1), LINE) / 16), Math.ceil(rows / 16), 1];
}

// work groups covering a field's cells (a dispatch whose first image is not the field it walks)
const cover = (f) => [Math.ceil(f.w / 16), Math.ceil(f.h / 16), 1];

/** The shape of a list field holding n items: one row up to LINE items, else rows of LINE. */
export function listShape(n) {
    n = Math.max(1, n);
    return n <= LINE ? [1, n] : [Math.ceil(n / LINE), LINE];
}

const F32 = new Float32Array(1), U32 = new Uint32Array(F32.buffer);

/** The largest float32 at or below x: a float32 value v satisfies v <= x (float64) exactly when v <= this. */
export function f32AtOrBelow(x) {
    const f = Math.fround(x);
    if (f <= x || Number.isNaN(x)) return f;
    F32[0] = f;
    if (f > 0) U32[0] -= 1;
    else if (f < 0) U32[0] += 1;
    else U32[0] = 0x80000001;                           // below zero: the negative float closest to it
    return F32[0];
}

/** A float from the sort key lib.wgsl fkey gives it. */
export function keyToFloat(k) {
    if (k === NONE) return NaN;
    U32[0] = (k & 0x80000000) ? (k & 0x7FFFFFFF) : (~k >>> 0);
    return F32[0];
}

// An in-place radix-2 FFT in float64 of a power-of-two length: Bluestein's chirp table, one per length (not per
// cell; the fields' transforms run on the GPU).
function fft64(re, im) {
    const n = re.length;
    for (let i = 1, j = 0; i < n; i++) {
        let bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) {
            [re[i], re[j]] = [re[j], re[i]];
            [im[i], im[j]] = [im[j], im[i]];
        }
    }
    for (let len = 2; len <= n; len *= 2) {
        const th = (-2 * Math.PI) / len;
        for (let k = 0; k < len / 2; k++) {
            const wr = Math.cos(th * k), wi = Math.sin(th * k);
            for (let i = k; i < n; i += len) {
                const j = i + len / 2;
                const xr = re[j] * wr - im[j] * wi, xi = re[j] * wi + im[j] * wr;
                re[j] = re[i] - xr;
                im[j] = im[i] - xi;
                re[i] += xr;
                im[i] += xi;
            }
        }
    }
}

/** masks.py _good_size: the smallest m >= n whose prime factors are 2, 3 and 5 (a fast FFT length). */
export function goodSize(n) {
    for (let m = n; ; m++) {
        let k = m;
        for (const p of [2, 3, 5]) while (k % p === 0) k /= p;
        if (k === 1) return m;
    }
}

export class Prims {
    constructor(R) {
        this.R = R;
        this.dummyF = R.field(1, 1, 1);
        this.dummyU = R.field(1, 1, 1, null, 'u32');
        this.counter = R.field(1, 1, 1, null, 'u32');      // the relaxations' count of changed tiles
        this._taps = new Map();                            // (sigma, N) -> a Gaussian's circular kernel
        this._fft = new Map();                             // the FFT's twiddles and Bluestein tables, per length
        this.dispatchCounts = {};                          // relaxation -> dispatches of its last run
    }

    // ------------------------------------------------------------------------------------------------ lists ---

    /** A list field for n items of `kind`, zeroed or holding `data` (n values; the rest of the field is zero). */
    list(n, kind = 'u32', data = null) {
        const [h, w] = listShape(n);
        if (data != null) {
            if (data.length !== h * w) {
                const Arr = data.constructor;
                const full = new Arr(h * w);
                full.set(data);
                data = full;
            }
        }
        return this.R.field(h, w, 1, data, kind);
    }

    _count(f, count) { return count ?? f.h * f.w; }

    // ------------------------------------------------------------------------------------------- reductions ---

    // the reduction tree of one channel of a float field, left on the GPU: { S (min, max, sum), N, C } of 1 x 1
    _reduceF(f, channel = 0, mask = null, count = null) {
        const R = this.R;
        let h = Math.ceil(f.h / 8), w = Math.ceil(f.w / 8);
        let S = R.field(h, w, 4), N = R.field(h, w, 1, null, 'u32'), C = R.field(h, w, 1, null, 'u32');
        R.run('prims/reduce_first', { src: f, mask: mask ?? this.dummyF }, { outS: S, outN: N, outC: C },
            { uChannel: channel, uMask: mask ? 1 : 0, uCount: this._count(f, count) });
        while (h > 1 || w > 1) {
            h = Math.ceil(h / 8);
            w = Math.ceil(w / 8);
            const S2 = R.field(h, w, 4), N2 = R.field(h, w, 1, null, 'u32'), C2 = R.field(h, w, 1, null, 'u32');
            R.run('prims/reduce_next', { inS: S, inN: N, inC: C }, { outS: S2, outN: N2, outC: C2 }, {});
            S.destroy(); N.destroy(); C.destroy();
            S = S2; N = N2; C = C2;
        }
        return { S, N, C };
    }

    /** One channel of a float field reduced: { min, max, sum, count, nonzero, mean } (a.min(), a.max(), a.sum(),
     * a.size, np.count_nonzero(a)). opts: channel, mask (a float field: only cells where it is > 0), count (a
     * list's items). min and max are exact; the sum is float32 in a fixed tree. NaN min / max with no cells. */
    async stats(f, opts = {}) {
        const r = this._reduceF(f, opts.channel ?? 0, opts.mask ?? null, opts.count ?? null);
        const [S, N, C] = await this.R.readAll([r.S, r.N, r.C]);
        r.S.destroy(); r.N.destroy(); r.C.destroy();
        const n = N[0];
        return { min: n ? S[0] : NaN, max: n ? S[1] : NaN, sum: S[2], count: n, nonzero: C[0], mean: n ? S[2] / n : NaN };
    }

    // the integer reduction tree, left on the GPU: { Lo, Hi, C } of 1 x 1
    _reduceU(f, count = null) {
        const R = this.R;
        let h = Math.ceil(f.h / 8), w = Math.ceil(f.w / 8);
        let Lo = R.field(h, w, 1, null, 'u32'), Hi = R.field(h, w, 1, null, 'u32'), C = R.field(h, w, 1, null, 'u32');
        R.run('prims/reduce_u32', { inLo: f, inHi: f, inC: f }, { outLo: Lo, outHi: Hi, outC: C },
            { uFirst: 1, uCount: this._count(f, count) });
        while (h > 1 || w > 1) {
            h = Math.ceil(h / 8);
            w = Math.ceil(w / 8);
            const L2 = R.field(h, w, 1, null, 'u32'), H2 = R.field(h, w, 1, null, 'u32'), C2 = R.field(h, w, 1, null, 'u32');
            R.run('prims/reduce_u32', { inLo: Lo, inHi: Hi, inC: C }, { outLo: L2, outHi: H2, outC: C2 }, { uFirst: 0, uCount: 0 });
            Lo.destroy(); Hi.destroy(); C.destroy();
            Lo = L2; Hi = H2; C = C2;
        }
        return { Lo, Hi, C };
    }

    /** An integer field (or list) reduced: { min, max, nonzero } (min NONE and max 0 with no items). */
    async statsU32(f, opts = {}) {
        const r = this._reduceU(f, opts.count ?? null);
        const [lo, hi, c] = await this.R.readAll([r.Lo, r.Hi, r.C]);
        r.Lo.destroy(); r.Hi.destroy(); r.C.destroy();
        return { min: lo[0], max: hi[0], nonzero: c[0] };
    }

    /** a OP value cell by cell, as a u32 field of 1 / 0 (OP one of < <= == >= > !=); index: true gives each
     * cell's row-major index where it holds and NONE where it does not. */
    where(f, op, value, opts = {}) {
        if (!(op in OPS)) throw new Error(`where: an operator of ${Object.keys(OPS).join(' ')}, got '${op}'`);
        const out = this.R.field(f.h, f.w, 1, null, 'u32');
        this.R.run('prims/where', { src: f }, { outF: out },
            { uOp: OPS[op], uValue: value, uChannel: opts.channel ?? 0, uIndex: opts.index ? 1 : 0 });
        return out;
    }

    /** np.argmin of one channel: the row-major index of the first smallest value (two waits). */
    async argmin(f, opts = {}) {
        const { min } = await this.stats(f, opts);
        const idx = this.where(f, '==', min, { channel: opts.channel ?? 0, index: true });
        const { min: first } = await this.statsU32(idx);
        idx.destroy();
        return first;
    }

    // --------------------------------------------------------------------------------- order statistics ---

    /** The exact k-th smallest values of one channel (ranks 0-based, ties counted: numpy's sorted order), as
     * float32 numbers: a radix select of four 8-bit passes over lib.wgsl's float keys. opts: channel, mask, count. */
    async orderStatistics(f, ranks, opts = {}) {
        const R = this.R;
        const out = new Array(ranks.length);
        const states = [];
        for (let g = 0; g < ranks.length; g += SELECT_RANKS) {
            const part = ranks.slice(g, g + SELECT_RANKS);
            const init = new Uint32Array(part.length * 2);
            part.forEach((k, i) => { init[2 * i + 1] = k; });
            let state = R.field(part.length, 2, 1, init, 'u32');
            const hist = R.field(part.length, 256, 1, null, 'u32');
            for (const shift of [24, 16, 8, 0]) {
                R.clear(hist);
                R.run('prims/select_hist', { src: f, mask: opts.mask ?? this.dummyF, state }, { hist },
                    { uShift: shift, uRanks: part.length, uChannel: opts.channel ?? 0, uMask: opts.mask ? 1 : 0,
                        uCount: this._count(f, opts.count) }, cover(f));
                const next = R.field(part.length, 2, 1, null, 'u32');
                R.run('prims/select_pick', { hist, state }, { outState: next }, { uShift: shift });
                state.destroy();
                state = next;
            }
            hist.destroy();
            states.push({ g, state, n: part.length });
        }
        const got = await R.readAll(states.map((s) => s.state));
        states.forEach((s, i) => {
            for (let r = 0; r < s.n; r++) out[s.g + r] = keyToFloat(got[i][2 * r]);
            s.state.destroy();
        });
        return out;
    }

    async _n(f, opts) {
        if (opts.mask) return (await this.stats(opts.mask, { mask: opts.mask })).count;
        return this._count(f, opts.count);
    }

    /** np.percentile(a, q) with numpy 2.3.4's 'linear' method (Blender 5.2's numpy), from the exact order
     * statistics around (n - 1) q / 100, in numpy's own arithmetic, which depends on the call: numpy 2.3.4 divides q
     * by a.dtype.type(100), so for float32 data a Python number q (a JS number here) runs the whole interpolation in
     * float32 and returns a float32, while a list of q (a JS array) runs it in float64 with the difference b - a in
     * float32; opts.dtype 'float64' (data numpy held in float64, of float32 values) is float64 throughout. A q that is
     * a numpy float64 scalar in the Blender call takes the list arithmetic: pass [q]. opts: channel, mask (a float
     * field: cells where it is > 0, as a[mask]), count, dtype. */
    percentile(f, q, opts = {}) {
        return this._quantiles(f, q, opts, true);
    }

    /** np.quantile(a, q) with numpy 2.3.4's 'linear' method: q in [0, 1]. numpy 2.3.4 casts a Python number q (or a
     * numpy float64, a subclass of float) to the data's dtype, so for float32 data a JS number q runs the
     * interpolation in float32 and returns a float32; a list of q (a JS array) runs it in float64 with the difference
     * b - a in float32; opts.dtype 'float64' is float64 throughout. opts as percentile's. */
    quantile(f, q, opts = {}) {
        return this._quantiles(f, q, opts, false);
    }

    // percentile (pct true: q in [0, 100], divided by dtype(100)) and quantile (q in [0, 1], cast to the dtype)
    async _quantiles(f, q, opts, pct) {
        const what = pct ? 'percentile' : 'quantile';
        const scalar = typeof q === 'number';
        const qs = scalar ? [q] : Array.from(q);
        const top = pct ? 100 : 1;
        for (const v of qs) {
            if (!(v >= 0 && v <= top)) throw new Error(`${what}: ${pct ? 'Percentiles' : 'Quantiles'} must be in the range [0, ${top}]`);
        }
        const n = await this._n(f, opts);
        if (!n) throw new Error(`${what}: no values (numpy raises on an empty array)`);
        const f32 = (opts.dtype ?? 'float32') === 'float32';
        const single = f32 && scalar;                          // every step rounded to float32
        const r32 = single ? Math.fround : (x) => x;
        const plan = qs.map((v) => {
            // percentile: np.true_divide(q, dtype(100)); quantile: np.asanyarray(q, dtype=a.dtype) for a number
            const quant = pct ? (single ? Math.fround(Math.fround(v) / 100) : v / 100) : (single ? Math.fround(v) : v);
            const virt = single ? Math.fround(Math.fround(n - 1) * quant) : (n - 1) * quant;
            let prev = Math.floor(virt), next = prev + 1;
            if (virt >= n - 1) prev = next = -1;               // numpy's index -1: the largest value
            const gamma = r32(virt - prev);                    // np.asanyarray(gamma, dtype=virtual_indexes.dtype)
            return { prev: prev < 0 ? n - 1 : prev, next: next < 0 ? n - 1 : next, gamma };
        });
        const want = [...new Set([...plan.flatMap((p) => [p.prev, p.next]), n - 1])].sort((a, b) => a - b);
        const vals = await this.orderStatistics(f, want, opts);
        const at = new Map(want.map((k, i) => [k, vals[i]]));
        const nan = Number.isNaN(at.get(n - 1));               // numpy: a NaN sorts last and the result is NaN
        const res = plan.map(({ prev, next, gamma }) => {
            if (nan) return NaN;
            const a = at.get(prev), b = at.get(next);
            const diff = f32 ? Math.fround(b - a) : b - a;     // _lerp: subtract(b, a) in the data's dtype
            let r = r32(a + r32(diff * gamma));
            if (gamma >= 0.5) r = r32(b - r32(diff * r32(1 - gamma)));
            return r;
        });
        return scalar ? res[0] : res;
    }

    /** np.median(a) (numpy 2.3.4 _median): the middle value, or the mean of the two middle values in the data's
     * dtype (float32 by default; opts.dtype 'float64' for data numpy held in float64). opts as percentile's. */
    async median(f, opts = {}) {
        const n = await this._n(f, opts);
        if (!n) throw new Error('median: no values');
        const ks = n % 2 ? [(n - 1) / 2] : [n / 2 - 1, n / 2];
        const v = await this.orderStatistics(f, [...ks, n - 1], opts);
        if (Number.isNaN(v[v.length - 1])) return NaN;
        if (n % 2) return v[0];
        return (opts.dtype ?? 'float32') === 'float32' ? Math.fround(Math.fround(v[0] + v[1]) / 2) : (v[0] + v[1]) / 2;
    }

    // ------------------------------------------------------------------------------- scans and histograms ---

    /** np.cumsum of a u32 list (exact modulo 2^32): inclusive by default, exclusive: true for the sum of the items
     * before each; flags: true counts each item as 1 when it is not zero. A u32 field of the list's shape. */
    cumsum(src, opts = {}) {
        const R = this.R;
        const n = this._count(src, opts.count);
        const inclusive = !opts.exclusive, bool = !!opts.flags;
        const levels = [];
        let cur = src, m = n, first = true;
        while (m > SCAN_BLOCK) {
            const nb = Math.ceil(m / SCAN_BLOCK);
            const sums = this.list(nb);
            R.run('prims/scan_up', { src: cur }, { outB: sums }, { uCount: m, uBool: first && bool ? 1 : 0 }, lineGroups(nb));
            levels.push({ src: cur, n: m, bool: first && bool });
            cur = sums;
            m = nb;
            first = false;
        }
        const top = levels.length ? R.like(cur) : R.field(src.h, src.w, 1, null, 'u32');
        R.run('prims/scan_down', { src: cur, base: this.dummyU }, { outP: top },
            { uCount: m, uTop: 1, uInclusive: !levels.length && inclusive ? 1 : 0, uBool: first && bool ? 1 : 0 }, lineGroups(1));
        let base = top;
        for (let k = levels.length - 1; k >= 0; k--) {
            const L = levels[k];
            const out = k === 0 ? R.field(src.h, src.w, 1, null, 'u32') : R.like(L.src);
            R.run('prims/scan_down', { src: L.src, base }, { outP: out },
                { uCount: L.n, uTop: 0, uInclusive: k === 0 && inclusive ? 1 : 0, uBool: L.bool ? 1 : 0 },
                lineGroups(Math.ceil(L.n / SCAN_BLOCK)));
            base.destroy();
            if (k + 1 < levels.length) levels[k + 1].src.destroy();
            base = out;
        }
        if (levels.length) cur.destroy();
        return base;
    }

    /** np.bincount(keys, minlength=n) for keys below n (a key at or above n is not counted): a u32 list of n. */
    bincount(keys, n, opts = {}) {
        const out = this.list(n);
        this.R.run('prims/histogram', { keys }, { hist: out }, { uCount: this._count(keys, opts.count) }, cover(keys));
        return out;
    }

    /** np.flatnonzero(flags): { index (a u32 list, its first n items the indices in order), n }. One wait. */
    async nonzero(flags, opts = {}) {
        const R = this.R;
        const count = this._count(flags, opts.count);
        const pos = this.cumsum(flags, { count, exclusive: true, flags: true });
        const index = this.list(count);
        R.run('prims/compact', { flags, pos }, { outI: index }, { uCount: count }, cover(flags));
        const [p, f] = await R.readParts([{ field: pos, first: count - 1, count: 1 }, { field: flags, first: count - 1, count: 1 }]);
        pos.destroy();
        return { index, n: p[0] + (f[0] !== 0 ? 1 : 0) };
    }

    // --------------------------------------------------------------------------------------------- sorting ---

    /** One channel of a float field as u32 sort keys in numpy's order (descending: true for the keys of -a). */
    floatKeys(f, opts = {}) {
        const out = this.R.field(f.h, f.w, 1, null, 'u32');
        this.R.run('prims/float_keys', { src: f }, { outK: out }, { uChannel: opts.channel ?? 0, uNegate: opts.descending ? 1 : 0 });
        return out;
    }

    /** An int32 field as u32 sort keys in its order. */
    intKeys(f) {
        const out = this.R.field(f.h, f.w, 1, null, 'u32');
        this.R.run('prims/int_keys', { src: f }, { outK: out }, {});
        return out;
    }

    /** A stable sort of u32 keys carrying u32 values (null: each item's own index): { keys, vals }, fields of the
     * keys' shape. bits: how many low bits of the keys can differ (fewer passes). Least significant digit first, 8
     * bits a pass, every pass stable: numpy's kind='stable' order. */
    sortPairs(keys, vals = null, opts = {}) {
        const R = this.R;
        const n = this._count(keys, opts.count);
        const nb = Math.ceil(n / SORT_BLOCK);
        const passes = Math.max(1, Math.ceil((opts.bits ?? 32) / 8));
        const hist = this.list(256 * nb);
        let K = keys, V = vals, iota = vals == null;
        for (let pass = 0; pass < passes; pass++) {
            const shift = 8 * pass;
            R.run('prims/sort_count', { keys: K }, { outH: hist }, { uCount: n, uShift: shift }, lineGroups(nb));
            const base = this.cumsum(hist, { count: 256 * nb, exclusive: true });
            const K2 = R.field(keys.h, keys.w, 1, null, 'u32'), V2 = R.field(keys.h, keys.w, 1, null, 'u32');
            R.run('prims/sort_scatter', { keys: K, vals: V ?? this.dummyU, base }, { outK: K2, outV: V2 },
                { uCount: n, uShift: shift, uIota: iota ? 1 : 0 }, lineGroups(nb));
            base.destroy();
            if (K !== keys) K.destroy();
            if (V && V !== vals) V.destroy();
            K = K2;
            V = V2;
            iota = false;
        }
        hist.destroy();
        return { keys: K, vals: V };
    }

    /** np.argsort(a, kind='stable') of one channel of a float field (or an int32 / u32 field): the permutation,
     * a u32 field of the field's shape. descending: true is np.argsort(-a) (floats). */
    argsort(f, opts = {}) {
        const keys = f.kind === 'f32' ? this.floatKeys(f, opts) : (f.kind === 'i32' ? this.intKeys(f) : f);
        const { keys: k, vals } = this.sortPairs(keys, null, opts);
        k.destroy();
        if (keys !== f) keys.destroy();
        return vals;
    }

    /** out[i] = src[index[i]] (numpy's a[idx]) over lists: a field of the index's shape (u32 or one float channel). */
    gather(src, index, opts = {}) {
        const R = this.R;
        if (src.kind === 'f32') {
            const out = R.field(index.h, index.w, 1);
            R.run('prims/gather_f32', { src, index }, { outG: out }, { uChannel: opts.channel ?? 0 });
            return out;
        }
        const out = R.field(index.h, index.w, 1, null, 'u32');
        R.run('prims/gather_u32', { src, index }, { outG: out }, {});
        return out;
    }

    /** np.lexsort(keys): keys are u32 key fields (floatKeys / intKeys of the columns), the last the primary order;
     * the permutation that sorts by them, ties in index order. */
    lexsort(keys, opts = {}) {
        let perm = null;
        for (const k of keys) {
            const kp = perm ? this.gather(k, perm) : k;
            const { keys: ks, vals } = this.sortPairs(kp, perm, opts);
            ks.destroy();
            if (kp !== k) kp.destroy();
            if (perm) perm.destroy();
            perm = vals;
        }
        return perm;
    }

    /** 1 at the first item of every run of equal keys in a sorted u32 list, else 0 (first[1:] = k[1:] != k[:-1]). */
    segmentHeads(keys, opts = {}) {
        const out = this.R.field(keys.h, keys.w, 1, null, 'u32');
        this.R.run('prims/segment_heads', { keys }, { outF: out }, { uCount: this._count(keys, opts.count) });
        return out;
    }

    // ------------------------------------------------------------------------------------ pointer jumping ---

    _jumpStart(rec) {
        const R = this.R;
        const P = R.pair(rec.h, rec.w, 1, null, 'u32'), D = R.pair(rec.h, rec.w, 1, null, 'u32');
        R.run('prims/jump_init', { rec }, { outP: P.src, outD: D.src }, {});
        return { P, D, rounds: Math.ceil(Math.log2(Math.max(2, rec.h * rec.w))) + 1 };
    }

    /** solvers/hydro.py path_steps(rec) and _terminal_of(rec), by pointer jumping: rec an int32 field of row-major
     * receiver indices (-1: none). { steps, terminal } (u32 fields). check: true waits once to confirm the pointers
     * settled (a cycle in rec would not; numpy's loop would stop after 64 rounds). */
    async pathSteps(rec, opts = {}) {
        const R = this.R;
        const { P, D, rounds } = this._jumpStart(rec);
        for (let r = 0; r < rounds; r++) {
            R.run('prims/jump', { ptr: P.src, dist: D.src }, { outP: P.dst, outD: D.dst }, {});
            P.swap();
            D.swap();
        }
        if (opts.check) {
            R.run('prims/jump', { ptr: P.src, dist: D.src }, { outP: P.dst, outD: D.dst }, {});
            const diff = R.field(rec.h, rec.w, 1, null, 'u32');
            R.run('prims/diff_u32', { a: P.src, b: P.dst }, { outF: diff }, {});
            const { nonzero } = await this.statsU32(diff);
            diff.destroy();
            if (nonzero) {
                P.destroy();
                D.destroy();
                throw new Error(`pathSteps: the receivers of ${nonzero} cells never reach an outlet (a cycle)`);
            }
        }
        P.dst.destroy();
        D.dst.destroy();
        return { steps: D.src, terminal: P.src };
    }

    /** The largest (min: true, smallest) of `val` along every cell's receiver path to its terminal, both ends
     * included, by pointer jumping (path maxima). rec: int32 receivers (-1 none); val: a float field. r32f. */
    pathMax(rec, val, opts = {}) {
        const R = this.R;
        const { P, D, rounds } = this._jumpStart(rec);
        D.destroy();
        const V = R.pair(rec.h, rec.w, 1);
        this._channel(val, opts.channel ?? 0, V.src);
        for (let r = 0; r < rounds; r++) {
            R.run('prims/jump_max', { ptr: P.src, val: V.src }, { outP: P.dst, outV: V.dst }, { uSign: opts.min ? -1 : 1 });
            P.swap();
            V.swap();
        }
        P.destroy();
        V.dst.destroy();
        return V.src;
    }

    // ----------------------------------------------------------------------------------------- relaxations ---

    // dispatch `step(src, dst, counted)` in chunks until the last dispatch of a chunk changes no tile
    async _relax(name, pair, step, maxDispatches = 200000) {
        const R = this.R;
        let done = 0, chunk = 8;
        for (;;) {
            R.clear(this.counter);
            for (let i = 0; i < chunk; i++) {
                step(pair.src, pair.dst, i === chunk - 1);
                pair.swap();
            }
            done += chunk;
            const [changed] = await R.readRange(this.counter, 0, 1);
            if (changed === 0) break;
            if (done >= maxDispatches) throw new Error(`${name}: not settled after ${done} dispatches`);
            chunk = Math.min(chunk * 2, 64);
        }
        this.dispatchCounts[name] = done;
        return done;
    }

    /** solvers/hydro.py fill_depressions(h, wrap, sea_level): every cell's spill level, bit for bit (float32
     * heights). h: a float field (channel 0); wrap [x, y]; seaLevel metres or null. { filled (r32f), outlet ('sea',
     * 'edge' or 'lowest basin', as numpy's info['outlet']), dispatches }. */
    async fillDepressions(h, opts = {}) {
        const R = this.R;
        const [wx, wy] = (opts.wrap ?? [false, false]).map((v) => (v ? 1 : 0));
        const seaLevel = opts.seaLevel ?? null;
        const sea = seaLevel != null ? 1 : 0, seaL = sea ? f32AtOrBelow(seaLevel) : 0;
        let seaAny = false;
        if (sea) {
            const flags = this.where(h, '<=', seaL);
            seaAny = (await this.statsU32(flags)).nonzero > 0;
            flags.destroy();
        }
        const open = !(wx && wy);
        let root = -1;
        if (!seaAny && !open) root = await this.argmin(h);
        const outlet = seaAny ? 'sea' : (open ? 'edge' : 'lowest basin');
        const W = R.pair(h.h, h.w, 1);
        const un = { uInit: 1, uWrapX: wx, uWrapY: wy, uSea: sea, uSeaLevel: seaL, uRoot: root, uCount: 0 };
        R.run('prims/fill_relax', { h, win: h }, { outW: W.src, changed: this.counter }, un);
        const dispatches = await this._relax('fill', W, (src, dst, counted) => {
            R.run('prims/fill_relax', { h, win: src }, { outW: dst, changed: this.counter },
                { ...un, uInit: 0, uCount: counted ? 1 : 0 });
        });
        W.dst.destroy();
        return { filled: W.src, outlet, dispatches };
    }

    /** solvers/hydro.py flat_distance(surface, wrap, sea_level): breadth-first steps across every flat from where
     * it drains, 0 off the flats and where nothing drains. A u32 field. */
    async flatDistance(surface, opts = {}) {
        const R = this.R;
        const [wx, wy] = (opts.wrap ?? [false, false]).map((v) => (v ? 1 : 0));
        const seaLevel = opts.seaLevel ?? null;
        const un = { uInit: 1, uSame: 1, uWrapX: wx, uWrapY: wy, uSea: seaLevel != null ? 1 : 0,
            uSeaLevel: seaLevel != null ? f32AtOrBelow(seaLevel) : 0, uCount: 0 };
        const D = R.pair(surface.h, surface.w, 1, null, 'u32');
        R.run('prims/bfs_relax', { surf: surface, seed: this.dummyU, din: D.dst }, { outD: D.src, changed: this.counter }, un);
        await this._relax('flat_distance', D, (src, dst, counted) => {
            R.run('prims/bfs_relax', { surf: surface, seed: this.dummyU, din: src }, { outD: dst, changed: this.counter },
                { ...un, uInit: 0, uCount: counted ? 1 : 0 });
        });
        R.run('prims/bfs_relax', { surf: surface, seed: this.dummyU, din: D.src }, { outD: D.dst, changed: this.counter },
            { ...un, uInit: 3, uCount: 0 });
        D.src.destroy();
        return D.dst;
    }

    /** Breadth-first steps (8-connected) from the nonzero cells of a u32 seed field, NONE where none reaches; with
     * opts.surface, steps only between cells of equal height. wrap [x, y]. A u32 field. */
    async bfs(seed, opts = {}) {
        const R = this.R;
        const [wx, wy] = (opts.wrap ?? [false, false]).map((v) => (v ? 1 : 0));
        const un = { uInit: 2, uSame: opts.surface ? 1 : 0, uWrapX: wx, uWrapY: wy, uSea: 0, uSeaLevel: 0, uCount: 0 };
        const surf = opts.surface ?? this.dummyF;
        const D = R.pair(seed.h, seed.w, 1, null, 'u32');
        R.run('prims/bfs_relax', { surf, seed, din: D.dst }, { outD: D.src, changed: this.counter }, un);
        await this._relax('bfs', D, (src, dst, counted) => {
            R.run('prims/bfs_relax', { surf, seed, din: src }, { outD: dst, changed: this.counter },
                { ...un, uInit: 0, uCount: counted ? 1 : 0 });
        });
        D.dst.destroy();
        return D.src;
    }

    /** core/metrics.py label(mask): the 8-connected components of the nonzero cells of a u32 mask, numbered 1..n in
     * the order of their smallest row-major index (numpy's np.unique of the roots), 0 for the background:
     * { labels (u32), count }. */
    async label(mask) {
        const R = this.R;
        const L = R.pair(mask.h, mask.w, 1, null, 'u32');
        R.run('prims/label_init', { mask }, { outL: L.src }, {});
        await this._relax('label', L, (src, dst, counted) => {
            R.run('prims/label_step', { lab: src }, { outL: dst, changed: this.counter }, { uCount: counted ? 1 : 0 });
        });
        const roots = L.dst;
        R.run('prims/label_final', { lab: L.src, pos: this.dummyU }, { outL: roots }, { uRoots: 1 });
        const pos = this.cumsum(roots, { exclusive: true });
        const labels = R.field(mask.h, mask.w, 1, null, 'u32');
        R.run('prims/label_final', { lab: L.src, pos }, { outL: labels }, { uRoots: 0 });
        const n = mask.h * mask.w;
        const [p, f] = await R.readParts([{ field: pos, first: n - 1, count: 1 }, { field: roots, first: n - 1, count: 1 }]);
        pos.destroy();
        L.destroy();
        return { labels, count: p[0] + f[0] };
    }

    // --------------------------------------------------------------------------------------------- filters ---

    _unitTaps() {
        if (!this._unit) this._unit = this.R.field(1, 1, 1, new Float32Array([1]));
        return this._unit;
    }

    // one channel of a float field into the r32f field `out`, exactly (a copy when it has one channel)
    _channel(f, ch, out) {
        if (f.channels === 1) {
            this.R.copy(f, out);
            return out;
        }
        this.R.run('prims/gauss_pass', { src: f, taps: this._unitTaps() }, { outB: out },
            { uAxis: 0, uLo: 0, uHi: 0, uPeriod: f.w, uPad: 0, uMode: 1, uChannel: ch });
        return out;
    }

    /** The circular kernel numpy's FFT blur applies on an axis of length N: g[m] = (1 / N) sum_k G(f_k) cos(2 pi k m
     * / N), G(f) = exp(-2 pi^2 sigma^2 f^2) on numpy's frequencies, in float64, and the offsets where it matters:
     * { field (g[0..]), lo, hi }. Cached. */
    gaussTaps(sigma, N) {
        const key = `${sigma}|${N}`;
        let t = this._taps.get(key);
        if (t) return t;
        const half = Math.floor(N / 2), d = 1.0 / N;           // numpy's fftfreq: k * (1 / (n d))
        const c = -2.0 * (Math.PI * sigma) ** 2;
        const G = new Float64Array(half + 1);
        for (let k = 0; k <= half; k++) G[k] = Math.exp(c * (k * d) * (k * d));
        const cos = new Float64Array(N);
        for (let j = 0; j < N; j++) cos[j] = Math.cos((2 * Math.PI * j) / N);
        const top = Math.ceil(N / 2) - 1;                      // the frequencies paired with their negatives
        const g = new Float64Array(half + 1);
        for (let m = 0; m <= half; m++) {
            let s = G[0];
            for (let k = 1; k <= top; k++) s += 2 * G[k] * cos[(k * m) % N];
            if (N % 2 === 0) s += G[half] * (m % 2 ? -1 : 1);
            g[m] = s / N;
        }
        // the smallest reach whose dropped taps weigh under 1e-9 (every offset once when that is the whole axis)
        let tail = 0, reach = half;
        for (let m = half; m >= 1; m--) {
            const w = (N % 2 === 0 && m === half) ? Math.abs(g[m]) : 2 * Math.abs(g[m]);
            if (tail + w > 1e-9) break;
            tail += w;
            reach = m - 1;
        }
        let lo, hi;
        if (reach >= Math.floor((N - 1) / 2)) {
            lo = -Math.floor((N - 1) / 2);
            hi = half;
        } else {
            lo = -reach;
            hi = reach;
        }
        const n = Math.max(-lo, hi) + 1;
        t = { field: this.R.field(1, n, 1, Float32Array.from(g.subarray(0, n))), lo, hi, N };
        this._taps.set(key, t);
        return t;
    }

    /** A Gaussian blur of one channel, sigma in cells, as the Blender edition's FFT blurs compute it. mode
     * 'reflect' (solvers/hillslope.py gaussian_blur: the field padded by reflection ceil(4 sigma) cells a side; no
     * blur at sigma <= 1e-6) or 'periodic' (masks.py gaussian_blur: the field taken as periodic, extended to opts.size
     * [rows, columns] by holding its last row and column, 'good' for masks.py's _good_size; volcanic.py _gauss_fft
     * with no size; no blur at sigma <= 0). An r32f field of the field's size. */
    gaussianBlur(f, sigma, opts = {}) {
        const R = this.R;
        const mode = opts.mode ?? 'reflect';
        if (mode !== 'reflect' && mode !== 'periodic') throw new Error(`gaussianBlur: mode 'reflect' or 'periodic', got '${mode}'`);
        const ch = opts.channel ?? 0;
        const out = R.field(f.h, f.w, 1);
        if ((mode === 'reflect' && sigma <= 1e-6) || (mode === 'periodic' && sigma <= 0)) return this._channel(f, ch, out);
        const size = opts.size === 'good' ? [goodSize(f.h), goodSize(f.w)] : (opts.size ?? [f.h, f.w]);
        const axis = (a) => {
            const len = a === 0 ? f.w : f.h;
            if (mode === 'reflect') {
                const pad = Math.ceil(4.0 * sigma);
                return { pad, N: len + 2 * pad, m: 0 };
            }
            const N = a === 0 ? size[1] : size[0];
            if (N < len) throw new Error(`gaussianBlur: a periodic size of ${N} is below the field's ${len}`);
            return { pad: 0, N, m: 1 };
        };
        const tmp = R.field(f.h, f.w, 1);
        for (const a of [0, 1]) {
            const { pad, N, m } = axis(a);
            const t = this.gaussTaps(sigma, N);
            R.run('prims/gauss_pass', { src: a === 0 ? f : tmp, taps: t.field }, { outB: a === 0 ? tmp : out },
                { uAxis: a, uLo: t.lo, uHi: t.hi, uPeriod: N, uPad: pad, uMode: m, uChannel: a === 0 ? ch : 0 });
        }
        tmp.destroy();
        return out;
    }

    /** A box blur of radius r cells (the mean of 2r + 1 cells per axis): opts.wrap [x, y] (an axis that wraps is
     * circular, else edges held), passes (default 1), axes 'xy' (x first: solvers/hydro.py box_blur, which runs 3
     * passes of int(max(1, radius))) or 'yx' (solvers/hydraulic.py _box: one pass, edges held). r32f. */
    boxBlur(f, r, opts = {}) {
        const R = this.R;
        const wrap = opts.wrap ?? [false, false];
        const order = (opts.axes ?? 'xy') === 'yx' ? [1, 0] : [0, 1];
        const passes = opts.passes ?? 1;
        let cur = f, ch = opts.channel ?? 0;
        for (let p = 0; p < passes; p++) {
            for (const a of order) {
                const out = R.field(f.h, f.w, 1);
                R.run('prims/box_pass', { src: cur }, { outB: out }, { uAxis: a, uRadius: r, uWrap: wrap[a] ? 1 : 0, uChannel: ch });
                if (cur !== f) cur.destroy();
                cur = out;
                ch = 0;
            }
        }
        return cur;
    }

    /** solvers/volcanic.py _dilate(a, r): the (2r + 1)^2 maximum filter, edges padded with their own values (min:
     * true, the minimum). Exact. r32f. */
    dilate(f, r, opts = {}) {
        const R = this.R;
        const tmp = R.field(f.h, f.w, 1), out = R.field(f.h, f.w, 1);
        const s = opts.min ? -1 : 1;
        R.run('prims/max_pass', { src: f }, { outB: tmp }, { uAxis: 0, uRadius: r, uSign: s, uChannel: opts.channel ?? 0 });
        R.run('prims/max_pass', { src: tmp }, { outB: out }, { uAxis: 1, uRadius: r, uSign: s, uChannel: 0 });
        tmp.destroy();
        return out;
    }

    // ------------------------------------------------------------------------------------------------- FFT ---

    // the twiddles exp(-2 pi i j / L), j < L / 2, float64 rounded once (a list of complex values)
    _twiddles(L) {
        const key = `tw${L}`;
        let t = this._fft.get(key);
        if (!t) {
            const a = new Float32Array(L);
            for (let j = 0; j < L / 2; j++) {
                const th = (-2 * Math.PI * j) / L;
                a[2 * j] = Math.cos(th);
                a[2 * j + 1] = Math.sin(th);
            }
            t = this.R.field(1, L / 2, 2, a);
            this._fft.set(key, t);
        }
        return t;
    }

    // a list of n complex ones: the chirp of a plain copy, transpose or crop through fft_chirp
    _ones(n) {
        const key = `one${n}`;
        let t = this._fft.get(key);
        if (!t) {
            const a = new Float32Array(2 * n);
            for (let j = 0; j < n; j++) a[2 * j] = 1;
            t = this.R.field(1, n, 2, a);
            this._fft.set(key, t);
        }
        return t;
    }

    // Bluestein's tables for length n: the chirp c_k = exp(-pi i k^2 / n) (k^2 reduced mod 2n exactly) and the DFT
    // of length M (a power of two >= 2n - 1) of b = conj(c) wrapped around, both from float64
    _bluestein(n) {
        const key = `bs${n}`;
        let t = this._fft.get(key);
        if (t) return t;
        let M = 1;
        while (M < 2 * n - 1) M *= 2;
        const cr = new Float64Array(n), ci = new Float64Array(n);
        for (let k = 0; k < n; k++) {
            const th = (-Math.PI * ((k * k) % (2 * n))) / n;
            cr[k] = Math.cos(th);
            ci[k] = Math.sin(th);
        }
        const br = new Float64Array(M), bi = new Float64Array(M);
        br[0] = cr[0];
        bi[0] = -ci[0];
        for (let k = 1; k < n; k++) {
            br[k] = br[M - k] = cr[k];
            bi[k] = bi[M - k] = -ci[k];
        }
        fft64(br, bi);
        const c = new Float32Array(2 * n), B = new Float32Array(2 * M);
        for (let k = 0; k < n; k++) { c[2 * k] = cr[k]; c[2 * k + 1] = ci[k]; }
        for (let k = 0; k < M; k++) { B[2 * k] = br[k]; B[2 * k + 1] = bi[k]; }
        t = { M, chirp: this.R.field(1, n, 2, c), B: this.R.field(1, M, 2, B) };
        this._fft.set(key, t);
        return t;
    }

    // log2(L) Stockham stages over the rows of A (rows x L complex); A is consumed, the result returned
    _stages(A, L, inverse) {
        const R = this.R;
        const tw = this._twiddles(L);
        let src = A, dst = R.like(A);
        const groups = [Math.ceil(L / 2 / 16), Math.ceil(A.h / 16), 1];
        for (let ns = 1; ns < L; ns *= 2) {
            R.run('prims/fft_stage', { src, tw }, { dst }, { uL: L, uNs: ns, uInverse: inverse ? 1 : 0 }, groups);
            const t = src;
            src = dst;
            dst = t;
        }
        dst.destroy();
        return src;
    }

    // fft_chirp: rows x out complex values from src (see the kernel)
    _chirp(src, chirp, rows, n, out, o) {
        const dst = this.R.field(rows, out, 2);
        this.R.run('prims/fft_chirp', { src, chirp }, { dst },
            { uN: n, uOut: out, uComplex: o.complex ? 1 : 0, uChannel: o.channel ?? 0, uSwap: o.swap ? 1 : 0, uScale: o.scale ?? 1 },
            [Math.ceil(out / 16), Math.ceil(rows / 16), 1]);
        return dst;
    }

    // the DFT of length n of `rows` rows (o.swap: of columns), its first `kept` bins: rows x kept complex
    _dftRows(src, rows, n, kept, o) {
        if ((n & (n - 1)) === 0) {
            const A = this._stages(this._chirp(src, this._ones(n), rows, n, n, o), n, false);
            if (kept === n) return A;
            const X = this._chirp(A, this._ones(n), rows, kept, kept, { complex: true });
            A.destroy();
            return X;
        }
        const t = this._bluestein(n);
        let A = this._stages(this._chirp(src, t.chirp, rows, n, t.M, o), t.M, false);
        const AB = this.R.like(A);
        this.R.run('prims/fft_mul', { src: A, b: t.B }, { dst: AB }, { uL: t.M }, [Math.ceil(t.M / 16), Math.ceil(rows / 16), 1]);
        A.destroy();
        A = this._stages(AB, t.M, true);
        const X = this._chirp(A, t.chirp, rows, kept, kept, { complex: true, scale: 1 / t.M });
        A.destroy();
        return X;
    }

    /** np.fft.rfft2 of one channel of a float field (core/metrics.py radial_spectrum's transform): an rg32f field
     * of h rows and w // 2 + 1 columns, numpy's layout (row 0 the zero frequency of the rows, fftfreq order). Radix-2
     * Stockham stages; a length that is not a power of two goes through Bluestein's chirp. float32 (numpy computes a
     * float64 field in float64). */
    rfft2(f, opts = {}) {
        const kept = Math.floor(f.w / 2) + 1;
        const X = this._dftRows(f, f.h, f.w, kept, { channel: opts.channel ?? 0 });
        const Y = this._dftRows(X, kept, f.h, f.h, { complex: true, swap: true });
        X.destroy();
        const out = this._chirp(Y, this._ones(kept), f.h, kept, kept, { complex: true, swap: true });
        Y.destroy();
        return out;
    }

    /** np.fft.fft2 of a complex rg32f field (or one channel of a real field, opts.real: true): rg32f, h x w. */
    fft2(f, opts = {}) {
        const X = this._dftRows(f, f.h, f.w, f.w, opts.real ? { channel: opts.channel ?? 0 } : { complex: true });
        const Y = this._dftRows(X, f.w, f.h, f.h, { complex: true, swap: true });
        X.destroy();
        const out = this._chirp(Y, this._ones(f.w), f.h, f.w, f.w, { complex: true, swap: true });
        Y.destroy();
        return out;
    }

    /** Release the primitives' own fields (the runner's own end releases the device). */
    destroy() {
        for (const t of this._taps.values()) t.field.destroy();
        this._taps.clear();
        for (const t of this._fft.values()) {
            if (t.chirp) { t.chirp.destroy(); t.B.destroy(); } else t.destroy();
        }
        this._fft.clear();
        for (const f of [this.dummyF, this.dummyU, this.counter, this._unit]) f?.destroy();
    }
}

const PRIMS = new WeakMap();                            // Runner -> Prims

/** The primitives of a runner (core/gpu.js init()), made once per runner. */
export function prims(R) {
    let p = PRIMS.get(R);
    if (!p) {
        p = new Prims(R);
        PRIMS.set(R, p);
    }
    return p;
}
