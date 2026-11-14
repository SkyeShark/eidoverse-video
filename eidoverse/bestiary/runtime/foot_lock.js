// (C3b STAGED, 11-08) foot_lock.js: THE PLANTED FOOT STAYS WHERE IT LANDED. A pass after the controller's update (the
// clip, the vertical foot IK, vrm.update) for any humanoid VRM it walks.
//
// WHY (measured, C3b): every human walk film since H4 (11-01) slid each planted foot 10-21 mm per step (the r09 measure,
// the foot bone over a planted run), the same with and without the robot hand: the controller's, not the graft's. The
// slide is mostly SIDEWAYS and OUTWARD (F: L +5..+9 mm, R -10..-13 mm across her heading; M: L +9..+13, R -9..-15),
// with some creep along it (F L +13..+16): the walk clip plays in place, so the hips' own sway and the stride's mismatch
// with the body's straight, tread-synced travel land in the planted foot. The foot IK (foot_ik.js) only grounds the
// foot in height ("vertical-only clamp preserves the horizontal foot-on-tread position"); nothing holds it in X / Z.
//
// WHAT: per leg, on the raw bones (upperLeg, lowerLeg, foot; toes when the rig has them):
//   * THE CONTACT is the ball of the foot: the toes joint (the foot bone on a rig without toes). It is the lowest joint
//     of the foot through the whole stance (the ankle joint stands 6-8 cm up), so pinning it lets the heel roll over it;
//   * PLANTED: walking (the caller's gate) and the contact within PLANT (12 mm, r09's band) of the ground it has shown
//     (its running minimum, risen at RISE m/s so a new floor height is learned);
//   * the LOCK: at the plant, the contact's ground position; while planted the correction (lock - contact) eases in
//     over EASE_IN s; at lift-off it decays with RELEASE s (the swing carries it off, no snap);
//   * the correction is applied by a TWO-BONE IK on the leg: the knee's bend from the law of cosines in the leg's own
//     plane (its pole kept), then the thigh turned onto the target; the foot's world rotation restored (the sole as the
//     clip and the foot IK left it). Heights are never changed: the foot IK's grounding stands.
// The correction is capped at MAX (40 mm): a lock that far off is a turn or a stop, released instead.
//   const L = createFootLock(vrm, THREE);   each frame after ctrl.update:  applyFootLock(L, dt, walking)  -> stats
export function createFootLock(vrm, THREE, opts = {}) {
    const raw = (n) => vrm.humanoid.getRawBoneNode(n);
    const legs = {};
    for (const [s, side] of [['L', 'left'], ['R', 'right']]) {
        const thigh = raw(side + 'UpperLeg'), shin = raw(side + 'LowerLeg'), foot = raw(side + 'Foot');
        if (!thigh || !shin || !foot) continue;
        legs[s] = { thigh, shin, foot, toes: raw(side + 'Toes'), ground: null, planted: false, lock: null, w: 0,
            corr: new THREE.Vector2(), steps: 0, maxCorr: 0 };
    }
    return { THREE, legs, PLANT: opts.plant ?? 0.012, RISE: opts.rise ?? 0.05, EASE_IN: opts.easeIn ?? 0.05,
        RELEASE: opts.release ?? 0.08, MAX: opts.max ?? 0.04, frames: 0 };
}

const _v = {};
function vec(S, k) { return (_v[k] ||= new S.THREE.Vector3()); }
function quat(S, k) { return (_v['q' + k] ||= new S.THREE.Quaternion()); }

// turn bone b by the WORLD rotation R about its own origin (its parent's world matrix current)
function turnWorld(S, b, R) {
    const qw = b.getWorldQuaternion(quat(S, 'a'));
    const qp = b.parent ? b.parent.getWorldQuaternion(quat(S, 'b')) : quat(S, 'b').identity();
    const nq = R.clone().multiply(qw);
    b.quaternion.copy(qp.invert().multiply(nq));
    b.updateMatrixWorld(true);
}

