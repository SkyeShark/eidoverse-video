/**
 * RobotPlanner — A* path planner over a RobotMemory occupancy grid.
 *
 * Stateless: each call to findPath() runs a fresh A* against the memory
 * snapshot. The planner is the only thing in the VRMRobotBody stack that
 * walks the grid in bulk — sensors fill it, planner reads it.
 *
 * Features:
 *   - 8-connectivity (cardinal + diagonal). Diagonals cost √2.
 *   - Octile-distance heuristic.
 *   - Diagonal corner-cutting prevention (can't slip between two blocked
 *     cells that share a corner).
 *   - Agent-radius dilation (treats a cell as blocked if any cell within
 *     `radiusCells` is blocked, so paths stay an agent's body away from
 *     walls).
 *   - Optimistic unknown handling (default ON): unmapped cells are
 *     considered walkable. The body strides confidently into the unknown
 *     and replans when sensors reveal an obstacle.
 *   - Line-of-sight path smoothing: the raw cell-by-cell A* path is
 *     post-processed into a small list of waypoints with straight
 *     segments between them.
 *
 * Usage:
 *   const planner = new RobotPlanner({ agentRadius: 0.35, optimistic: true });
 *   const path = planner.findPath(memory, fromX, fromZ, toX, toZ);
 *   // path: [{x, z}, ...] starting at the cell containing (fromX,fromZ)
 *   //       and ending at the cell containing (toX,toZ), or null if
 *   //       unreachable.
 *
 *   const blocked = planner.isPathBlocked(memory, path);
 *   // bool — true if any waypoint along path is now blocked. Use this
 *   //        from VRMRobotBody.update() to trigger replans.
 */

class RobotPlanner {
    constructor(opts = {}) {
        this.agentRadius = opts.agentRadius !== undefined ? opts.agentRadius : 0.35;
        this.optimistic = opts.optimistic !== undefined ? opts.optimistic : true;
        // How aggressively to penalize unknown cells vs free cells. >1 makes
        // the planner prefer mapped corridors when one exists. 1 = treat
        // unknown the same as free.
        this.unknownPenalty = opts.unknownPenalty !== undefined ? opts.unknownPenalty : 1.4;
        // 2.5D: how big a vertical step the body can climb in a single
        // cell-to-cell transition (stair tread default 0.4 m).
        this.maxStepHeight = opts.maxStepHeight !== undefined ? opts.maxStepHeight : 0.4;
        // Cell dilation around BLOCKED cells. Default 1 cell (so the
        // agent's body doesn't clip through wall edges). Dilation is
        // height-aware: a wall only blocks the candidate cell if its
        // recorded blocking Y intersects the body's vertical column at
        // the candidate cell's surface height. Stair geometry doesn't
        // generate BLOCKED records (step risers are ignored at sense
        // time) so dilation never affects stair-climbing.
        this.dilationCells = opts.dilationCells !== undefined ? opts.dilationCells : 1;
        // Body height — used by the dilation check to compute the agent's
        // vertical column at each candidate cell.
        this.agentHeight = opts.agentHeight !== undefined ? opts.agentHeight : 1.7;
        // Max search expansions before giving up — protects against
        // pathological grids
        this.maxExpansions = opts.maxExpansions !== undefined ? opts.maxExpansions : 50000;
    }

    // ============================================================
    //  WALKABILITY (with agent radius dilation)
    // ============================================================

