// The volcanoes and craters package's recipes judged whole (PORT_PLAN.md 8.2 row P9 "parity in class (caldera,
// cinder_cones, impact_crater first; stratovolcano once P12 lands)", "the bands against Fuji, Crater Lake, SP Crater
// and Meteor Crater"; 8.4, 5.3, 5.5): the port's draft saves (bake.mjs --save: makeTerrain through run.js, the
// recipe's defaults at the floor run's size) against the Blender floor runs of the same recipe and seed. All four
// recipes are field class (floor.json), seeds 1-2:
//   levels   per level RMS(dh) / relief and p99 |dh| / relief within 1.25 x the largest floor sample (never below
//            1e-4), the channel overlap at least the smallest sample's minus the samples' spread
//            (tests/parity/field_parity.mjs compareSaves)
//   judge    every number of the Blender judge on the port's save within its tolerance of the Blender save's
//            (tests/judge/judge.mjs compareVerdicts: 1.25 x the floor's largest change, a spectrum band, 1 % of the
//            band's tolerance); the bands each passes are reported beside Blender's (the references: Mount Fuji,
//            Crater Lake, SP Crater, Meteor Crater)
// A floor run missing under the parity key is taken from another key of the same Blender terrain code (_vc.mjs).
//
//     <the saves> deno run ... eidoverse/terrain/bake.mjs --recipe R --seed S --quality draft --no-cache --save
//                 --name R_sS [--size <the floor run's size>] --out eidoverse/terrain/tests/out/volcanoes_craters/saves
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/volcanoes_craters/whole_test.mjs
//         [--recipes caldera,...] [--saves <dir>]
// Writes tests/out/volcanoes_craters/whole_test.json and whole_test_detail.json. JavaScript per cell here is test
// code.

import * as J from '../judge/judge.mjs';
import * as FP from '../parity/field_parity.mjs';
import * as V from './_vc.mjs';

const { C, W } = V;
const A = V.argsOf();
const recipes = A.list('--recipes') ?? V.RECIPES;
const SAVES = A.opt('--saves', `${W.out('volcanoes_craters')}/saves`);
const T = new C.Checks('volcanoes_craters: the recipes judged whole, beside the Blender floor runs');
const KEY = W.parityKeyDir();
const out = { key: KEY?.split('/').pop() ?? null, recipes: {} };

for (const recipe of recipes) {
    let floor = null;
    const seeds = [1, 2];
    const rec = (out.recipes[recipe] = { seeds: {} });
    for (const seed of seeds) {
        const found = V.floorRunOfCode(recipe, seed);
        const save = `${SAVES}/${recipe}_s${seed}`;
        if (!found || !W.exists(`${save}.npz`)) {
            rec.seeds[seed] = { missing: !found ? 'the Blender floor run' : `the port save ${save}.npz` };
            T.ok(`${recipe} s${seed}: a Blender floor run and a port save`, false, rec.seeds[seed].missing);
            continue;
        }
        const [base, key] = found;
        floor ??= C.readJson(`${base}/../../floor.json`, { recipes: {} });
        const fr = floor.recipes?.[recipe] ?? null;
        const cls = fr?.class_ ?? fr?.class ?? null;
        rec.class = cls;
        const entry = fr?.seeds?.[String(seed)] ?? null;
        const s = (rec.seeds[seed] = { floor_key: key });
        const f = await FP.compareSaves(`${base}/terrain`, save, { floorEntry: entry, class_: cls });
        s.levels = f.levels;
        s.plan_equal = f.plan_equal;
        for (const l of f.levels) {
            T.ok(`${recipe} s${seed} L${l.index} (${l.role}, ${l.cell} m): RMS ${C.sci(l.rms_over_relief, 2)} of relief (<= ` +
                `${C.sci(l.tol_rms, 2)}), p99 ${C.sci(l.p99_abs_over_relief, 2)} (<= ${C.sci(l.tol_p99, 2)})` +
                (l.channel_overlap != null ? `, channel overlap ${l.channel_overlap.toFixed(3)} (>= ${l.overlap_min?.toFixed(3)})` : ''),
            l.ok === true, f.plan_equal ? '' : 'THE PLANS DIFFER');
        }
        const bv = C.readJson(`${base}/verdict.json`);
        const pv = await J.judgeSave(`${save}.npz`, { recipe, label: `${recipe}_seed${seed}`, outDir: `${SAVES}/judge_${recipe}_s${seed}` });
        if (!bv || !pv) {
            s.judge = { missing: !bv ? 'the Blender verdict' : 'the port verdict (see its judge.log)' };
            T.ok(`${recipe} s${seed}: judged`, false, s.judge.missing);
            continue;
        }
        const passed = (v) => v.rows.filter((r) => r.passed).length;
        const banded = bv.rows.filter((r) => r.passed !== null).length;
        s.bands = { port: passed(pv), blender: passed(bv), of: banded };
        s.numbers = Object.fromEntries(bv.rows.filter((r) => r.passed !== null).map((r) => [r.metric,
            { blender: r.gen, port: pv.rows.find((q) => q.metric === r.metric)?.gen ?? null, ref: r.ref ?? null,
                blender_passed: r.passed, port_passed: pv.rows.find((q) => q.metric === r.metric)?.passed ?? null }]));
        const cv = J.compareVerdicts(pv, bv, entry);
        s.judge = cv;
        const show = (v) => (typeof v === 'number' ? v.toPrecision(5) : JSON.stringify(v)?.slice(0, 60));
        T.ok(`${recipe} s${seed}: every judge number within its tolerance of Blender's (${cv.rows.length} numbers)`, cv.ok,
            cv.rows.filter((r) => !r.ok).map((r) => `${r.metric} ${show(r.port)} / ${show(r.blender)} (tol ${r.tol?.toPrecision?.(3)})`)
                .join('; ') + ` | bands passed: port ${s.bands.port}, Blender ${s.bands.blender} of ${banded}`);
        console.log(`${recipe} s${seed}: bands passed: port ${s.bands.port}, Blender ${s.bands.blender} of ${banded}`);
    }
}
Deno.writeTextFileSync(`${W.out('volcanoes_craters')}/whole_test_detail.json`, JSON.stringify(out, null, 1));
Deno.exit(V.finish(T, 'whole_test', { key: out.key }));
