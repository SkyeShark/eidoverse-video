// Shared by the mesh and API package's tests (PORT_PLAN.md section 8.2, P4): where things are, the fixtures, the
// result file. The checks are the runner package's (tests/core_runner/_common.mjs), the Blender edition's root the
// core-inputs package's lookup (tests/core_inputs/_common.mjs), reused.
//
// Paths are found from this file (import.meta.url) and from the environment, never from a machine:
//     the package             ../../                      (eidoverse/terrain/)
//     outputs                 ../out/mesh_api/            (git-ignored; made on first use)
//     fixtures                ../out/mesh_api/fixtures/<case>/  (mesh_expected.py makes them with Blender's Python)
//     the Blender edition     blender/ beside eidoverse/, else $EIDO_BLENDER_EDITION (the saves the fixtures name
//                             are read there; the DEMs too, unless $EIDO_TERRAIN_DEMS)
// tests/_where.mjs (the parity package's) will own these lookups for the whole port; until it exists this file is
// the mesh and API package's own.

import { Checks, bitsEqual, dirUrl, lcg } from '../core_runner/_common.mjs';
import { blenderEdition, sameJson, jsonDiff } from '../core_inputs/_common.mjs';

export { Checks, bitsEqual, dirUrl, lcg, blenderEdition, sameJson, jsonDiff };
export const TERRAIN = new URL('../../', import.meta.url);
export const OUT = new URL('../out/mesh_api/', import.meta.url);
export const FIXTURES = new URL('fixtures/', OUT);

export function outUrl(name) {
    Deno.mkdirSync(new URL('.', new URL(name, OUT)), { recursive: true });
    return new URL(name, OUT);
}

/** The fixture cases present (folder names with a manifest), or null with how to make them. */
export function fixtureCases(want = null) {
    const out = [];
    try {
        for (const e of Deno.readDirSync(FIXTURES)) {
            if (!e.isDirectory) continue;
            try {
                Deno.statSync(new URL(`${e.name}/manifest.json`, FIXTURES));
                if (!want || want.includes(e.name)) out.push(e.name);
            } catch (_e) { /* not a case */ }
        }
    } catch (_e) { /* no folder */ }
    out.sort();
    if (!out.length) {
        console.log("SKIP: no mesh fixtures. Make them with Blender's Python:\n    <blender>/<version>/python/bin/python -I -B " +
            'eidoverse/terrain/tests/mesh_api/mesh_expected.py\n(the Blender edition is found beside eidoverse/ or at ' +
            '$EIDO_BLENDER_EDITION)');
        return null;
    }
    return out;
}

export function manifest(name) {
    return JSON.parse(Deno.readTextFileSync(new URL(`${name}/manifest.json`, FIXTURES)));
}

const TYPED = { f32: Float32Array, f64: Float64Array, i32: Int32Array, u32: Uint32Array };

/** A fixture array (typed, flat) by its manifest name. */
export function arr(name, man, key) {
    const a = man.arrays[key];
    if (!a) throw new Error(`fixture ${name}: no array '${key}'`);
    const bytes = Deno.readFileSync(new URL(`${name}/${a.file}`, FIXTURES));
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
