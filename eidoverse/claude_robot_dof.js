// Claude's robot body — the hardware-DOF pass (animation craft guide 04.1, 04.11, 05.31-05.33). Retargeted human
// clips write full three-axis rotations into every humanoid bone, but the robot's knees and toes are single pins and
// its ankles a pitch + roll cardan with no yaw: a clip's knee twist or foot yaw would turn rigid parts about axes the
// machine lacks and drive covers through each other. Each frame, after the clip (mixer) and before vrm.update(), this
// projects every listed bone's NORMALIZED rotation (three-vrm: rest = identity, world-aligned axes, VRM 1.0 facing +Z,
// the robot's left +X) onto the joint's real degrees of freedom and clamps it to the joint's range:
//   hinge   the twist about the pin's axis only (swing-twist), clamped to [min, max] deg
//   cardan  the twist about `noTwist` removed (the ankle has no yaw), then each remaining Euler angle clamped
//   ball    each Euler angle (order XZY: pitch, roll, yaw) clamped
// Ranges are DESIGN values until the clash sweeps measure first contact (05.31: limits 2-4 deg inside contact); the
// right side mirrors the left (roll and yaw signs flip, pitch stays). Idempotent: projecting a projected pose is a no-op.
//
//   const DOF = await import(new URL('claude_robot_dof.js', EIDOVERSE_DIR).href);  ...  DOF.applyHardwareDOF(vrm, DOF.LEG_JOINTS);
//   (the body is eidoverse/assets/vrms/claude_robot.vrm, its joints file claude_robot.joints.json beside it; the whole
//   frame order in one scene: eidoverse/examples/claude_robot.js)
//   the hips' stages (below): initLegDOF(vrm) once at load, before anything poses it; applyHardwareDOF then sets them
//   the arms (below): initArmDOF(vrm, hinges) once at load, before anything poses it (hinges: the exporter's joints
//   file's 'hinges', parsed first; its leftLowerArm record sets the elbow); then each frame after the clip:
//   rehomeBody(vrm), applyHardwareDOF(vrm, LEG_JOINTS), applyArmDOF(vrm), vrm.update(dt)

const D = Math.PI / 180;

// the legs (v2: knee 85,-20,516 and ankle 79,22,94 pins along the robot's X; the hip a ball through H with pitch, roll
// and yaw stages; the toe hinge along X). Flexion signs in normalized space: knee + about X bends the shin back; a hip
// flexes forward by - about X; toes curl down by + about X
// MEASURED (lower round 4c, 10-18): first contacts on the built lower body (work/tmp/lr4/leg_reach.py: exact winding
// numbers on the GPU, the stages as the file's constraints set them, each joint alone, 5 deg steps refined to 0.25;
// probe_clash clear at each last clear step and in contact 0.25-0.75 past it; since 10-29 robot_dof solves the stages,
// THE HIP'S STAGES below, and the table was re-probed in that pose: its 64 corners clear (DESIGN_HIP P2), the walk too
// on the deforming mesh (REVIEW_HIP WK); in the stages' own angles it reaches flexion 99.15, extension 23.09, abduction
// 44.27, adduction 15.63 and yaw 40.34 (REVIEW_HIP G)). Each limit sits 2.5-3.5 inside the first contact of
// the leg against itself and the pelvis (05.31); the other leg is the animation's to avoid (with it at rest the soles
// meet from 2 deg of adduction, the shins from 7; with both legs adducting, the toes from 1 each):
//   hip pitch  flexion 101.25 (the thigh's top on the belt's front: the leg room was cut for 100, SPEC's hip), extension
//              26.5 (the thigh's top on the seat hem)
//   hip roll   abduction 47.25 (the thigh's seal on the drum), adduction 17.0 (the thigh's cup on the axle collar)
//   hip yaw    no contact to +-75 (the yaw ring turns in itself: the swing stage aims at the knee): the design +-40
//   knee       115.5 (the calf clevises on the lower thigh's back, the shin's top-back at 115.75); none to -25 (0 is the
//              one-sided hinge's stop, 05.32)
//   ankle      a CARDAN since lower round 5 (pitch outer on the stage bone AnklePitch, roll inner on the foot: the cross
//              block on D12 pitch pins in the shin's yoke, the foot's saddle rolling on a fore-aft D12 shaft through
//              it). MEASURED on the built meshes (10-19, work/tmp/lr5: ankle_reach / critic_reach, exact winding
//              numbers, pitch bisected to 1/16 deg at every 1 deg of roll, roll in 0.25 steps): toes down 33.88 at roll
//              0 falling to 30.4 at +-15 (the actuators' bodies on the back bar), toes up -29.81 at 0, -30.0 at +4,
//              -28.13 at +15 and -25.06 at -15 (the instep under the shin's front edge, its medial side); roll: the
//              stop pins land on their slots' ends at +-17.0 at every pitch (the lower rod eyes meet the heel clevis
//              only at +-19.56), narrowed by the instep toes up (-10.75 at -27, -13.0 at -26, -15.25 at -25) and by
//              the actuators toes down (+-17.0 at 30, +14.75 / -14.5 at 30.5, +12.75 / -12.0 at 31). The rods run out
//              23.0 at (-26, 15) (7.0 of the 30 left) and in 23.1; the lower rod ends tilt |roll| + 0.4 (15.4 at 15)
//              in their +-25 class eyes
//   clear at these limits: the sit (hip 90, knee 100), the squat (98 / 112 / ankle -27), the knee at 90 or 112 with the
//   ankle at either stop, the toe up with the ankle up, tiptoe, kneel
export const LEG_JOINTS = [
    { bone: 'UpperLeg', type: 'ball', range: { x: [-98, 23], z: [-14, 44], y: [-40, 40] },
      // COUPLED limits (05.32), measured the same way, each 3 inside its first contact, and read by applyHardwareDOF's
      // ball clamp (10-18): the box alone let its corners clash (pitch -98 with roll 44: the thigh's top 4.2 mm into
      // the pelvis's front side; with -14: 14.2 into its front centre). The roll range narrows as the
      // hip flexes past 67 (the thigh's top on the pelvis's front) or extends (the seal on the frame plate): zmin and
      // zmax piecewise linear in x (the step between -72.5 and -70 taken at the lower value); the internal yaw floor
      // ymin rises with abduction (the seal on the drum, at extension on the liner), piecewise linear in z, the floor
      // over the whole pitch range (the worst at extension 15-23: at pitch 0 it is lower, -38 at roll 22.5). The left
      // leg's signs, as range's: the right mirrors them (z and y negated)
      coupled: {
          x: [-98, -95, -90, -85, -80, -77.5, -75, -72.5, -70, -67.5, 0, 5, 10, 15, 20, 23],
          zmin: [-0.5, -1.5, -3, -5, -7.5, -9.25, -10.75, -12.5, -14, -14, -14, -14, -14, -14, -14, -14],
          zmax: [21, 21.5, 22.75, 25.5, 28, 29, 29.75, 30.75, 30.75, 44, 44, 40.75, 34.5, 28.5, 23, 19.5],
          z: [0, 15, 19.5, 23, 30, 37.5, 44],
          ymin: [-40, -40, -31.75, -21.25, -14, -9.25, -5.5],
      } },
    { bone: 'LowerLeg', type: 'hinge', axis: [1, 0, 0], range: [0, 112] },
    { bone: 'Foot', type: 'cardan', noTwist: [0, 1, 0], range: { x: [-26.9, 30.9], z: [-14.9, 14.9] },
      // COUPLED roll by pitch (05.32, lower round 5): every pose the table allows lies at least 2 deg inside first
      // contact along the roll AND along the pitch (the critic of 5a: the design's table was 3 inside along roll but
      // 0.6-1.2 along pitch at its steep ends), derived from the 2-D contact boundary above (work/tmp/lr5/fx_table.py:
      // 3,483 points checked, the least margin 2.00, at the stop 17.0 behind z 15; 40 points 1.95 past the table both
      // ways clear; its 44 boundary points clear on both legs and with the rods anti-rotated). z + lifts the sole's
      // lateral edge (eversion); piecewise linear in x, held at its ends; the left leg's signs, the right mirrors them.
      // Both feet INVERTING together meet at 10.25 each (their soles' inner fronts; 10-11 in the design): the
      // animation's to avoid, as lower round 4's other-leg pairs. The verifier's finer sweep (exact crossings bisected
      // to 0.02, work/tmp/lr5/v5m/table_margin.py) found 1.91 along the pitch at roll +9..+12 toes down, 1.92 at -14,
      // 1.97 toes up, and the stop's first contact at 16.98 (1.98 behind z 15): the lead moved every node 0.1 inward
      // in pitch and the roll range to 14.9 (10-20), so all of them clear 2.0 again
      coupled: {
          x: [-26.9, -26.4, -25.9, -22.9, 28.15, 28.4, 28.9, 29.9, 30.4, 30.9],
          zmin: [-3.75, -6.25, -8.25, -14.9, -14.9, -14.5, -11.5, -7.25, -4.75, -3],
          zmax: [10.5, 13.25, 14.9, 14.9, 14.9, 14, 12.5, 8.5, 6.5, 4.5],
      } },
    // (the toe hinge, MEASURED (lower round 4c, its mechanism verifier: exact triangle crossings, 0.5 deg steps bisected
    //  to 0.01, both legs alike): first contact 43.68 up, where the stop faces end (x 21.3 at the labyrinth's step, 133.35
    //  at the ring; the bell's rear face lies flat on the room's stop face from 44.0), and 2.96 down (the soles' V faces;
    //  the creams' 2.97); the next pairs 7.73 / 7.82 down. The limits sit 2.68 and 2.96 inside them (05.31); no travel
    //  down from rest: the V is a hairline, its 3 deg the down stop)
    { bone: 'Toes', type: 'hinge', axis: [1, 0, 0], range: [-41, 0] },
];

// a table piecewise linear in x, held at its ends
const lerpTable = (xs, ys, x) => {
    if (x <= xs[0]) return ys[0];
    for (let i = 1; i < xs.length; i++) {
        if (x <= xs[i]) return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
    }
    return ys[ys.length - 1];
};

