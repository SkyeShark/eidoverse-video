// What the parity package's Deno tools share (PORT_PLAN.md 5): reading the fixtures and dumps the Blender edition
// made (tests/parity/fixtures.py, blender_chaos_floor.py, blender_stage_dump.py), the grades of plan 5.3 as
// functions, and the result files. Paths come from tests/_where.mjs.
//
//     import * as C from './_common.mjs';
//     const fx = C.loadFixture('functions/metrics');     // { dir, manifest } or null (says how to make it)
//     const a = C.array(fx.dir, case.inputs.h);          // a typed array (f32, f64, i32, i64 as BigInt64, u32, u8)
//     C.grade(got, want, { k: 1e-6, range, m: 16 })      // a float grade: { ok, err, tol }
//     const T = new C.Checks('parity/metrics');  ...  Deno.exit(C.finish(T, 'metrics_test'));
//
// A float grade is max(k x range, m x ulp(|value|)) (the lead's rule on the plan's 5.3): k x range is the plan's
// tolerance for the grade (1e-4 of a channel's range for a kernel, 1e-5 for a float function, 1e-6 for a number),
// and m x ulp is the rounding the function's built-ins can leave on a correct port (about 4 for arithmetic, 16 with
// a square root and an arctangent, 80 with pow), so a correct port never fails a grade on rounding alone. ulp is
// float32's at the value unless the quantity is computed in doubles.

import * as W from '../_where.mjs';
import { Checks } from '../core_runner/_common.mjs';

export { Checks, W };

const F32 = new Float32Array(1), U32 = new Uint32Array(F32.buffer);

/** The spacing of float32 at |x| (np.spacing(np.float32(|x|))). */
export function ulp32(x) {
    const f = Math.fround(Math.abs(x));
    if (!Number.isFinite(f)) return NaN;
    F32[0] = f;
    U32[0] += 1;
    return F32[0] - f;
}

/** The spacing of float64 at |x|. */
export function ulp64(x) {
    const a = Math.abs(x);
    if (!Number.isFinite(a)) return NaN;
    if (a === 0) return Number.MIN_VALUE;
    const e = Math.floor(Math.log2(a));
    return Math.max(2 ** (e - 52), Number.MIN_VALUE);
}

/** A float grade (see above): opts { k, range, m, double (ulp of float64), abs (an absolute floor) }. */
export function grade(got, want, opts = {}) {
    const ulp = opts.double ? ulp64 : ulp32;
    const tol = Math.max((opts.k ?? 0) * (opts.range ?? Math.abs(want)), (opts.m ?? 0) * ulp(want), opts.abs ?? 0);
    const err = Math.abs(got - want);
    const same = got === want || (Number.isNaN(got) && Number.isNaN(want));
    return { ok: same || err <= tol, err: same ? 0 : err, tol };
}

/** Two arrays graded as a channel: max |got - want| against max(k x the want's range, m x ulp of its largest value).
 * { ok, err, tol, range, at } (plan 5.3's kernel and function grades; Blender's twins.compare, with the floor). */
export function gradeArray(got, want, opts = {}) {
    let lo = Infinity, hi = -Infinity, amax = 0, err = 0, at = -1, bad = 0;
    for (let i = 0; i < want.length; i++) {
        const w = want[i], g = got[i];
        if (Number.isNaN(w) && Number.isNaN(g)) continue;
        if (!Number.isFinite(w) || !Number.isFinite(g)) {
            if (w !== g) bad++;
            continue;
        }
        if (w < lo) lo = w;
        if (w > hi) hi = w;
        const a = Math.abs(w);
        if (a > amax) amax = a;
        const e = Math.abs(g - w);
        if (e > err) { err = e; at = i; }
    }
    const range = hi >= lo ? hi - lo : 0;
    const ulp = opts.double ? ulp64 : ulp32;
    const tol = Math.max((opts.k ?? 0) * Math.max(range, 1e-6 * amax, 1e-20), (opts.m ?? 0) * ulp(amax), opts.abs ?? 0);
    return { ok: bad === 0 && got.length === want.length && err <= tol, err, tol, range, at, nonFinite: bad };
}

const TYPES = { f32: Float32Array, f64: Float64Array, i32: Int32Array, u32: Uint32Array, u8: Uint8Array,
    i8: Int8Array, u16: Uint16Array, i64: BigInt64Array, f16: globalThis.Float16Array };

/** A fixture's array (little-endian, C order): { file, shape, dtype } read from `dir` as a typed array. */
export function array(dir, a) {
    const bytes = Deno.readFileSync(`${dir}/${a.file}`);
    const T = TYPES[a.dtype];
    if (!T) throw new Error(`fixture array ${a.file}: dtype ${a.dtype} is not read here`);
    return new T(bytes.buffer, bytes.byteOffset, bytes.byteLength / T.BYTES_PER_ELEMENT);
}

/** { dir, manifest } of a fixture kind (tests/_where.mjs fixtures), or null after saying how to make it. */
export function loadFixture(kind) {
    const dir = W.fixtures(kind);
    if (!dir) return null;
    return { dir, manifest: JSON.parse(Deno.readTextFileSync(`${dir}/manifest.json`)) };
}

/** A gzipped file of JSON lines (a dispatch log, plan 5.2) as an array of the parsed lines. */
export async function readJsonLinesGz(path) {
    const file = await Deno.open(path, { read: true });
    const text = await new Response(file.readable.pipeThrough(new DecompressionStream('gzip'))).text();
    const out = [];
    for (const line of text.split('\n')) if (line) out.push(JSON.parse(line));
    return out;
}

export const readJson = (path, dflt = null) => {
    try {
        return JSON.parse(Deno.readTextFileSync(path));
    } catch (_e) {
        return dflt;
    }
};

/** Write a test's result to tests/out/parity/<name>.json and return its exit code. */
export function finish(T, name, extra = {}) {
    Object.assign(T.extra, extra);
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(`${W.out('parity')}/${name}.json`, JSON.stringify(res, null, 1));
    return code;
}

export const sci = (x, d = 3) => (Number.isFinite(x) ? Number(x).toExponential(d) : String(x));
