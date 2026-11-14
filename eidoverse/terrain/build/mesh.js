// Port of blender/eidoblend/terrain/build/mesh.py at f90c6fc.
//
// The terrain's ring mesh (design section 8, PORT_PLAN.md 7.3): one mesh that draws every level as a ring (the
// level's window minus its child's window), so vertex density falls off with distance from the focus. Seams are
// stitched, the outermost ring has a skirt, and heightAt / normalAt read exactly its triangles.
//
//     import { buildRings, makeGeometry } from './build/mesh.js';
//     const rm = await buildRings(R, levels, heights, { cores: true });   // R: the GPU runner (core/gpu.js)
//     rm.heightAt(x, y)              // metres at Blender (x, y), on rm's triangles; numbers or arrays
//     rm.normalAt(x, y)              // the shading normal there, Blender axes
//     const geometry = makeGeometry(THREE, rm);   // a BufferGeometry in three.js axes, one group per ring
//
// Frames (design 2.1, PORT_PLAN.md 2.2). Blender axes, metres, everywhere but the geometry's buffers: a level is a
// square window, its south-west corner (x0, y0), n cells of `cell` metres; its field values sit at the cell centres
// x = x0 + (i + 0.5) cell, y = y0 + (j + 0.5) cell, arrays [row j, column i] with row 0 the south edge. Every window
// lies on its parent's cell grid and halves its cell, so every window edge is a whole number of finest cells from
// the outermost window's corner. The rings are built on that integer lattice, so a position two rings share is the
// same number in both. The geometry's positions are three.js's (x, z, -y): a rotation, so triangles keep their
// winding and face up.
//
// Rings. A ring's vertices sit on its level's cell corners every `stride` cells (stride = round(n / meshRes): 2 at
// 1024 cells), plus the lines its seams need (its hole's edges, its parent's lines). With cores (a focus is set) the
// finest level is also drawn as cores: half its side at half the stride, down to stride 1. Each grid quad is split
// along its (i, j) - (i + 1, j + 1) diagonal and the triangles are written explicitly.
//
// Heights. A vertex takes its level's field at the cell corner by Catmull-Rom (weights -1, 9, 9, -1 over 16 per
// axis). Seams: a ring's outermost vertex row takes the parent's straight edge there; where two rings have a vertex
// at the same place it is one shared vertex; the parent's quads along the hole are drawn as fans through the
// child's in-between vertices, so no T-junction is left. Skirt: the outermost ring hangs a vertical skirt from its
// border down to SKIRT_DROP_M below the lowest border vertex.
//
// Where this differs from mesh.py, and why (PORT_PLAN.md 7.3, C3, C4):
//   - The per-vertex work runs as GPU kernels (kernels/mesh/: ring_index, ring_heights, ring_vertices, ring_quads,
//     ring_fans, skirt_min, skirt, normals) and is read back once; JavaScript keeps what is not per vertex: the
//     windows, the ring specs, each ring's lattice lines (a few thousand integers a ring), the tables the kernels
//     read (rows' first vertices and triangles, the seams' parent segments, the fan list), and per-query sampling.
//   - Heights are evaluated in float32 (WGSL has no float64; Blender evaluates in float64 and rounds once): within
//     13.5 ulp of each corner's largest tap (measured worst 3), PORT_PLAN.md 2.3. x and z are Blender's lattice
//     lines, float32(origin + lattice * unit) made in JavaScript doubles: bit-equal.
//   - vertex_normals is a gather over the corners sorted by vertex (core/prims.js sortPairs), not np.bincount's
//     scatter: the same sum in a fixed order, float32 against float64 (within 1e-5 rad).
//   - No mask attributes (make_object writes every mask as a point attribute, about 30 on 3M vertices): the
//     material reads per-level data textures (PORT_PLAN.md 3.5); WebGPU's default maxVertexAttributes is 16.
//   - One geometry group per ring (C4): material 0, the near material, for the main and hero rings and the cores;
//     material 1, the far material, for the context rings; the skirt takes its ring's. mesh.py at f90c6fc writes
//     one material; the index per ring is the surfacing round's (SURFACING_DESIGN.md 3.7), reserved here. Until the
//     last wave both slots hold the clay.
//   - The skirt is flat-shaded in Blender; its vertices here carry their side's outward normal (the face normal of
//     every skirt face but the four at the corners).
//   - make_object's 'UVMap' (u = x, v = y, world metres) is the geometry's uv attribute (it is the same at every
//     corner of a vertex).
//   - rebuild(layout, verts) (a mesh rebuilt from a reopened .blend) is not ported: a three.js scene keeps its
//     Terrain; Terrain.load rebuilds from the fields.

import { keyToFloat, lineGroups, listShape, prims } from '../core/prims.js';
import { pyRound } from '../core/levels.js';

export const MESH_RES = 512;            // vertices per side a level is drawn at: stride = round(n / MESH_RES)
export const SKIRT_DROP_M = 50.0;       // the skirt's bottom, below the lowest border vertex
const NONE = 0xFFFFFFFF;


// ------------------------------------------------------------------------------------------------ windows ---

/** A level's square window: south-west corner (x0, y0), n cells of `cell` metres. */
export class Window {
    constructor(x0, y0, cell, n) {
        this.x0 = x0;
        this.y0 = y0;
        this.cell = cell;
        this.n = n;
    }

    get side() { return this.cell * this.n; }
}

