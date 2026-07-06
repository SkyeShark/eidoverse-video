// robotics_kit.js — globalThis.RoboticsKit / makeRobot: industrial robot
// assemblies that are NOT creatures (makeCreature owns organic/humanoid;
// this owns machines). Every archetype ships with REAL kinematics — closed
// form IK where it exists — and slew-rate-limited joints, which is most of
// what reads as "actual robot" instead of a prop: real machines move each
// joint at bounded speed toward the solution, they don't teleport.
//
//   const arm = globalThis.makeRobot('arm', {
//       position: [0, 0, 0], reach: 1.6, tool: 'gripper',
//       color: 0xd8891a, accent: 0x2a2a30,
//   });
//   scene.add(arm.group);
//   arm.pickAndPlace({ from: [1.1, 0, 0.4], to: [-0.9, 0.35, 0.6], period: 4 });
//   // or drive it yourself: arm.reachTo(worldVec3, dt); arm.setGrip(0..1)
//
//   const delta   = makeRobot('delta',   { position: [3, 2.2, 0] });   // hangs from its frame
//   delta.pickLoop({ radius: 0.45, floorY: 0.05, period: 1.1 });
//   const hexapod = makeRobot('stewart', { position: [-3, 0, 0], demo: 'wobble' });
//   const turret  = makeRobot('turret',  { position: [0, 0, -3] });
//   turret.track(() => agv.getPosition());                             // slew-limited aim
//   const agv     = makeRobot('agv',     { position: [4, 0, 4] });
//   agv.patrol([[4, 4], [4, -4], [-4, -4], [-4, 4]]);
//   const gantry  = makeRobot('gantry',  { position: [0, 0, 6], demo: 'scan' });
//   const scara   = makeRobot('scara',   { position: [6, 0, 0], demo: 'sort' });
//
// All robots self-animate (opts.auto !== false) via the engine's
// _autoRobots drain.
//
// CONTRAPTIONS — chain robots into weird animated assemblies:
//   agv.mount(turret)                                      // turret rides the AGV deck
//   RoboticsKit.connect(stewart, arm, { at: 'top' })       // arm on a wobbling hexapod
//   arm.mount(camera_prop, { at: 'flange' })               // anything on an arm wrist
//   gantry.mount(delta, { at: 'carriage', offset: [0, -0.1, 0] })
// Every robot exposes robot.mounts() (named frames: arm base/flange/tip,
// stewart base/top, turret base/head/barrel, agv deck/body, gantry
// frame/carriage, scara base/tool, delta frame/plate) and mountPoint()
// (the default ride frame). Children keep animating on a moving parent —
// arm IK and turret aim solve in their own local frames.
//
// MATERIALS — procedural by default (flat PBR metal from opts.color /
// opts.accent — no fetched content baked in). Adding materials is the
// AGENT'S option, three tiers:
//   makeRobot('arm', { color: 0xd84a4a, accent: 0x202020 })          // procedural tint
//   makeRobot('agv', { bodyMaterial: ProceduralMaterials.createWornMetal({...}) })
//   await RoboticsKit.applyTextures(arm,                             // fetched PBR set,
//       { diff: ASSETS.rust_diff, rough: ASSETS.rust_rough, normal: ASSETS.rust_normal },
//       { repeat: 2, part: 'body' });          // part: 'body' | 'accent' | 'all'
// applyTextures takes the SAME keys fetch_texture.py writes to
// tex_urls.json (values: raw ASSETS bytes or loaded THREE.Textures).
//
// Realism notes baked in:
// - joints obey maxRate (rad/s) — coordinated joint-interpolated motion
// - two-part pistons (sleeve + rod) stay coaxial at any pose (Stewart)
// - delta forearms render as true parallelogram rod pairs
// - hoses are link-local Loft sweeps, so they flex WITH the joint chain
(function () {
    const THREE = globalThis.THREE;
    const V = (x, y, z) => new THREE.Vector3(x, y, z);
    const UP = new THREE.Vector3(0, 1, 0);
    const TMPa = new THREE.Vector3(), TMPb = new THREE.Vector3(), TMPc = new THREE.Vector3(), TMPd = new THREE.Vector3();
    const TMPq = new THREE.Quaternion();
    const TMPm = new THREE.Matrix4();

    const metal = (color, rough = 0.38, met = 0.85) =>
        new THREE.MeshStandardNodeMaterial({ color, roughness: rough, metalness: met });
    const rubber = (color = 0x181818) =>
        new THREE.MeshStandardNodeMaterial({ color, roughness: 0.92, metalness: 0.05 });
    // Materials are PROCEDURAL by default (flat PBR metal from opts.color /
    // opts.accent). Agents can hand in ANY material instead — a
    // ProceduralMaterials generator, a NodeMaterial of their own, whatever:
    //   makeRobot('agv', { bodyMaterial: ProceduralMaterials.createWornMetal({...}) })
    // or dress a built robot later with RoboticsKit.applyTextures().
    const bodyMat = (opts, c, r = 0.38, m = 0.85) => opts.bodyMaterial || metal(opts.color ?? c, r, m);
    const accentMat = (opts, c, r = 0.45, m = 0.75) => opts.accentMaterial || metal(opts.accent ?? c, r, m);

    // slew a scalar toward target at bounded rate
    const slew = (cur, tgt, rate, dt) => {
        const d = tgt - cur;
        const m = rate * dt;
        return cur + Math.max(-m, Math.min(m, d));
    };
    // ── MOTION POLISH: spring-damped stepping ──
    // Rate-limited cruise + a slightly UNDERDAMPED settle at arrival (hard
    // slew stops read dead; real servos overshoot a hair and damp back).
    // The shared timescale also brings multi-joint moves to a COORDINATED
    // arrival instead of each joint stopping on its own schedule.
    const wrapPi = (a) => { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; };
    const springStep = (cur, vel, tgt, rate, dt, omega = 9, zeta = 0.8) => {
        const d = Math.max(1e-4, Math.min(dt || 1 / 30, 0.05));
        let v = vel + (omega * omega * (tgt - cur) - 2 * zeta * omega * vel) * d;
        if (v > rate) v = rate; else if (v < -rate) v = -rate;
        return [cur + v * d, v];
    };
    const springAngle = (cur, vel, tgt, rate, dt, omega, zeta) =>
        springStep(cur, vel, cur + wrapPi(tgt - cur), rate, dt, omega, zeta);

    const slewAngle = (cur, tgt, rate, dt) => {
        let d = (tgt - cur) % (Math.PI * 2);
        if (d > Math.PI) d -= Math.PI * 2;
        if (d < -Math.PI) d += Math.PI * 2;
        const m = rate * dt;
        return cur + Math.max(-m, Math.min(m, d));
    };

    // orient+stretch a unit-length (y-axis) cylinder mesh between two WORLD
    // points, in the mesh's parent space. THE two-point member primitive:
    // pistons, delta forearms, tie rods. DEDICATED temps: this must never
    // mutate its inputs — callers chain calls reusing the same vectors, and
    // an in-place worldToLocal here double-transforms the second call's
    // endpoints into garbage (stewart rods piled at the origin).
    const LBa = new THREE.Vector3(), LBb = new THREE.Vector3(), LBd = new THREE.Vector3();
    function linkBetween(mesh, aW, bW) {
        const parent = mesh.parent;
        const a = LBa.copy(aW), b = LBb.copy(bW);
        if (parent) { parent.worldToLocal(a); parent.worldToLocal(b); }
        const d = LBd.copy(b).sub(a);
        const len = Math.max(1e-6, d.length());
        mesh.position.copy(a).addScaledVector(d, 0.5);
        mesh.quaternion.setFromUnitVectors(UP, d.multiplyScalar(1 / len));
        mesh.scale.y = len;
        return len;
    }

    // decorative bolt ring on a flange
    function boltRing(parent, r, y, n, mat) {
        for (let i = 0; i < n; i++) {
            const a = (i / n) * Math.PI * 2;
            const bolt = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.07, r * 0.07, r * 0.1, 6), mat);
            bolt.position.set(Math.cos(a) * r * 0.8, y, Math.sin(a) * r * 0.8);
            parent.add(bolt);
        }
    }

    // link-local hose: a Loft sweep that rides its parent link rigidly
    function hose(parent, pts, r, mat) {
        if (!globalThis.Loft) return null;
        try {
            const h = globalThis.Loft.sweep({
                path: pts, profile: globalThis.Loft.circle(r, 6),
                sections: 10, material: mat || rubber(),
            });
            parent.add(h);
            return h;
        } catch (e) { return null; }
    }

    // ── TALKING (light-sync): pulse every emissive lamp on the machine in
    // speech rhythm — the classic sci-fi robot voice light. Procedural
    // syllables by default; setTalkEnvelope maps a real audio-amplitude fn
    // straight onto the lights for sync with generated TTS.
    const _talkTick = (robot, t) => {
        const tk = robot._talk;
        if (!tk) return;
        if (tk.until == null) tk.until = (tk.dur != null) ? t + tk.dur : Infinity;
        if (!robot._talkLights) {
            const L = [];
            robot.group.traverse((o) => {
                if (o.isMesh && o.material && o.material.emissive &&
                    (o.material.emissiveIntensity ?? 0) > 0.2 &&
                    (o.material.emissive.r + o.material.emissive.g + o.material.emissive.b) > 0.05) {
                    L.push({ m: o.material, base: o.material.emissiveIntensity });
                }
            });
            robot._talkLights = L;
            if (!L.length) console.warn('[robotics_kit] say(): this machine has no emissive lights to sync');
        }
        let open = 0;
        if (tk.env) open = Math.max(0, Math.min(1, tk.env(t) || 0));
        else if (t < tk.until) {
            robot._talkSeed = robot._talkSeed ?? Math.random() * 6.283;
            const sy = Math.sin(t * 27.2 + robot._talkSeed) * 0.5 + 0.5;
            const am = 0.55 + 0.45 * Math.sin(t * 7.31 + robot._talkSeed * 1.7);
            open = (tk.energy ?? 0.85) * Math.max(0, sy * am - 0.08);
        } else { robot.stopTalking(); return; }
        for (const l of robot._talkLights) l.m.emissiveIntensity = l.base * (0.3 + 2.2 * open);
        // tiny head nod where an articulated head exists (makeBot Head module)
        const hd = robot.head && (robot.head.pitchG || robot.head.yawG);
        if (hd) {
            if (hd.userData._talkBase == null) hd.userData._talkBase = hd.rotation.x;
            hd.rotation.x = hd.userData._talkBase - open * 0.08;
        }
    };

    const register = (robot, opts) => {
        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('robotics_kit');
        // kit robots stand at y=0 of their own group BY CONSTRUCTION — exempt
        // them from the hover audit (its footprint rays misread multi-part
        // machines and "rescue"-sink them ~0.1m into the floor). Mechanical
        // assemblies also OVERLAP by construction (drums in links, motors in
        // housings) — the clipping auto-separator must not pull them apart.
        robot.group.userData.noSupportCheck = true;
        robot.group.userData.noClippingCheck = true;
        // every robot gets the generic contraption API: robot.mount(child, {at, offset, rotation, scale})
        robot.mount = (child, o) => RoboticsKit.connect(robot, child, o);
        // every robot can TALK via its lights:
        //   bot.say('a sentence')  /  bot.say({ duration: 4, energy: 0.9 })
        //   bot.setTalkEnvelope((t) => amp01)   // sync to real audio
        //   bot.stopTalking()
        robot.say = (o) => {
            if (typeof o === 'string') o = { duration: Math.max(1.2, o.split(/\s+/).length / 2.6) };
            robot._talk = { dur: (o && o.duration) ?? 3, until: null,
                energy: (o && o.energy) ?? 0.85, env: (o && o.envelope) || null };
            return robot;
        };
        robot.stopTalking = () => {
            if (robot._talkLights) for (const l of robot._talkLights) l.m.emissiveIntensity = l.base;
            const hd = robot.head && (robot.head.pitchG || robot.head.yawG);
            if (hd && hd.userData._talkBase != null) hd.rotation.x = hd.userData._talkBase;
            robot._talk = null;
            return robot;
        };
        robot.setTalkEnvelope = (fn) => { robot._talk = fn ? { until: Infinity, env: fn } : null; return robot; };
        if (opts.auto !== false) (globalThis._autoRobots || (globalThis._autoRobots = [])).push((t, dt) => {
            robot.update(t, dt ?? 1 / 30);
            _talkTick(robot, t);
        });
        return robot;
    };

    // ════════════════════════════════════════════════════════════════════
    // 6-DOF industrial arm — yaw base, shoulder, elbow, wrist pitch + roll,
    // tool flange. Closed-form position IK (2R triangle after base yaw),
    // wrist aligns the tool to an approach vector. reachTo() is API-
    // compatible with the old robotic_arm helper.
    // ════════════════════════════════════════════════════════════════════
    class Arm6 {
        constructor(opts = {}) {
            this.opts = opts;
            const reach = opts.reach ?? 1.5;
            this.L1 = reach * 0.14;                 // base pedestal height → shoulder pivot
            this.L2 = reach * 0.44;                 // upper arm
            this.L3 = reach * 0.40;                 // forearm — slightly SHORTER than L2 (symmetric reads fake)
            this.toolLen = reach * 0.14;
            this.maxRate = opts.maxRate ?? 2.6;     // rad/s per joint
            const body = bodyMat(opts, 0xd8891a);
            const dark = accentMat(opts, 0x2a2a30);
            this.materials = { body, dark };
            const MP = globalThis.MechParts;        // procedural part vocabulary (mech_parts.js)

            const g = this.group = new THREE.Group();
            g.name = 'robot_arm6';
            if (opts.position) g.position.fromArray(opts.position);
            const r0 = reach * 0.09;
            const v2 = (x, y) => new THREE.Vector2(Math.max(x, 0), y);

            // pedestal — wide bolted base flange → tapered cast column, with
            // a junction box + floor conduit on the back (cell wiring enters
            // through the floor on real installs). MOUNTED arms (shoulder,
            // deck, drone belly) pass pedestal: false and get a compact
            // collar instead — no floor furniture floating in the air.
            if (opts.pedestal === false) {
                this.L1 = r0 * 0.55;
                const collar = new THREE.Mesh(new THREE.CylinderGeometry(r0 * 1.15, r0 * 1.3, this.L1, 16), dark);
                collar.position.y = this.L1 / 2; collar.castShadow = true; g.add(collar);
            } else if (MP) {
                // two crisp steps: wide flange disc + cylindrical column
                const flangeH = this.L1 * 0.2;
                const flangeGeo = new THREE.CylinderGeometry(r0 * 2.25, r0 * 2.3, flangeH, 22);
                flangeGeo.translate(0, flangeH / 2, 0);
                const colGeo = new THREE.CylinderGeometry(r0 * 1.5, r0 * 1.58, this.L1 - flangeH, 20);
                colGeo.translate(0, flangeH + (this.L1 - flangeH) / 2, 0);
                const boltGeos = MP.hexBolts(r0 * 2.4, flangeH + r0 * 0.04, 8, { seed: 11, boltR: r0 * 0.12 });
                const ped = new THREE.Mesh(THREE.mergeGeometries ? THREE.mergeGeometries([flangeGeo, colGeo, ...boltGeos], false) : colGeo, dark);
                ped.castShadow = ped.receiveShadow = true;
                g.add(ped);
                const jbox = MP.chamferedBox(r0 * 1.1, this.L1 * 0.46, r0 * 0.65, r0 * 0.05, dark);
                jbox.position.set(-r0 * 1.9, this.L1 * 0.52, 0); g.add(jbox);
                const conduit = MP.makeCable(V(-r0 * 1.9, this.L1 * 0.32, r0 * 0.3), V(-r0 * 2.2, 0.01, r0 * 1.0),
                    { radius: r0 * 0.09, sag: 0.0, corrugated: true });
                g.add(conduit);
            } else {
                const ped = new THREE.Mesh(new THREE.CylinderGeometry(r0 * 1.7, r0 * 2.1, this.L1, 18), dark);
                ped.position.y = this.L1 / 2; ped.castShadow = true; g.add(ped);
                boltRing(g, r0 * 2.1, 0.02, 8, body);
            }

            // clean joint-drum helper: centered cylinder on the joint axis
            // (X) + a coaxial motor can on one side — everything symmetric
            // about the axis, nothing off-center
            const drum = (parent, R, len, motorSide = 0) => {
                const d = new THREE.Mesh(new THREE.CylinderGeometry(R, R, len, 18), dark);
                d.rotation.z = Math.PI / 2; d.castShadow = true;
                parent.add(d);
                if (motorSide) {
                    const can = new THREE.Mesh(new THREE.CylinderGeometry(R * 0.72, R * 0.72, R * 0.85, 16), dark);
                    can.rotation.z = Math.PI / 2; can.position.x = motorSide * (len / 2 + R * 0.42);
                    can.castShadow = true; parent.add(can);
                    const cap = new THREE.Mesh(new THREE.CylinderGeometry(R * 0.5, R * 0.5, R * 0.12, 16), body);
                    cap.rotation.z = Math.PI / 2; cap.position.x = motorSide * (len / 2 + R * 0.9);
                    parent.add(cap);
                }
                return d;
            };

            // J1 yaw — turntable drum with a visible rotation seam
            this.j1 = new THREE.Group(); this.j1.position.y = this.L1; g.add(this.j1);
            const seam = new THREE.Mesh(new THREE.CylinderGeometry(r0 * 1.56, r0 * 1.56, r0 * 0.12, 20), dark);
            seam.position.y = r0 * 0.06; this.j1.add(seam);
            const turntable = new THREE.Mesh(new THREE.CylinderGeometry(r0 * 1.42, r0 * 1.52, r0 * 1.1, 20), body);
            turntable.position.y = r0 * 0.66; turntable.castShadow = true;
            this.j1.add(turntable);

            // J2 shoulder — one centered drum, motor can on +X
            this.j2 = new THREE.Group(); this.j2.position.y = r0 * 1.2; this.j1.add(this.j2);
            this._shoulderH = this.L1 + r0 * 1.2;   // shoulder pivot height in ARM-LOCAL space
            drum(this.j2, r0 * 1.02, r0 * 2.2, +1);
            // upper arm — clean tapered beam, wide at the shoulder
            const upper = MP
                ? MP.armLinkCasting({ length: this.L2, boxW: r0 * 1.5, boxH: r0 * 1.7, endW: r0 * 1.02, endH: r0 * 1.15, ribs: 0, material: body })
                : (() => { const m = new THREE.Mesh(new THREE.CapsuleGeometry(r0 * 0.85, this.L2 - r0 * 1.7, 6, 12), body); m.rotation.x = Math.PI / 2; m.position.z = this.L2 / 2; return m; })();
            upper.castShadow = true;
            this.j2.add(upper);
            // ONE tight backbone conduit along the top of the upper arm
            if (MP) {
                const loom = MP.makeCable(V(r0 * 0.45, r0 * 0.95, r0 * 0.25), V(r0 * 0.4, r0 * 0.72, this.L2 * 0.9),
                    { radius: r0 * 0.11, sag: r0 * 0.2, corrugated: true, seed: 5 });
                this.j2.add(loom);
            } else {
                hose(this.j2, [V(r0 * 0.9, r0 * 0.6, 0), V(r0 * 1.15, r0 * 0.3, this.L2 * 0.35), V(r0 * 0.9, 0, this.L2 * 0.8)], r0 * 0.16);
            }

            // J3 elbow — smaller centered drum, motor can on −X
            this.j3 = new THREE.Group(); this.j3.position.z = this.L2; this.j2.add(this.j3);
            drum(this.j3, r0 * 0.76, r0 * 1.6, -1);
            const fore = MP
                ? MP.armLinkCasting({ length: this.L3, boxW: r0 * 1.05, boxH: r0 * 1.2, endW: r0 * 0.7, endH: r0 * 0.78, ribs: 0, material: body })
                : (() => { const m = new THREE.Mesh(new THREE.CapsuleGeometry(r0 * 0.62, this.L3 - r0 * 1.4, 6, 12), body); m.rotation.x = Math.PI / 2; m.position.z = this.L3 / 2; return m; })();
            fore.castShadow = true;
            this.j3.add(fore);
            // thin tool harness along the forearm side
            if (MP) {
                const harness = MP.makeCable(V(-r0 * 0.42, r0 * 0.5, r0 * 0.15), V(-r0 * 0.3, r0 * 0.32, this.L3 * 0.9),
                    { radius: r0 * 0.07, sag: r0 * 0.16, corrugated: true, seed: 13 });
                this.j3.add(harness);
            } else {
                hose(this.j3, [V(-r0 * 0.7, r0 * 0.45, 0), V(-r0 * 0.9, r0 * 0.2, this.L3 * 0.4), V(-r0 * 0.65, 0, this.L3 * 0.85)], r0 * 0.13);
            }

            // J5 wrist pitch + J6 tool roll + flange — compact centered drum
            this.j5 = new THREE.Group(); this.j5.position.z = this.L3; this.j3.add(this.j5);
            drum(this.j5, r0 * 0.48, r0 * 1.05, +1);
            this.j6 = new THREE.Group(); this.j5.add(this.j6);
            const rollDrum = new THREE.Mesh(new THREE.CylinderGeometry(r0 * 0.46, r0 * 0.5, r0 * 0.34, 14), body);
            rollDrum.rotation.x = Math.PI / 2; rollDrum.position.z = r0 * 0.17;
            this.j6.add(rollDrum);
            const flangeGeos = [new THREE.CylinderGeometry(r0 * 0.42, r0 * 0.46, r0 * 0.2, 14)];
            if (MP && THREE.mergeGeometries) flangeGeos.push(...MP.hexBolts(r0 * 0.44, r0 * 0.11, 6, { seed: 3, boltR: r0 * 0.055 }));
            const flange = new THREE.Mesh(THREE.mergeGeometries ? THREE.mergeGeometries(flangeGeos, false) : flangeGeos[0], dark);
            flange.rotation.x = Math.PI / 2; flange.position.z = r0 * 0.42;
            flange.castShadow = true;
            this.j6.add(flange);

            // tool
            this.toolTip = new THREE.Group();                 // world frame of the business end
            this.toolTip.position.z = this.toolLen;
            this.j6.add(this.toolTip);
            this._grip = 1;                                    // 1 = open
            this._fingers = [];
            const tool = opts.tool ?? 'gripper';
            this._r0 = r0;
            if (tool === 'gripper') {
                // parallel-jaw gripper as an actual MECHANISM: actuator housing,
                // a visible cross rail, and two jaw CARRIAGES that slide the
                // rail (prismatic) — the only moving DOF is carriage x. Jaws
                // close onto the payload's real width (contact), no teleporting.
                const housing = MP
                    ? MP.chamferedBox(r0 * 1.15, r0 * 0.5, r0 * 0.62, r0 * 0.05, dark)
                    : new THREE.Mesh(new THREE.BoxGeometry(r0 * 1.15, r0 * 0.5, r0 * 0.62), dark);
                housing.position.z = r0 * 0.78; this.j6.add(housing);
                const railM = new THREE.Mesh(new THREE.BoxGeometry(r0 * 2.0, r0 * 0.13, r0 * 0.16), metal(0xd8dce2, 0.25, 0.9));
                railM.position.set(0, -r0 * 0.12, r0 * 1.06); this.j6.add(railM);
                this._jawOpen = r0 * 0.8;                  // carriage |x| fully open
                this._jawClosed = r0 * 0.1;                // carriage |x| fully closed
                for (const sd of [-1, 1]) {
                    const carriage = new THREE.Group();
                    carriage.position.set(sd * this._jawOpen, -r0 * 0.12, r0 * 1.06);
                    carriage.userData.side = sd;
                    const block = MP
                        ? MP.chamferedBox(r0 * 0.3, r0 * 0.26, r0 * 0.34, r0 * 0.03, body)
                        : new THREE.Mesh(new THREE.BoxGeometry(r0 * 0.3, r0 * 0.26, r0 * 0.34), body);
                    carriage.add(block);
                    const blade = MP
                        ? MP.chamferedBox(r0 * 0.14, r0 * 0.26, r0 * 0.9, r0 * 0.02, body)
                        : new THREE.Mesh(new THREE.BoxGeometry(r0 * 0.14, r0 * 0.26, r0 * 0.9), body);
                    blade.position.set(0, -r0 * 0.02, r0 * 0.55);
                    carriage.add(blade);
                    const pad = new THREE.Mesh(new THREE.BoxGeometry(r0 * 0.05, r0 * 0.22, r0 * 0.62), rubber(0x161616));
                    pad.position.set(-sd * r0 * 0.09, -r0 * 0.02, r0 * 0.62);
                    carriage.add(pad);
                    this.j6.add(carriage); this._fingers.push(carriage);
                }
                this._padInset = r0 * 0.115;               // pad contact face inset from carriage x
            } else if (tool === 'hand') {
                // humanoid robotic hand — 4 × 3-phalanx fingers + opposable
                // thumb, every knuckle a real pivot (nothing floats). Palm
                // plane ⊥ tool axis; fingers close from +Y, thumb from −Y, so
                // the grasp aperture runs along local Y. grip 1 = open, 0 = fist.
                const mkBox = (w, h, l, mat) => MP
                    ? MP.chamferedBox(w, h, l, Math.min(w, h) * 0.18, mat)
                    : new THREE.Mesh(new THREE.BoxGeometry(w, h, l), mat);
                const hs = (opts.handScale ?? 1) * 1.45 * r0;   // hand unit — reads right vs the arm
                const cuff = new THREE.Mesh(new THREE.CylinderGeometry(hs * 0.3, hs * 0.38, hs * 0.28, 12), dark);
                cuff.rotation.x = Math.PI / 2; cuff.position.z = r0 * 0.58; this.j6.add(cuff);
                const palm = mkBox(hs * 0.95, hs * 0.8, hs * 0.3, body);
                palm.position.z = r0 * 0.58 + hs * 0.42; this.j6.add(palm);
                const mkChain = (segs, width, root, padSide = -1) => {
                    const joints = [];
                    let parent = root;
                    for (const len of segs) {
                        const j = new THREE.Group();
                        parent.add(j);
                        if (joints.length) j.position.z = segs[joints.length - 1];
                        const knuckle = new THREE.Mesh(new THREE.SphereGeometry(width * 0.62, 8, 6), dark);
                        j.add(knuckle);
                        const seg = mkBox(width, width * 0.92, len * 0.94, body);
                        seg.position.z = len / 2;
                        j.add(seg);
                        joints.push(len);
                        parent = j;
                        (root.userData.joints = root.userData.joints || []).push(j);
                    }
                    // rubber pad on the distal segment's grasp face
                    const pad = new THREE.Mesh(new THREE.BoxGeometry(width * 0.8, width * 0.3, segs[segs.length - 1] * 0.7), rubber(0x161616));
                    pad.position.set(0, padSide * width * 0.42, segs[segs.length - 1] * 0.55);
                    parent.add(pad);
                    return root.userData.joints;
                };
                this._hand = { fingers: [], thumb: null };
                const lenScale = [0.95, 1.05, 1.0, 0.82];
                const palmZ = r0 * 0.58 + hs * 0.42;
                for (let fi = 0; fi < 4; fi++) {
                    const root = new THREE.Group();
                    root.position.set((fi - 1.5) * hs * 0.24, hs * 0.3, palmZ + hs * 0.16);
                    root.rotation.y = (fi - 1.5) * 0.07;               // slight splay
                    this.j6.add(root);
                    const s = lenScale[fi];
                    const joints = mkChain([hs * 0.38 * s, hs * 0.3 * s, hs * 0.24 * s], hs * 0.16, root);
                    this._hand.fingers.push({ j: joints });
                }
                const thumbRoot = new THREE.Group();
                thumbRoot.position.set(hs * 0.32, -hs * 0.32, palmZ - hs * 0.05);
                thumbRoot.rotation.set(0, -0.35, -0.5);                 // opposed, angled across the palm
                this.j6.add(thumbRoot);
                this._hand.thumb = { j: mkChain([hs * 0.34, hs * 0.27], hs * 0.18, thumbRoot, 1) };
                this._gripAxis = 'y';                       // aperture runs along tool-local Y
                this._handSkin = hs * 0.015;
                // EXACT aperture table: distal-pad distance from the tool axis
                // as a function of curl, from the same angles _applyGripPose
                // uses — a linear jaw model here makes fingers clip the part
                this._apTable = [];
                for (let i = 0; i <= 24; i++) {
                    const c = i / 24;
                    const t1 = -0.45 + c * 1.3, t2 = t1 + c * 0.85, t3 = t2 + c * 0.55;
                    this._apTable.push(hs * 0.3
                        - (hs * 0.38 * Math.sin(t1) + hs * 0.3 * Math.sin(t2) + hs * 0.24 * Math.sin(t3))
                        - hs * 0.067);
                }
            } else if (tool === 'welder') {
                const torch = new THREE.Mesh(new THREE.CylinderGeometry(r0 * 0.14, r0 * 0.22, this.toolLen, 10), dark);
                torch.rotation.x = Math.PI / 2; torch.position.z = this.toolLen * 0.5;
                this.j6.add(torch);
                const tipM = new THREE.Mesh(new THREE.CylinderGeometry(r0 * 0.05, r0 * 0.12, this.toolLen * 0.3, 8), metal(0xc9b46a, 0.3, 0.9));
                tipM.rotation.x = Math.PI / 2; tipM.position.z = this.toolLen * 0.92;
                this.j6.add(tipM);
                // wire-feed box + feed conduit into the torch body
                if (MP) {
                    const feeder = MP.chamferedBox(r0 * 0.5, r0 * 0.4, r0 * 0.55, r0 * 0.04, dark);
                    feeder.position.set(0, r0 * 0.42, r0 * 0.35); this.j6.add(feeder);
                    const feedHose = MP.makeCable(V(0, r0 * 0.42, r0 * 0.55), V(0, r0 * 0.12, this.toolLen * 0.62),
                        { radius: r0 * 0.05, sag: r0 * 0.16, seed: 21 });
                    this.j6.add(feedHose);
                }
            }

            // joint state (current, target) — motion is slew-limited
            this.q = { j1: 0, j2: 0.5, j3: 0.9, j5: -0.6, j6: 0 };
            this.qt = { ...this.q };
            this._target = null;
            this._approach = V(0, -1, 0);                     // default: tool points down at the work
            this._program = null;
            this._carried = null;
            this._applyPose();
        }

        _applyPose() {
            const w = (this._idleW || 0) * 0.0035;             // ~0.2 deg servo hunting
            const t = this._t || 0, ph = (this.opts.seed ?? 1) * 1.7;
            this.j1.rotation.y = this.q.j1 + w * Math.sin(t * 0.9 + ph);
            this.j2.rotation.x = -(this.q.j2 + w * Math.sin(t * 0.7 + ph * 2));      // positive j2 lifts the arm
            // relative elbow: forearm elevation j23 = j2 - q.j3, and with the
            // "-θ lifts" convention the CHILD rotation is +q.j3 (parent −j2
            // composes to −j23). A minus here bends the elbow the wrong way —
            // horizontal converges but the tool floats ~L3·sin(2·j2−2·j23)
            // above every target (found via the pick-contact instrumentation).
            this.j3.rotation.x = this.q.j3 + w * Math.sin(t * 1.1 + ph * 3);
            this.j5.rotation.x = -(this.q.j5 + w * 1.6 * Math.sin(t * 1.4 + ph * 4));
            this.j6.rotation.z = this.q.j6 + w * 2.2 * Math.sin(t * 1.7 + ph * 5);
        }

        /** point the TOOL TIP at world target; approach = desired tool direction (world) */
        reachTo(targetW, dt = 1 / 30, approachW) {
            // solve in the ARM'S LOCAL frame — an arm mounted on a moving base
            // (AGV deck, gantry carriage, stewart top) still aims correctly
            this.group.updateWorldMatrix(true, false);
            const inv = TMPm.copy(this.group.matrixWorld).invert();
            const a = TMPb.copy(approachW || this._approach).transformDirection(inv);
            // wrist center = target - approach * toolLen (tool extends along approach)
            const w = TMPa.copy(targetW).applyMatrix4(inv).addScaledVector(a, -this.toolLen);
            if (w.y < this.toolLen * 0.3) w.y = this.toolLen * 0.3;   // wrist never dives below the base plane
            const dx = w.x, dz = w.z;
            const r = Math.hypot(dx, dz);
            // yaw singularity: a target (nearly) on the yaw axis makes atan2
            // thrash +-PI — hold the current heading instead of chasing it
            const yaw = r < 0.07 ? this.q.j1 : Math.atan2(dx, dz);
            const ry = w.y - this._shoulderH;
            let D = Math.hypot(r, ry);
            D = Math.min(Math.max(D, Math.abs(this.L2 - this.L3) + 1e-4), (this.L2 + this.L3) * 0.999);
            const elev = Math.atan2(ry, r);
            const cosA = (this.L2 * this.L2 + D * D - this.L3 * this.L3) / (2 * this.L2 * D);
            const A = Math.acos(Math.max(-1, Math.min(1, cosA)));
            const cosI = (this.L2 * this.L2 + this.L3 * this.L3 - D * D) / (2 * this.L2 * this.L3);
            const I = Math.acos(Math.max(-1, Math.min(1, cosI)));   // interior elbow angle
            const j2 = elev + A;                    // elevation of the upper arm (elbow-up)
            const j23 = j2 + (I - Math.PI);         // absolute elevation of the forearm
            // wrist pitch so the tool aligns with the approach vector in the
            // arm's vertical plane: tool elevation should equal approach's
            const aElev = Math.atan2(a.y, Math.hypot(a.x, a.z) || 1e-6);
            const j5 = aElev - j23;
            // per-joint range limits (sbot/collada-kinematics style) — the
            // shoulder can't dive below its mount plane, the wrist can't flip
            this.qt.j1 = yaw;
            this.qt.j2 = Math.max(-0.25, Math.min(2.4, j2));
            this.qt.j3 = Math.max(-0.3, Math.min(2.8, j2 - j23));   // relative pitch (positive = bend down)
            this.qt.j5 = Math.max(-2.2, Math.min(2.2, j5));
            this._stepJoints(dt);
        }

        _stepJoints(dt) {
            // per-joint inertia-appropriate rates: base slowest, wrist fastest
            const R = this._rates || (this._rates = { j1: 0.85, j2: 1.0, j3: 1.15, j5: 1.9, j6: 2.4 });
            const V = this._qv || (this._qv = { j1: 0, j2: 0, j3: 0, j5: 0, j6: 0 });
            this._t = (this._t || 0) + (dt || 1 / 30);
            let r;
            r = springAngle(this.q.j1, V.j1, this.qt.j1, this.maxRate * R.j1, dt); this.q.j1 = r[0]; V.j1 = r[1];
            for (const k of ['j2', 'j3', 'j5', 'j6']) {
                r = springStep(this.q[k], V[k], this.qt[k], this.maxRate * R[k], dt);
                this.q[k] = r[0]; V[k] = r[1];
            }
            // idle micro-dither weight: a POWERED machine never sits
            // perfectly still — ramps in once converged, cuts on any motion
            let conv = !this._program;
            if (conv) for (const k of ['j1', 'j2', 'j3', 'j5', 'j6']) {
                if (Math.abs(this.qt[k] - this.q[k]) > 0.03 || Math.abs(V[k]) > 0.06) { conv = false; break; }
            }
            const d0 = dt || 1 / 30;
            this._idleW = Math.max(0, Math.min(1, (this._idleW || 0) + (conv ? d0 * 0.6 : -d0 * 4)));
            this._applyPose();
        }

        setGrip(v) { this._grip = Math.max(0, Math.min(1, v)); }
        getToolTip(out) { return this.toolTip.getWorldPosition(out || new THREE.Vector3()); }

        /** grip value (0..1) at which the pads CONTACT this object's surface */
        _contactGrip(obj) {
            if (this._jawOpen === undefined && !this._hand) return 0.3;   // no gripping tool fitted
            const box = new THREE.Box3().setFromObject(obj);
            box.getSize(TMPa);
            const axis = this._gripAxis === 'y' ? TMPb.set(0, 1, 0) : TMPb.set(1, 0, 0);
            const ax = axis.applyQuaternion(this.j6.getWorldQuaternion(TMPq));
            // near-horizontal grips: jaws can roll to the part's narrow side —
            // the raw AABB projection overestimates cylinders by √2 on diagonal
            // approaches and falsely reports "too wide to grip"
            const halfW = Math.abs(ax.y) < 0.5
                ? Math.min(TMPa.x, TMPa.z) / 2
                : (Math.abs(ax.x) * TMPa.x + Math.abs(ax.y) * TMPa.y + Math.abs(ax.z) * TMPa.z) / 2;
            if (this._hand) {
                // invert the exact aperture table (monotonic decreasing in curl)
                const T = this._apTable, target = halfW + this._handSkin;
                if (target >= T[0]) return 1;                 // wider than the open hand
                for (let i = 1; i < T.length; i++) {
                    if (T[i] <= target) {
                        const c = (i - 1 + (T[i - 1] - target) / Math.max(1e-6, T[i - 1] - T[i])) / (T.length - 1);
                        return Math.max(0, Math.min(1, 1 - c));
                    }
                }
                return 0;
            }
            const sep = halfW + this._padInset;              // aperture with pads on the surface
            return Math.max(0, Math.min(1, (sep - this._jawClosed) / (this._jawOpen - this._jawClosed)));
        }

        /** carry an object with the gripper (parents it to the tool, restores on release) */
        grab(obj) {
            if (!obj || this._carried) return;
            this._carried = { obj, parent: obj.parent };
            this.toolTip.attach(obj);
            // real jaws CENTER the part as they close — correct HORIZONTAL
            // offset (capped) so a moving-base grab doesn't carry the part
            // outside the claw. Vertical stays (the part was resting);
            // hands skip it (their grasp cage is not at the toolTip).
            if (!this._hand) {
                const c = new THREE.Box3().setFromObject(obj).getCenter(TMPa);
                const gp = this.getToolTip(TMPb);
                const d = gp.sub(c);
                d.y = 0;
                const cap = this.toolLen * 0.6;
                if (d.length() > cap) d.setLength(cap);
                if (d.lengthSq() > 1e-8) {
                    this.toolTip.getWorldQuaternion(TMPq).invert();
                    obj.position.add(d.applyQuaternion(TMPq));
                }
            }
        }
        release() {
            if (!this._carried) return;
            const { obj, parent } = this._carried;
            (parent || this.group.parent || this.group).attach(obj);
            this._carried = null;
        }

        /** looped pick-from → carry → place-at program */
        pickAndPlace({ from, to, period = 4, liftH = 0.45, payload = null, roundTrip = false }) {
            // the payload is robot-managed (carried mid-air by design)
            if (payload) payload.userData.noSupportCheck = true;
            this._program = { kind: 'pnp', from: V(...from), to: V(...to), period, liftH, payload, roundTrip, t0: null };
            return this;
        }
        /** free-run a target function: fn(t) -> Vector3 */
        follow(fn) { this._program = { kind: 'follow', fn }; return this; }

        update(t, dt) {
            const P = this._program;
            if (P && P.kind === 'follow') {
                this.reachTo(P.fn(t), dt);
            } else if (P && P.kind === 'pnp') {
                if (P.t0 === null) {
                    P.t0 = t;
                    if (P.payload) {
                        P._home = P.payload.getWorldPosition(new THREE.Vector3());
                        P._homeQ = P.payload.getWorldQuaternion(new THREE.Quaternion());
                    }
                }
                // approach first: hold the cycle clock until the tool has
                // actually ARRIVED over the pick station (a real cell homes
                // to the pick point before its cycle starts)
                if (!P._engaged) {
                    P.t0 = t;
                    this.setGrip(1);
                    const hover = TMPc.set(P.from.x, P.from.y + P.liftH, P.from.z);
                    if (this.getToolTip(TMPd).distanceTo(hover) < this.toolLen * 0.6) P._engaged = true;
                    this.reachTo(hover, dt);
                    this._applyGripPose();
                    return;
                }
                let u = ((t - P.t0) % P.period) / P.period;
                // moving-base robustness: HOLD the cycle clock at the two
                // co-location phases (close@from, open@to) until the tool has
                // physically arrived — a drifting base otherwise grabs at an
                // offset or releases mid-air because phases are clock-driven
                if (P.payload) {
                    const tipD = this.getToolTip(TMPd);
                    if (u > 0.14 && u < 0.28 && !this._carried && tipD.distanceTo(P.from) > this.toolLen * 1.2) P.t0 += dt;
                    else if (u > 0.58 && u < 0.7 && this._carried && tipD.distanceTo(P.to) > this.toolLen * 1.2) P.t0 += dt;
                    u = ((t - P.t0) % P.period) / P.period;
                }
                // cycle wrapped with the part left at 'to':
                //  roundTrip — swap stations and CARRY IT BACK next cycle;
                //  otherwise — present a fresh part at the pick station
                if (P.payload && P._lastU !== undefined && u < P._lastU && !this._carried) {
                    if (P.roundTrip) {
                        const tmp = P.from; P.from = P.to; P.to = tmp;
                    } else {
                        const pl = P.payload;
                        pl.position.copy(P._home);
                        pl.quaternion.copy(P._homeQ);
                        if (pl.parent) {
                            pl.parent.worldToLocal(pl.position);
                            pl.quaternion.premultiply(pl.parent.getWorldQuaternion(TMPq).invert());
                        }
                    }
                }
                P._lastU = u;
                const lift = (p, h) => TMPc.set(p.x, p.y + h, p.z);
                let target, grip;
                if (u < 0.18) { target = lift(P.from, P.liftH * (1 - u / 0.18)); grip = 1; }              // descend
                else if (u < 0.28) { target = P.from; grip = 1 - (u - 0.18) / 0.10; }                     // close
                else if (u < 0.62) {                                                                       // carry
                    const s = (u - 0.28) / 0.34, e = s * s * (3 - 2 * s);
                    target = TMPc.copy(P.from).lerp(P.to, e); target.y += Math.sin(s * Math.PI) * P.liftH;
                    grip = 0;
                } else if (u < 0.7) { target = P.to; grip = (u - 0.62) / 0.08; }                           // open
                else if (u < 0.78) {                                                                       // depart VERTICALLY off the part, hand open
                    target = lift(P.to, P.liftH * 0.5 * (u - 0.7) / 0.08); grip = 1;
                } else {                                                                                   // return
                    const s = (u - 0.78) / 0.22, e = s * s * (3 - 2 * s);
                    if (P.roundTrip) {
                        // next pick is HERE — just hover above the drop point
                        target = lift(P.to, P.liftH * (0.5 + 0.5 * e));
                    } else {
                        target = TMPc.copy(P.to).lerp(P.from, e);
                        target.y += P.liftH * (0.5 * (1 - e) + Math.sin(s * Math.PI) * 0.5);
                    }
                    grip = 1;
                }
                if (P.payload) {
                    // jaws stop AT the part's surface (contact), and the part
                    // is only picked once the pads actually reach it
                    const contact = this._contactGrip(P.payload);
                    if (globalThis.__robotDebug && (this._dbgN = (this._dbgN || 0) + 1) % 15 === 0) {
                        const tip = this.getToolTip(TMPd);
                        const pp = P.payload.getWorldPosition(TMPb);
                        console.log(`[pnp ${this.group.name}] u=${u.toFixed(2)} grip=${grip.toFixed(2)} contact=${contact.toFixed(2)} tip=(${tip.x.toFixed(2)},${tip.y.toFixed(2)},${tip.z.toFixed(2)}) part=(${pp.x.toFixed(2)},${pp.y.toFixed(2)},${pp.z.toFixed(2)}) dist=${tip.distanceTo(pp).toFixed(3)} carried=${!!this._carried}`);
                    }
                    if (this._carried) {
                        // freeze the aperture at the grab-time width — the
                        // live estimate inflates as the tool axis rotates
                        if (grip < this._carriedContact) grip = this._carriedContact;
                        else if (grip > Math.min(0.96, this._carriedContact + 0.04)) this.release();
                        // (capped: a tilted re-grab can measure contact ~0.97,
                        // making cc+0.04 > 1 — an unreachable release = forever-carry)
                    } else if (grip <= contact + 0.02) {
                        // proximity guard: only pick when the tool is actually AT the part
                        const near = this.getToolTip(TMPd).distanceTo(P.payload.getWorldPosition(TMPb)) < this.toolLen * 1.3;
                        if (contact >= 0.98) {
                            if (near && !P._fitWarned) {
                                P._fitWarned = true;
                                console.warn('[robotics_kit] pickAndPlace payload is wider than the tool opening — it will never be gripped. Shrink the part or use a bigger reach/tool.');
                            }
                        } else {
                            grip = contact;
                            if (near) { this.grab(P.payload); this._carriedContact = contact; }
                        }
                    }
                }
                this.setGrip(grip);
                this.reachTo(target, dt);
            } else if (this._target) {
                this.reachTo(this._target, dt);
            }
            this._applyGripPose();
        }

        _applyGripPose() {
            // jaw carriages slide their rail toward the current grip separation
            if (this._fingers.length) {
                const sep = this._jawClosed + (this._jawOpen - this._jawClosed) * this._grip;
                for (const f of this._fingers) f.position.x = f.userData.side * sep;
            }
            // humanoid hand: distribute the curl over the phalanges
            // (proximal most, distal least — natural power-grasp shape)
            if (this._hand) {
                // MUST match the _apTable angles exactly (contact accuracy)
                const c = 1 - this._grip;
                for (const f of this._hand.fingers) {
                    f.j[0].rotation.x = -0.45 + c * 1.3;
                    f.j[1].rotation.x = c * 0.85;
                    f.j[2].rotation.x = c * 0.55;
                }
                const th = this._hand.thumb;
                th.j[0].rotation.x = 0.35 - c * 0.95;
                th.j[1].rotation.x = -c * 0.6;
            }
        }
        mounts() { return { base: this.group, flange: this.j6, tip: this.toolTip }; }
        mountPoint() { return this.j6; }
    }

    // ════════════════════════════════════════════════════════════════════
    // Delta picker — 3 towers at 120°, closed-form IK, parallelogram
    // forearms. Hangs from a frame; effector plate below.
    // ════════════════════════════════════════════════════════════════════
    class Delta {
        constructor(opts = {}) {
            this.opts = opts;
            this.rf = opts.upperArm ?? 0.42;     // servo horn
            this.re = opts.forearm ?? 0.95;      // parallelogram rods
            this.f = opts.baseRadius ?? 0.35;    // base joint circle radius
            this.e = opts.effectorRadius ?? 0.11;
            this.maxRate = opts.maxRate ?? 5.0;
            const body = bodyMat(opts, 0xe8e4dc, 0.35, 0.7);
            const dark = accentMat(opts, 0x22262c, 0.45, 0.8);
            this.materials = { body, dark };

            const g = this.group = new THREE.Group();
            g.name = 'robot_delta';
            if (opts.position) g.position.fromArray(opts.position);   // the BASE plate origin (hangs downward)

            const plate = new THREE.Mesh(new THREE.CylinderGeometry(this.f * 1.5, this.f * 1.5, 0.07, 24), dark);
            plate.castShadow = true; g.add(plate);
            this.horns = []; this.rods = []; this.hornTips = [];
            for (let i = 0; i < 3; i++) {
                const phi = (i / 3) * Math.PI * 2;
                const piv = new THREE.Group();
                piv.position.set(Math.cos(phi) * this.f, 0, Math.sin(phi) * this.f);
                piv.rotation.y = -phi;            // local +X points OUTWARD along the tower azimuth
                g.add(piv);
                const servo = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.12, 0.18), dark);
                piv.add(servo);
                // drive motor can standing on the base plate above each servo
                const can = new THREE.Mesh(new THREE.CylinderGeometry(0.042, 0.048, 0.1, 12), dark);
                can.position.y = 0.115; can.castShadow = true; piv.add(can);
                const hornPiv = new THREE.Group(); piv.add(hornPiv);
                const horn = new THREE.Mesh(new THREE.CapsuleGeometry(0.035, this.rf - 0.07, 4, 8), body);
                horn.rotation.z = Math.PI / 2;    // capsule y → +X
                horn.position.x = this.rf / 2;
                horn.castShadow = true;
                hornPiv.add(horn);
                const tip = new THREE.Group(); tip.position.x = this.rf; hornPiv.add(tip);
                const tipBall = new THREE.Mesh(new THREE.SphereGeometry(0.028, 8, 6), dark);
                tip.add(tipBall);                          // ball joint at the horn end
                this.horns.push(hornPiv); this.hornTips.push(tip);
                // parallelogram rod PAIR (unit cylinders re-linked per frame)
                const pair = [];
                for (const sd of [-1, 1]) {
                    const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.016, 1, 6), body);
                    rod.castShadow = true;
                    g.add(rod);
                    pair.push({ rod, sd });
                }
                this.rods.push(pair);
            }
            this.plateMesh = new THREE.Mesh(new THREE.CylinderGeometry(this.e * 1.6, this.e * 1.6, 0.045, 16), dark);
            this.plateMesh.castShadow = true;
            g.add(this.plateMesh);
            this.tool = new THREE.Mesh(new THREE.ConeGeometry(0.045, 0.16, 10), body);
            this.tool.rotation.x = Math.PI;
            g.add(this.tool);
            this.plateFrame = new THREE.Group();      // rides the moving effector plate
            g.add(this.plateFrame);
            // sagging umbilical: base center → plate (stretched coil, no rebuild)
            if (globalThis.MechParts) {
                this.umbilical = globalThis.MechParts.hoseCoil({ turns: 3, coilR: 0.028, len: 1, tubeR: 0.006 });
                g.add(this.umbilical);
            }

            this.pos = V(0, -this.re * 0.75, 0);      // effector in BASE-plate local space (y down)
            this.target = this.pos.clone();
            this.theta = [0.5, 0.5, 0.5];
            this._program = null;
        }

        // canonical delta IK: solve one tower (frame with tower along +X)
        _angle(x0, y0, z0) {
            const y1 = -this.e;                      // effector joint pulled toward center
            y0 -= 0;                                  // y is DOWNWARD distance here (positive down)
            // work in the tower plane: horn pivot at (this.f, 0); solve circle intersection
            const a = (x0 * x0 + y0 * y0 + z0 * z0 + this.rf * this.rf - this.re * this.re - this.f * this.f + this.e * this.e - 2 * this.e * x0 + 2 * this.f * x0 - 2 * this.f * this.e) ;
            // Use the standard two-circle solution in the (x, y) tower plane:
            const xJ = x0 - this.e;                  // effector joint x in tower frame (toward tower)
            const dxp = xJ - this.f;                 // horizontal offset horn-pivot → effector joint
            const L = Math.hypot(dxp, y0);
            const Lr = Math.hypot(L, z0);            // include out-of-plane for forearm reach
            const cosB = (this.rf * this.rf + L * L - (this.re * this.re - z0 * z0)) / (2 * this.rf * L);
            if (cosB < -1 || cosB > 1 || (this.re * this.re - z0 * z0) < 0) return null;
            const B = Math.acos(cosB);
            const phi = Math.atan2(y0, dxp);         // angle of the pivot→joint line (y down positive)
            return phi - B;                          // horn angle below horizontal
        }

        moveTo(x, y, z) { this.target.set(x, y, z); }
        pickLoop({ radius = 0.4, floorY = null, period = 1.2 } = {}) {
            const dropY = -(this.re * 0.92);
            const upY = -(this.re * 0.55);
            this._program = (t) => {
                const u = (t % period) / period;
                const k = Math.floor(t / period) * 2.399;     // golden-angle scatter
                const px = Math.cos(k) * radius, pz = Math.sin(k) * radius;
                if (u < 0.25) return V(px, upY + (dropY - upY) * (u / 0.25), pz);
                if (u < 0.4) return V(px, dropY, pz);
                if (u < 0.65) { const s = (u - 0.4) / 0.25; return V(px * (1 - s), upY + Math.sin(s * Math.PI) * -0.05, pz * (1 - s)); }
                if (u < 0.8) return V(0, dropY * 0.92, 0);
                const s = (u - 0.8) / 0.2; return V(px * s * 0.2, upY, pz * s * 0.2);
            };
            return this;
        }

        update(t, dt) {
            if (this._program) this.target.copy(this._program(t));
            // slew the effector, then closed-form the horns
            const PV = this._pv || (this._pv = { x: 0, y: 0, z: 0 });
            let sr;
            sr = springStep(this.pos.x, PV.x, this.target.x, this.maxRate * 0.6, dt); this.pos.x = sr[0]; PV.x = sr[1];
            sr = springStep(this.pos.y, PV.y, this.target.y, this.maxRate * 0.6, dt); this.pos.y = sr[0]; PV.y = sr[1];
            sr = springStep(this.pos.z, PV.z, this.target.z, this.maxRate * 0.6, dt); this.pos.z = sr[0]; PV.z = sr[1];
            const p = this.pos;
            for (let i = 0; i < 3; i++) {
                const phi = (i / 3) * Math.PI * 2;
                // rotate effector position into tower frame (tower along +X)
                const c = Math.cos(phi), s = Math.sin(phi);
                const x0 = p.x * c + p.z * s;
                const z0 = -p.x * s + p.z * c;
                const th = this._angle(x0, -p.y, z0);
                if (th !== null) this.theta[i] = th;
                this.horns[i].rotation.z = -this.theta[i];
            }
            // place plate + parallelogram rods
            this.plateMesh.position.copy(p);
            this.plateFrame.position.copy(p);
            this.tool.position.set(p.x, p.y - 0.1, p.z);
            for (let i = 0; i < 3; i++) {
                const phi = (i / 3) * Math.PI * 2;
                const c = Math.cos(phi), s = Math.sin(phi);
                const tipW = this.hornTips[i].getWorldPosition(TMPa);
                for (const { rod, sd } of this.rods[i]) {
                    // parallelogram: offset both ends perpendicular to the tower
                    const off = TMPb.set(-s, 0, c).multiplyScalar(sd * 0.035);
                    const a2 = TMPc.copy(tipW).add(off);
                    const endLocal = V(p.x + c * this.e + off.x, p.y, p.z + s * this.e + off.z);
                    const endW = this.group.localToWorld(endLocal);
                    linkBetween(rod, a2, endW);
                }
            }
            if (this.umbilical) {
                const a = this.group.localToWorld(TMPa.set(0, -0.05, 0));
                const b = this.group.localToWorld(TMPb.set(p.x, p.y + 0.03, p.z));
                linkBetween(this.umbilical, a, b);
            }
        }
        mounts() { return { frame: this.group, plate: this.plateFrame }; }
        mountPoint() { return this.plateFrame; }
    }

    // ════════════════════════════════════════════════════════════════════
    // Kossel — LINEAR delta 3D printer. No elbows anywhere: three vertical
    // towers with SLIDING CARRIAGES, rigid rod pairs carriage→effector,
    // integrated build plate, spool on the crown, bowden tube down to the
    // hotend (the only thing connecting the effector to the top). moveTo()
    // targets group-local coords, y up from the floor.
    // ════════════════════════════════════════════════════════════════════
    class Kossel {
        constructor(opts = {}) {
            this.opts = opts;
            const R = this.R = opts.radius ?? 0.42;         // tower circle radius
            const H = this.H = opts.height ?? 1.2;          // tower height
            this.rodL = opts.rod ?? R * 1.6;                // rod length
            this.e = opts.effectorRadius ?? 0.07;
            this.maxRate = opts.maxRate ?? 3.5;
            const body = bodyMat(opts, 0x8a94a0, 0.35, 0.85);
            const dark = accentMat(opts, 0x22262c, 0.5, 0.7);
            const chrome = metal(0xd8dce2, 0.2, 0.95);
            const brass = metal(0xc9a44a, 0.35, 0.9);
            this.materials = { body, dark, chrome };
            const MP = globalThis.MechParts;
            const cb = (w, h, d, c, m) => {
                const mesh = MP ? MP.chamferedBox(w, h, d, c, m) : new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
                mesh.castShadow = true; return mesh;
            };
            const g = this.group = new THREE.Group();
            g.name = 'robot_kossel';
            if (opts.position) g.position.fromArray(opts.position);

            this.carriages = [];
            this.rods = [];
            this._tw = [];                                   // tower base xz
            for (let i = 0; i < 3; i++) {
                const phi = (i / 3) * Math.PI * 2;
                const tx = Math.cos(phi) * R, tz = Math.sin(phi) * R;
                this._tw.push([tx, tz, phi]);
                const col = cb(0.075, H, 0.09, 0.012, dark);
                col.position.set(tx, H / 2, tz);
                col.rotation.y = -phi; g.add(col);
                const foot = cb(0.16, 0.035, 0.2, 0.01, dark);
                foot.position.set(tx, 0.018, tz); foot.rotation.y = -phi; g.add(foot);
                // sliding carriage: block + two roller hints, faces center
                const car = new THREE.Group();
                car.position.set(tx, H * 0.6, tz); car.rotation.y = -phi;
                const block = cb(0.11, 0.13, 0.05, 0.012, body);
                block.position.x = -0.07;                    // rides the rail's inner face
                car.add(block);
                for (const sy of [-1, 1]) {
                    const roller = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.02, 10), chrome);
                    roller.rotation.z = Math.PI / 2;
                    roller.position.set(-0.02, sy * 0.045, 0); car.add(roller);
                }
                g.add(car); this.carriages.push(car);
                // parallelogram rod PAIR (unit cylinders re-linked per frame)
                const pair = [];
                for (const sd of [-1, 1]) {
                    const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 1, 6), chrome);
                    rod.castShadow = true; g.add(rod);
                    pair.push({ rod, sd });
                }
                this.rods.push(pair);
            }
            // base triangle + top crown beams between tower tops
            for (let i = 0; i < 3; i++) {
                const [ax, az] = this._tw[i], [bx, bz] = this._tw[(i + 1) % 3];
                for (const y of [0.05, H - 0.05]) {
                    const len = Math.hypot(bx - ax, bz - az);
                    const beam = cb(len - 0.06, 0.07, 0.05, 0.01, body);
                    beam.position.set((ax + bx) / 2, y, (az + bz) / 2);
                    beam.rotation.y = -Math.atan2(bz - az, bx - ax);
                    g.add(beam);
                }
            }
            // integrated BUILD PLATE: dark heated disc + rim + leveling knobs
            const plateR = R * 0.78;
            const plate = new THREE.Mesh(new THREE.CylinderGeometry(plateR, plateR, 0.035, 28), dark);
            plate.position.y = 0.085; plate.castShadow = true; g.add(plate);
            const rim = new THREE.Mesh(new THREE.CylinderGeometry(plateR + 0.025, plateR + 0.03, 0.018, 28), body);
            rim.position.y = 0.07; g.add(rim);
            for (let i = 0; i < 3; i++) {
                const phi = (i / 3) * Math.PI * 2 + Math.PI / 3;
                const knob = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.018, 0.016, 10), brass);
                knob.position.set(Math.cos(phi) * (plateR - 0.04), 0.11, Math.sin(phi) * (plateR - 0.04));
                g.add(knob);
            }
            this.plateTop = 0.085 + 0.0175;
            // SPOOL on the crown + hub the bowden drops from
            const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.11, 0.05, 12), dark);
            hub.position.y = H - 0.02; g.add(hub);
            // filament SPOOL: a vertical wheel on a horizontal axle on a
            // crown bracket (a flat unheld torus reads as a hovering halo)
            const post = cb(0.05, 0.12, 0.05, 0.008, dark);
            post.position.set(0, H + 0.06, 0); g.add(post);
            const axle = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.16, 8), chrome);
            axle.rotation.z = Math.PI / 2;
            axle.position.set(0, H + 0.14, 0); g.add(axle);
            const spoolG = new THREE.Group();
            spoolG.position.set(0, H + 0.14, 0);
            spoolG.rotation.y = Math.PI / 2;                 // wheel axis along the axle
            for (const sz of [-1, 1]) {
                const flange = new THREE.Mesh(new THREE.CylinderGeometry(0.125, 0.125, 0.012, 20), dark);
                flange.rotation.x = Math.PI / 2;
                flange.position.z = sz * 0.05; flange.castShadow = true; spoolG.add(flange);
            }
            const wind = new THREE.Mesh(new THREE.TorusGeometry(0.082, 0.034, 10, 22), bodyMat(opts, opts.filament ?? 0x2fa84f, 0.5, 0.1));
            wind.castShadow = true; spoolG.add(wind);
            g.add(spoolG);
            this.spool = spoolG;
            // effector: round plate + hotend (fins, heater, brass nozzle)
            this.plateFrame = new THREE.Group(); g.add(this.plateFrame);
            const eff = new THREE.Mesh(new THREE.CylinderGeometry(this.e * 1.5, this.e * 1.5, 0.02, 12), dark);
            this.plateFrame.add(eff);
            for (let i = 0; i < 3; i++) {
                const fin = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.006, 10), chrome);
                fin.position.y = -0.02 - i * 0.012; this.plateFrame.add(fin);
            }
            const heat = cb(0.045, 0.03, 0.045, 0.006, dark);
            heat.position.y = -0.065; this.plateFrame.add(heat);
            const noz = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.012, 0.025, 8), brass);
            noz.position.y = -0.092; this.plateFrame.add(noz);
            this.nozzleTip = 0.105;                          // effector origin -> nozzle tip drop
            // bowden tube: hub -> effector (the ONLY top connection)
            this.bowden = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 1, 6), accentMat(opts, 0x111111, 0.6, 0.2));
            g.add(this.bowden);

            this.pos = V(0, H * 0.55, 0);                    // effector target, group-local
            this.target = this.pos.clone();
        }

        moveTo(x, y, z) { this.target.set(x, y, z); }

        update(t, dt) {
            const PV = this._pv || (this._pv = { x: 0, y: 0, z: 0 });
            let sr;
            sr = springStep(this.pos.x, PV.x, this.target.x, this.maxRate * 0.6, dt); this.pos.x = sr[0]; PV.x = sr[1];
            sr = springStep(this.pos.y, PV.y, this.target.y, this.maxRate * 0.6, dt); this.pos.y = sr[0]; PV.y = sr[1];
            sr = springStep(this.pos.z, PV.z, this.target.z, this.maxRate * 0.6, dt); this.pos.z = sr[0]; PV.z = sr[1];
            const p = this.pos;
            this.plateFrame.position.copy(p);
            for (let i = 0; i < 3; i++) {
                const [tx, tz, phi] = this._tw[i];
                // linear delta IK: carriage height so the rigid rod reaches
                // the effector joint (offset e toward the tower's azimuth)
                const jx = p.x + Math.cos(phi) * this.e;
                const jz = p.z + Math.sin(phi) * this.e;
                const dx = tx - jx, dz = tz - jz;
                const h2 = this.rodL * this.rodL - dx * dx - dz * dz;
                const cy = p.y + (h2 > 0 ? Math.sqrt(h2) : this.rodL * 0.5);
                this.carriages[i].position.y = Math.min(this.H - 0.1, Math.max(0.12, cy));
                // rod pair: carriage -> effector joint, parallelogram offset
                const perp = TMPb.set(-Math.sin(phi), 0, Math.cos(phi));
                for (const { rod, sd } of this.rods[i]) {
                    const off = TMPc.copy(perp).multiplyScalar(sd * 0.028);
                    const a = TMPa.set(tx + off.x - Math.cos(phi) * 0.07, this.carriages[i].position.y, tz + off.z - Math.sin(phi) * 0.07);
                    const b = V(jx + off.x, p.y, jz + off.z);
                    linkBetween(rod, this.group.localToWorld(a.clone()), this.group.localToWorld(b));
                }
            }
            // bowden: crown hub down to the effector
            const a = this.group.localToWorld(V(0, this.H - 0.04, 0));
            const b = this.group.localToWorld(V(p.x, p.y + 0.02, p.z));
            linkBetween(this.bowden, a, b);
            this.spool.rotation.z += 0.4 * (dt ?? 1 / 30);
        }
        mounts() { return { frame: this.group, effector: this.plateFrame }; }
        mountPoint() { return this.plateFrame; }
    }

    // ════════════════════════════════════════════════════════════════════
    // Stewart platform — 6 two-part pistons between staggered anchor rings;
    // closed-form leg lengths from the platform pose.
    // ════════════════════════════════════════════════════════════════════
    class Stewart {
        constructor(opts = {}) {
            this.opts = opts;
            const rB = this.rB = opts.baseRadius ?? 0.55;
            const rT = this.rT = opts.topRadius ?? 0.34;
            this.h0 = opts.height ?? 0.55;
            const body = bodyMat(opts, 0x8a94a0, 0.35, 0.85);
            const dark = accentMat(opts, 0x22262c, 0.5, 0.7);
            const chrome = metal(0xd8dce2, 0.2, 0.95);
            this.materials = { body, dark, chrome };
            const g = this.group = new THREE.Group();
            g.name = 'robot_stewart';
            if (opts.position) g.position.fromArray(opts.position);

            const base = new THREE.Mesh(new THREE.CylinderGeometry(rB * 1.15, rB * 1.25, 0.08, 24), dark);
            base.position.y = 0.04; base.castShadow = true; g.add(base);
            this.top = new THREE.Group(); this.top.position.y = this.h0; g.add(this.top);
            const topPlate = new THREE.Mesh(new THREE.CylinderGeometry(rT * 1.2, rT * 1.2, 0.06, 24), body);
            topPlate.castShadow = true; this.top.add(topPlate);

            // anchor rings: pairs clustered near alternating azimuths (real
            // hexapod geometry) — base pairs at 0/120/240, top pairs at 60/180/300
            this.baseA = []; this.topA = [];
            for (let i = 0; i < 6; i++) {
                const k = Math.floor(i / 2), sd = i % 2 ? 1 : -1;
                const aB = (k / 3) * Math.PI * 2 + sd * 0.28;
                const aT = (k / 3) * Math.PI * 2 + (Math.PI / 3) - sd * 0.28;
                this.baseA.push(V(Math.cos(aB) * rB, 0.08, Math.sin(aB) * rB));
                this.topA.push(V(Math.cos(aT) * rT, -0.03, Math.sin(aT) * rT));
                const ball = new THREE.Mesh(new THREE.SphereGeometry(0.045, 10, 8), dark);
                ball.position.copy(this.baseA[i]); g.add(ball);
                const ball2 = new THREE.Mesh(new THREE.SphereGeometry(0.038, 10, 8), dark);
                ball2.position.copy(this.topA[i]); this.top.add(ball2);
            }
            // two-part pistons: sleeve (lower half, fatter) + rod (upper, thin)
            this.pistons = [];
            for (let i = 0; i < 6; i++) {
                const sleeve = new THREE.Mesh(new THREE.CylinderGeometry(0.042, 0.042, 1, 10), body);
                const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 1, 8), chrome);
                sleeve.castShadow = rod.castShadow = true;
                g.add(sleeve); g.add(rod);
                this.pistons.push({ sleeve, rod });
            }
            this.pose = { x: 0, y: this.h0, z: 0, rx: 0, ry: 0, rz: 0 };
            this.target = { ...this.pose };
            this._demo = opts.demo ?? null;
        }
        setPose(p) { Object.assign(this.target, p); }
        update(t, dt) {
            if (this._demo === 'wobble') {
                this.setPose({ x: Math.sin(t * 0.9) * 0.08, z: Math.cos(t * 1.3) * 0.08, y: this.h0 + Math.sin(t * 0.6) * 0.05,
                    rx: Math.sin(t * 1.1) * 0.16, rz: Math.cos(t * 0.8) * 0.16, ry: Math.sin(t * 0.4) * 0.2 });
            }
            for (const k of Object.keys(this.pose)) this.pose[k] = slew(this.pose[k], this.target[k], 1.2, dt);
            this.top.position.set(this.pose.x, this.pose.y, this.pose.z);
            this.top.rotation.set(this.pose.rx, this.pose.ry, this.pose.rz);
            this.top.updateMatrixWorld(true);
            for (let i = 0; i < 6; i++) {
                const aW = this.group.localToWorld(TMPa.copy(this.baseA[i]));
                const bW = this.top.localToWorld(TMPb.copy(this.topA[i]));
                // sleeve = lower 55% from base anchor; rod = full span (slides inside)
                const mid = TMPc.copy(aW).lerp(bW, 0.55);
                linkBetween(this.pistons[i].sleeve, aW, mid);
                linkBetween(this.pistons[i].rod, aW, bW);
            }
        }
        mounts() { return { base: this.group, top: this.top }; }
        mountPoint() { return this.top; }
    }

    // ════════════════════════════════════════════════════════════════════
    // Pan-tilt turret — slew-limited aim, sensor head.
    // ════════════════════════════════════════════════════════════════════
    class Turret {
        constructor(opts = {}) {
            this.opts = opts;
            const s = opts.scale ?? 1;
            this.maxRate = opts.maxRate ?? 1.8;
            const body = bodyMat(opts, 0x5a6470, 0.4, 0.8);
            const dark = accentMat(opts, 0x1c2026, 0.5, 0.7);
            this.materials = { body, dark };
            const g = this.group = new THREE.Group();
            g.name = 'robot_turret';
            if (opts.position) g.position.fromArray(opts.position);
            const base = new THREE.Mesh(new THREE.CylinderGeometry(0.28 * s, 0.34 * s, 0.3 * s, 16), dark);
            base.position.y = 0.15 * s; base.castShadow = true; g.add(base);
            boltRing(g, 0.34 * s, 0.02, 6, body);
            this.yawG = new THREE.Group(); this.yawG.position.y = 0.3 * s; g.add(this.yawG);
            // U-fork yoke: two plates flanking the pitch axis with pivot caps
            // (a single-arm pivot reads cheap — real pan-tilts fork)
            const MPt = globalThis.MechParts;
            for (const sd of [-1, 1]) {
                const plate = MPt
                    ? MPt.chamferedBox(0.05 * s, 0.28 * s, 0.24 * s, 0.012 * s, body)
                    : new THREE.Mesh(new THREE.BoxGeometry(0.05 * s, 0.28 * s, 0.24 * s), body);
                plate.position.set(sd * 0.155 * s, 0.13 * s, 0);
                this.yawG.add(plate);
                const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.055 * s, 0.055 * s, 0.02 * s, 14), dark);
                cap.rotation.z = Math.PI / 2; cap.position.set(sd * 0.19 * s, 0.16 * s, 0);
                this.yawG.add(cap);
            }
            const bridge = new THREE.Mesh(new THREE.BoxGeometry(0.31 * s, 0.06 * s, 0.2 * s), body);
            bridge.position.y = 0.015 * s; bridge.castShadow = true; this.yawG.add(bridge);
            this.pitchG = new THREE.Group(); this.pitchG.position.y = 0.16 * s; this.yawG.add(this.pitchG);
            const headBox = MPt
                ? MPt.chamferedBox(0.22 * s, 0.16 * s, 0.22 * s, 0.015 * s, dark)
                : new THREE.Mesh(new THREE.BoxGeometry(0.22 * s, 0.16 * s, 0.22 * s), dark);
            headBox.castShadow = true; this.pitchG.add(headBox);
            const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.05 * s, 0.07 * s, 0.5 * s, 10), dark);
            barrel.rotation.x = Math.PI / 2; barrel.position.z = 0.3 * s; barrel.castShadow = true;
            this.pitchG.add(barrel);
            const lens = new THREE.Mesh(new THREE.CylinderGeometry(0.075 * s, 0.075 * s, 0.05 * s, 12),
                new THREE.MeshStandardNodeMaterial({ color: 0x101418, roughness: 0.15, emissive: new THREE.Color(opts.eyeColor ?? 0xff3020), emissiveIntensity: 1.4 }));
            lens.rotation.x = Math.PI / 2; lens.position.z = 0.56 * s;
            this.pitchG.add(lens);
            this.yaw = 0; this.pitch = 0;
            this._track = null;
        }
        aimAt(worldPos, dt = 1 / 30) {
            const o = this.pitchG.getWorldPosition(TMPa);
            const d = TMPb.copy(worldPos).sub(o);
            const gy = this.group.getWorldQuaternion(TMPq);        // account for a rotated mount
            d.applyQuaternion(gy.invert());
            const wantYaw = Math.atan2(d.x, d.z);
            const wantPitch = Math.atan2(d.y, Math.hypot(d.x, d.z));
            const PV = this._pv || (this._pv = { y: 0, p: 0 });
            let sr;
            sr = springAngle(this.yaw, PV.y, wantYaw, this.maxRate, dt); this.yaw = sr[0]; PV.y = sr[1];
            sr = springStep(this.pitch, PV.p, Math.max(-0.5, Math.min(0.9, wantPitch)), this.maxRate, dt); this.pitch = sr[0]; PV.p = sr[1];
            this.yawG.rotation.y = this.yaw;
            this.pitchG.rotation.x = -this.pitch;
        }
        track(fn) { this._track = fn; return this; }
        update(t, dt) {
            if (this._track) { const p = this._track(t); if (p) this.aimAt(p, dt); }
            else this.aimAt(TMPc.set(Math.sin(t * 0.4) * 5, 1, Math.cos(t * 0.4) * 5).add(this.group.position), dt);
        }
        mounts() { return { base: this.group, head: this.yawG, barrel: this.pitchG }; }
        mountPoint() { return this.yawG; }
    }

    // ════════════════════════════════════════════════════════════════════
    // AGV — differential-drive base: chassis, four wheels that actually
    // roll, sensor mast, strobing beacon. driveTo/patrol.
    // ════════════════════════════════════════════════════════════════════
    class AGV {
        constructor(opts = {}) {
            this.opts = opts;
            const s = this.s = opts.scale ?? 1;
            this.speed = opts.speed ?? 0.9;
            this.turnRate = opts.turnRate ?? 1.6;
            const body = bodyMat(opts, 0xc9a12a, 0.45, 0.6);
            const dark = accentMat(opts, 0x22262c, 0.5, 0.7);
            this.materials = { body, dark };
            const g = this.group = new THREE.Group();
            g.name = 'robot_agv';
            if (opts.position) g.position.fromArray(opts.position);
            const MPa = globalThis.MechParts;
            const chassis = MPa
                ? MPa.chamferedBox(0.62 * s, 0.2 * s, 0.9 * s, 0.03 * s, body)
                : new THREE.Mesh(new THREE.BoxGeometry(0.62 * s, 0.2 * s, 0.9 * s), body);
            chassis.position.y = 0.22 * s; g.add(chassis);
            // perimeter bump strip — the black rubber band every real AMR wears
            const bump = new THREE.Mesh(new THREE.BoxGeometry(0.66 * s, 0.055 * s, 0.94 * s), rubber(0x0e0e10));
            bump.position.y = 0.15 * s; g.add(bump);
            const deck = new THREE.Mesh(new THREE.BoxGeometry(0.56 * s, 0.04 * s, 0.82 * s), dark);
            deck.position.y = 0.34 * s; g.add(deck);
            this.deck = new THREE.Group(); this.deck.position.y = 0.36 * s; g.add(this.deck);
            this.wheelR = 0.11 * s;
            this.wheels = [];
            for (const [sx, sz] of [[-1, 1], [1, 1], [-1, -1], [1, -1]]) {
                const w = MPa
                    ? MPa.makeWheel({ r: this.wheelR, width: 0.07 * s, hubR: 0.035 * s, lugCount: 16, lugDepth: 0.008 * s, boltCount: 5 })
                    : (() => { const m = new THREE.Mesh(new THREE.CylinderGeometry(this.wheelR, this.wheelR, 0.07 * s, 14), rubber(0x101010)); m.rotation.z = Math.PI / 2; return m; })();
                // tread lugs add to the rolling radius — ride on the lug tips
                w.position.set(sx * 0.34 * s, this.wheelR + (MPa ? 0.008 * s : 0), sz * 0.3 * s);
                w.castShadow = true;
                g.add(w); this.wheels.push(w);
            }
            // corner lidar puck with emitter band
            const lidar = new THREE.Mesh(new THREE.CylinderGeometry(0.045 * s, 0.05 * s, 0.055 * s, 14), dark);
            lidar.position.set(0.2 * s, 0.4 * s, 0.34 * s); g.add(lidar);
            const band = new THREE.Mesh(new THREE.CylinderGeometry(0.046 * s, 0.046 * s, 0.012 * s, 14),
                new THREE.MeshStandardNodeMaterial({ color: 0x101418, emissive: new THREE.Color(0x30c0ff), emissiveIntensity: 1.2 }));
            band.position.set(0.2 * s, 0.4 * s, 0.34 * s); g.add(band);
            // status LIGHT BAR across the rear deck edge (blink = the beacon)
            this.beacon = new THREE.Mesh(new THREE.BoxGeometry(0.4 * s, 0.022 * s, 0.028 * s),
                new THREE.MeshStandardNodeMaterial({ color: 0x1a0d02, emissive: new THREE.Color(0xff7a10), emissiveIntensity: 2 }));
            this.beacon.position.set(0, 0.375 * s, -0.42 * s); g.add(this.beacon);
            this.heading = opts.heading ?? 0;
            this._route = null; this._ri = 0;
            this._dist = 0;
        }
        getPosition(out) { return (out || new THREE.Vector3()).copy((this.driveGroup || this.group).position); }
        driveTo(x, z) { this._route = [[x, z]]; this._ri = 0; return this; }
        patrol(points) { this._route = points; this._ri = 0; this._loop = true; return this; }
        update(t, dt) {
            this.beacon.material.emissiveIntensity = 1 + Math.abs(Math.sin(t * 5)) * 2.2;
            if (!this._route || this._ri >= this._route.length) return;
            const [tx, tz] = this._route[this._ri];
            const dx = tx - this.group.position.x, dz = tz - this.group.position.z;
            const dist = Math.hypot(dx, dz);
            if (dist < 0.15) {
                this._ri++;
                if (this._loop && this._ri >= this._route.length) this._ri = 0;
                return;
            }
            const want = Math.atan2(dx, dz);
            this.heading = slewAngle(this.heading, want, this.turnRate, dt);
            this.group.rotation.y = this.heading;
            // diff drive: only advance when roughly facing the goal
            let dh = Math.abs((want - this.heading) % (Math.PI * 2));
            if (dh > Math.PI) dh = Math.PI * 2 - dh;
            const v = dh < 0.5 ? this.speed : this.speed * 0.15;
            this.group.position.x += Math.sin(this.heading) * v * dt;
            this.group.position.z += Math.cos(this.heading) * v * dt;
            this._dist += v * dt;
            const spin = this._dist / this.wheelR;
            for (const w of this.wheels) w.rotation.x = spin;   // note: with rot.z=π/2 this rolls
        }
        mounts() { return { deck: this.deck, body: this.group }; }
        mountPoint() { return this.deck; }
    }

    // ════════════════════════════════════════════════════════════════════
    // 3-axis gantry — rails + bridge + carriage + Z quill. moveTo in the
    // gantry's local working volume.
    // ════════════════════════════════════════════════════════════════════
    class Gantry {
        constructor(opts = {}) {
            this.opts = opts;
            const W = this.W = opts.width ?? 2.2, D = this.D = opts.depth ?? 1.4, H = this.H = opts.height ?? 1.1;
            const body = bodyMat(opts, 0x3a7a8a, 0.4, 0.7);
            const dark = accentMat(opts, 0x22262c, 0.5, 0.7);
            const chrome = metal(0xd8dce2, 0.2, 0.95);
            this.materials = { body, dark, chrome };
            const g = this.group = new THREE.Group();
            g.name = 'robot_gantry';
            if (opts.position) g.position.fromArray(opts.position);
            const MP = globalThis.MechParts;
            const cb = (w, h, d, c, m) => {
                const mesh = MP ? MP.chamferedBox(w, h, d, c, m) : new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
                mesh.castShadow = true; return mesh;
            };
            // frame: DISTINCT member widths + chamfers (identical coplanar
            // faces on the old box frame z-fought)
            for (const sx of [-1, 1]) {
                const rail = cb(0.09, 0.11, D, 0.015, dark);
                rail.position.set(sx * W / 2, H + 0.02, 0); g.add(rail);
                for (const sz of [-1, 1]) {
                    const leg = cb(0.13, H, 0.13, 0.02, body);
                    leg.position.set(sx * W / 2, H / 2, sz * (D / 2 - 0.065)); g.add(leg);
                    const foot = cb(0.2, 0.03, 0.2, 0.008, dark);
                    foot.position.set(sx * W / 2, 0.015, sz * (D / 2 - 0.065)); g.add(foot);
                    const gusset = cb(0.1, 0.14, 0.05, 0.012, dark);
                    gusset.position.set(sx * W / 2, H - 0.1, sz * (D / 2 - 0.155)); g.add(gusset);
                }
            }
            const brace = cb(W - 0.13, 0.08, 0.06, 0.012, body);
            brace.position.set(0, H * 0.42, -(D / 2 - 0.065)); g.add(brace);
            // control box + stack light on the front-left leg
            const ctl = cb(0.15, 0.22, 0.09, 0.012, dark);
            ctl.position.set(-W / 2 + 0.005, H * 0.6, D / 2 + 0.005); g.add(ctl);
            if (MP) {
                this._stack = MP.stackLight({ s: 0.9 });
                this._stack.group.position.set(-W / 2, H * 0.6 + 0.12, D / 2 + 0.005);
                g.add(this._stack.group);
            }
            // bridge rides the rails on wrap-around SHOES
            this.bridge = new THREE.Group(); this.bridge.position.y = H + 0.155; g.add(this.bridge);
            const beam = cb(W + 0.14, 0.13, 0.15, 0.02, body);
            this.bridge.add(beam);
            for (const sx of [-1, 1]) {
                const shoe = cb(0.17, 0.1, 0.26, 0.015, dark);
                shoe.position.set(sx * W / 2, -0.055, 0); this.bridge.add(shoe);
            }
            this.carriage = new THREE.Group(); this.bridge.add(this.carriage);
            const car = cb(0.22, 0.23, 0.22, 0.02, dark);
            this.carriage.add(car);
            const carPlate = cb(0.25, 0.16, 0.03, 0.01, body);
            carPlate.position.z = 0.11; this.carriage.add(carPlate);
            this.quill = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, H, 10), chrome);
            this.carriage.add(this.quill);
            this.head = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.14, 10), body);
            this.head.rotation.x = Math.PI;
            this.carriage.add(this.head);
            this.p = { x: 0, z: 0, y: H * 0.5 };
            this.target = { ...this.p };
            this._demo = opts.demo ?? null;
        }
        moveTo(x, y, z) { this.target = { x, y, z }; }
        update(t, dt) {
            if (this._stack) this._stack.update(t);
            if (this._demo === 'scan') {
                const u = (t * 0.25) % 2;
                const row = Math.floor((t * 0.25) / 2) % 4;
                this.target.x = (u < 1 ? u : 2 - u) * this.W * 0.7 - this.W * 0.35;
                this.target.z = (row / 3 - 0.5) * this.D * 0.6;
                this.target.y = this.H * (0.35 + 0.15 * Math.sin(t * 2));
            }
            const PV = this._pv || (this._pv = { x: 0, y: 0, z: 0 });
            let sr;
            sr = springStep(this.p.x, PV.x, this.target.x, 0.9, dt); this.p.x = sr[0]; PV.x = sr[1];
            sr = springStep(this.p.z, PV.z, this.target.z, 0.9, dt); this.p.z = sr[0]; PV.z = sr[1];
            sr = springStep(this.p.y, PV.y, this.target.y, 0.7, dt); this.p.y = sr[0]; PV.y = sr[1];
            this.bridge.position.z = this.p.z;
            this.carriage.position.x = this.p.x;
            const drop = this.H + 0.1 - this.p.y;
            // TELESCOPE the quill: it's a fixed H-long cylinder — without the
            // scale it hangs most of its length below the carriage and stabs
            // into whatever sits in the work volume
            this.quill.scale.y = Math.max(0.08, drop + 0.08) / this.H;
            this.quill.position.y = -drop / 2 + 0.04;
            this.head.position.y = -drop;
        }
        mounts() { return { frame: this.group, carriage: this.carriage }; }
        mountPoint() { return this.carriage; }
    }

    // ════════════════════════════════════════════════════════════════════
    // FDM 3D printer — portal frame, bed slides Z (bedslinger), head scans
    // X, the X-gantry rises as the PRINT GROWS on the bed. Bowden tube
    // flexes with the head; the filament spool spins while printing.
    // ════════════════════════════════════════════════════════════════════
    class Printer {
        constructor(opts = {}) {
            this.opts = opts;
            const s = this.s = opts.scale ?? 1;
            const W = this.W = (opts.width ?? 0.62) * s;    // X travel-ish
            const D = this.D = (opts.depth ?? 0.58) * s;
            const H = this.H = (opts.height ?? 0.72) * s;
            const frame = accentMat(opts, 0x1c1c20, 0.55, 0.6);    // black extrusion
            const body = bodyMat(opts, 0xe8862a, 0.5, 0.4);        // orange accents
            const chrome = metal(0xd8dce2, 0.25, 0.9);
            this.materials = { body, dark: frame, chrome };
            const MP = globalThis.MechParts;
            const g = this.group = new THREE.Group();
            g.name = 'robot_printer';
            if (opts.position) g.position.fromArray(opts.position);
            const ext = (w, h, d) => {                     // t-slot extrusion stick
                const m = MP ? MP.chamferedBox(w, h, d, Math.min(w, h, d) * 0.18, frame)
                    : new THREE.Mesh(new THREE.BoxGeometry(w, h, d), frame);
                m.castShadow = true; return m;
            };
            const t = 0.045 * s;                            // extrusion thickness
            for (const sx of [-1, 1]) {                     // base rails along Z
                const rail = ext(t, t, D); rail.position.set(sx * W * 0.4, t / 2, 0); g.add(rail);
            }
            const cross = ext(W * 0.8 + t, t, t); cross.position.set(0, t / 2, -D * 0.18); g.add(cross);
            for (const sx of [-1, 1]) {                     // portal columns + top beam
                const col = ext(t, H, t); col.position.set(sx * W * 0.5, H / 2 + t, -D * 0.18); g.add(col);
            }
            const top = ext(W + t, t, t); top.position.set(0, H + t * 1.5, -D * 0.18); g.add(top);
            // Z AXIS HARDWARE — lead screws the gantry actually rides:
            // screw rods + bottom steppers + carriage blocks on the gantry ends
            const chromeZ = metal(0xb8bcc2, 0.45, 0.6);   // satin, not mirror (mirror rods read as LED strips)
            this.zScrews = [];
            for (const sx of [-1, 1]) {
                const screw = new THREE.Mesh(new THREE.CylinderGeometry(0.009 * s, 0.009 * s, H, 8), chromeZ);
                screw.position.set(sx * W * 0.44, H / 2 + t, -D * 0.18);
                screw.castShadow = true; g.add(screw); this.zScrews.push(screw);
                const zmot = ext(0.06 * s, 0.05 * s, 0.06 * s);
                zmot.position.set(sx * W * 0.44, t * 1.3, -D * 0.18); g.add(zmot);
            }
            // bed (slides in Z) — dark slab + lighter print sheet + corner knobs
            this.bedG = new THREE.Group(); this.bedG.position.y = t * 1.6; g.add(this.bedG);
            const bed = new THREE.Mesh(new THREE.BoxGeometry(W * 0.78, 0.02 * s, D * 0.62), frame);
            bed.castShadow = bed.receiveShadow = true; this.bedG.add(bed);
            const sheet = new THREE.Mesh(new THREE.BoxGeometry(W * 0.74, 0.006 * s, D * 0.58),
                metal(0x33363c, 0.6, 0.3));
            sheet.position.y = 0.013 * s; this.bedG.add(sheet);
            for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
                const knob = new THREE.Mesh(new THREE.CylinderGeometry(0.016 * s, 0.016 * s, 0.014 * s, 10), body);
                knob.position.set(sx * W * 0.34, -0.017 * s, sz * D * 0.26); this.bedG.add(knob);
            }
            for (const sx of [-1, 1]) {                     // Y bearing blocks riding the base rails
                const blk = ext(0.06 * s, 0.05 * s, 0.1 * s);
                blk.position.set(sx * W * 0.4, -0.032 * s, 0); this.bedG.add(blk);
            }
            // X gantry (rises with the print) + head
            this.xG = new THREE.Group(); this.xG.position.set(0, H * 0.25, -D * 0.18); g.add(this.xG);
            const xBeam = ext(W, t * 0.8, t * 0.8); this.xG.add(xBeam);
            for (const sx of [-1, 1]) {                     // carriage blocks riding the screws/columns
                const blk = ext(0.075 * s, 0.075 * s, 0.08 * s);
                blk.position.set(sx * W * 0.46, 0, 0); this.xG.add(blk);
            }
            const belt = new THREE.Mesh(new THREE.BoxGeometry(W * 0.94, 0.012 * s, 0.006 * s), frame);
            belt.position.set(0, 0, t * 0.45); this.xG.add(belt);
            this.head = new THREE.Group(); this.head.position.z = t * 0.9; this.xG.add(this.head);
            const carriage = MP ? MP.chamferedBox(0.07 * s, 0.08 * s, 0.03 * s, 0.006 * s, body)
                : new THREE.Mesh(new THREE.BoxGeometry(0.07 * s, 0.08 * s, 0.03 * s), body);
            this.head.add(carriage);
            for (let i = 0; i < 4; i++) {                   // heatsink fin stack
                const fin = new THREE.Mesh(new THREE.CylinderGeometry(0.016 * s, 0.016 * s, 0.004 * s, 10), chrome);
                fin.position.set(0, -0.048 * s - i * 0.008 * s, 0.012 * s); this.head.add(fin);
            }
            const shroud = MP ? MP.chamferedBox(0.045 * s, 0.035 * s, 0.03 * s, 0.005 * s, body)
                : new THREE.Mesh(new THREE.BoxGeometry(0.045 * s, 0.035 * s, 0.03 * s), body);
            shroud.position.set(0.03 * s, -0.06 * s, 0.012 * s); this.head.add(shroud);
            const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.003 * s, 0.009 * s, 0.016 * s, 8), metal(0xc9b46a, 0.3, 0.9));
            nozzle.position.set(0, -0.089 * s, 0.012 * s); this.head.add(nozzle);
            this._nozzleTipY = -0.097 * s;                  // head-local nozzle tip
            // bowden tube: unit-length coil stretched between top beam + head
            if (MP) {
                this.bowden = MP.hoseCoil({ turns: 2.5, coilR: 0.014 * s, len: 1, tubeR: 0.004 * s });
                g.add(this.bowden);
                this._bowdenTop = V(W * 0.12, H + t, -D * 0.18);
            }
            // filament spool on the frame side
            this.spool = new THREE.Group();
            this.spool.position.set(W * 0.62, H + 0.09 * s, -D * 0.18); g.add(this.spool);
            for (const sy of [-1, 1]) {
                const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.09 * s, 0.09 * s, 0.008 * s, 18), frame);
                disc.rotation.z = Math.PI / 2; disc.position.x = sy * 0.03 * s; this.spool.add(disc);
            }
            const wind = new THREE.Mesh(new THREE.CylinderGeometry(0.06 * s, 0.06 * s, 0.05 * s, 16),
                new THREE.MeshStandardNodeMaterial({ color: opts.printColor ?? 0x2fa84f, roughness: 0.5 }));
            wind.rotation.z = Math.PI / 2; this.spool.add(wind);
            // the print itself — grows on the bed
            this.print = new THREE.Mesh(
                new THREE.BoxGeometry(W * 0.3, 1, D * 0.24),
                new THREE.MeshStandardNodeMaterial({ color: opts.printColor ?? 0x2fa84f, roughness: 0.55 }));
            this.print.castShadow = true;
            this.bedG.add(this.print);
            this.printH = (opts.printHeight ?? 0.34) * s;   // final print height
            this.printTime = opts.printTime ?? 40;          // seconds per print
            this._prog = 0;
        }
        update(t, dt) {
            if (this._printJobActive) return;   // a PrintSim job owns the axes
            const s = this.s;
            this._prog = ((t % this.printTime) / this.printTime);
            const h = Math.max(0.004 * s, this.printH * this._prog);
            this.print.scale.y = h;
            this.print.position.y = 0.016 * s + h / 2;
            // gantry tracks the top layer; head scans X; bed steps in Z
            const layerY = this.bedG.position.y + 0.016 * s + h - this._nozzleTipY;
            const gy0 = this.xG.position.y;
            this.xG.position.y = slew(this.xG.position.y, layerY, 0.12 * s, dt);
            // lead screws spin as the gantry climbs
            if (this.zScrews) for (const sc of this.zScrews) sc.rotation.y += (this.xG.position.y - gy0) * 260;
            this.head.position.x = Math.sin(t * 2.6) * this.W * 0.34;
            this.bedG.position.z = Math.sin(t * 0.9) * this.D * 0.16;
            this.spool.rotation.x += dt * 0.9;
            if (this.bowden) {
                const a = TMPa.copy(this._bowdenTop);
                const b = TMPb.set(this.head.position.x, 0, -this.D * 0.18 + 0.03 * this.s);
                b.y = this.xG.position.y + 0.02 * this.s;
                this.group.localToWorld(a); this.group.localToWorld(b);
                linkBetween(this.bowden, a, b);
            }
        }
        mounts() { return { frame: this.group, bed: this.bedG, head: this.head }; }
        mountPoint() { return this.bedG; }
    }

    // ════════════════════════════════════════════════════════════════════
    // SCARA — 2R planar arm + Z prismatic, the pick-sort classic.
    // ════════════════════════════════════════════════════════════════════
    class Scara {
        constructor(opts = {}) {
            this.opts = opts;
            this.L1 = opts.link1 ?? 0.5; this.L2 = opts.link2 ?? 0.42;
            this.H = opts.height ?? 0.7;
            this.maxRate = opts.maxRate ?? 3.2;
            const body = bodyMat(opts, 0xe8e4dc, 0.35, 0.7);
            const dark = accentMat(opts, 0x22262c, 0.5, 0.7);
            const chrome = metal(0xd8dce2, 0.2, 0.95);
            this.materials = { body, dark, chrome };
            const g = this.group = new THREE.Group();
            g.name = 'robot_scara';
            if (opts.position) g.position.fromArray(opts.position);
            const column = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.12, this.H, 14), dark);
            column.position.y = this.H / 2; column.castShadow = true; g.add(column);
            this.j1 = new THREE.Group(); this.j1.position.y = this.H; g.add(this.j1);
            const a1 = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.09, this.L1), body);
            a1.position.z = this.L1 / 2; a1.castShadow = true; this.j1.add(a1);
            this.j2 = new THREE.Group(); this.j2.position.z = this.L1; this.j1.add(this.j2);
            const a2 = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.075, this.L2), body);
            a2.position.set(0, -0.02, this.L2 / 2); a2.castShadow = true; this.j2.add(a2);
            this.zG = new THREE.Group(); this.zG.position.z = this.L2; this.j2.add(this.zG);
            this.shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, this.H * 0.8, 8), chrome);
            this.zG.add(this.shaft);
            this.cup = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.035, 0.05, 10), dark);
            this.zG.add(this.cup);
            this.q = { a: 0.6, b: 1.0, z: 0.3 };
            this.qt = { ...this.q };
            this._demo = opts.demo ?? null;
        }
        moveTo(x, z, y) {   // x/z in the robot's local plane, y = tool height
            const r = Math.min(Math.hypot(x, z), (this.L1 + this.L2) * 0.999);
            const base = Math.atan2(x, z);
            const cosB = (this.L1 * this.L1 + r * r - this.L2 * this.L2) / (2 * this.L1 * r);
            const A = Math.acos(Math.max(-1, Math.min(1, cosB)));
            const cosI = (this.L1 * this.L1 + this.L2 * this.L2 - r * r) / (2 * this.L1 * this.L2);
            const I = Math.acos(Math.max(-1, Math.min(1, cosI)));
            this.qt.a = base + A;
            this.qt.b = I - Math.PI;
            this.qt.z = Math.max(0.05, Math.min(this.H * 0.75, this.H - y));
        }
        update(t, dt) {
            if (this._demo === 'sort') {
                const period = 2.4, u = (t % period) / period, k = Math.floor(t / period) * 1.7;
                const from = [Math.sin(k) * 0.35 + 0.25, Math.cos(k) * 0.3 + 0.45];
                const to = [-0.45, 0.5];
                const p = u < 0.4 ? from : u < 0.5 ? from : to;
                const y = (u > 0.32 && u < 0.42) || u > 0.9 ? 0.12 : 0.4;
                this.moveTo(p[0], p[1], y);
            }
            this.q.a = slewAngle(this.q.a, this.qt.a, this.maxRate, dt);
            this.q.b = slewAngle(this.q.b, this.qt.b, this.maxRate, dt);
            this.q.z = slew(this.q.z, this.qt.z, 1.4, dt);
            this.j1.rotation.y = this.q.a;
            this.j2.rotation.y = this.q.b;
            this.shaft.position.y = -this.q.z / 2 + 0.05;
            this.cup.position.y = -this.q.z;
        }
        mounts() { return { base: this.group, tool: this.zG }; }
        mountPoint() { return this.zG; }
    }

    // ════════════════════════════════════════════════════════════════════
    // makeBot — KITBASH ASSEMBLY: compose unique robots from bases, arm
    // chains, masts, sensor heads and greebles (the creature creator, but
    // machines). Declarative, one call, self-animating:
    //
    //   const bot = globalThis.makeBot({
    //       base: 'tracked',                  // pedestal|wheeled|tracked|legged|ceiling
    //       trackLength: 1.4, scale: 1,
    //       arms: [{ name: 'left', segments: 3, reach: 1.1, tool: 'welder',
    //                mountAt: [-0.3, 0, 0.3] }],   // segments:3 = the full Arm6
    //       mast: { stages: 3, maxHeight: 2.0 },   // telescopic
    //       turret: { sensor: 'dish', mount: 'mast.top' },
    //       greebles: { density: 0.5, hazard: true },
    //       color: 0x3a4a3a, accent: 0x1c1c1c, seed: 7, position: [0,0,0],
    //   });
    //   scene.add(bot.group);
    //   bot.base.patrol([[0,0],[3,0]]);            // mobile bases drive
    //   bot.chain('left').pickAndPlace({...});     // 3-seg chains = full arm API
    //   bot.turret.track(() => target);            // sensor heads aim
    //   bot.mast.extendTo(1.6);
    //   bot.frame('mast.top') / bot.joint('left.j2')   // dotted addressing
    //
    // Chains with segments !== 3 use a CCD solver (reachTo/follow only);
    // segments: 3 chains ARE Arm6 instances — grippers, hands, pickAndPlace,
    // contact grasping included. Undriven chains idle on a seeded drift so
    // nothing reads frozen.
    // ════════════════════════════════════════════════════════════════════
    const mulberry = (seed) => {
        let a = (seed >>> 0) || 1;
        return () => {
            a |= 0; a = a + 0x6D2B79F5 | 0;
            let t = Math.imul(a ^ a >>> 15, 1 | a);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
    };

    // ── bases ──
    class PedestalBase {
        constructor(o, body, dark) {
            const s = o.scale ?? 1, MP = globalThis.MechParts;
            const g = this.group = new THREE.Group();
            const h = this.h = (o.height ?? 0.5) * s;
            const flange = new THREE.Mesh(new THREE.CylinderGeometry(0.3 * s, 0.32 * s, h * 0.16, 20), dark);
            flange.position.y = h * 0.08; flange.castShadow = true; g.add(flange);
            const col = new THREE.Mesh(new THREE.CylinderGeometry(0.16 * s, 0.19 * s, h * 0.84, 16), body);
            col.position.y = h * 0.16 + h * 0.42; col.castShadow = true; g.add(col);
            if (MP && THREE.mergeGeometries) {
                const bolts = new THREE.Mesh(THREE.mergeGeometries(MP.hexBolts(0.33 * s, h * 0.17, 8, { seed: 5, boltR: 0.02 * s }), false), dark);
                g.add(bolts);
            }
            this.deck = new THREE.Group(); this.deck.position.y = h; g.add(this.deck);
        }
        mounts() { return { deck: this.deck, body: this.group }; }
        mountPoint() { return this.deck; }
        update() {}
    }
    class WheeledBase {
        constructor(o, body, dark) {
            const s = o.scale ?? 1, MP = globalThis.MechParts;
            const L = (o.wheelBase ?? 0.9) * s, W = (o.trackWidth ?? 0.62) * s;
            this.speed = o.speed ?? 0.9; this.turnRate = o.turnRate ?? 1.6;
            const g = this.group = new THREE.Group();
            const chassis = MP ? MP.chamferedBox(W, 0.2 * s, L, 0.03 * s, body)
                : new THREE.Mesh(new THREE.BoxGeometry(W, 0.2 * s, L), body);
            chassis.position.y = 0.22 * s; g.add(chassis);
            const bump = new THREE.Mesh(new THREE.BoxGeometry(W + 0.04 * s, 0.055 * s, L + 0.04 * s), rubber(0x0e0e10));
            bump.position.y = 0.15 * s; g.add(bump);
            this.deck = new THREE.Group(); this.deck.position.y = 0.34 * s; g.add(this.deck);
            this.wheelR = 0.11 * s; this.wheels = [];
            const n = (o.wheels ?? 4) / 2;
            for (let i = 0; i < n; i++) for (const sx of [-1, 1]) {
                const w = MP ? MP.makeWheel({ r: this.wheelR, width: 0.07 * s, hubR: 0.035 * s, lugCount: 16, lugDepth: 0.008 * s, boltCount: 5 })
                    : (() => { const m = new THREE.Mesh(new THREE.CylinderGeometry(this.wheelR, this.wheelR, 0.07 * s, 14), rubber(0x101010)); m.rotation.z = Math.PI / 2; return m; })();
                w.position.set(sx * (W * 0.5 + 0.05 * s), this.wheelR + (MP ? 0.008 * s : 0), (i / Math.max(1, n - 1) - 0.5) * L * 0.66);
                w.castShadow = true; g.add(w); this.wheels.push(w);
            }
            this.heading = 0; this._route = null; this._ri = 0; this._dist = 0;
        }
        getPosition(out) { return (out || new THREE.Vector3()).copy((this.driveGroup || this.group).position); }
        driveTo(x, z) { this._route = [[x, z]]; this._ri = 0; return this; }
        patrol(pts) { this._route = pts; this._ri = 0; this._loop = true; return this; }
        update(t, dt) {
            const G = this.driveGroup || this.group;   // makeBot points this at the BOT ROOT
            if (!this._route || this._ri >= this._route.length) return;
            const [tx, tz] = this._route[this._ri];
            const dx = tx - G.position.x, dz = tz - G.position.z;
            if (Math.hypot(dx, dz) < 0.15) {
                this._ri++;
                if (this._loop && this._ri >= this._route.length) this._ri = 0;
                return;
            }
            const want = Math.atan2(dx, dz);
            this.heading = slewAngle(this.heading, want, this.turnRate, dt);
            G.rotation.y = this.heading;
            let dh = Math.abs((want - this.heading) % (Math.PI * 2));
            if (dh > Math.PI) dh = Math.PI * 2 - dh;
            const v = dh < 0.5 ? this.speed : this.speed * 0.15;
            G.position.x += Math.sin(this.heading) * v * dt;
            G.position.z += Math.cos(this.heading) * v * dt;
            this._dist += v * dt;
            for (const w of this.wheels) w.rotation.x = this._dist / this.wheelR;
        }
        mounts() { return { deck: this.deck, body: this.group }; }
        mountPoint() { return this.deck; }
    }
    class TrackedBase {
        constructor(o, body, dark) {
            const s = o.scale ?? 1, MP = globalThis.MechParts;
            const L = this.L = (o.trackLength ?? 1.1) * s, W = (o.trackWidth ?? 0.72) * s;
            this.speed = o.speed ?? 0.7; this.turnRate = o.turnRate ?? 1.1;
            const g = this.group = new THREE.Group();
            const hull = MP ? MP.chamferedBox(W * 0.62, 0.24 * s, L * 0.92, 0.035 * s, body)
                : new THREE.Mesh(new THREE.BoxGeometry(W * 0.62, 0.24 * s, L * 0.92), body);
            hull.position.y = 0.3 * s; g.add(hull);
            const glacis = MP ? MP.chamferedBox(W * 0.6, 0.1 * s, 0.22 * s, 0.03 * s, dark)
                : new THREE.Mesh(new THREE.BoxGeometry(W * 0.6, 0.1 * s, 0.22 * s), dark);
            glacis.position.set(0, 0.24 * s, L * 0.42); glacis.rotation.x = 0.5; g.add(glacis);
            this.deck = new THREE.Group(); this.deck.position.y = 0.43 * s; g.add(this.deck);
            this.treads = []; this.capR = 0.14 * s;
            for (const sx of [-1, 1]) {
                if (MP) {
                    const tr = MP.makeTreadTrack({ runLen: L * 0.62, capR: this.capR, width: 0.16 * s, plateN: 48 });
                    tr.rotation.y = Math.PI / 2;              // belt runs along Z
                    tr.position.set(sx * W * 0.42, this.capR + 0.012 * s, 0);
                    g.add(tr); this.treads.push(tr);
                    for (let k = -1; k <= 1; k++) {           // bogie wheels inside the belt
                        const bog = new THREE.Mesh(new THREE.CylinderGeometry(this.capR * 0.72, this.capR * 0.72, 0.1 * s, 12), dark);
                        bog.rotation.z = Math.PI / 2;
                        bog.position.set(sx * W * 0.42, this.capR + 0.012 * s, k * L * 0.24);
                        g.add(bog);
                    }
                } else {
                    const slab = new THREE.Mesh(new THREE.BoxGeometry(0.16 * s, this.capR * 2, L * 0.8), rubber(0x181818));
                    slab.position.set(sx * W * 0.42, this.capR, 0); g.add(slab); this.treads.push(null);
                }
            }
            this._peri = 2 * (L * 0.62) + 2 * Math.PI * this.capR;
            this.heading = 0; this._route = null; this._ri = 0;
        }
        getPosition(out) { return (out || new THREE.Vector3()).copy((this.driveGroup || this.group).position); }
        driveTo(x, z) { this._route = [[x, z]]; this._ri = 0; return this; }
        patrol(pts) { this._route = pts; this._ri = 0; this._loop = true; return this; }
        update(t, dt) {
            const G = this.driveGroup || this.group;
            if (!this._route || this._ri >= this._route.length) return;
            const [tx, tz] = this._route[this._ri];
            const dx = tx - G.position.x, dz = tz - G.position.z;
            if (Math.hypot(dx, dz) < 0.18) {
                this._ri++;
                if (this._loop && this._ri >= this._route.length) this._ri = 0;
                return;
            }
            const want = Math.atan2(dx, dz);
            const h0 = this.heading;
            this.heading = slewAngle(this.heading, want, this.turnRate, dt);
            G.rotation.y = this.heading;
            let dh = Math.abs((want - this.heading) % (Math.PI * 2));
            if (dh > Math.PI) dh = Math.PI * 2 - dh;
            const v = dh < 0.4 ? this.speed : this.speed * 0.1;
            G.position.x += Math.sin(this.heading) * v * dt;
            G.position.z += Math.cos(this.heading) * v * dt;
            // skid-steer: inner belt slows/reverses while turning
            const w = (this.heading - h0) / Math.max(dt, 1e-4);
            const MP = globalThis.MechParts;
            if (MP) for (let i = 0; i < 2; i++) {
                const sx = i === 0 ? -1 : 1;
                const vSide = v + sx * w * 0.35;
                if (this.treads[i]) MP.scrollTread(this.treads[i], -vSide * dt / this._peri);
            }
        }
        mounts() { return { deck: this.deck, body: this.group }; }
        mountPoint() { return this.deck; }
    }
    class LeggedBase {
        constructor(o, body, dark) {
            const s = o.scale ?? 1, MP = globalThis.MechParts;
            const pairs = this.pairs = o.legPairs ?? 2;      // 2 = quad, 3 = hexapod
            const legL = this.legL = (o.legLength ?? 0.42) * s;
            const bodyL = (o.bodyLength ?? (pairs === 2 ? 0.7 : 0.9)) * s, bodyW = 0.34 * s;
            this.speed = o.speed ?? 0.5; this.turnRate = o.turnRate ?? 1.0;
            const g = this.group = new THREE.Group();
            this.bodyY = legL * 1.0 + 0.035 * s;   // feet reach the floor with the resting knee bend
            const slab = MP ? MP.chamferedBox(bodyW, 0.16 * s, bodyL, 0.03 * s, body)
                : new THREE.Mesh(new THREE.BoxGeometry(bodyW, 0.16 * s, bodyL), body);
            this.slab = slab; slab.position.y = this.bodyY; g.add(slab);
            this.deck = new THREE.Group(); this.deck.position.y = this.bodyY + 0.09 * s; g.add(this.deck);
            this.legs = [];
            for (let p = 0; p < pairs; p++) for (const sx of [-1, 1]) {
                const hip = new THREE.Group();
                hip.position.set(sx * bodyW * 0.62, this.bodyY, (p / Math.max(1, pairs - 1) - 0.5) * bodyL * 0.72);
                g.add(hip);
                const pod = new THREE.Mesh(new THREE.CylinderGeometry(0.06 * s, 0.06 * s, 0.09 * s, 10), dark);
                pod.rotation.z = Math.PI / 2; hip.add(pod);
                const thigh = new THREE.Mesh(new THREE.CapsuleGeometry(0.035 * s, legL * 0.48, 4, 8), body);
                thigh.position.y = -legL * 0.27; hip.add(thigh);
                const knee = new THREE.Group(); knee.position.y = -legL * 0.52; hip.add(knee);
                const shin = new THREE.Mesh(new THREE.CapsuleGeometry(0.024 * s, legL * 0.44, 4, 8), dark);
                shin.position.y = -legL * 0.25; knee.add(shin);
                const foot = new THREE.Mesh(new THREE.SphereGeometry(0.045 * s, 8, 6), rubber(0x141414));
                foot.position.y = -legL * 0.5; knee.add(foot);
                // gait phase: diagonal pairs (quad) / tripod (hexapod)
                const idx = this.legs.length;
                const phase = pairs === 3 ? (idx % 2) * Math.PI : ((p + (sx > 0 ? 1 : 0)) % 2) * Math.PI;
                this.legs.push({ hip, knee, phase });
            }
            this.heading = 0; this._route = null; this._ri = 0; this._ph = 0;
        }
        getPosition(out) { return (out || new THREE.Vector3()).copy((this.driveGroup || this.group).position); }
        driveTo(x, z) { this._route = [[x, z]]; this._ri = 0; return this; }
        patrol(pts) { this._route = pts; this._ri = 0; this._loop = true; return this; }
        update(t, dt) {
            const G = this.driveGroup || this.group;
            let moving = false;
            if (this._route && this._ri < this._route.length) {
                const [tx, tz] = this._route[this._ri];
                const dx = tx - G.position.x, dz = tz - G.position.z;
                if (Math.hypot(dx, dz) < 0.15) {
                    this._ri++;
                    if (this._loop && this._ri >= this._route.length) this._ri = 0;
                } else {
                    const want = Math.atan2(dx, dz);
                    this.heading = slewAngle(this.heading, want, this.turnRate, dt);
                    G.rotation.y = this.heading;
                    G.position.x += Math.sin(this.heading) * this.speed * dt;
                    G.position.z += Math.cos(this.heading) * this.speed * dt;
                    moving = true;
                }
            }
            this._ph += (moving ? 2.1 : 0.4) * Math.PI * dt;  // stride freq; slow paw idle
            const amp = moving ? 1 : 0.12;
            for (const L of this.legs) {
                const c = Math.sin(this._ph + L.phase);
                L.hip.rotation.x = c * 0.4 * amp;
                // stance knee "give": extra flex right after touchdown
                const sw = Math.max(0, Math.sin(this._ph + L.phase + Math.PI / 2));
                L.knee.rotation.x = (0.35 + sw * 0.5) * amp + 0.15;
            }
            this.slab.position.y = this.bodyY + Math.sin(this._ph * 2) * 0.008 * (moving ? 1 : 0.3);
        }
        mounts() { return { deck: this.deck, body: this.group }; }
        mountPoint() { return this.deck; }
    }
    class DroneBase {
        constructor(o, body, dark) {
            const s = o.scale ?? 1, MP = globalThis.MechParts;
            this.alt = o.altitude ?? 1.6;
            this.speed = o.speed ?? 1.2;
            const g = this.group = new THREE.Group();
            const hull = MP ? MP.chamferedBox(0.24 * s, 0.09 * s, 0.3 * s, 0.02 * s, body)
                : new THREE.Mesh(new THREE.BoxGeometry(0.24 * s, 0.09 * s, 0.3 * s), body);
            g.add(hull);
            this.deck = new THREE.Group(); this.deck.position.y = -0.032 * s; g.add(this.deck);   // payload slings BELOW
            const hardpoint = new THREE.Mesh(new THREE.CylinderGeometry(0.06 * s, 0.07 * s, 0.03 * s, 12), dark);
            hardpoint.position.y = -0.04 * s; g.add(hardpoint);       // belly mount the payload sockets into
            const gps = new THREE.Mesh(new THREE.CylinderGeometry(0.03 * s, 0.012 * s, 0.05 * s, 10), dark);
            gps.position.y = 0.08 * s; g.add(gps);
            this.props = [];
            for (const [sx, sz] of [[-1, 1], [1, 1], [-1, -1], [1, -1]]) {
                const armM = new THREE.Mesh(new THREE.CylinderGeometry(0.014 * s, 0.014 * s, 0.3 * s, 8), dark);
                armM.rotation.z = Math.PI / 2;
                armM.rotation.y = -Math.atan2(sz, sx);      // lie along the hull->bell diagonal
                armM.position.set(sx * 0.155 * s, 0.028 * s, sz * 0.155 * s);
                g.add(armM);
                const bell = new THREE.Mesh(new THREE.CylinderGeometry(0.028 * s, 0.032 * s, 0.035 * s, 10), dark);
                bell.position.set(sx * 0.24 * s, 0.035 * s, sz * 0.24 * s); g.add(bell);
                const prop = new THREE.Group();
                prop.position.set(sx * 0.24 * s, 0.058 * s, sz * 0.24 * s);
                const pm = new THREE.MeshStandardNodeMaterial({ color: sz > 0 ? 0xff7a30 : 0x202226, roughness: 0.5 });
                for (const k of [0, 1]) {
                    const blade = new THREE.Mesh(new THREE.BoxGeometry(0.2 * s, 0.004 * s, 0.024 * s), pm);
                    blade.rotation.y = k * Math.PI / 2 + 0.2;
                    prop.add(blade);
                }
                g.add(prop);
                this.props.push({ prop, dir: sx * sz > 0 ? 1 : -1 });
            }
            this.heading = 0; this._route = null; this._ri = 0;
            this._vel = new THREE.Vector3();
        }
        getPosition(out) { return (out || new THREE.Vector3()).copy((this.driveGroup || this.group).position); }
        flyTo(x, z, alt) { if (alt !== undefined) this.alt = alt; this._route = [[x, z]]; this._ri = 0; return this; }
        patrol(pts) { this._route = pts; this._ri = 0; this._loop = true; return this; }
        update(t, dt) {
            const G = this.driveGroup || this.group;
            let vx = 0, vz = 0;
            if (this._route && this._ri < this._route.length) {
                const wp = this._route[this._ri];
                const dx = wp[0] - G.position.x, dz = wp[1] - G.position.z;
                if (wp[2] !== undefined) this.alt = wp[2];
                if (Math.hypot(dx, dz) < 0.2) {
                    this._ri++;
                    if (this._loop && this._ri >= this._route.length) this._ri = 0;
                } else {
                    const inv = this.speed / Math.hypot(dx, dz);
                    vx = dx * inv; vz = dz * inv;
                }
            }
            this._vel.x = slew(this._vel.x, vx, 2.0, dt);
            this._vel.z = slew(this._vel.z, vz, 2.0, dt);
            G.position.x += this._vel.x * dt;
            G.position.z += this._vel.z * dt;
            G.position.y = slew(G.position.y, this.alt + Math.sin(t * 7.3) * 0.008 + Math.sin(t * 11.7) * 0.005, 0.8, dt);
            G.rotation.z = -this._vel.x * 0.22;
            G.rotation.x = this._vel.z * 0.22;
            for (const P of this.props) P.prop.rotation.y += P.dir * 55 * dt;
        }
        mounts() { return { deck: this.deck, body: this.group }; }
        mountPoint() { return this.deck; }
    }
    class CeilingBase {
        constructor(o, body, dark) {
            const s = o.scale ?? 1;
            const drop = (o.dropLength ?? 0.5) * s;
            const g = this.group = new THREE.Group();
            const plate = new THREE.Mesh(new THREE.BoxGeometry(0.4 * s, 0.05 * s, 0.4 * s), dark);
            plate.castShadow = true; g.add(plate);
            const col = new THREE.Mesh(new THREE.CylinderGeometry(0.06 * s, 0.07 * s, drop, 12), body);
            col.position.y = -drop / 2; col.castShadow = true; g.add(col);
            this.flange = new THREE.Group(); this.flange.position.y = -drop; g.add(this.flange);
            g.userData.noSupportCheck = true;                // hangs, by definition
        }
        mounts() { return { anchor: this.group, flange: this.flange, deck: this.flange }; }
        mountPoint() { return this.flange; }
        update() {}
    }

    // ── telescopic mast ──
    class Mast {
        constructor(o, body, dark) {
            const s = o.scale ?? 1;
            const stages = this.stages = o.stages ?? 3;
            this.maxH = (o.maxHeight ?? 1.6) * s;
            const g = this.group = new THREE.Group();
            this._tubes = [];
            const stageH = this.maxH / stages;
            for (let i = 0; i < stages; i++) {
                const r = (0.075 - i * 0.016) * s;
                const tube = new THREE.Mesh(new THREE.CylinderGeometry(r, r * 1.06, stageH, 12), i % 2 ? dark : body);
                tube.castShadow = true;
                tube.position.y = stageH / 2;                 // extends upward from its parent joint
                const carrier = new THREE.Group();
                (i === 0 ? g : this._tubes[i - 1].carrier).add(carrier);
                carrier.add(tube);
                this._tubes.push({ carrier, stageH });
            }
            this.top = new THREE.Group();
            this._tubes[stages - 1].carrier.add(this.top);
            this._ext = 0.3; this._extT = 0.3;                // 30% idle extension
            this._apply();
        }
        _apply() {
            for (let i = 1; i < this.stages; i++) {
                // stage i only extends once stage i-1 is mostly out
                const u = Math.max(0, Math.min(1, this._ext * this.stages - (i - 1)));
                this._tubes[i].carrier.position.y = u * this._tubes[i - 1].stageH * 0.86;
            }
            this.top.position.y = this._tubes[this.stages - 1].stageH;
        }
        extendTo(h) { this._extT = Math.max(0.05, Math.min(1, h / this.maxH)); return this; }
        update(t, dt) {
            this._ext = slew(this._ext, this._extT, 0.25, dt);
            this._apply();
        }
        mounts() { return { base: this.group, top: this.top }; }
        mountPoint() { return this.top; }
    }

    // ── exotic chain (segments !== 3): yaw root + N pitch joints, CCD ──
    class BotChain {
        constructor(o, body, dark) {
            const segs = Math.max(1, o.segments ?? 2);
            const reach = o.reach ?? 0.8;
            this.maxRate = o.maxRate ?? 2.2;
            const MP = globalThis.MechParts;
            const g = this.group = new THREE.Group();
            const r0 = reach * 0.1;
            this.joints = [];
            const yaw = new THREE.Group(); g.add(yaw);
            const turn = new THREE.Mesh(new THREE.CylinderGeometry(r0 * 1.2, r0 * 1.3, r0 * 0.8, 14), dark);
            turn.position.y = r0 * 0.4; yaw.add(turn);
            this.joints.push({ group: yaw, axis: 'y', q: 0, range: [-Math.PI, Math.PI] });
            let parent = yaw, ly = r0 * 0.8;
            const wSum = segs * (segs + 1) / 2;
            for (let i = 0; i < segs; i++) {
                const L = reach * ((segs - i) / wSum) * 0.92;
                const j = new THREE.Group();
                j.position.y = ly; parent.add(j);
                const drumM = new THREE.Mesh(new THREE.CylinderGeometry(r0 * (0.8 - i * 0.1), r0 * (0.8 - i * 0.1), r0 * (1.5 - i * 0.2), 12), dark);
                drumM.rotation.z = Math.PI / 2; drumM.castShadow = true; j.add(drumM);
                const link = MP
                    ? MP.armLinkCasting({ length: L, boxW: r0 * (1.2 - i * 0.15), boxH: r0 * (1.3 - i * 0.15), endW: r0 * (0.9 - i * 0.12), endH: r0 * (1.0 - i * 0.12), ribs: 0, material: body })
                    : new THREE.Mesh(new THREE.CapsuleGeometry(r0 * 0.6, L * 0.8, 4, 8), body);
                link.rotation.x = -Math.PI / 2;               // casting extends +Z → point it +Y
                link.castShadow = true; j.add(link);
                // STOWED build pose — folded low like a parked excavator arm
                // (root leans well over, next joints fold back). The old
                // 0.35-rad near-vertical stack left any chain without a
                // follow()/reachTo() standing straight up: a mast on a bot
                // deck, a "robot arm worn as a hat" on a cyborg back mount.
                const stowQ = i === 0 ? 1.15 : (i % 2 ? -1.5 : 1.2);
                this.joints.push({ group: j, axis: 'x', q: stowQ, range: [-1.9, 1.9] });
                j.rotation.x = stowQ;
                parent = j; ly = L;
            }
            this.toolTip = new THREE.Group(); this.toolTip.position.y = ly; parent.add(this.toolTip);
            const tip = new THREE.Mesh(new THREE.ConeGeometry(r0 * 0.45, r0 * 1.1, 10), dark);
            tip.position.y = ly - r0 * 0.2; parent.add(tip);
            this._target = null; this._follow = null;
        }
        follow(fn) { this._follow = fn; return this; }
        reachTo(targetW) { (this._target = this._target || new THREE.Vector3()).copy(targetW); return this; }
        getToolTip(out) { return this.toolTip.getWorldPosition(out || new THREE.Vector3()); }
        update(t, dt) {
            const goal = this._follow ? this._follow(t) : this._target;
            if (!goal) return;
            // CCD, slew-limited: each joint turns a bounded step toward the goal
            this.group.updateWorldMatrix(true, true);
            const tip = TMPa, jw = TMPb, ax = TMPc, toT = TMPd;
            for (let pass = 0; pass < 3; pass++) {
                for (let i = this.joints.length - 1; i >= 0; i--) {
                    const J = this.joints[i];
                    this.toolTip.getWorldPosition(tip);
                    J.group.getWorldPosition(jw);
                    ax.set(J.axis === 'y' ? 0 : 1, J.axis === 'y' ? 1 : 0, 0)
                        .applyQuaternion(J.group.getWorldQuaternion(TMPq)).normalize();
                    tip.sub(jw); toT.copy(goal).sub(jw);
                    tip.addScaledVector(ax, -tip.dot(ax)).normalize();       // project ⊥ axis
                    toT.addScaledVector(ax, -toT.dot(ax)).normalize();
                    const cross = tip.cross(toT);            // tip×goal, both ⊥ axis and unit
                    let ang = Math.asin(Math.max(-1, Math.min(1, cross.dot(ax))));
                    ang = Math.max(-this.maxRate * dt, Math.min(this.maxRate * dt, ang));
                    J.q = Math.max(J.range[0], Math.min(J.range[1], J.q + ang));
                    J.group.rotation[J.axis] = J.q;
                    J.group.updateWorldMatrix(false, true);
                }
            }
        }
        mounts() { return { base: this.group, tip: this.toolTip }; }
        mountPoint() { return this.toolTip; }
    }

    // ── sensor head accessories on a Turret ──
    function dressTurret(tur, sensor, dark) {
        const s = tur.opts.scale ?? 1;
        if (sensor === 'dish') {
            const dish = new THREE.Mesh(new THREE.SphereGeometry(0.24 * s, 16, 10, 0, Math.PI * 2, 0, 0.9), metal(0xd8dce2, 0.4, 0.7));
            dish.rotation.x = -Math.PI / 2; dish.position.z = 0.32 * s;
            tur.pitchG.add(dish);
        } else if (sensor === 'lidar') {
            const drum = new THREE.Mesh(new THREE.CylinderGeometry(0.09 * s, 0.1 * s, 0.14 * s, 16), dark);
            drum.position.y = 0.3 * s; tur.yawG.add(drum);
            const band = new THREE.Mesh(new THREE.CylinderGeometry(0.092 * s, 0.092 * s, 0.03 * s, 16),
                new THREE.MeshStandardNodeMaterial({ color: 0x101418, emissive: new THREE.Color(0x30c0ff), emissiveIntensity: 1.4 }));
            band.position.y = 0.3 * s; tur.yawG.add(band);
            tur._spinDrum = drum;
        }
        return tur;
    }


    // ── Automatron-style part FAMILIES: same slots, distinct visual lines ──
    const FAMILIES = {
        industrial: { chamfer: 0.05, vents: 2, antenna: false, visor: 'lens' },
        military:   { chamfer: 0.025, vents: 1, antenna: true, visor: 'slit' },
        utility:    { chamfer: 0.07, vents: 3, antenna: false, visor: 'dome' },
        scout:      { chamfer: 0.09, vents: 0, antenna: true, visor: 'dome' },
    };
    class Torso {
        constructor(o, body, dark) {
            const s = o.scale ?? 1, MP = globalThis.MechParts;
            const fam = FAMILIES[o.family ?? 'industrial'] || FAMILIES.industrial;
            const w = (o.family === 'scout' ? 0.4 : o.family === 'military' ? 0.56 : 0.48) * s;
            const h = (o.family === 'military' ? 0.48 : 0.56) * s, d = 0.32 * s;
            const g = this.group = new THREE.Group();
            const shell = MP ? MP.chamferedBox(w, h, d, fam.chamfer * s, body)
                : new THREE.Mesh(new THREE.BoxGeometry(w, h, d), body);
            shell.position.y = h / 2; g.add(shell);
            const waist = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.32, w * 0.38, 0.06 * s, 12), dark);
            waist.position.y = 0.03 * s; g.add(waist);
            const collar = new THREE.Mesh(new THREE.CylinderGeometry(0.09 * s, 0.11 * s, 0.05 * s, 12), dark);
            collar.position.y = h + 0.02 * s; g.add(collar);
            if (MP) for (let i = 0; i < fam.vents; i++) {
                const v = MP.ventGrille({ w: 0.11 * s, h: 0.07 * s, material: dark });
                v.position.set((i - (fam.vents - 1) / 2) * 0.14 * s, h * 0.62, d / 2 + 0.002);
                v.userData.allowIntersect = true;
                g.add(v);
            }
            if (fam.antenna) {
                const an = new THREE.Mesh(new THREE.CylinderGeometry(0.006 * s, 0.009 * s, 0.5 * s, 6), dark);
                an.position.set(-w * 0.38, h + 0.24 * s, -d * 0.3);
                an.rotation.z = 0.12; g.add(an);
            }
            // SOCKETS — the fixed per-category contract (Automatron lesson):
            // shoulders, neck, back share local frames across EVERY family
            this.shoulderL = new THREE.Group(); this.shoulderL.position.set(-w / 2 - 0.02 * s, h * 0.8, 0); g.add(this.shoulderL);
            this.shoulderR = new THREE.Group(); this.shoulderR.position.set(w / 2 + 0.02 * s, h * 0.8, 0); g.add(this.shoulderR);
            this.neck = new THREE.Group(); this.neck.position.y = h + 0.045 * s; g.add(this.neck);
            this.back = new THREE.Group(); this.back.position.set(0, h * 0.62, -d / 2 - 0.01); g.add(this.back);
            for (const sd of [this.shoulderL, this.shoulderR]) {
                const pad = new THREE.Mesh(new THREE.CylinderGeometry(0.055 * s, 0.06 * s, 0.05 * s, 10), dark);
                pad.rotation.z = Math.PI / 2; sd.add(pad);
            }
        }
        update() {}
        mounts() { return { shoulderL: this.shoulderL, shoulderR: this.shoulderR, neck: this.neck, back: this.back, base: this.group }; }
        mountPoint() { return this.neck; }
    }
    class Head {
        constructor(o, body, dark) {
            const s = o.scale ?? 1, MP = globalThis.MechParts;
            const fam = FAMILIES[o.family ?? 'industrial'] || FAMILIES.industrial;
            const g = this.group = new THREE.Group();
            const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.035 * s, 0.045 * s, 0.06 * s, 10), dark);
            neck.position.y = 0.03 * s; g.add(neck);
            this.yawG = new THREE.Group(); this.yawG.position.y = 0.07 * s; g.add(this.yawG);
            const box = MP ? MP.chamferedBox(0.2 * s, 0.16 * s, 0.2 * s, fam.chamfer * 0.8 * s, body)
                : new THREE.Mesh(new THREE.BoxGeometry(0.2 * s, 0.16 * s, 0.2 * s), body);
            box.position.y = 0.08 * s; this.yawG.add(box);
            const eyeMat = new THREE.MeshStandardNodeMaterial({
                color: 0x101418, roughness: 0.2,
                emissive: new THREE.Color(o.eyeColor ?? 0x30c0ff), emissiveIntensity: 1.6,
            });
            if (fam.visor === 'lens') {
                const eye = new THREE.Mesh(new THREE.CylinderGeometry(0.045 * s, 0.045 * s, 0.02 * s, 12), eyeMat);
                eye.rotation.x = Math.PI / 2; eye.position.set(0, 0.085 * s, 0.1 * s); this.yawG.add(eye);
            } else if (fam.visor === 'slit') {
                const eye = new THREE.Mesh(new THREE.BoxGeometry(0.14 * s, 0.02 * s, 0.012 * s), eyeMat);
                eye.position.set(0, 0.09 * s, 0.1 * s); this.yawG.add(eye);
            } else {
                const eye = new THREE.Mesh(new THREE.SphereGeometry(0.055 * s, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2), eyeMat);
                eye.rotation.x = Math.PI / 2; eye.position.set(0, 0.085 * s, 0.095 * s); this.yawG.add(eye);
            }
            if (fam.antenna) {
                const an = new THREE.Mesh(new THREE.CylinderGeometry(0.004 * s, 0.006 * s, 0.16 * s, 6), dark);
                an.position.set(0.07 * s, 0.22 * s, -0.05 * s); this.yawG.add(an);
            }
            this._seed = (o.seed ?? 1) * 1.7;
        }
        update(t) { this.yawG.rotation.y = Math.sin(t * 0.4 + this._seed) * 0.5; }   // idle look-around
        mounts() { return { top: this.yawG, base: this.group }; }
        mountPoint() { return this.yawG; }
    }

    globalThis.makeBot = function makeBot(opts = {}) {
        if (opts.preset) return RoboticsKit[opts.preset] ? RoboticsKit[opts.preset](opts) : makeRobotThrow(opts.preset);
        const body = bodyMat(opts, 0x8a94a0, 0.42, 0.7);
        const dark = accentMat(opts, 0x22262c);
        const seed = opts.seed ?? 1;
        const rng = mulberry(seed);
        const bot = { chains: [], materials: { body, dark }, _mods: [] };
        const g = bot.group = new THREE.Group();
        g.name = 'makebot';
        if (opts.position) g.position.fromArray(opts.position);
        if (opts.rotation) g.rotation.y = opts.rotation;

        // base
        const BASES = { pedestal: PedestalBase, wheeled: WheeledBase, tracked: TrackedBase, legged: LeggedBase, drone: DroneBase, ceiling: CeilingBase };
        const BaseC = BASES[opts.base ?? 'wheeled'];
        if (!BaseC) throw new Error(`makeBot: unknown base '${opts.base}' — one of ${Object.keys(BASES).join('/')}`);
        bot.base = new BaseC(opts, body, dark);
        bot.base.driveGroup = g;                          // mobile bases drive the BOT ROOT
        g.add(bot.base.group);
        bot._mods.push(bot.base);
        const named = { base: bot.base };

        // dotted-path frame resolution over named modules
        bot.frame = (path) => {
            if (!path) return bot.base.mountPoint();
            const [head, ...rest] = path.split('.');
            const mod = named[head];
            if (mod) {
                const m = mod.mounts();
                return rest.length ? (m[rest[0]] || mod.mountPoint()) : mod.mountPoint();
            }
            return bot.base.mounts()[path] || bot.base.mountPoint();
        };
        const attach = (module, mOpts) => {
            const frame = bot.frame(mOpts.mount ?? 'deck');
            frame.add(module.group);
            if (mOpts.mountAt) module.group.position.fromArray(mOpts.mountAt);
            if (mOpts.rotation3) module.group.rotation.set(mOpts.rotation3[0], mOpts.rotation3[1], mOpts.rotation3[2]);
            module.group.userData.noSupportCheck = true;      // supported by its parent frame
            bot._mods.push(module);
        };

        // mast
        if (opts.mast) {
            bot.mast = new Mast({ ...opts.mast, scale: opts.scale ?? 1 }, body, dark);
            attach(bot.mast, opts.mast);
            named.mast = bot.mast;
        }
        // torso slot: a styled shell carrying shoulder/neck/back sockets
        if (opts.torso) {
            bot.torso = new Torso({ ...opts.torso, scale: opts.scale ?? 1 }, body, dark);
            attach(bot.torso, opts.torso);
            named.torso = bot.torso;
        }
        // head slot: sensor face on the torso neck (or wherever mounted)
        if (opts.head) {
            bot.head = new Head({ ...opts.head, scale: opts.scale ?? 1, seed: opts.seed }, body, dark);
            attach(bot.head, { mount: opts.head.mount ?? (opts.torso ? 'torso.neck' : 'deck'), ...opts.head });
            named.head = bot.head;
        }
        // arm chains — segments 3 (default) = the full Arm6; anything else = CCD chain
        let _shoulderToggle = 0;
        for (const aOpts of opts.arms ?? []) {
            const name = aOpts.name ?? `arm${bot.chains.length}`;
            if (!aOpts.mount && bot.torso) aOpts.mount = (_shoulderToggle++ % 2) ? 'torso.shoulderR' : 'torso.shoulderL';
            const segs = aOpts.segments ?? 3;
            let chain;
            if (segs === 3) {
                chain = new Arm6({ pedestal: false, ...aOpts, color: aOpts.color ?? opts.color, accent: aOpts.accent ?? opts.accent, position: undefined });
                chain._idleSeed = rng() * 100;
            } else {
                chain = new BotChain(aOpts, body, dark);
            }
            attach(chain, aOpts);
            named[name] = chain;
            bot.chains.push({ name, chain });
        }
        // sensor head (a Turret, optionally dressed)
        if (opts.turret) {
            bot.turret = dressTurret(new Turret({ scale: opts.turret.scale ?? 0.7, eyeColor: opts.turret.eyeColor, color: opts.color, accent: opts.accent }), opts.turret.sensor, dark);
            attach(bot.turret, opts.turret);
            named.turret = bot.turret;
        }
        // greebles: seeded deck/hull dressing
        const gr = opts.greebles;
        if (gr && globalThis.MechParts) {
            const MP = globalThis.MechParts;
            const deck = bot.base.mounts().deck || bot.base.mountPoint();
            const n = Math.round((gr.density ?? 0.4) * 5);
            for (let i = 0; i < n; i++) {
                const v = MP.ventGrille({ w: 0.1, h: 0.06, material: dark });
                v.position.set((rng() - 0.5) * 0.4, 0.03, (rng() - 0.5) * 0.6);
                v.rotation.x = -Math.PI / 2;
                v.userData.allowIntersect = true;
                deck.add(v);
            }
            if (gr.hazard) {
                const plate = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.001, 0.1),
                    MP.applyHazardStripes(new THREE.MeshStandardNodeMaterial({ roughness: 0.7 }), { freq: 8 }));
                plate.position.set(0, 0.021, 0.2);
                plate.userData.allowIntersect = true;
                deck.add(plate);
            }
            const bcn = MP.beacon({ r: 0.03, color: 0xff7a10 });
            bcn.mesh.position.set(0.15, 0.05, -0.2);
            deck.add(bcn.mesh);
            bot._beacon = bcn;
        }

        bot.chain = (name) => (named[name] && named[name].reachTo) ? named[name] : null;
        bot.joint = (path) => {
            const [cn, jn] = path.split('.');
            const c = named[cn];
            if (!c) return null;
            if (c.joints) return c.joints[parseInt(jn?.slice(1) ?? '0', 10)] ?? null;
            if (c.q && jn && jn in c.q) return { get target() { return c.qt[jn]; }, set target(v) { c.qt[jn] = v; }, current: c.q[jn] };
            return null;
        };
        bot.update = (t, dt) => {
            for (const m of bot._mods) if (m.update) m.update(t, dt);
            if (bot._beacon) bot._beacon.update(t);
            if (bot.turret && bot.turret._spinDrum) bot.turret._spinDrum.rotation.y = t * 9;   // lidar spins constant
            // seeded idle drift for undriven full arms — nothing reads frozen
            for (const { chain } of bot.chains) {
                if (chain instanceof Arm6 && !chain._program && !chain._target) {
                    const s0 = chain._idleSeed ?? 0;
                    const r = (chain.opts.reach ?? 1.5) * 0.5;
                    TMPd.set(Math.sin(t * 0.35 + s0) * r * 0.4, r * 0.9 + Math.sin(t * 0.5 + s0 * 2) * r * 0.14, r + Math.cos(t * 0.28 + s0) * r * 0.3);
                    chain.group.localToWorld(TMPd);
                    chain.reachTo(TMPd, dt);
                    chain._applyGripPose();
                }
            }
        };
        // ── workbench verbs: attach/detach parts at runtime ──
        const KINDS = {
            arm: (o2) => { const c = (o2.segments ?? 3) === 3 ? new Arm6({ pedestal: false, ...o2, color: o2.color ?? opts.color, accent: o2.accent ?? opts.accent, position: undefined }) : new BotChain(o2, body, dark); if (c instanceof Arm6) c._idleSeed = rng() * 100; return c; },
            turret: (o2) => dressTurret(new Turret({ scale: o2.scale ?? 0.7, eyeColor: o2.eyeColor, color: opts.color, accent: opts.accent }), o2.sensor, dark),
            mast: (o2) => new Mast({ ...o2, scale: opts.scale ?? 1 }, body, dark),
            torso: (o2) => new Torso({ ...o2, scale: opts.scale ?? 1 }, body, dark),
            head: (o2) => new Head({ ...o2, scale: opts.scale ?? 1, seed: opts.seed }, body, dark),
        };
        bot.attach = (name, kind, o2 = {}) => {
            if (named[name]) bot.detach(name);
            const mod = KINDS[kind] ? KINDS[kind](o2) : null;
            if (!mod) throw new Error("bot.attach: unknown kind " + kind + " - one of " + Object.keys(KINDS).join("/"));
            attach(mod, o2);
            named[name] = mod;
            if (kind === 'arm') bot.chains.push({ name, chain: mod });
            if (kind === 'torso') bot.torso = mod;
            if (kind === 'head') bot.head = mod;
            if (kind === 'turret') bot.turret = mod;
            if (kind === 'mast') bot.mast = mod;
            return mod;                              // attach() above already registered it in _mods
        };
        bot.detach = (name) => {
            const mod = named[name];
            if (!mod) return null;
            if (mod.group.parent) mod.group.parent.remove(mod.group);
            bot._mods = bot._mods.filter((m) => m !== mod);
            bot.chains = bot.chains.filter((c) => c.chain !== mod);
            for (const k of ['torso', 'head', 'turret', 'mast']) if (bot[k] === mod) bot[k] = null;
            delete named[name];
            return mod;                                  // still a live module - re-add its .group anywhere
        };
        bot.mounts = () => bot.base.mounts();
        bot.mountPoint = () => bot.base.mountPoint();
        return register(bot, opts);
    };
    const makeRobotThrow = (p) => { throw new Error(`makeBot: unknown preset '${p}'`); };

    const RoboticsKit = {
        arm: (o) => register(new Arm6(o || {}), o || {}),
        delta: (o) => register(new Delta(o || {}), o || {}),
        kossel: (o) => register(new Kossel(o || {}), o || {}),
        stewart: (o) => register(new Stewart(o || {}), o || {}),
        turret: (o) => register(new Turret(o || {}), o || {}),
        agv: (o) => register(new AGV(o || {}), o || {}),
        gantry: (o) => register(new Gantry(o || {}), o || {}),
        scara: (o) => register(new Scara(o || {}), o || {}),
        printer: (o) => register(new Printer(o || {}), o || {}),
    };

    // ════════════════════════════════════════════════════════════════════
    // CONTRAPTIONS — chain robots into weird animated assemblies. The child
    // rides the parent's mount frame; both keep animating independently
    // (the arm IK + turret aim solve in their own local frames, so they
    // stay correct on a moving base).
    //   RoboticsKit.connect(agv, turret)                          // default frame (deck)
    //   RoboticsKit.connect(stewart, arm, { at: 'top', offset: [0, 0.05, 0] })
    //   turret2.mount(scanner, { at: 'barrel', offset: [0, 0.1, 0.3] })   // same thing, method form
    // parent: a kit robot OR any Object3D. child: a kit robot OR any Object3D.
    // ════════════════════════════════════════════════════════════════════
    const frameOf = (x, at) => {
        if (!x) return null;
        if (x.isObject3D) return x;
        if (typeof x.mounts === 'function') {
            const m = x.mounts();
            if (at) {
                if (!m[at]) throw new Error(`RoboticsKit.connect: no mount '${at}' — available: ${Object.keys(m).join('/')}`);
                return m[at];
            }
        }
        if (typeof x.mountPoint === 'function') return x.mountPoint();
        return x.group && x.group.isObject3D ? x.group : null;
    };
    RoboticsKit.connect = (parent, child, o = {}) => {
        const frame = frameOf(parent, o.at);
        const cG = child && child.isObject3D ? child : child && child.group;
        if (!frame || !cG || !cG.isObject3D) throw new Error('RoboticsKit.connect(parent, child): pass kit robots or Object3Ds');
        frame.add(cG);
        cG.userData.noSupportCheck = true;    // mounted = supported by its parent frame, not the floor
        cG.position.set(0, 0, 0);
        if (o.offset) cG.position.fromArray(o.offset);
        if (o.rotation) cG.rotation.set(o.rotation[0], o.rotation[1], o.rotation[2]);
        if (o.scale) cG.scale.setScalar(o.scale);
        return child;
    };

    // ════════════════════════════════════════════════════════════════════
    // CREATURE CYBORG BRIDGE — fit robot attachments onto makeCreature
    // anchors in ONE declarative call. Measures the organic part under the
    // anchor bone, auto-scales the module to match, centers it on the
    // organic centroid, applies per-anchor orientation defaults, and hides
    // the organic part it replaces. Modules ride the living skeleton.
    //
    //   const mods = RoboticsKit.cyborg(creature, {
    //       head: { family: 'military', eyeColor: 0xff4020 },  // makeBot head spec
    //       wristR: true,                                      // default tool-pod
    //       back: { arms: [{ segments: 2, reach: 0.45 }] },    // makeBot spec
    //   });
    //   mods.back.chains[0].chain.follow(...)                  // program them
    //
    // Per-anchor spec values: a makeBot/makeRobot SPEC object, a prebuilt
    // module ({group} or Object3D), or true for the anchor's default. Each
    // entry may carry { fit, offset, rotation, scale } overrides.
    // ════════════════════════════════════════════════════════════════════
    // measure a creature by its SKELETON — Box3.setFromObject on skinned
    // meshes uses bind-space geometry that does NOT track the skeleton, so a
    // creature placed away from the origin measures wildly oversized (a 1.4m
    // wolf at (9,7.5) boxed 10m → modules auto-scaled 3× and landed beside
    // the body). Bone world positions are always correct; add flesh margin.
    const _skelBox = (creature) => {
        const box = new THREE.Box3();
        const v = new THREE.Vector3();
        if (creature.bones && creature.bones.length) {
            for (const b of creature.bones) { b.getWorldPosition(v); box.expandByPoint(v); }
            box.expandByScalar(0.15);
        } else {
            box.setFromObject(creature.group);
        }
        return box;
    };

    const _measureUnder = (root) => {
        // bbox of the organic meshes under an anchor, stopping at CHILD
        // BONES (a chest bone's subtree contains the whole head otherwise)
        root.updateWorldMatrix(true, true);
        const box = new THREE.Box3();
        const walk = (n) => {
            for (const c of n.children) {
                if (c.isBone) continue;
                if (c.visible === false) continue;
                if (c.isMesh && c.geometry) box.expandByObject(c);
                walk(c);
            }
        };
        walk(root);
        if (box.isEmpty()) return null;
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
        return { size, max: Math.max(size.x, size.y, size.z), centerLocal: center.applyMatrix4(inv) };
    };
    // ── cyber-enhancement GRAFT: the mounting that makes a back module read
    // as part of the BODY, not cargo. Segmented plates sunk into the flesh,
    // an emissive seam at the metal/flesh boundary, a socket collar the
    // module emerges from, and feed lines curving down INTO the body. No
    // saddles, no straps — implanted, not strapped on.
    const _cyberGraft = (t, opts = {}) => {
        const g = new THREE.Group();
        g.name = 'cyberGraft';
        const dark = metal(0x22262c, 0.5, 0.8);
        const acc = metal(opts.color ?? 0x8a94a0, 0.4, 0.8);
        const H = t * 0.12;
        // socket collar SUNK into the back — flesh meets metal at the rim
        const collar = new THREE.Mesh(new THREE.CylinderGeometry(t * 0.15, t * 0.2, H * 2.2, 14), dark);
        collar.position.y = -H * 0.85;                    // every edge buried in the sloped back
        collar.userData.allowIntersect = true; collar.castShadow = true; g.add(collar);
        // emissive seam RING at the metal/flesh boundary
        const seam = new THREE.Mesh(new THREE.TorusGeometry(t * 0.175, t * 0.03, 8, 24),
            new THREE.MeshStandardNodeMaterial({ color: 0x101418, roughness: 0.3,
                emissive: new THREE.Color(opts.seamColor ?? 0x30c0ff), emissiveIntensity: 1.3 }));
        seam.rotation.x = Math.PI / 2; seam.position.y = -H * 0.02;
        seam.userData.allowIntersect = true; g.add(seam);
        // one low spinal ridge plate aft of the socket, mostly buried
        const ridge = new THREE.Mesh(new THREE.BoxGeometry(t * 0.3, H, t * 0.62), acc);
        ridge.position.set(0, -H * 1.1, -t * 0.52);
        ridge.userData.allowIntersect = true; ridge.castShadow = true; g.add(ridge);
        // feed lines: tight arcs out of the collar base diving straight INTO
        // the back — implanted lines, nothing loose
        for (const sd of [-1, 1]) {
            const pts = [new THREE.Vector3(sd * t * 0.14, -H * 0.4, -t * 0.12),
                         new THREE.Vector3(sd * t * 0.3, -H * 1.6, -t * 0.2),
                         new THREE.Vector3(sd * t * 0.34, -H * 3.6, -t * 0.22)];
            const tube = new THREE.Mesh(
                new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 10, t * 0.03, 8), dark);
            tube.userData.allowIntersect = true; g.add(tube);
        }
        return g;
    };

    const _CYBORG_DEFAULTS = {
        head:   { fit: 1.1,  rotation: [0, 0, 0],        hide: 'children' },
        wristL: { fit: 1.5,  rotation: [Math.PI, 0, 0],  hide: 'hand' },
        wristR: { fit: 1.5,  rotation: [Math.PI, 0, 0],  hide: 'hand' },
        chest:  { fit: 0.55, rotation: [0.4, Math.PI, 0], back: true },
        back:   { fit: 0.55, rotation: [0.4, Math.PI, 0], back: true },
        hips:   { fit: 0.5,  rotation: [0, 0, 0] },
    };
    RoboticsKit.cyborg = (creature, spec, opts = {}) => {
        if (!creature || !creature.anchor) throw new Error('RoboticsKit.cyborg: pass a makeCreature (needs .anchor())');
        const out = {};
        for (const [name, want] of Object.entries(spec || {})) {
            const D = _CYBORG_DEFAULTS[name];
            if (!D || want == null || want === false) continue;
            let bone = creature.anchor(name);
            if (!bone) { console.warn(`[cyborg] creature has no '${name}' anchor — skipped`); continue; }
            // on a horizontal body the chest anchor is the NECK — a back
            // mount belongs on the spine, so quads use the hips bone
            const cS0 = _skelBox(creature).getSize(new THREE.Vector3());
            const isQuad = cS0.y < Math.max(cS0.x, cS0.z) * 0.8;
            if (D.back && isQuad) {
                // ride the MIDDLE of the BODY: walk root->head along the
                // bone chain, pick the bone physically closest to the
                // creature's center (the chain-INDEX midpoint lands in the
                // crook of the neck on neck-bone-dense rigs)
                const headB = creature.anchor('head');
                const chain = [];
                let b2 = creature.anchor('hips');
                while (b2) {
                    chain.push(b2);
                    b2 = b2.children.find((c) => c.isBone && headB && (c === headB || c.getObjectById(headB.id)));
                }
                if (chain.length > 2) {
                    creature.group.updateWorldMatrix(true, true);
                    const cc = _skelBox(creature).getCenter(new THREE.Vector3());
                    let best = bone, bd = Infinity;
                    const bw = new THREE.Vector3();
                    for (const cb2 of chain) {
                        cb2.getWorldPosition(bw);
                        const d = (bw.x - cc.x) * (bw.x - cc.x) + (bw.z - cc.z) * (bw.z - cc.z);
                        if (d < bd) { bd = d; best = cb2; }
                    }
                    bone = best;
                }
            }
            const organic = _measureUnder(bone);
            // build or accept the module
            let mod = want;
            const cfg = (typeof want === 'object' && !want.isObject3D && !want.group) ? want : {};
            if (want === true || (typeof want === 'object' && !want.isObject3D && !want.group)) {
                if (name === 'head') {
                    const donor = globalThis.makeBot({ head: (want === true ? { family: 'industrial' } : cfg), base: 'pedestal', height: 0.05, scale: 0.3 });
                    mod = donor.head;                        // steal the head module; donor never enters the scene
                } else if (name === 'wristL' || name === 'wristR') {
                    if (want === true) {
                        // a hand gets a HAND: steal the humanoid robotic hand
                        // (4 fingers + thumb) off a donor arm's wrist joint
                        const donor = globalThis.makeRobot('arm', { tool: 'hand', auto: false });
                        mod = donor.j6;
                        if (mod.parent) mod.parent.remove(mod);
                    } else {
                        mod = globalThis.makeRobot('turret', Object.assign({ scale: 0.16, auto: false }, cfg));
                    }
                } else if (typeof want === 'object' && (want.arms || want.base || want.torso)) {
                    mod = globalThis.makeBot(Object.assign({ base: 'pedestal', height: 0.02, scale: 0.35 }, cfg));
                } else {
                    // default back/hips module: a standalone ARM with the
                    // humanoid HAND. NOT a makeBot wrapper — a makeBot mounts
                    // its arm at the TORSO SHOULDER, offset from the group
                    // origin, so the visible arm emerges beside wherever the
                    // graft socket sits. A bare Arm6's base IS its origin —
                    // socket and arm base coincide by construction.
                    mod = globalThis.makeRobot('arm', Object.assign({ reach: 0.5, tool: 'hand' }, cfg));
                }
            }
            const mG = mod.isObject3D ? mod : mod.group;
            // auto-scale: heads/hands match the organic part they replace;
            // body-mounted modules scale to the CREATURE
            const cBox = _skelBox(creature);
            const cMax = Math.max(0.2, ...cBox.getSize(new THREE.Vector3()).toArray());
            const mBox = new THREE.Box3().setFromObject(mG);
            const mMax = Math.max(...mBox.getSize(new THREE.Vector3()).toArray()) || 1;
            const fit = cfg.fit ?? D.fit;
            const target = D.back || name === 'hips'
                ? cMax * 0.2 * fit / 0.55
                : (organic ? organic.max * fit : cMax * 0.16 * fit);
            const k = cfg.scale ?? (target / mMax);
            // hide the organic part being replaced (AFTER measuring it)
            if (D.hide === 'children') bone.children.forEach((c) => { if (!c.isBone) c.visible = false; });
            if (D.hide === 'hand') { const h = bone.children.find((c) => c.name === 'hand'); if (h) h.visible = false; }
            // two-step exact mount: attach at identity, measure where the
            // module landed in bone space, then place it — module origins
            // are arbitrary (mounting origins at centroids floated heads)
            const rot = cfg.rotation ?? (D.back && isQuad ? [0, 0, 0] : D.rotation);
            RoboticsKit.connect(bone, mod, { rotation: rot, scale: k });
            // wrists: point the fingers the way the organic hand extends
            if (!cfg.rotation && (name === 'wristL' || name === 'wristR') && organic && organic.centerLocal.lengthSq() > 1e-6) {
                mG.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), organic.centerLocal.clone().normalize());
            }
            bone.updateWorldMatrix(true, true);
            const invB = new THREE.Matrix4().copy(bone.matrixWorld).invert();
            const mBox2 = new THREE.Box3().setFromObject(mG);
            const mC = mBox2.getCenter(new THREE.Vector3()).applyMatrix4(invB);
            if (cfg.offset) {
                mG.position.add(new THREE.Vector3().fromArray(cfg.offset).sub(mC));
            } else if (D.back && isQuad) {
                // SEAT the module's base on the dorsal surface (center-
                // matching hangs tall masts in the air)
                const upL = new THREE.Vector3(0, 1, 0).applyQuaternion(bone.getWorldQuaternion(new THREE.Quaternion()).invert()).normalize();
                const boneW = bone.getWorldPosition(new THREE.Vector3());
                const dy = (boneW.y + cS0.y * 0.16) - mBox2.min.y;
                mG.position.add(upL.multiplyScalar(dy));
            } else if (D.back) {
                const tC = new THREE.Vector3(0, 0, -(cS0.z * 0.3 + mBox2.getSize(new THREE.Vector3()).z * 0.5));
                mG.position.add(tC.sub(mC));
            } else {
                let tC;
                if (organic) {
                    tC = organic.centerLocal.clone();
                    if (name === 'head') tC.y = Math.max(tC.y, 0);
                } else tC = new THREE.Vector3(0, name === 'head' ? 0.1 : -0.05, 0);
                mG.position.add(tC.sub(mC));
            }
            // cyber-enhancement graft under back/hips modules: segmented
            // plates SUNK into the flesh at the module's base, an emissive
            // metal/flesh seam, a socket collar, feed lines into the body —
            // the module reads implanted, not strapped on
            if (D.back || name === 'hips') {
                const gft = _cyberGraft(Math.max(0.08, target),
                    { color: opts.color, seamColor: cfg.seamColor });
                bone.add(gft);
                bone.updateWorldMatrix(true, true);
                const inv2 = new THREE.Matrix4().copy(bone.matrixWorld).invert();
                // anchor the graft at the module's ORIGIN (the pedestal base),
                // not the bbox center — a leaning arm shifts its bbox center
                // toward the lean and the socket lands beside the actual base
                const bb3 = new THREE.Box3().setFromObject(mG);
                const baseW = mG.getWorldPosition(new THREE.Vector3());
                baseW.y = bb3.min.y + (bb3.max.y - bb3.min.y) * 0.02;
                gft.position.copy(baseW.applyMatrix4(inv2));
                out[name + 'Graft'] = gft;
            }
            out[name] = mod;
        }
        return out;
    };

    // ════════════════════════════════════════════════════════════════════
    // FETCH_TEXTURE MATERIALS — apply a fetched PBR texture set to a robot.
    // Accepts the SAME key names fetch_texture.py writes into tex_urls.json
    // (diff/rough/normal/metal/ao) — values may be raw ASSETS bytes (base64
    // from scene.json) or already-loaded THREE.Texture objects.
    //   await RoboticsKit.applyTextures(arm, {
    //       diff: ASSETS.rust_diff, rough: ASSETS.rust_rough, normal: ASSETS.rust_normal,
    //   }, { repeat: 2 });                       // part: 'body' (default) | 'accent' | 'all'
    // A diffuse map clears the body tint to white (pass keepTint to blend)
    // and, if no metal map came with it, drops metalness so the albedo reads.
    // ════════════════════════════════════════════════════════════════════
    const TEX_SLOTS = {
        diff: 'map', albedo: 'map', color: 'map', map: 'map',
        rough: 'roughnessMap', roughness: 'roughnessMap', roughnessMap: 'roughnessMap',
        normal: 'normalMap', normal_gl: 'normalMap', normalMap: 'normalMap',
        metal: 'metalnessMap', metalness: 'metalnessMap', metalnessMap: 'metalnessMap',
        ao: 'aoMap', aoMap: 'aoMap',
    };
    RoboticsKit.applyTextures = async (robot, maps, o = {}) => {
        const reg = robot && robot.materials;
        if (!reg) throw new Error('applyTextures: pass a kit robot (has .materials registry)');
        const targets = (o.part === 'accent' ? [reg.dark] : o.part === 'all' ? Object.values(reg) : [reg.body]).filter(Boolean);
        const rep = Array.isArray(o.repeat) ? o.repeat : [o.repeat ?? 1, o.repeat ?? 1];
        const applied = {};
        for (const [key, val] of Object.entries(maps || {})) {
            const slot = TEX_SLOTS[key];
            if (!slot || val == null) continue;
            let tex = val;
            if (!tex.isTexture) tex = await globalThis.loadImageTexture(val, { srgb: slot === 'map' });
            tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
            tex.repeat.set(rep[0], rep[1]);
            if (slot === 'aoMap') tex.channel = 0;      // robots have one UV set
            applied[slot] = tex;
        }
        for (const m of targets) {
            for (const [slot, tex] of Object.entries(applied)) m[slot] = tex;
            if (applied.map && !o.keepTint) m.color.set(0xffffff);
            if (applied.roughnessMap) m.roughness = 1;          // let the map own it
            if (applied.metalnessMap) m.metalness = 1;
            else if (applied.map) m.metalness = o.metalness ?? 0.2;  // albedo reads without an env map
            if (o.roughness !== undefined) m.roughness = o.roughness;
            if (o.metalness !== undefined) m.metalness = o.metalness;
            m.needsUpdate = true;
        }
        return robot;
    };

    globalThis.RoboticsKit = RoboticsKit;
    globalThis.makeRobot = (type, opts) => {
        if (!RoboticsKit[type]) throw new Error(`makeRobot: unknown type '${type}' — one of ${Object.keys(RoboticsKit).join('/')}`);
        return RoboticsKit[type](opts);
    };
    console.log('[robotics_kit] makeRobot ready — arm (6-DOF IK + gripper/welder + pickAndPlace), delta (closed-form picker), stewart (hexapod pistons), turret (slew aim), agv (diff-drive), gantry, scara — all slew-limited, self-animating; connect()/mount() for contraptions, applyTextures() for fetch_texture PBR sets');
})();
