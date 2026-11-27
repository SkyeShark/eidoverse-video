// eidoverse/sets/town/things.js — what a lived-in town leaves about, from CC0 models: Poly Haven's scanned and authored
// models, fetched by ID into the shared library on first use (fetchModelFile; each keeps its .license.json beside it):
// the white monobloc chair on the roofs and in the yards, the gas cylinder by the kitchen door, plastic and steel
// jerrycans, steel drums, an old tyre on a roof, a car under its cover in a yard, a cardboard box, a bin; and, in a
// town built with damage, concrete road barriers where the road was closed and burnt tyres in the street. Each is set
// down where such a thing is put, by a ray cast on what the town built: by the dishes on the roofs people use, in the
// yards, by the shop fronts and the kerbs. Each model's parts are one geometry per material, placed many times; its
// own Poly Haven material is kept, with the town's dust laid over what faces up and, near a strike, more of it. A port
// of eidoblend.sets.town.things (its stream R(13), draw for draw).
import { M4 } from './mb.js';
import { caster } from './masks.js';
import { DUST } from './look.js';

// key: [Poly Haven ID, resolution]
export const LIB = {
    chair: ['plastic_monobloc_chair_01', '1k'], lpg: ['small_lpg_tank', '1k'], jerry_p: ['plastic_jerrycan', '1k'],
    jerry_m: ['metal_jerrycan_green', '1k'], drum: ['Barrel_02', '1k'], barrel: ['barrel_03', '1k'],
    tyre: ['old_tyre', '1k'], barrier: ['concrete_road_barrier', '1k'], covered_car: ['covered_car', '1k'],
    box: ['cardboard_box_01', '1k'], bin: ['metal_trash_can', '2k'],
};
// each kind kept at a share of its placings (the dense scans would otherwise be most of the town's triangles)
const KEEP = { chair: 0.40, lpg: 0.19, box: 0.10, jerry_p: 0.39, jerry_m: 0.44, tyre: 0.8, bin: 0.4, barrier: 0.5 };

// the town's dust over a model's own colour: on what faces up, broken by noise; thicker near a strike
function dustOver(THREE, src) {
    const { attribute, normalize, smoothstep, mx_noise_float, float, mix, clamp, texture, vec3, uv } = THREE;
    const m = new THREE.MeshStandardNodeMaterial();
    for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap']) if (src[k]) m[k] = src[k];
    m.color.copy(src.color || new THREE.Color(1, 1, 1));
    m.roughness = src.roughness ?? 1.0;
    m.metalness = src.metalness ?? 0.0;
    if (src.normalScale) m.normalScale.copy(src.normalScale);
    m.side = src.side ?? THREE.FrontSide;
    m.transparent = !!src.transparent; m.alphaTest = src.alphaTest || 0;
    const nz = normalize(attribute('normal', 'vec3')).z;
    const upF = smoothstep(0.45, 0.95, nz);
    const P = attribute('position', 'vec3');
    let n = null, amp = 1.0, mx = 0.0, fs = 1.0;                      // Blender's noise: scale 6, detail 3, normalized
    for (let i = 0; i <= 3; i++) { const v = mx_noise_float(P.mul(6.0 * fs)).mul(amp); n = n ? n.add(v) : v; mx += amp; amp *= 0.5; fs *= 2; }
    n = n.div(mx).mul(0.5).add(0.5);
    const near = attribute('inst', 'vec4').y;
    const f = clamp(upF.mul(near.mul(0.4).add(0.45)).add(n.mul(0.5).sub(0.17)), 0.0, 1.0);
    const base = (src.map ? texture(src.map, uv()).rgb : vec3(1, 1, 1)).mul(vec3(m.color.r, m.color.g, m.color.b));
    m.colorNode = THREE.vec4(mix(base, vec3(...DUST), f), 1.0);    // (a vec4: the weather's wetness wraps read .w)
    m.name = 'town.cc0.' + (src.name || 'mat');
    return m;
}