function solveLeg(S, g, target) {
    const T = S.THREE;
    const H = g.thigh.getWorldPosition(new T.Vector3());
    const K = g.shin.getWorldPosition(new T.Vector3());
    const A = g.foot.getWorldPosition(new T.Vector3());
    const footQ = g.foot.getWorldQuaternion(new T.Quaternion());
    const l1 = K.distanceTo(H), l2 = A.distanceTo(K);
    const d = Math.min(target.distanceTo(H), l1 + l2 - 1e-5);
    // 1. the knee: its interior angle for the new reach, about the leg's own bend axis (the pole kept)
    const u = K.clone().sub(H), w = A.clone().sub(K);
    let axis = new T.Vector3().crossVectors(u, w);
    if (axis.lengthSq() < 1e-12) axis = new T.Vector3(1, 0, 0).applyQuaternion(g.thigh.getWorldQuaternion(new T.Quaternion()));
    axis.normalize();
    const cosNow = Math.max(-1, Math.min(1, u.clone().negate().normalize().dot(w.clone().normalize())));
    const cosNew = Math.max(-1, Math.min(1, (l1 * l1 + l2 * l2 - d * d) / (2 * l1 * l2)));
    // (a turn of +phi about u x w carries the shin further from the thigh's line: the interior angle closes by phi)
    const dKnee = Math.acos(cosNow) - Math.acos(cosNew);
    if (Math.abs(dKnee) > 1e-7) turnWorld(S, g.shin, new T.Quaternion().setFromAxisAngle(axis, dKnee));
    // 2. the thigh: the hip-to-ankle line onto the hip-to-target line
    const A2 = g.foot.getWorldPosition(new T.Vector3());
    const from = A2.sub(H).normalize(), to = target.clone().sub(H).normalize();
    turnWorld(S, g.thigh, new T.Quaternion().setFromUnitVectors(from, to));
    // 3. the foot's world rotation as it was
    const sq = g.shin.getWorldQuaternion(new T.Quaternion());
    g.foot.quaternion.copy(sq.invert().multiply(footQ));
    g.foot.updateMatrixWorld(true);
}

export function applyFootLock(S, dt, walking) {
    const T = S.THREE;
    S.frames++;
    const out = {};
    for (const [s, g] of Object.entries(S.legs)) {
        const C = (g.toes || g.foot).getWorldPosition(vec(S, 'c' + s));      // the contact: the ball of the foot
        const low = C.y;
        g.ground = g.ground === null ? low : Math.min(low, g.ground + S.RISE * dt);
        const planted = walking && low - g.ground < S.PLANT;
        if (planted) {
            if (!g.planted) {
                g.lock = new T.Vector2(C.x + g.corr.x, C.z + g.corr.y);       // (the residual kept: no pop)
                g.w = 0;
                g.steps++;
            }
            g.w = Math.min(1, g.w + dt / S.EASE_IN);
            const want = new T.Vector2(g.lock.x - C.x, g.lock.y - C.z);
            if (want.length() > S.MAX) { g.lock = new T.Vector2(C.x, C.z); want.set(0, 0); }
            g.corr.copy(want.multiplyScalar(g.w).add(g.corr.clone().multiplyScalar(1 - g.w)));
        } else {
            g.corr.multiplyScalar(Math.exp(-dt / S.RELEASE));
        }
        g.planted = planted;
        const m = g.corr.length();
        g.maxCorr = Math.max(g.maxCorr, m);
        let resid = 0;
        if (m > 1e-5) {
            const A = g.foot.getWorldPosition(new T.Vector3());
            const tgt = new T.Vector3(A.x + g.corr.x, A.y, A.z + g.corr.y);
            solveLeg(S, g, tgt);
            resid = g.foot.getWorldPosition(new T.Vector3()).distanceTo(tgt);
        }
        g.maxResid = Math.max(g.maxResid || 0, resid);
        if (m > 1e-5) {
            const h = (g.hist ||= []);
            h.push([S.frames, Math.round(1e4 * m) / 10, Math.round(1e4 * resid) / 10, planted ? 1 : 0]);
            // (11-09) capped: the newest ~8k entries a leg (over 4 min of walking at 30 fps, every film's measure), dropped
            // 1k at a time, so a world that walks for hours never grows it without bound
            if (h.length > 9216) h.splice(0, 1024);
        }
        out[s] = { planted, corr_mm: 1000 * m, resid_mm: 1000 * resid };
    }
    return out;
}
