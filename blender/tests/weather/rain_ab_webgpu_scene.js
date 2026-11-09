// rain_ab_webgpu_scene.js: the WebGPU half of the rain A/B. eidoverse's own makeSky (sky_worlds.js, with its weather
// and the repo's rain_streak.png) over a plain street of grey blocks, one frame per weather state, each held from t = 0
// (the sky's drift is skyWind x t, so a state set at the frame is the state held all along). rain_ab_blender.py
// renders the same blocks, camera, hour and states in EEVEE with eidoblend.weather (wet_model 'eidoverse',
// rain_cells 'column': eidoverse's formulas), so the two frames can be laid side by side.
//
//   cd <worktree> && RENDER_CODEC=libx264 RENDER_CQ=1 deno run --allow-all --unstable-webgpu --no-lock \
//       eidoverse/render_scene.mjs blender/tests/weather/rain_ab_webgpu.json
//
// Env: RAB_STATES (JSON [[state, seconds], ...]; a seconds of 0 picks the first moment after 40 s at which the
// camera's own column rains: the gate >= 0.95), RAB_HOURS (16). Writes blender/tests/weather/out/verify/rain_ab/
// webgpu_at<t>.png (two per state, in RAB_STATES order: the frame, then the same frame with the rain hidden) and
// rain_ab_webgpu.json (each frame's moment and values).
const ENV = (k, d) => (globalThis.Deno?.env.get(k) ?? d);
const STATES = JSON.parse(ENV('RAB_STATES', '[["cyclone",60],["storm",0],["rain",0],["darkstorm",60]]'));
const HOURS = Number(ENV('RAB_HOURS', '16'));
const OUT = 'blender/tests/weather/out/verify/rain_ab/';

// the blocks, in three's axes (x right, y up, z toward the camera): two rows of buildings either side of a 16 m
// street and a far wall; rain_ab_blender.py builds the same list rotated into Blender's Z-up
globalThis.RAB_BLOCKS = (() => {
    const out = [];
    for (let k = 0; k < 9; k++) {
        const z0 = -6 - k * 13, z1 = z0 - 11;
        out.push({ x0: -22, x1: -8, y1: 12 + (k % 3) * 4, z0: z1, z1: z0, albedo: [0.30, 0.29, 0.27] });
        out.push({ x0: 8, x1: 22, y1: 14 + ((k + 1) % 3) * 4, z0: z1, z1: z0, albedo: [0.26, 0.27, 0.29] });
    }
    out.push({ x0: -30, x1: 30, y1: 26, z0: -136, z1: -128, albedo: [0.28, 0.28, 0.28] });
    return out;
})();

