// The hydrology package's kernel and function fixtures (PORT_PLAN.md 8.2 row P5, 5.1, 5.3): every case the Blender
// edition's own Python made (tests/parity/fixtures.py --kernels and --functions --only hydro) through the port's
// solvers/hydro.js and its kernels, on the production runner.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/hydro/hydro_test.mjs
//         [--only fill_depressions,lakes,...]          (on a shared machine, behind $EIDO_GPU_WRAP)
//
// Grades (plan 5.3):
//   kernels            flow_weights and route_area against their numpy twins: <= 1e-4 of each channel's range
//   fill_depressions   the spill levels bit for bit (numpy's float64 result is float32-valued), the outlet equal
//   flat_distance, flow_receivers (and fluvial.d8_receivers), path_steps       exact
//   _descend           the path-maximum form within 2 float32 steps of numpy's float64 (C11)
//   routing_surface    within 2 float32 steps of numpy's float64 surface; bit-equal cells counted
//   route_to_convergence   the drainage area within 1e-4 of its range; the iterations equal (or one test apart)
//   lakes, _parent_lake_water   h, water, deposit and the fill bit for bit; the lake count equal
//   inflow             within 1e-6 of the range (p = 1); with p != 1 pow()'s measured allowance as well
// JavaScript per cell here is test code (the edition's rule allows it in tests only). Writes
// tests/out/hydro/hydro_test.json.

import * as G from '../../core/gpu.js';
import { Level } from '../../core/levels.js';
import * as HY from '../../solvers/hydro.js';
import * as C from '../parity/_common.mjs';

const W = C.W;
const args = [...Deno.args];
const onlyAt = args.indexOf('--only');
const ONLY = onlyAt >= 0 ? new Set(args[onlyAt + 1].split(',')) : null;
const want = (f) => !ONLY || ONLY.has(f);

const T = new C.Checks('hydro: kernel and function fixtures');
const R = await G.init();
const results = { functions: {}, kernels: {} };

// ------------------------------------------------------------------------------------------------- helpers ---

const f32 = (a) => (a instanceof Float32Array ? a : Float32Array.from(a, (x) => x));
const i32 = (a) => Int32Array.from(a, (x) => Number(x));
function field(a, shape) {
    return R.field(shape[0], shape[1], 1, f32(a));
}
/** float64 values that are float32 values (numpy's fill of float32 heights): count of those that are not. */
function notF32(a) {
    let n = 0;
    for (let i = 0; i < a.length; i++) if (Math.fround(a[i]) !== a[i]) n++;
    return n;
}
function bitsDiff(got, want32) {
    const g = new Uint32Array(got.buffer, got.byteOffset, got.length), w = new Uint32Array(want32.buffer, want32.byteOffset, want32.length);
    let n = 0, first = -1;
    for (let i = 0; i < w.length; i++) if (g[i] !== w[i]) { n++; if (first < 0) first = i; }
    return { n, first };
}
function intDiff(got, want) {
    let n = 0, first = -1;
    for (let i = 0; i < want.length; i++) if (Number(got[i]) !== Number(want[i])) { n++; if (first < 0) first = i; }
    return { n, first };
}
function ulpStats(got, want64) {
    let worst = 0, over1 = 0, exact = 0, at = -1;
    for (let i = 0; i < want64.length; i++) {
        const u = C.ulp32(want64[i]) || 1e-45;
        const e = Math.abs(got[i] - want64[i]) / u;
        if (Math.fround(want64[i]) === got[i]) exact++;
        if (e > 1) over1++;
        if (e > worst) { worst = e; at = i; }
    }
    return { worst, over1, exact, at, n: want64.length };
}
const rec = (name) => (results.functions[name] ??= { cases: 0, failed: [], rows: [] });
function row(name, label, ok, detail) {
    const r = rec(name);
    r.cases++;
    if (!ok) r.failed.push(label);
    r.rows.push({ label, ok, ...detail });
    if (!ok) console.log(`  FAIL ${name}: ${label}: ${JSON.stringify(detail).slice(0, 300)}`);
}
function verdict(name, what) {
    const r = results.functions[name];
    if (!r) return;
    T.ok(`${name}: ${r.cases - r.failed.length} of ${r.cases} cases ${what}`, r.cases > 0 && r.failed.length === 0,
        r.failed.slice(0, 4).join(' | '));
}
const level = (d) => Level.fromDict(d);

