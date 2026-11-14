// The terrain mesh's collider proxy and its exact ray caster (PORT_PLAN.md 7.5). No Blender file has this role:
// the Blender edition marks its terrain object `trimesh_collider` and leaves ray casts to Blender; a three.js scene
// builds a Rapier trimesh in JavaScript and casts rays through three's own loop over every triangle, and a film
// terrain is about 3.3 million triangles. Both are made small here without changing the surface:
//
//     const proxy = colliderProxy(THREE, rm, mesh, { roles });   // a Mesh of the rings near the focus, outside the
//                                                                // scene graph; mesh.userData.colliderProxy
//     installRaycast(THREE, mesh, rm);                           // mesh.raycast walks the rings' lattices
//
// The proxy is the visual surface itself: the same position attribute and a contiguous run of the same index buffer
// (the rings of the hero levels and the cores, or the main ring when there is no focus), so a body standing on it
// stands on the rendered triangles. It follows the terrain mesh's world matrix.
//
// The ray caster visits only the lattice cells the ray's ground track crosses, in order (a 2D walk over each ring's
// lattice lines, down into a ring's hole through the child ring and out again), and tests each cell's triangles
// (its two halves, or its seam fan) with three's own Ray.intersectTriangle on the same vertices, as Mesh.raycast
// does. So every hit, its distance, point, face and face index are those of three's loop over all the triangles
// (tests/mesh_api/raycast_test.mjs compares them), at the cost of the cells crossed. A vertical ray is one cell.
// The skirt's triangles are tested only for a ray that crosses the outermost window's border.

import { searchsorted } from './mesh.js';

export const COLLIDER_MAX_TRIANGLES = 2.1e6;            // "at most about 2 M": five 376 k hero rings and a 500 k core fit

/** The run of rings the collider proxy takes: [first, last] ring numbers. The rings of the hero levels (cores
 * included) when there are any, else those of the main level and everything finer; the coarsest are dropped while
 * the run holds more than maxTriangles. `roles`: each level's role. */
export function colliderRings(rm, roles, maxTriangles = COLLIDER_MAX_TRIANGLES) {
    const rings = rm.rings;
    const roleOf = (r) => roles?.[r.spec.level] ?? null;
    let first = rings.findIndex((r) => roleOf(r) === 'hero');
    if (first < 0) first = rings.findIndex((r) => roleOf(r) === 'main');
    if (first < 0) first = rings.length - 1;
    const last = rings.length - 1;
    const count = (a) => rings[last].triBase + rings[last].triangles - rings[a].triBase;
    while (first < last && count(first) > maxTriangles) first++;
    return [first, last];
}

/** The collider proxy of a terrain mesh (see the module doc): a THREE.Mesh that is not in the scene graph, shares
 * the visual geometry's vertices and holds the triangles of the rings colliderRings() names. opts: roles (each
 * level's role), maxTriangles, rings ([first, last], instead of the rule). */
export function colliderProxy(THREE, rm, mesh, opts = {}) {
    const [first, last] = opts.rings ?? colliderRings(rm, opts.roles ?? null, opts.maxTriangles ?? COLLIDER_MAX_TRIANGLES);
    const a = rm.rings[first], b = rm.rings[last];
    const start = 3 * a.triBase, end = 3 * (b.triBase + b.triangles);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', mesh.geometry.getAttribute('position'));
    g.setIndex(new THREE.BufferAttribute(rm.index.subarray(start, end), 1));
    g.boundingBox = mesh.geometry.boundingBox.clone();
    g.boundingSphere = mesh.geometry.boundingSphere.clone();
    const proxy = new THREE.Mesh(g, Array.isArray(mesh.material) ? mesh.material[0] : mesh.material);
    proxy.name = (mesh.name || 'terrain') + '_collider';
    proxy.visible = false;
    proxy.matrixAutoUpdate = false;
    proxy.userData.trimeshCollider = true;
    proxy.userData.colliderOf = mesh;
    proxy.userData.rings = [first, last];
    proxy.userData.triangles = (end - start) / 3;
    proxy.updateMatrixWorld = function () {             // it is not in the scene graph: it takes the terrain's matrix
        mesh.updateWorldMatrix(true, false);
        this.matrixWorld.copy(mesh.matrixWorld);
    };
    proxy.updateWorldMatrix = function () { this.updateMatrixWorld(true); };
    proxy.updateMatrixWorld(true);
    return proxy;
}