// one model's parts as one geometry per material, in the town's +Z-up metres, its feet at the origin -> { geo, mats,
// size: [dx, dy, dz] }; null when the model is not in the library and cannot be fetched
async function load(THREE, key, log) {
    let path;
    try { path = await globalThis.fetchModelFile(LIB[key][0], { res: LIB[key][1] }); }
    catch (e) { log(`[town] CC0 ${key}: ${e.message}`); return null; }
    const loader = new globalThis.GLTFLoader();
    const bytes = Deno.readFileSync(path);
    const gltf = await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), path.replace(/[^\\/]*$/, ''));
    gltf.scene.updateMatrixWorld(true);
    const byMat = new Map();
    gltf.scene.traverse((o) => {
        if (!o.isMesh) return;
        const g = o.geometry.clone().applyMatrix4(o.matrixWorld);
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        if (!byMat.has(mats[0])) byMat.set(mats[0], []);
        byMat.get(mats[0]).push(g);
    });
    // glTF's +Y up into the town's +Z up: (x, y, z) -> (x, -z, y)
    const Z = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1);
    const parts = [];
    const box = new THREE.Box3();
    for (const [mat, gs] of byMat) {
        const merged = gs.length > 1 ? (await import('npm:three@0.184.0/addons/utils/BufferGeometryUtils.js')).mergeGeometries(gs.map((g) => {
            const keep = new THREE.BufferGeometry();
            for (const a of ['position', 'normal', 'uv']) if (g.attributes[a]) keep.setAttribute(a, g.attributes[a]);
            if (g.index) keep.setIndex(g.index);
            return keep;
        })) : gs[0];
        merged.applyMatrix4(Z);
        merged.computeBoundingBox();
        box.union(merged.boundingBox);
        parts.push([merged, mat]);
    }
    const shift = new THREE.Matrix4().makeTranslation(-(box.min.x + box.max.x) / 2, -(box.min.y + box.max.y) / 2, -box.min.z);
    for (const [g] of parts) g.applyMatrix4(shift);
    const size = [box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z];
    const faces = parts.reduce((s, [g]) => s + (g.index ? g.index.count : g.attributes.position.count) / 3, 0);
    log(`[town] CC0 ${key}: ${faces} faces, ${size.map((v) => v.toFixed(2)).join(' x ')} m, ${parts.length} materials`);
    return { parts: parts.map(([g, m]) => [g, dustOver(THREE, m)]), size };
}

// a ray caster over the whole built town (its designs' BVHs under every placing), straight down: (x, y) -> { z, n,
// name } at the first surface under z0, in the town's metres
export function townCaster(THREE, plan) {
    const C = new Map();
    for (const [name, b] of plan.designs) C.set(name, caster(THREE, b));
    const CELL = 20.0;
    const grid = new Map();
    const always = [];
    const items = plan.placements.map((p) => {
        const M = placingMatrix(p);
        const bb = plan.designs.get(p.mesh).bbox || bboxOf(plan.designs.get(p.mesh));
        plan.designs.get(p.mesh).bbox = bb;
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        for (const cx of [bb[0][0], bb[1][0]]) for (const cy of [bb[0][1], bb[1][1]]) for (const cz of [bb[0][2], bb[1][2]]) {
            const q = M4.apply(M, [cx, cy, cz]);
            x0 = Math.min(x0, q[0]); y0 = Math.min(y0, q[1]); x1 = Math.max(x1, q[0]); y1 = Math.max(y1, q[1]);
        }
        return { p, M, Mi: invert(M), aabb: [x0, y0, x1, y1] };
    });
    items.forEach((it, i) => {
        const [x0, y0, x1, y1] = it.aabb;
        if ((x1 - x0) * (y1 - y0) > 4e4) { always.push(i); return; }
        for (let gx = Math.floor(x0 / CELL); gx <= Math.floor(x1 / CELL); gx++) for (let gy = Math.floor(y0 / CELL); gy <= Math.floor(y1 / CELL); gy++) {
            const k = `${gx},${gy}`;
            if (!grid.has(k)) grid.set(k, []);
            grid.get(k).push(i);
        }
    });
    return (x, y, z0 = 40.0) => {
        const cand = [...(grid.get(`${Math.floor(x / CELL)},${Math.floor(y / CELL)}`) || []), ...always];
        let best = null;
        for (const i of cand) {
            const it = items[i];
            const [x0, y0, x1, y1] = it.aabb;
            if (x < x0 || x > x1 || y < y0 || y > y1) continue;
            const o = M4.apply(it.Mi, [x, y, z0]);
            const d = M4.rot(it.Mi, [0, 0, -1]);
            const L = Math.hypot(...d);
            const hit = C.get(it.p.mesh).cast(o, d.map((v) => v / L), (z0 + 5.0) / L * L);
            if (!hit) continue;
            const w = M4.apply(it.M, hit.point);
            if (w[2] > z0 || (best && w[2] <= best.z)) continue;
            const nw = hit.normal ? M4.rot(it.M, hit.normal) : [0, 0, 1];
            const nl = Math.hypot(...nw);
            best = { z: w[2], n: nw.map((v) => v / nl), name: it.p.name };
        }
        return best;
    };
}

