// The houseplants (eidoverse/props/houseplants.js) in the props' studio light (eidoverse/examples/studio_light.js): the
// rubber plant, the Monstera on its coir pole and the corn plant in a row, the basil and the watering can on a low
// plinth beside them, the camera drifting in toward the Monstera's leaves.
//
//   python eido.py render eidoverse/examples/houseplants/scene.json
//   python eido.py render eidoverse/examples/houseplants/scene.json --at 1 --at 5 --at 9      # stills
//
// The first build fetches the seven CC0 sets the pots, soil, bark and coir read into eidoverse/assets/cache/.
globalThis._noAutoEnhance = true;

globalThis.setup = async function () {
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    await renderer.init();
    renderer.setSize(WIDTH, HEIGHT);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.shadowMap.enabled = true;
    const view = await import(new URL('examples/studio_light.js', EIDOVERSE_DIR).href);
    const scene = view.studio(renderer, { grid: true });
    scene.traverse((o) => {
        if (o.isDirectionalLight) {
            o.castShadow = true;
            o.shadow.mapSize.set(4096, 4096);
            Object.assign(o.shadow.camera, { left: -2.5, right: 2.5, top: 2.5, bottom: -2.5, near: 0.5, far: 20 });
            o.shadow.normalBias = 0.01;
        }
    });
    const floor = new THREE.Mesh(new THREE.CircleGeometry(8, 96), new THREE.ShadowMaterial({ opacity: 0.3 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);
    const plinth = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.45, 0.42),
        new THREE.MeshStandardNodeMaterial({ color: 0xd8d6d0, roughness: 0.7 }));
    plinth.position.set(1.5, 0.225, 0.3);
    plinth.castShadow = plinth.receiveShadow = true;
    scene.add(plinth);

    const HP = await import(new URL('props/houseplants.js', EIDOVERSE_DIR).href);
    const library = await HP.library(THREE);          // one CC0 library for all five
    const plants = [];
    for (const [species, x, y, z, turn] of [['rubber_plant', -0.75, 0, 0, 0.3], ['monstera', 0.0, 0, 0, -0.2],
        ['corn_plant', 0.75, 0, 0, 0.6], ['basil', 1.36, 0.45, 0.32, 0], ['watering_can', 1.62, 0.45, 0.3, -0.7]]) {
        const p = await HP.build(THREE, species, { library });
        p.group.position.set(x, y, z);
        p.group.rotation.y = turn;
        scene.add(p.group);
        plants.push(p);
    }
    const camera = new THREE.PerspectiveCamera(30, WIDTH / HEIGHT, 0.05, 60);
    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;
    console.log(`[houseplants] ${plants.map((p) => `${p.group.name} ${Object.keys(p.parts).length} parts`).join(', ')}`);
};

globalThis.renderFrame = async function (t) {
    const cam = globalThis._c;
    const k = THREE.MathUtils.smootherstep(t, 0, 12);
    // from the whole row in toward the Monstera's leaves
    cam.position.set(-0.4 + 0.9 * k, 1.45 - 0.15 * k + 0.05 * Math.sin(t * 0.5), 5.2 - 2.4 * k);
    cam.lookAt(0.4 - 0.25 * k, 0.8 + 0.15 * k, 0.05);
    await globalThis._r.renderAsync(globalThis._s, cam);
};
