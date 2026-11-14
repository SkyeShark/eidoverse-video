// locomotion.js (A1, the runtime spine; work/bestiary/research/parity/ROADMAP.md §3 A1, CROSSBREED_DESIGN.md §4.5): ONE GAIT
// SCHEDULER for every base that walks on limbs, and the STEP SOLVERS per anatomy that realise each step.
//
//   * THE SCHEDULER (gaitScheduler): the body's controls (speed in m/s and turn in rad/s at the creature's size, piecewise constant
//     targets eased over EASE s, from a schedule or the api's calls) integrated on one fixed grid from t = 0 (cached: a --jump frame
//     equals the frame reached step by step); the gait's cycles the integral of the step rate, which follows the FASTEST FOOT (each
//     support limb's rest place moving with the body's speed and turn) over the stride, never under fMin while moving, one settling
//     cycle after a stop; each support limb SLOT's phase the cycles plus its offset (the chain record's label in the gait's phase
//     table, else the wave rule: the rank from the front x (1 - duty), the right side half a cycle on: the hexapod's wave, a
//     quadruped's lateral sequence at duty 0.75, a biped's alternation); a stance foot stays where it touched down (the body's pose
//     at its stance's `center`), a swing foot travels from plant to plant on an eased arc lifted with the step's length.
//     This is the B11 hexapod's machinery (moved here from bestiary.js, its arithmetic in the same order: the beetle's motion is the
//     same numbers, h11's records byte-identical), generalised from six named legs to the chain records' support slots.
//   * THE STEP SOLVERS (makeSolvers), chosen per slot by its ANATOMY (the chain record's `anatomy`, else the family's default):
//       tarsus       an arthropod leg: the coxa yaws the leg's plane toward the foot (clamped), femur + tibia a hinge-kept two-bone
//                    IK in that plane, the tarsus lying as it rests turned with the foot's heading (BEETLE_PLAN §6.4: the B11 code);
//       plantigrade  a limbed leg standing on its sole (the human, the axolotl): upper + lower a hinge-kept two-bone IK (the knee's
//                    plane carried from the bind, its included angle from the reach), the ankle's rest lie turned with the foot's
//                    heading so the contact joint lands on the plant; the heel lifts about the contact through the swing (toe-off);
//       digitigrade  the same on the toes (a canid's hind, a bird): the long metapodial keeps its rest pitch, flexes through the swing;
//       paw          digitigrade with the pastern / metacarpus as the last segment (a canid's fore);
//       mech         the two-bone hinge solve with no flesh limits; its actuators follow through the node-constraint pass
//                    (constraints.js: aim / copy-rotation / piston);
//       tentacle     a path solve: the chain laid at its bind lengths along a smooth curve from its root (its rest direction) to the
//                    contact on the ground (arriving flat), the moving contact target the scheduler's plant (CROSSBREED §4.5).
//   * THE CASES: hexapodMotion (the stag beetle: 6 tarsus slots + its life and its mech leg's pistons), limbedMotion (any base whose
//     support chains rest on the ground: quad or biped, plantigrade / digitigrade / paw / mech), and vrmLocomotion (the human's VRM
//     walk: the house's EidoverseRobotController owns the gait, feet and IK; this maps the api onto its waypoints). The axolotl's
//     salamander walk (axolotl.js, the same design with its own sprawl IK and swim) is registered as the 'sprawl' case in spine.js.
//
// The controls' api on every scheduler (gaitScheduler(...).controls): speed(v), turn(w), walkTo(x, z, { speed, turnRate, heading }),
// setHeading(a, { turnRate }). walkTo / setHeading are PLANNED exactly on the eased controls (each phase long enough for its ramps to
// close: the turn's integral is the bearing change, the walk's the distance), so the body arrives on the point and on the heading to
// the integration grid's precision (the B11 open-loop plan let the walk's speed ramp start under the turn's ramp-down: a curved
// start, 4-12 mm off at hero scale; tests/g03_walkto.mjs measures both).
const THREE = globalThis.THREE;

export function hash01(i, seed) {
    // lowbias32 (the forge's hash), to [0, 1) (bestiary.js's own, the same bits)
    let x = (Math.imul(i | 0, 0x9E3779B1) ^ Math.imul(seed | 0, 0x85EBCA77)) >>> 0;
    x ^= x >>> 16; x = Math.imul(x, 0x7FEB352D) >>> 0; x ^= x >>> 15; x = Math.imul(x, 0x846CA68B) >>> 0;
    x ^= x >>> 16;
    return (x >>> 8) / 16777216;
}

export const ZAX = new THREE.Vector3(0, 0, 1);         // a joint's fold axis in its own frame (families/arthropod.py)

// =============================================================================================== frame ops (P's frame)
// Every solver works in P's frame: the glb's scene node that parents the root joint (everything below is in its frame). Pinv is
// refreshed each frame (a scene moves, turns or scales the group after create()).
export function frameOps(group, P) {
    const V3 = THREE.Vector3, Q = THREE.Quaternion, M4 = THREE.Matrix4;
    group.updateMatrixWorld(true);
    const ops = {
        P,
        Pinv: new M4().copy(P.matrixWorld).invert(),
        // scratch (shared as the B11 hexapod shared them: the same values in the same order)
        vA: new V3(), vB: new V3(), vC: new V3(), qa: new Q(), qb: new Q(), mA: new M4(),
    };
    ops.refresh = () => { ops.Pinv.copy(P.matrixWorld).invert(); };
    ops.inP = (b) => new V3().setFromMatrixPosition(new M4().multiplyMatrices(ops.Pinv, b.matrixWorld));
    ops.qInP = (b) => new Q().setFromRotationMatrix(new M4().multiplyMatrices(ops.Pinv, b.matrixWorld));
    ops.setWorldQ = (b, qWorldP) => {                   // a bone's rotation in P's frame -> its local quaternion
        const pq = ops.qInP(b.parent);
        b.quaternion.copy(pq.invert().multiply(qWorldP));
        b.updateMatrixWorld(true);
    };
    ops.aim = (b, from, to, dirWanted) => {             // turn b so the direction from -> to becomes dirWanted (P's frame)
        const cur = ops.vA.copy(to).sub(from).normalize();
        ops.qa.setFromUnitVectors(cur, dirWanted);
        ops.setWorldQ(b, ops.qa.multiply(ops.qInP(b)));
    };
    return ops;
}

