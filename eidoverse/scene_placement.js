// scene_placement.js
//
// Intent-based scene composition primitives for the eidoverse pipeline.
// Raycast-driven where it matters (snap onto a surface, ground-snap,
// surface-normal alignment), bbox-aware where bboxes suffice (clearance,
// pairwise clipping audit).
//
// The earlier `placeRelativeTo(obj, ref, side, gap)` helper treated obj
// as a POINT — it placed obj.position at ref's edge minus the gap,
// without accounting for obj's own bounding box. Result: every model
// whose origin sits inside (or behind) its mesh got half-embedded into
// whatever it was placed against. These helpers replace it with primitives
// that account for both objects' actual geometry.
//
// CAVEAT (WebGPU + TSL): vertex deformation done in a TSL `positionNode`
// happens in the vertex shader at render time. `Box3.setFromObject` walks
// the CPU-side `geometry.attributes.position`, which is the *un-deformed*
// mesh. If a mesh has a TSL `positionNode` that warps it (extrude / twist /
// vertex noise), the bbox seen here is the un-deformed extent. Opt-in
// override: set `mesh.geometry.boundingBox = new THREE.Box3(...)` to the
// real deformed extent before using these helpers. This module honors a
// pre-set `geometry.boundingBox` and skips vertex iteration when present.
//
// Install pattern (wired up by `render_scene.mjs`):
//   installScenePlacement(THREE);
//   // → exposes globalThis.placeOn, placeAgainst, placeTouching, snapToGround,
//   //   alignToSurface, scatterOn, findClearSpot, checkClipping (now also
//   //   reports mesh-accurate DEEP interpenetration), placeInside,
//   //   placeRelativeTo (deprecated alias for placeAgainst).