// ------------------------------------------------------------------------------------------------- kernels ---

if (want('kernels')) {
    for (const [name, uses] of [['flow_weights', ['pow', 'divide']], ['route_area', ['pow', 'divide']]]) {
        const r = await C.kernelCases(R, name, { uses });
        if (!r) { T.ok(`${name}: kernel fixtures`, false, 'no kernel fixtures (tests/parity/fixtures.py --kernels)'); continue; }
        results.kernels[name] = { n: r.n, worst: r.worst, failed: r.failed };
        T.ok(`${name}: ${r.n} kernel fixture cases within 1e-4 of each channel's range`, r.ok, r.detail);
    }
}

// hydro/lib's integer sums on this device: sum3 equal to the exact sum rounded once, sum_sign4 equal to the exact
// sign (every value here is a float32 of 1e-3 to 1e4 in magnitude, so the sums are exact in JavaScript's doubles,
// and Math.fround of the double sum is the exact sum's rounding); ties and cancellations included; and whether fma()
// is fused here (informational: the receivers' and the descent's fma rounds once when it is)
if (want('kernels') || want('lakes') || want('_parent_lake_water')) {
    const N = 16384, data = new Float32Array(N * 4);
    let s = 12345;
    const rnd = () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296;
    const val = () => Math.fround((rnd() < 0.5 ? -1 : 1) * 10 ** (rnd() * 7 - 3));
    for (let i = 0; i < N; i++) {
        const a = val(), b = val();
        const kind = i % 4;                              // 0 random; 1 a + b - a (exact cancellation); 2 a tie; 3 c ~ -(a+b)
        let c = val();
        if (kind === 1) c = -a;
        if (kind === 3) c = Math.fround(-(a + b));
        data.set([a, b, c, kind === 2 ? val() : -c], 4 * i);
    }
    data.set([1 + 2 ** -12, 1 + 2 ** -12, -(1 + 2 ** -11), 0], 0);          // a b + c = 2^-24 exactly (fma probe)
    data.set([1, 2 ** -24, 0, 0], 4);                                       // a tie: rounds to even (1)
    data.set([1 + 2 ** -23, 2 ** -24, 0, 0], 8);                            // a tie: rounds to even (1 + 2^-22)
    const k = R.kernel('hydro_lib_check', { source: '//! include hydro/lib\n//! sampler ab\n//! image outS rgba32f\n' +
        'fn kmain(p: vec2<i32>) {\n  if (!inside(p, outS_size())) { return; }\n  let v = ab_at(p);\n' +
        '  outS_store(p, vec4<f32>(sum3(v.x, v.y, v.z), f32(sum_sign4(v.x, v.y, v.z, v.w)), fma(v.x, v.y, v.z), 0.0));\n}\n' });
    const ab = R.field(1, N, 4, data), o = R.field(1, N, 4);
    R.run(k, { ab }, { outS: o }, {});
    const g = await R.read(o);
    let badSum = 0, badSign = 0;
    const firstBad = [];
    for (let i = 1; i < N; i++) {
        const [a, b, c, d] = [data[4 * i], data[4 * i + 1], data[4 * i + 2], data[4 * i + 3]];
        if (g[4 * i] !== Math.fround(a + b + c) && !(g[4 * i] === 0 && a + b + c === 0)) {
            badSum++;
            if (firstBad.length < 4) firstBad.push([a, b, c, g[4 * i], Math.fround(a + b + c)]);
        }
        if (g[4 * i + 1] !== Math.sign(a + b + c + d)) badSign++;
    }
    results.fma_fused = g[2] === 2 ** -24;
    results.integer_sums = { triples: N - 1, wrong_sum3: badSum, wrong_sign4: badSign, first_wrong: firstBad, fma_probe: g[2] };
    T.ok(`hydro/lib: sum3 rounded once and sum_sign4 exact on ${N - 1} random sums with cancellations and ties ` +
        `(fma fused here: ${results.fma_fused})`, badSum === 0 && badSign === 0, `sum3 wrong ${badSum}, sum_sign4 wrong ${badSign} ` +
        JSON.stringify(firstBad));
    ab.destroy();
    o.destroy();
}

