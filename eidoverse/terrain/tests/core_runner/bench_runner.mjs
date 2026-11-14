// The plan's GPU benchmark (PORT_PLAN.md 4.8) re-run through the production runner (core/gpu.js) instead of the
// design probes' prototype (8.2, P1): the Blender design's probe kernel (one stream-power gather step, RGBA32F in
// and out), the Blender fluvial production step (9 passes: flow_weights, route_incise, h_keep, creep, creep_layers,
// threshold_excess and threshold twice, at the Blender cost test's settings, from the design probes' transcribed
// kernels), the cost of reading a field back, and determinism (the step run twice for 205 steps, bit for bit).
//
//     <Blender's python> -I eidoverse/terrain/tests/core_runner/twin_fixtures.py
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/core_runner/bench_runner.mjs [fixtures]
//
// GPU times are timestamp queries over one pass of many steps (Runner.timed); wall times are the loop without
// readbacks. The machine is shared, so the numbers move with what else runs (plan 4.8 ran each twice). On a shared
// machine put $EIDO_GPU_WRAP in front of the deno command.

import * as G from '../../core/gpu.js';
import { Checks, PROBES, bitsEqual, loadBin } from './_common.mjs';
import { twinFixtures } from './_twins.mjs';

const T = new Checks('core_runner/bench');
const R = await G.init();
T.extra.adapter = R.info?.description ?? null;
const PLAN = {                                           // PORT_PLAN.md 4.8, measured with the prototype
    probe_gpu_ms_per_pass: { 512: '0.0059-0.0066', 1024: '0.026', 2048: '0.20-0.28', 4096: '0.77-0.85' },
    probe_wall_ms_per_step: { 512: 0.032, 1024: 0.047, 2048: 0.32 },
    fluvial_wall_ms_per_step_quiet: { 512: 0.26, 1024: 1.08, 2048: 3.91 },
    fluvial_gpu_ms_per_step_quiet: { 512: 0.079, 1024: 0.61, 2048: 3.01 },
    fluvial_blender_glsl_wall_ms: { 1024: 1.02, 2048: 4.46 },
    readback_ms: { '1024 r32f': 27.8, '1024 rgba32f': 73.6, '2048 r32f': 63.9, '2048 rgba32f': 215.7 },
};
T.extra.plan = PLAN;

// ---- 1. the probe kernel: the gather of design section 2.5 (the prototype's STEP_BUF body, in the runner's grammar)
const PROBE = R.kernel('probe_step', `//! sampler src
//! image   dst rgba32f
//! uniform float dt
//! uniform float k
//! uniform float up
//! uniform float dx
//! uniform float cell
fn kmain(p: vec2<i32>) {
  let n = src_size();
  if (p.x >= n.x || p.y >= n.y) { return; }
  let c = src_at(p);
  let h = c.x;
  var best = 0.0;
  var acc = u.cell;
  var wsum = 0.0;
  for (var dy = -1; dy <= 1; dy++) {
    for (var dx = -1; dx <= 1; dx++) {
      if (dx == 0 && dy == 0) { continue; }
      let q = (p + vec2<i32>(dx, dy) + n) % n;
      let v = src_at(q);
      let d = length(vec2<f32>(f32(dx), f32(dy))) * u.dx;
      best = max(best, (h - v.x) / d);
      acc += max((v.x - h) / d, 0.0) * v.y * v.z;
      wsum += max((h - v.x) / d, 0.0);
    }
  }
  let hn = h - u.dt * u.k * sqrt(acc) * best + u.dt * u.up;
  dst_store(p, vec4<f32>(hn, acc, 1.0 / max(wsum, 1e-6), 1.0));
}`);
const probeUn = { dt: 100.0, k: 1e-5, up: 1e-3, dx: 10.0, cell: 100.0 };
T.extra.probe = {};
for (const N of [512, 1024, 2048, 4096]) {
    const init = new Float32Array(N * N * 4);
    for (let i = 0; i < N * N; i++) {                   // test data: a tilted, rippled plane (JS per cell: tests only)
        const x = i % N, y = Math.floor(i / N);
        init[4 * i] = 0.01 * x + 0.02 * y + Math.sin(x * 0.05) * Math.cos(y * 0.07) * 5;
        init[4 * i + 1] = 1;
        init[4 * i + 2] = 1;
        init[4 * i + 3] = 1;
    }
    const pp = R.pair(N, N, 4, init);
    const S = 200;
    const step = () => { R.run(PROBE, { src: pp.src }, { dst: pp.dst }, probeUn); pp.swap(); };
    for (let i = 0; i < 5; i++) step();
    await R.idle();
    const gpu = await R.timed(() => { for (let i = 0; i < S; i++) step(); });
    let wall = null;
    if (N <= 2048) {
        await R.idle();
        const t0 = performance.now();
        for (let i = 0; i < 500; i++) step();
        await R.idle();
        wall = (performance.now() - t0) / 500;
    }
    T.extra.probe[N] = { gpu_ms_per_pass: gpu == null ? null : +(gpu / S).toFixed(4), wall_ms_per_step: wall == null ? null : +wall.toFixed(4) };
    console.log('probe kernel', N, JSON.stringify(T.extra.probe[N]));
    pp.destroy();
}

