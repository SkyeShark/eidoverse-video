// The API against Blender's (PORT_PLAN.md 7.1, 7.2, 7.4, 8.2 P4): api.js on Blender Terrain.save files, compared
// with what Blender's own api.py gives for the same save (api_expected.py, run by Blender's Python).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/mesh_api/api_test.mjs [case ...]
//
// (from the repository root; on a shared machine put $EIDO_GPU_WRAP in front). Checks
//   options     an unknown option, an old makeTerrain option, a missing recipe, a bad quality, an unknown knob and
//               an unknown flatten key each raise naming the nearest; the frames (focus, flatten) convert
//   load        Terrain.load of the Blender save: only h is read until a field is asked for; the level specs give
//               Blender's indices and errors; heightAt and normalAt are the ring mesh's in three.js axes
//   masks       the names equal; Mask.at at Blender's 300 points equal to 1e-12 relative
//   viewpoint   every case of api_expected.py: the same error, or the same standing point (heading and distance
//               equal, the eye within 1e-3 m: the two meshes' heights differ by float32 rounding)
//   flatten     flattenFields on the GPU: Blender's resolved heights to the bit, the same levels changed, inside each
//               area exactly its height, beyond the falloff the input to the bit, the blend within 1e-5 of the range
//   save        Terrain.save of the loaded terrain: the .npz byte-identical to the Blender file, the .json equal as
//               JSON to Blender's own load -> save; the parity record written
//   plants      t.plants from Blender's spots files; saved again, every .f32 byte-identical and the JSON equal
//   scene       the mesh (two NodeMaterials, a group per ring), the collider proxy, the exact ray caster installed,
//               `const { mesh, heightAt, masks } = t`

import * as G from '../../core/gpu.js';
import * as A from '../../api.js';
import { Terrain, makeTerrain, recipes } from '../../index.js';
import * as C from './_common.mjs';

const args = Deno.args.filter((a) => !a.startsWith('--'));
const cases = C.fixtureCases(args.length ? args : null, C.API_FIXTURES);
if (!cases) Deno.exit(0);
const R = await G.init();
const T = new C.Checks('mesh and API: api.js against api.py');
T.extra.cases = {};
const quiet = () => {};
const rel = (a, b) => Math.abs(a - b) / Math.max(Math.abs(b), 1);

// ------------------------------------------------------------------------------------------------ options ---

