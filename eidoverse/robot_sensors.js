/**
 * RobotSensors — depth-camera-like raycast cone for VRMRobotBody.
 *
 * This is the ONLY module in the VRMRobotBody stack that touches scene
 * geometry directly. RobotMemory, RobotPlanner, and the body itself work
 * exclusively from sensor readings — no god's-eye access to colliders or
 * mesh lists.
 *
 * Each sense() call casts a configurable horizontal × vertical fan of rays
 * from a given world origin in a given direction. Returns a list of hits
 * (one per ray) including distance, world hit point, surface normal, and
 * the THREE object that was hit. Rays that don't hit anything return at
 * max range with `hit: false`.
 *
 * Conventions:
 *   - Cone is symmetric around its central axis (the heading direction).
 *   - hFov / vFov are TOTAL angles (so hFov=110 means ±55° from center).
 *   - Origin should typically be the head bone's world position; direction
 *     should be the head's forward direction (combining body heading and
 *     head bone yaw + pitch).
 *   - excludeObjects skips raycasts against the listed Object3Ds and all
 *     their descendants. Use this to skip the VRM's own body so the body's
 *     geometry doesn't show up as obstacles in its own sensors.
 *
 * Usage:
 *   const sensors = new RobotSensors(scene, {
 *       hFov: 110, vFov: 70, range: 6, hRays: 24, vRays: 16,
 *       excludeObjects: [vrm.scene],
 *   });
 *
 *   const reading = sensors.sense(originVec3, headingRad, pitchRad);
 *   // reading: {
 *   //     origin: Vector3,
 *   //     heading: number, pitch: number,
 *   //     hits: [
 *   //         { dir: Vector3, hit: bool, distance: number,
 *   //           point: Vector3, normal: Vector3 | null, object: Object3D | null,
 *   //           rayYaw: number, rayPitch: number }
 *   //         ...one entry per ray...
 *   //     ],
 *   //     count: number, hitCount: number,
 *   // }
 */

class RobotSensors {
    constructor(scene, opts = {}) {
        this.scene = scene;
        this.hFov = (opts.hFov !== undefined ? opts.hFov : 110) * Math.PI / 180;
        this.vFov = (opts.vFov !== undefined ? opts.vFov : 70) * Math.PI / 180;
        this.range = opts.range !== undefined ? opts.range : 6;
        // 16x14 = 224 rays. The vertical density matters most: with too
        // few vertical rays, stair treads (each 0.2m apart) fall between
        // the ray angles and never get detected as walkable surfaces,
        // causing the body to plan around stair geometry as if it were
        // a wall. 14 vRays at 70° vFov gives 5° spacing — fine enough
        // to hit every stair tread within 6m range.
        this.hRays = opts.hRays !== undefined ? opts.hRays : 16;
        this.vRays = opts.vRays !== undefined ? opts.vRays : 14;
        this.excludeObjects = opts.excludeObjects || [];

        this._raycaster = new THREE.Raycaster();
        this._raycaster.far = this.range;

        // Pre-compute the local-space ray directions (axis-aligned, then
        // rotated each call by the heading + pitch). Rays are fired along
        // the +Z axis with yaw spread on X and pitch spread on Y; we then
        // build a basis at sense() time to point them at heading.
        this._localRays = this._buildLocalRays();

        // Pre-flattened raycast target list — leaf meshes only, with all
        // descendants of excluded subtrees pruned. This is THE big perf
        // win: instead of asking the Raycaster to recurse through all of
        // scene.children (which includes the VRM's 11 meshes with hundreds
        // of thousands of vertices), we hand it a flat list of just the
        // walkable/visible geometry. Pass `recursive: false` to the
        // intersectObjects call so it doesn't re-traverse.
        // Call refresh() to rebuild after adding/removing meshes mid-scene.
        this._targets = [];
        this.refresh();

        // Reusable scratch
        this._tmpDir = new THREE.Vector3();
        this._tmpForward = new THREE.Vector3();
        this._tmpRight = new THREE.Vector3();
        this._tmpUp = new THREE.Vector3();
        this._worldUp = new THREE.Vector3(0, 1, 0);
    }