/** A Window from a level: anything with x0, y0, cell and n, or the tuple [x0, y0, side, cell, n] of design 2.2. */
export function asWindow(level) {
    if (level instanceof Window) return level;
    if (Array.isArray(level)) {
        const [x0, y0, _side, cell, n] = level;
        return new Window(Number(x0), Number(y0), Number(cell), Math.trunc(n));
    }
    if (level && ['x0', 'y0', 'cell', 'n'].every((k) => level[k] !== undefined)) {
        return new Window(Number(level.x0), Number(level.y0), Number(level.cell), Math.trunc(level.n));
    }
    throw new TypeError('asWindow: a level, a Window or [x0, y0, side, cell, n] is needed');
}

const assertion = (msg) => Object.assign(new Error(msg), { name: 'AssertionError' });

/** { origin: [X, Y] metres, unit: metres, iwins: [{ x0, y0, ci, n, x1, y1 }] } for nested windows (integer lattice
 * units of the finest cell from the outermost window's corner); throws if a window is off its parent's grid or a
 * cell is not the finest cell times a power of two (mesh.py _integer_windows). */
export function integerWindows(windows) {
    const u = Math.min(...windows.map((w) => w.cell));
    const X = windows[0].x0, Y = windows[0].y0;
    const out = [];
    windows.forEach((w, k) => {
        const ci = w.cell / u;
        const rci = pyRound(ci);
        if (Math.abs(ci - rci) > 1e-6 * ci || (rci & (rci - 1))) {
            throw new RangeError(`level ${k}: cell ${w.cell} m is not the finest cell ${u} m times a power of two`);
        }
        const fx = (w.x0 - X) / u, fy = (w.y0 - Y) / u;
        if (Math.abs(fx - pyRound(fx)) > 1e-5 || Math.abs(fy - pyRound(fy)) > 1e-5) {
            throw new RangeError(`level ${k}: window corner (${w.x0}, ${w.y0}) is not on the finest cell grid from the ` +
                `outermost corner (${X}, ${Y}); levels must be snapped to their parent cell grid`);
        }
        const iw = { x0: pyRound(fx), y0: pyRound(fy), ci: rci, n: Math.trunc(w.n) };
        iw.x1 = iw.x0 + iw.n * iw.ci;
        iw.y1 = iw.y0 + iw.n * iw.ci;
        out.push(iw);
    });
    for (let k = 1; k < out.length; k++) {
        const p = out[k - 1], c = out[k];
        if (!(p.x0 <= c.x0 && c.x1 <= p.x1 && p.y0 <= c.y0 && c.y1 <= p.y1)) throw new RangeError(`level ${k} is not inside level ${k - 1}`);
        if ((c.x0 - p.x0) % p.ci || (c.y0 - p.y0) % p.ci || (c.x1 - p.x0) % p.ci || (c.y1 - p.y0) % p.ci) {
            throw new RangeError(`level ${k}: window edges are not on level ${k - 1}'s cell grid`);
        }
    }
    return { origin: [X, Y], unit: u, iwins: out };
}


// --------------------------------------------------------------------------------------------------- rings ---

/** One ring: the window (integer units), its vertex spacing (units) and the level whose field it draws. */
export class RingSpec {
    constructor(level, x0, y0, x1, y1, sp) {
        Object.assign(this, { level, x0, y0, x1, y1, sp });
    }

    asList() { return [this.level, this.x0, this.y0, this.x1, this.y1, this.sp]; }
}

const floorDiv = (a, b) => Math.floor(a / b);

/** The rings for nested integer windows (mesh.py plan_rings): one per level at stride round(n / meshRes), then
 * (cores) the finest level again at half the side and half the stride, down to stride 1, centred in it and on its
 * parent's lattice. */
export function planRings(iwins, meshRes = MESH_RES, cores = false) {
    const rings = [];
    iwins.forEach((w, k) => {
        const stride = Math.max(1, pyRound(w.n / meshRes));
        rings.push(new RingSpec(k, w.x0, w.y0, w.x1, w.y1, stride * w.ci));
    });
    if (cores) {
        const k = iwins.length - 1;
        const w = iwins[k];
        while (rings[rings.length - 1].sp > w.ci) {
            const P = rings[rings.length - 1];
            const sp = Math.max(w.ci, floorDiv(floorDiv(P.sp, 2), w.ci) * w.ci);
            const side = floorDiv(floorDiv(P.x1 - P.x0, 2), P.sp) * P.sp;
            const margin = 2 * P.sp;
            if (side < 8 * sp || side > (P.x1 - P.x0) - 2 * margin) break;
            const cx = (P.x0 + P.x1) / 2.0, cy = (P.y0 + P.y1) / 2.0;
            const snap = (c, lo, hi) => {           // on the parent's lattice, at least `margin` inside it
                const v = lo + pyRound((c - side / 2.0 - lo) / P.sp) * P.sp;
                const top = lo + floorDiv(hi - margin - side - lo, P.sp) * P.sp;
                return Math.min(Math.max(v, lo + margin), top);
            };
            const x0 = snap(cx, P.x0, P.x1), y0 = snap(cy, P.y0, P.y1);
            rings.push(new RingSpec(k, x0, y0, x0 + side, y0 + side, sp));
        }
    }
    return rings;
}

/** The index of the first element > v ('right') or >= v ('left') of an ascending array (np.searchsorted). */
export function searchsorted(arr, v, side = 'left') {
    let lo = 0, hi = arr.length;
    if (side === 'right') {
        while (lo < hi) {
            const m = (lo + hi) >>> 1;
            if (arr[m] <= v) lo = m + 1; else hi = m;
        }
    } else {
        while (lo < hi) {
            const m = (lo + hi) >>> 1;
            if (arr[m] < v) lo = m + 1; else hi = m;
        }
    }
    return lo;
}

