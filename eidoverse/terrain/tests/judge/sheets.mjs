// The compare sheets (PORT_PLAN.md 6.3): per place or recipe, the reference's row (its Blender renders and numbers)
// above the port's row (the three views tests/judge/views.mjs rendered, and the Blender judge's numbers of the same
// save), laid out by the Blender judge's own sheet (judge/sheet.py compose, through tests/judge/sheet_compose.py).
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/judge/sheets.mjs --places a,b --saves <dir>
//          [--renders <dir>] [--out <png>]
//                 each place's save (views.mjs --bake made them) judged against its reference by the Blender judge
//                 (judge.mjs judgeSave, Blender's Python; a real_place save holds the reference's own data, so no
//                 source chain), its row's renders from --renders (views.mjs's out, default tests/out/judge/views),
//                 one sheet a place (<renders>/compare_<place>.png) and all of them stacked (--out, default
//                 <renders>/views_sheet.png)
//
// The sheet runs in a Python that has Pillow ($EIDO_SHEET_PYTHON, else `python` on the path): it lays out the
// pictures and the numbers the judge made, and computes none (the numbers stay Blender's Python's, plan C6).

import * as W from '../_where.mjs';
import * as J from './judge.mjs';
import { PLACES } from './views.mjs';

const HERE = W.urlPath(new URL('./', import.meta.url));

/** A Python with Pillow for the sheet: $EIDO_SHEET_PYTHON, else python (or python3) on the path; null after saying
 * what to set. */
export function sheetPython() {
    const e = Deno.env.get('EIDO_SHEET_PYTHON');
    if (e && W.exists(e)) return W.norm(e);
    const p = W.which('python') ?? W.which('python3');
    if (!p) W.skip('the compare sheet', 'needs a Python with Pillow: set EIDO_SHEET_PYTHON');
    return p;
}

/** One place's sheet: its save judged, its renders and the reference's laid out. { place, verdict, sheet, ok }. */
export async function placeSheet(place, save, renders) {
    const outDir = `${renders}/judge_${place}`;
    const v = await J.judgeSave(save, { reference: place, label: `${place}_port`, outDir, sourceChain: false });
    if (!v) return { place, ok: false, why: 'the judge failed' };
    const py = sheetPython();
    if (!py) return { place, ok: false, why: 'no Python with Pillow' };
    const sheet = `${renders}/compare_${place}.png`;
    const code = await W.run([py, `${HERE}/sheet_compose.py`, '--reference', place, '--row', `${place}_port=${outDir}/verdicts.json`,
        '--render-dir', renders, '--out', sheet, '--title', `${place}: the Blender reference renders above, the three.js port's renders of the same DEM below`],
    { cwd: W.blenderEdition() ?? W.REPO, log: `${outDir}/sheet.log`,
        env: { ...Deno.env.toObject(), EIDO_BLENDER_EDITION: W.blenderEdition() ?? '', PYTHONDONTWRITEBYTECODE: '1' } });
    const judged = v.rows.filter((r) => r.passed !== null);
    return { place, ok: code === 0 && W.exists(sheet), sheet, verdict: `${outDir}/verdicts.json`, passed: v.passed,
        bands: [judged.filter((r) => r.passed).length, judged.length] };
}

if (import.meta.main) {
    const args = [...Deno.args];
    const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args.splice(i, 2)[1] : null; };
    const places = opt('--places')?.split(',').filter(Boolean) ?? PLACES, saves = opt('--saves');
    const renders = W.absPath(opt('--renders') ?? `${W.out('judge')}/views`), outPng = opt('--out');
    if (!saves) {
        console.log('usage: sheets.mjs --places a,b --saves <dir> [--renders <dir>] [--out <png>]');
        Deno.exit(2);
    }
    const rows = [];
    for (const p of places) {
        const r = await placeSheet(p, `${W.absPath(saves)}/${p}`, renders);
        rows.push(r);
        console.log(`[sheets] ${p}: ${r.ok ? r.sheet : `FAILED: ${r.why ?? 'see the sheet log'}`}` +
            (r.bands ? ` (the judge: ${r.passed ? 'PASS' : 'FAIL'}, ${r.bands[0]} of ${r.bands[1]} bands)` : ''));
    }
    const sheets = rows.filter((r) => r.ok).map((r) => r.sheet);
    const all = W.absPath(outPng ?? `${renders}/views_sheet.png`);
    if (sheets.length) {
        await W.run([sheetPython(), `${HERE}/sheet_compose.py`, '--stack', all, ...sheets], { cwd: W.REPO });
    }
    Deno.writeTextFileSync(`${renders}/sheets.json`, JSON.stringify({ date: new Date().toISOString(), sheet: all, rows }, null, 1));
    Deno.exit(rows.every((r) => r.ok) ? 0 : 1);
}
