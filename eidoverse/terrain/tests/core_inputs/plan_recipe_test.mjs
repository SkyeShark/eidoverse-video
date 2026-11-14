// core/levels.js, core/recipe.js and core/expr.js's parser against the Blender edition's own (PORT_PLAN.md 8.2, P2):
// plan_levels JSON-equal on test_core.py's 20 focus cases as written and at every quality, and on focus points whose
// window snaps fall exactly half way between two grid lines (C10: Python's round() sends them to the even line);
// select_levels in every form; Python's round(), format(), repr() and difflib.get_close_matches; every registered
// recipe's to_dict() round trip, describe() and resolve() (with its defaults and two other knob sets, without the
// recipes' apply code, which their packages port); test_core.py's test recipe with its apply; the expression
// parser's trees, text, names, number values and errors. No GPU.
//
//     <Blender's python> -I eidoverse/terrain/tests/core_inputs/core_inputs_expected.py
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/core_inputs/plan_recipe_test.mjs [fixtures]

import * as L from '../../core/levels.js';
import { Knob, Params, Recipe, Stage, getOp, opNames, registerOp } from '../../core/recipe.js';
import * as E from '../../core/expr.js';
import { Checks, errText, finish, fixtures, intFloats, jsonDiff, manifest, pyErrText, sameJson } from './_common.mjs';

const T = new Checks('core_inputs/plan_recipe');
const FIX = fixtures();
if (!FIX) Deno.exit(0);
const M = manifest(FIX);
Object.assign(T.extra, { numpy: M.numpy, python: M.python, blender_commit: M.blender_commit });

const tryRun = (fn) => {
    try {
        return { value: fn() };
    } catch (e) {
        return { error: errText(e) };
    }
};


// ------------------------------------------------------------------------------------------------- levels ---

function runCase(c) {
    const warnings = [];
    let focus = c.focus;
    if (c.cameras) focus = c.focus.map((p) => ({ location: p }));
    const opts = { centre: c.centre, context: c.context, focus, hero: c.hero, warn: (m) => warnings.push(m) };
    if (c.band !== undefined) opts.band = c.band;
    if (c.max_cells !== undefined) opts.maxCells = c.max_cells;
    const r = tryRun(() => L.planLevels(c.size, c.resolution, opts));
    if (r.error) return { error: r.error };
    const plan = r.value;
    return { plan: plan.map((lv) => lv.toDict()), repr: plan.map(String), warnings, in_parent: plan.map((lv) => lv.inParent(plan)),
        with_cells: (plan[0].prepass.length ? plan[0].prepass : [64]).map((m) => plan[0].withCells(m).toDict()) };
}

function checkCases(group, cases) {
    let same = 0, half = 0, halfCases = 0;
    const bad = [];
    for (const c of cases) {
        const got = runCase(c);
        if (c.error || got.error) {
            const ok = intFloats(pyErrText(c.error)) === intFloats(got.error);
            if (ok) same++;
            else bad.push(`${c.label}: ${got.error ?? 'no error'} vs ${c.error ?? 'no error'}`);
            continue;
        }
        const diffs = ['plan', 'repr', 'warnings', 'in_parent', 'with_cells'].map((k) => [k, jsonDiff(got[k], c[k])]).filter(([, d]) => d);
        if (!diffs.length) same++;
        else bad.push(`${c.label}: ${diffs.map(([k, d]) => `${k} ${d}`).join('; ')}`);
        half += c.half_snaps ?? 0;
        if (c.half_snaps) halfCases++;
    }
    T.ok(`plan_levels ${group}: ${same} of ${cases.length} JSON-equal (plan, repr, warnings, in_parent, with_cells)`,
        same === cases.length, bad.slice(0, 3).join(' | ') + (halfCases ? ` (${halfCases} cases with ${half} half-way snaps)` : ''));
}

checkCases('test_core.py focus cases', M.levels.cases);
checkCases('the same at draft, film and hero quality', M.levels.quality_cases);
checkCases('half-way snaps (C10)', M.levels.half_cases);
checkCases('errors and options', M.levels.errors);
{
    const plan = M.levels.select_plan.map((d) => L.Level.fromDict(d));
    let same = 0;
    const bad = [];
    for (const s of M.levels.select) {
        const warnings = [];
        const r = tryRun(() => L.selectLevels(s.spec, plan, (m) => warnings.push(m)));
        const ok = s.error ? pyErrText(s.error) === r.error : (sameJson(r.value, s.picked) && sameJson(warnings, s.warnings));
        if (ok) same++;
        else bad.push(`${JSON.stringify(s.spec)}: ${r.error ?? JSON.stringify(r.value)} ${JSON.stringify(warnings)} vs ${s.error ?? JSON.stringify(s.picked)}`);
    }
    T.ok(`select_levels: ${same} of ${M.levels.select.length} forms equal (picks, warnings, errors)`, same === M.levels.select.length, bad.slice(0, 3).join(' | '));
}


