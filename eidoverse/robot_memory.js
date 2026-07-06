/**
 * RobotMemory — 2D occupancy grid + landmark dictionary for VRMRobotBody.
 *
 * This is the body's internal model of the world. It is built up over time
 * from RobotSensors readings — the body's only contact with truth — and is
 * what RobotPlanner queries when computing paths. The memory NEVER gets
 * direct access to scene meshes, colliders, or the god's-eye list of
 * obstacles. Everything in here was learned through sensor cone hits.
 *
 * The grid is a top-down (XZ plane) world-anchored array of cells. Each
 * cell is a single byte storing:
 *   - state in low 4 bits:  0=unknown, 1=free, 2=blocked, 3=cliff, 4=hazard
 *   - confidence in high 4 bits: 0-15 (Bayesian-ish damped certainty)
 *
 * A cell becomes "confidently known" only after multiple consistent
 * observations. A single jittery raycast won't permanently change a cell.
 *
 * Conventions:
 *   - Grid is square, side `size` meters, cell size `cellSize` meters.
 *   - Default size 50 m × 50 m at 0.2 m cells = 250×250 cells.
 *   - Center of grid is at world (originX, originZ) — pass these to put
 *     the grid where you want it. Default origin (0,0).
 *   - state UNKNOWN cells are walkable when the planner is in optimistic
 *     mode (default). The body confidently strides into unmapped territory
 *     and replans when sensors reveal something blocking.
 *
 * Usage:
 *   const memory = new RobotMemory({ size: 50, cellSize: 0.2 });
 *   memory.applySensorReading(reading, { floorY: 0 });   // each frame
 *   memory.tagLandmark('door', 5, -3, { type: 'door' });
 *   memory.getCellState(cx, cz);                          // STATE_FREE etc.
 *   memory.serialize();                                   // save
 *
 * Designed to be lifted out of the video harness and into a standalone
 * vrm-robot-body npm package. No dependencies on render_scene.mjs internals.
 */

const STATE_UNKNOWN = 0;
const STATE_FREE    = 1;
const STATE_BLOCKED = 2;
const STATE_CLIFF   = 3;
const STATE_HAZARD  = 4;

class RobotMemory {
    constructor(opts = {}) {
        this.size = opts.size !== undefined ? opts.size : 50;          // meters
        this.cellSize = opts.cellSize !== undefined ? opts.cellSize : 0.2;
        this.originX = opts.originX !== undefined ? opts.originX : 0;
        this.originZ = opts.originZ !== undefined ? opts.originZ : 0;
        this.bayesian = opts.bayesian !== undefined ? opts.bayesian : true;
        this.maxConfidence = 15;
        // 2.5D: how far below the body's standing Y a hit must be before
        // it's classified as a cliff edge instead of "low ground." Default
        // 1.0 m so a normal stair drop (0.2m) is fine but a 1.5m balcony
        // edge gets flagged.
        this.cliffThreshold = opts.cliffThreshold !== undefined ? opts.cliffThreshold : 1.0;
        // How far above the body's standing Y is still "the floor I'm on"
        // (a stair step UP). Default 0.4 m matches typical stair tread.
        this.stepUpTolerance = opts.stepUpTolerance !== undefined ? opts.stepUpTolerance : 0.4;

        this.cellsPerSide = Math.ceil(this.size / this.cellSize);
        // Cell origin (0,0) is at world (originX - size/2, originZ - size/2)
        this.gridMinX = this.originX - this.size / 2;
        this.gridMinZ = this.originZ - this.size / 2;

        // Flat Uint8Array of cells (state in low 4 bits, confidence in high 4 bits)
        this.cells = new Uint8Array(this.cellsPerSide * this.cellsPerSide);

        // 2.5D: walkable surface height at each cell. NaN = unknown (no
        // floor-ray has confirmed a surface here). Updated by observeCell
        // when state goes to FREE with a y argument.
        this.surfaceY = new Float32Array(this.cellsPerSide * this.cellsPerSide);
        this.surfaceY.fill(NaN);

        // 2.5D: blocking height at each cell — the world Y of the
        // recorded wall/obstacle hit. NaN = no blocking record. Used by
        // the planner's dilation check to ignore walls that don't
        // actually intersect the body's vertical column at the candidate
        // cell's standing surface (e.g. an overhead beam doesn't dilate
        // ground-floor cells, a wall on a platform doesn't dilate cells
        // beneath the platform).
        this.blockingY = new Float32Array(this.cellsPerSide * this.cellsPerSide);
        this.blockingY.fill(NaN);

        // Landmark dictionary: name -> {x, z, type, lastSeen, metadata}
        this.landmarks = new Map();

        // Stats
        this.observationCount = 0;
    }

