// Port of blender/eidoblend/terrain/build/surfacing.py at de1cf8c.
//
// The terrain's material (SURFACING_DESIGN.md 2.4-2.6, 3.3-3.7; PORT_PLAN.md 3.5): a TSL NodeMaterial built from a
// palette (build/palettes.js) and the terrain's baked surface data (surface/index.js SurfaceData), and grey clay
// without a palette. Every map is read per texel from the data's 2D-array textures through the two-slot level reader;
// the shading normal is the field normal from D plus the relief below the cell, the scans' normal maps in its tangent
// frame and the strata's bed relief; planar reads are hex-tiled, steep faces read eight fixed sector frames; every
// noise term fades with the pixel's footprint; past D0 the ground hands off to the baked far colour C. The maths is
// surfacing.py's node graph, transcribed node for node (Blender's Math, Map Range, Mix, Vector Math, Image Texture,
// Noise, Voronoi and White Noise nodes on TSL, in the Blender frame: x east, y north, z up), written against build/
// ops.js's TSL backend where it shares code with the surface bake (the mask language, surface/mask_expr.js, and
// Blender's shader noise, surface/noise.js).
//
//     import * as S from './build/surfacing.js';
//     const sd = await bakeSurface(t, { palette: 'auto' });              // surface/index.js
//     const mat = await S.surfaceMaterial('auto', { data: sd, recipe: t.recipe });   // the per-texel material
//     await S.applySurface(t, 'auto', { data: sd, cameras: [camera] });  // the same on t.mesh: slot 0 near, slot 1
//                                                                       // far for the rings beyond 1.5 D0 of every camera
//     S.clayMaterial(THREE)                                              // palette null: grey clay, albedo 0.18
//     const m = await S.terrainMap(sd, ['flow', 'cavity'])               // eido_terrain_map: any map's node by name
//     S.setFarDistance(mat, 2500)                                        // D0 moved in place (a uniform)
//     await S.packSet('Rock019')                                         // a CC0 scan set packed (albedo_height,
//                                                                       // normal_rough_ao, stats.json), cached
//
// What the material does per pixel, with baked data (surfacing.py's module doc, its second part):
//   - the reader: per pixel the finest window holding it; even levels in one slot, odd levels in the other, each slot
//     changing level only where its weight is exactly 0 (a dead band of three footprints inside every window edge),
//     so no 2 x 2 quad on a window edge reads a coarse mip; slope, aspect, northness, eastness and insolation come
//     from the field normal (D), height from the object z;
//   - layers: coverage from the palette's weight expressions over the maps, composited in order, the overlay of the
//     macro data and each scan's soft height, then the height blend (blend_depth); each layer's scan read hex-tiled
//     (planar) or in two sector slots of fixed frames tilted 65 degrees (box layers on faces over 47 degrees), its
//     albedo rescaled from the scan's mean to the palette's colour, ramp or strata band (debris at its source's bed,
//     src_strata), provenance, patina, patches, streaks, ledges, canopy;
//   - specular anti-aliasing (option specular_aa, default on): each scan's roughness takes back the normal variance
//     its mips have averaged away at the pixel's footprint (scanNormalVariance's table);
//   - past D0 (a main-level texel spanning 2.5 pixels, or the option far_m) the ground fades over D0..1.5 D0 to C
//     and its roughness, never inside the hero windows; rings beyond 1.5 D0 of every camera given to applySurface
//     take the far material (a cost saving only, the same weights for the specular and the roughness).
//
// The packed scans (packSet: cacheRoot() is surface/far_colour.js setsDir(): $EIDO_SURFACE_SETS, else this
// checkout's eidoverse/assets/cache/terrain_surface_sets/<set>_v<PACK_VERSION>/, where the far colour reads them):
//   albedo_height.png    RGB the scan's albedo (sRGB), A its height normalised to mean 0.5 std 0.15
//   normal_rough_ao.png  R, G the OpenGL normal's x, y (z rebuilt), B roughness, A ambient occlusion
//   stats.json           the scan's mean linear albedo, mean roughness and AO, its height mean/std, and its normal
//                        map's slope variance by mip level (normal_var: scanNormalVariance)
//
// Where this differs from surfacing.py, and why (each a forced deviation; the visible result is Blender's):
//   - TSL nodes for Blender's shader nodes, in Blender's frame: object (x, y, z) = three.js (X, -Z, Y) (plan 2.2; the
//     terrain keeps an identity transform, as in Blender); the final normal goes back to three.js world axes and on
//     to view space, where a NodeMaterial's normalNode lives. Each node's GLSL is transcribed: Map Range (smoothstep
//     and linear, clamped; 0 where its From range is empty), Mix (the factor clamped, Blender's default), Math
//     (DIVIDE and SQRT safe, ROUND as floor(x + 0.5), FLOORED_MODULO, ARCCOSINE clamped), Vector Math (NORMALIZE
//     safe), the Image Texture node's Linear (mipmapped, anisotropic 16x) and Cubic (its B-spline of four bilinear
//     taps at mip 0) reads, the Noise Texture (surface/noise.js), the Voronoi F1 distance and colour (noise.js's
//     PCG hashes; the distance added here, as the canopy reads it), the White Noise Texture's colour (Jenkins'
//     lookup3 of the float bits, noise.js's hashes), the Hue/Saturation/Value node (its RGB-HSV round trip) and
//     the Bump node (its surface gradient from the height's screen-space derivatives: EEVEE evaluates the height graph
//     again at positions offset within the pixel, by the node's Filter Width, per pixel; here dFdx and dFdy of the
//     height, the difference across the 2 x 2 pixel quad: the same derivative to first order, but one value a quad
//     where the height has detail at the pixel's own scale, so the bump crawls more as the camera moves).
//   - Selects (Blender's comparisons, safe divisions and Map Range's guards) are a node of this file (selectNode):
//     WGSL select() of two evaluated values, as Blender's GLSL computes them, where three's select writes an if/else
//     block around each (356 of them in the canyon's material made D3D12's shader compiler spend 237 s on one
//     pipeline) and its uniformFlow form returns an unassigned variable to a select's second reader (three r184).
//   - Node groups become TSL subgraphs built once per terrain and lattice (the reader, the hex grids, a layer's
//     reads), as Blender builds its groups once; their numbers are the same per pixel.
//   - Textures: WebGPU's default device allows 16 sampled textures and 16 samplers a stage, EEVEE 30 images. So the
//     scans travel as two 2D-array textures (albedo_height and normal_rough_ao, one layer per palette layer, Ekigar's
//     materials/texture_arrays.js pattern) where Blender reads two images a layer, and the M families are one
//     DataArrayTexture (layer = family x levels + level) where Blender reads one atlas a family; D, E, F, C and P are
//     surface/layers.js's arrays as they are. A scan smaller than the largest is resampled up to it (bilinear, on the
//     GPU); its own size still sets its anti-aliasing (stats.size). A material that would pass MAX_TEXTURES is
//     refused, naming what to drop, as Blender refuses one past MAX_SAMPLERS.
//   - The far hand-off distance D0 is a uniform (setFarDistance changes it without a rebuild), where Blender keeps it
//     in a Map Range node's sockets.
//   - The specular: Blender's Specular IOR Level s scales the Principled BSDF's F0 (0.04 at 0.5) through its IOR;
//     here the physical NodeMaterial's IOR is set to give that F0 (1 + sqrt(F0)) / (1 - sqrt(F0)), F0 = 0.08 s.
//   - Debug views (options.debug) are unlit MeshBasicNodeMaterials (Blender's Emission shader).
//   - The material without baked data (surfacing.py's attribute path: the masks read as the mesh's eido_<mask>
//     attributes) is not here: this edition's ring mesh carries no mask attributes, so surfaceMaterial and
//     farMaterial take the terrain's SurfaceData (data:) and refuse without it; palette null still gives the clay.
//   - Per-element work runs on the GPU (the edition's rule): the strata image's texels from the beds' table (made
//     in JavaScript doubles with numpy's draws, core/np_random.js), the packed scans' channels, their height
//     statistics and their normal variance pyramid (core/gpu.js kernels written in this file), canopyMean's 76,800
//     points; Blender does those in numpy.

import { createHash } from 'node:crypto';
import * as P from './palettes.js';
import * as MP from '../surface/maps.js';
import * as ops from './ops.js';
import { Compiler } from '../surface/mask_expr.js';
import { noise as noiseLib } from '../surface/noise.js';
import { setsDir } from '../surface/far_colour.js';
import { defaultRng } from '../core/np_random.js';

export const PACK_VERSION = 1;
// WebGPU's default maxSampledTexturesPerShaderStage is 16; a lit scene binds a shadow map and its environment too
export const MAX_TEXTURES = 13;
export const SECTOR_DIP_DEG = 65.0;                // the sector frames' fixed up-dip axis (SURFACING_DESIGN.md 3.4)
export const STEEP_DEG = [37.0, 47.0];             // box layers: planar below, sector frames above
export const HEX_POWER = 7.0;                      // hex tiling's sharpening of the barycentric weights
export const HEX_CONTRAST = 0.6;                   // ... and how much each read's own height weighs
export const HEX_LADDER = 2.5;                     // default hex lattices are this x 2^n metres (hexClass)
export const STEEP_HEX = 2.0;                      // the sector reads' lattice, in hexClass(the largest box tile)
export const STEEP_HEX_SHARE = 0.5;                // ... for box layers whose tile is at least this share of it
export const HEX_PATCH = 0.29;                     // a hexagon's width in hex_m
export const BLEND_PATCH_M = 1.0;                  // hexagons wider than this lend a layer edge less of their swing
export const CUBIC_FAMILIES = ['D'];               // the data read bicubic where a texel is magnified (Data.fam)
export const CUBIC_PX = [0.3, 0.6];                // ... from a pixel spanning this share of a texel to this
export const DEAD_FOOTPRINTS = 3.0;                // the reader's dead band inside a window edge, in footprints
export const FADE_CELLS = 8.0;                     // a level fades in over this many of its own cells
export const FAR_TEXEL_PX = 2.5;                   // D0: where a main-level texel spans this many pixels
export const FAR_FADE_MAIN_CELLS = 64.0;           // the far colour fades in over this many main cells past the heroes
export const FAR_GRAIN = 0.25;                     // how much of the base layer's scan luminance the far colour keeps
export const DETAIL_STRENGTH = 0.5;                // the relief below the cell, by default (options.detail_strength)
export const NORMAL_VAR_VERSION = 2;               // the scans' normal variance record in their stats.json
export const AA_GRAZING = 1.0 / 16.0;              // specular anti-aliasing's footprint: vd pix / sqrt(max(|N.V|, this))
// the 5-95 % half-range of (n - 0.5) of the mask language's noise() and fbm(): what a faded term's smoothstep widens by
export const NOISE_HALF = Object.freeze({ noise: 0.358, fbm: 0.344 });
// ... and of the raw Noise Texture's Fac (patches, streaks, damp, ledges), by detail 0..5
export const RAW_HALF = Object.freeze([0.2, 0.163, 0.143, 0.134, 0.130, 0.128]);
export const HEX_VERSION = 4;
export const CLAY_ALBEDO = 0.18;                   // the reference rig's grey clay (photographic mid grey, matte)
export const STRATA_PX_PER_M = 2.0;                // the strata image's resolution: 0.5 m per pixel
// options.debug = 'layers': one flat colour per layer (bottom first)
export const DEBUG_COLOURS = Object.freeze([[0.55, 0.38, 0.25], [0.35, 0.55, 0.2], [0.85, 0.75, 0.45], [0.6, 0.35, 0.6],
    [0.2, 0.55, 0.85], [0.95, 0.95, 0.95]]);
const LUMA = [0.2126, 0.7152, 0.0722];
const SHADER_NAMES = ['slope', 'aspect', 'northness', 'eastness', 'insolation', 'height', 'slope_20m'];

/** eidoverse/assets/cache/terrain_surface_sets/ of this checkout ($EIDO_SURFACE_SETS when set): where the packed scan
 * sets live, beside the terrain cache, not inside it (its prune would take them; surfacing.py cache_root), and where
 * surface/far_colour.js reads their stats. */
export function cacheRoot() {
    return setsDir();
}


// ------------------------------------------------------------------------- the node algebra (TSL) ---
// Blender's node helpers (terrain/_nodes.py Graph, surfacing.py _mul, _sat, _clamp01, _one_minus) on TSL. A value is a
// JavaScript number (a constant Blender's Python folds, or a socket's default value) or a TSL node; constants fold as
// Python folds them, so a constant expression stays a number (the weight of a layer that is always 1, a fade without a
// footprint), which later steps test for, as surfacing.py tests isinstance(x, float).

let T = null;          // three/tsl
let OPS = null;        // build/ops.js TSL backend over it (mask_expr.js, noise.js), its select SEL's
let NZ = null;         // surface/noise.js on OPS
let SEL = null;        // select(c, a, b): a where c, else b (selectNode)

// The graph's selects as WGSL select() of two evaluated values, as Blender's GLSL computes both sides of its Mix and
// Compare nodes, held in a variable where the graph reads one more than once (a TempNode, as three's math nodes).
// three's own select (ConditionalNode) compiles each into an if/else block: the material's 356 made D3D12's shader
// compiler take 237 s over one pipeline; and its uniformFlow form hands an unassigned variable (zero) to every read
// after the first (three r184's ConditionalNode.generate keeps the property it never assigns).
function selectNode(TempNode) {
    class EidoSelectNode extends TempNode {
        static get type() {
            return 'EidoSelectNode';
        }

        constructor(condNode, ifNode, elseNode) {
            super();
            this.condNode = condNode;
            this.ifNode = ifNode;
            this.elseNode = elseNode;
        }

        generateNodeType(builder) {
            const a = this.ifNode.getNodeType(builder), b = this.elseNode.getNodeType(builder);
            return builder.getTypeLength(b) > builder.getTypeLength(a) ? b : a;
        }

        generate(builder, output) {
            const type = this.getNodeType(builder);
            const c = this.condNode.build(builder, 'bool');
            const a = this.ifNode.build(builder, type);
            const b = this.elseNode.build(builder, type);
            return builder.format(builder.getTernary(c, a, b), type, output);
        }
    }
    const node = (v) => (typeof v === 'number' ? T.float(v) : T.nodeObject(v));
    return (c, a, b) => T.nodeObject(new EidoSelectNode(T.nodeObject(c), node(a), node(b)));
}

/** The TSL module (and the ops backend and noise on it), loaded once: opts.TSL, else import('three/tsl'); opts.THREE
 * (three/webgpu, else imported) lends the select node its TempNode. */
export async function tslModule(opts = {}) {
    if (!T || (opts.TSL && opts.TSL !== T)) {
        T = opts.TSL ?? await import('three/tsl');
        const W = opts.THREE?.TempNode ? opts.THREE : await import('three/webgpu');
        SEL = selectNode(W.TempNode);
        OPS = ops.TSL({ ...T, select: SEL });
        NZ = noiseLib(OPS);
    }
    return T;
}

const isNum = (v) => typeof v === 'number';
const F = (v) => (isNum(v) ? T.float(v) : v);
const V3 = (v) => (Array.isArray(v) ? T.vec3(v[0], v[1], v[2]) : v);

function add(a, b) {
    if (isNum(a) && isNum(b)) return a + b;
    if (isNum(a) && a === 0) return b;
    if (isNum(b) && b === 0) return a;
    return F(a).add(F(b));
}
function sub(a, b) {
    if (isNum(a) && isNum(b)) return a - b;
    if (isNum(b) && b === 0) return a;
    return F(a).sub(F(b));
}
// surfacing._mul: numbers multiply, 1 and 0 fold
function mul(a, b) {
    if (isNum(a) && isNum(b)) return a * b;
    if (isNum(a) && a === 1) return b;
    if (isNum(b) && b === 1) return a;
    if ((isNum(a) && a === 0) || (isNum(b) && b === 0)) return 0.0;
    return F(a).mul(F(b));
}
// Math DIVIDE: safe_divide (0 where b is 0)
function div(a, b) {
    if (isNum(a) && isNum(b)) return b !== 0 ? a / b : 0.0;
    if (isNum(b)) return b !== 0 ? F(a).div(b) : 0.0;
    return SEL(F(b).notEqual(0.0), F(a).div(F(b)), T.float(0.0));
}
// Math MULTIPLY_ADD: a b + c
function madd(a, b, c) {
    return add(mul(a, b), c);
}
function mmin(a, b) { return isNum(a) && isNum(b) ? Math.min(a, b) : T.min(F(a), F(b)); }
function mmax(a, b) { return isNum(a) && isNum(b) ? Math.max(a, b) : T.max(F(a), F(b)); }
function mabs(a) { return isNum(a) ? Math.abs(a) : T.abs(a); }
// Math SQRT: safe_sqrt (0 for a negative argument)
function msqrt(a) { return isNum(a) ? (a > 0 ? Math.sqrt(a) : 0.0) : T.sqrt(T.max(a, 0.0)); }
function mfloor(a) { return isNum(a) ? Math.floor(a) : T.floor(a); }
function mfract(a) { return isNum(a) ? a - Math.floor(a) : T.fract(a); }
// Math ROUND: floor(a + 0.5)
function mround(a) { return isNum(a) ? Math.floor(a + 0.5) : T.floor(F(a).add(0.5)); }
// Math FLOORED_MODULO: a - floor(a / b) b (0 where b is 0)
function mfmod(a, b) {
    if (isNum(a) && isNum(b)) return b !== 0 ? a - Math.floor(a / b) * b : 0.0;
    return F(a).sub(T.floor(F(a).div(b)).mul(b));
}
function mcos(a) { return isNum(a) ? Math.cos(a) : T.cos(a); }
function msin(a) { return isNum(a) ? Math.sin(a) : T.sin(a); }
// Math ARCTAN2(a, b) = atan(a, b)
function matan2(a, b) { return T.atan(F(a), F(b)); }
// Math ARCCOSINE: safe_acos (clamped to -1..1)
function macos(a) { return T.acos(T.clamp(F(a), -1.0, 1.0)); }
function mdeg(a) { return isNum(a) ? a * (180 / Math.PI) : F(a).mul(180 / Math.PI); }
// Math LOGARITHM(a, base): log2(a) / log2(base) for positive arguments, else 0
function mlog2(a) { return SEL(F(a).greaterThan(0.0), T.log2(T.max(F(a), 1e-38)), T.float(0.0)); }
// Math POWER: compatible_pow for a >= 0 (the callers clamp a at 0 first)
function mpow(a, b) {
    if (isNum(a) && isNum(b)) return a >= 0 ? (b === 0 ? 1.0 : a ** b) : 0.0;
    return SEL(F(b).equal(0.0), T.float(1.0), T.pow(T.max(F(a), 0.0), F(b)));
}
function mlt(a, b) { return isNum(a) && isNum(b) ? (a < b ? 1.0 : 0.0) : SEL(F(a).lessThan(F(b)), T.float(1.0), T.float(0.0)); }
function mgt(a, b) { return isNum(a) && isNum(b) ? (a > b ? 1.0 : 0.0) : SEL(F(a).greaterThan(F(b)), T.float(1.0), T.float(0.0)); }
function sat(a) { return isNum(a) ? Math.max(0.0, Math.min(1.0, a)) : T.clamp(a, 0.0, 1.0); }
const clamp01 = sat;
const oneMinus = (a) => sub(1.0, a);
// palettes._smooth on numbers
function pySmooth(e0, e1, x) {
    if (e1 === e0) return x >= e0 ? 1.0 : 0.0;
    const t = Math.min(Math.max((x - e0) / (e1 - e0), 0.0), 1.0);
    return t * t * (3.0 - 2.0 * t);
}
// Graph.smoothstep: Map Range SMOOTHSTEP, clamped; 0 where From Min equals From Max
function smooth(e0, e1, x) {
    if (isNum(e0) && isNum(e1)) {
        if (e0 === e1) return 0.0;
        if (isNum(x)) return pySmoothNode(e0, e1, x);
        const t = T.clamp(F(x).sub(e0).mul(1.0 / (e1 - e0)), 0.0, 1.0);
        return t.mul(t).mul(T.float(3.0).sub(t.mul(2.0)));
    }
    const d = sub(e1, e0);
    const t = T.clamp(F(sub(x, e0)).div(F(d)), 0.0, 1.0);
    return SEL(F(d).notEqual(0.0), t.mul(t).mul(T.float(3.0).sub(t.mul(2.0))), T.float(0.0));
}
function pySmoothNode(e0, e1, x) {
    const t = Math.min(Math.max((x - e0) / (e1 - e0), 0.0), 1.0);
    return t * t * (3.0 - 2.0 * t);
}
// Graph.map_range: Map Range LINEAR, clamped to the To range; 0 where the From range is empty
function mapRange(x, a, b, c, d) {
    if (a === b) return 0.0;
    const r = madd(sub(x, a), (d - c) / (b - a), c);
    return isNum(r) ? Math.min(Math.max(r, Math.min(c, d)), Math.max(c, d)) : T.clamp(r, Math.min(c, d), Math.max(c, d));
}
// Mix FLOAT (MIX, factor clamped): a + (b - a) clamp(fac)
function mixf(fac, a, b) {
    if (isNum(fac)) {
        const f = Math.max(0.0, Math.min(1.0, fac));
        if (f === 0) return a;
        if (f === 1) return b;
        if (isNum(a) && isNum(b)) return a + (b - a) * f;
    }
    return T.mix(F(a), F(b), sat(F(fac)));
}
// Mix VECTOR / RGBA (MIX, the factor clamped; an RGBA mix keeps the first alpha: colours are vec3 here)
function mixv(fac, a, b) {
    if (isNum(fac)) {
        const f = Math.max(0.0, Math.min(1.0, fac));
        if (f === 0) return a;
        if (f === 1) return b;
    }
    return T.mix(V3(a), V3(b), isNum(fac) ? Math.max(0.0, Math.min(1.0, fac)) : sat(fac));
}
const v3 = (x, y, z) => T.vec3(F(x), F(y), F(z));
const vadd = (a, b) => V3(a).add(V3(b));
const vsub = (a, b) => V3(a).sub(V3(b));
const vmulv = (a, b) => V3(a).mul(V3(b));
const vscale = (a, s) => (isNum(s) && s === 1 ? V3(a) : V3(a).mul(F(s)));
const vdot = (a, b) => T.dot(V3(a), V3(b));
const vcross = (a, b) => T.cross(V3(a), V3(b));
// Vector Math NORMALIZE: safe (a zero vector stays 0)
function vnorm(a) {
    const v = V3(a);
    const l = T.length(v);
    return SEL(l.greaterThan(0.0), v.div(T.max(l, 1e-30)), T.vec3(0.0, 0.0, 0.0));
}
const vmin = (a, b) => T.min(V3(a), V3(b));
const vmax = (a, b) => T.max(V3(a), V3(b));
const sep = (v) => [V3(v).x, V3(v).y, V3(v).z];


// ------------------------------------------------------------------------------------------- the strata ---

/** The numpy half of surfacing.strata_image, as the beds' table (JavaScript doubles, numpy's draws: core/np_random.js):
 * { W, rows, zLo, zHi, rep, beds: per row [{ k0, k1, rgb, a, part, hb, ledge }] } and, with relief, the ledges. The
 * image's texels are filled from it on the GPU (strataImage). A bed's pixels are [k0, k1) of its row (zc(k) =
 * z_lo + ((k + 0.5) / W) (z_hi - z_lo), numpy's arithmetic); rgb its clipped colour, a its roughness multiplier, part
 * its bedding plane's factor on its first pixel (1 without parting), hb its relief, ledge the first pixel of its
 * ledge (-1: none). Deterministic per column. */
