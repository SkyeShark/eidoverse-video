// Port of blender/eidoblend/terrain/surface/bake.py at d67f19e.
//
// The surface data bake (SURFACING_DESIGN.md 2.3): per level, the terrain's fields and masks in, the new maps out.
//
//     import * as B from './surface/bake.js';
//     const opts = await B.resolveOptions(terrain, palette, options);   // every setting, the terrain's constants in
//     const { levels, info } = await B.bakeLevels(terrain, opts);       // per level its maps as the cache stores them
//     await B.bakeKey(terrain, opts)                                    // the cache key of that bake
//
// Levels run coarsest first: a level reads what its parent kept (its padded height, settled layer, snow, provenance,
// wider crest and valley terms, filled surface and drainage area), so every map continues across a window edge, and
// each map's outer 16 cells are then blended to the parent's map with masks.pinBand's ramp.
//
// A level works on its window padded by MARGIN cells of its parents' terrain (the parent's padded height upsampled
// with the levels' own Catmull-Rom; beyond the coarsest level a linear extrapolation), so a blur, a march or a
// relaxation at the window's edge sees what the ring next to it shows. Heights go to the GPU less the level's mean
// (float32 keeps 7 digits).
//
// Per level (the design's steps, in the order they run):
//    5  the blur pyramid: crest, valley, n20 (blur, crest)
//   11  wind streaks, when the terrain has a wind (crest's exposure, streak)
//    7  snowpack, when the terrain has a snowline (relax, twice): before the relief, which it buries
//    2  field normal on the detail grid (upsample2, field_normal)
//    3  relief below the cell: a spectrum of flow-steered gullies from the terrain's top octave down to 2 texels,
//       varied in spacing and depth, started by the catchment, none on sand, buried by snow, stepping back where the
//       height already has relief (phacelle); rock ribs (solvers/detail.js's breakup strength)
//    4  cavity and crest_fine on the detail grid (cavity, blur)
//   10  debris provenance: src_strata and grain (carry_src)
//    6  settle (solvers/detail.js's relax)
//    8  the filled surface (fill) on every level; on hero levels the drainage area routed again with the parent's
//       catchment pinned in around the window (flow_weights, pin_inflow, solvers/hydro.js's routeToConvergence),
//       and flow, wetness and channels from it with masks.py's formulas and the main tile's norms
//    9  spi and fresh
//   12  pins (masks.pinBand)
// Gutters are filled when the data textures are made (surface/layers.js), from the parent's pinned maps.
//
// Where this differs from bake.py, and why (PORT_PLAN.md 2.3, 2.4, 3.5: every per-cell step runs on the GPU):
//   - The eleven kernels are surface/kernels/*.wgsl, transcribed (kernel()); every numpy step between them is a
//     kernel of surface/kernels/port/ (own, pad_child, crest_terms, crest_mean, combine, flow_unit, np_gradient, snow,
//     relax_io, gate, carry_io, settle, fill_io, differ, fresh, spi_norm, encode), checked against Blender's own bake
//     of the same terrains (tests/surface_data/bake_test.mjs). JavaScript keeps the level loop, the octave table, the
//     rock's term table (solvers/detail.js breakupTerms), the options, the keys and the few numbers read back.
//   - Fields stay on the GPU from a level's inputs to its maps; a level reads back once: its maps encoded as the
//     surface cache stores them (uint8 for the 8-bit maps, float16 for the rest, float32 for the drainage area and
//     the routing surface: encode.wgsl), plus the reductions the bake decides by (the fill's convergence: a count of
//     the cells a chunk of passes changed, differ.wgsl, instead of the whole surface; the F maps' medians). bake.py
//     reads every intermediate texture back into numpy.
//   - A level keeps for its child the GPU fields bake.py keeps as arrays; they are released once no later level
//     reads them (bake.py drops the grandparent's four largest).
//   - masks.py's pad_level, gaussian_blur, pin_band and norms_from are masks.js's (P7's), crop_upsample2
//     core/grid.js's, detail.relax solvers/detail.js's, route_to_convergence solvers/hydro.js's, percentiles and
//     medians core/prims.js's numpy 2.3.4 arithmetic per call form.
//   - The snowpack's flowing pass relaxes with a repose per cell; solvers/detail.js relax takes one number (its
//     kernels/detail/pipe_start.wgsl writes it into par), so that one call starts the pipe state with relax_io.wgsl's
//     per-cell form and runs the same pipes_thermal passes.
//   - h.mean() (the level's reference height) is core/prims.js stats' float32 tree sum over the float32 heights,
//     divided in doubles, where numpy sums in float64: the reference moves by under a micrometre, and every map is a
//     difference of heights less it.
//   - The keys are the port's own: the code hash is over this edition's surface code (BAKE_CODE), the options' JSON is
//     core/cache.js sortedJson (Python's json.dumps writes 1.0 where JavaScript writes 1). The terrain key is a
//     terrain's cache key, so a Blender terrain and its port share it.
//   - backend 'twin' (bake.py's numpy twins for small grids in plain Python) is not ported: the twins are the oracle,
//     run in Blender's Python (tests/surface_data/surface_fixtures.py); the option is accepted and ignored.
//   - The functions are async (GPU readbacks, files, the palettes module's dynamic import).

import { pyRound, pyReprValue, KeyError, ValueError, closeMatches } from '../core/levels.js';
import * as Gd from '../core/grid.js';
import * as Ch from '../core/cache.js';
import * as N from '../core/world_noise.js';
import { prims } from '../core/prims.js';
import * as M from '../masks.js';
import * as DT from '../solvers/detail.js';
import * as HYD from '../solvers/hydraulic.js';
import * as MP from './maps.js';

const f32 = Math.fround;
export const MARGIN = 48;                   // cells of the parents' terrain around a level's window (even)
export const BAND = 16;                     // the border band: a level's maps are blended to its parent's over it
export const BIG = 1.0e30;
export const BAKE_VERSION = 1;
export const GULLY_LAMBDA0_M = 4096.0;      // the world gully octaves: lambda_o = 4096 m x 2^-o on every level
export const CREST_SCALES_M = [8.0, 16.0, 32.0, 64.0, 128.0];    // crest's octaves, metres, on every level
export const GATE_SCALES_M = [8.0, 16.0, 32.0, 64.0];            // the geometry gates' crest scales
export const GATE_OWN_CELLS = 32.0;         // a level makes a gate whose window (2 s) spans at most this many cells

export const DEFAULTS = {
    maps: 'all',                    // 'all': every map; 'masks': the field normal only (D), beside the masks
    detail: 'auto',                 // the detail grid: 'auto' (half the cell on main and hero levels of at most 1024
                                    // cells, the cell elsewhere), 1 (the cell everywhere) or 2
    detail_strength: 0.5,           // the sub-cell relief's share in the height the cavity march reads
    crest_tau: 0.25,                // crest: the relief ratio one octave saturates at
    valley_min_m: 12.0,             // valley: its finest scale
    valley_flat: [0.16, 25.0],      // valley: the flatness threshold (a tangent) at a scale in metres
    settle: { layer_m: 0.5, repose_deg: 20.0, passes: 60, rate: 0.12 },
    snow: { depth_m: 1.5, band_m: 250.0, aspect_m: 220.0, slip_deg: 38.0, flow_deg: 14.0, passes: 100, rate: 0.12,
        melt_sun_m: 0.9, melt_low_m: 3.0, flow: [0.5, 0.7] },
    fresh: { spi: [0.72, 0.95], over_deg: [1.0, 9.0], steep_deg: [25.0, 35.0] },
    reroute_hero: false,            // route the hero levels' drainage again with the parent's catchment pinned in
    gully: {},                      // the gully filter's parameters over solvers/detail.js's GULLY
    relief: {                       // the gully spectrum (step 3; kernels/phacelle.wgsl says how each is used)
        top_cells: 12.0, top_max_m: 256.0, k: 0.025, jitter: 0.3, spread: 1.2, along: 3.0, steer: 0.35,
        initiation: 1.0, loose_initiation: 4.0, loose_m: [0.3, 2.0], sand_m: [0.1, 0.6], bury: [0.5, 2.0],
        geo: [0.12, 0.35],
    },
    rock_deg: [34.0, 46.0],         // bare rock for provenance and the ribs: a smoothstep of the slope
    reach_m: null,                  // how far fallen rock reaches (null: the masks' rock_toe_reach_m, 300 m)
    carry_passes: 512,              // provenance: the most Jacobi passes a level runs
    streak_cells: 10.0,             // the wind tail's length, cells
    fill_slope: 5.0e-4,             // the filled surface's least descent (metres per metre)
    fill_cap_m: 3.0,                // the deepest pit the fill fills
    flow_p: 1.0,                    // the multiple-flow exponent (the level runner's)
    backend: 'auto',                // 'gpu' | 'twin' | 'auto': accepted, the GPU always (module doc)
    snowline_m: null, base_elevation_m: null, sun_azimuth_deg: null, sun_elevation_deg: null, wind_azimuth_deg: null,
};
// what a constant is when neither the terrain, the palette nor palettes.CONSTANTS names it
export const CONSTANT_DEFAULTS = { base_elevation_m: 0.0, snowline_m: 1.0e5, sun_azimuth_deg: 180.0,
    sun_elevation_deg: 45.0, wind_azimuth_deg: null };
export const NO_SNOW_M = 2.0e4;             // a snowline at or above this is "no snow"

/** The eleven kernels transcribed from Blender's surface/kernels/*.glsl, named as Blender's twins register them. */
export const KERNELS = ['blur', 'upsample2', 'field_normal', 'crest', 'phacelle', 'cavity', 'carry_src', 'streak', 'fill',
    'pin_inflow', 'route_colour'];
export const PREFIX = 'surface_';
export const UPSAMPLE_KINDS = { catmull: 0, bilinear: 1, nearest: 2 };

/** A surface kernel on runner R: surface/kernels/<name>.wgsl (a Blender one, KERNELS), surface/kernels/port/<name>.wgsl
 * (the port's own: numpy code of bake.py moved to the GPU), or with a folder, surface/kernels/<folder>/<name>.wgsl
 * ('palette/...': numpy code of palette_bake.py and far_colour.py; 'atlas/...': of atlas.py and __init__.py's tiles,
 * which the palette bake reuses), compiled once per runner. */
export function kernel(R, name) {
    const blender = KERNELS.includes(name);
    const path = name.includes('/') ? name : `${blender ? '' : 'port/'}${name}`;
    const url = new URL(`kernels/${path}.wgsl`, import.meta.url);
    return R.kernel(PREFIX + name.replace('/', '_'), { url, blender });
}

