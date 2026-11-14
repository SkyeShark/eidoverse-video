// Design probe (PORT_PLAN.md sections 3 and 4.2): the WGSL ports of the fluvial step's kernels, run through the
// runner prototype (mini_runner.mjs), against the Blender edition's numpy twins on the Blender parity inputs
// (fixtures from make_twin_fixtures.py); the PCG chain and Ekigar's hash bit for bit; the world-noise kernel
// against core/world_noise.field in float64; the f32 built-ins' ULP error; then the production fluvial step
// (flow_weights + route_incise + h_keep + creep + creep_layers + (threshold_excess + threshold) x 2 = 9 passes, the
// Blender cost test's settings) timed at 512^2, 1024^2 and 2048^2, with a determinism check.
//
//     python eidoverse/terrain/tests/design_probes/make_twin_fixtures.py <fixtures>
//     deno run --no-config --no-lock --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/design_probes/kernel_parity.mjs <fixtures> [out.json]

import { Runner } from './mini_runner.mjs';

const FIX = Deno.args[0];
const OUT = Deno.args[1] ?? null;
if (!FIX) throw new Error('usage: kernel_parity.mjs <fixtures dir> [out.json]');
const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
const feats = ['timestamp-query'].filter((f) => adapter.features.has(f));
// route_incise.glsl and u_carve.glsl bind 7 inputs + 2 outputs: 9 storage buffers in one stage, one more than
// WebGPU's default maxStorageBuffersPerShaderStage (8), so the device must ask for the adapter's limit
const requiredLimits = {};
for (const k of ['maxStorageBufferBindingSize', 'maxBufferSize', 'maxStorageBuffersPerShaderStage']) requiredLimits[k] = adapter.limits[k];
const device = await adapter.requestDevice({ requiredFeatures: feats, requiredLimits });
const R = new Runner(device);
const man = JSON.parse(Deno.readTextFileSync(`${FIX}/manifest.json`));
const res = { adapter: adapter.info?.description, deno: Deno.version.deno, cases: {}, failed: [] };

function load(a) {
    const bytes = Deno.readFileSync(`${FIX}/${a.file}`);
    return a.dtype === 'u32' ? new Uint32Array(bytes.buffer) : new Float32Array(bytes.buffer);
}

const K = {};
for (const name of ['flow_weights', 'route_incise', 'creep', 'threshold_excess', 'threshold', 'creep_layers', 'h_keep',
    'world_noise_field', 'hash_probe', 'math_probe']) K[name] = R.kernel(name);
await R.check(K.world_noise_field, [4, 2]);
await R.check(K.hash_probe, [1]);
await R.check(K.math_probe, [4]);

// ---- 1. every kernel case against its numpy twin (Blender's compare(): per channel, max |d| / range <= 1e-4)
for (const c of man.cases) {
    const k = K[c.kernel];
    const samplers = {};
    for (const [s, a] of Object.entries(c.inputs)) samplers[s] = R.field(a.shape[0], a.shape[1], a.shape[2], load(a));
    await R.check(k, k.spec.samplers.map((s) => samplers[s].channels));
    const images = {};
    for (const [im, a] of Object.entries(c.outputs)) images[im] = R.field(a.shape[0], a.shape[1], a.shape[2]);
    R.run(k, samplers, images, c.uniforms);
    let worst = 0;
    const rows = [];
    for (const [im, a] of Object.entries(c.outputs)) {
        const got = await R.read(images[im]);
        const want = load(a);
        const C = a.shape[2];
        for (let ch = 0; ch < C; ch++) {
            let lo = Infinity, hi = -Infinity, amax = 0, err = 0;
            for (let i = ch; i < want.length; i += C) {
                const w = want[i];
                lo = Math.min(lo, w); hi = Math.max(hi, w); amax = Math.max(amax, Math.abs(w));
                err = Math.max(err, Math.abs(got[i] - w));
            }
            const ratio = err / Math.max(hi - lo, 1e-6 * amax, 1e-20);
            worst = Math.max(worst, ratio);
            rows.push(`${im}[${ch}] ${err.toExponential(2)}/${(hi - lo).toExponential(2)}`);
        }
    }
    const ok = worst <= 1e-4;
    res.cases[c.label] = { ok, worst: +worst.toExponential(3) };
    if (!ok) { res.failed.push(c.label); console.log('FAIL', c.label, rows.join(' ')); }
    for (const f of [...Object.values(samplers), ...Object.values(images)]) f.buffer.destroy();
    R.bindGroups.clear();
}
const worstAll = Math.max(...Object.values(res.cases).map((v) => v.worst));
console.log(`kernel cases: ${Object.keys(res.cases).length}, failed ${res.failed.length}, worst ${worstAll.toExponential(3)}`);
res.kernel_cases_worst = worstAll;