export function strataArray(column, opts = {}) {
    const { pxPerM = STRATA_PX_PER_M, seed = 0, rows = 1, parting = 0.0, padM = 0.0, looks = false, repeat = null,
        relief = false } = opts;
    let layers = P.columnLayers(column, looks);
    const rep = repeat === null ? P.columnRepeats(column) : Boolean(repeat);
    let zLo = layers[0][1], zHi = layers[layers.length - 1][2];
    if (!rep && padM > 0) {
        zLo -= padM;
        zHi += padM;
        const first = layers[0], last = layers[layers.length - 1];
        if (layers.length === 1) {
            layers = [[first[0], zLo, zHi, ...first.slice(3)]];
        } else {
            layers = [[first[0], zLo, ...first.slice(2)], ...layers.slice(1, -1), [last[0], last[1], zHi, ...last.slice(3)]];
        }
    }
    const W = Math.trunc(Math.min(16384, Math.max(64, Math.ceil((zHi - zLo) * pxPerM))));
    const R = Math.max(1, Math.trunc(rows));
    const zc = (k) => zLo + ((k + 0.5) / W) * (zHi - zLo);
    // the first pixel k with zc(k) >= z (W when none)
    const firstAt = (z) => {
        let lo = 0, hi = W;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (zc(mid) >= z) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    };
    let ordSum = 0;
    for (const L of layers) for (const c of String(L[0])) ordSum += c.codePointAt(0);
    const seed0 = seed + (ordSum % 9973);
    const out = [];
    for (let r = 0; r < R; r++) {
        const rng = defaultRng(seed0 + 7919 * r);
        const hrng = defaultRng(seed0 + 104729 + 7919 * r);   // the beds' hardness: its own draws
        const beds = [];
        for (const [, b, t, col, rough, bed, jit] of layers) {
            let z = b;
            while (z < t) {
                const th = Math.max(0.3, Number(rng.exponential(bed)));
                const top = Math.min(z + th, t);
                const k0 = firstAt(z), k1 = firstAt(top);
                const v = Math.exp(jit * Number(rng.standard_normal()));
                const hue = Array.from(rng.standard_normal(3)).map((g) => 1.0 + 0.3 * jit * g);
                let base;
                if (Array.isArray(col) && Array.isArray(col[0])) {         // a bed colour drawn by weight
                    const w = col.map((c) => c[1]);
                    const ws = w.reduce((s, x) => s + x, 0);
                    base = col[Math.trunc(Number(rng.choice(col.length, { p: w.map((x) => x / ws) })))][0];
                } else {
                    base = col;
                }
                const rgb = [0, 1, 2].map((c) => Math.min(Math.max(base[c] * v * hue[c], 0.0), 0.95));
                const a = rough * (1.0 + 0.4 * jit * Number(rng.standard_normal()));
                let part = 1.0;
                if (parting > 0.0 && k1 > k0) part = Math.max(0.0, 1.0 - parting * Number(rng.uniform(0.5, 1.5)));
                let hb = 0.0;
                if (relief) {
                    // hard or soft: a massive formation (roughness multiplier under 1) leans hard, and a bed thicker
                    // than its formation's mean stands out more
                    const lean = rough < 0.975 ? 0.62 : 0.42;
                    const hard = Number(hrng.random()) < lean + 0.25 * Math.tanh(th / Math.max(bed, 0.3) - 1.0);
                    hb = hard ? Number(hrng.uniform(0.7, 1.0)) : Number(hrng.uniform(0.0, 0.35));
                }
                if (k1 > k0) beds.push({ k0, k1, rgb, a, part, hb, ledge: -1 });
                z = top;
            }
        }
        if (relief) {
            // a ledge: the top metre of a bed that stands out over the bed above it, from the image's own runs of one
            // relief value (np.diff of the row: equal neighbours make one run)
            const k = pyRoundHalfEven(1.0 * pxPerM);
            for (let q = 0; q < beds.length - 1; q++) {
                const cur = beds[q], nxt = beds[q + 1];
                if (cur.hb === nxt.hb) continue;
                if (cur.hb - nxt.hb > 0.3) {
                    const e = cur.k1 - 1;
                    const from = Math.max(e - k + 1, 0);
                    // the pixels [from, e] may reach back into earlier beds of this run (np's slice runs on pixels)
                    for (let p = q; p >= 0 && beds[p].k1 - 1 >= from; p--) {
                        beds[p].ledge = beds[p].ledge >= 0 ? Math.min(beds[p].ledge, Math.max(from, beds[p].k0))
                            : Math.max(from, beds[p].k0);
                    }
                }
            }
        }
        out.push(beds);
    }
    return { W, rows: R, zLo, zHi, rep, beds: out, relief: Boolean(relief) };
}

function pyRoundHalfEven(x) {
    const r = Math.round(x);
    return (Math.abs(x % 1) === 0.5 && r % 2 !== 0) ? r - 1 : r;
}

// the strata image's texels from the beds' table: per pixel its bed by a binary search of the row's starts
const STRATA_FILL = `//! sampler beds
//! image outC r32ui
//! image outR r32ui
//! uniform int uBeds
//! uniform int uW
//! uniform int uRelief
//! local 64 1
fn bed_at(row: i32, k: i32) -> i32 {
  // the last bed of the row whose first pixel is at or before k
  var lo: i32 = 0;
  var hi: i32 = u.uBeds - 1;
  loop {
    if (lo >= hi) { break; }
    let mid = (lo + hi + 1) / 2;
    if (i32(beds_at(vec2<i32>(0, row * u.uBeds + mid)).x) <= k) { lo = mid; } else { hi = mid - 1; }
  }
  return lo;
}
fn kmain(p: vec2<i32>) {
  let k = p.x / 2;
  let hw = p.x - 2 * k;
  if (k >= u.uW) { return; }
  let row = p.y;
  let b = bed_at(row, k);
  let a0 = beds_at(vec2<i32>(0, row * u.uBeds + b));
  let a1 = beds_at(vec2<i32>(1, row * u.uBeds + b));
  let a2 = beds_at(vec2<i32>(2, row * u.uBeds + b));
  // a0: k0, k1, part, a; a1: r, g, b, hb; a2: ledge
  var rgb = a1.xyz;
  if (k == i32(a0.x)) { rgb = rgb * a0.z; }
  if (hw == 0) {
    outC_store(p, pack2x16float(vec2<f32>(rgb.x, rgb.y)));
  } else {
    outC_store(p, pack2x16float(vec2<f32>(rgb.z, a0.w)));
  }
  if (u.uRelief == 1) {
    let ledge = i32(a2.x);
    var g = 0.0;
    if (ledge >= 0 && k >= ledge) { g = 1.0; }
    if (hw == 0) {
      outR_store(p, pack2x16float(vec2<f32>(a1.w, g)));
    } else {
      outR_store(p, pack2x16float(vec2<f32>(0.0, 1.0)));
    }
  }
}
`;

/** The strata image of a column (surfacing.strata_image): { texture (a THREE.DataTexture, RGBA half float: linear RGB
 * the bed colour, A its roughness multiplier; rows x W, REPEAT along u for a repeating column, else clamped),
 * relief (the relief texture: R how far each bed stands out, G its ledges; or null), zLo, zHi, rows, rep, W }. Its
 * texels are made on the GPU from strataArray's table and read back once as halves (Blender uploads a float image at
 * half precision too: use_half_precision, SURFACING_DESIGN.md 1.3). */
export async function strataImage(column, opts = {}) {
    const { THREE, R } = opts;
    const st = strataArray(column, opts);
    const nb = Math.max(...st.beds.map((b) => b.length));
    const tab = new Float32Array(st.rows * nb * 3 * 4);
    for (let r = 0; r < st.rows; r++) {
        for (let q = 0; q < nb; q++) {
            // rows past a row's last bed repeat it (the search never lands there: their k0 is past W)
            const bd = st.beds[r][Math.min(q, st.beds[r].length - 1)];
            const o = ((r * nb + q) * 3) * 4;
            const k0 = q < st.beds[r].length ? bd.k0 : st.W + 1;
            tab.set([k0, bd.k1, bd.part, bd.a], o);
            tab.set([bd.rgb[0], bd.rgb[1], bd.rgb[2], bd.hb], o + 4);
            tab.set([bd.ledge, 0, 0, 0], o + 8);
        }
    }
    const beds = R.field(st.rows * nb, 3, 4, tab);
    const outC = R.field(st.rows, 2 * st.W, 1, null, 'u32');
    const outR = R.field(st.rows, 2 * st.W, 1, null, 'u32');
    R.run(R.kernel('surfacing_strata_fill', STRATA_FILL), { beds }, { outC, outR },
        { uBeds: nb, uW: st.W, uRelief: st.relief ? 1 : 0 });
    const [c, rr] = await R.readAll(st.relief ? [outC, outR] : [outC]).then((a) => [a[0], a[1] ?? null]);
    beds.destroy();
    outC.destroy();
    outR.destroy();
    const make = (words) => {
        const t = new THREE.DataTexture(new Uint16Array(words.buffer, words.byteOffset, st.rows * st.W * 4), st.W, st.rows,
            THREE.RGBAFormat, THREE.HalfFloatType);
        t.colorSpace = THREE.NoColorSpace;
        t.magFilter = THREE.LinearFilter;
        t.minFilter = THREE.LinearMipmapLinearFilter;
        t.generateMipmaps = true;
        t.wrapS = st.rep ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
        t.wrapT = THREE.ClampToEdgeWrapping;
        t.anisotropy = 16;
        t.flipY = false;
        t.needsUpdate = true;
        return t;
    };
    return { texture: make(c), relief: rr ? make(rr) : null, zLo: st.zLo, zHi: st.zHi, rows: st.rows, rep: st.rep, W: st.W,
        table: st };
}


// ---------------------------------------------------------------------------- expressions compiled to nodes ---

/** surfacing._Compiler: mask expressions (palettes.js parse trees) -> TSL values, or numbers where they fold (the
 * terrain constants fold in), sharing equal sub-expressions. The noise terms are mask_expr.js's (Blender's noise
 * through surface/noise.js on the ops TSL backend, faded and their detail dropped by the footprint `fp`, its
 * 'uniform' form with a per-pixel footprint); what is the material's own is here: the folding, Blender's Map Range
 * smoothstep, and the widened smoothstep around faded terms (lostSpread, SURFACING_DESIGN.md 3.2 rule 4).
 * flat: noise(), fbm() and cells() read their mean 0.5 (the bump's cheap coverage); data: the baked maps (Data),
 * read before anything else (a map the data lacks reads 0: the port's mesh carries no mask attributes, plan C4);
 * attrs: another compiler's reads, shared. */
export class MaterialCompiler extends Compiler {
    constructor({ pos, constants = null, noise3 = false, flat = false, data = null, fp = null, attrs = null }) {
        const p = sep(pos);
        super({ ops: OPS, read: null, pos: p, constants, noise3, texelM: (fp && !flat) ? 'uniform' : null, flat, foot: fp });
        this.read = (n) => this.attr(n);
        this.data = data;
        this.fp = flat ? null : fp;
        this.attrs = attrs ?? new Map();
        this.memo = new Map();
        this._fades = new Map();
        this._invFp = null;
    }

    /** smoothstep(1, 4, scale / footprint): 1 where a term of that scale spans 4 pixels or more, 0 under one (1.0
     * without a footprint). As Blender writes it, the edges divided by the scale: one node per scale. */
    fade(scaleM) {
        if (!this.fp) return 1.0;
        const key = Math.max(Number(scaleM), 1e-6);
        if (!this._fades.has(key)) {
            if (this._invFp === null) this._invFp = div(1.0, this.fp);
            this._fades.set(key, smooth(1.0 / key, 4.0 / key, this._invFp));
        }
        return this._fades.get(key);
    }

    attr(name) {
        if (!this.attrs.has(name)) {
            this.attrs.set(name, this.data && this.data.has(name) ? this.data.value(name) : 0.0);
        }
        return this.attrs.get(name);
    }

    expr(src) {
        return this._c(Array.isArray(src) ? src : P.parse(src));
    }

    /** The half-spread the faded noise terms of an expression tree lost (0 or a node): over its additive noise and
     * fbm terms, |coefficient| x NOISE_HALF x (1 - fade); products of two non-constant terms and the nonlinear
     * functions count 0 (their inner smoothsteps widen themselves). */
    lostSpread(t) {
        if (!this.fp) return 0.0;
        const k = t[0];
        if (k === 'num' || k === 'const' || k === 'mask') return 0.0;
        if (k === 'neg') return this.lostSpread(t[1]);
        const plus = (a, b) => (isNum(a) && a === 0 ? b : isNum(b) && b === 0 ? a : add(a, b));
        const scale = (c, s) => (isNum(s) ? Math.abs(c) * s : Math.abs(c) === 1 ? s : mul(s, Math.abs(c)));
        if (k === 'op') {
            const o = t[1];
            if (o === '+' || o === '-') return plus(this.lostSpread(t[2]), this.lostSpread(t[3]));
            if (o === '*') {
                const a = this._c(t[2]), b = this._c(t[3]);
                if (isNum(a)) return scale(a, this.lostSpread(t[3]));
                if (isNum(b)) return scale(b, this.lostSpread(t[2]));
                return 0.0;
            }
            if (o === '/') {
                const b = this._c(t[3]);
                if (isNum(b) && Math.abs(b) > 1e-12) return scale(1.0 / b, this.lostSpread(t[2]));
                return 0.0;
            }
            return 0.0;
        }
        if (k === 'call' && (t[1] === 'noise' || t[1] === 'fbm')) {
            const f = this.fade(Number(t[2][0][1]));
            const hs = NOISE_HALF[t[1]];
            return isNum(f) ? 0.0 : madd(f, -hs, hs);
        }
        return 0.0;
    }

    _c(t) {
        const key = P.treeKey(t);
        if (!this.memo.has(key)) this.memo.set(key, this._compile(t));
        return this.memo.get(key);
    }

    _bin(op, a, b) {
        if (isNum(a) && isNum(b)) {
            if (op === '+') return a + b;
            if (op === '-') return a - b;
            if (op === '*') return a * b;
            return a / (Math.abs(b) > 1e-12 ? b : 1e-12);
        }
        if (op === '+') return add(a, b);
        if (op === '-') return F(a).sub(F(b));
        if (op === '*') return mul(a, b);
        return div(a, b);
    }

    _compile(t) {
        const k = t[0];
        if (k === 'num') return Number(t[1]);
        if (k === 'const') return Number(t[1] in this.consts ? this.consts[t[1]] : P.CONSTANTS[t[1]]);
        if (k === 'mask') {
            this.names.add(t[1]);
            return this.attr(t[1]);
        }
        if (k === 'neg') {
            const a = this._c(t[1]);
            return isNum(a) ? -a : mul(a, -1.0);
        }
        if (k === 'op') return this._bin(t[1], this._c(t[2]), this._c(t[3]));
        const [, f, args] = t;
        if (f === 'noise' || f === 'fbm' || f === 'cells') {
            if (this.flat) return 0.5;
            const seed = args.length > 1 ? Math.trunc(args[1][1]) : 0;
            const scale = Number(args[0][1]);
            if (f === 'cells') return this._cells(scale, seed, args.length > 2 ? Number(args[2][1]) : 0.0);
            return this._noise(f, scale, seed);
        }
        const v = args.map((a) => this._c(a));
        if (f === 'smoothstep') {
            if (v.every(isNum)) return pySmooth(v[0], v[1], v[2]);
            let [e0, e1] = v;
            if (isNum(e0) && isNum(e1)) {
                const sp = this.lostSpread(args[2]);
                if (!isNum(sp)) {
                    const sgn = e1 >= e0 ? 1.0 : -1.0;
                    [e0, e1] = [madd(sp, -sgn, e0), madd(sp, sgn, e1)];
                }
            }
            return smooth(e0, e1, v[2]);
        }
        if (f === 'min' || f === 'max') {
            if (v.every(isNum)) return f === 'min' ? Math.min(...v) : Math.max(...v);
            let out = v[0];
            for (const e of v.slice(1)) out = f === 'min' ? T.min(F(out), F(e)) : T.max(F(out), F(e));
            return out;
        }
        if (f === 'clamp') {
            if (v.every(isNum)) return Math.min(Math.max(v[0], v[1]), v[2]);
            return T.max(T.min(F(v[0]), F(v[2])), F(v[1]));
        }
        if (f === 'abs') return mabs(v[0]);
        if (f === 'pow') return mpow(mmax(v[0], 0.0), v[1]);
        if (f === 'mix') return add(v[0], mul(sub(v[1], v[0]), v[2]));
        throw new P.ExprError(f);
    }
}

// surfacing._noise3: a 3D Noise Texture's Fac with features about scale_m across, decorrelated by an offset per seed
function noise3(pos, scaleM, detail = 2.0, roughness = 0.5, seed = 0.0) {
    const s = Number(scaleM);
    const off = [37.7 * seed + 11.3, -51.9 * seed + 7.1, 23.3 * seed - 3.7];
    const [x, y, z] = sep(pos);
    return NZ.noiseNode3(x.add(off[0] * s), y.add(off[1] * s), z.add(off[2] * s), T.float(1.0 / Math.max(s, 1e-6)),
        F(detail), F(roughness));
}

// Graph.noise: the Noise Texture in 4D, (Vector, W) x Scale
function noise4(pos, scale, detail = 3.0, roughness = 0.55, w = 0.0) {
    const [x, y, z] = sep(pos);
    return NZ.noiseNode4(x, y, z, F(w), F(scale), F(detail), F(roughness));
}

// the Voronoi texture node's F1 (3D, Euclidean, detail 0): vec4(distance, the cell's colour). noise.js's
// voronoiF1Colour3 with its distance kept (the canopy reads both outputs)
function voronoiF1(pos, scale, randomness) {
    const fn = voronoiF1Fn();
    const [x, y, z] = sep(pos);
    return fn(x, y, z, F(scale), F(randomness));
}
let VORONOI = null;
function voronoiF1Fn() {
    if (VORONOI && VORONOI.T === T) return VORONOI.fn;
    const fn = voronoiF1Of(OPS, NZ);
    VORONOI = { T, fn };
    return fn;
}
// the Voronoi F1 (3D) on any ops backend: TSL for the material, WGSL for canopyMean's kernel
function voronoiF1Of(o, N) {
    const INV31 = 1.0 / 2147483648.0;
    const fn = o.fn('eido_voronoi_f1_dist3', [['cx', 'float'], ['cy', 'float'], ['cz', 'float'], ['scale', 'float'],
        ['randomness', 'float']], 'vec4', (o_, cx, cy, cz, scale, randomness) => {
        const co = [o.mul(cx, scale), o.mul(cy, scale), o.mul(cz, scale)];
        const fl = co.map((v) => o.floor(v));
        const cell = fl.map((v) => o.ftoi(v));
        const loc = co.map((v, q) => o.sub(v, fl[q]));
        let best = o.f(3.4e38);
        let tt = [o.i(0), o.i(0), o.i(0)];
        const r = o.clamp(randomness, 0.0, 1.0);
        for (let k = -1; k <= 1; k++) {
            for (let j = -1; j <= 1; j++) {
                for (let i = -1; i <= 1; i++) {
                    const off = [i, j, k];
                    const h = N.pcg3d(o.iadd(cell[0], i), o.iadd(cell[1], j), o.iadd(cell[2], k)).map((v) => o.mul(o.itof(v), INV31));
                    const d2 = [0, 1, 2].map((q) => {
                        const pt = o.add(o.f(off[q]), o.mul(h[q], r));
                        const dd = o.sub(pt, loc[q]);
                        return o.mul(dd, dd);
                    });
                    const d = o.sqrt(o.add(o.add(d2[0], d2[1]), d2[2]));
                    const take = o.lt(d, best);
                    best = o.select(take, d, best);
                    tt = tt.map((v, q) => o.select(take, o.i(off[q]), v));
                }
            }
        }
        const c = N.pcg3d(o.iadd(cell[0], tt[0]), o.iadd(cell[1], tt[1]), o.iadd(cell[2], tt[2])).map((v) => o.mul(o.itof(v), INV31));
        return o.v4(best, c[0], c[1], c[2]);
    });
    return fn;
}

// the White Noise Texture (3D)'s Color: hash_vec3_to_vec3 of the vector, Jenkins' lookup3 of the float bits
// (hash_vec3_to_float, and hash_vec4_to_float of (k, 1) and (k, 2)), each over 0xFFFFFFFF
function whiteNoise3(x, y, z) {
    const b = [x, y, z].map((c) => T.floatBitsToUint(F(c)));
    const one = T.floatBitsToUint(T.float(1.0)), two = T.floatBitsToUint(T.float(2.0));
    const h0 = NZ.hash3(b[0], b[1], b[2]);
    const h1 = NZ.hash4(b[0], b[1], b[2], one);
    const h2 = NZ.hash4(b[0], b[1], b[2], two);
    const u2f = (h) => T.float(h).div(4294967295.0);
    return T.vec3(u2f(h0), u2f(h1), u2f(h2));
}


// ------------------------------------------------------------------------------------------- the strata ---

// surfacing._strata_zs: the stratigraphic height, from the baked `strata` (source 'attribute') or the object z with a
// dip (source 'position'), plus z_offset_m, fault throws, world-noise warps and the runnels' smear. base: a height
// that stands for the strata map or the object z (a debris' source height, src_strata), through the same offsets.
function strataZs(comp, st, coords, base = null) {
    const [x, y, z0] = sep(coords);
    let zs;
    const src = st.source ?? 'attribute';
    if (base !== null && src === 'attribute') {
        zs = base;
    } else if (src === 'attribute') {
        zs = comp.attr('strata');
    } else {
        const z = base !== null ? base : z0;
        const dip = Math.tan((Number(st.dip_deg ?? 0.0) * Math.PI) / 180);
        const az = (Number(st.dip_azimuth_deg ?? st.azimuth_deg ?? 0.0) * Math.PI) / 180;
        zs = z;
        if (dip) zs = sub(zs, mul(add(mul(x, Math.cos(az)), mul(y, Math.sin(az))), dip));
    }
    const off = Number(st.z_offset_m ?? 0.0);
    if (off) zs = add(zs, off);
    for (const f of st.faults ?? []) {
        const s = (Number(f.strike_deg ?? 0.0) * Math.PI) / 180;
        let nx = Math.cos(s), ny = -Math.sin(s);
        const want = { west: [-1, 0], east: [1, 0], north: [0, 1], south: [0, -1] }[f.down ?? 'west'];
        if (nx * want[0] + ny * want[1] < 0) { nx = -nx; ny = -ny; }
        const dist = add(mul(sub(x, Number(f.x ?? 0.0)), nx), mul(sub(y, Number(f.y ?? 0.0)), ny));
        const w = Math.max(Number(f.width_m ?? 50.0), 1e-3);
        zs = add(zs, mul(smooth(-0.5 * w, 0.5 * w, dist), Number(f.throw_m ?? 0.0)));
    }
    (st.warp ?? []).forEach(([scale, amp], k) => {
        const n = noise4(coords, 1.0 / Number(scale), 2.0, 0.5, 41.3 + 3.7 * k);
        zs = add(zs, mul(sub(n, 0.5), 2.0 * Number(amp)));
    });
    const sm = st.smear;
    if (sm && sm.length) {
        // runnels: a noise width_m across and ten times as tall drags the bands up to `metres` down the walls
        const width = Number(sm[0]), amp = Number(sm[1]);
        const sv = vmulv(coords, [1.0 / width, 1.0 / width, 1.0 / (10.0 * width)]);
        const n = noise4(sv, 1.0, 3.0, 0.55, 61.7);
        zs = add(zs, mul(sub(n, 0.5), 2.5 * amp));
    }
    return zs;
}

/** surfacing._Strata: the rock column's reads. band(offset) -> [colour, roughness] at the stratigraphic height plus
 * offset_m (each distinct offset one more read of the one strata image); bandAt(base) the same at another height (a
 * debris' source bed); relief() -> [relief 0..1, ledge 0..1] of the beds there; reliefSlope() their slope along zs. */
export class Strata {
    constructor(comp, st, coords, img) {
        this.comp = comp;
        this.st = st;
        this.coords = coords;
        this.img = img;
        this.reliefM = Number(st.relief_m ?? 0.0) || 0.0;
        this.zLo = img.zLo;
        this.zHi = img.zHi;
        this.zs = strataZs(comp, st, coords);
        const rows = Math.trunc(st.rows ?? 1);
        this.v = 0.5;
        if (rows > 1) {
            const n = noise4(coords, 1.0 / Number(st.facies_m ?? 700.0), 2.0, 0.5, 17.3);
            const t = sat(madd(sub(n, 0.5), 2.4, 0.5));
            this.v = madd(t, (rows - 1.0) / rows, 0.5 / rows);
        }
        this.reads = new Map();
        this._uv = new Map();
        this._at = new Map();
        this._relief = null;
        this._slope = null;
    }