export function installScenePlacement(THREE) {
    const _ray = new THREE.Raycaster();
    _ray.firstHitOnly = true;
    const _down = new THREE.Vector3(0, -1, 0);
    const _up = new THREE.Vector3(0, 1, 0);
    const _tmpVec = new THREE.Vector3();
    const _tmpBox = new THREE.Box3();

    // ───────── internal helpers ─────────

    // Collect every visible Mesh under `root` that should participate in
    // raycast / bbox math. Skips Lights, Cameras, helpers, invisible nodes,
    // VRM secondary chains (hair physics — bind-pose bboxes are wildly off),
    // and anything opted out via `userData.noClippingCheck = true`.
    function collectMeshes(root, exclude = []) {
        const out = [];
        const excludeSet = new Set(exclude);
        // NOTE: manual recursion, NOT root.traverse() — traverse() visits
        // children even when the callback bails, so `noClippingCheck` on a
        // GROUP (how robotics_kit exempts whole machines) silently failed to
        // exempt any of its child meshes and the auto-separator shoved
        // "exempt" robots around. Early-return here prunes the SUBTREE.
        (function walk(o) {
            if (!o.visible) return;
            if (excludeSet.has(o)) return;
            if (o.userData && o.userData.noClippingCheck) return;
            if (/^(secondary|hair|Hair)$/i.test(o.name)) return;
            if (o.isLight || o.isCamera) return;
            if (o.isMesh) out.push(o);
            for (const c of o.children) walk(c);
        })(root);
        return out;
    }

    // Compute a tight bbox of an object's visible mesh descendants.
    // Honors mesh.geometry.boundingBox if pre-set (the TSL-deformation
    // opt-in). Falls back to a plain `setFromObject` if no meshes survive
    // the filter (e.g. lights-only group).
    function tightBox(obj) {
        // updateWorldMatrix(parents, children) — updateMatrixWorld(true) alone
        // leaves STALE ancestor/sibling matrixWorlds, and the cached
        // geometry.boundingBox fast-path below then measures the object at its
        // LOCAL coordinates (the audit-sees-the-table-at-origin bug).
        obj.updateWorldMatrix(true, true);
        const box = new THREE.Box3();
        const meshes = collectMeshes(obj);
        for (const m of meshes) {
            if (m.geometry.boundingBox) {
                _tmpBox.copy(m.geometry.boundingBox).applyMatrix4(m.matrixWorld);
            } else {
                _tmpBox.setFromObject(m);
            }
            box.union(_tmpBox);
        }
        if (box.isEmpty()) box.setFromObject(obj);
        return box;
    }

    // Cast a downward ray at (x, ySky, z) against every Mesh descendant of
    // `targets`. Returns the first hit (THREE.Intersection) or null.
    function rayDownTo(targets, x, z, ySky = 10000) {
        const list = Array.isArray(targets) ? targets : [targets];
        const meshes = [];
        for (const t of list) for (const m of collectMeshes(t)) meshes.push(m);
        if (!meshes.length) return null;
        _ray.set(new THREE.Vector3(x, ySky, z), _down);
        const hits = _ray.intersectObjects(meshes, false);
        return hits.length ? hits[0] : null;
    }

    // Sample the supporting surface height across an object's FOOTPRINT,
    // not at a single point. Casts an n×n grid of downward rays spanning the
    // object's bbox xz extent (centered at cx,cz) against `meshes`, starting
    // from `startY`, and returns the HIGHEST hit Y found (so the object rests
    // ON the highest contact under it — no corner sinks into a lip/slope/board).
    // A single center ray (the old behavior) is the n=1 degenerate case and
    // misses lips, gaps, and uneven tops. This is the cheap, BVH-free analogue
    // of a box shapecast — fine because placement runs once in setup(), not
    // per frame. Returns { y, hits } or null if nothing under the footprint.
    function supportYUnderFootprint(obj, meshes, cx, cz, startY, grid = 3) {
        const oBox = tightBox(obj);
        const hx = (oBox.max.x - oBox.min.x) / 2;
        const hz = (oBox.max.z - oBox.min.z) / 2;
        const n = Math.max(1, grid | 0);
        let best = null, count = 0;
        for (let i = 0; i < n; i++) {
            for (let j = 0; j < n; j++) {
                const fx = n === 1 ? cx : cx - hx + (2 * hx) * (i / (n - 1));
                const fz = n === 1 ? cz : cz - hz + (2 * hz) * (j / (n - 1));
                _ray.set(new THREE.Vector3(fx, startY, fz), _down);
                const hits = _ray.intersectObjects(meshes, false);
                if (hits.length) {
                    count++;
                    if (best === null || hits[0].point.y > best) best = hits[0].point.y;
                }
            }
        }
        return best === null ? null : { y: best, hits: count };
    }

    // True iff `a` is an ancestor of `b` in the scene graph.
    function isAncestor(a, b) {
        let cur = b;
        while (cur) { if (cur === a) return true; cur = cur.parent; }
        return false;
    }

    // ───────── 1. placeOn — sit obj's bbox-bottom on target's top surface ─────────
    // Raycasts straight down from above target at (x, z) and snaps obj's
    // bbox-bottom to the hit point. Handles models whose origin is at the
    // centroid, a corner, or anywhere else — obj.position is adjusted so
    // the visible bottom of the mesh rests on the surface.
    //
    // opts:
    //   xz: 'centered' (default) | 'random' | [x, z]
    //   yOffset: extra lift above the surface (meters; default 0)
    //   xzOffset: [dx, dz] nudge applied AFTER the xz anchor is chosen
    //     (meters). Use this to shift an object on its surface instead of
    //     writing obj.position.x/z yourself — a raw position write puts the
    //     model's arbitrary ORIGIN at that coordinate (not its visible
    //     centre) and silently un-does the bbox-centering below.
    //   grid: footprint sample resolution (default 3 → a 3×3 grid of rays
    //     across the object's base). Seats on the HIGHEST support found so no
    //     corner sinks into a lip/edge. Set 1 for a single center ray.
    globalThis.placeOn = (obj, target, opts = {}) => {
        // xz default is 'auto': if the object was ALREADY positioned (non-zero
        // XZ), keep that spot; otherwise center on the target. The old
        // unconditional 'centered' default silently DISCARDED hand-set
        // positions — every bare placeOn(obj, floor) piled props at the
        // floor's center (the "furniture blob"). 'centered' is still available
        // explicitly.
        const { xz = 'auto', yOffset = 0, xzOffset = null, grid = 3, surfaceEps = 0.0006 } = opts;
        const tBox = tightBox(target);
        let x, z;
        if (Array.isArray(xz)) {
            x = xz[0]; z = xz[1];
        } else if (xz === 'random') {
            x = tBox.min.x + Math.random() * (tBox.max.x - tBox.min.x);
            z = tBox.min.z + Math.random() * (tBox.max.z - tBox.min.z);
        } else if (xz === 'auto' && (Math.abs(obj.position.x) > 1e-6 || Math.abs(obj.position.z) > 1e-6)) {
            // keep the author's spot — anchor on the object's bbox center
            const ob0 = tightBox(obj);
            x = (ob0.min.x + ob0.max.x) / 2;
            z = (ob0.min.z + ob0.max.z) / 2;
        } else {
            x = (tBox.min.x + tBox.max.x) / 2;
            z = (tBox.min.z + tBox.max.z) / 2;
        }
        if (Array.isArray(xzOffset)) { x += xzOffset[0]; z += xzOffset[1]; }
        // Sample the target surface across the object's whole footprint (not a
        // single point) and seat on the highest support so nothing sinks in.
        const tMeshes = collectMeshes(target);
        const support = supportYUnderFootprint(obj, tMeshes, x, z, tBox.max.y + 100, grid);
        if (!support) { console.warn('[placeOn] no surface under footprint at', x, z); return false; }
        const oBox = tightBox(obj);
        // Center the object's BBOX (not its arbitrary loader origin) at (x, z),
        // the same way the Y axis seats the bbox-BOTTOM (not the origin) on the
        // surface. A GLB whose pivot is a corner or otherwise offset would
        // otherwise land shifted sideways — the "desk off to the side" bug.
        // placeAgainst already corrects for this on its axes; placeOn now does
        // too. NOTE: reads the post-rotation bbox, so set obj.rotation BEFORE
        // calling placeOn.
        const oCtr = oBox.getCenter(_tmpVec);
        const originToCtrX = obj.position.x - oCtr.x;
        const originToCtrZ = obj.position.z - oCtr.z;
        const objBottomToOriginY = obj.position.y - oBox.min.y;
        // surfaceEps (0.6mm) lifts the bbox-bottom a hair PROUD of the support
        // surface. A flat-bottomed object (desk/table/plinth/rug on a floor)
        // seated EXACTLY on the surface lands its base face coplanar with the
        // surface top — coplanar faces at identical depth are the #1 cause of
        // floor z-fighting (checkZFighting only catches THIN decals, not two
        // solids sharing a plane, so it can't fix this). Sub-mm, invisible;
        // pass surfaceEps:0 for exact mechanical contact.
        obj.position.set(x + originToCtrX, support.y + objBottomToOriginY + yOffset + surfaceEps, z + originToCtrZ);
        // sink: bury a fraction of the object's height INTO the surface.
        // Natural objects (rocks, boulders, ruins, stumps, bones) read as
        // "balanced on the ground" when their bbox sits flush — real ones are
        // partially buried. sink: 0.15-0.35 is the rock sweet spot.
        if (opts.sink) {
            const h = oBox.max.y - oBox.min.y;
            obj.position.y -= Math.min(0.9, Math.max(0, opts.sink)) * h;
            // a deliberate burial by the placement system itself — the hovering
            // audit must not "rescue" it back to flush (it did: 22 carefully
            // sunk rocks got snapped back onto the surface)
            obj.userData._sunkPlacement = true;
        }
        // Support-chain memory: record what this object was seated ON so the
        // placement audit verifies against THIS support instead of guessing
        // from global geometry (prevents checkHovering snapping a deliberate
        // prop-on-prop placement — books on a table — down to the floor).
        obj.userData._supportTarget = target;
        return true;
    };

    // ───────── 2. placeAgainst — clearance-aware side placement ─────────
    // Sits obj's bbox flush against ref's chosen side, with `gap` of real
    // visible clearance between the two bbox edges. Accounts for obj's
    // own origin offset (the bug `placeRelativeTo` had).
    //
    // side: 'front' | 'behind' | 'left' | 'right' | 'above' | 'below'
    // gap:  meters of clearance (default 0.3)
    globalThis.placeAgainst = (obj, ref, side, gap = 0.3) => {
        const rBox = tightBox(ref);
        const oBox = tightBox(obj);
        const rCtr = rBox.getCenter(new THREE.Vector3());
        const oCtr = oBox.getCenter(new THREE.Vector3());
        // delta from obj's bbox center to obj.position (handles odd origins).
        const dx = obj.position.x - oCtr.x;
        const dy = obj.position.y - oCtr.y;
        const dz = obj.position.z - oCtr.z;
        const hX = (oBox.max.x - oBox.min.x) / 2;
        const hY = (oBox.max.y - oBox.min.y) / 2;
        const hZ = (oBox.max.z - oBox.min.z) / 2;
        const keepY = obj.position.y;
        const keepX = obj.position.x;
        const keepZ = obj.position.z;
        switch (side) {
            case 'behind': obj.position.set(rCtr.x + dx, keepY, rBox.min.z - gap - hZ + dz); break;
            case 'front':  obj.position.set(rCtr.x + dx, keepY, rBox.max.z + gap + hZ + dz); break;
            case 'left':   obj.position.set(rBox.min.x - gap - hX + dx, keepY, rCtr.z + dz); break;
            case 'right':  obj.position.set(rBox.max.x + gap + hX + dx, keepY, rCtr.z + dz); break;
            case 'above':  obj.position.set(rCtr.x + dx, rBox.max.y + gap + hY + dy, rCtr.z + dz); break;
            case 'below':  obj.position.set(rCtr.x + dx, rBox.min.y - gap - hY + dy, rCtr.z + dz); break;
            default: console.warn(`[placeAgainst] unknown side "${side}" — use front/behind/left/right/above/below`);
        }
    };

    // ───────── 2.4 placeTouching — slide obj until its MESH contacts target's MESH ─────────
    // The mesh-accurate sibling of placeAgainst. placeAgainst seats obj's BBOX
    // against ref's BBOX — fast, but an odd origin or a concave leading face
    // leaves a visible gap (or an overlap). placeTouching raycasts obj's leading
    // face against the target's ACTUAL geometry and slides obj along one axis
    // until the two surfaces just KISS (optionally leaving `gap`). Opt-in, for
    // ANY piece-based build: kit parts (a kit is ONE gltf with the pieces laid
    // out spread apart — loadKit re-centers each, then you assemble), several
    // separate models, or your own procedural meshes. Make them actually touch
    // instead of floating apart or interpenetrating.
    //   side: which way obj TRAVELS toward the target —
    //         left(-x) / right(+x) / front(+z) / behind(-z) / above(+y) / below(-y)
    //   opts.dir:   explicit unit direction [x,y,z] (overrides side)
    //   opts.gap:   stop this far short of contact (default 0; negative = bite in)
    //   opts.grid:  ray-fan resolution across the leading face (default 4 → 4×4)
    //   opts.allowIntersect: also tag obj so the clipping audit skips it
    // Returns true on contact, false (and warns) if no target surface lies in
    // that direction — so you can fall back to placeAgainst / hand coords.
    globalThis.placeTouching = (obj, target, side, opts = {}) => {
        const { dir: dirOpt = null, gap = 0, grid = 4, allowIntersect = false } = opts;
        const SIDE_DIR = { left: [-1,0,0], right: [1,0,0], behind: [0,0,-1], front: [0,0,1], below: [0,-1,0], above: [0,1,0] };
        const d = dirOpt || SIDE_DIR[side];
        if (!d) { console.warn(`[placeTouching] need a side (left/right/front/behind/above/below) or opts.dir`); return false; }
        const dir = new THREE.Vector3(d[0], d[1], d[2]);
        if (dir.lengthSq() === 0) { console.warn('[placeTouching] zero direction'); return false; }
        dir.normalize();

        // target meshes (a mesh, a group, or an array of either)
        const tMeshes = [];
        const addMeshes = (o) => { if (o && o.traverse) o.traverse((m) => { if (m.isMesh && m.visible) tMeshes.push(m); }); };
        if (Array.isArray(target)) target.forEach(addMeshes); else addMeshes(target);
        if (!tMeshes.length) { console.warn('[placeTouching] target has no raycastable meshes'); return false; }

        obj.updateWorldMatrix(true, true);
        const oBox = tightBox(obj);
        // The leading face is obj's bbox face pointing along `dir`. Fan rays
        // across it (inner 80%, to avoid glancing the outer edges) and take the
        // NEAREST target hit — so obj stops at first contact and never buries in.
        const axis = Math.abs(dir.x) > 0.5 ? 'x' : (Math.abs(dir.y) > 0.5 ? 'y' : 'z');
        const lead = dir[axis] > 0 ? oBox.max[axis] : oBox.min[axis];
        const span = ['x', 'y', 'z'].filter((a) => a !== axis);
        const savedFar = _ray.far;
        _ray.far = Infinity;
        let minDist = Infinity;
        const N = Math.max(2, grid);
        const origin = new THREE.Vector3();
        for (let i = 0; i < N; i++) {
            for (let j = 0; j < N; j++) {
                const fi = 0.1 + 0.8 * (i / (N - 1)), fj = 0.1 + 0.8 * (j / (N - 1));
                origin[axis] = lead;
                origin[span[0]] = oBox.min[span[0]] + fi * (oBox.max[span[0]] - oBox.min[span[0]]);
                origin[span[1]] = oBox.min[span[1]] + fj * (oBox.max[span[1]] - oBox.min[span[1]]);
                _ray.set(origin, dir);
                const h = _ray.intersectObjects(tMeshes, false);
                if (h.length && h[0].distance < minDist) minDist = h[0].distance;
            }
        }
        _ray.far = savedFar;
        if (!isFinite(minDist)) {
            console.warn(`[placeTouching] no target surface in the '${side || 'dir'}' direction — obj not moved. Check the direction or starting positions, or use placeAgainst.`);
            return false;
        }
        obj.position.addScaledVector(dir, minDist - gap);
        obj.updateWorldMatrix(true, true);
        if (allowIntersect) obj.userData.allowIntersect = true;
        return true;
    };

    // ───────── 2.5 placeInside — rest obj on an INTERIOR surface of a container ─────────
    // The shelf-board pattern, packaged: centers obj's bbox on the container's
    // bbox in XZ, aims at `aimY` (world height of the compartment you want),
    // then snapToGround({below:true}) rests it on the actual board geometry
    // beneath. Yaw: pass matchYaw:true (default) to copy the container's
    // rotation.y so long props (book rows) run along the boards. READ the
    // model's *_preview.jpg first to pick aimY (board heights) sanely.
    globalThis.placeInside = (obj, container, opts = {}) => {
        const { aimY = null, matchYaw = true, xzOffset = null } = opts;
        if (matchYaw) obj.rotation.y = container.rotation.y;
        container.updateWorldMatrix(true, true);
        const cb = tightBox(container);
        const cc = cb.getCenter(new THREE.Vector3());
        const y = aimY === null ? (cb.min.y + cb.max.y) / 2 : aimY;
        obj.position.set(cc.x, y, cc.z);
        obj.updateWorldMatrix(true, true);
        const ob = tightBox(obj);
        const oc = ob.getCenter(new THREE.Vector3());
        obj.position.x += cc.x - oc.x;
        obj.position.z += cc.z - oc.z;
        if (Array.isArray(xzOffset)) { obj.position.x += xzOffset[0]; obj.position.z += xzOffset[1]; }
        const ok = globalThis.snapToGround(obj, container, { below: true });
        if (!ok) console.warn('[placeInside] no interior surface beneath aimY', y, '— check the preview image for board heights');
        return ok;
    };

    // ───────── 3. snapToGround — rest obj on whatever ground is below ─────────
    // Raycasts downward from obj's current xz against the supplied ground
    // meshes; sits obj's bbox-bottom on the hit. Use for characters on
    // stairs / slopes / terraced terrain, props on uneven floor, etc.
    //
    // groundMeshes: a single Mesh, an array of Meshes, or any Object3D whose
    //               descendants include the walkable surfaces.
    // opts.yOffset: extra lift above the hit (default 0; raise for hovering).
    // opts.below:  when true, cast from the object's CURRENT height (not from
    //              high above), so it lands on the nearest surface BENEATH where
    //              you put it — not the topmost surface. This is how you target
    //              an INTERIOR board of a shelf/cabinet: position the item just
    //              above the board you want, then snapToGround(item, [shelf],
    //              {below:true}). Default (false) casts from the sky → topmost
    //              surface, correct for characters/props on terrain.
    // opts.grid: footprint sample resolution. Defaults to 1 (single center
    //            ray — preserves the original character/terrain behavior) but
    //            3 in `below` mode so a book doesn't drop through a gap in a
    //            board. Raise for props with irregular bases on uneven ground.
    globalThis.snapToGround = (obj, groundMeshes, opts = {}) => {
        const { yOffset = 0, below = false, grid = (below ? 3 : 1), surfaceEps = 0.0006 } = opts;
        const list = Array.isArray(groundMeshes) ? groundMeshes : [groundMeshes];
        // Ground meshes placed in the SAME setup() haven't had a render tick
        // yet — their matrixWorld is still identity, so raycasts hit them at
        // their GEOMETRY-local position and the object "snaps" onto a phantom
        // level (crates lifted 0.25m onto an unmoved pad's local top).
        obj.updateWorldMatrix(true, true);
        for (const g of list) if (g && g.updateWorldMatrix) g.updateWorldMatrix(true, true);
        const meshes = [];
        for (const g of list) for (const m of collectMeshes(g)) meshes.push(m);
        if (!meshes.length) { console.warn('[snapToGround] no ground meshes provided'); return false; }
        const oBox = tightBox(obj);
        const x = obj.position.x;
        const z = obj.position.z;
        // below: start at the object's current bbox-bottom + a hair, so the hit
        // is the board directly under it (higher boards are above the ray origin
        // and never intersected). Otherwise start high → topmost surface.
        const startY = below
            ? oBox.min.y + 0.01
            : Math.max(oBox.max.y, obj.position.y) + 100;
        const support = supportYUnderFootprint(obj, meshes, x, z, startY, grid);
        if (!support) { console.warn('[snapToGround] no ground under footprint at', x, z, below ? '(below mode — is the item above a board?)' : ''); return false; }
        const objBottomToOriginY = obj.position.y - oBox.min.y;
        // surfaceEps (0.6mm): lift a hair proud of the ground so a flat base
        // doesn't land coplanar with the surface top → kills floor z-fighting.
        // Sub-mm, invisible; pass surfaceEps:0 for exact contact.
        obj.position.y = support.y + objBottomToOriginY + yOffset + surfaceEps;
        obj.userData._supportTarget = groundMeshes;
        return true;
    };

    // ───────── 4. alignToSurface — match obj's +Y to the surface normal ─────────
    // Casts a ray down from obj's position; if it hits `target`, rotates
    // obj so its local +Y aligns with the surface normal. Use for signs on
    // slanted roofs, props on slopes, anything that should sit flush on a
    // non-horizontal surface.
    globalThis.alignToSurface = (obj, target) => {
        const tBox = tightBox(target);
        const hit = rayDownTo(target, obj.position.x, obj.position.z, tBox.max.y + 100);
        if (!hit || !hit.face) { console.warn('[alignToSurface] no hit or no face normal'); return false; }
        const normal = hit.face.normal.clone().transformDirection(hit.object.matrixWorld).normalize();
        const q = new THREE.Quaternion().setFromUnitVectors(_up, normal);
        obj.quaternion.copy(q);
        return true;
    };

    // ───────── 5. scatterOn — spread N items across target's top surface ─────────
    // For each item, samples a random xz on target's footprint, snaps onto
    // the surface, and checks against already-placed items for minSpacing.
    // Uses a deterministic LCG keyed by rngSeed so the same seed produces
    // the same arrangement (re-renders are reproducible).
    //
    // opts:
    //   count: number to place (default = items.length)
    //   minSpacing: minimum world distance between item centers (default 0.1)
    //   rngSeed: integer seed for the LCG (default 1)
    //   maxAttempts: per-item retries to find a non-colliding spot (default 30)
    globalThis.scatterOn = (items, target, opts = {}) => {
        // sink: number | [min,max] — bury each item by that fraction of its
        // height (rocks/debris belong IN the ground, not balanced on it).
        // tiltMax: radians — random x/z lean per item (seeded, deterministic).
        const { count = items.length, minSpacing = 0.1, rngSeed = 1, maxAttempts = 30, sink = 0, tiltMax = 0 } = opts;
        let rng = rngSeed | 0 || 1;
        const random = () => {
            rng = (Math.imul(rng, 1103515245) + 12345) & 0x7fffffff;
            return rng / 0x7fffffff;
        };
        const tBox = tightBox(target);
        const placed = [];
        const pPos = new THREE.Vector3();
        const itemPos = new THREE.Vector3();
        for (let i = 0; i < count && i < items.length; i++) {
            const item = items[i];
            if (tiltMax > 0) {
                item.rotation.x += (random() * 2 - 1) * tiltMax;
                item.rotation.z += (random() * 2 - 1) * tiltMax;
            }
            const itemSink = Array.isArray(sink) ? sink[0] + random() * (sink[1] - sink[0]) : sink;
            let success = false;
            for (let attempt = 0; attempt < maxAttempts; attempt++) {
                const x = tBox.min.x + random() * (tBox.max.x - tBox.min.x);
                const z = tBox.min.z + random() * (tBox.max.z - tBox.min.z);
                if (!globalThis.placeOn(item, target, { xz: [x, z], sink: itemSink })) continue;
                item.getWorldPosition(itemPos);
                let collision = false;
                for (const p of placed) {
                    p.getWorldPosition(pPos);
                    if (itemPos.distanceTo(pPos) < minSpacing) { collision = true; break; }
                }
                if (!collision) { placed.push(item); success = true; break; }
            }
            if (!success) console.warn(`[scatterOn] couldn't fit item ${i} after ${maxAttempts} attempts`);
        }
        return placed;
    };

    // ───────── 6. findClearSpot — search for a position obj's bbox fits ─────────
    // Samples positions in a spiral around `around`; returns the first one
    // where obj's bbox doesn't intersect any other mesh in the scene
    // (excluding obj itself and anything in opts.exclude). Returns null if
    // no candidate is clear.
    //
    // opts:
    //   radius: search radius (default 2.0)
    //   samples: number of spiral candidates (default 16)
    //   scene: scene to test clipping against (default globalThis._s / _scene)
    //   exclude: objects to ignore (defaults to [obj])
    //   yOffset: y of the candidate (default obj's current y)
    globalThis.findClearSpot = (obj, around, opts = {}) => {
        const sceneRoot = opts.scene || globalThis._s || globalThis._scene;
        if (!sceneRoot) { console.warn('[findClearSpot] no scene — pass opts.scene or set globalThis._s'); return null; }
        const radius = opts.radius ?? 2.0;
        const samples = opts.samples ?? 16;
        const exclude = opts.exclude ?? [obj];
        const oBox = tightBox(obj);
        const size = oBox.getSize(new THREE.Vector3());
        const yC = opts.yOffset ?? around.y;
        const others = collectMeshes(sceneRoot, exclude);
        const otherBoxes = others.map((m) => new THREE.Box3().setFromObject(m));
        const testBox = new THREE.Box3();
        for (let i = 0; i < samples; i++) {
            const angle = (i / samples) * Math.PI * 2;
            const r = radius * (0.3 + 0.7 * (i / samples));
            const c = new THREE.Vector3(around.x + Math.cos(angle) * r, yC, around.z + Math.sin(angle) * r);
            testBox.setFromCenterAndSize(c.clone().add(new THREE.Vector3(0, size.y / 2, 0)), size);
            let clear = true;
            for (const ob of otherBoxes) { if (testBox.intersectsBox(ob)) { clear = false; break; } }
            if (clear) return c;
        }
        return null;
    };

    // ───────── 7. checkClipping — audit the scene for intersecting solids ─────────
    // Walks the scene, pairs every solid mesh, and flags pairs whose bboxes
    // overlap (excluding parent/child nesting, which is usually intentional —
    // a chair child of a desk group, parts of a kitbash kit). With autoFix,
    // pushes the lighter member of each intersecting pair along the
    // shortest-overlap axis until the overlap is resolved.
    //
    // Returns: [{ a, b }, ...] — list of intersecting pairs.
    //
    // opts:
    //   autoFix: push apart intersecting pairs (default false)
    //   exclude: meshes to skip
    //   maxFixIters: per-pair max iterations when auto-fixing (default 3)
    globalThis.checkClipping = (scene, opts = {}) => {
        const { autoFix = false, exclude = [], maxFixIters = 3 } = opts;
        if (!scene) { console.warn('[checkClipping] scene required'); return []; }
        const meshes = collectMeshes(scene, exclude);
        // Group meshes by their PLACED OBJECT — the top-level scene child
        // (descending through a single wrapper group). A multi-mesh model (a
        // desk's top + legs + drawers, a rigged arm's segments) has sub-meshes
        // that legitimately overlap; pushing those apart with autoFix RIPS the
        // model into pieces (the "exploded desk"). So we only resolve clipping
        // BETWEEN different placed objects, never within one.
        let _roots = scene.children.filter((c) => c !== globalThis._c && c !== globalThis._camera && !c.isLight && !c.isCamera);
        let _g = 0;
        while (_roots.length === 1 && !_roots[0].isMesh && _roots[0].children &&
               _roots[0].children.filter((c) => !c.isLight && !c.isCamera).length > 1 && _g++ < 4) {
            _roots = _roots[0].children.filter((c) => !c.isLight && !c.isCamera);
        }
        const _rootSet = new Set(_roots);
        const placedRootOf = (m) => { let o = m; while (o && !_rootSet.has(o)) o = o.parent; return o || m; };
        const entries = meshes.map((m) => ({ m, box: new THREE.Box3().setFromObject(m), root: placedRootOf(m) }));
        const report = [];
        let movedCount = 0;
        for (let i = 0; i < entries.length; i++) {
            for (let j = i + 1; j < entries.length; j++) {
                const a = entries[i], b = entries[j];
                if (a.root && a.root === b.root) continue;   // same placed object — never separate its own parts
                // A SEATED VRM legitimately overlaps its chair — don't push them apart.
                if (globalThis._seatedVRMs && (globalThis._seatedVRMs.has(a.root) || globalThis._seatedVRMs.has(b.root))) continue;
                // Support-chain memory (placeOn/snapToGround record what an object
                // was seated ON): resting contact is NOT clipping. Without this,
                // autoFix shoves a table off its floor and the books off the table
                // (minimal-axis push × maxFixIters → props teleported to the void),
                // and checkHovering then reports the wreckage it caused.
                const aSup = a.root && a.root.userData && a.root.userData._supportTarget;
                const bSup = b.root && b.root.userData && b.root.userData._supportTarget;
                if (aSup && (aSup === b.root || isAncestor(aSup, b.m) || isAncestor(b.m, aSup))) continue;
                if (bSup && (bSup === a.root || isAncestor(bSup, a.m) || isAncestor(a.m, bSup))) continue;
                if (isAncestor(a.m, b.m) || isAncestor(b.m, a.m)) continue;
                if (!a.box.intersectsBox(b.box)) continue;
                report.push({ a: a.m, b: b.m });
                if (autoFix) {
                    // Bbox INTERSECTION is proximity, not penetration: resting
                    // contact (book on table, arch on floor, figure beside desk)
                    // intersects by a few mm on one axis. Only auto-move for
                    // SUBSTANTIAL volumetric interpenetration; touches are
                    // report-only. (This was the prop-bulldozer: 121 'fixes'
                    // teleporting a correctly-placed table into the void.)
                    {
                        const tox = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
                        const toy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
                        const toz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
                        if (Math.min(tox, toy, toz) < 0.04) continue;   // touch/rest — not clipping
                    }
                    // Intentional overlap (half-buried rocks, a stake in the
                    // ground, a controller-driven character wading the set) —
                    // report-only, never auto-move.
                    const allow = (o) => o && o.userData && o.userData.allowIntersect;
                    if (allow(a.root) || allow(b.root) || allow(a.m) || allow(b.m)) continue;
                    // NEVER move ground-scale geometry (terrain, a floor slab
                    // spanning the set): "separating" the WORLD from one prop
                    // teleports the ground everything else stands on — the
                    // floating-terrain bug. If both are ground-scale, skip.
                    const spanOf = (e) => Math.max(e.box.max.x - e.box.min.x, e.box.max.z - e.box.min.z);
                    const aGround = spanOf(a) > 20, bGround = spanOf(b) > 20;
                    if (aGround && bGround) continue;
                    // Never move something that was deliberately seated
                    // (placeOn/snapToGround record). Prefer moving the unseated
                    // party; both seated → report only.
                    let mover = b.root || b.m;
                    const aSeated = a.root && a.root.userData && a.root.userData._supportTarget;
                    const bSeated = b.root && b.root.userData && b.root.userData._supportTarget;
                    if (aGround) mover = b.root || b.m;
                    else if (bGround) mover = a.root || a.m;
                    else if (bSeated && !aSeated) mover = a.root || a.m;
                    else if (bSeated && aSeated) continue;
                    movedCount++;
                    for (let k = 0; k < maxFixIters; k++) {
                        a.box.setFromObject(a.m);
                        b.box.setFromObject(b.m);
                        if (!a.box.intersectsBox(b.box)) break;
                        const ox = Math.min(a.box.max.x, b.box.max.x) - Math.max(a.box.min.x, b.box.min.x);
                        const oy = Math.min(a.box.max.y, b.box.max.y) - Math.max(a.box.min.y, b.box.min.y);
                        const oz = Math.min(a.box.max.z, b.box.max.z) - Math.max(a.box.min.z, b.box.min.z);
                        let axis = 'x', overlap = ox;
                        if (oy < overlap) { axis = 'y'; overlap = oy; }
                        if (oz < overlap) { axis = 'z'; overlap = oz; }
                        // direction from WORLD box centres (robust under nesting)
                        const dir = (b.box.min[axis] + b.box.max[axis]) > (a.box.min[axis] + a.box.max[axis]) ? 1 : -1;
                        mover.position[axis] += overlap * dir * 0.55;
                        mover.updateMatrixWorld(true);
                    }
                }
            }
        }
        if (report.length) {
            const verb = autoFix ? `separated ${movedCount} of` : 'detected';
            console.warn(`[checkClipping] ${verb} ${report.length} clipping pair(s):`);
            for (const p of report.slice(0, 10)) {
                const an = p.a.name || '(unnamed)', bn = p.b.name || '(unnamed)';
                console.warn(`  ${an} <=> ${bn}`);
            }
            if (report.length > 10) console.warn(`  ...and ${report.length - 10} more`);
        }

        // ── DEEP-INTERPENETRATION report (mesh-accurate, MOVES NOTHING) ──────
        // The AABB `report` above is mostly resting-contact + shared-floor NOISE
        // (a floor "clips" everything standing on it; props share a stage). The
        // one pair that actually matters — a whole object ENGULFED by another
        // (a tree inside the ruined car) — gets buried in "...and N more". This
        // second pass keeps ONLY genuine interpenetration and surfaces it loud,
        // named, and never truncated, so the agent can fix the xz. It is a
        // DETECTOR, not a fixer — it moves nothing (the autofix history: shoving
        // ground-seated props apart collapsed scenes onto one coordinate). The
        // agent repositions, or sets userData.allowIntersect = true (or the
        // existing noClippingCheck) on an object whose overlap is INTENTIONAL.
        // Method: of the SMALLER object's sampled surface points, what fraction
        // are ENCLOSED by the larger object's geometry — ≥5 of 6 axis rays from
        // the point hit the target. Robust for non-watertight shells (a car
        // body) where simple parity-counting fails. Same THREE.Raycaster as
        // seating; gated by a cheap AABB-overlap fraction so it only does the
        // raycast work on a handful of suspicious pairs, once, post-setup.
        try {
            const rootOf = new Map(entries.map((e) => [e.m, e.root]));
            const meshesOf = (root) => { const out = []; root.traverse((o) => { if (o.isMesh && o.visible) out.push(o); }); return out; };
            const boxVol = (b) => { const s = b.getSize(new THREE.Vector3()); return Math.max(1e-9, s.x * s.y * s.z); };
            const AX = [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]].map(([x,y,z]) => new THREE.Vector3(x, y, z));
            const savedFar = _ray.far;
            const seenPair = new Set();
            const deep = [];
            for (const p of report) {
                const ra = rootOf.get(p.a) || p.a, rb = rootOf.get(p.b) || p.b;
                if (ra === rb) continue;
                const key = ra.uuid < rb.uuid ? ra.uuid + rb.uuid : rb.uuid + ra.uuid;
                if (seenPair.has(key)) continue;
                seenPair.add(key);
                const optOut = (r) => r.userData && (r.userData.allowIntersect || r.userData.noClippingCheck);
                if (optOut(ra) || optOut(rb)) continue;
                const ba = new THREE.Box3().setFromObject(ra), bb = new THREE.Box3().setFromObject(rb);
                const ox = Math.min(ba.max.x, bb.max.x) - Math.max(ba.min.x, bb.min.x);
                const oy = Math.min(ba.max.y, bb.max.y) - Math.max(ba.min.y, bb.min.y);
                const oz = Math.min(ba.max.z, bb.max.z) - Math.max(ba.min.z, bb.min.z);
                if (ox <= 0 || oy <= 0 || oz <= 0) continue;
                const smallIsA = boxVol(ba) <= boxVol(bb);
                const small = smallIsA ? ra : rb, big = smallIsA ? rb : ra;
                const smallBox = smallIsA ? ba : bb, bigBox = smallIsA ? bb : ba;
                // cheap gate: the overlap must be a real fraction of the SMALLER
                // object's box (resting contact overlaps by mm → skipped).
                if ((ox * oy * oz) / boxVol(smallBox) < 0.12) continue;
                const smallMeshes = meshesOf(small), bigMeshes = meshesOf(big);
                if (!smallMeshes.length || !bigMeshes.length) continue;
                // sample the smaller object's surface points that fall inside big's bbox
                const pts = [];
                const cap = 36;
                const v = new THREE.Vector3();
                outer: for (const m of smallMeshes) {
                    const pos = m.geometry && m.geometry.attributes && m.geometry.attributes.position;
                    if (!pos) continue;
                    const stride = Math.max(1, Math.floor(pos.count / Math.ceil(cap / smallMeshes.length)));
                    for (let i = 0; i < pos.count; i += stride) {
                        v.fromBufferAttribute(pos, i); m.localToWorld(v);
                        if (bigBox.containsPoint(v)) { pts.push(v.clone()); if (pts.length >= cap) break outer; }
                    }
                }
                if (pts.length < 4) continue;
                _ray.far = bigBox.getSize(new THREE.Vector3()).length();
                // Raycaster culls triangles by material.side. A point INSIDE a
                // solid prop sees only the target's BACK faces, which FrontSide
                // (the GLB default) skips → 0 hits → false negative. Force
                // DoubleSide on the target for the enclosure rays, then restore.
                const _savedSides = [];
                for (const m of bigMeshes) {
                    const mat = m.material;
                    (Array.isArray(mat) ? mat : [mat]).forEach((mm) => {
                        if (mm && mm.side !== THREE.DoubleSide) { _savedSides.push([mm, mm.side]); mm.side = THREE.DoubleSide; }
                    });
                }
                let enclosed = 0;
                for (const pt of pts) {
                    let hd = 0;
                    for (const d of AX) { _ray.set(pt, d); if (_ray.intersectObjects(bigMeshes, false).length) hd++; }
                    if (hd >= 5) enclosed++;
                }
                for (const [mm, s] of _savedSides) mm.side = s;
                const frac = enclosed / pts.length;
                if (frac >= 0.18) deep.push({ small, big, frac });
            }
            _ray.far = savedFar;
            if (deep.length) {
                deep.sort((a, b) => b.frac - a.frac);
                console.warn(`[checkClipping] ⚠ ${deep.length} object(s) substantially INSIDE another — likely misplaced. Move the smaller object's xz to a clear spot (findClearSpot helps), or set userData.allowIntersect = true if the overlap is intentional:`);
                for (const d of deep) {
                    console.warn(`  ${d.small.name || '(unnamed)'} is ~${Math.round(d.frac * 100)}% inside ${d.big.name || '(unnamed)'}`);
                }
            }
        } catch (e) {
            console.warn('[checkClipping] deep-interpenetration pass skipped:', e.message);
        }
        return report;
    };

    // ───────── 7.5 checkZFighting — flag + fix coplanar surfaces that z-fight ─────────
    // Z-fighting = two surfaces rendered at the SAME depth flicker frame-to-frame
    // (the depth buffer can't decide which is in front). It happens when geometry
    // is placed at the EXACT same point on an axis — a poster/screen/decal flush
    // ON a wall or floor, two panels at the same z, a logo quad on a billboard.
    // (Agents — esp. kimi — do this constantly: `panel.position.z = wall.z`.)
    //
    // Detection (low false-positive): a THIN mesh (extent < `thin` on one axis,
    // i.e. a flat panel/decal/quad) whose flat face is COPLANAR within `eps` with
    // another placed object's face, and which OVERLAPS it in the other two axes.
    // That's precisely the flush-decal case; solid stacked boxes aren't flagged.
    //
    // autoFix (default ON via the caller): nudge the THIN object OUT by `push`
    // (3 mm) along the coplanar axis, away from the other object's centre — enough
    // depth separation to kill the flicker, too small to see. Opt out per-object
    // with `userData.noZFightCheck = true` (e.g. an intentional polygonOffset decal).
    globalThis.checkZFighting = (scene, opts = {}) => {
        const { autoFix = false, exclude = [], eps = 0.002, thin = 0.06, push = 0.004, minOverlap = 0.02 } = opts;
        if (!scene) { console.warn('[checkZFighting] scene required'); return []; }
        const meshes = collectMeshes(scene, exclude).filter((m) => !(m.userData && m.userData.noZFightCheck));
        let _roots = scene.children.filter((c) => c !== globalThis._c && c !== globalThis._camera && !c.isLight && !c.isCamera);
        let _g = 0;
        while (_roots.length === 1 && !_roots[0].isMesh && _roots[0].children &&
               _roots[0].children.filter((c) => !c.isLight && !c.isCamera).length > 1 && _g++ < 4) {
            _roots = _roots[0].children.filter((c) => !c.isLight && !c.isCamera);
        }
        const _rootSet = new Set(_roots);
        const rootOf = (m) => { let o = m; while (o && !_rootSet.has(o)) o = o.parent; return o || m; };
        const E = meshes.map((m) => { const box = new THREE.Box3().setFromObject(m); return { m, box, root: rootOf(m), size: box.getSize(new THREE.Vector3()) }; });
        const AX = ['x', 'y', 'z'];
        const report = [];
        for (let i = 0; i < E.length; i++) {
            for (let j = i + 1; j < E.length; j++) {
                const a = E[i], b = E[j];
                if (a.root && a.root === b.root) continue;          // same model — its parts may share planes
                if (isAncestor(a.m, b.m) || isAncestor(b.m, a.m)) continue;
                for (const ax of AX) {
                    const o1 = AX[(AX.indexOf(ax) + 1) % 3], o2 = AX[(AX.indexOf(ax) + 2) % 3];
                    // must overlap in the other two axes
                    const ov1 = Math.min(a.box.max[o1], b.box.max[o1]) - Math.max(a.box.min[o1], b.box.min[o1]);
                    const ov2 = Math.min(a.box.max[o2], b.box.max[o2]) - Math.max(a.box.min[o2], b.box.min[o2]);
                    if (ov1 < minOverlap || ov2 < minOverlap) continue;
                    // coplanar on `ax`: some face of a within eps of some face of b
                    const faces = [[a.box.min[ax], b.box.min[ax]], [a.box.max[ax], b.box.max[ax]], [a.box.max[ax], b.box.min[ax]], [a.box.min[ax], b.box.max[ax]]];
                    if (!faces.some(([p, q]) => Math.abs(p - q) < eps)) continue;
                    // at least one must be THIN on `ax` (a panel/decal/quad)
                    const thinA = a.size[ax] < thin, thinB = b.size[ax] < thin;
                    if (!thinA && !thinB) continue;
                    report.push({ a: a.m, b: b.m, ax });
                    if (autoFix) {
                        const thinE = (thinA && (!thinB || a.size[ax] <= b.size[ax])) ? a : b;
                        const other = thinE === a ? b : a;
                        const dir = (thinE.box.min[ax] + thinE.box.max[ax]) >= (other.box.min[ax] + other.box.max[ax]) ? 1 : -1;
                        const mover = thinE.root || thinE.m;
                        mover.position[ax] += push * dir;
                        mover.updateMatrixWorld(true);
                        thinE.box.setFromObject(thinE.m);
                    }
                    break;   // one axis is enough per pair
                }
            }
        }
        if (report.length) {
            const verb = autoFix ? `nudged ${push * 1000}mm apart` : 'detected';
            console.warn(`[checkZFighting] ${verb} ${report.length} coplanar pair(s) that would flicker (place decals/panels a few mm proud of their surface, or set material.polygonOffset=true):`);
            for (const p of report.slice(0, 8)) console.warn(`  ${(p.a.name || '(unnamed)')} <=> ${(p.b.name || '(unnamed)')} (coplanar on ${p.ax})`);
            if (report.length > 8) console.warn(`  ...and ${report.length - 8} more`);
        }
        return report;
    };

    // ───────── 8. checkHovering — flag objects floating with no support below ─────────
    // Raycasts straight down from every solid mesh's bbox-bottom center. If
    // the ray hits another mesh between `minGap` and `maxGap` below, flags
    // the object as hovering in space when it should be resting on a surface.
    // Catches the classic "laptop floating mid-air off to the side of the
    // desk" / "props placed by hardcoded coords at vaguely the right height
    // but not actually on anything" failure mode.
    //
    // opts:
    //   minGap: ignore objects within this distance of the surface (touching;
    //           default 0.005 m).
    //   maxGap: ignore objects further than this from the nearest surface
    //           below (probably intentional: chandelier, drone, sky; default 1.0 m).
    //   autoFix: snap each flagged object down to its surface (default false).
    //   exclude: meshes to skip.
    //
    // Opt out per-object with `obj.userData.noSupportCheck = true` — use for
    // drones, balloons, chandeliers, characters mid-jump, etc.
    globalThis.checkHovering = (scene, opts = {}) => {
        const { minGap = 0.005, maxGap = 1.0, autoFix = false, exclude = [] } = opts;
        if (!scene) { console.warn('[checkHovering] scene required'); return []; }
        const excludeSet = new Set(exclude);
        // Operate on TOP-LEVEL placed objects (a desk, a chair, a fetched GLB),
        // NOT individual sub-meshes. A multi-part object's parts rest on each
        // other (a tabletop on its legs, a shelf board on its sides) — checking
        // each sub-mesh against the floor would false-flag every one of them.
        // Same granularity as checkDensity / the "things you placed" count.
        const allMeshes = collectMeshes(scene);
        // Find the "placed objects". Scenes usually parent everything under a
        // single wrapper group (`root`), so scene.children is just [root] — and
        // checking that one giant object finds no "others" beneath it and bails,
        // which is how a whole scene of mis-placed props sailed through. Descend
        // through a lone wrapper group (a few levels) to reach the real props.
        let roots = scene.children.filter((c) =>
            c !== globalThis._c && c !== globalThis._camera &&
            !c.isLight && !c.isCamera && !excludeSet.has(c));
        let _guard = 0;
        while (roots.length === 1 && !roots[0].isMesh && roots[0].children &&
               roots[0].children.filter((c) => !c.isLight && !c.isCamera).length > 1 && _guard++ < 4) {
            roots = roots[0].children.filter((c) =>
                c !== globalThis._c && c !== globalThis._camera &&
                !c.isLight && !c.isCamera && !excludeSet.has(c));
        }
        // Ground level = lowest surface in the scene. Objects resting at ground
        // level (the floor itself, or a prop sitting on the floor) are not
        // floaters — only flag things whose base is clearly ABOVE the ground.
        let groundY = Infinity;
        for (const m of allMeshes) {
            const b = new THREE.Box3().setFromObject(m);
            if (b.min.y < groundY) groundY = b.min.y;
        }
        const report = [];
        for (const root of roots) {
            if (root.userData && root.userData.noSupportCheck) continue;
            if (root.userData && root.userData._sunkPlacement) continue;   // deliberately buried by placeOn({sink}) — not a floater, not a sinker to rescue
            // A SEATED VRM rests on a chair (feet off the floor) — don't "snap her down".
            if (globalThis._seatedVRMs && globalThis._seatedVRMs.has(root)) continue;
            // Support-chain memory: if placeOn/snapToGround seated this object on a
            // recorded support, verify against THAT support (footprint rays, then a
            // bbox-contact fallback for geometry the rays slip through). Without
            // this, prop-on-prop placements get "corrected" to the floor — the
            // books-on-table → snapped-to-floor bug.
            // snapToGround records its groundMeshes ARRAY as the support;
            // placeOn records a single object. Normalize to a list.
            const recSupportRaw = root.userData && root.userData._supportTarget;
            const recSupports = !recSupportRaw ? null
                : (Array.isArray(recSupportRaw) ? recSupportRaw : [recSupportRaw]);
            if (recSupports && recSupports.length) {
                const sMeshes = recSupports.flatMap((r) => collectMeshes(r));
                if (sMeshes.length) {
                    const rb = tightBox(root);
                    const rcx = (rb.min.x + rb.max.x) / 2, rcz = (rb.min.z + rb.max.z) / 2;
                    const sup2 = supportYUnderFootprint(root, sMeshes, rcx, rcz, rb.min.y + 0.01, 5);
                    if (sup2 && rb.min.y - sup2.y < 0.06) continue;
                    let touching = false;
                    for (const rs of recSupports) {
                        const sb = tightBox(rs);
                        if (Math.abs(rb.min.y - sb.max.y) < 0.08 &&
                            rb.max.x > sb.min.x && rb.min.x < sb.max.x &&
                            rb.max.z > sb.min.z && rb.min.z < sb.max.z) { touching = true; break; }
                    }
                    if (touching) continue;
                }
            }
            const rootMeshes = collectMeshes(root);
            if (!rootMeshes.length) continue;           // lights-only / empty group
            const box = tightBox(root);
            const bx = (box.min.x + box.max.x) / 2;
            const bz = (box.min.z + box.max.z) / 2;
            const by = box.min.y;
            if (by <= groundY + 0.05) continue;         // resting at ground level — floor or floor-resting prop
            // targets = every mesh NOT part of this root object
            const others = allMeshes.filter((o) => !isAncestor(root, o) && o !== root);
            if (!others.length) continue;
            // Sample the whole footprint, not a single center point: take the
            // HIGHEST surface under the object's base. A center ray alone misses
            // the case where the object's centre is over a gap but its footprint
            // overhangs a surface (and vice-versa). Start the rays slightly
            // ABOVE the object's base so a surface it's resting ON (at exactly
            // by) is still caught as gap≈0 — starting below by would fall
            // through that surface to the floor and false-flag a seated object.
            // Skip pure-FX roots (glow planes, holograms, light sprites): if
            // every mesh is transparent it's not a solid prop that must rest on
            // something. Lights/cameras were already filtered above.
            let anyMesh = false, anyOpaque = false;
            root.traverse((o) => {
                if (!o.isMesh) return; anyMesh = true;
                const ms = Array.isArray(o.material) ? o.material : [o.material];
                if (ms.some((m) => m && !m.transparent)) anyOpaque = true;
            });
            if (anyMesh && !anyOpaque) continue;

            const support = supportYUnderFootprint(root, others, bx, bz, by + 0.01, 3);
            // Classify, DON'T silently skip the bad cases (the old code treated
            // "nothing beneath" and "far above" as intentional and ignored them
            // — which is exactly how a prop dumped in mid-air far from its desk
            // shipped unflagged). Unmarked floaters get reported; declare a
            // genuine floater (drone/lamp/orb) with userData.noSupportCheck.
            let kind, gap = 0;
            if (!support) {
                kind = 'void';                          // no surface under the footprint at all
            } else {
                gap = by - support.y;
                if (gap < minGap) continue;             // resting on something — fine
                kind = gap > maxGap ? 'far' : 'near';   // far above a surface vs a small hover
            }
            report.push({ obj: root, gap, kind });
            if (autoFix && kind === 'near') {           // only auto-snap a small, unambiguous hover
                root.position.y -= gap;
                root.updateMatrixWorld(true);
            }
        }
        if (report.length) {
            const verb = autoFix ? 'auto-snapped' : 'detected';
            console.warn(`[checkHovering] ${verb} ${report.length} hovering object(s) — rest props on a surface with placeOn(obj, surface); if a floater is intentional (drone/lamp/orb/bird) set obj.userData.noSupportCheck = true:`);
            for (const p of report.slice(0, 10)) {
                const n = p.obj.name || '(unnamed)';
                if (p.kind === 'void') console.warn(`  ${n} — floating with NO surface beneath its footprint (hand-coords don't say what it sits on; use placeOn)`);
                else if (p.kind === 'far') console.warn(`  ${n} — floating ${p.gap.toFixed(2)}m above the nearest surface below it`);
                else console.warn(`  ${n} — hovering ${p.gap.toFixed(3)}m above the nearest surface below it`);
            }
            if (report.length > 10) console.warn(`  ...and ${report.length - 10} more`);
        }
        return report;
    };

    // ───────── 9. checkDensity — flag sparse scenes ─────────
    // Counts the distinct "things" placed in the scene — top-level scene
    // children (and direct children of a single root group) that contain at
    // least one visible mesh with geometry. A fetched GLB, a VRM, or a
    // primitive added with one scene.add() each counts as one thing, so this
    // tracks "how many objects did you compose" rather than raw sub-mesh
    // count (a single GLB can be hundreds of sub-meshes). Warns when the
    // scene reads as a placeholder rather than a place.
    //
    // Advisory only — there's no auto-fix for "too empty"; you can't invent
    // geometry. The warning documents the sparse scene for the agent and for
    // the human reviewer. See AGENTS.md "Kitbash hard" for the density bar.
    //
    // opts:
    //   min: warn below this many distinct things (default 5).
    //   exclude: meshes to skip.
    globalThis.checkDensity = (scene, opts = {}) => {
        const { min = 5, exclude = [] } = opts;
        if (!scene) { console.warn('[checkDensity] scene required'); return 0; }
        const excludeSet = new Set(exclude);
        // A "thing" = a top-level scene child that owns renderable geometry.
        // Skip lights/cameras and camera-attached overlays.
        let things = 0;
        const roots = scene.children.filter((c) => c !== globalThis._c && c !== globalThis._camera);
        for (const root of roots) {
            if (excludeSet.has(root)) continue;
            if (root.isLight || root.isCamera) continue;
            let hasGeometry = false;
            root.traverse((o) => {
                if (hasGeometry) return;
                if (o.visible && o.isMesh && o.geometry) hasGeometry = true;
            });
            if (hasGeometry) things++;
        }
        if (things < min) {
            console.warn(
                `[checkDensity] sparse scene — ${things} distinct object(s) placed ` +
                `(a finished scene reads as a place, not a placeholder; aim for ${min}+). ` +
                `Kitbash: fetch_model.py many times, break kits into pieces, layer ` +
                `mid-ground dressing + architecture + atmosphere. See AGENTS.md "Kitbash hard".`
            );
        } else {
            console.log(`[checkDensity] ${things} distinct objects placed`);
        }
        return things;
    };

    // ───────── VRM expressive helpers (STATIONARY characters only) ─────────
    // These drive a planted VRM with an expressive clip (talk / cheer / reach /
    // raise / fist / salute / crazy / dance — sitting goes through seatOn /
    // sitOnGround). They are for a VRM that
    // is NOT being moved by a VRMCharacterController — the controller owns the
    // body's full-body clip while it walks/runs/climbs, and an expressive clip
    // played over it fights the locomotion (foot-slide, broken cycle). Use
    // these when she's standing/sitting still: a desk scene, a talking-to-
    // camera shot, an emote beat between moves. To go from moving → emoting,
    // let the controller finish (out of waypoints / forceAction('idle')) first.

    function getHipsNode(vrm) {
        const h = vrm && vrm.humanoid;
        if (h && h.getNormalizedBoneNode) { const n = h.getNormalizedBoneNode('hips'); if (n) return n; }
        if (h && h.getRawBoneNode) { const n = h.getRawBoneNode('hips'); if (n) return n; }
        let found = null;
        const root = (vrm && vrm.scene) || vrm;
        if (root && root.traverse) root.traverse((o) => { if (!found && /hips?$/i.test(o.name || '')) found = o; });
        return found;
    }

    // _markSeated(vrm) — register a VRM as SEATED so the post-setup placement
    // audit (checkClipping / checkHovering) skips it. A seated character legitimately
    // OVERLAPS the chair and has her feet off the floor; without this, the auto-fix
    // shoves her off the seat (separate-from-chair) or snaps her to the floor — the
    // "VRM floats off the seat / up in the air after seatOn" bug. The seated set
    // holds the VRM's scene root; the audits look up `globalThis._seatedVRMs`.
    function _markSeated(vrm) {
        if (vrm && vrm.scene) (globalThis._seatedVRMs = globalThis._seatedVRMs || new Set()).add(vrm.scene);
    }
    globalThis.unseat = (vrm) => { if (vrm && vrm.scene && globalThis._seatedVRMs) globalThis._seatedVRMs.delete(vrm.scene); };

    // findSeatSurface(chair) — raycast straight DOWN over a grid across the
    // chair's footprint and return the seat-pan height + its center xz. NOT
    // the bbox top (that's the backrest/headrest). The seat pan is the
    // BROADEST horizontal surface: a backrest is vertical (rays glance its
    // thin top edge), armrests/stretchers are small, but the seat catches the
    // most downward-ray hits. We histogram the hit heights and take the
    // fullest bin (tie → lower, so a tall flat-topped throne back loses to the
    // seat). Generalizes across chair models without per-model tuning.
    function findSeatSurface(chair) {
        const box = tightBox(chair);
        // Collect the chair's meshes DIRECTLY — do NOT use collectMeshes(), which
        // drops anything flagged userData.noClippingCheck. Chairs are routinely
        // marked noClippingCheck (so a seated VRM doesn't trip the clipping
        // audit), and that flag was silently hiding the seat from this raycast →
        // zero targets → bbox-estimate fallback → the VRM sank through the seat.
        // Seating must see the real geometry regardless of audit opt-outs.
        const meshes = [];
        chair.traverse((o) => { if (o.isMesh && o.visible) meshes.push(o); });
        const minX = box.min.x, maxX = box.max.x, minZ = box.min.z, maxZ = box.max.z;
        const ySky = box.max.y + 0.5;
        const N = 7;
        const hits = [];
        for (let i = 0; i < N; i++) {
            for (let j = 0; j < N; j++) {
                // inner 80% of the footprint — avoid riding the outer edges
                const x = minX + (0.1 + 0.8 * (i / (N - 1))) * (maxX - minX);
                const z = minZ + (0.1 + 0.8 * (j / (N - 1))) * (maxZ - minZ);
                _ray.set(new THREE.Vector3(x, ySky, z), _down);
                const h = meshes.length ? _ray.intersectObjects(meshes, false) : [];
                if (h.length) hits.push({ x, z, y: h[0].point.y });
            }
        }
        if (!hits.length) {
            // No raycastable geometry — estimate the seat ~45% up the bbox.
            return { y: box.min.y + 0.45 * (box.max.y - box.min.y),
                     cx: (minX + maxX) / 2, cz: (minZ + maxZ) / 2, fallback: true };
        }
        const BIN = 0.03;
        const bins = new Map();
        for (const h of hits) {
            const k = Math.round(h.y / BIN);
            (bins.get(k) || bins.set(k, []).get(k)).push(h);
        }
        let best = null;
        for (const [k, arr] of bins) {
            if (!best || arr.length > best.arr.length ||
                (arr.length === best.arr.length && k < best.k)) best = { k, arr };
        }
        const a = best.arr;
        const avg = (sel) => a.reduce((s, h) => s + sel(h), 0) / a.length;
        // pan extent (of the winning bin's hits) — lets seating bias the hips
        // toward the backrest instead of dead-centre
        const panMinX = Math.min(...a.map(h => h.x)), panMaxX = Math.max(...a.map(h => h.x));
        const panMinZ = Math.min(...a.map(h => h.z)), panMaxZ = Math.max(...a.map(h => h.z));
        return { y: avg((h) => h.y), cx: avg((h) => h.x), cz: avg((h) => h.z), fallback: false,
                 panDX: Math.max(0.001, panMaxX - panMinX), panDZ: Math.max(0.001, panMaxZ - panMinZ) };
    }

    // _detectChairFacing(chair, seat) — derive which way a chair "opens" from its
    // geometry, so a sitter faces OUT (away from the backrest) for ANY chair, no
    // hand-set faceY. The backrest is the chair geometry ABOVE the seat pan; its
    // XZ centroid, relative to the seat centre, points toward the BACK — so the
    // sitter faces the opposite way. Returns rotation.y radians, or null if the
    // chair has no clear back (a stool / centred backrest) so the caller can fall
    // back to faceY / camera-facing.
    function _detectChairFacing(chair, seat) {
        if (!chair) return null;
        const up = seat.y + 0.18;   // sample the backrest/arms zone above the pan
        const v = new THREE.Vector3();
        let sx = 0, sz = 0, n = 0;
        chair.traverse((o) => {
            if (!o.isMesh || !o.geometry || !o.geometry.attributes || !o.geometry.attributes.position) return;
            o.updateWorldMatrix(true, false);
            const pos = o.geometry.attributes.position;
            const step = Math.max(1, Math.floor(pos.count / 300));   // ~300 samples per mesh
            for (let i = 0; i < pos.count; i += step) {
                v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
                if (v.y > up) {
                    // weight = vertices this sample represents (so a 30k-vert
                    // backrest panel outvotes a 300-vert screw — unweighted,
                    // every MESH had equal say and detail meshes scrambled the
                    // centroid) × height above the pan (backrest TOP dominates
                    // armrests that sit just above the pan).
                    const w = step * (v.y - up);
                    sx += v.x * w; sz += v.z * w; n += w;
                }
            }
        });
        if (n <= 0) return null;
        const bx = (sx / n) - seat.cx, bz = (sz / n) - seat.cz;   // → toward the backrest
        const len = Math.hypot(bx, bz);
        if (len < 0.05) return null;   // backrest centred over the seat → ambiguous
        if (len < 0.10) console.warn('[seatOn] backrest signal is WEAK (near-symmetric chair geometry) — facing may be off; verify the render or pass faceY explicitly.');
        // face AWAY from the backrest. Heading convention: 0 = +Z, atan2(x, z).
        return Math.atan2(-bx / len, -bz / len);
    }

    // _restHipsOnSeat(vrm, seat, sink) — recentre the VRM over the seat and drop
    // it so the SEATED MESH UNDERSIDE (butt/thighs) rests on the seat surface.
    // Shared by seatOn's instant path AND its transition path's deferred settle
    // (after a stand_to_sit clip the body is in its final pose but at the clip's
    // authored height — this raycasts it onto the ACTUAL seat regardless of chair
    // height, the fix for "butt floating above the seat"). Assumes the seated
    // pose is already applied (mixer advanced).
    function _restHipsOnSeat(vrm, chair, seat, sink) {
        const hips = getHipsNode(vrm);
        if (!hips) { vrm.scene.position.y = seat.y - (sink || 0); vrm.scene.updateMatrixWorld(true); return; }
        vrm.scene.updateMatrixWorld(true);
        // 1) recentre XZ so the hips sit over the seat pan — biased toward the
        //    BACKREST, not dead-centre. A sitter's hips belong at the back of
        //    the pan; centring them left a visible gap to the backrest and hung
        //    the knees past the front edge ("doesn't line up with the chair").
        let tx = seat.cx, tz = seat.cz;
        const _facing = _detectChairFacing(chair, seat);
        if (_facing != null && seat.panDX !== undefined) {
            const backX = -Math.sin(_facing), backZ = -Math.cos(_facing);   // toward the backrest
            const depth = Math.abs(backX) * seat.panDX + Math.abs(backZ) * seat.panDZ;
            const shift = Math.min(0.12, depth * 0.18);
            tx += backX * shift; tz += backZ * shift;
        }
        let hp = hips.getWorldPosition(new THREE.Vector3());
        vrm.scene.position.x += (tx - hp.x);
        vrm.scene.position.z += (tz - hp.z);
        vrm.scene.updateMatrixWorld(true);
        // collect the chair's OWN meshes and the character's body meshes (disjoint
        // sets — chair is not under vrm.scene), so the two casts can't hit each
        // other.
        const chairMeshes = [];
        if (chair) chair.traverse((o) => { if (o.isMesh && o.visible) chairMeshes.push(o); });
        const bodyMeshes = [];
        vrm.scene.traverse((o) => { if (o.isMesh && o.visible) bodyMeshes.push(o); });
        // 2) Cast DOWN from above the hips onto the ACTUAL chair surface at the
        //    hips' XZ — this is the real seat height under the character, not a
        //    pre-computed scalar. If there's NO chair under the hips he is not
        //    actually over the seat → warn (don't silently float him at a guessed
        //    height, which read as "sitting on nothing").
        hp = hips.getWorldPosition(new THREE.Vector3());
        _ray.set(new THREE.Vector3(hp.x, hp.y + 0.5, hp.z), new THREE.Vector3(0, -1, 0));
        _ray.near = 0; _ray.far = 2.5;
        const ch = chairMeshes.length ? _ray.intersectObjects(chairMeshes, false) : [];
        let seatYhere = seat.y;
        if (ch.length) seatYhere = ch[0].point.y;
        else console.warn('[seatOn] settle: no chair surface beneath the hips — the character is NOT over the seat (check the standing spot / hipBack / facing). Resting at the estimated seat height; verify he is not floating.');
        // 3) rough lift so the body straddles the seat height, then find the lowest
        //    seated underside over the seat pan via a GRID of up-rays and rest THAT
        //    on the chair surface (mesh-to-mesh). Rays are restricted to the seat
        //    footprint so the forward feet/shins can't be picked. A single hip-XZ
        //    ray rests a higher thigh point and lets the butt clip; the grid finds
        //    the lower butt contact at the back of the pan.
        vrm.scene.position.y += (seatYhere - hp.y);
        vrm.scene.updateMatrixWorld(true);
        const up = new THREE.Vector3(0, 1, 0);
        let lowest = Infinity;
        const N = 6;                       // 13×13 fine grid → finds the true lowest, no between-sample miss
        for (let gi = -N; gi <= N; gi++) {
            for (let gj = -N; gj <= N; gj++) {
                const rx = seat.cx + gi * (0.20 / N);   // ±0.20 across the seat width
                const rz = seat.cz + gj * (0.22 / N);   // ±0.22 across the seat depth
                // start the up-ray just below the seat so it can't catch a foot
                // resting on the FLOOR far below the pan.
                _ray.set(new THREE.Vector3(rx, seatYhere - 0.25, rz), up);
                _ray.near = 0; _ray.far = 0.6;
                const h = bodyMeshes.length ? _ray.intersectObjects(bodyMeshes, false) : [];
                if (h.length && h[0].point.y < lowest) lowest = h[0].point.y;
            }
        }
        if (lowest < Infinity) vrm.scene.position.y += (seatYhere - lowest) - (sink || 0);
        else vrm.scene.position.y += 0.09;
        vrm.scene.updateMatrixWorld(true);
    }

    // _clampSeatedButt(vrm, chair, seat, sink) — per-frame ONE-SIDED clamp run
    // DURING the stand→sit descent: if the lowering body's underside drops BELOW
    // the seat surface over the pan, lift the root so it rests ON it (never below).
    // It only lifts — it never forces the body down — so the descent plays
    // naturally until the butt meets the seat, then holds there. This is the fix
    // for "the sit-down animation pushes the butt INTO the chair" (the one-shot
    // settle only fired at clip-end, so mid-descent the butt clipped through).
    // Coarse grid (cheap, runs every frame); no XZ recentre (that's the clip's job
    // mid-descent and the final settle's job at the end).
    function _clampSeatedButt(vrm, chair, seat, sink) {
        const target = seat.y - (sink || 0);
        const bodyMeshes = [];
        vrm.scene.traverse((o) => { if (o.isMesh && o.visible) bodyMeshes.push(o); });
        const up = new THREE.Vector3(0, 1, 0);
        let lowest = Infinity;
        const M = 3;   // 7×7 coarse grid — enough to catch the butt mid-descent
        for (let gi = -M; gi <= M; gi++) {
            for (let gj = -M; gj <= M; gj++) {
                const rx = seat.cx + gi * (0.20 / M);
                const rz = seat.cz + gj * (0.22 / M);
                _ray.set(new THREE.Vector3(rx, seat.y - 0.25, rz), up);
                _ray.near = 0; _ray.far = 0.6;
                const h = bodyMeshes.length ? _ray.intersectObjects(bodyMeshes, false) : [];
                if (h.length && h[0].point.y < lowest) lowest = h[0].point.y;
            }
        }
        if (lowest < Infinity && lowest < target) {
            vrm.scene.position.y += (target - lowest);   // lift only — clamp the butt onto the seat
            vrm.scene.updateMatrixWorld(true);
        }
    }
    globalThis._clampSeatedButt = _clampSeatedButt;

    // emote(vrm, slot, opts) — play an expressive clip on a stationary VRM.
    // Thin wrapper over playVRMADefault that defaults to looping and exists
    // so scene scripts read intent-first ("emote her", not "load a clip").
    // slot ∈ talk/cheer/reach/raise/fist/salute/crazy/dance (+ any loaded).
    // For sitting use seatOn / sitOnGround, not emote.
    globalThis.emote = async (vrm, slot, opts = {}) => {
        if (typeof globalThis.playVRMADefault !== 'function') {
            console.warn('[emote] playVRMADefault not available (no VRM modules loaded)');
            return;
        }
        return globalThis.playVRMADefault(vrm, slot, { loopOnce: false, ...opts });
    };

    // faceCamera(vrm, opts) — turn a stationary VRM to face the active camera.
    // The reusable version of seatOn's default facing: use it for talk-to-
    // camera shots, reaction beats, any planted character that should look at
    // the lens. opts.offset (radians) for a ¾ / profile turn (e.g. 0.4).
    // opts.camera to target a specific camera. Assumes the +Z-forward
    // convention (VRM faces +Z after VRMUtils.rotateVRM0 — AGENTS.md "VRM
    // facing wrong direction"); if a VRM reads backwards, add `offset: Math.PI`.
    globalThis.faceCamera = (vrm, opts = {}) => {
        const cam = opts.camera || globalThis._c || globalThis._camera;
        if (!cam || !cam.position || !vrm || !vrm.scene) {
            console.warn('[faceCamera] need a camera (globalThis._c) and a vrm');
            return;
        }
        const p = vrm.scene.position;
        vrm.scene.rotation.y = Math.atan2(cam.position.x - p.x, cam.position.z - p.z) + (opts.offset || 0);
        vrm.scene.updateMatrixWorld(true);
    };

    // focusPoint(obj, opts) — the world-space point to AIM A CAMERA AT.
    // NEVER `camera.lookAt(obj.position)` — an object's origin is wherever the
    // model was authored, and most placement-friendly assets (and VRMs) put it
    // at the BASE / feet (so snapToGround/placeOn work). Aiming there frames the
    // subject's ankles and points the camera at the floor. This returns the
    // object's VISUAL centre (bounding-box centre, honouring a pre-set
    // geometry.boundingBox), which is what you almost always want to frame.
    //   opts.yBias: fraction of the object's HEIGHT to nudge the target up/down
    //     from centre. For a character, ~+0.25 aims at the chest, ~+0.4 the face;
    //     0 (default) = dead centre. opts.target: reuse a Vector3.
    globalThis.focusPoint = (obj, opts = {}) => {
        const out = opts.target || new THREE.Vector3();
        if (!obj) { console.warn('[focusPoint] obj required'); return out; }
        const box = tightBox(obj);
        box.getCenter(out);
        const yBias = opts.yBias || 0;
        if (yBias) out.y += (box.max.y - box.min.y) * yBias;
        return out;
    };

    // lookAtObject(camera, obj, opts) — aim the camera at obj's visual centre
    // (not its origin). Convenience over focusPoint; same opts (yBias, etc.).
    globalThis.lookAtObject = (camera, obj, opts = {}) => {
        const cam = camera || globalThis._c || globalThis._camera;
        if (!cam || !obj) { console.warn('[lookAtObject] need a camera and an obj'); return; }
        cam.lookAt(globalThis.focusPoint(obj, opts));
    };

    // hinge(mesh, edge) — make a part swing around one EDGE instead of its
    // center: a box lid/flap opening, a door, a chest, a jaw, a book cover, a
    // gate. (Use it on parts YOU build — a primitive lid, a fetched door panel.
    // It only swings a single given mesh; it does NOT split a one-piece model
    // into moving sub-parts, so it can't, e.g., close the local laptop GLB,
    // which is modeled permanently open.) Rotating a mesh directly spins it
    // around its own origin (its
    // middle), so a lid "opens" by pivoting through the box — wrong. This puts a
    // pivot at the chosen edge of the mesh's current bounding box, reparents the
    // mesh under it preserving world position, and RETURNS THE PIVOT. Animate by
    // rotating the pivot, not the mesh:
    //     const lid = hinge(boxTop, 'back');     // hinge along the back edge
    //     // in renderFrame: lid.rotation.x = -openAmount;   // swings open
    // edge ∈ 'back'|'front'|'left'|'right'|'top'|'bottom' (the side the hinge is
    // on). Rotate around the axis the hinge runs along: back/front edge → rotate
    // .x; left/right edge → rotate .y; a horizontal flap on top/bottom → .x or .z.
    globalThis.hinge = (mesh, edge = 'back') => {
        if (!mesh) { console.warn('[hinge] mesh required'); return null; }
        mesh.updateMatrixWorld(true);
        const box = tightBox(mesh);
        const p = box.getCenter(new THREE.Vector3());
        if (edge === 'back') p.z = box.min.z;
        else if (edge === 'front') p.z = box.max.z;
        else if (edge === 'left') p.x = box.min.x;
        else if (edge === 'right') p.x = box.max.x;
        else if (edge === 'top') p.y = box.max.y;
        else if (edge === 'bottom') p.y = box.min.y;
        else console.warn(`[hinge] unknown edge "${edge}" — use back/front/left/right/top/bottom`);
        const pivot = new THREE.Group();
        pivot.name = (mesh.name || 'part') + '_hinge';
        pivot.position.copy(p);
        (mesh.parent || globalThis._scene || globalThis._s || mesh).add?.(pivot);
        pivot.updateMatrixWorld(true);
        pivot.attach(mesh);   // Object3D.attach reparents but PRESERVES world transform
        return pivot;
    };

    // seatOn(vrm, chair, opts) — sit a VRM properly IN a chair (not ON it).
    // Plays the sit clip, then lifts/lowers the whole VRM so its HIPS land on
    // the chair's seat surface — the fix for "she stands on the seat" (which
    // happens when you placeOn(vrm, chair), snapping her feet to the seat top,
    // or lower a standing-idle figure to a guessed height). After the sit clip
    // applies, her hips have some world height; we offset the root so that
    // height equals the seat's top. Feet then hang naturally toward the floor.
    //
    // opts:
    //   clip:  chair-sit slot (default 'sitting_normal_chair'; also
    //          'sitting_nervous_arm_rub_chair' for a fidgety variant)
    //   faceY: rotation.y to face her (e.g. 0 toward a +Z camera). Default: leave as-is.
    //   sink:  meters to sink hips below the seat surface so she rests in it (default 0.03)
    //
    //   transition: a stand→sit VRMA slot (e.g. 'stand_to_sit'). When set, seatOn
    //          does NOT snap into the seated pose — it stands the VRM in front of
    //          the seat (facing out) and plays the transition clip so she physically
    //          LOWERS into the chair (the Mixamo clip carries the hip descent), then
    //          defers the raycast butt-on-seat settle to clip-end (the descent runs
    //          in the render loop). Use this for "walk up and sit down" shots.
    //   fade:  crossfade seconds INTO the transition from the current clip (default 0.25)
    //   transitionDur / hipBack: override the clip length / how far in front to stand
    //          (default: clip duration / 0.46m, tuned for stand_to_sit).
    //
    // FACING CAVEAT: with no faceY, she's turned ONCE toward the camera's
    // position AT SETUP TIME. If your camera MOVES to a different angle for her
    // shot (most multi-shot scenes), she'll be facing the old setup position →
    // "turned away from camera". For a moving camera, pass `faceY` with the
    // fixed direction she should face for her shot, or call `faceCamera(vrm)` at
    // the start of that shot in renderFrame.
    globalThis.seatOn = async (vrm, chair, opts = {}) => {
        // ── TRANSITION MODE: walk-up-and-lower-into-the-chair ──
        if (opts.transition) {
            const seat = findSeatSurface(chair);
            if (seat.fallback) console.warn('[seatOn] transition: no raycastable seat surface — estimated from bbox; verify she lands flush.');
            // Facing priority: explicit faceY → the chair's own geometry (face
            // out, away from its backrest) → face the camera → leave as-is.
            let ry = vrm.scene.rotation.y;
            const cam = globalThis._c || globalThis._camera;
            const chairRy = _detectChairFacing(chair, seat);
            if (opts.faceY !== undefined) ry = opts.faceY;
            else if (chairRy != null) ry = chairRy;
            else if (cam && cam.position) ry = Math.atan2(cam.position.x - seat.cx, cam.position.z - seat.cz);
            vrm.scene.rotation.y = ry;
            // Stand in FRONT of the seat (facing out) so the clip's backward hip
            // travel lands the hips over the seat centre. PRESERVE the character's
            // current Y (the surface he's standing on — floor, landing, platform);
            // hard-coding Y=0 dropped him off any ELEVATED seat (e.g. a chair on a
            // landing), so the clip played in mid-air below it and he ended up
            // "sitting on nothing". The seat's own surface height is recovered by
            // the raycast settle at clip-end.
            const fwd = new THREE.Vector3(Math.sin(ry), 0, Math.cos(ry));
            const back = opts.hipBack ?? 0.46;
            const _curY = vrm.scene.position.y;
            vrm.scene.position.set(seat.cx + fwd.x * back, _curY, seat.cz + fwd.z * back);
            vrm.scene.updateMatrixWorld(true);
            let dur = opts.transitionDur ?? 2.25;
            // COHESIVE PATH: if this VRM is driven by a VRMRobotBody controller,
            // play the transition through the controller's seated state so it
            // crossfades from the prior emote/locomotion on the SAME mixer (and
            // the controller hands root control to us via _seated). Otherwise a
            // statically-placed VRM uses the standalone crossfade mixer.
            const _body = (typeof globalThis !== 'undefined' && globalThis._vrmControllers)
                ? globalThis._vrmControllers.get(vrm) : null;
            try {
                if (_body && typeof _body.beginSeated === 'function') {
                    const d = await _body.beginSeated(opts.transition, { fadeIn: opts.fade ?? 0.25 });
                    if (d && opts.transitionDur === undefined) dur = d;
                    // Keep the physics capsule in sync with the stand-in-front
                    // placement — otherwise the controller snaps the root back
                    // to the pre-sit stop point when it reclaims the body
                    // after standing up.
                    try {
                        const rb = _body.body ?? _body.charCtrl?.body ?? _body.controller?.charCtrl?.body;
                        if (rb && typeof rb.setTranslation === 'function') {
                            const bt = rb.translation();
                            rb.setTranslation({ x: seat.cx + fwd.x * back, y: bt.y, z: seat.cz + fwd.z * back }, true);
                        }
                    } catch (e) { /* body sync is best-effort */ }
                } else {
                    const r = await globalThis.playVRMADefault(vrm, opts.transition, { loop: false, fade: opts.fade ?? 0.25 });
                    if (r && r.clip && opts.transitionDur === undefined) dur = r.clip.duration;
                }
            } catch (e) { console.warn(`[seatOn] transition '${opts.transition}' failed: ${e.message}`); }
            // The descent plays out in the render loop. Two raycast corrections:
            //  • a per-frame CLAMP (from ~40% into the descent) keeps the lowering
            //    butt from clipping THROUGH the seat (the raycast affects the
            //    descent itself, not just the end);
            //  • a one-shot final SETTLE at clip-end does the precise mesh-to-mesh
            //    butt-on-seat placement (+ XZ recentre).
            // The render loop processes globalThis._seatSettles.
            const sink = opts.sink ?? 0.0;   // lowest seated vertex rests exactly ON the pan (mesh-to-mesh)
            const now = globalThis._sceneTime || 0;
            (globalThis._seatSettles = globalThis._seatSettles || []).push({
                clampFrom: now + Math.max(0.1, dur * 0.4),
                finalAt: now + Math.max(0.1, dur - 0.05),
                finalDone: false,
                clamp: () => { try { _clampSeatedButt(vrm, chair, seat, sink); } catch (e) {} },
                apply: () => { try { _restHipsOnSeat(vrm, chair, seat, sink); vrm.springBoneManager?.reset(); } catch (e) { console.warn('[seatOn] settle failed:', e.message); } },
            });
            _markSeated(vrm);   // exempt from the placement audit (overlaps chair / feet off floor)
            const _vNow = globalThis._sceneTime || 0;
            (globalThis._seatSettles = globalThis._seatSettles || []).push({
                clampFrom: Infinity, finalAt: _vNow + dur + 1.0, finalDone: false,
                clamp: () => {},
                apply: () => { try {
                    const facing = _detectChairFacing(chair, seat);
                    if (facing == null) return;
                    let dy = vrm.scene.rotation.y - facing;
                    dy = Math.atan2(Math.sin(dy), Math.cos(dy));
                    const deg = Math.abs(dy) * 180 / Math.PI;
                    if (deg > 110) console.warn(`[seatOn] ⚠ RE-RENDER REQUIRED — the sitter faces the BACKREST of '${chair.name || '(chair)'}' (${deg.toFixed(0)}° off). Most common cause: setting vrm.scene.rotation.y AFTER seatOn — remove it and pass faceY to seatOn instead.`);
                    else if (deg > 55) console.warn(`[seatOn] sitter is ${deg.toFixed(0)}° off '${chair.name || '(chair)'}'s natural facing — verify; pass faceY if deliberate.`);
                } catch (e) {} },
            });
            return seat.y;
        }
        const clip = opts.clip || 'sitting_normal_chair';
        if (typeof globalThis.playVRMADefault === 'function') {
            try { await globalThis.playVRMADefault(vrm, clip, { loopOnce: false }); }
            catch (e) { console.warn(`[seatOn] couldn't play '${clip}' (${e.message}); seating without a sit pose`); }
        }
        // Apply the sit pose BEFORE measuring hips. playVRMAFromBase64 plays the
        // clip at full weight but does NOT advance the AnimationMixer (the render
        // loop does, later), and vrm.update() drives spring bones / lookAt, NOT
        // the mixer. So without this the hips are measured in the REST pose
        // (standing, hips high); we'd seat those high hips, then the render loop
        // engages the sit pose and drops her ~0.4m → she sinks through the seat
        // to the floor. Advance the just-played mixer enough to settle the pose,
        // then update the VRM so bone world matrices reflect it.
        try {
            const mx = globalThis._mixer;
            if (mx && typeof mx.update === 'function') { mx.update(0.5); }
        } catch { /* mixer not ready */ }
        try { if (typeof vrm.update === 'function') vrm.update(1 / 30); } catch { /* not ready */ }

        // Raycast the actual seat pan (NOT the chair bbox top = backrest).
        const seat = findSeatSurface(chair);
        const seatTopY = seat.y;
        if (seat.fallback) console.warn('[seatOn] no raycastable seat surface found on the target — estimated from its bbox. If this is NOT a chair, or she\'s meant to sit on the FLOOR, use sitOnGround(vrm) instead — the chair sit clip on the ground/non-chair reads wrong (legs dangle/clip). Otherwise verify she sits flush.');
        // ── BAD-SEAT WARNINGS ──────────────────────────────────────────────
        // She is placed onto the seat surface regardless, but these read as bugs
        // on screen, so surface them loudly (the recurring "sits on nothing /
        // backwards" subagent failures).
        let _anyVisible = false;
        chair.traverse((o) => { if (o.isMesh && o.visible) _anyVisible = true; });
        if (!_anyVisible) console.warn('[seatOn] ⚠ the seat target has NO VISIBLE mesh — she will appear to SIT ON NOTHING. Use a REAL, visible chair, not an invisible placeholder cube. seatOn raycasts the seat surface itself, so a placeholder is never needed.');
        const _box = tightBox(chair); const _bs = _box.getSize(new THREE.Vector3());
        if (_detectChairFacing(chair, seat) == null) console.warn(`[seatOn] ⚠ the seat has no detectable BACKREST (featureless${_bs.y < 0.55 ? '/too-short cube' : ''}) — orientation falls back to facing the camera. A flat cube carries no facing; use a chair mesh with a back so the sitter faces out of it, or pass faceY.`);

        vrm.scene.position.x = seat.cx;
        vrm.scene.position.z = seat.cz;
        // Facing priority: explicit faceY → the chair's OWN geometry (face out,
        // away from the detected backrest) → face the camera. The chair-geometry
        // step is the fix for "sat backwards" — the sitter now orients to the
        // chair, not a guess. (Do NOT set vrm.scene.rotation.y yourself AFTER
        // seatOn — that overrides this; pass faceY instead.)
        const cam = globalThis._c || globalThis._camera;
        const _chairRy = _detectChairFacing(chair, seat);
        if (opts.faceY !== undefined) {
            vrm.scene.rotation.y = opts.faceY;
        } else if (_chairRy != null) {
            vrm.scene.rotation.y = _chairRy;
        } else if (cam && cam.position) {
            vrm.scene.rotation.y = Math.atan2(cam.position.x - seat.cx, cam.position.z - seat.cz);
        }
        vrm.scene.updateMatrixWorld(true);

        const hips = getHipsNode(vrm);
        const sink = opts.sink ?? 0.02;   // how far her underside presses INTO the seat (contact, no gap)
        if (hips) {
            // Step 1 — rough placement by the hip bone, just to get her mesh
            // near the seat for the measurement below.
            const hp0 = hips.getWorldPosition(new THREE.Vector3());
            vrm.scene.position.y += (seatTopY - hp0.y);
            vrm.scene.updateMatrixWorld(true);
            // Step 2 — place by the actual MESH, not the bone. The hip BONE sits
            // inside the pelvis ~10cm above the seat contact, so resting the bone
            // on the seat sinks her (butt below the seat, chair through the
            // stomach). Raycast UP through her own seated mesh at the hips' XZ;
            // the first hit is her underside (butt/thigh). Rest THAT on the seat.
            const bodyMeshes = [];
            vrm.scene.traverse((o) => { if (o.isMesh && o.visible) bodyMeshes.push(o); });
            const hp = hips.getWorldPosition(new THREE.Vector3());
            _ray.set(new THREE.Vector3(hp.x, seatTopY - 0.6, hp.z), new THREE.Vector3(0, 1, 0));
            _ray.near = 0; _ray.far = 1.4;
            const bh = bodyMeshes.length ? _ray.intersectObjects(bodyMeshes, false) : [];
            if (bh.length) {
                vrm.scene.position.y += (seatTopY - bh[0].point.y) - sink;  // underside → on the seat
            } else {
                // No mesh hit (rare) — fall back to a fixed pelvis-flesh offset
                // above the bone so she at least isn't sunk.
                vrm.scene.position.y += 0.09;
                console.warn('[seatOn] could not raycast the seated mesh under the hips — used a fixed pelvis offset; verify she sits flush');
            }
        } else {
            console.warn('[seatOn] hips bone not found — placing root at seat height; verify she sits, not floats');
            vrm.scene.position.y = seatTopY - sink;
        }
        vrm.scene.updateMatrixWorld(true);
        // A seated VRM OVERLAPS the chair (she's IN it) and her feet dangle above
        // the floor — so the post-setup placement audit would (a) push her off the
        // seat to separate her from the chair (checkClipping) and (b) snap her down
        // to the floor (checkHovering). Register her as SEATED so both audits skip
        // her. This is the fix for "the VRM floats off the seat / up in the air"
        // after seatOn (esp. in kimi scenes that don't mark anything).
        _markSeated(vrm);
        // the seat placement TELEPORTS the VRM — spring tails get dragged
        // through the body and can trap behind colliders (mane/hair/tie
        // chaos after seating). Re-init springs at the seated pose.
        try { vrm.springBoneManager?.reset(); } catch (e) {}
        _scheduleSeatVerify(vrm, chair, seat);
        return seatTopY;
    };

    // Deferred facing self-check: runs ~1.5s into the render, AFTER the scene's
    // own post-seatOn code (the classic mistake is setting vrm.scene.rotation.y
    // AFTER seatOn, silently undoing the chair-facing). Compares the sitter's
    // actual yaw to the chair's natural facing and escalates a near-180° error.
    function _scheduleSeatVerify(vrm, chair, seat) {
        const now = globalThis._sceneTime || 0;
        (globalThis._seatSettles = globalThis._seatSettles || []).push({
            clampFrom: Infinity, finalAt: now + 1.5, finalDone: false,
            clamp: () => {},
            apply: () => { try {
                const facing = _detectChairFacing(chair, seat);
                if (facing == null) return;
                let dy = vrm.scene.rotation.y - facing;
                dy = Math.atan2(Math.sin(dy), Math.cos(dy));
                const deg = Math.abs(dy) * 180 / Math.PI;
                if (deg > 110) {
                    console.warn(`[seatOn] ⚠ RE-RENDER REQUIRED — the sitter faces the BACKREST of '${chair.name || '(chair)'}' (${deg.toFixed(0)}° off its natural facing). Most common cause: the scene sets vrm.scene.rotation.y AFTER seatOn, overriding the chair-facing. Remove that line and pass faceY to seatOn instead.`);
                } else if (deg > 55) {
                    console.warn(`[seatOn] sitter is ${deg.toFixed(0)}° off '${chair.name || '(chair)'}'s natural facing — verify the render; pass faceY to seatOn if this is deliberate.`);
                }
            } catch (e) {} },
        });
    }

    // sitOnGround(vrm, opts) — sit a VRM on the FLOOR (cross-legged / floor pose),
    // NOT in a chair. The difference from seatOn: a chair has a seat surface the
    // hips rest ON; on the ground there's none — the pelvis rests just above the
    // floor and the legs fold. It uses a GROUND-sit clip ('sitting_on_ground')
    // because a chair-sit clip on the floor looks wrong (legs dangle / clip
    // through the ground). This is the fix for "she sat on the ground using the
    // chair sit animation." Plays the clip, settles the pose, then places the
    // hips at floorY + hipHeight.
    //
    // opts:
    //   clip:         ground-sit slot (default 'sitting_on_ground' — cross-legged;
    //                 pass 'sit_laying_on_ground' for lying down, with a larger hipHeight)
    //   at:           [x, z] ground position (default: the VRM's current x/z)
    //   groundMeshes: meshes to raycast for floor height (default: floor at opts.y)
    //   y:            explicit floor height when no groundMeshes (default 0)
    //   hipHeight:    how high the seated pelvis rests above the floor (default 0.08;
    //                 lying poses sit lower — try ~0.0–0.05)
    //   faceY:        fixed facing (same camera-facing default + stale-camera caveat as seatOn)
    globalThis.sitOnGround = async (vrm, opts = {}) => {
        if (!vrm || !vrm.scene) { console.warn('[sitOnGround] vrm required'); return 0; }
        let clip = opts.clip || 'sitting_on_ground';
        const loaded = globalThis.VRMA_DEFAULTS_B64 || {};
        if (!loaded[clip]) {
            if (loaded.sitting_normal_chair) {
                console.warn(`[sitOnGround] no '${clip}' VRMA loaded — add assets/animations/${clip}.vrma. Falling back to the CHAIR 'sitting_normal_chair' clip, which reads wrong on the floor (legs dangle/clip).`);
                clip = 'sitting_normal_chair';
            } else {
                console.warn(`[sitOnGround] no '${clip}' or chair-sit VRMA loaded — seating without a pose.`);
                clip = null;
            }
        }
        if (clip && typeof globalThis.playVRMADefault === 'function') {
            try { await globalThis.playVRMADefault(vrm, clip, { loopOnce: false }); }
            catch (e) { console.warn(`[sitOnGround] couldn't play '${clip}' (${e.message})`); }
        }
        // Settle the pose before measuring hips (same reason as seatOn — the
        // mixer isn't advanced by vrm.update()).
        try { const mx = globalThis._mixer; if (mx && mx.update) mx.update(0.5); } catch { /* not ready */ }
        try { if (typeof vrm.update === 'function') vrm.update(1 / 30); } catch { /* not ready */ }

        const at = opts.at || [vrm.scene.position.x, vrm.scene.position.z];
        vrm.scene.position.x = at[0];
        vrm.scene.position.z = at[1];
        let floorY = opts.y ?? 0;
        if (opts.groundMeshes) {
            const hit = rayDownTo(opts.groundMeshes, at[0], at[1]);
            if (hit) floorY = hit.point.y;
        }
        const cam = globalThis._c || globalThis._camera;
        if (opts.faceY !== undefined) vrm.scene.rotation.y = opts.faceY;
        else if (cam && cam.position) vrm.scene.rotation.y = Math.atan2(cam.position.x - at[0], cam.position.z - at[1]);
        vrm.scene.updateMatrixWorld(true);

        const hips = getHipsNode(vrm);
        if (hips) {
            // Place by the MESH, not the hip bone (the bone sits inside the body
            // — resting it on the floor sinks the butt/legs through the ground,
            // same bug as seatOn). Rough-lift by the bone, then raycast UP
            // through her own seated mesh at several points under her body and
            // rest the LOWEST hit (butt / folded shins / lying back — whatever
            // actually touches down) on the floor.
            const hp0 = hips.getWorldPosition(new THREE.Vector3());
            vrm.scene.position.y += (floorY + 0.25) - hp0.y;   // rough lift so the mesh is above the floor
            vrm.scene.updateMatrixWorld(true);
            const bodyMeshes = [];
            vrm.scene.traverse((o) => { if (o.isMesh && o.visible) bodyMeshes.push(o); });
            const hp = hips.getWorldPosition(new THREE.Vector3());
            // sample a grid under the body (hips ± 0.35m) so a forward knee/shin
            // or a lying torso is included, not just the point under the hips.
            let lowest = Infinity;
            for (let dx = -0.35; dx <= 0.351; dx += 0.175) {
                for (let dz = -0.35; dz <= 0.351; dz += 0.175) {
                    _ray.set(new THREE.Vector3(hp.x + dx, floorY - 0.6, hp.z + dz), new THREE.Vector3(0, 1, 0));
                    _ray.near = 0; _ray.far = 1.5;
                    const h = bodyMeshes.length ? _ray.intersectObjects(bodyMeshes, false) : [];
                    if (h.length && h[0].point.y < lowest) lowest = h[0].point.y;
                }
            }
            if (lowest !== Infinity) {
                vrm.scene.position.y += (floorY - lowest) + (opts.sink ?? 0.005);  // lowest underside → on the floor
            } else {
                vrm.scene.position.y += -0.25 + (opts.hipHeight ?? 0.08);   // undo rough lift, use hipHeight fallback
                console.warn('[sitOnGround] could not raycast the seated mesh — used hipHeight fallback; verify she rests on the floor');
            }
        } else {
            console.warn('[sitOnGround] hips bone not found — placing root at floor; verify she sits, not floats');
            vrm.scene.position.y = floorY + (opts.hipHeight ?? 0.08);
        }
        vrm.scene.updateMatrixWorld(true);
        _markSeated(vrm);   // floor-sitter: feet/legs folded, hips low — skip the audit's push/snap
        return floorY;
    };

    // ───────── heading helpers: objects that FACE where they point/go ─────────
    // The recurring bug these kill: an agent builds a vehicle with its nose
    // along one axis, then animates `obj.position.x = lerp(...)` — the model
    // slides SIDEWAYS, perpendicular to its own wheels, for the whole video
    // (the popemobile bug). Translation and heading must be coupled.
    //
    // `forward` is which LOCAL axis the model's nose/front points along in its
    // own space — read it off the fetch_model *_preview.jpg (axis guides).
    // three.js convention is '+z'; many GLBs are '-z' or '±x'.
    const _FWD_OFFSET = { '+z': 0, '-z': Math.PI, '+x': -Math.PI / 2, '-x': Math.PI / 2 };
    const _toVec3 = (p, fallbackY = 0) =>
        p?.isVector3 ? p.clone()
        : p?.isObject3D ? p.getWorldPosition(new THREE.Vector3())
        : Array.isArray(p) ? (p.length >= 3 ? new THREE.Vector3(p[0], p[1], p[2])
                                            : new THREE.Vector3(p[0], fallbackY, p[1]))
        : new THREE.Vector3();

    // Yaw-only aim: rotate obj about Y so its `forward` axis points at target
    // (Object3D | Vector3 | [x,z] | [x,y,z]). Pitch/roll untouched. Works for
    // nested objects (aims in the parent's space).
    globalThis.faceToward = (obj, target, opts = {}) => {
        const off = _FWD_OFFSET[opts.forward ?? '+z'] ?? 0;
        const tp = _toVec3(target, obj.position.y);
        if (obj.parent) obj.parent.worldToLocal(tp);
        const d = tp.sub(obj.position);
        if (d.x * d.x + d.z * d.z < 1e-10) return obj;     // directly above/below — keep yaw
        obj.rotation.y = Math.atan2(d.x, d.z) + off;
        return obj;
    };

    // Path mover with automatic heading: returns an `update(t)` to call each
    // frame. Positions obj along a smooth curve through the waypoints and
    // yaws it to face its travel direction — a vehicle/creature can never
    // travel sideways. Flat-ground yaw only (compose with alignToSurface for
    // slopes). Waypoints: [x,z] (keeps obj's current y), [x,y,z], or Vector3.
    //
    //   const drive = driveAlong(popemobile, [[-8,0],[0,1.5],[6,0]], { duration: 30, forward: '+z' });
    //   // in renderFrame: drive(t);
    //
    // opts: duration (s, default 10) · forward ('+z','-z','+x','-x') ·
    //       startTime (s the drive begins, default 0; before it: parked at the
    //       first waypoint, facing the path) · loop (wrap instead of stopping)
    globalThis.driveAlong = (obj, waypoints, opts = {}) => {
        const { duration = 10, forward, startTime = 0, loop = false } = opts;
        if (!forward || !(forward in _FWD_OFFSET)) {
            throw new Error("driveAlong: opts.forward is REQUIRED ('+z'|'-z'|'+x'|'-x') — which LOCAL axis the model's NOSE points along. There is no safe default: it varies per model. For fetched GLBs, read the *_preview.jpg axis guides (that's what they're for). For vehicles YOU build: house convention is nose along +Z, then forward:'+z'.");
        }
        const off = _FWD_OFFSET[forward];
        // sanity: a vehicle's nose is almost always along its LONG horizontal
        // axis — declaring forward perpendicular to it is the sideways bug
        // about to happen. Warn NOW, at setup, not 1200 frames later.
        try {
            const b = new THREE.Box3().setFromObject(obj);
            if (!b.isEmpty()) {
                // pivot-offset check: driveAlong moves the ORIGIN along the
                // path; if the mesh sits far from its origin (sloppy GLB
                // pivots), the body ORBITS the path — sweeping through
                // buildings while the origin politely follows the road.
                const c = b.getCenter(new THREE.Vector3());
                const lp = obj.position;
                const offXZ = Math.hypot(c.x - lp.x, c.z - lp.z);
                const dim = Math.max(b.max.x - b.min.x, b.max.z - b.min.z);
                if (offXZ > Math.max(0.5, dim * 0.6)) {
                    console.warn(`[driveAlong] ⚠ '${obj.name || '(unnamed)'}'s mesh is ${offXZ.toFixed(1)}m from its origin — driving the origin will swing the BODY wide of the path (through walls/buildings). Recenter first: wrap it (const rig = new THREE.Group(); rig.add(obj); obj.position.sub(center)) and drive the rig, or check the *_preview.jpg for the authored pivot.`);
                }
                const sx = b.max.x - b.min.x, sz = b.max.z - b.min.z;
                const longAxis = sx >= sz ? 'x' : 'z';
                const fwdAxis = (forward === '+x' || forward === '-x') ? 'x' : 'z';
                if (Math.max(sx, sz) / Math.max(0.001, Math.min(sx, sz)) >= 1.3 && longAxis !== fwdAxis) {
                    console.warn(`[driveAlong] ⚠ forward='${forward}' is PERPENDICULAR to '${obj.name || '(unnamed)'}'s long axis (${longAxis}) — for an elongated vehicle the nose is almost always along the long axis. Re-check the *_preview.jpg axis guides; this is probably forward:'${longAxis === 'x' ? '+x' : '+z'}' or its negative.`);
                }
            }
        } catch (e) { /* advisory only */ }
        const y0 = obj.position.y;
        const pts = waypoints.map(p => _toVec3(p, y0));
        if (pts.length < 2) throw new Error('driveAlong: need at least 2 waypoints');
        const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
        return (t) => {
            let u = (t - startTime) / duration;
            u = loop ? ((u % 1) + 1) % 1 : Math.min(1, Math.max(0, u));
            const p = curve.getPointAt(u);
            const tan = curve.getTangentAt(Math.min(0.999, Math.max(0.001, u)));
            obj.position.copy(p);
            if (tan.x * tan.x + tan.z * tan.z > 1e-10) {
                obj.rotation.y = Math.atan2(tan.x, tan.z) + off;
            }
            return u;
        };
    };

    // A worker/machine that OPERATES ON something stands BESIDE it, facing it —
    // a robot arm doesn't stand in the middle of its conveyor, a bartender
    // doesn't stand on the bar. Agents kept translating "the arm works the
    // line" into "the arm goes AT the line"; this helper encodes the right
    // layout in one call: offset along the machine's SHORT horizontal axis
    // (the working edge of an elongated machine), base kept at the machine's
    // floor level, nose aimed at the closest point of the machine.
    //
    //   stationBeside(robotArm, conveyor, { gap: 0.3, forward: '+z' });
    //
    // opts: gap (m of clearance from the machine's edge, default 0.2) ·
    //       side (+1 | -1 along the short axis; default = whichever side obj
    //       is already closest to, so a rough hand position picks the side) ·
    //       face (default true) · forward (obj's nose axis, for the aim)
    globalThis.stationBeside = (obj, machine, opts = {}) => {
        const { gap = 0.2, face = true, forward = '+z' } = opts;
        const mb = new THREE.Box3().setFromObject(machine);
        const ob = new THREE.Box3().setFromObject(obj);
        if (mb.isEmpty() || ob.isEmpty()) return obj;
        const msx = mb.max.x - mb.min.x, msz = mb.max.z - mb.min.z;
        const axis = msx <= msz ? 'x' : 'z';            // short horizontal axis = working side
        const mc = mb.getCenter(new THREE.Vector3());
        const half = (axis === 'x' ? msx : msz) / 2;
        const oHalf = (axis === 'x' ? (ob.max.x - ob.min.x) : (ob.max.z - ob.min.z)) / 2;
        const side = opts.side ?? (obj.position[axis] >= mc[axis] ? 1 : -1);
        // keep the obj's position along the machine's LONG axis (the author's
        // chosen station point), move it clear of the working edge
        obj.position[axis] = mc[axis] + side * (half + oHalf + gap);
        const longAxis = axis === 'x' ? 'z' : 'x';
        obj.position[longAxis] = Math.min(mb.max[longAxis], Math.max(mb.min[longAxis], obj.position[longAxis]));
        obj.position.y += mb.min.y - ob.min.y;          // base at the machine's floor level
        obj.updateMatrixWorld(true);
        if (face) {
            const aim = obj.position.clone(); aim[axis] = mc[axis];   // closest point on the line
            globalThis.faceToward(obj, aim, { forward });
        }
        return obj;
    };

    // Semantic line-intrusion audit: a TALL object planted IN a conveyor /
    // belt / assembly line (the recurring "robot arm standing in the middle of
    // its own conveyor"). Geometry can't know intent, but names can: anything
    // whose name matches the line regex is treated as a transport line; any
    // object rooted BELOW its surface that sticks UP through it, with its
    // footprint center inside the line's footprint, is an intruder. Parcels
    // riding ON the line (base at/above the surface) are fine. Opt out:
    // obj.userData.noIntrusionCheck (e.g. a deliberate crushed-by-the-line gag).
    const _LINE_RE = /conveyor|belt|assembly.?line|production.?line|treadmill|escalator/i;
    globalThis.checkLineIntrusion = (scene) => {
        const lines = [];
        scene.traverse(o => { if (_LINE_RE.test(o.name || '') && (o.isGroup || o.isMesh)) lines.push(o); });
        if (!lines.length) return [];
        const offenders = [];
        const isRelated = (a, b) => { let p = a; while (p) { if (p === b) return true; p = p.parent; } p = b; while (p) { if (p === a) return true; p = p.parent; } return false; };
        for (const line of lines) {
            const lb = new THREE.Box3().setFromObject(line);
            if (lb.isEmpty()) continue;
            const top = lb.max.y;
            const shrink = 0.1 * Math.min(lb.max.x - lb.min.x, lb.max.z - lb.min.z);
            for (const root of scene.children) {
                if (root === line || root.isLight || root.isCamera || !(root.isGroup || root.isMesh)) continue;
                if (root.userData?.noIntrusionCheck || root.userData?.vrm || isRelated(root, line)) continue;
                const ob = new THREE.Box3().setFromObject(root);
                if (ob.isEmpty()) continue;
                const cx = (ob.min.x + ob.max.x) / 2, cz = (ob.min.z + ob.max.z) / 2;
                const inside = cx > lb.min.x + shrink && cx < lb.max.x - shrink &&
                               cz > lb.min.z + shrink && cz < lb.max.z - shrink;
                if (!inside) continue;
                const rootedBelow = ob.min.y < top - 0.25;       // base under the surface = planted, not riding
                const sticksThrough = ob.max.y > top + 0.3;      // tall enough to pierce the line
                if (rootedBelow && sticksThrough) {
                    offenders.push({ obj: root, line });
                    console.warn(`[placement] ⚠ RE-RENDER REQUIRED — '${root.name || '(unnamed)'}' is planted IN THE MIDDLE of '${line.name}' (base below its surface, body sticking up through it). A machine/worker that operates on a line stands BESIDE it: stationBeside(obj, line, { gap, forward }) places it clear of the working edge, on the floor, facing the line. Items RIDING the line (parcels on top) are fine. Intentional intrusion: obj.userData.noIntrusionCheck = true.`);
                }
            }
        }
        if (!offenders.length) console.log(`[placement] line-intrusion OK (${lines.length} transport line(s) checked).`);
        return offenders;
    };

    // ───────── deprecated alias ─────────
    // Old scenes still call placeRelativeTo(obj, ref, side, gap). The bug
    // it carried (ignored obj's bbox) is gone now — this forwards to the
    // fixed placeAgainst so legacy scene scripts get the corrected behavior
    // without changes.
    globalThis.placeRelativeTo = (obj, ref, side, gap) => globalThis.placeAgainst(obj, ref, side, gap);
}
