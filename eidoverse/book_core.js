// book_core.js — the hardcover book rig, engine-agnostic and asset-agnostic.
//
// This is the distillation of the janus-book build (work/book_janus, 2026-08):
// a case binding that opens like a case binding, and a text block whose pages
// turn like paper. Everything here is a pure function of a SPEC — no GLB, no
// globals, no material creation, no TSL. Adapters own those:
//
//   eidoverse-video  eidoverse/book.js          measures a GLB into a spec,
//                                               wires NodeMaterial page glow
//   eidoverse-worlds client/lib/book_core.js    vendored copy of this file;
//                                               the `book` comp evaluator
//                                               builds specs from comp data
//
// makeBookRig(THREE, spec, materials, hooks?) -> rig
//
//   spec = {
//     boardLen,   // board width, joint -> fore-edge          (m)
//     halfH,      // half the board height                    (m)
//     halfT,      // half the CLOSED outer thickness          (m)
//     boardTh,    // board + cloth thickness                  (m)   [0.0025]
//     lip,        // French groove width (joint -> spine lip) (m)   [0.0056]
//     round,      // spine bulge past the lip                 (m)   [0.0024]
//     uJoint,     // wrap-U at the joint (arc-length layout)        [0.4573]
//     pages,      // leaf count                                     [26]
//     openAt,     // leaves already on the left when open           [1]
//     angle,      // case opening sweep, degrees                    [180]
//     pageAngle,  // where a turned leaf lies, degrees              [179]
//     square,     // board overhang past pages, fore-edge (closed)  [0.0047]
//     squareHT,   // board overhang past pages, head/tail           [0.006]
//     gutterIn,   // how far the block tucks toward the spine       [0.0045]
//   }
//
//   materials = { cloth, lining, edge, spread }   THREE.Material instances.
//     cloth   the wrap: arc-length U (0 back fore-edge .. uJoint back joint
//             .. 0.5 spine apex .. 1-uJoint front joint .. 1 front fore-edge)
//     lining  endpaper; sampled u 0.05..0.40, so keep that span plain
//     edge    the block's cut edges (never tinted by scene code)
//     spread  template for page faces; cloned per leaf face
//
//   hooks = {
//     onPageFace(mat, tex|null)   called whenever a leaf face (a clone of
//                                 `spread`) gets its texture; the video
//                                 adapter adds the TSL translucency glow here
//   }
//
//   rig.setOpen(k)                0..1, closed -> lying open
//   rig.setPage(n)                n leaves turned onto the left, instantly
//   rig.poseTurn(phase)           the NEXT leaf mid-flight at phase 0..1
//                                 (state machine: setPage(page+1) when done)
//   rig.riffle(t, opts)           the film driver: timed sequential turns
//   rig.loadSpreads(textures)     page artwork; loader owns decode
//   rig.layFlat()                 rotate root so thickness is world +Y
//   rig.seatBox()                 closed-case Box3 in root space, for seating
//   rig.metrics / rig.codeSurfaces() / rig.pageMaterials()
//
// THE THREE IDEAS EVERYTHING ELSE SERVES
//
// 1. One strip, one parameter. The case is a single continuous mesh — the
//    unrolled bookcloth — skinned to one bone chain by arc length s, and the
//    wrap texture is arc-length parameterized at the same scale. Artwork,
//    geometry and rig cannot drift apart, and the cloth cannot tear, because
//    they are all views of the same coordinate.
//
// 2. Poses, not shapes. The bind pose is the strip laid FLAT; the closed book
//    is a pose (the cross-section's rest tangents), and opening adds rotation
//    into the two joint grooves — the spine round rotates almost as a unit,
//    which is what carries the front joint down so both boards finish flat.
//    Measured alternatives both fail: rotation through the spine straightens
//    it (asymmetric squares), a rigid spine strands the joint mid-air (the
//    cover becomes a ramp through the page block).
//
// 3. Pages are arcs. A sheet leaving the gutter is a circular arc meeting a
//    straight tail, tangent-continuous — arc-length parameterized, so paper
//    is inextensible by construction. On a bone chain that is one tangent-
//    angle schedule; chains are posed by SEGMENT-MIDPOINT tangents, which
//    lands chain vertices exactly on the arc (start-tangent posing bows off
//    it by millimetres).
//
// Hard-won constraints preserved from the build (each one was a visible bug):
//   - the fold is MEASURED off the posed joints every move; a formula in the
//     open amount outruns the case and pages escape through the spine cloth
//   - the whole book rides up on its own spine (lowest chain bone = contact)
//   - leaf stack height splits radius/root (TAPER_FRAC), root term shifted
//     non-negative; either extreme puts pages through the spine
//   - one monotonic fan across the whole block; two scales let landed leaves
//     lie FLATTER than the ones beneath and tails climb through each other
//   - rims are double-sided and never sample the wrap near the spine artwork
//   - the turn-in exists only where there is a board; the hollow is lined

