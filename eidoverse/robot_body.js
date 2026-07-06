/**
 * VRMRobotBody — embodied robot abstraction over a VRM character.
 *
 * Treats the VRM as a robot body controlled by an LLM. The body has:
 *   - A pair of legs (the locomotion controller) driving canned anims
 *   - A head (controlled directly here) that can pan/tilt independently
 *     of the body, used as the "depth camera" mount
 *   - A forward-facing depth-camera-like sensor cone (RobotSensors) that
 *     is the body's ONLY contact with scene geometry
 *   - A 2D occupancy-grid + landmark memory (RobotMemory) that grows from
 *     sensor readings as the body moves and looks
 *   - An A* path planner (RobotPlanner) over the memory grid
 *
 * The body never has god's-eye access to scene meshes, colliders, or
 * walkable surfaces. Everything it knows about the world it has seen with
 * its own sensor cone. Memory is fresh per scene (no disk persistence in
 * the video harness — the serialize/deserialize API exists for the
 * standalone vrm-robot-body opensource use case but isn't used here).
 *
 * High-level action API (LLM-friendly, all async, all return Promises):
 *
 *   const body = await VRMRobotBody.create(vrm, mixer, scene, opts);
 *
 *   await body.walkTo(x, z);                      // plan path + walk along it
 *   await body.runTo(x, z);
 *   await body.walkToLandmark('door');            // resolve named landmark
 *   await body.lookAt(x, y, z);                   // turn head, no body rotation
 *   await body.faceDirection(headingRad);         // rotate whole body
 *   await body.scanArea({yawRange: 90, duration: 1.5});
 *   await body.performAction('dance', 5);         // canned full-body clip
 *   body.stop();                                  // halt all motion now
 *
 *   body.observe();                               // current sensor reading
 *   body.canSee(x, y, z);                         // is point in cone + LOS?
 *   body.distanceTo(x, z);                        // straight-line distance
 *   body.pathTo(x, z);                            // planned path or null
 *
 *   body.tagLandmark(name, x, z, opts);
 *   body.getLandmarks();
 *   body.getMap();                                // raw memory for debug
 *
 *   body.getPosition() / getHeading() / getHeadDirection() / isMoving()
 *
 * Per-frame integration:
 *
 *   In renderFrame(t): body.update(t, dt);
 *
 * The body internally calls controller.update() — do NOT also call it
 * yourself. The body uses controller.onPreVrmUpdate to apply head bone
 * overrides between mixer.update and vrm.update each frame, so the head
 * gaze tracks correctly under animation.
 */

