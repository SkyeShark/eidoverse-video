// A probe for the lead, not a port: the blade grasses the plant layer strokes through createFlora
// (eidoverse/vegetation.js), seen from the eye views' height under the views' light, as createFlora shades them (its
// light-gather normals: every blade lit as the ground plane, world up) and as the Blender edition's flora shades them
// by default (blender/eidoblend/flora/field.py and nodes.py at f9fba8c: create_flora(normals=None) gives a blade
// species 'true' normals, the cards' own, two-sided; its roughness x BLADE_ROUGH 1.6; the specular damped as the view
// grazes the card, x (1 - facing^3); faded where the shading normal turns from the camera (SPEC_FACING); the normal
// bent across the blade by its 'across' coordinate (BLADE_CURL 1.4)). The Blender flora's own comment names what its
// default avoids: "gather's up normals turn fine blades into grazing mirrors under a low sun: white specular streaks,
// a sky-coloured haze from a low camera". plant_instances.py calls create_flora with those defaults; createFlora has no
// such options, so the port's meadow, bunch and dune grasses keep the light-gather shading. Frame 0: createFlora as it
// is; frame 1: the same strokes with the Blender flora's blade shading set on their materials here (test code). Left:
// meadow grass (the alpine ecotope's: grass, green, 0.34 m); right: dune grass (galleta_dry, gain 2.2 2.1 1.5).
//
//     EIDO_GPU_WRAP='<the GPU queue>' deno run --config deno.json --frozen --allow-all \
//         eidoverse/terrain/tests/plants/blade_shading.mjs
//
// Writes tests/out/plants/blade_shading/{gather,blender}.png and blade_shading.json (each half's mean colour, CIELAB).

import * as S from './_plants.mjs';

const out = `${S.W.out('plants')}/blade_shading`;
const work = `${out}/_scenes`;
Deno.mkdirSync(work, { recursive: true });
const W = 960, H = 540;
const spec = { W, H, result: `${work}/result.json`, exposureEv: -0.5, hours: 15.5, sunLeftDeg: 70.0, eye: 1.7, pitchDeg: -6.0,
    bladeRough: 1.6, bladeCurl: 1.4 };
try { Deno.removeSync(spec.result); } catch (_e) { /* none yet */ }

