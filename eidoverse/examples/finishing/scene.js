// The finishing example, step 2: the film. The classic Claude sona sings song.py's two lines on a small dark stage
// under a warm key and a cool rim while the camera pushes in from the whole figure to the face. Its mouth is the
// vocal stem's own (lipsync.py get_viseme_timeline_from_vocal, written by song.py to work/finishing/visemes.json:
// values 0..1, set as they are). Render from the repository root after song.py:
//
//     python eido.py render eidoverse/examples/finishing/scene.json --at 4 --at 9     (stills first)
//     python eido.py render eidoverse/examples/finishing/scene.json
//
// then finish.py prints, measures and lays out the film (see README.md).

const DEC = new TextDecoder();
const J = (k) => JSON.parse(DEC.decode(globalThis.ASSETS[k]));
const smooth = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
const VISEMES = ['aa', 'ih', 'ou', 'ee', 'oh'];

globalThis.setup = async function () {
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.9;
    await renderer.init();

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d0a08);
    const camera = new THREE.PerspectiveCamera(32, WIDTH / HEIGHT, 0.1, 60);

    // the stage: boards, and a deep red curtain behind
    const boards = new THREE.Mesh(new THREE.CircleGeometry(3.2, 64),
        new THREE.MeshStandardNodeMaterial({ color: 0x5a3a22, roughness: 0.55, metalness: 0.0 }));
    boards.rotation.x = -Math.PI / 2;
    boards.position.y = -0.003;                  // (a hair under the soles, so they never share a depth)
    scene.add(boards);
    const curtain = new THREE.Mesh(new THREE.PlaneGeometry(9, 5, 90, 1),
        new THREE.MeshStandardNodeMaterial({ color: 0x5c0a10, roughness: 0.85 }));
    const pos = curtain.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) pos.setZ(i, 0.12 * Math.sin(pos.getX(i) * 7.0));   // the folds
    curtain.geometry.computeVertexNormals();
    curtain.position.set(0, 2.5, -2.2);
    scene.add(curtain);

    // light: a warm key from the front left, a cool rim from behind right, a low fill
    const key = new THREE.SpotLight(0xffd9b0, 15, 12, 0.42, 0.6, 1.5);
    key.position.set(-1.6, 3.2, 2.6);
    key.target.position.set(0, 1.2, 0);
    const rim = new THREE.SpotLight(0x8fb8ff, 30, 10, 0.5, 0.7, 1.5);
    rim.position.set(1.8, 2.6, -1.6);
    rim.target.position.set(0, 1.3, 0);
    scene.add(key, key.target, rim, rim.target, new THREE.HemisphereLight(0xffeedd, 0x140c08, 0.35));

    const loader = new globalThis.GLTFLoader();
    loader.register((p) => new globalThis.VRMLoaderPlugin(p));
    const gltf = await new Promise((res, rej) => loader.parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.character_vrm), '', res, rej));
    const vrm = gltf.userData.vrm;
    scene.add(vrm.scene);
    await globalThis.playVRMADefault(vrm, 'stand_breathe', { loop: true });

    globalThis._r = renderer;
    globalThis._s = scene;
    globalThis._c = camera;
    globalThis._vrm = vrm;                       // the engine updates it every frame (expressions, springs)
    globalThis._mouth = J('visemes');
};

globalThis.renderFrame = async function (t) {
    const cam = globalThis._c;
    const k = smooth(t / DURATION);              // from the whole figure to the face
    cam.position.set(0.35 - 0.3 * k, 1.25 + 0.2 * k, 4.4 - 3.1 * k);
    cam.lookAt(0, 1.0 + 0.42 * k, 0);
    const em = globalThis._vrm.expressionManager;
    if (em) {
        VISEMES.forEach((v) => em.setValue(v, 0));                      // reset every frame, then this frame's values
        const m = globalThis._mouth;
        const f = m.frames[Math.min(m.frames.length - 1, Math.floor(t * m.fps))];
        if (f) VISEMES.forEach((v) => em.setValue(v, f[v] || 0));
    }
    await globalThis._r.renderAsync(globalThis._s, cam);
};