    // ============================================================
    //  COORDINATE CONVERSION
    // ============================================================

    worldToCell(x, z) {
        const cx = Math.floor((x - this.gridMinX) / this.cellSize);
        const cz = Math.floor((z - this.gridMinZ) / this.cellSize);
        if (cx < 0 || cx >= this.cellsPerSide || cz < 0 || cz >= this.cellsPerSide) return null;
        return { cx, cz };
    }

    cellToWorld(cx, cz) {
        return {
            x: this.gridMinX + (cx + 0.5) * this.cellSize,
            z: this.gridMinZ + (cz + 0.5) * this.cellSize,
        };
    }

    inBounds(cx, cz) {
        return cx >= 0 && cx < this.cellsPerSide && cz >= 0 && cz < this.cellsPerSide;
    }

    // ============================================================
    //  CELL ACCESS
    // ============================================================

    _idx(cx, cz) { return cz * this.cellsPerSide + cx; }

    getCellRaw(cx, cz) {
        if (!this.inBounds(cx, cz)) return 0;
        return this.cells[this._idx(cx, cz)];
    }

    getCellState(cx, cz) {
        return this.getCellRaw(cx, cz) & 0x0F;
    }

    getCellConfidence(cx, cz) {
        return (this.getCellRaw(cx, cz) >> 4) & 0x0F;
    }

    setCellRaw(cx, cz, value) {
        if (!this.inBounds(cx, cz)) return;
        this.cells[this._idx(cx, cz)] = value;
    }

    /**
     * Bayesian-style observation update: nudges the cell state and
     * confidence toward the observed state. Multiple consistent
     * observations of the same state grow confidence; conflicting
     * observations erode it before flipping it.
     *
     * `y` is optional and means different things depending on state:
     *   - For STATE_FREE / STATE_CLIFF: walkable surface height. Blends
     *     into surfaceY[cell] (running average).
     *   - For STATE_BLOCKED: the world Y of the wall hit. Blends into
     *     blockingY[cell] (max-of-observations, so the recorded wall
     *     height tracks the tallest hit seen so far). Used by the
     *     planner's vertical-column dilation check.
     */
    observeCell(cx, cz, observedState, y) {
        if (!this.inBounds(cx, cz)) return;
        if (observedState === STATE_UNKNOWN) return;
        const idx = this._idx(cx, cz);
        const cell = this.cells[idx];
        const curState = cell & 0x0F;
        const curConf = (cell >> 4) & 0x0F;

        let newState, newConf;
        if (!this.bayesian) {
            newState = observedState;
            newConf = this.maxConfidence;
        } else if (curState === STATE_UNKNOWN || curState === observedState) {
            newState = observedState;
            newConf = Math.min(this.maxConfidence, curConf + 1);
        } else {
            // Conflict — confidence erodes. Flip when it hits 0.
            if (curConf <= 1) {
                newState = observedState;
                newConf = 1;
            } else {
                newState = curState;
                newConf = curConf - 1;
            }
        }
        this.cells[idx] = (newConf << 4) | newState;

        // Update surface height for FREE observations that came with a y.
        // Use a confidence-weighted running average so a single noisy
        // raycast doesn't dominate the surface estimate.
        if (y !== undefined && (newState === STATE_FREE || newState === STATE_CLIFF)) {
            const cur = this.surfaceY[idx];
            if (isNaN(cur)) {
                this.surfaceY[idx] = y;
            } else {
                const w = Math.min(curConf, this.maxConfidence - 1);
                this.surfaceY[idx] = (cur * w + y) / (w + 1);
            }
        }

        // Update blocking height for BLOCKED observations that came with
        // a y. We track the MAX recorded blocking Y (the tallest wall hit
        // so far) so the dilation check knows how high the obstruction
        // extends. Walls with multiple hits at increasing Y will converge
        // to their actual top.
        if (y !== undefined && newState === STATE_BLOCKED) {
            const cur = this.blockingY[idx];
            if (isNaN(cur) || y > cur) {
                this.blockingY[idx] = y;
            }
        }
    }