function twistAbout(q, a, out) {
    // the twist of q about the unit axis a: (a (q.v . a), q.w) normalised; identity when q is a pure swing
    const p = q.x * a[0] + q.y * a[1] + q.z * a[2];
    out.set(a[0] * p, a[1] * p, a[2] * p, q.w);
    const n = Math.hypot(out.x, out.y, out.z, out.w);
    if (n < 1e-9) out.set(0, 0, 0, 1); else out.set(out.x / n, out.y / n, out.z / n, out.w / n);
    return out;
}

// RE-HOMING (05.12: a rotation a clip writes into a joint the machine lacks goes to the joint that has it, logged):
// - the torso is rigid above the waist bellows (chest and upperChest pivot at the bellows' top and nothing bends
//   there): their rotation joins spine's (the bellows bends), then they rest at identity;
// - the clavicles (leftShoulder / rightShoulder) carry no joint (the arm's first stage sits in the torso's socket):
//   their rotation joins the upper arm's;
// - the neck is the pan stage alone (yaw about Y); the head's stages are pitch (about X) and roll (about Z): the
//   neck and head rotations compose, their yaw goes to the neck, the rest to the head, each clamped at the head's
//   built stops (roll +-11: 2.2 inside the crown's first contact over the head's range, 13.2; nod +-30; pan +-60)
export const HEAD_RANGE = { pan: [-60, 60], x: [-30, 30], z: [-11, 11] };   // (roll +-11: the head's stops, 10-17)
// spine (the waist bellows bends; chest and upperChest rehomed into it): the design values stand, every first contact
// measured 10-19 lies past them (torso fix round, work/tmp/tf/spine_reach.py: exact GPU contact scan of the assembled
// body, pivot the bellows' foot (0, -27, 1000), the bellows itself skinned and not counted, 0.25 deg resolution):
//   x forward: clear to 120 (arms T-pose), 106.25 (hanging: elbow yoke | hip dome), 82.0 with both hips at -60
//     (shell | thigh seals), 51.0 with both hips at -98 (shell | thigh shells: the binding pose, 26 past +25);
//   x back: -94.5 (shell | pelvis, both arm poses);
//   z side: 52.25 (T-pose: shell | pelvis), 26.25 hanging with applyArmClearance's 8 deg (fingertips | knee yoke;
//     without it the forearm meets the hip dome at 8.0: the clearance is what keeps the hanging arm clear, so
//     applyArmDOF applies it itself; the verifier re-measured 8.0 the same 10-19);
//   y twist: clear to 90 both ways, both arm poses.
export const SPINE_RANGE = { x: [-25, 25], z: [-15, 15], y: [-20, 20] };

export function rehomeBody(vrm, stats) {
    const THREE = globalThis.THREE;
    const H = vrm.humanoid, B = (n) => H.getNormalizedBoneNode(n);
    const e = new THREE.Euler(), tw = new THREE.Quaternion();
    const note = (k, q) => { if (stats) stats[k] = Math.max(stats[k] || 0, 2 * Math.acos(Math.min(1, Math.abs(q.w))) / D); };
    // the torso: spine * chest * upperChest -> spine
    const spine = B('spine'), chest = B('chest'), upper = B('upperChest');
    if (spine) {
        for (const n of [chest, upper]) {
            if (!n) continue;
            note('rehome_' + n.name, n.quaternion);
            spine.quaternion.multiply(n.quaternion);
            n.quaternion.identity();
        }
        e.setFromQuaternion(spine.quaternion, 'XZY');
        e.x = Math.min(SPINE_RANGE.x[1], Math.max(SPINE_RANGE.x[0], e.x / D)) * D;
        e.z = Math.min(SPINE_RANGE.z[1], Math.max(SPINE_RANGE.z[0], e.z / D)) * D;
        e.y = Math.min(SPINE_RANGE.y[1], Math.max(SPINE_RANGE.y[0], e.y / D)) * D;
        spine.quaternion.setFromEuler(e);
    }
    // the clavicles -> the upper arms
    for (const side of ['left', 'right']) {
        const sh = B(side + 'Shoulder'), ua = B(side + 'UpperArm');
        if (!sh || !ua) continue;
        note('rehome_' + side + 'Shoulder', sh.quaternion);
        ua.quaternion.premultiply(sh.quaternion);
        sh.quaternion.identity();
    }
    // the neck (pan) and the head (nod, roll)
    const neck = B('neck'), head = B('head');
    if (neck && head) {
        const R = neck.quaternion.clone().multiply(head.quaternion);
        twistAbout(R, [0, 1, 0], tw);
        let pan = 2 * Math.atan2(tw.y, tw.w);
        if (pan > Math.PI) pan -= 2 * Math.PI;
        pan = Math.min(HEAD_RANGE.pan[1], Math.max(HEAD_RANGE.pan[0], pan / D)) * D;
        neck.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), pan);
        const rest = neck.quaternion.clone().invert().multiply(R);
        e.setFromQuaternion(rest, 'XZY');
        e.x = Math.min(HEAD_RANGE.x[1], Math.max(HEAD_RANGE.x[0], e.x / D)) * D;
        e.z = Math.min(HEAD_RANGE.z[1], Math.max(HEAD_RANGE.z[0], e.z / D)) * D;
        e.y = 0;
        head.quaternion.setFromEuler(e);
    }
}

export function applyHardwareDOF(vrm, joints, stats) {
    const THREE = globalThis.THREE;
    const H = vrm.humanoid;
    const tw = new THREE.Quaternion(), e = new THREE.Euler(), clampDeg = (v, r) => Math.min(r[1], Math.max(r[0], v / D)) * D;
    for (const side of ['left', 'right']) {
        const m = side === 'left' ? 1 : -1;                         // the right side's roll and yaw mirror
        for (const j of joints) {
            const node = H.getNormalizedBoneNode(side + j.bone);
            if (!node) continue;
            const q = node.quaternion;
            const before = q.clone();
            if (j.type === 'hinge') {
                twistAbout(q, j.axis, tw);
                let ang = 2 * Math.atan2(tw.x * j.axis[0] + tw.y * j.axis[1] + tw.z * j.axis[2], tw.w);
                if (ang > Math.PI) ang -= 2 * Math.PI;
                q.setFromAxisAngle(new THREE.Vector3(...j.axis), clampDeg(ang, j.range));
            } else if (j.type === 'cardan') {
                twistAbout(q, j.noTwist, tw);
                q.multiply(tw.invert());                             // the swing alone (q = swing * twist)
                e.setFromQuaternion(q, 'XZY');
                e.x = clampDeg(e.x, j.range.x);
                e.z = clampDeg(e.z, m > 0 ? j.range.z : [-j.range.z[1], -j.range.z[0]]);
                // COUPLED (05.32, the ankle's roll, lower round 5): the roll within the range measured at this pitch,
                // in the left leg's signs (the right's roll mirrors), as the ball branch below
                if (j.coupled) {
                    const c = j.coupled, x = e.x / D;
                    const z = Math.min(lerpTable(c.x, c.zmax, x), Math.max(lerpTable(c.x, c.zmin, x), m * e.z / D));
                    e.z = m * z * D;
                }
                e.y = 0;
                q.setFromEuler(e);
            } else if (j.type === 'ball') {
                // each angle in its box, in the left leg's signs (the right's roll and yaw mirror); then, where the
                // joint has COUPLED limits (05.32), the roll within the range measured at this pitch and the yaw above
                // the floor measured at this roll: the box's corners clash
                e.setFromQuaternion(q, 'XZY');
                const r = j.range, c = j.coupled, cl = (v, rr) => Math.min(rr[1], Math.max(rr[0], v));
                const x = cl(e.x / D, r.x);
                let z = cl(m * e.z / D, r.z), y = cl(m * e.y / D, r.y);
                if (c) {
                    z = cl(z, [lerpTable(c.x, c.zmin, x), lerpTable(c.x, c.zmax, x)]);
                    y = Math.max(y, lerpTable(c.z, c.ymin, z));
                }
                e.x = x * D;
                e.z = m * z * D;
                e.y = m * y * D;
                q.setFromEuler(e);
            }
            if (stats) {
                const d = 2 * Math.acos(Math.min(1, Math.abs(before.dot(q)))) / D;
                const k = side + j.bone;
                stats[k] = Math.max(stats[k] || 0, d);
            }
        }
        // the hip's two stages, from the thigh as clamped above (THE HIP'S STAGES, below; after initLegDOF only)
        const hs = _legs.get(vrm)?.[side], thigh = hs && H.getNormalizedBoneNode(side + 'UpperLeg');
        if (thigh) hipSolve(thigh.quaternion, hs);
    }
}

// THE HIP'S STAGES (fix round 1, 10-29: DECISIONS.md 4, REVIEW_RUNTIME P3). The hip is a pitch -> roll -> yaw chain,
// all three axes through H (v2_hip): the BALL (leftHipPitch) turns on the cross axle about the robot's X; the ROLL
// FLANGE (leftHipSwing: the roll spindle, the upper thigh with its cup, seal and yaw lip) turns in the ball about the
// roll axle, the ball's own fore-aft axis (v2_leg_mech: the spindle along the sheet's Y; the stage bone's own Z); the
// YAW RING turns the lower thigh (leftUpperLeg, which carries the whole turn) against the upper about the thigh's own
// axis (the swing stage's Y, hip to knee). The file drives the two stages by VRM constraints: the pitch stage takes the
// twist about X of the thigh's WHOLE turn, the mechanism's pitch only while the yaw is 0 (at the coupled table's corner
// x -67.5 / z 44 it runs 3.83 past it at yaw +10, 15.27 at +40), and the swing stage aims at the knee by the shortest
// arc, which turns it off its axle wherever the pitch is off (13.1 deg at +40, where the seal went 0.19 mm into the
// pelvis: REVIEW_RUNTIME H1 / H3) and by up to 2.2 even with the pitch right (the thigh's axis leans 2.77 back off square
// to the axle, so no shortest arc runs about it). So, as the shoulder and the wrist, the stages are solved here, from
// the thigh as applyHardwareDOF clamped it: t, where its turn puts the thigh's axis d0; the roll b about the axle ZR that
// brings d0's cone to t's height along the pitch axis XP; then the pitch a about XP that turns it onto t. The yaw ring
// takes what is left, a pure turn about the thigh's axis by construction (the stages put d0 on t). Both stages are set
// directly; initLegDOF removes their constraints (the file keeps them, for runtimes without robot_dof). The axes are the
// stages' own, read at load (the pitch stage's X and Z, the swing stage's Y); each side is solved in its own frame, so
// nothing assumes the rig is mirrored. The thigh is not touched: only the parts the two stages carry move
const _legs = new WeakMap();

