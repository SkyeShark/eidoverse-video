// Eye views of real_place Lauterbrunnen's hero levels (PORT_PLAN.md 8.2 row P12: "eye views show rills, ribs and
// talus"): the Blender detail package's four cameras (blender/tests/terrain/detail/render_real_place.py, all from
// 1.7 m at the reference's eye spot):
//   eye      the reference's own eye camera: south up the valley
//   wall     west to the foot of the west wall, 400-500 m away (the 1 and 2 m levels)
//   slope    east across the floor to the forested slope below Wengen (1 and 2 m)
//   ground   the ground 4-40 m ahead, 12 degrees down (the 0.5 m level)
// their positions as the Blender package's r2 run placed them (out/detail/renders/r2_renders.json: per variant, at
// that variant's height_at + 1.7 m), rendered by the parity package's tests/judge/views.mjs (this edition's renderer
// with the reference rig: grey clay of albedo 0.18, the Earth sky at 15:30, the sun 70 degrees left of the view) for
//   port_detail      the port's detail variant (tests/detail/real_place_test.mjs)
//   port_upsampled   the port's upsampled variant: the DEM alone, what the detail adds to (from the detail's cameras,
//                    so it is framed as port_detail is)
//   blender_detail   the Blender edition's own detail run (tests/detail/blender_detail_runs.py lauterbrunnen_film),
//                    drawn by this renderer: the same ground through the same rig, for a like-for-like look
//   port_full        the port's full variant (the registered recipe), from the r2 run's full cameras
//   blender_full     the Blender edition's own run of the registered recipe (blender_detail_runs.py
//                    lauterbrunnen_film_full), from the same cameras
// and laid out beside the Blender package's own EEVEE renders of the same cameras (r2_<variant>_<view>_clay.png; made
// on 11-08 by the code before the terrain's first commit and its review's fix round, so a difference from them is
// weighed against blender_<variant>, today's code in this renderer) in one sheet per view and variant
// (tests/detail/sheet.py, Pillow: pictures only).
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/detail/views.mjs [--views eye,wall,slope,ground]
//         [--saves port_detail,port_upsampled,blender_detail,port_full,blender_full]   (each render a GPU job behind
//         $EIDO_GPU_WRAP)
//
// Writes tests/out/detail/views/<save>_<view>_eye_1p7m.png, the sheets <view>_sheet.png (detail) and
// <view>_full_sheet.png, and views.json.

import * as V from '../judge/views.mjs';
import * as D from './_detail.mjs';

const { C, W } = D;
const A = D.argsOf();
const VIEWS = A.list('--views') ?? ['eye', 'wall', 'slope', 'ground'];
// each save and the r2 variant whose cameras frame it
const SAVES = {
    port_detail: [`${W.out('detail')}/real_place/detail/terrain`, 'detail'],
    port_upsampled: [`${W.out('detail')}/real_place/upsampled/terrain`, 'detail'],
    blender_detail: [`${W.out('detail')}/runs/lauterbrunnen_film/base/terrain`, 'detail'],
    port_full: [`${W.out('detail')}/real_place/full/terrain`, 'full'],          // the registered recipe (with the fluvial package's ops)
    blender_full: [`${W.out('detail')}/runs/lauterbrunnen_film_full/base/terrain`, 'full'],
};
const WANT = A.list('--saves') ?? Object.keys(SAVES);
const OUT = `${W.out('detail')}/views`;
Deno.mkdirSync(`${OUT}/_json`, { recursive: true });

