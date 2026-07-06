// terrain_base.js — shared locomotion scene template. Builds walkable
// terrain (stairs/ramps/flats per globalThis.TERRAIN_CONFIG), loads a VRM,
// and wires the full controller + foot-IK stack. Scene scripts set
// TERRAIN_CONFIG (and ASSETS.character_vrm) then eval this file.
//
// TERRAIN_CONFIG schema:
//   { type: 'stairs', rise: 0.18, run: 0.28, num: 100 }
//   { type: 'ramp',   angleDeg: 33, horizLen: 28 }
//
// The terrain bottom edge always sits at world (0, 0, 1.5).

let RAPIER = null;

function _locNum(v, digits = 5) {
    return Number.isFinite(v) ? Number(v.toFixed(digits)) : null;
}

function _locVec(v) {
    if (!v) return null;
    return { x: _locNum(v.x), y: _locNum(v.y), z: _locNum(v.z) };
}

function _locDistance(a, b, xzOnly = false) {
    if (!a || !b) return null;
    const dx = a.x - b.x;
    const dy = xzOnly ? 0 : a.y - b.y;
    const dz = a.z - b.z;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

function _locActionTelemetry(action) {
    if (!action) return null;
    return {
        weight: _locNum(action.weight),
        timeScale: _locNum(action.timeScale),
        time: _locNum(action.time),
    };
}

function _locTerrainAt(z) {
    const segments = globalThis._terrainTelemetrySegments ?? [];
    for (const seg of segments) {
        if (z <= seg.startZ + 1e-4 && z >= seg.endZ - 1e-4) return seg;
    }
    return null;
}

function _locLimbTelemetry(ik, side, dt) {
    const limb = side === 'left' ? ik?.m_LeftLeg : ik?.m_RightLeg;
    if (!limb) return null;

    const state = globalThis._locomotionTelemetry;
    const prev = state?.prevFeet?.[side] ?? null;
    const actual = limb.LowBonePosition;
    const target = limb.targetPosition?.clone?.() ?? null;
    const hit = limb.LowestHitPoint?.clone?.() ?? null;
    const validTarget = !!limb.canReachTarget && !!target && !!hit;
    const footHeight = (limb.distanceFromMesh ?? 0) - (ik.m_FootHeightOffset ?? 0);
    const targetError = validTarget ? actual.distanceTo(target) : null;
    const targetErrorXZ = validTarget ? _locDistance(actual, target, true) : null;
    const hitGapY = validTarget ? actual.y - hit.y : null;
    const soleGapY = validTarget ? actual.y - hit.y - footHeight : null;
    const actualSpeed = validTarget && prev?.actual && dt > 0 ? _locDistance(actual, prev.actual) / dt : null;
    const targetSpeed = validTarget && prev?.target && dt > 0 ? _locDistance(target, prev.target) / dt : null;
    const hitSpeed = validTarget && prev?.hit && dt > 0 ? _locDistance(hit, prev.hit) / dt : null;
    const toe = limb.ExtraBone?.getWorldPosition?.(new THREE.Vector3()) ?? null;
    const toeGroundAngleDeg = toe
        ? Math.atan2(toe.y - actual.y, Math.hypot(toe.x - actual.x, toe.z - actual.z)) * 180 / Math.PI
        : null;

    if (state) {
        state.prevFeet[side] = validTarget
            ? { actual: actual.clone(), target: target.clone(), hit: hit.clone() }
            : null;
    }

    return {
        actual: _locVec(actual),
        toe: _locVec(toe),
        target: _locVec(target),
        hit: _locVec(hit),
        canReachTarget: !!limb.canReachTarget,
        inSwing: !!limb._inSwing,
        swingPhase: _locNum(limb._swingPhase),
        syntheticLift: _locNum(limb._syntheticLift),
        animatorWeight: _locNum(limb._animatorWeight),
        footHeight: _locNum(footHeight),
        targetError: _locNum(targetError),
        targetErrorXZ: _locNum(targetErrorXZ),
        hitGapY: _locNum(hitGapY),
        soleGapY: _locNum(soleGapY),
        toeGroundAngleDeg: _locNum(toeGroundAngleDeg),
        stairAscentSoleFitNudge: _locNum(limb._stairAscentSoleFitNudge),
        stairAscentSoleFitStatus: limb._stairAscentSoleFitStatus ?? null,
        stairAscentEdgeAlignNudge: _locNum(limb._stairAscentEdgeAlignNudge),
        stairAscentEdgeAlignStatus: limb._stairAscentEdgeAlignStatus ?? null,
        stairAscentEdgeProgressBefore: _locNum(limb._stairAscentEdgeProgressBefore),
        stairAscentEdgeProgressAfter: _locNum(limb._stairAscentEdgeProgressAfter),
        stairAscentEdgeMinProgress: _locNum(limb._stairAscentEdgeMinProgress),
        stairAscentEdgeRegroundStatus: limb._stairAscentEdgeRegroundStatus ?? null,
        stairAscentEdgeSurfaceYBefore: _locNum(limb._stairAscentEdgeSurfaceYBefore),
        stairAscentEdgeSurfaceYAfter: _locNum(limb._stairAscentEdgeSurfaceYAfter),
        footPlantForwardOffsetDistance: _locNum(limb._footPlantForwardOffsetDistance),
        footPlantForwardOffsetScalar: _locNum(limb._footPlantForwardOffsetScalar),
        actualSpeed: _locNum(actualSpeed),
        targetSpeed: _locNum(targetSpeed),
        hitSpeed: _locNum(hitSpeed),
    };
}

function _locEnsureTelemetry() {
    const cfg = globalThis.LOCOMOTION_TELEMETRY;
    if (!cfg?.enabled) return null;
    if (!globalThis._locomotionTelemetry) {
        globalThis._locomotionTelemetry = {
            config: { ...cfg },
            frames: [],
            prevFeet: { left: null, right: null },
            prevBodyY: null,
            prevBodyVelY: null,
        };
    }
    return globalThis._locomotionTelemetry;
}

function _locRecordTelemetry(t, frameIndex, dt, charCtrl) {
    const state = _locEnsureTelemetry();
    if (!state || !charCtrl) return;
    const sampleEvery = Math.max(1, state.config.sampleEvery ?? 1);
    const frame = Number.isInteger(frameIndex) ? frameIndex : state.frames.length;
    if (frame % sampleEvery !== 0) return;
    const maxFrames = state.config.maxFrames ?? Infinity;
    if (state.frames.length >= maxFrames) return;

    const body = charCtrl.bodyTranslation;
    const actions = charCtrl._actions ?? {};
    const ik = globalThis._legIK;
    const supportFrame = charCtrl.supportFrame ?? null;
    const bodyVelY = state.prevBodyY !== null && dt > 0 ? (body.y - state.prevBodyY) / dt : null;
    const bodyJerkY = state.prevBodyVelY !== null && bodyVelY !== null && dt > 0
        ? (bodyVelY - state.prevBodyVelY) / dt
        : null;
    state.prevBodyY = body.y;
    if (bodyVelY !== null) state.prevBodyVelY = bodyVelY;

    const terrain = _locTerrainAt(body.z);
    state.frames.push({
        frame,
        t: _locNum(t),
        terrain,
        body: {
            center: _locVec(body),
            feet: _locVec(charCtrl.feetWorldPosition),
            speedActual: _locNum(charCtrl.speedActual),
            speedInput: _locNum(charCtrl._smoothFwdSpeed),
            speedScale: _locNum(charCtrl.speedScale),
            grounded: !!charCtrl.grounded,
            groundY: _locNum(charCtrl.groundY),
            externalGroundY: _locNum(charCtrl.externalGroundY),
            supportMode: supportFrame?.body?.supportMode ?? null,
            usedFootSupportForRoot: !!supportFrame?.body?.usedFootSupportForRoot,
            blockedUpwardDescentSnap: !!supportFrame?.body?.blockedUpwardDescentSnap,
            raisedSupportDuringDescent: supportFrame?.body?.raisedSupportDuringDescent ?? null,
            ikGroundGrace: supportFrame?.body?.ikGroundGrace ?? null,
            bodyYTarget: _locNum(supportFrame?.body?.bodyYTarget),
            contactSupport: supportFrame?.body?.contactSupport ?? null,
            ikContactSupport: supportFrame?.body?.ikContactSupport ?? null,
            bodyVelY: _locNum(bodyVelY),
            bodyJerkY: _locNum(bodyJerkY),
        },
        support: {
            climbAngleDeg: _locNum(charCtrl.climbAngleDeg),
            signedClimbAngleDeg: _locNum(charCtrl.signedClimbAngleDeg),
            climbBlocked: !!charCtrl._climbBlocked,
            aheadHighestDelta: _locNum(charCtrl.aheadHighestDelta),
            aheadLowestDelta: _locNum(charCtrl.aheadLowestDelta),
            aheadProbeSpread: _locNum(charCtrl.aheadProbeSpread),
            aheadTreadRun: _locNum(charCtrl.aheadTreadRun),
            aheadStepLike: !!charCtrl.aheadStepLike,
            aheadIsolatedObstacle: !!charCtrl.aheadIsolatedObstacle,
            aheadSmoothRampLike: !!charCtrl.aheadSmoothRampLike,
            aheadTransitionCount: charCtrl.aheadTransitionCount ?? null,
            aheadProbeResidual: _locNum(charCtrl.aheadProbeResidual),
            aheadStepRiseRaw: _locNum(charCtrl.aheadStepRiseRaw),
            stairShape: charCtrl.aheadStairShape ?? null,
            stairRise: _locNum(charCtrl.aheadStairRise),
            footObservation: supportFrame?.footObservation ?? null,
            animation: supportFrame?.animation ?? null,
            stairAscentEdgeAlign: supportFrame?.stairAscentEdgeAlign ?? null,
        },
        actions: {
            idle: _locActionTelemetry(actions.idle),
            walk: _locActionTelemetry(actions.walk),
            run: _locActionTelemetry(actions.run),
            stairsUp: _locActionTelemetry(actions.stairsUp),
            stairsDown: _locActionTelemetry(actions.stairsDown),
            fallIdle: _locActionTelemetry(actions.fallIdle),
        },
        ik: ik ? {
            descentContext: !!ik.descentContext,
            flatWalkContext: !!ik.flatWalkContext,
            stepClearanceContext: !!ik.stepClearanceContext,
            stairAscentSoleFitContext: !!ik.stairAscentSoleFitContext,
            stairAscentTreadRun: _locNum(ik.stairAscentTreadRun),
            stairAscentOffsetScale: _locNum(ik.stairAscentOffsetScale),
            stairAscentSoleFitMaxScale: _locNum(ik.stairAscentSoleFitMaxScale),
            stairAscentEdgeAlignContext: !!ik.stairAscentEdgeAlignContext,
            stairAscentEdgePoint: ik.stairAscentEdgePoint ?? null,
            stairAscentMoveDir: ik.stairAscentMoveDir ?? null,
            stairAscentEdgeTreadRun: _locNum(ik.stairAscentEdgeTreadRun),
            footPlantForwardOffset: _locNum(ik.footPlantForwardOffset),
            rampFootClearanceOffset: _locNum(ik.rampFootClearanceOffset),
            extraCastReachScale: _locNum(ik.extraCastReachScale),
            canReachTargets: !!ik.CanReachTargets,
            left: _locLimbTelemetry(ik, 'left', dt),
            right: _locLimbTelemetry(ik, 'right', dt),
        } : null,
    });
}

function _locUpdateMetric(bucket, name, value) {
    if (!Number.isFinite(value)) return;
    const cur = bucket[name] ?? { max: 0, sum: 0, count: 0 };
    cur.max = Math.max(cur.max, Math.abs(value));
    cur.sum += Math.abs(value);
    cur.count += 1;
    cur.avg = cur.sum / cur.count;
    bucket[name] = cur;
}

function _locSummarizeTelemetry(frames) {
    const summary = {
        frameCount: frames.length,
        metrics: {},
        byTerrain: {},
    };
    for (const f of frames) {
        const key = f.terrain?.label ?? f.support?.stairShape ?? 'unclassified';
        if (!summary.byTerrain[key]) summary.byTerrain[key] = { frameCount: 0, metrics: {} };
        summary.byTerrain[key].frameCount += 1;

        const buckets = [summary.metrics, summary.byTerrain[key].metrics];
        for (const b of buckets) {
            _locUpdateMetric(b, 'bodyJerkY', f.body?.bodyJerkY);
            _locUpdateMetric(b, 'speedError', (f.body?.speedInput ?? 0) - (f.body?.speedActual ?? 0));
            for (const side of ['left', 'right']) {
                const foot = f.ik?.[side];
                _locUpdateMetric(b, `${side}TargetError`, foot?.targetError);
                _locUpdateMetric(b, `${side}TargetErrorXZ`, foot?.targetErrorXZ);
                _locUpdateMetric(b, `${side}SoleGapY`, foot?.soleGapY);
                _locUpdateMetric(b, `${side}TargetSpeed`, foot?.targetSpeed);
                _locUpdateMetric(b, `${side}HitSpeed`, foot?.hitSpeed);
            }
        }
    }
    return summary;
}

globalThis.setup = async function () {
    const TC = globalThis.TERRAIN_CONFIG ?? { type: 'stairs', rise: 0.18, run: 0.28, num: 100 };
    const TAG = '[rapier-terrain-' + (TC.type === 'ramp' ? `ramp${Math.round(TC.angleDeg)}` : `stairs${Math.round(TC.rise*100)}x${Math.round(TC.run*100)}`) + ']';

    const renderer = new THREE.WebGPURenderer({
        canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE,
    });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.shadowMap.enabled = true;
    await renderer.init();

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x182030);
    const camera = new THREE.PerspectiveCamera(45, WIDTH / HEIGHT, 0.1, 200);
    const FPS = 30;

    const sun = new THREE.DirectionalLight(0xffffee, 3);
    sun.position.set(4, 8, 4);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.left = -15; sun.shadow.camera.right = 15;
    sun.shadow.camera.top = 30;   sun.shadow.camera.bottom = -10;
    sun.shadow.camera.near = 0.5; sun.shadow.camera.far = 100;
    sun.shadow.bias = -0.001;
    scene.add(sun);
    scene.add(new THREE.AmbientLight(0xffffff, 0.5));

    const groundMat = new THREE.MeshStandardNodeMaterial({ color: 0x2a2a2a, metalness: 0.05, roughness: 0.85 });
    const obstMat   = new THREE.MeshStandardNodeMaterial({ color: 0xd97550, metalness: 0.1,  roughness: 0.7 });

    const groundExtent = TC.groundExtent ?? 120;
    const groundHalf = groundExtent / 2;
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(groundExtent, groundExtent), groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const FIRST_Z = 1.5;
    const bumpMeshes = [];
    const terrainTelemetrySegments = [];
    terrainTelemetrySegments.push({
        index: -1,
        kind: 'flat',
        dir: null,
        label: 'precourse_flat',
        startZ: 6,
        endZ: FIRST_Z,
        startY: 0,
        endY: 0,
        length: 6 - FIRST_Z,
        rise: null,
        run: null,
        num: null,
        angleDeg: null,
        height: null,
        depth: null,
        radius: null,
    });

    if (TC.type === 'stairs') {
        const RISE = TC.rise;
        const RUN = TC.run;
        const NUM = TC.num;
        for (let i = 0; i < NUM; i++) {
            const h = RISE * (i + 1);
            const z = FIRST_Z - i * RUN;
            const m = new THREE.Mesh(new THREE.BoxGeometry(3.0, h, RUN), obstMat);
            m.position.set(0, h / 2, z);
            m.castShadow = true; m.receiveShadow = true;
            scene.add(m);
            bumpMeshes.push({ mesh: m, half: { x: 1.5, y: h / 2, z: RUN / 2 } });
        }
        console.log(`${TAG} stairs ${NUM}x ${RISE}m × ${RUN}m, angle ${Math.atan2(RISE, RUN) * 180 / Math.PI |0}°`);
    } else if (TC.type === 'ramp') {
        const angleRad = TC.angleDeg * Math.PI / 180;
        const horizLen = TC.horizLen;
        const rise = horizLen * Math.tan(angleRad);
        const rampLength = Math.sqrt(horizLen ** 2 + rise ** 2);
        const rampThickness = 0.5;
        const cos = Math.cos(angleRad);
        const sin = Math.sin(angleRad);
        const yOff = (rampThickness/2)*cos - (rampLength/2)*sin;
        const zOff = (rampThickness/2)*sin + (rampLength/2)*cos;
        const ramp = new THREE.Mesh(
            new THREE.BoxGeometry(3.0, rampThickness, rampLength),
            obstMat,
        );
        ramp.rotation.x = angleRad;
        ramp.position.set(0, -yOff, FIRST_Z - zOff);
        ramp.castShadow = true; ramp.receiveShadow = true;
        scene.add(ramp);
        bumpMeshes.push({ mesh: ramp, half: { x: 1.5, y: rampThickness/2, z: rampLength/2 } });
        console.log(`${TAG} ramp ${TC.angleDeg}° horiz=${horizLen}m rise=${rise.toFixed(2)}m`);
    } else if (TC.type === 'stairs_pyramid') {
        // Stairs up + flat plateau + stairs down. Both staircases share
        // the same rise/run from the config. Plateau width fills between
        // the top of up-stairs and the top of down-stairs.
        const RISE = TC.rise;
        const RUN = TC.run;
        const NUM_UP = TC.numUp;
        const NUM_DOWN = TC.numDown;
        const PLATEAU_WIDTH = TC.plateauWidth ?? 3.0;
        // Up-stairs: as before, indexed 0..NUM_UP-1, taller as i grows.
        for (let i = 0; i < NUM_UP; i++) {
            const h = RISE * (i + 1);
            const z = FIRST_Z - i * RUN;
            const m = new THREE.Mesh(new THREE.BoxGeometry(3.0, h, RUN), obstMat);
            m.position.set(0, h / 2, z);
            m.castShadow = true; m.receiveShadow = true;
            scene.add(m);
            bumpMeshes.push({ mesh: m, half: { x: 1.5, y: h / 2, z: RUN / 2 } });
        }
        const peakHeight = RISE * NUM_UP;
        // Plateau at the peak, spanning PLATEAU_WIDTH in z.
        const lastUpZ = FIRST_Z - (NUM_UP - 1) * RUN;
        const plateauFrontZ = lastUpZ - RUN/2 - PLATEAU_WIDTH/2;
        const plateau = new THREE.Mesh(
            new THREE.BoxGeometry(3.0, peakHeight, PLATEAU_WIDTH),
            obstMat,
        );
        plateau.position.set(0, peakHeight / 2, plateauFrontZ);
        plateau.castShadow = true; plateau.receiveShadow = true;
        scene.add(plateau);
        bumpMeshes.push({ mesh: plateau, half: { x: 1.5, y: peakHeight / 2, z: PLATEAU_WIDTH / 2 } });
        // Down-stairs: descending from peak. First down-stair top is at
        // (peak - RISE), each subsequent step drops by RISE. Stop when
        // we'd hit/pass the ground (h <= 0).
        const downStartZ = plateauFrontZ - PLATEAU_WIDTH/2 - RUN/2;
        for (let i = 0; i < NUM_DOWN; i++) {
            const h = peakHeight - (i + 1) * RISE;
            if (h <= 0) break;
            const z = downStartZ - i * RUN;
            const m = new THREE.Mesh(new THREE.BoxGeometry(3.0, h, RUN), obstMat);
            m.position.set(0, h / 2, z);
            m.castShadow = true; m.receiveShadow = true;
            scene.add(m);
            bumpMeshes.push({ mesh: m, half: { x: 1.5, y: h / 2, z: RUN / 2 } });
        }
        console.log(`${TAG} pyramid stairs: ${NUM_UP}up + ${PLATEAU_WIDTH}m plateau + ${NUM_DOWN}down @ ${RISE}m × ${RUN}m, peak=${peakHeight.toFixed(2)}m`);
    } else if (TC.type === 'ramp_pyramid') {
        // Ramp up + flat plateau + ramp down.
        const angleRad = TC.angleDeg * Math.PI / 180;
        const horizLen = TC.horizLen;
        const rise = horizLen * Math.tan(angleRad);
        const rampLength = Math.sqrt(horizLen ** 2 + rise ** 2);
        const rampThickness = 0.5;
        const cos = Math.cos(angleRad);
        const sin = Math.sin(angleRad);
        const PLATEAU_WIDTH = TC.plateauWidth ?? 3.0;
        // Up ramp
        const yOff = (rampThickness/2)*cos - (rampLength/2)*sin;
        const zOff = (rampThickness/2)*sin + (rampLength/2)*cos;
        const upRamp = new THREE.Mesh(new THREE.BoxGeometry(3.0, rampThickness, rampLength), obstMat);
        upRamp.rotation.x = angleRad;
        upRamp.position.set(0, -yOff, FIRST_Z - zOff);
        upRamp.castShadow = true; upRamp.receiveShadow = true;
        scene.add(upRamp);
        bumpMeshes.push({ mesh: upRamp, half: { x: 1.5, y: rampThickness/2, z: rampLength/2 } });
        // Plateau at peak
        const peakZ = FIRST_Z - horizLen;
        const plateau = new THREE.Mesh(
            new THREE.BoxGeometry(3.0, rise, PLATEAU_WIDTH),
            obstMat,
        );
        plateau.position.set(0, rise / 2, peakZ - PLATEAU_WIDTH/2);
        plateau.castShadow = true; plateau.receiveShadow = true;
        scene.add(plateau);
        bumpMeshes.push({ mesh: plateau, half: { x: 1.5, y: rise/2, z: PLATEAU_WIDTH/2 } });
        // Down ramp — mirror of up ramp on the other side of plateau
        const downRampStartZ = peakZ - PLATEAU_WIDTH;
        const downRamp = new THREE.Mesh(new THREE.BoxGeometry(3.0, rampThickness, rampLength), obstMat);
        downRamp.rotation.x = -angleRad;  // opposite tilt: top in +Z direction
        // Position so its top-surface +Z corner is at (0, rise, downRampStartZ).
        // After rotation.x = -angleRad: top-surface +Z corner offset from center = (0, (t/2)cos + (L/2)sin, -(t/2)sin + (L/2)cos)
        const yOffDown = (rampThickness/2)*cos + (rampLength/2)*sin;
        const zOffDown = -(rampThickness/2)*sin + (rampLength/2)*cos;
        downRamp.position.set(0, rise - yOffDown, downRampStartZ - zOffDown);
        downRamp.castShadow = true; downRamp.receiveShadow = true;
        scene.add(downRamp);
        bumpMeshes.push({ mesh: downRamp, half: { x: 1.5, y: rampThickness/2, z: rampLength/2 } });
        console.log(`${TAG} pyramid ramp: ${TC.angleDeg}° up + ${PLATEAU_WIDTH}m plateau + ${TC.angleDeg}° down, peak=${rise.toFixed(2)}m`);
    } else if (TC.type === 'obstacle_course') {
        // Chain of varied obstacles. Each segment advances cursorZ. Final
        // forward distance = FIRST_Z - cursorZ. Spec via TC.segments:
        //   { kind: 'flat',  length: 2 }
        //   { kind: 'bump',  height: 0.10, depth: 0.40, width: 1.0 }
        //   { kind: 'stairs', rise: 0.18, run: 0.28, num: 8, dir: 'up'|'down' }
        //   { kind: 'ramp',  angleDeg: 15, horizLen: 3, dir: 'up'|'down' }
        // dir defaults to 'up'. Floor height at end of one segment becomes
        // floor for the next, so transitions are seamless.
        const segments = TC.segments ?? [];
        let cursorZ = FIRST_Z;
        let cursorY = 0;  // floor Y at current segment start
        for (let segIndex = 0; segIndex < segments.length; segIndex++) {
            const seg = segments[segIndex];
            const startZ = cursorZ;
            const startY = cursorY;
            const k = seg.kind;
            if (k === 'flat') {
                // Pure-flat segments don't need a mesh (the big ground plane
                // covers them) but if cursorY > 0 they need a raised slab.
                if (cursorY > 0.001) {
                    const len = seg.length;
                    const m = new THREE.Mesh(new THREE.BoxGeometry(3.0, cursorY, len), obstMat);
                    m.position.set(0, cursorY / 2, cursorZ - len / 2);
                    m.castShadow = true; m.receiveShadow = true;
                    scene.add(m);
                    bumpMeshes.push({ mesh: m, half: { x: 1.5, y: cursorY / 2, z: len / 2 } });
                }
                cursorZ -= seg.length;
            } else if (k === 'bump') {
                const h = seg.height, d = seg.depth, w = seg.width ?? 1.0;
                // Sit the bump on the current floor (cursorY).
                const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), obstMat);
                m.position.set(0, cursorY + h / 2, cursorZ - d / 2);
                m.castShadow = true; m.receiveShadow = true;
                scene.add(m);
                bumpMeshes.push({ mesh: m, half: { x: w / 2, y: h / 2, z: d / 2 } });
                cursorZ -= d;
                // Floor stays at cursorY (bump is an obstacle, not a step).
            } else if (k === 'dome') {
                // Half-sphere obstacle to walk over — curved surface for
                // testing IK adaptation. Mesh is a hemisphere (sphere top
                // half), physics collider is a Ball with center at floor
                // level so only the upper hemisphere is exposed.
                const r = seg.radius ?? 0.40;
                const geo = new THREE.SphereGeometry(r, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2);
                const m = new THREE.Mesh(geo, obstMat);
                m.position.set(0, cursorY, cursorZ - r);
                m.castShadow = true; m.receiveShadow = true;
                scene.add(m);
                bumpMeshes.push({ mesh: m, ballRadius: r });
                cursorZ -= 2 * r;
                // Floor stays at cursorY (dome is an obstacle, not a step).
            } else if (k === 'stairs') {
                const rise = seg.rise, run = seg.run, num = seg.num;
                const dir = seg.dir ?? 'up';
                for (let i = 0; i < num; i++) {
                    const stepTop = (dir === 'up')
                        ? (cursorY + rise * (i + 1))
                        : (cursorY - rise * (i + 1));
                    // Skip degenerate steps (descent ending exactly at floor).
                    if (stepTop <= 0.001) continue;
                    const stepZ = cursorZ - i * run - run / 2;
                    const m = new THREE.Mesh(new THREE.BoxGeometry(3.0, stepTop, run), obstMat);
                    m.position.set(0, stepTop / 2, stepZ);
                    m.castShadow = true; m.receiveShadow = true;
                    scene.add(m);
                    bumpMeshes.push({ mesh: m, half: { x: 1.5, y: stepTop / 2, z: run / 2 } });
                }
                cursorZ -= num * run;
                cursorY = (dir === 'up')
                    ? (cursorY + rise * num)
                    : (cursorY - rise * num);
            } else if (k === 'wall') {
                // Cover-height obstacle spanning the course — vault / climb
                // target (the controller's maneuver system handles it).
                const h = seg.height ?? 0.9, d = seg.depth ?? 0.35, w = seg.width ?? 3.0;
                const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), obstMat);
                m.position.set(0, cursorY + h / 2, cursorZ - d / 2);
                m.castShadow = true; m.receiveShadow = true;
                scene.add(m);
                bumpMeshes.push({ mesh: m, half: { x: w / 2, y: h / 2, z: d / 2 } });
                cursorZ -= d;
                // Floor stays at cursorY (a wall is an obstacle, not a step).
            } else if (k === 'gap') {
                // A void between raised slabs — jump target. Only meaningful
                // when the course floor is raised (cursorY > 0); at ground
                // level the big ground plane fills it.
                cursorZ -= seg.length;
            } else if (k === 'ladder') {
                // A tall block with ladder rungs on the approach face. The
                // course floor continues on TOP (cursorY rises by height) —
                // scale it with climbLadder(). Rungs are visual; the flat
                // face is the collider.
                const h = seg.height ?? 2.5, d = seg.depth ?? 0.5, w = seg.width ?? 3.0;
                const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), obstMat);
                m.position.set(0, cursorY + h / 2, cursorZ - d / 2);
                m.castShadow = true; m.receiveShadow = true;
                scene.add(m);
                bumpMeshes.push({ mesh: m, half: { x: w / 2, y: h / 2, z: d / 2 } });
                const railMat = new THREE.MeshStandardNodeMaterial({ color: 0xb8c2cc, metalness: 0.7, roughness: 0.35 });
                const railW = 0.5;
                // Rails + rungs are deliberate attached fixtures — declare
                // them to the placement audit or it "rescues" them: hovering
                // rungs get snapped to the ground and rail-intersecting ones
                // get shoved into a bunch (this exact ladder shipped mangled
                // until the probe dump caught the audit doing it).
                const markFixture = (o) => {
                    o.userData.noSupportCheck = true;
                    o.userData.noClippingCheck = true;
                    o.userData.allowIntersect = true;
                    o.userData.noZFightCheck = true;
                };
                for (const sx of [-railW / 2, railW / 2]) {
                    const rail = new THREE.Mesh(new THREE.BoxGeometry(0.06, h, 0.06), railMat);
                    rail.position.set(sx, cursorY + h / 2, cursorZ + 0.09);
                    rail.castShadow = true;
                    markFixture(rail);
                    scene.add(rail);
                }
                for (let ry = cursorY + 0.25; ry < cursorY + h - 0.05; ry += 0.28) {
                    const rung = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.028, railW, 10), railMat);
                    rung.rotation.z = Math.PI / 2;
                    rung.position.set(0, ry, cursorZ + 0.09);
                    rung.castShadow = true;
                    markFixture(rung);
                    scene.add(rung);
                }
                cursorZ -= d;
                cursorY += h;
            } else if (k === 'ramp') {
                const ang = seg.angleDeg * Math.PI / 180;
                const hl = seg.horizLen;
                const dir = seg.dir ?? 'up';
                const rise = hl * Math.tan(ang);
                const rampLen = Math.sqrt(hl * hl + rise * rise);
                const thick = 0.5;
                const cs = Math.cos(ang), sn = Math.sin(ang);
                const tilt = (dir === 'up') ? ang : -ang;
                const m = new THREE.Mesh(new THREE.BoxGeometry(3.0, thick, rampLen), obstMat);
                m.rotation.x = tilt;
                if (dir === 'up') {
                    const cy = cursorY + rise / 2 - (thick / 2) * cs;
                    const cz = cursorZ - hl / 2 + (thick / 2) * sn;
                    m.position.set(0, cy, cz);
                } else {
                    const cy = cursorY - rise / 2 - (thick / 2) * cs;
                    const cz = cursorZ - hl / 2 - (thick / 2) * sn;
                    m.position.set(0, cy, cz);
                }
                m.castShadow = true; m.receiveShadow = true;
                scene.add(m);
                bumpMeshes.push({ mesh: m, half: { x: 1.5, y: thick / 2, z: rampLen / 2 } });
                cursorZ -= hl;
                cursorY = (dir === 'up') ? (cursorY + rise) : (cursorY - rise);
            } else {
                throw new Error(`obstacle_course: unknown segment kind: ${k}`);
            }
            terrainTelemetrySegments.push({
                index: segIndex,
                kind: k,
                dir: seg.dir ?? null,
                label: `${segIndex}:${k}${seg.dir ? ':' + seg.dir : ''}`,
                startZ: _locNum(startZ),
                endZ: _locNum(cursorZ),
                startY: _locNum(startY),
                endY: _locNum(cursorY),
                length: _locNum(startZ - cursorZ),
                rise: _locNum(seg.rise),
                run: _locNum(seg.run),
                num: seg.num ?? null,
                angleDeg: _locNum(seg.angleDeg),
                height: _locNum(seg.height),
                depth: _locNum(seg.depth),
                radius: _locNum(seg.radius),
            });
            if (cursorY < -0.001) {
                throw new Error(`obstacle_course: cursorY went negative (${cursorY.toFixed(3)}) after segment ${JSON.stringify(seg)} — descent segment outsized the running height. Rebalance the course so cumulative rise stays ≥ 0.`);
            }
        }
        console.log(`${TAG} obstacle_course: ${segments.length} segments, traveled ${(FIRST_Z - cursorZ).toFixed(2)}m, final floor Y=${cursorY.toFixed(2)}`);
    } else {
        throw new Error(`unknown TERRAIN_CONFIG.type: ${TC.type}`);
    }
    globalThis._terrainTelemetrySegments = terrainTelemetrySegments;

    // The terrain pieces ARE the walkable ground — exempt them from the
    // prop-support audit (rotated ramps/plateaus read as "floating" to the
    // bbox footprint sampler even though they're the surface itself).
    ground.userData.noSupportCheck = true;
    for (const entry of bumpMeshes) entry.mesh.userData.noSupportCheck = true;

    // --- Load the character VRM ---
    const loader = new GLTFLoader();
    loader.register((parser) => new globalThis.VRMLoaderPlugin(parser));
    const vrmAsset = globalThis.ASSETS['character_vrm'];
    if (!vrmAsset) throw new Error(`${TAG} ASSETS.character_vrm missing`);
    const gltf = await new Promise((res, rej) =>
        loader.parse(b64toArrayBuffer(vrmAsset), '', res, rej));
    const vrm = gltf.userData.vrm;
    vrm.scene.traverse((c) => {
        if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; }
    });
    scene.add(vrm.scene);
    globalThis._vrm = vrm;

    const bbox = new THREE.Box3().setFromObject(vrm.scene);
    const vrmHeight = bbox.max.y - bbox.min.y;
    const vrmFootY = bbox.min.y;
    console.log(`${TAG} VRM height=${vrmHeight.toFixed(3)} footY=${vrmFootY.toFixed(3)}`);

    // --- Rapier setup ---
    // Import via the resolved file path first: the npm: specifier makes deno
    // (re)wire the node_modules symlink, which fails with 'File exists
    // (os error 17)' when the link was created by a different uid. The
    // direct path needs no linking at all.
    try {
        RAPIER = await import('file:///workspace/node_modules/.deno/@dimforge+rapier3d-compat@0.14.0/node_modules/@dimforge/rapier3d-compat/rapier.es.js')
            .then(m => m.default || m);
    } catch (e) {
        RAPIER = await import("npm:@dimforge/rapier3d-compat@0.14.0").then(m => m.default || m);
    }
    await RAPIER.init();

    const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
    world.integrationParameters.dt = 1 / FPS;

    const addStatic = (mesh, halfExtents) => {
        const body = world.createRigidBody(RAPIER.RigidBodyDesc.fixed());
        body.setTranslation({ x: mesh.position.x, y: mesh.position.y, z: mesh.position.z }, true);
        body.setRotation({
            x: mesh.quaternion.x, y: mesh.quaternion.y,
            z: mesh.quaternion.z, w: mesh.quaternion.w,
        }, true);
        world.createCollider(
            RAPIER.ColliderDesc.cuboid(halfExtents.x, halfExtents.y, halfExtents.z),
            body,
        );
    };
    const addStaticConvexHull = (mesh, vertices) => {
        // Vertices are already in world coordinates — rigid body at origin
        // with no rotation, collider holds the world-space hull.
        const body = world.createRigidBody(RAPIER.RigidBodyDesc.fixed());
        const colliderDesc = RAPIER.ColliderDesc.convexHull(vertices);
        if (!colliderDesc) {
            console.warn('[obstacle_course] convex hull failed for wedge — falling back to no collider');
            return;
        }
        world.createCollider(colliderDesc, body);
    };
    const addStaticBall = (mesh, radius) => {
        // Ball collider centered at the mesh position. For half-sphere
        // dome obstacles: mesh is the top hemisphere, ball center sits at
        // floor level (bottom of hemisphere), so the lower half of the
        // collider sphere is buried in the ground plane.
        const body = world.createRigidBody(RAPIER.RigidBodyDesc.fixed());
        body.setTranslation({ x: mesh.position.x, y: mesh.position.y, z: mesh.position.z }, true);
        world.createCollider(RAPIER.ColliderDesc.ball(radius), body);
    };
    {
        const body = world.createRigidBody(RAPIER.RigidBodyDesc.fixed());
        body.setTranslation({ x: 0, y: -0.05, z: 0 }, true);
        world.createCollider(RAPIER.ColliderDesc.cuboid(groundHalf, 0.05, groundHalf), body);
    }
    for (const entry of bumpMeshes) {
        if (entry.convexHull) {
            addStaticConvexHull(entry.mesh, entry.convexHull);
        } else if (entry.ballRadius) {
            addStaticBall(entry.mesh, entry.ballRadius);
        } else {
            addStatic(entry.mesh, entry.half);
        }
    }

    // The engine preloads this via HELPER_MODULES; keep a fallback so
    // the scene remains runnable standalone.
    if (!globalThis.VRMCharacterController) {
        const code = await Deno.readTextFile('eidoverse/character_controller.js');
        (0, eval)(code);
    }
    if (!globalThis.VRMCharacterController) throw new Error(`${TAG} VRMCharacterController class not loaded`);
    const charCtrl = new globalThis.VRMCharacterController(vrm, world, RAPIER, {
        startPosition: [0, 0, 5],
        footStanceX: 0.11,
        useContactSupportLift: true,
        contactSupportLiftMin: 0.025,
        contactSupportLiftMax: 0.18,
        contactSupportLiftRatio: 0.58,
        contactSupportSwingRatio: 0.32,
        contactSupportMaxRampAngle: 50,
        useIKContactSupportLift: true,
        ikContactSupportLiftRatio: 0.42,
        ikContactSupportSwingRatio: 0.18,
        ikContactSoleGapMax: 0.16,
        allowRaisedSupportDuringDescent: true,
        raisedSupportMinLift: 0.045,
        raisedSupportAheadMin: 0.035,
        raisedSupportFinishGap: 0.015,
        raisedSupportLatchFrames: 3,
        raisedSupportMaxSpread: 0.18,
        useIKGroundingGrace: true,
        ikGroundingGraceMaxDrop: 0.34,
        ikGroundingGraceMaxRise: 0.08,
        ikGroundingGraceMaxSoleGap: 0.56,
        preferWalkOnUntreadedObstacles: true,
        obstacleWalkMaxRise: 0.18,
        obstacleWalkMaxSpread: 0.18,
        requireConfirmedStairClips: true,
        confirmedStairHoldFrames: 12,
        bodyYRateUp: 1.35,
        bodyYRateDown: 1.25,
        yAverageWindowSize: 3,
    });

    // Controller owns its mixer and animation actions. One call loads
    // all standard locomotion clips (walk, run, idle, stairs variants,
    // fall) from the global VRMA library and strips tracks that would
    // fight the controller's pose overrides.
    await charCtrl.loadStandardAnimations();

    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;
    globalThis._charCtrl = charCtrl;
    globalThis._mixer = charCtrl._mixer;
    globalThis._tag = TAG;

    // The engine preloads this via HELPER_MODULES; keep a fallback so
    // the scene remains runnable standalone.
    if (!globalThis.VRMFootControllerIK) {
        const code = await Deno.readTextFile('eidoverse/foot_ik.js');
        (0, eval)(code);
    }
    if (!globalThis.VRMFootControllerIK) throw new Error(`${TAG} VRMFootControllerIK class not loaded`);
    const ik = new globalThis.VRMFootControllerIK(vrm, {
        world, RAPIER, collider: charCtrl.collider,
        // Toes back ON for slopes/ramps (anim authors toe pose for
        // angled surfaces). For stairs the edge cases are now handled
        // by spherecast (CastType.RayAndSphere below).
        increasedAccuracy: true,
        // Fixed-knee solver path — the non-fixed path made descent
        // poses more likely to fold across risers.
        fixKnee: true,
        // FootHeightOffset is an offset SUBTRACTED from the per-VRM
        // `distanceFromMesh` (= footBoneY − rootY − vrmBboxMinY, computed
        // dynamically per VRM at init). Setting this to 0 means the IK
        // uses the full dynamic bone-to-sole offset, so the mesh SOLE
        // (not the bone) plants at the raycast ground for whichever VRM
        // is loaded. Setting it positive pushes the bone toward the
        // ground (sole below ground); negative lifts it (sole above).
        FootHeightOffset: 0.012,
        // Cast type 2 = RayAndSphere: try single raycast first; if it
        // misses or hits a wall/edge (normal too horizontal), fall
        // back to spherecast emulation (8 rays in a ring around the
        // bone XZ + center, picks highest upward-facing surface).
        type: 2,
        // Small radius: bridges sub-cm geometry seams (the actual real
        // problem) without reaching across stair-tread edges (a 5cm ball
        // catches the next tread edge ~2.5cm before the foot xz actually
        // crosses it, biasing the foot up onto the higher tread early).
        sphereRadius: 0.015,
        MaxStepHeight: 0.6,
        // Target smoothing — with the partial-toe math in foot_ik.js,
        // snapping directly to stair-edge raycasts is more harmful than
        // helpful.
        DistancePower: 1,
        SmoothingAngle: 2,
        GlobalSmoothingPower: 0,
        meshHeightOffset: vrmFootY,  // computed from VRM bbox.min.y at init
    });
    globalThis._legIK = ik;

    // Hand off all per-frame locomotion responsibility to the controller:
    // mixer, animation actions, IK module. After this, renderFrame just
    // calls charCtrl.locomote(dt, direction) and the controller owns
    // everything (forward speed, anim weights, treadRun smoothing,
    // timeScale, hip lean, head pitch, body Y drop, foot IK offset,
    // descentContext, IK update). Test scenes are thin harnesses.
    // Controller already owns mixer + actions from loadStandardAnimations.
    // Just hand it the leg IK module.
    charCtrl.attachLocomotion({ legIK: ik });
};

