// claude_robot_dof.js on a mock VRM built from the Blender rig data (test_dof_parity.py writes it): the raw node tree
// (every bone's rest frame, three's axes), the normalized humanoid (identity rests, rest offsets), a skinned-mesh stand-in
// carrying the foot vertices (initLegClearance's set) and an expression manager. Each frame: the clip's pose, then the
// example's frame order; out: every normalized rotation and every stage as a turn in the VRM's frame.
//   deno run --no-config --no-lock -A dof_parity.mjs <three.module.js> <claude_robot_dof.js> <in.json> <out.json>
const [threePath, dofPath, inPath, outPath] = Deno.args;
const toUrl = (p) => 'file:///' + p.replace(/\\/g, '/').replace(/^\/+/, '');
const THREE = await import(toUrl(threePath));
globalThis.THREE = THREE;
// the module as shipped, plus one export of the legs' clearance memo (a test-only copy beside the outputs, so the
// comparison can read the pass's private state: loaded, the offsets, v_st)
const src = Deno.readTextFileSync(dofPath) + '\nexport { _legClear as __legClear };\n';
const copy = outPath.replace(/\.json$/, '_module.mjs');
Deno.writeTextFileSync(copy, src);
const DOF = await import(toUrl(copy));
const data = JSON.parse(Deno.readTextFileSync(inPath));
const { rig, hinges, frames, dt } = data;
const Q = (a) => new THREE.Quaternion(a[1], a[2], a[3], a[0]);     // [w, x, y, z] -> three
const A = (q) => [q.w, q.x, q.y, q.z];

const scene = new THREE.Group();
scene.name = 'vrm_scene';
// raw nodes: world rest frames -> locals under their parents
const raw = {};
for (const name of Object.keys(rig.bones)) { const o = new THREE.Object3D(); o.name = name; raw[name] = o; }
const world = {};
for (const [name, b] of Object.entries(rig.bones)) world[name] = { q: Q(b.q), p: new THREE.Vector3(...b.p) };
const placed = new Set();
function place(name) {
    if (placed.has(name)) return;
    const b = rig.bones[name], o = raw[name], W = world[name];
    if (b.parent) {
        place(b.parent);
        raw[b.parent].add(o);
        const P = world[b.parent], Pi = P.q.clone().invert();
        o.quaternion.copy(Pi.clone().multiply(W.q));
        o.position.copy(W.p.clone().sub(P.p).applyQuaternion(Pi));
    } else {
        scene.add(o);
        o.quaternion.copy(W.q);
        o.position.copy(W.p);
    }
    placed.add(name);
}
for (const name of Object.keys(rig.bones)) place(name);
// the normalized humanoid
const norm = {};
const normRoot = new THREE.Object3D();
normRoot.name = 'VRMHumanoidRig';
scene.add(normRoot);
for (const n of Object.keys(rig.humanoid)) { const o = new THREE.Object3D(); o.name = 'Normalized_' + n; norm[n] = o; }
const head = (n) => new THREE.Vector3(...rig.bones[rig.humanoid[n]].p);
for (const [n, p] of Object.entries(rig.norm_parent)) {
    (p ? norm[p] : normRoot).add(norm[n]);
    norm[n].position.copy(p ? head(n).sub(head(p)) : head(n));
}
// the foot vertices on a skinned-mesh stand-in (initLegClearance reads skinIndex / skinWeight / position, the skeleton's
// bones and boneInverses, the bindMatrix)
const mesh = new THREE.Object3D();
mesh.isSkinnedMesh = true;
{
    const pos = [], si = [], sw = [], bones = [], inv = [];
    for (const [bn, pts] of Object.entries(rig.feet)) {
        const k = bones.length;
        bones.push(raw[bn]);
        const hp = rig.bones[bn].p;
        inv.push(new THREE.Matrix4().makeTranslation(-hp[0], -hp[1], -hp[2]));
        for (const p of pts) { pos.push(p[0], p[1], p[2]); si.push(k, 0, 0, 0); sw.push(1, 0, 0, 0); }
    }
    mesh.geometry = { attributes: {
        position: new THREE.BufferAttribute(new Float32Array(pos), 3),
        skinIndex: new THREE.BufferAttribute(new Uint16Array(si), 4),
        skinWeight: new THREE.BufferAttribute(new Float32Array(sw), 4) } };
    mesh.skeleton = { bones, boneInverses: inv };
    mesh.bindMatrix = new THREE.Matrix4();
}
scene.add(mesh);
const em = { vals: {}, getValue(n) { return this.vals[n] || 0; }, setValue(n, v) { this.vals[n] = v; } };
const vrm = {
    scene,
    humanoid: { getNormalizedBoneNode: (n) => norm[n] || null, getRawBoneNode: (n) => (rig.humanoid[n] ? raw[rig.humanoid[n]] : null) },
    expressionManager: em,
};
scene.updateMatrixWorld(true);

