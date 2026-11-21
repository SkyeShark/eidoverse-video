// Port of blender/eidoblend/terrain/build/plants.py at f9fba8c.
//
// Plant placement on the terrain (SURFACING_DESIGN.md section 4): an ecotope's rules (build/ecotopes.js) turned into
// spots, the places where single plants stand: position, yaw, scale, age, species, individual and tint. The per-
// candidate work runs as GPU compute kernels (kernels/plants/*.wgsl, through core/gpu.js); JavaScript keeps the
// species loop, the control and the files (PORT_PLAN.md 3.5). build/plant_instances.js instances the spots in a
// three.js scene, and the saved spots are the file both editions read.
//
//     import * as PL from './build/plants.js';
//     const spots = await PL.planPlants(t, { ecotope: 'auto', focus: [x, z], seed: 0, data: sd });   // t: a Terrain
//     spots.names()                         // ['spruce', 'maple', 'meadow grass', ...]
//     spots.array('spruce')                 // Float32Array, 12 numbers a spot: x, y, z, yaw, scale, age, tint, nx,
//                                           // ny, nz, variant, level (Blender frame, as the saved records)
//     spots.field('spruce', 'scale')        // one column
//     spots.stats.spruce                    // candidates, kept, stems per hectare where the species is at home, ...
//     await spots.save('<dir>/valley')      // <dir>/valley.plants.json and valley.plants.<species>.f32
//     const s2 = await PL.PlantSpots.load('<dir>/valley', { terrain: t, data: sd })
//     await spots.cover('main')             // { canopy, canopy_expected, canopy_far, shrubs, shrubs_far, grass, grass_far }
//     sd.addMaps(await spots.coverExtra())  // every level's rasters into the terrain's surface data (P14's SurfaceData)
//     await PL.expectedCover(t, { data: sd })   // with no plan: { canopy_expected: [per level], canopy_far, shrubs, ... }
//
// plants.py's module doc says how a spot is placed, so the result can be trusted: candidates from a Thomas cluster
// process per world cell, every draw a hash of the cell, the species' name and the two seeds; the density (a mask
// expression read on the coarse levels, so stems per hectare never step at a hero window's edge) as a rejection;
// the exclusions on the finest level holding the point; the hard core as sequential inhibition in the order of the
// marks, checked by the margin test; size from a Weibull age; the view (radius, distance thinning, fade band,
// max_count); heights and normals from the rendered triangles. The saved format is SURFACING_DESIGN.md 4.5's.
//
// Frames: everything here is Blender's (x east, y north, metres; arrays [row j, column i], row 0 south), as the
// spots files and plants.py are. The options that meet a scene take three.js ground points ([x, z], z south; a
// three.js position [x, y, z]; an Object3D) and convert them (PORT_PLAN.md 2.2); exclude discs are three.js too.
//
// Where this differs from plants.py, and why:
//   - Every per-candidate and per-texel step is a GPU kernel (the edition's rule, PORT_PLAN.md 2.3 and 3.5):
//     candidates per world cell with splitmix64's finaliser emulated as u32 pairs (bit-exact; each uniform kept as
//     its 53-bit integer, compared with an f32 threshold exactly), the Poisson counts by inversion against integer
//     thresholds made in doubles (bit-exact), the density from the expression compiled into a kernel
//     (surface/mask_expr.js's Compiler with palettes.py's own scatter noise, kernels/plants/lib.wgsl, in place of the
//     shader noise the material reads), the maps sampled bilinearly as _Points.sample reads them, the exclusions, the
//     shade and the feet by a hashed grid, the hard core as rounds of the same parallel algorithm _hard_core runs
//     (its certainty rule included), ages, sizes, yaw and tint, the view, heights by build/mesh.js heightField and
//     normals by the same triangle rule (kernels/plants/ground_normal.wgsl), the derived rasters (n20, dist_channel,
//     dist_water, fall_streak) and the cover rasters. Float work is float32 where plants.py's is float64: a decision
//     can differ only where its comparison is a near-tie in float32 (the parity grade of PORT_PLAN.md 10.2: counted
//     by tests/plants/spots_test.mjs against Blender's spots files).
//   - Positions are carried as an integer part and a fraction per axis (metres; kernels/plants/lib.wgsl): a float32
//     world coordinate holds a millimetre at 10 km, and the hard core's distances and the noise lattice of a 1.5 m
//     octave need far less. The lattice coordinate of the scatter noise is made in fixed point from them.
//   - The candidates' order is plants.py's (world cells row by row, then parents, then offspring), so the records come
//     out in the order Blender writes them; the hard core needs no sort: a kernel compares (mark, id) pairs, the
//     order lexsort's keys give (x and y, lexsort's last keys, never decide between two candidates of distinct ids).
//   - Sums the GPU makes (the shade's product of crowns, the kept-cover profile) run in a fixed order or in integers,
//     so a plan gives the same bytes every run; their order is not plants.py's (float64 there, float32 here).
//   - planPlants, expectedCover, PlantSpots.load, cover and coverExtra are async (GPU readbacks, files); the options
//     are one object in the edition's camelCase (radiusM; snake_case accepted).
//   - cacheBase hashes this edition's plant code (build/plants.js, ecotopes.js, palettes.js), as plants.py hashes its
//     own: a cache entry of one edition is never taken for the other's.

import { createHash } from 'node:crypto';
import * as E from './ecotopes.js';
import * as P from './palettes.js';
import * as ops from './ops.js';
import * as G from '../core/gpu.js';
import { prims, lineGroups } from '../core/prims.js';
import { pyRound, KeyError, ValueError, pyReprValue } from '../core/levels.js';
import { Compiler } from '../surface/mask_expr.js';
import { gaussianBlur } from '../masks.js';

export const FORMAT = 'eidoverse-terrain-plants/1';
export const FIELDS = Object.freeze(['x', 'y', 'z', 'yaw', 'scale', 'age', 'tint', 'nx', 'ny', 'nz', 'variant', 'level']);
// names the density expressions may read beyond the masks and the surface bake's maps (ecotopes.js describes them)
export const DERIVED_NAMES = Object.freeze(['site', 'slope_20m', 'northness_20m', 'eastness_20m', 'soil', 'insolation',
    'dist_channel', 'dist_water', 'fall_streak', 'shade', 'ledge']);
export const STEEP_DEG = 60.0;          // no plant stands on its own cell steeper than this (unless it grows on rock)
// the cover rasters a plan gives the surface bake (PlantSpots.cover), of which coverExtra hands over those its map
// registry knows; and the kind of plant each cover kind counts
export const COVER_MAPS = Object.freeze(['canopy', 'canopy_expected', 'canopy_far', 'shrubs', 'shrubs_far', 'grass', 'grass_far']);
export const COVER_KIND = Object.freeze({ tree: 'tree', shrub: 'shrub', grass: 'grass', forb: 'grass', groundcover: 'grass' });
export const CORE_FACTOR = 0.75;        // two plants stand no closer than this x the sum of their radii (flora's rule)
export const PAD_CORES = 12.0;          // the margin generated around a planned radius, in hard-core distances
export const DIST_CHANNEL_CAP_M = 400.0; // dist_channel reads at most this
export const DIST_WATER_CAP_M = 800.0;  // dist_water reads at most this
export const SHADE_CHUNK = 1000000;     // (plants.py's chunked shade pass; the GPU pass needs no chunks)
export const STREAK_NOISE_M = 120.0;    // fall_streak: the noise's feature size across the fall line, metres
export const STREAK_HALF_M = 240.0;     // and how far it is smeared down and up the fall line from each point, metres
export const PATH_GAP_M = 600.0;        // a focus's consecutive points farther apart than this are separate views
export const KEPT_BINS = 48;            // distance bands of the kept-cover profile (_view), across a species' radius
export const FRAME = Object.freeze({
    axes: 'x east, y north, z up, metres (Blender)',
    three: 'position (x, z, -y)',
    yaw: 'radians about +z, counter-clockwise from +x; three rotation.y = yaw',
    size: 'a plant stands scale * size_m[1] metres tall: scale the grown individual (source seeds[variant]) to it',
    normal: '(nx, ny, nz) the ground normal at the spot, unit, Blender axes; three (nx, nz, -ny)',
    level: 'the index in terrain.levels of the finest level holding the spot',
});
// the spot fields each instancer turns into what it draws (SURFACING_DESIGN.md 4.6)
export const HONOURED = Object.freeze({ flora: ['x', 'y', 'z', 'scale'], ph: ['x', 'y', 'z', 'scale'],
    seedthree: ['x', 'y', 'z', 'yaw', 'scale', 'variant', 'tint'] });


// ----------------------------------------------------------------------------------------------- hashing ---
// Every random draw is a hash (splitmix64's finaliser over a chain of keys) turned into a uniform number. The GPU
// kernels compute them (kernels/plants/lib.wgsl, u64 as u32 pairs); these are the same in BigInt, for the chain
// prefixes and stream constants the kernels take, and for the tests.

const M64 = (1n << 64n) - 1n;
export const GOLD = 0x9E3779B97F4A7C15n;
export const MIX1 = 0xBF58476D1CE4E5B9n;
export const MIX2 = 0x94D049BB133111EBn;
export const H0 = 0x243F6A8885A308D3n;

/** splitmix64's finaliser (plants.py _mix) on a BigInt. */
export function mix64(z) {
    z = ((z ^ (z >> 30n)) * MIX1) & M64;
    z = ((z ^ (z >> 27n)) * MIX2) & M64;
    return z ^ (z >> 31n);
}

/** A u64 key as plants.py makes one of an integer: k.astype(np.int64).astype(np.uint64) (two's complement). */
export const key64 = (k) => BigInt.asUintN(64, BigInt(k));

/** plants.py _h(*keys) for scalar keys: the chain's hash (a BigInt). */
export function hashChain(...keys) {
    let h = H0;
    for (const k of keys) h = mix64(((h ^ (typeof k === 'bigint' ? k : key64(k))) + GOLD) & M64);
    return h;
}

/** plants.py _u(h, stream) as its 53-bit integer (u = k / 2^53). */
export function u53(h, stream) {
    const z = mix64((h + BigInt(stream) * GOLD + MIX2) & M64);
    return z >> 11n;
}

/** plants.py _u(h, stream) as the float64 it is. */
export const uniform = (h, stream) => Number(u53(h, stream)) * (1.0 / 9007199254740992.0);

/** plants.py _name_key: the first 8 bytes of the SHA-1 of the name (UTF-8), little-endian. */
export function nameKey(name) {
    const d = createHash('sha1').update(String(name), 'utf8').digest();
    let v = 0n;
    for (let i = 7; i >= 0; i--) v = (v << 8n) | BigInt(d[i]);
    return v;
}

/** A u64 BigInt as the [hi, lo] u32 pair the kernels take. */
export const pair64 = (v) => [Number((v >> 32n) & 0xFFFFFFFFn), Number(v & 0xFFFFFFFFn)];

/** plants.py _poisson's table as integer thresholds: entry k is ceil(cdf_k x 2^53), so the count of a 53-bit uniform
 * U is the number of entries at or below U (np.searchsorted(cdf, U / 2^53, side='right'), exactly). The cdf is
 * numpy's arithmetic in doubles (its cumsum is sequential, as here). */
export function poissonThresholds(mean) {
    mean = Number(mean);
    if (!(mean > 0.0)) return [];
    const kmax = Math.trunc(mean + 12.0 * Math.sqrt(mean) + 24.0);
    const lm = Math.log(mean);
    let cl = 0.0, cdf = 0.0;
    const out = [];
    for (let k = 0; k <= kmax; k++) {
        if (k > 0) cl += Math.log(k);
        const logp = -mean + k * lm - cl;
        cdf += Math.exp(logp);
        out.push(Math.ceil(cdf * 9007199254740992.0));
    }
    return out;
}


// ------------------------------------------------------------------------------------------- the ground ---

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

/** plants.py _smooth: Hermite between e0 and e1 (doubles). */
export function smooth(e0, e1, x) {
    const t = Math.min(Math.max((x - e0) / (e1 - e0), 0.0), 1.0);
    return t * t * (3.0 - 2.0 * t);
}

/** Metres from a point to the focus (plants.py path_distance, one point, Blender frame): a point, or the path through
 * the focus' points in order; two consecutive points farther apart than PATH_GAP_M are separate views. */
export function pathDistance(focus, x, y) {
    const f = focus;
    let d = Math.hypot(x - f[0][0], y - f[0][1]);
    for (let k = 0; k + 1 < f.length; k++) {
        const a = f[k], b = f[k + 1];
        const abx = b[0] - a[0], aby = b[1] - a[1];
        const L2 = abx * abx + aby * aby;
        if (L2 > PATH_GAP_M * PATH_GAP_M) {
            d = Math.min(d, Math.hypot(x - b[0], y - b[1]));
            continue;
        }
        if (L2 <= 0.0) continue;
        const t = Math.min(Math.max(((x - a[0]) * abx + (y - a[1]) * aby) / L2, 0.0), 1.0);
        d = Math.min(d, Math.hypot(x - (a[0] + t * abx), y - (a[1] + t * aby)));
    }
    return d;
}

