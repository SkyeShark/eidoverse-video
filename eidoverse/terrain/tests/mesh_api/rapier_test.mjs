// The collider proxy in Rapier (PORT_PLAN.md 7.5, 8.2 P4): the trimesh a controller builds from t.collider.
//
//     deno run --config deno.json --frozen --allow-all eidoverse/terrain/tests/mesh_api/rapier_test.mjs [case ...] [--scaling]
//
// (from the repository root). No GPU: it reads what collider_test.mjs wrote of each proxy
// (out/mesh_api/collider/<case>/: the proxy's vertices and triangles as a controller reads them from its geometry,
// its world matrix, 400 points over its rings with heightAt there), so it runs as a plain process, which is where a
// CPU build can be timed (a GPU queue may hold its jobs at low priority). Per case:
//   build      the trimesh made the way eidoverse/robot_controller.js makes one from a collision mesh (every vertex
//              through the world matrix into a Float32Array, a copy of the index, ColliderDesc.trimesh): the whole of
//              it under 2 s; the best of three builds is the figure (a build is single-threaded and the machine is
//              shared), every build's time is in the result
//   surface    rays cast straight down onto the trimesh land within 1e-3 m of heightAt at the 400 points
//   --scaling  the same build for the proxy without its coarsest ring, without its two coarsest, ...: what the
//              triangle limit (build/collider.js COLLIDER_MAX_TRIANGLES) is set from

import * as THREE from 'npm:three@0.184.0';
import * as C from './_common.mjs';

const args = Deno.args.filter((a) => !a.startsWith('--'));
const scaling = Deno.args.includes('--scaling');
const base = new URL('collider/', C.OUT);
const cases = [];
try {
    for (const e of Deno.readDirSync(base)) {
        if (e.isDirectory && (!args.length || args.includes(e.name))) {
            try {
                Deno.statSync(new URL(`${e.name}/meta.json`, base));
                cases.push(e.name);
            } catch (_e) { /* not a dump */ }
        }
    }
} catch (_e) { /* no folder */ }
cases.sort();
if (!cases.length) {
    console.log(`SKIP: no collider proxies in ${C.urlPath(base)}: collider_test.mjs writes them (a GPU job)`);
    Deno.exit(0);
}
const RAPIER = await import('npm:@dimforge/rapier3d-compat@0.14.0').then((m) => m.default || m);
await RAPIER.init();
const T = new C.Checks('mesh and API: the collider proxy as a Rapier trimesh');
T.extra.cases = {};

const read = (name, file, Arr) => {
    const b = Deno.readFileSync(new URL(`${name}/${file}`, base));
    return new Arr(b.buffer, b.byteOffset, b.byteLength / Arr.BYTES_PER_ELEMENT);
};

// eidoverse/robot_controller.js's trimesh path for one mesh: { copy_s, trimesh_s, world }
function build(positions, index, matrix) {
    const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
    const t0 = performance.now();
    const posA = new THREE.BufferAttribute(positions, 3);
    const v = new Float32Array(posA.count * 3);
    const tv = new THREE.Vector3();
    for (let i = 0; i < posA.count; i++) {
        tv.fromBufferAttribute(posA, i).applyMatrix4(matrix);
        v[i * 3] = tv.x; v[i * 3 + 1] = tv.y; v[i * 3 + 2] = tv.z;
    }
    const idx = new Uint32Array(index);
    const t1 = performance.now();
    const body = world.createRigidBody(RAPIER.RigidBodyDesc.fixed());
    world.createCollider(RAPIER.ColliderDesc.trimesh(v, idx), body);
    const t2 = performance.now();
    return { copy_s: (t1 - t0) / 1000, trimesh_s: (t2 - t1) / 1000, world };
}

for (const name of cases) {
    const meta = JSON.parse(Deno.readTextFileSync(new URL(`${name}/meta.json`, base)));
    const positions = read(name, 'positions.f32', Float32Array), index = read(name, 'index.u32', Uint32Array);
    const samples = read(name, 'samples.f64', Float64Array);
    const matrix = new THREE.Matrix4().fromArray(meta.matrix_world);
    const tag = (s) => `${name}: ${s}`;
    const rec = { rings: meta.rings, triangles: meta.triangles, vertices: meta.vertices, builds: [] };
    T.extra.cases[name] = rec;
    let world = null, best = Infinity;
    for (let k = 0; k < 3; k++) {
        const b = build(positions, index, matrix);
        rec.builds.push({ copy_s: +b.copy_s.toFixed(3), trimesh_s: +b.trimesh_s.toFixed(3) });
        best = Math.min(best, b.copy_s + b.trimesh_s);
        world?.free();
        world = b.world;
    }
    rec.best_s = +best.toFixed(3);
    T.ok(tag('the trimesh of the proxy is built as the robot controller builds it in under 2 s'), best < 2.0,
        `${meta.triangles.toLocaleString('en-US')} triangles on ${meta.vertices.toLocaleString('en-US')} vertices (rings ${meta.rings[0]}..${meta.rings[1]}; ` +
        `the visual mesh has ${meta.mesh_triangles.toLocaleString('en-US')} and ${meta.mesh_vertices.toLocaleString('en-US')}): ` +
        rec.builds.map((b) => `${(b.copy_s + b.trimesh_s).toFixed(2)} s (vertices ${b.copy_s.toFixed(2)}, trimesh ${b.trimesh_s.toFixed(2)})`).join(', '));
    world.step();
    const top = meta.height_range[1] + 100;
    let worst = 0, missed = 0;
    for (let q = 0; q < samples.length / 3; q++) {
        const x = samples[3 * q], z = samples[3 * q + 1], h = samples[3 * q + 2];
        const hit = world.castRay(new RAPIER.Ray({ x, y: top, z }, { x: 0, y: -1, z: 0 }), top - meta.height_range[0] + 200, true);
        if (!hit) { missed++; continue; }
        worst = Math.max(worst, Math.abs((top - (hit.timeOfImpact ?? hit.toi)) - h));
    }
    rec.surface_worst_m = worst;
    T.ok(tag('rays cast down onto the trimesh land within 1e-3 m of heightAt'), worst <= 1e-3 && missed === 0,
        `${samples.length / 3} rays over the proxy's rings: worst ${worst.toExponential(2)} m, ${missed} missed`);
    world.free();
    if (scaling) {
        // the proxy without its coarsest rings: the same triangles from a later ring on, their vertices from that
        // ring's parent on (JS per index: a test)
        rec.scaling = [];
        let skip = 0;
        for (const r of meta.run) {
            const idx = new Uint32Array(index.length - 3 * skip);
            for (let q = 0; q < idx.length; q++) idx[q] = index[3 * skip + q] - r.first_vertex;
            const b = build(positions.subarray(3 * r.first_vertex), idx, matrix);
            b.world.free();
            rec.scaling.push({ from_ring: r.ring, triangles: idx.length / 3, vertices: positions.length / 3 - r.first_vertex,
                copy_s: +b.copy_s.toFixed(3), trimesh_s: +b.trimesh_s.toFixed(3) });
            console.log(`  ${name} from ring ${r.ring}: ${(idx.length / 3).toLocaleString('en-US')} triangles, ` +
                `${(positions.length / 3 - r.first_vertex).toLocaleString('en-US')} vertices: vertices ${b.copy_s.toFixed(2)} s + trimesh ${b.trimesh_s.toFixed(2)} s`);
            skip += r.triangles;
        }
    }
}
Deno.exit(C.finish(T, 'rapier_test.json'));