const clone = (v) => (v === undefined ? undefined : structuredClone(v));
const deg = (d) => (Number(d) * Math.PI) / 180.0;
const tanDeg = (d) => Math.tan(deg(d));
// bake.py's TW.smoothstep edges as a kernel's (float32(e0), float32(e1 - e0)) pair: the doubles numpy rounds
const ssPair = (e0, e1) => [f32(e0), f32(e1 - e0)];
const cover16 = (h, w) => [Math.ceil(w / 16), Math.ceil(h / 16), 1];

let PALETTES_MODULE;
/** build/palettes.js (the look package's data, P14's port), or null when it is not in the checkout. */
export async function palettesModule() {
    if (PALETTES_MODULE === undefined) {
        try {
            Deno.statSync(new URL('../build/palettes.js', import.meta.url));
            PALETTES_MODULE = await import(new URL('../build/palettes.js', import.meta.url).href);
        } catch (_e) {
            PALETTES_MODULE = null;
        }
    }
    return PALETTES_MODULE;
}


// ---------------------------------------------------------------------------------------- the terrain's side ---

const DEFAULTS_MEMO = new WeakMap();

/** The recipe's defaults with its defaultsFor(knobs) merged in, as makeTerrain reads them. A recipe's defaultsFor is
 * async in this edition and may read files with a runner (real_place loads its DEM): it gets { R } and is awaited; a
 * failure leaves the static defaults, as bake.py's try. Memoised per terrain. */
export async function recipeDefaults(terrain) {
    if (terrain && DEFAULTS_MEMO.has(terrain)) return { ...DEFAULTS_MEMO.get(terrain) };
    const Rc = terrain?.recipe ?? null;
    const dfl = { ...(Rc?.defaults ?? {}) };
    const fn = Rc?.defaultsFor ?? Rc?.defaults_for ?? null;
    if (fn) {
        try {
            const G = await import('../core/gpu.js');
            const R = terrain.runner ?? await G.init();
            Object.assign(dfl, (await fn.call(Rc, terrain?.knobs ?? {}, { R })) ?? {});
        } catch (_e) { /* a recipe without its code, or its data */ }
    }
    if (terrain) DEFAULTS_MEMO.set(terrain, dfl);
    return { ...dfl };
}

/** The MaskParams the terrain's masks were made with (the recipe's mask_params, the sea level, the base elevation). */
export async function maskParams(terrain) {
    const info = terrain?.info ?? {};
    const mp = { ...((await recipeDefaults(terrain)).mask_params ?? {}) };
    mp.sea_level = info.sea_level ?? null;
    mp.base_elevation_m = Number(info.base_elevation_m ?? 0.0);
    const allowed = Object.keys(new M.MaskParams().toDict());
    return new M.MaskParams(Object.fromEntries(Object.entries(mp).filter(([k]) => allowed.includes(k))));
}

/** The terrain's own constants: its base elevation, and the snowline and treeline of its knobs, its recipe's mask
 * parameters or its real place (palettes.PLACES). */
export async function terrainConstants(terrain) {
    const info = terrain?.info ?? {};
    const out = {};
    if (info.base_elevation_m !== undefined && info.base_elevation_m !== null) out.base_elevation_m = Number(info.base_elevation_m);
    const knobs = terrain?.knobs ?? {};
    const mp = { ...((await recipeDefaults(terrain)).mask_params ?? {}) };
    if (typeof knobs.dem === 'string') {
        const P = await palettesModule();
        if (P && P.PLACES[knobs.dem]) Object.assign(mp, P.PLACES[knobs.dem].mask_params ?? {});
    }
    for (const key of ['snowline_m', 'treeline_m']) {
        if (knobs[key] !== undefined && knobs[key] !== null) mp[key] = knobs[key];
        if (mp[key] !== undefined && mp[key] !== null) out[key] = Number(mp[key]);
    }
    return out;
}

/** The filled-in palette a bake reads: `palette` as a name, 'auto', a palette object or one already filled in
 * (palettes.get), with the terrain's place strata merged in and the terrain's constants over the palette's. null
 * stays null. */
export async function resolvePalette(terrain, palette) {
    if (palette === null || palette === undefined) return null;
    const P = await palettesModule();
    if (!P) throw new ValueError('a palette needs build/palettes.js (the surfacing wave), which is not in this checkout');
    const info = terrain?.info ?? {};
    let pal;
    if (palette && typeof palette === 'object' && 'options' in palette && 'constants' in palette) {
        pal = clone(palette);
    } else {
        pal = P.get(palette, terrain?.recipe ?? null);
        const place = info.place;
        const st = place ? (P.PLACES[place] ?? {}).strata : null;
        if (st) {
            pal.strata = { ...(pal.strata ?? {}), ...clone(st) };
            for (const [k, v] of Object.entries(P.STRATA_DEFAULTS)) if (!(k in pal.strata)) pal.strata[k] = clone(v);
        }
    }
    for (const [k, v] of Object.entries(await terrainConstants(terrain))) pal.constants[k] = Number(v);
    return pal;
}

/** Every bake setting: DEFAULTS, the given options over them (an object option merges key by key), and the terrain
 * constants filled in: an option given wins, then the terrain's own, then the palette's, then palettes.CONSTANTS,
 * then CONSTANT_DEFAULTS. A palette's options may carry `relief` (an object over DEFAULTS.relief); an option given
 * wins over it. Throws KeyError naming an unknown option or relief key. */
export async function resolveOptions(terrain, palette = null, options = null) {
    const opts = clone(DEFAULTS);
    const pal = (palette === null || palette === undefined || typeof palette === 'object') ? palette :
        await resolvePalette(terrain, palette);
    const lookRelief = pal?.options?.relief;
    const srcs = (lookRelief && typeof lookRelief === 'object' && !Array.isArray(lookRelief) ? [{ relief: lookRelief }] : [])
        .concat([options ?? {}]);
    for (const src of srcs) {
        for (const [k, v] of Object.entries(src)) {
            if (!(k in DEFAULTS)) {
                const near = closeMatches(k, Object.keys(DEFAULTS), 3);
                throw new KeyError(`bake_surface: no option ${pyReprValue(k)}` + (near.length ? `; nearest: ${near.join(', ')}` : ''));
            }
            if (k === 'relief' && v && typeof v === 'object') {
                const bad = Object.keys(v).filter((q) => !(q in DEFAULTS.relief));
                if (bad.length) throw new KeyError(`bake_surface: no relief key ${pyReprValue(bad[0])}; the keys: ${Object.keys(DEFAULTS.relief).join(', ')}`);
            }
            const d = DEFAULTS[k];
            if (d && typeof d === 'object' && !Array.isArray(d) && v && typeof v === 'object' && !Array.isArray(v)) {
                Object.assign(opts[k], clone(v));
            } else {
                opts[k] = clone(v);
            }
        }
    }
    const palConsts = { ...(pal?.constants ?? {}) };
    const P = await palettesModule();
    const base = P ? { ...P.CONSTANTS } : {};
    const own = await terrainConstants(terrain);
    const given = options ?? {};
    const explicitSun = ['sun_azimuth_deg', 'sun_elevation_deg'].some((k) => k in given || k in own || k in palConsts);
    for (const [k, dflt] of Object.entries(CONSTANT_DEFAULTS)) {
        if (opts[k] === null || opts[k] === undefined) {
            const v = k in own ? own[k] : (k in palConsts ? palConsts[k] : (k in base ? base[k] : dflt));
            opts[k] = v === null || v === undefined ? null : Number(v);
        }
    }
    // the place's climatological sun (palettes.climate_sun from latitude_deg), unless something sets it outright
    const climateSun = P?.climateSun ?? P?.climate_sun ?? null;
    if (climateSun && !explicitSun) {
        const [az, el] = climateSun({ ...base, ...palConsts, ...own });
        opts.sun_azimuth_deg = Number(az);
        opts.sun_elevation_deg = Number(el);
    }
    if (opts.reach_m === null || opts.reach_m === undefined) opts.reach_m = Number((await maskParams(terrain)).rock_toe_reach_m);
    return opts;
}

// the port's surface code each hash covers (paths relative to eidoverse/terrain/; bake.py's BAKE_CODE, PALETTE_CODE
// and ATLAS_CODE, by the same roles)
export const BAKE_CODE = ['surface/bake.js', 'surface/maps.js', 'surface/kernels/*.wgsl', 'surface/kernels/port/*.wgsl'];
export const PALETTE_CODE = ['surface/palette_bake.js', 'surface/far_colour.js', 'surface/mask_expr.js', 'surface/noise.js',
    'build/ops.js', 'surface/kernels/palette/*.wgsl', 'surface/kernels/atlas/*.wgsl'];
export const ATLAS_CODE = ['surface/index.js', 'surface/layers.js', 'surface/maps.js', 'surface/kernels/atlas/*.wgsl'];

/** SHA-1 over a part of the surface package's code (core/cache.js codeHash over these globs). */
export function codeHash(globs = BAKE_CODE) {
    return Ch.codeHash(globs);
}

