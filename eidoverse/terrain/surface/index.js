// Port of blender/eidoblend/terrain/surface/__init__.py at d67f19e.
//
// The surface data bake (SURFACING_DESIGN.md 2.2, 2.3, 2.6, 2.7): a terrain's fields and masks turned into maps per
// texel, one data texture per kind and level, for the material, the looks and the plants.
//
//     import { bakeSurface, SurfaceData, MAPS } from './surface/index.js';
//     const sd = await bakeSurface(t, { palette: 'auto' });   // t: a Terrain (makeTerrain, Terrain.load)
//     await sd.maps('main')                     // { name: Float32Array } of a level (index or role), physical units
//     sd.at('crest', x, z)                      // bilinear on the finest level holding each point (three.js x, z)
//     sd.pack(names)                            // put these maps in the M families (the material's and plants' reads)
//     sd.channel('settle')                      // ['M0', 2, ['affine', 1, 0]]: family, channel(s), decode rule
//     sd.layouts                                // { family: Layout }: per level its layer, its tile, its UV rectangle
//     await sd.textures()                       // { family: THREE.DataArrayTexture } (surface/layers.js): D, E, M0.., F, C, P
//     await sd.save(folder)                     // the bake's files (npz per level, json) copied into a folder
//     MAPS.settle.doc                           // the registry (maps.js): every map's unit, family, encoding, meaning
//
// bakeSurface(terrain, { palette, options, cache, extra, log })
//     palette   null, 'auto', a name or a palette object: its terrain constants (snowline, sun, wind) steer the
//               snowpack, insolation and streaks, and with one the palette bake adds the far colour (C) and the
//               provenance colour (P). null: the terrain's own constants and palettes.CONSTANTS, and no C or P.
//     options   bake settings (bake.js DEFAULTS): { maps: 'masks' } packs the existing masks and the field normal only;
//               detail: 1 puts D and E at the cell.
//     cache     true: the surface cache's own root (cacheRoot(): $EIDO_SURFACE_THREEJS_CACHE, else
//               <repo>/eidoverse/assets/cache/terrain_surface_threejs/), <root>/<terrain key>/surface_<bake key>_L<i>.npz,
//               one bake per terrain key, whole keys pruned past 8 GB; a folder path: there; false: in memory.
//     extra     { canopy: [array per level], ... }: the plant layer's rasters, stored as M maps.
//
// What a reader must know (the material, the looks, the plants):
//   - Arrays are [row j, column i], row 0 south, texel centres at x0 + (i + 0.5) texel (the masks' frame, Blender
//     metres). The detail maps (D, E) are at half the cell on the main and hero levels of at most 1024 cells (their
//     shape says).
//   - `flow`, `wetness` and `channels` on hero levels come from the bake's own routing when it re-routes them
//     (option reroute_hero); elsewhere they are the masks'.
//   - `settle` is 0.5 on ground where the layer stayed (flat), toward 0 where it shed, toward 1 where it gathered.
//   - `src_strata` is metres of stratigraphic height (the masks' `strata` frame); the F family holds it, and
//     `strata`, less the pixel's own height and a per-level reference: decode ['z_plus', 1, refs] = object z +
//     refs[level] + texel.
//   - The unsuffixed curvatures' decode differs per level (their scale is 2 x the level's cell): decode rules with
//     arrays hold one number per level, folded in with the level's other constants.
//
// Where this differs from __init__.py, and why:
//   - A bake keeps each level's maps as the surface cache stores them (uint8 in their encoding, float16, float32: the
//     level's one readback, surface/bake.js), the same bytes whether it was just baked or read from the cache; a
//     fresh Blender bake holds its maps in float32 until it is reloaded. maps() decodes them on the GPU
//     (kernels/port/decode.wgsl, derive.wgsl) and is async; at() decodes the few texels a query reads (per-query work
//     is JavaScript, PORT_PLAN.md 2.4).
//   - The atlases are layers.js's data textures: one THREE.DataArrayTexture per family, one layer per level (plan
//     3.5: a film D atlas is taller than a default device's 8,192). `layouts` gives per level its layer, its tile's
//     pixel box in the layer and its UV rectangle there; images() / save_images() become textures() and save().
//   - at(name, x, z) takes three.js ground coordinates (z south), as MaskSet's Mask.at does; maps() and the arrays
//     are Blender's frame.
//   - The cache's root is this edition's own (terrain_surface_threejs: Blender's terrain_surface is the Blender
//     edition's, so neither prunes the other), its keys this edition's (surface/bake.js bakeKey); the files are
//     __init__.py's format, so a Blender bake folder loads here (loadCached) and the reverse.
//   - The functions that read files or the GPU are async.

import * as MP from './maps.js';
import { MAPS } from './maps.js';
import * as B from './bake.js';
import * as Io from '../core/io.js';
import { KeyError, ValueError, pyReprValue } from '../core/levels.js';

