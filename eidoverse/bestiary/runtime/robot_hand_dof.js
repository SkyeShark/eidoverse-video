// (C3 STAGED, 11-08) robot_hand_dof.js: the HAND pass of my robot's hardware-DOF module, for a robot hand GRAFTED on
// another creature (the human's wrist, cyborg_robot/c3). Copied VERBATIM from the robot body's eidoverse/
// claude_robot_dof.js (read only): its helpers (lines 107-113, 856-865) and THE HANDS
// (1258-1471: initHandDOF, handDebug, applyHandDOF), then Edits marked (C3): the name map.
// (C3-MOTION, 11-09) the copy above stays as it is; APPENDED below it (marked C3-MOTION): the rest of what the body's
// hardware does to a hand, so the creature's clips move the grafted hand only as the hand is built to move: THE WRIST's
// three stages (roll +-90 about the forearm, the drum's flexion +-70, the deviation pin +-12 with its coupled rows, the
// turn limit at the split's cuts), copied from the same file's THE ARMS (ARM's wrist rows, initWrist, wristDevRange,
// wristSolve, keepArmPose / restoreArmPose / resetArmDOF, applyArmDOF's hand step), with the graft's names and axes;
// the thumb's rotor kept continuous where the clip's thumb points out of its reach (no 60 deg spin in a frame); the
// fingers' tips held off the palm (a combined limit measured on the hand's own lows); the forearm's twist joints left off
// a grafted hand (the roll stage turns the hand inside the house; the skin collar rides the forearm with the house).
// (C3-MOTION round 2, 11-09, after check 1) the rotor's continuity only rate-limits the drawn rotor (no hold, nothing
// written into the copied solve); APPENDED at the end: the post-pass applyGraftContact, the thumb kept off the fingers
// and the hand kept off the creature's own skin, on the frame's final pose.
// For the creature: initGraftDOF(vrm, c3) once at load; each frame
// restoreArmPose(vrm) before the clip's mixer, keepArmPose(vrm) right after it, applyGraftDOF(vrm, stats, dt) before
// vrm.update; the twist joints driven from graftTwists(twists, vrm, c3); applyGraftContact(vrm, stats) LAST, once the
// frame's pose is final (after vrm.update, the foot lock and the twist joints).
const D = Math.PI / 180;
function twistAbout(q, a, out) {
    // the twist of q about the unit axis a: (a (q.v . a), q.w) normalised; identity when q is a pure swing
    const p = q.x * a[0] + q.y * a[1] + q.z * a[2];
    out.set(a[0] * p, a[1] * p, a[2] * p, q.w);
    const n = Math.hypot(out.x, out.y, out.z, out.w);
    if (n < 1e-9) out.set(0, 0, 0, 1); else out.set(out.x / n, out.y / n, out.z / n, out.w / n);
    return out;
}
const vdot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const vcross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const vunit = (a) => { const n = Math.hypot(a[0], a[1], a[2]); return [a[0] / n, a[1] / n, a[2] / n]; };
const vrot = (v, k, t) => {                      // v turned by t about the unit axis k (Rodrigues)
    const c = Math.cos(t), s = Math.sin(t), kv = vcross(k, v), kd = vdot(k, v) * (1 - c);
    return [v[0] * c + kv[0] * s + k[0] * kd, v[1] * c + kv[1] * s + k[1] * kd, v[2] * c + kv[2] * s + k[2] * kd];
};
const smooth = (e0, e1, x) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
const wrapPi = (a) => a - 2 * Math.PI * Math.floor((a + Math.PI) / (2 * Math.PI));
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