async function sha1Hex(bytesOrText) {
    const data = typeof bytesOrText === 'string' ? new TextEncoder().encode(bytesOrText) : bytesOrText;
    const d = await crypto.subtle.digest('SHA-1', data);
    return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** What names the terrain in a bake key: its cache key, or (a terrain made without one) a hash of its plan and its
 * main level's height. */
export async function terrainKey(terrain) {
    const info = terrain?.info ?? {};
    if (info.cache_key) return String(info.cache_key);
    const parts = terrain.levels.map((lv) => JSON.stringify([lv.x0, lv.y0, lv.cell, lv.n, lv.role])).join('|');
    const h = terrain.fields(mainIndex(terrain.levels)).h;
    const enc = new TextEncoder().encode(parts);
    const all = new Uint8Array(enc.length + h.byteLength);
    all.set(enc, 0);
    all.set(new Uint8Array(h.buffer, h.byteOffset, h.byteLength), enc.length);
    return 'nokey_' + await sha1Hex(all);
}

/** The bake's cache key: SHA-1 of the terrain's key, the bake's code, its version and its options. */
export async function bakeKey(terrain, opts) {
    const o = Object.fromEntries(Object.entries(opts).filter(([k]) => k !== 'backend'));
    return sha1Hex(Ch.sortedJson({ terrain: await terrainKey(terrain), code: codeHash(), version: BAKE_VERSION, options: o }));
}

export function mainIndex(levels) {
    const roles = levels.map((lv) => lv.role);
    if (roles.includes('main')) return roles.indexOf('main');
    const nonHero = roles.map((r, i) => [r, i]).filter(([r]) => r !== 'hero').map(([, i]) => i);
    return nonHero.length ? nonHero[nonHero.length - 1] : levels.length - 1;
}

/** Detail texels per cell on a level: 'auto' gives 2 on the main and hero levels of at most 1024 cells whose cell is
 * 2 m or more, else 1. */
export function detailFactor(level, opts) {
    const d = opts.detail ?? 'auto';
    if (d === 'auto') return (['main', 'hero'].includes(level.role) && level.n <= 1024 && Number(level.cell) >= 2.0 - 1e-6) ? 2 : 1;
    const k = Math.trunc(Number(d));
    if (k !== 1 && k !== 2) throw new ValueError(`bake_surface: detail ${pyReprValue(d)} is 'auto', 1 or 2`);
    return k === 2 && level.n <= 1024 ? 2 : 1;
}

// how the cache stores a map (__init__.py _stored): ['u8', encode kind, scale] | ['f16'] | ['f32']
export function storedForm(name, cell) {
    if (name === 'area' || name.startsWith('_')) return ['f32'];
    let s = null;
    try {
        s = MP.spec(name);
    } catch (_e) { /* not a registry map: kept in half */ }
    if (s && (s.family === 'E' || s.family === 'M') && ['unit', 'signed', 'bend', 'thick'].includes(s.encoding)) {
        const kind = { unit: 0, signed: 1, bend: 2, thick: 3 }[s.encoding];
        const scale = s.encoding === 'bend' ? MP.bendScale(s, cell) : s.encoding === 'thick' ? 1.0 / s.t_max : 1.0;
        return ['u8', kind, scale];
    }
    return ['f16'];
}

// the F family's arrays, kept in float16 less their level's reference (__init__.py _REF_OF)
export const REF_OF = { strata_dz: 'strata', src_dz: 'src_strata' };


// ------------------------------------------------------------------------------------------------- the bake ---

class Baker {
    /** One bake: the state every level shares (the terrain, the options, the runner, the main tile's norms) and what
     * each level keeps for its child. Use Baker.make (async). */
    constructor(terrain, opts, R, log, P) {
        this.t = terrain;
        this.o = opts;
        this.R = R;
        this.Pr = prims(R);
        this.log = log ?? (() => {});
        this.levels = [...terrain.levels];
        this.P = P;
        this.main = mainIndex(this.levels);
        const info = terrain.info ?? {};
        this.seed = Math.trunc(Number(info.seed ?? 0));
        this.base = Number(opts.base_elevation_m ?? 0.0);
        this.keep = new Map();
        this.times = [];
        this.octaveM = new Map();
        this._stages = null;
        this.snowOn = opts.snowline_m !== null && Number(opts.snowline_m) < NO_SNOW_M;
        this.wind = null;
        if (opts.wind_azimuth_deg !== null && opts.wind_azimuth_deg !== undefined) {
            const az = deg(opts.wind_azimuth_deg);
            this.wind = [Math.sin(az), Math.cos(az)];            // the unit vector the wind blows toward (a bearing)
        }
        const az = deg(opts.sun_azimuth_deg), el = deg(opts.sun_elevation_deg);
        this.sun = [Math.sin(az) * Math.cos(el), Math.cos(az) * Math.cos(el), Math.sin(el)];
        // the last level that reads each level as its parent: a level's fields go when it is done
        this.lastChild = new Map();
        this.levels.forEach((lv, i) => { if (lv.parent !== null && lv.parent !== undefined) this.lastChild.set(lv.parent, i); });
    }

    static async make(terrain, opts, R, log) {
        if (!['all', 'masks'].includes(opts.maps ?? 'all')) throw new ValueError(`bake_surface: maps ${pyReprValue(opts.maps)} is 'all' or 'masks'`);
        const B = new Baker(terrain, opts, R, log, await maskParams(terrain));
        const fm = terrain.fields(B.main);
        const lv = B.levels[B.main];
        const up = B.uploads(lv, fm, ['h', 'A', 'water']);
        try {
            B.norms = await M.normsFrom(up, { cell: lv.cell, params: B.P });
            B.spiNorm = await B.spiNorms(up, lv);
        } finally {
            for (const f of Object.values(up)) f.destroy();
        }
        return B;
    }

    // a level's host arrays as GPU fields ({ name: r32f }) for the names it has
    uploads(lv, arrays, names) {
        const out = {};
        for (const nm of names) {
            const a = arrays[nm];
            if (a !== undefined && a !== null) out[nm] = this.R.field(lv.n, lv.n, 1, a instanceof Float32Array ? a : new Float32Array(a));
        }
        return out;
    }

    // ---- norms and recipe stages

    /** The 5th and 95th percentiles of log10(a tan S) over the main tile's land (spi's normalisation), S the slope of
     * the height blurred at 20 m, as the levels' spi reads it. null without a drainage area. */
    async spiNorms(f, lv) {
        if (!f.A) return null;
        const R = this.R, cell = Number(lv.cell), n = lv.n;
        const st = await this.Pr.stats(f.h);
        const mean = st.sum / st.count;
        const hc = this.run1('own', { a: f.h }, { uMode: 0, uHi: f32(mean), uLo: f32(mean - f32(mean)) }, [n, n]);
        let hb = hc;
        const s20 = 20.0 / cell;
        if (s20 > 0.25) {
            const m = Math.ceil(4.0 * s20) + 2;
            const hp = M.padLevel(hc, m, cell, { wrap: this.P.wrap, fill: 'odd' });
            const b = M.gaussianBlur(hp, s20);
            hb = this.crop1(b, m, n);
            hp.destroy();
            b.destroy();
        }
        const hp1 = M.padLevel(hb, 1, cell, { wrap: this.P.wrap, fill: 'odd', pair: true });
        const geo = M.gradient(hp1, 1, n, n, cell);
        hp1.destroy();
        const D = Gd.dummies(R);
        const wk = f.water ? 1 : (this.P.sea_level !== null && this.P.sea_level !== undefined ? 2 : 0);
        const v = R.field(n, n, 1), land = R.field(n, n, 1);
        R.run(kernel(R, 'spi_norm'), { A: f.A, geo, water: f.water ?? D.f1, h: f.h }, { outV: v, outL: land },
            { uCell: cell, uCell2: cell * cell, uWater: wk, uSea: Number(this.P.sea_level ?? 0.0) });
        geo.destroy();
        if (hb !== hc) hb.destroy();
        hc.destroy();
        let mask = null;
        if (wk) {
            const cnt = (await this.Pr.stats(land, { mask: land })).count;
            if (cnt >= 16) mask = land;
        }
        const [lo, hi] = await this.Pr.percentile(v, [5.0, 95.0], { dtype: 'float64', ...(mask ? { mask } : {}) });
        v.destroy();
        land.destroy();
        return [lo, Math.max(hi, lo + 0.5)];
    }

    /** The recipe's stages with the knobs put in (their op, params and level selection), or []. */
    stages() {
        if (this._stages === null) {
            this._stages = [];
            const R = this.t.recipe ?? null;
            if (R && typeof R.resolve === 'function') {
                try {
                    const [, stages] = R.resolve(this.t.knobs ?? null);
                    this._stages = stages.filter((s) => (s.params ?? {}).enabled !== false)
                        .map((s) => [s, new Set(s.select(this.levels, () => {}))]);
                } catch (e) {
                    this.log(`[surface] the recipe's stages could not be read (${e.message}): defaults are used`);
                }
            }
        }
        return this._stages;
    }

    /** [params, ran]: the params of the recipe's first stage of `op`, and whether one ran on level i. */
    stage(op, i) {
        const hits = this.stages().filter(([s]) => s.op === op);
        if (!hits.length) return [{}, false];
        const on = hits.filter(([, sel]) => sel.has(i)).map(([s]) => s);
        return [{ ...(on.length ? on[0] : hits[0][0]).params }, on.length > 0];
    }

    // ---- small dispatches

    // one dispatch of a port kernel into a new field of `shape` (channels ch) as its first image; its other images
    // are 1 x 1 stand-ins (a store outside a field does nothing), every sampler and uniform not given a stand-in or 0
    run1(name, samplers, uniforms, shape, ch = 1) {
        const R = this.R, k = kernel(R, name), D = Gd.dummies(R);
        const out = R.field(shape[0], shape[1], ch);
        const s = {};
        for (const nm of k.spec.samplers) s[nm] = samplers[nm] ?? D.f1;
        const u = {};
        for (const [nm, t] of Object.entries(k.spec.uniforms)) u[nm] = uniforms[nm] ?? zeroOf(t);
        const images = { [k.imageNames[0]]: out };
        const extra = [];
        for (const nm of k.imageNames.slice(1)) {
            const fmt = k.spec.images[nm];
            const d = R.field(1, 1, fmt === 'r32f' ? 1 : fmt === 'rg32f' ? 2 : fmt.startsWith('r32') || fmt.startsWith('atomic') ? 1 : 4,
                null, fmt === 'r32ui' || fmt === 'atomic_u32' ? 'u32' : fmt === 'r32i' || fmt === 'atomic_i32' ? 'i32' : 'f32');
            images[nm] = d;
            extra.push(d);
        }
        R.run(k, s, images, u);
        for (const d of extra) d.destroy();
        return out;
    }

    // channel c of a field at offset (dx, dy), into a new r32f field of shape (h, w) (pick.wgsl)
    channel(src, c, dx, dy, h, w) {
        const R = this.R;
        const one = R.field(h, w, 1);
        R.run(kernel(R, 'pick'), { a: src }, { outF: one }, { uCh: c, uOffset: [dx, dy] });
        return one;
    }

    // the window of a padded r32f field: m cells in, n x n (bake.py _crop(a, m, n))
    crop1(src, m, n, f = 1) {
        return this.channel(src, 0, m * f, m * f, n * f, n * f);
    }

    /** Four Gaussian blurs (their sigmas in texels; 0: a copy) as one RGBA field, two dispatches: of src.x (fan) or
     * of src's four channels each. */
    blur4(src, sig4, fan = true) {
        const R = this.R, k = kernel(R, 'blur');
        const a = R.field(src.h, src.w, 4), b = R.field(src.h, src.w, 4);
        const sig = sig4.map(Number);
        R.run(k, { src }, { outB: a }, { uSigma: sig, uDir: [1, 0], uFan: fan ? 1 : 0 });
        R.run(k, { src: a }, { outB: b }, { uSigma: sig, uDir: [0, 1], uFan: 0 });
        a.destroy();
        return b;
    }

    win(i) {
        const lv = this.levels[i];
        const [i0, j0, mc] = lv.inParent(this.levels);
        return [i0 - MARGIN / 2 + MARGIN, j0 - MARGIN / 2 + MARGIN, mc + MARGIN];
    }

    /** The parent's padded field `key` on level i's whole padded grid (the child starts from it). */
    inherit(i, key, kind = 'bilinear') {
        const lv = this.levels[i];
        const [a, b, m] = this.win(i);
        return Gd.cropUpsample2(this.keep.get(lv.parent)[key], a, b, m, kind);
    }

    /** A level's field padded by MARGIN cells: the window its own (an n x n GPU field), the margin its parent's padded
     * field upsampled (kind) times `scale` plus `shift`; on the coarsest level the margin is `fill`
     * (masks.padLevel). A new r32f (N, N) field; `own` is not released. */
    pad(i, own, key, kind = 'bilinear', fill = 'edge', shift = 0.0, scale = 1.0) {
        const lv = this.levels[i];
        const par = lv.parent !== null && lv.parent !== undefined ? this.keep.get(lv.parent) : null;
        if (!par || !par[key]) {
            return M.padLevel(own, MARGIN, lv.cell, { x0: lv.x0, y0: lv.y0, wrap: this.P.wrap, outside: null, fill });
        }
        const up = this.inherit(i, key, kind);
        const out = this.run1('pad_child', { up, own }, { uM: MARGIN, uScale: f32(scale), uShift: f32(shift) }, [up.h, up.w]);
        up.destroy();
        return out;
    }

    /** A parent's padded RGBA field upsampled onto level i's padded grid (upsample2.wgsl). */
    fromParentTex(i, tex, kind) {
        const R = this.R, lv = this.levels[i];
        const [i0, j0] = lv.inParent(this.levels);
        const N_ = lv.n + 2 * MARGIN;
        const out = R.field(N_, N_, 4);
        R.run(kernel(R, 'upsample2'), { src: tex }, { outU: out },
            { uOrigin: [i0 - MARGIN / 2 + MARGIN, j0 - MARGIN / 2 + MARGIN], uSize: [N_, N_], uKind: UPSAMPLE_KINDS[kind] });
        return out;
    }

    // ---- one level

    /** maps='masks': the field normal on the detail grid (step 2), pinned, and nothing else. */
    async levelNormal(i) {
        const R = this.R, lv = this.levels[i], t0 = performance.now();
        const par = lv.parent !== null && lv.parent !== undefined ? this.keep.get(lv.parent) ?? null : null;
        const n = lv.n, m = MARGIN, cell = Number(lv.cell), fD = detailFactor(lv, this.o), ND = (n + 2 * m) * fD;
        const f = this.t.fields(i);
        const hO = this.uploads(lv, f, ['h']).h;
        const href = await this.reference(hO);
        const shift = par ? par.href - href : 0.0;
        const own = this.run1('own', { a: hO }, { uMode: 0, uHi: f32(href), uLo: f32(href - f32(href)) }, [n, n]);
        hO.destroy();
        const hp = this.pad(i, own, 'hp', 'catmull', 'odd', shift);
        own.destroy();
        let hD = hp;
        if (fD === 2) {
            hD = R.field(ND, ND, 4);
            R.run(kernel(R, 'upsample2'), { src: hp }, { outU: hD }, { uOrigin: [0, 0], uSize: [ND, ND], uKind: 0 });
        }
        const hg = R.field(ND, ND, 4);
        R.run(kernel(R, 'field_normal'), { hT: hD }, { outG: hg }, { uTexel: cell / fD });
        if (hD !== hp) hD.destroy();
        // normal = (-g.y / L, -g.z / L), L = sqrt(1 + g.y^2 + g.z^2): phacelle's outD without the relief
        const out = {};
        const nrm = this.normalOf(hg);
        hg.destroy();
        out.normal_x = this.crop1(nrm, m, n, fD);
        out.normal_y = this.channel(nrm, 1, m * fD, m * fD, n * fD, n * fD);
        nrm.destroy();
        if (par) this.pin(i, out, fD);
        this.keep.set(i, { href, hp, pinned: { ...out }, fD });
        this.times.push({ total: +((performance.now() - t0) / 1000).toFixed(4) });
        return out;
    }

    // (nx, ny, 0, 0) of the field normal from field_normal's (h, dh/dx, dh/dy, tan) (levelNormal; phacelle writes it
    // into outD itself): -g.y / L, -g.z / L, L = sqrt(1 + g.y g.y + g.z g.z), in float32 as bake.py's numpy
    normalOf(hg) {
        const R = this.R;
        const out = R.field(hg.h, hg.w, 4);
        const zero = R.field(1, 1, 4), rel = R.field(1, 1, 4);
        R.run(kernel(R, 'phacelle'), { hgT: hg, steerT: zero, octT: zero, rockT: zero, coverT: zero, gateT: zero },
            { outD: out, outR: rel }, this.phacelleNone());
        zero.destroy();
        rel.destroy();
        return out;
    }

    phacelleNone() {
        return { uOct: 0, uTexel: 1, uF: 1, uSteer: 0, uNorm: 0, uSlope: [10, 18, 30, 38], uRockDeg: [90, 91],
            uCover: [0.1, 1], uNormalCap: 1, uRockRef: 1, uRockOn: 0, uStrength: 0, uSpec: [0, 0, 1, 0], uInit: [1, 1, 0, 1],
            uLoose: [0, 1], uBury: [0, 1] };
    }

    /** The level's reference height: the mean of its heights (prims stats' tree sum, divided in doubles). */
    async reference(h) {
        const st = await this.Pr.stats(h);
        return st.sum / st.count;
    }

    async level(i) {
        if ((this.o.maps ?? 'all') === 'masks') return this.levelNormal(i);
        const R = this.R, o = this.o, D = Gd.dummies(R);
        const lv = this.levels[i];
        const f = this.t.fields(i);
        const mk = this.t.masks.level(i);
        const par = lv.parent !== null && lv.parent !== undefined ? this.keep.get(lv.parent) ?? null : null;
        const n = lv.n, m = MARGIN, cell = Number(lv.cell);
        const N_ = n + 2 * m;
        const fD = detailFactor(lv, o);
        const texel = cell / fD;
        const ND = N_ * fD;
        const tm = {};
        const t0 = performance.now();
        const lap = (k, t) => { tm[k] = (performance.now() - t) / 1000; };
        const keep = {};
        const out = {};
        const drop = (...fs) => { for (const x of fs) if (x && !x.destroyed && !Object.values(keep).includes(x)) x.destroy(); };

        // ---- inputs: the padded height (less the level's mean), cover, water, strata, drainage area
        const fieldNames = ['h', 'A', 'deposit', 'talus', 'sand', 'Sc', 'flow_x', 'flow_y', 'wear_recent'];
        const up = this.uploads(lv, f, fieldNames.filter((k) => k in f));
        const mup = this.uploads(lv, mk, ['water', 'strata', 'flow'].filter((k) => k in mk));
        const href = await this.reference(up.h);
        const shift = par ? par.href - href : 0.0;
        const hi = f32(href), lo = f32(href - hi);
        const ownH = this.run1('own', { a: up.h }, { uMode: 0, uHi: hi, uLo: lo }, [n, n]);
        const hp = this.pad(i, ownH, 'hp', 'catmull', 'odd', shift);
        keep.href = href;
        keep.hp = hp;
        const has = ['deposit', 'talus', 'sand'].map((k) => (up[k] ? 1 : 0));
        const cover = this.run1('own', { a: up.deposit ?? D.f1, b: up.talus ?? D.f1, c: up.sand ?? D.f1 },
            { uMode: 1, uHas: [...has, 0] }, [n, n]);
        keep.cover = this.pad(i, cover, 'cover');
        const water = mup.water ? this.run1('own', { a: mup.water }, { uMode: 2 }, [n, n]) : Gd.fill(R, [n, n], 0.0);
        keep.water = this.pad(i, water, 'water');
        const zsOwn = mup.strata ? this.run1('own', { a: mup.strata }, { uMode: 0, uHi: hi, uLo: lo }, [n, n]) : ownH;
        keep.zs = this.pad(i, zsOwn, 'zs', 'bilinear', 'edge', shift);
        if (zsOwn !== ownH) zsOwn.destroy();
        const hasA = !!up.A;
        const tH = hp;
        lap('inputs', t0);

        // ---- step 5: the blur pyramid, crest, valley, n20 (and the gully filter's steering, the wind exposure)
        let t1 = performance.now();
        const s20 = 20.0 / cell;
        const n20Own = s20 <= 16.0 || !par;
        const pyrA = this.blur4(tH, [1.0, 2.0, 4.0, 8.0]);
        const pyrB = this.blur4(tH, [16.0, Math.min(s20, 16.0), 0.0, 0.0]);
        const parT = par ? this.fromParentTex(i, par.tK, 'bilinear') : R.field(1, 1, 4);
        const outC = R.field(N_, N_, 4), outK = R.field(N_, N_, 4), outX = R.field(N_, N_, 4);
        const wind = this.wind ?? [0.0, 0.0];
        const inherited = par ? par.crest_inherited + 1 : 0;
        keep.crest_inherited = inherited;
        R.run(kernel(R, 'crest'), { hT: tH, pyrA, pyrB, parT }, { outC, outK, outX },
            { uCell: cell, uTau: Number(o.crest_tau), uTerms: 5.0 + inherited, uSmin: Number(o.valley_min_m),
                uValley: o.valley_flat.map(Number), uHasParent: par ? 1 : 0, uN20Own: n20Own ? 1 : 0, uWind: wind });
        // what the child reads of this level: (Kc, Kv, n20 x, n20 y) in one field
        keep.tK = R.field(N_, N_, 4);
        R.run(kernel(R, 'combine'), { a: outK, b: outC }, { outF: keep.tK }, { uMode: 0, uOffset: [0, 0] });
        out.crest = this.crestMetres(i, tH, par, keep);
        out.valley = this.channel(outC, 1, m, m, n, n);
        out.n20_x = this.channel(outC, 2, m, m, n, n);
        out.n20_y = this.channel(outC, 3, m, m, n, n);
        drop(pyrA, pyrB, parT);
        lap('pyramid', t1);

        // ---- step 11: wind streaks
        if (this.wind) {
            t1 = performance.now();
            const sT = R.field(N_, N_, 1);
            R.run(kernel(R, 'streak'), { exT: outX }, { outS: sT }, { uWind: this.wind, uLength: Number(o.streak_cells) });
            out.streak = this.crop1(sT, m, n);
            sT.destroy();
            lap('streak', t1);
        }
        outX.destroy();

        // ---- the slope, the field normal's parts and the altitude on the padded cell grid (snow)
        // ---- step 7: snowpack (before the relief, which it buries)
        let pack = null;
        if (this.snowOn) {
            t1 = performance.now();
            pack = await this.snowpack(i, hp, href, mup, par, keep);
            out.snowpack = this.crop1(pack, m, n);
            lap('snow', t1);
        }

        // ---- steps 2-4: the detail grid
        t1 = performance.now();
        let steer = outK;
        if (up.flow_x && up.flow_y) {                     // the routed flow vector, where the level has one
            const fu = R.field(n, n, 2);
            R.run(kernel(R, 'flow_unit'), { fx: up.flow_x, fy: up.flow_y }, { outF: fu }, {});
            const ux = this.channel(fu, 0, 0, 0, n, n), uy = this.channel(fu, 1, 0, 0, n, n);
            steer = R.field(N_, N_, 4);
            R.run(kernel(R, 'combine'), { a: ux, b: uy }, { outF: steer }, { uMode: 2, uOffset: [-m, -m] });
            for (const x of [fu, ux, uy]) x.destroy();
        }
        const sand = up.sand ? this.run1('own', { a: up.sand }, { uMode: 2 }, [n, n]) : Gd.fill(R, [n, n], 0.0);
        keep.sand = this.pad(i, sand, 'sand');
        sand.destroy();
        const aSpec = this.catchment(i, up, keep);
        const packF = pack ?? Gd.fill(R, [N_, N_], 0.0);
        const tCover = R.pack({ c: keep.cover, s: keep.sand, p: packF, a: aSpec }, ['c', 's', 'p', 'a']);
        if (!pack) packF.destroy();
        let hD = tH;
        if (fD === 2) {
            hD = R.field(ND, ND, 4);
            R.run(kernel(R, 'upsample2'), { src: tH }, { outU: hD }, { uOrigin: [0, 0], uSize: [ND, ND], uKind: 0 });
        }
        const hg = R.field(ND, ND, 4);
        R.run(kernel(R, 'field_normal'), { hT: hD }, { outG: hg }, { uTexel: texel });
        const { octs, gp, rp } = this.gullyOctaves(i, texel);
        // the table's octaves (a level too coarse for any: none), and their wavelengths (info.relief_octaves)
        let nOct = 0;
        for (let k = 0; 2 * k + 1 < octs.length / 4; k++) if (octs[4 * (2 * k + 1) + 2] > 0.5) nOct++;
        const oct = [];
        for (let k = 0; k < nOct; k++) oct.push(roundTo(1.0 / octs[4 * (2 * k + 1)], 6));
        this.octaveM.set(i, oct);
        const gates = this.geoGates(i, keep, octs);
        const { rockT, rockRef, rockDeg, normalCap } = this.rockRelief(i, hg, texel, ND);
        const outD = R.field(ND, ND, 4), outR = R.field(ND, ND, 4);
        const octT = R.field(1, octs.length / 4, 4, octs);
        const dummy4 = R.field(1, 1, 4);
        R.run(kernel(R, 'phacelle'), { hgT: hg, steerT: steer, octT, rockT: rockT ?? dummy4, coverT: tCover, gateT: gates },
            { outD, outR },
            { uOct: nOct, uTexel: texel, uF: fD, uSteer: Number(rp.steer), uNorm: Number(gp.normalization),
                uSlope: gp.slope_deg.map(Number), uRockDeg: rockDeg, uCover: this.P.cover_m.map(Number),
                uNormalCap: normalCap, uRockRef: rockRef, uRockOn: rockT ? 1 : 0, uStrength: Number(o.detail_strength),
                uSpec: [Number(rp.jitter), Number(rp.spread), Number(rp.along), 0.0],
                uInit: [Number(rp.initiation), Number(rp.loose_initiation), ...rp.sand_m.map(Number)],
                uLoose: rp.loose_m.map(Number), uBury: rp.bury.map(Number) });
        drop(tCover, gates, octT, dummy4);
        const blurD = this.blur4(outR, [1.0, 1.0, 1.0, 1.0], false);     // the relief surface at 1 and 2 texels
        const blurD2 = this.blur4(outR, [2.0, 2.0, 2.0, 2.0], false);
        const outE = R.field(ND, ND, 4);
        R.run(kernel(R, 'cavity'), { zT: outR, blurT: blurD, blur2T: blurD2 }, { outE }, { uTexel: texel, uTau: Number(o.crest_tau) });
        lap('detail', t1);
        t1 = performance.now();
        ['normal_x', 'normal_y', 'detail_gx', 'detail_gy'].forEach((nm, c) => { out[nm] = this.channel(outD, c, m * fD, m * fD, n * fD, n * fD); });
        ['crease', 'cavity', 'crest_fine'].forEach((nm, c) => { out[nm] = this.channel(outE, c, m * fD, m * fD, n * fD, n * fD); });
        drop(outD, outR, outE, blurD, blurD2, hg, rockT);
        if (hD !== tH) hD.destroy();
        if (steer !== outK) steer.destroy();
        drop(outK, outC);
        lap('detail_read', t1);

        // ---- step 10: debris provenance
        t1 = performance.now();
        const reach = Number(o.reach_m);
        const aux = R.field(N_, N_, 4);
        R.run(kernel(R, 'carry_io'), { a: keep.cover, b: keep.zs, c: D.f1 }, { outF: aux },
            { uMode: 0, uChild: par ? 1 : 0, uM: m, uShift: 0, uReach: reach, uFade: [0, 1] });
        let st0;
        if (par) {
            const upc = this.fromParentTex(i, par.carry, 'nearest');
            st0 = R.field(N_, N_, 4);
            R.run(kernel(R, 'carry_io'), { a: upc, b: D.f1, c: D.f1 }, { outF: st0 },
                { uMode: 1, uChild: 1, uM: m, uShift: f32(shift), uReach: reach, uFade: [0, 1] });
            upc.destroy();
        } else {
            st0 = R.field(N_, N_, 4);
            R.run(kernel(R, 'carry_io'), { a: keep.zs, b: D.f1, c: D.f1 }, { outF: st0 },
                { uMode: 1, uChild: 0, uM: m, uShift: 0, uReach: reach, uFade: [0, 1] });
        }
        const passes = Math.trunc(Math.min(Math.max(Math.ceil(reach / cell), 4), Math.trunc(Number(o.carry_passes))));
        let sA = st0, sB = R.field(N_, N_, 4);
        const kc = kernel(R, 'carry_src');
        const ku = { uCell: cell, uRockDeg: o.rock_deg.map(Number), uCover: this.P.cover_m.map(Number),
            uSalt: Math.trunc(i) + 7919 * (this.seed & 0xffff) };
        for (let k = 0; k < passes; k++) {
            R.run(kc, { hT: tH, auxT: aux, stT: sA }, { outS: sB }, ku);
            [sA, sB] = [sB, sA];
        }
        sB.destroy();
        aux.destroy();
        keep.carry = sA;
        const co = R.field(n, n, 4);
        R.run(kernel(R, 'carry_io'), { a: sA, b: keep.zs, c: hp }, { outF: co },
            { uMode: 2, uChild: par ? 1 : 0, uM: m, uShift: 0, uReach: f32(reach), uFade: ssPair(0.7 * reach, reach) });
        out.strata_dz = this.channel(co, 0, 0, 0, n, n);
        out.src_dz = this.channel(co, 1, 0, 0, n, n);
        out.grain = this.channel(co, 2, 0, 0, n, n);
        co.destroy();
        lap('carry', t1);

        // ---- step 6: settle
        t1 = performance.now();
        const so = o.settle;
        const layer = Number(so.layer_m);
        const inhS = par ? this.inherit(i, 'settle_d') : null;
        const d0 = this.run1('settle', { a: inhS ?? D.f1 }, { uMode: 0, uChild: par ? 1 : 0, uM: m, uLayer: f32(layer) }, [N_, N_]);
        if (inhS) inhS.destroy();
        const d1 = this.relax(hp, d0, tanDeg(so.repose_deg), Math.trunc(so.passes), Number(so.rate), cell);
        d0.destroy();
        keep.settle_d = d1;
        out.settle = this.run1('settle', { a: d1 }, { uMode: 1, uChild: 0, uM: m, uLayer: f32(layer) }, [n, n]);
        lap('settle', t1);

        // ---- step 8: the filled surface; on hero levels the drainage area again, the parent's catchment pinned in
        t1 = performance.now();
        const { W, passes: fillPasses } = await this.fill(i, hp, keep.water);
        keep.fill = W;
        lap('fill', t1);
        let Aw = hasA ? up.A : null;
        if (hasA) {
            t1 = performance.now();
            if (o.reroute_hero && lv.role === 'hero' && par && par.A) {
                const { A: Ap, iters } = await this.route(i, W, par);
                Aw = this.crop1(Ap, m, n);
                keep.A = Ap;
                out.area = Aw;
                Object.assign(out, await this.drainageMasks(Aw, up, mup, lv));
                lap('route', t1);
                tm.route_iterations = iters;
            } else {
                keep.A = this.pad(i, up.A, 'A', 'bilinear', 'edge', 0.0, 0.5);
            }
        }
        tm.fill_passes = fillPasses;

        // ---- step 9: spi and fresh
        if (hasA && this.spiNorm) {
            t1 = performance.now();
            const [slo, shi] = this.spiNorm;
            const fo = o.fresh;
            const sl = fo.steep_deg ?? [25.0, 35.0];
            const spi = R.field(n, n, 1), fresh = R.field(n, n, 1);
            R.run(kernel(R, 'fresh'), { A: Aw, n20x: out.n20_x, n20y: out.n20_y, water, cover, Sc: up.Sc ?? D.f1,
                wr: up.wear_recent ?? D.f1 }, { outS: spi, outF: fresh },
            { uCell: f32(cell), uCell2: f32(cell * cell), uNorm: [f32(slo), f32(shi - slo)], uWet: ssPair(0.0, 0.3),
                uCover: ssPair(this.P.cover_m[0], this.P.cover_m[1]), uSteep: ssPair(sl[0], sl[1]),
                uSpi: ssPair(fo.spi[0], fo.spi[1]), uOver: ssPair(fo.over_deg[0], fo.over_deg[1]), uHasSc: up.Sc ? 1 : 0,
                uHasWr: up.wear_recent ? 1 : 0 });
            out.spi = spi;
            out.fresh = fresh;
            lap('fresh', t1);
        }
        water.destroy();
        cover.destroy();
        ownH.destroy();

        // ---- step 12: pins
        t1 = performance.now();
        for (const [k, v] of Object.entries(out)) {
            // a 'thick' map holds at most its encoding's t_max, clipped before the pins
            const s = MP.MAPS[k];
            if (s && s.encoding === 'thick' && s.t_max) {
                const c = this.run1('own', { a: v }, { uMode: 5, uHi: f32(s.t_max) }, [v.h, v.w]);
                v.destroy();
                out[k] = c;
            }
        }
        if (par) this.pin(i, out, fD);
        keep.pinned = { ...out };
        keep.fD = fD;
        lap('pins', t1);

        // ---- the level's one readback: every map encoded as the cache stores it, the routing surface
        t1 = performance.now();
        const arrays = await this.readLevel(i, out, keep);
        lap('read', t1);
        tm.total = (performance.now() - t0) / 1000;
        // the uploads: every one was copied where it is kept (the padded fields, the maps)
        for (const x of [...Object.values(up), ...Object.values(mup)]) x.destroy();
        this.keep.set(i, keep);
        this.release(i);
        this.times.push(Object.fromEntries(Object.entries(tm).map(([k, v]) => [k, typeof v === 'number' && !Number.isInteger(v) ? +v.toFixed(4) : v])));
        return arrays;
    }

    // release what no later level reads: a parent once its last child is done, and a level with no child at once
    // (its pinned maps were read back)
    release(i) {
        const lv = this.levels[i];
        const free = (j) => {
            const k = this.keep.get(j);
            if (!k) return;
            for (const v of Object.values(k)) {
                if (v && v.destroy && !v.destroyed) v.destroy();
                else if (v && typeof v === 'object' && !v.destroy) {
                    for (const w of Object.values(v)) if (w && w.destroy && !w.destroyed) w.destroy();
                }
            }
            this.keep.set(j, { href: k.href, crest_inherited: k.crest_inherited, fD: k.fD, released: true });
        };
        if (lv.parent !== null && lv.parent !== undefined && this.lastChild.get(lv.parent) === i) free(lv.parent);
        if (!this.lastChild.has(i)) free(i);
    }

    // every map of a level as the surface cache stores it (encode.wgsl), and the routing surface: one readback.
    // { name: npArray } in bake.py's order, '_ref_<name>' beside the F maps, '_fill' last
    async readLevel(i, out, keep) {
        const R = this.R, lv = this.levels[i], cell = Number(lv.cell);
        const refs = {};
        for (const [nm, refKey] of Object.entries(REF_OF)) {
            if (!out[nm]) continue;
            const med = await this.Pr.median(out[nm]);
            refs[nm] = Math.fround(pyRound(Math.fround(med * 10)) / 10);        // float(np.round(np.median(dz), 1))
            void refKey;
        }
        const plan = [];
        for (const [nm, v] of Object.entries(out)) {
            const form = storedForm(nm, cell);
            if (form[0] === 'f32') {
                plan.push({ nm, v, form, field: v, own: false });
                continue;
            }
            const per = form[0] === 'u8' ? 4 : 2;
            const words = R.field(v.h, Math.ceil(v.w / per), 1, null, 'u32');
            R.run(kernel(R, 'encode'), { src: v }, { outW: words },
                { uKind: form[0] === 'u8' ? form[1] : 4, uScale: form[0] === 'u8' ? f32(form[2]) : 1.0, uRef: f32(refs[nm] ?? 0.0) });
            plan.push({ nm, v, form, field: words, own: true });
        }
        plan.push({ nm: '_fill', v: keep.fill, form: ['f32'], field: keep.fill, own: false });
        const got = await R.readAll(plan.map((p) => p.field));
        const arrays = new Map();
        plan.forEach((p, k) => {
            const h = p.v.h, w = p.v.w;
            const words = got[k];
            let a;
            if (p.form[0] === 'f32') {
                a = { dtype: '<f4', shape: [h, w], data: words };
            } else if (p.form[0] === 'u8') {
                a = { dtype: '|u1', shape: [h, w], data: unpad(new Uint8Array(words.buffer, words.byteOffset, words.byteLength), h, w, 4 * Math.ceil(w / 4)) };
            } else {
                a = { dtype: '<f2', shape: [h, w], data: new Float16Array(unpad16(new Uint16Array(words.buffer, words.byteOffset, words.byteLength / 2), h, w, 2 * Math.ceil(w / 2)).buffer) };
            }
            arrays.set(p.nm, a);
            if (p.nm in refs) arrays.set(`_ref_${p.nm}`, { dtype: '<f8', shape: [], data: new Float64Array([refs[p.nm]]) });
            if (p.own) p.field.destroy();
        });
        return arrays;
    }

    // ---- pieces

    /** Step 7: the snowpack on the padded cell grid, metres: the fall from the altitude against the snowline and from
     * the northness, relaxed at the slip-off, melted by the climatological sun and below the line, and the larger of
     * that and a second pass that flows along the drainage. Keeps the passes for the child. A new r32f field. */
    async snowpack(i, hp, href, mup, par, keep) {
        const R = this.R, o = this.o, sn = o.snow, D = Gd.dummies(R);
        const cell = Number(this.levels[i].cell);
        const line = Number(o.snowline_m), band = Number(sn.band_m);
        const grad = this.run1('np_gradient', { hp }, { uDx: f32(cell), uDx2: f32(2 * f32(cell)) }, [hp.h, hp.w], 4);
        const k = kernel(R, 'snow');
        const nil = R.field(1, 1, 1);                     // outB where a mode writes one image
        const fall = R.field(hp.h, hp.w, 1), melt = R.field(hp.h, hp.w, 1);
        const uBase = { uMode: 0, uFlow: 0, uAlt: f32(href + this.base), uLine: ssPair(line - band, line + band),
            uLow: ssPair(line - band, line), uNorth: ssPair(1.0, 3.0),
            uSnow: [f32(sn.depth_m), f32(sn.aspect_m), f32(sn.melt_sun_m), f32(sn.melt_low_m)],
            uSun: [f32(this.sun[0]), f32(this.sun[1]), f32(this.sun[2]), f32(this.sun[2])],
            uRep: [0, 0, 0, 1] };
        R.run(k, { a: hp, b: D.f1, c: D.f1, g: grad }, { outA: fall, outB: melt }, uBase);
        grad.destroy();
        keep.snow_fall = fall;
        const start = (key) => {
            if (!par) return fall;
            const a = this.inherit(i, key), b = this.inherit(i, 'snow_fall');
            const s = R.field(hp.h, hp.w, 1);
            R.run(k, { a: fall, b: a, c: b, g: D.f1 }, { outA: s, outB: nil }, { ...uBase, uMode: 1 });
            a.destroy();
            b.destroy();
            return s;
        };
        const rest0 = start('snow_rest');
        const rest = this.relax(hp, rest0, tanDeg(sn.slip_deg), Math.trunc(sn.passes), Number(sn.rate), cell);
        if (rest0 !== fall) rest0.destroy();
        keep.snow_rest = rest;
        // pack = max(rest - melt, 0), and with the flowing pass max(that, max(flowed - melt, 0)): snow.wgsl mode 2
        let flowed = null;
        if (mup.flow) {
            const flowp = this.pad(i, mup.flow, 'flow_mask');
            keep.flow_mask = flowp;
            const rep = R.field(hp.h, hp.w, 1);
            R.run(k, { a: flowp, b: D.f1, c: D.f1, g: D.f1 }, { outA: rep, outB: nil },
                { ...uBase, uMode: 3, uRep: [f32(tanDeg(sn.slip_deg)), f32(tanDeg(sn.flow_deg)), ...ssPair(sn.flow[0], sn.flow[1])] });
            const flow0 = par && par.snow_flow ? start('snow_flow') : fall;
            flowed = this.relax(hp, flow0, rep, Math.trunc(sn.passes), Number(sn.rate), cell);
            if (flow0 !== fall) flow0.destroy();
            rep.destroy();
            keep.snow_flow = flowed;
        }
        const pack = R.field(hp.h, hp.w, 1);
        R.run(k, { a: rest, b: melt, c: flowed ?? D.f1, g: D.f1 }, { outA: pack, outB: nil },
            { ...uBase, uMode: 2, uFlow: flowed ? 1 : 0 });
        melt.destroy();
        nil.destroy();
        return pack;
    }

    /** The specific catchment (metres: the drainage area over the cell's width) on the padded cell grid, the larger
     * of the level's own and its parent's there. 1e9 where the level has no drainage area. Kept for the child. */
    catchment(i, up, keep) {
        const R = this.R, lv = this.levels[i], cell = Number(lv.cell);
        const N_ = lv.n + 2 * MARGIN;
        let a;
        if (!up.A) {
            a = Gd.fill(R, [N_, N_], f32(1.0e9));
        } else {
            const own = this.run1('own', { a: up.A }, { uMode: 3, uCell: f32(cell), uCell2: f32(cell * cell) }, [lv.n, lv.n]);
            a = this.pad(i, own, 'a_spec');
            own.destroy();
            const par = lv.parent !== null && lv.parent !== undefined ? this.keep.get(lv.parent) : null;
            if (par && par.a_spec) {
                const inh = this.inherit(i, 'a_spec');
                const mx = this.run1('own', { a, b: inh }, { uMode: 4 }, [N_, N_]);
                a.destroy();
                inh.destroy();
                a = mx;
            }
        }
        keep.a_spec = a;
        return a;
    }

    /** The geometry gates (step 3) on the padded cell grid, an rgba32f field: per crest scale s of GATE_SCALES_M, 1
     * where the level's own height is smooth at that scale and 0 where it already holds relief of a gully octave's
     * size: the RMS of crest's term at s over a Gaussian of 2 s, past relief.geo. Only the channels the octave table
     * reads are made; the rest are 1. */
    geoGates(i, keep, octs) {
        const R = this.R, lv = this.levels[i], D = Gd.dummies(R);
        const cell = Number(lv.cell), N_ = lv.n + 2 * MARGIN;
        const [lo, hi] = this.o.relief.geo.map(Number);
        const need = new Set();
        for (let k = 1; k < octs.length / 4; k += 2) {
            const b = octs[4 * k + 3];
            if (b > -0.5) need.add(Math.trunc(pyRound(b)));
        }
        const terms = keep.crest_terms;
        const par = lv.parent !== null && lv.parent !== undefined ? this.keep.get(lv.parent) : null;
        const made = {};
        const own = GATE_SCALES_M.map((s, c) => c).filter((c) => 2.0 * GATE_SCALES_M[c] / cell <= GATE_OWN_CELLS && terms &&
            terms[CREST_SCALES_M.indexOf(GATE_SCALES_M[c])]);
        if (own.length) {
            const t = [0, 1, 2, 3].map((c) => (own.includes(c) ? terms[CREST_SCALES_M.indexOf(GATE_SCALES_M[c])] : D.f1));
            const sq = R.field(N_, N_, 4);
            const on = [0, 1, 2, 3].map((c) => (own.includes(c) ? 1 : 0));
            R.run(kernel(R, 'gate'), { a: D.f1, t0: t[0], t1: t[1], t2: t[2], t3: t[3] }, { outF: sq }, { uMode: 0, uOn: on, uEdge: [0, 1] });
            const sig = [0, 1, 2, 3].map((c) => (own.includes(c) ? 2.0 * GATE_SCALES_M[c] / cell : 0.0));
            const b = this.blur4(sq, sig, false);
            sq.destroy();
            const rms = R.field(N_, N_, 4);
            R.run(kernel(R, 'gate'), { a: b, t0: D.f1, t1: D.f1, t2: D.f1, t3: D.f1 }, { outF: rms }, { uMode: 1, uOn: [0, 0, 0, 0], uEdge: [0, 1] });
            b.destroy();
            for (const c of own) made[c] = this.channel(rms, c, 0, 0, N_, N_);
            rms.destroy();
        }
        for (let c = 0; c < GATE_SCALES_M.length; c++) {
            if (!(c in made) && par && par.geo_rms && par.geo_rms[c]) {
                const [a, b, m] = this.win(i);
                made[c] = Gd.cropUpsample2(par.geo_rms[c], a, b, m, 'bilinear');
            }
        }
        keep.geo_rms = made;
        const src = [0, 1, 2, 3].map((c) => {
            if (!need.has(c)) return null;
            for (let q = c; q < GATE_SCALES_M.length; q++) if (q in made) return made[q];
            return null;
        });
        const out = R.field(N_, N_, 4);
        R.run(kernel(R, 'gate'), { a: D.f1, t0: src[0] ?? D.f1, t1: src[1] ?? D.f1, t2: src[2] ?? D.f1, t3: src[3] ?? D.f1 },
            { outF: out }, { uMode: 2, uOn: src.map((s) => (s ? 1 : 0)), uEdge: ssPair(lo, hi) });
        return out;
    }

    /** crest at fixed metre scales (step 5): t_s = tanh((h - G_s h) / (tau s)) for s in CREST_SCALES_M, the mean over
     * the scales of at least one cell. A level blurs the scales of 1 to 16 of its cells itself; a wider one comes from
     * its parent's pass (upsampled). Keeps the padded terms for the child. Returns the window's crest. */
    crestMetres(i, tH, par, keep) {
        const R = this.R, lv = this.levels[i], D = Gd.dummies(R);
        const cell = Number(lv.cell), n = lv.n, m = MARGIN, N_ = n + 2 * m;
        const S = CREST_SCALES_M;
        const terms = [null, null, null, null, null];
        const own = S.map((s, k) => k).filter((k) => S[k] >= cell * (1 - 1e-9) && S[k] / cell <= 16.0 + 1e-9);
        for (let g = 0; g < own.length; g += 4) {
            const ks = own.slice(g, g + 4);
            const sig = [...ks.map((k) => S[k] / cell), 0.0, 0.0, 0.0, 0.0].slice(0, 4);
            const b = this.blur4(tH, sig);
            const outs = [0, 1, 2, 3].map((c) => (c < ks.length ? R.field(N_, N_, 1) : R.field(1, 1, 1)));
            const den = [0, 1, 2, 3].map((c) => (c < ks.length ? f32(Number(this.o.crest_tau) * S[ks[c]]) : 0.0));
            R.run(kernel(R, 'crest_terms'), { hp: tH, b }, { o0: outs[0], o1: outs[1], o2: outs[2], o3: outs[3] }, { uDen: den });
            b.destroy();
            ks.forEach((k, c) => { terms[k] = outs[c]; });
            for (let c = ks.length; c < 4; c++) outs[c].destroy();
        }
        if (par && par.crest_terms) {
            S.forEach((s, k) => {
                if (!own.includes(k) && s >= cell * (1 - 1e-9) && par.crest_terms[k]) {
                    const [a, b, mm] = this.win(i);
                    terms[k] = Gd.cropUpsample2(par.crest_terms[k], a, b, mm, 'bilinear');
                }
            });
        }
        keep.crest_terms = terms;
        const use = S.map((s, k) => k).filter((k) => S[k] >= cell * (1 - 1e-9) && terms[k]);
        if (!use.length) return Gd.fill(R, [n, n], 0.0);
        const t = [0, 1, 2, 3, 4].map((c) => (c < use.length ? terms[use[c]] : D.f1));
        return this.run1('crest_mean', { t0: t[0], t1: t[1], t2: t[2], t3: t[3], t4: t[4] }, { uN: use.length, uM: m }, [n, n]);
    }

    /** A loose layer d0 (metres, a field) on the ground hp relaxed at `reposeTan` (a number, or a field of tangents):
     * solvers/detail.js relax with the ground cohesive (its threshold out of reach). Returns the layer, metres (a new
     * r32f field). */
    relax(hp, d0, reposeTan, passes, rate, cell) {
        const R = this.R, D = Gd.dummies(R);
        const b0 = R.field(hp.h, hp.w, 4), bed = R.field(hp.h, hp.w, 4);
        R.run(kernel(R, 'relax_io'), { a: hp, b: d0, c: D.f1 }, { outA: b0, outB: bed },
            { uMode: 0, uCell: f32(cell), uBigTan: HYD.BIG_TAN, uFloor: f32(-1.0e6) });
        const bed1 = bed;                                 // (x: the cohesive top; pipe_start and relax_io read x)
        let res;
        if (typeof reposeTan === 'number') {
            const { state, accum } = DT.relax(b0, bed1, HYD.BIG_TAN, reposeTan, passes, rate);
            accum.destroy();
            res = state;
        } else {
            // the per-cell repose: relax's start written by relax_io.wgsl, then the same pipes_thermal passes
            const st = R.field(hp.h, hp.w, 4), par = R.field(hp.h, hp.w, 4);
            R.run(kernel(R, 'relax_io'), { a: b0, b: bed1, c: reposeTan }, { outA: st, outB: par },
                { uMode: 2, uCell: f32(cell), uBigTan: HYD.BIG_TAN, uFloor: f32(-1.0e6) });
            const pin = R.field(hp.h, hp.w, 4);
            const k = R.kernel('pipes_thermal');
            const S = [st, R.field(hp.h, hp.w, 4)], TA = [R.field(hp.h, hp.w, 4), R.field(hp.h, hp.w, 4)];
            const u = { uRate: Number(rate), uBound: HYD.BOUND_OPEN };
            for (let k2 = 0; k2 < passes; k2++) {
                R.run(k, { st: S[0], base: b0, par, pin, tacc: TA[0] }, { outS: S[1], outT: TA[1] }, u);
                S.reverse();
                TA.reverse();
            }
            par.destroy();
            pin.destroy();
            S[1].destroy();
            TA[0].destroy();
            TA[1].destroy();
            res = S[0];
        }
        b0.destroy();
        bed1.destroy();
        const o4 = this.run1('relax_io', { a: d0, b: res }, { uMode: 1, uCell: f32(cell) }, [hp.h, hp.w], 4);
        res.destroy();
        const out = this.channel(o4, 0, 0, 0, hp.h, hp.w);
        o4.destroy();
        return out;
    }

    /** (lam_top, o_top): the gully spectrum's top octave, the same on every level: the first world octave under
     * relief.top_cells cells of the main level and relief.top_max_m. */
    topOctave() {
        const rp = this.o.relief;
        const top = Math.min(Number(rp.top_cells) * Number(this.levels[this.main].cell), Number(rp.top_max_m));
        let lam = GULLY_LAMBDA0_M, o = 0;
        while (lam > top * (1.0 + 1e-9)) {
            lam *= 0.5;
            o += 1;
        }
        return [lam, o];
    }

    /** The gully spectrum's octave table for a level (two texels per octave, float32 (1, 2 n, 4) as a flat
     * Float32Array), the gully filter's parameters and the spectrum's: { octs, gp, rp } (bake.py _gully_octaves). */
    gullyOctaves(i, texel) {
        const lv = this.levels[i];
        const cell = Number(lv.cell);
        const [sp] = this.stage('gully', i);
        const given = { ...sp, ...(this.o.gully ?? {}) };
        const gp = DT.paramsOf(DT.GULLY, given, 'gully');
        const rp = { ...this.o.relief };
        if ('steer' in given) rp.steer = Number(gp.steer);
        const kAmp = (gp.amp_m !== null && gp.amp_m !== undefined && gp.wavelength_m) ? Number(gp.amp_m) / Number(gp.wavelength_m) : Number(rp.k);
        const x0p = lv.x0 - MARGIN * cell, y0p = lv.y0 - MARGIN * cell;
        const rows = [];
        let [lam, o] = this.topOctave();
        while (lam >= 2.0 * texel * (1.0 - 1e-9) && rows.length < 12) {
            const [ox, oy] = N.latticeOffset(this.seed + 4242, o);
            const bx = Math.floor(x0p / lam), by = Math.floor(y0p / lam);
            if (Math.abs(bx + ox) >= 2 ** 24 || Math.abs(by + oy) >= 2 ** 24) {
                throw new ValueError('gully lattice base beyond float32 integers: world coordinates too large');
            }
            let ch = -1.0;
            if (lam >= 3.0 * cell * (1.0 - 1e-9)) {
                const s = Math.min(Math.max(lam / 4.0, GATE_SCALES_M[0]), GATE_SCALES_M[GATE_SCALES_M.length - 1]);
                let best = 0, bd = Infinity;
                for (let q = 0; q < GATE_SCALES_M.length; q++) {
                    const d = Math.abs(Math.log(GATE_SCALES_M[q] / s));
                    if (d < bd) { bd = d; best = q; }
                }
                ch = best;
            }
            rows.push([[bx + ox, by + oy, x0p / lam - bx, y0p / lam - by], [1.0 / lam, kAmp * lam, 1.0, ch]]);
            lam *= 0.5;
            o += 1;
        }
        if (!rows.length) rows.push([[0.0, 0.0, 0.0, 0.0], [1.0 / GULLY_LAMBDA0_M, 0.0, 0.0, -1.0]]);
        const octs = new Float32Array(8 * rows.length);
        rows.forEach(([a, b], k) => {
            octs.set(a, 8 * k);
            octs.set(b, 8 * k + 4);
        });
        return { octs, gp, rp };
    }

    /** { rockT (a field or null), rockRef, rockDeg, normalCap }: solvers/detail.js's breakup strength on the detail
     * grid as a level of that texel, so its relief D is the band of the rock noise and joints below what the level's
     * cells hold. null where the level's own breakup stage already put that band in the height. */
    rockRelief(i, hg, texel, ND) {
        const R = this.R, lv = this.levels[i];
        const cell = Number(lv.cell);
        const [sp, ran] = this.stage('breakup', i);
        const p = DT.paramsOf(DT.BREAKUP, Object.fromEntries(Object.entries(sp).filter(([k]) => k in DT.BREAKUP)), 'breakup');
        p.bedding = null;
        const rockDeg = p.rock_slope_deg.map(Number);
        const cap = Number(p.normal_cap);
        if (ran && Math.abs(texel - cell) < 1e-9 * cell) return { rockT: null, rockRef: 1.0, rockDeg, normalCap: cap };
        const v = { cell: texel, x0: lv.x0 - MARGIN * cell, y0: lv.y0 - MARGIN * cell, n: ND };
        const { terms, n: nt, bed, texels } = DT.breakupTerms(p, v, this.seed);
        let ref = 0.0;
        for (let t = 0; 3 * t < texels; t++) ref += Math.abs(terms[4 * (3 * t) + 3]);
        ref *= N.GRADIENT_STD;
        if (ref <= 1e-6) return { rockT: null, rockRef: 1.0, rockDeg, normalCap: cap };
        const u = DT.breakupUniforms(p, v, nt, bed);
        const outB = R.field(ND, ND, 4);
        const table = R.field(1, texels, 4, terms);
        R.run('breakup', { terms: table, st: hg }, { outB }, u);
        table.destroy();
        return { rockT: outB, rockRef: ref, rockDeg, normalCap: cap };
    }

    /** The level's filled, tilted surface on its padded grid (fill.wgsl to its fixed point): { W, passes }. Held: the
     * padded grid's outer ring, at the ground. The test of the fixed point every 256 passes counts the cells the
     * chunk changed (differ.wgsl), bake.py's np.array_equal of the two surfaces. */
    async fill(i, hp, waterp) {
        const R = this.R, lv = this.levels[i];
        const N_ = lv.n + 2 * MARGIN;
        const zt = R.field(N_, N_, 4);
        let a = R.field(N_, N_, 1);
        R.run(kernel(R, 'fill_io'), { hp, water: waterp }, { outZ: zt, outW: a }, { uBig: BIG });
        // top = max |z|: the larger of |min| and |max| of z
        const st = await this.Pr.stats(zt);
        const top = Math.max(Math.abs(st.min), Math.abs(st.max));
        const eps = Math.max(Number(this.o.fill_slope) * Number(lv.cell), 4.0 * spacing32(f32(Math.max(top, 1.0))));
        let b = R.field(N_, N_, 1);
        const prev = R.field(N_, N_, 1);
        const cnt = R.field(1, 1, 1, null, 'u32');
        const k = kernel(R, 'fill'), kd = kernel(R, 'differ');
        const u = { uEps: f32(eps), uCap: f32(Number(this.o.fill_cap_m)) };
        let done = 0, first = true;
        const chunk = 256;
        while (done < 24 * N_) {
            for (let q = 0; q < chunk; q++) {
                R.run(k, { wT: a, zT: zt }, { outW: b }, u);
                [a, b] = [b, a];
            }
            done += chunk;
            if (!first) {
                R.clear(cnt);
                R.run(kd, { a, b: prev }, { cnt }, {}, cover16(N_, N_));
                const [c] = await R.readAll([cnt]);
                if (c[0] === 0) break;
            }
            first = false;
            R.copy(a, prev);
        }
        for (const x of [b, prev, cnt, zt]) x.destroy();
        return { W: a, passes: done };
    }

    /** A hero level's drainage area on its padded grid, the parent's specific catchment pinned in on the margin:
     * { A (an r32f field), iters }. flow_weights and route_area are the level runner's kernels. */
    async route(i, W, par) {
        const HY = await import('../solvers/hydro.js');
        const R = this.R, lv = this.levels[i], D = Gd.dummies(R);
        const n = lv.n, m = MARGIN, cell = Number(lv.cell), N_ = n + 2 * m;
        const p = Number(this.o.flow_p);
        const [wa, wb, wm] = this.win(i);
        // tgt = (the parent's drainage area x 0.5 (crop_upsample2(par['A']) * F(0.5)), 1 on the margin)
        const upA = Gd.cropUpsample2(par.A, wa, wb, wm, 'bilinear');
        const half = Gd.arith(R, 'scale', upA, null, { amp: 0.5 });
        upA.destroy();
        const pinned = this.run1('own', {}, { uMode: 6, uM: m }, [N_, N_]);
        const tgt = R.pack({ a: half, p: pinned }, ['a', 'p', null, null]);
        pinned.destroy();
        const ws = R.field(N_, N_, 1);
        R.run('flow_weights', { st: W }, { outW: ws }, { uDx: cell, uP: p, uBound: HYD.BOUND_OPEN });
        const outP = R.field(N_, N_, 1);
        R.run(kernel(R, 'pin_inflow'), { st: W, wsumT: ws, tgtT: tgt }, { outP }, { uDx: cell, uP: p, uBound: HYD.BOUND_OPEN });
        ws.destroy();
        tgt.destroy();
        const c2 = f32(cell * cell);
        const A0 = this.run1('own', { a: half }, { uMode: 7, uHi: c2 }, [N_, N_]);      // np.maximum(tgt[..., 0], F(cell^2))
        half.destroy();
        const { A, iterations } = await HY.routeToConvergence(R, W, cell, { A0, A_in: outP, bound: HYD.BOUND_OPEN, p });
        outP.destroy();
        A0.destroy();
        const out = this.run1('own', { a: A }, { uMode: 7, uHi: c2 }, [N_, N_]);
        A.destroy();
        void D;
        return { A: out, iters: iterations };
    }

    /** flow, channels and wetness from a drainage area, with masks.py's formulas and the main tile's norms: masks.js
     * compute on the level (its own kernels), the area given. */
    async drainageMasks(A, up, mup, lv) {
        const m = await M.compute({ h: up.h, A, ...(mup.water ? { water: mup.water } : {}), ...(up.sand ? { sand: up.sand } : {}) },
            { cell: lv.cell, x0: lv.x0, y0: lv.y0, names: ['flow', 'channels', 'wetness'], norms: this.norms, params: this.P,
                strict: false });
        const out = {};
        for (const k of ['flow', 'channels', 'wetness']) if (m.has(k)) out[k] = m[k];
        return out;
    }

    /** Blend a level's new maps to its parent's across the border band: masks.pinBand, the cell-grid maps over 16
     * cells, the detail maps over the same ground on their own grid. A map the parent took from the masks (its flow,
     * wetness, channels on the main level) is read from there. */
    pin(i, out, fD) {
        const R = this.R, lv = this.levels[i];
        const pk = this.keep.get(lv.parent);
        const plv = this.levels[lv.parent];
        const pmk = this.t.masks.level(lv.parent);
        const det = Object.keys(out).filter((k) => MP.MAPS[k] && MP.MAPS[k].grid === 'detail' && out[k].h === lv.n * fD && k !== 'grain');
        const cellmaps = Object.keys(out).filter((k) => !det.includes(k) && k !== 'area');
        const child = new M.Masks(lv.cell, lv.x0, lv.y0, [lv.n, lv.n]);
        const parent = new M.Masks(plv.cell, plv.x0, plv.y0, [plv.n, plv.n]);
        const made = [];
        for (const k of cellmaps) {
            let pv = pk.pinned?.[k] ?? null;
            if (!pv && k in pmk) {
                pv = R.field(plv.n, plv.n, 1, pmk[k]);
                made.push(pv);
            }
            if (pv && pv.h === plv.n && pv.w === plv.n) {
                child[k] = out[k];
                parent[k] = pv;
            }
        }
        M.pinBand(child, parent, BAND, []);
        const pf = pk.fD;
        const childD = new M.Masks(lv.cell / fD, lv.x0, lv.y0, [lv.n * fD, lv.n * fD]);
        const parentD = new M.Masks(plv.cell / pf, plv.x0, plv.y0, [plv.n * pf, plv.n * pf]);
        for (const k of det) {
            const pv = pk.pinned?.[k] ?? null;
            if (pv) {
                childD[k] = out[k];
                parentD[k] = pv;
            }
        }
        M.pinBand(childD, parentD, BAND * fD, []);
        for (const x of made) x.destroy();
    }
}

// a uniform's zero of its GLSL type
function zeroOf(t) {
    return { float: 0, int: 0, vec2: [0, 0], vec3: [0, 0, 0], vec4: [0, 0, 0, 0], ivec2: [0, 0], ivec3: [0, 0, 0], ivec4: [0, 0, 0, 0] }[t] ?? 0;
}

// np.spacing(np.float32(x)): the float32 step at |x|
function spacing32(x) {
    const b = new Float32Array([Math.abs(x)]);
    const u = new Uint32Array(b.buffer);
    u[0] += 1;
    return b[0] - Math.abs(Math.fround(x));
}

function roundTo(x, d) {
    return pyRound(x * 10 ** d) / 10 ** d;
}

// rows of packed bytes (stride bytes each) without their padding: the row copies, not a loop over texels
function unpad(bytes, h, w, stride) {
    if (stride === w) return bytes.slice(0, h * w);
    const out = new Uint8Array(h * w);
    for (let j = 0; j < h; j++) out.set(bytes.subarray(j * stride, j * stride + w), j * w);
    return out;
}

function unpad16(halves, h, w, stride) {
    if (stride === w) return halves.slice(0, h * w);
    const out = new Uint16Array(h * w);
    for (let j = 0; j < h; j++) out.set(halves.subarray(j * stride, j * stride + w), j * w);
    return out;
}

/** Bake every level, coarsest first: { levels: [Map name -> npArray, as the cache stores it], info }. The maps are
 * the new ones (and flow, wetness and channels on re-routed hero levels), pinned to their parents across the border
 * band; 'strata_dz' and 'src_dz' are the F family's metres (zs - h) less their level's reference ('_ref_<name>');
 * 'area' is a re-routed hero level's drainage area (m^2); '_fill' the padded routing surface. */
export async function bakeLevels(terrain, opts, opts2 = {}) {
    const G = await import('../core/gpu.js');
    const R = opts2.runner ?? await G.init(opts2.renderer ? { renderer: opts2.renderer } : {});
    const log = opts2.log === undefined ? console.log : opts2.log;
    const B = await Baker.make(terrain, opts, R, log);
    const out = [];
    const t0 = performance.now();
    for (let i = 0; i < B.levels.length; i++) {
        out.push(await B.level(i));
        const tm = B.times[B.times.length - 1];
        if (log) {
            log(`[surface] level ${i} ${B.levels[i].role} ${B.levels[i].n} cells @ ${Number(B.levels[i].cell).toPrecision(4)} m: ` +
                `${tm.total.toFixed(2)} s (` + Object.entries(tm).filter(([k]) => k !== 'total').map(([k, v]) => `${k} ${v}`).join(', ') + ')');
        }
    }
    const info = { seconds: +((performance.now() - t0) / 1000).toFixed(3), levels: B.times, backend: 'gpu',
        detail: B.levels.map((lv) => detailFactor(lv, opts)),
        norms: { flow_lo: B.norms.flow_lo, flow_hi: B.norms.flow_hi, twi_lo: B.norms.twi_lo, twi_hi: B.norms.twi_hi, spi: B.spiNorm },
        href: B.levels.map((_, i) => B.keep.get(i)?.href ?? null), snow: B.snowOn, wind: B.wind !== null,
        relief_octaves: B.levels.map((_, i) => B.octaveM.get(i) ?? []), maps: opts.maps ?? 'all' };
    for (const k of B.keep.values()) {
        for (const v of Object.values(k)) {
            if (v && v.destroy && !v.destroyed) v.destroy();
            else if (v && typeof v === 'object' && !v.destroy) for (const w of Object.values(v)) if (w && w.destroy && !w.destroyed) w.destroy();
        }
    }
    B.keep.clear();
    return { levels: out, info };
}

export {
    resolveOptions as resolve_options, resolvePalette as resolve_palette, terrainConstants as terrain_constants,
    maskParams as mask_params, bakeKey as bake_key, codeHash as code_hash, bakeLevels as bake_levels,
    detailFactor as detail_factor,
};
