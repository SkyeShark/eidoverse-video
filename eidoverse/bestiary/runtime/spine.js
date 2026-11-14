// spine.js (A1, the runtime spine; ROADMAP §3 A1, PARITY_MATRIX A7 / A8): THE ONE CONTRACT on every creature, over its own motion.
// bestiary.js create() calls attachSpine() once the creature's api exists; the old makeCreature controls come back on every base:
//
//   c.speed(0.03); c.turn(0.4);              // m/s and rad/s at the creature's size (the scheduler eases them; the old creator's
//                                            // c.speed = v property is the compat adapter's (A2) to map onto these calls)
//   c.walkTo(x, z, { speed, heading });      // a point of the group's parent; returns the time it ends (planned cases)
//   c.setHeading(a);                         // radians in the parent's frame (0 faces +z): a turn on the spot
//   c.fly(alt); c.land();                    // the body lifts to alt metres (pitch into the climb, bank into turns), legs tuck
//   c.anchor('head' | 'chest' | 'back' | 'hips' | 'wristL' | 'wristR')   // the old names on each base's sockets (RoboticsKit)
//   c.parts('cuticle' | 'eye' | 'arm3' | 'socket_crown' | ...)           // nodes by name, material kind, chain or cyborg kind
//   c.say('Some words'); c.talking = true; c.setTalkEnvelope((t) => amp)  // the talk rig by the head: the jaw where the head has
//                                            // one, the beetle's mandibles and palps, the octopus's siphon + mantle pulse, VRM visemes
//   c.idles({ blink, flick, tailWhip });     // idle behaviours per anatomy (lids, ears / antennae, tail), seeded, pure in t
//   c.pose()                                 // { x, z, heading } in the parent's frame
//
// THE CASES (locomotion.js): hexapod (the beetle) and limbed (any base on leg chains: quad / biped) carry the planned controls;
// 'salamander' (the axolotl's own walk and swim, axolotl.js) is driven here closed-loop (its controls are live commands: walkTo
// steers and stops within its radius, a final heading is a timed turn); 'radial' (the octopus) GLIDES: a body-only scheduler (no
// support slots) carries its root, its arms re-solve their resting paths on the ground under the moving crown every frame (the
// tentacle's contact stepping is the tentacle solver's, for grafted tentacle LEGS; the octopus's own crawl is a later round).
//
// UNUSED, IT IS NOTHING: every pass below runs only once its call has been made (a flag per feature), so a creature whose scene never
// calls the new api renders the very frames it did (the gate: octopus and beetle 0 px, tests/g01_identity.mjs).
import { gaitScheduler } from './locomotion.js';
import { readConstraints, constraintPass } from './constraints.js';

const THREE = globalThis.THREE;

function hash01(i, seed) {
    let x = (Math.imul(i | 0, 0x9E3779B1) ^ Math.imul(seed | 0, 0x85EBCA77)) >>> 0;
    x ^= x >>> 16; x = Math.imul(x, 0x7FEB352D) >>> 0; x ^= x >>> 15; x = Math.imul(x, 0x846CA68B) >>> 0;
    x ^= x >>> 16;
    return (x >>> 8) / 16777216;
}
const smooth = (x) => { const u = Math.min(1, Math.max(0, x)); return u * u * (3 - 2 * u); };

// THE OLD ANCHOR NAMES on each base: the first socket that exists, else a joint, else the geometric rule (the front-most chain tip
// on that side: +X is the creature's left)
const ANCHORS = {
    head: ['socket_head_top', 'socket_crown', 'socket_pronotum_top', '#head'],
    chest: ['socket_chest', 'socket_crown', '#thorax', '#spine_04', '#spine_03'],
    back: ['socket_back_mid', 'socket_back_shell', 'socket_back_0', 'socket_back_1', 'socket_mantle_apex'],
    hips: ['socket_hips', 'socket_tail_base', 'socket_abdomen_tip', '#pelvis', '#abdomen_0', '#body', '#root'],
    wristL: ['socket_wrist_L', 'socket_forepaw_L', 'socket_claw_f_L'],
    wristR: ['socket_wrist_R', 'socket_forepaw_R', 'socket_claw_f_R'],
};