// ---- 2. the fluvial production step: 9 passes, timed, deterministic
const FIX = twinFixtures(Deno.args[0]);
if (FIX) {
    const man = JSON.parse(Deno.readTextFileSync(new URL('manifest.json', FIX)));
    const K = {};
    for (const name of ['flow_weights', 'route_incise', 'creep', 'threshold_excess', 'threshold', 'creep_layers', 'h_keep', 'world_noise_field']) {
        K[name] = R.kernel(name, { url: new URL(`wgsl/${name}.wgsl`, PROBES).href, blender: true });
    }
    async function fluvialStep(N, steps, timed) {
        const cell = 10.0, nz = man.noise;
        // the start: an fbm field, 2000 m of relief, by the world-noise kernel; the packs as the probe built them
        const hf = R.field(N, N, 1), terms = R.field(1, 2 * nz.n_terms, 4, loadBin(FIX, nz.terms)), disp = R.field(N, N, 2);
        R.run(K.world_noise_field, { terms, disp }, { outF: hf }, { uTerms: nz.n_terms, uCell: cell, uConst: 0.0 });
        const h0 = await R.read(hf);
        const st = new Float32Array(N * N * 4), par = new Float32Array(N * N * 4), pin = new Float32Array(N * N * 4);
        for (let i = 0; i < N * N; i++) {
            const h = 1000.0 + 1000.0 * h0[i];
            st[4 * i] = h; st[4 * i + 1] = cell * cell;
            par[4 * i] = 2e-3; par[4 * i + 1] = 1.5e-5; par[4 * i + 2] = 0.7; par[4 * i + 3] = 0.5;
            const x = i % N, y = Math.floor(i / N);
            if (x === 0 || y === 0 || x === N - 1 || y === N - 1) { pin[4 * i] = 1.0; pin[4 * i + 1] = h; }
        }
        const S = [R.field(N, N, 4, st), R.field(N, N, 4)], M = [R.field(N, N, 4), R.field(N, N, 4)];
        const Wt = R.field(N, N, 1), Hk = R.field(N, N, 1), Phi = R.field(N, N, 1);
        const P = R.field(N, N, 4, par), Q = R.field(N, N, 4, pin), one = R.field(1, 1, 1);
        let s = 0, m = 0;
        const B = 2;
        const step = () => {
            R.run(K.flow_weights, { st: S[s] }, { outW: Wt }, { uDx: cell, uP: 1.0, uBound: B });
            R.run(K.route_incise, { st: S[s], wsumT: Wt, par: P, pin: Q, mk: M[m], kcol: one, zoff: one }, { outS: S[1 - s], outM: M[1 - m] },
                { uDx: cell, uDt: 130.0, uM: 0.5, uN: 1.0, uP: 1.0, uColZ0: 0.0, uColDz: 1.0, uColN: 0, uSlope: 1, uPitFill: 1, uPitEps: 1e-3, uBound: B });
            s = 1 - s; m = 1 - m;
            R.run(K.h_keep, { st: S[s] }, { outH: Hk }, {});
            R.run(K.creep, { st: S[s], par: P, pin: Q }, { outS: S[1 - s] }, { uDx: cell, uDtSub: 130.0, uD: 0.05, uCap: 5.0, uBound: B });
            s = 1 - s;
            R.run(K.creep_layers, { st: S[s], h0: Hk, mk: M[m] }, { outM: M[1 - m] }, {});
            m = 1 - m;
            for (let it = 0; it < 2; it++) {
                R.run(K.threshold_excess, { st: S[s], par: P }, { outP: Phi }, { uDx: cell, uBound: B });
                R.run(K.threshold, { st: S[s], par: P, pin: Q, mk: M[m], phiT: Phi }, { outS: S[1 - s], outM: M[1 - m] },
                    { uDx: cell, uRate: 0.12, uLoose: 0, uIso: 1, uBound: B });
                s = 1 - s; m = 1 - m;
            }
        };
        for (let i = 0; i < 5; i++) step();
        await R.idle();
        const d0 = R.dispatches;
        let issue = 0;
        const t0 = performance.now();
        for (let i = 0; i < steps; i++) {
            const a = performance.now();
            step();
            issue += performance.now() - a;
        }
        await R.idle();
        const wall = (performance.now() - t0) / steps;
        const perStep = (R.dispatches - d0) / steps;
        const out = await R.read(S[s]);
        const gpu = timed ? await R.timed(() => { for (let i = 0; i < 50; i++) step(); }) : null;
        for (const f of [...S, ...M, Wt, Hk, Phi, P, Q, one, hf, terms, disp]) f.destroy();
        return { wall_ms_per_step: +wall.toFixed(4), js_issue_ms_per_step: +(issue / steps).toFixed(4), dispatches_per_step: perStep,
            gpu_timestamp_ms_per_step: gpu == null ? null : +(gpu / 50).toFixed(4), out };
    }
    T.extra.fluvial_step = {};
    let allSame = true;
    for (const N of [512, 1024, 2048]) {
        const r1 = await fluvialStep(N, 200, true);
        const r2 = await fluvialStep(N, 200, false);
        const same = bitsEqual(r1.out, r2.out);
        allSame = allSame && same;
        delete r1.out;
        T.extra.fluvial_step[N] = { ...r1, wall_ms_per_step_second_run: r2.wall_ms_per_step, deterministic_205_steps: same };
        console.log('fluvial step', N, JSON.stringify(T.extra.fluvial_step[N]));
    }
    T.ok('determinism: the 9-pass fluvial step, 205 steps twice at 512, 1024 and 2048, bit for bit', allSame);
    // recorded, not gated: the machine is shared (plan 4.8's second run had a Blender job beside it)
    T.extra.fluvial_against_blender = Object.fromEntries([1024, 2048].map((N) => [N, +(Math.min(T.extra.fluvial_step[N].wall_ms_per_step,
        T.extra.fluvial_step[N].wall_ms_per_step_second_run) / PLAN.fluvial_blender_glsl_wall_ms[N]).toFixed(2)]));
}

