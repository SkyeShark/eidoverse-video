// Claude's robot body (eidoverse/assets/vrms/claude_robot.vrm): a stock clip played through the body's hardware
// limits, the OLED face running through a few expressions and a spoken "hello", the head and the crown's petals
// following the face. A starting template for scenes that cast the robot.
//
//   python eido.py render eidoverse/examples/claude_robot.json
//
// The frame order is the recipe: the clip (mixer) -> claude_robot_dof.js's pass on the normalized bones (the
// clip's pose projected onto the machine's joints and clamped to their ranges) -> the face's expressions -> the
// head and the crown (they read those expressions) -> vrm.update -> the body set down onto the floor -> render.

const ease = (x) => x * x * (3 - 2 * x);
const smooth = (a, b, x) => ease(Math.min(1, Math.max(0, (x - a) / (b - a))));
// a 0 -> 1 -> 0 bump over [t0, t1]
const bump = (t, t0, t1) => (t <= t0 || t >= t1) ? 0 : Math.sin(Math.PI * ease((t - t0) / (t1 - t0)));

// three's mixer writes a bone only when its mixed value changed (PropertyMixer.apply), so after the pose reset in
// renderFrame a bone whose key holds would sit at rest for as long as it holds (thumbs, fingers, the hips): write
// every active binding's value from the accumulator the update just filled, where apply reads it
function writeAll(mixer) {
    const b = mixer._bindings, n = mixer._nActiveBindings, k = mixer._accuIndex + 1;
    for (let i = 0; i < n; i++) b[i].binding.setValue(b[i].buffer, k * b[i].valueSize);
}

// the white shells under a studio key read as white, not glow: the bloom only takes the face's light
globalThis._bloomParams = { ...(globalThis._bloomParams || {}), threshold: 3.2 };

// a soft studio light, made here (no HDRI file): a key softbox front left, a fill front right, a rim behind, as an
// equirect through PMREM. Row 0 is straight down; u = atan2(z, x), as three's equirect lookup reads it
function studioEnvironment() {
    const W = 256, H = 128, data = new Uint16Array(W * H * 4), half = THREE.DataUtils.toHalfFloat;
    const boxes = [[[-0.55, 0.55, 0.63], 9.0, 0.3], [[0.75, 0.25, 0.6], 1.6, 0.45], [[0.45, 0.5, -0.75], 5.0, 0.22]]
        .map(([d, k, w]) => { const n = Math.hypot(...d); return { d: d.map((x) => x / n), k, w }; });
    for (let y = 0; y < H; y++) {
        const el = ((y + 0.5) / H - 0.5) * Math.PI;
        for (let x = 0; x < W; x++) {
            const az = ((x + 0.5) / W - 0.5) * 2 * Math.PI;
            const dx = Math.cos(el) * Math.cos(az), dy = Math.sin(el), dz = Math.cos(el) * Math.sin(az);
            let v = 0.05 + 0.08 * Math.max(0, dy);
            for (const b of boxes) v += b.k * Math.exp((dx * b.d[0] + dy * b.d[1] + dz * b.d[2] - 1) / (b.w * b.w));
            const i = (y * W + x) * 4;
            data[i] = data[i + 1] = data[i + 2] = half(v);
            data[i + 3] = half(1);
        }
    }
    const tex = new THREE.DataTexture(data, W, H, THREE.RGBAFormat, THREE.HalfFloatType);
    tex.mapping = THREE.EquirectangularReflectionMapping;
    tex.minFilter = THREE.LinearFilter; tex.magFilter = THREE.LinearFilter;
    tex.needsUpdate = true;
    return THREE.pmremTexture(tex);
}

