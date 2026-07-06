// character_controller.js — VRM character controller built on
// Rapier kinematic bodies, designed to coexist cleanly with leg IK.
//
// Design (per user's prior ragdoll work in claudethinking/claude-says):
//   • UPPER-BODY-ONLY cylinder collider (hip → head). Small bumps below
//     hip-Y pass UNDER the cylinder, so the body doesn't get teleported up
//     by autostep on every small obstacle.
//   • Legs are kinematic + animation-driven, NO physics collider. Visual
//     foot placement is handled entirely by leg IK (eidoverse_legik.js).
//   • Manual ground detection: TWO downward raycasts at approximate left
//     and right foot tracks. Body Y follows the LOWER hit (the load-bearing
//     leg) so when one foot is over a bump and the other on the floor, the
//     body stays at floor height — the IK then does its job lifting the
//     bumped foot onto the bump.
//   • Rapier's CharacterController still does X/Z move-and-slide against
//     walls. Autostep is configured for moderate obstacles (0.3m) — only
//     things tall enough to hit the cylinder above hip-Y.
//
// Future: per-limb capsules (one per bone segment) for ragdoll mode. Same
// architecture — kinematic during locomotion, dynamic during knockdown.
//
// Usage:
//   const ctrl = new VRMCharacterController(vrm, world, RAPIER, {
//       startPosition: [0, 0, 5],   // feet at this world position
//       footStanceX: 0.11,           // half-distance between feet
//   });
//   each frame:
//       ctrl.update(dt, { z: -1.5 });   // signed move velocity in m/s
//       vrm.scene.position.copy(ctrl.feetWorldPosition);
//       // grounded / speedActual / groundY available on ctrl

