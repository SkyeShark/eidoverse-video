(function() {
    'use strict';

    /**
     * CameraSafety — camera path checker + per-frame collision guard.
     * Uses Three.js Raycaster (no Rapier needed).
     *
     * Usage:
     *   const cam = new CameraSafety(scene);
     *   cam.exclude(ground);
     *
     *   // Check path BEFORE rendering — returns issues for you to fix
     *   const issues = cam.checkPath(keyframes);
     *   if (issues.length) console.warn('Camera issues:', issues);
     *   // Fix your keyframes based on the issues, then render
     *
     *   // Per-frame safety net in renderFrame(t):
     *   camera.position.copy(cam.safePosition(desiredPos, lookAtTarget));
     */
    function CameraSafety(scene, opts) {
        opts = opts || {};
        this.scene = scene;
        this.padding = opts.padding != null ? opts.padding : 0.5;
        this.minDistance = opts.minDistance != null ? opts.minDistance : 0.3;
        this._raycaster = new THREE.Raycaster();
        this._meshes = [];
        this._dir = new THREE.Vector3();
        this._excludeSet = new Set();

        this.refresh();
    }

    /**
     * Re-scan the scene for meshes. Call if you add objects after construction.
     */
    CameraSafety.prototype.refresh = function() {
        this._meshes = [];
        var self = this;
        this.scene.traverse(function(child) {
            if (child.isMesh && !self._excludeSet.has(child)) {
                self._meshes.push(child);
            }
        });
    };

    /**
     * Exclude specific objects from collision (ground plane, skybox, transparent
     * objects, the SUBJECT). Accepts a mesh, a Group (gltf.scene / vrm.scene —
     * every child mesh is excluded), or an array of either.
     */
    CameraSafety.prototype.exclude = function(obj) {
        var self = this;
        function add(o) {
            if (!o) return;
            if (o.traverse) {
                o.traverse(function(child) { if (child.isMesh) self._excludeSet.add(child); });
            }
            self._excludeSet.add(o);
        }
        if (Array.isArray(obj)) {
            for (var i = 0; i < obj.length; i++) add(obj[i]);
        } else {
            add(obj);
        }
        this.refresh();
    };

    // Internal: check if a ray from target to pos is clear
    CameraSafety.prototype._isClear = function(pos, target, padding) {
        var dir = pos.clone().sub(target);
        var dist = dir.length();
        if (dist < 0.001) return { clear: false, distance: 0, object: null };
        dir.normalize();
        this._raycaster.set(target, dir);
        this._raycaster.far = dist;
        this._raycaster.near = 0;
        var hits = this._raycaster.intersectObjects(this._meshes, false);
        if (hits.length > 0 && hits[0].distance < dist - (padding || this.padding) * 0.5) {
            return { clear: false, distance: hits[0].distance, object: hits[0].object };
        }
        return { clear: true, distance: dist, object: null };
    };

    /**
     * Check a camera path for obstructions. Returns an array of issues.
     * Call in setup() after building the scene — use the results to fix your keyframes.
     *
     * Also checks interpolated positions between keyframes (samples 5 points per segment)
     * since the camera can clip through objects mid-transition even if both endpoints are clear.
     *
     * @param {Array} keyframes — [{ time, position: [x,y,z], target: [x,y,z] }]
     * @param {Object} opts — { padding, samplesPerSegment (default 5) }
     * @returns {Array} — issues found. Empty = path is clean.
     *   Each issue: {
     *     index: keyframe index (or -1 for interpolated),
     *     time: seconds,
     *     position: [x,y,z] of the obstructed camera position,
     *     target: [x,y,z] what it was looking at,
     *     obstruction: name of the blocking object (or "unnamed_mesh"),
     *     hitDistance: how far the ray got before hitting,
     *     desiredDistance: how far it needed to go,
     *     severity: "blocked" (fully behind object) | "tight" (within padding),
     *     suggestion: [x,y,z] nearest clear position at same distance from target,
     *   }
     */
    CameraSafety.prototype.checkPath = function(keyframes, opts) {
        var padding = (opts && opts.padding != null) ? opts.padding : this.padding;
        var samplesPerSeg = (opts && opts.samplesPerSegment) || 5;
        var issues = [];
        var self = this;

        function getObjectName(obj) {
            if (!obj) return 'unknown';
            if (obj.name) return obj.name;
            if (obj.parent && obj.parent.name) return obj.parent.name;
            return 'unnamed_mesh';
        }

        function findSuggestion(pos, tgt) {
            var offset = pos.clone().sub(tgt);
            var radius = offset.length();
            var bestPos = null;
            var bestDist = Infinity;
            var phi = (1 + Math.sqrt(5)) / 2;
            var numSamples = 24;

            for (var i = 0; i < numSamples; i++) {
                var y = 1 - (2 * i / (numSamples - 1));
                var r = Math.sqrt(1 - y * y);
                var theta = 2 * Math.PI * i / phi;
                var candidate = new THREE.Vector3(
                    tgt.x + r * Math.cos(theta) * radius,
                    tgt.y + y * radius,
                    tgt.z + r * Math.sin(theta) * radius
                );
                if (candidate.y < tgt.y - 0.5) continue;

                var check = self._isClear(candidate, tgt, padding);
                if (check.clear) {
                    var d = candidate.distanceTo(pos);
                    if (d < bestDist) {
                        bestDist = d;
                        bestPos = candidate;
                    }
                }
            }
            return bestPos ? [
                Math.round(bestPos.x * 10) / 10,
                Math.round(bestPos.y * 10) / 10,
                Math.round(bestPos.z * 10) / 10
            ] : null;
        }

        function checkPoint(pos, tgt, index, time) {
            var check = self._isClear(pos, tgt, padding);
            if (!check.clear) {
                var desiredDist = pos.distanceTo(tgt);
                var severity = check.distance < desiredDist * 0.5 ? 'blocked' : 'tight';
                issues.push({
                    index: index,
                    time: Math.round(time * 100) / 100,
                    position: [
                        Math.round(pos.x * 10) / 10,
                        Math.round(pos.y * 10) / 10,
                        Math.round(pos.z * 10) / 10
                    ],
                    target: [
                        Math.round(tgt.x * 10) / 10,
                        Math.round(tgt.y * 10) / 10,
                        Math.round(tgt.z * 10) / 10
                    ],
                    obstruction: getObjectName(check.object),
                    hitDistance: Math.round(check.distance * 100) / 100,
                    desiredDistance: Math.round(desiredDist * 100) / 100,
                    severity: severity,
                    suggestion: findSuggestion(pos, tgt),
                });
            }
        }

        // Check each keyframe
        for (var i = 0; i < keyframes.length; i++) {
            var kf = keyframes[i];
            var pos = new THREE.Vector3().fromArray(kf.position);
            var tgt = new THREE.Vector3().fromArray(kf.target);
            checkPoint(pos, tgt, i, kf.time);
        }

        // Check interpolated points between keyframes
        for (var i = 0; i < keyframes.length - 1; i++) {
            var kfA = keyframes[i];
            var kfB = keyframes[i + 1];
            var posA = new THREE.Vector3().fromArray(kfA.position);
            var posB = new THREE.Vector3().fromArray(kfB.position);
            var tgtA = new THREE.Vector3().fromArray(kfA.target);
            var tgtB = new THREE.Vector3().fromArray(kfB.target);

            for (var s = 1; s <= samplesPerSeg; s++) {
                var alpha = s / (samplesPerSeg + 1);
                // Smoothstep
                var sm = alpha * alpha * (3 - 2 * alpha);
                var midPos = posA.clone().lerp(posB, sm);
                var midTgt = tgtA.clone().lerp(tgtB, sm);
                var midTime = kfA.time + (kfB.time - kfA.time) * alpha;
                checkPoint(midPos, midTgt, -1, midTime);
            }
        }

        // Sort by time
        issues.sort(function(a, b) { return a.time - b.time; });

        // Log summary
        if (issues.length > 0) {
            console.warn('[CameraSafety] checkPath found ' + issues.length + ' issue(s):');
            for (var i = 0; i < issues.length; i++) {
                var iss = issues[i];
                var kfLabel = iss.index >= 0 ? 'keyframe ' + iss.index : 'interpolated';
                console.warn('  t=' + iss.time + 's (' + kfLabel + ') ' + iss.severity +
                    ' by "' + iss.obstruction + '" at ' + iss.hitDistance + 'm/' + iss.desiredDistance + 'm' +
                    (iss.suggestion ? ' — try ' + JSON.stringify(iss.suggestion) : ' — no clear alternative found'));
            }
        } else {
            console.log('[CameraSafety] checkPath: all clear ✓');
        }

        return issues;
    };

    /**
     * Per-frame safety net — nudges camera position if it's about to clip.
     * Use as a last resort in renderFrame(t). Prefer fixing the path via checkPath().
     *
     * @param {THREE.Vector3} desired — where the camera wants to be
     * @param {THREE.Vector3} target — what the camera is looking at
     * @param {Object} opts — { padding, minDistance }
     * @returns {THREE.Vector3} — safe position (may equal desired if no obstruction)
     */
    CameraSafety.prototype.safePosition = function(desired, target, opts) {
        var padding = (opts && opts.padding != null) ? opts.padding : this.padding;
        var minDist = (opts && opts.minDistance != null) ? opts.minDistance : this.minDistance;

        this._dir.copy(desired).sub(target);
        var fullDist = this._dir.length();
        if (fullDist < 0.001) return desired.clone();
        this._dir.normalize();

        this._raycaster.set(target, this._dir);
        this._raycaster.far = fullDist;
        this._raycaster.near = 0;

        var hits = this._raycaster.intersectObjects(this._meshes, false);
        if (hits.length > 0) {
            var hitDist = hits[0].distance;
            var safeDist = Math.max(minDist, hitDist - padding);
            if (safeDist < fullDist) {
                return target.clone().add(this._dir.clone().multiplyScalar(safeDist));
            }
        }

        return desired.clone();
    };

    window.CameraSafety = CameraSafety;

    // ─── Agent-discoverable help ───
    CameraSafety.help = function () {
        const lines = [
            '────────── CameraSafety API reference ──────────',
            '',
            'Camera path checker + per-frame collision guard. Uses THREE.Raycaster',
            "(no Rapier needed). Catches camera paths that clip through walls/props.",
            '',
            '── Construction ──',
            '  const cam = new CameraSafety(scene);',
            '  cam.exclude(ground); cam.exclude(skyDome);   // surfaces to ignore',
            '',
            '── checkPath: verify a planned camera path BEFORE rendering ──',
            '  const issues = cam.checkPath([',
            '    { time: 0,  position: [0, 2, 8],  target: [0, 1, 0] },',
            '    { time: 5,  position: [3, 1.5, -2], target: [0, 1, 0] },',
            '  ]);',
            '  // issues = [{ index, time, severity, obstruction, hitDistance,',
            '  //            desiredDistance, position, target, suggestion }]',
            '  // Empty array = path is clean. If issues, fix your keyframes (the',
            '  // suggestion field gives a nearby clear position) BEFORE rendering.',
            '',
            '── safePosition: per-frame guard during free-form camera movement ──',
            '  const safe = cam.safePosition(desiredPos, target);',
            '  camera.position.copy(safe);',
            '  // Pulls camera back if it would clip into a registered mesh.',
            "  // Won't reroute or change shot framing — just prevents worst-case clip.",
            '',
            '── Other methods ──',
            '  cam.exclude(meshOrArray)   surfaces the safety check should ignore',
            '  cam.refresh()              re-scan scene for meshes (call after late add)',
            '',
            '── Common gotchas ──',
            '  • Always exclude the ground plane and skybox (every keyframe will hit them).',
            "  • checkPath() also samples interpolated points between keyframes — catches",
            "    mid-transition clips, not just endpoints.",
            '  • safePosition() is a band-aid — use checkPath() in setup() to fix the path',
            '    properly. Use safePosition() only for free-form movement (e.g. CharacterController',
            '    follow shots) where you can\'t pre-plan keyframes.',
            '',
            'Source: /opt/render3d/camera_safety.js',
        ];
        const msg = lines.join('\n');
        console.log(msg);
        return msg;
    };

    console.log('[camera_safety] Loaded: CameraSafety(scene) — checkPath, safePosition, exclude, refresh. Call CameraSafety.help() for API reference.');
})();
