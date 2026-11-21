// The package's recipes judged whole (PORT_PLAN.md 5.3 "recipe" and "judge", 5.4, 5.5, table 8.4): the port's draft
// saves (bake.mjs --save, the floor runs' own calls) beside the Blender floor runs of the same recipe and seed.
//   tower_karst  field class (floor.json: one ulp leaves its heights within 1.8e-8 of relief, so its tolerance is the
//                kernel grade, 1e-4): per level RMS and p99 |dh| over relief within the floor's tolerances and the
//                channel overlap at or above its minimum (tests/parity/field_parity.mjs compareSaves), seeds 1 and 2;
//                the Blender judge's numbers on the port's save within max(1.25 x the floor's largest change, one bin
//                of the spectrum, 1 % of the band's tolerance, 1e-4 of the number) of the Blender save's
//                (tests/judge/judge.mjs compareVerdicts)
//   sea_cliffs   distribution class (floor.json: 1.50 % RMS on one ulp): the Blender judge over seeds 1-4, each banded
//                number's mean within half its band's tolerance of Blender's mean, every band Blender passes on 3 or
//                more of the 4 seeds passed by the port on 3 or more (judge.mjs compareDistribution); per level numbers
//                reported for the eye
//   Moher        sea_cliffs rock 'layered' (the floor runs hold the chalk default only): the port's save and the
//                Blender edition's own save of the same call (its bake.py, tests/out/karst_coast/blender_saves/),
//                both judged against cliffs_of_moher, one seed: numbers side by side, verdicts reported
//                (--recipes sea_cliffs_layered)
//
//     <the saves> deno run ... eidoverse/terrain/bake.mjs --recipe R --seed S --quality draft --no-cache --save
//                 --name R_sS --out eidoverse/terrain/tests/out/karst_coast/saves              (a GPU job each)
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/karst_coast/judge_test.mjs
//          [--recipes tower_karst,sea_cliffs] [--seeds ...] [--saves <dir>]
//
// A floor run missing under the parity key is taken from another key of the same Blender terrain code. Writes
// tests/out/karst_coast/judge_test.json.

import * as J from '../judge/judge.mjs';
import * as FP from '../parity/field_parity.mjs';
import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const RECIPES = opt('--recipes', 'tower_karst,sea_cliffs').split(',');
const SAVES = opt('--saves', `${KC.OUT()}/saves`);
const SEEDS = { tower_karst: ['1', '2'], sea_cliffs: ['1', '2', '3', '4'] };
const REFERENCE = { tower_karst: 'guilin_karst', sea_cliffs: 'seven_sisters' };
const T = new C.Checks('karst and coast: the recipes judged whole, beside the Blender floor runs');
const out = { recipes: {} };

// floor.json of the key a run came from
const floorOf = (key) => C.readJson(`${W.parityOut()}/${key}/floor.json`, { recipes: {} });