    _read(tex, u) {
        const s = T.texture(tex, T.vec2(F(u), F(this.v)));
        return [s.rgb, s.a];
    }

    uv(offsetM = 0.0) {
        const key = Math.round(Number(offsetM) * 1000) / 1000;
        if (!this._uv.has(key)) {
            const span = this.zHi - this.zLo;
            const zs = key ? add(this.zs, key) : this.zs;
            this._uv.set(key, madd(zs, 1.0 / span, -this.zLo / span));
        }
        return this._uv.get(key);
    }

    band(offsetM = 0.0) {
        const key = Math.round(Number(offsetM) * 1000) / 1000;
        if (!this.reads.has(key)) this.reads.set(key, this._read(this.img.texture, this.uv(key)));
        return this.reads.get(key);
    }

    bandAt(base) {
        if (!this._at.has(base)) {
            const zs = strataZs(this.comp, this.st, this.coords, base);
            const span = this.zHi - this.zLo;
            this._at.set(base, this._read(this.img.texture, madd(zs, 1.0 / span, -this.zLo / span)));
        }
        return this._at.get(base);
    }

    relief() {
        if (!this.img.relief) return null;
        if (this._relief === null) {
            const [c] = this._read(this.img.relief, this.uv(0.0));
            this._relief = [c.x, c.y];
        }
        return this._relief;
    }

    /** [d relief / d zs per metre, the direction zs rises in]: the relief differentiated along the stratigraphic
     * height, half a pixel of the relief image either side (two more reads, mipmapped, so beds finer than a pixel
     * fade to no slope), and the unit-rise direction: +z, tilted by the dip of a 'position' source. */
    reliefSlope() {
        if (!this.img.relief) return null;
        if (this._slope === null) {
            const span = this.zHi - this.zLo;
            const d = 0.5 * span / this.img.W;
            const r = [d, -d].map((off) => this._read(this.img.relief, madd(this.zs, 1.0 / span, (off - this.zLo) / span))[0].x);
            let up = [0.0, 0.0, 1.0];
            if ((this.st.source ?? 'attribute') !== 'attribute') {
                const dip = Math.tan((Number(this.st.dip_deg ?? 0.0) * Math.PI) / 180);
                const az = (Number(this.st.dip_azimuth_deg ?? this.st.azimuth_deg ?? 0.0) * Math.PI) / 180;
                up = [-dip * Math.cos(az), -dip * Math.sin(az), 1.0];
            }
            this._slope = [mul(sub(r[0], r[1]), 1.0 / (2.0 * d)), up];
        }
        return this._slope;
    }
}


// --------------------------------------------------------------------------------- the two-slot reader ---

/** The two-slot level reader of a terrain's surface data (surfacing.reader_group; SURFACING_DESIGN.md 2.4), as TSL
 * nodes at the Blender-frame position `pos` (a vec3 node) with the footprint `fp` (metres a pixel spans there).
 * Returns { sel: [null, sel_1 ..], level, levelEven, levelOdd, wOdd, heroOutside, detail: [uv even, uv odd],
 * cell: [uv even, uv odd] }: the finest window holding the pixel (L counts the windows k >= 1 holding it), what each
 * slot reads (the even slot the finest even level holding it, else 0; the odd slot the finest odd one, else 1),
 * the odd slot's weight (L fades in over FADE_CELLS of its own cells behind a dead band of DEAD_FOOTPRINTS
 * footprints inside its edge, capped by the room before the next finer window), metres outside the outermost hero
 * window, and each slot's coordinates on the detail layout (D, E) and the cell layout (M, F, C, P). Every per-level
 * constant is a telescoping sum over the windows: q = q_first + sum_k sel_k (q_k - q_{k-step}). */
export function readerNodes(sd, pos, fp) {
    const rc = sd.readerConstants();
    const lv = [...sd.levels];
    const K = lv.length;
    const [x, y] = sep(pos);
    const cx = lv.map((v) => Number(v.x0) + 0.5 * Number(v.side));
    const cy = lv.map((v) => Number(v.y0) + 0.5 * Number(v.side));
    const cheb = (ax, ay) => T.max(T.abs(F(x).sub(F(ax))), T.abs(F(y).sub(F(ay))));
    const sel = [null];
    for (let k = 1; k < K; k++) sel.push(mlt(cheb(cx[k], cy[k]), 0.5 * Number(lv[k].side)));
    const tele = (vals, step = 1, first = 0) => {
        vals = vals.map(Number);
        let acc = vals[first];
        for (let k = first + step; k < K; k += step) {
            const d = vals[k] - vals[k - step];
            if (d !== 0) acc = madd(sel[k], d, acc);
        }
        return acc;
    };
    const range = (n) => Array.from({ length: n }, (_, i) => i);
    const out = { K, sel, level: tele(range(K)) };
    if (K > 1) {
        // L's centre, half side (level 0's: its whole side, more than any of its pixels lies inside it), cell, parity
        // and the cap on its dead band (the room before the next finer window, less the fade)
        const Rh = [Number(lv[0].side), ...lv.slice(1).map((v) => 0.5 * Number(v.side))];
        const cap = [];
        for (let k = 0; k < K; k++) {
            if (k + 1 < K) {
                const a = lv[k], b = lv[k + 1];
                const m = Math.min(b.x0 - a.x0, b.y0 - a.y0, a.x0 + a.side - b.x0 - b.side, a.y0 + a.side - b.y0 - b.side);
                cap.push(Math.max(Number(m) - FADE_CELLS * Number(a.cell), 0.0));
            } else {
                cap.push(1.0e6);
            }
        }
        const dIn = sub(tele(Rh), cheb(tele(cx), tele(cy)));
        const z = mmin(mul(fp, DEAD_FOOTPRINTS), tele(cap));
        const om = smooth(z, madd(tele(lv.map((v) => v.cell)), FADE_CELLS, z), dIn);
        const par = tele(range(K).map((k) => k % 2));
        out.wOdd = madd(par, madd(om, 2.0, -1.0), sub(1.0, om));
    } else {
        out.wOdd = 0.0;
    }
    out.levelEven = tele(range(K), 2, 0);
    out.levelOdd = K > 1 ? tele(range(K), 2, 1) : 0.0;
    for (const lay of ['detail', 'cell']) {
        const Tc = rc[lay];
        const au = Tc.map((t) => t.du / t.side), bu = Tc.map((t) => t.u0 - t.du * t.x0 / t.side);
        const av = Tc.map((t) => t.dv / t.side), bv = Tc.map((t) => t.v0 - t.dv * t.y0 / t.side);
        out[lay] = [0, 1].map((first) => {
            const f0 = K > first ? first : 0;
            return T.vec2(F(madd(x, tele(au, 2, f0), tele(bu, 2, f0))), F(madd(y, tele(av, 2, f0), tele(bv, 2, f0))));
        });
    }
    const roles = lv.map((v) => String(v.role ?? ''));
    const h = roles.indexOf('hero');
    out.heroOutside = h >= 0 ? sub(cheb(cx[h], cy[h]), 0.5 * Number(lv[h].side)) : 1.0e6;
    out.slotLayer = [out.levelEven, out.levelOdd];
    return out;
}


// --------------------------------------------------------------------------------------- the data's textures ---

/** The data textures a material reads, made once per SurfaceData and packing: { fam: { D, E, F, C, P: THREE
 * texture }, M: one DataArrayTexture of every M family (layer = family x levels + level) or null, mFamilies,
 * K (levels), sizes: { detail, cell } (a layer's side in texels) }. The families
 * are surface/layers.js's textures as they are (sd.textures()), but for the M families, joined into one array: a
 * WebGPU stage samples at most 16 textures by default (module doc). names: pack these maps into the M families
 * first. (The ramp image is the material's palette's: lutImage.) */
export async function dataTextures(sd, opts = {}) {
    const THREE = opts.THREE ?? await import('three/webgpu');
    const R = opts.R ?? await (await import('../core/gpu.js')).init();
    if (opts.names) sd.pack(opts.names);
    const sig = JSON.stringify(sd.packing()) + '|' + String(sd.key) + '|' + (sd._colour ? 'c' : '-');
    if (sd._eidoMaterialTextures && sd._eidoMaterialTextures.sig === sig && sd._textures) return sd._eidoMaterialTextures;
    const tex = await sd.textures(null, { THREE, R });
    const K = sd.levels.length;
    const fam = {};
    const mFamilies = [];
    for (const [f, t] of Object.entries(tex)) {
        if (f.startsWith('M')) {
            mFamilies.push(f);
            continue;
        }
        t.anisotropy = 16;                                // SURFACING_DESIGN.md 2.4 step 5: 16x anisotropic filtering
        fam[f] = t;
    }
    mFamilies.sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
    let M = null;
    if (mFamilies.length) {
        const first = tex[mFamilies[0]];
        const S = first.image.width;
        const per = S * S * 4 * K;
        const data = new Uint8Array(per * mFamilies.length);
        mFamilies.forEach((f, q) => {
            const d = tex[f].image.data;
            data.set(d.subarray(0, per), q * per);
            tex[f].dispose();
        });
        M = new THREE.DataArrayTexture(data, S, S, K * mFamilies.length);
        M.format = THREE.RGBAFormat;
        M.type = THREE.UnsignedByteType;
        M.colorSpace = THREE.NoColorSpace;
        M.magFilter = THREE.LinearFilter;
        M.minFilter = THREE.LinearMipmapLinearFilter;
        M.generateMipmaps = true;
        M.wrapS = M.wrapT = THREE.ClampToEdgeWrapping;
        M.flipY = false;
        M.anisotropy = 16;
        M.name = `eido_surf_${String(sd.key).slice(0, 8)}_M`;
        M.userData = { eido_families: mFamilies, eido_maps: mFamilies.map((f) => sd.familyMaps(f)) };
        M.needsUpdate = true;
    }
    const lays = sd.layouts;
    const out = { sig, fam, M, mFamilies, K, sizes: { detail: lays.detail.size, cell: lays.cell.size } };
    sd._eidoMaterialTextures = out;
    return out;
}

// EEVEE's Cubic read (node_tex_image_cubic): a cubic B-spline of four bilinear taps at mip 0
function cubicRead(tex, uv, layer, size) {
    const co = uv.mul(size);
    const tc = T.floor(co.sub(0.5)).add(0.5);
    const a = co.sub(tc), a2 = a.mul(a), a3 = a2.mul(a);
    const w0 = a3.negate().add(a2.mul(3.0)).sub(a.mul(3.0)).add(1.0).div(6.0);
    const w1 = a3.mul(3.0).sub(a2.mul(6.0)).add(4.0).div(6.0);
    const w2 = a3.mul(-3.0).add(a2.mul(3.0)).add(a.mul(3.0)).add(1.0).div(6.0);
    const w3 = a3.div(6.0);
    const s0 = w0.add(w1), s1 = w2.add(w3);
    const f0 = w1.div(s0), f1 = w3.div(s1);
    const c0 = tc.sub(1.0).add(f0).div(size), c1 = tc.add(1.0).add(f1).div(size);
    const tap = (u, v) => {
        const s = T.texture(tex, T.vec2(u, v)).level(0);
        return layer === null ? s : s.depth(layer);
    };
    return tap(c0.x, c0.y).mul(s0.x.mul(s0.y)).add(tap(c1.x, c0.y).mul(s1.x.mul(s0.y)))
        .add(tap(c0.x, c1.y).mul(s0.x.mul(s1.y))).add(tap(c1.x, c1.y).mul(s1.x.mul(s1.y)));
}

const layerInt = (v) => (isNum(v) ? T.int(Math.trunc(v)) : T.int(T.floor(F(v).add(0.5))));

/** surfacing._Data: a material's reads of baked surface data through the two-slot reader. has(name), value(name) (a
 * decoded map: the even and odd slots' reads mixed by the reader's weight), colour(family) (C or P, linear), the
 * field normal and the macro normal. Made by Data.create (the textures are async). */
export class Data {
    static async create(sd, names, coords, fp, consts, opts = {}) {
        const want = new Set();
        for (const n of names) {
            for (const m of (MP.PAIRS[n] ?? [n])) {
                try {
                    if (MP.spec(m).family === 'M' && sd.has(m)) want.add(m);
                } catch (_e) { /* a name the registry does not know: read as 0 */ }
            }
        }
        const have = new Set(sd.packing().flat());
        let packNames = null;
        if (![...want].every((n) => have.has(n))) packNames = [...new Set([...have, ...want])].sort();
        const tex = opts.textures ?? await dataTextures(sd, { THREE: opts.THREE, R: opts.R, names: packNames });
        return new Data(sd, tex, coords, fp, consts, opts);
    }

    constructor(sd, tex, coords, fp, consts, opts = {}) {
        const { tileM = 4.0, detailStrength = DETAIL_STRENGTH, cubic = true } = opts;
        this.sd = sd;
        this.tex = tex;
        this.coords = coords;
        this.consts = consts;
        this.fp = fp;
        this.cubic = Boolean(cubic);
        this.rd = readerNodes(sd, coords, fp);
        this.wOdd = this.rd.wOdd;
        this.K = sd.levels.length;
        this.tileM = Number(tileM);
        this.detailStrength = Number(detailStrength);
        this._fam = new Map();
        this._chan = new Map();
        this._val = new Map();
        this._mini = new Map();
        this._nf = null;
        this._nm = null;
        this.rc = sd.readerConstants();
    }

    /** The families the textures hold: D, E, F, C, P as present, and M0.. of the packing. */
    images() {
        return new Set([...Object.keys(this.tex.fam), ...this.tex.mFamilies]);
    }

    has(name) {
        if (SHADER_NAMES.includes(name)) {
            if (name === 'slope_20m') {
                const packed = new Set(this.sd.packing().flat());
                return packed.has('n20_x') && packed.has('n20_y');
            }
            return 'D' in this.tex.fam;
        }
        let fam;
        try {
            [fam] = this.sd.channel(name);
        } catch (_e) {
            return false;
        }
        return this.images().has(fam);
    }

    hasFamily(f) {
        return this.images().has(f);
    }

    /** A family's two slot reads, [[rgb, alpha] even, [rgb, alpha] odd]: mipmapped Linear; the CUBIC_FAMILIES (with
     * cubic) also read bicubic, taken where a texel is magnified (a pixel spanning under CUBIC_PX[0] of it; the
     * mipmapped read past CUBIC_PX[1]): a threshold on a bilinear read of a sharp slope break follows the texel grid
     * in a staircase, which a steep face stretches into teeth down the dip. */
    fam(f) {
        if (!this._fam.has(f)) {
            const lay = (f === 'D' || f === 'E') ? 'detail' : 'cell';
            const isM = f.startsWith('M');
            const tex = isM ? this.tex.M : this.tex.fam[f];
            const mOff = isM ? this.tex.mFamilies.indexOf(f) * this.K : 0;
            const out = [0, 1].map((s) => {
                const uv = this.rd[lay][s];
                const layer = layerInt(add(this.rd.slotLayer[s], mOff));
                const lin = T.texture(tex, uv).depth(layer);
                let col = lin.rgb, alpha = lin.a;
                if (this.cubic && CUBIC_FAMILIES.includes(f)) {
                    const cub = cubicRead(tex, uv, layer, this.tex.sizes[lay]);
                    const w = this._minified(lay, s);
                    col = mixv(w, cub.rgb, col);
                    alpha = mixf(w, cub.a, alpha);
                }
                return [col, alpha];
            });
            this._fam.set(f, out);
        }
        return this._fam.get(f);
    }

    _minified(lay, s) {
        const key = `${lay}:${s}`;
        if (!this._mini.has(key)) {
            const tex = this.rc[lay].map((t) => Number(t.texel));
            this._mini.set(key, smooth(CUBIC_PX[0], CUBIC_PX[1], div(this.fp, this.slotConst(tex, s))));
        }
        return this._mini.get(key);
    }

    chan(f, c) {
        const key = `${f}:${c}`;
        if (!this._chan.has(key)) {
            this._chan.set(key, this.fam(f).map(([col, alpha]) => (c === 3 ? alpha : sep(col)[c])));
        }
        return this._chan.get(key);
    }

    mix(e, o) {
        return mixf(this.wOdd, e, o);
    }

    /** A per-level constant as the slot (0 even, 1 odd) reads it: telescoped over that parity's windows. */
    slotConst(vals, slot) {
        vals = vals.map(Number);
        const first = this.K > slot ? slot : 0;
        let acc = vals[first];
        for (let k = first + 2; k < this.K; k += 2) {
            const d = vals[k] - vals[k - 2];
            if (d !== 0) acc = madd(this.rd.sel[k], d, acc);
        }
        return acc;
    }

    value(name) {
        if (this._val.has(name)) return this._val.get(name);
        let v;
        if (SHADER_NAMES.includes(name)) {
            v = this._derived(name);
        } else {
            const [fam, ch, [kind, a, b]] = this.sd.channel(name);
            if (Array.isArray(ch)) throw new Error(`${name}: a pair: read its channels by their own names`);
            v = this._decode(fam, ch, kind, a, b);
        }
        this._val.set(name, v);
        return v;
    }

    valueRaw(name) {
        if (!this._val.has(name)) {
            const [fam, ch, [kind, a, b]] = this.sd.channel(name);
            this._val.set(name, this._decode(fam, ch, kind, a, b));
        }
        return this._val.get(name);
    }

    _decode(fam, ch, kind, a, b) {
        const [e, o] = this.chan(fam, ch);
        if (kind === 'affine') {
            if (!Array.isArray(a) && !Array.isArray(b)) {
                const m = this.mix(e, o);
                return (Number(a) === 1.0 && Number(b) === 0.0) ? m : madd(m, Number(a), Number(b));
            }
            const av = Array.isArray(a) ? a : new Array(this.K).fill(a);
            const bv = Array.isArray(b) ? b : new Array(this.K).fill(b);
            return this.mix(madd(e, this.slotConst(av, 0), this.slotConst(bv, 0)), madd(o, this.slotConst(av, 1), this.slotConst(bv, 1)));
        }
        if (kind === 'square') return this.mix(mul(mul(e, e), Number(a)), mul(mul(o, o), Number(a)));
        if (kind === 'z_plus') {
            const bv = Array.isArray(b) ? b : new Array(this.K).fill(b);
            const z = sep(this.coords)[2];
            return add(z, this.mix(add(e, this.slotConst(bv, 0)), add(o, this.slotConst(bv, 1))));
        }
        throw new Error(`decode rule ${kind}`);
    }

    /** The linear colour of C or P (sRGB textures: the GPU hands the shader linear values). */
    colour(fam) {
        const key = `colour:${fam}`;
        if (!this._val.has(key)) {
            const [[e], [o]] = this.fam(fam);
            this._val.set(key, mixv(this.wOdd, e, o));
        }
        return this._val.get(key);
    }

    /** [nx, ny, nz, N]: the field normal from D (the two slots' x, y mixed, z rebuilt). */
    nField() {
        if (this._nf === null) {
            const nx = this.valueRaw('normal_x'), ny = this.valueRaw('normal_y');
            const nz = msqrt(mmax(sub(sub(1.0, mul(nx, nx)), mul(ny, ny)), 1e-4));
            this._nf = [nx, ny, nz, vnorm(v3(nx, ny, nz))];
        }
        return this._nf;
    }

    /** The macro normal: the field normal tilted by the relief below the cell, normalize(nx / nz - s k gx,
     * ny / nz - s k gy, 1), s the detail strength and k the level's fade (the relief's finest octave, two of D's
     * texels, against the scans' tile: under one tile the scans' own normals carry that band). */
    nMacro() {
        if (this._nm === null) {
            const [nx, ny, nz, N] = this.nField();
            if (this.detailStrength > 0.0 && this.has('detail_gx')) {
                const lam = this.rc.detail.map((t) => 2.0 * Number(t.texel));
                const kl = lam.map((v) => pySmooth(this.tileM, 2.0 * this.tileM, v) * this.detailStrength);
                const ks = new Set(kl).size > 1 ? this.mix(this.slotConst(kl, 0), this.slotConst(kl, 1)) : kl[0];
                const gx = this.valueRaw('detail_gx'), gy = this.valueRaw('detail_gy');
                let hx, hy;
                if (isNum(ks) && ks === 0.0) {
                    hx = div(nx, nz);
                    hy = div(ny, nz);
                } else {
                    hx = sub(div(nx, nz), mul(gx, ks));
                    hy = sub(div(ny, nz), mul(gy, ks));
                }
                this._nm = vnorm(v3(hx, hy, 1.0));
            } else {
                this._nm = N;
            }
        }
        return this._nm;
    }

    _derived(name) {
        if (name === 'height') return sep(this.coords)[2];
        if (name === 'slope_20m') {
            const ax = this.value('n20_x'), ay = this.value('n20_y');
            const nz = msqrt(mmax(sub(sub(1.0, mul(ax, ax)), mul(ay, ay)), 1e-6));
            return mdeg(macos(mmin(nz, 1.0)));
        }
        const [nx, ny, , N] = this.nField();
        if (name === 'slope') return mdeg(macos(mmin(sep(N)[2], 1.0)));
        if (name === 'aspect') return mfmod(mdeg(matan2(nx, ny)), 360.0);
        if (name === 'northness' || name === 'eastness') {
            const r = msqrt(mmax(add(mul(nx, nx), mul(ny, ny)), 1e-12));
            const fade = div(smooth(1.0, 3.0, this.value('slope')), r);
            return mul(name === 'northness' ? ny : nx, fade);
        }
        if (name === 'insolation') {
            const [az, el] = P.climateSun(this.consts).map((v) => (v * Math.PI) / 180);
            const s = [Math.sin(az) * Math.cos(el), Math.cos(az) * Math.cos(el), Math.sin(el)];
            return mmax(vdot(N, s), 0.0);
        }
        throw new Error(`no derived map ${name}`);
    }
}


// ------------------------------------------------------------------------------- where the shader stands ---

// The Blender-frame shading inputs of a NodeMaterial on the terrain mesh: object coordinates (TexCoord Object), the
// geometry normal and the incoming direction (world: the terrain keeps an identity transform), the view distance
// (Camera Data, the length of the view-space position).
function shadingInputs() {
    const p = T.positionLocal;
    const coords = T.vec3(p.x, p.z.negate(), p.y);
    const n = T.normalWorldGeometry;
    const Ng = T.vec3(n.x, n.z.negate(), n.y);
    const vin = T.normalize(T.cameraPosition.sub(T.positionWorld));
    const Vin = T.vec3(vin.x, vin.z.negate(), vin.y);
    const vd = T.length(T.positionView);
    return { coords, Ng, Vin, vd };
}

// a Blender-frame world direction to the view-space normal a NodeMaterial's normalNode is
function toViewNormal(n) {
    const w = T.vec3(n.x, n.z, n.y.negate());
    return T.normalize(T.cameraViewMatrix.mul(T.vec4(w, 0.0)).xyz);
}


// --------------------------------------------------------------------------------------- eido_terrain_map ---

/** eido_terrain_map (surfacing.terrain_map_group; SURFACING_DESIGN.md 2.7): a terrain's baked maps per pixel through
 * the same two-slot reader, for agents' own NodeMaterials. Returns { name: TSL node } decoded to its unit (maps.js
 * MAPS): the maps in the M families (by default the current packing), D's normal_x, normal_y, detail_gx, detail_gy,
 * E's crease, cavity, crest_fine, grain, F's strata and src_strata, C's far_colour and far_roughness and P's
 * down_colour and down_share where baked, the derived slope, aspect, northness, eastness, insolation, height
 * (slope_20m when n20 is packed), and Level (the finest window holding the pixel). Use the nodes in a material on the
 * terrain mesh (the reader reads the mesh's object coordinates). names: pack these maps into the M families first.
 * opts: THREE, R, TSL. */