    /**
     * Walk the scene graph and flatten all visible Mesh leaves into a list,
     * skipping any that are descendants of an excluded object. Call this
     * after the scene composition changes (added a new wall, hid a mesh,
     * etc.) to refresh the raycast target list.
     *
     * Also builds a BVH (bounding volume hierarchy) on every target mesh
     * the first time it's seen. three-mesh-bvh's accelerated raycast uses
     * the BVH to skip 99%+ of triangle tests for typical scenes — without
     * it, sensing 128 rays/frame against a few thousand triangles drops
     * the entire renderer to single digit FPS.
     */
    refresh() {
        const targets = [];
        const excluded = new Set(this.excludeObjects);
        const isExcluded = (obj) => {
            let cur = obj;
            while (cur) {
                if (excluded.has(cur)) return true;
                cur = cur.parent;
            }
            return false;
        };
        const hasBVH = (typeof MeshBVH !== 'undefined') &&
            (typeof THREE !== 'undefined') &&
            (typeof THREE.BufferGeometry.prototype.computeBoundsTree === 'function');
        this.scene.traverse((obj) => {
            if (!obj.isMesh) return;
            if (isExcluded(obj)) return;
            if (obj.visible === false) return;
            if (hasBVH && obj.geometry && !obj.geometry.boundsTree) {
                try { obj.geometry.computeBoundsTree(); }
                catch (e) { /* skinned/morph geometries can fail; fall back to slow raycast */ }
            }
            targets.push(obj);
        });
        this._targets = targets;
        return targets.length;
    }

    _buildLocalRays() {
        const rays = [];
        // Cone around +Z. yaw spreads across hFov, pitch across vFov.
        // For hRays=1, single ray straight ahead. Otherwise distribute evenly.
        for (let yi = 0; yi < this.vRays; yi++) {
            const pitch = this.vRays === 1
                ? 0
                : -this.vFov / 2 + (yi / (this.vRays - 1)) * this.vFov;
            for (let xi = 0; xi < this.hRays; xi++) {
                const yaw = this.hRays === 1
                    ? 0
                    : -this.hFov / 2 + (xi / (this.hRays - 1)) * this.hFov;
                // Ray direction in local cone space (forward = +Z)
                // yaw rotates around Y, pitch around X
                const cy = Math.cos(yaw), sy = Math.sin(yaw);
                const cp = Math.cos(pitch), sp = Math.sin(pitch);
                // Forward = (0,0,1), apply pitch first then yaw:
                //   after pitch:  (0, sp, cp)... wait, pitch around X axis:
                //   (x', y', z') = (x, y*cp - z*sp, y*sp + z*cp)
                //   from (0,0,1): (0, -sp, cp)
                // then yaw around Y axis:
                //   (x'', y'', z'') = (x'*cy + z'*sy, y', -x'*sy + z'*cy)
                //   from (0, -sp, cp): (cp*sy, -sp, cp*cy)
                rays.push({
                    rayYaw: yaw,
                    rayPitch: pitch,
                    local: new THREE.Vector3(cp * sy, -sp, cp * cy),
                });
            }
        }
        return rays;
    }

