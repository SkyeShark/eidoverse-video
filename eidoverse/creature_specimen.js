// creature_specimen.js — globalThis.makeSpecimen: a GROUND-UP realist
// creature creator. Shares only the OPTION VOCABULARY with makeCreature
// (stance, legPairs, bodyLength, neck, tail, legLength, colors, pattern,
// seed, speed...) — the skeleton, the gait engine, and the body are all
// its own. Nothing here calls or copies creature_builder.js.
//
// The body is sculpted offline (work/creaturelab/sculpt_creature.py
// specimen path: cross-section profile lofts + moon_collab surface layer
// + Quadriflow quads + capsule/Laplacian weights) around THIS skeleton,
// cached by spec hash, and bound at load.
//
//   const c = await globalThis.makeSpecimen({
//       stance: 'quad', bodyLength: 1.1, legLength: 0.62,
//       neck: 0.35, tail: 0.5, color: 0x6a5747, seed: 7, speed: 0.8,
//   });
//   scene.add(c.group);            // self-animating; c.walkTo(x, z), c.speed...
//
// SKELETON (quad, realist anatomy — the reason for ground-up):
//   pelvis → lumbar ×2 → thoracic ×2 → withers → neck ×3 → head
//   hind legs: femur → tibia → metatarsus (digitigrade hock) → toe
//   fore legs: scapula (glides on the ribcage) → humerus → radius → metacarpus → toe
//   tail ×5
// GAIT: 4-beat lateral-sequence walk (LH LF RH RF at quarter phases),
// two-bone IK per limb with hock/carpus follow-through, pelvis/chest bob
// in counterphase, spine yaw into turns, springy tail lag, head carriage
// stabilized in world space.
(function () {
    const THREE = globalThis.THREE;
    const LAB = 'work/creaturelab';
    const V = (x, y, z) => new THREE.Vector3(x, y, z);
    // Sculpt-open jaw angle: the bind pose has the mouth at full gape; the
    // runtime closes it by this rotation at rest (jawOpen=0) and say()
    // rotates back toward the bind (jawOpen=1).
    const JAW_OPEN = 0.35;

    // ─────────────────────────────────────────────── parametric skeleton ──
    // One source of truth: bind positions computed here, serialized to the
    // spec; python sculpts around them, weights bind back to these bones.
    function buildSkeleton(o) {
        const L = o.bodyLength ?? 1.1;           // pelvis→shoulder along +z
        const legL = o.legLength ?? 0.62;        // ground→withers-ish
        const neckL = o.neck ?? 0.35;
        const tailL = o.tail ?? 0.5;
        // raised 1.00/1.08→1.06/1.14: Sol's standard puts the elbow at
        // 0.51S and ours measured 0.41S — the legs were short under an
        // over-tall chest (measure_proportions.py, FUR_REVIEW5 §5)
        const hipH = legL * 1.08;                // pelvis height at bind
        const shH = legL * 1.14;                 // withers slightly higher
        const hipW = (o.bodyRadius ?? L * 0.16) * 0.81;
        const shW = (o.bodyRadius ?? L * 0.16) * 0.86;

        const bones = [];
        const mk = (name, role, pos, parent) => {
            const b = new THREE.Bone();
            b.name = name;
            b.userData.role = role;
            b.userData.bindPos = pos.clone();
            if (parent) { b.position.copy(pos).sub(parent.userData.bindPos); parent.add(b); }
            else b.position.copy(pos);
            bones.push(b);
            return b;
        };

        // axial chain: pelvis at z=0, chest toward +z
        const pelvis = mk('pelvis', 'pelvis', V(0, hipH, 0), null);
        const lum1 = mk('lumbar1', 'spine', V(0, hipH + L * 0.015, L * 0.2), pelvis);
        const lum2 = mk('lumbar2', 'spine', V(0, hipH + L * 0.02, L * 0.42), lum1);
        const tho1 = mk('thoracic1', 'spine', V(0, hipH + L * 0.03, L * 0.62), lum2);
        const tho2 = mk('thoracic2', 'spine', V(0, shH, L * 0.82), tho1);
        const withers = mk('withers', 'spine', V(0, shH + L * 0.015, L), tho2);
        // neck rises from the withers
        const nSeg = 3, neckRise = 0.70;   // upright neck: the reference
                                           // carries the head HIGH, not level
        let prevN = withers;
        const neckBones = [];
        for (let i = 1; i <= nSeg; i++) {
            const t = i / nSeg;
            const p = V(0, shH + L * 0.015 + neckL * neckRise * t,
                L + neckL * Math.sin(Math.acos(neckRise)) * t);
            prevN = mk(`neck${i}`, 'neck', p, prevN);
            neckBones.push(prevN);
        }
        const headLen = (o.headSize ?? 1) * Math.max(neckL * 0.55, L * 0.16);
        const head = mk('head', 'head',
            prevN.userData.bindPos.clone().add(V(0, headLen * 0.30, headLen * 0.42)), prevN);
        // hinged JAW for say()/lipsync: TMJ below the ear, chin under the
        // muzzle tip — mirrors the field's head frame so the bone runs
        // along the sculpted jawline. Explicit segEnd: a leaf bone's
        // auto-derived capsule points away from the skull and would never
        // reach the chin.
        const rBody = o.bodyRadius ?? L * 0.16;
        // 0.5→0.44 (−12% head scale, increment 1): measured H/S ran far
        // over the 0.36 standard — keep in sync with role_radius("head")
        const rHd = Math.max(rBody * 0.73, neckL * 0.35);
        const tH = V(0, 0.18, 0.98).normalize();
        const uH = V(0, 1, 0).addScaledVector(tH, -tH.y).normalize();
        const skullC = head.userData.bindPos.clone()
            .addScaledVector(tH, rHd * 0.1).addScaledVector(uH, rHd * 0.18);
        // The jaw BINDS WIDE OPEN (Skye): the mouth is sculpted open so the
        // wedge meshes cleanly (a thin closed slit welds shut in smoothing
        // and feeds QuadriFlow sliver geometry); the runtime CLOSES it by
        // rotating -JAW_OPEN at rest, and say() rotates back toward bind.
        const hinge = skullC.clone()
            .addScaledVector(tH, rHd * 0.05).addScaledVector(uH, -rHd * 0.42);
        const jaw = mk('jaw', 'jaw', hinge, head);
        // 2.15→2.26: follows the pv58 muzzle extension (upper lip front
        // moved to ~2.34rH; the chin keeps a slight overbite behind it)
        const chinDir = skullC.clone()
            .addScaledVector(tH, rHd * 2.26).addScaledVector(uH, -rHd * 0.74)
            .sub(hinge);
        chinDir.applyAxisAngle(V(1, 0, 0), JAW_OPEN);   // +x drops the chin
        jaw.userData.segEnd = hinge.clone().add(chinDir);

        // the tail is PART OF THE SPINE: it roots ABOVE the hips, continuing
        // the croup line, then droops gently — never from below the pelvis
        const tSeg = 5;
        let prevT = pelvis;
        for (let i = 1; i <= tSeg; i++) {
            const t = i / tSeg;
            // flatter root: the ref tail leaves the croup LOW and HANGS —
            // the sheet's tail tip reaches the hock, not straight back
            // hairless ref: the topline falls 0.12S over the last quarter —
            // the tail leaves BELOW the croup peak, dropping fast
            const p = V(0, hipH + tailL * (0.00 - 0.48 * t - 0.42 * t * t),
                -L * 0.05 - tailL * t * 0.50);
            prevT = mk(`tail${i}`, 'tail', p, prevT);
        }

        // legs — digitigrade hind, scapula-led fore. Segment fractions of
        // total leg length (ground reach at bind ≈ hipH with soft knees).
        const legs = [];
        for (const side of [-1, 1]) {
            // HIND: femur → tibia → metatarsus → toe
            // canid hind: the femur rides NEAR-HORIZONTAL, hidden inside the
            // body — the visible leg pivots from the STIFLE, low and forward.
            // The hip SOCKET sits forward of the tail base too (the croup
            // extends behind the legs), so the whole chain, socket included,
            // shifts ahead of the pelvis.
            const hz = L * 0.00;
            // STANDING columns (ref sheets): foot plants under/behind the
            // hip, hock stacked — the old far-forward toe was a permanent
            // sprinter crouch
            const hipP = V(side * hipW, hipH, hz);
            const stifle = V(side * hipW, hipH - legL * 0.34, hz + legL * 0.10);
            // hock dropped 0.56→0.63: measured 0.32-0.38S vs the 0.29S of
            // real tarsal joints — the cannon was too long
            // hind foot moved back 0.075→0.13: the hairless ref's paw
            // spread is 0.944S, ours measured 0.858S (short stance)
            const hock = V(side * hipW, hipH - legL * 0.63, hz - legL * 0.15);
            const toeH = V(side * hipW, 0, hz - legL * 0.15);   // plumb cannon
            const femur = mk(`femur${side > 0 ? 'R' : 'L'}`, 'leg_femur', hipP, pelvis);
            const tibia = mk(`tibia${side > 0 ? 'R' : 'L'}`, 'leg_tibia', stifle, femur);
            const met = mk(`metatarsus${side > 0 ? 'R' : 'L'}`, 'leg_metatarsus', hock, tibia);
            const toe = mk(`toeHind${side > 0 ? 'R' : 'L'}`, 'leg_toe', toeH, met);
            legs.push({ side, fore: false, chain: [femur, tibia, met, toe],
                L1: hipP.distanceTo(stifle), L2: stifle.distanceTo(hock),
                L3: hock.distanceTo(toeH) });
            // FORE: scapula → humerus → radius → metacarpus → toe
            // canid fore: humerus angles back-down inside the chest; the
            // elbow sits at the chest underline and the visible column is
            // radius→carpus→paw
            // near-plumb fore column under the shoulder (ref front/side)
            const scapTop = V(side * shW * 0.9, shH + L * 0.02, L * 0.86);
            const shoulder = V(side * shW, shH - legL * 0.24, L * 0.92);
            // elbow raised 0.52→0.44: measured 0.44S vs the 0.51S standard
            // (the sternum must meet the elbow, not hang below it)
            const elbow = V(side * shW, shH - legL * 0.44, L * 0.88);
            const carpus = V(side * shW, shH - legL * 0.74, L * 0.91);
            const toeF = V(side * shW, 0, L * 1.02);
            const scap = mk(`scapula${side > 0 ? 'R' : 'L'}`, 'arm_scapula', scapTop, tho2);
            const hum = mk(`humerus${side > 0 ? 'R' : 'L'}`, 'arm_humerus', shoulder, scap);
            const rad = mk(`radius${side > 0 ? 'R' : 'L'}`, 'arm_radius', elbow, hum);
            const mc = mk(`metacarpus${side > 0 ? 'R' : 'L'}`, 'arm_metacarpus', carpus, rad);
            const toeB = mk(`toeFore${side > 0 ? 'R' : 'L'}`, 'arm_toe', toeF, mc);
            legs.push({ side, fore: true, chain: [hum, rad, mc, toeB], scapula: scap,
                L1: shoulder.distanceTo(elbow), L2: elbow.distanceTo(carpus),
                L3: carpus.distanceTo(toeF) });
        }
        return { bones, pelvis, spine: [lum1, lum2, tho1, tho2, withers],
            neckBones, head, jaw, legs, dims: { L, legL, neckL, tailL, hipH, shH } };
    }

    // ───────────────────────────────────────────────── two-bone IK (ours) ──
    const IKT = { r: new THREE.Vector3(), h: new THREE.Vector3(), t: new THREE.Vector3(),
        p: new THREE.Vector3(), k: new THREE.Vector3(), q: new THREE.Quaternion(),
        q2: new THREE.Quaternion(), b: new THREE.Vector3(), w: new THREE.Vector3() };
    function solveTwoBone(upper, lower, endBind, target, pole, L1, L2) {
        upper.updateWorldMatrix(true, false);
        const H = IKT.h.setFromMatrixPosition(upper.matrixWorld);
        const T = IKT.t.copy(target);
        const HT = IKT.r.copy(T).sub(H);
        const rawD = HT.length();
        const d = Math.min(
            Math.max(rawD, Math.abs(L1 - L2) + 1e-4),
            (L1 + L2) * 0.999,
        );
        const axis = rawD > 1e-8
            ? HT.multiplyScalar(1 / rawD)
            : HT.set(0, -1, 0);
        // Sol's IK consistency guard: K and the lower bone must agree on ONE
        // reachable target — aiming the shank at an unreachable original T
        // while the knee used the clamped d was the locked-leg/flip bug.
        T.copy(H).addScaledVector(axis, d);
        const a = (L1 * L1 + d * d - L2 * L2) / (2 * d);
        const h = Math.sqrt(Math.max(0, L1 * L1 - a * a));
        const poleP = IKT.p.copy(pole).addScaledVector(axis, -pole.dot(axis));
        if (poleP.lengthSq() < 1e-8) poleP.set(0, 0, 1).addScaledVector(axis, -axis.z);
        poleP.normalize();
        const K = IKT.k.copy(H).addScaledVector(axis, a).addScaledVector(poleP, h);
        const parentQ = upper.parent.getWorldQuaternion(IKT.q);
        const bindDir = IKT.b.copy(lower.userData.bindPos).sub(upper.userData.bindPos).normalize();
        const wantL = IKT.w.copy(K).sub(H).normalize().applyQuaternion(IKT.q2.copy(parentQ).invert());
        upper.quaternion.setFromUnitVectors(bindDir, wantL);
        upper.updateWorldMatrix(true, false);
        const upQ = upper.getWorldQuaternion(IKT.q);
        const bindDir2 = IKT.b.copy(endBind).sub(lower.userData.bindPos).normalize();
        const wantL2 = IKT.w.copy(T).sub(K).normalize().applyQuaternion(IKT.q2.copy(upQ).invert());
        lower.quaternion.setFromUnitVectors(bindDir2, wantL2);
        return K;
    }

    // ─────────────────────────────────────────────────────── gait engine ──
    // 4-beat lateral-sequence walk: LH(0) LF(.25) RH(.5) RF(.75), duty .68.
    // Sol's gait engine (work/creaturelab/GAIT_REVIEW.md, integrated
    // 2026-07-10): support-polygon weight transfer, duty-based touchdown
    // lead, phase-indexed analytic swing, continuous paw direction.
    function makeGait(sk, o, group) {
        const TAU = Math.PI * 2;
        const JAW_AXIS = new THREE.Vector3(1, 0, 0);  // +x = chin drops
        const st = {
            speed: o.speed ?? 0.6, turn: o.turn ?? 0, heading: 0,
            pos: new THREE.Vector3(), phase: 0, target: null,
            tailQ: [], flyAlt: 0, talk: null, jawOpen: 0,
        };
        const { legs, pelvis, spine, neckBones, dims } = sk;

        const phaseFor = (l) => l.fore
            ? (l.side < 0 ? 0.25 : 0.75)   // LF, RF
            : (l.side < 0 ? 0.00 : 0.50);  // LH, RH

        const plant = legs.map((l) => ({
            leg: l,
            phase: phaseFor(l),
            foot: new THREE.Vector3(),
            lift: new THREE.Vector3(),
            next: new THREE.Vector3(),
            contactDir: new THREE.Vector3(0, 0, 1),
            liftDir: new THREE.Vector3(0, 0, 1),
            landDir: new THREE.Vector3(0, 0, 1),
            mode: 'unseeded',              // unseeded | idle | stance | swing
            planted: false,
            initialized: false,
        }));

        const TMPg = {
            f: new THREE.Vector3(), pose: new THREE.Vector3(),
            d0: new THREE.Vector3(), d1: new THREE.Vector3(),
            home: new THREE.Vector3(), rel: new THREE.Vector3(),
            axis: new THREE.Vector3(), right: new THREE.Vector3(),
            pole: new THREE.Vector3(), bindOff: new THREE.Vector3(),
            hock: new THREE.Vector3(), toe: new THREE.Vector3(),
            push: new THREE.Vector3(), hang: new THREE.Vector3(),
            land: new THREE.Vector3(),
        };

        const sat = (x) => THREE.MathUtils.clamp(x, 0, 1);
        const wrap01 = (x) => x - Math.floor(x);
        const ease5 = (x) => {
            x = sat(x);
            return x * x * x * (x * (x * 6 - 15) + 10);
        };
        const ramp = (x, a, b) => ease5((x - a) / Math.max(b - a, 1e-6));

        // Nominal girdle point in world space. right = (fwd.z, 0, -fwd.x).
        function homeAt(l, pos, fwd, out) {
            const side = l.side * dims.L * 0.11;
            const fore = l.fore ? dims.L * 1.04 : dims.L * 0.00;   // hind home under the hip socket
            out.copy(pos).addScaledVector(fwd, fore);
            out.x += fwd.z * side;
            out.z -= fwd.x * side;
            out.y = 0;
            return out;
        }

        // Constant-speed/constant-yaw-rate prediction, including negative
        // seconds for reconstructing a swing already in progress at frame 0.
        function predictPose(seconds, speed, outPos, outDir) {
            const h0 = st.heading;
            const w = st.turn;
            const h1 = h0 + w * seconds;
            outDir.set(Math.sin(h1), 0, Math.cos(h1));
            if (Math.abs(w) < 1e-5) {
                outPos.copy(st.pos).addScaledVector(outDir, speed * seconds);
            } else {
                outPos.set(
                    st.pos.x + speed / w * (Math.cos(h0) - Math.cos(h1)),
                    0,
                    st.pos.z + speed / w * (Math.sin(h1) - Math.sin(h0)),
                );
            }
        }

        // Analytic swing: fixed endpoints, zero horizontal/vertical velocity
        // at both ends, and positive clearance until actual touchdown.
        function sampleSwing(pl, s, out) {
            const l = pl.leg;
            const e = ease5(s);
            const apex = l.fore ? 0.44 : 0.40;
            const h = s < apex ? ramp(s, 0, apex) : 1 - ramp(s, apex, 1);
            const clearance = dims.legL * (l.fore ? 0.105 : 0.115);
            out.lerpVectors(pl.lift, pl.next, e);
            out.y = THREE.MathUtils.lerp(pl.lift.y, pl.next.y, e)
                + clearance * h;
            return out;
        }

        function seedLeg(pl, ph, duty, stride, cycleT, speed, dir) {
            const l = pl.leg;
            const stanceTravel = duty * stride;
            // The fore cap is specific to this rig's short humerus+radius
            // envelope. It retains a soft elbow at faster walks; revisit it
            // if the fore segment proportions change.
            const lead = Math.min(
                stanceTravel * 0.5,
                dims.legL * (l.fore ? 0.30 : 0.36),
            );
            const trail = stanceTravel - lead;

            if (ph < duty) {
                homeAt(l, st.pos, dir, TMPg.home);
                pl.foot.copy(TMPg.home)
                    .addScaledVector(dir, lead - ph * stride);
                pl.lift.copy(pl.foot);
                pl.next.copy(pl.foot);
                pl.contactDir.copy(dir);
                pl.liftDir.copy(dir);
                pl.landDir.copy(dir);
                pl.mode = 'stance';
                pl.planted = true;
            } else {
                const s = (ph - duty) / (1 - duty);
                const swingT = (1 - duty) * cycleT;

                predictPose(-s * swingT, speed, TMPg.pose, TMPg.d0);
                homeAt(l, TMPg.pose, TMPg.d0, TMPg.home);
                pl.lift.copy(TMPg.home).addScaledVector(TMPg.d0, -trail);
                pl.liftDir.copy(TMPg.d0);

                predictPose((1 - s) * swingT, speed, TMPg.pose, TMPg.d1);
                homeAt(l, TMPg.pose, TMPg.d1, TMPg.home);
                pl.next.copy(TMPg.home).addScaledVector(TMPg.d1, lead);
                pl.landDir.copy(TMPg.d1);

                sampleSwing(pl, s, pl.foot);
                pl.mode = 'swing';
                pl.planted = false;
            }
            pl.initialized = true;
        }

        let last = null;
        let gaitAmt = 0; // eased start/stop envelope; public API unchanged

        function update(t) {
            if (last == null) last = t;
            const dt = Math.min(Math.max(t - last, 0), 0.1);
            last = t;

            // Steering.
            if (st.target) {
                const dx = st.target.x - st.pos.x;
                const dz = st.target.z - st.pos.z;
                const want = Math.atan2(dx, dz);
                let dh = want - st.heading;
                while (dh > Math.PI) dh -= TAU;
                while (dh < -Math.PI) dh += TAU;
                st.turn = THREE.MathUtils.clamp(dh * 1.6, -0.9, 0.9);
                if (Math.hypot(dx, dz) < 0.25) {
                    st.target = null;
                    st.speed = 0;
                    st.turn = 0;
                }
            }

            const speed = Math.max(st.speed, 0);
            const moving = speed > 0.02;

            // Integrate the same circular arc that touchdown prediction uses.
            const h0 = st.heading;
            const h1 = h0 + st.turn * dt;
            if (Math.abs(st.turn) < 1e-5) {
                st.pos.x += Math.sin(h0) * speed * dt;
                st.pos.z += Math.cos(h0) * speed * dt;
            } else {
                st.pos.x += speed / st.turn * (Math.cos(h0) - Math.cos(h1));
                st.pos.z += speed / st.turn * (Math.sin(h1) - Math.sin(h0));
            }
            st.heading = h1;
            const dir = TMPg.f.set(Math.sin(st.heading), 0, Math.cos(st.heading));

            // Wolf-mass walk calibration; same-paw cadence, not total
            // footfalls. stride is therefore exactly root travel per cycle.
            const speedU = sat((speed - 0.60) / 0.30);
            const duty = THREE.MathUtils.lerp(0.68, 0.65, speedU);
            const cadence = THREE.MathUtils.lerp(1.10, 1.35, speedU)
                * Math.sqrt(0.62 / Math.max(dims.legL, 0.1));
            const cycleT = 1 / cadence;
            const stride = speed * cycleT;
            if (moving) st.phase = wrap01(st.phase + dt * cadence);

            gaitAmt += ((moving ? 1 : 0) - gaitAmt) * Math.min(1, dt * 6);
            const g = gaitAmt * THREE.MathUtils.lerp(0.90, 1.12, speedU);

            // Contact/load/pass model. Load ramps after strike, peaks through
            // midstance, and unloads before toe-off.
            let totalLoad = 0;
            let sideLoad = 0;
            let foreLoad = 0, hindLoad = 0;
            let foreVaultSum = 0, hindVaultSum = 0;
            let impact = 0;
            for (const pl of plant) {
                const ph = wrap01(st.phase - pl.phase);
                if (ph >= duty) continue;
                const sp = ph / duty;
                const load = 0.10 + 0.90
                    * ramp(sp, 0.00, 0.16)
                    * (1 - ramp(sp, 0.72, 1.00));
                const vault = Math.sin(Math.PI * sp);
                totalLoad += load;
                sideLoad += load * pl.leg.side;
                if (pl.leg.fore) {
                    foreLoad += load;
                    foreVaultSum += load * vault;
                } else {
                    hindLoad += load;
                    hindVaultSum += load * vault;
                }
                if (ph < 0.12) {
                    // smooth loading pulse — the old step (1 at strike)
                    // popped the pelvis 4x per cycle (Skye: micro-jitter)
                    const q = Math.sin(Math.PI * ph / 0.12);
                    impact += q * q * 0.8;
                }
            }

            const supportSide = totalLoad > 1e-6
                ? THREE.MathUtils.clamp(sideLoad / totalLoad, -1, 1) : 0;
            const foreBalance = totalLoad > 1e-6
                ? (foreLoad - hindLoad) / totalLoad : 0;
            const hindVault = hindLoad > 1e-6
                ? hindVaultSum / hindLoad : 0.70;
            const foreVault = foreLoad > 1e-6
                ? foreVaultSum / foreLoad : 0.70;
            const hindWave = THREE.MathUtils.clamp((hindVault - 0.70) / 0.30, -1, 1);
            const foreWave = THREE.MathUtils.clamp((foreVault - 0.70) / 0.30, -1, 1);

            // The croup follows hind support; pitch turns the fore/hind vault
            // difference into counterphase shoulder motion.
            const bobT = dims.legL * (0.028 * hindWave - 0.006 * impact) * g;
            const pelvisYaw = Math.cos(TAU * st.phase) * 0.045 * g;
            const pitchT = THREE.MathUtils.clamp(
                (hindWave - foreWave) * 0.022 * g, -0.045, 0.045,
            );
            const rollT = THREE.MathUtils.clamp(
                (-supportSide * 0.035 - st.turn * 0.012) * g,
                -0.045, 0.045,
            );
            // low-pass the load-derived body signals (~2Hz cutoff): footfall
            // transitions and clamp saturations put 6-12Hz kinks straight
            // into the pelvis — measured as +/-2-4px/frame back tremor
            // (Skye 07-14: "micromotion looks kinda jittery")
            const sm = Math.min(1, dt * 10);
            st.bobS = (st.bobS ?? bobT) + (bobT - (st.bobS ?? bobT)) * sm;
            st.pitchS = (st.pitchS ?? pitchT) + (pitchT - (st.pitchS ?? pitchT)) * sm;
            st.rollS = (st.rollS ?? rollT) + (rollT - (st.rollS ?? rollT)) * sm;
            st.swayS = (st.swayS ?? supportSide) + (supportSide - (st.swayS ?? supportSide)) * sm;
            st.fbS = (st.fbS ?? foreBalance) + (foreBalance - (st.fbS ?? foreBalance)) * sm;
            const bob = st.bobS;
            const pelvisPitch = st.pitchS;
            const pelvisRoll = st.rollS;

            group.position.set(st.pos.x, 0, st.pos.z);
            group.rotation.set(0, st.heading, 0);
            pelvis.position.set(
                st.swayS * dims.legL * 0.035 * g,
                dims.hipH + bob + st.flyAlt,
                st.fbS * dims.legL * 0.010 * g,
            );
            pelvis.quaternion.setFromEuler(
                new THREE.Euler(pelvisPitch, pelvisYaw, pelvisRoll),
            );

            // Shoulder girdle counters the pelvis. Apply a distributed delta
            // so hierarchy accumulation reaches the target once instead of
            // multiplying the requested rotation by five bones.
            const chestYaw = -0.65 * pelvisYaw + st.turn * 0.035 * g;
            const chestPitch = -0.30 * pelvisPitch;
            const chestRoll = -0.50 * pelvisRoll;
            const nx = (chestPitch - pelvisPitch) / spine.length;
            const ny = (chestYaw - pelvisYaw) / spine.length;
            const nz = (chestRoll - pelvisRoll) / spine.length;
            spine.forEach((b) => {
                b.quaternion.setFromEuler(new THREE.Euler(nx, ny, nz));
            });

            // Keep the gaze comparatively level while retaining a small
            // twice-cycle nod at loading response.
            const neckN = Math.max(neckBones.length, 1);
            const nod = Math.sin(TAU * 2 * st.phase + 0.8) * 0.018 * g;
            // rest carriage: the bind neck stands steeper than the hairless
            // ref's alert pose — pitch each neck bone slightly forward
            const NECK_REST = o.neckRest ?? 0.02;
            neckBones.forEach((b, i) => {
                b.quaternion.setFromEuler(new THREE.Euler(
                    NECK_REST - chestPitch / neckN + nod * (i === 0 ? 1 : 0.35),
                    -chestYaw / neckN,
                    -chestRoll / neckN,
                ));
            });
            // resting muzzle trim: the bind head rides up the raised neck —
            // pitch the gaze down to LEVEL (head-sheet overlay measured the
            // bridge ~15-20° above the ref's level carriage at 0.10)
            sk.head.quaternion.setFromEuler(new THREE.Euler(o.headTrim ?? 0.06, 0, 0));

            pelvis.updateWorldMatrix(true, true);

            for (const pl of plant) {
                const l = pl.leg;
                const ph = wrap01(st.phase - pl.phase);
                const stance = ph < duty;
                const sp = stance ? ph / duty : 0;
                const ss = stance ? 0 : (ph - duty) / (1 - duty);
                const stanceTravel = duty * stride;
                const lead = Math.min(
                    stanceTravel * 0.5,
                    dims.legL * (l.fore ? 0.30 : 0.36),
                );

                homeAt(l, st.pos, dir, TMPg.home);

                if (!moving) {
                    if (!pl.initialized) pl.foot.copy(TMPg.home);
                    else pl.foot.lerp(TMPg.home, Math.min(1, dt * 8));
                    pl.lift.copy(pl.foot);
                    pl.next.copy(pl.foot);
                    pl.contactDir.copy(dir);
                    pl.liftDir.copy(dir);
                    pl.landDir.copy(dir);
                    pl.mode = 'idle';
                    pl.planted = true;
                    pl.initialized = true;
                } else if (!pl.initialized || pl.mode === 'idle') {
                    seedLeg(pl, ph, duty, stride, cycleT, speed, dir);
                } else if (stance) {
                    if (pl.mode !== 'stance') {
                        pl.foot.copy(pl.next);       // one touchdown commit
                        pl.foot.y = 0;
                        pl.contactDir.copy(pl.landDir);
                        pl.mode = 'stance';
                    }
                    pl.planted = true;              // world point stays fixed
                } else {
                    if (pl.mode !== 'swing') {
                        // One lift-off capture and one fixed, predicted landing.
                        pl.lift.copy(pl.foot);
                        pl.liftDir.copy(pl.contactDir);
                        const remain = (1 - ss) * (1 - duty) * cycleT;
                        predictPose(remain, speed, TMPg.pose, TMPg.d1);
                        homeAt(l, TMPg.pose, TMPg.d1, TMPg.home);
                        pl.next.copy(TMPg.home).addScaledVector(TMPg.d1, lead);
                        pl.landDir.copy(TMPg.d1);
                        pl.mode = 'swing';
                    }
                    sampleSwing(pl, ss, pl.foot);
                    pl.planted = false;
                }

                const heelMax = l.fore ? 0.26 : 0.48;
                const hangHeel = l.fore ? 0.10 : 0.18;
                let heel = 0;

                if (moving && stance) {
                    const push = ramp(sp, 0.55, 0.98);
                    heel = heelMax * push;
                    TMPg.axis.copy(pl.contactDir);   // no planted-paw twist
                } else if (moving) {
                    heel = THREE.MathUtils.lerp(
                        heelMax, hangHeel, ramp(ss, 0.00, 0.32),
                    ) * (1 - ramp(ss, 0.58, 1.00));
                    TMPg.axis.lerpVectors(
                        pl.liftDir, pl.landDir, ease5(ss),
                    ).normalize();
                } else {
                    TMPg.axis.copy(dir);
                }

                // Scapula glide is heading-projected and happens BEFORE IK.
                if (l.fore && l.scapula) {
                    homeAt(l, st.pos, dir, TMPg.home);
                    const along = TMPg.rel.copy(pl.foot)
                        .sub(TMPg.home).dot(dir);
                    const reach = THREE.MathUtils.clamp(
                        along / Math.max(stanceTravel * 0.5, dims.legL * 0.08),
                        -1, 1,
                    );
                    l.scapula.quaternion.setFromEuler(
                        new THREE.Euler(-reach * 0.16, 0, 0),
                    );
                }

                // Heel-pivot hock/carpus target.
                const chain = l.chain;
                const bindOff = TMPg.bindOff.copy(
                    chain[2].userData.bindPos,
                ).sub(chain[3].userData.bindPos);
                const offY = bindOff.y;
                const offZ = Math.sign(bindOff.z || -1)
                    * Math.hypot(bindOff.x, bindOff.z);
                const ca = Math.cos(heel), sa = Math.sin(heel);
                const rotY = offY * ca - offZ * sa;
                const rotZ = offZ * ca + offY * sa;
                const hockTarget = TMPg.hock.set(
                    pl.foot.x + TMPg.axis.x * rotZ,
                    pl.foot.y + rotY,
                    pl.foot.z + TMPg.axis.z * rotZ,
                );

                // A slight outward pole component keeps a nearly straight
                // sagittal chain from choosing the opposite bend plane.
                TMPg.right.set(dir.z, 0, -dir.x);
                const pole = TMPg.pole.copy(dir)
                    .multiplyScalar(l.fore ? -1 : 1)
                    .addScaledVector(TMPg.right, l.side * 0.08)
                    .normalize();
                solveTwoBone(
                    chain[0], chain[1], chain[2].userData.bindPos,
                    hockTarget, pole, l.L1, l.L2,
                );

                // Aim cannon bone at the paw target.
                chain[1].updateWorldMatrix(true, false);
                const mQ = chain[1].getWorldQuaternion(IKT.q);
                const bindD = IKT.b.copy(
                    chain[3].userData.bindPos,
                ).sub(chain[2].userData.bindPos).normalize();
                chain[2].updateWorldMatrix(true, false);
                const hockW = IKT.h.setFromMatrixPosition(chain[2].matrixWorld);
                const wantW = IKT.w.copy(pl.foot).sub(hockW).normalize();
                chain[2].quaternion.setFromUnitVectors(
                    bindD,
                    wantW.applyQuaternion(IKT.q2.copy(mQ).invert()),
                );

                // Continuous paw direction: rolled push-off -> relaxed hang
                // -> level reach. Both swing boundaries equal stance.
                chain[2].updateWorldMatrix(true, false);
                const c2Q = chain[2].getWorldQuaternion(IKT.q);
                if (!moving || stance) {
                    // Digits stay flat on the ground for the whole stance.
                    // Heel-off opens the toe joint because the cannon
                    // pitches — the tip never rotates up off the ground.
                    TMPg.toe.copy(TMPg.axis).setY(0).normalize();
                } else {
                    TMPg.push.copy(pl.liftDir).setY(0).normalize();
                    // Skye 07-14: curling at 0.04 pointed the toe down while
                    // the paw was still at ground height — the tip clipped
                    // through the floor on every stride. Curl only once the
                    // leg is clearly airborne, and hang shallower.
                    // r4: the paw-fold FLOP was the hang vector itself —
                    // it pointed AGAINST travel (-axis), folding the paw
                    // backward under the cannon at mid-swing (paw sheet
                    // frames 4/14). A walking wolf's paw dips DOWN-FORWARD,
                    // never folds back.
                    TMPg.hang.set(
                        TMPg.axis.x * 0.45,
                        -0.60,
                        TMPg.axis.z * 0.45,
                    ).normalize();
                    TMPg.land.copy(pl.landDir).normalize();
                    TMPg.toe.lerpVectors(
                        TMPg.push, TMPg.hang, ramp(ss, 0.15, 0.45),
                    ).normalize();
                    TMPg.toe.lerp(
                        TMPg.land, ramp(ss, 0.55, 0.95),
                    ).normalize();
                }
                const toeBind = IKT.b.set(0, 0, 1);
                chain[3].quaternion.setFromUnitVectors(
                    toeBind,
                    TMPg.toe.applyQuaternion(IKT.q2.copy(c2Q).invert()),
                );
            }

            // Tail follows pelvic yaw rather than duplicating an unrelated
            // sine at the same phase. A footfall bounce travels down the
            // chain with a per-segment delay so it reads as a hanging brush
            // instead of a welded rod.
            let lag = -pelvisYaw * 0.55
                + Math.sin(TAU * st.phase) * 0.035 * g;
            let ti = 0;
            sk.bones.forEach((bn) => {
                if (bn.userData.role !== 'tail') return;
                const bounce = Math.sin(TAU * st.phase * 2 - ti * 0.9) * 0.028 * g;
                bn.quaternion.setFromEuler(new THREE.Euler(0.015 + bounce, lag, 0));
                lag *= 0.8; ti++;
            });

            // Talking — envelope mode maps an audio-amplitude fn straight
            // onto the jaw hinge for lipsync; procedural mode gates
            // syllables at ~4.3Hz with per-syllable amplitude variation
            // (same contract as the original creatures' say()).
            if (sk.jaw) {
                const tk = st.talk;
                let want = 0;
                if (tk) {
                    if (tk.until == null && tk.dur != null) tk.until = t + tk.dur;
                    if (tk.env) want = Math.max(0, Math.min(1, tk.env(t) || 0));
                    else if (t < (tk.until ?? Infinity)) {
                        const E = tk.energy ?? 0.85;
                        const sy = Math.sin(t * 27.2 + 1.7) * 0.5 + 0.5;
                        const am = 0.55 + 0.45 * Math.sin(t * 7.31 + 2.9);
                        want = E * Math.max(0, sy * am - 0.08);
                    } else st.talk = null;
                }
                st.jawOpen = (st.jawOpen || 0)
                    + (want - (st.jawOpen || 0)) * Math.min(1, dt * 16);
                // bind pose is WIDE OPEN: rest closes by -JAW_OPEN, talking
                // rotates back toward the sculpted gape. Rest OVERCLOSES 6%:
                // the chin/lip pad hangs below the bone line, so an exact
                // -JAW_OPEN leaves the lips visibly ajar (pose47 probe) —
                // pressing slightly past bind compresses them shut
                sk.jaw.quaternion.setFromAxisAngle(
                    JAW_AXIS, (st.jawOpen - 1.08) * JAW_OPEN);
            }
        }

        return { st, update };
    }

    // ───────────────────────────────────── spec + pipeline + bundle load ──
    async function sha12(text) {
        const buf = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(text));
        return [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, '0')).join('').slice(0, 12);
    }
    async function exists(p) { try { await Deno.stat(p); return true; } catch { return false; } }

    function specFromSkeleton(sk, o) {
        const idx = new Map(sk.bones.map((b, i) => [b, i]));
        // BEHAVIOR opts never reach the sculpt — strip them so walk/pose/
        // head/talk scenes share ONE cached body instead of re-sculpting
        // identical meshes under different hashes
        const { speed, turn, auto, fur, neckRest, headTrim, ...sculptOpts } = o;
        return {
            specimen: true, pv: 132,
            opts: sculptOpts,
            dims: sk.dims,
            bones: sk.bones.map((b, i) => ({
                i, name: b.name, role: b.userData.role,
                parent: b.parent && b.parent.isBone ? idx.get(b.parent) ?? -1 : -1,
                bind: [b.userData.bindPos.x, b.userData.bindPos.y, b.userData.bindPos.z],
                ...(b.userData.segEnd ? { segEnd: [
                    b.userData.segEnd.x, b.userData.segEnd.y, b.userData.segEnd.z] } : {}),
            })),
        };
    }

    // Derivative-based procedural micro-bump on the skinned body (Sol,
    // FUR_REVIEW3.md) — view-space normal, degenerate-safe.
    function proceduralBump(height, strength = 0.03) {
        const N = THREE.normalViewGeometry.normalize();
        const dx = THREE.positionView.dFdx();
        const dy = THREE.positionView.dFdy();
        const sx = dx.div(dx.length().max(1e-6));
        const sy = dy.div(dy.length().max(1e-6));
        const R1 = sy.cross(N);
        const R2 = N.cross(sx);
        const det = sx.dot(R1);
        const grad = det.sign().mul(
            height.dFdx().mul(R1).add(height.dFdy().mul(R2))
        ).mul(strength);
        return det.abs().max(1e-5).mul(N).sub(grad).normalize();
    }

    // LAYERED body PBR (Sol, FUR_REVIEW3.md): one material blending bare
    // skin, paw pads, oral tissue, and the nose pad by the baked partData
    // semantic masks — classic material layering, specialized wet surfaces
    // winning over the broad muzzle field.
    function makeSpecimenBodyMaterial(o = {}, baseOverride = null) {
        const pd = THREE.attribute('partData', 'vec4');
        const nose = pd.x.clamp(0, 1);
        const wet = pd.y.clamp(0, 1);
        const pad = pd.z.clamp(0, 1);
        const skin = pd.w.clamp(0, 1);
        const mouth = THREE.smoothstep(
            THREE.float(0.04), THREE.float(0.30), wet
        );
        const cavity = THREE.smoothstep(
            THREE.float(0.58), THREE.float(0.92), wet
        );

        // baked 1:1 UV albedo when present (texel paint beats 15k-vertex
        // paint); falls back to vertex color for pre-UV cache dirs
        const base = baseOverride ?? THREE.attribute('color', 'vec3');
        const p = THREE.positionGeometry;              // bind/local: no swimming

        const skinPores = THREE.mx_noise_float(
            p.mul(190).add(THREE.vec3(3.3, 7.9, 12.1))
        );
        const blotch = THREE.mx_noise_float(
            p.mul(45).add(THREE.vec3(8.2, 1.4, 5.5))
        );
        const noseMacro = THREE.mx_noise_float(
            p.mul(95).add(THREE.vec3(7.1, 2.3, 5.7))
        );
        const nosePores = THREE.mx_noise_float(
            p.mul(310).add(THREE.vec3(13.0, 1.7, 9.1))
        );
        const leather = THREE.mx_noise_float(
            p.mul(80).add(THREE.vec3(2.1, 5.3, 8.7))
        );
        const grain = THREE.mx_noise_float(
            p.mul(240).add(THREE.vec3(11.4, 3.8, 1.9))
        );
        const oral = THREE.mx_noise_float(
            p.mul(75).add(THREE.vec3(4.2, 9.1, 2.7))
        );

        const luma = base.dot(THREE.vec3(0.2126, 0.7152, 0.0722));
        const desat = THREE.vec3(luma).mul(THREE.vec3(1.04, 0.99, 0.94));
        const skinColor = THREE.mix(base, desat, THREE.float(0.24))
            .mul(THREE.mix(THREE.float(0.97), THREE.float(1.03), blotch));

        const noseColor = THREE.mix(
            THREE.vec3(0.018, 0.010, 0.008),
            THREE.vec3(0.040, 0.024, 0.018),
            noseMacro,
        );
        const padColor = THREE.mix(
            THREE.vec3(0.026, 0.016, 0.013),
            THREE.vec3(0.060, 0.039, 0.030),
            leather,
        );

        // dark red oral base, never zero; red-dominant paint = tongue keeps
        // its pink macro color
        const oralRound2 = THREE.mix(
            THREE.vec3(0.022, 0.0045, 0.005),
            THREE.vec3(0.072, 0.014, 0.016),
            oral,
        );
        const oralDepth = THREE.mix(
            oralRound2.mul(1.12), oralRound2.mul(0.72), cavity
        );
        const redDominance = base.r.sub(THREE.max(base.g, base.b));
        const tongue = THREE.smoothstep(
            THREE.float(0.02), THREE.float(0.14), redDominance
        ).mul(cavity);
        const paintedTongue = THREE.max(
            oralDepth, base.mul(THREE.vec3(0.68, 0.50, 0.52))
        );
        const mouthColor = THREE.mix(
            oralDepth, paintedTongue, tongue.mul(0.85)
        );

        // With a baked 1:1 albedo the texture IS the final pigment (the
        // nose/oral/pad colors were baked in) — re-mixing would double-tint
        // (Sol, FUR_REVIEW4). Vertex-color fallback keeps the full stack.
        let color;
        if (baseOverride) {
            color = base;
        } else {
            color = THREE.mix(base, skinColor, skin);
            color = THREE.mix(color, padColor, pad);
            color = THREE.mix(color, mouthColor, mouth);
            color = THREE.mix(color, noseColor, nose);
        }

        const wear = THREE.smoothstep(
            THREE.float(0.62), THREE.float(0.84), leather
        );
        let roughness = THREE.float(o.roughness ?? 0.62);
        roughness = THREE.mix(roughness, THREE.mix(
            THREE.float(0.67), THREE.float(0.57), skinPores
        ), skin);
        roughness = THREE.mix(roughness, THREE.mix(
            THREE.float(0.72), THREE.float(0.55), wear
        ), pad);
        const mouthRoughness = THREE.mix(
            THREE.float(0.46), THREE.float(0.34), oral
        ).sub(cavity.mul(0.025));
        roughness = THREE.mix(roughness, mouthRoughness, mouth);
        roughness = THREE.mix(roughness, THREE.mix(
            THREE.float(0.58), THREE.float(0.43), nosePores
        ), nose);

        const N = THREE.normalViewGeometry.normalize();
        let normal = N;
        normal = THREE.mix(
            normal, proceduralBump(skinPores, 0.018), skin
        ).normalize();
        normal = THREE.mix(
            normal,
            proceduralBump(leather.mul(0.7).add(grain.mul(0.3)), 0.028),
            pad,
        ).normalize();
        normal = THREE.mix(
            normal,
            proceduralBump(
                oral,
                THREE.mix(THREE.float(0.015), THREE.float(0.009), wet),
            ),
            mouth,
        ).normalize();
        normal = THREE.mix(
            normal,
            proceduralBump(
                noseMacro.mul(0.65).add(nosePores.mul(0.35)), 0.035
            ),
            nose,
        ).normalize();

        let clearcoat = THREE.float(0.0);
        clearcoat = THREE.mix(clearcoat, THREE.float(0.035), skin);
        clearcoat = THREE.mix(clearcoat, THREE.float(0.035), pad);
        clearcoat = THREE.mix(clearcoat, THREE.mix(
            THREE.float(0.12), THREE.float(0.20), wet
        ), mouth);
        clearcoat = THREE.mix(clearcoat, THREE.float(0.24), nose);

        let coatRoughness = THREE.float(0.25);
        coatRoughness = THREE.mix(coatRoughness, THREE.float(0.26), skin);
        coatRoughness = THREE.mix(coatRoughness, THREE.float(0.22), pad);
        coatRoughness = THREE.mix(coatRoughness, THREE.mix(
            THREE.float(0.15), THREE.float(0.09), wet
        ), mouth);
        coatRoughness = THREE.mix(
            coatRoughness, THREE.float(0.14), nose
        );

        let ior = THREE.float(1.43);
        ior = THREE.mix(ior, THREE.float(1.44), pad);
        ior = THREE.mix(ior, THREE.float(1.42), mouth);
        ior = THREE.mix(ior, THREE.float(1.45), nose);

        const mat = new THREE.MeshPhysicalNodeMaterial({
            metalness: 0,
            roughness: o.roughness ?? 0.62,
            ior: 1.43,
            // r184 ignores specularIntensityNode in setupSpecular()
            specularIntensity: o.bodySpecular ?? 0.43,
            clearcoat: 0,
            transparent: false,
            depthWrite: true,
        });
        mat.colorNode = color.clamp(0, 0.98);
        mat.roughnessNode = roughness.clamp(0.30, 0.74);
        mat.normalNode = normal;
        mat.clearcoatNode = clearcoat.clamp(0, 0.24);
        mat.clearcoatRoughnessNode = coatRoughness.clamp(0.08, 0.26);
        mat.clearcoatNormalNode = THREE.mix(N, normal, THREE.float(0.55))
            .normalize();
        mat.iorNode = ior;
        return mat;
    }

    // Tooth enamel (Sol, FUR_REVIEW3.md): cervical yellowing -> ivory body
    // -> milky glossy tip, with a bounded wrap + forward-scatter proxy for
    // thin-tip translucency — never transmissionNode (refraction path).
    class EnamelLightingModel extends THREE.PhysicalLightingModel {
        constructor(material) {
            super(material.useClearcoat, material.useSheen,
                material.useIridescence, material.useAnisotropy,
                material.useTransmission, material.useDispersion);
            this.enamel = material;
        }

        direct(input, builder) {
            super.direct(input, builder);

            const { lightDirection: L, lightColor, reflectedLight } = input;
            const m = this.enamel;
            const N = THREE.normalView.normalize();
            const V = THREE.positionViewDirection.normalize();
            const nl = N.dot(L).clamp(-1, 1);
            const D = nl.clamp(0, 1);

            const w = m.enamelWrapWidthNode;
            const k = m.enamelWrapMixNode;
            const W = nl.add(w).div(THREE.float(1).add(w)).clamp(0, 1);
            const Dwrap = THREE.mix(D, W, k)
                .div(THREE.float(1).add(k.mul(w)));
            const delta = Dwrap.sub(D);
            reflectedLight.directDiffuse.addAssign(
                lightColor.mul(delta).mul(
                    THREE.BRDF_Lambert({ diffuseColor: THREE.diffuseColor.rgb })
                )
            );

            const p = m.enamelBackPower;
            const phase = V.dot(L.negate()).clamp(0, 1).pow(p)
                .mul((p + 1) / (2 * Math.PI));
            reflectedLight.directDiffuse.addAssign(
                lightColor.mul(m.enamelBackColorNode)
                    .mul(phase).mul(m.enamelBackStrengthNode)
            );
        }
    }

    class ToothEnamelNodeMaterial extends THREE.MeshPhysicalNodeMaterial {
        static get type() { return 'ToothEnamelNodeMaterial'; }
        setupLightingModel() { return new EnamelLightingModel(this); }
    }

    function makeToothEnamelMaterial(o = {}) {
        const t = THREE.attribute('toothT', 'float').clamp(0, 1);
        const p = THREE.positionGeometry;
        const micro = THREE.mx_noise_float(
            p.mul(260).add(THREE.vec3(6.7, 2.4, 9.8))
        );
        const tip = THREE.smoothstep(
            THREE.float(0.62), THREE.float(0.96), t
        );
        const leaveGum = THREE.smoothstep(
            THREE.float(0.04), THREE.float(0.62), t
        );

        let color = THREE.mix(
            THREE.vec3(0.62, 0.48, 0.28),
            THREE.vec3(0.82, 0.75, 0.61),
            leaveGum,
        );
        color = THREE.mix(
            color, THREE.vec3(0.88, 0.86, 0.78), tip.mul(0.55)
        );
        color = color.mul(THREE.mix(
            THREE.float(0.975), THREE.float(1.025), micro
        ));

        const mat = new ToothEnamelNodeMaterial({
            metalness: 0,
            roughness: 0.28,
            ior: 1.62,
            specularIntensity: o.toothSpecular ?? 0.72,
            clearcoat: 0,
            transparent: false,
            depthWrite: true,
        });
        mat.colorNode = color.clamp(0, 0.94);
        mat.roughnessNode = THREE.mix(
            THREE.float(0.34), THREE.float(0.22), t
        ).add(micro.sub(0.5).mul(0.025)).clamp(0.20, 0.36);
        mat.normalNode = proceduralBump(micro, 0.0035);
        mat.clearcoatNode = THREE.mix(
            THREE.float(0.28), THREE.float(0.82), tip
        );
        mat.clearcoatRoughnessNode = THREE.mix(
            THREE.float(0.13), THREE.float(0.05), tip
        );
        mat.clearcoatNormalNode = proceduralBump(micro, 0.0012);

        mat.enamelWrapWidthNode = THREE.float(0.22);
        mat.enamelWrapMixNode = THREE.mix(
            THREE.float(0.06), THREE.float(0.11), tip
        );
        mat.enamelBackPower = 3;
        mat.enamelBackStrengthNode = THREE.mix(
            THREE.float(0.010), THREE.float(0.055), tip
        );
        mat.enamelBackColorNode = THREE.vec3(1.0, 0.62, 0.34);
        return mat;
    }

    // toothT: 0 at the gumline, 1 at the tip (cone local +Y), baked before
    // the tooth's transform so it survives rotation and merging
    function addToothTAlongLocalY(g) {
        const p = g.getAttribute('position');
        g.computeBoundingBox();
        const y0 = g.boundingBox.min.y;
        const dy = Math.max(g.boundingBox.max.y - y0, 1e-8);
        const a = new Float32Array(p.count);
        for (let i = 0; i < p.count; i++) a[i] = (p.getY(i) - y0) / dy;
        g.setAttribute('toothT', new THREE.BufferAttribute(a, 1));
        return g;
    }

    // Fur shading — Sol's PHOTOREAL v2 (FUR_REVIEW2.md), verbatim. The
    // load-bearing pieces: normalNode = normalViewGeometry (no DoubleSide
    // face flip), agouti banding per strand, deep-coat occlusion in aoNode
    // (never black root albedo), and a custom lighting model adding an
    // energy-normalized wrap-diffuse lobe + a shadow-aware forward-scatter
    // lobe per light (real rim from a real rear light — not transmission,
    // which would put the opaque coat on the refraction path).
    class FurLightingModel extends THREE.PhysicalLightingModel {
        constructor(material) {
            super(material.useClearcoat, material.useSheen,
                material.useIridescence, material.useAnisotropy,
                material.useTransmission, material.useDispersion);
            this.fur = material;
        }

        direct(input, builder) {
            // Native Physical direct diffuse, GGX, sheen, and anisotropy first.
            super.direct(input, builder);

            const { lightDirection: L, lightColor, reflectedLight } = input;
            const m = this.fur;
            // Deliberately the projected BASE normal, never the card normal.
            const N = THREE.normalViewGeometry.normalize();
            const V = THREE.positionViewDirection.normalize();
            const nl = N.dot(L).clamp(-1, 1);
            const D = nl.clamp(0, 1);

            // Energy-normalized wrap diffuse: integral over the sphere
            // matches plain Lambert exactly (see FUR_REVIEW2.md bounds).
            const w = m.furWrapWidthNode;
            const k = m.furWrapMixNode;
            const W = nl.add(w).div(THREE.float(1).add(w)).clamp(0, 1);
            const Dwrap = THREE.mix(D, W, k)
                .div(THREE.float(1).add(k.mul(w)));
            const delta = Dwrap.sub(D).mul(m.furScatterVisibilityNode);
            reflectedLight.directDiffuse.addAssign(
                lightColor.mul(delta).mul(
                    THREE.BRDF_Lambert({ diffuseColor: THREE.diffuseColor.rgb }),
                ),
            );

            // Forward scattering: normalized power lobe — at most
            // furBackStrength of incident energy, inherits the light's
            // attenuation/shadowing, vanishes with no rear light.
            const p = m.furBackPower;
            const forwardPhase = V.dot(L.negate()).clamp(0, 1).pow(p)
                .mul((p + 1) / (2 * Math.PI));
            const grazing = THREE.float(1).sub(
                N.dot(V).abs().clamp(0, 1),
            ).pow(2);
            const back = forwardPhase.mul(grazing)
                .mul(m.furBackMaskNode)
                .mul(m.furBackStrengthNode);
            reflectedLight.directDiffuse.addAssign(
                lightColor.mul(m.furBackColorNode).mul(back),
            );
        }
    }

    class FurNodeMaterial extends THREE.MeshPhysicalNodeMaterial {
        static get type() { return 'FurNodeMaterial'; }
        setupLightingModel() { return new FurLightingModel(this); }
    }

    function makeFurMaterial(baked, o = {}) {
        // Packed pv4 ABI: furData=(strandRandom, rootToTip, furSide, furFlex)
        // — separate attributes blew WebGPU's 8-vertex-buffer limit.
        const fd = THREE.attribute('furData', 'vec4');
        const rnd = fd.x.clamp(0, 1);
        const h = fd.y.clamp(0, 1);
        const signedSide = fd.z.clamp(-1, 1);
        const side = signedSide.abs();
        const flex = fd.w.clamp(0, 1);
        const ssaa = THREE.uniform(o.furSsaa ?? globalThis.SSAA_FACTOR ?? 1.0);
        // TEXTURED ROOTS (Sol, FUR_REVIEW4): follicles sample the baked
        // albedo at their root UV — the face markings carry into the coat.
        // Explicit .level(): a card has ONE root UV, so implicit derivative
        // mips would crawl at level 0.
        const root = THREE.attribute('rootData', 'vec4');
        const rootUV = root.xy.clamp(0, 1);
        const rootLod = root.z.clamp(0, 11);
        const rootAlbedo = THREE.texture(baked.albedo, rootUV).level(rootLod).rgb;
        const rootCoat = THREE.texture(baked.coat, rootUV).level(rootLod);
        const bandStrength = rootCoat.g.clamp(0.18, 1.0);
        const innerEarCream = rootCoat.b.clamp(0, 1);
        const creamHair = THREE.vec3(0.658, 0.539, 0.337); // linear #d4c29d
        const base = THREE.mix(rootAlbedo, creamHair, innerEarCream);

        // Three stable per-follicle hashes; constant over every card vertex.
        const rnd1 = THREE.fract(
            THREE.sin(rnd.mul(91.7).add(17.3)).mul(43758.5453)
        );
        const rnd2 = THREE.fract(
            THREE.sin(rnd.mul(173.3).add(41.1)).mul(24634.6345)
        );
        const rnd3 = THREE.fract(
            THREE.sin(rnd.mul(269.5).add(11.7)).mul(56445.2341)
        );

        // The speckle defect is a CARD that is nearly edge-on contributing a
        // few dark samples. normalFlat is the true card/derivative normal in
        // view space — used ONLY as an impostor correction; lighting still
        // uses the projected base normal.
        const cardFacing = THREE.normalFlat
            .dot(THREE.positionViewDirection).abs().clamp(0, 1);
        const edgeOn = THREE.float(1).sub(
            THREE.smoothstep(THREE.float(0.08), THREE.float(0.32), cardFacing)
        );
        const sideEdge = THREE.smoothstep(
            THREE.float(0.68), THREE.float(0.94), side
        );
        const speckleRisk = THREE.max(edgeOn, sideEdge);

        // One broad agouti band per strand — resolvable at 4m/720p instead
        // of subpixel zebra noise.
        const bandCenter = THREE.mix(
            THREE.float(0.50), THREE.float(0.66), rnd1
        );
        const bandHalfWidth = THREE.mix(
            THREE.float(0.085), THREE.float(0.150), rnd2
        );
        const bandFeather = THREE.mix(
            THREE.float(0.018), THREE.float(0.036), rnd3
        );
        const band = THREE.float(1).sub(THREE.smoothstep(
            bandHalfWidth,
            bandHalfWidth.add(bandFeather),
            h.sub(bandCenter).abs(),
        ));
        const bandWeight = band
            .mul(bandStrength)
            .mul(THREE.mix(THREE.float(0.82), THREE.float(1.0), rnd3))
            // Edge-on cards keep the band at 55% contrast: real ticking,
            // not dirty black speckle.
            .mul(THREE.mix(
                THREE.float(1.0), THREE.float(0.55), speckleRisk
            ));
        const bandTint = THREE.mix(
            THREE.vec3(1.0),
            THREE.vec3(0.80, 0.77, 0.74),
            bandWeight,
        );

        const rootMask = THREE.float(1).sub(
            THREE.smoothstep(THREE.float(0.08), THREE.float(0.42), h)
        );
        const tipMask = THREE.smoothstep(
            THREE.float(0.78), THREE.float(1.0), h
        );
        // 0.84 root, not 0.94: with fur albedo == skin albedo the coat
        // CAMOUFLAGES against the body under it and only silhouette fuzz
        // shows (pv6 finding — geometry was dense, contrast was zero).
        // Direct sun washes aoNode out, so some depth must live in albedo;
        // kept well above v1's 0.70 so edge-on cards stay ticking, not dirt.
        // coat.a = baked underside lift (down-facing coat brightens toward
        // the sheet's cream; counteracts strand under-shadow)
        const undersideLift = THREE.mix(
            THREE.float(1.0), THREE.float(1.72), rootCoat.a
        );
        const shaftValue = THREE.float(1.00).add(
            THREE.smoothstep(THREE.float(0.30), THREE.float(1.0), h)
                .mul(0.30)
        ).mul(undersideLift);
        const valueJitter = THREE.mix(
            THREE.float(0.97), THREE.float(1.03), rnd3
        );
        const temperature = THREE.mix(
            THREE.vec3(0.99, 1.00, 1.01),
            THREE.vec3(1.01, 1.00, 0.99),
            rnd2,
        );
        const warmth = THREE.mix(
            THREE.vec3(1.015, 1.00, 0.985),
            THREE.vec3(1.025, 1.00, 0.965),
            tipMask,
        );
        const rgb = base
            .mul(shaftValue)
            .mul(bandTint)
            .mul(valueJitter)
            .mul(temperature)
            .mul(warmth)
            .clamp(0, 0.98);

        // Opaque numeric cutout. No A2C (single-sample target drops the
        // draw) and no alphaHash (stochastic coverage = crawling speckle).
        const rootAlpha = THREE.smoothstep(
            THREE.float(0.04), THREE.float(0.14), h
        );
        const widthAlpha = THREE.float(1).sub(THREE.smoothstep(
            THREE.float(0.68), THREE.float(0.98), side
        ));
        const tipAlpha = THREE.float(1).sub(THREE.smoothstep(
            THREE.float(0.90), THREE.float(1.00), h
        ));
        const alpha = rootAlpha.mul(widthAlpha).mul(tipAlpha).clamp(0, 1);
        const cut = o.furAlphaTest ?? 0.34;

        // RESOLVABILITY RETIREMENT (Sol, FUR_REVIEW3): derivatives measure
        // the card's projected width in high-res pixels; divide by the SSAA
        // factor for DELIVERED pixels, and erode alpha toward full discard
        // as the card falls below ~1px — unresolved cards retire instead of
        // popping. Euclidean gradient avoids fwidth's orientation bias.
        const sideGrad = THREE.vec2(
            THREE.dFdx(signedSide), THREE.dFdy(signedSide)
        ).length().max(1e-4);
        const cardPxFinal = THREE.float(2.0).div(sideGrad).div(ssaa);
        const resolved = THREE.smoothstep(
            THREE.float(0.55), THREE.float(1.10), cardPxFinal
        );
        const stableAlpha = alpha.sub(
            THREE.float(1).sub(resolved).mul(THREE.float(1.0 - cut))
        ).clamp(0, 1);
        const coverage = THREE.smoothstep(
            THREE.float(cut), THREE.float(0.86), stableAlpha
        );

        // Deep roots receive less indirect light; longer coat gets more
        // depth; edge-on cards relax toward 1 (the targeted speckle fix).
        const aoDepth = THREE.mix(
            THREE.float(0.16), THREE.float(0.32), flex
        );
        const occludedAO = THREE.float(1).sub(rootMask.mul(aoDepth));
        const rootAO = THREE.mix(
            occludedAO,
            THREE.float(1.0),
            speckleRisk.mul(0.65),
        ).clamp(0.68, 1.0);

        const mat = new FurNodeMaterial({
            metalness: 0,
            roughness: 0.80,
            ior: 1.55,
            specularIntensity: o.furSpecular ?? 0.25,
            side: THREE.DoubleSide,
            shadowSide: THREE.DoubleSide,
            transparent: false,
            depthWrite: true,
            alphaTest: cut,
            alphaToCoverage: false,
        });

        // colorNode.a is required by r184's generated shadow material.
        mat.colorNode = THREE.vec4(rgb, stableAlpha);
        mat.normalNode = THREE.normalViewGeometry;
        mat.aoNode = rootAO;
        mat.furSsaaNode = ssaa;
        // auto-enhance must NOT flip A2C back on — single-sample target
        mat.userData.noAutoAlphaToCoverage = true;

        // Pelt, not varnished plastic: broad primary lobe, rough roots,
        // slightly cleaner guard tips.
        mat.roughnessNode = THREE.mix(
            THREE.float(0.84),
            THREE.float(0.71),
            THREE.smoothstep(THREE.float(0.08), THREE.float(0.95), h),
        ).add(rnd2.sub(0.5).mul(0.04))
            .add(band.mul(0.02))
            .clamp(0.69, 0.87);
        mat.sheenNode = rgb.mul(o.furSheen ?? 0.11).clamp(0, 0.14);
        mat.sheenRoughnessNode = THREE.float(
            o.furSheenRoughness ?? 0.86
        );
        const anisotropy = THREE.mix(
            THREE.float(0.26),
            THREE.float(o.furAnisotropy ?? 0.50),
            THREE.smoothstep(THREE.float(0.12), THREE.float(0.92), h),
        ).mul(THREE.mix(
            THREE.float(0.88), THREE.float(1.0), flex
        ));
        mat.anisotropyNode = THREE.vec2(anisotropy, THREE.float(0));
        mat.anisotropyRotation = 0;

        // Custom direct-light nodes consumed by FurLightingModel.
        mat.furWrapWidthNode = THREE.float(o.furWrap ?? 0.40);
        mat.furWrapMixNode = THREE.float(o.furWrapMix ?? 0.18);
        mat.furScatterVisibilityNode = THREE.mix(
            THREE.float(0.55),
            THREE.float(1.0),
            THREE.smoothstep(THREE.float(0.08), THREE.float(0.55), h),
        );
        mat.furBackPower = o.furBackPower ?? 5;
        mat.furBackStrengthNode = THREE.float(o.furBackStrength ?? 0.14);
        mat.furBackMaskNode = THREE.smoothstep(
            THREE.float(0.12), THREE.float(0.90), h
        ).mul(coverage);
        mat.furBackColorNode = rgb.mul(THREE.vec3(1.0, 0.68, 0.38));

        // Default zero: the per-light backscatter supplies the real rim.
        // v1's unconditional 0.012 glow double-counted it.
        const grazing = THREE.float(1).sub(
            THREE.normalViewGeometry
                .dot(THREE.positionViewDirection).abs().clamp(0, 1)
        );
        mat.emissiveNode = rgb.mul(grazing.pow(4))
            .mul(o.furRim ?? 0.0)
            .mul(coverage);

        mat.maskShadowNode = alpha.greaterThan(THREE.float(cut));
        return mat;
    }

    // Wet-cornea wolf eye — Sol's recipe (FUR_REVIEW2.md): amber fibered
    // iris, pupil + dark limbal ring, glossy clearcoat over a rougher
    // pigmented base. Assumes the eye mesh's local +Z is its optical axis.
    function makeWolfEyeMaterial() {
        const p = THREE.positionGeometry.normalize();
        const radial = p.x.pow(2).add(p.y.pow(2)).sqrt();
        const front = p.z;
        // iris covers more of the visible ball and reads BRIGHT amber —
        // the sheet's eyes are almost glowing (07-14 face dial-in)
        const irisMask = THREE.smoothstep(
            THREE.float(0.10), THREE.float(0.40), front
        );
        const pupil = THREE.float(1).sub(THREE.smoothstep(
            THREE.float(0.13), THREE.float(0.20), radial
        )).mul(irisMask);
        const limbal = THREE.smoothstep(
            THREE.float(0.72), THREE.float(0.90), radial
        ).mul(irisMask);
        const theta = THREE.atan(p.y, p.x);
        const fibers = THREE.sin(theta.mul(48).add(radial.mul(36)))
            .mul(0.5).add(0.5);
        const amber = THREE.mix(
            THREE.vec3(0.28, 0.120, 0.020),
            THREE.vec3(0.72, 0.42, 0.100),
            fibers,
        );
        let eye = THREE.mix(
            THREE.vec3(0.004, 0.003, 0.002), amber, irisMask
        );
        eye = THREE.mix(
            eye, THREE.vec3(0.003, 0.002, 0.001), limbal.mul(0.92)
        );
        eye = THREE.mix(eye, THREE.vec3(0.001), pupil);

        const mat = new THREE.MeshPhysicalNodeMaterial({
            metalness: 0,
            roughness: 0.24,
            ior: 1.376,
            specularIntensity: 0.95,
            clearcoat: 1.0,
            clearcoatRoughness: 0.025,
        });
        mat.colorNode = eye;
        // a whisper of emissive so the socket shadow can't swallow the
        // iris (the eye read as a dark smudge from every distance)
        mat.emissiveNode = amber.mul(irisMask).mul(0.22);
        return mat;
    }

    // Stable fur position (Sol, FUR_REVIEW3): COHERENT subpixel sway (the
    // old rnd*2pi phase made adjacent cards boil independently — 2.4mm was
    // 0.5-0.8px of per-strand random motion at the walk camera) + an exact
    // projected-width floor from the baked furCenter centerline: cards
    // widen toward ~1.1 DELIVERED pixels, capped so edge-on cards never
    // inflate into ribbons. Sway is applied to center AND edge, so it can
    // never change card width. Call AFTER fur.bind().
    function addStableFurPosition(mat, fur, o = {}) {
        const ssaa = mat.furSsaaNode || THREE.uniform(o.furSsaa ?? 1.0);
        const minOutPx = THREE.uniform(o.furMinPixels ?? 1.10);
        const maxScale = THREE.float(o.furMaxWidthScale ?? 1.7);
        const fd = THREE.attribute('furData', 'vec4');
        const h = fd.y.clamp(0, 1);
        const rnd = fd.x.clamp(0, 1);
        const flex = fd.w.clamp(0, 1);

        // positionLocal/normalLocal/tangentLocal are already post-skin here.
        const N = THREE.normalLocal.normalize();
        const T0 = THREE.tangentLocal;
        const T = T0.sub(N.mul(N.dot(T0))).normalize();
        const B = N.cross(T).normalize();

        const amplitude = THREE.uniform(o.amplitude ?? 0.0007);
        const speed = THREE.uniform(o.speed ?? 0.78);
        const P0 = THREE.positionLocal;
        const C0 = THREE.skinning(fur).getSkinnedPosition(
            undefined, THREE.attribute('furCenter', 'vec3')
        );

        // one spatial field moves a patch together; random phase is only
        // +/-0.175 rad, not an unrelated cycle per follicle
        const phase = THREE.time.mul(speed)
            .add(rnd.sub(0.5).mul(0.35))
            .add(C0.z.mul(1.70))
            .add(C0.x.mul(0.43));
        const gust = THREE.sin(
            THREE.time.mul(0.23)
                .add(C0.x.mul(1.13))
                .sub(C0.z.mul(0.71))
        );
        const sway = T.mul(
            THREE.sin(phase).mul(0.35).add(gust.mul(0.65))
        ).add(B.mul(
            THREE.sin(phase.mul(1.37).add(2.10)).mul(0.18)
        )).mul(h.pow(2)).mul(flex).mul(amplitude);

        const P = P0.add(sway);
        const C = C0.add(sway);

        const ndc = (q) => {
            const view = THREE.modelViewMatrix.mul(THREE.vec4(q, 1));
            const clip = THREE.cameraProjectionMatrix.mul(view);
            return clip.xy.div(clip.w.abs().max(1e-5));
        };
        const halfPx = ndc(P).sub(ndc(C))
            .mul(THREE.screenSize.mul(0.5))
            .length().max(0.05);
        const targetHalfPx = minOutPx.mul(ssaa).mul(0.5);
        const widthScale = targetHalfPx.div(halfPx)
            .clamp(1.0, maxScale);

        const wide = C.add(P.sub(C).mul(widthScale));
        mat.positionNode = wide;

        // never recompute a camera-pixel width in the light's frame
        mat.castShadowPositionNode = P;
        return { ssaa, minOutPx, amplitude, speed };
    }

    function geometryFromBundle(header, bytes) {
        const g = new THREE.BufferGeometry();
        const view = (name, Ctor) => {
            const h = header[name];
            return new Ctor(bytes.buffer, bytes.byteOffset + h.offset, h.count * h.components);
        };
        g.setAttribute('position', new THREE.BufferAttribute(view('position', Float32Array), 3));
        g.setAttribute('normal', new THREE.BufferAttribute(view('normal', Float32Array), 3));
        if (header.color) g.setAttribute('color', new THREE.BufferAttribute(view('color', Float32Array), 3));
        if (header.rootData) g.setAttribute('rootData', new THREE.BufferAttribute(view('rootData', Float32Array), 4));
        if (header.furData) g.setAttribute('furData', new THREE.BufferAttribute(view('furData', Float32Array), 4));
        if (header.furCenter) g.setAttribute('furCenter', new THREE.BufferAttribute(view('furCenter', Float32Array), 3));
        if (header.uv) g.setAttribute('uv', new THREE.BufferAttribute(view('uv', Float32Array), 2));
        if (header.partData) g.setAttribute('partData', new THREE.BufferAttribute(view('partData', Float32Array), 4));
        if (header.tangent) g.setAttribute('tangent', new THREE.BufferAttribute(view('tangent', Float32Array), 4));
        g.setAttribute('skinIndex', new THREE.BufferAttribute(view('skinIndex', Uint16Array), 4));
        g.setAttribute('skinWeight', new THREE.BufferAttribute(view('skinWeight', Float32Array), 4));
        g.setIndex(new THREE.BufferAttribute(view('index', Uint32Array), 1));
        return g;
    }

    async function runSculpt(specPath, outDir) {
        const cmd = new Deno.Command('python', {
            args: [`${LAB}/sculpt_creature.py`, '--spec', specPath, '--out', outDir],
            stdout: 'piped', stderr: 'piped' });
        const out = await cmd.spawn().output();
        const log = new TextDecoder().decode(out.stdout) + new TextDecoder().decode(out.stderr);
        for (const line of log.split('\n')) if (/sculpt|calipers|quadriflow/.test(line)) console.log('[specimen]', line.trim());
        if (!out.success) throw new Error(`[specimen] sculpt failed:\n${log.slice(-2000)}`);
    }

    globalThis.makeSpecimen = async function (opts = {}) {
        const o = { stance: 'quad', ...opts };
        if (o.stance !== 'quad') throw new Error('[specimen] v1 sculpts quads; more stances land with the parity sweep');
        const sk = buildSkeleton(o);
        const group = new THREE.Group();
        group.add(sk.pelvis);
        // ORDER MATTERS: Skeleton() captures boneInverses from the bones'
        // CURRENT matrixWorld — with stale (identity) matrices the inverses
        // are identity and every vertex gets its bone's ABSOLUTE position
        // added on top of its own (the smeared-giraffe bug)
        group.updateMatrixWorld(true);
        const skeleton = new THREE.Skeleton(sk.bones);

        const spec = specFromSkeleton(sk, o);
        const specJson = JSON.stringify(spec);
        const hash = await sha12(specJson);
        const dir = `${LAB}/cache/${hash}`;
        if (!(await exists(`${dir}/creature_mesh.json`))) {
            console.log(`[specimen] cache miss ${hash} — sculpting...`);
            await Deno.mkdir(dir, { recursive: true });
            await Deno.writeTextFile(`${dir}/spec.json`, specJson);
            await runSculpt(`${dir}/spec.json`, dir);
        } else console.log(`[specimen] cache hit ${hash}`);

        const header = JSON.parse(await Deno.readTextFile(`${dir}/creature_mesh.json`));
        const bytes = await Deno.readFile(`${dir}/creature_mesh.bin`);
        const g = geometryFromBundle(header, bytes);
        if (!g.getAttribute('partData')) {
            throw new Error('[specimen] pv38+ body is missing required partData');
        }
        let baseTexNode = null;
        let bodyAlbedoTex = null;
        if (header.aux?.textures?.albedo && o.bakedTextures !== false
            && globalThis.loadImageTexture) {
            const texBytes = await Deno.readFile(`${dir}/${header.aux.textures.albedo}`);
            bodyAlbedoTex = await globalThis.loadImageTexture(texBytes, { srgb: true });
            baseTexNode = THREE.texture(bodyAlbedoTex);
            console.log('[specimen] baked 1:1 albedo texture bound');
        }
        const mat = makeSpecimenBodyMaterial(o, baseTexNode);
        const sm = new THREE.SkinnedMesh(g, mat);
        sm.name = 'specimenBody';
        sm.castShadow = true; sm.receiveShadow = true; sm.frustumCulled = false;
        group.add(sm);
        sm.bind(skeleton, sm.matrixWorld);

        if (header.aux && header.aux.eyes) {
            const eyeMat = makeWolfEyeMaterial();
            const bindP = sk.head.userData.bindPos;
            // the iris pattern lives on local +Z: aim each eye along its
            // socket's outward direction (eye center relative to the skull
            // center approximates the orbital axis)
            const rBody2 = o.bodyRadius ?? sk.dims.L * 0.16;
            const rHd2 = Math.max(rBody2 * 0.68, sk.dims.neckL * 0.5);
            const tH2 = V(0, 0.18, 0.98).normalize();
            const uH2 = V(0, 1, 0).addScaledVector(tH2, -tH2.y).normalize();
            const skullC2 = bindP.clone()
                .addScaledVector(tH2, rHd2 * 0.1).addScaledVector(uH2, rHd2 * 0.18);
            for (const e of header.aux.eyes) {
                const eye = new THREE.Mesh(new THREE.SphereGeometry(e.r * 0.95, 24, 16), eyeMat);
                eye.name = 'specimenEye';
                eye.position.set(e.c[0] - bindP.x, e.c[1] - bindP.y, e.c[2] - bindP.z);
                // converge the gaze FORWARD: pure socket-outward aimed
                // the iris ~68deg sideways, so front-on views saw only the
                // dark sclera — the eyes read as smudges (07-14)
                const outward = new THREE.Vector3(e.c[0], e.c[1], e.c[2])
                    .sub(skullC2).normalize()
                    .multiplyScalar(0.45).addScaledVector(tH2, 0.85)
                    .normalize();
                eye.quaternion.setFromUnitVectors(V(0, 0, 1), outward);
                sk.head.add(eye);
            }
        }
        if (header.aux && header.aux.mouth && sk.jaw) {
            // DENTAL ARCADES: tooth rows that FOLLOW THE MAW — incisors at
            // the front, the big canine behind them, premolars along the
            // cheek line. Uppers ride the head bone along the lip line;
            // lowers ride the open-bound jaw along the jawline (closing
            // carries them up into occlusion).
            const rHd = Math.max((o.bodyRadius ?? sk.dims.L * 0.16) * 0.73, sk.dims.neckL * 0.35);
            const toothMat = makeToothEnamelMaterial(o);
            const mkTooth = (parent, pos, up, r, len, tiltZ) => {
                const bp = parent.userData.bindPos;
                const tooth = new THREE.Mesh(
                    addToothTAlongLocalY(new THREE.ConeGeometry(r, len, 7, 3)), toothMat);
                tooth.name = 'specimenTooth';
                tooth.position.set(pos.x - bp.x, pos.y - bp.y, pos.z - bp.z);
                tooth.rotation.x = up ? Math.PI : 0;   // uppers point down
                tooth.rotation.z = tiltZ;
                parent.add(tooth);
            };
            // (s along the row 0=front…1=corner, radius·rHd, length·rHd)
            // ref sheet: incisors sit on a forward ARCH between the two
            // long back-curved canines; premolars trail along the cheek
            // lengths trimmed ~15% (pose48: tooth tips peeked through the
            // CLOSED mouth seam — the canine stays the dominant fang open)
            const PLAN = [
                [0.015, 0.016, 0.050, 0.050], [0.055, 0.017, 0.052, 0.035], [0.10, 0.019, 0.055, 0.015],
                [0.17, 0.030, 0.140, 0.0],                             // canine
                [0.34, 0.020, 0.060, 0.0], [0.48, 0.023, 0.068, 0.0], [0.63, 0.025, 0.072, 0.0],
            ];
            const ma = header.aux.mouth.a, mb = header.aux.mouth.b;
            const A = V(ma[0], ma[1], ma[2]), B = V(mb[0], mb[1], mb[2]);
            const hingeV = sk.jaw.userData.bindPos;
            const chinV = sk.jaw.userData.segEnd;
            for (const side of [-1, 1]) {
                for (const [s, r, len, arch] of PLAN) {
                    // arc half-width: narrow at the muzzle tip, wide at the
                    // cheeks — the rows hug the maw instead of floating
                    const w = rHd * (0.09 + 0.30 * s);
                    const pu = A.clone().lerp(B, s);
                    pu.x += side * w;
                    pu.y += rHd * 0.055;
                    pu.z += rHd * arch;      // incisor arch bulges forward
                    mkTooth(sk.head, pu, true, rHd * r, rHd * len, -side * 0.12);
                    // lower arcade sits WELL inside the upper (occlusion):
                    // 0.82 lateral put the rear lowers outside the mandible
                    // flesh — they pierced the cheek when the jaw pressed
                    // shut (pose49 face probe)
                    const sl = 0.06 + s * 0.62;
                    const pl = chinV.clone().lerp(hingeV, sl);
                    pl.x += side * w * 0.70;
                    pl.y -= rHd * 0.015;
                    pl.z += rHd * arch * 0.7;
                    mkTooth(sk.jaw, pl, false, rHd * r * 0.9, rHd * len * 0.75, side * 0.10);
                }
            }
        }

        // FUR: a second skinned mesh sharing the skeleton (the TOTM
        // blade-mesh technique, FUR_BRIEF.md) — blades carry the BASE
        // surface's normal and color so they shade exactly like the skin;
        // uv = (strandRandom, rootToTip) drives the material ramp.
        if (o.fur) {
            const FUR_PV = 24;   // matches fur_bake.py — stale bakes rebuild
            let fhdr = (await exists(`${dir}/fur_mesh.json`))
                ? JSON.parse(await Deno.readTextFile(`${dir}/fur_mesh.json`)) : null;
            if (!fhdr || fhdr.furPv !== FUR_PV) {
                console.log('[specimen] fur cache miss/stale — baking blades...');
                const cmd = new Deno.Command('python', {
                    args: [`${LAB}/fur_bake.py`, dir], stdout: 'piped', stderr: 'piped' });
                const out = await cmd.spawn().output();
                const flog = new TextDecoder().decode(out.stdout) + new TextDecoder().decode(out.stderr);
                for (const line of flog.split('\n')) if (line.trim()) console.log('[specimen]', line.trim());
                if (!out.success) throw new Error(`[specimen] fur bake failed:\n${flog.slice(-1200)}`);
                fhdr = JSON.parse(await Deno.readTextFile(`${dir}/fur_mesh.json`));
            }
            const fbytes = await Deno.readFile(`${dir}/fur_mesh.bin`);
            const fg = geometryFromBundle(fhdr, fbytes);
            // never recompute normals/tangents here — that would replace the
            // projected TOTM frame with the cards' geometric frame
            if (!baseTexNode) {
                throw new Error('[specimen] fur pv13 requires the baked texture set');
            }
            const coatBytes = await Deno.readFile(`${dir}/coat.png`);
            const coatTex = await globalThis.loadImageTexture(coatBytes);   // linear
            const fmat = makeFurMaterial({ albedo: bodyAlbedoTex, coat: coatTex }, o);
            const fur = new THREE.SkinnedMesh(fg, fmat);
            fur.name = 'specimenFur';
            fur.receiveShadow = true;
            // dense individual-card shadows are a close-shot option — the
            // body remains the stable default shadow caster (FUR_REVIEW.md)
            fur.castShadow = o.furShadows === true;
            fur.frustumCulled = false;
            group.add(fur);
            fur.bind(skeleton, fur.matrixWorld);
            if (!fg.getAttribute('furCenter')) {
                throw new Error('[specimen] stable-width fur bake is missing furCenter');
            }
            addStableFurPosition(fmat, fur, {
                furSsaa: o.furSsaa ?? globalThis.SSAA_FACTOR ?? 1,
                furMinPixels: o.furMinPixels ?? 1.10,
                furMaxWidthScale: o.furMaxWidthScale ?? 1.7,
                amplitude: o.furSway === false ? 0
                    : (typeof o.furSway === 'number' ? o.furSway : 0.0007),
                speed: o.furSwaySpeed ?? 0.78,
            });
        }

        const gait = makeGait(sk, o, group);
        const api = {
            group, skeleton, bones: sk.bones, head: sk.head, mesh: sm,
            update: gait.update,
            get speed() { return gait.st.speed; }, set speed(v) { gait.st.speed = v; },
            set neckRest(v) { o.neckRest = v; }, set headTrim(v) { o.headTrim = v; },
            get turn() { return gait.st.turn; }, set turn(v) { gait.st.turn = v; },
            setHeading(a) { gait.st.heading = a; },
            // TALKING — same contract as the original creatures:
            //   c.say('Some words to speak')       // duration from word count
            //   c.say({ duration: 4, energy: 0.9 })
            //   c.talking = true;                  // continuous until = false
            //   c.setTalkEnvelope((t) => amp01)    // drive from an audio envelope
            say(txt) {
                let t = txt;
                if (typeof t === 'string') t = { duration: Math.max(1.2, t.split(/\s+/).length / 2.6) };
                gait.st.talk = { dur: (t && t.duration) ?? 3, until: null,
                    energy: (t && t.energy) ?? 0.85, env: (t && t.envelope) || null };
                return api;
            },
            get talking() { return !!gait.st.talk; },
            set talking(v) { gait.st.talk = v ? { until: Infinity, energy: 0.85, env: null } : null; },
            setTalkEnvelope(fn) { gait.st.talk = fn ? { until: Infinity, env: fn } : null; return api; },
            get hasJaw() { return !!sk.jaw; },
            walkTo(x, z, speed) { gait.st.target = { x, z }; if (speed != null) gait.st.speed = speed; else if (gait.st.speed < 0.05) gait.st.speed = 0.5; },
        };
        if (o.auto !== false) (globalThis._autoCreatures || (globalThis._autoCreatures = [])).push(gait.update);
        return api;
    };

    console.log('[creature_specimen] makeSpecimen ready — ground-up realist creature: own anatomy skeleton (scapula/digitigrade), own 4-beat gait, sculpted profile-loft body (cached), makeCreature option vocabulary');
})();
