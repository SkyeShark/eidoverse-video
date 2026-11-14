// Port of blender/eidoblend/terrain/build/water.py at f90c6fc.
//
// A terrain's water surfaces (design section 7): flat lake meshes at their levels, a sea grid at sea level, and a
// simple water material, dark and glossy, tinted by depth.
//
//     const lakes = await lakeObjects(THREE, R, t);          // one Mesh per level that holds lake water (its ring)
//     const sea = await seaObject(THREE, R, t, seaLevel);    // null when seaLevel is null
//     const mat = waterMaterial(THREE);
//
// Lakes come from each level's `water` field (lake depth in metres; the runner's hydrology fills depressions into
// it, real_place carves it under a DEM's lakes). On every level, the wet cells are split into lakes (8-connected); a
// lake shallower than minDepthM everywhere is dropped; each lake is flat at its level (the median of h + water over
// it, the spill level) and grown one cell under its shore, so the plane runs into the bank and the waterline is
// where the ground rises through it. A level draws only the cells of its own ring (outside its child's window,
// which lies on its cell grid), so the pieces of one lake on two levels meet edge to edge, at the same level,
// without overlapping. Cells at the sea's level are left to the sea grid. Each vertex carries eidoWater, the depth
// to the rendered ground under it (the material's tint).
//
// Where this differs from water.py, and why (PORT_PLAN.md 2.4, 3.2):
//   - Everything per cell and per vertex runs on the GPU (kernels/water/, core/prims.js) and is read back once per
//     level: the labels (prims.label, numpy's numbering); every lake's deepest water (an integer atomicMax per
//     label), cell count and level at once, where water.py loops over the lakes (the level from the two middle
//     items of the lake's run in a sort of the wet cells by (lake, h + water)); the (lake, cell) and (lake, corner)
//     streams by stream compaction, each stably sorted by lake, which are lake_geometry's quads and its np.unique
//     vertices in Blender's order; the depth under each vertex from the ring mesh's GPU sampler
//     (kernels/mesh/height_at.wgsl).
//   - h + water is added in float32 (Blender adds in float64): the order statistics are the float64 ones rounded to
//     float32, so a lake of an odd number of cells has Blender's float32 level to the bit and an even one is within
//     one float32 step of it. The depth is float32 (Blender: float64 rounded once).
//   - A three.js index buffer holds triangles: each quad (a, b, c, d) is written as (a, b, c), (a, c, d).
//   - Positions are three.js's (x, level, -y); the depth attribute is eidoWater (Blender: eido_water); the material
//     is a NodeMaterial with the same colours, roughness and index of refraction.
//   - The meshes are marked userData.noWalkable (a character does not stand on water) and are not parented to the
//     terrain mesh: a scene adds them (scene.add(t.mesh, ...t.water.lakes)).

import * as Gd from '../core/grid.js';
import { pyRound } from '../core/levels.js';
import { f32AtOrBelow, keyToFloat, lineGroups, prims } from '../core/prims.js';

export const SEA_TOL_M = 0.05;
export const SEA_GRID = 160;                            // vertices per side of the sea grid
const NONE = 0xFFFFFFFF;
const cover = (h, w = h) => [Math.ceil(w / 16), Math.ceil(h / 16), 1];
const bitsFor = (n) => Math.max(1, Math.ceil(Math.log2(Math.max(n, 2))));

/** One level's lakes (water.py _lake_cells, without the per-lake cell sets, which stay on the GPU as labels):
 * null when the level holds no lake water, else { labels (a u32 field: 0 dry, 1 .. count), rank (Uint32Array over
 * the labels: a kept lake's rank, NONE otherwise), lakes: [{ label, level (metres, float64), wet (cells), deepest
 * (metres) }], hole: [i0, j0, m, 0] the child's window in this level's cells }. `h` and `water` are the level's
 * n x n Float32Arrays (row 0 south); the caller releases `labels`. */
