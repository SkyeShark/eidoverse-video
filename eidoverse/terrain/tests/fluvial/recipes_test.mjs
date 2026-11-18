// The fluvial package's recipes as data (PORT_PLAN.md 5.3 'recipes' grade: equal JSON): rolling_hills, fluvial_range
// and meadow against the Blender registry's own (tests/core_inputs/core_inputs_expected.py, run by Blender's Python,
// records every registered recipe): to_dict(), describe(), and resolve() with its knob functions at the defaults and
// two other knob sets (every numeric knob a quarter and three quarters into its range, choices and bools moved), and
// resolve() of the recipe rebuilt from its dict; and the registry finds the package's ops. No GPU.
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/fluvial/recipes_test.mjs [fixtures folder]

import * as reg from '../../recipes/index.js';
import { Recipe } from '../../core/recipe.js';
import { fixtures, intFloats, jsonDiff, manifest } from '../core_inputs/_common.mjs';
import * as C from '../parity/_common.mjs';

const T = new C.Checks('fluvial: the recipes as data');
const FIX = fixtures();
if (!FIX) Deno.exit(0);
const M = manifest(FIX);
const NAMES = ['rolling_hills', 'fluvial_range', 'meadow'];

function resolved(r, params) {
    try {
        const [v, st] = r.resolve(params);
        return { params, values: JSON.parse(JSON.stringify(v)), stages: st.map((s) => s.toDict()) };
    } catch (e) {
        return { params, error: `${e.name}: ${e.message}` };
    }
}

for (const name of NAMES) {
    const want = M.recipes.recipes[name];
    if (!want) { T.ok(`${name}: in the Blender fixtures`, false, 'not recorded'); continue; }
    let r;
    try { r = reg.get(name); } catch (e) { T.ok(`${name}: registered`, false, e.message); continue; }
    const d = r.toDict();
    T.ok(`${name}: toDict() JSON-equal to Blender's to_dict()`, !jsonDiff(d, want.to_dict), jsonDiff(d, want.to_dict) ?? '');
    // P2's rule (plan_recipe_test.mjs): equal where Python prints an integral float as N.0 and JavaScript as N
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
}
for (const op of ['uplift', 'fluvial', 'valley_floor', 'incise', 'creep', 'talus', 'threshold', 'soil_hills', 'hummocks']) {
    T.ok(`the registry finds op '${op}'`, await reg.hasOp(op), '');
}
T.ok('no recipe or solver module failed to import', Object.keys(reg.failed()).length === 0, JSON.stringify(reg.failed()));
Deno.exit(C.finish(T, 'fluvial_recipes_test'));