async function optionChecks() {
    let r = await C.throwsWith(() => makeTerrain({ recipe: 'real_place', hero_cell: 1 }), ["'hero_cell'", 'heroCell'], 'TypeError');
    T.ok('options: an unknown option names the nearest (hero_cell -> heroCell)', r.ok, r.message);
    r = await C.throwsWith(() => makeTerrain({ size: 80, segments: 160, amplitude: 3 }), ['old makeTerrain', 'recipe', 'heightAt'], 'TypeError');
    T.ok('options: an old makeTerrain option names the new call and the nearest option', r.ok, r.message);
    r = await C.throwsWith(() => makeTerrain({ seed: 1 }), ['needs a recipe'], 'TypeError');
    T.ok('options: a call without a recipe says so', r.ok, r.message);
    r = await C.throwsWith(() => makeTerrain({ recipe: 'real_place', quality: 'flim' }), ["quality 'flim'", 'film'], 'ValueError');
    T.ok('options: a bad quality names the nearest', r.ok, r.message);
    r = await C.throwsWith(() => makeTerrain(['real_place']), ['one options object']);
    T.ok('options: a call that is not an options object says how to call it', r.ok, r.message);
    const names = recipes.names();
    if (names.includes('real_place')) {
        r = await C.throwsWith(() => makeTerrain({ recipe: 'real_plce' }), ["no recipe 'real_plce'", 'real_place'], 'KeyError');
        T.ok('options: an unknown recipe names the nearest', r.ok, r.message);
        r = await C.throwsWith(() => makeTerrain({ recipe: 'real_place', params: { bse: 'min' } }), ["no knob 'bse'", 'base'], 'KeyError');
        T.ok('options: an unknown knob names the nearest', r.ok, r.message);
    } else {
        T.ok('options: an unknown recipe and an unknown knob name the nearest', false, `recipes/real_place.js is not registered (${names.join(', ') || 'no recipes'})`);
    }
    r = await C.throwsWith(async () => A.checkFlatten([{ at: [0, 0], radus: 3 }]), ["unknown key 'radus'", 'radius'], 'KeyError');
    T.ok('options: an unknown flatten key names the nearest', r.ok, r.message);
    r = await C.throwsWith(async () => A.checkFlatten([{ radius: 3 }]), ["needs 'at'"], 'KeyError');
    T.ok('options: a flatten area without `at` says so', r.ok, r.message);
    // frames: a three.js ground point [x, z] is Blender (x, -z); a position [x, y, z] is (x, -z); an Object3D its world position
    const obj = { isObject3D: true, matrixWorld: { elements: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 7, 8, 9, 1] }, updateWorldMatrix() {} };
    const f = [A.blenderFocus([3, 4]), A.blenderFocus([[3, 4], [5, 60, 7]]), A.blenderFocus(obj), A.blenderFocus([obj, { isVector3: true, x: 1, y: 2, z: 3 }]),
        A.blenderFocus(null)];
    T.ok('frames: focus [x, z], positions, an Object3D and lists of them become Blender (x, -z)',
        C.sameJson(f, [[[3, -4]], [[3, -4], [5, -7]], [[7, -9]], [[7, -9], [1, -3]], null]), JSON.stringify(f));
    const fl = A.checkFlatten([{ at: [40, 12], radius: 15 }, { at: [1, 2], size: [30, 20], angleDeg: 30, height: 5 }]);
    T.ok('frames: flatten areas become Blender\'s (at (x, -z), angle_deg; falloff = the radius, or 10 for a rectangle)',
        C.sameJson(fl, [{ at: [40, -12], radius: 15, falloff: 15 }, { at: [1, -2], height: 5, size: [30, 20], angle_deg: 30, falloff: 10 }]), JSON.stringify(fl));
}

// --------------------------------------------------------------------------------------------- one save ---

