// Design probe (PORT_PLAN.md sections 1.2 and 3): raw WGSL compute on Deno's WebGPU device, run the way the port's
// runner (core/gpu.js) is designed to run kernels:
//   - fields in storage buffers (array<vec4<f32>> for an RGBA pack, array<f32> for one field), ping-ponged by
//     swapping bind groups;
//   - every dispatch's uniforms in its own 256-byte slot of one uniform ring, selected by a dynamic offset, the
//     whole ring uploaded once before the batch's submit (queue.writeBuffer is ordered before the submit);
//   - many dispatches per compute pass and per command buffer;
//   - readback through copyBufferToBuffer into a MAP_READ buffer.
// The kernel is the Blender design's probe (blender/tests/terrain/design_probes/gpu_bench.py): one stream-power
// gather step, 8 neighbour reads, slopes, an MFD area gather, incision and uplift, periodic edges. Timing as there:
// the same final readback after S and after 2S steps, so (T(2S) - T(S)) / S is the GPU time of one step free of
// the readback; plus the GPU's own timestamps (timestamp-query) over a pass of S steps when the device has them.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all \
//         eidoverse/terrain/tests/design_probes/gpu_runner_bench.mjs [out.json]

const OUT = Deno.args[0] ?? null;
const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
const feats = ['timestamp-query'].filter((f) => adapter.features.has(f));
const requiredLimits = {};
for (const k of ['maxStorageBufferBindingSize', 'maxBufferSize']) requiredLimits[k] = adapter.limits[k];
const device = await adapter.requestDevice({ requiredFeatures: feats, requiredLimits });
const HAS_TS = device.features.has('timestamp-query');
const res = { adapter: adapter.info?.description, deno: Deno.version.deno, timestamp_query: HAS_TS };

const SLOT = 256;                                   // minUniformBufferOffsetAlignment
const RING_SLOTS = 65536 / SLOT * 64;               // 4 MB ring: 16384 dispatches per submit

const STEP_BUF = /* wgsl */ `
struct U { dt: f32, k: f32, u: f32, dx: f32, cell: f32, nx: i32, ny: i32, pad: i32 }
@group(0) @binding(0) var<uniform> u: U;
@group(0) @binding(1) var<storage, read> src: array<vec4<f32>>;
@group(0) @binding(2) var<storage, read_write> dst: array<vec4<f32>>;
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let p = vec2<i32>(gid.xy);
  let n = vec2<i32>(u.nx, u.ny);
  if (p.x >= n.x || p.y >= n.y) { return; }
  let c = src[p.y * n.x + p.x];
  let h = c.x;
  var best = 0.0;
  var acc = u.cell;
  var wsum = 0.0;
  for (var dy = -1; dy <= 1; dy++) {
    for (var dx = -1; dx <= 1; dx++) {
      if (dx == 0 && dy == 0) { continue; }
      let q = (p + vec2<i32>(dx, dy) + n) % n;
      let v = src[q.y * n.x + q.x];
      let d = length(vec2<f32>(f32(dx), f32(dy))) * u.dx;
      best = max(best, (h - v.x) / d);
      acc += max((v.x - h) / d, 0.0) * v.y * v.z;
      wsum += max((h - v.x) / d, 0.0);
    }
  }
  let hn = h - u.dt * u.k * sqrt(acc) * best + u.dt * u.u;
  dst[p.y * n.x + p.x] = vec4<f32>(hn, acc, 1.0 / max(wsum, 1e-6), 1.0);
}`;

// the same kernel reading a sampled rgba32float texture (textureLoad) and writing a storage texture
const STEP_TEX = /* wgsl */ `
struct U { dt: f32, k: f32, u: f32, dx: f32, cell: f32, nx: i32, ny: i32, pad: i32 }
@group(0) @binding(0) var<uniform> u: U;
@group(0) @binding(1) var src: texture_2d<f32>;
@group(0) @binding(2) var dst: texture_storage_2d<rgba32float, write>;
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let p = vec2<i32>(gid.xy);
  let n = vec2<i32>(u.nx, u.ny);
  if (p.x >= n.x || p.y >= n.y) { return; }
  let c = textureLoad(src, p, 0);
  let h = c.x;
  var best = 0.0;
  var acc = u.cell;
  var wsum = 0.0;
  for (var dy = -1; dy <= 1; dy++) {
    for (var dx = -1; dx <= 1; dx++) {
      if (dx == 0 && dy == 0) { continue; }
      let q = (p + vec2<i32>(dx, dy) + n) % n;
      let v = textureLoad(src, q, 0);
      let d = length(vec2<f32>(f32(dx), f32(dy))) * u.dx;
      best = max(best, (h - v.x) / d);
      acc += max((v.x - h) / d, 0.0) * v.y * v.z;
      wsum += max((h - v.x) / d, 0.0);
    }
  }
  let hn = h - u.dt * u.k * sqrt(acc) * best + u.dt * u.u;
  textureStore(dst, p, vec4<f32>(hn, acc, 1.0 / max(wsum, 1e-6), 1.0));
}`;

