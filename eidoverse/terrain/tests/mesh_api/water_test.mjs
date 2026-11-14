// The water surfaces against Blender's (PORT_PLAN.md 3.2, 8.2 P4): build/water.js on Blender Terrain.save files,
// compared with build/water.py's lake cells, lake geometry, sea grid and depths on the same saves
// (mesh_expected.py's dump_lakes, run by Blender's Python).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/mesh_api/water_test.mjs [case ...]
//
// (from the repository root; on a shared machine put $EIDO_GPU_WRAP in front). Per save with a `water` field or a
// sea level:
//   lakes       the same levels hold lakes; per level the same lakes (their cell counts; their levels to the bit for
//               a lake of an odd number of cells, within one float32 step otherwise), the same vertex and quad counts
//   vertices    x and z bit-equal to Blender's float32 x and -y; y the lake's level
//   quads       Blender's quads, index for index (written as two triangles each)
//   depth       eidoWater within 1e-3 m of Blender's eido_water (float32 ground sampler against float64)
//   sea         the grid's vertices bit-equal, its quads Blender's, its depth within 1e-3 m
//   meshes      lakeObjects / seaObject: names, the eidoWater attribute, a NodeMaterial, userData.noWalkable

import * as G from '../../core/gpu.js';
import { Terrain } from '../../index.js';
import * as A from '../../api.js';
import * as W from '../../build/water.js';
import * as C from './_common.mjs';

const args = Deno.args.filter((a) => !a.startsWith('--'));
const all = C.fixtureCases(args.length ? args : null) ?? [];
const cases = all.filter((n) => {
    const m = C.manifest(n);
    return m.kind === 'save' && ((m.lakes?.length ?? 0) > 0 || m.sea);
});
if (!cases.length) {
    console.log('SKIP: no save fixture with lakes or a sea (mesh_expected.py makes them from the Blender saves it names)');
    Deno.exit(0);
}
const R = await G.init();
const THREE = await A.three();
const T = new C.Checks('mesh and API: build/water.js against build/water.py');
T.extra.cases = {};

