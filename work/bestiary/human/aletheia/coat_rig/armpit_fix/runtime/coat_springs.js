// coat_springs.js: THE SPRING SOLVER OF HER COAT (human/aletheia/coat_rig, 11-14, Fable 5.2). A private module of the coat's
// spring-rig round; nothing live imports it (the landing is coat_rig/STAGED.md).
//
// WHERE IT COMES FROM: the hair rebuild's motion step, hair_craft/rebuild/priv_motion/runtime/coat.js (sha1 fa7cc3de, 11-14
// 06:16; Opus 5.5), its section "the hang in motion": `springGrid` (copied unchanged) and `coatSprings` (its method kept:
// a position-based cage of particles, a fixed substep, Verlet with damping, a drive toward the skinned pose, distance links
// down / across / two down / diagonals, a max distance from the skinned pose, collider grids the host binds, and each free
// particle's place and the cage's local turn written into a joint the mesh is skinned to). A HAIR SPEC RUNS THROUGH THIS
// FILE AS BEFORE (no `anchor` in a group = every particle carried by the one parent joint, the joints named
// hair_<group>_c<jj>_r<k>, gravity as the change of gravity in the parent's frame, ctl.colliders as the host pushes them).
// WHAT A COAT NEEDED MORE (each is read only from its own key; coat_rig/staged/coat_springs_for_the_hair.diff is the same
// as a diff against the hair's coat.js):
//   1. ANCHORS: a particle is carried by up to four body joints (spec group.anchor[i] = [[joint, weight] ...]: linear blend
//      skinning of its rest point), not by one parent: the skirt's pin ring follows her spine joints, a sleeve's chain her
//      forearm. opts.carriers: Map name -> { object (its matrixWorld), inverse (Matrix4: the coat's inverse bind of that
//      joint; the coat is bound at HER STAND, so object.matrixWorld x inverse carries a stand-pose point) }.
//   2. PLUMB TARGETS (group.plumb[i] 0..1, group.upright = a joint): a skirt hangs from its ring, it does not tilt with the
//      trunk. The pose a particle is drawn back to goes from "carried rigidly" (0) to "the rest shape hanging under the
//      ring particle of its column, turned only by her heading" (1). Gravity enters as that target and as the RATE of the
//      pull: group.omega2[i] (1/s2) = stiffness x g / depth below the ring, a pendulum's own (a rigid swing of the column
//      by an angle is then pulled back with g x angle at every depth: gravity's restoring acceleration, exactly); the
//      material's stiffness multiplies it. The rest pose is the equilibrium whenever she stands upright.
//   3. THE AIR: params.air (1/m) x (the air's speed against the sheet along its normal) squared, along the normal: a film of
//      0.52 kg/m2 is light, a walk at 1.5 m/s presses a face-on panel with a third of its weight. params.wind [x, y, z] m/s
//      (+ params.gust: a share that comes and goes in travelling waves) is the same force from moving air.
//   4. A SHEET, NOT RIBBONS: links two ACROSS (params.bend_across) beside two down; group.edge[i] marks a bound free edge
//      (params.edge_bend: stiffer along it); spec.welds [[gA, iA, gB, iB]] (B is A: the centre back above the vent);
//      spec.ties [[gA, iA, gB, iB, k]] (a soft link between groups: the vent's two edges).
//   5. HER AS COLLIDERS: spec.sdf (one grid a rigid segment of hers, in the bind frame, carried by a joint: the hips, each
//      thigh, each calf and boot; opts.grids: name -> springGrid) and spec.capsules (two joints and two radii: forearms,
//      hands, the tentacles' roots). Tested at the particles AND at the middle of every across link and every cell (a grid
//      100 mm wide lets a 90 mm thigh 15 mm through between two particles; at the half spacing 3.5 mm), each sample's
//      clearance never more than the film's own room there at rest (so the rest pose stays the rest). A touched sample
//      takes params.friction of the segment's own motion.
//   6. NO ALLOCATION IN A STEP (the hair's step made 2 matrices a collider a substep), a speed cap (params.vmax), and the
//      cost: ctl.stats.ms (the mean per step).
// The joints: a free particle's joint sits at its rest point with no turn (inverse bind = a translation); each step writes
// its world place and the cage's turn (grid: across x down x normal; chain: down, with the carrier's x) against its rest.
const THREE = globalThis.THREE;

// an SDF grid as a collider (the hair's, unchanged): trilinear phi and its gradient in the grid's own frame
export function springGrid(phi, meta) {
    const [nx, ny, nz] = meta.dims, lo = meta.lo, h = meta.h;
    const at = (i, j, k) => phi[(i * ny + j) * nz + k];
    function sample(x, y, z, g) {
        const gx = (x - lo[0]) / h, gy = (y - lo[1]) / h, gz = (z - lo[2]) / h;
        if (gx < 0 || gy < 0 || gz < 0 || gx > nx - 1.001 || gy > ny - 1.001 || gz > nz - 1.001) return 1e3;
        const i = Math.floor(gx), j = Math.floor(gy), k = Math.floor(gz);
        const fx = gx - i, fy = gy - j, fz = gz - k;
        const c000 = at(i, j, k), c100 = at(i + 1, j, k), c010 = at(i, j + 1, k), c110 = at(i + 1, j + 1, k);
        const c001 = at(i, j, k + 1), c101 = at(i + 1, j, k + 1), c011 = at(i, j + 1, k + 1), c111 = at(i + 1, j + 1, k + 1);
        const x00 = c000 + (c100 - c000) * fx, x10 = c010 + (c110 - c010) * fx;
        const x01 = c001 + (c101 - c001) * fx, x11 = c011 + (c111 - c011) * fx;
        const y0 = x00 + (x10 - x00) * fy, y1 = x01 + (x11 - x01) * fy;
        if (g) {
            const dy0 = ((c100 - c000) * (1 - fy) + (c110 - c010) * fy), dy1 = ((c101 - c001) * (1 - fy) + (c111 - c011) * fy);
            g[0] = dy0 * (1 - fz) + dy1 * fz;
            g[1] = (x10 - x00) * (1 - fz) + (x11 - x01) * fz;
            g[2] = y1 - y0;
        }
        return y0 + (y1 - y0) * fz;
    }
    return { sample, meta };
}

// 4x4 column-major helpers on plain arrays (no allocation in a step)
function mulPoint(m, x, y, z, out, o) {
    out[o] = m[0] * x + m[4] * y + m[8] * z + m[12];
    out[o + 1] = m[1] * x + m[5] * y + m[9] * z + m[13];
    out[o + 2] = m[2] * x + m[6] * y + m[10] * z + m[14];
}
function invRigid(m, out) {
    // the inverse of a rotation (x a uniform scale) + translation
    const s2 = m[0] * m[0] + m[1] * m[1] + m[2] * m[2] || 1;
    const a = 1 / s2;
    out[0] = m[0] * a; out[1] = m[4] * a; out[2] = m[8] * a; out[3] = 0;
    out[4] = m[1] * a; out[5] = m[5] * a; out[6] = m[9] * a; out[7] = 0;
    out[8] = m[2] * a; out[9] = m[6] * a; out[10] = m[10] * a; out[11] = 0;
    out[12] = -(out[0] * m[12] + out[4] * m[13] + out[8] * m[14]);
    out[13] = -(out[1] * m[12] + out[5] * m[13] + out[9] * m[14]);
    out[14] = -(out[2] * m[12] + out[6] * m[13] + out[10] * m[14]);
    out[15] = 1;
}

