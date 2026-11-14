// The grades of tests/parity/_common.mjs, tested (PORT_PLAN.md 5.3; the rule every float grade follows:
// max(k x range, m x ulp(|value|), abs)), and the numbers behind its M and ABS tables measured again on this GPU.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/parity/grade_test.mjs
//
// (on a shared machine put $EIDO_GPU_WRAP in front; one short GPU job). Three parts:
//   1. grade(), gradeArray(), ulp32() and ulp64() on plain numbers: a value one float32 step off a nearly flat
//      channel far from zero passes with the rounding allowance and fails without it; a real error still fails.
//   2. The f32 built-ins of this GPU against the correctly rounded value (float64 in JavaScript, rounded once): pow,
//      exp, log, sqrt, tan, atan, atan2 and division over the plan's probe ranges; log near 1 and tan and sin near
//      0, where the error is absolute; sin and cos of arguments up to 20, whose error grows with the argument
//      (trigAbs). Every sample must sit inside max(M x ulp, ABS): that is the claim "a correct port cannot fail a
//      grade on rounding alone".
//   3. kernelCases(): the kernel fixtures' cases (tests/parity/fixtures.py --kernels) of the seven kernels the plan's
//      probes transcribed (tests/design_probes/wgsl/), each through the production runner at the kernel grade. The
//      production copies of those kernels belong to the hydrology and fluvial packages; this checks the fixtures
//      and the harness they will be tested with.
// Writes tests/out/parity/grade_test.json. JavaScript per sample here is test code.

import * as G from '../../core/gpu.js';
import { lcg } from '../core_runner/_common.mjs';
import * as C from './_common.mjs';

const T = new C.Checks('parity/grades');

// ------------------------------------------------------------------------------------------ 1. plain numbers ---
{
    const f = Math.fround;
    T.ok('ulp32 and ulp64 are numpy\'s spacing', C.ulp32(1) === 2 ** -23 && C.ulp32(-3000) === 2 ** -12 && C.ulp32(0) === 2 ** -149 &&
        C.ulp64(1) === 2 ** -52 && C.ulp64(1e10) === 2 ** -19, `${C.ulp32(1)} ${C.ulp32(-3000)} ${C.ulp64(1)}`);
    // a field of 2,400 m with 2 mm of relief: 1e-4 of its range is 0.2 micrometres, a float32 step there is 0.24 mm
    const want = Float32Array.from({ length: 64 }, (_, i) => 2400 + 0.002 * (i / 63));
    const got = Float32Array.from(want);
    got[10] = f(got[10] + 2 * C.ulp32(2400));
    const bare = C.gradeArray(got, want, { k: 1e-4 }), ruled = C.gradeArray(got, want, { k: 1e-4, uses: [] });
    T.ok('a nearly flat channel far from zero, two float32 steps off: fails on k x range alone, passes with the rounding allowance',
        !bare.ok && ruled.ok && ruled.tol === 4 * C.ulp32(want[63]), `|d| ${C.sci(ruled.err)}; k x range ${C.sci(bare.tol)}; with m = 4: ${C.sci(ruled.tol)}`);
    got[10] = f(want[10] + 0.5);
    T.ok('a real error on the same channel still fails', !C.gradeArray(got, want, { k: 1e-4, uses: ['pow'] }).ok);
    const g1 = C.grade(3e-7, 0, { uses: ['log'] }), g2 = C.grade(1e-6, 0, { uses: ['log'] }), g3 = C.grade(3e-7, 0, { uses: ['sqrt'] });
    T.ok('the absolute bound of log near 1 (a result near 0): 3e-7 passes, 1e-6 fails; without log in `uses` 3e-7 fails',
        g1.ok && !g2.ok && !g3.ok && g1.tol === C.ABS.log, `tolerance ${C.sci(g1.tol)}`);
    T.ok('trigAbs grows with the argument: 4 x |x| x 2^-23, never below ABS.sin', C.trigAbs(20) === 80 * 2 ** -23 && C.trigAbs(0.5) === C.ABS.sin);
    const inter = Float32Array.from([1, 100, 2, 200, 3, 300]), inter2 = Float32Array.from([1, 100.5, 2, 200, 3, 300]);
    T.ok('gradeArray grades one channel of an interleaved array (stride and offset)',
        C.gradeArray(inter2, inter, { k: 1e-4, stride: 2, offset: 0 }).ok && !C.gradeArray(inter2, inter, { k: 1e-4, stride: 2, offset: 1 }).ok);
    const nan = Float32Array.from([NaN, 1, Infinity]), nan2 = Float32Array.from([NaN, 1, Infinity]), nan3 = Float32Array.from([0, 1, Infinity]);
    T.ok('NaN and infinities: equal where both have them, a failure where one does not',
        C.gradeArray(nan2, nan, { k: 1e-4 }).ok && !C.gradeArray(nan3, nan, { k: 1e-4 }).ok);
    T.throws('an unknown built-in is refused, naming the known ones', () => C.grade(1, 1, { uses: ['sinh'] }), 'no measured error');
    T.ok('the largest m among the built-ins counts', C.grade(1 + 60 * 2 ** -23, 1, { uses: ['sqrt', 'pow'] }).ok &&
        !C.grade(1 + 60 * 2 ** -23, 1, { uses: ['sqrt'] }).ok);
}