let _logSec = -1;
globalThis.renderFrame = async function (t, frameIndex = null) {
    const dt = 1 / 30;
    const charCtrl = globalThis._charCtrl;
    const vrm = globalThis._vrm;
    const TAG = globalThis._tag;

    // ─── ENGINE CALL ───────────────────────────────────────────────────
    // The controller's locomote() owns the full per-frame stack:
    // forward speed, anim weights (with shape-adaptive engagement
    // lambdas + treadRun smoothing + timeScale), hip lean, head pitch,
    // body Y drop, foot IK config, IK update. Test scenes are thin.
    charCtrl.locomote(dt, { z: -1 });
    vrm.update(dt);
    _locRecordTelemetry(t, frameIndex, dt, charCtrl);

    // Local refs for logging + camera (read-only from controller state):
    const t2 = charCtrl.bodyTranslation;
    const speedActual = charCtrl.speedActual;
    const climbAngle = charCtrl.climbAngleDeg ?? 0;

    // ─── (rest of function below is logging + camera only) ──────────
    if (false) {  // skipped — legacy inlined locomotion below intentionally dead
    const FLAT_SPEED = 1.5;
    const STAIR_CADENCE = 2.5;  // multiplier on natural stride rate — 1.0 = anim-native, higher = brisker stair pace
    const stairsClipDur = globalThis._stairsUpAction?.getClip?.()?.duration ?? 1.0;
    const _treadRunForSpeed = charCtrl.aheadTreadRun ?? null;
    let targetForwardSpeed = FLAT_SPEED;
    if (_treadRunForSpeed !== null && (charCtrl.aheadProbeSpread ?? 0) > 0.10) {
        // Stair detected — set forward velocity so anim cycle covers exactly
        // 2 tread runs (one footplant per tread), scaled by STAIR_CADENCE.
        targetForwardSpeed = (2 * _treadRunForSpeed * STAIR_CADENCE) / stairsClipDur;
    }
    if (globalThis._smoothFwdSpeed === undefined) globalThis._smoothFwdSpeed = FLAT_SPEED;
    globalThis._smoothFwdSpeed = THREE.MathUtils.lerp(globalThis._smoothFwdSpeed, targetForwardSpeed, Math.min(1, 3 * dt));

    charCtrl.update(dt, { z: -globalThis._smoothFwdSpeed });
    const t2 = charCtrl.bodyTranslation;
    const grounded = charCtrl.grounded;
    const speedActual = charCtrl.speedActual;
    const moving = speedActual > 0.3;

    const walkAction = globalThis._walkAction;
    const idleAction = globalThis._idleAction;
    const stairsUpAction = globalThis._stairsUpAction;
    const stairsDownAction = globalThis._stairsDownAction;
    const fallIdleAction = globalThis._fallIdleAction;
    const lastBodyY = globalThis._lastBodyY ?? t2.y;
    const bodyVelY = (t2.y - lastBodyY) / dt;
    globalThis._lastBodyY = t2.y;
    const ASCEND_THRESHOLD = 0.4;
    const DESCEND_THRESHOLD = -0.4;
    const ascending = grounded && moving && bodyVelY >  ASCEND_THRESHOLD;
    const descending = grounded && moving && bodyVelY < DESCEND_THRESHOLD;

    const climbAngle = charCtrl.climbAngleDeg ?? 0;
    const climbBlocked = charCtrl._climbBlocked ?? false;
    // Stair detection via FORWARD PROBE SPREAD with sticky window.
    // Probe spread is naturally intermittent on stairs — when the body
    // is mid-tread, all 5 forward probes can hit the same tread giving
    // spread=0; just before/after the tread edge they hit different
    // treads giving spread=stair-rise. A raw threshold pops the anim
    // between walk and stairs every ~250ms, producing the visible
    // "jittery mess" on stairs_small (small rise = thinner detection
    // margin = more popping).
    //
    // Fix: maintain a 1-second history. If spread exceeded 0.10m at any
    // point in the last second, keep stair anim ON. Walk/stair toggle is
    // smoothed to once-per-second instead of once-per-stride.
    const probeSpread = charCtrl.aheadProbeSpread ?? 0;
    if (!globalThis._spreadHistory) globalThis._spreadHistory = [];
    globalThis._spreadHistory.push(probeSpread);
    if (globalThis._spreadHistory.length > 30) globalThis._spreadHistory.shift();
    let maxRecentSpread = 0;
    for (const v of globalThis._spreadHistory) {
        if (v > maxRecentSpread) maxRecentSpread = v;
    }
    const stairAhead = grounded && moving && maxRecentSpread > 0.10 && !climbBlocked;

    // Choose stair anim direction by looking ahead. The probe spread
    // detects "stairs are present" (up or down); the highest/lowest
    // probe Y deltas tell us the DIRECTION. If highest probe is well
    // above current feet → ascent ahead; if lowest probe is well below
    // → descent ahead. Use this to route stairAhead to stairsUp or
    // stairsDown anim while still on flat ground approaching the
    // transition (preempt, before bodyVelY actually changes).
    const aheadHigh = charCtrl.aheadHighestDelta ?? 0;
    const aheadLow  = charCtrl.aheadLowestDelta  ?? 0;
    // Ascent threshold lowered to 0.08 (was 0.10 strict): rise=0.10 stairs
    // reports aheadHigh = 0.10 ± epsilon, and strict `> 0.10` would miss
    // them. 0.08 gives a stable margin without firing on the 0.06 bumps
    // in the warmup section.
    // Descent threshold kept at -0.10: shallow downramps (8°) read
    // aheadLow ≈ -0.05; lowering would let stairDownAhead fire on smooth
    // ramps and contaminate the flat-walk anim with stair-anim transients.
    const stairUpAhead = stairAhead && aheadHigh > 0.08;
    const stairDownAhead = stairAhead && aheadLow < -0.10;

    let targetIdle = 0, targetWalk = 0, targetStairsUp = 0, targetStairsDown = 0, targetFall = 0;
    if (!grounded && fallIdleAction) targetFall = 1;
    else if (!moving) targetIdle = 1;
    else if ((ascending || stairUpAhead) && stairsUpAction) targetStairsUp = 1;
    else if ((descending || stairDownAhead) && stairsDownAction) targetStairsDown = 1;
    else targetWalk = 1;

    const enteringIdle = !moving;
    const blendLambda = (!grounded ? 20 : (enteringIdle ? 18 : 8));
    // Stair-anim disengagement uses 18 lambda (vs default 8) so the
    // residual "step up/down" foot trajectory doesn't bleed past the
    // plateau as a ghost-step into the air.
    //
    // Stair-anim engagement gets a boost SPECIFICALLY when a tall riser
    // (>0.20m) is detected ahead via the forward probe. Default lambda 8
    // reaches ~80% in the 0.35m approach window, leaving 20% walk-anim
    // bleeding into the first step. On small/normal stairs that 20%
    // bleed is tolerable (legs lift just enough for 10–18cm risers).
    // On large stairs (0.22m+ risers) the 20% bleed = body rises 11cm
    // anticipation while legs are still in flat-walk posture → reads as
    // "slides up before stepping". Triggered ONLY when the upcoming
    // riser exceeds 0.20m, so small (0.10) and normal (0.18) stairs
    // keep the default soft blend.
    const stairLeavingLambda  = 18;
    const aheadH_anim = charCtrl.aheadHighestDelta ?? 0;
    const tallRiserAhead = aheadH_anim > 0.20;
    const stairEngagingLambda = tallRiserAhead ? 16 : blendLambda;
    const dampStair = (cur, tgt) => THREE.MathUtils.damp(cur, tgt,
        (tgt === 0 && cur > 0.01)            ? stairLeavingLambda :
        (tgt > 0   && cur < 0.5)             ? stairEngagingLambda :
        blendLambda, dt);
    const damp = (cur, target) => THREE.MathUtils.damp(cur, target, blendLambda, dt);
    if (idleAction)       idleAction.weight       = damp(idleAction.weight, targetIdle);
    if (walkAction)       walkAction.weight       = damp(walkAction.weight, targetWalk);
    if (stairsUpAction)   stairsUpAction.weight   = dampStair(stairsUpAction.weight, targetStairsUp);
    if (stairsDownAction) stairsDownAction.weight = dampStair(stairsDownAction.weight, targetStairsDown);
    if (fallIdleAction)   fallIdleAction.weight   = damp(fallIdleAction.weight, targetFall);

    const NATIVE_WALK_SPEED = 1.5;
    const walkRatio   = Math.min(speedActual / NATIVE_WALK_SPEED, 1.3);
    if (walkAction) walkAction.timeScale = walkRatio;

    // Sync stair anim cadence to actual forward motion via detected geometry:
    // one anim cycle = one footplant per tread × 2 footplants per cycle =
    // 2 × tread_run of forward distance. timeScale = clipDur × speed / (2R).
    // Smooth treadRun across frames to avoid timeScale jitter when the
    // raycast detector flips between detected and not-detected.
    // The treadRun detector returns null on flat ground (no transitions in
    // the forward probe array) AND intermittently on stairs (when the probe
    // window happens to all-hit the same tread). When raw is null, HOLD
    // the last smoothed value rather than decaying toward a hardcoded
    // fallback — otherwise the anim cadence drifts toward whatever the
    // fallback happens to be (0.28 here) regardless of the actual stair
    // geometry, and the anim foot plants miss the treads on differently-
    // shaped stairs.
    const treadRunRaw = charCtrl.aheadTreadRun;
    if (globalThis._smoothTreadRun === undefined) globalThis._smoothTreadRun = 0.28;
    if (treadRunRaw !== null && treadRunRaw !== undefined) {
        // Faster convergence so transitioning from flat (or one stair size
        // to another) syncs the anim cadence within ~3 frames instead of
        // dragging for half a second.
        globalThis._smoothTreadRun = THREE.MathUtils.lerp(
            globalThis._smoothTreadRun, treadRunRaw, Math.min(1, 12 * dt),
        );
    }
    const treadRun = globalThis._smoothTreadRun;
    const stairsCycleDistance = 2 * treadRun;
    if (stairsUpAction) {
        const clipDur = stairsUpAction.getClip().duration;
        const k = (speedActual * clipDur) / stairsCycleDistance;
        stairsUpAction.timeScale = Math.max(0.2, Math.min(k, 3.0));  // raised cap
    }
    if (stairsDownAction) {
        const clipDur = stairsDownAction.getClip().duration;
        const k = (speedActual * clipDur) / stairsCycleDistance;
        stairsDownAction.timeScale = Math.max(0.2, Math.min(k, 3.0));  // raised cap
    }

    globalThis._mixer.update(dt);

    // Override head pitch from actual climb angle (not from anim).
    // The walk / stairsUp / stairsDown clips bake their own head movements
    // that don't match real terrain — e.g. she "looks up" while walking
    // over a 6cm bump (stairsUp anim) or "looks forward" while descending
    // a ramp (walk anim). Replace with motion-driven pitch so she always
    // looks along the actual angle of travel, regardless of clip.
    //
    // Plus body LEAN — pitch the hips bone forward by a fraction of the
    // motion angle so she leans into ascents and over the slope on
    // descents (real human gait does this; the flat-walk anim alone keeps
    // her upright on ramps). Lean is INTO the slope for both directions
    // (forward in body-frame regardless of whether climbing or descending).
    //
    // The head pitch then SUBTRACTS the hip lean's contribution so the
    // head's WORLD pitch still ends up at the signed climb angle (looking
    // along motion direction).
    let hipsLeanDeg = 0;
    if (vrm.humanoid) {
        const hipsBone = vrm.humanoid.getNormalizedBoneNode('hips');
        if (hipsBone) {
            // Both ascent and descent use a gentle hip lean — most of the
            // slope-walking visual comes from body-Y movement + head tilt,
            // not from pitching the torso. A heavy forward lean masks
            // the Y-crouch and reads as over-committing on gentle ramps.
            // (Descent gets a tiny bit more lean than ascent — real
            // walking down a slope does lean slightly forward to absorb
            // foot-strike, while up-walking is more vertical.)
            const climbForLean = charCtrl.signedClimbAngleDeg ?? 0;
            const HIP_LEAN_ASCENT  = 0.30;
            const HIP_LEAN_DESCENT = 0.40;
            const leanFactor = climbForLean >= 0 ? HIP_LEAN_ASCENT : HIP_LEAN_DESCENT;
            // Only lean when the walk anim is dominant. Stair clips have
            // authored lean already; double-stacking looks wrong.
            const walkW = walkAction?.weight ?? 0;
            const leanGate = Math.max(0, Math.min(1, walkW));
            const targetLean = Math.abs(climbForLean) * leanFactor * leanGate;
            if (globalThis._smoothHipsLeanDeg === undefined) globalThis._smoothHipsLeanDeg = 0;
            const k = Math.min(1, dt * 6);  // λ=6 → ~170ms time constant
            globalThis._smoothHipsLeanDeg =
                globalThis._smoothHipsLeanDeg * (1 - k) + targetLean * k;
            hipsLeanDeg = globalThis._smoothHipsLeanDeg;
            // Premultiply rather than replace so the anim's authored hip
            // motion (walk bob etc) is preserved — we just add the pitch.
            const pitchRad = hipsLeanDeg * Math.PI / 180;
            const pitchQuat = new THREE.Quaternion().setFromAxisAngle(
                new THREE.Vector3(1, 0, 0), pitchRad);
            hipsBone.quaternion.premultiply(pitchQuat);
        }
        const headBone = vrm.humanoid.getNormalizedBoneNode('head');
        if (headBone) {
            if (!globalThis._headRestQuat) {
                globalThis._headRestQuat = headBone.quaternion.clone();
            }
            // Base head world-pitch target = travel direction. On
            // flat-walk-anim ascent/descent (below the threshold for the
            // stair-anim swap), add a bonus so she's clearly LOOKING up
            // or down the ramp — not just looking along the slope line.
            // Walk-anim-gated so stair anims (which have authored head
            // motion) aren't affected.
            const climbForHead = charCtrl.signedClimbAngleDeg ?? 0;
            const walkWHead = walkAction?.weight ?? 0;
            let headPitchBonus = 0;
            if (climbForHead > 0) {
                headPitchBonus = Math.min(6, climbForHead * 0.5) * walkWHead;     // up to +6°  (look up)
            } else if (climbForHead < 0) {
                headPitchBonus = Math.max(-6, climbForHead * 0.5) * walkWHead;    // up to -6°  (look down)
            }
            const targetAngleDeg = climbForHead + headPitchBonus;
            if (globalThis._smoothHeadPitchDeg === undefined) globalThis._smoothHeadPitchDeg = 0;
            const headLpK = Math.min(1, dt * 6);
            globalThis._smoothHeadPitchDeg =
                globalThis._smoothHeadPitchDeg * (1 - headLpK) + targetAngleDeg * headLpK;
            // VRM head bone: + X rotation tilts head DOWN (chin to chest).
            // We want WORLD head pitch = full signed climb angle. Hip lean
            // contributes `hipsLeanDeg` of forward tilt to the head's world
            // frame (positive forward) regardless of climb sign. To
            // achieve world pitch = signedClimb, head LOCAL pitch needs
            // to add (signedClimb - hipsLeanDeg) — but in head-bone-local
            // convention where + X = head down, we negate.
            const headLocalDeg = globalThis._smoothHeadPitchDeg - hipsLeanDeg * Math.sign(globalThis._smoothHeadPitchDeg || 1);
            const pitchRad = -headLocalDeg * Math.PI / 180;
            const pitchQuat = new THREE.Quaternion().setFromAxisAngle(
                new THREE.Vector3(1, 0, 0), pitchRad);
            headBone.quaternion.copy(globalThis._headRestQuat).multiply(pitchQuat);
        }
    }

    vrm.scene.position.copy(charCtrl.feetWorldPosition);
    // Lower body Y when walking down an incline (flat-walk anim). On a
    // descending slope the leading (front) foot lands well below the
    // body's xz-reference ground (by stride_offset × tan(angle), ~6 cm at
    // 12°). Without dropping the body, the hip-to-front-foot distance
    // exceeds rest leg length and the IK stretches the leg straight to
    // reach. Dropping the body lets the leg keep a natural bend.
    // Factor 0.010/° → ~12 cm drop at 12° (comparable to the geometric
    // stretch).
    {
        const angle = charCtrl.signedClimbAngleDeg ?? 0;
        const walkW = walkAction?.weight ?? 0;
        // Descent: deep crouch (0.018/°, ~14cm at 8°, ~21cm cap). The
        // geometric leg-stretch on a downslope is ~stride×sin(angle)
        // (≈7 cm at 8° for a 0.5m stride). Dropping by 2× geometric gives
        // visible knee bend on top of just-reaching the ground.
        // Ascent: gentler crouch (0.006/°, ~5cm at 8°) — replaces the
        // strong forward lean we removed above. Reads as "leg-lifting
        // effort" rather than "falling forward".
        // Stair-anim descent on a RAMP (not actual stairs): the stairsDown
        // clip authors a crouch tuned to step geometry, but on a continuous
        // steep ramp the front foot has to keep reaching further down. Add
        // a smaller stair-gated drop, but ONLY when the forward probe does
        // NOT detect real stair edges (i.e. we're on a ramp, not stairs —
        // actual stairs already work fine).
        let targetDrop;
        if (angle < 0) {
            targetDrop = Math.min(0.22, Math.abs(angle) * 0.018) * walkW;
        } else if (angle > 0) {
            targetDrop = Math.min(0.08, angle * 0.006) * walkW;
        } else {
            targetDrop = 0;
        }
        const stairsDownW = stairsDownAction?.weight ?? 0;
        // stairDownAhead fires on real stairs AND on steep continuous
        // ramps (the forward probe sees the floor below the threshold).
        // The clean ramp-vs-stairs distinguisher is aheadTreadRun: null
        // on smooth ramps (no Y-discontinuities in the probe array),
        // non-null on actual stairs.
        const onRampNotStairs = (charCtrl.aheadTreadRun ?? null) === null;
        if (angle < 0 && stairsDownW > 0.01 && onRampNotStairs) {
            // 0.006/° at 25° ≈ 15 cm extra. Cap 0.18m.
            targetDrop += Math.min(0.18, Math.abs(angle) * 0.006) * stairsDownW;
        }
        if (globalThis._smoothBodyDrop === undefined) globalThis._smoothBodyDrop = 0;
        const k = Math.min(1, dt * 6);
        globalThis._smoothBodyDrop = globalThis._smoothBodyDrop * (1 - k) + targetDrop * k;
        vrm.scene.position.y -= globalThis._smoothBodyDrop;
    }
    vrm.scene.rotation.y = Math.PI;

    const ik = globalThis._legIK;
    if (ik) {
        // Engage the descent workaround for broken stairsDown foot-Y data
        // (running-min upY baseline subtract in the foot IK) when actually
        // descending. Detected via
        // charCtrl.aheadLowestDelta — if forward probes drop noticeably below
        // current feet AND we're moving, it's descent.
        const aheadLow = charCtrl.aheadLowestDelta ?? 0;
        const movingForward = (charCtrl.speedActual ?? 0) > 0.3;
        ik.descentContext = movingForward && aheadLow < -0.05;

        // Foot-plant offset — shift foot raycasts along the foot's
        // toe direction so the foot mesh lands centered on each tread.
        //
        //   ASCENT  → +forward (heel on tread, not dangling off back)
        //   DESCENT → −backward (toe on tread, not dangling off front)
        //
        // Magnitude scales with ExtraLength (anatomical, derives from
        // the VRM rig's own ankle→toe length) — no hardcoded geometry.
        //
        // steepFactor scales DOWN as climb angle steepens: steep stairs
        // have shorter tread runs where any shift can cross the tread's
        // edge onto the next riser/tread → IK pulls foot to wrong height.
        // Threshold tightened to 25° (was 30°) so large stairs (40°)
        // get a fully-zero offset across the brief entry transient too.
        const stairsUpW_ik   = globalThis._stairsUpAction?.weight   ?? 0;
        const stairsDownW_ik = globalThis._stairsDownAction?.weight ?? 0;
        // Smoothed climb angle to avoid threshold thrashing on transients.
        const climbDegRaw = charCtrl.climbAngleDeg ?? 0;
        if (globalThis._smoothClimbDegIK === undefined) globalThis._smoothClimbDegIK = 0;
        {
            const lpK = Math.min(1, dt * 5);
            globalThis._smoothClimbDegIK = globalThis._smoothClimbDegIK * (1 - lpK) + climbDegRaw * lpK;
        }
        const climbDegIK = globalThis._smoothClimbDegIK;
        const steepFactor = Math.max(0, Math.min(1, (25 - climbDegIK) / 10));
        const sign = stairsUpW_ik >= stairsDownW_ik ? +1 : -1;
        // Ascent uses 0.5×ExtraLength (heel hangs off back so foot needs
        // a strong forward shift). Descent uses 0.3×ExtraLength — smaller
        // backward shift centers the foot on tread without lagging the
        // raycast behind the foot bone (which causes the "heel touches
        // current step before sliding to next" artifact during swing).
        const offsetMag = sign > 0 ? 0.5 : 0.3;
        const animW = Math.max(stairsUpW_ik, stairsDownW_ik);
        ik.footPlantForwardOffset = sign * offsetMag * animW * steepFactor;

        // Keep increasedAccuracy ON (re-enabled). Disabling it killed the
        // large-stairs first-step catch — without the toe (ExtraBone)
        // anticipation cast, the foot doesn't lift to meet upcoming
        // tread edges, and she slides up the riser instead of stepping
        // onto it. The toe-cast jitter on 0.22m risers is the lesser
        // evil compared to no anticipation at all.
        ik.increasedAccuracy = true;
        // Skip IK foot placement when airborne. Otherwise the IK keeps
        // trying to reach the (far-below) ground while the fallIdle anim
        // plays — legs stretch out straight before she hits the ground.
        if (grounded) {
            ik.update(dt);
        }
        charCtrl.externalGroundY = null;
    }
    }  // end if(false) — legacy dead block; locomote() owns everything above

    const sec = Math.floor(t);
    if (sec !== _logSec) {
        _logSec = sec;
        // Detailed body+legik state for descent debugging.
        const ik = globalThis._legIK;
        const lFootY = ik?.feet?.left?.raycastHitPoint?.y ?? 0;
        const rFootY = ik?.feet?.right?.raycastHitPoint?.y ?? 0;
        const lOffset = ik?.feet?.left?.positionOffset ?? 0;
        const rOffset = ik?.feet?.right?.positionOffset ?? 0;
        const lInStance = ik?.feet?.left?.inStance ? '1' : '0';
        const rInStance = ik?.feet?.right?.inStance ? '1' : '0';
        const aheadHigh = charCtrl.aheadHighestDelta?.toFixed(2) ?? '0.00';
        const aheadLow  = charCtrl.aheadLowestDelta?.toFixed(2) ?? '0.00';
        const detectedTread = charCtrl.aheadTreadRun?.toFixed(3) ?? 'null';
        const smoothTread = globalThis._smoothTreadRun?.toFixed(3) ?? 'null';
        const probeSpread = charCtrl.aheadProbeSpread?.toFixed(3) ?? '0';
        const fwdSpeedInput = charCtrl._smoothFwdSpeed?.toFixed(3) ?? '?';
        const sUpAction = charCtrl._actions?.stairsUp;
        const sDownAction = charCtrl._actions?.stairsDown;
        const sUpScale = sUpAction?.timeScale?.toFixed(2) ?? '?';
        const sUpW = sUpAction?.weight?.toFixed(2) ?? '?';
        const sDownW = sDownAction?.weight?.toFixed(2) ?? '?';
        console.log(`${TAG} t=${sec}s body=(${t2.x.toFixed(2)},${t2.y.toFixed(2)},${t2.z.toFixed(2)}) speed=${speedActual.toFixed(2)} fwdIn=${fwdSpeedInput} treadRaw=${detectedTread} treadSm=${smoothTread} spread=${probeSpread} climb=${climbAngle.toFixed(0)}° upW=${sUpW} downW=${sDownW} upScale=${sUpScale}`);
    }

    const cam = globalThis._c;
    if (globalThis.CAMERA_MODE === 'hands_closeup' && vrm?.humanoid) {
        const lh = vrm.humanoid.getRawBoneNode('leftHand');
        const rh = vrm.humanoid.getRawBoneNode('rightHand');
        if (lh && rh) {
            const lp = lh.getWorldPosition(new THREE.Vector3());
            cam.position.set(lp.x - 0.8, lp.y + 0.05, lp.z);
            cam.lookAt(lp.x, lp.y, lp.z);
        } else {
            cam.position.set(5.0, t2.y + 0.2, t2.z + 0.0);
            cam.lookAt(t2.x, t2.y - 0.5, t2.z);
        }
    } else if (globalThis.CAMERA_MODE === 'three_quarter') {
        // Three-quarter view: camera offset 35° from pure side toward the
        // character's front (she faces -Z after π Y rotation, so front = -Z).
        // Camera ABOVE the body (head height + extra elevation) and looks
        // DOWN at foot level so both face AND foot-plants on stairs are
        // visible during ascent (when body is high relative to stair line).
        const R = 5.0;
        const a = 35 * Math.PI / 180;
        cam.position.set(t2.x + R * Math.cos(a), t2.y + 1.0, t2.z - R * Math.sin(a));
        cam.lookAt(t2.x, t2.y - 0.5, t2.z);
    } else {
        cam.position.set(5.0, t2.y + 0.2, t2.z + 0.0);
        cam.lookAt(t2.x, t2.y - 0.5, t2.z);
    }

    await globalThis._r.renderAsync(globalThis._s, cam);
};

globalThis.cleanup = async function () {
    const state = globalThis._locomotionTelemetry;
    if (!state?.config?.enabled) return;
    const outputPath = state.config.outputPath
        ?? 'work/locomotion_telemetry.json';
    const summaryPath = state.config.summaryPath
        ?? outputPath.replace(/\.json$/i, '_summary.json');
    const summary = _locSummarizeTelemetry(state.frames);
    const payload = {
        generatedAt: new Date().toISOString(),
        terrainSegments: globalThis._terrainTelemetrySegments ?? [],
        summary,
        frames: state.config.includeFrames === false ? undefined : state.frames,
    };
    await Deno.writeTextFile(outputPath, JSON.stringify(payload, null, 2));
    await Deno.writeTextFile(summaryPath, JSON.stringify(summary, null, 2));
    console.log(`[locomotion-telemetry] wrote ${state.frames.length} frames to ${outputPath}`);
    console.log(`[locomotion-telemetry] wrote summary to ${summaryPath}`);
};
