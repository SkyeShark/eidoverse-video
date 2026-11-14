// Port of blender/eidoblend/terrain/core/cache.py at f90c6fc (and api.py's _code_hash, the terrain hash).
//
// The terrain cache (design section 2.6).
//
//     const key = makeKey(recipe, knobs, size, resolution, seed, plan, focus);   // SHA-1 hex
//     const c = new Cache(key);            // eidoverse/assets/cache/terrain_threejs/<key>/ (git-ignored), or
//                                          // $EIDO_TERRAIN_THREEJS_CACHE/<key>/
//     if (c.complete()) {                  // meta.json written last: present = every level file is there
//         const fields = await c.loadLevel(i, level, R);
//     } else { ... run ...; await c.saveLevel(i, arrays); ...; c.writeMeta({ ... }); }
//     await prune({ keepGb: 20 });         // drop least recently used entries beyond a size;  clear()
//
// The key hashes the recipe dict, the resolved knob values, size, resolution, seed, the level plan, the focus,
// TERRAIN_CODE_VERSION, and the bytes of the code that makes the fields (PORT_PLAN.md C8, the split Blender makes):
//     the field hash (codeHash, cache.py code_hash): core/*.js, kernels/*.wgsl, the solver kernels
//         kernels/{prims,grid,compose,hydro,volcanic,impact,strata,karst,glacial,detail}/*.wgsl, solvers/*.js,
//         run.js; each file's path relative to the package and its bytes
//     the terrain hash (terrainCodeHash, api.py _code_hash, which api.js adds to its key's extra): recipes/*.js,
//         masks.js, kernels/masks/*.wgsl; their bytes
// build/, api.js, index.js, bake.mjs, surface/ and kernels/{mesh,water,metrics}/ never enter, so a mesh, API or
// material edit regenerates nothing; editing a kernel or an op invalidates old entries without anyone having to
// remember a bump. Bump TERRAIN_CODE_VERSION for what the sources cannot show (a driver or Deno change that alters
// results). GPU results are deterministic on one machine; across GPUs the last bits can differ, so the cache is
// per machine and tests compare metrics, not bytes.
//
// Level files are written to a temporary name and renamed into place, and meta.json last, so an interrupted run
// never leaves an entry that looks complete. An entry's size counts every file at its top level, so the files other
// layers keep in an entry (the plant spots, plants_<key>.plants.json and .f32; the surface bake's surface_*.npz when
// they sit there) are counted, pruned and cleared with it (C4).
//
// Where this differs from cache.py, and why:
//   - Its own root (terrain_threejs, $EIDO_TERRAIN_THREEJS_CACHE), apart from the Blender edition's terrain/ and
//     $EIDO_TERRAIN_CACHE, so neither edition's prune removes the other's entries (PORT_PLAN.md 3.2).
//   - The hashed files are sorted by their path relative to the package with '/' (Blender sorts absolute paths, whose
//     separator differs between systems); the key's JSON is JavaScript's (sorted keys, no spaces), not Python's: the
//     two editions' keys are never compared, only each one's own.
//   - prune takes { keepGb, base }; clear() empties the root (Cache.clear() one entry, as Blender's).
//   - saveLevel and loadLevel are async (npz through core/io.js); loadLevel uploads to the GPU when given a level and
//     a runner.

import { createHash } from 'node:crypto';
import { Fields } from './fields.js';
import { fieldFromArray, npArray, readNpz, writeNpz } from './io.js';

export const TERRAIN_CODE_VERSION = 1;
const TERRAIN_URL = new URL('../', import.meta.url);
export const FIELD_GLOBS = ['core/*.js', 'kernels/*.wgsl',
    'kernels/{prims,grid,compose,hydro,volcanic,impact,strata,karst,glacial,detail}/*.wgsl', 'solvers/*.js', 'run.js'];
export const TERRAIN_GLOBS = ['recipes/*.js', 'masks.js', 'kernels/masks/*.wgsl'];

/** A file URL as a path string ('/' separators; a drive letter without the leading slash). */
export function urlPath(u) {
    let p = decodeURIComponent(new URL(u).pathname);
    if (/^\/[A-Za-z]:/.test(p)) p = p.slice(1);
    return p.replace(/\/+$/, '');
}

export const TERRAIN_DIR = urlPath(TERRAIN_URL);
const join = (...parts) => parts.map((p, i) => (i ? String(p).replace(/^[\\/]+/, '') : String(p))).join('/').replace(/\\/g, '/')
    .replace(/\/{2,}/g, '/');

/** The cache folder: $EIDO_TERRAIN_THREEJS_CACHE, or <repo>/eidoverse/assets/cache/terrain_threejs. */
export function root() {
    return (Deno.env.get('EIDO_TERRAIN_THREEJS_CACHE') || urlPath(new URL('../../assets/cache/terrain_threejs/', import.meta.url)))
        .replace(/\\/g, '/').replace(/\/+$/, '');
}

