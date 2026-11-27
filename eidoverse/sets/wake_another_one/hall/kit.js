// eidoverse/sets/wake_another_one/hall/kit.js — the hall's geometry kit: a port of the Blender edition's
// eidoblend.sets.wake_another_one.hall._kit (and of build.py's MB, a subset of it). Metres, in the hall's own frame
// (+Z up; the hall's root carries it into three's +Y up).
//
//   const mb = new MB();  mb.span(lo, hi, 0);  mb.cyl(c, r, len, 'x', 16, 1);  mb.prism(poly, a, b, 'y', 0);  ...
//   const md = mb.mesh('name', ['steel_galv', 'steel_dark']);       // faces + material names (windings made outward)
//   finish(md, { bevel, inset, cavity, ground }, MeshBVH, THREE)    // the detail pass, then the cavity bake
//   const geo = toGeometry(THREE, md);                               // BufferGeometry: groups by material slot,
//                                                                    // attributes position, normal, uv, wear, cavity
//
// The layout builds from plain boxes and cylinders; finish() turns such a mesh into one a layered material can read,
// as the Blender kit's detail() and bake_cavity() do:
//   - every hard edge (faces meeting at more than 50 degrees) gets a real BEVEL: two segments on a round profile,
//     its width the island's (a thin part never caps a stout one's), in the kit's four width classes;
//   - every face gets an INSET loop a wear-width in from its hard edges (each smooth region's own width, the bmesh
//     call groups' smallest), and the vertex attribute `wear` runs 1 on the arris to 0 on that loop;
//   - hardened normals: a flat face its own, a smooth region its area-weighted mean, a bevel the mean of the two
//     regions it joins;
//   - a UV map in METRES (each face projected along its dominant axis);
//   - `cavity`: how much of a cosine-weighted hemisphere over each vertex meets the mesh within a few centimetres
//     (three-mesh-bvh ray casts, the Blender kit's fourteen directions), inner loops of large faces held at 0.
// Every primitive is its own island (no vertex is shared between two calls), so the detail pass works island by
// island on the polygons each primitive wrote, with the topology bmesh's inset_region and bevel make.

export const PI = Math.PI;
const SHARP = 50.0 * PI / 180.0;

// ------------------------------------------------------------------------------------------------ vectors
export const V = {
    add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
    sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
    mul: (a, k) => [a[0] * k, a[1] * k, a[2] * k],
    dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
    cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
    len: (a) => Math.hypot(a[0], a[1], a[2]),
    norm: (a) => { const l = Math.hypot(a[0], a[1], a[2]); return l > 0 ? [a[0] / l, a[1] / l, a[2] / l] : [0, 0, 0]; },
};
const { add, sub, mul, dot, cross, len, norm } = V;

// 3 x 3 rotations (row-major), as mathutils' Matrix.Rotation(angle, 3, axis)
export function rot3(a, axis) {
    const c = Math.cos(a), s = Math.sin(a);
    if (axis === 'X') return [[1, 0, 0], [0, c, -s], [0, s, c]];
    if (axis === 'Y') return [[c, 0, s], [0, 1, 0], [-s, 0, c]];
    if (axis === 'Z') return [[c, -s, 0], [s, c, 0], [0, 0, 1]];
    const [x, y, z] = norm(axis), t = 1 - c;                         // about an arbitrary axis (Rodrigues)
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y], [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
        [t * x * z - s * y, t * y * z + s * x, t * z * z + c]];
}
export const m3mul = (A, B) => A.map((r) => [0, 1, 2].map((j) => r[0] * B[0][j] + r[1] * B[1][j] + r[2] * B[2][j]));
export const m3app = (M, p) => [M[0][0] * p[0] + M[0][1] * p[1] + M[0][2] * p[2], M[1][0] * p[0] + M[1][1] * p[1] + M[1][2] * p[2],
    M[2][0] * p[0] + M[2][1] * p[1] + M[2][2] * p[2]];

// ------------------------------------------------------------------------------------------------ the builder
// a mesh from boxes, cylinders, prisms, tubes and quads; mi = material slot. Faces are vertex index lists; each call
// is its own island
export class MB {
    constructor() { this.v = []; this.f = []; this.mi = []; this.sm = []; this.isl = []; this.n = 0; }
    _faces(n0, quads, mi, sm) { const k = this.n++; for (const q of quads) { this.f.push(q.map((i) => n0 + i)); this.mi.push(mi); this.sm.push(sm); this.isl.push(k); } }

    box(c, s, mi = 0, rz = 0.0, rx = 0.0, ry = 0.0) {
        const hx = s[0] / 2, hy = s[1] / 2, hz = s[2] / 2;
        let pts = [[-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz], [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz]];
        if (rz || rx || ry) {
            const m = m3mul(m3mul(rot3(rz, 'Z'), rot3(ry, 'Y')), rot3(rx, 'X'));
            pts = pts.map((p) => m3app(m, p));
        }
        const n0 = this.v.length;
        for (const p of pts) this.v.push([p[0] + c[0], p[1] + c[1], p[2] + c[2]]);
        const k = this.n++;
        for (const q of [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]) {
            this.f.push(q.map((i) => n0 + i)); this.mi.push(mi); this.sm.push(false); this.isl.push(k);
        }
        return this;
    }

    span(lo, hi, mi = 0) {
        return this.box([0, 1, 2].map((i) => (lo[i] + hi[i]) / 2), [0, 1, 2].map((i) => Math.abs(hi[i] - lo[i])), mi);
    }

    // a cylinder (r2: the radius at its far end, for a cone)
    cyl(c, r, length, axis = 'x', n = 16, mi = 0, caps = true, r2 = null) {
        const n0 = this.v.length;
        for (const [side, rr] of [[-1, r], [1, r2 === null ? r : r2]]) {
            const d = side * length / 2;
            for (let i = 0; i < n; i++) {
                const a = Math.cos(2 * PI * i / n) * rr, b = Math.sin(2 * PI * i / n) * rr;
                const p = axis === 'x' ? [d, a, b] : axis === 'y' ? [b, d, a] : [a, b, d];
                this.v.push([c[0] + p[0], c[1] + p[1], c[2] + p[2]]);
            }
        }
        const k = this.n++;
        for (let i = 0; i < n; i++) {
            const j = (i + 1) % n;
            this.f.push([n0 + i, n0 + j, n0 + n + j, n0 + n + i]); this.mi.push(mi); this.sm.push(true); this.isl.push(k);
        }
        if (caps) {
            this.f.push([...Array(n).keys()].reverse().map((i) => n0 + i)); this.mi.push(mi); this.sm.push(false); this.isl.push(k);
            this.f.push([...Array(n).keys()].map((i) => n0 + n + i)); this.mi.push(mi); this.sm.push(false); this.isl.push(k);
        }
        return this;
    }

