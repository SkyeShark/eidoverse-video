// Adapter: makes the eidoverse VRMCharacterController (physics + IK + the new
// heading/turn control) a drop-in for the VRMRobotBody stack, which was written
// against the LEGACY anim+waypoint CharacterController. This is the seam that
// reconnects the fully-built nav stack — RobotSensors (lidar fan) → RobotMemory
// (on-the-fly occupancy navmesh) → RobotPlanner (A* + line-of-sight waypoints) →
// VRMRobotBody.walkTo() — to the GOOD locomotion/IK legs instead of the legacy
// straight-line-only ones.
//
// VRMRobotBody drives `this.controller` via: setWaypoints, update(t,dt),
// getState/getHeading/getPosition, heading, walkSpeed/runSpeed, actions/
// forceAction/getCurrentAction, onPreVrmUpdate. This class presents exactly that
// contract and translates it onto the eidoverse controller:
//   - per frame: current waypoint → unit world-direction → controller.locomote()
//     (which owns tread-synced forward speed AND now turns toward the direction,
//     so the stride matches travel — no foot-slip — and she follows turns).
//   - arrival (within arriveRadius of the last waypoint) → idle.
//   - the eidoverse controller is physics-based, so this owns a Rapier world and
//     builds ground/wall colliders from the scene's collidable meshes (its ground
//     detection is a Rapier castShape; without colliders she'd fall through).
//
// Phase-2 (sprint/vault/jump/climb, more foot tuning) lands on the eidoverse
// controller itself; this adapter is unaffected by that work.
(function () {
    class EidoverseRobotController {
        static async create(vrm, mixer, overrides = {}, opts = {}) {
            const THREE = globalThis.THREE;
            if (!globalThis.VRMCharacterController) {
                throw new Error('[eidoverse-robot] VRMCharacterController global missing — character_controller.js not loaded');
            }
            // Resolved file path first: the npm: specifier makes deno (re)wire
            // the node_modules symlink, which fails with 'File exists (os
            // error 17)' when the link was created by a different uid. The
            // direct path needs no linking at all.
            let RAPIER;
            try {
                RAPIER = await import('file:///workspace/node_modules/.deno/@dimforge+rapier3d-compat@0.14.0/node_modules/@dimforge/rapier3d-compat/rapier.es.js')
                    .then(m => m.default || m);
            } catch (e) {
                RAPIER = await import('npm:@dimforge/rapier3d-compat@0.14.0').then(m => m.default || m);
            }
            await RAPIER.init();
            const world = new RAPIER.World({ x: 0, y: opts.gravity ?? -9.81, z: 0 });

            // Static colliders so the controller has ground underfoot + walls to
            // slide on. Each collidable mesh → an AABB cuboid fixed body (fast;
            // matches the terrain_base pattern). The SCENE supplies the
            // list via opts.collisionMeshes — it knows which meshes are floor /
            // walls / solid obstacles vs decorative.
            const collMeshes = opts.collisionMeshes || [];
            let added = 0;
            for (const mesh of collMeshes) {
                try {
                    mesh.updateWorldMatrix(true, false);
                    const box = new THREE.Box3().setFromObject(mesh);
                    if (box.isEmpty()) continue;
                    const c = box.getCenter(new THREE.Vector3());
                    const s = box.getSize(new THREE.Vector3());
                    // Truly degenerate (a point/line) — skip.
                    if (box.isEmpty() || (s.x < 1e-4 && s.y < 1e-4) || (s.x < 1e-4 && s.z < 1e-4) || (s.y < 1e-4 && s.z < 1e-4)) continue;
                    // A flat plane (e.g. a PlaneGeometry floor) has ~0 thickness on
                    // ONE axis. Don't skip it — that left flat floors with NO
                    // Rapier collider whenever any other collision mesh existed
                    // (the added===0 fallback never fired), so the character fell
                    // through the world. Give a thin slab a minimum half-extent;
                    // the surface stays at the bbox face (centre is the bbox centre).
                    const MIN_HALF = 0.05;
                    const hy = Math.max(s.y / 2, MIN_HALF);
                    // Anchor the collider's TOP at the mesh's bbox top, not its
                    // centre. For a normal box this is identical (cy = centre); for
                    // a FLAT floor (s.y≈0) centring would put the slab top at
                    // +MIN_HALF above the surface, so feet grounded ~5cm in the air.
                    // Anchoring the top keeps the walking surface exactly at the
                    // visual floor.
                    const cy = box.max.y - hy;
                    const body = world.createRigidBody(
                        RAPIER.RigidBodyDesc.fixed().setTranslation(c.x, cy, c.z));
                    world.createCollider(
                        RAPIER.ColliderDesc.cuboid(
                            Math.max(s.x / 2, MIN_HALF),
                            hy,
                            Math.max(s.z / 2, MIN_HALF)), body);
                    added++;
                } catch (e) { /* un-boxable mesh — skip */ }
            }
            if (added === 0) {
                // Flat-ground fallback so she doesn't fall through an empty world.
                const gy = opts.groundY ?? 0;
                const body = world.createRigidBody(
                    RAPIER.RigidBodyDesc.fixed().setTranslation(0, gy - 0.05, 0));
                world.createCollider(RAPIER.ColliderDesc.cuboid(60, 0.05, 60), body);
                console.warn('[eidoverse-robot] no collisionMeshes provided — using a flat ground plane at y=' + gy);
            }

            const sp = opts.startPosition
                || (vrm.scene ? [vrm.scene.position.x, vrm.scene.position.y, vrm.scene.position.z] : [0, 0, 0]);
            const charCtrl = new globalThis.VRMCharacterController(vrm, world, RAPIER, {
                startPosition: sp,
                startHeading: opts.startHeading ?? Math.PI,
                enableTurning: true,   // the adapter follows turning waypoint paths

                walkSpeed: opts.walkSpeed,
                runSpeed: opts.runSpeed,
                maxTurnRate: opts.maxTurnRate,
                ...(opts.controllerOpts || {}),
            });
            await charCtrl.loadStandardAnimations(overrides.standardAnimationOverrides || {});

            // CRITICAL: hand locomotion to the controller. Without this,
            // charCtrl.locomote() crashes (its stair/step history arrays are
            // initialised inside attachLocomotion) — so VRMRobotBody.walkTo()
            // threw "Cannot read properties of undefined (reading 'push')" on
            // the first body.update(). The legacy terrain harness called this
            // explicitly; the robot adapter forgot to. Attach the foot IK too
            // (best-effort) so feet ground on flat floors instead of sliding.
            let legIK = null;
            try {
                if (globalThis.VRMFootControllerIK) {
                    const bbox = new THREE.Box3().setFromObject(vrm.scene);
                    legIK = new globalThis.VRMFootControllerIK(vrm, {
                        world, RAPIER, collider: charCtrl.collider,
                        increasedAccuracy: true, fixKnee: true, FootHeightOffset: 0.012,
                        type: 2, sphereRadius: 0.015, MaxStepHeight: 0.6,
                        DistancePower: 1, SmoothingAngle: 2, GlobalSmoothingPower: 0,
                        meshHeightOffset: bbox.min.y,
                    });
                }
            } catch (e) {
                console.warn('[eidoverse-robot] foot IK init failed; walking without it:', e.message);
                legIK = null;
            }
            charCtrl.attachLocomotion({
                ...(legIK ? { legIK } : {}),
                // Speeds only pass through when explicitly configured, so the
                // controller's tuned defaults stay authoritative otherwise.
                // (native*Speed stays the CLIP's authored pace — stride sync
                // scales timeScale from it, so feet keep matching the ground.)
                ...(opts.walkSpeed !== undefined ? { flatSpeed: opts.walkSpeed } : {}),
                ...(opts.runSpeed !== undefined ? { runSpeed: opts.runSpeed } : {}),
            });

            return new EidoverseRobotController(vrm, charCtrl, world, RAPIER, opts);
        }

        constructor(vrm, charCtrl, world, RAPIER, opts = {}) {
            this.vrm = vrm;
            this.charCtrl = charCtrl;
            this.world = world;
            this.RAPIER = RAPIER;
            this.waypoints = [];
            this.waypointIndex = 0;
            this.state = 'idle';            // 'idle' | 'walking' | 'running' | 'performing' | 'seated'
            this.walkSpeed = opts.walkSpeed ?? 1.5;   // mirrors controller flatSpeed default
            this.runSpeed = opts.runSpeed ?? 3.6;     // mirrors controller runSpeed default
            this.arriveRadius = opts.arriveRadius ?? 0.28;
            this.actions = {};              // VRMRobotBody reads this; emotes go via forceAction
            this.currentAction = null;
            this.onPreVrmUpdate = null;     // VRMRobotBody sets this for head-look
            this._emoteUntil = 0;
            this._t = 0;
            this._emotesLoaded = {};
        }

        // ── VRMRobotBody-contract accessors ──
        get heading() { return this.charCtrl._heading; }
        set heading(h) { this.charCtrl._heading = h; }
        getHeading() { return this.charCtrl._heading; }
        getPosition() {
            const f = this.charCtrl.feetWorldPosition;
            return { x: f.x, y: f.y, z: f.z };
        }
        getState() { return this.state; }
        getCurrentAction() { return this.currentAction; }
        isBusy() { return this.state !== 'idle' || this.waypointIndex < this.waypoints.length; }
        setWalkSpeed(v) { this.walkSpeed = v; if (this.charCtrl) this.charCtrl._flatSpeed = v; }
        setRunSpeed(v) { this.runSpeed = v; if (this.charCtrl) this.charCtrl._runSpeed = v; }
        setRunning(v) { if (this.charCtrl) this.charCtrl.running = !!v; }
        get isManeuvering() { return !!this.charCtrl?.isManeuvering; }
        // Parkour passthroughs — auto-maneuvers already fire en route; these
        // are for scripted moments.
        vault()          { return this.charCtrl?.vault?.() ?? false; }
        jump(opts)       { return this.charCtrl?.jump?.(opts) ?? false; }
        climbLedge()     { return this.charCtrl?.climbLedge?.() ?? false; }
        climbLadder(o)   { return this.charCtrl?.climbLadder?.(o) ?? false; }

        setWaypoints(waypoints) {
            // Preserve per-waypoint `action` ('run' → run-family gait to that
            // waypoint; VRMRobotBody.runTo emits these).
            this.waypoints = (waypoints || []).map((w) =>
                Array.isArray(w) ? { x: w[0], z: w[1] } : { x: w.x, z: w.z, action: w.action });
            this.waypointIndex = 0;
            // Clear any collision-stall latch so a freshly-issued path resumes
            // (otherwise a prior block would keep feeding zero input forever).
            if (this.charCtrl) this.charCtrl._blockedFrames = 0;
            if (this.state !== 'performing') {
                this.state = this.waypoints.length ? 'walking' : 'idle';
            }
        }

        async forceAction(name, duration) {
            // Stationary expressive clip via the controller's emote system
            // (auto-suspends locomotion at the engine level). Best-effort: an
            // unknown emote degrades to a no-op rather than throwing.
            try {
                if (typeof this.charCtrl.loadEmote === 'function' && !this._emotesLoaded[name]) {
                    await this.charCtrl.loadEmote(name);
                    this._emotesLoaded[name] = true;
                }
                this.charCtrl.playEmote?.(name);
                this.currentAction = name;
                this.state = 'performing';
                this._emoteUntil = this._t + (duration ?? 1.5);
            } catch (e) {
                console.warn('[eidoverse-robot] forceAction(' + name + ') failed: ' + e.message);
            }
        }

        // Enter the SEATED state: crossfade a seated clip (e.g. stand_to_sit) in
        // on the controller's OWN mixer (so it eases from the prior emote /
        // locomotion), and hand root placement to the caller (charCtrl._seated
        // stops the controller snapping the root to the feet / grounding IK).
        // Sticky — stays until endSeated(). Returns the clip duration if known.
        async beginSeated(slot, opts = {}) {
            try {
                // charCtrl.beginSeated sets _seated SYNCHRONOUSLY before any
                // await, so the very next update leaves the root to seatOn's
                // raycast (no facing/root clobber during the emote load).
                this.state = 'seated';
                this.currentAction = slot;
                return await this.charCtrl.beginSeated(slot, opts);
            } catch (e) {
                console.warn('[eidoverse-robot] beginSeated(' + slot + ') failed: ' + e.message);
                return null;
            }
        }

        // Leave SEATED: crossfade a stand-up clip in, then re-engage locomotion.
        async endSeated(slot, opts = {}) {
            try {
                if (slot) {
                    this.currentAction = slot;
                    this.state = 'performing';
                    this._emoteUntil = this._t + (opts.duration ?? 1.8);
                } else {
                    this.state = (this.waypointIndex < this.waypoints.length) ? 'walking' : 'idle';
                }
                return await this.charCtrl.endSeated(slot, opts);
            } catch (e) {
                console.warn('[eidoverse-robot] endSeated failed: ' + e.message);
            }
        }

        update(t, dt) {
            this._t = t;
            // Emote window: let the emote play, no locomotion, then resume.
            // 'seated' is a sticky variant — it never times out (the character
            // stays seated until endSeated()) and the controller leaves the root
            // to seatOn's raycast (charCtrl._seated gates that). Both states zero
            // locomotion input → nothing translates while a static clip plays.
            if (this.state === 'performing' || this.state === 'seated') {
                if (this.state === 'performing' && t >= this._emoteUntil) {
                    this.currentAction = null;
                    this.state = (this.waypointIndex < this.waypoints.length) ? 'walking' : 'idle';
                }
                this.charCtrl.locomote(dt, { x: 0, z: 0 });
                if (this.onPreVrmUpdate) this.onPreVrmUpdate(dt);
                this.vrm.update(dt);
                return;
            }

            // Waypoint follow: steer toward the current waypoint; arrival → idle.
            let dirX = 0, dirZ = 0;
            if (this.waypointIndex < this.waypoints.length) {
                const pos = this.charCtrl.feetWorldPosition;
                const wp = this.waypoints[this.waypointIndex];
                const dx = wp.x - pos.x, dz = wp.z - pos.z;
                const dist = Math.hypot(dx, dz);
                // Per-waypoint gait: 'run' waypoints run, everything else walks.
                const running = wp.action === 'run';
                this.charCtrl.running = running;
                if (dist <= this.arriveRadius) {
                    this.waypointIndex++;
                    if (this.waypointIndex >= this.waypoints.length) this.state = 'idle';
                } else {
                    dirX = dx / dist;
                    dirZ = dz / dist;
                    this.state = running ? 'running' : 'walking';
                }
            } else {
                this.state = 'idle';
                this.charCtrl.running = false;
            }

            // COLLISION STALL → grounded idle. If a solid blocks the path (the
            // controller's move-and-slide cancelled our movement for several
            // frames), STOP pushing into it: feed zero input so the avatar settles
            // into the normal grounded idle (feet on the floor) instead of
            // moon-walking in place against the obstacle. Feeding zero input is
            // exactly what idle does, so this reuses the working idle grounding
            // path — no foot-IK special-casing. The latch holds (no per-frame
            // re-probe, which caused a foot pop/jitter); it's cleared when a new
            // path is issued via setWaypoints(), so a fresh walkTo resumes.
            // (A maneuver in flight owns the frame — never latch idle mid-vault;
            // the controller cleared the block when the maneuver started.)
            if (!this.charCtrl.isManeuvering &&
                (this.charCtrl._blockedFrames || 0) >= 6) { dirX = 0; dirZ = 0; this.state = 'idle'; }
            // Unit direction → locomote owns the (tread-synced) speed + turning.
            this.charCtrl.locomote(dt, { x: dirX, z: dirZ });
            if (this.onPreVrmUpdate) this.onPreVrmUpdate(dt);
            this.vrm.update(dt);
        }
    }

    globalThis.EidoverseRobotController = EidoverseRobotController;
})();
