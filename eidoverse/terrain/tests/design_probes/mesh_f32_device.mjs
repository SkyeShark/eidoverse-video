// Design probe (PORT_PLAN.md 4.7, 7.3 and 8.4, the revision), the GPU half. Reads mesh_f32_prep.py's files from
// <dir> and measures, on this machine's WebGPU device:
//   corners  build/mesh.py's Catmull-Rom vertex height at every cell corner (weights (-1, 9, 9, -1)/16, rows first,
//            then columns, edges clamped) three ways against Blender's float64-then-float32: plain f32; a double-float
//            (two f32 per value) evaluation whose products use fma; and a double-float one with no fma at all (x 9/16 is
//            (8x + x)/16, an exact two-sum; x 1/16 is exact), so it does not depend on whether fma is fused
//   lines    the ring's lattice positions as Math.fround(origin + xs * unit) in JavaScript doubles against Blender's
//            np.float32(origin + xs * unit)
//   bypass   render_common.mjs's createShaderModule rewrite (u32(0) -> 0) on the instance, and a kernel compiled through
//            GPUDevice.prototype.createShaderModule.call(device, ...) instead
//   limits   the adapter's and a default device's limits that the mesh and the surfacing wave depend on
//     deno run --no-config --no-lock --unstable-webgpu --allow-all mesh_f32_device.mjs <dir>
const dir = Deno.args[0];
const prep = JSON.parse(Deno.readTextFileSync(`${dir}/prep.json`));
const f32 = (name) => new Float32Array(Deno.readFileSync(`${dir}/${name}`).buffer);

const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
const KEYS = ['maxTextureDimension2D', 'maxTextureArrayLayers', 'maxSampledTexturesPerShaderStage',
    'maxSamplersPerShaderStage', 'maxStorageTexturesPerShaderStage', 'maxStorageBuffersPerShaderStage',
    'maxVertexBuffers', 'maxVertexAttributes', 'maxInterStageShaderVariables', 'maxColorAttachments',
    'maxColorAttachmentBytesPerSample', 'maxBindGroups', 'maxComputeWorkgroupStorageSize', 'maxBufferSize',
    'maxStorageBufferBindingSize'];
const device = await adapter.requestDevice();
const out = {
    deno: Deno.version.deno, adapter: adapter.info?.description ?? '', numpy_of_reference: prep.numpy,
    adapter_limits: Object.fromEntries(KEYS.map((k) => [k, adapter.limits[k]])),
    default_device_limits: Object.fromEntries(KEYS.map((k) => [k, device.limits[k]])),
    features: [...adapter.features].sort(),
};

function buf(data, usage) {
    const b = device.createBuffer({ size: Math.max(16, data.byteLength), usage, mappedAtCreation: true });
    new data.constructor(b.getMappedRange()).set(data);
    b.unmap();
    return b;
}
async function run(code, bindings, count, outBytes, make = (d) => device.createShaderModule(d)) {
    device.pushErrorScope('validation');
    const module = make({ code });
    const msgs = (await module.getCompilationInfo()).messages.filter((m) => m.type === 'error');
    if (msgs.length) { await device.popErrorScope(); return { error: msgs.map((m) => m.message).join('; ') }; }
    const pipe = device.createComputePipeline({ layout: 'auto', compute: { module, entryPoint: 'main' } });
    const res = device.createBuffer({ size: outBytes, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC });
    const entries = bindings.map((b, i) => ({ binding: i, resource: { buffer: b } }));
    entries.push({ binding: bindings.length, resource: { buffer: res } });
    const bg = device.createBindGroup({ layout: pipe.getBindGroupLayout(0), entries });
    const enc = device.createCommandEncoder();
    const pass = enc.beginComputePass();
    pass.setPipeline(pipe);
    pass.setBindGroup(0, bg);
    pass.dispatchWorkgroups(Math.ceil(count / 256));
    pass.end();
    const rb = device.createBuffer({ size: outBytes, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST });
    enc.copyBufferToBuffer(res, 0, rb, 0, outBytes);
    device.queue.submit([enc.finish()]);
    const err = await device.popErrorScope();
    if (err) return { error: err.message };
    await rb.mapAsync(GPUMapMode.READ);
    const copy = rb.getMappedRange().slice(0);
    rb.unmap();
    res.destroy();
    rb.destroy();
    return { data: copy };
}

// ulp of a float32 value (normal numbers; the smallest normal's ulp below)
const ulp32 = (x) => {
    const e = (new Uint32Array(new Float32Array([Math.abs(x)]).buffer)[0] >>> 23) & 0xff;
    return 2 ** (Math.max(e, 1) - 127 - 23);
};

