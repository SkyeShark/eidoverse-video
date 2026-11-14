// Shared by the core-inputs package's tests (PORT_PLAN.md section 8.2, P2): where things are, the checks, the
// fixtures. The checks and the binary loader are the runner package's (tests/core_runner/_common.mjs), reused.
//
// Paths are found from this file (import.meta.url) and from the environment, never from a machine:
//     the package             ../../            (eidoverse/terrain/)
//     outputs                 ../out/core_inputs/   (git-ignored; made on first use)
//     fixtures                ../out/core_inputs/fixtures_<numpy version>/ (core_inputs_expected.py makes them
//                             with Blender's Python), or the folder given as the first argument
//     scratch                 $EIDO_TEST_SCRATCH, else the system's temporary folder (Deno.makeTempDir): large
//                             files (npz saves) never go into the checkout
// tests/_where.mjs (the parity package's) will own these lookups for the whole port; until it exists this file is
// the core-inputs package's own.

import { Checks, bitsEqual, dirUrl, loadBin as loadBin32, lcg } from '../core_runner/_common.mjs';

export { Checks, bitsEqual, dirUrl, lcg };
export const TERRAIN = new URL('../../', import.meta.url);
export const OUT = new URL('../out/core_inputs/', import.meta.url);

export function outUrl(name) {
    Deno.mkdirSync(OUT, { recursive: true });
    return new URL(name, OUT);
}

/** The fixture folder: the first argument, else the newest out/core_inputs/fixtures_*; null (and how to make it)
 * when there is none. */
export function fixtures(arg = Deno.args[0]) {
    if (arg && !arg.startsWith('--')) return dirUrl(arg);
    const found = [];
    try {
        for (const e of Deno.readDirSync(OUT)) if (e.isDirectory && e.name.startsWith('fixtures_')) found.push(e.name);
    } catch (_e) { /* none */ }
    found.sort();
    if (found.length) return new URL(found[found.length - 1] + '/', OUT);
    console.log('SKIP: no fixtures. Make them with Blender\'s Python:\n    <blender>/<version>/python/bin/python -I ' +
        'eidoverse/terrain/tests/core_inputs/core_inputs_expected.py\n(the Blender edition is found beside eidoverse/ or ' +
        'at $EIDO_BLENDER_EDITION)');
    return null;
}

export const manifest = (dir) => JSON.parse(Deno.readTextFileSync(new URL('manifest.json', dir)));

/** A fixture array: Float32Array, Float64Array, Float16Array, Uint8Array, Uint16Array, Uint32Array or Int32Array. */
export function loadBin(dir, a) {
    if (['f32', 'f64', 'u32', 'i32', 'i64'].includes(a.dtype)) return loadBin32(dir, a);
    const bytes = Deno.readFileSync(new URL(a.file, dir));
    const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    if (a.dtype === 'f16') return new Float16Array(buf);
    if (a.dtype === 'u16') return new Uint16Array(buf);
    if (a.dtype === 'u8') return new Uint8Array(buf);
    throw new Error(`loadBin: dtype ${a.dtype}`);
}

/** The Blender edition's root (a checkout of the blender branch): blender/ beside eidoverse/ in this checkout, else
 * $EIDO_BLENDER_EDITION; null when neither holds blender/eidoblend/terrain. A path with '/' separators. */
