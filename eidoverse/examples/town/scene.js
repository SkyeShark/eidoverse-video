// eidoverse/examples/town/scene.js — the town (eidoverse/sets/town/) under its sun and the sky family's sky, through its
// own lenses: one lens a second, as the Blender edition shoots them.
//   python eido.py render eidoverse/examples/town/scene.json                 # 11 lenses, 11 s
//   python eido.py render eidoverse/examples/town/scene.json --at 0.5 --at 7.5   # stills of the first and the eighth
// TOWN_EXTENT=260x160 (a small town), TOWN_DAMAGE=1 (struck round its strikes), TOWN_CLAY=1 (the form in clay).
globalThis.setup = async function () {
    Deno.mkdirSync('work/town_example', { recursive: true });       // (the film's folder, before the encoder opens it)
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    await renderer.init();
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, WIDTH / HEIGHT, 0.3, 6000);
    const env = (k, d) => Deno.env.get(k) ?? d;
    const TOWN = await import(new URL('sets/town/index.js', EIDOVERSE_DIR).href);
    const extent = env('TOWN_EXTENT', '840x300').split('x').map(Number);
    const town = await TOWN.build(THREE, { extent, damage: env('TOWN_DAMAGE', '0') === '1', clay: env('TOWN_CLAY', '0') === '1',
        edge: extent[0] < 500 ? 60 : 170, things: extent[0] >= 500 });
    scene.add(town.group);
    camera.position.set(0, 80, 0);
    const W = await TOWN.world(THREE, { scene, camera, renderer, root: town.group });
    const lenses = town.views();
    console.log(`[town example] lenses: ${lenses.map((v, i) => `${i}: ${v[0]}`).join(', ')}`);
    Object.assign(globalThis, { _r: renderer, _s: scene, _c: camera, _town: town, _W: W, _lenses: lenses, _TOWN: TOWN });
};

globalThis.renderFrame = async function (t) {
    const L = globalThis._lenses[Math.min(globalThis._lenses.length - 1, Math.floor(t))];
    globalThis._TOWN.aim(THREE, globalThis._c, globalThis._town.group, L[1], L[2], L[3]);
    globalThis._W.update(t);
    await globalThis._r.renderAsync(globalThis._s, globalThis._c);
};