class VRMRobotBody {
    /**
     * Async factory. Builds a locomotion controller via .create() (so the
     * baked VRMA defaults auto-load), wires up sensors/memory/planner, and
     * registers the head-bone hook.
     *
     * Required:
     *   vrm    — loaded VRM (after VRMUtils.rotateVRM0)
     *   mixer  — THREE.AnimationMixer bound to vrm.scene
     *   scene  — THREE.Scene root (for raycasting)
     *
     * opts:
     *   sensors:  RobotSensors options (hFov, vFov, range, hRays, vRays)
     *   memory:   RobotMemory options (size, cellSize, originX, originZ, bayesian)
     *   motion:   { agentRadius, agentHeight, walkSpeed, runSpeed, startX, startZ, startHeading }
     *   planner:  RobotPlanner options (optimistic, unknownPenalty)
     *   headRate: max head turn rate, rad/s (default 1.57 = 90°/s)
     *   yawLimit: max head yaw from neutral, rad (default 1.05 = 60°)
     *   pitchLimit: max head pitch from neutral, rad (default 0.52 = 30°)
     *   characterControllerOverrides: dict of clip overrides forwarded to
     *     the controller's .create() (e.g. {talk: talkClip}). The
     *     standard locomotion + obstacle clips auto-load from the baked
     *     defaults — only pass custom/perform clips here.
     */
    static async create(vrm, mixer, scene, opts = {}) {
        const motion = opts.motion || {};

        // Build the locomotion controller — the eidoverse physics+IK controller
        // (tread-synced stride, foot grounding, stairs, turning) via its robot
        // adapter. opts.legsClass overrides the legs implementation.
        // Heading convention on the eidoverse path: 0 = +Z, Math.PI = -Z.
        const controllerOverrides = opts.characterControllerOverrides || {};
        const _startY = (vrm.scene && vrm.scene.position) ? vrm.scene.position.y : 0;
        const controllerOpts = {
            startPosition: [
                motion.startX !== undefined ? motion.startX : 0,
                _startY,
                motion.startZ !== undefined ? motion.startZ : 0,
            ],
            startHeading: motion.startHeading !== undefined ? motion.startHeading : Math.PI,
            collisionMeshes: opts.collisionMeshes || motion.collisionMeshes || [],
            groundY: motion.groundY,
            maxTurnRate: motion.maxTurnRate,
        };
        if (motion.walkSpeed !== undefined) controllerOpts.walkSpeed = motion.walkSpeed;
        if (motion.runSpeed !== undefined)  controllerOpts.runSpeed  = motion.runSpeed;
        const Legs = opts.legsClass || globalThis.EidoverseRobotController
            || (typeof CharacterController !== 'undefined' ? CharacterController : null);
        if (!Legs) throw new Error('[VRMRobotBody] no locomotion controller available');
        const controller = await Legs.create(vrm, mixer, controllerOverrides, controllerOpts);

        const sensors = new RobotSensors(scene, Object.assign(
            { excludeObjects: [vrm.scene] },
            opts.sensors || {}
        ));
        const memory = new RobotMemory(opts.memory || {});
        const planner = new RobotPlanner(Object.assign(
            {
                agentRadius: motion.agentRadius !== undefined ? motion.agentRadius : 0.35,
                agentHeight: motion.agentHeight !== undefined ? motion.agentHeight : 1.7,
            },
            opts.planner || {}
        ));

        const body = new VRMRobotBody(vrm, mixer, scene, controller, sensors, memory, planner, opts);
        // Register vrm→body so engine helpers (e.g. seatOn) can find the
        // controller and route emotes/sit through its single mixer for cohesive
        // crossfades, instead of spinning up a competing standalone mixer.
        try {
            const g = (typeof globalThis !== 'undefined') ? globalThis : undefined;
            if (g) { (g._vrmControllers = g._vrmControllers || new Map()).set(vrm, body); }
        } catch (e) { /* registry is best-effort */ }
        return body;
    }

    constructor(vrm, mixer, scene, controller, sensors, memory, planner, opts = {}) {
        this.vrm = vrm;
        this.mixer = mixer;
        this.scene = scene;
        this.controller = controller;
        this.sensors = sensors;
        this.memory = memory;
        this.planner = planner;

        const motion = opts.motion || {};
        this.agentRadius = motion.agentRadius !== undefined ? motion.agentRadius : 0.35;
        this.agentHeight = motion.agentHeight !== undefined ? motion.agentHeight : 1.7;

        this.headRate = opts.headRate !== undefined ? opts.headRate : Math.PI / 2;          // 90°/sec
        this.yawLimit = opts.yawLimit !== undefined ? opts.yawLimit : Math.PI / 3;          // 60°
        this.pitchLimit = opts.pitchLimit !== undefined ? opts.pitchLimit : Math.PI / 6;    // 30°

        // Sense every Nth update() call. Default 2 = sensors fire at 12Hz
        // when update is called at 24fps, which is more than enough for a
        // robot moving at ~1.4 m/s (cell size 0.2m → 7 cells/sec at most;
        // 12Hz of sensing = 1.7 cell/sense, fine for nav).
        this.sensePeriod = opts.sensePeriod !== undefined ? opts.sensePeriod : 2;
        this._sensePhase = 0;

        // Cached head bone reference. May be null if VRM lacks a head bone.
        this.headBone = vrm.humanoid && vrm.humanoid.getNormalizedBoneNode('head');
        if (this.headBone) {
            this._headRestQuat = this.headBone.quaternion.clone();
        }

        // Head target state — what we WANT the head pointed at right now.
        // _headYawTarget / _headPitchTarget are in body-local space.
        this._headYawTarget = 0;
        this._headPitchTarget = 0;
        this._headYawCurrent = 0;
        this._headPitchCurrent = 0;
        this._lookAtWorldTarget = null;       // {x,y,z} or null

        // Action state. At most one async action is in flight at a time.
        this._pendingAction = null;
        this._currentPath = null;             // [{x,z}, ...] or null
        this._currentGoal = null;             // {x,z, mode:'walk'|'run'} or null
        this._lastReplanTime = -Infinity;
        this._replanCooldown = 0.4;           // seconds between forced replans
        this._blockedSince = -1;              // timestamp when last detected blocked
        this._blockedTimeout = 1.5;           // seconds before declaring unreachable

        // Scan state
        this._scan = null;                    // { startTime, duration, yawFrom, yawTo }

        // Latest sensor reading + frame stats
        this.lastReading = null;
        this.frameCount = 0;
        this._timeAccum = 0;

        // Hook into the controller's update sequence so head overrides land
        // between mixer.update and vrm.update.
        this.controller.onPreVrmUpdate = (dt) => this._applyHeadOverride(dt);
    }

