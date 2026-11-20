// The layered-rock package's recipes judged whole (PORT_PLAN.md 8.2 row P10 "parity in class", 8.4, 5.3, 5.5): the
// port's draft saves (bake.mjs --save: makeTerrain through run.js, the recipe's defaults) against the Blender floor
// runs of the same recipe and seed, by the class floor.json gives each recipe:
//   field class (incised_meanders, mesas_buttes, badlands; seeds 1-2):
//     levels   per level RMS(dh) / relief and p99 |dh| / relief within 1.25 x the largest floor sample (never below
//              1e-4), the channel overlap at least the smallest sample's minus the samples' spread
//              (tests/parity/field_parity.mjs compareSaves)
//     judge    every number of the Blender judge on the port's save within its tolerance of the Blender save's
//              (tests/judge/judge.mjs compareVerdicts: 1.25 x the floor's largest change, a spectrum band, 1 % of the
//              band's tolerance); the verdicts are reported, not compared
//   distribution class (canyon; seeds 1-4): every banded number's mean within half its band's tolerance of Blender's
//     mean, every band Blender passes on 3 or more of the 4 seeds passed by the port on 3 or more
//     (judge.mjs compareDistribution)
// A floor run missing under the parity key ($EIDO_PARITY_KEY, else the newest) is taken from another key of the same
// Blender terrain code (equal field and terrain hashes), as tests/fluvial/judge_test.mjs takes it.
//
//     <the saves> deno run ... eidoverse/terrain/bake.mjs --recipe R --seed S --quality draft --no-cache --save
//                 --name R_sS --out eidoverse/terrain/tests/out/layered_rock/saves          (a GPU job each)
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/layered_rock/whole_test.mjs
//         [--recipes canyon,...] [--saves <dir>]
// Writes tests/out/layered_rock/whole_test.json. JavaScript per cell here is test code.

import * as J from '../judge/judge.mjs';
import * as FP from '../parity/field_parity.mjs';
import { C, RECIPES, W, argsOf, finish } from './_layered.mjs';

const A = argsOf();
const recipes = A.recipes ? String(A.recipes).split(',') : RECIPES;
const SAVES = A.saves ?? `${W.out('layered_rock')}/saves`;
const T = new C.Checks('layered_rock: the recipes judged whole, beside the Blender floor runs');
const KEY = W.parityKeyDir();
const floor = C.readJson(`${KEY}/floor.json`, { recipes: {} });
const out = { key: KEY?.split('/').pop() ?? null, recipes: {} };

// the floor run of (recipe, seed) under the key, else under a key of the same terrain code: [dir, key name] or null
function floorRunOfCode(recipe, seed) {
    const own = W.floorRun(recipe, seed);
    if (own) return [own, out.key];
    const code = (dir) => { const k = C.readJson(`${dir}/manifest.json`)?.key; return k ? `${k.field_hash}|${k.terrain_hash}` : null; };
    const mine = KEY ? code(KEY) : null;
    if (!mine) return null;
    for (const k of W.parityKeys()) {
        const dir = `${k.dir}/${recipe}_s${seed}_draft/base`;
        if (k.dir !== KEY && code(k.dir) === mine && W.exists(`${dir}/done.json`)) return [dir, k.name];
    }
    return null;
}

