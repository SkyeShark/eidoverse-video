// Port of blender/tests/terrain/plants/match_billboards.py at f9fba8c (SURFACING_DESIGN.md 4.4: "billboards are matched
// to LOD2 before they are used"; 5.4 package 4 item 2; PORT_PLAN.md 8.2 row P15): each billboard beside the level it
// takes over from. Every SeedThree individual an ecotope grows (every recipe's ecotope, as match_billboards'
// individuals() collects them), alone on one spot, rendered as its full level (LOD0), its card level (LOD2) and its
// billboard through build/plant_instances.js' still grove (the LOD pass' hero count and card distance set to show one
// level) at the distance where a stand hands one over to the other (SWITCH_M), under make_sky with the sun 70 degrees
// left of the view (the review's light: make_sky's shadows=False drops the clouds' shadows only, and the scene keeps
// EEVEE's own, render_references.new_scene's use_shadows, so the crown shades itself under the sun, here through a
// shadow map fitted to the plant), from the eye height, with a lens that frames the plant, the film
// transparent (the sky's own objects hidden, its light kept), at four turns of the plant. Measured within each
// silhouette (the display image's alpha over 0.5): the area, the mean colour (CIELAB of the display image's mean linear
// colour, surfacing_judge/measures.mean_lab) and the mean scene-linear colour (a float render: no tone mapping, no
// exposure; straight, as Blender's EXR is read). The billboard is matched to the level that stands before it in a stand
// (the card level, or the full level for a species whose lod billboard_m is no farther than its hero_m): its gain is
// that level's mean scene-linear colour over the billboard's (rendered without one), per channel, and its cut-out the
// threshold that keeps the share of its baked alpha that scales its silhouette to that level's; the billboard is
// rendered again with them. The bar: the mean colour within 3 ΔE and the silhouette's area within 10 %.
//
// Where this differs from match_billboards.py, and why: the sky's sun stands where make_sky puts it and the view turns
// about the plant to have it 70 degrees left (Blender turns the sun with make_sky's azimuth); the plant's turns are
// taken from the view's heading, so each turn shows the plant as Blender's does. Also rendered: the billboard with
// Blender's own gain (plant_instances.js BILLBOARD_GAIN, measured on Blender's bakes), to show what that table does to
// this edition's bakes (SeedThree's three.js bakes, not its Blender add-on's). The measured gains are printed as
// BILLBOARD_GAIN_WEBGPU entries, the table plant_instances.js takes before Blender's.
//
//     EIDO_GPU_WRAP='<the GPU queue>' deno run --config deno.json --frozen --allow-all \
//         eidoverse/terrain/tests/plants/billboards.mjs [--only douglasFir,redMaple] [--sheen] [--from <match.json>]
//         [--label <name>]
//
//     --sheen  a diagnosis (into tests/out/plants/billboards_sheen): each level also drawn without its specular lobe
//     --label  the run's own folder, tests/out/plants/billboards_<name>
//     --from   the checks of a match this test wrote, again, without rendering
//
// Writes tests/out/plants/billboards/<species>_<seed>_<key8>.png (per turn: the full level | the card level | the
// billboard | the billboard matched, display images on grey), match.json (per individual: colours, areas, gain and
// cut-out, ΔE and area before, with Blender's gain and after, and how much of its full level's area its card level
// covers) and billboards.json (the checks).

import * as S from './_plants.mjs';
import * as E from '../../build/ecotopes.js';
import * as P from '../../build/palettes.js';
import { grownDials, gainKey } from '../../build/plant_instances.js';

const A = S.argsOf();
const T = new S.C.Checks('plants: billboards matched to the level they take over from (match_billboards.py)');
const only = A.list('--only', null);
// --sheen (a diagnosis, its own folder): each level also without its specular lobe, to see what of its colour the sky's
// reflection makes
const sheen = A.flag('--sheen');
// --label <name>: a run of its own (tests/out/plants/billboards_<name>), beside the earlier ones
const label = A.opt('--label', null);
const out = `${S.W.out('plants')}/billboards${label ? '_' + label : sheen ? '_sheen' : ''}`;
const work = `${out}/_scenes`;
Deno.mkdirSync(work, { recursive: true });
const W = 960, H = 540;