async function checkCase(name) {
    const man = C.manifest(name, C.API_FIXTURES);
    const rec = {};
    T.extra.cases[name] = rec;
    const base = C.blenderPath(man.save);
    const tag = (s) => `${name}: ${s}`;
    const arr = (k) => C.arr(name, man, k, C.API_FIXTURES);
    const spots = man.plants?.files ? C.urlPath(new URL(`${name}/spots`, C.API_FIXTURES)) : false;

    let t0 = performance.now();
    const t = await Terrain.load(base, { build: false, plants: spots });
    rec.load_s = +((performance.now() - t0) / 1000).toFixed(3);
    rec.blender_load_s = man.seconds_load;

    // load: lazy arrays, levels
    const loadedBefore = t.levels.map((_, i) => t._fields[i].names().filter((k) => t._fields[i].loaded(k)));
    const masksLoaded = t.levels.map((_, i) => t.masks._stack[i].names().filter((k) => t.masks._stack[i].loaded(k)).length);
    T.ok(tag('load reads only h of every level (and no mask) until an array is asked for'),
        loadedBefore.every((l) => C.sameJson(l, ['h'])) && masksLoaded.every((c) => c === 0),
        `loaded fields per level ${JSON.stringify(loadedBefore)}; masks loaded ${masksLoaded}; ${rec.load_s} s (Blender ${man.seconds_load} s)`);
    const fmain = t.fields('main');
    const A0 = fmain.A;
    T.ok(tag('t.fields(level) lists every field and reads one when asked'),
        Object.keys(fmain).length === t._fields[t.main.index].names().length && A0 instanceof Float32Array && A0.length === t.main.n ** 2 &&
        t._fields[t.main.index].loaded('A'), `${Object.keys(fmain).join(', ')}`);
    let lvOk = true, lvWhy = '';
    for (const [spec, want] of Object.entries(man.level_index)) {
        const s = /^-?\d+$/.test(spec) ? parseInt(spec, 10) : spec;
        let got;
        try {
            got = A.levelIndex(t.levels, s);
        } catch (e) {
            got = { error: e.message };
        }
        if (!C.sameJson(got, want)) { lvOk = false; lvWhy ||= `${spec}: ${JSON.stringify(got)} vs ${JSON.stringify(want)}`; }
    }
    T.ok(tag('level specs (roles, first, last, indices) give Blender\'s levels and errors'), lvOk, lvWhy || Object.keys(man.level_index).join(', '));

    // masks
    T.ok(tag('mask names equal'), C.sameJson(t.masks.names(), man.mask_names), `${t.masks.names().length} masks`);
    const mx = arr('mask_x'), my = arr('mask_y');
    const mz = Float64Array.from(my, (v) => -v);
    let mWorst = 0, mWhere = '';
    for (const mn of man.masks_at) {
        const want = arr(`mask_at_${mn}`);
        const got = t.mask(mn).at(mx, mz);
        for (let q = 0; q < want.length; q++) {
            const d = rel(got[q], want[q]);
            if (d > mWorst) { mWorst = d; mWhere = `${mn}[${q}]: ${got[q]} vs ${want[q]}`; }
        }
    }
    const sc = man.mask_at_scalar;
    const scalar = t.mask('slope').at(sc.x, -sc.y);
    T.ok(tag('Mask.at at Blender\'s points equal to 1e-12 relative (arrays and numbers)'), mWorst <= 1e-12 && rel(scalar, sc.slope) <= 1e-12,
        `${man.masks_at.join(', ')} at ${mx.length} points: worst ${mWorst.toExponential(2)}${mWorst > 1e-12 ? ' at ' + mWhere : ''}`);
    let skipWhy = '';
    try {
        t.mask('slpoe');
    } catch (e) {
        skipWhy = e.message;
    }
    T.ok(tag('an unknown mask names the nearest'), skipWhy.includes('slope'), skipWhy);

    // heightAt / normalAt in three.js axes
    const rm = t.ring;
    let hOk = true, nOk = true;
    for (let q = 0; q < 200; q++) {
        const x = mx[q], y = my[q];
        if (t.heightAt(x, -y) !== rm.heightAt(x, y)) hOk = false;
        const n3 = t.normalAt(x, -y), nb = rm.normalAt(x, y, true);
        if (n3[0] !== nb[0] || n3[1] !== nb[2] || n3[2] !== -nb[1]) nOk = false;
    }
    const hArr = t.heightAt(mx.subarray(0, 50), mz.subarray(0, 50));
    let arrOk = hArr instanceof Float64Array && hArr.length === 50;
    for (let q = 0; q < 50 && arrOk; q++) if (hArr[q] !== rm.heightAt(mx[q], my[q])) arrOk = false;
    T.ok(tag('heightAt(x, z) is the ring mesh\'s height at Blender (x, -z); normalAt its normal as (nx, nz, -ny); arrays work'), hOk && nOk && arrOk, '');

    // viewpoints
    let vOk = true, vWhy = '', found = 0, worstEye = 0;
    t0 = performance.now();
    for (const v of man.viewpoints) {
        const a = v.args, want = v.result;
        const target = a.target.length > 2 ? [a.target[0], a.target[2], -a.target[1]] : [a.target[0], -a.target[1]];
        const o = {};
        if ('prefer' in a) o.prefer = a.prefer;
        if ('heading' in a) o.heading = a.heading;
        if ('eye_height' in a) o.eyeHeight = a.eye_height;
        if ('look_dz' in a) o.lookDy = a.look_dz;
        if ('clearance_m' in a) o.clearanceM = a.clearance_m;
        if ('max_slope_deg' in a) o.maxSlopeDeg = a.max_slope_deg;
        if ('within' in a) o.within = a.within;
        if ('lens_mm' in a) o.lensMm = a.lens_mm;
        let got;
        try {
            got = t.viewpoint(target, a.distance, o);
        } catch (e) {
            got = { error: e.message };
        }
        if (want.error !== undefined) {
            // the same sentence; the point it names is three.js (x, z) here, and the option is lookDy
            const norm = (s) => s.replace(/look_dz/g, 'lookDy').replace(/\((-?[\d.]+), (-?[\d.]+)\)/g, (_m, x, y) => `(${x}, ${Math.abs(Number(y))})`);
            if (got.error === undefined || norm(got.error) !== norm(want.error)) { vOk = false; vWhy ||= `${JSON.stringify(a)}: ${JSON.stringify(got).slice(0, 200)} vs ${want.error}`; }
            continue;
        }
        if (got.error !== undefined) { vOk = false; vWhy ||= `${JSON.stringify(a)}: ${got.error}`; continue; }
        found++;
        const eyeB = [got.eye[0], -got.eye[2], got.eye[1]], tgtB = [got.target[0], -got.target[2], got.target[1]];
        const dEye = Math.hypot(eyeB[0] - want.eye[0], eyeB[1] - want.eye[1], eyeB[2] - want.eye[2]);
        worstEye = Math.max(worstEye, dEye);
        const same = dEye <= 1e-3 && Math.hypot(tgtB[0] - want.target[0], tgtB[1] - want.target[1], tgtB[2] - want.target[2]) <= 1e-3 &&
            Math.abs(got.groundY - want.ground_z) <= 1e-3 && got.headingDeg === want.heading_deg && Math.abs(got.pitchDeg - want.pitch_deg) <= 1e-4 &&
            rel(got.distance, want.distance) <= 1e-12 && Math.abs(got.clearanceM - want.clearance_m) <= 1e-3 && got.lensMm === want.lens_mm;
        if (!same) { vOk = false; vWhy ||= `${JSON.stringify(a)}: ${JSON.stringify(got)} vs ${JSON.stringify(want)}`; }
    }
    rec.viewpoint_s = +((performance.now() - t0) / 1000).toFixed(3);
    T.ok(tag('viewpoint: Blender\'s standing point or Blender\'s error in every case'), vOk,
        vWhy || `${found} found, ${man.viewpoints.length - found} errors equal; eyes within ${worstEye.toExponential(2)} m; ${rec.viewpoint_s} s for ${man.viewpoints.length} calls`);
    const cam = { position: { set(...v) { this.v = v; } }, up: { set() {} }, lookAt(...v) { this.at = v; }, isPerspectiveCamera: true,
        setFocalLength(f) { this.lens = f; }, updateMatrixWorld() {} };
    const vp0 = man.viewpoints.find((v) => v.result.error === undefined);
    if (vp0) {
        const vp = t.viewpoint([vp0.args.target[0], -vp0.args.target[1]], vp0.args.distance);
        A.placeCamera(vp, cam);
        T.ok(tag('placeCamera sets a camera at the eye, toward the target, with the lens on a 36 mm film'),
            C.sameJson(cam.position.v, vp.eye) && C.sameJson(cam.at, vp.target) && cam.lens === 35 && cam.filmGauge === 36, '');
    }

    // flatten
    await flattenChecks(name, man, t, tag, arr, rec);

    // save
    const outBase = C.urlPath(C.outUrl(`saved/${name}`));
    t0 = performance.now();
    const p = await t.save(outBase);
    rec.save_s = +((performance.now() - t0) / 1000).toFixed(2);
    const sha = await C.sha1File(p);
    T.ok(tag('save: the .npz is byte-identical to the Blender file'), sha === man.resave.original_npz_sha1,
        `sha1 ${sha} (${(Deno.statSync(p).size / 1e6).toFixed(0)} MB in ${rec.save_s} s); Blender's own load -> save ${man.resave.resaved_npz_sha1 === man.resave.original_npz_sha1 ? 'is too' : 'differs'}`);
    const js = JSON.parse(Deno.readTextFileSync(outBase + '.json'));
    T.ok(tag('save: the .json equals Blender\'s own load -> save as JSON'), C.sameJson(js, man.resave.resaved_json), C.jsonDiff(js, man.resave.resaved_json) ?? `${Object.keys(js).length} keys`);
    const par = JSON.parse(Deno.readTextFileSync(outBase + '_parity.json'));
    T.ok(tag('save: the parity record names the edition, the commit, the code hashes, the GPU and Deno'),
        par.edition === 'three.js' && typeof par.field_code_hash === 'string' && typeof par.terrain_code_hash === 'string' && par.deno === Deno.version.deno &&
        typeof par.gpu === 'string' && par.gpu.length > 0, JSON.stringify(par));
    // a port save loads again and gives the same ground
    const t2 = await Terrain.load(outBase, { build: false });
    let again = true;
    for (let q = 0; q < 300; q++) if (t2.heightAt(mx[q], mz[q]) !== t.heightAt(mx[q], mz[q])) again = false;
    T.ok(tag('save: the saved terrain loads again with the same heights'), again, '');

    // plants
    if (spots) {
        const pl = t.plants;
        const want = man.plants;
        let ok = pl !== null && C.sameJson(pl.names(), Object.keys(want.species));
        let why = '';
        for (const [sp, n] of Object.entries(want.species)) if (ok && pl.count(sp) !== n) { ok = false; why = `${sp}: ${pl.count(sp)} vs ${n}`; }
        const first = Object.entries(want.species).find(([, n]) => n > 0)?.[0];
        if (ok && first) {
            const xs = pl.field(first, 'x'), a = pl.array(first);
            ok = xs.length === want.species[first] && xs[0] === a[0] && xs[xs.length - 1] === a[(xs.length - 1) * 12];
        }
        T.ok(tag('plants: t.plants holds Blender\'s spots (names, counts, records)'), ok, why || JSON.stringify(want.species));
        let same = true, jsonOk = true;
        why = '';
        for (const fn of want.files.slice(1)) {
            const mine = `${outBase}${fn.slice('spots'.length)}`;
            const s1 = await C.sha1File(mine);
            if (s1 !== want.sha1[fn]) { same = false; why ||= `${fn}: ${s1} vs ${want.sha1[fn]}`; }
        }
        const bj = JSON.parse(Deno.readTextFileSync(C.urlPath(new URL(`${name}/spots.plants.json`, C.API_FIXTURES))));
        const mj = JSON.parse(Deno.readTextFileSync(`${outBase}.plants.json`));
        const stem = outBase.split('/').pop();
        for (const s of bj.species) s.file = s.file.replace(/^spots\./, `${stem}.`);
        jsonOk = C.sameJson(mj, bj);
        T.ok(tag('plants: saved again, every .f32 byte-identical and the JSON equal (file names aside)'), same && jsonOk,
            why || (jsonOk ? `${want.files.length - 1} species files` : C.jsonDiff(mj, bj)));
        const t3 = await Terrain.load(outBase, { build: false });
        T.ok(tag('plants: Terrain.load finds the spots beside a save'), t3.plants !== null && C.sameJson(t3.plants.names(), pl.names()), '');
        let coverWhy = '';
        try {
            pl.cover('main');
        } catch (e) {
            coverWhy = `${e.name}: ${e.message}`;
        }
        T.ok(tag('plants: cover() says it is the planner\'s (the last wave)'), coverWhy.startsWith('NotPortedError'), coverWhy);
    } else {
        T.ok(tag('plants: spots from Blender\'s planner'), false, `no spots fixture: ${JSON.stringify(man.plants)}`);
    }
    for (const f of [outBase + '.npz', outBase + '.json', outBase + '_parity.json']) Deno.removeSync(f);

    // the scene
    t0 = performance.now();
    const ts = await Terrain.load(base, { name: 'ground', log: quiet, plants: false });
    rec.load_and_build_s = +((performance.now() - t0) / 1000).toFixed(3);
    const { mesh, heightAt, masks } = ts;
    const [m2, h2] = ts;
    const mats = mesh.material;
    const table = ts.ring.ringTable();
    const groupsOk = mesh.geometry.groups.length === ts.ring.rings.length + 1 &&
        mesh.geometry.groups.every((g, k) => g.materialIndex === 0 && (k === table.length || (g.start === 3 * table[k].start && g.count === 3 * table[k].count)));
    T.ok(tag('scene: the mesh has the near and far clay NodeMaterials, one group a ring (the ring table\'s runs, every one on the near slot), no mask attributes'),
        mesh.isMesh && Array.isArray(mats) && mats.length === 2 && mats.every((m) => m.isNodeMaterial === true) && groupsOk &&
        C.sameJson(Object.keys(mesh.geometry.attributes).sort(), ['normal', 'position', 'uv']) && mesh.name === 'ground' && mesh.userData.trimeshCollider === true,
        `${mesh.geometry.groups.length} groups, attributes ${Object.keys(mesh.geometry.attributes).join(', ')}`);
    T.ok(tag('scene: `const { mesh, heightAt, masks } = t` and `const [mesh, heightAt] = t` work'),
        heightAt(mx[0], mz[0]) === ts.ring.heightAt(mx[0], my[0]) && masks === ts.masks && m2 === mesh && h2(mx[1], mz[1]) === ts.ring.heightAt(mx[1], my[1]), '');
    // the collider proxy: a view of the mesh's own vertex buffer from its first vertex, its rings' triangles counted
    // from there
    const proxy = ts.collider;
    const pp = proxy?.geometry.getAttribute('position').array, mp = mesh.geometry.getAttribute('position').array;
    const fv = proxy?.userData.firstVertex ?? 0, firstRing = ts.ring.rings[proxy?.userData.rings[0] ?? 0];
    let proxyOk = Boolean(proxy) && mesh.userData.colliderProxy === proxy && pp.buffer === mp.buffer && pp.byteOffset === mp.byteOffset + 12 * fv &&
        proxy.parent === null && proxy.userData.triangles > 0 && proxy.geometry.index.count === 3 * proxy.userData.triangles;
    const pi = proxy?.geometry.index.array;
    for (const q of [0, 1, 2, 3 * 777, pi.length - 1]) if (pi[q] + fv !== mesh.geometry.index.array[3 * firstRing.triBase + q]) proxyOk = false;
    T.ok(tag('scene: the collider proxy is on the mesh, its vertices a view of the mesh\'s vertex buffer from its first vertex, its triangles the rings\' run counted from there'),
        proxyOk, `rings ${JSON.stringify(proxy?.userData.rings)}, ${proxy?.userData.triangles} of ${ts.ring.triangleCount} triangles, ` +
        `${pp.length / 3} of ${mp.length / 3} vertices`);
    T.ok(tag('scene: the exact ray caster is installed and the geometry refuses a bounds tree'),
        mesh.userData.exactRaycast === true && Object.prototype.hasOwnProperty.call(mesh, 'raycast') && mesh.geometry.computeBoundsTree() === null, '');
    const ud = mesh.userData.eidoTerrain;
    T.ok(tag('scene: userData.eidoTerrain holds the recipe, knobs, seed, plan and cache key; eidoTerrainMesh the layout'),
        ud.recipe.name === man.recipe && ud.plan.length === ts.levels.length && ud.cache_key === js.cache_key && ud.seed === js.seed &&
        C.sameJson(JSON.parse(JSON.stringify(mesh.userData.eidoTerrainMesh)), JSON.parse(JSON.stringify(ts.ring.layout()))), '');
    rec.water = { lakes: ts.water.lakes.map((m) => m.userData.eidoWater), sea: ts.water.sea?.userData.eidoWater ?? null };
    rec.triangles = ts.ring.triangleCount;

    // preview: the hillshade and mask PNGs (looked at beside the DEM: out/mesh_api/preview/)
    const pbase = C.urlPath(C.outUrl(`preview/${name}`));
    t0 = performance.now();
    const files = await ts.preview(pbase);
    rec.preview_s = +((performance.now() - t0) / 1000).toFixed(2);
    const ihdr = (f) => {
        const b = Deno.readFileSync(f).subarray(0, 26), v = new DataView(b.buffer, b.byteOffset, 26);
        return { png: b[1] === 0x50 && b[2] === 0x4E && b[3] === 0x47, w: v.getUint32(16), h: v.getUint32(20), depth: b[24], colour: b[25] };
    };
    const main = ts.main, heads = files.map(ihdr);
    const wantMasks = ['slope', 'flow', 'rock', 'snow', 'vegetation', 'wetness', 'talus'].filter((m) => ts.masks._stack[main.index].has(m));
    const heroLast = ts.levels[ts.levels.length - 1].role === 'hero';
    T.ok(tag('preview: <path>_main_hillshade.png (RGB, the hero windows outlined), the hero hillshade when there is one, a PNG per mask present; n x n, 8-bit'),
        files.length === 1 + (heroLast ? 1 : 0) + wantMasks.length && heads.every((h) => h.png && h.depth === 8) &&
        heads[0].w === main.n && heads[0].h === main.n && heads[0].colour === 2 && files[0].endsWith('_main_hillshade.png') &&
        wantMasks.every((m) => files.includes(`${pbase}_mask_${m}.png`)),
        `${files.length} files in ${rec.preview_s} s: ${files.map((f) => f.split('/').pop()).join(', ')}`);

    // meshMasks: masks as point attributes (a debug option)
    const tm = await Terrain.load(base, { build: false, plants: false, meshMasks: ['slope', 'flow'] });
    const at = tm.ring.attributes;
    const lvOf = tm.ring.rings.map((r) => r.spec.level);
    let mmOk = at !== null && C.sameJson(Object.keys(at).sort(), ['flow', 'level', 'slope']) && at.slope.length === tm.ring.vertexCount;
    // a vertex of each ring's interior: its level, and its slope the mean of the four cells around its corner
    if (mmOk) {
        tm.ring.rings.forEach((r, k) => {
            const i = Math.min(3, r.nx - 2), j = Math.min(2, r.ny - 2), v = r.idx[j * r.nx + i];
            if (at.level[v] !== lvOf[k]) mmOk = false;
            const lv = tm.levels[lvOf[k]], a = tm.mask('slope').array(lvOf[k]);
            const cx = Math.round((r.xm[i] - lv.x0) / lv.cell), cy = Math.round((r.ym[j] - lv.y0) / lv.cell);
            const c = (q, n) => Math.min(Math.max(q, 0), n - 1);
            const wantV = Math.fround(Math.fround(Math.fround(a[c(cy - 1, lv.n) * lv.n + c(cx - 1, lv.n)] + a[c(cy, lv.n) * lv.n + c(cx - 1, lv.n)]) +
                Math.fround(a[c(cy - 1, lv.n) * lv.n + c(cx, lv.n)] + a[c(cy, lv.n) * lv.n + c(cx, lv.n)])) * 0.25);
            if (at.slope[v] !== wantV) mmOk = false;
        });
    }
    let r1 = await C.throwsWith(() => Terrain.load(base, { build: false, plants: false, meshMasks: ['slpoe'] }), ["no mask 'slpoe'", 'slope'], 'KeyError');
    const nine = tm.masks.names().slice(0, 9);
    let r2 = await C.throwsWith(() => Terrain.load(base, { build: false, plants: false, meshMasks: nine }), ['at most 8'], 'ValueError');
    T.ok(tag('meshMasks: the named masks and the level as point attributes (bilinear at the vertex, to the bit); an unknown mask names the nearest; more than eight are refused'),
        mmOk && r1.ok && r2.ok, mmOk ? `${Object.keys(at).join(', ')}; ${r1.message.slice(0, 80)}; ${r2.message.slice(0, 80)}` : 'attribute values');
    tm.dispose();
    ts.dispose();
    t.dispose();
}

