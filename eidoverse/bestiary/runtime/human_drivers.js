// human_drivers.js -- THE HUMAN'S PRE-VRM DRIVERS (L1, 11-08): the arm opening and the twist joints, run in the
// controller's existing pre-VRM hook (EidoverseRobotController.onPreVrmUpdate: after the clip and the IK, before
// vrm.update), with the face driver (human_face_eval.js) first. The order is the docs': the face driver, the arm
// opening, then the twists (the opening turns the upper arm about the forward axis, so its roll is unchanged, but the
// twists read the final quaternions). The two functions are VERBATIM from their staged docs:
//   * driveTwists: work/bestiary/human/h4b/rig/patches/twist_contract.md (the rig builder's contract: NORMALIZED
//     sources, the twist joints' raw nodes written, the glb's extras.bestiary.human.twists records; vrm.update
//     leaves the twist nodes alone, they are no humanoid bones). The weights are built for THIS rule;
//   * openArms: work/bestiary/human/h4b/rig/patches/arm_open_runtime.md (extras.bestiary.human.gait.arm_open_deg).
//
//   const face = makeFaceEval(vrm, human.face);                 // human = gltf.userData...extras.bestiary.human
//   installHumanDrivers(vrm, ctrl, human, { face });              // once, after the controller is made
const THREE = globalThis.THREE;

// three r184; vrm = the human's VRM; tw = gltf extras.bestiary.human.twists
const VRM_OF = { hand_L: 'leftHand', hand_R: 'rightHand', foot_L: 'leftFoot', foot_R: 'rightFoot',
                 upperarm_L: 'leftUpperArm', upperarm_R: 'rightUpperArm', thigh_L: 'leftUpperLeg', thigh_R: 'rightUpperLeg' };
export function driveTwists(vrm, tw) {
  for (const [name, r] of Object.entries(tw)) {
    const node = vrm.scene.getObjectByName(name);
    const src = vrm.humanoid.getNormalizedBoneNode(VRM_OF[r.source]);
    if (!node || !src) continue;
    const q = src.quaternion, a = r.axis_local;
    let tau = 2 * Math.atan2(q.x * a[0] + q.y * a[1] + q.z * a[2], q.w);
    tau = Math.atan2(Math.sin(tau), Math.cos(tau));
    node.quaternion.setFromAxisAngle(new THREE.Vector3(a[0], a[1], a[2]), r.gain * tau);
  }
}

// vrm = the human's VRM; deg = gltf extras.bestiary.human.gait.arm_open_deg (F 5.0, M 2.5 for the baselines)
export function openArms(vrm, deg) {
  if (!deg) return;
  for (const [side, sg] of [['left', 1], ['right', -1]]) {
    const n = vrm.humanoid.getNormalizedBoneNode(side + 'UpperArm');
    if (!n) continue;
    const dir = new THREE.Vector3(sg, 0, 0).applyQuaternion(n.quaternion);   // the arm in its parent's frame
    const hang = Math.asin(Math.max(-1, Math.min(1, -dir.y))) * 180 / Math.PI; // degrees under the horizontal
    const w = Math.max(0, Math.min(1, (hang - 30) / 30));                      // 0 at 30 deg or less, 1 at 60 or more
    if (w <= 0) continue;
    n.quaternion.premultiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), sg * deg * w * Math.PI / 180));
  }
}

// the three in the hook, in order; a hook already set on the controller runs first (it was there before)
export function installHumanDrivers(vrm, ctrl, human, { face = null, arms = true, twists = true } = {}) {
  const prev = ctrl.onPreVrmUpdate;
  const deg = arms ? (human?.gait?.arm_open_deg ?? 0) : 0;
  const tw = twists ? (human?.twists || {}) : {};
  ctrl.onPreVrmUpdate = (...a) => {
    if (prev) prev(...a);
    if (face) face.update();
    openArms(vrm, deg);
    driveTwists(vrm, tw);
  };
  return ctrl.onPreVrmUpdate;
}