// (C3) names: the robot's stage name -> the node's name in this creature (a graft's extras.bestiary.c3.sides[s].names,
// e.g. { leftThumbRotor: 'thumb_g03_L' }); without it the robot's own names (the robot VRM itself)
export function initHandDOF(vrm, hinges, names = null) {
    const THREE = globalThis.THREE;
    vrm.scene.updateMatrixWorld(true);
    const H = vrm.humanoid, mgr = vrm.nodeConstraintManager, st = { hinges, side: {} };
    const meta = hinges.leftThumbMetacarpal, rot = hinges.leftThumbRotor;
    for (const side of ['left', 'right']) {
        const m = side === 'left' ? 1 : -1;
        const helper = vrm.scene.getObjectByName((names && names[side + 'ThumbRotor']) || (side + 'ThumbRotor')) || null;   // (C3)
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

// ======================================================================================================================
// (C3-MOTION, 11-09) APPENDED: THE WRIST AND THE GRAFT'S FRAME. Copied from the same file of the body
// (the robot body's eidoverse/claude_robot_dof.js, read only): ARM's wrist rows (885-919), initWrist (1000-1039),
// wristDevRange (1041-1055), qAngle + wristSolve (1057-1114), keepArmPose / restoreArmPose / resetArmDOF (1116-1151) and
// applyArmDOF's hand step (1203-1224); Edits in them marked (C3-MOTION). Why: C3 copied only the hand pass, so on the
// human the clips turned the chassis with the human wrist's whole turn: the stages followed only by their VRM roll
// constraints (each the twist of the hand's whole turn about its own axis, exact for roll + flexion only), nothing
// clamped the deviation pin or the drum, and the chassis ran off its pin into the drum and the yoke (C3-MOTION's frame
// logs, the walk: deviation asked to 27 deg against +-12, the chassis 8 deg off its pin, 4.3 mm into the yoke).

// the WRIST's rows of the body's ARM (its other rows, the shoulder's and the elbow's, are the creature's own arm here)
export const ARM = {
    wristRoll: [-90, 90],
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
};

const _arms = new WeakMap();

// THE WRIST's stages at load (fix round 1): the roll stage (WristRoll, on the forearm) and the drum (WristFlex, on the
// roll stage); their VRM roll constraints removed as the pitch helper's (applyArmDOF sets both each frame); their rest
// (local, and the parent's turn in the VRM's own frame, where the normalized bones are axis-aligned at rest, whatever
// carries vrm.scene) and their own axes, in the left's frame (the right's mirrored: a turn's axis (x, -y, -z)): EL the
// roll stage's Y, EA the drum's X (squared to EL: 0.019 deg off square in the delivered file), ED = EL x EA the deviation pin the
// drum carries (the hand's -Z: the pin from its back plate is that axis to 2e-5, the F5 skeptic). A VRM without the two
// stages keeps the roll-only clamp (applyArmDOF)
// (C3-MOTION) names: the graft's node names (c3 sides' names map, as initHandDOF's); hinges: the graft's hinge record in
// the creature's frame (c3.hinges_left_frame). A graft's stages rest world-aligned (every rest of the creature is), so
// their local Y and X are not the mechanism's axes there: EL is the roll stage's own constraint axis (read before the
// constraint goes; the rigid map put the robot's roll axis on it exactly) and EA the drum's pin from the hinge record
// (the robot's own axis and sense, carried by the rigid map: the coupled rows read flexion in that sense)
function initWrist(vrm, side, names = null, hinges = null) {
    const THREE = globalThis.THREE;
    const nm = (k) => (names && names[side + k]) || (side + k);                                             // (C3-MOTION)
    const roll = vrm.scene.getObjectByName(nm('WristRoll')) || null, flex = vrm.scene.getObjectByName(nm('WristFlex')) || null;
    if (!roll || !flex || flex.parent !== roll || !roll.parent) return null;
    const mgr = vrm.nodeConstraintManager;
    let removed = 0;
    const cAxis = {};                                                                                       // (C3-MOTION)
    if (mgr) {
        for (const c of [...mgr.constraints]) {
            if (c.destination !== roll && c.destination !== flex) continue;
            if (c.rollAxis) cAxis[c.destination === roll ? 'roll' : 'flex'] = c.rollAxis;                   // (C3-MOTION)
            if (mgr.deleteConstraint) mgr.deleteConstraint(c); else mgr.constraints.delete(c);
            removed++;
        }
    }
    const S = vrm.scene.getWorldQuaternion(new THREE.Quaternion()).invert();
    const inVrm = (o) => S.clone().multiply(o.getWorldQuaternion(new THREE.Quaternion()));
    const m = side === 'left' ? 1 : -1, mir = (u) => (m > 0 ? [u.x, u.y, u.z] : [u.x, -u.y, -u.z]);
    const Pr = inVrm(roll.parent), Pd = inVrm(roll), Wd = inVrm(flex);
    // (C3-MOTION) the graft's axes (above); the body's own where no hinge record is given
    const unitAxis = (k) => new THREE.Vector3(k === 'X' ? 1 : 0, k === 'Y' ? 1 : 0, k === 'Z' ? 1 : 0);
    const graft = !!(hinges && hinges.leftWristFlex && cAxis.roll && cAxis.flex);
    const EL = vunit(mir((graft ? unitAxis(cAxis.roll) : new THREE.Vector3(0, 1, 0)).applyQuaternion(Pd)));
    const ea = graft ? vunit(hinges.leftWristFlex.axis) : mir(new THREE.Vector3(1, 0, 0).applyQuaternion(Wd)), k = vdot(ea, EL);
    const EA = vunit([ea[0] - k * EL[0], ea[1] - k * EL[1], ea[2] - k * EL[2]]);
    const ED = vcross(EL, EA);
    // (C3-MOTION) the drum's constraint turned it about an axis along EA (either sense): how far off, for the record
    const drumOff = graft ? Math.acos(Math.min(1, Math.abs(vdot(vunit(mir(unitAxis(cAxis.flex).applyQuaternion(Wd))), EA)))) / D : null;
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
             a: 0, b: 0, c: 0, asked: [0, 0, 0], graft, drumOff };                                          // (C3-MOTION) graft, drumOff
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

// (C3-MOTION) THE GRAFT AT LOAD: the hand pass (initHandDOF, the copy above) and each side's wrist stages (initWrist, by
// the graft's names and axes), from the glb's own record (extras.bestiary.c3: its sides' names, its hinges in the
// creature's frame); the right in the left's frame (sgnA / sgnD: initArmDOF's round 2 lines, as there). Once per VRM
// (as initArmDOF: the stages' rests are read at load, before anything poses it; a second call keeps the first record)
export function initGraftDOF(vrm, c3) {
    if (_arms.has(vrm)) return _arms.get(vrm);
    const names = Object.assign({}, c3?.sides?.L?.names, c3?.sides?.R?.names);
    const hinges = c3?.hinges_left_frame || null;
    vrm.scene.updateMatrixWorld(true);
    const st = { names };
    for (const side of ['left', 'right']) st[side] = { wrist: initWrist(vrm, side, names, hinges) };
    if (hinges) st.hand = initHandDOF(vrm, hinges, names);
    const WL = st.left && st.left.wrist, WR = st.right && st.right.wrist;
    if (WL) { WL.sgnA = 1; WL.sgnD = 1; }
    if (WR) {
        WR.sgnA = WL && vdot(WL.EA, WR.EA) < 0 ? -1 : 1;
        WR.sgnD = WL && vdot(WL.ED, WR.ED) < 0 ? -1 : 1;
    }
    const w = (W) => W && { graft: W.graft, removed: W.removed, EL: W.EL.map((x) => +x.toFixed(5)), EA: W.EA.map((x) => +x.toFixed(5)),
        squareDeg: +W.squareDeg.toFixed(4), restDeg: W.restDeg == null ? null : +W.restDeg.toFixed(4),
        drumOff: W.drumOff == null ? null : +W.drumOff.toFixed(4), sgnA: W.sgnA, sgnD: W.sgnD };
    st.summary = { left: w(WL), right: w(WR), hand: !!(st.hand && st.hand.ok),
        rotorConstraintsRemoved: st.hand ? ['left', 'right'].map((s) => st.hand.side[s].removed) : null };
    _arms.set(vrm, st);
    st.summary.contact = initGraftContact(vrm, st);                                 // (round 2) the hand off the body
    return st;
}

// (C3-MOTION) THE WRIST EACH FRAME: applyArmDOF's hand step (the body's, above its shoulder's), for a hand grafted at
// a creature's wrist. The body re-homes its forearm's twist into the wrist roll first (its elbow is a pin, 05.12); a
// graft's forearm is the creature's own, with the house on it, so the hand's turn against that forearm goes to the
// stages as it is. The split in the mechanism's order, clamped (wristSolve), the hand recomposed on its deviation pin,
// the roll stage and the drum set from the clamped angles
export function applyGraftWrist(vrm, stats) {
    const THREE = globalThis.THREE;
    const st = _arms.get(vrm);
    if (!st) return;
    const H = vrm.humanoid;
    const q = new THREE.Quaternion(), r = new THREE.Quaternion(), qs = new THREE.Quaternion();
    const v = new THREE.Vector3(), ax = (a) => v.set(a[0], a[1], a[2]);
    // the right side in the left's frame and back (the x -> -x mirror conjugates a turn: its axis (x, -y, -z))
    const mirror = (src, m, out) => (m > 0 ? out.copy(src) : out.set(src.x, -src.y, -src.z, src.w));
    const note = (k, before, after) => {
        if (stats) stats[k] = Math.max(stats[k] || 0, 2 * Math.acos(Math.min(1, Math.abs(before.dot(after)))) / D);
    };
    for (const side of ['left', 'right']) {
        const m = side === 'left' ? 1 : -1, W = st[side] && st[side].wrist;
        const hand = H.getNormalizedBoneNode(side + 'Hand');
        if (!hand || !W) continue;
        mirror(hand.quaternion, m, q);
        const hb = q.clone();
        // the wrist's three stages: the split in the mechanism's order, clamped, the hand recomposed (wristSolve)
        wristSolve(q, W);
        mirror(q, m, hand.quaternion);
        note(side + 'Hand', hb, q);
        // the roll stage: a about EL in the forearm's rest frame; the drum: b about EA in the roll stage's (it rides
        // the roll stage, so its axis is carried); the hand then turns c about the pin against the drum
        mirror(r.setFromAxisAngle(ax(W.EL), W.a), m, qs);
        W.roll.quaternion.copy(W.PrI).multiply(qs).multiply(W.Pr).multiply(W.Lr);
        mirror(r.setFromAxisAngle(ax(W.EA), W.b), m, qs);
        W.flex.quaternion.copy(W.PdI).multiply(qs).multiply(W.Pd).multiply(W.Ld);
    }
}

// (C3-MOTION) THE ROTOR, CONTINUOUS. The copied thumb solve puts the metacarpal on the in-range pair (rotor alpha, CMC
// beta) whose direction is nearest the clip's; where the clip's thumb points out of that reach (back of the palm: a
// stock clip's relaxed or extended thumb), the nearest pair sits on the reach's edge and jumps from one end of the
// rotor's 0..60 to the other on a fraction of a degree of the clip's motion: C3-MOTION's logs counted 53 such turns of
// 15-60 deg in one frame over the library on the graft (the idle's first frames, the jump, the vault, a fist; the body's
// own pass, the same asks replayed through it read only, made 94). A rotor does not spin 60 deg in a frame for a thumb
// that barely moved. So, after the solve, the DRAWN rotor follows the solve's: exactly while the solve turns at most the
// clip's own metacarpal turn plus ROTOR.turn deg a frame (every continuous move, as on the body), and at that rate where
// the solve jumps (the wrist's turn limit, B1b, for the rotor; 10: a 60 deg re-seat over 6 frames), the CMC re-flexed
// for the best direction at the drawn rotor. The MCP and IP keep their turns against the metacarpal (their pins ride
// it). Per side; the first frame and a reset take the solve as it is.
// (round 2, after check 1) This pass draws; it never writes the copied solve's memory (its s.alpha / s.beta, the
// tie-break of its next solve), and it never HOLDS. Round 1's version held the drawn rotor while the solve turned faster
// than the clip's metacarpal (any gradual move, not only a jump) and wrote the held pair back into s.alpha / s.beta (in
// 'salute' the drawn rotor sat at 40-56 deg for ~50 frames, f4130-4184). Now the copied solve runs exactly as the body's own:
// the body's pass, given the clip's asks as the graft's mechanism meets them (conjugated by C3's rigid map, 26.31 deg about
// the hand's long axis), returns this solve to 0.12 deg over the whole library (c3_motion/r2: k04 conj=1). The drawn
// rotor differs from it only for the few frames of a rate-limited jump. That solve opposes the thumb (rotor 60) while
// 'salute' curls the index through its place, as the body's own pass would: THE THUMB OFF THE FINGERS (below) keeps the
// two apart
export const ROTOR = { turn: 10 };
const _rotor = new WeakMap();
function thumbAsks(vrm) {
    const THREE = globalThis.THREE;
    const out = {};
    for (const [side, m] of [['left', 1], ['right', -1]]) {
        const n = vrm.humanoid.getNormalizedBoneNode(side + 'ThumbMetacarpal');
        if (!n) continue;
        const q = n.quaternion;
        out[side] = m > 0 ? q.clone() : new THREE.Quaternion(q.x, -q.y, -q.z, q.w);
    }
    return out;
}
function rotorContinuity(vrm, asks, stats) {
    const THREE = globalThis.THREE;
    const st = _hands.get(vrm);
    if (!st || !st.ok) return;
    const H = vrm.humanoid, T = st.hinges;
    let mem = _rotor.get(vrm);
    if (!mem) _rotor.set(vrm, (mem = {}));
    const Yr = vunit(T.leftThumbRotor.axis);
    const P0 = vunit(vcross(vcross(Yr, T.leftThumbMetacarpal.axis), Yr));
    const range = (j) => [(j.deg[0] - j.flex_at_rest) * D, (j.deg[1] - j.flex_at_rest) * D];
    const bR = range(T.leftThumbMetacarpal);
    // the coupled limit, as the copied pass reads it (the metacarpal's heel on the stator's lip as the rotor opposes)
    const bMax = (a) => {
        const o = a / D + T.leftThumbRotor.flex_at_rest;
        const lim = o <= 40 ? 87 : o <= 50 ? 87 - 0.1 * (o - 40) : 86 - 0.7 * (o - 50);
        return Math.min(bR[1], (lim - T.leftThumbMetacarpal.flex_at_rest) * D);
    };
    const v = new THREE.Vector3(), ax = (a) => v.set(a[0], a[1], a[2]);
    const mirror = (src, m, out) => (m > 0 ? out.copy(src) : out.set(src.x, -src.y, -src.z, src.w));
    const q = new THREE.Quaternion(), qr = new THREE.Quaternion(), r = new THREE.Quaternion();
    for (const side of ['left', 'right']) {
        const m = side === 'left' ? 1 : -1, s = st.side[side];
        const mc = H.getNormalizedBoneNode(side + 'ThumbMetacarpal'), qa = asks[side];
        if (!mc || !qa) continue;
        const M = mem[side];
        if (!M) { mem[side] = { a: s.alpha, b: s.beta, ask: qa.clone() }; continue; }
        const dv = new THREE.Vector3(s.m0[0], s.m0[1], s.m0[2]).applyQuaternion(qa), d = [dv.x, dv.y, dv.z];
        const dirOf = (a, b) => vrot(vrot(s.m0, P0, b), Yr, a), miss = (a, b) => 1 - vdot(dirOf(a, b), d);
        const bestB = (a) => {                              // the CMC's best flexion with the rotor at a (1 deg grid, halving)
            let best = { b: bR[0], e: miss(a, bR[0]) };
            const hi = bMax(a);
            for (let b = bR[0]; b <= hi + 1e-9; b += D) { const e = miss(a, b); if (e < best.e) best = { b, e }; }
            for (let step = 0.5 * D; step > 0.01 * D; step /= 2) {
                for (const b of [best.b - step, best.b + step]) {
                    if (b < bR[0] || b > hi) continue;
                    const e = miss(a, b);
                    if (e < best.e) best = { b, e };
                }
            }
            return best.b;
        };
        const askTurn = 2 * Math.acos(Math.min(1, Math.abs(qa.dot(M.ask))));
        // the drawn pair: the solve's (s.alpha / s.beta, left as the copied solve wrote them), or, past the turn limit,
        // the drawn rotor stepped toward it (round 2: no hold, no write-back)
        let a = s.alpha, b = s.beta, limited = false;
        const allow = askTurn + ROTOR.turn * D;
        if (Math.abs(a - M.a) > allow + 1e-9) { a = M.a + Math.sign(a - M.a) * allow; b = bestB(a); limited = true; }
        if (limited) {
            const before = new THREE.Quaternion();
            mirror(mc.quaternion, m, before);
            qr.setFromAxisAngle(ax(Yr), a);
            q.copy(qr).multiply(r.setFromAxisAngle(ax(P0), b));
            mirror(q, m, mc.quaternion);
            if (s.helper) {
                mirror(qr, m, r);
                s.helper.quaternion.copy(s.Pinv).multiply(r).multiply(s.P).multiply(s.Lrest);
            }
            if (stats) {
                stats[side + 'RotorLimited'] = (stats[side + 'RotorLimited'] || 0) + 1;
                stats[side + 'RotorMoved'] = Math.max(stats[side + 'RotorMoved'] || 0, 2 * Math.acos(Math.min(1, Math.abs(before.dot(q)))) / D);
            }
        }
        mem[side] = { a, b, ask: qa.clone(), limited };
    }
}

// (C3-MOTION) THE FINGERS' TIPS ON THE PALM. The hinge table holds each pin 2-4 deg inside its own first contact (05.31)
// and couples the little finger's MCP + PIP (<= 93, above); nothing held a finger curling into the palm, and the clips'
// fists do: C3-MOTION's logs, the index's tip 3.7 mm into the chassis at MCP 89 / PIP 92 / DIP 44 ('fist'), the ring's
// 6.4 mm ('crazy'); the body's own pass replayed on the same asks curls within 4 % of the graft. MEASURED on the hand's
// own lows (c3_motion/tools/m04_finger_sweep.py on the C3 builds, F and M within 0.3 deg: the rigid map is a turn and a
// uniform scale, so these are the body's own angles): per finger, the DIP at the first contact of its links with the
// chassis or with its own links, the MCP and PIP on a 5 deg grid; ROWS = MCP from FROM to 95 by 5 (the rows below have
// no contact), COLUMNS = PIP 0..95 by 5 (past 95 the last two extended), VALUES = that DIP (deg, hardware; 95 = no contact
// in the range). A finger past its row-and-column's DIP less MARGIN (05.31's 2-4 inside contact) gives the excess back off
// its three pins equally, each held at its lower stop (the little finger's MCP + PIP rule, for three pins): the fist
// closes onto the palm, not through it
export const TIP_LIMIT = {
    step: 5, margin: 2.5, from: { Index: 60, Middle: 60, Ring: 60, Little: 55 },
    rows: {
        Index: [[95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 94.8], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 82.8], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 89.9, 71.2], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 75.1, 59.8], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 78.3, 62.1, 48.2], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 80.4, 63.5, 48.6, 34.4], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 81.3, 63.9, 47.8, 34.2, 21.5], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 80.4, 61.2, 46.9, 33.7, 21.2, 9.6]],
        Middle: [[95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 94.8], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 78.9], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 84.5, 68.1], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 90.5, 71.5, 57.2], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 94.8, 74.3, 59.3, 45.7], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 76.1, 60.6, 46.9, 33.7], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 76.7, 61, 47.7, 34.8, 22.3], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 76.1, 61.2, 48.1, 34.2, 21.8, 9.7]],
        Ring: [[95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 94.8], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 78.9], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 84.5, 68.1], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 90.5, 71.5, 57.2], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 94.8, 74.3, 59.3, 45.7], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 76.1, 60.6, 46.9, 33.7], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 76.7, 61, 47.3, 34, 23], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 76.1, 60.6, 46.9, 36.7, 24.5, 11.3]],
        Little: [[95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 91.8], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 80.3], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 86.2, 69.6], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 92.6, 73.7, 59.5], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 77.3, 62.5, 48.7], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 80.2, 64.7, 50.7, 37], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 82.1, 66, 52, 38.1, 25.3], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 82.8, 66.4, 52.3, 38.6, 25.7, 14.1], [95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 95, 82.1, 66, 52, 38.1, 26.1, 14.4, 1.9]],
    },
};
// the DIP's limit (deg, hardware) at MCP p and PIP i: bilinear in the table (the row before FROM is all 95), less MARGIN
// where the table holds a contact
function tipLimit(f, p, i) {
    const T = TIP_LIMIT, R = T.rows[f], s = T.step, p0 = T.from[f];
    if (!R || p <= p0 - s) return Infinity;
    const col = (row) => {
        const c = Math.max(0, i / s), c0 = Math.min(row.length - 2, Math.floor(c)), t = c - c0;
        return row[c0] + t * (row[c0 + 1] - row[c0]);
    };
    const r = (p - p0) / s;
    let v;
    if (r < 0) v = 95 + (1 + r) * (col(R[0]) - 95);
    else {
        const r0 = Math.min(R.length - 2, Math.floor(r)), t = r - r0;
        v = col(R[r0]) + t * (col(R[r0 + 1]) - col(R[r0]));
    }
    return v >= 95 - 1e-9 ? Infinity : v - T.margin;
}
function applyFingerTips(vrm, stats) {
    const THREE = globalThis.THREE;
    const st = _hands.get(vrm);
    if (!st) return;
    const H = vrm.humanoid, T = st.hinges;
    const q = new THREE.Quaternion(), tw = new THREE.Quaternion(), v = new THREE.Vector3(), ax = (a) => v.set(a[0], a[1], a[2]);
    const mirror = (src, m, out) => (m > 0 ? out.copy(src) : out.set(src.x, -src.y, -src.z, src.w));
    const angleAbout = (qq, a) => {
        twistAbout(qq, a, tw);
        return wrapPi(2 * Math.atan2(tw.x * a[0] + tw.y * a[1] + tw.z * a[2], tw.w));
    };
    for (const [side, m] of [['left', 1], ['right', -1]]) {
        for (const f of ['Index', 'Middle', 'Ring', 'Little']) {
            const segs = ['Proximal', 'Intermediate', 'Distal'];
            const js = segs.map((sg) => T['left' + f + sg]), nodes = segs.map((sg) => H.getNormalizedBoneNode(side + f + sg));
            if (js.some((j) => !j) || nodes.some((n) => !n)) continue;
            // each pin's turn as the pass left it (a pure turn about its pin), in hardware degrees
            const hw = nodes.map((n, k) => { mirror(n.quaternion, m, q); return angleAbout(q, js[k].axis) / D + js[k].flex_at_rest; });
            if (hw[2] <= tipLimit(f, hw[0], hw[1])) continue;
            const lo = js.map((j) => j.deg[0]);
            const at = (t) => hw.map((x, k) => Math.max(lo[k], x - t));
            let a = 0, b = Math.max(...hw);
            for (let it = 0; it < 32; it++) {
                const mid = 0.5 * (a + b), w = at(mid);
                if (w[2] <= tipLimit(f, w[0], w[1])) b = mid; else a = mid;
            }
            const w = at(b);
            nodes.forEach((n, k) => { q.setFromAxisAngle(ax(js[k].axis), (w[k] - js[k].flex_at_rest) * D); mirror(q, m, n.quaternion); });
            if (stats) {
                stats[side + f + 'Tip'] = Math.max(stats[side + f + 'Tip'] || 0, b);
                stats.tipFrames = (stats.tipFrames || 0) + 1;
            }
        }
    }
}

