// eidoverse/examples/crowd/scene.js — the crowd tool (eidoverse/crowd.js) on the public robot body: a column of 3 files and
// 6 ranks marching on the beat (116 bpm) with a lantern hanging in every right fist, and two lines of five waving in
// canon with a hold, one of them stopped alone. Four seconds at 24 fps; the frame number drives every body.
//   python eido.py render eidoverse/examples/crowd/scene.json
//   python eido.py render eidoverse/examples/crowd/scene.json --at 2.5 --jump      # a still (film frame 61)
// CROWD_VIEW: kerb (default), close, canon, canon_close — the lens.

// a small hand lantern, its origin at the top of its wire bail (where the fist holds it), hanging below (+Y up): a
// base, a glass with a warm light in it, a cap, the bail (a tube along a half ring)
function lantern() {
    const g = new THREE.Group();
    g.name = 'lantern';
    const metal = new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(0.05, 0.05, 0.045), roughness: 0.38, metalness: 0.9 });
    const glass = new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(0.9, 0.75, 0.5), roughness: 0.2, metalness: 0.0 });
    glass.emissive = new THREE.Color(1.0, 0.62, 0.28);
    glass.emissiveIntensity = 6.0;
    const cyl = (r1, r2, y0, y1, m) => {
        const c = new THREE.Mesh(new THREE.CylinderGeometry(r2, r1, y1 - y0, 24), m);
        c.position.y = (y0 + y1) / 2;
        g.add(c);
    };
    cyl(0.062, 0.062, -0.300, -0.282, metal);                        // the base
    cyl(0.048, 0.048, -0.282, -0.150, glass);                        // the glass
    cyl(0.066, 0.020, -0.150, -0.110, metal);                        // the cap
    const pts = [];
    for (let i = 0; i <= 20; i++) { const a = Math.PI * i / 20; pts.push(new THREE.Vector3(-0.05 * Math.cos(a), -0.115 + 0.115 * Math.sin(a), 0)); }
    g.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 20, 0.0032, 8, false), metal));
    g.updateMatrixWorld(true);
    return g;
}