function find(sorted, v) {
    const i = Math.min(searchsorted(sorted, v), sorted.length - 1);
    if (sorted[i] !== v) throw assertion('ring lattice: a seam line is missing from the parent lattice');
    return i;
}

function uniqueSorted(values) {
    const a = Int32Array.from(new Set(values)).sort();
    return a;
}

/** np.interp(x, xp, fp) for one x, numpy's own arithmetic (numpy/_core/src/multiarray/compiled_base.c arr_interp):
 * the left / right values outside, an exact node's own value, else slope * (x - xp[j]) + fp[j]. */
export function npInterp(x, xp, fp) {
    const n = xp.length;
    if (Number.isNaN(x)) return x;
    if (x > xp[n - 1]) return fp[n - 1];
    if (x < xp[0]) return fp[0];
    const j = searchsorted(xp, x, 'right') - 1;
    if (j === n - 1) return fp[j];
    if (xp[j] === x) return fp[j];
    const slope = (fp[j + 1] - fp[j]) / (xp[j + 1] - xp[j]);
    let r = slope * (x - xp[j]) + fp[j];
    if (Number.isNaN(r)) {
        r = slope * (x - xp[j + 1]) + fp[j + 1];
        if (Number.isNaN(r) && fp[j] === fp[j + 1]) r = fp[j];
    }
    return r;
}

// The integer tables of one ring, in one i32 list for all rings (the kernels' TABLE layout), at offsets of the
// ring's nx and ny:
//   [0, ny)                 rowStart: own vertices in the rows before j
//   [ny, ny + nx)           border rows (a ring with a parent): -1 - the parent's column of a shared vertex, else
//                           the vertex's rank among the row's own
//   [ny + nx, 2ny + nx)     border columns: -1 - the parent's row of a shared vertex, else 0
//   [2ny + nx, 2ny + 2nx)   each column's cell-corner index on its level's grid
//   [2ny + 2nx, 3ny + 2nx)  each row's
//   [3ny + 2nx, 3ny + 5nx)  per column (m, o, L): the parent segment of a border row point (np.interp's m with
//                           xp[m] <= x, o = x - xp[m], L = xp[m + 1] - xp[m]; L = 0 on a parent vertex)
//   [3ny + 5nx, 6ny + 5nx)  per row, the same along a border column
//   [6ny + 5nx, 7ny + 5nx - 1)   (a, b, c) triangles in the quad rows before j
//   [7ny + 5nx - 1, 8ny + 5nx - 2)   (a, c, d) triangles in the quad rows before j
const tableSize = (nx, ny) => 8 * ny + 5 * nx - 2;

/** Lattices, vertex counts, triangle counts and tables of the rings (mesh.py _topology without the per-vertex
 * arrays): { rings, nv, terrainTriangles, perimeter, tables (Int32Array), fans (Int32Array) }. The order is a pure
 * function of the specs, as Blender's. */
