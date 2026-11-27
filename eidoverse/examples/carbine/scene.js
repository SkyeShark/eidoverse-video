// The carbine (eidoverse/props/carbine.js) in the props' studio light (eidoverse/examples/studio_light.js), with an 18 %
// grey ball and a mirror ball beside it to read the exposure and the room: three held views (the left three-quarter,
// the receiver close, the top from 0.6 m), then a slow turn round it.
//
//   python eido.py render eidoverse/examples/carbine/scene.json
//   python eido.py render eidoverse/examples/carbine/scene.json --at 1 --at 3 --at 5      # the three views as PNGs
//
// The first build fetches the material's six CC0 photographs (ambientCG) into eidoverse/assets/cache/.
globalThis._noAutoEnhance = true;

// the views: [centre, camera offset] in the carbine's space (metres: +X to the muzzle, +Y up, +Z its right), and the
// lens in mm on a 36 mm-wide frame
const VIEWS = [
    { name: 'left_three_quarter', centre: [0.20, -0.03, 0.0], offset: [0.35, 0.45, -1.15], lens: 50 },
    { name: 'receiver_left_close', centre: [0.10, -0.03, 0.0], offset: [0.06, 0.14, -0.40], lens: 60 },
    { name: 'top_left_0p6m', centre: [0.10, -0.03, 0.0], offset: [0.36, 0.448, -0.176], lens: 45 },
];
const HOLD = 2.0;

function lensFov(lens) {             // a horizontal 36 mm frame (the Blender camera's AUTO fit), as three's vertical FOV
    const h = 2 * Math.atan(18 / lens);
    return THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(h / 2) / (WIDTH / HEIGHT)));
}

globalThis.setup = async function () {
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    await renderer.init();
    renderer.setSize(WIDTH, HEIGHT);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.shadowMap.enabled = true;
    const view = await import(new URL('examples/studio_light.js', EIDOVERSE_DIR).href);
    const scene = view.studio(renderer, { grid: false });
    scene.traverse((o) => {
        if (o.isDirectionalLight) {
            o.castShadow = true;
            o.shadow.mapSize.set(2048, 2048);
            Object.assign(o.shadow.camera, { left: -0.5, right: 0.5, top: 0.5, bottom: -0.5, near: 0.5, far: 12 });
            o.shadow.normalBias = 0.002;
        }
    });

    const C = await import(new URL('props/carbine.js', EIDOVERSE_DIR).href);
    const rifle = await C.build(THREE, { condition: { wear: 1.0, polish: 1.0, dust: 1.0, grime: 1.0 } });
    scene.add(rifle.group);
    // the judging balls, 2 cm: an 18 % grey and a mirror
    for (const [x, col, rough, metal] of [[0.30, 0.18, 0.9, 0.0], [0.35, 0.9, 0.02, 1.0]]) {
        const b = new THREE.Mesh(new THREE.SphereGeometry(0.02, 48, 24),
            new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(col, col, col), roughness: rough, metalness: metal }));
        b.position.set(x, -0.16, -0.09);
        scene.add(b);
    }
    const camera = new THREE.PerspectiveCamera(30, WIDTH / HEIGHT, 0.01, 50);
    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera; globalThis._rifle = rifle;
    console.log(`[carbine] ${Object.keys(rifle.parts).length} parts`);
};

globalThis.renderFrame = async function (t) {
    const cam = globalThis._c;
    const i = Math.floor(t / HOLD);
    if (i < VIEWS.length) {
        const v = VIEWS[i];
        cam.fov = lensFov(v.lens);
        cam.position.set(v.centre[0] + v.offset[0], v.centre[1] + v.offset[1], v.centre[2] + v.offset[2]);
        cam.lookAt(...v.centre);
    } else {                                        // a slow turn round it, 1.3 m out
        const a = -Math.PI / 2 + (t - VIEWS.length * HOLD) * 0.45;
        cam.fov = lensFov(50);
        cam.position.set(0.2 + 1.3 * Math.sin(a), 0.38, 1.3 * Math.cos(a));
        cam.lookAt(0.2, -0.03, 0.0);
    }
    cam.updateProjectionMatrix();
    await globalThis._r.renderAsync(globalThis._s, cam);
};