export { MAPS };
const f32 = Math.fround;
export const DETAIL_CAP = 2048;             // texels per level side, D and E
export const CELL_CAP = 1024;               // M, F, C, P
export const KEEP_BAKES = 1;                // surface bakes kept per terrain key (a new bake replaces the old)
// what a channel holds where its map is absent from a level (the open sky of cavity, a toe's coarse grain)
export const NEUTRAL = Object.freeze({ cavity: 1.0, grain: 1.0, settle: 0.5, valley: 0.5 });
const FAMILY_ORDER = ['D', 'E', 'F', 'C', 'P'];
export const CACHE_GB = 8.0;                // the surface cache's own cap (whole terrain keys pruned, oldest first)

function levelIndex(levels, level) {
    if (typeof level === 'number') return ((Math.trunc(level) % levels.length) + levels.length) % levels.length;
    if (level && typeof level === 'object' && 'index' in level) return Math.trunc(level.index);
    const roles = levels.map((lv) => lv.role);
    if (level === 'first') return 0;
    if (level === 'last') return levels.length - 1;
    if (['main', 'context', 'hero'].includes(level)) {
        const hit = roles.map((r, i) => [r, i]).filter(([r]) => r === level).map(([, i]) => i);
        if (!hit.length) throw new KeyError(`no ${level} level in this terrain (${roles.join(', ')})`);
        return level !== 'context' ? hit[hit.length - 1] : hit[0];
    }
    throw new KeyError(`level ${pyReprValue(level)}: an index, a Level, or 'main' | 'context' | 'hero' | 'first' | 'last'`);
}

// how many texels a level's tile holds: its cells times `factor`, at most `cap` (halved while over it) (atlas.py)
export function texelCount(level, factor, cap) {
    let n = Math.trunc(level.n) * Math.trunc(factor);
    while (n > cap) {
        if (n % 2) throw new ValueError(`level ${level.index}: ${n} texels cannot be halved to fit ${cap}`);
        n /= 2;
    }
    return n;
}

// the stored arrays of one level: a Map name -> npArray, or an NpzFile whose entries load when first asked for
class LevelStore {
    constructor(src) {
        this.src = src;                             // Map | NpzFile
        this.loaded = new Map();
    }

    names() { return this.src instanceof Map ? [...this.src.keys()] : this.src.names; }
    has(name) { return this.src instanceof Map ? this.src.has(name) : this.src.has(name); }

    get(name) {
        if (this.src instanceof Map) return this.src.get(name);
        if (!this.loaded.has(name)) this.loaded.set(name, this.src.has(name) ? this.src.read(name) : undefined);
        return this.loaded.get(name);
    }
}

/** A terrain's baked surface maps: per level its stored arrays, the layouts, the M packing, and the textures. Made by
 * bakeSurface. */
export class SurfaceData {
    constructor(terrain, baked, info, options, key, palette = null, colour = null, cacheDir = null) {
        this.terrain = terrain;
        this.levels = [...terrain.levels];
        this.key = key;
        this.options = { ...options };
        this.info = { ...(info ?? {}) };
        this.palette = palette;
        this.cacheDir = cacheDir;
        this._baked = baked.map((b) => (b instanceof LevelStore ? b : new LevelStore(b)));
        this._colour = colour ? colour.map((c) => new LevelStore(c)) : null;
        this._colourTag = null;
        this._extra = {};
        this._packing = null;
        this._textures = null;
        this._memo = new Map();
        this.factors = this.levels.map((lv) => B.detailFactor(lv, this.options));
        const nDet = this.levels.map((lv, i) => texelCount(lv, this.factors[i], DETAIL_CAP));
        const nCell = this.levels.map((lv) => texelCount(lv, 1, CELL_CAP));
        this._gridLayouts = { detail: layoutOf(this.levels, nDet, 'detail'), cell: layoutOf(this.levels, nCell, 'cell') };
        const refs = this.info.refs;
        this.refs = refs ? Object.fromEntries(Object.entries(refs).map(([k, v]) => [k, [...v]])) : this._references();
    }

    toString() {
        return `SurfaceData(${this.levels.length} levels, ${this.names().length} maps, key ${String(this.key).slice(0, 10)}, ` +
            `${this._colour ? 'with' : 'no'} palette colour)`;
    }

    // ---- what there is

    // the names level i holds (its masks, its bake, the extras, the palette colour, the derived names)
    _names(i) {
        const out = new Set(this.terrain.masks.level(i) ? Object.keys(this.terrain.masks.level(i)) : []);
        for (const k of this._baked[i].names()) if (!k.startsWith('_')) out.add(k);
        for (const [k, per] of Object.entries(this._extra)) if (per[i] !== null && per[i] !== undefined) out.add(k);
        if (this._colour) for (const k of this._colour[i].names()) out.add(k);
        if (out.has('src_dz')) out.add('src_strata');
        if (out.has('slope') && out.has('aspect')) out.add('insolation');
        if (out.has('n20_x') && out.has('n20_y')) out.add('slope_20m');
        return out;
    }

    /** The map names a level holds (default: the finest), the shader-derived ones included. */
    names(level = null) {
        const i = level === null ? this.levels.length - 1 : levelIndex(this.levels, level);
        return [...this._names(i)].sort();
    }