export async function terrainMap(sd, names = null, opts = {}) {
    await tslModule(opts);
    if (names && names.length) sd.pack([...names]);
    const tex = await dataTextures(sd, { THREE: opts.THREE, R: opts.R });
    const { coords, Ng, Vin, vd } = shadingInputs();
    const ndv = mabs(vdot(Ng, Vin));
    const fp = div(mul(vd, Number(P.CONSTANTS.pixel_angle)), mmax(ndv, 0.05));
    const dat = new Data(sd, tex, coords, fp, { ...P.CONSTANTS }, { cubic: opts.cubic ?? true });
    const out = {};
    const packed = [...new Set(sd.packing().flat())].sort();
    const fixed = [];
    for (const f of ['D', 'E', 'F']) if (f in tex.fam) for (const n of MP.FAMILIES[f].channels) if (n !== null) fixed.push(n);
    for (const n of [...packed, ...fixed]) {
        if (dat.has(n)) out[n] = ['normal_x', 'normal_y', 'detail_gx', 'detail_gy'].includes(n) ? dat.valueRaw(n) : dat.value(n);
    }
    for (const [f, cn, an] of [['C', 'far_colour', 'far_roughness'], ['P', 'down_colour', 'down_share']]) {
        if (dat.hasFamily(f)) {
            out[cn] = dat.colour(f);
            out[an] = dat.value(an);
        }
    }
    for (const n of ['slope', 'aspect', 'northness', 'eastness', 'insolation', 'height']) out[n] = dat.value(n);
    if (dat.has('slope_20m')) out.slope_20m = dat.value('slope_20m');
    out.Level = dat.rd.level;
    for (const [k, v] of Object.entries(out)) out[k] = isNum(v) ? T.float(v) : v;
    Object.defineProperty(out, '_data', { value: dat, enumerable: false });
    return out;
}


// ------------------------------------------------------------------------------------- the packed scans ---

const DENO_BITMAP = Symbol.for('Deno_bitmapData');

/** An image file's pixels as stored: { data (Uint8Array, rows top first, `channels` bytes a pixel; 16-bit samples
 * as two bytes each, little-endian), width, height, channels, bits }. Deno's own decoder (the edition's
 * loadImageTexture's), with no colour transform. Its premultiplyAlpha stays 'default', which hands over the stored
 * bytes; 'none' divides a PNG's colour by its alpha on this Deno (measured on a packed scan: 132 read as 149 under
 * an alpha of 226), and a packed scan's alpha is data (height, AO). */
export async function readImage(path) {
    const bytes = await Deno.readFile(path);
    const bmp = await createImageBitmap(new Blob([bytes]), { colorSpaceConversion: 'none' });
    if (typeof bmp[DENO_BITMAP] !== 'function') throw new Error(`readImage: this Deno cannot hand over decoded pixels (${path})`);
    const raw = bmp[DENO_BITMAP]();
    const w = bmp.width, h = bmp.height, px = w * h;
    const per = raw.length / px;
    if (![1, 2, 3, 4, 6, 8].includes(per)) throw new Error(`readImage: ${raw.length} bytes for ${w} x ${h} (${path})`);
    // 16-bit samples: a grey, grey-alpha, RGB or RGBA image of two bytes a sample
    const sixteen = per === 6 || per === 8 || (per === 2 && /\.png$/i.test(path) && pngBitDepth(bytes) === 16);
    const channels = sixteen ? per / 2 : per;
    return { data: raw, width: w, height: h, channels, bits: sixteen ? 16 : 8 };
}

// n words of a byte array (a view when it is aligned, else a copy)
function u32Of(u8, n) {
    if (u8.byteOffset % 4 === 0) return new Uint32Array(u8.buffer, u8.byteOffset, n);
    const w = new Uint32Array(n);
    new Uint8Array(w.buffer).set(u8.subarray(0, 4 * n));
    return w;
}

function pngBitDepth(bytes) {
    return bytes.length > 24 && bytes[12] === 0x49 && bytes[13] === 0x48 ? bytes[24] : 8;   // IHDR's bit depth
}

/** surfacing.packed_set: { dir, stats, name } of a scan set, packing it first if the cache lacks it (packSet), with
 * its normal variance record (scanNormalVariance). */
export async function packedSet(name, prefer = '2k', opts = {}) {
    const dir = await packSet(name, prefer, opts);
    let stats = JSON.parse(await Deno.readTextFile(`${dir}/stats.json`));
    if ((stats.normal_var ?? {}).version !== NORMAL_VAR_VERSION) stats = await scanNormalVariance(dir, stats, opts);
    return { dir, stats, name: stats.set };
}

// the packed images of one scan, as the array's layer: RGBA8 bytes, rows south first (Blender's image rows: a read
// at v = 0 is the image's bottom row), resampled to S x S on the GPU when smaller
async function scanLayer(R, path, S) {
    const im = await readImage(path);
    if (im.channels !== 4 || im.bits !== 8) throw new Error(`${path}: a packed scan image is 8-bit RGBA (got ${im.channels} x ${im.bits}-bit)`);
    const { width: w, height: h } = im;
    const src = R.field(h, w, 1, u32Of(im.data, w * h), 'u32');
    const out = R.field(S, S, 1, null, 'u32');
    R.run(R.kernel('surfacing_scan_layer', SCAN_LAYER), { src }, { outW: out }, { uSrc: [w, h], uDst: S });
    const [got] = await R.readAll([out]);
    src.destroy();
    out.destroy();
    return new Uint8Array(got.buffer, got.byteOffset, S * S * 4);
}

// a packed scan image's layer: rows turned south first, bilinear onto S x S (REPEAT, a texel centre on a texel centre
// when the sizes agree: a copy)
const SCAN_LAYER = `//! sampler src r32ui
//! image outW r32ui
//! uniform ivec2 uSrc
//! uniform int uDst
fn texel(i: i32, j: i32) -> vec4<f32> {
  let w = u.uSrc.x;
  let h = u.uSrc.y;
  let ii = ((i % w) + w) % w;
  let jj = ((j % h) + h) % h;
  return unpack4x8unorm(src_at(vec2<i32>(ii, h - 1 - jj)));
}
fn kmain(p: vec2<i32>) {
  if (p.x >= u.uDst || p.y >= u.uDst) { return; }
  let w = u.uSrc.x;
  if (w == u.uDst) {
    outW_store(p, src_at(vec2<i32>(p.x, u.uSrc.y - 1 - p.y)));
    return;
  }
  let fx = (f32(p.x) + 0.5) * f32(w) / f32(u.uDst) - 0.5;
  let fy = (f32(p.y) + 0.5) * f32(u.uSrc.y) / f32(u.uDst) - 0.5;
  let x0 = i32(floor(fx));
  let y0 = i32(floor(fy));
  let a = fx - floor(fx);
  let b = fy - floor(fy);
  let v = mix(mix(texel(x0, y0), texel(x0 + 1, y0), a), mix(texel(x0, y0 + 1), texel(x0 + 1, y0 + 1), a), b);
  outW_store(p, pack4x8unorm(v));
}
`;

/** The packed scans of a palette's layers as two THREE.DataArrayTextures (Ekigar's materials/texture_arrays.js
 * makeArray, below, for the two packed images surfacing.py reads: albedo_height sRGB with its linear alpha, and
 * normal_rough_ao), one layer per distinct set, all at the largest set's size: { albedo, nrao, size, layerOf: { set:
 * layer }, sets: [packedSet per palette layer] }. Cached per palette's sets in the process. */
export async function scanArrays(pal, opts = {}) {
    const THREE = opts.THREE ?? await import('three/webgpu');
    const R = opts.R ?? await (await import('../core/gpu.js')).init();
    const prefer = opts.prefer ?? '2k';
    const sets = [];
    for (const L of pal.layers) sets.push(await packedSet(L.set, prefer, { log: opts.log, R }));
    const names = [...new Set(sets.map((s) => s.name))];
    const key = `${names.join(',')}|${prefer}`;
    if (SCANS.has(key)) return { ...SCANS.get(key), sets };
    const S = Math.max(...names.map((n) => Number(sets.find((s) => s.name === n).stats.size[0])));
    const per = S * S * 4;
    const planes = { albedo: new Uint8Array(per * names.length), nrao: new Uint8Array(per * names.length) };
    for (let k = 0; k < names.length; k++) {
        const s = sets.find((x) => x.name === names[k]);
        planes.albedo.set(await scanLayer(R, `${s.dir}/albedo_height.png`, S), k * per);
        planes.nrao.set(await scanLayer(R, `${s.dir}/normal_rough_ao.png`, S), k * per);
    }
    const out = { albedo: makeArray(THREE, 'albedo', planes.albedo, S, names.length, 16),
        nrao: makeArray(THREE, 'nrao', planes.nrao, S, names.length, 16), size: S,
        layerOf: Object.fromEntries(names.map((n, k) => [n, k])) };
    SCANS.set(key, out);
    return { ...out, sets };
}
const SCANS = new Map();

// From the earlier terrain prototype's texture arrays (Ekigar's materials/texture_arrays.js): one DataArrayTexture
// per channel set, sampled at a per-layer index, so a
// palette's six layers bind two textures. Its channel list is surfacing.py's two packed images here (albedo_height:
// sRGB colour, linear height in alpha; nrao: data), in place of the layer stack's four.
function makeArray(THREE, channel, data, size, depth, anisotropy) {
    const t = new THREE.DataArrayTexture(data, size, size, depth);
    t.format = THREE.RGBAFormat;
    t.type = THREE.UnsignedByteType;
    t.colorSpace = channel === 'albedo' ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    // linear is required for correctness and for the binding count to mean anything: an unfilterable texture is
    // bound without a sampler
    t.magFilter = THREE.LinearFilter;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.generateMipmaps = true;
    t.anisotropy = anisotropy;
    t.needsUpdate = true;
    t.name = `materialArray:${channel}`;
    return t;
}


// --------------------------------------------------------------------------------------------- hex tiling ---

/** A layer's default hex lattice, metres: its tile snapped to HEX_LADDER x 2^n (surfacing.hex_class). */
export function hexClass(tileM) {
    return HEX_LADDER * 2.0 ** pyRoundHalfEven(Math.log2(Math.max(Number(tileM), 1e-3) / HEX_LADDER));
}

/** surfacing.hex_grid_group: hex tiling's triangle grid (SURFACING_DESIGN.md 3.3; Mikkelsen 2022, written from the
 * published description) at `pos` (its x, y: metres along the frame's axes), 1 / hex_m, seed. Per slot c = 0, 1, 2:
 * { RD (the position from the slot's grid vertex, turned by its random angle), O (its random offset, in tiles), W
 * (its barycentric weight), CS ((cos, sin, 0) of the angle, with rotate) }. A read's coordinate is RD / tile + O; its
 * normal's (nx, ny) turned back into the frame is (dot(n, CS), cross(CS, n).z). A slot's vertex changes only across
 * the far edges of its hexagon, where its weight is 0. */
export function hexGrid(pos, invSize, seed, rotate = true) {
    const [U, V] = sep(pos);
    const k = invSize * 2.0 * Math.sqrt(3.0);
    const su = mul(U, k), sv = mul(V, k);
    const a = madd(sv, -0.57735027, su);                 // skewed onto the triangle grid
    const b = mul(sv, 1.15470054);
    const bx = mfloor(a), by = mfloor(b);
    const fx = sub(a, bx), fy = sub(b, by);
    const t = add(fx, fy);
    const s = mgt(t, 1.0);                               // the upper triangle of the cell
    const u1 = sub(1.0, t);
    const Wb = [mabs(u1), madd(s, u1, fx), madd(s, u1, fy)];
    // the vertices: P0 = base + s (1, 1) of class k0, P1 = base + (1, 0) of class k0 + 1, P2 = base + (0, 1) of class
    // k0 + 2 (k0 = (i - j) mod 3 of the base); slot c takes P_j with j = (c - k0) mod 3
    const k0 = mfmod(sub(bx, by), 3.0);
    const e0 = mlt(k0, 0.5), e2 = mgt(k0, 1.5);
    const E = [e0, sub(sub(1.0, e0), e2), e2];
    const hm = 1.0 / k, hv = hm * 0.8660254;
    const out = [];
    for (let c = 0; c < 3; c++) {
        const ea = E[c], eb = E[(c + 2) % 3], ec = E[(c + 1) % 3];
        const vx = add(bx, madd(ea, s, eb));
        const vy = add(by, madd(ea, s, ec));
        const w = madd(ec, Wb[2], madd(eb, Wb[1], mul(ea, Wb[0])));
        const cu = mul(madd(vy, 0.5, vx), hm);
        const cv = mul(vy, hv);
        const D = vsub(pos, v3(cu, cv, 0.0));
        const wn = whiteNoise3(vx, vy, seed);
        const slot = { O: wn, W: w };
        if (!rotate) {
            slot.RD = D;
        } else {
            // the turn: u = du cos - dv sin, v = du sin + dv cos, as a dot and a cross product with (cos, -sin, 0)
            const th = madd(wn.z, 2.0 * Math.PI, -Math.PI);
            const cs = T.cos(th), sn = T.sin(th);
            const csn = v3(cs, sn.negate(), 0.0);
            slot.RD = v3(vdot(D, csn), vcross(csn, D).z, 0.0);
            slot.CS = v3(cs, sn, 0.0);
        }
        out.push(slot);
    }
    return out;
}

/** surfacing._hex_plan: per layer [planar lattice, turned, sector lattice, turned], metres (0: one read). */
export function hexPlan(layers, hexed, opt = {}) {
    const pick = (L, key, dflt) => {
        const v = (L[key] !== null && L[key] !== undefined) ? L[key] : opt[key];
        return v === null || v === undefined ? dflt : v;
    };
    const boxTiles = layers.filter((L) => L.projection === 'box').map((L) => Number(L.tile_m));
    const steep = boxTiles.length ? STEEP_HEX * hexClass(Math.max(...boxTiles)) : 0.0;
    const share = Number(opt.steep_hex_share ?? STEEP_HEX_SHARE) || 0.0;
    return layers.map((L) => {
        let ph = Number(pick(L, 'hex_m', hexClass(L.tile_m)));
        const big = !boxTiles.length || Number(L.tile_m) >= share * Math.max(...boxTiles);
        let sh = Number(pick(L, 'steep_hex_m', big ? steep : 0.0));
        if (!hexed) ph = sh = 0.0;
        if (L.projection !== 'box') sh = 0.0;
        return [Math.max(ph, 0.0), Boolean(pick(L, 'hex_rotate', true)), Math.max(sh, 0.0), Boolean(pick(L, 'steep_rotate', false))];
    });
}


// --------------------------------------------------------------------------------------- a layer's reads ---

/** surfacing._layer_group: one layer's scan reads. Returns { col (the scan's albedo), h (its normalised height), hs
 * (the soft height: the same reads' heights by their plain weights), nx, ny (its normal in the world-XY tangent
 * frame: the planar reads), pert (box layers: the world-space tilt of the sector reads' normals), rough, ao }.
 * scans: scanArrays(); S: the layer's packedSet; plan: hexPlan's row; g: { P: the planar hex grid, S0, S1: the
 * sector slots' grids } (null for a frame read once); box inputs: sec (sectorFrames), steep. */
function layerReads(L, S, i, opt, box, plan, ctx) {
    const { scans, coords, vd, g, sec, steep } = ctx;
    const tile = Number(L.tile_m);
    const [hexM, , sHexM, sRot] = plan;
    const pRot = plan[1];
    const ns = Number(L.normal);
    const interp = opt.interpolation;
    const dd = (opt.detail_distance ?? [4.0, 9.0]).map(Number);
    const layer = T.int(scans.layerOf[S.name]);
    const farK = box ? (Number(opt.far_scale ?? 1.0) || 1.0) : 1.0;
    const wall = farK > 1.0 ? { k: farK, d: (opt.far_distance ?? [40.0, 200.0]).map(Number),
        mm: Number(L.macro_mod ?? opt.macro_mod ?? 0.0) || 0.0, fc: Number(L.far_contrast ?? opt.far_contrast ?? 0.65),
        fb: Number(opt.far_bump ?? 0.5), fh: L.far_height ?? true } : null;
    const far = interp === 'Auto' ? smooth(dd[0], dd[1], vd) : null;
    const inv = 1.0 / tile;
    const read = (tex, uv, how) => {
        if (how === 'Cubic') return cubicRead(tex, uv, layer, scans.size);
        return T.texture(tex, uv).depth(layer);
    };
    const albedo = (uv, auto) => {
        if (auto && interp === 'Auto') {
            const c1 = read(scans.albedo, uv, 'Cubic'), c2 = read(scans.albedo, uv, 'Linear');
            return [mixv(far, c1.rgb, c2.rgb), mixf(far, c1.a, c2.a)];
        }
        const s = read(scans.albedo, uv, interp === 'Cubic' ? 'Cubic' : 'Linear');
        return [s.rgb, s.a];
    };
    // one read of the scan at uv; cs: the (cos, sin, 0) of a turned read, its normal turned back into the frame
    const one = (uv, auto, cs = null) => {
        const [col, h] = albedo(uv, auto);
        const nr = read(scans.nrao, uv, 'Linear');
        let nx, ny;
        if (cs === null) {
            nx = madd(nr.r, 2.0 * ns, -ns);
            ny = madd(nr.g, 2.0 * ns, -ns);
        } else {
            const nv = V3(nr.rgb).mul(T.vec3(2.0 * ns, 2.0 * ns, 0.0)).add(T.vec3(-ns, -ns, 0.0));
            nx = vdot(nv, cs);
            ny = vcross(cs, nv).z;
        }
        return { col, h, hs: h, nx, ny, rough: nr.b, ao: nr.a };
    };
    const blend = (reads, ws) => {
        const o = {};
        for (const key of ['h', 'nx', 'ny', 'rough', 'ao']) {
            let acc = mul(reads[0][key], ws[0]);
            for (let q = 1; q < reads.length; q++) acc = madd(reads[q][key], ws[q], acc);
            o[key] = acc;
        }
        let acc = vscale(reads[0].col, ws[0]);
        for (let q = 1; q < reads.length; q++) acc = vadd(acc, vscale(reads[q].col, ws[q]));
        o.col = acc;
        return o;
    };
    // a frame's read: once at pos / tile (lattice 0), or the three reads of its hex grid, sharpened by w^7 and heights
    const frame = (grid, pos, auto, size, turned) => {
        if (size <= 0.0) {
            const uv = vscale(pos, inv);
            return one(T.vec2(uv.x, uv.y), auto);
        }
        const reads = [], ws = [];
        for (let c = 0; c < 3; c++) {
            const sl = grid[c];
            const uvw = V3(sl.RD).mul(T.vec3(inv, inv, 0.0)).add(sl.O);
            const r = one(T.vec2(uvw.x, uvw.y), auto, turned ? sl.CS : null);
            reads.push(r);
            ws.push(mul(mpow(sl.W, HEX_POWER), madd(r.h, 2.0 * HEX_CONTRAST, 1.0 - HEX_CONTRAST)));
        }
        const tot = div(1.0, mmax(add(add(ws[0], ws[1]), ws[2]), 1e-6));
        const o = blend(reads, ws.map((w) => mul(w, tot)));
        // the soft height: the three reads' heights by their plain barycentric weights (they sum to 1), its swing
        // about 0.5 scaled down where a hexagon is wider than BLEND_PATCH_M
        const hs = madd(reads[2].h, grid[2].W, madd(reads[1].h, grid[1].W, mul(reads[0].h, grid[0].W)));
        const f = Math.min(1.0, BLEND_PATCH_M / (HEX_PATCH * size));
        o.hs = f >= 1.0 ? hs : madd(sub(hs, 0.5), f, 0.5);
        return o;
    };
    // (a's share, b's share) of two reads by weight wa and height: a_i = w_i + h_i / 2, kept within 0.2, normalised
    const heightPair = (wa, ha, hb) => {
        const aa = madd(ha, 0.5, wa);
        const ab = madd(hb, 0.5, sub(1.0, wa));
        const ma = sub(mmax(aa, ab), 0.2);
        const ba = mmax(sub(aa, ma), 0.0), bb = mmax(sub(ab, ma), 0.0);
        const tot = div(1.0, mmax(add(ba, bb), 1e-5));
        return [mul(ba, tot), mul(bb, tot)];
    };
    const p = frame(g.P, coords, true, hexM, pRot);
    if (!box) return { col: p.col, h: p.h, hs: p.hs, nx: p.nx, ny: p.ny, pert: null, rough: p.rough, ao: p.ao };
    const W0 = sec[0].w;
    const secR = [0, 1].map((s) => frame(g[`S${s}`], sec[s].P, false, sHexM, sRot));
    const [we, wo] = heightPair(W0, secR[0].h, secR[1].h);
    const sb = blend(secR, [we, wo]);
    let hsSteep = mixf(W0, secR[1].hs, secR[0].hs);
    let pert = null;
    for (const [s, w] of [[0, we], [1, wo]]) {
        const t2 = vscale(vadd(vscale(sec[s].T, secR[s].nx), vscale(sec[s].B, secR[s].ny)), w);
        pert = pert === null ? t2 : vadd(pert, t2);
    }
    if (wall !== null) {
        // the far read on steep faces, one per sector slot, the two slots height blended
        const fd = smooth(wall.d[0], wall.d[1], vd);
        const invF = inv / wall.k;
        const nsf = ns * wall.fb;
        const slot = [0, 1].map((s) => {
            const vec = V3(sec[s].P).mul(T.vec3(invF, invF, 0.0)).add(T.vec3(0.37 + 0.21 * i + 0.5 * s, 0.71 - 0.17 * i + 0.3 * s, 0.0));
            const uv = T.vec2(vec.x, vec.y);
            const a = read(scans.albedo, uv, 'Linear');
            const nr = read(scans.nrao, uv, 'Linear');
            const t2 = vadd(vscale(sec[s].T, madd(nr.r, 2.0 * nsf, -nsf)), vscale(sec[s].B, madd(nr.g, 2.0 * nsf, -nsf)));
            return [a.rgb, a.a, t2];
        });
        const [fwe, fwo] = heightPair(W0, slot[0][1], slot[1][1]);
        let fcol = vadd(vscale(slot[0][0], fwe), vscale(slot[1][0], fwo));
        const fh = madd(slot[1][1], fwo, mul(slot[0][1], fwe));
        const fpert = vadd(vscale(slot[0][2], fwe), vscale(slot[1][2], fwo));
        const meanLin = S.stats.mean_albedo_linear.map(Number);
        let near = sb.col;
        if (wall.mm > 0.0) {                                // the scan as its own macro variation map
            const ml = Math.max(meanLin.reduce((acc, v, q) => acc + v * LUMA[q], 0), 1e-4);
            const lum = vdot(fcol, LUMA);
            const mod = mmin(mmax(madd(lum, wall.mm / ml, 1.0 - wall.mm), 0.55), 1.6);
            near = vscale(near, mod);
        }
        if (wall.fc !== 1.0) fcol = vadd(vscale(fcol, wall.fc), meanLin.map((v) => (1.0 - wall.fc) * v));
        sb.col = mixv(fd, near, fcol);
        if (wall.fh) {
            sb.h = mixf(fd, sb.h, fh);
            hsSteep = mixf(fd, hsSteep, fh);
        }
        pert = mixv(fd, pert, fpert);
    }
    const hs = mixf(steep, p.hs, hsSteep);
    const [wp, ws] = heightPair(sub(1.0, steep), p.h, sb.h);
    const o = blend([p, sb], [wp, ws]);
    return { col: o.col, h: o.h, hs, nx: mul(p.nx, wp), ny: mul(p.ny, wp), pert: vscale(pert, ws), rough: o.rough, ao: o.ao };
}

/** surfacing._sector_frames: the two sector slots (SURFACING_DESIGN.md 3.4), per slot { P (u, v, 0), w, T, B }. The
 * bearing is the azimuth of the field normal (the face's own, from D); the even slot reads the even sector nearest it
 * (multiples of 90 degrees), the odd slot the odd one; the even slot's weight is smoothstep(0.1, 0.9, s), s = |2
 * frac(phi / 90) - 1|, so a slot changes sector only where its weight is exactly 0. Frame k: u = P . t_k along the
 * strike, v = P . b_k up the fixed dip SECTOR_DIP_DEG. T, B: t_k and b_k on the shading normal's tangent plane. */
