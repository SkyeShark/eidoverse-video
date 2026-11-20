// The layered-rock package's plans (PORT_PLAN.md 8.2 row P10: "column tables equal; river courses equal (plan
// fixtures)"; 5.3's plan grade: 1e-12 relative, numpy's draws bit for bit): everything solvers/strata.js and
// solvers/rivers.js compute in JavaScript doubles from numpy's Generator, against the Blender edition's own results.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/layered_rock/plans_test.mjs     (no GPU)
//
//   1. the plan fixtures (tests/parity/fixtures.py --plans: every call the floor's base runs made, again for seeds
//      1-8, by Blender's Python): Column.__init__ (the four recipes' columns: layers, beds, the K, tan, creep, R and
//      formation tables), rivers._smooth_noise_1d (the walk's noise), rivers.kinoshita (the meander trains),
//      River.crests (the pools), strata.core_centres (the dart-thrown cores), strata._box_noise (their outlines)
//   2. the whole river courses of the floor runs (canyon, incised_meanders and mesas_buttes, seeds 1-2): makeRiver()
//      from the river_path stage's own parameters against the River the run kept (its points, arc lengths, the point
//      through which it was placed, its crests), and top(s) sampled from the run's own starting surface
//   3. course geometry (blender/tests/terrain/layered_rock/test_strata.py test_meanders, ported): Kinoshita courses
//      at sinuosity 1.5, 2.5 and 3.5 measure it within 2 %, their bend wavelength within 6 % of wavelength /
//      sinuosity, necks wider than four channel widths with the variation; the walk has no loops
// Writes tests/out/layered_rock/plans_test.json.

import * as RP from '../parity/replay.mjs';
import * as RV from '../../solvers/rivers.js';
import * as S from '../../solvers/strata.js';
import { C, RECIPES, W, compareNumbers, finish, floorRun, pairs } from './_layered.mjs';

const T = new C.Checks('layered_rock: plans');
const fx = C.loadFixture('plans');
const summary = {};

function argOf(c, v) {
    if (v && typeof v === 'object' && !Array.isArray(v) && v.__array__) {
        const a = c.inputs[v.__array__];
        return { data: C.array(fx.dir, a), shape: a.shape };
    }
    return v;
}
// a result array: from its file, or inline in the manifest (small arrays are stored as JSON lists there)
const resultArray = (c, key = 'result') => (c.outputs?.[key] ? C.array(fx.dir, c.outputs[key])
    : (key === 'result' && Array.isArray(c.result) ? c.result : null));

function tally(name, rows) {
    const n = rows.length, ok = rows.filter((r) => r.ok).length;
    const bit = rows.filter((r) => r.bit).length;
    const worst = Math.max(0, ...rows.map((r) => r.worst ?? 0));
    summary[name] = { cases: n, ok, bit_identical: bit, worst_relative: worst, failed: rows.filter((r) => !r.ok).map((r) => r.label).slice(0, 8) };
    return { n, ok, bit, worst };
}

