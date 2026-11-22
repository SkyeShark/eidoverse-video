// The look package's judge views, the scene side (PORT_PLAN.md 8.2 row P18): eidoverse/terrain/tests/surface_look/
// views.mjs writes the job's spec (a JSON file named by $EIDO_LOOK_SPEC) and runs this script through
// eidoverse/render_scene.mjs, which evaluates it with the edition's globals (THREE, canvas, GPU_ADAPTER, GPU_DEVICE,
// EIDOVERSE_DIR, WIDTH, HEIGHT).
//
// Port of blender/tests/terrain/surfacing/review_views.py at 2cf8c84 (render_group with --plants --layers: the final
// check's renders, out/surfacing/review/<recipe>/<view>_final2.png), and of surfacing_judge/shots.py at 2cf8c84
// (aim_camera, vista_discs, plant_spec, palette_now). Per terrain group (the views built together): the terrain (a
// saved one), the port's surface bake, the plants planned along every view of the group, their cover added before the
// palette bake, the material (build/surfacing.js applySurface with every camera of the group) and its debug='layers'
// twin built while the data is held, the rocks round the terrain's focus, the plants instanced; per view: the camera,
// the light (make_sky's earth at 15:30 with cumulus, the sun 70 degrees left of the view), the LOD pass, then
//   - the textured frame, scene-linear (no tone curve), into a half-float target at k x the review's size, written as
//     raw half floats: tests/surface_look/develop.py takes it through Blender's own display transform (AgX, the
//     review's look and exposure: blender_display.py's table) and through this edition's (three's AgX) and averages
//     it k x k down to the review's 960 x 540;
//   - the layer map (review_views.layer_scene): the layer material on every ring, water black, everything else
//     hidden, no sky, a transparent film, scene-linear, written the same way;
//   - the canvas frame render_scene captures (three's AgX, as the edition renders a film).
// The scene code follows tests/plants/views.mjs (P15's views of the same judge, which this extends: groups built
// once, the layer pass, the scene-linear readback, the palette of the code as it is now).
//
// Where this differs from the Blender rig, and why (each is the renderer's, not the surfacing's):
//   - the sky facade takes no azimuth, so the sun's light falls along the view's sun (70 degrees left of its heading,
//     at the facade's 15:30 elevation) and the sky's environment is turned to it (scene.environmentRotation); the sky
//     seen in the frame keeps the facade's own azimuth. The ground is not turned with the camera, as
//     tests/plants/views.mjs and tests/surfacing/views.mjs turn it: the terrain's material, like Blender's, takes the
//     terrain's frame for the world's, so a turned terrain is shaded with its normals turned by the same angle;
//   - EEVEE's 16 jittered samples with its 1.5 px Blackman-Harris film are k x k samples of a box here;
//   - one 4096^2 sun shadow map, where EEVEE renders virtual shadow maps: over the aim's ground as the other views
//     tools place it for an aerial; for an eye view over the ground the camera stands on and looks at out to 1.5 km,
//     so the near plants and ground keep their shadows (the aim of an eye view can lie kilometres off, beyond a box
//     round it); ground beyond the box is lit. The shadow camera stands 8 km sunward, so a valley wall kilometres
//     off still shades the floor, and a throwaway frame in setup() takes three's first-render depth reversal
//     before any view (see there);
//   - three.js has no specular occlusion and no sky occlusion (EEVEE's horizon scan and ray-traced reflections darken
//     the sky's light and its reflection in crevices, under foliage and on a deep valley's shaded floor; water
//     reflects the environment, not the walls round it); the materials are as their packages made them.

const _lookDeg = Math.PI / 180;
const SHADOW_BACK = 8000.0;        // metres from the sun's shadow camera to the centre of the ground it maps

