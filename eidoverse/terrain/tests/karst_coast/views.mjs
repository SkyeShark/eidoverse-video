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
//                the same call in tests/out/karst_coast/blender_saves/): cliffs_of_moher's top and aerial; the Moher
//                photographs (CC BY and CC BY-SA, the same folder)
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/karst_coast/views.mjs [--recipes tower_karst]
//         [--seed 1] [--views top,aerial,eye]       (each render a GPU job of its own behind $EIDO_GPU_WRAP: run this
//                                                    outside the queue)
//
// Writes tests/out/karst_coast/views/<label>_<view>.png, <recipe>_s<seed>_sheet.png and views.json.

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
// tower_karst is field class: the Blender karst package's photo-matched cameras (karst/render_photo_views.py, seed 1:
// out/karst/views/v4_views.json) frame the same ground on the port's save. The riverbank's (photograph 01, the
// towers along the Li, 1.7 m on a bank cell) was found on the Blender package's film terrain: on a draft save its
// eye is set 1.7 m over that save's own main level at the same point (the camera's ground differs by a cell's
// rounding), its target as found; the rig is the reference's eye rig.
const PHOTO_VIEWS = { tower_karst: { file: `${tests}/out/karst/views/v4_views.json`, views: { riverbank: 'guilin_karst_01.jpg' },
    blender_render: (v) => `${tests}/out/karst/views/v4_${v}_clay.png` } };

/** The save's main-level height at world (x, y) (Blender frame), bilinear over its cell centres. */
async function groundAt(save, x, y) {
    const info = C.readJson(`${save}.json`);
    const lv = info.levels.find((l) => l.role === 'main');
    const want = `L${lv.index}__f__h`;
    const arrays = await IO.readNpz(`${save}.npz`, { names: [want, `${want}.npy`] });
    const a = arrays[want] ?? arrays[`${want}.npy`];
    const n = lv.n, h = a.data ?? a;
    const fx = (x - lv.x0) / lv.cell - 0.5, fy = (y - lv.y0) / lv.cell - 0.5;
    const i = Math.max(0, Math.min(n - 2, Math.floor(fx))), j = Math.max(0, Math.min(n - 2, Math.floor(fy)));
    const u = fx - i, v = fy - j;
    return (1 - v) * ((1 - u) * h[j * n + i] + u * h[j * n + i + 1]) + v * ((1 - u) * h[(j + 1) * n + i] + u * h[(j + 1) * n + i + 1]);
}

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
        if (VIEWS.includes('photo') && pv && W.exists(pv.file)) {
            const found = C.readJson(pv.file).views;
            const rig = C.readJson(`${tests}/reference/renders/${place.reference}_views.json`).eye;
            for (const name of Object.keys(pv.views)) {
                const cam = found[name];
                if (!cam) continue;
                const z = (await groundAt(save, cam.camera[0], cam.camera[1])) + 1.7;
                const file = `${OUT}/_json/${label}_${name}_views.json`;
                Deno.mkdirSync(`${OUT}/_json`, { recursive: true });
                Deno.writeTextFileSync(file, JSON.stringify({ eye: { ...rig, camera: [cam.camera[0], cam.camera[1], z],
                    target: cam.target, lens_mm: cam.lens_mm, z_origin_m: 0.0, ground_z: z - 1.7 } }, null, 1));
                const r = await V.renderViews(save, { viewsJson: file, views: ['eye'], label: `${label}_${name}`, out: OUT });
                record.renders[`${label}_${name}`] = { ...(r?.views?.eye ?? {}), camera_z: z, found_z: cam.camera[2] };
            }
        }
    }
    // the photo-matched views beside their photographs and the Blender package's own (film) render of the camera
    const pv = PHOTO_VIEWS[recipe];
    if (VIEWS.includes('photo') && pv) {
        for (const [name, photo] of Object.entries(pv.views)) {
            const py = W.which('python') ?? W.which('python3');
            if (!py) break;
            await W.run([py, `${W.TESTS}/detail/sheet.py`, '--out', `${OUT}/${recipe}_s${SEED}_${name}_sheet.png`, '--title',
                `${recipe} s${SEED}, the ${name} camera (1.7 m): the photograph | Blender's film render (its package) | ` +
                'this renderer: Blender\'s draft save | the port\'s draft save',
            `${place.photos[0]}/${photo}`, pv.blender_render(name), `${OUT}/${recipe}_s${SEED}_blender_${name}_eye_1p7m.png`,
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