export function topology(specs, iwins, skirt = true) {
    const rings = [];
    let nv = 0;
    specs.forEach((s, k) => {
        let hole = null;
        if (k + 1 < specs.length) {
            const c = specs[k + 1];
            hole = [c.x0, c.y0, c.x1, c.y1];
            if (!(s.x0 < c.x0 && c.x1 < s.x1 && s.y0 < c.y0 && c.y1 < s.y1)) {
                throw new RangeError(`ring ${k + 1} must lie strictly inside ring ${k} (got [${c.asList()}] in [${s.asList()}])`);
            }
        }
        const P = k ? rings[k - 1] : null;
        const xv = [], yv = [];
        for (let v = s.x0; v < s.x1 + 1; v += s.sp) xv.push(v);
        for (let v = s.y0; v < s.y1 + 1; v += s.sp) yv.push(v);
        xv.push(s.x0, s.x1);
        yv.push(s.y0, s.y1);
        if (hole) {
            xv.push(hole[0], hole[2]);
            yv.push(hole[1], hole[3]);
        }
        if (P) {                              // the parent's lines that meet this ring's border: shared vertices
            for (const v of P.xs) if (v >= s.x0 && v <= s.x1) xv.push(v);
            for (const v of P.ys) if (v >= s.y0 && v <= s.y1) yv.push(v);
        }
        const xs = uniqueSorted(xv), ys = uniqueSorted(yv);
        const nx = xs.length, ny = ys.length;
        const r = { k, spec: s, hole, xs, ys, nx, ny, v0: nv, holeLines: null, parLines: null };
        // the hole's inner rows and columns
        let jLo = 1, jHi = 0, iLo = 1, iHi = 0;
        if (hole) {
            const jb = find(ys, hole[1]), jt = find(ys, hole[3]), il = find(xs, hole[0]), ir = find(xs, hole[2]);
            r.holeLines = [jb, jt, il, ir];
            jLo = jb + 1; jHi = jt - 1; iLo = il + 1; iHi = ir - 1;
        }
        r.holeInner = [jLo, jHi, iLo, iHi];
        const holeCols = hole ? iHi - iLo + 1 : 0;
        const holeRow = (j) => j >= jLo && j <= jHi;
        const tab = new Int32Array(tableSize(nx, ny));
        const T = { row: 0, bx: ny, by: ny + nx, mxc: 2 * ny + nx, myc: 2 * ny + 2 * nx, seamX: 3 * ny + 2 * nx,
            seamY: 3 * ny + 5 * nx, abc: 6 * ny + 5 * nx, acd: 7 * ny + 5 * nx - 1 };
        let countMx = 0;
        const my = new Uint8Array(ny);
        if (P) {
            r.parLines = [find(P.ys, s.y0), find(P.ys, s.y1), find(P.xs, s.x0), find(P.xs, s.x1)];
            for (let i = 0; i < nx; i++) {
                const ip = Math.min(searchsorted(P.xs, xs[i]), P.xs.length - 1);
                if (P.xs[ip] === xs[i]) {
                    tab[T.bx + i] = -1 - ip;
                    countMx++;
                } else {
                    tab[T.bx + i] = i - countMx;
                }
                const m = searchsorted(P.xs, xs[i], 'right') - 1;   // xp[m] <= x (x lies inside the parent's lines)
                const e = T.seamX + 3 * i;
                tab[e] = m;
                if (P.xs[m] !== xs[i] && m < P.xs.length - 1) {
                    tab[e + 1] = xs[i] - P.xs[m];
                    tab[e + 2] = P.xs[m + 1] - P.xs[m];
                }
            }
            for (let j = 0; j < ny; j++) {
                const jp = Math.min(searchsorted(P.ys, ys[j]), P.ys.length - 1);
                if (P.ys[jp] === ys[j]) {
                    tab[T.by + j] = -1 - jp;
                    my[j] = 1;
                }
                const m = searchsorted(P.ys, ys[j], 'right') - 1;
                const e = T.seamY + 3 * j;
                tab[e] = m;
                if (P.ys[m] !== ys[j] && m < P.ys.length - 1) {
                    tab[e + 1] = ys[j] - P.ys[m];
                    tab[e + 2] = P.ys[m + 1] - P.ys[m];
                }
            }
        }
        // own vertices per row, numbered in row-major order from v0
        let own = 0;
        for (let j = 0; j < ny; j++) {
            tab[T.row + j] = own;
            if (P && (j === 0 || j === ny - 1)) own += nx - countMx;
            else own += nx - (holeRow(j) ? holeCols : 0) - (P && my[j] ? 2 : 0);
        }
        r.own = own;
        nv += own;
        // the cell-corner indices on the level's grid (mesh.py _taps)
        const w = iwins[s.level];
        for (let i = 0; i < nx; i++) {
            const off = xs[i] - w.x0;
            if (off % w.ci) throw assertion("a ring vertex is not on its level's cell corners");
            tab[T.mxc + i] = off / w.ci;
        }
        for (let j = 0; j < ny; j++) {
            const off = ys[j] - w.y0;
            if (off % w.ci) throw assertion("a ring vertex is not on its level's cell corners");
            tab[T.myc + j] = off / w.ci;
        }
        // the lattice quads' triangles per row: what ring_quads drops (see there)
        let nAbc = 0, nAcd = 0;
        const [jb, jt, il, ir] = r.holeLines ?? [-1, -1, -1, -1];
        for (let j = 0; j < ny - 1; j++) {
            tab[T.abc + j] = nAbc;
            tab[T.acd + j] = nAcd;
            let a = nx - 1, c = nx - 1;
            if (hole && j >= jb && j < jt) {
                a -= ir - (il - 1);
                c -= ir + 1 - il;
            } else if (hole && j === jt) {
                a -= ir - il;
            } else if (hole && j === jb - 1) {
                c -= ir - il;
            }
            nAbc += a;
            nAcd += c;
        }
        r.nAbc = nAbc;
        r.nAcd = nAcd;
        r.tab = tab;
        rings.push(r);
    });
    // the seam fans, in mesh.py's order, and every ring's triangle range
    let triBase = 0;
    rings.forEach((r, k) => {
        r.fans = null;
        r.nFanTris = 0;
        if (r.hole) {
            const C = rings[k + 1];
            const [jb, jt, il, ir] = r.holeLines;
            const list = [];
            for (let i = il; i < ir; i++) {
                const lo = searchsorted(C.xs, r.xs[i], 'right'), hi = searchsorted(C.xs, r.xs[i + 1], 'left');
                list.push([jb - 1, i, 0, lo, hi], [jt, i, 1, lo, hi]);
            }
            for (let j = jb; j < jt; j++) {
                const lo = searchsorted(C.ys, r.ys[j], 'right'), hi = searchsorted(C.ys, r.ys[j + 1], 'left');
                list.push([j, il - 1, 2, lo, hi], [j, ir, 3, lo, hi]);
            }
            const nf = list.length;
            const fan = new Int32Array(nf + 1 + 5 * nf);
            let t = 0;
            list.forEach((f, q) => {
                fan[q] = t;
                t += f[4] - f[3] + 1;
                fan.set(f, nf + 1 + 5 * q);
            });
            fan[nf] = t;
            r.fans = fan;
            r.nFans = nf;
            r.nFanTris = t;
        }
        r.triBase = triBase;
        r.triangles = r.nAbc + r.nAcd + r.nFanTris;
        triBase += r.triangles;
    });
    const terrainTriangles = triBase;
    const r0 = rings[0];
    const perimeter = skirt ? 2 * r0.nx + 2 * r0.ny - 4 : 0;
    // one list of every ring's tables, one of the fans
    let tabLen = 0, fanLen = 0;
    for (const r of rings) {
        r.tabAt = tabLen;
        tabLen += r.tab.length;
        r.fanAt = fanLen;
        fanLen += r.fans ? r.fans.length : 0;
    }
    const tables = new Int32Array(Math.max(tabLen, 1));
    const fans = new Int32Array(Math.max(fanLen, 1));
    for (const r of rings) {
        tables.set(r.tab, r.tabAt);
        if (r.fans) fans.set(r.fans, r.fanAt);
    }
    return { rings, nv, terrainTriangles, perimeter, tables, fans };
}


