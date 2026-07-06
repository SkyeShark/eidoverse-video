// VRMFootControllerIK — raycast foot-planting IK for VRM characters in the
// Three.js + Rapier environment. Per frame (after mixer.update): sample the
// ground under each animated foot with a low ray + a toe ray, choose the
// support surface, conform the foot to the surface normal, smooth against
// last-frame state, and solve the leg with cosine-rule two-bone IK
// (pole vector + fixKnee). Fully self-contained — no external solver.

(function() {
    if (typeof THREE === 'undefined') {
        console.warn('[foot-ik] THREE not present');
        return;
    }

    const MAX_DISTANCE_POWER = 2;
    const MAX_SMOOTHING_ANGLE = 3;
    const SMOOTHING_POWER = 1;
    const MAX_STEP_HEIGHT = 2;
    const HEIGHT_OFFSET = 0.5;
    const RAD2DEG = 180 / Math.PI;
    const DEG2RAD = Math.PI / 180;
    // Min normal.y for a surface to count as "walkable ground" (not a
    // wall or edge). Default 0.7. Below this, raycast hits on stair
    // risers / steep slopes are rejected and we fall back to spherecast
    // to find the nearby tread surface.
    const NormalUpThreshold = 0.7;

    // ────────────────────────────────────────────────────────────────
    // Limb — per-leg state container.
    // Holds bone refs, precomputed lengths, cosine-rule constants,
    // and per-frame IK target + last-frame state for smoothing.
    // ────────────────────────────────────────────────────────────────
    class Limb {
        constructor(upBone, middleBone, lowBone, extraBone) {
            this.UpBone     = upBone;       // thigh
            this.MiddleBone = middleBone;   // knee
            this.LowBone    = lowBone;      // foot (ankle)
            this.ExtraBone  = extraBone || null;  // toe (optional)

            const tmpA = new THREE.Vector3();
            const tmpB = new THREE.Vector3();
            const tmpC = new THREE.Vector3();
            upBone.getWorldPosition(tmpA);
            middleBone.getWorldPosition(tmpB);
            lowBone.getWorldPosition(tmpC);

            this.UpperLength = tmpA.distanceTo(tmpB);
            this.LowerLength = tmpB.distanceTo(tmpC);
            this.ExtraLength = 0;
            if (this.ExtraBone) {
                const tmpE = new THREE.Vector3();
                extraBone.getWorldPosition(tmpE);
                this.ExtraLength = tmpC.distanceTo(tmpE);
            }
            this.Length = this.UpperLength + this.LowerLength + this.ExtraLength;

            this.UpperLengthSquared = this.UpperLength * this.UpperLength;
            this.LowerLengthSquared = this.LowerLength * this.LowerLength;
            this.CosineRuleNumeratorPart = this.UpperLengthSquared + this.LowerLengthSquared;
            this.CosineRuleDenominator = 2 * this.UpperLength * this.LowerLength;

            this.distanceFromMesh = 0;  // set externally during Initiation

            // Per-frame IK output
            this.targetPosition = new THREE.Vector3();
            this.targetRotation = new THREE.Quaternion();

            // Smoothing state
            this.lastLowBonePosition = new THREE.Vector3().copy(tmpC);
            this.lastLowBoneRotation = new THREE.Quaternion();
            this.lastMiddleBoneRotation = new THREE.Quaternion();
            this.lastUpBoneRotation = new THREE.Quaternion();
            this.lastLowBoneAnimationPosition = new THREE.Vector3().copy(tmpC);
            this.lastLowBoneAnimationRotation = new THREE.Quaternion();
            lowBone.getWorldQuaternion(this.lastLowBoneAnimationRotation);

            this.canReachTarget = false;
            this.LowestHitPoint = new THREE.Vector3();
            this._animatorWeight = 0;

            // Per-leg running min(upY) — used during descent to subtract the
            // anim's baseline drift (Mixamo descent anim floats the foot
            // bone ~0.08–0.50m above bind, never actually planting at 0).
            // Subtracting running min recovers swing-arc-above-stride-floor.
            this._minUpY = Infinity;

            // Swing-arc phase tracking (RifeWithKaiju feedback 2026-05-13).
            // Each foot has a binary inSwing flag (set by comparing FK foot Y
            // to the other foot at the top of FootIK) and a phase counter
            // that advances over swingDuration, then resets when the foot
            // plants again. The synthetic lift fed back into upY is
            // peakHeight * sin(phase * π).
            this._inSwing = false;
            this._swingPhase = 0;
            this._syntheticLift = 0;
            this._lastStepClearanceHitY = null;
            this._stepClearanceDropPhase = 1;
        }

        get LowBonePosition() {
            const v = new THREE.Vector3();
            this.LowBone.getWorldPosition(v);
            return v;
        }
        get LowBoneRotation() {
            const q = new THREE.Quaternion();
            this.LowBone.getWorldQuaternion(q);
            return q;
        }
        set LowBoneRotation(q) {
            // Set world rotation on the LowBone (foot).
            // Convert to local via parent.
            const parent = this.LowBone.parent;
            if (!parent) { this.LowBone.quaternion.copy(q); return; }
            const parentQ = new THREE.Quaternion();
            parent.getWorldQuaternion(parentQ);
            this.LowBone.quaternion.copy(parentQ.invert().multiply(q));
        }

        // Cosine rule helpers
        MiddleBoneAngle(targetDistance) {
            const c = (this.CosineRuleNumeratorPart - targetDistance * targetDistance) / this.CosineRuleDenominator;
            return Math.acos(Math.max(-1, Math.min(1, c))) * RAD2DEG;
        }
        LowerBoneAngle(targetDistance) {
            const c = (targetDistance * targetDistance + this.LowerLengthSquared - this.UpperLengthSquared)
                    / (2 * targetDistance * this.LowerLength);
            return Math.acos(Math.max(-1, Math.min(1, c))) * RAD2DEG;
        }
        UpperBoneAngle(targetDistance) {
            const c = (targetDistance * targetDistance + this.UpperLengthSquared - this.LowerLengthSquared)
                    / (2 * targetDistance * this.UpperLength);
            return Math.acos(Math.max(-1, Math.min(1, c))) * RAD2DEG;
        }
    }

    // ────────────────────────────────────────────────────────────────
    // FootControllerIK — the foot-planting solver
    // ────────────────────────────────────────────────────────────────
    const CastType = Object.freeze({ Ray: 0, Sphere: 1, RayAndSphere: 2 });
    const RotationType = Object.freeze({ RawTarget: 0, AddTarget: 1, Direction: 2, Animator: 3 });

    class VRMFootControllerIK {
        constructor(vrm, opts) {
            opts = opts || {};
            this.opts = opts;

            // Public fields (defaults from prefab: increasedAccuracy=1, fixKnee=1,
            // MaxStep=0.6, DistancePower=1, SmoothingAngle=2, GlobalSmoothingPower=0,
            // type=Ray, sphereRadius=0.03, rotationType=RawTarget)
            this.outsideUpdate     = opts.outsideUpdate     ?? false;
            this.increasedAccuracy = opts.increasedAccuracy ?? true;
            this.fixKnee           = opts.fixKnee           ?? true;
            this.footConstraint    = opts.footConstraint    ?? false;
            this.m_MaxStepHeight   = opts.MaxStepHeight     ?? 0.6;
            this.m_FootHeightOffset = opts.FootHeightOffset ?? 0;
            this.leftEnabled       = opts.leftEnabled       ?? true;
            this.rightEnabled      = opts.rightEnabled      ?? true;
            this.m_DistancePower   = opts.DistancePower     ?? 1;
            this.m_SmoothingAngle  = opts.SmoothingAngle    ?? 2;
            this.m_GlobalSmoothingPower = opts.GlobalSmoothingPower ?? 0;
            this.type              = opts.type              ?? CastType.Ray;
            this.sphereRadius      = opts.sphereRadius      ?? 0.03;
            this.rotationType      = opts.rotationType      ?? RotationType.RawTarget;

            // Swing-arc lift (per RifeWithKaiju feedback 2026-05-13):
            // when a foot is in swing phase, force a minimum sinusoidal lift
            // so the stride has a visible foot-arc even when the anim itself
            // barely lifts the foot. The arc is "cut short by the ground"
            // naturally because we take max(animUpY, syntheticLift).
            this.swingArcHeight    = opts.swingArcHeight    ?? 0.20;  // 20 cm peak
            this.swingDuration     = opts.swingDuration     ?? 0.40;  // s per swing
            this.swingDetectThreshold = opts.swingDetectThreshold ?? 0.005;  // 5 mm
            this.stepClearanceArcHeight = opts.stepClearanceArcHeight ?? 0.12;
            this.stepClearanceDropMin = opts.stepClearanceDropMin ?? 0.035;
            this.stepClearanceDropMax = opts.stepClearanceDropMax ?? 0.24;
            this.stepClearanceDropLift = opts.stepClearanceDropLift ?? 0.07;
            this.stepClearanceDropDuration = opts.stepClearanceDropDuration ?? 0.22;
            this.stepClearanceContext = false;
            this.rampFootClearanceOffset = 0;
            this._debugSwing       = opts.debugSwing        ?? false;

            // Foot-plant forward offset — when set externally, shifts the
            // foot raycast origin forward along the foot's toe direction
            // by `footPlantForwardOffset × ExtraLength` (ankle→toe length).
            // Used on stairs so the foot mesh lands with the heel ON the
            // tread instead of dangling off the back edge. Anatomically
            // adaptive (derives from rig's own ankle→toe length), no
            // hardcoded geometry. Default 0 = no offset (flat ground).
            this.footPlantForwardOffset = opts.footPlantForwardOffset ?? 0;
            this.stairAscentSoleFitContext = false;
            this.stairAscentTreadRun = null;
            this.stairAscentHeelProbeScale = opts.stairAscentHeelProbeScale ?? 0.90;
            this.stairAscentToeProbeScale = opts.stairAscentToeProbeScale ?? 0.95;
            this.stairAscentSoleFitTolerance = opts.stairAscentSoleFitTolerance ?? 0.025;
            this.stairAscentSoleFitUpYMax = opts.stairAscentSoleFitUpYMax ?? 0.14;
            this.stairAscentSoleFitStep = opts.stairAscentSoleFitStep ?? 0.012;
            this.stairAscentSoleFitMax = opts.stairAscentSoleFitMax ?? 0.14;
            this.stairAscentSoleFitTreadRunScale = opts.stairAscentSoleFitTreadRunScale ?? 0.45;
            this.stairAscentSoleFitExtraScale = opts.stairAscentSoleFitExtraScale ?? 1.05;
            this.stairAscentSoleFitMaxScale = 1;
            this.stairAscentOffsetScale = 1;
            this.stairAscentToeGuardRise = opts.stairAscentToeGuardRise ?? 0.085;
            this.stairAscentEdgeAlignContext = false;
            this.stairAscentEdgePoint = null;
            this.stairAscentMoveDir = null;
            this.stairAscentEdgeTreadRun = null;
            this.stairAscentEdgeRunMarginScale = opts.stairAscentEdgeRunMarginScale ?? 0.18;
            this.stairAscentEdgeFootMarginScale = opts.stairAscentEdgeFootMarginScale ?? 0.42;
            this.stairAscentEdgeMaxRunScale = opts.stairAscentEdgeMaxRunScale ?? 0.38;
            this.stairAscentEdgeMaxFootScale = opts.stairAscentEdgeMaxFootScale ?? 0.90;
            this.stairAscentEdgeToeReserveRunScale = opts.stairAscentEdgeToeReserveRunScale ?? 0.42;
            this.stairAscentEdgeToeReserveFootScale = opts.stairAscentEdgeToeReserveFootScale ?? 0.72;
            this.stairAscentEdgeMaxProgressRunScale = opts.stairAscentEdgeMaxProgressRunScale ?? 0.62;
            this.stairAscentEdgeMaxProgressFootReserveScale = opts.stairAscentEdgeMaxProgressFootReserveScale ?? 0.65;
            this.stairAscentEdgeBackMaxRunScale = opts.stairAscentEdgeBackMaxRunScale ?? 0.42;
            this.stairAscentEdgeBackMaxFootScale = opts.stairAscentEdgeBackMaxFootScale ?? 0.90;
            this.stairAscentEdgeTolerance = opts.stairAscentEdgeTolerance ?? 0.008;
            this.stairAscentEdgeUpYMax = opts.stairAscentEdgeUpYMax ?? 0.14;

            // ExtraBone (toe) cast reach scale. The toe bone sits ~0.15m
            // forward of the ankle for typical VRMs. On large-rise
            // short-run stairs (0.22m rise × 0.26m run), casting straight
            // down from the toe samples a surface 0.15m forward of the
            // ankle's surface — which can land on the NEXT tread up. With
            // reach=1.0 (full toe position), on flat-to-stairs approach
            // the toe is already over the FIRST riser top before the
            // ankle has reached the riser, but on continuous large stairs
            // the toe reaches past the back of the current tread onto
            // step 2 → foot anchors at step 2 from flat.
            // 0.5 = sample halfway between ankle and toe. Toe-anticipation
            // still works (next-tread-up gets sampled when foot is near
            // its edge) but doesn't reach 2 treads ahead.
            this.extraCastReachScale = opts.extraCastReachScale ?? 0.5;

            this.m_Incline = 0.85;
            this.m_InclineRadian = Math.acos(this.m_Incline);
            this.m_MinimalSmoothDistance = 0.005;
            this.m_MeshHeightOffset = 0;
            this.m_IsInitialized = false;

            // External integration (Rapier raycast + VRM bones)
            this.vrm = vrm;
            this.world = opts.world ?? null;
            this.RAPIER = opts.RAPIER ?? null;
            this.collider = opts.collider ?? null;
            this.rootObject = vrm.scene;

            // Reusable temps
            this._tmpV1 = new THREE.Vector3();
            this._tmpV2 = new THREE.Vector3();
            this._tmpV3 = new THREE.Vector3();
            this._tmpV4 = new THREE.Vector3();
            this._tmpV5 = new THREE.Vector3();
            this._tmpV6 = new THREE.Vector3();
            this._tmpQ1 = new THREE.Quaternion();
            this._tmpQ2 = new THREE.Quaternion();
            this._up = new THREE.Vector3(0, 1, 0);

            this.Initiation();
        }

        // Initiation() — bone discovery + rest-pose measurements
        Initiation() {
            if (this.m_IsInitialized) return;
            const h = this.vrm.humanoid;
            if (!h) throw new Error('[foot-ik] vrm.humanoid missing');

            const get = (name) => h.getNormalizedBoneNode(name);
            const leftUp    = get('leftUpperLeg');
            const leftMid   = get('leftLowerLeg');
            const leftFoot  = get('leftFoot');
            const leftToes  = get('leftToes');
            const rightUp   = get('rightUpperLeg');
            const rightMid  = get('rightLowerLeg');
            const rightFoot = get('rightFoot');
            const rightToes = get('rightToes');

            const haveToes = leftToes && rightToes;
            if (haveToes) {
                this.m_LeftLeg  = new Limb(leftUp,  leftMid,  leftFoot,  leftToes);
                this.m_RightLeg = new Limb(rightUp, rightMid, rightFoot, rightToes);
                // sphereRadius clamp from C# Initiation
                const leftHT = leftFoot.getWorldPosition(this._tmpV1).distanceTo(
                    leftMid.getWorldPosition(this._tmpV2));
                const rightHT = rightFoot.getWorldPosition(this._tmpV1).distanceTo(
                    rightMid.getWorldPosition(this._tmpV2));
                if (leftHT <= this.sphereRadius || rightHT <= this.sphereRadius) {
                    const useR = leftHT > rightHT ? rightHT / 3 : leftHT / 3;
                    this.sphereRadius = Math.max(0.01, useR);
                }
            } else {
                this.m_LeftLeg  = new Limb(leftUp,  leftMid,  leftFoot);
                this.m_RightLeg = new Limb(rightUp, rightMid, rightFoot);
            }

            // Mesh height offset — lowest point of the character mesh:
            // vrm bbox.min.y computed at init time. Caller supplies it via opts; else 0.
            this.m_MeshHeightOffset = this.opts?.meshHeightOffset ?? 0;

            const rootY = this.rootObject.position.y;
            const leftFootY  = leftFoot.getWorldPosition(this._tmpV1).y;
            const rightFootY = rightFoot.getWorldPosition(this._tmpV1).y;
            this.m_LeftLeg.distanceFromMesh  = (leftFootY  - rootY) - this.m_MeshHeightOffset;
            this.m_RightLeg.distanceFromMesh = (rightFootY - rootY) - this.m_MeshHeightOffset;

            this.m_IsInitialized = true;
        }

        get MaxStepHeight() { return this.m_MaxStepHeight; }
        set MaxStepHeight(v) { this.m_MaxStepHeight = Math.max(0, Math.min(MAX_STEP_HEIGHT, v)); }

        get LowestFootHeight() {
            if (this.m_LeftLeg.LowestHitPoint.y < this.m_RightLeg.LowestHitPoint.y)
                return this.m_LeftLeg.LowestHitPoint.y;
            return this.m_RightLeg.LowestHitPoint.y;
        }

        // Returns the HIGHER of the two feet's raycast hit Y. Used by the
        // character controller on steep descent: body Y should track the
        // planted (load-bearing) foot's tread, not the swing foot's
        // destination tread. Different from LowestFootHeight because feet
        // are raycast at the ACTUAL anim ankle XZ positions (one ahead,
        // one behind body), so they reliably sample different treads on
        // stairs — unlike the controller's body-XZ-based foot stance rays.
        get HighestFootHeight() {
            if (this.m_LeftLeg.LowestHitPoint.y > this.m_RightLeg.LowestHitPoint.y)
                return this.m_LeftLeg.LowestHitPoint.y;
            return this.m_RightLeg.LowestHitPoint.y;
        }

        get LowestFootPosition() {
            if (this.m_LeftLeg.LowestHitPoint.y < this.m_RightLeg.LowestHitPoint.y)
                return this.m_LeftLeg.LowestHitPoint.clone();
            return this.m_RightLeg.LowestHitPoint.clone();
        }

        DirectionalFootHeight(moveDirection) {
            const rootPos = this.rootObject.position;
            const left  = this.m_LeftLeg.LowBonePosition.sub(rootPos).dot(moveDirection);
            const right = this.m_RightLeg.LowBonePosition.sub(rootPos).dot(moveDirection);
            if (left > right) return this.m_LeftLeg.LowestHitPoint.clone();
            return this.m_RightLeg.LowestHitPoint.clone();
        }

        get CanReachTargets() {
            return this.m_LeftLeg.canReachTarget && this.m_RightLeg.canReachTarget;
        }

        // Per-leg swing-phase update — must be called BEFORE IK overrides
        // the foot bone positions. Reads pre-IK FK foot Y (which the anim
        // mixer just wrote this frame).
        //
        // Gating: synthetic lift is FLAT-WALK ONLY. On stairs the anim
        // already lifts feet sufficiently and the controller knows the
        // tread heights; adding synthetic lift produces unnatural
        // exaggerated motion that desyncs from anim cadence. The test
        // scene sets `ik.flatWalkContext = true` when walkAction dominates
        // (and false on stairs / falling / idle).
        //
        // Per-frame classification (simple, anim-synced):
        //   - whichever foot is currently higher (by `swingDetectThreshold`)
        //     advances its swing phase; the other resets.
        //   - synthetic lift = peak * sin(phase * π).
        //   - lowpass-smoothed to absorb any classifier flicker at the
        //     double-support transitions.
        _updateSwingPhase(dt) {
            const enabled = !!this.flatWalkContext || !!this.stepClearanceContext;
            const lY = this.m_LeftLeg.LowBonePosition.y;
            const rY = this.m_RightLeg.LowBonePosition.y;
            const threshold = this.swingDetectThreshold;
            const swingDur = Math.max(0.05, this.swingDuration);
            const peak = this.stepClearanceContext
                ? this.stepClearanceArcHeight
                : this.swingArcHeight;
            const k = Math.min(1, dt * 20);  // lowpass λ=20

            for (const leg of [this.m_LeftLeg, this.m_RightLeg]) {
                const thisY = (leg === this.m_LeftLeg) ? lY : rY;
                const otherY = (leg === this.m_LeftLeg) ? rY : lY;
                const swinging = enabled && (thisY > otherY + threshold);

                if (swinging) {
                    leg._inSwing = true;
                    leg._swingPhase = Math.min(1, leg._swingPhase + dt / swingDur);
                } else {
                    leg._inSwing = false;
                    leg._swingPhase = 0;
                }
                const targetLift = leg._inSwing
                    ? peak * Math.sin(leg._swingPhase * Math.PI)
                    : 0;
                leg._syntheticLift = (leg._syntheticLift || 0) * (1 - k) + targetLift * k;
            }
            if (this._debugSwing) {
                if (!this._swingDbgCount) this._swingDbgCount = 0;
                this._swingDbgCount++;
                if (this._swingDbgCount % 5 === 0) {
                    console.log(`[swing] gate=${enabled} L.fkY=${lY.toFixed(3)} R.fkY=${rY.toFixed(3)} ΔLR=${(lY-rY).toFixed(4)} | L: swing=${this.m_LeftLeg._inSwing} phase=${this.m_LeftLeg._swingPhase.toFixed(2)} lift=${this.m_LeftLeg._syntheticLift.toFixed(3)} | R: swing=${this.m_RightLeg._inSwing} phase=${this.m_RightLeg._swingPhase.toFixed(2)} lift=${this.m_RightLeg._syntheticLift.toFixed(3)}`);
                }
            }
        }

        // FootIK() — per-frame solve entry
        FootIK(dt) {
            this.rootObject.updateMatrixWorld(true);
            this._updateSwingPhase(dt);

            if (this.leftEnabled) {
                this.SetPositionRotationFromRayCast(this.m_LeftLeg);
                this.Smoothing(this.m_LeftLeg, dt);
                this.FootsPlacement(this.m_LeftLeg);
            }
            if (this.rightEnabled) {
                this.SetPositionRotationFromRayCast(this.m_RightLeg);
                this.Smoothing(this.m_RightLeg, dt);
                this.FootsPlacement(this.m_RightLeg);
            }

            this.GlobalSmoothing(this.m_LeftLeg);
            this.GlobalSmoothing(this.m_RightLeg);

            this.SavingPositionRotation(this.m_LeftLeg);
            this.SavingPositionRotation(this.m_RightLeg);
        }

        // External entry point — call once per frame, after mixer.update()
        update(dt) {
            if (!this.m_IsInitialized) return;
            this.FootIK(dt);
        }

        // Wrapped Rapier raycast: returns {hit, point, normal, distance}
        raycastDown(origin, dist) {
            if (!this.world || !this.RAPIER) {
                return { hit: false };
            }
            const ray = new this.RAPIER.Ray(
                { x: origin.x, y: origin.y, z: origin.z },
                { x: 0, y: -1, z: 0 },
            );
            const hit = this.world.castRayAndGetNormal(
                ray, dist, true, null, null, this.collider,
            );
            if (!hit) return { hit: false };
            return {
                hit: true,
                point: new THREE.Vector3(origin.x, origin.y - hit.timeOfImpact, origin.z),
                normal: new THREE.Vector3(hit.normal.x, hit.normal.y, hit.normal.z),
                distance: hit.timeOfImpact,
            };
        }

        // Spherecast emulation — fires the center ray plus N rays in a
        // ring of `radius` around the center XZ. Returns the hit whose
        // surface a sphere of that radius would FIRST touch as it falls
        // (= HIGHEST upward-normal hit). Rapier3D doesn't expose
        // sphereCast in its JS bindings, so we emulate via multiple rays.
        //
        // Native Rapier shape-cast — drops a sphere of `radius` downward
        // from `origin` and returns the world-space contact point on the
        // hit surface (the true contact point, not the ball center). Bridges geometry seams
        // (a ball can't fit through a sub-radius gap) AND stays aligned
        // to actual tread surfaces on stairs (uses the surface contact
        // point, not the ball's bottom — ball-bottom is below the true
        // surface at edge hits).
        sphereCastDown(origin, radius, dist) {
            if (!this._ikShapeIdentRot) {
                this._ikShapeIdentRot = { x: 0, y: 0, z: 0, w: 1 };
                this._ikShapeDownVel = { x: 0, y: -1, z: 0 };
                this._ikShapeByRadius = new Map();
                this._ikTmpQuat = new THREE.Quaternion();
                this._ikTmpVec  = new THREE.Vector3();
            }
            let shape = this._ikShapeByRadius.get(radius);
            if (!shape) {
                shape = new this.RAPIER.Ball(radius);
                this._ikShapeByRadius.set(radius, shape);
            }
            const hit = this.world.castShape(
                { x: origin.x, y: origin.y, z: origin.z },
                this._ikShapeIdentRot,
                this._ikShapeDownVel,
                shape,
                0, dist, true,
                undefined, undefined, this.collider,
            );
            if (!hit) return { hit: false };
            // Rapier's normal2 points INTO the second shape (opposite of
            // doc's "outward" wording). Use -normal2.y as outward Y.
            if (hit.normal2 && -hit.normal2.y < NormalUpThreshold) return { hit: false };
            // Rapier-compat 0.14 reports witness1 in WORLD coordinates
            // (the actual contact point on the surface).
            return {
                hit: true,
                point: new THREE.Vector3(hit.witness1.x, hit.witness1.y, hit.witness1.z),
                normal: new THREE.Vector3(-hit.normal2.x, -hit.normal2.y, -hit.normal2.z),
                distance: hit.time_of_impact + radius,
            };
        }

        // Pick which cast method to use based on `this.type` config
        cast(origin, dist) {
            if (this.type === CastType.Ray) {
                return this.raycastDown(origin, dist);
            } else if (this.type === CastType.Sphere) {
                return this.sphereCastDown(origin, this.sphereRadius, dist);
            } else { // RayAndSphere
                const r = this.raycastDown(origin, dist);
                if (r.hit && r.normal.y > NormalUpThreshold) return r;
                return this.sphereCastDown(origin, this.sphereRadius, dist);
            }
        }

        // SetPositionRotationFromRayCast(limb)
        SetPositionRotationFromRayCast(limb) {
            const rootPos = this.rootObject.position;
            const lowPos = limb.LowBonePosition;
            const currentHeight = lowPos.y - rootPos.y;
            limb._animatorWeight = currentHeight - limb.distanceFromMesh - this.m_MeshHeightOffset;

            // Compute toe-forward direction in world XZ (for footPlantForwardOffset).
            // Vector from ankle (LowBone) → toe (ExtraBone) gives the foot's
            // natural forward axis regardless of body rotation.
            let forwardOffsetX = 0, forwardOffsetZ = 0;
            limb._stairAscentSoleFitNudge = 0;
            limb._stairAscentSoleFitStatus = null;
            limb._stairAscentEdgeAlignNudge = 0;
            limb._stairAscentEdgeAlignStatus = null;
            limb._stairAscentEdgeProgressBefore = null;
            limb._stairAscentEdgeProgressAfter = null;
            limb._stairAscentEdgeMinProgress = null;
            limb._stairAscentEdgeRegroundStatus = null;
            limb._stairAscentEdgeSurfaceYBefore = null;
            limb._stairAscentEdgeSurfaceYAfter = null;
            limb._footPlantForwardOffsetScalar = 0;
            limb._footPlantForwardOffsetDistance = 0;
            if (Math.abs(this.footPlantForwardOffset) > 0.001 && limb.ExtraBone && limb.ExtraLength > 0.01) {
                const extraPos = limb.ExtraBone.getWorldPosition(this._tmpV4);
                let dx = extraPos.x - lowPos.x;
                let dz = extraPos.z - lowPos.z;
                const len = Math.hypot(dx, dz);
                if (len > 0.001) {
                    const mag = limb.ExtraLength * this.footPlantForwardOffset;
                    limb._footPlantForwardOffsetScalar = this.footPlantForwardOffset;
                    limb._footPlantForwardOffsetDistance = mag;
                    forwardOffsetX = (dx / len) * mag;
                    forwardOffsetZ = (dz / len) * mag;
                }
            }

            // Origin: foot.world + up * (MaxStep - currentHeight) [+ forward toe offset]
            const origin = this._tmpV1.set(
                lowPos.x + forwardOffsetX,
                lowPos.y + (this.m_MaxStepHeight - currentHeight),
                lowPos.z + forwardOffsetZ);
            const lowResult = this.cast(origin, this.m_MaxStepHeight * 2);

            if (this._debugIK && limb === this.m_LeftLeg) {
                const fmt = (v) => v ? `(${v.x.toFixed(2)},${v.y.toFixed(2)},${v.z.toFixed(2)})` : 'null';
                console.log(`[foot-ik-raycast] foot=${fmt(lowPos)} originY=${origin.y.toFixed(2)} lowHit=${lowResult.hit ? fmt(lowResult.point) : 'MISS'} normal=${fmt(lowResult.normal)}`);
            }

            if (this.increasedAccuracy && limb.ExtraBone) {
                const extraPos = limb.ExtraBone.getWorldPosition(this._tmpV2);
                // Lerp between ankle (LowBone) and toe (ExtraBone) by
                // extraCastReachScale. 1.0 = full toe sampling,
                // 0.5 = halfway between ankle and toe.
                // Reduces over-anticipation on short-run stairs.
                const reach = this.extraCastReachScale;
                const sampleX = lowPos.x + (extraPos.x - lowPos.x) * reach;
                const sampleY = lowPos.y + (extraPos.y - lowPos.y) * reach;
                const sampleZ = lowPos.z + (extraPos.z - lowPos.z) * reach;
                const extraHeight = sampleY - rootPos.y;
                const extraOrigin = this._tmpV3.set(
                    sampleX + forwardOffsetX,
                    sampleY + (this.m_MaxStepHeight - extraHeight),
                    sampleZ + forwardOffsetZ);
                const extraResult = this.cast(extraOrigin, this.m_MaxStepHeight * 2);
                if (this._debugIK && limb === this.m_LeftLeg) {
                    const fmt = (v) => v ? `(${v.x.toFixed(2)},${v.y.toFixed(2)},${v.z.toFixed(2)})` : 'null';
                    console.log(`[foot-ik-raycast]   toe=${fmt(extraPos)} toeHit=${extraResult.hit ? fmt(extraResult.point) : 'MISS'} chosen=${lowResult.point?.y > extraResult.point?.y ? 'foot' : 'toe'}`);
                }

                if (lowResult.hit && extraResult.hit) {
                    // Use whichever is lower (in root-local frame)
                    const localLowY  = lowResult.point.y  - rootPos.y;
                    const localExtY  = extraResult.point.y - rootPos.y;
                    if (localLowY > localExtY) {
                        // low is HIGHER → extra is the deeper hit
                        this.SetFootFromLow(limb, lowResult, extraResult);
                        limb.LowestHitPoint.copy(extraResult.point);
                    } else {
                        this.SetFootFromExtra(limb, extraResult, lowResult);
                        limb.LowestHitPoint.copy(lowResult.point);
                    }
                } else if (lowResult.hit) {
                    this.SetFootFromLow(limb, lowResult, null);
                    limb.LowestHitPoint.copy(lowResult.point);
                } else if (extraResult.hit) {
                    this.SetFootFromExtra(limb, extraResult, null);
                    limb.LowestHitPoint.copy(extraResult.point);
                } else {
                    limb.canReachTarget = false;
                }
            } else {
                if (lowResult.hit) {
                    this.SetFootFromLow(limb, lowResult, null);
                    limb.LowestHitPoint.copy(lowResult.point);
                } else {
                    limb.canReachTarget = false;
                }
            }
        }

        // SetFootFromLow(limb, lowHit [, extraHit])
        SetFootFromLow(limb, lowResult, extraResult) {
            let normal = lowResult.normal.clone();
            if (extraResult) {
                normal.add(extraResult.normal).multiplyScalar(0.5);
            }
            if (this.footConstraint) normal = this.ConstraintedNormal(normal);

            // animatorHeight (vertical, in world up): the foot's current
            // anim-driven Y deviation from rest. Carries through the
            // anim's authored foot lift / swing arc.
            //
            // KILLED during descent context (see this.descentContext flag).
            // The Mixamo stairsDown anim has BROKEN foot Y data (per the
            // well-documented community issue — Adobe never fixed it).
            // Adding animatorHeight propagates the broken Y trajectory
            // ("surfing on invisible ramp"). The community fix is to use
            // IK to override the bad FK foot Y; setting upY=0 here makes
            // the IK pin the foot to the actual raycast tread surface.
            // The anim's leg ROTATIONS still drive the stride; only the
            // broken Y is ignored.
            let upY = (limb.LowBonePosition.y - this.rootObject.position.y)
                    - limb.distanceFromMesh - this.m_MeshHeightOffset;
            const upYRaw = upY;
            // Adobe Control-Rig stackexchange fix, runtime version:
            // The Mixamo descent anim floats the FK foot bone ~0.08-0.50m
            // above bind-pose at all times, smoothly descending in world Y
            // (the "surfing the invisible ramp" effect). Subtract a per-leg
            // running min of upY to recover ONLY the swing-arc-above-floor
            // component of the anim, dropping the baseline drift.
            if (this.descentContext) {
                if (upY < limb._minUpY) limb._minUpY = upY;
                else limb._minUpY += 0.5 * 0.0167;  // slow drift up (~30 cm/s)
                upY = Math.max(0, upY - limb._minUpY);
            } else {
                limb._minUpY = Infinity;  // reset on non-descent
            }
            // Swing-arc floor (RifeWithKaiju 2026-05-13): if the synthetic
            // sinusoidal lift is higher than the anim's authored lift,
            // use it instead. This enforces a visible foot-arc when the
            // anim doesn't lift much (Mixamo flat walk being the case).
            // Ground naturally clips by virtue of upY being added to
            // lowResult.point (the raycast ground) — so the ellipse is
            // already "cut short by the ground" since we only LIFT above it.
            upY = Math.max(upY, limb._syntheticLift);
            if (this._debugIK) {
                const side = (limb === this.m_LeftLeg) ? 'L' : 'R';
                console.log(`[upY-${side}] raw=${upYRaw.toFixed(3)} minBase=${limb._minUpY.toFixed(3)} synth=${limb._syntheticLift.toFixed(3)} effective=${upY.toFixed(3)}`);
            }
            // footHeight along surface normal: foot bone above sole
            const footHeightScalar = limb.distanceFromMesh - this.m_FootHeightOffset
                + (this.rampFootClearanceOffset ?? 0);

            // target = lowHit.point + footHeight*normal + animatorHeight*up
            limb.targetPosition.copy(lowResult.point)
                .addScaledVector(normal, footHeightScalar)
                .addScaledVector(this._up, upY);
            const stairAscentSurfaceY = this._applyStairAscentEdgeAlign(limb, lowResult.point.y, upY);
            this._applyStairAscentSoleFit(limb, stairAscentSurfaceY, upY);

            // targetRotation = LookRotation aligned with normal as up
            limb.targetRotation.copy(this._quatFromUpToNormal(this._up, normal))
                .multiply(limb.LowBoneRotation);

            // Leg-reach safety: when target.y is further below the hip
            // than the leg can reach (e.g. descending stairs where the
            // tread is far below the FK hip pose), clamp target.y so the
            // knee can still bend. Without this, IK gives up and the FK
            // leg locks straight. Vertical-only clamp preserves the
            // horizontal foot-on-tread position.
            const upBonePos = limb.UpBone.getWorldPosition(this._tmpV1);
            // canReachTarget — can hip reach the target?
            const reach = limb.UpperLength + limb.LowerLength + this.m_MaxStepHeight;
            limb.canReachTarget = upBonePos.distanceTo(limb.targetPosition) <= reach;
        }

        // SetFootFromExtra(limb, extraHit [, lowHit])
        SetFootFromExtra(limb, extraResult, lowResult) {
            let normal = extraResult.normal.clone();
            if (lowResult) {
                normal.add(lowResult.normal).multiplyScalar(0.5);
            }
            if (this.footConstraint) normal = this.ConstraintedNormal(normal);

            const fromUpToNormal = this._quatFromUpToNormal(this._up, normal);

            const extraPos = limb.ExtraBone.getWorldPosition(this._tmpV1).clone();
            const lowPos   = limb.LowBonePosition;
            // If the extra/toe cast samples between ankle and toe, the inverse
            // foot offset must use the same fractional reach — subtracting the
            // FULL ankle-to-toe vector after a partial sample leaves the heel
            // hanging off short treads.
            const reachScale = Math.max(0, Math.min(1, this.extraCastReachScale ?? 1));
            const footDirection = new THREE.Vector3()
                .subVectors(extraPos, lowPos)
                .multiplyScalar(reachScale);

            // Decompose into character forward/right components
            const charFwd = new THREE.Vector3(0, 0, 1).applyQuaternion(this.rootObject.quaternion);
            const charRight = new THREE.Vector3(1, 0, 0).applyQuaternion(this.rootObject.quaternion);
            const forward = footDirection.dot(charFwd);
            const right   = footDirection.dot(charRight);
            const dirChar = new THREE.Vector3(right, 0, forward);
            const footDirRotated = dirChar.clone().applyQuaternion(this.rootObject.quaternion);
            const directioOnGround = footDirRotated.clone().applyQuaternion(fromUpToNormal);

            let upY = (limb.LowBonePosition.y - this.rootObject.position.y)
                    - limb.distanceFromMesh - this.m_MeshHeightOffset;
            // Mixamo descent — running min baseline subtract (see SetFootFromLow)
            if (this.descentContext) {
                if (upY < limb._minUpY) limb._minUpY = upY;
                else limb._minUpY += 0.5 * 0.0167;
                upY = Math.max(0, upY - limb._minUpY);
            } else {
                limb._minUpY = Infinity;
            }
            // Swing-arc floor — see SetFootFromLow for rationale.
            upY = Math.max(upY, limb._syntheticLift);
            const footHeightScalar = limb.distanceFromMesh - this.m_FootHeightOffset
                + (this.rampFootClearanceOffset ?? 0);

            if (this._debugIK && limb === this.m_LeftLeg) {
                const fmt = (v) => `(${v.x.toFixed(3)},${v.y.toFixed(3)},${v.z.toFixed(3)})`;
                console.log(`[foot-ik-diag] SetFootFromExtra: toePos=${fmt(extraPos)} footPos=${fmt(lowPos)}`);
                console.log(`[foot-ik-diag]   extraHit=${fmt(extraResult.point)} normal=${fmt(extraResult.normal)}`);
                console.log(`[foot-ik-diag]   footDir(world)=${fmt(footDirection)} fwd=${forward.toFixed(3)} right=${right.toFixed(3)}`);
                console.log(`[foot-ik-diag]   directioOnGround=${fmt(directioOnGround)}`);
                console.log(`[foot-ik-diag]   upY=${upY.toFixed(3)} footHeightScalar=${footHeightScalar.toFixed(3)}`);
            }

            limb.targetPosition.copy(extraResult.point)
                .sub(directioOnGround)
                .addScaledVector(normal, footHeightScalar)
                .addScaledVector(this._up, upY);
            const stairAscentSurfaceY = this._applyStairAscentEdgeAlign(limb, extraResult.point.y, upY);
            this._applyStairAscentSoleFit(limb, stairAscentSurfaceY, upY);

            limb.targetRotation.copy(fromUpToNormal).multiply(limb.LowBoneRotation);

            const upBonePos = limb.UpBone.getWorldPosition(this._tmpV1);
            const reach = limb.UpperLength + limb.LowerLength + this.m_MaxStepHeight;
            limb.canReachTarget = upBonePos.distanceTo(limb.targetPosition) <= reach;
        }

        // Helper — Quaternion.FromToRotation(up, normal)
        _quatFromUpToNormal(up, normal) {
            const q = new THREE.Quaternion();
            const n = normal.clone().normalize();
            q.setFromUnitVectors(up, n);
            return q;
        }

        _regroundStairAscentEdgeTarget(limb, surfaceY) {
            limb._stairAscentEdgeSurfaceYBefore = Number.isFinite(surfaceY) ? surfaceY : null;
            limb._stairAscentEdgeSurfaceYAfter = Number.isFinite(surfaceY) ? surfaceY : null;
            limb._stairAscentEdgeRegroundStatus = 'skipped';
            if (!Number.isFinite(surfaceY) || !limb?.targetPosition) return surfaceY;

            const targetYOffset = limb.targetPosition.y - surfaceY;
            const origin = new THREE.Vector3(
                limb.targetPosition.x,
                Math.max(limb.targetPosition.y, surfaceY, this.rootObject.position.y) + this.m_MaxStepHeight,
                limb.targetPosition.z,
            );
            const hit = this.cast(origin, this.m_MaxStepHeight * 2.5);
            if (!hit.hit || hit.normal.y <= NormalUpThreshold || !Number.isFinite(hit.point?.y)) {
                limb._stairAscentEdgeRegroundStatus = 'miss';
                return surfaceY;
            }

            limb.targetPosition.y = hit.point.y + targetYOffset;
            limb._stairAscentEdgeSurfaceYAfter = hit.point.y;
            limb._stairAscentEdgeRegroundStatus = 'hit';
            return hit.point.y;
        }

        _applyStairAscentEdgeAlign(limb, surfaceY, upY) {
            limb._stairAscentEdgeAlignNudge = 0;
            limb._stairAscentEdgeAlignStatus = null;
            limb._stairAscentEdgeProgressBefore = null;
            limb._stairAscentEdgeProgressAfter = null;
            limb._stairAscentEdgeMinProgress = null;
            limb._stairAscentEdgeRegroundStatus = null;
            limb._stairAscentEdgeSurfaceYBefore = null;
            limb._stairAscentEdgeSurfaceYAfter = null;
            if (!this.stairAscentEdgeAlignContext || !limb.ExtraBone || limb.ExtraLength <= 0.01) return surfaceY;
            if (!Number.isFinite(surfaceY) || !Number.isFinite(upY)) return surfaceY;
            const elevatedFoot = upY > (this.stairAscentEdgeUpYMax ?? 0.14);

            const edge = this.stairAscentEdgePoint;
            const move = this.stairAscentMoveDir;
            if (!edge || !move) return surfaceY;
            const len = Math.hypot(move.x ?? 0, move.z ?? 0);
            if (len <= 0.001) return surfaceY;
            const dirX = (move.x ?? 0) / len;
            const dirZ = (move.z ?? 0) / len;

            const progress =
                (limb.targetPosition.x - edge.x) * dirX +
                (limb.targetPosition.z - edge.z) * dirZ;
            const run = Number.isFinite(this.stairAscentEdgeTreadRun)
                ? this.stairAscentEdgeTreadRun
                : (Number.isFinite(this.stairAscentTreadRun) ? this.stairAscentTreadRun : null);
            const runMargin = Number.isFinite(run)
                ? run * (this.stairAscentEdgeRunMarginScale ?? 0.18)
                : Infinity;
            const footMargin = limb.ExtraLength * (this.stairAscentEdgeFootMarginScale ?? 0.42);
            const minProgress = Math.max(0.015, Math.min(runMargin, footMargin));
            limb._stairAscentEdgeProgressBefore = progress;
            limb._stairAscentEdgeMinProgress = minProgress;

            const tolerance = this.stairAscentEdgeTolerance ?? 0.008;
            if (Number.isFinite(run)) {
                const maxByRun = run * (this.stairAscentEdgeMaxProgressRunScale ?? 0.62);
                const maxByFootReserve = run - limb.ExtraLength * (this.stairAscentEdgeMaxProgressFootReserveScale ?? 0.65);
                const maxProgress = Math.max(minProgress, Math.min(maxByRun, maxByFootReserve));
                if (progress > maxProgress + tolerance) {
                    const backRunCap = run * (this.stairAscentEdgeBackMaxRunScale ?? 0.42);
                    const backFootCap = limb.ExtraLength * (this.stairAscentEdgeBackMaxFootScale ?? 0.90);
                    const back = Math.min(progress - maxProgress, backRunCap, backFootCap, 0.16);
                    if (back > tolerance * 0.25) {
                        limb.targetPosition.x -= dirX * back;
                        limb.targetPosition.z -= dirZ * back;
                        limb._stairAscentEdgeAlignNudge = -back;
                        limb._stairAscentEdgeProgressAfter = progress - back;
                        limb._stairAscentEdgeAlignStatus = back + 1e-6 < progress - maxProgress
                            ? 'overreach-capped'
                            : (elevatedFoot ? 'overreach-elevated' : 'overreach');
                        return this._regroundStairAscentEdgeTarget(limb, surfaceY);
                    }
                }
            }

            if (elevatedFoot) {
                limb._stairAscentEdgeAlignStatus = 'elevated-ok';
                limb._stairAscentEdgeProgressAfter = progress;
                return surfaceY;
            }

            if (progress >= minProgress - tolerance) {
                limb._stairAscentEdgeAlignStatus = 'already-forward';
                limb._stairAscentEdgeProgressAfter = progress;
                return surfaceY;
            }

            const runCap = Number.isFinite(run)
                ? run * (this.stairAscentEdgeMaxRunScale ?? 0.38)
                : Infinity;
            const footCap = limb.ExtraLength * (this.stairAscentEdgeMaxFootScale ?? 0.90);
            let maxNudge = Math.max(0, Math.min(runCap, footCap, 0.16));
            if (Number.isFinite(run)) {
                const toeReserve = Math.min(
                    run * (this.stairAscentEdgeToeReserveRunScale ?? 0.42),
                    limb.ExtraLength * (this.stairAscentEdgeToeReserveFootScale ?? 0.72),
                );
                const maxProgress = Math.max(minProgress, run - toeReserve);
                maxNudge = Math.min(maxNudge, Math.max(0, maxProgress - progress));
            }

            const needed = Math.max(0, minProgress - progress);
            const nudge = Math.min(needed, maxNudge);
            if (nudge <= tolerance * 0.25) {
                limb._stairAscentEdgeAlignStatus = maxNudge <= 0 ? 'toe-reserve' : 'no-nudge';
                limb._stairAscentEdgeProgressAfter = progress;
                return surfaceY;
            }

            limb.targetPosition.x += dirX * nudge;
            limb.targetPosition.z += dirZ * nudge;
            limb._stairAscentEdgeAlignNudge = nudge;
            limb._stairAscentEdgeProgressAfter = progress + nudge;
            limb._stairAscentEdgeAlignStatus = nudge + 1e-6 < needed ? 'capped' : 'aligned';
            return this._regroundStairAscentEdgeTarget(limb, surfaceY);
        }

        _applyStairAscentSoleFit(limb, surfaceY, upY) {
            limb._stairAscentSoleFitNudge = 0;
            limb._stairAscentSoleFitStatus = null;
            if (!this.stairAscentSoleFitContext || !limb.ExtraBone || limb.ExtraLength <= 0.01) return;
            if (!Number.isFinite(surfaceY) || !Number.isFinite(upY)) return;
            if (upY > (this.stairAscentSoleFitUpYMax ?? 0.14)) {
                limb._stairAscentSoleFitStatus = 'swing';
                return;
            }

            const lowPos = limb.LowBonePosition;
            const extraPos = limb.ExtraBone.getWorldPosition(new THREE.Vector3());
            const dir = new THREE.Vector3(extraPos.x - lowPos.x, 0, extraPos.z - lowPos.z);
            const len = dir.length();
            if (len <= 0.001) return;
            dir.multiplyScalar(1 / len);

            const heelBack = limb.ExtraLength * (this.stairAscentHeelProbeScale ?? 0.90);
            const toeAhead = limb.ExtraLength * (this.stairAscentToeProbeScale ?? 0.95);
            const tolerance = this.stairAscentSoleFitTolerance ?? 0.025;
            const toeGuardRise = this.stairAscentToeGuardRise ?? 0.085;
            const step = Math.max(0.001, this.stairAscentSoleFitStep ?? 0.012);
            const runCap = Number.isFinite(this.stairAscentTreadRun)
                ? Math.max(0, this.stairAscentTreadRun * (this.stairAscentSoleFitTreadRunScale ?? 0.45))
                : 0;
            const footCap = limb.ExtraLength * (this.stairAscentSoleFitExtraScale ?? 1.05);
            const maxNudge = Math.max(0, Math.min(
                this.stairAscentSoleFitMax ?? 0.14,
                Math.max(runCap, footCap),
            ) * Math.max(0, Math.min(1, this.stairAscentSoleFitMaxScale ?? 1)));
            let total = 0;
            let status = 'start';

            while (total + 1e-6 < maxNudge) {
                const heelOrigin = new THREE.Vector3(
                    limb.targetPosition.x - dir.x * heelBack,
                    surfaceY + this.m_MaxStepHeight,
                    limb.targetPosition.z - dir.z * heelBack,
                );
                const heelHit = this.cast(heelOrigin, this.m_MaxStepHeight * 2);
                if (heelHit.hit && heelHit.normal.y > NormalUpThreshold && heelHit.point.y >= surfaceY - tolerance) {
                    status = total > 0 ? 'supported' : 'already-supported';
                    break;
                }

                const toeOrigin = new THREE.Vector3(
                    limb.targetPosition.x + dir.x * toeAhead,
                    surfaceY + this.m_MaxStepHeight,
                    limb.targetPosition.z + dir.z * toeAhead,
                );
                const toeHit = this.cast(toeOrigin, this.m_MaxStepHeight * 2);
                if (toeHit.hit && toeHit.normal.y > NormalUpThreshold && toeHit.point.y > surfaceY + toeGuardRise) {
                    status = total > 0 ? 'toe-guard' : 'toe-guard-start';
                    break;
                }

                const nudge = Math.min(step, maxNudge - total);
                limb.targetPosition.addScaledVector(dir, nudge);
                total += nudge;
                status = 'max';
            }

            limb._stairAscentSoleFitNudge = total;
            limb._stairAscentSoleFitStatus = status;
        }

        // Smoothing(limb) — per-foot temporal smoothing
        Smoothing(limb, dt) {
            this._applyStepClearanceDrop(limb, dt);
            if (limb.canReachTarget && this.m_DistancePower > 0) {
                const animDistance = limb.lastLowBoneAnimationPosition
                    .distanceTo(limb.LowBonePosition);
                const movementDistance = limb.lastLowBonePosition
                    .distanceTo(limb.targetPosition);
                const animD = Math.max(animDistance, this.m_MinimalSmoothDistance);
                const factor = movementDistance > 1e-6
                    ? (animD * (MAX_DISTANCE_POWER - this.m_DistancePower)) / movementDistance
                    : 1;
                // Clamp the lerp factor to [0,1] so factor > 1 doesn't
                // extrapolate the target out into space.
                limb.targetPosition.lerpVectors(
                    limb.lastLowBonePosition, limb.targetPosition,
                    Math.max(0, Math.min(1, factor)),
                );
            }
            if (limb.canReachTarget && this.m_SmoothingAngle > 0) {
                const animAngle = limb.lastLowBoneAnimationRotation
                    .angleTo(limb.LowBoneRotation) * RAD2DEG;
                const targetAngle = limb.lastLowBoneRotation
                    .angleTo(limb.targetRotation) * RAD2DEG;
                const t = targetAngle > 1e-6
                    ? Math.max(0, Math.min(1, (animAngle + (MAX_SMOOTHING_ANGLE - this.m_SmoothingAngle)) / targetAngle))
                    : 1;
                limb.targetRotation.copy(
                    limb.lastLowBoneRotation.clone().slerp(limb.targetRotation, t),
                );
            }
            limb.lastLowBoneAnimationPosition.copy(limb.LowBonePosition);
            limb.lastLowBoneAnimationRotation.copy(limb.LowBoneRotation);
        }

        _applyStepClearanceDrop(limb, dt) {
            const hitY = limb.LowestHitPoint?.y;
            if (!this.stepClearanceContext || !Number.isFinite(hitY)) {
                limb._lastStepClearanceHitY = null;
                limb._stepClearanceDropPhase = 1;
                return;
            }

            const prevHitY = limb._lastStepClearanceHitY;
            const drop = Number.isFinite(prevHitY) ? prevHitY - hitY : 0;
            if (drop >= this.stepClearanceDropMin && drop <= this.stepClearanceDropMax) {
                limb._stepClearanceDropPhase = 0;
            }

            if (limb._stepClearanceDropPhase < 1) {
                const duration = Math.max(0.05, this.stepClearanceDropDuration);
                const nextPhase = Math.min(1, limb._stepClearanceDropPhase + dt / duration);
                const lift = this.stepClearanceDropLift * Math.sin(nextPhase * Math.PI);
                if (lift > 0) {
                    limb.targetPosition.addScaledVector(this._up, lift);
                    limb._syntheticLift = Math.max(limb._syntheticLift ?? 0, lift);
                    limb._inSwing = true;
                    limb._swingPhase = Math.max(limb._swingPhase ?? 0, nextPhase);
                }
                limb._stepClearanceDropPhase = nextPhase;
            }

            limb._lastStepClearanceHitY = hitY;
        }

        // GlobalSmoothing(limb)
        GlobalSmoothing(limb) {
            if (this.m_GlobalSmoothingPower <= 0) return;
            const factor = 1 - this.m_GlobalSmoothingPower;
            const tmpQ = new THREE.Quaternion();
            limb.UpBone.getWorldQuaternion(tmpQ);
            const upTarget = tmpQ.clone();
            const upBlended = limb.lastUpBoneRotation.clone().slerp(upTarget, factor);
            this._setWorldQuat(limb.UpBone, upBlended);

            limb.MiddleBone.getWorldQuaternion(tmpQ);
            const midBlended = limb.lastMiddleBoneRotation.clone().slerp(tmpQ, factor);
            this._setWorldQuat(limb.MiddleBone, midBlended);

            const lowCurrent = new THREE.Quaternion();
            limb.LowBone.getWorldQuaternion(lowCurrent);
            const lowBlended = limb.lastLowBoneRotation.clone().slerp(lowCurrent, factor);
            limb.LowBoneRotation = lowBlended;
        }

        _setWorldQuat(bone, qWorld) {
            const parent = bone.parent;
            if (!parent) { bone.quaternion.copy(qWorld); return; }
            const parentQ = new THREE.Quaternion();
            parent.getWorldQuaternion(parentQ);
            bone.quaternion.copy(parentQ.invert().multiply(qWorld));
        }

        // SavingPositionRotation(limb) — stash last-frame state
        SavingPositionRotation(limb) {
            limb.UpBone.getWorldQuaternion(limb.lastUpBoneRotation);
            limb.MiddleBone.getWorldQuaternion(limb.lastMiddleBoneRotation);
            limb.LowBone.getWorldQuaternion(limb.lastLowBoneRotation);
            limb.LowBone.getWorldPosition(limb.lastLowBonePosition);
        }

        // ConstraintedNormal(normal)
        ConstraintedNormal(normal) {
            if (normal.y < this.m_Incline) {
                const result = new THREE.Vector3();
                const axis = new THREE.Vector3().crossVectors(this._up, normal);
                if (axis.lengthSq() < 1e-6) return this._up.clone();
                axis.normalize();
                const q = new THREE.Quaternion().setFromAxisAngle(axis, this.m_InclineRadian);
                return this._up.clone().applyQuaternion(q);
            }
            return normal;
        }

        // ────────────────────────────────────────────────────────────
        // FootsPlacement(limb [, pole]) — cosine-rule two-bone leg solve
        // The two-bone IK solver (no external pole target — the knee
        // plane is derived from the leg itself).
        // ────────────────────────────────────────────────────────────
        FootsPlacement(limb) {
            const wantDiag = this._debugIK && limb === this.m_LeftLeg;
            if (!limb.canReachTarget) {
                if (wantDiag) console.log('[foot-ik-diag] L canReachTarget=false (skipping)');
                return;
            }

            const upBonePos = limb.UpBone.getWorldPosition(this._tmpV1).clone();
            const middleBonePos = limb.MiddleBone.getWorldPosition(this._tmpV2).clone();
            const lowBonePos = limb.LowBonePosition;

            const targetDistance = Math.min(
                limb.targetPosition.distanceTo(upBonePos),
                limb.UpperLength + limb.LowerLength - 0.001,
            );

            // planeThirdPoint (pole) — fixKnee knee-plane variant
            let planeThirdPoint;
            if (!this.fixKnee) {
                planeThirdPoint = middleBonePos.clone().add(lowBonePos).multiplyScalar(0.5)
                    .addScaledVector(
                        this._tmpV3.set(0, 0, 1).applyQuaternion(this.rootObject.quaternion),
                        0.05);
            } else {
                const targetVec = middleBonePos.clone().sub(upBonePos).normalize();
                const charRight = this._tmpV3.set(1, 0, 0).applyQuaternion(this.rootObject.quaternion);
                const ang = targetVec.angleTo(charRight) * RAD2DEG;
                const cross = this._tmpV4.set(0, 0, 1).applyQuaternion(this.rootObject.quaternion)
                    .applyAxisAngle(this._up, -ang * DEG2RAD).normalize();
                const rotated = targetVec.clone().applyAxisAngle(cross, Math.PI / 2);
                planeThirdPoint = middleBonePos.clone().addScaledVector(rotated, limb.Length);
            }

            const targetAngle = limb.MiddleBoneAngle(targetDistance);
            const sourceAngle = (lowBonePos.clone().sub(middleBonePos))
                .angleTo(upBonePos.clone().sub(middleBonePos)) * RAD2DEG;
            const axis = new THREE.Vector3()
                .crossVectors(
                    lowBonePos.clone().sub(planeThirdPoint),
                    upBonePos.clone().sub(planeThirdPoint),
                ).normalize();

            if (wantDiag) {
                const fmt = (v) => `(${v.x.toFixed(3)},${v.y.toFixed(3)},${v.z.toFixed(3)})`;
                console.log(`[foot-ik-diag] L hip=${fmt(upBonePos)} knee=${fmt(middleBonePos)} foot=${fmt(lowBonePos)}`);
                console.log(`[foot-ik-diag] L target=${fmt(limb.targetPosition)} targetDist=${targetDistance.toFixed(3)}`);
                console.log(`[foot-ik-diag] L planeThirdPoint=${fmt(planeThirdPoint)}`);
                console.log(`[foot-ik-diag] L targetAngle=${targetAngle.toFixed(1)}° sourceAngle=${sourceAngle.toFixed(1)}° Δ=${(sourceAngle-targetAngle).toFixed(1)}° axis=${fmt(axis)}`);
            }

            // limb.MiddleBone.rotation = AngleAxis(angle - targetAngle, axis) * MiddleBone.rotation
            const midDelta = new THREE.Quaternion().setFromAxisAngle(
                axis, (sourceAngle - targetAngle) * DEG2RAD);
            this._applyWorldDeltaToBone(limb.MiddleBone, midDelta);

            // UpBone rotation aligns thigh direction with target
            this.rootObject.updateMatrixWorld(true);
            const middleAfter = limb.MiddleBone.getWorldPosition(this._tmpV1).clone();
            const lowAfter = limb.LowBonePosition;

            if (wantDiag) {
                const fmt = (v) => `(${v.x.toFixed(3)},${v.y.toFixed(3)},${v.z.toFixed(3)})`;
                console.log(`[foot-ik-diag] L after mid: knee=${fmt(middleAfter)} foot=${fmt(lowAfter)}`);
            }

            const upDelta = new THREE.Quaternion().setFromUnitVectors(
                lowAfter.clone().sub(upBonePos).normalize(),
                limb.targetPosition.clone().sub(upBonePos).normalize(),
            );
            this._applyWorldDeltaToBone(limb.UpBone, upDelta);

            // Foot rotation
            this.rootObject.updateMatrixWorld(true);
            limb.LowBoneRotation = limb.targetRotation;

            if (wantDiag) {
                const fmt = (v) => `(${v.x.toFixed(3)},${v.y.toFixed(3)},${v.z.toFixed(3)})`;
                const footFinal = limb.LowBonePosition;
                console.log(`[foot-ik-diag] L FINAL foot=${fmt(footFinal)} (target was ${fmt(limb.targetPosition)})`);
            }
        }

        _applyWorldDeltaToBone(bone, worldDelta) {
            const parent = bone.parent;
            if (!parent) { bone.quaternion.premultiply(worldDelta); return; }
            const parentQ = new THREE.Quaternion();
            parent.getWorldQuaternion(parentQ);
            const parentQInv = parentQ.clone().invert();
            const localDelta = parentQInv.clone().multiply(worldDelta).multiply(parentQ);
            bone.quaternion.premultiply(localDelta);
        }
    }

    globalThis.VRMFootControllerIK = VRMFootControllerIK;
    globalThis.VRMFootControllerIK_CastType = CastType;
    globalThis.VRMFootControllerIK_RotationType = RotationType;
    console.log('[foot-ik] VRMFootControllerIK class registered on globalThis');
})();
