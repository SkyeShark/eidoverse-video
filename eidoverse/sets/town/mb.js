// eidoverse/sets/town/mb.js — the town's mesh builder: every mesh is written face by face from its construction's own
// numbers (a wall from its bays and the openings reserved in it first, a tank turned from its profile), not modelled
// and then cut. Metres, in the town's own frame: +Z up (the town is carried into three's +Y-up world by its root).
//
//   const b = new MB();  b.box(lo, hi, 'plaster', { skip: 'z-' });  b.lathe(prof, c, 'zinc', { n: 12 });  ...
//   const g = b.geometry(THREE, faceData);   // -> BufferGeometry (groups by material) + .userData.materials
//
// A face carries its material's NAME (look.js makes the material) and whether it shades smooth. Flat things get their
// own vertices, so a flat face stays flat; turned and lofted things share theirs, so a tank is round.
// place(at, rz, rx, ry, s) is a placing matrix; catenary(a, b, sag) a slack line's points; arc(c, r, a0, a1, n) points
// on an arc in plan. Small vector and matrix helpers (V, M4) are exported for the builders.

// ------------------------------------------------------------------------------------------------ vectors -----------
export const V = {
    add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
    sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
    mul: (a, k) => [a[0] * k, a[1] * k, a[2] * k],
    dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
    cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
    len: (a) => Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]),
    norm: (a) => { const l = V.len(a); return l > 0 ? [a[0] / l, a[1] / l, a[2] / l] : [0, 0, 0]; },
    lerp: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
    // mathutils' Vector.orthogonal(): a vector at right angles, from the dominant axis
    ortho: (v) => {
        const x = Math.abs(v[0]), y = Math.abs(v[1]), z = Math.abs(v[2]);
        const ax = x > y ? (x > z ? 0 : 2) : (y > z ? 1 : 2);
        if (ax === 0) return [-v[1] - v[2], v[0], v[0]];
        if (ax === 1) return [v[1], -v[0] - v[2], v[1]];
        return [v[2], v[2], -v[0] - v[1]];
    },
    v3: (p) => [p[0], p[1], p.length > 2 ? p[2] : 0.0],
};

// 4 x 4 matrices, row-major (as mathutils prints them): m[r * 4 + c]
export const M4 = {
    I: () => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    T: (p) => [1, 0, 0, p[0], 0, 1, 0, p[1], 0, 0, 1, p[2] ?? 0, 0, 0, 0, 1],
    S: (s) => [s, 0, 0, 0, 0, s, 0, 0, 0, 0, s, 0, 0, 0, 0, 1],
    R: (a, axis) => {
        const c = Math.cos(a), s = Math.sin(a);
        if (axis === 'X') return [1, 0, 0, 0, 0, c, -s, 0, 0, s, c, 0, 0, 0, 0, 1];
        if (axis === 'Y') return [c, 0, s, 0, 0, 1, 0, 0, -s, 0, c, 0, 0, 0, 0, 1];
        return [c, -s, 0, 0, s, c, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
    },
    mul: (a, b) => {
        const o = new Array(16);
        for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++)
            o[r * 4 + c] = a[r * 4] * b[c] + a[r * 4 + 1] * b[4 + c] + a[r * 4 + 2] * b[8 + c] + a[r * 4 + 3] * b[12 + c];
        return o;
    },
    chain: (...ms) => ms.reduce((acc, m) => M4.mul(acc, m)),
    apply: (m, p) => {
        const x = p[0], y = p[1], z = p.length > 2 ? p[2] : 0.0;
        return [m[0] * x + m[1] * y + m[2] * z + m[3], m[4] * x + m[5] * y + m[6] * z + m[7], m[8] * x + m[9] * y + m[10] * z + m[11]];
    },
    rot: (m, p) => [m[0] * p[0] + m[1] * p[1] + m[2] * p[2], m[4] * p[0] + m[5] * p[1] + m[6] * p[2], m[8] * p[0] + m[9] * p[1] + m[10] * p[2]],
    // rows given as [[a, b, c, d], ...] (mathutils' Matrix((row, row, row, row)))
    rows: (r) => [...r[0], ...r[1], ...r[2], ...r[3]],
};