export function attachSpine(api, ctx) {
    const { gltf, sp, opts = {}, bones, sockets, group } = ctx;
    const seed = opts.seed ?? 1;
    const V3 = THREE.Vector3, Q = THREE.Quaternion;
    const root = bones.get('root');
    const P = root?.parent || group;
    const used = { glide: false, fly: false, talk: false, idles: false, mission: false };
    let now = 0;
    const scaleOf = () => group.scale.x || 1;

    // ------------------------------------------------------------------------------------------------ locomotion
    const mo = ctx.locomotion || null;                    // hexapod / limbed: { controls, legBones, rest, root }
    // (its own speed / turn / walkTo already on the api; not when the limbed case drives its rig instead)
    const salamander = sp.motion === 'salamander' && !mo ? api : null;
    const salCtl = salamander ? { speed: api.speed, turn: api.turn, walkTo: api.walkTo } : null;
    let glide = null;
    if (sp.motion === 'radial' && root) {
        // the octopus's body-only scheduler: no support slots, its root carried; walkSpeed 4 cm/s, turnRate 0.5 rad/s
        const root0 = { p: root.position.clone(), q: root.quaternion.clone() };
        const g = gaitScheduler(group, root0, [], { duty: 0.5, stride: 1, fMin: 0, fMax: 1, lift: 0,
            walkSpeed: 0.04, turnRate: 0.5, ...(sp.glide || {}), ...(opts.glide || {}) });
        g.setFrameNode(P);
        glide = { g, root0 };
    }
    const ctl = mo?.controls || glide?.g.controls || null;
    const mission = { target: null, heading: null, turn: null };
    const salPose = () => {
        // the axolotl's BODY POINT in the group's parent frame: its pivot (the turn's centre, gait.pivot TL ahead of the root, half
        // way between the girdles: the point its walkTo steers and a turn on the spot keeps still), from its probe (the root in the
        // group's frame) and its heading
        const pr = api.gait?.probe?.();
        if (!pr) return null;
        group.updateMatrixWorld(true);
        const M = group.matrix.clone();
        const piv = api.axolotl?.motion?.controls?.pivot ?? 0;
        const p = new V3(pr.root[0] + Math.sin(pr.psi) * piv, 0, pr.root[2] + Math.cos(pr.psi) * piv).applyMatrix4(M);
        const o = new V3().applyMatrix4(M), d = new V3(Math.sin(pr.psi), 0, Math.cos(pr.psi)).applyMatrix4(M).sub(o);
        return { x: p.x, z: p.z, heading: Math.atan2(d.x, d.z), mode: pr.mode, v: pr.v };
    };
    const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));
    Object.assign(api, {
        speed(v) {
            if (glide) used.glide = true;
            mission.target = null; mission.heading = null;
            return salamander ? salCtl.speed(v) : ctl?.speed(v);
        },
        turn(w) {
            if (glide) used.glide = true;
            mission.target = null; mission.heading = null;
            return salamander ? salCtl.turn(w) : ctl?.turn(w);
        },
        walkTo(x, z, o = {}) {
            if (typeof o === 'number') o = { speed: o };
            if (glide) used.glide = true;
            if (salamander) {
                // closed loop: its steering walk, a tight arrival radius (the gate's 1 cm at any size: 4 mm in the parent's
                // metres), then a stop and (o.heading) a turn to it
                used.mission = true;
                const r = (o.radius ?? 0.004) / scaleOf();
                mission.target = { x, z, r: o.radius ?? 0.004 };
                mission.heading = o.heading ?? null;
                mission.turn = null;
                mission.arrived = null;
                mission.rate = o.turnRate ?? 0.3;
                return salCtl.walkTo(x, z, { ...o, radius: r });
            }
            return ctl?.walkTo(x, z, o);
        },
        setHeading(a, o = {}) {
            if (glide) used.glide = true;
            if (salamander) {
                used.mission = true;
                mission.target = null;
                mission.heading = a;
                mission.turn = null;
                mission.rate = o.turnRate ?? 0.3;
                return null;
            }
            return ctl?.setHeading?.(a, o);
        },
        pose() { return salamander ? salPose() : ctl?.pose?.() ?? null; },
        moving() { return salamander ? (salPose()?.mode === 'walk' || !!mission.target || mission.heading != null) : !!ctl?.moving?.(); },
    });
    function missionStep(t, dtFrame) {
        // (the axolotl) arrival: inside the radius -> stop (speed(0) clears its steer); then the heading turn: turn at the rate
        // until the error is under half a frame's turn, then stop (its turn is not eased: the error stays under 1 deg at 30 fps)
        const ps = salPose();
        if (!ps) return;
        if (mission.target) {
            const d = Math.hypot(mission.target.x - ps.x, mission.target.z - ps.z);
            if (d <= mission.target.r) { mission.target = null; mission.arrived = t; salCtl.speed(0); }
            return;
        }
        // the heading's turn waits one settling cycle after the arrival (the gait's clock at its settle rate: stride / (v_settle x
        // speed), 2.25 s): every foot is home under the body before it turns (a turn begun on the stop's last plants overreached
        // a hind limb by 2 mm x4: A1 g02's axolotl at life, 0.49 mm of slide)
        const G = sp.gait || {};
        const wait = mission.arrived != null ? (G.stride ?? 0.18) / Math.max(1e-6, (G.v_settle ?? 1) * (G.speed ?? 0.08)) : 0;
        if (mission.turn == null && mission.arrived != null && t < mission.arrived + wait) return;
        if (mission.heading != null && (mission.turn != null || ps.mode !== 'walk')) {
            const err = wrap(mission.heading - ps.heading), rate = mission.rate ?? 0.3;
            if (mission.turn == null) {
                if (Math.abs(err) < 0.5 * rate * dtFrame) { mission.heading = null; return; }
                mission.turn = Math.sign(err) * rate;
                salCtl.turn(mission.turn);
            } else if (Math.abs(err) < 0.5 * rate * dtFrame || Math.sign(err) !== Math.sign(mission.turn)) {
                salCtl.turn(0);
                mission.turn = null; mission.heading = null;
            }
        }
    }

    // ------------------------------------------------------------------------------------------------ fly / land
    // the altitude a schedule of eased moves: each fly(alt) / land() from the altitude it interrupts, at 0.5 m/s at the creature's
    // size (at least 1.2 s); the attitude: nose up into a climb (0.4 rad per m/s, at most 0.35), bank into the body's turn
    // (-0.4 x the yaw rate, at most 0.5); a soar bob; the legs tuck toward their rest lie as the body leaves the ground
    const flyCmds = [{ t: -1e9, alt: 0, dur: 1 }];
    const altAt = (t) => {
        let a = 0;
        for (const c of flyCmds) {
            if (c.t > t) break;
            const s = smooth((t - c.t) / c.dur);
            a = c.from + (c.alt - c.from) * s;
            if (c.t === -1e9) a = 0;
        }
        return a;
    };
    const flyTo = (alt) => {
        used.fly = true;
        const from = altAt(now);
        while (flyCmds.length > 1 && flyCmds[flyCmds.length - 1].t > now) flyCmds.pop();
        flyCmds.push({ t: now, from, alt, dur: Math.max(1.2, Math.abs(alt - from) / (0.5 * scaleOf())) });
    };
    api.fly = (alt = 1.6 * scaleOf(), speed) => {
        flyTo(alt);
        if (speed != null) api.speed(speed);
    };
    api.land = () => flyTo(0);
    Object.defineProperty(api, 'flying', { get: () => altAt(now) > 1e-4, configurable: true });
    const legRest = mo?.rest || null;
    const legBones = mo?.legBones || [];
    function flyPost(t) {
        const alt = altAt(t);
        if (alt <= 0 && altAt(t - 0.05) <= 0) return;
        const k = 1 / scaleOf();
        const climb = (altAt(t + 0.05) - altAt(t - 0.05)) / 0.1;
        let yawRate = 0;
        const p1 = api.pose?.(), hNow = p1?.heading;
        if (ctl?.pose && hNow != null) {
            const h0 = ctl.pose(Math.max(0, t - 0.1)).heading;
            yawRate = wrap(hNow - h0) / 0.1;
        }
        const pitch = Math.max(-0.3, Math.min(0.35, 0.4 * climb / scaleOf()));
        const bank = Math.max(-0.5, Math.min(0.5, -0.4 * yawRate));
        const air = smooth(alt / (0.08 * scaleOf()));
        // the legs toward their rest lie (their bind / stand rotations) as the feet leave the ground
        if (legRest && air > 0) {
            for (const b of legBones) {
                const r = legRest.get(b.name);
                if (r) b.quaternion.slerp(r.q, air);
            }
        }
        if (root) {
            const bob = air * 0.02 * scaleOf() * Math.sin(3.1 * t);
            root.position.y += (alt + bob) * k;
            const fwd = new V3(0, 0, 1).applyQuaternion(root.quaternion);
            const lat = new V3().crossVectors(new V3(0, 1, 0), fwd).normalize();
            root.quaternion.premultiply(new Q().setFromAxisAngle(fwd.normalize(), bank * air))
                .premultiply(new Q().setFromAxisAngle(lat, -pitch * air));
        }
    }

    // ------------------------------------------------------------------------------------------------ talk
    // the envelope: say() the old creator's syllables (~4.3 Hz gates with a slower amplitude, energy 0.85, duration from the
    // words: max(1.2, words / 2.6) s), talking = true without end, setTalkEnvelope(fn(t) -> 0..1) an audio envelope; pure in t
    let talk = null;
    const sylPhase = 6.2832 * hash01(911, seed);
    const envAt = (t) => {
        if (!talk) return 0;
        if (talk.env) return Math.max(0, Math.min(1, talk.env(t) || 0));
        if (t < talk.t0 || t > talk.until) return 0;
        const E = talk.energy ?? 0.85;
        const sy = Math.sin(t * 27.2 + sylPhase) * 0.5 + 0.5;
        const am = 0.55 + 0.45 * Math.sin(t * 7.31 + sylPhase * 1.7);
        const fade = smooth((t - talk.t0) / 0.08) * smooth((talk.until - t) / 0.12);
        return fade * E * Math.max(0, sy * am - 0.08);
    };
    api.say = (o) => {
        used.talk = true;
        if (typeof o === 'string') o = { duration: Math.max(1.2, o.split(/\s+/).filter(Boolean).length / 2.6) };
        talk = { t0: now, until: now + ((o && o.duration) ?? 3), energy: (o && o.energy) ?? 0.85, env: (o && o.envelope) || null };
        return api;
    };
    Object.defineProperty(api, 'talking', {
        get: () => !!talk && (talk.env != null || now <= talk.until),
        set: (v) => { used.talk = true; talk = v ? { t0: now, until: Infinity, energy: 0.85, env: null } : null; },
        configurable: true,
    });
    api.setTalkEnvelope = (fn) => { used.talk = true; talk = fn ? { t0: -Infinity, until: Infinity, env: fn } : null; return api; };
    api.talkEnvelope = envAt;
    // the talk rig by the head (sp.talk overrides: { jaw: name, axis, max (rad) }):
    const talkRig = (() => {
        const T = sp.talk || {};
        const jaw = bones.get(T.jaw || 'jaw');
        if (jaw) return { kind: 'jaw', b: jaw, axis: new V3(...(T.axis || [0, 0, 1])), max: T.max ?? 0.30 };
        const mL = bones.get('mandible_L'), mR = bones.get('mandible_R');
        if (mL && mR) {
            return { kind: 'mandibles', bs: [[mL, 1], [mR, 1]], max: T.max ?? 0.30,
                palps: ['palp_max_0_L', 'palp_max_0_R', 'palp_lab_0_L', 'palp_lab_0_R'].map((n) => bones.get(n)).filter(Boolean) };
        }
        const funnel = bones.get('funnel_1'), mantle = bones.get('mantle_1');
        if (funnel || mantle) return { kind: 'siphon', funnel, mantle };
        return null;
    })();
    Object.defineProperty(api, 'hasJaw', { get: () => talkRig?.kind === 'jaw' || talkRig?.kind === 'mandibles', configurable: true });
    const Z = new V3(0, 0, 1);
    function talkPost(t) {
        const e = envAt(t);
        if (!talkRig || e <= 0) return;
        if (talkRig.kind === 'jaw') {
            talkRig.b.quaternion.multiply(new Q().setFromAxisAngle(talkRig.axis, e * talkRig.max));
        } else if (talkRig.kind === 'mandibles') {
            // (+ about each mandible's own z opens it: tests/g04_talk_open.mjs, the tips' gap +; the first sign closed them 50 mm x10)
            for (const [b, s] of talkRig.bs) b.quaternion.multiply(new Q().setFromAxisAngle(Z, s * e * talkRig.max));
            talkRig.palps.forEach((b, i) => b.quaternion.multiply(new Q().setFromAxisAngle(Z, 0.25 * e * Math.sin(t * 31 + i))));
        } else if (talkRig.kind === 'siphon') {
            // the octopus's voice: the funnel's tip opens and contracts with the envelope (a jet's pulse), the mantle draws in
            if (talkRig.funnel) talkRig.funnel.scale.multiply(new V3(1.0, 1.0 + 0.45 * e, 1.0 + 0.45 * e));
            if (talkRig.mantle) talkRig.mantle.scale.multiply(new V3(1.0, 1.0 - 0.05 * e, 1.0 - 0.05 * e));
        }
    }

    // ------------------------------------------------------------------------------------------------ idles
    // per anatomy, each a seeded event schedule (pure in t): BLINK (lid joints: the upper lid down over 70 ms, up over 130 ms,
    // every 2-6 s), FLICK (an ear or antenna chain: a quick twitch every 3-9 s), TAIL WHIP (the tail chain: a travelling flick every
    // 5-12 s). api.idles() lists what this base has; api.idles({ blink: true, ... }) turns them on (off by default: every base's
    // own motion already carries its life)
    const chainsBy = (re) => (sp.chains || []).filter((c) => re.test(c.kind)).map((c) => c.joints.map((n) => bones.get(n)).filter(Boolean));
    const IDL = {
        blink: ['lid_upper_L', 'lid_upper_R'].map((n) => bones.get(n)).filter(Boolean),
        flick: chainsBy(/^(ear|antenna)/),
        tailWhip: chainsBy(/^tail/),
    };
    const idleOn = { blink: false, flick: false, tailWhip: false };
    api.idles = (o) => {
        if (o == null) return Object.fromEntries(Object.entries(IDL).map(([k, v]) => [k, v.length > 0]));
        if (o === true) o = { blink: true, flick: true, tailWhip: true };
        for (const k of Object.keys(idleOn)) if (o[k] != null) idleOn[k] = !!o[k] && IDL[k].length > 0;
        used.idles = Object.values(idleOn).some(Boolean);
        return api;
    };
    if (opts.idles) api.idles(opts.idles);
    // an event's weight at t: events at seeded intervals in [lo, hi] from t = 0 (the k-th event's time a cumulative sum)
    const eventW = (t, key, lo, hi, attack, release) => {
        let te = 0.5 + (hi - lo) * hash01(key, seed);
        for (let k = 0; k < 4096 && te <= t + release; k++) {
            if (t >= te && t <= te + attack + release) {
                const u = t - te;
                return { w: u < attack ? smooth(u / attack) : 1 - smooth((u - attack) / release), k };
            }
            te += lo + (hi - lo) * hash01(key * 7919 + k, seed);
        }
        return { w: 0, k: 0 };
    };
    function idlePost(t) {
        if (idleOn.blink) {
            const { w } = eventW(t, 1, 2.0, 6.0, 0.07, 0.13);
            if (w > 0) for (const b of IDL.blink) b.quaternion.multiply(new Q().setFromAxisAngle(Z, (sp.idles?.blinkAngle ?? 0.45) * w));
        }
        if (idleOn.flick) {
            IDL.flick.forEach((ch, i) => {
                const { w, k } = eventW(t, 2 + i, 3.0, 9.0, 0.06, 0.22);
                if (w <= 0) return;
                const s = (hash01(97 + k, seed + i) - 0.5) * 2;
                ch.forEach((b, j) => b.quaternion.multiply(new Q().setFromAxisAngle(Z, 0.25 * s * w / (1 + j))));
            });
        }
        if (idleOn.tailWhip) {
            for (const ch of IDL.tailWhip) {
                const n = ch.length;
                const { w, k } = eventW(t, 5, 5.0, 12.0, 0.15, 0.55);
                if (w <= 0) continue;
                const s = hash01(131 + k, seed) < 0.5 ? -1 : 1;
                ch.forEach((b, j) => {
                    const lag = j / n;
                    const a = s * 0.14 * w * Math.sin(Math.PI * Math.min(1, Math.max(0, w * 1.3 - 0.3 * lag)));
                    b.quaternion.multiply(new Q().setFromAxisAngle(new V3(0, 1, 0), a));
                });
            }
        }
    }

    // ------------------------------------------------------------------------------------------------ anchors and parts
    const byName = new Map();
    group.traverse((o) => { if (o.name && !byName.has(o.name)) byName.set(o.name, o); });
    api.anchor = (n) => {
        for (const c of ANCHORS[n] || [n]) {
            const o = c.startsWith('#') ? bones.get(c.slice(1)) : (sockets[c] || byName.get(c));
            if (o) return o;
        }
        if (n === 'wristL' || n === 'wristR') {
            // the front-most chain tip on that side (+X the creature's left): the octopus's first arm on each side
            const side = n === 'wristL' ? 'L' : 'R';
            let best = null, bz = -Infinity;
            group.updateMatrixWorld(true);
            for (const c of sp.chains || []) {
                if (c.side !== side || !c.tip || !sockets[c.tip]) continue;
                const z = sockets[c.tip].getWorldPosition(new V3()).applyMatrix4(group.matrixWorld.clone().invert()).z;
                if (z > bz) { bz = z; best = sockets[c.tip]; }
            }
            return best;
        }
        return null;
    };
    // a mesh's material kind as the glb wrote it (its JSON material's extras.bestiary: the runtime's builders replace the material
    // object, so the kind is read through the parser's association of the mesh with its primitive)
    const kindOf = (o) => {
        const as = gltf?.parser?.associations?.get(o);
        if (!as || as.meshes === undefined) return null;
        const idx = gltf.parser.json.meshes[as.meshes]?.primitives?.[as.primitives ?? 0]?.material;
        return idx == null ? null : gltf.parser.json.materials?.[idx]?.extras?.bestiary ?? null;
    };
    api.parts = (n) => {
        const out = new Set();
        group.traverse((o) => {
            if (o.name === n) out.add(o);
            if (!o.isMesh) return;
            if (kindOf(o) === n || o.material?.userData?.bestiary === n || o.userData?.bestiaryAxolotl === n) out.add(o);
        });
        const ch = (sp.chains || []).find((c) => c.name === n || c.label === n);
        if (ch) for (const j of ch.joints) { const b = bones.get(j); if (b) out.add(b); }
        for (const p of api.cyborgParts || []) if (p?.kind === n && p.group) out.add(p.group);
        return [...out];
    };

    // ------------------------------------------------------------------------------------------------ node constraints
    const cons = constraintPass(group, readConstraints(group, gltf));

    // ------------------------------------------------------------------------------------------------ the update wrap
    const inner = api.update;
    let lastT = null;
    api.update = (t) => {
        const dtFrame = lastT == null ? 1 / 30 : Math.max(1e-4, Math.abs(t - lastT));
        lastT = t;
        now = t;
        if (ctl) ctl.now = t;
        if (used.mission) missionStep(t, dtFrame);
        if (glide && (used.glide || used.fly)) {
            // the octopus's root on the glide's body before its arms solve (they lay their paths from the crown as it stands)
            const S = glide.g.integrate(t + glide.g.AHEAD), b = glide.g.bodyM(S, t);
            root.position.copy(b.p);
            root.quaternion.copy(b.q);
            group.updateMatrixWorld(true);
        }
        inner(t);
        let touched = false;
        if (used.fly) { flyPost(t); touched = true; }
        if (used.talk) { talkPost(t); touched = true; }
        if (used.idles) { idlePost(t); touched = true; }
        if (cons) { group.updateMatrixWorld(true); cons.solve(); touched = true; }
        if (touched) group.updateMatrixWorld(true);
    };
    api.spine = { used, constraints: cons, talkRig, idleRigs: IDL, glide, case: mo?.case || sp.motion };
    return api;
}