// the stock clips are a human's and play in place at a human's hips height, so the robot's feet would float or sink:
// each frame, once the pose is final, the body is set down (vertically) until the lowest vertex of either foot (every
// vertex whose strongest skin weight is a Foot or Toes bone) touches the floor at y 0
function footVertices(vrm) {
    const bones = new Set(['leftFoot', 'leftToes', 'rightFoot', 'rightToes']
        .map((n) => vrm.humanoid.getRawBoneNode(n)).filter(Boolean));
    const sets = [];
    vrm.scene.traverse((m) => {
        const si = m.isSkinnedMesh ? m.geometry.attributes.skinIndex : null, sw = si ? m.geometry.attributes.skinWeight : null;
        if (!sw) return;
        const verts = [];
        for (let i = 0; i < si.count; i++) {
            let best = 0, bw = -1;
            for (let k = 0; k < 4; k++) { const w = sw.getComponent(i, k); if (w > bw) { bw = w; best = si.getComponent(i, k); } }
            if (bones.has(m.skeleton.bones[best])) verts.push(i);
        }
        if (verts.length) sets.push({ m, verts });
    });
    return sets;
}

function setDownOnFloor(vrm, feet) {
    vrm.scene.updateMatrixWorld(true);
    const v = new THREE.Vector3();
    let lowest = Infinity;
    for (const { m, verts } of feet) {
        for (const i of verts) lowest = Math.min(lowest, m.getVertexPosition(i, v).applyMatrix4(m.matrixWorld).y);
    }
    if (!Number.isFinite(lowest)) return;
    vrm.scene.position.y -= lowest;
    vrm.scene.updateMatrixWorld(true);
}

globalThis.setup = async function () {
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.9;
    renderer.shadowMap.enabled = true;
    await renderer.init();

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x121214);
    scene.environmentNode = studioEnvironment();
    scene.environmentIntensity = 0.8;
    const key = new THREE.DirectionalLight(0xfff4e8, 2.2);
    key.position.set(-2.2, 3.2, 3.0);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    Object.assign(key.shadow.camera, { left: -1.2, right: 1.2, top: 2.0, bottom: -0.2 });
    key.shadow.bias = -0.0003;
    key.shadow.normalBias = 0.015;
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xdfe8ff, 1.0);
    rim.position.set(2.5, 2.0, -3.0);
    scene.add(rim);
    const floor = new THREE.Mesh(new THREE.CircleGeometry(6, 96),
        new THREE.MeshStandardNodeMaterial({ color: 0x2a2a2e, roughness: 0.7, metalness: 0.0 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    // the body: a VRM 1.0 like any other (VRMLoaderPlugin registered), 1.76 m tall, facing +Z
    const loader = new globalThis.GLTFLoader();
    loader.register((p) => new globalThis.VRMLoaderPlugin(p));
    const gltf = await new Promise((res, rej) =>
        loader.parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.character_vrm), '', res, rej));
    const vrm = gltf.userData.vrm;
    vrm.scene.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false; } });
    scene.add(vrm.scene);
    vrm.scene.updateMatrixWorld(true);

    // the hardware limits, set up at load BEFORE anything poses the body: the arms and hands read their hinges from
    // the joints file beside the VRM (without it the elbow falls back to built-in constants and the hands go
    // unclamped), the legs take over the hips' stages, the crown finds its twelve petals
    const DOF = await import(new URL('claude_robot_dof.js', EIDOVERSE_DIR).href);
    const joints = JSON.parse(new TextDecoder().decode(globalThis.b64toArrayBuffer(globalThis.ASSETS.joints)));
    DOF.initArmDOF(vrm, joints.hinges);
    DOF.initHandDOF(vrm, joints.hinges);
    DOF.initLegDOF(vrm);
    const crown = DOF.initCrown(vrm);

    const clip = await globalThis.playVRMADefault(vrm, 'idle');
    globalThis._robot = { vrm, clip, DOF, stats: {}, feet: footVertices(vrm),
                          camera: new THREE.PerspectiveCamera(30, WIDTH / HEIGHT, 0.05, 40) };
    globalThis._r = renderer; globalThis._s = scene; globalThis._c = globalThis._robot.camera; globalThis._vrm = vrm;
    console.log(`[claude_robot] crown petals ${crown.found}/12; foot vertices ${globalThis._robot.feet.reduce((n, s) => n + s.verts.length, 0)}`);
};

