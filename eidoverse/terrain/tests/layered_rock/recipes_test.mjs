// The layered-rock package's four recipes as data (PORT_PLAN.md 5.1's recipe fixtures, 5.3's recipe grade: equal
// JSON): canyon, incised_meanders, mesas_buttes and badlands against the Blender edition's own to_dict() and resolve()
// (tests/core_inputs/core_inputs_expected.py's fixtures, made by Blender's Python: the defaults and two more knob sets
// per recipe, each knob's apply code run, which is this package's port).
//
//     deno run --no-config --no-lock --allow-all eidoverse/terrain/tests/layered_rock/recipes_test.mjs     (no GPU)
//
// defaults.palette is compared in its strata part (the column's material bands, strata.js materialColumn) only: the
// rest of a recipe's palette is build/palettes.js's, the surfacing wave's (strata.js paletteFor). Writes
// tests/out/layered_rock/recipes_test.json.

import * as REG from '../../recipes/index.js';
import { C, RECIPES, finish } from './_layered.mjs';

const T = new C.Checks('layered_rock: the recipes as data');
const fixtureDir = `${C.W.TESTS}/out/core_inputs/fixtures_2.3.4`;
const M = C.readJson(`${fixtureDir}/manifest.json`);

function same(a, b, path = '') {
    if (a === b) return null;
    if (typeof a === 'number' && typeof b === 'number') return Object.is(a, b) || a === b ? null : `${path}: ${a} / ${b}`;
    if (a === null || b === null || typeof a !== typeof b) return `${path}: ${JSON.stringify(a)?.slice(0, 80)} / ${JSON.stringify(b)?.slice(0, 80)}`;
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
    for (const name of RECIPES) {
        const want = M.recipes.recipes[name];
        const rec = await REG.get(name);
        const got = rec.toDict();
        const wd = structuredClone(want.to_dict), gd = structuredClone(got);
        const wPal = wd.defaults.palette, gPal = gd.defaults.palette;
        delete wd.defaults.palette;
        delete gd.defaults.palette;
        const dd = same(gd, wd, name);
        T.ok(`${name}: toDict() JSON-equal to to_dict() (stages, knobs and their docs, defaults but the palette)`, dd === null, dd ?? '');
        const ps = same(gPal?.strata, wPal?.strata, `${name}.palette.strata`);
        T.ok(`${name}: defaults.palette's strata layers (the column's material bands) equal to Blender's`, ps === null,
            ps ?? `the rest of the palette (${Object.keys(wPal ?? {}).filter((k) => k !== 'strata').join(', ')}) is build/palettes.js's: ${gPal?.pending ?? 'present'}`);
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
        /canyon|meanders|mesas|badlands|strata|rivers/.test(k)), JSON.stringify(REG.failed()));
    const ops = await REG.opNames();
    T.ok('the ops strata, plateau, river_path and strata_fluvial are registered', ['strata', 'plateau', 'river_path',
        'strata_fluvial'].every((o) => ops.includes(o)), ops.join(', '));
}

Deno.exit(finish(T, 'recipes_test', { fixtures: fixtureDir, blender_commit: M?.blender_commit ?? null }));
