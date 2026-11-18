// The wind-and-sand package's control code against the Blender edition's, in plain JavaScript (no GPU): the
// parameters, the wind schedules (numpy's draws, core/np_random.js), the hop boxes and every uniform the slab model's
// kernels are given (PORT_PLAN.md 5.3 "plans", 5.7; 8.2 P8: "the wind schedules equal (numpy draws)").
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/wind_sand/plans_test.mjs
//
// (from the repository root). Fixtures (made by the Blender edition's own Python, plan C6):
//   tests/out/wind_sand/fixtures/        tests/wind_sand/aeolian_expected.py: resolve_params for every kind and the
//                                        recipe's stage, refine_settings, refine_winds, growth_index on real plans,
//                                        cycle_blocks, schedule, hop_box, uniforms_for, check_grid, normalise_winds
//   tests/out/parity/<key>/fixtures/plans/   tests/parity/fixtures.py --plans: every aeolian.schedule call the floor's
//                                        dunes runs made, again for seeds 1-8
//   the floor's dunes base runs          their stages.json (the recipe's to_dict) and their dispatch logs: every
//                                        dune_shadow, dune_activate and dune_avalanche dispatch of the growth run
//                                        (26,991 iterations, 458,847 dispatches a run) rebuilt here from the port's
//                                        resolveParams, growthIndex, schedule and uniformsFor and compared uniform by
//                                        uniform (dune_transport's box needs the steering's turn, a GPU number: the
//                                        stage replay compares it)
// Grades (plan 5.3): integers, strings and structure exact; plan floats within 1e-12 relative (both float64; V8's
// Math against the C library: a last-ulp difference at most). JavaScript per dispatch here is test code.

import * as A from '../../solvers/aeolian.js';
import { DUNES } from '../../recipes/dunes.js';
import { Level } from '../../core/levels.js';
import * as C from '../parity/_common.mjs';
import * as S from './_common.mjs';

const T = new S.Checks('wind and sand: parameters, schedules, hop boxes and uniforms against the Blender edition');

// ---- deep comparison: numbers within 1e-12 relative (exact for integers), everything else equal
function close(a, b, path = '', out = []) {
    if (out.length > 8) return out;
    if (typeof a === 'number' && typeof b === 'number') {
        if (Number.isInteger(a) && Number.isInteger(b) ? a !== b : !(Math.abs(a - b) <= 1e-12 * Math.max(Math.abs(a), Math.abs(b), 1e-300))) {
            out.push(`${path}: ${a} vs ${b}`);
        }
        return out;
    }
    if (b && typeof b === 'object' && b.nan === true) {
        if (!Number.isNaN(a)) out.push(`${path}: ${a} vs NaN`);
        return out;
    }
    if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length) out.push(`${path}: length ${a.length} vs ${b.length}`);
        for (let i = 0; i < Math.min(a.length, b.length); i++) close(a[i], b[i], `${path}[${i}]`, out);
        return out;
    }
    if (a && b && typeof a === 'object' && typeof b === 'object') {
        const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
        if (JSON.stringify(ka) !== JSON.stringify(kb)) out.push(`${path}: keys ${JSON.stringify(ka.filter((k) => !kb.includes(k)))} only here, ${JSON.stringify(kb.filter((k) => !ka.includes(k)))} only in Blender`);
        for (const k of ka) if (k in b) close(a[k], b[k], path ? `${path}.${k}` : k, out);
        return out;
    }
    if (a !== b && !(a === undefined && b === null) && !(a === null && b === undefined)) out.push(`${path}: ${JSON.stringify(a)} vs ${JSON.stringify(b)}`);
    return out;
}

const level = (d) => Level.fromDict(d);