    /**
     * Returns true if the agent's bounding circle can occupy this cell —
     * height-aware BLOCKED-state dilation only. A cell is rejected if any
     * BLOCKED neighbor within the agent's body radius has a wall that
     * actually intersects the body's vertical column at this candidate's
     * surface height. The dilation distance is `agentRadius` regardless
     * of `radiusCells`; the latter is kept for backward compatibility.
     *
     * Stairs are NOT marked BLOCKED (their fronts are step risers within
     * stepUp, which pass 2 ignores), so this dilation never triggers on
     * stair-front cells. Real walls ARE marked BLOCKED with blockingY,
     * so they correctly dilate the surrounding cells when the wall is
     * within the body's column at those cells.
     */
    _isWalkable(memory, cx, cz, radiusCells, fromCx, fromCz) {
        if (!memory.inBounds(cx, cz)) return false;
        const STATE_BLOCKED = RobotMemory.STATE_BLOCKED;
        const STATE_CLIFF   = RobotMemory.STATE_CLIFF;
        const STATE_HAZARD  = RobotMemory.STATE_HAZARD;
        const STATE_UNKNOWN = RobotMemory.STATE_UNKNOWN;
        const selfState = memory.getCellState(cx, cz);
        if (selfState === STATE_BLOCKED || selfState === STATE_CLIFF || selfState === STATE_HAZARD) return false;
        if (!this.optimistic && selfState === STATE_UNKNOWN) return false;

        // Body's standing Y at this candidate cell
        const candSurfY = memory.getCellSurfaceY(cx, cz);
        let bodyFloor = candSurfY;
        if (isNaN(bodyFloor) && fromCx !== undefined) {
            bodyFloor = memory.getCellSurfaceY(fromCx, fromCz);
        }
        if (isNaN(bodyFloor)) bodyFloor = 0;
        const bodyCeil = bodyFloor + this.agentHeight;

        // Search ALL cells within agentRadius of the candidate (not just
        // 1 cell). The body extends `agentRadius` from the cell center;
        // any BLOCKED cell within that disk could be a wall the body
        // clips into.
        const bodyRadiusCells = Math.max(radiusCells, Math.ceil(this.agentRadius / memory.cellSize));

        for (let dz = -bodyRadiusCells; dz <= bodyRadiusCells; dz++) {
            for (let dx = -bodyRadiusCells; dx <= bodyRadiusCells; dx++) {
                if (dx === 0 && dz === 0) continue;
                // Circular distance check
                const distMeters = Math.sqrt(dx * dx + dz * dz) * memory.cellSize;
                if (distMeters > this.agentRadius) continue;
                const nx = cx + dx, nz = cz + dz;
                if (!memory.inBounds(nx, nz)) continue;
                const s = memory.getCellState(nx, nz);
                if (s !== STATE_BLOCKED && s !== STATE_CLIFF && s !== STATE_HAZARD) continue;
                if (s === STATE_BLOCKED) {
                    // Height-aware: only count walls whose recorded
                    // blocking Y intersects the body's column at this
                    // candidate. Walls below the candidate's floor or
                    // above its head don't block.
                    const wallY = memory.getCellBlockingY(nx, nz);
                    if (!isNaN(wallY) && (wallY < bodyFloor + 0.05 || wallY > bodyCeil)) {
                        continue;
                    }
                }
                return false;
            }
        }

        // 2.5D slope check on transitions
        if (fromCx !== undefined && fromCz !== undefined) {
            const yFrom = memory.getCellSurfaceY(fromCx, fromCz);
            const yTo = memory.getCellSurfaceY(cx, cz);
            if (!isNaN(yFrom) && !isNaN(yTo)) {
                if (Math.abs(yTo - yFrom) > this.maxStepHeight) return false;
            }
        }
        return true;
    }

    _cellCost(memory, cx, cz) {
        const s = memory.getCellState(cx, cz);
        if (s === RobotMemory.STATE_UNKNOWN) return this.unknownPenalty;
        return 1.0;
    }

    // ============================================================
    //  A*
    // ============================================================

