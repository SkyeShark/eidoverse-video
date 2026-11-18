// The dunes recipe whole, the port's against the Blender edition's, in its class (PORT_PLAN.md 5.3, 5.4, 5.5, 8.4; 8.2
// P8: "parity in class for star, barchan, transverse and linear; the bands against the Namib, Great Sand Dunes, White
// Sands and the Namib linear dunes").
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/wind_sand/recipe_test.mjs [variants]
//
// (from the repository root; no GPU: it reads the saves and verdicts tests/wind_sand/recipe_runs.mjs (the port) and
// tests/wind_sand/blender_kinds.py (Blender) made: seeds 1-4 of each variant at draft quality at the reference's
// extent, the solvers' memos cleared, both judged by the one Blender judge). The chaos floor puts dunes in the
// distribution class (tests/out/parity/<key>/floor.json: its largest main-level sample 2.45 % RMS of relief, over the
// boundary of 0.98 %): one ulp anywhere moves the dunes by their own chaos, so the gate is the judge's numbers over
// seeds 1-4 (tests/judge/judge.mjs compareDistribution): each banded number's mean within half its band's tolerance
// of Blender's mean, and every band Blender passes on 3 or more of the 4 seeds passed by the port on 3 or more.
// Reported beside it, per seed: the bands each edition passes, and the fields level by level (RMS and p99 |dh| over
// relief, the channel overlap: tests/parity/field_parity.mjs) with the floor's tolerances where the floor measured
// that kind and seed (the star kind, seeds 1-2), for the eye. JavaScript per cell here is test code.

import * as FP from '../parity/field_parity.mjs';
import * as J from '../judge/judge.mjs';
import * as C from '../parity/_common.mjs';
import * as S from './_common.mjs';
import { BLENDER_DIR, PORT_DIR, VARIANTS } from './recipe_runs.mjs';

const variants = (Deno.args[0] ?? Object.keys(VARIANTS).join(',')).split(',');
const SEEDS = [1, 2, 3, 4];
const T = new S.Checks('wind and sand: the dunes recipe whole, in its class, against the Blender edition');
const key = S.W.parityKeyDir();
const floor = C.readJson(key ? `${key}/floor.json` : '');
const rec = floor?.recipes?.dunes ?? null;
T.ok('the chaos floor puts dunes in the distribution class (its own five samples over the class boundary)', rec?.class_ === 'distribution',
    rec ? `largest main-level sample ${S.sci(rec.main_level_largest_rms)} RMS of relief, boundary ${S.sci(floor.boundary?.value)}` : 'no floor.json');
const summary = {};
for (const variant of variants) {
    const v = VARIANTS[variant];
    const port = [], blender = [], seedRows = [];
    for (const seed of SEEDS) {
        const pd = `${PORT_DIR}/${variant}_s${seed}`, bd = `${BLENDER_DIR}/${variant}_s${seed}`;
        const pv = C.readJson(`${pd}/verdict.json`), bv = C.readJson(`${bd}/verdict.json`);
        if (!pv || !bv) continue;
        port.push(pv);
        blender.push(bv);
        const passed = (x) => x.rows.filter((r) => r.passed === true).length;
        const judged = (x) => x.rows.filter((r) => r.passed !== null).length;
        const fe = variant === 'star' ? rec?.seeds?.[String(seed)] ?? null : null;
        const fp = await FP.compareSaves(`${bd}/terrain`, `${pd}/terrain`, { floorEntry: fe, class_: null });
        const lv = fp.levels.map((l) => ({ level: l.index, role: l.role, cell: l.cell, rms: +l.rms_over_relief.toPrecision(3),
            p99: +l.p99_abs_over_relief.toPrecision(3), overlap: l.channel_overlap === null ? null : +l.channel_overlap.toFixed(3),
            ...(l.tol_rms != null ? { tol_rms: +l.tol_rms.toPrecision(3), tol_p99: +l.tol_p99.toPrecision(3), overlap_min: l.overlap_min,
                within_floor: l.ok } : {}) }));
        const pr = C.readJson(`${pd}/run.json`), br = C.readJson(`${bd}/run.json`);
        seedRows.push({ seed, bands_blender: `${passed(bv)}/${judged(bv)}`, bands_port: `${passed(pv)}/${judged(pv)}`,
            plan_equal: fp.plan_equal, levels: lv, seconds: [br?.seconds ?? null, pr?.seconds ?? null] });
    }
    if (port.length < 4) {
        T.ok(`${variant}: seeds 1-4 of both editions judged against ${v.reference}`, false,
            `${port.length} of 4: run recipe_runs.mjs and blender_kinds.py first`);
        continue;
    }
    const d = J.compareDistribution(port, blender);
    const badMeans = d.means.filter((m) => !m.ok), badBands = d.bands.filter((b) => !b.ok);
    T.ok(`${variant} against ${v.reference}: the distribution class over seeds 1-4 (each banded number's mean within half its ` +
        'band\'s tolerance of Blender\'s; every band Blender passes on 3 of 4 seeds, the port passes on 3 of 4)', d.ok,
        d.means.map((m) => `${m.metric} ${fmt(m.port)} / ${fmt(m.blender)} (tol ${fmt(m.tol)})${m.ok ? '' : ' OVER'}`).join('; ') +
        (badBands.length ? ` | bands: ${badBands.map((b) => `${b.metric} Blender ${b.blender_passes}/4, port ${b.port_passes}/4`).join(', ')}` : ''));
    T.ok(`${variant}: the same level plan as Blender's on every seed`, seedRows.every((r) => r.plan_equal));
    const main = seedRows.map((r) => r.levels[r.levels.length - 1]);
    T.ok(`${variant}: per seed, the bands passed (Blender | port) and the main level's RMS |dh| over relief (recorded, for the eye)`, true,
        seedRows.map((r, i) => `s${r.seed} ${r.bands_blender} | ${r.bands_port}, RMS ${S.sci(main[i].rms, 2)}` +
            (main[i].tol_rms != null ? ` (floor ${S.sci(main[i].tol_rms, 2)}: ${main[i].within_floor ? 'within' : 'over'})` : '')).join('; '));
    summary[variant] = { reference: v.reference, distribution: d, seeds: seedRows, mean_failures: badMeans.map((m) => m.metric),
        band_failures: badBands.map((b) => b.metric) };
}

function fmt(x) {
    return typeof x === 'number' ? String(+x.toPrecision(4)) : String(x);
}

Deno.exit(S.finish(T, 'recipe_test', { summary }));
