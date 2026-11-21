// The per-texel material from the surfacing judge's views, rendered by this edition's renderer
// (eidoverse/render_scene.mjs) beside Blender's renders of the same views (PORT_PLAN.md 8.2 row P17; 5.3 "look"): a
// bake case's terrain (Blender's snapshot), the port's surface data and palette bake of it (tests/out/surfacing/bakes,
// as _material.mjs makes them), build/surfacing.js applySurface with the views' cameras, each view's camera as
// blender/tests/terrain/surfacing/_material_scene.py places it (surfacing_judge/views.json: its eye over the main
// tile's centre, its aim and the frame point the aim lands on, its lens on a 36 mm sensor fitted horizontally) and
// its light as _material_scene.light gives it (make_sky's earth at 15:30, the sun 70 degrees left of the view's
// heading; AgX at -0.5 EV, the review's textured exposure). Every view of a case is one frame of one render job (one
// shader compile), its frames written as PNGs.
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/surfacing/views.mjs --case canyon
//         --views brink_down,low_oblique [--options '{"specular_aa": false}'] [--label port] [--out <dir>]
//         [--variants built,near,far,allow,band] [--save <a terrain save of the case's recipe>]
//     (the render is a GPU job of its own, behind $EIDO_GPU_WRAP; this orchestrator needs no GPU)
//
// Writes <out>/<case>_<view>_<label>.png (default out: tests/out/surfacing/views) and <case>_<label>_views.json.
// --variants (check_far.py's): built (the material as applySurface makes it), near (D0 past everything: the layers to
// the horizon), far (D0 at 1 cm: the far colour C wherever the hand-off allows it), allow (a mask: where the far colour
// may draw, more than 64 main cells outside the outermost hero window), band (a mask: view distance D0..1.5 D0); and
// check_shimmer.py's: turn1, turn2 (the material as built, the camera turned about the vertical by 0.5 and 1 pixel),
// dist<m> (a mask: view distance at least m metres; dist0 the ground); clay, clay_turn1, clay_turn2 (grey clay in place
// of the material: the frames' crawl without it). Masks draw the terrain alone, white where their test holds, black
// elsewhere. Each view once per variant, written <case>_<view>_<label>_<variant>.png; D0 moves by setFarDistance, so
// one compile. --turn-width: the frame width whose pixel the turns are (default --W; a supersampled render at 2 x the
// width turns by the 1 x frame's pixel with --turn-width 960).
//
// Where this differs from the Blender rig, and why: as tests/judge/views.mjs's rig, the sky facade takes no azimuth, so
// the ground and the camera are turned together about the vertical until the facade's 15:30 sun stands 70 degrees
// left of the view, as the review puts it; three's AgX has no "Medium High Contrast" look; one 4096^2 shadow map over
// the view's ground, where EEVEE renders virtual shadow maps.

import * as M from './_material.mjs';

const A = M.argsOf();
const name = A.opt('--case', 'canyon');
const views = A.list('--views', null);
const label = A.opt('--label', 'port');
const out = A.opt('--out', M.out('views'));
const W = Number(A.opt('--W', '960')), H = Number(A.opt('--H', '540'));
const options = A.opt('--options', null);
const variants = A.list('--variants', ['built']);
const PLAN_OF = { canyon: 'canyon', alpine_valley: 'alpine_valley', lauterbrunnen: 'real_place', meteor_crater: 'impact_crater',
    toroweap: 'canyon', fluvial_range: 'fluvial_range' };
const edition = M.W.needBlenderEdition('the snapshots and the judge\'s views');
if (!edition) Deno.exit(0);
// --save: a terrain save of the case's recipe in place of its bake snapshot (the judge's own, e.g.
// out/surfacing_judge/terrains/sea_cliffs.npz), baked with the default surface options where Blender has no bake record
const snap = A.opt('--save', `${M.W.blenderTests()}/out/surface_data/snap/${name}.npz`);
const judge = JSON.parse(Deno.readTextFileSync(`${M.W.blenderTests()}/surfacing_judge/views.json`));
const plan = judge[PLAN_OF[name] ?? name];
const pick = (views ?? plan.views.map((v) => v.name)).map((n) => {
    const v = plan.views.find((x) => x.name === n);
    if (!v) throw new Error(`${name}: no view ${n} (views: ${plan.views.map((x) => x.name).join(', ')})`);
    return v;
});
const bb = M.S.blenderBake(name);
const bakeDir = M.out(`bakes/${name}`);
Deno.mkdirSync(out, { recursive: true });
const work = `${out}/_scenes`;
Deno.mkdirSync(work, { recursive: true });
const sets = M.useSets();