for (const recipe of RECIPES.filter((r) => r in SEEDS)) {
    const rec = (out.recipes[recipe] = { seeds: {} });
    const seeds = opt('--seeds', null)?.split(',') ?? SEEDS[recipe];
    const port = [], blender = [];
    let cls = null;
    for (const seed of seeds) {
        const found = KC.floorRunOfCode(recipe, Number(seed));
        const save = `${SAVES}/${recipe}_s${seed}`;
        if (!found || !W.exists(`${save}.npz`)) {
            rec.seeds[seed] = { missing: !found ? 'the Blender floor run' : 'the port save' };
            T.ok(`${recipe} s${seed}: inputs`, false, rec.seeds[seed].missing);
            continue;
        }
        const [base, key] = found;
        const floor = floorOf(key);
        cls = floor.recipes?.[recipe]?.class ?? cls;
        const entry = floor.recipes?.[recipe]?.seeds?.[seed] ?? null;
        const bv = C.readJson(`${base}/verdict.json`);
        const pv = await J.judgeSave(`${save}.npz`, { recipe, label: `${recipe}_s${seed}_port`, outDir: `${KC.OUT()}/judge/${recipe}_s${seed}` });
        const row = (rec.seeds[seed] = { key, class: cls, blender_passed: bv?.passed ?? null, port_passed: pv?.passed ?? null });
        if (pv) port.push(pv);
        if (bv) blender.push(bv);
        const fields = await FP.compareSaves(`${base}/terrain`, save, { floorEntry: entry, class_: cls });
        row.levels = fields.levels;
        row.other_fields = fields.fields;
        const lvText = (l) => `L${l.index} RMS ${C.sci(l.rms_over_relief, 2)}${l.tol_rms != null ? ` (tol ${C.sci(l.tol_rms, 2)})` : ''} ` +
            `p99 ${C.sci(l.p99_abs_over_relief, 2)}${l.tol_p99 != null ? ` (tol ${C.sci(l.tol_p99, 2)})` : ''}` +
            (l.channel_overlap != null ? ` overlap ${l.channel_overlap.toFixed(3)}${l.overlap_min != null ? ` (min ${l.overlap_min.toFixed(3)})` : ''}` : '');
        if (cls === 'field' || recipe === 'tower_karst') {
            T.ok(`${recipe} s${seed}: every level within the floor's tolerances (RMS, p99, channel overlap; field class)`,
                fields.ok === true && fields.judged, fields.levels.map(lvText).join('; '));
            if (pv && bv) {
                const v = J.compareVerdicts(pv, bv, entry);
                row.judge = v;
                T.ok(`${recipe} s${seed}: the judge's numbers on the port's save within their grades of the Blender save's ` +
                    `(verdicts: port ${pv.passed}, Blender ${bv.passed})`, v.ok, v.failures.join(', ') || `${v.rows.length} numbers`);
            }
        } else {
            console.log(`${recipe} s${seed} (distribution class): ` + fields.levels.map(lvText).join('; '));
        }
    }
    if (cls !== 'field' && recipe !== 'tower_karst' && port.length && blender.length) {
        const d = J.compareDistribution(port, blender);
        rec.distribution = d;
        T.ok(`${recipe}: the distribution class over ${port.length} port and ${blender.length} Blender seeds (banded means ` +
            'within half their tolerance; every band Blender passes on 3 of 4, the port on 3 of 4)', d.ok,
        d.means.filter((m) => !m.ok).map((m) => `${m.metric} mean ${m.port.toFixed(3)} vs ${m.blender.toFixed(3)} (tol ${m.tol?.toFixed(3)})`)
            .concat(d.bands.filter((b) => !b.ok).map((b) => `${b.metric} passes ${b.port_passes} of ${b.of[1]} vs ${b.blender_passes} of ${b.of[0]}`)).join('; ') ||
            `${d.means.length} banded numbers`);
    }
}
// Moher: rock 'layered' (not in the floor runs, whose sea_cliffs is the chalk default): the port's save and the
// Blender edition's own of the same call (its bake.py, tests/out/karst_coast/blender_saves/), both judged against
// cliffs_of_moher; one seed, so its numbers are reported side by side, the verdicts named
if (!opt('--recipes', null) || RECIPES.includes('sea_cliffs_layered')) {
    const seed = opt('--seeds', '1').split(',')[0];
    const port = `${SAVES}/sea_cliffs_layered_s${seed}.npz`, blend = `${KC.OUT()}/blender_saves/sea_cliffs_layered_s${seed}.npz`;
    if (W.exists(port) && W.exists(blend)) {
        const jo = { recipe: 'sea_cliffs', reference: 'cliffs_of_moher' };
        const pv = await J.judgeSave(port, { ...jo, label: `sea_cliffs_layered_s${seed}_port`, outDir: `${KC.OUT()}/judge/sea_cliffs_layered_s${seed}` });
        const bv = await J.judgeSave(blend, { ...jo, label: `sea_cliffs_layered_s${seed}_blender`, outDir: `${KC.OUT()}/judge/sea_cliffs_layered_s${seed}_blender` });
        const rows = [];
        for (const [k, b] of Object.entries(bv?.numbers?.generated ?? {})) {
            const p = pv?.numbers?.generated?.[k];
            if (typeof b === 'number' && typeof p === 'number') rows.push({ metric: k, port: p, blender: b });
        }
        out.moher = { seed, port_passed: pv?.passed ?? null, port_failures: pv?.failures ?? null, blender_passed: bv?.passed ?? null,
            blender_failures: bv?.failures ?? null, numbers: rows };
        T.ok(`sea_cliffs rock 'layered' s${seed} against the Cliffs of Moher: reported (verdicts: port ${pv?.passed}, ` +
            `Blender ${bv?.passed})`, pv !== null && bv !== null,
        `port fails: ${(pv?.failures ?? []).join('; ') || 'none'} | Blender fails: ${(bv?.failures ?? []).join('; ') || 'none'}`);
    } else {
        console.log(`[skip] Moher: needs ${W.exists(port) ? '' : port} ${W.exists(blend) ? '' : blend}`);
    }
}
out.reference = REFERENCE;
Deno.exit(KC.finish(T, 'judge_test', out));