function sectorFrames(dat, coords, Nm) {
    const [nx, ny] = dat.nField();
    const [x, y, z] = sep(coords);
    const q = div(matan2(ny, nx), 0.5 * Math.PI);
    const fl = mfloor(q);
    const s = mabs(madd(sub(q, fl), 2.0, -1.0));
    const wEven = smooth(0.1, 0.9, s);
    const cd = Math.cos((SECTOR_DIP_DEG * Math.PI) / 180), sd = Math.sin((SECTOR_DIP_DEG * Math.PI) / 180);
    const out = [mul(mround(q), 0.5 * Math.PI), mul(add(fl, 0.5), 0.5 * Math.PI)].map((phi) => {
        const c = mcos(phi), sn = msin(phi);
        const U = madd(y, c, mul(x, mul(sn, -1.0)));
        const V = madd(z, sd, mul(madd(x, c, mul(y, sn)), -cd));
        const Tv = v3(mul(sn, -1.0), c, 0.0);
        const Tp = vnorm(vsub(Tv, vscale(Nm, vdot(Tv, Nm))));
        return { P: v3(U, V, 0.0), T: Tp, B: vcross(Nm, Tp) };
    });
    out[0].w = wEven;
    out[1].w = sub(1.0, wEven);
    return out;
}


// ------------------------------------------------------------------------------------- the layers' pieces ---

/** surfacing._canopy: a forest seen from afar (a palette layer's canopy). { col, h, crown, rEdge, far, bump, cmod }. */
function canopyNodes(cn, coords, i, vd) {
    const crownM = Number(cn.crown_m ?? 4.5);
    // a 3D partition, so crowns keep their size on a steep flank
    const vor = voronoiF1(vadd(coords, [13.7 * (i + 1), -29.1 * (i + 1), 0.0]), 1.0 / crownM, 0.85);
    const dist = vor.x, r1 = vor.y, r2 = vor.z, r3 = vor.w;
    // crowns of differing size and ragged outline
    const rag = noise3(coords, crownM / 2.2, 2.0, 0.5, 71.3 + i);
    const d = mul(dist, add(madd(r3, 0.45, 0.62), mul(rag, 0.45)));
    let crown = sub(1.0, smooth(0.08, 0.6, d));
    const lin = (h) => P.hexLinear(h).map(Number);
    let tone = mixv(r1, lin(cn.colour ?? '#26371f'), lin(cn.light ?? '#3d522c'));
    let bump = mul(mpow(crown, 0.6), Number(cn.height_m ?? 3.0));
    let rEdge = madd(r2, 0.76, 0.12);
    let h = madd(crown, 0.6, 0.25);
    let shade = madd(crown, 0.4, 0.72);
    const clumpM = Number(cn.clump_m ?? 0.0) || 0.0;
    let cmod = null;
    if (clumpM > 0.0) {
        // clumps: crowns grow in clusters a few trees across, with shadowed gaps between them, each its own tone and
        // relief; at the forest's edge whole clusters stand in or out
        const cv = voronoiF1(vadd(coords, [-41.3 * (i + 1), 17.9 * (i + 1), 5.3]), 1.0 / clumpM, 1.0);
        const k1 = cv.y, k2 = cv.z;
        const rag2 = noise3(coords, clumpM / 2.5, 2.0, 0.5, 83.1 + i);
        const cdist = mul(cv.x, madd(rag2, 0.5, 0.75));
        const gap = Number(cn.clump_gap ?? 0.25);
        const clump = sub(1.0, smooth(0.62 - 0.4 * gap, 0.9 - 0.4 * gap, cdist));
        tone = vscale(tone, madd(k1, 0.5, 0.76));
        shade = mul(shade, madd(clump, 0.42, 0.68));
        bump = add(bump, mul(mpow(clump, 0.8), Number(cn.clump_height_m ?? 4.0)));
        rEdge = mixf(0.65, rEdge, madd(k2, 0.76, 0.12));
        h = mul(h, madd(clump, 0.45, 0.55));
        const cf = madd(clump, 0.6, 0.4);
        crown = mul(crown, cf);
        cmod = mul(mul(madd(k1, 0.5, 0.76), madd(clump, 0.42, 0.68)), cf);
    }
    const lit = vscale(tone, shade);
    const col = mixv(smooth(0.0, 0.32, crown), lin(cn.gap ?? '#11160d'), lit);
    const [near0, near1] = (cn.near_m ?? [25.0, 90.0]).map(Number);
    const far = smooth(near0, near1, vd);
    return { col, h, crown, rEdge, far, bump, cmod };
}

function patchList(L) {
    const p = L.patches;
    if (!p) return [];
    return Array.isArray(p) ? [...p] : [p];
}

// surfacing._faded_smooth: smoothstep(lo, hi, n) of a raw Noise Texture Fac faded to its mean with the footprint, the
// edges widened by the spread it lost (RAW_HALF), so its mean cover stays put
function fadedSmooth(comp, lo, hi, n, scaleM, detail) {
    const f = comp.fade(scaleM);
    if (isNum(f)) return smooth(lo, hi, n);
    const nf = madd(sub(n, 0.5), f, 0.5);
    const hs = RAW_HALF[Math.trunc(Math.max(0, Math.min(5, Math.round(Number(detail)))))];
    const sp = madd(f, -hs, hs);
    const sgn = hi >= lo ? 1.0 : -1.0;
    return smooth(madd(sp, -sgn, Number(lo)), madd(sp, sgn, Number(hi)), nf);
}

// surfacing._ripples: wind ripples as a bump height (metres): an asymmetric sawtooth across the wind, its crests bent
// by noise, faded out between fade_m
function ripples(coords, rp, i, vd) {
    const wl = Number(rp.wavelength_m ?? 0.12);
    const hgt = Number(rp.height_m ?? 0.012);
    const az = (Number(rp.azimuth_deg ?? 45.0) * Math.PI) / 180;
    const [f0, f1] = (rp.fade_m ?? [12.0, 35.0]).map(Number);
    const [x, y] = sep(coords);
    const s = madd(x, Math.sin(az) / wl, mul(y, Math.cos(az) / wl));
    const d1 = mul(sub(noise4(coords, 1.0 / (6.0 * wl), 2.0, 0.55, 23.1 + i), 0.5), 1.6);
    const d2 = mul(sub(noise4(coords, 1.0 / (40.0 * wl), 2.0, 0.55, 29.3 + i), 0.5), 5.0);
    const f = mfract(add(s, add(d1, d2)));
    const prof = mmin(mul(f, 1.0 / 0.8), mul(sub(1.0, f), 1.0 / 0.2));
    const fade = sub(1.0, smooth(f0, f1, vd));
    return mul(mul(sub(prof, 0.5), hgt), fade);
}

// Blender's Hue/Saturation/Value node (node_hue_sat over rgb_to_hsv and hsv_to_rgb), factor 1
function hueSatValue(col, hue, satur, value) {
    const c = V3(col);
    const cmax = T.max(c.x, T.max(c.y, c.z)), cmin = T.min(c.x, T.min(c.y, c.z));
    const cdelta = cmax.sub(cmin);
    const s = SEL(cmax.notEqual(0.0), cdelta.div(T.max(cmax, 1e-30)), T.float(0.0));
    const cc = T.vec3(cmax).sub(c).div(T.max(cdelta, 1e-30));
    let h = SEL(c.x.equal(cmax), cc.z.sub(cc.y), SEL(c.y.equal(cmax), cc.x.sub(cc.z).add(2.0), cc.y.sub(cc.x).add(4.0)));
    h = h.div(6.0);
    h = SEL(h.lessThan(0.0), h.add(1.0), h);
    h = SEL(s.equal(0.0), T.float(0.0), h);
    let H = T.fract(h.add(F(hue)).add(0.5));
    const Sv = T.clamp(s.mul(F(satur)), 0.0, 1.0);
    const V = cmax.mul(F(value));
    H = SEL(H.equal(1.0), T.float(0.0), H).mul(6.0);
    const ii = T.floor(H), f = H.sub(ii);
    const p = V.mul(T.float(1.0).sub(Sv)), q = V.mul(T.float(1.0).sub(Sv.mul(f))), t = V.mul(T.float(1.0).sub(Sv.mul(T.float(1.0).sub(f))));
    const pick = (a, b, c2, d, e, g) => SEL(ii.equal(0.0), a, SEL(ii.equal(1.0), b, SEL(ii.equal(2.0), c2,
        SEL(ii.equal(3.0), d, SEL(ii.equal(4.0), e, g)))));
    const rgb = T.vec3(pick(V, q, p, p, t, V), pick(t, V, V, q, p, p), pick(p, p, t, V, V, q));
    return SEL(Sv.equal(0.0), T.vec3(V, V, V), rgb);
}

// surfacing._macro: the old material's world-scale variation, as octaves of brightness, hue and saturation drift
function macro(coords, albedo, octaves, n3) {
    if (!octaves || !octaves.length) return albedo;
    let val = null, hue = null, satr = null;
    octaves.forEach((o, k) => {
        const n = n3 ? noise3(coords, Number(o.scale_m), Number(o.detail ?? 2.0), Number(o.roughness ?? 0.5), Number(o.w ?? (1.7 + 2.9 * k)))
            : noise4(coords, 1.0 / Number(o.scale_m), Number(o.detail ?? 2.0), Number(o.roughness ?? 0.5), Number(o.w ?? (1.7 + 2.9 * k)));
        if (o.value) {
            const v = mapRange(n, 0.3, 0.7, 1.0 - o.value, 1.0 + o.value);
            val = val === null ? v : mul(val, v);
        }
        if (o.hue) {
            const h = mapRange(n, 0.3, 0.7, -o.hue, o.hue);
            hue = hue === null ? h : add(hue, h);
        }
        if (o.saturation) {
            const [lo, hi] = o.saturation;
            const s = mapRange(n, 0.3, 0.7, lo, hi);
            satr = satr === null ? s : mul(satr, s);
        }
    });
    // the node's Hue input is 0.5 for no shift: hue + 0.5, read by node_hue_sat as fract(h + Hue + 0.5)
    return hueSatValue(albedo, hue === null ? 0.5 : add(hue, 0.5), satr === null ? 1.0 : satr, val === null ? 1.0 : val);
}

// Blender's Bump node (node_bump, strength 1, not inverted): the surface gradient of the height across the pixel,
// from the position's and the height's screen-space derivatives (EEVEE evaluates the height a pixel over in x and y)
function bumpNode(N, height, dist, Pw) {
    const n = vnorm(N);
    const d = SEL(T.frontFacing, F(dist), F(dist).negate());
    const dPdx = T.dFdx(Pw), dPdy = T.dFdy(Pw);
    const Rx = T.cross(dPdy, n), Ry = T.cross(n, dPdx);
    const det = T.dot(dPdx, Rx);
    const dHdx = T.dFdx(F(height)), dHdy = T.dFdy(F(height));
    const surfgrad = Rx.mul(dHdx).add(Ry.mul(dHdy));
    return vnorm(n.mul(T.abs(det)).sub(surfgrad.mul(d.mul(T.sign(det)))));
}

/** The map names a palette's material reads with baked data (surfacing._data_names). */
function dataNames(pal, weights) {
    const out = new Set();
    const addAll = (e) => { for (const n of P.namesIn(e)) out.add(n); };
    pal.layers.forEach((L, q) => {
        addAll(weights[q]);
        for (const pt of patchList(L)) if (pt.where && !pt.from_ramp) addAll(pt.where);
        if (L.ramp) addAll(L.ramp.t);
        if (L.streaks_where) addAll(L.streaks_where);
        if (L.ledges && typeof L.ledges === 'object' && L.ledges.where) addAll(L.ledges.where);
        const prov = L.provenance ?? {};
        if (prov.src) out.add('src_strata');
        if (prov.down) out.add('deposit');
        if (L.patina !== null && L.patina !== undefined) out.add('fresh');
        if (L.canopy) { out.add('canopy_far'); out.add('canopy_expected'); }
    });
    const o = pal.options;
    for (const key of ['damp_where', 'tone']) if (o[key]) addAll(o[key]);
    for (const key of ['satmap', 'dusting']) {
        const d = o[key];
        if (d && typeof d === 'object') for (const k of ['t', 'where']) if (d[k]) addAll(d[k]);
    }
    const st = pal.strata;
    if (st && (st.source ?? 'attribute') === 'attribute' && pal.layers.some((L) => L.strata)) out.add('strata');
    if (out.has('slope_20m')) { out.add('n20_x'); out.add('n20_y'); }
    return out;
}

// a multiplier as linear [r, g, b]: a number, an [r, g, b] or an sRGB '#rrggbb'
function rgb3(v, dflt = 1.0) {
    if (v === null || v === undefined) v = dflt;
    if (typeof v === 'string') return P.hexLinear(v).map(Number);
    if (typeof v === 'number') return [v, v, v];
    return v.slice(0, 3).map(Number);
}

const amount = (v) => (v === true ? 1.0 : !v ? 0.0 : Number(v));

/** Each layer's weight expression with baked data: its weight, or its fallback where the weight reads a map the data
 * lacks (surfacing._layer_weights). */
function layerWeights(pal, sd, log = null) {
    return pal.layers.map((L) => {
        let w = L.weight;
        const miss = [...P.namesIn(w)].filter((n) => !sd.has(n)).sort();
        if (miss.length && L.fallback !== null && L.fallback !== undefined) {
            if (log) log(`[surfacing] ${pal.name}/${L.name}: the data lacks ${miss.join(', ')}: its fallback weight`);
            w = L.fallback;
        }
        return w;
    });
}

// surfacing._aa_constants: [V, e0, e1] of a layer's scan for the specular anti-aliasing (null without a record)
function aaConstants(S, L) {
    const nv = S.stats.normal_var ?? {};
    const total = Number(nv.total ?? 0.0);
    if (total <= 0.0 || S.stats.has_normal === false) return null;
    const ns = Number(L.normal);
    const l2t = Math.log2(Number(L.tile_m) / Number((S.stats.size ?? [2048])[0]));
    return [total * ns * ns, Number(nv.a) + l2t, Number(nv.b) + l2t];
}

// surfacing._aa_footprint: log2 of the pixel's footprint for the mips' normal averaging (vd pix / sqrt(max(|N.V|, g)))
function aaFootprint(vpix, ndv) {
    return mlog2(div(vpix, msqrt(mmax(ndv, AA_GRAZING))));
}

// surfacing._rough_lost: (r^4 + var)^(1/4), as two square roots
function roughLost(rough, v) {
    if (isNum(v) && v <= 0.0) return rough;
    const r2 = mul(rough, rough);
    return msqrt(msqrt(madd(r2, r2, v)));
}

// surfacing._rough_aa: the roughness with the slope variance its mips have averaged away at this pixel
function roughAa(rough, lfp, aa) {
    const [V, e0, e1] = aa;
    return roughLost(rough, mul(smooth(e0, e1, lfp), V));
}

function mainCell(sd) {
    const lv = [...sd.levels];
    const mains = lv.filter((v) => v.role === 'main');
    return Number((mains.length ? mains[mains.length - 1] : lv[0]).cell);
}

/** surfacing._blend_weights: the layers' blend weights from their coverages: the overlay of the macro data and each
 * scan's soft height on its coverage, the composite in order, then the height blend. per: one { L, cov, hsScan, hs }
 * per layer (a number height is the same for every layer: the far material's 0.5). edgeNoise(i): layer i's edge
 * noise (null: none). */
function blendWeights(comp, dat, sd, per, opt, edgeNoise = null) {
    if (opt.overlay !== false) {
        for (const p of per) {
            if (isNum(p.cov)) continue;
            const ov = { height: 1.0, ...(p.L.overlay ?? {}) };
            let amt = Number(ov.height ?? 0.0);
            let d = 0.5;
            if (amt && !isNum(p.hsScan)) {
                const k = mul(comp.fade(Number(p.L.tile_m)), amt);
                d = madd(sub(p.hsScan, 0.5), k, 0.5);
            }
            for (const key of ['crest', 'crest_fine', 'crease']) {
                amt = Number(ov[key] ?? 0.0) || 0.0;
                if (amt && dat.has(key)) {
                    let term = dat.value(key);
                    if (key !== 'crest') term = mul(term, comp.fade(2.0 * mainCell(sd) / 8.0));   // texel-scale terms fade
                    d = madd(term, amt, d);
                }
            }
            if (isNum(d)) continue;
            d = clamp01(d);
            const cv = p.cov;
            const aLo = mul(mul(cv, d), 2.0);
            const aHi = sub(1.0, mul(mul(sub(1.0, cv), sub(1.0, d)), 2.0));
            p.cov = mixf(mlt(cv, 0.5), aHi, aLo);
        }
    }
    const excl = new Array(per.length).fill(null);
    let rem = 1.0;
    for (let i = per.length - 1; i >= 0; i--) {
        excl[i] = mul(per[i].cov, rem);
        rem = mul(rem, oneMinus(per[i].cov));
    }
    const kb = Number(opt.height_blend);
    const a = per.map((p, i) => {
        let ai = excl[i];
        if (kb > 0 && !isNum(p.hs)) ai = add(ai, mul(p.hs, kb));
        const e = p.L.edge_noise !== null && p.L.edge_noise !== undefined ? Number(p.L.edge_noise) : Number(opt.edge_noise);
        if (e > 0 && i > 0 && edgeNoise) {
            const f = comp.fade(1.0 / 0.85);
            ai = add(ai, mul(sub(edgeNoise(i), 0.5), mul(f, 2.0 * e)));
        }
        return ai;
    });
    if (a.length === 1) return [1.0];
    let ma = a[0];
    for (const v of a.slice(1)) ma = mmax(ma, v);
    ma = sub(ma, Number(opt.blend_depth));
    const b = a.map((v) => mmax(sub(v, ma), 0.0));
    let s = b[0];
    for (const v of b.slice(1)) s = add(s, v);
    s = mmax(s, 1e-5);
    return b.map((v) => div(v, s));
}

/** D0, metres (SURFACING_DESIGN.md 3.7): where the near material hands off to the far colour C, the distance at which
 * a main-level texel spans FAR_TEXEL_PX pixels (c_main / (2.5 pixel_angle)), or the option far_m. */
export function farDistance(pal, sd) {
    const opt = pal.options;
    if (opt.far_m) return Number(opt.far_m);
    const consts = { ...P.CONSTANTS, ...(pal.constants ?? {}) };
    return mainCell(sd) / (FAR_TEXEL_PX * Number(consts.pixel_angle || P.CONSTANTS.pixel_angle));
}

/** Move a per-texel terrain material's hand-off to the far colour to far_m metres (D0: it fades over D0..1.5 D0), in
 * place: a uniform, so nothing is rebuilt or recompiled. The far material's rings are chosen at applySurface: call
 * it again when D0 moves a camera's 1.5 D0 across a ring. Returns the material. */
export function setFarDistance(material, farM) {
    const u = material?.userData?.eidoFarUniform;
    if (!u) throw new Error(`${material?.name ?? 'material'}: no far hand-off (a material without baked data, or a bake without a palette)`);
    u.value = Number(farM);
    material.userData.eidoFarM = Number(farM);
    return material;
}

// surfacing._far_grain: 1 + FAR_GRAIN (luminance / mean - 1) of the base layer's scan read once (mipmapped, planar)
function farGrain(L, S, coords, scans) {
    const meanLin = S.stats.mean_albedo_linear.map(Number);
    const ml = Math.max(meanLin.reduce((a, v, q) => a + v * LUMA[q], 0), 1e-4);
    const uv = vscale(coords, 1.0 / Number(L.tile_m));
    const n = T.texture(scans.albedo, T.vec2(uv.x, uv.y)).depth(T.int(scans.layerOf[S.name]));
    return madd(vdot(n.rgb, LUMA), FAR_GRAIN / ml, 1.0 - FAR_GRAIN);
}

/** The palette's ramps (palettes.rampRows) as surface/layers.js's 256 x rows sRGB LUT, read Closest
 * (surfacing._lut_image): { texture, index, rows, width } or null for a palette without ramps. */
async function lutImage(pal, { THREE, R }) {
    const [rows] = P.rampRows(pal);
    if (!rows.length) return null;
    const L = await import('../surface/layers.js');
    const t = await L.lutTexture(pal, { THREE, R });
    return { texture: t, index: t.userData.index, rows: t.image.height, width: t.image.width };
}

// a ramp's colour from the LUT: its row's centre, t clamped, read Closest
function lutRead(lut, info, t) {
    const W = lut.width, R = lut.rows;
    const u = madd(clamp01(t), (W - 1.0) / W, 0.5 / W);
    return T.texture(lut.texture, T.vec2(F(u), (info.row + 0.5) / R)).rgb;
}


// ------------------------------------------------------------------------------------- the materials ---

// what both materials share per pixel: the shading inputs and the footprints (surfacing._surface_group_data's head)
function pixelInputs(pal) {
    const s = shadingInputs();
    const consts = { ...P.CONSTANTS, ...(pal.constants ?? {}) };
    const pix = Number(consts.pixel_angle || P.CONSTANTS.pixel_angle);
    const ndv = mabs(vdot(s.Ng, s.Vin));
    const vpix = mul(s.vd, pix);
    return { ...s, consts, ndv, vpix, fpRead: div(vpix, mmax(ndv, 0.05)), fp: div(vpix, mmax(ndv, 0.25)) };
}

const worldBlender = () => {
    const p = T.positionWorld;
    return T.vec3(p.x, p.z.negate(), p.y);
};

/** surfacing._surface_group_data: the per-texel material's graph of a palette over a terrain's surface data. Returns
 * { albedo, roughness, normal (Blender frame), specular, emission (a debug view's colour, or null), farUniform, D0,
 * info }. opts: THREE, R, prefer, log. */
