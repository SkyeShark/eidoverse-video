// human_face_eval.js — THE ONE DRIVER of the Bestiary human's face (HUMAN_PLAN §4.5, decision 18; the H4 rig builder,
// 11-01). The VRM expressions carry NO binds: a scene (the talk driver, a blink, a preset) sets their values on
// vrm.expressionManager as for any VRM, and this evaluator reads them each frame and moves the face JOINTS by the
// creature's own control table (the glb's extras.bestiary.human.face, written by forge/species/human_face.py):
//   * the presets and visemes (aa ih ou ee oh, blink, happy ...) expand through the table's COMBOS into controls;
//     the ARKit customs (jawOpen, mouthSmileLeft ...) are controls themselves; each control's weight clamped to 0..1;
//   * each control's keys sum per joint: rotations (degrees about the T-pose rest's axes at the joint: every rest
//     rotation is the identity, so the joint's own axes) as rotation vectors, translations in mm;
//   * the joint's pose = its rest rotation x the summed rotation, its rest position + the summed translation. The jaw
//     is a humanoid bone (VRM 'jaw'): it is set on the NORMALIZED rig, which vrm.update() copies to the raw bone; the
//     lids, brows, cheeks, nostrils and lips are raw joints. The EYES are the VRM lookAt's (type bone): their keys are
//     skipped here.
// Call update() BEFORE the controller's (or vrm's) update each frame: the humanoid copy then carries the jaw.
// Staged for bestiary.js as patches/human_face_runtime.md (the runtime is the landings').
//
// (H4b face builder, 11-02: my copy of the rig builder's h4/rig/engine/human_face_eval.js, sha1 1af575cf, for the integrator's
// diff; staged with h4b/face/patches/human_face_runtime_h4b.md) THE LIDS FOLLOW THE GAZE: the face table's eyeLook*
// controls carry the lids' share of a look (upper 0.55 / lower 0.35 of the eye's pitch, the lid push over the cornea), and
// the H4 check found nothing set them: at the lookAt's extremes the man's lid skin sank 0.47 mm into his eyeball. Now each
// update reads the lookAt's yaw and pitch (three-vrm 3.5.2's VRMLookAt: yaw + = toward the character's left, pitch + =
// DOWN, degrees; its last frame's: the lookAt updates inside vrm.update, after this) and adds those controls at the same
// share of the gated range the eye turns (the range maps are 1:1 to it and clamp there), so only their LID keys act (the
// eye keys stay skipped). { coupleLids: false } turns it off.
export function makeFaceEval(vrm, face, { warn = console.warn, coupleLids = true } = {}) {
    const THREE = globalThis.THREE;
    const em = vrm.expressionManager;
    const HUM = { jaw: 'jaw', eye_L: 'leftEye', eye_R: 'rightEye' };
    const controls = face.controls || {};
    const combos = face.combos || {};
    const J = {};
    const want = new Set();
    for (const keys of Object.values(controls)) for (const k of keys) want.add(k[0]);
    for (const nm of want) {
        if (nm.startsWith('eye_')) continue;
        const o = HUM[nm] ? vrm.humanoid.getNormalizedBoneNode(HUM[nm]) : vrm.scene.getObjectByName(nm);
        if (!o) { warn(`[human_face_eval] no joint ${nm}`); continue; }
        J[nm] = { o, p0: o.position.clone(), q0: o.quaternion.clone() };
    }
    const names = em ? em.expressions.map((e) => e.expressionName) : [];
    const tmp = new THREE.Vector3(), q = new THREE.Quaternion();
    const acc = {};
    for (const nm of Object.keys(J)) acc[nm] = { r: new THREE.Vector3(), t: new THREE.Vector3() };
    let last = {};
    // (H4b face) the gated gaze range the lookAt's maps clamp at (the table's gaze_deg: out / inner 25, up 22, down 25)
    const gaze = face.gaze_deg ? { out: face.gaze_deg.out || 25, up: face.gaze_deg.up || 22, down: face.gaze_deg.down || 25 } : null;
    let lastGaze = null;
    return {
        joints: J,
        lastGaze: () => lastGaze,
        update() {
            const w = {};
            for (const nm of names) {
                const x = em.getValue(nm) || 0;
                if (x <= 0) continue;
                const c = combos[nm];
                if (c) { for (const [k, s] of Object.entries(c)) if (controls[k]) w[k] = (w[k] || 0) + x * s; }
                else if (controls[nm]) w[nm] = (w[nm] || 0) + x;
            }
            // (H4b face) the lids follow the lookAt's gaze (the eyeLook* controls' lid keys)
            if (coupleLids && vrm.lookAt && gaze) {
                const yaw = vrm.lookAt.yaw || 0, pitch = vrm.lookAt.pitch || 0;
                const add = (k, x) => { if (x > 0 && controls[k]) w[k] = (w[k] || 0) + Math.min(1, x); };
                const up = Math.max(0, -pitch) / gaze.up, dn = Math.max(0, pitch) / gaze.down;
                const lf = Math.max(0, yaw) / gaze.out, rt = Math.max(0, -yaw) / gaze.out;
                add('eyeLookUpLeft', up); add('eyeLookUpRight', up); add('eyeLookDownLeft', dn); add('eyeLookDownRight', dn);
                add('eyeLookOutLeft', lf); add('eyeLookInRight', lf); add('eyeLookInLeft', rt); add('eyeLookOutRight', rt);
                lastGaze = { yaw, pitch };
            }
            for (const a of Object.values(acc)) { a.r.set(0, 0, 0); a.t.set(0, 0, 0); }
            for (const [c, x0] of Object.entries(w)) {
                const x = Math.min(1, Math.max(0, x0));
                for (const k of controls[c]) {
                    const a = acc[k[0]];
                    if (!a) continue;
                    if (k[1] === 'rot') a.r.addScaledVector(tmp.fromArray(k[2]), (k[3] * x * Math.PI) / 180);
                    else a.t.addScaledVector(tmp.fromArray(k[2]), x * 0.001);
                }
            }
            for (const [nm, j] of Object.entries(J)) {
                const a = acc[nm];
                const ang = a.r.length();
                if (ang > 1e-9) q.setFromAxisAngle(tmp.copy(a.r).divideScalar(ang), ang);
                else q.identity();
                j.o.quaternion.copy(j.q0).multiply(q);
                j.o.position.copy(j.p0).add(a.t);
            }
            last = w;
            return w;
        },
        lastControls: () => last,
    };
}