if (fx) {
    const mine = fx.manifest.cases.filter((c) => RECIPES.includes(c.recipe));
    // ------------------------------------------------------------------------------------ the columns
    {
        const rows = [];
        for (const c of mine.filter((x) => x.function === 'solvers.strata.Column.__init__')) {
            const [layers, name, dz, seed] = c.call.args;
            const col = new S.Column(layers, name, dz, seed);
            const r = c.result;
            const parts = [];
            parts.push(col.name === r.name && col.dz === r.dz && col.top_m === r.top_m && col.z0 === r.z0);
            parts.push(JSON.stringify(col.layers.map((d) => d.name)) === JSON.stringify(r.layers.map((d) => d.name)));
            const lay = compareNumbers(col.layers.map((d) => [d.thickness_m, d.K_factor, d.Sc_deg, d.creep, d.base_m, d.top_m]),
                r.layers.map((d) => [d.thickness_m, d.K_factor, d.Sc_deg, d.creep, d.base_m, d.top_m]));
            const fine = compareNumbers(col.fine, r.fine);
            const tabs = ['zs', 'K', 'tan', 'creep', 'R'].map((k) => compareNumbers(col[k], resultArray(c, `result.${k}`)));
            const form = compareNumbers(col.formation, resultArray(c, 'result.formation'), 0);
            const all = [lay, fine, ...tabs, form];
            const ok = parts.every(Boolean) && all.every((x) => x.ok);
            rows.push({ label: c.label, ok, bit: all.every((x) => x.bitEqual === x.n) && parts.every(Boolean),
                worst: Math.max(...all.map((x) => x.worst)) });
        }
        const t = tally('column', rows);
        T.ok(`columns: ${t.ok} of ${t.n} Column constructions (layers, beds, the K, tan, creep, R and formation tables) within ` +
            `1e-12 of Blender's`, t.n > 0 && t.ok === t.n, `${t.bit} bit for bit; worst ${C.sci(t.worst)} relative`);
    }
    // ------------------------------------------------------------------------------------ the walk's noise
    {
        const rows = [];
        for (const c of mine.filter((x) => x.function === 'solvers.rivers._smooth_noise_1d')) {
            const [sArg, wl, seed, oct] = c.call.args.map((v) => argOf(c, v));
            const octaves = c.call.kwargs?.octaves ?? oct ?? 3;
            const got = RV._smoothNoise1d(sArg.data, wl, seed, octaves);
            const r = compareNumbers(got, resultArray(c));
            rows.push({ label: c.label, ok: r.ok, bit: r.bitEqual === r.n, worst: r.worst });
        }
        const t = tally('smooth_noise_1d', rows);
        T.ok(`river noise: ${t.ok} of ${t.n} _smooth_noise_1d calls within 1e-12`, t.n > 0 && t.ok === t.n, `${t.bit} bit for bit; worst ${C.sci(t.worst)}`);
    }
    // ------------------------------------------------------------------------------------ the meander trains
    {
        const rows = [];
        for (const c of mine.filter((x) => x.function === 'solvers.rivers.kinoshita')) {
            const a = c.call.args.map((v) => argOf(c, v));
            const kw = c.call.kwargs ?? {};
            const names = ['through', 'flow_azimuth_deg', 'length_m', 'wavelength_m', 'sinuosity', 'theta0_deg', 'skew', 'flat',
                'vary', 'seed', 'step_m', 'vary_scale', 'vary_skew', 'min_neck_m', 'centre'];
            const dflt = [null, null, null, 1200.0, 2.5, null, 0.03, 0.0, 0.15, 0, null, 3.0, 0.0, 0.0, 'course'];
            const v = names.map((nm, i) => (i < a.length ? a[i] : (nm in kw ? kw[nm] : dflt[i])));
            const got = RV.kinoshita(...v);
            const r = compareNumbers(got, resultArray(c));
            rows.push({ label: c.label, ok: r.ok, bit: r.bitEqual === r.n, worst: r.worst });
        }
        const t = tally('kinoshita', rows);
        T.ok(`meander trains: ${t.ok} of ${t.n} kinoshita courses within 1e-12 (of the course's extent)`, t.n > 0 && t.ok === t.n,
            `${t.bit} bit for bit; worst ${C.sci(t.worst)}`);
    }
    // ------------------------------------------------------------------------------------ the pools
    {
        const rows = [];
        for (const c of mine.filter((x) => x.function === 'solvers.rivers.River.crests')) {
            const d = c.call.args[0];
            const fc = argOf(c, d.final_course[0]);
            const rv = Object.create(RV.River.prototype);
            Object.assign(rv, { pool: d.pool.map(Number), pool_seed: Math.trunc(d.pool_seed), _crest_cache: null,
                final_course: [pairs(fc.data), Number(d.final_course[1])] });
            const got = rv.crests();
            const want = resultArray(c);
            const r = want ? compareNumbers(got, want) : { ok: got === null, bitEqual: 0, n: 0, worst: 0 };
            rows.push({ label: c.label, ok: r.ok, bit: r.bitEqual === r.n, worst: r.worst });
        }
        const t = tally('crests', rows);
        T.ok(`pools: ${t.ok} of ${t.n} River.crests within 1e-12`, t.n > 0 && t.ok === t.n, `${t.bit} bit for bit; worst ${C.sci(t.worst)}`);
    }
    // ------------------------------------------------------------------------------------ the cores
    {
        const rows = [];
        for (const c of mine.filter((x) => x.function === 'solvers.strata.core_centres')) {
            const [spec, seed] = c.call.args;
            const got = S.coreCentres(spec, seed);
            const r = compareNumbers(got, c.result);
            rows.push({ label: c.label, ok: r.ok && got.length === c.result.length, bit: r.bitEqual === r.n, worst: r.worst });
        }
        const t = tally('core_centres', rows);
        T.ok(`cores: ${t.ok} of ${t.n} core_centres plans (dart throwing, shapes, angles) within 1e-12`, t.n > 0 && t.ok === t.n,
            `${t.bit} bit for bit; worst ${C.sci(t.worst)}`);
        const rows2 = [];
        for (const c of mine.filter((x) => x.function === 'solvers.strata._box_noise')) {
            const [x, y, wl, seed] = c.call.args.map((v) => argOf(c, v));
            const got = S.boxNoise(x.data, y.data, wl, seed);
            const r = compareNumbers(got, resultArray(c));
            rows2.push({ label: c.label, ok: r.ok, bit: r.bitEqual === r.n, worst: r.worst });
        }
        const t2 = tally('box_noise', rows2);
        T.ok(`core outlines: ${t2.ok} of ${t2.n} _box_noise evaluations within 1e-12 (sines of arguments up to hundreds of radians)`,
            t2.n > 0 && t2.ok === t2.n, `${t2.bit} bit for bit; worst ${C.sci(t2.worst)}`);
    }
}

