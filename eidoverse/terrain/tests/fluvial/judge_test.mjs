// The fluvial package's recipes judged whole (PORT_PLAN.md 5.3 "recipe, distribution class" and "judge", 5.5): the
// port's draft saves of seeds 1-4 (bake.mjs --save, the floor runs' own calls) judged by the Blender edition's judge
// (tests/judge/judge.mjs judgeSave: blender/tests/terrain/judge run by Blender's Python) beside the Blender floor
// runs' verdicts of the same seeds. These recipes are of the distribution class (floor.json: a one-ulp difference
// makes another drainage network), so the gate is over seeds, as judge.mjs compareDistribution has it: each banded
// number's mean within half its band's tolerance of Blender's mean, and every band Blender passes on 3 or more of 4
// seeds passed by the port on 3 or more. meadow has no reference DEM: its criteria are the Blender recipe's own
// (slope p99 under 15 degrees, no pits), from core/metrics.js on the main level beside the Blender runs' own numbers,
// judged by the same class rule: the criteria Blender meets on 3 or more of the 4 seeds, the port meets on 3 or more,
// and (a one-sided criterion has no band tolerance for the mean) the port's mean slope p99 meets the criterion too.
// Each seed's numbers are printed and kept in the JSON; the class rule is the check.
//
//     <bake the saves> deno run ... eidoverse/terrain/bake.mjs --recipe R --seed S --quality draft --no-cache --save
//                      --out eidoverse/terrain/tests/out/fluvial/saves          (a GPU job each)
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/fluvial/judge_test.mjs
//          [--recipes fluvial_range,meadow] [--seeds 1,2,3,4] [--saves <dir>]
//
// A seed whose floor run is missing under the parity key ($EIDO_PARITY_KEY, else the newest) is looked for under the
// other keys of the same Blender terrain code (their manifests' field_hash and terrain_hash equal the key's: another
// commit of the branch that changed no file of the terrain), and the key it came from is recorded.
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
const KEY = W.parityKeyDir();
const out = { key: KEY && KEY.split('/').pop(), recipes: {} };

// the floor run of (recipe, seed) under the key, else under a key of the same terrain code: [dir, key name] or null
function floorRunOfCode(recipe, seed) {
    const own = W.floorRun(recipe, seed);
    if (own) return [own, KEY.split('/').pop()];
    const code = (dir) => { const k = C.readJson(`${dir}/manifest.json`)?.key; return k ? `${k.field_hash}|${k.terrain_hash}` : null; };
    const mine = KEY ? code(KEY) : null;
    if (!mine) return null;
    for (const k of W.parityKeys()) {
        const dir = `${k.dir}/${recipe}_s${seed}_draft/base`;
        if (k.dir !== KEY && code(k.dir) === mine && W.exists(`${dir}/done.json`)) return [dir, k.name];
    }
    return null;
}

for (const recipe of RECIPES) {
    const rec = (out.recipes[recipe] = { seeds: {} });
    const port = [], blender = [];
    for (const seed of SEEDS) {
        const found = floorRunOfCode(recipe, Number(seed));
        const base = found?.[0] ?? null;
        if (found && found[1] !== out.key) (rec.other_keys ??= {})[seed] = found[1];
        const save = `${SAVES}/${recipe}_s${seed}.npz`;
        if (!base || !W.exists(save)) {
            rec.seeds[seed] = { missing: !base ? 'the Blender floor run' : 'the port save' };
            continue;
        }
        if (recipe === 'meadow') {
            const bm = C.readJson(`${base}/run.json`)?.metrics_main ?? null;
            const pm = C.readJson(`${SAVES}/${recipe}_s${seed}_bake.json`)?.metrics ?? null;
            const meets = (m) => m.slope_p99 < 15.0 && m.depression_count === 0;
            rec.seeds[seed] = { blender: bm && { slope_p99: bm.slope_p99, depression_count: bm.depression_count, relief_m: bm.relief_m, meets: meets(bm) },
                port: pm && { slope_p99: pm.slope_p99, depression_count: pm.depression_count, relief_m: pm.relief_m, meets: meets(pm) } };
            if (pm) {
                console.log(`meadow s${seed}: slope p99 under 15 degrees and no pits: port ${meets(pm) ? 'meets' : 'misses'} (p99 ` +
                    `${pm.slope_p99.toFixed(2)}, ${pm.depression_count} pits), Blender ${bm ? (meets(bm) ? 'meets' : 'misses') : '?'} ` +
                    `(p99 ${bm?.slope_p99?.toFixed(2)}, ${bm?.depression_count} pits)`);
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
        const meets = (m) => m.slope_p99 < 15.0 && m.depression_count === 0;
        const bp = blender.filter(meets).length, pp = port.filter(meets).length, need = Math.ceil(0.75 * port.length);
        rec.distribution = { blender_meets: bp, port_meets: pp, of: port.length, need, means: rec.means };
        T.ok(`meadow: the distribution class over ${port.length} seeds: the criteria (slope p99 under 15 degrees, no pits) met by ` +
            `the port on 3 of 4 seeds where Blender meets them on 3 of 4, and the port's mean slope p99 under 15 degrees`,
        port.length >= 4 && (bp < need || pp >= need) && rec.means.port.slope_p99 < 15.0,
        `Blender meets them on ${bp} of ${blender.length} seeds, the port on ${pp} of ${port.length}; mean slope p99 port ` +
            `${rec.means.port.slope_p99.toFixed(2)}, Blender ${rec.means.blender.slope_p99.toFixed(2)}`);
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