// ---- 3. readback: one field, whole, into a preallocated array (the runner's one mapped buffer)
T.extra.readback_ms = {};
for (const [N, c] of [[1024, 1], [1024, 4], [2048, 1], [2048, 4]]) {
    const f = R.field(N, N, c);
    const into = new Float32Array(N * N * c);
    await R.read(f, into);
    const t = [];
    for (let i = 0; i < 5; i++) {
        const t0 = performance.now();
        await R.read(f, into);
        t.push(performance.now() - t0);
    }
    t.sort((a, b) => a - b);
    T.extra.readback_ms[`${N} ${c === 1 ? 'r32f' : 'rgba32f'}`] = +t[2].toFixed(1);
    f.destroy();
}
{
    const f = R.field(1, 4, 1);
    const t = [];
    for (let i = 0; i < 15; i++) {
        const t0 = performance.now();
        await R.readRange(f, 0, 4);
        t.push(performance.now() - t0);
    }
    t.sort((a, b) => a - b);
    T.extra.readback_ms['16 bytes'] = +t[7].toFixed(2);
    f.destroy();
}
console.log('readback', JSON.stringify(T.extra.readback_ms));
T.ok('readback: a 2048 x 2048 RGBA32F field in under a second', T.extra.readback_ms['2048 rgba32f'] < 1000, `${T.extra.readback_ms['2048 rgba32f']} ms`);

T.extra.counters = { dispatches: R.dispatches, submits: R.submits, peak_field_mb: +(R.peakFieldBytes / 2 ** 20).toFixed(1) };
const code = T.done('bench_runner.json');
G.shutdown();
Deno.exit(code);
