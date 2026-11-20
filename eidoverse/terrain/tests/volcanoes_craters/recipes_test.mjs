// The volcanoes and craters package's four recipes as data (PORT_PLAN.md 5.1's recipe fixtures, 5.3's recipe grade:
// equal JSON): stratovolcano, caldera, cinder_cones and impact_crater against the Blender edition's own to_dict(),
// describe() and resolve() (tests/core_inputs/core_inputs_expected.py's fixtures, made by Blender's Python: the
// defaults and two more knob sets per recipe, each knob's apply code run, which is this package's port).
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/volcanoes_craters/recipes_test.mjs     (no GPU)
//
// Writes tests/out/volcanoes_craters/recipes_test.json.

import * as REG from '../../recipes/index.js';
import * as V from './_vc.mjs';

const { C } = V;
const T = new C.Checks('volcanoes_craters: the recipes as data');
const fixtureDir = `${C.W.TESTS}/out/core_inputs/fixtures_2.3.4`;
const M = C.readJson(`${fixtureDir}/manifest.json`);

/** null when a and b are equal JSON (numbers by value, keys in any order), else where they first differ. */
function same(a, b, path = '') {
    if (a === b) return null;
    if (typeof a === 'number' && typeof b === 'number') return Object.is(a, b) || a === b ? null : `${path}: ${a} / ${b}`;
    if (a === null || b === null || a === undefined || b === undefined || typeof a !== typeof b) {
        return `${path}: ${JSON.stringify(a)?.slice(0, 80)} / ${JSON.stringify(b)?.slice(0, 80)}`;
    }
    if (Array.isArray(a) !== Array.isArray(b)) return `${path}: a list and a dict`;
    if (Array.isArray(a)) {
        if (a.length !== b.length) return `${path}: ${a.length} items / ${b.length}`;
        for (let i = 0; i < a.length; i++) { const d = same(a[i], b[i], `${path}[${i}]`); if (d) return d; }
        return null;
    }
    if (typeof a === 'object') {
        const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
        if (ka.join(',') !== kb.join(',')) return `${path}: keys ${ka.filter((k) => !kb.includes(k))} / ${kb.filter((k) => !ka.includes(k))}`;
        for (const k of ka) { const d = same(a[k], b[k], `${path}.${k}`); if (d) return d; }
        return null;
    }
    return `${path}: ${a} / ${b}`;
}

if (!M) {
    T.ok('recipe fixtures', false, `none at ${fixtureDir} (tests/core_inputs/core_inputs_expected.py)`);
} else {
    for (const name of V.RECIPES) {
        const want = M.recipes.recipes[name];
        const rec = REG.get(name);
        const dd = same(rec.toDict(), want.to_dict, name);
        T.ok(`${name}: toDict() JSON-equal to to_dict() (stages, knobs and their docs, defaults)`, dd === null, dd ?? '');
        // (a JavaScript number does not know it was written 8000.0: core/recipe.js prints a whole float as an
        // integer, as for every recipe of the edition; the text is compared with whole floats printed alike)
        const whole = (s) => s.replace(/(\d)\.0(?=[^\d]|$)/g, '$1');
        const got = whole(rec.describe()), wantD = whole(want.describe);
        let at = 0;
        while (at < got.length && got[at] === wantD[at]) at++;
        T.ok(`${name}: describe() equal to Blender's (whole floats printed alike)`, got === wantD,
            got === wantD ? '' : `at ${at}: ${JSON.stringify(got.slice(at - 40, at + 60))} / ${JSON.stringify(wantD.slice(at - 40, at + 60))}`);
        let ok = 0;
        const bad = [];
        for (const r of want.resolve) {
            try {
                const [values, stages] = rec.resolve(r.params);
                const d = same({ values, stages: stages.map((s) => s.toDict()) }, { values: r.values, stages: r.stages }, name);
                if (d === null) ok++;
                else bad.push(d);
            } catch (e) {
                bad.push(`${JSON.stringify(r.params).slice(0, 60)}: ${e.message}`);
            }
        }
        T.ok(`${name}: resolve() equal to Blender's for ${ok} of ${want.resolve.length} knob sets (each knob's apply code)`,
            ok === want.resolve.length, bad.slice(0, 2).join(' | '));
    }
    T.ok('the registry imported every recipe module and solver of this package', !Object.keys(REG.failed()).some((k) =>
        /stratovolcano|caldera|cinder_cones|impact_crater|volcanic|impact/.test(k)), JSON.stringify(REG.failed()));
    const ops = await REG.opNames();
    const mine = ['stratovolcano', 'cinder_cones', 'caldera_collapse', 'volcano_setting', 'volcano_plain', 'volcano_age',
        'lava_flows', 'lava_rubble', 'cone_rills', 'caldera_lake', 'volcano_lakes', 'impact_crater', 'crater_blocks'];
    T.ok(`the ops ${mine.join(', ')} are registered`, mine.every((o) => ops.includes(o)), mine.filter((o) => !ops.includes(o)).join(', '));
}

Deno.exit(V.finish(T, 'recipes_test', { fixtures: fixtureDir, blender_commit: M?.blender_commit ?? null }));
