// The karst plan against numpy's (PORT_PLAN.md 8.2 row P11, 5.1 "plan fixtures", 5.3 "plans: 1e-12 relative"):
// solvers/karst.js planKarst for every plan_karst call the tower_karst floor runs made, re-made for seeds 1-8 by
// tests/parity/fixtures.py --plans (Blender's Python 3.13, numpy 2.3.4): the Poisson disc's towers, every tower's
// shape numbers, peaks, ribs, scarps, bodies and wall tables, the river's least-cost course, its resamplings,
// curvature and widths, the cluster field's threshold (numpy 2.3.4's quantile, karst.py:744) and spread, the stats.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/karst_coast/plan_test.mjs [--seeds 1,2]
//
// Grades: integers (kinds, peak counts, tower counts) and NaN positions exact; every float array within 1e-12 of its
// largest |value| (plan 5.3: V8's Math and the C library differ in the last ulp at most); the stats JSON-equal.
// No GPU: the plan is JavaScript on the CPU (plan 2.4). Writes tests/out/karst_coast/plan_test.json.

import * as K from '../../solvers/karst.js';
import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';

const args = [...Deno.args];
const at = args.indexOf('--seeds');
const SEEDS = at >= 0 ? args[at + 1].split(',').map(Number) : null;
const T = new C.Checks('karst and coast: the karst plan against numpy');
const results = { seeds: {} };

// the noise tables the plan's world functions read
const fx = KC.loadFixtures();
const gt = fx && KC.findCase(fx, 'karst._GX16');
if (gt) {
    const gx = C.array(fx.dir, gt.outputs.gx), gy = C.array(fx.dir, gt.outputs.gy);
    const same = K.GX16.every((v, i) => v === gx[i]) && K.GY16.every((v, i) => v === gy[i]);
    let worst = 0;
    K.GX16.forEach((v, i) => { worst = Math.max(worst, Math.abs(v - gx[i]), Math.abs(K.GY16[i] - gy[i])); });
    T.ok("karst's 16 gradient directions bit for bit numpy's (np.cos, np.sin)", same, `largest difference ${C.sci(worst)}`);
} else {
    T.ok("karst's 16 gradient directions bit for bit numpy's (np.cos, np.sin)", false, KC.NO_FIXTURES);
}

const PF = KC.parityFixtures('plans');
const cases = PF ? PF.manifest.cases.filter((c) => c.function === 'solvers.karst.plan_karst' && (!SEEDS || SEEDS.includes(c.seed))) : [];
if (!cases.length) T.ok('karst plan fixtures', false, 'no karst plan fixtures (tests/parity/fixtures.py --plans)');

const arrOf = (c, name) => {
    const a = c.outputs[`result.${name}`];
    return a ? C.array(PF.dir, a) : null;
};

// a float array graded against numpy's: NaN positions equal, within k of the largest |value|
function gradeFloats(got, want, k = 1e-12) {
    if (got.length !== want.length) return { ok: false, detail: `length ${got.length}, numpy ${want.length}` };
    let amax = 0, err = 0, at = -1, nanBad = 0;
    for (let i = 0; i < want.length; i++) {
        const w = want[i], g = got[i];
        if (Number.isNaN(w) || Number.isNaN(g)) { if (Number.isNaN(w) !== Number.isNaN(g)) nanBad++; continue; }
        if (!Number.isFinite(w) || !Number.isFinite(g)) { if (w !== g) nanBad++; continue; }
        amax = Math.max(amax, Math.abs(w));
        const e = Math.abs(g - w);
        if (e > err) { err = e; at = i; }
    }
    const rel = amax ? err / amax : err;
    return { ok: nanBad === 0 && rel <= k, rel, at, nanBad, detail: `${C.sci(rel)} of the largest |value|` + (nanBad ? `, ${nanBad} NaN/inf positions differ` : '') };
}

for (const c of cases) {
    const [seed, domain, params, via, main] = c.call.args;
    const r = c.result;
    const t0 = performance.now();
    let plan, error = null;
    try {
        plan = K.planKarst(seed, domain, params, via, main);
    } catch (e) {
        error = `${e.name}: ${e.message}`;
    }
    const seconds = (performance.now() - t0) / 1000;
    const row = { seconds: +seconds.toFixed(2), fields: {} };
    results.seeds[seed] = row;
    if (error) { T.ok(`seed ${seed}: planKarst runs`, false, error); continue; }
    const fails = [];
    const note = (name, ok, detail) => { row.fields[name] = { ok, detail }; if (!ok) fails.push(`${name} (${detail})`); };
    // scalars
    for (const k of ['salt', 'strike', 'cluster_threshold', 'cluster_band', 'cluster_std', 'water_level']) {
        const g = plan[k], w = r[k];
        const ok = g === w || Math.abs(g - w) <= 1e-12 * Math.abs(w);
        note(k, ok, `${g} against ${w}`);
    }
    note('river_dir', plan.river_dir.every((v, i) => Math.abs(v - r.river_dir[i]) <= 1e-12), `${plan.river_dir} against ${r.river_dir}`);
    note('count', plan.count === r.x.shape[0], `${plan.count} towers against ${r.x.shape[0]}`);
    if (plan.count === r.x.shape[0]) {
        for (const k of ['kind', 'npk']) {
            const want = arrOf(c, k), got = plan[k];
            let bad = 0;
            for (let i = 0; i < want.length; i++) if (Number(want[i]) !== Number(got[i])) bad++;
            note(k, bad === 0, `${bad} of ${want.length} differ`);
        }
        for (const k of ['x', 'y', 'H', 'F', 'R', 'wall', 'floor', 'B', 'reach', 'elong', 'axis', 'lean', 'lean_dir', 'cluster',
            'interior', 'spur', 'pk_dx', 'pk_dy', 'pk_h', 'pk_r0', 'pk_b', 'pk_e', 'pk_axis', 'pk_rib', 'scarp', 'body_h',
            'body_R', 'body_tan']) {
            const g = gradeFloats(plan[k], arrOf(c, k));
            note(k, g.ok, g.detail);
        }
        // the wall tables (a list of arrays per tower)
        for (const k of ['wall_D', 'wall_Z', 'wall_D0']) {
            let worst = 0, lenBad = 0;
            r[k].forEach((want, t) => {
                const got = plan[k][t];
                if (got.length !== want.length) { lenBad++; return; }
                let amax = 0;
                for (const v of want) amax = Math.max(amax, Math.abs(v));
                for (let i = 0; i < want.length; i++) worst = Math.max(worst, Math.abs(got[i] - want[i]) / (amax || 1));
            });
            note(k, lenBad === 0 && worst <= 1e-12, `${C.sci(worst)} of each table's largest; ${lenBad} lengths differ`);
        }
    }
    for (const k of ['river', 'river_coarse', 'river_mid', 'river_s', 'river_kappa', 'river_hw']) {
        const want = arrOf(c, k);
        if (!want) { note(k, plan[k] === null, 'none in numpy'); continue; }
        const g = gradeFloats(plan[k], want);
        note(k, g.ok, g.detail + ` (${want.length} values)`);
    }
    note('stats', JSON.stringify(plan.stats) === JSON.stringify(r.stats), JSON.stringify(plan.stats).slice(0, 200));
    T.ok(`seed ${seed}: the plan equal to numpy's (${r.x.shape[0]} towers, the river's ${r.river.shape[0]} vertices) within ` +
        `1e-12, integers exact; ${seconds.toFixed(2)} s`, fails.length === 0, fails.slice(0, 6).join('; ') || 'every field');
}

Deno.exit(KC.finish(T, 'plan_test', { results }));