export function initLegDOF(vrm) {
    // at load, before anything poses the VRM: per side the stages' rest (local, and their parents' turns in the VRM's own
    // frame, where the normalized bones are axis-aligned at rest, whatever carries vrm.scene), their axes, and their VRM
    // constraints removed (applyHardwareDOF sets both stages every frame from then on). A side without the two stages
    // (null) keeps the file's constraints
    const THREE = globalThis.THREE;
    // (REVIEW_HIP P1, 10-29) a misplaced init is otherwise silent, and large: a second call would re-read the stages the
    // solve has posed as their rest (34 deg off over the review's walk), and a call after a posed vrm.update reads the
    // stages the constraints posed (25 deg off), while the log line still says 'removed'. So a second call keeps the
    // first record, and a raw hips or thigh turned off its rest (rawRestPose: vrm.update carries a pose into the raw
    // bones) is reported
    if (_legs.has(vrm)) {
        console.warn('[robot_dof] initLegDOF: called twice for this VRM: the first record is kept (the stages\' rests are read once, at load)');
        return _legs.get(vrm);
    }
    const hum = vrm.humanoid, posed = [];
    for (const n of ['hips', 'leftUpperLeg', 'rightUpperLeg']) {
        const node = hum?.getRawBoneNode?.(n), r = hum?.rawRestPose?.[n]?.rotation;
        if (!node || !r) continue;
        const q = new THREE.Quaternion(r[0], r[1], r[2], r[3]).invert().multiply(node.quaternion);
        const deg = 2 * Math.atan2(Math.hypot(q.x, q.y, q.z), Math.abs(q.w)) / D;
        if (deg > 1e-3) posed.push(`${n} ${deg.toFixed(3)}`);
    }
    if (posed.length) {
        console.warn(`[robot_dof] initLegDOF: the VRM was posed and updated before it (the raw ${posed.join(', ')} deg off its rest): ` +
            'the hip stages\' rests read now are wrong; call initLegDOF at load, before anything poses the VRM');
    }
    vrm.scene.updateMatrixWorld(true);
    const mgr = vrm.nodeConstraintManager, st = {};
    const S = vrm.scene.getWorldQuaternion(new THREE.Quaternion()).invert();
    const inVrm = (o) => S.clone().multiply(o.getWorldQuaternion(new THREE.Quaternion()));
    const axis = (q, x, y, z) => { const u = new THREE.Vector3(x, y, z).applyQuaternion(q); return vunit([u.x, u.y, u.z]); };
    for (const side of ['left', 'right']) {
        st[side] = null;
        const pitch = vrm.scene.getObjectByName(side + 'HipPitch') || null, swing = vrm.scene.getObjectByName(side + 'HipSwing') || null;
        if (!pitch || !swing || swing.parent !== pitch || !pitch.parent) continue;
        let removed = 0;
        if (mgr) {
            for (const c of [...mgr.constraints]) {
                if (c.destination !== pitch && c.destination !== swing) continue;
                if (mgr.deleteConstraint) mgr.deleteConstraint(c); else mgr.constraints.delete(c);
                removed++;
            }
        }
        const Pp = inVrm(pitch.parent), Ps = inVrm(pitch), Ws = inVrm(swing);
        const XP = axis(Ps, 1, 0, 0), ZR = axis(Ps, 0, 0, 1), d0 = axis(Ws, 0, 1, 0);
        // (records for the checks: the thigh's own axis at rest (hip to knee) against d0, 0 when the file rests at the
        // mechanism's zero; d0's lean off square to the axle, 2.77 in the v2 file)
        const up = vrm.humanoid?.getRawBoneNode?.(side + 'UpperLeg'), lo = vrm.humanoid?.getRawBoneNode?.(side + 'LowerLeg');
        let aimDeg = null;
        if (up && lo) {
            const k = lo.getWorldPosition(new THREE.Vector3()).sub(up.getWorldPosition(new THREE.Vector3())).applyQuaternion(S);
            aimDeg = Math.atan2(Math.hypot(...vcross([k.x, k.y, k.z], d0)), vdot([k.x, k.y, k.z], d0)) / D;
        }
        st[side] = { pitch, swing, removed, XP, ZR, d0, A: vdot(XP, d0), B: vdot(XP, vcross(ZR, d0)), aimDeg,
                     leanDeg: Math.asin(Math.min(1, Math.abs(vdot(ZR, d0)))) / D,
                     Lp: pitch.quaternion.clone(), Pp, PpI: Pp.clone().invert(), Ls: swing.quaternion.clone(), Ps, PsI: Ps.clone().invert(),
                     a: 0, b: 0, c: 0 };
    }
    _legs.set(vrm, st);
    return st;
}

// one side's stages from the thigh's turn q (normalized: the VRM's frame; s: initLegDOF's record). t = q d0. The roll b:
// XP . R(ZR, b) d0 = A cos b + B sin b (A = XP . d0, B = XP . (ZR x d0); its amplitude cos 2.77 deg) must equal XP . t,
// whose two roots are atan2(B, A) +- acos: the one nearer 0, the rest (the other turns the thigh over the top; the two
// meet only with the thigh's axis 2.77 deg from the pitch axis, 87 of abduction or 93 of adduction, far past the stops;
// past that reach, the cone's nearest). Then the pitch a: the turn about XP from R(ZR, b) d0's trace across XP to t's
// (undefined only with t along XP: the last frame's kept). The yaw ring's turn c is what is left of q, a turn about d0
// wherever the cone reaches t (s.a, s.b and s.c, rad, kept for the checks)
function hipSolve(q, s) {
    const THREE = globalThis.THREE;
    const v = new THREE.Vector3(), ax = (u) => v.set(u[0], u[1], u[2]);
    const tv = new THREE.Vector3(s.d0[0], s.d0[1], s.d0[2]).applyQuaternion(q), t = [tv.x, tv.y, tv.z];
    const ph = Math.atan2(s.B, s.A), h = Math.acos(Math.max(-1, Math.min(1, vdot(s.XP, t) / Math.hypot(s.A, s.B))));
    const b1 = wrapPi(ph + h), b2 = wrapPi(ph - h), b = Math.abs(b1) <= Math.abs(b2) ? b1 : b2;
    const off = (w) => { const k = vdot(w, s.XP); return [w[0] - k * s.XP[0], w[1] - k * s.XP[1], w[2] - k * s.XP[2]]; };
    const p1 = off(vrot(s.d0, s.ZR, b)), p2 = off(t);
    const a = Math.hypot(...p1) > 1e-9 && Math.hypot(...p2) > 1e-9 ? Math.atan2(vdot(vcross(p1, p2), s.XP), vdot(p1, p2)) : s.a;
    const Ra = new THREE.Quaternion().setFromAxisAngle(ax(s.XP), a), Rb = new THREE.Quaternion().setFromAxisAngle(ax(s.ZR), b);
    const y = Ra.clone().multiply(Rb).invert().multiply(q);
    s.a = a; s.b = b; s.c = wrapPi(2 * Math.atan2(y.x * s.d0[0] + y.y * s.d0[1] + y.z * s.d0[2], y.w));
    // the pitch stage: a about XP in its parent's (the hips') rest frame; the swing stage: b about the axle in the pitch
    // stage's rest frame (it rides the ball, so the axle is carried)
    s.pitch.quaternion.copy(s.PpI).multiply(Ra).multiply(s.Pp).multiply(s.Lp);
    s.swing.quaternion.copy(s.PsI).multiply(Rb).multiply(s.Ps).multiply(s.Ls);
}