const PRE = (N) => `
@group(0) @binding(0) var<storage, read> h: array<f32>;
@group(0) @binding(1) var<storage, read_write> z: array<f32>;
const N: i32 = ${N};
const M: i32 = ${N + 1};
const W = array<f32, 4>(-0.0625, 0.5625, 0.5625, -0.0625);
fn at(i: i32, j: i32) -> f32 { return h[clamp(j, 0, N - 1) * N + clamp(i, 0, N - 1)]; }
fn two_sum(a: f32, b: f32) -> vec2<f32> { let s = a + b; let bb = s - a; return vec2<f32>(s, (a - (s - bb)) + (b - bb)); }
fn quick(a: f32, b: f32) -> vec2<f32> { let s = a + b; return vec2<f32>(s, b - (s - a)); }
fn df_add(x: vec2<f32>, y: vec2<f32>) -> vec2<f32> {
  let s = two_sum(x.x, y.x);
  let t = two_sum(x.y, y.y);
  let u = quick(s.x, s.y + t.x);
  return quick(u.x, u.y + t.y);
}`;
const KERNELS = {
    plain: (N) => `${PRE(N)}
@compute @workgroup_size(256) fn main(@builtin(global_invocation_id) g: vec3<u32>) {
  let id = i32(g.x);
  if (id >= M * M) { return; }
  let ci = id % M;
  let cj = id / M;
  var zz = 0.0;
  for (var b = 0; b < 4; b++) {
    let i = ci - 2 + b;
    var t = at(i, cj - 2) * W[0];
    t += at(i, cj - 1) * W[1];
    t += at(i, cj) * W[2];
    t += at(i, cj + 1) * W[3];
    if (b == 0) { zz = t * W[0]; } else { zz += t * W[b]; }
  }
  z[id] = zz;
}`,
    df_fma: (N) => `${PRE(N)}
fn two_prod(a: f32, b: f32) -> vec2<f32> { let p = a * b; return vec2<f32>(p, fma(a, b, -p)); }
fn df_mulf(x: vec2<f32>, w: f32) -> vec2<f32> { let p = two_prod(x.x, w); return quick(p.x, fma(x.y, w, p.y)); }
@compute @workgroup_size(256) fn main(@builtin(global_invocation_id) g: vec3<u32>) {
  let id = i32(g.x);
  if (id >= M * M) { return; }
  let ci = id % M;
  let cj = id / M;
  var zz = vec2<f32>(0.0, 0.0);
  for (var b = 0; b < 4; b++) {
    let i = ci - 2 + b;
    var t = two_prod(at(i, cj - 2), W[0]);
    t = df_add(t, two_prod(at(i, cj - 1), W[1]));
    t = df_add(t, two_prod(at(i, cj), W[2]));
    t = df_add(t, two_prod(at(i, cj + 1), W[3]));
    zz = df_add(zz, df_mulf(t, W[b]));
  }
  z[id] = zz.x + zz.y;
}`,
    df_add9: (N) => `${PRE(N)}
// x * 9/16 = (8x + x) / 16: the two-sum is exact and so is the power-of-two scale; x * -1/16 is exact
fn p9(x: f32) -> vec2<f32> { let s = two_sum(x * 8.0, x); return vec2<f32>(s.x * 0.0625, s.y * 0.0625); }
fn p1(x: f32) -> vec2<f32> { return vec2<f32>(x * -0.0625, 0.0); }
fn d9(x: vec2<f32>) -> vec2<f32> { return df_add(p9(x.x), p9(x.y)); }
fn d1(x: vec2<f32>) -> vec2<f32> { return vec2<f32>(x.x * -0.0625, x.y * -0.0625); }
@compute @workgroup_size(256) fn main(@builtin(global_invocation_id) g: vec3<u32>) {
  let id = i32(g.x);
  if (id >= M * M) { return; }
  let ci = id % M;
  let cj = id / M;
  var zz = vec2<f32>(0.0, 0.0);
  for (var b = 0; b < 4; b++) {
    let i = ci - 2 + b;
    var t = p1(at(i, cj - 2));
    t = df_add(t, p9(at(i, cj - 1)));
    t = df_add(t, p9(at(i, cj)));
    t = df_add(t, p1(at(i, cj + 1)));
    if (b == 0 || b == 3) { zz = df_add(zz, d1(t)); } else { zz = df_add(zz, d9(t)); }
  }
  z[id] = zz.x + zz.y;
}`,
};

