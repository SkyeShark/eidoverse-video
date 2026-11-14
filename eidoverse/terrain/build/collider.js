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
// The ray caster visits only the lattice cells the ray's ground track touches (a 2D walk over each ring's lattice
// lines, down into a ring's hole through the child ring and out again), and tests each cell's triangles (its two
// halves, or its seam fan) with three's own Ray.intersectTriangle on the same vertices, as Mesh.raycast does. So
// every hit, its distance, point, face and face index are those of three's loop over all the triangles
// (tests/mesh_api/collider_test.mjs compares them), at the cost of the cells crossed. A vertical ray is one cell.
// A track that lies on a lattice line (a camera at x = 0 looking along z: the origin is on every ring's lattice)
// touches the cells on both sides of it, and a track through a lattice point all four around it: three counts a
// hit on a triangle's edge, so those cells are visited too. The skirt's triangles are tested only for a ray that
// crosses the outermost window's border.

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

const TOL = 1e-7;       // metres: a track this close to a lattice line or point touches the cells on its other side
const TIE = 1e-9;       // relative: two line crossings this close in ray parameter are one lattice point

// the cell holding v along one axis (on a lattice line: the cell above it), clamped to the ring
function cellOf(lines, v) {
    return Math.min(Math.max(searchsorted(lines, v, 'right') - 1, 0), lines.length - 2);
}

