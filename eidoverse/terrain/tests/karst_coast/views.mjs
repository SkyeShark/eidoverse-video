// The package's recipes beside their places (PORT_PLAN.md 5.3 "look", 6.3, 8.1 "Looking"): the Blender floor run's save
// and the port's save of the same recipe and seed drawn by this edition's renderer from the same cameras
// (tests/judge/views.mjs renderViews: the reference rig, grey clay of albedo 0.18, the Earth sky at 15:30), laid out
// with the reference place's own Blender renders and its photographs by tests/fluvial/sheet.py (Pillow, pictures only):
//   tower_karst  guilin_karst's top hillshade and 45-degree aerial (the reference's cameras), and the Blender judge's
//                eye camera on the generated terrain (blender/tests/terrain/out/karst/judge_tower_karst/
//                tower_karst_seed1_views.json: its eye spot stands on the tower_karst ground, which every quality
//                evaluates from the same world functions); the Li River photographs (CC0)
//   sea_cliffs   seven_sisters' top and aerial, and the Blender judge's sea_cliffs eye camera (out/coast/
//                judge_sea_cliffs/sea_cliffs_seed1_views.json); the Seven Sisters photographs (CC0 and CC BY-SA, in the
//                Blender package's out/coast/photos: never redistributed, the sheet stays under tests/out)
//   sea_cliffs_layered   rock 'layered' (the port's save sea_cliffs_layered_s<seed>, Blender's from its bake.py with
//                the same call in tests/out/karst_coast/blender_saves/): cliffs_of_moher's top and aerial (its
//                photographs are CC BY and CC BY-SA: none is shown, PORT_PLAN.md 6.4)
// and the photo-matched cameras (view 'photo', below): tower_karst's riverbank (photograph 01) and sea_cliffs' Seaford
// Head (photograph ss_seaford_head), each beside its photograph and the Blender package's own render of its camera.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/karst_coast/views.mjs [--recipes tower_karst]
//         [--seed 1] [--views top,aerial,eye,photo]  (each render a GPU job of its own behind $EIDO_GPU_WRAP: run
//                                                     this outside the queue)
//
// Writes tests/out/karst_coast/views/<label>_<view>.png, <recipe>_s<seed>_sheet.png, <recipe>_s<seed>_<camera>_sheet.png
// and views.json.

import * as IO from '../../core/io.js';
import * as V from '../judge/views.mjs';
import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const RECIPES = opt('--recipes', 'tower_karst,sea_cliffs').split(',');
const SEED = Number(opt('--seed', '1'));
const VIEWS = opt('--views', 'top,aerial,eye,photo').split(',');
const OUT = `${KC.OUT()}/views`;
Deno.mkdirSync(OUT, { recursive: true });
const tests = W.blenderTests();
if (!tests) {
    console.log('[skip] views: needs the Blender edition ($EIDO_BLENDER_EDITION): the reference views, renders and photographs');
    Deno.exit(0);
}
// each look: its reference, the Blender judge's eye camera, the photographs (a folder, and the names' prefix), and
// the Blender save (a floor run's, or a save of tests/out/karst_coast/blender_saves/ made by the Blender edition's
// bake.py with the same call)
const PLACES = {
    tower_karst: { reference: 'guilin_karst', judge: `${tests}/out/karst/judge_tower_karst/tower_karst_seed1_views.json`,
        photos: [`${tests}/out/integration/photos/guilin_karst`, 'guilin_karst_'] },
    sea_cliffs: { reference: 'seven_sisters', judge: `${tests}/out/coast/judge_sea_cliffs/sea_cliffs_seed1_views.json`,
        photos: [`${tests}/out/coast/photos`, 'ss_'] },
    sea_cliffs_layered: { recipe: 'sea_cliffs', reference: 'cliffs_of_moher', judge: null,
        photos: [`${tests}/out/coast/photos`, 'moher_'], blender: `${KC.OUT()}/blender_saves/sea_cliffs_layered_s${SEED}` },
};
// the photographs of one place in a folder of their own (sheet.py takes a folder's first three), under tests/out:
// only those sources.json lists as CC0 or public domain (PORT_PLAN.md 6.4; the coast folder also holds CC BY and
// CC BY-SA photographs of the Blender package's, which stay out of the port's sheets: Moher has none to show)
function photoDir([dir, prefix], name) {
    const to = `${OUT}/photos_${name}`;
    Deno.mkdirSync(to, { recursive: true });
    const src = C.readJson(`${dir}/sources.json`, []);
    const list = Array.isArray(src) ? src : Object.values(src.photos ?? src);
    const free = new Set(list.filter((s) => /^(CC0|public domain|PD)/i.test(String(s.licence ?? s.license ?? ''))).map((s) => s.file));
    for (const e of Deno.readDirSync(dir)) {
        if (e.isFile && e.name.startsWith(prefix) && free.has(e.name)) Deno.copyFileSync(`${dir}/${e.name}`, `${to}/${e.name}`);
    }
    return to;
}
/** A save's main level: { lv, info, n, h } (h row 0 south, Blender frame). */
async function mainLevel(save) {
    const info = C.readJson(`${save}.json`);
    const lv = (info.plan ?? info.levels).find((l) => l.role === 'main');
    const want = `L${lv.index}__f__h`;
    const arrays = await IO.readNpz(`${save}.npz`, { names: [want, `${want}.npy`] });
    const a = arrays[want] ?? arrays[`${want}.npy`];
    return { lv, info, n: lv.n, h: a.data ?? a };
}

