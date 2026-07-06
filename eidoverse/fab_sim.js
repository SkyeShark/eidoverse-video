// fab_sim.js — globalThis.FabSim: ADDITIVE + SUBTRACTIVE MANUFACTURING
// sims for the robotics_kit machines. One module, two processes, one idea:
// the workpiece exists in TWO STATES OF MATTER — transitional material is a
// GPU-raymarched metaball field (makeIsoField), settled material is the
// EXACT source mesh, and a molten glow line rides the boundary.
//
// FabSim.print(machine, anyMeshOrGeometry, opts)  — additive. Deposits land
//   as molten goo riding the deposition front and solidify into the true
//   mesh beneath it. Machines: the i3-style 'printer' preset (moving bed)
//   or the 'delta' (Kossel-style — gets a stand, heated build plate and a
//   flying hotend; `stand: false` when it hangs from a rig).
//   `{ duration, size, layerH, spacing, color, resolution (72), ballCells
//   (goo radius, 3.0), ballFlat (bead squash, 2.2), meltLayers (1.5) }`.
//
// FabSim.carve(gantry, anyMeshOrGeometry, opts)   — subtractive. A solid
//   metaball stock block is milled top-down; finished rows hand over to the
//   true mesh above the cutting front. `{ duration, size, resolution (44),
//   sink, color, margin, gpu:false debug fallback }`.
//
// PrintSim.print / CNCSim.carve remain as aliases. Both jobs are ordinary
// scene objects: parent the machine anywhere, several at once, no camera
// coupling. Self-animating via the engine's robot drain.
(function () {
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[fab_sim] THREE global not present — skipping load'); return; }

    async function print(printer, source, o = {}) {
        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('print_sim');
        const duration = o.duration ?? 18;
        const size = o.size ?? 0.45;
        const layerH = o.layerH ?? 0.03;
        const spacing = o.spacing ?? 0.02;
        const color = new THREE.Color(o.color ?? 0x2fa84f);

        // ── normalize the source to one geometry ──
        let geo = null;
        if (source && source.isBufferGeometry) geo = source;
        else if (source && source.isMesh) geo = source.geometry;
        else if (source && source.isObject3D) {
            const geos = [];
            source.updateMatrixWorld(true);
            source.traverse((m) => {
                if (m.isMesh && m.geometry) {
                    const g = m.geometry.clone().applyMatrix4(m.matrixWorld);
                    for (const k of Object.keys(g.attributes)) if (k !== 'position') g.deleteAttribute(k);
                    g.morphAttributes = {};                // blend shapes break mergeGeometries
                    g.morphTargetsRelative = false;
                    g.computeVertexNormals();
                    geos.push(g.toNonIndexed ? g.toNonIndexed() : g);
                }
            });
            geo = THREE.mergeGeometries ? THREE.mergeGeometries(geos, false) : geos[0];
        }
        if (!geo) throw new Error('PrintSim.print: source must be a Mesh, BufferGeometry, or Object3D tree');

        // fit into the build volume: scale to `size`, center XZ, ground at bed
        geo.computeBoundingBox();
        const bb = geo.boundingBox, dim = bb.getSize(new THREE.Vector3());
        const s = size / Math.max(dim.x, dim.y, dim.z);
        const cx = (bb.min.x + bb.max.x) / 2, cz = (bb.min.z + bb.max.z) / 2;

        // ── which machine is this? the i3-style printer preset (moving
        // bed) or the DELTA (Kossel-style: static build plate on the floor,
        // flying effector carries the hotend, closed-form IK via moveTo) ──
        const isKossel = !!(printer.carriages && printer.plateFrame);
        const isDelta = !isKossel && !!(printer.horns && printer.plateFrame);
        let mount = printer.bedG || null;
        let BED_TOP = isDelta ? 0.049 : 0.016 * (printer.s || 1) + 0.016;
        let plateY = 0;
        if (isKossel) {
            // the kossel IS a complete printer — integrated plate, hotend,
            // spool; nothing to build, just print on it
            mount = printer.group;
            BED_TOP = printer.plateTop + 0.004;
        } else if (isDelta) {
            printer._program = null;                       // the print owns the effector
            plateY = -(printer.re * 0.97);                 // build surface in base-local space
            mount = new THREE.Group();
            mount.position.y = plateY;
            printer.group.add(mount);
            const MP = globalThis.MechParts;
            // stand/plate/hotend wear the ROBOT's configured materials, so
            // makeRobot('delta', { color, accent }) flows into the conversion
            const dk = (printer.materials && printer.materials.dark) || new THREE.MeshStandardNodeMaterial({ color: 0x23262b, roughness: 0.55, metalness: 0.6 });
            const silv = (printer.materials && printer.materials.body) || new THREE.MeshStandardNodeMaterial({ color: 0x9aa2ac, roughness: 0.35, metalness: 0.85 });
            const brass = new THREE.MeshStandardNodeMaterial({ color: 0xc9a44a, roughness: 0.35, metalness: 0.9 });
            const cb = (w, h, d, c, m) => (MP ? MP.chamferedBox(w, h, d, c, m) : new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m));
            // an ACTUAL BUILD PLATE under the effector: dark heated disc,
            // brushed rim, leveling knobs
            const pw = o.plateSize ?? Math.max(size * 1.9, printer.f * 2.2);
            const plate = new THREE.Mesh(new THREE.CylinderGeometry(pw / 2, pw / 2, 0.045, 28), dk);
            plate.position.y = 0.0225; plate.castShadow = true; mount.add(plate);
            const rim = new THREE.Mesh(new THREE.CylinderGeometry(pw / 2 + 0.03, pw / 2 + 0.035, 0.02, 28), silv);
            rim.position.y = 0.01; rim.castShadow = true; mount.add(rim);
            for (let i = 0; i < 3; i++) {
                const phi = (i / 3) * Math.PI * 2 + Math.PI / 3;
                const knob = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.02, 0.018, 10), brass);
                knob.position.set(Math.cos(phi) * (pw / 2 - 0.05), 0.054, Math.sin(phi) * (pw / 2 - 0.05));
                mount.add(knob);
            }
            // Kossel-style STAND: three columns from the base plate down to
            // the floor ring (stand:false when the delta hangs from a rig)
            if (o.stand !== false) {
                const SH = -plateY;
                // columns sit BETWEEN the towers (60 deg offset) and OUTSIDE
                // the horn+forearm elbow sweep (f + rf + margin) — on the
                // tower azimuths at small radius they clip the elbows
                const standR = printer.f + printer.rf + 0.14;
                for (let i = 0; i < 3; i++) {
                    const phi = (i / 3) * Math.PI * 2 + Math.PI / 3;
                    const cxp = Math.cos(phi) * standR, czp = Math.sin(phi) * standR;
                    const col = cb(0.09, SH + 0.12, 0.11, 0.014, silv);
                    col.position.set(cxp, -SH / 2 + 0.03, czp); col.castShadow = true;
                    printer.group.add(col);
                    const foot = cb(0.16, 0.03, 0.18, 0.008, dk);
                    foot.position.set(cxp, plateY + 0.015, czp);
                    printer.group.add(foot);
                    // radial top beam ties the column into the base disc
                    const span = standR - printer.f * 1.3;
                    const beam = cb(span + 0.1, 0.07, 0.08, 0.012, silv);
                    beam.position.set(Math.cos(phi) * (standR - span / 2), 0.05, Math.sin(phi) * (standR - span / 2));
                    beam.rotation.y = -phi; beam.castShadow = true;
                    printer.group.add(beam);
                }
            }
            // hotend on the flying effector: heatsink fins, heater block,
            // brass tip (replaces the pick cone)
            const ext = new THREE.Group();
            for (let i = 0; i < 4; i++) {
                const fin = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.006, 0.06), silv);
                fin.position.y = -0.02 - i * 0.013; ext.add(fin);
            }
            const heat = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.04, 0.055), dk);
            heat.position.y = -0.095; ext.add(heat);
            const tip = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.013, 0.03, 8), brass);
            tip.position.y = -0.13; ext.add(tip);
            printer.plateFrame.add(ext);
            if (printer.tool) printer.tool.visible = false;
            const reach = -plateY - printer.re * 0.45;
            if (BED_TOP + size + 0.16 > reach) console.warn(`[print_sim] delta print may exceed effector reach (print top ${(BED_TOP + size).toFixed(2)} vs reach ${reach.toFixed(2)}) — reduce size`);
        }

        // ── surface-sample into locked particles ──
        const { MeshSurfaceSampler } = await import('npm:three@0.184.0/examples/jsm/math/MeshSurfaceSampler.js');
        const sampler = new MeshSurfaceSampler(new THREE.Mesh(geo)).build();
        // area estimate → sample count for the requested spacing
        // (de-index first: the triplet walk mis-reads indexed geometry)
        const flat = geo.index ? geo.toNonIndexed() : geo;
        const pos = flat.attributes.position; let area = 0;
        const eA = new THREE.Vector3(), eB = new THREE.Vector3(), eC = new THREE.Vector3();
        for (let i = 0; i + 2 < pos.count; i += 3) {
            eA.fromBufferAttribute(pos, i); eB.fromBufferAttribute(pos, i + 1); eC.fromBufferAttribute(pos, i + 2);
            eB.sub(eA); eC.sub(eA);
            area += eB.cross(eC).length() / 2;
        }
        let N = Math.round((area * s * s) / (spacing * spacing));
        if (!isFinite(N)) N = 1500;
        N = Math.max(200, Math.min(6000, N));
        const deposits = [];
        const sp = new THREE.Vector3();
        for (let i = 0; i < N; i++) {
            sampler.sample(sp);
            deposits.push(new THREE.Vector3((sp.x - cx) * s, (sp.y - bb.min.y) * s + BED_TOP, (sp.z - cz) * s));
        }
        // bottom-up layers, in-layer angular sweep (a plausible toolpath)
        deposits.sort((a, b) => {
            const La = Math.floor(a.y / layerH), Lb = Math.floor(b.y / layerH);
            return (La - Lb) || (Math.atan2(a.z, a.x) - Math.atan2(b.z, b.x));
        });

        // ── the print, in two coexisting states of matter ──
        // SETTLED plastic: the EXACT source mesh revealed below a rising
        // solidification line — crisp true geometry (coil contacts, edges).
        // MOLTEN plastic: a thin metaball band of fresh deposits riding the
        // deposition front (GPU-raymarched via makeIsoField); as the front
        // rises past a deposit it UNSTAMPS from the field while the real
        // mesh appears beneath it. The finished print IS the source mesh.
        const { uniform, positionWorld, smoothstep, step, vec3, fract } = THREE;
        const cut = uniform(0.0);                          // deposition front (world y)
        const cutSolid = cut.sub(layerH * 1.2);            // solidification line
        const gv = smoothstep(0.38, 0.5, fract(positionWorld.y.div(layerH)).sub(0.5).abs().mul(2.0));
        const solidMat = new THREE.MeshStandardNodeMaterial({ metalness: 0.05, side: THREE.DoubleSide });
        solidMat.colorNode = vec3(color.r, color.g, color.b).mul(gv.mul(-0.24).add(1.0));
        solidMat.roughnessNode = gv.mul(0.32).add(0.42);
        solidMat.emissiveNode = vec3(1.0, 0.45, 0.1).mul(smoothstep(cutSolid.sub(layerH), cutSolid, positionWorld.y)).mul(1.1);
        solidMat.opacityNode = step(positionWorld.y, cutSolid);
        solidMat.alphaTest = 0.5;
        const partGeo = geo.clone();
        if (!partGeo.attributes.normal) partGeo.computeVertexNormals();
        partGeo.applyMatrix4(new THREE.Matrix4().makeTranslation(0, BED_TOP, 0)
            .multiply(new THREE.Matrix4().makeScale(s, s, s))
            .multiply(new THREE.Matrix4().makeTranslation(-cx, -bb.min.y, -cz)));
        const mc = new THREE.Mesh(partGeo, solidMat);      // rides the bed (name kept: job.solid)
        mc.castShadow = true; mc.frustumCulled = false;
        mc.userData.noSupportCheck = true;
        mount.add(mc);

        const res = o.resolution ?? 72;
        const HALF = size * 0.62;
        if (!globalThis.makeIsoField) throw new Error('PrintSim.print: makeIsoField not available (iso_field.js must load first)');
        const isoF = globalThis.makeIsoField({
            resolution: res, half: HALF, iso: 50,
            metalness: 0.0, roughness: 0.3,                // wet molten plastic
            steps: o.steps ?? Math.max(180, Math.round(res * 2.2)),
            colorNode: () => vec3(color.r, color.g, color.b).mul(1.15),
            emissive: () => vec3(1.0, 0.45, 0.12).mul(0.55),
            parent: mount,
        });
        isoF.mesh.position.set(0, BED_TOP + HALF, 0);
        const field = isoF.field;
        const R1g = res - 1;
        const BALL = o.ballCells ?? 3.0;                   // in-plane bead radius (cells)
        const FLAT = o.ballFlat ?? 2.2;                    // vertical squash: beads are FLAT
        // (a squished extrusion bead, not a sphere — round blobs read fat
        // against thin geometry)
        // additive stamps with NO clamp — unstamping (sign -1) must reverse
        // a stamp exactly or drained goo leaves ghost residue
        const stampBall = (p, sign) => {                   // bed-local deposit
            const gx = ((p.x + HALF) / (2 * HALF)) * R1g;
            const gy = ((p.y - BED_TOP) / (2 * HALF)) * R1g;
            const gz = ((p.z + HALF) / (2 * HALF)) * R1g;
            const ry = BALL / FLAT;
            const x0 = Math.max(0, Math.ceil(gx - BALL)), x1 = Math.min(R1g, Math.floor(gx + BALL));
            const y0 = Math.max(0, Math.ceil(gy - ry)), y1 = Math.min(R1g, Math.floor(gy + ry));
            const z0 = Math.max(0, Math.ceil(gz - BALL)), z1 = Math.min(R1g, Math.floor(gz + BALL));
            for (let z = z0; z <= z1; z++) for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
                const dx = x - gx, dy = (y - gy) * FLAT, dz = z - gz;
                const q = 1 - (dx * dx + dy * dy + dz * dz) / (BALL * BALL);
                if (q <= 0) continue;
                const i = x + y * res + z * res * res;
                field[i] = Math.max(0, field[i] + sign * 90 * q * q);
            }
        };
        const molten = [];                                 // FIFO: deposits currently goo

        // fresh dots at the nozzle (they fuse into the field right behind)
        const WINDOW = o.dotsWindow ?? 10;
        const dots = new THREE.InstancedMesh(
            new THREE.SphereGeometry(spacing * 0.55, 8, 6),
            new THREE.MeshStandardNodeMaterial({ color: o.color ?? 0x2fa84f, roughness: 0.45, emissive: new THREE.Color(0xff8a30), emissiveIntensity: 0.5 }),
            64);
        dots.frustumCulled = false;
        const hide = new THREE.Matrix4().makeScale(0, 0, 0);
        for (let i = 0; i < 64; i++) dots.setMatrixAt(i, hide);
        mount.add(dots);
        const dm = new THREE.Matrix4(), dq = new THREE.Quaternion(), d1 = new THREE.Vector3(1, 1, 1);

        // nozzle-tip probe for the i3 printer's generic axis solve (the
        // delta drives moveTo in plain base-local coordinates)
        let tipMarker = null;
        if (!isDelta && !isKossel) {
            tipMarker = new THREE.Object3D();
            tipMarker.position.set(0, printer._nozzleTipY, 0.012 * printer.s);
            printer.head.add(tipMarker);
        }

        const job = {
            printer, deposits, solid: mc, progress: 0, done: false,
            _n: 0, _t0: null, _c: null, _lastGY: null,
        };
        printer._printJobActive = true;                    // the job owns the axes
        if (printer.print) printer.print.visible = false;  // …and replaces the demo print
        const bA = new THREE.Vector3(), bB = new THREE.Vector3(), bUP = new THREE.Vector3(0, 1, 0);
        const bedW = new THREE.Vector3();
        const topY = deposits[deposits.length - 1].y;      // bed-local top of the print

        job._update = (t, dt) => {
            if (job.done && job.progress >= 1) { /* parked */ }
            if (job._t0 === null) {
                job._t0 = t;
                if (!isDelta && !isKossel) {
                    // world-space probe: linear axis constants
                    printer.group.updateMatrixWorld(true);
                    const tip0 = tipMarker.getWorldPosition(new THREE.Vector3());
                    const bed0 = printer.bedG.getWorldPosition(new THREE.Vector3());
                    job._c = { hx: bed0.x - tip0.x + printer.head.position.x,
                        bz: printer.bedG.position.z + (tip0.z - bed0.z),
                        gy: printer.xG.position.y - tip0.y + bed0.y };
                }
            }
            const u = Math.min(1, (t - job._t0) / duration);
            job.progress = u;
            const target = Math.floor(u * deposits.length);
            let fieldDirty = job._n < target;
            while (job._n < target) {
                const p = deposits[job._n];
                dm.compose(p, dq, d1);
                dots.setMatrixAt(job._n % 64, dm);
                if (job._n >= WINDOW) dots.setMatrixAt((job._n - WINDOW) % 64, hide);
                stampBall(p, 1);                           // lands as molten goo
                molten.push(p);
                job._n++;
            }
            dots.instanceMatrix.needsUpdate = true;
            // drive the axes
            const cur = deposits[Math.min(deposits.length - 1, target)];
            const C = job._c;
            if (u < 1) {
                if (isKossel) {
                    printer.moveTo(cur.x, cur.y + printer.nozzleTip + 0.01, cur.z);
                } else if (isDelta) {
                    // effector target in base-local space: the hotend tip
                    // rides just above the current deposit
                    printer.moveTo(cur.x, plateY + cur.y + 0.155, cur.z);
                } else {
                    printer.head.position.x = cur.x + C.hx;
                    printer.bedG.position.z = C.bz - cur.z;
                    const ly = (Math.floor(cur.y / layerH) + 0.5) * layerH;
                    printer.xG.position.y = Math.max(printer.xG.position.y, C.gy + ly);
                }
            } else {
                if (isKossel) {
                    printer.moveTo(0, printer.H * 0.62, 0);   // retract to the crown
                } else if (isDelta) {
                    // RETRACT: park well above the finished print's top
                    printer.moveTo(0, -printer.re * 0.34, 0);
                } else {
                    printer.xG.position.y = Math.min(printer.xG.position.y + 0.007, printer.H + 0.1);
                    if (printer.xG.position.y > printer.H) {
                        printer.head.position.x *= 0.96;
                        printer.bedG.position.z *= 0.96;
                    }
                }
                if (!job.done) {
                    job.done = true;
                    for (let i = 0; i < 64; i++) dots.setMatrixAt(i, hide);
                    dots.instanceMatrix.needsUpdate = true;
                    if (o.onDone) { try { o.onDone(job); } catch (e) {} }
                }
            }
            if (printer.xG) {                              // i3 only — the delta has no Z gantry
                if (job._lastGY !== null && printer.zScrews)
                    for (const sc of printer.zScrews) sc.rotation.y += (printer.xG.position.y - job._lastGY) * 260;
                job._lastGY = printer.xG.position.y;
            }
            if (printer.spool) printer.spool.rotation.x += (u < 1 ? 1.2 : 0.05) * (dt ?? 1 / 30);
            if (printer.bowden && printer._bowdenTop) {   // i3 bowden tracks the head (kossel manages its own)
                bA.copy(printer._bowdenTop);
                bB.set(printer.head.position.x, printer.xG.position.y + 0.02 * printer.s, printer.xG.position.z + 0.02);
                printer.group.localToWorld(bA); printer.group.localToWorld(bB);
                const m = printer.bowden;
                m.position.copy(bA).add(bB).multiplyScalar(0.5);
                const d = bB.sub(bA); const len = Math.max(1e-6, d.length());
                m.quaternion.setFromUnitVectors(bUP, d.multiplyScalar(1 / len));
                m.scale.y = len;
                printer.group.worldToLocal(m.position);
            }
            // melt front (WORLD y): tracks the deposition point while
            // printing, then RAMPS up past the top so the last layers
            // solidify and the glow sweeps off — no teleport pop at done
            mount.getWorldPosition(bedW);
            if (u < 1) cut.value = 0.02 + bedW.y + cur.y - layerH * 0.4;
            else cut.value = Math.min(cut.value + layerH * 8 * (dt ?? 1 / 30), bedW.y + topY + layerH * 8);
            // solidify: goo below the melt line unstamps — the true mesh is
            // already revealed beneath it
            const meltH = layerH * (o.meltLayers ?? 1.5);
            while (molten.length && molten[0].y < (cut.value - bedW.y) - meltH) {
                stampBall(molten.shift(), -1);
                fieldDirty = true;
            }
            // bind LAST — the axes (including the MOVING BED) are set for
            // THIS frame now; binding earlier left the goo one bed-move
            // behind the mesh every frame
            isoF.bind();
            if (fieldDirty || !job._fieldInit) { isoF.upload(); job._fieldInit = true; }
            if (globalThis.__printDebug && job._n - (job._dbgLast || 0) >= 200) {
                job._dbgLast = job._n;
                let mx = 0; for (let k = 0; k < field.length; k += 5) if (field[k] > mx) mx = field[k];
                const sw = new THREE.Vector3(); mc.getWorldPosition(sw);
                const iw = new THREE.Vector3(); isoF.mesh.getWorldPosition(iw);
                console.log(`[pdbg] n=${job._n} cut=${cut.value.toFixed(3)} bedW=${bedW.y.toFixed(3)} molten=${molten.length} fieldMax=${mx.toFixed(0)} partW=${sw.y.toFixed(3)} isoW=${iw.y.toFixed(3)}`);
            }
        };
        (globalThis._autoRobots || (globalThis._autoRobots = [])).push((t, dt) => job._update(t, dt));
        console.log(`[print_sim] job ready — ${N} particles, ${Math.ceil(deposits[deposits.length - 1].y / layerH)} layers over ${duration}s`);
        return job;
    }

    async function carve(gantry, source, o = {}) {
        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('cnc_sim');
        const duration = o.duration ?? 20;
        const size = o.size ?? 0.5;
        const res = o.resolution ?? 44;
        // sink: bury the model's bottom below the block base. A 3-axis
        // top-down mill can't undercut — a plinth pinch (narrow waist over a
        // wider foot) is unmachinable, so sink it out of the visible stock.
        const sink = Math.max(0, o.sink ?? 0);

        // ── normalize source to one geometry, fit to `size` ──
        let geo = null;
        if (source && source.isBufferGeometry) geo = source;
        else if (source && source.isMesh) geo = source.geometry;
        else if (source && source.isObject3D) {
            // zero-thickness shells (hair cards, lash planes) permanently flip
            // ray parity — every voxel behind one classifies "inside" and the
            // carve grows spikes. They're unmachinable anyway: skip any mesh
            // whose position-welded edges are mostly boundary.
            const openRatio = (g) => {
                const pos = g.attributes.position;
                const index = g.index ? g.index.array : null;
                const triCount = Math.floor((index ? index.length : pos.count) / 3);
                if (triCount > 120000) return 0;
                const q = (i) => `${Math.round(pos.getX(i) * 1e5)},${Math.round(pos.getY(i) * 1e5)},${Math.round(pos.getZ(i) * 1e5)}`;
                const vAt = (t, k) => (index ? index[t * 3 + k] : t * 3 + k);
                const edges = new Map();
                for (let t = 0; t < triCount; t++) {
                    const a = q(vAt(t, 0)), b = q(vAt(t, 1)), c = q(vAt(t, 2));
                    for (const e of [[a, b], [b, c], [c, a]]) {
                        const key = e[0] < e[1] ? e[0] + '|' + e[1] : e[1] + '|' + e[0];
                        edges.set(key, (edges.get(key) || 0) + 1);
                    }
                }
                let open = 0;
                for (const v of edges.values()) if (v === 1) open++;
                return open / Math.max(1, edges.size);
            };
            const geos = [];
            source.updateMatrixWorld(true);
            source.traverse((m) => {
                if (m.isMesh && m.geometry) {
                    const g = m.geometry.clone();
                    if (!g.attributes.normal) g.computeVertexNormals();
                    g.applyMatrix4(m.matrixWorld);
                    // keep normals — the finished-surface mesh renders them
                    for (const k of Object.keys(g.attributes)) if (k !== 'position' && k !== 'normal') g.deleteAttribute(k);
                    g.morphAttributes = {};                // blend shapes break mergeGeometries
                    g.morphTargetsRelative = false;
                    const r = openRatio(g);
                    if (r > 0.15) { console.log(`[cnc_sim] skipping open-shell mesh "${m.name}" (${Math.round(r * 100)}% boundary edges — not a millable solid)`); return; }
                    geos.push(g);
                }
            });
            geo = THREE.mergeGeometries ? THREE.mergeGeometries(geos, false) : geos[0];
        }
        if (!geo) throw new Error('CNCSim.carve: source must be a Mesh, BufferGeometry, or Object3D tree');
        geo = geo.index ? geo.toNonIndexed() : geo.clone();
        geo.computeBoundingBox();
        const bb = geo.boundingBox, dim = bb.getSize(new THREE.Vector3());
        const s = size / Math.max(dim.x, dim.y, dim.z);
        const cx = (bb.min.x + bb.max.x) / 2, cz = (bb.min.z + bb.max.z) / 2;
        // target transform: model space -> block-local space (centered, grounded)
        const fit = (p) => p.set((p.x - cx) * s, (p.y - bb.min.y) * s, (p.z - cz) * s);

        // ── the stock block: target bounds + margin ──
        const tgt = new THREE.Vector3(dim.x * s, dim.y * s, dim.z * s);
        const margin = o.margin ?? 0.05;
        const block = { w: tgt.x + margin * 2, h: tgt.y + margin - sink, d: tgt.z + margin * 2 };
        const HALF = Math.max(block.w, block.h, block.d) * 0.58;   // hug the stock — fidelity = voxels IN the block

        // ── voxel classification: inside the target? (BVH parity raycast) ──
        const probe = new THREE.Mesh(geo);
        // DoubleSide is LOAD-BEARING: three's raycaster CULLS BACKFACES on
        // FrontSide materials, so the exit crossing of a ray leaving a shell
        // never registers — parity reads 0 = "outside" for every interior
        // point of a single shell. The bust hero lost half its head to this.
        probe.material.side = THREE.DoubleSide;
        if (geo.computeBoundsTree) geo.computeBoundsTree();
        const ray = new THREE.Raycaster();
        ray.firstHitOnly = false;
        // 3-direction PARITY VOTE: a single ray grazing tangent to a surface
        // running parallel to it flips parity and misclassifies whole streaks
        // (a knot came out as a scrambled ball). Majority of 3 skewed rays
        // is robust to tangencies.
        const dirs = [new THREE.Vector3(1, 0.03, 0.07).normalize(),
            new THREE.Vector3(0.07, 0.03, 1).normalize(),
            new THREE.Vector3(0.577, 0.61, 0.55).normalize()];
        const org = new THREE.Vector3();
        const inside = (bx, by, bz) => {                  // block-local point
            org.set(bx / s + cx, (by + sink) / s + bb.min.y, bz / s + cz);   // back to model space
            let votes = 0;
            for (const d of dirs) {
                ray.set(org, d);
                if ((ray.intersectObject(probe, false).length % 2) === 1) votes++;
            }
            return votes >= 2;
        };

        // ── the milled solid: a scalar field that STARTS SOLID ──
        // Default renderer: makeIsoField — the SAME metaball isosurface but
        // raymarched per-pixel on the GPU (realtime, no triangle ceiling).
        // `gpu: false` falls back to three's MarchingCubes, a JS polygonizer
        // that re-triangulates the whole field on CPU every changed frame
        // (~1fps at 1080p — background/debug only).
        const { uniform, positionWorld, smoothstep, step, vec3 } = THREE;
        const cutY = uniform(1e3);
        const cellW = (2 * HALF) / (res - 1);
        const col = new THREE.Color(o.color ?? 0x9aa2ac);
        const band = (posY) => vec3(1.0, 0.5, 0.15)
            .mul(smoothstep(cutY.sub(0.02), cutY, posY))
            .mul(smoothstep(cutY.add(0.05), cutY, posY)).mul(0.9);
        const useGPU = (o.gpu ?? true) && !!globalThis.makeIsoField;
        let mc = null, isoF = null, solid, field, shadowBox = null;
        if (useGPU) {
            isoF = globalThis.makeIsoField({
                resolution: res, half: HALF, iso: 50,
                color: col.getHex(), metalness: 0.85, roughness: 0.35,
                steps: o.steps ?? Math.max(180, Math.round(res * 2.2)),
                emissive: (hp) => band(hp.y),
                parent: gantry.group,                      // parks at (0, HALF, 0)
            });
            solid = isoF.mesh;
            field = isoF.field;
            // raymarched pixels can't cast shadows — an invisible box stands
            // in, shrinking with the milling front
            shadowBox = new THREE.Mesh(new THREE.BoxGeometry(block.w, block.h, block.d),
                new THREE.MeshBasicNodeMaterial({ colorWrite: false, depthWrite: false }));
            shadowBox.castShadow = true;
            shadowBox.position.set(0, block.h / 2, 0);
            shadowBox.userData.noSupportCheck = true;
            shadowBox.userData.noClippingCheck = true;
            gantry.group.add(shadowBox);
        } else {
            const mat = new THREE.MeshStandardNodeMaterial({ roughness: 0.35, metalness: 0.85 });
            mat.colorNode = vec3(col.r, col.g, col.b);
            if (globalThis.MechParts) globalThis.MechParts.applyBrushedMetal(mat, { baseRough: 0.32 });
            // hot milling front: a thin glow band at the current cutting height
            mat.emissiveNode = band(positionWorld.y);
            const { MarchingCubes } = await import('npm:three@0.184.0/examples/jsm/objects/MarchingCubes.js');
            // triangle budget scales with res — MarchingCubes TRUNCATES SILENTLY
            // past maxPolyCount (geometry just goes missing mid-carve)
            const maxPoly = Math.min(900000, Math.max(300000, Math.round(res * res * res * 2.2)));
            mc = new MarchingCubes(res, mat, false, false, maxPoly);
            mc.scale.setScalar(HALF);
            mc.isolation = 50;
            mc.castShadow = true;
            mc.frustumCulled = false;
            // park the block on the floor between the gantry legs
            mc.position.set(0, HALF, 0);
            gantry.group.add(mc);
            mc.userData.noSupportCheck = true;
            solid = mc;
            field = mc.field;
        }

        // ── the FINISHED SURFACE: the exact source mesh, revealed above the
        // milling front as regions complete (field rows hand over below).
        // Crisp true geometry where machining is done, chunky metaball stock
        // where it isn't; the glow band hides the handover seam.
        const floorClip = uniform(-1e3);                   // set at job start (hides the sunk sliver)
        const partGeo = geo.clone();
        if (!partGeo.attributes.normal) partGeo.computeVertexNormals();
        partGeo.applyMatrix4(new THREE.Matrix4().makeTranslation(0, -sink, 0)
            .multiply(new THREE.Matrix4().makeScale(s, s, s))
            .multiply(new THREE.Matrix4().makeTranslation(-cx, -bb.min.y, -cz)));
        const partMat = new THREE.MeshStandardNodeMaterial({ roughness: 0.32, metalness: 0.88, side: THREE.DoubleSide });
        partMat.colorNode = vec3(col.r, col.g, col.b);
        if (globalThis.MechParts) globalThis.MechParts.applyBrushedMetal(partMat, { baseRough: 0.3 });
        partMat.emissiveNode = band(positionWorld.y);
        partMat.opacityNode = step(cutY.add(cellW * 2.5), positionWorld.y).mul(step(floorClip, positionWorld.y));
        partMat.alphaTest = 0.5;
        const part = new THREE.Mesh(partGeo, partMat);
        part.castShadow = true;
        part.frustumCulled = false;
        part.userData.noSupportCheck = true;
        gantry.group.add(part);

        // field indexing (three MarchingCubes layout: x + y*size + z*size*size)
        const size2 = res * res;
        const idx = (x, y, z) => x + y * res + z * size2;
        const toBlock = (gx) => (gx / (res - 1)) * 2 * HALF - HALF;   // grid -> block-local (x,z)
        const toBlockY = (gy) => (gy / (res - 1)) * 2 * HALF;          // grid -> local y (0..2*HALF)
        const cuts = [];                                   // carve list: outside-target block voxels
        const keptMask = new Uint8Array(res * res * res);
        let kept = 0;
        for (let gz = 0; gz < res; gz++) for (let gy = 0; gy < res; gy++) for (let gx = 0; gx < res; gx++) {
            const bx = toBlock(gx), by = toBlockY(gy), bz = toBlock(gz);
            const inBlock = Math.abs(bx) <= block.w / 2 && by <= block.h && Math.abs(bz) <= block.d / 2;
            if (!inBlock) { field[idx(gx, gy, gz)] = 0; continue; }
            field[idx(gx, gy, gz)] = 100;                  // solid stock
            if (inside(bx, by, bz)) { kept++; keptMask[idx(gx, gy, gz)] = 1; continue; }
            cuts.push({ gx, gy, gz, bx, by, bz });
        }
        // ── scrub parity debris: any open surface that slipped through the
        // mesh filter (or holes in a "solid") leaves 1-voxel streaks. Kept
        // cells with <3 kept 6-neighbors are debris, not model — demote.
        if (o.scrub !== false) {
            let removed = 0;
            for (let pass = 0; pass < 2; pass++) {
                const demote = [];
                for (let gz = 0; gz < res; gz++) for (let gy = 0; gy < res; gy++) for (let gx = 0; gx < res; gx++) {
                    if (!keptMask[idx(gx, gy, gz)]) continue;
                    let nb = 0;
                    if (gx > 0 && keptMask[idx(gx - 1, gy, gz)]) nb++;
                    if (gx < res - 1 && keptMask[idx(gx + 1, gy, gz)]) nb++;
                    if (gy > 0 && keptMask[idx(gx, gy - 1, gz)]) nb++;
                    if (gy < res - 1 && keptMask[idx(gx, gy + 1, gz)]) nb++;
                    if (gz > 0 && keptMask[idx(gx, gy, gz - 1)]) nb++;
                    if (gz < res - 1 && keptMask[idx(gx, gy, gz + 1)]) nb++;
                    if (nb < 3) demote.push([gx, gy, gz]);
                }
                for (const [gx, gy, gz] of demote) {
                    keptMask[idx(gx, gy, gz)] = 0; kept--; removed++;
                    cuts.push({ gx, gy, gz, bx: toBlock(gx), by: toBlockY(gy), bz: toBlock(gz) });
                }
            }
            if (removed) console.log(`[cnc_sim] scrubbed ${removed} parity-debris voxels`);
        }
        // ── sub-voxel fidelity: grade the MILLED side of the boundary. The
        // kept side stays at 100 — grading kept cells down toward the iso
        // let trilinear interpolation dip BELOW it through diagonal milled
        // neighbors, punching see-through pinholes in the surface. Instead,
        // each to-be-milled cell that touches the model carries a graded
        // value (0..48) encoding where the true surface crosses; the mill
        // stamps that value (not 0) when it cuts the cell.
        const stepW = (2 * HALF) / (res - 1);              // one cell in world units
        const axisDirs = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]
            .map((a) => new THREE.Vector3(...a));
        let graded = 0;
        for (const c of cuts) {
            c.v = 0;
            const kNb =
                (c.gx > 0 && keptMask[idx(c.gx - 1, c.gy, c.gz)]) || (c.gx < res - 1 && keptMask[idx(c.gx + 1, c.gy, c.gz)]) ||
                (c.gy > 0 && keptMask[idx(c.gx, c.gy - 1, c.gz)]) || (c.gy < res - 1 && keptMask[idx(c.gx, c.gy + 1, c.gz)]) ||
                (c.gz > 0 && keptMask[idx(c.gx, c.gy, c.gz - 1)]) || (c.gz < res - 1 && keptMask[idx(c.gx, c.gy, c.gz + 1)]);
            if (!kNb) continue;
            org.set(c.bx / s + cx, (c.by + sink) / s + bb.min.y, c.bz / s + cz);
            let d = stepW;                                 // distance from the AIR cell to the surface
            ray.far = (stepW * 1.75) / s;                  // model-space early-out
            for (const a of axisDirs) {
                ray.set(org, a);
                const h = ray.intersectObject(probe, false);
                if (h.length) d = Math.min(d, h[0].distance * s);
            }
            ray.far = Infinity;
            // crossing sits t of the way from the kept neighbor: v = 100 - 50/t
            const t = Math.max(0.55, 1 - d / stepW);
            c.v = Math.max(0, Math.min(48, 100 - 50 / t));
            graded++;
        }
        // mill top-down, sweeping across each layer
        cuts.sort((a, b) => (b.gy - a.gy) || (((a.gy % 2) ? 1 : -1) * (a.gx - b.gx)) || (a.gz - b.gz));
        console.log(`[cnc_sim] stock voxels: ${kept + cuts.length}, to mill: ${cuts.length}, keeping: ${kept} (${graded} surface cells sub-voxel graded)`);

        // ── the spindle: a spinning cutter bit on the gantry head ──
        const dark = new THREE.MeshStandardNodeMaterial({ color: 0x22262c, roughness: 0.5, metalness: 0.7 });
        const spindle = new THREE.Group();
        const collet = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.035, 0.06, 10), dark);
        spindle.add(collet);
        const bit = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.011, 0.09, 6), new THREE.MeshStandardNodeMaterial({ color: 0xc9b46a, roughness: 0.3, metalness: 0.9 }));
        bit.position.y = -0.07;
        spindle.add(bit);
        spindle.position.y = -0.05;
        gantry.head.add(spindle);
        gantry._printJobActive = true;                     // CNCSim owns the axes (same yield flag)

        // chip spray at the cutter (short-lived sparks riding the bit)
        let chips = null;
        const chipPos = new THREE.Vector3();
        if (o.chips !== false && globalThis.makeParticles) {
            let root = gantry.group;
            while (root.parent) root = root.parent;
            if (root.isScene) chips = globalThis.makeParticles({
                scene: root, preset: 'sparks', count: 70, size: 0.018,
                lifetime: 0.28, gravity: [0, -3.5, 0], color: 0xffd9a0, origin: [0, 0, 0],
            });
        }

        const job = { gantry, solid: part, field: solid, progress: 0, done: false, _n: 0, _t0: null, _row: res - 1 };
        const gpos = gantry.group.position;
        job._update = (t, dt) => {
            if (job._t0 === null) {
                job._t0 = t;
                floorClip.value = gpos.y + 0.004;          // clip the sunk sliver at the floor
            }
            const u = Math.min(1, (t - job._t0) / duration);
            job.progress = u;
            const target = Math.floor(u * cuts.length);
            let changed = false;
            while (job._n < target) {
                const c = cuts[job._n++];
                field[idx(c.gx, c.gy, c.gz)] = c.v || 0;   // graded boundary cells carve sub-voxel
                changed = true;
            }
            const cur = cuts[Math.min(cuts.length - 1, target)];
            if (u < 1 && cur) {
                // drive the gantry axes to the current cut (gantry-local coords)
                gantry.p.x = cur.bx;
                gantry.p.z = cur.bz;
                gantry.p.y = Math.min(gantry.H * 0.9, cur.by + HALF * 0 + 0.12);
                gantry.bridge.position.z = gantry.p.z;
                gantry.carriage.position.x = gantry.p.x;
                const drop = gantry.bridge.position.y - (cur.by + 0.16);
                gantry.quill.scale.y = Math.max(0.08, drop + 0.08) / gantry.H;  // telescoping quill
                gantry.quill.position.y = -drop / 2 + 0.04;
                gantry.head.position.y = -drop;
                cutY.value = gpos.y + cur.by + 0.02;
                // hand FULLY-MILLED rows over from the field to the true
                // mesh: above the lag band the region is finished — the
                // field zeroes there and the exact source geometry shows
                while (job._row >= 0 && toBlockY(job._row) > cur.by + cellW * 2.5) {
                    const gy = job._row--;
                    for (let hz = 0; hz < res; hz++) for (let hx = 0; hx < res; hx++) field[idx(hx, gy, hz)] = 0;
                    changed = true;
                }
                if (chips) { bit.getWorldPosition(chipPos); chips.mesh.position.copy(chipPos); }
            } else if (!job.done && u >= 1) {
                job.done = true;
                cutY.value = -1e3;                         // mesh fully revealed, band off
                field.fill(0);                             // the field hands over entirely
                changed = true;
                if (shadowBox) shadowBox.visible = false;  // the part casts its own shadow
                if (chips) chips.mesh.visible = false;     // spindle stops, chips stop
                gantry._printJobActive = false;            // hand the axes back
                if (o.onDone) { try { o.onDone(job); } catch (e) {} }
            }
            spindle.rotation.y += 40 * (dt ?? 1 / 30);
            if (changed || !job._mcInit) {
                if (isoF) isoF.upload(); else mc.update();
                job._mcInit = true;
            }
            if (shadowBox && !job.done) {                  // proxy tracks the remaining stock
                const hFrac = Math.min(1, Math.max(0.06, (cutY.value - gpos.y) / block.h));
                shadowBox.scale.y = hFrac;
                shadowBox.position.y = (block.h * hFrac) / 2;
            }
        };
        (globalThis._autoRobots || (globalThis._autoRobots = [])).push((t, dt) => job._update(t, dt));
        return job;
    }

    globalThis.FabSim = { print, carve };
    globalThis.PrintSim = { print };                   // back-compat aliases
    globalThis.CNCSim = { carve };
    console.log('[fab_sim] FabSim.print (additive: molten goo band + true mesh; printer/delta) & FabSim.carve (subtractive: metaball stock + true mesh; gantry) — PrintSim/CNCSim alias here');
})();
