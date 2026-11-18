// The fluvial package's recipes judged whole (PORT_PLAN.md 5.3 "recipe, distribution class" and "judge", 5.5): the
// port's draft saves of seeds 1-4 (bake.mjs --save, the floor runs' own calls) judged by the Blender edition's judge
// (tests/judge/judge.mjs judgeSave: blender/tests/terrain/judge run by Blender's Python) beside the Blender floor
// runs' verdicts of the same seeds. These recipes are of the distribution class (floor.json: a one-ulp difference
// makes another drainage network), so the gate is over seeds, as judge.mjs compareDistribution has it: each banded
// number's mean within half its band's tolerance of Blender's mean, and every band Blender passes on 3 or more of 4
// seeds passed by the port on 3 or more. meadow has no reference DEM: its criteria are the Blender recipe's own
// (slope p99 under 15 degrees, no pits), from core/metrics.js on the main level beside the Blender runs' own numbers.
//
//     <bake the saves> deno run ... eidoverse/terrain/bake.mjs --recipe R --seed S --quality draft --no-cache --save
//                      --out eidoverse/terrain/tests/out/fluvial/saves          (a GPU job each)
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/fluvial/judge_test.mjs
//          [--recipes fluvial_range,meadow] [--seeds 1,2,3,4] [--saves <dir>]
//
// Writes tests/out/fluvial/judge_test.json.

import * as J from '../judge/judge.mjs';
import * as C from '../parity/_common.mjs';

const W = C.W;
const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const RECIPES = opt('--recipes', 'fluvial_range,meadow').split(',');
const SEEDS = opt('--seeds', '1,2,3,4').split(',');
const SAVES = opt('--saves', `${W.out('fluvial')}/saves`);
const T = new C.Checks('fluvial: the recipes judged whole, beside the Blender floor runs');
const out = { recipes: {} };

for (const recipe of RECIPES) {
    const rec = (out.recipes[recipe] = { seeds: {} });
    const port = [], blender = [];
    for (const seed of SEEDS) {
        const base = W.floorRun(recipe, Number(seed));
        const save = `${SAVES}/${recipe}_s${seed}.npz`;
        if (!base || !W.exists(save)) {
            rec.seeds[seed] = { missing: !base ? 'the Blender floor run' : 'the port save' };
            continue;
        }
        if (recipe === 'meadow') {
            const bm = C.readJson(`${base}/run.json`)?.metrics_main ?? null;
            const pm = C.readJson(`${SAVES}/${recipe}_s${seed}_bake.json`)?.metrics ?? null;
            rec.seeds[seed] = { blender: bm && { slope_p99: bm.slope_p99, depression_count: bm.depression_count, relief_m: bm.relief_m },
                port: pm && { slope_p99: pm.slope_p99, depression_count: pm.depression_count, relief_m: pm.relief_m } };
            if (pm) {
                T.ok(`meadow s${seed}: slope p99 under 15 degrees and no pits (the recipe's criteria)`, pm.slope_p99 < 15.0 && pm.depression_count === 0,
                    `port p99 ${pm.slope_p99.toFixed(2)}, ${pm.depression_count} pits (Blender ${bm?.slope_p99?.toFixed(2)}, ${bm?.depression_count} pits)`);
            }
            if (pm && bm) { port.push(pm); blender.push(bm); }
            continue;
        }
        const bv = C.readJson(`${base}/verdict.json`);
        const pv = await J.judgeSave(save, { recipe, label: `${recipe}_seed${seed}`, outDir: `${SAVES}/judge_${recipe}_s${seed}` });
        if (!bv || !pv) {
            rec.seeds[seed] = { missing: !bv ? 'the Blender verdict' : 'the port verdict (see its judge.log)' };
            continue;
        }
        port.push(pv);
        blender.push(bv);
        const rows = (v) => Object.fromEntries(v.rows.filter((r) => r.passed !== null).map((r) => [r.metric, { gen: r.gen, passed: r.passed }]));
        rec.seeds[seed] = { port: rows(pv), blender: rows(bv), port_passed: pv.rows.filter((r) => r.passed).length,
            blender_passed: bv.rows.filter((r) => r.passed).length, bands: pv.rows.filter((r) => r.passed !== null).length };
        console.log(`${recipe} s${seed}: bands passed: port ${rec.seeds[seed].port_passed}, Blender ${rec.seeds[seed].blender_passed} of ` +
            `${rec.seeds[seed].bands}`);
    }
    if (recipe === 'meadow') {
        const mean = (xs, k) => xs.reduce((s, x) => s + x[k], 0) / Math.max(xs.length, 1);
        rec.means = { port: { slope_p99: mean(port, 'slope_p99'), relief_m: mean(port, 'relief_m') },
            blender: { slope_p99: mean(blender, 'slope_p99'), relief_m: mean(blender, 'relief_m') }, seeds: port.length };
        continue;
    }
    if (port.length >= 2) {
        const d = J.compareDistribution(port, blender);
        rec.distribution = d;
        T.ok(`${recipe}: the distribution class over ${port.length} seeds: every banded number's mean within half its band's ` +
            `tolerance of Blender's, every band Blender passes on 3 of 4 seeds passed by the port on 3 of 4`, d.ok && port.length >= 4,
        (port.length < 4 ? `only ${port.length} seeds; ` : '') + d.means.filter((m) => !m.ok).map((m) => `${m.metric} port ${m.port.toPrecision(4)} ` +
            `Blender ${m.blender.toPrecision(4)} (tol ${m.tol?.toPrecision(3)})`).concat(d.bands.filter((b) => !b.ok).map((b) =>
            `${b.metric}: Blender passes ${b.blender_passes}, port ${b.port_passes}`)).join('; '));
    }
}
Deno.writeTextFileSync(`${W.out('fluvial')}/judge_test.json`, JSON.stringify(out, null, 1));
Deno.exit(C.finish(T, '../fluvial/judge_test_checks'));
