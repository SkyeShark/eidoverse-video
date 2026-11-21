// Each SeedThree individual's billboard beside the level it takes over from, at the switch distance, under the sky
// (SURFACING_DESIGN.md 4.4: "billboards are matched to LOD2 before they are used"; 5.4 package 4 item 2's boards;
// the Blender edition measures the same with blender/tests/terrain/plants/match_billboards.py and keeps the gains in
// plant_instances.py BILLBOARD_GAIN): per individual of the given ecotopes, two plants of it on flat grey ground, one
// just inside its card distance (its card level, or its full level where hero_m reaches as far: the broadleaves) and
// one just beyond (its billboard, build/plant_instances.js' material with the measured gain), side by side; their
// mean colour (CIELAB, over the pixels each plant covers) and their silhouette areas compared. The gains were
// measured on Blender's renders; here they are checked, not tuned (the design's ΔE 3 and 10 % are reported).
//
//     EIDO_GPU_WRAP='<the GPU queue>' deno run --config deno.json --frozen --allow-all \
//         eidoverse/terrain/tests/plants/billboards.mjs [--ecotopes alpine,desert,...]
//
// Writes tests/out/plants/billboards/<species>_<seed>.png (the pair) and billboards.json.

import * as S from './_plants.mjs';
import * as E from '../../build/ecotopes.js';

const A = S.argsOf();
const T = new S.C.Checks('plants: billboards beside their levels at the switch distance');
// the ecotopes the design's six views take (recipe[:place], as ecotopes.get('auto', recipe, place) resolves them)
const want = A.list('--recipes', ['real_place:lauterbrunnen', 'canyon', 'caldera', 'fluvial_range', 'dunes']);
const out = `${S.W.out('plants')}/billboards`;
const work = `${out}/_scenes`;
Deno.mkdirSync(work, { recursive: true });
const W = 960, H = 540;
const cases = [];
for (const rp of want) {
    const [recipe, place] = rp.split(':');
    const eco = E.get('auto', recipe, place ?? null, null);
    const name = eco.name ?? recipe;
    for (const s of eco.species) {
        const [kind, id, opts, seeds] = s.source;
        if (kind !== 'seedthree') continue;
        if (cases.some((c) => c.id === id && JSON.stringify(c.dials) === JSON.stringify(opts) && c.seed === seeds[0])) continue;
        cases.push({ ecotope: name, species: s.name, kind: s.kind, id, dials: opts, seed: seeds[0], size_m: s.size_m, lod: s.lod,
            sink: s.sink, foot_m: s.foot_m, crown_m: s.crown_m, core_m: s.core_m });
    }
}
const spec = { cases, W, H, result: `${work}/result.json`, exposureEv: -0.5, hours: 15.5 };
try { Deno.removeSync(spec.result); } catch (_e) { /* none yet */ }