// "hello", one vowel preset at a time: each fades in and out over 60 ms, the next fading in as it fades out
const LINE = [[3.3, 3.55, 'ee'], [3.55, 3.75, 'ih'], [3.75, 4.2, 'oh']];
const ROUND = new Set(['oh', 'ou']);

function face(vrm, t) {
    const em = vrm.expressionManager;
    const set = { happy: bump(t, 1.2, 3.1), surprised: bump(t, 4.5, 6.0), relaxed: smooth(6.0, 6.6, t),
                  blink: bump(t, 0.7, 0.95) + bump(t, 6.1, 6.35) };
    // the mouth: a round shape (oh, ou) passes a heart halfway, so it is eased in quickly; the mouth's summed weight
    // stays at or under 1 (two shapes over it show the teeth and the tongue together)
    const mouth = {};
    for (const [t0, t1, v] of LINE) {
        const w = Math.min(1, Math.max(0, (t - t0 + 0.03) / 0.06)) * Math.min(1, Math.max(0, (t1 + 0.03 - t) / 0.06));
        mouth[v] = (mouth[v] || 0) + (ROUND.has(v) ? smooth(0.15, 0.6, w) : w);
    }
    const sum = Object.values(mouth).reduce((a, b) => a + b, 0);
    for (const v of ['aa', 'ih', 'ou', 'ee', 'oh']) set[v] = (mouth[v] || 0) / Math.max(1, sum);
    for (const [name, w] of Object.entries(set)) em.setValue(name, Math.min(1, w));
    // the eyes look left, then right (the look-at drives the face's look expressions; the crown leans into the look)
    vrm.lookAt.yaw = 20 * (bump(t, 6.4, 7.2) - bump(t, 7.2, 8.0));
    vrm.lookAt.pitch = 0;
}

globalThis.renderFrame = async function (t) {
    const { vrm, clip, DOF, stats, feet, camera } = globalThis._robot;
    const dt = 1 / FPS;
    // the clip, from the rest pose each frame (a bone the clip leaves alone must not keep last frame's additions).
    // three's mixer writes a bone only when its value changed, so every value it computed is written after it
    // (writeAll: no held key leaves its bone at rest), and the bones the arm pass reads are put back to the clip's
    // last pose after the reset and kept right after the mixer (the module's own guard, for loops without writeAll)
    vrm.humanoid.resetNormalizedPose();
    DOF.restoreArmPose(vrm);
    clip.mixer.update(dt);
    writeAll(clip.mixer);
    DOF.keepArmPose(vrm);
    // the hardware pass: the torso's, clavicles' and neck's turns re-homed to the joints that have them, then each
    // joint projected onto its real axes and clamped (legs, arms, hands), the legs kept clear of each other (dt is
    // the frame's real time step: the legs' pass reads its stance velocities over it)
    DOF.rehomeBody(vrm, stats);
    DOF.applyHardwareDOF(vrm, DOF.LEG_JOINTS, stats);
    DOF.applyLegClearance(vrm, stats, dt);
    DOF.applyArmDOF(vrm, stats, dt);
    DOF.applyHandDOF(vrm, stats);
    // the face, then the head and the crown, which follow its expressions at their actuators' rates
    face(vrm, t);
    DOF.applyHeadExpression(vrm, dt);
    DOF.applyCrown(vrm, dt);
    vrm.update(dt);
    setDownOnFloor(vrm, feet);

    // the camera: the whole body, then easing in to the head and shoulders
    const k = ease(Math.min(1, Math.max(0, (t - 1.2) / 4.3)));
    const dist = 3.9 + (1.6 - 3.9) * k, a = 0.35 - 0.2 * k;
    camera.position.set(Math.sin(a) * dist, 1.0 + 0.55 * k, Math.cos(a) * dist);
    camera.lookAt(0, 0.88 + 0.57 * k, 0);
    await globalThis._r.renderAsync(globalThis._s, camera);
};
// preflight: ASSETS['character_vrm'], ASSETS['joints']
