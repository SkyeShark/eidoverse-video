// Runs three-fluid-fx's own WGSLFluidSimulation (the package fluid_sim.js wraps; read-only, from the main checkout's
// node_modules) headless on WebGPU with a scripted splat sequence and writes its textures as raw float32: the
// parity reference for eidoblend.fx.stable_fluids (test_stable_fluids_parity.py runs the port on the same script).
//
//   deno run --no-config --no-lock -A --import-map=<this folder>/importmap_engine.json \
//       engine_run_stable_fluids.mjs out=<dir> case=<name> [frames=60]
//
// case: 'motion' (splat colour = the package default (dx, dy, 1), dye on), 'colour' (fluid_sim.js's splat(): the
// colour tints density AND drives velocity), 'novort' (vorticity off, BFECC off, no wall reflection).
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
const fx = await import('file:///C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01/node_modules/three-fluid-fx/dist-lib/tsl/three-fluid-fx.es.js');
const CASE = args.case || 'motion';
const N = Number(args.frames || 60);
const opts = { profile: 'performance', enableVorticity: CASE !== 'novort', enableDye: true, curlStrength: 0.55 };
if (CASE === 'novort') { opts.bfecc = false; opts.reflectWalls = false; }
const sim = new fx.FluidSimulation(renderer, opts);
sim.enableDye = true;
if (CASE === 'colour') sim.resize(1920, 1080);
// the script (the Python test generates the same one): a circling splat, two crossing jets
const script = (k) => {
    const a = k / N * 2 * Math.PI;
    const out = [[0.5 + 0.3 * Math.cos(a), 0.5 + 0.3 * Math.sin(a), -40 * Math.sin(a), 40 * Math.cos(a)]];
    if (k % 3 === 0) out.push([0.2, 0.25, 30, 12]);
    if (k % 4 === 1) out.push([0.8, 0.7, -25, -18]);
    return out;
};
for (let k = 0; k < N; k++) {
    for (const [x, y, dx, dy] of script(k)) {
        const col = [0.5 + 0.5 * Math.sin(k * 0.3), 0.4, 0.5 + 0.5 * Math.cos(k * 0.2)];
        if (CASE === 'colour') sim.addSplat(x, y, dx, dy, { color: col, dyeColor: col });
        else sim.addSplat(x, y, dx, dy, { dyeColor: col });
    }
    sim.step(1 / 60);
}
await device.queue.onSubmittedWorkDone();
function f16(h) {
    const s = (h & 0x8000) ? -1 : 1, e = (h >> 10) & 0x1f, m = h & 0x3ff;
    if (e === 0) return s * Math.pow(2, -14) * (m / 1024);
    if (e === 31) return m ? NaN : s * Infinity;
    return s * Math.pow(2, e - 15) * (1 + m / 1024);
}
async function dump(tex, name) {
    const gt = sim.getGpuTexture(tex);
    const w = gt.width, h = gt.height, bpr = Math.ceil(w * 8 / 256) * 256;
    const buf = device.createBuffer({ size: bpr * h, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    const enc = device.createCommandEncoder();
    enc.copyTextureToBuffer({ texture: gt }, { buffer: buf, bytesPerRow: bpr }, [w, h, 1]);
    device.queue.submit([enc.finish()]);
    await buf.mapAsync(GPUMapMode.READ);
    const u16 = new Uint16Array(buf.getMappedRange());
    const out = new Float32Array(w * h * 4);
    for (let y = 0; y < h; y++) for (let x = 0; x < w * 4; x++) out[y * w * 4 + x] = f16(u16[y * bpr / 2 + x]);
    buf.unmap();
    Deno.writeFileSync(`${args.out}/engine_fluid2d_${CASE}_${name}.f32`, new Uint8Array(out.buffer));
    return [h, w, 4];
}
const shapes = {
    velocity: await dump(sim.velocity.read, 'velocity'),
    density: await dump(sim.density.read, 'density'),
    dye: await dump(sim.dye.read, 'dye'),
    pressure: await dump(sim.pressure.read, 'pressure'),
};
Deno.writeTextFileSync(`${args.out}/engine_fluid2d_${CASE}.json`, JSON.stringify({ case: CASE, frames: N, opts, shapes }));
console.log('[engine fluid2d]', CASE, JSON.stringify(shapes));
Deno.exit(0);