// -------------------------------------------------------------------------------------- 2. the built-ins ---
const R = await G.init();
T.extra.adapter = R.info?.description ?? null;
{
    const N = 256, n = N * N, rnd = lcg(20261114);
    const xin = new Float32Array(4 * n), yin = new Float32Array(4 * n);
    for (let i = 0; i < n; i++) {
        xin[4 * i] = 10 ** (-3 + 9 * rnd());                         // a in (1e-3, 1e6), every decade alike
        xin[4 * i + 1] = 0.3 + 2.2 * rnd();                          // b in (0.3, 2.5)
        xin[4 * i + 2] = -20 + 40 * rnd();                           // c in (-20, 20)
        xin[4 * i + 3] = -1.5 + 3 * rnd();                           // d in (-1.5, 1.5)
        const sgn = rnd() < 0.5 ? -1 : 1;
        yin[4 * i] = 1 + sgn * 10 ** (-7 + 6 * rnd());               // e: within 1e-7 .. 1e-1 of 1
        yin[4 * i + 1] = sgn * 10 ** (-8 + 7 * rnd());               // f: 1e-8 .. 1e-1 from 0
        yin[4 * i + 2] = Math.PI * Math.round(-6 + 12 * rnd()) + sgn * 10 ** (-7 + 5 * rnd());        // near a zero of sin
        yin[4 * i + 3] = Math.PI * (Math.round(-6 + 12 * rnd()) + 0.5) + sgn * 10 ** (-7 + 5 * rnd()); // near a zero of cos
    }
    const k = R.kernel('parity_builtins', `//! sampler xin
//! sampler yin
//! image outA rgba32f
//! image outB rgba32f
//! image outC rgba32f
//! image outD rgba32f
fn kmain(p: vec2<i32>) {
  if (!inside(p, xin_size())) { return; }
  let v = xin_at(p);
  let w = yin_at(p);
  outA_store(p, vec4<f32>(pow(v.x, v.y), exp(v.z), log(v.x), sqrt(v.x)));
  outB_store(p, vec4<f32>(tan(v.w), atan(5.0 * v.w), atan2(v.z, v.w), v.x / v.y));
  outC_store(p, vec4<f32>(sin(v.z), cos(v.z), log(w.x), tan(w.y)));
  outD_store(p, vec4<f32>(sin(w.z), cos(w.w), sin(w.y), 0.0));
}`);
    const fx = R.field(N, N, 4, xin), fy = R.field(N, N, 4, yin);
    const outs = { outA: R.empty([N, N], 4), outB: R.empty([N, N], 4), outC: R.empty([N, N], 4), outD: R.empty([N, N], 4) };
    R.run(k, { xin: fx, yin: fy }, outs, {});
    const [A, B, Cc, D] = await R.readAll(Object.values(outs));
    for (const f of [fx, fy, ...Object.values(outs)]) f.destroy();
    const f = Math.fround;
    // [name, the built-in graded, got(i), the correctly rounded reference(i), the argument(i) when the allowance is
    //  trigAbs(argument): sin and cos of arguments beyond 1]
    const rows = [
        ['pow(a, b)', 'pow', (i) => A[4 * i], (i) => Math.pow(xin[4 * i], xin[4 * i + 1])],
        ['exp(c)', 'exp', (i) => A[4 * i + 1], (i) => Math.exp(xin[4 * i + 2])],
        ['log(a)', 'log', (i) => A[4 * i + 2], (i) => Math.log(xin[4 * i])],
        ['sqrt(a)', 'sqrt', (i) => A[4 * i + 3], (i) => Math.sqrt(xin[4 * i])],
        ['tan(d)', 'tan', (i) => B[4 * i], (i) => Math.tan(xin[4 * i + 3])],
        ['atan(5 d)', 'atan', (i) => B[4 * i + 1], (i) => Math.atan(f(5 * xin[4 * i + 3]))],
        ['atan2(c, d)', 'atan2', (i) => B[4 * i + 2], (i) => Math.atan2(xin[4 * i + 2], xin[4 * i + 3])],
        ['a / b', 'divide', (i) => B[4 * i + 3], (i) => xin[4 * i] / xin[4 * i + 1]],
        ['log(e), e near 1', 'log', (i) => Cc[4 * i + 2], (i) => Math.log(yin[4 * i])],
        ['tan(f), f near 0', 'tan', (i) => Cc[4 * i + 3], (i) => Math.tan(yin[4 * i + 1])],
        ['sin(f), f near 0', 'sin', (i) => D[4 * i + 2], (i) => Math.sin(yin[4 * i + 1])],
        ['sin(c), |c| up to 20', 'sin', (i) => Cc[4 * i], (i) => Math.sin(xin[4 * i + 2]), (i) => xin[4 * i + 2]],
        ['cos(c), |c| up to 20', 'cos', (i) => Cc[4 * i + 1], (i) => Math.cos(xin[4 * i + 2]), (i) => xin[4 * i + 2]],
        ['sin near its zeros up to 6 pi', 'sin', (i) => D[4 * i], (i) => Math.sin(yin[4 * i + 2]), (i) => yin[4 * i + 2]],
        ['cos near its zeros up to 6.5 pi', 'cos', (i) => D[4 * i + 1], (i) => Math.cos(yin[4 * i + 3]), (i) => yin[4 * i + 3]],
    ];
    const measured = {};
    for (const [name, builtin, got, ref, arg] of rows) {
        const steps = new Float64Array(n);
        let outside = 0, worstAbs = 0, worstOver = 0, worstPerArg = 0;
        for (let i = 0; i < n; i++) {
            const g = got(i), r = ref(i), rr = f(r);
            const e = Math.abs(g - r);
            steps[i] = Math.abs(g - rr) / C.ulp32(rr);
            worstAbs = Math.max(worstAbs, e);
            const abs = arg ? C.trigAbs(arg(i)) : (C.ABS[builtin] ?? 0);
            const tol = Math.max(C.M[builtin] * C.ulp32(rr), abs);
            worstOver = Math.max(worstOver, e / tol);
            if (arg) worstPerArg = Math.max(worstPerArg, e / (Math.max(1, Math.abs(arg(i))) * 2 ** -23));
            if (!(e <= tol)) outside++;
        }
        steps.sort();
        const m = { max_steps: +steps[n - 1].toFixed(1), p99_steps: +steps[Math.floor(0.99 * n)].toFixed(1), max_abs: worstAbs,
            max_abs_in_steps_of_1: +(worstAbs / 2 ** -23).toFixed(2), allowed_m: C.M[builtin],
            allowed_abs: arg ? 'trigAbs(argument)' : (C.ABS[builtin] ?? 0), largest_share_of_the_allowance: +worstOver.toFixed(3) };
        if (arg) m.max_abs_over_argument_steps = +worstPerArg.toFixed(2);
        measured[name] = m;
        const allow = arg ? ', trigAbs(argument))' : (C.ABS[builtin] ? `, ${C.sci(C.ABS[builtin], 1)} absolute)` : ')');
        T.ok(`${name}: every one of ${n} samples within max(${C.M[builtin]} float32 steps${allow}`,
            outside === 0, `largest ${m.max_steps} steps (99th percentile ${m.p99_steps}); largest absolute error ${C.sci(worstAbs)} ` +
            `(${m.max_abs_in_steps_of_1} steps of 1.0` + (arg ? `, ${m.max_abs_over_argument_steps} x |argument| x 2^-23` : '') +
            `); ${(100 * worstOver).toFixed(0)} % of the allowance` + (outside ? `; ${outside} outside` : ''));
    }
    T.extra.builtins = measured;
}