// ---- 2. hashes, bit for bit
{
    const H = 80, W = 96;
    const imgs = { outPcg: R.field(H, W, 1, null, 'u32'), outPcg2: R.field(H, W, 1, null, 'u32'),
        outPcg3: R.field(H, W, 1, null, 'u32'), outCell: R.field(H, W, 1, null, 'u32'), outU01: R.field(H, W, 1),
        outGrad: R.field(H, W, 2), outH2: R.field(H, W, 1, null, 'u32') };
    R.run(K.hash_probe, { dummy: R.field(1, 1, 1) }, imgs, {});
    const eq = (a, b) => a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
    const hm = man.hashes;
    const grad = await R.read(imgs.outGrad);
    const gradEq = (gx, gy) => gx.every((v, i) => v === grad[2 * i]) && gy.every((v, i) => v === grad[2 * i + 1]);
    let worstUlp = 0;
    {
        const gx = load(hm.ekigar_hash2_gx), gy = load(hm.ekigar_hash2_gy);
        const f = new Float32Array(1), b = new Int32Array(f.buffer);
        const bits = (v) => { f[0] = v; return b[0]; };
        for (let i = 0; i < gx.length; i++) {
            worstUlp = Math.max(worstUlp, Math.abs(bits(gx[i]) - bits(grad[2 * i])), Math.abs(bits(gy[i]) - bits(grad[2 * i + 1])));
        }
    }
    res.hashes_bit_exact = { pcg: eq(await R.read(imgs.outPcg), load(hm.pcg)), pcg2: eq(await R.read(imgs.outPcg2), load(hm.pcg2)),
        pcg3: eq(await R.read(imgs.outPcg3), load(hm.pcg3)),
        cell_hash: eq(await R.read(imgs.outCell), load(hm.cell_hash_it3_seed11)),
        u01: eq(await R.read(imgs.outU01), load(hm.u01_of_pcg)),
        ekigar_hash2_integer: eq(await R.read(imgs.outH2), load(hm.ekigar_hash2_u32)),
        ekigar_hash2_gradient_vs_float32_arithmetic: gradEq(load(hm.ekigar_hash2_gx_f32), load(hm.ekigar_hash2_gy_f32)),
        ekigar_hash2_gradient_vs_numpy_float64_worst_ulp: worstUlp };
    console.log('hashes', JSON.stringify(res.hashes_bit_exact));
}

// ---- 3. world noise against core/world_noise.field (float64)
{
    const nz = man.noise;
    const n = nz.shape[0];
    const terms = load(nz.terms);
    const out = R.field(n, n, 1);
    R.run(K.world_noise_field, { terms: R.field(1, 2 * nz.n_terms, 4, terms), disp: R.field(n, n, 2) }, { outF: out },
        { uTerms: nz.n_terms, uCell: nz.cell, uConst: nz.const });
    const got = await R.read(out);
    const want = load(nz.expected_float64_as_f32);
    let lo = Infinity, hi = -Infinity, err = 0;
    for (let i = 0; i < want.length; i++) { lo = Math.min(lo, want[i]); hi = Math.max(hi, want[i]); err = Math.max(err, Math.abs(got[i] - want[i])); }
    res.world_noise = { level: '96 cells of 7.5 m at x0 = 40 km', terms: nz.n_terms, max_abs: err, range: hi - lo,
        ratio: +(err / (hi - lo)).toExponential(3) };
    console.log('world noise', JSON.stringify(res.world_noise));
}

// ---- 4. the f32 built-ins' error in ULPs against the correctly rounded float64 result
{
    const N = 256;
    const x = new Float32Array(N * N * 4);
    let s = 7 >>> 0;
    const r = () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
    for (let i = 0; i < N * N; i++) {
        x[4 * i] = Math.fround(1e-3 * Math.pow(1e9, r()));
        x[4 * i + 1] = Math.fround(0.3 + 2.2 * r());
        x[4 * i + 2] = Math.fround(-20 + 40 * r());
        x[4 * i + 3] = Math.fround(-1.5 + 3 * r());
    }
    const oa = R.field(N, N, 4), ob = R.field(N, N, 4);
    R.run(K.math_probe, { xin: R.field(N, N, 4, x) }, { outA: oa, outB: ob }, {});
    const A = await R.read(oa), B = await R.read(ob);
    const f32 = new Float32Array(1), u32 = new Uint32Array(f32.buffer);
    const ord = (v) => { f32[0] = v; const b = u32[0]; return b & 0x80000000 ? -(b & 0x7fffffff) : b; };
    const ulp = (got, ref) => Math.abs(ord(got) - ord(Math.fround(ref)));
    const fns = {
        pow: (i) => [A[4 * i], Math.pow(x[4 * i], x[4 * i + 1])], exp: (i) => [A[4 * i + 1], Math.exp(x[4 * i + 2])],
        log: (i) => [A[4 * i + 2], Math.log(x[4 * i])], sqrt: (i) => [A[4 * i + 3], Math.sqrt(x[4 * i])],
        tan: (i) => [B[4 * i], Math.tan(x[4 * i + 3])], atan: (i) => [B[4 * i + 1], Math.atan(Math.fround(5 * x[4 * i + 3]))],
        atan2: (i) => [B[4 * i + 2], Math.atan2(x[4 * i + 2], x[4 * i + 3])], divide: (i) => [B[4 * i + 3], x[4 * i] / x[4 * i + 1]],
    };
    res.builtin_ulp = {};
    for (const [nm, fn] of Object.entries(fns)) {
        const e = [];
        for (let i = 0; i < N * N; i++) { const [g, rf] = fn(i); e.push(ulp(g, rf)); }
        e.sort((a, b) => a - b);
        res.builtin_ulp[nm] = { max: e[e.length - 1], p99: e[Math.floor(0.99 * e.length)], exact_frac: +(e.filter((v) => v === 0).length / e.length).toFixed(3) };
    }
    console.log('builtin ulp', JSON.stringify(res.builtin_ulp));
}