// ---------------------------------------------------------------------------------- the floor runs' courses
{
    const rows = [];
    for (const recipe of ['canyon', 'incised_meanders', 'mesas_buttes']) {
        for (const seed of [1, 2]) {
            const dir = floorRun(recipe, seed);
            if (!dir) continue;
            const run = await RP.loadRun(dir);
            const st = run.stages.find((s) => s.op === 'river_path');
            const nxt = run.stages.find((s) => s.call === st.call + 1);
            const before = await RP.npz(`${dir}/stages/${nxt.before}`);
            const d = nxt.context.shared.river;
            const want = (ref) => before[`shared__${ref.__array__}`];
            const rv = RV.makeRiver(structuredClone(st.params), st.seed, run.levels[0].side);
            const pts = compareNumbers(rv.points, want(d.points).data);
            const s = compareNumbers(rv.s, want(d.s).data);
            const s0 = Math.abs(rv.s_through - d.s_through) / Math.max(Math.abs(d.s_through), 1);
            const cr = d._crest_cache ? compareNumbers(rv.crests(), want(d._crest_cache).data) : { ok: rv.crests() === null, bitEqual: 0, n: 0, worst: 0 };
            const tf = want(d.top_field[0]);
            await rv.sampleTop({ n: tf.shape[0], x0: d.top_field[1], y0: d.top_field[2], cell: d.top_field[3] }, Float32Array.from(tf.data));
            const top = compareNumbers(rv.top, want(d.top).data);
            const ok = pts.ok && s.ok && s0 <= 1e-12 && cr.ok && top.ok;
            rows.push({ label: `${recipe} s${seed}`, ok, bit: pts.bitEqual === pts.n, worst: Math.max(pts.worst, s.worst, s0, cr.worst, top.worst),
                points: rv.points.length, kind: st.params.kind });
        }
    }
    const t = tally('floor_courses', rows);
    T.ok(`river courses: ${t.ok} of ${t.n} floor runs' courses (points, arc lengths, the placing point, crests, top(s)) within 1e-12`,
        t.n > 0 && t.ok === t.n, `${t.bit} with every point bit for bit; worst ${C.sci(t.worst)}; ${rows.map((r) => `${r.label} ${r.kind} ${r.points} points`).join(', ')}`);
}

