// Full locomotion-vocabulary course — walk + run over ramps, small
// obstacles, two stair sizes, cover vaults, a mount+drop, a gap jump, a
// wall climb, a ladder, a sit-down rest stop, and an upper-body gesture
// while walking. Driven end-to-end by VRMCharacterController; this scene
// is a thin harness: terrain config + gait/zone script + camera.
globalThis.TERRAIN_CONFIG = {
    type: 'obstacle_course',
    segments: [
        { kind: 'flat',   length: 2.2 },                                // 0  walk start
        { kind: 'bump',   height: 0.10, depth: 0.30 },                  // 1  small obstacle step-over
        { kind: 'flat',   length: 1.2 },                                // 2
        { kind: 'ramp',   angleDeg: 8, horizLen: 2.0, dir: 'up' },      // 3  ramp up
        { kind: 'flat',   length: 1.0 },                                // 4
        { kind: 'ramp',   angleDeg: 8, horizLen: 2.0, dir: 'down' },    // 5  ramp down
        { kind: 'flat',   length: 1.2 },                                // 6
        { kind: 'stairs', rise: 0.10, run: 0.30, num: 5, dir: 'up' },   // 7  small stairs up
        { kind: 'flat',   length: 1.0 },                                // 8
        { kind: 'stairs', rise: 0.10, run: 0.30, num: 5, dir: 'down' }, // 9  small stairs down
        { kind: 'flat',   length: 1.4 },                                // 10
        { kind: 'wall',   height: 0.55, depth: 0.30 },                  // 11 walk VAULT (low cover)
        { kind: 'flat',   length: 1.8 },                                // 12
        { kind: 'wall',   height: 1.15, depth: 1.90 },                  // 13 MOUNT (climbLedge) + top walk + drop → FALL-LAND
        { kind: 'flat',   length: 2.0 },                                // 14 recovery
        { kind: 'flat',   length: 1.8 },                                // 15 ← RUN starts here
        { kind: 'stairs', rise: 0.18, run: 0.28, num: 5, dir: 'up' },   // 16 stairsRunUp
        { kind: 'flat',   length: 1.4 },                                // 17 raised slab
        { kind: 'gap',    length: 1.1 },                                // 18 run GAP JUMP
        { kind: 'flat',   length: 1.6 },                                // 19 raised slab
        { kind: 'stairs', rise: 0.18, run: 0.28, num: 5, dir: 'down' }, // 20 stairsRunDown
        { kind: 'flat',   length: 1.6 },                                // 21
        { kind: 'wall',   height: 0.85, depth: 0.35 },                  // 22 run VAULT (chest cover)
        { kind: 'flat',   length: 2.2 },                                // 23 ← RUN ends at end of this
        { kind: 'wall',   height: 2.20, depth: 2.40 },                  // 24 CLIMB WALL (full hang-to-mantle) + top + drop → FALL-LAND
        { kind: 'flat',   length: 1.6 },                                // 25 recovery walk
        { kind: 'flat',   length: 1.6 },                                // 26 SIT STOP — bench at the middle
        { kind: 'flat',   length: 1.9 },                                // 27 GESTURE while walking
        { kind: 'ladder', height: 2.5, depth: 0.5 },                    // 28 LADDER (explicit climbLadder)
        { kind: 'flat',   length: 2.4 },                                // 29 finale platform → salute
    ],
};
globalThis.CAMERA_MODE = 'three_quarter';

const baseCode = Deno.readTextFileSync('eidoverse/terrain_base.js');
(0, eval)(baseCode);

