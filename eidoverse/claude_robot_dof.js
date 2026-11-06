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
//   file's 'hinges', parsed first; its leftLowerArm record sets the elbow); then each frame, dt its real time step:
//   restoreArmPose(vrm), the clip's mixer.update(dt), keepArmPose(vrm) (THE CLIP'S POSE FOR THE ARM PASS, below); then
//   rehomeBody(vrm), applyHardwareDOF(vrm, LEG_JOINTS), applyLegClearance(vrm, stats, dt) (THE LEGS' CLEARANCE, below),
//   applyArmDOF(vrm, stats, dt), vrm.update(dt)

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
//   neck and head rotations compose, and the composite is split in the mechanism's own order, pan (the neck) then nod
//   then roll (R = Ry(pan) Rx(nod) Rz(roll), three's Euler 'YXZ', as applyHeadExpression and the film's key check split
//   it), each clamped at the head's built stops (roll +-11: 2.2 inside the crown's first contact over the head's range,
//   13.2; nod +-30; pan +-60). (Round 2: the split had been the twist about Y, then XZY with y dropped, which moved a
//   pose inside the stops: pan -60, nod -30, roll 11 came out -57.04 / -30.0 / 9.51, the head 2.56 deg off; the film
//   rig's verifier, film/unboxing/rig/verify/NOTES.md:174)
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
    const e = new THREE.Euler();
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
        // the composite neck * head = Ry(pan) Rx(nod) Rz(roll): Euler 'YXZ' (y the pan, x the nod, z the roll); each
        // clamped, the neck set to the pan alone and the head to nod then roll (Euler 'XZY' with y 0 = Rx Rz). A pose
        // inside the stops comes back exactly, and a projected pose projects to itself (|nod| <= 30, far from YXZ's
        // singular 90)
        const R = neck.quaternion.clone().multiply(head.quaternion);
        e.setFromQuaternion(R, 'YXZ');
        const pan = Math.min(HEAD_RANGE.pan[1], Math.max(HEAD_RANGE.pan[0], e.y / D)) * D;
        const nod = Math.min(HEAD_RANGE.x[1], Math.max(HEAD_RANGE.x[0], e.x / D)) * D;
        const roll = Math.min(HEAD_RANGE.z[1], Math.max(HEAD_RANGE.z[0], e.z / D)) * D;
        neck.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), pan);
        head.quaternion.setFromEuler(e.set(nod, 0, roll, 'XZY'));
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