// ---------------------------------------------------------------------------------------- the ray caster ---

// the cell of a point along one axis, by the way the ray travels: on a lattice line it is the cell ahead
function cellAt(lines, v, d) {
    const n = lines.length;
    const i = (d < 0 ? searchsorted(lines, v, 'left') : searchsorted(lines, v, 'right')) - 1;
    return Math.min(Math.max(i, 0), n - 2);
}

// clip the parameter interval tr of a ray o + t d against lo <= coordinate <= hi; false when nothing is left
function slab(o, d, lo, hi, tr) {
    if (d === 0) return o >= lo && o <= hi;
    let a = (lo - o) / d, b = (hi - o) / d;
    if (a > b) [a, b] = [b, a];
    if (a > tr[0]) tr[0] = a;
    if (b < tr[1]) tr[1] = b;
    return tr[0] <= tr[1];
}

/** Call visit(ring, i, j) for every lattice cell of the ring mesh that the ground track of the ray o + t d crosses
 * for t in [t0, t1], in the order the ray meets them (Blender axes: ox, oy the origin, dx, dy the direction's ground
 * components). visit returning true stops the walk. Cells inside a ring's hole are the child ring's. */
export function walkCells(rm, ox, oy, dx, dy, t0, t1, visit) {
    const rings = rm.rings;
    const EPS = 1e-9;
    if (dx === 0 && dy === 0) {
        // a vertical ray: the cells holding the point (two or four of them when it lies on a lattice line or point,
        // and the neighbour ring's when it lies on a ring's border)
        for (let k = 0; k < rings.length; k++) {
            const r = rings[k];
            if (ox < r.xm[0] || ox > r.xm[r.nx - 1] || oy < r.ym[0] || oy > r.ym[r.ny - 1]) break;
            const is = [cellAt(r.xm, ox, 1)], js = [cellAt(r.ym, oy, 1)];
            const il = cellAt(r.xm, ox, -1), jl = cellAt(r.ym, oy, -1);
            if (il !== is[0]) is.push(il);
            if (jl !== js[0]) js.push(jl);
            for (const j of js) for (const i of is) if (!inHole(r, i, j) && visit(k, i, j)) return true;
        }
        return false;
    }
    const sx = dx > 0 ? 1 : -1, sy = dy > 0 ? 1 : -1;
    const tr = [0, 0];

    const walk = (k, tA, tB) => {
        const r = rings[k], xm = r.xm, ym = r.ym, nx = r.nx, ny = r.ny;
        const hole = r.holeLines;
        let i = cellAt(xm, ox + tA * dx, dx), j = cellAt(ym, oy + tA * dy, dy);
        // a ray along a lattice line touches the cells on both of its sides
        const twinJ = dy === 0 && j > 0 && oy === ym[j] ? j - 1 : -1;
        const twinI = dx === 0 && i > 0 && ox === xm[i] ? i - 1 : -1;
        let tCur = tA;
        for (;;) {
            if (hole && i >= hole[2] && i < hole[3] && j >= hole[0] && j < hole[1]) {
                tr[0] = tCur;
                tr[1] = tB;
                if (slab(ox, dx, xm[hole[2]], xm[hole[3]], tr) && slab(oy, dy, ym[hole[0]], ym[hole[1]], tr) && tr[1] > tr[0]) {
                    const h0 = tr[0], h1 = tr[1];
                    // along a hole's edge line: this ring's cells on the line's other side, beside the hole
                    if (twinJ >= 0 && !inHole(r, i, twinJ)) {
                        const ia = cellAt(xm, ox + h0 * dx, dx), ib = cellAt(xm, ox + h1 * dx, -dx);
                        for (let q = Math.min(ia, ib); q <= Math.max(ia, ib); q++) if (visit(k, q, twinJ)) return true;
                    }
                    if (twinI >= 0 && !inHole(r, twinI, j)) {
                        const ja = cellAt(ym, oy + h0 * dy, dy), jb = cellAt(ym, oy + h1 * dy, -dy);
                        for (let q = Math.min(ja, jb); q <= Math.max(ja, jb); q++) if (visit(k, twinI, q)) return true;
                    }
                    if (walk(k + 1, h0, h1)) return true;
                    if (h1 >= tB) return false;
                    tCur = h1;
                    i = cellAt(xm, ox + h1 * dx, dx);
                    j = cellAt(ym, oy + h1 * dy, dy);
                    if (i >= hole[2] && i < hole[3] && j >= hole[0] && j < hole[1]) {
                        // rounding left the point inside the hole: leave through the side the ray crosses first
                        const tx = dx > 0 ? (xm[hole[3]] - ox) / dx : dx < 0 ? (xm[hole[2]] - ox) / dx : Infinity;
                        const ty = dy > 0 ? (ym[hole[1]] - oy) / dy : dy < 0 ? (ym[hole[0]] - oy) / dy : Infinity;
                        if (tx <= ty) i = dx > 0 ? hole[3] : hole[2] - 1;
                        if (ty <= tx) j = dy > 0 ? hole[1] : hole[0] - 1;
                    }
                    if (i < 0 || i > nx - 2 || j < 0 || j > ny - 2) return false;
                    continue;
                }
            } else {
                if (visit(k, i, j)) return true;
                if (twinJ >= 0 && !inHole(r, i, twinJ) && visit(k, i, twinJ)) return true;
                if (twinI >= 0 && !inHole(r, twinI, j) && visit(k, twinI, j)) return true;
            }
            const tx = dx > 0 ? (xm[i + 1] - ox) / dx : dx < 0 ? (xm[i] - ox) / dx : Infinity;
            const ty = dy > 0 ? (ym[j + 1] - oy) / dy : dy < 0 ? (ym[j] - oy) / dy : Infinity;
            const tn = Math.min(tx, ty);
            if (tn > tB) return false;
            if (Math.abs(tx - ty) <= EPS * (1 + Math.abs(tn))) {
                // through a lattice point (or within rounding of one): the two cells beside it are touched too
                const i2 = i + sx, j2 = j + sy;
                if (i2 >= 0 && i2 <= nx - 2 && !inHole(r, i2, j) && visit(k, i2, j)) return true;
                if (j2 >= 0 && j2 <= ny - 2 && !inHole(r, i, j2) && visit(k, i, j2)) return true;
                i = i2;
                j = j2;
            } else if (tx < ty) {
                i += sx;
            } else {
                j += sy;
            }
            if (i < 0 || i > nx - 2 || j < 0 || j > ny - 2) return false;
            tCur = tn;
        }
    };

    const r0 = rings[0];
    tr[0] = t0;
    tr[1] = t1;
    if (!slab(ox, dx, r0.xm[0], r0.xm[r0.nx - 1], tr) || !slab(oy, dy, r0.ym[0], r0.ym[r0.ny - 1], tr)) return false;
    return walk(0, tr[0], tr[1]);
}