// =============================================================================================== THE GAIT SCHEDULER
// legs: [{ N (the foot's rest place in the root's frame, a Vector3), off (phase offset), center (where in the stance the foot stands
// under its rest place: 0.5 mid-stance) }]; G: { duty, stride, fMin, fMax, lift } (the glb's units, cycles per second);
// root0: { p, q } the root's rest pose in P's frame; opts.walk.schedule [[t, v, w], ...]
export function gaitScheduler(group, root0, legs, G, opts = {}) {
    const V3 = THREE.Vector3, Q = THREE.Quaternion, M4 = THREE.Matrix4;
    const duty = G.duty, stride0 = G.stride, fMax = G.fMax, lift = G.lift;
    const UP = new V3(0, 1, 0);
    // the controls: piecewise constant targets eased over EASE seconds (no pops), a schedule given or the API's calls
    const EASE = 0.6, DT = 1 / 120, AHEAD = 2.0;
    const sched = (opts.walk?.schedule || []).map(([t, v, w]) => ({ t, v, w }));
    if (!sched.length || sched[0].t > 0) sched.unshift({ t: 0, v: 0, w: 0 });
    const ctl = (t) => {
        // the eased speed and turn at time t (each change ramps over EASE from the value it interrupts)
        let v = sched[0].v, w = sched[0].w;
        for (let i = 1; i < sched.length && sched[i].t <= t; i++) {
            const s = Math.min(1, (t - sched[i].t) / EASE), e = s * s * (3 - 2 * s);
            const vPrev = v, wPrev = w;
            v = vPrev + (sched[i].v - vPrev) * e;
            w = wPrev + (sched[i].w - wPrev) * e;
        }
        return { v, w };
    };
    const scaleOf = () => group.scale.x || 1;
    // the step rate follows the FASTEST FOOT: a foot at its rest place (x, z) in the root's frame (its rest rotation is the
    // identity) moves at (w z, vg - w x) while the body walks at vg and turns at w, so in a turn no foot strides further than
    // the stride per cycle (the outer ones at it, the inner shorter); walking straight it is the body's speed; turning on the
    // spot the farthest foot's (B11, b10_notes restart 3)
    // (A1) G.turnStride: a turn's share counted 1 / turnStride (a turning foot takes shorter steps: a sprawled limb reaches less
    // across than along; 1 keeps the B11 law, the beetle's, exactly: x / 1 is x)
    const TS = G.turnStride ?? 1;
    const footSpeed = (vg, w) => {
        let m = Math.abs(vg);
        for (const L of legs) m = Math.max(m, Math.hypot(w * L.N.z / TS, vg - w * L.N.x / TS));
        return m;
    };
    // the step rate's floor: a slow walk takes shorter steps, never slower ones, and when the body comes to rest the legs keep
    // stepping at it for ONE more cycle, so every swing foot lands on its rest place under the stopped body
    const fMin = G.fMin ?? 1.0;
    // the integrated body: heading th, position x z (the glb's units), the gait's cycles c, sampled every DT; S.starts the cycles'
    // value at every start from rest. CACHED: the samples grow with t on the one fixed grid from 0 and start over when a command
    // changes the schedule or the size; a frame costs its new samples only
    let cache = null, schedVersion = 0;
    function integrate(tEnd) {
        const n = Math.max(2, Math.ceil(tEnd / DT) + 1);
        const k = 1 / scaleOf();
        if (!cache || cache.version !== schedVersion || cache.k !== k) {
            cache = { version: schedVersion, k, len: 0, cap: 0, starts: [], s: { x: 0, z: 0, th: 0, c: 0, owe: 0, fPrev: 0 } };
        }
        if (cache.len < n) {
            if (cache.cap < n) {
                const cap = Math.max(n, 2 * cache.cap, 512);
                for (const key of ['T', 'X', 'Z', 'TH', 'C']) {
                    const a = new Float64Array(cap);
                    if (cache[key]) a.set(cache[key].subarray(0, cache.len));
                    cache[key] = a;
                }
                cache.cap = cap;
            }
            const s = cache.s, T = cache.T, X = cache.X, Z = cache.Z, TH = cache.TH, C = cache.C;
            for (let i = cache.len; i < n; i++) {
                const t = i * DT;
                T[i] = t; X[i] = s.x; Z[i] = s.z; TH[i] = s.th; C[i] = s.c;
                const { v, w } = ctl(t);
                const vg = v * k;                                   // metres per second at its size -> the glb's units
                const fm = Math.min(fMax, footSpeed(vg, w) / stride0);
                let f = 0;
                if (fm > 1e-6) {
                    f = Math.max(fm, fMin);
                    s.owe = 1.0;
                } else if (s.owe > 0) {
                    f = Math.min(fMin, s.owe / DT);                // the settling cycle, ending on its exact count
                    s.owe -= f * DT;
                }
                if (f > 0 && s.fPrev === 0) cache.starts.push({ i, c: s.c });
                s.fPrev = f;
                s.x += Math.sin(s.th) * vg * DT; s.z += Math.cos(s.th) * vg * DT; s.th += w * DT; s.c += f * DT;
            }
            cache.len = n;
        }
        return { T: cache.T, X: cache.X, Z: cache.Z, TH: cache.TH, C: cache.C, n,
            starts: cache.starts.filter((e) => e.i < n).map((e) => e.c) };
    }
    const at = (S, A, t) => {
        const u = Math.max(0, Math.min(S.n - 1, t / DT)), i = Math.min(S.n - 2, Math.floor(u)), f = u - i;
        return A[i] + (A[i + 1] - A[i]) * f;
    };
    const timeOfCycle = (S, c) => {          // the first time the cycles reach c (they never fall), clamped to the sampled span
        if (c <= S.C[0]) return 0;
        if (c >= S.C[S.n - 1]) return S.T[S.n - 1];
        let lo = 0, hi = S.n - 1;
        while (hi - lo > 1) { const m = (lo + hi) >> 1; if (S.C[m] < c) lo = m; else hi = m; }
        const d = S.C[hi] - S.C[lo];
        return S.T[lo] + (d > 1e-12 ? (c - S.C[lo]) / d : 0) * DT;
    };
    const bodyM = (S, t) => {                // the root's pose at time t in P's frame
        const th = at(S, S.TH, t);
        const q = new Q().setFromAxisAngle(UP, th).multiply(root0.q);
        const p = new V3(root0.p.x + at(S, S.X, t), root0.p.y, root0.p.z + at(S, S.Z, t));
        return { m: new M4().compose(p, q, new V3(1, 1, 1)), th, p, q };
    };
    // a support slot's foot now (P's frame): its phase, its plants, the swing's arc; sets L.ph, L.stance, L.up, L.target
    function footAt(L, S, t) {
        const cyc = at(S, S.C, t) + L.off;
        const k = Math.floor(cyc), ph = cyc - k;
        const plant = (kk) => {
            // (A1) a plant FROZEN by a command made while this foot stood on it (below: command) stays where it was put
            const fz = frozen.get(L)?.get(kk);
            if (fz) return { p: fz.p.clone(), th: fz.th };
            // the foot stands under its rest place at L.center of its stance (mid-stance: 0.5; a leg whose rest pose stands near
            // full reach behind, the beetle's hind pair, later: its stance shifted forward)
            const tm = timeOfCycle(S, kk + duty * L.center - L.off);
            const bm = bodyM(S, tm);
            return { p: L.N.clone().applyMatrix4(bm.m), th: bm.th };
        };
        let foot, th, up = 0, s = 0;
        if (ph < duty) {
            const p0 = plant(k);
            foot = p0.p; th = p0.th;
        } else {
            // a swing in progress when the body last started from rest begins THERE (the foot was standing: its phase at the start
            // counts as the swing's beginning, so it lifts from the ground instead of popping up mid-arc)
            s = (ph - duty) / (1 - duty);
            const cNow = cyc - L.off;
            let cGo = null;
            for (const c0 of S.starts) { if (c0 <= cNow + 1e-9) cGo = c0; else break; }
            if (cGo != null) {
                const cg = cGo + L.off, kg = Math.floor(cg), sg = (cg - kg - duty) / (1 - duty);
                if (kg === k && sg > 0) s = Math.max(0, (s - sg) / (1 - sg));
            }
            // (B10b) the step's ease over the swing's last 90 %: the foot rises before it moves
            const sh = Math.min(1, Math.max(0, (s - 0.1) / 0.9));
            const e = sh * sh * (3 - 2 * sh);
            const p0 = plant(k), p1 = plant(k + 1);
            foot = p0.p.clone().lerp(p1.p, e);
            // the lift with the step's length (a re-placing step of a millimetre does not rise like a stride): full from 0.35
            // strides; sin^2: no vertical speed at lift-off or at touch-down
            const step = p0.p.distanceTo(p1.p) + Math.abs(p1.th - p0.th) * Math.hypot(L.N.x, L.N.z);
            const sl = Math.sin(Math.PI * s);
            up = sl * sl * Math.min(1, step / (0.35 * stride0));
            foot.y += lift * up;
            th = p0.th + (p1.th - p0.th) * e;
        }
        L.ph = ph; L.stance = ph < duty; L.up = up; L.swing = s; L.target = foot.clone();
        return { foot, th, up };
    }
    // a new command at time t replaces whatever was scheduled after t (a walkTo's remaining plan) and keeps the other control's
    // last target (sched stays sorted: ctl reads it in order)
    // (A1) A COMMAND NEVER MOVES A PLANTED FOOT: a stance's plant is where the body will stand at its stance's centre, which can lie
    // after the command; so every foot standing at t keeps the plant the schedule before the command gave it (frozen, tagged with
    // t: a later command at an earlier time, which pops this one, drops it too). A swing re-targets in the air, as it should. (A
    // walkTo called mid-walk slid the stance feet up to a stride's centre shift: the B11 controls never froze them.)
    const frozen = new Map();
    function freezeAt(t) {
        for (const [, m] of frozen) for (const [kk, p] of m) if (p.tag > t) m.delete(kk);
        if (!legs.length) return;
        const S = integrate(t + AHEAD);
        for (const L of legs) {
            const cyc = at(S, S.C, t) + L.off;
            const k = Math.floor(cyc);
            if (cyc - k >= duty) continue;                     // in the air: nothing to keep
            let m = frozen.get(L);
            if (!m) frozen.set(L, (m = new Map()));
            if (m.has(k)) continue;
            const tm = timeOfCycle(S, k + duty * L.center - L.off);
            const bm = bodyM(S, tm);
            m.set(k, { p: L.N.clone().applyMatrix4(bm.m), th: bm.th, tag: t });
            for (const kk of [...m.keys()]) if (kk < k - 1) m.delete(kk);
        }
    }
    const command = (t, v, w) => {
        freezeAt(t);
        while (sched.length > 1 && sched[sched.length - 1].t > t) sched.pop();
        const last = sched[sched.length - 1];
        sched.push({ t, v: v ?? last.v, w: w ?? last.w });
        schedVersion++;                                    // the integration's cache starts over
    };
    // THE PLANNER (walkTo, setHeading): from the body at rest at t0 (a moving body is first brought to rest over EASE), a turn
    // on the spot of exactly dth (its rate cut so the turn lasts at least EASE: the ramps never overlap, the eased integral is the
    // rate x the time), then a walk of exactly the distance (its speed cut the same way), then an optional turn to a final heading.
    // Returns the time it ends (the last ramp closed)
    const restAt = (t) => {
        // at rest: both controls' last targets 0 and their eased values 0 now (a ramp toward 0 in progress is not rest)
        const c = ctl(t), last = sched[sched.length - 1];
        return last.v === 0 && last.w === 0 && Math.abs(c.v) < 1e-12 && Math.abs(c.w) < 1e-12;
    };
    function settle(t0) {
        if (restAt(t0)) return t0;
        command(t0, 0, 0);
        return t0 + EASE;
    }
    function planTurn(t, dth, rate) {
        dth = Math.atan2(Math.sin(dth), Math.cos(dth));
        if (Math.abs(dth) < 1e-9) return t;
        const W = Math.min(rate, Math.abs(dth) / EASE);
        const T = Math.abs(dth) / W;
        command(t, 0, Math.sign(dth) * W);
        command(t + T, 0, 0);
        return t + T + EASE;
    }
    function planWalk(t, dist, speed) {
        // dist in the glb's units, speed in m/s at the creature's size
        if (dist < 1e-12) return t;
        const k = scaleOf();
        const V = Math.min(speed, dist * k / EASE);
        const T = dist * k / V;
        command(t, V, 0);
        command(t + T, 0, 0);
        return t + T + EASE;
    }
    // the point (x, 0, z) of the group's PARENT carried into P's frame through the group's own position, rotation and scale (and P's
    // place under it); a heading of the parent's frame likewise (a direction). The body's heading th is P's: it travels along
    // (sin th, cos th) and its rest forward (P's +z for every base: the manifests' forward [0, 0, 1]) turns with it
    function parentToP(x, z) {
        group.updateMatrixWorld(true);
        const toP = new M4().copy(P0().matrixWorld).invert();
        if (group.parent) toP.multiply(group.parent.matrixWorld);
        return { p: new V3(x, 0, z).applyMatrix4(toP), toP };
    }
    function headingToP(a, toP) {
        const o = new V3(0, 0, 0).applyMatrix4(toP), d = new V3(Math.sin(a), 0, Math.cos(a)).applyMatrix4(toP).sub(o);
        return Math.atan2(d.x, d.z);
    }
    let P0 = () => group;                                  // set by the case (the root's parent)
    const api = {
        sched, EASE, DT,
        speed(v, t = api.now) { command(t, v, null); },
        turn(w, t = api.now) { command(t, null, w); },
        // walk to a point of the group's parent (metres at its size): turn on the spot toward it, walk, stop, and (o.heading, radians
        // in the parent's frame) turn to a final heading; each phase planned exactly (above). Returns the time it ends
        walkTo(x, z, o = {}) {
            if (typeof o === 'number') o = { speed: o };
            const { speed = G.walkSpeed * scaleOf(), turnRate = G.turnRate ?? 0.8 } = o;
            let t = settle(api.now);
            const S = integrate(t + DT), body = bodyM(S, t);
            const { p: q, toP } = parentToP(x, z);
            const dx = q.x - body.p.x, dz = q.z - body.p.z;
            const bearing = Math.atan2(dx, dz);
            t = planTurn(t, bearing - body.th, turnRate);
            t = planWalk(t, Math.hypot(dx, dz), speed);
            if (o.heading != null) t = planTurn(t, headingToP(o.heading, toP) - bearing, turnRate);
            api.until = t;
            return t;
        },
        // turn on the spot to a heading of the parent's frame (radians: 0 faces +z, pi/2 faces +x)
        setHeading(a, o = {}) {
            const { turnRate = G.turnRate ?? 0.8 } = o;
            let t = settle(api.now);
            const S = integrate(t + DT), body = bodyM(S, t);
            const { toP } = parentToP(0, 0);
            t = planTurn(t, headingToP(a, toP) - body.th, turnRate);
            api.until = t;
            return t;
        },
        // the body's pose now in the parent's frame: { x, z, heading }
        pose(t = api.now) {
            const S = integrate(t + DT), b = bodyM(S, t);
            const { toP } = parentToP(0, 0);
            const fromP = toP.clone().invert();
            const p = b.p.clone().applyMatrix4(fromP);
            const o = new V3().applyMatrix4(fromP), d = new V3(Math.sin(b.th), 0, Math.cos(b.th)).applyMatrix4(fromP).sub(o);
            return { x: p.x, z: p.z, heading: Math.atan2(d.x, d.z) };
        },
        moving(t = api.now) { const c = ctl(t); return Math.abs(c.v) > 1e-9 || Math.abs(c.w) > 1e-9 || t < (api.until ?? 0); },
        now: 0,
        until: 0,
    };
    return { integrate, at, timeOfCycle, bodyM, footAt, command, controls: api, AHEAD, DT,
        setFrameNode(P) { P0 = () => P; } };
}