// ---- 1. the aeolian fixture's plan cases
const FX = `${S.OUT}/fixtures`;
const man = C.readJson(`${FX}/manifest.json`);
if (!man) {
    S.W.skip('the aeolian plan cases', "make them with <Blender's python> -I eidoverse/terrain/tests/wind_sand/aeolian_expected.py");
} else {
    const by = {};
    for (const c of man.plans) (by[c.function] ??= []).push(c);
    const run = (name, fn) => {
        const cases = by[name] ?? [];
        const bad = [];
        for (const c of cases) {
            let got;
            try {
                got = fn(c);
            } catch (e) {
                got = { __error: `${e.name}: ${e.message}` };
            }
            const d = close(got, c.result ?? null, '');
            if (d.length) bad.push(`${c.label}: ${d.slice(0, 3).join('; ')}`);
        }
        T.ok(`${name}: ${cases.length} cases equal to the Blender edition's`, cases.length > 0 && !bad.length, bad.slice(0, 4).join(' | '));
    };
    run('resolve_params', (c) => A.resolveParams(c.params));
    {
        const cases = by.resolve_params_error ?? [];
        const bad = cases.filter((c) => {
            try {
                A.resolveParams(c.params);
                return true;
            } catch (e) {
                return e.message !== c.error;
            }
        });
        T.ok(`resolve_params: an unknown kind raises Blender's message (${cases.length} cases)`, cases.length > 0 && !bad.length,
            bad.map((c) => c.label).join(', ') || cases[0]?.error);
    }
    run('refine_settings', (c) => A.refineSettings(c.params, level(c.level)));
    run('refine_winds', (c) => A.refineWinds(c.params, c.mode));
    {
        const cases = by.growth_index ?? [];
        const bad = [];
        for (const c of cases) {
            const warns = [];
            const g = A.growthIndex(c.plan.map(level), c.spacing_m, c.cells_per_spacing, (m) => warns.push(m));
            if (g !== c.result || JSON.stringify(warns) !== JSON.stringify(c.warnings)) bad.push(`${c.label}: ${g} ${JSON.stringify(warns)} vs ${c.result} ${JSON.stringify(c.warnings)}`);
        }
        T.ok(`growth_index: ${cases.length} plans (four kinds, draft, film and hero quality), the same level and warnings`, cases.length > 0 && !bad.length,
            bad.slice(0, 3).join(' | '));
    }
    run('cycle_blocks', (c) => A.cycleBlocks(c.winds, c.block));
    run('schedule', (c) => A.schedule(...c.args));
    run('hop_box', (c) => A.hopBox(c.hop, c.long_f, c.turn));
    run('uniforms_for', (c) => A.uniformsFor(c.params, c.cell, c.from_deg, c.it, c.seed, c.bound, c.turn));
    {
        const cases = by.check_grid ?? [];
        const bad = [];
        for (const c of cases) {
            let err = null;
            try {
                A.checkGrid(c.shape, c.params, c.bound);
            } catch (e) {
                err = e.message;
            }
            if (err !== c.error) bad.push(`${c.label}: ${err} vs ${c.error}`);
        }
        T.ok(`check_grid: ${cases.length} grids, the same errors word for word`, cases.length > 0 && !bad.length, bad.join(' | '));
    }
    {
        const cases = by.normalise_winds ?? [];
        const bad = [];
        for (const c of cases) {
            let got = null, err = null;
            try {
                got = A.normaliseWinds(c.winds);
            } catch (e) {
                err = e.message;
            }
            if (err !== c.error || close(got, c.result).length) bad.push(`${c.label}: ${JSON.stringify(got)} ${err} vs ${JSON.stringify(c.result)} ${c.error}`);
        }
        T.ok(`normalise_winds: ${cases.length} forms (pairs, objects, bare angles, zero and negative weights)`, cases.length > 0 && !bad.length, bad.join(' | '));
    }
    T.extra.fixture_versions = man.versions;
}

// ---- 2. the floor's plan fixtures: every aeolian.schedule call of the dunes runs, for seeds 1-8
const pf = C.loadFixture('plans');
if (pf) {
    const cases = pf.manifest.cases.filter((c) => c.function === 'solvers.aeolian.schedule');
    const bad = [];
    const names = ['winds', 'iterations', 'block', 'jitter_deg', 'seed', 'gust', 'spread_deg', 'with_wind'];
    for (const c of cases) {
        const args = [...c.call.args];
        for (const [k, v] of Object.entries(c.call.kwargs ?? {})) args[names.indexOf(k)] = v;
        const d = close(A.schedule(...args), c.result);
        if (d.length) bad.push(`${c.label}: ${d.slice(0, 2).join('; ')}`);
    }
    T.ok(`schedule: the ${cases.length} calls the floor's dunes runs made (seeds 1-8 and as run) equal draw for draw`, cases.length > 0 && !bad.length,
        bad.slice(0, 3).join(' | ') || `${cases.reduce((s, c) => s + (c.result?.length ?? 0), 0)} gusts and blocks`);
}