    // the closed section poly [(u, v)] swept from a to b along axis; (u, v) is (x, z) for 'y', (y, z) for 'x', (x, y)
    // for 'z'; `at` is added to every (u, v)
    prism(poly, a, b, axis = 'y', mi = 0, at = [0.0, 0.0]) {
        const n0 = this.v.length, k = poly.length;
        for (const d of [a, b]) {
            for (let [u, v] of poly) {
                u += at[0]; v += at[1];
                this.v.push(axis === 'y' ? [u, d, v] : axis === 'x' ? [d, u, v] : [u, v, d]);
            }
        }
        const isl = this.n++;
        for (let i = 0; i < k; i++) {
            const j = (i + 1) % k;
            this.f.push([n0 + i, n0 + j, n0 + k + j, n0 + k + i]); this.mi.push(mi); this.sm.push(false); this.isl.push(isl);
        }
        this.f.push([...Array(k).keys()].reverse().map((i) => n0 + i)); this.mi.push(mi); this.sm.push(false); this.isl.push(isl);
        this.f.push([...Array(k).keys()].map((i) => n0 + k + i)); this.mi.push(mi); this.sm.push(false); this.isl.push(isl);
        return this;
    }

    // a hexagon head (across corners 2 r) on a washer
    bolt(c, r = 0.009, h = 0.007, axis = 'z', mi = 0, washer = true) {
        if (washer) {
            const off = [0, 0, 0];
            off['xyz'.indexOf(axis)] = -h / 2 - 0.001;
            this.cyl([c[0] + off[0], c[1] + off[1], c[2] + off[2]], r * 1.45, 0.002, axis, 12, mi);
        }
        return this.cyl(c, r, h, axis, 6, mi);
    }

    quad(pts, mi = 0) {
        const n0 = this.v.length;
        for (const p of pts) this.v.push([p[0], p[1], p[2]]);
        this._faces(n0, [[0, 1, 2, 3]], mi, false);
        return this;
    }

    // a round tube swept through the points (a conduit with its bends, a cable, a handle): one ring of n vertices at
    // every point, mitred, the frame carried along without twist
    tube(pts, r, n = 10, mi = 0, caps = true) {
        const P = pts.map((p) => [p[0], p[1], p[2]]);
        const k = P.length;
        const tang = [];
        for (let i = 0; i < k; i++) {
            const a = i > 0 ? sub(P[i], P[i - 1]) : sub(P[1], P[0]);
            const b = i < k - 1 ? sub(P[i + 1], P[i]) : sub(P[k - 1], P[k - 2]);
            const t = add(norm(a), norm(b));
            tang.push(len(t) > 1e-9 ? norm(t) : norm(a));
        }
        const up = Math.abs(tang[0][2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
        let u = norm(cross(tang[0], up));
        const n0 = this.v.length;
        for (let i = 0; i < k; i++) {
            u = norm(sub(u, mul(tang[i], dot(u, tang[i]))));
            const w = cross(tang[i], u);
            const c = (i > 0 && i < k - 1) ? Math.max(0.35, dot(tang[i], norm(sub(P[i], P[i - 1])))) : 1.0;
            for (let j = 0; j < n; j++) {
                const a = 2 * PI * j / n;
                this.v.push(add(P[i], mul(add(mul(u, Math.cos(a)), mul(w, Math.sin(a))), r / c)));
            }
        }
        const isl = this.n++;
        for (let i = 0; i < k - 1; i++) {
            for (let j = 0; j < n; j++) {
                const j2 = (j + 1) % n;
                this.f.push([n0 + i * n + j, n0 + i * n + j2, n0 + (i + 1) * n + j2, n0 + (i + 1) * n + j]);
                this.mi.push(mi); this.sm.push(true); this.isl.push(isl);
            }
        }
        if (caps) {
            this.f.push([...Array(n).keys()].reverse().map((j) => n0 + j)); this.mi.push(mi); this.sm.push(false); this.isl.push(isl);
            this.f.push([...Array(n).keys()].map((j) => n0 + (k - 1) * n + j)); this.mi.push(mi); this.sm.push(false); this.isl.push(isl);
        }
        return this;
    }

    rod(a, b, r, n = 10, mi = 0) { return this.tube([a, b], r, n, mi); }

    // a rectangular bar w x h from a to b (any direction): w across, h along the frame's second axis (up for a level bar)
    bar(a, b, w, h, mi = 0, roll = 0.0) {
        const d = sub(b, a), t = norm(d);
        const up = Math.abs(t[2]) < 0.95 ? [0, 0, 1] : [1, 0, 0];
        let u = norm(cross(t, up)), v = cross(u, t);
        if (roll) { const m = rot3(roll, t); u = m3app(m, u); v = m3app(m, v); }
        const n0 = this.v.length;
        for (const p of [a, b]) for (const [su, sv] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) this.v.push(add(add(p, mul(u, su * w / 2)), mul(v, sv * h / 2)));
        this._faces(n0, [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]], mi, false);
        return this;
    }

    _quads(pts, quads, mi) {
        const n0 = this.v.length;
        for (const p of pts) this.v.push([p[0], p[1], p[2]]);
        this._faces(n0, quads, mi, false);
        return this;
    }

    // a plate in the XZ plane (its thickness along Y) with a rectangular hole: ONE closed shell
    frame(lo, hi, holeLo, holeHi, mi = 0) {
        const [x0, y0, z0] = lo, [x1, y1, z1] = hi, [a0, c0] = holeLo, [a1, c1] = holeHi;
        const ring = [[x0, z0], [x1, z0], [x1, z1], [x0, z1], [a0, c0], [a1, c0], [a1, c1], [a0, c1]];
        const pts = [...ring.map(([x, z]) => [x, y0, z]), ...ring.map(([x, z]) => [x, y1, z])];
        const quads = [];
        for (let k = 0; k < 4; k++) {
            const j = (k + 1) % 4;
            quads.push([k, j, 4 + j, 4 + k], [8 + k, 12 + k, 12 + j, 8 + j], [k, 8 + k, 8 + j, j], [4 + k, 4 + j, 12 + j, 12 + k]);
        }
        return this._quads(pts, quads, mi);
    }

    // a box of sheet t thick, open on its +Y side: one closed shell with its hollow
    tub(lo, hi, t, mi = 0) {
        const [x0, y0, z0] = lo, [x1, y1, z1] = hi;
        const o = [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1], [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]];
        const i = [[x0 + t, y0 + t, z0 + t], [x1 - t, y0 + t, z0 + t], [x1 - t, y0 + t, z1 - t], [x0 + t, y0 + t, z1 - t],
            [x0 + t, y1, z0 + t], [x1 - t, y1, z0 + t], [x1 - t, y1, z1 - t], [x0 + t, y1, z1 - t]];
        const quads = [[0, 1, 2, 3], [8, 11, 10, 9]];
        for (let k = 0; k < 4; k++) {
            const j = (k + 1) % 4;
            quads.push([k, 4 + k, 4 + j, j], [8 + k, 8 + j, 12 + j, 12 + k], [4 + k, 12 + k, 12 + j, 4 + j]);
        }
        return this._quads([...o, ...i], quads, mi);
    }