// THE ARMS (v2, 10-17: work/v2/bones_arm.json and v2_arm.bones()'s docstring). The shoulder is a PITCH stage about the
// robot's X (the pin in the torso's socket) carrying a ROLL stage about an axle square to X and to the hanging arm (RY,
// its back end 3.95 deg low), then a TWIST ring about the upper arm; the elbow a pin (flexion about -XE: the forearm
// forward); the wrist a roll about the forearm (FA). The VRM's rest is the T-pose, the arm chain turned by the shortest
// arc from the hanging arm U to X (a pure roll of 82.8 deg about the axle), so there the pitch pin runs ALONG the arm:
// the pitch helper's VRM roll constraint (the twist of the arm's turn about X) is right in the frontal plane only, and
// a forward swing would turn no fork while the swing helper's aim turned the axle ~30 deg off the fork's bores. So the
// shoulder is solved here each frame: from the arm's direction d, the pitch phi that turns the axle square to d (two
// branches 180 apart: the one the stops allow, nearest the last frame; held within 10 deg of the T-pose's line, where
// the axle is undefined; turning at most 360 deg/s, so no pop where the arm leaves that line), and the roll from the
// hanging arm to d about the pitched axle. The arm is put on what the stages reach (pitch -150..60, roll -0.5..110:
// 2 deg inside the torso flank, the hard stop at -2), its twist at the ring clamped (+-90), the pitch helper set to phi
// itself (initArmDOF removes its roll constraint), and the swing helper's aim constraint is then exact. The elbow keeps its flexion only (0..135; the forearm's twist about its own axis goes to the wrist roll, 05.12).
// THE WRIST (fix round 1, 10-29: L3-RIG F5 = MECH-D4) is three stages in series on the forearm, solved here as the
// shoulder is: the ROLL stage (WristRoll, the yoke, about the forearm's axis EL), the DRUM on it (WristFlex, flexion
// about EA) and the hand's chassis on the DEVIATION pin through the drum (about ED = EL x EA). The file's two roll
// constraints (WristRoll Y <- Hand, WristFlex X <- Hand) each take the twist of the hand's WHOLE turn about their own
// axis, which is exact for roll + flexion only, and nothing clamped the deviation: in the walk the left chassis turned
// 24.7 about its pin (the tongue's shoulders meet the slot's end walls from 12.3) and 14.3 off it, 4.4 mm into the drum
// (L3-RIG J10, the F5 / MECH-D4 skeptics). So the hand's turn against the forearm is split in the mechanism's order,
// q = R(EL, roll) R(EA, flexion) R(ED, deviation), each clamped at its stop (+-90 / +-70 / +-12), the hand recomposed
// from the clamped three and the two stages set from them (initArmDOF removes their constraints). The axes are the
// stages' own, read at load (the roll stage's Y, the drum's X: what the file's constraints turn them about), so a
// runtime without robot_dof turns the same stages about the same axes. Body limits from the clash sweeps (the arm
// delivery, 10-17): hanging with the elbow under ~15 deg the forearm meets the hip dome from -1.6 deg of turn-in and
// from about -55 deg of twist; 20 deg of flexion or 30 of abduction clears it (a torso lean moves the dome against the
// arm: these hold for the spine near upright). The right arm mirrors the left: it is solved in the left's frame.
// THE ELBOW AT THE VRM's REST (fix round 1, C): the exporter folds the forearm about its pin, not by an arc (the built
// forearm lies 0.6 deg off square to the pin, so it rests 0.6 off X), which leaves the rest elbow at HARDWARE +3.15
// (the sheet's 0 is the hard stop's 0). The joints file's hinges.leftLowerArm records it (axis = XF, deg = the hardware
// range, flex_at_rest, forearm_axis = the T-posed forearm): initArmDOF(vrm, hinges) reads it, so the clamp is the
// hardware [0, 135] (normalized [-3.15, 131.85]: at 135 the yoke's bridge sits on the flex stop's buffer, MECH-D2) and
// the body limits read the hardware flexion they were measured at. The forearm's roll axis is the wrist's roll stage's
// own (EL, above); the record's forearm_axis stands in for it only on a VRM without the wrist's stages (the two lie
// 0.018 deg apart in the rehearsal's file). Without the record (an older VRM; the tests' stand-in rigs) ARM's constants
// stand: [0, 135] from the rest, FA carried by the upper arm only; initArmDOF warns when given hinges without it.
const B2T = (v) => [v[0], v[2], -v[1]];          // Blender (Z up, facing -Y, left +X) -> VRM / three (Y up, facing +Z)
const vdot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const vcross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const vunit = (a) => { const n = Math.hypot(a[0], a[1], a[2]); return [a[0] / n, a[1] / n, a[2] / n]; };
const vrot = (v, k, t) => {                      // v turned by t about the unit axis k (Rodrigues)
    const c = Math.cos(t), s = Math.sin(t), kv = vcross(k, v), kd = vdot(k, v) * (1 - c);
    return [v[0] * c + kv[0] * s + k[0] * kd, v[1] * c + kv[1] * s + k[1] * kd, v[2] * c + kv[2] * s + k[2] * kd];
};
const rotX = (v, a) => [v[0], v[1] * Math.cos(a) - v[2] * Math.sin(a), v[1] * Math.sin(a) + v[2] * Math.cos(a)];
const smooth = (e0, e1, x) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
const wrapPi = (a) => a - 2 * Math.PI * Math.floor((a + Math.PI) / (2 * Math.PI));

export const ARM = (() => {
    // bones_arm.json (Blender, mm): the shoulder, elbow and wrist centres; the roll axle square to X and the hanging arm
    // (v2_arm.RY: bones_arm.json's roll_axle.direction 0, 0.99763, -0.06887, rounded there)
    const S = [165.0, -28.0, 1337.0], E = [199.0, -46.5, 1069.0], W = [234.5, -50.0, 811.0];
    const Ub = vunit([E[0] - S[0], E[1] - S[1], E[2] - S[2]]), FAb = vunit([W[0] - E[0], W[1] - E[1], W[2] - E[2]]);
    const RYb = vunit(vcross([1, 0, 0], Ub));
    const XEb = vunit(vcross(Ub, [0, 1, 0]));                        // v2_arm.XE: lateral, square to the upper arm
    const U = B2T(Ub), RY = vunit(B2T(RYb)), X = [1, 0, 0], nRY = [-RY[0], -RY[1], -RY[2]];
    // the export's T-pose: the shortest arc U -> X, about -RY; the elbow pin and the forearm turn with it (the forearm
    // then folds about the pin: the joints file's hinges.leftLowerArm, read by initArmDOF; these two are the fallback)
    const k = vunit(vcross(U, X)), t = Math.acos(Math.min(1, vdot(U, X)));
    return {
        U, RY, nRY,
        XF: vrot(B2T(XEb.map((c) => -c)), k, t),                     // flexion's axis in the T-posed upper arm
        FA: vrot(B2T(FAb), k, t),                                    // the forearm's roll axis, the upper arm's turn only
        rollT: Math.atan2(vdot(vcross(U, X), nRY), vdot(U, X)),     // the T-pose's roll (rad, 82.8 deg)
        // deg. The turn-in's HARD stop is -2 (the blocks on the fork's buffers), but the upper arm's cover meets the
        // torso's flank from between -2.5 and -3 (the arm's verifier, 10-17): the runtime stops 2 inside, at -0.5
        pitch: [-150, 60], roll: [-0.5, 110], twist: [-90, 90], flex: [0, 135], wristRoll: [-90, 90],
        // the wrist's other two stages (work/v2/bones_hand.json limits.leftHand): flexion +-70 about EA (clear at 72
        // with full deviation; the chassis meets the yoke at ~80 with none), deviation +-12 about the pin (the tongue's
        // shoulders on the slot's end walls: first touch at 12.3, 0.13 mm at 13; the MECH-D4 skeptic's H1)
        wristFlex: [-70, 70], wristDev: [-12, 12],
        pitchRate: 360,                                              // deg/s, the pitch stage's fastest turn
        // the body limits (deg): the hanging, straight arm clears the hip dome by 1.6 deg of turn-in, so it keeps its
        // rest roll (0) until the elbow passes 12..20 deg; its twist ends at -52 (3 inside -55) until 12..20 deg of
        // flexion or 20..30 of roll
        hang: { rollMin: 0, twistMin: -52, flex: [12, 20], roll: [20, 30] },
    };
})();

const _arms = new WeakMap();

// THE HANDS' CLEARANCE FROM THE THIGHS (10-19): stock clips are a human's, and our thigh shells are wider than a human
// thigh, so a hanging hand swinging past one (the walk) put the thumb into it (Skye's frame; with the hand pass off as
// well, so not the thumb's solve). Before the arm's stages are solved, each upper arm that hangs is turned out about the
// body's front axis by up to `deg`: all of it when the arm hangs straight down, none once it is raised 60 deg from
// there (the hand-to-heart and reaching clips keep their targets). 8 cleared the walk in the engine test
export function applyArmClearance(vrm, deg = 8) {
    const THREE = globalThis.THREE;
    const H = vrm.humanoid, z = new THREE.Vector3(0, 0, 1), dir = new THREE.Vector3(), q = new THREE.Quaternion();
    for (const [side, sg] of [['left', 1], ['right', -1]]) {
        const ua = H.getNormalizedBoneNode(side + 'UpperArm');
        if (!ua) continue;
        dir.set(sg, 0, 0).applyQuaternion(ua.quaternion);          // the arm (T-pose +-X) in its parent's frame
        const w = smooth(0.5, 0.95, -dir.y);                         // -dir.y: 1 hanging straight down
        if (w > 0) ua.quaternion.premultiply(q.setFromAxisAngle(z, sg * deg * D * w));
    }
}

export function initArmDOF(vrm, hinges) {
    // at load, before anything poses the VRM: the pitch helpers' rest (local, and their parents' world turn) and their
    // VRM roll constraints removed (the solve sets them; a constraint left in place would overwrite them in update).
    // hinges: the exporter's joints file 'hinges' (as initHandDOF takes them); its leftLowerArm record sets the elbow
    // (THE ELBOW AT THE VRM's REST, above); without it ARM's constants stand
    const THREE = globalThis.THREE;
    vrm.scene.updateMatrixWorld(true);
    const st = {}, mgr = vrm.nodeConstraintManager;
    for (const side of ['left', 'right']) {
        const helper = vrm.scene.getObjectByName(side + 'ShoulderPitch') || null;
        let removed = 0;
        if (helper && mgr) {
            for (const c of [...mgr.constraints]) {
                if (c.destination !== helper) continue;
                if (mgr.deleteConstraint) mgr.deleteConstraint(c); else mgr.constraints.delete(c);
                removed++;
            }
        }
        const P = helper ? helper.parent.getWorldQuaternion(new THREE.Quaternion()) : null;
        st[side] = { phi: 0, helper, removed, Lrest: helper ? helper.quaternion.clone() : null, P, Pinv: P ? P.clone().invert() : null };
        st[side].wrist = initWrist(vrm, side);
    }
    // the elbow (the left's frame; the right is solved in it): its pin, its clamp in normalized terms (the hardware
    // range less the flexion at the rest), that flexion (deg: the body limits read hardware) and the forearm's roll axis;
    // `record` says which (a caller prints it: a wrong argument falls back without an error otherwise)
    const el = hinges && hinges.leftLowerArm;
    if (hinges && !el) {
        console.warn("[robot_dof] initArmDOF: hinges without a leftLowerArm record: the elbow keeps ARM's constants " +
            '(its clamp [0, 135] from the rest, FA the upper arm\'s turn only): pass the joints file\'s hinges of a VRM exported with it');
    }
    st.elbow = el ? { record: true, XF: vunit(el.axis), FA: vunit(el.forearm_axis || ARM.FA), rest: el.flex_at_rest,
                      flex: [el.deg[0] - el.flex_at_rest, el.deg[1] - el.flex_at_rest] }
                  : { record: false, XF: ARM.XF, FA: ARM.FA, rest: 0, flex: ARM.flex };
    _arms.set(vrm, st);
    return st;
}

