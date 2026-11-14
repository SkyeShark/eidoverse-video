// Design probe (PORT_PLAN.md section 3.1): in a FRESH process, the TSL probe kernel of tsl_compute_bench.mjs against
// the raw WGSL kernel of gpu_runner_bench.mjs after one step, both against a float64 reference, at 64^2 and 512^2;
// and whether a first renderer.compute() / computeAsync() call runs. (tsl_compute_bench.mjs saw a stale read after
// one step inside a long session; this checks the kernels themselves.)
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/design_probes/tsl_vs_wgsl_fresh.mjs [out.json]

const OUT = Deno.args[0] ?? null;
const watchdog = setTimeout(() => { console.log('WATCHDOG'); Deno.exit(3); }, 120000);
class FakeCtx {
    constructor(c) { this.canvas = c; this.t = null; }
    configure(o) { this.t = o.device.createTexture({ size: [16, 16, 1], format: o.format, usage: o.usage | GPUTextureUsage.COPY_SRC }); }
    unconfigure() {}
    getCurrentTexture() { return this.t; }
}
const canvas = { width: 16, height: 16, style: {}, addEventListener() {}, removeEventListener() {},
    getContext(t) { return t === 'webgpu' ? this._ctx : null; } };
canvas._ctx = new FakeCtx(canvas);
globalThis.window ??= globalThis;
globalThis.self ??= globalThis;
globalThis.document ??= { createElement: (t) => (String(t).toLowerCase() === 'canvas' ? canvas : { style: {} }),
    createElementNS: () => ({ style: {} }), addEventListener() {}, removeEventListener() {} };
globalThis.GPUCanvasContext ??= FakeCtx;
globalThis.requestAnimationFrame ??= (cb) => setTimeout(() => cb(performance.now()), 16);
const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
const device = await adapter.requestDevice({});
const orig = device.features;
Object.defineProperty(device, 'features', { value: { has: (f) => f === 'core-features-and-limits' || orig.has(f),
    [Symbol.iterator]: function* () { yield 'core-features-and-limits'; yield* orig; }, get size() { return orig.size + 1; },
    forEach(cb, t) { for (const f of this) cb.call(t, f, f, this); } }, configurable: true });
const THREE = await import('npm:three@0.184.0/webgpu');
const { Fn, instanceIndex, storage, uniform, float, int, vec4, max, sqrt, If, Return } = await import('npm:three@0.184.0/tsl');
const renderer = new THREE.WebGPURenderer({ canvas, adapter, device, antialias: false });
await renderer.init();
const WGSL = Deno.readTextFileSync(new URL('./gpu_runner_bench.mjs', import.meta.url)).split('const STEP_BUF = /* wgsl */ `')[1].split('`;')[0];
const uDt = uniform(100.0), uK = uniform(1e-5), uU = uniform(1e-3), uDx = uniform(10.0), uCell = uniform(100.0);
const res = { adapter: adapter.info?.description, one_step: {}, first_call: {} };

function initField(N) {
    const a = new Float32Array(N * N * 4);
    let s = 1 >>> 0;
    for (let i = 0; i < N * N; i++) { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; a[4 * i] = (s / 4294967296) * 100; a[4 * i + 1] = 1; a[4 * i + 2] = 0.125; }
    return a;
}