    // points on an arc round c (for tube()): angles in radians in the plane across `axis`
    arc(c, r, a0, a1, axis = 'z', steps = 8) {
        const out = [];
        for (let i = 0; i <= steps; i++) {
            const a = a0 + (a1 - a0) * i / steps;
            const ca = Math.cos(a) * r, sa = Math.sin(a) * r;
            const p = axis === 'z' ? [ca, sa, 0.0] : axis === 'x' ? [0.0, ca, sa] : [sa, 0.0, ca];
            out.push([c[0] + p[0], c[1] + p[1], c[2] + p[2]]);
        }
        return out;
    }

    // -> mesh data: { name, mats, v, f, mi, sm, isl } with every closed island's faces turned outward (bmesh's
    // recalc_face_normals: consistent winding, then the side the volume says is out)
    mesh(name, mats, recalc = true) {
        const md = { name, mats: [...mats], v: this.v, f: this.f, mi: this.mi, sm: this.sm, isl: this.isl };
        if (recalc) recalcNormals(md);
        return md;
    }
}

// a mesh's faces as an MB-shaped record from raw polygons (for sheets built outside MB): uv optional per face corner
export function meshData(name, mats, v, f, { mi = null, sm = null, uv = null } = {}) {
    return { name, mats: [...mats], v, f, mi: mi || f.map(() => 0), sm: sm || f.map(() => false), isl: f.map(() => 0), uv };
}

// the closed section of an I beam (height h, flange width w, flange tf, web tw), centred, for MB.prism: (u across the
// flanges, v up); r > 0 adds the root fillets as one chamfer
export function i_section(h, w, tf, tw, r = 0.0) {
    const a = w / 2, b = tw / 2, c = h / 2;
    if (r <= 0) return [[-a, -c], [a, -c], [a, -c + tf], [b, -c + tf], [b, c - tf], [a, c - tf], [a, c], [-a, c], [-a, c - tf], [-b, c - tf], [-b, -c + tf], [-a, -c + tf]];
    return [[-a, -c], [a, -c], [a, -c + tf], [b + r, -c + tf], [b, -c + tf + r], [b, c - tf - r], [b + r, c - tf], [a, c - tf],
        [a, c], [-a, c], [-a, c - tf], [-b - r, c - tf], [-b, c - tf - r], [-b, -c + tf + r], [-b - r, -c + tf], [-a, -c + tf]];
}

// a channel (height h, flange w, thickness t), its back on u = 0, opening toward +u
export function c_section(h, w, t) {
    const c = h / 2;
    return [[0, -c], [w, -c], [w, -c + t], [t, -c + t], [t, c - t], [w, c - t], [w, c], [0, c]];
}

// ------------------------------------------------------------------------------------------------ topology helpers
function newell(pts) {
    let nx = 0, ny = 0, nz = 0;
    for (let k = 0; k < pts.length; k++) {
        const a = pts[k], b = pts[(k + 1) % pts.length];
        nx += (a[1] - b[1]) * (a[2] + b[2]); ny += (a[2] - b[2]) * (a[0] + b[0]); nz += (a[0] - b[0]) * (a[1] + b[1]);
    }
    const l = Math.hypot(nx, ny, nz);
    return { n: l > 0 ? [nx / l, ny / l, nz / l] : [0, 0, 1], area: l / 2 };
}
const ekey = (a, b) => (a < b ? `${a},${b}` : `${b},${a}`);

// every island: windings made consistent across its manifold edges, then turned out (a closed island by its signed
// volume; an open one so its face furthest from the island's middle faces away from it, as bmesh decides)
function recalcNormals(md) {
    const byIsl = new Map();
    md.f.forEach((f, i) => { const k = md.isl[i]; if (!byIsl.has(k)) byIsl.set(k, []); byIsl.get(k).push(i); });
    for (const faces of byIsl.values()) {
        const edges = new Map();
        for (const fi of faces) {
            const f = md.f[fi];
            for (let k = 0; k < f.length; k++) {
                const key = ekey(f[k], f[(k + 1) % f.length]);
                if (!edges.has(key)) edges.set(key, []);
                edges.get(key).push(fi);
            }
        }
        const dirOf = (f, a, b) => { for (let k = 0; k < f.length; k++) if (f[k] === a && f[(k + 1) % f.length] === b) return 1; return -1; };
        const done = new Set();
        for (const start of faces) {
            if (done.has(start)) continue;
            done.add(start);
            const stack = [start];
            while (stack.length) {
                const fi = stack.pop(), f = md.f[fi];
                for (let k = 0; k < f.length; k++) {
                    const a = f[k], b = f[(k + 1) % f.length];
                    const ns = edges.get(ekey(a, b));
                    if (ns.length !== 2) continue;
                    const g = ns[0] === fi ? ns[1] : ns[0];
                    if (g === fi || done.has(g)) continue;
                    if (dirOf(md.f[g], a, b) === 1) md.f[g] = [...md.f[g]].reverse();
                    done.add(g); stack.push(g);
                }
            }
        }
        const closed = [...edges.values()].every((l) => l.length === 2);
        let flip = false;
        if (closed) {
            let vol = 0;
            for (const fi of faces) {
                const f = md.f[fi], p0 = md.v[f[0]];
                for (let k = 1; k < f.length - 1; k++) vol += dot(p0, cross(md.v[f[k]], md.v[f[k + 1]]));
            }
            flip = vol < 0;
        } else {
            const cen = [0, 0, 0];
            let cnt = 0;
            for (const fi of faces) for (const i of md.f[fi]) { cen[0] += md.v[i][0]; cen[1] += md.v[i][1]; cen[2] += md.v[i][2]; cnt++; }
            const c = mul(cen, 1 / cnt);
            let best = -1, bd = -1;
            for (const fi of faces) {
                const pts = md.f[fi].map((i) => md.v[i]);
                const fc = mul(pts.reduce((s, p) => add(s, p), [0, 0, 0]), 1 / pts.length);
                const d = len(sub(fc, c));
                if (d > bd + 1e-9) { bd = d; best = fi; }
            }
            if (best >= 0) {
                const pts = md.f[best].map((i) => md.v[i]);
                const fc = mul(pts.reduce((s, p) => add(s, p), [0, 0, 0]), 1 / pts.length);
                flip = dot(newell(pts).n, sub(fc, c)) < -1e-12;
            }
        }
        if (flip) for (const fi of faces) md.f[fi] = [...md.f[fi]].reverse();
    }
}

