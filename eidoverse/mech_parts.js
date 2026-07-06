// mech_parts.js — globalThis.MechParts: procedural MECHANICAL part generators.
// The geometry vocabulary under robotics_kit's makeRobot/makeBot — machined
// housings, castings, cables, treads, wheels, greebles — all setup-time
// geometry (no per-frame CPU vertex work; the one sanctioned exception is
// tread-plate instance matrices, see scrollTread).
//
//   MechParts.chamferedBox(w, h, d, chamfer, material)         // crisp-facet box
//   MechParts.motorHousing({ r, len, finN, material })          // finned lathe motor
//   MechParts.gearboxBell({ inR, bellR, bellLen, flangeR })     // bell + crisp flange
//   MechParts.jointHub({ shaftR, hubR, flangeR, hubLen })       // joint hub casting
//   MechParts.armLinkCasting({ length, boxW, boxH, cylR })      // box→cylinder loft shell + ribs
//   MechParts.makeCable(A, B, { radius, sag, corrugated })      // sagging cable / conduit
//   MechParts.makeEChain(pointsOrCurve, { linkLen })            // segmented cable carrier
//   MechParts.makeTreadTrack({ runLen, capR, width, plateN })   // tank tread (instanced plates)
//   MechParts.scrollTread(tread, dU)                            // advance the belt (per-frame OK)
//   MechParts.makeWheel({ r, width, lugCount })                 // lathe tire + merged lugs, axle = local X
//   MechParts.makeMecanumWheel({ hubR, rollerCount })           // 45° roller wheel
//   MechParts.ventGrille({ w, h, finN })                        // louvered vent (one merged mesh)
//   MechParts.hexBolts(r, y, n, { seed, boltR })                // hex heads w/ facet jitter → geometry[]
//   MechParts.pistonRod({ r, clevisW }) / pistonSleeve({ r })   // unit-length, linkBetween-ready
//   MechParts.hoseCoil({ turns, coilR, len, tubeR })            // helix hose (build once; scale.y to breathe)
//   MechParts.beacon({ r, color }) / stackLight({ s })          // strobe + red/amber/green tower
//   MechParts.applyHazardStripes(mat, { freq, angle })          // TSL yellow/black chevrons
//   MechParts.applyBrushedMetal(mat, { baseRough })             // TSL 1-D grain roughness
//   MechParts.catenaryPoints(A, B, { sag, n })                  // sagging polyline for custom cables
//   MechParts.mulberry(seed)                                    // deterministic PRNG
//
// Conventions: every generator takes `material` (defaults to a plain PBR
// metal); castShadow/receiveShadow set on; crisp mechanical facets use
// analytic normals (never computeVertexNormals on them, never mergeVertices
// across parts — it smooths intentional creases).
(function () {
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[mech_parts] THREE global not present — skipping load'); return; }
    const V2 = (x, y) => new THREE.Vector2(x, y);
    const V3 = (x, y, z) => new THREE.Vector3(x, y, z);

    const metal = (color = 0x9aa0a8, rough = 0.4, met = 0.8) =>
        new THREE.MeshStandardNodeMaterial({ color, roughness: rough, metalness: met });
    const rubber = (color = 0x181818) =>
        new THREE.MeshStandardNodeMaterial({ color, roughness: 0.92, metalness: 0.05 });

    const mulberry = (seed) => {
        let a = (seed >>> 0) || 1;
        return () => {
            a |= 0; a = a + 0x6D2B79F5 | 0;
            let t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
    };

    // ════════════════════════════════════════════════════════════════════
    // chamferedBox — 6 inset faces + 12 edge bevels + 8 corner tris, all
    // with ANALYTIC normals (bisector on edges, octant on corners) so the
    // facets stay crisp. Planar per-face UVs from the dominant axis.
    // ════════════════════════════════════════════════════════════════════
    function chamferedBoxGeometry(w, h, d, chamfer) {
        const X = w / 2, Y = h / 2, Z = d / 2;
        const c = Math.min(chamfer, X, Y, Z) * 0.999;
        const X2 = X - c, Y2 = Y - c, Z2 = Z - c;
        const pos = [], nor = [], uv = [], idx = [];
        const inv = 1 / Math.max(w, h, d);
        const uvOf = (p, n) => {
            const ax = Math.abs(n[0]), ay = Math.abs(n[1]), az = Math.abs(n[2]);
            if (ax >= ay && ax >= az) return [p[2] * inv + 0.5, p[1] * inv + 0.5];
            if (ay >= az) return [p[0] * inv + 0.5, p[2] * inv + 0.5];
            return [p[0] * inv + 0.5, p[1] * inv + 0.5];
        };
        const emit = (pts, n) => {
            // winding self-check: flip if the face normal disagrees
            const e1 = [pts[1][0] - pts[0][0], pts[1][1] - pts[0][1], pts[1][2] - pts[0][2]];
            const e2 = [pts[2][0] - pts[1][0], pts[2][1] - pts[1][1], pts[2][2] - pts[1][2]];
            const cx = e1[1] * e2[2] - e1[2] * e2[1], cy = e1[2] * e2[0] - e1[0] * e2[2], cz = e1[0] * e2[1] - e1[1] * e2[0];
            if (cx * n[0] + cy * n[1] + cz * n[2] < 0) pts = pts.slice().reverse();
            const v0 = pos.length / 3;
            for (const p of pts) {
                pos.push(p[0], p[1], p[2]); nor.push(n[0], n[1], n[2]);
                const u = uvOf(p, n); uv.push(u[0], u[1]);
            }
            for (let i = 1; i < pts.length - 1; i++) idx.push(v0, v0 + i, v0 + i + 1);
        };
        for (const sx of [1, -1]) emit([[sx * X, -Y2, -Z2], [sx * X, Y2, -Z2], [sx * X, Y2, Z2], [sx * X, -Y2, Z2]], [sx, 0, 0]);
        for (const sy of [1, -1]) emit([[-X2, sy * Y, -Z2], [X2, sy * Y, -Z2], [X2, sy * Y, Z2], [-X2, sy * Y, Z2]], [0, sy, 0]);
        for (const sz of [1, -1]) emit([[-X2, -Y2, sz * Z], [X2, -Y2, sz * Z], [X2, Y2, sz * Z], [-X2, Y2, sz * Z]], [0, 0, sz]);
        const s2 = 1 / Math.SQRT2, s3 = 1 / Math.sqrt(3);
        for (const sx of [1, -1]) for (const sy of [1, -1])
            emit([[sx * X, sy * Y2, -Z2], [sx * X2, sy * Y, -Z2], [sx * X2, sy * Y, Z2], [sx * X, sy * Y2, Z2]], [sx * s2, sy * s2, 0]);
        for (const sy of [1, -1]) for (const sz of [1, -1])
            emit([[-X2, sy * Y, sz * Z2], [-X2, sy * Y2, sz * Z], [X2, sy * Y2, sz * Z], [X2, sy * Y, sz * Z2]], [0, sy * s2, sz * s2]);
        for (const sx of [1, -1]) for (const sz of [1, -1])
            emit([[sx * X2, -Y2, sz * Z], [sx * X, -Y2, sz * Z2], [sx * X, Y2, sz * Z2], [sx * X2, Y2, sz * Z]], [sx * s2, 0, sz * s2]);
        for (const sx of [1, -1]) for (const sy of [1, -1]) for (const sz of [1, -1])
            emit([[sx * X, sy * Y2, sz * Z2], [sx * X2, sy * Y, sz * Z2], [sx * X2, sy * Y2, sz * Z]], [sx * s3, sy * s3, sz * s3]);
        const geo = new THREE.BufferGeometry();
        geo.setIndex(idx);
        geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        geo.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
        geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
        return geo;
    }
    function chamferedBox(w, h, d, chamfer, material) {
        const mesh = new THREE.Mesh(chamferedBoxGeometry(w, h, d, chamfer), material || metal());
        mesh.castShadow = mesh.receiveShadow = true;
        return mesh;
    }

    // ════════════════════════════════════════════════════════════════════
    // Lathe housings — crisp profile corners = DUPLICATED profile points.
    // ════════════════════════════════════════════════════════════════════
    const toV2 = (pts) => pts.map(([x, y]) => V2(Math.max(x, 0), y));

    function motorHousingProfile({ r = 0.14, len = 0.5, finN = 10, finR, shaftR = 0.05, capR = 0.03 } = {}) {
        finR = finR ?? r * 0.14;                            // fins proportional to the housing
        const pts = [[0, len / 2 + capR], [capR * 0.8, len / 2 + capR * 0.3], [r * 0.9, len / 2],
            [r * 0.9, len / 2], [r, len / 2]];
        const finPitch = (len * 0.62) / finN;
        let y = len / 2 - len * 0.04;
        for (let i = 0; i < finN; i++) {
            pts.push([r, y], [r, y]);
            pts.push([r + finR, y - finPitch * 0.15]);
            pts.push([r + finR, y - finPitch * 0.5]);
            pts.push([r, y - finPitch * 0.85], [r, y - finPitch * 0.85]);
            y -= finPitch;
        }
        pts.push([r, -len / 2], [r, -len / 2], [shaftR * 2.2, -len / 2], [shaftR * 2.2, -len / 2]);
        pts.push([shaftR, -len / 2 - 0.02], [0, -len / 2 - 0.02]);
        return toV2(pts);
    }
    function gearboxBellProfile({ inR = 0.05, bellR = 0.16, bellLen = 0.22, flangeR = 0.2, flangeT = 0.02 } = {}) {
        return toV2([
            [0, bellLen * 0.5 + 0.01], [inR * 1.4, bellLen * 0.5], [inR * 1.4, bellLen * 0.5], [inR * 2.2, bellLen * 0.42],
            [bellR * 0.55, bellLen * 0.15], [bellR * 0.85, -bellLen * 0.1], [bellR, -bellLen * 0.35],
            [bellR, -bellLen * 0.35], [flangeR, -bellLen * 0.35],
            [flangeR, -bellLen * 0.35 - flangeT], [flangeR, -bellLen * 0.35 - flangeT], [bellR * 0.4, -bellLen * 0.35 - flangeT],
            [0, -bellLen * 0.35 - flangeT - 0.01],
        ]);
    }
    function jointHubProfile({ shaftR = 0.045, hubR = 0.1, flangeR = 0.14, flangeT = 0.018, hubLen = 0.12 } = {}) {
        return toV2([
            [0, hubLen / 2], [shaftR, hubLen / 2 - 0.01], [hubR * 0.7, hubLen / 2 - 0.03], [hubR, hubLen * 0.1],
            [hubR, hubLen * 0.1], [flangeR, hubLen * 0.1],
            [flangeR, hubLen * 0.1 - flangeT], [flangeR, hubLen * 0.1 - flangeT], [hubR * 0.85, hubLen * 0.1 - flangeT],
            [hubR * 0.6, -hubLen / 2 + 0.02], [shaftR, -hubLen / 2], [0, -hubLen / 2],
        ]);
    }
    function lathe(points, { segments = 24, material } = {}) {
        const mesh = new THREE.Mesh(new THREE.LatheGeometry(points, segments), material || metal());
        mesh.castShadow = mesh.receiveShadow = true;
        return mesh;
    }
    const motorHousing = (o = {}) => lathe(motorHousingProfile(o), o);
    const gearboxBell = (o = {}) => lathe(gearboxBellProfile(o), o);
    const jointHub = (o = {}) => lathe(jointHubProfile(o), o);

    // ════════════════════════════════════════════════════════════════════
    // Arm link casting — Loft box→cylinder morph (single-shell casting
    // look, no glue seam) + longitudinal ribs merged in. Extends along +Z.
    // ════════════════════════════════════════════════════════════════════
    function armLinkCasting({ length = 0.6, boxW = 0.14, boxH = 0.16, cylR = 0.075, endW, endH, ribs = 4, ribW = 0.012, ribDepth = 0.012, material } = {}) {
        const Loft = globalThis.Loft;
        const geos = [];
        if (Loft) {
            const shell = Loft.sweep({
                path: [V3(0, 0, 0), V3(0, 0, length * 0.5), V3(0, 0, length)],
                sections: 16,
                profile: Loft.rect(boxW, boxH, 16),
                // rect→rect = clean tapered beam; rect→circle = classic casting
                profileEnd: (endW && endH) ? Loft.rect(endW, endH, 16) : Loft.circle(cylR, 16),
                closed: true, capStart: true, capEnd: true,
            });
            geos.push(shell.geometry);
        } else {
            const g = new THREE.CapsuleGeometry(Math.max(boxW, boxH) * 0.5, length * 0.8, 6, 12);
            g.rotateX(Math.PI / 2); g.translate(0, 0, length / 2);
            geos.push(g);
        }
        // ribs on the four faces near the fat (box) end, fading toward the round end
        const stations = [[boxW / 2, 0, 0], [-boxW / 2, 0, Math.PI], [0, boxH / 2, Math.PI / 2], [0, -boxH / 2, -Math.PI / 2]];
        for (let i = 0; i < Math.min(ribs, 4); i++) {
            const [sx, sy] = stations[i];
            const rib = new THREE.BoxGeometry(ribDepth * 2, ribW, length * 0.6);
            const rOut = Math.hypot(sx, sy);
            rib.translate(rOut, 0, length * 0.34);
            rib.rotateZ(Math.atan2(sy, sx));
            geos.push(rib);
        }
        const merged = THREE.mergeGeometries ? THREE.mergeGeometries(geos, false) : geos[0];
        const mesh = new THREE.Mesh(merged, material || metal());
        mesh.castShadow = mesh.receiveShadow = true;
        return mesh;
    }

    // ════════════════════════════════════════════════════════════════════
    // Cables — parabolic sag (≈catenary below sag/span 0.3), optional
    // corrugated conduit via Loft radius wave. Points are LOCAL to the
    // mesh's intended parent.
    // ════════════════════════════════════════════════════════════════════
    function catenaryPoints(A, B, { sag = 0.05, n = 12, lateralJitter = 0, seed = 1 } = {}) {
        const rng = mulberry(seed);
        const down = V3(0, -1, 0);
        const side = V3().subVectors(B, A).cross(down).normalize();
        const pts = [];
        for (let i = 0; i <= n; i++) {
            const t = i / n;
            const p = A.clone().lerp(B, t).addScaledVector(down, sag * 4 * t * (1 - t));
            if (lateralJitter) p.addScaledVector(side, (rng() - 0.5) * lateralJitter * Math.sin(t * Math.PI));
            pts.push(p);
        }
        return pts;
    }
    function makeCable(A, B, { radius = 0.01, sag = 0.05, corrugated = false, material, seed = 1 } = {}) {
        const pts = catenaryPoints(A, B, { sag, n: 12, seed });
        const curve = new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.4);
        let mesh;
        if (corrugated && globalThis.Loft) {
            const ridges = Math.max(3, Math.round(curve.getLength() * 18));
            mesh = globalThis.Loft.sweep({
                path: curve, sections: Math.min(ridges * 4, 240),
                profile: globalThis.Loft.circle(radius, 8),
                scale: (t) => 1 + 0.22 * Math.sin(t * Math.PI * 2 * ridges),
                closed: true, capStart: true, capEnd: true,
                material: material || rubber(0x1a1a1a),
            });
        } else {
            mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, 32, radius, 8, false), material || rubber());
        }
        mesh.castShadow = true;
        return mesh;
    }
    function makeEChain(pointsOrCurve, { linkLen = 0.03, count, material } = {}) {
        const curve = pointsOrCurve.isCurve ? pointsOrCurve
            : new THREE.CatmullRomCurve3(pointsOrCurve, false, 'catmullrom', 0.3);
        count = count ?? Math.max(4, Math.round(curve.getLength() / linkLen));
        const mesh = new THREE.InstancedMesh(
            new THREE.BoxGeometry(linkLen * 0.9, linkLen * 0.62, linkLen * 0.9),
            material || metal(0x30343a, 0.5, 0.6), count);
        mesh.castShadow = true;
        mesh.userData.curve = curve;
        updateEChain(mesh);
        return mesh;
    }
    function updateEChain(mesh, curve) {                    // re-call ONLY when the path moves
        curve = curve || mesh.userData.curve;
        mesh.userData.curve = curve;
        const count = mesh.count;
        const m = new THREE.Matrix4(), q = new THREE.Quaternion(), up = V3(0, 1, 0), one = V3(1, 1, 1);
        for (let i = 0; i < count; i++) {
            const u = i / (count - 1);
            q.setFromUnitVectors(up, curve.getTangentAt(u));
            m.compose(curve.getPointAt(u), q, one);
            mesh.setMatrixAt(i, m);
        }
        mesh.instanceMatrix.needsUpdate = true;
    }

    // ════════════════════════════════════════════════════════════════════
    // Tank treads — instanced plates on a rounded-rect loop, scrolled by
    // recomposing instance matrices (~80 × Matrix4/frame — sub-ms, the one
    // sanctioned per-frame CPU write in this module). Local XY plane; the
    // belt runs along X, wheel axles along Z. Parent + rotate to taste.
    // ════════════════════════════════════════════════════════════════════
    function treadPathPoint(s, runLen, capR) {
        const peri = 2 * runLen + 2 * Math.PI * capR;
        let d = ((s % 1) + 1) % 1 * peri;
        if (d < runLen) return { x: runLen / 2 - d, y: capR, a: Math.PI };                     // top run, leftward
        d -= runLen;
        if (d < Math.PI * capR) { const t = d / capR;                                           // left cap
            return { x: -runLen / 2 - Math.sin(t) * capR, y: capR * Math.cos(t), a: Math.PI + t }; }
        d -= Math.PI * capR;
        if (d < runLen) return { x: -runLen / 2 + d, y: -capR, a: 0 };                           // bottom run, rightward
        d -= runLen; const t = d / capR;                                                          // right cap
        return { x: runLen / 2 + Math.sin(t) * capR, y: -capR * Math.cos(t), a: t };
    }
    function makeTreadTrack({ runLen = 0.9, capR = 0.22, width = 0.18, plateN = 64, lug = 0.012, material } = {}) {
        const peri = 2 * runLen + 2 * Math.PI * capR;
        const plateL = peri / plateN;
        // plate + a chevron lug merged (spins with the plate for free)
        const plate = new THREE.BoxGeometry(plateL * 0.92, 0.028, width);
        const lugG = new THREE.BoxGeometry(plateL * 0.34, 0.028 + lug * 2, width * 0.82);
        const merged = THREE.mergeGeometries ? THREE.mergeGeometries([plate, lugG], false) : plate;
        const mesh = new THREE.InstancedMesh(merged, material || rubber(0x1c1c1e), plateN);
        mesh.castShadow = mesh.receiveShadow = true;
        mesh.userData.tread = { runLen, capR, plateN, u: 0, peri };
        scrollTread(mesh, 0);
        return mesh;
    }
    function scrollTread(mesh, dU) {
        const T = mesh.userData.tread;
        T.u = (T.u + dU) % 1;
        const m = new THREE.Matrix4(), q = new THREE.Quaternion(), z = V3(0, 0, 1), one = V3(1, 1, 1), p = V3();
        for (let i = 0; i < T.plateN; i++) {
            const st = treadPathPoint(i / T.plateN + T.u, T.runLen, T.capR);
            q.setFromAxisAngle(z, st.a);
            m.compose(p.set(st.x, st.y, 0), q, one);
            mesh.setMatrixAt(i, m);
        }
        mesh.instanceMatrix.needsUpdate = true;
    }

    // ════════════════════════════════════════════════════════════════════
    // Wheels — lathe tire carcass + merged tread lugs. Reorientation is
    // BAKED (rotateZ π/2) so the axle is local X and only rotation.x rolls.
    // ════════════════════════════════════════════════════════════════════
    function tireProfile(r, width, hubR) {
        const hw = width / 2;
        return toV2([
            [0, hw * 0.6], [hubR, hw * 0.6], [hubR, hw * 0.6], [hubR * 1.3, hw * 0.55],
            [r * 0.9, hw * 0.5], [r, hw * 0.15], [r, -hw * 0.15], [r * 0.9, -hw * 0.5],
            [hubR * 1.3, -hw * 0.55], [hubR, -hw * 0.6], [hubR, -hw * 0.6], [0, -hw * 0.6],
        ]);
    }
    function makeWheel({ r = 0.28, width = 0.16, hubR = 0.08, lugCount = 22, lugDepth = 0.014, boltCount = 6, material, hubMaterial } = {}) {
        const carcass = new THREE.LatheGeometry(tireProfile(r, width, hubR), 28);
        const geos = [carcass];
        for (let i = 0; i < lugCount; i++) {
            const a = (i / lugCount) * Math.PI * 2;
            const lugG = new THREE.BoxGeometry(0.03 * (r / 0.28), width * 0.85, lugDepth * 2);
            lugG.translate(0, 0, r);
            lugG.rotateY(a);
            geos.push(lugG);
        }
        const merged = THREE.mergeGeometries ? THREE.mergeGeometries(geos, false) : carcass;
        merged.rotateZ(Math.PI / 2);                      // axle = local X
        const wheel = new THREE.Mesh(merged, material || rubber(0x151515));
        wheel.castShadow = wheel.receiveShadow = true;
        const hubMat = hubMaterial || metal(0xc0c0c8, 0.3, 0.9);
        const hub = new THREE.Mesh(new THREE.CylinderGeometry(hubR * 0.9, hubR * 0.9, width * 0.55, 12), hubMat);
        hub.rotation.z = Math.PI / 2;
        wheel.add(hub);
        for (let i = 0; i < boltCount; i++) {
            const a = (i / boltCount) * Math.PI * 2;
            const bolt = new THREE.Mesh(new THREE.CylinderGeometry(hubR * 0.13, hubR * 0.13, width * 0.6, 6), hubMat);
            bolt.rotation.z = Math.PI / 2;
            bolt.position.set(0, Math.cos(a) * hubR * 0.55, Math.sin(a) * hubR * 0.55);
            wheel.add(bolt);
        }
        return wheel;                                     // roll with wheel.rotation.x
    }
    function makeMecanumWheel({ hubR = 0.09, hubWidth = 0.08, rollerCount = 9, rollerLen = 0.075, rollerR = 0.028, material, hubMaterial } = {}) {
        const group = new THREE.Group();
        const hub = new THREE.Mesh(new THREE.CylinderGeometry(hubR, hubR, hubWidth, 16), hubMaterial || metal(0x3a3a40, 0.4, 0.8));
        hub.rotation.z = Math.PI / 2; hub.castShadow = true; group.add(hub);
        const profile = toV2([[0, -rollerLen / 2], [rollerR * 0.7, -rollerLen * 0.3], [rollerR, 0], [rollerR * 0.7, rollerLen * 0.3], [0, rollerLen / 2]]);
        const rollerGeo = new THREE.LatheGeometry(profile, 10);
        rollerGeo.rotateX(Math.PI / 2);
        for (let i = 0; i < rollerCount; i++) {
            const a = (i / rollerCount) * Math.PI * 2;
            const roller = new THREE.Mesh(rollerGeo, material || rubber(0x202020));
            roller.castShadow = true;
            roller.position.set(0, Math.cos(a) * hubR * 1.05, Math.sin(a) * hubR * 1.05);
            roller.rotation.x = a;
            roller.rotation.z = Math.PI / 4;              // the mecanum skew
            group.add(roller);
        }
        return group;                                     // roll with group.rotation.x
    }

    // ════════════════════════════════════════════════════════════════════
    // Greebles
    // ════════════════════════════════════════════════════════════════════
    function ventGrille({ w = 0.12, h = 0.08, finN = 7, finAngle = 0.5, finDepth = 0.012, material } = {}) {
        const geos = [];
        for (let i = 0; i < finN; i++) {
            const g = new THREE.BoxGeometry(w * 0.92, 0.005, finDepth);
            g.rotateX(finAngle);
            g.translate(0, (i / (finN - 1) - 0.5) * h * 0.85, 0);
            geos.push(g);
        }
        const frame = new THREE.BoxGeometry(w, h, finDepth * 0.4);
        frame.translate(0, 0, -finDepth * 0.35);
        geos.push(frame);
        const merged = THREE.mergeGeometries ? THREE.mergeGeometries(geos, false) : geos[geos.length - 1];
        const mesh = new THREE.Mesh(merged, material || metal(0x1c1c20, 0.55, 0.7));
        mesh.castShadow = true;
        return mesh;
    }
    // hex bolt heads (with facet-phase jitter) as GEOMETRY array — merge into
    // the owner's static accent geometry, or wrap in a Mesh directly.
    function hexBolts(r, y, n, { seed = 7, boltR } = {}) {
        const rng = mulberry(seed);
        const bR = boltR ?? r * 0.075;
        const geos = [];
        for (let i = 0; i < n; i++) {
            const a = (i / n) * Math.PI * 2;
            const head = new THREE.CylinderGeometry(bR, bR, bR * 1.3, 6);
            head.rotateY(rng() * Math.PI * 2);
            head.translate(Math.cos(a) * r * 0.8, y, Math.sin(a) * r * 0.8);
            geos.push(head);
        }
        return geos;
    }

    // ════════════════════════════════════════════════════════════════════
    // Pistons — unit-length local space (clevis ears + pin baked in), so
    // robotics_kit's linkBetween() stretches them with zero extra cost.
    // ════════════════════════════════════════════════════════════════════
    function pistonRod({ r = 0.02, clevisW = 0.05, clevisT = 0.009, material } = {}) {
        const rod = new THREE.CylinderGeometry(r, r, 0.9, 10); rod.translate(0, -0.05, 0);
        const earA = new THREE.BoxGeometry(clevisT, 0.1, clevisW); earA.translate(0, 0.45, clevisW * 0.5);
        const earB = new THREE.BoxGeometry(clevisT, 0.1, clevisW); earB.translate(0, 0.45, -clevisW * 0.5);
        const pin = new THREE.CylinderGeometry(r * 0.4, r * 0.4, clevisW * 1.5, 8);
        pin.rotateX(Math.PI / 2); pin.translate(0, 0.45, 0);
        const geos = [rod, earA, earB, pin];
        const merged = THREE.mergeGeometries ? THREE.mergeGeometries(geos, false) : rod;
        const mesh = new THREE.Mesh(merged, material || metal(0xd8dce2, 0.2, 0.95));
        mesh.castShadow = true;
        return mesh;
    }
    function pistonSleeve({ r = 0.042, wiper = true, material } = {}) {
        const body = new THREE.CylinderGeometry(r, r, 0.9, 12); body.translate(0, -0.05, 0);
        const collar = new THREE.CylinderGeometry(r * 1.25, r * 1.25, 0.06, 12); collar.translate(0, 0.42, 0);
        const base = new THREE.CylinderGeometry(r * 1.2, r * 1.35, 0.08, 12); base.translate(0, -0.46, 0);
        const geos = [body, collar, base];
        const merged = THREE.mergeGeometries ? THREE.mergeGeometries(geos, false) : body;
        const mesh = new THREE.Mesh(merged, material || metal());
        mesh.castShadow = true;
        return mesh;
    }
    function hoseCoil({ turns = 6, coilR = 0.03, len = 0.3, tubeR = 0.006, material } = {}) {
        const n = turns * 12, pts = [];
        for (let i = 0; i <= n; i++) {
            const t = i / n;
            pts.push(V3(Math.cos(t * turns * Math.PI * 2) * coilR, len * (t - 0.5), Math.sin(t * turns * Math.PI * 2) * coilR));
        }
        const mesh = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), n, tubeR, 6, false),
            material || rubber(0x101014));
        mesh.castShadow = true;
        return mesh;                                       // breathe with mesh.scale.y, never rebuild
    }

    // ════════════════════════════════════════════════════════════════════
    // Lights — beacon strobe + industrial stack light (red/amber/green).
    // Both return { mesh/group, update(t) } and self-register nothing; the
    // OWNER's update should call them (robotics_kit wires this).
    // ════════════════════════════════════════════════════════════════════
    function beacon({ r = 0.05, color = 0xff7a10, rate = 5 } = {}) {
        const mat = new THREE.MeshStandardNodeMaterial({ color: 0x1a0d02, emissive: new THREE.Color(color), emissiveIntensity: 2 });
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(r, 10, 8), mat);
        return { mesh, update: (t) => { mat.emissiveIntensity = 1 + Math.abs(Math.sin(t * rate)) * 2.2; } };
    }
    function stackLight({ s = 1 } = {}) {
        const group = new THREE.Group();
        const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.008 * s, 0.008 * s, 0.09 * s, 8), metal(0x22262c, 0.5, 0.7));
        pole.position.y = 0.045 * s; group.add(pole);
        const segs = [];
        const colors = { red: 0xd82020, amber: 0xe8a020, green: 0x28c840 };
        let y = 0.09 * s;
        for (const name of ['red', 'amber', 'green']) {
            const mat = new THREE.MeshStandardNodeMaterial({
                color: 0x181818, emissive: new THREE.Color(colors[name]), emissiveIntensity: 0.12,
                roughness: 0.35, metalness: 0.1,
            });
            const seg = new THREE.Mesh(new THREE.CylinderGeometry(0.03 * s, 0.03 * s, 0.038 * s, 12), mat);
            seg.position.y = y + 0.019 * s; y += 0.04 * s;
            group.add(seg);
            segs.push({ name, mat });
        }
        const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.032 * s, 0.03 * s, 0.012 * s, 12), metal(0x22262c, 0.5, 0.7));
        cap.position.y = y + 0.006 * s; group.add(cap);
        const state = { mode: 'run' };                     // 'run' | 'warn' | 'fault' | 'off'
        const update = (t) => {
            const blink1 = Math.sin(t * Math.PI * 2 * 1.5) > 0 ? 1 : 0;   // 1.5 Hz warn
            const blink5 = Math.sin(t * Math.PI * 2 * 5) > 0 ? 1 : 0;     // 5 Hz fault
            for (const { name, mat } of segs) {
                let on = 0.12;
                if (state.mode === 'run' && name === 'green') on = 2.2;
                if (state.mode === 'warn' && name === 'amber') on = 0.4 + blink1 * 2.2;
                if (state.mode === 'fault' && name === 'red') on = 0.4 + blink5 * 2.6;
                mat.emissiveIntensity = on;
            }
        };
        return { group, state, update };
    }

    // ════════════════════════════════════════════════════════════════════
    // TSL surface treatments (NodeMaterial, no textures)
    // ════════════════════════════════════════════════════════════════════
    function applyHazardStripes(mat, { freq = 24, angle = Math.PI / 4, colorA = 0xf5c400, colorB = 0x151515, useWorldPos = false } = {}) {
        const { uv, positionGeometry, mod, mix, vec3, smoothstep } = THREE;
        const ca = new THREE.Color(colorA), cb = new THREE.Color(colorB);
        const cA = Math.cos(angle), sA = Math.sin(angle);
        const p = useWorldPos ? positionGeometry : uv();
        const d = useWorldPos
            ? p.x.mul(cA).add(p.z.mul(sA)).mul(freq)
            : p.x.mul(cA).add(p.y.mul(sA)).mul(freq);
        const stripe = mod(d, 1.0).sub(0.5).abs().mul(2.0);
        mat.colorNode = mix(vec3(ca.r, ca.g, ca.b), vec3(cb.r, cb.g, cb.b), smoothstep(0.46, 0.54, stripe));
        return mat;
    }
    function applyBrushedMetal(mat, { baseRough = 0.32, grainFreq = 240, grainAmp = 0.05 } = {}) {
        const { uv, sin } = THREE;
        mat.roughnessNode = sin(uv().x.mul(grainFreq)).mul(sin(uv().x.mul(grainFreq * 2.3).add(1.7))).mul(grainAmp).add(baseRough);
        return mat;
    }

    globalThis.MechParts = {
        chamferedBox, chamferedBoxGeometry,
        motorHousing, gearboxBell, jointHub, lathe,
        motorHousingProfile, gearboxBellProfile, jointHubProfile, tireProfile,
        armLinkCasting,
        catenaryPoints, makeCable, makeEChain, updateEChain,
        makeTreadTrack, scrollTread, treadPathPoint,
        makeWheel, makeMecanumWheel,
        ventGrille, hexBolts,
        pistonRod, pistonSleeve, hoseCoil,
        beacon, stackLight,
        applyHazardStripes, applyBrushedMetal,
        mulberry, metal, rubber,
    };
    console.log('[mech_parts] MechParts ready — chamferedBox, lathe housings (motor/gearbox/hub), armLinkCasting, cables/e-chains, treads, wheels (+mecanum), vents/bolts, pistons, beacon/stackLight, hazard/brushed TSL');
})();