    has(name) {
        if (name in MP.PAIRS) return MP.PAIRS[name].every((n) => this.has(n));
        return this._names(this.levels.length - 1).has(name);
    }

    // one stored array of level i by name (the bake's, an extra, the palette colour's) as stored, or undefined
    _stored(i, name) {
        if (this._extra[name] && this._extra[name][i]) {
            const a = this._extra[name][i];
            const n = Math.round(Math.sqrt(a.length));
            return { dtype: '<f4', shape: [n, n], data: a };
        }
        if (this._colour && this._colour[i].has(name)) return this._colour[i].get(name);
        return this._baked[i].get(name);
    }

    /** { name: Float32Array } of one level (an index or a role), physical units (maps.MAPS): the masks, the bake's
     * maps (they replace the masks' flow, wetness and channels on re-routed hero levels), the plant rasters given to
     * addMaps, the palette bake's colours (n x n x 3 for the colours), and the derived names src_strata, insolation
     * and slope_20m. Decoded on the GPU from the stored bytes, once per level. Arrays are shared, not copies. */
    async maps(level) {
        const i = levelIndex(this.levels, level);
        if (this._memo.has(i)) return { ...this._memo.get(i) };
        const G = await import('../core/gpu.js');
        const R = await G.init();
        const out = {};
        const mk = this.terrain.masks.level(i);
        for (const k of Object.keys(mk)) out[k] = mk[k];
        const decodeList = [];
        const names = [...this._baked[i].names(), ...(this._colour ? this._colour[i].names() : [])];
        for (const k of names) {
            if (k.startsWith('_')) continue;
            decodeList.push(k);
        }
        const fields = [];
        for (const k of decodeList) fields.push([k, this._decodeField(R, i, k)]);
        for (const [k, per] of Object.entries(this._extra)) if (per[i]) out[k] = per[i];
        const got = fields.length ? await R.readAll(fields.map(([, f]) => f)) : [];
        fields.forEach(([k, f], q) => {
            const a = this._stored(i, k);
            out[k] = got[q];
            if (a.shape.length === 3) out[k].shape3 = a.shape;
            f.destroy();
        });
        // the derived names, on the GPU
        const lv = this.levels[i];
        const derive = [];
        if ('src_dz' in out && !('h' in out)) derive.push(['src_strata', 2, this.terrain.fields(i).h, out.src_dz]);
        if ('slope' in out && 'aspect' in out) derive.push(['insolation', 0, out.slope, out.aspect]);
        if ('n20_x' in out && 'n20_y' in out) derive.push(['slope_20m', 1, out.n20_x, out.n20_y]);
        if (derive.length) {
            const az = (Number(this.options.sun_azimuth_deg || 180.0) * Math.PI) / 180.0;
            const el = (Number(this.options.sun_elevation_deg || 45.0) * Math.PI) / 180.0;
            const made = derive.map(([, mode, a, b]) => {
                const n = Math.round(Math.sqrt(a.length));
                const fa = R.field(n, n, 1, a), fb = R.field(n, n, 1, b), o = R.field(n, n, 1);
                R.run(B.kernel(R, 'derive'), { a: fa, b: fb }, { outF: o },
                    { uMode: mode, uSun: [f32(Math.sin(az)), f32(Math.cos(az)), f32(Math.cos(el)), f32(Math.sin(el))] });
                fa.destroy();
                fb.destroy();
                return o;
            });
            const vals = await R.readAll(made);
            derive.forEach(([k], q) => { out[k] = vals[q]; made[q].destroy(); });
        }
        void lv;
        this._memo.set(i, out);
        return { ...out };
    }

    // a stored map of level i as a GPU field of its physical values (decode.wgsl): the caller releases it
    _decodeField(R, i, name) {
        const a = this._stored(i, name);
        const cell = Number(this.levels[i].cell);
        const [h, w] = [a.shape[0], a.shape.length > 2 ? a.shape[1] * a.shape[2] : a.shape[1]];
        if (a.dtype === '<f4') return R.field(h, w, 1, a.data);
        const per = a.dtype === '|u1' ? 4 : 2;
        const stride = Math.ceil(w / per);
        const words = new Uint32Array(h * stride);
        const bytes = new Uint8Array(words.buffer);
        const src = new Uint8Array(a.data.buffer, a.data.byteOffset, a.data.byteLength);
        const rowBytes = w * (per === 4 ? 1 : 2);
        if (rowBytes === stride * 4) bytes.set(src);
        else for (let j = 0; j < h; j++) bytes.set(src.subarray(j * rowBytes, (j + 1) * rowBytes), j * stride * 4);
        const src32 = R.field(h, stride, 1, words, 'u32');
        const out = R.field(h, w, 1);
        let kind = 1, square = 0, A = 1.0, Bv = 0.0;
        if (a.dtype === '|u1') {
            const [k, ra, rb] = MP.decodeRule(MP.spec(name), [cell]);
            kind = 0;
            square = k === 'square' ? 1 : 0;
            A = Array.isArray(ra) ? ra[0] : ra;
            Bv = Array.isArray(rb) ? rb[0] : rb;
        } else {
            const ref = this._stored(i, `_ref_${name}`);
            Bv = ref ? ref.data[0] : 0.0;
        }
        R.run(B.kernel(R, 'decode'), { src: src32 }, { outF: out }, { uKind: kind, uSquare: square, uA: f32(A), uB: f32(Bv) });
        src32.destroy();
        return out;
    }