// THE LEGS' CLEARANCE FROM EACH OTHER (fix round 2, the second legs design, 11-02: V7-D1; work/tmp/final/fix2/legs/d2/
// DESIGN_LEGS2.md, building REVIEW_LEGS.md 4; design 2.1, 11-02: work/tmp/final/fix2/legs/d21/DESIGN_LEGS21.md, its
// review's C1-C3 built in: the pair's shortfall, loaded at any height, the swivel's conditioning; design 2.2, 11-05:
// work/tmp/final/fix2/legs/d22/DESIGN_LEGS22.md, C3's weight eased in and C2's velocities read over a fixed time, so the
// landings don't twist a planted foot and the stance holds at 60 and 120 Hz). Stock clips are a human's: they put both
// feet on one narrow track and
// swing a foot close past the other ankle, and my feet (125.7 mm wide, their inner edges 26 mm apart at rest) and shins
// are wider than a human's, so the legs passed through each other at every step of the walk, and in the run, the turn,
// the stair run, the vault, the ladder, the salute, the reach and the walk / run crossfade. After applyHardwareDOF, each
// ankle is moved out on the floor plane by up to `width` and the leg re-posed to reach it, the foot keeping the clip's
// sole and, on the floor, its heading:
//   THE OFFSET  o, per leg in the root frame, on the floor plane: its target `width` along the pelvis's lateral away
//               from the other hip (the hip joints, on the floor plane), narrowed to nothing where the clip's own ankles
//               are already need[0] -> need[1] apart across (a crouch, a landing, a sit: the hip's table could not hold it
//               there, and every crossing frame of every stock clip has them under 150 mm) for a leg hanging within
//               `support` of straight down (a raised leg keeps the whole width: the vault's pike). While the foot bears
//               weight o is HELD, so a planted foot moves by the offset it landed with and nothing else, whatever the
//               body's yaw or the knee does over it. While the foot is up, o eases toward its target by at most `ease` of
//               the clip's own motion of that leg in the frame (the least of the ankle's, the ball's and twice the knee's
//               step): the pass never moves a foot faster than half the clip moves it (where the clip's own ankle jumps
//               more than `jump` m in a frame, a loop seam or a cut, it takes it at once, hidden in the jump); and a foot
//               up is never left more than `hold` deg off the pelvis's lateral (past it the offset would narrow the
//               stance; every stance of every stock clip ends within 81 deg of it).
//               THE PAIR (2.1, C1): a foot held short of its own target along the lateral (one it landed with where the
//               need had narrowed it, or one the table shrank: talk, cheer, a landing hand the next clip a planted foot at
//               o ~ 0) would leave the other's next pass short of 2 W. So while the other foot is loaded and short, a
//               hanging up foot's target takes that shortfall on top of its own (by smooth(pair[0], pair[1]) of the
//               shortfall: one within the walk's 19 mm clearance margin, a pelvis's sway or a turn's lag, is left; one a
//               clip handed on is made up whole; never past the other's own target; a leg raised past the support angle
//               takes none, as the need narrows a hanging leg only). The feet pass 2 W apart whatever the clip before
//               left; the up foot lands wide, and the stance comes back to W a side within a stride, as each foot lifts.
//               And the loaded foot itself (C1 b, THE SLIDE): one whose offset is shorter than its target makes it up
//               along the lateral while the clip itself slides it off the stance, by at most `ease` of that slide (in
//               double support the pair's slide against itself or this foot's departure from the stance, the less, past
//               slide[0] m/s; in single support its departure from the stance past slide[1]): a crossfade that drags the
//               feet together before the swing foot can take the pair widens them as it drags them. A standing foot takes
//               none; the length, not the projection, so a sway or a turn's lag is no deficit; never at a seam; weighted
//               by `pair`'s band on the largest deficit the foot has carried since it was last up, so a few mm the table
//               took are not given back under it.
//   LOADED      this foot's lowest point within load[0] of the lower foot's (released above load[1]) and the leg within
//               support[0] deg of hanging straight down (released past support[1]), in the clip's pose before the pass
//               and the grounding. The points are the foot's own Foot + Toes vertices, the grounding's set
//               (avatar_ground.js), read once from the bind: a foot on its toe or its heel counts; the turns' 4-12 mm
//               shuffle lifts free it. Every stance of every stock clip has its leg within 50 deg; a raised leg (the
//               vault's pike, 56-75; the jump's tuck) bears no weight however low its foot.
//               AT ANY HEIGHT (2.1, C2): also loaded while the foot moves with the clip's stance (its ankle or its ball
//               within stance[0] m/s of the stance velocity v_st to enter, stance[1] to stay; the leg within the support
//               angle): a foot standing on a step, a rung or a hold above the other foot bears weight too. v_st (in the
//               memo) is the velocity the clip's standing feet move with (an in-place clip's treadmill): eased halfway in
//               1/30 s to the mean of its witnesses, the feet loaded (by height now, or by stance at the last input) whose
//               steadier point (the ball at a heel-off, the ankle at a heel-strike) changed velocity by at most `steady`
//               m/s2 and lies within `track` m/s of v_st; with no witness for `stale` s the next one sets it afresh. (2.2)
//               Every velocity here is read over at least `window` s (the inputs since the newest one that far back), the
//               time base these knobs were set at: per input at 120 Hz a clip keyed at 24 fps steps its velocity at each
//               key, and the witness failed there.
//   THE LEG     the target T = the clip's hip -> ankle + o. The knee set so |hip -> ankle| = |T| (the law of cosines on
//               the thigh and the shin, within the knee's range); the thigh turned by the least rotation onto T, then
//               swivelled about hip -> T until its X (the knee's and the ankle's pitch pin) lies square to the clip's foot
//               forward, the swivel weighted by the foot's height over the lower foot (whole below swivel[0], none from
//               swivel[1]: a foot's heading matters only on the floor, and a high swing's swivel only threw its knee), or
//               whole while it moves with the stance at any height (2.1, C2: fading as it leaves it); and (2.1, C3) by its
//               own conditioning, smooth(cond[0], cond[1], |Fz x u|): where the clip's foot forward lies near hip -> T
//               (a foot pointing along its folded leg: the jump's take-off) a turn about hip -> T barely moves the heading,
//               and the swivel only swung the knee (107 mm in a frame); there the foot keeps the least turn's heading.
//               (2.2) That weight falls at once but rises by at most `condRate` a second: at a landing it crossed the band
//               in a frame, and the whole swivel twisted the planted foot 15-20 deg on the frame after touchdown.
//               The ankle's cardan has no yaw, so the foot's forward is square to that pin: on the floor the cardan holds
//               the clip's whole foot turn, and the foot moves by o and nothing else (its sole, its heading and its height
//               the clip's). A planted foot neither slides nor floats, and the grounding finds both feet where the clip
//               has them. A T past the leg's reach (the knee straight) is met at the reachable length along hip -> T, the
//               foot then a few mm high (the raise's straight leg 6.6 mm at 72 mm): THE LEVEL takes that back.
//   THE TABLE   a loaded leg takes the largest share s of o whose thigh the hip's table holds (the box and the coupled
//               table, as applyHardwareDOF clamps them; bisected, s = 0 being the clip's own clamped thigh): the planted
//               foot gives up offset along o only, never shoved, and o stays shrunk while it bears weight (no give-back
//               under it). An unloaded leg takes the clamp's own projection (a tucked leg on its roll limit still moves
//               part of the way out: climbLedge's tuck needs it).
//   THE CLAMPS  the thighs and the knees clamped as applyHardwareDOF clamps them and the hip's stages solved; each
//               foot's sole normal (the clip's) restored in the new shin's frame and clamped as the cardan is.
//   THE LEVEL   every foot near the floor raised by the same height: each foot the pass raised less than the most-raised
//               LOADED foot is raised to it (its target lifted, the leg re-posed: a bent knee bends a little more; the
//               lift weighted by the foot's height as the swivel is, and kept inside the table), and the grounding, which
//               sets the body down on the lower foot, takes the common height back off the whole body. So no loaded foot
//               floats while the other bears the body, and none slides: every foot where the clip has it, the body the
//               reach's few mm lower.
// The state (loaded, o, the clip's last knee, ankle and ball, their recent inputs and velocities, the swivel's weight;
// v_st) is per leg (v_st per VRM) in the
// per-VRM memo and advances once per new clip input: a bone the clip has not written since still holds the pass's output,
// and its input is then the last input, so a second pass in a frame, or a pose held, changes nothing (the contract at the
// top). The easing is measured against the clip's own motion, whatever the frame rate; dt turns the stance's motion into
// velocities (2.1, C2: 1/30 s when absent); it keeps applyArmDOF's call shape.
//   applyHardwareDOF(vrm, LEG_JOINTS, stats); applyLegClearance(vrm, stats, dt); applyArmDOF(vrm, stats, dt, 8) ...
export const LEG_CLEARANCE = { width: 0.072, need: [0.18, 0.23], load: [0.003, 0.006], support: [45, 55], ease: 0.5, jump: 0.25, hold: 90,
    swivel: [0.02, 0.1], level: true,
    // (design 2.1, 11-02: C1 the band on the other foot's shortfall over which it is taken, m, and the slide's noise in
    //  double / single support, m/s (at 30 Hz 6 mm a frame, C2's stay threshold / 20 mm a frame, past v_st's wander in a
    //  walk's stance); C2 the stance: m/s to enter / stay, the witnesses' steadiness in m/s2, their tracking in m/s, the
    //  stale time in s (at 30 Hz: 4 / 6 mm a frame, 3 mm a frame per frame, 5 mm a frame, 3 frames); C3 the swivel's
    //  conditioning band on |Fz x u|)
    pair: [0.02, 0.045], slide: [0.18, 0.6], stance: [0.12, 0.18], steady: 2.7, track: 0.15, stale: 0.1, cond: [0.3, 0.5],
    // (design 2.2, 11-05: C2's velocities are read over at least `window` s, the time base its knobs above were set at,
    //  so the witness and the stance see the same motion at 30, 60 and 120 Hz; C3's weight rises by at most `condRate`
    //  a second, so the swivel comes on over several frames where a landing turns it on)
    window: 1 / 30, condRate: 3 };
const _legClear = new WeakMap();

