// The glacial package's kernels (PORT_PLAN.md 8.2 row P13, 5.1, 5.3): every case of the Blender edition's own GPU
// test (blender/tests/terrain/glacial/test_gpu.py test_parity, as tests/parity/fixtures.py --kernels ran it through
// the numpy twins) through the production runner.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/glacial/kernels_test.mjs
//                                                                  (on a shared machine, behind $EIDO_GPU_WRAP)
//
//   ice_flux    one dispatch per case (D8 receivers, and the water's MFD weights at p 1 and 1.3; open, periodic and
//               pinned): max |gpu - twin| within 1e-4 of the output's range (plan 5.3's kernel grade, with the
//               rounding floor of pow and the division, tests/parity/_common.mjs)
//   jump_flood  one pass per case (the target and the distance metrics, jumps 32 to 1, from the twins' own
//               half-flooded states): the candidates IDENTICAL to the twin's, cell by cell and slot by slot (the
//               plan's acceptance); beside it Blender's own test's measure, the candidates' float64 metrics within
//               1e-4 of their range with the same slots filled (test_gpu.py: a last-bit tie may rank two seeds
//               either way)
//   u_carve     the shoulders, the cap, three cirques, open and pinned: every output channel within 1e-4 of range
// JavaScript per cell here is test code. Writes tests/out/glacial/kernels_test.json.

import * as G from '../../core/gpu.js';
import * as C from '../parity/_common.mjs';
import { decodeBest } from './_glacial.mjs';

const W = C.W;
const T = new C.Checks('glacial: kernel fixtures');
const R = await G.init();
const results = {};

// ice_flux: pow (the tongue's width, the MFD weights) and the division
{
    const r = await C.kernelCases(R, 'ice_flux', { uses: ['pow', 'divide'] });
    if (!r) T.ok('ice_flux: kernel fixtures', false, 'no kernel fixtures (tests/parity/fixtures.py --kernels)');
    else {
        results.ice_flux = { n: r.n, worst: r.worst, failed: r.failed, cases: r.cases.map((c) => ({ label: c.label, ok: c.ok, worst: c.worst })) };
        T.ok(`ice_flux: ${r.n} kernel fixture cases within 1e-4 of the range`, r.ok && r.n > 0, r.detail);
    }
}

// jump_flood: the candidates identical; the metrics as Blender's own test grades them
{
    const fx = C.loadFixture('kernels');
    const cases = fx ? fx.manifest.cases.filter((c) => c.kernel === 'jump_flood') : [];
    const k = R.kernel('jump_flood');
    let identical = 0, cells = 0, slots = 0, worstMetric = 0, sameValid = true;
    const rows = [];
    for (const c of cases) {
        const shape = c.inputs.candT.shape, [n0, n1] = shape;
        const ins = {};
        for (const [s, a] of Object.entries(c.inputs)) ins[s] = R.field(a.shape[0], a.shape[1], a.shape[2], C.array(fx.dir, a));
        const out = R.field(n0, n1, 4);
        R.run(k, ins, { outC: out }, c.uniforms);
        const got = await R.read(out);
        const want = C.array(fx.dir, c.outputs.outC);
        let diffCells = 0, diffSlots = 0;
        for (let p = 0; p < n0 * n1; p++) {
            let d = 0;
            for (let q = 0; q < 4; q++) if (!Object.is(got[4 * p + q], want[4 * p + q])) d++;
            if (d) diffCells++;
            diffSlots += d;
        }
        // Blender's test: decode both candidate sets' metrics (float64) and compare within 1e-4 of their range
        const sA = C.array(fx.dir, c.inputs.seedA), sB = C.array(fx.dir, c.inputs.seedB), sC = C.array(fx.dir, c.inputs.seedC);
        const u = c.uniforms, metric = u.uMetric;
        const mg = decodeBest(got, sA, sB, sC, n0, n1, u.uDx, u, metric);
        const mw = decodeBest(want, sA, sB, sC, n0, n1, u.uDx, u, metric);
        let lo = Infinity, hi = -Infinity, err = 0, valid = true;
        for (let i = 0; i < mw.length; i++) {
            const fw = Number.isFinite(mw[i]), fg = Number.isFinite(mg[i]);
            if (fw !== fg) valid = false;
            if (!fw) continue;
            lo = Math.min(lo, mw[i]);
            hi = Math.max(hi, mw[i]);
            if (fg) err = Math.max(err, Math.abs(mg[i] - mw[i]));
        }
        const rel = err / Math.max(hi - lo, 1e-9);
        cells += n0 * n1;
        identical += n0 * n1 - diffCells;
        slots += diffSlots;
        worstMetric = Math.max(worstMetric, rel);
        sameValid = sameValid && valid;
        rows.push({ label: c.label, step: u.uStep, metric, cells_differing: diffCells, slots_differing: diffSlots,
            metric_err_over_range: rel, same_slots_filled: valid });
        for (const f of [...Object.values(ins), out]) f.destroy();
    }
    results.jump_flood = { n: cases.length, cells, identical_cells: identical, slots_differing: slots,
        worst_metric_over_range: worstMetric, cases: rows };
    T.ok(`jump_flood: ${cases.length} kernel fixture cases, the candidates identical to the twin's in every cell and slot`,
        cases.length > 0 && identical === cells, `${identical} of ${cells} cells identical, ${slots} slots differ`);
    T.ok(`jump_flood: the candidates' float64 metrics within 1e-4 of their range, the same slots filled (Blender's test_gpu grade)`,
        cases.length > 0 && sameValid && worstMetric <= 1e-4, `worst ${C.sci(worstMetric)} of the range`);
}

// u_carve: sqrt, the divisions, pow, exp (the moraine), atan2 and the sines of the cirques' rims (arguments up to
// 3 pi + 2 pi: their absolute error, tests/parity/_common.mjs trigAbs)
{
    const r = await C.kernelCases(R, 'u_carve', { uses: ['sqrt', 'divide', 'pow', 'exp', 'atan2', 'sin'], abs: C.trigAbs(20) });
    if (!r) T.ok('u_carve: kernel fixtures', false, 'no kernel fixtures (tests/parity/fixtures.py --kernels)');
    else {
        results.u_carve = { n: r.n, worst: r.worst, failed: r.failed, cases: r.cases };
        T.ok(`u_carve: ${r.n} kernel fixture cases, every output channel within 1e-4 of its range`, r.ok && r.n > 0, r.detail);
    }
}

Deno.writeTextFileSync(`${W.out('glacial')}/kernels_test.json`, JSON.stringify({ test: T.title, deno: Deno.version.deno,
    date: new Date().toISOString(), adapter: R.info?.description ?? null, ...results,
    checks: T.rows.length, failed: T.rows.filter((r) => !r.passed).map((r) => r.check), rows: T.rows }, null, 1));
const code = T.rows.every((r) => r.passed) ? 0 : 1;
console.log(`${T.rows.filter((r) => r.passed).length} of ${T.rows.length} checks pass`);
G.shutdown();
Deno.exit(code);
