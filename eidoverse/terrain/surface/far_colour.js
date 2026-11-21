// Port of blender/eidoblend/terrain/surface/far_colour.py at d67f19e.
//
// The far colour C (SURFACING_DESIGN.md 2.3, 3.1.7, 3.7): the palette's ground per texel, every layer at its scan's
// mean, on the context and main levels' cells, from one generated GPU kernel per palette, compiled once. A hero level
// holds its parent's far colour: the far hand-off never reaches inside a hero window.
//
//     import * as FC from './surface/far_colour.js';
//     const out = await FC.bake(sd, palette);   // per level { rgba: an rgba32f GPU field (linear albedo, roughness) }
//     FC.kernelSource(palette)                  // { src (WGSL), names (the maps it reads, in sampler order), column }
//     FC.scanStats('Rock019')                   // a packed scan set's stats.json, or null
//
// Per texel, as build/surfacing.py's surface_group composes the near material, with each scan at its mean:
//   coverage   the layer's weight expression, clamped (mask_expr.js: Blender's noise where the expression has noise);
//   colour     the layer's target (its colour, or the strata column's formation colour at the stratigraphic height
//              plus strata_offset_m, mixed by a fractional `strata`), else its scan's mean; times its tint; its
//              patches (the palette's ramps and satmap arrive as patches through palettes.get) mixed in by their
//              noise, `where` and amount; the streaks' mean darkening on steep faces; times value; clamped to
//              0..0.95. A canopy layer far away is its crowns' mean tone over the gaps (CANOPY_COVER);
//   roughness  the scan's mean roughness times the layer's (times the column's at the height);
//   composite  the coverages in order, e_i = c_i prod_{j > i} (1 - c_j), then the material's height blend with
//              every scan at its mean height (a_i = e_i + h_i k, kept within blend_depth of the tallest, normalised);
//   then       ambient occlusion by the scans' mean AO, the tone expression (x clamp(1 + tone, 0.4, 1.6)), the macro
//              octaves (hue, saturation and value by world noise), damp (darker, smoother).
// Each texel is the mean of 4 x 4 sub-samples (SUB; the height interpolated at each), so terms finer than a texel are
// box-filtered; a noise term finer than a sub-sample reads its mean (mask_expr.js's footprint fade at a quarter
// texel, the uniform uFoot).
//
// Known differences from the near material (far_colour.py's own): the overlay of 3.2; the strata beds' jitter,
// partings and relief shading, the ledges' plants and the canopy's crown pattern enter as their means (the beds by
// their formation's colour); the height is the field's, not the ring mesh's interpolated vertices.
//
// Where this differs from far_colour.py, and why:
//   - Blender writes the kernel as GLSL text; here the palette's part (shade()'s body) is calls on build/ops.js's
//     WGSL backend through mask_expr.js and noise.js, the same arithmetic in far_colour.py's order, and the fixed
//     parts (the column lookup, the bilinear height, the HSV of Blender's Hue/Saturation/Value node, the sub-sample
//     loop) are far_colour.py's GLSL transcribed. The kernel is a compute kernel through core/gpu.js, as Blender's
//     is a compute kernel through its GPU module, not the TSL render pass PORT_PLAN.md 3.5 names: the C bake reads
//     the bake's GPU fields and runs headless with the other surface kernels on one runner, and the material's TSL
//     (P17) does not exist yet, so a TSL pass would be a second, parallel version of these maths now. When the
//     material lands, mask_expr.js's TSL instantiation gives it the same expressions from the same source.
//   - The `keep` factor of far_colour.py's main() (1 for any real value, so its GLSL compiler keeps every uniform)
//     is left out: core/gpu.js binds by an explicit layout, an unused binding stays.
//   - The strata column texture and the streaks' mean darkening are made on the GPU (kernels/palette/strata_column.wgsl,
//     the streak noise as a generated kernel and core/prims.js's sum): the column's formation per texel from each
//     formation's first texel at or above its top, found in doubles with numpy's arithmetic (exact); the streak
//     mean's 20,000 points are numpy's default_rng(7) draws (core/np_random.js, draw for draw), the noise over them
//     on the GPU (within float32 of noise.py), their mean a float32 tree sum (numpy's is pairwise: within float32).
//   - A detail-grid map (2n texels) reaches the n cells as the 2 x 2 box average on the GPU (kernels/atlas/
//     resample.wgsl), as _to_cells; a hero level's colour is its parent's, bilinear at its cell centres on the GPU
//     (kernels/atlas/bilinear.wgsl, atlas.sample_bilinear's arithmetic).
//   - scan_stats reads the packed sets from $EIDO_SURFACE_SETS when it is set (the tests point it at the Blender
//     edition's packed sets), else from this edition's eidoverse/assets/cache/terrain_surface_sets/ (far_colour.py's
//     SETS_DIR, its own repository's). Without a set's stats the layer takes far_colour.py's fallbacks (its own
//     colour or 0.3 grey, roughness 0.8, AO 1).