// ------------------------------------------------------------------------------------------------ the output soup
// polygons with per-corner attributes: pos, nrm, wear, inner (the inset loop), and the polygon's material slot
class Soup {
    constructor() { this.pos = []; this.nrm = []; this.wear = []; this.inner = []; this.start = []; this.count = []; this.mi = []; this.uv = null; }
    poly(pts, nrms, wear, inner, mi) {
        this.start.push(this.pos.length / 3); this.count.push(pts.length); this.mi.push(mi);
        for (let k = 0; k < pts.length; k++) {
            this.pos.push(pts[k][0], pts[k][1], pts[k][2]);
            this.nrm.push(nrms[k][0], nrms[k][1], nrms[k][2]);
            this.wear.push(wear[k]);
            this.inner.push(inner[k] ? 1 : 0);
        }
    }
}

// the plain mesh as a soup: flat faces their own normal, smooth ones the corner-angle-weighted mean of the island's
// smooth faces round each vertex (Blender's), no wear
function plainSoup(md) {
    const S = new Soup();
    const fn = md.f.map((f) => newell(f.map((i) => md.v[i])).n);
    const vn = new Map();
    md.f.forEach((f, fi) => {
        if (!md.sm[fi]) return;
        for (let k = 0; k < f.length; k++) {
            const p = md.v[f[k]], a = md.v[f[(k - 1 + f.length) % f.length]], b = md.v[f[(k + 1) % f.length]];
            const ang = Math.acos(Math.max(-1, Math.min(1, dot(norm(sub(a, p)), norm(sub(b, p))))));
            const acc = vn.get(f[k]) || [0, 0, 0];
            vn.set(f[k], add(acc, mul(fn[fi], ang)));
        }
    });
    md.f.forEach((f, fi) => {
        const pts = f.map((i) => md.v[i]);
        const nr = md.sm[fi] ? f.map((i) => norm(vn.get(i))) : f.map(() => fn[fi]);
        S.poly(pts, nr, f.map(() => 0), f.map(() => 0), md.mi[fi]);
    });
    if (md.uv) S.uv = md.uv.flat();
    return S;
}