    /**
     * Read the walkable surface height at a cell, or NaN if unknown.
     */
    getCellSurfaceY(cx, cz) {
        if (!this.inBounds(cx, cz)) return NaN;
        return this.surfaceY[this._idx(cx, cz)];
    }

    // ============================================================
    //  SENSOR READING APPLICATION
    // ============================================================

    /**
     * Walk every ray in a sensor reading through the grid, applying free
     * and blocked observations to the cells the ray crosses or hits.
     *
     * The non-obvious part: when the cone fans out from a head at ~1.5m
     * height, MOST rays travel through 3D space well above the floor.
     * They may pass over a low obstacle (a 0.7m crate) and hit a tall
     * wall behind it. Naively marking "all cells the ray traversed" as
     * FREE corrupts the map — the cells where the crate sits get marked
     * free even though the ray flew above the crate, never seeing its top.
     *
     * The honest classification is:
     *   - "Floor rays" (downward-pitched enough that they GRAZE the floor
     *     and reach floor Y within their range) provide reliable free-cell
     *     evidence. The body actually saw the floor of every cell the ray
     *     crossed before it hit something. Walk the cells and mark them
     *     FREE up to (and including) the hit cell. Mark the hit cell
     *     BLOCKED if the hit point is something other than the floor itself.
     *   - "Level / upward rays" provide UNRELIABLE free-cell evidence —
     *     they may have flown over short obstacles. Do NOT mark cells along
     *     the path as free. Only the HIT cell is touched: BLOCKED if the
     *     hit point is at agent-body height (within `agentHeight` of floor),
     *     otherwise nothing (the ray hit a ceiling or sky and tells us
     *     nothing useful for floor navigation).
     *
     * This produces a sparser but TRUSTWORTHY occupancy grid. The body
     * still maps the floor in front of it (downward rays do most of the
     * free-marking work) and detects walls/furniture (any hit at body
     * height marks the cell blocked), but it no longer assumes the floor
     * is clear under cells that an over-pitched ray happened to fly above.
     *
     * `floorY` is the body's current floor reference (typically position.y).
     * `agentHeight` is how tall the agent's body is (default 1.7m) —
     * obstacles within this height range count as blockers.
     */
    applySensorReading(reading, opts = {}) {
        if (!reading || !reading.hits) return;
        const floorY = opts.floorY !== undefined ? opts.floorY : 0;
        const agentHeight = opts.agentHeight !== undefined ? opts.agentHeight : 1.7;
        this.observationCount++;

        const ox = reading.origin.x;
        const oz = reading.origin.z;
        const stepUp = this.stepUpTolerance;
        const cliffDrop = this.cliffThreshold;

        // Two-pass classification. We need every floor observation to be
        // recorded BEFORE we decide whether a "wall hit" is actually a wall
        // or just the side of a step/platform whose top is walkable from
        // above. Pass 1 records floor evidence; pass 2 handles obstacle
        // hits, suppressing them when the cell already has a walkable
        // surface known to be above the hit Y.

        // Pre-compute cell coordinates for every ray once (used in both
        // passes).
        const N = reading.hits.length;
        const x0Arr = new Int32Array(N);
        const z0Arr = new Int32Array(N);
        const x1Arr = new Int32Array(N);
        const z1Arr = new Int32Array(N);
        for (let i = 0; i < N; i++) {
            const hit = reading.hits[i];
            if (!hit) continue;
            x0Arr[i] = Math.floor((ox - this.gridMinX) / this.cellSize);
            z0Arr[i] = Math.floor((oz - this.gridMinZ) / this.cellSize);
            x1Arr[i] = Math.floor((hit.point.x - this.gridMinX) / this.cellSize);
            z1Arr[i] = Math.floor((hit.point.z - this.gridMinZ) / this.cellSize);
        }

        // ---- PASS 1: floor evidence ----
        for (let i = 0; i < N; i++) {
            const hit = reading.hits[i];
            if (!hit) continue;
            const hy = hit.point.y;
            const pitch = hit.rayPitch || 0;
            const downwardEnough = pitch <= -10 * Math.PI / 180;
            const normalUp = hit.normal && hit.normal.y > 0.6;
            const drop = floorY - hy;

            if (!hit.hit) {
                // Miss at max range. Only downward-pitched rays generate
                // floor evidence (they would have hit the floor if there
                // had been one). Other miss directions tell us nothing.
                if (downwardEnough) {
                    this._bresenhamApplyFree(x0Arr[i], z0Arr[i], x1Arr[i], z1Arr[i], floorY);
                }
                continue;
            }
            // Any ACTUAL hit on a normal-up surface is REAL floor evidence,
            // regardless of pitch. A ray at -5° pitch that lands on a
            // platform top 4m away IS a floor observation — the body has
            // literally seen the surface. The downwardEnough check only
            // applied to MISSES (where we're inferring an absent floor).
            if (normalUp && drop <= cliffDrop) {
                this._bresenhamApplyFree(x0Arr[i], z0Arr[i], x1Arr[i], z1Arr[i], hy);
                continue;
            }
            // Floor hit far below body — cliff (a real drop-off)
            if (normalUp && drop > cliffDrop) {
                this.observeCell(x1Arr[i], z1Arr[i], STATE_CLIFF, hy);
                continue;
            }
        }

        // ---- PASS 2: wall classification ----
        // Pass 1 recorded all DIRECTLY OBSERVED walkable surfaces (floor
        // hits with normal pointing up). Pass 2 handles vertical face hits
        // (walls, platform fronts, true obstacles).
        //
        // Decision tree per hit:
        //   - normal up                 → handled by pass 1, skip
        //   - hit above body's head     → ceiling, ignore
        //   - hit within stepUp of floor → step riser of a walkable step,
        //                                  ignore (the step's top will
        //                                  be marked by floor rays)
        //   - cell already has a known walkable surface at or above
        //     hit Y → the wall is the side of a walkable platform whose
        //     top has been observed. Don't mark BLOCKED.
        //   - otherwise → real wall. Mark cell BLOCKED with blockingY.
        //
        // The cell index is offset INSIDE the wall (along ray direction)
        // so the BLOCKED marker lands in the cell behind the surface, not
        // on the boundary cell that's actually free space in front.
        for (let i = 0; i < N; i++) {
            const hit = reading.hits[i];
            if (!hit || !hit.hit) continue;
            const hy = hit.point.y;
            const normalUp = hit.normal && hit.normal.y > 0.6;
            if (normalUp) continue;
            if (hy >= floorY + agentHeight) continue;
            if (hy >= floorY - 0.05 && hy <= floorY + stepUp) continue;
            // Cell offset along ray direction → inside the obstacle
            const offset = this.cellSize * 0.6;
            const insideX = hit.point.x + (hit.dir ? hit.dir.x : 0) * offset;
            const insideZ = hit.point.z + (hit.dir ? hit.dir.z : 0) * offset;
            const cellX = Math.floor((insideX - this.gridMinX) / this.cellSize);
            const cellZ = Math.floor((insideZ - this.gridMinZ) / this.cellSize);
            if (!this.inBounds(cellX, cellZ)) continue;
            // Suppress wall mark if THIS cell or any immediate neighbor
            // has a known walkable surface at or above the hit Y. The
            // neighbor check matters because the wall hit's cell is
            // computed from an offset push along the ray; the actual
            // walkable platform top might be observed by a floor ray in
            // an adjacent cell. If a neighbor has an observed top at or
            // above this hit Y, this hit is the SIDE of a walkable
            // surface, not a real wall.
            let suppressed = false;
            for (let nz = -1; nz <= 1 && !suppressed; nz++) {
                for (let nx = -1; nx <= 1 && !suppressed; nx++) {
                    const ncx = cellX + nx, ncz = cellZ + nz;
                    if (!this.inBounds(ncx, ncz)) continue;
                    const known = this.surfaceY[this._idx(ncx, ncz)];
                    if (!isNaN(known) && known >= hy - 0.05) suppressed = true;
                }
            }
            if (suppressed) continue;
            this.observeCell(cellX, cellZ, STATE_BLOCKED, hy);
        }
    }

