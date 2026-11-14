// core/prims.js against the numpy code it replaces (PORT_PLAN.md 3.4 and 8.2, P1): every case prims_expected.py
// recorded from the Blender edition's own functions and numpy (with Blender's numpy, 2.3.4), on synthetic fields
// with pits, flats and ties and on real DEMs. The grades of plan 5.3: the fill, labels, flat distances, pointer
// jumping, sorts, scans, histograms, compaction, dilation, order statistics, percentiles and medians bit for bit;
// the Gaussian and box blurs within 1e-5 of the range; sums within float32's fixed-tree rounding; the FFT (rfft2 on
// what core/metrics.py radial_spectrum transforms, and fft2) within 1e-5 of the largest coefficient, with the
// spectrum's band powers' relative error recorded.
//
//     <Blender's python> -I eidoverse/terrain/tests/core_runner/prims_expected.py
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/core_runner/prims_test.mjs [fixtures]
//
// On a shared machine put $EIDO_GPU_WRAP in front of the deno command.

import * as G from '../../core/gpu.js';
import { prims } from '../../core/prims.js';
import { Checks, OUT, bitsEqual, dirUrl, loadBin } from './_common.mjs';

const T = new Checks('core_runner/prims');

function fixtures() {
    if (Deno.args[0]) return dirUrl(Deno.args[0]);
    const found = [];
    try {
        for (const e of Deno.readDirSync(OUT)) if (e.isDirectory && e.name.startsWith('prims_')) found.push(e.name);
    } catch (_e) { /* none */ }
    found.sort();
    return found.length ? new URL(found[0] + '/', OUT) : null;
}

const FIX = fixtures();
if (!FIX) {
    console.log('SKIP: no fixtures. Make them with Blender\'s Python:\n    <blender>/<version>/python/bin/python -I ' +
        'eidoverse/terrain/tests/core_runner/prims_expected.py\n(the Blender edition is found beside eidoverse/ or at $EIDO_BLENDER_EDITION)');
    Deno.exit(0);
}
const man = JSON.parse(Deno.readTextFileSync(new URL('manifest.json', FIX)));
T.extra.numpy = man.numpy;
T.extra.blender_commit = man.blender_commit;

const R = await G.init();
const P = prims(R);
T.extra.adapter = R.info?.description ?? null;

const KIND = { f32: 'f32', f64: 'f32', u32: 'u32', i32: 'i32' };
function upload(a) {
    const data = loadBin(FIX, a);
    const kind = KIND[a.dtype];
    const arr = a.dtype === 'f64' ? Float32Array.from(data) : data;
    if (a.shape.length === 1) return P.list(a.shape[0], kind, arr);
    return R.field(a.shape[0], a.shape[1], a.shape[2] ?? 1, arr, kind);
}
// complex arrays (re, im interleaved): the largest |got - want| over the largest |want|
const complexErr = (got, want) => {
    let big = 0, err = 0;
    for (let i = 0; i < want.length; i += 2) {
        big = Math.max(big, Math.hypot(want[i], want[i + 1]));
        err = Math.max(err, Math.hypot(got[i] - want[i], got[i + 1] - want[i + 1]));
    }
    return err / big;
};
const items = (a) => a.shape.reduce((s, d) => s * d, 1);
const rangeErr = (got, want) => {
    let lo = Infinity, hi = -Infinity, err = 0;
    for (let i = 0; i < want.length; i++) {
        lo = Math.min(lo, want[i]);
        hi = Math.max(hi, want[i]);
        err = Math.max(err, Math.abs(got[i] - want[i]));
    }
    return err / Math.max(hi - lo, 1e-30);
};
const firstDiff = (got, want) => {
    for (let i = 0; i < want.length; i++) if (got[i] !== want[i]) return `first difference at ${i}: ${got[i]} against ${want[i]}`;
    return got.length !== want.length ? `lengths ${got.length} and ${want.length}` : '';
};
const exact = (name, got, want) => T.ok(name, bitsEqual(got, want), firstDiff(got, want));

const timing = {}, worst = {};
const timed = async (name, fn) => {
    const t0 = performance.now();
    const v = await fn();
    timing[name] = +(performance.now() - t0).toFixed(1);
    return v;
};