// =============================================================================================== THE STEP SOLVERS
// ctx: { ops (frameOps), root0, rootInv0, UP } -> { tarsus(L, foot, th, up, body), limb(L, foot, th, up, body), tentacle(...) }
export function makeSolvers(ctx) {
    const V3 = THREE.Vector3, Q = THREE.Quaternion, M4 = THREE.Matrix4;
    const { ops, root0, rootInv0 } = ctx;
    const UP = new V3(0, 1, 0);
    const { inP, qInP, setWorldQ, aim } = ops;
    const restWorldQ = new Map();
    const qInPRest = (b) => restWorldQ.get(b).clone();
    // ---------------------------------------------------------------------------------- tarsus (an arthropod leg; B11 verbatim)
    function tarsusInit(L) {
        restWorldQ.set(L.coxa, qInP(L.coxa).premultiply(root0.q.clone().invert()));
    }
    function tarsus(L, foot, th, up, body) {
        const { vB, vC, qa, qb, mA } = ops;
        // the coxa: yaw the leg's plane toward the foot about the body's up (in the root's frame), clamped to its range
        const rinv = mA.copy(body.m).invert();
        const fR = vB.copy(foot).applyMatrix4(rinv);           // the foot in the root's frame
        const cR = vC.copy(L.C).applyMatrix4(rootInv0);         // the coxa joint in the root's frame (the body is rigid on the root)
        const a0 = Math.atan2(L.N.x - cR.x, L.N.z - cR.z), a1 = Math.atan2(fR.x - cR.x, fR.z - cR.z);
        let yaw = a1 - a0;
        yaw = Math.atan2(Math.sin(yaw), Math.cos(yaw));
        yaw = Math.max(-L.range, Math.min(L.range, yaw));
        const qCoxa = qb.setFromAxisAngle(UP, yaw);
        setWorldQ(L.coxa, qCoxa.multiply(body.q).multiply(qInPRest(L.coxa)));
        // femur and tibia: the KNEE A HINGE about the tibia joint's own z (§6.3: femur-tibia 1 DOF; families/arthropod.py: a turn
        // about z folds it), its included angle from the foot's distance (the law of cosines; a few secant steps, the axis not
        // quite square to the leg), then the femur turned (the least turn) so the ankle lands on the foot
        const F = inP(L.femur);
        const toFoot = foot.clone().sub(F);
        const dMin = Math.abs(L.Lf - L.Lt) + 1e-5, dMax = L.Lf + L.Lt - 1e-5;
        const d = Math.max(dMin, Math.min(dMax, toFoot.length()));
        const want = Math.acos(Math.max(-1, Math.min(1, (L.Lf * L.Lf + L.Lt * L.Lt - d * d) / (2 * L.Lf * L.Lt))));
        const incl = () => { const K = inP(L.tibia); return F.clone().sub(K).angleTo(inP(L.tarsus).sub(K)); };
        const q0 = L.tibia.quaternion.clone();
        const knee = (dl) => {
            L.tibia.quaternion.copy(q0).multiply(qa.setFromAxisAngle(ZAX, dl));
            L.tibia.updateMatrixWorld(true);
            return incl() - want;
        };
        let x0 = 0.0, f0 = incl() - want, x1 = -0.05, f1 = knee(x1);
        for (let it = 0; it < 10 && Math.abs(f1) > 1e-7 && Math.abs(f1 - f0) > 1e-12; it++) {
            const x2 = x1 - f1 * (x1 - x0) / (f1 - f0);
            x0 = x1; f0 = f1; x1 = x2; f1 = knee(x1);
        }
        aim(L.femur, F, inP(L.tarsus), toFoot.clone().normalize());
        L.err = inP(L.tarsus).distanceTo(foot);                // the IK's miss (the glb's units): 0 while the foot is in reach
        const K3 = inP(L.tibia);
        L.knee = F.clone().sub(K3).angleTo(inP(L.tarsus).sub(K3)) * 180 / Math.PI;    // the femur-tibia included angle (deg)
        // the tarsus: its rest lie in the root's frame, turned with the foot's heading, its tip lifted through the swing
        const qT = new Q().setFromAxisAngle(UP, th).multiply(root0.q).multiply(L.qTar);
        if (up > 0) qT.multiply(new Q().setFromAxisAngle(new V3(0, 0, 1), -0.45 * up));
        setWorldQ(L.tarsus, qT);
    }
    // ---------------------------------------------------------------------------------- limb (plantigrade / digitigrade / paw / mech)
    // L: { upper, lower, ankle, contact (bones), anatomy } read at the rest pose (the body at root0): the hip H0, knee K0, ankle A0,
    // contact N (root frame), the segment lengths, the knee's plane normal n0 and its bend side; each joint's rest rotation in the
    // root's frame
    const basisQ = (x, n) => {
        const xx = x.clone().normalize();
        const nn = n.clone().addScaledVector(xx, -n.dot(xx)).normalize();
        const yy = new V3().crossVectors(nn, xx);
        return new Q().setFromRotationMatrix(new M4().makeBasis(xx, yy, nn));
    };
    const toRoot = (v) => v.clone().applyMatrix4(rootInv0);
    const qRoot = (b) => qInP(b).premultiply(root0.q.clone().invert());
    function limbInit(L) {
        L.H0 = toRoot(inP(L.upper)); L.K0 = toRoot(inP(L.lower)); L.A0 = toRoot(inP(L.ankle)); L.N = toRoot(inP(L.contact));
        L.L1 = L.H0.distanceTo(L.K0); L.L2 = L.K0.distanceTo(L.A0);
        L.n0 = new V3().crossVectors(L.K0.clone().sub(L.H0), L.A0.clone().sub(L.K0));
        if (L.n0.lengthSq() < 1e-20) L.n0.set(1, 0, 0);       // a straight bind: the knee's plane the root's lateral one
        L.n0.normalize();
        L.qU0 = qRoot(L.upper); L.qL0 = qRoot(L.lower); L.qA0 = qRoot(L.ankle);
        L.offA = L.A0.clone().sub(L.N);                         // the ankle from the contact, root frame
        L.incl0 = L.H0.clone().sub(L.K0).angleTo(L.A0.clone().sub(L.K0));
    }
    function limb(L, foot, th, up, body) {
        // the ankle's target: the contact's plant plus the rest offset turned with the foot's heading; through the swing the heel
        // rises about the contact (toe-off, plantigrade) or the metapodial flexes (digitigrade, paw): pitch about the knee's axis
        const qH = new Q().setFromAxisAngle(UP, th).multiply(root0.q);
        const nW = L.n0.clone().applyQuaternion(qH);
        const pitch = (L.toe ?? 0) * up;
        const qPitch = new Q().setFromAxisAngle(nW, pitch);
        const A = L.offA.clone().applyQuaternion(qH).applyQuaternion(qPitch).add(foot);
        // the hip now (the body posed: the upper's parent chain is the body's), the knee's plane normal carried by the BODY (not the
        // foot: the knee points where the body faces), the two-bone solve
        const H = inP(L.upper);
        const nB = L.n0.clone().applyQuaternion(body.q);
        const HA = A.clone().sub(H);
        const dRaw = HA.length();
        const dMin = Math.abs(L.L1 - L.L2) + 1e-6, dMax = L.L1 + L.L2 - 1e-6;
        const d = Math.max(dMin, Math.min(dMax, dRaw));
        const u = HA.clone().normalize();
        const a = (L.L1 * L.L1 - L.L2 * L.L2 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, L.L1 * L.L1 - a * a));
        // the bend direction: in the plane normal to nB through u, on the bind's side (n0 = (K0 - H0) x (A0 - K0) puts the bind's
        // knee on u x n0's side of the hip-ankle line)
        const side = new V3().crossVectors(u, nB).normalize();
        const K = H.clone().addScaledVector(u, a).addScaledVector(side, h);
        const Ar = H.clone().addScaledVector(u, d);              // the reachable ankle
        // upper: map (rest H->K, n0) to (H->K, n1), n1 the plane normal of the solved chain (nB's direction by construction)
        let n1 = new V3().crossVectors(K.clone().sub(H), Ar.clone().sub(K));
        if (n1.lengthSq() < 1e-20) n1 = nB.clone();
        const qRestW = (qr) => body.q.clone().multiply(qr);    // a rest rotation (root frame) carried by the body
        const H0w = L.H0.clone().applyQuaternion(body.q), K0w = L.K0.clone().applyQuaternion(body.q), A0w = L.A0.clone().applyQuaternion(body.q);
        const n0w = L.n0.clone().applyQuaternion(body.q);
        const R1 = basisQ(K.clone().sub(H), n1).multiply(basisQ(K0w.clone().sub(H0w), n0w).invert());
        setWorldQ(L.upper, R1.clone().multiply(qRestW(L.qU0)));
        const Kn = inP(L.lower);
        const R2 = basisQ(Ar.clone().sub(Kn), n1).multiply(basisQ(A0w.clone().sub(K0w), n0w).invert());
        setWorldQ(L.lower, R2.multiply(qRestW(L.qL0)));
        // the ankle: its rest lie turned with the foot's heading, pitched by the swing's toe-off
        setWorldQ(L.ankle, qPitch.clone().multiply(qH).multiply(L.qA0));
        L.err = inP(L.contact).distanceTo(foot);
        const K3 = inP(L.lower);
        L.knee = inP(L.upper).sub(K3).angleTo(inP(L.ankle).sub(K3)) * 180 / Math.PI;
    }
    // ---------------------------------------------------------------------------------- tentacle (a path solve)
    // L: { joints: [bones from the root to the tip], tip (the contact point: a socket or the last joint) }: the chain laid at its bind
    // lengths along a cubic from the root (its rest direction carried by the body) to the contact (arriving along the body's heading
    // in the ground plane), the curve's handles sized so its length is the chain's (a bisection), each joint aimed at the curve's
    // point one bind length on (a chord walk)
    function tentacleInit(L) {
        L.P0 = L.joints.map((b) => toRoot(inP(b)));
        L.tipR = toRoot(inP(L.tipNode || L.joints[L.joints.length - 1]));
        L.N = L.tipR.clone();
        L.seg = [];
        for (let i = 0; i < L.joints.length; i++) {
            const a = L.P0[i], b = i + 1 < L.joints.length ? L.P0[i + 1] : L.tipR;
            L.seg.push(a.distanceTo(b));
        }
        L.total = L.seg.reduce((x, y) => x + y, 0);
        L.d0 = L.P0[1 < L.P0.length ? 1 : 0].clone().sub(L.P0[0]).normalize();
    }
    function tentacle(L, foot, th, up, body) {
        const R = inP(L.joints[0]);
        const d0 = L.d0.clone().applyQuaternion(body.q);
        const qH = new Q().setFromAxisAngle(UP, th).multiply(root0.q);
        const flat = L.tipR.clone().sub(L.P0[0]).setY(0).normalize().applyQuaternion(qH);
        const cubic = (h, s) => {
            const p1 = R.clone().addScaledVector(d0, h), p2 = foot.clone().addScaledVector(flat, -h);
            const m = 1 - s;
            return R.clone().multiplyScalar(m * m * m).addScaledVector(p1, 3 * m * m * s).addScaledVector(p2, 3 * m * s * s)
                .addScaledVector(foot, s * s * s);
        };
        const lenOf = (h) => { let l = 0, p = R; for (let i = 1; i <= 48; i++) { const q = cubic(h, i / 48); l += p.distanceTo(q); p = q; } return l; };
        let lo = 0, hi = L.total;
        for (let it = 0; it < 30; it++) { const m = 0.5 * (lo + hi); if (lenOf(m) < L.total) lo = m; else hi = m; }
        const h = 0.5 * (lo + hi);
        // the chord walk: from each joint the curve's next point one segment on
        let s = 0;
        for (let i = 0; i < L.joints.length; i++) {
            const b = L.joints[i], P = inP(b);
            const next = i + 1 < L.joints.length ? L.joints[i + 1] : (L.tipNode || null);
            if (!next) break;
            let lo2 = s, hi2 = 1;
            for (let it = 0; it < 30; it++) { const m = 0.5 * (lo2 + hi2); if (cubic(h, m).distanceTo(P) < L.seg[i]) lo2 = m; else hi2 = m; }
            s = 0.5 * (lo2 + hi2);
            const Q2 = cubic(h, s);
            aim(b, P, inP(next), Q2.sub(P).normalize());
        }
        L.err = inP(L.tipNode || L.joints[L.joints.length - 1]).distanceTo(foot);
    }
    return { tarsusInit, tarsus, limbInit, limb, tentacleInit, tentacle };
}