async function surfaceGroupData(pal, sd, opts) {
    const { THREE, R, prefer = '2k' } = opts;
    const log = opts.log === undefined ? console.log : opts.log;
    const opt = pal.options;
    const layers = pal.layers;
    // opts.scans: scanArrays' result made elsewhere (a test's colour grid in place of a scan, check 2)
    const scans = opts.scans ?? await scanArrays(pal, { THREE, R, prefer, log });
    const sets = scans.sets;
    const { coords, Ng, Vin, vd, consts, ndv, vpix, fpRead, fp } = pixelInputs(pal);
    const aaOn = opt.specular_aa !== false;
    const lfp = aaOn ? aaFootprint(vpix, ndv) : null;          // the scans' mips (specular anti-aliasing)
    const detile = opt.detile || 'offset';
    const n3 = detile !== 'offset';
    const hexed = Boolean(opt.anti_tile) && (detile === 'rotate' || detile === 'hex');
    const weights = layerWeights(pal, sd, log);
    const tiles = layers.map((L) => Number(L.tile_m)).sort((a, b) => a - b);
    const dat = await Data.create(sd, dataNames(pal, weights), coords, fpRead, consts, { tileM: tiles[Math.floor(tiles.length / 2)],
        detailStrength: Number(opt.detail_strength ?? DETAIL_STRENGTH), THREE, R });
    const comp = new MaterialCompiler({ pos: coords, constants: pal.constants, noise3: n3, data: dat, fp });
    const nfz = dat.nField()[2];
    const Nm = dat.nMacro();
    const lut = await lutImage(pal, { THREE, R });
    const noise = (pos, scaleM, detail, roughness, seed) => (n3 ? noise3(pos, scaleM, detail, roughness, seed)
        : noise4(pos, 1.0 / Number(scaleM), detail, roughness, seed));
    const boxAny = layers.some((L) => L.projection === 'box');
    const sec = boxAny ? sectorFrames(dat, coords, Nm) : null;
    const rad = (d) => (d * Math.PI) / 180;
    const steep = boxAny ? smooth(Math.cos(rad(STEEP_DEG[0])), Math.cos(rad(STEEP_DEG[1])), nfz) : null;
    let steepFace = null;
    let strata = null;
    if (pal.strata && layers.some((L) => L.strata)) {
        const st = pal.strata;
        const img = await strataImage(st.column, { THREE, R, rows: Math.trunc(st.rows ?? 1), parting: Number(st.parting ?? 0.0),
            padM: Number(st.pad_m ?? 0.0), looks: Boolean(st.looks ?? false), relief: (Number(st.relief_m ?? 0.0) || 0.0) > 0.0 });
        strata = new Strata(comp, st, coords, img);
    }
    // the hex grids: one per lattice (a frame, a size, turned or not), shared by every layer read on it
    const plan = hexPlan(layers, hexed, opt);
    const grids = new Map();
    const grid = (frame, pos, size, turned) => {
        const key = `${frame}|${Math.round(size * 1e6) / 1e6}|${turned}`;
        if (!grids.has(key)) grids.set(key, hexGrid(pos, 1.0 / size, 7.1 + 13.7 * grids.size, turned));
        return grids.get(key);
    };
    const per = [];
    for (let i = 0; i < layers.length; i++) {
        const L = layers[i], S = sets[i];
        let cov = clamp01(comp.expr(P.parse(weights[i])));
        const box = L.projection === 'box';
        const [pHex, pRot, sHex, sRot] = plan[i];
        const g = { P: pHex > 0 ? grid('planar', coords, pHex, pRot) : null };
        if (box) for (const s of [0, 1]) g[`S${s}`] = sHex > 0 ? grid(`sector ${s}`, sec[s].P, sHex, sRot) : null;
        const lg = layerReads(L, S, i, opt, box, plan[i], { scans, coords, vd, g, sec, steep });
        let col = lg.col, h = lg.h, hs = lg.hs;
        const meanLin = S.stats.mean_albedo_linear.map(Number);
        const mean = meanLin.map((v) => Math.max(v, 1e-4));
        const contrast = Number(L.contrast ?? 1.0);
        const own = L.colour ? P.hexLinear(L.colour).map(Number) : null;
        const rp = (L.ramp && lut) ? lut.index[L.name] : undefined;
        let base = own;
        if (rp && rp.kind === 'colour') base = lutRead(lut, rp, comp.expr(P.parse(rp.t)));   // the ramp stands for `colour`
        const smix = L.strata === true ? 1.0 : Number(L.strata || 0);
        const prov = L.provenance ?? {};
        let bandRough = null;
        let target;
        if (smix > 0 && strata) {
            let [band, br] = strata.band(Number(L.strata_offset_m ?? 0.0));
            bandRough = br;
            const src = amount(prov.src);
            if (src > 0.0 && dat.has('src_strata')) {
                // debris takes the column at its source's stratigraphic height
                const [sb, sr] = strata.bandAt(dat.value('src_strata'));
                band = src >= 1.0 ? sb : mixv(src, band, sb);
                bandRough = src >= 1.0 ? sr : mixf(src, bandRough, sr);
            }
            target = (smix >= 1.0 || base === null) ? band : mixv(smix, base, band);
        } else {
            target = base;
        }
        let tintMult = null;
        if (rp && rp.kind === 'tint') {
            tintMult = vscale(lutRead(lut, rp, comp.expr(P.parse(rp.t))), Number(rp.gain));
            if (target !== null) {
                target = vmulv(target, tintMult);
                tintMult = null;
            }
        }
        const down = amount(prov.down);
        if (down > 0.0 && target !== null) {
            let cd = null, share = 1.0;
            if (dat.hasFamily('P')) {
                cd = dat.colour('P');
                share = dat.value('down_share');
            } else if (strata && dat.has('src_strata')) {
                cd = strata.bandAt(dat.value('src_strata'))[0];      // P deferred: the debris' own provenance
            }
            if (cd !== null) {
                const k = mul(mul(smooth(0.1, 1.5, comp.attr('deposit')), share), down);
                const pale = rgb3(prov.pale, 1.0);
                if (!(pale[0] === 1 && pale[1] === 1 && pale[2] === 1)) cd = vmulv(cd, pale);
                target = mixv(k, target, cd);
            }
        }
        if (target !== null) {
            // rescale from the scan's mean to the target, channel by channel: target (1 + c (scan / mean - 1))
            let rel = vmulv(col, mean.map((v) => 1.0 / v));
            if (contrast !== 1.0) rel = vadd(vscale(rel, contrast), [1.0 - contrast, 1.0 - contrast, 1.0 - contrast]);
            col = vmulv(rel, target);
        }
        if (tintMult !== null) col = vmulv(col, tintMult);
        if (L.tint !== null && L.tint !== undefined) col = vmulv(col, L.tint.slice(0, 3).map(Number));
        if (L.patina !== null && L.patina !== undefined && dat.has('fresh')) {
            // weathered rock against fresh: the patina where the face stands, the fresh gain where it fails
            col = vmulv(col, mixv(dat.value('fresh'), rgb3(L.patina), rgb3(L.fresh_gain, 1.0)));
        }
        let rough = mul(lg.rough, Number(L.roughness));
        if (bandRough !== null) rough = mul(rough, smix >= 1.0 ? bandRough : mixf(smix, 1.0, bandRough));
        const aa = aaOn ? aaConstants(S, L) : null;
        if (aa) rough = roughAa(rough, lfp, aa);              // the scan's normals its mips average away, as roughness
        let reliefRv = null, reliefLv = null;
        if (smix >= 1.0 && strata && L.relief !== false && strata.relief() !== null) {
            [reliefRv, reliefLv] = strata.relief();
            const shade = Number(pal.strata.relief_shade ?? 0.15);
            if (shade > 0.0) col = vscale(col, madd(reliefRv, shade, 1.0 - shade));
        }
        let nx = lg.nx, ny = lg.ny;
        const hsScan = hs;                                   // the scan's own soft height (mean 0.5): the overlay's
        let canopyBump = null;
        if (L.canopy) {
            const cn = canopyNodes(L.canopy, coords, i, vd);
            const crownM = Number(L.canopy.crown_m ?? 4.5);
            const fc = comp.fade(crownM);
            let ccol = cn.col;
            if (!isNum(fc)) {
                // finer than a few pixels the crowns read their mean (canopyMean: what the crowns drawn near average
                // to, their relief's shading included), times their clump's factor on it until the clumps are finer
                // than a pixel too
                const mc = await canopyMean(L.canopy, { R });
                let faded = [...mc];
                if (cn.cmod !== null) {
                    let k = div(cn.cmod, await canopyClumpMean(L.canopy, { R }));
                    const fcl = comp.fade(Number(L.canopy.clump_m));
                    if (!isNum(fcl)) k = mixf(fcl, 1.0, k);
                    faded = vscale(mc, k);
                }
                ccol = mixv(fc, faded, ccol);
            }
            let kf = cn.far;
            if (dat.has('canopy_far') && dat.has('canopy_expected')) {
                // the stand-in crowns cover what the instances leave to the material: off where trees stand
                kf = mul(kf, clamp01(div(dat.value('canopy_far'), mmax(dat.value('canopy_expected'), 0.02))));
            }
            col = mixv(kf, col, ccol);
            h = mixf(kf, h, cn.h);
            hs = mixf(kf, hs, cn.h);
            rough = mixf(kf, rough, 0.9);
            nx = mul(nx, sub(1.0, kf));
            ny = mul(ny, sub(1.0, kf));
            if (Number(L.canopy.height_m ?? 3.0) > 0) canopyBump = mul(mul(cn.bump, kf), fc);
            if (L.canopy.edge && !isNum(cov)) {
                const t = cn.rEdge;
                cov = mixf(kf, cov, smooth(sub(t, 0.05), add(t, 0.05), cov));
            }
        }
        patchList(L).forEach((pt, k) => {
            if (pt.from_ramp) return;                        // the ramp image draws it
            const amt = Number(pt.amount ?? 0.6);
            let pm;
            if (pt.scale_m === null || pt.scale_m === undefined) {
                pm = amt;
            } else {
                const det = Number(pt.detail ?? 3.0);
                const pn = noise(coords, Number(pt.scale_m), det, 0.55, 33.7 + 2.3 * i + 5.1 * k);
                pm = mul(fadedSmooth(comp, Number(pt.lo ?? 0.42), Number(pt.hi ?? 0.62), pn, Number(pt.scale_m), det), amt);
            }
            if (pt.where) pm = mul(pm, clamp01(comp.expr(P.parse(pt.where))));
            let ratio;
            if (pt.tint) {
                ratio = pt.tint.slice(0, 3).map(Number);
            } else {
                const ref = L.colour ? P.hexLinear(L.colour).map(Number) : mean;
                ratio = P.hexLinear(pt.colour).map((v, q) => v / Math.max(ref[q], 1e-4));
            }
            col = mixv(pm, col, vmulv(col, ratio));
        });
        if (L.streaks) {
            if (steepFace === null) steepFace = smooth(0.78, 0.5, nfz);
            const st = L.streaks.map(Number);
            const [width, amt] = st;
            const [lo, hi] = st.length >= 4 ? [st[2], st[3]] : [0.45, 0.68];
            const sv = vmulv(coords, [1.0 / width, 1.0 / width, 1.0 / (8.0 * width)]);
            const sn = noise(sv, 1.0, 3.0, 0.55, 19.7 + 3.3 * i);
            let dark = mul(mul(fadedSmooth(comp, lo, hi, sn, width, 3.0), amt), steepFace);
            if (L.streaks_where) dark = mul(dark, clamp01(comp.expr(P.parse(L.streaks_where))));
            col = vscale(col, sub(1.0, dark));
        }
        let reliefH = null;
        if (reliefRv !== null) {
            reliefH = reliefRv;
            const ld = L.ledges;
            if (ld) {
                const sc = Number(ld.scale_m ?? 5.0);
                const pn = noise(coords, sc, 3.0, 0.55, 51.3 + 3.1 * i);
                let pm = mul(mul(reliefLv, fadedSmooth(comp, Number(ld.lo ?? 0.38), Number(ld.hi ?? 0.6), pn, sc, 3.0)), Number(ld.amount ?? 0.75));
                if (ld.where) pm = mul(pm, clamp01(comp.expr(P.parse(ld.where))));
                col = mixv(pm, col, vmulv(col, ld.tint.slice(0, 3).map(Number)));
            }
        }
        if (Number(L.value ?? 1.0) !== 1.0) col = vscale(col, Number(L.value));
        col = vmin(vmax(col, [0.0, 0.0, 0.0]), [0.95, 0.95, 0.95]);
        const ripple = L.ripples ? ripples(coords, L.ripples, i, vd) : null;
        let bumpOwn = null;
        if (Number(L.bump_m) > 0 && (!box || S.stats.has_normal === false)) bumpOwn = Number(L.bump_m);   // no normal map
        per.push({ L, cov, col, h, hs, hsScan, nx, ny, pert: box ? lg.pert : null, rough, ao: lg.ao, box, ripple, canopyBump,
            relief: reliefH, bumpOwn, v: aa ? aa[0] : null });
    }

    // the overlay of the macro data and the scans' heights, the composite and the height blend
    const wn = blendWeights(comp, dat, sd, per, opt, (i) => noise(coords, 1.0 / 0.85, 3.0, 0.62, 11.1 + 7.3 * i));
    const wsum = (vals) => {
        let acc = null;
        vals.forEach((v, q) => {
            if (v === null || v === undefined) return;
            const term = mul(v, wn[q]);
            acc = acc === null ? term : add(acc, term);
        });
        return acc === null ? 0.0 : acc;
    };
    const wsumVec = (vals) => {
        let acc = null;
        vals.forEach((v, q) => {
            if (v === null || v === undefined) return;
            const term = vscale(v, wn[q]);
            acc = acc === null ? term : vadd(acc, term);
        });
        return acc;
    };
    let albedo = wsumVec(per.map((p) => p.col));
    let rough = wsum(per.map((p) => p.rough));
    if (Number(opt.ao) > 0) albedo = vscale(albedo, add(1.0 - Number(opt.ao), mul(wsum(per.map((p) => p.ao)), Number(opt.ao))));
    if (opt.tone) {
        const tv = comp.expr(P.parse(opt.tone));
        if (!isNum(tv)) albedo = vscale(albedo, mmin(mmax(add(tv, 1.0), 0.4), 1.6));
        else if (tv !== 0.0) albedo = vscale(albedo, Math.min(Math.max(1.0 + tv, 0.4), 1.6));
    }
    albedo = macro(coords, albedo, opt.macro ?? [], n3);
    if (lut && lut.index.satmap) {
        const si = lut.index.satmap;
        albedo = vmulv(albedo, vscale(lutRead(lut, si, comp.expr(P.parse(si.t))), Number(si.gain)));
    }
    if (Number(opt.damp) > 0 || opt.damp_where) {
        let dm = 0.0;
        if (Number(opt.damp) > 0) {
            const sc = Number(opt.damp_scale_m ?? 6.25);
            const dn = noise(coords, sc, 3.0, 0.6, 13.3);
            dm = mul(fadedSmooth(comp, 0.5, 0.68, dn, sc, 3.0), Number(opt.damp));
        }
        if (opt.damp_where) {
            const dw = clamp01(comp.expr(P.parse(opt.damp_where)));
            dm = (isNum(dm) && dm === 0.0) ? dw : mmax(dm, dw);
        }
        if (!(isNum(dm) && dm === 0.0)) {
            albedo = vscale(albedo, sub(1.0, mul(dm, 0.38)));
            rough = mul(rough, sub(1.0, mul(dm, 0.32)));
        }
    }

    // the far hand-off (SURFACING_DESIGN.md 3.7): past D0 the ground fades to its baked far colour C (x a faint grain
    // of the base layer's scan) over D0..1.5 D0 of view distance, never inside the hero windows
    const D0 = farDistance(pal, sd);
    const farUniform = T.uniform(D0);
    let wFar = null;
    if (dat.hasFamily('C')) {
        const cm = mainCell(sd);
        const fade = smooth(farUniform, farUniform.mul(1.5), vd);
        wFar = mul(fade, smooth(0.0, FAR_FADE_MAIN_CELLS * cm, dat.rd.heroOutside));
        const fcCol = vscale(dat.colour('C'), farGrain(layers[0], sets[0], coords, scans));
        albedo = mixv(wFar, albedo, fcCol);
        // C's roughness is the scans' own; past D0 every scan's normals have averaged flat, so it takes the layers'
        // normal variance by their weights
        let rc = dat.value('far_roughness');
        if (aaOn) rc = roughLost(rc, wsum(per.map((p) => p.v)));
        rough = mixf(wFar, rough, rc);
    } else if (log) {
        log(`[surfacing] ${pal.name}: no far colour in the data (no palette bake): no far hand-off`);
    }

    // normals: the macro normal, the planar reads' normal maps in its world-XY tangent frame, the sector reads' tilts
    // in their own frames, then the bumps
    const nxs = wsum(per.map((p) => p.nx)), nys = wsum(per.map((p) => p.ny));
    const dot = vdot(Nm, [1.0, 0.0, 0.0]);
    const Txy = vnorm(vsub([1.0, 0.0, 0.0], vscale(Nm, dot)));
    const Bxy = vcross(Nm, Txy);
    const nzs = msqrt(mmax(sub(sub(1.0, mul(nxs, nxs)), mul(nys, nys)), 0.0));
    let nvec = vadd(vadd(vscale(Txy, nxs), vscale(Bxy, nys)), vscale(Nm, nzs));
    const pert = wsumVec(per.map((p) => p.pert));
    if (pert !== null) nvec = vadd(nvec, pert);
    let normal = vnorm(nvec);
    const keep = wFar === null ? 1.0 : sub(1.0, wFar);
    // the beds in relief: an analytic tilt of the normal by the relief's slope along the stratigraphic height,
    // n' = normalize(n - k (up - (up . n) n)), k = weight x relief_m x d(relief)/d(zs)
    if (strata && per.some((p) => p.relief !== null)) {
        const [slope, up] = strata.reliefSlope();
        const k = mul(mul(mul(wsum(per.map((p) => (p.relief !== null ? 1.0 : null))), keep), strata.reliefM), slope);
        const sg = vsub(up, vscale(normal, vdot(normal, up)));
        normal = vnorm(vsub(normal, vscale(sg, k)));
    }
    // the bumps: ripples, canopy (and a scan without a normal map), each its own Bump with its weight (cheap
    // coverages: every weight with its noise at its mean, composited) and the far fade in its distance
    const cheap = new MaterialCompiler({ pos: coords, constants: pal.constants, noise3: true, flat: true, attrs: comp.attrs, data: dat });
    const bumped = per.map((p) => p.bumpOwn !== null || p.ripple !== null || p.canopyBump !== null);
    if (bumped.some(Boolean)) {
        const ccov = per.map((p, i) => ((bumped[i] || bumped.slice(0, i).some(Boolean)) ? clamp01(cheap.expr(P.parse(weights[i]))) : 0.0));
        const bw = new Array(per.length).fill(0.0);
        let crem = 1.0;
        for (let i = per.length - 1; i >= 0; i--) {
            bw[i] = bumped[i] ? mul(ccov[i], crem) : 0.0;
            crem = mul(crem, oneMinus(ccov[i]));
        }
        const Pw = worldBlender();
        per.forEach((p, i) => {
            const terms = [];
            if (p.bumpOwn !== null) terms.push([sub(p.h, 0.5), p.bumpOwn]);
            if (p.ripple !== null) terms.push([p.ripple, 1.0]);
            if (p.canopyBump !== null) terms.push([p.canopyBump, 1.0]);
            for (const [hgt, scale] of terms) {
                const dist = mul(mul(bw[i], keep), scale);
                if (isNum(dist) && dist === 0.0) continue;
                normal = bumpNode(normal, hgt, dist, Pw);
            }
        });
    }
    // a grazing pixel whose shading normal turns away from the camera is pulled toward the mesh's own normal
    const facing = smooth(0.0, 0.1, vdot(normal, Vin));
    normal = vnorm(mixv(facing, Ng, normal));
    if (opt.dusting) {
        // powder and ash on every ledge and grain the scans and the macro normal draw, by the final normal
        const du = opt.dusting;
        const [t0, t1] = (du.slope_deg ?? [25.0, 45.0]).map(Number);
        const nzf = sep(normal)[2];
        let dm = mul(smooth(Math.cos(rad(t1)), Math.cos(rad(t0)), nzf), Number(du.amount ?? 0.6));
        if (du.where) dm = mul(dm, clamp01(comp.expr(P.parse(du.where))));
        if (wFar !== null) dm = mul(dm, sub(1.0, wFar));
        albedo = mixv(dm, albedo, P.hexLinear(du.colour ?? '#f2f4f6').map(Number));
    }
    // each layer's own specular, past D0 as well
    const specs = per.map((p) => Number(p.L.specular ?? opt.specular));
    const specular = new Set(specs).size === 1 ? specs[0] : wsum(specs);
    albedo = vmin(albedo, [0.95, 0.95, 0.95]);
    const roughC = isNum(rough) ? rough : mmin(mmax(rough, 0.02), 1.0);
    let emission = null;
    const dbg = opt.debug;
    if (dbg) {
        if (dbg === 'weights') {
            const n = wn.length;
            emission = v3(wn[n - 1], n > 1 ? wn[n - 2] : 0.0, n > 2 ? wn[n - 3] : 0.0);
        } else if (dbg === 'layers') {
            emission = per.length > 1 ? wsumVec(per.map((p, i) => DEBUG_COLOURS[i % DEBUG_COLOURS.length])) : V3(DEBUG_COLOURS[0]);
        } else if (dbg === 'level') {
            const lvl = dat.rd.level;
            emission = v3(mfract(mul(lvl, 0.37)), mfract(mul(lvl, 0.61)), mfract(mul(lvl, 0.83)));
        } else {
            emission = V3(albedo);
        }
    }
    const nTex = countTextures(dat, scans, strata, lut);
    if (nTex > MAX_TEXTURES) {
        throw new Error(`palette ${pal.name}: with baked data its material samples ${nTex} textures; a WebGPU stage takes 16 ` +
            `by default, a lit scene's shadow map and environment two of them (${MAX_TEXTURES} with a margin): drop a layer ` +
            'or the strata relief');
    }
    return { albedo, roughness: roughC, normal, specular, emission, farUniform, D0, scans, dat,
        info: { palette: pal.name, sets: sets.map((s) => s.name), textures: nTex, hex: hexed, grids: grids.size,
            surfaceKey: String(sd.key), farM: D0 } };
}

// the textures a material samples: the data families it reads (the M families one array), the two scan arrays, the
// strata image and its relief, the LUT
function countTextures(dat, scans, strata, lut) {
    let n = 0;
    for (const f of Object.keys(dat.tex.fam)) if (dat._fam.has(f)) n++;
    if ([...dat._fam.keys()].some((f) => f.startsWith('M'))) n++;
    if (scans) n += 2;
    if (strata) n += strata.img.relief ? 2 : 1;
    if (lut) n++;
    return n;
}

/** surfacing.far_group: the far material's graph (SURFACING_DESIGN.md 3.7): the baked far colour C, the macro normal
 * from D, the base layer's faint grain, and the near material's specular and roughness there from the same layer
 * weights (each layer's coverage, overlay, composite and blend, its scan at its mean height). A cost saving only:
 * what the near material shows past 1.5 D0, for rings beyond that from every camera. The weights read the maps
 * through the packing the near material made (applySurface builds it first). */
async function farGroupData(pal, sd, opts) {
    const { THREE, R, prefer = '2k' } = opts;
    const opt = pal.options;
    const layers = pal.layers;
    const scans = await scanArrays(pal, { THREE, R, prefer, log: opts.log });
    const sets = scans.sets;
    const { coords, Ng, Vin, consts, fpRead, fp } = pixelInputs(pal);
    const tiles = layers.map((L) => Number(L.tile_m)).sort((a, b) => a - b);
    const weights = layerWeights(pal, sd, null);
    const names = new Set();
    for (const w of weights) for (const n of P.namesIn(w)) names.add(n);
    if (names.has('slope_20m')) { names.add('n20_x'); names.add('n20_y'); }
    const dat = await Data.create(sd, names, coords, fpRead, consts, { tileM: tiles[Math.floor(tiles.length / 2)],
        detailStrength: Number(opt.detail_strength ?? DETAIL_STRENGTH), cubic: false, THREE, R });
    if (!dat.hasFamily('C')) throw new Error('far material: the surface data has no far colour (bake it with a palette)');
    const comp = new MaterialCompiler({ pos: coords, constants: pal.constants, noise3: (opt.detile || 'offset') !== 'offset', data: dat, fp });
    const per = layers.map((L, q) => ({ L, cov: clamp01(comp.expr(P.parse(weights[q]))), hsScan: 0.5, hs: 0.5 }));
    const wn = blendWeights(comp, dat, sd, per, opt);
    const wsum = (vals) => {
        let acc = null;
        vals.forEach((v, q) => {
            if (v === null || v === undefined) return;
            const term = mul(v, wn[q]);
            acc = acc === null ? term : add(acc, term);
        });
        return acc === null ? 0.0 : acc;
    };
    let normal = dat.nMacro();
    const facing = smooth(0.0, 0.1, vdot(normal, Vin));
    normal = vnorm(mixv(facing, Ng, normal));
    const albedo = vmin(vscale(dat.colour('C'), farGrain(layers[0], sets[0], coords, scans)), [0.95, 0.95, 0.95]);
    let rc = dat.value('far_roughness');
    if (opt.specular_aa !== false) rc = roughLost(rc, wsum(sets.map((S, q) => aaConstants(S, layers[q])?.[0] ?? null)));
    const roughness = mmin(mmax(rc, 0.02), 1.0);
    const specs = layers.map((L) => Number(L.specular ?? opt.specular));
    const specular = new Set(specs).size === 1 ? specs[0] : wsum(specs);
    return { albedo, roughness, normal, specular, emission: null, scans, dat,
        info: { palette: pal.name, far: true, textures: countTextures(dat, scans, null, null), surfaceKey: String(sd.key) } };
}

