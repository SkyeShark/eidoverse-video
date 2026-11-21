// karst evaluate on the GPU against numpy's (PORT_PLAN.md 8.2 row P11: "evaluate within 1e-5 of range"; 5.1 function
// fixtures): solvers/karst.js evaluate (kernels/karst/*) on the windows tests/karst_coast/karst_coast_expected.py ran
// karst.py's evaluate on with Blender's Python: hero cells of 0.5, 1, 2 and 4 m (the flutes, the ledges' field, the
// benches, 2 x 2 subsamples), a film cell, a window across the main tile's edge (the plan's floor map inside, the
// level's own cockpits outside), a fengcong plan (the plinth, no river); and the plans' cockpit floor maps.
//
//     deno run --no-config --no-lock --unstable-webgpu --allow-all eidoverse/terrain/tests/karst_coast/evaluate_test.mjs
//         [--only "hero 2 m,film"] [--dump]               (on a shared machine, behind $EIDO_GPU_WRAP; --dump writes
//                                                            the port's fields to tests/out/karst_coast/evaluate/)
//
// Per field (h, bed, deposit, talus, water, plain, Sc): max |gpu - numpy| against 1e-5 of the field's range (the plan's
// float-function grade), with the share of cells over it and over 1e-4 named: numpy's float64 against float32 meets
// a few discrete decisions of the source (a subsample on the channel's edge, a basin's floor kept or not at a
// threshold) where a last-bit difference flips a cell; each such cell is counted and located. tower_id: the share of
// cells that agree. The floor maps: the basins kept (finite cells) equal, the levels within 1e-5 of the range.
// Beside each window, numpy's own window floor (tests/karst_coast/karst_window_floor.py: karst.py's evaluate again
// from windows shifted by whole cells, the same world cells compared) says how far the source itself moves there: its
// tower loop works in window-local float32 metres on wall tables up to 57 m per metre steep, so its bed, deposit and
// talus move by up to 6e-5 of their ranges (2e-4 for talus) with the window alone.
// JavaScript per cell here is test code. Writes tests/out/karst_coast/evaluate_test.json.

import * as G from '../../core/gpu.js';
import * as IO from '../../core/io.js';
import * as K from '../../solvers/karst.js';
import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';

const args = [...Deno.args];
const at = args.indexOf('--only');
const ONLY = at >= 0 ? args[at + 1].split(',') : null;
const DUMP = args.includes('--dump');                  // also write the port's fields (tests/out/karst_coast/evaluate/)
const T = new C.Checks('karst and coast: karst evaluate against numpy');
const fx = KC.loadFixtures();
const R = await G.init();
const results = { windows: {}, floor_maps: {} };
const plans = {};
const planOf = (a) => (plans[a.plan] ??= K.planKarst(a.seed, a.domain, a.params, a.via, a.main));

/** One field graded: { ok, over (max error / range), range, n1e5, n1e4, at: [i, j], got, want }. */
export function gradeField(got, want, n, k = 1e-5) {
    let lo = Infinity, hi = -Infinity, nonFinite = 0;
    for (let i = 0; i < want.length; i++) {
        const w = want[i];
        if (!Number.isFinite(w)) continue;
        if (w < lo) lo = w;
        if (w > hi) hi = w;
    }
    const range = hi > lo ? hi - lo : Math.max(Math.abs(hi), 1e-6);
    let err = 0, idx = -1, n5 = 0, n4 = 0;
    for (let i = 0; i < want.length; i++) {
        const w = want[i], g = got[i];
        if (!Number.isFinite(w) || !Number.isFinite(g)) { if (w !== g) nonFinite++; continue; }
        const e = Math.abs(g - w);
        if (e > err) { err = e; idx = i; }
        if (e > 1e-5 * range) n5++;
        if (e > 1e-4 * range) n4++;
    }
    return { ok: err <= k * range && nonFinite === 0, over: err / range, range, n1e5: n5, n1e4: n4, nonFinite,
        at: idx >= 0 ? [idx % n, Math.floor(idx / n)] : null, got: idx >= 0 ? got[idx] : null, want: idx >= 0 ? want[idx] : null };
}

