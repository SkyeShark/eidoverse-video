// eidoverse/examples/desert/scene.js — the desert (eidoverse/sets/desert/) under the town's sun and the sky family's sky,
// through the Blender edition's lenses on it, one lens a second. The scene config chooses what stands in it:
//   scene.json   the desert alone (the town's plane where the town would stand): the ring of twelve lenses from 75 m
//                over the town's middle and its two ends, the nearest cliff band and the nearest high dunes (14 s)
//   town.json    the town standing in the desert, as the Blender edition shoots it ("town": true): the same 14 and the
//                town's own pull_back_35mm and across_to_the_edge_40mm (16 s)
//   python eido.py render eidoverse/examples/desert/town.json                        # the film, a lens a second
//   python eido.py render eidoverse/examples/desert/town.json --at 0.5 --at 12.5     # stills of the first and the 13th
globalThis.setup = async function () {
    const cfg = JSON.parse(Deno.readTextFileSync(Deno.args[0]));
    const out = String(cfg.outputVideo || '');                       // (the film's folder, before the encoder opens it)
    if (out.includes('/')) Deno.mkdirSync(out.slice(0, out.lastIndexOf('/')), { recursive: true });
    // (the post chain's AO off: its 0.3 m samples speckle a floor seen kilometres off at a grazing angle, and at these
    //  heights it darkens nothing the eye can find)
    globalThis._aoParams = { enabled: false };
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    await renderer.init();
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, WIDTH / HEIGHT, 1.0, 40000);   // (the Blender lens: 1 m to 40 km)
    const DESERT = await import(new URL('sets/desert/index.js', EIDOVERSE_DIR).href);
    const desert = await DESERT.build(THREE, { renderer, plane: !cfg.town });
    scene.add(desert.group);
    const roots = [desert.group];
    let lenses = desert.views();
    if (cfg.town) {
        const TOWN = await import(new URL('sets/town/index.js', EIDOVERSE_DIR).href);
        const town = await TOWN.build(THREE);
        scene.add(town.group);
        roots.push(town.group);
        lenses = lenses.concat(town.views().filter(([n]) => n === 'pull_back_35mm' || n === 'across_to_the_edge_40mm'));
    }
    camera.position.set(0, 80, 0);
    const W = await DESERT.world(THREE, { scene, camera, renderer, roots });
    console.log(`[desert example] lenses: ${lenses.map((v, i) => `${i}: ${v[0]}`).join(', ')}`);
    Object.assign(globalThis, { _r: renderer, _s: scene, _c: camera, _desert: desert, _W: W, _lenses: lenses, _DESERT: DESERT });
};

globalThis.renderFrame = async function (t) {
    const L = globalThis._lenses[Math.min(globalThis._lenses.length - 1, Math.floor(t))];
    globalThis._DESERT.aim(THREE, globalThis._c, globalThis._desert.group, L[1], L[2], L[3]);
    globalThis._W.update(t);
    await globalThis._r.renderAsync(globalThis._s, globalThis._c);
};