// (round 2) THE POST-PASS IS A CALL OF ITS OWN (applyGraftContact, at the end: it needs the frame's final pose, so it
// cannot run in here). A frame loop written for round 1's passes runs without it, and nothing else would say so: the
// thumb then crosses a curling finger and the hand goes through the creature's skin as before. So it is said, once per
// creature, when a frame's pass starts and the last frame's post-pass never ran
function contactDue(vrm) {
    const rec = _contact.get(vrm);
    if (!rec || !Object.keys(rec.sides).length) return;
    if (rec.due && !rec.told) {
        rec.told = true;
        console.warn('[robot_hand_dof] applyGraftContact(vrm, stats) did not run after the last frame\'s applyGraftDOF: the thumb is not '
            + 'kept off the fingers, nor the hand off the creature\'s skin. Call it LAST in each frame, once the pose is final '
            + '(after vrm.update, the foot lock and the twist joints).');
    }
    rec.due = true;
}

// (C3-MOTION) THE GRAFT EACH FRAME, in the body's order (applyArmDOF, then applyHandDOF): the wrist's stages, then the
// pins and the thumb (the copy above), then the rotor kept continuous and the fingers' tips held off the palm. Before
// vrm.update; the frame loop keeps the clip's pose for it (keepArmPose right after the mixer, restoreArmPose before it)
export function applyGraftDOF(vrm, stats, dt) {
    contactDue(vrm);                                                                // (round 2) the post-pass's wiring
    applyGraftWrist(vrm, stats);
    const asks = thumbAsks(vrm);
    applyHandDOF(vrm, stats);
    rotorContinuity(vrm, asks, stats);
    applyFingerTips(vrm, stats);
}

// (C3-MOTION) a cut or a seek (a new shot, a jump in the clip's time): the wrists' turn limit (resetArmDOF, the copy) and
// the rotors' memory both start fresh
export function resetGraftDOF(vrm, side) {
    resetArmDOF(vrm, side);
    const mem = _rotor.get(vrm);
    if (mem) for (const s of side ? [side] : ['left', 'right']) delete mem[s];
    const cm = _contact.get(vrm);                                                   // (round 2) the easings: wrist, thumb
    if (cm) {
        for (const s of side ? [side] : ['left', 'right']) {
            if (!cm.sides[s]) continue;
            cm.sides[s].off = null;
            cm.sides[s].fresh = true;                                               // (the contact's turn: as it is, once)
            if (cm.sides[s].clear) cm.sides[s].clear.off = null;
        }
    }
}

// (C3-MOTION) the stages' last angles per side (deg): the clamped roll a, flexion b, deviation c, the split's ask, and
// whether the turn limit acted
export function graftDebug(vrm) {
    const st = _arms.get(vrm);
    if (!st) return null;
    const one = (W) => W && { a: +(W.a / D).toFixed(3), b: +(W.b / D).toFixed(3), c: +(W.c / D).toFixed(3),
        asked: W.asked.map((x) => +(x / D).toFixed(3)), limited: !!(W.memo && W.memo.limited) };
    return { L: one(st.left && st.left.wrist), R: one(st.right && st.right.wrist) };
}

// (C3-MOTION) THE TWIST JOINTS of a creature with a grafted hand: the creature's forearm twist joints take a share of
// its hand's twist about the forearm (h4b's driver: lowerarm_twist_01 2/3, _02 1/3, source the hand), which spreads a
// living wrist's pronation along the forearm's skin. A grafted robot hand turns in its own roll stage, inside the house
// on the forearm, and the skin's collar over the house rides those twist joints: driven, the collar slid round the
// still house by 2/3 of the hand's roll (C3-MOTION's logs: 16 mm at the lip in the walk). So every twist joint whose
// source is a grafted hand is left undriven (at its rest on the forearm, with the house); the others as recorded
export function graftTwists(twists, vrm, c3) {
    if (!twists || !c3 || !vrm) return twists;
    const hands = new Set();
    for (const [s, side] of [['L', 'left'], ['R', 'right']]) {
        const n = c3.sides && c3.sides[s] && vrm.humanoid.getRawBoneNode(side + 'Hand');
        if (n) hands.add(n.name);
    }
    const out = {};
    for (const [k, d] of Object.entries(twists)) if (!hands.has(d.source)) out[k] = d;
    return out;
}

// ======================================================================================================================
// (C3-MOTION round 2) THE HAND OFF THE CREATURE'S OWN BODY. Check 1 (11-09) measured what round 1 never did, the grafted
// hand against the creature's own skin: in the films' crouch (fallLand, 10.87 s) the right thumb's distal went 23.6 mm
// (the man) / 7.9 mm (the woman) into the calf below the knee. The cause is the clip's arm path on this body: the human's
// OWN hand (his h4d build, no graft, the same timeline) goes 33-44 mm into his knee there (c3_motion/r2, h02); the robot
// hand inherits the arm, and of it only the thumb, standing out on the chassis's radial edge, reaches the skin (h04: every
// other link >= 15 mm clear). A rigid hand does not pass through a leg; a hand that meets one turns at its wrist. So once
// the frame's pose is final (vrm.update, the foot lock, the creature's twist joints), each grafted hand is measured
// against the creature's skin (CONTACT.bodies, skinned on the CPU near the hand as the renderer skins it; the signed
// distance from the nearest feature by its angle-weighted pseudo-normal) and, where a link is inside it or nearer than
// CONTACT.margin, the wrist's three stages turn the hand off it: the least turn (in the stages' own angles, inside their
// stops and the coupled rows) that clears every link, searched along the contact's own push and the last frame's turn
// (each stage alone only where neither clears), by bisection up to CONTACT.cap deg. The turn goes to the raw hand and the
// two stages only: the clip's pose, the wrist's turn-limit memo and the thumb's solve are not touched, so the next frame
// starts from the clip again. The turn is a motion of the wrist like any other, so it does not jump: it changes at most
// CONTACT.attack deg a frame (in the stages' angles; a fresh start or a reset takes it as it is, as the wrist's own turn
// limit does) and after a contact it eases off at CONTACT.release deg a frame instead of snapping back. Where no turn
// within the cap clears it (a clip that buries the hand itself in the body, as the sitting clips played standing do) a
// turn under way keeps easing off and a fresh one is not started (the hand as the clip has it); the frame is counted
// (stats[side + 'ContactUncleared']). As check 1's k07 measures it, a hand's points
// within 60 mm of either wrist joint (the skin is open there; the collar sits on the house by design) or 120 mm of the
// neck (open too) are not asked.
//   initGraftDOF builds the record at load; applyGraftContact(vrm, stats) LAST in the frame: after ctrl.update (vrm.update
// and the foot lock inside it) and the creature's twist joints, before the render (it runs THE THUMB OFF THE FINGERS
// first, below). contactDebug(vrm): the last frame's numbers per side
// (coherence: a turn is chosen by its size plus this many times its distance from the last frame's turn, in the stages'
// degrees, so a contact that lasts does not flick the hand between ways off it; measured on stairsDown, check 1's clip)
// THE SURFACES ASKED (CONTACT.bodies: skinned meshes by name; a name ending in * by its start, as 'garment_*'): each
// answers for itself by its own nearest place, and the deepest answer counts. A surface's OPEN BORDER (an edge with one
// triangle: the skin's cuts at the neck and the wrists, and, on a CLOTHED creature, the skin's cut edges where the
// creator culls it under each garment) has no inside or outside: a point whose nearest place on a surface is on its
// border is beyond that surface's opening, and the surface does not answer for it. (Read by the border triangle's plane,
// the calf skin's cut edge at the trouser cuff put the thumb 17 mm "inside" from 26 mm away: the creator's woman in tee
// and trousers, the films' crouch.)
// KNOWN, MEASURED, NOT SOLVED HERE: WHAT THE CREATURE WEARS. Only the skin is asked by default, and under clothes the
// skin is culled, so a clothed creature's hand is not kept off its clothes: through the creator the thumb ends 46.6 mm
// inside the trouser leg in that crouch, as with no pass. Asking the garments by name ('garment_*': the creator's names)
// clears the trousers (0 mm), but an open garment's inside is not its wearer's: the hand hanging under the tee's hem
// reads 55-70 mm "inside" the tee on four frames of the walk, and the wrist turns 5-7 deg for nothing. What a worn
// surface needs is the whole skin for the side (the creator's culled index hides it) and the cloth's stand-off for the
// clearance; until then the garments stay out of the default
export const CONTACT = { margin: 0.002, cap: 25, attack: 10, release: 4, coherence: 1, bodies: ['skin_BODY'], cell: 0.025,
    around: 0.08, wristSkip: 0.06, neckSkip: 0.12 };