    /** One map's physical value at texel (i, j) of level k: the stored byte or half decoded (per-query reads). */
    _value(k, name, idx) {
        const a = this._stored(k, name);
        if (!a) return NaN;
        const cell = Number(this.levels[k].cell);
        if (a.dtype === '|u1') return MP.decode1(MP.spec(name), f32(a.data[idx] * f32(1.0 / 255.0)), cell);
        let v = Number(a.data[idx]);
        const ref = this._stored(k, `_ref_${name}`);
        if (ref) v = f32(v + f32(ref.data[0]));
        return v;
    }

    /** A map at three.js ground points (x, z): bilinear on the finest level whose window holds each point (MaskSet's
     * rule; Blender's frame inside: y = -z). Numbers or arrays; a level lacking the map is skipped. The masks and
     * the bake's stored maps; a palette colour reads its first channel. */
    at(name, x, z) {
        const scalar = typeof x === 'number';
        const xs = scalar ? [x] : Array.from(x), ys = scalar ? [-z] : Array.from(z, (v) => -v);
        const out = new Float64Array(xs.length);
        const done = new Uint8Array(xs.length);
        let any = false;
        for (let k = this.levels.length - 1; k >= 0; k--) {
            const lv = this.levels[k];
            const mk = this.terrain.masks.level(k);
            const inMask = name in mk;
            const a = inMask ? null : this._stored(k, name);
            if (!inMask && !a) continue;
            any = true;
            const n = inMask ? lv.n : a.shape[0];
            const texel = lv.side / n;
            const read = inMask ? ((idx) => mk[name][idx]) : ((idx) => this._value(k, name, a.shape.length > 2 ? idx * a.shape[2] : idx));
            for (let q = 0; q < xs.length; q++) {
                if (done[q]) continue;
                if (k > 0 && !lv.contains(xs[q], ys[q])) continue;
                // atlas.py sample_bilinear: clamped to the outermost texel centres
                const fi = Math.min(Math.max((xs[q] - lv.x0) / texel - 0.5, 0.0), n - 1.0);
                const fj = Math.min(Math.max((ys[q] - lv.y0) / texel - 0.5, 0.0), n - 1.0);
                const i0 = Math.min(Math.floor(fi), Math.max(n - 2, 0)), j0 = Math.min(Math.floor(fj), Math.max(n - 2, 0));
                const ti = f32(fi - i0), tj = f32(fj - j0);
                const i1 = Math.min(i0 + 1, n - 1), j1 = Math.min(j0 + 1, n - 1);
                const v00 = read(j0 * n + i0), v10 = read(j0 * n + i1), v01 = read(j1 * n + i0), v11 = read(j1 * n + i1);
                out[q] = (v00 * (1 - ti) + v10 * ti) * (1 - tj) + (v01 * (1 - ti) + v11 * ti) * tj;
                done[q] = 1;
            }
        }
        if (!any) throw new KeyError(`no surface map ${pyReprValue(name)}; there are: ${this.names().join(', ')}`);
        return scalar ? out[0] : out;
    }

    /** Add rasters per level ({ canopy: [Float32Array or null per level], ... }): M maps of the registry (the plant
     * layer's), each (n, n) on its level's cells. Clears the M textures made before. */
    addMaps(extra) {
        for (const [k, per0] of Object.entries(extra ?? {})) {
            MP.spec(k);
            const per = [...per0];
            if (per.length !== this.levels.length) throw new ValueError(`extra map ${pyReprValue(k)}: ${per.length} arrays for ${this.levels.length} levels`);
            this._extra[k] = per.map((a) => (a === null || a === undefined ? null : a instanceof Float32Array ? a : new Float32Array(a)));
        }
        this._memo.clear();
        this._textures = null;
        return this;
    }

    // ---- layouts and channels

    /** { family: Layout } for every family the data holds (D, E on the detail grid; M0.., F, C, P on the cell grid),
     * plus 'detail' and 'cell'. A Layout's tiles[i] is level i's: its layer (= i), its tile's pixel box in the layer
     * (gutter included) and rect() its data's UV rectangle there. */
    get layouts() {
        const out = { ...this._gridLayouts };
        for (const fam of this.families()) out[fam] = this._gridLayouts[(fam === 'D' || fam === 'E') ? 'detail' : 'cell'];
        return out;
    }

    /** What a material's reader folds in per level (SURFACING_DESIGN.md 2.4): { detail: [...], cell: [...] }, each a
     * list by level of { x0, y0, side, texel, layer, u0, v0, du, dv }: the level's window (Blender metres), its texel
     * on that layout, its layer and its data rectangle in the layer's UV (u = u0 + du (x - x0) / side). */
    readerConstants() {
        const out = {};
        for (const [g, lay] of Object.entries(this._gridLayouts)) {
            out[g] = lay.tiles.map((t) => {
                const [u0, v0, du, dv] = t.rect(lay);
                return { x0: t.x0, y0: t.y0, side: t.side, texel: t.texel, layer: t.level, u0, v0, du, dv };
            });
        }
        return out;
    }