// the cell of a point along one axis, by the way the ray travels: on a lattice line it is the cell ahead
function cellAt(lines, v, d) {
    const i = (d < 0 ? searchsorted(lines, v, 'left') : searchsorted(lines, v, 'right')) - 1;
    return Math.min(Math.max(i, 0), lines.length - 2);
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

function inHole(r, i, j) {
    const h = r.holeLines;
    return h !== null && i >= h[2] && i < h[3] && j >= h[0] && j < h[1];
}

/** Call visit(ring, i, j) once for every lattice cell of the ring mesh that the ground track of the ray o + t d
 * touches for t in [t0, t1] (Blender axes: ox, oy the origin, dx, dy the direction's ground components), the cells
 * a track lying on a lattice line or passing through a lattice point touches on every side included (within 1e-7 m).
 * Cells inside a ring's hole are the child ring's. A ring's cells come in the order the ray meets them; visit may
 * return a ray parameter, and the walk then ends once it has passed it (the nearest hit: nothing beyond it is
 * needed). */
export function walkCells(rm, ox, oy, dx, dy, t0, t1, visit) {
    const rings = rm.rings;
    const seen = new Set();
    const tr = [0, 0];
    let limit = Infinity;

    const call = (k, i, j) => {
        const key = (k * 65536 + j) * 65536 + i;
        if (seen.has(key)) return;
        seen.add(key);
        const s = visit(k, i, j);
        if (typeof s === 'number' && s < limit) limit = s;
    };

    // every cell within TOL of the box [xa, xb] x [ya, yb] (a point, or a track that stays within TOL of one), in
    // ring k and, where the box reaches its hole, in the rings inside it
    const touchBox = (k, xa, xb, ya, yb) => {
        const r = rings[k], xm = r.xm, ym = r.ym;
        if (xb < xm[0] - TOL || xa > xm[r.nx - 1] + TOL || yb < ym[0] - TOL || ya > ym[r.ny - 1] + TOL) return;
        const i0 = cellOf(xm, xa - TOL), i1 = cellOf(xm, xb + TOL), j0 = cellOf(ym, ya - TOL), j1 = cellOf(ym, yb + TOL);
        let child = false;
        for (let j = j0; j <= j1; j++) {
            for (let i = i0; i <= i1; i++) {
                if (inHole(r, i, j)) child = true;
                else call(k, i, j);
            }
        }
        if (child) touchBox(k + 1, xa, xb, ya, yb);
    };
    const touchAt = (k, t) => touchBox(k, ox + t * dx, ox + t * dx, oy + t * dy, oy + t * dy);

    if (dx === 0 && dy === 0) {                          // a vertical ray: the cells holding the point
        touchBox(0, ox, ox, oy, oy);
        return;
    }
    const r0 = rings[0];
    tr[0] = t0;
    tr[1] = t1;
    if (!slab(ox, dx, r0.xm[0] - TOL, r0.xm[r0.nx - 1] + TOL, tr) || !slab(oy, dy, r0.ym[0] - TOL, r0.ym[r0.ny - 1] + TOL, tr)) return;
    const tA0 = tr[0], tB0 = tr[1];
    const xa = ox + tA0 * dx, xb = ox + tB0 * dx, ya = oy + tA0 * dy, yb = oy + tB0 * dy;
    const flatX = Math.abs(xb - xa) <= TOL, flatY = Math.abs(yb - ya) <= TOL;     // the track keeps to one x, one y
    if (flatX && flatY) {
        touchBox(0, Math.min(xa, xb), Math.max(xa, xb), Math.min(ya, yb), Math.max(ya, yb));
        return;
    }

    if (flatX || flatY) {
        // The track runs along one axis: in every ring it touches the rows (columns) within TOL of it, two of them
        // when it lies on a lattice line. Each ring is swept in the ray's direction; where a touched cell is in the
        // ring's hole the child ring is swept over the hole's stretch (once: it finds its own rows).
        const alongX = flatY;
        const o = alongX ? ox : oy, d = alongX ? dx : dy;
        const cLo = alongX ? Math.min(ya, yb) : Math.min(xa, xb), cHi = alongX ? Math.max(ya, yb) : Math.max(xa, xb);
        const up = d > 0;
        const sweep = (k, tA, tB) => {
            const r = rings[k];
            const along = alongX ? r.xm : r.ym, across = alongX ? r.ym : r.xm;
            if (cHi < across[0] - TOL || cLo > across[across.length - 1] + TOL) return;
            const a0 = cellOf(across, cLo - TOL), a1 = cellOf(across, cHi + TOL);
            const pA = o + tA * d, pB = o + tB * d;
            const b0 = cellOf(along, Math.min(pA, pB) - TOL), b1 = cellOf(along, Math.max(pA, pB) + TOL);
            let descended = false;
            for (let b = up ? b0 : b1; up ? b <= b1 : b >= b0; b += up ? 1 : -1) {
                if (((up ? along[b] : along[b + 1]) - o) / d > limit) return;
                for (let a = a0; a <= a1; a++) {
                    const i = alongX ? b : a, j = alongX ? a : b;
                    if (!inHole(r, i, j)) {
                        call(k, i, j);
                    } else if (!descended) {
                        descended = true;
                        const h = r.holeLines;
                        tr[0] = tA;
                        tr[1] = tB;
                        if (slab(o, d, (alongX ? r.xm[h[2]] : r.ym[h[0]]) - TOL, (alongX ? r.xm[h[3]] : r.ym[h[1]]) + TOL, tr)) {
                            sweep(k + 1, tr[0], tr[1]);
                        }
                    }
                }
            }
        };
        sweep(0, tA0, tB0);
        return;
    }

    // The general ray: a walk over each ring's lattice lines, cell by cell in the order the ray crosses them.
    const sx = dx > 0 ? 1 : -1, sy = dy > 0 ? 1 : -1;
    const walk = (k, tA, tB) => {
        const r = rings[k], xm = r.xm, ym = r.ym, nx = r.nx, ny = r.ny;
        const hole = r.holeLines;
        if (tA > limit) return;
        touchAt(k, tA);                                  // a start on a lattice line: the cells behind it too
        let i = cellAt(xm, ox + tA * dx, dx), j = cellAt(ym, oy + tA * dy, dy);
        let tCur = tA;
        for (;;) {
            if (tCur > limit) return;
            if (hole && i >= hole[2] && i < hole[3] && j >= hole[0] && j < hole[1]) {
                tr[0] = tCur;
                tr[1] = tB;
                if (slab(ox, dx, xm[hole[2]], xm[hole[3]], tr) && slab(oy, dy, ym[hole[0]], ym[hole[1]], tr) && tr[1] > tr[0]) {
                    const h1 = tr[1];
                    walk(k + 1, tr[0], h1);              // the child ring's stretch
                    if (h1 >= tB) break;
                    tCur = h1;
                    i = cellAt(xm, ox + h1 * dx, dx);
                    j = cellAt(ym, oy + h1 * dy, dy);
                    if (i >= hole[2] && i < hole[3] && j >= hole[0] && j < hole[1]) {
                        // rounding left the point inside the hole: leave through the side the ray crosses first
                        const ex = dx > 0 ? (xm[hole[3]] - ox) / dx : (xm[hole[2]] - ox) / dx;
                        const ey = dy > 0 ? (ym[hole[1]] - oy) / dy : (ym[hole[0]] - oy) / dy;
                        if (ex <= ey) i = dx > 0 ? hole[3] : hole[2] - 1;
                        if (ey <= ex) j = dy > 0 ? hole[1] : hole[0] - 1;
                    }
                    if (i < 0 || i > nx - 2 || j < 0 || j > ny - 2) break;
                    continue;
                }
            } else {
                call(k, i, j);
            }
            const tx = dx > 0 ? (xm[i + 1] - ox) / dx : (xm[i] - ox) / dx;
            const ty = dy > 0 ? (ym[j + 1] - oy) / dy : (ym[j] - oy) / dy;
            const tn = Math.min(tx, ty);
            if (tn > tB) break;
            if (Math.abs(tx - ty) <= TIE * (1 + Math.abs(tn))) {
                touchAt(k, tn);                          // through a lattice point: every cell around it
                i += sx;
                j += sy;
            } else if (tx < ty) {
                i += sx;
            } else {
                j += sy;
            }
            if (i < 0 || i > nx - 2 || j < 0 || j > ny - 2) break;
            tCur = tn;
        }
        if (tB <= limit) touchAt(k, tB);                 // an end on a lattice line: the cells beyond it too
    };
    walk(0, tA0, tB0);
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

    // three's checkGeometryIntersection for triangle t (Mesh.js, r184), on the same vertices: the hit is pushed on
    // `out`; returns its parameter along the local ray, or Infinity when the ray misses the triangle
    const test = (t, raycaster, out) => {
        const a = index[3 * t], b = index[3 * t + 1], c = index[3 * t + 2];
        const mi = slotOf(t);
        const material = Array.isArray(mesh.material) ? mesh.material[mi] : mesh.material;
        if (!material) return Infinity;
        vA.fromBufferAttribute(position, a);
        vB.fromBufferAttribute(position, b);
        vC.fromBufferAttribute(position, c);
        const hit = material.side === THREE.BackSide ? ray.intersectTriangle(vC, vB, vA, true, point)
            : ray.intersectTriangle(vA, vB, vC, material.side === THREE.FrontSide, point);
        if (hit === null) return Infinity;
        world.copy(point).applyMatrix4(mesh.matrixWorld);
        const distance = raycaster.ray.origin.distanceTo(world);
        if (distance < raycaster.near || distance > raycaster.far) return Infinity;
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
        return tmp.copy(point).sub(ray.origin).dot(ray.direction);
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
            let nearest = Infinity;
            for (let q = 0; q < n; q++) nearest = Math.min(nearest, test(tris[q], raycaster, found));
            // the nearest hit only: the cells the ray enters after it hold nothing nearer
            return first && nearest < Infinity ? nearest * (1 + 1e-9) + 1e-9 : undefined;
        });
        // The skirt hangs from the outermost border, a vertical wall on each side of the window: a ray can meet it
        // only where its ground track comes to that side's line, so only the wall's quads there are tested (quad k
        // runs from perimeter point k to k + 1, counter-clockwise from the south-west corner: kernels/mesh/skirt.wgsl)
        if (nAll > nTerrain) {
            const nx = r0.nx, ny = r0.ny, m = (nAll - nTerrain) / 2;
            for (let side = 0; side < 4; side++) {       // south, east, north, west
                const alongX = side === 0 || side === 2;
                const line = side === 0 ? ymin : side === 1 ? xmax : side === 2 ? ymax : xmin;
                const lines = alongX ? r0.xm : r0.ym;
                const oc = alongX ? oy : ox, dc = alongX ? dy : dx, oa = alongX ? ox : oy, da = alongX ? dx : dy;
                const tr = [t0, t1];
                if (!slab(oc, dc, line - TOL, line + TOL, tr) || !slab(oa, da, lines[0] - TOL, lines[lines.length - 1] + TOL, tr)) continue;
                const pa = da === 0 ? oa : oa + tr[0] * da, pb = da === 0 ? oa : oa + tr[1] * da;
                const s0 = cellOf(lines, Math.min(pa, pb) - TOL), s1 = cellOf(lines, Math.max(pa, pb) + TOL);
                for (let s = s0; s <= s1; s++) {
                    const k = side === 0 ? s : side === 1 ? nx - 1 + s : side === 2 ? 2 * nx + ny - 4 - s : m - 1 - s;
                    test(nTerrain + k, raycaster, found);
                    test(nTerrain + m + k, raycaster, found);
                }
            }
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
