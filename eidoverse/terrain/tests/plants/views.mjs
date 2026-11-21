// The plants seen from the design's acceptance views (SURFACING_DESIGN.md 5.4 package 4 item 2; PORT_PLAN.md 8.2 row
// P15: "renders beside the photographs at the design's six views, objects near and canopy far"), rendered by this
// edition's renderer as the Blender edition's review renders them (blender/tests/terrain/surfacing/review_views.py
// --plants, its final renders out/surfacing/review/<recipe>/<view>_final2.png): each view's terrain (the review's
// saved one: --snap's <recipe>_<view>[_j].npz, a view without a focus the judge's out/surfacing_judge/terrains), the
// port's surface bake of it with the palette's options, the plants planned as make_terrain plans them (an eye view's
// round its camera, an aerial's round its aim, the views built together along their points; the vista discs, the
// standing camera's disc, the flats), their cover added to the data before the palette bake, the material
// (build/surfacing.js applySurface), the rocks (build/dressing.js, round the terrain's focus), the plants instanced
// for a still shot (build/plant_instances.js) with the sun bound, the review's light (make_sky's earth at 15:30, the
// sun 70 degrees left of the view; AgX at -0.5 EV) and the view's camera.
//
//     EIDO_GPU_WRAP='<the GPU queue>' deno run --config deno.json --frozen --allow-all \
//         eidoverse/terrain/tests/plants/views.mjs --snap <the review's snapshots>[,<more folders>]
//         [--views real_place/floor_lischmaad,...]
//         [--label port]
//
// One render job (eidoverse/render_scene.mjs), one frame a view (each view's terrain built in its frame and freed
// after it). Writes tests/out/plants/views/<recipe>_<view>_<label>.png and views_<label>.json (per view: the plan's
// counts and seconds, the instancing's, the rocks', the second frame's seconds).

import * as M from '../surfacing/_material.mjs';
import * as S from './_plants.mjs';

const A = M.argsOf();
const ALL = ['real_place/floor_lischmaad', 'real_place/ridge_schynige', 'canyon/approach_walk', 'caldera/rim_east',
    'fluvial_range/canyon_road', 'dunes/interdune_floor'];
const want = A.list('--views', ALL);
const label = A.opt('--label', 'port');
// the saved terrains' folders (comma-separated: a view's terrain is looked for in each, in order)
const snapDirs = (A.opt('--snap', Deno.env.get('EIDO_VIEW_SNAPS') ?? '') ?? '').split(',').filter(Boolean);
const W = Number(A.opt('--W', '960')), H = Number(A.opt('--H', '540'));
const edition = M.W.needBlenderEdition('the review views and the judge\'s terrains');
if (!edition) Deno.exit(0);
const tests = M.W.blenderTests();
const judge = JSON.parse(Deno.readTextFileSync(`${tests}/surfacing_judge/views.json`));
const out = `${S.W.out('plants')}/views`;
const work = `${out}/_scenes`;
Deno.mkdirSync(work, { recursive: true });
const sets = M.useSets();

// the views and, per view, the views its terrain was built with (review_views.py: a view with a focus has its own
// terrain; the views without one share the judge's)
const specs = [];
for (const rv of want) {
    const [recipe, name] = rv.split('/');
    const plan = judge[recipe];
    const v = plan.views.find((x) => x.name === name);
    if (!v) throw new Error(`${recipe}: no view ${name}`);
    const group = v.focus ? [v] : plan.views.filter((x) => !x.focus);
    let snap = null;
    if (!v.focus) snap = `${tests}/out/surfacing_judge/terrains/${recipe}.npz`;
    else {
        for (const dir of snapDirs) {
            for (const suf of ['', '_j']) {
                const p = `${dir}/${recipe}_${name}${suf}.npz`;
                if (!snap && M.W.exists(p)) snap = p;
            }
        }
    }
    if (!snap || !M.W.exists(snap)) {
        console.log(`[skip] ${rv}: no saved terrain (--snap <the review's snapshot folder>)`);
        continue;
    }
    specs.push({ recipe, name, view: v, group, snap, bakeDir: M.out(`bakes/view_${recipe}_${name}`) });
}
if (!specs.length) Deno.exit(0);