    /**
     * Cast the ray cone from `origin` in the direction defined by `headingRad`
     * (yaw, world Y axis, 0 = facing +Z) and `pitchRad` (looking up = positive).
     * Returns a reading object — see file header for the shape.
     */
    sense(origin, headingRad, pitchRad) {
        if (pitchRad === undefined) pitchRad = 0;

        // Build the world-space basis for the cone:
        //   forward = (sin(h)*cos(p), -sin(p), cos(h)*cos(p))
        //   right   = (cos(h),         0,        -sin(h))
        //   up      = forward × right ... no, right × forward
        const cy = Math.cos(headingRad), sy = Math.sin(headingRad);
        const cp = Math.cos(pitchRad), sp = Math.sin(pitchRad);
        this._tmpForward.set(sy * cp, -sp, cy * cp);
        this._tmpRight.set(cy, 0, -sy);
        // Recompute up so it stays orthogonal even when looking up/down
        this._tmpUp.crossVectors(this._tmpRight, this._tmpForward).normalize();

        // Build raycast targets list: scene.children minus excluded subtrees.
        // (We rely on Raycaster's recursive flag and post-filter the hits.)
        const reading = {
            origin: origin.clone(),
            heading: headingRad,
            pitch: pitchRad,
            hits: new Array(this._localRays.length),
            count: this._localRays.length,
            hitCount: 0,
        };

        for (let i = 0; i < this._localRays.length; i++) {
            const ray = this._localRays[i];
            // Transform local ray dir into world space using the basis.
            // local = (lx, ly, lz) where +Z is forward
            //   worldDir = lx*right + ly*up + lz*forward
            const lx = ray.local.x, ly = ray.local.y, lz = ray.local.z;
            this._tmpDir.set(
                lx * this._tmpRight.x + ly * this._tmpUp.x + lz * this._tmpForward.x,
                lx * this._tmpRight.y + ly * this._tmpUp.y + lz * this._tmpForward.y,
                lx * this._tmpRight.z + ly * this._tmpUp.z + lz * this._tmpForward.z
            ).normalize();

            this._raycaster.set(origin, this._tmpDir);
            this._raycaster.far = this.range;
            // Pre-flattened target list, recursive=false — no scene-graph
            // traversal, no excluded geometry visited.
            const intersects = this._raycaster.intersectObjects(this._targets, false);
            const hit = intersects.length > 0 ? intersects[0] : null;

            if (hit) {
                let normal = null;
                if (hit.face && hit.object.matrixWorld) {
                    normal = hit.face.normal.clone().transformDirection(hit.object.matrixWorld).normalize();
                }
                reading.hits[i] = {
                    dir: this._tmpDir.clone(),
                    hit: true,
                    distance: hit.distance,
                    point: hit.point.clone(),
                    normal,
                    object: hit.object,
                    rayYaw: ray.rayYaw,
                    rayPitch: ray.rayPitch,
                };
                reading.hitCount++;
            } else {
                // No hit — synthetic miss point at max range
                reading.hits[i] = {
                    dir: this._tmpDir.clone(),
                    hit: false,
                    distance: this.range,
                    point: new THREE.Vector3(
                        origin.x + this._tmpDir.x * this.range,
                        origin.y + this._tmpDir.y * this.range,
                        origin.z + this._tmpDir.z * this.range
                    ),
                    normal: null,
                    object: null,
                    rayYaw: ray.rayYaw,
                    rayPitch: ray.rayPitch,
                };
            }
        }

        return reading;
    }

    /**
     * Cast a single arbitrary ray. Useful for canSee() / quick LOS checks.
     * Returns {hit, distance, point, normal, object} or null if origin/dir
     * are bad.
     */
    castOne(origin, dir, maxDist) {
        if (!origin || !dir) return null;
        const d = (typeof dir.normalize === 'function') ? dir.clone().normalize() : new THREE.Vector3(dir.x, dir.y, dir.z).normalize();
        this._raycaster.set(origin, d);
        this._raycaster.far = maxDist !== undefined ? maxDist : this.range;
        const intersects = this._raycaster.intersectObjects(this._targets, false);
        if (intersects.length === 0) {
            return { hit: false, distance: this._raycaster.far, point: null, normal: null, object: null };
        }
        const it = intersects[0];
        let normal = null;
        if (it.face && it.object.matrixWorld) {
            normal = it.face.normal.clone().transformDirection(it.object.matrixWorld).normalize();
        }
        return {
            hit: true,
            distance: it.distance,
            point: it.point.clone(),
            normal,
            object: it.object,
        };
    }

    /**
     * Add an object (and its descendants) to the exclusion list at runtime.
     * Used by VRMRobotBody after the VRM is loaded. Triggers a target list
     * refresh.
     */
    exclude(obj) {
        if (!obj) return;
        if (this.excludeObjects.indexOf(obj) === -1) {
            this.excludeObjects.push(obj);
            this.refresh();
        }
    }
}

if (typeof window !== 'undefined') window.RobotSensors = RobotSensors;