    // ============================================================
    //  PUBLIC INFO
    // ============================================================

    getPosition() { return this.controller.getPosition(); }
    getHeading()  { return this.controller.getHeading(); }
    getCurrentAction() {
        if (this._pendingAction) return this._pendingAction.kind;
        return this.controller.getCurrentAction();
    }
    isMoving() {
        const s = this.controller.getState();
        return s !== 'idle' && s !== 'performing';
    }
    isBlocked() {
        return this._blockedSince > 0 && (this._timeAccum - this._blockedSince) > this._blockedTimeout;
    }
    getMap() { return this.memory; }
    getLandmarks() { return this.memory.listLandmarks(); }
    tagLandmark(name, x, z, opts) { this.memory.tagLandmark(name, x, z, opts); }
    forgetLandmark(name) { this.memory.forgetLandmark(name); }

    /**
     * Returns the head bone's current world forward direction as a Vector3.
     */
    getHeadDirection() {
        if (!this.headBone) return new THREE.Vector3(0, 0, 1);
        const fwd = new THREE.Vector3(0, 0, 1);
        const q = new THREE.Quaternion();
        this.headBone.getWorldQuaternion(q);
        return fwd.applyQuaternion(q);
    }

    /**
     * Returns the head bone's current world position.
     */
    getHeadPosition() {
        if (!this.headBone) {
            const p = this.getPosition();
            return new THREE.Vector3(p.x, p.y + this.agentHeight, p.z);
        }
        const v = new THREE.Vector3();
        this.headBone.getWorldPosition(v);
        return v;
    }

    // ============================================================
    //  ACTIONS — async, return Promises
    // ============================================================

    walkTo(x, z) { return this._beginGoToAction(x, z, 'walk'); }
    runTo(x, z)  { return this._beginGoToAction(x, z, 'run'); }

    walkToLandmark(name) {
        const lm = this.memory.getLandmark(name);
        if (!lm) return Promise.reject(new Error(`unknown landmark: ${name}`));
        return this.walkTo(lm.x, lm.z);
    }

    runToLandmark(name) {
        const lm = this.memory.getLandmark(name);
        if (!lm) return Promise.reject(new Error(`unknown landmark: ${name}`));
        return this.runTo(lm.x, lm.z);
    }

    _beginGoToAction(x, z, mode) {
        // Cancel any existing pending action
        this._cancelPendingAction('superseded');

        return new Promise((resolve, reject) => {
            const pos = this.getPosition();
            const path = this.planner.findPath(this.memory, pos.x, pos.z, x, z);
            if (!path) {
                reject(new Error(`no path from (${pos.x.toFixed(2)},${pos.z.toFixed(2)}) to (${x.toFixed(2)},${z.toFixed(2)})`));
                return;
            }
            // Skip the first cell (where we already are) and convert the
            // rest into controller waypoints.
            const wps = path.slice(1).map(p => ({ x: p.x, z: p.z, action: mode }));
            if (wps.length === 0) {
                resolve();
                return;
            }
            this.controller.setWaypoints(wps);
            this._currentPath = path;
            this._currentGoal = { x, z, mode };
            this._blockedSince = -1;
            this._pendingAction = { kind: mode === 'run' ? 'running' : 'walking', resolve, reject, mode };
        });
    }

    /**
     * Turn the head to face a world point. Resolves when the head is
     * within ~5° of the target direction. Pass {hold: true} to keep
     * tracking the target indefinitely (resolves immediately on first
     * arrival; the head keeps following until lookAt() is called again
     * or _lookAtWorldTarget is cleared).
     */
    lookAt(x, y, z, opts = {}) {
        this._lookAtWorldTarget = { x, y, z };
        if (opts.instant) {
            // Snap immediately
            this._updateHeadTargetFromLookAt();
            this._headYawCurrent = this._headYawTarget;
            this._headPitchCurrent = this._headPitchTarget;
            return Promise.resolve();
        }
        // Action: wait until head reaches target.
        this._cancelPendingAction('superseded');
        return new Promise((resolve, reject) => {
            this._pendingAction = {
                kind: 'lookingAt',
                resolve, reject,
                hold: !!opts.hold,
            };
        });
    }

