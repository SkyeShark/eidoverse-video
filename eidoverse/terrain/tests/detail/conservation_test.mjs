// The pipe model's physics on the GPU, the Blender detail package's GPU tests ported (blender/tests/terrain/detail/
// test_detail_gpu.py, PORT_PLAN.md 8.2 row P12: "water and sediment conserved"), on the same inputs (made by Blender's
// own Python: tests/detail/blender_detail_fixtures.py, group model), with the same bounds:
//   conservation   3,000 steps at 128^2, heights 500+ cells, closed edges and periodic ones, outflow off: ground +
//                  suspended sediment conserved (its largest net change over the run against the material moved,
//                  under 1e-5), and the water following its budget step by step, W' = (W + rain) (1 - Ke dt), within
//                  2e-5 (Blender's GPU: 1.7e-9 and 3.9e-6 closed, 5.3e-10 and 8.2e-6 periodic)
//   the twins      300 steps at 64^2 from the Blender test's slope, against the numpy twins' own run (the fixture):
//                  the totals the Blender test compares (wear p99, water, eroded, deposited) within 5 %
//   the thermal    the thermal pass alone, 3,000 passes of loose debris on a steep cone (rate 0.06): the mass
//                  conserved to the Kahan carry (the GLSL's precise lines, kernels/detail/exact.wgsl), against the
//                  same passes with the carry dropped (a measurement: what the shield is for)
//   costs          at 1024^2: one model step (four passes), a whole hydraulic level (3,000 steps), the breakup dispatch
//                  and 400 relaxation passes, beside Blender's (gpu_tests.json: 0.771 ms, 2.31 s, 76 ms, 670 ms)
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/detail/conservation_test.mjs
//         [--skip-costs]                                         (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/detail/conservation_test.json. JavaScript per cell here is test code.

import * as G from '../../core/gpu.js';
import { Level } from '../../core/levels.js';
import * as DT from '../../solvers/detail.js';
import * as HY from '../../solvers/hydraulic.js';
import * as D from './_detail.mjs';

const { C } = D;
const A = D.argsOf();
const T = new C.Checks('detail: the pipe model on the GPU');
const R = await G.init();
const fx = C.loadFixture('functions/detail');
const model = (fn) => fx?.manifest.cases.find((c) => c.function === fn) ?? null;
const out = {};
const f32 = (a) => Float32Array.from(a, (x) => Math.fround(x));

/** The Blender test's model inputs for ground b (cell units, n x n): base, state (bed = bedOf(b)), src
 * (rain 1, inflow 0, erodibility erod), par (BIG_TAN, repose 0.7, floor 0), pin (zeros). */
/** T.rgba(a) of an n x n Float32Array: the pipe model's `base`. */
function rgbaOf(a, n) {
    const f = R.field(n, n, 1, a);
    const out = R.pack({ f }, ['f', null, null, null]);
    f.destroy();
    return out;
}

function modelRun(b, n, bed, erod = 0.5) {
    const b0 = rgbaOf(b, n);
    const bedF = R.field(n, n, 1, bed);
    const { state, par } = HY.startFields(R, b0, { bed: bedF, sc: HY.BIG_TAN, rep: Math.fround(0.7), floor: 0.0 });
    const src = R.field(n, n, 4, Float32Array.from({ length: n * n * 4 }, (_, i) => (i % 4 === 0 ? 1 : i % 4 === 2 ? erod : 0)));
    const pin = R.field(n, n, 4);
    bedF.destroy();
    return { run: new HY.PipeRun(R, b0, state, src, par, pin), own: [b0, par, src, pin] };
}

// ---------------------------------------------------------------------------------------------- conservation ---