globalThis.setup = async function () {
    Deno.mkdirSync('work/crowd_example', { recursive: true });
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.shadowMap.enabled = true;
    await renderer.init();
    const scene = new THREE.Scene();
    // a level floor, a low warm sun, a cool sky
    const sky = new THREE.Color(0.36 * 0.55, 0.45 * 0.55, 0.62 * 0.55);
    scene.background = sky;
    scene.add(new THREE.HemisphereLight(new THREE.Color(0.36, 0.45, 0.62), new THREE.Color(0.16, 0.155, 0.15), 0.55 * Math.PI));
    const sun = new THREE.DirectionalLight(new THREE.Color(1.0, 0.86, 0.7), 3.2);
    sun.position.set(-0.696, 0.469, -0.544).multiplyScalar(40);
    sun.castShadow = true;
    sun.shadow.mapSize.set(4096, 4096);
    Object.assign(sun.shadow.camera, { left: -25, right: 25, top: 25, bottom: -25, near: 1, far: 120 });
    sun.shadow.bias = -0.0003;
    scene.add(sun, sun.target);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(160, 160), new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(0.16, 0.155, 0.15), roughness: 0.7 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);
    const camera = new THREE.PerspectiveCamera(40, WIDTH / HEIGHT, 0.05, 500);

    // the donor: the public robot body, its joints' limits set up before anything poses it. Its VRM names its licence,
    // CC BY 4.0, as its licenseUrl, which three-vrm accepts only when told to
    const { VRMMetaLoaderPlugin } = await import('npm:@pixiv/three-vrm@3.5.2');
    const accept = ['https://vrm.dev/licenses/1.0/', 'https://creativecommons.org/licenses/by/4.0/'];
    const loader = new globalThis.GLTFLoader();
    loader.register((p) => new globalThis.VRMLoaderPlugin(p, { metaPlugin: new VRMMetaLoaderPlugin(p, { acceptLicenseUrls: accept }) }));
    const gltf = await loader.parseAsync(globalThis.b64toArrayBuffer(globalThis.ASSETS.character_vrm), '');
    const vrm = gltf.userData.vrm;
    vrm.scene.updateMatrixWorld(true);
    const DOF = await import(new URL('claude_robot_dof.js', EIDOVERSE_DIR).href);
    const joints = JSON.parse(new TextDecoder().decode(globalThis.b64toArrayBuffer(globalThis.ASSETS.joints)));
    DOF.initArmDOF(vrm, joints.hinges);
    DOF.initHandDOF(vrm, joints.hinges);
    DOF.initLegDOF(vrm);
    DOF.initCrown(vrm);
    const stats = {};
    // the body's own pass on every baked pose (as eidoverse/examples/claude_robot.js plays a clip through it)
    const prePose = (v) => DOF.restoreArmPose(v);
    const perPose = (v, dt) => {
        DOF.keepArmPose(v);
        DOF.rehomeBody(v, stats);
        DOF.applyHardwareDOF(v, DOF.LEG_JOINTS, stats);
        DOF.applyLegClearance(v, stats, dt);
        DOF.applyArmDOF(v, stats, dt);
        DOF.applyHandDOF(v, stats);
        DOF.applyHeadExpression(v, dt);
        DOF.applyCrown(v, dt);
    };
    const clip = async (key) => {
        const l = new globalThis.GLTFLoader();
        l.register((p) => new globalThis.VRMAnimationLoaderPlugin(p));
        const g = await l.parseAsync(globalThis.b64toArrayBuffer(globalThis.ASSETS[key]), '');
        const c = globalThis.createVRMAnimationClip(g.userData.vrmAnimations[0], vrm);
        c.name = key;
        return c;
    };
    const CROWD = await import(new URL('crowd.js', EIDOVERSE_DIR).href);
    const lamp = CROWD.heldProp(THREE, lantern(), { bone: 'rightHand', grip: 'fist', hang: true, name: 'lantern' });
    const fps = FPS;
    // ONE stride on the beat, the lantern in the right fist, the face happy
    const cyc = await CROWD.strideCycle(THREE, vrm, await clip('walk'), { fps, bpm: 116, posesPerFrame: 2, props: [lamp], curl: { right: 80 },
        face: { happy: 1 }, prePose, perPose, name: 'march' });
    // the column: 3 files of 6 ranks marching toward +X, the head's middle at the origin on the ref frame
    const pts = CROWD.formation({ files: 3, ranks: 6, interval: 0.85, distance: 1.05, origin: [0, 0, 0], heading: 90,
        jitter: { lateral: 0.03, along: 0.05, phase: 0.03, seed: 11 } });
    const column = CROWD.crowd(THREE, 'column', pts, CROWD.columnGroup(cyc, { refFrame: 1, show: [10, 4000] }));
    scene.add(column.group);
    // the same donor, a one-shot clip: two lines of five waving in canon, a hold, one body stopped alone on frame 50
    DOF.resetArmDOF?.(vrm);
    const wave = await CROWD.onceFlipbook(THREE, vrm, await clip('wave'), { fps, every: 2, prePose, perPose, name: 'wave' });
    const g = CROWD.grid({ lines: 2, units: 5, linePitch: 2.2, unitPitch: 1.25, origin: [0, 0, -14], heading: 0 });
    const stops = g.map((_, i) => (i === 3 ? 50 : null));
    const canon = CROWD.crowd(THREE, 'canon', g, CROWD.onceGroup(wave, { hold: [64, 24] }), { starts: CROWD.canonStarts(g, { first: 12, stepLine: 10, stepUnit: 4 }), stops });
    scene.add(canon.group);
    // the checks: the feet stay planted through 48 frames; every point shows the pose its clock asks for
    const fs = [0, 10].map((p) => CROWD.feetSlide(THREE, column, [...Array(48).keys()].map((k) => 40 + k), p));
    console.log(`[crowd example] the stride: ${JSON.stringify(cyc.record)}`);
    console.log(`[crowd example] the feet: ${JSON.stringify(fs)}`);
    console.log(`[crowd example] the canon on frames 30, 63, 70, 87, 100: ${[30, 63, 70, 87, 100].map((f) => CROWD.shownPoses(canon, f).join(' ')).join(' | ')}`);
    console.log(`[crowd example] the body stopped on 50 holds pose ${canon.poseOf(3, 51).pose} on 51 and ${canon.poseOf(3, 110).pose} on 110`);
    Object.assign(globalThis, { _r: renderer, _s: scene, _c: camera, _crowds: [column, canon], _sun: sun, _column: column, _canon: canon,
        _view: Deno.env.get('CROWD_VIEW') || 'kerb' });
};

// a lens, in Blender's own numbers (a 36 mm sensor's horizontal field)
function aim(camera, pos, at, lens) {
    camera.position.copy(pos);
    camera.fov = 2 * Math.atan(Math.tan(Math.atan(18 / lens)) / camera.aspect) * 180 / Math.PI;
    camera.updateProjectionMatrix();
    camera.lookAt(at);
}

globalThis.renderFrame = async function (t, frameIndex) {
    const f = frameIndex + 1;                                        // the film's frame number (the first is 1, as Blender counts)
    for (const c of globalThis._crowds) c.update(f);
    const cam = globalThis._c, view = globalThis._view;
    const local = (C, i, fr, p) => new THREE.Vector3(...p).applyMatrix4(C.frameOf(i, fr));
    if (view === 'kerb' || view === 'close') {
        const mid = globalThis._column.frameOf(1, f);                // the head rank's middle file
        const hx = mid.elements[12];
        if (view === 'kerb') aim(cam, new THREE.Vector3(hx + 4.6, 1.55, 4.2), new THREE.Vector3(hx - 2.2, 0.95, 0), 35);
        else aim(cam, local(globalThis._column, 1, f, [0.9, 1.35, 1.9]), local(globalThis._column, 1, f, [-0.12, 0.95, 0.15]), 50);
    } else if (view === 'canon') aim(cam, new THREE.Vector3(6.8, 3.2, -4.6), new THREE.Vector3(0, 0.9, -13), 35);
    else aim(cam, local(globalThis._canon, 0, f, [0.6, 1.45, 2.6]), local(globalThis._canon, 0, f, [0, 1.2, 0]), 50);
    const s = globalThis._sun;
    s.target.position.set(cam.position.x, 0, cam.position.z - 6);
    s.position.copy(s.target.position).add(new THREE.Vector3(-0.696, 0.469, -0.544).multiplyScalar(40));
    s.target.updateMatrixWorld();
    await globalThis._r.renderAsync(globalThis._s, cam);
};