export function coatSprings(spec, bones, parent, opts = {}) {
    const P = { ...spec.params, ...(opts.params || {}) };
    const H = P.substep || 1 / 120;
    const now = () => (globalThis.performance ? globalThis.performance.now() : Date.now());
    // ---------------------------------------------------------------- the carriers (joints whose motion the cage reads)
    const car = [], carAt = new Map();
    const identity = new THREE.Matrix4();
    function carrier(name) {
        if (carAt.has(name)) return carAt.get(name);
        let c = opts.carriers?.get ? opts.carriers.get(name) : null;
        if (!c && parent && (name === spec.parent || name === '#parent')) c = { object: parent, inverse: null };
        if (!c) throw new Error(`[springs] no carrier joint '${name}'`);
        const k = car.length;
        car.push({ name, object: c.object, inverse: c.inverse || identity, K1: new Float64Array(16), K0: new Float64Array(16), K: new Float64Array(16),
            Ki: new Float64Array(16), Kp: new Float64Array(16), tmp: new THREE.Matrix4() });
        carAt.set(name, k);
        return k;
    }
    function readCarriers() {
        for (const c of car) {
            c.object.updateWorldMatrix?.(true, false);
            c.tmp.multiplyMatrices(c.object.matrixWorld, c.inverse);
            c.K1.set(c.tmp.elements);
        }
    }
    // ---------------------------------------------------------------- the particles
    const groups = [];
    let nAll = 0;
    for (const g of spec.groups) {
        const n = g.cols * g.rows;
        groups.push({ g, n, base: nAll, idx: (j, k) => j * g.rows + k });
        nAll += n;
    }
    const rest = new Float64Array(3 * nAll), pinned = new Uint8Array(nAll), maxd = new Float64Array(nAll), maxdR = new Float64Array(nAll);
    const clearP = new Float64Array(nAll), plumb = new Float64Array(nAll), omega2 = new Float64Array(nAll), colBase = new Int32Array(nAll);
    const aOff = new Int32Array(nAll + 1), aJ = [], aW = [];
    const boneOf = new Array(nAll).fill(null), jointName = new Array(nAll).fill(null), slaveOf = new Int32Array(nAll).fill(-1);
    const upright = new Int32Array(nAll).fill(-1), groupOf = new Int32Array(nAll), collides = new Uint8Array(nAll);
    const sagP = new Float64Array(nAll), sagAx = new Float64Array(3 * nAll);
    // (11-18) a particle's PLANES (group.planes[i] = [[nx, ny, nz, room m] ...], directions in its carrier's frame at the
    // stand, pointing from her limb out to the film): the particle never moves further AGAINST a direction than its room
    // (a sleeve's belly joint and her forearm: the film on that side would meet her arm); group.across_only: it moves only
    // across the limb's axis (group.axis)
    const plOff = new Int32Array(nAll + 1), plD = [], acrossOnly = new Uint8Array(nAll);
    const hairMode = !spec.groups.some((g) => g.anchor);
    const parentIdx = hairMode ? carrier(spec.parent || '#parent') : -1;
    groups.forEach((G, gi) => {
        const g = G.g;
        const flat = g.rest.flat();
        for (let q = 0; q < G.n; q++) {
            const i = G.base + q, j = Math.floor(q / g.rows), k = q % g.rows;
            rest[3 * i] = flat[3 * q]; rest[3 * i + 1] = flat[3 * q + 1]; rest[3 * i + 2] = flat[3 * q + 2];
            pinned[i] = g.pinned[q] ? 1 : 0;
            maxd[i] = g.max_dist ? g.max_dist[q] : 0;
            maxdR[i] = g.max_dist_rigid ? g.max_dist_rigid[q] : 0;
            clearP[i] = g.clear ? g.clear[q] : 0;
            plumb[i] = g.plumb ? g.plumb[q] : 0;
            // (11-18, the lead's note of 07:58: tuning the swing) params.stiff_scale: the pull back to the hanging shape x this
            // (a number, or one a row: [row 0 .. row 6]); the material's own numbers stay in the spec (c20 MATERIALS)
            const ss = P.stiff_scale == null ? 1 : (Array.isArray(P.stiff_scale) ? (P.stiff_scale[k] ?? 1) : P.stiff_scale);
            omega2[i] = g.omega2 ? g.omega2[q] * ss : -1;
            colBase[i] = G.base + G.idx(j, 0);
            groupOf[i] = gi;
            collides[i] = g.collide === false ? 0 : 1;
            if (g.upright) upright[i] = carrier(g.upright);
            if (g.sag || g.across_only) { sagP[i] = g.sag ? (g.sag[q] || 0) : 0; const a = g.axis || [0, -1, 0]; sagAx[3 * i] = a[0]; sagAx[3 * i + 1] = a[1]; sagAx[3 * i + 2] = a[2]; }
            acrossOnly[i] = g.across_only ? 1 : 0;
            plOff[i] = plD.length / 4;
            if (g.planes && g.planes[q]) for (const pl of g.planes[q]) plD.push(pl[0], pl[1], pl[2], pl[3]);
            aOff[i] = aJ.length;
            if (g.anchor) for (const [nm, w] of g.anchor[q]) { aJ.push(carrier(nm)); aW.push(w); }
            else { aJ.push(parentIdx); aW.push(1); }
            const nm = g.joint ? g.joint[q] : (k > 0 ? `hair_${g.name}_c${String(j).padStart(2, '0')}_r${k}` : null);
            jointName[i] = nm;
            boneOf[i] = nm && bones?.get ? (bones.get(nm) || null) : null;
        }
    });
    aOff[nAll] = aJ.length;
    plOff[nAll] = plD.length / 4;
    const PL = Float64Array.from(plD);
    for (const w of spec.welds || []) {
        const a = groups[w[0]].base + w[1], b = groups[w[2]].base + w[3];
        slaveOf[b] = a;
    }
    // ---------------------------------------------------------------- the links: [a, b, stiffness, rest length]
    // (a welded particle's links and samples act on its master: both sheets pull on the one particle)
    const eA = [], eB = [], eK = [], eL = [], eC = [];
    const master = (i) => (slaveOf[i] >= 0 ? slaveOf[i] : i);
    const restLen = (a, b) => Math.hypot(rest[3 * b] - rest[3 * a], rest[3 * b + 1] - rest[3 * a + 1], rest[3 * b + 2] - rest[3 * a + 2]);
    // (11-18, the lead's note of 07:58) params.fold_across 0..1: a FILM DOES NOT STRETCH BUT FOLDS. An across or a diagonal
    // link that is SHORTER than its rest pushes back only by this share (0: it folds freely, as film buckles where a leg
    // pushes into a panel; 1: the old two-sided spring, which moved the panel as one shell). Stretching is always resisted
    const FOLD = P.fold_across ?? 1.0;
    // (11-18 09:05) params.fold_from_row: the rows from which the film folds (above it the links stay two-sided: round her
    // hips the film rests on her, and a folding hip row sagged 2-4 mm into her at the vent and the pockets in the turn)
    const FOLD_FROM = P.fold_from_row ?? 0;
    const foldAt = (k) => (k >= FOLD_FROM ? FOLD : 1.0);
    const link = (a, b, s, comp = 1.0) => {
        if (!(s > 0) || (pinned[a] && pinned[b])) return;
        const L = restLen(a, b);
        a = master(a); b = master(b);
        if (a !== b) { eA.push(a); eB.push(b); eK.push(s); eL.push(L); eC.push(comp); }
    };
    for (const G of groups) {
        const g = G.g, at = (j, k) => G.base + G.idx(j, k);
        if (g.links === false) continue;                    // (a sleeve's belly: one free point between two carried ones)
        for (let j = 0; j < g.cols; j++) for (let k = 0; k < g.rows; k++) {
            const i = at(j, k), edge = g.edge ? g.edge[G.idx(j, k)] : 0;
            if (k + 1 < g.rows) link(i, at(j, k + 1), P.stretch ?? 1.0);
            if (k + 2 < g.rows) link(i, at(j, k + 2), edge ? Math.max(P.bend ?? 0.25, P.edge_bend ?? 0) : (P.bend ?? 0.25));
            if (j + 1 < g.cols && k > 0) link(i, at(j + 1, k), P.lateral ?? 0.5, foldAt(k));
            if (j + 2 < g.cols && k > 0) link(i, at(j + 2, k), P.bend_across ?? 0, foldAt(k));
            if (j + 1 < g.cols && k + 1 < g.rows) {
                link(i, at(j + 1, k + 1), P.shear ?? 0.2, foldAt(k));
                link(at(j + 1, k), at(j, k + 1), P.shear ?? 0.2, foldAt(k));
            }
        }
    }
    for (const t of spec.ties || []) link(groups[t[0]].base + t[1], groups[t[2]].base + t[3], t[4]);
    const nE = eA.length;
    const EA = Int32Array.from(eA), EB = Int32Array.from(eB), EK = Float64Array.from(eK), EL = Float64Array.from(eL), EC = Float64Array.from(eC);
    // ---------------------------------------------------------------- her colliders
    const ctl = { params: P, colliders: [], stats: { frames: 0, resets: 0, maxMove: 0, maxMoveFrame: 0, pushes: 0, clamped: 0, ms: 0, msSum: 0, steps: 0, msCollide: 0, msRead: 0, msBones: 0 },
        groups, enabled: true };
    const sdfs = [];                                        // { grid, car } (spec.sdf + opts.grids), in the bind frame
    for (const s of spec.sdf || []) {
        const grid = opts.grids?.[s.name];
        // (a grid's own clearance, spec.sdf[].clear m: a LIMB's (her forearm, her hand) keeps a small one and is listed, so
        // met, before her body's grids; without it the sample's own)
        if (grid && opts.carriers?.get(s.joint)) sdfs.push({ name: s.name, grid, car: carrier(s.joint), clear: s.clear ?? -1 });
    }
    const caps = (spec.capsules || []).filter((c) => !opts.carriers || (opts.carriers.get(c.a) && opts.carriers.get(c.b)))
        .map((c) => ({ name: c.name, a: carrier(c.a), b: carrier(c.b), ra: c.ra, rb: c.rb, A: new Float64Array(3), B: new Float64Array(3) }));
    // the samples: every colliding free particle, the middle of every across link, the centre of every cell; OR (11-18) a
    // group's own PROBES (group.probes: [j0, k0, fa, fb, x, y, z, clearance] each): a point of the FILM the cell (j0, k0)
    // carries: its place at the stand (x, y, z) and its bilinear weights (fa, fb) on the cell's four joints. A probe is
    // carried EXACTLY AS THE SKIN CARRIES THAT FILM VERTEX: the weighted sum of its four joints' moves, each joint's own
    // turn applied to the vertex's offset from it (a pinned corner: its carrier's turn). The cage is the broad sheet; the
    // film's folds lie up to 5 cm under it, and it is the film that must not pass through her (c20_weights.py lays a probe
    // a quarter cell, at the film vertex that lies furthest inward; the hair's m4 probes are the same idea).
    const REST_BOUND = P.rest_bound !== false;
    const sIdx = [], sN = [], sClear = [], sW = [], sO = [], sKind = [], sGain = [], sCell = [], sTier = [], cellAt = new Map(), cellIds = [], cellR = [];
    const sample = (ids, clear) => {
        sN.push(ids.length); for (let q = 0; q < 4; q++) { sIdx.push(q < ids.length ? master(ids[q]) : -1); sW.push(q < ids.length ? 1 / ids.length : 0); }
        sClear.push(clear); for (let q = 0; q < 12; q++) sO.push(0); sKind.push(0); sGain.push(1);
    };
    const gvec = [0, 0, 0];
    const restPhi = (x, y, z) => {
        let d = 1e3;
        for (const s of sdfs) d = Math.min(d, s.grid.sample(x, y, z, null));
        return d;
    };
    for (const G of groups) {
        const g = G.g, at = (j, k) => G.base + G.idx(j, k);
        if (g.collide === false) continue;
        if (g.probes) {
            for (const p of g.probes) {
                const [j0, k0, fa, fb, px, py, pz, clear, tier] = p;
                const ids = [at(j0, k0), at(j0 + 1, k0), at(j0, k0 + 1), at(j0 + 1, k0 + 1)];
                const w = [(1 - fa) * (1 - fb), fa * (1 - fb), (1 - fa) * fb, fa * fb];
                let free = 0;
                for (let q = 0; q < 4; q++) if (!pinned[ids[q]]) free += w[q];
                if (free < 0.05) continue;                  // (carried by her body: nothing here can move)
                sN.push(4);
                let far = 0;
                for (let q = 0; q < 4; q++) {
                    sIdx.push(master(ids[q])); sW.push(w[q]);
                    const ox = px - rest[3 * ids[q]], oy = py - rest[3 * ids[q] + 1], oz = pz - rest[3 * ids[q] + 2];
                    sO.push(ox, oy, oz);                    // the vertex from each of its joints, at the stand
                    far = Math.max(far, Math.sqrt(ox * ox + oy * oy + oz * oz));
                }
                // (its cell, for the frame's candidate search: the cell's four joints and how far a probe of it reaches)
                const ck = `${G.base}:${j0}:${k0}`;
                if (!cellAt.has(ck)) { cellAt.set(ck, cellIds.length / 4); for (let q = 0; q < 4; q++) cellIds.push(master(ids[q])); cellR.push(0); }
                const ci = cellAt.get(ck);
                cellR[ci] = Math.max(cellR[ci], far);
                sCell[sN.length - 1] = ci;
                sTier[sN.length - 1] = tier || 0;
                // (a probe part of whose cell is pinned moves by its free share of a push: the push is that much larger)
                sClear.push(clear); sKind.push(1); sGain.push(Math.min(2.5, 1 / free));
            }
            continue;
        }
        for (let j = 0; j < g.cols; j++) for (let k = 0; k < g.rows; k++) {
            const i = at(j, k);
            if (!pinned[i] && slaveOf[i] < 0) sample([i], clearP[i]);
        }
        if (P.samples === false) continue;
        const mid = (ids) => {
            let x = 0, y = 0, z = 0, c = 0, free = 0;
            for (const i of ids) { x += rest[3 * i]; y += rest[3 * i + 1]; z += rest[3 * i + 2]; c += clearP[i]; if (!pinned[i]) free++; }
            if (!free) return;
            const n = ids.length;
            // a sample between particles: never more clearance than the film's own room there at rest (params.rest_bound;
            // false = the spec's clearances as given: a coat's are the film's own depth under the cage + a margin, c20)
            const room = restPhi(x / n, y / n, z / n);
            sample(ids, REST_BOUND ? Math.max(0.0005, Math.min(c / n, room - 0.001)) : c / n);
        };
        for (let j = 0; j + 1 < g.cols; j++) for (let k = 1; k < g.rows; k++) mid([at(j, k), at(j + 1, k)]);
        for (let j = 0; j + 1 < g.cols; j++) for (let k = 0; k + 1 < g.rows; k++) mid([at(j, k), at(j + 1, k), at(j, k + 1), at(j + 1, k + 1)]);
    }
    // (a particle's own clearance, too, never more than its room at rest)
    if (REST_BOUND) for (let s = 0; s < sN.length; s++) if (sN[s] === 1) {
        const i = sIdx[4 * s];
        sClear[s] = Math.max(0.0005, Math.min(sClear[s], restPhi(rest[3 * i], rest[3 * i + 1], rest[3 * i + 2]) - 0.001));
    }
    const nS = sN.length, anyProbes = sKind.some((k) => k === 1);
    const SCELL = new Int32Array(nS).fill(-1), STIER = new Uint8Array(nS);
    for (let s = 0; s < nS; s++) if (sCell[s] != null) { SCELL[s] = sCell[s]; STIER[s] = sTier[s] || 0; }
    // (params.probe_tiers: a probe of tier 1, one of the dense ones where the film rests near her, meets her colliders on
    // every second substep and always on a frame's last; false = every probe on every substep)
    const TIERS = P.probe_tiers !== false;
    const nCell = cellR.length, CELL = Int32Array.from(cellIds), CELLR = Float64Array.from(cellR);
    const SI = Int32Array.from(sIdx), SN = Int32Array.from(sN), SC = Float64Array.from(sClear);
    const SW = Float64Array.from(sW), SO = Float64Array.from(sO), SK = Uint8Array.from(sKind), SG = Float64Array.from(sGain);
    // a sample's place now -> sp (the mean of its particles; a probe: its film vertex as the skin carries it: each of its
    // four joints' place + that joint's turn (TQ, see turns()) on the vertex's offset from it, by its weights)
    const sp = [0, 0, 0];
    function samplePos(s) {
        const o = 4 * s;
        if (!SK[s]) {
            const n = SN[s];
            let x = 0, y = 0, z = 0;
            for (let q = 0; q < n; q++) { const i = 3 * SI[o + q]; x += cur[i]; y += cur[i + 1]; z += cur[i + 2]; }
            sp[0] = x / n; sp[1] = y / n; sp[2] = z / n;
            return;
        }
        let x = 0, y = 0, z = 0;
        for (let q = 0; q < 4; q++) {
            const w = SW[o + q];
            if (w === 0) continue;
            // (TR: the joint's turn as a matrix, row major, from turns(): a pinned corner's is its carrier's)
            const i = SI[o + q], oo = 12 * s + 3 * q, ox = SO[oo], oy = SO[oo + 1], oz = SO[oo + 2], r = 9 * i, p = 3 * i;
            x += w * (cur[p] + TR[r] * ox + TR[r + 1] * oy + TR[r + 2] * oz);
            y += w * (cur[p + 1] + TR[r + 3] * ox + TR[r + 4] * oy + TR[r + 5] * oz);
            z += w * (cur[p + 2] + TR[r + 6] * ox + TR[r + 7] * oy + TR[r + 8] * oz);
        }
        sp[0] = x; sp[1] = y; sp[2] = z;
    }
    // which colliders a sample can meet in this frame (a bit a collider: grids first, then capsules), found once a frame
    const nD = sdfs.length, nC = caps.length;
    const cand = new Int32Array(nS);
    const capA = new Float64Array(3 * nC), capB = new Float64Array(3 * nC);
    const REACH = 0.15;                                     // m: a sample farther than this from a collider's box / axis now does not meet it this frame
    // ---------------------------------------------------------------- state
    const cur = new Float64Array(3 * nAll), prev = new Float64Array(3 * nAll);
    const R0 = new Float64Array(3 * nAll), R1 = new Float64Array(3 * nAll), Rt = new Float64Array(3 * nAll);     // carried rigidly
    const T0 = new Float64Array(3 * nAll), T1 = new Float64Array(3 * nAll), Tt = new Float64Array(3 * nAll);     // the pose pulled to
    const nrm = new Float64Array(3 * nAll);
    const v3 = new THREE.Vector3(), qa = new THREE.Quaternion(), mb = new THREE.Matrix4();
    const ax = new THREE.Vector3(), ay = new THREE.Vector3(), az = new THREE.Vector3();
    const down = new THREE.Vector3(0, -1, 0), gRest = new THREE.Vector3(...(spec.gravity_rest || [0, -1, 0])), acc = new THREE.Vector3();
    const restQ = new Array(nAll).fill(null);
    const tp = [0, 0, 0], tq = [0, 0, 0];
    let last = null, tNow = 0;
    ctl.jointWorld = new Float64Array(7 * nAll);            // per particle: its world place and the cage's turn (x, y, z, w)

    // the cage's local frame at particle i from positions X (flat, any frame): across, down, normal. A chain (one column)
    // takes its across axis from ref (the carrier's own x)
    function frameAt(G, X, j, k, out, ref) {
        const g = G.g, p = (jj, kk) => 3 * (G.base + G.idx(jj, kk));
        const k0 = k > 0 ? k - 1 : k, k1 = k + 1 < g.rows ? k + 1 : k;
        const j0 = j > 0 ? j - 1 : j, j1 = j + 1 < g.cols ? j + 1 : j;
        ay.set(X[p(j, k1)] - X[p(j, k0)], X[p(j, k1) + 1] - X[p(j, k0) + 1], X[p(j, k1) + 2] - X[p(j, k0) + 2]).normalize();
        if (j1 !== j0) ax.set(X[p(j1, k)] - X[p(j0, k)], X[p(j1, k) + 1] - X[p(j0, k) + 1], X[p(j1, k) + 2] - X[p(j0, k) + 2]);
        else if (ref) ax.set(ref[0], ref[1], ref[2]);
        else ax.set(1, 0, 0);
        ax.addScaledVector(ay, -ax.dot(ay)).normalize();
        az.crossVectors(ax, ay);
        mb.makeBasis(ax, ay, az);
        return out.setFromRotationMatrix(mb);
    }
    for (const G of groups) for (let j = 0; j < G.g.cols; j++) for (let k = 0; k < G.g.rows; k++) {
        restQ[G.base + G.idx(j, k)] = frameAt(G, rest, j, k, new THREE.Quaternion(), null).invert();
    }
    // EVERY PARTICLE'S TURN NOW (TQ: x, y, z, w a particle): the cage's frame at it (across, down, across x down; frameAt's
    // rule in plain arithmetic) against its rest frame. What its joint is given (writeBones) and what a probe turns its
    // offset by (samplePos): found once a substep, before her colliders are met
    const TQ = new Float64Array(4 * nAll), RQ = new Float64Array(4 * nAll), TR = new Float64Array(9 * nAll);
    for (let i = 0; i < nAll; i++) {
        const q = restQ[i];
        RQ[4 * i] = q.x; RQ[4 * i + 1] = q.y; RQ[4 * i + 2] = q.z; RQ[4 * i + 3] = q.w; TQ[4 * i + 3] = 1;
        TR[9 * i] = TR[9 * i + 4] = TR[9 * i + 8] = 1;
    }
    function turns() {
        for (const G of groups) {
            const rows = G.g.rows, cols = G.g.cols, base = G.base;
            for (let j = 0; j < cols; j++) for (let k = 0; k < rows; k++) {
                const i = base + j * rows + k;
                if (pinned[i] && anyProbes) {
                    // (a pinned corner of a probe's cell turns with its carrier: its matrix for samplePos)
                    const K = car[aJ[aOff[i]]].K, r = 9 * i;
                    TR[r] = K[0]; TR[r + 1] = K[4]; TR[r + 2] = K[8]; TR[r + 3] = K[1]; TR[r + 4] = K[5]; TR[r + 5] = K[9]; TR[r + 6] = K[2]; TR[r + 7] = K[6]; TR[r + 8] = K[10];
                }
                const a = 3 * (i - (k > 0 ? 1 : 0)), b = 3 * (i + (k + 1 < rows ? 1 : 0));
                let yx = cur[b] - cur[a], yy = cur[b + 1] - cur[a + 1], yz = cur[b + 2] - cur[a + 2];
                let l = Math.sqrt(yx * yx + yy * yy + yz * yz) || 1e-12;
                yx /= l; yy /= l; yz /= l;
                let xx, xy, xz;
                if (cols > 1) {
                    const c = 3 * (i - (j > 0 ? rows : 0)), d = 3 * (i + (j + 1 < cols ? rows : 0));
                    xx = cur[d] - cur[c]; xy = cur[d + 1] - cur[c + 1]; xz = cur[d + 2] - cur[c + 2];
                } else { const K = car[aJ[aOff[i]]].K1; xx = K[0]; xy = K[1]; xz = K[2]; }      // (a chain: its carrier's own x)
                const dt = xx * yx + xy * yy + xz * yz;
                xx -= dt * yx; xy -= dt * yy; xz -= dt * yz;
                l = Math.sqrt(xx * xx + xy * xy + xz * xz) || 1e-12;
                xx /= l; xy /= l; xz /= l;
                const zx = xy * yz - xz * yy, zy = xz * yx - xx * yz, zz = xx * yy - xy * yx;
                // the quaternion of the basis (columns x, y, z)
                const tr = xx + yy + zz;
                let qx, qy, qz, qw;
                if (tr > 0) { const s = 0.5 / Math.sqrt(tr + 1); qw = 0.25 / s; qx = (yz - zy) * s; qy = (zx - xz) * s; qz = (xy - yx) * s; }
                else if (xx > yy && xx > zz) { const s = 2 * Math.sqrt(1 + xx - yy - zz); qw = (yz - zy) / s; qx = 0.25 * s; qy = (yx + xy) / s; qz = (zx + xz) / s; }
                else if (yy > zz) { const s = 2 * Math.sqrt(1 + yy - xx - zz); qw = (zx - xz) / s; qx = (yx + xy) / s; qy = 0.25 * s; qz = (zy + yz) / s; }
                else { const s = 2 * Math.sqrt(1 + zz - xx - yy); qw = (xy - yx) / s; qx = (zx + xz) / s; qy = (zy + yz) / s; qz = 0.25 * s; }
                // x the rest frame's inverse
                const bx = RQ[4 * i], by = RQ[4 * i + 1], bz = RQ[4 * i + 2], bw = RQ[4 * i + 3];
                const ux = qx * bw + qw * bx + qy * bz - qz * by, uy = qy * bw + qw * by + qz * bx - qx * bz,
                    uz = qz * bw + qw * bz + qx * by - qy * bx, uw = qw * bw - qx * bx - qy * by - qz * bz;
                TQ[4 * i] = ux; TQ[4 * i + 1] = uy; TQ[4 * i + 2] = uz; TQ[4 * i + 3] = uw;
                if (anyProbes && !pinned[i]) {
                    // (the same turn as a matrix, row major: a probe turns its offset by it, samplePos)
                    const r = 9 * i, x2 = ux + ux, y2 = uy + uy, z2 = uz + uz;
                    const xx2 = ux * x2, xy2 = ux * y2, xz2 = ux * z2, yy2 = uy * y2, yz2 = uy * z2, zz2 = uz * z2, wx2 = uw * x2, wy2 = uw * y2, wz2 = uw * z2;
                    TR[r] = 1 - yy2 - zz2; TR[r + 1] = xy2 - wz2; TR[r + 2] = xz2 + wy2;
                    TR[r + 3] = xy2 + wz2; TR[r + 4] = 1 - xx2 - zz2; TR[r + 5] = yz2 - wx2;
                    TR[r + 6] = xz2 - wy2; TR[r + 7] = yz2 + wx2; TR[r + 8] = 1 - xx2 - yy2;
                }
            }
        }
    }
    function targets(R, T) {
        // R: every particle's rest point carried by its anchors (linear blend); T: the pose it is pulled to (plumb)
        for (let i = 0; i < nAll; i++) {
            let x = 0, y = 0, z = 0;
            const rx = rest[3 * i], ry = rest[3 * i + 1], rz = rest[3 * i + 2];
            for (let a = aOff[i]; a < aOff[i + 1]; a++) {
                mulPoint(car[aJ[a]].K1, rx, ry, rz, tp, 0);
                x += aW[a] * tp[0]; y += aW[a] * tp[1]; z += aW[a] * tp[2];
            }
            R[3 * i] = x; R[3 * i + 1] = y; R[3 * i + 2] = z;
        }
        for (let i = 0; i < nAll; i++) {
            const pl = plumb[i];
            if (pl > 0 && upright[i] >= 0) {
                const b = colBase[i], K = car[upright[i]].K1;
                const hl = Math.hypot(K[8], K[10]) || 1, s = K[8] / hl, c = K[10] / hl;      // her heading
                const ox = rest[3 * i] - rest[3 * b], oy = rest[3 * i + 1] - rest[3 * b + 1], oz = rest[3 * i + 2] - rest[3 * b + 2];
                const px = R[3 * b] + c * ox + s * oz, py = R[3 * b + 1] + oy, pz = R[3 * b + 2] - s * ox + c * oz;
                T[3 * i] = R[3 * i] + (px - R[3 * i]) * pl; T[3 * i + 1] = R[3 * i + 1] + (py - R[3 * i + 1]) * pl; T[3 * i + 2] = R[3 * i + 2] + (pz - R[3 * i + 2]) * pl;
            } else { T[3 * i] = R[3 * i]; T[3 * i + 1] = R[3 * i + 1]; T[3 * i + 2] = R[3 * i + 2]; }
            if (sagP[i] > 0) {
                // A SLEEVE'S END ROUND HER FOREARM (group.sag[i] m, group.axis: the limb's axis at the stand): it lies where
                // gravity lays it, toward the ground ACROSS the limb (nothing along a hanging arm, its whole room under a
                // level one), less the same at the stand (the drape already hangs so). down = (0, -1, 0)
                const K = car[aJ[aOff[i]]].K1, a0 = sagAx[3 * i], a1 = sagAx[3 * i + 1], a2 = sagAx[3 * i + 2];
                const wx = K[0] * a0 + K[4] * a1 + K[8] * a2, wy = K[1] * a0 + K[5] * a1 + K[9] * a2, wz = K[2] * a0 + K[6] * a1 + K[10] * a2;
                const s0x = a1 * a0, s0y = a1 * a1 - 1, s0z = a1 * a2;
                const rx = K[0] * s0x + K[4] * s0y + K[8] * s0z, ry = K[1] * s0x + K[5] * s0y + K[9] * s0z, rz = K[2] * s0x + K[6] * s0y + K[10] * s0z;
                T[3 * i] += sagP[i] * (wy * wx - rx); T[3 * i + 1] += sagP[i] * (wy * wy - 1 - ry); T[3 * i + 2] += sagP[i] * (wy * wz - rz);
            }
        }
        for (let i = 0; i < nAll; i++) if (slaveOf[i] >= 0) {
            const a = slaveOf[i];
            for (let q = 0; q < 3; q++) { R[3 * i + q] = R[3 * a + q]; T[3 * i + q] = T[3 * a + q]; }
        }
    }
    function normals() {
        // the sheet's normal at every particle of a grid (for the air), from the cage as it stands
        for (const G of groups) {
            const g = G.g;
            if (g.cols < 2) continue;
            for (let j = 0; j < g.cols; j++) for (let k = 0; k < g.rows; k++) {
                const i = G.base + G.idx(j, k);
                frameAt(G, cur, j, k, qa, null);
                nrm[3 * i] = az.x; nrm[3 * i + 1] = az.y; nrm[3 * i + 2] = az.z;
            }
        }
    }
    function relax(n) {
        // THE CAGE PUT CLEAR OF HER WITHOUT MOTION (a reset: the first frame, a jump in time). The pose a particle is pulled
        // to can lie inside her (her legs stand otherwise than at the coat's bind: 60 mm inside her thigh at the first frame
        // of her walk, and the first step then threw the hem 40 cm): the links, the reach and her colliders, n rounds, and
        // the cage is at rest where that leaves it. params.settle (0 = the hair's reset, unchanged)
        if (!(n > 0)) return;
        Rt.set(R1); Tt.set(T1);
        for (const c of car) { c.K.set(c.K1); c.Kp.set(c.K1); invRigid(c.K, c.Ki); }
        turns();
        candidates();
        linkStiffness(H);
        for (let k = 0; k < n; k++) { projectLinks(); clampReach(); turns(); collide(); weldAll(false); }
        prev.set(cur);
    }
    function reset() {
        readCarriers();
        for (const c of car) { c.K0.set(c.K1); c.Kp.set(c.K1); c.K.set(c.K1); invRigid(c.K, c.Ki); }
        targets(R1, T1);
        R0.set(R1); T0.set(T1); cur.set(T1); prev.set(T1);
        for (let i = 0; i < nAll; i++) if (pinned[i]) for (let q = 0; q < 3; q++) { cur[3 * i + q] = R1[3 * i + q]; prev[3 * i + q] = R1[3 * i + q]; }
        // (the hair's host colliders: their last matrices)
        for (const C of ctl.colliders) { C.object.updateWorldMatrix?.(true, false); C.M0 = C.object.matrixWorld.clone(); }
        relax(P.settle ?? 0);
        ctl.stats.resets++;
    }
    function wind(i, t, out) {
        const W = P.wind;
        if (!W || (!W[0] && !W[1] && !W[2])) { out[0] = out[1] = out[2] = 0; return; }
        const x = cur[3 * i], y = cur[3 * i + 1], z = cur[3 * i + 2];
        const gs = P.gust ?? 0;
        const g1 = gs ? 1 + gs * (0.6 * Math.sin(1.9 * t + 2.2 * x + 1.1 * z) + 0.4 * Math.sin(3.7 * t - 1.6 * x + 2.9 * y + 0.7)) : 1;
        out[0] = W[0] * g1; out[1] = W[1] * g1; out[2] = W[2] * g1;
    }
    const FR = P.friction ?? 0;
    function pushSample(s, dx, dy, dz, kc) {
        // move a sample out by (dx, dy, dz): each of its free particles takes the whole move (a probe with a pinned corner:
        // its gain); a touched particle takes a share of the segment's own motion (friction): kc = the carrier whose
        // surface it touched
        const n = SN[s], gn = SG[s];
        if (gn !== 1) { dx *= gn; dy *= gn; dz *= gn; }
        for (let q = 0; q < n; q++) {
            const i = SI[4 * s + q];
            if (pinned[i]) continue;
            const x = 3 * i;
            cur[x] += dx; cur[x + 1] += dy; cur[x + 2] += dz;
            if (FR > 0) {
                // where this point of the segment was a substep ago: the particle's velocity goes toward the segment's
                const c = car[kc];
                mulPoint(c.Ki, cur[x], cur[x + 1], cur[x + 2], tq, 0);
                mulPoint(c.Kp, tq[0], tq[1], tq[2], tp, 0);
                prev[x] += (tp[0] - prev[x]) * FR; prev[x + 1] += (tp[1] - prev[x + 1]) * FR; prev[x + 2] += (tp[2] - prev[x + 2]) * FR;
            }
        }
        ctl.stats.pushes++;
    }
    function capsuleEnds(useK1) {
        for (let c = 0; c < nC; c++) {
            // a capsule's ends: its two joints' own places (K x the joint's place at the stand: car.home)
            const ca = car[caps[c].a], cb = car[caps[c].b];
            mulPoint(useK1 ? ca.K1 : ca.K, ca.home[0], ca.home[1], ca.home[2], capA, 3 * c);
            mulPoint(useK1 ? cb.K1 : cb.K, cb.home[0], cb.home[1], cb.home[2], capB, 3 * c);
        }
    }
    function bitsAt(x, y, z, reach) {
        // the colliders within `reach` of a point now: a grid's box, a capsule's axis (+ its radius)
        let bits = 0;
        for (let d = 0; d < nD; d++) {
            const sd = sdfs[d], c = car[sd.car], m = sd.grid.meta;
            mulPoint(c.Ki, x, y, z, tp, 0);
            if (tp[0] > m.lo[0] - reach && tp[1] > m.lo[1] - reach && tp[2] > m.lo[2] - reach && tp[0] < m.lo[0] + m.h * m.dims[0] + reach
                && tp[1] < m.lo[1] + m.h * m.dims[1] + reach && tp[2] < m.lo[2] + m.h * m.dims[2] + reach) bits |= 1 << d;
        }
        for (let c = 0; c < nC; c++) {
            const a = 3 * c, ex = capB[a] - capA[a], ey = capB[a + 1] - capA[a + 1], ez = capB[a + 2] - capA[a + 2];
            const l2 = ex * ex + ey * ey + ez * ez || 1e-12;
            let t = ((x - capA[a]) * ex + (y - capA[a + 1]) * ey + (z - capA[a + 2]) * ez) / l2;
            t = t < 0 ? 0 : t > 1 ? 1 : t;
            const px = x - (capA[a] + t * ex), py = y - (capA[a + 1] + t * ey), pz = z - (capA[a + 2] + t * ez);
            const r = Math.max(caps[c].ra, caps[c].rb) + reach;
            if (px * px + py * py + pz * pz < r * r) bits |= 1 << (nD + c);
        }
        return bits;
    }
    const cellBits = new Int32Array(nCell);
    function candidates() {
        // once a frame: the colliders each sample can meet before the next (its box / axis within REACH now, at either end
        // of the frame's motion). A PROBE takes its cell's (11-18: the cell's middle, with the cell's own reach more: 96
        // tests for 964; found a sample at a time it cost a third of the cage's own time)
        if (!nS || nD + nC === 0) return;
        capsuleEnds(true);
        for (let d = 0; d < nD; d++) { const c = car[sdfs[d].car]; invRigid(c.K1, c.Ki); }
        for (let c = 0; c < nCell; c++) {
            let x = 0, y = 0, z = 0;
            for (let q = 0; q < 4; q++) { const i = 3 * CELL[4 * c + q]; x += cur[i]; y += cur[i + 1]; z += cur[i + 2]; }
            cellBits[c] = bitsAt(x / 4, y / 4, z / 4, REACH + CELLR[c]);
        }
        for (let s = 0; s < nS; s++) {
            if (SCELL[s] >= 0) { cand[s] = cellBits[SCELL[s]]; continue; }
            samplePos(s);
            cand[s] = bitsAt(sp[0], sp[1], sp[2], REACH);
        }
    }
    const CAPCL = P.cap_clear ?? -1;                        // a capsule's clearance (m); < 0: the sample's own
    const CPASS = P.collide_passes ?? 1;
    const SEEN = new Float64Array(4 * nS * Math.max(1, nD));    // per sample and grid: where the grid was last read, the room there
    function collide(skipTier1 = false) {
        if (!nS || nD + nC === 0) return;
        capsuleEnds(false);
        for (let s = 0; s < nS; s++) {
            const bits = cand[s];
            if (!bits || (skipTier1 && STIER[s])) continue;
            samplePos(s);
            let x = sp[0], y = sp[1], z = sp[2];
            const cl = SC[s];
            // HER LIMBS' CAPSULES FIRST, HER BODY'S GRIDS LAST: where the film is squeezed between her hand and her thigh the
            // two cannot both be kept; the last word is her body's (a hand brushing the film's outside by a few mm is what a
            // hand does to a coat; a thigh through the film is not). A capsule keeps params.cap_clear, the grids the sample's own
            const clc = CAPCL >= 0 ? Math.min(cl, CAPCL) : cl;
            for (let c = 0; c < nC; c++) {
                if (!(bits & (1 << (nD + c)))) continue;
                const a = 3 * c, ex = capB[a] - capA[a], ey = capB[a + 1] - capA[a + 1], ez = capB[a + 2] - capA[a + 2];
                const l2 = ex * ex + ey * ey + ez * ez || 1e-12;
                let t = ((x - capA[a]) * ex + (y - capA[a + 1]) * ey + (z - capA[a + 2]) * ez) / l2;
                t = t < 0 ? 0 : t > 1 ? 1 : t;
                const px = x - (capA[a] + t * ex), py = y - (capA[a + 1] + t * ey), pz = z - (capA[a + 2] + t * ez);
                const d2 = px * px + py * py + pz * pz, r = caps[c].ra + (caps[c].rb - caps[c].ra) * t + clc;
                if (d2 >= r * r || d2 < 1e-18) continue;
                const dd = Math.sqrt(d2), k = (r - dd) / dd;
                pushSample(s, px * k, py * k, pz * k, caps[c].a);
                x += px * k; y += py * k; z += pz * k;
            }
            for (let d = 0; d < nD; d++) {
                if (!(bits & (1 << d))) continue;
                const sd = sdfs[d], c = car[sd.car], clg = sd.clear >= 0 && sd.clear < cl ? sd.clear : cl;
                mulPoint(c.Ki, x, y, z, tp, 0);
                // (the hair's m4 rule: a distance field changes by at most the distance moved, so a sample that has moved
                // less, in the grid's own frame, than the room it had at its last read is still clear and the grid is not
                // read: SEEN = where it was read and the room it had there. Outside the grid's box the room is the way back
                // to the box: her surface lies a box margin further)
                const cb = 4 * (s * nD + d), ex = tp[0] - SEEN[cb], ey = tp[1] - SEEN[cb + 1], ez = tp[2] - SEEN[cb + 2], sl = SEEN[cb + 3];
                if (sl > 0 && ex * ex + ey * ey + ez * ez < sl * sl) continue;
                // (the distance alone first: the gradient only for a sample that is pushed)
                const d0 = sd.grid.sample(tp[0], tp[1], tp[2], null);
                SEEN[cb] = tp[0]; SEEN[cb + 1] = tp[1]; SEEN[cb + 2] = tp[2];
                if (d0 >= 999) {
                    const m = sd.grid.meta, lo = m.lo, h = m.h, dm = m.dims;
                    const bx = Math.max(lo[0] - tp[0], 0, tp[0] - (lo[0] + h * (dm[0] - 1))), by = Math.max(lo[1] - tp[1], 0, tp[1] - (lo[1] + h * (dm[1] - 1))),
                        bz = Math.max(lo[2] - tp[2], 0, tp[2] - (lo[2] + h * (dm[2] - 1)));
                    SEEN[cb + 3] = Math.sqrt(bx * bx + by * by + bz * bz);
                    continue;
                }
                SEEN[cb + 3] = d0 - clg - 1e-4;
                if (d0 >= clg) continue;
                SEEN[cb + 3] = 0;
                const dist = sd.grid.sample(tp[0], tp[1], tp[2], gvec);
                const gl = Math.sqrt(gvec[0] * gvec[0] + gvec[1] * gvec[1] + gvec[2] * gvec[2]) || 1, push = (clg - dist) / gl, K = c.K;
                const dx = (K[0] * gvec[0] + K[4] * gvec[1] + K[8] * gvec[2]) * push, dy = (K[1] * gvec[0] + K[5] * gvec[1] + K[9] * gvec[2]) * push,
                    dz = (K[2] * gvec[0] + K[6] * gvec[1] + K[10] * gvec[2]) * push;
                pushSample(s, dx, dy, dz, sd.car);
                x += dx; y += dy; z += dz;
            }
        }
    }
    function projectLinks() {
        for (let e = 0; e < nE; e++) {
            const ia = EA[e], ib = EB[e], a = 3 * ia, b = 3 * ib;
            const wa = pinned[ia] ? 0 : 1, wb = pinned[ib] ? 0 : 1;
            const dx = cur[b] - cur[a], dy = cur[b + 1] - cur[a + 1], dz = cur[b + 2] - cur[a + 2];
            const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1e-9;
            const k = EKh[e] * (d < EL[e] ? EC[e] : 1.0) * (d - EL[e]) / d / (wa + wb);
            cur[a] += wa * k * dx; cur[a + 1] += wa * k * dy; cur[a + 2] += wa * k * dz;
            cur[b] -= wb * k * dx; cur[b + 1] -= wb * k * dy; cur[b + 2] -= wb * k * dz;
        }
        for (let i = 0; i < nAll; i++) if (slaveOf[i] >= 0) {
            const a = 3 * slaveOf[i], x = 3 * i;
            cur[x] = cur[a]; cur[x + 1] = cur[a + 1]; cur[x + 2] = cur[a + 2];
        }
    }
    function clampReach() {
        for (let i = 0; i < nAll; i++) {
            if (pinned[i] || slaveOf[i] >= 0) continue;
            const x = 3 * i;
            if (maxd[i] > 0 || (hairMode && maxd[i] === 0)) {
                // the max distance from the pose pulled to (the hair: from the skinned pose, 0 = held)
                const dx = cur[x] - Tt[x], dy = cur[x + 1] - Tt[x + 1], dz = cur[x + 2] - Tt[x + 2], d2 = dx * dx + dy * dy + dz * dz;
                if (d2 > maxd[i] * maxd[i]) { const s = maxd[i] / (Math.sqrt(d2) || 1); cur[x] = Tt[x] + dx * s; cur[x + 1] = Tt[x + 1] + dy * s; cur[x + 2] = Tt[x + 2] + dz * s; ctl.stats.clamped++; }
            }
            if (maxdR[i] > 0) {
                const dx = cur[x] - Rt[x], dy = cur[x + 1] - Rt[x + 1], dz = cur[x + 2] - Rt[x + 2], d2 = dx * dx + dy * dy + dz * dz;
                if (d2 > maxdR[i] * maxdR[i]) { const s = maxdR[i] / Math.sqrt(d2); cur[x] = Rt[x] + dx * s; cur[x + 1] = Rt[x + 1] + dy * s; cur[x + 2] = Rt[x + 2] + dz * s; ctl.stats.clamped++; }
            }
            const p0 = plOff[i], p1 = plOff[i + 1];
            if (p1 > p0 || acrossOnly[i]) {
                // its move from where its carrier carries it (s), in the world; the carrier's turn now (K)
                const K = car[aJ[aOff[i]]].K;
                let sx = cur[x] - Rt[x], sy = cur[x + 1] - Rt[x + 1], sz = cur[x + 2] - Rt[x + 2];
                if (acrossOnly[i]) {
                    const a0 = sagAx[x], a1 = sagAx[x + 1], a2 = sagAx[x + 2];
                    const wx = K[0] * a0 + K[4] * a1 + K[8] * a2, wy = K[1] * a0 + K[5] * a1 + K[9] * a2, wz = K[2] * a0 + K[6] * a1 + K[10] * a2;
                    const al = sx * wx + sy * wy + sz * wz;
                    sx -= al * wx; sy -= al * wy; sz -= al * wz;
                }
                for (let pass = 0; pass < 2; pass++) for (let p = p0; p < p1; p++) {
                    const n0 = PL[4 * p], n1 = PL[4 * p + 1], n2 = PL[4 * p + 2], room = PL[4 * p + 3];
                    const wx = K[0] * n0 + K[4] * n1 + K[8] * n2, wy = K[1] * n0 + K[5] * n1 + K[9] * n2, wz = K[2] * n0 + K[6] * n1 + K[10] * n2;
                    const dn = sx * wx + sy * wy + sz * wz;
                    if (dn < -room) { const k = -room - dn; sx += k * wx; sy += k * wy; sz += k * wz; if (!pass) ctl.stats.clamped++; }
                }
                cur[x] = Rt[x] + sx; cur[x + 1] = Rt[x + 1] + sy; cur[x + 2] = Rt[x + 2] + sz;
            }
        }
    }
    function weldAll(withPrev) {
        for (let i = 0; i < nAll; i++) if (slaveOf[i] >= 0) {
            const a = 3 * slaveOf[i], x = 3 * i;
            cur[x] = cur[a]; cur[x + 1] = cur[a + 1]; cur[x + 2] = cur[a + 2];
            if (withPrev) { prev[x] = prev[a]; prev[x + 1] = prev[a + 1]; prev[x + 2] = prev[a + 2]; }
        }
    }
    const wv = [0, 0, 0];
    // (11-18) the links' stiffness at THIS step (the hair's m4 rule): 1 - (1 - k)^(h / H) relaxes a soft link as far in a
    // second at any step as k does at the spec's substep; a full link (k = 1) stays full
    const EKh = new Float64Array(nE);
    let EKfor = -1;
    function linkStiffness(h) {
        if (EKfor === h) return;
        const same = Math.abs(h - H) < 1e-9;
        for (let e = 0; e < nE; e++) EKh[e] = same || EK[e] >= 1 ? EK[e] : 1 - Math.pow(1 - EK[e], h / H);
        EKfor = h;
    }
    // (11-18) WHAT THE DAMPING IS TAKEN AGAINST (params.damp_against: 'pose' = a coat's default, 'world' = the first form and
    // the hair's cages without `dyn`). A film's own friction is against the body it hangs from, not against the world: damped
    // against the world, a skirt on a figure that walks at 1.5 m/s stood behind its hanging pose for as long as she walked
    // (damping x 12.5 mm a substep over omega2 h2: 20 cm at the hem; the hair round measured the same fault on her hair, 94
    // mm, and cured it so: its motion_NOTES m4). The world's share is the AIR's (params.air: a push by the speed through it).
    const POSE_DAMP = (P.damp_against ?? (hairMode ? 'world' : 'pose')) === 'pose';
    const LEE = P.air_lee ?? 1.0;                           // the air's push on a sheet from its INSIDE (through her): a share
    const outSign = new Float64Array(nAll).fill(1);         // +1 / -1: the cage's normal (across x down) x this = outward
    groups.forEach((G) => { const s = G.g.normal_sign ?? 1; for (let q = 0; q < G.n; q++) outSign[G.base + q] = s; });
    function substep(h, f, t, inv, doCollide = true, skipTier1 = false) {
        const damp = 1 - Math.pow(1 - (P.damping ?? 0.03), h / H);
        const driveH = 1 - Math.pow(1 - (P.drive ?? 0.02), h / H);
        const air = P.air ?? 0, vmax = (P.vmax ?? 0) * h;
        const pd = POSE_DAMP ? inv : 0;
        linkStiffness(h);
        for (let x = 0; x < 3 * nAll; x++) { Rt[x] = R0[x] + (R1[x] - R0[x]) * f; Tt[x] = T0[x] + (T1[x] - T0[x]) * f; }
        for (const c of car) {
            c.Kp.set(c.K);
            for (let e = 0; e < 16; e++) c.K[e] = c.K0[e] + (c.K1[e] - c.K0[e]) * f;
            invRigid(c.K, c.Ki);
        }
        // (the hair's gravity: the CHANGE of gravity in the parent's frame; a coat's gravity is its plumb target)
        let gx = 0, gy = 0, gz = 0;
        if (hairMode && (P.gravity ?? 1.0) > 0) {
            const K = car[parentIdx].K;
            mb.set(K[0], K[4], K[8], 0, K[1], K[5], K[9], 0, K[2], K[6], K[10], 0, 0, 0, 0, 1);
            acc.copy(gRest).applyMatrix4(mb).normalize();
            acc.subVectors(down, acc).multiplyScalar(9.81 * (P.gravity ?? 1.0) * h * h);
            gx = acc.x; gy = acc.y; gz = acc.z;
        }
        for (let i = 0; i < nAll; i++) {
            const x = 3 * i;
            if (pinned[i]) { for (let a = 0; a < 3; a++) { cur[x + a] = Rt[x + a]; prev[x + a] = Rt[x + a]; } continue; }
            if (slaveOf[i] >= 0) continue;
            // the pose's own move in this substep (dT): the damping acts on the particle's speed against it
            const dTx = (T1[x] - T0[x]) * pd, dTy = (T1[x + 1] - T0[x + 1]) * pd, dTz = (T1[x + 2] - T0[x + 2]) * pd;
            let vx = dTx + (cur[x] - prev[x] - dTx) * (1 - damp), vy = dTy + (cur[x + 1] - prev[x + 1] - dTy) * (1 - damp),
                vz = dTz + (cur[x + 2] - prev[x + 2] - dTz) * (1 - damp);
            if (vmax > 0) {
                // (the speed cap is on the speed against the pose's own: a figure that runs is not capped)
                const ux = vx - dTx, uy = vy - dTy, uz = vz - dTz, sp2 = ux * ux + uy * uy + uz * uz;
                if (sp2 > vmax * vmax) { const k = vmax / Math.sqrt(sp2); vx = dTx + ux * k; vy = dTy + uy * k; vz = dTz + uz * k; }
            }
            let fx = gx, fy = gy, fz = gz;
            if (air > 0) {
                // the air on the sheet: along its normal, by the square of the air's speed against it; air that would
                // have to come THROUGH HER to push the sheet from its inside pushes with a share (params.air_lee: the back
                // of a coat walks in her wake; a wind from behind presses the back on and leaves the fronts in her lee)
                wind(i, t, wv);
                const n0 = nrm[x], n1 = nrm[x + 1], n2 = nrm[x + 2];
                const vn = (wv[0] - vx / h) * n0 + (wv[1] - vy / h) * n1 + (wv[2] - vz / h) * n2;
                const a = air * (vn * outSign[i] > 0 ? LEE : 1) * vn * Math.abs(vn) * h * h;
                // (never more than stops the sheet against the air in this substep)
                const lim = Math.abs(vn) * h, aa = Math.abs(a) > lim ? Math.sign(a) * lim : a;
                fx += aa * n0; fy += aa * n1; fz += aa * n2;
            }
            prev[x] = cur[x]; prev[x + 1] = cur[x + 1]; prev[x + 2] = cur[x + 2];
            cur[x] += vx + fx; cur[x + 1] += vy + fy; cur[x + 2] += vz + fz;
            const dr = omega2[i] >= 0 ? Math.min(0.5, omega2[i] * h * h) : driveH;
            cur[x] += (Tt[x] - cur[x]) * dr; cur[x + 1] += (Tt[x + 1] - cur[x + 1]) * dr; cur[x + 2] += (Tt[x + 2] - cur[x + 2]) * dr;
        }
        const its = P.iterations ?? 3;
        for (let it = 0; it < its; it++) projectLinks();
        clampReach();
        // (params.collide_passes: a probe's push moves its cell's four joints, which its neighbours' probes share: a second
        // round settles what the first left between them. params.collide_every n: her colliders are met on every n th
        // substep and always on a frame's last: what a frame shows is clear of her; between, the links alone hold the sheet)
        if (doCollide) {
            const c0 = now();
            for (let cp = 0; cp < CPASS; cp++) { if (anyProbes) turns(); collide(skipTier1); }
            ctl.stats.msCollide += now() - c0;              // (her colliders' share of the step's cost: ctl.stats.msCollide / steps)
        }
        weldAll(true);
    }
    // the hair's host colliders (ctl.colliders: { object, grid }, phi in the object's own units), as the hair steps them
    function collideHost(f) {
        for (const C of ctl.colliders) {
            const m0 = C.M0 || C.M1, m1 = C.M1;
            if (!C._m) { C._m = new THREE.Matrix4(); C._i = new THREE.Matrix4(); }
            for (let e = 0; e < 16; e++) C._m.elements[e] = m0.elements[e] + (m1.elements[e] - m0.elements[e]) * f;
            C._i.copy(C._m).invert();
            for (let i = 0; i < nAll; i++) {
                if (pinned[i] || slaveOf[i] >= 0 || !collides[i]) continue;
                v3.set(cur[3 * i], cur[3 * i + 1], cur[3 * i + 2]).applyMatrix4(C._i);
                const d = C.grid.sample(v3.x, v3.y, v3.z, gvec);
                if (d >= clearP[i]) continue;
                const gl = Math.hypot(gvec[0], gvec[1], gvec[2]) || 1, push = clearP[i] - d;
                v3.x += gvec[0] / gl * push; v3.y += gvec[1] / gl * push; v3.z += gvec[2] / gl * push;
                v3.applyMatrix4(C._m);
                cur[3 * i] = v3.x; cur[3 * i + 1] = v3.y; cur[3 * i + 2] = v3.z;
                ctl.stats.pushes++;
            }
        }
    }
    const pM = new THREE.Matrix4(), pMi = new THREE.Matrix4(), bM = new THREE.Matrix4(), one = new THREE.Vector3(1, 1, 1), bP = new THREE.Vector3(),
        bS = new THREE.Vector3(), bS2 = new THREE.Vector3(), pQi = new THREE.Quaternion();
    function writeBones() {
        // each free particle's joint: its world place and the cage's turn against its rest; into ctl.jointWorld and,
        // when the joint exists as a bone, into the bone (its local place and turn under its own parent)
        let mv = 0, lastParent = null, parentRigid = true;
        const out = ctl.jointWorld;
        turns();
        for (const G of groups) {
            const g = G.g;
            for (let j = 0; j < g.cols; j++) for (let k = 0; k < g.rows; k++) {
                const i = G.base + G.idx(j, k);
                qa.set(TQ[4 * i], TQ[4 * i + 1], TQ[4 * i + 2], TQ[4 * i + 3]);
                out[7 * i] = cur[3 * i]; out[7 * i + 1] = cur[3 * i + 1]; out[7 * i + 2] = cur[3 * i + 2];
                out[7 * i + 3] = qa.x; out[7 * i + 4] = qa.y; out[7 * i + 5] = qa.z; out[7 * i + 6] = qa.w;
                const d = Math.hypot(cur[3 * i] - T1[3 * i], cur[3 * i + 1] - T1[3 * i + 1], cur[3 * i + 2] - T1[3 * i + 2]);
                if (d > mv) mv = d;
                const b = boneOf[i];
                if (!b) continue;
                bP.set(cur[3 * i], cur[3 * i + 1], cur[3 * i + 2]);
                if (b.parent) {
                    // (11-18: the parent's inverse once a frame and a parent, not once a joint: the spring joints of a coat
                    // all hang under one node; with an invert and a decompose a joint this took 0.44 ms of a 2.5 ms step)
                    if (b.parent !== lastParent) {
                        lastParent = b.parent;
                        pMi.copy(b.parent.matrixWorld).invert();
                        pMi.decompose(bS2, pQi, bS);
                        parentRigid = Math.abs(bS.x - 1) < 1e-5 && Math.abs(bS.y - 1) < 1e-5 && Math.abs(bS.z - 1) < 1e-5;
                    }
                    if (parentRigid) { b.position.copy(bP).applyMatrix4(pMi); b.quaternion.multiplyQuaternions(pQi, qa); }
                    else { bM.compose(bP, qa, one); pM.multiplyMatrices(pMi, bM); pM.decompose(b.position, b.quaternion, bS); }
                } else { b.position.copy(bP); b.quaternion.copy(qa); }
                // (the joint's matrices are its scene's to update, as every other joint's: three does it before it draws; a
                // host that reads these joints' world matrices before its render sets params.syncWorld)
                if (P.syncWorld) { b.updateMatrix(); b.matrixWorld.compose(bP, qa, one); }
            }
        }
        ctl.stats.maxMoveFrame = mv;
        ctl.stats.maxMove = Math.max(ctl.stats.maxMove, mv);
    }
    // a joint's own place at the stand (the origin of its inverse bind's inverse): where a capsule's end sits
    for (const c of car) {
        const m = new THREE.Matrix4().copy(c.inverse).invert();
        c.home = [m.elements[12], m.elements[13], m.elements[14]];
    }
    ctl.reset = () => { reset(); normals(); writeBones(); last = null; };
    ctl.step = (t) => {
        // once per rendered frame, after the creature's pose: t in seconds. A first call, a step back or a jump over
        // params.maxGap s puts the cage at its target pose
        if (!ctl.enabled) return;
        const t0 = now();
        ctl.stats.frames++;
        if (last === null || !(t > last) || t - last > (P.maxGap ?? 0.25)) {
            reset();
            last = t; tNow = t;
            normals();
            writeBones();
            return;
        }
        const dt = t - last;
        last = t;
        for (const c of car) c.K0.set(c.K1);
        R0.set(R1); T0.set(T1);
        readCarriers();
        targets(R1, T1);
        const t1 = now();
        ctl.stats.msRead += t1 - t0;                         // (where a step's time goes: reading her joints ...
        // (the hair's host colliders: each keeps its own two matrices; nothing is made in a step)
        for (const C of ctl.colliders) {
            C.object.updateWorldMatrix?.(true, false);
            if (!C.M1 || C.M1 === C.M0) C.M1 = new THREE.Matrix4();
            C.M1.copy(C.object.matrixWorld);
        }
        normals();
        candidates();
        const n = Math.max(1, Math.round(dt / H));
        const every = P.collide_every ?? 1;
        for (let s = 1; s <= n; s++) {
            substep(dt / n, s / n, tNow + dt * s / n, 1 / n, s === n || (n - s) % every === 0, TIERS && (n - s) % 2 === 1);
            if (ctl.colliders.length) collideHost(s / n);
        }
        for (const C of ctl.colliders) { if (C.M0) C.M0.copy(C.M1); else C.M0 = C.M1.clone(); }
        tNow = t;
        const t2 = now();
        writeBones();
        ctl.stats.msBones += now() - t2;                     // ... writing its joints; msCollide: her colliders; the rest: the cage)
        const ms = now() - t0;
        ctl.stats.msSum += ms; ctl.stats.steps++; ctl.stats.ms = ctl.stats.msSum / ctl.stats.steps;
    };
    // the particles as they stand (world): for the review pictures and the replay; the pose each is pulled to (world)
    ctl.particles = () => cur;
    ctl.targets = () => T1;
    // THE CAGE AGAINST HER, as it stands at the end of a step (for the tuning runs: never called by a film): every collision
    // sample's distance to her grids and capsules less its own clearance; { under: samples nearer than their clearance,
    // inside: samples inside her, deepest: the least distance (m), by: [sample index, particles, collider] of the deepest }
    ctl.audit = () => {
        const out = { under: 0, inside: 0, deepest: 1e3, by: null };
        if (!nS) return out;
        capsuleEnds(true);
        for (let k = 0; k < nD; k++) { const c = car[sdfs[k].car]; invRigid(c.K1, c.Ki); }
        for (let s = 0; s < nS; s++) {
            const n = SN[s];
            samplePos(s);
            const x = sp[0], y = sp[1], z = sp[2];
            let d = 1e3, who = null;
            for (let k = 0; k < nD; k++) {
                const sd = sdfs[k], c = car[sd.car];
                mulPoint(c.Ki, x, y, z, tp, 0);
                const v = sd.grid.sample(tp[0], tp[1], tp[2], null);
                if (v < d) { d = v; who = sd.name; }
            }
            for (let c = 0; c < nC; c++) {
                const a = 3 * c, ex = capB[a] - capA[a], ey = capB[a + 1] - capA[a + 1], ez = capB[a + 2] - capA[a + 2];
                const l2 = ex * ex + ey * ey + ez * ez || 1e-12;
                let t = ((x - capA[a]) * ex + (y - capA[a + 1]) * ey + (z - capA[a + 2]) * ez) / l2;
                t = t < 0 ? 0 : t > 1 ? 1 : t;
                const px = x - (capA[a] + t * ex), py = y - (capA[a + 1] + t * ey), pz = z - (capA[a + 2] + t * ez);
                const v = Math.sqrt(px * px + py * py + pz * pz) - (caps[c].ra + (caps[c].rb - caps[c].ra) * t);
                if (v < d) { d = v; who = caps[c].name; }
            }
            if (d < SC[s] - 1e-4) out.under++;
            if (d < 0) out.inside++;
            if (d < out.deepest) { out.deepest = d; out.by = [s, n, who]; }
        }
        return out;
    };
    ctl.layout = () => ({ n: nAll, groups: groups.map((G) => ({ name: G.g.name, base: G.base, cols: G.g.cols, rows: G.g.rows })), joints: jointName, links: nE, samples: nS,
        sdf: sdfs.map((s) => s.name), capsules: caps.map((c) => c.name), carriers: car.map((c) => c.name) });
    // a line drawing of the cages (world), for the review pictures: links as segments, refreshed by each render
    ctl.helper = (color = 0xff3060) => {
        const segs = [];
        for (let e = 0; e < nE; e++) if (eK[e] >= Math.min(P.lateral ?? 0.5, P.stretch ?? 1.0) - 1e-9) segs.push(eA[e], eB[e]);
        const geo = new THREE.BufferGeometry();
        const pos = new Float32Array(segs.length * 3);
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        const line = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true }));
        line.renderOrder = 999;
        line.frustumCulled = false;
        line.onBeforeRender = () => {
            for (let s = 0; s < segs.length; s++) for (let a = 0; a < 3; a++) pos[3 * s + a] = cur[3 * segs[s] + a];
            geo.attributes.position.needsUpdate = true;
        };
        return line;
    };
    reset();
    normals();
    writeBones();
    return ctl;
}