// ------------------------------------------------------------------------------------------------ the detail pass
// Bevel + inset + `wear` + hardened normals, in place (md.soup). Closed shells only: a sheet (a face with an open edge)
// is left as it is. -> { faces, bevelled_edges, regions }
export function detail(md, { bevel = 0.0025, inset = 0.014, segments = 2, sharp = SHARP } = {}) {
    const NF = md.f.length;
    const fn = [], area = [];
    for (const f of md.f) { const r = newell(f.map((i) => md.v[i])); fn.push(r.n); area.push(r.area); }
    // edges
    const E = new Map();
    md.f.forEach((f, fi) => {
        for (let k = 0; k < f.length; k++) {
            const a = f[k], b = f[(k + 1) % f.length], key = ekey(a, b);
            if (!E.has(key)) E.set(key, { a: Math.min(a, b), b: Math.max(a, b), faces: [] });
            E.get(key).faces.push([fi, k]);
        }
    });
    for (const e of E.values()) {
        e.manifold = e.faces.length === 2;
        e.hard = !e.manifold || Math.acos(Math.max(-1, Math.min(1, dot(fn[e.faces[0][0]], fn[e.faces[1][0]])))) > sharp;
        e.len = len(sub(md.v[e.a], md.v[e.b]));
    }
    const edgeOf = (f, k) => E.get(ekey(f[k], f[(k + 1) % f.length]));
    // smooth regions (in face order, as bmesh walks them)
    const region = new Int32Array(NF).fill(-1);
    const regions = [];
    for (let fi = 0; fi < NF; fi++) {
        if (region[fi] >= 0) continue;
        const rid = regions.length;
        region[fi] = rid;
        const grp = [fi], stack = [fi];
        while (stack.length) {
            const g = stack.pop(), f = md.f[g];
            for (let k = 0; k < f.length; k++) {
                const e = edgeOf(f, k);
                if (e.hard) continue;
                for (const [h] of e.faces) if (region[h] < 0) { region[h] = rid; grp.push(h); stack.push(h); }
            }
        }
        regions.push(grp);
    }
    const NR = regions.length;
    const closed = new Uint8Array(NR), thick = new Float64Array(NR), neigh = regions.map(() => new Set());
    regions.forEach((grp, rid) => {
        let ok = true, ar = 0, per = 0;
        for (const fi of grp) {
            ar += area[fi];
            const f = md.f[fi];
            for (let k = 0; k < f.length; k++) {
                const e = edgeOf(f, k);
                if (!e.manifold) ok = false;
                else if (e.hard) { per += e.len; for (const [h] of e.faces) if (region[h] !== rid) neigh[rid].add(region[h]); }
            }
        }
        closed[rid] = ok ? 1 : 0;
        thick[rid] = (ok && per > 1e-9) ? Math.min(inset, 0.30 * 2.0 * ar / per) : 0.0;
    });
    // the arris: every vertex on a hard manifold edge of a closed shell
    const arris = new Uint8Array(md.v.length);
    const bevelable = (e) => e.hard && e.manifold && e.faces.every(([h]) => closed[region[h]]);
    for (const e of E.values()) if (bevelable(e)) { arris[e.a] = 1; arris[e.b] = 1; }
    // bevel width per island, in the kit's classes
    const classes = [bevel, bevel * 0.5, bevel * 0.25, bevel * 0.12];
    const islW = new Map();
    for (const e of E.values()) {
        if (!bevelable(e)) continue;
        let w = Math.min(bevel, 0.22 * e.len);
        for (const [h] of e.faces) w = Math.min(w, thick[region[h]] > 0 ? 0.55 * thick[region[h]] : bevel);
        const k = md.isl[e.faces[0][0]];
        islW.set(k, Math.min(islW.has(k) ? islW.get(k) : bevel, w));
    }
    const islClass = new Map();
    for (const [k, w] of islW) islClass.set(k, classes.find((c) => w >= c * 0.999) || 0.0);
    let nBev = 0;
    for (const e of E.values()) { e.w = bevelable(e) ? islClass.get(md.isl[e.faces[0][0]]) || 0 : 0; if (e.w > 0) nBev++; }
    // insets: regions coloured so that neighbours across a hard edge go in different calls; each call's width is the
    // smallest of its regions' (bmesh inset_region, one call per (colour, width class))
    const colour = new Map();
    const order = [...Array(NR).keys()].sort((a, b) => neigh[b].size - neigh[a].size || a - b);
    for (const rid of order) {
        if (!closed[rid] || thick[rid] < 0.0006) continue;
        const used = new Set([...neigh[rid]].filter((n) => colour.has(n)).map((n) => colour.get(n)));
        const tc = thick[rid] >= inset * 0.999 ? 0 : thick[rid] >= inset * 0.5 ? 1 : thick[rid] >= inset * 0.2 ? 2 : 3;
        let c = 0;
        while (used.has(`${c},${tc}`)) c++;
        colour.set(rid, `${c},${tc}`);
    }
    const groupMin = new Map();
    for (const [rid, key] of colour) groupMin.set(key, Math.min(groupMin.has(key) ? groupMin.get(key) : Infinity, thick[rid]));
    const tReg = new Float64Array(NR);
    for (const [rid, key] of colour) tReg[rid] = groupMin.get(key);

    // ---- corners: each face's corners at the bevel's boundary (level 0, width w on bevelled edges) and at the inset
    // loop (level 1, the region's inset on the hard edges that bound it); a corner between a soft and a hard edge
    // slides along the soft edge, the same point from both faces that share it. The bmesh bevel also bevels the inset
    // loop's own edges (they carry the bevel width the inset copied onto them): flat, between coplanar faces, but its
    // new vertices are the loop's, so the wear band ends at t - w; the loop is placed there
    const boundary = (e) => e.hard && (!e.manifold || region[e.faces[0][0]] !== region[e.faces[1][0]]);
    const off = (fi, k, lvl) => {
        const e = edgeOf(md.f[fi], k);
        if (lvl === 0) return e.w;
        const t = tReg[region[fi]];
        return (t > 0 && boundary(e)) ? Math.max(t - e.w, e.w + 1e-5) : e.w;
    };
    const slide = new Map();                                            // `${lvl}|${v}|${u}` -> [sum, n]
    const raw = [];                                                     // raw[fi][lvl][k] = { p, slideKey }
    for (let fi = 0; fi < NF; fi++) {
        const f = md.f[fi], n = fn[fi], m = f.length;
        const P = f.map((i) => md.v[i]);
        const dirs = P.map((p, k) => norm(sub(P[(k + 1) % m], p)));
        const ins = dirs.map((d) => cross(n, d));                       // into the face, in its plane
        const per = [[], []];
        for (const lvl of [0, 1]) {
            const o = [];
            for (let k = 0; k < m; k++) o.push(off(fi, k, lvl));
            for (let k = 0; k < m; k++) {
                const kp = (k - 1 + m) % m;
                const o0 = o[kp], o1 = o[k];
                if (o0 === 0 && o1 === 0) { per[lvl].push({ p: P[k], key: null }); continue; }
                const a = ins[kp], b = ins[k];
                const c = dot(a, b);
                let s;
                if (1 - c * c < 1e-9) s = mul(b, Math.max(o0, o1));
                else {
                    const lam = (o0 - c * o1) / (1 - c * c), mu = (o1 - c * o0) / (1 - c * c);
                    s = add(mul(a, lam), mul(b, mu));
                }
                const pt = add(P[k], s);
                let key = null;
                if (o0 === 0 || o1 === 0) {                              // a slide along the soft edge
                    const u = o0 === 0 ? f[kp] : f[(k + 1) % m];
                    key = `${lvl}|${f[k]}|${u}`;
                    const acc = slide.get(key) || [[0, 0, 0], 0];
                    slide.set(key, [add(acc[0], pt), acc[1] + 1]);
                }
                per[lvl].push({ p: pt, key });
            }
        }
        raw.push(per);
    }
    const pointOf = (c) => (c.key ? mul(slide.get(c.key)[0], 1 / slide.get(c.key)[1]) : c.p);
    // the corner normals: a region's area-weighted mean over its faces that hold the point
    const vFaces = new Map();
    md.f.forEach((f, fi) => { for (const i of f) { if (!vFaces.has(i)) vFaces.set(i, []); vFaces.get(i).push(fi); } });
    const regionNormal = (fi, k, lvl) => {
        const f = md.f[fi], m = f.length, rid = region[fi];
        if (regions[rid].length === 1) return fn[fi];
        const c = raw[fi][lvl][k];
        let fs;
        if (c.key) {                                                    // on a soft edge: the faces that share it
            const u = Number(c.key.split('|')[2]);
            fs = E.get(ekey(f[k], u)).faces.map(([h]) => h);
        } else if (c.p === md.v[f[k]]) fs = vFaces.get(f[k]).filter((h) => region[h] === rid);
        else fs = [fi];
        let acc = [0, 0, 0];
        for (const h of fs) acc = add(acc, mul(fn[h], area[h]));
        return len(acc) > 1e-12 ? norm(acc) : fn[fi];
    };
    // ---- the faces: the inner polygon, the band to the inset loop
    const S = new Soup();
    const isInset = (fi) => tReg[region[fi]] > 0;
    for (let fi = 0; fi < NF; fi++) {
        const f = md.f[fi], m = f.length, mi = md.mi[fi];
        const L0 = raw[fi][0].map(pointOf), L1 = raw[fi][1].map(pointOf);
        const N0 = f.map((_, k) => regionNormal(fi, k, 0)), N1 = f.map((_, k) => regionNormal(fi, k, 1));
        const w0 = f.map((i, k) => (L0[k] !== md.v[i] || arris[i] ? 1 : 0));   // a bevel's boundary or the arris: 1
        if (isInset(fi)) {
            // a corner the inset moved is the loop's (wear 0); one it left where the bevel put it keeps the bevel's
            const moved = f.map((_, k) => off(fi, (k - 1 + m) % m, 1) > off(fi, (k - 1 + m) % m, 0) || off(fi, k, 1) > off(fi, k, 0));
            S.poly(L1, N1, f.map((_, k) => (moved[k] ? 0 : w0[k])), moved.map((x) => (x ? 1 : 0)), mi);
            for (let k = 0; k < m; k++) {
                const j = (k + 1) % m;
                if (off(fi, k, 1) <= off(fi, k, 0)) continue;
                S.poly([L0[k], L0[j], L1[j], L1[k]], [N0[k], N0[j], N1[j], N1[k]], [w0[k], w0[j], 0, 0], [0, 0, 1, 1], mi);
            }
        } else {
            S.poly(L0, N0, w0, f.map(() => 0), mi);
        }
    }
    // ---- the bevels: a strip of `segments` (2) rows of quads along every bevelled edge, its middle row on the arc
    // inscribed between the two faces; at a vertex where three or more meet, a corner patch; where two meet with soft
    // faces between them, the strips run on through one shared point
    const cornerAt = (fi, v, lvl = 0) => { const f = md.f[fi]; const k = f.indexOf(v); return { k, p: pointOf(raw[fi][lvl][k]), n: regionNormal(fi, k, lvl) }; };
    const mid = new Map();                                              // `${edgeKey}|${v}` -> point
    const midN = new Map();
    const bev = [...E.values()].filter((e) => e.w > 0);
    for (const e of bev) {
        const [[fa], [fb]] = e.faces;
        const d = norm(sub(md.v[e.b], md.v[e.a]));
        for (const v of [e.a, e.b]) {
            const A = cornerAt(fa, v), B = cornerAt(fb, v), pv = md.v[v];
            const a = sub(A.p, pv), b = sub(B.p, pv);
            const ad = dot(a, d), bd = dot(b, d);
            const ap = sub(a, mul(d, ad)), bp = sub(b, mul(d, bd));
            const la = len(ap), lb = len(bp);
            let p;
            if (la < 1e-12 || lb < 1e-12) p = add(pv, mul(add(a, b), 0.5));
            else {
                const ah = mul(ap, 1 / la), bh = mul(bp, 1 / lb);
                const ang = Math.acos(Math.max(-1, Math.min(1, dot(ah, bh))));
                const bis = norm(add(ah, bh));
                const wv = 0.5 * (la + lb);
                const k = Math.cos(ang / 2) > 1e-6 ? (1 - Math.sin(ang / 2)) / Math.cos(ang / 2) : 0;
                p = add(add(pv, mul(d, 0.5 * (ad + bd))), mul(bis, wv * k));
            }
            mid.set(`${ekey(e.a, e.b)}|${v}`, p);
            midN.set(`${ekey(e.a, e.b)}|${v}`, norm(add(A.n, B.n)));
        }
    }
    // the fan of faces round each vertex that a bevel touches
    const vBev = new Map();
    for (const e of bev) for (const v of [e.a, e.b]) { if (!vBev.has(v)) vBev.set(v, []); vBev.get(v).push(e); }
    const fanOf = (v) => {
        const fs = vFaces.get(v);
        const start = fs[0], out = [start];
        let cur = start;
        for (let guard = 0; guard < fs.length + 1; guard++) {
            const f = md.f[cur], k = f.indexOf(v), q = f[(k + 1) % f.length];
            const e = E.get(ekey(v, q));
            if (!e.manifold) return null;
            const nxt = e.faces[0][0] === cur ? e.faces[1][0] : e.faces[0][0];
            if (nxt === start) return out.length === fs.length ? out : null;
            out.push(nxt); cur = nxt;
        }
        return null;
    };
    for (const [v, es] of vBev) {
        if (es.length === 2) {                                          // the strips run on: one middle point
            const k0 = `${ekey(es[0].a, es[0].b)}|${v}`, k1 = `${ekey(es[1].a, es[1].b)}|${v}`;
            const p = mul(add(mid.get(k0), mid.get(k1)), 0.5), n = norm(add(midN.get(k0), midN.get(k1)));
            mid.set(k0, p); mid.set(k1, p); midN.set(k0, n); midN.set(k1, n);
        }
    }
    for (const e of bev) {
        const [[fa], [fb]] = e.faces;
        // in fa the edge runs a -> b or b -> a; the strip is wound so that fa's winding carries on into it
        const f = md.f[fa], k = e.faces[0][1];
        const s = f[k], t = f[(k + 1) % f.length];                     // fa's edge s -> t
        const As = cornerAt(fa, s), At = cornerAt(fa, t), Bs = cornerAt(fb, s), Bt = cornerAt(fb, t);
        const ks = `${ekey(e.a, e.b)}|${s}`, kt = `${ekey(e.a, e.b)}|${t}`;
        const Ms = mid.get(ks), Mt = mid.get(kt), Ns = midN.get(ks), Nt = midN.get(kt);
        S.poly([At.p, As.p, Ms, Mt], [At.n, As.n, Ns, Nt], [1, 1, 1, 1], [0, 0, 0, 0], md.mi[fa]);
        S.poly([Mt, Ms, Bs.p, Bt.p], [Nt, Ns, Bs.n, Bt.n], [1, 1, 1, 1], [0, 0, 0, 0], md.mi[fb]);
    }
    // what is left open round a vertex: three or more bevels meeting (a corner patch about a middle point, quads from
    // it to each face's corner), or a bevel ending where the faces round it are soft (the hole between the faces'
    // slid corners, the strip's end and the vertex filled from its middle)
    for (const [v, es] of vBev) {
        const fan = fanOf(v);
        if (!fan) continue;
        const ring = [];
        const pv = md.v[v];
        let nsum = [0, 0, 0];
        for (let i = 0; i < fan.length; i++) {
            const fi = fan[i], f = md.f[fi], k = f.indexOf(v), q = f[(k + 1) % f.length];
            const c = cornerAt(fi, v);
            nsum = add(nsum, mul(fn[fi], area[fi]));
            const last = ring[ring.length - 1];
            if (!last || len(sub(last.p, c.p)) > 1e-9) ring.push({ p: c.p, n: c.n, w: true, mi: md.mi[fi] });
            const e = E.get(ekey(v, q));
            if (e.w > 0) ring.push({ p: mid.get(`${ekey(e.a, e.b)}|${v}`), n: midN.get(`${ekey(e.a, e.b)}|${v}`), w: false, mi: md.mi[fi] });
        }
        while (ring.length > 1 && len(sub(ring[0].p, ring[ring.length - 1].p)) < 1e-9) ring.pop();
        const n = ring.length;
        if (n < 3) continue;
        const Cn = norm(nsum);
        const ws = ring.filter((r) => r.w);
        const alternating = ring.every((r, i) => r.w !== ring[(i + 1) % n].w);
        if (es.length >= 3 && alternating && ws.length >= 3) {
            let cs = [0, 0, 0];
            for (const r of ws) cs = add(cs, sub(r.p, pv));
            const C = add(pv, mul(cs, 0.2113));
            for (let i = 0; i < n; i++) {
                if (!ring[i].w) continue;
                const prev = ring[(i - 1 + n) % n], next = ring[(i + 1) % n];
                let pts = [C, next.p, ring[i].p, prev.p], nr = [Cn, next.n, ring[i].n, prev.n];
                if (dot(newell(pts).n, Cn) < 0) { pts = pts.reverse(); nr = nr.reverse(); }
                S.poly(pts, nr, [1, 1, 1, 1], [0, 0, 0, 0], ring[i].mi);
            }
            continue;
        }
        const ar = newell(ring.map((r) => r.p)).area;
        if (ar < 1e-12) continue;                                       // the strips run on through: nothing open
        let cs = [0, 0, 0];
        for (const r of ring) cs = add(cs, r.p);
        const C = mul(cs, 1 / n);
        for (let i = 0; i < n; i++) {
            const a = ring[i], b = ring[(i + 1) % n];
            let pts = [C, a.p, b.p], nr = [Cn, a.n, b.n];
            if (newell(pts).area < 1e-14) continue;
            if (dot(newell(pts).n, Cn) < 0) { pts = pts.reverse(); nr = nr.reverse(); }
            S.poly(pts, nr, [1, 1, 1], [0, 0, 0], a.mi);
        }
    }
    md.soup = S;
    return { faces: S.count.length, bevelled_edges: nBev, regions: NR };
}

