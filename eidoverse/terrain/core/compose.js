// Port of blender/eidoblend/terrain/core/compose.py at f90c6fc.
//
// Composition: world-space shapes, stamps, uplift fields and flatten areas (design sections 4.1 and 4.13). Every
// shape is a function of world (x, y) metres, given as a JSON spec, so a level samples the same shape at its own
// cells (inputs are functions of world position) and a recipe stays data. The shapes are evaluated on the GPU at a
// window's cell centres (a Level, or { x0, y0, cell, n } / { ..., h, w }), each moved by opts.disp when given (an
// rg32f field of metres); every call returns a new field the caller owns.
//
//     import * as C from './core/compose.js';
//     const s = C.shape(R, { kind: 'cone', centre: [0, 0], radius_m: 18000, height_m: 3700 }, level);
//     const h = C.stamp(h0, s, 'smooth_max', 40.0);          // add | max | min | smooth_max | smooth_min | blend
//     const u = C.uplift(R, { kind: 'ridge', centre: [0, 0], azimuth_deg: 30, length_m: 14000, width_m: 7000,
//                             spurs: 6 }, level, 3);         // 0..1, no creases
//     const h1 = await C.startSurface(R, spec, level, 3, { heightM: 600 });   // the uplift shape as a rough start
//     const rigid = C.flattenMask(R, areas, level);          // 1 inside flatten areas: U = K = 0 there
//     const zs = await C.resolveFlatHeights(areas, [[level, hField], ...]);   // each area's height
//     const h2 = C.flattenExact(h, level, areas, zs);        // exact, C1 falloff
//
// Shapes (all lengths in metres, heights in metres, angles in degrees):
//     cone      centre, radius_m, height_m, profile 'linear' | 'cosine' | 'exp' (lambda_m), crater_radius_m
//     bowl      centre, radius_m, depth_m, exponent (2: parabolic): negative inside the radius, 0 outside
//     profile   centre, r_m [...], z_m [...]: a radial profile table, linearly interpolated (constant past its ends)
//     array     path (.npy, metres, row 0 south) or values, x0, y0, cell: a painted array, sampled bilinearly
//     dome / ridge / plateau / massif: the uplift shapes, 0..1 (see uplift())
//     field     any core/world_noise.js field spec ({ kind: 'fbm', ... }) under 'of'
//
// Where this differs from compose.py, and why (each checked against its numpy original, tests/core_inputs/):
//   - numpy evaluates the shapes in float64 at any points; the kernels (kernels/compose/) are float32 at a window's
//     cells, with positions relative to the shape's centre ((x0 - cx) in doubles), within 1e-5 of the range.
//   - uplift's noise is world_noise.fieldGpu's always (compose.py's _Noise with a level; shape() calls uplift
//     without one, numpy's path, the same function in float64). The spur and peak plans (numpy's Generator) are
//     drawn in JavaScript doubles (core/np_random.js) and read by the kernel from a table.
//   - The hard edges of the flatten areas (r <= radius) decide each cell as numpy's float64 np.hypot does: per row,
//     the interval of columns inside is found in doubles (a table over rows, not cells) and the kernel reads it;
//     resolveFlatHeights' medians are an exact selection (core/prims.js median) over that set, finest level first
//     (Blender walks coarsest first and keeps the last level that holds the area: the same level). A cell whose
//     distance lies within one ulp of the radius could still go the other way where V8's Math.hypot and the C
//     library's hypot round differently.
//   - start_surface is async when it finds the shape's peak itself (one readback); shape 'array' with a path reads
//     its .npy synchronously (core/io.js readNpySync), and is float32 on the GPU.

import * as Gd from './grid.js';
import * as N from './world_noise.js';
import { ValueError, pyRepr, pyReprValue, pyStr } from './levels.js';
import { defaultRng } from './np_random.js';
import { prims } from './prims.js';
import { readNpySync } from './io.js';

