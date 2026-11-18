// The fluvial package's kernels (PORT_PLAN.md 8.2 row P6, 5.1, 5.3): every case of the Blender edition's own kernel
// tests (blender/tests/terrain/fluvial/test_kernels.py and layered_rock/test_kernels.py, as tests/parity/fixtures.py
// --kernels ran them through the numpy twins) through the production runner, and the kernels' mass conservation.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/fluvial/kernels_test.mjs
//         [--only fixtures,conservation]                      (on a shared machine, behind $EIDO_GPU_WRAP)
//
//   1. fixtures: one dispatch of each of the nine kernels this package owns (route_incise, creep, threshold,
//      threshold_excess, h_keep, creep_layers, lock_restrict, lock_apply, soil_jacobi) per Blender case (every
//      boundary mode, D-infinity and D8, n = 1 and 1.5, pits filled and left, the layered-rock column, creep caps 5
//      and 1, the isotropic and pair thresholds with and without the loose limit, the soil step with and without the
//      asymmetry, the lock's blocks 2, 8 and 16 at their offsets and its second stage): max |gpu - twin| within
//      1e-4 of each output channel's range (plan 5.3's kernel grade, with the rounding floor of the built-ins each
//      kernel leans on, tests/parity/_common.mjs)
//   2. conservation (test_kernels.py test_conservation, ported): 300 creep sub-steps and 300 threshold iterations
//      (isotropic, loose only, pair excess) on a rough 256^2 field, open and periodic: the sum of h unchanged
//      within 1e-5 (relative), and material moved (mean |dh| over 1 cm). The field is twins.random_field's, drawn
//      here with numpy's Generator (core/np_random.js) and the twin's float64 box blur
// JavaScript per cell here is test code (the edition's rule allows it in tests only). Writes
// tests/out/fluvial/kernels_test.json.

import * as G from '../../core/gpu.js';
import { defaultRng } from '../../core/np_random.js';
import * as C from '../parity/_common.mjs';

const W = C.W;
const args = [...Deno.args];
const onlyAt = args.indexOf('--only');
const ONLY = onlyAt >= 0 ? new Set(args[onlyAt + 1].split(',')) : null;
const want = (s) => !ONLY || ONLY.has(s);

const T = new C.Checks('fluvial: kernel fixtures and conservation');
const R = await G.init();
const results = { kernels: {}, conservation: {} };

// the kernels and the built-ins each leans on (the grade's rounding floor)
export const KERNELS = [
    ['route_incise', ['pow', 'divide', 'sqrt']],
    ['creep', ['divide']],
    ['threshold', ['divide']],
    ['threshold_excess', ['sqrt', 'divide']],
    ['h_keep', []],
    ['creep_layers', []],
    ['lock_restrict', ['divide']],
    ['lock_apply', ['divide']],
    ['soil_jacobi', ['divide']],
];

if (want('fixtures')) {
    for (const [name, uses] of KERNELS) {
        const r = await C.kernelCases(R, name, { uses });
        if (!r) { T.ok(`${name}: kernel fixtures`, false, 'no kernel fixtures (tests/parity/fixtures.py --kernels)'); continue; }
        results.kernels[name] = { n: r.n, worst: r.worst, failed: r.failed,
            cases: r.cases.map((c) => ({ label: c.label, ok: c.ok, worst: c.worst })) };
        T.ok(`${name}: ${r.n} kernel fixture cases within 1e-4 of each channel's range`, r.ok && r.n > 0, r.detail);
    }
}

// ----------------------------------------------------------------------------------------- conservation ---

/** core/twins.py _box(a, r): the separable box blur of radius r with edge clamping, float64 (a test field). */
function box(a, h, w, r) {
    let cur = a;
    for (const axis of [0, 1]) {
        const n = axis === 0 ? h : w, out = new Float64Array(h * w);
        const at = (j, i) => cur[j * w + i];
        for (let line = 0; line < (axis === 0 ? w : h); line++) {
            const c = new Float64Array(n + 2 * r + 1);
            let s = 0;
            for (let k = 0; k < n + 2 * r; k++) {
                const src = Math.min(Math.max(k - r, 0), n - 1);
                s += axis === 0 ? at(src, line) : at(line, src);
                c[k + 1] = s;
            }
            for (let k = 0; k < n; k++) {
                const v = (c[k + 2 * r + 1] - c[k]) / (2 * r + 1);
                if (axis === 0) out[k * w + line] = v; else out[line * w + k] = v;
            }
        }
        cur = out;
    }
    return cur;
}

