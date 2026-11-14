// Port of blender/eidoblend/terrain/core/grid.py at f90c6fc.
//
// Frames, units and grid operations of the terrain core (design section 2.1), with every per-cell operation on the
// GPU (kernels/grid/, through core/gpu.js).
//
// Frames
//     Blender axes: Z up, metres, XY the ground plane (PORT_PLAN.md 2.2: the port keeps every array in this frame;
//     only the mesh, heightAt and the scene-facing helpers convert to three.js's (x, z, -y)).
//     Arrays are [row j, column i] with row 0 the SOUTH edge. A cell centre is at
//         x = x0 + (i + 0.5) * cell,   y = y0 + (j + 0.5) * cell.
//     A window is square: (x0, y0, side, cell, n) with side = n * cell (core/levels.js).
//     Top-down files (PNGs other tools read) have row 0 = NORTH: fromNorthUp / toNorthUp flip once.
//
// Units, in every public parameter: metres (heights, sizes, spacings), years (durations), degrees (angles; their
// tangent inside kernels: tanDeg / degOfTan, computed in doubles on the CPU, PORT_PLAN.md 2.3), m/yr, m^2/yr.
//
// Operations (fields are core/gpu.js fields of one float channel; each call records GPU work and returns a new
// field the caller owns)
//     upsample2(f, 'catmull' | 'bilinear' | 'nearest')   x2, cell-centred: child centres at parent i -/+ 0.25
//     cropUpsample2(f, i0, j0, m, kind, mj)              a child window (m parent cells from parent cell (i0, j0))
//     boxDown(f, k)                                      integer box average
//     resampleBox(f, srcCell, dstCell, nOut)             exact area-weighted average to any coarser pixel
//     sampleWindow(src, srcWindow, window, disp)         sample_bilinear at a window's cell centres (+ a displacement)
//     edgeDistance(R, n) / borderRamp(R, n, band, kind)  the distance from the edge, the border band's pin weight
//     gradient(h, cell) / slopeDeg / aspectDeg           central differences (np.gradient), the references' slope
//     fromNorthUp(f) / toNorthUp(f)                      the row flip
//     indexOf(x, y, x0, y0, cell), sampleBilinear(a, shape, x0, y0, cell, x, y): per-query numbers (a few points,
//     never a level's cells), in doubles exactly as numpy
//
// Where this differs from grid.py, and why (each checked against its numpy original, tests/core_inputs/):
//   - numpy computes in float64 and rounds to float32 once; the kernels are float32, in numpy's order of operations
//     (resampling: within a few ulp of the field's largest value).
//   - cell_centres (float64 meshgrids of every cell) is not ported: a kernel makes a cell's centre from its window
//     (common.wgsl world_xy), and the shape and noise functions take the window (core/compose.js, world_noise.js).
//   - resample_box's running sums (np.cumsum) become a gather of the same area average per pixel
//     (kernels/grid/resample_axis.wgsl), whose pixel edges come from a table computed in doubles as numpy computes
//     them; in float32 the difference of two running sums would lose the small differences of large sums.
//   - edge_distance returns float32 holding its integers exactly (numpy's int64; every consumer compares or scales it).

import { ValueError, pyRound, pyReprValue, pyStr } from './levels.js';

export const DEG = Math.PI / 180.0;
// Catmull-Rom weights at t = 0.25 and t = 0.75 (p0, p1, p2, p3): the cell-centred x2 child sits at parent i + 0.25
// (between p_i and p_i+1, t = 0.25) and at i - 0.25 (between p_i-1 and p_i, t = 0.75); kernels/grid/upsample2.wgsl
export const CR25 = [-0.0703125, 0.8671875, 0.2265625, -0.0234375];
export const CR75 = [...CR25].reverse();
const KINDS = { catmull: 0, bilinear: 1, nearest: 2 };


// --------------------------------------------------------------------------------------------- frames, units ---

/** An angle in degrees as the tangent kernels use (a number, or an array of numbers): np.tan(deg * DEG). */
export function tanDeg(deg) {
    return Array.isArray(deg) ? deg.map((d) => Math.tan(d * DEG)) : Math.tan(deg * DEG);
}