const script = `// The plants package's blade-shading probe (eidoverse/terrain/tests/plants/blade_shading.mjs writes this file).
globalThis.setup = async function () {
    const V = ${JSON.stringify(spec)};
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE, reversedDepthBuffer: true });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = Math.pow(2, V.exposureEv);
    renderer.shadowMap.enabled = true;
    await renderer.init();
    globalThis._r = renderer;
    globalThis._noAutoEnhance = true;
    const TSL = THREE.TSL ?? THREE;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, WIDTH / HEIGHT, 0.1, 20000);
    globalThis._s = scene;
    globalThis._c = camera;
    const sun = new THREE.DirectionalLight(0xffffff, 1.0);
    scene.add(sun, sun.target);
    globalThis.EANPA_NO_MRT = true;
    eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
    const sky = await makeSky({ scene, camera, renderer, world: 'earth', hours: V.hours, clouds: 'cumulus', weather: null, sun, audio: false });
    sky.update(0);
    await sky.bakeEnv();
    // the view: the sun 70 degrees left of it (the review's light), the eye 1.7 m over flat ground, 6 degrees down
    const s = sky.sunDir;
    const az = Math.atan2(-s.z, s.x) - V.sunLeftDeg * Math.PI / 180;
    const ux = Math.cos(az), uz = -Math.sin(az), rx = Math.sin(az), rz = Math.cos(az);
    camera.position.set(0, V.eye, 0);
    const pd = Math.tan(V.pitchDeg * Math.PI / 180);
    camera.lookAt(ux, V.eye + pd, uz);
    camera.updateMatrixWorld(true);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    const sc = sun.shadow.camera;
    sc.left = -40; sc.right = 40; sc.top = 40; sc.bottom = -40; sc.near = -200; sc.far = 200;
    sc.updateProjectionMatrix();
    sun.target.position.set(20 * ux, 0, 20 * uz);
    sun.position.copy(sun.target.position).add(new THREE.Vector3(s.x, s.y, s.z).multiplyScalar(100));
    sun.target.updateMatrixWorld(true);
    sun.updateMatrixWorld(true);
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(4000, 4000), new THREE.MeshStandardNodeMaterial({ color: 0x5a5146, roughness: 1 }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);
    // two stands per shading, side by side across the view (left: meadow grass; right: dune grass)
    const at = (side, fwd) => [fwd * ux + side * rx, fwd * uz + side * rz];
    const sunDir = [s.x, s.y, s.z];
    const stroke = async (o, side) => {
        const c = at(side * 9, 16);
        return await createFlora({ ...o, center: c, width: 18, depth: 30, seed: 7, wind: 0, sunDir, heightFn: () => 0 });
    };
    const sets = {};
    for (const mode of ['gather', 'blender']) {
        const a = await stroke({ species: 'grass', color: 'green', height: 0.34 }, -1);
        const b = await stroke({ species: 'galleta_dry' }, 1);
        for (const f of [b]) {
            const g = TSL.vec3(2.2, 2.1, 1.5);
            const c = TSL.vec4(f.material.colorNode);
            f.material.colorNode = TSL.vec4(c.rgb.mul(g), c.a);
            if (f.material.thicknessColorNode) f.material.thicknessColorNode = TSL.vec3(f.material.thicknessColorNode).mul(g);
        }
        if (mode === 'blender') for (const f of [a, b]) bladeShading(f, TSL, V);
        for (const f of [a, b]) { f.material.needsUpdate = true; scene.add(f.mesh); }
        sets[mode] = [a, b];
    }
    globalThis._p = { V, sets, done: {} };
};

// the Blender flora's blade shading (nodes.leaf_material with normal_mode 'mesh', grazing_damp, SPEC_FACING, curl) on
// a createFlora blade stroke: the cards' own normals back (bunchGeometry blends them up), two-sided; the roughness x
// BLADE_ROUGH; the specular x (1 - facing^3) x smoothstep(0, 0.1, N.V); the normal bent across the blade (u runs edge
// to edge, the vertices alternate -1 / +1 across it) along the instance's turned UV tangent
function bladeShading(f, T, V) {
    const g = f.mesh.geometry;
    g.computeVertexNormals();
    g.computeTangents();
    const m = f.material;
    const yaw = T.attribute('aPosRot').w;
    const cR = T.cos(yaw), sR = T.sin(yaw);
    const tl = T.attribute('tangent').xyz;
    const tV = T.modelViewMatrix.mul(T.vec4(tl.x.mul(cR).sub(tl.z.mul(sR)), tl.y, tl.x.mul(sR).add(tl.z.mul(cR)), 0.0)).xyz.normalize();
    const across = T.varying(T.float(T.vertexIndex.mod(2)).mul(2.0).sub(1.0));
    const n = T.normalize(T.vec3(m.normalNode).mul(T.faceDirection).add(tV.mul(across.mul(V.bladeCurl))));
    m.normalNode = n;
    if (m.roughnessNode) m.roughnessNode = T.float(m.roughnessNode).mul(V.bladeRough);
    else m.roughness = Math.min(1, m.roughness * V.bladeRough);
    const ndv = T.dot(n, T.positionView.negate().normalize());
    const facing = T.float(1.0).sub(T.abs(ndv));
    m.specularIntensityNode = T.float(1.0).sub(facing.mul(facing).mul(facing)).mul(T.smoothstep(0.0, 0.1, ndv));
}

const toLin = (x) => (x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
function labOf(m) {
    const [R1, G1, B1] = m;
    const X = (0.4124 * R1 + 0.3576 * G1 + 0.1805 * B1) / 0.95047, Y = 0.2126 * R1 + 0.7152 * G1 + 0.0722 * B1;
    const Z = (0.0193 * R1 + 0.1192 * G1 + 0.9505 * B1) / 1.08883;
    const f = (t) => (t > (6 / 29) ** 3 ? Math.cbrt(Math.max(t, 0)) : t / (3 * (6 / 29) ** 2) + 4 / 29);
    return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))].map((v) => +v.toFixed(2));
}

globalThis.renderFrame = async function (tt) {
    const P = globalThis._p, r = globalThis._r, scene = globalThis._s, camera = globalThis._c;
    const mode = Math.round(tt) >= 1 ? 'blender' : 'gather';
    for (const [k, fs] of Object.entries(P.sets)) for (const f of fs) f.mesh.visible = k === mode;
    if (!P.done[mode]) {
        P.done[mode] = true;
        const rt = new THREE.RenderTarget(WIDTH, HEIGHT);
        r.setOutputRenderTarget(rt);
        await r.renderAsync(scene, camera);
        const d = await r.readRenderTargetPixelsAsync(rt, 0, 0, WIDTH, HEIGHT);
        r.setOutputRenderTarget(null);
        rt.dispose();
        // the lower third of each half: the near stands
        const half = [];
        for (const side of [0, 1]) {
            const acc = [0, 0, 0];
            let n = 0;
            for (let y = Math.round(HEIGHT * 2 / 3); y < HEIGHT; y++) {
                for (let x = side * WIDTH / 2 + 40; x < (side + 1) * WIDTH / 2 - 40; x++) {
                    const i = 4 * (y * WIDTH + x);
                    for (let c = 0; c < 3; c++) acc[c] += toLin(d[i + c] / 255);
                    n++;
                }
            }
            half.push(labOf(acc.map((v) => v / n)));
        }
        let res = {};
        try { res = JSON.parse(Deno.readTextFileSync(P.V.result)); } catch (_e) { /* the first */ }
        res[mode] = { meadow_grass_lab: half[0], dune_grass_lab: half[1] };
        Deno.writeTextFileSync(P.V.result, JSON.stringify(res, null, 1));
    }
    await r.renderAsync(scene, camera);
};
`;
const scriptPath = `${work}/blade_shading.js`, config = `${work}/blade_shading.json`, video = `${work}/blade_shading.mp4`;
Deno.writeTextFileSync(scriptPath, script);
const rel = (p) => {
    const a = S.W.norm(p), r = S.W.REPO + '/';
    return a.startsWith(r) ? a.slice(r.length) : a;
};
Deno.writeTextFileSync(config, JSON.stringify({ width: W, height: H, fps: 1, duration: 2, script: rel(scriptPath),
    outputVideo: rel(video), capture: { at: [0, 1], jump: true } }, null, 1));
const argv = S.W.gpuArgv([S.W.norm(Deno.execPath()), 'run', '--allow-all', '--unstable-webgpu', '--node-modules-dir=auto',
    'eidoverse/render_scene.mjs', rel(config)], { cwd: S.W.REPO });
const log = `${work}/blade_shading.log`;
const code = await S.W.run(argv, { cwd: S.W.REPO, log, env: { ...Deno.env.toObject(), RENDER_CODEC: 'libx264', RENDER_CQ: '0' } });
const res = S.W.exists(spec.result) ? JSON.parse(Deno.readTextFileSync(spec.result)) : {};
['gather', 'blender'].forEach((m, k) => {
    const shot = `${work}/blade_shading_at${k.toFixed(2)}s.png`;
    if (S.W.exists(shot)) Deno.copyFileSync(shot, `${out}/${m}.png`);
});
Deno.writeTextFileSync(`${out}/blade_shading.json`, JSON.stringify({ exit: code, ...res }, null, 1));
console.log(`[blade_shading] exit ${code}: ${JSON.stringify(res)}`);
Deno.exit(code);