    /**
     * Clear any active head look-at target so the head returns to neutral.
     */
    lookForward() {
        this._lookAtWorldTarget = null;
        this._headYawTarget = 0;
        this._headPitchTarget = 0;
    }

    /**
     * Rotate the whole body to face a heading (radians, 0 = +Z).
     * Uses the controller's standing turn animation.
     */
    faceDirection(headingRad) {
        this._cancelPendingAction('superseded');
        const cur = this.controller.heading;
        let diff = headingRad - cur;
        while (diff > Math.PI) diff -= Math.PI * 2;
        while (diff < -Math.PI) diff += Math.PI * 2;
        if (Math.abs(diff) < 0.05) return Promise.resolve();
        // Use controller's internal turn machinery via a one-step waypoint
        // pattern. Easiest hack: snap heading directly. The standing turn
        // animation requires going through the waypoint state machine,
        // which the agent doesn't typically need for body rotation. Use
        // _startTurn-style logic by setting target heading and switching
        // to a turning state. Easier: just snap.
        this.controller.heading = headingRad;
        return Promise.resolve();
    }

    /**
     * Smooth head sweep covering an arc. Builds out a wider chunk of
     * memory without rotating the body. Yaw range is in degrees, centered
     * on current body forward (or pass `centerYaw` in radians to offset).
     *
     * opts:
     *   yawRange: degrees (default 90)
     *   pitchRange: degrees (default 0 — flat sweep)
     *   duration: seconds (default 1.5)
     *   centerYaw: radians from body forward (default 0)
     *   passes: how many back-and-forth sweeps (default 1)
     */
    scanArea(opts = {}) {
        this._cancelPendingAction('superseded');
        const yawRangeRad = (opts.yawRange !== undefined ? opts.yawRange : 90) * Math.PI / 180;
        const duration = opts.duration !== undefined ? opts.duration : 1.5;
        const centerYaw = opts.centerYaw !== undefined ? opts.centerYaw : 0;
        const passes = opts.passes !== undefined ? opts.passes : 1;
        return new Promise((resolve, reject) => {
            this._scan = {
                startTime: this._timeAccum,
                duration,
                yawHalf: yawRangeRad / 2,
                centerYaw,
                passes,
            };
            // Stop walking while scanning
            this.controller.setWaypoints([]);
            this._lookAtWorldTarget = null;
            this._pendingAction = { kind: 'scanning', resolve, reject };
        });
    }

    /**
     * Play a canned clip on the controller. Forwards to forceAction.
     * The clip must be in the controller's clip set (either a default or
     * passed via characterControllerOverrides at create time).
     */
    performAction(clipName, duration) {
        this._cancelPendingAction('superseded');
        return new Promise((resolve, reject) => {
            // Accept either a clip preloaded into the controller's set OR a
            // loadable VRMA-default slot (emotes like salute/cheer/talk load
            // on demand inside forceAction → loadEmote, so they're NOT listed
            // in controller.actions). Without the VRMA_DEFAULTS_B64 check this
            // rejected every standard emote as "unknown clip".
            const g = (typeof globalThis !== 'undefined') ? globalThis : undefined;
            const known = (this.controller.actions && this.controller.actions[clipName]) ||
                          (g && g.VRMA_DEFAULTS_B64 && g.VRMA_DEFAULTS_B64[clipName]);
            if (!known) {
                reject(new Error(`unknown clip: ${clipName}`));
                return;
            }
            this.controller.forceAction(clipName, duration);
            this._pendingAction = { kind: 'performing', resolve, reject };
        });
    }

    /**
     * Parkour — auto-maneuvers already fire during walkTo/runTo travel
     * (cover-height walls vault, blocks/ledges climb, gaps jump, big drops
     * land with a recovery). These explicit calls are for scripted moments:
     * vault/climb act on whatever obstacle is ahead along the heading;
     * jump leaps forward; climbLadder scales a ladder-like face.
     * All return false when the geometry doesn't support the move.
     */
    vault()           { return this.controller.vault?.() ?? false; }
    jump(opts)        { return this.controller.jump?.(opts) ?? false; }
    climbLedge()      { return this.controller.climbLedge?.() ?? false; }
    climbLadder(opts) { return this.controller.climbLadder?.(opts) ?? false; }
    setRunning(v)     { this.controller.setRunning?.(v); }
    isManeuvering()   { return !!this.controller.isManeuvering; }