export async function lakeCells(R, lv, h, water, child, minDepthM, seaLevel) {
    const P = prims(R);
    const n = lv.n;
    const wF = R.field(n, n, 1, water);
    const made = [wF];
    try {
        const wet = P.where(wF, '>', f32AtOrBelow(1e-6));     // float64(w) > 1e-6, decided exactly in float32
        made.push(wet);
        const { labels, count } = await P.label(wet);
        if (!count) {
            labels.destroy();
            return null;
        }
        made.push(labels);
        // every lake's deepest water, and the wet cells sorted by (lake, h + water)
        const deepest = P.list(count + 1, 'u32');
        R.run('water/label_max', { lab: labels, w: wF }, { outM: deepest }, {}, cover(n));
        const hF = R.field(n, n, 1, h);
        const s = Gd.arith(R, 'add', hF, wF);
        const sKeys = P.floatKeys(s);
        made.push(deepest, hF, s, sKeys);
        const { index, n: N } = await P.nonzero(wet);
        const lab = P.gather(labels, index), sk = P.gather(sKeys, index), sv = P.gather(s, index);
        const perm = P.lexsort([sk, lab], { count: N });
        const sorted = P.gather(sv, perm);
        const cnt = P.bincount(lab, count + 1, { count: N });
        made.push(index, lab, sk, sv, perm, sorted, cnt);
        const [dk, cn] = await R.readParts([{ field: deepest, count: count + 1 }, { field: cnt, count: count + 1 }]);
        // the two middle items of every lake's run
        const picks = new Uint32Array(2 * count);
        let start = 0;
        for (let k = 1; k <= count; k++) {
            picks[2 * (k - 1)] = start + ((cn[k] - 1) >> 1);
            picks[2 * (k - 1) + 1] = start + (cn[k] >> 1);
            start += cn[k];
        }
        const pick = P.list(2 * count, 'u32', picks);
        const mids = P.gather(sorted, pick);
        made.push(pick, mids);
        const md = await R.readRange(mids, 0, 2 * count);
        const rank = new Uint32Array(count + 1).fill(NONE);
        const lakes = [];
        for (let k = 1; k <= count; k++) {
            const deep = keyToFloat(dk[k]);
            if (deep < minDepthM) continue;
            const a = md[2 * (k - 1)], b = md[2 * (k - 1) + 1];
            const level = cn[k] % 2 ? a : (a + b) / 2;       // np.median of the float64 sums
            if (seaLevel !== null && Math.abs(level - seaLevel) <= SEA_TOL_M) continue;
            rank[k] = lakes.length;
            lakes.push({ label: k, level, wet: cn[k], deepest: deep });
        }
        let hole = [0, 0, 0, 0];
        if (child) {
            hole = [pyRound((child.x0 - lv.x0) / lv.cell), pyRound((child.y0 - lv.y0) / lv.cell), pyRound(child.side / lv.cell), 0];
        }
        made.splice(made.indexOf(labels), 1);
        return { labels, rank, lakes, hole, count };
    } finally {
        for (const f of made) if (!f.destroyed) f.destroy();
    }
}

/** The geometry of a level's lakes (water.py lake_geometry and lake_objects' depth), from lakeCells' result:
 * null when no lake keeps a cell in the level's ring, else { positions, normals (three.js axes, 3 numbers a
 * vertex), depth (one a vertex), index (Uint32Array, two triangles a quad), vertices, quads, lakes: [{ level_m,
 * cells }] in Blender's order (a lake whose grown cells all lie in the child's window is left out, as Blender
 * leaves it out) }. One quad per cell, counter-clockwise from above, corners shared within a lake. */