globalThis.setup = async function () {
    const V = JSON.parse(Deno.readTextFileSync(Deno.env.get('EIDO_LOOK_SPEC')));
    if (V.sets) Deno.env.set('EIDO_SURFACE_SETS', V.sets);
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
    const sky = await makeSky({ scene, camera, renderer, world: 'earth', hours: V.hours, clouds: 'cumulus', weather: null,
        sun, audio: false });
    sky.update(0);
    sun.castShadow = true;
    sun.shadow.mapSize.set(V.shadowMap, V.shadowMap);
    sun.shadow.bias = -0.0001;                          // of the shadow camera's 16 km depth: 1.6 m
    await sky.bakeEnv();
    // one throwaway frame with a lit, shadowed plate before any view: three r184 reverses a camera's depth at its first
    // render (Renderer.render), and ShadowNode.renderShadow takes the shadow's matrix from the projection before it
    // renders the map, so the sun's first shadow map is reversed while its lookup is not (a job's first view was lit
    // where its ground lies in shade: alpine floor_axis's floor)
    {
        const plate = new THREE.Mesh(new THREE.PlaneGeometry(10, 10), new THREE.MeshStandardNodeMaterial());
        plate.rotation.x = -Math.PI / 2;
        plate.castShadow = plate.receiveShadow = true;
        scene.add(plate);
        camera.position.set(0, 20, 20);
        camera.lookAt(0, 0, 0);
        camera.updateMatrixWorld(true);
        await renderer.renderAsync(scene, camera);
        scene.remove(plate);
        plate.geometry.dispose();
        plate.material.dispose();
    }
    const G = await import(EIDOVERSE_DIR + 'terrain/core/gpu.js');
    globalThis._look = { V, sun, sky, TSL, R: await G.init({ renderer }), cur: null, records: [], frames: V.frames,
        T: await import(EIDOVERSE_DIR + 'terrain/index.js'), SI: await import(EIDOVERSE_DIR + 'terrain/surface/index.js'),
        B: await import(EIDOVERSE_DIR + 'terrain/surface/bake.js'), Sf: await import(EIDOVERSE_DIR + 'terrain/build/surfacing.js'),
        PL: await import(EIDOVERSE_DIR + 'terrain/build/plants.js'), PI: await import(EIDOVERSE_DIR + 'terrain/build/plant_instances.js'),
        D: await import(EIDOVERSE_DIR + 'terrain/build/dressing.js'), RG: await import(EIDOVERSE_DIR + 'terrain/recipes/index.js') };
    const Pm = await globalThis._look.B.palettesModule();
    console.log(`[look] ${V.frames.length} views in ${V.groups.length} terrain groups; palettes ` +
        `${Pm?.PALETTES ? Object.keys(Pm.PALETTES).length + ' (' + (V.palettesFile ?? 'build/palettes.js') + ')' : 'missing'}`);
};

// a judge view's camera on terrain t (review_views.view_camera and shots.aim_camera): Blender eye, aim and ground, the
// three.js eye, look point and target, the clip planes, the vertical field of view, the sun 70 degrees left of the
// view's heading at the review's elevation (three.js frame), heading and pitch as the record keeps them
function cameraOf(t, v, V) {
    const main = t.levels.find((l) => l.role === 'main') ?? t.levels[0];
    const cx = main.x0 + main.side / 2, cy = main.y0 + main.side / 2;
    const ex = v.cam[0] + cx, ey = v.cam[1] + cy;
    const [kind, dz] = v.cam_z;
    const ground = t.ring.heightAt(ex, ey);
    const ez = kind === 'ground' ? ground + Number(dz) : Number(dz);
    const tgt = [v.aim[0] + cx, v.aim[1] + cy, v.aim[2]];
    const lens = Number(v.lens), frame = v.frame ?? [0.5, 0.5];
    const dx = tgt[0] - ex, dy = tgt[1] - ey, dzz = tgt[2] - ez;
    const yawT = Math.atan2(dy, dx), pitchT = Math.atan2(dzz, Math.hypot(dx, dy));
    const u = (frame[0] - 0.5) * 36.0 / lens, w = (0.5 - frame[1]) * 36.0 * V.H / V.W / lens;
    const yaw = yawT + Math.atan(u), pitch = pitchT - Math.atan(w);
    const d = [Math.cos(pitch) * Math.cos(yaw), Math.cos(pitch) * Math.sin(yaw), Math.sin(pitch)];
    const dist = Math.hypot(dx, dy, dzz);
    const near = kind === 'ground' ? 0.1 : Math.max(1.0, 0.01 * dist);
    const far = kind === 'ground' ? 4.0 * t.levels[0].side + 40000.0 : 30.0 * dist;
    const hd = Math.atan2(d[1], d[0]) + V.sunLeftDeg * _lookDeg;
    const el = V.sunElevationDeg * _lookDeg;
    const sunDir = [Math.cos(hd) * Math.cos(el), Math.sin(el), -Math.sin(hd) * Math.cos(el)];
    const fovV = 2 * Math.atan(18.0 * (V.H / V.W) / lens) / _lookDeg;
    const eyeView = kind === 'ground' && Number(dz) <= 10.0;
    return { name: v.name, eyeB: [ex, ey, ez], aimB: tgt, ground, eye: [ex, ez, -ey],
        look: [ex + 1000 * d[0], ez + 1000 * d[2], -(ey + 1000 * d[1])], dirB: d, near, far, fovV, sun: sunDir,
        target: [tgt[0], tgt[2], -tgt[1]], dist, eyeView, lens,
        heading: ((90.0 - Math.atan2(d[1], d[0]) / _lookDeg) % 360 + 360) % 360, pitch: pitch / _lookDeg };
}

