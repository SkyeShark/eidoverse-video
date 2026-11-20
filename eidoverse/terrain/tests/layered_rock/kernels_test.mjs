// The layered-rock package's kernels (PORT_PLAN.md 8.2 row P10, 5.1, 5.3): every case of the Blender edition's own
// kernel test (blender/tests/terrain/layered_rock/test_kernels.py, as tests/parity/fixtures.py --kernels ran it through
// the numpy twins) through the production runner.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/layered_rock/kernels_test.mjs
//                                                          (on a shared machine, behind $EIDO_GPU_WRAP)
//
// One dispatch of each of the four kernels this package owns per Blender case (strata_threshold: the column's run,
// the loose cover at repose, the rock mass's run factor, the facies, every boundary mode; strata_cell; strata_creep;
// strata_weather: the rock and loose rates, the drainage boost and its slope ramp, the saturated and linear slope
// terms, the facies, pins): max |gpu - twin| within 1e-4 of each output channel's range (plan 5.3's kernel grade,
// with the rounding floor of the built-ins each kernel leans on, tests/parity/_common.mjs). The route_incise and
// flow_weights cases of the same Blender test (the K(zs) column lookup) are the fluvial and hydrology packages'
// kernels and their tests (tests/fluvial/kernels_test.mjs, tests/hydro/hydro_test.mjs).
// JavaScript per cell here is test code (the edition's rule allows it in tests only). Writes
// tests/out/layered_rock/kernels_test.json.

import * as G from '../../core/gpu.js';
import * as C from '../parity/_common.mjs';

const W = C.W;
const T = new C.Checks('layered_rock: kernel fixtures');
const R = await G.init();
const results = { kernels: {} };

// the kernels and the built-ins each leans on (the grade's rounding floor)
export const KERNELS = [
    ['strata_threshold', ['sqrt', 'divide', 'exp']],
    ['strata_cell', ['divide']],
    ['strata_creep', ['divide']],
    ['strata_weather', ['sqrt', 'divide', 'exp']],
];

for (const [name, uses] of KERNELS) {
    const r = await C.kernelCases(R, name, { uses });
    if (!r) { T.ok(`${name}: kernel fixtures`, false, 'no kernel fixtures (tests/parity/fixtures.py --kernels)'); continue; }
    results.kernels[name] = { n: r.n, worst: r.worst, failed: r.failed,
        cases: r.cases.map((c) => ({ label: c.label, ok: c.ok, worst: c.worst,
            channels: c.channels.map((h) => ({ image: h.image, channel: h.channel, over: h.over, ok: h.ok })) })) };
    T.ok(`${name}: ${r.n} kernel fixture cases within 1e-4 of each channel's range`, r.ok && r.n > 0, r.detail);
}

Deno.writeTextFileSync(`${W.out('layered_rock')}/kernels_test.json`, JSON.stringify({ test: T.title, deno: Deno.version.deno,
    date: new Date().toISOString(), adapter: R.info?.description ?? null, ...results,
    checks: T.rows.length, failed: T.rows.filter((r) => !r.passed).map((r) => r.check), rows: T.rows }, null, 1));
const code = T.rows.every((r) => r.passed) ? 0 : 1;
console.log(`${T.rows.filter((r) => r.passed).length} of ${T.rows.length} checks pass`);
G.shutdown();
Deno.exit(code);