// a placing: turned about x, then y, then z, scaled, then moved to `at`
export function place(at, rz = 0.0, rx = 0.0, ry = 0.0, s = 1.0) {
    let m = M4.chain(M4.T(at), M4.R(rz, 'Z'), M4.R(ry, 'Y'), M4.R(rx, 'X'));
    if (s !== 1.0) m = M4.mul(m, M4.S(s));
    return m;
}

const FACES = [['z-', [0, 3, 2, 1]], ['z+', [4, 5, 6, 7]], ['y-', [0, 1, 5, 4]], ['x+', [1, 2, 6, 5]], ['y+', [2, 3, 7, 6]], ['x-', [3, 0, 4, 7]]];

export class MB {
    constructor() { this.v = []; this.f = []; this.m = []; this.s = []; this.uv = new Map(); }

    // ------------------------------------------------------------------ raw
    verts(pts) {
        const i = this.v.length;
        for (const p of pts) this.v.push([p[0], p[1], p[2]]);
        return i;
    }

    face(idx, m, smooth = false) { this.f.push([...idx]); this.m.push(m); this.s.push(smooth); }

    poly(pts, m, smooth = false, uv = null) {
        pts = [...pts];
        if (pts.length < 3) return;
        const i = this.verts(pts);
        this.face(pts.map((_, k) => i + k), m, smooth);
        if (uv) this.uv.set(this.f.length - 1, uv);
    }

    quad(a, b, c, d, m, uv = null) { this.poly([a, b, c, d], m, false, uv); }

    // another builder's faces, placed by M
    stamp(other, M = null) {
        const i = this.v.length;
        for (const p of other.v) this.v.push(M ? M4.apply(M, p) : [...p]);
        const n = this.f.length;
        for (const f of other.f) this.f.push(f.map((k) => k + i));
        this.m.push(...other.m);
        this.s.push(...other.s);
        for (const [k, uv] of other.uv) this.uv.set(n + k, uv);
    }

    // ------------------------------------------------------------------ flat-faced solids
    // a six-faced solid on eight corners in a box's order: the bottom four round, then the top four above them
    hexa(p, m, skip = '', top = null, mats = null) {
        for (const [k, idx] of FACES) {
            if (skip.includes(k)) continue;
            this.poly(idx.map((i) => p[i]), (mats && mats[k]) || ((k === 'z+' && top) ? top : m));
        }
    }