// ------------------------------------------------------------------------------------------------ building ---

function asLevelField(R, h, w, k) {
    if (h && typeof h === 'object' && h.runner !== undefined && h.buffer !== undefined) {
        if (h.h !== w.n || h.w !== w.n || h.channels !== 1 || h.kind !== 'f32') {
            throw new RangeError(`level ${k}: heights must be (${w.n}, ${w.n}) float32, got (${h.h}, ${h.w}) ${h.format}`);
        }
        return { f: h, own: false };
    }
    const data = h?.data instanceof Float32Array ? h.data : h;
    if (!(data instanceof Float32Array) || data.length !== w.n * w.n) {
        const got = data?.length ?? (h == null ? 'nothing' : typeof h);
        throw new RangeError(`level ${k}: heights must be (${w.n}, ${w.n}) float32 (${w.n * w.n} values), got ${got}`);
    }
    return { f: R.field(w.n, w.n, 1, data), own: true };
}

const groups2d = (nx, ny) => [Math.ceil(nx / 16), Math.ceil(ny / 16), 1];
const listField = (R, n, kind) => {
    const [h, w] = listShape(n);
    return R.field(h, w, 1, null, kind);
};

/** The ring mesh of nested levels, coarsest first (mesh.py build_rings, on the GPU and read back once).
 *   R          the GPU runner (core/gpu.js)
 *   levels     windows (asWindow), each inside the one before, on its cell grid, cell halved; Level objects carry
 *              their role, which picks each ring's material (opts.roles otherwise)
 *   heights    per level, its n x n heights (metres, row 0 south): a GPU field, a Float32Array, or { data }
 *   opts       cores (draw the finest level again down to stride 1: when there is a focus), meshRes, skirt,
 *              skirtDropM, roles
 * Returns a RingMesh. */