// a NodeMaterial of a graph: Blender's Principled BSDF (base colour, roughness, normal, its Specular IOR Level as
// the IOR that gives its F0, module doc), or an unlit debug view
function nodeMaterial(THREE, gr, name) {
    if (gr.emission) {
        const m = new THREE.MeshBasicNodeMaterial();
        m.colorNode = T.vec4(V3(gr.emission), 1.0);
        m.name = name;
        return m;
    }
    const m = new THREE.MeshPhysicalNodeMaterial({ metalness: 0.0, roughness: 1.0 });
    m.colorNode = T.vec4(V3(gr.albedo), 1.0);
    m.roughnessNode = F(gr.roughness);
    m.metalnessNode = T.float(0.0);
    m.normalNode = toViewNormal(gr.normal);
    const s = gr.specular;
    if (isNum(s) && s <= 0.0) {
        m.specularIntensity = 0.0;
    } else {
        const f0 = mul(0.08, s);
        const r = msqrt(f0);
        m.iorNode = F(div(add(1.0, r), mmax(sub(1.0, r), 1e-4)));
        m.specularIntensity = 1.0;
    }
    m.name = name;
    return m;
}


// -------------------------------------------------------------------------------------------- the calls ---

/** palette null: grey clay, albedo 0.18, roughness 0.9, no specular (the reference rig's; surfacing.clay_material).
 * A NodeMaterial. */
export function clayMaterial(THREE, name = 'terrain_clay') {
    const m = new THREE.MeshPhysicalNodeMaterial({ roughness: 0.9, metalness: 0.0 });
    m.color.setRGB(CLAY_ALBEDO, CLAY_ALBEDO, CLAY_ALBEDO);
    m.specularIntensity = 0.0;
    m.name = name;
    m.userData.eidoPalette = 'clay';
    return m;
}

/** The terrain constants (palettes CONSTANTS) of a terrain: its base elevation, and its snowline and treeline (its
 * knobs, its recipe's mask parameters, or its real place's, palettes PLACES). {} for anything else
 * (surfacing.terrain_constants, from the Terrain's own record where Blender reads the object's eido_terrain). */
export function terrainConstants(t) {
    const info = t?.mesh?.userData?.eidoTerrain ?? (t?.info ? { ...t.info, recipe: t.recipe?.toDict?.() ?? t.info.recipe, knobs: t.knobs } : null);
    if (!info) return {};
    const out = {};
    if (info.base_elevation_m !== null && info.base_elevation_m !== undefined) out.base_elevation_m = Number(info.base_elevation_m);
    const knobs = info.knobs ?? t?.knobs ?? {};
    const mp = {};
    const rec = info.recipe ?? {};
    const dfl = rec && typeof rec === 'object' ? rec.defaults : null;
    if (dfl && typeof dfl === 'object') Object.assign(mp, dfl.mask_params ?? {});
    const dem = knobs.dem;
    if (typeof dem === 'string' && dem in P.PLACES) Object.assign(mp, P.PLACES[dem].mask_params ?? {});
    for (const key of ['snowline_m', 'treeline_m']) {
        if (knobs[key] !== null && knobs[key] !== undefined) mp[key] = knobs[key];
        if (mp[key] !== null && mp[key] !== undefined) out[key] = Number(mp[key]);
    }
    return out;
}

/** The filled-in palette surfaceMaterial builds: palette (name, 'auto', object) with a strata override (a column
 * name, a column, or a strata object merged over the palette's), material options and terrain constants merged in
 * (surfacing.resolve). */
export function resolve(palette = 'auto', recipe = null, strata = null, options = null, constants = null) {
    const pal = P.get(palette, recipe);
    if (strata !== null && strata !== undefined) {
        if (typeof strata === 'object' && !Array.isArray(strata) && ('column' in strata || 'faults' in strata || 'source' in strata)) {
            pal.strata = { ...(pal.strata ?? {}), ...strata };
        } else {
            pal.strata = { ...(pal.strata ?? { source: 'attribute' }), column: strata };
        }
        for (const [k, v] of Object.entries(P.STRATA_DEFAULTS)) if (!(k in pal.strata)) pal.strata[k] = structuredClone(v);
    }
    if (options) Object.assign(pal.options, options);
    if (constants) {
        for (const [k, v] of Object.entries(constants)) if (k in P.CONSTANTS && v !== null && v !== undefined) pal.constants[k] = Number(v);
    }
    const problems = P.check(pal);
    if (problems.length) throw new Error(`palette ${pal.name}: ${problems.join('; ')}`);
    return pal;
}

async function threeOf(opts) {
    const THREE = opts.THREE ?? await import('three/webgpu');
    const R = opts.R ?? await (await import('../core/gpu.js')).init({ renderer: opts.renderer ?? null });
    await tslModule(opts);
    return { THREE, R };
}

/** A NodeMaterial for a terrain's ground (surfacing.surface_material); palette null gives clayMaterial().
 *   palette    a name (palettes names()), 'auto' (the recipe's), or a palette object
 *   opts       recipe (for 'auto'), strata (the rock column: a column name, a column, or a strata object), options
 *              (material options over the palette's: detile, detail_strength, far_m, overlay, dusting, debug
 *              ('weights' | 'layers' | 'level' | 'albedo'), hex_m, hex_rotate, steep_hex_m, steep_rotate,
 *              steep_hex_share, specular_aa: surfacing.py's), constants (terrain constants over the palette's),
 *              data (the terrain's SurfaceData: required, the port's mesh carries no mask attributes), name, prefer
 *              (the scans' resolution, '2k'), log, THREE, R, TSL
 * The material's userData: eidoPalette, eidoSets, eidoTextures, eidoSurfaceKey, eidoFarM, eidoFarUniform. */
export async function surfaceMaterial(palette = 'auto', opts = {}) {
    const { THREE, R } = await threeOf(opts);
    const name = opts.name ?? 'terrain_ground';
    if (palette === null) return clayMaterial(THREE, name);
    if (!opts.data) {
        throw new Error('surfaceMaterial: the per-texel material needs the terrain\'s surface data (data: bakeSurface(t)); ' +
            'the material without baked data reads the masks as mesh attributes, which this edition\'s mesh does not carry');
    }
    const t0 = performance.now();
    const pal = resolve(palette, opts.recipe ?? null, opts.strata ?? null, opts.options ?? null, opts.constants ?? null);
    const gr = await surfaceGroupData(pal, opts.data, { THREE, R, prefer: opts.prefer, log: opts.log, scans: opts.scans });
    const m = nodeMaterial(THREE, gr, name);
    Object.assign(m.userData, { eidoPalette: pal.name, eidoSets: gr.info.sets, eidoTextures: gr.info.textures,
        eidoSurfaceKey: gr.info.surfaceKey, eidoFarM: gr.D0, eidoFarUniform: gr.farUniform, eidoHex: gr.info.hex,
        eidoBuildS: +((performance.now() - t0) / 1000).toFixed(2), eidoConstants: pal.constants });
    const log = opts.log === undefined ? console.log : opts.log;
    if (log) {
        log(`[surfacing] ${pal.name} (baked data ${String(opts.data.key).slice(0, 10)}): ${pal.layers.length} layers, ` +
            `${gr.info.textures} textures, ${gr.info.grids} hex grids, in ${m.userData.eidoBuildS} s; far hand-off at ${gr.D0.toFixed(0)} m`);
    }
    return m;
}

/** The far material of a terrain with baked data (material slot 1: its far colour C, the macro normal, a faint grain;
 * SURFACING_DESIGN.md 3.7). applySurface(cameras) gives it to the rings beyond 1.5 D0 of every camera. */
export async function farMaterial(palette = 'auto', opts = {}) {
    const { THREE, R } = await threeOf(opts);
    if (!opts.data) throw new Error('farMaterial needs the terrain\'s surface data (data:)');
    const t0 = performance.now();
    const pal = resolve(palette, opts.recipe ?? null, opts.strata ?? null, opts.options ?? null, opts.constants ?? null);
    const gr = await farGroupData(pal, opts.data, { THREE, R, prefer: opts.prefer, log: opts.log });
    const m = nodeMaterial(THREE, gr, opts.name ?? 'terrain_far');
    Object.assign(m.userData, { eidoPalette: pal.name, eidoFar: true, eidoTextures: gr.info.textures,
        eidoSurfaceKey: gr.info.surfaceKey, eidoBuildS: +((performance.now() - t0) / 1000).toFixed(2) });
    const log = opts.log === undefined ? console.log : opts.log;
    if (log) log(`[surfacing] ${pal.name} far material: ${gr.info.textures} textures in ${m.userData.eidoBuildS} s`);
    return m;
}

/** [N, 2] Blender (x, y) of camera positions: Object3Ds (their world position), three.js [x, z] or [x, y, z] points,
 * or arrays of them (points along a camera path) (surfacing._camera_points; three.js axes in, plan 2.2). */
export function cameraPoints(cameras) {
    const pts = [];
    const one = (c) => {
        if (c && typeof c === 'object' && c.isObject3D) {
            c.updateMatrixWorld?.(true);
            const e = c.matrixWorld.elements;
            pts.push([e[12], -e[14]]);
        } else if (Array.isArray(c) && c.length && Array.isArray(c[0])) {
            for (const r of c) one(r);
        } else if (Array.isArray(c) || ArrayBuffer.isView(c)) {
            pts.push(c.length >= 3 ? [Number(c[0]), -Number(c[2])] : [Number(c[0]), -Number(c[1])]);
        } else if (c && typeof c === 'object' && 'x' in c) {
            pts.push([Number(c.x), -Number(c.z ?? 0)]);
        }
    };
    for (const c of cameras ?? []) one(c);
    return pts;
}

/** The rings of a terrain that lie beyond 1.5 D0 (horizontal metres) from every camera point: those the far material
 * may draw (surfacing.far_rings). D0: farM, else the palette's farDistance. No cameras, no rings. */
export function farRings(t, data, cameras, farM = null, palette = null) {
    const pts = cameraPoints(cameras);
    if (!pts.length) return [];
    if (farM === null || farM === undefined) farM = farDistance(P.get(palette ?? 'auto'), data);
    const lim = 1.5 * Number(farM);
    const out = [];
    for (const r of t.ring.ringTable()) {
        const [x0, y0, x1, y1] = r.window;
        let dmin = Infinity;
        for (const [px, py] of pts) {
            const dx = Math.max(Math.max(x0 - px, px - x1), 0.0), dy = Math.max(Math.max(y0 - py, py - y1), 0.0);
            let d = Math.hypot(dx, dy);
            if (r.hole) {
                const [hx0, hy0, hx1, hy1] = r.hole;
                if (px > hx0 && px < hx1 && py > hy0 && py < hy1) d = Math.min(Math.min(px - hx0, hx1 - px), Math.min(py - hy0, hy1 - py));
            }
            dmin = Math.min(dmin, d);
        }
        if (dmin > lim) out.push(Math.trunc(r.ring));
    }
    return out;
}

// material slot 1 on the geometry groups of these rings (the far material), 0 elsewhere (surfacing._set_far_rings)
function setFarRings(t, rings) {
    const g = t.mesh.geometry;
    const table = t.ring.ringTable();
    const far = new Set(rings);
    let n = 0;
    g.groups.forEach((gr, k) => {
        const row = k < table.length ? table[k] : null;
        const isFar = row !== null && far.has(row.ring);
        gr.materialIndex = isFar ? 1 : 0;
        if (isFar) n += gr.count / 3;
    });
    return n;
}

/** surfaceMaterial on a terrain's mesh (surfacing.apply_surface): t.mesh.material becomes [near, far] (the far slot
 * the near material again unless a camera leaves rings beyond 1.5 D0), with the terrain's own constants
 * (terrainConstants) under any given. opts as surfaceMaterial's, plus cameras: Object3Ds, three.js points or arrays
 * of points along a camera path; rings beyond 1.5 D0 of all of them take the far material (slot 1). None: every ring
 * the near material, which hands off to the same far colour by itself past D0. Returns the near material. */
export async function applySurface(t, palette = 'auto', opts = {}) {
    const consts = { ...terrainConstants(t), ...(opts.constants ?? {}) };
    const name = opts.name ?? `${t.mesh?.name ?? 'terrain'}_ground`;
    const near = await surfaceMaterial(palette, { ...opts, constants: consts, name, recipe: opts.recipe ?? t.recipe });
    let far = near;
    if (palette !== null && opts.data) {
        const rings = opts.cameras ? farRings(t, opts.data, opts.cameras, near.userData.eidoFarM) : [];
        if (rings.length && opts.data.families().includes('C')) {
            far = await farMaterial(palette, { ...opts, constants: consts, name: name.replace(/_ground$/, '') + '_far', recipe: opts.recipe ?? t.recipe });
            const n = setFarRings(t, rings);
            const log = opts.log === undefined ? console.log : opts.log;
            if (log) log(`[surfacing] ${t.mesh.name}: rings ${JSON.stringify(rings)} (${n.toLocaleString('en-US')} triangles) beyond ` +
                `${(1.5 * near.userData.eidoFarM).toFixed(0)} m of every camera take the far material`);
        } else {
            setFarRings(t, []);
        }
    }
    for (const m of Array.isArray(t.mesh.material) ? t.mesh.material : [t.mesh.material]) {
        if (m && m !== near && m !== far && m.userData?.eidoPalette === 'clay') m.dispose?.();
    }
    t.mesh.material = [near, far];
    return near;
}

// ------------------------------------------------------------------------------ the masks as attributes ---

/** [[attribute name, [mask, ...]], ...]: a set of mask names, sorted, three to a vec3 attribute named
 * eido_pk<hash>_<k> by the set (surfacing.mask_packs; the attribute path's, for a mesh that carries masks: this
 * edition's ring mesh carries none unless makeTerrain's debug option meshMasks adds them). */
export function maskPacks(names) {
    const sorted = [...names].sort();
    const h = createHashSync(sorted.join(','));
    const out = [];
    for (let k = 0; k < Math.ceil(sorted.length / 3); k++) out.push([`eido_pk${h.slice(0, 6)}_${k}`, sorted.slice(3 * k, 3 * k + 3)]);
    return out;
}

/** The masks a palette (a name or object) or a list of names reads that the terrain's mesh does not carry as
 * eido_<name> (surfacing.missing_masks). */
export function missingMasks(t, paletteOrNames) {
    const names = (typeof paletteOrNames === 'string' || (paletteOrNames && !Array.isArray(paletteOrNames) && paletteOrNames.layers))
        ? [...P.masksUsed(P.get(paletteOrNames))] : [...paletteOrNames].map(String);
    const geo = t.mesh?.geometry ?? t.geometry ?? null;
    const have = new Set(geo ? Object.keys(geo.attributes) : []);
    return names.filter((n) => !have.has('eido_' + n)).sort();
}

// a SHA-1 hex digest of a string, synchronous (node's crypto, as surface/far_colour.js uses it)
function createHashSync(s) {
    return createHash('sha1').update(s).digest('hex');
}


// ------------------------------------------------------------------------------------- packing the scans ---
// surfacing.py's pack_set over the shared texture library (terrain/_pbr.py's find_set: CC0 sets fetched by
// fetch_texture.py --cache into eidoverse/assets/cache/textures/<SET>_<res>/, never committed). Per texel on the GPU:
// the channels (kernels below), the height's mean and spread (core/prims.js sums), the PNGs' rows (core/io.js
// encodePng: the Up filter on the GPU, deflate by CompressionStream); the stats in JavaScript.