const _contact = new WeakMap();

// the point of triangle abc nearest p, into out; returns the feature: 0 the face, 1 / 2 / 3 the edge ab / bc / ca, 4 / 5 / 6
// the vertex a / b / c (Ericson, Real-Time Collision Detection 5.1.5)
function nearestOnTri(px, py, pz, ax, ay, az, bx, by, bz, cx, cy, cz, out) {
    const abx = bx - ax, aby = by - ay, abz = bz - az, acx = cx - ax, acy = cy - ay, acz = cz - az;
    const apx = px - ax, apy = py - ay, apz = pz - az;
    const d1 = abx * apx + aby * apy + abz * apz, d2 = acx * apx + acy * apy + acz * apz;
    if (d1 <= 0 && d2 <= 0) { out[0] = ax; out[1] = ay; out[2] = az; return 4; }
    const bpx = px - bx, bpy = py - by, bpz = pz - bz;
    const d3 = abx * bpx + aby * bpy + abz * bpz, d4 = acx * bpx + acy * bpy + acz * bpz;
    if (d3 >= 0 && d4 <= d3) { out[0] = bx; out[1] = by; out[2] = bz; return 5; }
    const vc = d1 * d4 - d3 * d2;
    if (vc <= 0 && d1 >= 0 && d3 <= 0) { const t = d1 / (d1 - d3); out[0] = ax + t * abx; out[1] = ay + t * aby; out[2] = az + t * abz; return 1; }
    const cpx = px - cx, cpy = py - cy, cpz = pz - cz;
    const d5 = abx * cpx + aby * cpy + abz * cpz, d6 = acx * cpx + acy * cpy + acz * cpz;
    if (d6 >= 0 && d5 <= d6) { out[0] = cx; out[1] = cy; out[2] = cz; return 6; }
    const vb = d5 * d2 - d1 * d6;
    if (vb <= 0 && d2 >= 0 && d6 <= 0) { const t = d2 / (d2 - d6); out[0] = ax + t * acx; out[1] = ay + t * acy; out[2] = az + t * acz; return 3; }
    const va = d3 * d6 - d5 * d4;
    if (va <= 0 && d4 - d3 >= 0 && d5 - d6 >= 0) {
        const t = (d4 - d3) / ((d4 - d3) + (d5 - d6));
        out[0] = bx + t * (cx - bx); out[1] = by + t * (cy - by); out[2] = bz + t * (cz - bz); return 2;
    }
    const dn = 1 / (va + vb + vc), v = vb * dn, w = vc * dn;
    out[0] = ax + abx * v + acx * w; out[1] = ay + aby * v + acy * w; out[2] = az + abz * v + acz * w; return 0;
}

// at load (initGraftDOF): the creature's skin (welded: the UV seams split its vertices in the file, its sign test needs
// the surface's own topology; each welded vertex's four bones and weights; each triangle's neighbour across each edge;
// each bone's reach, for the near-hand prefilter) and each grafted hand's links (every vertex on one joint, C3's build:
// grouped by joint, the house and the seal on the forearm left out; each group's kind: the hand's subtree, the roll
// stage, the drum)
function initGraftContact(vrm, st) {
    const THREE = globalThis.THREE;
    const H = vrm.humanoid, rec = { bodies: [], sides: {}, last: {} };
    vrm.scene.updateMatrixWorld(true);
    const meshes = [];
    const asked = (n) => CONTACT.bodies.some((b) => (b.endsWith('*') ? n.startsWith(b.slice(0, -1)) : n === b));
    vrm.scene.traverse((o) => {
        if (o.isSkinnedMesh && (asked(o.name) || (o.parent && asked(o.parent.name)))) meshes.push(o);
    });
    const v = new THREE.Vector3();
    for (const mesh of meshes) {
        const g = mesh.geometry, P = g.attributes.position, SI = g.attributes.skinIndex, SW = g.attributes.skinWeight;
        if (!P || !SI || !SW || !g.index) continue;
        const key = new Map(), weld = new Int32Array(P.count), rep = [];
        for (let i = 0; i < P.count; i++) {
            const k = Math.round(P.getX(i) * 1e6) + ',' + Math.round(P.getY(i) * 1e6) + ',' + Math.round(P.getZ(i) * 1e6);
            let w = key.get(k);
            if (w === undefined) { w = rep.length; key.set(k, w); rep.push(i); }
            weld[i] = w;
        }
        const nv = rep.length, src = g.index.array, tri = [];
        for (let t = 0; t < src.length; t += 3) {
            const a = weld[src[t]], b = weld[src[t + 1]], c = weld[src[t + 2]];
            if (a !== b && b !== c && c !== a) tri.push(a, b, c);
        }
        const T = Int32Array.from(tri), nt = T.length / 3;
        const edges = new Map(), nb = new Int32Array(3 * nt).fill(-1);
        for (let t = 0; t < nt; t++) {
            for (let k = 0; k < 3; k++) {
                const a = T[3 * t + k], b = T[3 * t + (k + 1) % 3], id = Math.min(a, b) * nv + Math.max(a, b);
                const o = edges.get(id);
                if (o === undefined) edges.set(id, 3 * t + k);
                else { nb[3 * t + k] = Math.floor(o / 3); nb[o] = t; }
            }
        }
        // the surface's open borders: an edge with one triangle (nb -1), and the vertices on such an edge
        const border = new Uint8Array(nv);
        for (let t = 0; t < nt; t++) {
            for (let k = 0; k < 3; k++) if (nb[3 * t + k] < 0) { border[T[3 * t + k]] = 1; border[T[3 * t + (k + 1) % 3]] = 1; }
        }
        const VB = new Int32Array(4 * nv), VW = new Float32Array(4 * nv), VP = new Float32Array(3 * nv), dom = new Int32Array(nv);
        for (let w = 0; w < nv; w++) {
            const i = rep[w];
            v.fromBufferAttribute(P, i).applyMatrix4(mesh.bindMatrix);
            VP[3 * w] = v.x; VP[3 * w + 1] = v.y; VP[3 * w + 2] = v.z;
            let best = -1;
            for (let k = 0; k < 4; k++) {
                VB[4 * w + k] = SI.getComponent(i, k); VW[4 * w + k] = SW.getComponent(i, k);
                if (VW[4 * w + k] > best) { best = VW[4 * w + k]; dom[w] = VB[4 * w + k]; }
            }
        }
        const bones = mesh.skeleton.bones, invs = mesh.skeleton.boneInverses, reach = new Float32Array(bones.length);
        const bpos = invs.map((M) => new THREE.Vector3().setFromMatrixPosition(M.clone().invert()));
        const byBone = bones.map(() => []);
        for (let w = 0; w < nv; w++) {
            const b = dom[w], d = Math.hypot(VP[3 * w] - bpos[b].x, VP[3 * w + 1] - bpos[b].y, VP[3 * w + 2] - bpos[b].z);
            if (d > reach[b]) reach[b] = d;
            byBone[b].push(w);
        }
        rec.bodies.push({ mesh, nv, nt, T, nb, border, VB, VW, VP, reach, byBone: byBone.map((a) => Int32Array.from(a)),
            X: new Float32Array(3 * nv), VN: new Float32Array(3 * nv), FN: new Float32Array(3 * nt),
            stamp: new Int32Array(nv), tstamp: new Int32Array(nt), SM: new Float32Array(16 * bones.length), frame: 0 });
    }
    rec.wrists = ['left', 'right'].map((s) => H.getRawBoneNode(s + 'Hand')).filter(Boolean);
    rec.neck = vrm.scene.getObjectByName('neck_02') || H.getRawBoneNode('neck') || null;
    for (const [s, side] of [['L', 'left'], ['R', 'right']]) {
        const W = st[side] && st[side].wrist, hand = H.getRawBoneNode(side + 'Hand'), fore = H.getRawBoneNode(side + 'LowerArm');
        const obj = vrm.scene.getObjectByName('c3_hand_' + s);
        if (!W || !hand || !obj) continue;
        const hm = [];
        obj.traverse((o) => { if (o.isSkinnedMesh) hm.push(o); });
        const kindOf = (b) => {
            if (b === W.roll) return 'roll';
            if (b === W.flex) return 'flex';
            for (let o = b; o; o = o.parent) if (o === hand) return 'hand';
            return 'fixed';
        };
        const groups = new Map();
        for (const mesh of hm) {
            const g = mesh.geometry, P = g.attributes.position, SI = g.attributes.skinIndex, SW = g.attributes.skinWeight;
            const bones = mesh.skeleton.bones, invs = mesh.skeleton.boneInverses, own = new Array(P.count), at = new Int32Array(P.count);
            for (let i = 0; i < P.count; i++) {
                let bi = 0, bw = -1;
                for (let k = 0; k < 4; k++) { const w = SW.getComponent(i, k); if (w > bw) { bw = w; bi = SI.getComponent(i, k); } }
                const bone = bones[bi];
                if (bone === fore) continue;
                let gr = groups.get(bone);
                if (!gr) { gr = { bone, inv: invs[bi], mesh, kind: kindOf(bone), p: [], t: [] }; groups.set(bone, gr); }
                v.fromBufferAttribute(P, i).applyMatrix4(mesh.bindMatrix);
                at[i] = gr.p.length / 3;
                own[i] = gr;
                gr.p.push(v.x, v.y, v.z);
            }
            // each link's own triangles (every triangle's three vertices on one joint, C3's build), in its points' numbering
            if (g.index) {
                const ix = g.index.array;
                for (let t = 0; t < ix.length; t += 3) {
                    const gr = own[ix[t]];
                    if (gr && own[ix[t + 1]] === gr && own[ix[t + 2]] === gr) gr.t.push(at[ix[t]], at[ix[t + 1]], at[ix[t + 2]]);
                }
            }
        }
        const G = [...groups.values()].filter((gr) => gr.kind !== 'fixed').map((gr) => {
            const p = Float32Array.from(gr.p), n = p.length / 3;
            let cx = 0, cy = 0, cz = 0, r = 0;
            for (let i = 0; i < n; i++) { cx += p[3 * i]; cy += p[3 * i + 1]; cz += p[3 * i + 2]; }
            cx /= n; cy /= n; cz /= n;
            for (let i = 0; i < n; i++) r = Math.max(r, Math.hypot(p[3 * i] - cx, p[3 * i + 1] - cy, p[3 * i + 2] - cz));
            return { bone: gr.bone, name: gr.bone.name, inv: gr.inv, mesh: gr.mesh, kind: gr.kind, p, n, t: Int32Array.from(gr.t),
                     c: new THREE.Vector3(cx, cy, cz), r, M: new THREE.Matrix4(), Mc: new THREE.Matrix4() };
        });
        // the thumb's three links and the fingers' twelve, each with its own static shape (the thumb off the fingers)
        const bn = (b) => H.getRawBoneNode(side + b);
        const pick = (b) => G.find((g) => g.bone === bn(b)) || null;
        const thumb = ['ThumbMetacarpal', 'ThumbProximal', 'ThumbDistal'].map(pick);
        const fingers = ['Index', 'Middle', 'Ring', 'Little'].flatMap((f) => ['Proximal', 'Intermediate', 'Distal'].map((s2) => pick(f + s2)));
        let clear = null;
        if (thumb.every(Boolean) && fingers.every(Boolean)) {
            for (const g of thumb.concat(fingers)) g.shape = linkShape(g.p, g.t);
            clear = { thumb, fingers, mc: bn('ThumbMetacarpal'), off: null };
        }
        rec.sides[side] = { W, hand, G, off: null, fresh: true, clear };
    }
    _contact.set(vrm, rec);
    return { bodies: rec.bodies.map((b) => ({ name: b.mesh.name, verts: b.nv, tris: b.nt })),
        hands: Object.fromEntries(Object.entries(rec.sides).map(([k, S]) => [k, { groups: S.G.length, points: S.G.reduce((a, g) => a + g.n, 0) }])) };
}