    /**
     * Enter the SEATED state — crossfade a seated clip (e.g. 'stand_to_sit') in
     * on the controller's mixer (eases from the prior emote/locomotion) and let
     * the caller own the root placement (seatOn's raycast butt-on-seat). Sticky
     * until standUp(). Returns the clip duration if known. Normally you call
     * seatOn(vrm, chair, {transition}) which uses this under the hood.
     */
    beginSeated(slot, opts = {}) {
        if (typeof this.controller.beginSeated !== 'function') return Promise.resolve(null);
        return this.controller.beginSeated(slot, opts);
    }

    /** Leave SEATED — crossfade a stand-up clip, then resume locomotion. */
    standUp(slot = 'sit_to_stand', opts = {}) {
        if (typeof this.controller.endSeated !== 'function') return Promise.resolve();
        return this.controller.endSeated(slot, opts);
    }

    /**
     * Aim STANDING emotes (salute / cheer / talk played via performAction) at a
     * fixed world heading instead of the default Math.PI. Pass the rotation.y
     * radians the VRM should face during emotes (e.g. atan2(camX-x, camZ-z) to
     * face the camera). Pass null to restore the default. Does not affect
     * locomotion heading or the seated facing (that's seatOn's faceY).
     */
    setEmoteFacing(ry) {
        const cc = this.controller && this.controller.charCtrl;
        if (cc) cc._emoteFacingY = ry;
    }

    /**
     * Halt all motion immediately. Cancels any in-flight async action with
     * a "stopped" rejection so the caller can distinguish.
     */
    stop() {
        this._cancelPendingAction('stopped');
        this.controller.setWaypoints([]);
        this._scan = null;
        this._currentPath = null;
        this._currentGoal = null;
    }

    _cancelPendingAction(reason) {
        if (!this._pendingAction) return;
        const a = this._pendingAction;
        this._pendingAction = null;
        if (a.reject) {
            try { a.reject(new Error(`action ${a.kind} ${reason}`)); }
            catch (e) {}
        }
    }

    // ============================================================
    //  SENSING / QUERIES
    // ============================================================

    observe() { return this.lastReading; }

    /**
     * Is a world point inside the current sensor cone AND not occluded?
     */
    canSee(x, y, z) {
        const headPos = this.getHeadPosition();
        const dir = new THREE.Vector3(x - headPos.x, y - headPos.y, z - headPos.z);
        const dist = dir.length();
        if (dist > this.sensors.range) return false;
        dir.normalize();
        // Inside cone?
        const headDir = this.getHeadDirection();
        const cosAngle = headDir.dot(dir);
        const halfFov = Math.max(this.sensors.hFov, this.sensors.vFov) / 2;
        if (cosAngle < Math.cos(halfFov)) return false;
        // LOS?
        const r = this.sensors.castOne(headPos, dir, dist);
        return !r || !r.hit || r.distance >= dist - 0.05;
    }

    distanceTo(x, z) {
        const p = this.getPosition();
        const dx = x - p.x, dz = z - p.z;
        return Math.sqrt(dx * dx + dz * dz);
    }

    pathTo(x, z) {
        const p = this.getPosition();
        return this.planner.findPath(this.memory, p.x, p.z, x, z);
    }

    // ============================================================
    //  PER-FRAME UPDATE
    // ============================================================