// the feet's lowest-point candidates, once per VRM: each side's vertices whose dominant joint (the largest skin weight)
// is its Foot or its Toes, as offsets from that bone at the bind in the normalized frame (world-aligned at rest), within
// 50 mm of the set's lowest (the sole and its lower edges)
function initLegClearance(vrm) {
    const THREE = globalThis.THREE;
    const H = vrm.humanoid, own = new Map(), pts = {}, M = new THREE.Matrix4(), p = new THREE.Vector3();
    for (const side of ['left', 'right']) {
        for (const b of ['Foot', 'Toes']) { const r = H.getRawBoneNode?.(side + b); if (r) own.set(r, side + b); }
    }
    vrm.scene.traverse((m) => {
        if (!m.isSkinnedMesh) return;
        const g = m.geometry, si = g.attributes.skinIndex, sw = g.attributes.skinWeight, pos = g.attributes.position;
        if (!si || !sw || !pos) return;
        const org = new Map();
        for (let i = 0; i < si.count; i++) {
            let best = -1, bw = -1;
            for (let k = 0; k < 4; k++) { const w = sw.getComponent(i, k); if (w > bw) { bw = w; best = si.getComponent(i, k); } }
            const key = own.get(m.skeleton.bones[best]);
            if (!key) continue;
            let o = org.get(best);
            if (!o) org.set(best, o = new THREE.Vector3().setFromMatrixPosition(M.copy(m.skeleton.boneInverses[best]).invert()));
            p.fromBufferAttribute(pos, i).applyMatrix4(m.bindMatrix).sub(o);
            (pts[key] = pts[key] || []).push(p.x, p.y, p.z);
        }
    });
    const keep = (a) => {
        if (!a) return new Float64Array(0);
        let lo = Infinity;
        for (let i = 1; i < a.length; i += 3) lo = Math.min(lo, a[i]);
        const out = [];
        for (let i = 0; i < a.length; i += 3) if (a[i + 1] < lo + 0.05) out.push(a[i], a[i + 1], a[i + 2]);
        return Float64Array.from(out);
    };
    const mem = { sig: null, vst: null, stale: 0 };
    for (const side of ['left', 'right']) {
        mem[side] = { foot: keep(pts[side + 'Foot']), toes: keep(pts[side + 'Toes']), M: {}, loaded: false, h: null, next: null, last: null,
                      st: false, hist: [], wst: 0, dmax: 0, wc: 1, cap: Infinity };
    }
    return mem;
}

// the lowest y of a point set (offsets in a bone's normalized frame) turned by q, the bone's origin at height y0
function lowestY(P, q, y0) {
    const r0 = 2 * (q.x * q.y + q.w * q.z), r1 = 1 - 2 * (q.x * q.x + q.z * q.z), r2 = 2 * (q.y * q.z - q.w * q.x);
    let lo = Infinity;
    for (let i = 0; i < P.length; i += 3) { const y = r0 * P[i] + r1 * P[i + 1] + r2 * P[i + 2]; if (y < lo) lo = y; }
    return y0 + lo;
}