// the creature's skin near a hand this frame: the vertices of the bones within reach skinned (linear blend, as the
// renderer: mesh x bindInverse x bone x boneInverse x bind), each skinned triangle's unit normal, each skinned vertex's
// angle-weighted normal, and the triangles within RR of the hand's centre in a hash of CONTACT.cell cells
function skinNear(rec, hc, RR) {
    const THREE = globalThis.THREE;
    const cell = CONTACT.cell, ic = 1 / cell, hash = new Map(), tb = [], tt = [];
    const bm = new THREE.Matrix4(), MB = new THREE.Matrix4(), v = new THREE.Vector3();
    const box = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
    let maxEdge = 0;
    rec.bodies.forEach((B, bi) => {
        const f = ++B.frame, bones = B.mesh.skeleton.bones, invs = B.mesh.skeleton.boneInverses, SM = B.SM;
        MB.multiplyMatrices(B.mesh.matrixWorld, B.mesh.bindMatrixInverse);
        for (let b = 0; b < bones.length; b++) { bm.multiplyMatrices(MB, bones[b].matrixWorld).multiply(invs[b]); SM.set(bm.elements, 16 * b); }
        const X = B.X, VP = B.VP, VB = B.VB, VW = B.VW, VN = B.VN, far2 = (RR + 0.06) ** 2;
        for (let b = 0; b < bones.length; b++) {
            const list = B.byBone[b];
            if (!list.length) continue;
            bones[b].getWorldPosition(v);
            if (v.distanceTo(hc) > B.reach[b] + RR + 0.05) continue;
            const o = 16 * b;
            for (let k = 0; k < list.length; k++) {
                const w = list[k], px = VP[3 * w], py = VP[3 * w + 1], pz = VP[3 * w + 2];
                // where its own bone alone puts it: far from the hand (60 mm beyond the reach, the blend's room), skipped
                const rx = SM[o] * px + SM[o + 4] * py + SM[o + 8] * pz + SM[o + 12] - hc.x;
                const ry = SM[o + 1] * px + SM[o + 5] * py + SM[o + 9] * pz + SM[o + 13] - hc.y;
                const rz = SM[o + 2] * px + SM[o + 6] * py + SM[o + 10] * pz + SM[o + 14] - hc.z;
                if (rx * rx + ry * ry + rz * rz > far2) continue;
                let x = 0, y = 0, z = 0;
                for (let j = 0; j < 4; j++) {
                    const wt = VW[4 * w + j];
                    if (wt === 0) continue;
                    const s = 16 * VB[4 * w + j];
                    x += wt * (SM[s] * px + SM[s + 4] * py + SM[s + 8] * pz + SM[s + 12]);
                    y += wt * (SM[s + 1] * px + SM[s + 5] * py + SM[s + 9] * pz + SM[s + 13]);
                    z += wt * (SM[s + 2] * px + SM[s + 6] * py + SM[s + 10] * pz + SM[s + 14]);
                }
                X[3 * w] = x; X[3 * w + 1] = y; X[3 * w + 2] = z;
                VN[3 * w] = 0; VN[3 * w + 1] = 0; VN[3 * w + 2] = 0;
                B.stamp[w] = f;
            }
        }
        const T = B.T, FN = B.FN;
        const ang = (a, b, c) => {                          // the angle at a in the triangle abc
            const ux = X[3 * b] - X[3 * a], uy = X[3 * b + 1] - X[3 * a + 1], uz = X[3 * b + 2] - X[3 * a + 2];
            const wx = X[3 * c] - X[3 * a], wy = X[3 * c + 1] - X[3 * a + 1], wz = X[3 * c + 2] - X[3 * a + 2];
            const d = (ux * wx + uy * wy + uz * wz) / (Math.hypot(ux, uy, uz) * Math.hypot(wx, wy, wz) || 1);
            return Math.acos(Math.max(-1, Math.min(1, d)));
        };
        for (let t = 0; t < B.nt; t++) {
            const a = T[3 * t], b = T[3 * t + 1], c = T[3 * t + 2];
            if (B.stamp[a] !== f || B.stamp[b] !== f || B.stamp[c] !== f) continue;
            B.tstamp[t] = f;
            const ux = X[3 * b] - X[3 * a], uy = X[3 * b + 1] - X[3 * a + 1], uz = X[3 * b + 2] - X[3 * a + 2];
            const wx = X[3 * c] - X[3 * a], wy = X[3 * c + 1] - X[3 * a + 1], wz = X[3 * c + 2] - X[3 * a + 2];
            let nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx;
            const nn = Math.hypot(nx, ny, nz) || 1;
            nx /= nn; ny /= nn; nz /= nn;
            FN[3 * t] = nx; FN[3 * t + 1] = ny; FN[3 * t + 2] = nz;
            for (const [p, q2, r2] of [[a, b, c], [b, c, a], [c, a, b]]) {
                const g = ang(p, q2, r2);
                B.VN[3 * p] += g * nx; B.VN[3 * p + 1] += g * ny; B.VN[3 * p + 2] += g * nz;
            }
            const x0 = Math.min(X[3 * a], X[3 * b], X[3 * c]), x1 = Math.max(X[3 * a], X[3 * b], X[3 * c]);
            const y0 = Math.min(X[3 * a + 1], X[3 * b + 1], X[3 * c + 1]), y1 = Math.max(X[3 * a + 1], X[3 * b + 1], X[3 * c + 1]);
            const z0 = Math.min(X[3 * a + 2], X[3 * b + 2], X[3 * c + 2]), z1 = Math.max(X[3 * a + 2], X[3 * b + 2], X[3 * c + 2]);
            const dx = Math.max(x0 - hc.x, 0, hc.x - x1), dy = Math.max(y0 - hc.y, 0, hc.y - y1), dz = Math.max(z0 - hc.z, 0, hc.z - z1);
            if (dx * dx + dy * dy + dz * dz > RR * RR) continue;
            const id = tb.length;
            tb.push(bi); tt.push(t);
            maxEdge = Math.max(maxEdge, x1 - x0, y1 - y0, z1 - z0);
            box[0] = Math.min(box[0], x0); box[1] = Math.min(box[1], y0); box[2] = Math.min(box[2], z0);
            box[3] = Math.max(box[3], x1); box[4] = Math.max(box[4], y1); box[5] = Math.max(box[5], z1);
            for (let ix = Math.floor(x0 * ic); ix <= Math.floor(x1 * ic); ix++) {
                for (let iy = Math.floor(y0 * ic); iy <= Math.floor(y1 * ic); iy++) {
                    for (let iz = Math.floor(z0 * ic); iz <= Math.floor(z1 * ic); iz++) {
                        const k = ((ix + 4096) * 8192 + (iy + 4096)) * 8192 + (iz + 4096);
                        const l = hash.get(k);
                        if (l) l.push(id); else hash.set(k, [id]);
                    }
                }
            }
        }
        for (let w = 0; w < B.nv; w++) {
            if (B.stamp[w] !== f) continue;
            const n = Math.hypot(B.VN[3 * w], B.VN[3 * w + 1], B.VN[3 * w + 2]) || 1;
            B.VN[3 * w] /= n; B.VN[3 * w + 1] /= n; B.VN[3 * w + 2] /= n;
        }
    });
    // the cells with skin in or beside them (a point elsewhere is farther than a cell from it: one lookup)
    const near = new Set();
    for (const k of hash.keys()) {
        const iz = (k % 8192) - 4096, iy = (Math.floor(k / 8192) % 8192) - 4096, ix = Math.floor(k / (8192 * 8192)) - 4096;
        for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) {
            near.add(((ix + dx + 4096) * 8192 + (iy + dy + 4096)) * 8192 + (iz + dz + 4096));
        }
    }
    const nB = rec.bodies.length;
    return { rec, hash, near, tb: Int32Array.from(tb), tt: Int32Array.from(tt), seen: new Int32Array(tb.length), q: 0, box, maxEdge,
             cp: [0, 0, 0], best: new Float64Array(nB), bt: new Int32Array(nB), bf: new Int8Array(nB), bc: new Float64Array(3 * nB) };
}

