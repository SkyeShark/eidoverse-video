// Design probe (PORT_PLAN.md section 3.1): the same stream-power probe kernel as gpu_runner_bench.mjs, written in
// TSL and run through three r184's WebGPURenderer (renderer.compute / computeAsync on StorageBufferAttributes), the
// way fluid_swe.js and cloth_sim.js run their kernels. It measures what choosing TSL for the terrain kernels would
// cost: the JS time per compute() call, the wall time per step, and whether the result equals the raw WGSL kernel's.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/design_probes/tsl_compute_bench.mjs [out.json]

const OUT = Deno.args[0] ?? null;
const T0 = performance.now();
const log = (...a) => console.log(`[${((performance.now() - T0) / 1000).toFixed(1)} s]`, ...a);
// a GPU slot is shared: never hold it past four minutes
const watchdog = setTimeout(() => { log('WATCHDOG: stopping after 240 s'); Deno.exit(3); }, 240000);

// headless shims (Ekigar's test/gpu/run_gpu_tests.mjs and render_common.mjs use the same): three's WebGPURenderer
// wants a canvas whose context it can configure, even when everything it does is compute
class FakeGPUCanvasContext {
    constructor(canvas) { this.canvas = canvas; this._texture = null; }
    configure(opts) {
        if (this._texture) this._texture.destroy();
        this._texture = opts.device.createTexture({ size: [this.canvas.width, this.canvas.height, 1],
            format: opts.format, usage: opts.usage | GPUTextureUsage.COPY_SRC });
    }
    unconfigure() { this._texture = null; }
    getCurrentTexture() { return this._texture; }
}
const canvas = { width: 16, height: 16, style: {}, addEventListener() {}, removeEventListener() {},
    getContext(t) { return t === 'webgpu' ? this._ctx : null; } };
canvas._ctx = new FakeGPUCanvasContext(canvas);
globalThis.window ??= globalThis;
globalThis.self ??= globalThis;
globalThis.document ??= { createElement: (tag) => (String(tag).toLowerCase() === 'canvas' ? canvas : { style: {} }),
    createElementNS: () => ({ style: {} }), addEventListener() {}, removeEventListener() {} };
globalThis.GPUCanvasContext ??= FakeGPUCanvasContext;
globalThis.requestAnimationFrame ??= (cb) => setTimeout(() => cb(performance.now()), 16);
globalThis.cancelAnimationFrame ??= (id) => clearTimeout(id);

const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
const requiredLimits = {};
for (const k of ['maxStorageBufferBindingSize', 'maxBufferSize']) requiredLimits[k] = adapter.limits[k];
const device = await adapter.requestDevice({ requiredLimits });
// render_common.mjs's shim: three keys its full mode on this feature, which deno 2.8's wgpu does not advertise
if (!device.features.has('core-features-and-limits')) {
    const orig = device.features;
    Object.defineProperty(device, 'features', { value: {
        has: (f) => f === 'core-features-and-limits' || orig.has(f),
        [Symbol.iterator]: function* () { yield 'core-features-and-limits'; yield* orig; },
        get size() { return orig.size + 1; },
        forEach(cb, t) { for (const f of this) cb.call(t, f, f, this); } }, configurable: true });
}

const THREE = await import('npm:three@0.184.0/webgpu');
const { Fn, instanceIndex, storage, uniform, float, int, vec2, vec4, max, sqrt, If, Return } =
    await import('npm:three@0.184.0/tsl');

log('three', THREE.REVISION, 'imported');
const renderer = new THREE.WebGPURenderer({ canvas, adapter, device, antialias: false });
await renderer.init();
log('renderer initialised');

function initField(N) {
    const a = new Float32Array(N * N * 4);
    let s = 1 >>> 0;
    for (let i = 0; i < N * N; i++) {
        s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
        a[4 * i] = (s / 4294967296) * 100.0;
        a[4 * i + 1] = 1.0;
        a[4 * i + 2] = 0.125;
    }
    return a;
}