const spec = { snap, bakeDir, bakeOptions: { ...(bb?.info?.options ?? {}) }, views: pick, W, H, exposureEv: -0.5, hours: 15.5,
    sunLeftDeg: 70.0, sunElevationDeg: 37.7, options: options ? JSON.parse(options) : null, sets, label, name, variants,
    usedJson: `${out}/${name}_${label}_views.json`, turnWidth: Number(A.opt('--turn-width', String(W))) };

const script = `// The surfacing package's views (eidoverse/terrain/tests/surfacing/views.mjs writes this file).
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
    const T = await import(EIDOVERSE_DIR + 'terrain/index.js');
    const SI = await import(EIDOVERSE_DIR + 'terrain/surface/index.js');
    const B = await import(EIDOVERSE_DIR + 'terrain/surface/bake.js');
    const Sf = await import(EIDOVERSE_DIR + 'terrain/build/surfacing.js');
    const t = await T.Terrain.load(V.snap, { renderer, THREE, log: () => {} });
    const sd = await SI.bakeSurface(t, { palette: null, options: V.bakeOptions, cache: V.bakeDir, log: null });
    let p = 'auto';
    if (t.info?.palette && t.info.palette !== 'auto') p = t.info.palette;
    const pal = await B.resolvePalette(t, p);
    sd.palette = pal;
    sd._palettes = await B.palettesModule();
    await sd.bakePalette(pal, { cache: V.bakeDir, log: null, provenance: true });
    // the views' cameras (Blender frame): _material_scene.camera and aim_camera
    const main = t.levels.find((l) => l.role === 'main') ?? t.levels[0];
    const cx = main.x0 + main.side / 2, cy = main.y0 + main.side / 2;
    const cams = V.views.map((v) => {
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
        // the sun 70 degrees left of the view's heading, 37.7 degrees up (make_sky at 15:30)
        const hd = Math.atan2(d[1], d[0]) + V.sunLeftDeg * Math.PI / 180;
        const el = V.sunElevationDeg * Math.PI / 180;
        const sun = [Math.cos(hd) * Math.cos(el), Math.sin(el), -Math.sin(hd) * Math.cos(el)];
        // the horizontal field of view of a 36 mm sensor fitted horizontally: the vertical one three takes
        const fovV = 2 * Math.atan(18.0 * (HEIGHT / WIDTH) / lens) * 180 / Math.PI;
        return { name: v.name, eye: [ex, ez, -ey], look: [ex + 1000 * d[0], ez + 1000 * d[2], -(ey + 1000 * d[1])],
            near, far, fovV, sun, target: [tgt[0], tgt[2], -tgt[1]], dist, lens };
    });
    await Sf.applySurface(t, pal, { data: sd, cameras: cams.map((c) => c.eye), THREE, TSL, renderer, options: V.options,
        log: (m) => console.log(m) });
    const built = [...t.mesh.material];
    const near = built[0];
    const D0 = near.userData.eidoFarM;
    // the variants' masks, white on the terrain where their test holds, black elsewhere (the sky and water hidden):
    // check_far.py's region (where the far colour may draw, and the hand-off's band) and check_shimmer.py's bands of
    // view distance (dist<m>: at least m metres; dist0 the ground)
    const masks = {};
    const vd = TSL.length(TSL.positionView);
    const mk = (cond) => {
        const m = new THREE.MeshBasicNodeMaterial();
        m.colorNode = TSL.vec4(TSL.select(cond, TSL.vec3(50.0), TSL.vec3(0.0)), 1.0);
        m.fog = false;
        return m;
    };
    if (V.variants.includes('allow') || V.variants.includes('band')) {
        const tm = await Sf.terrainMap(sd, null, { THREE, TSL, renderer });
        const cm = (t.levels.filter((l) => l.role === 'main').pop() ?? t.levels[0]).cell;
        const ho = tm._data.rd.heroOutside;
        const allow = typeof ho === 'number' ? TSL.float(1.0) : TSL.smoothstep(0.0, 64.0 * cm, ho);
        masks.allow = mk(allow.greaterThan(0.999));
        masks.band = mk(vd.greaterThanEqual(D0).and(vd.lessThanEqual(1.5 * D0)));
    }
    for (const v of V.variants) {
        const m = /^dist([0-9.]+)$/.exec(v);
        if (m) masks[v] = mk(vd.greaterThanEqual(Number(m[1])));
    }
    const world = new THREE.Group();
    world.add(t.mesh);
    for (const m of [...t.water.lakes, t.water.sea].filter(Boolean)) world.add(m);
    scene.add(world);
    const sun = new THREE.DirectionalLight(0xffffff, 1.0);
    scene.add(sun, sun.target);
    globalThis.EANPA_NO_MRT = true;
    eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
    const sky = await makeSky({ scene, camera, renderer, world: 'earth', hours: V.hours, clouds: 'cumulus', weather: null, sun, audio: false });
    sky.update(0);
    globalThis._sky = sky;
    const s = sky.sunDir;
    const elSky = Math.asin(Math.max(-1, Math.min(1, s.y))) * 180 / Math.PI;
    sun.castShadow = true;
    sun.shadow.mapSize.set(4096, 4096);
    sun.shadow.bias = -0.0002;
    await sky.bakeEnv();
    const clay = V.variants.some((v) => v.startsWith('clay')) ? Sf.clayMaterial(THREE, 'clay') : null;
    globalThis._views = { cams, world, sun, sky, s, elSky, t, built, near, D0, masks, Sf, variants: V.variants, clay,
        turnWidth: V.turnWidth };
    Deno.writeTextFileSync(V.usedJson, JSON.stringify({ case: V.name, label: V.label, sky_sun_elevation_deg: elSky,
        views: cams, options: V.options, material: { textures: t.mesh.material[0].userData.eidoTextures,
            far_m: t.mesh.material[0].userData.eidoFarM, build_s: t.mesh.material[0].userData.eidoBuildS } }, null, 1));
};
globalThis.renderFrame = async function (tt) {
    const { cams, world, sun, sky, s, t, built, near, D0, masks, Sf, variants, clay, turnWidth } = globalThis._views;
    const k = Math.max(0, Math.round(tt));
    const c = cams[Math.min(cams.length - 1, Math.floor(k / variants.length))];
    const variant = variants[k % variants.length];
    const mask = masks[variant] ?? null;
    // clay, clay_turn1, clay_turn2: the grey clay in place of the material (the frames' floor without it)
    const base = variant.startsWith('clay') ? (variant.slice(5) || 'built') : variant;
    if (variant.startsWith('clay')) {
        t.mesh.material = [clay, clay];
    } else if (variant === 'built' || variant === 'turn1' || variant === 'turn2') {
        t.mesh.material = built;
        Sf.setFarDistance(near, D0);
    } else if (variant === 'near' || variant === 'far') {
        t.mesh.material = [near, near];
        Sf.setFarDistance(near, variant === 'near' ? 1.0e9 : 0.01);
    } else {
        t.mesh.material = [mask, mask];
    }
    const camera = globalThis._c;
    // the ground and the camera turned together about the vertical so the facade's sun stands where the view wants it
    const theta = Math.atan2(c.sun[2], c.sun[0]) - Math.atan2(s.z, s.x);
    world.rotation.y = theta;
    world.updateMatrixWorld(true);
    const R = new THREE.Matrix4().makeRotationY(theta);
    // check_shimmer.py's turns: the camera turned about the world's vertical through itself by 0.5 and 1 pixel
    // ((36 / lens) / width radians, the frame's centre), Blender's +z the vertical here too
    const turn = base === 'turn1' ? 0.5 : base === 'turn2' ? 1.0 : 0.0;
    const lookAt = new THREE.Vector3(...c.look);
    if (turn) {
        const e = new THREE.Vector3(...c.eye);
        lookAt.sub(e).applyAxisAngle(new THREE.Vector3(0, 1, 0), turn * (36.0 / c.lens) / (turnWidth ?? WIDTH)).add(e);
    }
    const pos = new THREE.Vector3(...c.eye).applyMatrix4(R), look = lookAt.applyMatrix4(R);
    const tgt = new THREE.Vector3(...c.target).applyMatrix4(R);
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
    // the shadow map over the view's ground: around the aim, as wide as the eye is far from it (at most 6 km)
    const half = Math.min(6000, Math.max(300, 0.8 * c.dist));
    const sc = sun.shadow.camera;
    sc.left = -half; sc.right = half; sc.top = half; sc.bottom = -half;
    sc.near = -20000; sc.far = 20000;
    sc.updateProjectionMatrix();
    sun.shadow.normalBias = 2.0 * (2 * half / 4096);
    // the sky first: its update sets the light's colour and strength and puts the light at 120 x the sun's direction
    // from the origin, which, with the target on the view's ground kilometres away, turns the light's direction (its
    // position less its target's) away from the sun, below the horizon; then the light along the sky's sun direction
    // from the view's ground (tests/plants/views.mjs found and fixed the same order)
    sky.update(0);
    sun.target.position.copy(tgt);
    sun.position.copy(tgt).add(new THREE.Vector3(s.x, s.y, s.z).multiplyScalar(1000));
    sun.target.updateMatrixWorld(true);
    sun.updateMatrixWorld(true);
    // a mask frame draws the terrain alone: the sky's domes and the water hidden, so the black reads as "not here"
    for (const o of [...globalThis._s.children, ...world.children]) {
        if (o === world || o === t.mesh || o.isLight) continue;
        if (o.userData.eidoShown === undefined) o.userData.eidoShown = o.visible;
        o.visible = mask ? false : o.userData.eidoShown;
    }
    await globalThis._r.renderAsync(globalThis._s, camera);
};
`;
const scriptPath = `${work}/${name}_${label}.js`, config = `${work}/${name}_${label}.json`, video = `${work}/${name}_${label}.mp4`;
Deno.writeTextFileSync(scriptPath, script);
const rel = (p) => {
    const a = M.W.norm(p), r = M.W.REPO + '/';
    return a.startsWith(r) ? a.slice(r.length) : a;
};
const nFrames = pick.length * variants.length;
Deno.writeTextFileSync(config, JSON.stringify({ width: W, height: H, fps: 1, duration: nFrames, script: rel(scriptPath),
    outputVideo: rel(video), capture: { at: Array.from({ length: nFrames }, (_, k) => k), jump: true } }, null, 1));
