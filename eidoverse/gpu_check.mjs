/** Prefer hardware; clearly report software WebGPU fallback and diagnostics. */
const HELP = 'See docs/SETUP.md#gpu-setup-for-wsl-2 for hardware setup, or ' +
    'docs/SETUP.md#software-fallback for environments without GPU access.';

export async function requestRenderAdapter(gpu = globalThis.navigator?.gpu, warn = console.warn) {
    if (!gpu) throw new Error('navigator.gpu missing — run Deno with --unstable-webgpu.');
    // The runtime normally returns software when hardware is unavailable.
    // Some implementations expose it only through an explicit fallback request.
    const adapter = await gpu.requestAdapter({ powerPreference: 'high-performance' }) ??
        await gpu.requestAdapter({ forceFallbackAdapter: true });
    if (!adapter) throw new Error(`No WebGPU adapter found. ${HELP}`);
    const raw = adapter.info ?? await adapter.requestAdapterInfo?.();
    const info = {
        vendor: raw?.vendor ?? '', device: raw?.device ?? '',
        description: raw?.description ?? '', architecture: raw?.architecture ?? '',
        isFallbackAdapter: raw?.isFallbackAdapter ?? adapter.isFallbackAdapter ?? null,
    };
    const label = [info.description, info.vendor, info.device, info.architecture].filter(Boolean).join(' / ');
    // Check names too: some older implementations omit or misreport the flag.
    const software = /llvmpipe|lavapipe|swiftshader|software|basic render|\bwarp\b|softpipe/i.test(label);
    info.backend = info.isFallbackAdapter === true || software ? 'software' :
        info.isFallbackAdapter === false && label ? 'hardware' : 'unknown';
    if (info.backend === 'software') {
        warn(`[gpu] WARNING: Software WebGPU fallback: ${label || '(unnamed)'}. ` +
            'Rendering/compute will run on the CPU and may be much slower. ' +
            `If GPU access is available, check its driver/backend configuration. ${HELP}`);
    } else if (info.backend === 'unknown') {
        warn(`[gpu] WARNING: Cannot verify the WebGPU adapter type: ${label || '(unnamed)'}. ${HELP}`);
    }
    return { adapter, info };
}

/** Exercise an actual compute dispatch and readback, without scene dependencies. */
export async function checkWebGPU(gpu = globalThis.navigator?.gpu) {
    const { adapter, info } = await requestRenderAdapter(gpu);
    const device = await adapter.requestDevice();
    const resources = [];
    try {
        device.pushErrorScope('validation');
        const count = 64;
        const output = device.createBuffer({ size: count * 4,
            usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC });
        const readback = device.createBuffer({ size: count * 4,
            usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
        resources.push(output, readback);
        const module = device.createShaderModule({ code: `
            @group(0) @binding(0) var<storage, read_write> result: array<u32>;
            @compute @workgroup_size(64)
            fn main(@builtin(global_invocation_id) id: vec3u) {
                result[id.x] = id.x * 3u + 7u;
            }` });
        const pipeline = await device.createComputePipelineAsync({ layout: 'auto',
            compute: { module, entryPoint: 'main' } });
        const bindings = device.createBindGroup({ layout: pipeline.getBindGroupLayout(0),
            entries: [{ binding: 0, resource: { buffer: output } }] });
        const encoder = device.createCommandEncoder();
        const pass = encoder.beginComputePass();
        pass.setPipeline(pipeline);
        pass.setBindGroup(0, bindings);
        pass.dispatchWorkgroups(1);
        pass.end();
        encoder.copyBufferToBuffer(output, 0, readback, 0, count * 4);
        device.queue.submit([encoder.finish()]);
        const error = await device.popErrorScope();
        if (error) throw new Error(error.message);
        await readback.mapAsync(GPUMapMode.READ);
        const values = new Uint32Array(readback.getMappedRange());
        if (!values.every((value, i) => value === i * 3 + 7)) {
            throw new Error('GPU compute readback returned incorrect values.');
        }
        readback.unmap();
        return { ...info, computeReadback: 'passed' };
    } catch (error) {
        throw new Error(`GPU compute check failed on ${info.description}: ${error.message}`);
    } finally {
        for (const resource of resources) resource.destroy();
        device.destroy();
    }
}

if (import.meta.main) {
    const timeout = setTimeout(() => {
        console.error('[gpu] Adapter/device check timed out after 25 seconds.');
        Deno.exit(1);
    }, 25000);
    try {
        console.log(JSON.stringify(await checkWebGPU()));
    } catch (error) {
        console.error(`[gpu] ${error.message}`);
        Deno.exitCode = 1;
    } finally {
        clearTimeout(timeout);
    }
}