/** The angle in degrees of a tangent: np.degrees(np.arctan(t)). */
export function degOfTan(t) {
    const f = (x) => Math.atan(x) * (180.0 / Math.PI);
    return Array.isArray(t) ? t.map(f) : f(t);
}

/** Fractional array indices [i, j] of a world point: cell centres are whole numbers. */
export function indexOf(x, y, x0, y0, cell) {
    return [(x - x0) / cell - 0.5, (y - y0) / cell - 0.5];
}

/** The bilinear value of a cell-centred host grid `a` (row-major [h, w]) at world (x, y), clamped to the outermost
 * cell centres: sample_bilinear for a few queries (x, y numbers or arrays of numbers), in doubles. */
export function sampleBilinear(a, shape, x0, y0, cell, x, y) {
    const [h, w] = shape;
    const one = (px, py) => {
        let [fi, fj] = indexOf(px, py, x0, y0, cell);
        fi = Math.min(Math.max(fi, 0.0), w - 1.0);
        fj = Math.min(Math.max(fj, 0.0), h - 1.0);
        const i0 = Math.min(Math.floor(fi), Math.max(w - 2, 0));
        const j0 = Math.min(Math.floor(fj), Math.max(h - 2, 0));
        const ti = fi - i0, tj = fj - j0;
        const i1 = Math.min(i0 + 1, w - 1), j1 = Math.min(j0 + 1, h - 1);
        return (a[j0 * w + i0] * (1 - ti) + a[j0 * w + i1] * ti) * (1 - tj) + (a[j1 * w + i0] * (1 - ti) + a[j1 * w + i1] * ti) * tj;
    };
    return Array.isArray(x) ? x.map((px, k) => one(px, y[k])) : one(x, y);
}


// ------------------------------------------------------------------------------------------- GPU plumbing ---

const DUMMIES = new WeakMap();

/** A runner's 1 x 1 stand-in fields, for the bindings a kernel's mode does not read. */
export function dummies(R) {
    let d = DUMMIES.get(R);
    if (!d) {
        d = { f1: R.field(1, 1, 1), f2: R.field(1, 1, 2), u1: R.field(1, 1, 1, null, 'u32') };
        DUMMIES.set(R, d);
    }
    return d;
}

function oneChannel(f, what) {
    if (!f || typeof f.h !== 'number' || !f.runner) throw new TypeError(`${what}: a GPU field (core/gpu.js) is needed`);
    if (f.kind !== 'f32') throw new TypeError(`${what}: a float field is needed, got ${f.format}`);
}

function shapeOf(n) {
    return typeof n === 'number' ? [n, n] : [n[0], n[1]];
}

const ARITH = { add: 0, mul: 1, affine: 2, sub: 3, fill: 4, disp: 5, scale: 6 };

/** Cell-by-cell arithmetic (kernels/grid/arith.wgsl), float32 with one rounding per operation as numpy's float32:
 * 'add' a + b, 'mul' a * b, 'sub' a - b, 'affine' off + amp a, 'scale' a amp, 'fill' (a constant off; opts.shape).
 * Returns a new field (or opts.out). */
export function arith(R, op, a = null, b = null, opts = {}) {
    const D = dummies(R);
    const shape = opts.shape ?? (a ? [a.h, a.w] : null);
    const out = opts.out ?? R.field(shape[0], shape[1], 1);
    R.run('grid/arith', { a: a ?? D.f1, b: b ?? D.f1, c: D.f1 }, { outF: out, outD: D.f2 },
        { uOp: ARITH[op], uAmp: opts.amp ?? 1.0, uOff: opts.off ?? 0.0 });
    return out;
}

/** A constant field of shape [h, w] (a Fields entry set to a number). */
export function fill(R, shape, value) {
    return arith(R, 'fill', null, null, { shape: shapeOf(shape), off: value });
}

/** The displacement field (base.x + dx, base.y + dy), rg32f: a warp's moved sample points. */
export function addDisp(base, dx, dy) {
    const R = dx.runner;
    const D = dummies(R);
    const out = R.field(dx.h, dx.w, 2);
    R.run('grid/arith', { a: base, b: dx, c: dy }, { outF: D.f1, outD: out }, { uOp: ARITH.disp, uAmp: 1.0, uOff: 0.0 },
        [Math.ceil(dx.w / 16), Math.ceil(dx.h / 16), 1]);
    return out;
}