const UPLIFT_KINDS = ['dome', 'ridge', 'plateau', 'massif'];
const num = (v, d) => (v === undefined || v === null ? d : Number(v));
const int = (v, d) => (v === undefined || v === null ? d : Math.trunc(Number(v)));
const radians = (deg) => deg * (Math.PI / 180.0);
const windowShape = (lv) => (lv.h !== undefined && lv.w !== undefined ? [lv.h, lv.w] : [lv.n, lv.n]);
const isField = (v) => v !== null && typeof v === 'object' && typeof v.h === 'number' && v.runner !== undefined;


// --------------------------------------------------------------------------------------------- blending ---

/** Polynomial smooth minimum (C1) with a blend width of k metres; min(a, b) when k <= 0. Numbers (in doubles), or
 * fields (a new field). */
export function smoothMin(a, b, k) {
    if (isField(a)) return stamp(a, b, 'smooth_min', k);
    if (k <= 0) return Math.min(a, b);
    const hh = Math.max(k - Math.abs(a - b), 0.0) / k;
    return Math.min(a, b) - hh * hh * k * 0.25;
}

export function smoothMax(a, b, k) {
    if (isField(a)) return stamp(a, b, 'smooth_max', k);
    return -smoothMin(-a, -b, k);
}

const STAMP = { add: 0, max: 1, min: 2, smooth_max: 3, smooth_min: 4, blend: 5 };

/** Apply shape values s to heights h (fields): 'add', 'max', 'min', 'smooth_max' / 'smooth_min' (C1, widthM
 * metres) or 'blend' (h (1 - mask) + s mask). A new field. */
export function stamp(h, s, mode = 'add', widthM = 0.0, mask = null) {
    if (!(mode in STAMP)) {
        throw new ValueError(`stamp mode ${pyReprValue(mode)} is one of 'add', 'max', 'min', 'smooth_max', 'smooth_min', 'blend'`);
    }
    if (mode === 'blend' && !mask) throw new ValueError("stamp mode 'blend' needs a mask");
    const R = h.runner;
    const out = R.field(h.h, h.w, 1);
    R.run('compose/stamp', { h, s, mask: mask ?? Gd.dummies(R).f1 }, { outF: out }, { uMode: STAMP[mode], uK: Number(widthM) });
    return out;
}


// ------------------------------------------------------------------------------------------------- shapes ---

function centreOf(spec) {
    const c = spec.centre ?? [0.0, 0.0];
    return [Number(c[0]), Number(c[1])];
}

const PROFILES = { linear: 0, cosine: 1, exp: 2 };