const tests = W.blenderTests();
if (!tests) {
    console.log('[skip] views: needs the Blender edition ($EIDO_BLENDER_EDITION): the reference views and its renders');
    Deno.exit(0);
}
const ref = C.readJson(`${tests}/reference/renders/lauterbrunnen_views.json`);
const r2 = C.readJson(`${tests}/out/detail/renders/r2_renders.json`);
// (a run with --saves adds its renders to the record of the runs before it)
const before = A.list('--saves') ? C.readJson(`${OUT}/views.json`, null) : null;
const record = { views: { ...(before?.views ?? {}) }, saves: {}, renders: { ...(before?.renders ?? {}) } };
for (const view of VIEWS) {
    for (const variant of ['detail', 'full']) {
        const names = WANT.filter((n) => SAVES[n]?.[1] === variant);
        if (!names.length) continue;
        const cam = r2?.[variant]?.[`${view}_clay`];
        if (!cam) { console.log(`[skip] ${view}: no ${variant} camera in the Blender package's r2_renders.json`); continue; }
        // the reference's eye entry with this camera; z_origin_m 0: the cameras are in the terrain's own frame (the
        // Blender package placed them at its terrain's height_at + 1.7 m), which a save's datum ('save') draws as it is
        const v = { ...ref.eye, camera: cam.camera, target: cam.target, lens_mm: cam.lens, z_origin_m: 0.0, ground_z: cam.camera[2] - 1.7 };
        // the sun 70 degrees left of this view's heading, at the rig's elevation (render_real_place.py's render())
        const hd = Math.atan2(cam.target[1] - cam.camera[1], cam.target[0] - cam.camera[0]) + (70.0 * Math.PI) / 180;
        const el = (ref.eye.sun_elevation_deg * Math.PI) / 180;
        v.sun_dir = [Math.cos(hd) * Math.cos(el), Math.sin(hd) * Math.cos(el), Math.sin(el)];
        const file = `${OUT}/_json/${variant}_${view}_views.json`;
        Deno.writeTextFileSync(file, JSON.stringify({ eye: v }, null, 1));
        record.views[`${variant}_${view}`] = { camera: cam.camera, target: cam.target, lens: cam.lens, sun_dir: v.sun_dir,
            blender_render: `${tests}/out/detail/renders/r2_${variant}_${view}_clay.png` };
        for (const name of names) {
            const save = SAVES[name][0];
            if (!W.exists(`${save}.npz`)) { console.log(`[skip] ${name}: no save at ${save}.npz`); continue; }
            const r = await V.renderViews(save, { viewsJson: file, views: ['eye'], label: `${name}_${view}`, out: OUT });
            record.renders[`${name}_${view}`] = { ...(r?.views?.eye ?? {}), cameras: variant };
        }
    }
}
Deno.writeTextFileSync(`${OUT}/views.json`, JSON.stringify(record, null, 1));
// one sheet per view and variant: Blender's EEVEE render (11-08), then this renderer's of Blender's save of today's
// code, then the port's (for the detail, also the port's DEM alone)
const SHEETS = {
    detail: [['blender_detail', 'port_detail', 'port_upsampled'], '', 'Blender EEVEE (its r2 detail render, 11-08 code) | this renderer: Blender\'s detail save | the port\'s detail | the port\'s DEM alone'],
    full: [['blender_full', 'port_full'], '_full', 'Blender EEVEE (its r2 full render, 11-08 code) | this renderer: Blender\'s full save (today\'s code) | the port\'s full recipe'],
};
const py = W.which('python') ?? W.which('python3');
for (const [key, view] of Object.keys(record.views).filter((k) => /^(detail|full)_/.test(k)).map((k) => [k, k.split('_').slice(1).join('_')])) {
    const variant = key.split('_')[0];
    const [names, suffix, title] = SHEETS[variant];
    const pics = [record.views[key].blender_render, ...names.map((n) => `${OUT}/${n}_${view}_eye_1p7m.png`)];
    if (py) {
        await W.run([py, `${W.TESTS}/detail/sheet.py`, '--out', `${OUT}/${view}${suffix}_sheet.png`, '--title',
            `real_place Lauterbrunnen, ${view} view (1.7 m): ${title}`, ...pics]);
    }
}
console.log(`[views] ${Object.keys(record.renders).length} renders -> ${OUT}`);