// ---------------------------------------------------------------------------------------------- functions ---

const fx = C.loadFixture('functions/hydro');
if (!fx) {
    T.ok('hydro function fixtures', false, 'none: <Blender\'s python> -I eidoverse/terrain/tests/parity/fixtures.py --functions --only hydro');
} else {
    const A = (a) => C.array(fx.dir, a);
    let nonF32Inputs = 0;
    for (const c of fx.manifest.cases) {
        const fn = c.function.split('.').pop();
        if (!want(fn)) continue;
        const a = c.args ?? {};
        const wrap = a.wrap ?? [false, false], seaLevel = a.sea_level ?? null;
        const out = {};
        for (const [k, v] of Object.entries(c.outputs)) out[k] = v && v.file ? A(v) : null;
        if (fn === 'fill_depressions') {
            const hi = c.inputs.height;
            const h = field(A(hi), hi.shape);
            const { filled, info } = await HY.fillDepressions(h, { wrap, seaLevel });
            const got = await R.read(filled);
            const d = bitsDiff(got, out.filled_f32);
            row(fn, c.label, d.n === 0 && info.outlet === c.values.outlet && notF32(out.filled) === 0,
                { differ: d.n, outlet: [info.outlet, c.values.outlet], dispatches: info.dispatches });
            h.destroy();
            filled.destroy();
        } else if (fn === 'flat_distance') {
            const si = c.inputs.surface, s64 = A(si);
            nonF32Inputs += notF32(s64);
            const s = field(s64, si.shape);
            const dist = await HY.flatDistance(s, { wrap, seaLevel });
            const got = await R.read(dist);
            const d = intDiff(got, out.dist);
            row(fn, c.label, d.n === 0, { differ: d.n });
            s.destroy();
            dist.destroy();
        } else if (fn === 'flow_receivers') {
            const fi = c.inputs.filled;
            const f = field(A(fi), fi.shape);
            const r1 = await HY.flowReceivers(f, { wrap, seaLevel }), r2 = HY.d8Receivers(f);
            const [g1, g2] = await R.readAll([r1, r2]);
            const d1 = intDiff(g1, out.rec), d2 = intDiff(g2, out.d8);
            row(fn, c.label, d1.n === 0 && d2.n === 0, { rec_differ: d1.n, d8_differ: d2.n });
            for (const x of [f, r1, r2]) x.destroy();
        } else if (fn === 'path_steps') {
            const ri = c.inputs.rec;
            // the receivers are flat; the field is the one its label names (fixtures.py _hydro_fields)
            const shape = c.label.includes('crater_lake') ? [160, 192] : [80, 96];
            if (shape[0] * shape[1] !== ri.shape[0]) throw new Error(`path_steps ${c.label}: ${ri.shape[0]} cells, not ${shape}`);
            const rf = R.field(shape[0], shape[1], 1, i32(A(ri)), 'i32');
            const steps = await HY.pathSteps(rf);
            const got = await R.read(steps);
            const d = intDiff(got, out.steps);
            row(fn, c.label, d.n === 0, { differ: d.n });
            rf.destroy();
            steps.destroy();
        } else if (fn === '_descend') {
            const fi = c.inputs.filled, ri = c.inputs.rec;
            const f = field(A(fi), fi.shape);
            const rf = R.field(fi.shape[0], fi.shape[1], 1, i32(A(ri)), 'i32');
            const rs = await HY.descend(f, rf, a.eps);
            const got = await R.read(rs);
            const u = ulpStats(got, out.rs);
            row(fn, c.label, u.worst <= 2, { worst_ulp: +u.worst.toFixed(3), over_1_ulp: u.over1, equal_to_f32_of_f64: u.exact, cells: u.n });
            for (const x of [f, rf, rs]) x.destroy();
        } else if (fn === 'routing_surface') {
            const fi = c.inputs.filled;
            const f = field(A(fi), fi.shape);
            const rs = await HY.routingSurface(f, { wrap, seaLevel });
            const got = await R.read(rs);
            const u = ulpStats(got, out.surface_f64), d = bitsDiff(got, out.surface);
            row(fn, c.label, u.worst <= 2, { worst_ulp: +u.worst.toFixed(3), over_1_ulp: u.over1, bit_equal_to_blender_f32: u.n - d.n, cells: u.n,
                eps: [HY.routingEps((() => { let t = 0; for (const v of A(fi)) t = Math.max(t, Math.abs(v)); return t; })()), c.values?.eps] });
            f.destroy();
            rs.destroy();
        } else if (fn === 'route_to_convergence') {
            const si = c.inputs.surface;
            const s = field(A(si), si.shape);
            const A0 = c.inputs.A0 ? field(A(c.inputs.A0), si.shape) : null;
            const Ain = c.inputs.A_in ? field(A(c.inputs.A_in), si.shape) : null;
            const r = await HY.routeToConvergence(R, s, a.cell, { A0, A_in: Ain, bound: a.bound, p: a.p, tol: a.tol, check: a.check,
                maxIter: a.max_iter });
            const got = await R.read(r.A);
            const g = C.gradeArray(got, out.A, { k: 1e-4, uses: ['pow', 'divide'] });
            const itOk = Math.abs(r.iterations - c.values.iterations) <= (a.check ?? 128);
            row(fn, c.label, g.ok && itOk, { over: g.over, err: g.err, range: g.range, iterations: [r.iterations, c.values.iterations] });
            for (const x of [s, A0, Ain, r.A]) x?.destroy();
        } else if (fn === 'lakes') {
            const hi = c.inputs.h;
            const shape = hi.shape;
            const fields = { h: field(A(hi), shape) };
            if (c.inputs.deposit) fields.deposit = field(A(c.inputs.deposit), shape);
            let noLake = null, parent = null, lv;
            if (c.inputs.no_lake) noLake = field(Float32Array.from(A(c.inputs.no_lake), (x) => (x ? 1 : 0)), shape);
            if (c.inputs.parent_h) {
                const plv = level(a.parent);
                lv = level(a.child);
                const ps = c.inputs.parent_h.shape;
                parent = [plv, { h: field(A(c.inputs.parent_h), ps), water: field(A(c.inputs.parent_water), ps) }];
            } else {
                lv = new Level(1, 'main', -0.5 * shape[1] * 10.0, -0.5 * shape[0] * 10.0, shape[1] * 10.0, 10.0, shape[1]);
            }
            const keep = new Set(Object.values(fields));
            const { filled, nlakes } = await HY.lakes(fields, lv, a.threshold_m, a.mode ?? 'lake',
                { parent, seaLevel: a.sea_level ?? null, band: a.band ?? 0, noLake });
            const names = ['h', 'water', 'deposit'].filter((k) => out[k]);
            const got = await R.readAll(names.map((k) => fields[k]));
            const diffs = {};
            names.forEach((k, i) => { diffs[k] = bitsDiff(got[i], out[k]).n; });
            const fg = await R.read(filled);
            let fdiff = 0;
            for (let i = 0; i < fg.length; i++) if (fg[i] !== out.filled[i]) fdiff++;
            const depOk = out.deposit ? true : !('deposit' in fields) || keep.has(fields.deposit);
            const ok = Object.values(diffs).every((n) => n === 0) && fdiff === 0 && nlakes === c.values.nlakes && depOk;
            row(fn, c.label, ok, { differ: diffs, filled_differ: fdiff, nlakes: [nlakes, c.values.nlakes], deposit_made: 'deposit' in fields });
            for (const x of new Set([...Object.values(fields), filled, noLake, parent?.[1].h, parent?.[1].water])) x?.destroy();
        } else if (fn === '_parent_lake_water') {
            const plv = level(a.parent), clv = level(a.child);
            const h = field(A(c.inputs.h), c.inputs.h.shape);
            const ps = c.inputs.parent_h.shape;
            const pf = { h: field(A(c.inputs.parent_h), ps), water: field(A(c.inputs.parent_water), ps) };
            const w = HY.parentLakeWater(clv, h, plv, pf);
            const got = await R.read(w);
            const d = bitsDiff(got, f32(out.water));
            row(fn, c.label, d.n === 0, { differ: d.n, cells: got.length });
            for (const x of [h, pf.h, pf.water, w]) x.destroy();
        } else if (fn === 'inflow') {
            const plv = level(a.parent), clv = level(a.child);
            const ps = c.inputs.parent_A.shape;
            const pf = { A: field(A(c.inputs.parent_A), ps), qs: field(A(c.inputs.parent_qs), ps) };
            let surf = null;
            if (c.inputs.parent_surface) surf = field(A(c.inputs.parent_surface), ps);
            if (c.inputs.parent_h) pf.h = field(A(c.inputs.parent_h), ps);
            const { A_in, qs_in } = await HY.inflow(plv, pf, clv, a.p, surf);
            const [ga, gq] = await R.readAll([A_in, qs_in]);
            const uses = a.p === 1.0 ? ['divide'] : ['pow', 'divide'];
            const g1 = C.gradeArray(ga, out.A_in, { k: 1e-6, uses }), g2 = C.gradeArray(gq, out.qs_in, { k: 1e-6, uses });
            let nz = 0;
            for (const v of out.A_in) if (v) nz++;
            row(fn, c.label, g1.ok && g2.ok, { A_in_over: g1.over, qs_in_over: g2.over, A_in_tol_over_range: g1.tol / (g1.range || 1),
                nonzero_cells: nz });
            for (const x of [pf.A, pf.qs, pf.h, surf, A_in, qs_in]) x?.destroy();
        }
    }
    results.non_float32_inputs = nonF32Inputs;
    verdict('fill_depressions', 'bit for bit, the outlet equal');
    verdict('flat_distance', 'exact');
    verdict('flow_receivers', 'exact (flow_receivers and fluvial.d8_receivers)');
    verdict('path_steps', 'exact');
    verdict('_descend', 'within 2 float32 steps of numpy\'s float64 (C11)');
    verdict('routing_surface', 'within 2 float32 steps of numpy\'s float64');
    verdict('route_to_convergence', 'within 1e-4 of the range, the iterations within one test');
    verdict('lakes', 'bit for bit (h, water, deposit, the fill) with the lake count');
    verdict('_parent_lake_water', 'bit for bit');
    verdict('inflow', 'within 1e-6 of the range (pow\'s allowance with p != 1)');
}

const code = T.done(null);
const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(), seconds: +((performance.now() - T.t0) / 1000).toFixed(2),
    checks: T.rows.length, failed: T.rows.filter((r) => !r.passed).map((r) => r.check), ...results, rows: T.rows };
Deno.writeTextFileSync(`${W.out('hydro')}/hydro_test.json`, JSON.stringify(res, null, 1));
G.shutdown();
Deno.exit(code);
