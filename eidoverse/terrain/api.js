// Port of blender/eidoblend/terrain/api.py at f90c6fc.
//
// makeTerrain and the Terrain it returns (design section 8, PORT_PLAN.md section 7).
//
//     import { makeTerrain, Terrain } from './terrain/index.js';      // in a scene: await makeTerrain({ ... })
//     const t = await makeTerrain({ recipe: 'real_place', params: { dem: 'lauterbrunnen' }, focus: [480, -1640], seed: 1 });
//     scene.add(t.mesh);
//     const { mesh, heightAt, masks } = t;      // or the members below
//     t.heightAt(x, z)             // metres (three.js y) exactly on the rendered triangles (numbers or arrays)
//     t.normalAt(x, z)             // the shading normal there, three.js axes
//     t.mask('slope').at(x, z)     // any mask at world points, from the finest level holding them
//     t.viewpoint([0, 3000], 1500) // a standing point that sees the target (not a wall)
//     await t.preview('<dir>/name')   // hillshade and mask PNGs, to look at before a render
//     await t.save('<dir>/name')      // <name>.npz + .json: the Terrain.save format both editions read
//     const t2 = await Terrain.load('<dir>/name')    // a port save or a Blender save
//
// The call, in order (api.py's): the recipe (a name, a Recipe, a recipe dict or a list of stages) and its knobs are
// resolved and checked; the defaults come from the recipe, its DEM (real_place) and the quality; planLevels lays out
// the levels around the focus; the cache is read, or the level runner (run.js: runLevels) runs the stages and writes
// it; the exact flatten pass; the masks (masks.js); the ring mesh; then, for the scene, the mesh with the clay
// material, the collider proxy, the exact ray caster and the lake and sea surfaces. One summary line is logged,
// naming any stage whose op is not registered (the runner skips it).
//
// Frames (PORT_PLAN.md 2.2). Everything a scene touches is three.js's: +Y up, X east, Z south. A ground point is
// [x, z]; a three.js position is [x, y, z] (or a Vector3, or an Object3D's world position). Everything the
// generator holds is Blender's (x east, y north, z up; arrays [row j, column i], row 0 south): t.levels,
// t.fields(level), mask.array(level), t.info and the saved files. The two meet as (X, Y, Z) = (x, z, -y): only
// this module, build/mesh.js, build/water.js and build/collider.js convert.
//
// Where this differs from api.py, and why:
//   - makeTerrain is async (GPU readbacks and files are) and takes one options object in the edition's camelCase:
//     heroCell, seaLevel, baseElevationM, meshRes (PORT_PLAN.md 7.1); knob names stay Blender's (recipes are shared
//     JSON). `collection` (Blender) has no counterpart; `renderer` (optional) names the device.
//   - Arrays stay where they are until asked for: a loaded or cached terrain reads h (and water) of every level for
//     the mesh, and each other field or mask from its file the first time it is asked for (api.py loads every array
//     at once: 0.8 GB for a film terrain, which is the whole budget of a cache hit here). t.fields(level) and
//     mask.array(level) are still plain synchronous calls.
//   - Masks keep the dtype the cache stores (float16 for the bounded ones) until asked for; mask.array(level) gives
//     float32, as api.py's load does.
//   - The exact flatten pass runs on the GPU (kernels/mesh/flatten_fields.wgsl): numpy's float64 decides the cells
//     inside each area and the cells its falloff reaches (per-row tables made in doubles), so the ground inside is
//     the area's height to the bit and the ground beyond the falloff is untouched to the bit; the blend between is
//     float32 where numpy's is float64 rounded once.
//   - The mesh carries no mask attributes and one geometry group per ring (build/mesh.js; PORT_PLAN.md C4): its
//     material is the array [near, far], every ring on the near slot until the surfacing module names the far
//     rings from the cameras (as Blender's apply_surface does). `meshMasks: [names]` (a debug option, 7.3) adds up
//     to eight masks as the point attributes api.py always writes, eido_<mask>, and eido_level.
//   - `surface` and `plants` (SURFACING_DESIGN.md 5.3) are accepted and reserved: until the surfacing wave is
//     ported 'auto' resolves to none, like `palette: 'auto'` gives the grey clay, with one notice. t.plants holds
//     the spots a save carries (Terrain.load reads <base>.plants.json and its .f32 files, save writes them back).
//   - Terrain.save also writes <name>_parity.json (the edition, the commit, the code hashes, the GPU, the Deno
//     version, the date: PORT_PLAN.md 5.2).
//   - terrain_height_at (heightAt from a reopened .blend) has no counterpart: a scene keeps its Terrain, and
//     Terrain.load rebuilds one from a save.
//   - run.js (the level runner), masks.js and core/metrics.js belong to other packages of the port. Until each is in
//     the checkout, what needs it says so by name: a terrain can then be loaded or read from the cache, not generated.
//   - resolveCall(opts) has no counterpart: generate's first half (the recipe, the knobs, the defaults, the level
//     plan, the cache key) as a function of its own, which generate calls, so a tool or a test can find a call's
//     cache entry without running the call.

import { crc32, inflateRawSync } from 'node:zlib';
import * as registry from './recipes/index.js';
import * as Mesh from './build/mesh.js';
import * as Water from './build/water.js';
import * as Collider from './build/collider.js';
import * as Lv from './core/levels.js';
import { KeyError, ValueError, closeMatches, pyFormat, pyRound, pyReprValue } from './core/levels.js';
import * as G from './core/gpu.js';
import * as Ch from './core/cache.js';
import * as Io from './core/io.js';
import { sampleBilinear } from './core/grid.js';
import { prims } from './core/prims.js';

export const API_VERSION = 1;
export const ARGS = ['recipe', 'size', 'resolution', 'seed', 'params', 'focus', 'heroCell', 'context', 'flatten',
    'seaLevel', 'baseElevationM', 'palette', 'dress', 'surface', 'plants', 'quality', 'cache', 'name', 'meshRes',
    'meshMasks', 'renderer', 'log'];
// the old makeTerrain's options (eidoverse/terrain.js, a value-noise plane), and what took each one's place
const OLD_ARGS = { segments: 'resolution', amplitude: 'params', layers: 'palette', flatRadius: 'flatten',
    flatHeight: 'flatten', slopeSteep: 'palette', highStart: 'palette', octaves: 'recipe', frequency: 'recipe' };
const HERE = new URL('./', import.meta.url);
const now = () => performance.now() / 1000;
const round2 = (s) => Math.round(s * 100) / 100;

function nearest(name, options) {
    const opts = [...options];
    const near = closeMatches(String(name), opts, 3, 0.4);
    return near.length ? `; nearest: ${near.join(', ')}` : `; valid: ${[...opts].sort().join(', ')}`;
}

/** A module of the port that another package owns, or null while it is not in the checkout. */
async function optionalModule(rel) {
    const url = new URL(rel, HERE);
    try {
        Deno.statSync(url);
    } catch (_e) {
        return null;
    }
    return await import(url.href);
}

class NotPortedError extends Error {
    constructor(message) {
        super(message);
        this.name = 'NotPortedError';
    }
}

let THREE_NS = null;

/** three.js as the scene has it (globalThis.THREE: three/webgpu and three/tsl merged, eidoverse/render_common.mjs),
 * else the two modules merged here. */
export async function three(given = null) {
    if (given) return given;
    const g = globalThis.THREE;
    if (g?.MeshPhysicalNodeMaterial && g?.attribute) return g;
    if (!THREE_NS) {
        const [a, b] = await Promise.all([import('three/webgpu'), import('three/tsl')]);
        THREE_NS = { ...a, ...b };
    }
    return THREE_NS;
}


// ------------------------------------------------------------------------------------------------ frames ---

const isObject3D = (v) => v !== null && typeof v === 'object' && v.isObject3D === true;
const isVector = (v) => v !== null && typeof v === 'object' && (v.isVector3 === true || v.isVector2 === true);

// one focus item as a Blender ground point [x, y]: [x, z], a three.js position [x, y, z], a Vector2 (x, z), a
// Vector3 or an Object3D (its world position)
function groundPoint(v, what) {
    if (isObject3D(v)) {
        v.updateWorldMatrix(true, false);
        const e = v.matrixWorld.elements;
        return [e[12], -e[14]];
    }
    if (isVector(v)) return v.isVector3 ? [v.x, -v.z] : [v.x, -v.y];
    if (Array.isArray(v) && v.every((c) => typeof c === 'number')) {
        if (v.length === 2) return [v[0], -v[1]];
        if (v.length === 3) return [v[0], -v[2]];
    }
    throw new ValueError(`${what} must be [x, z] (or a three.js position [x, y, z]), a list of them, an Object3D (a ` +
        'camera) or a list of Object3Ds');
}

/** A focus in three.js terms as Blender ground points [[x, y], ...], or null. */
export function blenderFocus(focus) {
    if (focus === null || focus === undefined) return null;
    if (Array.isArray(focus) && !focus.every((c) => typeof c === 'number')) {
        if (!focus.length) throw new ValueError('focus: an empty list');
        return focus.map((f) => groundPoint(f, 'focus'));
    }
    return [groundPoint(focus, 'focus')];
}

const flatToThree = (s) => {
    const out = { at: [s.at[0], -s.at[1]] };
    for (const [k, v] of Object.entries(s)) {
        if (k === 'at') continue;
        out[k === 'angle_deg' ? 'angleDeg' : k] = v;
    }
    return out;
};


// --------------------------------------------------------------------------------------------- the arrays ---

