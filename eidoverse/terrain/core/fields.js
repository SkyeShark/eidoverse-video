// Port of blender/eidoblend/terrain/core/fields.py at f90c6fc.
//
// Fields: a level's named float32 arrays (design section 2.4), held on the GPU (core/gpu.js fields, one channel).
//
//     const f = new Fields(level, { h: startSurface }, R);   // field name -> GPU field, row 0 south; .level attached
//     f.h = start                       // a field of the level's size, a number (filled on the GPU) or a
//                                       // Float32Array of n * n values (uploaded); the shape is checked
//     f.new('qs');                      // a zero field;  f.ensure('wear') keeps an existing one
//     const child = f.inherit(childLevel);   // the child's start: h and bed Catmull-Rom x2, other fields bilinear
//                                       // x2, U, K, Sc and the pins left out (re-evaluated from world space per level)
//     f.thickness()                     // h - bed (sediment, sand, talus): a new field
//
// Ops read and write fields by name, f.h or f['pin_w'] (FIELD_DOCS is the table of the design); Object.keys(f),
// 'h' in f and delete f.h work as on a dict.
//
// Where this differs from fields.py, and why:
//   - The arrays are GPU fields (per-cell work runs on the GPU, PORT_PLAN.md 2.4), so a Fields owns them: replacing
//     or deleting a name releases the field it held, unless another name of the same Fields still holds it;
//     dispose() releases them all. Give a Fields its own copy of a field that is also used elsewhere.
//   - A runner (core/gpu.js) makes the fields: the third argument, else the runner of a field given.
//   - summary() and toHost() are async (a readback); fromHost() uploads host arrays (a cache hit, a load).

import * as Gd from './grid.js';
import { ValueError, pyRound, pyReprValue } from './levels.js';
import { prims } from './prims.js';

export const FIELD_DOCS = {
    h: 'surface height, m',
    bed: 'top of rock, m; sediment, sand and talus thickness is h - bed',
    A: 'drainage area, m^2',
    qs: 'sediment flux, m^3/yr',
    U: 'uplift, m/yr',
    K: 'erodibility, m^(1-2m)/yr',
    Sc: 'threshold slope (tangent)',
    G: 'deposition coefficient (dimensionless: 0 bedrock incision, about 1 alluvial floors)',
    pin_w: 'Dirichlet pin weight 0..1 (borders, sea, flatten areas)',
    pin_h: 'Dirichlet pin value, m',
    wear: 'eroded depth, m',
    deposit: 'deposited sediment, m',
    talus: 'talus gained by threshold failure, m',
    sand: 'sand thickness, m',
    ice: 'ice (glacier) thickness or discharge, per the glacial solver',
    lava: 'lava-flow footprint / thickness',
    water: 'lake or sea depth, m',
};
export const CATMULL = ['h', 'bed'];                    // surfaces: Catmull-Rom x2
export const NOT_INHERITED = ['U', 'K', 'Sc', 'pin_w', 'pin_h'];   // re-evaluated from world space / set per level

const isField = (v) => v !== null && typeof v === 'object' && typeof v.h === 'number' && v.runner !== undefined &&
    v.buffer !== undefined;
const OWN = new Set(['level', 'runner', '_map']);

/** A level's named float32 GPU fields; .level is the Level (core/levels.js) they belong to. */
export class Fields {
    constructor(level, arrays = null, runner = null) {
        Object.defineProperty(this, 'level', { value: level, writable: true, configurable: true, enumerable: false });
        Object.defineProperty(this, '_map', { value: new Map(), configurable: true, enumerable: false });
        const first = Object.values(arrays ?? {}).find(isField);
        Object.defineProperty(this, 'runner', { value: runner ?? first?.runner ?? null, writable: true, configurable: true,
            enumerable: false });
        const proxy = new Proxy(this, {
            get(t, k, recv) {
                if (typeof k === 'string' && t._map.has(k) && !(k in Fields.prototype) && !OWN.has(k)) return t._map.get(k);
                return Reflect.get(t, k, recv);
            },
            set(t, k, v) {
                if (typeof k === 'string' && !(k in Fields.prototype) && !OWN.has(k)) {
                    t.set(k, v);
                    return true;
                }
                return Reflect.set(t, k, v);
            },
            has(t, k) { return (typeof k === 'string' && t._map.has(k)) || Reflect.has(t, k); },
            deleteProperty(t, k) {
                if (typeof k === 'string' && t._map.has(k)) t.delete(k);
                return true;
            },
            ownKeys(t) { return [...t._map.keys()]; },
            getOwnPropertyDescriptor(t, k) {
                if (typeof k === 'string' && t._map.has(k)) return { value: t._map.get(k), writable: true, enumerable: true, configurable: true };
                return undefined;
            },
        });
        for (const [k, v] of Object.entries(arrays ?? {})) proxy.set(k, v);
        return proxy;
    }

    /** [n, n]: the level's shape. */
    get shape() { return [this.level.n, this.level.n]; }

    get R() {
        if (!this.runner) throw new Error(`Fields(${this.level}): no GPU runner (pass one, or give a field)`);
        return this.runner;
    }