    // a box between two corners. skip: the faces nobody can see ('z-', 'y+x-' ...); M: a placing
    box(lo, hi, m, { skip = '', top = null, mats = null, M = null } = {}) {
        const [x0, y0, z0] = lo, [x1, y1, z1] = hi;
        let p = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]];
        if (M) p = p.map((q) => M4.apply(M, q));
        this.hexa(p, m, skip, top, mats);
    }

    // a bar of section w x h from a to b (an angle-iron leg, a rail, a brace): h stands along `up`
    beam(a, b, w, h, m, { up = [0.0, 0.0, 1.0], caps = true } = {}) {
        a = V.v3(a); b = V.v3(b);
        let t = V.sub(b, a);
        if (V.len(t) < 1e-6) return;
        t = V.norm(t);
        let s = V.cross(t, up);
        if (V.len(s) < 1e-4) s = V.cross(t, [1.0, 0.0, 0.0]);
        s = V.norm(s);
        let u = V.cross(s, t);
        s = V.mul(s, w / 2.0); u = V.mul(u, h / 2.0);
        const p = [V.sub(V.sub(a, s), u), V.sub(V.add(a, s), u), V.sub(V.add(b, s), u), V.sub(V.sub(b, s), u),
            V.add(V.sub(a, s), u), V.add(V.add(a, s), u), V.add(V.add(b, s), u), V.add(V.sub(b, s), u)];
        this.hexa(p, m, caps ? '' : 'y-y+');
    }

    // an outline [(x, y)], counter-clockwise from above, from z0 up to z1. sides: which of its edges get a wall
    prism(outline, z0, z1, m, { top = null, bottom = null, cap_top = true, cap_bot = true, sides = null, side_m = null } = {}) {
        const n = outline.length;
        if (cap_top) this.poly(outline.map(([x, y]) => [x, y, z1]), top || m);
        if (cap_bot) this.poly([...outline].reverse().map(([x, y]) => [x, y, z0]), bottom || m);
        for (let k = 0; k < n; k++) {
            if (sides && !sides[k]) continue;
            const [xa, ya] = outline[k], [xb, yb] = outline[(k + 1) % n];
            if (Math.abs(xa - xb) + Math.abs(ya - yb) < 1e-6) continue;
            this.quad([xa, ya, z0], [xb, yb, z0], [xb, yb, z1], [xa, ya, z1], side_m || m);
        }
    }

    // a broken piece of slab or wall: an outline [(x, y)] in its own plane (counter-clockwise), `thick` below it,
    // placed by M (hanging by its steel, lying on a heap)
    plate(outline, M, thick, top, side, bottom = null) {
        const up = outline.map(([x, y]) => M4.apply(M, [x, y, 0.0]));
        const dn = outline.map(([x, y]) => M4.apply(M, [x, y, -thick]));
        const n = outline.length;
        this.poly(up, top);
        this.poly([...dn].reverse(), bottom || side);
        for (let k = 0; k < n; k++) {
            const j = (k + 1) % n;
            this.quad(dn[k], dn[j], up[j], up[k], side);
        }
    }

    // ------------------------------------------------------------------ smooth surfaces (shared vertices)
    // a skin over rows of points P[row][column]; wrap_u: each row is a closed ring
    grid(P, m, { smooth = true, wrap_u = false, wrap_v = false, flip = false } = {}) {
        const nv = P.length, nu = P[0].length;
        const base = this.verts(P.flat());
        for (let j = 0; j < nv - (wrap_v ? 0 : 1); j++) {
            for (let i = 0; i < nu - (wrap_u ? 0 : 1); i++) {
                const a = base + j * nu + i, b = base + j * nu + (i + 1) % nu;
                const c = base + ((j + 1) % nv) * nu + (i + 1) % nu, d = base + ((j + 1) % nv) * nu + i;
                this.face(flip ? [a, d, c, b] : [a, b, c, d], m, smooth);
            }
        }
        return base;
    }

    // a profile [(radius, height)], bottom to top, turned about the vertical through c. cap0, cap1: materials for its
    // bottom and top discs. M: a placing (a tank lying down, a dome's finial leaning)
    lathe(prof, c, m, { n = 12, smooth = true, cap0 = null, cap1 = null, phase = 0.0, M = null } = {}) {
        const P = [];
        for (let [r, z] of prof) {
            r = Math.max(r, 0.002);
            const ring = [];
            for (let k = 0; k < n; k++) {
                const a = phase + 2 * Math.PI * k / n;
                ring.push([c[0] + r * Math.cos(a), c[1] + r * Math.sin(a), c[2] + z]);
            }
            P.push(M ? ring.map((q) => M4.apply(M, q)) : ring);
        }
        this.grid(P, m, { smooth, wrap_u: true });
        if (cap0) this.poly([...P[0]].reverse(), cap0);
        if (cap1) this.poly(P[P.length - 1], cap1);
    }

    // a round bar from a to b (a pole, a pipe, a leg); r1: its radius at b
    tube(a, b, r, m, { n = 8, r1 = null, caps = true, smooth = true } = {}) {
        this.path([a, b], r, m, { n, r1, caps, smooth });
    }

    // a round section carried along a line of points (a wire, a bent bar, a trunk): the frame is carried from point
    // to point without spinning. r may be a function of the fraction along
    path(pts, r, m, { n = 6, r1 = null, caps = false, smooth = true } = {}) {
        const P = pts.map(V.v3);
        if (P.length < 2) return;
        const L = P.length;
        let T = P.map((_, i) => V.sub(P[Math.min(i + 1, L - 1)], P[Math.max(i - 1, 0)]));
        T = T.map((t) => (V.len(t) > 1e-9 ? V.norm(t) : [0.0, 0.0, 1.0]));
        let u = V.norm(V.ortho(T[0]));
        const rings = [];
        T.forEach((t, i) => {
            u = V.sub(u, V.mul(t, V.dot(u, t)));
            u = V.len(u) > 1e-6 ? V.norm(u) : V.norm(V.ortho(t));
            const w = V.cross(t, u);
            let rr = r1 === null || typeof r === 'function' ? r : r + (r1 - r) * i / (L - 1);
            if (typeof r === 'function') rr = r(i / (L - 1));
            const ring = [];
            for (let k = 0; k < n; k++) {
                const ca = Math.cos(2 * Math.PI * k / n), sa = Math.sin(2 * Math.PI * k / n);
                ring.push(V.add(P[i], V.mul(V.add(V.mul(u, ca), V.mul(w, sa)), rr)));
            }
            rings.push(ring);
        });
        this.grid(rings, m, { smooth: smooth && n > 4, wrap_u: true });
        if (caps) {
            this.poly([...rings[0]].reverse(), m);
            this.poly(rings[rings.length - 1], m);
        }
    }

    // ------------------------------------------------------------------ a wall run in plan (parapets, kerbs, yard walls)
    // a wall of thickness t standing on a line of points [(x, y)] from z0 to z1, built to the LEFT of the line as it is
    // walked, mitred at every corner so nothing overlaps. inner: its inner face's material; ends: an open run's ends
    run(pts, t, z0, z1, m, { closed = false, top = null, inner = null, ends = [true, true], skip_outer = false } = {}) {
        const P = pts.map((p) => [p[0], p[1]]);
        if (closed && Math.hypot(P[0][0] - P[P.length - 1][0], P[0][1] - P[P.length - 1][1]) < 1e-6) P.pop();
        const n = P.length;
        if (n < 2) return;
        const seg = closed ? n : n - 1;
        const D = [];
        for (let k = 0; k < seg; k++) {
            const d = [P[(k + 1) % n][0] - P[k][0], P[(k + 1) % n][1] - P[k][1]];
            const l = Math.hypot(d[0], d[1]);
            D.push(l > 1e-9 ? [d[0] / l, d[1] / l] : [1.0, 0.0]);
        }
        const N = D.map((d) => [-d[1], d[0]]);                      // left of the walk
        const I = [];
        for (let k = 0; k < n; k++) {
            let n0, n1;
            if (closed) { n0 = N[((k - 1) % seg + seg) % seg]; n1 = N[k % seg]; }
            else { n0 = N[Math.max(k - 1, 0)]; n1 = N[Math.min(k, seg - 1)]; }
            const den = 1.0 + n0[0] * n1[0] + n0[1] * n1[1];
            I.push(den > 0.05 ? [P[k][0] + (n0[0] + n1[0]) * (t / den), P[k][1] + (n0[1] + n1[1]) * (t / den)]
                : [P[k][0] + n1[0] * t, P[k][1] + n1[1] * t]);
        }
        top = top || m;
        inner = inner || m;
        for (let k = 0; k < seg; k++) {
            const j = (k + 1) % n;
            const a = P[k], b_ = P[j], ia = I[k], ib = I[j];
            if (!skip_outer) this.quad([a[0], a[1], z0], [b_[0], b_[1], z0], [b_[0], b_[1], z1], [a[0], a[1], z1], m);
            this.quad([ib[0], ib[1], z0], [ia[0], ia[1], z0], [ia[0], ia[1], z1], [ib[0], ib[1], z1], inner);
            this.quad([a[0], a[1], z1], [b_[0], b_[1], z1], [ib[0], ib[1], z1], [ia[0], ia[1], z1], top);
        }
        if (!closed) {
            if (ends[0]) {
                const a = P[0], ia = I[0];
                this.quad([ia[0], ia[1], z0], [a[0], a[1], z0], [a[0], a[1], z1], [ia[0], ia[1], z1], m);
            }
            if (ends[1]) {
                const a = P[n - 1], ia = I[n - 1];
                this.quad([a[0], a[1], z0], [ia[0], ia[1], z0], [ia[0], ia[1], z1], [a[0], a[1], z1], m);
            }
        }
    }

    count() { return this.f.length; }

    // ------------------------------------------------------------------ out
    // the polygons' normals (Newell) and areas, and the smooth vertex normals (angle-weighted over the faces that
    // share a vertex, as Blender computes them)
    normals() {
        const fn = [], area = [];
        for (const f of this.f) {
            let nx = 0, ny = 0, nz = 0;
            for (let k = 0; k < f.length; k++) {
                const a = this.v[f[k]], b = this.v[f[(k + 1) % f.length]];
                nx += (a[1] - b[1]) * (a[2] + b[2]); ny += (a[2] - b[2]) * (a[0] + b[0]); nz += (a[0] - b[0]) * (a[1] + b[1]);
            }
            const l = Math.hypot(nx, ny, nz);
            fn.push(l > 0 ? [nx / l, ny / l, nz / l] : [0, 0, 1]);
            area.push(l / 2);
        }
        const vn = new Float64Array(this.v.length * 3);
        this.f.forEach((f, fi) => {
            if (!this.s[fi]) return;
            const n = fn[fi];
            for (let k = 0; k < f.length; k++) {
                const p = this.v[f[k]], a = this.v[f[(k - 1 + f.length) % f.length]], b = this.v[f[(k + 1) % f.length]];
                const e1 = V.norm(V.sub(a, p)), e2 = V.norm(V.sub(b, p));
                const ang = Math.acos(Math.max(-1, Math.min(1, V.dot(e1, e2))));
                vn[f[k] * 3] += n[0] * ang; vn[f[k] * 3 + 1] += n[1] * ang; vn[f[k] * 3 + 2] += n[2] * ang;
            }
        });
        for (let i = 0; i < this.v.length; i++) {
            const l = Math.hypot(vn[i * 3], vn[i * 3 + 1], vn[i * 3 + 2]);
            if (l > 0) { vn[i * 3] /= l; vn[i * 3 + 1] /= l; vn[i * 3 + 2] /= l; }
        }
        return { fn, area, vn };
    }

    // the faces as triangles: [[a, b, c] corner indices into the face], as Blender tessellates them (a quad on its
    // first diagonal unless that folds it; an n-gon by ear clipping in its own plane)
    static tessellate(pts, n, THREE) {
        if (pts.length === 3) return [[0, 1, 2]];
        if (pts.length === 4) {
            const d = (i, j, k) => V.dot(V.cross(V.sub(pts[j], pts[i]), V.sub(pts[k], pts[i])), n);
            if (d(0, 1, 2) > 0 && d(0, 2, 3) > 0) return [[0, 1, 2], [0, 2, 3]];
            return [[1, 2, 3], [1, 3, 0]];
        }
        const ax = Math.abs(n[0]) > Math.abs(n[1]) ? (Math.abs(n[0]) > Math.abs(n[2]) ? 0 : 2) : (Math.abs(n[1]) > Math.abs(n[2]) ? 1 : 2);
        const [i0, i1] = ax === 0 ? [1, 2] : ax === 1 ? [2, 0] : [0, 1];
        const flip = n[ax] < 0;
        const c2 = pts.map((p) => new THREE.Vector2(flip ? p[i1] : p[i0], flip ? p[i0] : p[i1]));
        const tris = THREE.ShapeUtils.triangulateShape(c2, []);
        return tris.map((t) => (THREE.ShapeUtils.isClockWise(c2) ? [t[0], t[2], t[1]] : t));
    }

    // -> BufferGeometry, Z-up, its faces grouped by material (geometry.userData.materials: the keys, in group order).
    // faceData: optional { name: [Float32Array(n * k), k] } per-face values written to every corner of the face;
    // keyOf(name): the material a face's name is drawn with (several names may share one, told apart by faceData)
    geometry(THREE, faceData = {}, keyOf = (m) => m) {
        const { fn, vn } = this.normals();
        const names = [];
        const slot = new Map();
        const keys = this.m.map(keyOf);
        keys.forEach((m) => { if (!slot.has(m)) { slot.set(m, names.length); names.push(m); } });
        const order = this.f.map((_, i) => i).sort((a, b) => slot.get(keys[a]) - slot.get(keys[b]) || a - b);
        const pos = [], nrm = [], uvs = [], idx = [];
        const extra = Object.fromEntries(Object.entries(faceData).map(([k, [, w]]) => [k, []]));
        const groups = [];
        let cur = -1, start = 0;
        const hasUV = this.uv.size > 0;
        for (const fi of order) {
            const g = slot.get(keys[fi]);
            if (g !== cur) {
                if (cur >= 0) groups.push([start, idx.length - start, cur]);
                cur = g; start = idx.length;
            }
            const f = this.f[fi];
            const pts = f.map((k) => this.v[k]);
            const base = pos.length / 3;
            const uv = this.uv.get(fi);
            for (let k = 0; k < f.length; k++) {
                pos.push(pts[k][0], pts[k][1], pts[k][2]);
                if (this.s[fi]) nrm.push(vn[f[k] * 3], vn[f[k] * 3 + 1], vn[f[k] * 3 + 2]);
                else nrm.push(fn[fi][0], fn[fi][1], fn[fi][2]);
                if (hasUV) { const q = uv ? uv[k % uv.length] : [0, 0]; uvs.push(q[0], q[1]); }
                for (const [name, [arr, w]] of Object.entries(faceData)) for (let c = 0; c < w; c++) extra[name].push(arr[fi * w + c]);
            }
            for (const t of MB.tessellate(pts, fn[fi], THREE)) idx.push(base + t[0], base + t[1], base + t[2]);
        }
        if (cur >= 0) groups.push([start, idx.length - start, cur]);
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        geo.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3));
        if (hasUV) geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
        for (const [name, [, w]] of Object.entries(faceData)) geo.setAttribute(name, new THREE.Float32BufferAttribute(extra[name], w));
        geo.setIndex(pos.length / 3 > 65535 ? new THREE.Uint32BufferAttribute(idx, 1) : new THREE.Uint16BufferAttribute(idx, 1));
        for (const [s, c, m] of groups) geo.addGroup(s, c, m);
        geo.computeBoundingBox();
        geo.computeBoundingSphere();
        geo.userData.materials = names;
        return geo;
    }
}

// points on an arc in plan, degrees
export function arc(c, r, a0, a1, n) {
    const out = [];
    for (let k = 0; k <= n; k++) {
        const a = (a0 + (a1 - a0) * k / n) * Math.PI / 180;
        out.push([c[0] + r * Math.cos(a), c[1] + r * Math.sin(a)]);
    }
    return out;
}

// a slack line's points between two points, hanging `sag` at its middle
export function catenary(a, b, sag, n = 8) {
    const out = [];
    for (let k = 0; k <= n; k++) {
        const p = V.lerp(a, b, k / n);
        out.push([p[0], p[1], p[2] - sag * (1.0 - (2.0 * k / n - 1.0) ** 2)]);
    }
    return out;
}