out.corners = {};
for (const [name, fi] of Object.entries(prep.fields)) {
    const N = fi.n, M = N + 1;
    const h = f32(`${name}_h.bin`), ref = f32(`${name}_cr.bin`), tap = f32(`${name}_tap.bin`);
    const refBits = new Int32Array(ref.buffer);
    const hBuf = buf(h, GPUBufferUsage.STORAGE);
    const rec = { n: N, h_min: fi.h_min, h_max: fi.h_max, max_grad_per_cell: +fi.max_grad_per_cell.toFixed(2) };
    for (const [kname, make] of Object.entries(KERNELS)) {
        const r = await run(make(N), [hBuf], M * M, M * M * 4);
        if (r.error) { rec[kname] = { error: r.error }; continue; }
        const z = new Float32Array(r.data), bits = new Int32Array(r.data);
        let diff = 0, maxUlpZ = 0, maxUlpTap = 0, maxAbs = 0, over4UlpZ = 0, maxUlpZat = null;
        const hist = {};
        for (let k = 0; k < z.length; k++) {
            if (bits[k] === refBits[k]) continue;
            diff++;
            const d = Math.abs(z[k] - ref[k]);
            const uz = d / ulp32(ref[k]), ut = d / ulp32(tap[k]);
            const b = uz <= 4 ? String(Math.round(uz)) : uz <= 64 ? '5-64' : uz <= 4096 ? '65-4096' : '>4096';
            hist[b] = (hist[b] ?? 0) + 1;
            if (uz > 4) over4UlpZ++;
            if (uz > maxUlpZ) { maxUlpZ = uz; maxUlpZat = { z: ref[k], tap_max: tap[k], abs_m: d }; }
            if (ut > maxUlpTap) maxUlpTap = ut;
            if (d > maxAbs) maxAbs = d;
        }
        rec[kname] = { vertices: z.length, bit_equal: z.length - diff, differing: diff,
            frac_differing: +(diff / z.length).toExponential(3), max_ulp_of_z: +maxUlpZ.toPrecision(4),
            worst_vertex: maxUlpZat, over_4_ulp_of_z: over4UlpZ, max_ulp_of_largest_tap: +maxUlpTap.toPrecision(4),
            max_abs_m: maxAbs, histogram_ulp_of_z: hist };
    }
    out.corners[name] = rec;
    hBuf.destroy();
}

// lattice lines
{
    const lines = f32('lines.bin');
    const cnt = prep.lines.count;
    let bad = 0;
    prep.lines.pairs.forEach(([o, u], p) => {
        for (let x = 0; x < cnt; x++) if (Math.fround(o + x * u) !== lines[p * cnt + x]) bad++;
    });
    out.lines = { pairs: prep.lines.pairs.length, values: prep.lines.pairs.length * cnt, differing: bad };
}

// the createShaderModule rewrite and its bypass
{
    const cnt = `
@group(0) @binding(0) var<storage, read> h: array<f32>;
@group(0) @binding(1) var<storage, read_write> o: array<u32>;
@compute @workgroup_size(256) fn main(@builtin(global_invocation_id) g: vec3<u32>) {
  var c = u32(0);
  for (var k = 0u; k < 4u; k++) { if (h[g.x + k] > 0.5) { c = c + 1u; } }
  o[g.x] = c;
}`;
    const data = new Float32Array(260).map((_, i) => (i % 3 === 0 ? 1 : 0));
    const hb = buf(data, GPUBufferUsage.STORAGE);
    const origCSM = device.createShaderModule.bind(device);              // render_common.mjs's patch, verbatim
    device.createShaderModule = function (desc) {
        const orig = desc.code || '';
        const code = orig.replace(/\bu32\s*\(\s*0(?:\.0+)?u?\s*\)/g, '0');
        return code !== orig ? origCSM({ ...desc, code }) : origCSM(desc);
    };
    const proto = typeof GPUDevice !== 'undefined' ? GPUDevice.prototype.createShaderModule : undefined;
    const a = await run(cnt, [hb], 256, 1024);
    const b = proto ? await run(cnt, [hb], 256, 1024, (d) => proto.call(device, d)) : { error: 'no GPUDevice.prototype' };
    let ok = null;
    if (b.data) {
        const o = new Uint32Array(b.data);
        ok = o.every((v, i) => v === [0, 1, 2, 3].reduce((s, k) => s + (data[i + k] > 0.5 ? 1 : 0), 0));
    }
    out.bypass = { prototype_method: typeof proto, patched_instance: a.error ? `error: ${a.error.slice(0, 140)}` : 'compiles',
        prototype_call: b.error ? `error: ${b.error.slice(0, 140)}` : 'compiles', prototype_call_result_exact: ok };
    device.createShaderModule = origCSM;
    hb.destroy();
}

console.log(JSON.stringify(out, null, 1));
Deno.writeTextFileSync(`${dir}/device.json`, JSON.stringify(out, null, 1));
device.destroy();