// the signed distance (+ outside) from p to the creature's surface near the hand, with the outward normal there, or null
// when no surface answers. Each surface (CONTACT.bodies) answers for itself by ITS nearest
// place to p (the nearest feature's pseudo-normal: the face's, an edge's two faces', a vertex's angle-weighted); the
// least of the answers is returned (inside any of them is inside). A surface does not answer when none of its triangles
// lies in p's cell or the 26 around it (farther than CONTACT.cell: clear), or when its nearest place is on its open
// border (CONTACT, above: beyond its opening)
function skinDistance(L, x, y, z, out) {
    const ic = 1 / CONTACT.cell, ix = Math.floor(x * ic), iy = Math.floor(y * ic), iz = Math.floor(z * ic);
    if (!L.near.has(((ix + 4096) * 8192 + (iy + 4096)) * 8192 + (iz + 4096))) return null;
    const bodies = L.rec.bodies, nB = bodies.length, best = L.best, bt = L.bt, bf = L.bf, bc = L.bc;
    for (let b = 0; b < nB; b++) { best[b] = Infinity; bt[b] = -1; }
    const q = ++L.q, cp = L.cp;
    for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
            for (let dz = -1; dz <= 1; dz++) {
                const l = L.hash.get(((ix + dx + 4096) * 8192 + (iy + dy + 4096)) * 8192 + (iz + dz + 4096));
                if (!l) continue;
                for (let k = 0; k < l.length; k++) {
                    const id = l[k];
                    if (L.seen[id] === q) continue;
                    L.seen[id] = q;
                    const bi = L.tb[id], B = bodies[bi], t = L.tt[id], T = B.T, X = B.X;
                    const a = 3 * T[3 * t], b = 3 * T[3 * t + 1], c = 3 * T[3 * t + 2];
                    const fe = nearestOnTri(x, y, z, X[a], X[a + 1], X[a + 2], X[b], X[b + 1], X[b + 2], X[c], X[c + 1], X[c + 2], cp);
                    const d2 = (x - cp[0]) ** 2 + (y - cp[1]) ** 2 + (z - cp[2]) ** 2;
                    if (d2 < best[bi]) { best[bi] = d2; bt[bi] = t; bf[bi] = fe; bc[3 * bi] = cp[0]; bc[3 * bi + 1] = cp[1]; bc[3 * bi + 2] = cp[2]; }
                }
            }
        }
    }
    let got = false;
    for (let bi = 0; bi < nB; bi++) {
        const t = bt[bi];
        if (t < 0) continue;
        const B = bodies[bi], FN = B.FN, feat = bf[bi];
        let nx, ny, nz;
        if (feat === 0) { nx = FN[3 * t]; ny = FN[3 * t + 1]; nz = FN[3 * t + 2]; }
        else if (feat <= 3) {
            const o = B.nb[3 * t + feat - 1];
            if (o < 0) continue;                                                    // on this surface's open border
            const oo = B.tstamp[o] === B.frame ? o : t;
            nx = FN[3 * t] + FN[3 * oo]; ny = FN[3 * t + 1] + FN[3 * oo + 1]; nz = FN[3 * t + 2] + FN[3 * oo + 2];
        } else {
            const w = B.T[3 * t + feat - 4];
            if (B.border[w]) continue;                                              // on this surface's open border
            nx = B.VN[3 * w]; ny = B.VN[3 * w + 1]; nz = B.VN[3 * w + 2];
        }
        const d = Math.sqrt(best[bi]), s = (x - bc[3 * bi]) * nx + (y - bc[3 * bi + 1]) * ny + (z - bc[3 * bi + 2]) * nz;
        const sd = s >= 0 ? d : -d;
        if (got && sd >= out.d) continue;
        const nn = Math.hypot(nx, ny, nz) || 1;
        out.d = sd; out.nx = nx / nn; out.ny = ny / nn; out.nz = nz / nn; out.b = bi;
        got = true;
    }
    return got ? out : null;
}

// how far the hand's links are inside the margin (pen = margin - the signed distance, > 0: a contact) with the given
// matrices per group (null: as the frame left them); early: stop at the first contact
function handPenetration(S, L, Ms, skip, early) {
    const C = CONTACT, b = L.box, out = { d: 0, nx: 0, ny: 0, nz: 0, b: -1 };
    const res = { pen: -Infinity, p: null, n: null, g: -1, b: -1 };
    const v = new globalThis.THREE.Vector3();
    for (let gi = 0; gi < S.G.length; gi++) {
        const g = S.G[gi], M = Ms ? Ms[gi] : g.M, e = M.elements;
        v.copy(g.c).applyMatrix4(M);
        const r = g.r + C.margin + C.cell;
        if (v.x < b[0] - r || v.y < b[1] - r || v.z < b[2] - r || v.x > b[3] + r || v.y > b[4] + r || v.z > b[5] + r) continue;
        const p = g.p;
        for (let i = 0; i < g.n; i++) {
            const px = p[3 * i], py = p[3 * i + 1], pz = p[3 * i + 2];
            const x = e[0] * px + e[4] * py + e[8] * pz + e[12], y = e[1] * px + e[5] * py + e[9] * pz + e[13], z = e[2] * px + e[6] * py + e[10] * pz + e[14];
            if (skip(x, y, z)) continue;
            if (!skinDistance(L, x, y, z, out)) continue;
            const pen = C.margin - out.d;
            if (pen > res.pen) { res.pen = pen; res.p = [x, y, z]; res.n = [out.nx, out.ny, out.nz]; res.g = gi; res.b = out.b; }
            if (early && pen > 0) return res;
        }
    }
    return res;
}

// (C3-MOTION round 2) THE THUMB OFF THE FINGERS. Check 1 found the right thumb's distal 2.89 mm (the woman) / 3.15 mm (the
// man) into the index's in 'salute' (library 138.93 s): the thumb opposed (rotor 60) while the index curls through its
// place. With round 1's hold gone, the copied solve is the body's own: the body's pass given the asks as the graft's
// mechanism meets them (conjugated by C3's rigid map, 26.31 deg about the hand's long axis) returns the graft's solve to
// 0.12 deg over the whole library, rotor 60 there (r2: k04 conj). So the body's hand pass itself crosses the thumb and a
// curling finger on this clip; nothing in it keeps one link off another. This does, for the thumb against the twelve
// finger links: once the frame is final, each pair whose bounds meet is measured both ways (the thumb's vertices against
// the finger link's shape, the finger's against the thumb link's; each shape built once in its own bind frame, the
// signed distance by the nearest feature's pseudo-normal), and where one is inside the other or nearer than
// THUMB_CLEAR.margin, the thumb gives way: the least change of its rotor and CMC (inside their ranges and the coupled
// stop; the MCP and IP keep their turns against the metacarpal) that clears every pair, along the contact's own push and
// the last frame's change (8 ways of the two stages only where neither clears), by bisection up to THUMB_CLEAR.cap deg;
// after a contact the change eases off at THUMB_CLEAR.release deg a frame (where nothing clears, easing off as it is).
// The drawn rotor's memory and the copied solve are not touched (the next frame starts from the clip). The fingers
// keep the clip's curl: the thumb's reading of a human clip is the approximate one (its rest lies 53 deg from the robot
// thumb's, C3-MOTION round 1)
export const THUMB_CLEAR = { margin: 0.0004, cap: 40, release: 6, coherence: 1, cell: 0.004 };

// a rigid link's shape in its own bind frame, built once: welded vertices, each triangle's unit normal and its neighbours
// across its edges, each vertex's angle-weighted normal, a hash of THUMB_CLEAR.cell cells (and the cells beside them)
function linkShape(p, t) {
    const n = p.length / 3, key = new Map(), weld = new Int32Array(n), rep = [];
    for (let i = 0; i < n; i++) {
        const k = Math.round(p[3 * i] * 1e7) + ',' + Math.round(p[3 * i + 1] * 1e7) + ',' + Math.round(p[3 * i + 2] * 1e7);
        let w = key.get(k);
        if (w === undefined) { w = rep.length; key.set(k, w); rep.push(i); }
        weld[i] = w;
    }
    const nv = rep.length, X = new Float32Array(3 * nv);
    for (let w = 0; w < nv; w++) { X[3 * w] = p[3 * rep[w]]; X[3 * w + 1] = p[3 * rep[w] + 1]; X[3 * w + 2] = p[3 * rep[w] + 2]; }
    const tri = [];
    for (let k = 0; k < t.length; k += 3) {
        const a = weld[t[k]], b = weld[t[k + 1]], c = weld[t[k + 2]];
        if (a !== b && b !== c && c !== a) tri.push(a, b, c);
    }
    const T = Int32Array.from(tri), nt = T.length / 3, nb = new Int32Array(3 * nt).fill(-1), edges = new Map();
    for (let tt = 0; tt < nt; tt++) {
        for (let k = 0; k < 3; k++) {
            const a = T[3 * tt + k], b = T[3 * tt + (k + 1) % 3], id = Math.min(a, b) * nv + Math.max(a, b), o = edges.get(id);
            if (o === undefined) edges.set(id, 3 * tt + k); else { nb[3 * tt + k] = Math.floor(o / 3); nb[o] = tt; }
        }
    }
    const FN = new Float32Array(3 * nt), VN = new Float32Array(3 * nv), hash = new Map(), ic = 1 / THUMB_CLEAR.cell;
    const ang = (a, b, c) => {
        const ux = X[3 * b] - X[3 * a], uy = X[3 * b + 1] - X[3 * a + 1], uz = X[3 * b + 2] - X[3 * a + 2];
        const wx = X[3 * c] - X[3 * a], wy = X[3 * c + 1] - X[3 * a + 1], wz = X[3 * c + 2] - X[3 * a + 2];
        const d = (ux * wx + uy * wy + uz * wz) / (Math.hypot(ux, uy, uz) * Math.hypot(wx, wy, wz) || 1);
        return Math.acos(Math.max(-1, Math.min(1, d)));
    };
    for (let tt = 0; tt < nt; tt++) {
        const a = T[3 * tt], b = T[3 * tt + 1], c = T[3 * tt + 2];
        const ux = X[3 * b] - X[3 * a], uy = X[3 * b + 1] - X[3 * a + 1], uz = X[3 * b + 2] - X[3 * a + 2];
        const wx = X[3 * c] - X[3 * a], wy = X[3 * c + 1] - X[3 * a + 1], wz = X[3 * c + 2] - X[3 * a + 2];
        let nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx;
        const nn = Math.hypot(nx, ny, nz) || 1;
        nx /= nn; ny /= nn; nz /= nn;
        FN[3 * tt] = nx; FN[3 * tt + 1] = ny; FN[3 * tt + 2] = nz;
        for (const [q1, q2, q3] of [[a, b, c], [b, c, a], [c, a, b]]) {
            const g = ang(q1, q2, q3);
            VN[3 * q1] += g * nx; VN[3 * q1 + 1] += g * ny; VN[3 * q1 + 2] += g * nz;
        }
        const x0 = Math.min(X[3 * a], X[3 * b], X[3 * c]), x1 = Math.max(X[3 * a], X[3 * b], X[3 * c]);
        const y0 = Math.min(X[3 * a + 1], X[3 * b + 1], X[3 * c + 1]), y1 = Math.max(X[3 * a + 1], X[3 * b + 1], X[3 * c + 1]);
        const z0 = Math.min(X[3 * a + 2], X[3 * b + 2], X[3 * c + 2]), z1 = Math.max(X[3 * a + 2], X[3 * b + 2], X[3 * c + 2]);
        for (let ix = Math.floor(x0 * ic); ix <= Math.floor(x1 * ic); ix++) {
            for (let iy = Math.floor(y0 * ic); iy <= Math.floor(y1 * ic); iy++) {
                for (let iz = Math.floor(z0 * ic); iz <= Math.floor(z1 * ic); iz++) {
                    const k = ((ix + 4096) * 8192 + (iy + 4096)) * 8192 + (iz + 4096), l = hash.get(k);
                    if (l) l.push(tt); else hash.set(k, [tt]);
                }
            }
        }
    }
    for (let w = 0; w < nv; w++) {
        const nn = Math.hypot(VN[3 * w], VN[3 * w + 1], VN[3 * w + 2]) || 1;
        VN[3 * w] /= nn; VN[3 * w + 1] /= nn; VN[3 * w + 2] /= nn;
    }
    const near = new Set();
    for (const k of hash.keys()) {
        const iz = (k % 8192) - 4096, iy = (Math.floor(k / 8192) % 8192) - 4096, ix = Math.floor(k / (8192 * 8192)) - 4096;
        for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) {
            near.add(((ix + dx + 4096) * 8192 + (iy + dy + 4096)) * 8192 + (iz + dz + 4096));
        }
    }
    return { X, T, nb, FN, VN, hash, near, seen: new Int32Array(nt), q: 0, cp: [0, 0, 0], bc: [0, 0, 0] };
}