    /** The families the data holds now: D, E, F, C, P as present, and M0..Mk of the current packing. */
    families() {
        const have = this._names(this.levels.length - 1);
        const out = [];
        for (const fam of FAMILY_ORDER) {
            const chans = MP.FAMILIES[fam].channels;
            if (fam === 'F') {
                if (have.has('strata') || have.has('src_dz')) out.push(fam);
            } else if (chans.some((c) => c !== null && have.has(c))) {
                out.push(fam);
            }
        }
        for (let k = 0; k < this.packing().length; k++) out.push(`M${k}`);
        return out;
    }

    /** The M families: [[map, ...] (up to four), ...]. Set by pack(); by default the palette's mask reads (when the
     * bake had a palette) or every M map present. */
    packing() {
        if (this._packing === null) {
            let names = null;
            if (this.palette !== null && this._palettes) {
                try {
                    names = [...this._palettes.materialMasks(this.palette)].sort();
                } catch (_e) {
                    names = null;
                }
            }
            if (names === null) names = [...this._names(this.levels.length - 1)].filter((k) => isM(k));
            this.pack(names);
        }
        return this._packing;
    }

    /** Put these maps (and only these) in the M families, four to a texture: the maps a material and the plant layer
     * read. Pair names ('n20') take both channels side by side; names that are not M maps, or that the data lacks,
     * are left out. Returns { name: [family, channel] }. Clears the M textures made before. */
    pack(names) {
        const have = this._names(this.levels.length - 1);
        const want = [];
        for (const nm of names) {
            for (const n of (MP.PAIRS[nm] ?? [nm])) if (!want.includes(n) && isM(n) && have.has(n)) want.push(n);
        }
        want.sort();
        const groups = [];
        let cur = [];
        for (const n of want) {                       // a pair stays in one texture
            const pair = MP.spec(n).pair;
            if (pair !== null && want.includes(pair) && want.indexOf(pair) < want.indexOf(n)) continue;
            const unit = [n, ...(pair !== null && want.includes(pair) ? [pair] : [])];
            if (cur.length + unit.length > 4) {
                groups.push(cur);
                cur = [];
            }
            cur.push(...unit);
        }
        if (cur.length) groups.push(cur);
        this._packing = groups;
        this._textures = null;
        const out = {};
        groups.forEach((g, k) => g.forEach((n, c) => { out[n] = [`M${k}`, c]; }));
        return out;
    }

    /** [family, channel, decode] of a map: the texture family ('D', 'E', 'M0'.., 'F', 'C', 'P'), the channel index
     * (an array for a pair or a colour), and maps.decodeRule's [kind, a, b], a and b arrays with one number per level
     * where they differ by level. The shader-derived names give ['shader', null, null]. Throws KeyError for a map the
     * data does not hold. */
    channel(name) {
        if (name in MP.PAIRS) {
            const parts = MP.PAIRS[name].map((n) => this.channel(n));
            const fams = new Set(parts.map((p) => p[0]));
            if (fams.size !== 1) throw new KeyError(`${pyReprValue(name)}: its channels are in different textures`);
            return [parts[0][0], parts.map((p) => p[1]), parts[0][2]];
        }
        const s = MP.spec(name);
        if (s.family === 'shader') return ['shader', null, null];
        const cells = this.levels.map((lv) => Number(lv.cell));
        if (s.family === 'M') {
            const packing = this.packing();
            for (let k = 0; k < packing.length; k++) {
                if (packing[k].includes(name)) return [`M${k}`, packing[k].indexOf(name), MP.decodeRule(s, cells)];
            }
            throw new KeyError(`surface map ${pyReprValue(name)} is not in the M families (pack() it; packed: ` +
                `${packing.flat().join(', ')})`);
        }
        if (!this.has(s.family !== 'F' ? name : (name === 'src_strata' ? 'src_dz' : name))) {
            throw new KeyError(`surface map ${pyReprValue(name)} is not in this bake (maps: ${this.names().join(', ')})`);
        }
        const refs = this.refs[name] ?? this.levels.map(() => 0.0);
        return [s.family, s.channel, MP.decodeRule(s, cells, refs)];
    }

    // the F family's per-level references (metres): what the bake stored beside its F maps (__init__.py
    // _references: the median of each map's height above the ground, to 0.1 m), 0 where a level has none
    _references() {
        const out = {};
        for (const [nm, src] of [['strata', 'strata_dz'], ['src_strata', 'src_dz']]) {
            out[nm] = this.levels.map((_, i) => {
                const r = this._baked[i].get(`_ref_${src}`);
                return r ? Number(r.data[0]) : 0.0;
            });
        }
        return out;
    }