// shots.vista_discs: the ground a view's vista_m keeps open, points every VISTA_STEP_M out to vista_m across the
// frame's width (the lens's horizontal field, a tenth wider, about the camera's own heading), at most VISTA_GAP_M apart
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

// make_terrain's plants= for the views built together (review_views.group_plants, shots.plant_spec) and the build's
// exclusions (api.py _plan: the vista discs, the standing cameras' discs, the flats where nothing else is given), as
// tests/plants/views.mjs transcribes them
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

// core/levels.Level's repr, as render records keep it (surfacing_judge/states.levels reads it back)
function levelText(lv, i) {
    const f = (x) => String(+Number(x).toFixed(4));
    return `Level(${i} ${lv.role} ${f(lv.side)} m @ ${f(lv.cell)} m x${lv.n}, x0 ${f(lv.x0)} y0 ${f(lv.y0)})`;
}

const secs = (t0) => +((performance.now() - t0) / 1000).toFixed(1);

async function buildGroup(G, g) {
    const { V, T, SI, B, Sf, PL, PI, D, R, TSL, RG } = G;
    const renderer = globalThis._r;
    const rec = { terrain: g.snap.split('/').pop(), cache_hit: 'snapshot', seconds: {} };
    let t0 = performance.now();
    const t = await T.Terrain.load(g.snap, { renderer, THREE, log: () => {} });
    rec.terrain_s = secs(t0);
    // the palette of the code as it is now (shots.palette_now): 'auto' for a real place, else the registry recipe's
    // 'auto' palette (a saved terrain carries its recipe as it was saved, with that day's palette copy)
    const Pm = await B.palettesModule();
    const palNow = g.recipe === 'real_place' ? 'auto' : Pm.get('auto', RG.get(g.recipe));
    const pal = await B.resolvePalette(t, palNow);
    rec.palette = pal.name;
    const opts = await B.resolveOptions(t, pal, null);
    t0 = performance.now();
    const sd = await SI.bakeSurface(t, { palette: null, options: opts, cache: g.bakeDir, log: null });
    rec.seconds.surface = secs(t0);
    const cams = g.group.map((v) => cameraOf(t, v, V));
    let spots = null, plants = null;
    if (V.plants) {
        const ps = plantSpec(t, cams, g.group, V);
        t0 = performance.now();
        spots = await PL.planPlants(t, { ecotope: 'auto', focus: { blender: ps.focus }, seed: 0, data: sd,
            ...(ps.exclude ? { exclude: { blender: ps.exclude } } : {}), log: null, R });
        rec.seconds.plants_plan = secs(t0);
        rec.plants = Object.fromEntries(spots.species.map((e) => [e.name, e.count]));
        rec.plant_focus = ps.focus.length === 1 ? ps.focus[0] : ps.focus;
        rec.plant_notes = spots.notes;
        t0 = performance.now();
        sd.addMaps(await spots.coverExtra());
        rec.seconds.plants_cover = secs(t0);
    } else {
        // make_terrain(plants=None): the bake still holds the ecotope's expected cover (plants.expected_cover with no
        // plan), so a palette's forest and chaparral read the same rule with plants and without
        t0 = performance.now();
        sd.addMaps(await PL.expectedCover(t, { ecotope: 'auto', data: sd, R }));
        rec.seconds.plants_cover = secs(t0);
        rec.plants = null;
    }
    sd.palette = pal;
    sd._palettes = Pm;
    t0 = performance.now();
    await sd.bakePalette(pal, { cache: g.bakeDir, log: null, provenance: true });
    rec.seconds.palette_bake = secs(t0);
    t0 = performance.now();
    const near = await Sf.applySurface(t, pal, { data: sd, cameras: cams.map((c) => c.eye), THREE, TSL, renderer,
        log: V.logMaterial ? (m) => console.log(`[look material] ${g.recipe}: ${m}`) : null });
    rec.seconds.material = secs(t0);
    rec.far_m = near.userData.eidoFarM;
    rec.textures = near.userData.eidoTextures;
    // where the far material lies (review_views.far_rings_of): the rings beyond 1.5 D0 of every camera, and the window
    // edges between a near ring and a far one
    const farSet = new Set(Sf.farRings(t, sd, cams.map((c) => c.eye), near.userData.eidoFarM));
    const table = t.ring.ringTable();
    rec.far_material = farSet.size > 0;
    rec.far_rings = [...farSet];
    rec.far_edges = table.slice(0, -1).filter((r, k) => r.hole && farSet.has(r.ring) !== farSet.has(table[k + 1].ring))
        .map((r) => r.hole.map((c) => +Number(c).toFixed(3)));
    let lmat = null;
    if (V.layers) {
        lmat = await Sf.surfaceMaterial(pal, { data: sd, recipe: t.recipe, options: { debug: 'layers' },
            constants: Sf.terrainConstants(t), THREE, TSL, renderer, log: null, name: 'terrain_layers' });
        lmat.fog = false;
    }
    const world = new THREE.Group();
    world.add(t.mesh);
    const water = [...(t.water?.lakes ?? []), t.water?.sea].filter(Boolean);
    for (const m of water) world.add(m);
    // the rocks round the terrain's focus (api.py: the palette's dressing spec, the terrain's seed, the flats kept clear)
    const dspec = pal.dressing ?? null;
    const tf = t.info?.focus;
    rec.rocks = null;
    let rocks = null;
    if (V.rocks && dspec && tf && tf.length) {
        t0 = performance.now();
        const fx = tf.reduce((a, q) => a + Number(q[0]), 0) / tf.length, fy = tf.reduce((a, q) => a + Number(q[1]), 0) / tf.length;
        rocks = await D.scatterRocks(dspec, { terrain: t, data: sd, focus: [fx, fy], seed: t.info.seed ?? 0, renderer, R,
            exclude: (t.info.flats ?? []).filter((f) => f.radius).map((f) => [f.at[0], f.at[1], Number(f.radius)]), log: null });
        world.add(rocks.group);
        rec.rocks = rocks.count;
        rec.seconds.rocks = secs(t0);
    }
    if (spots) {
        t0 = performance.now();
        plants = await PI.instancePlants(spots, t, { renderer, R, log: null });
        rec.seconds.plants_instance = secs(t0);
        rec.instanced = Object.fromEntries(Object.entries(plants.species ?? {}).map(([k, s]) => [k, { card_m: s.card_m,
            hero_m: s.hero_m, spots: s.spots, individuals: (s.individuals ?? []).length }]));
        spots.dispose();                                 // the plan's GPU maps: the cover is made, the spots instanced
        world.add(plants.group);
    }
    globalThis._s.add(world);
    rec.levels = t.levels.map((lv, i) => levelText(lv, i));
    rec.views_built_together = g.group.map((v) => v.name);
    return { t, sd, world, plants, rocks, water, lmat, cams, rec };
}