// a focus given in the scene's frame as Blender ground points [[x, y], ...]: [x, z] (three.js ground), a three.js
// position [x, y, z], an Object3D (its world position), or a list of them; a Blender list ({ blender: [[x, y], ...] })
// as it is (what a saved plan's meta holds)
export function focusPoints(focus) {
    if (focus === null || focus === undefined) return null;
    if (isObj(focus) && Array.isArray(focus.blender)) return focus.blender.map((p) => [Number(p[0]), Number(p[1])]);
    const one = (p) => {
        if (p && p.isObject3D) {
            const v = p.getWorldPosition ? p.getWorldPosition(new p.position.constructor()) : p.position;
            return [Number(v.x), -Number(v.z)];
        }
        if (p && (p.isVector3 || p.isVector2)) return p.isVector3 ? [Number(p.x), -Number(p.z)] : [Number(p.x), -Number(p.y)];
        if (Array.isArray(p) && p.length >= 2) return p.length > 2 ? [Number(p[0]), -Number(p[2])] : [Number(p[0]), -Number(p[1])];
        throw new TypeError(`focus: a ground point [x, z], a position [x, y, z], an Object3D or a list of them; got ${JSON.stringify(p)}`);
    };
    if (Array.isArray(focus) && focus.length && (Array.isArray(focus[0]) || focus[0]?.isObject3D || focus[0]?.isVector3)) {
        return focus.map(one);
    }
    return [one(focus)];
}

/** The terrain constants (palettes CONSTANTS) of a Terrain: its base elevation, its snowline and treeline from its
 * recipe's mask parameters, its real place's (palettes PLACES) or its knobs, and a real place's latitude (plants.py
 * terrain_constants). */
export async function terrainConstants(terrain) {
    const info = terrain?.info ?? {};
    const knobs = terrain?.knobs ?? {};
    const out = {};
    if (info.base_elevation_m !== null && info.base_elevation_m !== undefined) out.base_elevation_m = Number(info.base_elevation_m);
    const mp = {};
    const R = terrain?.recipe ?? null;
    const dfl = { ...(R?.defaults ?? {}) };
    const hook = R?.defaultsFor ?? R?.defaults_for ?? null;
    if (hook) {
        try {
            Object.assign(dfl, await hook(knobs, {}));
        } catch (_e) { /* a recipe whose defaults need what the Terrain no longer has */ }
    }
    Object.assign(mp, dfl.mask_params ?? {});
    const place = info.place ?? knobs.dem;
    if (typeof place === 'string' && place in P.PLACES) {
        Object.assign(mp, P.PLACES[place].mask_params ?? {});
        if (P.PLACES[place].latitude_deg !== null && P.PLACES[place].latitude_deg !== undefined) {
            out.latitude_deg = Number(P.PLACES[place].latitude_deg);
        }
    }
    for (const key of ['snowline_m', 'treeline_m']) {
        if (knobs[key] !== null && knobs[key] !== undefined) mp[key] = knobs[key];
        if (mp[key] !== null && mp[key] !== undefined) out[key] = Number(mp[key]);
    }
    return out;
}

/** The terrain constants a plan reads: the palette's (palettes CONSTANTS filled in), the terrain's own
 * (terrainConstants) and the ecotope's (plants.py _constants). */
export async function planConstants(terrain, eco = null) {
    const info = terrain?.info ?? {};
    let consts;
    try {
        const pal = info.palette;
        consts = { ...P.get(pal !== null && pal !== undefined ? pal : 'auto', terrain?.recipe ?? null, false).constants };
    } catch (_e) {
        consts = { ...P.CONSTANTS };
    }
    Object.assign(consts, await terrainConstants(terrain));
    Object.assign(consts, eco?.constants ?? {});
    return consts;
}

// an ecotope as plan_plants takes it: a resolved one as it is, else ecotopes.get with the terrain's recipe, place and
// palette (plants.py _resolve, _resolved)
function resolved(ecotope) {
    return isObj(ecotope) && Array.isArray(ecotope.species) && ecotope.species.length > 0 && 'priority' in ecotope.species[0] &&
        'cluster' in ecotope.species[0] && Array.isArray(ecotope.species[0].source) && ecotope.species[0].source.length === 4;
}

export function resolveEcotope(terrain, ecotope = 'auto') {
    const info = terrain?.info ?? {};
    if (resolved(ecotope)) return ecotope;
    return E.get(ecotope, terrain?.recipe ?? null, info.place ?? null, info.palette ?? null);
}