export async function buildRings(R, levels, heights, opts = {}) {
    const { cores = false, meshRes = MESH_RES, skirt = true, skirtDropM = SKIRT_DROP_M } = opts;
    const t0 = performance.now();
    const windows = levels.map(asWindow);
    const roles = opts.roles ?? levels.map((l) => l?.role ?? null);
    const { origin, unit, iwins } = integerWindows(windows);
    const specs = planRings(iwins, meshRes, cores);
    const topo = topology(specs, iwins, skirt);
    const { rings, nv, terrainTriangles, perimeter } = topo;
    const m = perimeter;
    const V = nv + 2 * m, T = terrainTriangles + 2 * m;
    // the lattice lines in metres, as Blender writes them: float32(origin + lattice * unit) in doubles
    let linesLen = 0;
    for (const r of rings) {
        r.xm = new Float64Array(r.nx);
        r.ym = new Float64Array(r.ny);
        for (let i = 0; i < r.nx; i++) r.xm[i] = Math.fround(origin[0] + r.xs[i] * unit);
        for (let j = 0; j < r.ny; j++) r.ym[j] = Math.fround(origin[1] + r.ys[j] * unit);
        r.lineAt = linesLen;
        linesLen += r.nx + r.ny;
    }
    const lines = new Float32Array(linesLen);
    for (const r of rings) {
        lines.set(r.xm, r.lineAt);
        lines.set(r.ym, r.lineAt + r.nx);
    }
    const P = prims(R);
    const owned = [];
    const tabF = P.list(topo.tables.length, 'i32', topo.tables);
    const fanF = P.list(topo.fans.length, 'i32', topo.fans);
    const lineF = P.list(lines.length, 'f32', lines);
    owned.push(tabF, fanF, lineF);
    const levelF = [];
    try {
        for (let k = 0; k < windows.length; k++) levelF.push(asLevelField(R, heights[k], iwins[k], k));
        const dummyU = R.field(1, 1, 1, null, 'u32'), dummyF = R.field(1, 1, 1);
        owned.push(dummyU, dummyF);
        // vertex numbers and heights, ring by ring (each reads its parent's)
        rings.forEach((r, k) => {
            r.I = R.field(r.ny, r.nx, 1, null, 'u32');
            r.Z = R.field(r.ny, r.nx, 1);
            const par = k ? rings[k - 1] : null;
            const pl = r.parLines ?? [0, 0, 0, 0];
            R.run('mesh/ring_index', { tab: tabF, par: par ? par.I : dummyU }, { outI: r.I },
                { uDims: [r.nx, r.ny, r.v0, par ? 1 : 0], uHole: r.holeInner, uPar: pl, uTab: [r.tabAt, 0, 0, 0] },
                groups2d(r.nx, r.ny));
            R.run('mesh/ring_heights', { hl: levelF[r.spec.level].f, tab: tabF, pz: par ? par.Z : dummyF }, { outZ: r.Z },
                { uDims: [r.nx, r.ny, par ? 1 : 0, iwins[r.spec.level].n], uPar: pl, uTab: [r.tabAt, 0, 0, 0] },
                groups2d(r.nx, r.ny));
        });
        for (const lf of levelF) if (lf.own) lf.f.destroy();
        levelF.length = 0;
        // positions, uv and the index buffer
        const pos = listField(R, 3 * V, 'f32'), uv = listField(R, 2 * V, 'f32'), nrm = listField(R, 3 * V, 'f32');
        const tri = listField(R, 3 * T, 'u32');
        const bounds = R.field(1, 2, 1, null, 'u32');      // bound as ring_vertices' atomic_u32 image
        owned.push(pos, uv, nrm, tri, bounds);
        rings.forEach((r, k) => {
            R.run('mesh/ring_vertices', { zg: r.Z, ig: r.I, lines: lineF }, { outP: pos, outU: uv, outB: bounds },
                { uDims: [r.nx, r.ny, r.v0, r.lineAt] }, groups2d(r.nx, r.ny));
            const hl = r.holeLines ?? [-1, -1, -1, -1];
            R.run('mesh/ring_quads', { ig: r.I, tab: tabF }, { outT: tri },
                { uDims: [r.nx, r.ny, r.triBase, r.nAbc], uHole: hl, uTab: [r.tabAt, 0, 0, 0] }, groups2d(r.nx - 1, r.ny - 1));
            if (r.hole) {
                const C = rings[k + 1];
                R.run('mesh/ring_fans', { ig: r.I, cg: C.I, fan: fanF }, { outT: tri },
                    { uDims: [r.nx, C.nx, C.ny, r.nFans], uFan: [r.fanAt, r.triBase + r.nAbc + r.nAcd, r.nFanTris, 0] },
                    lineGroups(r.nFanTris));
            }
        });
        // the skirt
        let zmin = null;
        if (m) {
            const r0 = rings[0];
            zmin = R.field(1, 1, 1);
            owned.push(zmin);
            R.run('mesh/skirt_min', { zg: r0.Z }, { outM: zmin }, { uDims: [r0.nx, r0.ny, 0, 0] }, [1, 1, 1]);
            R.run('mesh/skirt', { zg: r0.Z, ig: r0.I, lines: lineF, zmin }, { outP: pos, outU: uv, outN: nrm, outT: tri },
                { uDims: [r0.nx, r0.ny, nv, m], uBase: [terrainTriangles, 0, 0, 0], uDrop: skirtDropM }, lineGroups(m));
        }
        owned.push(...gpuNormals(R, pos, tri, nv, terrainTriangles, nrm));
        // one wait for everything the host keeps
        const parts = [{ field: pos, count: 3 * V }, { field: nrm, count: 3 * V }, { field: uv, count: 2 * V },
            { field: tri, count: 3 * T }, { field: bounds, count: 2 }];
        if (zmin) parts.push({ field: zmin, count: 1 });
        for (const r of rings) parts.push({ field: r.Z }, { field: r.I });
        const got = await R.readParts(parts);
        const [positions, normals, uvs, index, b] = got;
        let q = zmin ? 6 : 5;
        for (const r of rings) {
            r.Zf = got[q++];
            r.idx = got[q++];
        }
        const hmin = keyToFloat(~b[0] >>> 0), hmax = keyToFloat(b[1]);
        const bottom = zmin ? Math.fround(got[5][0] - skirtDropM) : null;
        const skirtInfo = m ? { drop_m: skirtDropM, bottom_z: got[5][0] - skirtDropM, first_vertex: nv } : null;
        for (const r of rings) {
            r.I.destroy();
            r.Z.destroy();
            r.I = r.Z = null;
            r.Z = r.Zf;
            delete r.Zf;
            delete r.tab;
        }
        const groups = rings.map((r) => ({ start: 3 * r.triBase, count: 3 * r.triangles,
            materialIndex: ringMaterial(roles[r.spec.level]) }));
        if (m) groups.push({ start: 3 * terrainTriangles, count: 6 * m, materialIndex: groups[0].materialIndex, skirt: true });
        return new RingMesh({ origin, unit, windows, specs, rings, positions, normals, uvs, index, groups,
            nv, terrainTriangles, skirt: skirtInfo, heightRange: [Math.min(hmin, bottom ?? hmin), hmax],
            seconds: (performance.now() - t0) / 1000 });
    } finally {
        for (const lf of levelF) if (lf.own) lf.f.destroy();
        for (const f of owned) if (!f.destroyed) f.destroy();
        for (const r of rings) {
            if (r.I && !r.I.destroyed) r.I.destroy();
            if (r.Z && r.Z.destroyed === false) r.Z.destroy();
        }
    }
}

/** Record the terrain vertices' normals (mesh.py vertex_normals) into `nrm` (3 numbers a vertex): the corners of
 * the first `terrainTriangles` triangles of `tri` sorted by vertex (a stable radix sort: each vertex's corners stay
 * in triangle order), every vertex's count and first corner, then kernels/mesh/normals.wgsl's gather. `pos` holds 3
 * numbers a vertex. Returns the fields it made, for the caller to release after its read. */
export function gpuNormals(R, pos, tri, nv, terrainTriangles, nrm) {
    const P = prims(R);
    const corners = 3 * terrainTriangles;
    const bits = Math.max(1, Math.ceil(Math.log2(Math.max(nv, 2))));
    const sorted = P.sortPairs(tri, null, { count: corners, bits });
    const counts = P.bincount(tri, nv, { count: corners });
    const starts = P.cumsum(counts, { count: nv, exclusive: true });
    R.run('mesh/normals', { pos, tri, start: starts, count: counts, corner: sorted.vals }, { outN: nrm },
        { uCount: nv }, lineGroups(nv));
    return [sorted.keys, sorted.vals, counts, starts];
}

/** The material slot of a ring (C4): 1, the far material, for a context ring; 0 for the rest. */
export function ringMaterial(role) {
    return role === 'context' ? 1 : 0;
}


// ---------------------------------------------------------------------------------------------- ring mesh ---