// Keep the base setup (terrain + VRM + Rapier + controller + IK), then add
// course direction on top.
const _baseSetup = globalThis.setup;
globalThis.setup = async function () {
    await _baseSetup();
    const cc = globalThis._charCtrl;
    await cc.loadEmote('salute', { loop: false });
    await cc.loadGesture('cheer');
    // Register the controller so the production seat system (seatOn) plays
    // its transition through the controller's seated state.
    (globalThis._vrmControllers = globalThis._vrmControllers || new Map())
        .set(globalThis._vrm, cc);
    // Spring bones (tail / mane) settle at the spawn pose.
    try { globalThis._vrm?.springBoneManager?.reset?.(); } catch (e) {}

    // Bench prop at the sit stop — a real SOLID (Rapier collider) so the character
    // can't phase through it; the sit trigger stops just short of its
    // front face and the sit transition eases back onto it.
    const segs = globalThis._terrainTelemetrySegments || [];
    const sitSeg = segs.find(s => s.index === 26);
    if (sitSeg) {
        const benchZ = (sitSeg.startZ + sitSeg.endZ) / 2;
        const benchMat = new THREE.MeshStandardNodeMaterial({ color: 0x7a5a3a, roughness: 0.8 });
        // Narrow enough (1.1m) that the walk-around lane at x≈0.9 clears it
        // comfortably while staying well on the 3m-wide course floor.
        const bench = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.45, 0.5), benchMat);
        bench.position.set(0, 0.225, benchZ);
        bench.castShadow = true; bench.receiveShadow = true;
        globalThis._s.add(bench);
        const w = cc.world, R = cc.RAPIER;
        const bb = w.createRigidBody(R.RigidBodyDesc.fixed().setTranslation(0, 0.225, benchZ));
        w.createCollider(R.ColliderDesc.cuboid(0.55, 0.225, 0.25), bb);
        globalThis._benchZ = benchZ;
        globalThis._benchObj = bench;
    }

    globalThis._course = {
        ladderDone: false, finaleAt: null, saluted: false,
        sitPhase: null, sitT: 0, sitDone: false, wpI: 0,
        gestureOn: false, gestureDone: false,
    };
};