// match_billboards.individuals: per individual (species, seed, the dials SeedThree grows) its kind, the largest
// size_m[1] of its users, its users and the level that stands before its billboard
const inds = new Map();
for (const r of Object.keys(P.RECIPE_PALETTES).sort()) {
    const eco = E.get('auto', r);
    for (const s of eco.species) {
        const [kind, id, opts, seeds] = s.source;
        if (kind !== 'seedthree' || (only && !only.includes(id))) continue;
        const level = Number(s.lod.billboard_m) > Number(s.lod.hero_m) ? 'card' : 'full';
        for (const sd of seeds) {
            const dials = grownDials(opts);
            const key = gainKey(id, sd, dials);
            const o = inds.get(key) ?? { key, id, seed: Math.trunc(Number(sd)), dials, kind: s.kind, size: 0, users: [], level };
            o.size = Math.max(o.size, Number(s.size_m[1]));
            o.users.push(`${eco.name}/${s.name}`);
            inds.set(key, o);
        }
    }
}
const cases = [...inds.values()];
for (const c of cases) {
    const h = new Uint8Array(await crypto.subtle.digest('SHA-1', new TextEncoder().encode(c.key)));
    c.tag = `${c.id}_${c.seed}_${[...h.slice(0, 4)].map((b) => b.toString(16).padStart(2, '0')).join('')}`;
}
const spec = { cases, W, H, out, result: `${work}/match.json`, exposureEv: -0.5, hours: 15.5, sunLeftDeg: 70.0,
    switchM: { tree: 60.0, shrub: 120.0 }, yaws: [0.0, 25.0, 50.0, 75.0], fill: 0.6, eye: 1.7, cutRange: [0.2, 0.9], sheen };
try { Deno.removeSync(spec.result); } catch (_e) { /* none yet */ }

