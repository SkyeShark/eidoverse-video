// eidoverse/sets/town/masks.js — the town's masks, from its geometry: every mask has a physical cause and the
// geometric signal that encodes it, computed once per unique mesh and stored PER FACE as the numbers the shader draws
// the mask with per pixel (look.js). Ray casts run on three-mesh-bvh. A port of eidoblend.sets.town.masks.
//
//   tlE  on an upright face: (edge, u0, u1, ends). edge: the height of the nearest edge water runs off above it (the
//        underside of what juts out over it, or the top of the wall it is part of), cast up from just outside and
//        just inside the face's top edge (1e4 elsewhere: no runs); u0, u1: its extent along the wall (x on a face
//        that looks along y, y on one that looks along x); ends: 1 when its low end is an INSIDE corner (something
//        stands out in front of the face there) + 2 when its high end is
//   tlB  on a face that looks up: its extent (x0, y0, x1, y1): dust and grit drift against whatever stands at its edges
//   tlS  on the upright faces of a struck building: the opening under it whose room burned (its middle along the wall,
//        its head's height, its half width, how hard it burned); on a road or a track: (its middle line, its half
//        width, 0, 0), the lane frame its wheel paths, oil line, gutters and ruts are drawn in
import { MeshBVH } from 'npm:three-mesh-bvh@0.9.10';

export const FAR = 1.0e4;
const SKIP = ['car_', 'palm', 'tree', 'bicycle'];                    // (things whose materials read no mask)
const STRUCK = ['town_HA', 'town_HC'];                               // the struck houses (soot over their openings)

// the faces' measures: normals, extents, the top edge's middle, the centre
export function faceInfo(b) {
    const n = b.f.length;
    const F = { n, nrm: [], x0: [], x1: [], y0: [], y1: [], z0: [], z1: [], tx: [], ty: [], cx: [], cy: [], area: [] };
    const { fn, area } = b.normals();
    for (let i = 0; i < n; i++) {
        const P = b.f[i].map((k) => b.v[k]);
        const xs = P.map((p) => p[0]), ys = P.map((p) => p[1]), zs = P.map((p) => p[2]);
        const z1 = Math.max(...zs);
        const top = P.filter((p) => p[2] >= z1 - 0.01);
        F.nrm.push(fn[i]); F.area.push(area[i]);
        F.x0.push(Math.min(...xs)); F.x1.push(Math.max(...xs)); F.y0.push(Math.min(...ys)); F.y1.push(Math.max(...ys)); F.z0.push(Math.min(...zs)); F.z1.push(z1);
        F.tx.push(top.reduce((s, p) => s + p[0], 0) / top.length); F.ty.push(top.reduce((s, p) => s + p[1], 0) / top.length);
        F.cx.push(xs.reduce((s, v) => s + v, 0) / P.length); F.cy.push(ys.reduce((s, v) => s + v, 0) / P.length);
    }
    return F;
}

// a BVH over a builder's polygons (triangulated), in its own space: cast(origin, dir, far) -> { z, distance } | null
export function caster(THREE, b) {
    const pos = [];
    for (const f of b.f) {
        for (let k = 1; k < f.length - 1; k++) for (const i of [f[0], f[k], f[k + 1]]) pos.push(...b.v[i]);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    const bvh = new MeshBVH(geo);
    const ray = new THREE.Ray();
    return {
        bvh, geo,
        cast(o, d, far) {
            ray.origin.set(o[0], o[1], o[2]);
            ray.direction.set(d[0], d[1], d[2]);
            const hit = bvh.raycastFirst(ray, THREE.DoubleSide, 0, far);
            if (!hit || hit.distance > far) return null;
            return { point: [hit.point.x, hit.point.y, hit.point.z], distance: hit.distance, normal: hit.face ? [hit.face.normal.x, hit.face.normal.y, hit.face.normal.z] : null };
        },
    };
}

// a stable number in 0..1 from a key (the per-mesh chance a burnt room had: two in three)
function h01(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0) / 0xFFFFFFFF;
}