    findPath(memory, fromX, fromZ, toX, toZ) {
        // Dilation: how many cells of clearance the agent's body needs.
        // Set to 0 by default — the controller's physical collision system
        // handles actual body penetration. Dilation in the planner just
        // makes tight corridors and stair-platform junctions unwalkable
        // (adjacent steps are 1 cell apart, any dilation > 0 deadlocks).
        // Increase via planner.dilationCells if you need wider clearance
        // (e.g. for outdoor open-space scenes with sparse obstacles).
        const radiusCells = this.dilationCells !== undefined
            ? this.dilationCells
            : 0;
        const startCell = memory.worldToCell(fromX, fromZ);
        const goalCell = memory.worldToCell(toX, toZ);
        if (!startCell || !goalCell) return null;

        // Allow start cell to be "currently blocked" by the agent's own
        // dilation footprint — the agent IS at that cell, so it's
        // tautologically reachable. Just check the goal can be approached.
        if (!this._isWalkable(memory, goalCell.cx, goalCell.cz, radiusCells)) {
            // Try snapping the goal to the nearest walkable cell within a
            // small search radius. Often the LLM gives a goal that lands on
            // a wall or just inside one — bring it back into walkable space.
            const snapped = this._snapToNearestWalkable(memory, goalCell.cx, goalCell.cz, radiusCells, 6);
            if (!snapped) return null;
            goalCell.cx = snapped.cx;
            goalCell.cz = snapped.cz;
        }

        const N = memory.cellsPerSide;
        const total = N * N;
        const idx = (cx, cz) => cz * N + cx;

        const gScore = new Float32Array(total).fill(Infinity);
        const fScore = new Float32Array(total).fill(Infinity);
        const cameFrom = new Int32Array(total).fill(-1);
        const closed = new Uint8Array(total);

        const startIdx = idx(startCell.cx, startCell.cz);
        const goalIdx = idx(goalCell.cx, goalCell.cz);

        gScore[startIdx] = 0;
        fScore[startIdx] = this._heuristic(startCell.cx, startCell.cz, goalCell.cx, goalCell.cz);

        // Min-heap of indices keyed by fScore
        const heap = new MinHeap((a, b) => fScore[a] - fScore[b]);
        heap.push(startIdx);

        const NEIGHBORS = [
            [ 1, 0, 1.0], [-1, 0, 1.0], [0, 1, 1.0], [0, -1, 1.0],
            [ 1, 1, Math.SQRT2], [ 1, -1, Math.SQRT2], [-1, 1, Math.SQRT2], [-1, -1, Math.SQRT2],
        ];

        let expansions = 0;
        while (heap.size() > 0) {
            if (++expansions > this.maxExpansions) {
                console.warn('[RobotPlanner] max expansions exceeded — giving up');
                return null;
            }
            const cur = heap.pop();
            if (closed[cur]) continue;
            closed[cur] = 1;
            if (cur === goalIdx) {
                return this._reconstruct(cameFrom, cur, N, memory, radiusCells);
            }
            const cx = cur % N;
            const cz = (cur - cx) / N;
            for (const [dx, dz, baseCost] of NEIGHBORS) {
                const nx = cx + dx, nz = cz + dz;
                if (!memory.inBounds(nx, nz)) continue;
                // Pass from-cell for slope check on this transition
                if (!this._isWalkable(memory, nx, nz, radiusCells, cx, cz)) continue;
                // Diagonal corner cutting: forbid moving (cx,cz)→(nx,nz) if
                // either of the orthogonal neighbors is blocked
                if (dx !== 0 && dz !== 0) {
                    if (!this._isWalkable(memory, cx + dx, cz, radiusCells, cx, cz)) continue;
                    if (!this._isWalkable(memory, cx, cz + dz, radiusCells, cx, cz)) continue;
                }
                const nIdx = idx(nx, nz);
                if (closed[nIdx]) continue;
                const stepCost = baseCost * this._cellCost(memory, nx, nz);
                const tentative = gScore[cur] + stepCost;
                if (tentative < gScore[nIdx]) {
                    cameFrom[nIdx] = cur;
                    gScore[nIdx] = tentative;
                    fScore[nIdx] = tentative + this._heuristic(nx, nz, goalCell.cx, goalCell.cz);
                    heap.push(nIdx);
                }
            }
        }
        return null;  // unreachable
    }

    _heuristic(x0, z0, x1, z1) {
        const dx = Math.abs(x1 - x0);
        const dz = Math.abs(z1 - z0);
        // Octile distance
        return (dx + dz) + (Math.SQRT2 - 2) * Math.min(dx, dz);
    }

    _reconstruct(cameFrom, endIdx, N, memory, radiusCells) {
        const cells = [];
        let cur = endIdx;
        while (cur !== -1) {
            const cx = cur % N;
            const cz = (cur - cx) / N;
            cells.push({ cx, cz });
            cur = cameFrom[cur];
        }
        cells.reverse();
        // Convert to world points (with surface Y) and smooth
        const worldPath = cells.map(c => {
            const w = memory.cellToWorld(c.cx, c.cz);
            const sy = memory.getCellSurfaceY(c.cx, c.cz);
            return { x: w.x, z: w.z, y: sy };
        });
        return this._smoothPath(memory, worldPath, radiusCells);
    }

    /**
     * Line-of-sight smoothing — compress the raw cell path into a small
     * waypoint list. Walks the path and at each step skips ahead as far as
     * a straight line of walkable cells allows.
     */
    _smoothPath(memory, path, radiusCells) {
        if (path.length <= 2) return path;
        const out = [path[0]];
        let i = 0;
        while (i < path.length - 1) {
            let j = path.length - 1;
            // Find the furthest j such that the straight line from path[i]
            // to path[j] passes through only walkable cells.
            while (j > i + 1) {
                if (this._lineOfSight(memory, path[i], path[j], radiusCells)) break;
                j--;
            }
            out.push(path[j]);
            i = j;
        }
        return out;
    }

