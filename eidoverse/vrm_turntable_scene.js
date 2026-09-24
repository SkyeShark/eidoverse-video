// vrm_turntable_scene.js — the scene behind vrm_turntable.py (repo root): a VRM in a neutral studio, in blocks of
// HOLD frames — for each outfit, for each framing, for each turntable yaw. Judge the LAST frame of a block (frame 0 of
// any render is the VRM's load pose; spring bones settle over the block). Configured by environment variables that
// vrm_turntable.py sets; see tools-guides/characters.md ("Turntable sheets").
//   VT_OUTFITS  comma list of claudesona_wardrobe WARDROBE keys, or "-" for no wardrobe (any VRM)
//   VT_VIEWS    yaw degrees       VT_FRAMES  face|head|chest|body      VT_HOLD  frames per block
//   VT_SPIN=1   one eased turn per block (a reel)
//   VT_ANIM     VRMA default slot(s) to play (stand_breathe, idle, dance…); a comma list gives each outfit one row
//               per clip (a clip sheet)
//   VT_SCALE    VRM scale (0.87 puts the 2.00 m claude_suit rig at a human 1.74 m)
//   VT_PRESETS  JSON {name: {base: key, ...overrides}} extra wardrobe variants; "key:nofold" drops a preset's fold
//   VT_FACES    JSON list of raw morph-weight dicts, one per outfit row (expression sheets)
//   VT_LIGHT    studio light level (default 0.7)

const env = (k, d) => Deno.env.get(k) || d;
const OUTFITS = env('VT_OUTFITS', '-').split(',');
const VIEWS = env('VT_VIEWS', '0,35,90,150,180').split(',').map(Number);
const FRAMES = env('VT_FRAMES', 'head,body').split(',');
const HOLD = Number(env('VT_HOLD', '12'));
const SPIN = env('VT_SPIN', '') === '1';
const ANIMS = env('VT_ANIM', 'idle').split(',');
const SCALE = Number(env('VT_SCALE', '1'));
const FACES = JSON.parse(env('VT_FACES', '[]'));

globalThis._aoParams = { quality: 'High', aoRadius: 0.3, intensity: 1.0 };