// ------------------------------------------------------------------------------------------------ resampling ---

/** The x2 child of a window m parent cells wide (mj tall, default m) starting at parent cell (i0, j0): a field of
 * (2 mj, 2 m) cells. Reads 2 parent cells around the window (clamped at the parent's edge), so the result equals
 * upsample2(f) cropped there. kind 'catmull' (h and bed), 'bilinear' (masks, A, qs) or 'nearest'. */
export function cropUpsample2(f, i0, j0, m, kind = 'catmull', mj = null, out = null) {
    oneChannel(f, 'crop_upsample2');
    if (!(kind in KINDS)) throw new ValueError(`upsample kind ${pyReprValue(kind)} is 'catmull', 'bilinear' or 'nearest'`);
    mj = mj ?? m;
    const R = f.runner;
    out = out ?? R.field(2 * mj, 2 * m, 1);
    R.run('grid/upsample2', { src: f }, { outF: out }, { uOrigin: [i0, j0], uKind: KINDS[kind] });
    return out;
}

/** x2 cell-centred upsampling (child cells nest 2 x 2 in each parent cell): 'catmull' (Catmull-Rom, for h and
 * bed), 'bilinear' (masks, A, qs) or 'nearest'. */
export function upsample2(f, kind = 'catmull') {
    return cropUpsample2(f, 0, 0, f.w, kind, f.h);
}

/** Integer box average by k on both axes (the shape must divide). */
export function boxDown(f, k) {
    oneChannel(f, 'box_down');
    if (f.h % k || f.w % k) throw new ValueError(`box_down: shape (${f.h}, ${f.w}) does not divide by ${k}`);
    const R = f.runner;
    const out = R.field(f.h / k, f.w / k, 1);
    R.run('grid/box_down', { src: f }, { outF: out }, { uF: k });
    return out;
}

// the pixel edges of _box_axis along an axis of n cells: (floor index, fraction) per edge, in doubles as numpy
function edgeTable(R, r, nOut, n) {
    const t = new Float32Array(2 * (nOut + 1));
    for (let k = 0; k <= nOut; k++) {
        const e = Math.min(k * r, n);
        const kk = Math.min(Math.floor(e), n - 1);
        t[2 * k] = kk;
        t[2 * k + 1] = e - kk;
    }
    return R.field(1, nOut + 1, 2, t);
}

/** The exact area-weighted (box) average of a grid of `srcCell` pixels onto `dstCell` pixels over the same extent
 * from the same origin (the judge's "box-average to the reference's pixel"). nOut defaults to the whole pixels that
 * fit: floor(n srcCell / dstCell) per axis; a number or [rows, columns]. dstCell must be at least srcCell. */
export function resampleBox(f, srcCell, dstCell, nOut = null) {
    oneChannel(f, 'resample_box');
    const r = Number(dstCell) / Number(srcCell);
    if (r < 1.0 - 1e-9) {
        throw new ValueError(`resample_box averages down; dst_cell ${pyStr(dstCell)} m is finer than src_cell ${pyStr(srcCell)} m`);
    }
    const [h, w] = [f.h, f.w];
    if (nOut === null || nOut === undefined) nOut = [Math.floor(h / r + 1e-6), Math.floor(w / r + 1e-6)];
    else if (typeof nOut === 'number') nOut = [nOut, nOut];
    const ri = pyRound(r);
    if (Math.abs(r - ri) < 1e-9 && h % ri === 0 && w % ri === 0 && nOut[0] === h / ri && nOut[1] === w / ri) return boxDown(f, ri);
    const R = f.runner;
    const e0 = edgeTable(R, r, nOut[0], h), e1 = edgeTable(R, r, nOut[1], w);
    const mid = R.field(nOut[0], w, 1), out = R.field(nOut[0], nOut[1], 1);
    R.run('grid/resample_axis', { src: f, edges: e0 }, { outF: mid }, { uAxis: 0, uR: r });
    R.run('grid/resample_axis', { src: mid, edges: e1 }, { outF: out }, { uAxis: 1, uR: r });
    for (const t of [e0, e1, mid]) t.destroy();
    return out;
}