// ------------------------------------------------------------------------------------------------ UV in metres
// each face projected along its dominant axis (x: (y, z), y: (x, z), z: (x, y)); a soup that carries its own UVs
// (the sheets, the painted lines) keeps them
function uvMetres(S) {
    if (S.uv) return;
    const uv = new Float32Array((S.pos.length / 3) * 2);
    for (let p = 0; p < S.start.length; p++) {
        const s = S.start[p], c = S.count[p];
        const pts = [];
        for (let k = 0; k < c; k++) pts.push([S.pos[(s + k) * 3], S.pos[(s + k) * 3 + 1], S.pos[(s + k) * 3 + 2]]);
        const n = newell(pts).n.map(Math.abs);
        const ax = n[0] >= n[1] && n[0] >= n[2] ? 0 : (n[1] >= n[2] ? 1 : 2);
        for (let k = 0; k < c; k++) {
            const q = pts[k];
            const [u, v] = ax === 0 ? [q[1], q[2]] : ax === 1 ? [q[0], q[2]] : [q[0], q[1]];
            uv[(s + k) * 2] = u; uv[(s + k) * 2 + 1] = v;
        }
    }
    S.uv = uv;
}

// ------------------------------------------------------------------------------------------------ the cavity bake
// the Blender kit's fourteen cosine-weighted directions (numpy's default_rng(7))
const HEMI = [[-0.790306969, -0.02259119, 0.612294483], [-0.894204738, -0.312428692, 0.320602868], [0.880378226, -0.024897174, 0.473618317],
    [0.125689219, -0.457612729, 0.880223159], [-0.394210607, -0.380479017, 0.836560646], [0.93239317, -0.064779791, 0.355593243],
    [0.015691618, 0.070845449, 0.997363873], [0.484555312, 0.765790159, 0.422813885], [-0.678736598, -0.579987982, 0.450478158],
    [0.658150438, 0.186475075, 0.72942789], [0.536708194, 0.122379495, 0.834845838], [-0.525353293, -0.04929026, 0.849455348],
    [-0.493508141, 0.106392209, 0.863209368], [0.578807925, -0.331749442, 0.744932006]];