/** A species' file name part (plants.py _file_part). */
export const filePart = (name) => String(name).replace(/[^A-Za-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '') || 'species';

/** Python's round(x, n) of a float: the decimal rounding of x's exact value, a tie to the even digit. */
export function pyRoundN(x, n) {
    if (!Number.isFinite(x) || Math.abs(x) >= 1e21) return x;
    const neg = x < 0;
    const [ip, fp] = Math.abs(x).toFixed(100).split('.');
    const keep = fp.slice(0, n), rest = fp.slice(n);
    let up = rest[0] > '5';
    if (rest[0] === '5') up = /[1-9]/.test(rest.slice(1)) || Number((ip + keep).slice(-1)) % 2 === 1;
    let digits = (BigInt(ip + keep) + (up ? 1n : 0n)).toString().padStart(n + 1, '0');
    const v = Number(n ? `${digits.slice(0, digits.length - n)}.${digits.slice(digits.length - n)}` : digits);
    return neg ? -v : v;
}


// ===================================================================================== the GPU planner ===

const f32 = Math.fround;
const CAND = 16;                        // a candidate's record, numbers (kernels/plants/offspring.wgsl)
const PAR = 8;                          // a cluster centre's record (kernels/plants/parents.wgsl)
const PLACED = 8;                       // a placed plant in the feet and shade lists (kernels/plants/placed_list.wgsl)
const MIS_CHECK = 8;                    // hard-core rounds between two counts of the undecided
const F32B = new Float32Array(1), U32B = new Uint32Array(F32B.buffer);
const fbits = (v) => { F32B[0] = v; return U32B[0]; };
const bitsf = (b) => { U32B[0] = b >>> 0; return F32B[0]; };
const intOf = (u) => u | 0;

/** [integer part, fraction] of a coordinate in metres (the kernels' positions), the fraction rounded to float32. */
export function splitCoord(v) {
    const i = Math.floor(v);
    return [i, f32(v - i)];
}

// round(v 2^F) as the [hi, lo] int bits of a u64 (an ivec2 uniform)
function fixedBits(v, F) {
    const big = BigInt(Math.round(v * 2 ** F));
    return [Number(BigInt.asIntN(32, big >> 32n)), Number(BigInt.asIntN(32, big & 0xFFFFFFFFn))];
}
const u64Bits = (b) => [Number(BigInt.asIntN(32, b >> 32n)), Number(BigInt.asIntN(32, b & 0xFFFFFFFFn))];
// the fraction bits of a noise term's fixed-point reciprocal 2^F / s: |x| W stays under 2^63 for |x| < 2^15 m
const noiseBits = (s) => Math.max(32, Math.min(56, 47 + Math.floor(Math.log2(Math.max(s, 1e-9)))));
const wgslF = (v) => {
    const x = f32(v);
    if (!Number.isFinite(x)) return x > 0 ? '3.4e38' : '-3.4e38';
    let s = String(x);
    if (!/[.eE]/.test(s)) s += '.0';
    return s;
};

/** The planner's GPU helpers: lists, kernels by name, scans, compaction, counts. */
class Gpu {
    constructor(R) {
        this.R = R;
        this.P = prims(R);
        this.dummyU = R.field(1, 1, 1, null, 'u32');
        this.dummyF = R.field(1, 1, 1);
        this.held = [];
    }

    k(name) { return this.R.kernel(`plants/${name}`); }

    list(n, kind = 'u32', data = null) { return this.P.list(Math.max(1, n), kind, data); }

    hold(f) { this.held.push(f); return f; }

    run(name, s, im, un, count) {
        if (count <= 0) return;
        this.R.run(typeof name === 'string' ? this.k(name) : name, s, im, un, lineGroups(count));
    }

    /** The exclusive scan of n u32 counts and their total (one wait). */
    async scan(counts, n) {
        const offs = this.P.cumsum(counts, { count: n, exclusive: true });
        const [a, b] = await this.R.readParts([{ field: offs, first: n - 1, count: 1 }, { field: counts, first: n - 1, count: 1 }]);
        return { offs, total: a[0] + b[0] };
    }

    /** The records (stride numbers each) whose 0/1 flag is set, in order: { list, n }. */
    async compact(flags, n, src, stride) {
        if (!n) return { list: this.list(stride), n: 0 };
        const { index, n: m } = await this.P.nonzero(flags, { count: n });
        const out = this.list(Math.max(m, 1) * stride);
        this.run('gather_rec', { src, index }, { outR: out }, { uStride: stride, uCount: m, uFirst: 0 }, m);
        index.destroy();
        return { list: out, n: m, index: null };
    }

    /** A u32 list of n items, every one `value`. */
    fillU32(n, value) {
        const out = this.list(n);
        this.run('fill_u32', {}, { outV: out }, { uValue: intOf(value), uCount: n }, n);
        return out;
    }

    /** A 0/1 list of the items in [lo, hi) whose flags hold `mask` (and none of `not`). */
    bit(flags, n, mask, not = 0, lo = 0, hi = null) {
        const out = this.list(n);
        this.run('bit', { flags, lvt: this.dummyF }, { outB: out }, { uMask: intOf(mask), uNot: intOf(not), uLo: lo,
            uHi: hi ?? n, uMaxCell: 0, uCount: n }, n);
        return out;
    }

    /** Counts of (flags & mask) == mask per mask (at most 8), and the largest of vals over the items holding maxMask. */
    async tally(flags, n, masks, vals = null, maxMask = 0) {
        const out = this.list(9);
        const m = [...masks, 0, 0, 0, 0, 0, 0, 0, 0].slice(0, 8).map(intOf);
        this.run('tally', { flags, vals: vals ?? this.dummyF }, { outT: out },
            { uM0: m.slice(0, 4), uM1: m.slice(4, 8), uMaxMask: intOf(maxMask), uCount: n }, n);
        const a = await this.R.readRange(out, 0, 9);
        out.destroy();
        return { counts: Array.from(a.slice(0, masks.length)), max: bitsf(a[8]) };
    }

    /** A hashed grid of n points (records of `stride`, the position at `pos`) in cells of `cell` metres about the
     * origin [xi, xf, yi, yf]: { uniforms, starts, counts, index }. */
    grid(recs, n, stride, pos, cell, origin) {
        const P = this.P;
        let T = 1024;
        while (T < 2 * n) T *= 2;
        const un = { uGO: origin, uGW: fixedBits(1.0 / cell, 40), uGInv: f32(1.0 / cell), uGMask: T - 1 };
        const keys = this.list(n);
        this.run('grid_key', { rec: recs }, { outK: keys }, { ...un, uStride: stride, uPos: pos, uCount: n }, n);
        const { keys: sk, vals } = P.sortPairs(keys, null, { count: n, bits: Math.log2(T) });
        sk.destroy();
        const counts = P.bincount(keys, T, { count: n });
        keys.destroy();
        const starts = P.cumsum(counts, { count: T, exclusive: true });
        return { un, starts, counts, index: vals, destroy() { starts.destroy(); counts.destroy(); vals.destroy(); } };
    }

    destroy() {
        for (const f of this.held) if (!f.destroyed) f.destroy();
        this.held.length = 0;
        this.dummyU.destroy();
        this.dummyF.destroy();
    }
}

/** What the planner reads of a terrain (plants.py _Ground): its levels, each level's maps (its masks; with a surface
 * bake, everything SurfaceData.maps gives a level), the derived rasters, and the constants; uploaded to the GPU per
 * map as the reads need them. */
class Ground {
    constructor(gpu, terrain, data, consts) {
        this.g = gpu;
        this.R = gpu.R;
        this.terrain = terrain;
        this.data = data;
        this.constants = { ...E.CONSTANTS, ...(consts ?? {}) };
        this.levels = terrain.levels.map((lv, i) => ({ index: i, role: String(lv.role ?? 'main'), x0: Number(lv.x0),
            y0: Number(lv.y0), side: Number(lv.side), cell: Number(lv.cell), n: Math.trunc(Number(lv.n)) }));
        this.coarse = this.levels.filter((lv) => lv.role !== 'hero').map((lv) => lv.index);
        if (!this.coarse.length) this.coarse = [0];
        this.all = this.levels.map((lv) => lv.index);
        const lv0 = this.levels[0];
        this.bounds = [lv0.x0, lv0.y0, lv0.x0 + lv0.side, lv0.y0 + lv0.side];
        this.notes = [];
        this._maps = new Map();
        this._stacks = new Map();
        this._derived = {};
        this._lvt = null;
        this._n20 = null;
        this._streak = null;
        this._dist = {};
        this.site = P.parse(E.SITE);
    }

    /** Level i's maps: SurfaceData.maps(i) with a bake (the masks, the bake's maps, the plant rasters), else the
     * masks. */
    async maps(i) {
        if (!this._maps.has(i)) {
            let m;
            if (this.data) {
                m = await this.data.maps(i);
            } else {
                const mk = this.terrain.masks.level(i);
                m = {};
                for (const k of Object.keys(mk)) m[k] = mk[k];
            }
            this._maps.set(i, m);
        }
        return this._maps.get(i);
    }

    /** The level table plants/locate reads (12 numbers a level). */
    lvt() {
        if (!this._lvt) {
            const t = new Float32Array(12 * this.levels.length);
            this.levels.forEach((lv, k) => {
                const [a, b] = splitCoord(lv.x0), [c, d] = splitCoord(lv.y0);
                const [e, f] = splitCoord(lv.x0 + lv.side), [g, h] = splitCoord(lv.y0 + lv.side);
                t.set([a, b, c, d, e, f, g, h, lv.role !== 'hero' ? 1 : 0, lv.cell, lv.n, 0], 12 * k);
            });
            this._lvt = this.g.hold(this.g.list(t.length, 'f32', t));
        }
        return this._lvt;
    }

    /** Points' levels: { fine, coarse } (u32 lists), records of `stride` with the position at `pos`. */
    locate(pts, n, stride = CAND, pos = 0) {
        const fine = this.g.list(n), coarse = this.g.list(n);
        this.g.run('locate', { rec: pts, lvt: this.lvt() }, { outF: fine, outC: coarse },
            { uStride: stride, uPos: pos, uLevels: this.levels.length, uCount: n }, n);
        return { fine, coarse };
    }

    // a name's arrays per level: a derived raster's, else the level's map
    async arrays(name) {
        if (this._derived[name]) return this._derived[name];
        const out = [];
        for (let i = 0; i < this.levels.length; i++) {
            const a = (await this.maps(i))[name];
            out.push(a && a.length && !a.shape3 ? a : null);
        }
        return out;
    }

    /** Whether any level has a map (plants.py: a name no level has reads None, and then 0). */
    async has(name) {
        return (await this.arrays(name)).some((a) => a !== null);
    }

    /** A map's rasters uploaded for points located on the levels of `located`, with _Points.sample's fallback:
     * { stack, tab }, or null when no level has the map. */
    async stack(name, located) {
        const key = `${name}|${located.join(',')}`;
        if (this._stacks.has(key)) return this._stacks.get(key);
        const s = this.stackOf(await this.arrays(name), located);
        this._stacks.set(key, s);
        return s;
    }

    stackOf(arrays, located) {
        const L = this.levels.length;
        const fb = arrays.map((a, i) => {
            if (a) return i;
            for (let j = i - 1; j >= 0; j--) if (arrays[j]) return j;
            for (let j = i + 1; j < L; j++) if (arrays[j]) return j;
            return -1;
        });
        if (fb.every((j) => j < 0)) return null;
        const need = [...new Set(located.map((i) => fb[i]).filter((j) => j >= 0))].sort((a, b) => a - b);
        let total = 0;
        const first = new Map();
        for (const j of need) {
            first.set(j, total);
            total += arrays[j].length;
        }
        const data = new Float32Array(Math.max(total, 1));
        for (const j of need) data.set(arrays[j], first.get(j));
        const tab = new Uint32Array(12 * L);
        for (let i = 0; i < L; i++) {
            tab[12 * i + 2] = Math.max(fb[i], 0);
            if (!first.has(i)) continue;
            const lv = this.levels[i];
            const nr = Math.round(Math.sqrt(arrays[i].length));
            const texel = lv.side / nr;
            const [whi, wlo] = fixedBits(1.0 / texel, 40);
            const [xi, xf] = splitCoord(lv.x0), [yi, yf] = splitCoord(lv.y0);
            tab.set([first.get(i), nr, Math.max(fb[i], 0), whi >>> 0, wlo >>> 0, fbits(f32(1.0 / texel)), fbits(xi), fbits(xf),
                fbits(yi), fbits(yf), 0, 0], 12 * i);
        }
        const out = { stack: this.g.list(data.length, 'f32', data), tab: this.g.list(tab.length, 'u32', tab) };
        this.g.hold(out.stack);
        this.g.hold(out.tab);
        return out;
    }

    /** One map at located points (plants/sample): an f32 list, or null when no level has it. */
    async sample(name, pts, n, lvl, located, stride = CAND, pos = 0) {
        const st = await this.stack(name, located);
        if (!st) return null;
        return this.sampleStack(st, pts, n, lvl, stride, pos);
    }

    sampleStack(st, pts, n, lvl, stride = CAND, pos = 0) {
        const out = this.g.list(n, 'f32');
        this.g.run('sample', { rec: pts, lvl, stack: st.stack, tab: st.tab }, { outV: out },
            { uStride: stride, uPos: pos, uCount: n }, n);
        return out;
    }

    /** The texel centres of an m x m raster over level i's window as position records (4 numbers a point). */
    gridPoints(i, m) {
        const lv = this.levels[i];
        const half = lv.side / m / 2.0;
        const F = Math.max(32, Math.min(56, 50 - Math.ceil(Math.log2(Math.max(half, 1e-9)))));
        const [xi, xf] = splitCoord(lv.x0), [yi, yf] = splitCoord(lv.y0);
        const out = this.g.list(4 * m * m);
        this.g.run('grid_points', {}, { outP: out }, { uO: [xi, xf, yi, yf], uH: fixedBits(half, F), uF: F, uM: m }, m * m);
        return out;
    }

    // ---- the derived rasters (the coarse levels' only, as plants.py's)

    /** Per level the 20 m normal's [x, y] arrays (null on hero levels): the bake's n20 where the data holds it, else
     * the normal of the level's height blurred at 20 m, else the masks' slope and aspect (plants.py n20). */
    async n20() {
        if (this._n20) return this._n20;
        const R = this.R;
        const out = this.levels.map(() => null);
        for (const i of this.coarse) {
            const m = await this.maps(i), lv = this.levels[i];
            if (m.n20_x && m.n20_y) {
                out[i] = [m.n20_x, m.n20_y];
                continue;
            }
            let h = null;
            try {
                h = this.terrain.fields(i).h ?? null;
            } catch (_e) {
                h = null;
            }
            const n = lv.n;
            if (h && h.length === n * n) {
                out[i] = await this.normal20(h, lv);
            } else if (m.slope && m.aspect && m.slope.length === n * n) {
                const a = R.field(n, n, 1, m.slope), b = R.field(n, n, 1, m.aspect);
                const x = R.field(n, n, 1), y = R.field(n, n, 1);
                R.run(this.g.k('n20'), { a, b }, { outX: x, outY: y }, { uMode: 2, uM: 0, uN: n, uMu: 0, uCell: lv.cell },
                    [Math.ceil(n / 16), Math.ceil(n / 16), 1]);
                out[i] = await R.readAll([x, y]);
                for (const f of [a, b, x, y]) f.destroy();
            }
        }
        if (out.every((a) => a === null)) {
            const lv = this.levels[this.coarse[this.coarse.length - 1]];
            out[lv.index] = [new Float32Array(lv.n * lv.n), new Float32Array(lv.n * lv.n)];
            this.notes.push('no height, n20 or slope on the coarse levels: densities read flat ground');
        }
        this._n20 = out;
        this._derived.n20_x = out.map((a) => (a ? a[0] : null));
        this._derived.n20_y = out.map((a) => (a ? a[1] : null));
        return out;
    }

    // plants.py _normal_20m: the masks' Gaussian (a periodic FFT) over the height padded by reflection out to 4
    // sigma, then central differences
    async normal20(h, lv) {
        const R = this.R, n = lv.n;
        const s = 20.0 / lv.cell;
        const hf = R.field(n, n, 1, h instanceof Float32Array ? h : new Float32Array(h));
        const x = R.field(n, n, 1), y = R.field(n, n, 1);
        if (s > 0.25) {
            const m = Math.min(Math.ceil(4.0 * s) + 2, n - 1);
            const mu = (await this.g.P.stats(hf)).mean;
            const w = n + 2 * m;
            const pad = R.field(w, w, 1);
            R.run(this.g.k('n20'), { a: hf, b: hf }, { outX: pad, outY: y }, { uMode: 0, uM: m, uN: n, uMu: f32(mu), uCell: lv.cell },
                [Math.ceil(w / 16), Math.ceil(w / 16), 1]);
            const blur = gaussianBlur(pad, s);
            R.run(this.g.k('n20'), { a: blur, b: hf }, { outX: x, outY: y }, { uMode: 1, uM: m, uN: n, uMu: f32(mu), uCell: lv.cell },
                [Math.ceil(n / 16), Math.ceil(n / 16), 1]);
            pad.destroy();
            blur.destroy();
        } else {
            R.run(this.g.k('n20'), { a: hf, b: hf }, { outX: x, outY: y }, { uMode: 1, uM: 0, uN: n, uMu: 0, uCell: lv.cell },
                [Math.ceil(n / 16), Math.ceil(n / 16), 1]);
        }
        const out = await R.readAll([x, y]);
        for (const f of [hf, x, y]) f.destroy();
        return out;
    }

    /** dist_channel or dist_water per level (the coarse levels'): metres to the nearest stream cell (flow at least
     * channel_flow, or with channel_mask the channels mask where the cell is 7.6 m or more) or to water over 0.05 m,
     * capped; a level takes its parent's distance where that is nearer (plants.py dist_channel, dist_water). */
    async dist(kind) {
        if (this._dist[kind]) return this._dist[kind];
        const R = this.R, g = this.g;
        const cap = kind === 'dist_channel' ? DIST_CHANNEL_CAP_M : DIST_WATER_CAP_M;
        const out = this.levels.map(() => null);
        let prev = null;
        for (const i of this.coarse) {
            const lv = this.levels[i], m = await this.maps(i), n = lv.n;
            const fit = (a) => (a && a.length === n * n ? a : null);
            const seed = R.field(n, n, 1, null, 'u32');
            let useA = 0, useB = 0, a = null, b = null, thA = 0, thB = 0, modeA = 0;
            if (kind === 'dist_channel') {
                const flow = fit(m.flow), ch = fit(m.channels);
                if (flow) { a = flow; useA = 1; thA = Number(this.constants.channel_flow); modeA = 0; }
                if (ch && lv.cell >= 7.6 && Number(this.constants.channel_mask ?? 1.0)) { b = ch; useB = 1; thB = 0.5; }
            } else {
                const w = fit(m.water);
                if (w) { a = w; useA = 1; thA = 0.05; modeA = 1; }
            }
            const fa = a ? R.field(n, n, 1, a) : g.dummyF, fb = b ? R.field(n, n, 1, b) : g.dummyF;
            R.run(g.k('seed'), { a: fa, b: fb }, { outS: seed }, { uA: thA, uB: thB, uModeA: modeA, uUseA: useA, uUseB: useB },
                [Math.ceil(n / 16), Math.ceil(n / 16), 1]);
            if (a) fa.destroy();
            if (b) fb.destroy();
            const any = (await g.P.statsU32(seed)).nonzero > 0;
            const Rc = Math.ceil(cap / lv.cell);
            const dfield = R.field(n, n, 1);
            let par = g.dummyF, usePar = 0;
            if (prev !== null) {
                const pts = this.gridPoints(i, n);
                const lvl = g.fillU32(n * n, prev);
                const arrays = this.levels.map((_, k) => (k === prev ? out[prev] : null));
                const st = this.stackOf(arrays, [prev]);
                par = this.sampleStack(st, pts, n * n, lvl, 4, 0);
                usePar = 1;
                pts.destroy();
                lvl.destroy();
            }
            if (any) {
                const gg = R.field(n, n, 1);
                R.run(g.k('dist_rows'), { seed }, { outG: gg }, { uR: Rc }, lineGroups(n));
                R.run(g.k('dist_cols'), { g: gg, par }, { outD: dfield }, { uR: Rc, uCell: lv.cell, uCap: cap, uParent: usePar },
                    [Math.ceil(n / 16), Math.ceil(n / 16), 1]);
                gg.destroy();
            } else {
                // no seed: the cap everywhere (then the parent's, where nearer)
                const gg = R.field(n, n, 1);
                g.run('one_minus_exp', { v: g.dummyF }, { outV: gg }, { uFill: 1, uValue: f32((cap / lv.cell) ** 2), uCount: n * n }, n * n);
                R.run(g.k('dist_cols'), { g: gg, par }, { outD: dfield }, { uR: 0, uCell: lv.cell, uCap: cap, uParent: usePar },
                    [Math.ceil(n / 16), Math.ceil(n / 16), 1]);
                gg.destroy();
            }
            seed.destroy();
            if (usePar) par.destroy();
            out[i] = await R.read(dfield);
            dfield.destroy();
            prev = i;
        }
        this._dist[kind] = out;
        this._derived[kind] = out;
        return out;
    }

    /** fall_streak per level (the coarse levels'): a 0..1 world noise of 120 m smeared 240 m along the 20 m normal's
     * fall line, the levels sharing one stretch (plants.py fall_streak). */
    async fallStreak() {
        if (this._streak) return this._streak;
        const R = this.R, g = this.g;
        const n20 = await this.n20();
        const raw = new Map();
        for (const i of this.coarse) {
            if (!n20[i]) continue;
            const lv = this.levels[i];
            const n = Math.round(Math.sqrt(n20[i][0].length));
            const cell = lv.side / n;
            const pts = this.gridPoints(i, n);
            const noise = R.field(n, n, 1);
            const F = noiseBits(STREAK_NOISE_M);
            g.run('noise_raster', { pts }, { outV: noise }, { uW: fixedBits(1.0 / STREAK_NOISE_M, F), uF: F,
                uInv: f32(1.0 / STREAK_NOISE_M), uN: [71, 3, 0, 0], uG: [0.5, 1.6], uCount: n * n }, n * n);
            pts.destroy();
            const nx = R.field(n, n, 1, n20[i][0]), ny = R.field(n, n, 1, n20[i][1]);
            const step = Math.max(cell, 12.0);
            const k = Math.max(Math.trunc(pyRound(STREAK_HALF_M / step)), 1);
            const r = R.field(n, n, 1);
            R.run(g.k('streak'), { nx, ny, noise }, { outV: r }, { uCell: f32(cell), uStep: f32(step), uK: k, uLoHi: [0, 0], uMode: 0 },
                [Math.ceil(n / 16), Math.ceil(n / 16), 1]);
            noise.destroy();
            raw.set(i, { r, nx, ny, n });
        }
        const out = this.levels.map(() => null);
        if (raw.size) {
            const main = [...this.coarse].reverse().find((i) => raw.has(i));
            const [lo, hi] = await g.P.percentile(raw.get(main).r, [5.0, 95.0], { dtype: 'float64' });
            for (const [i, v] of raw) {
                const o = R.field(v.n, v.n, 1);
                R.run(g.k('streak'), { nx: v.nx, ny: v.ny, noise: v.r }, { outV: o }, { uCell: 1, uStep: 1, uK: 0,
                    uLoHi: [f32(lo), f32(hi)], uMode: 1 }, [Math.ceil(v.n / 16), Math.ceil(v.n / 16), 1]);
                out[i] = await R.read(o);
                for (const f of [o, v.r, v.nx, v.ny]) f.destroy();
            }
        } else {
            this.notes.push('no 20 m normal on the coarse levels: fall_streak reads 0.5');
            const lv = this.levels[this.coarse[this.coarse.length - 1]];
            out[lv.index] = new Float32Array(lv.n * lv.n).fill(0.5);
        }
        this._streak = out;
        this._derived.fall_streak = out;
        return out;
    }

    /** Make sure the derived rasters a set of names reads exist. */
    async derive(names) {
        if (names.has('n20_x') || names.has('n20_y')) await this.n20();
        if (names.has('dist_channel')) await this.dist('dist_channel');
        if (names.has('dist_water')) await this.dist('dist_water');
        if (names.has('fall_streak')) await this.fallStreak();
    }

    /** The climatological sun's terms of the insolation (palettes.climate_sun): cos(el) sin(az), cos(el) cos(az),
     * sin(el). */
    sun() {
        const [azd, eld] = P.climateSun(this.constants);
        const az = (azd * Math.PI) / 180.0, el = (eld * Math.PI) / 180.0;
        return [Math.cos(el) * Math.sin(az), Math.cos(el) * Math.cos(az), Math.sin(el)];
    }
}


// ------------------------------------------------------------------------ a species' expressions, compiled ---

// mask_expr.js's Compiler with palettes.py's own scatter noise (value_noise, voronoi_cells: kernels/plants/lib.wgsl)
// in place of the shader noise the material reads: what plants.py's palettes.evaluate computes
class ScatterCompiler extends Compiler {
    constructor(o, read, constants, terms) {
        super({ ops: o, read, constants });
        this.terms = terms;                              // the kernel's noise helpers, in order
    }

    _noise(f, scale, seed) {
        const key = `${f}:${scale}:${seed}`;
        if (!this.noises.has(key)) {
            const fbm = f === 'fbm';
            const k = this.terms.length;
            this.terms.push({ kind: 'value', scale: Number(scale), seed: fbm ? seed + 101 : seed, octaves: fbm ? 5 : 2,
                gain: fbm ? 0.6 : 0.5, stretch: fbm ? 2.2 : 1.6 });
            this.noises.set(key, this.o.ext('f32', `nz${k}`));
        }
        return this.noises.get(key);
    }

    _cells(scale, seed, zk) {
        const key = `cells:${scale}:${seed}:${zk}`;
        if (!this.noises.has(key)) {
            const k = this.terms.length;
            this.terms.push({ kind: 'cells', scale: Number(scale), seed, zk: Number(zk) });
            const z = zk > 0.0 ? this.read('height') : this.o.f(0.0);
            this.noises.set(key, this.o.ext('f32', `nz${k}`, z));
        }
        return this.noises.get(key);
    }
}

// the WGSL of one noise helper
function noiseFn(t, k) {
    const s = Math.max(t.scale, 1e-9);
    const F = noiseBits(s);
    const W = BigInt(Math.round(2 ** F / s));
    const w = `vec2<u32>(${Number((W >> 32n) & 0xFFFFFFFFn)}u, ${Number(W & 0xFFFFFFFFn)}u)`;
    if (t.kind === 'cells') {
        return `fn nz${k}(z: f32) -> f32 { return voronoi_cells(POS, ${w}, ${F}u, ${wgslF(1.0 / s)}, ${Math.trunc(t.seed)}, z, ${wgslF(t.zk)}); }`;
    }
    return `fn nz${k}() -> f32 { return value_noise(POS, ${w}, ${F}u, ${wgslF(1.0 / s)}, ${Math.trunc(t.seed)}, ${t.octaves}, ` +
        `${wgslF(t.gain)}, ${wgslF(t.stretch)}); }`;
}

/** A species' kernel: its density, its stature and its exclusions at points (plants.py _thin's getter and fine
 * reads, _exclusions; _level_cover's with steep false). Returns { kernel, reads: [[name, 'coarse' | 'fine']] (the
 * sampler v<k> of each), shade (whether it reads the shade list) }. */
async function speciesKernel(gpu, ground, s, { steep = true } = {}) {
    const W = ops.WGSL();
    const reads = [];                                    // [name, mode]
    const index = new Map();
    const terms = [];
    const fns = [];
    let usesShade = false;
    const has = new Map();
    const exists = async (name) => {
        if (!has.has(name)) has.set(name, await ground.has(name));
        return has.get(name);
    };
    // the names to know before compiling: every mask a density may read, and the exclusions'
    const known = new Set();
    for (const n of P.namesIn(s._density)) known.add(n);
    if (s._stature) for (const n of P.namesIn(s._stature)) known.add(n);
    for (const n of P.namesIn(P.parse('bare'))) known.add(n);
    for (const n of [...known, ...P.namesIn(ground.site), 'deposit', 'talus', 'sand', 'crest', 'settle', 'snow', 'water',
        'snowpack', 'slope', 'height', 'n20_x', 'n20_y']) await exists(n);
    const sampled = (name, mode) => {
        const key = `${mode}:${name}`;
        if (!index.has(key)) {
            const k = reads.length;
            index.set(key, k);
            reads.push([name, mode]);
            fns.push(`fn rd${k}() -> f32 { return v${k}_b[Q]; }`);
        }
        return W.ext('f32', `rd${index.get(key)}`);
    };
    const memo = new Map();
    let C = null;
    const DERIVED_RASTERS = new Set(['dist_channel', 'dist_water', 'fall_streak']);
    const n20 = () => {
        if (!memo.has('_n20')) {
            const nx = sampled('n20_x', 'coarse'), ny = sampled('n20_y', 'coarse');
            const o = W;
            const g2 = o.min(o.add(o.mul(nx, nx), o.mul(ny, ny)), 0.9999);
            const slope = o.degrees(o.atan(o.sqrt(o.div(g2, o.sub(1.0, g2)))));
            const t = o.clamp(o.div(o.sub(slope, 1.0), 2.0), 0.0, 1.0);
            const sm = o.mul(o.mul(t, t), o.sub(3.0, o.mul(2.0, t)));
            const fade = o.div(sm, o.max(o.sqrt(g2), 1e-12));
            memo.set('_n20', { slope, north: o.mul(ny, fade), east: o.mul(nx, fade) });
        }
        return memo.get('_n20');
    };
    // site(): a name as every density reads it, on the coarse levels
    const site = (name) => {
        if (memo.has(name)) return memo.get(name);
        let v;
        if (name === 'shade') {
            usesShade = true;
            if (!fns.includes('fn rdshade() -> f32 { return shade_b[Q]; }')) fns.push('fn rdshade() -> f32 { return shade_b[Q]; }');
            v = W.ext('f32', 'rdshade');
        } else if (name === 'site') {
            v = C.expr(ground.site);
        } else if (name === 'slope_20m' || name === 'northness_20m' || name === 'eastness_20m') {
            const d = n20();
            v = name === 'slope_20m' ? d.slope : name === 'northness_20m' ? d.north : d.east;
        } else if (name === 'insolation') {
            const d = n20();
            const [ea, na, z] = ground.sun();
            const o = W;
            const sn = o.sin(o.radians(d.slope)), cs = o.cos(o.radians(d.slope));
            v = o.max(o.add(o.add(o.mul(o.mul(sn, d.east), ea), o.mul(o.mul(sn, d.north), na)), o.mul(cs, z)), 0.0);
        } else if (name === 'soil') {
            const o = W;
            let acc = o.f(0.0);
            for (const k of ['deposit', 'talus', 'sand']) if (has.get(k)) acc = o.add(acc, sampled(k, 'coarse'));
            if (has.get('crest')) acc = o.mul(acc, o.add(1.0, o.clamp(o.neg(sampled('crest', 'coarse')), 0.0, 1.0)));
            if (has.get('settle')) {
                const t = o.clamp(o.div(o.sub(n20().slope, 10.0), 10.0), 0.0, 1.0);
                const kk = o.mul(o.mul(t, t), o.sub(3.0, o.mul(2.0, t)));
                acc = o.mul(acc, o.add(1.0, o.mul(kk, o.sub(o.mul(2.0, sampled('settle', 'coarse')), 1.0))));
            }
            v = acc;
        } else if (name === 'ledge') {
            v = W.f(0.0);
        } else if (DERIVED_RASTERS.has(name)) {
            v = sampled(name, 'coarse');
        } else {
            v = has.get(name) ? sampled(name, 'coarse') : W.f(0.0);
        }
        memo.set(name, v);
        return v;
    };
    // what an exclusion reads: the finest level holding the point
    const fine = (name) => (has.get(name) ? sampled(name, 'fine') : null);
    C = new ScatterCompiler(W, (name) => {
        if (!has.has(name) && !DERIVED_NAMES.includes(name)) throw new Error(`plants: the name ${name} was not looked up`);
        return site(name);
    }, ground.constants, terms);
    let stature = null;
    if (s._stature) stature = C.expr(s._stature);
    const dens = W.max(C.expr(s._density), 0.0);
    // _exclusions
    const on = new Set(s.on);
    let ok = W.f(true);
    if (!on.has('water')) {
        const w = fine('water');
        if (w) ok = W.and(ok, W.le(w, 0.05));
    }
    if (!on.has('snow')) {
        const sp = fine('snowpack');
        if (sp) ok = W.and(ok, W.le(sp, 0.2));
        else if (has.get('snow')) ok = W.and(ok, W.le(site('snow'), 0.5));
    }
    if (!on.has('rock')) {
        ok = W.and(ok, W.le(C.expr(P.parse('bare')), 0.5));
        if (steep) {
            const sl = fine('slope');
            if (sl) ok = W.and(ok, W.le(sl, STEEP_DEG));
        }
    }
    for (const sub of ['talus', 'sand']) {
        if (!on.has(sub)) {
            const v = fine(sub);
            if (v) ok = W.and(ok, W.le(v, Number(s.roots_m)));
        }
    }
    for (let k = 0; k < terms.length; k++) fns.push(noiseFn(terms[k], k));
    const head = ['//! include plants/lib', '//! sampler pts r32ui     the points\' records (uStride numbers each, the position at uPos)',
        ...reads.map(([n, m], k) => `//! sampler v${k} r32f      ${m} ${n}`),
        '//! sampler shade r32f', '//! image   outD r32f', '//! image   outA r32ui', '//! image   outS r32f',
        '//! uniform int uCount', '//! uniform int uStride', '//! uniform int uPos'];
    const src = [`// the density, stature and exclusions of the species ${JSON.stringify(s.name)} (build/plants.js speciesKernel)`,
        ...head, 'var<private> Q: i32;', 'var<private> POS: vec4<f32>;', W.module(), ...fns,
        'fn kmain(p: vec2<i32>) {', '  Q = lin(p);', '  if (Q >= u.uCount) { return; }', '  let o = u32(Q * u.uStride + u.uPos);',
        '  POS = vec4<f32>(bitcast<f32>(pts_b[o]), bitcast<f32>(pts_b[o + 1u]), bitcast<f32>(pts_b[o + 2u]), bitcast<f32>(pts_b[o + 3u]));',
        W.body('  '), `  outD_b[Q] = ${W.code(dens)};`, `  outS_b[Q] = ${stature ? W.code(stature) : '1.0'};`,
        `  outA_b[Q] = select(0u, 1u, ${W.code(ok)});`, '}', ''].join('\n');
    const hash = createHash('sha1').update(src).digest('hex').slice(0, 12);
    return { kernel: gpu.R.kernel(`plants_species_${hash}`, { source: src }), reads, shade: usesShade, src };
}

/** Evaluate a species' kernel at points: { dens, allowed, stat } (lists). */
async function evaluateSpecies(gpu, ground, sk, pts, n, loc, shade, stride = CAND, pos = 0) {
    const samplers = { pts, shade: shade ?? gpu.dummyF };
    const made = [];
    for (let k = 0; k < sk.reads.length; k++) {
        const [name, mode] = sk.reads[k];
        const lvl = mode === 'fine' ? loc.fine : loc.coarse;
        const located = mode === 'fine' ? ground.all : ground.coarse;
        const v = await ground.sample(name, pts, n, lvl, located, stride, pos);
        samplers[`v${k}`] = v ?? gpu.dummyF;
        if (v) made.push(v);
    }
    const dens = gpu.list(n, 'f32'), allowed = gpu.list(n), stat = gpu.list(n, 'f32');
    gpu.run(sk.kernel, samplers, { outD: dens, outA: allowed, outS: stat }, { uCount: n, uStride: stride, uPos: pos }, n);
    for (const f of made) f.destroy();
    return { dens, allowed, stat };
}


// ------------------------------------------------------------------------------------------- the planner ---

/** plants.py _cell_m: a species' world cell, 4 x its mean spacing, at least 8 m. */
export function cellM(s) {
    const c = s.cluster;
    const spacing = 1.0 / Math.sqrt(Math.max(c.parents_per_ha * c.mu / 1.0e4, 1e-12));
    return Math.max(8.0, 4.0 * spacing);
}

// the Poisson tables of a species (its cells' centres, its centres' offspring) as one u32 list of (hi, lo) pairs
function poissonTables(gpu, s) {
    const c = cellM(s);
    const a = poissonThresholds(s.cluster.parents_per_ha * 1.0e-4 * c * c);
    const b = poissonThresholds(s.cluster.mu);
    const t = new Uint32Array(2 * (a.length + b.length) + 2);
    [...a, ...b].forEach((v, k) => {
        t[2 * k] = Math.floor(v / 4294967296);
        t[2 * k + 1] = v % 4294967296;
    });
    return { list: gpu.list(t.length, 'u32', t), par: [0, a.length], mu: [a.length, b.length] };
}

// plants.py _candidates: every candidate whose cluster centre lies in a world cell within `reach` of the focus
async function candidates(gpu, ground, s, chain, focus, reach) {
    const c = cellM(s);
    const b = ground.bounds;
    const fx = focus.list.map((p) => p[0]), fy = focus.list.map((p) => p[1]);
    const x0 = Math.max(Math.min(...fx) - reach, b[0] - c), y0 = Math.max(Math.min(...fy) - reach, b[1] - c);
    const x1 = Math.min(Math.max(...fx) + reach, b[2] + c), y1 = Math.min(Math.max(...fy) + reach, b[3] + c);
    if (x1 < x0 || y1 < y0) return null;
    const ix0 = Math.floor(x0 / c), iy0 = Math.floor(y0 / c);
    const nx = Math.floor(x1 / c) - ix0 + 1, ny = Math.floor(y1 / c) - iy0 + 1;
    const ncell = nx * ny;
    const tabs = poissonTables(gpu, s);
    const C = fixedBits(c, 32);
    const npar = gpu.list(ncell), hcs = gpu.list(2 * ncell);
    gpu.run('cells', { thr: tabs.list, foc: focus.field }, { outN: npar, outH: hcs },
        { uBox: [ix0, iy0, nx, ny], uC: C, uCm: f32(c), uNear: f32(reach + 0.7072 * c), uKey: u64Bits(chain), uTab: tabs.par,
            uCount: ncell, uFocusN: focus.list.length }, ncell);
    const ps = await gpu.scan(npar, ncell);
    let out = null;
    if (ps.total > 0) {
        const par = gpu.list(PAR * ps.total), noff = gpu.list(ps.total);
        gpu.run('parents', { npar, offs: ps.offs, hcs, thr: tabs.list }, { outP: par, outO: noff },
            { uBox: [ix0, iy0, nx, ny], uC: C, uCm: f32(c), uTab: tabs.mu, uCount: ncell }, ncell);
        const os = await gpu.scan(noff, ps.total);
        if (os.total > 0) {
            const a = s.age;
            const clip = BigInt(Math.round((1.0 - 1e-12) * 9007199254740992.0));
            const list = gpu.list(CAND * os.total);
            gpu.run('offspring', { par, offs: os.offs }, { outC: list },
                { uAge: [Number(a.shape), Number(a.scale), Number(a.stand ?? 0.5), f32(-Math.log1p(-(1.0 - 1e-12)))],
                    uClip: u64Bits(clip), uSize: [s.size_m[0], s.size_m[1], Number(s.cluster.sigma_m), 1.0 - Math.exp(-3.0)],
                    uCount: ps.total }, ps.total);
            out = { list, n: os.total };
        }
        for (const f of [par, noff, os.offs]) f.destroy();
    }
    for (const f of [npar, hcs, ps.offs, tabs.list]) f.destroy();
    return out;
}

// plants.py _shade_at: the shade at the candidates from the shade-casting plants placed so far
function shadeAt(gpu, cand, n, casters, radius, origin, stride = CAND, pos = 0) {
    const out = gpu.list(n, 'f32');
    if (!casters || !casters.n || !n) return out;
    const reach = radius * casters.rmax;
    if (!(reach > 0)) return out;
    const grid = gpu.grid(casters.list, casters.n, PLACED, 0, reach, origin);
    gpu.run('shade', { rec: cand, cb: casters.list, gstart: grid.starts, gcount: grid.counts, gidx: grid.index },
        { outS: out }, { ...grid.un, uRad: f32(radius), uReach: f32(reach), uStride: stride, uPos: pos, uCount: n }, n);
    grid.destroy();
    return out;
}

// plants.py _thin: the candidates of a species that survive everything short of the hard core among their own
// priority, with the stats it records
async function thin(gpu, ground, s, c, gi, focus, discs, feet, casters, st, origin) {
    const R = gpu.R;
    // on the terrain, within reach, off the excluded discs
    const flags0 = gpu.list(c.n);
    const [bxi, bxf] = splitCoord(ground.bounds[0]), [byi, byf] = splitCoord(ground.bounds[1]);
    const [Bxi, Bxf] = splitCoord(ground.bounds[2]), [Byi, Byf] = splitCoord(ground.bounds[3]);
    gpu.run('prefilter', { foc: focus.field, dsc: discs.field }, { cand: c.list, outF: flags0 },
        { uBI: [bxi, byi, Bxi, Byi], uBF: [bxf, byf, Bxf, Byf], uLim: [f32(gi.exact + gi.pad), Number(s.crown_m ?? s.core_m),
            Number(s.size_m[1]), 0], uDiscs: discs.n, uCount: c.n, uFocusN: focus.list.length }, c.n);
    let cc = await gpu.compact(flags0, c.n, c.list, CAND);
    flags0.destroy();
    c.list.destroy();
    if (!cc.n) return cc;
    let loc = ground.locate(cc.list, cc.n);
    if (s.max_cell_m !== null && s.max_cell_m !== undefined) {
        // on a level no coarser than the species' max_cell_m, the candidates located again
        const fine = gpu.list(cc.n);
        gpu.run('bit', { flags: loc.fine, lvt: ground.lvt() }, { outB: fine }, { uMask: 0, uNot: 0, uLo: 0, uHi: cc.n,
            uMaxCell: f32(Number(s.max_cell_m)), uCount: cc.n }, cc.n);
        loc.fine.destroy();
        loc.coarse.destroy();
        const c2 = await gpu.compact(fine, cc.n, cc.list, CAND);
        fine.destroy();
        cc.list.destroy();
        cc = c2;
        if (!cc.n) return cc;
        loc = ground.locate(cc.list, cc.n);
    }
    const shade = shadeAt(gpu, cc.list, cc.n, casters, Number(s.shade.radius), origin);
    const sk = await speciesKernel(gpu, ground, s, { steep: true });
    await ground.derive(new Set(sk.reads.map(([nm]) => nm)));
    const ev = await evaluateSpecies(gpu, ground, sk, cc.list, cc.n, loc, shade);
    const dmax = s.cluster.parents_per_ha * s.cluster.mu * 1.0e-4;
    const flags = gpu.list(cc.n);
    gpu.run('thin', { dens: ev.dens, allowed: ev.allowed, stat: ev.stat, shade, lvl: loc.fine, pw: gpu.dummyF },
        { cand: cc.list, outF: flags }, { uS: [f32(dmax), f32(s._radius), f32(1.0 - Number(s.shade.tolerance)),
            s._stature ? 1 : 0], uC: [Number(s.core_m), Number(s.size_m[1]), 0, 0], uCount: cc.n }, cc.n);
    const t = await gpu.tally(flags, cc.n, [1, 2, 4 | 2, 8 | 2, 16 | 1], ev.dens, 2);
    const [own, drawn, clipped, homeDrawn, afterDensity] = t.counts;
    st.candidates = own;
    if (drawn > 0) {
        st.density_max = t.max;
        st.clipped = clipped / drawn;
    }
    st.home_m2 = homeDrawn / dmax;
    st.after_density = afterDensity;
    for (const f of [ev.dens, ev.allowed, ev.stat, shade, loc.fine, loc.coarse]) f.destroy();
    // clear of the feet of the plants placed before
    if (feet && feet.n) {
        const rcmax = Number(s.core_m) * 1.0;     // r = core_m x size / size_m[1] <= core_m
        const reach = CORE_FACTOR * (feet.rmax + rcmax) + 1e-9;
        const grid = gpu.grid(feet.list, feet.n, PLACED, 0, reach, origin);
        gpu.run('feet', { cand: cc.list, pb: feet.list, gstart: grid.starts, gcount: grid.counts, gidx: grid.index },
            { flags }, { ...grid.un, uCF: CORE_FACTOR, uCount: cc.n }, cc.n);
        grid.destroy();
    }
    const keep = gpu.bit(flags, cc.n, 32);
    flags.destroy();
    const out = await gpu.compact(keep, cc.n, cc.list, CAND);
    keep.destroy();
    cc.list.destroy();
    return out;
}

// plants.py _hard_core over a priority group's thinned candidates (concatenated in species order): accepted and
// within the exact radius, per candidate; throws NeedMargin when a decision inside it is not certain
class NeedMargin extends Error {}

async function hardCore(gpu, list, n, gi, origin) {
    const R = gpu.R;
    const rmax = gi.rmax;
    const deg = gpu.list(n);
    let offs = null, adj = null, grid = null;
    if (rmax > 0) {
        grid = gpu.grid(list, n, CAND, 0, 2.0 * CORE_FACTOR * rmax, origin);
        gpu.run('edges', { cand: list, gstart: grid.starts, gcount: grid.counts, gidx: grid.index, offs: gpu.dummyU },
            { outD: deg, outA: gpu.dummyU }, { ...grid.un, uCF: CORE_FACTOR, uMode: 0, uCount: n }, n);
        const sc = await gpu.scan(deg, n);
        offs = sc.offs;
        adj = gpu.list(Math.max(sc.total, 1));
        gpu.run('edges', { cand: list, gstart: grid.starts, gcount: grid.counts, gidx: grid.index, offs },
            { outD: gpu.dummyU, outA: adj }, { ...grid.un, uCF: CORE_FACTOR, uMode: 1, uCount: n }, n);
        grid.destroy();
    } else {
        offs = gpu.list(n);
        adj = gpu.list(1);
    }
    const state = gpu.list(n), cert = gpu.list(n), newf = gpu.list(n), cnt = gpu.list(2);
    const taint = f32(gi.exact + gi.pad - gi.spill - 2.0 * CORE_FACTOR * gi.core);
    const run = (phase) => gpu.run('mis', { cand: list, offs, deg, adj }, { state, cert, newf, cnt },
        { uPhase: phase, uTaint: taint, uExact: f32(gi.exact), uCount: n }, n);
    run(3);
    let rounds = 0;
    for (;;) {
        for (let k = 0; k < MIS_CHECK; k++) {
            run(0);
            run(1);
            run(2);
        }
        rounds += MIS_CHECK;
        R.clear(cnt);
        run(4);
        const [u] = await R.readRange(cnt, 0, 1);
        if (u === 0) break;
        if (rounds > 100000) throw new Error('plants: the hard core did not settle');
    }
    R.clear(cnt);
    run(5);
    const [, uncertain] = await R.readRange(cnt, 0, 2);
    for (const f of [deg, offs, adj, state, cert, cnt]) f.destroy();
    if (uncertain > 0) {
        newf.destroy();
        throw new NeedMargin();
    }
    return { keep: newf, rounds };
}

// a list of the placed plants' positions and radii (feet: foot_m x scale; casters: crown_m x scale), all species
// placed so far
async function placedList(gpu, parts, factorOf) {
    const n = parts.reduce((a, p) => a + p.n, 0);
    if (!n) return null;
    const list = gpu.list(PLACED * n);
    let at = 0, rmax = 0;
    for (const p of parts) {
        if (!p.n) continue;
        const k = factorOf(p.s);
        gpu.run('placed_list', { pl: p.list }, { outL: list, outF: gpu.dummyU },
            { uS: [k, Number(p.s.size_m[1]), 0, 0], uFirst: at, uFlags: 0, uCount: p.n }, p.n);
        at += p.n;
        rmax = Math.max(rmax, k);                          // scale <= 1: the radius is at most the factor
    }
    return { list, n, rmax };
}

// plants.py _kept_profile from the bins' integer sums
function keptProfile(bins) {
    const tot = [], got = [];
    for (let b = 0; b < KEPT_BINS; b++) {
        tot.push(bins[4 * b] + bins[4 * b + 1] * 4294967296);
        got.push(bins[4 * b + 2] + bins[4 * b + 3] * 4294967296);
    }
    const ok = tot.map((v) => v > 0);
    if (!ok.some(Boolean)) return new Array(KEPT_BINS).fill(1.0);
    const xs = [], ys = [];
    for (let b = 0; b < KEPT_BINS; b++) if (ok[b]) { xs.push(b); ys.push(got[b] / tot[b]); }
    const out = [];
    for (let c = 0; c < KEPT_BINS; c++) {
        // np.interp(c, xs, ys): ends held
        let v;
        if (c <= xs[0]) v = ys[0];
        else if (c >= xs[xs.length - 1]) v = ys[ys.length - 1];
        else {
            let k = 0;
            while (xs[k + 1] < c) k++;
            v = xs[k + 1] === c ? ys[k + 1] : ys[k] + (ys[k + 1] - ys[k]) * ((c - xs[k]) / (xs[k + 1] - xs[k]));
        }
        out.push(pyRoundN(v, 4));
    }
    return out;
}

// plants.py _view: a species' records for the plan's focus (the placed plants within its radius, tall enough for
// their distance, thinned over the fade band, capped at max_count), heights and normals from the terrain
async function view(gpu, ground, s, p, st) {
    const R = gpu.R, P_ = gpu.P;
    if (!p.n) return new Float32Array(0);
    const Rr = s._radius;
    const [f0, f1] = s.fade;
    const flags = gpu.list(p.n), keys = gpu.list(p.n, 'f32');
    gpu.run('view', { cand: p.list }, { outF: flags, outK: keys },
        { uV: [f32(Rr), Number(s.lod_m_per_m), f32(f0 * Rr), f32(f1 * Rr)], uFade: f1 > f0 ? 1 : 0, uCount: p.n }, p.n);
    let { index, n } = await P_.nonzero(flags, { count: p.n });
    const cap = s.max_count;
    if (cap !== null && cap !== undefined && n > Math.trunc(cap)) {
        // the smallest for their distance go first: np.argsort(-(size / max(d, 1)), kind='stable')[:cap], sorted
        const kk = P_.gather(keys, index, { count: n });
        const order = P_.argsort(kk, { descending: true, count: n });
        const pick = P_.gather(index, order, { count: Math.trunc(cap) });
        const { keys: sorted, vals } = P_.sortPairs(pick, null, { count: Math.trunc(cap) });
        vals.destroy();
        for (const f of [kk, order, pick, index]) f.destroy();
        index = sorted;
        n = Math.trunc(cap);
        ground.notes.push(`${s.name}: capped at max_count ${Math.trunc(cap).toLocaleString('en-US')} (the smallest and ` +
            'farthest dropped); a capped plan does not keep its spots when the radius grows');
    }
    // the kept share of the crown area per distance band
    const kept = gpu.list(p.n);
    gpu.run('mark', { index }, { outM: kept }, { uCount: n }, n);
    const bins = gpu.list(4 * KEPT_BINS);
    gpu.run('kept_bins', { cand: p.list, keep: kept }, { outB: bins }, { uR: f32(Rr), uCount: p.n }, p.n);
    const b = await R.readRange(bins, 0, 4 * KEPT_BINS);
    if (st) {
        st.kept_area = keptProfile(b);
        st.kept_band_m = pyRoundN(Rr / KEPT_BINS, 4);
    }
    for (const f of [flags, keys, kept, bins]) f.destroy();
    if (!n) {
        index.destroy();
        return new Float32Array(0);
    }
    const kp = gpu.list(CAND * n);
    gpu.run('gather_rec', { src: p.list, index }, { outR: kp }, { uStride: CAND, uCount: n, uFirst: 0 }, n);
    index.destroy();
    const pts = gpu.list(2 * n, 'f32');
    gpu.run('spot_xy', { kp }, { outP: pts }, { uCount: n }, n);
    const rm = ground.terrain.ring;
    const zs = rm.heightField(R, pts, n);
    const nrm = gpu.list(3 * n, 'f32');
    const tg = rm._gpu;
    gpu.run('ground_normal', { pts, zs: tg.zs, lines: tg.lines, ring: tg.ring }, { outN: nrm },
        { uCount: n, uRings: rm.rings.length }, n);
    const rec = gpu.list(FIELDS.length * n, 'f32');
    gpu.run('records', { kp, zs, nrm }, { outR: rec }, { uR: [Number(s.size_m[1]), Math.max(s.source[3].length, 1), 0, 0], uCount: n }, n);
    const out = await R.readRange(rec, 0, FIELDS.length * n);
    for (const f of [kp, pts, zs, nrm, rec]) f.destroy();
    return out;
}

// plants.py _plan: every species' accepted plants within its exact radius of the focus, and the stats
async function planGroups(gpu, ground, species, focus, tseed, seed, discs, scale, origin, log) {
    const groups = [];
    for (const s of species) {
        if (!groups.length || groups[groups.length - 1][0].priority !== s.priority) groups.push([]);
        groups[groups.length - 1].push(s);
    }
    const info = groups.map((g) => {
        const core = Math.max(...g.map((s) => Number(s.core_m)));
        const spill = Math.max(...g.map((s) => 3.0 * Number(s.cluster.sigma_m)));
        const pad = scale * (PAD_CORES * 2.0 * CORE_FACTOR * core + 4.0) + spill;
        return { core, spill, pad, R: Math.max(...g.map((s) => s._radius)), exact: 0.0, rmax: core };
    });
    for (let k = groups.length - 1; k >= 0; k--) {
        let need = info[k].R;
        for (let j = k + 1; j < groups.length; j++) {
            const feet = Math.max(...groups[k].map((s) => Number(s.foot_m)));
            const crown = Math.max(...groups[k].map((s) => Number(s.crown_m)));
            let reach = CORE_FACTOR * (feet + info[j].core);
            reach = Math.max(reach, Math.max(...groups[j].map((s) => Number(s.shade.radius))) * crown);
            const ar = groups[j].filter((s) => s.around).map((s) => Number(s.around.radius ?? 1.5) * crown);
            reach = Math.max(reach, ar.length ? Math.max(...ar) : 0.0);
            need = Math.max(need, info[j].exact + info[j].pad + reach + 1.0);
        }
        info[k].exact = need;
    }
    const placed = new Map(), stats = {};
    const placedParts = [], casterParts = [];
    let feet = null, casters = null;
    for (let gk = 0; gk < groups.length; gk++) {
        const g = groups[gk], gi = info[gk];
        const cands = [];
        for (const s of g) {
            if (s.around) {
                throw new Error(`plants: species ${pyReprValue(s.name)} grows around another (around), which no ecotope ` +
                    'of f9fba8c does and this port does not take yet');
            }
            const chain = hashChain(Number(tseed), Number(seed), nameKey(s.name));
            const c = await candidates(gpu, ground, s, chain, focus, gi.exact + gi.pad);
            const st = stats[s.name] = { candidates: 0, after_density: 0, kept: 0, clipped: 0.0, density_max: 0.0, home_m2: 0.0,
                home_count: 0, per_ha_home: null };
            st.yield = 1.0;
            placed.set(s.name, { s, list: gpu.list(CAND), n: 0 });
            if (!c || !c.n) continue;
            cands.push([s, await thin(gpu, ground, s, c, gi, focus, discs, feet, casters, st, origin)]);
        }
        if (!cands.length) continue;
        const total = cands.reduce((a, [, t]) => a + t.n, 0);
        const list = gpu.list(CAND * Math.max(total, 1));
        let at = 0;
        const ranges = [];
        for (const [s, t] of cands) {
            gpu.run('copy_rec', { src: t.list }, { outR: list }, { uStride: CAND, uCount: t.n, uFirst: at }, t.n);
            ranges.push([s, at, t.n]);
            at += t.n;
            t.list.destroy();
        }
        const rmax = Math.max(...cands.map(([s]) => Number(s.core_m)));    // r = core_m x size / size_m[1] <= core_m
        const hc = total ? await hardCore(gpu, list, total, { ...gi, rmax }, origin) : { keep: gpu.list(1) };
        for (const [s, a, n] of ranges) {
            // this species' part of the group: its range of the keep flags
            let part = { list: gpu.list(CAND), n: 0 };
            if (n) {
                const sub = gpu.bit(hc.keep, total, 1, 0, a, a + n);
                part.list.destroy();
                part = await gpu.compact(sub, total, list, CAND);
                sub.destroy();
            }
            const st = stats[s.name];
            placed.get(s.name).list.destroy();
            placed.set(s.name, { s, list: part.list, n: part.n });
            if (part.n) {
                const pf = gpu.list(part.n);
                gpu.run('placed_list', { pl: part.list }, { outL: gpu.dummyU, outF: pf },
                    { uS: [0, Number(s.size_m[1]), f32(s._radius), 0], uFirst: 0, uFlags: 1, uCount: part.n }, part.n);
                const tt = await gpu.tally(pf, part.n, [1, 8 | 1]);
                pf.destroy();
                st.kept = tt.counts[0];
                st.home_count = tt.counts[1];
                if (st.home_m2 > 0.0) st.per_ha_home = pyRoundN(1.0e4 * st.home_count / st.home_m2, 2);
                st.yield = pyRoundN(tt.counts[0] / Math.max(st.after_density, 1), 4);
            } else {
                if (st.home_m2 > 0.0) st.per_ha_home = pyRoundN(0.0, 2);
                st.yield = pyRoundN(0.0 / Math.max(st.after_density, 1), 4);
            }
        }
        hc.keep.destroy();
        list.destroy();
        for (const s of g) {
            const p = placed.get(s.name);
            placedParts.push({ s, list: p.list, n: p.n });
            if (s.casts_shade) casterParts.push({ s, list: p.list, n: p.n });
        }
        if (feet) feet.list.destroy();
        if (casters) casters.list.destroy();
        feet = await placedList(gpu, placedParts, (s) => Number(s.foot_m));
        casters = await placedList(gpu, casterParts, (s) => Number(s.crown_m));
        void log;
    }
    if (feet) feet.list.destroy();
    if (casters) casters.list.destroy();
    return { placed, stats };
}

// the focus' points as the kernels' list (4 numbers a point)
function focusList(gpu, f) {
    const a = new Float32Array(4 * f.length);
    f.forEach((p, k) => a.set([...splitCoord(p[0]), ...splitCoord(p[1])], 4 * k));
    return { list: f, field: gpu.list(a.length, 'f32', a) };
}

// exclusion discs (Blender (x, y, r[, 'crown'])) as the kernels' list (6 numbers a disc)
function discList(gpu, discs) {
    const a = new Float32Array(6 * Math.max(discs.length, 1));
    discs.forEach((d, k) => a.set([...splitCoord(Number(d[0])), ...splitCoord(Number(d[1])), Number(d[2]),
        d.length > 3 && d[3] === 'crown' ? 1 : 0], 6 * k));
    return { n: discs.length, field: gpu.list(a.length, 'f32', a) };
}

// exclude discs as plan_plants takes them: { blender: [[x, y, r, 'crown'?], ...] } as it is; else three.js discs
// [x, z, r, 'crown'?] (the scene's frame)
function blenderDiscs(exclude) {
    if (!exclude) return [];
    if (isObj(exclude) && Array.isArray(exclude.blender)) return exclude.blender.map((d) => [...d]);
    return exclude.map((d) => [Number(d[0]), -Number(d[1]), ...d.slice(2)]);
}

const PLAN_OPTS = ['ecotope', 'focus', 'radiusM', 'radius_m', 'seed', 'data', 'exclude', 'log', 'R'];

/** The spots of an ecotope on a terrain (plants.py plan_plants; the module doc says how each is placed).
 *
 *     terrain    a Terrain (makeTerrain's, Terrain.load's): its levels, masks, fields, ring mesh and info are read
 *     ecotope    'auto' (the terrain's place's, recipe's or palette's: ecotopes.get), an ecotope name or object
 *     focus      [x, z] (three.js ground), [x, y, z], an Object3D, a list of them (a path), or { blender: [[x, y],
 *                ...] }: where the plants are wanted; default the terrain's own focus, else the main level's centre
 *     radiusM    a cap on every species' max_radius_m (null: each species' own)
 *     seed       the plan's seed (the terrain's own seed is hashed in too)
 *     data       the terrain's SurfaceData (surface/index.js bakeSurface), when there is one: every level's maps are
 *                read from it; without one, the masks alone (a bake map an expression names then reads 0)
 *     exclude    discs kept clear: three.js [x, z, r] or [x, z, r, 'crown'] (no crown over the disc either: a spot a
 *                person stands on, a camera at eye height), or { blender: [...] }; default the terrain's flatten areas
 * Returns a PlantSpots. */
export async function planPlants(terrain, opts = {}) {
    const bad = Object.keys(opts).find((k) => !PLAN_OPTS.includes(k));
    if (bad) throw new TypeError(`planPlants() got an unexpected option ${pyReprValue(bad)}; the options are ${PLAN_OPTS.join(', ')}`);
    const t0 = performance.now();
    const ecotope = opts.ecotope ?? 'auto';
    const radiusM = opts.radiusM ?? opts.radius_m ?? null;
    const seed = Math.trunc(Number(opts.seed ?? 0));
    const data = opts.data ?? null;
    const log = opts.log === undefined ? console.log : opts.log;
    const info = terrain.info ?? {};
    const eco = resolveEcotope(terrain, ecotope);
    const consts = await planConstants(terrain, eco);
    const R = opts.R ?? (terrain._runner ? await terrain._runner() : await G.init());
    const gpu = new Gpu(R);
    const ground = new Ground(gpu, terrain, data, consts);
    let f = focusPoints(opts.focus);
    if (!f && Array.isArray(info.focus) && info.focus.length) f = info.focus.map((p) => [Number(p[0]), Number(p[1])]);
    if (!f) {
        const main = ground.levels.find((lv) => lv.role === 'main') ?? ground.levels[ground.levels.length - 1];
        f = [[main.x0 + 0.5 * main.side, main.y0 + 0.5 * main.side]];
    }
    let discs = blenderDiscs(opts.exclude);
    if (opts.exclude === null || opts.exclude === undefined) {
        discs = (info.flats ?? []).filter((fl) => fl.radius).map((fl) => [Number(fl.at[0]), Number(fl.at[1]), Number(fl.radius)]);
    }
    const tseed = Math.trunc(Number(info.seed || 0));
    const order = eco.species.map((s, i) => i).sort((a, b) => eco.species[a].priority - eco.species[b].priority || a - b);
    const species = order.map((i) => {
        const s = { ...eco.species[i] };
        s._radius = radiusM !== null ? Math.min(Number(s.max_radius_m), Number(radiusM)) : Number(s.max_radius_m);
        s._density = P.parse(s.density);
        s._stature = s.stature !== null && s.stature !== undefined ? P.parse(s.stature) : null;
        return s;
    });
    const focus = focusList(gpu, f);
    const dl = discList(gpu, discs);
    const origin = [...splitCoord(f[0][0]), ...splitCoord(f[0][1])];
    let scale = 1.0, res = null;
    try {
        for (let attempt = 0; attempt < 5; attempt++) {
            try {
                res = await planGroups(gpu, ground, species, focus, tseed, seed, dl, scale, origin, log);
                break;
            } catch (e) {
                if (!(e instanceof NeedMargin)) throw e;
                scale *= 2.0;
            }
        }
        if (!res) throw new Error('plan_plants: the hard-core margin did not settle after five widenings');
        const outSpecies = [], arrays = new Map();
        for (const s of species) {
            const st = res.stats[s.name];
            const rec = await view(gpu, ground, s, res.placed.get(s.name), st);
            arrays.set(s.name, rec);
            st.count = rec.length / FIELDS.length;
            outSpecies.push(speciesRecord(s, st.count, st));
        }
        for (const p of res.placed.values()) p.list.destroy();
        const meta = {
            format: FORMAT, frame: { ...FRAME },
            terrain: { cache_key: info.cache_key ?? null, recipe: E.recipeName(terrain.recipe) ?? info.recipe_name ?? null, seed: tseed,
                levels: ground.levels.map((lv) => [lv.x0, lv.y0, lv.side, lv.cell, lv.n]), roles: ground.levels.map((lv) => lv.role) },
            focus: f.map(([a, b]) => [a, b]), seed, radius_m: radiusM === null ? null : Number(radiusM),
            ecotope: `${eco.name}#${E.ecotopeHash(eco)}`, fields: [...FIELDS],
            constants: Object.fromEntries(Object.entries(consts).filter(([, v]) => typeof v === 'number')),
        };
        const spots = new PlantSpots(meta, outSpecies, arrays, { ground, ecotope: eco });
        spots.seconds = pyRoundN((performance.now() - t0) / 1000, 2);
        spots.notes = [...ground.notes];
        if (log) {
            const parts = outSpecies.map((s) => `${s.name} ${s.count.toLocaleString('en-US')}`).join(', ') || 'no species';
            log(`[plants] ${eco.name}: ${parts} around (${f[0][0].toFixed(0)}, ${f[0][1].toFixed(0)})` +
                (f.length > 1 ? ` .. (${f[f.length - 1][0].toFixed(0)}, ${f[f.length - 1][1].toFixed(0)})` : '') + ` in ${spots.seconds} s`);
            for (const s of species) {
                const st = res.stats[s.name];
                if (st.clipped > 0.02) {
                    const c = s.cluster;
                    log(`[plants] ${s.name}: its density asks for more than parents_per_ha x mu = ${c.parents_per_ha * c.mu} ` +
                        `per ha at ${(100 * st.clipped).toFixed(0)} % of its candidates (up to ${(st.density_max * 1e4).toFixed(0)} ` +
                        'per ha): raise parents_per_ha or mu');
                }
            }
            for (const n of ground.notes) log('[plants] ' + n);
        }
        return spots;
    } finally {
        focus.field.destroy();
        dl.field.destroy();
    }
}

// plants.py _species_record
function speciesRecord(s, count, st) {
    const rule = {};
    for (const [k, v] of Object.entries(s)) if (!k.startsWith('_') && k !== 'source') rule[k] = v;
    return { name: s.name, kind: s.kind, source: E.sourceDict(s.source), honoured: [...HONOURED[s.source[0]]],
        size_m: [Number(s.size_m[0]), Number(s.size_m[1])], core_m: Number(s.core_m), crown_m: Number(s.crown_m),
        foot_m: Number(s.foot_m), cluster: JSON.parse(JSON.stringify(s.cluster)), sink: Number(s.sink), align: Number(s.align),
        lod: { ...s.lod }, ground: s.ground, count: Math.trunc(count), fields: [...FIELDS], rule: JSON.parse(JSON.stringify(rule)),
        stats: { ...st } };
}


// ---------------------------------------------------------------------------------------------- the spots ---

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

/** The spots of a plan (plants.py PlantSpots): per species a Float32Array of count x 12 records (FIELDS per spot,
 * Blender frame), with what an instancer needs to know of each species (.species: name, kind, source, size_m, core_m,
 * lod, count ...) and the plan's description (.meta). save / load round-trip the saved format (both editions');
 * cover(level) gives the cover rasters the material reads. */
export class PlantSpots {
    constructor(meta, species, arrays, opts = {}) {
        this.meta = meta;
        this.species = species;
        this._arrays = arrays instanceof Map ? arrays : new Map(Object.entries(arrays));
        this._ground = opts.ground ?? null;
        this._ecotope = opts.ecotope ?? null;
        this.stats = Object.fromEntries(species.map((s) => [s.name, s.stats ?? {}]));
        this.notes = [];
        this.seconds = null;
    }

    /** These spots from another PlantSpots holding the same files (api.js's, which Terrain.load fills). */
    static from(other) {
        if (other instanceof PlantSpots) return other;
        return new PlantSpots(other.meta, other.species, other._arrays);
    }

    names() { return this.species.map((s) => s.name); }
    has(name) { return this._arrays.has(name); }
    get length() { let n = 0; for (const a of this._arrays.values()) n += a.length / FIELDS.length; return n; }

    toString() {
        return `PlantSpots(${this.meta.ecotope}: ` + this.species.map((s) => `${s.name} ${this.count(s.name).toLocaleString('en-US')}`).join(', ') + ')';
    }

    entry(name) {
        const s = this.species.find((e) => e.name === name);
        if (!s) throw new KeyError(`no species ${pyReprValue(name)}; the plan has ${this.names().join(', ')}`);
        return s;
    }

    /** The records of a species: a Float32Array, FIELDS per spot. */
    array(name) {
        this.entry(name);
        return this._arrays.get(name);
    }

    /** One field of a species' spots (a copy: a column of the records; test and per-query use). */
    field(name, field) {
        const k = FIELDS.indexOf(field);
        if (k < 0) throw new KeyError(`no field ${pyReprValue(field)}; the fields are ${FIELDS.join(', ')}`);
        const a = this.array(name), n = a.length / FIELDS.length, out = new Float32Array(n);
        for (let i = 0; i < n; i++) out[i] = a[i * FIELDS.length + k];
        return out;
    }

    count(name) { return this.array(name).length / FIELDS.length; }

    /** Write <base>.plants.json and one <base>.plants.<species>.f32 per species (headerless little-endian float32,
     * FIELDS per spot). Returns the paths written, the JSON first. */
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
            entries.push({ ...s, count: a.length / FIELDS.length, file: fn });
        }
        const jpath = `${base}.plants.json`;
        await Deno.writeTextFile(jpath + '.tmp', JSON.stringify({ ...this.meta, species: entries }, null, 1));
        await Deno.rename(jpath + '.tmp', jpath);
        return [jpath, ...out];
    }

    /** The spots save() wrote (this edition's or Blender's). With the terrain they were planned on (opts.terrain,
     * opts.data), cover() works too. */
    static async load(base, opts = {}) {
        base = stripExt(base);
        const meta = JSON.parse(await Deno.readTextFile(`${base}.plants.json`));
        if (meta.format !== FORMAT) {
            throw new ValueError(`${base}.plants.json: format ${pyReprValue(meta.format ?? null)}, this reads ${pyReprValue(FORMAT)}`);
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
            arrays.set(s.name, new Float32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)));
        }
        const spots = new PlantSpots(meta, species, arrays);
        if (opts.terrain) await spots.attach(opts.terrain, opts.data ?? null, opts.R ?? null);
        return spots;
    }

    /** Give loaded spots the terrain they were planned on, for cover(): read with the constants the plan read (saved
     * in its description), else the terrain's. */
    async attach(terrain, data = null, R = null) {
        const consts = await planConstants(terrain);
        Object.assign(consts, this.meta.constants ?? {});
        const runner = R ?? (terrain._runner ? await terrain._runner() : await G.init());
        this._ground = new Ground(new Gpu(runner), terrain, data, consts);
        return this;
    }

    levelIndex(level) {
        const roles = this.meta.terrain.roles ?? this.meta.terrain.levels.map(() => 'main');
        const n = roles.length;
        if (typeof level === 'number') return ((Math.trunc(level) % n) + n) % n;
        if (level === 'first') return 0;
        if (level === 'last') return n - 1;
        const hit = roles.map((r, i) => [r, i]).filter(([r]) => r === level).map(([, i]) => i);
        if (!hit.length) throw new KeyError(`level ${pyReprValue(level)}: an index, 'main', 'context', 'hero', 'first' or 'last' (${roles.join(', ')})`);
        return level === 'context' ? hit[0] : hit[hit.length - 1];
    }

    // plants.py PlantSpots._kept_at: the share of a species' crown area its instances carry at a distance, as the
    // profile plants/cover_acc reads: { prof: Float32Array(48), band, placed }
    keptOf(entry) {
        const st = entry.stats ?? {};
        if (st.kept_area && st.kept_area.length) {
            return { prof: Float32Array.from(st.kept_area), band: Number(st.kept_band_m), placed: true };
        }
        if (!entry.count) return { prof: new Float32Array(KEPT_BINS), band: 1.0, placed: false };
        // spots saved without a profile: its fade band, as 48 bands of R / 48
        const rule = entry.rule;
        const cap = this.meta.radius_m;
        const Rr = cap === null || cap === undefined ? Number(rule.max_radius_m) : Math.min(Number(rule.max_radius_m), Number(cap));
        const [f0, f1] = rule.fade.map(Number);
        const band = Rr / KEPT_BINS;
        const prof = new Float32Array(KEPT_BINS);
        for (let k = 0; k < KEPT_BINS; k++) {
            const d = (k + 0.5) * band;
            prof[k] = f1 > f0 ? 1.0 - smooth(f0 * Rr, f1 * Rr, d) : (d > Rr ? 0.0 : 1.0);
        }
        return { prof, band, placed: true };
    }

    /** The cover rasters of one level (an index or role), row 0 south, at the level's cell (at most maxN across: a
     * finer level is read every other cell): canopy (the placed tree crowns as discs), canopy_expected (the trees'
     * densities' cover, everywhere), canopy_far (the part the instances leave to the material), shrubs, shrubs_far,
     * grass, grass_far (plants.py PlantSpots.cover). { name: Float32Array } of n x n; .n the raster's side. */
    async cover(level = 'main', maxN = 1024, densityN = 512) {
        if (!this._ground) throw new Error('cover() reads the terrain: PlantSpots.load(base, { terrain }), or spots.attach(t)');
        const g = this._ground;
        const i = this.levelIndex(level);
        const entries = Object.fromEntries(this.species.map((s) => [s.name, s]));
        const rules = this.species.map((s) => ({ ...s.rule, name: s.name, kind: s.kind }));
        const focus = this.meta.focus.map((p) => [Number(p[0]), Number(p[1])]);
        const lc = await levelCover(g, rules, i, maxN, densityN, (name) => this.keptOf(entries[name]), focus);
        const lv = g.levels[i];
        const cell = lv.cell * lc.step;
        const canopy = await discs(g, this.species.filter((s) => s.kind === 'tree').map((s) => [s, this._arrays.get(s.name)]), lv, cell, lc.m);
        const out = { canopy, ...lc.rasters };
        out.n = lc.m;
        return out;
    }

    /** The cover rasters of every level in the form the surface bake takes (SurfaceData.addMaps): { canopy: [array per
     * level], canopy_expected: [...], ... }, the rasters its map registry (surface/maps.js MAPS) knows. */
    async coverExtra(maxN = 1024, densityN = 512) {
        const { MAPS: known } = await import('../surface/maps.js');
        const names = COVER_MAPS.filter((k) => k in known);
        const out = Object.fromEntries(names.map((k) => [k, []]));
        for (let i = 0; i < this.meta.terrain.levels.length; i++) {
            const c = await this.cover(i, maxN, densityN);
            for (const k of names) out[k].push(c[k]);
        }
        return out;
    }
}