// tlE, tlB, tlS of one design (name: its mesh's name) -> { tlE, tlB, tlS: [Float32Array(n * 4), 4] } (faceData for
// mb.geometry), or null for meshes that read no mask
export function annotate(THREE, name, b, stats = {}) {
    if (SKIP.some((p) => name.startsWith(p)) || b.f.length === 0) return null;
    const F = faceInfo(b);
    const C = caster(THREE, b);
    const n = F.n;
    const tlE = new Float32Array(n * 4), tlB = new Float32Array(n * 4), tlS = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) {
        const [nx0, ny0, nz] = F.nrm[i];
        tlE.set([FAR, -FAR, FAR, 0], i * 4);
        tlB.set([-FAR, -FAR, FAR, FAR], i * 4);
        if (Math.abs(nz) < 0.35) {
            const L = Math.hypot(nx0, ny0);
            if (L < 1e-6) continue;
            const nx = nx0 / L, ny = ny0 / L;
            // the water's edge above it
            const z = F.z1[i] - 0.02;
            let best = null;
            for (const off of [0.03, -0.04]) {                        // just outside the face, and just inside the wall
                const hit = C.cast([F.tx[i] + nx * off, F.ty[i] + ny * off, z], [0, 0, 1], 8.0);
                if (hit && hit.distance > 0.004) best = best === null ? hit.point[2] : Math.min(best, hit.point[2]);
            }
            tlE[i * 4] = best !== null ? best : F.z1[i];
            stats.walls = (stats.walls || 0) + 1;
            // its inside corners
            const alongx = Math.abs(ny0) > Math.abs(nx0);
            const [u0, u1] = alongx ? [F.x0[i], F.x1[i]] : [F.y0[i], F.y1[i]];
            if (u1 - u0 < 0.05) continue;
            const zc = (F.z0[i] + F.z1[i]) / 2.0;
            const flags = [];
            for (const [end, sgn] of [[u0, -1.0], [u1, 1.0]]) {
                const px = alongx ? end - sgn * 0.02 : F.cx[i];
                const py = alongx ? F.cy[i] : end - sgn * 0.02;
                const hit = C.cast([px + nx * 0.05, py + ny * 0.05, zc], alongx ? [sgn, 0, 0] : [0, sgn, 0], 0.3);
                flags.push(hit ? 1 : 0);
            }
            tlE[i * 4 + 1] = u0; tlE[i * 4 + 2] = u1; tlE[i * 4 + 3] = flags[0] + 2 * flags[1];
            if (flags[0] || flags[1]) stats.corners = (stats.corners || 0) + 1;
        } else if (nz > 0.7) {
            tlB.set([F.x0[i], F.y0[i], F.x1[i], F.y1[i]], i * 4);
            stats.flats = (stats.flats || 0) + 1;
        }
    }
    if (STRUCK.some((p) => name.startsWith(p))) stats.soot = (stats.soot || 0) + sootSources(name, b, F, tlS);
    if (name === 'town_ground' || name === 'town_streets') stats.lanes = (stats.lanes || 0) + lanes(b, F, tlS);
    C.geo.dispose();
    stats.meshes = (stats.meshes || 0) + 1;
    return { tlE: [tlE, 4], tlB: [tlB, 4], tlS: [tlS, 4] };
}

// soot over the openings whose room burned: from the house's 'void' faces (a dark room behind a lost window); which of
// those rooms burned is the mesh's own chance (two in three)
function sootSources(name, b, F, out) {
    const S = [];
    for (let i = 0; i < F.n; i++) {
        if (b.m[i] !== 'void' || Math.abs(F.nrm[i][2]) >= 0.3) continue;
        const alongx = Math.abs(F.nrm[i][1]) > Math.abs(F.nrm[i][0]);
        const [u0, u1] = alongx ? [F.x0[i], F.x1[i]] : [F.y0[i], F.y1[i]];
        const plane = alongx ? F.cy[i] : F.cx[i];
        const k = h01(`${name}|${F.cx[i].toFixed(2)}|${F.cy[i].toFixed(2)}|${F.z1[i].toFixed(2)}`);
        if (k > 0.67 || (u1 - u0) < 0.3) continue;
        S.push([alongx, Math.sign(alongx ? F.nrm[i][1] : F.nrm[i][0]), plane, (u0 + u1) / 2.0, F.z1[i], (u1 - u0) / 2.0, 0.55 + 0.45 * k / 0.67]);
    }
    if (!S.length) return 0;
    for (let i = 0; i < F.n; i++) {
        const nr = F.nrm[i];
        if (Math.abs(nr[2]) >= 0.3) continue;
        let bestV = out[i * 4 + 3] > 0 ? Math.exp(-(((alongOf(F, i, out[i * 4 + 0])) / (out[i * 4 + 2] + 0.42 * Math.max(F.z0[i] - out[i * 4 + 1], 0.0) + 0.3)) ** 2)) * out[i * 4 + 3] : 0.0;
        for (const [alongx, sgn, plane, su, sz, sw, sk] of S) {
            const c = alongx ? nr[1] : nr[0];
            if (!(Math.abs(c) > 0.9 && Math.sign(c) === sgn)) continue;
            if (Math.abs((alongx ? F.cy[i] : F.cx[i]) - plane) >= 0.8) continue;
            const uc = alongx ? F.cx[i] : F.cy[i];
            const dz = F.z0[i] - sz;
            if (!(dz > -0.4 && dz < 3.2)) continue;
            const wid = sw + 0.42 * Math.max(dz, 0.0) + 0.3;
            const v = Math.exp(-(((uc - su) / wid) ** 2)) * sk;
            if (v > bestV && v > 0.06) { out.set([su, sz, sw, sk], i * 4); bestV = v; }
        }
    }
    return S.length;
}
const alongOf = (F, i, su) => (Math.abs(F.nrm[i][1]) > Math.abs(F.nrm[i][0]) ? F.cx[i] : F.cy[i]) - su;

// the roads and tracks: each is a quad across its whole width, so its own extent is its lane frame
function lanes(b, F, out) {
    let n_ = 0;
    for (let i = 0; i < F.n; i++) {
        const m = b.m[i];
        if (!['road', 'road:y', 'track', 'track:y'].includes(m)) continue;
        if (m.endsWith(':y')) out.set([(F.x0[i] + F.x1[i]) / 2.0, (F.x1[i] - F.x0[i]) / 2.0, 0, 0], i * 4);
        else out.set([(F.y0[i] + F.y1[i]) / 2.0, (F.y1[i] - F.y0[i]) / 2.0, 0, 0], i * 4);
        n_ += 1;
    }
    return n_;
}