    /** The four channel names of a family (null for an unused channel). */
    familyMaps(fam) {
        if (fam.startsWith('M')) {
            const g = this.packing()[Number(fam.slice(1))];
            return [...g, ...new Array(4 - g.length).fill(null)];
        }
        return [...MP.FAMILIES[fam].channels];
    }

    /** { family: THREE.DataArrayTexture } (surface/layers.js): one texture per family, one layer per level, the
     * tiles with their gutters filled from the coarser levels on the GPU. names: pack these maps into the M families
     * first. Made once; pack() and addMaps() clear them. opts: THREE (the three module the renderer uses; default
     * import('three/webgpu')), R (the GPU runner). */
    async textures(names = null, opts = {}) {
        if (names !== null) this.pack(names);
        if (!this._textures) {
            const L = await import('./layers.js');
            this._textures = await L.makeTextures(this, opts);
        }
        return this._textures;
    }

    /** The bake's files copied into `folder` (its npz per level, its json; the palette bake's beside them): what a
     * scene that renders elsewhere loads with loadCached. Returns the paths. */
    async save(folder) {
        await Deno.mkdir(folder, { recursive: true });
        const out = [];
        const n = this.levels.length;
        for (let i = 0; i < n; i++) {
            const p = `${folder}/surface_${this.key}_L${i}.npz`;
            await Io.writeNpz(p, this._baked[i].names().map((k) => [k, () => this._baked[i].get(k)]));
            out.push(p);
        }
        const meta = `${folder}/surface_${this.key}.json`;
        await Deno.writeTextFile(meta, JSON.stringify(plain(this.info), null, 1));
        out.push(meta);
        if (this._colour && this._colourTag) {
            for (let i = 0; i < n; i++) {
                const p = `${folder}/surface_${this.key}_${this._colourTag}_L${i}.npz`;
                await Io.writeNpz(p, this._colour[i].names().map((k) => [k, () => this._colour[i].get(k)]));
                out.push(p);
            }
        }
        return out;
    }

    /** A text table: per level its maps, per family its layout and memory. */
    describe() {
        const lines = [String(this)];
        for (const fam of this.families()) {
            const lay = this.layouts[fam];
            const base = fam.startsWith('M') ? 'M' : fam;
            const bpt = MP.FAMILIES[base].format === 'RGBA16F' ? 8 : 4;
            const mb = lay.size * lay.size * lay.tiles.length * bpt * (4 / 3) / 1e6;
            lines.push(`  ${fam.padEnd(3)} ${lay.size} x ${lay.size} x ${lay.tiles.length} layers  ${mb.toFixed(0)} MB  ` +
                JSON.stringify(this.familyMaps(fam)));
        }
        return lines.join('\n');
    }

    // ---- the palette bake

    /** The far colour (C) and provenance colour (P) of a palette (surface/palette_bake.js), cached beside the bake.
     * provenance: 'budget' (P while the palette bake stays within its 30 s), true always, false never.
     * info.palette_bake says what was made, cached or deferred. Returns this. */
    async bakePalette(palette = null, opts = {}) {
        const PB = await import('./palette_bake.js');
        const pal = palette ?? this.palette;
        if (pal === null || pal === undefined) throw new ValueError('bakePalette needs a palette');
        const colour = await PB.bake(this, pal, { cache: opts.cache ?? this.cacheDir, log: opts.log, pMode: opts.provenance ?? 'budget' });
        this._colour = colour.map((c) => new LevelStore(c));
        this._memo.clear();
        this._textures = null;
        return this;
    }
}

function isM(name) {
    try {
        return MP.spec(name).family === 'M';
    } catch (_e) {
        return false;
    }
}

// JSON-able copies (typed arrays as lists)
function plain(v) {
    if (ArrayBuffer.isView(v)) return Array.from(v);
    if (Array.isArray(v)) return v.map(plain);
    if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, plain(x)]));
    return v;
}


// ---------------------------------------------------------------------------------------------- the layout ---

/** A family's per-level tiles in its data texture: each level a layer (its index), its tile of n + 2 g texels in the
 * layer's corner (g = 32 up to 1024 texels, 64 above: atlas.py gutter_for), the layer as large as the largest tile. */
export class Tile {
    constructor(level, n, gutter, texel, x0, y0, side) {
        Object.assign(this, { level, n, gutter, texel, x0, y0, side, x: 0, y: 0 });
    }

    get size() { return this.n + 2 * this.gutter; }

    /** [u0, v0, du, dv]: the data region of the tile in its layer's UV (0..1). */
    rect(lay) {
        const W = lay.size, H = lay.size;
        return [(this.x + this.gutter) / W, (this.y + this.gutter) / H, this.n / W, this.n / H];
    }

    /** [x0, y0, x1, y1]: the tile's pixel box in its layer, gutter included, end exclusive. */
    pixels() { return [this.x, this.y, this.x + this.size, this.y + this.size]; }

    /** World x (columns) and y (rows) of every texel centre of the tile, gutter included. */
    centres() {
        const s = this.size, xs = new Float64Array(s), ys = new Float64Array(s);
        for (let k = 0; k < s; k++) {
            xs[k] = this.x0 + (k - this.gutter + 0.5) * this.texel;
            ys[k] = this.y0 + (k - this.gutter + 0.5) * this.texel;
        }
        return [xs, ys];
    }

