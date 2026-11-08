// Runs the ENGINE's fluid_water.js (read-only) headless and prints its GPU volume trace: the parity reference.
globalThis.self = globalThis; globalThis.requestAnimationFrame = () => 0; globalThis.cancelAnimationFrame = () => {};
const THREE = await import('three/webgpu');
const args = Object.fromEntries(Deno.args.map(a => a.split('=')));
const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
const device = await adapter.requestDevice();
const W = 64, H = 64;
const fakeTex = () => device.createTexture({ size: [W, H], format: 'bgra8unorm', usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC });
const context = { configure() {}, unconfigure() {}, getCurrentTexture: fakeTex };
const canvas = { width: W, height: H, style: {}, addEventListener() {}, removeEventListener() {}, getContext: () => context };
const renderer = new THREE.WebGPURenderer({ canvas, context, adapter, device, antialias: false });
await renderer.init();
const { createWaterSim } = await import('file:///C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/eidoverse/fluid_water.js');
const opts = JSON.parse(args.opts || '{}');
const water = await createWaterSim(renderer, Object.assign({ gridSize: [64, 48, 64], worldSize: [2, 1.5, 2], columnDepth: 0.62, measureVolume: true }, opts));
const T = Number(args.T || 6), fps = Number(args.fps || 30), every = Number(args.every || 15);
const out = [];
let f = 0;
const v0 = await water.measureVolume();
out.push([0, v0]);
while (water.simTime < T - 1e-9) {
  await water.step(1 / fps); f++;
  if (f % every === 0) { const v = await water.measureVolume(); out.push([water.simTime, v]); console.log(`[vol] t=${water.simTime.toFixed(2)} V=${v.toFixed(5)}`); }
}
if (args.json) Deno.writeTextFileSync(args.json, JSON.stringify({ opts, fps, trace: out }, null, 1));
Deno.exit(0);