// =============================================================================================== THE VRM SPINE (the human, B1's path)
// The same contract on a VRM walked by the house's EidoverseRobotController (locomotion.js vrmLocomotion): talk through the VRM's
// visemes ('aa' with the envelope, 'oh' at a third of it), the blink idle through its 'blink' expression, the anchors on the
// humanoid bones. Call spine.update(t) BEFORE ctrl.update(t, dt) each frame (its carrot and its expressions; vrm.update applies them)
export function vrmSpine(vrm, ctrl, loco, opts = {}) {
    const seed = opts.seed ?? 1;
    let talk = null, now = 0, blink = false;
    const sylPhase = 6.2832 * hash01(911, seed);
    const envAt = (t) => {
        if (!talk) return 0;
        if (talk.env) return Math.max(0, Math.min(1, talk.env(t) || 0));
        if (t < talk.t0 || t > talk.until) return 0;
        const sy = Math.sin(t * 27.2 + sylPhase) * 0.5 + 0.5, am = 0.55 + 0.45 * Math.sin(t * 7.31 + sylPhase * 1.7);
        return smooth((t - talk.t0) / 0.08) * smooth((talk.until - t) / 0.12) * (talk.energy ?? 0.85) * Math.max(0, sy * am - 0.08);
    };
    const H = (n) => vrm.humanoid?.getNormalizedBoneNode?.(n) || null;
    const api = {
        ...loco.controls,
        anchor(n) {
            return { head: H('head'), chest: H('chest'), back: H('upperChest') || H('chest'), hips: H('hips'),
                wristL: H('leftHand'), wristR: H('rightHand') }[n] || vrm.scene.getObjectByName(n) || null;
        },
        parts(n) { const out = []; vrm.scene.traverse((o) => { if (o.name === n || o.material?.userData?.bestiary === n) out.push(o); }); return out; },
        say(o) {
            if (typeof o === 'string') o = { duration: Math.max(1.2, o.split(/\s+/).filter(Boolean).length / 2.6) };
            talk = { t0: now, until: now + ((o && o.duration) ?? 3), energy: (o && o.energy) ?? 0.85, env: (o && o.envelope) || null };
            return api;
        },
        get talking() { return !!talk && (talk.env != null || now <= talk.until); },
        set talking(v) { talk = v ? { t0: now, until: Infinity, energy: 0.85, env: null } : null; },
        setTalkEnvelope(fn) { talk = fn ? { t0: -Infinity, until: Infinity, env: fn } : null; return api; },
        get hasJaw() { return true; },
        idles(o) { if (o == null) return { blink: true, flick: false, tailWhip: false }; blink = !!(o === true || o.blink); return api; },
        fly() { console.warn('[Bestiary] fly: the human walks (the controller has no flight)'); },
        land() {},
        update(t) {
            now = t;
            loco.controls.step(t);
            const em = vrm.expressionManager;
            if (!em) return;
            if (talk) { const e = envAt(t); em.setValue('aa', e); em.setValue('oh', e / 3); }
            if (blink) {
                let te = 0.5 + 4 * hash01(1, seed), w = 0;
                for (let k = 0; k < 4096 && te <= t + 0.13; k++) {
                    if (t >= te && t <= te + 0.2) { const u = t - te; w = u < 0.07 ? smooth(u / 0.07) : 1 - smooth((u - 0.07) / 0.13); break; }
                    te += 2 + 4 * hash01(7919 + k, seed);
                }
                em.setValue('blink', w);
            }
        },
    };
    return api;
}