/** A world-space shape's values at a window's cells (see the module doc): a new field. */
export function shape(R, spec, window, seed = 0, opts = {}) {
    const kind = spec.kind;
    const disp = opts.disp ?? null;
    const [h, w] = windowShape(window);
    const D = Gd.dummies(R);
    if (kind === 'cone' || kind === 'bowl' || kind === 'profile') {
        const [cx, cy] = centreOf(spec);
        const u = { uDisp: disp ? 1 : 0, uOrigin: [window.x0 - cx, window.y0 - cy], uCell: window.cell, uR: 1.0, uH: 0.0,
            uLam: 1.0, uRc: 0.0, uER: 0.0, uCount: 0, uKind: 0 };
        let table = null;
        if (kind === 'cone') {
            const prof = spec.profile ?? 'linear';
            if (!(prof in PROFILES)) throw new ValueError(`cone profile ${pyReprValue(prof)} is 'linear', 'cosine' or 'exp'`);
            u.uKind = PROFILES[prof];
            u.uR = Number(spec.radius_m);
            u.uH = Number(spec.height_m);
            if (prof === 'exp') {
                const lam = Number(spec.lambda_m), rc = num(spec.crater_radius_m, 0.0);
                u.uLam = lam;
                u.uRc = rc;
                u.uER = Math.exp(-(u.uR - rc) / lam);
            }
        } else if (kind === 'bowl') {
            u.uKind = 3;
            u.uR = Number(spec.radius_m);
            u.uH = Number(spec.depth_m);
            u.uLam = num(spec.exponent, 2.0);
        } else {
            const xp = spec.r_m.map(Number), fp = spec.z_m.map(Number);
            const t = new Float32Array(4 * xp.length);
            for (let k = 0; k < xp.length; k++) {
                const slope = k + 1 < xp.length ? (fp[k + 1] - fp[k]) / (xp[k + 1] - xp[k]) : 0.0;
                t.set([xp[k], fp[k], slope, 0.0], 4 * k);
            }
            table = R.field(1, xp.length, 4, t);
            u.uKind = 4;
            u.uCount = xp.length;
        }
        const out = R.field(h, w, 1);
        R.run('compose/radial', { disp: disp ?? D.f2, table: table ?? D.f1 }, { outF: out }, u);
        if (table) table.destroy();
        return out;
    }
    if (kind === 'array') {
        let src;
        if ('path' in spec) {
            const a = readNpySync(spec.path);
            if (a.shape.length !== 2) throw new ValueError(`shape 'array': ${spec.path} holds a ${a.shape.length}-d array; a 2-d one is needed`);
            src = R.field(a.shape[0], a.shape[1], 1, Float32Array.from(a.data));
        } else {
            const rows = spec.values;
            const ah = rows.length, aw = rows[0].length;
            const data = new Float32Array(ah * aw);
            rows.forEach((r, j) => data.set(r, j * aw));
            src = R.field(ah, aw, 1, data);
        }
        const out = Gd.sampleWindow(src, { x0: Number(spec.x0), y0: Number(spec.y0), cell: Number(spec.cell) },
            { x0: window.x0, y0: window.y0, cell: window.cell, h, w }, disp);
        src.destroy();
        return out;
    }
    if (UPLIFT_KINDS.includes(kind)) return uplift(R, spec, window, seed, { disp });
    if (kind === 'field') return N.fieldGpu(R, spec.of, window, seed, { disp });
    throw new ValueError(`shape kind ${pyReprValue(kind ?? null)} is one of 'cone', 'bowl', 'profile', 'array', 'dome', 'ridge', ` +
        "'plateau', 'massif', 'field'");
}


// ------------------------------------------------------------------------------------------- uplift shapes ---

/** The CPU part of an uplift shape: its size, warp, texture, the numpy draws of its spurs or peaks (the order
 * compose.py draws them in), as positions relative to the centre. */
export function upliftPlan(spec, seed = 0) {
    const kind = spec.kind;
    const s = Math.trunc(seed) + int(spec.seed, 0);
    const [cx, cy] = centreOf(spec);
    const size = num(spec.radius_m, num(spec.length_m, 10000.0) * 0.5);
    const wm = num(spec.warp_m, 0.08 * size);
    const rng = defaultRng(Math.abs(s) * 7919 + 17);
    const plan = { kind, s, cx, cy, size, warp: wm, texture: num(spec.texture, 0.25), table: [], width: 0.0,
        spine: [0, 0, 0, 0] };
    if (kind === 'dome') {
        // nothing to plan
    } else if (kind === 'plateau') {
        plan.width = Math.max(num(spec.edge_m, 0.2 * size), 1e-9);
    } else if (kind === 'ridge') {
        const az = radians(num(spec.azimuth_deg, 0.0));
        const L = num(spec.length_m, 10000.0), W = num(spec.width_m, 4000.0);
        const dx = Math.sin(az), dy = Math.cos(az);                  // azimuth from north, clockwise
        const ax = cx - (dx * L) / 2, ay = cy - (dy * L) / 2, bx = cx + (dx * L) / 2, by = cy + (dy * L) / 2;
        plan.width = W;
        plan.spine = [ax - cx, ay - cy, bx - cx, by - cy];
        const nSp = int(spec.spurs, 0);
        const sl = num(spec.spur_length_m, 0.45 * W);
        for (let k = 0; k < nSp; k++) {
            const t = (k + 0.5 + rng.uniform(-0.3, 0.3)) / nSp;
            const px = ax + (bx - ax) * t, py = ay + (by - ay) * t;
            const side = k % 2 === 0 ? 1.0 : -1.0;
            const ang = az + side * radians(90.0 + rng.uniform(-25.0, 25.0));
            const ln = sl * rng.uniform(0.6, 1.3);
            const ex = px + Math.sin(ang) * ln, ey = py + Math.cos(ang) * ln;
            plan.table.push([px - cx, py - cy, ex - cx, ey - cy]);
        }
    } else if (kind === 'massif') {
        const nPk = int(spec.peaks, 5);
        for (let k = 0; k < nPk; k++) {
            const a = rng.uniform(0, 2 * Math.PI), r = size * Math.sqrt(rng.uniform(0.0, 0.5));
            const px = cx + r * Math.cos(a), py = cy + r * Math.sin(a);
            const amp = rng.uniform(0.6, 1.0);
            const sigma = size * rng.uniform(0.18, 0.35);
            plan.table.push([px - cx, py - cy, amp, sigma]);
        }
    } else {
        throw new ValueError(`uplift kind ${pyReprValue(kind ?? null)} is 'dome', 'ridge', 'plateau' or 'massif'`);
    }
    return plan;
}