// '{a,b}' alternatives, then '<dir>/<name>' with * in the name: the files that match, as paths relative to base
function expand(pattern, base) {
    const m = /\{([^}]*)\}/.exec(pattern);
    if (m) return m[1].split(',').flatMap((alt) => expand(pattern.slice(0, m.index) + alt + pattern.slice(m.index + m[0].length), base));
    const k = pattern.lastIndexOf('/');
    const dir = k >= 0 ? pattern.slice(0, k) : '';
    const name = k >= 0 ? pattern.slice(k + 1) : pattern;
    if (!name.includes('*')) {
        try {
            return Deno.statSync(join(base, pattern)).isFile ? [pattern] : [];
        } catch (_e) {
            return [];
        }
    }
    const re = new RegExp('^' + name.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '[^/]*').replace(/\?/g, '[^/]') + '$');
    const out = [];
    try {
        for (const e of Deno.readDirSync(join(base, dir || '.'))) {
            if (e.isFile && re.test(e.name)) out.push(dir ? `${dir}/${e.name}` : e.name);
        }
    } catch (_e) { /* no folder: no files */ }
    return out;
}

/** The files a hash covers: paths relative to the package, sorted. */
export function codeFiles(globs = FIELD_GLOBS, base = TERRAIN_DIR) {
    return [...new Set(globs.flatMap((g) => expand(g, base)))].sort();
}

/** The field hash: SHA-1 over the relative paths and bytes of the code that makes the fields (cache.py code_hash). */
export function codeHash(globs = FIELD_GLOBS, base = TERRAIN_DIR) {
    const h = createHash('sha1');
    for (const p of codeFiles(globs, base)) {
        h.update(new TextEncoder().encode(p));
        h.update(Deno.readFileSync(join(base, p)));
    }
    return h.digest('hex');
}

/** The terrain hash: SHA-1 over the bytes of the code outside the field hash that shapes a cached terrain, the
 * recipes and the masks (api.py _code_hash; api.js puts it in its key's extra). */
export function terrainCodeHash(globs = TERRAIN_GLOBS, base = TERRAIN_DIR) {
    const h = createHash('sha1');
    for (const p of codeFiles(globs, base)) h.update(Deno.readFileSync(join(base, p)));
    return h.digest('hex');
}

/** v as JSON data: objects with toDict() as their dicts, typed arrays as lists (cache.py _plain). */
export function plain(v) {
    if (v && typeof v.toDict === 'function') return v.toDict();
    if (ArrayBuffer.isView(v) && !(v instanceof DataView)) return Array.from(v, (x) => (typeof x === 'bigint' ? Number(x) : x));
    if (Array.isArray(v)) return v.map(plain);
    if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [String(k), plain(x)]));
    return v === undefined ? null : v;
}