const armSt = DOF.initArmDOF(vrm, hinges);
const handSt = DOF.initHandDOF(vrm, hinges);
const legSt = DOF.initLegDOF(vrm);
const crown = DOF.initCrown(vrm);

// each stage's rest, for its turn in the VRM's frame: R = P * local * Lrest^-1 * P^-1 (P its parent's world rest)
const stageNames = [];
for (const s of ['left', 'right']) {
    for (const k of ['HipPitch', 'HipSwing', 'ShoulderPitch', 'WristRoll', 'WristFlex', 'ThumbRotor']) stageNames.push(s + k);
}
const stageRest = {};
for (const n of stageNames) {
    const o = raw[n];
    if (!o) continue;
    stageRest[n] = { P: o.parent.getWorldQuaternion(new THREE.Quaternion()), L: o.quaternion.clone() };
}
const turnOf = (n) => {
    const r = stageRest[n], o = raw[n];
    return r.P.clone().multiply(o.quaternion).multiply(r.L.clone().invert()).multiply(r.P.clone().invert());
};
const petalRest = [];
for (let i = 0; i < 12; i++) { const o = raw['petal_' + String(i).padStart(2, '0')]; petalRest.push(o ? o.quaternion.clone() : null); }

const out = [];
const stats = {};
const t0 = performance.now();
for (const fr of frames) {
    DOF.restoreArmPose(vrm);
    for (const [n, q] of Object.entries(fr.q)) norm[n].quaternion.copy(Q(q));
    norm.hips.position.set(...fr.hp);
    DOF.keepArmPose(vrm);
    DOF.rehomeBody(vrm, stats);
    DOF.applyHardwareDOF(vrm, DOF.LEG_JOINTS, stats);
    DOF.applyLegClearance(vrm, stats, dt);
    DOF.applyArmDOF(vrm, stats, dt);
    DOF.applyHandDOF(vrm, stats);
    em.vals = { ...fr.w };
    DOF.applyHeadExpression(vrm, dt);
    DOF.applyCrown(vrm, dt);
    const q = {};
    for (const n of Object.keys(fr.q)) q[n] = A(norm[n].quaternion);
    const st = {};
    for (const n of stageNames) {
        if (!stageRest[n]) continue;
        const side = n.startsWith('left') ? 'left' : 'right', k = n.slice(side.length);
        const R = turnOf(n);
        if (k === 'HipPitch') st[side + 'HipPitch'] = A(R);
        else if (k === 'HipSwing') st[side + 'HipSwing'] = A(R);
        else if (k === 'ShoulderPitch') st[side + 'ShoulderPhi'] = 2 * Math.atan2(R.x, R.w);
        else if (k === 'WristRoll') st[side + 'WristRoll'] = A(R);
        else if (k === 'WristFlex') st[side + 'WristFlex'] = A(R);
        else if (k === 'ThumbRotor') st[side + 'ThumbRotor'] = A(R);
    }
    const petals = [];
    for (let i = 0; i < 12; i++) {
        const o = raw['petal_' + String(i).padStart(2, '0')];
        const d = petalRest[i].clone().invert().multiply(o.quaternion);
        petals.push(35 + 2 * Math.atan2(d.x, d.w) * 180 / Math.PI);
    }
    const mem = DOF.__legClear.get(vrm), dbg = {};
    for (const s of ['left', 'right']) {
        const W = armSt[s] && armSt[s].wrist, T = handSt.side[s], L = legSt[s], M = mem && mem[s];
        dbg[s] = { wrist: W ? [W.a, W.b, W.c, ...W.asked] : null, thumb: [T.alpha, T.beta], hip: L ? [L.a, L.b, L.c] : null,
                   loaded: M ? M.loaded : null, st: M ? M.st : null, next: M ? M.next : null, wst: M ? M.wst : null };
    }
    dbg.vst = mem && mem.vst ? [mem.vst.x, mem.vst.y, mem.vst.z] : null;
    out.push({ q, stages: st, petals, dbg });
}
const ms = performance.now() - t0;
Deno.writeTextFileSync(outPath, JSON.stringify({ frames: out, counts: { frames: out.length, crown: crown.found, ms: Math.round(ms) } }));
console.log(`[dof_parity.mjs] ${out.length} frames in ${ms.toFixed(0)} ms; petals ${crown.found}/12`);
