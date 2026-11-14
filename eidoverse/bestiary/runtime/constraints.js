// constraints.js (A1, the runtime spine; ROBOT_PARTS.md §3.3): THE NODE-CONSTRAINT PASS for creatures that are not VRMs (a VRM's
// own constraints run in vrm.update). After the motion has posed the bones, each constrained node takes its rotation from its
// source, in dependency order (a source that is itself constrained is solved first), each on its REST rotation:
//   aim       the node turns (the least turn from its rest) so its aim axis points at the source's world position; with `up`
//             (a local axis) and `upSource`/`upWorld` the roll is fixed too (a calf actuator's cylinder keeps its clevis square)
//   rotation  the source's rotation over ITS rest, copied onto the node's rest (VRMC_node_constraint's rotation)
//   roll      the source's twist about rollAxis over its rest, onto the node's rest about the same axis (VRMC roll)
//   piston    a cylinder: it turns about its rest hinge axis (local z) so its x points at a pin fixed on the target, and its rod
//             (a child named by `rod`) slides along x by |pin - pivot| - L0 (the cyborg beetle's helper rule, generalised)
// each with a weight (0..1: the slerp from the rest). The records come from the glb:
//   * a node's extras.constraint (three: object.userData.constraint), one record or a list:
//       { type: 'aim', source: 'tibia_f_L', axis: [1, 0, 0], up: [0, 0, 1], upWorld: [0, 1, 0], weight: 1 }
//       { type: 'piston', target: 'tibia_f_L', pin: [x, y, z] (the target's frame), L0: 0.031, rod: 'rod_f_L' }
//   * a node's VRMC_node_constraint extension (glTF JSON: { constraint: { aim | rotation | roll: { source: <node index>,
//     aimAxis: 'PositiveX' | ..., rollAxis: 'X' | 'Y' | 'Z', weight } } }), read through the parser's associations.
// A creature with no records has no pass (create() never calls it): its motion's output is untouched.
const THREE = globalThis.THREE;

const AXES = { PositiveX: [1, 0, 0], NegativeX: [-1, 0, 0], PositiveY: [0, 1, 0], NegativeY: [0, -1, 0],
    PositiveZ: [0, 0, 1], NegativeZ: [0, 0, -1], X: [1, 0, 0], Y: [0, 1, 0], Z: [0, 0, 1] };

export function readConstraints(group, gltf) {
    const byName = new Map();
    group.traverse((o) => { if (o.name) byName.set(o.name, o); });
    const out = [];
    // extras
    group.traverse((o) => {
        const c = o.userData?.constraint;
        if (!c) return;
        for (const r of Array.isArray(c) ? c : [c]) {
            const src = byName.get(r.source || r.target);
            if (!src) continue;
            out.push({ node: o, type: r.type, src, axis: r.axis, up: r.up, upWorld: r.upWorld, upSource: byName.get(r.upSource),
                rollAxis: r.rollAxis, weight: r.weight ?? 1, pin: r.pin, L0: r.L0, rod: r.rod ? byName.get(r.rod) : null });
        }
    });
    // VRMC_node_constraint (by the parser's node associations)
    const json = gltf?.parser?.json;
    if (json?.nodes) {
        const objOf = new Map();
        group.traverse((o) => {
            const as = gltf.parser.associations?.get(o);
            if (as && as.nodes !== undefined && !objOf.has(as.nodes)) objOf.set(as.nodes, o);
        });
        json.nodes.forEach((n, i) => {
            const c = n.extensions?.VRMC_node_constraint?.constraint;
            const o = objOf.get(i);
            if (!c || !o) return;
            const [type, r] = Object.entries(c)[0];
            const src = objOf.get(r.source);
            if (!src) return;
            out.push({ node: o, type, src, axis: AXES[r.aimAxis] || null, rollAxis: r.rollAxis, weight: r.weight ?? 1 });
        });
    }
    return out;
}

