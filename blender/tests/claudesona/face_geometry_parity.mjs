// face_geometry_parity.mjs: claudesona_face.js's installSuitMouth / installVisemeMouth run in deno on the CPU on the
// claudesona's VRM, as the reference test_face_geometry.py measures the Blender port's shape keys against. Prints one
// result JSON line on stdout.
//
//   deno run --no-config --no-lock -A --import-map=<map.json> face_geometry_parity.mjs <job.json>
//
// job: { module (file URL of claudesona_face.js), vrm, install: 'suit' | 'viseme' }
// result: { meshes: [{ name, mats, rest0: [x, y, z ...] (geometry space before the install), rest: [...] (after),
//           targets: { name: [dx, dy, dz ...] } (every morph target's deltas after the install, relative to `rest`) }],
//           idx: { target name: index on the plate } }                            (three's axes, metres)
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';

const job = JSON.parse(Deno.readTextFileSync(Deno.args[0]));
globalThis.THREE = THREE;
const data = Deno.readFileSync(job.vrm);
const loader = new GLTFLoader();
loader.register((p) => new VRMLoaderPlugin(p));
const gltf = await new Promise((res, rej) => loader.parse(data.buffer, '', res, rej));
const vrm = gltf.userData.vrm;
const scene = new THREE.Scene();
scene.add(vrm.scene);
scene.updateMatrixWorld(true);

// the face meshes as the runtime finds them: every mesh with morphs, plus the face disc
const pick = [];
vrm.scene.traverse((o) => {
    if (!o.isMesh) return;
    const mats = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => m?.name);
    if (o.morphTargetInfluences || mats.includes('face')) pick.push(o);
});
const rest0 = new Map(pick.map((o) => [o, Array.from(o.geometry.attributes.position.array)]));
const F = await import(job.module);
const face = job.install === 'viseme' ? F.installVisemeMouth(vrm) : F.installSuitMouth(vrm);
const out = { meshes: [], idx: face.idx || null };
for (const o of pick) {
    const mats = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => m?.name);
    const names = Object.entries(o.morphTargetDictionary || {});
    const targets = {};
    const T = o.geometry.morphAttributes.position || [];
    for (let t = 0; t < T.length; t++) {
        let nm = (names.find(([, k]) => k === t) || [null])[0];
        if (nm === null) nm = `#${t}`;                       // the install's own targets have no dictionary name
        targets[nm] = Array.from(T[t].array);
    }
    out.meshes.push({ name: o.name, mats, isPlate: o === face.plate, rest0: rest0.get(o), rest: Array.from(o.geometry.attributes.position.array), targets });
}
console.log(JSON.stringify(out));
