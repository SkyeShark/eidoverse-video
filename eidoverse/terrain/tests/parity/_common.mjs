// What the parity package's Deno tools share (PORT_PLAN.md 5): reading the fixtures and dumps the Blender edition
// made (tests/parity/fixtures.py, blender_chaos_floor.py, blender_stage_dump.py), the grades of plan 5.3 as
// functions, and the result files. Paths come from tests/_where.mjs.
//
//     import * as C from './_common.mjs';
//     const fx = C.loadFixture('functions/metrics');     // { dir, manifest } or null (says how to make it)
//     const a = C.array(fx.dir, case.inputs.h);          // a typed array (f32, f64, i32, i64 as BigInt64, u32, u8)
//     C.grade(got, want, { k: 1e-6, range, uses: ['sqrt', 'atan'] })     // a float grade: { ok, err, tol }
//     C.gradeArray(got, want, { k: 1e-4, uses: ['pow'] })                // a channel: { ok, err, tol, range, at }
//     const r = await C.kernelCases(R, 'route_incise', { uses: ['pow'] });   // every fixture case of a kernel, graded
//     const T = new C.Checks('parity/metrics');  ...  Deno.exit(C.finish(T, 'metrics_test'));
//
// EVERY FLOAT GRADE is max(k x range, m x ulp(|value|), abs) (the lead's rule on the plan's 5.3). k x range is the
// plan's tolerance for the grade (1e-4 of a channel's range for a kernel, 1e-5 for a float function, 1e-6 for a
// number). m x ulp is the rounding the function's built-ins can leave on a correct port: M below, from what this
// GPU's built-ins were measured to do (plan 2.3; tests/parity/grade_test.mjs measures them again), so a correct port
// never fails a grade on rounding alone: where a channel's range is tiny beside its values (a nearly flat field far
// from zero) k x range alone is below one float32 step. `abs` is the absolute bound of the two built-ins whose error
// is not relative: log where its result is near 0 (its argument near 1) and tan where its result is near 0. A grade
// names the built-ins it leans on (`uses`) and takes the largest m and abs among them; plain arithmetic is always
// counted. ulp is float32's at the value unless the quantity is computed in doubles (`double`).

import * as W from '../_where.mjs';
import { Checks } from '../core_runner/_common.mjs';

export { Checks, W };

/** The float32 steps a correct port may be off by, per built-in a function uses, each with headroom over what this
 * GPU's built-ins were measured to do against the correctly rounded value (plan 2.3, and again by
 * tests/parity/grade_test.mjs, 65,536 samples each): sqrt 1; division, atan and atan2 2; exp 15; pow 67-69; log 5
 * and tan 83 at the 99th percentile. log, tan, sin and cos also have an error that is absolute, not relative (ABS). */
export const M = Object.freeze({ arithmetic: 4, divide: 4, sqrt: 4, atan: 4, atan2: 4, sin: 8, cos: 8, exp: 32, log: 16,
    pow: 80, tan: 160 });

const STEP1 = 2 ** -23;                                  // one float32 step at 1.0

/** The absolute error of the built-ins whose error is not relative where their result is near 0 (measured, in
 * float32 steps of 1.0): log(x) near x = 1: 0.9 (millions of steps of its own near-zero result); tan(x) and
 * sin(x) for |x| < 0.1: 2.8. Arguments of sin and cos beyond 1 need trigAbs() instead: their error grows with the
 * argument. */
export const ABS = Object.freeze({ log: 4 * STEP1, tan: 8 * STEP1, sin: 8 * STEP1, cos: 8 * STEP1 });

/** The absolute error allowed to sin(x) and cos(x) for arguments up to |x| = maxArg: this GPU's are off by about
 * |x| x 2^-23 (measured 2.4e-6 at |x| = 20: the argument's own rounding in the range reduction), so 4 x that, never
 * below ABS.sin. Pass it as a grade's `abs` where a kernel takes the sine or cosine of a large angle. */
export const trigAbs = (maxArg) => 4 * STEP1 * Math.max(2, Math.abs(maxArg));

// the m and the absolute bound of a grade: its own, or the largest among the built-ins it names (arithmetic always)
function allowance(opts) {
    let m = opts.m ?? null, abs = opts.abs ?? 0;
    if (opts.uses) {
        m = Math.max(m ?? 0, M.arithmetic);
        for (const u of opts.uses) {
            if (!(u in M)) throw new Error(`grade: no measured error for the built-in '${u}' (known: ${Object.keys(M).join(', ')})`);
            m = Math.max(m, M[u]);
            abs = Math.max(abs, ABS[u] ?? 0);
        }
    }
    return { m: m ?? 0, abs };
}

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

/** A float grade (see the top): opts { k, range (default |want|), uses (the built-ins leaned on: M and ABS), m and
 * abs (given outright; the larger of these and `uses` counts), double (ulp of float64), scale (the value whose ulp
 * counts when the result is a difference or a ratio of larger numbers: default |want|) }. { ok, err, tol }. */
export function grade(got, want, opts = {}) {
    const ulp = opts.double ? ulp64 : ulp32;
    const { m, abs } = allowance(opts);
    const tol = Math.max((opts.k ?? 0) * (opts.range ?? Math.abs(want)), m * ulp(opts.scale ?? want), abs);
    const err = Math.abs(got - want);
    const same = got === want || (Number.isNaN(got) && Number.isNaN(want));
    return { ok: same || err <= tol, err: same ? 0 : err, tol };
}