/** The main level's height at world (x, y), bilinear over its cell centres. */
function heightOn(M, x, y) {
    const { lv, n, h } = M;
    const fx = (x - lv.x0) / lv.cell - 0.5, fy = (y - lv.y0) / lv.cell - 0.5;
    const i = Math.max(0, Math.min(n - 2, Math.floor(fx))), j = Math.max(0, Math.min(n - 2, Math.floor(fy)));
    const u = Math.min(Math.max(fx - i, 0), 1), v = Math.min(Math.max(fy - j, 0), 1);
    return (1 - v) * ((1 - u) * h[j * n + i] + u * h[j * n + i + 1]) + v * ((1 - u) * h[(j + 1) * n + i] + u * h[(j + 1) * n + i + 1]);
}

// sea_cliffs is distribution class, its terrain not Blender's: the Blender coast package's matching rule
// (blender/tests/terrain/coast/render_photo_views.py: CoastFrame, anchor ('along', 0), resolve_view) is ported here
// and run on each save's own main level. The coast frame: n0 the seaward normal (the recipe's azimuth_deg), t0 along
// the shore; the anchor the mainland's shore cell (land beside the sea, h > 0.3 m, the largest 8-connected body)
// within 1.5 cells of the centre line, the median one seaward; its frame (t, n) the principal direction of the
// mainland's shore cells within 300 m; its cliff top the first point inland (2 m steps) past a 10 m climb where the
// slope over 4 m falls under 25 degrees. The Seaford Head view (photograph ss_seaford_head, CC0): from 72 m over
// the sea 2.9 km along t and 900 m out along n from the anchor, 91 mm, toward 300 m back along t and 60 m in, 30 m
// under the anchor's cliff top, the sun at compass 190 degrees.
function seafordHead(M) {
    const { lv, n, h, info } = M;
    const az = ((info.knobs?.azimuth_deg ?? 200.0) * Math.PI) / 180.0;
    const sea = Uint8Array.from(h, (v) => (v <= 0.3 ? 1 : 0));
    const lab = new Int32Array(n * n), counts = [0];
    for (let s = 0; s < n * n; s++) {
        if (sea[s] || lab[s]) continue;
        const L = counts.length, stack = [s];
        lab[s] = L;
        let c = 0;
        while (stack.length) {
            const q = stack.pop(), qi = q % n, qj = (q - qi) / n;
            c++;
            for (let dj = -1; dj <= 1; dj++) {
                for (let di = -1; di <= 1; di++) {
                    const i = qi + di, j = qj + dj, r = j * n + i;
                    if (i >= 0 && j >= 0 && i < n && j < n && !sea[r] && !lab[r]) { lab[r] = L; stack.push(r); }
                }
            }
        }
        counts.push(c);
    }
    let main = 0;
    for (let l = 1; l < counts.length; l++) if (counts[l] > counts[main]) main = l;
    const cx = lv.x0 + lv.side / 2, cy = lv.y0 + lv.side / 2;
    const n0 = [Math.sin(az), Math.cos(az)], t0 = [n0[1], -n0[0]];
    const P = [], L = [], along = [], out = [];
    for (let j = 1; j < n - 1; j++) {
        for (let i = 1; i < n - 1; i++) {
            const k = j * n + i;
            if (sea[k]) continue;
            let nb = false;
            for (let dj = -1; dj <= 1 && !nb; dj++) for (let di = -1; di <= 1; di++) if (sea[(j + dj) * n + i + di]) { nb = true; break; }
            if (!nb) continue;
            const x = lv.x0 + (i + 0.5) * lv.cell, y = lv.y0 + (j + 0.5) * lv.cell;
            P.push([x, y]);
            L.push(lab[k]);
            along.push((x - cx) * t0[0] + (y - cy) * t0[1]);
            out.push((x - cx) * n0[0] + (y - cy) * n0[1]);
        }
    }
    // shore_at(0)
    let idx = P.map((_, k) => k).filter((k) => Math.abs(along[k]) < 1.5 * lv.cell && L[k] === main);
    let p;
    if (!idx.length) {
        let best = Infinity, bk = 0;
        P.forEach((_, k) => { const v = Math.abs(along[k]) + (L[k] === main ? 0 : 1e6); if (v < best) { best = v; bk = k; } });
        p = P[bk];
    } else {
        idx = idx.sort((a, b) => out[a] - out[b]);
        p = P[idx[Math.floor(idx.length / 2)]];
    }
    // local_frame(p): the principal direction of the mainland's shore cells within 300 m
    let t = t0, nv = n0;
    const near = P.filter((q, k) => Math.hypot(q[0] - p[0], q[1] - p[1]) < 300.0 && L[k] === main);
    if (near.length >= 5) {
        const mx = near.reduce((s, q) => s + q[0], 0) / near.length, my = near.reduce((s, q) => s + q[1], 0) / near.length;
        let sxx = 0, sxy = 0, syy = 0;
        for (const q of near) { const a = q[0] - mx, b = q[1] - my; sxx += a * a; sxy += a * b; syy += b * b; }
        const th = 0.5 * Math.atan2(2 * sxy, sxx - syy);
        t = [Math.cos(th), Math.sin(th)];
        if (t[0] * t0[0] + t[1] * t0[1] < 0) t = [-t[0], -t[1]];
        nv = [-t[1], t[0]];
        if (nv[0] * n0[0] + nv[1] * n0[1] < 0) nv = [-nv[0], -nv[1]];
    }
    // top_of(p, n)
    const zs = [], pts = [];
    for (let s = 0; s < 160; s += 2) { const q = [p[0] - s * nv[0], p[1] - s * nv[1]]; pts.push(q); zs.push(heightOn(M, q[0], q[1])); }
    let topZ = null;
    for (let k = 2; k < zs.length && topZ === null; k++) {
        if (zs[k] - zs[0] > 10.0 && (zs[k] - zs[k - 2]) / 4.0 < Math.tan((25.0 * Math.PI) / 180.0)) topZ = zs[k];
    }
    if (topZ === null) topZ = Math.max(...zs);
    const at = (a, o, z) => [p[0] + a * t[0] + o * nv[0], p[1] + a * t[1] + o * nv[1], z];
    return { camera: at(2900.0, 900.0, 72.0), target: at(-300.0, -60.0, topZ - 30.0), lens_mm: 91.0, sun_compass_deg: 190.0,
        anchor: p, anchor_top_m: topZ, t, n: nv };
}