const cons = model('model.conservation');
if (!cons) {
    T.ok('conservation: the Blender test\'s inputs', false, 'no fixture: run tests/detail/blender_detail_fixtures.py with Blender\'s Python');
} else {
    const n = 128, p = HY.defaults({ rain_cover: 1.0 });
    for (const [label, mode, name] of [['closed', HY.BOUND_OPEN, 'closed'], ['periodic', HY.BOUND_PERIODIC, 'periodic']]) {
        const b = f32(C.array(fx.dir, cons.inputs[name]));
        const bed = Float32Array.from(b, (x) => Math.fround(x - 0.3));        // numpy's float32 b - 0.3
        const { run, own } = modelRun(b, n, bed);
        const rec = [];
        const t0 = performance.now();
        for (let i = 0; i < 3000; i++) {
            run.step(p, i, 7, mode, false);
            if ((i + 1) % 100 === 0) {
                const [st, ta] = await R.readAll([run.state(), run.accum()]);
                let water = 0, mass = 0;
                for (let q = 0; q < st.length; q += 4) { water += st[q + 1]; mass += st[q] + st[q + 2] + ta[q + 1]; }
                rec.push([i + 1, water, mass]);
            }
        }
        const sec = (performance.now() - t0) / 1000;
        // the water budget, step by step: W' = (W + n^2 rain dt) (1 - Ke dt), in float32 steps as the Blender test
        const rain = Math.fround(Math.fround(p.rain) * Math.fround(p.dt)) * n * n;
        const keep = Math.fround(Math.max(Math.fround(1 - Math.fround(Math.fround(p.Ke) * Math.fround(p.dt))), 0));
        let W = 0, worstW = 0, k = 0;
        for (let i = 1; i <= 3000; i++) {
            W = (W + rain) * keep;
            if (k < rec.length && rec[k][0] === i) { worstW = Math.max(worstW, Math.abs(rec[k][1] - W) / W); k++; }
        }
        const st = await R.read(run.state());
        let gross = 0, moved = 0;
        for (let q = 0; q < st.length; q += 4) { gross += Math.abs(st[q]); moved = Math.max(moved, Math.abs(st[q])); }
        const net = Math.max(...rec.map((r) => Math.abs(r[2])));
        out[label] = { net, gross, ratio: net / gross, worst_water: worstW, water: rec[rec.length - 1][1], budget: W,
            ground_moved_max: moved, seconds: +sec.toFixed(2) };
        T.ok(`GPU conservation, ${label} edges, 3000 steps at 128^2: ground + sediment`, net / gross < 1e-5,
            `net change ${C.sci(net, 2)} cells^3 against ${gross.toFixed(1)} cells^3 moved (${C.sci(net / gross, 2)}); the ground ` +
            `moved up to ${moved.toFixed(3)} cells (Blender's GPU: ${label === 'closed' ? '1.68e-9 of 1261.0' : '5.27e-10 of 5621.7'})`);
        T.ok(`GPU conservation, ${label} edges: the water budget (rain in, evaporation out)`, worstW < 2e-5,
            `worst relative error ${C.sci(worstW, 2)}, water ${rec[rec.length - 1][1].toFixed(2)} vs ${W.toFixed(2)} cells^3 ` +
            `(Blender's GPU: ${label === 'closed' ? '3.93e-6' : '8.22e-6'})`);
        run.destroy();
        for (const f of own) f.destroy();
    }
}

// ----------------------------------------------------------------------------------------- against the twins ---

const tw = model('model.run_numpy');
if (tw) {
    const n = 64, p = HY.defaults({ roughness: 0.0 });
    const b = f32(C.array(fx.dir, tw.inputs.b));
    const { run, own } = modelRun(b, n, b);
    for (let i = 0; i < 300; i++) run.step(p, i, 7, HY.BOUND_OPEN, true);
    const g = await R.read(run.state());
    const totals = (st) => {
        const dh = D.channel(st, 4, 0), neg = Float64Array.from(dh, (x) => -x).sort();
        // np.percentile(-dh, 99): linear between the order statistics (float32 data, scalar q: float32 arithmetic)
        const nn = neg.length, virt = Math.fround(Math.fround(nn - 1) * Math.fround(Math.fround(99) / 100));
        const lo = Math.floor(virt), gam = Math.fround(virt - lo);
        const a = neg[lo], bb = neg[Math.min(lo + 1, nn - 1)], diff = Math.fround(bb - a);
        let p99 = Math.fround(a + Math.fround(diff * gam));
        if (gam >= 0.5) p99 = Math.fround(bb - Math.fround(diff * Math.fround(1 - gam)));
        let water = 0, eroded = 0, deposited = 0;
        for (let q = 0; q < st.length; q += 4) { water += st[q + 1]; eroded += Math.max(-st[q], 0); deposited += Math.max(st[q], 0); }
        return { wear_p99: p99, water, eroded, deposited };
    };
    const gpu = totals(g), twin = tw.values.totals;
    const rel = Object.fromEntries(Object.keys(twin).map((k) => [k, Math.abs(gpu[k] - twin[k]) / Math.max(Math.abs(twin[k]), 1e-9)]));
    out.twins = { gpu, twin, relative: rel };
    T.ok('300 steps on the GPU vs the twins (64^2): totals within 5 %', Math.max(...Object.values(rel)) < 0.05,
        Object.entries(rel).map(([k, v]) => `${k} ${C.sci(v, 2)}`).join(', ') + ' (Blender\'s GPU: all within 2.3e-7)');
    run.destroy();
    for (const f of own) f.destroy();
}

// ------------------------------------------------------------------------------------------- the thermal pass ---