// THE WRIST's stages at load (fix round 1): the roll stage (WristRoll, on the forearm) and the drum (WristFlex, on the
// roll stage); their VRM roll constraints removed as the pitch helper's (applyArmDOF sets both each frame); their rest
// (local, and the parent's turn in the VRM's own frame, where the normalized bones are axis-aligned at rest, whatever
// carries vrm.scene) and their own axes, in the left's frame (the right's mirrored: a turn's axis (x, -y, -z)): EL the
// roll stage's Y, EA the drum's X (squared to EL: 0.019 deg off square in the delivered file), ED = EL x EA the deviation pin the
// drum carries (the hand's -Z: the pin from its back plate is that axis to 2e-5, the F5 skeptic). A VRM without the two
// stages keeps the roll-only clamp (applyArmDOF)
function initWrist(vrm, side) {
    const THREE = globalThis.THREE;
    const roll = vrm.scene.getObjectByName(side + 'WristRoll') || null, flex = vrm.scene.getObjectByName(side + 'WristFlex') || null;
    if (!roll || !flex || flex.parent !== roll || !roll.parent) return null;
    const mgr = vrm.nodeConstraintManager;
    let removed = 0;
    if (mgr) {
        for (const c of [...mgr.constraints]) {
            if (c.destination !== roll && c.destination !== flex) continue;
            if (mgr.deleteConstraint) mgr.deleteConstraint(c); else mgr.constraints.delete(c);
            removed++;
        }
    }
    const S = vrm.scene.getWorldQuaternion(new THREE.Quaternion()).invert();
    const inVrm = (o) => S.clone().multiply(o.getWorldQuaternion(new THREE.Quaternion()));
    const m = side === 'left' ? 1 : -1, mir = (u) => (m > 0 ? [u.x, u.y, u.z] : [u.x, -u.y, -u.z]);
    const Pr = inVrm(roll.parent), Pd = inVrm(roll), Wd = inVrm(flex);
    const EL = vunit(mir(new THREE.Vector3(0, 1, 0).applyQuaternion(Pd)));
    const ea = mir(new THREE.Vector3(1, 0, 0).applyQuaternion(Wd)), k = vdot(ea, EL);
    const EA = vunit([ea[0] - k * EL[0], ea[1] - k * EL[1], ea[2] - k * EL[2]]);
    const ED = vcross(EL, EA);
    // the stages' basis (x EL, y EA, z ED): there the mechanism's q = R(EL, a) R(EA, b) R(ED, c) is Euler 'XYZ' (a, b, c)
    const B = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(
        new THREE.Vector3(...EL), new THREE.Vector3(...EA), new THREE.Vector3(...ED)));
    // (a record for the checks: the hand's rest frame against the drum's, 0 when the wrist rests at its mechanism zero;
    // the delivered file: 0.004 deg, the F5 skeptic)
    const hand = vrm.humanoid?.getRawBoneNode?.(side + 'Hand');
    const hd = hand ? Wd.clone().invert().multiply(inVrm(hand)) : null;
    const restDeg = hd ? 2 * Math.atan2(Math.hypot(hd.x, hd.y, hd.z), Math.abs(hd.w)) / D : null;
    return { roll, flex, removed, EL, EA, ED, B, Bi: B.clone().invert(), squareDeg: Math.asin(Math.min(1, Math.abs(k))) / D, restDeg,
             Lr: roll.quaternion.clone(), Pr, PrI: Pr.clone().invert(), Ld: flex.quaternion.clone(), Pd, PdI: Pd.clone().invert(),
             a: 0, b: 0, c: 0, asked: [0, 0, 0] };
}

// the hand's turn q against the forearm (the left's frame) split in the mechanism's order and clamped at the stops: in
// the stages' basis q is Euler 'XYZ' (roll a, flexion b, deviation c); of its two branches, (a, b, c) and (a + 180,
// 180 - b, c + 180), the one whose clamped turn lies nearest q (the second where q is nearer a flexion past 90), the
// last frame's on a tie. q is set to the clamped turn; W.a / W.b / W.c keep the stages' angles (rad), W.asked the split's
function wristSolve(q, W) {
    const THREE = globalThis.THREE;
    const e = new THREE.Euler(), qb = W.Bi.clone().multiply(q).multiply(W.B), qc = new THREE.Quaternion();
    e.setFromQuaternion(qb, 'XYZ');
    const lim = (x, r) => Math.min(r[1] * D, Math.max(r[0] * D, x));
    let best = null;
    for (const [a0, b0, c0] of [[e.x, e.y, e.z], [wrapPi(e.x + Math.PI), wrapPi(Math.PI - e.y), wrapPi(e.z + Math.PI)]]) {
        const a = lim(a0, ARM.wristRoll), b = lim(b0, ARM.wristFlex), c = lim(c0, ARM.wristDev);
        qc.setFromEuler(e.set(a, b, c, 'XYZ'));
        const err = 1 - Math.abs(qc.dot(qb)), tie = Math.abs(a - W.a) + Math.abs(b - W.b) + Math.abs(c - W.c);
        if (!best || err < best.err - 1e-12 || (err < best.err + 1e-12 && tie < best.tie)) best = { a, b, c, err, tie, asked: [a0, b0, c0] };
    }
    W.a = best.a; W.b = best.b; W.c = best.c; W.asked = best.asked;
    q.setFromEuler(e.set(best.a, best.b, best.c, 'XYZ')).premultiply(W.B).multiply(W.Bi);
    return best;
}

// clearance: applyArmClearance's turn-out (deg), applied first; it is part of the contract, not the caller's choice
// (the verifier, 10-19: without it the hanging forearm meets the hip dome at a side bend of 8 deg, inside SPINE_RANGE's
// 15). 0 only for tests of the arm's stages alone
export function applyArmDOF(vrm, stats, dt, clearance = 8) {
    const THREE = globalThis.THREE;
    if (clearance) applyArmClearance(vrm, clearance);
    const H = vrm.humanoid, A = ARM;
    const st = _arms.get(vrm) || initArmDOF(vrm), elbow = st.elbow;
    const q = new THREE.Quaternion(), r = new THREE.Quaternion(), tw = new THREE.Quaternion(), qa = new THREE.Quaternion();
    const qs = new THREE.Quaternion();
    const v = new THREE.Vector3(), ax = (a) => v.set(a[0], a[1], a[2]);
    // the right side in the left's frame and back (the x -> -x mirror conjugates a turn: its axis (x, -y, -z))
    const mirror = (src, m, out) => (m > 0 ? out.copy(src) : out.set(src.x, -src.y, -src.z, src.w));
    const angleAbout = (qq, a) => {                                 // the twist (rad) of qq about the unit axis a
        twistAbout(qq, a, tw);
        return wrapPi(2 * Math.atan2(tw.x * a[0] + tw.y * a[1] + tw.z * a[2], tw.w));
    };
    const clampD = (x, lo, hi) => Math.min(hi, Math.max(lo, x / D)) * D;
    const note = (k, before, after) => {
        if (stats) stats[k] = Math.max(stats[k] || 0, 2 * Math.acos(Math.min(1, Math.abs(before.dot(after)))) / D);
    };
    const rollFor = (phi, d) => {                                   // the roll (rad) to d's trace on the pitched plane
        const d0 = rotX(d, -phi), k = vdot(d0, A.RY);
        const p = vunit([d0[0] - k * A.RY[0], d0[1] - k * A.RY[1], d0[2] - k * A.RY[2]]);
        return Math.atan2(vdot(vcross(A.U, p), A.nRY), vdot(A.U, p));
    };
    for (const side of ['left', 'right']) {
        const m = side === 'left' ? 1 : -1, s = st[side], W = s.wrist || null;
        const ua = H.getNormalizedBoneNode(side + 'UpperArm'), la = H.getNormalizedBoneNode(side + 'LowerArm');
        const hand = H.getNormalizedBoneNode(side + 'Hand');
        if (!ua || !la) continue;
        // 1. the elbow: its flexion only, clamped at its hardware stops (elbow.flex: normalized, from the rest's
        // flexion); the forearm's twist about its own axis goes to the wrist roll (the hand). That axis is the roll
        // stage's own (EL, read at load) where the VRM has the wrist's stages, else the elbow's FA (the record's
        // forearm_axis, or ARM.FA without it)
        const FAx = W ? W.EL : elbow.FA;
        mirror(la.quaternion, m, q);
        const before = q.clone();
        const flex = clampD(angleAbout(q, elbow.XF), elbow.flex[0], elbow.flex[1]);
        qa.setFromAxisAngle(ax(elbow.XF), flex);
        const pron = angleAbout(qa.clone().invert().multiply(q), FAx);
        mirror(qa, m, la.quaternion);
        note(side + 'LowerArm', before, qa);
        if (hand) {
            mirror(hand.quaternion, m, q);
            const hb = q.clone();
            q.premultiply(r.setFromAxisAngle(ax(FAx), pron));
            if (W) {
                // the wrist's three stages: the split in the mechanism's order, clamped, the hand recomposed (wristSolve)
                wristSolve(q, W);
            } else {
                const roll = angleAbout(q, elbow.FA);                // (no stages: the roll clamped, the swing kept)
                q.multiply(r.setFromAxisAngle(ax(elbow.FA), -roll)).multiply(r.setFromAxisAngle(ax(elbow.FA), clampD(roll, A.wristRoll[0], A.wristRoll[1])));
            }
            mirror(q, m, hand.quaternion);
            note(side + 'Hand', hb, q);
            if (W) {
                // the roll stage: a about EL in the forearm's rest frame; the drum: b about EA in the roll stage's (it rides
                // the roll stage, so its axis is carried); the hand then turns c about the pin against the drum
                mirror(r.setFromAxisAngle(ax(W.EL), W.a), m, qs);
                W.roll.quaternion.copy(W.PrI).multiply(qs).multiply(W.Pr).multiply(W.Lr);
                mirror(r.setFromAxisAngle(ax(W.EA), W.b), m, qs);
                W.flex.quaternion.copy(W.PdI).multiply(qs).multiply(W.Pd).multiply(W.Ld);
            }
        }
        // 2. the shoulder: the pitch that turns the axle square to the arm, the roll, the twist at the ring
        mirror(ua.quaternion, m, q);
        const qb = q.clone();
        const dv = new THREE.Vector3(1, 0, 0).applyQuaternion(q), d = [dv.x, dv.y, dv.z];
        const fd = flex / D + elbow.rest;                           // (hardware: the body limits' sweeps were the sheet's)
        const rMin = (A.hang.rollMin + (A.roll[0] - A.hang.rollMin) * smooth(A.hang.flex[0], A.hang.flex[1], fd)) * D;
        const rMax = A.roll[1] * D, pLo = A.pitch[0] * D, pHi = A.pitch[1] * D;
        const base = Math.atan2(d[2], d[1]) - Math.atan2(A.RY[2], A.RY[1]);
        let best = null;
        for (const c of [wrapPi(base + Math.PI / 2), wrapPi(base - Math.PI / 2)]) {
            const p = Math.min(pHi, Math.max(pLo, c)), rr = rollFor(p, d);
            const cost = Math.abs(p - c) + Math.max(0, rMin - rr, rr - rMax) + 1e-3 * Math.abs(wrapPi(p - s.phi));
            if (!best || cost < best.cost) best = { p, cost };
        }
        // (within 10 deg of the T-pose's line the axle is undefined: the pitch holds; and it turns at most A.pitchRate,
        // so where the arm leaves that line forward or back, the stage swings its ~86 deg in a quarter second, no pop)
        const target = Math.abs(d[0]) > Math.cos(10 * D) ? s.phi : best.p, step = A.pitchRate * D * (dt || 1 / 30);
        const phi = Math.min(pHi, Math.max(pLo, s.phi + Math.min(step, Math.max(-step, wrapPi(target - s.phi)))));
        s.phi = phi;
        const rho = Math.min(rMax, Math.max(rMin, rollFor(phi, d)));
        const swing = new THREE.Quaternion().setFromAxisAngle(ax([1, 0, 0]), phi)
            .multiply(r.setFromAxisAngle(ax(A.nRY), rho - A.rollT));
        const clear = Math.max(smooth(A.hang.flex[0], A.hang.flex[1], fd), smooth(A.hang.roll[0], A.hang.roll[1], rho / D));
        const tMin = A.hang.twistMin + (A.twist[0] - A.hang.twistMin) * clear;
        const tau = clampD(angleAbout(swing.clone().invert().multiply(q), [1, 0, 0]), tMin, A.twist[1]);
        q.copy(swing).multiply(r.setFromAxisAngle(ax([1, 0, 0]), tau));
        mirror(q, m, ua.quaternion);
        note(side + 'UpperArm', qb, q);
        // 3. the pitch helper: phi about the torso's X, in its parent's rest frame (the mirror leaves a turn about X)
        if (s.helper) s.helper.quaternion.copy(s.Pinv).multiply(r.setFromAxisAngle(ax([1, 0, 0]), phi)).multiply(s.P).multiply(s.Lrest);
    }
}

