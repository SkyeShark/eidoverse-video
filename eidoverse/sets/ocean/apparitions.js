// ocean/apparitions.js — "not the robot from the movies, not a digital human — something new".
// Two figures rise out of the ocean of faces in the moon path and dissolve back into it:
//   · the movie ROBOT (robot.glb): a dark silhouette with a moonlit rim; it breaks up from the top down,
//     every fragment's edge burning the faces' gold, and sinks as it goes;
//   · the HUMAN OF LIGHT (human.glb): a figure of glowing points sampled from its surface plus a faint
//     fresnel shell; it comes apart into rising sparks.
// Both are GLBs built in Blender (the pack's figures/ in eidoverse/assets/sets/ocean/). If they are missing,
// this module adds nothing.
//
// buildApparitions(THREE, { dir, base }) -> { group, update(u) }
//   dir: design-frame directory with robot.glb / human.glb; base: THREE.Vector3 where they rise (design frame)

import { rng, OCEAN_ASSETS } from './util.js';

async function loadGLB(path) {
    try {
        const bytes = Deno.readFileSync(path);
        const loader = new globalThis.GLTFLoader();
        const gltf = await new Promise((res, rej) => loader.parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '', res, rej));
        return gltf.scene;
    } catch (e) { return null; }
}

// area-weighted surface samples (world space of the root after its transforms)
function sampleSurface(THREE, root, n, seed = 5) {
    const R = rng(seed);
    const tris = [];
    let total = 0;
    root.updateMatrixWorld(true);
    root.traverse((o) => {
        if (!o.isMesh) return;
        const g = o.geometry, p = g.attributes.position, idx = g.index;
        const m = o.matrixWorld;
        const count = idx ? idx.count : p.count;
        const A = new THREE.Vector3(), B = new THREE.Vector3(), C = new THREE.Vector3();
        for (let i = 0; i < count; i += 3) {
            const ia = idx ? idx.getX(i) : i, ib = idx ? idx.getX(i + 1) : i + 1, ic = idx ? idx.getX(i + 2) : i + 2;
            A.fromBufferAttribute(p, ia).applyMatrix4(m); B.fromBufferAttribute(p, ib).applyMatrix4(m); C.fromBufferAttribute(p, ic).applyMatrix4(m);
            const area = B.clone().sub(A).cross(C.clone().sub(A)).length() * 0.5;
            if (area <= 0) continue;
            total += area;
            tris.push([A.clone(), B.clone(), C.clone(), total]);
        }
    });
    const pts = [];
    for (let k = 0; k < n && tris.length; k++) {
        const r = R() * total;
        let lo = 0, hi = tris.length - 1;
        while (lo < hi) { const mid = (lo + hi) >> 1; if (tris[mid][3] < r) lo = mid + 1; else hi = mid; }
        const [A, B, C] = tris[lo];
        let u = R(), v = R();
        if (u + v > 1) { u = 1 - u; v = 1 - v; }
        pts.push(A.clone().addScaledVector(B.clone().sub(A), u).addScaledVector(C.clone().sub(A), v));
    }
    return pts;
}

