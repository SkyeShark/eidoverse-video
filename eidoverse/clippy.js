// clippy.js — globalThis.makeClippy(opts): the Office Assistant, rebuilt as
// an eidoverse character with his COMPLETE original animation vocabulary
// (all 43 Microsoft Agent clip names) as MORPH TARGETS.
//
// The core idea: Clippy's transformations were always the same wire re-bent
// into something else. Here every morph target re-evaluates the WHOLE
// character — wire centerline re-routed (atom orbits, rope pile, floppy,
// envelope, printer, wizard hat), eyes re-homed to their weird places,
// brows and his legal-pad paper riding along — so one influence slider IS
// one transformation.
//
//   const clippy = makeClippy({ height: 1.2 });
//   scene.add(clippy.group);
//   clippy.play('IdleAtom');         // any of the 43 original names
//   clippy.playAll(1.0);             // full showcase; returns [name, t0] order
//   clippy.update(t);                // media-time seconds
//
// Morph classes:
//   pose:  lean tilt squash curl wave tap scratch point
//   face:  blink browUp browDown lookAside lookUp peer
//   shape: shapeAtom shapePile shapeFloppy shapeEnvelope shapePrinter shapeWizard
//   paper: paperUp paperFeed paperCrumple
// Special sequencer tracks: '@scale' (group scale), '@hopY' (bounce),
// '@spinY' (deterministic spin).
(function () {
    'use strict';
    const THREE = globalThis.THREE;
    const TAU = Math.PI * 2;
    const ease = (x) => { x = Math.min(Math.max(x, 0), 1); return x * x * (3 - 2 * x); };

    // ── 3D path machinery: segments sampled to a fixed N ────────────────
    function segsSample(segs, N) {
        // segs marked {ghost:true} are CONNECTORS: sampled like wire but
        // reported so the sweep can pinch their radius to ~0 — the shape
        // reads as disconnected pieces (the original atom is 3 separate
        // rings!) while the tube topology stays continuous and morphable.

        for (const g of segs) {
            if (g.kind === 'l') g.len = Math.hypot(g.p1[0] - g.p0[0], g.p1[1] - g.p0[1], g.p1[2] - g.p0[2]);
            else g.len = Math.abs(g.a1 - g.a0) * (g.r1 + g.r2) * 0.5;
        }
        const total = segs.reduce((s, g) => s + g.len, 0);
        const pts = [];
        const ghost = new Float32Array(N);
        for (let i = 0; i < N; i++) {
            let s = (i / (N - 1)) * total;
            let p = null;
            for (const g of segs) {
                if (s > g.len) { s -= g.len; continue; }
                if (g.ghost) ghost[i] = 1;
                const f = g.len > 1e-9 ? s / g.len : 0;
                if (g.kind === 'l') {
                    p = [g.p0[0] + (g.p1[0] - g.p0[0]) * f, g.p0[1] + (g.p1[1] - g.p0[1]) * f,
                        g.p0[2] + (g.p1[2] - g.p0[2]) * f];
                } else {
                    const a = g.a0 + (g.a1 - g.a0) * f;
                    const c = Math.cos(a) * g.r1, sn = Math.sin(a) * g.r2;
                    p = [g.C[0] + g.U[0] * c + g.V[0] * sn,
                        g.C[1] + g.U[1] * c + g.V[1] * sn,
                        g.C[2] + g.U[2] * c + g.V[2] * sn];
                }
                break;
            }
            if (!p) {
                const g = segs[segs.length - 1];
                if (g.kind === 'l') p = g.p1.slice();
                else {
                    const c = Math.cos(g.a1) * g.r1, sn = Math.sin(g.a1) * g.r2;
                    p = [g.C[0] + g.U[0] * c + g.V[0] * sn, g.C[1] + g.U[1] * c + g.V[1] * sn,
                        g.C[2] + g.U[2] * c + g.V[2] * sn];
                }
            }
            pts.push(new THREE.Vector3(p[0], p[1], p[2]));
        }
        pts.ghost = ghost;
        return pts;
    }
    const L = (p0, p1) => ({ kind: 'l', p0, p1 });
    const GL = (p0, p1) => ({ kind: 'l', p0, p1, ghost: true });
    const E = (C, U, V, r1, r2, a0, a1) => ({ kind: 'e', C, U, V, r1, r2, a0, a1 });
    const UX = [1, 0, 0], UY = [0, 1, 0];

    // ── the gem paperclip (with the wizard-hat head variant) ────────────
    function gemSegs(hat) {
        // REF-CORRECTED (Skye 07-14: "yours is upside down in parts"):
        // the real Clippy is the gem clip narrow-END UP — the small arch
        // is his head crest, the two nested U-bends are his base, and
        // BOTH free ends curl outward near his face like little arms.
        const W = 0.34, d = 0.075;
        const xL = -W / 2, xR = W / 2;              // outer lines
        const xl = -(W / 2 - d), xr = W / 2 - d;    // inner lines
        const rBi = 0.095, rBo = 0.17;              // nested base bends
        const yBi = 0.235, yBo = 0.215;             // lifted: low point 0.045
                                                    // (he CLIPPED into his mat, lol — Skye)
        const rA = (xR - xl) / 2;                   // head arch radius
        const cA = (xR + xl) / 2;                   // head arch center x
        const yA = 1.00 - rA;                       // arch center height
        const s = [];
        // E1: right little arm — curls outward beside the face
        s.push(E([xr + 0.045, 0.66, 0], UX, UY, 0.045, 0.045, Math.PI * 0.55, Math.PI * 1.5));
        s.push(L([xr, 0.64, 0], [xr, yBi, 0]));
        s.push(E([0, yBi, 0], UX, UY, rBi, rBi, 0, -Math.PI));       // inner base U
        s.push(L([xl, yBi, 0], [xl, yA, 0]));
        if (hat) {
            // the head arch becomes a pointed wizard hat, pom and all
            s.push(L([xl, yA, 0], [-0.02, 1.12, 0]));
            s.push(L([-0.02, 1.12, 0], [0.055, 1.33, 0]));
            s.push(E([0.085, 1.335, 0], UX, UY, 0.032, 0.032, Math.PI, -Math.PI * 0.5));
            s.push(L([0.115, 1.30, 0], [0.17, 1.02, 0]));
            s.push(L([0.17, 1.02, 0], [xR, yA, 0]));
        } else {
            s.push(E([cA, yA, 0], UX, UY, rA, rA, Math.PI, 0));      // HEAD ARCH
        }
        s.push(L([xR, yA, 0], [xR, yBo, 0]));
        s.push(E([0, yBo, 0], UX, UY, rBo, rBo, 0, -Math.PI));       // outer base U
        s.push(L([xL, yBo, 0], [xL, 0.62, 0]));
        // E2: left little arm — curls outward-up
        s.push(E([xL - 0.045, 0.62, 0], UX, UY, 0.045, 0.045, 0, Math.PI * 0.95));
        return s;
    }

    // ── transformation shapes: full centerline re-routes ────────────────
    function rotYv(v, a) { return [v[0] * Math.cos(a) + v[2] * Math.sin(a), v[1], -v[0] * Math.sin(a) + v[2] * Math.cos(a)]; }
    function shapeSegs(name) {
        const s = [];
        if (name === 'atom') {
            // the classic Bohr symbol (ref strip 22): three slim ellipses
            // rotated IN the view plane, tiny z offsets, nucleus coil —
            // reads as RINGS, not a wire tangle
            const C = [0, 0.56, 0];
            s.push(E([C[0], C[1], 0.035], UX, UY, 0.05, 0.05, 0, TAU * 1.75));
            let prevEnd = [C[0] + 0.05 * Math.cos(TAU * 1.75), C[1] + 0.05 * Math.sin(TAU * 1.75), 0.035];
            for (let k = 0; k < 3; k++) {
                const ph = (k / 3) * Math.PI;
                const U = [Math.cos(ph) * 0.375, Math.sin(ph) * 0.375, 0];
                const Vv = [-Math.sin(ph) * 0.135, Math.cos(ph) * 0.135, 0];
                const Cz = [C[0], C[1], (k - 1) * 0.028];
                const a0 = Math.PI * 0.25;
                const st = [Cz[0] + U[0] * Math.cos(a0) + Vv[0] * Math.sin(a0),
                    Cz[1] + U[1] * Math.cos(a0) + Vv[1] * Math.sin(a0),
                    Cz[2] + U[2] * Math.cos(a0) + Vv[2] * Math.sin(a0)];
                s.push(GL(prevEnd, st));               // pinched-off bridge
                s.push(E(Cz, U, Vv, 1, 1, a0, a0 + TAU));
                prevEnd = st;
            }
            return s;
        }
        if (name === 'pile') {
            // slumped coil — helix winding down into a pile of wire
            const turns = 5.5, NN = 44;
            let prev = null;
            for (let i = 0; i <= NN; i++) {
                const f = i / NN;
                const a = f * TAU * turns;
                const wob = Math.sin(a * 0.37 + 1.7) * 0.06;   // messy tangle, not a neat cone
                const r = 0.30 - 0.13 * f + wob;
                const p = [Math.cos(a) * r + wob * 0.8, 0.05 + 0.11 * f,
                    Math.sin(a) * r * 0.8 - wob];
                if (prev) s.push(L(prev, p));
                prev = p;
            }
            s.push(L(prev, [prev[0] - 0.03, prev[1] + 0.10, prev[2]]));
            return s;
        }
        if (name === 'floppy') {
            // rounded-square diskette outline + shutter + label swoop
            const w = 0.36, y0 = 0.50, r = 0.05;
            s.push(L([-w + r, y0 - w, 0], [w - r, y0 - w, 0]));
            s.push(E([w - r, y0 - w + r, 0], UX, UY, r, r, -Math.PI / 2, 0));
            s.push(L([w, y0 - w + r, 0], [w, y0 + w - r, 0]));
            s.push(E([w - r, y0 + w - r, 0], UX, UY, r, r, 0, Math.PI / 2));
            s.push(L([w - r, y0 + w, 0], [-w + r, y0 + w, 0]));
            s.push(E([-w + r, y0 + w - r, 0], UX, UY, r, r, Math.PI / 2, Math.PI));
            s.push(L([-w, y0 + w - r, 0], [-w, y0 - w + r, 0]));
            s.push(E([-w + r, y0 - w + r, 0], UX, UY, r, r, Math.PI, Math.PI * 1.5));
            // routing between features dives BEHIND the face plane (the
            // probe showed face-crossing jogs reading as a trapeze)
            s.push(GL([-w + r, y0 - w, -0.05], [-w + 0.04, y0 + w - 0.06, -0.05]));
            s.push(GL([-w + 0.04, y0 + w - 0.06, -0.05], [0.04, y0 + w - 0.05, -0.05]));
            s.push(L([0.04, y0 + w - 0.03, 0.02], [0.04, y0 + 0.20, 0.02]));
            s.push(L([0.04, y0 + 0.20, 0.02], [0.26, y0 + 0.20, 0.02]));
            s.push(L([0.26, y0 + 0.20, 0.02], [0.26, y0 + w - 0.03, 0.02]));
            s.push(GL([0.26, y0 + w - 0.03, -0.05], [0.28, y0 - 0.14, -0.02]));
            s.push(L([0.26, y0 - 0.17, 0.03], [-0.26, y0 - 0.17, 0.03]));
            return s;
        }
        if (name === 'envelope') {
            const w = 0.42, h = 0.26, y0 = 0.46;
            s.push(L([-w, y0 - h, 0], [w, y0 - h, 0]));
            s.push(L([w, y0 - h, 0], [w, y0 + h, 0]));
            s.push(L([w, y0 + h, 0], [-w, y0 + h, 0]));
            s.push(L([-w, y0 + h, 0], [-w, y0 - h, 0]));
            s.push(GL([-w, y0 - h, 0.015], [-w, y0 + h, 0.015]));
            s.push(L([-w, y0 + h, 0.02], [0, y0 - 0.02, 0.03]));
            s.push(L([0, y0 - 0.02, 0.03], [w, y0 + h, 0.02]));
            return s;
        }
        if (name === 'printer') {
            const y0 = 0.16;
            s.push(L([-0.34, y0, 0], [0.34, y0, 0]));
            s.push(L([0.34, y0, 0], [0.34, y0 + 0.22, 0]));
            s.push(L([0.34, y0 + 0.22, 0], [0.24, y0 + 0.22, 0]));
            s.push(L([0.24, y0 + 0.22, 0], [0.24, y0 + 0.36, 0]));
            s.push(L([0.24, y0 + 0.36, 0], [0.10, y0 + 0.36, 0]));
            s.push(L([0.10, y0 + 0.36, 0], [0.10, y0 + 0.30, 0]));
            s.push(L([0.10, y0 + 0.30, 0], [-0.10, y0 + 0.30, 0]));
            s.push(L([-0.10, y0 + 0.30, 0], [-0.10, y0 + 0.36, 0]));
            s.push(L([-0.10, y0 + 0.36, 0], [-0.24, y0 + 0.36, 0]));
            s.push(L([-0.24, y0 + 0.36, 0], [-0.24, y0 + 0.22, 0]));
            s.push(L([-0.24, y0 + 0.22, 0], [-0.34, y0 + 0.22, 0]));
            s.push(L([-0.34, y0 + 0.22, 0], [-0.34, y0, 0]));
            s.push(L([-0.34, y0, 0.03], [-0.26, y0 + 0.10, 0.05]));
            s.push(L([-0.26, y0 + 0.10, 0.05], [-0.18, y0 + 0.10, 0.05]));
            return s;
        }
        if (name === 'check') {
            // Congratulate (ref strip 3): the wire unfurls into a big
            // CHECKMARK planted on the page
            s.push(L([-0.26, 0.52, 0], [-0.02, 0.16, 0]));
            s.push(L([-0.02, 0.16, 0], [0.34, 0.88, 0]));
            s.push(L([0.34, 0.88, 0], [0.30, 0.90, 0.03]));
            s.push(L([0.30, 0.90, 0.03], [0.0, 0.20, 0.03]));
            s.push(L([0.0, 0.20, 0.03], [-0.23, 0.55, 0.03]));
            return s;
        }
        if (name === 'vortex') {
            // EmptyTrash (ref strip 17): an inverted whirlwind cone that
            // shreds the page — wide at top, point at the floor
            const turns = 6.0, NN = 44;
            let prev = null;
            for (let i = 0; i <= NN; i++) {
                const f = i / NN;
                const a = f * TAU * turns;
                const r = 0.34 - 0.28 * f;
                const p = [Math.cos(a) * r, 0.62 - 0.54 * f, Math.sin(a) * r];
                if (prev) s.push(L(prev, p));
                prev = p;
            }
            return s;
        }
        if (name === 'bike') {
            // one continuous wire, no cross-body jumps: grip -> bars ->
            // head tube -> fork -> FRONT WHEEL -> chainstay -> REAR WHEEL
            // -> seat stay -> saddle. Wheels lifted clear of the mat.
            const hubY = 0.20, rW = 0.165;
            s.push(L([0.34, 0.66, 0.05], [0.25, 0.62, 0.02]));           // grip -> stem
            s.push(L([0.25, 0.62, 0.02], [0.21, 0.50, 0.02]));           // head tube
            s.push(L([0.21, 0.50, 0.02], [0.19, hubY + 0.02, 0.02]));    // fork
            s.push(E([0.19, hubY, 0], UX, UY, rW, rW, Math.PI / 2, Math.PI / 2 + TAU));
            s.push(L([0.19, hubY, 0.02], [-0.19, hubY, 0.02]));          // chainstay
            s.push(E([-0.19, hubY, 0], UX, UY, rW, rW, Math.PI / 2, Math.PI / 2 + TAU));
            s.push(L([-0.19, hubY, 0.02], [-0.06, 0.52, 0.02]));         // seat tube
            s.push(L([-0.06, 0.52, 0.02], [0.21, 0.50, 0.03]));          // top tube
            s.push(L([0.21, 0.50, 0.03], [-0.06, 0.52, 0.04]));          // (double back)
            s.push(L([-0.06, 0.52, 0.04], [-0.16, 0.58, 0.04]));         // saddle
            return s;
        }
        if (name === 'mobile') {
            // GetArtsy (ref strip 11): a Calder kinetic mobile — balance
            // arms with hanging elements, his eye as the big piece
            // depth spread: a FLAT mobile collapses to a streak when the
            // spin turns it edge-on (07-14 grid tile)
            s.push(E([0, 1.06, 0], UX, UY, 0.045, 0.045, 0, TAU * 0.75));
            s.push(L([0, 1.02, 0], [0, 0.94, 0]));
            s.push(L([0, 0.94, 0], [-0.30, 0.86, 0.10]));            // left arm (forward)
            s.push(L([-0.30, 0.86, 0.10], [-0.30, 0.68, 0.10]));     // left drop
            s.push(E([-0.30, 0.57, 0.10], UX, UY, 0.11, 0.11, Math.PI / 2, Math.PI * 2.5));
            s.push(L([-0.30, 0.86, 0.10], [0.20, 0.98, -0.09]));     // right arm (back)
            s.push(L([0.20, 0.98, -0.09], [0.20, 0.84, -0.09]));
            s.push(L([0.20, 0.84, -0.09], [0.36, 0.80, -0.02]));     // sub-arm
            s.push(L([0.36, 0.80, -0.02], [0.36, 0.70, -0.02]));
            s.push(E([0.36, 0.645, -0.02], UX, UY, 0.055, 0.055, Math.PI / 2, Math.PI * 2.5));
            return s;
        }
        return gemSegs(false);
    }

    // ── face anchors per shape — the eyes go to WEIRD PLACES ────────────
    const FACE = {
        gem:      { eL: [-0.098, 0.815, 0.05], eR: [0.062, 0.755, 0.055], eS: 1,
                    bL: [-0.118, 0.955, 0.05], bR: [0.085, 0.905, 0.05],
                    bY: 0.99, bX: 0.105, bZ: 0.052, bS: 1 },
        wizard:   { eL: [-0.098, 0.815, 0.05], eR: [0.062, 0.755, 0.055], eS: 1,
                    bL: [-0.118, 0.945, 0.05], bR: [0.085, 0.90, 0.05],
                    bY: 0.97, bX: 0.105, bZ: 0.052, bS: 1 },
        atom:     { eL: [-0.21, 0.42, -0.07], eR: [0.16, 0.75, 0.13], eS: 0.9,
                    pL: [0.265, 0.825, 0.0], pR: [-0.30, 0.375, 0.028],   // free ELECTRONS riding the rings
                    bY: 0.98, bX: 0.30, bZ: -0.02, bS: 0.04 },
        pile:     { eL: [-0.05, 0.27, 0.19], eR: [0.10, 0.26, 0.17], eS: 0.85,
                    bY: 0.385, bX: 0.055, bZ: 0.17, bS: 0.8 },
        floppy:   { eL: [-0.11, 0.60, 0.055], eR: [0.09, 0.60, 0.055], eS: 0.82,
                    bY: 0.735, bX: 0.11, bZ: 0.05, bS: 0.9 },
        envelope: { eL: [-0.10, 0.735, 0.05], eR: [0.10, 0.735, 0.05], eS: 0.78,
                    bY: 0.845, bX: 0.105, bZ: 0.05, bS: 0.85 },
        printer:  { eL: [-0.09, 0.44, 0.10], eR: [0.09, 0.44, 0.10], eS: 0.72,
                    bY: 0.545, bX: 0.10, bZ: 0.09, bS: 0.8 },
        check:    { eL: [-0.27, 0.60, 0.05], eR: [-0.16, 0.66, 0.05], eS: 0.75,
                    bY: 0.76, bX: -0.21, bZ: 0.05, bS: 0.8, bDX: true },
        vortex:   { eL: [-0.07, 0.70, 0.24], eR: [0.09, 0.70, 0.23], eS: 0.8,
                    bY: 0.84, bX: 0.08, bZ: 0.22, bS: 0.7 },
        bike:     { eL: [-0.19, 0.20, 0.06], eR: [0.19, 0.20, 0.06], eS: 1.25,
                    bY: 0.70, bX: 0.28, bZ: 0.04, bS: 0.05 },
        mobile:   { eL: [-0.30, 0.57, 0.135], eR: [0.36, 0.645, 0.015], eS: 1.0,
                    sL: 1.0, sR: 0.5,
                    bY: 1.0, bX: 0.3, bZ: 0, bS: 0.04 },
    };
    function activeShape(pose) {
        if (pose.shapeAtom) return 'atom';
        if (pose.shapePile) return 'pile';
        if (pose.shapeFloppy) return 'floppy';
        if (pose.shapeEnvelope) return 'envelope';
        if (pose.shapePrinter) return 'printer';
        if (pose.shapeWizard) return 'wizard';
        if (pose.shapeCheck) return 'check';
        if (pose.shapeVortex) return 'vortex';
        if (pose.shapeBike) return 'bike';
        if (pose.shapeMobile) return 'mobile';
        return 'gem';
    }

    // ── pose field (gem-family only; shapes carry their own statics) ────
    function rotYZ(v, pivotY, a) {
        const y = v.y - pivotY, z = v.z;
        v.y = pivotY + y * Math.cos(a) - z * Math.sin(a);
        v.z = z * Math.cos(a) + y * Math.sin(a);
    }
    function rotXY(v, pivotY, a) {
        const y = v.y - pivotY, x = v.x;
        v.x = x * Math.cos(a) - y * Math.sin(a);
        v.y = pivotY + y * Math.cos(a) + x * Math.sin(a);
    }
    function applyPose(v, pose) {
        if (pose.curl) {
            const f = ease((0.34 - v.y) / 0.34);
            if (f > 0) rotYZ(v, 0.34, -1.05 * pose.curl * f);
        }
        if (pose.squash) {
            const k = pose.squash;
            v.y = 0.03 + (v.y - 0.03) * (1 - 0.24 * k);
            v.x *= 1 + 0.16 * k;
            v.z *= 1 + 0.16 * k;
        }
        if (pose.tilt) {
            const f = ease((v.y - 0.52) / 0.40);
            if (f > 0) rotXY(v, 0.52, 0.38 * pose.tilt * f);
        }
        if (pose.lean) {
            const f = ease((v.y - 0.16) / 0.72);
            if (f > 0) rotYZ(v, 0.16, -0.52 * pose.lean * f);
        }
    }

    // ── wire sweep (centerline gestures → pose field → tube) ────────────
    function sweepWire(pose, N, RADIAL, wireR) {
        const shape = activeShape(pose);
        const pts = segsSample(shape === 'gem' || shape === 'wizard'
            ? gemSegs(shape === 'wizard') : shapeSegs(shape), N);
        const endHinge = (t0, fn) => {
            const i0 = Math.floor(t0 * (N - 1));
            const hinge = pts[i0].clone();
            for (let i = i0; i < N; i++) fn(pts[i], hinge, ease((i / (N - 1) - t0) / (1 - t0)));
        };
        const startHinge = (t0, fn) => {
            const i0 = Math.ceil(t0 * (N - 1));
            const hinge = pts[i0].clone();
            for (let i = i0; i >= 0; i--) fn(pts[i], hinge, ease((t0 - i / (N - 1)) / t0));
        };
        const gemFam = shape === 'gem' || shape === 'wizard';
        if (gemFam) {
            // E2 (path end) = his LEFT arm: wave / head-scratch.
            // E1 (path start) = his RIGHT arm: point / impatient tap.
            if (pose.wave) endHinge(0.84, (p, h, f) => {
                const a = -1.8 * f * pose.wave;
                const dx = p.x - h.x, dy = p.y - h.y;
                p.x = h.x + dx * Math.cos(a) - dy * Math.sin(a);
                p.y = h.y + dy * Math.cos(a) + dx * Math.sin(a);
                p.z += 0.10 * f * pose.wave;
            });
            if (pose.tap) startHinge(0.06, (p, h, f) => {
                p.y -= 0.10 * f * pose.tap;
                p.z += 0.05 * f * pose.tap;
            });
            if (pose.scratch) endHinge(0.78, (p, h, f) => {
                // long arm from low on the side so the tip lands ON the
                // head arch (the short arm scratched thin air — Skye)
                const a = -2.05 * f * pose.scratch;
                const dx = p.x - h.x, dy = p.y - h.y;
                p.x = h.x + dx * Math.cos(a) - dy * Math.sin(a);
                p.y = h.y + dy * Math.cos(a) + dx * Math.sin(a);
                p.z += 0.09 * f * pose.scratch;
            });
            if (pose.point) startHinge(0.075, (p, h, f) => {
                const a = 1.25 * f * pose.point;
                const dx = p.x - h.x, dy = p.y - h.y;
                p.x = h.x + dx * Math.cos(a) - dy * Math.sin(a);
                p.y = h.y + dy * Math.cos(a) + dx * Math.sin(a);
                p.z += 0.12 * f * pose.point;
            });
            for (const p of pts) applyPose(p, pose);
        }
        // parallel-transport tube (fixed seed normal, NaN-guarded)
        const tans = [], nors = [], bins = [];
        for (let i = 0; i < N; i++) {
            const a = pts[Math.max(i - 1, 0)], b = pts[Math.min(i + 1, N - 1)];
            tans.push(new THREE.Vector3().subVectors(b, a).normalize());
        }
        let n0 = new THREE.Vector3(0, 0, 1);
        n0.sub(tans[0].clone().multiplyScalar(n0.dot(tans[0]))).normalize();
        if (!Number.isFinite(n0.x) || n0.lengthSq() < 0.5) n0.set(0, 1, 0);
        for (let i = 0; i < N; i++) {
            if (i > 0) {
                const axis = new THREE.Vector3().crossVectors(tans[i - 1], tans[i]);
                const s2 = axis.length();
                if (s2 > 1e-8) {
                    axis.multiplyScalar(1 / s2);
                    n0 = n0.clone().applyAxisAngle(axis, Math.asin(Math.min(s2, 1)));
                }
                n0.sub(tans[i].clone().multiplyScalar(n0.dot(tans[i]))).normalize();
                if (!Number.isFinite(n0.x) || n0.lengthSq() < 0.5) n0.set(0, 1, 0);
            }
            nors.push(n0.clone());
            bins.push(new THREE.Vector3().crossVectors(tans[i], n0).normalize());
        }
        // ghost spans pinch the tube to a hairline (smoothed over
        // neighbours so the pinch-off reads as the wire splitting)
        const g0 = pts.ghost || new Float32Array(N);
        const rMul = new Float32Array(N).fill(1);
        for (let i = 0; i < N; i++) {
            if (!g0[i]) continue;
            for (let k = -3; k <= 3; k++) {
                const ii = Math.min(Math.max(i + k, 0), N - 1);
                rMul[ii] = Math.min(rMul[ii], 0.03 + 0.97 * Math.abs(k) / 4);
            }
        }
        const pos = [], nor = [], idx = [];
        for (let i = 0; i < N; i++) {
            const rr = wireR * rMul[i];
            for (let j = 0; j < RADIAL; j++) {
                const th = (j / RADIAL) * TAU;
                const nrm = nors[i].clone().multiplyScalar(Math.cos(th))
                    .addScaledVector(bins[i], Math.sin(th));
                pos.push(pts[i].x + nrm.x * rr, pts[i].y + nrm.y * rr,
                    pts[i].z + nrm.z * rr);
                nor.push(nrm.x, nrm.y, nrm.z);
            }
        }
        for (let i = 0; i < N - 1; i++) {
            for (let j = 0; j < RADIAL; j++) {
                const a = i * RADIAL + j, b = i * RADIAL + (j + 1) % RADIAL;
                idx.push(a, a + RADIAL, b, b, a + RADIAL, b + RADIAL);
            }
        }
        return { pos, nor, idx, ends: [pts[0], pts[N - 1]] };
    }

    // ── ellipsoid part (eyes, pupils, brows, caps) ──────────────────────
    function sphere(pose, center, r, o) {
        o = o || {};
        const seg = o.seg || 14;
        const g = new THREE.SphereGeometry(1, seg, seg);
        const pa = g.getAttribute('position');
        const pos = [], nor = [], idx = Array.from(g.getIndex().array);
        for (let i = 0; i < pa.count; i++) {
            const v = new THREE.Vector3(pa.getX(i) * r[0], pa.getY(i) * r[1], pa.getZ(i) * r[2]);
            if (o.roll) {
                const x = v.x, y = v.y;
                v.x = x * Math.cos(o.roll) - y * Math.sin(o.roll);
                v.y = y * Math.cos(o.roll) + x * Math.sin(o.roll);
            }
            if (o.yaw) {
                const x = v.x, z = v.z;
                v.x = x * Math.cos(o.yaw) + z * Math.sin(o.yaw);
                v.z = z * Math.cos(o.yaw) - x * Math.sin(o.yaw);
            }
            if (o.scale != null) v.multiplyScalar(o.scale);
            if (o.blinkK) v.y *= 1 - 0.80 * o.blinkK;
            v.x += center.x + (o.dx || 0);
            v.y += center.y + (o.dy || 0);
            v.z += center.z + (o.dz || 0);
            if (o.posed !== false) applyPose(v, pose);
            pos.push(v.x, v.y, v.z);
            nor.push(0, 1, 0);
        }
        g.dispose();
        return { pos, nor, idx };
    }

    // ── the paper: his lined legal-pad page (a prop with its own life) ──
    function paperPart(pose) {
        const GX = 16, GY = 20, W2 = 0.36, H2 = 0.50;
        const pos = [], nor = [], uv = [], idx = [];
        const fUp = pose.paperUp || 0, fFeed = pose.paperFeed || 0, fCr = pose.paperCrumple || 0;
        for (let j = 0; j <= GY; j++) {
            for (let i = 0; i <= GX; i++) {
                const u = i / GX, w = j / GY;
                // REF (fullscreen showcase): the page LEANS behind him
                // (~30 deg from vertical), bottom edge at his base, top-right
                // corner curling; he stands in front of its lower edge.
                const gx = (u - 0.5) * W2 * 2, gy = w * H2 * 2;
                const curl = 0.22 * Math.pow(Math.max(u + w - 1.35, 0) / 0.65, 2)
                    + 0.10 * Math.pow(Math.max((1 - u) - w - 0.45, 0) / 0.55, 2);
                let px = 0.07 + gx * 0.965 + gy * 0.115 - curl * gx * 0.3;
                let py = 0.012 + gy * 0.845 + curl * 0.55;
                let pz = -0.115 - gy * 0.50 + gx * 0.155 + curl * 0.6;
                if (fCr) {
                    // EmptyTrash: the wad gets pulled UP into the vortex
                    const h1 = Math.sin(i * 12.9898 + j * 78.233) * 43758.5453;
                    const h2 = Math.sin(i * 39.425 + j * 11.135) * 24634.6345;
                    const tx = gx * 0.42 + (h1 - Math.floor(h1) - 0.5) * 0.15;
                    const ty = 0.38 + (gy - 0.5) * 0.35 + (h2 - Math.floor(h2) - 0.5) * 0.15;
                    const tz = Math.sin(h1) * 0.07;
                    px += (tx - px) * fCr; py += (ty - py) * fCr; pz += (tz - pz) * fCr;
                }
                if (fUp) {   // held up front like a checklist/canvas
                    const tx = -0.02 + gx, ty = 0.30 + gy * 0.9, tz = 0.30 - 0.05 * gy;
                    px += (tx - px) * fUp; py += (ty - py) * fUp; pz += (tz - pz) * fUp;
                }
                if (fFeed) { // feeding out of the printer slot, upright
                    const tx = gx * 0.7, ty = 0.56 + gy * 0.75, tz = 0.02 * Math.sin(w * 9);
                    px += (tx - px) * fFeed; py += (ty - py) * fFeed; pz += (tz - pz) * fFeed;
                }
                pos.push(px, py, pz);
                nor.push(0, 1, 0);
                uv.push(u, w);
            }
        }
        for (let j = 0; j < GY; j++) {
            for (let i = 0; i < GX; i++) {
                const a = j * (GX + 1) + i, b = a + 1, c = a + GX + 1, d2 = c + 1;
                idx.push(a, b, c, b, d2, c);
            }
        }
        return { pos, nor, idx, uv };
    }

    // ── full-character evaluation ───────────────────────────────────────
    function buildAll(pose, C) {
        const parts = [];
        const wire = sweepWire(pose, C.N, C.RADIAL, C.wireR);
        parts.push({ ...wire, mat: 0 });
        for (const e of wire.ends) {
            parts.push({ ...sphere({}, e, [C.wireR, C.wireR, C.wireR], { seg: 10, posed: false }), mat: 0 });
        }
        const F = FACE[activeShape(pose)];
        const browUp = pose.browUp || 0, browDn = pose.browDown || 0;
        const blink = pose.blink || 0;
        const lookX = (pose.lookAside || 0) * 0.030;
        const lookY = (pose.lookUp || 0) * 0.028;
        const peer = pose.peer || 0;
        const bulge = pose.bulge || 0;         // ref: eyes SCALE UP for emphasis
        const droop = pose.droopEyes || 0;     // ref: eyes wander down the wire
        for (const s of [-1, 1]) {
            const ec = new THREE.Vector3(...(s < 0 ? F.eL : F.eR));
            if (droop) ec.lerp(new THREE.Vector3(s * 0.015, s < 0 ? 0.40 : 0.24, 0.09), droop);
            const perSide = s < 0 ? (F.sL ?? 1) : (F.sR ?? 1);
            const eyeScale = F.eS * perSide * (1 + (s < 0 ? 0.55 : -0.42) * peer)
                * (1 + 0.45 * bulge);
            parts.push({ ...sphere(pose, ec, [0.095, 0.130, 0.055],
                { blinkK: blink, scale: eyeScale }), mat: 1 });
            const pOver = s < 0 ? F.pL : F.pR;
            // pupil offsets scale WITH the eye — a fixed offset let the
            // bulged/peered white swallow the pupil (Skye: pupils vanish)
            const pc = pOver
                ? new THREE.Vector3(pOver[0], pOver[1], pOver[2])
                : new THREE.Vector3(ec.x - s * 0.012 * eyeScale,
                    ec.y - 0.024 * eyeScale, ec.z + 0.052 * eyeScale);
            parts.push({ ...sphere(pose, pc,
                [0.042, 0.052, 0.017],
                { blinkK: pOver ? 0 : blink, dx: lookX, dy: lookY,
                  scale: pOver ? 1 : eyeScale, seg: 10 }), mat: 2 });
            // brows — or, in the phones morph, chunky HEADPHONE CUPS
            const phones = pose.phones || 0;
            const bOver = s < 0 ? F.bL : F.bR;
            const bc = bOver
                ? new THREE.Vector3(bOver[0], bOver[1], bOver[2])
                : (F.bDX
                    ? new THREE.Vector3(F.bX + (s > 0 ? 0.11 : 0), F.bY, F.bZ)
                    : new THREE.Vector3(s * F.bX, F.bY, F.bZ));
            if (phones) bc.lerp(new THREE.Vector3(s * 0.165, 0.775, 0.03), phones);
            const roll = (1 - phones) * s * (-0.18 - 0.42 * browDn + 0.38 * browUp);
            parts.push({ ...sphere(pose, bc,
                [0.066, 0.019, 0.024],
                { roll, yaw: phones * s * 1.45,
                  dy: (0.038 * browUp - 0.032 * browDn) * (1 - phones),
                  scale: F.bS * (1 + 2.0 * phones), seg: 10 }), mat: 2 });
        }
        // HEADBAND (Hearing_1): thin black band arcing over the arch,
        // tucked invisible until the phones morph
        {
            const hk = pose.phones || 0;
            parts.push({ ...sphere(pose,
                new THREE.Vector3(0.03, 0.88 + 0.10 * hk, 0.0),
                [0.175, 0.075, 0.03],
                { scale: 0.012 + 0.988 * hk, seg: 10 }), mat: 2 });
        }
        // PENCIL (ref: Writing) — tucked invisible inside the body until
        // the pencil morph holds it at the writing end
        {
            const pk = pose.pencil || 0;
            const pcen = new THREE.Vector3(0.0, 0.55, -0.01).lerp(
                new THREE.Vector3(0.24, 0.34, 0.15), pk);
            const proll = -0.9 * pk;
            const psc = 0.012 + 0.988 * pk;
            parts.push({ ...sphere(pose, pcen, [0.016, 0.15, 0.016],
                { roll: proll, scale: psc, seg: 8 }), mat: 4 });
            const tipOff = new THREE.Vector3(Math.sin(proll) * 0.15, -Math.cos(proll) * 0.15, 0)
                .multiplyScalar(psc);
            parts.push({ ...sphere(pose, pcen.clone().add(tipOff), [0.017, 0.035, 0.017],
                { roll: proll, scale: psc, seg: 8 }), mat: 2 });
        }
        parts.push({ ...paperPart(pose), mat: 3 });
        const pos = [], nor = [], uv = [], idx = [], matRuns = [];
        let vBase = 0;
        for (const p of parts) {
            for (const v of p.idx) idx.push(v + vBase);
            pos.push(...p.pos); nor.push(...p.nor);
            const nv = p.pos.length / 3;
            if (p.uv) uv.push(...p.uv);
            else for (let i = 0; i < nv; i++) uv.push(0, 0);
            matRuns.push({ mat: p.mat, count: p.idx.length });
            vBase += nv;
        }
        const groups = [];
        let run = 0;
        for (const r of matRuns) {
            groups.push({ start: run, count: r.count, mat: r.mat });
            run += r.count;
        }
        return { pos: new Float32Array(pos), uv: new Float32Array(uv), idx, groups };
    }

    // ── the lined legal-pad texture ─────────────────────────────────────
    function paperTexture() {
        const W = 64, H = 88;
        const d = new Uint8Array(W * H * 4);
        for (let j = 0; j < H; j++) {
            for (let i = 0; i < W; i++) {
                const k = (j * W + i) * 4;
                let r = 244, g = 232, b = 168;
                if (j % 8 === 2 && j > 8) { r = 150; g = 175; b = 215; }
                if (i === 9) { r = 225; g = 130; b = 130; }
                d[k] = r; d[k + 1] = g; d[k + 2] = b; d[k + 3] = 255;
            }
        }
        const t = new THREE.DataTexture(d, W, H, THREE.RGBAFormat, THREE.UnsignedByteType);
        t.needsUpdate = true;
        t.magFilter = THREE.LinearFilter;
        t.minFilter = THREE.LinearFilter;
        t.colorSpace = THREE.SRGBColorSpace;
        return t;
    }

    globalThis.makeClippy = function makeClippy(opts = {}) {
        const C = { N: 700, RADIAL: 20, wireR: opts.wireRadius ?? 0.031 };
        const H = opts.height ?? 1.2;
        const MORPHS = [
            'lean', 'tilt', 'squash', 'curl', 'wave', 'tap', 'scratch', 'point',
            'blink', 'browUp', 'browDown', 'lookAside', 'lookUp', 'peer',
            'bulge', 'phones', 'droopEyes', 'pencil',
            'shapeAtom', 'shapePile', 'shapeFloppy', 'shapeEnvelope', 'shapePrinter', 'shapeWizard',
            'shapeCheck', 'shapeVortex', 'shapeBike', 'shapeMobile',
            'paperUp', 'paperFeed', 'paperCrumple',
        ];

        const geoOf = (pose) => {
            const b = buildAll(pose, C);
            const g = new THREE.BufferGeometry();
            g.setAttribute('position', new THREE.BufferAttribute(b.pos, 3));
            g.setAttribute('uv', new THREE.BufferAttribute(b.uv, 2));
            g.setIndex(b.idx);
            g.computeVertexNormals();
            return { g, groups: b.groups };
        };

        const base = geoOf({});
        const geometry = base.g;
        // merge consecutive same-material runs FULLY before registering —
        // addGroup copies its args (mutating after silently drops parts)
        const runs = [];
        for (const gr of base.groups) {
            const cur = runs[runs.length - 1];
            if (cur && cur.materialIndex === gr.mat) cur.count += gr.count;
            else runs.push({ start: gr.start, count: gr.count, materialIndex: gr.mat });
        }
        for (const r of runs) geometry.addGroup(r.start, r.count, r.materialIndex);
        geometry.morphTargetsRelative = true;
        geometry.morphAttributes.position = [];
        geometry.morphAttributes.normal = [];
        const basePos = geometry.getAttribute('position');
        const baseNor = geometry.getAttribute('normal');
        for (const name of MORPHS) {
            const m = geoOf({ [name]: 1 });
            const mp = m.g.getAttribute('position');
            const mn = m.g.getAttribute('normal');
            const dp = new Float32Array(mp.count * 3);
            const dn = new Float32Array(mp.count * 3);
            for (let i = 0; i < mp.count * 3; i++) {
                dp[i] = mp.array[i] - basePos.array[i];
                dn[i] = mn.array[i] - baseNor.array[i];
            }
            const ap = new THREE.BufferAttribute(dp, 3); ap.name = name;
            const an = new THREE.BufferAttribute(dn, 3); an.name = name;
            geometry.morphAttributes.position.push(ap);
            geometry.morphAttributes.normal.push(an);
            m.g.dispose();
        }

        const chrome = new THREE.MeshStandardMaterial({
            color: 0xcdd3dc, metalness: 1.0, roughness: 0.17 });
        const white = new THREE.MeshStandardMaterial({
            color: 0xffffff, metalness: 0.0, roughness: 0.32 });
        const black = new THREE.MeshStandardMaterial({
            color: 0x14161a, metalness: 0.1, roughness: 0.42 });
        const paper = new THREE.MeshStandardMaterial({
            map: paperTexture(), roughness: 0.92, metalness: 0.0,
            side: THREE.DoubleSide });
        const pencilY = new THREE.MeshStandardMaterial({
            color: 0xe8b93c, roughness: 0.6, metalness: 0.0 });
        const mesh = new THREE.Mesh(geometry, [chrome, white, black, paper, pencilY]);
        mesh.castShadow = true; mesh.frustumCulled = false;
        mesh.scale.setScalar(H);
        const group = new THREE.Group();
        group.add(mesh);
        if (!mesh.morphTargetInfluences) mesh.updateMorphTargets();
        const mi = mesh.morphTargetInfluences;
        const midx = {};
        MORPHS.forEach((n, i) => { midx[n] = i; });

        // ── the 43 original clips ───────────────────────────────────────
        const T = (dur, tracks) => ({ dur, tracks });
        const hold = (a, b, w, dur) => [[a, 0], [a + 0.45, w], [b, w], [Math.min(b + 0.5, dur), 0]];
        const CLIPS = {
            RestPose: T(1.6, {}),
            Idle1_1: T(4.2, { droopEyes: [[0.4, 0], [1.2, 1], [3.2, 1], [4.0, 0]],
                lookAside: [[1.4, 0], [1.9, 0.6], [2.5, -0.6], [3.0, 0]] }),
            IdleEyeBrowRaise: T(2.2, { browUp: [[0.3, 0], [0.6, 0.9], [0.9, 0.1], [1.2, 0.9], [1.8, 0]] }),
            IdleSideToSide: T(3.6, {
                tilt: [[0.2, 0], [0.9, 0.6], [1.8, -0.6], [2.7, 0.5], [3.5, 0]],
                lookAside: [[0.2, 0], [0.9, 0.8], [1.8, -0.8], [2.7, 0.7], [3.5, 0]] }),
            IdleFingerTap: T(3.2, {
                tap: [[0.2, 0], [0.5, 0.9], [0.7, 0.35], [0.9, 0.9], [1.1, 0.35], [1.3, 0.9],
                    [1.5, 0.35], [1.7, 0.9], [2.1, 0.9], [2.8, 0]],
                lookAside: hold(0.3, 2.4, -0.6, 3.2) }),
            IdleHeadScratch: T(3.6, {
                scratch: [[0.3, 0], [1.0, 1], [1.25, 0.84], [1.5, 1], [1.75, 0.84], [2.0, 1], [2.9, 0]],
                tilt: hold(0.3, 2.6, 0.4, 3.6), browDown: hold(0.4, 2.6, 0.5, 3.6) }),
            IdleSnooze: T(5.6, {
                shapePile: [[0.5, 0], [1.7, 0.85], [4.6, 0.85], [5.5, 0]],
                blink: [[1.2, 0], [1.9, 0.95], [4.4, 0.95], [5.2, 0]],
                browDown: [[1.0, 0], [1.8, 0.3], [4.4, 0.3], [5.2, 0]] }),
            IdleRopePile: T(6.4, {
                droopEyes: [[0.3, 0], [1.0, 1], [1.6, 1], [2.2, 0]],
                shapePile: [[1.6, 0], [2.6, 1], [5.2, 1], [6.2, 0]],
                blink: [[3.4, 0], [3.55, 1], [3.7, 0]] }),
            IdleAtom: T(5.8, { shapeAtom: [[0.4, 0], [1.6, 1], [4.6, 1], [5.6, 0]],
                // electrons drift along the rings via the pupil-look
                // morphs — the page must NOT spin (it rode @spinY before)
                lookAside: [[1.8, 0], [2.5, 0.9], [3.2, -0.9], [3.9, 0.9], [4.5, 0]],
                lookUp: [[1.8, 0], [2.2, 0.7], [2.9, -0.7], [3.6, 0.7], [4.3, -0.5], [4.8, 0]] }),
            Alert: T(2.4, { lean: [[0.1, 0], [0.4, 0.9], [1.9, 0.9], [2.4, 0]],
                browUp: [[0.1, 0], [0.35, 0.85], [2.0, 0.85], [2.4, 0]],
                bulge: [[0.1, 0], [0.35, 1.2], [1.9, 1.2], [2.4, 0]],
                squash: [[0.4, 0], [0.5, 0.4], [0.62, 0], [0.74, 0.4], [0.86, 0]] }),
            GetAttention: T(3.0, { browUp: hold(0.2, 2.4, 0.85, 3.0),
                bulge: hold(0.2, 2.3, 1.2, 3.0),
                tap: [[0.4, 0], [0.7, 0.8], [1.9, 0.8], [2.4, 0]],
                squash: [[0.3, 0], [0.5, -0.22], [1.9, -0.22], [2.4, 0]],
                '@hopY': [[0.3, 0], [0.6, 1], [1.6, 1], [2.2, 0]] }),
            Greeting: T(3.2, {
                wave: [[0.2, 0], [0.7, 1], [1.0, 0.55], [1.3, 1], [1.6, 0.55], [1.9, 1], [2.6, 0]],
                browUp: hold(0.1, 2.4, 0.75, 3.2), lean: hold(0.2, 2.4, 0.45, 3.2),
                tilt: hold(0.3, 2.3, 0.4, 3.2) }),
            Wave: T(2.8, {
                wave: [[0.15, 0], [0.55, 1], [0.85, 0.5], [1.15, 1], [1.45, 0.5], [1.75, 1], [2.4, 0]],
                browUp: hold(0.1, 2.1, 0.7, 2.8) }),
            Explain: T(3.0, { point: hold(0.25, 2.3, 0.9, 3.0),
                browUp: hold(0.3, 2.2, 0.45, 3.0), lookAside: hold(0.3, 2.2, -0.5, 3.0) }),
            GestureRight: T(2.4, { wave: hold(0.2, 1.8, 0.85, 2.4), lookAside: hold(0.2, 1.8, 0.7, 2.4) }),
            GestureLeft: T(2.4, { point: hold(0.2, 1.8, 0.9, 2.4), lookAside: hold(0.2, 1.8, -0.7, 2.4),
                tilt: hold(0.2, 1.8, -0.3, 2.4) }),
            GestureUp: T(2.4, { wave: hold(0.2, 1.8, 0.7, 2.4), lookUp: hold(0.2, 1.8, 0.85, 2.4),
                browUp: hold(0.2, 1.8, 0.6, 2.4), lean: hold(0.2, 1.8, -0.2, 2.4) }),
            GestureDown: T(2.4, { tap: hold(0.2, 1.8, 0.85, 2.4), lean: hold(0.2, 1.8, 0.5, 2.4),
                lookUp: hold(0.2, 1.8, -0.85, 2.4) }),
            LookRight: T(2.0, { lookAside: hold(0.2, 1.5, 0.95, 2.0), tilt: hold(0.2, 1.5, 0.15, 2.0) }),
            LookLeft: T(2.0, { lookAside: hold(0.2, 1.5, -0.95, 2.0), tilt: hold(0.2, 1.5, -0.15, 2.0) }),
            LookUp: T(2.0, { lookUp: hold(0.2, 1.5, 0.95, 2.0), browUp: hold(0.2, 1.5, 0.3, 2.0) }),
            LookDown: T(2.0, { lookUp: hold(0.2, 1.5, -0.95, 2.0) }),
            LookUpRight: T(2.0, { lookUp: hold(0.2, 1.5, 0.8, 2.0), lookAside: hold(0.2, 1.5, 0.8, 2.0) }),
            LookUpLeft: T(2.0, { lookUp: hold(0.2, 1.5, 0.8, 2.0), lookAside: hold(0.2, 1.5, -0.8, 2.0) }),
            LookDownRight: T(2.0, { lookUp: hold(0.2, 1.5, -0.8, 2.0), lookAside: hold(0.2, 1.5, 0.8, 2.0) }),
            LookDownLeft: T(2.0, { lookUp: hold(0.2, 1.5, -0.8, 2.0), lookAside: hold(0.2, 1.5, -0.8, 2.0) }),
            CheckingSomething: T(4.2, { paperUp: [[0.3, 0], [1.0, 1], [3.4, 1], [4.1, 0]],
                lookUp: hold(0.5, 3.2, -0.6, 4.2), browDown: hold(0.5, 3.2, 0.3, 4.2),
                lookAside: [[1.2, 0], [1.9, 0.5], [2.6, -0.5], [3.2, 0]] }),
            Writing: T(4.6, { pencil: [[0.3, 0], [0.9, 1], [3.8, 1], [4.5, 0]],
                lean: [[0.5, 0], [1.1, 1.05], [1.5, 0.9], [1.9, 1.1], [2.3, 0.9],
                    [2.7, 1.1], [3.1, 0.95], [3.8, 1.0], [4.4, 0]],
                lookUp: hold(0.5, 3.6, -0.9, 4.6) }),
            Processing: T(3.6, { browDown: hold(0.3, 2.8, 0.55, 3.6),
                tilt: [[0.3, 0], [0.8, 0.3], [1.3, -0.3], [1.8, 0.3], [2.3, -0.3], [2.9, 0]],
                lookAside: [[0.3, 0], [0.7, 0.7], [1.1, -0.7], [1.5, 0.7], [1.9, -0.7], [2.5, 0]],
                squash: [[0.5, 0], [0.7, 0.12], [0.9, 0], [1.1, 0.12], [1.3, 0], [1.5, 0.12], [1.7, 0]] }),
            Thinking: T(3.4, { tilt: [[0.2, 0], [0.8, -0.8], [2.8, -0.8], [3.4, 0]],
                browDown: hold(0.2, 2.7, 0.9, 3.4), lookUp: hold(0.3, 2.6, 1, 3.4),
                lookAside: [[0.3, 0], [0.9, 0.7], [1.9, 0.7], [2.2, -0.5], [2.6, -0.5], [3.2, 0]] }),
            Searching: T(3.8, { peer: [[0.3, 0], [0.9, 1], [3.0, 1], [3.7, 0]],
                lean: hold(0.3, 3.0, 0.5, 3.8), browDown: hold(0.3, 3.0, 0.25, 3.8),
                lookAside: [[0.5, 0], [1.2, 0.8], [2.0, -0.8], [2.8, 0.6], [3.4, 0]] }),
            Hearing_1: T(3.6, { phones: [[0.2, 0], [0.7, 1], [2.9, 1], [3.5, 0]],
                tilt: [[0.8, 0], [1.1, 0.35], [1.4, -0.35], [1.7, 0.35], [2.0, -0.35], [2.3, 0.35], [2.7, 0]],
                squash: [[0.9, 0], [1.1, 0.08], [1.3, 0], [1.5, 0.08], [1.7, 0], [1.9, 0.08], [2.1, 0]] }),
            Congratulate: T(4.6, { shapeCheck: [[0.3, 0], [1.2, 1], [3.6, 1], [4.5, 0]],
                browUp: [[1.2, 0], [1.6, 0.8], [3.4, 0.8], [4.0, 0]],
                '@hopY': [[1.4, 0], [1.7, 0.7], [2.6, 0.7], [3.1, 0]] }),
            GetArtsy: T(5.0, { shapeMobile: [[0.3, 0], [1.3, 1], [4.0, 1], [4.9, 0]],
                tilt: [[1.6, 0], [2.4, 0.25], [3.2, -0.25], [4.0, 0.2], [4.6, 0]] }),
            GetTechy: T(4.0, { browDown: hold(0.3, 3.2, 0.45, 4.0), lean: hold(0.3, 3.2, 0.45, 4.0),
                tap: [[0.5, 0], [0.65, 0.6], [0.8, 0.2], [0.95, 0.6], [1.1, 0.2], [1.25, 0.6],
                    [1.4, 0.2], [1.55, 0.6], [1.7, 0.2], [1.85, 0.6], [2.4, 0.6], [3.2, 0]],
                lookAside: [[0.4, 0], [0.7, 0.5], [1.0, -0.5], [1.3, 0.5], [1.6, -0.5], [2.2, 0]] }),
            GetWizardy: T(4.8, { shapeWizard: [[0.3, 0], [1.2, 1], [3.8, 1], [4.7, 0]],
                wave: [[1.4, 0], [1.9, 0.8], [2.3, 0.45], [2.7, 0.8], [3.1, 0.45], [3.6, 0]],
                browUp: [[1.2, 0], [1.7, 0.6], [3.4, 0.6], [4.0, 0]] }),
            Save: T(4.6, { shapeFloppy: [[0.4, 0], [1.4, 1], [3.5, 1], [4.5, 0]],
                blink: [[2.2, 0], [2.35, 1], [2.5, 0]] }),
            Print: T(5.2, { shapePrinter: [[0.4, 0], [1.4, 1], [4.2, 1], [5.1, 0]],
                paperFeed: [[1.6, 0], [2.4, 0.55], [3.6, 1], [4.1, 1], [4.7, 0]] }),
            EmptyTrash: T(5.0, { shapeVortex: [[0.3, 0], [1.2, 1], [4.0, 1], [4.9, 0]],
                paperCrumple: [[0.9, 0], [1.8, 1], [3.8, 1], [4.5, 0]],
                '@spinY': [[1.9, 0], [2.3, 2.2], [3.7, 2.2], [4.1, 0]] }),
            SendMail: T(4.6, { shapeEnvelope: [[0.4, 0], [1.4, 1], [3.5, 1], [4.4, 0]],
                '@hopY': [[3.4, 0], [3.7, 1], [4.1, 0]] }),
            Show: T(2.6, { '@scale': [[0, 0.01], [0.55, 1.14], [0.85, 0.95], [1.15, 1]],
                browUp: [[0.6, 0], [1.0, 0.8], [2.1, 0.8], [2.6, 0]],
                wave: [[0.9, 0], [1.4, 0.8], [2.2, 0]] }),
            Hide: T(2.2, { '@scale': [[0.2, 1], [0.8, 1.09], [1.7, 0.01], [2.2, 0.01]],
                squash: [[0.3, 0], [0.9, 0.5], [1.6, 0]],
                browUp: [[0.2, 0], [0.5, 0.7], [1.2, 0]] }),
            GoodBye: T(12.0, {
                wave: [[0.3, 0], [0.8, 1], [1.15, 0.5], [1.5, 1], [2.1, 0]],
                shapeBike: [[2.0, 0], [3.0, 1], [5.6, 1]],
                '@slideX': [[3.4, 0], [5.4, 1]],
                '@scale': [[4.6, 1], [5.5, 0.01]] }),
        };
        const active = [];

        function evalTrack(keys, t) {
            // tracks HOLD their first/last key values at both ends — the
            // old zero-outside behavior hid the whole GoodBye lead-up
            // (@scale starting at 4.6 meant scale=0 from t=0)
            if (t <= keys[0][0]) return keys[0][1];
            for (let i = 0; i < keys.length - 1; i++) {
                const [ta, wa] = keys[i], [tb, wb] = keys[i + 1];
                if (t >= ta && t <= tb) return wa + (wb - wa) * ease((t - ta) / Math.max(tb - ta, 1e-6));
            }
            return keys[keys.length - 1][1];
        }
        const hash1 = (k) => { const s = Math.sin(k * 12.9898) * 43758.5453; return s - Math.floor(s); };

        const W = {};
        for (const n of MORPHS) W[n] = 0;

        const api = {
            group, mesh, morphs: MORPHS.slice(), clips: Object.keys(CLIPS),
            play(name, t0) { if (CLIPS[name]) active.push({ clip: CLIPS[name], t0: t0 ?? api._t ?? 0, name }); },
            playAll(t0, gap) {
                let t = t0 ?? 0.8;
                const order = [];
                for (const name of Object.keys(CLIPS)) {
                    api.play(name, t);
                    order.push([name, t, CLIPS[name].dur]);
                    t += CLIPS[name].dur + (gap ?? 0.5);
                }
                return order;
            },
            setWeight(n, w) { W[n] = w; },
            currentClip(t) {
                for (const a of active) if (t >= a.t0 && t <= a.t0 + a.clip.dur) return a.name;
                return '';
            },
            _t: 0,
            update(t) {
                api._t = t;
                for (const n of MORPHS) W[n] = 0;
                let scale = 1, hop = 0, spin = 0, slide = 0, anyClip = false;
                for (const a of active) {
                    const ct = t - a.t0;
                    if (ct < 0 || ct > a.clip.dur + 0.1) continue;
                    anyClip = true;
                    for (const [n, keys] of Object.entries(a.clip.tracks)) {
                        const w = evalTrack(keys, ct);
                        if (n === '@scale') scale = w;
                        else if (n === '@hopY') hop = w;
                        else if (n === '@spinY') spin += w * ct;
                        else if (n === '@slideX') slide = w;
                        else W[n] += w;
                    }
                }
                if (!anyClip) {   // idle fidgets only BETWEEN clips (agent-authentic)
                    const bi = Math.floor(t / 2.8);
                    const bt = t - (bi * 2.8 + 2.0 * hash1(bi + 3));
                    if (bt > 0 && bt < 0.22) W.blink += Math.sin((bt / 0.22) * Math.PI);
                    const wi = Math.floor(t / 4.3);
                    const wt = t - (wi * 4.3 + 2.6 * hash1(wi + 11));
                    if (wt > 0 && wt < 0.5 && hash1(wi) > 0.45) {
                        W.browUp += 0.5 * Math.sin((wt / 0.5) * Math.PI);
                    }
                }
                group.scale.setScalar(Math.max(scale, 0.01));
                group.position.x = slide * -2.6;
                group.position.y = 0.012 * H * Math.sin(t * 1.7)
                    + hop * Math.abs(Math.sin(t * Math.PI * 3.2)) * 0.13 * H;
                group.rotation.z = 0.022 * Math.sin(t * 0.9 + 1.3);
                group.rotation.y = 0.05 * Math.sin(t * 0.53) + spin * 1.9;
                for (const n of MORPHS) mi[midx[n]] = Math.min(Math.max(W[n], -1), 1.25);
            },
        };
        return api;
    };
})();
