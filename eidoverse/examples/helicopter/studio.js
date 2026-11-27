// The helicopter (eidoverse/props/helicopter.js) in the library's studio light (eidoverse/robotics/studio.js), on its
// wheels with its rotors idling, the camera walking round it: the open left door and its troop seat, the nose, the
// tail, the rotor head.
//
//   python eido.py render eidoverse/examples/helicopter/studio.json
//   python eido.py render eidoverse/examples/helicopter/studio.json --at 1 --at 5 --at 9      # stills
globalThis._noAutoEnhance = true;

const IDLE_RPM = 30, IDLE_TAIL_RPM = 140;   // slow enough to read every blade (in flight: H.RPM, H.TAIL_RPM)

globalThis.setup = async function () {
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    await renderer.init();
    renderer.setSize(WIDTH, HEIGHT);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.shadowMap.enabled = true;
    const view = await import(new URL('robotics/studio.js', EIDOVERSE_DIR).href);
    const scene = view.studio(renderer, { grid: true });
    scene.traverse((o) => {
        if (o.isDirectionalLight) {
            o.castShadow = true;
            o.position.set(8, 20, 12);
            o.shadow.mapSize.set(4096, 4096);
            Object.assign(o.shadow.camera, { left: -12, right: 12, top: 12, bottom: -12, near: 1, far: 60 });
            o.shadow.normalBias = 0.02;
        }
    });
    const floor = new THREE.Mesh(new THREE.CircleGeometry(30, 96), new THREE.ShadowMaterial({ opacity: 0.3 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    const H = await import(new URL('props/helicopter.js', EIDOVERSE_DIR).href);
    const heli = await H.build(THREE, { rpm: IDLE_RPM, tailRpm: IDLE_TAIL_RPM });
    heli.group.position.y = 0.91;                // the gear hangs as in flight: its main wheels reach y -0.91
    scene.add(heli.group);
    const camera = new THREE.PerspectiveCamera(32, WIDTH / HEIGHT, 0.1, 300);
    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera; globalThis._heli = heli;
    console.log(`[helicopter studio] ${Object.keys(heli.parts).length} named nodes, ${Object.keys(heli.materials).length} materials`);
};

globalThis.renderFrame = async function (t) {
    const heli = globalThis._heli, cam = globalThis._c;
    heli.update(t);
    // most of the way round it in the film's 12 s: from the left front (the open door, +Z) by the tail (+X) to the right
    const a = 2.3 - t * (2 * Math.PI / 12) * 0.85;
    const r = 17 - 3 * Math.sin(t * 0.5);
    cam.position.set(2.5 + r * Math.cos(a), 3.2 + 1.2 * Math.sin(t * 0.4), r * Math.sin(a));
    cam.lookAt(2.0, 1.6, 0);
    await globalThis._r.renderAsync(globalThis._s, cam);
};