    /** Set a field: a GPU field of the level's shape (one float channel), a number (a constant field) or a
     * Float32Array of n * n values (row 0 south). Throws ValueError for a wrong shape. */
    set(name, value) {
        const [h, w] = this.shape;
        let f;
        if (typeof value === 'number') {
            f = Gd.fill(this.R, [h, w], value);
        } else if (value instanceof Float32Array) {
            if (value.length !== h * w) throw new ValueError(`field ${pyReprValue(name)}: ${value.length} values, the level is (${h}, ${w}) (${this.level})`);
            f = this.R.field(h, w, 1, value);
        } else if (isField(value)) {
            if (value.h !== h || value.w !== w || value.channels !== 1 || value.kind !== 'f32') {
                throw new ValueError(`field ${pyReprValue(name)}: shape (${value.h}, ${value.w}) ${value.format}, the level is (${h}, ${w}) (${this.level})`);
            }
            if (!this.runner) this.runner = value.runner;
            f = value;
        } else {
            throw new TypeError(`field ${pyReprValue(name)}: a GPU field, a number or a Float32Array is needed`);
        }
        const old = this._map.get(name);
        this._map.set(name, f);
        if (f.name === null || f.name === undefined) f.name = name;
        if (old && old !== f) this._release(old);
        return f;
    }

    get(name) { return this._map.get(name); }
    has(name) { return this._map.has(name); }
    names() { return [...this._map.keys()]; }
    entries() { return [...this._map.entries()]; }
    get size() { return this._map.size; }

    /** Remove a field, releasing it unless another name holds it. */
    delete(name) {
        const old = this._map.get(name);
        if (!old) return false;
        this._map.delete(name);
        this._release(old);
        return true;
    }

    _release(f) {
        for (const g of this._map.values()) if (g === f) return;
        if (!f.destroyed) f.destroy();
    }

    /** Several fields at once (dict.update). */
    update(other = {}) {
        const src = other instanceof Map ? [...other.entries()] : Object.entries(other);
        for (const [k, v] of src) this.set(k, v);
    }

    /** A new field of `fill` (replacing any old one). */
    new(name, fill = 0.0) { return this.set(name, Gd.fill(this.R, this.shape, fill)); }

    /** The existing field, or a new one of `fill`. */
    ensure(name, fill = 0.0) { return this._map.get(name) ?? this.new(name, fill); }

    /** h - bed (0 where there is no bed field): a new field the caller owns. */
    thickness() {
        if (!this._map.has('bed')) return Gd.fill(this.R, this.shape, 0.0);
        return Gd.arith(this.R, 'sub', this._map.get('h'), this._map.get('bed'));
    }

    /** A copy: the same level, a copy of every field. */
    copy() {
        const out = new Fields(this.level, null, this.runner);
        for (const [k, f] of this._map) {
            const c = this.R.like(f);
            this.R.copy(f, c);
            out.set(k, c);
        }
        return out;
    }

    /** The child level's start, from these (parent) fields. `child` is a Level whose cell is half of this level's and
     * whose window lies on this level's grid lines (planLevels makes them so), or the same window at twice the cells
     * (a coarse-to-fine pre-pass). Per field: 'catmull' for h and bed, 'skip' for U, K, Sc and the pins, 'bilinear'
     * for the rest; opts.rules ({ name: 'catmull' | 'bilinear' | 'nearest' | 'skip' }) overrides, and opts.names
     * limits which fields are carried. */
    inherit(child, opts = {}) {
        const { rules = null, names = null } = opts;
        const p = this.level;
        if (Math.abs(child.cell * 2.0 - p.cell) > 1e-9 * p.cell) {
            throw new ValueError(`inherit: the child cell ${child.cell} m is not half of ${p.cell} m`);
        }
        const fi = (child.x0 - p.x0) / p.cell, fj = (child.y0 - p.y0) / p.cell;
        const i0 = pyRound(fi), j0 = pyRound(fj), m = pyRound(child.side / p.cell);
        if (Math.abs(fi - i0) > 1e-6 || Math.abs(fj - j0) > 1e-6) {
            throw new ValueError(`inherit: the child window ${child} is not on the grid lines of ${p}`);
        }
        const out = new Fields(child, null, this.runner);
        for (const [name, a] of this._map) {
            if (names !== null && !names.includes(name)) continue;
            let kind = rules ? rules[name] : undefined;
            if (kind === undefined || kind === null) kind = NOT_INHERITED.includes(name) ? 'skip' : (CATMULL.includes(name) ? 'catmull' : 'bilinear');
            if (kind === 'skip') continue;
            out.set(name, Gd.cropUpsample2(a, i0, j0, m, kind));
        }
        return out;
    }

    /** { name: [min, max, mean] } for a log line (one readback per field). */
    async summary() {
        const P = prims(this.R);
        const out = {};
        for (const [k, f] of this._map) {
            const s = await P.stats(f);
            out[k] = [s.min, s.max, s.mean];
        }
        return out;
    }

    /** { name: Float32Array } of every field, in one wait. */
    async toHost() {
        const names = this.names();
        const arrays = await this.R.readAll(names.map((n) => this._map.get(n)));
        return Object.fromEntries(names.map((n, i) => [n, arrays[i]]));
    }

    /** A Fields on `level` from host arrays ({ name: Float32Array }), uploaded. */
    static fromHost(R, level, arrays) {
        return new Fields(level, arrays, R);
    }

    /** Release every field. */
    dispose() {
        for (const f of new Set(this._map.values())) if (!f.destroyed) f.destroy();
        this._map.clear();
    }

    toString() { return `Fields(${this.level}, [${this.names().sort().map(pyReprValue).join(', ')}])`; }
}
