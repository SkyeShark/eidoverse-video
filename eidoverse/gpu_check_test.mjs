import { requestRenderAdapter } from './gpu_check.mjs';

const gpuWith = adapter => ({ requestAdapter: async () => adapter });
async function rejects(gpu, message) {
    try { await requestRenderAdapter(gpu, () => {}); }
    catch (error) {
        if (error.message.includes(message)) return;
        throw error;
    }
    throw new Error(`Expected failure containing: ${message}`);
}

Deno.test('hardware GPU is accepted and high performance is requested', async () => {
    let options;
    const adapter = { info: { description: 'NVIDIA GeForce RTX 5090', isFallbackAdapter: false } };
    let calls = 0;
    const result = await requestRenderAdapter({ requestAdapter: async opts => { calls++; options = opts; return adapter; } }, () => { throw new Error('Hardware should not warn'); });
    if (result.adapter !== adapter || result.info.backend !== 'hardware' || calls !== 1 || options.powerPreference !== 'high-performance') throw new Error('Wrong adapter or preference');
});
Deno.test('hardware Mesa D3D12 may report zero vendor and device IDs', async () => {
    await requestRenderAdapter(gpuWith({ info: { vendor: '0', device: '0',
        description: 'D3D12 (NVIDIA GeForce RTX 5090 Laptop GPU)', isFallbackAdapter: false } }));
});
Deno.test('software fallback works and warns even when its name is unfamiliar', async () => {
    const warnings = [];
    const result = await requestRenderAdapter(gpuWith({ info: { description: 'Adapter 0', isFallbackAdapter: true } }), message => warnings.push(message));
    if (result.info.backend !== 'software' || warnings.length !== 1 || !warnings[0].includes('CPU')) throw new Error('Software fallback must be reported');
});
Deno.test('known software names are correctly reported even with a false fallback flag', async () => {
    for (const description of ['llvmpipe (LLVM 21)', 'lavapipe', 'Google SwiftShader',
        'Microsoft Basic Render Driver', 'WARP', 'softpipe']) {
        const warnings = [];
        const { info } = await requestRenderAdapter(gpuWith({ info: { description, isFallbackAdapter: false } }), message => warnings.push(message));
        if (info.backend !== 'software' || warnings.length !== 1) throw new Error(`${description} should warn and remain usable`);
    }
});
Deno.test('missing GPU or adapter produces a setup error', async () => {
    await rejects(null, 'navigator.gpu missing');
    await rejects(gpuWith(null), 'No WebGPU adapter');
});
Deno.test('unverifiable adapters stay usable without claiming hardware acceleration', async () => {
    for (const info of [{description:'Unidentified driver'}, {isFallbackAdapter:false}]) {
        const warnings = [];
        const result = await requestRenderAdapter(gpuWith({ info }), message => warnings.push(message));
        if (result.info.backend !== 'unknown' || warnings.length !== 1) throw new Error('Unknown adapter must be reported');
    }
});
Deno.test('legacy adapter-info and fallback properties are supported', async () => {
    await requestRenderAdapter(gpuWith({ requestAdapterInfo: async () => ({ description: 'AMD Radeon' }), isFallbackAdapter: false }));
    const result = await requestRenderAdapter(gpuWith({ requestAdapterInfo: async () => ({ description: 'Adapter 0' }), isFallbackAdapter: true }), () => {});
    if (result.info.backend !== 'software') throw new Error('Legacy software adapter misidentified');
});

Deno.test('explicit software adapter is tried when normal selection returns none', async () => {
    const requests = [];
    const fallback = {info:{description:'CPU renderer',isFallbackAdapter:true}};
    const { adapter } = await requestRenderAdapter({requestAdapter: async options => {
        requests.push(options);
        return options.forceFallbackAdapter ? fallback : null;
    }}, () => {});
    if (adapter !== fallback || requests.length !== 2 || requests[0].forceFallbackAdapter || !requests[1].forceFallbackAdapter) throw new Error('Hardware must be tried before explicit fallback');
});