    update(t, dt) {
        this._timeAccum = t;
        this.frameCount++;

        // 1. Resolve any timed action progress (scan)
        if (this._scan) {
            this._updateScan();
        }

        // 2. If we have a look-at target, recompute the head yaw/pitch
        //    relative to current body heading + head world position.
        if (this._lookAtWorldTarget) {
            this._updateHeadTargetFromLookAt();
        } else if (!this._scan) {
            // Default: head returns to neutral when nothing else is driving it
            this._headYawTarget = 0;
            this._headPitchTarget = 0;
        }

        // 3. Smooth current head toward target
        const maxStep = this.headRate * dt;
        const yDiff = this._headYawTarget - this._headYawCurrent;
        const pDiff = this._headPitchTarget - this._headPitchCurrent;
        this._headYawCurrent += Math.max(-maxStep, Math.min(maxStep, yDiff));
        this._headPitchCurrent += Math.max(-maxStep, Math.min(maxStep, pDiff));

        // Clamp to anatomical limits
        this._headYawCurrent = Math.max(-this.yawLimit, Math.min(this.yawLimit, this._headYawCurrent));
        this._headPitchCurrent = Math.max(-this.pitchLimit, Math.min(this.pitchLimit, this._headPitchCurrent));

        // 4. Sense (cone from head world pos in head world direction).
        // Throttled by sensePeriod to keep CPU cost manageable — at 24fps
        // and sensePeriod=2 we sense at 12Hz, which is plenty for a robot
        // moving at walking speed.
        const pos = this.getPosition();
        const shouldSense = (this._sensePhase++ % this.sensePeriod) === 0;
        if (shouldSense) {
            const headPos = this.getHeadPosition();
            const worldHeading = this.controller.heading + this._headYawCurrent;
            const reading = this.sensors.sense(headPos, worldHeading, this._headPitchCurrent);
            this.lastReading = reading;
            // 5. Update memory with the new reading
            this.memory.applySensorReading(reading, {
                floorY: pos.y,
                agentHeight: this.agentHeight,
            });
        }
        // Standing footprint is cheap — mark every frame so the agent's
        // own cell stays free even when sensors are sleeping. Pass the
        // body's current Y so the cells get the surface height baked in.
        this.memory.markStandingFootprint(pos.x, pos.z, this.agentRadius * 1.2, pos.y);

        // 6. Replan if our current path is now blocked
        if (this._currentPath && this._currentGoal &&
            (t - this._lastReplanTime) > this._replanCooldown) {
            // Check the remaining path (from current cell to goal) for new
            // blocked cells
            const remaining = this._remainingPath(pos);
            if (this.planner.isPathBlocked(this.memory, remaining)) {
                this._replan(t);
            }
        }

        // 7. Detect "stuck" — no controller progress for a while
        this._checkStuck(t, dt);

        // 8. Drive the legs
        this.controller.update(t, dt);

        // 9. Resolve pending actions if their conditions are met
        this._resolvePendingAction();
    }

    _updateScan() {
        const elapsed = this._timeAccum - this._scan.startTime;
        const u = Math.min(elapsed / this._scan.duration, 1);
        // Triangle wave for back-and-forth: 0 → 1 → -1 → 1 → ... over the
        // span of `passes` passes.
        const phase = u * this._scan.passes;
        const tri = 1 - 2 * Math.abs((phase * 2) % 2 - 1);
        const yaw = this._scan.centerYaw + tri * this._scan.yawHalf;
        this._headYawTarget = yaw;
        this._headPitchTarget = 0;
        if (u >= 1) {
            // Scan complete — return head to neutral on next frame
            this._scan = null;
            // Don't resolve here; let _resolvePendingAction handle it once
            // the head has actually arrived back at neutral.
            this._headYawTarget = 0;
            // Mark scan as done so the action resolver picks it up
            if (this._pendingAction && this._pendingAction.kind === 'scanning') {
                this._pendingAction._scanDone = true;
            }
        }
    }

    _updateHeadTargetFromLookAt() {
        const headPos = this.getHeadPosition();
        const dx = this._lookAtWorldTarget.x - headPos.x;
        const dy = this._lookAtWorldTarget.y - headPos.y;
        const dz = this._lookAtWorldTarget.z - headPos.z;
        // Body-local direction: rotate (dx, dy, dz) by -bodyHeading around Y
        const cy = Math.cos(-this.controller.heading);
        const sy = Math.sin(-this.controller.heading);
        const lx = cy * dx + sy * dz;
        const ly = dy;
        const lz = -sy * dx + cy * dz;
        // After body-local rotation, +Z is body forward.
        const yaw = Math.atan2(lx, lz);
        const horizDist = Math.sqrt(lx * lx + lz * lz);
        const pitch = -Math.atan2(ly, horizDist);   // looking up = negative dy → positive pitch
        this._headYawTarget = Math.max(-this.yawLimit, Math.min(this.yawLimit, yaw));
        this._headPitchTarget = Math.max(-this.pitchLimit, Math.min(this.pitchLimit, pitch));
    }