const script = `// The plants package's billboard check (eidoverse/terrain/tests/plants/billboards.mjs writes this file).
globalThis.setup = async function () {
    const V = ${JSON.stringify(spec)};
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE, reversedDepthBuffer: true });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = Math.pow(2, V.exposureEv);
    await renderer.init();
    globalThis._r = renderer;
    globalThis._noAutoEnhance = true;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(20, WIDTH / HEIGHT, 1, 20000);
    globalThis._s = scene;
    globalThis._c = camera;
    const sun = new THREE.DirectionalLight(0xffffff, 1.0);
    scene.add(sun, sun.target);
    globalThis.EANPA_NO_MRT = true;
    eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
    const sky = await makeSky({ scene, camera, renderer, world: 'earth', hours: V.hours, clouds: 'clear', weather: null, sun, audio: false });
    sky.update(0);
    await sky.bakeEnv();
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(4000, 4000), new THREE.MeshStandardNodeMaterial({ color: 0x5a5a5a, roughness: 1 }));
    ground.rotation.x = -Math.PI / 2;
    scene.add(ground);
    const G = await import(EIDOVERSE_DIR + 'terrain/core/gpu.js');
    globalThis._b = { V, sky, sun, R: await G.init({ renderer }), PL: await import(EIDOVERSE_DIR + 'terrain/build/plants.js'),
        PI: await import(EIDOVERSE_DIR + 'terrain/build/plant_instances.js'), results: [], cur: null };
};

// two spots of one individual, d1 and d2 metres off the camera, 2 x the plant's width apart across the view
function pairSpots(PL, c, d1, d2, gap) {
    const rec = new Float32Array(24);
    const put = (k, x, y) => rec.set([x, y, 0, 0.3, 1.0, 1.0, 0.5, 0, 0, 1, 0, 0], 12 * k);
    put(0, -gap / 2, d1);
    put(1, gap / 2, d2);
    const entry = { name: c.species, kind: c.kind, source: { seedthree: c.id, dials: c.dials, seeds: [c.seed] }, size_m: c.size_m,
        core_m: c.core_m, crown_m: c.crown_m, foot_m: c.foot_m, sink: c.sink, lod: c.lod, count: 2, fields: [...PL.FIELDS] };
    return new PL.PlantSpots({ format: PL.FORMAT, focus: [[0, 0]], seed: 0, ecotope: 'test', terrain: null, species: [entry] },
        [entry], { [c.species]: rec });
}

globalThis.renderFrame = async function (tt) {
    const B = globalThis._b;
    const k = Math.max(0, Math.min(B.V.cases.length - 1, Math.round(tt)));
    const r = globalThis._r, camera = globalThis._c, scene = globalThis._s;
    if (!B.cur || B.cur.k !== k) {
        if (B.cur) { B.cur.plants.dispose(); }
        const c = B.V.cases[k];
        // the card distance this species takes (no stand round the camera: its billboard_m, or a shrub's 4 pixels)
        const probe = pairSpots(B.PL, c, 50, 60, 10);
        const p0 = await B.PI.instancePlants(probe, null, { renderer: r, R: B.R, log: null });
        const cardM = p0.species[c.species].card_m;
        p0.dispose();
        const spots = pairSpots(B.PL, c, cardM * 0.985, cardM * 1.015, 1.2 * c.size_m[1]);
        const plants = await B.PI.instancePlants(spots, null, { renderer: r, R: B.R, log: (m) => console.log(m) });
        scene.add(plants.group);
        B.cur = { k, c, plants, cardM, done: false };
    }
    const { c, plants, cardM } = B.cur;
    camera.position.set(0, 1.7, 0);
    camera.lookAt(0, 0.5 * c.size_m[1], -cardM);
    camera.fov = 2.6 * Math.atan(c.size_m[1] / cardM) * 180 / Math.PI;
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
    const s = B.sky.sunDir;
    B.sun.position.set(s.x * 1000, s.y * 1000, s.z * 1000);
    B.sun.target.position.set(0, 0, -cardM);
    B.sun.updateMatrixWorld(true);
    B.sun.target.updateMatrixWorld(true);
    B.sky.update(0);
    await plants.bindSun(s);
    plants.update(camera);
    if (!B.cur.done) {
        B.cur.done = true;
        const rt = new THREE.RenderTarget(WIDTH, HEIGHT, { samples: 4 });
        const px = [];
        for (const on of [true, false]) {
            plants.group.visible = on;
            r.setRenderTarget(rt);
            await r.renderAsync(scene, camera);
            px.push(await r.readRenderTargetPixelsAsync(rt, 0, 0, WIDTH, HEIGHT));
        }
        r.setRenderTarget(null);
        plants.group.visible = true;
        rt.dispose();
        // per half of the frame: the pixels the plant changes, their mean colour (sRGB -> linear -> CIELAB), and count
        const lin = (v) => { const x = v / 255; return x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
        const lab = (rgb) => {
            const [R1, G1, B1] = rgb;
            let X = 0.4124 * R1 + 0.3576 * G1 + 0.1805 * B1, Y = 0.2126 * R1 + 0.7152 * G1 + 0.0722 * B1, Z = 0.0193 * R1 + 0.1192 * G1 + 0.9505 * B1;
            X /= 0.95047; Z /= 1.08883;
            const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
            return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))];
        };
        const half = [];
        for (const side of [0, 1]) {
            let n = 0; const acc = [0, 0, 0];
            for (let y = 0; y < HEIGHT; y++) {
                for (let x = side ? WIDTH / 2 : 0; x < (side ? WIDTH : WIDTH / 2); x++) {
                    const i = 4 * (y * WIDTH + x);
                    const d = Math.abs(px[0][i] - px[1][i]) + Math.abs(px[0][i + 1] - px[1][i + 1]) + Math.abs(px[0][i + 2] - px[1][i + 2]);
                    if (d <= 12) continue;
                    n++;
                    for (let ch = 0; ch < 3; ch++) acc[ch] += lin(px[0][i + ch]);
                }
            }
            half.push({ n, lab: n ? lab(acc.map((v) => v / n)) : null });
        }
        const [a, b] = half;
        const dE = a.lab && b.lab ? Math.hypot(a.lab[0] - b.lab[0], a.lab[1] - b.lab[1], a.lab[2] - b.lab[2]) : null;
        B.results.push({ ...c, card_m: cardM, level: { area: a.n, lab: a.lab }, billboard: { area: b.n, lab: b.lab }, dE,
            area_ratio: a.n ? b.n / a.n : null });
        Deno.writeTextFileSync(B.V.result, JSON.stringify(B.results, null, 1));
    }
    await r.renderAsync(scene, camera);
};
`;
const scriptPath = `${work}/billboards.js`, config = `${work}/billboards.json`, video = `${work}/billboards.mp4`;
Deno.writeTextFileSync(scriptPath, script);
const rel = (p) => {
    const a = S.W.norm(p), r = S.W.REPO + '/';
    return a.startsWith(r) ? a.slice(r.length) : a;
};
Deno.writeTextFileSync(config, JSON.stringify({ width: W, height: H, fps: 1, duration: cases.length, script: rel(scriptPath),
    outputVideo: rel(video), capture: { at: cases.map((_, k) => k), jump: true } }, null, 1));