function bboxOf(b) {
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const v of b.v) for (let i = 0; i < 3; i++) { lo[i] = Math.min(lo[i], v[i]); hi[i] = Math.max(hi[i], v[i]); }
    return [lo, hi];
}

// a placing's matrix: turned about x, then y, then z (Blender's XYZ Euler), then moved
export function placingMatrix(p) {
    return M4.chain(M4.T(p.loc), M4.R(p.rot[2], 'Z'), M4.R(p.rot[1], 'Y'), M4.R(p.rot[0], 'X'));
}

function invert(m) {
    const R = [m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]];   // rotation only (no scale in a placing)
    const t = [m[3], m[7], m[11]];
    const Rt = [R[0], R[3], R[6], R[1], R[4], R[7], R[2], R[5], R[8]];
    const ti = [-(Rt[0] * t[0] + Rt[1] * t[1] + Rt[2] * t[2]), -(Rt[3] * t[0] + Rt[4] * t[1] + Rt[5] * t[2]), -(Rt[6] * t[0] + Rt[7] * t[1] + Rt[8] * t[2])];
    return [Rt[0], Rt[1], Rt[2], ti[0], Rt[3], Rt[4], Rt[5], ti[1], Rt[6], Rt[7], Rt[8], ti[2], 0, 0, 0, 1];
}

