// ocean/perform.js — the claudesona's verse-3 gestures, layered over whatever clip the conductor plays.
// Works on VRM 1.0 NORMALIZED bones (rest rotation identity, model axes: +y up, +z the way she faces,
// +x her left), then pushes them to the raw skeleton with vrm.humanoid.update() (no spring double-step).
//
//   const P = makePerformer(THREE);
//   P.handToFlower(vrm, w, { side: 'right', tilt })   // two-bone IK: the hand rises to the petals by her cheek
//   P.lookAt(vrm, worldPoint, w)                       // neck + head turn toward a world point (clamped)
//   P.commit(vrm)                                      // normalized -> raw

export function makePerformer(THREE) {
    const V = () => new THREE.Vector3(), Q = () => new THREE.Quaternion();
    const tmp = { a: V(), b: V(), c: V(), q: Q(), q2: Q(), m: new THREE.Matrix4(), inv: new THREE.Matrix4() };
    const node = (vrm, name) => vrm.humanoid?.getNormalizedBoneNode?.(name);
    // model-space (vrm.scene local) position / rotation of a normalized bone
    const modelPos = (vrm, n, out) => {
        n.getWorldPosition(out);
        tmp.inv.copy(vrm.scene.matrixWorld).invert();
        return out.applyMatrix4(tmp.inv);
    };
    const modelQuat = (vrm, n, out) => {
        n.getWorldQuaternion(out);
        vrm.scene.getWorldQuaternion(tmp.q2);
        return out.premultiply(tmp.q2.invert());
    };
    const basis = (dir, hinge) => {                         // orthonormal frame [dir, hinge, dir x hinge] as a quaternion
        const x = dir.clone().normalize();
        const y = hinge.clone().sub(x.clone().multiplyScalar(hinge.dot(x))).normalize();
        const z = x.clone().cross(y);
        return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z));
    };
    const slerpLocal = (n, target, w) => { n.quaternion.slerp(target, w); };

    return {
        // the hand rises to the flower: wrist target beside the face disc, elbow down and a little out
        handToFlower(vrm, w, { side = 'right', reach = [0.0, 0.0, 0.0], tilt = 0, curl = 0.45 } = {}) {
            if (!vrm || w <= 0.0001) return;
            const s = side === 'right' ? -1 : 1;             // model x of her right side is -x
            const P = side === 'right' ? 'right' : 'left';
            const up = node(vrm, P + 'UpperArm'), lo = node(vrm, P + 'LowerArm'), hand = node(vrm, P + 'Hand');
            const head = node(vrm, 'head');
            if (!up || !lo || !hand || !head) return;
            vrm.scene.updateMatrixWorld(true);
            const S = modelPos(vrm, up, V()), H = modelPos(vrm, head, V());
            const a = lo.position.length(), b = hand.position.length();
            // target (rig units, measured on claude_suit): the face disc is centred ~(0, head+0.03, 0.12), radius
            // ~0.16; the wrist goes just outside its edge at cheek height, so the fingers rise into the petals
            const T = H.clone().add(new THREE.Vector3(s * (0.245 + reach[0]), -0.17 + reach[1], 0.10 + reach[2]));
            const dST = T.clone().sub(S);
            const d = Math.min(Math.max(dST.length(), 0.05), (a + b) * 0.995);
            dST.normalize();
            const cosA = (a * a + d * d - b * b) / (2 * a * d);
            const alpha = Math.acos(Math.max(-1, Math.min(1, cosA)));
            const pole = new THREE.Vector3(s * 0.35, -1, -0.25).normalize();   // elbow down, out, a little back
            const perp = pole.clone().sub(dST.clone().multiplyScalar(pole.dot(dST))).normalize();
            const E = S.clone().add(dST.clone().multiplyScalar(Math.cos(alpha) * a)).add(perp.multiplyScalar(Math.sin(alpha) * a));
            const Tt = S.clone().add(dST.clone().multiplyScalar(d));
            const u = E.clone().sub(S).normalize(), f = Tt.clone().sub(E).normalize();
            // rest frame: the arm points along s*x, the elbow flexes the forearm toward +z (hinge = dir x +z)
            const d0 = new THREE.Vector3(s, 0, 0), f0 = new THREE.Vector3(0, 0, 1);
            const hinge0 = d0.clone().cross(f0).normalize();
            let hinge = u.clone().cross(f);
            if (hinge.lengthSq() < 1e-8) hinge = hinge0.clone();
            hinge.normalize();
            const B0 = basis(d0, hinge0);
            const qUp = basis(u, hinge).multiply(B0.clone().invert());       // model-space rotations
            const qLo = basis(f, hinge).multiply(B0.clone().invert());
            const qParent = modelQuat(vrm, up.parent, Q());
            const locUp = qParent.clone().invert().multiply(qUp);
            const locLo = qUp.clone().invert().multiply(qLo);
            slerpLocal(up, locUp, w);
            slerpLocal(lo, locLo, w);
            // the wrist: palm toward the cheek, fingers up into the petals
            const wrist = new THREE.Quaternion().setFromEuler(new THREE.Euler(0.0, 0.15 * s, 0.22 * s));
            slerpLocal(hand, wrist, w);
            // a soft curl of the fingers (curl axis: +z for the right hand, -z for the left)
            const fingers = ['Index', 'Middle', 'Ring', 'Little'];
            for (const [fi, F] of fingers.entries()) for (const [ji, J] of ['Proximal', 'Intermediate', 'Distal'].entries()) {
                const n = node(vrm, P + F + J);
                if (!n) continue;
                const k = curl * (0.55 + ji * 0.25) * (0.8 + fi * 0.12);
                slerpLocal(n, new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, -s), k), w);
            }
            const th = node(vrm, P + 'ThumbProximal');
            if (th) slerpLocal(th, new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), 0.35 * s), w);
            if (tilt) {                                        // lean the flower into the hand
                const hq = head.quaternion.clone().multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), tilt * -s));
                slerpLocal(head, hq, w);
            }
        },
        // neck + head toward a world point, clamped; w blends from the clip
        lookAt(vrm, worldPoint, w, { maxYaw = 1.1, maxPitch = 0.45, neckShare = 0.4 } = {}) {
            if (!vrm || !worldPoint || w <= 0.0001) return;
            const head = node(vrm, 'head'), neck = node(vrm, 'neck');
            if (!head) return;
            vrm.scene.updateMatrixWorld(true);
            const Hm = modelPos(vrm, head, V());
            tmp.inv.copy(vrm.scene.matrixWorld).invert();
            const Pm = worldPoint.clone().applyMatrix4(tmp.inv);
            const dir = Pm.sub(Hm).normalize();
            const yaw = Math.max(-maxYaw, Math.min(maxYaw, Math.atan2(dir.x, dir.z)));
            const pitch = Math.max(-maxPitch, Math.min(maxPitch, Math.asin(Math.max(-1, Math.min(1, dir.y)))));
            const want = new THREE.Quaternion().setFromEuler(new THREE.Euler(-pitch, yaw, 0, 'YXZ'));   // model-space head rotation
            if (neck) {
                const pn = modelQuat(vrm, neck.parent, Q());
                const nq = new THREE.Quaternion().setFromEuler(new THREE.Euler(-pitch * neckShare, yaw * neckShare, 0, 'YXZ'));
                slerpLocal(neck, pn.clone().invert().multiply(nq), w);
                vrm.scene.updateMatrixWorld(true);
            }
            const ph = modelQuat(vrm, head.parent, Q());
            slerpLocal(head, ph.invert().multiply(want), w);
        },
        commit(vrm) { try { vrm.humanoid.update(); } catch (e) { } },
    };
}
