/**
 * RobotDebug — visualization helpers for VRMRobotBody.
 *
 * Tooling for tuning + watching the robot's view of the world. None of
 * these are required for navigation to work — they're for debugging and
 * for cinematic "show what the AI sees" overlays in videos.
 *
 *   const dbg = new RobotDebug(body, scene);
 *   dbg.showRays(true);            // current sensor cone as line segments
 *   dbg.showMap(true);             // occupancy grid as a textured floor
 *   dbg.showPath(true);            // current planned path as a polyline
 *   dbg.showLandmarks(true);       // landmark markers
 *   // Then in renderFrame after body.update(): dbg.update();
 *
 *   // Toggle anything off:
 *   dbg.showRays(false);
 *
 * Each helper is a child of the scene, so anything you don't want to be
 * visible in the final render — turn off via showX(false). The map decal
 * sits at y=0.02 above the ground plane to avoid z-fighting.
 */

class RobotDebug {
    constructor(body, scene, opts = {}) {
        this.body = body;
        this.scene = scene;
        this.opts = opts;

        // Helpers — created lazily on first showX(true) call.
        this._raysHelper = null;
        this._mapHelper = null;
        this._mapTexture = null;
        this._mapData = null;
        this._pathHelper = null;
        this._landmarksHelper = null;

        this._enabled = {
            rays: false,
            map: false,
            path: false,
            landmarks: false,
        };

        // Map color palette (one RGBA per RobotMemory.STATE_*)
        this._stateColors = {
            0: [0, 0, 0, 0],          // unknown — transparent
            1: [40, 200, 80, 140],    // free — green
            2: [220, 40, 60, 220],    // blocked — red
            3: [220, 180, 0, 220],    // cliff — yellow
            4: [180, 60, 220, 220],   // hazard — purple
        };
    }

    // ============================================================
    //  TOGGLES
    // ============================================================

    showRays(on) {
        this._enabled.rays = !!on;
        if (on && !this._raysHelper) this._buildRaysHelper();
        if (this._raysHelper) this._raysHelper.visible = !!on;
    }

    showMap(on) {
        this._enabled.map = !!on;
        if (on && !this._mapHelper) this._buildMapHelper();
        if (this._mapHelper) this._mapHelper.visible = !!on;
    }

    showPath(on) {
        this._enabled.path = !!on;
        if (on && !this._pathHelper) this._buildPathHelper();
        if (this._pathHelper) this._pathHelper.visible = !!on;
    }

    showLandmarks(on) {
        this._enabled.landmarks = !!on;
        if (on && !this._landmarksHelper) this._buildLandmarksHelper();
        if (this._landmarksHelper) this._landmarksHelper.visible = !!on;
    }

    // ============================================================
    //  PER-FRAME UPDATE
    // ============================================================

    update() {
        if (this._enabled.rays) this._updateRays();
        if (this._enabled.map) this._updateMap();
        if (this._enabled.path) this._updatePath();
        if (this._enabled.landmarks) this._updateLandmarks();
    }

    // ============================================================
    //  RAYS — current sensor cone
    // ============================================================