globalThis.setup = async function () {
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    await renderer.init();
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x2c3038);
    const camera = new THREE.PerspectiveCamera(26, WIDTH / HEIGHT, 0.05, 100);
    // neutral studio: key front-right, cool fill front-left, rim from behind, soft sky/ground ambient. Levels are
    // set for MToon (toon shading adds lights without the 1/pi of a PBR diffuse): white cloth stays under the
    // engine's bloom threshold, so a white coat reads as cloth, not a glow. VT_LIGHT scales the whole studio.
    const L = Number(env('VT_LIGHT', '0.7'));
    const key = new THREE.DirectionalLight(0xfff1e2, 2.3 * L); key.position.set(2.2, 3.0, 3.2);
    const fill = new THREE.DirectionalLight(0xd8e4ff, 0.75 * L); fill.position.set(-3.0, 1.6, 2.4);
    const rim = new THREE.DirectionalLight(0xffffff, 1.4 * L); rim.position.set(-0.8, 2.8, -3.4);
    scene.add(key, fill, rim, new THREE.HemisphereLight(0xe6ecf6, 0x3c3a40, 0.9 * L));
    const floor = new THREE.Mesh(new THREE.CircleGeometry(3, 64), new THREE.MeshStandardNodeMaterial({ color: 0x4a4e57, roughness: 0.9 }));
    floor.rotation.x = -Math.PI / 2; scene.add(floor);

    const loader = new GLTFLoader();
    loader.register((p) => new VRMLoaderPlugin(p));
    const gltf = await new Promise((res, rej) => loader.parse(b64toArrayBuffer(ASSETS.vrm), '', res, rej));
    const vrm = gltf.userData.vrm;
    vrm.scene.scale.setScalar(SCALE);
    vrm.scene.traverse((o) => { if (o.isMesh) o.frustumCulled = false; });
    scene.add(vrm.scene);
    await globalThis.playVRMADefault(vrm, ANIMS[0], { loop: true });
    globalThis._vrm = vrm;
    // frame the character by its own head height (works for any rig and scale)
    vrm.scene.updateWorldMatrix(true, true);
    const head = vrm.humanoid?.getNormalizedBoneNode('head');
    const H = head ? head.getWorldPosition(new THREE.Vector3()).y : 1.3;

    let wardrobe = null;
    if (OUTFITS[0] !== '-') {
        const { makeWardrobe, WARDROBE } = await import(new URL('claudesona_wardrobe.js', EIDOVERSE_DIR).href);
        for (const [name, spec] of Object.entries(JSON.parse(env('VT_PRESETS', '{}')))) {
            const { base, ...over } = spec;
            WARDROBE[name] = { ...(WARDROBE[base] || {}), ...over };
        }
        for (const o of OUTFITS) {
            const [base, mod] = o.split(':');
            if (mod === 'nofold' && WARDROBE[base]) WARDROBE[o] = { ...WARDROBE[base], fold: undefined };
        }
        wardrobe = makeWardrobe(THREE, vrm);
        console.log('[turntable] wardrobe layers: ' + Object.keys(wardrobe.layers).join(', '));
    }
    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;   // the engine's per-frame VRM step keys on these
    globalThis._T = { renderer, scene, camera, vrm, wardrobe, H, block: -1, anim: ANIMS[0], face: {} };
    if (FACES.length) {                                    // raw morph weights, written at render time: the engine's
        vrm.scene.traverse((o) => {                        // VRM pass would overwrite weights set in renderFrame
            if (!o.morphTargetDictionary) return;
            const prev = o.onBeforeRender;
            o.onBeforeRender = function (...a) {
                prev?.apply(this, a);
                for (const [key, idx] of Object.entries(o.morphTargetDictionary)) o.morphTargetInfluences[idx] = globalThis._T.face[key] ?? 0;
            };
        });
    }
};

globalThis.renderFrame = async function (t, i) {
    const T = globalThis._T, { vrm, camera, H } = T;
    const block = Math.floor(i / HOLD);
    const nV = VIEWS.length, nF = FRAMES.length, nA = ANIMS.length;
    const view = VIEWS[block % nV], framing = FRAMES[Math.floor(block / nV) % nF];
    const anim = ANIMS[Math.floor(block / (nV * nF)) % nA];
    const oi = Math.min(OUTFITS.length - 1, Math.floor(block / (nV * nF * nA)));
    if (block !== T.block) {
        T.block = block;
        if (T.wardrobe) T.wardrobe.wear(OUTFITS[oi]);
        if (anim !== T.anim) { T.anim = anim; await globalThis.playVRMADefault(vrm, anim, { loop: true }); }
        vrm.scene.rotation.y = view * Math.PI / 180;
        vrm.scene.updateWorldMatrix(true, true);
        vrm.springBoneManager?.reset();
        console.log(`[turntable] block ${block}: ${OUTFITS[oi]} ${anim} ${framing} yaw ${view}`);
    }
    if (SPIN) {
        const u = (i % HOLD) / HOLD, e = u * u * (3 - 2 * u);
        vrm.scene.rotation.y = (view - 25 + 385 * e) * Math.PI / 180;
    }
    const k = H / 1.305;                                   // framings authored on a 1.305 m head height
    const shots = {
        face: [14, 1.335, 1.35, 1.33], head: [24, 1.42, 2.25, 1.36],
        chest: [24, 1.15, 2.4, 1.08], body: [26, 1.05, 4.7, 0.92],
    };
    const [fov, cy, cz, ty] = shots[framing] || shots.body;
    camera.fov = fov; camera.position.set(0, cy * k, cz * k); camera.lookAt(0, ty * k, 0);
    camera.updateProjectionMatrix();
    if (FACES.length) T.face = FACES[Math.min(FACES.length - 1, oi)] || {};   // applied in each mesh's onBeforeRender
    await T.renderer.renderAsync(T.scene, camera);
};