const spec = { specs, W, H, exposureEv: -0.5, hours: 15.5, sunLeftDeg: 70.0, sunElevationDeg: 37.7, sets, label,
    record: `${out}/views_${label}.json`, standM: 1.5, eyeCameraM: 50.0, vistaStepM: 2.0, vistaGapM: 4.0, vistaWiden: 1.1 };

const script = `// The plants package's views (eidoverse/terrain/tests/plants/views.mjs writes this file).
globalThis.setup = async function () {
    const V = ${JSON.stringify(spec)};
    Deno.env.set('EIDO_SURFACE_SETS', V.sets);
    const TSL = THREE.TSL ?? THREE;
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE,
        reversedDepthBuffer: true });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = Math.pow(2, V.exposureEv);
    renderer.shadowMap.enabled = true;
    await renderer.init();
    globalThis._r = renderer;
    globalThis._noAutoEnhance = true;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, WIDTH / HEIGHT, 1, 10);
    globalThis._s = scene;
    globalThis._c = camera;
    const sun = new THREE.DirectionalLight(0xffffff, 1.0);
    scene.add(sun, sun.target);
    globalThis.EANPA_NO_MRT = true;
    eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
    const sky = await makeSky({ scene, camera, renderer, world: 'earth', hours: V.hours, clouds: 'cumulus', weather: null, sun, audio: false });
    sky.update(0);
    sun.castShadow = true;
    sun.shadow.mapSize.set(4096, 4096);
    sun.shadow.bias = -0.0002;
    await sky.bakeEnv();
    const G = await import(EIDOVERSE_DIR + 'terrain/core/gpu.js');
    globalThis._views = { V, sun, sky, TSL, R: await G.init({ renderer }), world: null, records: [], cur: null,
        T: await import(EIDOVERSE_DIR + 'terrain/index.js'), SI: await import(EIDOVERSE_DIR + 'terrain/surface/index.js'),
        B: await import(EIDOVERSE_DIR + 'terrain/surface/bake.js'), Sf: await import(EIDOVERSE_DIR + 'terrain/build/surfacing.js'),
        PL: await import(EIDOVERSE_DIR + 'terrain/build/plants.js'), PI: await import(EIDOVERSE_DIR + 'terrain/build/plant_instances.js'),
        D: await import(EIDOVERSE_DIR + 'terrain/build/dressing.js') };
};

// a judge view's camera on terrain t (_material_scene.camera and aim_camera, as tests/surfacing/views.mjs places it)
function cameraOf(t, v, V) {
    const main = t.levels.find((l) => l.role === 'main') ?? t.levels[0];
    const cx = main.x0 + main.side / 2, cy = main.y0 + main.side / 2;
    const ex = v.cam[0] + cx, ey = v.cam[1] + cy;
    const [kind, dz] = v.cam_z;
    const ground = t.ring.heightAt(ex, ey);
    const ez = kind === 'ground' ? ground + Number(dz) : Number(dz);
    const tgt = [v.aim[0] + cx, v.aim[1] + cy, v.aim[2]];
    const lens = Number(v.lens), frame = v.frame;
    const dx = tgt[0] - ex, dy = tgt[1] - ey, dzz = tgt[2] - ez;
    const yawT = Math.atan2(dy, dx), pitchT = Math.atan2(dzz, Math.hypot(dx, dy));
    const u = (frame[0] - 0.5) * 36.0 / lens, w = (0.5 - frame[1]) * 36.0 * HEIGHT / WIDTH / lens;
    const yaw = yawT + Math.atan(u), pitch = pitchT - Math.atan(w);
    const d = [Math.cos(pitch) * Math.cos(yaw), Math.cos(pitch) * Math.sin(yaw), Math.sin(pitch)];
    const dist = Math.hypot(dx, dy, dzz);
    const near = ez - ground < 50 ? 0.1 : Math.max(1.0, 0.01 * dist);
    const far = 4.0 * t.levels[0].side + 40000.0;
    const hd = Math.atan2(d[1], d[0]) + V.sunLeftDeg * Math.PI / 180;
    const el = V.sunElevationDeg * Math.PI / 180;
    const sunDir = [Math.cos(hd) * Math.cos(el), Math.sin(el), -Math.sin(hd) * Math.cos(el)];
    const fovV = 2 * Math.atan(18.0 * (HEIGHT / WIDTH) / lens) * 180 / Math.PI;
    return { name: v.name, eyeB: [ex, ey, ez], aimB: tgt, ground, eye: [ex, ez, -ey], look: [ex + 1000 * d[0], ez + 1000 * d[2], -(ey + 1000 * d[1])],
        near, far, fovV, sun: sunDir, target: [tgt[0], tgt[2], -tgt[1]], dist, eyeView: kind === 'ground' && Number(dz) <= 10.0 };
}

// shots.vista_discs (surfacing_judge/shots.py at 2cf8c84, the code of the final2 renders): the ground a view's vista_m
// keeps open, points every VISTA_STEP_M out to vista_m across the frame's width (the lens's horizontal field, a tenth
// wider, about the camera's own heading), at most VISTA_GAP_M apart, each a disc of radius 0 no plant's crown covers
function vistaDiscs(v, eyeB, aimB, V) {
    const lens = Number(v.lens);
    const yaw = Math.atan2(aimB[1] - eyeB[1], aimB[0] - eyeB[0]) + Math.atan((Number(v.frame[0]) - 0.5) * 36.0 / lens);
    const half = Math.atan(18.0 / lens) * V.vistaWiden;
    const out = [];
    for (let k = 1; k <= Math.floor(Number(v.vista_m) / V.vistaStepM + 1e-9); k++) {
        const s = V.vistaStepM * k;
        const n = Math.max(1, Math.ceil(2.0 * s * Math.tan(half) / V.vistaGapM));
        for (let j = 0; j <= n; j++) {
            const a = yaw - half + 2.0 * half * j / n;
            out.push([eyeB[0] + s * Math.cos(a), eyeB[1] + s * Math.sin(a), 0.0, 'crown']);
        }
    }
    return out;
}

// make_terrain's plants= for the views built together (review_views.py group_plants, shots.plant_spec at 2cf8c84)
// and its exclusions (api.py _plan: the vista discs, the standing cameras' discs, the flats where nothing else is given)
function plantSpec(t, cams, group, V) {
    const foci = [], excl = [];
    group.forEach((v, k) => {
        const c = cams[k];
        foci.push(c.eyeView ? [c.eyeB[0], c.eyeB[1]] : [c.aimB[0], c.aimB[1]]);
        if (v.vista_m) excl.push(...vistaDiscs(v, c.eyeB, c.aimB, V));
    });
    const stand = [];
    for (const c of cams) if (c.eyeB[2] - c.ground <= V.eyeCameraM) stand.push([c.eyeB[0], c.eyeB[1], V.standM, 'crown']);
    let exclude = excl.length ? excl : null;
    if (exclude === null && stand.length) exclude = (t.info.flats ?? []).filter((f) => f.radius).map((f) => [f.at[0], f.at[1], Number(f.radius)]);
    if (stand.length) exclude = [...(exclude ?? []), ...stand];
    return { focus: foci, exclude };
}

async function buildView(G, sp) {
    const { V, T, SI, B, Sf, PL, PI, D, R, TSL } = G;
    const renderer = globalThis._r;
    const rec = { view: sp.recipe + '/' + sp.name, snap: sp.snap.split('/').pop(), seconds: {} };
    let t0 = performance.now();
    const t = await T.Terrain.load(sp.snap, { renderer, THREE, log: () => {} });
    rec.seconds.terrain = +((performance.now() - t0) / 1000).toFixed(1);
    let p = 'auto';
    if (t.info?.palette && t.info.palette !== 'auto') p = t.info.palette;
    const pal = await B.resolvePalette(t, p);
    const opts = await B.resolveOptions(t, pal, null);
    t0 = performance.now();
    const sd = await SI.bakeSurface(t, { palette: null, options: opts, cache: sp.bakeDir, log: null });
    rec.seconds.surface = +((performance.now() - t0) / 1000).toFixed(1);
    const cams = sp.group.map((v) => cameraOf(t, v, V));
    const c = cams[sp.group.findIndex((v) => v.name === sp.name)];
    const ps = plantSpec(t, cams, sp.group, V);
    t0 = performance.now();
    const spots = await PL.planPlants(t, { ecotope: 'auto', focus: { blender: ps.focus }, seed: 0, data: sd,
        ...(ps.exclude ? { exclude: { blender: ps.exclude } } : {}), log: null, R });
    rec.seconds.plants_plan = +((performance.now() - t0) / 1000).toFixed(1);
    rec.plants = Object.fromEntries(spots.species.map((e) => [e.name, e.count]));
    rec.plant_focus = ps.focus;
    rec.notes = spots.notes;
    t0 = performance.now();
    sd.addMaps(await spots.coverExtra());
    rec.seconds.plants_cover = +((performance.now() - t0) / 1000).toFixed(1);
    sd.palette = pal;
    sd._palettes = await B.palettesModule();
    t0 = performance.now();
    await sd.bakePalette(pal, { cache: sp.bakeDir, log: null, provenance: true });
    await Sf.applySurface(t, pal, { data: sd, cameras: [c.eye], THREE, TSL, renderer, log: null });
    rec.seconds.material = +((performance.now() - t0) / 1000).toFixed(1);
    const world = new THREE.Group();
    world.add(t.mesh);
    for (const m of [...(t.water?.lakes ?? []), t.water?.sea].filter(Boolean)) world.add(m);
    // the rocks round the terrain's focus (api.py: the palette's dressing spec, the terrain's seed, the flats kept clear)
    const dspec = pal.dressing ?? null;
    const tf = t.info?.focus;
    if (dspec && tf && tf.length) {
        t0 = performance.now();
        const fx = tf.reduce((a, q) => a + Number(q[0]), 0) / tf.length, fy = tf.reduce((a, q) => a + Number(q[1]), 0) / tf.length;
        const rocks = await D.scatterRocks(dspec, { terrain: t, data: sd, focus: [fx, fy], seed: t.info.seed ?? 0, renderer, R,
            exclude: (t.info.flats ?? []).filter((f) => f.radius).map((f) => [f.at[0], f.at[1], Number(f.radius)]), log: (m) => console.log(m) });
        world.add(rocks.group);
        rec.rocks = rocks.count;
        rec.seconds.rocks = +((performance.now() - t0) / 1000).toFixed(1);
    }
    t0 = performance.now();
    const plants = await PI.instancePlants(spots, t, { renderer, R, log: (m) => console.log(m) });
    rec.seconds.plants_instance = +((performance.now() - t0) / 1000).toFixed(1);
    rec.instanced = plants.species;
    spots.dispose();                                     // the plan's GPU maps: the cover is made, the spots instanced
    world.add(plants.group);
    globalThis._s.add(world);
    return { t, sd, world, plants, c, rec };
}

// a finished view's GPU memory: its plants, its terrain's mesh and runner tables, its surface data's textures
function freeView(view) {
    view.plants.dispose();
    globalThis._s.remove(view.world);
    for (const tex of Object.values(view.sd?._textures ?? {})) tex?.dispose?.();
    view.t.dispose();
}

globalThis.renderFrame = async function (tt) {
    const G = globalThis._views;
    const k = Math.max(0, Math.min(G.V.specs.length - 1, Math.round(tt)));
    const r = globalThis._r;
    if (!G.cur || G.cur.k !== k) {
        if (G.cur) {
            freeView(G.cur.view);
            G.cur = null;
        }
        const view = await buildView(G, G.V.specs[k]);
        G.cur = { k, view, done: false };
    }
    const { world, plants, c, rec } = G.cur.view;
    const { sun, sky } = G;
    const camera = globalThis._c;
    const s = sky.sunDir;
    const theta = Math.atan2(c.sun[2], c.sun[0]) - Math.atan2(s.z, s.x);
    world.rotation.y = theta;
    world.updateMatrixWorld(true);
    const Rm = new THREE.Matrix4().makeRotationY(theta);
    const pos = new THREE.Vector3(...c.eye).applyMatrix4(Rm), look = new THREE.Vector3(...c.look).applyMatrix4(Rm);
    const tgt = new THREE.Vector3(...c.target).applyMatrix4(Rm);
    camera.position.copy(pos);
    camera.up.set(0, 1, 0);
    camera.lookAt(look);
    camera.fov = c.fovV;
    camera.near = c.near;
    camera.far = c.far;
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
    for (const d of globalThis._s.children.filter((o) => o.isMesh && o.renderOrder <= -98 && o.material?.side === THREE.BackSide)) {
        const r0 = d.geometry?.parameters?.radius ?? 3200;
        d.scale.setScalar(0.9 * camera.far / r0);
    }
    const half = Math.min(6000, Math.max(300, 0.8 * c.dist));
    const sc = sun.shadow.camera;
    sc.left = -half; sc.right = half; sc.top = half; sc.bottom = -half;
    sc.near = -20000; sc.far = 20000;
    sc.updateProjectionMatrix();
    sun.shadow.normalBias = 2.0 * (2 * half / 4096);
    // the sky first: its update sets the light's colour and strength and puts the light at 120 x the sun's
    // direction from the origin, which, with the target on the view's ground kilometres away, turns the light's
    // direction (its position less its target's) away from the sun, below the horizon; then the light along the
    // sky's sun direction from the view's ground
    sky.update(0);
    sun.target.position.copy(tgt);
    sun.position.copy(tgt).add(new THREE.Vector3(s.x, s.y, s.z).multiplyScalar(1000));
    sun.target.updateMatrixWorld(true);
    sun.updateMatrixWorld(true);
    if (!G.cur.done) {
        G.cur.done = true;
        // the billboards' shade under this view's sun (in the terrain's frame), then a first frame and a timed second
        await plants.bindSun(c.sun);
        plants.update(camera);
        await r.renderAsync(globalThis._s, camera);
        await r.backend.device.queue.onSubmittedWorkDone();
        const t0 = performance.now();
        plants.update(camera);
        await r.renderAsync(globalThis._s, camera);
        await r.backend.device.queue.onSubmittedWorkDone();
        rec.seconds.second_frame = +((performance.now() - t0) / 1000).toFixed(2);
        G.records.push(rec);
        Deno.writeTextFileSync(G.V.record, JSON.stringify(G.records, null, 1));
    }
    plants.update(camera);
    await r.renderAsync(globalThis._s, camera);
};
`;
const scriptPath = `${work}/views_${label}.js`, config = `${work}/views_${label}.json`, video = `${work}/views_${label}.mp4`;
Deno.writeTextFileSync(scriptPath, script);
const rel = (p) => {
    const a = M.W.norm(p), r = M.W.REPO + '/';
    return a.startsWith(r) ? a.slice(r.length) : a;
};
const nFrames = specs.length;
Deno.writeTextFileSync(config, JSON.stringify({ width: W, height: H, fps: 1, duration: nFrames, script: rel(scriptPath),
    outputVideo: rel(video), capture: { at: Array.from({ length: nFrames }, (_, k) => k), jump: true } }, null, 1));
const argv = M.W.gpuArgv([M.W.norm(Deno.execPath()), 'run', '--allow-all', '--unstable-webgpu', '--node-modules-dir=auto',
    'eidoverse/render_scene.mjs', rel(config)], { cwd: M.W.REPO });
const t0 = performance.now();
const log = `${work}/views_${label}.log`;
const code = await M.W.run(argv, { cwd: M.W.REPO, log, env: { ...Deno.env.toObject(), RENDER_CODEC: 'libx264', RENDER_CQ: '0' } });
const pngs = [];
specs.forEach((sp, k) => {
    const shot = `${work}/views_${label}_at${k.toFixed(2)}s.png`;
    const png = `${out}/${sp.recipe}_${sp.name}_${label}.png`;
    if (M.W.exists(shot)) {
        Deno.renameSync(shot, png);
        pngs.push(png);
    }
});
console.log(`[views] ${pngs.length} of ${nFrames} frames in ${((performance.now() - t0) / 1000).toFixed(0)} s (exit ${code}; ${log})\n  ${pngs.join('\n  ')}`);
Deno.exit(code === 0 && pngs.length === nFrames ? 0 : 1);
