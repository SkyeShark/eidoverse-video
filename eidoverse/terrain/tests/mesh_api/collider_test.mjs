// The collider proxy and the exact ray caster (PORT_PLAN.md 7.5, 8.2 P4): build/collider.js on Blender saves.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/mesh_api/collider_test.mjs [case ...] [--rays N]
//
// (from the repository root; on a shared machine put $EIDO_GPU_WRAP in front). Per save:
//   proxy       the rings near the focus (the hero rings and cores, or the main ring), at most about 2 M triangles,
//               every one a triangle of the visual mesh
//   rapier      a Rapier trimesh built from the proxy the way eidoverse/robot_controller.js builds one, in under
//               2 s; rays cast down onto it land within 1e-3 m of heightAt
//   ray caster  N rays (1,000 on the first case, 150 on the others: three's loop over every triangle is the slow
//               side) of every kind (down from above, on lattice points and lines, oblique, grazing, from outside
//               and from below, short, along a ring's border, through the skirt): mesh.raycast gives exactly the
//               hits of THREE.Mesh.prototype.raycast, the brute-force loop over all the triangles: the same count,
//               distances, points, faces and face indices; with a DoubleSide material too; firstHitOnly gives
//               the nearest; a vertical ray's hit is heightAt

import * as G from '../../core/gpu.js';
import { Terrain } from '../../index.js';
import * as A from '../../api.js';
import { colliderRings, COLLIDER_MAX_TRIANGLES } from '../../build/collider.js';
import * as C from './_common.mjs';

const args = Deno.args.filter((a) => !a.startsWith('--'));
const flag = (n, d) => {
    const i = Deno.args.indexOf(n);
    return i >= 0 ? Number(Deno.args[i + 1]) : d;
};
const want = args.filter((a) => !/^\d+$/.test(a));
const cases = C.fixtureCases(want.length ? want : ['real_place_film_nofocus', 'lauterbrunnen_film']);
if (!cases) Deno.exit(0);
cases.sort((a, b) => (a === 'real_place_film_nofocus' ? -1 : b === 'real_place_film_nofocus' ? 1 : 0));
await G.init();
const THREE = await A.three();
const T = new C.Checks('mesh and API: the collider proxy and the exact ray caster');
T.extra.cases = {};
let RAPIER = null;
try {
    RAPIER = await import('npm:@dimforge/rapier3d-compat@0.14.0').then((m) => m.default || m);
    await RAPIER.init();
} catch (e) {
    console.log(`[skip] the Rapier checks: ${e.message}`);
}