export async function buildApparitions(THREE, { dir = OCEAN_ASSETS + 'figures/', base = new THREE.Vector3(), yaw = 0 } = {}) {
    const { Fn, uniform, float, vec2, vec3, vec4, attribute, positionLocal, positionWorld, normalView, positionViewDirection, mix, smoothstep, clamp,
        step, dot, abs, pow, max, exp, sin, length, cameraProjectionMatrix, modelViewMatrix, mrt, mx_noise_float } = THREE;
    const group = new THREE.Group();
    group.name = 'ocean:apparitions';
    const U = { rRise: uniform(0), rDiss: uniform(0), hRise: uniform(0), hDiss: uniform(0), t: uniform(0), rBase: uniform(0), rTop: uniform(9), rEyes: uniform(0) };
    const out = { group, U, robot: null, human: null };

    // ---------------------------------------------------------------- the robot
    const robot = await loadGLB(dir + 'robot.glb');
    if (robot) {
        const box = new THREE.Box3().setFromObject(robot);
        const H = box.max.y - box.min.y;
        const S = 10.5 / Math.max(0.1, H);                            // ~10.5 m tall out on the water
        const holder = new THREE.Group();
        robot.position.y = -box.min.y;
        holder.add(robot);
        holder.scale.setScalar(S);
        const rim = new THREE.Color(0.62, 0.72, 1.0), gold = new THREE.Color(1.0, 0.6, 0.24);
        const c3 = (c) => vec3(c.r, c.g, c.b);
        // one silhouette material family; the lenses and lamps keep their glow (red eyes, amber chest lights)
        const silhouette = (glow) => {
            const m = new THREE.MeshBasicNodeMaterial({ side: THREE.DoubleSide });
            const fres = pow(float(1).sub(abs(dot(normalView, positionViewDirection))), 2.5);
            const hN = clamp(positionWorld.y.sub(U.rBase).div(U.rTop.sub(U.rBase)), 0, 1);   // 0 feet .. 1 head (world)
            const n = mx_noise_float(positionLocal.mul(14.0)).mul(0.5).add(0.5);
            // the dissolve front runs top-down: a point goes when (1 - height)*0.55 + noise*0.45 < progress
            const key = float(1).sub(hN).mul(0.55).add(n.mul(0.45));
            const thr = U.rDiss.mul(1.08);
            const edge = smoothstep(thr.add(0.09), thr, key).mul(step(0.001, U.rDiss));
            // NB: vec3(<THREE.Color>) evaluates to ZERO on this stack — always pass components (c3)
            const base = glow ? c3(glow).mul(U.rEyes) : mix(vec3(0.012, 0.013, 0.02), c3(rim), fres.mul(0.55));
            m.colorNode = base.add(c3(gold).mul(edge.mul(edge)).mul(9.0));
            m.opacityNode = step(thr, key);
            m.alphaTest = 0.5;
            return m;
        };
        const LENS = new THREE.Color(1.0, 0.08, 0.04).multiplyScalar(5), LAMP = new THREE.Color(1.0, 0.55, 0.15).multiplyScalar(2.5);
        robot.traverse((o) => {
            if (!o.isMesh) return;
            const pick = (mm) => /lens/i.test(mm?.name || '') ? silhouette(LENS) : /lamp/i.test(mm?.name || '') ? silhouette(LAMP) : silhouette(null);
            o.material = Array.isArray(o.material) ? o.material.map(pick) : pick(o.material);
            o.castShadow = false;
        });
        group.add(holder);
        out.robot = { holder, H: 10.5 };
    }

    // ---------------------------------------------------------------- the human of light
    const human = await loadGLB(dir + 'human.glb');
    if (human) {
        const box = new THREE.Box3().setFromObject(human);
        const H = box.max.y - box.min.y;
        const S = 8.5 / Math.max(0.1, H);
        human.position.y = -box.min.y;
        const holder = new THREE.Group();
        holder.add(human);
        holder.scale.setScalar(S);
        holder.updateMatrixWorld(true);
        // a faint fresnel shell (the figure's edge in light)
        human.traverse((o) => {
            if (!o.isMesh) return;
            const m = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide });
            const fres = pow(float(1).sub(abs(dot(normalView, positionViewDirection))), 3.0);
            m.colorNode = vec3(0.55, 0.85, 1.0).mul(fres.mul(0.9).add(0.02)).mul(float(1).sub(U.hDiss));
            m.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) });
            o.material = m;
        });
        // points of light on its surface (holder-local)
        const pts = sampleSurface(THREE, human, 5200, 13);
        const inv = new THREE.Matrix4().copy(holder.matrixWorld).invert();
        const n = pts.length;
        const cen = new Float32Array(n * 12), cor = new Float32Array(n * 8), rnd = new Float32Array(n * 16);
        const R = rng(17), idx = [];
        const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
        pts.forEach((p, i) => {
            const q = p.clone().applyMatrix4(inv);
            const a = [R(), R(), R(), R()];
            for (let k = 0; k < 4; k++) { cen.set([q.x, q.y, q.z], (i * 4 + k) * 3); cor.set(corners[k], (i * 4 + k) * 2); rnd.set(a, (i * 4 + k) * 4); }
            idx.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3);
        });
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.BufferAttribute(cen.slice(), 3));
        g.setAttribute('center', new THREE.BufferAttribute(cen, 3));
        g.setAttribute('corner', new THREE.BufferAttribute(cor, 2));
        g.setAttribute('rnd', new THREE.BufferAttribute(rnd, 4));
        g.setIndex(idx);
        g.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 1, 0), 5);
        const pm = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
        pm.vertexNode = Fn(() => {
            const c = attribute('center', 'vec3'), r = attribute('rnd', 'vec4');
            // dissolve: each point lifts and drifts outward, a little twinkle while it holds
            const d = U.hDiss;
            const outward = vec3(c.x, 0, c.z).mul(d.mul(1.6).mul(r.x.add(0.3)));
            const up = vec3(0, d.mul(d).mul(r.y.mul(2.2).add(0.6)), 0);
            const sway = vec3(sin(U.t.mul(1.7).add(r.z.mul(6.28))).mul(0.01), 0, 0);
            const p = c.add(outward).add(up).add(sway);
            const mv = modelViewMatrix.mul(vec4(p, 1.0));
            const size = max(float(0.012).add(r.w.mul(0.012)), length(mv.xyz).mul(0.0018));
            return cameraProjectionMatrix.mul(vec4(mv.xyz.add(vec3(attribute('corner', 'vec2').mul(size), 0.0)), 1.0));
        })();
        pm.colorNode = Fn(() => {
            const q = attribute('corner', 'vec2'), r = attribute('rnd', 'vec4');
            const k = exp(dot(q, q).mul(-3.2));
            const tw = sin(U.t.mul(r.x.mul(9.0).add(2.0)).add(r.y.mul(6.28))).mul(0.25).add(0.75);
            const fade = float(1).sub(smoothstep(r.z.mul(0.5).add(0.35), 1.0, U.hDiss));
            return vec4(mix(vec3(0.55, 0.85, 1.0), vec3(1.0, 0.95, 0.85), r.w).mul(k).mul(tw).mul(fade).mul(0.75), 1.0);
        })();
        pm.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) });
        const points = new THREE.Mesh(g, pm);
        points.frustumCulled = false;
        holder.add(points);
        group.add(holder);
        out.human = { holder, H: 8.5 };
    }

    // placement: out on the water in the moon path, turned toward her rise
    for (const a of [out.robot, out.human]) {
        if (!a) continue;
        a.holder.position.copy(base);
        a.holder.rotation.y = yaw;
        a.holder.visible = false;
    }
    const ease = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
    out.update = (u, t) => {
        U.t.value = t;
        if (out.robot) {
            const rise = ease((u - 15.0) / 0.65), diss = ease((u - 15.95) / 0.7);
            out.robot.holder.visible = u > 14.95 && u < 16.8;
            out.robot.holder.position.y = base.y - 1.3 - (1 - rise) * out.robot.H * 0.75 - diss * 1.6;   // knee-deep in the sea
            U.rDiss.value = diss;
            U.rEyes.value = rise * (u < 15.9 ? Math.min(1, (u - 15.2) / 0.25) : 1);   // the eyes come on as it stands
            const wp = new THREE.Vector3();
            out.robot.holder.updateMatrixWorld(true);
            out.robot.holder.getWorldPosition(wp);
            U.rBase.value = wp.y; U.rTop.value = wp.y + out.robot.H;
        }
        if (out.human) {
            const rise = ease((u - 16.45) / 0.5), diss = ease((u - 17.2) / 0.75);
            out.human.holder.visible = u > 16.4 && u < 18.3;
            out.human.holder.position.y = base.y - 0.9 - (1 - rise) * out.human.H * 0.7;
            U.hDiss.value = diss;
        }
    };
    return out;
}
