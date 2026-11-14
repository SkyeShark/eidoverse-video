// cyborg_cable.js — THE HOSE AS A SKIN-RIDING CABLE (the lead's C5d call 2: work/bestiary/patches/cyborg_c5d_bestiary.md;
// C5e: work/bestiary/patches/cyborg_c5e_bestiary.md).
// C5c drew the hose exactly in one reference pose and skinned its rigid rings linearly: through the swim the arm's root
// left it (rings 0.14-0.27 mm into the skin, pads 0.45 mm in, the rings tilted 35-41 deg off the tube). Here the hose is
// re-made every frame from the creature's RENDERED skin, as data the forge builds per seed (forge/cyborg_cable.py: the
// hose glb's extras bestiary.cable):
//   ANCHORS   skin points: a triangle of the skin's vertex set and its barycentrics; each frame its three corners come
//             from the skin's own skinning (three's SkinnedMesh.applyBoneTransform, term by term, on the bones' skin
//             matrices computed once per frame: C5e), giving the point, the skin's smooth normal there (its corners'
//             skinned normals blended) and a frame (e1 the triangle's first edge made normal to it, e2 = n x e1)
//   LYING     every ring that lies on the skin (the lying runs and the ramps into the pads) rides one anchor, its FOOT:
//             its centre on the foot's normal at the lowest height that clears the foot and its LIPS (the skin points
//             round its lower half at rest, anchored the same way) by r + clearance, plus its rest lift over that height
//             (contactRings); each run then laid at its rings' rest arc fractions along its anchors (relay), and by each
//             clamp its ramp re-drawn as the Hermite between its held ends plus its rest detail, never under the skin
//   RIGID     the rings inside the plate fitting (the skin matrix blend of its site, as three skins the fitting), inside
//             the port (bone 7's, as the tentacle) and in each clamp (the CLAMP FRAME: the rigid motion that best carries
//             the anchors under its pad's underside from their rest places, Kabsch by polar decomposition, then seated,
//             C5e: moved along its normal to the middle of the skin's height changes under it, so the rigid pad's lift
//             and press are equal); the anchored rings either side of a clamp drawn toward where its frame carries them
//             (the blend), their contact floor fading by the blend weight (at the face a ring follows the pad into the
//             flesh it presses)
//   FREE      C5e: the arches, the humps, the descent from the plate fitting and the rise into the port are each an
//             INEXTENSIBLE ROD (rodSolve): NR equal segments of its rest arc length between its two end rings, leaving and
//             entering along the ends' tangents, at the least bending energy sum l w(k^2) (w(q) = q + rref^10 q^6: the
//             elastica's, steep past ROD.rref so a tight bend spreads), held clear of the skin points under its rings and
//             of the flange's pieces (each bound a plane through its point, a stiff penalty past its clearance), and
//             tethered to its REST SHAPE carried by its ends (the forge's rest centreline in the frame of its chord and its
//             ends' up axes): one deterministic solution per frame from that shape (Newton on the augmented Lagrangian,
//             banded Cholesky), so no mirror flip, no lean axis to wrap, no history. The tether is weak along the chord and
//             up, firm ACROSS it for the arches and the humps: an arch turns about its chord for nothing (it keeps the
//             rest side's lean), a hump lifts rather than swinging sideways. A span the skin pulls taut BORROWS hose from
//             the lying run it lands on (borrowEval: the run slides that much into it), so it keeps its rest length
//   FRAMES    rotation-minimising (double reflection) along the centre curve from the plate fitting's reference axis;
//             each ring's plane normal to the centre curve's central difference there: no tilt by construction
//   PADS      C5e: every pad vertex RIGID in its clamp frame (C5d anchored its underside on the skin, and the swim
//             shortened pad 1 by 11-18 %); the straps and rivets rigid in the clamp frame over the tube
// One update() per frame, after the bones are posed and the group's matrices updated: positions in the skin mesh's
// local space (the creature's group). No allocation per frame. A frame whose bones are all where the last one had them
// re-uses the last result (the output is a function of the pose alone: history-free).
const THREE = globalThis.THREE;

const NS = 64;                     // the initial guess's Hermite samples (a span without its rest shape: the bow guess)
const FAIR_CLEAR = 0.05e-3;        // a faired ring (by a clamp: relay's fairStretch) kept this far over its contact
const RUN_SMOOTH = 1;              // a lying run's control points smoothed this many times ([1 2 1] / 4; the ends held)
// C5e: the free spans' ROD (rodSolve), in mm inside the solve (ROD's keys; opts.rod overrides any of them)
const ROD = {
    step: 1.0,                     // mm: a span's segments at most this long (NR = ceil(L0 / step), within 16..72)
    rref: 10.0,                    // mm: the bending energy steep past this radius (w(q) = q + rref^(2 pow - 2) q^pow)
    pow: 6,                        // its steep term's power of the curvature squared (the larger, the nearer the curve of the
                                   // least largest curvature: 4 bent the swim's arch 1 to 6.60 mm, 6 to 6.82, s06)
    rho: 2.0e4,                    // the augmented Lagrangian's weight on the segments' lengths (2e3 took the swim's arch
                                   // 86 Newton steps a frame on average, 2e4 54, the same curve: s06)
    nu: 2.0e4,                     // the bounds' clearance penalty
    margin: 0.02,                  // mm: each bound aimed this far past its clearance (the penalty's give)
    outer: 8, inner: 12,           // multiplier updates, Newton steps per update
    tol: 2.0e-5,                   // a segment's length within this share of its rest length (2e-4 gave the arch the same
                                   // curve but the rise and the humps 0.4-0.6 mm one-frame jitter in the swim, s07)
    dtol: 1.0e-6,                  // mm: a Newton step this small ends the inner loop
    exact: false,                  // the length terms' curvature kept where compressive (a raised diagonal if it fails)
    latfix: 0,                     // the rest shape's sideways line bent to the ends' sideways directions now: 0 none (the
                                   // rest line, carried by the ends), 1 by their slopes, 2 by their unit tangents' sideways
                                   // parts (2 put a 0.57 mm one-frame step into seed 4's hump at its lift's onset, s07)
    slack: 0.004,                  // a span whose ends the skin carries apart keeps at least this share of slack: the
                                   // lying run it lands on SLIDES that much hose into it (borrow); the descent and the
                                   // rise (model 'hermite') keep their REST slack (rest_d): pulled taut on 0.4 % the
                                   // swim's descent turned off the plate fitting in 7.0 mm, s06
    slackRest: { hermite: 1.0, hump: 0.0, arch: 0.0 },   // the share of its rest slack a span of each model keeps
    borrowMax: 0.15,               // at most this share of its rest length borrowed
    // the tether to the rest shape per span model, along (the chord, up, across): weak along and up (a tie-break, the
    // branch), firm ACROSS for the arches and the humps: an arch clamped along its chord turns about it for nothing (with
    // 1e-4 across the swim's arch 1 crept 15 mm sideways between a solve and one with 4x its budget, s05; with 1e-2 seed
    // 9's arch still flipped from leaning 6.8 mm one way to 3.7 the other in one frame, four times a swim; with 0.3 it
    // holds its plane on every seed, its crest moving at most 0.02 mm a frame sideways, at 0.04-0.3 mm tighter bends, s07),
    // and a hump lifts rather than swinging sideways
    tether: { arch: [1.0e-4, 1.0e-4, 0.3], hump: [1.0e-4, 1.0e-4, 2.0e-2], hermite: [1.0e-3, 1.0e-3, 1.0e-3] },
};
const PAD_SEAT = 0.12e-3;          // the pads' underside this far over the skin at rest (forge/cyborg_pads.py PAD seat)
const HB = 8;                      // the Hessian's half bandwidth (a bend couples nodes two apart: 3 x 2 + 2)
const NB_BORROW = 12;              // at most this many lying rings borrowed at each end of a span (C5f: 6 -> 12, room for
                                   // a run's lend as well as a taut span's borrow)
const LEND_MAX = 0.25;             // C5f (the lead's call 8): a lying run lends a hump at most this share of its rest length
const LEND_EPS = 1.0e-6;           // m: a run shortened by less lends nothing (its rest pose lays it exactly)
const SHADOW_H = 1.0e-3;           // C5f (the lead's call 9): the contact shadow's sweep toward the sun: what a rim of this
const SHADOW_MAX = 1.6e-3;         // height casts at the sun's elevation over the pad, at most this (m)
// STAGE 2B (work/bestiary/patches/landing2b_cable.md): a LYING ring never stands off the skin it lies on. Its rest lift
// (the forge's: its rest height less the point contact's) passes whole up to LIE_SOFT over the height at which it clears
// its foot's and lips' TRIANGLES by rho, and softly (tanh) never past LIE_MAX: so its ANCHORED centre (contactRings'
// output, relay's control point) stands at most rho - r + LIE_MAX (0.16 mm) off those triangles (the swim floated ride
// 0's end 0.30-0.52 mm, the bar 0.30). The DRAWN ring can stand a little higher: relay() re-lays the rings at their rest
// arc fractions along those control points, smoothed, ~1.6 mm along the hose in the swim; measured +0.184..+0.217 mm
// over the 16 swims (seed 9, frame 12, ring 237: +0.160 anchored, +0.214 drawn; the stage-2b check), not bounded in
// every pose by the cap alone
const LIE_SOFT = 0.06e-3;          // m
const LIE_MAX = 0.12e-3;           // m
const FAIR_LIFT_SMOOTH = 2;        // STAGE 2B: passes smoothing the fairing's floor lifts along a stretch (fairStretch)

function normalize3(a, o) {
    const l = Math.hypot(a[o], a[o + 1], a[o + 2]) || 1e-30;
    a[o] /= l; a[o + 1] /= l; a[o + 2] /= l;
}

function sweptExit(V, i0, i1, i2, bx, by, bz, nx, ny, nz, rho) {
    // STAGE 2B: where the line B + h n (n unit) LEAVES the triangle (V[i0..], V[i1..], V[i2..]: offsets into a flat xyz
    // array) swept by a ball of radius rho: the largest h at which the point is still within rho of the triangle (the
    // swept triangle is convex, so the line's part inside it is one interval and its end the largest of its parts'
    // ends: the slab over the face, the three edges' cylinders, the three corners' balls); -Infinity where the line
    // misses it
    let h = -Infinity;
    for (let q = 0; q < 3; q++) {
        // a corner's ball: |B + h n - P| = rho (the point contact's own root); (no array per call: the cable allocates
        // nothing per frame)
        const p = q === 0 ? i0 : q === 1 ? i1 : i2, e = q === 0 ? i1 : q === 1 ? i2 : i0;
        const dx = bx - V[p], dy = by - V[p + 1], dz = bz - V[p + 2];
        const dn = dx * nx + dy * ny + dz * nz;
        const disc = dn * dn - (dx * dx + dy * dy + dz * dz) + rho * rho;
        if (disc >= 0.0) h = Math.max(h, -dn + Math.sqrt(disc));
        // an edge's cylinder: |(B + h n - P) less its part along the edge u| = rho, within the edge's length
        let ux = V[e] - V[p], uy = V[e + 1] - V[p + 1], uz = V[e + 2] - V[p + 2];
        const L = Math.hypot(ux, uy, uz);
        if (L < 1e-12) continue;
        ux /= L; uy /= L; uz /= L;
        const nu = nx * ux + ny * uy + nz * uz, wu = dx * ux + dy * uy + dz * uz;
        const ax = nx - nu * ux, ay = ny - nu * uy, az = nz - nu * uz;
        const wx = dx - wu * ux, wy = dy - wu * uy, wz = dz - wu * uz;
        const aa = ax * ax + ay * ay + az * az;
        if (aa < 1e-12) continue;
        const ab = ax * wx + ay * wy + az * wz, d2 = ab * ab - aa * (wx * wx + wy * wy + wz * wz - rho * rho);
        if (d2 < 0.0) continue;
        const hc = (-ab + Math.sqrt(d2)) / aa, t = wu + hc * nu;
        if (t >= 0.0 && t <= L) h = Math.max(h, hc);
    }
    // the face's slab: its plane offset rho toward n, the point's foot inside the triangle
    const p0 = i0, p1 = i1, p2 = i2;
    const e1x = V[p1] - V[p0], e1y = V[p1 + 1] - V[p0 + 1], e1z = V[p1 + 2] - V[p0 + 2];
    const e2x = V[p2] - V[p0], e2y = V[p2 + 1] - V[p0 + 1], e2z = V[p2 + 2] - V[p0 + 2];
    let tx = e1y * e2z - e1z * e2y, ty = e1z * e2x - e1x * e2z, tz = e1x * e2y - e1y * e2x;
    const tl = Math.hypot(tx, ty, tz);
    if (tl < 1e-18) return h;
    tx /= tl; ty /= tl; tz /= tl;
    let den = nx * tx + ny * ty + nz * tz;
    if (den < 0.0) { tx = -tx; ty = -ty; tz = -tz; den = -den; }
    if (den < 1e-6) return h;
    const hs = (rho - ((bx - V[p0]) * tx + (by - V[p0 + 1]) * ty + (bz - V[p0 + 2]) * tz)) / den;
    // (the point there, its foot on the plane, its barycentrics by the edges' sides)
    const qx = bx + hs * nx - V[p0], qy = by + hs * ny - V[p0 + 1], qz = bz + hs * nz - V[p0 + 2];
    const d00 = e1x * e1x + e1y * e1y + e1z * e1z, d01 = e1x * e2x + e1y * e2y + e1z * e2z;
    const d11 = e2x * e2x + e2y * e2y + e2z * e2z;
    const d20 = qx * e1x + qy * e1y + qz * e1z, d21 = qx * e2x + qy * e2y + qz * e2z;
    const dd = d00 * d11 - d01 * d01;
    if (Math.abs(dd) < 1e-30) return h;
    const b1 = (d11 * d20 - d01 * d21) / dd, b2 = (d00 * d21 - d01 * d20) / dd;
    if (b1 >= 0.0 && b2 >= 0.0 && b1 + b2 <= 1.0) h = Math.max(h, hs);
    return h;
}

