// Shared by the mesh and API package's tests (PORT_PLAN.md section 8.2, P4): where things are, the fixtures, the
// result file. The checks are the runner package's (tests/core_runner/_common.mjs), the JSON comparisons the
// core-inputs package's (tests/core_inputs/_common.mjs), the lookups of everything outside this repository the
// parity package's tests/_where.mjs: reused.
//
// Paths are found from this file (import.meta.url) and from the environment, never from a machine:
//     the package             ../../                      (eidoverse/terrain/)
//     outputs                 ../out/mesh_api/            (git-ignored; made on first use)
//     mesh fixtures           ../out/mesh_api/fixtures/<case>/      (mesh_expected.py, with Blender's Python)
//     API fixtures            ../out/mesh_api/api_fixtures/<case>/  (api_expected.py, with Blender's Python)
//     the Blender edition     blender/ beside eidoverse/, else $EIDO_BLENDER_EDITION (the saves the fixtures name
//                             are read there; the DEMs too, unless $EIDO_TERRAIN_DEMS): tests/_where.mjs

import { Checks, bitsEqual, dirUrl, lcg } from '../core_runner/_common.mjs';
import { sameJson, jsonDiff } from '../core_inputs/_common.mjs';
import * as W from '../_where.mjs';

export { Checks, bitsEqual, dirUrl, lcg, sameJson, jsonDiff, W };
export const blenderEdition = W.blenderEdition;
export const TERRAIN = new URL('../../', import.meta.url);
export const OUT = new URL('../out/mesh_api/', import.meta.url);
export const FIXTURES = new URL('fixtures/', OUT);
export const API_FIXTURES = new URL('api_fixtures/', OUT);
export const urlPath = W.urlPath;

export function outUrl(name) {
    Deno.mkdirSync(new URL('.', new URL(name, OUT)), { recursive: true });
    return new URL(name, OUT);
}

const HOW = {
    [FIXTURES.href]: 'mesh_expected.py',
    [API_FIXTURES.href]: 'api_expected.py',
};

/** The fixture cases present in a fixture folder (folder names with a manifest), or null with how to make them. */
export function fixtureCases(want = null, base = FIXTURES) {
    const out = [];
    try {
        for (const e of Deno.readDirSync(base)) {
            if (!e.isDirectory) continue;
            try {
                Deno.statSync(new URL(`${e.name}/manifest.json`, base));
                if (!want || want.includes(e.name)) out.push(e.name);
            } catch (_e) { /* not a case */ }
        }
    } catch (_e) { /* no folder */ }
    out.sort();
    if (!out.length) {
        const script = HOW[base.href] ?? 'mesh_expected.py';
        console.log(`SKIP: no fixtures${want ? ` named ${want.join(', ')}` : ''} in ${urlPath(base)}. Make them with Blender's Python:\n` +
            `    <blender>/<version>/python/bin/python -I -B eidoverse/terrain/tests/mesh_api/${script}\n` +
            '(the Blender edition is found beside eidoverse/ or at $EIDO_BLENDER_EDITION)');
        return null;
    }
    return out;
}

export function manifest(name, base = FIXTURES) {
    return JSON.parse(Deno.readTextFileSync(new URL(`${name}/manifest.json`, base)));
}

const TYPED = { f32: Float32Array, f64: Float64Array, i32: Int32Array, u32: Uint32Array };

/** A fixture array (typed, flat) by its manifest name. */
export function arr(name, man, key, base = FIXTURES) {
    const a = man.arrays[key];
    if (!a) throw new Error(`fixture ${name}: no array '${key}'`);
    const bytes = Deno.readFileSync(new URL(`${name}/${a.file}`, base));
    const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    return new TYPED[a.dtype](buf);
}

export const has = (man, key) => Object.prototype.hasOwnProperty.call(man.arrays, key);

/** A path below the Blender edition's root, or null when there is none. */
export function blenderPath(rel) {
    const root = blenderEdition();
    return root ? `${root}/${rel}` : null;
}

/** Write T's rows to out/mesh_api/<file> and return the exit code. */
export function finish(T, file) {
    const code = T.done(null);
    const failed = T.rows.filter((r) => !r.passed);
    const res = { test: T.title, deno: Deno.version.deno, date: new Date().toISOString(),
        seconds: +((performance.now() - T.t0) / 1000).toFixed(2), checks: T.rows.length,
        failed: failed.map((r) => r.check), ...T.extra, rows: T.rows };
    Deno.writeTextFileSync(outUrl(file), JSON.stringify(res, null, 1));
    return code;
}

const F1 = new Float32Array(1), U1 = new Uint32Array(F1.buffer);

/** ulp of a float32 magnitude: the spacing of float32 numbers above |v| (np.spacing of a float32). */
export function ulp32(v) {
    F1[0] = Math.abs(v);
    const e = (U1[0] >>> 23) & 0xFF;
    return e === 0 ? 2 ** -149 : 2 ** (e - 150);
}

/** The angle between two 3-vectors, radians (atan2 form: accurate near 0). */
export function angle(a, b) {
    const cx = a[1] * b[2] - a[2] * b[1], cy = a[2] * b[0] - a[0] * b[2], cz = a[0] * b[1] - a[1] * b[0];
    return Math.atan2(Math.hypot(cx, cy, cz), a[0] * b[0] + a[1] * b[1] + a[2] * b[2]);
}

export function percentile(values, q) {
    const a = Float64Array.from(values).sort();
    if (!a.length) return NaN;
    const pos = (a.length - 1) * q / 100, lo = Math.floor(pos), hi = Math.ceil(pos);
    return a[lo] + (a[hi] - a[lo]) * (pos - lo);
}

/** The SHA-1 of a file, streamed (hex). */
export async function sha1File(path) {
    const { createHash } = await import('node:crypto');
    const h = createHash('sha1');
    const f = await Deno.open(path, { read: true });
    try {
        const buf = new Uint8Array(1 << 22);
        for (;;) {
            const n = await f.read(buf);
            if (n === null) break;
            h.update(buf.subarray(0, n));
        }
    } finally {
        f.close();
    }
    return h.digest('hex');
}

/** Whether an async call throws an error whose message holds every one of `parts` (and whose name is `kind`, when
 * given): { ok, message }. */
export async function throwsWith(fn, parts, kind = null) {
    try {
        await fn();
    } catch (e) {
        const msg = String(e?.message ?? e);
        const ok = parts.every((p) => msg.includes(p)) && (kind === null || e?.name === kind);
        return { ok, message: `${e?.name}: ${msg}` };
    }
    return { ok: false, message: 'nothing was thrown' };
}
