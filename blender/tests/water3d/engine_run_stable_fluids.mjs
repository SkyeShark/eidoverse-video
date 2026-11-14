// Runs three-fluid-fx's own WGSLFluidSimulation (the package fluid_sim.js wraps; read-only, from this checkout's
// node_modules, else the main checkout's) headless on WebGPU with a scripted splat sequence and writes its textures as
// raw float32: the parity reference for eidoblend.fx.stable_fluids (test_stable_fluids_parity.py runs the port on the
// same script).
//
//   deno run --no-config --no-lock -A --import-map=<this folder>/importmap_engine.json \
//       engine_run_stable_fluids.mjs out=<dir> case=<name> [frames=60]
//   (the import map takes three from this checkout's node_modules/)
//
// case: 'motion' (splat colour = the package default (dx, dy, 1), dye on), 'colour' (fluid_sim.js's splat(): the
// colour tints density AND drives velocity), 'novort' (vorticity off, BFECC off, no wall reflection), 'showcase'
// (work/_showcase/fluid's options and splats, 75 frames: test_stable_fluids.py holds its bake to this density).
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
// the checkout that holds the untracked node_modules/, found as blender/tests/_where.py's main_checkout() finds it:
// EIDO_MAIN_CHECKOUT, else the main worktree when this checkout is a linked git worktree (its .git is a file
// "gitdir: <main>/.git/worktrees/<name>"), else this checkout
const repo = new URL('../../../', import.meta.url);
const folderUrl = (p, base) => {            // a folder path, absolute or relative to base, as a file: URL
    p = p.replace(/\\/g, '/').replace(/\/?$/, '/');
    return /^([A-Za-z]:)?\//.test(p) ? new URL('file:///' + p.replace(/^\/+/, '')) : new URL(p, base);
};
const mainCheckout = () => {
    const env = Deno.env.get('EIDO_MAIN_CHECKOUT');
    if (env) return folderUrl(env);
    try {
        const line = Deno.readTextFileSync(new URL('.git', repo)).trim();
        if (line.startsWith('gitdir:')) return new URL('../../../', folderUrl(line.slice(7).trim(), repo));
    } catch { /* .git is the repository's own folder: this is the main checkout */ }
    return repo;
};
const FX = 'node_modules/three-fluid-fx/dist-lib/tsl/three-fluid-fx.es.js';
const isFile = (u) => { try { return Deno.statSync(u).isFile; } catch { return false; } };
const fxUrl = [new URL(FX, repo), new URL(FX, mainCheckout())].find(isFile) ?? new URL(FX, mainCheckout());
const fx = await import(fxUrl.href);
const CASE = args.case || 'motion';
const N = Number(args.frames || (CASE === 'showcase' ? 75 : 60));
// 'showcase': work/_showcase/fluid as the engine ran it (fluid_sim.js's options; its enableDye never reached the
// package, so dye stays off; no resize: the sim stays square), 2.5 s of its renderFrame splats at 30 fps
const opts = CASE === 'showcase'
    ? { profile: 'balanced', enableVorticity: true, curlStrength: 4, densityDissipation: 0.985, splatRadius: 0.004 }
    : { profile: 'performance', enableVorticity: CASE !== 'novort', enableDye: true, curlStrength: 0.55 };
if (CASE === 'novort') { opts.bfecc = false; opts.reflectWalls = false; }
const sim = new fx.FluidSimulation(renderer, opts);
if (CASE !== 'showcase') sim.enableDye = true;
if (CASE === 'colour') sim.resize(1920, 1080);
if (CASE === 'showcase') {
    for (let k = 0; k < N; k++) {
        const t = k / 30;
        for (const [x, y, dx, dy, c] of [[0.30, 0.5, 60, 20, [0.9, 0.2, 0.3]], [0.70, 0.5, -60, -20, [0.2, 0.5, 1.0]],
            [0.5 + Math.sin(t * 1.3) * 0.3, 0.5 + Math.cos(t * 1.9) * 0.3, Math.cos(t * 3) * 50, Math.sin(t * 3) * 50,
             [Math.sin(t) * 0.5 + 0.5, 0.8, Math.cos(t * 1.4) * 0.5 + 0.5]]]) {
            sim.addSplat(x, y, dx, dy, { color: c, dyeColor: c });
        }
        sim.step(1 / 30);
    }
}
// the script (the Python test generates the same one): a circling splat, two crossing jets
const script = (k) => {
    const a = k / N * 2 * Math.PI;
    const out = [[0.5 + 0.3 * Math.cos(a), 0.5 + 0.3 * Math.sin(a), -40 * Math.sin(a), 40 * Math.cos(a)]];
    if (k % 3 === 0) out.push([0.2, 0.25, 30, 12]);
    if (k % 4 === 1) out.push([0.8, 0.7, -25, -18]);
    return out;
};
for (let k = 0; k < (CASE === 'showcase' ? 0 : N); k++) {
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