// the vertex attribute `cavity` (0 open .. 1 closed in): the share of the hemisphere over each vertex that meets the
// mesh (or the plane z = ground) within dist, nearer hits counting more; a vertex of the inset loop of a large face
// holds 0 (a per-vertex mask may only vary where the mesh is dense)
export function bakeCavity(md, THREE, MeshBVH, { dist = 0.10, ground = null, bigFace = 0.0025 } = {}) {
    const S = md.soup;
    const nc = S.pos.length / 3;
    const vid = new Int32Array(nc);
    const keys = new Map();
    const P = [];
    for (let i = 0; i < nc; i++) {
        const k = `${Math.round(S.pos[i * 3] * 1e6)},${Math.round(S.pos[i * 3 + 1] * 1e6)},${Math.round(S.pos[i * 3 + 2] * 1e6)}`;
        let id = keys.get(k);
        if (id === undefined) { id = P.length; keys.set(k, id); P.push([S.pos[i * 3], S.pos[i * 3 + 1], S.pos[i * 3 + 2]]); }
        vid[i] = id;
    }
    const nv = P.length;
    const vn = new Float64Array(nv * 3), inner = new Uint8Array(nv), big = new Float64Array(nv);
    const tri = [];
    let lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (let p = 0; p < S.start.length; p++) {
        const s = S.start[p], c = S.count[p];
        const pts = [];
        for (let k = 0; k < c; k++) pts.push(P[vid[s + k]]);
        const { n, area } = newell(pts);
        for (let k = 0; k < c; k++) {
            const q = pts[k], a = pts[(k - 1 + c) % c], b = pts[(k + 1) % c];
            const ang = Math.acos(Math.max(-1, Math.min(1, dot(norm(sub(a, q)), norm(sub(b, q))))));
            const id = vid[s + k];
            vn[id * 3] += n[0] * ang; vn[id * 3 + 1] += n[1] * ang; vn[id * 3 + 2] += n[2] * ang;
            if (S.inner[s + k]) inner[id] = 1;
            big[id] = Math.max(big[id], area);
            lo = [Math.min(lo[0], q[0]), Math.min(lo[1], q[1]), Math.min(lo[2], q[2])];
            hi = [Math.max(hi[0], q[0]), Math.max(hi[1], q[1]), Math.max(hi[2], q[2])];
        }
        for (let k = 1; k < c - 1; k++) tri.push(...pts[0], ...pts[k], ...pts[k + 1]);
    }
    if (ground !== null && nv) {
        const a = [lo[0] - 1, lo[1] - 1, ground], b = [hi[0] + 1, lo[1] - 1, ground], c = [hi[0] + 1, hi[1] + 1, ground], d = [lo[0] - 1, hi[1] + 1, ground];
        tri.push(...a, ...b, ...c, ...a, ...c, ...d);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(tri, 3));
    const bvh = new MeshBVH(geo);
    const ray = new THREE.Ray();
    const out = new Float32Array(nv);
    for (let i = 0; i < nv; i++) {
        const n = norm([vn[i * 3], vn[i * 3 + 1], vn[i * 3 + 2]]);
        if (len(n) < 1e-6) continue;
        let t = cross(n, [0, 0, 1]);
        if (len(t) < 1e-4) t = cross(n, [1, 0, 0]);
        t = norm(t);
        const b = cross(n, t);
        const o = add(P[i], mul(n, 0.0008));
        let acc = 0;
        for (const [hx, hy, hz] of HEMI) {
            const d = [t[0] * hx + b[0] * hy + n[0] * hz, t[1] * hx + b[1] * hy + n[1] * hz, t[2] * hx + b[2] * hy + n[2] * hz];
            ray.origin.set(o[0], o[1], o[2]);
            ray.direction.set(d[0], d[1], d[2]);
            const hit = bvh.raycastFirst(ray, THREE.DoubleSide, 0, dist);
            if (hit && hit.distance <= dist) acc += 1.0 - hit.distance / dist;
        }
        out[i] = acc / HEMI.length;
        if (inner[i] && big[i] > bigFace) out[i] = 0;
    }
    geo.dispose();
    const cav = new Float32Array(nc);
    for (let i = 0; i < nc; i++) cav[i] = Math.min(1, Math.max(0, out[vid[i]] * 1.6));
    S.cavity = cav;
    let sum = 0, mx = 0;
    for (let i = 0; i < nv; i++) { sum += out[i]; mx = Math.max(mx, out[i]); }
    return { vertices: nv, mean: nv ? sum / nv : 0, max: mx };
}