globalThis.renderFrame = async function (t, frameIndex = null) {
    const dt = 1 / 30;
    const cc = globalThis._charCtrl;
    const vrm = globalThis._vrm;
    const course = globalThis._course;
    const segs = globalThis._terrainTelemetrySegments || [];
    const seg = (i) => segs.find(s => s.index === i);
    const z = cc.bodyTranslation.z;

    // RUN zone: from the start of segment 15 to the end of segment 23.
    const rs = seg(15), re = seg(23);
    cc.running = !!(rs && re && z <= rs.startZ && z >= re.endZ) &&
        !course.finaleAt && !course.sitPhase;

    // SIT STOP (segment 26): the bench sits ON the walking line, so the character
    // ROUTES AROUND it (a person doesn't walk through furniture), rejoins
    // the line just past it, squares up to the course heading, and sits
    // straight BACK onto the pan — the stand_to_sit clip's own baked
    // backward hip travel (~0.47m) carries the hips onto it. No pivots, no
    // scoots: the production seat system (seatOn) settles the butt onto the
    // pan, and stand-up REVERSES the same clip forward. Then the walk simply
    // resumes — the bench is behind her.
    const sitSeg = seg(26);
    cc.autoManeuvers = !(sitSeg && !course.sitDone &&
        z <= sitSeg.startZ + 1.2 && z >= sitSeg.endZ - 0.6);
    const bz = globalThis._benchZ;
    let routeInput = null;
    if (bz !== undefined && !course.sitDone && !course.sitPhase &&
        !cc.isManeuvering && z <= bz + 1.6) {
        course.sitPhase = 'route';
        course.wpI = 0;
    }
    if (course.sitPhase === 'route') {
        const wps = [[0.92, bz + 0.95], [0.88, bz - 0.05], [0.0, bz - 0.46]];
        const b = cc.bodyTranslation;
        while (course.wpI < wps.length) {
            const [wx, wz] = wps[course.wpI];
            const dx = wx - b.x, dz = wz - b.z;
            const dist = Math.hypot(dx, dz);
            if (dist < (course.wpI === wps.length - 1 ? 0.14 : 0.26)) { course.wpI++; continue; }
            routeInput = { x: dx / dist, z: dz / dist };
            break;
        }
        if (course.wpI >= wps.length) {
            course.sitPhase = 'settle';
            course.sitT = t;
        }
    }
    if (course.sitPhase === 'settle') {
        // Square up to the course heading — a small settling turn, like
        // anyone lining themselves up in front of a seat.
        let d = Math.PI - cc._heading;
        d = Math.atan2(Math.sin(d), Math.cos(d));
        cc._heading += d * (1 - Math.exp(-8 * dt));
        if (t > course.sitT + 0.45) {
            course.sitPhase = 'sit_down';
            course.sitT = t;
            globalThis.seatOn(vrm, globalThis._benchObj,
                { transition: 'stand_to_sit', faceY: Math.PI })
                .catch(e => console.warn('[course] seatOn failed:', e.message));
        }
    } else if (course.sitPhase === 'sit_down' && t > course.sitT + 2.9) {
        course.sitPhase = 'hold';
        course.sitT = t;
    } else if (course.sitPhase === 'hold' && t > course.sitT + 2.2) {
        course.sitPhase = 'stand_up';
        course.sitT = t;
        cc.endSeated(null, { reverse: true, reverseSpeed: 1.25 });
    } else if (course.sitPhase === 'stand_up' && t > course.sitT + 2.3) {
        course.sitPhase = null;
        course.sitDone = true;
        cc.stopEmote({ fadeOut: 0.3 });
    }

    // GESTURE (segment 27): cheer with the upper body while still walking.
    const ges = seg(27);
    if (ges && course.sitDone && !course.gestureDone) {
        if (!course.gestureOn && !cc.isManeuvering && z <= ges.startZ) {
            course.gestureOn = true;
            cc.playGesture('cheer', { weight: 2.75 });
        } else if (course.gestureOn && z <= ges.endZ + 0.9) {
            // Threshold sits BEFORE the ladder stop point (endZ+0.56) — any
            // deeper and it can never fire, and the cheer bleeds into the
            // climb.
            course.gestureOn = false;
            course.gestureDone = true;
            cc.stopGesture();
        }
    }

    // LADDER: explicit climb on reaching the ladder face (segment 28).
    const lad = seg(28);
    if (lad && !course.ladderDone && !cc.isManeuvering &&
        z <= lad.startZ + 0.55 && z > lad.endZ) {
        cc.stopGesture();   // hands belong to the rungs now, whatever else was queued
        if (cc.climbLadder({ height: 2.5 })) course.ladderDone = true;
    }

    // FINALE: stop at the centre of the top platform (segment 29), salute.
    const top = seg(29);
    if (top && !course.finaleAt && course.ladderDone && !cc.isManeuvering &&
        z <= (top.startZ + top.endZ) / 2) {
        course.finaleAt = t;
    }

    const stopped = course.finaleAt ||
        (course.sitPhase && course.sitPhase !== 'route');
    const input = stopped ? { x: 0, z: 0 } : (routeInput ?? { z: -1 });
    cc.locomote(dt, input);
    vrm.update(dt);

    if (course.finaleAt && !course.saluted && t > course.finaleAt + 0.7) {
        course.saluted = true;
        // Face the camera, wherever it currently orbits.
        const cp = globalThis._c.position, bp = cc.bodyTranslation;
        cc._emoteFacingY = Math.atan2(cp.x - bp.x, cp.z - bp.z);
        cc.playEmote('salute', { fadeIn: 0.35 });
    }

    // Per-second course log.
    const sec = Math.floor(t);
    if (sec !== (globalThis._courseLogSec ?? -1)) {
        globalThis._courseLogSec = sec;
        const b = cc.bodyTranslation;
        const man = cc._maneuver ? `${cc._maneuver.type}@${cc._maneuver.t.toFixed(1)}s` : '-';
        console.log(`[course] t=${sec}s z=${b.z.toFixed(2)} y=${b.y.toFixed(2)} speed=${cc.speedActual.toFixed(2)} run=${cc.running} maneuver=${man} sit=${course.sitPhase ?? '-'} emoting=${cc.isEmoting} seated=${!!cc._seated} grounded=${cc.grounded}`);
    }

    // FULL SIDE follow camera — the course runs along Z, so a pure +X side
    // view keeps every maneuver in profile. Exception: the LADDER — edge-on
    // a ladder collapses to a line — so the camera swings to a rear-¾ angle
    // for the ladder + finale, seeing the rungs and the climb face-on-ish.
    // Pushes in during maneuvers and the sit so detail work reads clearly.
    const t2 = cc.bodyTranslation;
    const cam = globalThis._c;
    const wantR = (cc.isManeuvering || course.sitPhase) ? 3.4 : 5.2;
    globalThis._camR = globalThis._camR === undefined ? 5.2
        : THREE.MathUtils.damp(globalThis._camR, wantR, 2.5, dt);
    const ladCam = seg(28);
    const wantA = (ladCam && z <= ladCam.startZ + 2.2) ? (46 * Math.PI / 180) : 0;
    globalThis._camA = globalThis._camA === undefined ? 0
        : THREE.MathUtils.damp(globalThis._camA, wantA, 1.8, dt);
    const R = globalThis._camR, A = globalThis._camA;
    cam.position.set(t2.x + R * Math.cos(A), t2.y + 0.45 + R * 0.07, t2.z + R * Math.sin(A));
    cam.lookAt(t2.x, t2.y - 0.30, t2.z);

    await globalThis._r.renderAsync(globalThis._s, cam);
};
// preflight: ASSETS['character_vrm']