// =============================================================================================== (B11) THE HEXAPOD (a case)
// BEETLE_PLAN §6.4 on the 104-joint skeleton (families/arthropod.py: each joint's frame x along the bone to its child, a positive
// turn about z folding it the anatomical way), a pure function of time and the controls' history (AG 00.5: --jump is exact):
//   * the GAIT: the scheduler's wave (lag between neighbouring legs on one side 1 - duty, hind to fore, 1/2 across);
//   * the FEET: the scheduler's plants (the hind and fore pairs' stance centred at gait.center);
//   * the LEG: the tarsus solver (coxa yaw clamped to §6.3's +-40 / 30 / 25 deg, the hinge-kept femur-tibia IK, the tarsus's lie);
//     (B10b) the rest is the rig's STAND (extras.bestiary.rig.stand: the body up, the tarsi pitched down to the claws), not the
//     bind, when the glb carries one;
//   * LIFE: the antennae sweep and their clubs fan, the palps chatter, the abdomen ventilates, the mandibles breathe a little
//     about their rest opening (8 deg), each on seeded phases.
// The controls (api.speed / api.turn / api.walkTo / api.setHeading, or opts.walk.schedule [[t, speed, turn], ...]) are speeds in
// metres per second and radians per second at the creature's own size (its group's scale applied).
const HEX_PAIRS = ['f', 'm', 'h'];
const HEX_COXA_RANGE = { f: 40, m: 30, h: 25 };       // deg, promotion-remotion (§6.3)
export function hexapodMotion(bones, seed, group, sp, opts = {}) {
    const V3 = THREE.Vector3, Q = THREE.Quaternion, M4 = THREE.Matrix4;
    const G = { walkSpeed: 0.3, ...sp.gait, ...(opts.gait || {}) };
    const duty = G.duty;
    const B = (n) => bones.get(n);
    const root = B('root');
    if (!root) return null;                              // (no root joint: create() leaves the creature still)
    const P = root.parent;                               // the glb's scene node: everything below is in its frame
    // (B10b) THE STAND (opts.stand: the rig's extras.bestiary.rig.stand): set on the bones BEFORE the rest is read
    if (opts.stand) {
        root.position.y += opts.stand.rise ?? 0;
        for (const [leg, a] of Object.entries(opts.stand.pitch || {})) {
            const b = B(`tarsus_1_${leg}`);
            if (b) b.quaternion.multiply(new Q().setFromAxisAngle(ZAX, a));
        }
    }
    // the rest (bind) pose: every bone's local quaternion and position, and the legs' joints in the root's frame
    const rest = new Map();
    for (const [n, b] of bones) rest.set(n, { q: b.quaternion.clone(), p: b.position.clone() });
    const ops = frameOps(group, P);
    const { inP, qInP } = ops;
    const root0 = { p: root.position.clone(), q: root.quaternion.clone() };
    const rootInv0 = new M4().compose(root0.p, root0.q, new V3(1, 1, 1)).invert();
    const legs = [];
    for (const pair of HEX_PAIRS) {
        for (const side of ['L', 'R']) {
            const nm = (j) => `${j}_${pair}_${side}`;
            const L = { pair, side, coxa: B(nm('coxa')), femur: B(nm('femur')), tibia: B(nm('tibia')), tarsus: B(nm('tarsus_1')) };
            if (!L.coxa || !L.femur || !L.tibia || !L.tarsus) continue;
            L.C = inP(L.coxa); L.F = inP(L.femur); L.K = inP(L.tibia); L.A = inP(L.tarsus);
            L.Lf = L.F.distanceTo(L.K); L.Lt = L.K.distanceTo(L.A);
            L.N = L.A.clone().applyMatrix4(rootInv0);                 // the foot's rest place in the root's frame
            L.qTar = qInP(L.tarsus).premultiply(root0.q.clone().invert());   // the tarsus's rest rotation in the root's frame
            // the gait's offset (the scheduler's wave rule): hind leads (2 (1 - duty)), then mid (1 - duty), then fore (0); the right
            // side half a cycle on
            L.off = ({ h: 2, m: 1, f: 0 }[pair] * (1 - duty) + (side === 'R' ? 0.5 : 0)) % 1;
            L.range = HEX_COXA_RANGE[pair] * Math.PI / 180;
            L.center = G.center?.[pair] ?? 0.5;
            L.anatomy = 'tarsus';
            legs.push(L);
        }
    }
    const gait = gaitScheduler(group, root0, legs, G, opts);
    gait.setFrameNode(P);
    const solvers = makeSolvers({ ops, root0, rootInv0 });
    // the seeded life phases
    const rnd = (i) => hash01(i, seed);
    const lifeJ = [];
    for (const side of ['L', 'R']) {
        const sg = side === 'L' ? 1 : -1;
        lifeJ.push({ b: B(`antenna_0_${side}`), axis: new V3(0, 0, 1), amp: 0.10, f: 0.31 + 0.1 * rnd(11 + sg), ph: rnd(21 + sg) });
        lifeJ.push({ b: B(`antenna_0_${side}`), axis: new V3(0, 1, 0), amp: 0.12, f: 0.23 + 0.1 * rnd(31 + sg), ph: rnd(41 + sg) });
        lifeJ.push({ b: B(`antenna_1_${side}`), axis: new V3(0, 0, 1), amp: 0.08, f: 0.41 + 0.1 * rnd(51 + sg), ph: rnd(61 + sg) });
        for (let k = 0; k < 4; k++) {
            lifeJ.push({ b: B(`lamella_${k}_${side}`), axis: new V3(0, 0, 1), amp: 0.10 + 0.04 * k, f: 0.19, ph: rnd(71 + sg) });
        }
        lifeJ.push({ b: B(`palp_max_0_${side}`), axis: new V3(0, 0, 1), amp: 0.12, f: 1.7 + 0.6 * rnd(81 + sg), ph: rnd(91 + sg) });
        lifeJ.push({ b: B(`palp_max_1_${side}`), axis: new V3(0, 0, 1), amp: 0.15, f: 2.3 + 0.6 * rnd(101 + sg), ph: rnd(111 + sg) });
        lifeJ.push({ b: B(`palp_lab_0_${side}`), axis: new V3(0, 0, 1), amp: 0.10, f: 1.9 + 0.6 * rnd(121 + sg), ph: rnd(131 + sg) });
        // the mandibles breathe +-2 deg about their rest opening (§6.3: 0-35 deg, rest 8)
        lifeJ.push({ b: B(`mandible_${side}`), axis: new V3(0, 0, 1), amp: 0.035, f: 0.17, ph: rnd(141) });
    }
    lifeJ.push({ b: B('abdomen_0'), axis: new V3(0, 0, 1), amp: 0.020, f: 0.42, ph: rnd(151) });      // ventilation (+-1.2 deg)
    lifeJ.push({ b: B('abdomen_1'), axis: new V3(0, 0, 1), amp: 0.030, f: 0.42, ph: rnd(151) + 0.15 });
    lifeJ.push({ b: B('head'), axis: new V3(0, 1, 0), amp: 0.025, f: 0.13, ph: rnd(161) });
    lifeJ.push({ b: B('head'), axis: new V3(0, 0, 1), amp: 0.020, f: 0.09, ph: rnd(171) });
    const life = lifeJ.filter((j) => j.b);
    // PISTON HELPERS (the cyborg beetle's mech fore leg: variants/cyborg/mechleg.py; each helper node's rule in its extras,
    // work/bestiary/beetle/b10/r04_helpers.py): after the legs, each cylinder turns about its rest z (the knee axis) so its x
    // points at its pin on the tibia, and each rod slides along its cylinder's x by |pin - pivot| - L0. Read at the bind
    const cyl = [], rods = [];
    for (const [, b] of bones) {
        const h = b.userData?.helper;
        if (h?.rule === 'piston_cylinder' && B(h.aim)) {
            cyl.push({ b, tgt: B(h.aim), pin: new V3().fromArray(h.pin), L0: h.L0, pivot: b.position.clone(),
                z: new V3(0, 0, 1).applyQuaternion(b.quaternion).normalize(), len: h.L0 });
        } else if (h?.rule === 'piston_rod') {
            rods.push({ b, cyl: h.cylinder, L0: h.L0, p0: b.position.clone() });
        }
    }
    const pistons = () => {
        const mA = ops.mA;
        for (const c of cyl) {
            const pp = c.pin.clone().applyMatrix4(c.tgt.matrixWorld).applyMatrix4(mA.copy(c.b.parent.matrixWorld).invert());
            const d = pp.sub(c.pivot);
            c.len = d.length();
            const cx = d.sub(c.z.clone().multiplyScalar(d.dot(c.z))).normalize();
            c.b.quaternion.setFromRotationMatrix(new M4().makeBasis(cx, new V3().crossVectors(c.z, cx), c.z));
            c.b.position.copy(c.pivot);
        }
        for (const r of rods) {
            const c = cyl.find((x) => x.b.name === r.cyl);
            if (c) r.b.position.set(r.p0.x + (c.len - r.L0), r.p0.y, r.p0.z);
        }
    };
    for (const L of legs) solvers.tarsusInit(L);
    const api = gait.controls;
    function motion(t) {
        api.now = t;
        for (const [n, b] of bones) { const r = rest.get(n); b.quaternion.copy(r.q); b.position.copy(r.p); }
        // P's frame as the group stands NOW
        group.updateMatrixWorld(true);
        ops.refresh();
        const S = gait.integrate(t + gait.AHEAD);
        const body = gait.bodyM(S, t);
        root.position.copy(body.p);
        root.quaternion.copy(body.q);
        root.updateMatrixWorld(true);
        for (const L of legs) {
            const { foot, th, up } = gait.footAt(L, S, t);
            solvers.tarsus(L, foot, th, up, body);
        }
        if (cyl.length) pistons();
        for (const j of life) {
            const a = j.amp * Math.sin(2 * Math.PI * (j.f * t + j.ph));
            j.b.quaternion.multiply(ops.qa.setFromAxisAngle(j.axis, a));
        }
        group.updateMatrixWorld(true);
    }
    // the gait's state for gates and probes, in world metres: each leg's phase, stance, swing lift, the foot's target and the
    // ankle where the IK put it, its miss (the glb's units)
    function probe() {
        const Pm = P.matrixWorld;
        return legs.map((L) => ({ leg: `${L.pair}_${L.side}`, ph: L.ph, stance: L.stance, up: L.up, err: L.err, knee: L.knee,
            target: L.target.clone().applyMatrix4(Pm).toArray(), ankle: inP(L.tarsus).applyMatrix4(Pm).toArray() }));
    }
    // a piston's miss: its pin (on the tibia) against its rod's end (L0 along the rod's x), in the glb's units
    function probePistons() {
        const k = P.matrixWorld.getMaxScaleOnAxis();
        return rods.map((r) => {
            const c = cyl.find((x) => x.b.name === r.cyl);
            return c ? { name: r.b.name, len: c.len, miss: c.pin.clone().applyMatrix4(c.tgt.matrixWorld)
                .distanceTo(new V3(r.L0, 0, 0).applyMatrix4(r.b.matrixWorld)) / k } : null;
        });
    }
    // (A1) the legs' bones for the air pose (spine.js fly: the legs tuck toward their rest lie)
    const legBones = legs.flatMap((L) => [L.coxa, L.femur, L.tibia, L.tarsus]);
    return { motion, controls: api, legs, probe, probePistons, legBones, rest, root, P, case: 'hexapod' };
}