// --------------------------------------------------------------------------- course geometry (test_meanders)
{
    // blender/tests/terrain/layered_rock/test_strata.py test_meanders, its cases and criteria as they are
    const rows = [];
    let ok = true;
    for (const sig of [1.5, 2.5, 3.5]) {
        const lam = 1200.0;
        const pts = RV.kinoshita([0.0, 0.0], 90.0, 40000.0, lam, sig, null, 0.03, 0.0, 0.0, 1);
        const m = RV.metrics(pts, lam);
        const want = lam / sig;
        const good = Math.abs(m.sinuosity / sig - 1.0) <= 0.02 && Math.abs(m.wavelength_m / want - 1.0) <= 0.06 && m.neck_m > 4 * 40.0;
        ok = ok && good;
        rows.push(`sinuosity ${sig}: ${m.sinuosity.toFixed(4)}, bends ${m.wavelength_m.toFixed(1)} m apart (want ${want.toFixed(1)}), neck ${m.neck_m.toFixed(1)} m`);
    }
    for (const seed of [1, 2, 3]) {
        const pts = RV.kinoshita([500.0, -300.0], 250.0, 30000.0, 1100.0, 3.0, null, 0.03, 0.0, 0.15, seed);
        const m = RV.metrics(pts, 1100.0);
        const d0 = Math.min(...pts.map(([x, y]) => Math.hypot(x - 500.0, y + 300.0)));
        const cx = pts[pts.length - 1][0] - pts[0][0], cy = pts[pts.length - 1][1] - pts[0][1];
        const az = (((Math.atan2(cx, cy) * 180.0) / Math.PI) % 360.0 + 360.0) % 360.0;
        const good = m.neck_m > 4 * 40.0 && d0 < 2.0 && Math.abs(((az - 250.0 + 180) % 360 + 360) % 360 - 180) < 2.0 &&
            m.sinuosity > 2.6 && m.sinuosity < 3.4;
        ok = ok && good;
        rows.push(`seed ${seed} varied: sinuosity ${m.sinuosity.toFixed(3)}, neck ${m.neck_m.toFixed(1)} m, through ${d0.toFixed(3)} m, azimuth ${az.toFixed(2)}`);
    }
    const w = RV.walk([0.0, 0.0], 45.0, 30000.0, 12.0, 3000.0, 4);
    const mw = RV.metrics(w);
    const goodW = mw.sinuosity > 1.0 && mw.sinuosity < 1.15 && mw.neck_m > 1000.0;
    ok = ok && goodW;
    rows.push(`walk: sinuosity ${mw.sinuosity.toFixed(4)}, neck ${mw.neck_m.toFixed(1)} m`);
    // a growing train (growth 0.55): the stages' sinuosity rises to the final course's, which is the fixed course itself,
    // and every bend keeps its down-valley place (the crossings of the valley axis move little)
    const p = { kind: 'kinoshita', through: [0.0, 0.0], flow_azimuth_deg: 90.0, wavelength_m: 7000.0, sinuosity: 3.8, vary: 0.3,
        flat: 0.02, growth: 0.55, growth_stages: 6, length_m: 20000.0 };
    const rv = RV.makeRiver(p, 1, 12000.0);
    const [fixed] = RV.course({ ...p, growth: 1.0 }, 1, 12000.0);
    const sins = [...rv.stages.map(([, pts]) => RV.metrics(pts).sinuosity), RV.metrics(rv.final_course[0]).sinuosity];
    const crossings = (pts) => {
        const out = [];
        for (let i = 0; i + 1 < pts.length; i++) if (Math.sign(pts[i + 1][1]) !== Math.sign(pts[i][1])) out.push(pts[i][0]);
        return out;
    };
    const c0 = crossings(rv.stages[0][1]), c1 = crossings(rv.final_course[0]);
    const inner = c1.filter((x) => Math.abs(x) < 6000.0);
    const shifts = inner.map((x) => Math.min(...c0.map((y) => Math.abs(y - x)))).sort((a, b) => a - b);
    const shift = shifts.length && c0.length ? (shifts.length % 2 ? shifts[(shifts.length - 1) / 2]
        : 0.5 * (shifts[shifts.length / 2 - 1] + shifts[shifts.length / 2])) : Infinity;
    const same = fixed.length === rv.final_course[0].length && fixed.every((q, i) => q[0] === rv.final_course[0][i][0] && q[1] === rv.final_course[0][i][1]);
    const goodG = sins.every((v, i) => i === 0 || v > sins[i - 1]) && same && shift < 0.15 * (7000.0 / 3.8);
    ok = ok && goodG;
    rows.push(`growth 0.55: stage sinuosity ${sins.map((v) => v.toFixed(2)).join(' < ')}, final course the fixed one ${same}, ` +
        `crossings moved ${shift.toFixed(1)} m (limit ${(0.15 * 7000 / 3.8).toFixed(1)})`);
    T.ok('meander curve geometry (test_strata.py test_meanders: Kinoshita sinuosity within 2 %, bend wavelength within 6 %, ' +
        'necks over 4 channel widths, placement and azimuth, the walk, a growing train)', ok, rows.join('; '));
}

Deno.exit(finish(T, 'plans_test', { summary, key: W.parityKeyDir() }));