/** The rings of one terrain: positions, normals and uv (three.js axes, Float32Array, 3 / 3 / 2 a vertex), the index
 * buffer (Uint32Array, the skirt's triangles last), one group per ring, and heightAt / normalAt on the triangles
 * (Blender axes). rings[k]: { spec, hole, holeLines, xs, ys (lattice), xm, ym (metres, the float32 values),
 * Z (heights as written, ny x nx Float32Array), idx (vertex numbers, NONE in the hole), v0, triBase, ... }. */
export class RingMesh {
    constructor(o) {
        Object.assign(this, o);
    }

    get triangleCount() { return this.index.length / 3; }
    get vertexCount() { return this.positions.length / 3; }

    /** [xmin, ymin, xmax, ymax] of the outermost window, metres (Blender axes). */
    bounds() {
        const r = this.rings[0];
        return [r.xm[0], r.ym[0], r.xm[r.nx - 1], r.ym[r.ny - 1]];
    }

    /** What rebuilds this mesh's lattices (mesh.py layout(), JSON-able, the same JSON). */
    layout() {
        return {
            origin: [this.origin[0], this.origin[1]], unit: this.unit,
            windows: this.windows.map((w) => [w.x0, w.y0, w.cell, w.n]),
            rings: this.specs.map((s) => s.asList()), skirt: this.skirt !== null,
            skirt_drop_m: this.skirt ? this.skirt.drop_m : SKIRT_DROP_M,
        };
    }

    // locating points ----------------------------------------------------------------------------------------

    _clamp(x, y) {
        const [xmin, ymin, xmax, ymax] = this.bounds();
        return [Math.min(Math.max(x, xmin), xmax), Math.min(Math.max(y, ymin), ymax)];
    }

    /** The index of the finest ring whose window holds the point (already clamped to the outermost window). */
    _ringOf(x, y) {
        for (let k = this.rings.length - 1; k >= 1; k--) {
            const r = this.rings[k];
            if (x >= r.xm[0] && x <= r.xm[r.nx - 1] && y >= r.ym[0] && y <= r.ym[r.ny - 1]) return k;
        }
        return 0;
    }

    /** The finest ring holding each point (clamped to the outermost window): a number, or an Int32Array. */
    ringOf(x, y) {
        if (typeof x === 'number' && typeof y === 'number') return this._ringOf(...this._clamp(x, y));
        const n = x.length, out = new Int32Array(n);
        for (let q = 0; q < n; q++) out[q] = this._ringOf(...this._clamp(x[q], y[q]));
        return out;
    }

    static _locate(r, x, y) {
        const i = Math.min(Math.max(searchsorted(r.xm, x, 'right') - 1, 0), r.nx - 2);
        const j = Math.min(Math.max(searchsorted(r.ym, y, 'right') - 1, 0), r.ny - 2);
        const fx = (x - r.xm[i]) / (r.xm[i + 1] - r.xm[i]);
        const fy = (y - r.ym[j]) / (r.ym[j + 1] - r.ym[j]);
        return [i, j, fx, fy];
    }

    /** One point's height (Blender axes, the point clamped), and what it read: [z, trace] with trace = { ring, i, j,
     * lower, fan (null or the fan case 0-3) }. mesh.py height_at for one point, in its order of operations. */
    _height(x0, y0) {
        const [x, y] = this._clamp(x0, y0);
        const k = this._ringOf(x, y);
        const r = this.rings[k];
        const [i, j, fx, fy] = RingMesh._locate(r, x, y);
        const Z = r.Z, nx = r.nx;
        const ha = Z[j * nx + i], hb = Z[j * nx + i + 1], hc = Z[(j + 1) * nx + i + 1], hd = Z[(j + 1) * nx + i];
        const lower = fx >= fy;
        let z = lower ? ha + fx * (hb - ha) + fy * (hc - hb) : ha + fy * (hd - ha) + fx * (hc - hd);
        let fan = null;
        if (r.hole) {
            const C = this.rings[k + 1];
            const [jb, jt, il, ir] = r.holeLines;
            const inx = i >= il && i < ir, iny = j >= jb && j < jt;
            const xm = r.xm, ym = r.ym;
            let c = null;
            if (j === jb - 1 && inx && !lower) {
                // below the hole: (a, c, d) fanned from a = (i, jb - 1) to the edge y = ym[jb]: the child's bottom row
                c = { axis: 'y', qx: xm[i], qy: ym[jb - 1], qz: Z[(jb - 1) * nx + i], edge: ym[jb], line: 'bottom', kind: 0 };
            } else if (j === jt && inx && lower) {
                // above the hole: (a, b, c) fanned from c = (i + 1, jt + 1) to the edge y = ym[jt]: the child's top row
                c = { axis: 'y', qx: xm[i + 1], qy: ym[jt + 1], qz: Z[(jt + 1) * nx + i + 1], edge: ym[jt], line: 'top', kind: 1 };
            } else if (i === il - 1 && iny && lower) {
                // left of the hole: (a, b, c) fanned from a = (il - 1, j) to the edge x = xm[il]: the child's left column
                c = { axis: 'x', qx: xm[il - 1], qy: ym[j], qz: Z[j * nx + il - 1], edge: xm[il], line: 'left', kind: 2 };
            } else if (i === ir && iny && !lower) {
                // right of the hole: (a, c, d) fanned from c = (ir + 1, j + 1) to the edge x = xm[ir]: its right column
                c = { axis: 'x', qx: xm[ir + 1], qy: ym[j + 1], qz: Z[(j + 1) * nx + ir + 1], edge: xm[ir], line: 'right', kind: 3 };
            }
            if (c) {
                let s, hit;
                if (c.axis === 'y') {                 // the edge is a row: the ray meets it at y = edge
                    s = (y - c.qy) / (c.edge - c.qy);
                    hit = c.qx + (x - c.qx) / Math.max(s, 1e-300);
                } else {                              // a column: at x = edge
                    s = (x - c.qx) / (c.edge - c.qx);
                    hit = c.qy + (y - c.qy) / Math.max(s, 1e-300);
                }
                const [pos, zs] = childLine(C, c.line);
                const ze = npInterp(hit, pos, zs);
                z = c.qz + s * (ze - c.qz);
                fan = c.kind;
            }
        }
        return [z, { ring: k, i, j, lower, fan }];
    }