/** Two arrays graded as a channel: max |got - want| against max(k x the want's range, m x ulp of its largest
 * |value|, abs). { ok, err, tol, range, amax, at, over (err / range), nonFinite } (plan 5.3's kernel and function
 * grades: Blender's twins.compare with the rounding floor). opts as grade(), and stride / offset to grade one
 * channel of an interleaved (H, W, C) array (stride C, offset the channel); scale: the largest |input| when the
 * channel is a difference of larger inputs (default: the channel's own largest |value|). */
export function gradeArray(got, want, opts = {}) {
    const stride = opts.stride ?? 1, offset = opts.offset ?? 0;
    let lo = Infinity, hi = -Infinity, amax = 0, err = 0, at = -1, bad = 0;
    for (let i = offset; i < want.length; i += stride) {
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
    const { m, abs } = allowance(opts);
    const span = Math.max(range, 1e-6 * amax, 1e-20);       // twins.compare's own floor for a flat channel
    const tol = Math.max((opts.k ?? 0) * span, m * ulp(Math.max(amax, opts.scale ?? 0)), abs);
    return { ok: bad === 0 && got.length === want.length && err <= tol, err, tol, range, amax, at, over: err / span,
        nonFinite: bad };
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

/** Every case of one Blender kernel in the kernel fixtures (tests/parity/fixtures.py --kernels: the Blender tests' own
 * parity cases, run through the numpy twins) dispatched once through the runner R and graded per output channel:
 * plan 5.3's kernel grade, max |gpu - twin| <= max(1e-4 x the channel's range, m x ulp, abs).
 *
 *     const r = await C.kernelCases(R, 'route_incise', { uses: ['pow'] });
 *     T.ok(`route_incise: ${r.n} cases within 1e-4 of range`, r.ok, r.detail);
 *
 * opts: kernel (the runner's kernel when it is not R.kernel(name): a handle, or a function of the case for a kernel
 *       with variants: an inline source, defines, one source per ray count), uses / m / abs (the grade's rounding
 *       allowance: the built-ins the kernel leans on), k (1e-4), exact ({ image: [channels] } compared bit for bit:
 *       hash decisions, integer counts held as floats), filter (a function of the case), fixture (a loaded one).
 * Returns null without the fixtures (a line says how to make them), else { kernel, n, ok, worst (the largest
 * max |d| / range), failed: [labels], detail (one line), cases: [{ label, ok, worst, channels: [{ image, channel,
 * ok, err, tol, range, over, exact }] }] }. A case's `channels` entry (the Blender test compares only some channels
 * of an image) is honoured. JavaScript per cell (a test). */
export async function kernelCases(R, name, opts = {}) {
    const fx = opts.fixture ?? loadFixture('kernels');
    if (!fx) return null;
    const cases = fx.manifest.cases.filter((c) => c.kernel === name && (!opts.filter || opts.filter(c)));
    const out = { kernel: name, n: cases.length, ok: cases.length > 0, worst: 0, failed: [], cases: [] };
    let handle = null;
    for (const c of cases) {
        const kern = typeof opts.kernel === 'function' ? opts.kernel(c) : (opts.kernel ?? (handle ??= R.kernel(name)));
        const samplers = {}, images = {};
        for (const [s, a] of Object.entries(c.inputs)) samplers[s] = R.field(a.shape[0], a.shape[1], a.shape[2], array(fx.dir, a));
        for (const [im, a] of Object.entries(c.outputs)) images[im] = R.field(a.shape[0], a.shape[1], a.shape[2]);
        R.run(kern, samplers, images, c.uniforms);
        const names = Object.keys(c.outputs);
        const got = await R.readAll(names.map((n) => images[n]));
        const row = { label: c.label, ok: true, worst: 0, channels: [] };
        names.forEach((im, idx) => {
            const a = c.outputs[im], want = array(fx.dir, a), nch = a.shape[2];
            const only = c.channels?.[im] ?? null, exact = opts.exact?.[im] ?? [];
            for (let ch = 0; ch < nch; ch++) {
                if (only && !only.includes(ch)) continue;
                const isExact = exact.includes(ch);
                const g = gradeArray(got[idx], want, { k: isExact ? 0 : (opts.k ?? 1e-4), uses: isExact ? undefined : (opts.uses ?? []),
                    m: isExact ? 0 : opts.m, abs: isExact ? 0 : opts.abs, stride: nch, offset: ch });
                row.channels.push({ image: im, channel: ch, ok: g.ok, err: g.err, tol: g.tol, range: g.range, over: g.over, exact: isExact });
                row.worst = Math.max(row.worst, g.over);
                if (!g.ok) row.ok = false;
            }
        });
        for (const f of [...Object.values(samplers), ...Object.values(images)]) f.destroy();
        out.cases.push(row);
        out.worst = Math.max(out.worst, row.worst);
        if (!row.ok) { out.ok = false; out.failed.push(c.label); }
    }
    out.detail = cases.length ? `worst ${sci(out.worst)} of range` + (out.failed.length ? `; failed: ${out.failed.slice(0, 6).join(', ')}` : '')
        : `no case of ${name} in the kernel fixtures`;
    return out;
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