    _applyHeadOverride(dt) {
        if (!this.headBone) return;
        // Apply YXZ rotation (yaw on Y, pitch on X) on top of the rest
        // quaternion baked from the current animation frame. We REPLACE
        // the head's local quaternion — the animation sets it during
        // mixer.update, then we override here. This loses any animated
        // head bobble, which is acceptable: gaze stability matters more
        // than micro-bobble.
        const e = new THREE.Euler(this._headPitchCurrent, this._headYawCurrent, 0, 'YXZ');
        this.headBone.quaternion.setFromEuler(e);
    }

    _remainingPath(pos) {
        if (!this._currentPath) return [];
        // Find the closest path point and return the slice from there.
        let bestI = 0;
        let bestD = Infinity;
        for (let i = 0; i < this._currentPath.length; i++) {
            const p = this._currentPath[i];
            const d = (p.x - pos.x) ** 2 + (p.z - pos.z) ** 2;
            if (d < bestD) { bestD = d; bestI = i; }
        }
        return this._currentPath.slice(bestI);
    }

    _replan(t) {
        if (!this._currentGoal) return;
        const pos = this.getPosition();
        const newPath = this.planner.findPath(this.memory, pos.x, pos.z, this._currentGoal.x, this._currentGoal.z);
        this._lastReplanTime = t;
        if (!newPath) {
            // Goal unreachable from new info — fail the action
            if (this._pendingAction) {
                this._pendingAction.reject(new Error('replan: goal unreachable'));
                this._pendingAction = null;
            }
            this.controller.setWaypoints([]);
            this._currentPath = null;
            this._currentGoal = null;
            return;
        }
        this._currentPath = newPath;
        const wps = newPath.slice(1).map(p => ({ x: p.x, z: p.z, action: this._currentGoal.mode }));
        this.controller.setWaypoints(wps);
        this._blockedSince = -1;
    }

    _checkStuck(t, dt) {
        // Track whether the controller is making progress along its current
        // waypoint. If position hasn't changed appreciably for a while AND
        // the controller thinks it's walking, force a replan.
        if (!this._stuckCheck) {
            this._stuckCheck = { lastPos: this.getPosition(), lastTime: t };
            return;
        }
        const pos = this.getPosition();
        const dx = pos.x - this._stuckCheck.lastPos.x;
        const dz = pos.z - this._stuckCheck.lastPos.z;
        const moved = Math.sqrt(dx * dx + dz * dz);
        const dt_ = t - this._stuckCheck.lastTime;
        if (dt_ < 0.5) return;
        const speed = moved / dt_;
        const expectedSpeed = this._currentGoal && this._currentGoal.mode === 'run'
            ? this.controller.runSpeed * 0.3
            : this.controller.walkSpeed * 0.3;
        const isMoving = this.controller.getState() === 'walking' || this.controller.getState() === 'running';
        if (isMoving && speed < expectedSpeed) {
            if (this._blockedSince < 0) this._blockedSince = t;
            // Force replan after cooldown
            if ((t - this._lastReplanTime) > this._replanCooldown) {
                this._replan(t);
            }
        } else {
            this._blockedSince = -1;
        }
        this._stuckCheck.lastPos = pos;
        this._stuckCheck.lastTime = t;
    }

    _resolvePendingAction() {
        if (!this._pendingAction) return;
        const a = this._pendingAction;
        const cs = this.controller.getState();

        if (a.kind === 'walking' || a.kind === 'running') {
            if (cs === 'idle' && this.controller.waypointIndex >= this.controller.waypoints.length) {
                this._pendingAction = null;
                this._currentPath = null;
                this._currentGoal = null;
                a.resolve();
            }
        } else if (a.kind === 'lookingAt') {
            const yawErr = Math.abs(this._headYawTarget - this._headYawCurrent);
            const pitchErr = Math.abs(this._headPitchTarget - this._headPitchCurrent);
            if (yawErr < 0.05 && pitchErr < 0.05) {
                this._pendingAction = null;
                a.resolve();
                if (!a.hold) this._lookAtWorldTarget = null;
            }
        } else if (a.kind === 'scanning') {
            // Resolve when scan loop has marked done AND head returned to neutral
            if (a._scanDone && Math.abs(this._headYawCurrent) < 0.05) {
                this._pendingAction = null;
                a.resolve();
            }
        } else if (a.kind === 'performing') {
            if (cs !== 'performing') {
                this._pendingAction = null;
                a.resolve();
            }
        }
    }
}

if (typeof window !== 'undefined') window.VRMRobotBody = VRMRobotBody;