async function checkCase(name) {
    const man = C.manifest(name);
    const rec = { lakes: [], sea: null };
    T.extra.cases[name] = rec;
    const tag = (s) => `${name}: ${s}`;
    const t = await Terrain.load(C.blenderPath(man.save), { build: false, plants: false });
    const sea = t.info.sea_level ?? null;
    const byLevel = new Map((man.lakes ?? []).map((l) => [l.level, l]));
    let levelsOk = true, levelsWhy = '';
    const t0 = performance.now();
    for (let k = 0; k < t.levels.length; k++) {
        const f = t._fields[k];
        const want = byLevel.get(k) ?? null;
        let geo = null;
        if (f.has('water')) {
            const st = await W.lakeCells(R, t.levels[k], f.f32('h'), f.f32('water'), t.levels[k + 1] ?? null, 0.5, sea);
            if (st) {
                geo = await W.lakeGeometry(R, t.levels[k], st, t.ring);
                st.labels.destroy();
            }
        }
        if ((geo === null) !== (want === null)) {
            levelsOk = false;
            levelsWhy ||= `level ${k}: ${geo ? 'lakes here' : 'no lakes here'}, ${want ? 'lakes in Blender' : 'none in Blender'}`;
            continue;
        }
        if (!geo) continue;
        // the lakes
        let lakesOk = geo.lakes.length === want.lakes.length, why = `${geo.lakes.length} lakes (Blender ${want.lakes.length})`, exact = 0;
        for (let q = 0; lakesOk && q < geo.lakes.length; q++) {
            const a = geo.lakes[q], b = want.lakes[q];
            const dl = Math.abs(Math.fround(a.level_m) - Math.fround(b.level_m));
            if (dl === 0) exact++;
            if (a.cells !== b.cells || dl > C.ulp32(b.level_m)) { lakesOk = false; why = `lake ${q}: ${JSON.stringify(a)} vs ${JSON.stringify(b)}`; }
        }
        T.ok(tag(`level ${k}: the same lakes (cells; levels to the bit, or one float32 step for an even count), vertices and quads`),
            lakesOk && geo.vertices === want.vertices && geo.quads === want.quads,
            `${why}; ${exact} of ${geo.lakes.length} levels to the bit; ${geo.vertices} vertices (Blender ${want.vertices}), ${geo.quads} quads (Blender ${want.quads})`);
        if (geo.vertices !== want.vertices || geo.quads !== want.quads) continue;
        const bv = C.arr(name, man, `lake_verts_${k}`), bq = C.arr(name, man, `lake_quads_${k}`), bd = C.arr(name, man, `lake_depth_${k}`);
        let xz = true, yWorst = 0, yExact = 0, at = -1;
        for (let v = 0; v < geo.vertices; v++) {
            if (geo.positions[3 * v] !== bv[3 * v] || geo.positions[3 * v + 2] !== -bv[3 * v + 1]) { xz = false; at = at < 0 ? v : at; }
            const dy = Math.abs(geo.positions[3 * v + 1] - bv[3 * v + 2]);
            if (dy === 0) yExact++;
            yWorst = Math.max(yWorst, dy / C.ulp32(bv[3 * v + 2]));
        }
        T.ok(tag(`level ${k}: vertices' x and z bit-equal to Blender's x and -y, y the lake's level`), xz && yWorst <= 1,
            xz ? `${geo.vertices} vertices; y to the bit on ${yExact}, worst ${yWorst} float32 steps` : `vertex ${at}: (${geo.positions[3 * at]}, ${-geo.positions[3 * at + 2]}) vs (${bv[3 * at]}, ${bv[3 * at + 1]})`);
        let quadsOk = true, qat = -1;
        for (let q = 0; q < geo.quads && quadsOk; q++) {
            const i = geo.index, o = 6 * q;
            const mine = [i[o], i[o + 1], i[o + 2], i[o + 5]];
            if (i[o + 3] !== i[o] || i[o + 4] !== i[o + 2]) quadsOk = false;
            for (let c = 0; c < 4; c++) if (mine[c] !== bq[4 * q + c]) quadsOk = false;
            if (!quadsOk) qat = q;
        }
        T.ok(tag(`level ${k}: Blender's quads, index for index (two triangles a quad)`), quadsOk, quadsOk ? `${geo.quads} quads` : `quad ${qat}`);
        let dWorst = 0, dAt = -1;
        for (let v = 0; v < geo.vertices; v++) {
            const e = Math.abs(geo.depth[v] - bd[v]);
            if (e > dWorst) { dWorst = e; dAt = v; }
        }
        let nUp = true;
        for (let v = 0; v < geo.vertices && nUp; v++) if (geo.normals[3 * v] !== 0 || geo.normals[3 * v + 1] !== 1 || geo.normals[3 * v + 2] !== 0) nUp = false;
        T.ok(tag(`level ${k}: the depth under every vertex within 1e-3 m of Blender's; normals up`), dWorst <= 1e-3 && nUp,
            `worst ${dWorst.toExponential(2)} m` + (dWorst > 1e-3 ? ` at vertex ${dAt}: ${geo.depth[dAt]} vs ${bd[dAt]}` : ''));
        rec.lakes.push({ level: k, lakes: geo.lakes.length, vertices: geo.vertices, quads: geo.quads, depth_worst_m: dWorst, level_y_exact: yExact });
    }
    rec.lakes_s = +((performance.now() - t0) / 1000).toFixed(3);
    T.ok(tag('the same levels hold lakes as in Blender'), levelsOk, levelsWhy || `levels ${[...byLevel.keys()].join(', ') || '(none)'}; ${rec.lakes_s} s`);

    if (man.sea) {
        const t1 = performance.now();
        const g = await W.seaGeometry(R, t.ring, man.sea.level_m, man.sea.n);
        rec.sea_s = +((performance.now() - t1) / 1000).toFixed(3);
        const bv = C.arr(name, man, 'sea_verts'), bd = C.arr(name, man, 'sea_depth');
        const n = man.sea.n;
        let ok = g.positions.length === bv.length, dWorst = 0;
        for (let v = 0; ok && v < n * n; v++) {
            if (g.positions[3 * v] !== bv[3 * v] || g.positions[3 * v + 2] !== -bv[3 * v + 1] || g.positions[3 * v + 1] !== bv[3 * v + 2]) ok = false;
            dWorst = Math.max(dWorst, Math.abs(g.depth[v] - bd[v]));
        }
        let quads = g.index.length === 6 * (n - 1) * (n - 1);
        for (let j = 0; quads && j < n - 1; j++) {
            for (let i = 0; quads && i < n - 1; i++) {
                const o = 6 * (j * (n - 1) + i), a = j * n + i;
                const want = [a, a + 1, a + n + 1, a, a + n + 1, a + n];
                for (let c = 0; c < 6; c++) if (g.index[o + c] !== want[c]) quads = false;
            }
        }
        T.ok(tag('sea: the grid\'s vertices bit-equal to Blender\'s, its quads Blender\'s, the depth within 1e-3 m'), ok && quads && dWorst <= 1e-3,
            `${n} x ${n} vertices at ${man.sea.level_m} m; depth worst ${dWorst.toExponential(2)} m; ${rec.sea_s} s`);
        rec.sea = { n, depth_worst_m: dWorst };
    }

    // the meshes, as makeTerrain adds them
    const lakes = await W.lakeObjects(THREE, R, t, { name: 'ground_lake' });
    const seaMesh = await W.seaObject(THREE, R, t, sea, { name: 'ground_sea' });
    const wantNames = [...byLevel.keys()].sort((a, b) => a - b).map((k) => `ground_lake_L${k}`);
    const meshes = [...lakes, ...(seaMesh ? [seaMesh] : [])];
    const good = meshes.every((m) => m.isMesh && m.material.isNodeMaterial === true && m.material.colorNode && m.userData.noWalkable === true &&
        m.geometry.getAttribute('eidoWater')?.count === m.geometry.getAttribute('position').count && m.geometry.index.count % 3 === 0 &&
        m.geometry.boundingSphere !== null && m.parent === null);
    T.ok(tag('lakeObjects and seaObject: one mesh per level with lakes, the sea when there is a sea level; NodeMaterial, eidoWater, noWalkable'),
        C.sameJson(lakes.map((m) => m.name), wantNames) && (seaMesh !== null) === (sea !== null) && good &&
        (lakes.length < 2 || lakes[0].material === lakes[1].material),
        `${lakes.map((m) => m.name).join(', ') || 'no lakes'}${seaMesh ? ', ' + seaMesh.name : ''}`);
    for (const m of meshes) m.geometry.dispose();
    t.dispose();
}

for (const name of cases) {
    try {
        await checkCase(name);
    } catch (e) {
        T.ok(`${name}: ran`, false, `${e.name}: ${e.message}\n${e.stack?.split('\n').slice(1, 8).join('\n')}`);
    }
}
G.shutdown();
Deno.exit(C.finish(T, 'water_test.json'));