const argv = M.W.gpuArgv([M.W.norm(Deno.execPath()), 'run', '--allow-all', '--unstable-webgpu', '--node-modules-dir=auto',
    'eidoverse/render_scene.mjs', rel(config)], { cwd: M.W.REPO });
const t0 = performance.now();
const log = `${work}/${name}_${label}.log`;
const code = await M.W.run(argv, { cwd: M.W.REPO, log, env: { ...Deno.env.toObject(), RENDER_CODEC: 'libx264', RENDER_CQ: '0' } });
const pngs = [];
for (let k = 0; k < nFrames; k++) {
    const v = pick[Math.floor(k / variants.length)], variant = variants[k % variants.length];
    const shot = `${work}/${name}_${label}_at${k.toFixed(2)}s.png`;
    const png = `${out}/${name}_${v.name}_${label}${variants.length > 1 || variant !== 'built' ? '_' + variant : ''}.png`;
    if (M.W.exists(shot)) {
        Deno.renameSync(shot, png);
        pngs.push(png);
    }
}
console.log(`[views] ${name} ${label}: ${pngs.length} of ${nFrames} frames in ${((performance.now() - t0) / 1000).toFixed(0)} s ` +
    `(exit ${code}; ${log})\n  ${pngs.join('\n  ')}`);
Deno.exit(code === 0 && pngs.length === nFrames ? 0 : 1);