export function constraintPass(group, records) {
    if (!records.length) return null;
    const V3 = THREE.Vector3, Q = THREE.Quaternion, M4 = THREE.Matrix4;
    // the rests (as the nodes stand at the bind, before any motion)
    for (const r of records) {
        r.q0 = r.node.quaternion.clone();
        r.p0 = r.node.position.clone();
        r.sq0 = r.src.quaternion.clone();
        if (r.rod) r.rodP0 = r.rod.position.clone();
        if (r.type === 'piston') r.z = new V3(0, 0, 1).applyQuaternion(r.q0).normalize();
    }
    // dependency order: a record whose source (or an ancestor of its node) is another record's node comes after it
    const isAnc = (a, b) => { for (let x = b; x; x = x.parent) if (x === a) return true; return false; };
    const order = [];
    const left = records.slice();
    while (left.length) {
        const i = left.findIndex((r) => !left.some((s) => s !== r && (isAnc(s.node, r.src) || isAnc(s.node, r.node.parent))));
        order.push(...left.splice(i < 0 ? 0 : i, 1));
    }
    const qa = new Q(), qb = new Q(), va = new V3(), vb = new V3(), mA = new M4();
    const worldQ = (o) => o.getWorldQuaternion(new Q());
    function solve() {
        for (const r of order) {
            const n = r.node;
            n.parent.updateWorldMatrix(true, false);
            r.src.updateWorldMatrix(true, false);
            const parQ = worldQ(n.parent);
            if (r.type === 'aim') {
                // the aim axis in the node's parent frame at the rest, and the wanted direction there
                const ax = va.fromArray(r.axis || [1, 0, 0]).applyQuaternion(r.q0).normalize();
                const pW = new V3().setFromMatrixPosition(n.parent.matrixWorld.clone().multiply(mA.compose(n.position, r.q0, n.scale)));
                const sW = new V3().setFromMatrixPosition(r.src.matrixWorld);
                const want = sW.sub(pW).applyQuaternion(parQ.clone().invert()).normalize();
                const swing = qa.setFromUnitVectors(ax, want);
                const q = swing.clone().multiply(r.q0);
                if (r.up) {
                    // the roll about the aim: the node's up axis toward the up reference, projected off the aim
                    const upRef = r.upSource ? new V3().setFromMatrixPosition(r.upSource.matrixWorld).sub(pW)
                        : new V3().fromArray(r.upWorld || [0, 1, 0]);
                    const upP = upRef.applyQuaternion(parQ.clone().invert());
                    const u = vb.fromArray(r.up).applyQuaternion(q);
                    const a = want.clone();
                    const u1 = u.clone().addScaledVector(a, -u.dot(a)).normalize();
                    const u2 = upP.addScaledVector(a, -upP.dot(a)).normalize();
                    if (u1.lengthSq() > 0.5 && u2.lengthSq() > 0.5) {
                        const ang = Math.atan2(new V3().crossVectors(u1, u2).dot(a), u1.dot(u2));
                        q.premultiply(qb.setFromAxisAngle(a, ang));
                    }
                }
                n.quaternion.copy(r.q0).slerp(q, r.weight);
            } else if (r.type === 'rotation') {
                const d = r.sq0.clone().invert().multiply(r.src.quaternion);
                n.quaternion.copy(r.q0).multiply(qa.identity().slerp(d, r.weight));
            } else if (r.type === 'roll') {
                const ax = va.fromArray(AXES[r.rollAxis] || [1, 0, 0]);
                const d = r.sq0.clone().invert().multiply(r.src.quaternion);
                let tau = 2 * Math.atan2(d.x * ax.x + d.y * ax.y + d.z * ax.z, d.w);
                tau = Math.atan2(Math.sin(tau), Math.cos(tau));
                n.quaternion.copy(r.q0).multiply(qa.setFromAxisAngle(ax, r.weight * tau));
            } else if (r.type === 'piston') {
                const pp = new V3().fromArray(r.pin).applyMatrix4(r.src.matrixWorld)
                    .applyMatrix4(mA.copy(n.parent.matrixWorld).invert());
                const d = pp.sub(r.p0);
                r.len = d.length();
                const cx = d.sub(r.z.clone().multiplyScalar(d.dot(r.z))).normalize();
                n.quaternion.setFromRotationMatrix(new M4().makeBasis(cx, new V3().crossVectors(r.z, cx), r.z));
                n.position.copy(r.p0);
                if (r.rod) r.rod.position.set(r.rodP0.x + (r.len - r.L0), r.rodP0.y, r.rodP0.z);
            }
            n.updateMatrixWorld(true);
        }
    }
    // the misses for gates: an aim's angle off its source (deg), a piston's pin against its rod's end (world units)
    function probe() {
        return order.map((r) => {
            const n = r.node;
            if (r.type === 'aim') {
                const ax = new V3().fromArray(r.axis || [1, 0, 0]).applyQuaternion(worldQ(n)).normalize();
                const d = new V3().setFromMatrixPosition(r.src.matrixWorld).sub(new V3().setFromMatrixPosition(n.matrixWorld)).normalize();
                return { node: n.name, type: r.type, deg: ax.angleTo(d) * 180 / Math.PI };
            }
            if (r.type === 'piston' && r.rod) {
                return { node: n.name, type: r.type, miss: new V3().fromArray(r.pin).applyMatrix4(r.src.matrixWorld)
                    .distanceTo(new V3(r.L0, 0, 0).applyMatrix4(r.rod.matrixWorld)) };
            }
            return { node: n.name, type: r.type };
        });
    }
    return { solve, probe, records: order };
}