// THE HANDS (v2, 10-17: work/v2/bones_hand.json; the exporter's joints file 'hinges', written by v2_rig_export.
// hinge_table from the T-posed rest: each pin's axis in the glTF frame, its range, its flexion at that rest). Every
// finger joint and the thumb's MCP and IP are single pins: a clip's splay or twist there would turn a link off its pin,
// so each keeps its twist about the pin only, clamped to its range from its flexion at rest. The thumb's metacarpal
// sits on two stages: the ROTOR turning in the stator about the thumb's rest axis (opposition, 0..60), carrying the
// CMC PIN square to it (flexion, 0..93). The exported rotor constraint copies the metacarpal's Y turn, which is exact only
// while the CMC is straight (the hand verifier, 10-17: 45.7 deg off with a shortest-arc rest). So, as the shoulder: from
// the clip's thumb direction d, the flexion beta that puts the metacarpal at d's angle from the rotor axis, the rotor
// alpha that turns it round onto d (where d runs along the rotor axis alpha is undefined: the clip's twist about it is
// taken instead, blended in over 4..12 deg); the metacarpal is set to rotor(alpha) * pin(beta), the rotor helper to
// alpha (initHandDOF removes its constraint). The right hand mirrors the left: solved in the left's frame.
//   initHandDOF(vrm, joints.hinges) once at load; applyHandDOF(vrm, stats) each frame after applyArmDOF
const FINGER_PINS = ['Index', 'Middle', 'Ring', 'Little'].flatMap((f) => ['Proximal', 'Intermediate', 'Distal'].map((s) => f + s))
    .concat(['ThumbProximal', 'ThumbDistal']);
const _hands = new WeakMap();

export function initHandDOF(vrm, hinges) {
    const THREE = globalThis.THREE;
    vrm.scene.updateMatrixWorld(true);
    const H = vrm.humanoid, mgr = vrm.nodeConstraintManager, st = { hinges, side: {} };
    const meta = hinges.leftThumbMetacarpal, rot = hinges.leftThumbRotor;
    for (const side of ['left', 'right']) {
        const m = side === 'left' ? 1 : -1;
        const helper = vrm.scene.getObjectByName(side + 'ThumbRotor') || null;
        let removed = 0;
        if (helper && mgr) {
            for (const c of [...mgr.constraints]) {
                if (c.destination !== helper) continue;
                if (mgr.deleteConstraint) mgr.deleteConstraint(c); else mgr.constraints.delete(c);
                removed++;
            }
        }
        // the metacarpal's rest direction (normalized bones are world-aligned at rest), in the left's frame
        const mc = H.getNormalizedBoneNode(side + 'ThumbMetacarpal'), px = H.getNormalizedBoneNode(side + 'ThumbProximal');
        let m0 = rot ? rot.axis : [1, 0, 0];
        if (mc && px) {
            const a = mc.getWorldPosition(new THREE.Vector3()), b = px.getWorldPosition(new THREE.Vector3());
            m0 = vunit([m * (b.x - a.x), b.y - a.y, b.z - a.z]);
        }
        // the thumb's proximal segment at rest (proximal -> distal), the direction its MCP and IP pins carry
        const di = H.getNormalizedBoneNode(side + 'ThumbDistal');
        let s0 = m0;
        if (px && di) {
            const b = px.getWorldPosition(new THREE.Vector3()), c = di.getWorldPosition(new THREE.Vector3());
            s0 = vunit([m * (c.x - b.x), c.y - b.y, c.z - b.z]);
        }
        const P = helper ? helper.parent.getWorldQuaternion(new THREE.Quaternion()) : null;
        st.side[side] = { helper, removed, m0, s0, alpha: 0, beta: 0, Lrest: helper ? helper.quaternion.clone() : null, P,
                          Pinv: P ? P.clone().invert() : null };
    }
    st.ok = !!(meta && rot);
    _hands.set(vrm, st);
    return st;
}

// the thumb solve's last numbers per side (deg): alpha, beta, the direction's azimuth aDir, the clip's twist aTw, w, d
export function handDebug(vrm) {
    const st = _hands.get(vrm);
    return st ? { left: st.side.left.dbg, right: st.side.right.dbg } : null;
}