    /** Metres at Blender (x, y) on this mesh's triangles: the finest ring that holds the point, its quad, the
     * (i, j) - (i + 1, j + 1) diagonal, and in a seam fan the fan's own triangle. Points outside the outermost window
     * read its edge. A number for numbers; a Float64Array for arrays. */
    heightAt(x, y) {
        if (typeof x === 'number' && typeof y === 'number') return this._height(x, y)[0];
        const n = x.length, out = new Float64Array(n);
        for (let q = 0; q < n; q++) out[q] = this._height(x[q], y[q])[0];
        return out;
    }

    /** A vertex's shading normal in Blender axes (the geometry holds three.js's: (x, z, -y)). */
    vertexNormal(v) {
        const n = this.normals;
        return [n[3 * v], -n[3 * v + 2], n[3 * v + 1]];
    }

    /** The surface normal at Blender (x, y), Blender axes: smooth, the shading normal (the quad triangle's vertex
     * normals blended by barycentric weight; a seam fan reads the corners of the triangle it subdivides); else the
     * triangle's own face normal (mesh.py normal_at). [nx, ny, nz] for numbers; an array of them for arrays. */
    normalAt(x, y, smooth = true) {
        if (typeof x !== 'number' || typeof y !== 'number') {
            return Array.from(x, (xv, q) => this.normalAt(xv, y[q], smooth));
        }
        [x, y] = this._clamp(x, y);
        const k = this._ringOf(x, y);
        const r = this.rings[k];
        const [i, j, fx, fy] = RingMesh._locate(r, x, y);
        const lower = fx >= fy;
        let n;
        if (smooth) {
            const I = r.idx, nx = r.nx;
            const na = this.vertexNormal(I[j * nx + i]), nb = this.vertexNormal(I[j * nx + i + 1]);
            const nc = this.vertexNormal(I[(j + 1) * nx + i + 1]), nd = this.vertexNormal(I[(j + 1) * nx + i]);
            n = [0, 1, 2].map((a) => (lower ? na[a] * (1 - fx) + nb[a] * (fx - fy) + nc[a] * fy
                : na[a] * (1 - fy) + nc[a] * fx + nd[a] * (fy - fx)));
        } else {
            const Z = r.Z, nx = r.nx;
            const ha = Z[j * nx + i], hb = Z[j * nx + i + 1], hc = Z[(j + 1) * nx + i + 1], hd = Z[(j + 1) * nx + i];
            const dx = r.xm[i + 1] - r.xm[i], dy = r.ym[j + 1] - r.ym[j];
            const gx = lower ? (hb - ha) / dx : (hc - hd) / dx;
            const gy = lower ? (hc - hb) / dy : (hd - ha) / dy;
            n = [-gx, -gy, 1.0];
        }
        const l = Math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
        return [n[0] / l, n[1] / l, n[2] / l];
    }

    /** The lattice point (i, j) of ring k as [x, y, z] (Blender axes, the float32 values). */
    latticePoint(k, i, j) {
        const r = this.rings[k];
        return [r.xm[i], r.ym[j], r.Z[j * r.nx + i]];
    }
}

// a child ring's border line (positions along it, heights as written), cached on the ring
function childLine(C, which) {
    C._lines = C._lines ?? {};
    let l = C._lines[which];
    if (!l) {
        const nx = C.nx, ny = C.ny, Z = C.Z;
        if (which === 'bottom') l = [C.xm, Z.subarray(0, nx)];
        else if (which === 'top') l = [C.xm, Z.subarray((ny - 1) * nx, ny * nx)];
        else {
            const col = new Float32Array(ny);
            const c = which === 'left' ? 0 : nx - 1;
            for (let j = 0; j < ny; j++) col[j] = Z[j * nx + c];
            l = [C.ym, col];
        }
        C._lines[which] = l;
    }
    return l;
}


// ---------------------------------------------------------------------------------------------- three.js ---

/** The BufferGeometry of a RingMesh: position, normal and uv (three.js axes, world metres), the Uint32 index, one
 * group per ring (and the skirt's), its bounding box and sphere from the heights' range (nothing walks the
 * vertices). userData.ringMesh is the RingMesh. */
export function makeGeometry(THREE, rm) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(rm.positions, 3));
    g.setAttribute('normal', new THREE.BufferAttribute(rm.normals, 3));
    g.setAttribute('uv', new THREE.BufferAttribute(rm.uvs, 2));
    g.setIndex(new THREE.BufferAttribute(rm.index, 1));
    for (const gr of rm.groups) g.addGroup(gr.start, gr.count, gr.materialIndex);
    const [xmin, ymin, xmax, ymax] = rm.bounds();
    g.boundingBox = new THREE.Box3(new THREE.Vector3(xmin, rm.heightRange[0], -ymax),
        new THREE.Vector3(xmax, rm.heightRange[1], -ymin));
    g.boundingSphere = g.boundingBox.getBoundingSphere(new THREE.Sphere());
    g.userData.ringMesh = rm;
    return g;
}

export { NONE };