function freeGroup(cur) {
    cur.plants?.dispose();
    globalThis._s.remove(cur.world);
    for (const tex of Object.values(cur.sd?._textures ?? {})) tex?.dispose?.();
    cur.lmat?.dispose?.();
    cur.t.dispose();
}

// a scene-linear frame of the scene from `camera` into a half-float target of w x h: { bytes, w, h, row (elements a
// row, padding included) }; with layers, cleared to transparent black
async function linearFrame(r, scene, camera, w, h, samples, clearAlpha) {
    const rt = new THREE.RenderTarget(w, h, { type: THREE.HalfFloatType, depthBuffer: true, samples });
    const prev = r.getRenderTarget();
    const cc = new THREE.Color();
    r.getClearColor(cc);
    const ca = r.getClearAlpha();
    r.setRenderTarget(rt);
    r.setClearColor(0x000000, clearAlpha);
    await r.renderAsync(scene, camera);
    const raw = await r.readRenderTargetPixelsAsync(rt, 0, 0, w, h);
    r.setRenderTarget(prev);
    r.setClearColor(cc, ca);
    rt.dispose();
    return { bytes: new Uint8Array(raw.buffer, raw.byteOffset, raw.byteLength), w, h, row: raw.length / h };
}

function writeFrame(path, f, meta) {
    Deno.writeFileSync(path, f.bytes);
    Deno.writeTextFileSync(path.replace(/\.f16$/, '.json'), JSON.stringify({ w: f.w, h: f.h, row: f.row, format: 'rgba16float',
        rows: 'top first', ...meta }));
}

