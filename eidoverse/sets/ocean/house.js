// ocean/house.js — the small house on the spit (house.glb in the pack eidoverse/assets/sets/ocean/house/,
// built in Blender by the pack's blender/house/*.py).
// One window, warm, switched on with the kick at bar 12 ("is there someone home"); the porch light —
// the most important light of the verse — comes on at "on" (u 28.13), an incandescent swell with a
// breath of flicker, a halo in the sea air, a pool of light on the porch, a glint on the cove.
//
// buildHouse(THREE, { path, envMap }) -> null | { group, porchLocal, windowLocal, update(u, t) }
//   group: the GLB scene (origin at grade, front +z); the set places it on the spit.

import { OCEAN_ASSETS } from './util.js';

async function loadGLB(path) {
    try {
        const bytes = Deno.readFileSync(path);
        const loader = new globalThis.GLTFLoader();
        const gltf = await new Promise((res, rej) => loader.parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '', res, rej));
        return gltf.scene;
    } catch (e) { console.warn('[ocean] house.glb not loaded:', e.message); return null; }
}

// a loaded glTF material -> a MeshStandardNodeMaterial with the same maps (so nodes + our envMap apply)
function toNode(THREE, m, envMap) {
    const n = new THREE.MeshStandardNodeMaterial();
    for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap', 'alphaMap']) if (m[k]) n[k] = m[k];
    n.color.copy(m.color ?? new THREE.Color(1, 1, 1));
    n.roughness = m.roughness ?? 1; n.metalness = m.metalness ?? 0;
    if (m.normalScale) n.normalScale.copy(m.normalScale);
    n.transparent = !!m.transparent; n.opacity = m.opacity ?? 1; n.alphaTest = m.alphaTest ?? 0;
    n.side = m.side ?? THREE.FrontSide; n.depthWrite = m.depthWrite ?? true;
    n.name = m.name;
    if (envMap) { n.envMap = envMap; n.envMapIntensity = 0.8; }
    return n;
}

export async function buildHouse(THREE, { path = OCEAN_ASSETS + 'house/house.glb', envMap = null } = {}) {
    const scene = await loadGLB(path);
    if (!scene) return null;
    const { uniform, float, vec3, vec4, mix, pow, abs, dot, normalView, positionViewDirection, texture, uv, mrt, exp, length } = THREE;
    const U = { porch: uniform(0), win: uniform(0), t: uniform(0) };
    // meshes whose own name or an ancestor's name matches (glTF often wraps a mesh in a named node)
    const byName = (re) => {
        const out = [];
        scene.traverse((o) => {
            if (!o.isMesh) return;
            let n = o, hit = false;
            while (n && !hit) { hit = re.test(n.name || ''); n = n.parent; }
            if (hit) out.push(...(Array.isArray(o.material) ? o.material.map((m) => ({ material: m })) : [o]));
        });
        return out;
    };
    const warm = new THREE.Color(1.0, 0.6, 0.28), lampCol = new THREE.Color(1.0, 0.64, 0.32);
    const c3 = (c) => vec3(c.r, c.g, c.b);                  // NB: vec3(<THREE.Color>) evaluates to zero on this stack
    scene.traverse((o) => {
        if (!o.isMesh) return;
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        const conv = mats.map((m) => toNode(THREE, m, envMap));
        o.material = Array.isArray(o.material) ? conv : conv[0];
        o.castShadow = false; o.receiveShadow = false;
    });
    // the window: warm light behind the curtain; the glass carries it
    for (const o of byName(/window_curtain/i)) {
        const m = o.material;
        const base = m.map ? texture(m.map, uv()).rgb : vec3(m.color.r, m.color.g, m.color.b);
        m.emissiveNode = base.mul(c3(warm)).mul(U.win.mul(2.4));
    }
    for (const o of byName(/window_glass/i)) {
        const m = o.material;
        m.transparent = true; m.opacity = 0.55; m.roughness = 0.08; m.metalness = 0;
        m.emissiveNode = c3(warm).mul(U.win.mul(0.9));
        m.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) });
    }
    // the porch lamp: glass and bulb come alive with the light
    for (const o of byName(/lamp_bulb/i)) {
        o.material.emissiveNode = vec3(1.0, 0.78, 0.5).mul(U.porch.mul(9.0));
    }
    for (const o of byName(/lamp_glass/i)) {
        const m = o.material;
        m.transparent = true; m.opacity = 0.45; m.roughness = 0.12;
        const fres = pow(float(1).sub(abs(dot(normalView, positionViewDirection))), 1.5);
        m.emissiveNode = c3(lampCol).mul(U.porch.mul(fres.mul(1.6).add(0.9)));
        m.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) });
    }
    // lights
    scene.updateMatrixWorld(true);
    const lampPt = scene.getObjectByName('lamp_light_point');
    const winPt = scene.getObjectByName('window_light_point');
    const porchLocal = new THREE.Vector3(0.7, 2.0, 2.3);
    if (lampPt) { lampPt.getWorldPosition(porchLocal); scene.worldToLocal(porchLocal); }
    const windowLocal = winPt ? new THREE.Vector3() : new THREE.Vector3(-1.1, 1.9, 1.6);
    if (winPt) { winPt.getWorldPosition(windowLocal); scene.worldToLocal(windowLocal); }
    const porchLight = new THREE.PointLight(lampCol, 0, 13, 2);
    porchLight.position.copy(porchLocal);
    const winLight = new THREE.PointLight(warm, 0, 5, 2);
    winLight.position.copy(windowLocal).add(new THREE.Vector3(0, -0.3, 0.95));     // just outside the glass
    scene.add(porchLight, winLight);
    // the porch lamp's halo in the salt air: a soft camera-facing glow (additive, never in the G-buffer)
    const haloMat = new THREE.SpriteNodeMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    const r2 = uv().sub(0.5).mul(2.0);
    haloMat.colorNode = c3(lampCol).mul(exp(dot(r2, r2).mul(-4.0)).mul(0.9).add(exp(dot(r2, r2).mul(-22.0)).mul(1.4))).mul(U.porch);
    haloMat.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) });
    const halo = new THREE.Sprite(haloMat);
    halo.scale.setScalar(1.1);
    halo.position.copy(porchLocal);
    scene.add(halo);
    const ease = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
    return {
        group: scene, U, porchLocal, windowLocal, porchLight, winLight,
        update(u, t) {
            U.t.value = t;
            // someone home: the window on the downbeat of bar 12 (a lamp switched on inside)
            const win = u < 22.52 ? 0 : ease((u - 22.52) / 0.3);
            // the porch light on "on": incandescent swell, a single catch, then steady with a faint breath
            let porch = 0;
            if (u >= 28.13) {
                const a = u - 28.13;
                porch = ease(a / 0.14) * (a < 0.3 ? 1 - 0.18 * Math.exp(-Math.pow((a - 0.2) / 0.035, 2)) : 1) * (1 + 0.012 * Math.sin(t * 7.3));
            }
            U.win.value = win; U.porch.value = porch;
            porchLight.intensity = 7.5 * porch;
            winLight.intensity = 1.6 * win;
        },
    };
}