export function mountCable(data, skin, bones, opts = {}) {
    // data: the hose glb's extras bestiary.cable; skin: a SkinnedMesh of the creature's skin vertex set (the anchors'
    // indices); bones: the creature's Map name -> Bone; opts.debug: keep the anchored rings' centres before and after
    // the clamps' blend (the cable's debug); opts.profile: per-phase timings in stats.phase; opts.rod: any of ROD's keys.
    // Returns the cable (its arrays are the meshes' attributes)
    const D = data;
    const RO = Object.assign({}, ROD, opts.rod || {});
    RO.tether = Object.assign({}, ROD.tether, (opts.rod || {}).tether || {});
    const N = D.rings, S = D.sides, nc = S + 1, r = D.r;
    const RR = D.ring_r || null;                          // C5f: each ring's radius where a convoluted section has its own
    const DBG = opts.debug ? { anch: new Float64Array(3 * N), blend: new Float64Array(3 * N) } : null;
    const nv = D.skin_verts.length, na = D.anchors.length / 6;
    const SV = new Float64Array(3 * nv);                  // the skinned skin vertices the anchors read
    const AP = new Float64Array(3 * na), AE1 = new Float64Array(3 * na), AN = new Float64Array(3 * na),
        AE2 = new Float64Array(3 * na);
    const C = new Float64Array(3 * N);                    // the ring centres
    const T = new Float64Array(3 * N), E1 = new Float64Array(3 * N), E2 = new Float64Array(3 * N);
    const sleevePos = new Float32Array(3 * N * nc), sleeveNrm = new Float32Array(3 * N * nc),
        sleeveTan = new Float32Array(4 * N * nc);
    const np_ = D.pads ? D.pads.n : 0;
    const padPos = new Float32Array(3 * np_), padNrm = new Float32Array(3 * np_), padTan = new Float32Array(4 * np_);
    const v = new THREE.Vector3(), mA = new THREE.Matrix4();
    const COS = Float64Array.from({ length: nc }, (_, j) => Math.cos((2.0 * Math.PI * j) / S));
    const SIN = Float64Array.from({ length: nc }, (_, j) => Math.sin((2.0 * Math.PI * j) / S));
    const gInv = new THREE.Matrix4();
    // the frames: their bones resolved once; each frame's matrix (column-major, three's) refreshed every update
    const frames = D.frames.map((f) => {
        const o = { kind: f.kind, M: new THREE.Matrix4(), e: null };
        if (f.kind === 'bone' || f.kind === 'blend') {
            const names = f.kind === 'bone' ? [f.bone] : f.bones;
            o.bones = names.map((nm) => {
                const b = bones.get(nm);
                if (!b) throw new Error(`[cable] no bone ${nm} on this creature`);
                const k = skin.skeleton.bones.indexOf(b);
                if (k < 0) throw new Error(`[cable] bone ${nm} is not in the skin's skeleton`);
                return { b, inv: skin.skeleton.boneInverses[k] };
            });
            o.w = f.kind === 'bone' ? [1.0] : f.w;
        } else {
            o.anchors = f.anchors;
            o.loc = f.loc;
        }
        o.blend = [];
        return o;
    });
    for (const b of D.ring_blend || []) frames[b[1]].blend.push(b);
    const fe = (f) => frames[f].M.elements;
    const stats = { ms: 0.0, frames: 0, maxMs: 0.0, taut: 0, lifted: 0, reused: 0, newton: 0, stretch: 0.0,
        phase: opts.profile ? { skin: 0, anchors: 0, contact: 0, frames: 0, fixed: 0, spans: 0, rings: 0, pads: 0 } : null };

    // ------------------------------------------------------------------ the skin (C5e: the bones' matrices once a frame)
    const SN = new Float64Array(3 * nv);
    const pA = skin.geometry.attributes.position, nrmA = skin.geometry.attributes.normal,
        siA = skin.geometry.attributes.skinIndex, swA = skin.geometry.attributes.skinWeight;
    const sbones = skin.skeleton.bones, sinv = skin.skeleton.boneInverses;
    // the bones the skin vertices read, each one's skin matrix (bone.matrixWorld x its inverse bind) per frame
    const used = new Map();
    const VI = new Int32Array(4 * nv), VW = new Float64Array(4 * nv), VB = new Float64Array(3 * nv),
        VN = new Float64Array(3 * nv);
    for (let q = 0; q < nv; q++) {
        const i = D.skin_verts[q];
        VB[3 * q] = pA.getX(i); VB[3 * q + 1] = pA.getY(i); VB[3 * q + 2] = pA.getZ(i);
        VN[3 * q] = nrmA.getX(i); VN[3 * q + 1] = nrmA.getY(i); VN[3 * q + 2] = nrmA.getZ(i);
        for (let c = 0; c < 4; c++) {
            const w = swA.getComponent(i, c);
            VW[4 * q + c] = w;
            if (w === 0) { VI[4 * q + c] = -1; continue; }
            const k = siA.getComponent(i, c);
            if (!used.has(k)) used.set(k, used.size);
            VI[4 * q + c] = used.get(k);
        }
    }
    const UB = Array.from(used.keys());                   // slot -> bone index
    const BM = new Float64Array(16 * UB.length);          // the slots' skin matrices this frame
    const BW = new Float64Array(16 * sbones.length);      // every bone's matrixWorld at the last update (the reuse test)
    let haveLast = false;
    const morph = !!(skin.morphTargetInfluences && skin.geometry.morphAttributes?.position);
    function skinVerts() {
        // each vertex the anchors read, as three skins it (SkinnedMesh.getVertexPosition: its base position by the bind
        // matrix, the weighted sum of the bones' skin matrices on it, the bind matrix's inverse; the same operations in
        // the same order on the same matrices, computed once per bone instead of once per vertex and weight); its
        // normal as three's SkinningNode turns it (the blended skin matrices' linear part, then the bind matrix's
        // inverse), unit. A skin with morph targets: three's own getVertexPosition
        for (let s = 0; s < UB.length; s++) {
            mA.multiplyMatrices(sbones[UB[s]].matrixWorld, sinv[UB[s]]);
            BM.set(mA.elements, 16 * s);
        }
        const bm = skin.bindMatrix.elements, bi = skin.bindMatrixInverse.elements;
        for (let q = 0; q < nv; q++) {
            let x0, y0, z0;
            if (morph) {
                skin.getVertexPosition(D.skin_verts[q], v);
                SV[3 * q] = v.x; SV[3 * q + 1] = v.y; SV[3 * q + 2] = v.z;
            } else {
                // _basePosition.copy(target).applyMatrix4(bindMatrix)
                const px = VB[3 * q], py = VB[3 * q + 1], pz = VB[3 * q + 2];
                let w_ = 1 / (bm[3] * px + bm[7] * py + bm[11] * pz + bm[15]);
                x0 = (bm[0] * px + bm[4] * py + bm[8] * pz + bm[12]) * w_;
                y0 = (bm[1] * px + bm[5] * py + bm[9] * pz + bm[13]) * w_;
                z0 = (bm[2] * px + bm[6] * py + bm[10] * pz + bm[14]) * w_;
                let x = 0.0, y = 0.0, z = 0.0;
                for (let c = 0; c < 4; c++) {
                    const s = VI[4 * q + c];
                    if (s < 0) continue;
                    const e = BM, o = 16 * s, w = VW[4 * q + c];
                    // _vector3.copy(_basePosition).applyMatrix4(_matrix4), added scaled by the weight
                    const iw = 1 / (e[o + 3] * x0 + e[o + 7] * y0 + e[o + 11] * z0 + e[o + 15]);
                    x += ((e[o] * x0 + e[o + 4] * y0 + e[o + 8] * z0 + e[o + 12]) * iw) * w;
                    y += ((e[o + 1] * x0 + e[o + 5] * y0 + e[o + 9] * z0 + e[o + 13]) * iw) * w;
                    z += ((e[o + 2] * x0 + e[o + 6] * y0 + e[o + 10] * z0 + e[o + 14]) * iw) * w;
                }
                w_ = 1 / (bi[3] * x + bi[7] * y + bi[11] * z + bi[15]);
                SV[3 * q] = (bi[0] * x + bi[4] * y + bi[8] * z + bi[12]) * w_;
                SV[3 * q + 1] = (bi[1] * x + bi[5] * y + bi[9] * z + bi[13]) * w_;
                SV[3 * q + 2] = (bi[2] * x + bi[6] * y + bi[10] * z + bi[14]) * w_;
            }
            const n0 = VN[3 * q], n1 = VN[3 * q + 1], n2 = VN[3 * q + 2];
            let x = 0.0, y = 0.0, z = 0.0;
            for (let c = 0; c < 4; c++) {
                const s = VI[4 * q + c];
                if (s < 0) continue;
                const e = BM, o = 16 * s, w = VW[4 * q + c];
                x += w * (e[o] * n0 + e[o + 4] * n1 + e[o + 8] * n2);
                y += w * (e[o + 1] * n0 + e[o + 5] * n1 + e[o + 9] * n2);
                z += w * (e[o + 2] * n0 + e[o + 6] * n1 + e[o + 10] * n2);
            }
            SN[3 * q] = bi[0] * x + bi[4] * y + bi[8] * z;
            SN[3 * q + 1] = bi[1] * x + bi[5] * y + bi[9] * z;
            SN[3 * q + 2] = bi[2] * x + bi[6] * y + bi[10] * z;
            normalize3(SN, 3 * q);
        }
    }
    function samePose() {
        // C5e: every bone's world matrix as at the last update (a still pose: the last result stands)
        let same = haveLast;
        for (let k = 0; k < sbones.length; k++) {
            const e = sbones[k].matrixWorld.elements, o = 16 * k;
            for (let c = 0; c < 16; c++) {
                if (BW[o + c] !== e[c]) { same = false; BW[o + c] = e[c]; }
            }
        }
        haveLast = true;
        return same;
    }
    // which anchors need their frame (e1, e2): the rings' feet and the end tangents; the rest only their point and normal
    const needFrame = new Uint8Array(na);
    {
        const K = D.ring_kind, R0 = D.ring_ref;
        for (let i = 0; i < N; i++) if (K[i] === 1) needFrame[R0[i]] = 1;
        for (const s of D.spans || []) {
            for (const sp of [s.ta_spec, s.tb_spec]) if (sp[0] === 'anchor') needFrame[sp[1]] = 1;
        }
    }
    function anchorsEval() {
        // each anchor: its point (the barycentric blend of its corners), the skin's SMOOTH normal there (the corners'
        // normals blended, unit: neighbouring anchors on different triangles turn alike); for the anchors that carry
        // an offset, e1 its triangle's first edge made normal to it, e2 = n x e1
        const A = D.anchors;
        for (let a = 0; a < na; a++) {
            const i0 = 3 * A[6 * a], i1 = 3 * A[6 * a + 1], i2 = 3 * A[6 * a + 2];
            const b0 = A[6 * a + 3], b1 = A[6 * a + 4], b2 = A[6 * a + 5];
            const o = 3 * a;
            for (let c = 0; c < 3; c++) {
                AP[o + c] = b0 * SV[i0 + c] + b1 * SV[i1 + c] + b2 * SV[i2 + c];
                AN[o + c] = b0 * SN[i0 + c] + b1 * SN[i1 + c] + b2 * SN[i2 + c];
            }
            normalize3(AN, o);
            if (!needFrame[a]) continue;
            const ux = SV[i1] - SV[i0], uy = SV[i1 + 1] - SV[i0 + 1], uz = SV[i1 + 2] - SV[i0 + 2];
            const dn = ux * AN[o] + uy * AN[o + 1] + uz * AN[o + 2];
            AE1[o] = ux - dn * AN[o]; AE1[o + 1] = uy - dn * AN[o + 1]; AE1[o + 2] = uz - dn * AN[o + 2];
            normalize3(AE1, o);
            AE2[o] = AN[o + 1] * AE1[o + 2] - AN[o + 2] * AE1[o + 1];
            AE2[o + 1] = AN[o + 2] * AE1[o] - AN[o] * AE1[o + 2];
            AE2[o + 2] = AN[o] * AE1[o + 1] - AN[o + 1] * AE1[o];
        }
    }
    function framesEval() {
        // a bone or a blend: the skin matrix three applies (its bindMatrixInverse x sum w bone.matrixWorld x the
        // inverse bind; the hose's bind matrix is the identity, as the skin's); a clamp: its anchors' fit
        gInv.copy(skin.bindMatrixInverse);
        for (const f of frames) {
            const M = f.M;
            if (f.bones) {
                const e = M.elements;
                e.fill(0.0);
                for (let q = 0; q < f.bones.length; q++) {
                    mA.multiplyMatrices(f.bones[q].b.matrixWorld, f.bones[q].inv);
                    const a = mA.elements, w = f.w[q];
                    for (let c = 0; c < 16; c++) e[c] += w * a[c];
                }
                M.premultiply(gInv);
            } else {
                clampFit(f, M.elements);
            }
        }
    }
    const HM = new Float64Array(9), RK = new Float64Array(9), RI = new Float64Array(9);
    function clampFit(f, e) {
        // a CLAMP's frame: the rigid motion that best carries its underside anchors' rest places (f.loc, in the frame)
        // onto where the skin has them now (least squares, Kabsch): the cross-covariance H = sum (p - pm)(q - qm)^T,
        // its orthogonal polar factor R (Higham's Newton iteration R <- (R + R^-T) / 2), the origin pm - R qm
        const A = f.anchors, Lq = f.loc, n = A.length;
        let px = 0, py = 0, pz = 0, qx = 0, qy = 0, qz = 0;
        for (let i = 0; i < n; i++) {
            const a = 3 * A[i];
            px += AP[a]; py += AP[a + 1]; pz += AP[a + 2];
            qx += Lq[3 * i]; qy += Lq[3 * i + 1]; qz += Lq[3 * i + 2];
        }
        px /= n; py /= n; pz /= n; qx /= n; qy /= n; qz /= n;
        HM.fill(0.0);
        for (let i = 0; i < n; i++) {
            const a = 3 * A[i];
            const p0 = AP[a] - px, p1 = AP[a + 1] - py, p2 = AP[a + 2] - pz;
            const q0 = Lq[3 * i] - qx, q1 = Lq[3 * i + 1] - qy, q2 = Lq[3 * i + 2] - qz;
            HM[0] += p0 * q0; HM[1] += p0 * q1; HM[2] += p0 * q2;
            HM[3] += p1 * q0; HM[4] += p1 * q1; HM[5] += p1 * q2;
            HM[6] += p2 * q0; HM[7] += p2 * q1; HM[8] += p2 * q2;
        }
        let s = 0.0;
        for (let k = 0; k < 9; k++) s += HM[k] * HM[k];
        s = Math.sqrt(s / 3.0) || 1.0;
        for (let k = 0; k < 9; k++) RK[k] = HM[k] / s;
        for (let it = 0; it < 12; it++) {
            // R^-T: the cofactor matrix over the determinant
            const m = RK;
            const c00 = m[4] * m[8] - m[5] * m[7], c01 = m[5] * m[6] - m[3] * m[8], c02 = m[3] * m[7] - m[4] * m[6];
            const c10 = m[2] * m[7] - m[1] * m[8], c11 = m[0] * m[8] - m[2] * m[6], c12 = m[1] * m[6] - m[0] * m[7];
            const c20 = m[1] * m[5] - m[2] * m[4], c21 = m[2] * m[3] - m[0] * m[5], c22 = m[0] * m[4] - m[1] * m[3];
            const det = m[0] * c00 + m[1] * c01 + m[2] * c02;
            if (Math.abs(det) < 1e-30) break;
            RI[0] = c00 / det; RI[1] = c01 / det; RI[2] = c02 / det;
            RI[3] = c10 / det; RI[4] = c11 / det; RI[5] = c12 / det;
            RI[6] = c20 / det; RI[7] = c21 / det; RI[8] = c22 / det;
            let dmax = 0.0;
            for (let k = 0; k < 9; k++) {
                const v_ = 0.5 * (RK[k] + RI[k]);
                dmax = Math.max(dmax, Math.abs(v_ - RK[k]));
                RK[k] = v_;
            }
            if (dmax < 1e-13) break;
        }
        // (the underside is nearly flat, so the frame's y, across it, is the least determined axis: x and z taken from
        // the fit, y = z x x, a proper rotation whatever the patch's flatness)
        let xx = RK[0], xy = RK[3], xz = RK[6];
        let l = Math.hypot(xx, xy, xz) || 1.0;
        xx /= l; xy /= l; xz /= l;
        let zx = RK[2], zy = RK[5], zz = RK[8];
        const dz = zx * xx + zy * xy + zz * xz;
        zx -= dz * xx; zy -= dz * xy; zz -= dz * xz;
        l = Math.hypot(zx, zy, zz) || 1.0;
        zx /= l; zy /= l; zz /= l;
        const yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
        RK[0] = xx; RK[3] = xy; RK[6] = xz;
        RK[1] = yx; RK[4] = yy; RK[7] = yz;
        RK[2] = zx; RK[5] = zy; RK[8] = zz;
        // three's column-major: column c is the frame's axis c (RK row-major r, c)
        for (let c = 0; c < 3; c++) {
            e[4 * c] = RK[c]; e[4 * c + 1] = RK[3 + c]; e[4 * c + 2] = RK[6 + c]; e[4 * c + 3] = 0;
        }
        e[12] = px - (RK[0] * qx + RK[1] * qy + RK[2] * qz);
        e[13] = py - (RK[3] * qx + RK[4] * qy + RK[5] * qz);
        e[14] = pz - (RK[6] * qx + RK[7] * qy + RK[8] * qz);
        e[15] = 1;
        // then SEATED (C5e): moved along its y by the middle of the skin points' height changes under it in the frame (dy,
        // each point's height now less its rest height): the rigid pad's largest lift off the skin and its deepest press
        // into it are equal, each half the range of dy. C5d raised it to the highest point and then by its ramps' rings'
        // deficits: in the swim the rigid pad 1 stood up to 5.8 mm off the skin (the ramp raise 3.8 mm of it); on the
        // highest point alone it still floated 2.1 mm over the skin's low side. In the swim the skin under pad 1
        // deforms by up to ~2 mm (pad 2 ~1 mm), which no rigid pad follows (s18_seat.py). The ramps' rings by a clamp
        // follow it into the flesh it presses (ringsFixed's blend and relay's fairing: their contact floor fades by the
        // blend weight, none at the face); held at their contact the swim kinked ramp 1a to 22-25 deg (s19_variants.py)
        let dmax = -Infinity, dmin = Infinity;
        for (let i = 0; i < n; i++) {
            const a = 3 * A[i];
            const dy = (AP[a] - e[12]) * RK[1] + (AP[a + 1] - e[13]) * RK[4] + (AP[a + 2] - e[14]) * RK[7] - Lq[3 * i + 1];
            if (dy > dmax) dmax = dy;
            if (dy < dmin) dmin = dy;
        }
        const rise = 0.5 * (dmax + dmin);
        e[12] += rise * RK[1]; e[13] += rise * RK[4]; e[14] += rise * RK[7];
        f.rise = rise;
        // (the pad's underside against the skin points under it, the designed seat gap PAD_SEAT apart: its largest lift
        // off them and its deepest press into them, m)
        f.lift = PAD_SEAT + rise - dmin;
        f.press = dmax - rise - PAD_SEAT;
    }
    // a point / a direction (unit) of frame f's local coordinates
    const fpoint = (f, x, y, z, out, o) => {
        const e = fe(f);
        out[o] = e[0] * x + e[4] * y + e[8] * z + e[12];
        out[o + 1] = e[1] * x + e[5] * y + e[9] * z + e[13];
        out[o + 2] = e[2] * x + e[6] * y + e[10] * z + e[14];
    };
    const fdir = (f, x, y, z, out, o) => {
        const e = fe(f);
        out[o] = e[0] * x + e[4] * y + e[8] * z;
        out[o + 1] = e[1] * x + e[5] * y + e[9] * z;
        out[o + 2] = e[2] * x + e[6] * y + e[10] * z;
        normalize3(out, o);
    };
    const anchored = (a, dx, dn, dz, out, o) => {
        const q = 3 * a;
        for (let c = 0; c < 3; c++) out[o + c] = AP[q + c] + dx * AE1[q + c] + dn * AN[q + c] + dz * AE2[q + c];
    };
    const bq = new Float64Array(3);
    const R_ = D.ring_ref;
    const CS = D.ring_contact_start, CL = D.ring_contact, LIFT = D.ring_lift, RHO = D.rho;
    const CC = new Float64Array(3 * N);                   // each anchored ring's contact centre (its lift apart)
    const BWR = new Float64Array(N);                      // each ring's clamp blend weight (0 off the clamps' blends)
    for (const b of D.ring_blend || []) BWR[b[0]] = Math.max(BWR[b[0]], b[5]);
    const A6 = D.anchors, FAIR0 = D.ring_fair;            // (STAGE 2B: the anchors' triangles; the faired rings)
    // STAGE 3: LIE_MAX caps a line with pads, the hose. A feed line's rest lifts alternate in sign over its contact points:
    // capping only the upward ones lowers the mean relay() smooths, and line 0's ring 22 sank -0.075 mm (c03d K3 / K4)
    const LIE_CAP = !!D.pads;
    let held = 0;
    function contactRings() {
        // every ANCHORED ring's centre (C5d s22): from its foot (its anchor and its rest offsets across the normal) along
        // the foot's normal, at the lowest height that clears its foot and each of its lips (the skin points round its
        // lower half at rest, anchored) by rho: for a point p the height h must keep |B + h n - p| >= rho, i.e. h past
        // the larger root of h^2 + 2 h (d.n) + |d|^2 - rho^2 (d = B - p); then its rest lift over that height. A crease
        // the rest pose drew a ring over that opens lets it down onto the floor; one that closes lifts it (a glb
        // without the contact data: the rest offset, as before)
        const K = D.ring_kind, L = D.ring_loc;
        held = 0;
        for (let i = 0; i < N; i++) {
            if (K[i] !== 1) continue;
            const q = 3 * R_[i], lx = L[3 * i], lz = L[3 * i + 2];
            if (!CS) {
                anchored(R_[i], lx, L[3 * i + 1], lz, C, 3 * i);
                continue;
            }
            const bx = AP[q] + lx * AE1[q] + lz * AE2[q], by = AP[q + 1] + lx * AE1[q + 1] + lz * AE2[q + 1],
                bz = AP[q + 2] + lx * AE1[q + 2] + lz * AE2[q + 2];
            const nx = AN[q], ny = AN[q + 1], nz = AN[q + 2];
            let h = -Infinity, lip = false;
            for (let k = CS[i]; k < CS[i + 1]; k++) {
                const p = 3 * CL[k];
                const dx = bx - AP[p], dy = by - AP[p + 1], dz = bz - AP[p + 2];
                const dn = dx * nx + dy * ny + dz * nz;
                const disc = dn * dn - (dx * dx + dy * dy + dz * dz) + RHO * RHO;
                if (disc < 0.0) continue;
                const hk = -dn + Math.sqrt(disc);
                if (hk > h) { h = hk; lip = k > CS[i]; }
            }
            if (h === -Infinity) h = RHO;
            if (lip) held++;
            CC[3 * i] = bx + h * nx; CC[3 * i + 1] = by + h * ny; CC[3 * i + 2] = bz + h * nz;
            h += LIFT[i];
            if (LIE_CAP && !(FAIR0 && FAIR0[i] > 0) && BWR[i] < 1.0) {
                // STAGE 2B: never more than LIE_MAX over the skin it lies on (LIE_SOFT, LIE_MAX): the height at which it
                // clears its foot's and lips' TRIANGLES by rho (the points only sample them: at rest ride 0's end
                // pressed 0.06-0.67 mm past them, which its rest lift makes up; in the swim that skin flattens, the
                // points are exact and the lift alone stood the rings off it). Its rest lift over that height passes
                // whole up to LIE_SOFT, softly capped at LIE_MAX; a ring by a clamp (its blend weight) keeps its share of
                // the climb, a faired ring is re-drawn by relay anyway
                let ht = -Infinity;
                for (let k = CS[i]; k < CS[i + 1]; k++) {
                    const a6 = 6 * CL[k];
                    ht = Math.max(ht, sweptExit(SV, 3 * A6[a6], 3 * A6[a6 + 1], 3 * A6[a6 + 2], bx, by, bz, nx, ny, nz, RHO));
                }
                const over = ht > -Infinity ? h - ht : 0.0;
                if (over > LIE_SOFT) {
                    const cap = LIE_SOFT + (LIE_MAX - LIE_SOFT) * Math.tanh((over - LIE_SOFT) / (LIE_MAX - LIE_SOFT));
                    h -= (1.0 - BWR[i]) * (over - cap);
                }
            }
            C[3 * i] = bx + h * nx; C[3 * i + 1] = by + h * ny; C[3 * i + 2] = bz + h * nz;
        }
        if (DBG) { DBG.anch.set(C); DBG.blend.set(C); }
    }
    function ringsFixed() {
        // (the anchored rings' centres: contactRings, before the clamps' frames, whose seat reads them)
        const K = D.ring_kind, L = D.ring_loc;
        for (let i = 0; i < N; i++) {
            if (K[i] === 0) fpoint(R_[i], L[3 * i], L[3 * i + 1], L[3 * i + 2], C, 3 * i);
        }
        // the clamps' BLEND: an anchored ring by a clamp drawn toward where the clamp's rigid frame carries it (wholly
        // at the face, none a ramp's length away): the skin round a pad stretches and shrinks, the clamp does not
        for (const b of D.ring_blend || []) {
            const i = b[0], w = b[5];
            fpoint(b[1], b[2], b[3], b[4], bq, 0);
            // (never lower, along its anchor's normal, than its anchor puts it: where the skin bulges up under a ramp
            // the clamp's frame does not see it, and blended rings sank 1.7 mm into it, s15; blended in height only,
            // the skin's shrinking carried the last rings past the clamp's face, a 92 deg fold, s12)
            const a3 = 3 * R_[i];
            let lo = 0.0;
            for (let c = 0; c < 3; c++) {
                const x = C[3 * i + c] + w * (bq[c] - C[3 * i + c]);
                lo += (x - C[3 * i + c]) * AN[a3 + c];
                bq[c] = x;
            }
            // (C5e: the floor fades by the blend weight: at the face the ring follows the clamp into the flesh the pad
            // presses, a ramp's length away it lies on its contact)
            const lift = lo < 0 ? -lo * (1.0 - w) : 0.0;
            for (let c = 0; c < 3; c++) C[3 * i + c] = bq[c] + lift * AN[a3 + c];
            if (DBG) for (let c = 0; c < 3; c++) DBG.blend[3 * i + c] = C[3 * i + c];
        }
        borrowEval();
        relay();
    }
    const runs = [], runOf = new Int32Array(N).fill(-1);
    const RS = D.ring_s || null;                          // C5e: each ring's rest arc length along the hose (m)
    const RT0 = new Map((D.run_tot || []).map(([a, t]) => [a, t]));   // C5f: each run's rest path as relay lays it (m)
    {
        // the runs of anchored rings (each between two rings of another kind, or the hose's end): relay() lays them; C5e:
        // s0 / s1 the hose a free span at its start / its end has slid out of it this frame (borrowEval), M its rest
        // length; C5f: tot0 its rest path as relay lays it (the forge's run_tot), lend the humps beside it (relay)
        const K = D.ring_kind;
        for (let i = 0; i < N;) {
            if (K[i] !== 1) { i++; continue; }
            let j = i;
            while (j + 1 < N && K[j + 1] === 1) j++;
            if (j - i >= 2) {
                for (let q = i; q <= j; q++) runOf[q] = runs.length;
                runs.push({ a: i, b: j, s0: 0.0, s1: 0.0, M: RS ? RS[j] - RS[i] : 0.0, tot0: RT0.get(i) || 0.0, lend: [] });
            }
            i = j + 1;
        }
    }
    function borrowEval() {
        // C5e: a free span whose ends the skin carries farther apart than its rest length allows (its slack under
        // RO.slack) cannot stay inextensible between them: the lying run it lands on slides the missing hose into it
        // (the run, laid on the skin, already follows the skin's stretch; the span keeps its rest length). The amount:
        // its chord (1 + slack) less its rest length, from the lying run at each anchored end (half each when both are),
        // at most borrowMax of its rest length
        for (const R of runs) { R.s0 = 0.0; R.s1 = 0.0; }
        if (!RS) return;
        for (const s of SP) {
            s.sA = 0.0; s.sB = 0.0;
            const ra = s.runA, rb = s.runB;
            if ((ra < 0 && rb < 0) || s.bellows) continue;   // (C5f: a bellows takes its length from its chord itself)
            const iA = 3 * (s.first - 1), iB = 3 * (s.last + 1);
            const Dc = Math.hypot(C[iB] - C[iA], C[iB + 1] - C[iA + 1], C[iB + 2] - C[iA + 2]);
            const need = Math.min(Math.max(0.0, Dc * (1.0 + s.slack) - s.L0), RO.borrowMax * s.L0);
            if (need <= 0.0) continue;
            if (ra >= 0 && rb >= 0) { s.sA = 0.5 * need; s.sB = 0.5 * need; } else if (ra >= 0) s.sA = need; else s.sB = need;
            if (ra >= 0) s.sA = Math.min(s.sA, runs[ra].M - runs[ra].s0);
            if (rb >= 0) s.sB = Math.min(s.sB, runs[rb].M - runs[rb].s1);
            if (ra >= 0) runs[ra].s1 = s.sA;
            if (rb >= 0) runs[rb].s0 = s.sB;
            stats.borrow = Math.max(stats.borrow || 0.0, s.sA + s.sB);
        }
    }
    const RP = new Float64Array(3 * (N + 4)), RC = new Float64Array(N + 4), RT_ = new Float64Array(3 * (N + 4)),
        RL = new Float64Array(3 * (N + 4));
    let relaid = 0.0;
    const u0 = new Float64Array(3), u1 = new Float64Array(3), FD = D.ring_fair_d;
    const FLF = new Float64Array(N + 4), FLT = new Float64Array(N + 4);     // (STAGE 2B: the floor's lifts, smoothed)
    function fairStretch(A, B, M, base) {
        // the control points A..B of RP (A, B held; ring of point k = base + k) re-drawn on the Hermite between A and B
        const unit = (o1, o2, out) => {
            for (let c = 0; c < 3; c++) out[c] = RP[o2 + c] - RP[o1 + c];
            normalize3(out, 0);
        };
        if (A >= 1) unit(3 * (A - 1), 3 * A, u0); else unit(3 * A, 3 * B, u0);
        if (B <= M - 2) unit(3 * B, 3 * (B + 1), u1); else unit(3 * A, 3 * B, u1);
        RC[A] = 0.0;
        for (let k = A + 1; k <= B; k++) {
            const p = 3 * k;
            RC[k] = RC[k - 1] + Math.hypot(RP[p] - RP[p - 3], RP[p + 1] - RP[p - 2], RP[p + 2] - RP[p - 1]);
        }
        const L = Math.hypot(RP[3 * B] - RP[3 * A], RP[3 * B + 1] - RP[3 * A + 1], RP[3 * B + 2] - RP[3 * A + 2]);
        const tot = RC[B] || 1e-12;
        for (let k = A + 1; k < B; k++) {
            const t = RC[k] / tot, t2 = t * t, t3 = t2 * t;
            const h00 = 2 * t3 - 3 * t2 + 1, h10 = t3 - 2 * t2 + t, h01 = -2 * t3 + 3 * t2, h11 = t3 - t2;
            const i = base + k, q = 3 * R_[i];
            // (plus the ring's rest detail off its stretch's rest Hermite, in its anchor's frame: the forge's
            // ring_fair_d; the rest pose is its rest curve)
            const dx = FD ? FD[3 * i] : 0.0, dy = FD ? FD[3 * i + 1] : 0.0, dz = FD ? FD[3 * i + 2] : 0.0;
            let dn = 0.0;
            for (let c = 0; c < 3; c++) {
                const x = h00 * RP[3 * A + c] + h10 * L * u0[c] + h01 * RP[3 * B + c] + h11 * L * u1[c]
                    + dx * AE1[q + c] + dy * AN[q + c] + dz * AE2[q + c];
                RL[3 * k + c] = x;
                dn += (x - CC[3 * i + c]) * AN[q + c];
            }
            // (no lower than FAIR_CLEAR over its contact, or than its rest lift where that is less: a lying ring the rest
            // pose pressed into the skin stays as pressed, and the rest pose its rest curve)
            dn -= Math.min(FAIR_CLEAR, LIFT[i]);
            // (C5e: that floor fades by the ring's clamp blend weight, as the blend's: by a clamp it follows the pad)
            FLF[k] = -(1.0 - BWR[i]) * Math.min(dn, 0.0);
        }
        // STAGE 2B: the floor's lifts SMOOTHED along the stretch ([1 2 1] / 4, FAIR_LIFT_SMOOTH passes, the held ends
        // 0) before they are applied: where the Hermite dives under the floor (a pad pressed into the skin, the swim's pad
        // 1 by 0.8-1.3 mm) it crossed the floor between two rings and the lift came in whole at one ring, a corner (ring
        // 249's 9.6-9.7 deg turn, a 6.7-7.0 mm bend: gate 9's bar 7.3); smoothed, the stiff hose eases onto the floor
        // over a few rings (a ring sinks under it by at most a few hundredths of a mm) and a stretch the floor leaves
        // alone, the rest pose's among them, is unchanged
        FLF[A] = 0.0;
        FLF[B] = 0.0;
        for (let it = 0; it < FAIR_LIFT_SMOOTH; it++) {
            for (let k = A; k <= B; k++) FLT[k] = FLF[k];
            for (let k = A + 1; k < B; k++) FLF[k] = 0.25 * (FLT[k - 1] + 2.0 * FLT[k] + FLT[k + 1]);
        }
        for (let k = A + 1; k < B; k++) {
            const q = 3 * R_[base + k];
            for (let c = 0; c < 3; c++) RL[3 * k + c] += FLF[k] * AN[q + c];
        }
        for (let k = A + 1; k < B; k++) for (let c = 0; c < 3; c++) RP[3 * k + c] = RL[3 * k + c];
    }
    function relay() {
        // each LYING RUN laid along its anchors: its control points (the ring before it, its anchored centres, the
        // ring after it), smoothed RUN_SMOOTH times ([1 2 1] / 4; the ends held), and its rings placed at their REST arc
        // fractions along them: the skin under a run stretches and shrinks unevenly (the swim pressed the root's by
        // 30 %), and anchored ring by ring the rings bunched, passed each other at a pad (a 128 deg turn, s14) and
        // rippled at the skin's facets; laid this way their order and spacing hold and the run follows the skin's
        // shape. At the reference pose the run is its rest curve (the smoothing moves it at most a few hundredths of a
        // mm there)
        const F = D.ring_frac, K = D.ring_kind, FAIR = D.ring_fair;
        relaid = 0.0;
        for (const R of runs) {
            const a = R.a, b = R.b;
            // (its two end rings hold their anchored places: a run's neighbour may be a free span's, placed after it; a
            // RIGID neighbour, a clamp's face ring, is a fixed control point past the end, and the end ring by it is
            // faired with the ramp)
            const m = b - a + 1;
            let pre = 0, post = 0;
            while (pre < 2 && a - pre - 1 >= 0 && K[a - pre - 1] === 0) pre++;
            while (post < 2 && b + post + 1 < N && K[b + post + 1] === 0) post++;
            const M = m + pre + post, o = 3 * pre;
            for (let k = 0; k < M; k++) for (let c = 0; c < 3; c++) RP[3 * k + c] = C[3 * (a - pre + k) + c];
            for (let it = 0; it < RUN_SMOOTH; it++) {
                for (let k = 0; k < 3 * M; k++) RT_[k] = RP[k];
                for (let k = pre + 1; k < pre + m - 1; k++) {
                    for (let c = 0; c < 3; c++) {
                        RP[3 * k + c] = 0.25 * (RT_[3 * k - 3 + c] + 2 * RT_[3 * k + c] + RT_[3 * k + 3 + c]);
                    }
                }
            }
            // the FAIRING by the clamps (D.ring_fair: the ramps and the lying rings next to them): each stretch of them
            // between two held control points re-drawn as the cubic Hermite between those two, along the tangents the
            // hose has there (the ring before, the rigid ring past the face), its rings at their fractions of the
            // stretch's arc, then each kept off the skin (never under its contact centre along its foot's normal, by
            // FAIR_CLEAR): a valley the skin makes into a clamp is bridged as a stiff hose bridges it
            if (FAIR) {
                let k = 1;
                while (k <= M - 2) {
                    const i = a - pre + k;
                    if (!(K[i] === 1 && FAIR[i] > 0)) { k++; continue; }
                    let k2 = k;
                    while (k2 + 1 <= M - 2 && K[a - pre + k2 + 1] === 1 && FAIR[a - pre + k2 + 1] > 0) k2++;
                    fairStretch(k - 1, k2 + 1, M, a - pre);
                    k = k2 + 2;
                }
            }
            RC[0] = 0.0;
            for (let k = 1; k < m; k++) {
                const p = o + 3 * k;
                RC[k] = RC[k - 1] + Math.hypot(RP[p] - RP[p - 3], RP[p + 1] - RP[p - 2], RP[p + 2] - RP[p - 1]);
            }
            const tot = RC[m - 1];
            // C5f (the lead's call 8): a run the skin SHORTENS below its rest path (tot0) slides the difference into the
            // hump beside it (half into each when both its ends have one): its rings keep their rest spacing, laid as
            // when a span borrows (the rings within s0 / s1 of an end ride the hump's rod), where they bunched along the
            // shortened path (ride 2.0 and ramp 2b by up to 11 % in the swim, the C5e check)
            if (R.lend.length && R.tot0 - tot > LEND_EPS) {
                const ex = Math.min(R.tot0 - tot, LEND_MAX * R.M) / R.lend.length;
                for (const [s, end] of R.lend) {
                    // (at most as far as NB_BORROW rings reach from that end: the hump places only those)
                    if (end === 1) {
                        const x = Math.max(0.0, Math.min(ex, RS[b] - RS[Math.max(a, b - NB_BORROW + 1)] - 1e-6 - R.s1));
                        R.s1 += x; s.sA += x;
                    } else {
                        const x = Math.max(0.0, Math.min(ex, RS[Math.min(b, a + NB_BORROW - 1)] - RS[a] - 1e-6 - R.s0));
                        R.s0 += x; s.sB += x;
                    }
                }
                stats.lend = Math.max(stats.lend || 0.0, R.s0 + R.s1);
            }
            let j = 0;
            if (R.s0 === 0.0 && R.s1 === 0.0) {
                for (let c = 0; c < 3; c++) { C[3 * a + c] = RP[o + c]; C[3 * b + c] = RP[o + 3 * (m - 1) + c]; }
            }
            // (C5e: the hose a free span slid out of its start or its end: the rings whose rest place lies in it are the
            // span's (rodSolve places them), the rest laid over the whole path at their fractions of what remains)
            const sh = R.s0 === 0.0 && R.s1 === 0.0 ? 0.0 : R.s0 / R.M, sc = R.s0 === 0.0 && R.s1 === 0.0 ? 1.0
                : 1.0 - (R.s0 + R.s1) / R.M;
            const i0 = R.s0 === 0.0 && R.s1 === 0.0 ? a + 1 : a, i1 = R.s0 === 0.0 && R.s1 === 0.0 ? b - 1 : b;
            for (let i = i0; i <= i1; i++) {
                if (R.s0 > 0.0 && RS[i] - RS[a] < R.s0) continue;
                if (R.s1 > 0.0 && RS[b] - RS[i] < R.s1) continue;
                const target = Math.min(1.0, Math.max(0.0, (F[i] - sh) / sc)) * tot;
                while (j < m - 2 && RC[j + 1] < target) j++;
                const seg = RC[j + 1] - RC[j], t = seg > 0 ? (target - RC[j]) / seg : 0.0;
                for (let c = 0; c < 3; c++) {
                    const x = RP[o + 3 * j + c] + t * (RP[o + 3 * j + 3 + c] - RP[o + 3 * j + c]);
                    relaid = Math.max(relaid, Math.abs(x - C[3 * i + c]));
                    C[3 * i + c] = x;
                }
            }
        }
    }
    // ------------------------------------------------------------------ C5e: the free spans as inextensible rods
    const tmp3 = new Float64Array(3);
    function endTangent(spec, out) {
        // a span end's tangent, along the hose (A -> B): rigid in a frame, or in its end ring's anchor triangle's frame
        if (spec[0] === 'frame') {
            fdir(spec[1], spec[2], spec[3], spec[4], out, 0);
        } else {
            anchored(spec[1], spec[2], spec[3], spec[4], out, 0);
            const q = 3 * spec[1];
            for (let c = 0; c < 3; c++) out[c] -= AP[q + c];
            normalize3(out, 0);
        }
    }
    function upOf(spec, out) {
        if (spec[0] === 'frame') fdir(spec[1], spec[2], spec[3], spec[4], out, 0);
        else for (let c = 0; c < 3; c++) out[c] = AN[3 * spec[1] + c];
    }
    const SP = (D.spans || []).map((s) => {
        const nR = s.rest ? s.rest.length / 3 - 1 : Math.min(72, Math.max(16, Math.ceil((s.L0 * 1e3) / RO.step)));
        const nU = 3 * (nR - 1);
        const model = s.pieces.every((p) => p.startsWith('hump')) ? 'hump'
            : s.pieces.every((p) => p.startsWith('arch') || p.startsWith('hump')) ? 'arch' : 'hermite';
        const B = s.bounds || { ring: [], kind: [], ref: [], loc: [], clear: [] };
        const nb0 = B.ring.length, nbMax = nb0 + 2 * NB_BORROW;
        // (the lying runs it lands on, at an end that is a run's end ring: they may slide hose into it, borrowEval)
        const iA = s.first - 1, iB = s.last + 1, K = D.ring_kind;
        const runA = RS && K[iA] === 1 && runOf[iA] >= 0 && runs[runOf[iA]].b === iA ? runOf[iA] : -1;
        const runB = RS && K[iB] === 1 && runOf[iB] >= 0 && runs[runOf[iB]].a === iB ? runOf[iB] : -1;
        // (the slack it keeps when the skin pulls it taut: RO.slack, or as much of its rest slack as its model keeps)
        const restSlack = s.rest_d ? Math.max(0.0, s.L0 / s.rest_d - 1.0) : 0.0;
        const slack = Math.max(RO.slack, (RO.slackRest[model] || 0.0) * restSlack);
        return {
            ...s, model, nR, nU, runA, runB, sA: 0.0, sB: 0.0, slack,
            // C5f (the lead's call 5): a BELLOWS span (a convoluted section) keeps its length over its chord at the rest
            // ratio, within cmp of its rest length: Le its own length this frame (L0 for every other span)
            bellows: !!s.bellows, cmp: s.compress || [0.6, 1.15], Le: s.L0,
            P: new Float64Array(3 * (NS + 1)), cum: new Float64Array(NS + 1),
            X: new Float64Array(3 * (nR + 1)), XT: new Float64Array(3 * (nR + 1)), G: new Float64Array(3 * (nR + 1)),
            lam: new Float64Array(nR), band: new Float64Array(nU * (HB + 1)), grad: new Float64Array(nU),
            dx: new Float64Array(nU),
            bA: new Float64Array(3), bB: new Float64Array(3), tA: new Float64Array(3), tB: new Float64Array(3),
            up: new Float64Array(3), ex: new Float64Array(3), ey: new Float64Array(3), ez: new Float64Array(3),
            // the bounds: its own rings' at their rest fractions of the span (bf0), then the borrowed rings' feet; this
            // frame's fractions of the rod, points and normals (mm, off A) and clearances (mm)
            bf0: Float64Array.from(B.ring, (i) => s.frac[i - s.first]), bf: new Float64Array(nbMax),
            bQ: new Float64Array(3 * nbMax), bN: new Float64Array(3 * nbMax), bC: new Float64Array(nbMax),
            bR: new Int32Array(nbMax), nb0, nb: nb0, B,
            // the borrowed rings this frame (at the start, at the end) and every ring's fraction of the rod
            brA: new Int32Array(NB_BORROW), brB: new Int32Array(NB_BORROW), nA: 0, nB: 0,
            tw: RO.tether[model], h: 0.0, stretch: 0.0, lifted: 0.0, newton: 0, outer: 0, cmax: 0.0, skinMin: 0.0,
            Lm: s.L0, key: new Float64Array(17 + 8 * nbMax), solved: false,
        };
    });
    // C5f (the lead's call 8): the humps each lying run lends to (relay): a hump after its end takes from its end, one
    // before its start from its start
    for (const s of SP) {
        if (s.model !== 'hump') continue;
        if (s.runA >= 0) runs[s.runA].lend.push([s, 1]);
        if (s.runB >= 0) runs[s.runB].lend.push([s, 0]);
    }
    function hermiteGuess(s, Lt) {
        // (a span without its rest shape, a glb of C5d's: the initial shape is C5d's Hermite of its end tangents and an
        // h sin^2(pi u^p) bow along `up` whose length is the rest length, by bisection on h)
        const A = s.bA, B = s.bB, ta = s.tA, tb = s.tB, up = s.up;
        const ch = Math.hypot(B[0] - A[0], B[1] - A[1], B[2] - A[2]);
        const sample = (h) => {
            let len = 0.0;
            for (let i = 0; i <= NS; i++) {
                const u = i / NS, u2 = u * u, u3 = u2 * u;
                const h00 = 2 * u3 - 3 * u2 + 1, h10 = u3 - 2 * u2 + u, h01 = -2 * u3 + 3 * u2, h11 = u3 - u2;
                const bw = h * Math.sin(Math.PI * Math.pow(u, s.bp)) ** 2;
                for (let c = 0; c < 3; c++) {
                    s.P[3 * i + c] = h00 * A[c] + h10 * ch * s.k0 * ta[c] + h01 * B[c] + h11 * ch * s.k1 * tb[c] + bw * up[c];
                }
                if (i > 0) {
                    len += Math.hypot(s.P[3 * i] - s.P[3 * i - 3], s.P[3 * i + 1] - s.P[3 * i - 2], s.P[3 * i + 2] - s.P[3 * i - 1]);
                }
                s.cum[i] = len;
            }
            return len;
        };
        let lo = 0.0, hi = 0.004;
        if (sample(0.0) < Lt) {
            while (sample(hi) < Lt && hi < 0.256) hi *= 2.0;
            for (let it = 0; it < 40; it++) {
                const m = 0.5 * (lo + hi);
                if (sample(m) < Lt) lo = m; else hi = m;
            }
            sample(hi);
        }
        // its NR + 1 nodes at equal arc fractions (mm, off A)
        const nR = s.nR, tot = s.cum[NS];
        let j = 0;
        for (let k = 0; k <= nR; k++) {
            const target = (k / nR) * tot;
            while (j < NS - 1 && s.cum[j + 1] < target) j++;
            const seg = s.cum[j + 1] - s.cum[j], t = seg > 0 ? (target - s.cum[j]) / seg : 0.0;
            for (let c = 0; c < 3; c++) {
                s.G[3 * k + c] = 1e3 * (s.P[3 * j + c] + t * (s.P[3 * j + 3 + c] - s.P[3 * j + c]) - A[c]);
            }
        }
    }
    function restGuess(s, Lmm, Dmm) {
        // the span's REST SHAPE carried by its ends (forge/cyborg_cable.py's rest: its NR + 1 nodes in the frame of its
        // rest chord and its ends' up axes, mm): along the chord scaled to the chord now, across as it was, up scaled by
        // the one factor that gives it its rest length (bisection: a shorter chord, a taller bow), in this frame's axes
        const R0 = s.rest, nR = s.nR, sx = Dmm / (s.rest_d * 1e3);
        const len = (sy) => {
            let L = 0.0, x0 = 0.0, y0 = 0.0, z0 = 0.0;
            for (let k = 0; k <= nR; k++) {
                const x = 1e3 * R0[3 * k] * sx, y = 1e3 * R0[3 * k + 1] * sy, z = 1e3 * R0[3 * k + 2];
                if (k > 0) L += Math.hypot(x - x0, y - y0, z - z0);
                x0 = x; y0 = y; z0 = z;
            }
            return L;
        };
        let sy = 1.0;
        if (len(0.0) < Lmm) {
            let lo = 0.0, hi = 1.0;
            while (len(hi) < Lmm && hi < 64) hi *= 2.0;
            for (let it = 0; it < 40; it++) {
                const m = 0.5 * (lo + hi);
                if (len(m) < Lmm) lo = m; else hi = m;
            }
            sy = hi;
        } else {
            sy = 0.0;
        }
        s.h = sy;
        // (across the chord, the rest shape bent by the cubic that gives it the end tangents' sideways slopes now: a pad
        // rolled sideways in the swim turns the hose's ends, and the tether across the chord kept to the rest line held
        // them against it)
        const ta = s.tA, tb = s.tB;
        const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
        let dA = 0.0, dB = 0.0;
        if (RO.latfix === 1) {
            // (the sideways slopes dz/dx: unbounded where an end turns steeply off the chord)
            const x1 = 1e3 * R0[3] * sx, xn = 1e3 * R0[3 * (nR - 1)] * sx;
            dA = dot(ta, s.ez) / Math.max(dot(ta, s.ex), 0.2) - (1e3 * R0[5] - 1e3 * R0[2]) / Math.max(x1, 1e-6);
            dB = dot(tb, s.ez) / Math.max(dot(tb, s.ex), 0.2)
                - (1e3 * R0[3 * nR + 2] - 1e3 * R0[3 * (nR - 1) + 2]) / Math.max(Dmm - xn, 1e-6);
        } else if (RO.latfix === 2) {
            // (the unit tangents' sideways parts, bounded: the shape's own end directions against the ends' now)
            const g = (k0, k1) => {
                const ax = 1e3 * (R0[3 * k1] - R0[3 * k0]) * sx, ay = 1e3 * (R0[3 * k1 + 1] - R0[3 * k0 + 1]) * sy,
                    az = 1e3 * (R0[3 * k1 + 2] - R0[3 * k0 + 2]);
                return az / (Math.hypot(ax, ay, az) || 1.0);
            };
            dA = dot(ta, s.ez) - g(0, 1);
            dB = dot(tb, s.ez) - g(nR - 1, nR);
        }
        for (let k = 0; k <= nR; k++) {
            const x = 1e3 * R0[3 * k] * sx, y = 1e3 * R0[3 * k + 1] * sy;
            const u = Math.min(Math.max(x / Dmm, 0.0), 1.0), u2 = u * u, u3 = u2 * u;
            const z = 1e3 * R0[3 * k + 2] + Dmm * ((u3 - 2 * u2 + u) * dA + (u3 - u2) * dB);
            for (let c = 0; c < 3; c++) s.G[3 * k + c] = x * s.ex[c] + y * s.ey[c] + z * s.ez[c];
        }
    }
    const qb = new Float64Array(3), nb = new Float64Array(3);
    const BORROW_CLEAR = (RHO || 0.0) - 0.03e-3;         // a borrowed ring's bound: its foot's plane, nearly its contact
    function spanInputs(s) {
        // the span's ends from its neighbours (already placed: a borrowed end is its run's touchdown, where relay left
        // it), their tangents, its up axis (the ends' up axes' mean), its length this frame (its rest length and what it
        // borrowed), its rings' fractions of it, its bounds' points and normals; returns whether anything differs from
        // the last solve's inputs
        for (let c = 0; c < 3; c++) { s.bA[c] = C[3 * (s.first - 1) + c]; s.bB[c] = C[3 * (s.last + 1) + c]; }
        endTangent(s.ta_spec, s.tA);
        endTangent(s.tb_spec, s.tB);
        upOf(s.ua_spec, tmp3);
        const ux = tmp3[0], uy = tmp3[1], uz = tmp3[2];
        upOf(s.ub_spec, tmp3);
        s.up[0] = ux + tmp3[0]; s.up[1] = uy + tmp3[1]; s.up[2] = uz + tmp3[2];
        normalize3(s.up, 0);
        const sA = s.sA || 0.0, sB = s.sB || 0.0;
        if (s.bellows) {
            // (C5f: a convoluted section's length follows its chord at its rest ratio: the convolutions bunch, the arch
            // keeps its rest shape; held at its rest length the swim pressed arch 1's 41 mm into a 12 mm curl)
            const Dc = Math.hypot(s.bB[0] - s.bA[0], s.bB[1] - s.bA[1], s.bB[2] - s.bA[2]);
            s.Le = s.L0 * Math.min(Math.max(Dc / s.rest_d, s.cmp[0]), s.cmp[1]);
        }
        const Lm = s.Le + sA + sB;
        s.Lm = Lm;
        const iA = s.first - 1, iB = s.last + 1;
        s.nA = 0; s.nB = 0;
        if (sA > 0.0) for (let j = iA; j >= runs[s.runA].a && RS[iA] - RS[j] < sA && s.nA < NB_BORROW; j--) s.brA[s.nA++] = j;
        if (sB > 0.0) for (let j = iB; j <= runs[s.runB].b && RS[j] - RS[iB] < sB && s.nB < NB_BORROW; j++) s.brB[s.nB++] = j;
        const B = s.B;
        for (let q = 0; q < s.nb0; q++) {
            if (B.kind[q] === 1) {
                const a = B.ref[q];
                for (let c = 0; c < 3; c++) { qb[c] = AP[3 * a + c]; nb[c] = AN[3 * a + c]; }
            } else {
                const f = B.ref[q], L = B.loc;
                fpoint(f, L[6 * q], L[6 * q + 1], L[6 * q + 2], qb, 0);
                fdir(f, L[6 * q + 3], L[6 * q + 4], L[6 * q + 5], nb, 0);
            }
            for (let c = 0; c < 3; c++) { s.bQ[3 * q + c] = 1e3 * (qb[c] - s.bA[c]); s.bN[3 * q + c] = nb[c]; }
            s.bf[q] = (s.bf0[q] * s.Le + sA) / Lm;
            s.bC[q] = 1e3 * B.clear[q];
            s.bR[q] = B.ring[q];
        }
        // (a borrowed ring, at its fraction of the rod: its rest arc off the touchdown; held no lower than the hose lies
        // at the TOUCHDOWN t, the end ring the rod leaves: over t's foot's plane by t's contact and rest lift (relay left
        // it there), nor than its contact. C5f: the touchdown's plane, where the borrowed rings now ride. Each ring's own
        // foot lies behind the touchdown, and on the arm's convex skin its plane carried forward stands over the skin
        // there: held over it, the rings a run LENDS a hump lifted the rod's start against its end tangent, a 13.6 deg
        // corner at the hand-over (seed 6 in the swim; 7.9 deg without these bounds, C5e's 3 deg where nothing is lent))
        let nbq = s.nb0;
        const addB = (j, f, t) => {
            const a = 3 * R_[t];
            let hl = 0.0;
            for (let c = 0; c < 3; c++) {
                s.bQ[3 * nbq + c] = 1e3 * (AP[a + c] - s.bA[c]); s.bN[3 * nbq + c] = AN[a + c];
                hl += (C[3 * t + c] - AP[a + c]) * AN[a + c];
            }
            s.bf[nbq] = f;
            s.bC[nbq] = 1e3 * Math.min(BORROW_CLEAR, hl - 0.03e-3);
            s.bR[nbq] = j;
            nbq++;
        };
        for (let q = 0; q < s.nA; q++) { const j = s.brA[q]; addB(j, (sA - (RS[iA] - RS[j])) / Lm, iA); }
        for (let q = 0; q < s.nB; q++) { const j = s.brB[q]; addB(j, (sA + s.Le + (RS[j] - RS[iB])) / Lm, iB); }
        s.nb = nbq;
        // (the key: every input of the solve; equal to the last one's, its solution stands. C5e check: with each bound's
        // clearance too, a borrowed ring's bound reads its height where relay left it (C[j]), which the other inputs
        // do not fix, so without it a reuse could differ from a fresh solve)
        const K = s.key;
        let same = s.solved, o = 0;
        const put = (x) => { if (K[o] !== x) { same = false; K[o] = x; } o++; };
        for (let c = 0; c < 3; c++) { put(s.bA[c]); put(s.bB[c]); put(s.tA[c]); put(s.tB[c]); put(s.up[c]); }
        put(sA); put(sB);
        for (let q = 0; q < s.nb; q++) {
            for (let c = 0; c < 3; c++) { put(s.bQ[3 * q + c]); put(s.bN[3 * q + c]); }
            put(s.bf[q]);
            put(s.bC[q]);
        }
        return !same;
    }
    // the rod's energy terms (mm): bending l w(|D_k|^2 / l^4) at every node k = 0..NR (D_k the second difference, the
    // ghosts A - l tA and B + l tB past the ends), the tether l sum_a mu_a ((X_k - G_k) . e_a)^2, the bounds
    // nu l max(0, c + margin - (X(f) - Q) . n)^2, and the segments' lengths in the augmented Lagrangian
    // lam_k c_k + rho / 2 c_k^2, c_k = (|X_k+1 - X_k|^2 - l^2) / (2 l)
    const PW = RO.pow, RQ6 = Math.pow(RO.rref, 2 * PW - 2);
    const wq = (q) => q + RQ6 * Math.pow(q, PW);
    const XX = (s, X, k, c) => {
        // a node's coordinate, the ghosts past the ends (mm, off A)
        if (k < 0) return X[c] - s.l * s.tA[c];
        if (k > s.nR) return X[3 * s.nR + c] + s.l * s.tB[c];
        return X[3 * k + c];
    };
    function rodEnergy(s, X) {
        const nR = s.nR, l = s.l, l4 = l * l * l * l, mu = s.tw;
        let E = 0.0;
        for (let k = 0; k <= nR; k++) {
            let q = 0.0;
            for (let c = 0; c < 3; c++) {
                const d = XX(s, X, k - 1, c) - 2 * X[3 * k + c] + XX(s, X, k + 1, c);
                q += d * d;
            }
            E += l * wq(q / l4);
        }
        for (let k = 1; k < nR; k++) {
            let rx = 0.0, ry = 0.0, rz = 0.0;
            for (let c = 0; c < 3; c++) {
                const d = X[3 * k + c] - s.G[3 * k + c];
                rx += d * s.ex[c]; ry += d * s.ey[c]; rz += d * s.ez[c];
            }
            E += l * (mu[0] * rx * rx + mu[1] * ry * ry + mu[2] * rz * rz);
        }
        for (let k = 0; k < nR; k++) {
            let dd = 0.0;
            for (let c = 0; c < 3; c++) { const d = X[3 * k + 3 + c] - X[3 * k + c]; dd += d * d; }
            const ck = (dd - l * l) / (2 * l);
            E += s.lam[k] * ck + 0.5 * RO.rho * ck * ck;
        }
        for (let b = 0; b < s.nb; b++) {
            const f = s.bf[b] * nR, k = Math.min(Math.floor(f), nR - 1), t = f - k;
            let h = 0.0;
            for (let c = 0; c < 3; c++) h += ((1 - t) * X[3 * k + c] + t * X[3 * k + 3 + c] - s.bQ[3 * b + c]) * s.bN[3 * b + c];
            const g = s.bC[b] + RO.margin - h;
            if (g > 0) E += RO.nu * l * g * g;
        }
        return E;
    }
    const DB = new Float64Array(3), DD = new Float64Array(3);
    function rodAssemble(s, X) {
        // the gradient and the (positive semi-definite) Hessian of the energy over the free nodes 1..NR-1, the Hessian
        // in band storage (row i, column i - d at band[i (HB + 1) + d]); the length terms' curvature dropped where its
        // multiplier is compressive (Gauss-Newton: the band stays positive definite)
        const nR = s.nR, l = s.l, l4 = l * l * l * l, mu = s.tw, g = s.grad, H = s.band, W = HB + 1;
        g.fill(0.0);
        H.fill(0.0);
        const addH = (ia, ib, val) => {
            // (the lower triangle only: ia >= ib)
            if (ia >= ib) H[ia * W + (ia - ib)] += val;
            else H[ib * W + (ib - ia)] += val;
        };
        const blk = (ka, kb, M00, coef, dvec, iso) => {
            // a node pair's 3x3 block coef (M00 d d^T + iso I), each entry added once (the lower triangle)
            if (ka < 1 || ka >= nR || kb < 1 || kb >= nR) return;
            const oa = 3 * (ka - 1), ob = 3 * (kb - 1);
            for (let p = 0; p < 3; p++) {
                for (let q = 0; q < 3; q++) {
                    const ia = oa + p, ib = ob + q;
                    if (ka === kb && q > p) continue;
                    if (ka > kb || (ka === kb)) addH(ia, ib, coef * (M00 * dvec[p] * dvec[q] + (p === q ? iso : 0.0)));
                }
            }
        };
        const cf = [1.0, -2.0, 1.0];
        for (let k = 0; k <= nR; k++) {
            let q = 0.0;
            for (let c = 0; c < 3; c++) {
                DB[c] = XX(s, X, k - 1, c) - 2 * X[3 * k + c] + XX(s, X, k + 1, c);
                q += DB[c] * DB[c];
            }
            q /= l4;
            const w1 = 1 + PW * RQ6 * Math.pow(q, PW - 1), w2 = PW * (PW - 1) * RQ6 * Math.pow(q, PW - 2);
            for (let a = 0; a < 3; a++) {
                const ka = k - 1 + a;
                if (ka < 1 || ka >= nR) continue;
                for (let c = 0; c < 3; c++) g[3 * (ka - 1) + c] += l * w1 * (2 / l4) * cf[a] * DB[c];
                for (let b = 0; b <= a; b++) {
                    const kb = k - 1 + b;
                    if (kb < 1 || kb >= nR) continue;
                    // l [w'' (2/l^4)^2 ca cb D D^T + w' (2/l^4) ca cb I]
                    blk(ka, kb, (w2 * 2 / l4) / w1, l * w1 * (2 / l4) * cf[a] * cf[b], DB, 1.0);
                }
            }
        }
        for (let k = 1; k < nR; k++) {
            let rx = 0.0, ry = 0.0, rz = 0.0;
            for (let c = 0; c < 3; c++) {
                const d = X[3 * k + c] - s.G[3 * k + c];
                rx += d * s.ex[c]; ry += d * s.ey[c]; rz += d * s.ez[c];
            }
            const o = 3 * (k - 1);
            for (let c = 0; c < 3; c++) {
                g[o + c] += 2 * l * (mu[0] * rx * s.ex[c] + mu[1] * ry * s.ey[c] + mu[2] * rz * s.ez[c]);
                for (let c2 = 0; c2 <= c; c2++) {
                    addH(o + c, o + c2, 2 * l * (mu[0] * s.ex[c] * s.ex[c2] + mu[1] * s.ey[c] * s.ey[c2]
                        + mu[2] * s.ez[c] * s.ez[c2]));
                }
            }
        }
        for (let k = 0; k < nR; k++) {
            let dd = 0.0;
            for (let c = 0; c < 3; c++) { DD[c] = X[3 * k + 3 + c] - X[3 * k + c]; dd += DD[c] * DD[c]; }
            const ck = (dd - l * l) / (2 * l), gc = s.lam[k] + RO.rho * ck;
            for (let c = 0; c < 3; c++) {
                if (k + 1 < nR) g[3 * k + c] += gc * DD[c] / l;
                if (k >= 1) g[3 * (k - 1) + c] -= gc * DD[c] / l;
            }
            const iso = (RO.exact ? gc : Math.max(gc, 0.0)) / l;
            const m00 = RO.rho / (l * l);
            // (k+1, k+1), (k, k): m00 d d^T + iso I; (k+1, k): -(m00 d d^T + iso I)
            blk(k + 1, k + 1, m00, 1.0, DD, iso);
            blk(k, k, m00, 1.0, DD, iso);
            blk(k + 1, k, m00, -1.0, DD, iso);
        }
        for (let b = 0; b < s.nb; b++) {
            const f = s.bf[b] * nR, k = Math.min(Math.floor(f), nR - 1), t = f - k;
            let h = 0.0;
            for (let c = 0; c < 3; c++) h += ((1 - t) * X[3 * k + c] + t * X[3 * k + 3 + c] - s.bQ[3 * b + c]) * s.bN[3 * b + c];
            const gg = s.bC[b] + RO.margin - h;
            if (gg <= 0) continue;
            const nvec = s.bN.subarray(3 * b, 3 * b + 3), cc = 2 * RO.nu * l;
            for (let c = 0; c < 3; c++) {
                if (k >= 1) g[3 * (k - 1) + c] -= cc * gg * (1 - t) * nvec[c];
                if (k + 1 < nR) g[3 * k + c] -= cc * gg * t * nvec[c];
            }
            blk(k, k, 1.0, cc * (1 - t) * (1 - t), nvec, 0.0);
            blk(k + 1, k + 1, 1.0, cc * t * t, nvec, 0.0);
            blk(k + 1, k, 1.0, cc * t * (1 - t), nvec, 0.0);
        }
    }
    function bandSolve(s) {
        // the band's Cholesky (L L^T, in place) and the solve of H dx = -g; a non-positive pivot: the diagonal raised
        // a little and the factorisation repeated (true when solved)
        const n = s.nU, W = HB + 1, H = s.band, x = s.dx;
        for (let tries = 0; tries < 4; tries++) {
            let ok = true;
            for (let i = 0; i < n && ok; i++) {
                for (let j = Math.max(0, i - HB); j <= i; j++) {
                    let sum = H[i * W + (i - j)];
                    for (let k = Math.max(0, i - HB, j - HB); k < j; k++) sum -= H[i * W + (i - k)] * H[j * W + (j - k)];
                    if (i === j) {
                        if (!(sum > 1e-14)) { ok = false; break; }
                        H[i * W] = Math.sqrt(sum);
                    } else {
                        H[i * W + (i - j)] = sum / H[j * W];
                    }
                }
            }
            if (ok) {
                for (let i = 0; i < n; i++) {
                    let sum = -s.grad[i];
                    for (let k = Math.max(0, i - HB); k < i; k++) sum -= H[i * W + (i - k)] * x[k];
                    x[i] = sum / H[i * W];
                }
                for (let i = n - 1; i >= 0; i--) {
                    let sum = x[i];
                    for (let k = i + 1; k <= Math.min(n - 1, i + HB); k++) sum -= H[k * W + (k - i)] * x[k];
                    x[i] = sum / H[i * W];
                }
                return true;
            }
            // (re-assemble with a raised diagonal)
            rodAssemble(s, s.X);
            const lift = 1e-6 * Math.pow(100, tries);
            for (let i = 0; i < n; i++) H[i * W] += lift;
        }
        return false;
    }
    function rodNewton(s, X) {
        // Newton on the augmented Lagrangian at the current power: RO.inner steps with a halving line search on the
        // energy, RO.outer multiplier updates, done when every segment holds its length; X (and s.lam) updated in place
        const nR = s.nR;
        let it = 0, outer = 0, cmax = Infinity;
        for (; outer < RO.outer; outer++) {
            for (let inner = 0; inner < RO.inner; inner++) {
                rodAssemble(s, X);
                if (!bandSolve(s)) break;
                const E0 = rodEnergy(s, X);
                let step = 1.0, ok = false, dmax = 0.0;
                for (let ls = 0; ls < 12; ls++) {
                    s.XT.set(X);
                    for (let k = 1; k < nR; k++) for (let c = 0; c < 3; c++) s.XT[3 * k + c] += step * s.dx[3 * (k - 1) + c];
                    if (rodEnergy(s, s.XT) <= E0) { ok = true; break; }
                    step *= 0.5;
                }
                it++;
                if (!ok) break;
                for (let k = 1; k < nR; k++) {
                    for (let c = 0; c < 3; c++) dmax = Math.max(dmax, Math.abs(step * s.dx[3 * (k - 1) + c]));
                }
                X.set(s.XT);
                if (dmax < RO.dtol) break;
            }
            // the multipliers; done when every segment holds its length
            cmax = 0.0;
            for (let k = 0; k < nR; k++) {
                let dd = 0.0;
                for (let c = 0; c < 3; c++) { const d = X[3 * k + 3 + c] - X[3 * k + c]; dd += d * d; }
                const ck = (dd - s.l * s.l) / (2 * s.l);
                s.lam[k] += RO.rho * ck;
                cmax = Math.max(cmax, Math.abs(ck) / s.l);
            }
            if (cmax < RO.tol) { outer++; break; }
        }
        return { it, outer, cmax };
    }
    function rodSolve(s) {
        // the span's ROD this frame: its frame (the chord, up across it, ez = ex x ey), its initial shape and tether
        // target (the rest shape carried by its ends, or C5d's bow guess), then Newton on the augmented Lagrangian
        // (RO.inner steps with a halving line search on the energy, RO.outer multiplier updates). Its length: its rest
        // length and what it borrowed this frame (s.Lm)
        const nR = s.nR, A = s.bA, B = s.bB;
        const Dmm = 1e3 * Math.hypot(B[0] - A[0], B[1] - A[1], B[2] - A[2]);
        const Lmm = 1e3 * s.Lm;
        s.l = Lmm / nR;
        for (let c = 0; c < 3; c++) s.ex[c] = (B[c] - A[c]) * 1e3 / Dmm;
        let ud = 0.0;
        for (let c = 0; c < 3; c++) ud += s.up[c] * s.ex[c];
        for (let c = 0; c < 3; c++) s.ey[c] = s.up[c] - ud * s.ex[c];
        if (Math.hypot(s.ey[0], s.ey[1], s.ey[2]) < 1e-6) {
            // (up along the chord: any axis across it)
            const ax = Math.abs(s.ex[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
            const d = ax[0] * s.ex[0] + ax[1] * s.ex[1] + ax[2] * s.ex[2];
            for (let c = 0; c < 3; c++) s.ey[c] = ax[c] - d * s.ex[c];
        }
        normalize3(s.ey, 0);
        s.ez[0] = s.ex[1] * s.ey[2] - s.ex[2] * s.ey[1];
        s.ez[1] = s.ex[2] * s.ey[0] - s.ex[0] * s.ey[2];
        s.ez[2] = s.ex[0] * s.ey[1] - s.ex[1] * s.ey[0];
        if (s.rest) restGuess(s, Lmm, Dmm);
        else hermiteGuess(s, s.Lm);
        const X = s.X;
        X.set(s.G);
        // (the ends exact: A at the origin, B at the chord's end)
        for (let c = 0; c < 3; c++) { X[c] = 0.0; X[3 * nR + c] = 1e3 * (B[c] - A[c]); }
        s.lam.fill(0.0);
        const { it, outer, cmax } = rodNewton(s, X);
        s.newton = it;
        s.outer = outer;
        s.cmax = cmax;
        // its bounds' least clearance (mm, past their own) and its length
        let worst = Infinity;
        s.worstB = -1;
        for (let b = 0; b < s.nb; b++) {
            const f = s.bf[b] * nR, k = Math.min(Math.floor(f), nR - 1), t = f - k;
            let h = 0.0;
            for (let c = 0; c < 3; c++) h += ((1 - t) * X[3 * k + c] + t * X[3 * k + 3 + c] - s.bQ[3 * b + c]) * s.bN[3 * b + c];
            if (h - s.bC[b] < worst) { worst = h - s.bC[b]; s.worstB = b; }
        }
        s.chord = Dmm / Lmm;
        s.skinMin = worst;
        s.lifted = Math.max(0.0, -worst) * 1e-3;
        let len = 0.0;
        for (let k = 0; k < nR; k++) {
            len += Math.hypot(X[3 * k + 3] - X[3 * k], X[3 * k + 4] - X[3 * k + 1], X[3 * k + 5] - X[3 * k + 2]);
        }
        s.stretch = len / Lmm - 1.0;
        s.solved = true;
    }
    function placeRings(s) {
        // the span's rings at their rest arc fractions of the rod (its nodes' arc: equal segments), on the cubic Hermite
        // through the nodes (Catmull-Rom tangents, the ghosts past the ends): back to metres off the span's start
        const nR = s.nR, X = s.X, A = s.bA, sA = s.sA || 0.0, Lm = s.Lm;
        const put = (i, fr) => {
            const f = Math.min(Math.max(fr, 0.0), 1.0) * nR, k = Math.min(Math.floor(f), nR - 1), t = f - k;
            const t2 = t * t, t3 = t2 * t;
            const h00 = 2 * t3 - 3 * t2 + 1, h10 = t3 - 2 * t2 + t, h01 = -2 * t3 + 3 * t2, h11 = t3 - t2;
            for (let c = 0; c < 3; c++) {
                const p0 = X[3 * k + c], p1 = X[3 * k + 3 + c];
                const m0 = 0.5 * (p1 - XX(s, X, k - 1, c)), m1 = 0.5 * (XX(s, X, k + 2, c) - p0);
                C[3 * i + c] = A[c] + 1e-3 * (h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1);
            }
        };
        for (let q = 0; q <= s.last - s.first; q++) put(s.first + q, (s.frac[q] * s.Le + sA) / Lm);
        // (C5e: the rings it borrowed from the lying runs at its ends)
        const iA = s.first - 1, iB = s.last + 1;
        for (let q = 0; q < s.nA; q++) { const j = s.brA[q]; put(j, (sA - (RS[iA] - RS[j])) / Lm); }
        for (let q = 0; q < s.nB; q++) { const j = s.brB[q]; put(j, (sA + s.Le + (RS[j] - RS[iB])) / Lm); }
    }
    function spanEval(s) {
        if (spanInputs(s)) rodSolve(s);
        else stats.spanReused = (stats.spanReused || 0) + 1;
        placeRings(s);
    }
    function frameRings() {
        // tangents (the centres' central differences, one-sided at the ends), rotation-minimising normals from the plate
        // fitting's reference axis (double reflection, Wang et al. 2008), each ring's vertices round its centre
        for (let i = 0; i < N; i++) {
            const a = Math.max(i - 1, 0), b = Math.min(i + 1, N - 1);
            for (let c = 0; c < 3; c++) T[3 * i + c] = C[3 * b + c] - C[3 * a + c];
            normalize3(T, 3 * i);
        }
        const e0 = D.e1_0;
        fdir(e0[0], e0[1], e0[2], e0[3], E1, 0);
        let d = E1[0] * T[0] + E1[1] * T[1] + E1[2] * T[2];
        for (let c = 0; c < 3; c++) E1[c] -= d * T[c];
        normalize3(E1, 0);
        for (let i = 0; i < N - 1; i++) {
            const o = 3 * i, p = o + 3;
            const v10 = C[p] - C[o], v11 = C[p + 1] - C[o + 1], v12 = C[p + 2] - C[o + 2];
            const c1 = v10 * v10 + v11 * v11 + v12 * v12;
            if (c1 < 1e-24) { E1[p] = E1[o]; E1[p + 1] = E1[o + 1]; E1[p + 2] = E1[o + 2]; continue; }
            const kr = (2.0 / c1) * (v10 * E1[o] + v11 * E1[o + 1] + v12 * E1[o + 2]);
            const rL0 = E1[o] - kr * v10, rL1 = E1[o + 1] - kr * v11, rL2 = E1[o + 2] - kr * v12;
            const kt = (2.0 / c1) * (v10 * T[o] + v11 * T[o + 1] + v12 * T[o + 2]);
            const tL0 = T[o] - kt * v10, tL1 = T[o + 1] - kt * v11, tL2 = T[o + 2] - kt * v12;
            const v20 = T[p] - tL0, v21 = T[p + 1] - tL1, v22 = T[p + 2] - tL2;
            const c2 = v20 * v20 + v21 * v21 + v22 * v22;
            const k2 = c2 > 1e-24 ? (2.0 / c2) * (v20 * rL0 + v21 * rL1 + v22 * rL2) : 0.0;
            E1[p] = rL0 - k2 * v20; E1[p + 1] = rL1 - k2 * v21; E1[p + 2] = rL2 - k2 * v22;
            d = E1[p] * T[p] + E1[p + 1] * T[p + 1] + E1[p + 2] * T[p + 2];
            for (let c = 0; c < 3; c++) E1[p + c] -= d * T[p + c];
            normalize3(E1, p);
        }
        for (let i = 0; i < N; i++) {
            const o = 3 * i;
            E2[o] = T[o + 1] * E1[o + 2] - T[o + 2] * E1[o + 1];
            E2[o + 1] = T[o + 2] * E1[o] - T[o] * E1[o + 2];
            E2[o + 2] = T[o] * E1[o + 1] - T[o + 1] * E1[o];
            // (C5f, the lead's call 5: a convoluted section's ring its own radius, its normals tilted along the hose by
            // the profile's slope over the rings' spacing now: pressed, the convolutions stand steeper)
            let rr = r, sl = 0.0;
            if (RR) {
                const a = Math.max(i - 1, 0), b = Math.min(i + 1, N - 1);
                const dl = Math.hypot(C[3 * b] - C[3 * a], C[3 * b + 1] - C[3 * a + 1], C[3 * b + 2] - C[3 * a + 2]);
                rr = RR[i];
                sl = dl > 1e-12 ? (RR[b] - RR[a]) / dl : 0.0;
            }
            const ks = 1.0 / Math.sqrt(1.0 + sl * sl);
            for (let j = 0; j < nc; j++) {
                const ca = COS[j], sa = SIN[j];
                const q = i * nc + j;
                for (let c = 0; c < 3; c++) {
                    const nn = ca * E1[o + c] + sa * E2[o + c];
                    sleeveNrm[3 * q + c] = RR ? (nn - sl * T[o + c]) * ks : nn;
                    sleevePos[3 * q + c] = C[o + c] + rr * nn;
                    sleeveTan[4 * q + c] = -sa * E1[o + c] + ca * E2[o + c];
                }
                sleeveTan[4 * q + 3] = D.tan_w;
            }
        }
    }
    // (C5e, the cost pass: the pads' rest data as typed arrays once, and per pad run its frame and the vertices it holds)
    const PADV = D.pads ? { rig: Float64Array.from(D.pads.rig), nrm: Float64Array.from(D.pads.nrm),
        tan: Float64Array.from(D.pads.tan), runs: [] } : null;
    if (PADV) {
        for (let i = 0; i < np_;) {
            let j = i;
            while (j + 1 < np_ && D.pads.frame[j + 1] === D.pads.frame[i]) j++;
            PADV.runs.push([D.pads.frame[i], i, j + 1]);
            i = j + 1;
        }
    }
    function padsEval() {
        // C5e: every pad vertex RIGID in its clamp frame (its rest place there, P.rig), its normal and tangent turned
        // with it: the pads keep their shape in every motion (C5d anchored the underside on the skin and blended the
        // flanks: pad 1's underside shortened 11-18 % in the swim). The cost pass: each run of vertices on one frame in
        // a tight loop on that frame's matrix (a clamp frame is a proper rotation: the turned normals and tangents stay
        // unit, as the per-vertex normalise left them to 1e-16; 1.4-1.9 ms a frame before, s12)
        if (!PADV) return;
        const Rg = PADV.rig, Nl = PADV.nrm, Tl = PADV.tan;
        for (const [f, i0, i1] of PADV.runs) {
            const e = fe(f);
            const a0 = e[0], a1 = e[1], a2 = e[2], b0 = e[4], b1 = e[5], b2 = e[6], c0 = e[8], c1 = e[9], c2 = e[10];
            const t0 = e[12], t1 = e[13], t2 = e[14];
            const unit = frames[f].kind === 'clamp';
            for (let i = i0; i < i1; i++) {
                const o = 3 * i, q = 4 * i;
                const x = Rg[o], y = Rg[o + 1], z = Rg[o + 2];
                padPos[o] = a0 * x + b0 * y + c0 * z + t0;
                padPos[o + 1] = a1 * x + b1 * y + c1 * z + t1;
                padPos[o + 2] = a2 * x + b2 * y + c2 * z + t2;
                let nx = a0 * Nl[o] + b0 * Nl[o + 1] + c0 * Nl[o + 2], ny = a1 * Nl[o] + b1 * Nl[o + 1] + c1 * Nl[o + 2],
                    nz = a2 * Nl[o] + b2 * Nl[o + 1] + c2 * Nl[o + 2];
                let tx = a0 * Tl[q] + b0 * Tl[q + 1] + c0 * Tl[q + 2], ty = a1 * Tl[q] + b1 * Tl[q + 1] + c1 * Tl[q + 2],
                    tz = a2 * Tl[q] + b2 * Tl[q + 1] + c2 * Tl[q + 2];
                if (!unit) {
                    const ln = Math.hypot(nx, ny, nz) || 1e-30, lt = Math.hypot(tx, ty, tz) || 1e-30;
                    nx /= ln; ny /= ln; nz /= ln; tx /= lt; ty /= lt; tz /= lt;
                }
                padNrm[o] = nx; padNrm[o + 1] = ny; padNrm[o + 2] = nz;
                padTan[q] = tx; padTan[q + 1] = ty; padTan[q + 2] = tz; padTan[q + 3] = Tl[q + 3];
            }
        }
    }
    const PH = stats.phase;
    const now = () => performance.now();
    function update() {
        const t0 = now();
        skin.updateMatrixWorld();
        if (samePose()) {
            // (a still pose: the last result stands, exactly as a re-make would give it)
            stats.reused++;
            const dt = now() - t0;
            stats.ms += dt;
            stats.frames++;
            return;
        }
        let t = t0, t1;
        skinVerts();
        if (PH) { t1 = now(); PH.skin += t1 - t; t = t1; }
        anchorsEval();
        if (PH) { t1 = now(); PH.anchors += t1 - t; t = t1; }
        contactRings();
        if (PH) { t1 = now(); PH.contact += t1 - t; t = t1; }
        framesEval();
        if (PH) { t1 = now(); PH.frames += t1 - t; t = t1; }
        ringsFixed();
        if (PH) { t1 = now(); PH.fixed += t1 - t; t = t1; }
        for (const s of SP) spanEval(s);
        if (PH) { t1 = now(); PH.spans += t1 - t; t = t1; }
        frameRings();
        if (PH) { t1 = now(); PH.rings += t1 - t; t = t1; }
        padsEval();
        if (PH) { t1 = now(); PH.pads += t1 - t; t = t1; }
        const dt = now() - t0;
        stats.ms += dt;
        stats.frames++;
        stats.maxMs = Math.max(stats.maxMs, dt);
        stats.lifted = SP.reduce((a, s) => Math.max(a, s.lifted), stats.lifted);
        stats.stretch = SP.reduce((a, s) => Math.max(a, Math.abs(s.stretch)), stats.stretch);
        stats.newton = Math.max(stats.newton, SP.reduce((a, s) => Math.max(a, s.newton), 0));
        stats.relaid = Math.max(stats.relaid || 0.0, relaid);
        stats.held = Math.max(stats.held || 0, held);
    }
    // the pads' CONTACTS in the bind space (the skin shader's contact AO and contact shadow read them: they follow the
    // skin because they live where the skin's own bind positions are): per pad its centre c, its DUAL axes gx (along the
    // hose) and gz (across it), its unit normal n, its half-length hl and half-width hw. C5e check: the footprint is
    // the bind space's image of the pad's underside rectangle by the AFFINE map that best carries its clamp frame's
    // (x, z) to the bind points of the anchors under the pad (least squares over its ~600 anchors: their rest places
    // f.loc, their bind points from the skin's own bind positions); a bind point p reads u = gx.(p - c), v = gz.(p - c),
    // the pad's own coordinates in mm at the reference pose, against the rectangle of the anchors' rest extents. The
    // forge's rectangle (c.c, c.x, c.n, hl, hw: the bind points' extents along a bind axis) is a box round a sheared,
    // stretched image of the pad, and on the posed skin its edge stood 0.1-3.0 mm (median per pad) outside the rigid
    // pad's (patches/scratch_check_c5e/k02_swim.py); a hose without clamp frames keeps the forge's rectangle exactly
    // (gx = x, gz = n x x)
    const clampIdx = frames.map((f, i) => (f.kind === 'clamp' ? i : -1)).filter((i) => i >= 0);
    const contacts = (D.contacts || []).map((c, ci) => {
        const n0 = new THREE.Vector3().fromArray(c.n), x0 = new THREE.Vector3().fromArray(c.x);
        const fit = clampIdx.length === (D.contacts || []).length ? footprintFit(clampIdx[ci], n0) : null;
        if (fit) return fit;
        return { c: new THREE.Vector3().fromArray(c.c), gx: x0.clone(), gz: new THREE.Vector3().crossVectors(n0, x0),
            n: n0, hl: c.hl, hw: c.hw };
    });
    function footprintFit(fi, nRef) {
        // the affine map (x, z) -> bind point over the clamp's anchors: p = p0 + a (x - x0) + b (z - z0), least squares;
        // its dual axes (the rows of [a b]'s pseudo-inverse); the rectangle: the extents in its clamp frame of the pad's
        // own rigid vertices (pad, strap and rivets: the pad's box bounds them), else of the anchors (on pad 1, over the
        // arm's root, the anchors' feet stood up to 0.6 mm inside the pad's edge)
        const f = frames[fi], A = D.anchors, n = f.anchors.length;
        if (n < 6) return null;
        const P = new Float64Array(3 * n);
        let px = 0, py = 0, pz = 0, xm = 0, zm = 0;
        let xlo = Infinity, xhi = -Infinity, zlo = Infinity, zhi = -Infinity;
        for (let i = 0; i < n; i++) {
            const a = f.anchors[i];
            for (let c = 0; c < 3; c++) {
                P[3 * i + c] = A[6 * a + 3] * VB[3 * A[6 * a] + c] + A[6 * a + 4] * VB[3 * A[6 * a + 1] + c]
                    + A[6 * a + 5] * VB[3 * A[6 * a + 2] + c];
            }
            px += P[3 * i]; py += P[3 * i + 1]; pz += P[3 * i + 2];
            const x = f.loc[3 * i], z = f.loc[3 * i + 2];
            xm += x; zm += z;
            xlo = Math.min(xlo, x); xhi = Math.max(xhi, x); zlo = Math.min(zlo, z); zhi = Math.max(zhi, z);
        }
        px /= n; py /= n; pz /= n; xm /= n; zm /= n;
        if (PADV) {
            let plo = Infinity, phi = -Infinity, qlo = Infinity, qhi = -Infinity;
            for (const [fr, i0, i1] of PADV.runs) {
                if (fr !== fi) continue;
                for (let i = i0; i < i1; i++) {
                    const x = PADV.rig[3 * i], z = PADV.rig[3 * i + 2];
                    plo = Math.min(plo, x); phi = Math.max(phi, x); qlo = Math.min(qlo, z); qhi = Math.max(qhi, z);
                }
            }
            if (phi > plo && qhi > qlo) { xlo = plo; xhi = phi; zlo = qlo; zhi = qhi; }
        }
        let sxx = 0, sxz = 0, szz = 0;
        const rx = [0, 0, 0], rz = [0, 0, 0];
        for (let i = 0; i < n; i++) {
            const x = f.loc[3 * i] - xm, z = f.loc[3 * i + 2] - zm;
            const d = [P[3 * i] - px, P[3 * i + 1] - py, P[3 * i + 2] - pz];
            sxx += x * x; sxz += x * z; szz += z * z;
            for (let c = 0; c < 3; c++) { rx[c] += d[c] * x; rz[c] += d[c] * z; }
        }
        const det = sxx * szz - sxz * sxz;
        if (!(det > 1e-24)) return null;
        // [a b] = R S^-1
        const a = new THREE.Vector3(), b = new THREE.Vector3();
        a.set(...[0, 1, 2].map((c) => (rx[c] * szz - rz[c] * sxz) / det));
        b.set(...[0, 1, 2].map((c) => (rz[c] * sxx - rx[c] * sxz) / det));
        const g11 = a.dot(a), g12 = a.dot(b), g22 = b.dot(b), gd = g11 * g22 - g12 * g12;
        if (!(gd > 1e-24)) return null;
        const gx = a.clone().multiplyScalar(g22 / gd).addScaledVector(b, -g12 / gd);
        const gz = b.clone().multiplyScalar(g11 / gd).addScaledVector(a, -g12 / gd);
        const xc = 0.5 * (xlo + xhi), zc = 0.5 * (zlo + zhi);
        const cc = new THREE.Vector3(px, py, pz).addScaledVector(a, xc - xm).addScaledVector(b, zc - zm);
        const nn = new THREE.Vector3().crossVectors(a, b).normalize();
        if (nn.dot(nRef) < 0) nn.negate();
        return { c: cc, gx, gz, n: nn, hl: 0.5 * (xhi - xlo), hw: 0.5 * (zhi - zlo), fi };
    }
    function contactSweeps(L, out) {
        // C5f (the lead's call 9): the pads' contact shadow WIDER ON THE SUN SIDE. L: the direction toward the sun in the
        // skin mesh's space (unit); per contact (out[2 k], out[2 k + 1]) the sweep of its footprint TOWARD the sun in the
        // pad's own coordinates (m; the footprint's u along the hose is its clamp frame's x, v across its z): L taken
        // into the clamp frame (its matrix's columns are its axes), its part across the pad's plane, as long as a rim
        // SHADOW_H tall casts at that elevation, at most SHADOW_MAX; none where the sun stands under the pad's plane or
        // for a footprint without a clamp frame. (Toward it: on the far side the hose's own cast shadow already takes the
        // sun's light off the skin by the pad, so only the sunward base shows the contact shadow, the faint line the C5e
        // check measured; swept away from the sun it changed no pixel of the pads film)
        for (let k = 0; k < contacts.length; k++) {
            const fi = contacts[k].fi;
            out[2 * k] = 0.0;
            out[2 * k + 1] = 0.0;
            if (fi == null) continue;
            const e = fe(fi);
            const lx = e[0] * L[0] + e[1] * L[1] + e[2] * L[2], ly = e[4] * L[0] + e[5] * L[1] + e[6] * L[2],
                lz = e[8] * L[0] + e[9] * L[1] + e[10] * L[2];
            const h = Math.hypot(lx, lz);
            if (ly <= 0.05 || h < 1e-6) continue;
            const len = Math.min(SHADOW_MAX, (SHADOW_H * h) / ly);
            out[2 * k] = (len * lx) / h;
            out[2 * k + 1] = (len * lz) / h;
        }
        return out;
    }
    return { update, stats, spans: SP, centres: C, sleevePos, sleeveNrm, sleeveTan, padPos, padNrm, padTan, contacts,
        contactSweeps, rings: N, sides: S, r, debug: DBG, frames };
}
