// What the layered-rock package's tests share (PORT_PLAN.md 8.1: tests in tests/layered_rock/, outputs in
// tests/out/layered_rock/): the plan grade, a River rebuilt from a Blender stage dump, and the floor runs of the four
// recipes. Paths come from tests/_where.mjs; JavaScript per element here is test code.

import * as C from '../parity/_common.mjs';
import * as RV from '../../solvers/rivers.js';

export { C };
export const W = C.W;
export const RECIPES = ['canyon', 'incised_meanders', 'mesas_buttes', 'badlands'];

/** Command-line flags: --name value pairs and bare --flags. */
export function argsOf(argv = Deno.args) {
    const out = {};
    for (let i = 0; i < argv.length; i++) {
        if (!argv[i].startsWith('--')) continue;
        const k = argv[i].slice(2);
        if (i + 1 < argv.length && !argv[i + 1].startsWith('--')) out[k] = argv[++i];
        else out[k] = true;
    }
    return out;
}

/** The plan grade (PORT_PLAN.md 5.3): two numbers equal within 1e-12 relative (of `scale`, default the larger
 * magnitude). Returns the relative difference. */
export function rel(a, b, scale = null) {
    if (a === b || (Number.isNaN(a) && Number.isNaN(b))) return 0;
    const s = scale ?? Math.max(Math.abs(a), Math.abs(b));
    return Math.abs(a - b) / (s || 1);
}

/** Compare two arrays of numbers (or nested arrays) under the plan grade: { n, bitEqual, worst (relative, of the
 * largest |value| of `want`), ok (worst <= tol), lengthOk }. */
export function compareNumbers(got, want, tol = 1e-12) {
    const g = flat(got), w = flat(want);
    let scale = 0;
    for (const v of w) if (Number.isFinite(v)) scale = Math.max(scale, Math.abs(v));
    let bit = 0, worst = 0;
    const n = Math.min(g.length, w.length);
    for (let i = 0; i < n; i++) {
        if (Object.is(g[i], w[i]) || g[i] === w[i] || (Number.isNaN(g[i]) && Number.isNaN(w[i]))) { bit++; continue; }
        worst = Math.max(worst, Math.abs(g[i] - w[i]) / (scale || 1));
    }
    return { n: w.length, bitEqual: bit, worst, lengthOk: g.length === w.length, ok: g.length === w.length && worst <= tol };
}

function flat(a) {
    if (typeof a === 'number' || typeof a === 'bigint') return [Number(a)];
    if (ArrayBuffer.isView(a)) return Array.from(a, Number);
    const out = [];
    const walk = (x) => {
        if (Array.isArray(x) || ArrayBuffer.isView(x)) for (const y of x) walk(y);
        else out.push(Number(x));
    };
    walk(a);
    return out;
}

/** An (N, 2) float64 array as numpy's list of [x, y] pairs. */
export function pairs(a) {
    const out = new Array(a.length / 2);
    for (let i = 0; i < out.length; i++) out[i] = [a[2 * i], a[2 * i + 1]];
    return out;
}

/** A River (solvers/rivers.js) rebuilt from its stage-dump form: the JSON of ctx.shared.river with its arrays under
 * their paths (`arrays`: name -> { data, shape } as tests/parity/replay.mjs reads them, the paths 'shared.river.*').
 * Blender's replays unpickle the River; this is the port's counterpart, in the tests only. */
export function reviveRiver(d, arrays, prefix = 'shared.river') {
    const arr = (ref) => {
        if (ref === null || ref === undefined) return null;
        if (typeof ref === 'object' && ref.__array__) {
            const a = arrays[ref.__array__];
            if (!a) throw new Error(`revive river: no array ${ref.__array__} in the dump`);
            return a;
        }
        return ref;
    };
    const rv = Object.create(RV.River.prototype);
    rv.width_m = Number(d.width_m);
    rv.bed_m = Number(d.bed_m);
    rv.gradient = Number(d.gradient);
    rv.schedule = d.schedule.map((r) => r.map(Number));
    rv.spec = structuredClone(d.spec ?? {});
    rv.pool = d.pool.map(Number);
    rv.pool_seed = Math.trunc(d.pool_seed);
    const cc = arr(d._crest_cache);
    rv._crest_cache = cc ? Float64Array.from(cc.data) : null;
    const fc = arr(d.final_course[0]);
    const fcPts = pairs(fc.data);
    rv.final_course = [fcPts, Number(d.final_course[1])];
    rv.stages = (d.stages ?? []).map(([f, p, s0]) => [Number(f), pairs(arr(p).data), Number(s0)]);
    const pts = arr(d.points);
    // the course in use is the final one unless the dump's points differ (a growing course's stage)
    const ptsPairs = pairs(pts.data);
    const same = fc.data.length === pts.data.length && fc.data.every((v, i) => v === pts.data[i]);
    rv.points = same ? fcPts : ptsPairs;
    rv.s = Float64Array.from(arr(d.s).data);
    rv.s_through = Number(d.s_through);
    const tf = d.top_field;
    if (tf) {
        const h = arr(tf[0]);
        rv.top_field = [Float64Array.from(h.data), [h.shape[0], h.shape[1]], Number(tf[1]), Number(tf[2]), Number(tf[3])];
    } else {
        rv.top_field = null;
    }
    const top = arr(d.top);
    rv.top = top ? Float64Array.from(top.data) : null;
    rv._table = null;
    rv._pinsMade = [];
    if (d.seed !== undefined) rv.seed = d.seed;
    void prefix;
    return rv;
}

/** The floor run of a recipe and seed (tests/_where.mjs floorRun), or null. */
export const floorRun = (recipe, seed, which = 'base') => W.floorRun(recipe, seed, which);

/** Write a test's result to tests/out/layered_rock/<name>.json and return its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const code = T.done(null);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: T.rows.filter((r) => !r.passed).map((r) => r.check), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${W.out('layered_rock')}/${name}.json`, JSON.stringify(res, null, 1));
    return code;
}