export async function lakeGeometry(R, lv, st, rm) {
    const P = prims(R);
    const n = lv.n, m = n + 1;
    const nl = st.lakes.length;
    if (!nl) return null;
    const made = [];
    const keep = (f) => { made.push(f); return f; };
    try {
        const rank = keep(P.list(st.count + 1, 'u32', st.rank));
        const d1 = keep(R.field(1, 1, 1, null, 'u32')), d2 = keep(R.field(1, 1, 1, null, 'u32'));
        const uHole = st.hole;
        // how many lakes cover each cell, and use each corner
        const cellN = keep(R.field(n, n, 1, null, 'u32'));
        R.run('water/lake_cells', { lab: st.labels, rank, pos: P.dummyU }, { outN: cellN, outR: d1, outC: d2 }, { uMode: 0, uHole }, cover(n));
        const cornN = keep(R.field(m, m, 1, null, 'u32'));
        R.run('water/lake_corners', { lab: st.labels, rank, pos: P.dummyU }, { outN: cornN, outR: d1, outC: d2 }, { uMode: 0, uHole }, cover(m));
        const cellPos = keep(P.cumsum(cellN, { exclusive: true })), cornPos = keep(P.cumsum(cornN, { exclusive: true }));
        const tot = await R.readParts([{ field: cellPos, first: n * n - 1, count: 1 }, { field: cellN, first: n * n - 1, count: 1 },
            { field: cornPos, first: m * m - 1, count: 1 }, { field: cornN, first: m * m - 1, count: 1 }]);
        const Q = tot[0][0] + tot[1][0], V = tot[2][0] + tot[3][0];
        if (!Q) return null;
        // the (lake, cell) and (lake, corner) streams, each sorted by lake (stable: cells and corners stay in order)
        const qR = keep(P.list(Q)), qC = keep(P.list(Q)), vR = keep(P.list(V)), vC = keep(P.list(V));
        R.run('water/lake_cells', { lab: st.labels, rank, pos: cellPos }, { outN: cellN, outR: qR, outC: qC }, { uMode: 1, uHole }, cover(n));
        R.run('water/lake_corners', { lab: st.labels, rank, pos: cornPos }, { outN: cornN, outR: vR, outC: vC }, { uMode: 1, uHole }, cover(m));
        const bits = bitsFor(nl);
        const qs = P.sortPairs(qR, qC, { count: Q, bits }), vs = P.sortPairs(vR, vC, { count: V, bits });
        keep(qs.keys); keep(qs.vals); keep(vs.keys); keep(vs.vals);
        const vCnt = keep(P.bincount(vs.keys, nl + 1, { count: V }));
        const vStart = keep(P.cumsum(vCnt, { count: nl + 1, exclusive: true }));
        const qCnt = keep(P.bincount(qs.keys, nl + 1, { count: Q }));
        // the corner lines and the levels as Blender's mesh holds them: float64 rounded once to float32
        const xl = new Float32Array(m), yl = new Float32Array(m);
        for (let c = 0; c < m; c++) {
            xl[c] = lv.x0 + c * lv.cell;
            yl[c] = lv.y0 + c * lv.cell;
        }
        const xlF = keep(P.list(m, 'f32', xl)), ylF = keep(P.list(m, 'f32', yl));
        const levelF = keep(P.list(nl, 'f32', Float32Array.from(st.lakes, (l) => l.level)));
        const pos = keep(P.list(3 * V, 'f32')), nrm = keep(P.list(3 * V, 'f32')), pts = keep(P.list(2 * V, 'f32'));
        R.run('water/lake_vertices', { vRank: vs.keys, vCorner: vs.vals, xl: xlF, yl: ylF, level: levelF },
            { outP: pos, outN: nrm, outQ: pts }, { uCount: V, uN: n }, lineGroups(V));
        const tri = keep(P.list(6 * Q, 'u32'));
        R.run('water/lake_quads', { qRank: qs.keys, qCell: qs.vals, vCorner: vs.vals, vStart }, { outT: tri },
            { uCount: Q, uN: n }, lineGroups(Q));
        const ground = keep(rm.heightField(R, pts, V));
        const depth = keep(P.list(V, 'f32'));
        R.run('water/depth', { pos, ground }, { outD: depth }, { uCount: V }, lineGroups(V));
        const [positions, normals, dep, index, qc] = await R.readParts([{ field: pos, count: 3 * V }, { field: nrm, count: 3 * V },
            { field: depth, count: V }, { field: tri, count: 6 * Q }, { field: qCnt, count: nl }]);
        const lakes = [];
        st.lakes.forEach((l, r) => {
            if (qc[r]) lakes.push({ level_m: l.level, cells: qc[r], wet: l.wet, deepest_m: l.deepest });
        });
        return { positions, normals, depth: dep, index, vertices: V, quads: Q, lakes };
    } finally {
        for (const f of made) if (!f.destroyed) f.destroy();
    }
}

function meshObject(THREE, name, geo, material, box) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(geo.positions, 3));
    g.setAttribute('normal', new THREE.BufferAttribute(geo.normals, 3));
    g.setAttribute('eidoWater', new THREE.BufferAttribute(geo.depth, 1));
    g.setIndex(new THREE.BufferAttribute(geo.index, 1));
    g.boundingBox = new THREE.Box3(new THREE.Vector3(box[0], box[4], -box[3]), new THREE.Vector3(box[2], box[5], -box[1]));
    g.boundingSphere = g.boundingBox.getBoundingSphere(new THREE.Sphere());
    const mesh = new THREE.Mesh(g, material);
    mesh.name = name;
    mesh.receiveShadow = true;
    mesh.userData.noWalkable = true;
    return mesh;
}

/** The lake meshes of a Terrain (module doc): one per level that holds lake water, named <name>_L<level>.
 * opts: name ('terrain_lake'), minDepthM (0.5), material. */