// plants.py _crown_and_scale: the mean crown area and the mean scale of a species' plants over its age distribution
// (24 x 24 quantiles of the stand's draw and the plant's own): a per-species constant (576 numbers), in doubles
export function crownAndScale(rule) {
    const a = rule.age;
    const k = Number(a.stand ?? 0.5);
    const w = (u) => Number(a.scale) * (-Math.log1p(-Math.min(u, 1.0 - 1e-12))) ** (1.0 / Number(a.shape));
    const [lo, hi] = rule.size_m.map(Number);
    const crown = Number(rule.crown_m ?? rule.core_m);
    let area = 0.0, sc = 0.0;
    for (let r = 0; r < 24; r++) {
        for (let c = 0; c < 24; c++) {
            const us = (c + 0.5) / 24.0, uo = (r + 0.5) / 24.0;
            const age = Math.min(Math.max(k * w(us) + (1.0 - k) * w(uo), 0.02), 1.0);
            const grow = (1.0 - Math.exp(-3.0 * age)) / (1.0 - Math.exp(-3.0));
            const s = (lo + (hi - lo) * grow) / hi;
            area += Math.PI * (crown * s) ** 2;
            sc += s;
        }
    }
    return [area / 576, sc / 576];
}

// plants.py _kept_by_core's constant: a = dens x g(0) pi d^2 (0: no hard core)
function coreCoef(rule, meanScale) {
    const core = Number(rule.core_m);
    if (core <= 0.0) return 0.0;
    const cl = rule.cluster;
    const kappa = Math.max(Number(cl.parents_per_ha) * 1.0e-4, 1e-12);
    const sig = Math.max(Number(cl.sigma_m), 0.1);
    const g0 = 1.0 + 1.0 / (4.0 * Math.PI * sig * sig * kappa);
    const d = 2.0 * CORE_FACTOR * core * meanScale;
    return g0 * Math.PI * d * d;
}