export function applyHandDOF(vrm, stats) {
    const THREE = globalThis.THREE;
    const st = _hands.get(vrm);
    if (!st) return;
    const H = vrm.humanoid, T = st.hinges;
    const q = new THREE.Quaternion(), r = new THREE.Quaternion(), tw = new THREE.Quaternion(), v = new THREE.Vector3();
    const ax = (a) => v.set(a[0], a[1], a[2]);
    const mirror = (src, m, out) => (m > 0 ? out.copy(src) : out.set(src.x, -src.y, -src.z, src.w));
    const angleAbout = (qq, a) => {
        twistAbout(qq, a, tw);
        return wrapPi(2 * Math.atan2(tw.x * a[0] + tw.y * a[1] + tw.z * a[2], tw.w));
    };
    // a turn's range about its pin, from its flexion at rest (deg) -> rad
    const range = (j) => [(j.deg[0] - j.flex_at_rest) * D, (j.deg[1] - j.flex_at_rest) * D];
    const clampR = (x, rr) => Math.min(rr[1], Math.max(rr[0], x));
    const note = (k, before, after) => {
        if (stats) stats[k] = Math.max(stats[k] || 0, 2 * Math.acos(Math.min(1, Math.abs(before.dot(after)))) / D);
    };
    for (const side of ['left', 'right']) {
        const m = side === 'left' ? 1 : -1, s = st.side[side];
        // 1. the pins: the twist about each pin only, clamped (the thumb's MCP and IP after its metacarpal: 2b)
        const turned = {};
        for (const b of FINGER_PINS) {
            if (st.ok && b.startsWith('Thumb')) continue;
            const j = T['left' + b], node = H.getNormalizedBoneNode(side + b);
            if (!j || !node) continue;
            mirror(node.quaternion, m, q);
            const before = q.clone();
            turned[b] = { j, node, before, g: clampR(angleAbout(q, j.axis), range(j)) };
            q.setFromAxisAngle(ax(j.axis), turned[b].g);
            mirror(q, m, node.quaternion);
            note(side + b, before, q);
        }
        // the little finger's MCP and PIP share one limit (the hand round, 10-19: its proximal cover meets the
        // intermediate's knuckle tongue past 93 deg together): any excess comes off both pins equally
        const lp = turned.LittleProximal, li = turned.LittleIntermediate;
        if (lp && li) {
            const over = (lp.g / D + lp.j.flex_at_rest) + (li.g / D + li.j.flex_at_rest) - 93;
            if (over > 0) {
                const room = (t) => Math.max(0, t.g - range(t.j)[0]), tot = over * D;     // (one at its stop: the other)
                let d1 = Math.min(0.5 * tot, room(lp));
                const d2 = Math.min(tot - d1, room(li));
                d1 = Math.min(tot - d2, room(lp));
                lp.g -= d1; li.g -= d2;
                for (const t of [lp, li]) {
                    q.setFromAxisAngle(ax(t.j.axis), t.g);
                    mirror(q, m, t.node.quaternion);
                    note(side + (t === lp ? 'LittleProximal' : 'LittleIntermediate'), t.before, q);
                }
            }
        }
        // 2. the thumb's metacarpal: rotor alpha about Yr, then the CMC pin beta about P0 (square to Yr)
        const mc = H.getNormalizedBoneNode(side + 'ThumbMetacarpal');
        if (!st.ok || !mc) continue;
        const Yr = vunit(T.leftThumbRotor.axis), m0 = s.m0;
        const P0 = vunit(vcross(vcross(Yr, T.leftThumbMetacarpal.axis), Yr));     // (square to Yr exactly: the file rounds)
        mirror(mc.quaternion, m, q);
        const before = q.clone(), qmClip = q.clone();
        const dv = new THREE.Vector3(m0[0], m0[1], m0[2]).applyQuaternion(q), d = [dv.x, dv.y, dv.z];
        // beta: Yr . pin(beta) m0 = A cos(beta) + Bs sin(beta) = Yr . d; of the two roots, the one in range nearest the last
        const A = vdot(Yr, m0), Bs = vdot(Yr, vcross(P0, m0)), Rn = Math.hypot(A, Bs), ph = Math.atan2(Bs, A);
        const bR = range(T.leftThumbMetacarpal), aR = range(T.leftThumbRotor);
        const c = Math.acos(Math.max(-1, Math.min(1, vdot(Yr, d) / Math.max(Rn, 1e-9))));
        let beta = null;
        for (const cand of [wrapPi(ph + c), wrapPi(ph - c)]) {
            const b = clampR(cand, bR), cost = Math.abs(b - cand) + 1e-3 * Math.abs(b - s.beta);
            if (beta === null || cost < beta.cost) beta = { b, cost };
        }
        beta = beta.b;
        // alpha: the turn about Yr from pin(beta) m0's trace to d's (both off the rotor axis), or the clip's twist
        // about Yr where d runs along it
        const mb = vrot(m0, P0, beta);
        const off = (w) => { const k = vdot(w, Yr); return [w[0] - k * Yr[0], w[1] - k * Yr[1], w[2] - k * Yr[2]]; };
        const p1 = off(mb), p2 = off(d), n1 = Math.hypot(...p1), n2 = Math.hypot(...p2);
        const aDir = n1 > 1e-6 && n2 > 1e-6 ? Math.atan2(vdot(vcross(p1, p2), Yr), vdot(p1, p2)) : 0;
        const aTw = angleAbout(q, Yr);
        const w = smooth(4 * D, 12 * D, Math.asin(Math.min(1, Math.min(n1, n2))));
        let alpha = clampR(aTw + w * wrapPi(aDir - aTw), aR);
        // the analytic pair matches d's angle from the rotor axis exactly, which is right only when the pair reaches d:
        // the rotor axis leans 14 deg below the hand, so a clip that rolls the thumb about itself (the walk: d within 3
        // deg of the rest) has no small root, the in-range one flexed the CMC 29-42 deg into the palm while the rotor,
        // needing -40, clamped at 0, and the thumb stood out of the palm into the thigh (10-19). Where the analytic pair
        // misses d, take the in-range pair whose direction is nearest d (a 5 deg grid, then halving steps), the clip's
        // twist steering alpha where d runs along the rotor axis, the last pair breaking ties
        const dirOf = (a, b) => vrot(vrot(m0, P0, b), Yr, a);
        const miss = (a, b) => 1 - vdot(dirOf(a, b), d);
        // the coupled limit (the hand round, 10-19): the metacarpal's heel meets the stator's lip as the rotor opposes,
        // so the CMC's flexion stops at 87 deg to 40 of opposition, 86 at 50, 79 at 60 (linear between)
        const bMax = (a) => {
            const o = a / D + T.leftThumbRotor.flex_at_rest;
            const lim = o <= 40 ? 87 : o <= 50 ? 87 - 0.1 * (o - 40) : 86 - 0.7 * (o - 50);
            return Math.min(bR[1], (lim - T.leftThumbMetacarpal.flex_at_rest) * D);
        };
        if (miss(alpha, beta) > 1e-6 || beta > bMax(alpha)) {
            const cost = (a, b) => miss(a, b) + (1 - w) * 0.05 * (a - aTw) ** 2
                + 0.002 * (Math.abs(a - s.alpha) + Math.abs(b - s.beta));
            const b0 = Math.min(beta, bMax(alpha));
            let best = { a: alpha, b: b0, e: cost(alpha, b0) };
            for (let a = aR[0]; a <= aR[1] + 1e-9; a += 5 * D) {
                for (let b = bR[0]; b <= bMax(a) + 1e-9; b += 5 * D) {
                    const e = cost(a, b);
                    if (e < best.e) best = { a, b, e };
                }
            }
            for (let step = 2.5 * D; step > 0.02 * D; step /= 2) {
                for (let moved = true; moved;) {
                    moved = false;
                    for (const [da, db] of [[step, 0], [-step, 0], [0, step], [0, -step]]) {
                        const a = clampR(best.a + da, aR), b = clampR(best.b + db, [bR[0], bMax(a)]), e = cost(a, b);
                        if (e < best.e - 1e-12) { best = { a, b, e }; moved = true; }
                    }
                }
            }
            alpha = best.a; beta = best.b;
        }
        s.alpha = alpha; s.beta = beta;
        s.dbg = { alpha: alpha / D, beta: beta / D, aDir: aDir / D, aTw: aTw / D, w, d };       // (handDebug)
        const qr = new THREE.Quaternion().setFromAxisAngle(ax(Yr), alpha);
        q.copy(qr).multiply(r.setFromAxisAngle(ax(P0), beta));
        mirror(q, m, mc.quaternion);
        note(side + 'ThumbMetacarpal', before, q);
        // 2b. the thumb's MCP and IP pins by DIRECTION: each flexed so its segment points nearest the clip's segment
        // (the clip's own chain, its roll about the metacarpal included, against ours, which has no such joint). Its
        // twist about each pin had copied the clip's curl into a plane rolled 45 deg from the clip's, across the palm:
        // in the walk the thumb tips cut into the thighs (10-19)
        const ourChain = q.clone(), clipChain = qmClip;
        for (const b of ['ThumbProximal', 'ThumbDistal']) {
            const j = T['left' + b], node = H.getNormalizedBoneNode(side + b);
            if (!j || !node) continue;
            mirror(node.quaternion, m, q);
            const before2 = q.clone();
            clipChain.multiply(q);
            const u = new THREE.Vector3(s.s0[0], s.s0[1], s.s0[2]).applyQuaternion(clipChain)
                .applyQuaternion(ourChain.clone().invert());                       // the clip's segment, in our parent
            const a = vunit(j.axis), off = (w) => { const k = vdot(w, a); return [w[0] - k * a[0], w[1] - k * a[1], w[2] - k * a[2]]; };
            const p1 = off(s.s0), p2 = off([u.x, u.y, u.z]);
            const g = Math.hypot(...p1) > 1e-6 && Math.hypot(...p2) > 1e-6
                ? Math.atan2(vdot(vcross(p1, p2), a), vdot(p1, p2)) : angleAbout(q, j.axis);   // (along the pin: its twist)
            q.setFromAxisAngle(ax(a), clampR(g, range(j)));
            ourChain.multiply(q);
            mirror(q, m, node.quaternion);
            note(side + b, before2, q);
        }
        // 3. the rotor helper: alpha about Yr, in its parent's rest frame
        if (s.helper) {
            mirror(qr, m, r);
            s.helper.quaternion.copy(s.Pinv).multiply(r).multiply(s.P).multiply(s.Lrest);
        }
    }
}

// THE CROWN (10-19: the petals take part in the face's expressions). VRM expressions bind morph targets
// and materials, never bones, so the crown reads the face's expression weights each frame and blends each petal's fold
// phi from its states (refstudy/SPEC.md 3.3: phi 0 = radial in the face plane, + folding back; the petal bones rest at
// 35 with local X on the hinge, + folding back), adds the listening bias toward where the eyes look (the petals facing
// it open flatter), holds every petal on its BUILT stops (PETAL_FOLD), keeps SPEC's stem interlock (a stem at 70 or more
// while the head rolls 4 deg or more toward it), and moves no petal faster than its lead-screw actuator would (240 deg/s).
//   initCrown(vrm) once at load; applyCrown(vrm, dt[, { state, weight }]) each frame after the face's expressions are
//   set and before vrm.update (state: one of CROWN_STATES blended on top, e.g. 'thinking', 'resting', 'curious')
// THE STATIONS' CLOCK ANGLES (fix round 1, 10-29), deg from 12 o'clock, + toward the robot's left: v2_crown.CLOCKS, as
// built, petal_00 .. petal_11 in its _stations() order (the left side top to bottom, then the right bottom to top;
// test_crown_dof.mjs checks them against v2_crown.py). The look's bias weighs each petal by its own station (the even
// steps of 19 .. 140 used before lay up to 15.8 deg off them). A petal's rank (the top pair 0, down each side to the
// stems 5) is its index's: i on the left, 11 - i on the right
export const PETAL_A = [18.4, 49.4, 79.8, 107.4, 128.2, 148.5, -148.5, -128.2, -107.4, -79.8, -49.4, -18.4];
const PETAL_REST = 35;
// THE BUILT STOPS (fix round 1, 10-29: MECH-D1), fold [min, max] per petal as v2_crown.STOPS / FOLD_MAX build them and
// work/v2/bones_crown.json limits.petal_NN.fold records them (test_crown_dof.mjs checks this table against that file).
// SPEC's -6 / +100 hold on the upper eight; the lower stations' front pads are thicker rubber wedges that stop the lug
// later: the long lower pair (04 / 07) at +10 and the stems (05 / 06) at +30, where the crown clears the torso, its
// collar and the neck boot at every head pose by geometry (v2_crown: first contact at a 13.2 / 15.4 deg head roll, the
// roll stop 11). The pad's face IS the stop (the tongue first crosses it at 10.001 / 30.001; past it the lug goes ~0.15
// mm per deg into the rubber: the MECH-D1 skeptic), so no state, look or clip may take a petal past it
export const PETAL_FOLD = [[-6, 100], [-6, 100], [-6, 100], [-6, 100], [10, 100], [30, 100],
                           [30, 100], [10, 100], [-6, 100], [-6, 100], [-6, 100], [-6, 100]];