async function flattenChecks(name, man, t, tag, arr, rec) {
    const fl = man.flatten;
    const specs = fl.specs.map((s) => {
        const o = { at: [s.at[0], -s.at[1]] };
        for (const k of ['radius', 'falloff', 'height', 'size']) if (k in s) o[k] = s[k];
        if ('angle_deg' in s) o.angleDeg = s.angle_deg;
        return o;
    });
    const fields = t.levels.map((lv, i) => {
        const f = t.fields(i);
        const o = { h: R.field(lv.n, lv.n, 1, f.h) };
        if ('bed' in f) o.bed = R.field(lv.n, lv.n, 1, f.bed);
        return o;
    });
    const t0 = performance.now();
    const flats = await A.flattenFields(R, fields, t.levels, A.checkFlatten(specs));
    await R.idle();
    rec.flatten_s = +((performance.now() - t0) / 1000).toFixed(3);
    const heights = flats.map((f) => f.height), want = fl.flats.map((f) => f.height);
    const hOk = flats.every((f, k) => Math.fround(f.height) === Math.fround(want[k]) && f.level === fl.flats[k].level && C.sameJson(f.at, fl.flats[k].at));
    T.ok(tag('flatten: the resolved heights (median of a disc, of a rotated rectangle, the nearest cell of a tiny area, a given one) and levels are Blender\'s'),
        hOk, `${JSON.stringify(heights)} vs ${JSON.stringify(want)}`);
    let changedOk = true, worst = 0, where = '', exactCells = 0, cells = 0, bandCells = 0;
    const changed = [];
    for (let i = 0; i < t.levels.length; i++) {
        const lv = t.levels[i], f = t.fields(i);
        const got = { h: await R.read(fields[i].h) };
        if (fields[i].bed) got.bed = await R.read(fields[i].bed);
        const isChanged = fl.changed_levels.includes(i);
        let differs = false;
        for (const k of Object.keys(got)) {
            const before = f[k];
            const wantA = isChanged ? arr(`flat_${k}_${i}`) : before;
            let lo = Infinity, hi = -Infinity;
            for (let q = 0; q < before.length; q++) { if (before[q] < lo) lo = before[q]; if (before[q] > hi) hi = before[q]; }
            const range = Math.max(hi - lo, 1e-9);
            for (let q = 0; q < wantA.length; q++) {
                cells++;
                if (got[k][q] !== before[q]) differs = true;
                if (got[k][q] === wantA[q]) { exactCells++; continue; }
                // a cell Blender left unchanged, or set to an area's height, must be so to the bit
                const untouched = wantA[q] === before[q];
                const flat = k === 'h' && want.some((z) => Math.fround(z) === wantA[q]);
                const d = Math.abs(got[k][q] - wantA[q]) / range;
                bandCells++;
                if (untouched || flat || d > 1e-5) {
                    changedOk = false;
                    where ||= `level ${i} ${k}[${q}]: ${got[k][q]} vs ${wantA[q]} (${untouched ? 'untouched in Blender' : flat ? 'a flat cell in Blender' : 'blend'})`;
                }
                worst = Math.max(worst, d);
            }
        }
        if (differs) changed.push(i);
        fields[i].h.destroy();
        fields[i].bed?.destroy();
        void lv;
    }
    rec.flatten = { seconds: rec.flatten_s, worst_over_range: worst, cells, bit_equal: exactCells, blend_cells_differing: bandCells };
    T.ok(tag('flatten: the same levels change; flat cells and untouched cells to the bit; the blend within 1e-5 of the range'),
        changedOk && C.sameJson(changed, fl.changed_levels),
        where || `levels ${JSON.stringify(changed)}; ${exactCells} of ${cells} cells bit-equal to Blender's, ${bandCells} blend cells differ, worst ${worst.toExponential(2)} of the range; ${rec.flatten_s} s`);
    const three = flats.map((f) => (f.size ? 'rect' : 'disc'));
    void three;
}

try {
    await optionChecks();
} catch (e) {
    T.ok('options: ran', false, `${e.name}: ${e.message}\n${e.stack?.split('\n').slice(1, 6).join('\n')}`);
}
for (const name of cases) {
    try {
        await checkCase(name);
    } catch (e) {
        T.ok(`${name}: ran`, false, `${e.name}: ${e.message}\n${e.stack?.split('\n').slice(1, 8).join('\n')}`);
    }
}
G.shutdown();
Deno.exit(C.finish(T, 'api_test.json'));