    toDict(lay) {
        const [u0, v0, du, dv] = this.rect(lay);
        return { level: this.level, layer: this.level, x: this.x, y: this.y, size: this.size, n: this.n, gutter: this.gutter,
            texel: this.texel, x0: this.x0, y0: this.y0, side: this.side, u0, v0, du, dv };
    }
}

export function gutterFor(nTexels) {
    return Math.trunc(nTexels) <= 1024 ? 32 : 64;
}

/** One layer per level (atlas.py layout, as layers of a 2D-array texture instead of shelves of a tall image). */
export function layoutOf(levels, nTexels, grid = 'cell') {
    const tiles = levels.map((lv, i) => new Tile(Math.trunc(lv.index ?? i), Math.trunc(nTexels[i]), gutterFor(nTexels[i]),
        Number(lv.side) / nTexels[i], Number(lv.x0), Number(lv.y0), Number(lv.side)));
    const size = Math.max(...tiles.map((t) => t.size));
    if (size > 8192) throw new ValueError(`a ${grid} data texture layer of ${size} texels passes a default device's 8192`);
    return { grid, size, width: size, height: size, layers: tiles.length, tiles,
        toDict() { return { grid, size, layers: tiles.length, tiles: tiles.map((t) => t.toDict(this)) }; } };
}


// --------------------------------------------------------------------------------------------- the cache ---

/** The surface cache's own root: $EIDO_SURFACE_THREEJS_CACHE, else <repo>/eidoverse/assets/cache/terrain_surface_threejs
 * (git-ignored, as the terrain cache is; never inside the terrain cache, whose prune must not count it). */
export function cacheRoot() {
    const e = Deno.env.get('EIDO_SURFACE_THREEJS_CACHE');
    if (e) return e.replace(/\\/g, '/').replace(/\/+$/, '');
    let p = decodeURIComponent(new URL('../../assets/cache/terrain_surface_threejs/', import.meta.url).pathname);
    if (/^\/[A-Za-z]:/.test(p)) p = p.slice(1);
    return p.replace(/\/+$/, '');
}

/** Where a terrain's bakes are cached: <cacheRoot()>/<terrain key>/ when cache is true, the folder when cache is a
 * path, else null (in memory). */
export async function cacheFolder(terrain, cache) {
    if (!cache) return null;
    const folder = typeof cache === 'string' ? cache : `${cacheRoot()}/${await B.terrainKey(terrain)}`;
    await Deno.mkdir(folder, { recursive: true });
    return folder;
}

/** Delete whole terrain keys from the surface cache's root, least recently used first, until it holds at most
 * keepGb (never the newest). Returns the bytes freed. */
export async function pruneRoot(keepGb = CACHE_GB, root = null) {
    root = root ?? cacheRoot();
    const ents = [];
    try {
        for (const d of Deno.readDirSync(root)) {
            if (!d.isDirectory) continue;
            const p = `${root}/${d.name}`;
            let size = 0, used = 0;
            for (const f of Deno.readDirSync(p)) {
                if (!f.isFile) continue;
                const st = Deno.statSync(`${p}/${f.name}`);
                size += st.size;
                used = Math.max(used, st.mtime?.getTime() ?? 0);
            }
            ents.push([used || (Deno.statSync(p).mtime?.getTime() ?? 0), size, p]);
        }
    } catch (_e) {
        return 0;
    }
    ents.sort((a, b) => a[0] - b[0]);
    const total = ents.reduce((s, e) => s + e[1], 0);
    let freed = 0;
    for (const [, size, p] of ents.slice(0, -1)) {
        if (total - freed <= keepGb * 1e9) break;
        await Deno.remove(p, { recursive: true });
        freed += size;
    }
    return freed;
}

const paths = (folder, key, n) => [Array.from({ length: n }, (_, i) => `${folder}/surface_${key}_L${i}.npz`), `${folder}/surface_${key}.json`];
const exists = (p) => {
    try {
        Deno.statSync(p);
        return true;
    } catch (_e) {
        return false;
    }
};

/** [baked per level (lazy: each level's npz opened, its entries read when first asked for), info] from a cache
 * folder, or null when any file is missing (__init__.py load_cached; a Blender bake folder reads too). */
export async function loadCached(folder, key, nLevels) {
    if (!folder) return null;
    const [files, meta] = paths(folder, key, nLevels);
    if (!exists(meta) || !files.every(exists)) return null;
    const { NpzFile } = await import('../api.js');
    const out = [];
    for (const p of files) out.push(new LevelStore(await NpzFile.open(p)));
    const info = JSON.parse(await Deno.readTextFile(meta));
    try {
        const now = new Date();
        await Deno.utime(meta, now, now);
    } catch (_e) { /* a read-only cache */ }
    return [out, info];
}

/** Write a bake to its cache folder (each level atomically, the json last) and delete the folder's surface bakes
 * beyond the newest `keep`. baked: per level a Map name -> npArray (as bake.js reads them back). */