    /**
     * Read the recorded blocking height at a cell, or NaN if no wall
     * observation has been made there. Used by the planner's vertical-
     * column dilation check.
     */
    getCellBlockingY(cx, cz) {
        if (!this.inBounds(cx, cz)) return NaN;
        return this.blockingY[this._idx(cx, cz)];
    }

    /**
     * DDA-walk a 2D line from (x0,z0) to (x1,z1) for a floor-grazing ray.
     * All cells along the way are marked FREE without a surfaceY update
     * (we don't know the floor height under the ray's intermediate path —
     * could be flat, could be stepped, could be sloped). Only the ENDPOINT
     * cell gets surfaceY because that's where the ray actually contacted
     * the floor. Other rays at slightly different yaws will fill in the
     * traversal cells' surface heights from their own hit points.
     */
    _bresenhamApplyFree(x0, z0, x1, z1, surfaceYAtHit) {
        const adx = Math.abs(x1 - x0);
        const adz = Math.abs(z1 - z0);
        const sx = x0 < x1 ? 1 : -1;
        const sz = z0 < z1 ? 1 : -1;
        let err = adx - adz;
        let cx = x0, cz = z0;
        const maxSteps = adx + adz + 4;
        let steps = 0;
        while (steps++ < maxSteps) {
            const isLast = (cx === x1 && cz === z1);
            // Only the hit cell gets a surfaceY. Traversal cells become
            // FREE but their surfaceY stays NaN (or whatever was previously
            // recorded by another ray that DID directly hit their floor).
            this.observeCell(cx, cz, STATE_FREE, isLast ? surfaceYAtHit : undefined);
            if (isLast) break;
            const e2 = 2 * err;
            if (e2 > -adz) { err -= adz; cx += sx; }
            if (e2 < adx)  { err += adx; cz += sz; }
        }
    }