// =============================================================================================== THE LIMBED CASE (quad / biped)
// Any base whose SUPPORT chains (chain records of a leg kind whose contact rests on the ground at the rest pose) stand it up:
// the scheduler over those slots, each slot's anatomy solver (plantigrade by default, the chain record's `anatomy` else), the
// body's carriage (a biped's pelvis bob and sway, a quad's trunk roll and pitch with its footfalls), the arms' counter-swing on a
// biped. The rest pose is the stand: opts.stand { rotations: { joint: [x, y, z, w] pose over the bind } } (the axolotl's
// extras.bestiary.stand format) when given.
//   chains: the glb's chain records (extras.bestiary.chains); opts.gait over the manifest's motion.walk
const LEG_KINDS = new Set(['leg', 'leg_fore', 'leg_hind', 'leg_mid']);
export function supportChains(chains, bones, group, P, groundTol = 0.15) {
    // the chains whose contact (their last joint, or the tip socket's joint) lies within groundTol x the body's height of the
    // lowest contact: the human's arms (kind leg_fore) hang far above it; an axolotl's four feet all stand
    const ops = frameOps(group, P);
    const cand = [];
    for (const c of chains || []) {
        if (!LEG_KINDS.has(c.kind) && c.anatomy !== 'tentacle') continue;
        const js = (c.joints || []).map((n) => bones.get(n)).filter(Boolean);
        if (js.length < 3) continue;
        cand.push({ c, js, y: ops.inP(js[js.length - 1]).y });
    }
    if (!cand.length) return [];
    const yMin = Math.min(...cand.map((x) => x.y));
    let yTop = -Infinity;
    for (const [, b] of bones) yTop = Math.max(yTop, ops.inP(b).y);
    const h = Math.max(1e-6, yTop - yMin);
    return cand.filter((x) => x.y - yMin <= groundTol * h);
}
export function limbedMotion(bones, seed, group, sp, opts = {}, chains = []) {
    const V3 = THREE.Vector3, Q = THREE.Quaternion, M4 = THREE.Matrix4;
    const root = bones.get('root');
    if (!root) return null;
    const P = root.parent;
    const UP = new V3(0, 1, 0);
    // the stand (poses over the bind) before the rest is read
    for (const [nm, q] of Object.entries(opts.stand?.rotations || {})) {
        const b = bones.get(nm);
        if (b) b.quaternion.multiply(new Q(...q));
    }
    if (opts.stand?.rise) root.position.y += opts.stand.rise;
    group.updateMatrixWorld(true);
    const rest = new Map();
    for (const [n, b] of bones) rest.set(n, { q: b.quaternion.clone(), p: b.position.clone() });
    const ops = frameOps(group, P);
    const root0 = { p: root.position.clone(), q: root.quaternion.clone() };
    const rootInv0 = new M4().compose(root0.p, root0.q, new V3(1, 1, 1)).invert();
    const sup = supportChains(chains, bones, group, P);
    const nLegs = sup.length;
    // the gait's numbers: the manifest's (sp.gait) over these defaults by the support count (a biped walks at duty 0.62, a quad at
    // 0.75's lateral sequence), the stride from the legs' length (a step of 0.9 leg lengths: Alexander's walking strides)
    const legLen = (x) => { let l = 0; for (let i = 1; i < x.js.length; i++) l += ops.inP(x.js[i]).distanceTo(ops.inP(x.js[i - 1])); return l; };
    const Lleg = sup.length ? sup.reduce((a, x) => a + legLen(x), 0) / sup.length : 0.1;
    // (a biped's: stride 0.75 leg lengths, the walking body CROUCHED 3.5 % of the leg below its straight-legged stand so the stance's
    // ends stay in reach: at the stand's full height a straight bind leg overreached every plant by 11-15 mm, A1 g02)
    const D = nLegs === 2 ? { duty: 0.62, stride: 0.75 * Lleg, fMin: 0.6, fMax: 2.2, lift: 0.08 * Lleg, toe: 0.35, crouch: 0.035, bob: 0.015 }
        : { duty: 0.75, stride: 0.8 * Lleg, fMin: 0.5, fMax: 2.5, lift: 0.12 * Lleg, toe: 0.25, crouch: 0.0, bob: 0.0, turnStride: 0.3 };
    // (the manifest's gait row only when this IS its case: a base with its own motion, the axolotl's salamander rows, keeps them for
    // its own and gives the limbed case sp.limbed if any)
    const own = sp.motion === 'limbed' ? (sp.gait || {}) : (sp.limbed || {});
    const G = { walkSpeed: 0.5 * D.stride * 1.2 * (group.scale.x || 1), turnRate: 0.8, ...D, ...own, ...(opts.gait || {}) };
    const solvers = makeSolvers({ ops, root0, rootInv0 });
    // rank from the front (the contact's forward place) for the wave rule; the side from the record
    const legs = sup.map((x) => {
        const c = x.c, js = x.js, n = js.length;
        const anatomy = c.anatomy ?? sp.anatomy?.[c.kind] ?? (sp.family === 'arthropod' ? 'tarsus' : 'plantigrade');
        const L = { name: c.name, label: c.label || c.name, side: c.side || (/_R$/.test(c.name) ? 'R' : 'L'), anatomy, kind: c.kind };
        if (anatomy === 'tentacle') {
            L.joints = js; L.tipNode = c.tip ? (group.getObjectByName(c.tip) || null) : null;
            solvers.tentacleInit(L);
        } else {
            const ik = c.ik || {};
            L.upper = bones.get(ik.upper) || js[n - 4] || js[0];
            L.lower = bones.get(ik.lower) || js[n - 3];
            L.ankle = bones.get(ik.ankle) || js[n - 2];
            L.contact = bones.get(ik.contact) || js[n - 1];
            L.toe = { plantigrade: G.toe, digitigrade: -0.5 * G.toe, paw: -0.5 * G.toe, mech: 0 }[anatomy] ?? 0;
            solvers.limbInit(L);
        }
        return L;
    });
    const fwd = legs.map((L) => L.N.z);
    const ranks = [...new Set(fwd.map((z) => Math.round(z * 1e4)))].sort((a, b) => b - a);
    for (const L of legs) {
        const r = ranks.indexOf(Math.round(L.N.z * 1e4));
        const pairs = Math.max(1, Math.ceil(nLegs / 2));
        const rank = Math.min(pairs - 1, Math.round(r * (pairs - 1) / Math.max(1, ranks.length - 1)));
        L.off = G.phase?.[L.label] ?? ((rank * (1 - G.duty) + (L.side === 'R' ? 0.5 : 0)) % 1);
        L.center = G.center?.[L.label] ?? 0.5;
    }
    const gait = gaitScheduler(group, root0, legs, G, opts);
    gait.setFrameNode(P);
    const api = gait.controls;
    // the carriage: a biped's pelvis drops at the double support and rises over the stance leg (the COM's vault, ~2.5 % of the leg),
    // sways toward the stance side, yaws with the swing leg; the arms swing against the legs (the shoulder's pitch); a quad's trunk
    // rolls a little with its diagonal support
    const pelvis = bones.get('pelvis');
    const arms = (chains || []).filter((c) => (c.kind === 'leg_fore' || /arm/.test(c.name)) && !sup.some((x) => x.c === c))
        .map((c) => ({ c, b: bones.get(c.joints[1] || c.joints[0]), side: c.side }))
        .filter((a) => a.b);
    for (const a of arms) a.q0 = a.b.quaternion.clone();
    function motion(t) {
        api.now = t;
        for (const [n, b] of bones) { const r = rest.get(n); b.quaternion.copy(r.q); b.position.copy(r.p); }
        group.updateMatrixWorld(true);
        ops.refresh();
        const S = gait.integrate(t + gait.AHEAD);
        const body = gait.bodyM(S, t);
        const c = gait.at(S, S.C, t);
        const om = Math.min(1, Math.max(0, (gait.at(S, S.C, t + 0.05) - gait.at(S, S.C, t - 0.05)) / 0.1 / Math.max(G.fMin, 1e-6)));
        if (G.crouch) body.p.y -= om * G.crouch * Lleg;
        if (nLegs === 2) {
            // two vaults per cycle (one per stance), highest at each mid-stance
            body.p.y += om * G.bob * Lleg * (Math.cos(4 * Math.PI * (c + legs[0].off - 0.5 * G.duty)) - 1) * 0.5;
            const sway = om * 0.012 * Lleg * Math.sin(2 * Math.PI * (c + legs[0].off - 0.25 * G.duty));
            body.p.add(new V3(sway, 0, 0).applyQuaternion(body.q));
        }
        root.position.copy(body.p);
        root.quaternion.copy(body.q);
        root.updateMatrixWorld(true);
        if (pelvis && nLegs === 2) {
            pelvis.quaternion.multiply(ops.qa.setFromAxisAngle(UP, om * 0.07 * Math.sin(2 * Math.PI * (c + legs[0].off))));
            pelvis.updateMatrixWorld(true);
        }
        for (const L of legs) {
            const { foot, th, up } = gait.footAt(L, S, t);
            solvers[L.anatomy === 'tentacle' ? 'tentacle' : L.anatomy === 'tarsus' ? 'tarsus' : 'limb'](L, foot, th, up, body);
        }
        if (nLegs === 2) {
            for (const a of arms) {
                // the arms HANG first (a bind in T or A: the upper arm turned, the least turn, from its rest line to down and 12 deg
                // out at its side, in the body's frame; the A1 human film walked in its T bind)
                const kid = a.b.children.find((x) => x.isBone);
                if (kid && G.armHang !== false) {
                    const out = (a.side === 'R' ? -1 : 1) * Math.sin(12 * Math.PI / 180);
                    const want = new V3(out, -Math.cos(12 * Math.PI / 180), 0).applyQuaternion(body.q).normalize();
                    ops.aim(a.b, ops.inP(a.b), ops.inP(kid), want);
                }
                const sg = a.side === 'R' ? 1 : -1;
                const sw = om * 0.30 * Math.sin(2 * Math.PI * (c + legs[0].off) + (sg > 0 ? 0 : Math.PI));
                // the arm's pitch about the body's lateral axis, in the upper arm's parent frame
                const lat = new V3(1, 0, 0).applyQuaternion(body.q);
                const pq = ops.qInP(a.b.parent).invert();
                a.b.quaternion.premultiply(new Q().setFromAxisAngle(lat.applyQuaternion(pq).normalize(), sw));
            }
        }
        group.updateMatrixWorld(true);
    }
    function probe() {
        const Pm = P.matrixWorld;
        return legs.map((L) => ({ leg: L.label, anatomy: L.anatomy, ph: L.ph, stance: L.stance, up: L.up, err: L.err, knee: L.knee,
            target: L.target.clone().applyMatrix4(Pm).toArray(),
            contact: ops.inP(L.contact || L.tipNode || L.joints[L.joints.length - 1]).applyMatrix4(Pm).toArray() }));
    }
    const legBones = legs.flatMap((L) => L.joints || [L.upper, L.lower, L.ankle]);
    return { motion, controls: api, legs, probe, legBones, rest, root, P, case: nLegs === 2 ? 'biped' : 'limbed', G };
}