function readFully(file, into, what) {
    let o = 0;
    while (o < into.length) {
        const n = file.readSync(into.subarray(o));
        if (n === null) throw new ValueError(`${what}: the file ends ${into.length - o} bytes early`);
        o += n;
    }
}

/** An npz on disk whose entries are read one at a time, synchronously, when asked for: the directory comes from
 * core/io.js (npzDirectory); an entry is read as np.load reads it (stored or deflated, its CRC-32 checked). */
export class NpzFile {
    constructor(path, directory) {
        this.path = path;
        this.names = directory.map((e) => e.name);
        this.entries = new Map(directory.map((e) => [e.name, e]));
    }

    static async open(path) {
        return new NpzFile(path, await Io.npzDirectory(path));
    }

    has(name) { return this.entries.has(name); }

    /** The array of an entry: { dtype, shape, data } (core/io.js's form). */
    read(name) {
        const e = this.entries.get(name);
        if (!e) throw new KeyError(`${this.path}: no array ${pyReprValue(name)}`);
        const file = Deno.openSync(this.path, { read: true });
        let raw;
        try {
            const lh = new Uint8Array(30);
            file.seekSync(e.offset, Deno.SeekMode.Start);
            readFully(file, lh, this.path);
            const v = new DataView(lh.buffer);
            if (v.getUint32(0, true) !== 0x04034b50) throw new ValueError(`${this.path}: no local header for ${e.file}`);
            file.seekSync(e.offset + 30 + v.getUint16(26, true) + v.getUint16(28, true), Deno.SeekMode.Start);
            raw = new Uint8Array(e.csize);
            readFully(file, raw, this.path);
        } finally {
            file.close();
        }
        if (e.method === 8) {
            const out = inflateRawSync(raw);
            raw = new Uint8Array(out.buffer, out.byteOffset, out.byteLength);
        } else if (e.method !== 0) {
            throw new ValueError(`${this.path}: entry ${e.file} uses zip method ${e.method}; stored (0) or deflated (8) are read`);
        }
        if ((crc32(raw) >>> 0) !== (e.crc >>> 0)) throw new ValueError(`${this.path}: Bad CRC-32 for file '${e.file}'`);
        const h = Io.parseNpyHeader(raw);
        if (h.fortran) throw new ValueError(`${this.path}: ${e.file} is a Fortran-order array; C order is needed`);
        const count = h.shape.reduce((a, b) => a * b, 1);
        const T = TYPED[h.dtype];
        if (!T) throw new ValueError(`${this.path}: ${e.file}: dtype ${h.dtype} is not one this reader takes`);
        const at = raw.byteOffset + h.offset;
        const data = at % T.BYTES_PER_ELEMENT === 0 ? new T(raw.buffer, at, count)
            : new T(raw.buffer.slice(at, at + count * T.BYTES_PER_ELEMENT));
        return { dtype: h.dtype, shape: h.shape, data };
    }
}

const TYPED = { '<f4': Float32Array, '<f8': Float64Array, '<f2': Float16Array, '|u1': Uint8Array, '|i1': Int8Array,
    '|b1': Uint8Array, '<u2': Uint16Array, '<i2': Int16Array, '<u4': Uint32Array, '<i4': Int32Array };

/** A level's named arrays (its fields, or its masks): each one loaded ({ dtype, shape, data }) or waiting in its
 * file until first asked for. Insertion order is kept: a save writes the arrays in it. */
export class Arrays {
    constructor(shape) {
        this.shape = shape;
        this._map = new Map();
    }

    /** Set an array: { dtype, shape, data }, or a typed array of the level's cells. */
    set(name, a) {
        if (ArrayBuffer.isView(a)) a = Io.npArray(a, this.shape);
        this._map.set(name, { array: a, load: null, f32: null });
    }

    /** Name an array that `load()` reads when it is first asked for. */
    lazy(name, load) { this._map.set(name, { array: null, load, f32: null }); }

    has(name) { return this._map.has(name); }
    names() { return [...this._map.keys()]; }
    loaded(name) { return this._map.get(name)?.array != null; }
    delete(name) { return this._map.delete(name); }

    /** The array as stored: { dtype, shape, data }. */
    get(name) {
        const e = this._map.get(name);
        if (!e) return undefined;
        if (e.array === null) {
            e.array = e.load();
            e.load = null;
        }
        return e.array;
    }

    /** The array as stored, without keeping it when it was still in its file (a save copies arrays through). */
    read(name) {
        const e = this._map.get(name);
        if (!e) return undefined;
        return e.array ?? e.load();
    }

    /** The array's values as a Float32Array (a float16 mask widened once and kept: exact). */
    f32(name) {
        const a = this.get(name);
        if (a === undefined) return undefined;
        if (a.data instanceof Float32Array) return a.data;
        const e = this._map.get(name);
        if (e.f32 === null) e.f32 = new Float32Array(a.data);
        return e.f32;
    }

    /** { name: Float32Array } whose members load when read (Object.keys lists them without loading). */
    view() {
        const out = {};
        for (const name of this._map.keys()) {
            Object.defineProperty(out, name, { enumerable: true, configurable: true, get: () => this.f32(name) });
        }
        return out;
    }
}


// ------------------------------------------------------------------------------------------------- masks ---

function levelIndex(plan, level) {
    if (typeof level === 'number' && Number.isInteger(level)) return ((level % plan.length) + plan.length) % plan.length;
    if (level instanceof Lv.Level) return Math.trunc(level.index);
    if (['main', 'context', 'hero', 'first', 'last'].includes(level)) {
        if (level === 'first') return 0;
        if (level === 'last') return plan.length - 1;
        const hit = plan.filter((lv) => lv.role === level).map((lv) => lv.index);
        if (!hit.length) throw new KeyError(`no ${level} level in this terrain (${Lv.pyStr(plan.map((lv) => lv.role))})`);
        return level !== 'context' ? hit[hit.length - 1] : hit[0];
    }
    throw new KeyError(`level ${pyReprValue(level)}: an index, a Level, or 'main' | 'context' | 'hero' | 'first' | 'last'`);
}

/** One mask over every level: .at(x, z) samples the finest level that holds each point (bilinear on its cell
 * centres), .array(level) is a level's n x n Float32Array (Blender frame: row 0 south), level by index or role. */
export class Mask {
    constructor(name, stack, plan) {
        this.name = name;
        this._stack = stack;
        this._plan = plan;
    }

    array(level = 'main') {
        const i = levelIndex(this._plan, level);
        const a = this._stack[i].f32(this.name);
        if (a === undefined) throw new KeyError(`mask ${pyReprValue(this.name)} was not made on level ${i} (${this._plan[i]})`);
        return a;
    }

    /** The mask at three.js ground points (x, z): a number for numbers, a Float64Array for arrays. */
    at(x, z) {
        const one = (px, pz) => {
            const py = -pz;
            for (let i = this._plan.length - 1; i >= 0; i--) {
                if (!this._stack[i].has(this.name)) continue;
                const lv = this._plan[i];
                if (i && !lv.contains(px, py)) continue;
                return sampleBilinear(this._stack[i].f32(this.name), lv.shape, lv.x0, lv.y0, lv.cell, px, py);
            }
            return 0.0;
        };
        if (typeof x === 'number' && typeof z === 'number') return one(x, z);
        const out = new Float64Array(x.length);
        for (let q = 0; q < x.length; q++) out[q] = one(x[q], z[q]);
        return out;
    }

    toString() { return `Mask(${pyReprValue(this.name)}, ${this._stack.filter((m) => m.has(this.name)).length} levels)`; }
}

/** Every mask of a terrain: t.masks.get('slope').at(x, z), .array(level), .names(). */
export class MaskSet {
    constructor(stack, plan) {
        this._stack = stack;
        this._plan = plan;
        this._names = [...new Set(stack.flatMap((m) => m.names()))].sort();
    }

    names() { return [...this._names]; }

    get(name) {
        if (!this._names.includes(name)) throw new KeyError(`no mask ${pyReprValue(name)}` + nearest(name, this._names));
        return new Mask(name, this._stack, this._plan);
    }

    has(name) { return this._names.includes(name); }
    [Symbol.iterator]() { return this._names[Symbol.iterator](); }
    get length() { return this._names.length; }

    /** The masks of one level: { name: Float32Array }, each read when first asked for. */
    level(level = 'main') { return this._stack[levelIndex(this._plan, level)].view(); }

    /** { level index: { mask: why } } for masks the masks package left out (an input field absent). */
    skipped() {
        const out = {};
        this._stack.forEach((m, i) => {
            if (m.skipped && Object.keys(m.skipped).length) out[i] = { ...m.skipped };
        });
        return out;
    }
}


// ---------------------------------------------------------------------------------------------- viewpoint ---

/** Set a three.js camera to a viewpoint: at the eye, looking at the target, level horizon; a perspective camera
 * takes the lens (Blender's 36 mm sensor width, so the framing is the Blender camera's). */
export function placeCamera(vp, camera, lensMm = null) {
    camera.position.set(vp.eye[0], vp.eye[1], vp.eye[2]);
    camera.up.set(0, 1, 0);
    camera.lookAt(vp.target[0], vp.target[1], vp.target[2]);
    if (camera.isPerspectiveCamera) {
        camera.filmGauge = 36;
        camera.setFocalLength(Number(lensMm ?? vp.lensMm));
    }
    camera.updateMatrixWorld(true);
    return camera;
}