export function applyLegClearance(vrm, stats, dt, width = LEG_CLEARANCE.width) {
    const THREE = globalThis.THREE;
    const H = vrm.humanoid, B = (n) => H.getNormalizedBoneNode(n), hips = B('hips');
    if (!hips || !width) return;
    let mem = _legClear.get(vrm);
    if (!mem) _legClear.set(vrm, mem = initLegClearance(vrm));
    const UL = LEG_JOINTS.find((j) => j.bone === 'UpperLeg'), LL = LEG_JOINTS.find((j) => j.bone === 'LowerLeg');
    const FT = LEG_JOINTS.find((j) => j.bone === 'Foot');
    const C = LEG_CLEARANCE;
    const same = (a, b) => !!a && Math.abs(a.dot(b)) > 1 - 1e-12;
    const Qh = hips.quaternion, Qi = Qh.clone().invert(), hp = hips.position;
    const e = new THREE.Euler(), legs = {};
    // 1. the inputs (the clip's, clamped; a bone still holding the pass's output gives back its input), each leg's hip ->
    //    ankle v in the hips' frame, its foot's turn there, and its foot's lowest point in the root frame
    for (const [side, m] of [['left', 1], ['right', -1]]) {
        const t = B(side + 'UpperLeg'), s = B(side + 'LowerLeg'), f = B(side + 'Foot'), to = B(side + 'Toes');
        if (!t || !s || !f) return;
        const Mm = mem[side].M;
        const input = (k, node) => (same(Mm[k]?.out, node.quaternion) ? Mm[k].in : node.quaternion).clone();
        const qt = input('t', t), qs = input('s', s), qf = input('f', f), qe = to ? to.quaternion.clone() : null;
        const v = f.position.clone().applyQuaternion(qs).add(s.position).applyQuaternion(qt);
        const qF = qt.clone().multiply(qs).multiply(qf), RF = Qh.clone().multiply(qF);
        const ankle = t.position.clone().add(v).applyQuaternion(Qh).add(hp);
        const knee = s.position.clone().applyQuaternion(qt).add(t.position).applyQuaternion(Qh).add(hp);
        const ball = to ? to.position.clone().applyQuaternion(RF).add(ankle) : ankle;
        let lo = lowestY(mem[side].foot, RF, ankle.y);
        if (to) lo = Math.min(lo, lowestY(mem[side].toes, RF.clone().multiply(qe), ball.y));
        legs[side] = { m, t, s, f, to, Mm, qt, qs, qf, qe, qF, v, lo, at: [knee, ankle, ball] };
    }
    const low = Math.min(legs.left.lo, legs.right.lo);
    // 2. the state, once per new input: loaded (hysteresis on the lowest points and on the leg's angle from hanging; or, at
    //    any height, moving with the clip's stance: C2); o (carried from the last input: held while loaded, but for a
    //    deficit the clip's own slide of that foot makes up (C1 b); while up, eased by `ease` of the clip's own motion
    //    of the leg toward its width plus the loaded other foot's shortfall (C1 a), and kept within `hold` of the pelvis's
    //    lateral)
    const sig = [Qh.x, Qh.y, Qh.z, Qh.w, hp.x, hp.y, hp.z];
    for (const L of Object.values(legs)) for (const q of [L.qt, L.qs, L.qf, L.qe]) if (q) sig.push(q.x, q.y, q.z, q.w);
    if (!mem.sig || mem.sig.length !== sig.length || sig.some((x, i) => x !== mem.sig[i])) {
        mem.sig = sig;
        const dtv = dt > 0 ? dt : 1 / 30;
        const lat = legs.left.t.position.clone().sub(legs.right.t.position).applyQuaternion(Qh);
        const lh = Math.hypot(lat.x, lat.z), tgt = lh > 0.25 * lat.length() ? [lat.x / lh, lat.z / lh] : null;
        // the need: the clip's own gap between the ankles across (along the hip joints' line, on the floor plane); where
        // the feet are already that far apart (a crouch, a landing, a sit, a climb) the target narrows to nothing
        const gap = tgt ? (legs.left.at[1].x - legs.right.at[1].x) * tgt[0] + (legs.left.at[1].z - legs.right.at[1].z) * tgt[1] : 0;
        const wide = C.need ? smooth(C.need[0], C.need[1], gap) : 0;
        const rot = (u, a) => [u[0] * Math.cos(a) - u[1] * Math.sin(a), u[0] * Math.sin(a) + u[1] * Math.cos(a)];
        const Q = {};
        for (const [side, L] of Object.entries(legs)) {
            const S = mem[side], up = L.lo - low, tg = tgt && [L.m * tgt[0], L.m * tgt[1]];
            const vr = L.v.clone().applyQuaternion(Qh), hang = Math.acos(Math.max(-1, Math.min(1, -vr.y / vr.length()))) / D;
            // (the need narrows a HANGING leg's target only: a leg raised past the support angle bears no weight and
            //  keeps the whole width, ready for a pike or a tuck)
            const wd = width * (1 - wide * (1 - smooth(C.support[0], C.support[1], hang)));
            const st = S.last ? L.at.map((p, i) => p.distanceTo(S.last[i])) : [0, 0, 0];
            const moved = st[1] > C.jump ? Infinity : Math.min(2 * st[0], st[1], st[2]);
            // (C2: the ankle's and the ball's velocities, m/s in the root frame. 2.2: over the newest past input at least
            //  `window` s back: at 30 Hz since the last input (2.1's, to the digit), at 60 / 120 Hz since the 2nd / 4th input
            //  back. A clip keyed at 24 fps, read per input at 120 Hz, holds its velocity for a few inputs and then jumps at a
            //  key, so 2.1's per-input witness failed `steady` at every key and v_st went stale under a planted foot. pw: the
            //  velocities read at that input; span: the time since it. An input 10 % short of the window still counts, so a
            //  frame clock that jitters about 30 Hz reads the last input, as 2.1 did; exact 30 / 60 / 120 Hz read 1 / 2 / 4
            //  back either way)
            let k = S.hist.length - 1, span = dtv;
            while (k > 0 && span < 0.9 * (C.window || 0)) span += S.hist[k--].dt;
            const H0 = S.hist[k], vel = H0 ? [1, 2].map((i) => L.at[i].clone().sub(H0.at[i]).divideScalar(span)) : null;
            S.hist.push({ dt: dtv, at: L.at, vel });
            if (k > 0) S.hist.splice(0, k);
            const prev = S.last;
            S.last = L.at;
            // (C3, 2.2: the swivel's weight on this input rises by at most condRate a second over the last input's; it falls
            //  at once, so the take-off's guard is 2.1's)
            S.cap = C.condRate ? S.wc + C.condRate * dtv : Infinity;
            if (!S.next) S.next = tg ? [wd * tg[0], wd * tg[1]] : [width * L.m, 0];
            Q[side] = { S, up, tg, hang, wd, moved, vel, pw: H0 ? H0.vel : null, span, prev, dev: Infinity };
        }
        // (C2) the clip's stance velocity v_st, carried in the memo: the velocity a standing foot moves with in the clip's
        //      frame (the in-place clip's treadmill). Its witnesses: the feet loaded by height now, or by stance at the last
        //      input, their legs within the support angle, whose steadier point (of the ankle and the ball: the ball at a
        //      heel-off, the ankle at a heel-strike) changed velocity by at most `steady` (m/s2) since the last input and,
        //      while v_st is fresh, lies within `track` of it. v_st eases halfway to the witnesses' mean in 1/30 s; after
        //      `stale` s with no witness the next one sets it afresh
        if (C.stance) {
            let vw = null, nw = 0;
            for (const q of Object.values(Q)) {
                const pv = q.pw;
                if (!q.vel || !pv || q.hang > C.support[1]) continue;
                const ch = [q.vel[0].distanceTo(pv[0]), q.vel[1].distanceTo(pv[1])], j = ch[0] <= ch[1] ? 0 : 1;
                if (ch[j] > C.steady * q.span) continue;
                if (!(q.up <= (q.S.loaded ? C.load[1] : C.load[0]) || q.S.st)) continue;
                if (mem.vst && mem.stale < C.stale && q.vel[j].distanceTo(mem.vst) > C.track) continue;
                vw = vw ? vw.add(q.vel[j]) : q.vel[j].clone();
                nw++;
            }
            if (nw) {
                vw.divideScalar(nw);
                if (!mem.vst || mem.stale >= C.stale) mem.vst = vw;
                else mem.vst.lerp(vw, 1 - Math.pow(0.5, dtv * 30));
                mem.stale = 0;
            } else mem.stale += dtv;
        }
        // LOADED: by height, or (C2) at any height while the foot moves with the clip's stance (its ankle or its ball within
        // stance[0] m/s of v_st to enter, stance[1] to stay): a foot on a step, a rung or a hold above the other foot
        for (const q of Object.values(Q)) {
            const S = q.S;
            const hgt = S.loaded ? q.up <= C.load[1] && q.hang <= C.support[1] : q.up <= C.load[0] && q.hang <= C.support[0];
            let stn = false;
            if (C.stance && mem.vst && q.vel) {
                q.dev = Math.min(q.vel[0].distanceTo(mem.vst), q.vel[1].distanceTo(mem.vst));
                stn = S.loaded ? q.dev <= C.stance[1] && q.hang <= C.support[1] : q.dev <= C.stance[0] && q.hang <= C.support[0];
            }
            S.st = stn;
            S.loaded = hgt || stn;
            // (the swivel's stance weight, kept for every pass on this input: whole while the foot moves with the stance,
            //  fading to none at twice the stay threshold, none for a leg past the support angle: C2's swivel follows C2)
            S.wst = C.stance && Number.isFinite(q.dev) ? (1 - smooth(C.stance[1], 2 * C.stance[1], q.dev)) * (1 - smooth(C.support[0], C.support[1], q.hang)) : 0;
        }
        // (C1 b) the clip's slide of the pair against itself since the last input, on the floor plane (m): the least of the
        //        ankles' and the balls' relative steps. Two standing feet cannot move against each other, so in double
        //        support this is motion off the stance (a crossfade dragging both feet, a shuffle), read without v_st
        let rel = 0;
        if (Q.left.prev && Q.right.prev) {
            rel = Math.min(...[1, 2].map((i) => {
                const d = legs.left.at[i].clone().sub(legs.right.at[i]).sub(Q.left.prev[i].clone().sub(Q.right.prev[i]));
                return Math.hypot(d.x, d.z);
            }));
        }
        for (const [side, q] of Object.entries(Q)) {
            const S = q.S, tg = q.tg, oq = Q[side === 'left' ? 'right' : 'left'];
            let h = S.next.slice(), pair = 0, slid = 0;
            // (C1 b) the largest length deficit this foot has carried since it was last up (the memo): (b)'s weight
            if (!S.loaded) S.dmax = 0;
            else if (tg) S.dmax = Math.max(S.dmax || 0, q.wd - Math.hypot(h[0], h[1]));
            if (tg && !S.loaded) {
                // (C1) the pair's shortfall: where the other foot is loaded and short of its own target along the lateral
                //      (an offset it landed with, or one the table shrank), this foot takes that shortfall on top of its
                //      own width, so the feet pass 2 W apart whatever the clip before left (never past the other's target).
                //      The shortfall is taken by smooth(pair[0], pair[1], shortfall) of itself (m): one within the walk's own
                //      clearance margin (19 mm) needs no making up (the pelvis's sway under a held foot, a turn's lagging
                //      offsets: given it, a turn's held 86 mm made a leg reach straight), one a clip handed on (talk's 72 mm)
                //      is made up whole. A leg raised past the support angle takes none (as the need narrows a hanging leg
                //      only: a raised leg passes no foot, and one that took it landed holding it)
                if (C.pair && oq.S.loaded && oq.tg) {
                    const short = Math.min(oq.wd, Math.max(0, oq.wd - (oq.S.next[0] * oq.tg[0] + oq.S.next[1] * oq.tg[1])));
                    pair = short * smooth(C.pair[0], C.pair[1], short) * (1 - smooth(C.support[0], C.support[1], q.hang));
                }
                const wd = q.wd + pair;
                const dx = wd * tg[0] - h[0], dz = wd * tg[1] - h[1], n = Math.hypot(dx, dz), c = C.ease * q.moved;
                h = n > c ? [h[0] + dx * c / n, h[1] + dz * c / n] : [wd * tg[0], wd * tg[1]];
                const a = Math.atan2(h[0] * tg[1] - h[1] * tg[0], h[0] * tg[0] + h[1] * tg[1]), lim = C.hold * D;
                if (Math.hypot(h[0], h[1]) > 1e-9 && Math.abs(a) > lim) h = rot(h, a - Math.sign(a) * lim);
            } else if (tg && C.slide && S.loaded && Number.isFinite(q.moved)) {
                // (C1 b) THE SLIDE: a loaded foot whose offset is shorter than its own target (what the clip before, the
                //        need or the table left it: its length, so a pelvis's sway or a turn's angular lag, |o| = W, is never
                //        read as one) makes it up along the lateral only while the clip itself slides it off the stance: by at
                //        most `ease` of that slide. In double support the slide is the least of the pair's slide against
                //        itself and this foot's own departure from v_st, past slide[0] m/s of noise (two standing feet cannot
                //        move against each other: a standing foot takes none; of a pivoting pair, the pivoting foot); in
                //        single support, its departure from v_st past slide[1] (v_st alone wanders 10-20 mm a frame in a
                //        steady walk's stance; a crossfade drags a foot 30-120). Never at a seam (a loaded foot holds there,
                //        as before). A crossfade that drags the feet together before the swing foot can take the pair
                //        (sitting_normal_chair > idle 6 > walk: both feet at o = 0 from the seat, 33-124 mm a frame; talk >
                //        idle 6 > walk @.9375: the left at o = 0 dragged 30-100 mm a frame under the right's first swing)
                //        widens them as it drags them. Weighted by (a)'s band on the largest deficit the foot has carried
                //        since it was last up: one within the walk's clearance margin (a few mm the table took in a turn)
                //        is not given back under it (turnLeft's right knee); one a clip handed on is made up whole
                const deficit = Math.max(0, q.wd - Math.hypot(h[0], h[1]));
                if (deficit > 0) {
                    const two = oq.S.loaded, dv = Number.isFinite(q.dev) ? q.dev * dtv : (two ? rel : 0);
                    const ns = two ? Math.min(rel, dv) - C.slide[0] * dtv : dv - C.slide[1] * dtv;
                    slid = smooth(C.pair[0], C.pair[1], S.dmax) * Math.min(deficit, C.ease * Math.min(q.moved, Math.max(0, ns)));
                    if (slid > 0) h = [h[0] + slid * tg[0], h[1] + slid * tg[1]];
                }
            }
            S.h = h;
        }
    }
    // 3. per leg, for a target T = v + s o: the knee for |T|; the thigh's least turn onto T; the swivel about hip -> T that
    //    puts the thigh's X square to the clip's foot forward, X(psi) . Fz = A cos psi + B sin psi + C = 0 (Rodrigues), its
    //    root of least |psi|, weighted by the foot's nearness to the floor (its heading matters only in contact). s = 1
    //    where the hip's table holds that thigh (the box and the coupled table, as applyHardwareDOF clamps it), else the
    //    largest s it holds (bisected): s = 0 is the clip's own clamped thigh, inside the table
    const kx = new THREE.Vector3(...LL.axis), ex = new THREE.Vector3(1, 0, 0), ez = new THREE.Vector3(0, 0, 1);
    const solve = (L, T, sw) => {
        const a = L.s.position, b = L.f.position;
        // |a + Rx(k) b|^2 = |a|^2 + |b|^2 + 2 (a.x b.x + P cos k + Q sin k), a = the knee from the hip and b = the ankle
        // from the knee at rest: the root inside the knee's range, clamped to it
        const P = a.y * b.y + a.z * b.z, Q = a.z * b.y - a.y * b.z;
        const c = (T.lengthSq() - a.lengthSq() - b.lengthSq() - 2 * a.x * b.x) / (2 * Math.hypot(P, Q));
        const k = Math.min(LL.range[1] * D, Math.max(LL.range[0] * D, Math.atan2(Q, P) + Math.acos(Math.max(-1, Math.min(1, c)))));
        const qs = new THREE.Quaternion().setFromAxisAngle(kx, k);
        const w = b.clone().applyQuaternion(qs).add(a);
        const u = T.clone().normalize();
        const q1 = new THREE.Quaternion().setFromUnitVectors(w.clone().applyQuaternion(L.qt).normalize(), u).multiply(L.qt);
        const X1 = ex.clone().applyQuaternion(q1), Fz = ez.clone().applyQuaternion(L.qF);
        const Cc = X1.dot(u) * Fz.dot(u), Ac = X1.dot(Fz) - Cc, Bc = u.clone().cross(X1).dot(Fz), R = Math.hypot(Ac, Bc);
        let psi = 0;
        if (R > 1e-9) {
            const ph = Math.atan2(Bc, Ac), g = -Cc / R;
            if (g >= 1) psi = ph;
            else if (g <= -1) psi = ph + Math.PI;
            else { const p1 = wrapPi(ph + Math.acos(g)), p2 = wrapPi(ph - Math.acos(g)); psi = Math.abs(p1) <= Math.abs(p2) ? p1 : p2; }
        }
        // (C3) the swivel guarded by its own conditioning: where the clip's foot forward lies near hip -> T (|Fz x u| -> 0,
        //      a foot pointing along its leg) a turn about hip -> T barely moves the foot's heading, so the root swings a
        //      long way for a few degrees of heading (the jump's take-off: 20 deg, the folded knee 107 mm in a frame). The
        //      swivel fades out by smooth(cond[0], cond[1], |Fz x u|); there the foot keeps the least turn's heading. (2.2)
        //      It comes back no faster than condRate a second (L.cap, this input's): at a landing |Fz x u| crosses the band
        //      in one frame, and the whole swivel at once twisted the planted foot 15-20 deg on the frame after touchdown
        const cnd = Fz.clone().cross(u).length(), wc = C.cond ? Math.min(smooth(C.cond[0], C.cond[1], cnd), L.cap ?? Infinity) : 1;
        psi = wrapPi(psi) * sw * wc;
        return { qt: new THREE.Quaternion().setFromAxisAngle(u, psi).multiply(q1), qs, u, w, psi, T, cnd, wc };
    };
    const inTable = (q, m) => {
        e.setFromQuaternion(q, 'XZY');
        const x = e.x / D, z = m * e.z / D, y = m * e.y / D, r = UL.range, cp = UL.coupled, tol = 1e-6;
        if (x < r.x[0] - tol || x > r.x[1] + tol || z < r.z[0] - tol || z > r.z[1] + tol || y < r.y[0] - tol || y > r.y[1] + tol) return false;
        return !cp || (z >= lerpTable(cp.x, cp.zmin, x) - tol && z <= lerpTable(cp.x, cp.zmax, x) + tol && y >= lerpTable(cp.z, cp.ymin, z) - tol);
    };
    for (const [side, L] of Object.entries(legs)) {
        const S = mem[side], o = new THREE.Vector3(S.h[0], 0, S.h[1]).applyQuaternion(Qi);
        // (the swivel's weight: whole for a foot within swivel[0] of the lower foot, none from swivel[1]; and, C2, whole for
        //  a foot moving with the clip's stance at any height, fading as it leaves it)
        const sw = C.swivel ? Math.max(1 - smooth(C.swivel[0], C.swivel[1], L.lo - low), S.wst || 0) : 1;
        const at = (s) => solve(L, o.clone().multiplyScalar(s).add(L.v), sw);
        L.o = o;
        L.sw = sw;
        L.cap = S.cap;
        let sol = at(1);
        L.se = 1;
        if (S.loaded && !inTable(sol.qt, L.m)) {
            let lo = 0, hi = 1;
            for (let i = 0; i < 16; i++) { const mid = 0.5 * (lo + hi); if (inTable(at(mid).qt, L.m)) lo = mid; else hi = mid; }
            L.se = lo;
            sol = at(lo);
        }
        L.t.quaternion.copy(sol.qt);
        L.s.quaternion.copy(sol.qs);
        L.wc = sol.wc;
    }
    // 4. the thighs and the knees clamped as applyHardwareDOF clamps them (the box, the coupled table), the stages solved
    applyHardwareDOF(vrm, [UL, LL]);
    // 5. each foot: the clip's sole normal in the new shin's frame, Rx(p) Rz(r) (0, -1, 0) = (sin r, -cos r cos p, -cos r
    //    sin p) (where the swivel held, the clip's whole foot turn); then clamped as applyHardwareDOF clamps the cardan
    const sole = (L) => {
        const n = new THREE.Vector3(0, -1, 0).applyQuaternion(L.qF).applyQuaternion(L.t.quaternion.clone().multiply(L.s.quaternion).invert());
        L.f.quaternion.setFromEuler(e.set(Math.atan2(-n.z, -n.y), 0, Math.asin(Math.max(-1, Math.min(1, n.x))), 'XZY'));
    };
    for (const L of Object.values(legs)) sole(L);
    applyHardwareDOF(vrm, [FT]);
    // 6. THE LEVEL: every foot raised by the same height. A loaded leg that cannot reach its target (the knee straight, T
    //    past the leg's length) leaves its foot high, and the grounding sets the body down on the lower foot, so that foot
    //    would float. So each foot the pass raised less than the most-raised LOADED foot is raised to it (its target lifted
    //    and the leg re-posed: a bent knee bends a little more; the lift weighted by the foot's height, kept inside the
    //    hip's table), and the grounding takes the common height back off the whole body: every foot where the clip has
    //    it, none slid
    if (C.level !== false) {
        const upH = new THREE.Vector3(0, 1, 0).applyQuaternion(Qi);
        const lowNow = (L, side) => {
            const RF = Qh.clone().multiply(L.t.quaternion).multiply(L.s.quaternion).multiply(L.f.quaternion);
            const ankle = L.f.position.clone().applyQuaternion(L.s.quaternion).add(L.s.position).applyQuaternion(L.t.quaternion)
                .add(L.t.position).applyQuaternion(Qh).add(hp);
            let y = lowestY(mem[side].foot, RF, ankle.y);
            if (L.to) y = Math.min(y, lowestY(mem[side].toes, RF.clone().multiply(L.qe), L.to.position.clone().applyQuaternion(RF).add(ankle).y));
            return y;
        };
        let R = -Infinity, lifted = false;
        for (const [side, L] of Object.entries(legs)) { L.rise = lowNow(L, side) - L.lo; if (mem[side].loaded) R = Math.max(R, L.rise); }
        for (const [side, L] of Object.entries(legs)) {
            L.lift = 0;
            // (weighted by the foot's height as the swivel is: whole within swivel[0] of the lower foot, so on every loaded
            //  foot; none from swivel[1]: a foot that high has no floor to float over, and a folded raised leg's lift only
            //  pushed its thigh out of the table, the ladder's knee thrown 24 mm for a frame)
            if (!Number.isFinite(R) || (R - L.rise) * L.sw <= 1e-4) continue;
            const T0 = L.o.clone().multiplyScalar(L.se).add(L.v), atL = (x) => solve(L, T0.clone().addScaledVector(upH, x), L.sw);
            let lift = (R - L.rise) * L.sw, sol = atL(lift);
            if (!inTable(sol.qt, L.m)) {
                // (kept inside the hip's table, bisected; a leg the clamp already holds at the table's edge takes none)
                if (!inTable(atL(0).qt, L.m)) continue;
                let lo = 0, hi = 1;
                for (let i = 0; i < 16; i++) { const mid = 0.5 * (lo + hi); if (inTable(atL(lift * mid).qt, L.m)) lo = mid; else hi = mid; }
                lift *= lo;
                sol = atL(lift);
            }
            L.t.quaternion.copy(sol.qt);
            L.s.quaternion.copy(sol.qs);
            L.wc = sol.wc;
            L.lift = lift;
            lifted = true;
        }
        if (lifted) {
            applyHardwareDOF(vrm, [UL, LL]);
            for (const L of Object.values(legs)) if (L.lift) sole(L);
            applyHardwareDOF(vrm, [FT]);
        }
    }
    // 7. the offset carried to the next input: while the foot bears weight, shrunk to the share the table held (never
    //    grown, never turned: no give-back under a loaded foot); while it is up, as it was (the ease moves it); the memo
    for (const [side, L] of Object.entries(legs)) {
        const S = mem[side], kk = S.loaded ? L.se : 1;
        S.next = [S.h[0] * kk, S.h[1] * kk];
        S.wc = L.wc;
        L.Mm.t = { in: L.qt, out: L.t.quaternion.clone() };
        L.Mm.s = { in: L.qs, out: L.s.quaternion.clone() };
        L.Mm.f = { in: L.qf, out: L.f.quaternion.clone() };
        if (stats) {
            const k = side + 'LegClearance';
            stats[k] = Math.max(stats[k] || 0, 2 * Math.acos(Math.min(1, Math.abs(L.qt.dot(L.t.quaternion)))) / D);
        }
    }
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
        // the COUPLED clamp (round 2, G13 (a), the lead's call in FIX1/DECISIONS 19): past -62 of extension the radial
        // corner opens (background through the chassis / the yoke's lower C-ring, view 40's family), so deviation's lower
        // limit rises with extension. Rows {flexion, dev_min, dev_max} (deg), linear in flexion between rows, the box's
        // own limits outside them; measured over all 48 probe views on round 2's lows (FIX2/BUILD/an/g13_fit.json: a
        // HOLE of 100 px, ~1 mm2, or more), less a 1 deg margin. BUILD/out/wrist_coupled.json carries the same rows for
        // the film's key check. Both hands alike, in the anatomical sense: wristSolve reads the rows in the left hand's
        // sense on both (the right's raw flexion and deviation through initArmDOF's W.sgnA / W.sgnD, the json's raw_sign)
        wristCoupled: [
            { flexion: -70, dev_min: -3, dev_max: 12 }, { flexion: -68, dev_min: -5, dev_max: 12 },
            { flexion: -66, dev_min: -5, dev_max: 12 }, { flexion: -65, dev_min: -7, dev_max: 12 },
            { flexion: -64, dev_min: -7, dev_max: 12 }, { flexion: -62, dev_min: -9, dev_max: 12 },
            { flexion: -61, dev_min: -12, dev_max: 12 }, { flexion: -60, dev_min: -12, dev_max: 12 },
        ],
        // the wrist's TURN LIMIT (VERIFY3 part B1b, 11-05; the lead's call, FIX1/DECISIONS 24.1): wristSolve takes the
        // natural branch (flexion within +-90) every frame and holds no branch; the hand turns at most the ask's own turn
        // since the last input it solved (the frame before, in a frame loop that feeds the clip's pose: keepArmPose)
        // plus `turn` deg toward it. The natural branch is continuous but at its three cuts (the
        // split's roll and deviation wrapping at +-180, the gimbal at flexion +-90), where alone it turns the hand up to
        // 180 deg in a frame; there the limit spreads that turn over a few frames. `jump` (deg): an input that moved more
        // than this since the frame before is a cut (a new shot, a loop's seam, a test's next pose), and takes the natural
        // branch at once, as a fresh start. MEASURED over every stock clip, the legs' crossfades, the vault's speeds and
        // fresh starts and C4's sequences (FIX2/verify3/wrist2, scan_N): the natural branch turns the hand at most 4.8 deg
        // over its ask in a frame in a clip alone and 19.6 in the controller's fastest fade, so 25 (B1's margin for the
        // wrist's own share) never acts there, and no ask comes nearer a cut than 19.7 deg; a wrist's ask moves at most
        // 64.4 deg in a frame in a fade and up to 121.7 at the one-shot clips' seams, so 90 keeps every fade continuous.
        // KNOWN (VERIFY3 part B1c; no clip does either): an input that moved more than `jump` is a cut and is not
        // limited, so the hand's turn there can exceed the ask's by up to 90 deg; an ask that hovers at a cut (dithers
        // across it frame after frame) is chased within the allowance, the hand turning up to `turn` deg a frame for as
        // long as it hovers. The limit counts frames, not seconds: at a high step rate it spreads a cut over less time
        wristLimit: { turn: 25, jump: 90 },
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
    // (round 2, N-i: initLegDOF's guard, REVIEW_HIP P1) a second call would re-read the pitch helpers' rests and the
    // wrist stages' (initWrist's Lr / Ld) from nodes the solve has posed, silently, and the constraints it removed the
    // first time are gone: so a second call keeps the first record (and its elbow; the hinges it is given now are not read)
    if (_arms.has(vrm)) {
        console.warn('[robot_dof] initArmDOF: called twice for this VRM: the first record is kept (the arm\'s and wrist\'s stage rests are read once, at load)');
        return _arms.get(vrm);
    }
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
    // (round 2: the coupled wrist clamp is not symmetric about 0, so each wrist reads ARM.wristCoupled in the LEFT's sense.
    //  The right's stages, built from its own drum's X and mirrored into the left's frame, can come out with EA or ED
    //  reversed: sgnA / sgnD are +1 or -1 against the left's axes. The box clamp was symmetric and never needed them)
    const WL = st.left && st.left.wrist, WR = st.right && st.right.wrist;
    if (WL) { WL.sgnA = 1; WL.sgnD = 1; }
    if (WR) {
        WR.sgnA = WL && vdot(WL.EA, WR.EA) < 0 ? -1 : 1;
        WR.sgnD = WL && vdot(WL.ED, WR.ED) < 0 ? -1 : 1;
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
// the stages' basis q is Euler 'XYZ' (roll a, flexion b, deviation c), split as three.js splits it (its flexion within
// +-90: the NATURAL branch), each angle clamped; the hand turns toward that as fast as ARM.wristLimit allows (VERIFY3
// part B1b). q is set to the result; W.a / W.b / W.c keep the stages' angles (rad), W.asked the split's
// the coupled wrist clamp (round 2): deviation's range [lo, hi] (deg) at flexion bDeg, linear in flexion between
// ARM.wristCoupled's rows, the box's own limits (ARM.wristDev) outside them
export function wristDevRange(bDeg) {
    const R = ARM.wristCoupled, box = ARM.wristDev;
    if (!R || !R.length || bDeg < R[0].flexion || bDeg > R[R.length - 1].flexion) return box;
    let i = 1;
    while (i < R.length - 1 && bDeg > R[i].flexion) i++;
    const r0 = R[i - 1], r1 = R[i], t = (bDeg - r0.flexion) / ((r1.flexion - r0.flexion) || 1);
    return [Math.max(box[0], r0.dev_min + t * (r1.dev_min - r0.dev_min)),
            Math.min(box[1], r0.dev_max + t * (r1.dev_max - r0.dev_max))];
}

// (VERIFY3 part B1b: THE NATURAL BRANCH, AND A TURN LIMIT AT ITS CUTS. B1's continuity kept the branch nearer the last
//  output, and in every continuous run of the set that was the natural branch (scan_N: 0 frames apart in 827 runs), while
//  its memo held the far one after a fresh start mid-vault and let go only by a flip. So the natural branch is taken every
//  frame: a fresh start or a cut lands where a continuous run is, and a reachable ask is solved exactly. It is continuous
//  but at three cuts, where alone it turns the hand up to 180 deg in a frame. So each hand keeps a memo (W.memo, in
//  initArmDOF's per-VRM record): the last input and output in the stages' basis and the output's angles. A new input turns
//  the hand at most its own turn since the last input plus ARM.wristLimit.turn: a step from the last output's angles
//  toward the natural branch's, inside the stops (the box is convex in the stages' angles; the deviation re-clamped in the
//  coupled range at the stepped flexion), the largest within that. Only a cut asks more, and no clip comes within 19.7 deg
//  of one. An input that moved more than ARM.wristLimit.jump takes the natural branch at once (a cut). An input equal to
//  the last OUTPUT (a second call in the same frame) returns the last solution and changes nothing; the last INPUT
//  again is not returned early, so a step under way goes on while a clip holds its pose. That
//  needs the frame loop to feed the clip's pose (keepArmPose / restoreArmPose, VERIFY3 part B1c): three's mixer does not
//  write a held key, and the pass would otherwise read its own output there, return early and freeze the step)
const qAngle = (p, q) => 2 * Math.acos(Math.min(1, Math.abs(p.dot(q))));
function wristSolve(q, W) {
    const THREE = globalThis.THREE;
    const e = new THREE.Euler(), qb = W.Bi.clone().multiply(q).multiply(W.B);
    const M = W.memo || null, L = ARM.wristLimit;
    if (M && Math.abs(qb.dot(M.out)) > 1 - 1e-12) {
        W.a = M.a; W.b = M.b; W.c = M.c; W.asked = M.asked;
        q.copy(M.out).premultiply(W.B).multiply(W.Bi);
        return M;
    }
    e.setFromQuaternion(qb, 'XYZ');
    const lim = (x, r) => Math.min(r[1] * D, Math.max(r[0] * D, x));
    // the natural branch: three.js's own split, its flexion within +-90 (asin)
    const a0 = e.x, b0 = e.y, c0 = e.z;
    // (round 2: the flexion clamped in the box first, then the deviation in the coupled range at that flexion, both
    //  read in the left's sense: W.sgnA / W.sgnD, initArmDOF)
    const sA = W.sgnA ?? 1, sD = W.sgnD ?? 1;
    const a = lim(a0, ARM.wristRoll), b = lim(b0, ARM.wristFlex), dl = wristDevRange(sA * b / D);
    const c = lim(c0, sD > 0 ? dl : [-dl[1], -dl[0]]);
    let s = { a, b, c, asked: [a0, b0, c0] };
    const qo = new THREE.Quaternion().setFromEuler(e.set(a, b, c, 'XYZ'));
    if (M && L && qAngle(qb, M.in) <= L.jump * D) {
        const allow = qAngle(qb, M.in) + L.turn * D;
        if (qAngle(qo, M.out) > allow) {
            // a cut: the largest step from the last output's angles toward these that turns the hand at most `allow`
            const at = (u) => {
                const bu = M.b + u * (b - M.b), du = wristDevRange(sA * bu / D);
                return [M.a + u * (a - M.a), bu, lim(M.c + u * (c - M.c), sD > 0 ? du : [-du[1], -du[0]])];
            };
            let lo = 0, hi = 1;
            for (let i = 0; i < 30; i++) {
                const m = (lo + hi) / 2, v = at(m);
                if (qAngle(qo.setFromEuler(e.set(v[0], v[1], v[2], 'XYZ')), M.out) <= allow) lo = m; else hi = m;
            }
            const v = at(lo);
            s = { a: v[0], b: v[1], c: v[2], asked: [a0, b0, c0], limited: true };
            qo.setFromEuler(e.set(v[0], v[1], v[2], 'XYZ'));
        }
    }
    W.a = s.a; W.b = s.b; W.c = s.c; W.asked = s.asked;
    W.memo = { in: qb.clone(), out: qo.clone(), a: s.a, b: s.b, c: s.c, asked: s.asked };
    q.copy(qo).premultiply(W.B).multiply(W.Bi);
    return s;
}

// THE CLIP'S POSE FOR THE ARM PASS, EVERY FRAME (VERIFY3 part B1c, 11-05; the lead's call, FIX2/BRIEF_b2.md call 2). three's
// mixer writes a bone only when its mixed value changed since its last write (PropertyMixer.apply), and the passes write
// their solve into the same normalized bones, so on a held key the arm pass read its own output as the clip's ask: a wrist
// step under way froze, a held hand took its forearm's twist again every frame (climbLedge's left: 87 deg over the clip)
// and a held forearm lost its twist (ask_me's right at 24 fps: a 93 deg pop). keepArmPose(vrm), right after
// mixer.update, keeps the clip's pose of the bones the arm pass reads (the clavicles, which rehomeBody folds into the upper
// arms, the upper arms, the forearms, the hands); restoreArmPose(vrm), first in the next frame (after any
// resetNormalizedPose, before any clip switch and before mixer.update), puts it back, so a bone the mixer leaves holds the
// clip's value, not the pass's. A frame where the mixer writes every bone is the same with them or without:
//   restoreArmPose(vrm); mixer.update(dt); keepArmPose(vrm); rehomeBody(...); ...; applyArmDOF(...); ...
// (a clip switched to after the restore takes the clip's pose as its start, as the mixer reads it; KNOWN: a clip without a
//  track for one of these bones leaves it at the pose kept last)
export const ARM_POSE_BONES = ['Shoulder', 'UpperArm', 'LowerArm', 'Hand'].flatMap((b) => ['left' + b, 'right' + b]);
const _armPose = new WeakMap();
export function keepArmPose(vrm) {
    let k = _armPose.get(vrm);
    if (!k) {
        const nodes = ARM_POSE_BONES.map((n) => vrm.humanoid.getNormalizedBoneNode(n)).filter(Boolean);
        _armPose.set(vrm, (k = { nodes, qs: nodes.map((o) => o.quaternion.clone()) }));
    }
    k.nodes.forEach((o, i) => k.qs[i].copy(o.quaternion));
}
export function restoreArmPose(vrm) {
    const k = _armPose.get(vrm);
    if (k) k.nodes.forEach((o, i) => o.quaternion.copy(k.qs[i]));
}

// resetArmDOF(vrm[, side]): the next applyArmDOF solves that VRM's wrists (or the one hand, 'left' or 'right') as a fresh
// load does: their turn limit's memo is cleared (VERIFY3 part B1c). For a cut or a seek (a new shot, a jump in the clip's
// time), and for a tool that poses unrelated draws in turn on one VRM (each draw its own solve). Other VRMs, the other
// hand, the shoulder's pitch stage (it turns at its rate, by dt) and the kept clip pose (keepArmPose) are left as they are
export function resetArmDOF(vrm, side) {
    const st = _arms.get(vrm);
    if (!st) return;
    for (const s of side ? [side] : ['left', 'right']) if (st[s]?.wrist) delete st[s].wrist.memo;
}

// clearance: applyArmClearance's turn-out (deg), applied first; it is part of the contract, not the caller's choice
// (the verifier, 10-19: without it the hanging forearm meets the hip dome at a side bend of 8 deg, inside SPINE_RANGE's
// 15). 0 only for tests of the arm's stages alone
export function applyArmDOF(vrm, stats, dt, clearance = 8) {
    const THREE = globalThis.THREE;
    if (clearance) applyArmClearance(vrm, clearance);
    const H = vrm.humanoid, A = ARM;
    let st = _arms.get(vrm);
    if (!st) {
        // (VERIFY3 part B1c) once per VRM: a VRM nobody initialized is initialized here, from the pose it has now
        console.warn('[robot_dof] applyArmDOF: initArmDOF(vrm, hinges) was not called at load: initialized now, without the ' +
            'hinges (the elbow on ARM\'s constants) and from the pose the VRM has now');
        st = initArmDOF(vrm);
    }
    const elbow = st.elbow;
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
