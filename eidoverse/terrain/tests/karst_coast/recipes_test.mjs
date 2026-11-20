// The package's recipes as data (PORT_PLAN.md 5.3 "recipes: toDict(), resolved stages, describe(): equal JSON"):
// recipes/tower_karst.js and recipes/sea_cliffs.js against the Blender recipes' to_dict(), describe() and resolve()
// with their defaults and two other knob sets (tests/core_inputs/core_inputs_expected.py's recipe fixtures, Blender's
// Python), and sea_cliffs' flint column (numpy's default_rng(1907)) against sea_cliffs.py _flint_column().
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/karst_coast/recipes_test.mjs
//
// One key is set aside and named: defaults.palette, the dict tower_karst.py's karst_palette() and sea_cliffs.py's
// chalk_palette() build from build/palettes.py, the surfacing wave's module, not ported yet (the recipes' headers say
// so); every other key of to_dict() must be equal. No GPU. Writes tests/out/karst_coast/recipes_test.json.

import * as C from '../parity/_common.mjs';
import * as KC from './_common.mjs';
import * as SC from '../../recipes/sea_cliffs.js';
import * as TK from '../../recipes/tower_karst.js';

const T = new C.Checks('karst and coast: the recipes as data');
const fxDir = `${C.W.TESTS}/out/core_inputs`;
let M = null;
for (const e of (() => { try { return [...Deno.readDirSync(fxDir)]; } catch (_e) { return []; } })()) {
    if (e.isDirectory && e.name.startsWith('fixtures_')) M = C.readJson(`${fxDir}/${e.name}/manifest.json`) ?? M;
}
const canon = (v) => JSON.stringify(v, (_k, x) => (x && typeof x === 'object' && !Array.isArray(x) ?
    Object.fromEntries(Object.keys(x).sort().map((kk) => [kk, x[kk]])) : x));
const intFloats = (s) => s.replace(/(\d)\.0(?!\d)/g, '$1');
if (!M) T.ok('recipe fixtures', false, 'no core_inputs fixtures (tests/core_inputs/core_inputs_expected.py)');
for (const [name, rec] of [['tower_karst', TK.TOWER_KARST], ['sea_cliffs', SC.SEA_CLIFFS]]) {
    const r = M?.recipes?.recipes?.[name];
    if (!r) { T.ok(`${name}: fixture`, false, 'not in the recipe fixtures'); continue; }
    const mine = rec.toDict(), want = structuredClone(r.to_dict);
    const palMine = mine.defaults.palette, palWant = want.defaults.palette;
    delete mine.defaults.palette;
    delete want.defaults.palette;
    T.ok(`${name}: toDict() JSON-equal to to_dict() but for defaults.palette (the surfacing wave's dict; here ` +
        `'${typeof palMine === 'string' ? palMine : 'a dict'}')`, canon(mine) === canon(want),
    canon(mine) === canon(want) ? `Blender's palette: ${typeof palWant === 'object' ? `a dict titled "${palWant.title?.slice(0, 60)}..."` : palWant}` : 'differs');
    T.ok(`${name}: describe() equal (but the palette line)`, intFloats(rec.describe()).split('\n').filter((l) => !l.includes('palette=')).join('\n') ===
        intFloats(r.describe).split('\n').filter((l) => !l.includes('palette=')).join('\n'), '');
    let ok = 0;
    const bad = [];
    for (const want of r.resolve) {
        try {
            const [values, stages] = rec.resolve(want.params);
            const got = { values, stages: stages.map((s) => s.toDict()) };
            if (canon(got) === canon({ values: want.values, stages: want.stages })) ok++;
            else bad.push(JSON.stringify(want.params));
        } catch (e) {
            if (want.error) ok++; else bad.push(`${JSON.stringify(want.params)}: ${e.message}`);
        }
    }
    T.ok(`${name}: resolve() equal for its defaults and ${r.resolve.length - 1} other knob sets (values and every stage's ` +
        'parameters, the knobs\' apply included)', ok === r.resolve.length, bad.join('; ') || `${ok} of ${r.resolve.length}`);
}

// the chalk face's flint column (numpy's default_rng(1907))
const fx = KC.loadFixtures();
const fc = fx && KC.findCase(fx, 'sea_cliffs._flint_column');
if (fc) {
    const want = C.array(fx.dir, fc.outputs.thickness), got = SC.flintColumn().formations.map((r) => r[1]);
    T.ok('sea_cliffs: the flint column bit for bit numpy\'s (default_rng(1907))', got.length === want.length &&
        got.every((v, i) => v === want[i]), `${got.length} rows`);
} else {
    T.ok('sea_cliffs: the flint column', false, KC.NO_FIXTURES);
}
Deno.exit(KC.finish(T, 'recipes_test'));