const argv = S.W.gpuArgv([S.W.norm(Deno.execPath()), 'run', '--allow-all', '--unstable-webgpu', '--node-modules-dir=auto',
    'eidoverse/render_scene.mjs', rel(config)], { cwd: S.W.REPO });
const log = `${work}/billboards.log`;
const code = await S.W.run(argv, { cwd: S.W.REPO, log, env: { ...Deno.env.toObject(), RENDER_CODEC: 'libx264', RENDER_CQ: '0' } });
T.ok('the render job ran', code === 0, `exit ${code}; ${log}`);
const res = S.W.exists(spec.result) ? JSON.parse(Deno.readTextFileSync(spec.result)) : [];
for (const [k, r] of res.entries()) {
    const tag = `${r.id} ${r.seed} ${JSON.stringify(r.dials)}`;
    T.ok(`${r.ecotope} / ${r.species} (${tag}): its billboard's mean colour beside its level at ${r.card_m.toFixed(0)} m (the design's ΔE 3)`,
        r.dE !== null && r.dE <= 3.0, `ΔE ${r.dE === null ? 'n/a' : r.dE.toFixed(2)}; level L*a*b* ${JSON.stringify(r.level.lab?.map((v) => +v.toFixed(1)))}, ` +
        `billboard ${JSON.stringify(r.billboard.lab?.map((v) => +v.toFixed(1)))}`);
    T.ok(`${r.ecotope} / ${r.species} (${tag}): its silhouette's area within 10 % of its level's`, r.area_ratio !== null &&
        Math.abs(r.area_ratio - 1) <= 0.1, `${r.billboard.area} / ${r.level.area} pixels (${r.area_ratio === null ? 'n/a' : r.area_ratio.toFixed(3)})`);
    const shot = `${work}/billboards_at${k.toFixed(2)}s.png`;
    if (S.W.exists(shot)) Deno.copyFileSync(shot, `${out}/${r.id}_${r.seed}.png`);
}
Deno.exit(S.finish(T, 'billboards', { results: res }));