// ---- 3. the recipe and 4. the growth run's uniforms, against the floor's dunes runs
const runs = [1, 2].map((s) => S.W.floorRun('dunes', s, 'base')).filter(Boolean);
if (!runs.length) S.W.skip('the dunes recipe and the growth run\'s uniforms', 'tests/parity/floor_runs.sh --recipes dunes makes the floor runs');

async function* gzLines(path) {
    const file = await Deno.open(path, { read: true });
    const reader = file.readable.pipeThrough(new DecompressionStream('gzip')).pipeThrough(new TextDecoderStream()).getReader();
    let rest = '';
    for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        rest += value;
        let i;
        while ((i = rest.indexOf('\n')) >= 0) {
            const line = rest.slice(0, i);
            rest = rest.slice(i + 1);
            if (line) yield line;
        }
    }
    if (rest) yield rest;
}

for (const dir of runs) {
    const hdr = C.readJson(`${dir}/stages/stages.json`);
    const seed = hdr.seed;
    T.ok(`dunes seed ${seed}: the recipe's toDict() equals the run's to_dict()`, !close(DUNES.toDict(), hdr.recipe).length,
        close(DUNES.toDict(), hdr.recipe).slice(0, 3).join('; '));
    const [values, stages] = DUNES.resolve(null);
    const st0 = hdr.stages[0];
    T.ok(`dunes seed ${seed}: the knob values and the stage's parameters equal the run's`,
        !close(values, hdr.values).length && !close(stages[0].params, st0.params).length,
        JSON.stringify(stages[0].params));
    // the growth run as grow_tile makes it: the plan, the growth level, the sim's seed, the schedule, the uniforms
    const plan = hdr.plan.map(level);
    const p = A.resolveParams(st0.params);
    const g = A.growthIndex(plan, p.spacing_m, Number(p.cells_per_spacing), null);
    p.growth_period_m = plan[g].side;
    const lv = plan[g];
    const P = A.paramsFor(p);
    const simSeed = seed * 131 + 7;
    const sched = A.schedule(p.winds, p.grow_iters, Number(P.block), Number(P.jitter_deg), simSeed, Number(P.gust), Number(P.spread_deg), true);
    const passes = Number(P.aval_passes);
    // expected dispatches, generated lazily: [kernel, uniforms or null (transport)]
    function* expected() {
        let it = 0;
        for (const [d, b] of sched) {
            const u = A.uniformsFor(P, lv.cell, d, it, simSeed, A.BOUND_PERIODIC, [0.0, 0.0]);
            for (let i = 0; i < b; i++) {
                yield ['dune_shadow', u.dune_shadow];
                yield ['dune_activate', { ...u.dune_activate, uIter: it }];
                yield ['dune_transport', null];
                for (let k = 0; k < passes; k++) yield ['dune_avalanche', u.dune_avalanche];
                it++;
            }
        }
    }
    const gen = expected();
    let n = 0, compared = 0, firstBad = null, extra = 0, short = 0;
    const counts = {};
    for await (const line of gzLines(`${dir}/dispatch_log.jsonl.gz`)) {
        if (!line.includes('"dune_')) continue;
        const d = JSON.parse(line);
        if (d[0] !== 'dune_field' || !String(d[1]).startsWith('dune_')) continue;
        counts[d[1]] = (counts[d[1]] ?? 0) + 1;
        const e = gen.next();
        if (e.done) { extra++; continue; }
        const [kernel, u] = e.value;
        n++;
        if (kernel !== d[1]) {
            firstBad ??= `dispatch ${n}: ${d[1]} in Blender, ${kernel} here`;
            continue;
        }
        if (!u) continue;
        const theirs = Object.fromEntries(d[2]);
        const diff = close(u, theirs);
        compared++;
        if (diff.length && !firstBad) firstBad = `dispatch ${n} (${kernel}): ${diff.slice(0, 2).join('; ')}`;
    }
    for (let e = gen.next(); !e.done; e = gen.next()) short++;
    const iters = sched.reduce((s, x) => s + x[1], 0);
    T.ok(`dunes seed ${seed}: the growth run's schedule and uniforms rebuilt from the port's parameters equal Blender's dispatch log ` +
        `(${iters} iterations from seed ${simSeed}; dune_shadow, dune_activate and dune_avalanche, every uniform)`,
        !firstBad && !extra && !short && compared > 0, firstBad ??
        `${n} dispatches in order (${JSON.stringify(counts)}), ${compared} with their uniforms compared; growth level ${g} (${lv})`);
}

Deno.exit(S.finish(T, 'plans_test'));