import { createHash } from 'node:crypto';
import * as ops from '../build/ops.js';
import * as P from '../build/palettes.js';
import { Compiler } from './mask_expr.js';
import { noise } from './noise.js';
import { kernel as surfaceKernel } from './bake.js';
import { defaultRng } from '../core/np_random.js';
import { prims } from '../core/prims.js';

const f32 = Math.fround;
export const COLUMN_TEXELS_PER_M = 1.0;
export const CANOPY_COVER = 0.72;         // the share of a far canopy texel in lit crowns (the rest the gaps' tone)
export const CANOPY_SHADE = 0.92;
export const SUB = 4;                     // sub-samples per texel side

/** Where the packed scan sets are: $EIDO_SURFACE_SETS, else <repo>/eidoverse/assets/cache/terrain_surface_sets. */
export function setsDir() {
    let env = null;
    try {
        env = globalThis.Deno?.env.get('EIDO_SURFACE_SETS') ?? null;
    } catch (_e) { /* no env access */ }
    if (env) return env.replace(/\\/g, '/').replace(/\/$/, '');
    return decodeURIComponent(new URL('../../assets/cache/terrain_surface_sets', import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1');
}

const STATS = new Map();

/** The packed scan set's stats (build/surfacing.py's pack_set: mean_albedo_linear, mean_roughness, mean_ao), or null
 * when the set has not been packed on this machine. */
export function scanStats(setName, prefer = '2k') {
    const dir = setsDir();
    const key = `${dir}|${setName}|${prefer}`;
    if (STATS.has(key)) return STATS.get(key);
    let out = null;
    try {
        const cands = [];
        const re = new RegExp(`^${String(setName).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}_.*_v.*$`);
        for (const e of Deno.readDirSync(dir)) {
            if (!e.isDirectory || !re.test(e.name)) continue;
            const p = `${dir}/${e.name}/stats.json`;
            try {
                Deno.statSync(p);
                cands.push(p);
            } catch (_e) { /* no stats */ }
        }
        cands.sort();
        if (cands.length) {
            const pick = cands.find((c) => c.includes(`_${prefer}_`)) ?? cands[0];
            out = JSON.parse(Deno.readTextFileSync(pick));
        }
    } catch (_e) {
        out = null;
    }
    STATS.set(key, out);
    return out;
}

const lin = (h) => P.hexLinear(h).map(Number);

// ---------------------------------------------------------------------------------------- the strata column ---

/** The column's mean colour of a formation's colour entry (a colour, or [[colour, weight], ...]): doubles. */
function meanColour(col) {
    if (Array.isArray(col) && Array.isArray(col[0])) {
        let w = 0;
        const s = [0, 0, 0];
        for (const [c, wt] of col) {
            for (let k = 0; k < 3; k++) s[k] += c[k] * wt;
            w += wt;
        }
        return s.map((v) => v / Math.max(w, 1e-9));
    }
    return col.map(Number);
}

/** far_colour._column: { W, zLo, zHi, rep, formations: [[K_f, r, g, b, roughness]] } of the palette's strata column
 * (the texel count, the end formations run on past the ends by pad_m), or null without strata layers. */
export function column(pal) {
    const st = pal.strata ?? {};
    if (!(st.column && pal.layers.some((L) => L.strata))) return null;
    const layers = P.columnLayers(st.column, Boolean(st.looks ?? false));
    const rep = P.columnRepeats(st.column);
    let zLo = layers[0][1], zHi = layers[layers.length - 1][2];
    if (!rep) {
        const pad = Number(st.pad_m ?? 0.0);
        zLo -= pad;
        zHi += pad;
    }
    const W = Math.trunc(Math.min(16384, Math.max(16, Math.ceil((zHi - zLo) * COLUMN_TEXELS_PER_M))));
    // z_k = z_lo + (k + 0.5) / W * (z_hi - z_lo), numpy's doubles; K_f: the first texel with z_k >= top_f
    const zc = (k) => zLo + ((k + 0.5) / W) * (zHi - zLo);
    const formations = layers.map((L) => {
        const top = L[2];
        let lo = 0, hi = W;                       // the first k in [0, W] with zc(k) >= top (W: none)
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (zc(mid) >= top) hi = mid;
            else lo = mid + 1;
        }
        const c = meanColour(L[3]);
        return [lo, f32(c[0]), f32(c[1]), f32(c[2]), Number(L[4])];
    });
    return { W, zLo, zHi, rep: Boolean(rep), formations };
}

/** The column as a (1, W) rgba32f GPU field (kernels/port/strata_column.wgsl). */
function columnField(R, col) {
    const nf = col.formations.length;
    const form = new Float32Array(4 * nf), rough = new Float32Array(4 * nf);
    col.formations.forEach(([K, r, g, b, ro], f) => {
        form.set([K, r, g, b], 4 * f);
        rough[4 * f] = ro;
    });
    const fT = R.field(1, nf, 4, form), rT = R.field(1, nf, 4, rough);
    const out = R.field(1, col.W, 4);
    R.run(surfaceKernel(R, 'palette/strata_column'), { formT: fT, roughT: rT }, { outC: out }, { uN: nf });
    fT.destroy();
    rT.destroy();
    return out;
}

// ---------------------------------------------------------------------------------- the streaks' mean darkening ---

let STREAK_POINTS = null;

/** E[smoothstep(lo, hi, n)] of the streak noise (detail 3, roughness 0.55) over the plane: its darkening's mean,
 * at far_colour._streak_mean's 20,000 points (numpy's default_rng(7)), the noise on the GPU. */
export async function streakMean(R, lo, hi, n3, seed = 19.7) {
    if (!STREAK_POINTS) {
        const co = defaultRng(7).uniform(-5000, 5000, [20000, 3]);
        const pts = new Float32Array(4 * 20000);
        for (let k = 0; k < 20000; k++) pts.set([co[3 * k], co[3 * k + 1], co[3 * k + 2]], 4 * k);   // .astype(F)
        STREAK_POINTS = pts;
    }
    const W = ops.WGSL();
    const N = noise(W);
    const q = ['x', 'y', 'z'].map((c) => ({ code: `q.${c}`, type: 'f32', wgsl: true }));
    let n;
    if (n3) {
        const off = [37.7 * seed + 11.3, -51.9 * seed + 7.1, 23.3 * seed - 3.7].map(f32);
        n = N.noiseNode3(W.add(q[0], off[0]), W.add(q[1], off[1]), W.add(q[2], off[2]), 1.0, 3.0, 0.55);
    } else {
        n = N.noiseNode4(q[0], q[1], q[2], f32(seed), 1.0, 3.0, 0.55);
    }
    const t = W.clamp(W.div(W.sub(n, f32(lo)), f32(Math.max(hi - lo, 1e-6))), 0.0, 1.0);
    const v = W.mul(W.mul(t, t), W.sub(3.0, W.mul(2.0, t)));
    const src = `//! sampler pts\n//! image outV r32f\n${W.module()}\n\nfn kmain(p: vec2<i32>) {\n` +
        `  if (!inside(p, outV_size())) { return; }\n  let q = pts_at(p);\n${W.body()}\n` +
        `  outV_store(p, vec4<f32>(${W.code(v)}, 0.0, 0.0, 0.0));\n}\n`;
    const k = R.kernel(`surface_streak_mean_${sha1(src).slice(0, 12)}`, { source: src });
    const pf = R.field(1, 20000, 4, STREAK_POINTS);
    const of = R.field(1, 20000, 1);
    R.run(k, { pts: pf }, { outV: of }, {});
    const st = await prims(R).stats(of);
    pf.destroy();
    of.destroy();
    return f32(st.sum / st.count);
}

function sha1(s) {
    return createHash('sha1').update(s).digest('hex');
}

// ----------------------------------------------------------------------------------------- the generator ---

const HSV = `
fn rgb_to_hsv_b(rgb: vec3<f32>) -> vec3<f32> {
  let cmax = max(rgb.x, max(rgb.y, rgb.z));
  let cmin = min(rgb.x, min(rgb.y, rgb.z));
  let cdelta = cmax - cmin;
  let v = cmax;
  var s = 0.0;
  var h = 0.0;
  if (cmax != 0.0) { s = cdelta / cmax; }
  if (s != 0.0) {
    let c = (vec3<f32>(cmax) - rgb) / cdelta;
    if (rgb.x == cmax) {
      h = c.z - c.y;
    } else if (rgb.y == cmax) {
      h = 2.0 + c.x - c.z;
    } else {
      h = 4.0 + c.y - c.x;
    }
    h = h / 6.0;
    if (h < 0.0) { h = h + 1.0; }
  }
  return vec3<f32>(h, s, v);
}
fn hsv_to_rgb_b(hsv: vec3<f32>) -> vec3<f32> {
  var h = hsv.x;
  let s = hsv.y;
  let v = hsv.z;
  if (s == 0.0) { return vec3<f32>(v); }
  if (h == 1.0) { h = 0.0; }
  h = h * 6.0;
  let i = floor(h);
  let f = h - i;
  let p = v * (1.0 - s);
  let q = v * (1.0 - s * f);
  let t = v * (1.0 - s * (1.0 - f));
  if (i == 0.0) { return vec3<f32>(v, t, p); }
  if (i == 1.0) { return vec3<f32>(q, v, p); }
  if (i == 2.0) { return vec3<f32>(p, v, t); }
  if (i == 3.0) { return vec3<f32>(p, q, v); }
  if (i == 4.0) { return vec3<f32>(t, p, v); }
  return vec3<f32>(v, p, q);
}
// Blender's Hue/Saturation/Value node with Fac 1 (the material's _macro: Hue = 0.5 + shift)
fn hue_sat(shift: f32, sat: f32, val: f32, col: vec3<f32>) -> vec3<f32> {
  var hsv = rgb_to_hsv_b(col);
  hsv.x = fract(hsv.x + shift + 1.0);
  hsv.y = clamp(hsv.y * sat, 0.0, 1.0);
  hsv.z = hsv.z * val;
  return hsv_to_rgb_b(hsv);
}
`;

const FIXED = `
fn column(zs: f32) -> vec4<f32> {
  let n = colT_size();
  var t = (zs - u.uColumn.x) / max(u.uColumn.y - u.uColumn.x, 1e-6);
  if (u.uColumn.z > 0.5) { t = t - floor(t); }
  let i = clamp(i32(floor(t * f32(n.x))), 0, n.x - 1);
  return colT_at(vec2<i32>(i, 0));
}

// the ground's height at a point inside texel p (offset in texels from its centre): bilinear on the cell centres
fn hsample(p: vec2<i32>, off: vec2<f32>) -> f32 {
  let n = hT_size();
  let c = vec2<f32>(p) + off;
  let fl = floor(c);
  let t = c - fl;
  let i0 = clamp(vec2<i32>(fl), vec2<i32>(0), n - 1);
  let i1 = clamp(vec2<i32>(fl) + 1, vec2<i32>(0), n - 1);
  return mix(mix(hT_at(i0).x, hT_at(vec2<i32>(i1.x, i0.y)).x, t.x),
             mix(hT_at(vec2<i32>(i0.x, i1.y)).x, hT_at(i1).x, t.x), t.y);
}
`;

const MAIN = `
// each texel the mean of uSub x uSub sub-samples: terms finer than a texel are box-filtered, not point-sampled (the
// count is a uniform: one copy of shade() in a loop)
fn kmain(p: vec2<i32>) {
  let n = hT_size();
  if (!inside(p, n)) { return; }
  let ns = max(i32(u.uSub + 0.5), 1);
  let inv = 1.0 / f32(ns);
  var acc = vec4<f32>(0.0);
  for (var k = 0; k < ns * ns; k++) {
    let off = (vec2<f32>(f32(k % ns), f32(k / ns)) + 0.5) * inv - 0.5;
    let pos = vec3<f32>(u.uLevel.xy + (vec2<f32>(p) + 0.5 + off) * u.uLevel.z, hsample(p, off));
    acc = acc + shade(pos, p);
  }
  outC_store(p, acc * (inv * inv));
}
`;

/** The kernel's generator: reads of maps by name become channels of packed samplers (far_colour._Gen). */
class Gen {
    constructor(pal, W) {
        this.pal = pal;
        this.opt = pal.options ?? {};
        this.n3 = this.opt.detile === 'rotate';
        this.W = W;
        this.pos = ['x', 'y', 'z'].map((c) => ({ code: `uPos.${c}`, type: 'f32', wgsl: true }));
        this.comp = new Compiler({ ops: W, read: (nm) => ({ code: `@@${nm}@@`, type: 'f32', wgsl: true }), pos: this.pos,
            constants: pal.constants ?? null, noise3: this.n3, texelM: 'uniform', foot: { code: 'u.uFoot', type: 'f32', wgsl: true } });
    }

    e(src) {
        return this.comp.expr(src);
    }

    /** surface_group's noise(): 3D on a landscape palette, else the old 4D (w = seed), faded by the footprint. */
    noise(scaleM, detail, roughness, seed) {
        const W = this.W, c = this.comp;
        const fade = c._fade(scaleM);
        const det = c._detail(scaleM, detail);
        let n;
        if (this.n3) {
            n = c.node3(scaleM, det, roughness, seed);
        } else {
            n = noise(W).noiseNode4(this.pos[0], this.pos[1], this.pos[2], f32(seed), f32(1.0 / scaleM),
                typeof det === 'number' ? f32(det) : det, f32(roughness));
        }
        if (typeof fade === 'number' && fade >= 1.0) return n;
        return W.add(0.5, W.mul(W.sub(n, 0.5), typeof fade === 'number' ? f32(fade) : fade));
    }
}

const v3 = (W, c) => W.v3(f32(c[0]), f32(c[1]), f32(c[2]));

/** { src, names, column, kernelName }: the far colour kernel of a palette (module doc). One source serves every
 * level: the footprint (a quarter texel, uFoot) and the sub-sample count (uSub) are uniforms. */
export async function kernelSource(pal, R = null) {
    R = R ?? await (await import('../core/gpu.js')).init();          // the streaks' mean darkening runs on the GPU
    const W = ops.WGSL();
    const g = new Gen(pal, W);
    const opt = g.opt;
    const L_ = pal.layers;
    const col = column(pal);
    let strataZs = null;
    // shade()'s first statements: slopeDeg and steepFace, as far_colour.py's shade() starts
    const slopeDeg = { code: '@@slope@@', type: 'f32', wgsl: true };
    const steepFace = g.comp._smooth(W.f(0.78), W.f(0.5), W.cos(W.radians(slopeDeg)));
    if (col !== null) {
        const st = pal.strata;
        let zs;
        if ((st.source ?? 'attribute') === 'attribute') {
            zs = { code: '@@strata@@', type: 'f32', wgsl: true };
            g.comp.names.add('strata');
        } else {
            const dip = Math.tan((Number(st.dip_deg ?? 0.0) * Math.PI) / 180);
            const az = (Number(st.dip_azimuth_deg ?? st.azimuth_deg ?? 0.0) * Math.PI) / 180;
            zs = W.sub(g.pos[2], W.mul(W.add(W.mul(g.pos[0], f32(Math.cos(az))), W.mul(g.pos[1], f32(Math.sin(az)))), f32(dip)));
        }
        zs = W.add(zs, f32(Number(st.z_offset_m ?? 0.0)));
        for (const f of st.faults ?? []) {
            const s = (Number(f.strike_deg ?? 0.0) * Math.PI) / 180;
            let nx = Math.cos(s), ny = -Math.sin(s);
            const want = { west: [-1, 0], east: [1, 0], north: [0, 1], south: [0, -1] }[f.down ?? 'west'];
            if (nx * want[0] + ny * want[1] < 0) {
                nx = -nx;
                ny = -ny;
            }
            const w = Math.max(Number(f.width_m ?? 50.0), 1e-3);
            const d = W.add(W.mul(W.sub(g.pos[0], f32(Number(f.x ?? 0.0))), f32(nx)), W.mul(W.sub(g.pos[1], f32(Number(f.y ?? 0.0))), f32(ny)));
            zs = W.add(zs, W.mul(g.comp._smooth(W.f(f32(-0.5 * w)), W.f(f32(0.5 * w)), d), f32(Number(f.throw_m ?? 0))));
        }
        (st.warp ?? []).forEach(([scale, amp], k) => {
            const det = g.comp._detail(Number(scale), 2.0);
            const n = noise(W).noiseNode4(g.pos[0], g.pos[1], g.pos[2], f32(41.3 + 3.7 * k), f32(1.0 / Number(scale)),
                typeof det === 'number' ? f32(det) : det, 0.5);
            const fade = g.comp._fade(Number(scale));
            const gain = typeof fade === 'number' ? f32(2.0 * Number(amp) * fade) : W.mul(f32(2.0 * Number(amp)), fade);
            zs = W.add(zs, W.mul(W.sub(n, 0.5), gain));
        });
        strataZs = zs;
    }
    const cols = [], roughs = [], covs = [], pers = [], hmeans = [];
    for (let i = 0; i < L_.length; i++) {
        const L = L_[i];
        const stats = scanStats(L.set);
        const mean = stats ? stats.mean_albedo_linear.map(Number) : (L.colour ? lin(L.colour) : [0.3, 0.3, 0.3]);
        const mrough = stats ? Number(stats.mean_roughness) : 0.8;
        const mao = stats ? Number(stats.mean_ao) : 1.0;
        hmeans.push(0.5);                 // the packed height's mean: pack_set stores 0.5 + 0.15 (d - mean) / std
        covs.push(W.clamp(g.e(L.weight), 0.0, 1.0));
        const own = L.colour ? lin(L.colour) : null;
        const smix = L.strata === true ? 1.0 : Number(L.strata);
        let rough = W.f(f32(mrough * Number(L.roughness ?? 1.0)));
        let target;
        if (smix > 0 && col !== null && L.strata) {
            const off = Number(L.strata_offset_m ?? 0.0);
            const band = W.ext('vec4', 'column', W.add(strataZs, f32(off)));
            const rgb = W.v3(W.vx(band), W.vy(band), W.vz(band));
            target = (smix >= 1.0 || own === null) ? rgb : W.vmix(v3(W, own), rgb, f32(smix));
            rough = smix >= 1.0 ? W.mul(rough, W.vw(band)) : W.mul(rough, W.mix(1.0, W.vw(band), f32(smix)));
        } else if (own !== null) {
            target = v3(W, own);
        } else {
            target = v3(W, mean);
        }
        let c = target;
        if (L.tint !== null && L.tint !== undefined) c = W.vmulv(c, v3(W, [...L.tint].slice(0, 3).map(Number)));
        if (L.strata && smix >= 1.0 && col !== null && (L.relief ?? true) && Number((pal.strata || {}).relief_m || 0.0) > 0) {
            const shade = Number(pal.strata.relief_shade ?? 0.15);
            c = W.vmuls(c, f32(1.0 - 0.5 * shade));          // the beds' relief shade, at its mean
        }
        if (L.canopy) {
            const cn = L.canopy;
            const a = lin(cn.colour ?? '#26371f'), b = lin(cn.light ?? '#3d522c');
            const lit = a.map((x, k) => 0.5 * (x + b[k]) * CANOPY_SHADE);
            const gap = lin(cn.gap ?? '#11160d');
            c = W.vmix(v3(W, gap), v3(W, lit), f32(CANOPY_COVER));   // crowns far away
            rough = W.f(0.9);
        }
        const pts = L.patches ?? [];
        const list = Array.isArray(pts) ? pts : [pts];
        list.forEach((pt, k) => {
            const amount = Number(pt.amount ?? 0.6);
            let pm;
            if (pt.scale_m === null || pt.scale_m === undefined) {
                pm = W.f(f32(amount));
            } else {
                const pn = g.noise(Number(pt.scale_m), Number(pt.detail ?? 3.0), 0.55, 33.7 + 2.3 * i + 5.1 * k);
                pm = W.mul(g.comp._smooth(W.f(f32(Number(pt.lo ?? 0.42))), W.f(f32(Number(pt.hi ?? 0.62))), pn), f32(amount));
            }
            if (pt.where) pm = W.mul(pm, W.clamp(g.e(pt.where), 0.0, 1.0));
            let ratio;
            if (pt.tint) {
                ratio = [...pt.tint].slice(0, 3).map(Number);
            } else {
                const ref = L.colour ? lin(L.colour) : mean.map((x) => Math.max(x, 1e-4));
                const pc = lin(pt.colour);
                ratio = pc.map((x, q) => x / Math.max(ref[q], 1e-4));
            }
            c = W.vmix(c, W.vmulv(c, v3(W, ratio)), pm);
        });
        if (L.streaks) {
            const stv = L.streaks.map(Number);
            const [lo, hi] = stv.length >= 4 ? [stv[2], stv[3]] : [0.45, 0.68];
            const meanDark = stv[1] * await streakMean(R, lo, hi, g.n3, 19.7 + 3.3 * i);
            let dark = W.mul(f32(meanDark), steepFace);
            if (L.streaks_where) dark = W.mul(dark, W.clamp(g.e(L.streaks_where), 0.0, 1.0));
            c = W.vmuls(c, W.sub(1.0, dark));
        }
        if (Number(L.value ?? 1.0) !== 1.0) c = W.vmuls(c, f32(Number(L.value)));
        c = W.vclamp(c, 0.0, 0.95);
        cols.push(c);
        roughs.push(rough);
        pers.push(mao);
    }
    // the composite: coverage in order, then the material's height blend with every scan at its mean height
    const n = L_.length;
    let rem = W.f(1.0);
    const e = new Array(n);
    for (let i = n - 1; i >= 0; i--) {
        e[i] = W.mul(covs[i], rem);
        rem = W.mul(rem, W.sub(1.0, covs[i]));
    }
    const kHb = Number(opt.height_blend || 0.0);
    const bd = Number(opt.blend_depth || 0.2);
    let w;
    if (n > 1) {
        const a = e.map((ei, i) => W.add(ei, f32(hmeans[i] * kHb)));
        let mx = a[n - 1];
        for (let i = n - 2; i >= 0; i--) mx = W.max(a[i], mx);
        const ma = W.sub(mx, f32(bd));
        w = a.map((ai) => W.max(W.sub(ai, ma), 0.0));
        let sum = w[0];
        for (let i = 1; i < n; i++) sum = W.add(sum, w[i]);
        const ws = W.max(sum, 1e-5);
        w = w.map((wi) => W.div(wi, ws));
    } else {
        w = [W.f(1.0)];
    }
    let albedo = W.vmuls(cols[0], w[0]);
    let rough = W.mul(w[0], roughs[0]);
    for (let i = 1; i < n; i++) {
        albedo = W.vadd(albedo, W.vmuls(cols[i], w[i]));
        rough = W.add(rough, W.mul(w[i], roughs[i]));
    }
    const ao = Number(opt.ao || 0.0);
    if (ao > 0) {
        let s = W.mul(w[0], f32(pers[0]));
        for (let i = 1; i < n; i++) s = W.add(s, W.mul(w[i], f32(pers[i])));
        albedo = W.vmuls(albedo, W.add(f32(1.0 - ao), W.mul(s, f32(ao))));
    }
    if (opt.tone) albedo = W.vmuls(albedo, W.clamp(W.add(1.0, g.e(opt.tone)), 0.4, 1.6));
    const macro = opt.macro ?? [];
    if (macro.length) {
        const val = [], hue = [], sat = [];
        macro.forEach((o, k) => {
            const seed = o.w ?? 1.7 + 2.9 * k;
            const mac = g.noise(Number(o.scale_m), Number(o.detail ?? 2.0), Number(o.roughness ?? 0.5), Number(seed));
            const t = () => W.clamp(W.div(W.sub(mac, 0.3), 0.4), 0.0, 1.0);
            if (o.value) val.push(W.add(f32(1.0 - o.value), W.mul(t(), f32(2.0 * o.value))));
            if (o.hue) hue.push(W.add(f32(-o.hue), W.mul(t(), f32(2.0 * o.hue))));
            if (o.saturation) {
                const [lo, hi] = o.saturation.map(Number);
                sat.push(W.add(f32(lo), W.mul(t(), f32(hi - lo))));
            }
        });
        const fold = (xs, op, dflt) => (xs.length ? xs.slice(1).reduce((s, x) => W[op](s, x), xs[0]) : W.f(dflt));
        albedo = W.ext('vec3', 'hue_sat', fold(hue, 'add', 0.0), fold(sat, 'mul', 1.0), fold(val, 'mul', 1.0), albedo);
    }
    const dampAmt = Number(opt.damp || 0.0);
    if (dampAmt > 0 || opt.damp_where) {
        let dm = null;
        if (dampAmt > 0) {
            const dn = g.noise(Number(opt.damp_scale_m ?? 6.25), 3.0, 0.6, 13.3);
            dm = W.mul(g.comp._smooth(W.f(0.5), W.f(0.68), dn), f32(dampAmt));
        }
        if (opt.damp_where) {
            const dw = W.clamp(g.e(opt.damp_where), 0.0, 1.0);
            dm = dm === null ? dw : W.max(dm, dw);
        }
        albedo = W.vmuls(albedo, W.sub(1.0, W.mul(dm, 0.38)));
        rough = W.mul(rough, W.sub(1.0, W.mul(dm, 0.32)));
    }
    albedo = W.vmax(W.vmin(albedo, 0.95), 0.0);
    const result = W.v4(W.vx(albedo), W.vy(albedo), W.vz(albedo), W.clamp(rough, 0.02, 1.0));
    // the maps it reads: packed four to a sampler, after the noise terms are known
    const names = [...new Set([...g.comp.names, 'slope'])].sort();
    const slot = Object.fromEntries(names.map((nm, k) => [nm, [k >> 2, k & 3]]));
    const ns = (names.length + 3) >> 2;
    let body = W.body('  ');
    let fns = W.module();
    for (const [nm, [s, c]] of Object.entries(slot)) {
        const rep = `m${s}.${'xyzw'[c]}`;
        body = body.split(`@@${nm}@@`).join(rep);
        fns = fns.split(`@@${nm}@@`).join(rep);
    }
    const ret = W.code(result).split('@@slope@@').join(`m${slot.slope[0]}.${'xyzw'[slot.slope[1]]}`);
    const head = ['// far_colour: the palette\'s ground per texel, generated by surface/far_colour.js (its doc).'];
    for (let s = 0; s < ns; s++) head.push(`//! sampler maps${s}   maps ${names.filter((nm) => slot[nm][0] === s).join(', ')}`);
    head.push('//! sampler hT      x: the ground height (Blender z)');
    head.push('//! sampler colT    the strata column: rgb, roughness multiplier (one row)');
    head.push('//! image   outC rgba32f   linear albedo, roughness');
    head.push('//! uniform vec3 uLevel    (x0, y0, texel) of the level, metres');
    head.push('//! uniform vec3 uColumn   (z_lo, z_hi, repeat)');
    head.push('//! uniform float uFoot    the footprint the noise terms fade at: the sub-samples\' spacing, metres');
    head.push('//! uniform float uSub     sub-samples per texel side');
    const reads = Array.from({ length: ns }, (_x, s) => `  let m${s} = maps${s}_at(p);`).join('\n');
    const src = head.join('\n') + '\n' + fns + '\n' + HSV + FIXED +
        `\n// the near material's colour logic at one point (its maps read at the texel holding it)\n` +
        `fn shade(uPos: vec3<f32>, p: vec2<i32>) -> vec4<f32> {\n${reads}\n${body}\n  return ${ret};\n}\n` + MAIN;
    return { src, names, column: col, kernelName: `surface_far_colour_${sha1(src).slice(0, 12)}` };
}

// ------------------------------------------------------------------------------------------------ the bake ---

/** [rgba32f GPU field (n x n: linear albedo, roughness)] per level: the far colour on the context and main levels'
 * cells; a hero level holds its parent's, bilinear at its cell centres. The caller releases the fields. */
export async function bake(sd, pal, { R, log = console.log } = {}) {
    const out = [];
    const { src, names, column: col, kernelName } = await kernelSource(pal, R);
    const k = R.kernel(kernelName, { source: src });
    const colT = col ? columnField(R, col) : R.field(1, 1, 4);
    const ucol = col ? [col.zLo, col.zHi, col.rep ? 1.0 : 0.0] : [0.0, 1.0, 0.0];
    try {
        for (let i = 0; i < sd.levels.length; i++) {
            const t0 = performance.now();
            const lv = sd.levels[i];
            const texel = Number(lv.cell);
            if (lv.role === 'hero' && lv.parent !== null && lv.parent !== undefined) {
                // atlas.sample_bilinear at the cell centres x0 + (i + 0.5) cell: fi = (x - px0) / pcell - 0.5
                const plv = sd.levels[lv.parent];
                const pc = Number(plv.cell);
                const ax = (Number(lv.x0) + 0.5 * texel - Number(plv.x0)) / pc - 0.5;
                const ay = (Number(lv.y0) + 0.5 * texel - Number(plv.y0)) / pc - 0.5;
                const o = R.field(lv.n, lv.n, 4);
                R.run(surfaceKernel(R, 'atlas/bilinear'), { src: out[lv.parent] }, { outB: o },
                    { uMap: [f32(ax), f32(texel / pc), f32(ay), f32(texel / pc)] });
                out.push(o);
                if (log) log(`[surface] palette bake: far colour on level ${i} (hero: its parent's) in ${((performance.now() - t0) / 1000).toFixed(2)} s`);
                continue;
            }
            const m = await sd.maps(i);
            const n = lv.n;
            const h = sd.terrain.fields(i).h;
            const hT = R.field(n, n, 1, h instanceof Float32Array ? h : new Float32Array(h));
            const samp = { hT, colT };
            const made = [hT];
            for (let s = 0; s < (names.length + 3) >> 2; s++) {
                const four = names.slice(4 * s, 4 * s + 4);
                const chans = {};
                four.forEach((nm) => {
                    let v = m[nm];
                    if ((v === undefined || v === null) && nm === 'height') v = h;
                    if (v === undefined || v === null) return;
                    let f = R.field(Math.round(Math.sqrt(v.length)), Math.round(Math.sqrt(v.length)), 1, v instanceof Float32Array ? v : new Float32Array(v));
                    made.push(f);
                    if (f.h !== n) {
                        if (f.h !== 2 * n) throw new Error(`a map of ${f.h} texels on a level of ${n} cells`);
                        const c = R.field(n, n, 4);
                        R.run(surfaceKernel(R, 'atlas/resample'), { src: f }, { outR: c }, { uMode: 0 });
                        const one = R.field(n, n, 1);
                        R.run(surfaceKernel(R, 'pick'), { a: c }, { outF: one }, { uCh: 0, uOffset: [0, 0] });
                        c.destroy();
                        made.push(one);
                        f = one;
                    }
                    chans[nm] = f;
                });
                const packed = R.pack(chans, four.concat(Array(4 - four.length).fill(null)), [n, n]);
                made.push(packed);
                samp[`maps${s}`] = packed;
            }
            const o = R.field(n, n, 4);
            R.run(k, samp, { outC: o }, { uLevel: [f32(Number(lv.x0)), f32(Number(lv.y0)), f32(texel)], uColumn: ucol.map(f32),
                uFoot: f32(texel / SUB), uSub: SUB });
            for (const f of made) f.destroy();
            out.push(o);
            if (log) log(`[surface] palette bake: far colour on level ${i} in ${((performance.now() - t0) / 1000).toFixed(2)} s`);
        }
    } finally {
        colT.destroy();
    }
    return out;
}

export { kernelSource as kernel_source, scanStats as scan_stats };