/** core/twins.py random_field(shape, lo, hi, seed, smooth): numpy's default_rng(seed).random, box-smoothed,
 * rescaled to [lo, hi], float32. */
export function randomField(h, w, lo, hi, seed, smooth = 0) {
    let a = Float64Array.from(defaultRng(seed).random(h * w));
    for (let k = 0; k < smooth; k++) a = box(a, h, w, 2);
    let mn = Infinity, mx = -Infinity;
    for (const v of a) { if (v < mn) mn = v; if (v > mx) mx = v; }
    const span = Math.max(mx - mn, 1e-12);
    return Float32Array.from(a, (v) => lo + (hi - lo) * ((v - mn) / span));
}

function rgba(n, ...chans) {
    const out = new Float32Array(n * 4);
    chans.forEach((c, k) => { if (c) for (let i = 0; i < n; i++) out[4 * i + k] = c[i]; });
    return out;
}

if (want('conservation')) {
    const HS = await import('../../solvers/hillslope.js');
    const n = 256, N = n * n;
    const h = randomField(n, n, 0.0, 300.0, 3, 1);
    const r4 = randomField(n, n, 0, 1, 4, 2);
    const t30 = Math.tan((30.0 * Math.PI) / 180.0);
    const sc = Float32Array.from(r4, (v) => Math.fround(t30 * Math.fround(0.8 + Math.fround(0.4 * v))));
    const loose = randomField(n, n, 0.0, 4.0, 5, 0);
    const z = new Float32Array(N);
    let s0 = 0;
    for (const v of h) s0 += v;
    for (const [modeName, mode] of [['open', 0], ['periodic', 1]]) {
        for (const kind of ['creep', 'threshold', 'threshold_loose', 'threshold_pair']) {
            const S = R.pair(n, n, 4, rgba(N, h)), M = R.pair(n, n, 4, rgba(N, z, z, z, loose));
            const P = R.field(n, n, 4, rgba(N, null, null, sc)), Q = R.field(n, n, 4);
            let phi = null;
            const t0 = performance.now();
            for (let it = 0; it < 300; it++) {
                if (kind === 'creep') {
                    R.run('creep', { st: S.src, par: P, pin: Q }, { outS: S.dst },
                        { uDx: 5.0, uDtSub: (0.9 * 25.0) / (3.4 * 0.3 * 5.0), uD: 0.3, uCap: 5.0, uBound: mode });
                    S.swap();
                } else {
                    const iso = kind === 'threshold_pair' ? 0 : 1;
                    phi = HS.thresholdPass(R, S, M, P, Q, 5.0, iso ? 0.12 : 0.06, kind === 'threshold_loose', mode, iso, phi);
                }
            }
            const got = await R.read(S.src);
            const ms = performance.now() - t0;
            let s1 = 0, moved = 0;
            for (let i = 0; i < N; i++) {
                s1 += got[4 * i];
                moved += Math.abs(got[4 * i] - h[i]);
            }
            moved /= N;
            const rel = Math.abs(s1 - s0) / Math.abs(s0);
            results.conservation[`${kind}/${modeName}`] = { rel_sum_change: rel, mean_abs_change_m: moved, ms: +ms.toFixed(1) };
            T.ok(`conservation ${kind} ${modeName} (300 passes): the sum of h within 1e-5`, rel <= 1e-5 && moved > 0.01,
                `sum change ${C.sci(rel)} (relative), material moved ${moved.toFixed(3)} m per cell on average`);
            for (const x of [S, M, P, Q]) x.destroy();
            if (phi && phi.h === n) phi.destroy();
        }
    }
}

Deno.writeTextFileSync(`${W.out('fluvial')}/kernels_test.json`, JSON.stringify({ test: T.title, deno: Deno.version.deno,
    date: new Date().toISOString(), adapter: R.info?.description ?? null, ...results,
    checks: T.rows.length, failed: T.rows.filter((r) => !r.passed).map((r) => r.check), rows: T.rows }, null, 1));
const code = T.rows.every((r) => r.passed) ? 0 : 1;
console.log(`${T.rows.filter((r) => r.passed).length} of ${T.rows.length} checks pass`);
G.shutdown();
Deno.exit(code);