(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.BookCore = factory();
})(typeof self !== 'undefined' ? self : globalThis, function () {
    'use strict';

    const DEFAULTS = {
        boardTh: 0.0025, lip: 0.0056, round: 0.0024, uJoint: 0.4573,
        pages: 26, openAt: 1, angle: 180, pageAngle: 179,
        square: 0.0047, squareHT: 0.006, gutterIn: 0.0045,
    };

    /** uJoint for a composed wrap: solved so texel density is uniform along
     *  the developed cross-section (board+lip vs the spine round). */
    function solveWrapLayout({ boardLen, lip, round, halfT }) {
        let arc = 0;
        let px = lip + round * Math.cos(-Math.PI / 2);
        let py = halfT * Math.sin(-Math.PI / 2);
        for (let i = 1; i <= 26; i++) {
            const ph = -Math.PI / 2 + Math.PI * (i / 26);
            const x = lip + round * Math.cos(ph), y = halfT * Math.sin(ph);
            arc += Math.hypot(x - px, y - py); px = x; py = y;
        }
        return (boardLen + lip) / (2 * (boardLen + lip) + arc);
    }

    let __rigSerial = 0;   // per-rig program-cache namespace (see RIG_TAG)

    function makeBookRig(THREE, specIn, materials, hooks = {}) {
        const spec = Object.assign({}, DEFAULTS, specIn);
        // The root origin need not bisect the board: a measured GLB keeps its
        // own origin (janus: joint at -0.0727, fore-edge at +0.0777), and the
        // scene's framing depends on it. Default = symmetric.
        if (spec.jointX === undefined) spec.jointX = spec.boardLen / 2;
        if (spec.foreX === undefined) spec.foreX = spec.boardLen - spec.jointX;
        const {
            boardLen: BOARD_LEN, halfH: HALF_H, halfT: HALF_T,
            boardTh: BOARD_TH, lip: LIP, round: SPINE_D, uJoint: U_JOINT,
            pages: N_LEAF, openAt, angle, pageAngle,
            square: SQUARE, squareHT: SQUARE_HT, gutterIn: GUTTER_IN,
        } = spec;
        const clothMat = materials.cloth;
        const innerMat = materials.lining || clothMat;
        const edgeMat = materials.edge || innerMat;
        const spreadMat = materials.spread || innerMat;
        // TRIM: the plain bookcloth that wraps board edges (rims) and folds
        // onto the board interiors (turn-ins). For a measured asset whose wrap
        // has plain cloth to sample (janus) this can BE the cloth material;
        // for composed wraps there is no plain region — the back cover's art
        // sits exactly where the old sampling looked, and it smeared onto
        // every edge of the case. Adapters pass a plain cloth here.
        // An explicit trim material is used AS-IS (cloning a NodeMaterial here
        // lost its map on this stack — the clone rendered white); only the
        // janus-style fallback, sharing the cloth texture, needs the clone so
        // DoubleSide doesn't leak onto the cover.
        const trimMat = materials.trim || clothMat.clone();
        trimMat.side = THREE.DoubleSide;
        const onPageFace = hooks.onPageFace || (() => {});
        // TSL: the leaf field computes its fold in the VERTEX STAGE, so the
        // rig needs the node-function namespace. Video's THREE carries TSL
        // merged (THREE.Fn exists); worlds passes it via hooks.tsl
        // (import * as tsl from 'three/tsl').
        const tsl = hooks.tsl || (typeof THREE.Fn === 'function' ? THREE : null);
        if (!tsl) throw new Error('[bookRig] no TSL: pass hooks.tsl (three/tsl) or a THREE build that includes it');
        const log = hooks.log || ((m) => console.log(m));

        // ---- shared helpers -------------------------------------------------

        // Skin a geometry to a chain by a per-vertex arc length, blending the
        // two bracketing bones so the surface stays smooth across bones.
        function skinByCoord(geo, coord, boneS) {
            const n = coord.length;
            const idx = new Uint16Array(n * 4);
            const wgt = new Float32Array(n * 4);
            const last = boneS.length - 1;
            for (let v = 0; v < n; v++) {
                const c = coord[v];
                let i = 0;
                while (i < last - 1 && boneS[i + 1] < c) i++;
                const span = Math.max(1e-9, boneS[i + 1] - boneS[i]);
                const f = Math.max(0, Math.min(1, (c - boneS[i]) / span));
                idx[v * 4] = i; idx[v * 4 + 1] = i + 1;
                wgt[v * 4] = 1 - f; wgt[v * 4 + 1] = f;
            }
            geo.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(idx, 4));
            geo.setAttribute('skinWeight', new THREE.Float32BufferAttribute(wgt, 4));
        }

        // A STRAIGHT chain along local +X at the given arc positions. The bind
        // pose is straight; ALL shape — including the case's rest curvature —
        // comes from posing, so the bind matrix can never disagree with it.
        function makeChain(boneS) {
            const bones = [];
            for (let i = 0; i < boneS.length; i++) {
                const b = new THREE.Bone();
                b.name = `b${i}`;
                b.position.x = i === 0 ? boneS[0] : boneS[i] - boneS[i - 1];
                if (i > 0) bones[i - 1].add(b);
                bones.push(b);
            }
            return bones;
        }

        function bindSkinned(geo, mat, bones, parent) {
            const mesh = new THREE.SkinnedMesh(geo, mat);
            parent.add(mesh);
            mesh.add(bones[0]);
            mesh.updateMatrixWorld(true);
            mesh.bind(new THREE.Skeleton(bones));
            // Culling stays ON: the naive reason to disable it (posed verts
            // leave the bind bbox) is answered by the generous spheres below,
            // which the frustum test uses. With it off, every book in a world
            // drew all ~120 calls per frame even fully off-screen — the
            // opposite of what a many-visitor server needs.
            mesh.frustumCulled = true;
            mesh.userData.noSupportCheck = true;
            // ...and give raycasters a sphere that contains the posed verts.
            // BOTH spheres: Mesh.raycast reads the geometry's, but
            // SkinnedMesh.raycast (three r158+) reads the mesh-level one —
            // and computes it ONCE from the current pose if left null, so a
            // sphere cached at the closed pose silently skips the swung-open
            // board and rays report phantom page escapes behind it.
            geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1);
            mesh.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1);
            return mesh;
        }

        // Segment-midpoint tangent angles -> per-bone LOCAL rotations.
        function poseChain(bones, dirAt) {
            let prev = 0;
            for (let i = 0; i < bones.length; i++) {
                const a = dirAt(i);
                bones[i].rotation.z = a - prev;
                prev = a;
            }
        }

        function frame(parent, X, Y, Z, origin) {
            const g = new THREE.Group();
            g.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, Y, Z));
            g.position.copy(origin);
            parent.add(g);
            return g;
        }
        const EX = () => new THREE.Vector3(1, 0, 0);
        const EY = () => new THREE.Vector3(0, 1, 0);
        const EZ = () => new THREE.Vector3(0, 0, 1);

        // ---- frames ---------------------------------------------------------
        // root:  the book's own node (thickness +z until layFlat)
        // body:  everything hangs here so the book can RIDE UP on its spine —
        //        opening rolls the round to face down, below the seating plane
        // caseFrame: X back-fore-edge -> spine -> front-fore-edge, Y out
        //        through the front cover, Z the turning axis; origin at the
        //        cross-section's START (the back board's fore-edge)
        const root = new THREE.Group();
        root.name = 'book';
        const body = new THREE.Group();
        root.add(body);
        const JOINT_X = spec.jointX;
        const FORE_X = spec.foreX;
        const caseFrame = frame(body, EX().negate(), EZ(), EY(),
            new THREE.Vector3(FORE_X, 0, -HALF_T));

        // =====================================================================
        // THE CASE — one continuous strip on one bone chain
        // =====================================================================

        // The cross-section, walked once as a polyline in caseFrame's XY plane;
        // each sample carries arc length s and wrap coordinate u. U runs
        // CONTINUOUSLY through both joint grooves — a groove with zero U width
        // smears one texel column across its 5.6 mm (the "stretched patch"),
        // so each groove borrows its share of u from the board beside it
        // (compressing that board's artwork ~3.6%: invisible).
        const CS = [];
        const push = (x, y, u) => {
            const p = { x, y, u, s: 0 };
            if (CS.length) {
                const q = CS[CS.length - 1];
                p.s = q.s + Math.hypot(x - q.x, y - q.y);
            }
            CS.push(p);
        };
        const NB = 43, NS = 26;
        const U_BOARD = U_JOINT * BOARD_LEN / (BOARD_LEN + LIP);
        for (let i = 0; i <= NB; i++) {                       // back board
            const f = i / NB;
            push(-FORE_X + f * BOARD_LEN, -HALF_T, f * U_BOARD);
        }
        const I_GROOVE_B = CS.length - 1;
        push(JOINT_X + LIP, -HALF_T, U_JOINT);                // back groove
        for (let i = 1; i <= NS; i++) {                       // spine round
            const ph = -Math.PI / 2 + Math.PI * (i / NS);
            push(JOINT_X + LIP + SPINE_D * Math.cos(ph), HALF_T * Math.sin(ph),
                 U_JOINT + (1 - 2 * U_JOINT) * (i / NS));
        }
        const I_GROOVE_F0 = CS.length - 1;
        push(JOINT_X, HALF_T, (1 - U_JOINT) + (U_JOINT - U_BOARD));  // front groove
        const I_GROOVE_F1 = CS.length - 1;
        for (let i = 1; i <= NB; i++) {                       // front board
            const f = i / NB;
            push(JOINT_X - f * BOARD_LEN, HALF_T,
                 (1 - U_JOINT) + (U_JOINT - U_BOARD) + f * U_BOARD);
        }
        for (let i = 0; i < CS.length; i++) {                 // tangents + normals
            const a = CS[Math.max(0, i - 1)], b = CS[Math.min(CS.length - 1, i + 1)];
            const tx = b.x - a.x, ty = b.y - a.y;
            const l = Math.hypot(tx, ty) || 1;
            CS[i].ang = Math.atan2(ty, tx);
            CS[i].nx = ty / l; CS[i].ny = -tx / l;
        }
        const S_END = CS[CS.length - 1].s;
        const S_BEND0 = CS[I_GROOVE_B].s;
        const S_BEND1 = CS[I_GROOVE_F1].s;
        const S_GROOVE_F = CS[I_GROOVE_F0].s;
        const S_GROOVE_B = CS[I_GROOVE_B + 1].s;

        // Bone chain along s: dense across the spine and grooves, sparse on
        // the rigid boards.
        const caseBoneS = [0];
        for (let i = 1; i <= 3; i++) caseBoneS.push(S_BEND0 * (i / 3));
        for (let i = 1; i <= 24; i++)
            caseBoneS.push(S_BEND0 + (S_BEND1 - S_BEND0) * (i / 24));
        for (let i = 1; i <= 4; i++)
            caseBoneS.push(S_BEND1 + (S_END - S_BEND1) * (i / 4));
        const caseBones = makeChain(caseBoneS);

        // THE SPINE BAND — how the case opens. Every mechanism that keeps the
        // cloth's full length has to put it somewhere when the boards lie
        // flat: rotate the strip flat (joints a spine-width apart → the
        // block, whose fold is measured between the joints, slid ~40 mm
        // along its own board: the squish), let it hang in a loop (below
        // the desk: "the spine clips into the desk"), or arch it up (through
        // the block's throw-up). None survives her eyes. So the band is
        // posed, not conserved:
        //   closed        — the rest chain, exactly (rims flat, round bulging)
        //   rims          — the groove cloth TIGHTENS over the first third of
        //                   the sweep (the hinge hugs the block; no hairpins)
        //   round         — a rigid spine that tilts toward the desk and, over
        //                   the second half, COMPRESSES uniformly into the gap
        //                   under the gutter (its title squashes where the
        //                   boards and pages hide it)
        //   front rim+board — rotate through the sweep as before
        // Nothing ever drops below the board plane, nothing crosses the
        // block, the joints end ~0.15 T apart, and the fold's travel stays
        // under a centimetre on a 1000-page tome. Bones carry their segment
        // length in position.x, so compression is a per-bone length scale.
        const isBackRim = (s) => s > S_BEND0 + 1e-6 && s <= S_GROOVE_B + 1e-6;
        const isRound = (s) => s > S_GROOVE_B + 1e-6 && s < S_GROOVE_F - 1e-6;
        const isFrontRim = (s) => s >= S_GROOVE_F - 1e-6 && s < S_BEND1 - 1e-6;
        const smooth01 = (t) => { t = Math.min(1, Math.max(0, t)); return t * t * (3 - 2 * t); };
        // THE CASE IS A FOUR-BAR. Back board fixed; the spine inlay hinged to it
        // at the back groove; the front board hinged to the inlay's far end.
        // Nothing compresses (cloth and card do not): the cover swings on the
        // standing spine until it is upright, then, as it leans past vertical,
        // the spine TIPS BACK onto the desk under it — the front joint descends
        // continuously — and the round unbends as it lies down, so the open
        // case is back board, a flat spine a full spine's width, front board:
        // exactly what a thick hardcover shows lying open. (The previous band
        // compressed the round to 15% and collapsed it in the last 15% of the
        // sweep: the cover rode 55 mm up in the air and dropped, and the open
        // book had no spine at all.)
        // THE CASE FOLLOWS THE READING. Where the spine goes when the cover is
        // open depends on where the block is. Mid-book the two stacks pull it
        // flat onto the desk and the block's spine throws up over it (the
        // hollow back). At the first page the block is whole on the back
        // board and the spine stays wrapped round it, standing; the cover
        // hinges at the top of that spine — a board's length from its far
        // edge, a block's height up — so it cannot lie flat: it PROPS, its far
        // edge on the desk at asin(height / length) (a 5 cm tome: 20°; a
        // novel: 6°). At the last page the mirror: the spine hangs from the
        // raised back joint and the BACK board props on its fore-edge.
        // Everything is continuous in the page fraction f: the spine's tip
        // runs 0 → 90° → 180° across the book and its round straightens only
        // around the middle. Over the sweep (k) the cover swings on the
        // standing spine until upright, then the spine tips as the cover
        // leans past vertical.
        const sweep = (k) => smooth01((k - 0.5) / 0.5);
        const tipTarget = (f) => Math.PI * f;                                  // at k = 1
        const flatTarget = (f) => smooth01(2 * Math.min(f, 1 - f));            // round straightened, at k = 1
        const caseState = { f: 0.5, c: 0, tip: 0, beta: 0, alpha: 0 };
        function caseDirAt(i, k, sign) {
            const s = caseMidS[i], rest = restAng(s);
            if (isRound(s)) return rest + (Math.PI / 2 - rest) * caseState.c + sign * caseState.tip;
            if (isFrontRim(s) || s >= S_BEND1 - 1e-6)
                return rest + sign * (OPEN_DEG * Math.PI / 180 + caseState.alpha) * k;
            return rest - sign * caseState.beta;                  // back board + back rim: the prop
        }
        const caseScaleAt = () => 1;
        // Compression is a bone SCALE, not a bone spacing: skinned vertices
        // keep their bind offset from their bone, so bunching the bones left
        // the rim's 12 mm of cloth hanging off them as a grey band between
        // spine and cover. But a rotation inside a parent's non-uniform scale
        // is a SHEAR, so the scale cannot ride the hierarchy either (it put
        // the hinge 70 mm up and the cloth under the desk). Each bone's local
        // matrix is therefore written directly:
        //   local = T(L) · S(parent)⁻¹ · Rz(Δangle) · S(own)
        // which composes to  rigid(parent) · T(parentScale·L) · Rz · S(own):
        // the parent's scale shortens THIS segment, this bone's frame stays
        // rigid, and its own scale compresses only the cloth bound to it.
        const _mSi = new THREE.Matrix4(), _mR = new THREE.Matrix4(), _mS = new THREE.Matrix4();
        function writeCase(dirAt, scaleAt) {
            let prevA = 0, prevS = 1;
            for (let i = 0; i < caseBones.length; i++) {
                const b = caseBones[i];
                const a = dirAt(i), s = scaleAt(i);
                const L = i === 0 ? caseBoneS[0] : caseBoneS[i] - caseBoneS[i - 1];
                b.matrixAutoUpdate = false;
                b.matrix.makeTranslation(L, 0, 0)
                    .multiply(_mSi.makeScale(1 / prevS, 1, 1))
                    .multiply(_mR.makeRotationZ(a - prevA))
                    .multiply(_mS.makeScale(s, 1, 1));
                b.matrixWorldNeedsUpdate = true;
                prevA = a; prevS = s;
            }
        }
        const _gv = new THREE.Vector3();
        function grooveY(bone) {                          // a groove's height over the desk (caseFrame y)
            caseBones[0].updateMatrixWorld(true);
            bone.getWorldPosition(_gv);
            caseFrame.worldToLocal(_gv);
            return _gv.y;
        }
        let B_GB = 0, B_GF = 0, HINGE_R = 1;              // set once the chain exists (below)
        function poseCase(k, sign, f = 0.5) {
            const sw = sweep(k);
            caseState.f = f;
            caseState.tip = tipTarget(f) * sw;
            caseState.c = flatTarget(f) * sw;
            caseState.beta = 0; caseState.alpha = 0;
            const write = () => writeCase((i) => caseDirAt(i, k, sign), (i) => caseScaleAt(i, k));
            write();
            // a spine tipped past flat would hang below the desk — and a
            // tipping round's first corner digs into it: the back board props
            // on its fore-edge by just enough to lift the lowest of them to it
            let yg0 = grooveY(caseBones[B_GF]);
            for (let i = B_GB; i < B_GF; i++) yg0 = Math.min(yg0, grooveY(caseBones[i]));
            if (yg0 < -1e-6) { caseState.beta = Math.asin(Math.min(1, -yg0 / HINGE_R)); write(); }
            // the front board falls no further than the desk: with its groove
            // this high, its far edge lands at −asin(h / R) — the prop
            const yg = grooveY(caseBones[B_GF]);
            caseState.alpha = yg > 1e-6 ? Math.asin(Math.min(1, yg / HINGE_R)) : 0;
            write();
        }
        function bindRestCase() {
            writeCase(() => 0, () => 1);
        }
        const caseMidS = caseBoneS.map((v, i) =>
            i < caseBoneS.length - 1 ? (v + caseBoneS[i + 1]) / 2 : v);

        function restAng(s) {
            let i = 0;
            while (i < CS.length - 2 && CS[i + 1].s < s) i++;
            const span = Math.max(1e-9, CS[i + 1].s - CS[i].s);
            const f = (s - CS[i].s) / span;
            const a0 = CS[i].ang; let a1 = CS[i + 1].ang;
            while (a1 - a0 > Math.PI) a1 -= 2 * Math.PI;
            while (a0 - a1 > Math.PI) a1 += 2 * Math.PI;
            return a0 + (a1 - a0) * f;
        }

        // Which rotation sense opens the cover, measured at MID-sweep (the end
        // states are indistinguishable: 180±angle both land near flat; only
        // the route differs — up over the top vs down through the desk). The
        // chain needs no scene parent for this: bones compose their own world.
        const OPEN_DEG = angle, PAGE_DEG = pageAngle;
        const nearestBone = (target) => caseBoneS.reduce((best, v, i) =>
            Math.abs(v - target) < Math.abs(caseBoneS[best] - target) ? i : best, 0);
        const B_BACK = nearestBone(S_BEND0), B_FRONT = nearestBone(S_BEND1);
        B_GB = nearestBone(S_GROOVE_B); B_GF = nearestBone(S_GROOVE_F);
        HINGE_R = LIP + BOARD_LEN;                       // front groove -> the cover's far edge
        let openSign = -1;
        let foldOpenSep = S_BEND1 - S_BEND0;   // fallback: fully developed
        let tubeDepth = 0;                     // closed spine hollow, joint -> round interior
        {
            const _p = new THREE.Vector3(), _q = new THREE.Vector3();
            const poseK = (sg, k) => {
                poseCase(k, sg);
                caseBones[0].updateMatrixWorld(true);
            };
            const tipY = (sg) => {
                poseK(sg, 0.5);
                return caseBones[caseBones.length - 1].getWorldPosition(_p).y;
            };
            const up = tipY(1), dn = tipY(-1);
            openSign = up >= dn ? 1 : -1;
            // The OPEN joint separation, measured off the posed chain — this is
            // what sizes the turn-in so the pasted panel meets the pages. A
            // fixed panel width kept the janus-era value while the open square
            // moved, and the panel edge missed the page edge by ~6 mm.
            poseK(openSign, 1);
            caseBones[B_BACK].getWorldPosition(_p);
            caseBones[B_FRONT].getWorldPosition(_q);
            foldOpenSep = Math.abs(_q.x - _p.x);
            // The CLOSED spine hollow: from the joint line to the round's
            // interior. A flat-backed block leaves all of it visible down the
            // head slot — an unread shadow line on a 22 mm book, an open cave
            // on a 75 mm one. Measured here so the block can be ROUNDED into
            // it (the binder's rounding-and-backing), sized to the real tube.
            poseK(openSign, 0);
            const jointX = caseBones[B_BACK].getWorldPosition(_p).x;
            let apexX = jointX;
            for (let i = B_BACK; i <= B_FRONT; i++) {
                const x = caseBones[i].getWorldPosition(_q).x;
                if (Math.abs(x - jointX) > Math.abs(apexX - jointX)) apexX = x;
            }
            tubeDepth = Math.max(0, Math.abs(apexX - jointX) - BOARD_TH);
            bindRestCase();                       // back to bind rest
        }
        // Rounding amplitude: the block's spine edge bows into the hollow,
        // deepest at mid-stack, leaving a real clearance to the cloth. The
        // fore-edge goes correspondingly concave — as on any thick book.

        // ---- the strip mesh, authored FLAT ----------------------------------
        // Rest shape = the unrolled cloth: a straight ribbon along +X, cloth
        // face -Y, board thickness +Y. Closed is a pose; authoring the curved
        // cross-section instead bakes a constant offset into every skinned
        // section (the bind chain is straight) and the case comes apart.
        const ROWS = 2;
        const casePos = [], caseNor = [], caseUv = [], caseCoord = [];
        const idxOuter = [], idxInner = [], idxRim = [], idxInlay = [];
        const zAt = (j) => HALF_H - (2 * HALF_H) * (j / ROWS);
        const vAt = (j) => j / ROWS;

        // The lining walks a narrow plain window of the endpaper texture; the
        // rims ping-pong through plain back-board cloth at the wrap's own
        // metre scale (never reaching the spine artwork), with real 2D extent
        // across the strip — a rim whose two vertices share a uv smears one
        // texel column around the whole edge.
        // Two lining mappings. 'window' walks a narrow plain span of the
        // texture — right for the janus endpaper, whose art bakes the whole
        // interior into one image at its own layout. 'fit' is the TEMPLATE
        // contract: the interior of an opened empty case is ONE continuous
        // paper field across both boards AND the spine, framed by the cloth
        // turn-in — so the endpaper image spans that whole field once,
        // u proportional to developed arc length, v to height. Uniform
        // density everywhere: nothing can stretch, and a standard landscape
        // endpaper scan drops straight in.
        const LINING_FIT = spec.liningFit === true;
        // fit-mode orientation measured off the labeled endpaper: the field
        // reads upright with the open book head-up after a 180° turn of the
        // naive mapping (u and v both flip).
        const U_LINING = (s) => LINING_FIT ? (1 - s / S_END)
            : 0.05 + 0.35 * (s / S_END);
        const V_LINING = (v) => LINING_FIT ? (1 - v) : v;
        const RIM_RATE = U_JOINT / (BOARD_LEN + LIP);
        const RIM_SPAN = 0.35;
        const U_RIM = (t) => {
            const p = ((t * RIM_RATE) % (2 * RIM_SPAN) + 2 * RIM_SPAN) % (2 * RIM_SPAN);
            return 0.05 + (p < RIM_SPAN ? p : 2 * RIM_SPAN - p);
        };
        const RIM_DU = BOARD_TH * RIM_RATE;
        const RIM_DV = BOARD_TH / (2 * HALF_H);

        // The turn-in: cloth folds over the board edges onto the inside, and
        // the endpaper is pasted down INSIDE that fold, so each board interior
        // is a cloth border framing a paper panel. It exists only where there
        // is a BOARD — the hollow between the joints is lined, not wrapped
        // (running it across the spine put the gold spine stamping on the
        // book's top edge). Fore-edge width tracks the OPEN square, head/tail
        // the closed one, so the panel frames the pages when you actually see
        // it. Widths snap to cross-section samples for a crisp paste line.
        // Head/tail paste line TUCKS UNDER the block (fit mode): at
        // TI_HEAD = SQUARE_HT exactly, the cloth->endpaper seam sat right at
        // the page edge, visible down the closed book's head slot along with
        // the fore-edge mismatch running off it. Real endpapers end under the
        // pages, and head/tail never slide with opening, so the tuck hides
        // the seam in BOTH states. (The janus window mapping keeps the exact
        // square — its interior art bakes its own layout.)
        const TI_HEAD = SQUARE_HT + (LINING_FIT ? 0.003 : 0);
        // Fore-edge turn-in width = the OPEN square, derived from the same
        // numbers the pages obey (root lands fold-centred when open; a leaf
        // reaches boardLen - square + gutterIn past it) — so the pasted
        // panel's edge MEETS the page edge with the book lying open, for any
        // book, instead of tracking a fixed fraction tuned on janus.
        const TI_FORE = Math.max(BOARD_LEN * 2 / NB,
            SQUARE - GUTTER_IN + foldOpenSep / 2);
        const OUT_Z = [], IN_Z = [HALF_H, HALF_H - TI_HEAD, HALF_H * 0.45, 0,
            -HALF_H * 0.45, -(HALF_H - TI_HEAD), -HALF_H];
        for (let j = 0; j <= ROWS; j++) OUT_Z.push(zAt(j));
        // Fore-edge turn-ins exist only where there is a board. The head/tail
        // band is different: real cloth wraps over the spine ends too (the
        // HEADCAPS), and with trim now a dedicated plain material there is no
        // artwork to bleed — so under liningFit the band runs the full width,
        // and the HOLLOW between the joints is cloth-backed rather than bare
        // lining (a real case shows cloth down the open gutter). The measured
        // janus asset keeps its approved cream hollow: its trim shares the
        // wrap texture, where the band over the spine would sample the gold
        // stamping — the exact bug that once banished spine turn-ins.
        const ON_BOARD = (s) => s < S_BEND0 || s > S_BEND1;
        const IS_TURNIN = (s, z) =>
            (ON_BOARD(s) && (s < TI_FORE || S_END - s < TI_FORE))
            || (HALF_H - Math.abs(z) < TI_HEAD);

        (function outerStrip() {
            const NR = OUT_Z.length, base = casePos.length / 3;
            for (let i = 0; i < CS.length; i++)
                for (let j = 0; j < NR; j++) {
                    casePos.push(CS[i].s, 0, OUT_Z[j]);
                    caseNor.push(0, -1, 0);
                    caseUv.push(CS[i].u, (HALF_H - OUT_Z[j]) / (2 * HALF_H));
                    caseCoord.push(CS[i].s);
                }
            for (let i = 0; i < CS.length - 1; i++)
                for (let j = 0; j < NR - 1; j++) {
                    const a = base + i * NR + j, b = a + 1;
                    const c = base + (i + 1) * NR + j, d = c + 1;
                    idxOuter.push(a, b, c, b, d, c);
                }
        })();

        // Interior: two complete vertex sets over one grid — pastedown UVs and
        // cloth UVs — each quad drawn from whichever set its centroid belongs
        // to. Crisp paste line, no UV ramp. The cloth set MIRRORS the wrap
        // into the plain back-board half (u -> 1-u past 0.5): the front
        // board's artwork must never appear inside, and the mirrored
        // coordinate keeps the weave at natural size.
        // THE GROOVES. The strip is a board's thickness on the boards, cloth
        // alone over the joints (T_JOINT), a card inlay over the spine
        // (T_SPINE): lying open the case reads as board · groove · spine ·
        // groove · board, not one flat slab, and the shut block's spine
        // overhangs a real hollow at the joints.
        // kraft-backed open-weave cloth: a 1 cm tile, ten threads each way
        function mullTexture() {
            const S = 256;
            const { c, ctx } = canvas2d(S, S);
            ctx.fillStyle = '#a3855f';
            ctx.fillRect(0, 0, S, S);
            let seed = 7;
            const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
            for (let i = 0; i < 5000; i++) {               // paper fibre
                const g = 40 + rnd() * 70;
                ctx.fillStyle = `rgba(${g | 0},${(g * 0.78) | 0},${(g * 0.5) | 0},${0.05 + rnd() * 0.12})`;
                ctx.fillRect(rnd() * S, rnd() * S, 1 + rnd() * 3, 1);
            }
            const pitch = S / 10;
            for (let k = 0; k < 10; k++) {                 // the threads, wandering periodically
                const o = k * pitch + pitch / 2;
                for (const [col, w, dy] of [['rgba(64,48,28,0.42)', 1.4, 0], ['rgba(214,192,156,0.30)', 0.8, 1.2]]) {
                    ctx.strokeStyle = col; ctx.lineWidth = w;
                    ctx.beginPath();
                    for (let x = 0; x <= S; x += 4) {
                        const y = o + dy + 0.9 * Math.sin((x / S) * Math.PI * 2 * 3 + k);
                        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                    }
                    ctx.stroke();
                    ctx.beginPath();
                    for (let y = 0; y <= S; y += 4) {
                        const x = o + dy + 0.9 * Math.sin((y / S) * Math.PI * 2 * 3 + k * 1.7);
                        if (y === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                    }
                    ctx.stroke();
                }
            }
            const t = new THREE.CanvasTexture(c);
            t.wrapS = t.wrapT = THREE.RepeatWrapping;
            t.colorSpace = THREE.SRGBColorSpace;
            t.anisotropy = 4;
            return t;
        }
        const mullMat = new THREE.MeshStandardNodeMaterial();
        mullMat.map = mullTexture();
        mullMat.roughness = 0.96;
        mullMat.side = THREE.DoubleSide;
        const T_JOINT = Math.min(BOARD_TH, 0.0003), T_SPINE = Math.min(BOARD_TH, 0.0008);
        const thickAt = (sv) => {
            const ease = (t) => { t = Math.min(1, Math.max(0, t)); return t * t * (3 - 2 * t); };
            if (sv <= S_BEND0) return BOARD_TH - (BOARD_TH - T_JOINT) * ease((sv - (S_BEND0 - 0.004)) / 0.004);
            if (sv >= S_BEND1) return BOARD_TH - (BOARD_TH - T_JOINT) * ease(((S_BEND1 + 0.004) - sv) / 0.004);
            if (sv < S_GROOVE_B) return T_JOINT + (T_SPINE - T_JOINT) * ease((sv - (S_GROOVE_B - 0.004)) / 0.004);
            if (sv > S_GROOVE_F) return T_JOINT + (T_SPINE - T_JOINT) * ease(((S_GROOVE_F + 0.004) - sv) / 0.004);
            return T_SPINE;
        };
        (function innerSurface() {
            const NR = IN_Z.length;
            const baseP = casePos.length / 3;
            for (let i = 0; i < CS.length; i++)
                for (let j = 0; j < NR; j++) {
                    casePos.push(CS[i].s, thickAt(CS[i].s), IN_Z[j]);
                    caseNor.push(0, 1, 0);
                    caseUv.push(U_LINING(CS[i].s),
                        V_LINING((HALF_H - IN_Z[j]) / (2 * HALF_H)));
                    caseCoord.push(CS[i].s);
                }
            const baseC = casePos.length / 3;
            for (let i = 0; i < CS.length; i++)
                for (let j = 0; j < NR; j++) {
                    casePos.push(CS[i].s, thickAt(CS[i].s), IN_Z[j]);
                    caseNor.push(0, 1, 0);
                    // U_RIM, not mirrored wrap: the mirror lands on the spine
                    // stamping at u~0.5, which is what once forced the head
                    // band to stop at the boards and left a pale notch in the
                    // gutter's ends; the ping-pong walks plain cloth only, so
                    // the band can run the full width on every book.
                    caseUv.push(U_RIM(CS[i].s), (HALF_H - IN_Z[j]) / (2 * HALF_H));
                    caseCoord.push(CS[i].s);
                }
            // THE SPINE INLAY: over the round the case's inside is the stiff
            // kraft strip the cloth is glued to, not the endpaper — it is
            // what you see on the floor of the hollow when the book lies open
            const baseI = casePos.length / 3;
            for (let i = 0; i < CS.length; i++)
                for (let j = 0; j < NR; j++) {
                    casePos.push(CS[i].s, thickAt(CS[i].s), IN_Z[j]);
                    caseNor.push(0, 1, 0);
                    caseUv.push(CS[i].s / 0.01, IN_Z[j] / 0.01);
                    caseCoord.push(CS[i].s);
                }
            for (let i = 0; i < CS.length - 1; i++)
                for (let j = 0; j < NR - 1; j++) {
                    const sc = (CS[i].s + CS[i + 1].s) / 2;
                    const zc = (IN_Z[j] + IN_Z[j + 1]) / 2;
                    const turn = IS_TURNIN(sc, zc);
                    const inlay = !turn && sc > S_GROOVE_B && sc < S_GROOVE_F;
                    const b = turn ? baseC : inlay ? baseI : baseP;
                    const a = b + i * NR + j, bb = a + 1;
                    const c = b + (i + 1) * NR + j, dd = c + 1;
                    (turn ? idxRim : inlay ? idxInlay : idxInner).push(a, c, bb, bb, c, dd);
                }
        })();

        // Rims: head/tail bands + the two fore-edges, closing the case from
        // every angle. Drawn double-sided — at 2.5 mm that costs nothing and
        // makes them immune to winding mistakes (both fore-edge bands once
        // faced inward and the case had a hole at each end).
        function edgeBand(j) {
            const base = casePos.length / 3;
            const z = zAt(j), nz = j === 0 ? 1 : -1;
            for (let i = 0; i < CS.length; i++)
                for (const y of [0, thickAt(CS[i].s)]) {
                    casePos.push(CS[i].s, y, z);
                    caseNor.push(0, 0, nz);
                    const off = (y === 0 ? 0 : (j === 0 ? -RIM_DV : RIM_DV));
                    caseUv.push(U_RIM(CS[i].s), vAt(j) + off);
                    caseCoord.push(CS[i].s);
                }
            for (let i = 0; i < CS.length - 1; i++) {
                const a = base + i * 2, b = a + 1, c = a + 2, d = a + 3;
                if (nz > 0) idxRim.push(a, c, b, b, c, d);
                else idxRim.push(a, b, c, b, d, c);
            }
        }
        edgeBand(0);
        edgeBand(ROWS);
        function foreBand(i, outward) {
            const base = casePos.length / 3;
            const c = CS[i];
            for (let j = 0; j <= ROWS; j++)
                for (const y of [0, BOARD_TH]) {
                    casePos.push(c.s, y, zAt(j));
                    caseNor.push(outward, 0, 0);
                    const u0 = 0.20 + (y === 0 ? 0 : outward * RIM_DU);
                    caseUv.push(u0, vAt(j));
                    caseCoord.push(c.s);
                }
            for (let j = 0; j < ROWS; j++) {
                const a = base + j * 2, b = a + 1, cc = a + 2, d = a + 3;
                if (outward > 0) idxRim.push(a, cc, b, b, cc, d);
                else idxRim.push(a, b, cc, b, d, cc);
            }
        }
        foreBand(0, -1);
        foreBand(CS.length - 1, 1);

        const caseGeo = new THREE.BufferGeometry();
        caseGeo.setAttribute('position', new THREE.Float32BufferAttribute(casePos, 3));
        caseGeo.setAttribute('normal', new THREE.Float32BufferAttribute(caseNor, 3));
        caseGeo.setAttribute('uv', new THREE.Float32BufferAttribute(caseUv, 2));
        caseGeo.setIndex([...idxOuter, ...idxInner, ...idxRim, ...idxInlay]);
        caseGeo.addGroup(0, idxOuter.length, 0);
        caseGeo.addGroup(idxOuter.length, idxInner.length, 1);
        caseGeo.addGroup(idxOuter.length + idxInner.length, idxRim.length, 2);
        caseGeo.addGroup(idxOuter.length + idxInner.length + idxRim.length, idxInlay.length, 3);
        skinByCoord(caseGeo, caseCoord, caseBoneS);

        const caseMesh = bindSkinned(caseGeo, [clothMat, innerMat, trimMat, mullMat],
                                     caseBones, caseFrame);
        caseMesh.name = 'case';


        // =====================================================================
        // THE PAGES — a stack of skinned leaves posed by the arc rule
        // =====================================================================

        // Gutter radius DERIVES from the case interior (chain roots sit on the
        // back board's inner face; the arc rises exactly one radius), so flat
        // pages land at their own stack height by construction.
        const PAGE_R = HALF_T - BOARD_TH;
        // Stack height splits between radius (the taper into the binding) and
        // root height, root term shifted non-negative. Both extremes were
        // rendered and measured to put pages through the spine: all-radius
        // spreads radii 1..20 mm and the reach-compensating walk marches the
        // deep leaves out through the cloth; a centred split puts upper roots
        // BELOW the board and they stab down through it. TAPER_FRAC must stay
        // under 1 - 2*TH_FRAC so root separation clears sheet thickness.
        const TAPER_FRAC = 0.30;
        const TH_FRAC = 0.32;       // paper as a share of its slot (~0.28 mm air)
        const CLEAR = 0.0016;       // air under the pastedown
        const BLOCK_H = (PAGE_R - CLEAR) / (1 + 2 * TH_FRAC / N_LEAF);
        const PAGE_R_EFF = PAGE_R - BLOCK_H * (1 - TAPER_FRAC);
        // A leaf's gutter arc eats r*(PI/2 - 1) of horizontal reach before the
        // flat tail starts; the cut is longer by exactly that, plus gutterIn
        // (the block tucks toward the spine to fill the hollow you can see
        // into at the head), so neither moves the fore-edge square.
        const REACH_LOSS = PAGE_R_EFF * (Math.PI / 2 - 1);
        // + the fold's depth into the round beyond the joint line: sitting in
        // the round, the folds are that much further spine-ward than the joint
        const LEAF_W = BOARD_LEN - SQUARE + GUTTER_IN + REACH_LOSS + Math.min(0.006, 0.4 * tubeDepth);
        const LEAF_H = HALF_H * 2 - 2 * SQUARE_HT;
        const LEAF_TH = (BLOCK_H * 2 / N_LEAF) * TH_FRAC;

        const pageFrame = frame(body, EX(), EZ(), EY().negate(),
            new THREE.Vector3(-(JOINT_X + GUTTER_IN), 0, -(HALF_T - BOARD_TH)));

        // Quadratic spacing: the whole gutter curl lives in the first ~18 mm.
        const LEAF_BONES = 12, LEAF_SEGS = 22;
        const along = (k, n) => LEAF_W * Math.pow(k / n, 2);
        const leafBoneS = [];
        for (let k = 0; k <= LEAF_BONES; k++) leafBoneS.push(along(k, LEAF_BONES));
        const leafMidS = leafBoneS.map((v, i) =>
            i < leafBoneS.length - 1 ? (v + leafBoneS[i + 1]) / 2 : v);

        // A sheet is a WEDGE: thin at the fold (clearance where sheets
        // converge), thickening toward the fore-edge until neighbours all but
        // touch — so the block's visible edges are a solid wall, not the
        // 26-slot comb that screen-space AO renders as a dark stipple. Head,
        // tail and fore-edge are all closed for the same reason.
        const PITCH = (BLOCK_H * 2) / N_LEAF;
        const H_EDGE = PITCH * 0.48;
        const hAt = (x) => LEAF_TH + (H_EDGE - LEAF_TH) * Math.pow(x / LEAF_W, 2);

        function buildLeaf(yOff) {
            const pos = [], nor = [], uv = [], coord = [];
            const iT = [], iB = [], iE = [];
            const zOf = (j) => LEAF_H * (j / 2 - 0.5);

            for (const [sgn, dst] of [[1, iT], [-1, iB]]) {
                const base = pos.length / 3;
                for (let i = 0; i <= LEAF_SEGS; i++) {
                    const x = along(i, LEAF_SEGS);
                    for (let j = 0; j <= 2; j++) {
                        pos.push(x, sgn * hAt(x), zOf(j));
                        nor.push(0, sgn, 0);
                        // recto = right half of its spread, verso mirrors so it
                        // reads correctly once turned; v flipped because page
                        // -Z is the HEAD of the book but v=0 samples the
                        // texture's bottom
                        const u = (x / LEAF_W) * 0.5;
                        uv.push(sgn > 0 ? 0.5 + u : 0.5 - u, 1 - j / 2);
                        coord.push(x);
                    }
                }
                for (let i = 0; i < LEAF_SEGS; i++)
                    for (let j = 0; j < 2; j++) {
                        const a = base + i * 3 + j, b = a + 1;
                        const c = base + (i + 1) * 3 + j, d = c + 1;
                        if (sgn > 0) dst.push(a, b, c, b, d, c);
                        else dst.push(a, c, b, b, c, d);
                    }
            }
            for (const j of [0, 2]) {          // head + tail walls
                const base = pos.length / 3;
                const z = zOf(j), nz = j === 0 ? -1 : 1;
                for (let i = 0; i <= LEAF_SEGS; i++) {
                    const x = along(i, LEAF_SEGS);
                    for (const sgn of [1, -1]) {
                        pos.push(x, sgn * hAt(x), z);
                        nor.push(0, 0, nz);
                        uv.push(x / LEAF_W, j / 2);
                        coord.push(x);
                    }
                }
                for (let i = 0; i < LEAF_SEGS; i++) {
                    const a = base + i * 2, b = a + 1, c = a + 2, d = a + 3;
                    if (nz > 0) iE.push(a, b, c, b, d, c);
                    else iE.push(a, c, b, b, c, d);
                }
            }
            {                                   // fore-edge wall
                const base = pos.length / 3;
                for (let j = 0; j <= 2; j++)
                    for (const sgn of [1, -1]) {
                        pos.push(LEAF_W, sgn * H_EDGE, zOf(j));
                        nor.push(1, 0, 0); uv.push(1, j / 2); coord.push(LEAF_W);
                    }
                for (let j = 0; j < 2; j++) {
                    const a = base + j * 2, b = a + 1, c = a + 2, d = a + 3;
                    iE.push(a, b, c, b, d, c);
                }
            }
            return { pos, nor, uv, iT, iB, iE };
        }

        // ---- the GPU leaf field ---------------------------------------------
        // No leaf is a skinned mesh any more. The fold is ANALYTIC — the old
        // bone chain only ever integrated leafPhi over 12 segments — so the
        // vertex stage does the same sum from 5 scalars per leaf:
        //     pos(s) = root + Σₖ clamp(s−Sₖ, 0, Lₖ)·(cos φ(Mₖ), sin φ(Mₖ))
        // with φ(u) = arc(u) + bow·sin(πu/W)/2 and
        // arc(u) = π/2 − dir·min(u/r, |π/2 − rad|) (leafPhi's atan2 collapses
        // to plain arithmetic). A whole book is then: TWO instanced draws for
        // every stock leaf (shells + edges), THREE textured "window" leaves
        // around the opening on the same math driven by uniforms, and the
        // skinned case. Page turns and open/close are buffer writes — no
        // skeletons, no bone uploads, no baked block, no settle bookkeeping.
        const arrays = buildLeaf();
        const mkGeo = (idx, groups) => {
            const g = new THREE.BufferGeometry();
            g.setAttribute('position', new THREE.Float32BufferAttribute(arrays.pos, 3));
            g.setAttribute('normal', new THREE.Float32BufferAttribute(arrays.nor, 3));
            g.setAttribute('uv', new THREE.Float32BufferAttribute(arrays.uv, 2));
            g.setIndex(idx);
            if (groups) groups.forEach(([s, c, m]) => g.addGroup(s, c, m));
            g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1);
            return g;
        };
        const shellGeo = mkGeo([...arrays.iT, ...arrays.iB]);
        const edgeGeoI = mkGeo([...arrays.iE]);
        const windowGeo = mkGeo([...arrays.iT, ...arrays.iB, ...arrays.iE], [
            [0, arrays.iT.length, 0],
            [arrays.iT.length, arrays.iB.length, 1],
            [arrays.iT.length + arrays.iB.length, arrays.iE.length, 2],
        ]);

        // THE SHEET IS A HEADING PROFILE. What the GPU gets per leaf is its
        // fold (root x, y) and one heading per segment of its length — the
        // vertex stage only integrates them. Any path a sheet can take is a
        // heading profile: the crease and the gutter curl, a hang down the
        // block's spine, a drape hugging the arch's hump, a flight's bow.
        // The CPU stages the analytic solve in pA = (rad, r, rootX, rootY),
        // pB = (bow, phi0, lead, -) — phi0 the heading leaving the fold, lead
        // a straight run before the curl of radius r to the plane heading
        // rad, bow a sine of heading along the width — and BAKES it into the
        // profile (bakeLeaf); a path the solve cannot express writes the
        // profile directly (setHeadings). pVis = 0 while a window slot draws
        // that leaf.
        const NSEG = LEAF_BONES;
        const NROW = Math.ceil((NSEG + 2) / 4);          // root xy + NSEG headings, vec4 rows
        const pA = new Float32Array(N_LEAF * 4);
        const pB = new Float32Array(N_LEAF * 4);
        const pVis = new Float32Array(N_LEAF).fill(1);
        const hRows = [];
        const attrH = [];
        for (let r = 0; r < NROW; r++) {
            const arr = new Float32Array(N_LEAF * 4);
            const a = new THREE.InstancedBufferAttribute(arr, 4);
            a.setUsage(THREE.DynamicDrawUsage);
            hRows.push(arr); attrH.push(a);
            shellGeo.setAttribute(`leafH${r}`, a);
            edgeGeoI.setAttribute(`leafH${r}`, a);
        }
        const attrV = new THREE.InstancedBufferAttribute(pVis, 1);
        attrV.setUsage(THREE.DynamicDrawUsage);
        shellGeo.setAttribute('leafV', attrV);
        edgeGeoI.setAttribute('leafV', attrV);
        const setRoot = (i, x, y) => { hRows[0][i * 4] = x; hRows[0][i * 4 + 1] = y; };
        const setHeading = (i, k, v) => { const j = k + 2; hRows[j >> 2][i * 4 + (j & 3)] = v; };
        // the staged analytic solve, evaluated at arc position u
        // the curl turns the SHORT way from phi0 to rad: headings come off
        // atan2 and a cover lying at −179.9° is a hair from one at 179°, not
        // a full circle (the raw difference sent sheets round the long way —
        // down through the desk and up again as a standing fan)
        const BOW_K = Math.PI / LEAF_W;
        const bowS = leafMidS.map((u) => 0.5 * Math.sin(BOW_K * u));
        function bakeLeaf(i) {
            const o4 = i * 4;
            const rad = pA[o4], r = Math.max(1e-4, pA[o4 + 1]);
            const bow = pB[o4], phi0 = pB[o4 + 1], lead = pB[o4 + 2];
            let d = rad - phi0; d = Math.atan2(Math.sin(d), Math.cos(d));
            const sg = Math.sign(d), ad = Math.abs(d);
            hRows[0][o4] = pA[o4 + 2]; hRows[0][o4 + 1] = pA[o4 + 3];
            for (let k = 0; k < NSEG; k++) {
                const run = leafMidS[k] - lead;
                const ph = phi0 + sg * Math.min(run > 0 ? run / r : 0, ad) + bow * bowS[k];
                const j = k + 2;
                hRows[j >> 2][o4 + (j & 3)] = ph;
            }
        }

        const T = tsl;
        const HPI = Math.PI / 2;
        // the fold, as nodes. rows = NROW vec4 nodes (instance attributes or
        // uniforms): rows[0].xy the fold, then one heading per segment; vis a
        // float node. The vertex walks its segments summing run·(cos, sin) of
        // each segment's heading; its own heading (for the sheet's thickness
        // and normal) is read between the segment midpoints so the surface
        // stays smooth across them. Returns {positionNode, normalNode}.
        function foldNodes(rows, visN) {
            const H = (k) => { const j = k + 2, row = rows[j >> 2]; return [row.x, row.y, row.z, row.w][j & 3]; };
            const headingAt = (s) => {
                const ph = T.float(H(0)).toVar();
                for (let k = 0; k < NSEG - 1; k++) {
                    const t = T.clamp(s.sub(leafMidS[k]).div(leafMidS[k + 1] - leafMidS[k]), 0, 1);
                    ph.addAssign(H(k + 1).sub(H(k)).mul(t));
                }
                return ph;
            };
            const posFn = T.Fn(() => {
                const p = T.positionGeometry;
                const s = p.x.toVar();
                const xy = T.vec2(rows[0].x, rows[0].y).toVar();
                for (let k = 0; k < NSEG; k++) {
                    const L = leafBoneS[k + 1] - leafBoneS[k];
                    const run = T.clamp(s.sub(leafBoneS[k]), 0, L);
                    const ph = T.float(H(k)).toVar();
                    xy.addAssign(T.vec2(T.cos(ph), T.sin(ph)).mul(run));
                }
                const phS = headingAt(s);
                const cS = T.cos(phS).toVar(), sS = T.sin(phS).toVar();
                return T.vec3(
                    xy.x.sub(p.y.mul(sS)),
                    xy.y.add(p.y.mul(cS)),
                    p.z).mul(visN);
            });
            const norFn = T.Fn(() => {
                const n = T.normalGeometry;
                const ph = headingAt(T.positionGeometry.x);
                const c = T.cos(ph).toVar(), sn = T.sin(ph).toVar();
                return T.transformNormalToView(T.vec3(
                    n.x.mul(c).sub(n.y.mul(sn)),
                    n.x.mul(sn).add(n.y.mul(c)),
                    n.z));
            });
            return { positionNode: posFn(), normalNode: norFn() };
        }

        const texShape = (m) => (m.map ? '+m' : '') + (m.emissiveMap ? '+e' : '');
        // Cache keys are unique PER RIG: every leaf material's fold nodes
        // close over THIS book's instance buffers and slot uniforms, and a
        // key shared across books lets the backend alias their compiled
        // pipelines — book B then draws with book A's captured bindings
        // (turning janus's pages visibly re-posed the bog book's sheets,
        // and the closed tome wore janus's open-book slot poses as pages
        // jutting from its block).
        const RIG_TAG = '#' + (++__rigSerial);
        const mkLeafMat = (tag, base) => {
            const m = new THREE.MeshStandardNodeMaterial();
            m.roughness = base?.roughness ?? 0.9;
            if (base?.color) m.color.copy(base.color);
            if (base?.map) m.map = base.map;
            m.side = THREE.FrontSide;
            m.customProgramCacheKey = () => `bookcore-${tag}${RIG_TAG}` + texShape(m);
            return m;
        };

        // stock: every leaf, two instanced draws
        const iNodes = foldNodes(
            attrH.map((a) => T.instancedBufferAttribute(a, 'vec4')),
            T.instancedBufferAttribute(attrV, 'float'));
        const stockPaper = mkLeafMat('stockpaper', spreadMat);
        stockPaper.map = null;
        onPageFace(stockPaper, null);
        const stockEdge = mkLeafMat('stockedge', edgeMat);
        Object.assign(stockPaper, iNodes);
        Object.assign(stockEdge, iNodes);
        const noRay = () => {};
        const mkInst = (geo, mat, name) => {
            const m = new THREE.InstancedMesh(geo, mat, N_LEAF);
            m.name = name;
            m.frustumCulled = true;
            m.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1);
            m.userData.noSupportCheck = true;
            m.raycast = noRay;      // GPU-posed: the bind pose would lie to rays
            pageFrame.add(m);
            return m;
        };
        const stockShells = mkInst(shellGeo, stockPaper, 'leaf_stock');
        const stockEdges = mkInst(edgeGeoI, stockEdge, 'leaf_stock_edges');

        // =====================================================================
        // THE MULL — the loose binding cloth
        // =====================================================================
        // A case-bound block is not glued to its case. Its spine is lined with
        // an open-weave cloth (the mull, or super) whose flanges reach past the
        // shoulders and are pasted to the boards under the endpapers: that
        // cloth is all that ties the block to the case. Shut, it lies between
        // the folds and the case round; lying open mid-book it arches up off
        // the flat spine with the block (the hollow beneath is its underside);
        // at the first and last page it stands with the block's spine while
        // the case tips away, its flange running down the joint to the board.
        // One ribbon, the block's height, posed every move along: back joint ·
        // back lip · back foot · the strip's outer face · front foot · front
        // lip · front joint.
        const MULL_N_LIP = 6, MULL_N_STRIP = 40;
        const MULL_PTS = (MULL_N_LIP + 1) + (MULL_N_STRIP + 1) + (MULL_N_LIP + 1);
        const mullGeo = new THREE.BufferGeometry();
        const mullPos = new Float32Array(MULL_PTS * 2 * 3);
        const mullNor = new Float32Array(MULL_PTS * 2 * 3);
        const mullUv = new Float32Array(MULL_PTS * 2 * 2);
        {
            const idx = [];
            for (let q = 0; q < MULL_PTS - 1; q++) {
                const a = q * 2, b = a + 1, c = a + 2, d = a + 3;
                idx.push(a, c, b, b, c, d);
            }
            // BufferAttribute keeps the typed array it is handed (the posed
            // profile is written straight into these); Float32BufferAttribute
            // would copy it and every pose would land in an orphaned buffer
            const posA = new THREE.BufferAttribute(mullPos, 3);
            posA.setUsage(THREE.DynamicDrawUsage);
            const norA = new THREE.BufferAttribute(mullNor, 3);
            norA.setUsage(THREE.DynamicDrawUsage);
            mullGeo.setAttribute('position', posA);
            mullGeo.setAttribute('normal', norA);
            mullGeo.setAttribute('uv', new THREE.BufferAttribute(mullUv, 2));
            mullGeo.setIndex(idx);
            mullGeo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1);
        }
        const mull = new THREE.Mesh(mullGeo, mullMat);
        mull.name = 'mull';
        mull.frustumCulled = false;
        mull.userData.noSupportCheck = true;
        mull.raycast = noRay;
        pageFrame.add(mull);
        const _mp = new Float32Array(MULL_PTS * 2);      // the posed profile [x0,y0, x1,y1, ...]
        const MULL_OVER = 0.0001;                          // the cloth over the case lining
        function updateMull() {
            let n = 0;
            const put = (x, y) => { _mp[n * 2] = x; _mp[n * 2 + 1] = y; n++; };
            for (let i = 0; i <= MULL_N_LIP; i++) {        // back joint -> back groove, on the lining
                const sv = S_BEND0 + (S_GROOVE_B - S_BEND0) * (i / MULL_N_LIP);
                const q = caseInnerAt(sv, thickAt(sv) + MULL_OVER);
                put(q.x, q.y);
            }
            // the strip's outer face: behind the folds by half a sheet, over
            // the lining by the cloth (= the fold line's clearance, spent)
            const back = 0.5 * LEAF_TH + FOLD_UP - MULL_OVER;
            const e = 0.004;
            for (let i = 0; i <= MULL_N_STRIP; i++) {
                const u = i / MULL_N_STRIP;
                const f = foldAt(u), x = f.x, y = f.y;
                const p1 = foldAt(Math.min(1, u + e)), x1 = p1.x, y1 = p1.y;
                const p0 = foldAt(Math.max(0, u - e)), x0 = p0.x, y0 = p0.y;
                let nx = y1 - y0, ny = -(x1 - x0);
                const L = Math.hypot(nx, ny) || 1; nx /= L; ny /= L;      // inward, into the block
                put(x - nx * back, y - ny * back);
            }
            for (let i = 0; i <= MULL_N_LIP; i++) {        // front groove -> front joint
                const sv = S_GROOVE_F + (S_BEND1 - S_GROOVE_F) * (i / MULL_N_LIP);
                const q = caseInnerAt(sv, thickAt(sv) + MULL_OVER);
                put(q.x, q.y);
            }
            // the ribbon: two rows (head, tail), normals off the profile
            let arc = 0;
            for (let q = 0; q < MULL_PTS; q++) {
                const x = _mp[q * 2], y = _mp[q * 2 + 1];
                const a = Math.max(0, q - 1), b = Math.min(MULL_PTS - 1, q + 1);
                let tx = _mp[b * 2] - _mp[a * 2], ty = _mp[b * 2 + 1] - _mp[a * 2 + 1];
                const L = Math.hypot(tx, ty) || 1; tx /= L; ty /= L;
                if (q > 0) arc += Math.hypot(x - _mp[q * 2 - 2], y - _mp[q * 2 - 1]);
                for (let j = 0; j < 2; j++) {
                    const v = q * 2 + j;
                    mullPos[v * 3] = x; mullPos[v * 3 + 1] = y; mullPos[v * 3 + 2] = (j ? 0.5 : -0.5) * LEAF_H;
                    mullNor[v * 3] = ty; mullNor[v * 3 + 1] = -tx; mullNor[v * 3 + 2] = 0;
                    mullUv[v * 2] = arc / 0.01; mullUv[v * 2 + 1] = j * (LEAF_H / 0.01);
                }
            }
            mullGeo.attributes.position.needsUpdate = true;
            mullGeo.attributes.normal.needsUpdate = true;
            mullGeo.attributes.uv.needsUpdate = true;
        }

        // window: the three leaves a reader can meet, textured, uniform-driven.
        // Their map is NEVER null: a 1x1 white placeholder stands in for bare
        // paper, so the material's texture SHAPE — and with it the cache key
        // and compiled pipeline — never changes. Toggling texture<->null
        // re-keys the material and the WebGPU backend recompiles it async,
        // drawing FRAMES OF GARBAGE POSE from an uninitialized uniform
        // buffer meanwhile (a sheet standing bolt upright at settle), plus
        // one pipeline compile per material per page turn.
        const WHITE = new THREE.DataTexture(
            new Uint8Array([255, 255, 255, 255]), 1, 1);
        WHITE.colorSpace = THREE.SRGBColorSpace;
        WHITE.needsUpdate = true;
        const windowSlots = [];
        for (let w = 0; w < 3; w++) {
            const uRows = [];
            for (let r = 0; r < NROW; r++) uRows.push(T.uniform(new THREE.Vector4()));
            const nodes = foldNodes(uRows, T.float(1));
            const recto = mkLeafMat(`recto${w}`, spreadMat); recto.map = WHITE;
            const verso = mkLeafMat(`verso${w}`, spreadMat); verso.map = WHITE;
            const edgeW = mkLeafMat(`edge${w}`, edgeMat);
            for (const m of [recto, verso, edgeW]) Object.assign(m, nodes);
            const mesh = new THREE.Mesh(windowGeo, [recto, verso, edgeW]);
            mesh.name = `leaf_window_${w}`;
            mesh.frustumCulled = true;
            mesh.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1);
            mesh.userData.noSupportCheck = true;
            mesh.raycast = noRay;
            mesh.visible = false;
            pageFrame.add(mesh);
            windowSlots.push({ mesh, uRows, recto, verso, leaf: -1 });
        }

        // picking: rays cannot see GPU-posed geometry, so two invisible BOXES
        // stand where the page stacks live — left of the fold turns back,
        // right turns forward. bookui reads the names.
        const pickH = BLOCK_H * 2 + 0.02;
        const mkPick = (name, cx) => {
            const g = new THREE.BoxGeometry(LEAF_W, pickH, LEAF_H);
            const m = new THREE.Mesh(g, stockPaper);
            m.name = name;
            m.visible = false;                  // raycasts still hit invisible meshes
            m.position.set(cx, BLOCK_H * (1 - TAPER_FRAC), 0);
            pageFrame.add(m);
            return m;
        };
        const pickL = mkPick('pickL', -LEAF_W / 2);
        const pickR = mkPick('pickR', LEAF_W / 2);

        // THE BLOCK'S SPINE. Shut, every fold sits in the case round — leaf
        // N−1 at the back groove, leaf 0 at the front, sampled off the POSED
        // case bones every move: the block's rounding IS the round. The block
        // is not glued to the case, though (a case binding never is): what
        // ties them is the mull, pasted to the boards past each shoulder. So
        // as the round straightens onto the desk mid-book the fold line lifts
        // off it and THROWS UP into the hollow-back arch (archSet, below),
        // and near either end of the book — where the case stays wrapped
        // round the whole block and a cover props — it simply stays put.
        const _sp = { x: 0, y: 0, ang: 0 };
        // the case's inner face at arc length s (back joint .. front joint),
        // `off` in from the cloth. The inward normal is BLENDED between the
        // bones: offsetting along each segment's own normal broke the line at
        // every bone where the chain bends (the round's corner turns ~60° in
        // one segment — the offset points there stepped back on themselves,
        // and the sheets folded at that step read their normal as pointing
        // down through the desk).
        function caseInnerAt(s, off) {
            s = Math.min(S_BEND1, Math.max(S_BEND0, s));
            let j = B_BACK;
            while (j < B_FRONT - 1 && caseBoneS[j + 1] < s) j++;
            const s0 = caseBoneS[j], s1 = caseBoneS[j + 1];
            const t = Math.min(1, Math.max(0, (s - s0) / Math.max(1e-9, s1 - s0)));
            const o0 = (j - B_BACK) * 2, o1 = o0 + 2;
            let nx = clothNrm[o0] + (clothNrm[o1] - clothNrm[o0]) * t;
            let ny = clothNrm[o0 + 1] + (clothNrm[o1 + 1] - clothNrm[o0 + 1]) * t;
            const L = Math.hypot(nx, ny) || 1; nx /= L; ny /= L;
            _sp.x = clothPts[o0] + (clothPts[o1] - clothPts[o0]) * t + nx * off;
            _sp.y = clothPts[o0 + 1] + (clothPts[o1 + 1] - clothPts[o0 + 1]) * t + ny * off;
            _sp.ang = Math.atan2(ny, nx);
            return _sp;
        }
        const FOLD_UP = 0.00015;                                     // the fold line's clearance over the cloth (the mull lives in it)
        function spineAt(u) {
            const s = S_GROOVE_B + (S_GROOVE_F - S_GROOVE_B) * Math.min(1, Math.max(0, u));
            return caseInnerAt(s, thickAt(s) + 0.5 * LEAF_TH + FOLD_UP);
        }
        // THE HOLLOW BACK. Shut, the block's spine lies in the case round. As the
        // case spine tips back and flattens, the block's spine — glued, rounded,
        // stiff — does not: it lifts off the case spine and THROWS UP into an
        // arch between the shoulders with the hollow beneath (Skye's reference:
        // the case spine flat on the table, the block's spine a hump above it
        // wearing its headband, both stacks' sheets leaving the hump and curling
        // down onto their boards). Its curvature reverses on the way — round,
        // flat, arch — as a rounded spine does when a book is laid open.
        const ARCH_DEG = 150;                           // the open arch's angle (≈ the photo)
        let thetaD = 1.7;                               // the shut round's angle, measured at build
        const arch = { w: 0, ax: 0, ay: 0, bx: 0, by: 0, th: 0 };
        function archSet(w) {                           // w = how far the round has straightened
            arch.w = w;
            if (w <= 0) return;
            const A = spineAt(0), ax = A.x, ay = A.y;
            const B = spineAt(1), bx = B.x, by = B.y;
            const L = S_GROOVE_F - S_GROOVE_B;
            const thA = ARCH_DEG * Math.PI / 180;
            const cA = L * Math.sin(thA / 2) / (thA / 2);           // the open arch's chord
            let cx = bx - ax, cy = by - ay;
            const d = Math.hypot(cx, cy) || 1; cx /= d; cy /= d;
            const mx = (ax + bx) / 2, my = (ay + by) / 2;
            // feet: the round's own ends shut, drawn in to the arch's chord open
            const half = (d + (cA - d) * w) / 2;
            arch.ax = mx - cx * half; arch.ay = my - cy * half;
            arch.bx = mx + cx * half; arch.by = my + cy * half;
            arch.th = -thetaD + (thA + thetaD) * w;
        }
        const _fd = { x: 0, y: 0 };
        function archAt(u) {                            // the arc through the feet at the blended angle
            const ax = arch.ax, ay = arch.ay, bx = arch.bx, by = arch.by, th = arch.th;
            let cx = bx - ax, cy = by - ay;
            const d = Math.hypot(cx, cy) || 1; cx /= d; cy /= d;
            const nx = cy, ny = -cx;                     // toward the block: +n̂ bulges the arch up
            const mx = (ax + bx) / 2, my = (ay + by) / 2;
            if (Math.abs(th) < 1e-3) {
                _fd.x = mx + cx * d * (u - 0.5); _fd.y = my + cy * d * (u - 0.5);
                return _fd;
            }
            const R = d / (2 * Math.sin(th / 2)), b = -th / 2 + th * u;
            const along = R * Math.sin(b), out = R * (Math.cos(b) - Math.cos(th / 2));
            _fd.x = mx + cx * along + nx * out; _fd.y = my + cy * along + ny * out;
            return _fd;
        }
        const _fo = { x: 0, y: 0 };
        function foldAt(u) {                            // the block's spine: in the round, or thrown up
            const sp = spineAt(u);
            let x = sp.x, y = sp.y;
            if (arch.w > 0) { const a = archAt(u); x += (a.x - x) * arch.w; y += (a.y - y) * arch.w; }
            _fo.x = x; _fo.y = y;
            return _fo;
        }
        function leafParams(i, deg, bow = 0) {
            const u = (N_LEAF - 0.5 - i) / N_LEAF;
            const f = foldAt(u), x = f.x, y = f.y;
            // the strip's outward normal, read off the fold line itself
            const e = 0.004;
            const p1 = foldAt(Math.min(1, u + e)), x1 = p1.x, y1 = p1.y;
            const p0 = foldAt(Math.max(0, u - e)), x0 = p0.x, y0 = p0.y;
            const ang = Math.atan2(-(x1 - x0), y1 - y0);
            const o4 = i * 4;
            pA[o4] = deg * Math.PI / 180; pA[o4 + 1] = R_CREASE;
            pA[o4 + 2] = x; pA[o4 + 3] = y;
            pB[o4] = bow; pB[o4 + 1] = ang; pB[o4 + 2] = 0;
        }

        // ---- posing ---------------------------------------------------------
        // (leafPhi lives in the vertex stage now — see foldNodes above; the
        // CPU keeps only the root solve in leafParams.)

        // The FRONT BOARD'S FRAME, measured in pageFrame coordinates — joint
        // position and surface angle read straight off the posed case bones,
        // so the bridge aims each sheet at the ACTUAL bend with nothing inferred.
        const _pj = new THREE.Vector3(), _pt = new THREE.Vector3();
        function boardFrame() {
            pageFrame.updateMatrixWorld(true);
            pageFrame.worldToLocal(caseBones[B_FRONT].getWorldPosition(_pj));
            pageFrame.worldToLocal(caseBones[caseBones.length - 1].getWorldPosition(_pt));
            return { jx: _pj.x, jy: _pj.y,
                     ang: Math.atan2(_pt.y - _pj.y, _pt.x - _pj.x) };
        }
        // the BACK board's frame the same way (it props at the last page)
        function backFrame() {
            pageFrame.worldToLocal(caseBones[B_BACK].getWorldPosition(_pj));
            pageFrame.worldToLocal(caseBones[0].getWorldPosition(_pt));
            return { jx: _pj.x, jy: _pj.y,
                     ang: Math.atan2(_pt.y - _pj.y, _pt.x - _pj.x) };
        }

        // The posed spine, sampled into a polyline each move (pageFrame): the
        // case bones from the back joint to the front joint — spineAt reads it.
        const clothPts = [];          // flat [x0,y0, x1,y1, ...] in pageFrame
        const clothNrm = [];          // per bone: inward normal, the mean of its two segments'
        const _cp = new THREE.Vector3();
        function refreshClothProfile() {
            pageFrame.updateMatrixWorld(true);
            clothPts.length = 0;
            for (let i = B_BACK; i <= B_FRONT; i++) {
                caseBones[i].getWorldPosition(_cp);
                pageFrame.worldToLocal(_cp);
                clothPts.push(_cp.x, _cp.y);
            }
            clothNrm.length = 0;
            const n = clothPts.length / 2;
            for (let j = 0; j < n; j++) {
                const a = Math.max(0, j - 1), b = Math.min(n - 1, j + 1);
                const dx = clothPts[b * 2] - clothPts[a * 2], dy = clothPts[b * 2 + 1] - clothPts[a * 2 + 1];
                const L = Math.hypot(dx, dy) || 1;
                clothNrm.push(dy / L, -dx / L);
            }
        }

        const R_CREASE = Math.max(LEAF_TH * 3, 0.0004);   // the fold's own tight curl
        // ONE monotonic fan over the whole block, indexed by leaf number — a
        // leaf higher in a stack must always tilt more, or a lower tail climbs
        // through the sheet above it (two independent fan scales did exactly
        // that, coincident to 15 µm).
        const LAID = PAGE_DEG;
        const FAN = 1.2;
        const split = openAt;
        const rightDeg = (i) => FAN * (N_LEAF - 1 - i) / Math.max(1, N_LEAF - 1 - split);
        const leftDeg = (i) => LAID - FAN * i / Math.max(1, N_LEAF - 1);

        // (the arch's geometry lives in archSet/foldAt above; how far it has
        // thrown up is the case round's own straightening, caseState.c —
        // page one and the last page keep the round, and the block, wrapped)
        let jointBackX = 0, headGap = 0;                // the back joint; the shut cover's clearance over the block
        // THE BRIDGE — how a sheet gets from its fold on the spine to its
        // stack, whose plane lies against a board (turned sheets against the
        // cover, resting ones on the back board), its own layer in from that
        // board's inner face. Below its plane it leaves along the spine's
        // normal and curls up to it with the radius that lands it exactly
        // (the gutter's V lying open, the shoulders of a shut round, a sheet
        // hooking over the block's corner onto a propped cover). A little
        // above it, it dips onto it in one arc; well above it — the endpaper
        // at page one, a stack riding a lifting cover — it HANGS: straight
        // toward the board, then a paper-radius bend onto it.
        const R_BEND = Math.min(0.012, 0.3 * BLOCK_H + 0.002);
        const R_REACH = 0.5 * LEAF_W;                     // the widest curl a sheet will make to reach its plane
        // A sheet's plane: heading `rad`, normal n̂ = (nx, ny) pointing off the
        // board into the block, through the point J + n̂·layer. Which way is
        // "up off the plane" for a heading is read from n̂ itself (a resting
        // sheet at 0° and a turned one at 180° both have n̂ = +y).
        const HANG_MIN = 3 * R_BEND;                      // above this a sheet DROPS; below, one arc
        function bridge(o4, rad, px, py, layer, nx, ny, jx, jy, spineAng) {
            const d = (px - jx) * nx + (py - jy) * ny - layer;
            const up = Math.sign(-Math.sin(rad) * nx + Math.cos(rad) * ny) || 1;   // +1: rad+δ lifts off the plane
            let phi0 = rad, r = R_CREASE, lead = 0;
            if (d > 0.5 * R_CREASE) {
                if (d < HANG_MIN) {
                    // a little above its plane: the sheet leaves its fold dipping
                    // toward it and lands in one arc no wider than four times
                    // the drop (a sheet falling off the block's shoulder onto
                    // the cover beside it)
                    const rCap = Math.max(R_BEND, 4 * d);
                    const dl = Math.acos(Math.max(-1, 1 - d / rCap));
                    phi0 = rad - up * dl;
                    r = d / (1 - Math.cos(dl));
                } else {
                    phi0 = rad - up * Math.PI / 2;                 // straight toward the board
                    r = Math.min(R_BEND, d);
                    lead = d - r;
                }
            } else if (d < -0.5 * R_CREASE) {
                // the spine's normal sets how FAR from the plane the sheet
                // leaves; WHICH side is its own stack's. A normal facing the
                // other stack (past 90° from the plane) means this sheet goes
                // over the END of the strip — it leaves along the strip's
                // tangent instead (a sheet folded over the block's shoulder,
                // not a hairpin). And it lands within a sane radius: never
                // more than four times its rise, never less than a paper bend.
                let dl = Math.abs(Math.atan2(Math.sin(rad - spineAng), Math.cos(rad - spineAng)));
                if (dl > Math.PI / 2) dl -= Math.PI / 2;
                const rCap = Math.min(R_REACH, Math.max(R_BEND, 4 * -d));
                dl = Math.max(dl, Math.acos(Math.max(-1, 1 + d / rCap)));
                phi0 = rad + up * dl;
                r = -d / (1 - Math.cos(dl));
            }
            pA[o4] = rad;
            pA[o4 + 1] = Math.max(R_CREASE, Math.min(0.8 * LEAF_W, r));
            pB[o4 + 1] = phi0; pB[o4 + 2] = lead;
        }

        // Ride up on whatever part of the case is lowest: the strip's outer
        // surface is authored at local y=0, so the chain joints ARE the
        // surface and the lowest bone is the contact point. (A Box3 would read
        // the bind pose — the cloth unrolled flat.)
        const _v = new THREE.Vector3();
        function reseat() {
            // The BOARDS sit on the desk. The spine strip may hang below the
            // desk plane (a hollow's loop, hidden in the desk) and must never
            // lift the book: seating on the lowest CLOTH point floated an
            // open tome 10.6 mm off its desk and bobbed it with every sweep.
            caseFrame.updateMatrixWorld(true);
            let lo = Infinity;
            for (let i = 0; i < caseBones.length; i++) {
                const s = caseBoneS[i];
                if (s > S_BEND0 + 1e-6 && s < S_BEND1 - 1e-6) continue;   // grooves + round: may hang
                caseBones[i].getWorldPosition(_v);
                caseFrame.worldToLocal(_v);
                if (_v.y < lo) lo = _v.y;
            }
            body.position.z = -Math.min(0, lo);
        }


        // ---- public state ----------------------------------------------------
        let openK = null;        // 0..1 case opening
        let page = 0;            // leaves turned by setPage/poseTurn, atop split
        let turnPhase = null;    // non-null while a leaf is mid-flight
        let turnWad = 1;         // sheets in the air together (bulk skips)

        // the page fraction this pose reads at — sheets turned over the block,
        // a flight counted by how far it has gone
        const fNow = () => {
            const pp = source ? physFor(page) : page;
            const inAir = turnPhase !== null ? turnPhase * turnWad : 0;
            return Math.min(1, Math.max(0, (split + pp + inAir) / N_LEAF));
        };
        function poseAll() {
            const k = openK ?? 0;
            poseCase(k, openSign, fNow());
            reseat();
            const bf = boardFrame(), bb = backFrame();
            refreshClothProfile();
            archSet(caseState.c);
            const kL = Math.min(1, k);
            const pp = source ? physFor(page) : page;
            const centre = split + pp;
            // the two boards' inner faces at their joints, for the bridge
            const nfx = Math.sin(bf.ang), nfy = -Math.cos(bf.ang);
            const jfx = bf.jx + nfx * BOARD_TH, jfy = bf.jy + nfy * BOARD_TH;
            const nbx = -Math.sin(bb.ang), nby = Math.cos(bb.ang);
            const jbx = bb.jx + nbx * BOARD_TH, jby = bb.jy + nby * BOARD_TH;
            // a turned sheet lies on the COVER, wherever the cover is — its
            // heading is the board's own plus its place in the fan (pageAngle
            // measured against a flat-open cover); a resting sheet the same
            // against the back board
            const turnedRad = (i) => bf.ang + (leftDeg(i) - 180) * Math.PI / 180;
            const restingRad = (i) => bb.ang + rightDeg(i) * Math.PI / 180;

            // a shut cover clears the block by the head slot; that clearance is
            // the turned sheets' extra layer until the cover has lifted off
            const gapNow = headGap * (1 - smooth01(k / 0.15));
            for (let i = 0; i < N_LEAF; i++) {
                const o4 = i * 4;
                // Turned leaves RIDE the cover: scaled by openK so closing the
                // book carries the left stack down with it (page state
                // persists; reopening shows the same spread). Unscaled they
                // stick out of a closing case and read as escaped pages.
                if (i < centre) {
                    leafParams(i, turnedRad(i) * 180 / Math.PI);
                    bridge(o4, pA[o4], pA[o4 + 2], pA[o4 + 3],
                        (i + 0.5) * PITCH + gapNow, nfx, nfy, jfx, jfy, pB[o4 + 1]);
                    continue;
                }
                if (turnPhase !== null && i >= centre && i < centre + turnWad) {
                    // WAD flights: a grabbed chunk of sheets in the air
                    // together, each lagging the one above it — a skip reads
                    // as a handful of pages, not a fast-forwarded single
                    // turn. The lead sheet launches first and every sheet
                    // has landed by phase 1.
                    const spread = turnWad > 1 ? 0.45 : 0;
                    const lag = turnWad > 1 ? (i - centre) / (turnWad - 1) : 0;
                    const p = Math.max(0, Math.min(1,
                        turnPhase * (1 + spread) - spread * lag));
                    const e = p < 0.5 ? 2 * p * p
                        : 1 - Math.pow(-2 * p + 2, 2) / 2;
                    // scaled by openK like every other leaf: a sheet caught
                    // mid-flight SETTLES as the case closes — unscaled it
                    // stood at ~90° while the cover swept shut through it
                    // A FLIGHT is a sheet on a plane that swings over the top —
                    // counter-clockwise from its resting heading to the cover's,
                    // whatever atan2 called the cover's angle — through a point
                    // sliding from its place in the right stack to its place in
                    // the left. Its fold stays on the spine and the same bridge
                    // poses it, so takeoff and landing ARE the resting and
                    // turned poses: nothing to snap at either end. (The old
                    // flight lifted the fold a block-height off the hump and
                    // lerped raw angles: near a propped cover at −160° the
                    // sheets went round the long way, down through the desk.)
                    leafParams(i, 0, Math.sin(Math.PI * e) * 0.55 * kL);
                    const from = restingRad(i);
                    let dd = turnedRad(i) - from;
                    dd = ((dd % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
                    const rad = from + dd * e;
                    const layR = (N_LEAF - 0.5 - i) * PITCH, layT = (i + 0.5) * PITCH + gapNow;
                    const qx = (jbx + nbx * layR) * (1 - e) + (jfx + nfx * layT) * e;
                    const qy = (jby + nby * layR) * (1 - e) + (jfy + nfy * layT) * e;
                    let vnx = nbx * (1 - e) + nfx * e, vny = nby * (1 - e) + nfy * e;
                    const vl = Math.hypot(vnx, vny) || 1; vnx /= vl; vny /= vl;
                    bridge(o4, rad, pA[o4 + 2], pA[o4 + 3], 0, vnx, vny, qx, qy, pB[o4 + 1]);
                    continue;
                }
                leafParams(i, restingRad(i) * 180 / Math.PI);
                bridge(o4, pA[o4], pA[o4 + 2], pA[o4 + 3],
                    (N_LEAF - 0.5 - i) * PITCH, nbx, nby, jbx, jby, pB[o4 + 1]);
            }
            for (let i = 0; i < N_LEAF; i++) bakeLeaf(i);
            updateMull();
            // window slots ride centre-1..centre+1: textured meshes take those
            // leaves (uniform copies of the same params), stock hides them
            pVis.fill(1);
            for (let w = 0; w < 3; w++) {
                const slot = windowSlots[w];
                const li = centre - 1 + w;
                const on = li >= 0 && li < N_LEAF;
                slot.mesh.visible = on;
                slot.leaf = on ? li : -1;
                if (on) {
                    pVis[li] = 0;
                    const o4 = li * 4;
                    for (let r = 0; r < NROW; r++) {
                        const h = hRows[r];
                        slot.uRows[r].value.set(h[o4], h[o4 + 1], h[o4 + 2], h[o4 + 3]);
                    }
                }
            }
            for (const a of attrH) a.needsUpdate = true;
            attrV.needsUpdate = true;
            // Pick boxes are SENSED by every scene ray (raycasters ignore
            // visibility) — they are the book's touchable body now, so they
            // must follow its state: closed, the left page's box would hang
            // in the air beside the block, a phantom slab to any sensor or
            // weapon ray. Folded shut it collapses into the block's volume.
            const openish = k >= 0.5;
            pickL.position.x = openish ? -LEAF_W / 2 : LEAF_W / 2;
            pickL.scale.x = openish ? 1 : 0.001;
        }

        // (A FORWARD close — the finished book lying back-cover-up — is NOT
        // a rig pose: extending k past 1 corkscrews the chain, because the
        // forward-closed book is the SAME closed shape rotated 180° about
        // its spine line. Drivers compose it: close normally while rotating
        // the holder over the spine — see bookcomp's finish flip.)
        function setOpen(k) {
            k = Math.max(0, Math.min(1, k));
            if (k === openK) return;
            openK = k;
            poseAll();
        }

        // ---- virtual spreads: any page count on a fixed leaf budget ---------
        // A SOURCE ({count, get(i) -> Promise<texture|null>}) replaces the
        // static spread array: `page` becomes the VIRTUAL page over `count`
        // spreads, mapped onto the physical leaves proportionally, and only
        // the spreads around the current opening are ever decoded (small
        // LRU; far leaf faces are plain stock — their faces are hidden in
        // the block anyway). setPage/poseTurn/riffle keep their contracts,
        // so every existing driver — the film scenes, the worlds comp —
        // reads a 300-page PDF book without changing a line.
        let source = null;
        let srcSeq = 0;
        const srcCache = new Map();          // spread index -> texture | promise
        const SRC_KEEP = 3;                  // decoded spreads live in V±3 only
        const P_CAP = N_LEAF - split - 1;
        // Virtual pages map 1:1 onto physical leaves and STOP at the last
        // physical sheet — maxPage takes the min below. A proportional
        // carousel was tried instead (re-turning leaves to carry longer
        // documents): pages visibly generated out of nowhere at the end of
        // the block. Adapters size the leaf count to the document (the
        // wedge construction thins leaves automatically), so the whole
        // document fits as REAL paper.
        const physFor = (V) => Math.min(V, P_CAP);
        const pPage = () => source ? physFor(page) : page;

        function srcFetch(k, seq, apply) {
            if (k < 0 || k >= source.count) { apply(null); return; }
            const have = srcCache.get(k);
            if (have && have.isTexture) { apply(have); return; }
            if (!have) {
                const p = Promise.resolve(source.get(k)).then((t) => {
                    if (srcCache.get(k) === p) srcCache.set(k, t);
                    return t;
                }).catch(() => { srcCache.delete(k); return null; });
                srcCache.set(k, p);
            }
            Promise.resolve(srcCache.get(k)).then((t) => {
                if (seq === srcSeq && t) apply(t);
            });
        }

        function applyVirtual() {
            const seq = ++srcSeq;
            const V = page;
            // Only the window slots carry textures — the three leaves a
            // reader can meet. Slot w draws leaf centre-1+w: its recto is
            // the right half of spread V-1+w, its verso the left half of the
            // next. Everything else is plain stock in the instanced field;
            // the whole book holds ~4 decoded spreads, however long the
            // source document is.
            const setFace = (mat, tex) => {
                mat.map = tex ?? WHITE;     // never null — pipeline stays warm
                onPageFace(mat, tex);
                mat.needsUpdate = true;
            };
            for (let w = 0; w < 3; w++) {
                const slot = windowSlots[w];
                const kv = V - 1 + w;
                setFace(slot.recto, null); setFace(slot.verso, null);
                srcFetch(kv, seq, (t) => setFace(slot.recto, t));
                srcFetch(kv + 1, seq, (t) => setFace(slot.verso, t));
            }
            // warm one further each way, then evict the rest
            srcFetch(V + 2, seq, () => {});
            srcFetch(V - 1, seq, () => {});
            for (const [k, v] of srcCache) {
                if (Math.abs(k - V) > SRC_KEEP) {
                    srcCache.delete(k);
                    if (v && v.isTexture && source?.dispose !== false) v.dispose?.();
                }
            }
        }

        function setSpreadSource(s) {
            source = s && s.count > 0 && typeof s.get === 'function' ? s : null;
            srcSeq++;
            for (const [, v] of srcCache) if (v && v.isTexture) v.dispose?.();
            srcCache.clear();
            page = 0; turnPhase = null;
            if (source) applyVirtual();
            poseAll();
            return source ? source.count : 0;
        }

        // the LAST spread is fully viewable (its left half is the verso of
        // the final turned leaf, its right half the recto beneath) — the
        // ceiling is spreads-1, not -2: the old -2 quietly amputated every
        // book's final spread (janus's own 'simulators' essay included)
        const maxPage = () => Math.max(0, Math.min(
            source ? source.count - 1 : N_LEAF - split - 1,
            N_LEAF - split - 1));

        function setPage(n) {
            n = Math.max(0, Math.min(maxPage(), Math.round(n)));
            if (n === page && turnPhase === null) return page;
            page = n; turnPhase = null; turnWad = 1;
            if (source) applyVirtual();
            poseAll();
            return page;
        }

        // A leaf mid-flight: phase 0 = resting on the right stack, 1 = landed
        // left. Drive 0->1 then call setPage(page+1); or drive 1->0 after
        // setPage(page-1)+poseTurn(1) for a backward turn. `wad` sheets fly
        // together (staggered) for bulk skips — the landing page jump is the
        // driver's business; the wad is only what the eye sees in the air.
        function poseTurn(phase, wad = 1) {
            if (page >= maxPage() + 1) return false;
            turnPhase = Math.max(0, Math.min(1, phase));
            turnWad = Math.max(1, Math.min(8, Math.round(wad)));
            poseAll();
            return true;
        }

        // ---- spreads ---------------------------------------------------------
        // A static spread list IS a source — one already-decoded texture per
        // spread. dispose:false because the textures are the CALLER'S (film
        // scenes pass loaded assets); the staging LRU must not destroy them.
        function setSpreadTextures(textures) {
            const list = textures.slice();
            return setSpreadSource({
                count: list.length, get: (i) => list[i],
                pages: null, dispose: false,
            });
        }

        // ---- film driver ------------------------------------------------------
        function riffle(t, { start = 0, secondsPerPage = 1.2, turnFraction = 0.72 } = {}) {
            if (!source) return 0;
            const local = Math.max(0, t - start);
            const n = Math.floor(local / secondsPerPage);
            const idx = Math.min(n, maxPage());
            if (idx !== page) { page = idx; applyVirtual(); }
            const phase = (local % secondsPerPage) / secondsPerPage;
            // Past turnFraction the sheet lies LANDED (phase clamps to 1 —
            // e=1 is exactly the landed pose); null would snap it back to the
            // right stack until the next page increments.
            turnPhase = (n > maxPage()) ? null
                : Math.min(1, phase / turnFraction);
            turnWad = 1;
            poseAll();
            return idx;
        }

        function layFlat() {
            root.rotation.set(-Math.PI / 2, 0, 0);
            root.updateMatrixWorld(true);
            return root;
        }

        // Closed-case bounds in root space — for seating without a source GLB.
        function seatBox() {
            // Root-frame x: fore-edge at +FORE_X, spine bulge at
            // -(JOINT_X + LIP + round). (These were mirrored once — only y was
            // ever consumed, which is why seating still worked.)
            const b = new THREE.Box3();
            b.min.set(-(JOINT_X + LIP + SPINE_D), -HALF_H, -HALF_T - 0.0002);
            b.max.set(FORE_X, HALF_H, HALF_T + 0.0002);
            return b.applyMatrix4(root.matrix);
        }

        const pageMaterials = () => {
            const out = [stockPaper];
            for (const s of windowSlots) out.push(s.recto, s.verso);
            return out;
        };

        // Surface identification for debugging: every material a flat primary
        // so a render names the surface it shows. Call AFTER any scene-side
        // tinting/spread loading, or those undo it.
        //   case cloth RED · lining BLUE · case rim CYAN
        //   leaf recto GREEN · leaf verso YELLOW · leaf edge MAGENTA
        function codeSurfaces() {
            const M = caseMesh.material;
            M[0] = M[0].clone(); M[0].map = null; M[0].color.setHex(0xdd2222);
            M[1] = M[1].clone(); M[1].map = null; M[1].color.setHex(0x2255ee);
            M[2] = M[2].clone(); M[2].map = null; M[2].color.setHex(0x00cccc);
            for (const s of windowSlots) {
                s.recto.map = null; s.recto.emissiveNode = null;
                s.verso.map = null; s.verso.emissiveNode = null;
                s.recto.color.setHex(0x22cc22); s.verso.color.setHex(0xdddd22);
                s.recto.needsUpdate = s.verso.needsUpdate = true;
            }
            stockPaper.emissiveNode = null; stockPaper.emissiveMap = null;
            stockPaper.color.setHex(0x116611); stockPaper.needsUpdate = true;
            stockEdge.map = null; stockEdge.color.setHex(0xdd22dd);
            stockEdge.needsUpdate = true;
            log('[bookRig] surfaces colour-coded');
            return true;
        }

        log(`[bookRig] case ${casePos.length / 3}v/${caseBones.length}b  `
            + `leaf field ${N_LEAF} instanced + 3 window (GPU fold)  `
            + `block ±${BLOCK_H.toFixed(4)}  openSign ${openSign}`);

        setOpen(0);
        // the CLOSED case's seated height, measured off the posed bones —
        // drivers that cartwheel the book over its spine (the finish flip)
        // must rise by exactly this or the flipped body sits inside the desk
        const SEATED_T = (() => {
            let hi = 0;
            const v = new THREE.Vector3();
            caseFrame.updateMatrixWorld(true);
            for (const b of caseBones) {
                b.getWorldPosition(v);
                caseFrame.worldToLocal(v);
                if (v.y > hi) hi = v.y;
            }
            return hi;
        })();
        {
            // measured off the shut case: the back joint (the resting sheets'
            // board plane starts there) and the head slot (the shut cover's
            // clearance over the block, which the turned sheets keep until
            // the cover has lifted off)
            const v = new THREE.Vector3();
            pageFrame.updateMatrixWorld(true);
            caseBones[B_BACK].getWorldPosition(v);
            pageFrame.worldToLocal(v);
            jointBackX = v.x;
            caseBones[B_FRONT].getWorldPosition(v);
            pageFrame.worldToLocal(v);
            headGap = Math.max(0, v.y - BOARD_TH - 2 * BLOCK_H);
            // the shut round's angle: chord over arc of its inner face
            refreshClothProfile();
            {
                const A = spineAt(0), ax = A.x, ay = A.y;
                const B = spineAt(1);
                const ratio = Math.min(0.999, Math.hypot(B.x - ax, B.y - ay) / (S_GROOVE_F - S_GROOVE_B));
                let t = 1;
                for (let it = 0; it < 12; it++) {           // Newton on sin t − ratio·t
                    const g = Math.sin(t) - ratio * t, dg = Math.cos(t) - ratio;
                    t = Math.min(Math.PI, Math.max(1e-3, t - g / (dg || 1e-6)));
                }
                thetaD = 2 * t;
            }
            poseAll();
        }
        return {
            root, body, caseMesh, caseBones,
            leafField: { stockShells, stockEdges, windowSlots, pickL, pickR },
            mull,
            setOpen, setPage, poseTurn, riffle,
            setSpreadTextures, setSpreadSource, layFlat, seatBox,
            pageMaterials, edgeMaterial: edgeMat, codeSurfaces,
            frames: { caseFrame, pageFrame },
            metrics: {
                HALF_T, HALF_H, BOARD_LEN, BOARD_TH, JOINT_X, LIP, SPINE_D,
                U_JOINT, S_END, S_BEND0, S_BEND1, LEAF_W, LEAF_H, LEAF_TH,
                BLOCK_H, PAGE_R, N_LEAF, split, openSign, SEATED_T,
                caseVerts: casePos.length / 3, caseBoneCount: caseBones.length,
            },
            get spreadCount() { return source ? source.count : 0; },
            get openAmount() { return openK; },
            get page() { return page; },
            get maxPage() { return maxPage(); },
            // instruments: the measured internals a tool needs to settle a
            // geometry dispute in millimetres (pageFrame metres) — never
            // presentation state
            probe: () => ({
                cloth: clothPts.slice(),
                joints: { back: B_BACK, front: B_FRONT },
                GUTTER_IN, TAPER_FRAC, tubeDepth, PAGE_R_EFF,
                caseBoneS: caseBoneS.slice(),
                jointBackX, headGap, R_BEND, thetaD, archW: arch.w,
                caseState: Object.assign({}, caseState),
                turnPhase, turnWad, page, centre: split + (source ? physFor(page) : page),
                leaf: (i) => ({ A: Array.from(pA.subarray(i * 4, i * 4 + 4)), B: Array.from(pB.subarray(i * 4, i * 4 + 4)) }),
                mull: () => Array.from(_mp),
                leafBoneS: leafBoneS.slice(), leafMidS: leafMidS.slice(), NSEG, NROW,
                spine: (u) => { const q = spineAt(u); return [q.x, q.y, q.ang]; },
                fold: (u) => { const q = foldAt(u); return [q.x, q.y]; },
            }),
        };
    }

    // Compose an arc-length wrap from separate cover images. Layout matches
    // the geometry's U mapping: [back cover, mirrored] [spine, rotated]
    // [front cover] — uJoint is solved so texel density is uniform along the
    // developed cross-section, which is the whole point of the wrap.
    /** A 2D canvas that works everywhere this runs: browsers, and the deno
     *  render harness (whose OffscreenCanvas is WebGPU-only — its 2d context
     *  is null, so document.createElement's shim canvas comes FIRST). */
    function canvas2d(W, H) {
        if (typeof document !== 'undefined') {
            const c = Object.assign(document.createElement('canvas'), { width: W, height: H });
            const ctx = c.getContext('2d');
            if (ctx) return { c, ctx };
        }
        if (typeof OffscreenCanvas !== 'undefined') {
            const c = new OffscreenCanvas(W, H);
            const ctx = c.getContext('2d');
            if (ctx) return { c, ctx };
        }
        throw new Error('[BookCore] no 2d canvas available');
    }

    async function composeWrapTexture(THREE, { front, back, spine, color = '#8a1420' }, uJoint, res = 4096) {
        // res: film closeups earn 4096 (22.6 MB RGBA); a world with many
        // books passes 2048 (5.6 MB) — stamping still crisp at ~6 px/mm.
        const W = res, H = Math.round(res * 1380 / 4096);
        const { c, ctx } = canvas2d(W, H);
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, W, H);

        // Decode to something THIS environment's canvas can draw: a browser
        // draws ImageBitmaps; the render harness's Skia-backed shim needs its
        // own image type and provides globalThis.loadCanvasImage for it.
        const img = async (v) => {
            if (!v) return null;
            if (v && (v.width > 0) && (v.close || v.src !== undefined)) return v;  // already drawable
            let bytes = null;
            if (typeof v === 'string') {
                const r = await fetch(v);
                bytes = new Uint8Array(await r.arrayBuffer());
            } else if (v instanceof Blob) {
                bytes = new Uint8Array(await v.arrayBuffer());
            } else if (v instanceof ArrayBuffer) bytes = new Uint8Array(v);
            else if (v?.buffer) bytes = new Uint8Array(v.buffer, v.byteOffset ?? 0, v.byteLength);
            if (!bytes) return null;
            if (typeof globalThis.loadCanvasImage === 'function')
                return globalThis.loadCanvasImage(bytes);
            return createImageBitmap(new Blob([bytes]));
        };
        const [fi, bi, si] = await Promise.all([img(front), img(back), img(spine)]);

        const xJ = Math.round(W * uJoint);           // back joint
        const xJ2 = Math.round(W * (1 - uJoint));    // front joint
        // THE AUTHORING CONTRACT: every panel is authored UPRIGHT, exactly
        // as you'd see it looking at the closed book from outside — front
        // and back as portraits (top = head), spine as its tall strip. The
        // composer owns every flip: the ONE continuous strip carries one
        // inherent vertical inversion, so every panel takes the same
        // vertical flip and nothing else. (History: the back once took a
        // horizontal mirror instead — upright art rendered upside down;
        // "fixing" it with 180° made it upright but MIRRORED. The bog
        // book's readable back cover finally showed both.)
        if (bi) {
            ctx.save(); ctx.translate(0, H); ctx.scale(1, -1);    // flipV
            ctx.drawImage(bi, 0, 0, xJ, H); ctx.restore();
        } else if (fi) {                                   // echo front, dimmed
            ctx.save(); ctx.translate(0, H); ctx.scale(1, -1);
            ctx.globalAlpha = 0.25; ctx.drawImage(fi, 0, 0, xJ, H); ctx.restore();
            ctx.globalAlpha = 1;
            ctx.fillStyle = color + 'cc';
            ctx.fillRect(0, 0, xJ, H);
        }
        if (si) {
            ctx.save(); ctx.translate(xJ, H); ctx.scale(1, -1);
            ctx.drawImage(si, 0, 0, xJ2 - xJ, H); ctx.restore();
        }
        if (fi) {
            ctx.save(); ctx.translate(xJ2, H); ctx.scale(1, -1);
            ctx.drawImage(fi, 0, 0, W - xJ2, H); ctx.restore();
        }

        const t = new THREE.CanvasTexture(c);
        t.colorSpace = THREE.SRGBColorSpace;
        t.anisotropy = 8;
        return t;
    }


    return { makeBookRig, composeWrapTexture, solveWrapLayout, canvas2d, DEFAULTS };
});