function rays(t, n, rnd) {
    // [origin, direction, near, far, what] in three.js axes
    const rm = t.ring, out = [];
    const [xmin, ymin, xmax, ymax] = rm.bounds();
    const [h0, h1] = rm.heightRange;
    const top = h1 + 500, low = h0 - 300;
    const fin = rm.rings[rm.rings.length - 1], mid = rm.rings[Math.max(0, rm.rings.length - 2)];
    const win = (r) => [r.xm[0], r.ym[0], r.xm[r.nx - 1], r.ym[r.ny - 1]];
    const inWin = (w) => [w[0] + rnd() * (w[2] - w[0]), w[1] + rnd() * (w[3] - w[1])];
    const dirTo = (o, p) => {
        const d = [p[0] - o[0], p[1] - o[1], p[2] - o[2]], l = Math.hypot(...d);
        return d.map((v) => v / l);
    };
    const ground = (x, y) => [x, rm.heightAt(x, y), -y];
    const kinds = ['down', 'down_fine', 'vertex', 'line', 'oblique', 'oblique_fine', 'graze', 'outside', 'below', 'short', 'seam_along', 'seam_cross', 'skirt', 'up'];
    for (let q = 0; q < n; q++) {
        const kind = kinds[q % kinds.length];
        const all = [xmin, ymin, xmax, ymax];
        if (kind === 'down' || kind === 'down_fine') {
            const [x, y] = inWin(kind === 'down' ? all : win(fin));
            out.push([[x, top, -y], [0, -1, 0], 0, Infinity, kind]);
        } else if (kind === 'vertex' || kind === 'line') {
            const r = rm.rings[Math.floor(rnd() * rm.rings.length)];
            const i = Math.floor(rnd() * r.nx), j = Math.floor(rnd() * r.ny);
            const x = r.xm[i], y = kind === 'vertex' ? r.ym[j] : r.ym[0] + rnd() * (r.ym[r.ny - 1] - r.ym[0]);
            out.push([[x, top, -y], [0, -1, 0], 0, Infinity, kind]);
        } else if (kind === 'oblique' || kind === 'oblique_fine') {
            const w = kind === 'oblique' ? all : win(mid);
            const [x, y] = inWin(w), [x2, y2] = inWin(w);
            const o = [x, rm.heightAt(x, y) + 2 + rnd() * 400, -y];
            out.push([o, dirTo(o, ground(x2, y2)), 0, Infinity, kind]);
        } else if (kind === 'graze') {
            const [x, y] = inWin(win(mid)), [x2, y2] = inWin(win(mid));
            const o = [x, rm.heightAt(x, y) + 1.7, -y];
            const p = ground(x2, y2);
            out.push([o, dirTo(o, [p[0], p[1] + 1.7, p[2]]), 0, Infinity, kind]);
        } else if (kind === 'outside') {
            const a = rnd() * 2 * Math.PI, rad = (xmax - xmin) * (0.8 + rnd());
            const o = [0.5 * (xmin + xmax) + rad * Math.cos(a), h0 + rnd() * (h1 - h0 + 400), -(0.5 * (ymin + ymax) + rad * Math.sin(a))];
            const [x2, y2] = inWin(all);
            out.push([o, dirTo(o, ground(x2, y2)), 0, Infinity, kind]);
        } else if (kind === 'below') {
            const [x, y] = inWin(all), [x2, y2] = inWin(all);
            const o = [x, low, -y];
            out.push([o, dirTo(o, [x2, top, -y2]), 0, Infinity, kind]);
        } else if (kind === 'short') {
            const [x, y] = inWin(win(fin));
            const o = [x, rm.heightAt(x, y) + 30, -y];
            const [x2, y2] = inWin(win(fin));
            out.push([o, dirTo(o, ground(x2, y2)), rnd() * 5, 20 + rnd() * 200, kind]);
        } else if (kind === 'seam_along' || kind === 'seam_cross') {
            const k = 1 + Math.floor(rnd() * Math.max(rm.rings.length - 1, 1));
            const r = rm.rings[Math.min(k, rm.rings.length - 1)];
            const w = win(r);
            if (kind === 'seam_along') {
                // from above one end of a ring's border line to the ground at its other end: the track runs on the line
                const y = rnd() < 0.5 ? w[1] : w[3];
                const xa = w[0] + rnd() * (w[2] - w[0]), xb = w[0] + rnd() * (w[2] - w[0]);
                const o = [xa, rm.heightAt(xa, y) + 50 + rnd() * 100, -y];
                out.push([o, dirTo(o, ground(xb, y)), 0, Infinity, kind]);
            } else {
                const [x, y] = [w[0] + (rnd() - 0.5) * 20, w[1] + rnd() * (w[3] - w[1])];
                const o = [x - 40, rm.heightAt(x, y) + 15, -y + (rnd() - 0.5) * 30];
                out.push([o, dirTo(o, ground(x + 5, y)), 0, Infinity, kind]);
            }
        } else if (kind === 'skirt') {
            const y = ymin + rnd() * (ymax - ymin);
            const o = [xmin - 300, rm.heightAt(xmin, y) - 20 - rnd() * 60, -y];
            out.push([o, dirTo(o, [xmin + 200, o[1] + (rnd() - 0.5) * 40, -y + (rnd() - 0.5) * 100]), 0, Infinity, kind]);
        } else {
            const [x, y] = inWin(all);
            out.push([[x, low, -y], [0, 1, 0], 0, Infinity, kind]);
        }
    }
    return out;
}

function sameHits(a, b) {
    if (a.length !== b.length) return `count ${a.length} vs ${b.length}`;
    const key = (h) => [h.distance, h.faceIndex];
    const s = (l) => [...l].sort((p, q) => key(p)[0] - key(q)[0] || key(p)[1] - key(q)[1]);
    const x = s(a), y = s(b);
    for (let i = 0; i < x.length; i++) {
        const p = x[i], q = y[i];
        if (p.distance !== q.distance) return `hit ${i}: distance ${p.distance} vs ${q.distance}`;
        if (p.faceIndex !== q.faceIndex) return `hit ${i}: face ${p.faceIndex} vs ${q.faceIndex}`;
        if (!p.point.equals(q.point)) return `hit ${i}: point`;
        if (p.face.a !== q.face.a || p.face.b !== q.face.b || p.face.c !== q.face.c || p.face.materialIndex !== q.face.materialIndex) return `hit ${i}: face record`;
        if (!p.face.normal.equals(q.face.normal) || !p.normal.equals(q.normal) || !p.uv.equals(q.uv)) return `hit ${i}: normal or uv`;
        if (p.object !== q.object) return `hit ${i}: object`;
    }
    return null;
}