for (const N of [64, 512]) {
    const init = initField(N);
    const A = new THREE.StorageBufferAttribute(init.slice(), 4), B = new THREE.StorageBufferAttribute(new Float32Array(N * N * 4), 4);
    const src = storage(A, 'vec4', N * N).toReadOnly(), dst = storage(B, 'vec4', N * N);
    const k = Fn(() => {
        const i = int(instanceIndex);
        If(i.greaterThanEqual(int(N * N)), () => { Return(); });
        const px = i.mod(int(N)), py = i.div(int(N));
        const h = src.element(i).x;
        const best = float(0).toVar(), acc = uCell.toVar(), wsum = float(0).toVar();
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
            if (dx === 0 && dy === 0) continue;
            const qx = px.add(int(dx + N)).mod(int(N)), qy = py.add(int(dy + N)).mod(int(N));
            const v = src.element(qy.mul(int(N)).add(qx));
            const d = uDx.mul(Math.hypot(dx, dy));
            best.assign(max(best, h.sub(v.x).div(d)));
            acc.addAssign(max(v.x.sub(h).div(d), 0.0).mul(v.y).mul(v.z));
            wsum.addAssign(max(h.sub(v.x).div(d), 0.0));
        }
        dst.element(i).assign(vec4(h.sub(uDt.mul(uK).mul(sqrt(acc)).mul(best)).add(uDt.mul(uU)), acc, float(1.0).div(max(wsum, 1e-6)), 1.0));
    })().compute(N * N, [256]);
    renderer.compute(k);
    const tsl = new Float32Array(await renderer.getArrayBufferAsync(B));
    // the raw WGSL kernel, one dispatch
    const bgl = device.createBindGroupLayout({ entries: [
        { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'uniform' } },
        { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } },
        { binding: 2, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } }] });
    const pipe = device.createComputePipeline({ layout: device.createPipelineLayout({ bindGroupLayouts: [bgl] }),
        compute: { module: device.createShaderModule({ code: WGSL }), entryPoint: 'main' } });
    const ub = device.createBuffer({ size: 32, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    const u = new ArrayBuffer(32);
    new Float32Array(u).set([100.0, 1e-5, 1e-3, 10.0, 100.0]);
    new Int32Array(u).set([N, N, 0], 5);
    device.queue.writeBuffer(ub, 0, u);
    const mk = () => device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    const X = mk(), Y = mk();
    device.queue.writeBuffer(X, 0, init);
    const bg = device.createBindGroup({ layout: bgl, entries: [{ binding: 0, resource: { buffer: ub } },
        { binding: 1, resource: { buffer: X } }, { binding: 2, resource: { buffer: Y } }] });
    const enc = device.createCommandEncoder();
    const pass = enc.beginComputePass();
    pass.setPipeline(pipe); pass.setBindGroup(0, bg); pass.dispatchWorkgroups(Math.ceil(N / 16), Math.ceil(N / 16), 1); pass.end();
    const rb = device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    enc.copyBufferToBuffer(Y, 0, rb, 0, N * N * 16);
    device.queue.submit([enc.finish()]);
    await rb.mapAsync(GPUMapMode.READ);
    const wg = new Float32Array(rb.getMappedRange().slice(0));
    // the float64 reference
    let wt = 0, ww = 0, dmax = 0;
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
        const i = y * N + x, h = init[4 * i];
        let best = 0, acc = 100;
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
            if (!dx && !dy) continue;
            const q = ((y + dy + N) % N) * N + ((x + dx + N) % N), vx = init[4 * q], d = Math.hypot(dx, dy) * 10;
            best = Math.max(best, (h - vx) / d); acc += Math.max((vx - h) / d, 0) * init[4 * q + 1] * init[4 * q + 2];
        }
        const ref = h - 100 * 1e-5 * Math.sqrt(acc) * best + 0.1;
        wt = Math.max(wt, Math.abs(tsl[4 * i] - ref) / Math.abs(ref));
        ww = Math.max(ww, Math.abs(wg[4 * i] - ref) / Math.abs(ref));
        dmax = Math.max(dmax, Math.abs(tsl[4 * i] - wg[4 * i]));
    }
    res.one_step[N] = { tsl_vs_float64_worst_rel_h: +wt.toExponential(2), wgsl_vs_float64_worst_rel_h: +ww.toExponential(2),
        tsl_vs_wgsl_worst_abs_h: dmax };
    console.log('one step', N, JSON.stringify(res.one_step[N]));
}

// a first call runs: compute() and computeAsync() on fresh kernels, read back at once
{
    const N = 512;
    const init = new Float32Array(N * N * 4).fill(1.0);
    const uAdd = uniform(0.5);
    for (const [label, useAsync] of [['compute', false], ['computeAsync', true]]) {
        const A = new THREE.StorageBufferAttribute(init.slice(), 4), B = new THREE.StorageBufferAttribute(init.slice(), 4);
        const a = storage(A, 'vec4', N * N).toReadOnly(), b = storage(B, 'vec4', N * N);
        const k = Fn(() => { const i = int(instanceIndex); b.element(i).assign(vec4(a.element(i).x.add(uAdd), 0, 0, 1)); })().compute(N * N, [256]);
        if (useAsync) await renderer.computeAsync(k); else renderer.compute(k);
        const out = new Float32Array(await renderer.getArrayBufferAsync(B));
        res.first_call[label] = out[0] === 1.5 ? 'ran' : `stale (${out[0]})`;
    }
    console.log('first call', JSON.stringify(res.first_call));
}
console.log('RESULT ' + JSON.stringify(res));
if (OUT) Deno.writeTextFileSync(OUT, JSON.stringify(res, null, 1));
clearTimeout(watchdog);
Deno.exit(0);
