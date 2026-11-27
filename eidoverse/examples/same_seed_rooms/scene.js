// One of the SAME SEED rooms (sets/same_seed.js) through one of its own lenses. The scene config names them:
//   { ..., "script": "eidoverse/examples/same_seed_rooms/scene.js", "room": "kitchen", "camera": "wide" }
//   python eido.py render eidoverse/examples/same_seed_rooms/kitchen.json --at 0     # a still
// Each room brings its own light, bounce, reflections, background and exposure; nothing else lights it.

globalThis.setup = async function () {
    const cfg = JSON.parse(Deno.readTextFileSync(Deno.args[0]));
    const ROOM = cfg.room || 'kitchen', CAM = cfg.camera || 'wide';
    const out = String(cfg.outputVideo || '');            // (work/same_seed_rooms/ on a fresh checkout: made here,
    if (out.includes('/')) Deno.mkdirSync(out.slice(0, out.lastIndexOf('/')), { recursive: true });   //  before the encoder opens it)
    globalThis._bloomParams = { strength: 0 };   // (the rooms were lit for a render without bloom: their tubes and
                                                  //  windows would haze the whole frame)

    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    await renderer.init();

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, WIDTH / HEIGHT, 0.05, 200);

    const SS = await import(new URL('sets/same_seed.js', EIDOVERSE_DIR).href);
    const room = await SS.build(ROOM, { THREE });
    scene.add(room.group);
    room.applyTo(scene, renderer);          // its world behind the windows, AgX at the room's exposure
    room.camera(CAM, camera);

    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera; globalThis._room = room;
};

globalThis.renderFrame = async function (t) {
    if (globalThis._fx?.update) await globalThis._fx.update(t);
    await globalThis._r.renderAsync(globalThis._s, globalThis._c);
};