// the things, where such things are put -> { models: { key: { parts, size } }, placings: [{ key, loc, rot, dust }],
// counts }
export async function place(THREE, plan, { log = console.log } = {}) {
    const rng = plan.R(13);
    const strikes = plan.strikes;
    const lib = {};
    for (const k of Object.keys(LIB)) {
        if (!strikes.length && k === 'barrier') continue;
        const m = await load(THREE, k, log);
        if (m) lib[k] = m;
    }
    const cast = townCaster(THREE, plan);
    const struck = plan.struck;
    const counts = {};
    const placings = [];
    const put = (key, x, y, z, rot, lie = false, tilt = 0.0) => {
        const me = lib[key];
        if (!me || rng.random() > (KEEP[key] ?? 1.0)) return null;
        counts[key] = (counts[key] || 0) + 1;
        // laid on its side: turned about x, then lifted by half its depth so it rests on the surface, not in it
        const o = { key, loc: [x, y, z + (lie ? me.size[1] / 2.0 : 0.0)], rot: [lie ? Math.PI / 2 : tilt, 0.0, rot], dust: Math.max(0.0, Math.min(1.0, 1.15 - struck(x, y) / 1.2)) };
        placings.push(o);
        return o;
    };
    const flatAt = (x, y, want_z = null, tol = 0.2, names = ['bld.', 'town_streets']) => {
        const h = cast(x, y);
        if (!h) return null;
        if (h.n[2] < 0.92 || !names.some((s) => h.name.startsWith(s))) return null;
        if (want_z !== null && Math.abs(h.z - want_z) > tol) return null;
        return h.z;
    };
    const group = (cx, cy, z, kinds, spread, want_z = null, names = ['bld.', 'town_streets']) => {
        for (const kind of kinds) {
            for (let i = 0; i < 6; i++) {
                const x = cx + rng.uniform(-spread, spread), y = cy + rng.uniform(-spread, spread);
                const zz = flatAt(x, y, want_z !== null ? want_z : z, 0.12, names);
                if (zz === null) continue;
                if (kind === 'tyre_flat') put('tyre', x, y, zz, rng.uniform(0, 6.28), true);
                else if (kind === 'tyre_lean') put('tyre', x, y, zz, rng.uniform(0, 6.28), false);
                else put(kind, x, y, zz, rng.uniform(0, 6.28));
                break;
            }
        }
    };
    // ROOFS: by the dishes (they stand on the roofs people use)
    for (const d of plan.placements.filter((o) => o.name.startsWith('dish.'))) {
        if (rng.random() > 0.42) continue;
        const [x0, y0, z0] = d.loc;
        if (struck(x0, y0) < 0.7 && rng.random() < 0.7) continue;
        const pick = rng.random();
        let kinds;
        if (pick < 0.40) kinds = ['chair', 'chair', ...(rng.random() < 0.3 ? ['chair'] : [])];
        else if (pick < 0.58) kinds = ['lpg', ...(rng.random() < 0.5 ? ['jerry_p'] : [])];
        else if (pick < 0.74) kinds = ['tyre_flat', ...(rng.random() < 0.4 ? ['tyre_flat'] : [])];
        else if (pick < 0.88) kinds = rng.random() < 0.5 ? ['drum'] : ['barrel'];
        else kinds = ['box', 'jerry_p'];
        const a = rng.uniform(0, 6.28), r = rng.uniform(1.6, 3.2);
        group(x0 + r * Math.cos(a), y0 + r * Math.sin(a), z0, kinds, 0.9, z0, ['bld.']);
    }
    // YARDS and PAVEMENTS: the street mesh's own faces of each kind
    const st = plan.designs.get('town_streets');
    if (st) {
        const { fn, area } = st.normals();
        const yard = [], walk = [];
        st.f.forEach((f, i) => {
            if (st.m[i] === 'yard' && area[i] > 6.0) yard.push(i);
            if (st.m[i] === 'walk' && area[i] > 3.0 && fn[i][2] > 0.9) walk.push(i);
        });
        rng.shuffle(yard);
        rng.shuffle(walk);
        const ext = (i) => {
            const P = st.f[i].map((k) => st.v[k]);
            return [Math.min(...P.map((p) => p[0])), Math.max(...P.map((p) => p[0])), Math.min(...P.map((p) => p[1])), Math.max(...P.map((p) => p[1])), Math.max(...P.map((p) => p[2]))];
        };
        for (const i of yard.slice(0, Math.trunc(yard.length * 0.55))) {
            const [xa, xb, ya, yb] = ext(i);
            const x0 = xa + 0.6, x1 = xb - 0.6, y0 = ya + 0.6, y1 = yb - 0.6;
            if (x1 <= x0 || y1 <= y0) continue;
            const cx = rng.uniform(x0, x1), cy = rng.uniform(y0, y1);
            const pick = rng.random();
            if (pick < 0.07 && (x1 - x0) > 5.0 && (y1 - y0) > 2.6 && struck(cx, cy) > 1.0) {
                const xc = (x0 + x1) / 2, yc = (y0 + y1) / 2;
                let ok = true;
                for (const dx of [-2.0, 0.0, 2.0]) { for (const dy of [-0.7, 0.7]) { if (flatAt(xc + dx, yc + dy, 0.012, 0.08, ['town_streets']) === null) { ok = false; break; } } if (!ok) break; }
                if (ok) { const rz = Math.PI / 2 + rng.choice([0.0, Math.PI]) + rng.uniform(-0.06, 0.06); put('covered_car', xc, yc, 0.012, rz); }
            } else if (pick < 0.42) group(cx, cy, 0.012, ['chair', 'chair', ...(rng.random() < 0.25 ? ['chair', 'chair'] : [])], 0.9, null, ['town_streets']);
            else if (pick < 0.58) group(cx, cy, 0.012, rng.random() < 0.3 ? ['lpg', 'lpg'] : ['lpg'], 0.5, null, ['town_streets']);
            else if (pick < 0.74) group(cx, cy, 0.012, ['drum', 'barrel', 'jerry_m'], 0.8, null, ['town_streets']);
            else if (pick < 0.86) group(cx, cy, 0.012, ['tyre_lean', 'tyre_flat'], 0.8, null, ['town_streets']);
            else group(cx, cy, 0.012, ['box', 'box', 'jerry_p'], 0.7, null, ['town_streets']);
        }
        for (const i of walk.slice(0, Math.trunc(walk.length * 0.5))) {   // by the shop fronts and the kerbs
            const [xa, xb, ya, yb, z] = ext(i);
            const x0 = xa + 0.4, x1 = xb - 0.4, y0 = ya + 0.35, y1 = yb - 0.35;
            if (x1 <= x0 || y1 <= y0) continue;
            const n = 1 + Math.trunc((x1 - x0) * (y1 - y0) / 60.0);
            for (let q = 0; q < n; q++) {
                const cx = rng.uniform(x0, x1), cy = rng.uniform(y0, y1);
                const pick = rng.random();
                if (pick < 0.22) group(cx, cy, z, Array(rng.randrange(2, 6)).fill('lpg'), 0.5, null, ['town_streets']);
                else if (pick < 0.40) group(cx, cy, z, ['jerry_p', 'jerry_p', 'jerry_m', 'drum'].slice(0, rng.randrange(2, 5)), 0.6, null, ['town_streets']);
                else if (pick < 0.62) group(cx, cy, z, ['chair', 'chair'], 0.6, null, ['town_streets']);
                else if (pick < 0.80) group(cx, cy, z, ['box', 'box', 'box'].slice(0, rng.randrange(1, 4)), 0.5, null, ['town_streets']);
                else group(cx, cy, z, ['bin'], 0.3, null, ['town_streets']);
            }
        }
    }
    // WHERE THE ROAD WAS CLOSED: barriers across the street near each strike, staggered; burnt tyres in the road
    for (const [sx, sy, sr] of strikes) {
        const [yc, wd] = plan.ystreets.reduce((m, s) => (Math.abs(s[0] - sy) < Math.abs(m[0] - sy) ? s : m));
        const bx = sx + rng.choice([-1, 1]) * sr * rng.uniform(0.9, 1.3);
        const n_b = Math.trunc(wd / 1.9);
        for (let k = 0; k < n_b; k++) {
            if (rng.random() < 0.2) continue;
            const y = yc - wd / 2 + 1.0 + k * (wd - 2.0) / Math.max(1, n_b - 1);
            const z = flatAt(bx, y, null, 0.2, ['town_ground', 'town_streets']);
            if (z !== null) { const px = bx + rng.uniform(-0.15, 0.15); put('barrier', px, y, z, Math.PI / 2 + rng.uniform(-0.12, 0.12)); }
        }
        const nt = rng.randrange(2, 6);
        for (let k = 0; k < nt; k++) {
            const x = sx + rng.uniform(-0.6, 0.6) * sr, y = yc + rng.uniform(-0.35, 0.35) * wd;
            const z = flatAt(x, y, null, 0.3, ['town_ground', 'town_streets']);
            if (z !== null) { const o = put('tyre', x, y, z, rng.uniform(0, 6.28), true); if (o) o.dust = 1.0; }
        }
    }
    const total = Object.entries(counts).reduce((s, [k, n]) => s + n * lib[k].parts.reduce((q, [g]) => q + (g.index ? g.index.count : g.attributes.position.count) / 3, 0), 0);
    log(`[town] CC0 placed ${JSON.stringify(counts)}: ${total} faces`);
    return { models: lib, placings, counts };
}