function inHole(r, i, j) {
    const h = r.holeLines;
    return h !== null && i >= h[2] && i < h[3] && j >= h[0] && j < h[1];
}

/** Replace mesh.raycast by the height-grid ray caster (see the module doc). The geometry is also kept from a
 * three-mesh-bvh tree (geometry.computeBoundsTree does nothing): building one would reorder the index buffer, whose
 * order the ring groups, the collider proxy and this ray caster rely on, and the caster needs none. */
export function installRaycast(THREE, mesh, rm) {
    const geometry = mesh.geometry;
    const position = geometry.getAttribute('position');
    const index = rm.index;
    const groups = geometry.groups;
    const ray = new THREE.Ray(), inverse = new THREE.Matrix4();
    const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
    const point = new THREE.Vector3(), world = new THREE.Vector3(), tmp = new THREE.Vector3();
    const tris = [];
    const nTerrain = rm.terrainTriangles, nAll = index.length / 3;
    const r0 = rm.rings[0];
    const xmin = r0.xm[0], xmax = r0.xm[r0.nx - 1], ymin = r0.ym[0], ymax = r0.ym[r0.ny - 1];

    // the material slot of triangle t: its geometry group's (one group a ring, then the skirt's)
    const slotOf = (t) => {
        let g = 0;
        while (g + 1 < groups.length && 3 * t >= groups[g + 1].start) g++;
        return groups.length ? groups[g].materialIndex : 0;
    };

    // three's checkGeometryIntersection for triangle t (Mesh.js, r184), on the same vertices
    const test = (t, raycaster, out) => {
        const a = index[3 * t], b = index[3 * t + 1], c = index[3 * t + 2];
        const mi = slotOf(t);
        const material = Array.isArray(mesh.material) ? mesh.material[mi] : mesh.material;
        if (!material) return false;
        vA.fromBufferAttribute(position, a);
        vB.fromBufferAttribute(position, b);
        vC.fromBufferAttribute(position, c);
        const hit = material.side === THREE.BackSide ? ray.intersectTriangle(vC, vB, vA, true, point)
            : ray.intersectTriangle(vA, vB, vC, material.side === THREE.FrontSide, point);
        if (hit === null) return false;
        world.copy(point).applyMatrix4(mesh.matrixWorld);
        const distance = raycaster.ray.origin.distanceTo(world);
        if (distance < raycaster.near || distance > raycaster.far) return false;
        const barycoord = new THREE.Vector3();
        THREE.Triangle.getBarycoord(point, vA, vB, vC, barycoord);
        const it = { distance, point: world.clone(), object: mesh };
        const uv = geometry.attributes.uv, normal = geometry.attributes.normal;
        if (uv) it.uv = THREE.Triangle.getInterpolatedAttribute(uv, a, b, c, barycoord, new THREE.Vector2());
        if (normal) {
            it.normal = THREE.Triangle.getInterpolatedAttribute(normal, a, b, c, barycoord, new THREE.Vector3());
            if (it.normal.dot(ray.direction) > 0) it.normal.multiplyScalar(-1);
        }
        const face = { a, b, c, normal: new THREE.Vector3(), materialIndex: mi };
        THREE.Triangle.getNormal(vA, vB, vC, face.normal);
        it.face = face;
        it.barycoord = barycoord;
        it.faceIndex = t;
        out.push(it);
        return true;
    };

    mesh.raycast = function (raycaster, intersects) {
        if (this.material === undefined) return;
        inverse.copy(this.matrixWorld).invert();
        ray.copy(raycaster.ray).applyMatrix4(inverse);
        if (geometry.boundingBox !== null && ray.intersectsBox(geometry.boundingBox) === false) return;
        // the walk's range along the local ray, from the world near and far distances
        let t0 = 0, t1 = Infinity;
        const along = (d) => tmp.copy(raycaster.ray.direction).multiplyScalar(d).add(raycaster.ray.origin).applyMatrix4(inverse)
            .sub(ray.origin).dot(ray.direction);
        if (raycaster.near > 0) t0 = Math.max(0, along(raycaster.near) * (1 - 1e-9) - 1e-9);
        if (Number.isFinite(raycaster.far)) t1 = along(raycaster.far) * (1 + 1e-9) + 1e-9;
        if (!(t1 >= t0)) return;
        // Blender's ground plane: x east, y north = -z
        const ox = ray.origin.x, oy = -ray.origin.z, dx = ray.direction.x, dy = -ray.direction.z;
        const first = raycaster.firstHitOnly === true;
        const found = [];
        walkCells(rm, ox, oy, dx, dy, t0, t1, (k, i, j) => {
            const n = rm.cellTriangles(k, i, j, tris);
            let any = false;
            for (let q = 0; q < n; q++) any = test(tris[q], raycaster, found) || any;
            return first && any;
        });
        // the skirt hangs on the outermost border: only a ray whose ground track reaches the border can meet it
        if (nAll > nTerrain) {
            const inside = (x, y) => x > xmin && x < xmax && y > ymin && y < ymax;
            let reaches;
            if (dx === 0 && dy === 0) {
                reaches = !inside(ox, oy) && ox >= xmin && ox <= xmax && oy >= ymin && oy <= ymax;
            } else {
                const tr = [t0, t1];
                reaches = slab(ox, dx, xmin, xmax, tr) && slab(oy, dy, ymin, ymax, tr) &&
                    (tr[0] > t0 || tr[1] < t1 || !inside(ox + t0 * dx, oy + t0 * dy) || !inside(ox + t1 * dx, oy + t1 * dy));
            }
            if (reaches) for (let t = nTerrain; t < nAll; t++) test(t, raycaster, found);
        }
        if (first && found.length > 1) {
            found.sort((p, q) => p.distance - q.distance);
            found.length = 1;
        }
        for (const it of found) intersects.push(it);
    };
    geometry.computeBoundsTree = function () { return null; };
    mesh.userData.exactRaycast = true;
    return mesh;
}
