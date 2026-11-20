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
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/karst_coast/views.mjs [--recipes tower_karst]
//         [--seed 1] [--views top,aerial,eye]       (each render a GPU job of its own behind $EIDO_GPU_WRAP: run this
//                                                    outside the queue)
//
// Writes tests/out/karst_coast/views/<label>_<view>.png, <recipe>_s<seed>_sheet.png and views.json.

import * as V from '../judge/views.mjs';
import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const RECIPES = opt('--recipes', 'tower_karst,sea_cliffs').split(',');
const SEED = Number(opt('--seed', '1'));
const VIEWS = opt('--views', 'top,aerial,eye').split(',');
const OUT = `${KC.OUT()}/views`;
Deno.mkdirSync(OUT, { recursive: true });
const tests = W.blenderTests();
if (!tests) {
    console.log('[skip] views: needs the Blender edition ($EIDO_BLENDER_EDITION): the reference views, renders and photographs');
    Deno.exit(0);
}
const PLACES = {
    tower_karst: { reference: 'guilin_karst', judge: `${tests}/out/karst/judge_tower_karst/tower_karst_seed1_views.json`,
        photos: `${tests}/out/integration/photos/guilin_karst` },
    sea_cliffs: { reference: 'seven_sisters', judge: `${tests}/out/coast/judge_sea_cliffs/sea_cliffs_seed1_views.json`,
        photos: `${tests}/out/coast/photos` },
};
const record = C.readJson(`${OUT}/views.json`, { renders: {} });
for (const recipe of RECIPES) {
    const place = PLACES[recipe];
    const found = KC.floorRunOfCode(recipe, SEED);
    const saves = { blender: found ? `${found[0]}/terrain` : null, port: `${KC.OUT()}/saves/${recipe}_s${SEED}` };
    for (const [who, save] of Object.entries(saves)) {
        if (!save || !W.exists(`${save}.npz`)) { console.log(`[skip] ${recipe} ${who}: no save`); continue; }
        const label = `${recipe}_s${SEED}_${who}`;
        const ref = VIEWS.filter((v) => v !== 'eye');
        if (ref.length) {
            const r = await V.renderViews(save, { reference: place.reference, views: ref, label, out: OUT });
            record.renders[label] = { ...(record.renders[label] ?? {}), ...(r?.views ?? {}) };
        }
        if (VIEWS.includes('eye') && W.exists(place.judge)) {
            const r = await V.renderViews(save, { viewsJson: place.judge, views: ['eye'], label: `${label}_judge`, out: OUT });
            record.renders[`${label}_judge`] = r?.views ?? null;
        }
    }
    const py = W.which('python') ?? W.which('python3');
    if (py) {
        await W.run([py, `${W.TESTS}/fluvial/sheet.py`, '--recipe', recipe, '--reference', place.reference,
            '--reference-renders', `${tests}/reference/renders`, '--renders', OUT,
            '--blender-label', `${recipe}_s${SEED}_blender`, '--port-label', `${recipe}_s${SEED}_port`, '--photos', place.photos,
            '--out', `${OUT}/${recipe}_s${SEED}_sheet.png`]);
    }
}
Deno.writeTextFileSync(`${OUT}/views.json`, JSON.stringify(record, null, 1));
console.log(`[views] -> ${OUT}`);