// plants.py _level_cover: the expected cover of trees, of shrubs and of grasses on level i from the rules' densities
// alone, with kept (the instances' share by distance) also what the instances leave to the material
async function levelCover(ground, rules, i, maxN = 1024, densityN = 512, kept = null, focus = null) {
    const gpu = ground.g, R = gpu.R;
    const lv = ground.levels[i];
    let step = 1;
    while (Math.trunc(lv.n / step) > maxN) step *= 2;
    const m = Math.trunc(lv.n / step);
    const k = Math.trunc(m / Math.ceil(m / Math.max(Math.trunc(densityN), 1)));
    const n = k * k;
    const pts = ground.gridPoints(i, k);
    const loc = ground.locate(pts, n, 4, 0);
    // a grid point's level for the fine reads is level i itself (plants.py _GridPoints), its coarse level the located one
    loc.fine.destroy();
    loc.fine = gpu.fillU32(n, i);
    let dist = null;
    if (kept && focus) {
        const fl = focusList(gpu, focus);
        dist = gpu.list(n, 'f32');
        gpu.run('path_dist', { foc: fl.field, rec: pts }, { outD: dist }, { uStride: 4, uCount: n, uFocusN: focus.length }, n);
        fl.field.destroy();
    }
    const exp = {}, far = {};
    for (const kind of ['tree', 'shrub', 'grass']) {
        exp[kind] = R.field(k, k, 1);
        far[kind] = R.field(k, k, 1);
    }
    let tshade = null;
    for (const kind of ['tree', 'shrub', 'grass']) {
        if (kind === 'shrub') {
            // the undergrowth's shade: 1 - exp(-the trees' exponent)
            tshade = gpu.list(n, 'f32');
            gpu.run('one_minus_exp', { v: exp.tree }, { outV: tshade }, { uFill: 0, uValue: 0, uCount: n }, n);
        }
        for (const rule of rules) {
            if (COVER_KIND[rule.kind] !== kind) continue;
            const s = { ...rule, _density: P.parse(rule.density), _stature: null };
            const sk = await speciesKernel(gpu, ground, s, { steep: false });
            const shade = sk.shade ? (kind === 'tree' ? gpu.list(n, 'f32') : tshade) : null;
            await ground.derive(new Set(sk.reads.map(([nm]) => nm)));
            const ev = await evaluateSpecies(gpu, ground, sk, pts, n, loc, shade, 4, 0);
            const [crown, meanScale] = crownAndScale(rule);
            const coef = coreCoef(rule, meanScale);
            const dmax = rule.cluster.parents_per_ha * rule.cluster.mu * 1.0e-4;
            const kp = kept ? kept(rule.name) : null;
            const prof = gpu.list(KEPT_BINS, 'f32', kp ? kp.prof : new Float32Array(KEPT_BINS));
            R.run(gpu.k('cover_acc'), { dens: ev.dens, allowed: ev.allowed, tshade: tshade ?? gpu.dummyF, dist: dist ?? gpu.dummyF, prof },
                { outE: exp[kind], outF: far[kind] }, { uS: [f32(dmax), f32(1.0 - Number(rule.shade.tolerance)), f32(crown), kind !== 'tree' ? 1 : 0],
                    uC: [f32(coef), coef > 0 ? 1 : 0, 0, 0], uK: [kp ? 1 : 0, kp ? f32(kp.band) : 1, kp ? (kp.placed ? 1 : 0) : 1, 0], uCount: n },
                [Math.ceil(k / 16), Math.ceil(k / 16), 1]);
            for (const f of [ev.dens, ev.allowed, ev.stat, prof]) f.destroy();
            if (shade && kind === 'tree') shade.destroy();
        }
    }
    const rasters = {};
    const names = { tree: ['canopy_expected', 'canopy_far'], shrub: ['shrubs', 'shrubs_far'], grass: ['grass', 'grass_far'] };
    for (const kind of ['tree', 'shrub', 'grass']) {
        for (const [which, src] of [[names[kind][0], exp[kind]], [names[kind][1], far[kind]]]) {
            const o = R.field(m, m, 1);
            R.run(gpu.k('cover_raster'), { v: src }, { outC: o }, { uK: k }, [Math.ceil(m / 16), Math.ceil(m / 16), 1]);
            rasters[which] = await R.read(o);
            o.destroy();
        }
        exp[kind].destroy();
        far[kind].destroy();
    }
    for (const f of [pts, loc.fine, loc.coarse, tshade, dist]) if (f) f.destroy();
    return { m, step, k, rasters };
}