// the signed distance (+ outside) from p (the link's bind frame) to a link's shape, or null when p is farther than a
// cell from it
function shapeDistance(L, x, y, z) {
    const ic = 1 / THUMB_CLEAR.cell, ix = Math.floor(x * ic), iy = Math.floor(y * ic), iz = Math.floor(z * ic);
    if (!L.near.has(((ix + 4096) * 8192 + (iy + 4096)) * 8192 + (iz + 4096))) return null;
    let best = Infinity, bt = -1, feat = 0;
    const q = ++L.q, cp = L.cp, bc = L.bc, T = L.T, X = L.X;
    for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
            for (let dz = -1; dz <= 1; dz++) {
                const l = L.hash.get(((ix + dx + 4096) * 8192 + (iy + dy + 4096)) * 8192 + (iz + dz + 4096));
                if (!l) continue;
                for (let k = 0; k < l.length; k++) {
                    const t = l[k];
                    if (L.seen[t] === q) continue;
                    L.seen[t] = q;
                    const a = 3 * T[3 * t], b = 3 * T[3 * t + 1], c = 3 * T[3 * t + 2];
                    const fe = nearestOnTri(x, y, z, X[a], X[a + 1], X[a + 2], X[b], X[b + 1], X[b + 2], X[c], X[c + 1], X[c + 2], cp);
                    const d2 = (x - cp[0]) ** 2 + (y - cp[1]) ** 2 + (z - cp[2]) ** 2;
                    if (d2 < best) { best = d2; bt = t; feat = fe; bc[0] = cp[0]; bc[1] = cp[1]; bc[2] = cp[2]; }
                }
            }
        }
    }
    if (bt < 0) return null;
    let nx, ny, nz;
    if (feat === 0) { nx = L.FN[3 * bt]; ny = L.FN[3 * bt + 1]; nz = L.FN[3 * bt + 2]; }
    else if (feat <= 3) {
        const o = L.nb[3 * bt + feat - 1], oo = o >= 0 ? o : bt;
        nx = L.FN[3 * bt] + L.FN[3 * oo]; ny = L.FN[3 * bt + 1] + L.FN[3 * oo + 1]; nz = L.FN[3 * bt + 2] + L.FN[3 * oo + 2];
    } else {
        const w = T[3 * bt + feat - 4];
        nx = L.VN[3 * w]; ny = L.VN[3 * w + 1]; nz = L.VN[3 * w + 2];
    }
    const d = Math.sqrt(best);
    return (x - bc[0]) * nx + (y - bc[1]) * ny + (z - bc[2]) * nz >= 0 ? d : -d;
}

// the thumb off the fingers, one side, the frame final (the groups' matrices current): returns the debug record or null
function thumbOffFingers(vrm, side, S, stats) {
    const THREE = globalThis.THREE;
    const Cc = S.clear, TC = THUMB_CLEAR, hs = _hands.get(vrm), rm = _rotor.get(vrm);
    if (!Cc || !hs || !hs.ok || !rm || !rm[side]) return null;
    const s = hs.side[side], T = hs.hinges, m = side === 'left' ? 1 : -1, H = vrm.humanoid;
    const Yr = vunit(T.leftThumbRotor.axis), P0 = vunit(vcross(vcross(Yr, T.leftThumbMetacarpal.axis), Yr));
    const range = (j) => [(j.deg[0] - j.flex_at_rest) * D, (j.deg[1] - j.flex_at_rest) * D];
    const aR = range(T.leftThumbRotor), bR = range(T.leftThumbMetacarpal);
    const bMax = (a) => {                                    // the copied pass's coupled stop
        const o = a / D + T.leftThumbRotor.flex_at_rest;
        const lim = o <= 40 ? 87 : o <= 50 ? 87 - 0.1 * (o - 40) : 86 - 0.7 * (o - 50);
        return Math.min(bR[1], (lim - T.leftThumbMetacarpal.flex_at_rest) * D);
    };
    const clampAB = (a, b) => { a = Math.min(aR[1], Math.max(aR[0], a)); return [a, Math.min(bMax(a), Math.max(bR[0], b))]; };
    const a0 = rm[side].a, b0 = rm[side].b;                  // the drawn pair this frame
    const V3 = (u) => new THREE.Vector3(u[0], u[1], u[2]);
    const mir = (q) => (m > 0 ? q : q.set(q.x, -q.y, -q.z, q.w));
    const qOf = (a, b) => new THREE.Quaternion().setFromAxisAngle(V3(Yr), a).multiply(new THREE.Quaternion().setFromAxisAngle(V3(P0), b));
    const q0inv = mir(qOf(a0, b0)).invert();
    const Qh = H.getNormalizedBoneNode(side + 'Hand').getWorldQuaternion(new THREE.Quaternion()), QhI = Qh.clone().invert();
    const piv = Cc.mc.getWorldPosition(new THREE.Vector3());
    const fInv = Cc.fingers.map((g) => g.M.clone().invert());
    const fC = Cc.fingers.map((g) => g.c.clone().applyMatrix4(g.M));
    const thumbMs = (a, b) => {
        const dR = Qh.clone().multiply(mir(qOf(a, b)).multiply(q0inv)).multiply(QhI);
        const D4 = new THREE.Matrix4().makeTranslation(piv.x, piv.y, piv.z).multiply(new THREE.Matrix4().makeRotationFromQuaternion(dR))
            .multiply(new THREE.Matrix4().makeTranslation(-piv.x, -piv.y, -piv.z));
        return { dR, Ms: Cc.thumb.map((g) => {
            const MB = new THREE.Matrix4().multiplyMatrices(g.mesh.matrixWorld, g.mesh.bindMatrixInverse);
            return MB.clone().multiply(D4).multiply(MB.invert()).multiply(g.M);
        }) };
    };
    const side1 = (pts, n, A, shape, res, early, tag) => {   // pts through A into shape's frame
        const e = A.elements;
        for (let i = 0; i < n; i++) {
            const px = pts[3 * i], py = pts[3 * i + 1], pz = pts[3 * i + 2];
            const d = shapeDistance(shape, e[0] * px + e[4] * py + e[8] * pz + e[12], e[1] * px + e[5] * py + e[9] * pz + e[13],
                e[2] * px + e[6] * py + e[10] * pz + e[14]);
            if (d === null) continue;
            const pen = TC.margin - d;
            if (pen > res.pen) { res.pen = pen; res.pair = tag; }
            if (early && pen > 0) return true;
        }
        return false;
    };
    const pen = (Ms, early) => {
        const res = { pen: -Infinity, pair: null };
        for (let i = 0; i < 3; i++) {
            const gt = Cc.thumb[i], Mt = Ms[i], ct = gt.c.clone().applyMatrix4(Mt), MtI = Mt.clone().invert();
            for (let j = 0; j < Cc.fingers.length; j++) {
                const gf = Cc.fingers[j];
                if (ct.distanceTo(fC[j]) > gt.r + gf.r + TC.margin) continue;
                if (side1(gt.p, gt.n, fInv[j].clone().multiply(Mt), gf.shape, res, early, gt.name + '>' + gf.name) && early) return res;
                if (side1(gf.p, gf.n, MtI.clone().multiply(gf.M), gt.shape, res, early, gf.name + '>' + gt.name) && early) return res;
            }
        }
        return res;
    };
    const own = pen(Cc.thumb.map((g) => g.M), false);
    const dbg = { pen: own.pen > -Infinity ? +(own.pen * 1e3).toFixed(3) : null, pair: own.pair, turn: 0, cleared: true };
    const at = (off) => clampAB(a0 + off[0] * D, b0 + off[1] * D);
    const clearAt = (ab) => pen(thumbMs(ab[0], ab[1]).Ms, true).pen <= 0;
    const size = (ab) => Math.hypot(ab[0] - a0, ab[1] - b0) / D;
    let best = null;
    if (own.pen > 0) {
        // the push: the deepest pair's change per degree of the rotor and of the CMC (0.5 deg differences)
        const dirs = [], g = [];
        for (const off of [[0.5, 0], [0, 0.5]]) g.push((pen(thumbMs(...at(off)).Ms, false).pen - own.pen) / 0.5);
        const gn = Math.hypot(...g);
        if (gn > 1e-12) dirs.push([-g[0] / gn, -g[1] / gn]);
        const lastN = Cc.off ? Math.hypot(...Cc.off) : 0;                // the last frame's change, its own way too
        if (lastN > 1e-6) dirs.push(Cc.off.map((x) => x / lastN));
        const ways = [[1, 0], [-1, 0], [0, 1], [0, -1], [0.7071, 0.7071], [0.7071, -0.7071], [-0.7071, 0.7071], [-0.7071, -0.7071]];
        const cost = (ab) => size(ab) + TC.coherence * (Cc.off ? Math.hypot((ab[0] - a0) / D - Cc.off[0], (ab[1] - b0) / D - Cc.off[1]) : size(ab));
        for (const list of [dirs, ways]) {                              // the push and the last way first, then the 8
            for (const u of list) {
                if (!clearAt(at([u[0] * TC.cap, u[1] * TC.cap]))) continue;
                let lo = 0, hi = TC.cap;
                for (let it = 0; it < 9; it++) {                           // 9 halvings: 0.08 deg at the cap
                    const mid = 0.5 * (lo + hi);
                    if (clearAt(at([u[0] * mid, u[1] * mid]))) hi = mid; else lo = mid;
                }
                const ab = at([u[0] * hi, u[1] * hi]);
                if (!best || cost(ab) < cost(best)) best = ab;
            }
            if (best) break;
        }
        if (!best) { dbg.cleared = false; if (stats) stats[side + 'ThumbUncleared'] = (stats[side + 'ThumbUncleared'] || 0) + 1; }
    }
    if (Cc.off) {                                            // easing off (and, where nothing clears, easing off as it is)
        const n = Math.hypot(...Cc.off), k = Math.max(0, n - TC.release) / (n || 1);
        const eased = at(Cc.off.map((x) => x * k));
        if (!best || (size(eased) > size(best) + 1e-9 && clearAt(eased))) best = eased;
    }
    if (best && size(best) > 1e-6) {
        const { dR } = thumbMs(best[0], best[1]);
        const Pw = Cc.mc.parent.getWorldQuaternion(new THREE.Quaternion());
        Cc.mc.quaternion.premultiply(Pw.clone().invert().multiply(dR).multiply(Pw));
        if (s.helper) {
            const r = mir(new THREE.Quaternion().setFromAxisAngle(V3(Yr), best[0]));
            s.helper.quaternion.copy(s.Pinv).multiply(r).multiply(s.P).multiply(s.Lrest);
        }
        S.hand.updateMatrixWorld(true);
        Cc.off = [(best[0] - a0) / D, (best[1] - b0) / D];
        dbg.turn = +size(best).toFixed(3);
        dbg.off = Cc.off.map((x) => +x.toFixed(3));
        if (stats) {
            stats[side + 'ThumbFrames'] = (stats[side + 'ThumbFrames'] || 0) + 1;
            stats[side + 'ThumbTurnMax'] = Math.max(stats[side + 'ThumbTurnMax'] || 0, size(best));
        }
    } else Cc.off = null;
    if (stats && own.pen > 0) stats[side + 'ThumbPenMax'] = Math.max(stats[side + 'ThumbPenMax'] || 0, own.pen * 1e3);
    return dbg;
}

