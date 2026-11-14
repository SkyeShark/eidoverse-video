// Design probe (PORT_PLAN.md section 1.2): the WebGPU device this machine gives Deno, as the terrain port would
// request it (render_common.mjs's request: core-features-and-limits when offered, the buffer limits raised to the
// adapter's maximum), plus the optional features the port's runner would use when present.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/design_probes/gpu_device.mjs [out.json]
//
// Prints one JSON object: adapter info, every adapter feature, the device limits the runner depends on, and
// whether the optional features (timestamp-query, shader-f16, float32-filterable, subgroups) can be enabled.

const out = Deno.args[0] ?? null;
const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
if (!adapter) throw new Error('no WebGPU adapter');
const info = adapter.info ?? {};
const want = ['core-features-and-limits', 'timestamp-query', 'shader-f16', 'float32-filterable', 'subgroups'];
const requiredFeatures = want.filter((f) => adapter.features.has(f));
const requiredLimits = {};
for (const k of ['maxStorageBufferBindingSize', 'maxBufferSize', 'maxComputeWorkgroupStorageSize',
    'maxComputeInvocationsPerWorkgroup', 'maxStorageBuffersPerShaderStage', 'maxStorageTexturesPerShaderStage',
    'maxSampledTexturesPerShaderStage', 'maxBindGroups', 'maxUniformBufferBindingSize']) {
    const v = adapter.limits?.[k];
    if (v != null) requiredLimits[k] = v;
}
const device = await adapter.requestDevice({ requiredFeatures, requiredLimits });
const L = {};
for (const k of ['maxBufferSize', 'maxStorageBufferBindingSize', 'maxUniformBufferBindingSize',
    'minUniformBufferOffsetAlignment', 'minStorageBufferOffsetAlignment', 'maxTextureDimension2D',
    'maxComputeWorkgroupSizeX', 'maxComputeWorkgroupSizeY', 'maxComputeInvocationsPerWorkgroup',
    'maxComputeWorkgroupStorageSize', 'maxComputeWorkgroupsPerDimension', 'maxStorageBuffersPerShaderStage',
    'maxStorageTexturesPerShaderStage', 'maxSampledTexturesPerShaderStage', 'maxBindGroups',
    'maxBindingsPerBindGroup', 'maxDynamicUniformBuffersPerPipelineLayout']) {
    L[k] = device.limits[k];
}
// storage-texture formats the runner might bind read_write (core WebGPU: r32float / r32uint / r32sint only)
const rw = {};
for (const fmt of ['r32float', 'rgba32float', 'rg32float']) {
    device.pushErrorScope('validation');
    const tex = device.createTexture({ size: [16, 16], format: fmt,
        usage: GPUTextureUsage.STORAGE_BINDING | GPUTextureUsage.TEXTURE_BINDING });
    let ok = true;
    try {
        device.createBindGroupLayout({ entries: [{ binding: 0, visibility: GPUShaderStage.COMPUTE,
            storageTexture: { access: 'read-write', format: fmt, viewDimension: '2d' } }] });
    } catch (e) { ok = false; }
    const err = await device.popErrorScope();
    rw[fmt] = ok && !err;
    tex.destroy();
}
const res = {
    deno: Deno.version.deno,
    adapter: { vendor: info.vendor, architecture: info.architecture, device: info.device,
        description: info.description, isFallbackAdapter: info.isFallbackAdapter ?? null },
    adapter_features: [...adapter.features].sort(),
    device_features: [...device.features].sort(),
    limits: L,
    read_write_storage_texture: rw,
    wgsl_language_features: navigator.gpu.wgslLanguageFeatures ? [...navigator.gpu.wgslLanguageFeatures].sort() : null,
};
console.log(JSON.stringify(res, null, 1));
if (out) Deno.writeTextFileSync(out, JSON.stringify(res, null, 1));
device.destroy();