// numpy's own window floor (tests/karst_coast/karst_window_floor.py: karst.py's evaluate again from windows shifted by
// whole cells, the same world cells compared), reported beside each window: how far the source itself moves
const FLOOR = fx ? C.readJson(`${fx.dir}/window_floor.json`, {}) : {};
const cases = fx ? KC.findCases(fx, 'karst.evaluate').filter((c) => !ONLY || ONLY.some((t) => c.label.includes(t))) : [];
if (!cases.length) T.ok('karst.evaluate fixtures', false, KC.NO_FIXTURES);
for (const c of cases) {
    const a = c.args;
    const plan = planOf(a);
    const t0 = performance.now();
    let out;
    try {
        out = await K.evaluate(R, plan, a.x0, a.y0, a.cell, a.n);
        await R.idle();
    } catch (e) {
        T.ok(`${c.label}: runs`, false, `${e.name}: ${e.message}`.slice(0, 600));
        continue;
    }
    const seconds = (performance.now() - t0) / 1000;
    const names = ['h', 'bed', 'deposit', 'talus', 'water', 'plain', 'Sc'];
    const got = await R.readAll([...names.map((k) => out[k]), out.tower_id]);
    const row = { seconds: +seconds.toFixed(2), numpy_seconds: a.seconds, fields: {} };
    const fails = [];
    names.forEach((k, i) => {
        const g = gradeField(got[i], C.array(fx.dir, c.outputs[k]), a.n);
        row.fields[k] = g;
        if (!g.ok) fails.push(`${k} ${C.sci(g.over)} of range (${g.n1e5} cells over 1e-5, ${g.n1e4} over 1e-4; at ${g.at})`);
    });
    if (DUMP) {
        const arrays = Object.fromEntries(names.map((k, i) => [k, IO.npArray(got[i], [a.n, a.n])]));
        arrays.tower_id = IO.npArray(got[names.length], [a.n, a.n]);
        Deno.mkdirSync(`${KC.OUT()}/evaluate`, { recursive: true });
        await IO.writeNpz(`${KC.OUT()}/evaluate/${c.label.replace(/[^A-Za-z0-9]+/g, '_').slice(0, 60)}.npz`, arrays);
    }
    const tid = got[names.length], tw = C.array(fx.dir, c.outputs.tower_id);
    let same = 0;
    for (let i = 0; i < tw.length; i++) if (tid[i] === tw[i]) same++;
    row.tower_id_equal = same / tw.length;
    const fl = FLOOR[c.label]?.fields ?? null;
    row.window_floor = fl ? Object.fromEntries(Object.entries(fl).map(([k, v]) => [k, v.over])) : null;
    results.windows[c.label] = row;
    const floorText = fl ? `; numpy's own window floor ${['bed', 'deposit', 'talus'].map((k) => `${k} ${C.sci(fl[k]?.over ?? 0)}`).join(', ')}` : '';
    T.ok(`${c.label}: every field within 1e-5 of its range (tower_id equal on ${(100 * row.tower_id_equal).toFixed(3)} %); ` +
        `${seconds.toFixed(2)} s (numpy ${a.seconds} s)`, fails.length === 0, (fails.join('; ') ||
        `worst ${names.map((k) => `${k} ${C.sci(row.fields[k].over)}`).join(', ')}`) + floorText);
    for (const k of [...names, 'tower_id']) if (out[k] && !out[k].destroyed && k !== 'river') out[k].destroy();
}

for (const c of fx ? KC.findCases(fx, 'karst._floor_map').filter(() => !ONLY || ONLY.includes('floors')) : []) {
    const plan = plans[c.args.plan] ?? planOf({ ...c.args, ...KC.findCases(fx, 'karst.evaluate').find((x) => x.args.plan === c.args.plan).args });
    const fm = await K.floorMap(R, plan);
    const got = await R.read(fm.field), want = C.array(fx.dir, c.outputs.floors);
    let keptBad = 0, kept = 0;
    for (let i = 0; i < want.length; i++) {
        if (Number.isFinite(want[i])) kept++;
        if (Number.isFinite(want[i]) !== Number.isFinite(got[i])) keptBad++;
    }
    const g = gradeField(got, want, fm.n);
    results.floor_maps[c.args.plan] = { kept_cells: kept, kept_differ: keptBad, ...g, geometry_equal: fm.x0 === c.args.x0 && fm.cell === c.args.cell };
    T.ok(`the ${c.args.plan} plan's cockpit floor map (${fm.n}^2 at ${fm.cell} m): the floored cells equal, the levels within ` +
        '1e-5 of the range', keptBad === 0 && g.ok && fm.x0 === c.args.x0 && fm.cell === c.args.cell,
    `${kept} floored cells, ${keptBad} differ; levels ${C.sci(g.over)} of range`);
}

Deno.exit(KC.finish(T, 'evaluate_test', { results }));