globalThis.setup = async function () {
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    await renderer.init();
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, WIDTH / HEIGHT, 0.1, 60000);
    camera.position.set(0, 1.4, 0);
    camera.lookAt(0, 3.2, -40);
    camera.updateMatrixWorld();
    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;

    // node materials, so the weather's wrapScene wets them (it wraps NodeMaterials only)
    const mat = (rgb, rough) => {
        const m = new THREE.MeshStandardNodeMaterial({ roughness: rough, metalness: 0 });
        m.color.setRGB(rgb[0], rgb[1], rgb[2], THREE.LinearSRGBColorSpace);
        return m;
    };
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), mat([0.07, 0.07, 0.075], 0.75));
    ground.rotation.x = -Math.PI / 2;
    ground.name = 'ground';
    scene.add(ground);
    for (const [i, b] of RAB_BLOCKS.entries()) {
        const box = new THREE.Mesh(new THREE.BoxGeometry(b.x1 - b.x0, b.y1, b.z1 - b.z0), mat(b.albedo, 0.85));
        box.position.set((b.x0 + b.x1) / 2, b.y1 / 2, (b.z0 + b.z1) / 2);
        box.name = 'block_' + i;
        scene.add(box);
    }
    const sun = new THREE.DirectionalLight(0xffffff, 3.0);
    const hemi = new THREE.HemisphereLight(0xbfd4ff, 0x4a5a3a, 0.6);
    scene.add(sun, sun.target, hemi);
    eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
    const sky = await makeSky({ scene, camera, renderer, sun, hemi, world: 'earth', hours: HOURS,
                                weather: STATES[0][0], audio: false });
    const S = sky._internals.sky, wx = sky._internals.wx;
    // each state's moment: the given seconds, or the first after 40 s at which the camera's own column rains under
    // both drift conventions: this engine's (the field sampled at p + skyWind t) and the Blender sky's (Eanpa's: at
    // p - the integrated wind; sky-weather.md, Wind direction), so the two renders rain at the camera alike
    const sstep = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
    const plan = STATES.map(([name, secs]) => {
        wx.setWeather(name, 1);
        const w = wx.WEATHER[name];
        const gateAt = (T, sign = 1) => {
            S.uniforms.time.value = T;
            const wv = S.uniforms.skyWind.value;
            const k = sign > 0 ? 0 : 2 * T;              // weatherAt(p - 2 W T) = the field at p - W T
            const cov = S.weatherAt(camera.position.x - wv.x * k, camera.position.z - wv.z * k);
            const g = sstep(w.cellLo ?? 0.9, w.cellHi ?? 1.45, cov);
            const c = Math.min(1, Math.max(0, Number(S.uniforms.stormCanopy.value) || 0));
            return g + (1 - g) * c;
        };
        let T = Number(secs);
        if (!(T > 0)) {
            T = 40;
            while (T < 600 && Math.min(gateAt(T), gateAt(T, -1)) < 0.95) T += 0.5;
        }
        return { name, T, gate: gateAt(T), gateBlenderDrift: gateAt(T, -1) };
    });
    console.log('[rain_ab] plan ' + JSON.stringify(plan));
    globalThis._rab = { renderer, scene, camera, sky, S, wx, plan, records: [] };
};

// two frames per state: even frames with the rain, odd frames the same moment with the streaks and splashes hidden
// (their difference is the rain alone: rain_ab_blender.py measures it in both renderers)
globalThis.renderFrame = async function (t, i) {
    const m = globalThis._rab;
    const p = m.plan[Math.min(i >> 1, m.plan.length - 1)];
    const rainOn = (i % 2) === 0;
    m.sky.setWeather(p.name, 1);
    m.sky.update(p.T);
    if (rainOn) {
        await m.sky.bakeEnv();
        m.sky.update(p.T);
    }
    const [rainInst, splashInst] = m.wx.pipelineWarmupObjects();
    const vis = [rainInst.visible, splashInst.visible];
    if (!rainOn) { rainInst.visible = false; splashInst.visible = false; }
    const u = m.wx.uniforms;
    const rec = {
        name: p.name, T: p.T, gate: p.gate, gateBlenderDrift: p.gateBlenderDrift, frame: i, rain: rainOn,
        rainVisible: vis[0],
        rainK: u.rainK.value, denseA: u.denseA.value, rainLight: u.rainLight.value,
        rainColor: [u.rainColor.value.x, u.rainColor.value.y, u.rainColor.value.z],
        streakLen: u.streakLen.value, fallMul: u.fallMul.value,
        windVec: [u.windVec.value.x, u.windVec.value.y, u.windVec.value.z],
        wetness: u.wetness.value, cellLo: u.cellLo.value, cellHi: u.cellHi.value,
        stormCanopy: Number(m.S.uniforms.stormCanopy.value), flash: m.wx.diagnostics.lightning.flash,
        weatherAtCamera: m.S.weatherAt(m.camera.position.x, m.camera.position.z),
    };
    m.records.push(rec);
    console.log('[rain_ab] ' + JSON.stringify(rec));
    await m.renderer.renderAsync(m.scene, m.camera);
    rainInst.visible = vis[0];
    splashInst.visible = vis[1];
};

globalThis.cleanup = async function () {
    const m = globalThis._rab;
    Deno.mkdirSync(OUT, { recursive: true });
    Deno.writeTextFileSync(OUT + 'rain_ab_webgpu.json', JSON.stringify({ hours: HOURS, blocks: RAB_BLOCKS,
        camera: { position: [0, 1.4, 0], lookAt: [0, 3.2, -40], fovY: 50 }, records: m.records }, null, 1));
};