// ---------------------------------------------------------------- 3. the kernel fixtures through the runner ---
{
    const fx = C.loadFixture('kernels');
    if (fx) {
        T.extra.fixture_versions = fx.manifest.versions;
        const probes = new URL('../design_probes/wgsl/', import.meta.url);
        const all = {};
        let total = 0, worst = 0;
        // the built-ins each kernel leans on (its WGSL text): flow_weights raises slopes to a power, route_incise is
        // the stream power law, the others are sums, divisions and square roots
        const uses = { flow_weights: ['pow', 'sqrt'], route_incise: ['pow', 'sqrt'], creep: ['divide'], threshold_excess: ['sqrt', 'divide'],
            threshold: ['sqrt', 'divide'], creep_layers: ['divide'], h_keep: [] };
        for (const name of Object.keys(uses)) {
            const kern = R.kernel(name, { url: new URL(`${name}.wgsl`, probes).href, blender: true });
            const r = await C.kernelCases(R, name, { kernel: kern, uses: uses[name], fixture: fx });
            all[name] = { cases: r.n, worst: +r.worst.toExponential(3), failed: r.failed };
            total += r.n;
            worst = Math.max(worst, r.worst);
            T.ok(`kernel fixtures: ${name}: ${r.n} case${r.n === 1 ? '' : 's'} of the Blender tests within the kernel grade`, r.ok && r.n > 0, r.detail);
        }
        T.extra.kernel_cases = all;
        T.ok(`kernel fixtures: ${total} cases of seven kernels through C.kernelCases, worst ${C.sci(worst)} of range (the grade: 1e-4)`,
            total >= 60 && worst <= 1e-4);
        const none = await C.kernelCases(R, 'no_such_kernel', { fixture: fx, kernel: null });
        T.ok('a kernel with no fixture case is reported, not passed', none.n === 0 && !none.ok, none.detail);
    }
}

const code = C.finish(T, 'grade_test');
G.shutdown();
Deno.exit(code);