export async function lakeObjects(THREE, R, t, opts = {}) {
    const { name = 'terrain_lake', minDepthM = 0.5, material = null } = opts;
    const plan = t.levels;
    const sea = t.info.sea_level ?? null;
    let mat = null;
    const out = [];
    for (let k = 0; k < plan.length; k++) {
        const f = t._fields[k];
        if (!f.has('water')) continue;
        const lv = plan[k];
        const st = await lakeCells(R, lv, f.f32('h'), f.f32('water'), plan[k + 1] ?? null, minDepthM, sea);
        if (!st) continue;
        let geo;
        try {
            geo = await lakeGeometry(R, lv, st, t.ring);
        } finally {
            st.labels.destroy();
        }
        if (!geo) continue;
        mat = mat ?? material ?? waterMaterial(THREE, name + '_water');
        const levels = geo.lakes.map((l) => l.level_m);
        const mesh = meshObject(THREE, `${name}_L${k}`, geo, mat, [lv.x0, lv.y0, lv.x1, lv.y1, Math.min(...levels), Math.max(...levels)]);
        mesh.userData.eidoWater = { kind: 'lakes', level: k, lakes: geo.lakes, vertices: geo.vertices, quads: geo.quads };
        out.push(mesh);
    }
    return out;
}

/** The sea grid's geometry (water.py sea_object): { positions, normals, depth, index, n } at seaLevel over the
 * outermost window, n x n vertices, the depth to the ground under each. */
export async function seaGeometry(R, rm, seaLevel, n = SEA_GRID) {
    const P = prims(R);
    const [xmin, ymin, xmax, ymax] = rm.bounds();
    // np.linspace(lo, hi, n) in float64, rounded once to float32 as the mesh's vertices are
    const lin = (lo, hi) => {
        const a = new Float32Array(n), step = (hi - lo) / (n - 1);
        for (let i = 0; i < n; i++) a[i] = i * step + lo;
        a[n - 1] = hi;
        return a;
    };
    const V = n * n, Q = (n - 1) * (n - 1);
    const made = [];
    const keep = (f) => { made.push(f); return f; };
    try {
        const xs = keep(P.list(n, 'f32', lin(xmin, xmax))), ys = keep(P.list(n, 'f32', lin(ymin, ymax)));
        const pos = keep(P.list(3 * V, 'f32')), nrm = keep(P.list(3 * V, 'f32')), pts = keep(P.list(2 * V, 'f32'));
        const tri = keep(P.list(6 * Q, 'u32'));
        R.run('water/sea_grid', { xs, ys }, { outP: pos, outN: nrm, outQ: pts, outT: tri }, { uN: n, uLevel: Number(seaLevel) }, cover(n));
        const ground = keep(rm.heightField(R, pts, V));
        const depth = keep(P.list(V, 'f32'));
        R.run('water/depth', { pos, ground }, { outD: depth }, { uCount: V }, lineGroups(V));
        const [positions, normals, dep, index] = await R.readParts([{ field: pos, count: 3 * V }, { field: nrm, count: 3 * V },
            { field: depth, count: V }, { field: tri, count: 6 * Q }]);
        return { positions, normals, depth: dep, index, n };
    } finally {
        for (const f of made) if (!f.destroyed) f.destroy();
    }
}

/** A sea grid at seaLevel over the outermost level (n x n vertices, the depth to the ground as eidoWater), or null
 * when seaLevel is null. opts: name ('terrain_sea'), material, n (SEA_GRID). */
export async function seaObject(THREE, R, t, seaLevel, opts = {}) {
    if (seaLevel === null || seaLevel === undefined) return null;
    const { name = 'terrain_sea', material = null, n = SEA_GRID } = opts;
    const geo = await seaGeometry(R, t.ring, seaLevel, n);
    const [xmin, ymin, xmax, ymax] = t.ring.bounds();
    const mesh = meshObject(THREE, name, geo, material ?? waterMaterial(THREE, name + '_water'),
        [xmin, ymin, xmax, ymax, Number(seaLevel), Number(seaLevel)]);
    mesh.userData.eidoWater = { kind: 'sea', level_m: Number(seaLevel), n };
    return mesh;
}

/** Dark glossy water whose colour runs from a green shallow tint to a deep blue-black over 0-12 m of depth (the
 * eidoWater attribute): water.py water_material as a NodeMaterial (roughness 0.06, index of refraction 1.333). */
export function waterMaterial(THREE, name = 'terrain_water') {
    const mat = new THREE.MeshPhysicalNodeMaterial({ roughness: 0.06, metalness: 0.0, ior: 1.333 });
    const depth = THREE.attribute('eidoWater', 'float');
    mat.colorNode = THREE.mix(THREE.vec3(0.055, 0.12, 0.10), THREE.vec3(0.006, 0.018, 0.028), THREE.smoothstep(0.0, 12.0, depth));
    mat.name = name;
    return mat;
}

export { lakeObjects as lake_objects, seaObject as sea_object, waterMaterial as water_material, lakeGeometry as lake_geometry };