const UPLIFT = { dome: 0, plateau: 1, ridge: 2, massif: 3 };

/** An uplift shape, about 0..1, smooth everywhere (Gaussian falloffs of distances in a domain-warped plane, unions
 * by smooth maximum: no creases, design 4.1), with multi-scale texture at kilometre scales. Common keys: centre
 * [x, y], warp_m (default 8 % of the size), texture (about 1.5 x the texture's relative standard deviation; default
 * 0.25, about +-17 %).
 *   dome      radius_m
 *   ridge     azimuth_deg, length_m, width_m (the spine's half-width scale), spurs (count), spur_length_m
 *   plateau   radius_m, edge_m (the width of the rim's fall)
 *   massif    radius_m, peaks (count)
 * A new field of the window's cells. */
export function uplift(R, spec, window, seed = 0, opts = {}) {
    const plan = upliftPlan(spec, seed);
    const [h, w] = windowShape(window);
    const D = Gd.dummies(R);
    const given = opts.disp ?? null;
    const own = [];
    let disp = given;
    if (plan.warp > 0) {
        // _Noise.warp(wm, max(size * 0.6, 1), s + 11): two fbm fields (std 1/3) scaled to wm metres, read at the
        // unwarped points; every later read is at the warped ones
        const wl = Math.max(plan.size * 0.6, 1.0);
        const sd = plan.s + 11;
        const fx = N.fieldGpu(R, { kind: 'fbm', wavelength_m: wl, octaves: 3, amp: plan.warp }, window, sd * 2 + 101, { disp: given });
        const fy = N.fieldGpu(R, { kind: 'fbm', wavelength_m: wl, octaves: 3, amp: plan.warp }, window, sd * 2 + 102, { disp: given });
        let base = given;
        if (!base) {
            base = R.field(h, w, 2);
            own.push(base);
        }
        disp = Gd.addDisp(base, fx, fy);
        own.push(fx, fy, disp);
    }
    let tex = null;
    if (plan.texture > 0) {
        // kilometre-scale texture only (half the shape's size down to an eighth): peaks and saddles along a spine
        tex = N.fieldGpu(R, { kind: 'fbm', wavelength_m: plan.size * 0.5, octaves: 3 }, window, plan.s + 21, { disp });
        own.push(tex);
    }
    const n = Math.max(plan.table.length, 1);
    const tt = new Float32Array(4 * n);
    plan.table.forEach((row, k) => tt.set(row, 4 * k));
    const table = R.field(1, n, 4, tt);
    own.push(table);
    const out = R.field(h, w, 1);
    R.run('compose/uplift', { disp: disp ?? D.f2, tex: tex ?? D.f1, table }, { outF: out },
        { uDisp: disp ? 1 : 0, uKind: UPLIFT[plan.kind], uOrigin: [window.x0 - plan.cx, window.y0 - plan.cy], uCell: window.cell,
            uSize: plan.size, uWidth: plan.width, uSpine: plan.spine, uCount: plan.table.length, uTex: plan.texture });
    for (const f of own) f.destroy();
    return out;
}