const ROLES = {
    color: ['_Color', '_diff', '_diffuse', '_albedo', '_basecolor', '_col'],
    normal: ['_NormalGL', '_normal', '_nor_gl'],
    roughness: ['_Roughness', '_rough', '_roughness'],
    ao: ['_AmbientOcclusion', '_ao'],
    displacement: ['_Displacement', '_displacement', '_disp', '_height'],
    arm: ['_arm'],
    metalness: ['_Metalness', '_metal', '_metallic'],
};
const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.exr', '.tif', '.tiff'];
const isDir = (p) => {
    try {
        return Deno.statSync(p).isDirectory;
    } catch (_e) {
        return false;
    }
};
const exists = (p) => {
    try {
        Deno.statSync(p);
        return true;
    } catch (_e) {
        return false;
    }
};
const repoRoot = () => decodeURIComponent(new URL('../../../', import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1').replace(/\/+$/, '');

/** Where the texture library is looked for, in order (_pbr.texture_roots): this checkout's
 * eidoverse/assets/cache/textures, $EIDO_TEXTURE_CACHE, $EIDO_ASSET_CACHE/textures, then the main checkout's when this
 * one is a git worktree (read only). Only the folders that exist. */
export function textureRoots() {
    const root = repoRoot();
    const roots = [`${root}/eidoverse/assets/cache/textures`];
    const e1 = Deno.env.get('EIDO_TEXTURE_CACHE');
    if (e1) roots.push(e1.replace(/\\/g, '/'));
    const e2 = Deno.env.get('EIDO_ASSET_CACHE');
    if (e2) roots.push(`${e2.replace(/\\/g, '/')}/textures`);
    try {
        const git = `${root}/.git`;
        if (Deno.statSync(git).isFile) {
            const line = Deno.readTextFileSync(git).trim();
            if (line.startsWith('gitdir:')) {
                let gd = line.slice('gitdir:'.length).trim().replace(/\\/g, '/');
                if (!/^([A-Za-z]:)?\//.test(gd)) gd = `${root}/${gd}`;
                const parts = gd.replace(/\/+$/, '').split('/');
                roots.push(`${parts.slice(0, -3).join('/')}/eidoverse/assets/cache/textures`);
            }
        }
    } catch (_e) { /* not a worktree */ }
    return roots.filter(isDir);
}

function resRank(name, prefer) {
    const order = [prefer, '2k', '4k', '1k', '8k'];
    for (let i = 0; i < order.length; i++) if (name.toLowerCase().endsWith('_' + order[i])) return i;
    return order.length;
}

/** A texture set: 'Ground106' (the best resolution, 2k first) or 'Ground106_2k' (_pbr.find_set): { name, dir, role:
 * path, ... } for the roles found, or throws naming where it looked. */
export function findSet(name, prefer = '2k') {
    const roots = textureRoots();
    let cands = [];
    for (const r of roots) {
        if (isDir(`${r}/${name}`)) {
            cands.push(`${r}/${name}`);
            break;
        }
        for (const e of Deno.readDirSync(r)) {
            if (e.isDirectory && e.name.toLowerCase().startsWith(name.toLowerCase() + '_')) cands.push(`${r}/${e.name}`);
        }
        if (cands.length) break;
    }
    if (!cands.length) throw new Error(`texture set '${name}' not found in ${JSON.stringify(roots)} (fetch it with fetch_texture.py ${name} 2k --cache)`);
    cands = cands.map((d) => [resRank(d.split('/').pop(), prefer), d]).sort((a, b) => a[0] - b[0]);
    const d = cands[0][1];
    const files = [...Deno.readDirSync(d)].filter((e) => e.isFile && IMAGE_EXTS.some((x) => e.name.toLowerCase().endsWith(x)))
        .map((e) => e.name).sort();
    const out = { name: d.split('/').pop(), dir: d };
    for (const [role, sufs] of Object.entries(ROLES)) {
        for (const suf of sufs) {
            const hit = files.filter((f) => {
                const stem = f.replace(/\.[^.]*$/, '').toLowerCase();
                return stem.endsWith(suf.toLowerCase()) && !stem.endsWith('normaldx');
            });
            if (hit.length) {
                out[role] = `${d}/${hit[0]}`;
                break;
            }
        }
    }
    return out;
}

// one source image as samples on the GPU: { field (H x W x 4, 0..1: a byte / 255, a 16-bit sample / 65535), w, h }
async function imageField(R, path) {
    const im = await readImage(path);
    const { width: w, height: h, channels: c, bits } = im;
    const bytes = new Uint8Array(im.data.buffer, im.data.byteOffset, im.data.byteLength);
    const words = new Uint32Array(Math.ceil(bytes.length / 4));
    new Uint8Array(words.buffer).set(bytes);
    const src = R.field(1, words.length, 1, words, 'u32');
    const out = R.field(h, w, 4);
    R.run(R.kernel('surfacing_unpack_image', UNPACK_IMAGE), { src }, { outF: out }, { uSize: [w, h], uChannels: c, uBits: bits });
    src.destroy();
    return { field: out, w, h };
}

const UNPACK_IMAGE = `//! sampler src r32ui
//! image outF rgba32f
//! uniform ivec2 uSize
//! uniform int uChannels
//! uniform int uBits
fn byte_at(o: u32) -> u32 { return (src_b[o >> 2u] >> ((o & 3u) * 8u)) & 0xFFu; }
fn sample(px: u32, c: u32, chan: u32) -> f32 {
  if (u.uBits == 16) {
    let o = (px * c + chan) * 2u;
    return f32(byte_at(o) | (byte_at(o + 1u) << 8u)) / 65535.0;
  }
  return f32(byte_at(px * c + chan)) / 255.0;
}
fn kmain(p: vec2<i32>) {
  if (p.x >= u.uSize.x || p.y >= u.uSize.y) { return; }
  let c = u32(u.uChannels);
  let px = u32(p.y * u.uSize.x + p.x);
  var v = vec4<f32>(0.0, 0.0, 0.0, 1.0);
  if (c <= 2u) {
    // grey (and alpha): Blender's grey image reads as grey RGB
    let g = sample(px, c, 0u);
    v = vec4<f32>(g, g, g, 1.0);
    if (c == 2u) { v.w = sample(px, c, 1u); }
  } else {
    v = vec4<f32>(sample(px, c, 0u), sample(px, c, 1u), sample(px, c, 2u), 1.0);
    if (c == 4u) { v.w = sample(px, c, 3u); }
  }
  outF_store(p, v);
}
`;

// the packed images' samples from the source maps (surfacing.pack_set's arrays): A (albedo RGB as stored, the height
// normalised to mean 0.5 std 0.15) and B (the normal's x, y, roughness, AO), each a u32 sample a channel (h x 4 w,
// the PNG's rows top first), as Blender's byte images store a float: (uchar)(255 f + 0.5), clamped; and the linear
// albedo, roughness and AO per texel for their means. Each map is fitted to the colour's size, nearest
// (surfacing._fit). uHas: normal, roughness, ao, displacement, arm (1 / 0).
const PACK = `//! sampler col
//! sampler nrm
//! sampler rgh
//! sampler aom
//! sampler dsp
//! sampler arm
//! image outA r32ui
//! image outB r32ui
//! image outL rgba32f
//! uniform ivec2 uSize
//! uniform ivec4 uHas
//! uniform int uArm
//! uniform vec2 uHeight
fn at_fit(which: i32, p: vec2<i32>) -> vec4<f32> {
  let W = u.uSize.x;
  let H = u.uSize.y;
  if (which == 0) { let s = nrm_size(); return nrm_at(vec2<i32>(p.x * s.x / W, p.y * s.y / H)); }
  if (which == 1) { let s = rgh_size(); return rgh_at(vec2<i32>(p.x * s.x / W, p.y * s.y / H)); }
  if (which == 2) { let s = aom_size(); return aom_at(vec2<i32>(p.x * s.x / W, p.y * s.y / H)); }
  if (which == 3) { let s = dsp_size(); return dsp_at(vec2<i32>(p.x * s.x / W, p.y * s.y / H)); }
  let s = arm_size();
  return arm_at(vec2<i32>(p.x * s.x / W, p.y * s.y / H));
}
fn byte(f: f32) -> u32 {
  if (f <= 0.0) { return 0u; }
  if (f > 1.0 - 0.5 / 255.0) { return 255u; }
  return u32(255.0 * f + 0.5);
}
fn lin(c: f32) -> f32 {
  if (c <= 0.04045) { return c / 12.92; }
  return pow((c + 0.055) / 1.055, 2.4);
}
fn kmain(p: vec2<i32>) {
  if (p.x >= u.uSize.x || p.y >= u.uSize.y) { return; }
  let rgb = col_at(p).xyz;
  var n = vec2<f32>(0.5, 0.5);
  if (u.uHas.x == 1) { n = at_fit(0, p).xy; }
  var r = 0.8;
  var a = 1.0;
  if (u.uHas.y == 1) { r = at_fit(1, p).x; } else if (u.uArm == 1) { r = at_fit(4, p).y; }
  if (u.uHas.z == 1) { a = at_fit(2, p).x; } else if (u.uArm == 1) { a = at_fit(4, p).x; }
  var hn = 0.5;
  if (u.uHas.w == 1) { hn = 0.5 + 0.15 * (at_fit(3, p).x - u.uHeight.x) / u.uHeight.y; }
  outA_store(vec2<i32>(p.x * 4, p.y), byte(clamp(rgb.x, 0.0, 1.0)));
  outA_store(vec2<i32>(p.x * 4 + 1, p.y), byte(clamp(rgb.y, 0.0, 1.0)));
  outA_store(vec2<i32>(p.x * 4 + 2, p.y), byte(clamp(rgb.z, 0.0, 1.0)));
  outA_store(vec2<i32>(p.x * 4 + 3, p.y), byte(clamp(hn, 0.0, 1.0)));
  outB_store(vec2<i32>(p.x * 4, p.y), byte(clamp(n.x, 0.0, 1.0)));
  outB_store(vec2<i32>(p.x * 4 + 1, p.y), byte(clamp(n.y, 0.0, 1.0)));
  outB_store(vec2<i32>(p.x * 4 + 2, p.y), byte(clamp(r, 0.0, 1.0)));
  outB_store(vec2<i32>(p.x * 4 + 3, p.y), byte(clamp(a, 0.0, 1.0)));
  let c = clamp(rgb, vec3<f32>(0.0), vec3<f32>(1.0));
  outL_store(p, vec4<f32>(lin(c.x), lin(c.y), lin(c.z), 0.0));
}
`;

// the displacement's squared deviation from its mean, for the spread (numpy's two-pass std)
const DEV2 = `//! sampler dsp
//! image outF r32f
//! uniform ivec2 uSize
//! uniform float uMean
fn kmain(p: vec2<i32>) {
  if (p.x >= u.uSize.x || p.y >= u.uSize.y) { return; }
  let s = dsp_size();
  let d = dsp_at(vec2<i32>(p.x * s.x / u.uSize.x, p.y * s.y / u.uSize.y)).x - u.uMean;
  outF_store(p, vec4<f32>(d * d, 0.0, 0.0, 0.0));
}
`;

/** Pack a scan set into albedo_height.png and normal_rough_ao.png (+ stats.json) in the cache, once
 * (surfacing.pack_set). Returns the folder. Missing maps fall back: roughness from the ARM map's G, else 0.8; AO
 * from ARM's R, else 1; a missing height map packs as a flat 0.5. opts: force, log, R. Float (EXR) colour maps are
 * not read here (Deno's decoder reads PNG and JPEG): such a set raises. */
export async function packSet(name, prefer = '2k', opts = {}) {
    const log = opts.log === undefined ? console.log : opts.log;
    const src = findSet(name, prefer);
    const d = `${cacheRoot()}/${src.name}_v${PACK_VERSION}`;
    const aPath = `${d}/albedo_height.png`, bPath = `${d}/normal_rough_ao.png`, sPath = `${d}/stats.json`;
    const roles = ['color', 'normal', 'roughness', 'ao', 'displacement', 'arm'].filter((r) => r in src);
    const newest = Math.max(...roles.map((r) => Deno.statSync(src[r]).mtime?.getTime() ?? 0));
    if (!opts.force && exists(aPath) && exists(bPath) && exists(sPath)
        && Math.min(Deno.statSync(aPath).mtime.getTime(), Deno.statSync(bPath).mtime.getTime()) >= newest) return d;
    if (!('color' in src)) throw new Error(`texture set ${src.name} has no colour map in ${src.dir}`);
    if (/\.(exr|tiff?)$/i.test(src.color)) throw new Error(`texture set ${src.name}: its colour map is a float image (${src.color}); this edition decodes PNG and JPEG`);
    const t0 = performance.now();
    const R = opts.R ?? await (await import('../core/gpu.js')).init();
    const { prims } = await import('../core/prims.js');
    const PR = prims(R);
    Deno.mkdirSync(d, { recursive: true });
    const tm = {};
    let tl = performance.now();
    const lap = (k) => { const n = performance.now(); tm[k] = +((n - tl) / 1000).toFixed(2); tl = n; };
    const col = await imageField(R, src.color);
    const W = col.w, H = col.h;
    const stand = R.field(1, 1, 4, new Float32Array([0.5, 0.5, 0.5, 1.0]));
    const maps = {};
    for (const r of ['normal', 'roughness', 'ao', 'displacement', 'arm']) maps[r] = r in src ? (await imageField(R, src[r])).field : null;
    lap('decode');
    // the height's mean and spread over the fitted displacement (numpy's float64 mean and two-pass std; float32 sums
    // in a fixed tree here)
    let hm = 0.5, hs = 0.0;
    if (maps.displacement) {
        const fitted = R.field(H, W, 4), dev = R.field(H, W, 1);
        R.run(R.kernel('surfacing_fit_dsp', FIT_DSP), { dsp: maps.displacement }, { outF: fitted }, { uSize: [W, H] });
        hm = (await PR.stats(fitted, { channel: 0 })).mean;
        R.run(R.kernel('surfacing_dev2', DEV2), { dsp: maps.displacement }, { outF: dev }, { uSize: [W, H], uMean: f32(hm) });
        hs = Math.max(Math.sqrt((await PR.stats(dev, { channel: 0 })).mean), 1e-3);
        fitted.destroy();
        dev.destroy();
    }
    lap('height');
    const outA = R.field(H, 4 * W, 1, null, 'u32'), outB = R.field(H, 4 * W, 1, null, 'u32'), outL = R.field(H, W, 4);
    R.run(R.kernel('surfacing_pack', PACK), { col: col.field, nrm: maps.normal ?? stand, rgh: maps.roughness ?? stand,
        aom: maps.ao ?? stand, dsp: maps.displacement ?? stand, arm: maps.arm ?? stand }, { outA, outB, outL },
    { uSize: [W, H], uHas: [maps.normal ? 1 : 0, maps.roughness ? 1 : 0, maps.ao ? 1 : 0, maps.displacement ? 1 : 0],
        uArm: maps.arm ? 1 : 0, uHeight: [f32(hm), f32(hs)] });
    const Io = await import('../core/io.js');
    const tmpA = `${d}/albedo_height.${Deno.pid}.tmp.png`, tmpB = `${d}/normal_rough_ao.${Deno.pid}.tmp.png`;
    await Io.writePng(tmpA, { field: outA, width: W, height: H, channels: 4, bitDepth: 8 });
    await Io.writePng(tmpB, { field: outB, width: W, height: H, channels: 4, bitDepth: 8 });
    Deno.renameSync(tmpA, aPath);
    Deno.renameSync(tmpB, bPath);
    lap('png');
    // the stats: means over the texels (numpy's float32 means; float32 sums in a fixed tree here)
    const lin = [];
    for (let c = 0; c < 3; c++) lin.push((await PR.stats(outL, { channel: c })).mean);
    const rough = maps.roughness ? (await PR.stats(maps.roughness, { channel: 0 })).mean : maps.arm ? (await PR.stats(maps.arm, { channel: 1 })).mean : 0.8;
    const ao = maps.ao ? (await PR.stats(maps.ao, { channel: 0 })).mean : maps.arm ? (await PR.stats(maps.arm, { channel: 0 })).mean : 1.0;
    for (const f of [col.field, stand, outA, outB, outL, ...Object.values(maps)]) f?.destroy();
    const hex2 = (v) => pyRoundHalfEven(v * 255).toString(16).padStart(2, '0');
    const stats = { version: PACK_VERSION, set: src.name, size: [W, H], mean_albedo_linear: lin,
        mean_albedo_srgb: '#' + lin.map((v) => hex2(P.linearToSrgb(v))).join(''), mean_roughness: rough, mean_ao: ao,
        height_mean: hm, height_std: maps.displacement ? hs : 0.0, has_height: 'displacement' in src, has_normal: 'normal' in src,
        sources: Object.fromEntries(['color', 'normal', 'roughness', 'ao', 'displacement', 'arm'].filter((k) => k in src).map((k) => [k, src[k]])) };
    const tmp = `${d}/stats.${Deno.pid}.tmp`;
    Deno.writeTextFileSync(tmp, JSON.stringify(stats, null, 1));
    Deno.renameSync(tmp, sPath);
    lap('stats');
    if (log) log(`[surfacing] packed ${src.name} (${W}x${H}) in ${((performance.now() - t0) / 1000).toFixed(1)} s (${JSON.stringify(tm)}) -> ${d}`);
    return d;
}

const FIT_DSP = `//! sampler dsp
//! image outF rgba32f
//! uniform ivec2 uSize
fn kmain(p: vec2<i32>) {
  if (p.x >= u.uSize.x || p.y >= u.uSize.y) { return; }
  let s = dsp_size();
  outF_store(p, dsp_at(vec2<i32>(p.x * s.x / u.uSize.x, p.y * s.y / u.uSize.y)));
}
`;

// the normals of normal_rough_ao.png's x, y (z rebuilt as the material rebuilds it, then normalised), and the 2 x 2
// block means of a level of them, for surfacing._normal_variance
const NORMALS = `//! sampler src r32ui
//! image outN rgba32f
//! uniform ivec2 uSize
fn kmain(p: vec2<i32>) {
  if (p.x >= u.uSize.x || p.y >= u.uSize.y) { return; }
  let c = unpack4x8unorm(src_at(p));
  let nx = c.x * 2.0 - 1.0;
  let ny = c.y * 2.0 - 1.0;
  var n = vec3<f32>(nx, ny, sqrt(max(1.0 - nx * nx - ny * ny, 0.0)));
  n = n / max(length(n), 1e-6);
  outN_store(p, vec4<f32>(n, 1.0));
}
`;
const BLOCKS = `//! sampler src
//! image outN rgba32f
//! image outL r32f
fn kmain(p: vec2<i32>) {
  if (!inside(p, outN_size())) { return; }
  let q = 2 * p;
  let b = (src_at(q).xyz + src_at(q + vec2<i32>(1, 0)).xyz + src_at(q + vec2<i32>(0, 1)).xyz + src_at(q + vec2<i32>(1, 1)).xyz) / 4.0;
  outN_store(p, vec4<f32>(b, 1.0));
  outL_store(p, vec4<f32>(length(b), 0.0, 0.0, 0.0));
}
`;

/** surfacing._loss_curve: [a, b, largest error] of smoothstep(a, b, m) fitted to lost[m] / total over the mip levels
 * 0-10, by numpy's grid search (a over -4..3, b over 0.5..12, steps of 0.1; the first minimum in row order). */
export function lossCurve(lost, total) {
    const fr = lost.slice(0, 11).map((v) => Number(v) / Math.max(Number(total), 1e-12));
    const As = [], Bs = [];
    for (let k = 0; -4.0 + k * 0.1 < 3.0001; k++) As.push(-4.0 + k * 0.1);
    for (let k = 0; 0.5 + k * 0.1 < 12.0001; k++) Bs.push(0.5 + k * 0.1);
    let best = [0, 0, Infinity];
    for (const A of As) {
        for (const B of Bs) {
            if (!((B - A) > 0.2)) continue;
            let err = 0;
            for (let m = 0; m < fr.length; m++) {
                const t = Math.min(Math.max((m - A) / Math.max(B - A, 1e-6), 0.0), 1.0);
                err = Math.max(err, Math.abs(t * t * (3.0 - 2.0 * t) - fr[m]));
            }
            if (err < best[2]) best = [A, B, err];
        }
    }
    return best;
}

/** A packed scan's stats with its normal map's slope variance (stats.normal_var: version, total, lost by mip level,
 * the loss curve's smoothstep edges a and b in mip levels and its fit error; surfacing.scan_normal_variance), made
 * once from its normal_rough_ao.png (a record of an older version refits its stored table) and kept in its
 * stats.json. total = 2 (1 - |mean n|); lost[m] = 2 (1 - the mean over the 2^m blocks of |block mean n|). */
export async function scanNormalVariance(folder, stats = null, opts = {}) {
    const log = opts.log === undefined ? console.log : opts.log;
    if (stats === null) stats = JSON.parse(Deno.readTextFileSync(`${folder}/stats.json`));
    const t0 = performance.now();
    const old = stats.normal_var ?? {};
    let total, lost;
    if (old.lost && old.total !== null && old.total !== undefined) {
        total = Number(old.total);
        lost = old.lost.map(Number);
    } else {
        const R = opts.R ?? await (await import('../core/gpu.js')).init();
        const { prims } = await import('../core/prims.js');
        const PR = prims(R);
        const im = await readImage(`${folder}/normal_rough_ao.png`);
        const w = im.width, h = im.height;
        const src = R.field(h, w, 1, u32Of(im.data, w * h), 'u32');
        let b = R.field(h, w, 4);
        R.run(R.kernel('surfacing_normals', NORMALS), { src }, { outN: b }, { uSize: [w, h] });
        src.destroy();
        const m = [];
        for (let c = 0; c < 3; c++) m.push((await PR.stats(b, { channel: c })).mean);
        total = 2.0 * (1.0 - Math.hypot(m[0], m[1], m[2]));
        lost = [0.0];
        let bh = h, bw = w;
        while (Math.min(bh, bw) >= 2) {
            bh = Math.floor(bh / 2);
            bw = Math.floor(bw / 2);
            const nb = R.field(bh, bw, 4), nl = R.field(bh, bw, 1);
            R.run(R.kernel('surfacing_blocks', BLOCKS), { src: b }, { outN: nb, outL: nl }, {});
            lost.push(2.0 * (1.0 - (await PR.stats(nl, { channel: 0 })).mean));
            b.destroy();
            nl.destroy();
            b = nb;
        }
        b.destroy();
        total = Math.max(total, 0.0);
    }
    const [a, bb, err] = lossCurve(lost, total);
    const round = (v, n) => Number(Number(v).toFixed(n));
    stats = { ...stats, normal_var: { version: NORMAL_VAR_VERSION, total: round(total, 6), lost: lost.map((v) => round(v, 6)),
        a: round(a, 3), b: round(bb, 3), fit_err: round(err, 4) } };
    const tmp = `${folder}/stats.${Deno.pid}.tmp`;
    try {
        Deno.writeTextFileSync(tmp, JSON.stringify(stats, null, 1));
        Deno.renameSync(tmp, `${folder}/stats.json`);
    } catch (_e) {
        try { Deno.removeSync(tmp); } catch (_e2) { /* gone */ }
    }
    if (log) {
        log(`[surfacing] ${stats.set ?? folder}: normal variance ${total.toFixed(4)} (lost by mip ` +
            `${lost.slice(1, 6).map((v) => (v / Math.max(total, 1e-12)).toFixed(2)).join(', ')}, ...) in ${((performance.now() - t0) / 1000).toFixed(1)} s`);
    }
    return stats;
}


// ---------------------------------------------------------------------------------- the canopy's mean ---

const CANOPY = new Map();

/** [r, g, b] linear: what a canopy's crowns as the material draws them (canopyNodes) average to where a crown is finer
 * than a pixel, their relief's shading included (their mean colour times the mean n_z of their bump), over `slices`
 * grids of n x n points a tenth of a crown apart at random heights (numpy's default_rng(seed) draws, core/np_random.js),
 * the crowns' and clumps' Voronoi and the ragged outlines' noise as the material's (surfacing.canopy_mean). Per point
 * on the GPU; its means in float32 trees (numpy's in float64). */
export async function canopyMean(cn, opts = {}) {
    return (await canopyStats(cn, opts)).mean;
}

/** The mean of the canopy's clump factor (surfacing.canopy_clump_mean): 1.0 for a canopy without clumps. */
export async function canopyClumpMean(cn, opts = {}) {
    return (await canopyStats(cn, opts)).clump;
}

async function canopyStats(cn, opts = {}) {
    const n = opts.n ?? 160, slices = opts.slices ?? 3, seed = opts.seed ?? 11;
    const key = JSON.stringify([cn, n, slices, seed]);
    if (CANOPY.has(key)) return CANOPY.get(key);
    const R = opts.R ?? await (await import('../core/gpu.js')).init();
    const { prims } = await import('../core/prims.js');
    const PR = prims(R);
    const rng = defaultRng(seed);
    const crownM = Number(cn.crown_m ?? 4.5), clumpM = Number(cn.clump_m ?? 0.0) || 0.0;
    const step = crownM / 10.0;
    const offs = [];
    for (let s = 0; s < slices; s++) {
        offs.push([Number(rng.uniform(0.0, 1000.0)), Number(rng.uniform(0.0, 1000.0)), Number(rng.uniform(0.0, 50.0 * Math.max(crownM, clumpM)))]);
    }
    const W = ops.WGSL();
    const N = noiseLib(W);
    const vor = voronoiF1Of(W, N);
    const v = (c) => ({ code: c, type: 'f32', wgsl: true });
    const [cx, cy, cz] = [v('co.x'), v('co.y'), v('co.z')];
    const lin = (hx) => P.hexLinear(hx).map(Number);
    const sm = (e0, e1, x) => {
        const t = W.clamp(W.div(W.sub(x, f32(e0)), f32(e1 - e0)), 0.0, 1.0);
        return W.mul(W.mul(t, t), W.sub(3.0, W.mul(2.0, t)));
    };
    const fv = vor(cx, cy, cz, f32(1.0 / crownM), f32(0.85));
    const rag = N.noiseNode3(cx, cy, cz, f32(2.2 / crownM), 2.0, 0.5);
    let crown = W.sub(1.0, sm(0.08, 0.6, W.mul(W.vx(fv) /* distance */, W.add(W.add(W.mul(W.vw(fv), 0.45), 0.62), W.mul(rag, 0.45)))));
    let bump = W.mul(W.pow(W.max(crown, 0.0), 0.6), f32(Number(cn.height_m ?? 3.0)));
    const r1 = W.vy(fv);
    const c0 = lin(cn.colour ?? '#26371f'), c1 = lin(cn.light ?? '#3d522c'), gp = lin(cn.gap ?? '#11160d');
    let tone = [0, 1, 2].map((q) => W.add(W.mul(f32(c0[q]), W.sub(1.0, r1)), W.mul(f32(c1[q]), r1)));
    let shade = W.add(W.mul(crown, 0.4), 0.72);
    let clumpF = W.f(1.0);
    if (clumpM > 0.0) {
        const cvv = vor(cx, cy, cz, f32(1.0 / clumpM), f32(1.0));
        const rag2 = N.noiseNode3(cx, cy, cz, f32(2.5 / clumpM), 2.0, 0.5);
        const gap = Number(cn.clump_gap ?? 0.25);
        const clump = W.sub(1.0, sm(0.62 - 0.4 * gap, 0.9 - 0.4 * gap, W.mul(W.vx(cvv), W.add(W.mul(rag2, 0.5), 0.75))));
        const k1 = W.add(W.mul(W.vy(cvv), 0.5), 0.76);
        tone = tone.map((t) => W.mul(t, k1));
        shade = W.mul(shade, W.add(W.mul(clump, 0.42), 0.68));
        bump = W.add(bump, W.mul(W.pow(W.max(clump, 0.0), 0.8), f32(Number(cn.clump_height_m ?? 4.0))));
        crown = W.mul(crown, W.add(W.mul(clump, 0.6), 0.4));
        clumpF = W.mul(W.mul(k1, W.add(W.mul(clump, 0.42), 0.68)), W.add(W.mul(clump, 0.6), 0.4));
    }
    const lit = sm(0.0, 0.32, crown);
    const colr = [0, 1, 2].map((q) => W.add(W.mul(f32(gp[q]), W.sub(1.0, lit)), W.mul(W.mul(tone[q], shade), lit)));
    const src = `//! image outC rgba32f\n//! image outK r32f\n//! uniform vec4 uO0\n//! uniform vec4 uO1\n//! uniform vec4 uO2\n` +
        `//! uniform int uN\n//! uniform float uStep\n${W.module()}\n\nfn kmain(p: vec2<i32>) {\n` +
        `  if (p.x >= u.uN || p.y >= 3 * u.uN) { return; }\n  let sl = p.y / u.uN;\n  let j = p.y - sl * u.uN;\n` +
        `  var o = u.uO0.xyz;\n  if (sl == 1) { o = u.uO1.xyz; }\n  if (sl == 2) { o = u.uO2.xyz; }\n` +
        `  let co = vec3<f32>(f32(p.x) * u.uStep + o.x, f32(j) * u.uStep + o.y, o.z);\n${W.body()}\n` +
        `  outC_store(p, vec4<f32>(${colr.map((c) => W.code(c)).join(', ')}, ${W.code(bump)}));\n` +
        `  outK_store(p, vec4<f32>(${W.code(clumpF)}, 0.0, 0.0, 0.0));\n}\n`;
    const k = R.kernel(`surfacing_canopy_${fnv(src)}`, { source: src });
    const outC = R.field(slices * n, n, 4), outK = R.field(slices * n, n, 1);
    const pad = (o) => [f32(o[0]), f32(o[1]), f32(o[2]), 0];
    R.run(k, {}, { outC, outK }, { uO0: pad(offs[0]), uO1: pad(offs[1 % slices]), uO2: pad(offs[2 % slices]), uN: n, uStep: f32(step) });
    const mean = [];
    for (let c = 0; c < 3; c++) mean.push((await PR.stats(outC, { channel: c })).mean);
    let nz = 1.0;
    if (Number(cn.height_m ?? 3.0) > 0.0) {
        const nzf = R.field(slices * n, n, 1);
        R.run(R.kernel('surfacing_canopy_nz', CANOPY_NZ), { src: outC }, { outF: nzf }, { uN: n, uStep: f32(step) });
        nz = (await PR.stats(nzf, { channel: 0 })).mean;
        nzf.destroy();
    }
    const clump = clumpM > 0.0 ? (await PR.stats(outK, { channel: 0 })).mean : 1.0;
    outC.destroy();
    outK.destroy();
    const out = { mean: mean.map((x) => x * nz), clump, nz };
    CANOPY.set(key, out);
    return out;
}

// np.gradient of each slice's bump (central differences inside, one-sided at the edges), and its normal's z
const CANOPY_NZ = `//! sampler src
//! image outF r32f
//! uniform int uN
//! uniform float uStep
fn bump(i: i32, j: i32, sl: i32) -> f32 { return src_at(vec2<i32>(i, sl * u.uN + j)).w; }
fn kmain(p: vec2<i32>) {
  if (p.x >= u.uN || p.y >= 3 * u.uN) { return; }
  let n = u.uN;
  let sl = p.y / n;
  let i = p.x;
  let j = p.y - sl * n;
  var dx = 0.0;
  var dy = 0.0;
  if (i == 0) { dx = (bump(1, j, sl) - bump(0, j, sl)) / u.uStep; }
  else if (i == n - 1) { dx = (bump(n - 1, j, sl) - bump(n - 2, j, sl)) / u.uStep; }
  else { dx = (bump(i + 1, j, sl) - bump(i - 1, j, sl)) / (2.0 * u.uStep); }
  if (j == 0) { dy = (bump(i, 1, sl) - bump(i, 0, sl)) / u.uStep; }
  else if (j == n - 1) { dy = (bump(i, n - 1, sl) - bump(i, n - 2, sl)) / u.uStep; }
  else { dy = (bump(i, j + 1, sl) - bump(i, j - 1, sl)) / (2.0 * u.uStep); }
  outF_store(p, vec4<f32>(1.0 / sqrt(1.0 + dx * dx + dy * dy), 0.0, 0.0, 0.0));
}
`;

const f32 = Math.fround;
function fnv(s) {
    let h = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 0x01000193) >>> 0;
    return h.toString(16);
}

export { hexClass as hex_class, farDistance as far_distance, setFarDistance as set_far_distance, strataArray as strata_array,
    strataImage as strata_image, surfaceMaterial as surface_material, farMaterial as far_material, applySurface as apply_surface,
    clayMaterial as clay_material, terrainMap as terrain_map_group, terrainConstants as terrain_constants, farRings as far_rings,
    packSet as pack_set, packedSet as packed_set, scanNormalVariance as scan_normal_variance, canopyMean as canopy_mean,
    canopyClumpMean as canopy_clump_mean, readerNodes as reader_group, hexGrid as hex_grid_group, cubicRead as _cubicRead };