for (const recipe of recipes) {
    const fr = floor.recipes?.[recipe] ?? null;
    const cls = fr?.class_ ?? fr?.class ?? null;
    const rec = (out.recipes[recipe] = { class: cls, seeds: {} });
    const seeds = cls === 'distribution' ? [1, 2, 3, 4] : [1, 2];
    const port = [], blender = [];
    for (const seed of seeds) {
        const found = floorRunOfCode(recipe, seed);
        const save = `${SAVES}/${recipe}_s${seed}`;
        if (!found || !W.exists(`${save}.npz`)) {
            rec.seeds[seed] = { missing: !found ? 'the Blender floor run' : `the port save ${save}.npz` };
            T.ok(`${recipe} s${seed}: a Blender floor run and a port save`, false, rec.seeds[seed].missing);
            continue;
        }
        const [base, key] = found;
        const s = (rec.seeds[seed] = { floor_key: key });
        const entry = fr?.seeds?.[String(seed)] ?? null;
        if (cls === 'field') {
            const f = await FP.compareSaves(`${base}/terrain`, save, { floorEntry: entry, class_: cls });
            s.levels = f.levels;
            s.plan_equal = f.plan_equal;
            for (const l of f.levels) {
                T.ok(`${recipe} s${seed} L${l.index} (${l.role}, ${l.cell} m): RMS ${C.sci(l.rms_over_relief, 2)} of relief (<= ` +
                    `${C.sci(l.tol_rms, 2)}), p99 ${C.sci(l.p99_abs_over_relief, 2)} (<= ${C.sci(l.tol_p99, 2)})` +
                    (l.channel_overlap != null ? `, channel overlap ${l.channel_overlap.toFixed(3)} (>= ${l.overlap_min?.toFixed(3)})` : ''),
                l.ok === true, f.plan_equal ? '' : 'THE PLANS DIFFER');
            }
        }
        const bv = C.readJson(`${base}/verdict.json`);
        const pv = await J.judgeSave(`${save}.npz`, { recipe, label: `${recipe}_seed${seed}`, outDir: `${SAVES}/judge_${recipe}_s${seed}` });
        if (!bv || !pv) {
            s.judge = { missing: !bv ? 'the Blender verdict' : 'the port verdict (see its judge.log)' };
            T.ok(`${recipe} s${seed}: judged`, false, s.judge.missing);
            continue;
        }
        port.push(pv);
        blender.push(bv);
        const passed = (v) => v.rows.filter((r) => r.passed).length;
        const banded = bv.rows.filter((r) => r.passed !== null).length;
        s.bands = { port: passed(pv), blender: passed(bv), of: banded };
        s.numbers = Object.fromEntries(bv.rows.filter((r) => r.passed !== null).map((r) => [r.metric,
            { blender: r.gen, port: pv.rows.find((q) => q.metric === r.metric)?.gen ?? null, ref: r.ref ?? null,
                blender_passed: r.passed, port_passed: pv.rows.find((q) => q.metric === r.metric)?.passed ?? null }]));
        if (cls === 'field') {
            const cv = J.compareVerdicts(pv, bv, entry);
            s.judge = cv;
            T.ok(`${recipe} s${seed}: every judge number within its tolerance of Blender's (${cv.rows.length} numbers)`, cv.ok,
                cv.rows.filter((r) => !r.ok).map((r) => `${r.metric} ${typeof r.port === 'number' ? r.port.toPrecision(5) : r.port} / ` +
                    `${typeof r.blender === 'number' ? r.blender.toPrecision(5) : r.blender} (tol ${r.tol?.toPrecision?.(3)})`).join('; ') +
                ` | bands passed: port ${s.bands.port}, Blender ${s.bands.blender} of ${banded}`);
        }
        console.log(`${recipe} s${seed}: bands passed: port ${s.bands.port}, Blender ${s.bands.blender} of ${banded}`);
    }
    if (cls === 'distribution' && port.length) {
        const d = J.compareDistribution(port, blender);
        rec.distribution = d;
        T.ok(`${recipe}: the distribution class over ${port.length} seeds: every banded number's mean within half its band's ` +
            'tolerance of Blender\'s, every band Blender passes on 3 of 4 seeds passed by the port on 3 of 4', d.ok && port.length >= 4,
        (port.length < 4 ? `only ${port.length} seeds; ` : '') + d.means.map((m) => `${m.metric} ${m.port.toPrecision(4)} / ` +
            `${m.blender.toPrecision(4)} (tol ${m.tol?.toPrecision(3)}${m.ok ? '' : ' OVER'})`).join(', ') + '; ' +
            d.bands.filter((b) => !b.ok).map((b) => `${b.metric}: Blender passes ${b.blender_passes}, port ${b.port_passes}`).join('; '));
    }
}
Deno.writeTextFileSync(`${W.out('layered_rock')}/whole_test_detail.json`, JSON.stringify(out, null, 1));
Deno.exit(finish(T, 'whole_test', { key: out.key }));