// numpy's np.mod for doubles: the remainder with the divisor's sign
const npMod = (a, n) => {
    let r = a % n;
    if (r !== 0 && (r < 0) !== (n < 0)) r += n;
    return r;
};


// ------------------------------------------------------------------------------------------------- plants ---

export const PLANTS_FORMAT = 'eidoverse-terrain-plants/1';
const filePart = (name) => String(name).replace(/[^A-Za-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '') || 'species';

function stripExt(base) {
    base = String(base);
    for (const ext of ['.plants.json', '.json', '.npz']) if (base.endsWith(ext)) return base.slice(0, -ext.length);
    return base;
}

const dirOf = (p) => {
    const q = String(p).replace(/\\/g, '/');
    const k = q.lastIndexOf('/');
    return k < 0 ? '.' : q.slice(0, k) || '/';
};
const baseName = (p) => String(p).replace(/\\/g, '/').split('/').pop();

/** The plant spots a save carries (blender/eidoblend/terrain/build/plants.py PlantSpots at ebd8c8d, its files only:
 * SURFACING_DESIGN.md 4.5). Per species an n x stride Float32Array of records, FIELDS per spot, Blender frame:
 * x, y, z, yaw, scale, age, tint, nx, ny, nz, variant, level. The planner, the cover rasters and the instancer are
 * the surfacing wave's (build/plants.js); until then this holds what Terrain.load read, so a save keeps its spots. */
export class PlantSpots {
    constructor(meta, species, arrays) {
        this.meta = meta;
        this.species = species;
        this._arrays = arrays;                             // Map: species name -> Float32Array (count x stride)
        this.stats = Object.fromEntries(species.map((s) => [s.name, s.stats ?? {}]));
    }

    names() { return this.species.map((s) => s.name); }
    has(name) { return this._arrays.has(name); }

    entry(name) {
        const s = this.species.find((e) => e.name === name);
        if (!s) throw new KeyError(`no species ${pyReprValue(name)}; the plan has ${this.names().join(', ')}`);
        return s;
    }

    /** A species' records as saved: a Float32Array of count x stride numbers (stride = entry(name).fields.length). */
    array(name) {
        this.entry(name);
        return this._arrays.get(name);
    }

    count(name) { return this.array(name).length / this.entry(name).fields.length; }

    /** One field of a species' spots (a copy: a column of the records). */
    field(name, field) {
        const fields = this.entry(name).fields;
        const k = fields.indexOf(field);
        if (k < 0) throw new KeyError(`no field ${pyReprValue(field)}` + nearest(field, fields));
        const a = this.array(name), stride = fields.length, out = new Float32Array(a.length / stride);
        for (let i = 0; i < out.length; i++) out[i] = a[i * stride + k];
        return out;
    }

    cover(_level = 'main') {
        throw new NotPortedError('PlantSpots.cover: the cover rasters are the plant planner\'s (build/plants.js, the ' +
            'surfacing wave of the port, not in this checkout yet)');
    }

    /** Write <base>.plants.json and one <base>.plants.<species>.f32 per species (headerless little-endian float32).
     * Returns the paths written, the JSON first. */
    async save(base) {
        base = stripExt(base);
        const folder = dirOf(base), stem = baseName(base);
        await Deno.mkdir(folder, { recursive: true });
        const out = [], used = new Set(), entries = [];
        for (const s of this.species) {
            let part = filePart(s.name);
            while (used.has(part)) part += '_';
            used.add(part);
            const fn = `${stem}.plants.${part}.f32`;
            const a = this._arrays.get(s.name);
            const path = `${folder}/${fn}`;
            await Deno.writeFile(path + '.tmp', new Uint8Array(a.buffer, a.byteOffset, a.byteLength));
            await Deno.rename(path + '.tmp', path);
            out.push(path);
            entries.push({ ...s, count: a.length / s.fields.length, file: fn });
        }
        const jpath = `${base}.plants.json`;
        await Deno.writeTextFile(jpath + '.tmp', JSON.stringify({ ...this.meta, species: entries }, null, 1));
        await Deno.rename(jpath + '.tmp', jpath);
        return [jpath, ...out];
    }

    /** The spots save() wrote, here or in Blender. */
    static async load(base) {
        base = stripExt(base);
        const meta = JSON.parse(await Deno.readTextFile(`${base}.plants.json`));
        if (meta.format !== PLANTS_FORMAT) {
            throw new ValueError(`${base}.plants.json: format ${pyReprValue(meta.format ?? null)}, this reads ${pyReprValue(PLANTS_FORMAT)}`);
        }
        const species = meta.species;
        delete meta.species;
        const arrays = new Map();
        const folder = dirOf(base);
        for (const s of species) {
            const stride = s.fields.length;
            const bytes = await Deno.readFile(`${folder}/${s.file}`);
            if (bytes.length !== s.count * stride * 4) {
                throw new ValueError(`${s.file}: ${bytes.length / 4} numbers, the description says ${s.count} x ${stride}`);
            }
            arrays.set(s.name, new Float32Array(bytes.buffer, bytes.byteOffset, bytes.length / 4));
        }
        return new PlantSpots(meta, species, arrays);
    }

    toString() {
        return `PlantSpots(${this.meta.ecotope}: ` + this.species.map((s) => `${s.name} ${this.count(s.name)}`).join(', ') + ')';
    }
}


// ------------------------------------------------------------------------------------------------ terrain ---

// os.path.splitext(path)[0]
function splitext(path) {
    const p = String(path);
    const sep = Math.max(p.lastIndexOf('/'), p.lastIndexOf('\\'));
    const dot = p.lastIndexOf('.');
    if (dot <= sep) return p;
    let k = sep + 1;
    while (k < dot && p[k] === '.') k++;
    return k === dot ? p : p.slice(0, dot);
}

/** A made terrain (PORT_PLAN.md 7.2). `const { mesh, heightAt, masks } = t` works, and so does iterating it. */
export class Terrain {
    constructor(recipe, values, plan, fields, masks, ring, info, runner = null) {
        this.recipe = recipe;
        this.knobs = values;
        this.levels = plan;                              // Blender metres: each level's window, cell and role
        this._fields = fields;                           // per level, an Arrays
        this.masks = masks;
        this.ring = ring;                                // build/mesh.js RingMesh (Blender axes)
        this.info = info;                                // the record a save carries (Blender's names and frame)
        this.runner = runner;
        this.mesh = null;
        this.collider = null;
        this.water = { lakes: [], sea: null };
        this.rocks = null;
        this.surface = null;                             // the surface data (the surfacing wave)
        this.plants = null;                              // PlantSpots, when the save carried them
        this.loadedFrom = null;                          // the save it was loaded from
        this.loadSeconds = null;
        this._views = new Map();
        // bound, so `const { heightAt, normalAt } = t` and callbacks (heightFn: t.heightAt) work
        for (const k of ['heightAt', 'normalAt', 'mask', 'fields', 'viewpoint', 'metrics', 'preview', 'save', 'dispose']) {
            this[k] = this[k].bind(this);
        }
    }

    *[Symbol.iterator]() {
        yield this.mesh;
        yield this.heightAt;
        yield this.masks;
    }

    toString() {
        return `Terrain(${pyReprValue(this.recipe.name)}, ${this.levels.length} levels, ${this.ring.triangleCount.toLocaleString('en-US')} triangles` +
            (this.mesh ? `, mesh ${pyReprValue(this.mesh.name)}` : '') + ')';
    }

    /** The resolved flatten areas, three.js frame: { at: [x, z], radius | size + angleDeg, falloff, height, level }. */
    get flats() { return (this.info.flats ?? []).map(flatToThree); }

    // sampling ---------------------------------------------------------------------------------------------------

    /** Metres (three.js y) at three.js (x, z), exactly on the rendered triangles of the finest ring holding the point
     * (the mesh's float32 vertices; outside the outermost window, its edge). A number for numbers, a Float64Array
     * for arrays. */
    heightAt(x, z) {
        if (typeof x === 'number' && typeof z === 'number') return this.ring.heightAt(x, -z);
        const out = new Float64Array(x.length);
        for (let q = 0; q < out.length; q++) out[q] = this.ring.heightAt(x[q], -z[q]);
        return out;
    }

    /** The surface normal at three.js (x, z), three.js axes: the shading normal (smooth) or the triangle's.
     * [nx, ny, nz] for numbers, an array of them for arrays. */
    normalAt(x, z, smooth = true) {
        const one = (px, pz) => {
            const n = this.ring.normalAt(px, -pz, smooth);
            return [n[0], n[2], -n[1]];
        };
        if (typeof x === 'number' && typeof z === 'number') return one(x, z);
        return Array.from(x, (px, q) => one(px, z[q]));
    }

    mask(name) { return this.masks.get(name); }

    /** A level's raw arrays (h, bed, water, wear ...: { name: Float32Array }, Blender frame, row 0 south), level by
     * index or role; each is read when first asked for. */
    fields(level = 'main') {
        const i = levelIndex(this.levels, level);
        if (!this._views.has(i)) this._views.set(i, this._fields[i].view());
        return this._views.get(i);
    }

    get main() { return this.levels[levelIndex(this.levels, 'main')]; }

    /** The judge's generic numbers (core/metrics.js) of the main level, box-averaged to pixelM first if given. */
    async metrics(pixelM = null) {
        const Mt = await optionalModule('core/metrics.js');
        if (!Mt) {
            throw new NotPortedError('t.metrics(): core/metrics.js (the parity and judge package of the port) is not in ' +
                'this checkout yet; the Python judge reads a save: t.save(path)');
        }
        const R = await this._runner();
        const lv = this.main;
        const h = R.field(lv.n, lv.n, 1, this.fields('main').h);
        try {
            if (pixelM !== null && pixelM > lv.cell * (1 + 1e-9)) {
                const hp = await (Mt.toPixel ?? Mt.to_pixel)(h, lv.cell, pixelM);
                try {
                    return await Mt.metrics(hp, pixelM);
                } finally {
                    hp.destroy?.();
                }
            }
            return await Mt.metrics(h, lv.cell);
        } finally {
            h.destroy();
        }
    }

    async _runner() {
        this.runner = this.runner ?? await G.init();
        return this.runner;
    }

    // viewpoints --------------------------------------------------------------------------------------------------

    /** A standing point about `distance` metres from `target` (a ground point [x, z], or a three.js position
     * [x, y, z]) from which an eye eyeHeight above the ground sees the target: the sight line clears the terrain by
     * clearanceM all the way (so an eye-level camera does not face a wall), the footing is under maxSlopeDeg, inside
     * the `within` level. Candidates every 5 degrees around the target at 0.55-1.5 x the distance; the visible ones
     * are ranked by the heading asked for (compass degrees the camera looks toward: 0 north, 90 east), then prefer
     * 'low' (a valley floor) or 'high' (a rim), then the distance asked for. Returns { eye, target (three.js
     * positions), groundY, headingDeg, pitchDeg, distance, clearanceM, lensMm }; placeCamera(vp, camera) sets a
     * camera to it. Throws ValueError when no candidate sees the target. (api.py viewpoint, in its order.) */
    viewpoint(target, distance, opts = {}) {
        const bad = Object.keys(opts).find((k) => !VIEWPOINT_OPTS.includes(k));
        if (bad) throw new TypeError(`viewpoint() got an unexpected option ${pyReprValue(bad)}` + nearest(bad, VIEWPOINT_OPTS));
        const { eyeHeight = 1.7, heading = null, maxSlopeDeg = 30.0, lensMm = 35.0, lookDy = 0.0, prefer = null,
            clearanceM = 1.0, within = 'main' } = opts;
        const tp = isVector(target) ? (target.isVector3 ? [target.x, target.y, target.z] : [target.x, target.y]) : target;
        const tx = Number(tp[0]), ty = tp.length > 2 ? -Number(tp[2]) : -Number(tp[1]);     // Blender (x, y)
        const rm = this.ring;
        const tz = (tp.length > 2 ? Number(tp[1]) : rm.heightAt(tx, ty)) + lookDy;
        const lv = this.levels[levelIndex(this.levels, within)];
        const fac = [1.0, 0.85, 1.15, 0.7, 1.3, 0.55, 1.5];
        const dist0 = Number(distance);
        const px = [], py = [], A = [], D = [];
        for (const f of fac) {
            for (let a = 0; a < 72; a++) {
                const ang = (a * 5.0) * (Math.PI / 180.0);          // compass bearing from the target to the eye
                const d = f * dist0;
                const x = tx + d * Math.sin(ang), y = ty + d * Math.cos(ang);
                if (!lv.contains(x, y, 2 * lv.cell)) continue;
                px.push(x); py.push(y); A.push(ang); D.push(d);
            }
        }
        const n = px.length;
        if (!n) {
            throw new ValueError(`viewpoint: no point ${pyFormat(dist0, 'g')} m from (${pyFormat(tx, 'g')}, ${pyFormat(-ty, 'g')}) lies inside the ${within} level`);
        }
        const gz = new Float64Array(n), ez = new Float64Array(n), clear = new Float64Array(n);
        const good = new Uint8Array(n);
        const k = 160;
        let any = false, gmin = Infinity, gmax = -Infinity;
        for (let q = 0; q < n; q++) {
            gz[q] = rm.heightAt(px[q], py[q]);
            gmin = Math.min(gmin, gz[q]);
            gmax = Math.max(gmax, gz[q]);
            const nz = rm.normalAt(px[q], py[q], false)[2];
            const flat = Math.acos(Math.min(Math.max(nz, -1), 1)) * (180.0 / Math.PI) <= maxSlopeDeg;
            ez[q] = gz[q] + eyeHeight;
            const t0 = Math.min(3.0 / Math.max(D[q], 3.0), 0.5);     // from 3 m out (the eye clears its own feet)
            let c = Infinity;
            for (let s = 0; s < k; s++) {
                const t = t0 + (0.97 - t0) * (s === k - 1 ? 1.0 : s * (1.0 / (k - 1)));
                const lx = px[q] + (tx - px[q]) * t, ly = py[q] + (ty - py[q]) * t, lz = ez[q] + (tz - ez[q]) * t;
                c = Math.min(c, lz - rm.heightAt(lx, ly));
            }
            clear[q] = c;
            good[q] = flat && c >= clearanceM ? 1 : 0;
            any = any || good[q] === 1;
        }
        if (!any) {
            let best = 0;
            for (let q = 1; q < n; q++) if (clear[q] > clear[best]) best = q;
            throw new ValueError(`viewpoint: nothing ${pyFormat(dist0, 'g')} m around (${pyFormat(tx, 'g')}, ${pyFormat(-ty, 'g')}) sees it (best clearance ` +
                `${pyFormat(clear[best], '.1f')} m from (${pyFormat(px[best], '.0f')}, ${pyFormat(-py[best], '.0f')})): try another distance or lookDy`);
        }
        const ptp = Math.max(gmax - gmin, 1e-6);
        let b = -1, bestScore = -Infinity, bestHeading = 0;
        for (let q = 0; q < n; q++) {
            const look = npMod(A[q] * (180.0 / Math.PI) + 180.0, 360.0);     // the camera looks back toward the target
            let score = 0.0;
            if (heading !== null) score -= Math.abs(npMod(look - heading + 180.0, 360.0) - 180.0) / 10.0;
            if (prefer === 'low' || prefer === 'high') {
                const rel = (gz[q] - gmin) / ptp;
                score += (prefer === 'low' ? 1.0 - rel : rel) * 6.0;
            }
            score -= Math.abs(D[q] / dist0 - 1.0) * 4.0;
            score += Math.min(clear[q], 50.0) / 50.0;
            if (!good[q]) score = -Infinity;
            if (b < 0 || score > bestScore) {
                b = q;
                bestScore = score;
                bestHeading = look;
            }
        }
        const dist = Math.hypot(tx - px[b], ty - py[b]);
        const pitch = Math.atan2(tz - ez[b], dist) * (180.0 / Math.PI);
        return { eye: [px[b], ez[b], -py[b]], target: [tx, tz, -ty], groundY: gz[b], headingDeg: bestHeading,
            pitchDeg: pitch, distance: dist, clearanceM: clear[b], lensMm: Number(lensMm) };
    }

    // files ---------------------------------------------------------------------------------------------------------

    /** Hillshade and mask PNGs for a look before a render: <path>_main_hillshade.png (north up, the hero windows
     * outlined), <path>_hero_hillshade.png (the finest level), and <path>_mask_<name>.png (main level) for each mask
     * present. Returns the paths written. The per-texel work runs on the GPU (core/io.js; kernels/mesh/
     * preview_rgb.wgsl draws the outlines). */
    async preview(path, masks = ['slope', 'flow', 'rock', 'snow', 'vegetation', 'wetness', 'talus']) {
        const R = await this._runner();
        const P = prims(R);
        const out = [];
        await Deno.mkdir(dirOf(path), { recursive: true });
        const lv = this.main;
        const h = R.field(lv.n, lv.n, 1, this.fields('main').h);
        const hs = Io.hillshade(h, lv.cell);
        const grey = Io.toU8(hs);
        const rects = new Int32Array(4 * 16);
        let nr = 0;
        for (const c of this.levels.slice(lv.index + 1)) {     // the hero windows, outlined
            if (nr === 16) break;
            const i0 = pyRound((c.x0 - lv.x0) / lv.cell), j0 = pyRound((c.y0 - lv.y0) / lv.cell);
            const m = Math.max(pyRound(c.side / lv.cell), 1);
            rects.set([i0, j0, Math.min(i0 + m, lv.n - 1), Math.min(j0 + m, lv.n - 1)], 4 * nr++);
        }
        const rf = R.field(1, 64, 1, rects, 'i32');
        const rgb = R.field(lv.n, 3 * lv.n, 1, null, 'u32');
        R.run('mesh/preview_rgb', { grey, rects: rf }, { outC: rgb }, { uRects: nr, uColour: [255, 200, 40, 0] },
            [Math.ceil(lv.n / 16), Math.ceil(lv.n / 16), 1]);
        out.push(await Io.writePng(path + '_main_hillshade.png', { field: rgb, width: lv.n, height: lv.n, channels: 3, bitDepth: 8 }));
        for (const f of [h, hs, grey, rf, rgb]) f.destroy();
        const last = this.levels[this.levels.length - 1];
        if (last.role === 'hero') {
            const hf = R.field(last.n, last.n, 1, this.fields(last.index).h);
            const s = Io.hillshade(hf, last.cell);
            const q = Io.toU8(s, { flip: true });
            out.push(await Io.writePng(path + '_hero_hillshade.png', { field: q, width: last.n, height: last.n, channels: 1, bitDepth: 8 }));
            for (const f of [hf, s, q]) f.destroy();
        }
        for (const name of masks) {
            if (!this.masks.has(name) || !this.masks._stack[lv.index].has(name)) continue;
            const a = R.field(lv.n, lv.n, 1, this.masks.get(name).array('main'));
            const [lo, hi] = [await P.percentile(a, 1, { dtype: 'float64' }), await P.percentile(a, 99, { dtype: 'float64' })];
            const q = Io.quantise(a, lo, Math.max(hi - lo, 1e-9), 255, { flip: true });
            out.push(await Io.writePng(`${path}_mask_${name}.png`, { field: q, width: lv.n, height: lv.n, channels: 1, bitDepth: 8 }));
            a.destroy();
            q.destroy();
        }
        return out;
    }

    /** Write the terrain (every level's fields and masks, the plan, the recipe and knobs, the flats) to <path>.npz
     * with its description in <path>.json: the Terrain.save format, which Blender's Terrain.load reads too
     * (PORT_PLAN.md 5.2). Beside them <path>_parity.json, and the plant spots when the terrain has any. Returns the
     * .npz path. */
    async save(path) {
        const Mk = await optionalModule('masks.js');
        const list = [];
        this._fields.forEach((f, i) => {
            for (const k of f.names()) list.push([`L${i}__f__${k}`, () => f.read(k)]);
        });
        this.masks._stack.forEach((m, i) => {
            for (const k of m.names()) list.push([`L${i}__m__${k}`, () => cacheDtype(Mk, k, m.read(k))]);
        });
        const base = splitext(path);
        await Deno.mkdir(dirOf(base), { recursive: true });
        await Io.writeNpz(base + '.npz', list);
        const meta = { ...this.info, recipe: this.recipe.toDict(), knobs: this.knobs, plan: this.levels.map((lv) => lv.toDict()),
            api_version: API_VERSION };
        await Deno.writeTextFile(base + '.json', JSON.stringify(Ch.plain(meta), null, 1));
        const info = this.runner?.info ?? null;
        const parity = { edition: 'three.js', commit: gitCommit(), field_code_hash: Ch.codeHash(), terrain_code_hash: Ch.terrainCodeHash(),
            gpu: info ? [info.vendor, info.architecture, info.device, info.description].filter(Boolean).join(' / ') : null,
            deno: Deno.version.deno, v8: Deno.version.v8, date: new Date().toISOString(), api_version: API_VERSION,
            source: this.loadedFrom ? 'loaded from a save' : 'made by makeTerrain' };
        await Deno.writeTextFile(base + '_parity.json', JSON.stringify(parity, null, 1));
        if (this.plants) await this.plants.save(base);
        return base + '.npz';
    }

    /** A Terrain from save() (this edition's or Blender's). opts: build (true: also the mesh, the collider and the
     * water, as makeTerrain makes them), name, palette ('keep': the one it was made with), dress, renderer, log,
     * THREE, plants (the base path of plant spots saved elsewhere; false: none; default: the spots beside the
     * save, when it carries any). */
    static async load(path, opts = {}) {
        const bad = Object.keys(opts).find((k) => !LOAD_OPTS.includes(k));
        if (bad) throw new TypeError(`Terrain.load() got an unexpected option ${pyReprValue(bad)}` + nearest(bad, LOAD_OPTS));
        const { build = true, name = null, palette = 'keep', dress = false, renderer = null, log = console.log } = opts;
        const t0 = now();
        const base = splitext(path);
        const meta = JSON.parse(await Deno.readTextFile(base + '.json'));
        const plan = meta.plan.map((d) => Lv.Level.fromDict(d));
        const recipe = registry.resolve(meta.recipe);
        const npz = await NpzFile.open(base + '.npz');
        const fields = plan.map((lv) => new Arrays(lv.shape)), stack = plan.map((lv) => new Arrays(lv.shape));
        for (const key of npz.names) {
            const a = key.indexOf('__'), b = key.indexOf('__', a + 2);
            if (a < 0 || b < 0) throw new ValueError(`${base}.npz: ${pyReprValue(key)} is not L<level>__f|m__<name>`);
            const i = parseInt(key.slice(1, a), 10), kind = key.slice(a + 2, b), nm = key.slice(b + 2);
            (kind === 'f' ? fields : stack)[i].lazy(nm, () => npz.read(key));
        }
        const R = await G.init({ renderer });
        const info = { ...meta };
        const t = await assembleTerrain(R, recipe, meta.knobs, plan, fields, stack, info, { meshMasks: opts.meshMasks ?? null });
        t.loadedFrom = base;
        if (typeof opts.plants === 'string') {           // spots kept elsewhere (the terrain cache keeps a plan's)
            t.plants = await PlantSpots.load(opts.plants);
        } else if (opts.plants !== false) {              // the spots beside the save, when it carries any
            let there = true;
            try {
                Deno.statSync(base + '.plants.json');
            } catch (_e) {
                there = false;
            }
            if (there) t.plants = await PlantSpots.load(base);
        }
        t.loadSeconds = round2(now() - t0);
        if (build) {
            const pal = palette === 'keep' ? info.palette : palette;
            await buildScene(t, name ?? info.name ?? 'terrain', pal, dress, log, opts.THREE ?? null);
        }
        return t;
    }

    /** Release the geometry, the materials and what the terrain holds on the GPU. */
    dispose() {
        for (const m of [this.mesh, this.water.sea, ...this.water.lakes]) {
            if (!m) continue;
            m.geometry?.dispose();
            for (const mat of Array.isArray(m.material) ? m.material : [m.material]) mat?.dispose?.();
            m.removeFromParent?.();
        }
        this.collider?.geometry?.dispose();
        this.ring.dispose?.();
        this.mesh = this.collider = null;
        this.water = { lakes: [], sea: null };
    }
}

const VIEWPOINT_OPTS = ['eyeHeight', 'heading', 'maxSlopeDeg', 'lensMm', 'lookDy', 'prefer', 'clearanceM', 'within'];
const LOAD_OPTS = ['build', 'name', 'palette', 'dress', 'renderer', 'log', 'THREE', 'meshMasks', 'plants'];

// The checkout's commit, read from its git files (no process is started); null outside a git checkout.
function gitCommit() {
    try {
        const repo = new URL('../../', HERE);
        const read = (u) => Deno.readTextFileSync(u).trim();
        let gitdir = new URL('.git/', repo);
        if (Deno.statSync(new URL('.git', repo)).isFile) {
            const line = read(new URL('.git', repo));
            if (!line.startsWith('gitdir:')) return null;
            const p = line.slice(7).trim().replace(/\\/g, '/');
            gitdir = /^([A-Za-z]:)?\//.test(p) ? new URL('file:///' + p.replace(/^\//, '') + '/') : new URL(p + '/', repo);
        }
        const head = read(new URL('HEAD', gitdir));
        if (!head.startsWith('ref:')) return head.slice(0, 12);
        const ref = head.slice(4).trim();
        let common = gitdir;
        try {
            const c = read(new URL('commondir', gitdir)).replace(/\\/g, '/');
            common = /^([A-Za-z]:)?\//.test(c) ? new URL('file:///' + c.replace(/^\//, '') + '/') : new URL(c + '/', gitdir);
        } catch (_e) { /* not a linked worktree */ }
        for (const root of [gitdir, common]) {
            try {
                return read(new URL(ref, root)).slice(0, 12);
            } catch (_e) { /* packed, or in the other folder */ }
        }
        const packed = read(new URL('packed-refs', common)).split('\n').find((l) => l.endsWith(' ' + ref));
        return packed ? packed.slice(0, 12) : null;
    } catch (_e) {
        return null;
    }
}


// ------------------------------------------------------------------------------------------------ flatten ---

const FLATTEN_KEYS = ['at', 'radius', 'falloff', 'height', 'size', 'angleDeg'];

/** The flatten areas of a call, checked, as api.py holds them (Blender frame: at (x, y), angle_deg). */
function checkFlatten(flatten) {
    const out = [];
    (flatten ?? []).forEach((spec, i) => {
        const bad = Object.keys(spec).filter((k) => !FLATTEN_KEYS.includes(k)).sort();
        if (bad.length) throw new KeyError(`flatten[${i}]: unknown key ${pyReprValue(bad[0])}` + nearest(bad[0], FLATTEN_KEYS));
        if (spec.at === undefined || spec.at === null) throw new KeyError(`flatten[${i}] needs 'at': [x, z] metres`);
        const at = groundPoint(spec.at, `flatten[${i}].at`);
        const s = { at };
        for (const k of ['radius', 'falloff', 'height', 'size']) if (k in spec) s[k] = spec[k];
        if ('angleDeg' in spec) s.angle_deg = spec.angleDeg;
        if (!('falloff' in s)) s.falloff = (s.size ?? null) === null ? Number(s.radius ?? 10.0) : 10.0;
        out.push(s);
    });
    return out;
}

// api.py _flat_distance for one point, in doubles as numpy computes it: metres from the area's edge (0 inside)
function flatDistance(spec) {
    const cx = Number(spec.at[0]), cy = Number(spec.at[1]);
    if ((spec.size ?? null) !== null) {
        const w = Number(spec.size[0]), l = Number(spec.size[1]);
        const a = Number(spec.angle_deg ?? 0.0) * (Math.PI / 180.0);
        const ca = Math.cos(a), sa = Math.sin(a);
        return (x, y) => {
            const u = (x - cx) * ca + (y - cy) * sa, v = -(x - cx) * sa + (y - cy) * ca;
            return Math.hypot(Math.max(Math.abs(u) - w / 2, 0.0), Math.max(Math.abs(v) - l / 2, 0.0));
        };
    }
    const r = Number(spec.radius ?? 10.0);
    return (x, y) => Math.max(Math.hypot(x - cx, y - cy) - r, 0.0);
}

/** Per row of a level, the columns whose centres numpy's float64 distance puts at or under `limits[q]` metres from
 * the area's edge: an Int32Array of 2 * limits.length numbers a row (first, last; first > last: none), and the
 * cells counted per limit. The distance along a row is convex, so each set is one run of columns: the row's nearest
 * column is found by a ternary search and the run's ends by bisection, evaluating numpy's own expressions in
 * doubles (a table of the level's rows, not its cells). */
export function flatRows(spec, lv, limits) {
    const n = lv.n, nl = limits.length;
    const d = flatDistance(spec);
    const rows = new Int32Array(2 * nl * n);
    const counts = new Array(nl).fill(0);
    const xs = (i) => lv.x0 + (i + 0.5) * lv.cell;
    let dmin = Infinity, argmin = 0;
    for (let j = 0; j < n; j++) {
        const y = lv.y0 + (j + 0.5) * lv.cell;
        const f = (i) => d(xs(i), y);
        let lo = 0, hi = n - 1;
        while (hi - lo > 2) {
            const m1 = lo + Math.floor((hi - lo) / 3), m2 = hi - Math.floor((hi - lo) / 3);
            const f1 = f(m1), f2 = f(m2);
            if (f1 < f2) hi = m2 - 1;
            else if (f1 > f2) lo = m1 + 1;
            else { lo = m1; hi = m2; }
        }
        let ic = lo, fc = f(lo);
        for (let i = lo + 1; i <= hi; i++) {
            const v = f(i);
            if (v < fc) { fc = v; ic = i; }
        }
        // the first column of the row holding its smallest distance (numpy's argmin is row-major)
        while (ic > 0 && f(ic - 1) <= fc) fc = f(--ic);
        if (fc < dmin) { dmin = fc; argmin = j * n + ic; }
        for (let q = 0; q < nl; q++) {
            const o = 2 * nl * j + 2 * q;
            if (!(fc <= limits[q])) {
                rows[o] = 1;
                rows[o + 1] = 0;
                continue;
            }
            let a = 0, b = ic;                           // the first column at or under the limit, in [0, ic]
            while (a < b) {
                const m = (a + b) >> 1;
                if (f(m) <= limits[q]) b = m;
                else a = m + 1;
            }
            let c = ic, e = n - 1;                       // the last, in [ic, n - 1]
            while (c < e) {
                const m = (c + e + 1) >> 1;
                if (f(m) <= limits[q]) c = m;
                else e = m - 1;
            }
            rows[o] = a;
            rows[o + 1] = c;
            counts[q] += c - a + 1;
        }
    }
    return { rows, counts, dmin, argmin };
}

/** The exact flatten pass (design 4.13; api.py flatten_fields), in place on every level's h (and bed, kept under
 * it): inside each area the ground is exactly its height (given, or the median of the finest level's h there),
 * blended back over `falloff` metres with a C1 smoothstep. `fields`: per level, an object or core/fields.js Fields
 * with the GPU fields h (and bed), which are replaced; `flatten`: the areas as checkFlatten gives them (Blender
 * frame). Returns the resolved areas (info.flats). */
export async function flattenFields(R, fields, plan, flatten) {
    const P = prims(R);
    const flats = [];
    for (const s of flatten) {
        let fin = null;
        for (let k = plan.length - 1; k >= 0 && fin === null; k--) {
            if (plan[k].contains(s.at[0], s.at[1], Number(s.radius ?? 0.0))) fin = plan[k];
        }
        fin = fin ?? plan[0];
        const fo = Math.max(Number(s.falloff), 1e-6);
        const tables = plan.map((lv) => flatRows(s, lv, [0.0, fo]));
        let z;
        if ((s.height ?? null) !== null) {
            z = Number(s.height);
        } else {
            const tb = tables[fin.index], h0 = fields[fin.index].h;
            if (tb.counts[0]) {                          // the area's median
                const rf = R.field(fin.n, 4, 1, tb.rows, 'i32');
                const mask = R.field(fin.n, fin.n, 1);
                R.run('mesh/flatten_fields', { h: h0, bed: h0, rows: rf }, { outH: mask, outB: P.dummyF },
                    { uMode: 1, uShape: [0, 0, 0, 0], uAt: [0, 0, 0, 0], uCell: fin.cell, uZ: 0.0, uBed: 0 });
                z = await P.median(h0, { mask });
                rf.destroy();
                mask.destroy();
            } else {                                     // an area smaller than a cell: its nearest cell
                z = (await R.readRange(h0, tb.argmin, 1))[0];
            }
        }
        const rect = (s.size ?? null) !== null;
        const ang = Number(s.angle_deg ?? 0.0) * (Math.PI / 180.0);
        plan.forEach((lv, i) => {
            const tb = tables[i];
            if (tb.dmin > fo) return;
            const f = fields[i];
            const rf = R.field(lv.n, 4, 1, tb.rows, 'i32');
            const out = R.field(lv.n, lv.n, 1);
            const bed = f.bed ?? null;
            const outB = bed ? R.field(lv.n, lv.n, 1) : P.dummyF;
            R.run('mesh/flatten_fields', { h: f.h, bed: bed ?? f.h, rows: rf }, { outH: out, outB },
                { uMode: 0, uCell: lv.cell, uZ: z, uBed: bed ? 1 : 0,
                    uAt: [s.at[0] - lv.x0, s.at[1] - lv.y0, Math.cos(ang), Math.sin(ang)],
                    uShape: rect ? [1, Number(s.size[0]) / 2, Number(s.size[1]) / 2, fo] : [0, Number(s.radius ?? 10.0), 0, fo] },
                [Math.ceil(lv.n / 16), Math.ceil(lv.n / 16), 1]);
            rf.destroy();
            const oldH = f.h;
            f.h = out;                                   // a Fields releases the field it replaces
            if (!oldH.destroyed) oldH.destroy();
            if (bed) {
                f.bed = outB;
                if (!bed.destroyed) bed.destroy();
            }
        });
        flats.push({ ...s, height: z, at: [Number(s.at[0]), Number(s.at[1])], level: fin.index });
    }
    return flats;
}


// ------------------------------------------------------------------------------------------- the levels ---

const HALF_UNITS = ['0-1', '-1..1', 'deg'];

/** A mask as the cache stores it (api.py _cache_dtype): float16 for the bounded ones (0-1, -1..1, degrees: a
 * 0.05-degree step at most), float32 for metres and curvatures. `Mk` is masks.js (its MASKS table names each mask's
 * unit); while that module is not in the checkout an array keeps the dtype it was stored with, which for a loaded
 * save is Blender's choice already. `a` is { dtype, shape, data }. */
function cacheDtype(Mk, name, a) {
    if (!Mk) return a;
    let unit = null;
    try {
        unit = Mk.MASKS[(Mk.parseName ?? Mk.parse_name)(name)[0]][0];
    } catch (_e) { /* not a mask the table names: float32 */ }
    const want = HALF_UNITS.includes(unit) ? '<f2' : '<f4';
    if (a.dtype === want) return a;
    return Io.npArray(want === '<f2' ? new Float16Array(a.data) : new Float32Array(a.data), a.shape, want);
}

function scaledResolution(res, quality) {
    if (!res) return null;
    const f = { draft: 0.5, film: 1.0, hero: 2.0 }[quality];
    return Math.trunc(Math.max(64, pyRound(res * f / 8.0) * 8));
}

let NOTICED = false;

// the surfacing wave's options: accepted, resolved to none until it is ported, with one notice a process
function reserved(o, log) {
    const waiting = [];
    if (o.palette !== null && o.palette !== undefined) waiting.push(`palette ${pyReprValue(typeof o.palette === 'string' ? o.palette : 'a palette')}: grey clay`);
    if (o.surface !== null && o.surface !== undefined) waiting.push('surface: no surface data');
    if (o.plants !== null && o.plants !== undefined) waiting.push('plants: none');
    if (waiting.length && !NOTICED) {
        NOTICED = true;
        log(`[makeTerrain] the surface and the plants are the port's last wave (not in this checkout yet): ${waiting.join('; ')}`);
    }
}


// ----------------------------------------------------------------------------------------------- the call ---

function checkOptions(opts, what) {
    if (opts === null || typeof opts !== 'object' || Array.isArray(opts)) {
        throw new TypeError(`${what} takes one options object: await makeTerrain({ recipe: 'alpine_valley', seed: 7, ... })`);
    }
    for (const k of Object.keys(opts).sort()) {
        if (ARGS.includes(k)) continue;
        if (k in OLD_ARGS) {
            throw new TypeError(`${what}: '${k}' is an option of the old makeTerrain (a noise plane), which this one replaced. ` +
                `The new call: await makeTerrain({ recipe, size, seed, params, focus, flatten, quality }) -> a Terrain with ` +
                `.mesh and .heightAt (makeTerrain.recipes() lists the recipes, makeTerrain.describe(name) a recipe's knobs); ` +
                `nearest option: ${OLD_ARGS[k]}`);
        }
        throw new TypeError(`${what} got an unexpected option ${pyReprValue(k)}` + nearest(k, ARGS));
    }
    if (opts.recipe === null || opts.recipe === undefined) {
        throw new TypeError(`${what} needs a recipe: one of ${registry.names().join(', ')}`);
    }
    const quality = opts.quality ?? 'film';
    if (!Object.prototype.hasOwnProperty.call(Lv.QUALITY, quality)) {
        throw new ValueError(`quality ${pyReprValue(quality)}` + nearest(quality, Object.keys(Lv.QUALITY)));
    }
    const o = { recipe: null, size: null, resolution: null, seed: 0, params: null, focus: null, heroCell: null, context: null,
        flatten: null, seaLevel: null, baseElevationM: null, palette: 'auto', dress: true, surface: 'auto', plants: null,
        quality, cache: true, name: 'terrain', meshRes: null, meshMasks: null, renderer: null, log: console.log };
    for (const k of ARGS) if (opts[k] !== undefined) o[k] = opts[k];
    o.quality = quality;
    o.seed = opts.seed || 0;
    return o;
}

/** A terrain (PORT_PLAN.md 7.1). Resolves to a Terrain; `const { mesh, heightAt, masks } = await makeTerrain(...)`
 * also works.
 *
 *   recipe          a name from makeTerrain.recipes(), a Recipe, a recipe dict (recipe.toDict(), edited) or a list
 *                   of stages
 *   size            metres, the main tile's side (default: the recipe's; real_place: the DEM's extent)
 *   resolution      cells across the main tile (default: the quality's 512 / 1024 / 2048, or the recipe's, scaled)
 *   seed            the random seed of every stage
 *   params          the recipe's knobs, in their units ({ relief_m: 2800 }); an unknown knob names the nearest
 *   focus           [x, z], [[x, z], ...], an Object3D (a camera) or a list of them: hero levels around it
 *   heroCell        metres, the finest cell around the focus (default 0.5, 0.25 at quality 'hero'; draft: none)
 *   context         the horizon levels' extent multiplier (default the recipe's)
 *   flatten         [{ at: [x, z], radius, falloff, height: null }, ...]: flat areas (or size: [w, l] and angleDeg,
 *                   the rotation about +Y, for a rectangle); height null = the area's median
 *   seaLevel        metres (three.js y), or null
 *   baseElevationM  the altitude of y = 0 (snowline, treeline, ELA)
 *   palette         'auto' | a palette name | a palette dict | null (grey clay); the surfacing wave's: clay until then
 *   dress           rocks near the focus (the surfacing wave's)
 *   surface         'auto' | null | options: the surface data bake (the surfacing wave's)
 *   plants          null | 'auto' | { ecotope, focus, radiusM, seed }: the plant layer (the surfacing wave's)
 *   quality         'draft' | 'film' | 'hero'
 *   cache           read and write eidoverse/assets/cache/terrain_threejs/<key>
 *   name            the mesh's name
 *   meshRes         vertices per side each level is drawn at (default 512: about 3.3M triangles for seven levels)
 *   renderer        optional: a WebGPURenderer whose device runs the kernels (default: the scene's GPU_DEVICE)
 *   log             where the summary and the notices go (default console.log)
 */
export async function makeTerrain(opts = {}) {
    const t0 = now();
    const o = checkOptions(opts, 'makeTerrain()');
    const t = await generateChecked(o);
    const tb = now();
    await buildScene(t, o.name, o.palette, o.dress, o.log, null);
    t.info.seconds.scene = round2(now() - tb);
    t.info.seconds.total = round2(now() - t0);
    summary(t, o.log);
    (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('makeTerrain');
    return t;
}

/** Everything makeTerrain does short of the scene objects: the levels, their fields and masks, and the ring mesh
 * (heightAt, normalAt, masks, save and preview work; t.mesh is null). bake.mjs uses it. Options as makeTerrain's. */
export function generate(opts = {}) {
    return generateChecked(checkOptions(opts, 'generate()'));
}

/** What a call resolves to before anything runs (the first half of api.py generate): the recipe, its knobs and
 * stages, the defaults, the level plan, the mask parameters and the cache key ({ recipe, values, stages, plan, key,
 * ... }). Nothing is generated, and the cache is not read. What finds (or, in a test, seeds) a terrain's cache entry.
 * Options as makeTerrain's. */
export async function resolveCall(opts = {}) {
    const o = checkOptions(opts, 'resolveCall()');
    const R = await G.init({ renderer: o.renderer });
    return resolveChecked(o, R);
}

async function resolveChecked(o, R) {
    const log = o.log;
    const recipe = registry.resolve(o.recipe);
    const [values, stages] = recipe.resolve(o.params);
    const dfl = { ...recipe.defaults };
    if (recipe.defaultsFor) Object.assign(dfl, await recipe.defaultsFor(values, { R, log }));
    const quality = o.quality;
    const Q = Lv.QUALITY[quality];
    const size = Number(o.size ?? (dfl.size || 0.0));
    if (!(size > 0)) throw new ValueError(`recipe ${pyReprValue(recipe.name)} has no default size: pass size (metres)`);
    const res = Math.trunc(o.resolution || scaledResolution(dfl.resolution, quality) || Q.resolution);
    const ctxm = o.context ?? dfl.context ?? null;
    let hero;
    if (o.heroCell !== null) hero = Number(o.heroCell);
    else if (Q.hero_cell === null) hero = null;
    else hero = Math.min(Number(dfl.hero_cell ?? Q.hero_cell), Number(Q.hero_cell));
    const seaLevel = o.seaLevel ?? dfl.sea_level ?? null;
    const baseElevationM = o.baseElevationM ?? Number(dfl.base_elevation_m ?? 0.0);
    const centre = [...(dfl.centre ?? [0.0, 0.0])];
    const flatten = checkFlatten(o.flatten);
    const warnings = [];
    const warn = (m) => {
        warnings.push(m);
        log('[makeTerrain] ' + m);
    };
    reserved(o, log);
    const focusList = blenderFocus(o.focus);
    const plan = Lv.planLevels(size, res, { centre, context: ctxm, focus: focusList, hero, warn });
    const maskParams = { ...(dfl.mask_params ?? {}) };
    maskParams.sea_level = seaLevel;                     // y's frame, as MaskParams wants it
    maskParams.base_elevation_m = baseElevationM;
    // the cache: everything that decides the fields and masks
    const seed = Math.trunc(o.seed);
    const key = Ch.makeKey(recipe.toDict(), values, size, res, seed, plan, focusList,
        { flatten, sea_level: seaLevel, base_elevation_m: baseElevationM, mask_params: maskParams, quality, api: API_VERSION,
            code: Ch.terrainCodeHash() });
    return { recipe, values, stages, dfl, quality, size, res, ctxm, hero, seaLevel, baseElevationM, flatten, warnings,
        warn, focusList, plan, maskParams, seed, key };
}

async function generateChecked(o) {
    const log = o.log;
    const secs = {};
    const t0 = now();
    const R = await G.init({ renderer: o.renderer });
    const { recipe, values, stages, dfl, quality, size, res, ctxm, hero, seaLevel, baseElevationM, flatten, warnings, warn,
        focusList, plan, maskParams, seed, key } = await resolveChecked(o, R);
    secs.plan = round2(now() - t0);
    const C = new Ch.Cache(key);
    const hit = Boolean(o.cache) && C.complete();
    let skipped = [], flats = [];
    const fields = plan.map((lv) => new Arrays(lv.shape)), stack = plan.map((lv) => new Arrays(lv.shape));
    const gpuH = new Array(plan.length).fill(null);
    const t1 = now();
    if (hit) {
        for (let i = 0; i < plan.length; i++) {
            const npz = await NpzFile.open(C.levelPath(i));
            for (const k of npz.names) {
                if (k.startsWith('f__')) fields[i].lazy(k.slice(3), () => npz.read(k));
                else if (k.startsWith('m__')) stack[i].lazy(k.slice(3), () => npz.read(k));
            }
        }
        const meta = C.readMeta() ?? {};
        flats = meta.flats ?? [];
        skipped = meta.skipped ?? [];
        secs.load = round2(now() - t1);
    } else {
        const Run = await optionalModule('run.js');
        if (!Run) {
            throw new NotPortedError(`makeTerrain: this terrain is not in the cache, and the level runner (eidoverse/terrain/run.js, ` +
                `the hydrology and level runner package of the port) is not in this checkout yet, so it cannot be generated here. ` +
                `Terrain.load(path) reads a saved terrain (this edition's or the Blender edition's bake.py --save), and a cached ` +
                `terrain is read as before (cache key ${key})`);
        }
        if (recipe.prepare) await recipe.prepare(values, plan, { R, log });
        const info = {};
        const runLevels = Run.runLevels ?? Run.run_levels;
        const made = [...await runLevels(plan, recipe, values, stages, { seed, flatten, seaLevel, baseElevationM, log,
            cache: Boolean(o.cache), info, runner: R })];
        skipped = (Run.skippedStages ?? Run.skipped_stages)(info);
        secs.levels = round2(now() - t1);
        const t2 = now();
        if (flatten.length) flats = await flattenFields(R, made, plan, flatten);
        const Mk = await optionalModule('masks.js');
        let masksMade = plan.map(() => ({}));
        if (Mk) {
            const allowed = Object.keys(new Mk.MaskParams());
            const bad = Object.keys(maskParams).filter((k) => !allowed.includes(k)).sort();
            if (bad.length) throw new KeyError(`mask parameter ${pyReprValue(bad[0])}` + nearest(bad[0], allowed));
            masksMade = await (Mk.computeStack ?? Mk.compute_stack)(made, plan, { params: new Mk.MaskParams(maskParams) });
        } else {
            warn('masks.js (the masks package of the port) is not in this checkout yet: this terrain has no masks');
        }
        secs.masks = round2(now() - t2);
        // host copies of everything (PORT_PLAN.md 4.9); the heights stay on the GPU for the mesh
        for (let i = 0; i < plan.length; i++) {
            const f = made[i];
            const names = typeof f.names === 'function' ? f.names() : Object.keys(f);
            const got = await R.readAll(names.map((k) => f[k]));
            names.forEach((k, q) => fields[i].set(k, got[q]));
            gpuH[i] = f.h;
            const m = masksMade[i];
            if (m.skipped) stack[i].skipped = m.skipped;
            for (const [k, v] of Object.entries(m)) {
                if (k === 'skipped') continue;
                stack[i].set(k, ArrayBuffer.isView(v) || v?.data ? v : await R.read(v));
            }
        }
        if (o.cache) {
            for (let i = 0; i < plan.length; i++) {
                const arrays = {};
                for (const k of fields[i].names()) arrays['f__' + k] = fields[i].get(k);
                for (const k of stack[i].names()) arrays['m__' + k] = cacheDtype(Mk, k, stack[i].get(k));
                await C.saveLevel(i, arrays);
            }
            C.writeMeta({ recipe: recipe.name, knobs: values, size, resolution: res, seed, levels: plan.length, plan,
                focus: focusList, flats, skipped });
            // a film terrain is about 450 MB here: keep the cache to EIDO_TERRAIN_CACHE_GB (default 8), oldest out
            Ch.prune({ keepGb: Number(Deno.env.get('EIDO_TERRAIN_CACHE_GB') ?? 8.0) });
        }
    }
    const info = { name: null, recipe_name: recipe.name, size, resolution: res, seed, quality, focus: focusList,
        hero_cell: hero, context: ctxm, sea_level: seaLevel, base_elevation_m: baseElevationM,
        palette: o.palette === 'auto' ? (dfl.palette ?? null) : o.palette, place: dfl.place ?? null, cache_key: key,
        cache_hit: hit, skipped_stages: skipped, flats, warnings, mesh_res: Math.trunc(o.meshRes || Mesh.MESH_RES),
        seconds: secs, attribution: dfl.attribution ?? null };
    const tm = now();
    const t = await assembleTerrain(R, recipe, values, plan, fields, stack, info, { heights: gpuH, meshMasks: o.meshMasks });
    for (const h of gpuH) if (h && !h.destroyed) h.destroy();
    secs.mesh = round2(now() - tm);
    secs.generate = round2(now() - t0);
    return t;
}

async function assembleTerrain(R, recipe, values, plan, fields, stack, info, opts = {}) {
    const cores = plan.some((lv) => lv.role === 'hero');
    const heights = plan.map((lv, i) => {
        const g = opts.heights?.[i] ?? null;
        if (g) return g;
        const a = fields[i].f32('h');
        if (a === undefined) throw new ValueError(`level ${i}: no field 'h'`);
        return a;
    });
    // meshMasks (a debug option): those masks as point attributes of the mesh, eido_<mask>, with eido_level
    let attributes = null;
    if (opts.meshMasks) {
        const names = typeof opts.meshMasks === 'string' ? [opts.meshMasks] : [...opts.meshMasks];
        const have = [...new Set(stack.flatMap((m) => m.names()))];
        for (const n of names) if (!have.includes(n)) throw new KeyError(`meshMasks: no mask ${pyReprValue(n)}` + nearest(n, have));
        if (names.length > Mesh.MAX_ATTRIBUTES) {
            throw new ValueError(`meshMasks: ${names.length} masks; at most ${Mesh.MAX_ATTRIBUTES} (a vertex has 16 attributes ` +
                'by default, and the material reads its masks from data textures, not from the mesh)');
        }
        attributes = Object.fromEntries(names.map((n) => [n, stack.map((m) => (m.has(n) ? m.f32(n) : null))]));
    }
    const roles = plan.map((lv) => lv.role);
    const ring = await Mesh.buildRings(R, plan, heights, { cores, meshRes: Math.trunc(info.mesh_res || Mesh.MESH_RES), attributes,
        collider: (rings) => Collider.colliderRings({ rings }, roles) });
    return new Terrain(recipe, values, plan, fields, new MaskSet(stack, plan), ring, info, R);
}


// ---------------------------------------------------------------------------------------------- the scene ---

/** palette null: grey clay, albedo 0.18, roughness 0.9, no specular (the reference rig's, for shape comparisons;
 * blender/eidoblend/terrain/build/surfacing.py clay_material). A NodeMaterial. It moves to build/surfacing.js with
 * the surfacing wave. */
export function clayMaterial(THREE, name = 'terrain_clay') {
    const m = new THREE.MeshPhysicalNodeMaterial({ roughness: 0.9, metalness: 0.0 });
    m.color.setRGB(0.18, 0.18, 0.18);
    m.specularIntensity = 0.0;
    m.name = name;
    m.userData.eidoPalette = 'clay';
    return m;
}

// api.py _build_blender: the mesh, its materials, the collider proxy, the ray caster, the water
async function buildScene(t, name, palette, dress, log, THREEgiven) {
    const THREE = await three(THREEgiven);
    const info = t.info;
    info.name = name;
    const rm = t.ring;
    const geometry = Mesh.makeGeometry(THREE, rm);
    // two material slots (PORT_PLAN.md 7.3): 0 near, 1 far. Every ring's group is on slot 0, as Blender leaves
    // every polygon; the surfacing wave's material names the far rings from the cameras (surfacing.py far_rings)
    // and moves their groups to slot 1. The clay in both until then.
    const near = clayMaterial(THREE, name + '_clay'), far = clayMaterial(THREE, name + '_clay_far');
    const mesh = new THREE.Mesh(geometry, [near, far]);
    mesh.name = name;
    mesh.receiveShadow = true;
    mesh.castShadow = true;
    mesh.userData.trimeshCollider = true;                // real ground for the robot controller (its trimesh path)
    mesh.userData.eidoTerrain = Ch.plain({ recipe: t.recipe.toDict(), knobs: t.knobs, seed: info.seed, size: info.size,
        resolution: info.resolution, quality: info.quality, focus: info.focus, plan: t.levels.map((lv) => lv.toDict()),
        cache_key: info.cache_key, flats: info.flats ?? [], sea_level: info.sea_level, base_elevation_m: info.base_elevation_m,
        api_version: API_VERSION });
    mesh.userData.eidoTerrainMesh = rm.layout();
    mesh.userData.terrain = t;
    t.mesh = mesh;
    t.collider = Collider.colliderProxy(THREE, rm, mesh, { roles: t.levels.map((lv) => lv.role) });
    mesh.userData.colliderProxy = t.collider;
    Collider.installRaycast(THREE, mesh, rm);
    info.palette = palette === 'auto' && info.place ? (info.palette ?? 'auto') : palette;
    // water
    const R = await t._runner();
    const lakes = await Water.lakeObjects(THREE, R, t, { name: name + '_lake' });
    const sea = (info.sea_level ?? null) !== null ? await Water.seaObject(THREE, R, t, info.sea_level, { name: name + '_sea' }) : null;
    t.water = { lakes, sea };
    // rocks near the focus are the surfacing wave's (build/dressing.js)
    void dress;
    void log;
    return mesh;
}

function summary(t, log) {
    const i = t.info, lv = t.levels, s = i.seconds;
    const parts = Object.entries(s).filter(([k]) => k !== 'total' && k !== 'generate').map(([k, v]) => `${k} ${v}`).join(', ');
    const skipped = i.skipped_stages?.length ? `; stages skipped (no op of that name is registered): ${i.skipped_stages.join(', ')}` : '';
    const first = lv[0], last = lv[lv.length - 1];
    log(`[makeTerrain] ${t.recipe.name}${'dem' in t.knobs ? ' ' + pyReprValue(t.knobs.dem) : ''}: ` +
        `${lv.length} levels (${pyFormat(first.side / 1000, 'g')} km @ ${pyFormat(first.cell, '.3g')} m .. ${pyFormat(last.side, 'g')} m @ ${pyFormat(last.cell, '.3g')} m), ` +
        `cache ${i.cache_hit ? 'hit' : 'miss'}, ${s.total ?? s.generate} s (${parts}), ` +
        `${t.ring.triangleCount.toLocaleString('en-US')} triangles${skipped}`);
}


// ------------------------------------------------------------------------------------------- discovery ---

/** { name: title } of every recipe. */
export function recipes() {
    return registry.listing();
}

/** Log (and return) a recipe's stages, knobs (unit, default, range, what each does) and references, with any stage
 * whose op is not registered marked. */
export async function describe(recipe, log = console.log) {
    const Rc = registry.resolve(recipe);
    let text = Rc.describe();
    const missing = [];
    for (const s of Rc.stages) if (!(await registry.hasOp(s.op))) missing.push(s.op);
    if (missing.length) text += '\n  ops not registered (the runner skips these stages): ' + [...new Set(missing)].join(', ');
    if (Rc.name === 'real_place') {
        const rp = await optionalModule('recipes/real_place.js');
        if (rp) text += '\n  DEMs here: ' + ((rp.demNames ?? rp.dem_names)().join(', ') || '(none: set EIDO_TERRAIN_DEMS, or EIDO_BLENDER_EDITION)');
    }
    if (log) log(text);
    return text;
}

makeTerrain.recipes = recipes;
makeTerrain.describe = describe;
makeTerrain.load = (path, opts) => Terrain.load(path, opts);

export { makeTerrain as make_terrain, flattenFields as flatten_fields, placeCamera as place_camera, NotPortedError, levelIndex,
    checkFlatten, cacheDtype, assembleTerrain, buildScene, summary };