// ------------------------------------------------------------------------------------- Python's behaviours ---

{
    const P = M.python;
    let bad = P.round.filter(([v, r]) => L.pyRound(v) !== r);
    T.ok(`pyRound: ${P.round.length - bad.length} of ${P.round.length} equal to Python's round() (halves to even)`, !bad.length,
        bad.map(([v, r]) => `${v}: ${L.pyRound(v)} vs ${r}`).join(', '));
    T.ok('Math.round differs from round() on the half-way values (the reason for pyRound)',
        P.round.some(([v, r]) => Math.round(v) !== r), P.round.filter(([v, r]) => Math.round(v) !== r).map(([v]) => v).join(', '));
    bad = P.format.filter(([v, s, t]) => L.pyFormat(v, s) !== t);
    T.ok(`pyFormat: ${P.format.length - bad.length} of ${P.format.length} equal to Python's format()`, !bad.length,
        bad.slice(0, 5).map(([v, s, t]) => `${v} '${s}': ${L.pyFormat(v, s)} vs ${t}`).join(', '));
    bad = P.repr.filter(([v, t]) => L.pyRepr(v) !== t);
    T.ok(`pyRepr: ${P.repr.length - bad.length} of ${P.repr.length} equal to Python's repr()`, !bad.length,
        bad.map(([v, t]) => `${v}: ${L.pyRepr(v)} vs ${t}`).join(', '));
    bad = P.close.filter(([w, p, n, c, want]) => !sameJson(L.closeMatches(w, p, n, c), want));
    T.ok(`closeMatches: ${P.close.length - bad.length} of ${P.close.length} equal to difflib.get_close_matches`, !bad.length,
        bad.map(([w, p, n, c, want]) => `${w.slice(0, 20)}: ${JSON.stringify(L.closeMatches(w, p, n, c))} vs ${JSON.stringify(want)}`).join(', '));
}


// ------------------------------------------------------------------------------------------------- recipes ---