// a turn of the wrist's stages to (a, b, c) (rad, the left's sense as wristSolve keeps them): each group's matrices
// (the hand's subtree turned about the hand's pivot by the change of the hand's turn, the roll stage and the drum set
// as applyGraftWrist sets them), and the raw locals to apply
function wristCandidate(S, base, a, b, c) {
    const THREE = globalThis.THREE;
    const W = S.W, m = base.m, e = new THREE.Euler();
    const mir = (q) => (m > 0 ? q : q.set(q.x, -q.y, -q.z, q.w));
    const q1 = new THREE.Quaternion().setFromEuler(e.set(a, b, c, 'XYZ')).premultiply(W.B).multiply(W.Bi);
    const dq = mir(q1.multiply(base.q0inv));                                      // the hand's normalized local change
    const dR = base.Qn.clone().multiply(dq).multiply(base.QnI);                   // in the world
    const piv = base.piv, D4 = new THREE.Matrix4().makeTranslation(piv.x, piv.y, piv.z)
        .multiply(new THREE.Matrix4().makeRotationFromQuaternion(dR)).multiply(new THREE.Matrix4().makeTranslation(-piv.x, -piv.y, -piv.z));
    const rollL = W.PrI.clone().multiply(mir(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(...W.EL), a))).multiply(W.Pr).multiply(W.Lr);
    const flexL = W.PdI.clone().multiply(mir(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(...W.EA), b))).multiply(W.Pd).multiply(W.Ld);
    const rollW = W.roll.parent.matrixWorld.clone().multiply(new THREE.Matrix4().compose(W.roll.position, rollL, W.roll.scale));
    const flexW = rollW.clone().multiply(new THREE.Matrix4().compose(W.flex.position, flexL, W.flex.scale));
    const Ms = S.G.map((g) => {
        const MB = new THREE.Matrix4().multiplyMatrices(g.mesh.matrixWorld, g.mesh.bindMatrixInverse);
        // the hand's subtree: its bones turned in the world (bone' = D4 bone), so the skinning matrix MB bone' inv
        if (g.kind === 'hand') return MB.clone().multiply(D4).multiply(MB.clone().invert()).multiply(g.M);
        return MB.multiply(g.kind === 'roll' ? rollW : flexW).multiply(g.inv);
    });
    return { Ms, dR, rollL, flexL, abc: [a, b, c] };
}

export function applyGraftContact(vrm, stats) {
    const THREE = globalThis.THREE;
    const rec = _contact.get(vrm);
    if (!rec) return;
    rec.due = false;                                                                // (the wiring: contactDue)
    const C = CONTACT, H = vrm.humanoid;
    const wp = rec.wrists.map((o) => o.getWorldPosition(new THREE.Vector3()));
    const np = rec.neck ? rec.neck.getWorldPosition(new THREE.Vector3()) : null;
    const skip = (x, y, z) => {
        for (const w of wp) if ((x - w.x) ** 2 + (y - w.y) ** 2 + (z - w.z) ** 2 < C.wristSkip ** 2) return true;
        return !!np && (x - np.x) ** 2 + (y - np.y) ** 2 + (z - np.z) ** 2 < C.neckSkip ** 2;
    };
    const lim = (x, r) => Math.min(r[1] * D, Math.max(r[0] * D, x));
    rec.last = {};
    for (const side of ['left', 'right']) {
        const S = rec.sides[side];
        if (!S) continue;
        const W = S.W, m = side === 'left' ? 1 : -1, sA = W.sgnA ?? 1, sD = W.sgnD ?? 1;
        // 1. the hand as the frame left it; the thumb off the fingers first (inside the hand), then the hand off the body
        const mats = () => { for (const g of S.G) g.M.multiplyMatrices(g.mesh.matrixWorld, g.mesh.bindMatrixInverse).multiply(g.bone.matrixWorld).multiply(g.inv); };
        mats();
        const tdbg = thumbOffFingers(vrm, side, S, stats);
        if (tdbg && tdbg.turn) mats();
        const hc = new THREE.Vector3();
        for (const g of S.G) hc.add(g.c.clone().applyMatrix4(g.M));
        hc.multiplyScalar(1 / S.G.length);
        let R = 0;
        for (const g of S.G) R = Math.max(R, g.c.clone().applyMatrix4(g.M).distanceTo(hc) + g.r);
        // 2. the skin near it (the reach of a turn up to the cap included); a creature without CONTACT.bodies: the thumb only
        if (!rec.bodies.length) { if (tdbg) rec.last[side] = { pen: null, turn: 0, cleared: true, thumb: tdbg }; continue; }
        const L = skinNear(rec, hc, R + C.around);
        const own = handPenetration(S, L, null, skip, false);
        const dbg = { pen: own.pen > -Infinity ? +(own.pen * 1e3).toFixed(3) : null, turn: 0, cleared: true };
        if (own.pen > 0) { dbg.link = S.G[own.g].name; dbg.surface = rec.bodies[own.b].mesh.name; }      // (what met what)
        // 3. the turn: the least that clears, or the last turn easing off
        const clampABC = (a, b, c) => {
            a = lim(a, ARM.wristRoll); b = lim(b, ARM.wristFlex);
            const dl = wristDevRange(sA * b / D);
            return [a, b, lim(c, sD > 0 ? dl : [-dl[1], -dl[0]])];
        };
        const cur = [W.a, W.b, W.c];
        const Qn = H.getNormalizedBoneNode(side + 'LowerArm').getWorldQuaternion(new THREE.Quaternion());
        const q0 = new THREE.Quaternion().setFromEuler(new THREE.Euler(W.a, W.b, W.c, 'XYZ')).premultiply(W.B).multiply(W.Bi);
        const base = { m, Qn, QnI: Qn.clone().invert(), q0inv: q0.clone().invert(), piv: S.hand.getWorldPosition(new THREE.Vector3()) };
        const at = (off) => clampABC(cur[0] + off[0] * D, cur[1] + off[1] * D, cur[2] + off[2] * D);
        const clearAt = (abc) => {
            const cand = wristCandidate(S, base, abc[0], abc[1], abc[2]);
            return handPenetration(S, L, cand.Ms, skip, true).pen <= 0;
        };
        const size = (abc) => Math.hypot(abc[0] - cur[0], abc[1] - cur[1], abc[2] - cur[2]) / D;
        let pick = null;
        if (own.pen > 0) {
            // the push: how the deepest point moves along its normal per degree of each stage (a 0.5 deg difference)
            const dirs = [];
            const gi = own.g, p0 = own.p, n0 = own.n, J = [];
            for (let k = 0; k < 3; k++) {
                const off = [0, 0, 0];
                off[k] = 0.5;
                const abc = at(off), cand = wristCandidate(S, base, abc[0], abc[1], abc[2]);
                const pl = new THREE.Vector3(...p0).applyMatrix4(S.G[gi].M.clone().invert()).applyMatrix4(cand.Ms[gi]);
                J.push(((pl.x - p0[0]) * n0[0] + (pl.y - p0[1]) * n0[1] + (pl.z - p0[2]) * n0[2]) / 0.5);
            }
            const jn = Math.hypot(...J);
            if (jn > 1e-9) dirs.push(J.map((x) => x / jn));
            // the last frame's turn, its own direction too: a contact that lasts keeps turning the hand the same way
            const lastN = S.off ? Math.hypot(...S.off) : 0;
            if (lastN > 1e-6) dirs.push(S.off.map((x) => x / lastN));
            const axes = [];
            for (let k = 0; k < 3; k++) for (const s of [1, -1]) { const u = [0, 0, 0]; u[k] = s; axes.push(u); }
            const cost = (abc) => size(abc) + C.coherence * (S.off ? Math.hypot((abc[0] - cur[0]) / D - S.off[0],
                (abc[1] - cur[1]) / D - S.off[1], (abc[2] - cur[2]) / D - S.off[2]) : size(abc));
            // the push and the last way first; each stage alone only where neither clears (8 halvings: 0.1 deg at the cap)
            for (const list of [dirs, axes]) {
                for (const u of list) {
                    if (!clearAt(at(u.map((x) => x * C.cap)))) continue;
                    let lo = 0, hi = C.cap;
                    for (let it = 0; it < 8; it++) {
                        const mid = 0.5 * (lo + hi);
                        if (clearAt(at(u.map((x) => x * mid)))) hi = mid; else lo = mid;
                    }
                    const abc = at(u.map((x) => x * hi));
                    if (!pick || cost(abc) < cost(pick)) pick = abc;
                }
                if (pick) break;
            }
            if (!pick) { dbg.cleared = false; if (stats) stats[side + 'ContactUncleared'] = (stats[side + 'ContactUncleared'] || 0) + 1; }
        }
        // the last turn eased off by CONTACT.release deg: kept while it is the larger and clear, and where no turn clears
        // the contact at all, eased off as it is (the hand does not snap back into a body it cannot leave)
        if (S.off) {
            const n = Math.hypot(...S.off), k = Math.max(0, n - C.release) / (n || 1);
            const eased = at(S.off.map((x) => x * k));
            if (!pick || (size(eased) > size(pick) + 1e-9 && clearAt(eased))) pick = eased;
        }
        // the turn changes at most CONTACT.attack deg a frame. Unlimited (the libraries' logs, the woman and the man), a
        // contact that came on at once, or whose way off changed where the first way reached the cap, flicked the wrist
        // 10-29 deg in ONE frame on 6-19 frames a hand (the bows, the sitting, stairs and sit-to-stand clips: the hand
        // pressed 5-48 mm into the body), in slow and held poses too: a pop of the creator's own making. Limited, such a
        // turn takes two or three frames, and on 2-13 of those frames a hand a link is still in the skin (1-27 mm, less
        // than the clip alone puts it there: 5-42 mm). The films' crouch asks 9.5 deg in its fastest frame
        if (pick && !S.fresh) {
            const prev = S.off || [0, 0, 0];
            const want = [0, 1, 2].map((i) => (pick[i] - cur[i]) / D - prev[i]), wn = Math.hypot(...want);
            if (wn > C.attack) {
                pick = at(prev.map((x, i) => x + want[i] * C.attack / wn));
                dbg.limited = true;
                if (stats) stats[side + 'ContactLimited'] = (stats[side + 'ContactLimited'] || 0) + 1;
            }
        }
        S.fresh = false;
        if (pick && size(pick) > 1e-6) {
            const cand = wristCandidate(S, base, pick[0], pick[1], pick[2]);
            // the raw hand turned by dR in the world (its parent's frame: raw local' = Pw^-1 dR Pw raw local), the stages set
            const Pw = S.hand.parent.getWorldQuaternion(new THREE.Quaternion());
            S.hand.quaternion.premultiply(Pw.clone().invert().multiply(cand.dR).multiply(Pw));
            W.roll.quaternion.copy(cand.rollL);
            W.flex.quaternion.copy(cand.flexL);
            S.hand.updateMatrixWorld(true);
            W.roll.updateMatrixWorld(true);
            S.off = [(pick[0] - cur[0]) / D, (pick[1] - cur[1]) / D, (pick[2] - cur[2]) / D];
            dbg.turn = +size(pick).toFixed(3);
            dbg.off = S.off.map((x) => +x.toFixed(3));
            if (stats) {
                stats[side + 'ContactFrames'] = (stats[side + 'ContactFrames'] || 0) + 1;
                stats[side + 'ContactTurnMax'] = Math.max(stats[side + 'ContactTurnMax'] || 0, size(pick));
            }
        } else S.off = null;
        if (stats && own.pen > 0) stats[side + 'ContactPenMax'] = Math.max(stats[side + 'ContactPenMax'] || 0, own.pen * 1e3);
        if (tdbg) dbg.thumb = tdbg;
        rec.last[side] = dbg;
    }
}

// (round 2) the contact's last frame per side: pen (mm, the frame's own deepest inside the margin; <= 0 clear) and, in a
// contact, the hand's link and the surface it met; the turn applied (deg, in the stages' angles) and its parts, cleared
// (false: no turn within the cap cleared it), limited (true: the turn was held to CONTACT.attack deg of change this frame)
export function contactDebug(vrm) {
    const rec = _contact.get(vrm);
    return rec ? rec.last : null;
}