    /**
     * Mark a known-walkable footprint around a position. The body knows
     * it's standing on something walkable at its current Y, even if no
     * rays have hit there yet — call this from VRMRobotBody.update() with
     * the body's current position and a small radius.
     *
     * `y` is the body's standing Y; gets recorded as the surface height
     * for these cells so the planner has accurate ground for the start of
     * any path.
     */
    markStandingFootprint(x, z, radius, y) {
        const r = radius !== undefined ? radius : this.cellSize * 1.5;
        const minX = Math.max(0, Math.floor((x - r - this.gridMinX) / this.cellSize));
        const maxX = Math.min(this.cellsPerSide - 1, Math.floor((x + r - this.gridMinX) / this.cellSize));
        const minZ = Math.max(0, Math.floor((z - r - this.gridMinZ) / this.cellSize));
        const maxZ = Math.min(this.cellsPerSide - 1, Math.floor((z + r - this.gridMinZ) / this.cellSize));
        for (let cz = minZ; cz <= maxZ; cz++) {
            for (let cx = minX; cx <= maxX; cx++) {
                this.observeCell(cx, cz, STATE_FREE, y);
            }
        }
    }

    // ============================================================
    //  LANDMARKS
    // ============================================================

    tagLandmark(name, x, z, opts = {}) {
        this.landmarks.set(name, {
            name,
            x, z,
            type: opts.type || 'point',
            lastSeen: opts.lastSeen !== undefined ? opts.lastSeen : 0,
            metadata: opts.metadata || {},
        });
    }