/** The rough start of an erosion run: the uplift shape scaled so its peak is heightM, times (1 - roughness +
 * roughness noise), as the design probe's start (a flat start makes corduroy for millions of years). opts.peak is
 * the shape's maximum over the whole terrain (pass the coarsest level's, so every level scales alike); default:
 * the maximum here (one readback). opts: heightM (600), roughness (0.4), peak, disp. A new field. */
export async function startSurface(R, spec, window, seed = 0, opts = {}) {
    const { heightM = 600.0, roughness = 0.4, peak = null, disp = null } = opts;
    const u = UPLIFT_KINDS.includes(spec.kind) ? uplift(R, spec, window, seed, { disp }) : shape(R, spec, window, seed, { disp });
    const size = num(spec.radius_m, num(spec.length_m, 10000.0) * 0.5);
    const n = N.fieldGpu(R, { kind: 'fbm', wavelength_m: size * 0.3, octaves: 5, amp: 1.5, offset: 0.5 }, window,
        Math.trunc(seed) + 31, { disp });
    const pk = peak === null || peak === undefined ? (await prims(R).stats(u)).max : Number(peak);
    const [h, w] = windowShape(window);
    const out = R.field(h, w, 1);
    R.run('compose/start', { shape: u, rough: n }, { outF: out }, { uHeight: Number(heightM), uPeak: Math.max(pk, 1e-9),
        uRough: Number(roughness) });
    u.destroy();
    n.destroy();
    return out;
}


// ------------------------------------------------------------------------------------------------- flatten ---

/** The flatten areas, checked and normalised (compose.py _areas). */
export function normaliseAreas(areas) {
    const out = [];
    for (const a of areas ?? []) {
        const at = a.at;
        if (at === undefined || at === null || !(num(a.radius, 0) > 0)) {
            throw new ValueError(`a flatten area needs 'at' (x, y) and a positive 'radius' in metres: ${pyStr(a)}`);
        }
        out.push({ at: [Number(at[0]), Number(at[1])], radius: Number(a.radius), falloff: num(a.falloff, 0.0), height: a.height ?? null });
    }
    return out;
}

/** Per row of a window, the first and last column whose centre numpy's float64 np.hypot(x - ax, y - ay) puts at or
 * inside `radius` (first > last: none), and the cells counted: the interval is found by bisection from the column
 * nearest ax, evaluating numpy's expressions in doubles. */
export function discRows(window, ax, ay, radius) {
    const [h, w] = windowShape(window);
    const { x0, y0, cell } = window;
    const rows = new Int32Array(2 * h);
    let count = 0;
    const xs = (i) => x0 + (i + 0.5) * cell;
    for (let j = 0; j < h; j++) {
        const dy = y0 + (j + 0.5) * cell - ay;
        const ins = (i) => Math.hypot(xs(i) - ax, dy) <= radius;
        let ic = Math.min(Math.max(Math.round((ax - x0) / cell - 0.5), 0), w - 1);
        for (const k of [ic - 1, ic + 1]) if (k >= 0 && k < w && Math.abs(xs(k) - ax) < Math.abs(xs(ic) - ax)) ic = k;
        if (!ins(ic)) {
            rows[2 * j] = 1;
            rows[2 * j + 1] = 0;
            continue;
        }
        let lo = 0, hi = ic;                          // the first inside column in [0, ic]
        while (lo < hi) {
            const m = (lo + hi) >> 1;
            if (ins(m)) hi = m;
            else lo = m + 1;
        }
        let a = ic, b = w - 1;                        // the last inside column in [ic, w - 1]
        while (a < b) {
            const m = (a + b + 1) >> 1;
            if (ins(m)) a = m;
            else b = m - 1;
        }
        rows[2 * j] = lo;
        rows[2 * j + 1] = a;
        count += a - lo + 1;
    }
    return { rows, count };
}

