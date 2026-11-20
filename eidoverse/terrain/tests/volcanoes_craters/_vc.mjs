// What the volcanoes and craters package's tests share: the result file, the arguments, the floor runs of the four
// recipes (found under any parity key of the same Blender terrain code), and a dumped context turned back into what
// the port's ops hold. Paths come from tests/_where.mjs.
//
//     import * as V from './_vc.mjs';
//     const T = new V.C.Checks('volcanoes_craters: ...');   ...   Deno.exit(V.finish(T, 'replay_test'));
//
// JavaScript per cell here is test code (the edition's rule allows it in tests only).

import * as C from '../parity/_common.mjs';

export { C };
export const W = C.W;
export const RECIPES = ['stratovolcano', 'caldera', 'cinder_cones', 'impact_crater'];

/** Write a test's result to tests/out/volcanoes_craters/<name>.json and return its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${W.out('volcanoes_craters')}/${name}.json`, JSON.stringify(res, null, 1));
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

/** The floor run of (recipe, seed) under the parity key, else under another key of the same Blender terrain code
 * (equal field and terrain hashes in the keys' manifests): [dir, key name] or null. */
export function floorRunOfCode(recipe, seed, which = 'base') {
    const key = W.parityKeyDir();
    if (!key) return null;
    const own = W.floorRun(recipe, seed, which);
    if (own) return [own, key.split('/').pop()];
    const code = (dir) => { const k = C.readJson(`${dir}/manifest.json`)?.key; return k ? `${k.field_hash}|${k.terrain_hash}` : null; };
    const mine = code(key);
    if (!mine) return null;
    for (const k of W.parityKeys()) {
        const dir = `${k.dir}/${recipe}_s${seed}_draft/${which}`;
        if (k.dir !== key && code(k.dir) === mine && W.exists(`${dir}/done.json`)) return [dir, k.name];
    }
    return null;
}

/** A dumped context's shared record with its arrays ({ __array__: path } placeholders, the arrays in
 * ctx.sharedArrays: tests/parity/replay.mjs stageContext) as GPU fields, as the port's ops keep them (stampAdd's
 * ctx.shared._stamps). Returns the fields made (the caller releases them). */
export function sharedToGpu(R, ctx) {
    const made = [];
    const walk = (o) => {
        if (!o || typeof o !== 'object') return o;
        if (Array.isArray(o)) return o.map(walk);
        if (typeof o.__array__ === 'string') {
            const a = ctx.sharedArrays?.[o.__array__];
            if (!a) throw new Error(`the dump holds no array ${o.__array__}`);
            const data = a.dtype === '<f4' ? a.data : Float32Array.from(a.data);
            const f = R.field(a.shape[0], a.shape[1] ?? 1, 1, data);
            made.push(f);
            return f;
        }
        for (const k of Object.keys(o)) o[k] = walk(o[k]);
        return o;
    };
    if (ctx?.shared) walk(ctx.shared);
    return made;
}