    getLandmark(name) {
        return this.landmarks.get(name) || null;
    }

    forgetLandmark(name) {
        this.landmarks.delete(name);
    }

    listLandmarks() {
        return Array.from(this.landmarks.values());
    }

    // ============================================================
    //  STATS / QUERIES
    // ============================================================

    /**
     * Total area in m² that has any non-unknown observation.
     */
    getExploredArea() {
        let count = 0;
        for (let i = 0; i < this.cells.length; i++) {
            if ((this.cells[i] & 0x0F) !== STATE_UNKNOWN) count++;
        }
        return count * this.cellSize * this.cellSize;
    }

    /**
     * Returns an array of {cx, cz, state} for all non-unknown cells.
     * Useful for debug rendering.
     */
    getKnownCells() {
        const out = [];
        for (let cz = 0; cz < this.cellsPerSide; cz++) {
            for (let cx = 0; cx < this.cellsPerSide; cx++) {
                const s = this.cells[this._idx(cx, cz)] & 0x0F;
                if (s !== STATE_UNKNOWN) out.push({ cx, cz, state: s });
            }
        }
        return out;
    }

    // ============================================================
    //  SERIALIZATION
    // ============================================================

    serialize() {
        // Encode surfaceY by converting Float32 → byte buffer → base64.
        const surfBuf = new Uint8Array(this.surfaceY.buffer);
        return {
            size: this.size,
            cellSize: this.cellSize,
            originX: this.originX,
            originZ: this.originZ,
            cliffThreshold: this.cliffThreshold,
            stepUpTolerance: this.stepUpTolerance,
            cellsB64: btoa(String.fromCharCode(...this.cells)),
            surfaceB64: btoa(String.fromCharCode(...surfBuf)),
            landmarks: Array.from(this.landmarks.values()),
            observationCount: this.observationCount,
        };
    }

    static deserialize(blob) {
        const m = new RobotMemory({
            size: blob.size,
            cellSize: blob.cellSize,
            originX: blob.originX,
            originZ: blob.originZ,
            cliffThreshold: blob.cliffThreshold,
            stepUpTolerance: blob.stepUpTolerance,
        });
        const bin = atob(blob.cellsB64);
        for (let i = 0; i < bin.length; i++) m.cells[i] = bin.charCodeAt(i);
        if (blob.surfaceB64) {
            const surfBin = atob(blob.surfaceB64);
            const buf = new Uint8Array(surfBin.length);
            for (let i = 0; i < surfBin.length; i++) buf[i] = surfBin.charCodeAt(i);
            const f32 = new Float32Array(buf.buffer);
            for (let i = 0; i < f32.length; i++) m.surfaceY[i] = f32[i];
        }
        for (const l of blob.landmarks || []) m.landmarks.set(l.name, l);
        m.observationCount = blob.observationCount || 0;
        return m;
    }
}

// State constants for external use
RobotMemory.STATE_UNKNOWN = STATE_UNKNOWN;
RobotMemory.STATE_FREE    = STATE_FREE;
RobotMemory.STATE_BLOCKED = STATE_BLOCKED;
RobotMemory.STATE_CLIFF   = STATE_CLIFF;
RobotMemory.STATE_HAZARD  = STATE_HAZARD;

if (typeof window !== 'undefined') window.RobotMemory = RobotMemory;
