// What the plants package's tests share (PORT_PLAN.md 8.2 row P15): where its fixtures are, the result file, and a
// few helpers. Paths come from tests/_where.mjs.
//
//     import * as S from './_plants.mjs';
//     const root = S.fixtureRoot();                  // tests/out/plants/fixtures/blender_<commit>, or null (says how)
//     const T = new S.C.Checks('plants: ...');  ...  Deno.exit(S.finish(T, 'ecotopes_test'));
//
// The fixtures are tests/plants/plants_fixtures.py's, made by the Blender edition's own Python from the commit the
// port files name: $EIDO_PLANTS_FIXTURES names the folder (tests/out/plants/fixtures/<name>), else the newest.
// JavaScript per spot here is test code (the edition's rule allows it in tests only).

import * as C from '../parity/_common.mjs';

export { C };
export const W = C.W;

/** tests/out/plants/fixtures/<key>: $EIDO_PLANTS_FIXTURES, else the newest folder by its key.json; null after saying
 * how to make them. */
export function fixtureRoot(what = 'the plant fixtures') {
    const root = `${W.out('plants')}/fixtures`;
    const want = Deno.env.get('EIDO_PLANTS_FIXTURES');
    if (want) return W.exists(`${root}/${want}/key.json`) ? `${root}/${want}` : null;
    let best = null, t = -1;
    try {
        for (const e of Deno.readDirSync(root)) {
            const k = `${root}/${e.name}/key.json`;
            if (!e.isDirectory || !W.exists(k)) continue;
            const m = Deno.statSync(k).mtime?.getTime() ?? 0;
            if (m > t) { t = m; best = `${root}/${e.name}`; }
        }
    } catch (_e) { /* no fixtures yet */ }
    if (!best) {
        console.log(`[skip] ${what}: make them with EIDO_BLENDER_EDITION=<a checkout or an export of the blender branch> ` +
            `<Blender's python> -I eidoverse/terrain/tests/plants/plants_fixtures.py --ecotopes --spots`);
    }
    return best;
}

/** The key record of the fixtures (commit, code hash, versions), or null. */
export function fixtureKey() {
    const root = fixtureRoot();
    return root ? JSON.parse(Deno.readTextFileSync(`${root}/key.json`)) : null;
}

/** Write a test's result to tests/out/plants/<name>.json and return its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), fixtures: fixtureKey(), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${W.out('plants')}/${name}.json`, JSON.stringify(res, null, 1));
    return code;
}

/** The arguments of a test: opt('--x', dflt), flag('--y'), list('--z'). */
export function argsOf(argv = Deno.args) {
    const args = [...argv];
    return {
        opt: (n, d = null) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; },
        flag: (n) => args.includes(n),
        list: (n, d = null) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1].split(',') : d; },
    };
}

/** JSON-equality of two JSON-like values, with the first difference's path (numbers equal as doubles). */
export function jsonDiff(a, b, path = '') {
    if (typeof a === 'number' && typeof b === 'number') return a === b || (Number.isNaN(a) && Number.isNaN(b)) ? null : `${path}: ${a} != ${b}`;
    if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') {
        return a === b ? null : `${path}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`;
    }
    if (Array.isArray(a) !== Array.isArray(b)) return `${path}: an array against an object`;
    if (Array.isArray(a)) {
        if (a.length !== b.length) return `${path}: length ${a.length} != ${b.length}`;
        for (let i = 0; i < a.length; i++) {
            const d = jsonDiff(a[i], b[i], `${path}[${i}]`);
            if (d) return d;
        }
        return null;
    }
    const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
    if (ka.join('\u0000') !== kb.join('\u0000')) {
        const only = ka.filter((k) => !kb.includes(k)), other = kb.filter((k) => !ka.includes(k));
        return `${path}: keys ${JSON.stringify(only)} only here, ${JSON.stringify(other)} only there`;
    }
    for (const k of ka) {
        const d = jsonDiff(a[k], b[k], `${path}.${k}`);
        if (d) return d;
    }
    return null;
}

export const sci = C.sci;
