// What the karst-and-coast package's tests share: this package's own fixtures (tests/karst_coast/
// karst_coast_expected.py, run by Blender's Python), the floor runs of its recipes under any parity key of the same
// Blender terrain code, and the result files (tests/out/karst_coast/). Test code: JavaScript per cell is allowed
// here only.

import * as C from '../parity/_common.mjs';

const W = C.W;
export const OUT = () => W.out('karst_coast');
export const NO_FIXTURES = 'no karst_coast fixtures: make them with <Blender\'s python> -I ' +
    'eidoverse/terrain/tests/karst_coast/karst_coast_expected.py (needs $EIDO_BLENDER_EDITION)';

/** This package's fixtures { dir, manifest }, or null. */
export function loadFixtures() {
    const dir = `${OUT()}/fixtures`;
    const m = C.readJson(`${dir}/manifest.json`);
    if (!m) {
        console.log(`[skip] ${NO_FIXTURES}`);
        return null;
    }
    return { dir, manifest: m };
}

/** The first case of a function (and a label's start, when given). */
export const findCase = (fx, fn, label = null) => fx.manifest.cases.find((c) => c.function === fn && (!label || c.label.startsWith(label)));
export const findCases = (fx, fn) => fx.manifest.cases.filter((c) => c.function === fn);

const codeOf = (dir) => {
    const k = C.readJson(`${dir}/manifest.json`)?.key;
    return k ? `${k.field_hash}|${k.terrain_hash}` : null;
};

/** The parity key folder whose fixtures (a kind of tests/parity/fixtures.py) exist: $EIDO_PARITY_KEY or the newest
 * key, else another key of the same Blender terrain code (its manifest's field_hash and terrain_hash equal). */
export function parityFixtures(kind) {
    const key = W.parityKeyDir();
    if (!key) return null;
    const mine = codeOf(key);
    for (const k of [{ dir: key }, ...W.parityKeys()]) {
        if (k.dir !== key && codeOf(k.dir) !== mine) continue;
        const dir = `${k.dir}/fixtures/${kind}`;
        if (W.exists(`${dir}/manifest.json`)) return { dir, manifest: JSON.parse(Deno.readTextFileSync(`${dir}/manifest.json`)) };
    }
    console.log(`[skip] no ${kind} fixtures under a parity key of this Blender code (tests/parity/fixtures.py)`);
    return null;
}

/** The floor run (recipe, seed, which) under the parity key, else under another key of the same Blender terrain
 * code: [dir, key name] or null. */
export function floorRunOfCode(recipe, seed, which = 'base') {
    const key = W.parityKeyDir();
    if (!key) return null;
    const mine = codeOf(key);
    for (const k of [{ dir: key, name: key.split('/').pop() }, ...W.parityKeys()]) {
        if (k.dir !== key && codeOf(k.dir) !== mine) continue;
        const dir = `${k.dir}/${recipe}_s${seed}_draft/${which}`;
        if (W.exists(`${dir}/done.json`)) return [dir, k.name];
    }
    return null;
}

/** Write a test's result to tests/out/karst_coast/<name>.json; its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${OUT()}/${name}.json`, JSON.stringify(res, null, 1));
    return code;
}

/** A Float64Array of a fixture array (any float dtype). */
export const f64 = (fx, a) => Float64Array.from(C.array(fx.dir, a));