{
    const RS = M.recipes.recipes;
    let rt = 0, desc = 0, descExact = 0, res = 0, reprs = 0, total = 0, nres = 0;
    const bad = [];
    for (const [name, r] of Object.entries(RS)) {
        total++;
        // the registered recipe's apply functions are its package's port; a base whose deriving knobs carry a
        // stand-in apply (writing nothing) stands for it, so `derives` and describe() come out as Blender's
        const kd = r.to_dict.knobs;
        const base = new Recipe(name, r.to_dict.title, [], {}, Object.fromEntries(Object.entries(kd).map(([k, v]) =>
            [k, new Knob(v.default, v.unit, v.range, v.doc, v.derives ? () => {} : null)])), []);
        const rec = Recipe.fromDict(structuredClone(r.to_dict), base);
        const d = jsonDiff(rec.toDict(), r.to_dict);
        if (!d) rt++;
        else bad.push(`${name} to_dict ${d}`);
        // describe() of the recipe its dict makes (Python's tuples are lists there, as in JavaScript)
        const txt = rec.describe();
        if (txt === r.describe_dict) descExact++;
        if (intFloats(txt) === intFloats(r.describe_dict)) desc++;
        else {
            const a = intFloats(txt).split('\n'), b = intFloats(r.describe_dict).split('\n');
            const i = a.findIndex((l, k) => l !== b[k]);
            bad.push(`${name} describe line ${i}: ${a[i]?.slice(0, 160)} | ${b[i]?.slice(0, 160)}`);
        }
        if (intFloats(String(rec)) === intFloats(r.repr) && rec.stages.every((s, i) => intFloats(String(s)) === intFloats(r.stage_reprs[i]) && s.label === r.labels[i])) reprs++;
        else bad.push(`${name} repr ${String(rec)} | ${r.repr}`);
        for (const want of r.resolve_nobase) {
            nres++;
            const got = tryRun(() => rec.resolve(want.params));
            if (want.error || got.error) {
                if (pyErrText(want.error) === got.error) res++;
                else bad.push(`${name} resolve ${got.error} vs ${want.error}`);
                continue;
            }
            const [values, stages] = got.value;
            const dd = jsonDiff({ values, stages: stages.map((s) => s.toDict()) }, { values: want.values, stages: want.stages });
            if (!dd) res++;
            else bad.push(`${name} resolve(${JSON.stringify(want.params)?.slice(0, 80)}) ${dd}`);
        }
    }
    T.ok(`recipes: ${rt} of ${total} registered recipes' to_dict() round trip JSON-equal through Recipe.fromDict`, rt === total, bad.filter((b) => b.includes('to_dict')).slice(0, 2).join(' | '));
    T.ok(`recipes: describe() equal to the describe() of Recipe.from_dict(to_dict()) for ${desc} of ${total} (${descExact} also character for character; the rest differ only where Python prints an integral float as N.0)`,
        desc === total, bad.filter((b) => b.includes('describe')).slice(0, 2).join(' | '));
    T.ok(`recipes: repr of the recipe and every stage, and stage labels, equal for ${reprs} of ${total}`, reprs === total, bad.filter((b) => b.includes('repr')).slice(0, 2).join(' | '));
    T.ok(`recipes: resolve() equal (values and every stage) for ${res} of ${nres} knob sets (defaults and two more per recipe; apply code is the recipe packages')`,
        res === nres, bad.filter((b) => b.includes('resolve')).slice(0, 3).join(' | '));
    T.ok('recipes: every Blender recipe module imported', !Object.keys(M.recipes.failed).length, JSON.stringify(M.recipes.failed));
    const knobNames = Object.values(RS).flatMap((r) => Object.keys(r.to_dict.knobs));
    T.ok(`recipes: no knob name shadows Params' methods (${knobNames.length} knobs)`, !knobNames.some((k) => ['stage', 'stages', 'recipe', '_stages'].includes(k)));

    // test_core.py's recipe, with its apply written again here
    const TR = M.recipes.test_recipe;
    const spacingToD = (p) => {
        const f = p.stage('fluvial');
        f.D = f.K * (p.valley_spacing_m / 6.5) ** 2;
    };
    const tr = new Recipe('test_range', 'a test range', ['san_gabriel_mountains'],
        { size: 12000.0, resolution: 1024, context: 4, hero_cell: 0.5, palette: 'alpine' },
        { relief_m: new Knob(2000.0, 'm', [200.0, 6000.0], 'p99.5 relief'),
            valley_spacing_m: new Knob(400.0, 'm', [60.0, 3000.0], 'valley spacing', spacingToD),
            kind: new Knob('star', 'choice', ['star', 'barchan'], 'dune kind') },
        [new Stage('uplift', { shape: { kind: 'ridge', length_m: 9000 } }),
            new Stage('fluvial', { K: 1.5e-5, relief_m: '$relief_m', list: ['$kind', 3] }, 'all'),
            new Stage('breakup', { scales_m: [50, 15, 5] }, 'hero', 'smoothstep(30, 45, slope)')],
        'a recipe for the tests');
    T.ok('test recipe: toDict() JSON-equal', sameJson(tr.toDict(), TR.to_dict), jsonDiff(tr.toDict(), TR.to_dict) ?? '');
    T.ok('test recipe: describe() equal (integral floats as N)', tr.describe() === intFloats(TR.describe), tr.describe().split('\n')[2]);
    let ok = 0;
    for (const want of TR.resolve) {
        const [values, stages] = tr.resolve(want.params);
        if (sameJson({ values, stages: stages.map((s) => s.toDict()) }, { values: want.values, stages: want.stages })) ok++;
        else T.extra.test_recipe_diff = jsonDiff({ values, stages: stages.map((s) => s.toDict()) }, { values: want.values, stages: want.stages });
    }
    T.ok(`test recipe: resolve() with its apply bit-equal for ${ok} of ${TR.resolve.length} knob sets (D = K (s / 6.5)^2 in doubles)`, ok === TR.resolve.length, T.extra.test_recipe_diff ?? '');
    const twin = Recipe.fromDict(JSON.parse(JSON.stringify(tr.toDict())), tr);
    const [, st2] = twin.resolve({ valley_spacing_m: 800 });
    T.ok('test recipe: a JSON round trip keeps apply from the base; without a base there is none',
        Math.abs(st2[1].params.D - 1.5e-5 * (800 / 6.5) ** 2) < 1e-18 && !('D' in Recipe.fromDict(tr.toDict()).resolve()[1][1].params));
    const errs = {
        unknown_knob: () => tr.resolve({ relief: 100 }), out_of_range: () => tr.resolve({ relief_m: 9e9 }),
        bad_choice: () => tr.resolve({ kind: 'linear' }), not_a_number: () => tr.resolve({ relief_m: 'high' }),
        bad_levels: () => new Stage('x', null, 'heroes'), bad_where: () => new Stage('x', null, 'all', 'slope >'),
        bad_stage_key: () => Stage.fromDict({ op: 'x', level: 'all' }), bad_unit: () => new Knob(1.0, 'metres'),
        no_stage: () => new Params({}, tr.stages).stage('fluvail'),
    };
    const eb = [];
    let es = 0;
    for (const [k, fn] of Object.entries(errs)) {
        const got = tryRun(fn).error;
        const want = pyErrText(TR.errors[k]);
        if (got === want || intFloats(got ?? '') === intFloats(want)) es++;
        else eb.push(`${k}: ${got} vs ${want}`);
    }
    T.ok(`recipe errors: ${es} of ${Object.keys(errs).length} messages equal to Python's (integral floats as N)`, es === Object.keys(errs).length, eb.join(' | '));
    T.ok('Recipe.fromStages JSON-equal', sameJson(Recipe.fromStages([{ op: 'fluvial', params: { K: 1e-5 } }, { op: 'talus' }]).toDict(), M.recipes.from_stages));
    registerOp('test_op_xyz', () => 1);
    const near = tryRun(() => getOp('test_op_xzy')).error ?? '';
    T.ok('op registry: register, get, names, a miss names the nearest', getOp('test_op_xyz')() === 1 && opNames().includes('test_op_xyz') &&
        near.includes('test_op_xyz'), near);
    const sp = L.planLevels(12000, 1024, { context: 4, focus: [0, 0], hero: 0.5, warn: () => {} });
    T.ok('a stage selects its levels', sameJson(tr.stages[2].select(sp), sp.filter((lv) => lv.role === 'hero').map((lv) => lv.index)));
}