/** JSON with sorted keys and no spaces (json.dumps(sort_keys=True, separators=(',', ':'), default=str)). */
export function sortedJson(v) {
    if (v === null || v === undefined) return 'null';
    if (typeof v === 'number' || typeof v === 'boolean') return JSON.stringify(v);
    if (typeof v === 'string') return JSON.stringify(v);
    if (Array.isArray(v)) return '[' + v.map(sortedJson).join(',') + ']';
    if (typeof v === 'object') {
        return '{' + Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${sortedJson(v[k])}`).join(',') + '}';
    }
    return JSON.stringify(String(v));
}

/** The cache key: SHA-1 hex of everything that decides the fields (see the module doc). `recipe` is a Recipe or its
 * dict, `plan` a list of Levels (or their dicts), `focus` points or null, `extra` any JSON-able settings the runner
 * adds (sea level, flatten areas, the terrain hash ...). */
export function makeKey(recipe, knobs, size, resolution, seed, plan, focus = null, extra = null) {
    const payload = { recipe: plain(recipe), knobs: plain(knobs ?? {}), size: Number(size), resolution: Math.trunc(resolution),
        seed: Math.trunc(seed), plan: plain(plan), focus: plain(focus), extra: plain(extra), version: TERRAIN_CODE_VERSION,
        code: codeHash() };
    return createHash('sha1').update(sortedJson(payload)).digest('hex');
}

function fileTime(path) {
    try {
        return Deno.statSync(path).mtime?.getTime() ?? 0;
    } catch (_e) {
        return null;
    }
}

const exists = (p) => fileTime(p) !== null;
const isFieldLike = (v) => v !== null && typeof v === 'object' && typeof v.h === 'number' && v.runner !== undefined && v.buffer !== undefined;

function stamp(d = new Date()) {
    const z = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())} ${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`;
}

/** One cache entry: <root>/<key>/level_<i>.npz and meta.json. */
export class Cache {
    constructor(key, base = null) {
        this.key = key;
        this.path = join(base ?? root(), key);
    }

    levelPath(i) { return join(this.path, `level_${Math.trunc(i)}.npz`); }
    get metaPath() { return join(this.path, 'meta.json'); }

    /** True when meta.json exists and every level file it lists is present. */
    complete() {
        const meta = this.readMeta();
        if (meta === null) return false;
        for (let i = 0; i < Math.trunc(meta.levels ?? 0); i++) if (!exists(this.levelPath(i))) return false;
        return true;
    }

    /** Write a level's arrays to level_<i>.npz, atomically: `arrays` maps names to arrays ({ dtype, shape, data },
     * core/io.js), GPU fields (read back as float32) or a Fields; `names` limits which. Uncompressed by default:
     * loading is the cache hit's budget (5 s). */
    async saveLevel(i, arrays, names = null, compress = false) {
        await Deno.mkdir(this.path, { recursive: true });
        const list = [];
        for (const k of Object.keys(arrays)) {
            if (names !== null && !names.includes(k)) continue;
            const v = arrays[k];
            list.push([k, isFieldLike(v) ? async () => npArray(await v.runner.read(v), [v.h, v.w]) : v]);
        }
        const tmp = this.levelPath(i) + '.tmp.npz';
        await writeNpz(tmp, list, { compress });
        await Deno.rename(tmp, this.levelPath(i));
        return this.levelPath(i);
    }

    /** The arrays of level i ({ name: { dtype, shape, data } }), or a Fields on `level` (uploaded with runner R) when
     * both are given. */
    async loadLevel(i, level = null, R = null) {
        const arrays = await readNpz(this.levelPath(i));
        if (level === null || R === null) return arrays;
        const f = new Fields(level, null, R);
        for (const [k, a] of Object.entries(arrays)) f.set(k, fieldFromArray(R, a));
        return f;
    }

    /** meta.json, written last: what makes the entry complete. Adds key, version, code hash and time. */
    writeMeta(meta) {
        Deno.mkdirSync(this.path, { recursive: true });
        const m = { ...plain(meta), key: this.key, version: TERRAIN_CODE_VERSION, code: codeHash(), written: stamp() };
        const tmp = this.metaPath + '.tmp';
        Deno.writeTextFileSync(tmp, JSON.stringify(m, null, 1));
        Deno.renameSync(tmp, this.metaPath);
        return m;
    }

    readMeta() {
        let m;
        try {
            m = JSON.parse(Deno.readTextFileSync(this.metaPath));
        } catch (_e) {
            return null;
        }
        try {
            const now = new Date();
            Deno.utimeSync(this.metaPath, now, now);     // a read counts as a use, for prune()
        } catch (_e) { /* read-only: fine */ }
        return m;
    }

    /** The bytes of every file at the entry's top level (the levels, meta.json, and what other layers keep there). */
    sizeBytes() {
        let n = 0;
        try {
            for (const e of Deno.readDirSync(this.path)) {
                if (!e.isFile) continue;
                try {
                    n += Deno.statSync(join(this.path, e.name)).size;
                } catch (_e) { /* gone meanwhile */ }
            }
        } catch (_e) { /* no folder */ }
        return n;
    }

    clear() {
        try {
            Deno.removeSync(this.path, { recursive: true });
        } catch (_e) { /* already gone */ }
    }
}

/** [{ time (last use, ms), bytes, cache }] of every entry, oldest first. */
export function entries(base = null) {
    const b = base ?? root();
    const out = [];
    let list;
    try {
        list = [...Deno.readDirSync(b)];
    } catch (_e) {
        return out;
    }
    for (const d of list) {
        if (!d.isDirectory) continue;
        const c = new Cache(d.name, b);
        const t = fileTime(c.metaPath) ?? fileTime(c.path) ?? 0;
        out.push({ time: t, bytes: c.sizeBytes(), cache: c });
    }
    return out.sort((x, y) => x.time - y.time);
}

/** Delete the least recently used entries until the cache holds at most keepGb. Returns the bytes freed. */
export function prune(opts = {}) {
    const { keepGb = 20.0, base = null } = opts;
    const es = entries(base);
    const total = es.reduce((s, e) => s + e.bytes, 0);
    let freed = 0;
    for (const e of es) {
        if (total - freed <= keepGb * 1e9) break;
        e.cache.clear();
        freed += e.bytes;
    }
    return freed;
}

/** Delete every entry. Returns the bytes freed. */
export function clear(opts = {}) {
    return prune({ ...opts, keepGb: -1 });
}

export { makeKey as make_key, codeHash as code_hash };
