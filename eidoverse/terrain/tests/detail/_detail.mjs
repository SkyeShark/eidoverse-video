// What the detail package's tests share: the result file and a few grades. Paths come from tests/_where.mjs.
//
//     import * as D from './_detail.mjs';
//     const T = new D.C.Checks('detail: ...');   ...   Deno.exit(D.finish(T, 'kernels_test'));
//
// JavaScript per cell here is test code (the edition's rule allows it in tests only).

import * as C from '../parity/_common.mjs';

export { C };
export const W = C.W;

/** Write a test's result to tests/out/detail/<name>.json and return its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${W.out('detail')}/${name}.json`, JSON.stringify(res, null, 1));
    return code;
}

/** The arguments of a test: opt('--x', dflt), flag('--y'). */
export function argsOf(argv = Deno.args) {
    const args = [...argv];
    return {
        opt: (n, d = null) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; },
        flag: (n) => args.includes(n),
        list: (n, d = null) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1].split(',') : d; },
    };
}

/** Bits of two Float32Arrays that differ: { n, first }. */
export function bitsDiff(a, b) {
    const x = new Uint32Array(a.buffer, a.byteOffset, a.length), y = new Uint32Array(b.buffer, b.byteOffset, b.length);
    let n = 0, first = -1;
    for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) { n++; if (first < 0) first = i; }
    return { n: n + Math.abs(x.length - y.length), first };
}

/** One channel of an interleaved array as its own Float32Array. */
export function channel(a, nch, c) {
    const out = new Float32Array(a.length / nch);
    for (let i = 0; i < out.length; i++) out[i] = a[i * nch + c];
    return out;
}

/** Sum of a typed array in float64. */
export function sum64(a, nch = 1, c = 0) {
    let s = 0;
    for (let i = c; i < a.length; i += nch) s += a[i];
    return s;
}