// -------------------------------------------------------------------------------------------- expr parser ---

{
    let ok = 0, vals = 0, nvals = 0;
    const bad = [];
    for (const c of M.expr.cases) {
        const e = E.parse(c.text);
        const same = sameJson(e.tree, c.tree) && String(e) === c.str && sameJson([...e.names()].sort(), c.names) &&
            String(E.parse(String(e))) === c.round_trip;
        if (same) ok++;
        else bad.push(`${c.text}: ${JSON.stringify(e.tree)} '${e}' vs ${JSON.stringify(c.tree)} '${c.str}'`);
        if (c.scalar !== undefined) {
            nvals++;
            const x = await e.eval({ a: 1, b: 2, c: 3, d: 4, e: 5 });
            if (x === c.scalar) vals++;
            else bad.push(`${c.text} = ${x} vs ${c.scalar}`);
        }
    }
    T.ok(`expr: ${ok} of ${M.expr.cases.length} parse trees, texts, names and round trips equal to expr.py's`, ok === M.expr.cases.length, bad.slice(0, 3).join(' | '));
    T.ok(`expr: ${vals} of ${nvals} number-only values equal to Python's float arithmetic, bit for bit`, vals === nvals, bad.filter((b) => b.includes(' = ')).join(' | '));
    let es = 0;
    const eb = [];
    for (const c of M.expr.errors) {
        const got = tryRun(() => E.parse(c.text)).error;
        const want = pyErrText(c.error);
        if (got === want) es++;
        else eb.push(`${JSON.stringify(c.text)}: ${got} vs ${want}`);
    }
    T.ok(`expr: ${es} of ${M.expr.errors.length} parse errors equal to expr.py's messages`, es === M.expr.errors.length, eb.slice(0, 4).join(' | '));
    const unk = await E.parse('slpoe * 2').eval({ slope: 1, wear: 2, deposit: 3, h: 4, A: 5 }).catch((e) => errText(e));
    T.ok('expr: an unknown name names the nearest', unk === pyErrText(M.expr.unknown_name), `${unk} vs ${M.expr.unknown_name}`);
}

Deno.exit(finish(T, 'plan_recipe_test.json'));