const caseMs = {};                                       // each case's wall time, uploads and readbacks included
for (const c of man.cases) {
    const c0 = performance.now();
    const inp = {};
    for (const [k, a] of Object.entries(c.inputs)) inp[k] = upload(a);
    const want = Object.fromEntries(Object.entries(c.outputs).map(([k, a]) => [k, loadBin(FIX, a)]));
    const made = [];
    const keep = (f) => { made.push(f); return f; };
    const pr = c.params;
    try {
        if (c.kind === 'fill') {
            const r = await timed(c.label, () => P.fillDepressions(inp.h, { wrap: pr.wrap, seaLevel: pr.sea_level }));
            keep(r.filled);
            const got = await R.read(r.filled);
            T.ok(`${c.label}: bit for bit, outlet '${pr.outlet}'`, bitsEqual(got, want.filled) && r.outlet === pr.outlet,
                `${firstDiff(got, want.filled)} outlet ${r.outlet}; ${pr.filled_cells} cells filled; ${r.dispatches} dispatches`);
        } else if (c.kind === 'label') {
            const r = await timed(c.label, () => P.label(inp.mask));
            keep(r.labels);
            const got = await R.read(r.labels);
            T.ok(`${c.label}: ${pr.count} components, numbered as numpy numbers them`, bitsEqual(got, want.labels) && r.count === pr.count,
                `${firstDiff(got, want.labels)} count ${r.count}`);
        } else if (c.kind === 'percentile') {
            const got = await P.percentile(inp.a, pr.q, { mask: inp.mask ?? null, dtype: pr.data_dtype ?? 'float32' });
            const g = pr.scalar ? [got] : got;
            T.ok(`${c.label}: equal to np.percentile`, g.length === pr.expected.length && g.every((v, i) => v === pr.expected[i]),
                `got ${JSON.stringify(g)}, want ${JSON.stringify(pr.expected)}`);
        } else if (c.kind === 'quantile') {
            const got = await P.quantile(inp.a, pr.q, { dtype: pr.data_dtype ?? 'float32' });
            const g = pr.scalar ? [got] : got;
            T.ok(`${c.label}: equal to np.quantile`, g.length === pr.expected.length && g.every((v, i) => v === pr.expected[i]),
                `got ${JSON.stringify(g)}, want ${JSON.stringify(pr.expected)}`);
        } else if (c.kind === 'median') {
            const got = await P.median(inp.a, { count: items(c.inputs.a), dtype: pr.data_dtype ?? 'float32' });
            T.ok(`${c.label}: equal to np.median (${pr.dtype})`, got === pr.expected, `got ${got}, want ${pr.expected}`);
        } else if (c.kind === 'argsort') {
            const n = items(c.inputs.a);
            const perm = keep(await timed(c.label, () => P.argsort(inp.a, { descending: pr.descending, count: n })));
            exact(`${c.label}: the stable order`, (await R.read(perm)).subarray(0, n), want.perm);
        } else if (c.kind === 'lexsort') {
            const n = items(c.inputs.k0);
            const k0 = keep(P.floatKeys(inp.k0));
            const perm = keep(P.lexsort([k0, inp.k1], { count: n }));
            exact(`${c.label}: np.lexsort's order`, (await R.read(perm)).subarray(0, n), want.perm);
        } else if (c.kind === 'segments') {
            const n = items(c.inputs.keys);
            const f = keep(P.segmentHeads(inp.keys, { count: n }));
            exact(`${c.label}`, (await R.read(f)).subarray(0, n), want.first);
        } else if (c.kind === 'cumsum') {
            const n = items(c.inputs.a);
            const inc = keep(P.cumsum(inp.a, { count: n }));
            const exc = keep(P.cumsum(inp.a, { count: n, exclusive: true }));
            const [gi, ge] = await R.readAll([inc, exc]);
            const v = loadBin(FIX, c.inputs.a);
            const we = want.inclusive.map((s, i) => (s - v[i]) >>> 0);
            T.ok(`${c.label}: inclusive and exclusive, exact`, bitsEqual(gi.subarray(0, n), want.inclusive) && bitsEqual(ge.subarray(0, n), we),
                firstDiff(gi.subarray(0, n), want.inclusive) + firstDiff(ge.subarray(0, n), we));
        } else if (c.kind === 'nonzero') {
            const n = items(c.inputs.flags);
            const r = await P.nonzero(inp.flags, { count: n });
            keep(r.index);
            const got = (await R.read(r.index)).subarray(0, r.n);
            T.ok(`${c.label}: ${want.index.length} indices in order`, r.n === want.index.length && bitsEqual(got, want.index), firstDiff(got, want.index));
        } else if (c.kind === 'bincount') {
            const h = keep(P.bincount(inp.keys, pr.bins, { count: items(c.inputs.keys) }));
            exact(`${c.label}`, (await R.read(h)).subarray(0, pr.bins), want.counts);
        } else if (c.kind === 'stats') {
            const s = await P.stats(inp.a);
            const am = await P.argmin(inp.a);
            const rel = Math.abs(s.sum - pr.sum) / Math.abs(pr.sum);
            worst.sum_relative = Math.max(worst.sum_relative ?? 0, rel);
            T.ok(`${c.label}: min, max, count_nonzero and argmin exact; the float32 sum within 1e-6`,
                s.min === pr.min && s.max === pr.max && s.nonzero === pr.nonzero && am === pr.argmin && rel < 1e-6,
                `min ${s.min}/${pr.min} max ${s.max}/${pr.max} nonzero ${s.nonzero}/${pr.nonzero} argmin ${am}/${pr.argmin} sum ${rel.toExponential(2)} relative`);
        } else if (c.kind === 'paths') {
            const r = await timed(c.label, () => P.pathSteps(inp.rec, { check: true }));
            keep(r.steps);
            keep(r.terminal);
            const pm = keep(P.pathMax(inp.rec, inp.val));
            const [st, te, pmv] = await R.readAll([r.steps, r.terminal, pm]);
            T.ok(`${c.label}: steps and terminals exact (longest path ${pr.longest})`, bitsEqual(st, want.steps) && bitsEqual(te, want.terminal),
                firstDiff(st, want.steps) + firstDiff(te, want.terminal));
            exact(`${c.label}: path maxima exact`, pmv, want.pathmax);
        } else if (c.kind === 'flat') {
            const d = keep(await timed(c.label, () => P.flatDistance(inp.surface, { wrap: pr.wrap, seaLevel: pr.sea_level })));
            const got = await R.read(d);
            T.ok(`${c.label}: exact (longest ${pr.longest} steps)`, bitsEqual(got, want.dist),
                `${firstDiff(got, want.dist)}; ${P.dispatchCounts.flat_distance} dispatches`);
        } else if (c.kind === 'gauss') {
            const out = keep(await timed(c.label, () => P.gaussianBlur(inp.a, pr.sigma, { mode: pr.mode, size: pr.size })));
            const e = rangeErr(await R.read(out), want.out);
            worst.gauss = Math.max(worst.gauss ?? 0, e);
            T.ok(`${c.label}: within 1e-5 of the range`, e <= 1e-5, `${e.toExponential(3)} of the range`);
        } else if (c.kind === 'box') {
            const out = keep(P.boxBlur(inp.a, pr.r, { wrap: pr.wrap, passes: pr.passes, axes: pr.axes }));
            const e = rangeErr(await R.read(out), want.out);
            worst.box = Math.max(worst.box ?? 0, e);
            T.ok(`${c.label}: within 1e-5 of the range`, e <= 1e-5, `${e.toExponential(3)} of the range`);
        } else if (c.kind === 'dilate') {
            const out = keep(P.dilate(inp.a, pr.r));
            exact(`${c.label}: exact`, await R.read(out), want.out);
        } else if (c.kind === 'rfft2' || c.kind === 'fft2') {
            const F = keep(await timed(c.label, () => (c.kind === 'rfft2' ? P.rfft2(inp.a) : P.fft2(inp.a))));
            const got = await R.read(F);
            const e = complexErr(got, want.F);
            worst.fft = Math.max(worst.fft ?? 0, e);
            let band = 0;
            if (c.kind === 'rfft2') {                                // radial_spectrum's band powers from these coefficients
                const tot = new Float64Array(48), cnt = new Float64Array(48);
                want.bins.forEach((b, i) => {
                    if (b < 48) { tot[b] += got[2 * i] ** 2 + got[2 * i + 1] ** 2; cnt[b]++; }
                });
                pr.band_power.forEach((p, b) => { if (cnt[b]) band = Math.max(band, Math.abs(tot[b] / cnt[b] - p) / p); });
                worst.fft_band_power = Math.max(worst.fft_band_power ?? 0, band);
            }
            T.ok(`${c.label}: within 1e-5 of the largest coefficient`, e <= 1e-5,
                `${e.toExponential(3)}${c.kind === 'rfft2' ? `; radial_spectrum's band powers within ${band.toExponential(2)} relative` : ''}`);
        } else {
            T.ok(`${c.label}: a kind this test knows`, false, c.kind);
        }
    } catch (e) {
        T.ok(`${c.label}: ran`, false, e.message.slice(0, 600));
    }
    for (const f of [...Object.values(inp), ...made]) f.destroy();
    caseMs[c.label] = +(performance.now() - c0).toFixed(1);
}

// determinism: the large fill and labels again, bit for bit (exact kinds), and the blur again (float, fixed order)
{
    const big = man.cases.find((c) => c.kind === 'fill' && c.label.includes('palouse'));
    if (big) {
        const h = upload(big.inputs.h);
        const a = await P.fillDepressions(h), b = await P.fillDepressions(h);
        const g1 = P.gaussianBlur(h, 6.0), g2 = P.gaussianBlur(h, 6.0);
        const [fa, fb, ga, gb] = await R.readAll([a.filled, b.filled, g1, g2]);
        T.ok('determinism: the 1000 x 1000 fill and its blur, twice, bit for bit', bitsEqual(fa, fb) && bitsEqual(ga, gb));
        for (const f of [h, a.filled, b.filled, g1, g2]) f.destroy();
    }
}

T.extra.ms = timing;
T.extra.case_ms = caseMs;
T.extra.worst = Object.fromEntries(Object.entries(worst).map(([k, v]) => [k, +v.toExponential(3)]));
T.extra.compile_ms = R.compileMs;
T.extra.counters = { dispatches: R.dispatches, submits: R.submits, fields_alive: R.fields, peak_field_mb: +(R.peakFieldBytes / 2 ** 20).toFixed(1) };
const code = T.done('prims_test.json');
G.shutdown();
Deno.exit(code);