export async function saveCached(folder, key, baked, info, keep = KEEP_BAKES) {
    if (!folder) return;
    await Deno.mkdir(folder, { recursive: true });
    const [files, meta] = paths(folder, key, baked.length);
    for (let i = 0; i < baked.length; i++) {
        const tmp = files[i] + '.tmp.npz';
        await Io.writeNpz(tmp, [...baked[i].entries()]);
        await Deno.rename(tmp, files[i]);
    }
    await Deno.writeTextFile(meta + '.tmp', JSON.stringify(plain(info), null, 1));
    await Deno.rename(meta + '.tmp', meta);
    await pruneBakes(folder, keep);
}

/** Delete a folder's surface bakes (and their palette bakes) beyond the `keep` most recently used. */
export async function pruneBakes(folder, keep = KEEP_BAKES) {
    const metas = [];
    for (const e of Deno.readDirSync(folder)) {
        if (e.isFile && e.name.startsWith('surface_') && e.name.endsWith('.json') && !e.name.includes('_pal')) {
            metas.push([Deno.statSync(`${folder}/${e.name}`).mtime?.getTime() ?? 0, e.name]);
        }
    }
    metas.sort((a, b) => b[0] - a[0]);
    for (const [, nm] of metas.slice(keep)) {
        const k = nm.slice('surface_'.length, -'.json'.length);
        for (const e of Deno.readDirSync(folder)) {
            if (e.isFile && e.name.startsWith(`surface_${k}`)) {
                try {
                    await Deno.remove(`${folder}/${e.name}`);
                } catch (_e) { /* gone already */ }
            }
        }
    }
}


// ----------------------------------------------------------------------------------------------- the call ---

/** A terrain's SurfaceData (module doc). Cached by the terrain's key, the bake's code and its options. */
export async function bakeSurface(terrain, opts = {}) {
    let { palette = null, options = null, cache = true, extra = null } = opts;
    const log = opts.log === undefined ? console.log : opts.log;
    const t0 = performance.now();
    const info0 = terrain.info ?? {};
    if (palette === 'auto' && info0.palette !== null && info0.palette !== undefined && info0.palette !== 'auto') palette = info0.palette;
    const pal = palette !== null ? await B.resolvePalette(terrain, palette) : null;
    const bopts = await B.resolveOptions(terrain, pal, options);
    const key = await B.bakeKey(terrain, bopts);
    const folder = await cacheFolder(terrain, cache);
    const n = terrain.levels.length;
    const hit = await loadCached(folder, key, n);
    let baked, info;
    if (hit) {
        [baked, info] = hit;
        info = { ...info, cache_hit: true, load_seconds: +((performance.now() - t0) / 1000).toFixed(3) };
        if (log) log(`[surface] bake ${key.slice(0, 10)}: cache hit, ${n} levels in ${info.load_seconds} s`);
    } else {
        const r = await B.bakeLevels(terrain, bopts, { log, renderer: opts.renderer ?? null });
        baked = r.levels;
        const refs = { strata: [], src_strata: [] };
        for (const m of baked) {
            refs.strata.push(m.has('_ref_strata_dz') ? Number(m.get('_ref_strata_dz').data[0]) : 0.0);
            refs.src_strata.push(m.has('_ref_src_dz') ? Number(m.get('_ref_src_dz').data[0]) : 0.0);
        }
        info = { ...r.info, cache_hit: false, key, terrain: await B.terrainKey(terrain), options: bopts,
            names: baked.map((m) => [...m.keys()].filter((k) => !k.startsWith('_')).sort()), refs };
        const t1 = performance.now();
        await saveCached(folder, key, baked, info);
        if (folder && cache === true) await pruneRoot();
        info.save_seconds = +((performance.now() - t1) / 1000).toFixed(3);
        if (log) log(`[surface] bake ${key.slice(0, 10)}: ${n} levels in ${info.seconds} s` + (folder ? ` (saved in ${info.save_seconds} s to ${folder})` : ' (in memory)'));
    }
    const sd = new SurfaceData(terrain, baked, info, bopts, key, pal, null, folder);
    sd._palettes = await B.palettesModule();
    if (extra) sd.addMaps(extra);
    if (pal !== null && (bopts.maps ?? 'all') === 'all') {
        try {
            await sd.bakePalette(pal, { cache: folder, log });
        } catch (e) {
            // the palette bake's pieces are not all there yet (__init__.py's ImportError)
            if (!/Module not found|Cannot find module|ERR_MODULE_NOT_FOUND/.test(String(e?.message ?? e))) throw e;
            sd.info.palette_bake = `skipped: ${e?.message ?? e}`;
            if (log) log(`[surface] no palette bake: ${e?.message ?? e}`);
        }
    }
    sd.info.seconds_total = +((performance.now() - t0) / 1000).toFixed(3);
    return sd;
}

export {
    bakeSurface as bake_surface, cacheFolder as cache_folder, loadCached as load_cached, saveCached as save_cached,
    pruneBakes as prune_bakes, LevelStore,
};