// =============================================================================================== THE VRM CASE (the human)
// The human's walk belongs to the house's character controller (eidoverse/robot_controller.js EidoverseRobotController: physics
// locomotion, the walk clip, foot IK; tools-guides/characters.md): this maps the spine's controls onto its waypoints. walkTo(x, z)
// = setWaypoints([{x, z}]) (arriveRadius from o.radius, default 0.01 m: the gate's 1 cm; the controller's own default 0.28 m);
// speed(v) / turn(w) steer a carrot two metres ahead on the integrated heading (a waypoint re-issued each update); setHeading(a)
// a short step toward the heading (the controller turns as it locomotes; it has no turn-on-the-spot).
export function vrmLocomotion(ctrl, o = {}) {
    let v = 0, w = 0, head = null, lastT = null;
    const api = {
        now: 0,
        speed(x) { v = x; if (x > 0 && ctrl.setWalkSpeed) ctrl.setWalkSpeed(x); },
        turn(x) { w = x; },
        walkTo(x, z, oo = {}) {
            if (typeof oo === 'number') oo = { speed: oo };
            if (oo.speed && ctrl.setWalkSpeed) ctrl.setWalkSpeed(oo.speed);
            ctrl.arriveRadius = oo.radius ?? o.radius ?? 0.01;
            v = 0; w = 0;
            ctrl.setWaypoints([{ x, z, action: oo.run ? 'run' : undefined }]);
        },
        setHeading(a) {
            const p = ctrl.getPosition();
            ctrl.arriveRadius = 0.05;
            ctrl.setWaypoints([{ x: p.x + 0.25 * Math.sin(a), z: p.z + 0.25 * Math.cos(a) }]);
        },
        pose() { const p = ctrl.getPosition(); return { x: p.x, z: p.z, heading: ctrl.getHeading() }; },
        moving() { return ctrl.isBusy ? ctrl.isBusy() : false; },
        // called by the spine before the controller's own update (the drive mode's carrot)
        step(t) {
            const dt = lastT == null ? 0 : t - lastT;
            lastT = t;
            api.now = t;
            if (v === 0 && w === 0) { head = null; return; }
            if (head == null) head = ctrl.getHeading();
            head += w * dt;
            const p = ctrl.getPosition();
            const r = v > 0 ? 2.0 : 0.25;
            ctrl.arriveRadius = 0.05;
            ctrl.setWaypoints([{ x: p.x + r * Math.sin(head), z: p.z + r * Math.cos(head) }]);
        },
    };
    return { controls: api, case: 'vrm' };
}
