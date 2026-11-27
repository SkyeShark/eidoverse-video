// eidoverse/examples/wake_another_one_hall/scene.js — the WAKE ANOTHER ONE hall (sets/wake_another_one/hall.js)
// through the Blender edition's own lenses, its machines on their controls. The scene config names them:
//   { ..., "small": true, "cameras": ["cam_aisle_out", "cam_station"], "per": 1, "state": { "run": 3.4 },
//     "keys": { "run": [[1, 0], [97, 2]] }, "look": { "fill": 0.1 } }
//   python eido.py render eidoverse/examples/wake_another_one_hall/small.json        # the small hall, two lenses
//   python eido.py render eidoverse/examples/wake_another_one_hall/full.json         # the whole hall, two lenses
//   python eido.py render eidoverse/examples/wake_another_one_hall/cycle.json        # the crane through its cycles
// cameras: one lens every `per` seconds; state: the controls held; keys: the controls keyed on frames (1 = t 0), as
// the Blender edition's animate() keys them; look: build()'s options. The hall brings its own light, sky and air.
globalThis.setup = async function () {
    const cfg = JSON.parse(Deno.readTextFileSync(Deno.args[0]));
    const out = String(cfg.outputVideo || '');
    if (out.includes('/')) Deno.mkdirSync(out.slice(0, out.lastIndexOf('/')), { recursive: true });   // (before the encoder opens it)
    globalThis._bloomParams = { strength: 0 };           // (the hall was lit for a render without bloom)
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    await renderer.init();
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, WIDTH / HEIGHT, 0.05, 7000);
    const HALL = await import(new URL('sets/wake_another_one/hall.js', EIDOVERSE_DIR).href);
    const hall = await HALL.build(THREE, { small: cfg.small !== false, trees: cfg.trees !== false, sky: cfg.sky !== false, ...(cfg.look || {}) });
    scene.add(hall.group);
    const cams = cfg.cameras || ['cam_aisle_out'];
    hall.camera(cams[0], camera);
    await hall.applyTo(scene, renderer, camera);
    const key = cfg.keys ? HALL.animate(cfg.keys, { fps: FPS }) : null;
    console.log(`[hall example] ${cfg.small !== false ? 'small' : 'full'} hall; lenses ${cams.join(', ')}; ${JSON.stringify(hall.report.layout.lines)}`);
    Object.assign(globalThis, { _r: renderer, _s: scene, _c: camera, _hall: hall, _cfg: cfg, _cams: cams, _key: key });
};

globalThis.renderFrame = async function (t) {
    const { _hall: hall, _cfg: cfg, _cams: cams, _key: key } = globalThis;
    hall.camera(cams[Math.min(cams.length - 1, Math.floor(t / (cfg.per || 1)))], globalThis._c);
    hall.update(t, { ...(cfg.state || {}), ...(key ? key(t) : {}) });
    if (globalThis._fx?.update) await globalThis._fx.update(t);
    await globalThis._r.renderAsync(globalThis._s, globalThis._c);
};