// the photo-matched cameras per look: the photograph, the Blender package's own render of its camera, and the camera
// on a save. tower_karst is field class: the Blender karst package's photo-matched cameras (karst/render_photo_views.py,
// seed 1: out/karst/views/v4_views.json) frame the same ground on the port's save. The riverbank's (photograph 01,
// the towers along the Li, 1.7 m on a bank cell) was found on the Blender package's film terrain: on a draft save
// its eye is set 1.7 m over that save's own main level at the same point (the ground under it differs by a cell's
// rounding), its target as found. The rig is the reference's eye rig.
const PHOTO_VIEWS = {
    tower_karst: { riverbank: { photo: 'guilin_karst_01.jpg', blender: `${tests}/out/karst/views/v4_riverbank_clay.png`,
        camera: (M) => {
            const cam = C.readJson(`${tests}/out/karst/views/v4_views.json`).views.riverbank;
            const z = heightOn(M, cam.camera[0], cam.camera[1]) + 1.7;
            return { camera: [cam.camera[0], cam.camera[1], z], target: cam.target, lens_mm: cam.lens_mm, found_z: cam.camera[2] };
        } } },
    sea_cliffs: { seaford_head: { photo: 'ss_seaford_head.jpg', blender: `${tests}/out/coast/views/p5_ss_seaford_head_clay.png`,
        camera: seafordHead } },
};