(function () {
    if (!globalThis.THREE) {
        console.warn('[eidoverse-controller] THREE global not present — skipping');
        return;
    }
    const THREE = globalThis.THREE;

    class VRMCharacterController {
        constructor(vrm, world, RAPIER, opts = {}) {
            this.vrm = vrm;
            this.world = world;
            this.RAPIER = RAPIER;

            // Register this VRM as controller-driven so the render harness's
            // foot-slide detector knows its translation is legit (stride synced
            // to speed), instead of flagging it as hand-rolled locomotion.
            // Additive only — does not touch locomotion/IK behaviour.
            try {
                (globalThis._controllerVrms || (globalThis._controllerVrms = new Set())).add(vrm?.scene || vrm);
            } catch (e) { /* registration is best-effort */ }

            // Measure VRM dimensions
            const bbox = new THREE.Box3().setFromObject(vrm.scene);
            const vrmHeight = bbox.max.y - bbox.min.y;
            const vrmFootY = bbox.min.y;

            // Hip world Y in rest pose — defines where the upper-body cylinder
            // bottom sits.
            const hipBoneNode = vrm.humanoid.getNormalizedBoneNode('hips');
            if (!hipBoneNode) throw new Error('[eidoverse-controller] vrm.humanoid hips bone missing');
            const hipRestWorld = new THREE.Vector3();
            hipBoneNode.getWorldPosition(hipRestWorld);
            const hipY = hipRestWorld.y - vrmFootY;

            const upperHeight = vrmHeight - hipY;
            const halfH = upperHeight / 2;
            const radius = opts.cylinderRadius ?? 0.22;
            const centerAboveFeet = hipY + halfH;

            this.vrmHeight   = vrmHeight;
            this.vrmFootY    = vrmFootY;
            this.hipY        = hipY;
            this.halfHeight  = halfH;
            this.radius      = radius;
            this.footStanceX = opts.footStanceX ?? 0.11;
            // Heading/turn control (steer model). Body turns its facing toward
            // the desired world direction at maxTurnRate, then walks forward
            // along that facing. Default π is a no-op for the straight {z:-1}
            // test input (byte-identical to pre-turning behavior). UNDER RENDER
            // VERIFICATION — not wired into the production locomotion path.
            this.maxTurnRate = opts.maxTurnRate ?? 3.5; // rad/s
            this.maxFallSpeed = opts.maxFallSpeed ?? 20.0;
            this.gravity      = opts.gravity ?? -9.81;

            const start = opts.startPosition ?? [0, 0, 0];
            const startCenter = start[1] + centerAboveFeet;

            const bodyDesc = RAPIER.RigidBodyDesc.kinematicPositionBased()
                .setTranslation(start[0], startCenter, start[2]);
            this.body = world.createRigidBody(bodyDesc);
            this.collider = world.createCollider(
                RAPIER.ColliderDesc.cylinder(halfH, radius),
                this.body,
            );

            this.controller = world.createCharacterController(opts.skin ?? 0.05);
            // Slope/autostep/snap-to-ground are all OFF — MSCC ground-projection
            // pattern handles Y entirely. Rapier here only does X/Z move-and-slide
            // against walls and the upper-body cylinder collider.
            this.controller.setMaxSlopeClimbAngle((opts.maxSlope ?? 60) * Math.PI / 180);
            this.controller.setApplyImpulsesToDynamicBodies(false);

            this._velocityY = 0;
            this._lastZ = start[2];
            this._lastX = start[0];
            // Turning is OPT-IN (default OFF) so the controller is byte-identical
            // for every existing scene until turning is render-verified.
            this._turningEnabled = opts.enableTurning === true;
            this._heading = opts.startHeading ?? Math.PI;
            this.grounded = false;
            this.groundY = -Infinity;
            this.speedActual = 0;
            this.supportFrame = null;
            this.externalGroundY = null;
            this._footSupportObservation = null;
            this._useFootSupportForRoot = false;
            this._footSupportRootStableFrames = 4;
            this._footSupportRootMaxDelta = 0.08;
            this._footSupportStableFrames = 0;
            this._lastFootSupportY = null;

            // MSCC pattern parameters
            // Fall threshold — if the detected ground is more than this many
            // meters below the body's feet, controller switches to airborne
            // (gravity-driven Y) instead of smooth-damping body Y to ground.
            // Without this, walking off a stair top is handled by smooth-damp
            // and never registers as a fall — IK keeps running, walk pose
            // continues, no falling animation triggers, and the descent reads
            // as a fast smooth interpolation rather than physical free-fall.
            // 0.4m = a tall step or knee-height drop; anything taller is a fall.
            this.fallThreshold = opts.fallThreshold ?? 0.4;
            this.maxClimbAngle = opts.maxClimbAngle ?? 50;       // degrees — block stepping up onto anything steeper
            this.lookAhead = opts.lookAhead ?? 0.35;             // distance ahead to project ground target
            this.smallStairAscentEarlyLookAhead = opts.smallStairAscentEarlyLookAhead ?? 0.76;
            this.smallStairAscentEarlyProbeCount = opts.smallStairAscentEarlyProbeCount ?? 36;
            this.smallStairAscentEarlyMinPositiveEdges = opts.smallStairAscentEarlyMinPositiveEdges ?? 2;
            this.smallStairAscentEarlyMaxNegativeEdges = opts.smallStairAscentEarlyMaxNegativeEdges ?? 0;
            this.smallStairAscentEarlyHoldFrames = opts.smallStairAscentEarlyHoldFrames ?? 8;
            this._smallStairAscentEarlyFrames = 0;
            this.smallStairAscentEarlyUp = false;
            this.smallStairAscentEarlyInfo = null;
            // Convention: allow the pelvis to drop FASTER than it rises, to
            // quickly accommodate lower steps — with a RATE-CAP (m/s), not
            // exponential damp. Rate-cap is critical for stairs because the body-Y target
            // jumps in discrete tread-sized steps (0.18m), and exponential
            // damp slams the body to each new target in ~16ms which reads as
            // "body Y teleports between treads, IK chases trying to keep up,
            // legs scrunch / knees flip." Rate-cap moves the body smoothly
            // at a fixed walking rate regardless of target jumps.
            //
            // Walking down 18cm stairs at 1.5 m/s along ground = 0.81 m/s
            // descent. Cap at 2.5 m/s gives 3× headroom over walk descent.
            // For ramps the same cap easily sustains continuous slope
            // motion. Faster than 2.5 m/s reproduces the scrunching.
            this.bodyYRateDown = opts.bodyYRateDown ?? 1.2;      // m/s — descent rate cap
            this.bodyYRateUp   = opts.bodyYRateUp   ?? 1.5;      // m/s — rise rate cap
            // Legacy — only used for above-feet (rising) path with old damp;
            // keeping defaults for backwards compat with other callers.
            this.bodyYDampHz   = opts.bodyYDampHz   ?? 60;
            this.bodyYDampHzUp = opts.bodyYDampHzUp ?? 30;
            this.useContactSupportLift = opts.useContactSupportLift ?? false;
            this.contactSupportLiftMin = opts.contactSupportLiftMin ?? 0.025;
            this.contactSupportLiftMax = opts.contactSupportLiftMax ?? 0.18;
            this.contactSupportLiftRatio = opts.contactSupportLiftRatio ?? 0.55;
            this.contactSupportSwingRatio = opts.contactSupportSwingRatio ?? 0.30;
            this.contactSupportMaxRampAngle = opts.contactSupportMaxRampAngle ?? 12;
            this.useIKContactSupportLift = opts.useIKContactSupportLift ?? false;
            this.ikContactSupportLiftRatio = opts.ikContactSupportLiftRatio ?? 0.42;
            this.ikContactSupportSwingRatio = opts.ikContactSupportSwingRatio ?? 0.18;
            this.ikContactSoleGapMax = opts.ikContactSoleGapMax ?? 0.16;
            this.allowRaisedSupportDuringDescent = opts.allowRaisedSupportDuringDescent ?? false;
            this.raisedSupportMinLift = opts.raisedSupportMinLift ?? 0.045;
            this.raisedSupportAheadMin = opts.raisedSupportAheadMin ?? 0.035;
            this.raisedSupportFinishGap = opts.raisedSupportFinishGap ?? 0.015;
            this.raisedSupportLatchFrames = opts.raisedSupportLatchFrames ?? 3;
            this.raisedSupportMaxSpread = opts.raisedSupportMaxSpread ?? 0.18;
            this._raisedSupportDescentLatch = 0;
            this.useIKGroundingGrace = opts.useIKGroundingGrace ?? false;
            this.ikGroundingGraceMaxDrop = opts.ikGroundingGraceMaxDrop ?? 0.34;
            this.ikGroundingGraceMaxRise = opts.ikGroundingGraceMaxRise ?? 0.08;
            this.ikGroundingGraceMaxSoleGap = opts.ikGroundingGraceMaxSoleGap ?? 0.56;
            this.preferWalkOnUntreadedObstacles = opts.preferWalkOnUntreadedObstacles ?? false;
            this.obstacleWalkMaxRise = opts.obstacleWalkMaxRise ?? 0.18;
            this.obstacleWalkMaxSpread = opts.obstacleWalkMaxSpread ?? 0.18;
            this.preferWalkOnIsolatedObstacles = opts.preferWalkOnIsolatedObstacles ?? true;
            this._isolatedObstacleSignHoldFrames = opts.isolatedObstacleSignHoldFrames ?? 14;
            this._isolatedObstacleContextHoldFrames = opts.isolatedObstacleContextHoldFrames ?? 8;
            this._recentPositiveStepFrames = 0;
            this._recentNegativeStepFrames = 0;
            this._isolatedObstacleFrames = 0;
            this.stairLiftTrigger = opts.stairLiftTrigger ?? 0.05; // m — if a foot's ground hit exceeds current body feet Y by this much, body target = that higher foot's hit (instead of min of both feet). Below this threshold body still follows the lower foot for stability on flat / micro-bumpy ground.
            this.aheadProbeCount = opts.aheadProbeCount ?? 25;   // multi-probe forward sampling (finer for tread-run detection)
            this.forwardBias = opts.forwardBias ?? 0.5;          // 0..1 — fraction of forward probe to blend into body Y when climbing
                                                                  // (0 = pure per-foot, 1 = pure forward anticipation)
                                                                  // 0.5 raises body enough at stair entry that leg from hip
                                                                  // to foot clears stair top instead of passing through riser
                                                                  // by ~1cm. Higher = more leg clearance, more back-foot hover.
            // Target absolute clearance the body anticipates over an
            // upcoming riser (in meters). The bias formula scales the raw
            // forwardBias × aheadHit anticipation DOWN inversely with
            // detected rise so that big-rise stairs don't produce
            // proportionally bigger body lift (which reads as "slides up
            // before stepping"). 0.05m is anatomical-clearance scale.
            this.bodyAnticipationClearance = opts.bodyAnticipationClearance ?? 0.05;
            this.minStairSpeedScale = opts.minStairSpeedScale ?? 0.37;  // aggressive — matches typical residential
                                                                         // stair climb pace (~0.56 m/s = 0.37 × 1.5 base).
                                                                         // For one-step-per-tread alignment with the
                                                                         // stairsUp clip's authored stride.
            // ── MANEUVERS (vault / mount-climb / gap-jump / landing) ──────
            // One-shot root-trajectory moves layered over locomotion. When the
            // path ahead demands more than a step (a cover-height wall, a deep
            // block, a gap), the controller plays the matching one-shot clip
            // while driving the body along a procedural trajectory (the clips'
            // hips-position tracks are stripped — the controller is the sole
            // root authority, same as for walking). Auto-triggered during
            // travel (autoManeuvers) and/or explicitly via vault()/jump()/
            // climbLedge(). Foot IK + ground probing suspend for the flight;
            // landing re-grounds cleanly.
            this.autoManeuvers    = opts.autoManeuvers    ?? true;
            this.vaultMinRise     = opts.vaultMinRise     ?? 0.42;  // below this a step/stair handles it
            this.vaultMaxRise     = opts.vaultMaxRise     ?? 1.15;  // max cover height to vault over
            this.vaultMaxDepth    = opts.vaultMaxDepth    ?? 1.00;  // deeper than this → mount instead
            this.mountMaxRise     = opts.mountMaxRise     ?? 1.35;  // climbLedge onto a block/ledge
            this.wallClimbMaxRise = opts.wallClimbMaxRise ?? 2.30;  // hang-mantle mount; taller → scramble
            this.wallScrambleMaxRise = opts.wallScrambleMaxRise ?? 4.5;  // looped wall-scramble + mantle
            this.jumpAutoGap      = opts.jumpAutoGap      ?? true;
            this.jumpMaxGap       = opts.jumpMaxGap       ?? 2.20;  // widest auto-jumpable gap
            this.maneuverScanRange   = opts.maneuverScanRange   ?? 2.6;
            this.maneuverScanStep    = opts.maneuverScanStep    ?? 0.15;
            this.maneuverClearance   = opts.maneuverClearance   ?? 0.16; // apex above obstacle top
            this.maneuverCooldown    = opts.maneuverCooldown    ?? 0.5;  // s between maneuvers
            this.fallLandMinDrop     = opts.fallLandMinDrop     ?? 0.85; // falls deeper than this play fallLand
            this._maneuver = null;
            this._maneuverCooldownT = 0;
            this._fadingManeuverAction = null;
            this._airborneFromY = null;
            this._airborneTime = 0;

            this._bodyYTarget = start[1] + centerAboveFeet;
            // Y averaging window — smooths per-frame Y jitter from ground
            // projection. Smaller now (4 frames @ 30fps = ~130ms) because the
            // body-Y target itself is staircase-shaped (jumps to each higher
            // foot's tread on landing). A long average smears those step-up
            // moments and undoes the asymmetric upward damping. Just enough
            // to kill noise from forward-probe edge crossings.
            this._yAvgWindow = [];
            this._yAvgSize = opts.yAverageWindowSize ?? 4;

            // Reusable temp objects
            this._feetWorld = new THREE.Vector3();
            this._tmpPos = new THREE.Vector3();

            console.log(`[eidoverse-controller] hipY=${hipY.toFixed(3)} upperHeight=${upperHeight.toFixed(3)} halfHeight=${halfH.toFixed(3)} radius=${radius.toFixed(3)}`);
        }

        // input: { x?: number, z?: number } — desired velocity in m/s
        update(dt, input = {}) {
            const cur = this.body.translation();
            let inX = input.x ?? 0;
            let inZ = input.z ?? 0;
            const flatLen = Math.sqrt(inX*inX + inZ*inZ);

            // STEER (opt-in via enableTurning; default OFF leaves inX/inZ exactly
            // as passed = original behavior). When on: turn the facing toward the
            // input world-direction at maxTurnRate, then walk forward along the
            // facing so the stride matches travel through turns.
            if (this._turningEnabled && flatLen > 1e-4) {
                const tgtHeading = Math.atan2(inX, inZ);
                let d = tgtHeading - this._heading;
                while (d > Math.PI) d -= 2 * Math.PI;
                while (d < -Math.PI) d += 2 * Math.PI;
                const maxStep = this.maxTurnRate * dt;
                this._heading += Math.max(-maxStep, Math.min(maxStep, d));
                inX = Math.sin(this._heading) * flatLen;
                inZ = Math.cos(this._heading) * flatLen;
            }

            // ─── GROUND PROBES ─────────────────────────────────────────────
            // We cast THREE rays each frame:
            //   - leftFootRay  at (cur.x - footStanceX, ..., cur.z)
            //   - rightFootRay at (cur.x + footStanceX, ..., cur.z)
            //   - forwardRay   at (cur.x + fwd * lookAhead, ..., cur.z)
            //
            // Body Y target = MIN(leftFoot, rightFoot) + hipY + halfH. This puts
            // the body at the LOWER of the two foot tracks' ground heights, so
            // the swing-phase foot doesn't dangle above its tread. Mid-stair the
            // body is at the lower (back) foot's level, the front foot's leg IK
            // stretches up to the higher tread.
            //
            // Forward probe is used ONLY for the climb-angle gate — does not
            // determine body Y. Stops walls but doesn't cause early lift on
            // stair anticipation.
            const fwdX = flatLen > 1e-6 ? inX / flatLen : 0;
            const fwdZ = flatLen > 1e-6 ? inZ / flatLen : 0;
            const probeY = cur.y + this.halfHeight + 5.0;

            // Foot-stance axis. Flag OFF → (-1,0)·stance = the original
            // axis-aligned cur.x∓footStanceX. Flag ON → perpendicular to the
            // heading so the probes track the feet through turns.
            const _perpX = this._turningEnabled ? Math.cos(this._heading) : -1;
            const _perpZ = this._turningEnabled ? -Math.sin(this._heading) : 0;
            const leftHit  = this._groundVector(cur.x + _perpX * this.footStanceX, probeY, cur.z + _perpZ * this.footStanceX);
            const rightHit = this._groundVector(cur.x - _perpX * this.footStanceX, probeY, cur.z - _perpZ * this.footStanceX);

            // Multi-probe forward sampling: cast N rays at evenly-spaced
            // distances over [0, lookAhead] forward range. Average their Y.
            // As body crosses a tread edge, only 1/N probes transition per
            // edge, so the average moves smoothly instead of in 9cm jumps.
            // Eliminates per-tread Y jitter at its source.
            let aheadHit = null;
            // Track min/max probe Y to detect stair discontinuity. On a
            // continuous ramp, probes are monotonically increasing with
            // small per-probe deltas (max-min ≈ stride × tan(angle)). On
            // stairs, probes can hit different tread Y's giving a much
            // bigger max-min spread. Used by the test scene to fire stair
            // anim on stairs without firing on gentle ramps.
            let aheadMin = Infinity;
            let aheadMax = -Infinity;
            // Sample each probe's Y so we can detect tread RUN by counting
            // discontinuities. tread_run = lookAhead / numTransitions.
            const probeYs = [];
            if (flatLen > 1e-3) {
                const N = this.aheadProbeCount ?? 5;
                let sumY = 0, hits = 0;
                for (let i = 1; i <= N; i++) {
                    const d = (this.lookAhead * i) / N;
                    const y = this._groundVector(
                        cur.x + fwdX * d, probeY, cur.z + fwdZ * d,
                    );
                    probeYs.push({ d, y });
                    if (y !== null) {
                        sumY += y; hits++;
                        if (y < aheadMin) aheadMin = y;
                        if (y > aheadMax) aheadMax = y;
                    }
                }
                if (hits > 0) aheadHit = sumY / hits;
            }
            this.aheadProbeSpread = (aheadMax > -Infinity && aheadMin < Infinity)
                ? (aheadMax - aheadMin)
                : 0;
            // Tread RUN estimate — find each Y-discontinuity's POSITION across
            // the probe array, then measure the average distance between
            // adjacent transitions. Stairs are piecewise-flat with a small
            // number of sharp Y jumps. Curved obstacles can have comparable
            // total spread, but their Y change is distributed over many probe
            // intervals; do not let those update stair/tread-run memory.
            const transitionDs = [];
            const transitionDys = [];
            let smallDiffAbsSum = 0;
            let validAdjacentPairs = 0;
            let lastDiffSign = 0;
            let diffSignChanges = 0;
            const discontinuityThreshold = this._stairDiscontinuityThreshold ?? 0.03;
            for (let i = 1; i < probeYs.length; i++) {
                const a = probeYs[i - 1].y, b = probeYs[i].y;
                if (a === null || b === null) continue;
                const dy = b - a;
                const absDy = Math.abs(dy);
                validAdjacentPairs++;
                if (absDy > discontinuityThreshold) {
                    // Linearly interpolate within the [i-1, i] probe interval
                    // to find the fractional position of the half-jump.
                    const fract = 0.5;  // assume mid-step (no sub-probe info)
                    const dInterp = probeYs[i - 1].d + fract * (probeYs[i].d - probeYs[i - 1].d);
                    transitionDs.push(dInterp);
                    transitionDys.push(dy);
                } else {
                    smallDiffAbsSum += absDy;
                }
                if (absDy > 0.005) {
                    const s = Math.sign(dy);
                    if (lastDiffSign !== 0 && s !== lastDiffSign) diffSignChanges++;
                    lastDiffSign = s;
                }
            }

            const maxTransitionAbs = transitionDys.reduce((m, dy) => Math.max(m, Math.abs(dy)), 0);
            const maxStepTransitions = this._maxStairTransitionsInLookAhead ?? 3;
            const residualLimit = this._stairResidualLimit ?? 0.045;
            const minStepRise = this._minStairRise ?? 0.075;
            const hasStepDiscontinuity =
                transitionDs.length > 0 &&
                transitionDs.length <= maxStepTransitions &&
                maxTransitionAbs >= minStepRise &&
                smallDiffAbsSum <= residualLimit;
            const smoothRampLike =
                !hasStepDiscontinuity &&
                validAdjacentPairs > 0 &&
                transitionDs.length === 0 &&
                this.aheadProbeSpread > this._stairSpreadThreshold &&
                diffSignChanges <= 1;

            let smallStairAscentEarlyInfo = null;
            const earlyLookAhead = this.smallStairAscentEarlyLookAhead ?? this.lookAhead;
            if (flatLen > 1e-3 && earlyLookAhead > this.lookAhead + 0.05) {
                const earlyN = Math.max(4, this.smallStairAscentEarlyProbeCount ?? 36);
                const earlyYs = [];
                for (let i = 1; i <= earlyN; i++) {
                    const d = (earlyLookAhead * i) / earlyN;
                    const y = this._groundVector(
                        cur.x + fwdX * d, probeY, cur.z + fwdZ * d,
                    );
                    earlyYs.push({ d, y });
                }

                const positiveDs = [];
                const negativeDs = [];
                let earlyMaxTransitionAbs = 0;
                let earlyResidual = 0;
                for (let i = 1; i < earlyYs.length; i++) {
                    const a = earlyYs[i - 1].y, b = earlyYs[i].y;
                    if (a === null || b === null) continue;
                    const dy = b - a;
                    const absDy = Math.abs(dy);
                    if (absDy > discontinuityThreshold) {
                        const dInterp = earlyYs[i - 1].d + 0.5 * (earlyYs[i].d - earlyYs[i - 1].d);
                        if (dy > 0) positiveDs.push(dInterp);
                        else negativeDs.push(dInterp);
                        earlyMaxTransitionAbs = Math.max(earlyMaxTransitionAbs, absDy);
                    } else {
                        earlyResidual += absDy;
                    }
                }

                let earlyRun = null;
                if (positiveDs.length >= 2) {
                    let sum = 0;
                    for (let k = 1; k < positiveDs.length; k++) sum += positiveDs[k] - positiveDs[k - 1];
                    earlyRun = sum / (positiveDs.length - 1);
                }

                const earlyLooksLikeSmallStairs =
                    positiveDs.length >= (this.smallStairAscentEarlyMinPositiveEdges ?? 2) &&
                    negativeDs.length <= (this.smallStairAscentEarlyMaxNegativeEdges ?? 0) &&
                    earlyMaxTransitionAbs >= minStepRise &&
                    earlyMaxTransitionAbs < 0.13 &&
                    earlyResidual <= (this._stairResidualLimit ?? 0.045) * 1.5;
                if (earlyLooksLikeSmallStairs) {
                    this._smallStairAscentEarlyFrames = this.smallStairAscentEarlyHoldFrames ?? 12;
                } else {
                    this._smallStairAscentEarlyFrames = Math.max(0, (this._smallStairAscentEarlyFrames ?? 0) - 1);
                }
                this.smallStairAscentEarlyUp = (this._smallStairAscentEarlyFrames ?? 0) > 0;
                smallStairAscentEarlyInfo = {
                    active: this.smallStairAscentEarlyUp,
                    detected: earlyLooksLikeSmallStairs,
                    holdFrames: this._smallStairAscentEarlyFrames ?? 0,
                    positiveEdges: positiveDs.length,
                    negativeEdges: negativeDs.length,
                    firstPositiveD: positiveDs.length ? positiveDs[0] : null,
                    run: earlyRun,
                    maxTransitionAbs: earlyMaxTransitionAbs,
                    residual: earlyResidual,
                    lookAhead: earlyLookAhead,
                };
            } else {
                this._smallStairAscentEarlyFrames = Math.max(0, (this._smallStairAscentEarlyFrames ?? 0) - 1);
                this.smallStairAscentEarlyUp = (this._smallStairAscentEarlyFrames ?? 0) > 0;
                smallStairAscentEarlyInfo = {
                    active: this.smallStairAscentEarlyUp,
                    detected: false,
                    holdFrames: this._smallStairAscentEarlyFrames ?? 0,
                };
            }
            this.smallStairAscentEarlyInfo = smallStairAscentEarlyInfo;

            this.aheadStepLike = hasStepDiscontinuity;
            this.aheadSmoothRampLike = smoothRampLike;
            this.aheadTransitionCount = transitionDs.length;
            this.aheadProbeResidual = smallDiffAbsSum;
            this.aheadStepRiseRaw = hasStepDiscontinuity ? maxTransitionAbs : 0;
            const positiveStepEdge = transitionDys.some(dy => dy > discontinuityThreshold);
            const negativeStepEdge = transitionDys.some(dy => dy < -discontinuityThreshold);
            if (positiveStepEdge) {
                this._recentPositiveStepFrames = this._isolatedObstacleSignHoldFrames;
            } else {
                this._recentPositiveStepFrames = Math.max(0, (this._recentPositiveStepFrames ?? 0) - 1);
            }
            if (negativeStepEdge) {
                this._recentNegativeStepFrames = this._isolatedObstacleSignHoldFrames;
            } else {
                this._recentNegativeStepFrames = Math.max(0, (this._recentNegativeStepFrames ?? 0) - 1);
            }
            const hasOpposedStepEdges =
                (this._recentPositiveStepFrames ?? 0) > 0 &&
                (this._recentNegativeStepFrames ?? 0) > 0;
            const isolatedObstacleNow =
                hasStepDiscontinuity &&
                hasOpposedStepEdges &&
                maxTransitionAbs <= (this.obstacleWalkMaxRise ?? 0.18) &&
                this.aheadProbeSpread <= (this.obstacleWalkMaxSpread ?? 0.18);
            if (isolatedObstacleNow) {
                this._isolatedObstacleFrames = this._isolatedObstacleContextHoldFrames;
            } else {
                this._isolatedObstacleFrames = Math.max(0, (this._isolatedObstacleFrames ?? 0) - 1);
            }
            // Hold briefly across the flat top between an obstacle's up edge
            // and down edge. This is generic terrain state: an isolated step
            // can have one or two probe frames where no edge is visible while
            // the foot is still clearing it.
            this.aheadIsolatedObstacle = (this._isolatedObstacleFrames ?? 0) > 0;

            if (hasStepDiscontinuity && maxTransitionAbs > 0) {
                this.aheadStairRise = maxTransitionAbs;
                this.aheadStairShape =
                    maxTransitionAbs < 0.13 ? 'small' :
                    maxTransitionAbs < 0.20 ? 'normal' : 'large';
                this._latchedStairRise = this.aheadStairRise;
                this._latchedStairShape = this.aheadStairShape;
                this._stairShapeMissFrames = 0;
            } else if (this._latchedStairShape &&
                       (this._stairShapeMissFrames ?? 999) < (this._stairShapeMemoryFrames ?? 20)) {
                this._stairShapeMissFrames = (this._stairShapeMissFrames ?? 0) + 1;
                this.aheadStairRise = this._latchedStairRise;
                this.aheadStairShape = this._latchedStairShape;
            } else {
                this._stairShapeMissFrames = (this._stairShapeMissFrames ?? 0) + 1;
                this.aheadStairRise = 0;
                this.aheadStairShape = null;
            }

            if (hasStepDiscontinuity && transitionDs.length >= 2) {
                // Mean distance between consecutive transitions = tread run.
                let sum = 0;
                for (let k = 1; k < transitionDs.length; k++) {
                    sum += transitionDs[k] - transitionDs[k - 1];
                }
                this.aheadTreadRun = sum / (transitionDs.length - 1);
                this._lastTreadRun = this.aheadTreadRun;
                this._lastTreadRunAge = 0;
                this._noStepEvidenceFrames = 0;
            } else if (hasStepDiscontinuity && transitionDs.length === 1) {
                const fallbackRun =
                    this.aheadStairShape === 'small'  ? 0.30 :
                    this.aheadStairShape === 'normal' ? 0.28 :
                    this.aheadStairShape === 'large'  ? 0.26 : null;
                if (this._lastTreadRun &&
                    (this._lastTreadRunAge ?? 999) <= (this._treadRunMemoryFrames ?? 75)) {
                    // Only one stair edge is visible in the probe window.
                    // Reuse recent stair run only if current probes still
                    // look like a step.
                    this.aheadTreadRun = this._lastTreadRun;
                    this._lastTreadRunAge = 0;
                } else if (fallbackRun !== null) {
                    // First visible edge of a staircase: seed cadence from
                    // the detected rise shape so small stairs engage on the
                    // first tread instead of waiting for two edges.
                    this.aheadTreadRun = fallbackRun;
                    this._lastTreadRun = fallbackRun;
                    this._lastTreadRunAge = 0;
                } else {
                    this.aheadTreadRun = null;
                }
                this._noStepEvidenceFrames = 0;
            } else {
                this.aheadTreadRun = null;
                this._lastTreadRunAge = (this._lastTreadRunAge ?? 999) + 1;
                this._noStepEvidenceFrames = hasStepDiscontinuity
                    ? 0
                    : (this._noStepEvidenceFrames ?? 0) + 1;
                if (this._noStepEvidenceFrames > (this._treadRunMemoryFrames ?? 75)) {
                    this._lastTreadRun = null;
                }
            }
            // Hold raw min/max here; compute deltas vs feet-Y after
            // currentFeetY is declared below.
            this._aheadMinRaw = aheadMin < Infinity ? aheadMin : null;
            this._aheadMaxRaw = aheadMax > -Infinity ? aheadMax : null;

            // Body Y target = LOWER of (leftHit, rightHit). Both null → airborne.
            const currentFeetY = cur.y - this.halfHeight - this.hipY;
            // Now compute the descent/ascent deltas relative to feet Y.
            this.aheadLowestDelta = this._aheadMinRaw !== null
                ? (this._aheadMinRaw - currentFeetY)
                : 0;
            this.aheadHighestDelta = this._aheadMaxRaw !== null
                ? (this._aheadMaxRaw - currentFeetY)
                : 0;
            let targetGroundY = null;
            let grounded = false;
            let climbBlocked = false;

            // Body Y follows the LOWER foot (load-bearing leg). On stairs
            // the higher foot's leg bends UP via IK (high-knee step pose)
            // which the leg can handle comfortably (hip-to-foot distance
            // ~0.6m vs leg length ~0.85m). The opposite — body following
            // the higher foot — strands the lower leg STRETCHED DOWN past
            // its max length, producing the "weird leg throw" at flat-
            // to-stairs transitions. Knee-bend-up is forgiving, leg-
            // stretch-down is not.
            let perFootGroundY = null;
            if (leftHit !== null && rightHit !== null) {
                perFootGroundY = Math.min(leftHit, rightHit);
            } else if (leftHit !== null) {
                perFootGroundY = leftHit;
            } else if (rightHit !== null) {
                perFootGroundY = rightHit;
            }

            // Grounded hysteresis. The 1cm body ground
            // sphere can briefly hit a riser side or ramp seam, then reject
            // the hit by normal, yielding a one-frame null even though forward
            // probes still see continuous walkable support. Treat that as a
            // contact seam for a few frames instead of dropping into gravity.
            const isLargeDescent = (this.aheadLowestDelta ?? 0) < -0.18;
            const supportSeamLikely =
                hasStepDiscontinuity ||
                smoothRampLike ||
                (this.aheadProbeSpread ?? 0) > (this._stairSpreadThreshold ?? 0.10) ||
                this.aheadStairShape !== null;
            let ikGroundGraceInfo = null;
            if (perFootGroundY === null && supportSeamLikely && this._lastValidGroundY !== undefined) {
                this._groundStaleFrames = (this._groundStaleFrames ?? 0) + 1;
                const maxStale = isLargeDescent ? 3 : 2;
                if (this._groundStaleFrames <= maxStale) {
                    perFootGroundY = this._lastValidGroundY;
                }
            }
            if (perFootGroundY === null && this.useIKGroundingGrace && Array.isArray(this._priorIKSupportContacts)) {
                const eligible = this._priorIKSupportContacts
                    .filter(c =>
                        c?.valid &&
                        Number.isFinite(c.hitY) &&
                        Number.isFinite(c.soleGapY) &&
                        Math.abs(c.soleGapY) <= (this.ikGroundingGraceMaxSoleGap ?? 0.56) &&
                        (currentFeetY - c.hitY) <= (this.ikGroundingGraceMaxDrop ?? 0.34) &&
                        (c.hitY - currentFeetY) <= (this.ikGroundingGraceMaxRise ?? 0.08))
                    .map(c => c.hitY);
                if (eligible.length > 0) {
                    perFootGroundY = Math.min(...eligible);
                    ikGroundGraceInfo = {
                        y: perFootGroundY,
                        contacts: eligible.length,
                        currentFeetY,
                    };
                }
            }
            if (perFootGroundY !== null) {
                this._lastValidGroundY = perFootGroundY;
                this._groundStaleFrames = 0;
            }

            // "Grounded" requires the detected ground be within fallThreshold
            // of the current feet position. If ground is way below (cliff /
            // stair top), we're airborne — gravity drives Y, IK suppresses
            // (legik gates on isGrounded), and the test scene blends the
            // fall animation. Re-grounds when feet drop close enough.
            if (perFootGroundY !== null &&
                (currentFeetY - perFootGroundY) <= this.fallThreshold) {
                grounded = true;
            }

            // Climb-angle gate + small forward bias for body Y when climbable.
            // Bias gives body anticipation so legs approach next stair from
            // above instead of horizontal-into-riser.
            let climbAngleDeg = 0;
            targetGroundY = perFootGroundY;
            let contactSupportLift = 0;
            let contactSupportInfo = null;

            // Foot IK support is an observation, not a same-loop root
            // authority. The foot IK exposes a useful directional foot hit, but
            // kinematic-character body movement should own root support. If an
            // experiment explicitly enables foot-to-root support, only accept a
            // candidate after it has been stable and close to the body support.
            const footObs = this._footSupportObservation;
            const footCandidateY = Number.isFinite(footObs?.y) ? footObs.y : null;
            const footCandidateDelta = footCandidateY !== null && perFootGroundY !== null
                ? footCandidateY - perFootGroundY
                : null;
            const footCandidateStable =
                !!footObs?.stable &&
                footCandidateY !== null &&
                footCandidateDelta !== null &&
                Math.abs(footCandidateDelta) <= (this._footSupportRootMaxDelta ?? 0.08);
            let usedFootSupportForRoot = false;
            if (this._useFootSupportForRoot && grounded && footCandidateStable) {
                targetGroundY = footCandidateY;
                usedFootSupportForRoot = true;
            }
            if (this.useContactSupportLift &&
                grounded &&
                leftHit !== null &&
                rightHit !== null &&
                perFootGroundY !== null &&
                !hasStepDiscontinuity) {
                const highY = Math.max(leftHit, rightHit);
                const lowY = Math.min(leftHit, rightHit);
                const footDelta = highY - lowY;
                const highSide = leftHit >= rightHit ? 'left' : 'right';
                const priorSwing = this._priorFootContactState?.[highSide]?.inSwing ?? false;
                const localRampAngle = Math.atan2(footDelta, Math.max(0.001, this.footStanceX * 2)) * 180 / Math.PI;
                const lowObstacleLike =
                    footDelta >= (this.contactSupportLiftMin ?? 0.025) &&
                    footDelta <= (this.contactSupportLiftMax ?? 0.18) &&
                    (!smoothRampLike || localRampAngle <= (this.contactSupportMaxRampAngle ?? 12));
                if (lowObstacleLike) {
                    const ratio = priorSwing
                        ? (this.contactSupportSwingRatio ?? 0.30)
                        : (this.contactSupportLiftRatio ?? 0.55);
                    contactSupportLift = footDelta * Math.max(0, Math.min(1, ratio));
                    targetGroundY = Math.max(targetGroundY, lowY + contactSupportLift);
                    contactSupportInfo = {
                        enabled: true,
                        highSide,
                        highY,
                        lowY,
                        footDelta,
                        lift: contactSupportLift,
                        ratio,
                        highSideInSwing: priorSwing,
                        localRampAngle,
                    };
                }
            }
            let ikContactSupportInfo = null;
            if (this.useIKContactSupportLift &&
                grounded &&
                perFootGroundY !== null &&
                !hasStepDiscontinuity &&
                Array.isArray(this._priorIKSupportContacts)) {
                for (const c of this._priorIKSupportContacts) {
                    if (!c?.valid) continue;
                    const deltaY = c.hitY - perFootGroundY;
                    if (deltaY < (this.contactSupportLiftMin ?? 0.025) ||
                        deltaY > (this.contactSupportLiftMax ?? 0.18)) continue;
                    if (Math.abs(c.soleGapY ?? 999) > (this.ikContactSoleGapMax ?? 0.16)) continue;
                    const ratio = c.inSwing
                        ? (this.ikContactSupportSwingRatio ?? 0.18)
                        : (this.ikContactSupportLiftRatio ?? 0.42);
                    const lift = deltaY * Math.max(0, Math.min(1, ratio));
                    const candidateY = perFootGroundY + lift;
                    if (candidateY > targetGroundY) {
                        targetGroundY = candidateY;
                        ikContactSupportInfo = {
                            enabled: true,
                            side: c.side,
                            hitY: c.hitY,
                            deltaY,
                            lift,
                            ratio,
                            inSwing: c.inSwing,
                            soleGapY: c.soleGapY,
                        };
                    }
                }
            }
            if (grounded && aheadHit !== null && aheadHit > perFootGroundY + 0.01) {
                // ASCENT — bias body Y up so legs approach next stair from
                // above instead of clipping horizontally into the riser.
                const dy = aheadHit - currentFeetY;
                climbAngleDeg = Math.atan2(Math.max(0, dy), this.lookAhead) * 180 / Math.PI;
                if (climbAngleDeg > this.maxClimbAngle) {
                    climbBlocked = true;
                } else {
                    // Ramp the bias by climb angle so the transition from
                    // flat→ascent doesn't pop the body Y target up by 9cm
                    // in a single frame (causing the "kicking" entry).
                    // Below ~5° (gentle slope): no bias.
                    // Above ~25° (full stair): full bias.
                    const angleRamp = Math.max(0, Math.min(1, (climbAngleDeg - 5) / 20));
                    const bias = this.forwardBias * angleRamp;
                    targetGroundY = perFootGroundY * (1 - bias) + aheadHit * bias;
                }
            } else if (grounded && aheadHit !== null && aheadHit < perFootGroundY - 0.01) {
                // DESCENT — sign-flipped angle; used for slowdown only. Body Y
                // tracking already follows externalGroundY (the forward foot's
                // raycast hit) so no body-Y bias is added here.
                const dy = perFootGroundY - aheadHit;
                climbAngleDeg = Math.atan2(Math.max(0, dy), this.lookAhead) * 180 / Math.PI;
            }

            // Stair speed slowdown — linear interp from 1.0 at the engage
            // threshold to a moderate floor at full stair angle. Floor of
            // 0.7 = 30% slowdown — between the too-fast cos() (~15%) and
            // the too-slow minStairSpeedScale=0.37 (~63%). Applied on
            // BOTH ascent and descent.
            let targetScale = 1.0;
            const engageDeg = 5;
            const fullDeg   = 30;
            const floor     = 0.55;
            if (climbAngleDeg > engageDeg && climbAngleDeg <= 45 && !climbBlocked) {
                const t = Math.min(1, (climbAngleDeg - engageDeg) / (fullDeg - engageDeg));
                targetScale = 1.0 * (1 - t) + floor * t;
            }
            if (this._smoothSpeedScale === undefined) this._smoothSpeedScale = 1.0;
            // λ=10 → ~100ms time constant. Absorbs the flat→stair angle pop.
            const lpK = Math.min(1, dt * 10);
            this._smoothSpeedScale = this._smoothSpeedScale * (1 - lpK) + targetScale * lpK;
            const speedScale = this._smoothSpeedScale;
            this.climbAngleDeg = climbAngleDeg;
            // Signed climb angle: + ascending, − descending, 0 flat. Used
            // by the head-pitch system in the test scene to look up/down
            // along the actual motion path (independent of which anim clip
            // is playing).
            const isDescent = grounded && aheadHit !== null && aheadHit < perFootGroundY - 0.01;
            this.signedClimbAngleDeg = climbBlocked ? 0
                : (isDescent ? -climbAngleDeg : climbAngleDeg);
            this.speedScale = speedScale;

            this.grounded = grounded;
            this.groundY = grounded ? targetGroundY : -Infinity;
            this._climbBlocked = climbBlocked;
            const supportMode = !grounded ? 'airborne'
                : hasStepDiscontinuity ? (isDescent ? 'stairDown' : 'stairUp')
                : smoothRampLike ? (isDescent ? 'rampDown' : 'rampUp')
                : 'flat';
            this.supportFrame = {
                dt,
                input: { x: inX, z: inZ, fwdX, fwdZ, flatLen, originX: cur.x, originY: cur.y, originZ: cur.z },
                body: {
                    currentFeetY,
                    perFootGroundY,
                    targetGroundY,
                    usedFootSupportForRoot,
                    contactSupport: contactSupportInfo,
                    ikContactSupport: ikContactSupportInfo,
                    ikGroundGrace: ikGroundGraceInfo,
                    supportMode,
                    climbBlocked,
                },
                probes: {
                    leftY: leftHit,
                    rightY: rightHit,
                    aheadY: aheadHit,
                    rawYs: probeYs.map(p => ({ d: p.d, y: p.y })),
                    aheadMin: this._aheadMinRaw,
                    aheadMax: this._aheadMaxRaw,
                    spread: this.aheadProbeSpread,
                    transitionDs: transitionDs.slice(),
                    transitionDys: transitionDys.slice(),
                    residual: smallDiffAbsSum,
                    stepLike: hasStepDiscontinuity,
                    isolatedObstacle: this.aheadIsolatedObstacle,
                    smoothRampLike,
                    smallStairAscentEarly: this.smallStairAscentEarlyInfo,
                },
                terrain: {
                    mode: supportMode,
                    shape: this.aheadStairShape,
                    rise: this.aheadStairRise ?? 0,
                    run: this.aheadTreadRun ?? null,
                    signedAngle: this.signedClimbAngleDeg,
                    highestDelta: this.aheadHighestDelta,
                    lowestDelta: this.aheadLowestDelta,
                    isolatedObstacle: this.aheadIsolatedObstacle,
                    smallStairAscentEarly: this.smallStairAscentEarlyInfo,
                },
                footObservation: footObs ? {
                    y: footCandidateY,
                    deltaFromBodySupport: footCandidateDelta,
                    stable: !!footObs.stable,
                    stableFrames: footObs.stableFrames ?? 0,
                    source: footObs.source ?? null,
                } : null,
            };

            // ─── Y TARGET WITH AVERAGING WINDOW ───────────────────────────
            // MSCC averages the last N frames' Y forces to kill stuttering as
            // the forward probe crosses tread edges. We average the target Y
            // directly (equivalent for kinematic motion).
            let smoothedY;
            if (grounded) {
                const wantedBodyY = targetGroundY + this.hipY + this.halfHeight;
                this._yAvgWindow.push(wantedBodyY);
                if (this._yAvgWindow.length > this._yAvgSize) {
                    this._yAvgWindow.shift();
                }
                const avgY = this._yAvgWindow.reduce((a, b) => a + b, 0) / this._yAvgWindow.length;
                this._bodyYTarget = avgY;
                this._velocityY = 0;
                // Rate-cap on RISE only (kept from session for ascent
                // behavior we agreed not to touch). On DESCENT use the
                // original 60Hz exponential damp so body Y tracks target
                // smoothly through tread crossings without rate-cap
                // discretization (which manifested as bouncing-off-edges).
                const isDescent = this._bodyYTarget < cur.y;
                // GPT variant: cap both directions. The exponential descent
                // path could snap the root toward a lower lead-foot hit in a
                // single frame, producing deep crouches and foot sliding on
                // ramp/stair descents.
                const wantsUpDuringDescent =
                    (supportMode === 'stairDown' || supportMode === 'rampDown') &&
                    this._bodyYTarget > cur.y;
                const raisedSupportLift = targetGroundY - currentFeetY;
                const raisedSupportCandidate =
                    this.allowRaisedSupportDuringDescent &&
                    wantsUpDuringDescent &&
                    raisedSupportLift >= (this.raisedSupportMinLift ?? 0.045) &&
                    this.aheadHighestDelta >= (this.raisedSupportAheadMin ?? 0.035) &&
                    this.aheadProbeSpread <= (this.raisedSupportMaxSpread ?? 0.18);
                if (raisedSupportCandidate) {
                    this._raisedSupportDescentLatch = Math.max(
                        this._raisedSupportDescentLatch ?? 0,
                        this.raisedSupportLatchFrames ?? 3,
                    );
                }
                const raisedSupportDuringDescent =
                    this.allowRaisedSupportDuringDescent &&
                    wantsUpDuringDescent &&
                    raisedSupportLift >= (this.raisedSupportFinishGap ?? 0.015) &&
                    (raisedSupportCandidate || (this._raisedSupportDescentLatch ?? 0) > 0);
                const blockUpwardDescentSnap = wantsUpDuringDescent && !raisedSupportDuringDescent;
                const rate = isDescent ? this.bodyYRateDown : this.bodyYRateUp;
                const maxStep = rate * dt;
                let delta = this._bodyYTarget - cur.y;
                // Godot/PhysX-style direction-aware snap: while descending,
                // allow downward adhesion but block sudden upward root
                // correction unless ascent is explicitly classified. Pelvis/IK
                // can absorb small leg reach; the root should not pop upward at
                // descent seams.
                if (blockUpwardDescentSnap) delta = 0;
                const clamped = Math.sign(delta) * Math.min(Math.abs(delta), maxStep);
                smoothedY = cur.y + clamped;
                if ((this._raisedSupportDescentLatch ?? 0) > 0) {
                    this._raisedSupportDescentLatch = raisedSupportDuringDescent
                        ? Math.max(0, this._raisedSupportDescentLatch - 1)
                        : 0;
                }
                if (this.supportFrame) {
                this.supportFrame.body.bodyYTarget = this._bodyYTarget;
                this.supportFrame.body.blockedUpwardDescentSnap = blockUpwardDescentSnap;
                this.supportFrame.body.raisedSupportDuringDescent = raisedSupportDuringDescent ? {
                    lift: raisedSupportLift,
                    aheadHighestDelta: this.aheadHighestDelta,
                    latchFrames: this._raisedSupportDescentLatch,
                } : null;
                this.supportFrame.body.smoothedY = smoothedY;
                if (contactSupportInfo) {
                    this.supportFrame.body.contactSupport.bodyYTargetLift = contactSupportLift;
                }
                }
            } else {
                // Airborne (cliff edge or climb-blocked) — pure gravity, no smoothing
                this._velocityY = Math.max(
                    this._velocityY + this.gravity * dt,
                    -this.maxFallSpeed,
                );
                smoothedY = cur.y + this._velocityY * dt;
                // Clear the smoothing average so a future ground re-grounds cleanly
                this._yAvgWindow.length = 0;
                this._bodyYTarget = smoothedY;
            }

            // ─── X/Z VIA RAPIER FOR WALL COLLISION ─────────────────────────
            // Body Y comes from MSCC pattern; Rapier handles ONLY horizontal
            // move-and-slide against walls. We pass Y=0 to the controller so
            // its autostep + snap-to-ground don't fight our smooth-damp Y.
            // X/Z input is scaled by the climb-speed multiplier so stairs
            // actually slow her down (cos(climbAngle) at runtime).
            const desired = {
                x: inX * dt * speedScale,
                y: 0,
                z: inZ * dt * speedScale,
            };
            this.controller.computeColliderMovement(this.collider, desired);
            const corrected = this.controller.computedMovement();
            // BLOCKED detection (physics-level, drive-agnostic): if we ASKED to
            // move horizontally but Rapier's move-and-slide cancelled most of it,
            // a solid is in the way. Count consecutive blocked frames so the gait
            // can settle to idle instead of moon-walking in place against the wall
            // (the walk anim otherwise keeps striding because the body jitters
            // against the collider and speedActual spikes above the move threshold).
            {
                const desLen = Math.hypot(desired.x, desired.z);
                const corLen = Math.hypot(corrected.x, corrected.z);
                if (desLen > 1e-4 && corLen < 0.4 * desLen) this._blockedFrames = (this._blockedFrames || 0) + 1;
                else if (corLen > 0.05) this._blockedFrames = 0;   // actually moved → clear
                // else (no real input / no real motion): HOLD the count, so a
                // caller that responds to the block by feeding zero input (idle)
                // doesn't immediately un-latch it and oscillate.
            }
            this.body.setNextKinematicTranslation({
                x: cur.x + corrected.x,
                y: smoothedY,           // direct from MSCC smooth-damp
                z: cur.z + corrected.z,
            });
            this.world.step();

            const t2 = this.body.translation();

            // World speed (XZ-plane) actually achieved this frame
            const dxA = t2.x - this._lastX;
            const dzA = t2.z - this._lastZ;
            this.speedActual = Math.sqrt(dxA*dxA + dzA*dzA) / dt;
            this._lastX = t2.x;
            this._lastZ = t2.z;

            // Feet world position for caller to place vrm.scene
            this._feetWorld.set(
                t2.x,
                t2.y - this.halfHeight - this.hipY - this.vrmFootY,
                t2.z,
            );
        }

        // ─── HELPER: GroundVector — shape-cast a small ball downward.
        // Returns the world-space Y of the actual contact point on the
        // hit collider's surface (the true contact point, matching what
        // the foot IK samples). Handles
        // collision-geometry seams (ball can't fit through sub-radius
        // gaps) AND stays aligned to actual tread surfaces on stairs
        // (witness2 = exact contact point, NOT ball-bottom which would be
        // below the true surface at edge hits).
        //
        // Rapier's normal2 convention: points INTO the second shape (the
        // collider), opposite to the doc's "outward" wording. We use
        // -normal2.y as outward Y.
        _groundVector(x, originY, z) {
            if (!this._groundShape) {
                // Small radius — bridges sub-cm geometry seams without
                // reaching across stair-tread edges and lifting body Y
                // ahead of the body's actual xz.
                this._groundShape = new this.RAPIER.Ball(0.01);
                this._groundRot = { x: 0, y: 0, z: 0, w: 1 };
                this._groundVel = { x: 0, y: -1, z: 0 };
                this._gTmpQuat = new THREE.Quaternion();
                this._gTmpVec  = new THREE.Vector3();
            }
            const hit = this.world.castShape(
                { x, y: originY, z },
                this._groundRot,
                this._groundVel,
                this._groundShape,
                0, 2000, true,
                undefined, undefined, this.collider,
            );
            if (!hit) return null;
            // Reject side hits — only upward-facing surfaces.
            if (hit.normal2 && -hit.normal2.y < 0.5) return null;
            // Rapier-compat 0.14 reports witness1 in WORLD coordinates
            // (the actual contact point on the surface, despite the doc
            // saying "local-space"). Use witness1.y directly — equivalent
            // to Unity Physics.SphereCast hit.point.y.
            return hit.witness1.y;
        }

        get bodyTranslation() { return this.body.translation(); }
        get feetWorldPosition() { return this._feetWorld; }

        // ──────────────────────────────────────────────────────────────
        // ANIMATION SETUP — controller owns its mixer and anim actions.
        // Test scenes hand it a VRM; controller loads all standard locomotion
        // clips from the VRMA_DEFAULTS_B64 library (walk, run, idle, stairs
        // variants, fall) and creates the actions. Clip tracks for hips
        // position and head/neck rotation are stripped so they don't fight
        // the controller's pose overrides (we drive hips lean + head pitch
        // procedurally from detected climb angle; hip XZ is driven by Rapier).
        // ──────────────────────────────────────────────────────────────
        async loadStandardAnimations(opts = {}) {
            const THREE = globalThis.THREE;
            const GLTFLoader              = globalThis.GLTFLoader;
            const VRMAnimationLoaderPlugin = globalThis.VRMAnimationLoaderPlugin;
            const createVRMAnimationClip   = globalThis.createVRMAnimationClip;
            const b64toArrayBuffer         = globalThis.b64toArrayBuffer;
            const VRMA_DEFAULTS_B64        = opts.vrmaLibrary ?? globalThis.VRMA_DEFAULTS_B64;
            if (!GLTFLoader || !VRMAnimationLoaderPlugin || !createVRMAnimationClip
                || !b64toArrayBuffer || !VRMA_DEFAULTS_B64) {
                throw new Error('[eidoverse-controller] loadStandardAnimations: required globals missing (GLTFLoader, VRMAnimationLoaderPlugin, createVRMAnimationClip, b64toArrayBuffer, VRMA_DEFAULTS_B64)');
            }

            const vrm = this.vrm;
            const mixer = new THREE.AnimationMixer(vrm.scene);
            this._mixer = mixer;

            // Maneuver clips whose authored hips ROTATION also gets stripped:
            // these moves are root-driven by the maneuver trajectory, and the
            // source clips carry root-motion yaw baked into the hips (a vault
            // that reads as a mid-air 360, a ladder climbed facing backwards).
            // The trajectory + heading own the body's orientation; the clip
            // contributes limbs/spine.
            const STRIP_HIPS_ROT = new Set(['vault', 'jump', 'climbLadder', 'climbLedge', 'climbWallUp']);

            // ROOT-MOTION EXTRACTION — before stripping, sample the clip's
            // hips.position curve (normalized-humanoid metres). For climb
            // maneuvers this curve IS the trajectory: driving the capsule
            // with the clip's own authored root motion puts the body exactly
            // where the animation expects it, so the limbs touch where they
            // look like they touch — no synthetic keypoints to misalign.
            const extractRootMotion = (clip, slot) => {
                const tr = clip.tracks.find(t => {
                    const n = t.name.toLowerCase();
                    return n.includes('hips') && n.endsWith('.position');
                });
                if (!tr || !tr.times?.length) return;
                const N = 48;
                const dur = clip.duration || 1;
                const x = new Float32Array(N + 1), y = new Float32Array(N + 1), z = new Float32Array(N + 1);
                let k = 0;
                for (let i = 0; i <= N; i++) {
                    const t = dur * i / N;
                    while (k < tr.times.length - 2 && tr.times[k + 1] <= t) k++;
                    const k2 = Math.min(k + 1, tr.times.length - 1);
                    const t0 = tr.times[k], t1 = tr.times[k2];
                    const f = t1 > t0 ? Math.min(1, Math.max(0, (t - t0) / (t1 - t0))) : 0;
                    x[i] = tr.values[k * 3]     + (tr.values[k2 * 3]     - tr.values[k * 3])     * f;
                    y[i] = tr.values[k * 3 + 1] + (tr.values[k2 * 3 + 1] - tr.values[k * 3 + 1]) * f;
                    z[i] = tr.values[k * 3 + 2] + (tr.values[k2 * 3 + 2] - tr.values[k * 3 + 2]) * f;
                }
                (this._clipRootMotion = this._clipRootMotion || {})[slot] = { x, y, z, N, dur };
            };

            // YAW-ONLY hips-rotation strip (swing-twist decomposition).
            // Maneuver clips carry the body LEAN in the hips rotation — the
            // vault's horizontal layout, the mantle's head-down fold over the
            // lip. Dropping the whole track (the old fix for baked root-yaw
            // spins) also killed that lean, leaving an upright body with
            // flailing limbs. Removing only the Y-twist keeps the authored
            // pitch/roll while the trajectory + heading own the yaw.
            const stripHipsYaw = (track) => {
                const v = track.values;
                const q = new THREE.Quaternion(), tw = new THREE.Quaternion();
                for (let i = 0; i + 3 < v.length; i += 4) {
                    q.set(v[i], v[i + 1], v[i + 2], v[i + 3]);
                    const n = Math.hypot(q.y, q.w);
                    if (n < 1e-8) continue;
                    tw.set(0, q.y / n, 0, q.w / n).invert();
                    q.multiply(tw).normalize();   // swing = q ⊗ twist⁻¹
                    v[i] = q.x; v[i + 1] = q.y; v[i + 2] = q.z; v[i + 3] = q.w;
                }
            };

            const stripTracks = (clip, slot) => {
                extractRootMotion(clip, slot);
                clip.tracks = clip.tracks.filter(t => {
                    const n = t.name.toLowerCase();
                    // Strip hips position track — controller's Rapier
                    // physics is the sole authority on body XYZ position.
                    if (n.includes('hips') && n.endsWith('.position')) return false;
                    if (STRIP_HIPS_ROT.has(slot) &&
                        n.includes('hips') && n.endsWith('.quaternion')) {
                        stripHipsYaw(t);
                        return true;
                    }
                    // Strip head + neck rotation tracks — controller's
                    // motion-driven head pitch (from detected climb angle)
                    // is the sole authority on head orientation.
                    if (n.endsWith('.quaternion') && (
                        n.includes('.head') || n.endsWith('.head') ||
                        n.includes('.neck') || n.endsWith('.neck')
                    )) return false;
                    return true;
                });
                return clip;
            };

            const loadSlot = async (slot) => {
                const b64 = VRMA_DEFAULTS_B64[slot];
                if (!b64) return null;
                const aLoader = new GLTFLoader();
                aLoader.register((p) => new VRMAnimationLoaderPlugin(p));
                const buf = b64toArrayBuffer(b64);
                const animGltf = await new Promise((res, rej) =>
                    aLoader.parse(buf, '', res, rej));
                const vrmAnim = animGltf?.userData?.vrmAnimations?.[0];
                if (!vrmAnim) return null;
                return stripTracks(createVRMAnimationClip(vrmAnim, vrm), slot);
            };

            // Locomotion slot list — the full movement vocabulary. Loop
            // clips run continuously at weight 0 until locomote() raises
            // them; ONE_SHOT clips (maneuvers + landing recovery) rewind
            // and play once when their maneuver triggers.
            const SLOTS = [
                'walk', 'run', 'idle',
                'stairsUp', 'stairsDown', 'stairsRunUp', 'stairsRunDown',
                'fallIdle',
                'jump', 'vault', 'climbLedge', 'climbWallUp', 'fallLand',
                'climbLadder',   // loops per rung — LOOP slot, ladder maneuver paces it
            ];
            const ONE_SHOT = new Set(['jump', 'vault', 'climbLedge', 'climbWallUp', 'fallLand']);
            const actions = {};
            for (const slot of SLOTS) {
                const clip = await loadSlot(slot);
                if (!clip) { actions[slot] = null; continue; }
                const loopMode = ONE_SHOT.has(slot) ? THREE.LoopOnce : THREE.LoopRepeat;
                const action = mixer.clipAction(clip).setLoop(loopMode);
                if (ONE_SHOT.has(slot)) action.clampWhenFinished = true;
                action.play();
                // walk starts with full weight (the default ground anim);
                // everything else weight 0 — locomote() takes over each frame.
                action.setEffectiveWeight(slot === 'walk' ? 1 : 0);
                actions[slot] = action;
            }
            this._actions = actions;
            return actions;
        }

        // Load a single non-locomotion EMOTE clip (talking, salute, cheer,
        // fist, raise, reach, or any VRMA emote in the global library).
        // Test/agent scenes load emotes ahead of time; play them with
        // playEmote() which AUTO-SUSPENDS LOCOMOTION (so the character
        // can't slide around while dancing). Emote tracks are NOT
        // stripped — emotes generally want their authored head motion
        // etc. to come through (unlike locomotion clips which we
        // override the head pitch on).
        async loadEmote(slot, opts = {}) {
            const THREE = globalThis.THREE;
            const GLTFLoader              = globalThis.GLTFLoader;
            const VRMAnimationLoaderPlugin = globalThis.VRMAnimationLoaderPlugin;
            const createVRMAnimationClip   = globalThis.createVRMAnimationClip;
            const b64toArrayBuffer         = globalThis.b64toArrayBuffer;
            const VRMA_DEFAULTS_B64        = opts.vrmaLibrary ?? globalThis.VRMA_DEFAULTS_B64;
            if (!this._mixer) throw new Error('[eidoverse-controller] loadEmote: call loadStandardAnimations() first');
            const b64 = VRMA_DEFAULTS_B64?.[slot];
            if (!b64) return null;
            const aLoader = new GLTFLoader();
            aLoader.register((p) => new VRMAnimationLoaderPlugin(p));
            const buf = b64toArrayBuffer(b64);
            const animGltf = await new Promise((res, rej) =>
                aLoader.parse(buf, '', res, rej));
            const vrmAnim = animGltf?.userData?.vrmAnimations?.[0];
            if (!vrmAnim) return null;
            const clip = createVRMAnimationClip(vrmAnim, this.vrm);
            const loopMode = opts.loop === false ? THREE.LoopOnce : THREE.LoopRepeat;
            const action = this._mixer.clipAction(clip).setLoop(loopMode);
            if (opts.loop === false) action.clampWhenFinished = true;
            action.play();
            action.setEffectiveWeight(0);
            // Store in a separate map so emotes don't collide with
            // locomotion slots in this._actions.
            if (!this._emoteActions) this._emoteActions = {};
            this._emoteActions[slot] = action;
            return action;
        }

        // ───── Emote playback API ─────────────────────────────────────
        // Emotes SUSPEND locomotion at the engine level: while any emote
        // has weight > emoteThreshold, locomote() forces input speed to
        // zero, fades all locomotion anims out, skips hip-lean / head-
        // pitch / foot-offset overrides, and still runs the mixer + IK
        // so the emote plays and feet stay planted on terrain. This
        // prevents agents from accidentally producing a character that
        // slides around while dancing.
        //
        // Agent usage:
        //   await charCtrl.loadEmote('salute', { loop: false });
        //   await charCtrl.playEmote('salute', { fadeIn: 0.3 });
        //   ...wait for completion or external trigger...
        //   await charCtrl.stopEmote({ fadeOut: 0.3 });
        playEmote(slot, opts = {}) {
            if (this._maneuver) {
                console.warn(`[eidoverse-controller] playEmote('${slot}') ignored — a ${this._maneuver.type} maneuver is in flight; wait for it to finish`);
                return null;
            }
            if (!this._emoteActions || !this._emoteActions[slot]) {
                console.warn(`[eidoverse-controller] playEmote: '${slot}' not loaded — call loadEmote('${slot}') first`);
                return null;
            }
            const fadeIn = opts.fadeIn ?? 0.2;
            // Stop any currently-active emote first (single-emote at a time).
            for (const [k, a] of Object.entries(this._emoteActions)) {
                if (k !== slot && a.enabled !== false &&
                    (a.getEffectiveWeight?.() ?? a.weight) > 0.01) {
                    a.fadeOut(opts.fadeOut ?? 0.2);
                }
            }
            const action = this._emoteActions[slot];
            // Reset clip to start if it's a one-shot, so the emote
            // plays cleanly from the beginning each invocation.
            // three.js fadeIn() ramps a MULTIPLIER on action.weight, and
            // reset() does NOT restore weight (it only clears time/fading) — so
            // loadEmote's dormant setEffectiveWeight(0) would leave weight=0 and
            // the fade would be 0 * ramp = 0 forever (emote never appears). Set
            // weight back to 1 explicitly, THEN fadeIn ramps the effective 0→1.
            action.reset();
            action.timeScale = 1;   // clear any prior reversal (endSeated reverse mode)
            action.setEffectiveWeight(1);
            action.play();
            action.fadeIn(fadeIn);
            this._activeEmote = slot;
            return action;
        }

        stopEmote(opts = {}) {
            const fadeOut = opts.fadeOut ?? 0.3;
            if (this._emoteActions) {
                for (const a of Object.values(this._emoteActions)) {
                    if (a && a.enabled !== false &&
                        (a.getEffectiveWeight?.() ?? a.weight) > 0.01) a.fadeOut(fadeOut);
                }
            }
            this._activeEmote = null;
        }

        // ── SEATED state ──────────────────────────────────────────────
        // Sitting is a sticky emote variant: the transition clip plays on
        // the controller's own mixer (easing from whatever was active),
        // `_seated` hands root placement to the caller (a seat helper's
        // raycast owns butt-on-seat), and locomotion stays suspended until
        // endSeated(). `_seated` is set synchronously BEFORE any await so
        // the very next frame already respects the caller's root.
        async beginSeated(slot = 'stand_to_sit', opts = {}) {
            this._seated = true;
            if (!this._emoteActions?.[slot]) await this.loadEmote(slot, { loop: false });
            const a = this.playEmote(slot, { fadeIn: opts.fadeIn ?? 0.25 });
            return a?.getClip?.()?.duration ?? null;
        }

        async endSeated(slot = 'sit_to_stand', opts = {}) {
            // Reverse mode: play the STILL-ACTIVE seated transition clip
            // backwards (stand_to_sit in reverse). Exactly the same poses in
            // the opposite order — no cross-clip hip-offset mismatch, which
            // is what slides the body forward off the seat while still in
            // the seated pose when crossfading to a separate stand-up clip.
            if (opts.reverse) {
                const activeSlot = this._activeEmote;
                const a = activeSlot && this._emoteActions?.[activeSlot];
                if (a) {
                    const clipDur = a.getClip().duration;
                    const speed = opts.reverseSpeed ?? 1;
                    a.paused = false;
                    a.enabled = true;
                    if (a.time <= 0 || a.time > clipDur) a.time = clipDur;
                    a.timeScale = -speed;
                    const remaining = a.time / speed;
                    this._seatedReleaseIn = Math.max(0.3, remaining * (opts.releaseAt ?? 0.92));
                    return remaining;
                }
            }
            let dur = null;
            if (slot) {
                if (!this._emoteActions?.[slot]) await this.loadEmote(slot, { loop: false });
                const a = this.playEmote(slot, { fadeIn: opts.fadeIn ?? 0.25 });
                dur = a?.getClip?.()?.duration ?? null;
                // Root authority returns only once the stand-up clip has
                // carried the hips back over the feet. Releasing _seated
                // immediately snaps the root from the seat to the pre-sit
                // stop point — the "pops forward out of the chair" bug.
                this._seatedReleaseIn = Math.max(0.3, (dur ?? 1.8) * (opts.releaseAt ?? 0.85));
            } else {
                this._seated = false;
            }
            return dur;
        }

        // ── UPPER-BODY GESTURES DURING LOCOMOTION ─────────────────────
        // A gesture is an emote clip MASKED to the upper body (spine /
        // chest / neck / head / shoulders / arms / hands — rotations
        // only) and blended OVER the active gait, so the character can
        // wave / cheer / talk with her hands while walking or running.
        // Legs, hips and the root stay fully owned by locomotion — which
        // is why this doesn't destabilize the walk the way additive
        // blending does (no reference-pose subtraction involved).
        // `weight` is a mixer blend weight: the upper body shows
        // weight/(1+weight) of the gesture (2.5 ≈ 70%, 4 ≈ 80%).
        async loadGesture(slot, opts = {}) {
            const THREE = globalThis.THREE;
            const GLTFLoader               = globalThis.GLTFLoader;
            const VRMAnimationLoaderPlugin = globalThis.VRMAnimationLoaderPlugin;
            const createVRMAnimationClip   = globalThis.createVRMAnimationClip;
            const b64toArrayBuffer         = globalThis.b64toArrayBuffer;
            const VRMA_DEFAULTS_B64        = opts.vrmaLibrary ?? globalThis.VRMA_DEFAULTS_B64;
            if (!this._mixer) throw new Error('[eidoverse-controller] loadGesture: call loadStandardAnimations() first');
            const b64 = VRMA_DEFAULTS_B64?.[slot];
            if (!b64) return null;
            const aLoader = new GLTFLoader();
            aLoader.register((p) => new VRMAnimationLoaderPlugin(p));
            const animGltf = await new Promise((res, rej) =>
                aLoader.parse(b64toArrayBuffer(b64), '', res, rej));
            const vrmAnim = animGltf?.userData?.vrmAnimations?.[0];
            if (!vrmAnim) return null;
            const clip = createVRMAnimationClip(vrmAnim, this.vrm);
            // Upper-body mask — resolve the rig's actual node names from the
            // humanoid map so the filter adapts to any VRM.
            const h = this.vrm.humanoid;
            const UPPER = ['spine', 'chest', 'upperChest', 'neck', 'head',
                'leftShoulder', 'leftUpperArm', 'leftLowerArm', 'leftHand',
                'rightShoulder', 'rightUpperArm', 'rightLowerArm', 'rightHand'];
            if (h?.humanBones) {
                for (const b of Object.keys(h.humanBones)) {
                    if (/(Thumb|Index|Middle|Ring|Little)/.test(b)) UPPER.push(b);
                }
            }
            const keep = new Set();
            for (const b of UPPER) {
                const n = h?.getNormalizedBoneNode?.(b);
                if (n?.name) keep.add(n.name);
            }
            clip.tracks = clip.tracks.filter(t =>
                t.name.endsWith('.quaternion') && keep.has(t.name.split('.')[0]));
            if (!clip.tracks.length) {
                console.warn(`[eidoverse-controller] loadGesture('${slot}'): no upper-body tracks survived the mask`);
                return null;
            }
            const loopMode = opts.loop === false ? THREE.LoopOnce : THREE.LoopRepeat;
            const action = this._mixer.clipAction(clip).setLoop(loopMode);
            if (opts.loop === false) action.clampWhenFinished = true;
            action.play();
            action.setEffectiveWeight(0);
            if (!this._gestureActions) this._gestureActions = {};
            this._gestureActions[slot] = action;
            return action;
        }

        playGesture(slot, opts = {}) {
            const a = this._gestureActions?.[slot];
            if (!a) {
                console.warn(`[eidoverse-controller] playGesture: '${slot}' not loaded — call loadGesture('${slot}') first`);
                return null;
            }
            a.reset();
            a.play();
            this._activeGesture = slot;
            this._gestureWeight = opts.weight ?? 2.5;
            return a;
        }

        stopGesture() {
            this._activeGesture = null;
        }

        // Per-frame gesture weight ramping (locomote + maneuvers call this).
        _updateGestureWeights(dt, forceOff = false) {
            if (!this._gestureActions) return;
            const THREE = globalThis.THREE;
            for (const [k, a] of Object.entries(this._gestureActions)) {
                if (!a) continue;
                const tgt = (!forceOff && this._activeGesture === k) ? (this._gestureWeight ?? 2.5) : 0;
                a.weight = THREE.MathUtils.damp(a.weight, tgt, 8, dt);
            }
        }

        // True while any emote action has non-trivial weight. Used by
        // locomote() to suspend locomotion every frame.
        // NOTE: read the EFFECTIVE weight, not `.weight` — three.js fadeOut()
        // drives an interpolant and disables the action on completion but
        // leaves the `.weight` property at its old value, so a `.weight`
        // check latches emoting=true forever after any stopEmote() (the
        // "stands still for the rest of the video after standing up" bug).
        get isEmoting() {
            const thresh = this.emoteSuspendThreshold ?? 0.05;
            if (!this._emoteActions) return false;
            for (const a of Object.values(this._emoteActions)) {
                if (a && a.enabled !== false &&
                    (a.getEffectiveWeight?.() ?? a.weight) > thresh) return true;
            }
            return false;
        }

        // ──────────────────────────────────────────────────────────────
        // LOCOMOTION LAYER (per-frame: physics + detection + anim + pose
        // + IK). This is the engine surface that test scenes / agents
        // call once per frame. All detection/triggering logic that used
        // to live in test_terrain_base.js renderFrame now lives here.
        // ──────────────────────────────────────────────────────────────
        attachLocomotion(opts = {}) {
            // Mixer + actions are owned by the controller (set up via
            // loadStandardAnimations). Accept overrides for back-compat
            // and for callers that want to inject custom anim sets.
            if (opts.mixer)   this._mixer = opts.mixer;
            if (opts.actions) this._actions = opts.actions;
            this._legIK = opts.legIK ?? null;

            // Locomotion params (defaults work for residential-stair-ish
            // VRMs; agents can override per-scene).
            this._flatSpeed              = opts.flatSpeed              ?? 1.5;
            this._stairCadence           = opts.stairCadence           ?? 2.5;
            this._nativeWalkSpeed        = opts.nativeWalkSpeed        ?? 1.5;
            this._ascendThreshold        = opts.ascendThreshold        ?? 0.4;
            this._descendThreshold       = opts.descendThreshold       ?? -0.4;
            this._stairLeavingLambda     = opts.stairLeavingLambda     ?? 18;
            this._stairEngageLambda      = opts.stairEngageLambda      ?? 12;
            this._tallRiserThreshold     = opts.tallRiserThreshold     ?? 0.20;
            this._tallRiserEngageLambda  = opts.tallRiserEngageLambda  ?? 16;
            this._stairUpAheadThreshold  = opts.stairUpAheadThreshold  ?? 0.055;
            this._stairDownAheadThreshold= opts.stairDownAheadThreshold?? -0.08;
            this._stairSpreadThreshold   = opts.stairSpreadThreshold   ?? 0.10;
            this._stairSpreadHistoryLen  = opts.stairSpreadHistoryLen  ?? 30;
            this._stairDiscontinuityThreshold = opts.stairDiscontinuityThreshold ?? 0.03;
            this._maxStairTransitionsInLookAhead = opts.maxStairTransitionsInLookAhead ?? 3;
            this._stairResidualLimit      = opts.stairResidualLimit      ?? 0.045;
            this._minStairRise            = opts.minStairRise            ?? 0.075;
            this._treadRunMemoryFrames    = opts.treadRunMemoryFrames    ?? 75;
            this._stairShapeMemoryFrames  = opts.stairShapeMemoryFrames  ?? 20;
            this._requireConfirmedStairClips = opts.requireConfirmedStairClips ?? false;
            this._confirmedStairHoldFrames = opts.confirmedStairHoldFrames ?? 12;
            this._confirmedStairFrames = 0;
            this._hipLeanAscent          = opts.hipLeanAscent          ?? 0.30;
            this._hipLeanDescent         = opts.hipLeanDescent         ?? 0.40;
            this._bodyYDropAscent        = opts.bodyYDropAscent        ?? 0.006;
            this._bodyYDropDescent       = opts.bodyYDropDescent       ?? 0.018;
            this._bodyYDropDescentCap    = opts.bodyYDropDescentCap    ?? 0.22;
            this._bodyYDropAscentCap     = opts.bodyYDropAscentCap     ?? 0.08;
            this._bodyYDropStairRamp     = opts.bodyYDropStairRamp     ?? 0.006;
            this._bodyYDropStairRampCap  = opts.bodyYDropStairRampCap  ?? 0.18;
            this._rampWalkAngleThreshold = opts.rampWalkAngleThreshold ?? 2.0;
            this._rampWalkMaxAngle       = opts.rampWalkMaxAngle       ?? 8.0;
            this._rampWalkMinProbeSpread = opts.rampWalkMinProbeSpread ?? 0.015;
            this._rampWalkMaxProbeSpread = opts.rampWalkMaxProbeSpread ?? 0.085;
            this._rampWalkSteepMaxProbeSpread = opts.rampWalkSteepMaxProbeSpread ?? 0.17;
            this._rampEdgeAngleThreshold = opts.rampEdgeAngleThreshold ?? 8.0;
            this._rampContextHoldFrames  = opts.rampContextHoldFrames  ?? 12;
            this._rampStairClearLambda   = opts.rampStairClearLambda   ?? 30;
            this._rampBodyYDropDescent   = opts.rampBodyYDropDescent   ?? 0.012;
            this._rampBodyYDropDescentCap= opts.rampBodyYDropDescentCap?? 0.12;
            this._rampFootClearanceOffset= opts.rampFootClearanceOffset?? 0.008;
            this._headPitchBonusMax      = opts.headPitchBonusMax      ?? 6;
            this._footOffsetAscent       = opts.footOffsetAscent       ?? 0.9;
            this._footOffsetDescent      = opts.footOffsetDescent      ?? 0.5;
            this._footOffsetLargeDescent = opts.footOffsetLargeDescent ?? 0.6;
            this._footOffsetAscentSmallScale = opts.footOffsetAscentSmallScale ?? 0.90;
            this._footOffsetDescentSmall  = opts.footOffsetDescentSmall  ?? 0.42;
            this._footOffsetDescentNormal = opts.footOffsetDescentNormal ?? 0.25;
            this._footOffsetDescentLarge  = opts.footOffsetDescentLarge  ?? 0.20;
            this._largeDescentClimbKnee  = opts.largeDescentClimbKnee  ?? 28;
            this._largeDescentClimbWidth = opts.largeDescentClimbWidth ?? 12;
            this._largeStairAscentSpeedScale = opts.largeStairAscentSpeedScale ?? 0.58;
            this._footOffsetSteepKnee    = opts.footOffsetSteepKnee    ?? 25;
            this._footOffsetSteepWidth   = opts.footOffsetSteepWidth   ?? 10;
            this._useFootSupportForRoot  = opts.useFootSupportForRoot  ?? false;
            this._footSupportRootStableFrames = opts.footSupportRootStableFrames ?? 4;
            this._footSupportRootMaxDelta = opts.footSupportRootMaxDelta ?? 0.08;
            this._largeStairFullToeReach = opts.largeStairFullToeReach ?? false;
            this._oppositeStairClearLambda = opts.oppositeStairClearLambda ?? 30;

            // RUN MODE — agent-facing flag. When `running` is true the
            // controller selects run / stairsRunUp / stairsRunDown anim
            // family instead of walk / stairsUp / stairsDown, and moves
            // the body at runSpeed instead of flatSpeed. Same per-shape
            // detection and pose adjustments apply (hip lean, head pitch,
            // body Y drop, foot offsets) — these were already gated on
            // walk-anim weight; we extend the gate to (walk OR run)
            // weight so they apply correctly in either mode.
            this.running         = opts.running         ?? false;
            this._runSpeed       = opts.runSpeed       ?? 3.6;   // m/s — typical jog
            this._nativeRunSpeed = opts.nativeRunSpeed ?? 3.6;   // run anim's authored speed
            this._stairCadenceRun = opts.stairCadenceRun ?? 1.4; // multiplier for stair-run anim cycle
            // Native walk speed (timeScale base) — separated from flat
            // movement speed for clarity. Existing flatSpeed/nativeWalkSpeed
            // remain for walk mode.

            // Smoothed state
            this._smoothFwdSpeed      = this._flatSpeed;
            this._smoothTreadRun      = 0.28;
            this._smoothHipsLeanDeg   = 0;
            this._smoothHeadPitchDeg  = 0;
            this._smoothBodyDrop      = 0;
            this._smoothClimbDegIK    = 0;
            this._lastBodyY           = null;
            this._spreadHistory       = [];
            this._stepEvidenceHistory = [];
            this._stairMotionHistory  = [];
            this._lastTreadRun        = null;
            this._lastTreadRunAge     = 999;
            this._noStepEvidenceFrames = 999;
            this._latchedStairRise    = 0;
            this._latchedStairShape   = null;
            this._stairShapeMissFrames = 999;
            this._headRestQuat        = null;
            this._smoothRampContextFrames = 0;
            this._smallStairPhaseLock = opts.smallStairPhaseLock ?? true;
            this._smallStairPhaseLockAscent = opts.smallStairPhaseLockAscent ?? false;
            this._smallStairPhaseLockDescent = opts.smallStairPhaseLockDescent ?? true;
            this._smallStairAscentPhaseOffset = opts.smallStairAscentPhaseOffset ?? 0.0;
            this._smallStairDescentPhaseOffset = opts.smallStairDescentPhaseOffset ?? 0.0;
            this._smallStairPhaseMinWeight = opts.smallStairPhaseMinWeight ?? 0.05;
            this._smallStairAscentSoleFit = opts.smallStairAscentSoleFit ?? true;
            this._smallStairAscentGuardRise = opts.smallStairAscentGuardRise ?? 0.035;
            this._smallStairAscentSingleRiseOffsetScale = opts.smallStairAscentSingleRiseOffsetScale ?? 0.58;
            this._smallStairAscentSingleRiseSoleFitScale = opts.smallStairAscentSingleRiseSoleFitScale ?? 0.36;
            this._smallStairAscentMultiRiseOffsetScale = opts.smallStairAscentMultiRiseOffsetScale ?? 0.60;
            this._smallStairAscentMultiRiseSoleFitScale = opts.smallStairAscentMultiRiseSoleFitScale ?? 0.46;
            this._smallStairAscentEarlyOffsetScale = opts.smallStairAscentEarlyOffsetScale ?? 0.42;
            this._smallStairAscentExitClearLambda = opts.smallStairAscentExitClearLambda ?? 48;
            this._smallStairAscentEdgeAlign = opts.smallStairAscentEdgeAlign ?? true;
            this._smallStairAscentEdgeHoldFrames = opts.smallStairAscentEdgeHoldFrames ?? 12;
            this._smallStairAscentEdgeMaxDistance = opts.smallStairAscentEdgeMaxDistance ?? 0.48;
            this._smallStairAscentEdgeAdvanceRunScale = opts.smallStairAscentEdgeAdvanceRunScale ?? 0.98;
            this._smallStairAscentEdgeLatch = null;
            this._smallStairAscentEdgeInfo = null;
            this._stairPhaseLockActive = false;
            this._stairPhaseLockDir = null;
            this._stairPhaseLockShape = null;
            this._stairPhaseDistance = 0;
            this._stairPhaseLockInfo = null;
        }

        _updateSmallStairAscentEdgeAlignHint(active) {
            const frame = this.supportFrame;
            const input = frame?.input ?? {};
            const probes = frame?.probes ?? {};
            const fwdX = Number.isFinite(input.fwdX) ? input.fwdX : 0;
            const fwdZ = Number.isFinite(input.fwdZ) ? input.fwdZ : 0;
            const fwdLen = Math.hypot(fwdX, fwdZ);
            const transitions = probes.transitionDs ?? [];
            const transitionDys = probes.transitionDys ?? [];
            const threshold = this._stairDiscontinuityThreshold ?? 0.03;
            const maxDistance = this._smallStairAscentEdgeMaxDistance ?? 0.48;
            const holdFrames = this._smallStairAscentEdgeHoldFrames ?? 12;
            const run = this.aheadTreadRun ?? this._lastTreadRun ?? this._smoothTreadRun ?? null;
            const body = this.bodyTranslation;
            const makeLatch = (d, dy, source) => {
                const ox = Number.isFinite(input.originX) ? input.originX : body.x;
                const oz = Number.isFinite(input.originZ) ? input.originZ : body.z;
                return {
                    point: { x: ox + fwdX * d, y: null, z: oz + fwdZ * d },
                    dir: { x: fwdX / fwdLen, z: fwdZ / fwdLen },
                    run: Number.isFinite(run) ? run : null,
                    age: 0,
                    distance: d,
                    dy,
                    source,
                };
            };

            let bestD = null;
            let bestDy = null;
            if (active && fwdLen > 0.5) {
                for (let i = 0; i < transitions.length; i++) {
                    const d = transitions[i];
                    const dy = transitionDys[i];
                    if (!Number.isFinite(d) || !Number.isFinite(dy)) continue;
                    if (dy <= threshold || d < 0 || d > maxDistance) continue;
                    if (bestD === null || d < bestD) {
                        bestD = d;
                        bestDy = dy;
                    }
                }
            }

            if (!active || fwdLen <= 0.5) {
                this._smallStairAscentEdgeLatch = null;
            } else if (!this._smallStairAscentEdgeLatch && bestD !== null) {
                this._smallStairAscentEdgeLatch = makeLatch(bestD, bestDy, 'probe-first');
            } else if (this._smallStairAscentEdgeLatch) {
                this._smallStairAscentEdgeLatch.age += 1;
                const latch = this._smallStairAscentEdgeLatch;
                const bodyProgress =
                    (body.x - latch.point.x) * latch.dir.x +
                    (body.z - latch.point.z) * latch.dir.z;
                const runNow = Number.isFinite(latch.run)
                    ? latch.run
                    : (Number.isFinite(run) ? run : null);
                const advanceProgress = Number.isFinite(runNow)
                    ? runNow * (this._smallStairAscentEdgeAdvanceRunScale ?? 0.78)
                    : Infinity;
                const expireProgress = Number.isFinite(runNow) ? runNow * 1.35 : Infinity;
                if (bestD !== null && bodyProgress >= advanceProgress) {
                    this._smallStairAscentEdgeLatch = makeLatch(bestD, bestDy, 'probe-advance');
                } else if (latch.age > holdFrames && bodyProgress > expireProgress) {
                    this._smallStairAscentEdgeLatch = null;
                }
            } else if (bestD !== null) {
                this._smallStairAscentEdgeLatch = makeLatch(bestD, bestDy, 'probe-reacquire');
            }

            const latch = this._smallStairAscentEdgeLatch;
            if (!latch) {
                this._smallStairAscentEdgeInfo = {
                    active: false,
                    reason: active ? 'no-positive-edge' : 'inactive',
                };
                return this._smallStairAscentEdgeInfo;
            }

            const bodyProgress =
                (body.x - latch.point.x) * latch.dir.x +
                (body.z - latch.point.z) * latch.dir.z;
            this._smallStairAscentEdgeInfo = {
                active: true,
                point: latch.point,
                dir: latch.dir,
                run: latch.run,
                age: latch.age,
                distance: latch.distance,
                dy: latch.dy,
                source: latch.source,
                bodyProgress,
            };
            return this._smallStairAscentEdgeInfo;
        }

        // Per-frame: physics + detection + anim weights + pose + IK.
        // input: { z: forward-dir-scalar, x: side-dir-scalar }.
        // The controller handles speed scaling internally — input is
        // direction-of-travel, not raw m/s.
        locomote(dt, input = { z: -1 }) {
            const THREE = globalThis.THREE;
            const vrm = this.vrm;
            const actions = this._actions || {};
            // Deferred seated-release (see endSeated) — ticks every frame
            // regardless of which path the frame takes.
            if (this._seatedReleaseIn != null) {
                this._seatedReleaseIn -= dt;
                if (this._seatedReleaseIn <= 0) {
                    this._seatedReleaseIn = null;
                    this._seated = false;
                }
            }
            const walkAction          = actions.walk;
            const runAction           = actions.run;
            const idleAction          = actions.idle;
            const stairsUpAction      = actions.stairsUp;
            const stairsDownAction    = actions.stairsDown;
            const stairsRunUpAction   = actions.stairsRunUp;
            const stairsRunDownAction = actions.stairsRunDown;
            const fallIdleAction      = actions.fallIdle;
            const ik = this._legIK;
            const mixer = this._mixer;

            // ── EMOTE SUSPEND ──────────────────────────────────────────
            // When an emote is active, locomotion is suspended at the
            // engine level. No sliding while dancing.
            //  - input.x/z are zeroed (no body translation)
            //  - all locomotion anim weights damp toward 0 (emote owns pose)
            //  - hip-lean / head-pitch / body-Y-drop / foot-offset are
            //    NOT applied (emote's authored motion is the truth)
            //  - mixer still updates (so emote plays)
            //  - physics still runs (so gravity keeps character planted)
            //  - IK still runs (so feet stay on terrain if it slopes)
            if (this.isEmoting) {
                const fadeLambda = 12;
                const fadeWeight = (a) => {
                    if (!a) return;
                    a.weight = THREE.MathUtils.damp(a.weight, 0, fadeLambda, dt);
                };
                // Fade all locomotion anims toward 0 — EXCEPT while the emote
                // itself is fading OUT (stopEmote called, nothing active):
                // then idle crossfades IN underneath it, so the pose blends
                // emote→idle instead of emote→rest-pose(T)→idle.
                for (const a of Object.values(actions)) {
                    if (a === idleAction && !this._activeEmote && !this._seated) {
                        a.weight = THREE.MathUtils.damp(a.weight, 1, 6, dt);
                        continue;
                    }
                    fadeWeight(a);
                }
                // A full-body emote owns the pose — gestures fade out too.
                this._updateGestureWeights(dt, true);
                // Zero input — character physically doesn't move.
                this.update(dt, { x: 0, z: 0 });
                // Advance mixer; pose comes from the emote.
                if (mixer) mixer.update(dt);
                // SEATED disengage: a seated emote (e.g. stand_to_sit) is NOT a
                // standing emote — its pose lifts the feet off the floor and the
                // hips translate down/back, and the body's world placement is owned
                // externally by seatOn's raycast (butt-on-seat). So when _seated,
                // do NOT snap the root to the feet or run grounding IK (both assume
                // a standing figure and would yank the seated pose to the floor).
                // The mixer still plays (so the clip crossfades + animates).
                if (!this._seated) {
                    if (vrm?.scene) {
                        vrm.scene.position.copy(this.feetWorldPosition);
                        // Standing emotes face a configurable direction (default
                        // Math.PI, the historic value). Set `_emoteFacingY` to aim a
                        // talk/salute/cheer at the camera without re-laying out the
                        // whole scene — the hardcoded PI forced every emote to face
                        // world −Z regardless of where the shot was.
                        // TURN-TO-FACE (not snap): when an emote engages straight off
                        // a walk, the character was facing its travel heading; snapping
                        // rotation.y to the emote facing in one frame reads as an
                        // instant spin. Instead damp toward the target along the
                        // shortest arc (~0.25s) so it pivots to face the camera as the
                        // emote crossfades in. Snap only once it's within ~1°.
                        {
                            // While an emote is ACTIVE it owns the facing.
                            // Once it's only fading out (stopEmote/stand-up),
                            // ease toward the locomotion heading instead —
                            // otherwise the fade pivots to the emote default
                            // and locomotion immediately turns back: a double
                            // turn on every stand-up.
                            const _tgt = this._activeEmote
                                ? ((this._emoteFacingY != null) ? this._emoteFacingY : Math.PI)
                                : this._heading;
                            let _d = _tgt - vrm.scene.rotation.y;
                            while (_d >  Math.PI) _d -= 2 * Math.PI;
                            while (_d < -Math.PI) _d += 2 * Math.PI;
                            if (Math.abs(_d) < 0.02) vrm.scene.rotation.y = _tgt;
                            else vrm.scene.rotation.y += _d * (1 - Math.exp(-12 * dt));
                        }
                    }
                    if (ik && this.grounded) {
                        ik.descentContext = false;
                        ik.footPlantForwardOffset = 0;
                        ik.update(dt);
                    }
                }
                this.externalGroundY = null;
                return;
            }

            // ── MANEUVER IN FLIGHT ─────────────────────────────────────
            // A vault/jump/climb/landing owns the frame end-to-end: root
            // trajectory, anim weights, mixer. Normal locomotion resumes
            // when it completes.
            if (this._maneuver) {
                this._updateManeuver(dt);
                return;
            }
            if (this._maneuverCooldownT > 0) this._maneuverCooldownT -= dt;
            // A completed maneuver's one-shot clip fades out under the
            // resuming locomotion.
            if (this._fadingManeuverAction) {
                const fa = this._fadingManeuverAction;
                fa.weight = THREE.MathUtils.damp(fa.weight, 0, 10, dt);
                if (fa.weight < 0.01) { fa.weight = 0; this._fadingManeuverAction = null; }
            }

            // RUN MODE — select active anim family based on this.running.
            // If running is true and run anims are available, use them;
            // otherwise fall back to walk anims (graceful degrade if
            // agent forgot to load the run clips).
            const isRunning = this.running && runAction != null;
            const groundAnim   = isRunning ? runAction          : walkAction;
            const stairUpAnim  = isRunning && stairsRunUpAction   ? stairsRunUpAction   : stairsUpAction;
            const stairDownAnim= isRunning && stairsRunDownAction ? stairsRunDownAction : stairsDownAction;

            // ── 1. Forward speed: shape-synced to detected tread run ──
            // In run mode, base speed is runSpeed (~3.6 m/s) and stair
            // cadence uses stairCadenceRun (lower than walk's because
            // stair-run anim cycles cover more ground per cycle).
            const speedLooksDown = (this.aheadLowestDelta ?? 0) < this._stairDownAheadThreshold;
            const speedLooksUp = (this.aheadHighestDelta ?? 0) > this._stairUpAheadThreshold;
            const stairsClipDur = speedLooksDown && !speedLooksUp
                ? (stairDownAnim?.getClip?.()?.duration ?? stairUpAnim?.getClip?.()?.duration ?? 1.0)
                : (stairUpAnim?.getClip?.()?.duration ?? stairDownAnim?.getClip?.()?.duration ?? 1.0);
            const treadRunForSpeed = this.aheadTreadRun ?? null;
            const baseSpeed   = isRunning ? this._runSpeed       : this._flatSpeed;
            const stairCad    = isRunning ? this._stairCadenceRun : this._stairCadence;
            let targetForwardSpeed = baseSpeed;
            const confirmedStairSpeed =
                !this._requireConfirmedStairClips ||
                (this._confirmedStairFrames ?? 0) > 0;
            if (confirmedStairSpeed &&
                treadRunForSpeed !== null &&
                (this.aheadProbeSpread ?? 0) > this._stairSpreadThreshold) {
                targetForwardSpeed = (2 * treadRunForSpeed * stairCad) / stairsClipDur;
                if (this.aheadStairShape === 'large' &&
                    (this.aheadHighestDelta ?? 0) > this._stairUpAheadThreshold) {
                    targetForwardSpeed *= this._largeStairAscentSpeedScale;
                }
            }
            this._smoothFwdSpeed = THREE.MathUtils.lerp(
                this._smoothFwdSpeed, targetForwardSpeed, Math.min(1, 3 * dt));

            // Combine commanded direction with computed speed.
            const inZ = (input.z ?? 0) * this._smoothFwdSpeed;
            const inX = (input.x ?? 0) * this._smoothFwdSpeed;

            // ── 2. Physics + ground detection ──
            if (ik) {
                const readIKContact = (side, limb) => {
                    if (!limb || !limb.canReachTarget) return { side, valid: false };
                    const hit = limb.LowestHitPoint;
                    const actual = limb.LowBonePosition;
                    const footHeight = (limb.distanceFromMesh ?? 0) - (ik.m_FootHeightOffset ?? 0);
                    const hitY = Number.isFinite(hit?.y) ? hit.y : null;
                    const soleGapY = hitY !== null ? actual.y - hitY - footHeight : null;
                    return {
                        side,
                        valid: hitY !== null && Number.isFinite(soleGapY),
                        hitY,
                        soleGapY,
                        inSwing: !!limb._inSwing || (limb._syntheticLift ?? 0) > 0.035,
                        syntheticLift: limb._syntheticLift ?? 0,
                    };
                };
                this._priorIKSupportContacts = [
                    readIKContact('left', ik.m_LeftLeg),
                    readIKContact('right', ik.m_RightLeg),
                ];
                this._priorFootContactState = {
                    left: {
                        inSwing: !!ik.m_LeftLeg?._inSwing,
                        swingPhase: ik.m_LeftLeg?._swingPhase ?? 0,
                        syntheticLift: ik.m_LeftLeg?._syntheticLift ?? 0,
                    },
                    right: {
                        inSwing: !!ik.m_RightLeg?._inSwing,
                        swingPhase: ik.m_RightLeg?._swingPhase ?? 0,
                        syntheticLift: ik.m_RightLeg?._syntheticLift ?? 0,
                    },
                };
            }
            this.update(dt, { x: inX, z: inZ });

            const t2 = this.bodyTranslation;
            const grounded = this.grounded;
            const speedActual = this.speedActual;
            const moving = speedActual > 0.3;

            // ── 2.5 Landing recovery + auto-maneuvers ─────────────────
            // Track airborne drop height; a touchdown after a real fall
            // plays the fallLand recovery one-shot (zero input, grounded
            // physics) before locomotion resumes.
            {
                const feetYNow = t2.y - this.halfHeight - this.hipY;
                if (!grounded) {
                    if (this._airborneFromY === null) this._airborneFromY = feetYNow;
                    else this._airborneFromY = Math.max(this._airborneFromY, feetYNow);
                    this._airborneTime += dt;
                } else {
                    if (this._airborneFromY !== null) {
                        const drop = this._airborneFromY - feetYNow;
                        if (drop >= this.fallLandMinDrop && this._actions?.fallLand) {
                            this._airborneFromY = null;
                            this._airborneTime = 0;
                            if (this._startManeuver({
                                type: 'land', slot: 'fallLand',
                                duration: null,   // native clip duration (capped in _startManeuver)
                            })) return;
                        }
                    }
                    this._airborneFromY = null;
                    this._airborneTime = 0;
                }
            }
            // Scan the travel direction for things a step can't handle:
            // cover-height walls → VAULT, deep/tall blocks → MOUNT/CLIMB,
            // gaps with a level far side → JUMP. Auto-triggered en route.
            // (Cooldown gating happens per-branch inside — solid obstacles
            // must fire even during cooldown, or a wall below hip height
            // slides under the upper-body collider and she phases through.)
            if (this.autoManeuvers && grounded && moving &&
                (Math.abs(inX) > 1e-3 || Math.abs(inZ) > 1e-3)) {
                let fx, fz;
                if (this._turningEnabled) {
                    fx = Math.sin(this._heading);
                    fz = Math.cos(this._heading);
                } else {
                    const l = Math.hypot(inX, inZ);
                    fx = inX / l; fz = inZ / l;
                }
                if (this._maybeAutoManeuver(fx, fz, speedActual)) return;
            }

            // ── 3. Vertical motion detection (ascending/descending) ──
            if (this._lastBodyY === null) this._lastBodyY = t2.y;
            const bodyVelY = (t2.y - this._lastBodyY) / dt;
            this._lastBodyY = t2.y;
            const ascending  = grounded && moving && bodyVelY >  this._ascendThreshold;
            const descending = grounded && moving && bodyVelY <  this._descendThreshold;

            // ── 4. Stair detection (sticky-window + direction classifier) ──
            const climbBlocked = this._climbBlocked ?? false;
            const stepLikeNow = !!this.aheadStepLike;
            const steepRampLikeNow = !!this.aheadSmoothRampLike;
            const transitionCountNow = this.supportFrame?.probes?.transitionDs?.length ?? 0;
            const measuredMultiEdgeStair = stepLikeNow && transitionCountNow >= 2;
            if (measuredMultiEdgeStair) {
                this._confirmedStairFrames = this._confirmedStairHoldFrames;
            } else if ((this._confirmedStairFrames ?? 0) > 0 && (stepLikeNow || steepRampLikeNow)) {
                this._confirmedStairFrames = Math.max(0, this._confirmedStairFrames - 1);
            } else if (!stepLikeNow && !steepRampLikeNow) {
                this._confirmedStairFrames = 0;
            }
            this._stepEvidenceHistory.push(stepLikeNow ? 1 : 0);
            this._stairMotionHistory.push((stepLikeNow || steepRampLikeNow) ? 1 : 0);
            if (this._stepEvidenceHistory.length > this._stairSpreadHistoryLen) this._stepEvidenceHistory.shift();
            if (this._stairMotionHistory.length > this._stairSpreadHistoryLen) this._stairMotionHistory.shift();
            let recentStepEvidence = false;
            for (const v of this._stepEvidenceHistory) if (v > 0) { recentStepEvidence = true; break; }
            let recentStairMotion = false;
            for (const v of this._stairMotionHistory) if (v > 0) { recentStairMotion = true; break; }
            const confirmedStairClip =
                !this._requireConfirmedStairClips ||
                measuredMultiEdgeStair ||
                (this._confirmedStairFrames ?? 0) > 0;
            const stairAhead = grounded && moving && recentStairMotion && confirmedStairClip && !climbBlocked;
            const aheadHigh = this.aheadHighestDelta ?? 0;
            const aheadLow  = this.aheadLowestDelta  ?? 0;
            const stairUpAhead   = stairAhead && aheadHigh > this._stairUpAheadThreshold;
            const stairDownAhead = stairAhead && aheadLow  < this._stairDownAheadThreshold;
            const smallStairGuardRise = this._smallStairAscentGuardRise ?? 0.035;
            const smallStairNoFutureRise =
                this.aheadStairShape === 'small' &&
                !stepLikeNow &&
                aheadHigh <= smallStairGuardRise &&
                aheadLow >= -smallStairGuardRise;
            const tallRiserAhead = aheadHigh > this._tallRiserThreshold;
            const absClimbAngle = Math.abs(this.signedClimbAngleDeg ?? 0);
            const rampWalkSpread = this.aheadProbeSpread ?? 0;
            const activeStairClipWindow = (this._confirmedStairFrames ?? 0) > 0;
            const shallowContinuousRamp =
                absClimbAngle <= (this._rampWalkMaxAngle ?? 8.0) &&
                rampWalkSpread <= (this._rampWalkMaxProbeSpread ?? 0.085);
            const steepContinuousStairContext =
                grounded &&
                moving &&
                !stepLikeNow &&
                (this.aheadTreadRun ?? null) === null &&
                steepRampLikeNow &&
                absClimbAngle > (this._rampWalkMaxAngle ?? 8.0) &&
                !climbBlocked;
            const smoothRampWalkNow =
                grounded &&
                moving &&
                !activeStairClipWindow &&
                !stepLikeNow &&
                (this.aheadTreadRun ?? null) === null &&
                rampWalkSpread >= (this._rampWalkMinProbeSpread ?? 0.015) &&
                absClimbAngle >= (this._rampWalkAngleThreshold ?? 2.0) &&
                shallowContinuousRamp;
            const shallowSingleLargeEdge =
                grounded &&
                moving &&
                !activeStairClipWindow &&
                stepLikeNow &&
                transitionCountNow === 1 &&
                (this.aheadStepRiseRaw ?? 0) > (this._tallRiserThreshold ?? 0.20) &&
                absClimbAngle <= (this._rampEdgeAngleThreshold ?? 8.0);
            const recentSmoothRampContext = (this._smoothRampContextFrames ?? 0) > 0;
            const smoothRampContext =
                smoothRampWalkNow ||
                shallowSingleLargeEdge ||
                (recentSmoothRampContext && !steepContinuousStairContext && (!stepLikeNow || shallowSingleLargeEdge));
            if (smoothRampWalkNow || shallowSingleLargeEdge) {
                this._smoothRampContextFrames = this._rampContextHoldFrames ?? 12;
            } else if (steepContinuousStairContext) {
                this._smoothRampContextFrames = 0;
            } else if (stepLikeNow) {
                this._smoothRampContextFrames = 0;
            } else {
                this._smoothRampContextFrames = Math.max(0, (this._smoothRampContextFrames ?? 0) - 1);
            }
            const untreadedObstacleWalk =
                this.preferWalkOnUntreadedObstacles &&
                grounded &&
                moving &&
                stepLikeNow &&
                this.aheadTreadRun === null &&
                (this.aheadProbeSpread ?? 0) <= (this.obstacleWalkMaxSpread ?? 0.18) &&
                Math.max(Math.abs(aheadHigh), Math.abs(aheadLow)) <= (this.obstacleWalkMaxRise ?? 0.18);
            const isolatedObstacleWalk =
                this.preferWalkOnIsolatedObstacles &&
                grounded &&
                moving &&
                !!this.aheadIsolatedObstacle;
            const smallStairEarlyAscent =
                grounded &&
                moving &&
                !!this.smallStairAscentEarlyUp &&
                !smallStairNoFutureRise &&
                !isolatedObstacleWalk &&
                !climbBlocked;

            // ── 5. Anim weight targets ──
            let targetIdle = 0, targetWalk = 0, targetStairsUp = 0, targetStairsDown = 0, targetFall = 0;
            if (!grounded && fallIdleAction)                            targetFall = 1;
            else if (!moving)                                           targetIdle = 1;
            else if (smoothRampContext)                                 targetWalk = 1;
            else if (steepContinuousStairContext && (this.signedClimbAngleDeg ?? 0) > 0 && stairsUpAction) targetStairsUp = 1;
            else if (steepContinuousStairContext && (this.signedClimbAngleDeg ?? 0) < 0 && stairsDownAction) targetStairsDown = 1;
            else if (untreadedObstacleWalk || isolatedObstacleWalk)      targetWalk = 1;
            else if ((smallStairEarlyAscent || ((ascending && !smallStairNoFutureRise) || stairUpAhead)) && stairsUpAction) targetStairsUp = 1;
            else if ((descending || stairDownAhead) && stairsDownAction) targetStairsDown = 1;
            else                                                        targetWalk = 1;

            const enteringIdle = !moving;
            const baseLambda = (!grounded ? 20 : (enteringIdle ? 18 : 8));
            const stairEngLambda = tallRiserAhead ? this._tallRiserEngageLambda : this._stairEngageLambda;
            const dampStair = (cur, tgt) => THREE.MathUtils.damp(cur, tgt,
                (tgt === 0 && cur > 0.01) ? this._stairLeavingLambda :
                (tgt > 0   && cur < 0.5)  ? stairEngLambda :
                baseLambda, dt);
            const damp = (cur, tgt) => THREE.MathUtils.damp(cur, tgt, baseLambda, dt);
            // Weights go to the ACTIVE gait family (walk-family or run-family,
            // per this.running). The inactive family always damps to 0 — so
            // toggling running mid-path crossfades walk↔run instead of the run
            // clip never receiving weight (speed at run pace over a capped
            // walk clip = the glide bug this replaced).
            if (idleAction)     idleAction.weight     = damp(idleAction.weight, targetIdle);
            if (groundAnim)     groundAnim.weight     = damp(groundAnim.weight, targetWalk);
            if (stairUpAnim)    stairUpAnim.weight    = dampStair(stairUpAnim.weight, targetStairsUp);
            if (stairDownAnim)  stairDownAnim.weight  = dampStair(stairDownAnim.weight, targetStairsDown);
            if (fallIdleAction) fallIdleAction.weight = damp(fallIdleAction.weight, targetFall);
            for (const a of [walkAction, runAction, stairsUpAction, stairsDownAction,
                             stairsRunUpAction, stairsRunDownAction]) {
                if (a && a !== groundAnim && a !== stairUpAnim && a !== stairDownAnim) {
                    a.weight = THREE.MathUtils.damp(a.weight, 0, 10, dt);
                }
            }
            if (smallStairNoFutureRise && stairUpAnim) {
                stairUpAnim.weight = THREE.MathUtils.damp(
                    stairUpAnim.weight, 0, this._smallStairAscentExitClearLambda ?? 48, dt);
            }
            if (smoothRampContext) {
                if (stairUpAnim) {
                    stairUpAnim.weight = THREE.MathUtils.damp(
                        stairUpAnim.weight, 0, this._rampStairClearLambda, dt);
                }
                if (stairDownAnim) {
                    stairDownAnim.weight = THREE.MathUtils.damp(
                        stairDownAnim.weight, 0, this._rampStairClearLambda, dt);
                }
            }
            // Stateful descent/ascent entry: if raw support says one stair
            // direction is active, clear the opposite stair clip faster. This
            // follows the controller references' "stateful contact" model and
            // avoids stale stairsUp pose bleeding into large-stair descent.
            if (!untreadedObstacleWalk && !isolatedObstacleWalk && stairDownAhead && stairUpAnim) {
                stairUpAnim.weight = THREE.MathUtils.damp(
                    stairUpAnim.weight, 0, this._oppositeStairClearLambda, dt);
            }
            if (!untreadedObstacleWalk && !isolatedObstacleWalk && stairUpAhead && stairDownAnim) {
                stairDownAnim.weight = THREE.MathUtils.damp(
                    stairDownAnim.weight, 0, this._oppositeStairClearLambda, dt);
            }
            if (this.supportFrame) {
                this.supportFrame.animation = {
                    targetIdle,
                    targetWalk,
                    targetStairsUp,
                    targetStairsDown,
                    targetFall,
                    confirmedStairClip,
                    confirmedStairFrames: this._confirmedStairFrames ?? 0,
                    measuredMultiEdgeStair,
                    untreadedObstacleWalk,
                    isolatedObstacleWalk,
                    smoothRampContext,
                    smoothRampWalkNow,
                    shallowSingleLargeEdge,
                    shallowContinuousRamp,
                    steepContinuousStairContext,
                    smallStairEarlyAscent,
                    stairPhaseLock: this._stairPhaseLockInfo,
                    running: isRunning,
                    weights: {
                        idle: idleAction?.weight ?? 0,
                        ground: groundAnim?.weight ?? 0,
                        stairsUp: stairUpAnim?.weight ?? 0,
                        stairsDown: stairDownAnim?.weight ?? 0,
                        fallIdle: fallIdleAction?.weight ?? 0,
                    },
                };
            }

            // ── 6. Anim timeScale (stride/cadence sync to body velocity) ──
            const nativeGaitSpeed = isRunning ? this._nativeRunSpeed : this._nativeWalkSpeed;
            const gaitRatio = Math.min(speedActual / nativeGaitSpeed, 1.4);
            if (groundAnim) groundAnim.timeScale = gaitRatio;

            // treadRun smoothing — HOLDS last value when raw is null so
            // anim cadence stays synced to the actual stair geometry,
            // not a hardcoded fallback.
            const treadRunRaw = this.aheadTreadRun;
            if (treadRunRaw !== null && treadRunRaw !== undefined) {
                this._smoothTreadRun = THREE.MathUtils.lerp(
                    this._smoothTreadRun, treadRunRaw, Math.min(1, 12 * dt));
            }
            const stairsCycleDistance = 2 * this._smoothTreadRun;
            if (stairUpAnim) {
                const clipDur = stairUpAnim.getClip().duration;
                const k = (speedActual * clipDur) / stairsCycleDistance;
                stairUpAnim.timeScale = Math.max(0.2, Math.min(k, 3.0));
            }
            if (stairDownAnim) {
                const clipDur = stairDownAnim.getClip().duration;
                const k = (speedActual * clipDur) / stairsCycleDistance;
                stairDownAnim.timeScale = Math.max(0.2, Math.min(k, 3.0));
            }

            // Small-stair phase lock: body speed and stair clip timeScale
            // already agree on "one footfall per tread". What was still
            // arbitrary was the clip's starting phase, because all actions run
            // in the background at zero weight. Anchor the active stair clip to
            // measured tread progress so the same terrain position maps to the
            // same gait phase in every scene. This candidate applies it to
            // descent only; ascent phase needs separate calibration because
            // the first phase-lock pass put toes into risers.
            this._stairPhaseLockInfo = null;
            if (this._smallStairPhaseLock && !isolatedObstacleWalk && this.aheadStairShape === 'small') {
                const stairsUpW = stairUpAnim?.weight ?? 0;
                const stairsDownW = stairDownAnim?.weight ?? 0;
                const dir = stairsDownW > stairsUpW ? 'down' : 'up';
                const phaseAction = dir === 'down' ? stairDownAnim : stairUpAnim;
                const phaseWeight = dir === 'down' ? stairsDownW : stairsUpW;
                const run = this.aheadTreadRun ?? this._lastTreadRun ?? this._smoothTreadRun;
                const directionEnabled = dir === 'down'
                    ? (this._smallStairPhaseLockDescent ?? true)
                    : (this._smallStairPhaseLockAscent ?? false);
                const canLock =
                    directionEnabled &&
                    grounded &&
                    moving &&
                    recentStepEvidence &&
                    phaseAction &&
                    phaseWeight > (this._smallStairPhaseMinWeight ?? 0.05) &&
                    Number.isFinite(run) &&
                    run > 0.08;
                if (canLock) {
                    const transitions = this.supportFrame?.probes?.transitionDs ?? [];
                    let nearestEdgeD = null;
                    for (const d of transitions) {
                        if (!Number.isFinite(d)) continue;
                        if (nearestEdgeD === null || d < nearestEdgeD) nearestEdgeD = d;
                    }
                    const resetPhase =
                        !this._stairPhaseLockActive ||
                        this._stairPhaseLockDir !== dir ||
                        this._stairPhaseLockShape !== this.aheadStairShape;
                    if (resetPhase) {
                        const edgeProgress = nearestEdgeD !== null
                            ? THREE.MathUtils.euclideanModulo(run - nearestEdgeD, run)
                            : 0;
                        this._stairPhaseDistance = edgeProgress;
                        this._stairPhaseLockActive = true;
                        this._stairPhaseLockDir = dir;
                        this._stairPhaseLockShape = this.aheadStairShape;
                    } else {
                        this._stairPhaseDistance += Math.max(0, speedActual * dt);
                    }

                    const clipDur = phaseAction.getClip().duration;
                    const cycleDistance = Math.max(0.01, 2 * run);
                    const phaseOffset = dir === 'down'
                        ? (this._smallStairDescentPhaseOffset ?? 0)
                        : (this._smallStairAscentPhaseOffset ?? 0);
                    const targetNorm = THREE.MathUtils.euclideanModulo(
                        this._stairPhaseDistance / cycleDistance + phaseOffset,
                        1,
                    );
                    const targetTime = targetNorm * clipDur;
                    const preMixerTime = THREE.MathUtils.euclideanModulo(
                        targetTime - (phaseAction.timeScale ?? 1) * dt,
                        clipDur,
                    );
                    phaseAction.time = preMixerTime;
                    this._stairPhaseLockInfo = {
                        active: true,
                        dir,
                        shape: this.aheadStairShape,
                        run,
                        nearestEdgeD,
                        distance: this._stairPhaseDistance,
                        targetNorm,
                        targetTime,
                        preMixerTime,
                        weight: phaseWeight,
                    };
                } else {
                    this._stairPhaseLockActive = false;
                    this._stairPhaseLockDir = null;
                    this._stairPhaseLockShape = null;
                }
            } else {
                this._stairPhaseLockActive = false;
                this._stairPhaseLockDir = null;
                this._stairPhaseLockShape = null;
            }

            // ── 6.5 Upper-body gesture overlay (wave/talk while moving) ──
            this._updateGestureWeights(dt);

            // ── 7. Advance the mixer (anim FK pose) ──
            if (mixer) mixer.update(dt);

            // ── 8. Pose overrides — hip lean + head pitch ──
            let hipsLeanDeg = 0;
            if (vrm?.humanoid) {
                const hipsBone = vrm.humanoid.getNormalizedBoneNode('hips');
                if (hipsBone) {
                    const climbForLean = this.signedClimbAngleDeg ?? 0;
                    const leanFactor = climbForLean >= 0 ? this._hipLeanAscent : this._hipLeanDescent;
                    const walkW = groundAnim?.weight ?? 0;
                    const leanGate = Math.max(0, Math.min(1, walkW));
                    const targetLean = Math.abs(climbForLean) * leanFactor * leanGate;
                    const kLean = Math.min(1, dt * 6);
                    this._smoothHipsLeanDeg = this._smoothHipsLeanDeg * (1 - kLean) + targetLean * kLean;
                    hipsLeanDeg = this._smoothHipsLeanDeg;
                    const pitchRad = hipsLeanDeg * Math.PI / 180;
                    const pitchQuat = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), pitchRad);
                    hipsBone.quaternion.premultiply(pitchQuat);
                }
                const headBone = vrm.humanoid.getNormalizedBoneNode('head');
                if (headBone) {
                    if (!this._headRestQuat) this._headRestQuat = headBone.quaternion.clone();
                    const climbForHead = this.signedClimbAngleDeg ?? 0;
                    const walkWHead = groundAnim?.weight ?? 0;
                    let headPitchBonus = 0;
                    if (climbForHead > 0)
                        headPitchBonus = Math.min(this._headPitchBonusMax, climbForHead * 0.5) * walkWHead;
                    else if (climbForHead < 0)
                        headPitchBonus = Math.max(-this._headPitchBonusMax, climbForHead * 0.5) * walkWHead;
                    const targetAngleDeg = climbForHead + headPitchBonus;
                    const headLpK = Math.min(1, dt * 6);
                    this._smoothHeadPitchDeg = this._smoothHeadPitchDeg * (1 - headLpK) + targetAngleDeg * headLpK;
                    const headLocalDeg = this._smoothHeadPitchDeg - hipsLeanDeg * Math.sign(this._smoothHeadPitchDeg || 1);
                    const pitchRad = -headLocalDeg * Math.PI / 180;
                    const pitchQuat = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), pitchRad);
                    headBone.quaternion.copy(this._headRestQuat).multiply(pitchQuat);
                }
            }

            // ── 9. Place VRM at controller's feet world position ──
            if (vrm?.scene) {
                vrm.scene.position.copy(this.feetWorldPosition);
                vrm.scene.rotation.y = this._turningEnabled ? this._heading : Math.PI;
                // A finished climb's end-crouch sink fades with the fading
                // clip's weight — pose and root rise together, so the feet
                // never sink into (or pop off) the landing surface.
                if (this._maneuverVisualSink > 0.005 && this._fadingManeuverAction) {
                    const w = this._fadingManeuverAction.getEffectiveWeight?.() ?? 0;
                    vrm.scene.position.y -= this._maneuverVisualSink * Math.min(1, w);
                    if (w < 0.02) this._maneuverVisualSink = 0;
                    // The crouch pose reaches its hands near the surface, and
                    // the maneuver's own contact IK is gone — keep the hands
                    // pushed up OUT of the landing surface through the fade.
                    if (this.groundY != null) {
                        const st = (this._postManeuverIK = this._postManeuverIK || {});
                        for (const side of ['left', 'right']) {
                            const n = vrm.humanoid?.getNormalizedBoneNode?.(side + 'Hand');
                            if (!n) continue;
                            const hp = n.getWorldPosition(new THREE.Vector3());
                            if (hp.y < this.groundY + 0.01) {
                                this._solveArmIK(side, this._smoothLimbTarget(st, side + 'HandPost',
                                    new THREE.Vector3(hp.x, this.groundY + 0.02, hp.z)), 0.65);
                            }
                        }
                    }
                }
            }

            // ── 10. Body Y drop on descent (knee bend, prevents leg-stretch) ──
            {
                const angle = this.signedClimbAngleDeg ?? 0;
                const walkW = groundAnim?.weight ?? 0;
                // Ramp-vs-stairs distinguisher: treadRun is null on smooth
                // ramps AND probe spread is small (no Y discontinuities).
                const onRampNotStairs = (this.aheadTreadRun ?? null) === null
                    && (this.aheadProbeSpread ?? 0) < 0.10;

                // Walk-anim body drop only applies when we're ACTUALLY on
                // a ramp (or flat). On stairs the natural per-tread body
                // drop already handles vertical descent — adding the
                // walk-anim drop on top during the brief stair-anim
                // transition window (when walkW is still partial but
                // stairs are detected) produces a visible duck up to 22cm
                // beyond the natural step-down. Gating on onRampNotStairs
                // prevents this.
                let targetDrop;
                if (angle < 0 && smoothRampContext) {
                    targetDrop = Math.min(
                        this._rampBodyYDropDescentCap,
                        Math.abs(angle) * this._rampBodyYDropDescent,
                    ) * walkW;
                }
                else if (angle < 0 && onRampNotStairs) targetDrop = Math.min(this._bodyYDropDescentCap, Math.abs(angle) * this._bodyYDropDescent) * walkW;
                else if (angle > 0 && onRampNotStairs) targetDrop = Math.min(this._bodyYDropAscentCap,  angle * this._bodyYDropAscent) * walkW;
                else                                   targetDrop = 0;

                const stairsDownW = stairDownAnim?.weight ?? 0;
                if (!smoothRampContext && angle < 0 && stairsDownW > 0.01 && onRampNotStairs) {
                    targetDrop += Math.min(this._bodyYDropStairRampCap, Math.abs(angle) * this._bodyYDropStairRamp) * stairsDownW;
                }
                const kDrop = Math.min(1, dt * 6);
                this._smoothBodyDrop = this._smoothBodyDrop * (1 - kDrop) + targetDrop * kDrop;
                if (vrm?.scene) vrm.scene.position.y -= this._smoothBodyDrop;
            }

            // ── 11. Foot IK config (descentContext + plant offset) ──
            if (ik) {
                const movingForward = speedActual > 0.3;
                // descentContext engages a per-leg rolling-min upY
                // subtraction in the IK (compensates for Mixamo stairsDown
                // clip's foot-bone baseline drift). Scoped to shallow
                // descents only — on tall stairs the subtract pulled
                // the swing foot below the FK arc.
                const stairsUpW   = stairUpAnim?.weight   ?? 0;
                const stairsDownW = stairDownAnim?.weight ?? 0;
                const animW = Math.max(stairsUpW, stairsDownW);
                const smallStairDescent = this.aheadStairShape === 'small' && stairsDownW > 0.05;
                const isShallowDescent = Math.abs(aheadLow) < 0.13 || smallStairDescent;
                const stairRise = Math.max(0.001, this.aheadStairRise || this._latchedStairRise || 0.10);
                const multiSmallRiseAhead =
                    this.aheadStairShape === 'small' &&
                    aheadHigh > stairRise * 1.35;
                const smallStairCurrentRise =
                    this.aheadStairShape === 'small' &&
                    aheadHigh > smallStairGuardRise &&
                    !smallStairNoFutureRise;
                const earlyOnlySmallStairAscent = smallStairEarlyAscent && !smallStairCurrentRise;
                const smallStairOffsetContext = smallStairCurrentRise || earlyOnlySmallStairAscent;
                const smallStairSingleRiseScale = multiSmallRiseAhead
                    ? (this._smallStairAscentMultiRiseOffsetScale ?? 0.60)
                    : (this._smallStairAscentSingleRiseOffsetScale ?? 0.58);
                const smallStairSoleFitScale = multiSmallRiseAhead
                    ? (this._smallStairAscentMultiRiseSoleFitScale ?? 0.46)
                    : (this._smallStairAscentSingleRiseSoleFitScale ?? 0.36);
                const smallStairOffsetScale = earlyOnlySmallStairAscent
                    ? (this._smallStairAscentEarlyOffsetScale ?? 0.42)
                    : smallStairSingleRiseScale;
                ik.descentContext = !isolatedObstacleWalk && movingForward && aheadLow < -0.05 && isShallowDescent;
                ik.stepClearanceContext = isolatedObstacleWalk;
                ik.flatWalkContext = grounded && movingForward && !isolatedObstacleWalk && smoothRampContext;
                ik.stairAscentSoleFitContext =
                    !!this._smallStairAscentSoleFit &&
                    !isolatedObstacleWalk &&
                    grounded &&
                    movingForward &&
                    smallStairCurrentRise &&
                    this.aheadStairShape === 'small' &&
                    stairsUpW > 0.20 &&
                    stairsUpW > stairsDownW;
                ik.stairAscentTreadRun = ik.stairAscentSoleFitContext
                    ? (this.aheadTreadRun ?? this._lastTreadRun ?? null)
                    : null;
                ik.stairAscentOffsetScale = smallStairOffsetContext ? smallStairOffsetScale : 0;
                ik.stairAscentSoleFitMaxScale = ik.stairAscentSoleFitContext ? smallStairSoleFitScale : 0;
                const smallStairEdgeAlignContext =
                    !!this._smallStairAscentEdgeAlign &&
                    !isolatedObstacleWalk &&
                    grounded &&
                    movingForward &&
                    this.aheadStairShape === 'small' &&
                    stairsUpW > 0.12 &&
                    stairsUpW > stairsDownW &&
                    (smallStairCurrentRise || earlyOnlySmallStairAscent || smallStairEarlyAscent);
                const stairAscentEdgeAlign = this._updateSmallStairAscentEdgeAlignHint(smallStairEdgeAlignContext);
                ik.stairAscentEdgeAlignContext = !!stairAscentEdgeAlign?.active;
                ik.stairAscentEdgePoint = stairAscentEdgeAlign?.point ?? null;
                ik.stairAscentMoveDir = stairAscentEdgeAlign?.dir ?? null;
                ik.stairAscentEdgeTreadRun =
                    stairAscentEdgeAlign?.run ?? this.aheadTreadRun ?? this._lastTreadRun ?? null;
                if (this.supportFrame) {
                    this.supportFrame.stairAscentEdgeAlign = stairAscentEdgeAlign;
                }
                ik.rampFootClearanceOffset =
                    smoothRampContext && (this.signedClimbAngleDeg ?? 0) < -0.5
                        ? (this._rampFootClearanceOffset ?? 0.008)
                        : 0;
                let combinedOffset = 0;

                if (!isolatedObstacleWalk && stairsUpW > stairsDownW && (recentStepEvidence || smallStairEarlyAscent)) {
                    // ASCENT — use the raw/latching stair-rise bucket, not a
                    // smoothed climb-angle curve. This prevents large-stair
                    // entry from briefly passing through the "small stair"
                    // offset branch while climb angle converges.
                    const shape = this.aheadStairShape;
                    if ((shape === 'small' && smallStairCurrentRise) || earlyOnlySmallStairAscent) {
                        combinedOffset = this._footOffsetAscent *
                            this._footOffsetAscentSmallScale *
                            smallStairOffsetScale *
                            animW;
                    }
                } else if (!isolatedObstacleWalk && stairsDownW > 0.05 && recentStepEvidence) {
                    // DESCENT — explicit per-rise buckets. Small stairs keep
                    // the old working shift; normal/large get slightly less
                    // forward shift to reduce riser/heel overreach without
                    // a continuous curve bleeding through transient values.
                    const aheadLowRaw = this.aheadLowestDelta ?? 0;
                    if (aheadLowRaw < -0.05) {
                        let mag;
                        if (this.aheadStairShape === 'small') {
                            mag = this._footOffsetDescentSmall;
                        } else if (this.aheadStairShape === 'normal') {
                            mag = this._footOffsetDescentNormal;
                        } else if (this.aheadStairShape === 'large') {
                            mag = this._footOffsetDescentLarge;
                        } else {
                            const rise = Math.abs(aheadLowRaw);
                            mag = Math.max(0.20, Math.min(0.40, 0.43 - 0.9 * rise));
                        }
                        combinedOffset = mag * animW;
                    }
                }

                ik.footPlantForwardOffset = combinedOffset;
                if (ik._gptDefaultExtraCastReachScale === undefined) {
                    ik._gptDefaultExtraCastReachScale = ik.extraCastReachScale ?? 0.5;
                }
                const largeStairAscentIK =
                    !isolatedObstacleWalk &&
                    stairsUpW > 0.05 &&
                    recentStepEvidence &&
                    this.aheadStairShape === 'large' &&
                    aheadHigh > 0.05;
                ik.extraCastReachScale = (this._largeStairFullToeReach && largeStairAscentIK)
                    ? 1.00
                    : ik._gptDefaultExtraCastReachScale;

                ik.increasedAccuracy = true;

                if (grounded) {
                    ik.update(dt);

                    // Directional foot support is recorded as a
                    // support observation. By default it does not drive root Y;
                    // update() may consume it only if useFootSupportForRoot is
                    // explicitly enabled and the candidate is stable.
                    const useDirectionalFootSupport = recentStepEvidence;
                    let footSupportY = null;
                    let footSupportSource = null;
                    if (ik.CanReachTargets && useDirectionalFootSupport) {
                        const moveLen = Math.hypot(inX, inZ);
                        if (moveLen > 1e-4 && typeof ik.DirectionalFootHeight === 'function') {
                            const moveDir = new THREE.Vector3(inX / moveLen, 0, inZ / moveLen);
                            const footPoint = ik.DirectionalFootHeight(moveDir);
                            footSupportY = Number.isFinite(footPoint?.y) ? footPoint.y : null;
                            footSupportSource = 'directionalFoot';
                        } else if (Number.isFinite(ik.LowestFootHeight)) {
                            footSupportY = ik.LowestFootHeight;
                            footSupportSource = 'lowestFoot';
                        }
                    }
                    if (Number.isFinite(footSupportY)) {
                        if (Number.isFinite(this._lastFootSupportY) &&
                            Math.abs(footSupportY - this._lastFootSupportY) <= 0.04) {
                            this._footSupportStableFrames++;
                        } else {
                            this._footSupportStableFrames = 1;
                        }
                        this._lastFootSupportY = footSupportY;
                        this._footSupportObservation = {
                            y: footSupportY,
                            source: footSupportSource,
                            stableFrames: this._footSupportStableFrames,
                            stable: this._footSupportStableFrames >= (this._footSupportRootStableFrames ?? 4),
                            canReachTargets: !!ik.CanReachTargets,
                        };
                        this.externalGroundY = footSupportY;
                    } else {
                        this._footSupportStableFrames = 0;
                        this._lastFootSupportY = null;
                        this._footSupportObservation = null;
                        this.externalGroundY = null;
                    }
                } else {
                    this._footSupportStableFrames = 0;
                    this._lastFootSupportY = null;
                    this._footSupportObservation = null;
                    this.externalGroundY = null;
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // MANEUVER ENGINE — vault / mount-climb / gap-jump / landing.
        // One-shot clips over procedural root trajectories. The clips'
        // hips-position tracks are stripped at load, so the controller
        // remains the sole root authority; the clip contributes limb/
        // torso posing while the trajectory carries the body. Foot IK
        // and ground probing suspend for the flight; landing re-grounds
        // cleanly and locomotion resumes.
        // ──────────────────────────────────────────────────────────────
        get isManeuvering() { return !!this._maneuver; }

        setRunning(v) { this.running = !!v; }

        // Dense downward probes along the travel direction — the maneuver
        // planner's view of what's coming (walls, blocks, gaps).
        _scanPathAhead(fx, fz) {
            const cur = this.body.translation();
            const feetY = cur.y - this.halfHeight - this.hipY;
            const originY = cur.y + this.halfHeight + 3.0;
            const step = this.maneuverScanStep;
            const N = Math.max(6, Math.ceil(this.maneuverScanRange / step));
            const samples = [];
            for (let i = 1; i <= N; i++) {
                const d = i * step;
                samples.push({ d, y: this._groundVector(cur.x + fx * d, originY, cur.z + fz * d) });
            }
            return { feetY, samples };
        }

        // Classify the scan into at most one OBSTACLE (a wall-like face —
        // a single-probe-step vertical jump ≥0.40m, which no stair riser
        // produces; stairs rise the same total height but spread it across
        // many probe steps and stay with the stair system) and one GAP (a
        // drop deeper than fallThreshold that returns to ~feet level).
        _classifyPathAhead(scan) {
            const { feetY, samples } = scan;
            const edgeMin = 0.40;
            let obstacle = null;
            let prevY = feetY;
            for (let i = 0; i < samples.length; i++) {
                const s = samples[i];
                if (s.y === null) { prevY = null; continue; }
                if (prevY !== null) {
                    const dy = s.y - prevY;
                    if (dy >= edgeMin && (s.y - feetY) >= this.vaultMinRise) {
                        let topY = s.y, endD = s.d, j = i + 1;
                        for (; j < samples.length; j++) {
                            const t = samples[j];
                            if (t.y === null) break;
                            if (t.y - feetY < this.vaultMinRise * 0.5) break;
                            topY = Math.max(topY, t.y);
                            endD = t.d;
                        }
                        let landing = null;
                        for (let k = j; k < samples.length; k++) {
                            const t = samples[k];
                            if (t.y !== null && Math.abs(t.y - feetY) <= 0.35) { landing = t; break; }
                        }
                        const lastD = samples[samples.length - 1].d;
                        obstacle = {
                            startD: s.d, endD,
                            depth: endD - s.d + this.maneuverScanStep,
                            topY, rise: topY - feetY,
                            landingD: landing ? landing.d : null,
                            landingY: landing ? landing.y : null,
                            plateau: endD >= lastD - 1e-6 || landing === null,
                        };
                        break;
                    }
                }
                prevY = s.y;
            }
            let gap = null;
            if (!obstacle || obstacle.startD > 0.6) {
                // A jumpable gap is a CUT IN THE CURRENT WALKING PLANE:
                //   level approach → deep void → level far side.
                // Anything else — descending stairs with a wall-top beyond
                // (reads as "level far side" but isn't a gap), a lone null
                // probe from a riser face — must NOT trigger a jump.
                let gapStart = null, deepCount = 0, relPrev = 0;
                for (const s of samples) {
                    if (obstacle && s.d >= obstacle.startD) break;
                    const rel = (s.y === null) ? null : s.y - feetY;
                    if (gapStart === null) {
                        if (rel !== null && rel < -this.fallThreshold) {
                            // The void must drop off a NEAR-LEVEL edge. From
                            // mid-stair height the treads slope down into the
                            // "void" gradually — that's stairs to descend, not
                            // a gap to jump (a wall-top beyond can masquerade
                            // as the "far side" otherwise).
                            if (Math.abs(relPrev) > 0.12) break;
                            gapStart = s.d; deepCount = 1;
                        } else if (rel !== null && Math.abs(rel) > 0.30) {
                            break;  // approach isn't level (stairs/slope) — no gap here
                        } else if (rel !== null) {
                            relPrev = rel;
                        }
                        // (null pre-gap samples: edge-face noise — keep scanning)
                    } else if (rel === null || rel < -this.fallThreshold) {
                        if (rel !== null) deepCount++;
                    } else if (Math.abs(rel) <= 0.30) {
                        // Far side back at walking level. Require a REAL void:
                        // ≥2 finite deep readings and a real width.
                        const width = s.d - gapStart;
                        if (deepCount >= 2 && width >= 0.45) {
                            gap = { startD: gapStart, width, landingD: s.d, landingY: s.y };
                        }
                        break;
                    } else {
                        break;  // far side at a different level — not a clean jump
                    }
                }
            }
            return { obstacle, gap, feetY };
        }

        // Auto-trigger during travel. Called from locomote() when grounded
        // + moving. Returns true if a maneuver started.
        // Cooldown policy: GAP jumps honor the full cooldown (they're the
        // noise-prone trigger); solid OBSTACLES only honor a short hard
        // guard — a wall is physical, and skipping it because a jump just
        // finished lets sub-hip walls pass under the body collider.
        _maybeAutoManeuver(fx, fz, speed) {
            const hardGuard = this._maneuverCooldownT > Math.max(0, this.maneuverCooldown - 0.15);
            const gapCooled = this._maneuverCooldownT <= 0;
            if (hardGuard) return false;
            // While the body is still converging up to its known ground
            // (e.g. the damped rise out of a climb's end-crouch), the scan
            // measures rises against transiently-low feet and re-mounts the
            // very surface she's standing on. Wait until settled.
            if (this.groundY != null) {
                const feetNow = this.body.translation().y - this.halfHeight - this.hipY;
                if (this.groundY - feetNow > 0.22) return false;
            }
            const scan = this._scanPathAhead(fx, fz);
            const { obstacle: ob, gap } = this._classifyPathAhead(scan);
            const obstacleTrigger = 0.35 + speed * 0.30;
            const gapTrigger = 0.28 + speed * 0.14;
            if (ob && ob.startD <= obstacleTrigger) {
                if (!ob.plateau && ob.rise <= this.vaultMaxRise &&
                    ob.depth <= this.vaultMaxDepth && ob.landingD !== null) {
                    return this._startVaultOver(scan, ob, fx, fz);
                }
                if (ob.rise <= this.mountMaxRise) return this._startMountOnto(scan, ob, fx, fz, 'climbLedge');
                if (ob.rise <= this.wallClimbMaxRise) return this._startMountOnto(scan, ob, fx, fz, 'climbWallUp');
                if (ob.rise <= this.wallScrambleMaxRise) return this._startWallScramble(scan, ob, fx, fz);
                return false;   // taller than the vocabulary — stays blocked
            }
            if (gap && this.jumpAutoGap && gapCooled &&
                gap.width <= this.jumpMaxGap && gap.startD <= gapTrigger) {
                return this._startGapJump(scan, gap, fx, fz);
            }
            return false;
        }

        _startVaultOver(scan, ob, fx, fz) {
            const cur = this.body.translation();
            const feetY = cur.y - this.halfHeight - this.hipY;
            const landD = Math.min(ob.landingD + 0.25, this.maneuverScanRange);
            const landY = ob.landingY ?? feetY;
            // LOW arc — a vault carries the body barely above the cover and
            // lets the tucked legs clear it (flying the root over
            // top+clearance reads as a moon leap). The clip tucks the legs
            // ~0.3m, so the root only needs the remainder.
            // Readable pace — the vault clip's ACTION segment plays close to
            // its authored rate (the full clip is 3.5s incl. approach steps
            // and a long settle; clipWindow trims to the vault itself). A
            // walking-speed vault stays snappy: floaty slow-motion over a
            // knee-high slab reads weirder than a quick hop.
            const duration = Math.max(0.85, Math.min(1.2, landD / 2.0));
            const VC0 = 0.20, VC1 = 0.62;   // the clip's vault-action window
            // ROOT-MOTION arc (same principle as the climbs): the clip's own
            // hips curve carries the body over the obstacle at the height the
            // animation was authored for — low enough that the planted hand
            // actually MEETS the top. A synthetic ballistic arc floats the
            // body clear of the obstacle and the hands never touch anything.
            let path;
            const rm = this._clipRootMotion?.vault;
            if (rm) {
                const i0 = Math.round(VC0 * rm.N), i1 = Math.round(VC1 * rm.N);
                const zTravel = Math.abs(rm.z[i1] - rm.z[i0]) || 1;
                let peak = 0.001;
                for (let i = i0; i <= i1; i++) peak = Math.max(peak, rm.y[i] - rm.y[i0]);
                // Scale the clip's rise so its peak passes the top with the
                // authored margin (the clip tucks the legs the rest of the way).
                const ys = Math.max(0.5, (ob.rise - 0.22) / peak);
                path = [];
                for (let i = i0; i <= i1; i++) {
                    const u = (i - i0) / Math.max(1, i1 - i0);
                    const d = Math.abs(rm.z[i] - rm.z[i0]) / zTravel * landD;
                    const y = feetY + Math.max(0, rm.y[i] - rm.y[i0]) * ys + (landY - feetY) * u;
                    path.push({ u, x: cur.x + fx * d, y, z: cur.z + fz * d, ease: 'linear' });
                }
                path[path.length - 1].u = 1;
                path[path.length - 1].y = landY;
            } else {
                const apexY = Math.max(feetY, landY) + Math.max(0.12, ob.rise - 0.30);
                const uApex = Math.max(0.35, Math.min(0.65, (ob.startD + (ob.endD - ob.startD) * 0.5) / landD));
                path = [
                    { u: 0,     x: cur.x,                       y: feetY, z: cur.z },
                    { u: uApex, x: cur.x + fx * landD * uApex,  y: apexY, z: cur.z + fz * landD * uApex },
                    { u: 1,     x: cur.x + fx * landD,          y: landY, z: cur.z + fz * landD },
                ];
            }
            // Contact IK — the clip owns all motion; the solve adds only
            // (a) the PLANT: a hand grabs the obstacle top whenever the
            // plant line comes within arm's reach during the crossing,
            // (b) clearance: a foot that would clip INTO the obstacle is
            // pushed up out of it. One-sided otherwise.
            const plantD = ob.startD + Math.min(0.22, (ob.endD - ob.startD) * 0.5);
            const grab = {
                type: 'vaultGeo', window: [0.06, 0.85],
                fx, fz, perpX: -fz, perpZ: fx,
                topY: ob.topY,
                d0: ob.startD - 0.12, d1: ob.endD + 0.12,
                ox: cur.x, oz: cur.z,
                px: cur.x + fx * plantD, pz: cur.z + fz * plantD,
            };
            return this._startManeuver({
                type: 'vault', slot: 'vault', slotFallbacks: ['jump'],
                path, duration, landingGroundY: landY, grab,
                // The vault.vrma ACTION segment (verified frame-by-frame in
                // the clip zoo): approach twist-crouch at u≈0.26, body goes
                // HORIZONTAL over the obstacle with the hand planting at
                // u≈0.37, back on the feet by u≈0.6. Everything after is
                // recovery/settle (which plays out under the ending fade).
                clipWindow: [VC0, VC1],
            });
        }

        _startMountOnto(scan, ob, fx, fz, slot) {
            const cur = this.body.translation();
            const feetY = cur.y - this.halfHeight - this.hipY;
            const topY = ob.topY;
            const rise = topY - feetY;
            // ROOT-MOTION climb: the climbLedge clip's own hips curve drives
            // the capsule, so the body is exactly where the animation authored
            // it and the limbs touch where they look like they touch. A wall
            // shorter than the clip's full rise JOINS the choreography late —
            // the tail of the clip is precisely the mantle-over-the-lip.
            const rm = this._clipRootMotion?.climbLedge;
            if (!rm) {
                console.warn('[eidoverse-controller] mount: climbLedge root motion unavailable');
                return false;
            }
            const N = rm.N;
            const zSgn = Math.sign(rm.z[N] - rm.z[0]) || 1;
            // End of the climb = where the clip's Y tops out (the rest is
            // the on-top settle, which plays out under the post-maneuver
            // fade to locomotion).
            let yMax = -Infinity;
            for (let i = 0; i <= N; i++) yMax = Math.max(yMax, rm.y[i]);
            let iEnd = N;
            for (let i = 0; i <= N; i++) { if (rm.y[i] >= yMax - 0.03) { iEnd = i; break; } }
            iEnd = Math.min(N, iEnd + 2);
            // Walk back from the end until the segment's rise covers the wall.
            let iStart = 0;
            for (let i = iEnd - 1; i >= 0; i--) {
                if (rm.y[iEnd] - rm.y[i] >= rise) { iStart = i; break; }
            }
            const clipRise = rm.y[iEnd] - rm.y[iStart];
            const ys = clipRise > 0.2 ? rise / clipRise : 1;
            // Horizontal: the clip's own forward travel, scaled so the climb
            // ends standing just past the lip. Below the lip the body is
            // clamped outside the wall face.
            const zTravel = (rm.z[iEnd] - rm.z[iStart]) * zSgn;
            const dEnd = ob.startD + 0.32;
            const zs = zTravel > 0.15 ? dEnd / zTravel : 0;
            // Standoff covers the HEAD's forward lean past the chest (plus
            // hair) — a body-radius margin buries the face in the wall.
            const faceMaxD = Math.max(0.04, ob.startD - (this.radius + 0.22));
            const path = [];
            for (let i = iStart; i <= iEnd; i++) {
                const u = (i - iStart) / Math.max(1, iEnd - iStart);
                let d = zs > 0 ? (rm.z[i] - rm.z[iStart]) * zSgn * zs : dEnd * u;
                // Approach: reach the wall face over the first beat — the
                // clip's own forward travel mostly happens at the top-over.
                d = Math.max(d, faceMaxD * Math.min(1, u / 0.12));
                const y = feetY + (rm.y[i] - rm.y[iStart]) * ys;
                if (y < topY - 0.30) d = Math.min(d, faceMaxD);
                path.push({ u, x: cur.x + fx * d, y, z: cur.z + fz * d, ease: 'linear' });
            }
            path[path.length - 1].u = 1;
            // Natural rate: maneuver time = the clip segment's own length.
            const duration = Math.max(1.0, Math.min(3.8, (iEnd - iStart) / N * rm.dur));
            // Hand IK is geometric: grip the lip line while rising toward it,
            // press the top surface during the pull-over. Lateral follows
            // each hand's own animated swing. No leg IK — the clip owns the
            // legs until the top (there's nothing to plant them on).
            const grab = {
                type: 'climb', window: [0, 1],
                fx, fz, perpX: -fz, perpZ: fx,
                topY,
                lipX: cur.x + fx * ob.startD, lipZ: cur.z + fz * ob.startD,
            };
            return this._startManeuver({
                type: 'mount', slot: 'climbLedge', slotFallbacks: [slot, 'jump'],
                path, duration, landingGroundY: topY, grab,
                clipWindow: [iStart / N, iEnd / N],
                // The clip ENDS in a crouch with the feet drawn ~0.65m up
                // toward the hips (probe-measured, rig-independent). The
                // hips-anchored path is truth for the BODY; the crouch is
                // applied as a VISUAL-ONLY sink that fades out with the
                // clip's weight after the maneuver — feet stay planted on
                // the top through the whole crouch-to-stand, no sinking, no
                // popping, and the physics ends exactly at the ledge.
                visualSink: { amount: 0.65, u0: 0.55, u1: 0.98 },
            });
        }

        _startGapJump(scan, gap, fx, fz) {
            const cur = this.body.translation();
            const feetY = cur.y - this.halfHeight - this.hipY;
            const landD = Math.min(gap.landingD + 0.22, this.maneuverScanRange);
            const landY = gap.landingY ?? feetY;
            const apexY = Math.max(feetY, landY) + 0.32 + gap.width * 0.10;
            const uApex = Math.max(0.40, Math.min(0.60, (gap.startD + gap.width * 0.5) / landD));
            const duration = Math.max(0.70, Math.min(1.25, landD / 2.6));
            const path = [
                { u: 0,     x: cur.x,                      y: feetY, z: cur.z },
                { u: uApex, x: cur.x + fx * landD * uApex, y: apexY, z: cur.z + fz * landD * uApex },
                { u: 1,     x: cur.x + fx * landD,         y: landY, z: cur.z + fz * landD },
            ];
            return this._startManeuver({
                type: 'jump', slot: 'jump', path, duration, landingGroundY: landY,
                clipWindow: [0.15, 0.80],   // takeoff→landing inside the 1.9s clip
            });
        }

        // ── Explicit agent-facing APIs ────────────────────────────────
        // vault()/climbLedge() scan along the current heading and perform
        // the move on whatever obstacle is there; jump({distance, height})
        // leaps forward blind (probing the landing height). All return
        // false (with a warn) when the geometry doesn't support the move.
        vault()      { return this._explicitManeuver('vault'); }
        climbLedge() { return this._explicitManeuver('mount'); }

        jump(opts = {}) {
            if (this._maneuver) return false;
            const fx = Math.sin(this._heading), fz = Math.cos(this._heading);
            const cur = this.body.translation();
            const feetY = cur.y - this.halfHeight - this.hipY;
            const dist = opts.distance ?? 1.4;
            const height = opts.height ?? 0.45;
            const probeY = cur.y + this.halfHeight + 3.0;
            const landProbe = this._groundVector(cur.x + fx * dist, probeY, cur.z + fz * dist);
            const landY = (landProbe !== null && Math.abs(landProbe - feetY) < 1.5) ? landProbe : feetY;
            const path = [
                { u: 0,   x: cur.x,                     y: feetY, z: cur.z },
                { u: 0.5, x: cur.x + fx * dist * 0.5,   y: Math.max(feetY, landY) + height, z: cur.z + fz * dist * 0.5 },
                { u: 1,   x: cur.x + fx * dist,         y: landY, z: cur.z + fz * dist },
            ];
            const duration = Math.max(0.65, Math.min(1.30, dist / 2.4));
            return this._startManeuver({
                type: 'jump', slot: 'jump', path, duration, landingGroundY: landY,
                clipWindow: [0.15, 0.80],
            });
        }

        _explicitManeuver(kind) {
            if (this._maneuver) return false;
            const fx = Math.sin(this._heading), fz = Math.cos(this._heading);
            const scan = this._scanPathAhead(fx, fz);
            const { obstacle: ob } = this._classifyPathAhead(scan);
            if (!ob) {
                console.warn(`[eidoverse-controller] ${kind}: no obstacle ahead along the heading`);
                return false;
            }
            if (kind === 'vault') {
                if (ob.landingD === null) {
                    console.warn('[eidoverse-controller] vault: no landing beyond the obstacle — use climbLedge()');
                    return false;
                }
                return this._startVaultOver(scan, ob, fx, fz);
            }
            const slot = ob.rise > this.mountMaxRise ? 'climbWallUp' : 'climbLedge';
            return this._startMountOnto(scan, ob, fx, fz, slot);
        }

        // Climb a ladder (or ladder-like face) directly ahead. The clip
        // LOOPS at native pace while the trajectory rises at `rate` m/s —
        // per-rung cycling instead of one stretched shot. Height comes
        // from opts.height or the scanned face. Call it when the
        // character is at/near the ladder, facing it.
        climbLadder(opts = {}) {
            if (this._maneuver) return false;
            const fx = Math.sin(this._heading), fz = Math.cos(this._heading);
            const scan = this._scanPathAhead(fx, fz);
            const { obstacle: ob } = this._classifyPathAhead(scan);
            const cur = this.body.translation();
            const feetY = cur.y - this.halfHeight - this.hipY;
            const height = opts.height ?? (ob ? ob.rise : null);
            if (!Number.isFinite(height) || height <= 0.2) {
                console.warn('[eidoverse-controller] climbLadder: no height (pass opts.height or face a wall)');
                return false;
            }
            const faceStart = ob ? ob.startD : 0.35;
            // Body centre stays well off the ladder face — the rungs stick
            // out in FRONT of the face, and a climber's chest (and head,
            // which leans past the chest) hangs a good hand-reach behind
            // them.
            const faceD = Math.max(0.06, faceStart - (this.radius + 0.34));
            const topY = feetY + height;
            const rate = opts.rate ?? 0.55;                 // m/s vertical
            // The ladder LOOP only climbs until the CHEST reaches the lip;
            // the top-out then CHAINS into the root-motion mount, whose fit
            // picks exactly the climbLedge clip's mantle tail — an actual
            // pull-over-the-edge animation at the ledge, not the ladder
            // cycle continuing in mid-air.
            const mantleH = Math.min(height, 1.35);
            const climbH = Math.max(0, height - mantleH);
            if (climbH < 0.05) {
                // Too short to bother with the loop — it's just a mount.
                const chainOb = { topY, rise: height, startD: faceStart, endD: faceStart + 0.5 };
                return this._startMountOnto(null, chainOb, fx, fz, 'climbLedge');
            }
            const tApproach = 0.35, tClimb = climbH / rate;
            const total = tApproach + tClimb;
            const u1 = tApproach / total;
            const path = [
                { u: 0,  x: cur.x,               y: feetY,          z: cur.z },
                { u: u1, x: cur.x + fx * faceD,  y: feetY,          z: cur.z + fz * faceD },
                { u: 1,  x: cur.x + fx * faceD,  y: feetY + climbH, z: cur.z + fz * faceD, ease: 'linear' },
            ];
            // Hands/feet get a SUBTLE pull to the rung grid as she climbs
            // (each limb toward the rung nearest its animated position).
            const grab = {
                type: 'ladder', window: [u1 * 0.7, 0.98],
                fx, fz,
                // The RUNG plane — rungs protrude ~0.09 in front of the face.
                x: cur.x + fx * (faceStart - 0.09),
                z: cur.z + fz * (faceStart - 0.09),
                perpX: -fz, perpZ: fx,
                baseRungY: feetY + (opts.firstRung ?? 0.25),
                rungSpacing: opts.rungSpacing ?? 0.28,
                maxRung: Math.floor((height - 0.10) / (opts.rungSpacing ?? 0.28)),
            };
            const self = this;
            return this._startManeuver({
                type: 'ladder', slot: 'climbLadder',
                slotFallbacks: ['climbWallUp', 'climbLedge'],
                path, duration: total, landingGroundY: topY,
                loop: true, timeScale: opts.timeScale ?? 1,
                grab,
                chain: () => {
                    const b = self.body.translation();
                    const fY = b.y - self.halfHeight - self.hipY;
                    const chainOb = {
                        topY, rise: topY - fY,
                        startD: faceStart - faceD,
                        endD: faceStart - faceD + 0.5,
                    };
                    return self._startMountOnto(null, chainOb, fx, fz, 'climbLedge');
                },
            });
        }

        // Scramble up a TALL wall (no ladder) directly ahead: the
        // wall-climb cycle LOOPS while the trajectory rises, palms and
        // toes latching continuous holds on the face, then chains into
        // the ledge mantle at the top — the same composition as the
        // ladder, minus the rungs.
        climbWall(opts = {}) {
            if (this._maneuver) return false;
            const fx = Math.sin(this._heading), fz = Math.cos(this._heading);
            const scan = this._scanPathAhead(fx, fz);
            const { obstacle: ob } = this._classifyPathAhead(scan);
            if (!ob) {
                console.warn('[eidoverse-controller] climbWall: no wall ahead');
                return false;
            }
            return this._startWallScramble(scan, ob, fx, fz, opts);
        }

        _startWallScramble(scan, ob, fx, fz, opts = {}) {
            const cur = this.body.translation();
            const feetY = cur.y - this.halfHeight - this.hipY;
            const height = ob.rise;
            const faceStart = ob.startD;
            // Closer standoff than the ladder — the scramble clip's hands
            // reach at most ~0.45 m forward, and there are no protruding
            // rungs to meet them halfway; the cycle's body lean keeps the
            // head clear.
            const faceD = Math.max(0.06, faceStart - (this.radius + 0.20));
            const topY = ob.topY;
            const rate = opts.rate ?? 0.34;      // m/s — the cycle gains ~0.5 m per 2 s
            const mantleH = Math.min(height, 1.35);
            const climbH = Math.max(0, height - mantleH);
            if (climbH < 0.05) return this._startMountOnto(scan, ob, fx, fz, 'climbLedge');
            const tApproach = 0.35, tClimb = climbH / rate;
            const total = tApproach + tClimb;
            const u1 = tApproach / total;
            const path = [
                { u: 0,  x: cur.x, y: feetY, z: cur.z },
                { u: u1, x: cur.x + fx * faceD, y: feetY, z: cur.z + fz * faceD },
                { u: 1,  x: cur.x + fx * faceD, y: feetY + climbH, z: cur.z + fz * faceD, ease: 'linear' },
            ];
            // Contact = the wall FACE plane itself: no rungSpacing, so the
            // climb-face IK latches continuous palm/toe holds on the plane.
            const grab = {
                type: 'ladder', window: [u1 * 0.7, 0.98],
                fx, fz,
                x: cur.x + fx * faceStart,
                z: cur.z + fz * faceStart,
                perpX: -fz, perpZ: fx,
            };
            const self = this;
            return this._startManeuver({
                type: 'wallScramble', slot: 'climbWallUp',
                slotFallbacks: ['climbLadder', 'climbLedge'],
                path, duration: total, landingGroundY: topY,
                loop: true, timeScale: opts.timeScale ?? 1.1,
                grab,
                chain: () => {
                    const b = self.body.translation();
                    const fY = b.y - self.halfHeight - self.hipY;
                    const chainOb = {
                        topY, rise: topY - fY,
                        startD: faceStart - faceD,
                        endD: faceStart - faceD + 0.5,
                    };
                    return self._startMountOnto(null, chainOb, fx, fz, 'climbLedge');
                },
            });
        }

        _startManeuver(spec) {
            const slots = [spec.slot, ...(spec.slotFallbacks || [])];
            let action = null, usedSlot = null;
            for (const s of slots) {
                if (this._actions?.[s]) { action = this._actions[s]; usedSlot = s; break; }
            }
            if (!action) {
                console.warn(`[eidoverse-controller] maneuver '${spec.type}' skipped — clip '${spec.slot}' not loaded`);
                return false;
            }
            const clipDur = action.getClip().duration || 1;
            let duration;
            if (spec.duration === 'clip') {
                // Follow the clip's native length (clamped) — timeScale ≈ 1,
                // the animation plays as authored.
                const cl = spec.durationClamp ?? [0.5, 3.0];
                duration = Math.max(cl[0], Math.min(cl[1], clipDur));
            } else {
                duration = spec.duration ?? Math.min(1.25, clipDur);
            }
            action.reset();
            // One-shots complete exactly over the trajectory; loop specs
            // (ladder) cycle at their own pace while the trajectory runs.
            // clipWindow plays only [c0,c1] of the clip across the maneuver
            // (trailing frames continue under the post-maneuver fade — a
            // natural follow-through).
            const [c0, c1] = spec.clipWindow ?? [0, 1];
            // The SPEC decides looping, not the slot's load-time default —
            // a cyclic clip (the wall-scramble) can serve a looped maneuver
            // even though it loads as a one-shot for mounts.
            action.setLoop(spec.loop ? globalThis.THREE.LoopRepeat : globalThis.THREE.LoopOnce, Infinity);
            action.clampWhenFinished = !spec.loop;
            action.timeScale = spec.loop ? (spec.timeScale ?? 1) : ((c1 - c0) * clipDur / duration);
            action.play();
            if (c0 > 0) action.time = c0 * clipDur;
            // A maneuver owns the whole body — any active gesture ends here
            // (not just fades for the flight: without clearing it, the
            // gesture ramps right back up when the maneuver completes).
            this._activeGesture = null;
            this._maneuver = { ...spec, slot: usedSlot, duration, t: 0, action };
            this._blockedFrames = 0;
            this._fadingManeuverAction = null;
            console.log(`[eidoverse-controller] maneuver ${spec.type} (${usedSlot}) dur=${duration.toFixed(2)}s`);
            return true;
        }

        // Piecewise keypoint path. Horizontal progress is linear within a
        // leg; vertical uses ease-out rising / ease-in falling, which
        // approximates ballistic arcs without stalling horizontal motion
        // at the apex keypoint.
        _sampleManeuverPath(path, u) {
            if (u <= path[0].u) return path[0];
            for (let i = 1; i < path.length; i++) {
                if (u <= path[i].u) {
                    const a = path[i - 1], b = path[i];
                    const t = (u - a.u) / Math.max(1e-6, b.u - a.u);
                    // Destination keypoint may pin its own vertical easing
                    // (ladders climb at constant rate → 'linear').
                    const ts = b.ease === 'linear' ? t
                        : (b.y >= a.y) ? (1 - (1 - t) * (1 - t)) : (t * t);
                    return {
                        x: a.x + (b.x - a.x) * t,
                        y: a.y + (b.y - a.y) * ts,
                        z: a.z + (b.z - a.z) * t,
                    };
                }
            }
            return path[path.length - 1];
        }

        // ── Maneuver HAND IK ──────────────────────────────────────────
        // During climbs/vaults the hands reach for the actual geometry —
        // the ledge lip, the vault plant point, the ladder rungs — via a
        // two-bone (upperArm/lowerArm/hand) cosine-rule solve, blended
        // over the clip's arm pose by a windowed weight. Same math as the
        // foot IK's FootsPlacement, arm-shaped.
        _applyWorldDeltaToBoneCC(bone, worldDelta) {
            const THREE = globalThis.THREE;
            const parent = bone.parent;
            if (!parent) { bone.quaternion.premultiply(worldDelta); return; }
            const parentQ = new THREE.Quaternion();
            parent.getWorldQuaternion(parentQ);
            const parentQInv = parentQ.clone().invert();
            const localDelta = parentQInv.clone().multiply(worldDelta).multiply(parentQ);
            bone.quaternion.premultiply(localDelta);
        }

        // Reference pattern (adaptive-parkour): IK targets come from the
        // GEOMETRY nearest to where the ANIMATION already put the limb, and
        // are lerped per frame — the clip drives, the solve corrects onto
        // the real surface. Targets are smoothed per limb key so rung/lip
        // switches don't snap.
        _smoothLimbTarget(m, key, target, lerp = 0.4) {
            const THREE = globalThis.THREE;
            if (!m._limbTargets) m._limbTargets = {};
            const prev = m._limbTargets[key];
            if (!prev) {
                m._limbTargets[key] = target.clone();
            } else {
                prev.lerp(target, lerp);
                m._limbTargets[key] = prev;
            }
            return m._limbTargets[key];
        }

        _solveArmIK(side, target, w) {
            this._solveLimbIK(side + 'UpperArm', side + 'LowerArm', side + 'Hand', target, w);
        }

        _solveLegIK(side, target, w) {
            this._solveLimbIK(side + 'UpperLeg', side + 'LowerLeg', side + 'Foot', target, w);
        }

        _solveLimbIK(upName, midName, endName, target, w) {
            const THREE = globalThis.THREE;
            const h = this.vrm?.humanoid;
            if (!h || w <= 0.01) return;
            const up  = h.getNormalizedBoneNode(upName);
            const mid = h.getNormalizedBoneNode(midName);
            const end = h.getNormalizedBoneNode(endName);
            if (!up || !mid || !end) return;
            const upQ0 = up.quaternion.clone(), midQ0 = mid.quaternion.clone();
            this.vrm.scene.updateMatrixWorld(true);
            const a = up.getWorldPosition(new THREE.Vector3());
            const b = mid.getWorldPosition(new THREE.Vector3());
            const c = end.getWorldPosition(new THREE.Vector3());
            // A target closer to the limb root than a fist-length means the
            // solve would fold the limb back through the body — skip.
            if (a.distanceTo(target) < 0.18) return;
            const lu = a.distanceTo(b), ll = b.distanceTo(c);
            const dist = Math.min(
                Math.max(a.distanceTo(target), Math.abs(lu - ll) + 0.01),
                lu + ll - 0.005,
            );
            // Elbow bend from the law of cosines, applied about the arm's
            // CURRENT bend plane (keeps the clip's natural elbow direction).
            const cosMid = (lu * lu + ll * ll - dist * dist) / (2 * lu * ll);
            const desired = Math.acos(Math.max(-1, Math.min(1, cosMid)));
            const vBA = a.clone().sub(b), vBC = c.clone().sub(b);
            const current = vBA.angleTo(vBC);
            const axis = new THREE.Vector3().crossVectors(vBC, vBA);
            if (axis.lengthSq() > 1e-8) {
                axis.normalize();
                this._applyWorldDeltaToBoneCC(
                    mid, new THREE.Quaternion().setFromAxisAngle(axis, current - desired));
            }
            this.vrm.scene.updateMatrixWorld(true);
            const c2 = end.getWorldPosition(new THREE.Vector3());
            const upDelta = new THREE.Quaternion().setFromUnitVectors(
                c2.clone().sub(a).normalize(),
                target.clone().sub(a).normalize(),
            );
            this._applyWorldDeltaToBoneCC(up, upDelta);
            // Blend the solved pose over the clip's arms by w.
            up.quaternion.copy(upQ0.clone().slerp(up.quaternion.clone(), w));
            mid.quaternion.copy(midQ0.clone().slerp(mid.quaternion.clone(), w));
        }

        _applyManeuverHandIK(m, u) {
            const THREE = globalThis.THREE;
            const g = m.grab;
            if (!g) return;
            const h = this.vrm?.humanoid;
            const boneWorld = (name) => {
                const n = h?.getNormalizedBoneNode?.(name);
                return n ? n.getWorldPosition(new THREE.Vector3()) : null;
            };
            // Weight philosophy (same as the foot IK): the CLIP drives the
            // limb's motion; the solve only pulls the contact point onto the
            // geometry, at partial weight. Full-weight fixed targets override
            // the animated swing entirely — arms wrench across the torso and
            // freeze there.
            const ramp = (a, b, maxW) => {
                if (u < a || u > b) return 0;
                const p = (u - a) / Math.max(1e-6, b - a);
                return Math.min(maxW, Math.sin(Math.PI * p) * maxW * 1.6);
            };
            // Lateral component of the ANIMATED limb along the surface —
            // the clip keeps its swing; only depth/height pin to geometry.
            const latOf = (p, cx, cz, clampLat) => {
                const raw = (p.x - cx) * g.perpX + (p.z - cz) * g.perpZ;
                return Math.max(-clampLat, Math.min(clampLat, raw));
            };
            const [w0, w1] = g.window;
            if (u < w0 || u > w1) return;
            const sm = (a, b, v) => Math.min(1, Math.max(0, (v - a) / (b - a)));
            if (g.type === 'climb') {
                // ONE-SIDED correction (the IK's job is to push limbs OUT of
                // surfaces, not to drag them around) + one deliberate
                // contact: the lip GRAB while the body hangs below the top.
                const feetNow = m._curFeetY ?? (this.body.translation().y - this.halfHeight - this.hipY);
                const toTop = g.topY - feetNow;
                for (const side of ['left', 'right']) {
                    const hp = boneWorld(side + 'Hand');
                    if (!hp) continue;
                    const along = (hp.x - g.lipX) * g.fx + (hp.z - g.lipZ) * g.fz;
                    if (hp.y < g.topY + 0.01 && hp.y > g.topY - 0.50 && along > -0.10) {
                        // The TOP PLANE is a hard floor for the hands, from
                        // the grab through the crouch: any hand the clip
                        // sweeps below it plants ON the surface — never down
                        // the face — so the body visibly rises over planted
                        // hands (the pull-up). Weight scales with penetration
                        // depth toward full: a partial blend of a half-metre
                        // sweep still reads as sunk-in-the-mesh.
                        const depth = g.topY + 0.01 - hp.y;
                        const lat = latOf(hp, g.lipX, g.lipZ, 0.35);
                        const alongTop = Math.max(0.10, Math.min(0.45, along));
                        const tgt = new THREE.Vector3(
                            g.lipX + g.perpX * lat + g.fx * alongTop, g.topY + 0.02,
                            g.lipZ + g.perpZ * lat + g.fz * alongTop);
                        this._solveArmIK(side, this._smoothLimbTarget(m, side + 'HandClimb', tgt, 0.7),
                            Math.min(0.98, 0.25 + depth * 4.5));
                    } else if (hp.y < g.topY - 0.06 && along > -0.02) {
                        // Deep in the wall FACE while climbing → push out.
                        const lat = latOf(hp, g.lipX, g.lipZ, 0.40);
                        const tgt = new THREE.Vector3(
                            g.lipX + g.perpX * lat - g.fx * 0.04, hp.y,
                            g.lipZ + g.perpZ * lat - g.fz * 0.04);
                        this._solveArmIK(side, this._smoothLimbTarget(m, side + 'HandClimb', tgt, 0.7), 0.90);
                    } else if (hp.y >= g.topY - 0.28 && toTop > 0.45 && toTop < 1.10) {
                        // GRAB: hand near the lip, body hanging below → pull
                        // onto the lip line (lateral follows the clip).
                        const near = sm(g.topY - 0.28, g.topY - 0.10, hp.y);
                        const lat = latOf(hp, g.lipX, g.lipZ, 0.32);
                        const tgt = new THREE.Vector3(
                            g.lipX + g.perpX * lat, g.topY + 0.02, g.lipZ + g.perpZ * lat);
                        this._solveArmIK(side, this._smoothLimbTarget(m, side + 'HandClimb', tgt), 0.60 * near);
                    }
                }
                for (const side of ['left', 'right']) {
                    const fp = boneWorld(side + 'Foot');
                    if (!fp) continue;
                    const alongF = (fp.x - g.lipX) * g.fx + (fp.z - g.lipZ) * g.fz;
                    if (toTop <= 0.55 && fp.y > g.topY - 0.45 && fp.y < g.topY + 0.02 && alongF > -0.35) {
                        // MANTLE: the stepping foot lands ON the top surface.
                        // Catch it while it is still in FRONT of the face (the
                        // old along>0 gate let the kick punch into the wall
                        // side before any correction) and eject up with
                        // depth-scaled weight — zero force at the surface, so
                        // the settled end-crouch feet are left to the clip.
                        const depth = g.topY + 0.02 - fp.y;
                        const lat = latOf(fp, g.lipX, g.lipZ, 0.30);
                        const alongTop = Math.max(0.15, alongF);
                        const tgt = new THREE.Vector3(
                            g.lipX + g.perpX * lat + g.fx * alongTop, g.topY + 0.02,
                            g.lipZ + g.perpZ * lat + g.fz * alongTop);
                        this._solveLegIK(side, this._smoothLimbTarget(m, side + 'FootClimb', tgt, 0.7),
                            Math.min(0.97, depth * 7.0));
                    } else if (fp.y < g.topY - 0.05 && alongF > 0.00) {
                        // Foot inside the wall face (climb phase or a deep
                        // trailing leg) → push OUT, depth-scaled.
                        const lat = latOf(fp, g.lipX, g.lipZ, 0.30);
                        const tgt = new THREE.Vector3(
                            g.lipX + g.perpX * lat - g.fx * 0.06, fp.y,
                            g.lipZ + g.perpZ * lat - g.fz * 0.06);
                        this._solveLegIK(side, this._smoothLimbTarget(m, side + 'FootClimb', tgt, 0.7),
                            Math.min(0.95, 0.60 + Math.min(0.35, alongF) * 1.5));
                    }
                }
            } else if (g.type === 'vaultGeo') {
                // The clip owns the vault; IK adds the visible PROP — ONE
                // hand plants on the obstacle top and stays committed
                // through the crossing (the body pushes over it), plus foot
                // clearance out of the obstacle. Nothing else.
                if (u > 0.12 && u < 0.68) {
                    // Pick the prop hand once (the one nearer the plant
                    // line) and keep it — per-frame switching flickers.
                    if (!m._propSide) {
                        let best = null, bestD = Infinity;
                        for (const side of ['left', 'right']) {
                            const hp = boneWorld(side + 'Hand');
                            if (!hp) continue;
                            const d = Math.hypot(hp.x - g.px, hp.z - g.pz);
                            if (d < bestD) { bestD = d; best = side; }
                        }
                        m._propSide = best;
                    }
                    const side = m._propSide;
                    const hp = side && boneWorld(side + 'Hand');
                    if (hp) {
                        const sh = boneWorld(side + 'UpperArm') ?? hp;
                        const lat = latOf(hp, g.px, g.pz, 0.32);
                        const tgt = new THREE.Vector3(
                            g.px + g.perpX * lat, g.topY + 0.02, g.pz + g.perpZ * lat);
                        // Soft distance ramp — a straight arm reaching for
                        // the surface reads as the prop even before contact;
                        // no hard reach cutoff.
                        const w = 0.85 * sm(1.20, 0.85, sh.distanceTo(tgt));
                        if (w > 0.02) this._solveArmIK(side, this._smoothLimbTarget(m, side + 'HandVault', tgt), w);
                    }
                }
                for (const side of ['left', 'right']) {
                    const fp = boneWorld(side + 'Foot');
                    if (fp) {
                        const along = (fp.x - g.ox) * g.fx + (fp.z - g.oz) * g.fz;
                        if (along > g.d0 - 0.05 && along < g.d1 + 0.05 && fp.y < g.topY + 0.04) {
                            this._solveLegIK(side, this._smoothLimbTarget(m, side + 'FootVault',
                                new THREE.Vector3(fp.x, g.topY + 0.07, fp.z)), 0.85);
                        }
                    }
                }
            } else if (g.type === 'ladder') {
                // Climb-face contact — the clip owns the climb. With
                // `rungSpacing` set (a real ladder) limbs GRIP discrete
                // rungs; without it (a flat wall scramble) palms and toes
                // latch continuous holds on the face plane. Either way a
                // limb beyond the plane is pushed back out at
                // penetration-scaled strength, and one approaching it is
                // pulled onto its hold. Limbs swinging freely are left
                // alone.
                const wGate = ramp(w0, w1, 1.0);
                if (wGate <= 0.01) return;
                const spacing = g.rungSpacing;
                const rungY = (y, lo, hi) => {
                    const k = Math.max(lo, Math.min(hi,
                        Math.round((y - g.baseRungY) / spacing)));
                    return g.baseRungY + k * spacing;
                };
                const maxR = g.maxRung ?? 99;
                const alongOf = (p) => (p.x - g.x) * g.fx + (p.z - g.z) * g.fz;
                for (const side of ['left', 'right']) {
                    const hp = boneWorld(side + 'Hand');
                    if (hp) {
                        const along = alongOf(hp);
                        // GRIP, not just ejection: as the animated hand
                        // approaches the rung plane it is pulled onto the
                        // nearest rung (the clip keeps its timing and
                        // lateral swing); beyond the plane the pull becomes
                        // a penetration-scaled push back out. Weights meet
                        // at the plane, so contact is seamless.
                        const nearLo = spacing ? -0.26 : -0.42;
                        let w = 0;
                        if (along > 0.0) w = Math.min(0.95, 0.65 + along * 2.5);
                        else if (along > nearLo) w = 0.65 * sm(nearLo, -0.05, along);
                        if (w > 0.02) {
                            // Latch the hold: a gripped hand KEEPS its hold
                            // while the body rises, and only re-targets
                            // during its swing phase (clear of the plane) —
                            // discrete regrips instead of sliding up
                            // mid-grip. Forced re-grip when the body
                            // outruns the hold.
                            const key = side + 'RungK';
                            let hy;
                            if (spacing) {
                                const kPref = Math.round((hp.y + 0.05 - g.baseRungY) / spacing);
                                let k = m[key];
                                if (k == null || (along < -0.10 && kPref !== k) ||
                                    kPref - k >= 2) k = kPref;
                                k = Math.max(1, Math.min(maxR, k));
                                m[key] = k;
                                hy = g.baseRungY + k * spacing;
                            } else {
                                // Flat face: the palm latches its own height
                                // at grip entry and holds it there.
                                let held = m[key];
                                if (held == null || along < -0.10) held = hp.y + 0.02;
                                else if (hp.y - held > 0.55) held = hp.y - 0.10;
                                m[key] = held;
                                hy = held;
                            }
                            const lat = latOf(hp, g.x, g.z, 0.24);
                            // Rest ON the rung — a touch in FRONT of the
                            // plane, so residual blend never leaves the hand
                            // behind it at the wall.
                            const tgt = new THREE.Vector3(
                                g.x + g.perpX * lat - g.fx * 0.02, hy,
                                g.z + g.perpZ * lat - g.fz * 0.02);
                            this._solveArmIK(side, this._smoothLimbTarget(m, side + 'Hand', tgt, 0.55), w * wGate);
                        }
                    }
                    const fp = boneWorld(side + 'Foot');
                    if (fp) {
                        const along = alongOf(fp);
                        const nearLoF = spacing ? -0.22 : -0.38;
                        let w = 0;
                        if (along > 0.0) w = Math.min(0.95, 0.65 + along * 2.5);
                        else if (along > nearLoF) w = 0.60 * sm(nearLoF, -0.05, along);
                        if (w > 0.02) {
                            const key = side + 'FootRungK';
                            let fy;
                            if (spacing) {
                                const kPref = Math.round((fp.y - g.baseRungY) / spacing);
                                let k = m[key];
                                if (k == null || (along < -0.10 && kPref !== k) ||
                                    kPref - k >= 2) k = kPref;
                                k = Math.max(0, Math.min(maxR - 3, k));
                                m[key] = k;
                                fy = g.baseRungY + k * spacing;
                            } else {
                                let held = m[key];
                                if (held == null || along < -0.10) held = fp.y;
                                else if (fp.y - held > 0.50) held = fp.y - 0.10;
                                m[key] = held;
                                fy = held;
                            }
                            const lat = latOf(fp, g.x, g.z, 0.15);
                            const tgt = new THREE.Vector3(
                                g.x + g.perpX * lat - g.fx * 0.02, fy + 0.03,
                                g.z + g.perpZ * lat - g.fz * 0.02);
                            this._solveLegIK(side, this._smoothLimbTarget(m, side + 'Foot', tgt, 0.55), w * wGate);
                        }
                    }
                }
            }
        }

        _updateManeuver(dt) {
            const THREE = globalThis.THREE;
            const m = this._maneuver;
            m.t += dt;
            const u = Math.min(1, m.t / m.duration);
            if (m.path) {
                const p = this._sampleManeuverPath(m.path, u);
                m._curFeetY = p.y;
                this.body.setNextKinematicTranslation({
                    x: p.x, y: p.y + this.hipY + this.halfHeight, z: p.z,
                });
                this.world.step();
                const t2 = this.body.translation();
                const dxA = t2.x - this._lastX, dzA = t2.z - this._lastZ;
                this.speedActual = Math.hypot(dxA, dzA) / dt;
                this._lastX = t2.x; this._lastZ = t2.z;
                this._feetWorld.set(t2.x, t2.y - this.halfHeight - this.hipY - this.vrmFootY, t2.z);
                this.grounded = true;
                this._velocityY = 0;
                this._airborneFromY = null;
            } else {
                // Landing recovery — grounded physics with zero input; the
                // recovery clip owns the pose while the body settles.
                this.update(dt, { x: 0, z: 0 });
            }
            for (const a of Object.values(this._actions || {})) {
                if (!a) continue;
                a.weight = THREE.MathUtils.damp(a.weight, a === m.action ? 1 : 0, 14, dt);
            }
            // Maneuvers own the whole body — gestures fade out for the flight.
            this._updateGestureWeights(dt, true);
            if (this._mixer) this._mixer.update(dt);
            const vrm = this.vrm;
            if (vrm?.scene) {
                vrm.scene.position.copy(this.feetWorldPosition);
                vrm.scene.rotation.y = this._turningEnabled ? this._heading : Math.PI;
                // End-crouch visual sink (see the mount spec) — root drops so
                // the crouch pose's tucked feet stay planted on the surface.
                if (m.visualSink) {
                    const vs = m.visualSink;
                    const k = Math.min(1, Math.max(0, (u - vs.u0) / Math.max(1e-6, vs.u1 - vs.u0)));
                    m._sinkNow = vs.amount * (k * k * (3 - 2 * k));
                    vrm.scene.position.y -= m._sinkNow;
                }
            }
            // Hands reach the geometry (ledge lip / plant point / rungs).
            this._applyManeuverHandIK(m, u);
            this.supportFrame = {
                dt,
                maneuver: { type: m.type, slot: m.slot, u: +u.toFixed(3), duration: m.duration },
                body: { supportMode: 'maneuver:' + m.type },
                probes: null,
                terrain: { mode: 'maneuver:' + m.type },
                animation: null,
            };
            this.externalGroundY = null;
            if (u >= 1) {
                if (m.chain) {
                    // Chained maneuver (ladder → mantle): the next move takes
                    // over seamlessly; this one's clip fades under it.
                    this._maneuver = null;
                    this._fadingManeuverAction = m.action;
                    let ok = false;
                    try { ok = m.chain(); }
                    catch (e) { console.warn('[eidoverse-controller] chained maneuver failed:', e.message); }
                    if (!ok) { this._maneuver = m; this._endManeuver(); }
                } else {
                    this._endManeuver();
                }
            }
        }

        _endManeuver() {
            const m = this._maneuver;
            this._maneuver = null;
            this._maneuverCooldownT = this.maneuverCooldown;
            this._fadingManeuverAction = m.action;
            // Carry the end-crouch visual sink into locomotion, where it
            // fades in lockstep with the clip's weight — the feet stay on
            // the surface through the whole crouch-to-stand.
            this._maneuverVisualSink = m._sinkNow ?? 0;
            if (m.path && m.landingGroundY !== undefined && m.landingGroundY !== null) {
                this._bodyYTarget = m.landingGroundY + this.hipY + this.halfHeight;
                this._yAvgWindow.length = 0;
                this._lastValidGroundY = m.landingGroundY;
                this._groundStaleFrames = 0;
                this._velocityY = 0;
                this._lastBodyY = null;
                this.groundY = m.landingGroundY;
                this.grounded = true;
            }
            this._airborneFromY = null;
            this._airborneTime = 0;
            console.log(`[eidoverse-controller] maneuver ${m.type} complete`);
        }
    }

    globalThis.VRMCharacterController = VRMCharacterController;
    console.log('[eidoverse-controller] VRMCharacterController class registered on globalThis');
})();