// plants.py _discs: the placed tree crowns as discs on a level's m x m raster of `cell` metres
async function discs(ground, trees, lv, cell, m) {
    const gpu = ground.g, R = gpu.R;
    const area = gpu.list(m * m), stamp = gpu.list(m * m), out = gpu.list(m * m, 'f32');
    for (const [s, a] of trees) {
        if (!a || !a.length) continue;
        const nrec = a.length / FIELDS.length;
        const recs = gpu.list(a.length, 'f32', a);
        const cr = gpu.list(4 * nrec, 'f32');
        gpu.run('crowns', { rec: recs }, { outC: cr }, { uO: [f32(lv.x0), f32(lv.y0), f32(cell), Number(s.crown_m ?? s.core_m)], uCount: nrec }, nrec);
        gpu.run('discs', { crowns: cr }, { area, stamp, outC: out }, { uMode: 0, uCount: nrec, uNx: m, uNy: m }, nrec);
        recs.destroy();
        cr.destroy();
    }
    R.run(gpu.k('discs'), { crowns: gpu.dummyF }, { area, stamp, outC: out }, { uMode: 1, uCount: 0, uNx: m, uNy: m },
        [Math.ceil(m / 16), Math.ceil(m / 16), 1]);
    const v = await R.readRange(out, 0, m * m);
    for (const f of [area, stamp, out]) f.destroy();
    return v;
}

