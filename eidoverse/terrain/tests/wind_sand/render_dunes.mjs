// The dunes recipe rendered by both editions from the Blender judge's cameras, beside the reference's own renders and
// the photographs (PORT_PLAN.md 6.3, 8.1 "Looking"; 8.2 P8: "renders beside the photographs, looked at").
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/wind_sand/render_dunes.mjs <step> [--seed 1]
//          [--variant star] [--quality film]
//
// (from the repository root; GPU jobs go behind $EIDO_GPU_WRAP). The steps, in order:
//   --blender   the Blender judge's own job (blender/tests/terrain/judge/blender_job.py, as it is: the recipe at the
//               reference's extent, the clay rig's top, aerial and eye views from its eye spot, and a terrain with
//               hero levels around that spot for the hero eye view), written to tests/out/wind_sand/renders/blender/
//   --make      (a GPU job: run it behind $EIDO_GPU_WRAP) the port's terrains of the same calls: the recipe as the
//               judge makes it (api.js generate, no focus) and the same with the focus on the Blender eye spot (hero
//               levels), each saved (Terrain.save) and judged by the Blender judge
//   --render    the port's saves drawn by tests/judge/views.mjs (P4's mesh, this edition's renderer, the reference
//               rig) from the cameras the Blender job used (its <label>_views.json). The top and aerial cameras frame
//               the tile and stand as they are. The eye camera stands where the Blender eye spot is, 1.7 m above
//               the port's own ground there (the dunes are the same field only statistically: plan 5.4's distribution
//               class), its target the same point raised by the same pitch; the hero eye likewise on the focused save
//   --sheet     the Blender judge's sheet (tests/judge/sheet_compose.py): the reference's row, Blender's, the port's
// JavaScript per view here (cameras, files); every pixel is a renderer's.

import * as W from '../_where.mjs';
import * as C from '../parity/_common.mjs';
import * as V from '../judge/views.mjs';
import * as S from './_common.mjs';
import { VARIANTS } from './recipe_runs.mjs';

const args = [...Deno.args];
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args.splice(i, 2)[1] : d; };
const flag = (n) => { const i = args.indexOf(n); if (i < 0) return false; args.splice(i, 1); return true; };
const seed = Number(opt('--seed', '1')), variant = opt('--variant', 'star'), quality = opt('--quality', 'film');
const v = VARIANTS[variant];
const DIR = `${S.OUT}/renders`;
const BL = `${DIR}/blender`;
// a film call is generated here in both editions; a draft one is the saves recipe_runs.mjs (the port) and
// blender_kinds.py (Blender) made, the Blender one drawn by the Blender judge job as a field item
const draft = quality === 'draft';
const label = `dunes_${variant}_seed${seed}` + (draft ? '_draft' : '');
const PORT = `${DIR}/port`;
const portSave = (name) => (draft ? `${S.OUT}/port_kinds/${variant}_s${seed}/terrain` : `${PORT}/${name}`);
Deno.mkdirSync(BL, { recursive: true });
Deno.mkdirSync(PORT, { recursive: true });

// a Blender save's main level (and the context level around it) as a judge field item: { h, cell, context_h, context_cell }
async function fieldItem(base, out) {
    const IO = await import('../../core/io.js');
    const info = C.readJson(`${base}.json`);
    const main = info.plan.find((l) => l.role === 'main');
    const ctx = info.plan.find((l) => l.index === main.parent) ?? null;
    const read = async (lv) => Object.values(await IO.readNpz(`${base}.npz`, { names: [`L${lv.index}__f__h.npy`, `L${lv.index}__f__h`] }))[0];
    const arrays = { h: await read(main), cell: IO.npArray(Float64Array.of(main.cell), []) };
    if (ctx) Object.assign(arrays, { context_h: await read(ctx), context_cell: IO.npArray(Float64Array.of(ctx.cell), []) });
    await IO.writeNpz(out, arrays);
    return out;
}