// loose debris on a steep cone over a cohesive base, 3,000 passes: the change summed against the material moved,
// with the Kahan carry (the kernel) and without it (the same pass with the carry dropped: tacc.y forced to 0 each
// time), to measure what exact.wgsl keeps
{
    const n = 96;
    const b = new Float32Array(n * n), bed = new Float32Array(n * n);
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
        const cone = Math.max(30.0 - 0.8 * Math.hypot(i - 47.3, j - 51.1), 0.0);
        b[j * n + i] = Math.fround(700.0 + 0.05 * i + cone);
        bed[j * n + i] = Math.fround(700.0 + 0.05 * i);
    }
    const res = {};
    for (const carry of [true, false]) {
        const b0 = rgbaOf(b, n);
        const bedF = R.field(n, n, 1, bed);
        const { state, par } = HY.startFields(R, b0, { bed: bedF, sc: 1.0e3, rep: Math.fround(Math.tan(35 * Math.PI / 180)), floor: -1.0e6 });
        const pin = R.field(n, n, 4), zero = R.field(n, n, 4);
        const S = [state, R.field(n, n, 4)], TA = [R.field(n, n, 4), R.field(n, n, 4)];
        const k = R.kernel('pipes_thermal');
        for (let i = 0; i < 3000; i++) {
            R.run(k, { st: S[0], base: b0, par, pin, tacc: carry ? TA[0] : zero }, { outS: S[1], outT: TA[1] }, { uRate: 0.06, uBound: 0 });
            S.reverse();
            TA.reverse();
        }
        const [st, ta] = await R.readAll([S[0], TA[0]]);
        let net = 0, gross = 0;
        for (let q = 0; q < st.length; q += 4) { net += st[q] + (carry ? ta[q + 1] : 0); gross += Math.abs(st[q]); }
        res[carry ? 'kahan' : 'dropped'] = { net, gross, ratio: Math.abs(net) / gross };
        for (const f of [b0, bedF, par, pin, zero, ...S, ...TA]) f.destroy();
    }
    out.thermal = res;
    T.ok('the thermal pass conserves the debris over 3,000 passes (with the Kahan carry the GLSL keeps precise)',
        res.kahan.ratio < 1e-7, `net ${C.sci(res.kahan.net, 2)} cells^3 against ${res.kahan.gross.toFixed(1)} moved ` +
        `(${C.sci(res.kahan.ratio, 2)}); without the carry ${C.sci(res.dropped.ratio, 2)} (Blender's measurement without ` +
        'it: 4e-6 of the material moved)');
}

// -------------------------------------------------------------------------------------------------- costs ---

if (!A.flag('--skip-costs')) {
    const n = 1024, p = HY.defaults();
    const b = new Float32Array(n * n);
    let s = 4;
    const rnd = () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296;
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) b[j * n + i] = Math.fround(500 + 0.45 * j + 3 * Math.sin(i / n * 6) + 2 * rnd());
    const { run, own } = modelRun(b, n, b);
    for (let i = 0; i < 20; i++) run.step(p, i, 1, HY.BOUND_OPEN, true);
    await R.idle();
    let t0 = performance.now();
    const steps = 500;
    for (let i = 0; i < steps; i++) run.step(p, 20 + i, 1, HY.BOUND_OPEN, true);
    await R.idle();
    const perStep = (performance.now() - t0) / steps;
    const gpuMs = await R.timed(() => { for (let i = 0; i < 100; i++) run.step(p, 600 + i, 1, HY.BOUND_OPEN, true); });
    run.destroy();
    for (const f of own) f.destroy();
    const lv = new Level(0, 'hero', -260.0, 1380.0, n * 0.5, 0.5, n);
    const h = R.field(n, n, 1, Float32Array.from(b, (x) => Math.fround(x * 0.5)));
    t0 = performance.now();
    const st = DT.strength(DT.paramsOf(DT.BREAKUP, null, 'breakup'), lv, h, 1);
    await R.read(st);
    const tStrength = performance.now() - t0;
    const b0 = rgbaOf(b, n);
    const sc = R.field(n, n, 1, new Float32Array(n * n).fill(Math.fround(Math.tan(70 * Math.PI / 180))));
    t0 = performance.now();
    const rl = DT.relax(b0, null, sc, 0.7, 400, 0.06);
    await R.read(rl.state);
    const tRelax = performance.now() - t0;
    for (const f of [h, st, b0, sc, rl.state, rl.accum]) f.destroy();
    out.costs = { pipe_step_ms_1024: +perStep.toFixed(3), pipe_step_gpu_ms_1024: gpuMs === null ? null : +(gpuMs / 100).toFixed(3),
        hydraulic_level_3000_steps_s: +(perStep * 3).toFixed(2), breakup_dispatch_ms_1024: +tStrength.toFixed(1),
        relax_400_iterations_ms_1024: +tRelax.toFixed(1), compile_ms: R.compileMs,
        blender: { pipe_step_ms_1024: 0.771, hydraulic_level_3000_steps_s: 2.31, breakup_dispatch_ms_1024: 76.0, relax_400_iterations_ms_1024: 670.1 } };
    T.ok('a pipe-model step at 1024^2 costs at most 2 ms (four passes; the Blender test\'s bound)', perStep <= 2.0,
        `${perStep.toFixed(3)} ms wall, ${gpuMs === null ? '?' : (gpuMs / 100).toFixed(3)} ms GPU (Blender 0.771 ms); breakup ` +
        `${tStrength.toFixed(1)} ms with its readback (Blender 76), 400 relaxation passes ${tRelax.toFixed(1)} ms (Blender 670)`);
}

T.extra.results = out;
const code = D.finish(T, 'conservation_test');
G.shutdown();
Deno.exit(code);