// the area table and the hard-edge rows of `areas` on a window (radiusOf: the hard edge's radius per area)
function flattenTables(R, window, areas, radiusOf, heights = []) {
    const [h] = windowShape(window);
    const n = Math.max(areas.length, 1);
    const at = new Float32Array(8 * n);
    const rows = new Int32Array(h * 2 * n);
    for (let j = 0; j < h; j++) for (let a = 0; a < n; a++) rows.set([1, 0], j * 2 * n + 2 * a);
    areas.forEach((a, k) => {
        at.set([a.at[0] - window.x0, a.at[1] - window.y0, a.radius, a.falloff], 8 * k);
        at[8 * k + 4] = heights[k] ?? 0.0;
        const r = radiusOf(a);
        if (r === null) return;
        const { rows: rr } = discRows(window, a.at[0], a.at[1], r);
        for (let j = 0; j < h; j++) rows.set([rr[2 * j], rr[2 * j + 1]], j * 2 * n + 2 * k);
    });
    return { areas: R.field(1, 2 * n, 4, at), rows: R.field(h, 2 * n, 1, rows, 'i32') };
}

function flattenRun(R, window, mode, tables, opts) {
    const [h, w] = windowShape(window);
    const out = R.field(h, w, 1);
    R.run('compose/flatten', { h: opts.h ?? Gd.dummies(R).f1, areas: tables.areas, rows: tables.rows }, { outF: out },
        { uMode: mode, uAreas: opts.count ?? 0, uArea: opts.area ?? 0, uCell: window.cell });
    tables.areas.destroy();
    tables.rows.destroy();
    return out;
}

/** 1 inside the radius, a C1 smoothstep down to 0 at radius + falloff (with no falloff, r <= radius): a new field. */
export function flattenWeight(R, area, window) {
    const [a] = normaliseAreas([area]);
    const t = flattenTables(R, window, [a], (x) => (x.falloff <= 0 ? x.radius : null));
    return flattenRun(R, window, 0, t, { count: 1, area: 0 });
}

/** The rigid-block mask of the erosion stages: 1 inside any area's radius plus its falloff (U = K = 0 there, so
 * rivers route around or fill against it instead of being dammed by a pinned plate). A new field. */
export function flattenMask(R, areas, window) {
    const as = normaliseAreas(areas);
    const t = flattenTables(R, window, as, (x) => x.radius + x.falloff);
    return flattenRun(R, window, 1, t, { count: as.length });
}

/** Each area's flat height: its own 'height', or the median of h inside its radius on the finest level that holds
 * the area whole. levelFields: [[Level, h field], ...], coarsest first. Returns [height, ...]. */
export async function resolveFlatHeights(areas, levelFields) {
    const out = [];
    for (const a of normaliseAreas(areas)) {
        if (a.height !== null) {
            out.push(Number(a.height));
            continue;
        }
        let val = null;
        for (let k = levelFields.length - 1; k >= 0 && val === null; k--) {
            const [lv, h] = levelFields[k];
            const ext = a.radius + a.falloff;
            if (!(lv.contains(a.at[0] - ext, a.at[1] - ext) && lv.contains(a.at[0] + ext, a.at[1] + ext))) continue;
            const { count } = discRows(lv, a.at[0], a.at[1], a.radius);
            if (!count) continue;
            const R = h.runner;
            const mask = flattenRun(R, lv, 1, flattenTables(R, lv, [a], (x) => x.radius), { count: 1 });
            val = await prims(R).median(h, { mask });
            mask.destroy();
        }
        if (val === null) {
            throw new ValueError(`flatten area at (${pyRepr(a.at[0])}, ${pyRepr(a.at[1])}) (radius ${pyRepr(a.radius)} m) is not inside any level`);
        }
        out.push(val);
    }
    return out;
}

/** The exact post pass: each area flattened to its height inside its radius, blended with a C1 falloff of
 * `falloff` metres. Areas apply in order. A new field. */
export function flattenExact(h, window, areas, heights) {
    const as = normaliseAreas(areas).slice(0, heights.length);
    const R = h.runner;
    const t = flattenTables(R, window, as, (x) => (x.falloff <= 0 ? x.radius : null), heights.map(Number));
    return flattenRun(R, window, 2, t, { h, count: as.length });
}

export {
    smoothMin as smooth_min, smoothMax as smooth_max, startSurface as start_surface, flattenWeight as flatten_weight,
    flattenMask as flatten_mask, resolveFlatHeights as resolve_flat_heights, flattenExact as flatten_exact,
};
