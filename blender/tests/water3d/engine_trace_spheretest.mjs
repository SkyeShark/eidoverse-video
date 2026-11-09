// Runs the ENGINE's fluid_water.js (read-only) on the spheretest scene's water, headless, and writes its GPU volume
// trace: the parity reference for the dynamic sphere colliders (test_water3d_spheretest_parity.py).
//
//   deno run --no-config --no-lock -A --import-map=importmap_engine.json engine_trace_spheretest.mjs \
//       json=engine_trace_spheretest_novc.json [opts={"volumeControl":false}] [T=10]
//
// E:/eidoverse-video-desktop-work-folder/spheretest/scene.js, option for option: gridSize [64, 48, 64], worldSize
// [2, 1.5, 2], domainCenter [0, 0.75, 0], maxSpheres 4, columnDepth 0.62, measureVolume; a 0.26 m ball held at
// y = 1.30 for 3 s, then descending 0.42 m/s to y = 0.30 and, from 5 s, sweeping x = 0.55 sin((t - 5) 1.5), fed with
// setSpheres once per frame before step(1/30). The volume (solid cells excluded, as the sensor does) every 15 frames.
globalThis.self = globalThis; globalThis.requestAnimationFrame = () => 0; globalThis.cancelAnimationFrame = () => {};
const THREE = await import('three/webgpu');
const args = Object.fromEntries(Deno.args.map(a => a.split('=')));
const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
const device = await adapter.requestDevice();
const fakeTex = () => device.createTexture({ size: [64, 64], format: 'bgra8unorm',
    usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC });
const context = { configure() {}, unconfigure() {}, getCurrentTexture: fakeTex };
const canvas = { width: 64, height: 64, style: {}, addEventListener() {}, removeEventListener() {}, getContext: () => context };
const renderer = new THREE.WebGPURenderer({ canvas, context, adapter, device, antialias: false });
await renderer.init();
const { createWaterSim } = await import('file:///C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/eidoverse/fluid_water.js');
const opts = JSON.parse(args.opts || '{"volumeControl":false}');
const water = await createWaterSim(renderer, Object.assign({ gridSize: [64, 48, 64], worldSize: [2, 1.5, 2],
    domainCenter: [0, 0.75, 0], maxSpheres: 4, measureVolume: true, columnDepth: 0.62 }, opts));
const T = Number(args.T || 10), FPS = 30, R = 0.26;
const out = [[0, await water.measureVolume()]];
for (let f = 0; f < Math.round(T * FPS); f++) {
    const t = f / FPS;
    const y = t < 3 ? 1.30 : Math.max(0.30, 1.30 - (t - 3) * 0.42);
    const x = t < 5 ? 0 : Math.sin((t - 5) * 1.5) * 0.55;
    water.setSpheres([{ x, y, z: 0, r: R }]);
    await water.step(1 / FPS);
    if ((f + 1) % 15 === 0) out.push([water.simTime, await water.measureVolume()]);
}
console.log('[spheretest] ' + out.map(([t, v]) => t.toFixed(1) + ':' + v.toFixed(4)).join(' '));
if (args.json) Deno.writeTextFileSync(args.json, JSON.stringify({ opts, fps: FPS, trace: out }, null, 1));
Deno.exit(0);