const ring = device.createBuffer({ size: RING_SLOTS * SLOT, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
const staging = new ArrayBuffer(RING_SLOTS * SLOT);
const stF = new Float32Array(staging);
const stI = new Int32Array(staging);

function uniformLayoutEntry() {
    return { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'uniform', hasDynamicOffset: true,
        minBindingSize: 32 } };
}

function pipelineFor(code, entries) {
    const bgl = device.createBindGroupLayout({ entries: [uniformLayoutEntry(), ...entries] });
    const module = device.createShaderModule({ code });
    const pipeline = device.createComputePipeline({ layout: device.createPipelineLayout({ bindGroupLayouts: [bgl] }),
        compute: { module, entryPoint: 'main' } });
    return { bgl, pipeline };
}

const PB = pipelineFor(STEP_BUF, [
    { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } },
    { binding: 2, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } }]);
const PT = pipelineFor(STEP_TEX, [
    { binding: 1, visibility: GPUShaderStage.COMPUTE, texture: { sampleType: 'unfilterable-float' } },
    { binding: 2, visibility: GPUShaderStage.COMPUTE, storageTexture: { access: 'write-only', format: 'rgba32float' } }]);

function initField(N) {
    // the design probe's start: h uniform random 0..100 m, A = 1, wsum^-1 = 0.125 (a fixed-seed LCG: reproducible)
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

async function readBuffer(buf, bytes) {
    const rb = device.createBuffer({ size: bytes, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    const enc = device.createCommandEncoder();
    enc.copyBufferToBuffer(buf, 0, rb, 0, bytes);
    device.queue.submit([enc.finish()]);
    await rb.mapAsync(GPUMapMode.READ);
    const out = new Float32Array(rb.getMappedRange().slice(0));
    rb.unmap();
    rb.destroy();
    return out;
}

async function readTexture(tex, N) {
    const bytes = N * N * 16;
    const rb = device.createBuffer({ size: bytes, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    const enc = device.createCommandEncoder();
    enc.copyTextureToBuffer({ texture: tex }, { buffer: rb, bytesPerRow: N * 16, rowsPerImage: N }, [N, N, 1]);
    device.queue.submit([enc.finish()]);
    await rb.mapAsync(GPUMapMode.READ);
    const out = new Float32Array(rb.getMappedRange().slice(0));
    rb.unmap();
    rb.destroy();
    return out;
}

function makeTimestamp() {
    if (!HAS_TS) return null;
    const qs = device.createQuerySet({ type: 'timestamp', count: 2 });
    const rs = device.createBuffer({ size: 16, usage: GPUBufferUsage.QUERY_RESOLVE | GPUBufferUsage.COPY_SRC });
    const rb = device.createBuffer({ size: 16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    return { qs, rs, rb };
}

// Encode `steps` dispatches into ONE compute pass of ONE command buffer: every dispatch has its own uniform slot.
function encodeSteps(P, groupsXY, bgs, steps, uni, ts) {
    let issue = 0;
    const t0 = performance.now();
    for (let i = 0; i < steps; i++) {
        const o = (i * SLOT) / 4;
        stF[o] = uni.dt; stF[o + 1] = uni.k; stF[o + 2] = uni.u; stF[o + 3] = uni.dx; stF[o + 4] = uni.cell;
        stI[o + 5] = uni.n; stI[o + 6] = uni.n; stI[o + 7] = 0;
    }
    device.queue.writeBuffer(ring, 0, staging, 0, steps * SLOT);
    const enc = device.createCommandEncoder();
    const pass = enc.beginComputePass(ts ? { timestampWrites: { querySet: ts.qs, beginningOfPassWriteIndex: 0,
        endOfPassWriteIndex: 1 } } : undefined);
    pass.setPipeline(P.pipeline);
    for (let i = 0; i < steps; i++) {
        pass.setBindGroup(0, bgs[i & 1], [i * SLOT]);
        pass.dispatchWorkgroups(groupsXY, groupsXY, 1);
    }
    pass.end();
    if (ts) {
        enc.resolveQuerySet(ts.qs, 0, 2, ts.rs, 0);
        enc.copyBufferToBuffer(ts.rs, 0, ts.rb, 0, 16);
    }
    device.queue.submit([enc.finish()]);
    issue = performance.now() - t0;
    return issue;
}

async function gpuPassMs(ts) {
    await ts.rb.mapAsync(GPUMapMode.READ);
    const v = new BigUint64Array(ts.rb.getMappedRange().slice(0));
    ts.rb.unmap();
    return Number(v[1] - v[0]) / 1e6;
}

const uni0 = { dt: 100.0, k: 1e-5, u: 1e-3, dx: 10.0, cell: 100.0 };
res.buffers = {};
res.textures = {};
for (const N of [512, 1024, 2048, 4096]) {
    const uni = { ...uni0, n: N };
    const g = Math.ceil(N / 16);
    const init = initField(N);
    // --- storage buffers
    const A = device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    const B = device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    let t = performance.now();
    device.queue.writeBuffer(A, 0, init);
    device.queue.writeBuffer(B, 0, init);
    await device.queue.onSubmittedWorkDone();
    const uploadMs = (performance.now() - t) / 2;
    const bgs = [
        device.createBindGroup({ layout: PB.bgl, entries: [{ binding: 0, resource: { buffer: ring, size: 32 } },
            { binding: 1, resource: { buffer: A } }, { binding: 2, resource: { buffer: B } }] }),
        device.createBindGroup({ layout: PB.bgl, entries: [{ binding: 0, resource: { buffer: ring, size: 32 } },
            { binding: 1, resource: { buffer: B } }, { binding: 2, resource: { buffer: A } }] }),
    ];
    encodeSteps(PB, g, bgs, 20, uni, null);                       // warm-up (pipeline, first dispatches)
    await readBuffer(A, 16);
    const S = N <= 1024 ? 1000 : (N === 2048 ? 400 : 100);
    const T = {};
    const issue = {};
    for (const s of [S, 2 * S]) {
        t = performance.now();
        issue[s] = encodeSteps(PB, g, bgs, s, uni, null);
        const r = await readBuffer(A, N * N * 16);
        T[s] = performance.now() - t;
        if (!r.every(Number.isFinite)) throw new Error('non-finite');
    }
    t = performance.now();
    const r1 = await readBuffer(A, N * N * 16);
    const readMs4 = performance.now() - t;
    t = performance.now();
    await readBuffer(A, N * N * 4);
    const readMs1 = performance.now() - t;
    let tsMs = null;
    const ts = makeTimestamp();
    if (ts) {
        encodeSteps(PB, g, bgs, S, uni, ts);
        tsMs = (await gpuPassMs(ts)) / S;
    }
    // determinism: the same S steps again from the same start, bit for bit
    device.queue.writeBuffer(A, 0, init);
    device.queue.writeBuffer(B, 0, init);
    encodeSteps(PB, g, bgs, 200, uni, null);
    const d1 = await readBuffer(A, N * N * 16);
    device.queue.writeBuffer(A, 0, init);
    device.queue.writeBuffer(B, 0, init);
    encodeSteps(PB, g, bgs, 200, uni, null);
    const d2 = await readBuffer(A, N * N * 16);
    const same = new Uint32Array(d1.buffer).every((v, i) => v === new Uint32Array(d2.buffer)[i]);
    res.buffers[N] = { ms_per_step: +((T[2 * S] - T[S]) / S).toFixed(4),
        js_issue_ms_per_dispatch: +(issue[S] / S).toFixed(4), gpu_timestamp_ms_per_step: tsMs && +tsMs.toFixed(4),
        readback_rgba32f_ms: +readMs4.toFixed(1), readback_r32f_ms: +readMs1.toFixed(1),
        upload_rgba32f_ms: +uploadMs.toFixed(1), deterministic_200_steps: same, finite: r1.every(Number.isFinite) };
    console.log('buffers', N, JSON.stringify(res.buffers[N]));
    A.destroy(); B.destroy();

    // --- textures (sampled rgba32float read, storage rgba32float write)
    if (N <= 2048) {
        const usage = GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.STORAGE_BINDING | GPUTextureUsage.COPY_SRC |
            GPUTextureUsage.COPY_DST;
        const TA = device.createTexture({ size: [N, N], format: 'rgba32float', usage });
        const TB = device.createTexture({ size: [N, N], format: 'rgba32float', usage });
        device.queue.writeTexture({ texture: TA }, init, { bytesPerRow: N * 16 }, [N, N]);
        device.queue.writeTexture({ texture: TB }, init, { bytesPerRow: N * 16 }, [N, N]);
        const tbg = [
            device.createBindGroup({ layout: PT.bgl, entries: [{ binding: 0, resource: { buffer: ring, size: 32 } },
                { binding: 1, resource: TA.createView() }, { binding: 2, resource: TB.createView() }] }),
            device.createBindGroup({ layout: PT.bgl, entries: [{ binding: 0, resource: { buffer: ring, size: 32 } },
                { binding: 1, resource: TB.createView() }, { binding: 2, resource: TA.createView() }] }),
        ];
        encodeSteps(PT, g, tbg, 20, uni, null);
        await readTexture(TA, N);
        const TT = {};
        for (const s of [S, 2 * S]) {
            t = performance.now();
            encodeSteps(PT, g, tbg, s, uni, null);
            await readTexture(TA, N);
            TT[s] = performance.now() - t;
        }
        let tts = null;
        const ts2 = makeTimestamp();
        if (ts2) {
            encodeSteps(PT, g, tbg, S, uni, ts2);
            tts = (await gpuPassMs(ts2)) / S;
        }
        // the two layouts compute the same numbers
        device.queue.writeTexture({ texture: TA }, init, { bytesPerRow: N * 16 }, [N, N]);
        device.queue.writeTexture({ texture: TB }, init, { bytesPerRow: N * 16 }, [N, N]);
        encodeSteps(PT, g, tbg, 200, uni, null);
        const dt = await readTexture(TA, N);
        const sameAsBuffers = new Uint32Array(dt.buffer).every((v, i) => v === new Uint32Array(d1.buffer)[i]);
        res.textures[N] = { ms_per_step: +((TT[2 * S] - TT[S]) / S).toFixed(4),
            gpu_timestamp_ms_per_step: tts && +tts.toFixed(4), bit_identical_to_buffers_200_steps: sameAsBuffers };
        console.log('textures', N, JSON.stringify(res.textures[N]));
        TA.destroy(); TB.destroy();
    }
}

// Wall time per step with no readback in the loop: encode + submit S steps, then wait for the queue
// (onSubmittedWorkDone). This is what a solver loop costs between its rare readbacks.
res.wall = {};
for (const N of [512, 1024, 2048]) {
    const uni = { ...uni0, n: N };
    const g = Math.ceil(N / 16);
    const A = device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    const B = device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    device.queue.writeBuffer(A, 0, initField(N));
    const bgs = [
        device.createBindGroup({ layout: PB.bgl, entries: [{ binding: 0, resource: { buffer: ring, size: 32 } },
            { binding: 1, resource: { buffer: A } }, { binding: 2, resource: { buffer: B } }] }),
        device.createBindGroup({ layout: PB.bgl, entries: [{ binding: 0, resource: { buffer: ring, size: 32 } },
            { binding: 1, resource: { buffer: B } }, { binding: 2, resource: { buffer: A } }] }),
    ];
    encodeSteps(PB, g, bgs, 50, uni, null);
    await device.queue.onSubmittedWorkDone();
    const S = 2000;
    const t = performance.now();
    let issue = 0;
    for (let k = 0; k < S / 500; k++) issue += encodeSteps(PB, g, bgs, 500, uni, null);   // 4 submits of 500
    await device.queue.onSubmittedWorkDone();
    res.wall[N] = { wall_ms_per_step: +((performance.now() - t) / S).toFixed(4), js_issue_ms_per_dispatch: +(issue / S).toFixed(4) };
    console.log('wall', N, JSON.stringify(res.wall[N]));
    A.destroy(); B.destroy();
}

// Readback: the fixed latency of one small read (16 bytes, a reused MAP_READ buffer, 20 times) and the time of
// whole fields (a reused MAP_READ buffer, copied into a preallocated Float32Array, median of 5)
{
    const big = device.createBuffer({ size: 2048 * 2048 * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    device.queue.writeBuffer(big, 0, initField(1024));
    const rb = device.createBuffer({ size: 2048 * 2048 * 16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    const dstArr = new Float32Array(2048 * 2048 * 4);
    async function timed(bytes) {
        const t = performance.now();
        const enc = device.createCommandEncoder();
        enc.copyBufferToBuffer(big, 0, rb, 0, bytes);
        device.queue.submit([enc.finish()]);
        await rb.mapAsync(GPUMapMode.READ, 0, bytes);
        dstArr.set(new Float32Array(rb.getMappedRange(0, bytes)), 0);
        rb.unmap();
        return performance.now() - t;
    }
    const med = (a) => a.sort((x, y) => x - y)[Math.floor(a.length / 2)];
    const small = [];
    for (let i = 0; i < 20; i++) small.push(await timed(16));
    res.readback = { small_16B_ms_median: +med(small).toFixed(2), small_16B_ms_min: +Math.min(...small).toFixed(2) };
    for (const [name, bytes] of [['1024_r32f', 1024 * 1024 * 4], ['1024_rgba32f', 1024 * 1024 * 16],
        ['2048_r32f', 2048 * 2048 * 4], ['2048_rgba32f', 2048 * 2048 * 16]]) {
        const a = [];
        for (let i = 0; i < 5; i++) a.push(await timed(bytes));
        res.readback[name + '_ms_median'] = +med(a).toFixed(1);
    }
    // the queue's own round trip with nothing to map
    const w = [];
    for (let i = 0; i < 20; i++) {
        const t = performance.now();
        device.queue.submit([device.createCommandEncoder().finish()]);
        await device.queue.onSubmittedWorkDone();
        w.push(performance.now() - t);
    }
    res.readback.empty_submit_roundtrip_ms_median = +med(w).toFixed(2);
    console.log('readback', JSON.stringify(res.readback));
    big.destroy(); rb.destroy();
}

// The cost of issuing a dispatch on its own submit (the pattern a naive port would use), at 1024^2
{
    const N = 1024, g = 64, uni = { ...uni0, n: N };
    const A = device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    const B = device.createBuffer({ size: N * N * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
    device.queue.writeBuffer(A, 0, initField(N));
    const bgs = [
        device.createBindGroup({ layout: PB.bgl, entries: [{ binding: 0, resource: { buffer: ring, size: 32 } },
            { binding: 1, resource: { buffer: A } }, { binding: 2, resource: { buffer: B } }] }),
        device.createBindGroup({ layout: PB.bgl, entries: [{ binding: 0, resource: { buffer: ring, size: 32 } },
            { binding: 1, resource: { buffer: B } }, { binding: 2, resource: { buffer: A } }] }),
    ];
    const S = 500;
    const t = performance.now();
    for (let i = 0; i < S; i++) encodeSteps(PB, g, bgs, 1, uni, null);
    await readBuffer(A, 16);
    res.one_submit_per_dispatch_1024 = { ms_per_dispatch_wall: +((performance.now() - t) / S).toFixed(4) };
    console.log('one submit per dispatch', JSON.stringify(res.one_submit_per_dispatch_1024));
    A.destroy(); B.destroy();
}

// Memory: the fields of seven 2048^2 levels held on the GPU at once (the worst case the plan allows: the solving
// level's working set of RGBA packs plus every finished level's single fields), allocated and touched.
{
    const N = 2048;
    const one = N * N * 4;
    const bufs = [];
    device.pushErrorScope('out-of-memory');
    device.pushErrorScope('validation');
    const t = performance.now();
    for (let i = 0; i < 9; i++) bufs.push(device.createBuffer({ size: one * 4, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST | GPUBufferUsage.COPY_SRC }));
    for (let lv = 0; lv < 7; lv++) for (let f = 0; f < 24; f++) bufs.push(device.createBuffer({ size: one, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST | GPUBufferUsage.COPY_SRC }));
    const z = new Float32Array(N * N);
    for (const b of bufs) device.queue.writeBuffer(b, 0, z, 0, Math.min(z.length, b.size / 4));
    await device.queue.onSubmittedWorkDone();
    const v = await device.popErrorScope();
    const o = await device.popErrorScope();
    const bytes = bufs.reduce((s, b) => s + b.size, 0);
    res.memory_7_levels_2048 = { buffers: bufs.length, gib: +(bytes / 2 ** 30).toFixed(2),
        allocate_and_clear_ms: +(performance.now() - t).toFixed(0), validation_error: v ? v.message : null,
        oom_error: o ? o.message : null };
    console.log('memory', JSON.stringify(res.memory_7_levels_2048));
    for (const b of bufs) b.destroy();
}

console.log('RESULT ' + JSON.stringify(res));
if (OUT) Deno.writeTextFileSync(OUT, JSON.stringify(res, null, 1));
device.destroy();