const res = { adapter: adapter.info?.description, three: THREE.REVISION };
const uDt = uniform(100.0), uK = uniform(1e-5), uU = uniform(1e-3), uDx = uniform(10.0), uCell = uniform(100.0);

function kernelFor(srcNode, dstNode, N) {
    return Fn(() => {
        const i = int(instanceIndex);
        If(i.greaterThanEqual(int(N * N)), () => { Return(); });
        const px = i.mod(int(N)), py = i.div(int(N));
        const c = srcNode.element(i);
        const h = c.x;
        const best = float(0).toVar();
        const acc = uCell.toVar();
        const wsum = float(0).toVar();
        for (let dy = -1; dy <= 1; dy++) {
            for (let dx = -1; dx <= 1; dx++) {
                if (dx === 0 && dy === 0) continue;
                const qx = px.add(int(dx + N)).mod(int(N));
                const qy = py.add(int(dy + N)).mod(int(N));
                const v = srcNode.element(qy.mul(int(N)).add(qx));
                const d = uDx.mul(Math.hypot(dx, dy));
                best.assign(max(best, h.sub(v.x).div(d)));
                acc.addAssign(max(v.x.sub(h).div(d), 0.0).mul(v.y).mul(v.z));
                wsum.addAssign(max(h.sub(v.x).div(d), 0.0));
            }
        }
        const hn = h.sub(uDt.mul(uK).mul(sqrt(acc)).mul(best)).add(uDt.mul(uU));
        dstNode.element(i).assign(vec4(hn, acc, float(1.0).div(max(wsum, 1e-6)), 1.0));
    })().compute(N * N, [256]);
}

res.tsl = {};
for (const N of [512, 1024, 2048]) {
    const init = initField(N);
    const A = new THREE.StorageBufferAttribute(init.slice(), 4);
    const B = new THREE.StorageBufferAttribute(init.slice(), 4);
    const sA = storage(A, 'vec4', N * N), sB = storage(B, 'vec4', N * N);
    const kAB = kernelFor(sA.toReadOnly(), sB, N);
    const kBA = kernelFor(sB.toReadOnly(), sA, N);
    log(N, 'kernels built; first compute');
    const tc = performance.now();
    renderer.compute(kAB);                             // first call builds the pipeline
    renderer.compute(kBA);
    await device.queue.onSubmittedWorkDone();
    const firstMs = performance.now() - tc;
    log(N, 'first two calls', firstMs.toFixed(1), 'ms');
    const S = 400;
    // renderer.compute (sync) S times, then wait for the queue
    let t = performance.now();
    for (let s = 0; s < S; s++) renderer.compute(s & 1 ? kBA : kAB);
    const issue = (performance.now() - t) / S;
    await device.queue.onSubmittedWorkDone();
    const wall = (performance.now() - t) / S;
    log(N, 'compute x', S, 'done');
    // computeAsync, as fluid_swe.js calls it
    t = performance.now();
    for (let s = 0; s < 50; s++) await renderer.computeAsync(s & 1 ? kBA : kAB);
    await device.queue.onSubmittedWorkDone();
    const wallAsync = (performance.now() - t) / 50;
    log(N, 'computeAsync x 50 done');
    // readback through three
    t = performance.now();
    const ab = await renderer.getArrayBufferAsync(A);
    const readMs = performance.now() - t;
    log(N, 'readback done');
    const a = new Float32Array(ab);
    res.tsl[N] = { first_two_calls_ms: +firstMs.toFixed(1), js_ms_per_compute_call: +issue.toFixed(4),
        wall_ms_per_step_compute: +wall.toFixed(4), wall_ms_per_step_computeAsync: +wallAsync.toFixed(4),
        readback_rgba32f_ms: +readMs.toFixed(1), finite: a.every(Number.isFinite) };
    console.log('tsl', N, JSON.stringify(res.tsl[N]));
}