if (flag('--blender')) {
    const edition = W.needBlenderEdition('the Blender judge job');
    if (!edition) Deno.exit(2);
    const item = draft ? { label, field: await fieldItem(`${S.OUT}/blender_kinds/${variant}_s${seed}/terrain`, `${BL}/${label}_field.npz`) }
        : { label, recipe: 'dunes', seed, quality, params: v.params ?? {}, textured: false };
    const job = { reference: v.reference, out_dir: BL, cache_root: `${BL}/_sky_cache`, samples: 16, items: [item] };
    const jf = `${BL}/job_${label}.json`;
    Deno.writeTextFileSync(jf, JSON.stringify(job, null, 1));
    const code = await W.run(W.blenderCmd(`${edition}/blender/tests/terrain/judge/blender_job.py`, '--job', jf),
        { cwd: edition, log: `${BL}/${label}_job.log`, env: { ...Deno.env.toObject(), PYTHONDONTWRITEBYTECODE: '1' } });
    console.log(`[render_dunes] the Blender judge job: exit ${code} (${BL}/${label}_job.log)`);
    Deno.exit(code);
}

if (flag('--make')) {
    const G = await import('../../core/gpu.js');
    const A = await import('../../solvers/aeolian.js');
    const { generate } = await import('../../api.js');
    const J = await import('../judge/judge.mjs');
    const views = C.readJson(`${BL}/${label}_views.json`);
    if (!views) { console.log(`no ${BL}/${label}_views.json: run --blender first`); Deno.exit(2); }
    await G.init();
    const calls = [[label, null], [`${label}_hero`, [views.eye.camera[0], views.eye.camera[1]]]];
    for (const [name, focus] of calls) {
        A.clearTiles();
        const t0 = performance.now();
        const logs = [];
        // the focus in three.js axes (x, z) = Blender (x, -y) (PORT_PLAN.md 2.2)
        const t = await generate({ recipe: 'dunes', size: v.size, seed, params: v.params, quality, cache: false,
            focus: focus ? [focus[0], -focus[1]] : null, log: (m) => logs.push(m) });
        const secs = +((performance.now() - t0) / 1000).toFixed(1);
        await t.save(`${PORT}/${name}`);
        const levels = t.levels.map(String);
        t.dispose();
        const verdict = await J.judgeSave(`${PORT}/${name}`, { reference: v.reference, label: `${name}_port`, outDir: `${PORT}/judge_${name}` });
        Deno.writeTextFileSync(`${PORT}/${name}_run.json`, JSON.stringify({ name, focus, seconds: secs, levels,
            log: logs.filter((m) => m.includes('aeolian') || m.includes('terrain.run')), passed: verdict?.passed ?? null }, null, 1));
        const judged = verdict ? verdict.rows.filter((r) => r.passed !== null) : [];
        console.log(`[render_dunes] ${name}: ${secs} s, ${levels.length} levels, the judge ${judged.filter((r) => r.passed).length}/${judged.length} bands`);
    }
    A.clearTiles();
    G.shutdown();
    Deno.exit(0);
}

// ---- the cameras on the port's ground
async function mainHeights(base) {
    const IO = await import('../../core/io.js');
    const info = C.readJson(`${base}.json`);
    const plan = info.plan;
    const main = plan.find((l) => l.role === 'main');
    const finest = (x, y) => [...plan].reverse().find((l) => x >= l.x0 && x <= l.x0 + l.side && y >= l.y0 && y <= l.y0 + l.side);
    const cache = {};
    const h = async (lv) => (cache[lv.index] ??= (await IO.readNpz(`${base}.npz`, { names: [`L${lv.index}__f__h.npy`, `L${lv.index}__f__h`] })));
    const at = async (x, y) => {
        const lv = finest(x, y);
        const got = await h(lv);
        const a = Object.values(got)[0];
        const Gd = await import('../../core/grid.js');
        return Gd.sampleBilinear(a.data, a.shape, lv.x0, lv.y0, lv.cell, x, y);
    };
    const m = Object.values(await h(main))[0].data;
    let lo = Infinity;
    for (const x of m) if (x < lo) lo = x;
    return { at, zmin: lo };
}

/** The Blender job's cameras for the port's save (see the top): a views JSON in the save's own datum. */
async function portViews(blenderViews, base) {
    const g = await mainHeights(base);
    const out = structuredClone(blenderViews);
    for (const [kind, view] of Object.entries(out)) {
        view.z_origin_m = g.zmin;                          // positions are metres above the tile's lowest point
        if (kind === 'eye') {
            const [cx, cy, cz] = view.camera, [tx, ty, tz] = view.target;
            const pitch = Math.atan2(tz - cz, Math.hypot(tx - cx, ty - cy));
            const ground = (await g.at(cx, cy)) - g.zmin;
            view.camera = [cx, cy, ground + 1.7];
            view.ground_z = ground;
            view.target = [tx, ty, view.camera[2] + Math.hypot(tx - cx, ty - cy) * Math.tan(pitch)];
            view.note = 'the Blender eye spot, 1.7 m above the port\'s ground, the target at the Blender view\'s pitch';
        } else if (kind === 'aerial') {
            const [tx, ty] = view.target;
            const dz = (await g.at(tx, ty)) - g.zmin - view.target[2];
            view.target = [tx, ty, view.target[2] + dz];
            view.camera = [view.camera[0], view.camera[1], view.camera[2] + dz];
        }
    }
    return out;
}

