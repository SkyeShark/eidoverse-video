// tuta_parity.mjs: claudesona_wardrobe.js itself (makeWardrobe on claude_suit_wardrobe.vrm, the TuTa wardrobe) run in
// deno on the CPU, three's WebGPU build for its TSL and no renderer: the reference test_tuta.py measures the Blender
// port against. Reads a job JSON, prints one result JSON line on stdout.
//
//   deno run --no-config --no-lock -A --import-map=<map.json> tuta_parity.mjs <job.json>
//
// job: { module (file URL of claudesona_wardrobe.js), vrm, scale, fps, frames: [f0, f1], texroot (the texture
//        library: <id>_<res>/<id>_Color.jpg ...), now: [[method, ...args]] (called once, before the frames),
//        schedule: [{at, pin} | {at, unpin, ghost, eject, linger}], wear_after: key | null (a garment outfit worn
//        after the frames: the cyclist's folds and hat), petal_keys: [...] }
// result: { layers: {name: visible}, frames: [{f, t, badges: {k: {vis, c: centroid, cov: 3x3, glow, ghost}},
//           sparks: {k: {vis, a, flare: [p, s], embers: [[p, s]]}}}], uniforms, pinned, ghosts, world: {k: ...},
//           cyclist: {folds, lift, petal_dirs, hat: {c, cov}} }       (positions in three's world, metres)
import * as W from 'three/webgpu';
import * as TSL from 'three/tsl';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';
import { MToonMaterialLoaderPlugin } from '@pixiv/three-vrm-materials-mtoon';
import { MToonNodeMaterial } from '@pixiv/three-vrm-materials-mtoon/nodes';

const THREE = { ...W, ...TSL };
const job = JSON.parse(Deno.readTextFileSync(Deno.args[0]));
globalThis.THREE = THREE;
// the engine's texture globals, reduced to what a CPU run needs: the files are read (as the engine reads them), the
// textures are empty (nothing is drawn)
globalThis.fetchPBR = async (id, { res = '1k' } = {}) => {
    const d = `${job.texroot}/${id}_${String(res).toLowerCase()}/`;
    return { files: { diff: d + `${id}_Color.jpg`, displacement: d + `${id}_Displacement.jpg` } };
};
globalThis.loadImageTexture = async (_bytes, opts = {}) => {
    const t = new THREE.Texture();
    if (opts.wrap) t.wrapS = t.wrapT = opts.wrap;
    return t;
};

const data = Deno.readFileSync(job.vrm);
const loader = new GLTFLoader();
loader.register((p) => new VRMLoaderPlugin(p, { mtoonMaterialPlugin: new MToonMaterialLoaderPlugin(p, { materialType: MToonNodeMaterial }) }));
const gltf = await new Promise((res, rej) => loader.parse(data.buffer, '', res, rej));
const vrm = gltf.userData.vrm;
const scene = new THREE.Scene();
scene.add(vrm.scene);
vrm.scene.scale.setScalar(job.scale ?? 1);
scene.updateMatrixWorld(true);

const { makeWardrobe, BADGES, WARDROBE } = await import(job.module);
for (const [name, spec] of Object.entries(job.presets || {})) WARDROBE[name] = spec;
const wd = await makeWardrobe(THREE, vrm, { wear: 'tuta' });
for (const [m, ...args] of job.now || []) wd[m](...args);
if (job.schedule) wd.schedule(job.schedule);