    /**
     * Bresenham-walk the line between two world points and confirm every
     * intermediate cell is walkable for an agent of `radiusCells`. Also
     * enforces the 2.5D slope constraint between consecutive cells along
     * the line, so a smoothed segment can't skip over a step bigger than
     * `maxStepHeight`.
     */
    _lineOfSight(memory, p0, p1, radiusCells) {
        const c0 = memory.worldToCell(p0.x, p0.z);
        const c1 = memory.worldToCell(p1.x, p1.z);
        if (!c0 || !c1) return false;
        let x0 = c0.cx, z0 = c0.cz;
        const x1 = c1.cx, z1 = c1.cz;
        const adx = Math.abs(x1 - x0);
        const adz = Math.abs(z1 - z0);
        const sx = x0 < x1 ? 1 : -1;
        const sz = z0 < z1 ? 1 : -1;
        let err = adx - adz;
        let safety = adx + adz + 4;
        let prevX = x0, prevZ = z0;
        let first = true;
        while (safety-- > 0) {
            // First cell check is "is this cell walkable in isolation"
            // (no transition); subsequent cells include slope check from
            // the previous step.
            if (first) {
                if (!this._isWalkable(memory, x0, z0, radiusCells)) return false;
                first = false;
            } else {
                if (!this._isWalkable(memory, x0, z0, radiusCells, prevX, prevZ)) return false;
            }
            if (x0 === x1 && z0 === z1) return true;
            prevX = x0; prevZ = z0;
            const e2 = 2 * err;
            if (e2 > -adz) { err -= adz; x0 += sx; }
            if (e2 <  adx) { err += adx; z0 += sz; }
        }
        return false;
    }

    /**
     * Spiral-search outward from (cx, cz) for the nearest walkable cell.
     * Used when the goal point lands on a wall or outside walkable space.
     */
    _snapToNearestWalkable(memory, cx, cz, radiusCells, maxDistCells) {
        for (let r = 1; r <= maxDistCells; r++) {
            for (let dz = -r; dz <= r; dz++) {
                for (let dx = -r; dx <= r; dx++) {
                    if (Math.max(Math.abs(dx), Math.abs(dz)) !== r) continue;
                    if (this._isWalkable(memory, cx + dx, cz + dz, radiusCells)) {
                        return { cx: cx + dx, cz: cz + dz };
                    }
                }
            }
        }
        return null;
    }

    /**
     * Check whether a previously-computed path is still valid against the
     * current memory state. Used to trigger replans when sensors reveal new
     * obstacles along the planned route.
     */
    isPathBlocked(memory, path) {
        if (!path || path.length < 2) return false;
        const radiusCells = this.dilationCells !== undefined ? this.dilationCells : 0;
        for (let i = 0; i < path.length - 1; i++) {
            if (!this._lineOfSight(memory, path[i], path[i + 1], radiusCells)) return true;
        }
        return false;
    }
}

// ============================================================
//  Tiny min-heap (for A* open set)
// ============================================================
class MinHeap {
    constructor(compare) {
        this.compare = compare;
        this.data = [];
    }
    size() { return this.data.length; }
    push(item) {
        this.data.push(item);
        this._bubbleUp(this.data.length - 1);
    }
    pop() {
        if (this.data.length === 0) return undefined;
        const top = this.data[0];
        const last = this.data.pop();
        if (this.data.length > 0) {
            this.data[0] = last;
            this._sinkDown(0);
        }
        return top;
    }
    _bubbleUp(i) {
        const item = this.data[i];
        while (i > 0) {
            const parent = (i - 1) >> 1;
            if (this.compare(item, this.data[parent]) < 0) {
                this.data[i] = this.data[parent];
                i = parent;
            } else break;
        }
        this.data[i] = item;
    }
    _sinkDown(i) {
        const n = this.data.length;
        const item = this.data[i];
        while (true) {
            let left = i * 2 + 1;
            let right = left + 1;
            let swap = -1;
            if (left < n && this.compare(this.data[left], item) < 0) swap = left;
            if (right < n && this.compare(this.data[right], swap === -1 ? item : this.data[swap]) < 0) swap = right;
            if (swap === -1) break;
            this.data[i] = this.data[swap];
            i = swap;
        }
        this.data[i] = item;
    }
}

if (typeof window !== 'undefined') {
    window.RobotPlanner = RobotPlanner;
    window.RobotPlannerHeap = MinHeap;
}