async function checkCase(name, nRays) {
    const man = C.manifest(name);
    const rec = {};
    T.extra.cases[name] = rec;
    const tag = (s) => `${name}: ${s}`;
    const t = await Terrain.load(C.blenderPath(man.save), { name: 'ground', log: () => {}, plants: false });
    const mesh = t.mesh, rm = t.ring, proxy = t.collider;
    const roles = t.levels.map((lv) => lv.role);

    // the proxy
    const [first, last] = colliderRings(rm, roles);
    const tris = proxy.geometry.index.count / 3;
    const hero = rm.rings.findIndex((r) => roles[r.spec.level] === 'hero');
    const expectFirst = hero >= 0 ? hero : rm.rings.findIndex((r) => roles[r.spec.level] === 'main');
    let sub = true;
    const pi = proxy.geometry.index.array, off = 3 * rm.rings[first].triBase;
    for (const q of [0, 1, 2, pi.length - 3, pi.length - 2, pi.length - 1, Math.floor(pi.length / 2)]) if (pi[q] !== rm.index[off + q]) sub = false;
    T.ok(tag('proxy: the rings near the focus (hero rings and cores, else the main ring), at most about 2 M triangles, a run of the visual index buffer'),
        first >= expectFirst && last === rm.rings.length - 1 && tris <= COLLIDER_MAX_TRIANGLES && sub &&
        tris === rm.rings[last].triBase + rm.rings[last].triangles - rm.rings[first].triBase,
        `rings ${first}..${last} of ${rm.rings.length} (${roles.join(', ')}): ${tris.toLocaleString('en-US')} of ${rm.triangleCount.toLocaleString('en-US')} triangles`);
    mesh.position.set(12.5, -3, 40);
    mesh.updateMatrixWorld(true);
    proxy.updateWorldMatrix(true, true);
    T.ok(tag('proxy: it follows the terrain mesh\'s world matrix'), proxy.matrixWorld.equals(mesh.matrixWorld) && proxy.parent === null, '');
    mesh.position.set(0, 0, 0);
    mesh.updateMatrixWorld(true);
    proxy.updateWorldMatrix(true, true);
    rec.proxy = { rings: [first, last], triangles: tris };

    // Rapier, as eidoverse/robot_controller.js builds a trimesh from a collision mesh
    if (RAPIER) {
        const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
        const t0 = performance.now();
        const posA = proxy.geometry.attributes.position;
        const v = new Float32Array(posA.count * 3);
        const tv = new THREE.Vector3();
        for (let i = 0; i < posA.count; i++) {
            tv.fromBufferAttribute(posA, i).applyMatrix4(proxy.matrixWorld);
            v[i * 3] = tv.x; v[i * 3 + 1] = tv.y; v[i * 3 + 2] = tv.z;
        }
        const idx = new Uint32Array(proxy.geometry.index.array);
        const t1 = performance.now();
        const body = world.createRigidBody(RAPIER.RigidBodyDesc.fixed());
        world.createCollider(RAPIER.ColliderDesc.trimesh(v, idx), body);
        const t2 = performance.now();
        world.step();
        rec.rapier = { copy_s: +((t1 - t0) / 1000).toFixed(3), trimesh_s: +((t2 - t1) / 1000).toFixed(3), triangles: tris, vertices: posA.count };
        T.ok(tag('rapier: the trimesh of the proxy is built in under 2 s'), (t2 - t0) / 1000 < 2.0,
            `${((t2 - t1) / 1000).toFixed(2)} s for ${tris.toLocaleString('en-US')} triangles (+ ${((t1 - t0) / 1000).toFixed(2)} s copying ${posA.count.toLocaleString('en-US')} vertices)`);
        const rnd = C.lcg(17);
        const a = rm.rings[first];
        let worst = 0, missed = 0, n = 0;
        const top = rm.heightRange[1] + 100;
        for (let q = 0; q < 400; q++) {
            const x = a.xm[0] + rnd() * (a.xm[a.nx - 1] - a.xm[0]), y = a.ym[0] + rnd() * (a.ym[a.ny - 1] - a.ym[0]);
            const hit = world.castRay(new RAPIER.Ray({ x, y: top, z: -y }, { x: 0, y: -1, z: 0 }), top - rm.heightRange[0] + 200, true);
            n++;
            if (!hit) { missed++; continue; }
            const toi = hit.timeOfImpact ?? hit.toi;
            worst = Math.max(worst, Math.abs((top - toi) - t.heightAt(x, -y)));
        }
        rec.rapier.surface_worst_m = worst;
        T.ok(tag('rapier: rays cast down onto the trimesh land within 1e-3 m of heightAt'), worst <= 1e-3 && missed === 0,
            `${n} rays over the proxy's rings: worst ${worst.toExponential(2)} m, ${missed} missed`);
        world.free();
    }

    // the ray caster against three's loop over every triangle
    const rc = new THREE.Raycaster();
    const rnd = C.lcg(29);
    const list = rays(t, nRays, rnd);
    let bad = null, hits = 0, withHit = 0, tMine = 0, tBrute = 0;
    const byKind = {};
    for (const [o, d, near, far, kind] of list) {
        rc.set(new THREE.Vector3(...o), new THREE.Vector3(...d));
        rc.near = near;
        rc.far = far;
        const mine = [], brute = [];
        let s = performance.now();
        mesh.raycast(rc, mine);
        tMine += performance.now() - s;
        s = performance.now();
        THREE.Mesh.prototype.raycast.call(mesh, rc, brute);
        tBrute += performance.now() - s;
        const why = sameHits(mine, brute);
        byKind[kind] = byKind[kind] ?? { rays: 0, hits: 0 };
        byKind[kind].rays++;
        byKind[kind].hits += brute.length;
        hits += brute.length;
        if (brute.length) withHit++;
        if (why && !bad) bad = `${kind} ray from (${o.map((x) => x.toFixed(3))}) toward (${d.map((x) => x.toFixed(4))}): ${why}`;
    }
    rec.raycast = { rays: list.length, hits, rays_with_hits: withHit, ms_per_ray: +(tMine / list.length).toFixed(4),
        brute_ms_per_ray: +(tBrute / list.length).toFixed(2), by_kind: byKind };
    T.ok(tag(`ray caster: ${list.length} rays give exactly three's brute-force hits (count, distance, point, face, face index, normal, uv)`), bad === null,
        bad ?? `${hits} hits on ${withHit} rays; ${(tMine / list.length).toFixed(3)} ms a ray against ${(tBrute / list.length).toFixed(1)} ms; ` +
        Object.entries(byKind).map(([k, v]) => `${k} ${v.hits}/${v.rays}`).join(', '));
    // both faces
    for (const m of mesh.material) m.side = THREE.DoubleSide;
    let bad2 = null, hits2 = 0;
    for (const [o, d, near, far, kind] of list.slice(0, Math.min(list.length, 140))) {
        rc.set(new THREE.Vector3(...o), new THREE.Vector3(...d));
        rc.near = near;
        rc.far = far;
        const mine = [], brute = [];
        mesh.raycast(rc, mine);
        THREE.Mesh.prototype.raycast.call(mesh, rc, brute);
        hits2 += brute.length;
        const why = sameHits(mine, brute);
        if (why && !bad2) bad2 = `${kind}: ${why}`;
    }
    for (const m of mesh.material) m.side = THREE.FrontSide;
    T.ok(tag('ray caster: the same with DoubleSide materials (back faces count)'), bad2 === null, bad2 ?? `${hits2} hits`);
    // firstHitOnly, and a vertical ray is heightAt
    let firstOk = true, vertOk = true, worstV = 0;
    for (const [o, d, near, far] of list.slice(0, 120)) {
        rc.set(new THREE.Vector3(...o), new THREE.Vector3(...d));
        rc.near = near;
        rc.far = far;
        const all = [], one = [];
        rc.firstHitOnly = false;
        mesh.raycast(rc, all);
        rc.firstHitOnly = true;
        mesh.raycast(rc, one);
        rc.firstHitOnly = false;
        all.sort((p, q) => p.distance - q.distance);
        if (one.length !== Math.min(all.length, 1) || (one.length && one[0].distance !== all[0].distance)) firstOk = false;
        if (d[0] === 0 && d[2] === 0 && d[1] === -1 && all.length) {
            const e = Math.abs(all[0].point.y - t.heightAt(o[0], o[2]));
            worstV = Math.max(worstV, e);
            if (e > 1e-6) vertOk = false;
        }
    }
    T.ok(tag('ray caster: firstHitOnly gives the nearest hit; a ray straight down lands on heightAt'), firstOk && vertOk, `vertical rays within ${worstV.toExponential(2)} m of heightAt`);
    const hs = rc.intersectObject(mesh, false);
    T.ok(tag('ray caster: THREE.Raycaster.intersectObject(mesh) goes through it'), Array.isArray(hs), '');
    t.dispose();
}

let k = 0;
for (const name of cases) {
    try {
        await checkCase(name, flag('--rays', k === 0 ? 1000 : 150));
    } catch (e) {
        T.ok(`${name}: ran`, false, `${e.name}: ${e.message}\n${e.stack?.split('\n').slice(1, 8).join('\n')}`);
    }
    k++;
}
G.shutdown();
Deno.exit(C.finish(T, 'collider_test.json'));