// a node's world vertices (every mesh under it, skinned or not): centroid + covariance, order-free
const cloud = (node) => {
    node.updateWorldMatrix(true, true);
    const P = [];
    const v = new THREE.Vector3();
    node.traverse((m) => {
        if (!m.isMesh) return;
        const a = m.geometry.attributes.position;
        for (let i = 0; i < a.count; i++) {
            v.fromBufferAttribute(a, i);
            if (m.isSkinnedMesh) m.applyBoneTransform(i, v);
            v.applyMatrix4(m.matrixWorld);
            P.push([v.x, v.y, v.z]);
        }
    });
    const c = [0, 0, 0];
    for (const p of P) for (let k = 0; k < 3; k++) c[k] += p[k] / P.length;
    const cov = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    for (const p of P) for (let r = 0; r < 3; r++) for (let k = 0; k < 3; k++) cov[r][k] += (p[r] - c[r]) * (p[k] - c[k]) / P.length;
    return { c, cov, n: P.length };
};
const visibleChain = (o) => { for (let n = o; n; n = n.parent) if (!n.visible) return false; return true; };
const wp = (o) => { o.updateWorldMatrix(true, false); const p = o.getWorldPosition(new THREE.Vector3()); return [p.x, p.y, p.z]; };
const ws = (o) => { const s = o.getWorldScale(new THREE.Vector3()); return s.x; };

const out = { layers: {}, frames: [], BADGES };
for (const n of ['tuta', 'uf_boots', 'uf_straps', 'acc_sundisc', ...BADGES]) out.layers[n] = wd.layers[n] ? wd.layers[n].visible : null;
const shoes = [];
vrm.scene.traverse((o) => { if (o.isMesh && o.name.startsWith('shoes')) shoes.push(o.visible); });
out.layers.shoes = shoes;
const fps = job.fps ?? 30;
const [f0, f1] = job.frames || [1, 1];
for (let f = f0; f <= f1; f++) {
    const t = (f - 1) / fps;
    wd.update(t);
    scene.updateMatrixWorld(true);
    const fr = { f, t, badges: {}, sparks: {} };
    for (const k of BADGES) {
        const o = wd.badges[k];
        if (!o) continue;
        const C = cloud(o);
        const mats = [];
        o.traverse((m) => { if (m.isMesh) for (const mm of (Array.isArray(m.material) ? m.material : [m.material])) if (mm?.userData?.ufEmissive !== undefined) mats.push(mm); });
        const glow = mats.length ? mats[0].emissiveIntensity / mats[0].userData.ufEmissive : null;
        fr.badges[k] = { vis: visibleChain(o), c: C.c, cov: C.cov, glow, ghost: wd.uniforms.ghost[BADGES.indexOf(k)].value };
        const sp = scene.getObjectByName('uf_sparks_' + k);
        if (sp) {
            const flare = sp.children[0], embers = sp.children.slice(1);
            fr.sparks[k] = { vis: sp.visible, flare: [wp(flare), ws(flare)], embers: embers.map((e) => [wp(e), ws(e)]) };
        }
    }
    out.frames.push(fr);
}
out.uniforms = { neon: wd.uniforms.neon.value, paint: wd.uniforms.paint.value, eyes: wd.uniforms.eyes.value, eyeNeon: wd.uniforms.eyeNeon.value };
out.pinned = [...wd.pinned];
out.ghosts = [...wd.ghosts];
out.world = {};
for (const k of BADGES) { const r = wd.badgeWorld(k); out.world[k] = { p: [r.position.x, r.position.y, r.position.z], flying: r.flying, visible: r.visible }; }
if (job.wear_after) {
    wd.wear(job.wear_after);
    scene.updateMatrixWorld(true);
    const dirs = {};
    for (const k of job.petal_keys || []) dirs[k] = wd.petalDir(k);
    const hat = wd.layers.boater;
    out.cyclist = { folds: wd.folds, lift: wd.lift, petal_dirs: dirs, hat: hat ? cloud(hat) : null,
        layers: Object.fromEntries(Object.entries(wd.layers).map(([n, o]) => [n, o.visible])) };
}
out.wears = {};
for (const key of job.wears || []) {          // more presets worn in turn: the layers shown and the hat
    wd.wear(key);
    scene.updateMatrixWorld(true);
    const hat = wd.layers.boater;
    out.wears[key] = { hat: hat ? cloud(hat) : null,
        layers: Object.fromEntries(Object.entries(wd.layers).map(([n, o]) => [n, o.visible])) };
}
console.log(JSON.stringify(out));