    _buildRaysHelper() {
        const numRays = this.body.sensors.hRays * this.body.sensors.vRays;
        const positions = new Float32Array(numRays * 6);    // 2 verts per ray
        const colors = new Float32Array(numRays * 6);
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        const mat = new THREE.LineBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.6,
            depthWrite: false,
        });
        this._raysHelper = new THREE.LineSegments(geo, mat);
        this._raysHelper.frustumCulled = false;
        this._raysHelper.renderOrder = 999;
        this.scene.add(this._raysHelper);
    }

    _updateRays() {
        const reading = this.body.lastReading;
        if (!reading) return;
        const positions = this._raysHelper.geometry.attributes.position.array;
        const colors = this._raysHelper.geometry.attributes.color.array;
        const o = reading.origin;
        for (let i = 0; i < reading.hits.length; i++) {
            const h = reading.hits[i];
            const j = i * 6;
            positions[j + 0] = o.x;
            positions[j + 1] = o.y;
            positions[j + 2] = o.z;
            positions[j + 3] = h.point.x;
            positions[j + 4] = h.point.y;
            positions[j + 5] = h.point.z;
            // Hits = red, misses = cyan
            const r = h.hit ? 1.0 : 0.0;
            const g = h.hit ? 0.2 : 0.9;
            const b = h.hit ? 0.2 : 1.0;
            colors[j + 0] = r; colors[j + 1] = g; colors[j + 2] = b;
            colors[j + 3] = r; colors[j + 4] = g; colors[j + 5] = b;
        }
        this._raysHelper.geometry.attributes.position.needsUpdate = true;
        this._raysHelper.geometry.attributes.color.needsUpdate = true;
    }

    // ============================================================
    //  MAP — occupancy grid as a textured floor decal
    // ============================================================

    _buildMapHelper() {
        const m = this.body.memory;
        const N = m.cellsPerSide;
        const total = N * N;
        // Build a 2.5D mesh: each cell is a small quad floating at its
        // surfaceY (or 0.02 if surfaceY is unknown). One quad per cell;
        // colors are per-vertex so we can repaint without rebuilding.
        // 4 vertices + 2 triangles (6 indices) per cell.
        const positions = new Float32Array(total * 4 * 3);
        const colors = new Float32Array(total * 4 * 3);
        const alphas = new Float32Array(total * 4);
        const indices = new Uint32Array(total * 6);

        const half = m.cellSize * 0.49;  // tiny gap so adjacent cells visually separate
        for (let cz = 0; cz < N; cz++) {
            for (let cx = 0; cx < N; cx++) {
                const i = cz * N + cx;
                const w = m.cellToWorld(cx, cz);
                const v = i * 4;
                // 4 corners of the quad in XZ plane (Y will be set by _updateMap)
                positions[v*3 + 0] = w.x - half; positions[v*3 + 1] = 0; positions[v*3 + 2] = w.z - half;
                positions[(v+1)*3 + 0] = w.x + half; positions[(v+1)*3 + 1] = 0; positions[(v+1)*3 + 2] = w.z - half;
                positions[(v+2)*3 + 0] = w.x + half; positions[(v+2)*3 + 1] = 0; positions[(v+2)*3 + 2] = w.z + half;
                positions[(v+3)*3 + 0] = w.x - half; positions[(v+3)*3 + 1] = 0; positions[(v+3)*3 + 2] = w.z + half;
                // Two triangles per quad
                const idx = i * 6;
                indices[idx + 0] = v + 0;
                indices[idx + 1] = v + 1;
                indices[idx + 2] = v + 2;
                indices[idx + 3] = v + 0;
                indices[idx + 4] = v + 2;
                indices[idx + 5] = v + 3;
            }
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geo.setAttribute('alpha', new THREE.BufferAttribute(alphas, 1));
        geo.setIndex(new THREE.BufferAttribute(indices, 1));

        // Custom shader so we can use per-vertex alpha for the confidence
        // fade. (Standard MeshBasicMaterial vertexColors only handles RGB.)
        const mat = new THREE.ShaderMaterial({
            vertexShader: `
                attribute vec3 color;
                attribute float alpha;
                varying vec3 vColor;
                varying float vAlpha;
                void main() {
                    vColor = color;
                    vAlpha = alpha;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                varying vec3 vColor;
                varying float vAlpha;
                void main() {
                    if (vAlpha < 0.01) discard;
                    gl_FragColor = vec4(vColor, vAlpha);
                }
            `,
            transparent: true,
            depthWrite: false,
            side: THREE.DoubleSide,
        });

        const mesh = new THREE.Mesh(geo, mat);
        mesh.frustumCulled = false;
        mesh.renderOrder = 998;
        this._mapHelper = mesh;
        this._mapPositions = positions;
        this._mapColors = colors;
        this._mapAlphas = alphas;
        this.scene.add(mesh);
    }

    _updateMap() {
        const m = this.body.memory;
        if (m.observationCount === this._lastObsCount) return;
        this._lastObsCount = m.observationCount;
        const N = m.cellsPerSide;
        const positions = this._mapPositions;
        const colors = this._mapColors;
        const alphas = this._mapAlphas;
        const colorTable = this._stateColors;
        const cells = m.cells;
        const surfaceY = m.surfaceY;
        for (let i = 0; i < cells.length; i++) {
            const cell = cells[i];
            const state = cell & 0x0F;
            const conf = (cell >> 4) & 0x0F;
            const c = colorTable[state] || colorTable[0];
            const v = i * 4;
            // Y for the four corners of this cell. Use the cell's
            // surfaceY if known; otherwise sit at 0.02 above ground.
            const sy = surfaceY[i];
            const cellY = isNaN(sy) ? 0.02 : (sy + 0.02);
            positions[v*3 + 1] = cellY;
            positions[(v+1)*3 + 1] = cellY;
            positions[(v+2)*3 + 1] = cellY;
            positions[(v+3)*3 + 1] = cellY;

            // Per-corner color (same color for all 4 corners of one cell)
            const r = c[0] / 255, g = c[1] / 255, b = c[2] / 255;
            colors[v*3 + 0] = r; colors[v*3 + 1] = g; colors[v*3 + 2] = b;
            colors[(v+1)*3 + 0] = r; colors[(v+1)*3 + 1] = g; colors[(v+1)*3 + 2] = b;
            colors[(v+2)*3 + 0] = r; colors[(v+2)*3 + 1] = g; colors[(v+2)*3 + 2] = b;
            colors[(v+3)*3 + 0] = r; colors[(v+3)*3 + 1] = g; colors[(v+3)*3 + 2] = b;

            // Alpha (confidence-faded, 0 for unknown so the cell vanishes)
            const alpha = state === 0 ? 0 : (c[3] / 255) * Math.min(1, (conf + 1) / 8);
            alphas[v + 0] = alpha;
            alphas[v + 1] = alpha;
            alphas[v + 2] = alpha;
            alphas[v + 3] = alpha;
        }
        this._mapHelper.geometry.attributes.position.needsUpdate = true;
        this._mapHelper.geometry.attributes.color.needsUpdate = true;
        this._mapHelper.geometry.attributes.alpha.needsUpdate = true;
    }

    // ============================================================
    //  PATH — current planned path
    // ============================================================

    _buildPathHelper() {
        const positions = new Float32Array(2048 * 3);     // up to 2048 points
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setDrawRange(0, 0);
        const mat = new THREE.LineBasicMaterial({
            color: 0xffff00,
            transparent: true,
            opacity: 0.85,
            depthWrite: false,
        });
        const line = new THREE.Line(geo, mat);
        line.frustumCulled = false;
        line.renderOrder = 1000;
        this._pathHelper = line;
        this.scene.add(line);
    }

    _updatePath() {
        const path = this.body._currentPath;
        const positions = this._pathHelper.geometry.attributes.position.array;
        if (!path || path.length < 2) {
            this._pathHelper.geometry.setDrawRange(0, 0);
            return;
        }
        const n = Math.min(path.length, 2048);
        for (let i = 0; i < n; i++) {
            positions[i * 3 + 0] = path[i].x;
            positions[i * 3 + 1] = 0.05;
            positions[i * 3 + 2] = path[i].z;
        }
        this._pathHelper.geometry.attributes.position.needsUpdate = true;
        this._pathHelper.geometry.setDrawRange(0, n);
    }

    // ============================================================
    //  LANDMARKS — small markers
    // ============================================================

    _buildLandmarksHelper() {
        // Lazily build a group; markers added on update
        this._landmarksHelper = new THREE.Group();
        this._landmarkInstances = new Map();
        this.scene.add(this._landmarksHelper);
    }

    _updateLandmarks() {
        const seen = new Set();
        for (const lm of this.body.memory.listLandmarks()) {
            seen.add(lm.name);
            let inst = this._landmarkInstances.get(lm.name);
            if (!inst) {
                const geo = new THREE.SphereGeometry(0.15, 8, 8);
                const mat = new THREE.MeshBasicMaterial({ color: 0x00ddff, transparent: true, opacity: 0.9 });
                inst = new THREE.Mesh(geo, mat);
                inst.renderOrder = 1001;
                this._landmarksHelper.add(inst);
                this._landmarkInstances.set(lm.name, inst);
            }
            inst.position.set(lm.x, 0.5, lm.z);
        }
        // Remove instances for landmarks that no longer exist
        for (const [name, inst] of this._landmarkInstances) {
            if (!seen.has(name)) {
                this._landmarksHelper.remove(inst);
                inst.geometry.dispose();
                inst.material.dispose();
                this._landmarkInstances.delete(name);
            }
        }
    }
}

if (typeof window !== 'undefined') window.RobotDebug = RobotDebug;