/** The ecotope's cover rasters with no plan (plants.py expected_cover, SURFACING_DESIGN.md 4.7): per level, from its
 * tree, shrub and grass densities alone, in the form SurfaceData.addMaps takes ({ canopy_expected: [array per level],
 * canopy_far, shrubs, shrubs_far, ... }, the names the surface data's registry knows), the far ones equal to the
 * expected ones (nothing is instanced). opts: ecotope, data, maxN, densityN, R. */
export async function expectedCover(terrain, opts = {}) {
    const { MAPS: known } = await import('../surface/maps.js');
    const eco = resolveEcotope(terrain, opts.ecotope ?? 'auto');
    const consts = await planConstants(terrain, eco);
    const R = opts.R ?? (terrain._runner ? await terrain._runner() : await G.init());
    const gpu = new Gpu(R);
    const ground = new Ground(gpu, terrain, opts.data ?? null, consts);
    const out = { canopy_expected: [], canopy_far: [], shrubs: [], shrubs_far: [], grass: [], grass_far: [] };
    try {
        for (let i = 0; i < ground.levels.length; i++) {
            const lc = await levelCover(ground, eco.species, i, opts.maxN ?? 1024, opts.densityN ?? 512);
            for (const [kind, name] of [['tree', 'canopy_expected'], ['shrub', 'shrubs'], ['grass', 'grass']]) {
                void kind;
                out[name].push(lc.rasters[name]);
                out[name === 'canopy_expected' ? 'canopy_far' : name + '_far'].push(lc.rasters[name].slice());
            }
        }
    } finally {
        gpu.destroy();
    }
    return Object.fromEntries(Object.entries(out).filter(([k]) => k in known));
}