const script = `// The plants package's billboard match (eidoverse/terrain/tests/plants/billboards.mjs writes this file).
globalThis.setup = async function () {
    const V = ${JSON.stringify(spec)};
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE, reversedDepthBuffer: true });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping;
    renderer.toneMappingExposure = Math.pow(2, V.exposureEv);
    renderer.shadowMap.enabled = true;                 // the crown's own shadow under the sun, as EEVEE's
    await renderer.init();
    globalThis._r = renderer;
    globalThis._noAutoEnhance = true;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(20, WIDTH / HEIGHT, 0.5, 20000);
    globalThis._s = scene;
    globalThis._c = camera;
    const sun = new THREE.DirectionalLight(0xffffff, 1.0);
    scene.add(sun, sun.target);
    globalThis.EANPA_NO_MRT = true;
    eval(Deno.readTextFileSync('eidoverse/sky_worlds.js'));
    const sky = await makeSky({ scene, camera, renderer, world: 'earth', hours: V.hours, clouds: 'cumulus', weather: null, sun, audio: false });
    sky.update(0);
    await sky.bakeEnv();
    // one throwaway frame with a lit, shadowed plate first (as tests/surface_look/_scene.js has it): three r184 reverses
    // a camera's depth at its first render, and the sun's first shadow map is taken before that, reversed against its
    // lookup
    {
        sun.castShadow = true;
        sun.shadow.mapSize.set(4096, 4096);
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
    globalThis._b = { V, sky, sun, R: await G.init({ renderer }), PL: await import(EIDOVERSE_DIR + 'terrain/build/plants.js'),
        PI: await import(EIDOVERSE_DIR + 'terrain/build/plant_instances.js'), Io: await import(EIDOVERSE_DIR + 'terrain/core/io.js'),
        skyObjs: scene.children.filter((o) => o !== sun && o !== sun.target), results: [], shown: null, k: -1,
        rtD: new THREE.RenderTarget(WIDTH, HEIGHT),
        rtL: new THREE.RenderTarget(WIDTH, HEIGHT, { type: THREE.HalfFloatType, samples: 4 }) };
};

// one spot of an individual at the origin (match_billboards.plant: its yaw, scale 1, a neutral tone, upright)
function oneSpot(PL, c) {
    const rec = new Float32Array(12);
    rec[4] = 1.0;
    rec[6] = 0.5;
    rec[9] = 1.0;
    const entry = { name: c.id + ' ' + c.seed, kind: c.kind, source: { seedthree: c.id, dials: c.dials, seeds: [c.seed] },
        size_m: [0.5 * c.size, c.size], sink: 0.0, foot_m: 0.0, core_m: 0.0, crown_m: 0.0,
        lod: { hero_m: 1.0e9, billboard_m: 1.0e9, near_m: 0.0 }, count: 1, fields: [...PL.FIELDS] };
    return new PL.PlantSpots({ format: PL.FORMAT, focus: [[0, 0]], seed: 0, ecotope: 'match', terrain: null, species: [entry] },
        [entry], { [entry.name]: rec });
}

// match_billboards.show: one level through the LOD pass' hero count and card distance
function show(st, lv) {
    const p = st.pass;
    if (lv === 'full') { p.uHeroM.value = 1.0e9; p.uHeroK.value = Math.max(1, st.hero_k); p.uCardM.value = 1.0e9; }
    else if (lv === 'card') { p.uHeroK.value = 0; p.uCardM.value = 1.0e9; }
    else { p.uHeroK.value = 0; p.uCardM.value = 0.0; }
}

// one frame, twice: the display image (the output pass into an 8-bit target: AgX at the exposure, sRGB) and the
// scene-linear one (a half-float target: no tone mapping)
async function shoot(B, plants) {
    const r = globalThis._r, scene = globalThis._s, camera = globalThis._c;
    plants.update(camera);
    r.setOutputRenderTarget(B.rtD);
    r.setRenderTarget(null);
    await r.renderAsync(scene, camera);
    const d = await r.readRenderTargetPixelsAsync(B.rtD, 0, 0, WIDTH, HEIGHT);
    r.setOutputRenderTarget(null);
    r.setRenderTarget(B.rtL);
    await r.renderAsync(scene, camera);
    const l = await r.readRenderTargetPixelsAsync(B.rtL, 0, 0, WIDTH, HEIGHT);
    r.setRenderTarget(null);
    return { d: new Uint8Array(d.buffer, d.byteOffset, WIDTH * HEIGHT * 4).slice(), l };
}

const toLin = (x) => (x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
// measures.srgb_to_lab of linear_to_srgb(m): CIELAB of a linear colour (D65)
function labOf(m) {
    const [R1, G1, B1] = m;
    const X = (0.4124 * R1 + 0.3576 * G1 + 0.1805 * B1) / 0.95047, Y = 0.2126 * R1 + 0.7152 * G1 + 0.0722 * B1;
    const Z = (0.0193 * R1 + 0.1192 * G1 + 0.9505 * B1) / 1.08883;
    const f = (t) => (t > (6 / 29) ** 3 ? Math.cbrt(Math.max(t, 0)) : t / (3 * (6 / 29) ** 2) + 4 / 29);
    return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))];
}
const dE = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

// match_billboards.stats: the silhouette (display alpha over 0.5), its area, mean Lab and mean scene-linear colour
function stats(shot) {
    const { d, l } = shot;
    const half = THREE.DataUtils.fromHalfFloat;
    let n = 0;
    const dl = [0, 0, 0], ln = [0, 0, 0];
    for (let i = 0, N = WIDTH * HEIGHT; i < N; i++) {
        const a = d[4 * i + 3] / 255;
        if (a <= 0.5) continue;
        n++;
        for (let c = 0; c < 3; c++) dl[c] += toLin(Math.min(1, d[4 * i + c] / 255 / a));
        const la = half(l[4 * i + 3]);
        for (let c = 0; c < 3; c++) ln[c] += la > 1e-6 ? half(l[4 * i + c]) / la : 0.0;
    }
    if (!n) return { area: 0, lab: [0, 0, 0], linear: [0, 0, 0] };
    return { area: n, lab: labOf(dl.map((v) => v / n)).map((v) => +v.toFixed(2)), linear: ln.map((v) => v / n) };
}

// the baked alpha of an individual's two billboard cards as a histogram of its 8-bit values
function alphaHist(p) {
    const h = new Float64Array(256);
    let any = false;
    for (const side of ['front', 'side']) {
        const tex = p?.billboard?.textures?.[side]?.albedo;
        let data = tex?.image?.data ?? null;
        if (!data && tex?.image?.getContext) {
            const im = tex.image;
            data = im.getContext('2d').getImageData(0, 0, im.width, im.height).data;
        }
        if (!data) continue;
        any = true;
        for (let i = 3; i < data.length; i += 4) h[data[i]]++;
    }
    return any ? h : null;
}

// match_billboards.matching_cut: the cut-out keeping 1 / ratio of the texels the default keeps, within CUT_RANGE
function matchingCut(hist, ratio, cut, range) {
    if (!hist || Math.abs(ratio - 1.0) <= 0.10) return cut;
    let tot = 0;
    for (const c of hist) tot += c;
    const frac = (t) => { let k = 0; for (let v = 0; v < 256; v++) if (v / 255 > t) k += hist[v]; return k / tot; };
    const want = frac(cut) / ratio;
    let lo = ratio > 1.0 ? cut : range[0], hi = ratio > 1.0 ? range[1] : cut;
    for (let it = 0; it < 40; it++) {
        const mid = 0.5 * (lo + hi);
        if (frac(mid) > want) lo = mid;
        else hi = mid;
    }
    return Math.round(500 * (lo + hi)) / 1000;
}

// a display image straight over grey, half size (match_billboards.board's tiles)
function tile(d) {
    const w = WIDTH / 2, h = HEIGHT / 2, t = new Uint8Array(w * h * 3);
    for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
            const acc = [0, 0, 0];
            for (const [dx, dy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
                const i = 4 * ((2 * y + dy) * WIDTH + 2 * x + dx);
                const a = d[i + 3] / 255;
                for (let c = 0; c < 3; c++) acc[c] += (a > 0 ? Math.min(255, d[i + c] / a) : 0) * a + 128 * (1 - a);
            }
            for (let c = 0; c < 3; c++) t[3 * (y * w + x) + c] = Math.round(acc[c] / 4);
        }
    }
    return t;
}

async function board(B, path, rows) {
    const w = WIDTH / 2, h = HEIGHT / 2, cols = Math.max(...rows.map((r) => r.length));
    const BW = w * cols, BH = h * rows.length;
    const px = new Uint32Array(BW * BH * 4).fill(40);
    rows.forEach((row, j) => row.forEach((d, i) => {
        const t = tile(d);
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const o = 4 * ((j * h + y) * BW + i * w + x);
                for (let c = 0; c < 3; c++) px[o + c] = t[3 * (y * w + x) + c];
                px[o + 3] = 255;
            }
        }
    }));
    const f = B.R.field(BH, BW * 4, 1, px, 'u32');
    await B.Io.writePng(path, { field: f, width: BW, height: BH, channels: 4, bitDepth: 8 });
    f.destroy();
}

async function matchOne(B, c) {
    const V = B.V, PI = B.PI, r = globalThis._r, camera = globalThis._c, scene = globalThis._s;
    const t0 = performance.now();
    const dist = V.switchM[c.kind] ?? V.switchM.tree;
    // the view: the sky's sun 70 degrees left of it, the plant at the origin, the camera at the eye height
    const s0 = B.sky.sunDir;
    const az = Math.atan2(-s0.z, s0.x) - V.sunLeftDeg * Math.PI / 180;
    camera.position.set(-dist * Math.cos(az), V.eye, dist * Math.sin(az));
    camera.up.set(0, 1, 0);
    camera.lookAt(0, 0.5 * c.size, 0);
    camera.fov = 2 * Math.atan(0.5 * c.size / V.fill / dist) * 180 / Math.PI;
    camera.near = 0.5;
    camera.far = 4.0 * dist + 100.0;
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
    B.sky.update(0);
    const s = B.sky.sunDir;
    B.sun.target.position.set(0, 0.5 * c.size, 0);
    B.sun.position.set(s.x * 1000, 0.5 * c.size + s.y * 1000, s.z * 1000);
    B.sun.target.updateMatrixWorld(true);
    B.sun.updateMatrixWorld(true);
    // the sun's shadow over the plant alone: an orthographic map round it, 4096 texels over 1.4 x its height (a
    // few millimetres a texel on a shrub, a centimetre on a 30 m tree: each leaf's own shadow), from 1 km sunward
    B.sun.castShadow = true;
    const sc = B.sun.shadow.camera, half = 0.7 * c.size + 1.0;
    sc.left = -half; sc.right = half; sc.top = half; sc.bottom = -half;
    sc.near = 1000.0 - 2.0 * half; sc.far = 1000.0 + 2.0 * half;
    sc.updateProjectionMatrix();
    B.sun.shadow.mapSize.set(4096, 4096);
    B.sun.shadow.bias = -0.0002;
    B.sun.shadow.normalBias = 2.0 * (2 * half / 4096);
    B.sun.shadow.needsUpdate = true;
    // the film transparent: the sky's objects and background hidden, its light (the sun, the baked environment) kept
    const bg = scene.background;
    scene.background = null;
    for (const o of B.skyObjs) o.visible = false;
    r.setClearColor(0x000000, 0);
    const variant = async (gainEntry, levels, keep = false, noSpec = false) => {
        const plants = await PI.instancePlants(oneSpot(B.PL, c), null, { renderer: r, R: B.R, log: null,
            billboardGains: { [c.key]: gainEntry } });
        if (noSpec) {                                    // --sheen: the levels' copies without their specular lobe
            plants.group.traverse((o) => {
                for (const m of [o.material].flat()) if (m?.isMeshPhysicalNodeMaterial && !m.userData?.eidoBillboard) m.specularIntensity = 0.0;
            });
        }
        scene.add(plants.group);
        await plants.bindSun([s.x, s.y, s.z]);
        const st = plants._still[0];
        const got = [];
        for (const yaw of V.yaws) {
            st.rec[3] = yaw * Math.PI / 180 + az;            // the plant turned as Blender's, against the view
            st.recAttr.needsUpdate = true;
            const g = {};
            for (const lv of levels) {
                show(st, lv);
                g[lv] = await shoot(B, plants);
            }
            got.push(g);
        }
        if (keep) return { got, plants, st };
        plants.dispose();
        return { got };
    };
    const base = await variant(null, ['full', 'card', 'billboard']);
    const per = base.got.map((g, k) => ({ yaw: V.yaws[k], full: stats(g.full), card: stats(g.card), billboard: stats(g.billboard) }));
    if (V.sheen) {
        const flat = await variant(null, ['full', 'card'], false, true);
        per.forEach((p, k) => { p.full_nospec = stats(flat.got[k].full); p.card_nospec = stats(flat.got[k].card); });
    }
    const lv = c.level;
    const mean = (f) => [0, 1, 2].map((ch) => per.reduce((a, p) => a + f(p)[ch], 0) / per.length);
    const refLin = mean((p) => p[lv].linear), bbLin = mean((p) => p.billboard.linear);
    const gain = refLin.map((v, ch) => +Math.min(2.0, Math.max(0.2, v / Math.max(bbLin[ch], 1e-6))).toFixed(3));
    const ratio0 = per.reduce((a, p) => a + p.billboard.area / Math.max(p[lv].area, 1), 0) / per.length;
    const grown = await PI.growSeedThree(c.id, c.seed, c.dials, { renderer: r });
    const cut = matchingCut(alphaHist(grown), ratio0, PI.ALPHA_CUT, V.cutRange);
    const bl = PI.billboardGain(c.id, c.seed, c.dials);
    const withBl = await variant(bl ?? null, ['billboard']);
    const after = await variant({ gain, alpha: cut }, ['billboard'], true);
    per.forEach((p, k) => {
        p.blender = stats(withBl.got[k].billboard);
        p.gained = stats(after.got[k].billboard);
        p.de_before = +dE(p[lv].lab, p.billboard.lab).toFixed(2);
        p.de_blender = +dE(p[lv].lab, p.blender.lab).toFixed(2);
        p.de_after = +dE(p[lv].lab, p.gained.lab).toFixed(2);
        p.area_ratio = +(p.billboard.area / Math.max(p[lv].area, 1)).toFixed(3);
        p.area_ratio_blender = +(p.blender.area / Math.max(p[lv].area, 1)).toFixed(3);
        p.area_ratio_after = +(p.gained.area / Math.max(p[lv].area, 1)).toFixed(3);
        p.card_over_full = +(p.card.area / Math.max(p.full.area, 1)).toFixed(3);
        for (const q of [p.full, p.card, p.billboard, p.blender, p.gained]) q.linear = q.linear.map((v) => +v.toFixed(5));
    });
    await board(B, V.out + '/' + c.tag + '.png', base.got.map((g, k) => [g.full.d, g.card.d, g.billboard.d, after.got[k].billboard.d]));
    const avg = (f) => +(per.reduce((a, p) => a + f(p), 0) / per.length).toFixed(3);
    const rec = { tag: c.tag, key: c.key, species: c.id, seed: c.seed, dials: c.dials, kind: c.kind, size_m: c.size, users: c.users,
        switch_m: dist, matched_to: lv, gain, alpha: cut, blender: bl, turns: per, card_over_full: avg((p) => p.card_over_full),
        de_before: avg((p) => p.de_before), de_blender: avg((p) => p.de_blender), de_after: avg((p) => p.de_after),
        area_ratio: avg((p) => p.area_ratio), area_ratio_blender: avg((p) => p.area_ratio_blender),
        area_ratio_after: avg((p) => p.area_ratio_after), seconds: +((performance.now() - t0) / 1000).toFixed(1) };
    rec.passed = rec.de_after <= 3.0 && Math.abs(rec.area_ratio_after - 1.0) <= 0.10;
    console.log('[match] ' + c.tag + ' (' + [...new Set(c.users)].sort().join(', ') + '): against its ' + lv + ' level: gain ' +
        JSON.stringify(gain) + ', alpha ' + cut + ', ΔE ' + rec.de_before + ' -> ' + rec.de_after + ' (Blender\\'s gain: ' + rec.de_blender +
        '), area ratio ' + rec.area_ratio + ' -> ' + rec.area_ratio_after + '; its card level covers ' + rec.card_over_full +
        ' of its full level (' + rec.seconds + ' s)');
    // the canvas frame: the matched billboard under the sky
    scene.background = bg;
    for (const o of B.skyObjs) o.visible = true;
    show(after.st, 'billboard');
    B.shown = after.plants;
    return rec;
}

globalThis.renderFrame = async function (tt) {
    const B = globalThis._b;
    const k = Math.max(0, Math.min(B.V.cases.length - 1, Math.round(tt)));
    if (B.k !== k) {
        B.k = k;
        if (B.shown) { B.shown.dispose(); B.shown = null; }
        B.results.push(await matchOne(B, B.V.cases[k]));
        Deno.writeTextFileSync(B.V.result, JSON.stringify(B.results, null, 1));
    }
    const r = globalThis._r;
    B.shown?.update(globalThis._c);
    await r.renderAsync(globalThis._s, globalThis._c);
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
// --from <a match.json this test wrote>: its checks again, no render
const from = A.opt('--from', null);
let res;
if (from) res = JSON.parse(Deno.readTextFileSync(from));
else {
    const argv = S.W.gpuArgv([S.W.norm(Deno.execPath()), 'run', '--allow-all', '--unstable-webgpu', '--node-modules-dir=auto',
        'eidoverse/render_scene.mjs', rel(config)], { cwd: S.W.REPO });
    const log = `${work}/billboards.log`;
    const code = await S.W.run(argv, { cwd: S.W.REPO, log, env: { ...Deno.env.toObject(), RENDER_CODEC: 'libx264', RENDER_CQ: '0' } });
    T.ok('the render job ran', code === 0, `exit ${code}; ${log}`);
    res = S.W.exists(spec.result) ? JSON.parse(Deno.readTextFileSync(spec.result)) : [];
    Deno.writeTextFileSync(`${out}/match.json`, JSON.stringify(res, null, 1));
}
T.ok('every individual measured', res.length === cases.length, `${res.length} of ${cases.length}`);
for (const r of res) {
    const tag = `${r.species} ${r.seed} ${JSON.stringify(r.dials)} (${[...new Set(r.users)].join(', ')})`;
    T.ok(`${tag}: its billboard matched to its ${r.matched_to} level within 3 ΔE`, r.de_after <= 3.0,
        `ΔE ${r.de_before} without a gain, ${r.de_blender} with Blender's ${JSON.stringify(r.blender?.gain ?? null)}, ` +
        `${r.de_after} with the measured ${JSON.stringify(r.gain)}`);
    T.ok(`${tag}: its silhouette's area within 10 % of its ${r.matched_to} level's`, Math.abs(r.area_ratio_after - 1.0) <= 0.10,
        `area ratio ${r.area_ratio} at cut ${0.35}, ${r.area_ratio_after} at the measured cut ${r.alpha}`);
}
console.log('\n// BILLBOARD_GAIN_WEBGPU entries (plant_instances.js):');
for (const r of res) console.log(`    '${r.key}': { gain: [${r.gain.join(', ')}], alpha: ${r.alpha} },   // ΔE ${r.de_before} -> ${r.de_after}, area ${r.area_ratio_after}`);
Deno.exit(S.finish(T, sheen ? 'billboards_sheen' : 'billboards', { results: res.map((r) => ({ ...r, turns: undefined })) }));