async function renderView(G, entry) {
    const { V, sun, sky } = G;
    const cur = G.cur;
    const r = globalThis._r;
    const scene = globalThis._s;
    const camera = globalThis._c;
    const k = cur.cams.findIndex((c) => c.name === entry.view);
    const c = cur.cams[k];
    const v = entry.v;
    const t0 = performance.now();
    // the sun where the view wants it, the ground where it is: the facade's sky takes no azimuth, so the sun's light
    // falls along the view's sun (70 degrees left of its heading) and the sky's environment is turned about the
    // vertical until its sun stands there too (scene.environmentRotation). The ground is not turned with the camera, as
    // the other views tools turn it: the terrain's material, like Blender's, takes the terrain's frame for the world's
    // (surfacing.py: "the terrain keeps an identity transform"), so a turned terrain is shaded with turned normals
    const s = sky.sunDir;
    const theta = Math.atan2(c.sun[2], c.sun[0]) - Math.atan2(s.z, s.x);
    cur.world.rotation.y = 0;
    cur.world.updateMatrixWorld(true);
    scene.environmentRotation.set(0, -theta, 0);
    const Rm = new THREE.Matrix4();
    const pos = new THREE.Vector3(...c.eye), look = new THREE.Vector3(...c.look);
    const sunV = new THREE.Vector3(...c.sun).normalize();
    camera.position.copy(pos);
    camera.up.set(0, 1, 0);
    camera.lookAt(look);
    camera.fov = c.fovV;
    camera.aspect = V.W / V.H;
    camera.near = c.near;
    camera.far = c.far;
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
    for (const d of scene.children.filter((o) => o.isMesh && o.renderOrder <= -98 && o.material?.side === THREE.BackSide)) {
        const r0 = d.geometry?.parameters?.radius ?? 3200;
        d.scale.setScalar(0.9 * camera.far / r0);
    }
    // the shadow map: an aerial's over the ground round its aim (as wide as the eye is far from it, at most 6 km); an
    // eye view's over the ground it stands on and looks at, out to 1.5 km
    let centre, half;
    if (c.eyeView && V.shadowNearM) {                  // a probe: the map over the camera's first metres only
        const h = Math.hypot(c.dirB[0], c.dirB[1]) || 1;
        const mx = c.eyeB[0] + 0.5 * V.shadowNearM * c.dirB[0] / h, my = c.eyeB[1] + 0.5 * V.shadowNearM * c.dirB[1] / h;
        centre = new THREE.Vector3(mx, cur.t.ring.heightAt(mx, my), -my);
        half = V.shadowNearM;
    } else if (c.eyeView) {
        const reach = Math.min(1500.0, c.dist);
        const h = Math.hypot(c.dirB[0], c.dirB[1]) || 1;
        const mx = c.eyeB[0] + 0.5 * reach * c.dirB[0] / h, my = c.eyeB[1] + 0.5 * reach * c.dirB[1] / h;
        centre = new THREE.Vector3(mx, cur.t.ring.heightAt(mx, my), -my);
        half = Math.max(300.0, 0.6 * reach);
    } else {
        centre = new THREE.Vector3(...c.target);
        half = Math.min(6000, Math.max(300, 0.8 * c.dist));
    }
    centre.applyMatrix4(Rm);
    // the shadow camera stands SHADOW_BACK metres sunward of the box's centre and sees everything from there to as far
    // beyond: a ridge or a valley wall kilometres sunward of the ground it shades must lie in front of it (with the
    // light 1 km sunward and a negative near plane, as the other views tools place it, a valley wall's shadow across
    // the floor was lost: alpine floor_axis's floor lit where Blender's lies in the east wall's shadow)
    const sc = sun.shadow.camera;
    sc.left = -half; sc.right = half; sc.top = half; sc.bottom = -half;
    sc.near = 1.0; sc.far = 2.0 * SHADOW_BACK;
    sc.updateProjectionMatrix();
    sun.shadow.normalBias = 2.0 * (2 * half / V.shadowMap);
    // the sky first: its update sets the light's colour and strength and puts the light at 120 x the sun's direction
    // from the origin; then the light along the view's sun from the view's ground (the sky's own sun has the same
    // elevation, 37.7 degrees: its azimuth is the environment's, turned above)
    sky.update(0);
    sun.target.position.copy(centre);
    sun.position.copy(centre).add(sunV.clone().multiplyScalar(SHADOW_BACK));
    sun.target.updateMatrixWorld(true);
    sun.updateMatrixWorld(true);
    if (cur.plants) {
        await cur.plants.bindSun(c.sun);
        cur.plants.update(camera);
    }
    const W2 = V.W * V.k, H2 = V.H * V.k;
    const base = `${entry.dir}/${v.name}`;
    // the textured frame, scene-linear
    const t1 = performance.now();
    const tex = await linearFrame(r, scene, camera, W2, H2, V.msaa, 1.0);
    const firstS = secs(t1);
    writeFrame(`${base}.f16`, tex, { view: v.name, kind: 'textured', k: V.k, msaa: V.msaa });
    let secondS = null;
    if (V.second) {                                     // a second frame, timed (the first compiles)
        const t2 = performance.now();
        if (cur.plants) cur.plants.update(camera);
        await r.renderAsync(scene, camera);
        await r.backend.device.queue.onSubmittedWorkDone();
        secondS = +((performance.now() - t2) / 1000).toFixed(2);
    }
    // the layer map (review_views.layer_scene): the layer material on every ring, water black, the rest hidden
    let layersS = null;
    if (cur.lmat) {
        const t3 = performance.now();
        const mesh = cur.t.mesh;
        const built = mesh.material;
        mesh.material = [cur.lmat, cur.lmat];
        const black = new THREE.MeshBasicNodeMaterial({ color: 0x000000 });
        black.fog = false;
        const wmats = cur.water.map((o) => o.material);
        for (const o of cur.water) o.material = black;
        const shown = [];
        const keep = new Set([cur.world, mesh, ...cur.water]);
        for (const o of [...scene.children, ...cur.world.children]) {
            if (keep.has(o) || o.isLight) continue;
            shown.push([o, o.visible]);
            o.visible = false;
        }
        const bg = scene.background, bgn = scene.backgroundNode, fog = scene.fog, fogn = scene.fogNode;
        scene.background = null;
        if (bgn !== undefined) scene.backgroundNode = null;
        scene.fog = null;
        if (fogn !== undefined) scene.fogNode = null;
        const lay = await linearFrame(r, scene, camera, W2, H2, V.msaa, 0.0);
        writeFrame(`${base}_layers.f16`, lay, { view: v.name, kind: 'layers', k: V.k, msaa: V.msaa });
        scene.background = bg;
        if (bgn !== undefined) scene.backgroundNode = bgn;
        scene.fog = fog;
        if (fogn !== undefined) scene.fogNode = fogn;
        for (const [o, vis] of shown) o.visible = vis;
        cur.water.forEach((o, i) => { o.material = wmats[i]; });
        black.dispose();
        mesh.material = built;
        layersS = secs(t3);
    }
    // with V.clay (a probe, not a judge frame): the same frame with the ground in grey clay (albedo 0.18, roughness
    // 0.9, no specular: the reference rig's, surfacing.clay_material) and no plants or rocks, scene-linear: where the
    // sun and the sky's light fall, read apart from the surfacing (tests/surface_look/blender_clay.py renders
    // Blender's twin of it)
    if (V.clay) {
        const mesh = cur.t.mesh;
        const built = mesh.material;
        const clay = G.Sf.clayMaterial(THREE, 'probe_clay');
        mesh.material = [clay, clay];
        const hidden = [cur.plants?.group, cur.rocks?.group].filter(Boolean).map((o) => [o, o.visible]);
        for (const [o] of hidden) o.visible = false;
        // a new node frame, so the sun's shadow map is drawn again without the plants and rocks (three r184 draws it
        // once a frame: ShadowNode.updateBefore keys its WeakMap with [], so every camera shares one key), the clock
        // kept where the frame's is
        const nf = r._nodes?.nodeFrame;
        if (nf) {
            const tKeep = nf.time;
            nf.update();
            nf.time = tKeep;
            nf.deltaTime = 0;
        }
        const cl = await linearFrame(r, scene, camera, W2, H2, V.msaa, 1.0);
        writeFrame(`${base}_clay.f16`, cl, { view: v.name, kind: 'clay', k: V.k, msaa: V.msaa });
        for (const [o, vis] of hidden) o.visible = vis;
        mesh.material = built;
        clay.dispose();
    }
    const rec = { ...cur.rec, camera: c.eyeB.map((x) => +x.toFixed(1)), ground: +c.ground.toFixed(1),
        aim: c.aimB.map((x) => +x.toFixed(1)), lens: v.lens, heading_deg: +c.heading.toFixed(1), pitch_deg: +c.pitch.toFixed(2),
        focus: entry.focus, vista_m: v.vista_m ?? null, caption: v.caption, photo: v.photo ?? null, frame: v.frame,
        first_render_s: firstS, second_render_s: secondS, layers_render_s: layersS, view_s: secs(t0),
        layers: cur.lmat ? `${v.name}_layers.png` : null, palettes_file: V.palettesFile ?? null, k: V.k, msaa: V.msaa };
    G.records.push({ recipe: entry.recipe, view: v.name, record: rec });
    Deno.writeTextFileSync(V.recordPath, JSON.stringify(G.records, null, 1));
}

