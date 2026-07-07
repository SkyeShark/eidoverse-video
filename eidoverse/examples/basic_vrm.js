// Minimal scene: load a VRM, play idle, orbit the camera.
// Starting template for scenes that don't use the terrain harness.

globalThis.setup = async function () {
    // Renderer — adapter + device come from the harness; passing them is mandatory
    // (Three.js otherwise creates its own GPU handles and your readback returns black)
    const renderer = new THREE.WebGPURenderer({
        canvas, antialias: true,
        adapter: GPU_ADAPTER, device: GPU_DEVICE,
    });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    await renderer.init();

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a14);

    const camera = new THREE.PerspectiveCamera(50, WIDTH / HEIGHT, 0.1, 100);
    camera.position.set(0, 1.4, 2.5);
    camera.lookAt(0, 1.1, 0);

    // Lighting
    scene.add(new THREE.HemisphereLight(0xffffff, 0x202040, 0.8));
    const sun = new THREE.DirectionalLight(0xffffff, 2.5);
    sun.position.set(3, 6, 4);
    scene.add(sun);

    // Reflective ground — metalness > 0.4 picks up cloud reflections automatically
    const floor = new THREE.Mesh(
        new THREE.PlaneGeometry(10, 10),
        new THREE.MeshStandardNodeMaterial({ color: 0x1a1a2e, roughness: 0.35, metalness: 0.8 }),
    );
    floor.rotation.x = -Math.PI / 2;
    scene.add(floor);

    // Load VRM — registering VRMLoaderPlugin is REQUIRED (without it the
    // character parses as a plain GLB: no userData.vrm, black MToon body)
    const loader = new globalThis.GLTFLoader();
    loader.register(p => new globalThis.VRMLoaderPlugin(p));
    const buf = globalThis.b64toArrayBuffer(globalThis.ASSETS.character_vrm);
    const gltf = await new Promise((res, rej) => loader.parse(buf, '', res, rej));
    const vrm = gltf.userData.vrm;
    scene.add(vrm.scene);
    await globalThis.playVRMADefault(vrm, 'idle', { loopOnce: false });

    globalThis._r = renderer;
    globalThis._s = scene;
    globalThis._c = camera;
    globalThis._vrm = vrm;

    // Depth fog — atmospheric depth cue (for a full sky + moving cloud
    // reflections use makeSkySystem instead; see AGENTS.md "WORLD-SPACE SKY")
    globalThis._fx = globalThis.CustomEffectsDeno.applyTo({
        scene, camera,
        effects: 'depth_fog',
        opts: {
            depth_fog: { density: 0.06 },
        },
    });
};

globalThis.renderFrame = async function (t) {
    const camera = globalThis._c;
    // Orbit the camera
    const r = 2.5;
    const angle = t * 0.4;
    camera.position.set(Math.cos(angle) * r, 1.4, Math.sin(angle) * r);
    camera.lookAt(0, 1.1, 0);

    // _fx.update(t) only pushes effect uniforms — it does NOT render.
    // ALWAYS renderAsync afterward (never behind an `else`).
    if (globalThis._fx?.update) await globalThis._fx.update(t);
    await globalThis._r.renderAsync(globalThis._s, camera);
};
// preflight: ASSETS['character_vrm']
