// The karst-and-coast package's kernels (PORT_PLAN.md 8.2 row P11, 5.1, 5.3): every case of the Blender edition's own
// coast kernel tests (blender/tests/terrain/coast/test_coast_gpu.py, as tests/parity/fixtures.py --kernels ran them
// through the numpy twins) through the production runner, and the whole jump flood against the twin device.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/karst_coast/kernels_test.mjs
//         [--only tables,fixtures,flood]                      (on a shared machine, behind $EIDO_GPU_WRAP)
//
//   1. tables: the fetch kernel's direction constants (solvers/coast.js dirs, invDirs) bit for bit coast.py's
//      _dirs(16) and _inv_dirs(16) (tests/karst_coast/karst_coast_expected.py, Blender's Python)
//   2. fixtures: one dispatch of coast_fetch_16, coast_seed and coast_jfa (steps 16, 4, 1) per Blender case. The
//      fetch's traversal and the jump flood's choices are exact (comparisons, integer steps, and products kept as
//      written): their outputs bit for bit the twin's. coast_seed divides (this GPU's division is within 2 ulp): its
//      crossings within 1e-4 of the channel's range (plan 5.3's kernel grade), its payload and flag bit for bit
//   3. flood: solvers/coast.js nearestCrossing (seed + the JFA+2 schedule + the distance kernel) against coast.py's
//      nearest_crossing on the twin device, the Blender test's wavy level set: the distance within 1e-4 cells (the
//      Blender test's own grade for its GPU), the payload equal
// JavaScript per cell here is test code (the edition's rule allows it in tests only). Writes
// tests/out/karst_coast/kernels_test.json.

import * as G from '../../core/gpu.js';
import * as CO from '../../solvers/coast.js';
import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';

const args = [...Deno.args];
const onlyAt = args.indexOf('--only');
const ONLY = onlyAt >= 0 ? new Set(args[onlyAt + 1].split(',')) : null;
const want = (s) => !ONLY || ONLY.has(s);

const T = new C.Checks('karst and coast: kernel fixtures');
const R = await G.init();
const results = {};
const fx = KC.loadFixtures();

if (want('tables')) {
    const c = fx && KC.findCase(fx, 'coast._dirs');
    if (!c) {
        T.ok('fetch directions bit for bit coast.py _dirs(16), _inv_dirs(16)', false, KC.NO_FIXTURES);
    } else {
        const d = C.array(fx.dir, c.outputs.dirs), inv = C.array(fx.dir, c.outputs.inv);
        const md = CO.dirs(16), mi = CO.invDirs(16);
        const same = (a, b) => a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
        T.ok('fetch directions bit for bit coast.py _dirs(16), _inv_dirs(16)', same(md, d) && same(mi, inv),
            `dirs ${md.length / 2} pairs, inv ${mi.length / 2} pairs`);
    }
}

if (want('fixtures')) {
    // the fetch: its traversal is exact, its last line divides (this GPU's division is within 2 ulp of the correctly
    // rounded quotient, plan 2.3). So every shore value within one float32 step of the twin's: one ray stopping at
    // another cell moves a value by at least 1 / (2 x 16 x uMaxCells), thousands of steps. Non-shore cells -1 both
    const kf = C.loadFixture('kernels');
    const cases = kf ? kf.manifest.cases.filter((c) => c.kernel === 'coast_fetch_16') : [];
    if (!cases.length) T.ok('coast_fetch_16: kernel fixtures', false, 'no kernel fixtures (tests/parity/fixtures.py --kernels)');
    for (const c of cases) {
        const a = c.inputs.seaT, sea = R.field(a.shape[0], a.shape[1], 1, C.array(kf.dir, a));
        const out = R.field(a.shape[0], a.shape[1], 1);
        R.run(CO.fetchKernel(R, 16), { seaT: sea }, { outE: out }, c.uniforms);
        const got = await R.read(out), wantE = C.array(kf.dir, c.outputs.outE);
        let shore = 0, maxSteps = 0, minusOne = 0, bad = 0;
        for (let i = 0; i < wantE.length; i++) {
            if (wantE[i] < 0) { if (got[i] === -1) minusOne++; else bad++; continue; }
            shore++;
            maxSteps = Math.max(maxSteps, Math.abs(got[i] - wantE[i]) / C.ulp32(wantE[i]));
        }
        results.coast_fetch_16 = { label: c.label, shore, max_steps: maxSteps, non_shore_minus_one: minusOne, bad };
        T.ok('coast_fetch_16: the exact traversal (every shore value within one float32 step of the twin\'s: the ' +
            'last division; a ray stopping at another cell moves it by thousands), -1 on every other cell',
        maxSteps <= 1 && bad === 0, `${shore} shore cells, max ${maxSteps} float32 steps; ${minusOne} cells -1 on both`);
        sea.destroy();
        out.destroy();
    }
    const seed = await C.kernelCases(R, 'coast_seed', { uses: ['divide'], exact: { outS: [2, 3] } });
    if (seed) {
        results.coast_seed = seed;
        T.ok(`coast_seed: ${seed.n} case(s) within 1e-4 of each channel's range, payload and flag bit for bit`,
            seed.ok && seed.n > 0, seed.detail);
    }
    const jfa = await C.kernelCases(R, 'coast_jfa', { exact: { outS: [0, 1, 2, 3] } });
    if (jfa) {
        results.coast_jfa = jfa;
        T.ok(`coast_jfa: ${jfa.n} cases (steps 16, 4, 1) bit for bit`, jfa.ok && jfa.n > 0, jfa.detail);
    }
}

if (want('flood')) {
    const c = fx && KC.findCase(fx, 'coast.nearest_crossing');
    if (!c) {
        T.ok('nearestCrossing against the twin device within 1e-4 cells', false, KC.NO_FIXTURES);
    } else {
        const [H, W] = c.inputs.phi.shape;
        const phi = R.field(H, W, 1, C.array(fx.dir, c.inputs.phi)), pay = R.field(H, W, 1, C.array(fx.dir, c.inputs.pay));
        const out = CO.nearestCrossing(R, phi, pay);
        const got = await R.read(out);
        const dWant = C.array(fx.dir, c.outputs.d), pWant = C.array(fx.dir, c.outputs.payload);
        let worst = 0, finMismatch = 0, payEq = 0, n = 0;
        for (let i = 0; i < H * W; i++) {
            const dg = got[4 * i], dw = dWant[i];
            if (Number.isFinite(dg) !== Number.isFinite(dw)) { finMismatch++; continue; }
            if (!Number.isFinite(dw)) continue;
            n++;
            worst = Math.max(worst, Math.abs(dg - dw));
            if (Math.abs(got[4 * i + 1] - pWant[i]) < 1e-6) payEq++;
        }
        results.flood = { cells: n, worst_cells: worst, finite_mismatch: finMismatch, payload_equal: payEq / Math.max(n, 1) };
        T.ok('nearestCrossing (seed, JFA+2, distance) against coast.py nearest_crossing on the twin device: the ' +
            'distance within 1e-4 cells, the payload equal', worst <= 1e-4 && finMismatch === 0 && payEq === n,
            `max |d - d_twin| ${C.sci(worst)} cells over ${n} cells; payload equal on ${(100 * payEq / Math.max(n, 1)).toFixed(3)} %`);
        for (const f of [phi, pay, out]) f.destroy();
    }
}

Deno.exit(KC.finish(T, 'kernels_test', { results }));