// SPEC's stem interlock: a stem folds back to 70 or more while the head rolls 4 deg or more toward it. With the stems on
// their built +30 it is no longer needed for clearance (above); it stays as SPEC's behaviour
export const STEM_LOCK = { roll: 4, fold: 70 };
// phi per rank, the top pair first; every value inside both petals' built stops (ranks 4 and 5: 04 / 07 from +10, the
// stems from +30), so a blend toward a state reaches its stop smoothly instead of sitting on the clamp
export const CROWN_STATES = {
    neutral: [35, 35, 35, 35, 35, 35],
    happy: [2, 8, 16, 26, 36, 44],            // a lift: the upper petals open to the light, the lower ones easing back
    angry: [-6, 20, 60, 74, 82, 88],          // a crest perked forward over the side petals pinned back, as ears flatten
    sad: [70, 76, 82, 88, 92, 94],            // a droop back toward resting, the lowest furthest
    relaxed: [55, 58, 60, 62, 64, 66],        // settled, half folded
    surprised: [-4, -4, -2, 0, 10, 30],       // snapped wide open (the lower two pairs on their built stops)
    thinking: [0, 0, 0, 0, 10, 30],           // fully radial: the radiators spread to shed heat (SPEC; the lower two on their stops)
    listening: [28, 28, 28, 28, 28, 30],      // SPEC's listening fold (the stems on their stop)
    curious: [-6, 30, 30, 30, 58, 58],        // the top pair perked (SPEC -10, held at the stop), the lowest folded
    resting: [97, 97, 97, 97, 97, 97],        // folded back like a hat (3 inside the built +100, as SPEC's 94 sat 3 inside its +97)
};
const CROWN_EMOTIONS = ['happy', 'angry', 'sad', 'relaxed', 'surprised'];
const _crowns = new WeakMap();

// THE HEAD IN THE EXPRESSIONS (10-19: the head tilts and turns with the face): each
// emotion carries a small head pose, added on top of whatever the animation does and moved at the neck actuators' rate:
// pitch (+ nods the chin down), roll (SPEC's sign: + lowers the +X side, the head tilting toward its left) and pan
// (+ toward its left), deg, kept well inside the head's stops (bones_head.json: pan +-60, nod +-30, roll +-11)
export const HEAD_STATES = {
    happy: { pitch: -6, roll: 5, pan: 0 },       // a lift and a cheerful tilt
    angry: { pitch: 8, roll: 0, pan: 0 },        // the chin down
    sad: { pitch: 12, roll: -3, pan: 0 },        // lowered, drooping a little to the side
    relaxed: { pitch: 3, roll: 3, pan: 0 },      // a soft tilt
    surprised: { pitch: -8, roll: 0, pan: 0 },   // pulled up and back
    curious: { pitch: -2, roll: 9, pan: 0 },     // SPEC's curious head roll (12-20), held inside the 11 stop
    thinking: { pitch: -6, roll: 4, pan: 10 },   // looking up and off to the side
};
const _heads = new WeakMap();

// applyHeadExpression(vrm, dt[, { state, weight }]) each frame after the expressions are set, before applyCrown (whose
// stem interlock reads the head's roll) and before vrm.update
export function applyHeadExpression(vrm, dt, opts = {}) {
    const THREE = globalThis.THREE;
    const H = vrm.humanoid, head = H?.getNormalizedBoneNode('head'), neck = H?.getNormalizedBoneNode('neck');
    if (!head) return;
    const em = vrm.expressionManager, val = (n) => (em ? em.getValue(n) || 0 : 0);
    const ws = CROWN_EMOTIONS.map(val), sum = ws.reduce((a, b) => a + b, 0), k = sum > 1 ? 1 / sum : 1;
    const want = { pitch: 0, roll: 0, pan: 0 };
    CROWN_EMOTIONS.forEach((e, j) => { for (const c in want) want[c] += k * ws[j] * HEAD_STATES[e][c]; });
    if (opts.state && HEAD_STATES[opts.state]) {
        for (const c in want) want[c] += (opts.weight ?? 1) * (HEAD_STATES[opts.state][c] - want[c]);
    }
    let st = _heads.get(vrm);
    if (!st) _heads.set(vrm, (st = { pitch: 0, roll: 0, pan: 0 }));
    const step = 120 * dt;                                           // the neck's actuators: 120 deg/s
    for (const c in want) st[c] += Math.max(-step, Math.min(step, want[c] - st[c]));
    const q = new THREE.Quaternion(), r = new THREE.Quaternion();
    // VRM's normalized frame: +X the robot's left, +Y up, +Z forward; a turn about +X nods the chin down, about +Z
    // raises the +X side (so SPEC's roll is its negative), about +Y pans toward +X
    q.setFromAxisAngle(new THREE.Vector3(1, 0, 0), st.pitch * D).multiply(r.setFromAxisAngle(new THREE.Vector3(0, 0, 1), -st.roll * D));
    head.quaternion.premultiply(q);
    if (neck && st.pan) neck.quaternion.premultiply(q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), st.pan * D));
    // (fix round 1) the sum inside the head's built stops: rehomeBody clamps the clip's head, and the expression's pose
    // goes on top (a clip at nod 30 plus sad's 12 put the head at 42 against its stop 30). The neck * head turn split as
    // the stages are stacked, pan (the neck) then nod then roll (Euler 'YXZ'); only a split past a stop is clamped and
    // recomposed, so every pose inside them passes untouched
    const nq = neck ? neck.quaternion : new THREE.Quaternion();
    const e = new THREE.Euler().setFromQuaternion(nq.clone().multiply(head.quaternion), 'YXZ');
    const cl = (x, rr) => Math.min(rr[1] * D, Math.max(rr[0] * D, x));
    const pan = cl(e.y, HEAD_RANGE.pan), nod = cl(e.x, HEAD_RANGE.x), rl = cl(e.z, HEAD_RANGE.z);
    if (pan !== e.y || nod !== e.x || rl !== e.z) {
        if (neck) neck.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), pan);
        head.quaternion.setFromEuler(new THREE.Euler(nod, neck ? 0 : pan, rl, 'YXZ'));
    }
}

export function initCrown(vrm) {
    const petals = [];
    for (let i = 0; i < 12; i++) {
        const o = vrm.scene.getObjectByName('petal_' + String(i).padStart(2, '0'));
        petals.push(o ? { o, rest: o.quaternion.clone(), phi: PETAL_REST } : null);
    }
    const st = { petals, found: petals.filter(Boolean).length };
    _crowns.set(vrm, st);
    return st;
}

export function applyCrown(vrm, dt, opts = {}) {
    const THREE = globalThis.THREE;
    const st = _crowns.get(vrm);
    if (!st) return;
    const em = vrm.expressionManager, val = (n) => (em ? em.getValue(n) || 0 : 0);
    const ws = CROWN_EMOTIONS.map(val), sum = ws.reduce((a, b) => a + b, 0), k = sum > 1 ? 1 / sum : 1;
    const look = val('lookLeft') - val('lookRight');                 // + toward the robot's left (+X, a > 0)
    // the head's roll, + lowering the +X side (SPEC): its normalized turn about the face axis (VRM +Z) negated
    const head = vrm.humanoid?.getNormalizedBoneNode('head');
    const roll = head ? -2 * Math.atan2(head.quaternion.z, head.quaternion.w) / D : 0;
    const X = new THREE.Vector3(1, 0, 0), q = new THREE.Quaternion();
    for (let i = 0; i < 12; i++) {
        const p = st.petals[i];
        if (!p) continue;
        const r = i < 6 ? i : 11 - i;                                // the rank: the top pair 0 .. the stems 5
        let phi = CROWN_STATES.neutral[r];
        CROWN_EMOTIONS.forEach((e, j) => { phi += k * ws[j] * (CROWN_STATES[e][r] - CROWN_STATES.neutral[r]); });
        if (opts.state && CROWN_STATES[opts.state]) phi += (opts.weight ?? 1) * (CROWN_STATES[opts.state][r] - phi);
        phi -= 15 * Math.abs(look) * Math.max(0, Math.cos((PETAL_A[i] - Math.sign(look) * 90) * D));
        // the built stops (the look's bias lands on them); above a stem's, SPEC's interlock, its roll compared with a hair
        // of slack (thinking's exact 4 reads back from the head's quaternion as 3.9999999999999991)
        const [lo0, hi] = PETAL_FOLD[i];
        const toward = PETAL_A[i] > 0 ? roll : -roll;
        const lo = r === 5 && toward >= STEM_LOCK.roll - 1e-6 ? Math.max(lo0, STEM_LOCK.fold) : lo0;
        phi = Math.min(hi, Math.max(lo, phi));
        const step = 240 * dt;
        p.phi += Math.max(-step, Math.min(step, phi - p.phi));
        p.phi = Math.min(hi, Math.max(lo0, p.phi));                  // (the hardware's stops, whatever the rate left)
        p.o.quaternion.copy(p.rest).multiply(q.setFromAxisAngle(X, (p.phi - PETAL_REST) * D));
    }
}