const record = C.readJson(`${OUT}/views.json`, { renders: {} });
for (const recipe of RECIPES) {
    const place = PLACES[recipe];
    const found = place.blender ? null : KC.floorRunOfCode(place.recipe ?? recipe, SEED);
    const saves = { blender: place.blender ?? (found ? `${found[0]}/terrain` : null), port: `${KC.OUT()}/saves/${recipe}_s${SEED}` };
    for (const [who, save] of Object.entries(saves)) {
        if (!save || !W.exists(`${save}.npz`)) { console.log(`[skip] ${recipe} ${who}: no save`); continue; }
        const label = `${recipe}_s${SEED}_${who}`;
        const ref = VIEWS.filter((v) => v !== 'eye');
        if (ref.length) {
            const r = await V.renderViews(save, { reference: place.reference, views: ref, label, out: OUT });
            record.renders[label] = { ...(record.renders[label] ?? {}), ...(r?.views ?? {}) };
        }
        if (VIEWS.includes('eye') && place.judge && W.exists(place.judge)) {
            const r = await V.renderViews(save, { viewsJson: place.judge, views: ['eye'], label: `${label}_judge`, out: OUT });
            record.renders[`${label}_judge`] = r?.views ?? null;
        }
        const pv = PHOTO_VIEWS[recipe];
        if (VIEWS.includes('photo') && pv) {
            const M = await mainLevel(save);
            const rig = C.readJson(`${tests}/reference/renders/${place.reference}_views.json`).eye;
            const el = (rig.sun_elevation_deg * Math.PI) / 180;
            for (const [name, spec] of Object.entries(pv)) {
                const cam = spec.camera(M);
                const view = { ...rig, camera: cam.camera, target: cam.target, lens_mm: cam.lens_mm, z_origin_m: 0.0,
                    ground_z: heightOn(M, cam.camera[0], cam.camera[1]) };
                if (cam.sun_compass_deg != null) {
                    const a = (cam.sun_compass_deg * Math.PI) / 180;
                    view.sun_dir = [Math.sin(a) * Math.cos(el), Math.cos(a) * Math.cos(el), Math.sin(el)];
                }
                const file = `${OUT}/_json/${label}_${name}_views.json`;
                Deno.mkdirSync(`${OUT}/_json`, { recursive: true });
                Deno.writeTextFileSync(file, JSON.stringify({ eye: view }, null, 1));
                const r = await V.renderViews(save, { viewsJson: file, views: ['eye'], label: `${label}_${name}`, out: OUT });
                record.renders[`${label}_${name}`] = { ...(r?.views?.eye ?? {}), camera: cam };
            }
        }
    }
    // the photo-matched views beside their photographs and the Blender package's own (film) render of its camera
    const pv = PHOTO_VIEWS[recipe];
    if (VIEWS.includes('photo') && pv) {
        for (const [name, spec] of Object.entries(pv)) {
            const py = W.which('python') ?? W.which('python3');
            if (!py) break;
            await W.run([py, `${W.TESTS}/detail/sheet.py`, '--out', `${OUT}/${recipe}_s${SEED}_${name}_sheet.png`, '--title',
                `${recipe} s${SEED}, the ${name} camera: the photograph | Blender's film render (its package) | ` +
                'this renderer: Blender\'s draft save | the port\'s draft save',
            `${place.photos[0]}/${spec.photo}`, spec.blender, `${OUT}/${recipe}_s${SEED}_blender_${name}_eye_1p7m.png`,
            `${OUT}/${recipe}_s${SEED}_port_${name}_eye_1p7m.png`]);
        }
    }
    const py = W.which('python') ?? W.which('python3');
    if (py) {
        await W.run([py, `${W.TESTS}/fluvial/sheet.py`, '--recipe', recipe, '--reference', place.reference,
            '--reference-renders', `${tests}/reference/renders`, '--renders', OUT,
            '--blender-label', `${recipe}_s${SEED}_blender`, '--port-label', `${recipe}_s${SEED}_port`,
            '--photos', photoDir(place.photos, place.reference), '--out', `${OUT}/${recipe}_s${SEED}_sheet.png`]);
    }
}
Deno.writeTextFileSync(`${OUT}/views.json`, JSON.stringify(record, null, 1));
console.log(`[views] -> ${OUT}`);