/** sample_bilinear of a source grid (window { x0, y0, cell }) at the cell centres of a target window ({ x0, y0, cell,
 * n } or { ..., h, w }), each moved by `disp` (an rg32f field of metres, or null): a field of the target's cells. */
export function sampleWindow(src, srcWindow, window, disp = null) {
    oneChannel(src, 'sample_bilinear');
    const R = src.runner;
    const [h, w] = window.h !== undefined ? [window.h, window.w] : [window.n, window.n];
    const out = R.field(h, w, 1);
    R.run('grid/sample_bilinear', { src, disp: disp ?? dummies(R).f2 }, { outF: out },
        { uDisp: disp ? 1 : 0, uOrigin: [window.x0 - srcWindow.x0, window.y0 - srcWindow.y0], uCell: window.cell,
            uSrcCell: srcWindow.cell });
    return out;
}


// ---------------------------------------------------------------------------------------------- the border ---

/** The Chebyshev distance of every cell of an (n, n) window (or an [h, w] shape) from its nearest edge, in cells
 * (0 on the edge row): float32 holding exact integers. */
export function edgeDistance(R, n) {
    const [h, w] = shapeOf(n);
    const out = R.field(h, w, 1);
    R.run('grid/border', {}, { outF: out }, { uMode: 0, uBand: 1.0 });
    return out;
}

/** The border band's pin weight (design section 2.2): 1 on the edge, falling to 0 at `band` cells in. 'smooth' is
 * 1 - smoothstep(0, band, d), C1 so the blend leaves no crease line; 'linear' is 1 - d / band. */
export function borderRamp(R, n, band = 16, kind = 'smooth') {
    const [h, w] = shapeOf(n);
    const out = R.field(h, w, 1);
    R.run('grid/border', {}, { outF: out }, { uMode: kind === 'smooth' ? 1 : 2, uBand: band });
    return out;
}


// --------------------------------------------------------------------------------------------- derivatives ---

function derive(f, cell, mode, opts = {}) {
    oneChannel(f, 'gradient');
    const R = f.runner;
    const a = R.field(f.h, f.w, 1);
    const b = mode === 0 ? R.field(f.h, f.w, 1) : dummies(R).f1;
    R.run('grid/gradient', { h: f }, { outA: a, outB: b },
        { uMode: mode, uCell: cell, uZ: opts.z ?? 1.0, uLight: opts.light ?? [0.0, 0.0, 1.0] },
        [Math.ceil(f.w / 16), Math.ceil(f.h / 16), 1]);
    return mode === 0 ? { gx: a, gy: b } : a;
}

/** { gx: dh/dx east, gy: dh/dy north } by central differences (one-sided on the edges), as np.gradient: rows run
 * north. Two new fields. */
export const gradient = (h, cell) => derive(h, cell, 0);

/** Slope in degrees by central differences, never clipped: the reference JSONs' definition (shape_stats). */
export const slopeDeg = (h, cell) => derive(h, cell, 1);

/** The compass direction the slope faces (downhill), degrees clockwise from north, 0..360. */
export const aspectDeg = (h, cell) => derive(h, cell, 2);

/** io.hillshade's kernel: (light [lx, ly, lz], z the height factor). core/io.js hillshade() calls it. */
export const shade = (h, cell, light, z) => derive(h, cell, 3, { light, z });


// ------------------------------------------------------------------------------------------------- frames ---

/** A top-down field (row 0 = north, files') in this package's frame (row 0 = south), as a new field. */
export function fromNorthUp(f) {
    oneChannel(f, 'from_north_up');
    const R = f.runner;
    const out = R.field(f.h, f.w, 1);
    R.run('grid/flip_rows', { src: f }, { outF: out });
    return out;
}

export const toNorthUp = fromNorthUp;

export {
    tanDeg as tan_deg, degOfTan as deg_of_tan, indexOf as index_of, sampleBilinear as sample_bilinear,
    cropUpsample2 as crop_upsample2, boxDown as box_down, resampleBox as resample_box,
    edgeDistance as edge_distance, borderRamp as border_ramp, slopeDeg as slope_deg, aspectDeg as aspect_deg,
    fromNorthUp as from_north_up, toNorthUp as to_north_up,
};