/** Where a plan of this terrain is kept in the terrain cache (plants.py cache_base): <terrain cache entry>/plants_<key>,
 * the key a hash of the ecotope, the seed, the focus, the radius, the surface bake it read (data, its key), the discs
 * it keeps clear when given and this edition's plant code (build/plants.js, ecotopes.js and palettes.js). null for a
 * terrain without a cache entry. opts as planPlants takes them. */
export async function cacheBase(terrain, opts = {}) {
    const info = terrain.info ?? {};
    if (!info.cache_key) return null;
    const Ch = await import('../core/cache.js');
    const eco = resolveEcotope(terrain, opts.ecotope ?? 'auto');
    let f = focusPoints(opts.focus);
    if (!f && Array.isArray(info.focus) && info.focus.length) f = info.focus.map((p) => [Number(p[0]), Number(p[1])]);
    const h = createHash('sha1');
    for (const fn of ['plants.js', 'ecotopes.js', 'palettes.js']) h.update(Deno.readFileSync(new URL(fn, import.meta.url)));
    const r3 = (v) => pyRoundN(v, 3);
    const key = [E.ecotopeHash(eco), Math.trunc(Number(opts.seed ?? 0)), f === null ? null : f.map((p) => p.map(r3)),
        (opts.radiusM ?? opts.radius_m ?? null) === null ? null : Number(opts.radiusM ?? opts.radius_m),
        opts.data ? String(opts.data.key ?? '') : null];
    if (opts.exclude !== null && opts.exclude !== undefined) {
        key.push(blenderDiscs(opts.exclude).map((d) => d.map((v) => (typeof v === 'string' ? v : r3(Number(v))))));
    }
    h.update(JSON.stringify(key));
    return `${new Ch.Cache(info.cache_key).path}/plants_${h.digest('hex').slice(0, 16)}`;
}

export {
    planPlants as plan_plants, expectedCover as expected_cover, cacheBase as cache_base, pathDistance as path_distance,
    terrainConstants as terrain_constants,
};