// the TSL result against the raw WGSL kernel's after ONE step and after 200 steps at 512^2 (same start). One step
// says whether the two compute the same thing; 200 steps on a white-noise start show how fast a one-instruction
// difference (TSL folds sqrt(2) into a literal, the WGSL calls length()) grows in this rough a field.
async function compareSteps(steps) {
    const N = 512;
    const init = initField(N);
    const A = new THREE.StorageBufferAttribute(init.slice(), 4);
    const B = new THREE.StorageBufferAttribute(init.slice(), 4);
    const sA = storage(A, 'vec4', N * N), sB = storage(B, 'vec4', N * N);
    const kAB = kernelFor(sA.toReadOnly(), sB, N);
    const kBA = kernelFor(sB.toReadOnly(), sA, N);
    for (let s = 0; s < steps; s++) renderer.compute(s & 1 ? kBA : kAB);
    const tslOut = new Float32Array(await renderer.getArrayBufferAsync(steps & 1 ? B : A));
    // the WGSL kernel of gpu_runner_bench.mjs, one buffer pair, plain bind groups
    const code = Deno.readTextFileSync(new URL('./gpu_runner_bench.mjs', import.meta.url)).split('const STEP_BUF = /* wgsl */ `')[1].split('`;')[0];
    const bgl = device.createBindGroupLayout({ entries: [
        { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'uniform' } },
        { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } },
        { binding: 2, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } }] });
    const pipe = device.createComputePipeline({ layout: device.createPipelineLayout({ bindGroupLayouts: [bgl] }),
        compute: { module: device.createShaderModule({ code }), entryPoint: 'main' } });
    const ub = device.createBuffer({ size: 32, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    const u = new ArrayBuffer(32);
    new Float32Array(u).set([100.0, 1e-5, 1e-3, 10.0, 100.0]);
    new Int32Array(u).set([N, N, 0], 5);
    device.queue.writeBuffer(ub, 0, u);
    const mk = () => device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    const X = mk(), Y = mk();
    device.queue.writeBuffer(X, 0, init);
    const bg = [[X, Y], [Y, X]].map(([s, d]) => device.createBindGroup({ layout: bgl, entries: [
        { binding: 0, resource: { buffer: ub } }, { binding: 1, resource: { buffer: s } }, { binding: 2, resource: { buffer: d } }] }));
    const enc = device.createCommandEncoder();
    const pass = enc.beginComputePass();
    pass.setPipeline(pipe);
    for (let s = 0; s < steps; s++) { pass.setBindGroup(0, bg[s & 1]); pass.dispatchWorkgroups(N / 16, N / 16, 1); }
    pass.end();
    const rb = device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    enc.copyBufferToBuffer(steps & 1 ? Y : X, 0, rb, 0, N * N * 16);
    device.queue.submit([enc.finish()]);
    await rb.mapAsync(GPUMapMode.READ);
    const wg = new Float32Array(rb.getMappedRange().slice(0));
    let identical = 0, lo = Infinity, hi = -Infinity, worst = 0;
    for (let i = 0; i < wg.length; i += 4) {             // the height channel
        if (Object.is(wg[i], tslOut[i])) identical++;
        lo = Math.min(lo, wg[i]); hi = Math.max(hi, wg[i]);
        worst = Math.max(worst, Math.abs(wg[i] - tslOut[i]));
    }
    const r = { identical_fraction_h: +(identical / (wg.length / 4)).toFixed(6), worst_abs_h: worst,
        worst_over_range_h: +(worst / (hi - lo)).toExponential(3) };
    log('tsl vs wgsl after', steps, 'steps', JSON.stringify(r));
    return r;
}
res.tsl_vs_wgsl_512 = { one_step: await compareSteps(1), steps_200: await compareSteps(200) };

console.log('RESULT ' + JSON.stringify(res));
if (OUT) Deno.writeTextFileSync(OUT, JSON.stringify(res, null, 1));
clearTimeout(watchdog);
Deno.exit(0);