globalThis.renderFrame = async function (tt) {
    const G = globalThis._look;
    const k = Math.max(0, Math.min(G.frames.length - 1, Math.round(tt)));
    const entry = G.frames[k];
    if (!entry.done) {
        if (!G.cur || G.cur.g !== entry.g) {
            if (G.cur) {
                freeGroup(G.cur);
                G.cur = null;
            }
            const g = G.V.groups[entry.g];
            const t0 = performance.now();
            try {
                G.cur = { g: entry.g, ...(await buildGroup(G, g)) };
                G.cur.rec.build_s = secs(t0);
                console.log(`[look] ${g.recipe} ${g.snap.split('/').pop()}: built in ${G.cur.rec.build_s} s ${JSON.stringify(G.cur.rec.seconds)}`);
            } catch (e) {
                console.error(`[look] ${g.recipe} ${g.snap}: build failed: ${e.stack ?? e}`);
                G.records.push({ recipe: g.recipe, views: g.views, error: String(e.stack ?? e) });
                Deno.writeTextFileSync(G.V.recordPath, JSON.stringify(G.records, null, 1));
                G.cur = { g: entry.g, failed: true };
            }
        }
        entry.done = true;
        if (!G.cur.failed) {
            try {
                await renderView(G, entry);
                console.log(`[look] ${entry.recipe}/${entry.view} written`);
            } catch (e) {
                console.error(`[look] ${entry.recipe}/${entry.view}: ${e.stack ?? e}`);
                G.records.push({ recipe: entry.recipe, view: entry.view, error: String(e.stack ?? e) });
                Deno.writeTextFileSync(G.V.recordPath, JSON.stringify(G.records, null, 1));
            }
        }
    }
    if (G.cur?.plants) G.cur.plants.update(globalThis._c);
    await globalThis._r.renderAsync(globalThis._s, globalThis._c);
};