export function blenderEdition() {
    const here = decodeURIComponent(new URL('../../../../', import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1');
    for (const root of [here, Deno.env.get('EIDO_BLENDER_EDITION') ?? '']) {
        if (!root) continue;
        const r = root.replace(/\\/g, '/').replace(/\/+$/, '');
        try {
            if (Deno.statSync(`${r}/blender/eidoblend/terrain/core`).isDirectory) return r;
        } catch (_e) { /* not here */ }
    }
    return null;
}

/** A scratch folder for large files: $EIDO_TEST_SCRATCH, else a new temporary folder. */
export function scratch(prefix = 'eido_core_inputs_') {
    const env = Deno.env.get('EIDO_TEST_SCRATCH');
    if (env) {
        Deno.mkdirSync(env, { recursive: true });
        return env.replace(/\\/g, '/').replace(/\/+$/, '');
    }
    return Deno.makeTempDirSync({ prefix }).replace(/\\/g, '/');
}

/** Write T's rows to out/core_inputs/<file> (the runner package's result format) and return the exit code. */
export function finish(T, file) {
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(outUrl(file), JSON.stringify(res, null, 1));
    return code;
}

/** Deep equality of JSON-like values with exact numbers (Python's 2000.0 and 2000 are one number here). */
export function sameJson(a, b) {
    if (a === b) return true;
    if (typeof a === 'number' && typeof b === 'number') return Object.is(a, b) || (a === b) || (Number.isNaN(a) && Number.isNaN(b));
    if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => sameJson(x, b[i]));
    if (a && b && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) {
        const ka = Object.keys(a), kb = Object.keys(b);
        return ka.length === kb.length && ka.every((k) => Object.prototype.hasOwnProperty.call(b, k) && sameJson(a[k], b[k]));
    }
    return false;
}

/** The first difference of two JSON-like values, as a path and the two values (for a check's detail). */
export function jsonDiff(a, b, path = '') {
    if (sameJson(a, b)) return null;
    if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length) return `${path}: length ${a.length} vs ${b.length}`;
        for (let i = 0; i < a.length; i++) {
            const d = jsonDiff(a[i], b[i], `${path}[${i}]`);
            if (d) return d;
        }
    }
    if (a && b && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) {
        const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
        for (const k of keys) {
            const d = jsonDiff(a[k], b[k], `${path}.${k}`);
            if (d) return d;
        }
    }
    return `${path}: ${JSON.stringify(a)?.slice(0, 200)} vs ${JSON.stringify(b)?.slice(0, 200)}`;
}

/** 'Kind: message' of a thrown error, as the fixture scripts record Python's (KeyError's quotes taken off). */
export function errText(e) {
    return `${e.name === 'Error' ? 'Error' : e.name}: ${e.message}`;
}

export function pyErrText(s) {
    if (s === null || s === undefined) return s;
    const m = /^(\w+): ([\s\S]*)$/.exec(s);
    if (!m) return s;
    let msg = m[2];
    if (m[1] === 'KeyError' && /^(['"])[\s\S]*\1$/.test(msg)) {
        msg = msg.slice(1, -1).replace(/\\'/g, "'").replace(/\\"/g, '"').replace(/\\\\/g, '\\');
    }
    return `${m[1]}: ${msg}`;
}

/** Python's text with every float that prints as N.0 printed as N (JavaScript has one number type). */
export const intFloats = (s) => String(s).replace(/(\d)\.0(?![\d])/g, '$1');

/** Relative error grades: max |got - want| over a scale (the range of want, or 1 when that is 0), and where. */
export function maxErr(got, want, scale = null) {
    let lo = Infinity, hi = -Infinity, err = 0, at = -1;
    for (let i = 0; i < want.length; i++) {
        const w = want[i];
        if (w < lo) lo = w;
        if (w > hi) hi = w;
        const d = Math.abs(got[i] - w);
        if (!(d <= err)) {
            err = d;
            at = i;
        }
    }
    const range = hi - lo;
    const s = scale ?? (range > 0 ? range : Math.max(1, Math.abs(hi)));
    return { abs: err, rel: err / s, range, at, got: got[at], want: want[at] };
}

/** The largest error in units in the last place of float32 at the given magnitude (per element, or one scale). */
export function ulp32(x) {
    const a = Math.abs(Math.fround(x));
    if (a === 0) return 2 ** -149;
    const e = Math.floor(Math.log2(a));
    return 2 ** (Math.max(e, -126) - 23);
}