// ---- 5. the production fluvial step: 9 passes, timed, deterministic
async function fluvialStep(N, steps, timed) {
    const cell = 10.0;
    // the start: an fbm field, 2000 m of relief, made by the world-noise kernel (no CPU loop over cells)
    const nz = man.noise;
    const hf = R.field(N, N, 1);
    R.run(K.world_noise_field, { terms: R.field(1, 2 * nz.n_terms, 4, load(nz.terms)), disp: R.field(N, N, 2) }, { outF: hf },
        { uTerms: nz.n_terms, uCell: cell, uConst: 0.0 });
    const h0 = await R.read(hf);
    const st = new Float32Array(N * N * 4), par = new Float32Array(N * N * 4), pin = new Float32Array(N * N * 4);
    for (let i = 0; i < N * N; i++) {
        const h = 1000.0 + 1000.0 * h0[i];
        st[4 * i] = h; st[4 * i + 1] = cell * cell;
        par[4 * i] = 2e-3; par[4 * i + 1] = 1.5e-5; par[4 * i + 2] = 0.7; par[4 * i + 3] = 0.5;
        const x = i % N, y = Math.floor(i / N);
        if (x === 0 || y === 0 || x === N - 1 || y === N - 1) { pin[4 * i] = 1.0; pin[4 * i + 1] = h; }
    }
    const S = [R.field(N, N, 4, st), R.field(N, N, 4)];
    const M = [R.field(N, N, 4), R.field(N, N, 4)];
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
    await R.check(K.h_keep, [4]);                       // the one step kernel with no fixture case
    for (let i = 0; i < 5; i++) step();
    await R.idle();
    const t0 = performance.now();
    const d0 = R.dispatches;
    let issue = 0;
    for (let i = 0; i < steps; i++) {
        const a = performance.now();
        step();
        issue += performance.now() - a;
        if (i % 50 === 49) R.flush();
    }
    await R.idle();
    const wall = (performance.now() - t0) / steps;
    const out = await R.read(S[s]);
    let ts = null;
    if (timed && device.features.has('timestamp-query')) {
        // the GPU's own time of 50 steps in one pass
        R.flush();
        const qs = device.createQuerySet({ type: 'timestamp', count: 2 });
        const rs = device.createBuffer({ size: 16, usage: GPUBufferUsage.QUERY_RESOLVE | GPUBufferUsage.COPY_SRC });
        const rb = device.createBuffer({ size: 16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
        R.pass = R.enc.beginComputePass({ timestampWrites: { querySet: qs, beginningOfPassWriteIndex: 0, endOfPassWriteIndex: 1 } });
        for (let i = 0; i < 50; i++) step();
        R.pass.end();
        R.pass = null;
        R.enc.resolveQuerySet(qs, 0, 2, rs, 0);
        R.enc.copyBufferToBuffer(rs, 0, rb, 0, 16);
        R.flush();
        await rb.mapAsync(GPUMapMode.READ);
        const v = new BigUint64Array(rb.getMappedRange().slice(0));
        ts = Number(v[1] - v[0]) / 1e6 / 50;
        rb.unmap();
    }
    for (const f of [...S, ...M, Wt, Hk, Phi, P, Q, one, hf]) f.buffer.destroy();
    R.bindGroups.clear();
    return { wall_ms_per_step: +wall.toFixed(4), js_issue_ms_per_step: +(issue / steps).toFixed(4),
        dispatches_per_step: (R.dispatches - d0) / steps, gpu_timestamp_ms_per_step: ts && +ts.toFixed(4), out };
}
res.fluvial_step = {};
for (const N of [512, 1024, 2048]) {
    const r1 = await fluvialStep(N, 200, true);
    const r2 = await fluvialStep(N, 200, false);
    const same = new Uint32Array(r1.out.buffer).every((v, i) => v === new Uint32Array(r2.out.buffer)[i]);
    delete r1.out;
    res.fluvial_step[N] = { ...r1, deterministic_205_steps: same, blender_glsl_step_ms: N === 1024 ? 1.0161 : N === 2048 ? 4.4557 : null };
    console.log('fluvial step', N, JSON.stringify(res.fluvial_step[N]));
}

console.log('RESULT ' + JSON.stringify({ failed: res.failed, worst: res.kernel_cases_worst }));
if (OUT) Deno.writeTextFileSync(OUT, JSON.stringify(res, null, 1));
device.destroy();
Deno.exit(res.failed.length ? 1 : 0);