// the whole preparation of one built mesh: detail(), then bakeCavity() (cavity 0: none)
export function finish(md, { bevel = 0.0025, inset = 0.014, cavity = 0.10, ground = null } = {}, ctx = null) {
    const r = detail(md, { bevel, inset });
    if (cavity && ctx) r.cavity = bakeCavity(md, ctx.THREE, ctx.MeshBVH, { dist: cavity, ground });
    if (ctx && ctx.log) ctx.log(`   detail ${md.name}: ${JSON.stringify(r)}`);
    return r;
}

// ------------------------------------------------------------------------------------------------ out
// a polygon's triangles: a quad on its first diagonal unless that folds it (as Blender tessellates), an n-gon by ear
// clipping in its own plane
function triangles(pts) {
    const m = pts.length;
    if (m === 3) return [[0, 1, 2]];
    const n = newell(pts).n;
    if (m === 4) {
        const d = (i, j, k) => dot(cross(sub(pts[j], pts[i]), sub(pts[k], pts[i])), n);
        if (d(0, 1, 2) > 0 && d(0, 2, 3) > 0) return [[0, 1, 2], [0, 2, 3]];
        return [[1, 2, 3], [1, 3, 0]];
    }
    const a = Math.abs(n[0]) > Math.abs(n[1]) ? (Math.abs(n[0]) > Math.abs(n[2]) ? 0 : 2) : (Math.abs(n[1]) > Math.abs(n[2]) ? 1 : 2);
    const [i0, i1] = a === 0 ? [1, 2] : a === 1 ? [2, 0] : [0, 1];
    const sgn = n[a] < 0 ? -1 : 1;
    const P2 = pts.map((p) => [p[i0], p[i1] * sgn]);
    const idx = [...Array(m).keys()];
    const out = [];
    const area2 = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
    let guard = 0;
    while (idx.length > 3 && guard++ < m * m) {
        let cut = false;
        for (let i = 0; i < idx.length; i++) {
            const ia = idx[(i - 1 + idx.length) % idx.length], ib = idx[i], ic = idx[(i + 1) % idx.length];
            const A = P2[ia], B = P2[ib], C = P2[ic];
            if (area2(A, B, C) <= 1e-18) continue;
            let inside = false;
            for (const j of idx) {
                if (j === ia || j === ib || j === ic) continue;
                const p = P2[j];
                if (area2(A, B, p) >= 0 && area2(B, C, p) >= 0 && area2(C, A, p) >= 0) { inside = true; break; }
            }
            if (inside) continue;
            out.push([ia, ib, ic]);
            idx.splice(i, 1);
            cut = true;
            break;
        }
        if (!cut) break;
    }
    if (idx.length === 3) out.push([idx[0], idx[1], idx[2]]);
    else for (let k = 1; k < idx.length - 1; k++) out.push([idx[0], idx[k], idx[k + 1]]);
    return out;
}

// -> BufferGeometry (Z-up, the hall's metres): its polygons grouped by material slot, the attributes position, normal,
// uv (metres), wear and cavity; geometry.userData.materials: the slots' material names
export function toGeometry(THREE, md) {
    const S = md.soup || (md.soup = plainSoup(md));
    uvMetres(S);
    const order = [...S.start.keys()].sort((a, b) => S.mi[a] - S.mi[b] || a - b);
    const idx = [];
    const groups = [];
    let cur = -1, gs = 0;
    for (const p of order) {
        if (S.mi[p] !== cur) { if (cur >= 0) groups.push([gs, idx.length - gs, cur]); cur = S.mi[p]; gs = idx.length; }
        const s = S.start[p], c = S.count[p];
        const pts = [];
        for (let k = 0; k < c; k++) pts.push([S.pos[(s + k) * 3], S.pos[(s + k) * 3 + 1], S.pos[(s + k) * 3 + 2]]);
        for (const t of triangles(pts)) idx.push(s + t[0], s + t[1], s + t[2]);
    }
    if (cur >= 0) groups.push([gs, idx.length - gs, cur]);
    const nc = S.pos.length / 3;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(S.pos), 3));
    geo.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(S.nrm), 3));
    geo.setAttribute('uv', new THREE.BufferAttribute(S.uv instanceof Float32Array ? S.uv : new Float32Array(S.uv), 2));
    geo.setAttribute('wear', new THREE.BufferAttribute(new Float32Array(S.wear), 1));
    geo.setAttribute('cavity', new THREE.BufferAttribute(S.cavity || new Float32Array(nc), 1));
    geo.setIndex(nc > 65535 ? new THREE.Uint32BufferAttribute(idx, 1) : new THREE.Uint16BufferAttribute(idx, 1));
    for (const [s, c, m] of groups) geo.addGroup(s, c, m);
    geo.computeBoundingBox();
    geo.computeBoundingSphere();
    geo.name = md.name;
    geo.userData.materials = md.mats;
    geo.userData.triangles = idx.length / 3;
    return geo;
}

// a topology check for the tests: every edge of the soup's polygons, welded by position, is shared by exactly two
// polygons (a closed input stays closed through the detail pass) -> the number of edges that are not
export function openEdges(md) {
    const S = md.soup;
    const key = (i) => `${Math.round(S.pos[i * 3] * 1e7)},${Math.round(S.pos[i * 3 + 1] * 1e7)},${Math.round(S.pos[i * 3 + 2] * 1e7)}`;
    const cnt = new Map();
    for (let p = 0; p < S.start.length; p++) {
        const s = S.start[p], c = S.count[p];
        for (let k = 0; k < c; k++) {
            const a = key(s + k), b = key(s + (k + 1) % c);
            if (a === b) continue;
            const e = a < b ? `${a}|${b}` : `${b}|${a}`;
            cnt.set(e, (cnt.get(e) || 0) + 1);
        }
    }
    let bad = 0;
    for (const v of cnt.values()) if (v !== 2) bad++;
    return bad;
}
