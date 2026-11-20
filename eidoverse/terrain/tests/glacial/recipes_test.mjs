// The glacial package's recipe as data (PORT_PLAN.md 5.3 'recipes' grade: equal JSON): alpine_valley against the
// Blender registry's own (tests/core_inputs/core_inputs_expected.py, run by Blender's Python, records every registered
// recipe): to_dict(), describe(), and resolve() with its knob functions at the defaults and two other knob sets (every
// numeric knob a quarter and three quarters into its range, choices and bools moved), and resolve() of the recipe
// rebuilt from its dict; the yosemite preset resolves; the bench check raises as Blender's does; the registry finds
// the package's ops. No GPU.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/glacial/recipes_test.mjs

import * as reg from '../../recipes/index.js';
import { Recipe } from '../../core/recipe.js';
import * as AV from '../../recipes/alpine_valley.js';
import { fixtures, intFloats, jsonDiff, manifest } from '../core_inputs/_common.mjs';
import * as C from '../parity/_common.mjs';
import { finish } from './_glacial.mjs';

const T = new C.Checks('glacial: the recipe as data');
const FIX = fixtures();
if (!FIX) Deno.exit(0);
const M = manifest(FIX);

function resolved(r, params) {
    try {
        const [v, st] = r.resolve(params);
        return { params, values: JSON.parse(JSON.stringify(v)), stages: st.map((s) => s.toDict()) };
    } catch (e) {
        return { params, error: `${e.name}: ${e.message}` };
    }
}

const name = 'alpine_valley';
const want = M.recipes.recipes[name];
if (!want) T.ok(`${name}: in the Blender fixtures`, false, 'not recorded');
else {
    const r = reg.get(name);
    const d = r.toDict();
    T.ok(`${name}: toDict() JSON-equal to Blender's to_dict()`, !jsonDiff(d, want.to_dict), jsonDiff(d, want.to_dict) ?? '');
    const a = intFloats(r.describe()), b = intFloats(want.describe);
    T.ok(`${name}: describe() equal (integral floats as N)`, a === b, a === b ? '' :
        `first difference at ${[...a].findIndex((ch, i) => ch !== b[i])}`);
    want.resolve.forEach((w, i) => {
        const got = resolved(r, w.params);
        const diff = jsonDiff(got, w);
        T.ok(`${name}: resolve() with knob set ${i} (${i ? 'moved' : 'defaults'}) equal, knob functions included`, !diff, diff ?? '');
    });
    const nb = Recipe.fromDict(JSON.parse(JSON.stringify(d)));
    want.resolve_nobase.forEach((w, i) => {
        const diff = jsonDiff(resolved(nb, w.params), w);
        T.ok(`${name}: resolve() of the recipe rebuilt from its dict, knob set ${i}`, !diff, diff ?? '');
    });
    // the Yosemite preset: its knobs resolve (the upland horseshoe draining west, no cirques)
    const y = AV.preset('yosemite');
    const ry = resolved(r, y.params);
    const vu = ry.stages?.find((s) => s.op === 'valley_uplift');
    T.ok("the 'yosemite' preset resolves: the upland horseshoe draining west, its trunk at bench_m 970, no cirques",
        !ry.error && vu.params.shape.kind === 'horseshoe' && vu.params.shape.azimuth_deg === 270 &&
        vu.params.shape.trunk.bench_m === 970 && ry.stages.find((s) => s.op === 'glacial').params.cirques === false &&
        y.size === 12000 && y.base_elevation_m === 1100, ry.error ?? JSON.stringify(vu?.params.shape.trunk));
    // the bench check (alpine_valley.py _shape): a trunk held over 0.75 of the relief raises, as Blender's does
    const bad = resolved(r, { relief_m: 1100.0, bench_m: 970.0 });
    T.ok('bench_m over 0.75 of relief_m raises, naming both', /bench_m 970 m is over 0\.75 of relief_m 1100 m/.test(bad.error ?? ''),
        bad.error ?? 'no error');
    T.ok('defaultsFor gives the masks\' snow and tree lines', JSON.stringify(r.defaultsFor({ snowline_m: 2750, treeline_m: 1950 })) ===
        JSON.stringify({ mask_params: { snowline_m: 2750, treeline_m: 1950 } }), '');
}
for (const op of ['valley_uplift', 'glacial']) T.ok(`the registry finds op '${op}'`, await reg.hasOp(op), '');
T.ok('no recipe or solver module failed to import', Object.keys(reg.failed()).length === 0, JSON.stringify(reg.failed()));
Deno.exit(finish(T, 'recipes_test'));
