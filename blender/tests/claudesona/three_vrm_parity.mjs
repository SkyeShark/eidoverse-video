// three_vrm_parity.mjs: the engine's own three-vrm 3.5.2 (the main checkout's node_modules) on a VRM, CPU only, as the
// reference the Blender ports are measured against. Reads a job JSON, prints a result JSON on stdout.
//
//   deno run --no-config --no-lock -A --import-map=<map.json> three_vrm_parity.mjs <job.json>
//
// job: { vrm, scale, fps, frames, turn: [[t, deg], ...] (the scene's yaw, linear between keys),
//        nod: [[t, deg], ...] (the normalized head about +X), tie: deg | null (render_scene.mjs's tie limiter),
//        look: { targets: [[x, y, z], ...] (three world, one per frame) } | null, faces: true }
// result: { joints: [{bone, child}], tails: [[[x, y, z] per joint] per frame] (three world, the child's world position
//           after the frame's update), eyes: [[qL, qR] per frame] (world quaternions), yawPitch: [[yaw, pitch]],
//           face: { meshes: [{name, mats, verts, morphs, mouthPlate}] } }
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';

const job = JSON.parse(Deno.readTextFileSync(Deno.args[0]));
const data = Deno.readFileSync(job.vrm);
const loader = new GLTFLoader();
loader.register((p) => new VRMLoaderPlugin(p));
const gltf = await new Promise((res, rej) => loader.parse(data.buffer, '', res, rej));
const vrm = gltf.userData.vrm;
const scene = new THREE.Scene();
scene.add(vrm.scene);
vrm.scene.scale.setScalar(job.scale ?? 1);
const fps = job.fps ?? 30, dt = 1 / fps;
const lerpKeys = (keys, t) => {
    if (!keys || !keys.length) return 0;
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) if (t <= keys[i][0]) {
        const [t0, v0] = keys[i - 1], [t1, v1] = keys[i];
        return v0 + (v1 - v0) * (t - t0) / (t1 - t0);
    }
    return keys[keys.length - 1][1];
};
const D = Math.PI / 180;
const head = vrm.humanoid.getNormalizedBoneNode('head');
const pose = (t) => {
    vrm.scene.rotation.y = lerpKeys(job.turn, t) * D;
    head.quaternion.setFromAxisAngle(new THREE.Vector3(1, 0, 0), lerpKeys(job.nod, t) * D);
};
// render_scene.mjs's tie-blade limiter, verbatim in effect (a wrapper on vrm.update)
if (job.tie != null) {
    const tie1 = vrm.scene.getObjectByName('tie_1'), tie2 = vrm.scene.getObjectByName('tie_2');
    if (tie1 && tie2) {
        const orig = vrm.update.bind(vrm);
        const DOWN = new THREE.Vector3(0, -1, 0);
        let rest2 = null;
        vrm.update = function (dt2) {
            orig(dt2);
            const maxRad = job.tie * Math.PI / 180;
            tie1.updateWorldMatrix(true, false); tie2.updateWorldMatrix(true, false);
            const d = tie2.getWorldPosition(new THREE.Vector3()).sub(tie1.getWorldPosition(new THREE.Vector3()));
            if (d.lengthSq() > 1e-9) {
                d.normalize();
                const ang = d.angleTo(DOWN);
                const lim = job.tie === 0 ? 0 : maxRad;
                if (ang > lim + 1e-4) {
                    const full = new THREE.Quaternion().setFromUnitVectors(DOWN, d);
                    const partial = new THREE.Quaternion().slerp(full, lim / ang);
                    const target = DOWN.clone().applyQuaternion(partial);
                    const corr = new THREE.Quaternion().setFromUnitVectors(d, target);
                    const wq = tie1.getWorldQuaternion(new THREE.Quaternion()).premultiply(corr);
                    const pInv = tie1.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
                    tie1.quaternion.copy(pInv.multiply(wq));
                    tie1.updateWorldMatrix(false, true);
                }
            }
            if (!rest2) rest2 = tie2.quaternion.clone();
            else {
                const tipMax = Math.min(maxRad, 8 * Math.PI / 180);
                const a2 = rest2.angleTo(tie2.quaternion);
                if (a2 > tipMax) { tie2.quaternion.copy(rest2.clone().slerp(tie2.quaternion, tipMax / a2)); tie2.updateWorldMatrix(false, false); }
            }
        };
    }
}
const out = { joints: [], tails: [], eyes: [], yawPitch: [] };
const sbm = vrm.springBoneManager;
const joints = sbm ? [...sbm.joints] : [];
for (const j of joints) out.joints.push({ bone: j.bone.name, child: j.child ? j.child.name : null });
// the cold start the Blender bake's preroll=0 matches: frame 0's pose, then reset (the tails seated on it)
pose(0);
vrm.scene.updateMatrixWorld(true);
vrm.humanoid.update();
vrm.scene.updateMatrixWorld(true);
sbm?.reset();
const target = new THREE.Object3D();
scene.add(target);
if (job.look) {
    vrm.lookAt.target = target;
    const l = vrm.humanoid.getRawBoneNode('leftEye'), r = vrm.humanoid.getRawBoneNode('rightEye');
    out.eyesRest = [l ? l.getWorldQuaternion(new THREE.Quaternion()).toArray() : null, r ? r.getWorldQuaternion(new THREE.Quaternion()).toArray() : null];
}
for (let f = 0; f < job.frames; f++) {
    const t = f * dt;
    pose(t);
    if (job.look) { const p = job.look.targets[f]; target.position.set(p[0], p[1], p[2]); target.updateMatrixWorld(true); }
    vrm.scene.updateMatrixWorld(true);
    vrm.update(dt);
    vrm.scene.updateMatrixWorld(true);
    out.tails.push(joints.map((j) => (j.child ? j.child.getWorldPosition(new THREE.Vector3()) : j.bone.getWorldPosition(new THREE.Vector3())).toArray()));
    if (job.look) {
        const l = vrm.humanoid.getRawBoneNode('leftEye'), r = vrm.humanoid.getRawBoneNode('rightEye');
        out.eyes.push([l ? l.getWorldQuaternion(new THREE.Quaternion()).toArray() : null, r ? r.getWorldQuaternion(new THREE.Quaternion()).toArray() : null]);
        out.yawPitch.push([vrm.lookAt.yaw, vrm.lookAt.pitch]);
    }
}
if (job.colliders) {                       // every collider at the last frame: world position, capsule end, radius
    out.colliders = [];
    vrm.scene.updateMatrixWorld(true);
    for (const c of sbm.colliders) {
        c.updateWorldMatrix(true, false);
        const p = new THREE.Vector3().setFromMatrixPosition(c.colliderMatrix);
        const e = { node: c.parent?.name, type: c.shape.type, pos: p.toArray(), radius: c.shape.radius ?? null, inside: !!c.shape.inside };
        if (c.shape.type === 'capsule') e.tail = c.shape.tail.clone().sub(c.shape.offset).applyMatrix4(c.colliderMatrix).toArray();
        out.colliders.push(e);
    }
}
if (job.faces) {
    const isMouthPlate = (x, y, z) => Math.abs(x) < 0.03 && y > 1.44 && y < 1.48 && z < 0.095;
    out.face = { meshes: [] };
    vrm.scene.traverse((o) => {
        if (!o.isMesh || !o.morphTargetInfluences) return;
        const pos = o.geometry.attributes.position;
        let nm = 0;
        for (let i = 0; i < pos.count; i++) if (isMouthPlate(pos.getX(i), pos.getY(i), pos.getZ(i))) nm++;
        out.face.meshes.push({ name: o.name, mats: (Array.isArray(o.material) ? o.material : [o.material]).map((m) => m?.name), verts: pos.count, morphs: o.morphTargetInfluences.length, mouthPlate: nm });
    });
}
console.log(JSON.stringify(out));