if (flag('--render')) {
    const bv = C.readJson(`${BL}/${label}_views.json`);
    if (!bv) { console.log(`no ${BL}/${label}_views.json: run --blender first`); Deno.exit(2); }
    const rows = [];
    const calls = draft ? [[label, ['top', 'aerial', 'eye']]] : [[label, ['top', 'aerial', 'eye']], [`${label}_hero`, ['eye']]];
    for (const [name, kinds] of calls) {
        const base = portSave(name);
        if (!W.exists(`${base}.npz`)) { console.log(`no ${base}.npz: run --make first`); continue; }
        const pv = await portViews(bv, base);
        const vj = `${PORT}/${name}_port_views_in.json`;
        Deno.writeTextFileSync(vj, JSON.stringify(pv, null, 1));
        const r = await V.renderViews(base, { reference: v.reference, viewsJson: vj, views: kinds, label: `${name}_port`, out: PORT });
        rows.push(r);
    }
    Deno.writeTextFileSync(`${PORT}/${label}_renders.json`, JSON.stringify(rows, null, 1));
    Deno.exit(rows.every((r) => r && Object.values(r.views).every((x) => x.ok)) ? 0 : 1);
}

if (flag('--sheet')) {
    const { sheetPython } = await import('../judge/sheets.mjs');
    const py = sheetPython();
    if (!py) Deno.exit(2);
    // the sheet reads <render-dir>/<label>_<view>.png per row: Blender's renders and the port's side by side
    for (const f of ['top_hillshade', 'aerial_45deg', 'eye_1p7m']) {
        const b = `${BL}/${label}_${f}.png`;
        if (W.exists(b)) Deno.copyFileSync(b, `${PORT}/${label}_blender_${f}.png`);
    }
    // each row's numbers: the Blender judge's verdict of that edition's terrain (judge.mjs judgeSave: Blender's Python)
    const J = await import('../judge/judge.mjs');
    const bsave = draft ? `${S.OUT}/blender_kinds/${variant}_s${seed}/terrain` : `${BL}/${label}`;
    const bvf = `${PORT}/judge_${label}_blender/verdicts.json`;
    if (!W.exists(bvf)) {
        if (W.exists(`${bsave}.json`)) {
            await J.judgeSave(bsave, { reference: v.reference, label: `${label}_blender`, outDir: `${PORT}/judge_${label}_blender` });
        } else {                                      // a Blender job's field item: its numbers from its own npz
            await J.judgeSave(`${BL}/${label}.npz`, { reference: v.reference, label: `${label}_blender`, outDir: `${PORT}/judge_${label}_blender` });
        }
    }
    const pvf = draft ? `${S.OUT}/port_kinds/${variant}_s${seed}/verdicts.json` : `${PORT}/judge_${label}/verdicts.json`;
    const out = `${PORT}/compare_${label}.png`;
    const code = await W.run([py, `${W.TESTS}/judge/sheet_compose.py`, '--reference', v.reference,
        '--row', `${label}_blender=${bvf}`, '--row', `${label}_port=${pvf}`,
        '--render-dir', PORT, '--out', out, '--title',
        `dunes (${variant}) seed ${seed}, ${quality}: the reference, the Blender edition, the three.js port (clay, the reference rig)`],
    { cwd: W.blenderEdition() ?? W.REPO, log: `${PORT}/${label}_sheet.log`,
        env: { ...Deno.env.toObject(), EIDO_BLENDER_EDITION: W.blenderEdition() ?? '', PYTHONDONTWRITEBYTECODE: '1' } });
    console.log(`[render_dunes] sheet: ${code === 0 ? out : `FAILED (exit ${code}): see ${PORT}/${label}_sheet.log`}`);
    Deno.exit(code);
}

console.log('usage: render_dunes.mjs --blender | --make | --render | --sheet [--seed 1] [--variant star] [--quality film]');
Deno.exit(2);
