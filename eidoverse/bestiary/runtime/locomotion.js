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

// =============================================================================================== THE OCTOPUS ARM'S PATH LAW (CROSS)
// CROSS (work/bestiary/remix_r1/cross/STAGED.md; CROSSBREED §4.5: "a path solve for a tentacle ... and in tail mode with no ground
// contact"): the octopus arm's own resting path as a LAW, moved here word for word from bestiary.js radialMotion so that the arm's
// solver is ONE piece of code wherever an arm is (the octopus's eight on the sand, radialMotion's solveArm; an arm grafted for a
// tail, axolotl.js's tail mode): the seeded draws per arm (armSeeds: the spacing jitter, the slow wander along the length, the
// distal spiral's side, start and tightness, the tips that rise, the drape, the two phases) and the path's curvature in its bending
// plane (armCurvature, 1/m at the octopus's own size: the wander, then the spiral rising toward the tip as the coils curl and
// uncurl, the tips exploring). Every expression is radialMotion's own, in its order: the octopus's arms move bit for bit as before
// (cross/tests/t01_identity.mjs)
const armSmooth = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
export function armSeeds(h) {
    // h(i): the arm's own seeded draw i in [0, 1) (radialMotion: hash01(j * 31 + i, seed) for arm j)
    return {
        dAz: (h(1) - 0.5) * 0.45,
        wanderK: (h(2) - 0.5) * 2.0 * 2.2, wanderL: 0.30 + 0.30 * h(3), wanderPh: h(4) * 6.2832,
        coilSide: h(5) < 0.5 ? -1 : 1, coilS0: 0.50 + 0.22 * h(6), coilG: 0.28 + 0.30 * h(7),
        tipLift: h(8) < 0.35 ? 0.015 + 0.03 * h(9) : 0.0, drape: 0.10 + 0.08 * h(10),
        ph0: h(11) * 6.2832, ph1: h(12) * 6.2832,
    };
}
// the coils' slow breath at time t (solveArm's coilMul)
export const armCoilMul = (a, t) => 1.0 + 0.10 * Math.sin(6.2832 * 0.06 * t + a.ph0);
export function armCurvature(a, sm, u, L, coilMul, t) {
    // the path's curvature (1/m) at arc length sm of an arm of length L (u = sm / L): solveArm's three terms
    let kap = a.wanderK * Math.sin(6.2832 * sm / a.wanderL + a.wanderPh) * (0.3 + 0.7 * armSmooth(0.05, 0.3, u));
    const rem = Math.max(L - sm, 0.0);
    kap += a.coilSide * coilMul * armSmooth(a.coilS0, a.coilS0 + 0.12, u) / (0.010 + a.coilG * rem);
    kap += 0.9 * Math.sin(6.2832 * 0.21 * t - 9.0 * u + a.ph1) * armSmooth(0.75, 1.0, u);
    return kap;
}

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
    // (D4.1b fix) a slot with a walk place (L.Nw, limbedMotion) walks with its foot there: its walk place is its fastest foot's
    const footSpeed = (vg, w) => {
        let m = Math.abs(vg);
        for (const L of legs) { const N = L.Nw || L.N; m = Math.max(m, Math.hypot(w * N.z / TS, vg - w * N.x / TS)); }
        return m;
    };
    // the step rate's floor: a slow walk takes shorter steps, never slower ones, and when the body comes to rest the legs keep
    // stepping at it for ONE more cycle, so every swing foot lands on its rest place under the stopped body
    const fMin = G.fMin ?? 1.0;
    // the integrated body: heading th, position x z (the glb's units), the gait's cycles c, sampled every DT; S.starts the cycles'
    // value at every start from rest. CACHED: the samples grow with t on the one fixed grid from 0 and start over when a command
    // changes the schedule or the size; a frame costs its new samples only
    let cache = null, schedVersion = 0;
    // (D4.1b fix 2, work/bestiary/research/tarantula_notes/d41b_fix2_NOTES.md) A SLOT WITH THE D4.1b RECORDS (L.walkW: a walk
    // place L.Nw, its own lift, or a second hinge; limbedMotion, slotInit) is scheduled so that NO PLANTED FOOT EVER CHANGES
    // PLACE IN ONE FRAME and no foot in the air jumps, on the command path and on a fixed schedule alike (plantW, footW, the
    // swing's events and freezeAt below). OPT: a gait with such a slot. Every other slot and gait is scheduled by MOUNT's
    // lines, as before.
    const OPT = legs.some((L) => L.walkW);
    // A GAIT WITH WALK PLACES SETTLES IN SETTLE_N CYCLES after a stop, not one: its plants are WALKING ones while their stance's
    // centre lies within WALK_X cycles after the body last moved (every foot lands under the stopped body where it walks), then
    // standing ones (a walk-place slot steps back to its rest place, the bind's). That rest place may fold it over a
    // neighbour's base (the tarantula's leg II over leg I's, i01's standing pose), which only a neighbour already at rest
    // leaves room for (with one cycle leg II settled while leg I still swung in, through it: fix 1's E5). WALK_X 0.5: the
    // smallest window in which leg II's folding step always comes after leg I's last step on both sides (the tarantula's
    // phase table, L1 0.42 / L2 0.0 and R1 0.0 / R2 0.49, needs at least 0.4805); fix 1's window of a whole cycle left leg II
    // folding back alone 1.8-3.6 s after the call (the check's L1). SETTLE_N 1.5: the folding step's touchdown inside the count.
    // Its settle STEPS AT THE RATE THE GAIT HAD WHEN THE STOP BEGAN (the rate EASE before the body came to rest, never under
    // fMin), not at fMin: every settling step, leg II's folding step too, takes its walking swing's time (at fMin the folding
    // step took 0.83 s against the walking swing's 0.63 s). The poses are the same functions of the cycles, only sooner.
    // MV, per sample: the last sample time the body moved (the integrator's own fm > 1e-6), -1 before it ever did
    const WALK_X = 0.5, SETTLE_N = 1.5;
    const PLACES = legs.some((L) => L.Nw);
    const settleN = PLACES ? SETTLE_N : 1;
    function integrate(tEnd) {
        const n = Math.max(2, Math.ceil(tEnd / DT) + 1);
        const k = 1 / scaleOf();
        if (!cache || cache.version !== schedVersion || cache.k !== k) {
            cache = { version: schedVersion, k, len: 0, cap: 0, starts: [], resumes: [],
                s: { x: 0, z: 0, th: 0, c: 0, owe: 0, fPrev: 0, fSet: 0 } };
        }
        if (cache.len < n) {
            if (cache.cap < n) {
                const cap = Math.max(n, 2 * cache.cap, 512);
                for (const key of (OPT ? ['T', 'X', 'Z', 'TH', 'C', 'MV'] : ['T', 'X', 'Z', 'TH', 'C'])) {
                    const a = new Float64Array(cap);
                    if (cache[key]) a.set(cache[key].subarray(0, cache.len));
                    cache[key] = a;
                }
                cache.cap = cap;
            }
            const s = cache.s, T = cache.T, X = cache.X, Z = cache.Z, TH = cache.TH, C = cache.C, MV = cache.MV;
            for (let i = cache.len; i < n; i++) {
                const t = i * DT;
                T[i] = t; X[i] = s.x; Z[i] = s.z; TH[i] = s.th; C[i] = s.c;
                const { v, w } = ctl(t);
                const vg = v * k;                                   // metres per second at its size -> the glb's units
                const fm = Math.min(fMax, footSpeed(vg, w) / stride0);
                let f = 0;
                if (fm > 1e-6) {
                    f = Math.max(fm, fMin);
                    s.owe = settleN;
                    if (PLACES) s.fSet = 0;
                } else if (s.owe > 0) {
                    if (PLACES && s.fSet === 0) {                  // (fix 2) the rate the gait had when the stop began
                        const c0 = ctl(Math.max(0, t - EASE));
                        s.fSet = Math.max(fMin, Math.min(fMax, footSpeed(c0.v * k, c0.w) / stride0));
                    }
                    f = Math.min(PLACES ? s.fSet : fMin, s.owe / DT);   // the settling cycle, ending on its exact count
                    s.owe -= f * DT;
                }
                if (OPT) {
                    // (fix 2) a RESUME: the body moves again after a sample at rest (a start from rest, or one inside the settle)
                    if (fm > 1e-6 && i > 0 && MV[i - 1] !== T[i - 1]) cache.resumes.push({ i, t });
                    MV[i] = fm > 1e-6 ? t : (i > 0 ? MV[i - 1] : -1);
                }
                if (f > 0 && s.fPrev === 0) cache.starts.push({ i, c: s.c });
                s.fPrev = f;
                s.x += Math.sin(s.th) * vg * DT; s.z += Math.cos(s.th) * vg * DT; s.th += w * DT; s.c += f * DT;
            }
            cache.len = n;
        }
        return { T: cache.T, X: cache.X, Z: cache.Z, TH: cache.TH, C: cache.C, MV: cache.MV, n,
            starts: cache.starts.filter((e) => e.i < n).map((e) => e.c),
            resumes: OPT ? cache.resumes.filter((e) => e.i < n).map((e) => e.t) : null };
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
    // ((D4.1b fix 2) a slot with the D4.1b records: footW, below)
    function footAt(L, S, t) {
        const cyc = at(S, S.C, t) + L.off;
        const k = Math.floor(cyc), ph = cyc - k;
        if (L.walkW) return footW(L, S, t, cyc, k, ph);
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
    // ---------------------------------------------------------------------- (D4.1b fix 2) the slots with the D4.1b records
    // THE PLAN'S HORIZON. A plant is decided from what the schedule says up to a horizon that never passes the next RESUME of
    // the body: a standing animal does not know when it will walk, though a film's schedule does from frame 0 and a command's
    // plan does after it. (Fix 1 read a standing foot's walk weight at its stance's centre, up to the 2.0 s look-ahead ahead,
    // and moved the planted foot to its walk place in one frame, 18.25 mm, 2.0 s before a scheduled start; MOUNT's own plants
    // crept toward the coming walk along the ground, 7 mm in 0.5 s: the check's F2, R11, R12.) A decision made at tr sees the
    // schedule up to tr + AHEAD, the last sample before the next resume after tr and the sampled span's end, whichever is first
    const horizon = (S, tr) => {
        let h = Math.min(tr + AHEAD, S.T[S.n - 1]);
        for (const r of S.resumes) if (r > tr + 1e-9) { h = Math.min(h, r - DT); break; }
        return h;
    };
    // THE PLAN OF A STANCE, decided at its touchdown: a stance under way is decided at its touchdown (it never changes while the
    // foot stands), a coming one now (the swing's target). The foot stands under its place at the body's pose at the stance's
    // centre, as MOUNT's plants, the centre clamped to the horizon (a stance begun standing whose centre comes after a start
    // stands where the body stood; a foot standing at frame 0 is on the bind whatever the schedule says next). Its walk weight:
    // 1 (walking: the walk place, the second hinge's rules) when the centre's cycle lies within WALK_X cycles after the body
    // last moved, else 0 (standing: the rest place, the bind), read from the centre's own cycle (fix 1 read the cycles at the
    // clamped time, which move with now). In a steady walk nothing is clamped: fix 1's plants, value for value
    function planW(L, S, t, kk) {
        const fz = frozen.get(L)?.get(kk);
        if (fz) return { p: fz.p.clone(), th: fz.th, w: fz.w };
        const cTd = kk - L.off, cCe = cTd + duty * L.center;
        const tm = Math.min(timeOfCycle(S, cCe), horizon(S, Math.min(t, timeOfCycle(S, cTd))));
        const bm = bodyM(S, tm);
        const tl = S.MV[Math.max(0, Math.min(S.n - 1, Math.floor(tm / DT)))];
        const w = tl >= 0 && at(S, S.C, tl) >= cCe - WALK_X ? 1 : 0;
        return { p: (w === 1 ? (L.Nw || L.N) : L.N).clone().applyMatrix4(bm.m), th: bm.th, w };
    }
    // THE SWING'S CLOCK for cycle k's swing at time t. raw: the share of the swing's own phase that has passed (under 0: the
    // phase is still the stance's). b: where the swing begins. 0: at its phase. Over 0: by footAt's own rule (MOUNT's), the
    // share at which the body last started from rest (a swing in progress when the body starts from rest begins THERE: the
    // foot stood until then). Under 0: EARLY, in the end of its stance: the swing after one that a start from rest cut short
    // (below: the share of a re-target) lifts as much earlier as that one's step fell short, so the stance between, begun in
    // effect at the start, lasts no longer than a stance does (with its phase's whole length a hind foot stood a whole stance
    // behind a skittering body, 2.1 mm out of its reach before it lifted, and was dragged 0.35 mm in one frame, at 2 of 128
    // skitter starts). s: its fraction, 0 at b and 1 at its touchdown
    function swingClock(L, S, k, t) {
        const c = at(S, S.C, t);
        const raw = (c + L.off - k - duty) / (1 - duty);
        let b = 0;
        for (let q = S.starts.length - 1; q >= 0; q--) {
            if (S.starts[q] > c + 1e-9) continue;
            const cg = S.starts[q] + L.off, kg = Math.floor(cg), sg = (cg - kg - duty) / (1 - duty);
            if (sg > 0 && kg === k) b = sg;
            else if (sg > 0 && kg === k - 1) b = -(1 - retarget(sg)) * (1 - sg);
            break;
        }
        return { raw, b, s: b !== 0 ? Math.min(1, Math.max(0, (raw - b) / (1 - b))) : raw };
    }
    // is the foot in cycle k's swing at phase ph: in the swing's own phase, or in the end of the stance before it when that
    // swing begins early (b < 0; never earlier than RT_HI of a swing)
    function airborne(L, S, t, k, ph) {
        if (ph >= duty) return true;
        if (ph < duty - RT_HI * (1 - duty) || !S.starts.length) return false;
        const ck = swingClock(L, S, k, t);
        return ck.b < 0 && ck.raw >= ck.b;
    }
    // one swing from plant p0 to plant p1 at fraction s (fix 1's arithmetic in its order): the place, the lift share up (with the
    // step's length) and its height h, the heading and the walk weight. THE LIFT: the slot's walking swing's (L.lift, else the
    // gait's), the FOLDING step back to its rest place after a stop included (fix 1 lifted it by L.liftPlace 15.9 mm: the foot
    // 19.5 mm up, over the body, three times the walking swing's 6.6: the check's L1). The UNFOLDING step from the rest place
    // out to the walk place at a start lifts by L.liftPlace where the CASE gives one, else by the walking lift too. The
    // tarantula's case gives none (the lead's call, 11-18): its second foot unfolds 6.6 mm up, as it walks, and the hair
    // coats of thighs I and II pass 0.92 mm through each other for 0.28 s at a start, the cuticles 0.48 mm apart (a row of
    // 15.9 mm held those coats to 0.26 mm for 0.12 s and put the foot 19.6 mm up, over the body's top)
    function swingPath(L, p0, p1, s, o) {
        const sh = Math.min(1, Math.max(0, (s - 0.1) / 0.9));
        const e = sh * sh * (3 - 2 * sh);
        o.pos.copy(p0.p).lerp(p1.p, e);
        const Nr = L.Nw || L.N;
        const step = p0.p.distanceTo(p1.p) + Math.abs(p1.th - p0.th) * Math.hypot(Nr.x, Nr.z);
        const sl = Math.sin(Math.PI * s);
        o.up = sl * sl * Math.min(1, step / (0.35 * stride0));
        o.h = (p1.w > p0.w && L.liftPlace != null ? L.liftPlace : (L.lift ?? lift)) * o.up;
        o.th = p0.th + (p1.th - p0.th) * e;
        o.w = p0.w + (p1.w - p0.w) * e;
        return o;
    }
    // THE EVENTS OF A SWING: the moments its target changed while the foot was in the air, each with the plan it flew to
    // before: a command made NOW (freezeAt records it; MOUNT's swings re-target at a command, "as it should", in that very
    // frame: 7-19 mm at a restart, the check's F1(b)) and a resume of the body (on any schedule: the horizon moves past it).
    // Up to t or the swing's touchdown, in time order, into out
    const swingRec = new Map();
    function swingEvents(L, S, k, t, out) {
        out.length = 0;
        const t1 = Math.min(t, timeOfCycle(S, k + 1 - L.off));
        const rs = swingRec.get(L)?.get(k);
        if (rs) for (const r of rs) if (r.tag <= t1 + 1e-9) out.push({ t: r.tag, p1: r.p1 });
        if (S.resumes.length) {
            const b = swingClock(L, S, k, t).b;
            const tLift = timeOfCycle(S, (b < 0 ? k + duty + b * (1 - duty) : k + duty) - L.off);
            for (let i = S.resumes.length - 1; i >= 0; i--) {
                const r = S.resumes[i];
                if (r > t1 + 1e-9) continue;
                if (r <= tLift + 1e-9) break;
                out.push({ t: r, p1: planW(L, S, r - 0.5 * DT, k + 1) });
            }
        }
        if (out.length > 1) out.sort((a, b) => a.t - b.t);
        return out;
    }
    // THE SHARE OF A RE-TARGET a swing still takes on, by how much of its own PHASE is left at the event (1 - raw): the whole
    // while 30 % of the swing or more remains, none in its last 5 % (a foot about to land lands where it was going, and its
    // next step carries the change: a whole re-target 8 % before touch-down crowded leg II's 18 mm into three frames; with none
    // from 15 % on, a hind foot landed behind a body that had started to walk and stood a whole stance out of its reach by
    // 0.94 mm). Between, the blend moves a foot at most 0.15 of the re-target a frame at the walk's rate: a swing's own speed.
    // A START FROM REST IS SUCH AN EVENT TOO. A foot whose phase at rest lies in its swing begins that swing at the start
    // (footAt's rule, b above) with only the rest of the phase to make it in, and MOUNT gives it the whole step whatever is
    // left: with 1.5 % of the phase left the tarantula's second foot, standing, was at its walk place 18 mm away in the NEXT
    // FRAME (on a schedule and at a command alike: fix 1 at 10 of 128 walk starts and 10 of 128 skitter starts, up to 21 mm;
    // d41b_fix2 S7). By the share it makes the whole step with 30 % of the phase left, part of it with less, and with under
    // 5 % it stands where it stood, as a foot whose phase at rest lies in its stance does; the stance after stands where the
    // foot came down, and the swing after that lifts early by what the step fell short (the clock's b < 0). (Tried instead:
    // the whole step in at least 30 % of a swing's phase, the touchdown put off: no foot is left behind, but four feet landing
    // late met three lifting on time, ONE foot on the ground for two frames at a start)
    const RT_LO = 0.05, RT_HI = 0.3;
    const retarget = (raw) => { const x = Math.min(1, Math.max(0, (1 - raw - RT_LO) / (RT_HI - RT_LO))); return x * x * (3 - 2 * x); };
    const sameP = (a, b) => a.p.distanceTo(b.p) < 1e-12 && Math.abs(b.th - a.th) < 1e-12 && a.w === b.w;
    const mixP = (a, b, r) => ({ p: a.p.clone().lerp(b.p, r), th: a.th + (b.th - a.th) * r, w: a.w + (b.w - a.w) * r });
    // A PLANT: the stance's plan, or, where the swing before it had events, the place that swing LANDED (each event moves the
    // landing toward the plan after it by its share), so the foot stands where it came down
    const EV2 = [];
    function plantW(L, S, t, kk) {
        const fz = frozen.get(L)?.get(kk);
        if (fz) return { p: fz.p.clone(), th: fz.th, w: fz.w };
        const P = planW(L, S, t, kk);
        const ev = swingEvents(L, S, kk - 1, t, EV2);
        if (!ev.length) return P;
        let T = ev[0].p1;
        for (let i = 0; i < ev.length; i++) {
            const pb = i + 1 < ev.length ? ev[i + 1].p1 : P;
            if (sameP(ev[i].p1, pb)) continue;
            const r = retarget(swingClock(L, S, kk - 1, ev[i].t).raw);
            T = r >= 1 ? pb : r <= 0 ? T : mixP(T, pb, r);
        }
        return T;
    }
    const sw1 = { pos: new V3(), up: 0, h: 0, th: 0, w: 0 }, sw2 = { pos: new V3(), up: 0, h: 0, th: 0, w: 0 }, EV = [];
    // the foot of a slot with the D4.1b records. STANCE: its plant. SWING: from its plant to the next one (swingPath: its lift);
    // and at each EVENT of the swing (above) the path BLENDS from the target before to the target after (by its share) over the
    // rest of the swing (the swing's own ease from the event on), so the foot never jumps; where the new target lies off the old
    // one the foot rises at least by the walking swing's arc for the step to it (no foot slides along the ground). An event
    // at which the swing begins (a start from rest: footAt's rule begins the swing there) gives the swing its new target, by
    // its share, from lift-off. A swing begun at a start from rest has only the share 1 - b of a swing's phase to run and
    // lifts by that share of its lift: a step with a third of the time rises a third as high, at a swing's own speed
    function footW(L, S, t, cyc, k, ph) {
        let foot, th, up = 0, s = 0;
        const air = airborne(L, S, t, k, ph);
        if (!air) {
            const p0 = plantW(L, S, t, k);
            foot = p0.p; th = p0.th;
            L.w = p0.w;
        } else {
            const ck = swingClock(L, S, k, t);
            s = ck.s;
            const low = Math.min(1, 1 - ck.b);
            const p0 = plantW(L, S, t, k), p1 = planW(L, S, t, k + 1);
            const ev = swingEvents(L, S, k, t, EV);
            let T = ev.length ? ev[0].p1 : p1;
            const A = swingPath(L, p0, T, s, sw1);
            for (let i = 0; i < ev.length; i++) {
                const pb = i + 1 < ev.length ? ev[i + 1].p1 : p1;
                if (sameP(ev[i].p1, pb)) continue;
                const cki = swingClock(L, S, k, ev[i].t), r = retarget(cki.raw);
                if (r <= 0) continue;
                const Tn = r >= 1 ? pb : mixP(T, pb, r);
                const si = cki.s;
                if (si <= 1e-12) { T = Tn; swingPath(L, p0, T, s, A); continue; }
                const B = swingPath(L, p0, Tn, s, sw2);
                const sp = Math.min(1, Math.max(0, (s - si) / (1 - si)));
                const gh = Math.min(1, Math.max(0, (sp - 0.1) / 0.9)), g = gh * gh * (3 - 2 * gh);
                const Nr = L.Nw || L.N;
                const d = T.p.distanceTo(Tn.p) + Math.abs(Tn.th - T.th) * Math.hypot(Nr.x, Nr.z);
                const sl = Math.sin(Math.PI * sp), arc = sl * sl * Math.min(1, d / (0.35 * stride0));
                A.pos.lerp(B.pos, g);
                A.up = Math.max(A.up + (B.up - A.up) * g, arc);
                A.h = Math.max(A.h + (B.h - A.h) * g, (L.lift ?? lift) * arc);
                A.th += (B.th - A.th) * g;
                A.w += (B.w - A.w) * g;
                T = Tn;
            }
            foot = A.pos.clone();
            up = A.up * low;
            // (D4.1b) a slot's own swing lift where its case gave it one (L.lift: the tarantula's front legs swing at the height
            // of its back); every other slot the gait's one lift (swingPath)
            foot.y += A.h * low;
            th = A.th;
            L.w = A.w;
        }
        L.ph = ph; L.stance = !air; L.up = up; L.swing = s; L.target = foot.clone();
        return { foot, th, up };
    }
    // a new command at time t replaces whatever was scheduled after t (a walkTo's remaining plan) and keeps the other control's
    // last target (sched stays sorted: ctl reads it in order)
    // (A1) A COMMAND NEVER MOVES A PLANTED FOOT: a stance's plant is where the body will stand at its stance's centre, which can lie
    // after the command; so every foot standing at t keeps the plant the schedule before the command gave it (frozen, tagged with
    // t: a later command at an earlier time, which pops this one, drops it too). A swing re-targets in the air, as it should. (A
    // walkTo called mid-walk slid the stance feet up to a stride's centre shift: the B11 controls never froze them.)
    // (D4.1b fix 2) A slot with the D4.1b records is frozen AT THE MOMENT THE COMMAND IS MADE (tF: the present, api.now; a command
    // dated in the past at its own time), whatever time the command is dated: a foot standing then keeps the plant it stands
    // on, and every swing in the air then records the plan it flew to before (footW blends from it). MOUNT's line freezes the
    // feet standing at the command's OWN time; for a command dated later (walkTo's turn, walk and stop, each filed by
    // command() at its own time; speed(v, t) with a later t) that left a foot standing NOW free to take a new plant in the
    // frame the command was made (a stop dated 0.06 s ahead inside a walkTo: a hind foot 3.47 mm, d41b_fix2 S7), and its
    // pruning, counted from the command's later cycle, dropped the plant a foot stood on NOW, which a walking plant then
    // replaced 18.56 mm away in one frame (the check's F1(a)). At the command's own later time nothing is frozen: no new
    // news reaches the feet then (the plan is known from the moment it is made, and the plants follow it). Every other slot
    // as MOUNT has it
    const frozen = new Map();
    function freezeAt(t) {
        for (const [, m] of frozen) for (const [kk, p] of m) if (p.tag > t) m.delete(kk);
        if (OPT) {
            for (const [, m] of swingRec) {
                for (const [kk, a] of m) {
                    const keep = a.filter((r) => r.tag <= t);
                    if (keep.length) m.set(kk, keep); else m.delete(kk);
                }
            }
        }
        if (!legs.length) return;
        const S = integrate(t + AHEAD);
        const tF = OPT ? Math.min(t, api.now) : t;
        for (const L of legs) {
            const cyc = at(S, S.C, L.walkW ? tF : t) + L.off;
            const k = Math.floor(cyc);
            if (L.walkW) {
                if (airborne(L, S, tF, k, cyc - k)) {          // in the air: the plan it flew to before
                    let m = swingRec.get(L);
                    if (!m) swingRec.set(L, (m = new Map()));
                    const a = m.get(k) || [];
                    if (!a.some((r) => Math.abs(r.tag - tF) < 1e-12)) a.push({ tag: tF, p1: planW(L, S, tF, k + 1) });
                    m.set(k, a);
                    for (const kk of [...m.keys()]) if (kk < k - 1) m.delete(kk);
                    continue;
                }
                let m = frozen.get(L);
                if (!m) frozen.set(L, (m = new Map()));
                if (m.has(k)) continue;
                const p = plantW(L, S, tF, k);                 // frozen where it stands (its walk or its rest place)
                m.set(k, { p: p.p, th: p.th, w: p.w, tag: tF });
                for (const kk of [...m.keys()]) if (kk < k - 1) m.delete(kk);
                continue;
            }
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

// CROSS: THE OCTOPUS EYE'S OWN MOTION, moved here word for word from bestiary.js radialMotion (one law wherever an octopus eye is:
// on the octopus, radialMotion; grafted in another creature's eye ports, axolotl.js): SACCADES, a fixation held 1.7 s and a fast
// jump (~70 ms) to the next, both eyes together on a seeded schedule; the eye joint turned Ry(yaw) Rz(pitch) over its rest (its x
// the optical axis, its z level: the octopus's eye frame, which REROOT's eye graft keeps on the host's eye joint).
// h(i): the creature's own seeded draw in [0, 1) (radialMotion: hash01(i, seed)). DONOR_EYE: the eye motion a grafted eye brings
export const DONOR_EYE = { octopus_eye: 'saccade' };
export function eyeSaccade(t, h) {
    const seg = Math.floor(t / 1.7), f = t / 1.7 - seg;
    const pick = (s, o) => (h(s * 13 + o) - 0.5);
    const w = Math.min(1, f / 0.04);                         // ~70 ms saccade
    const yaw = (pick(seg - 1, 1) + (pick(seg, 1) - pick(seg - 1, 1)) * w) * 0.35;
    const pitch = (pick(seg - 1, 2) + (pick(seg, 2) - pick(seg - 1, 2)) * w) * 0.18;
    return { yaw, pitch };
}

// =============================================================================================== THE SLOT'S SOLVER (MOUNT)
// MOUNT (work/bestiary/remix_r1/mount/STAGED.md; CROSSBREED §4.3 / §4.5: "the base's gait schedules footfalls per limb SLOT; each
// slot's ANATOMY solver realises the step"): the solver a limb slot dispatches to, read from its chain record. A GRAFTED slot
// takes its DONOR's (the graft record's anatomy: a stag beetle's fore leg on an axolotl's or a dog's fore limb steps with the
// arthropod's tarsus solver), every other slot as before: its record's anatomy, else the species' (sp.anatomy[kind]), else the
// family's (an arthropod's legs 'tarsus', any other base's 'plantigrade')
export const DONOR_SOLVER = { arthropod_leg: 'tarsus', tarsus: 'tarsus', tentacle: 'tentacle', octopus_arm: 'tentacle',
    plantigrade: 'plantigrade', digitigrade: 'digitigrade', paw: 'paw', mech: 'mech', mech_leg: 'mech' };
export function slotAnatomy(c, sp = {}) {
    return DONOR_SOLVER[c?.graft?.anatomy] ?? c?.anatomy ?? sp.anatomy?.[c?.kind]
        ?? (sp.family === 'arthropod' ? 'tarsus' : 'plantigrade');
}
// an ARTHROPOD LEG SLOT's four solver joints from its record (the hexapod's B11 names generalised): the record's ik block
// (ik.coxa, ik.femur, ik.tibia, ik.tarsus) where it has one; on a grafted chain the graft's ROLES (the donor's tibia and first
// tarsomere by role, the femur and coxa the two host joints before that tibia: on an axolotl's fore limb grafted at its axilla
// ring, the radius is the femur and the humerus the coxa); else the arthropod chain's own order (families/arthropod.py: coxa,
// trochanter, femur, tibia, tarsus_1 ...)
export function tarsusSlot(c, js, bones) {
    const ik = c.ik || {};
    const by = (n) => (n ? bones.get(n) || null : null);
    let coxa = by(ik.coxa), femur = by(ik.femur), tibia = by(ik.tibia), tarsus = by(ik.tarsus);
    const g = c.graft;
    if (Array.isArray(g?.roles) && Array.isArray(g?.joints)) {
        const role = (r) => { const i = g.roles.indexOf(r); return i >= 0 ? by(g.joints[i]) : null; };
        tibia = tibia || role('tibia');
        tarsus = tarsus || role('tarsus_1') || role('tarsus');
        const ti = js.indexOf(tibia);
        // CROSS (work/bestiary/remix_r1/cross/STAGED.md), read on the first real bug-legged axolotl (REROOT's AX-X5): THE GRAFT ROOT
        // IS NO SOLVER JOINT. The root (graft.root: the host joint the part hangs from) carries the SOCKET collar's middle and the
        // sunk end of the donor's shell, and its own pivot need not be at the ring (the axolotl's radius_L turns about the old
        // elbow, 21 mm past the knee: a turn there swings the shell's sunk end through the upper arm's skin). It keeps its bind
        // relation to its parent, as M2's solver keeps arm0_08 (bestiary.js legPose: "the graft root and the knee keep their BIND
        // relation but for the knee's flex"). The FEMUR is the host's last free joint before it (the axolotl's humerus: the upper
        // arm from the shoulder to the knee), and the COXA the joint the record names (ik.coxa / graft.coxa), else that same
        // joint: a ball joint takes the yaw and the swing both. A graft whose root is not in the chain keeps MOUNT's rule (the
        // two joints before the tibia)
        const ri = g.root ? js.findIndex((b) => b && b.name === g.root) : -1;
        if (ri >= 0 && ri < ti) {
            femur = femur || (ri >= 1 ? js[ri - 1] : js[ri]);
            coxa = coxa || by(g.coxa) || femur;
        }
        femur = femur || (ti >= 1 ? js[ti - 1] : null);
        coxa = coxa || (ti >= 2 ? js[ti - 2] : null);
    }
    return { coxa: coxa || js[0], femur: femur || js[2] || js[1], tibia: tibia || js[3], tarsus: tarsus || js[4] };
}
// CROSS: A DONOR ARTHROPOD LEG'S STAND ON ITS HOST, set on the bones BEFORE its rest is read (the hexapod's own rule for the
// beetle's rig.stand, above: "set on the bones BEFORE the rest is read"). A grafted leg is bound where the forge put it (REROOT's
// AX-X5: the tibia level at the host's elbow height, the tarsus rising 43 deg from it: its foot's rest place hung in the air and
// the leg walked there). Its stand is found from the leg itself and the host's ground, no number of this cross in it:
//   * the leg points STRAIGHT OUT from its femur's joint (the root frame's lateral axis on its side): a stance then sweeps past it
//     tangentially, which asks the least reach of a leg whose knee sits in a collar;
//   * the KNEE folds the anatomical way (+ about its own z) until the femur-to-ankle reach is `reserve` short of the straight leg's
//     (G.reachReserve, 2 %: the gait's sway and a stance's ends need reach in hand; the straight leg has none);
//   * the FOOT stands by the beetle's own rig.stand rule (b10/r01_rig.py, B10b: "the rise and each pitch measured on the drawn
//     geometry; the claws back at their bind height, every tarsus point over them, the tibiae clear"), measured here on this
//     leg's DRAWN geometry (drawnLow: the skinned vertices riding its joints): the tarsus turned about its own hinge only until
//     the CLAWS' lowest point rests on the ground (groundY + tipClear, 0.3 mm: the beetle's own claw height 0.317 mm at x10),
//     and the ankle raised from the level foot's height until the tibia's toothed apex and every tarsus point (its setae with
//     it) clear the ground too. Without drawn geometry (a record-only test): the tip socket on the ground, the tarsus level.
// The coxa yaws about the up axis and the femur swings in the leg's vertical plane (the solver's own two steps), a few passes
// until the foot rests. Returns the stand's numbers for the probes; the bones are left standing
function drawnLow(group, Pinv) {
    // the lowest drawn point (P's frame y) of the skinned vertices whose heaviest joint is one of `bones`, as the pose stands
    const cache = new Map();
    const v = new THREE.Vector3();
    return (bones) => {
        const set = new Set(bones.filter(Boolean));
        let low = Infinity;
        group.traverse((o) => {
            if (!o.isSkinnedMesh || !o.geometry?.attributes?.skinIndex) return;
            const key = `${o.uuid}|${[...set].map((b) => b.name).join(',')}`;
            if (!cache.has(key)) {
                const g = o.geometry, si = g.attributes.skinIndex, sw = g.attributes.skinWeight, ids = [];
                const on = o.skeleton.bones.map((b) => set.has(b));
                if (on.some(Boolean)) {
                    for (let i = 0; i < si.count; i++) {
                        let cmax = 0, w = sw.getX(i);
                        for (let q = 1; q < 4; q++) if (sw.getComponent(i, q) > w) { w = sw.getComponent(i, q); cmax = q; }
                        if (on[si.getComponent(i, cmax)]) ids.push(i);
                    }
                }
                cache.set(key, ids);
            }
            const ids = cache.get(key);
            if (!ids.length) return;
            const pos = o.geometry.attributes.position;
            for (const i of ids) {
                o.applyBoneTransform(i, v.fromBufferAttribute(pos, i));
                v.applyMatrix4(o.matrixWorld).applyMatrix4(Pinv);
                if (v.y < low) low = v.y;
            }
        });
        return low;
    };
}
// CROSS: what is DRAWN under each of a chain's joints at the bind: over the skinned vertices whose heaviest joint it is, the
// farthest along the joint's own -y (a chord frame's y is the aboral side: bestiary.js fleshReach's measure, on any creature's
// meshes). Read before anything poses the bones. Returns [m] per joint (0 where no vertex rides it)
export function drawnReach(group, joints) {
    // (in the group's own frame: the creature's authored size, whatever size the group shows it at)
    group.updateMatrixWorld(true);
    const gi = new THREE.Matrix4().copy(group.matrixWorld).invert(), W = new THREE.Matrix4();
    const at = new Map(joints.map((b, k) => {
        W.multiplyMatrices(gi, b.matrixWorld);
        return [b, { k, P: new THREE.Vector3().setFromMatrixPosition(W), Y: new THREE.Vector3().setFromMatrixColumn(W, 1).normalize() }];
    }));
    const out = new Array(joints.length).fill(0.0);
    const v = new THREE.Vector3(), seen = new Set();
    group.traverse((o) => {
        if (!o.isSkinnedMesh || !o.geometry?.attributes?.skinIndex || seen.has(o.geometry.attributes.position)) return;
        seen.add(o.geometry.attributes.position);
        const pos = o.geometry.attributes.position, si = o.geometry.attributes.skinIndex, sw = o.geometry.attributes.skinWeight;
        const sb = o.skeleton.bones;
        W.multiplyMatrices(gi, o.matrixWorld);
        for (let i = 0; i < pos.count; i++) {
            let c = 0, w = sw.getX(i);
            for (let q = 1; q < 4; q++) if (sw.getComponent(i, q) > w) { w = sw.getComponent(i, q); c = q; }
            const e = at.get(sb[si.getComponent(i, c)]);
            if (!e) continue;
            const d = -v.fromBufferAttribute(pos, i).applyMatrix4(W).sub(e.P).dot(e.Y);
            if (d > out[e.k]) out[e.k] = d;
        }
    });
    return out;
}
// CROSS (r1c): THE DRAWN SUPPORT of a set of joints: the vertices each of them carries alone (weight >= 0.999: a shell rigid on
// its joint), kept in that joint's own frame, read once. low(Pinv[, at]) is their lowest point now (P's frame y; `at` takes its
// place): what drawnLow measures, without skinning a vertex, so a solver can ask it every frame
export function drawnSupport(group, bones) {
    const set = new Set(bones.filter(Boolean));
    const per = new Map([...set].map((b) => [b, []]));
    const v = new THREE.Vector3(), inv = new THREE.Matrix4();
    group.updateMatrixWorld(true);
    const seen = new Set();
    group.traverse((o) => {
        if (!o.isSkinnedMesh || !o.geometry?.attributes?.skinIndex || seen.has(o.geometry.attributes.position)) return;
        seen.add(o.geometry.attributes.position);
        const g = o.geometry, si = g.attributes.skinIndex, sw = g.attributes.skinWeight, pos = g.attributes.position;
        const sb = o.skeleton.bones;
        if (!sb.some((b) => set.has(b))) return;
        for (let i = 0; i < si.count; i++) {
            let c = 0, w = sw.getX(i);
            for (let q = 1; q < 4; q++) if (sw.getComponent(i, q) > w) { w = sw.getComponent(i, q); c = q; }
            const b = sb[si.getComponent(i, c)];
            if (w < 0.999 || !set.has(b)) continue;
            o.applyBoneTransform(i, v.fromBufferAttribute(pos, i));
            v.applyMatrix4(o.matrixWorld).applyMatrix4(inv.copy(b.matrixWorld).invert());
            per.get(b).push(v.x, v.y, v.z);
        }
    });
    const parts = [...per].filter(([, a]) => a.length).map(([bone, a]) => ({ bone, p: Float64Array.from(a) }));
    const M = new THREE.Matrix4();
    const low = (Pinv, at = null) => {
        let lo = Infinity;
        for (const { bone, p } of parts) {
            const e = M.multiplyMatrices(Pinv, bone.matrixWorld).elements;
            for (let i = 0; i < p.length; i += 3) {
                const y = e[1] * p[i] + e[5] * p[i + 1] + e[9] * p[i + 2] + e[13];
                if (y < lo) {
                    lo = y;
                    if (at) at.set(e[0] * p[i] + e[4] * p[i + 1] + e[8] * p[i + 2] + e[12], y, e[2] * p[i] + e[6] * p[i + 1] + e[10] * p[i + 2] + e[14]);
                }
            }
        }
        return lo;
    };
    return { low, count: parts.reduce((s, x) => s + x.p.length / 3, 0) };
}
// CROSS (r1c): A POSED LIMB LIFTED CLEAR OF THE GROUND. A pose that no solver planted (a donor leg part way between its walk
// and its swim lie: each joint's rotation blended, so the shoulder's blend can swing the foot down through the floor: MEASURED
// 17.9 mm under it 0.2 s into a swim) is turned at its shoulder (L.femur), about the level axis square to the line from the
// shoulder to its lowest drawn point, until that point stands on the ground; a few passes (another point may then be the
// lowest). `support` is a drawnSupport of the limb's shells. Returns how far it was lifted (0: it was clear, nothing touched)
export function liftClear(L, ops, support, groundY, passes = 4) {
    const V3 = THREE.Vector3;
    let lifted = 0.0;
    const at = new V3();
    for (let k = 0; k < passes; k++) {
        const need = groundY - support.low(ops.Pinv, at);
        if (need <= 1e-6) break;
        const r = at.clone().sub(ops.inP(L.femur)), rho = r.length();
        const lvl = new V3(r.x, 0, r.z);
        if (rho < 1e-6 || lvl.lengthSq() < 1e-12) break;
        const n = new V3().crossVectors(lvl.normalize(), new V3(0, 1, 0)).normalize();        // (a + turn lifts the point)
        const a0 = Math.asin(Math.max(-1, Math.min(1, r.y / rho))), a1 = Math.asin(Math.max(-1, Math.min(1, (r.y + need) / rho)));
        ops.setWorldQ(L.femur, new THREE.Quaternion().setFromAxisAngle(n, a1 - a0).multiply(ops.qInP(L.femur)));
        lifted += need;
    }
    return lifted;
}
export function tarsusStand(L, tip, ctx, foot = null) {
    const V3 = THREE.Vector3, Q = THREE.Quaternion;
    const { ops, G = {}, root0, group } = ctx;
    const { inP, qInP, setWorldQ, aim } = ops;
    const UP = new V3(0, 1, 0);
    const groundY = G.groundY ?? 0.0, clear = G.tipClear ?? 0.0003, reserve = G.reachReserve ?? 0.02;
    const side = L.side === 'R' ? -1 : 1;
    const q0 = { tibia: L.tibia.quaternion.clone(), tarsus: L.tarsus.quaternion.clone() };
    const F = inP(L.femur);
    const reach = () => inP(L.tarsus).distanceTo(F);
    // the knee's fold for the reserve (the reach falls as it folds: a bisection on the bones)
    const setKnee = (f) => { L.tibia.quaternion.copy(q0.tibia).multiply(new Q().setFromAxisAngle(ZAX, f)); L.tibia.updateMatrixWorld(true); };
    setKnee(0.0);
    const dStraight = reach();
    // (inside the socketed knee's own range where the slot has one: ctx.kneeRange, about the bind)
    let lo = Math.max(0.0, ctx.kneeRange?.[0] ?? 0.0), hi = Math.min(1.2, ctx.kneeRange?.[1] ?? 1.2);
    let dWant = (1.0 - reserve) * dStraight;
    // (r1c) A KNEE WITH STOPS (ctx.kneeStops: the record's stops, [lo, hi] rad about its bind) STANDS IN THE MIDDLE OF ITS REACH:
    // the reach half way between the reaches at its two stops. The 2 % rule above is for a leg bound straight (its bind is its
    // longest reach, so it only needs room to lengthen). A leg cut at the femur is bound at the beetle's own rest knee (92.5 deg
    // included) and its fold stop sits 19 deg from that bind (the girth-scaled club meets the tibia's teeth): standing 2 % short
    // of the bind left 2.5 mm of reach to shorten, and the salamander's stance asks 4.4 (its trunk sways toward the planted
    // foot), so the knee stood on its stop and the planted foot missed by 2.3 mm. From the middle a stance has the same reach in
    // hand to shorten as to lengthen (the beetle's own rest is the middle of its knee's range too: 92.5 of 25..165 deg)
    const KS = Array.isArray(ctx.kneeStops) && ctx.kneeStops[1] > ctx.kneeStops[0] ? ctx.kneeStops : null;
    if (KS) {
        setKnee(KS[0]); const dExt = reach();
        setKnee(KS[1]); const dFold = reach();
        if (dExt > dFold) { lo = KS[0]; hi = KS[1]; dWant = 0.5 * (dExt + dFold); }
    }
    for (let it = 0; it < 40; it++) { const m = 0.5 * (lo + hi); setKnee(m); if (reach() > dWant) lo = m; else hi = m; }
    const knee = 0.5 * (lo + hi);
    setKnee(knee);
    const d = reach();
    // the coxa's yaw to straight out (about the up axis, from the bind's heading of the ankle seen from the coxa)
    const C = inP(L.coxa), A0 = inP(L.tarsus);
    const lat = new V3(side, 0, 0).applyQuaternion(root0.q);
    const yaw = Math.atan2(lat.x, lat.z) - Math.atan2(A0.x - C.x, A0.z - C.z);
    setWorldQ(L.coxa, new Q().setFromAxisAngle(UP, Math.atan2(Math.sin(yaw), Math.cos(yaw))).multiply(qInP(L.coxa)));
    // the foot: the femur swung in the leg's vertical plane so the ankle stands at a height hA, the tarsus turned about its own
    // hinge (a secant on its angle) until a measure of it is zero: first its first tarsomere's axis LEVEL with the tip socket on
    // the ground (the level foot's ankle height), then, on the drawn geometry, the CLAWS' lowest point on the ground at each
    // ankle height tried, the ankle raised until the tibia's and the tarsus's lowest points clear the ground
    const low = foot && group ? drawnLow(group, ops.Pinv) : null;
    let hA = groundY + clear, trim = 0.0;
    const setAnkle = (h) => {
        const Fp = inP(L.femur);
        const drop = Math.max(-d, Math.min(d, h - Fp.y));
        const dir = lat.clone().multiplyScalar(Math.sqrt(Math.max(0, d * d - drop * drop))).add(new V3(0, drop, 0)).normalize();
        aim(L.femur, Fp, inP(L.tarsus), dir);
    };
    // (r1c) the ankle held inside its stops (ctx.ankleRange: about its bind, which q0.tarsus is here), where the slot has them
    const AR = ctx.ankleRange || null;
    const inAR = (a) => (AR ? Math.max(AR[0], Math.min(AR[1], a)) : a);
    const hinge = (measure) => {
        const at = (a) => {
            L.tarsus.quaternion.copy(q0.tarsus).multiply(new Q().setFromAxisAngle(ZAX, inAR(a)));
            L.tarsus.updateMatrixWorld(true);
            return measure();
        };
        let x0 = trim, f0 = at(x0), x1 = trim + 0.05, f1 = at(x1);
        for (let it = 0; it < 24 && Math.abs(f1) > 1e-9 && Math.abs(f1 - f0) > 1e-14; it++) {
            const x2 = x1 - f1 * (x1 - x0) / (f1 - f0);
            x0 = x1; f0 = f1; x1 = x2; f1 = at(x1);
        }
        trim = inAR(x1);
        at(trim);
    };
    const level = () => new V3(1, 0, 0).applyQuaternion(qInP(L.tarsus)).y;
    for (let pass = 0; pass < 8; pass++) {
        setAnkle(hA);
        hinge(level);
        const e = (tip ? inP(tip).y : inP(L.tarsus).y) - (groundY + clear);
        if (Math.abs(e) < 1e-7) break;
        hA -= e;
    }
    let lows = null;
    if (low) {
        const claws = () => low(foot.claws) - (groundY + clear);
        for (let pass = 0; pass < 12; pass++) {
            setAnkle(hA);
            hinge(claws);
            lows = { tibia: low([L.tibia]), tarsus: low(foot.tarsi), claws: low(foot.claws) };
            let need = (groundY + clear) - Math.min(lows.tibia, lows.tarsus);
            // (r1c loop 2, 11-12) AN ANKLE ON ITS STOP CANNOT LAY THE CLAWS ON THE GROUND: the hinge above turns only inside
            // ctx.ankleRange, and a leg whose tibia stands steep asks it to open past its closing stop (the knee-down leg at M2's
            // proportions: the stop 1 deg from the bind, the level foot 11.6 deg past it; MEASURED at the stand: the tarsomeres
            // just clear of the plane and the claws 2.23 mm UNDER it, in every stance too). What the hinge cannot give, the
            // ankle's height gives (the beetle's own rule: the claws on the ground, every tarsus point over them): once the tibia
            // and the tarsus are clear, the claws' own shortfall raises the ankle and the hinge is solved again. Only where this
            // loop used to stop with the claws under the ground: a leg whose hinge reached it (every earlier leg: the stout legs'
            // claws 0.0000 mm off the plane) takes the very steps it took, and a leg without stops (M2's) never comes here
            if (need < 1e-6 && AR) need = (groundY + clear) - lows.claws;
            if (need < 1e-6) break;
            hA += need;
        }
    }
    return { knee, trim, reach: d, straight: dStraight, ankleY: inP(L.tarsus).y, tipY: tip ? inP(tip).y : null, yaw, lows };
}
// the tarsus solver's rest data on a slot (L.coxa, femur, tibia, tarsus set): each joint in P's frame, the femur's and the tibia's
// lengths, the foot's rest place in the root's frame and the tarsus's rest rotation there (the B11 hexapod's arithmetic, in its
// order: the beetle's legs give the very numbers they did)
export function tarsusFrames(L, ops, root0, rootInv0) {
    const { inP, qInP } = ops;
    L.C = inP(L.coxa); L.F = inP(L.femur); L.K = inP(L.tibia); L.A = inP(L.tarsus);
    L.Lf = L.F.distanceTo(L.K); L.Lt = L.K.distanceTo(L.A);
    L.N = L.A.clone().applyMatrix4(rootInv0);                 // the foot's rest place in the root's frame
    L.qTar = qInP(L.tarsus).premultiply(root0.q.clone().invert());   // the tarsus's rest rotation in the root's frame
    return L;
}
// the solver function a slot's anatomy calls (makeSolvers' names)
export const solverKey = (anatomy) => (anatomy === 'tentacle' ? 'tentacle' : anatomy === 'tarsus' ? 'tarsus' : 'limb');
// a slot's SOLVER INPUTS from its record (L.anatomy set; js the record's joints as bones) and its solver's rest data: a tentacle
// the chain's joints to its tip socket (the path solve); an arthropod leg tarsusSlot's four (the tarsus solver; L.contact its
// tarsus, for the probes); a limb (plantigrade / digitigrade / paw / mech) its upper, lower, ankle and contact joints, the
// record's ik block else the chain's last four (limbedMotion's rule, moved here so the hexapod's grafted slots share it)
export function slotInit(solvers, L, c, js, ctx) {
    const { bones, group, G, ops, root0, rootInv0 } = ctx;
    const n = js.length;
    if (L.anatomy === 'tentacle') {
        L.joints = js; L.tipNode = c.tip ? (group.getObjectByName(c.tip) || null) : null;
        solvers.tentacleInit(L);
    } else if (L.anatomy === 'tarsus') {
        Object.assign(L, tarsusSlot(c, js, bones));
        // (r1c, the lead's call (c)) THE ANKLE'S STOPS: the graft record's stops (cross/tests/g08_stops.py: each joint swept on
        // the shipped shells to contact, 2 deg backed off; [lo, hi] rad about its own fold axis z from its BIND), read with the
        // ankle's bind rotation, before anything poses it: the stand and every frame's solve hold the ankle inside them
        const stp = c.graft?.stops || null;
        if (stp && L.tarsus && Array.isArray(stp[L.tarsus.name])) {
            L.ankleRange = [Number(stp[L.tarsus.name][0]), Number(stp[L.tarsus.name][1])];
            L.ankleBind = L.tarsus.quaternion.clone();
        }
        // (the ankle's second freedom: its side tilt's stops, about its own y from the bind: stops_side)
        const sds = c.graft?.stops_side || null;
        if (sds && L.tarsus && Array.isArray(sds[L.tarsus.name])) {
            L.ankleSide = [Number(sds[L.tarsus.name][0]), Number(sds[L.tarsus.name][1])];
            L.ankleBind = L.ankleBind || L.tarsus.quaternion.clone();
        }
        // CROSS: a GRAFTED arthropod leg stands on this host's floor before its rest is read (tarsusStand; ctx.stand false: at
        // its bind, as MOUNT read it)
        if (c.graft && (G.stand ?? ctx.stand) !== false) {
            L.tipNode = c.tip ? (group.getObjectByName(c.tip) || null) : null;
            // the foot's joints past the ankle: the tarsomeres, and the last one the claws'
            const fj = js.slice(js.indexOf(L.tarsus));
            // (the socketed knee's range about its bind, where the record or the gait gives one: the stand folds inside it)
            const kr = G.kneeRange ?? c.graft.knee_range;
            if (Array.isArray(kr) && kr.length === 2) L.kneeRange = [Number(kr[0]), Number(kr[1])];
            // (r1c, the lead's call (a)) THE HOST'S OWN FORE-FOOT CONTACT PLANE: where the record carries it (the forge's
            // contact_y: the native foot's lowest drawn point at the host's stand) the claws stand ON it, no clearance (the
            // host's own fingers press there); without it the floor at y 0 and the beetle's claw height, as before
            const cy = c.graft.contact_y;
            const Gs = Number.isFinite(cy) && G.groundY == null ? { ...G, groundY: cy, tipClear: G.tipClear ?? 0.0 } : G;
            // (r1c) the knee's own stops from the record (the stand takes the middle of their reach: tarsusStand)
            const ks = stp && L.tibia && Array.isArray(stp[L.tibia.name]) ? [Number(stp[L.tibia.name][0]), Number(stp[L.tibia.name][1])] : null;
            L.stand = tarsusStand(L, L.tipNode, { ...ctx, G: Gs, kneeRange: L.kneeRange || null, ankleRange: L.ankleRange || null, kneeStops: ks },
                fj.length >= 2 ? { tarsi: fj.slice(0, -1), claws: fj.slice(-1) } : null);
            L.kneeStand = L.stand.knee;
            // (r1c) with the host's contact plane in the record, the leg keeps its tibia off that plane every frame (the tarsus
            // solver's clearance pass): the tibia's and the claws' drawn support, read here once
            if (Number.isFinite(cy) && fj.length >= 2 && group) {
                const cl = { shank: drawnSupport(group, [L.tibia]), claws: drawnSupport(group, fj.slice(-1)),
                    leg: drawnSupport(group, [L.tibia, ...fj]), groundY: Gs.groundY ?? 0.0, margin: Gs.tipClear ?? 0.0 };
                if (cl.shank.count && cl.claws.count) L.clearance = cl;
            }
        }
        tarsusFrames(L, ops, root0, rootInv0);
        L.contact = L.tarsus;
        if (L.range == null) L.range = (G.coxaRange ?? 35) * Math.PI / 180;
        solvers.tarsusInit(L);
        // (D4.1b) THE SECOND HINGE, opt-in by the slot's record: ik.hinge2 names the joint beyond the knee that shares the reach (a
        // tarantula's tibia-metatarsus joint); ik.band the femur's elevation it holds [lo, hi], ik.turn2 that joint's own turn
        // from rest [lo, hi] (+ closes it), ik.knee the knee's included angle [lo, hi], all in degrees. A record without
        // ik.hinge2 is solved as before
        const h2 = c.ik?.hinge2 ? bones.get(c.ik.hinge2) : null;
        if (h2) {
            L.hinge2 = h2;
            L.h2 = { band: c.ik.band, turn: c.ik.turn2, knee: c.ik.knee };
            solvers.tarsus2Init(L);
            L.walkW = true;              // (D4.1b fix) its rules are the walking animal's: the scheduler gives it the walk weight L.w
        }
    } else {
        const ik = c.ik || {};
        L.upper = bones.get(ik.upper) || js[n - 4] || js[0];
        L.lower = bones.get(ik.lower) || js[n - 3];
        L.ankle = bones.get(ik.ankle) || js[n - 2];
        L.contact = bones.get(ik.contact) || js[n - 1];
        L.toe = { plantigrade: G.toe, digitigrade: -0.5 * G.toe, paw: -0.5 * G.toe, mech: 0 }[L.anatomy] ?? 0;
        solvers.limbInit(L);
    }
    return L;
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
    // (D4.1b fix) the place the coxa's yaw is measured from: a slot with a walk place (L.Nw) measures it from the place its foot
    // stands on: the walk place on a walking plant (L.w 1), the rest place on a standing one (L.w 0: the bind), between them
    // through the step from one to the other; every other slot from its rest place, as before (the twin: TarsusLeg.ref)
    const vNr = new V3();
    const refN = (L) => {
        if (!L.Nw) return L.N;
        const w = L.w ?? 1;
        return w === 1 ? L.Nw : w === 0 ? L.N : vNr.copy(L.N).lerp(L.Nw, w);
    };
    // ---------------------------------------------------------------------------------- tarsus (an arthropod leg; B11 verbatim)
    function tarsusInit(L) {
        restWorldQ.set(L.coxa, qInP(L.coxa).premultiply(root0.q.clone().invert()));
    }
    function tarsus(L, foot, th, up, body) {
        if (L.hinge2) return tarsus2(L, foot, th, up, body);   // (D4.1b) a slot with a second hinge: below
        const { vB, vC, qa, qb, mA } = ops;
        // the coxa: yaw the leg's plane toward the foot about the body's up (in the root's frame), clamped to its range
        const rinv = mA.copy(body.m).invert();
        const fR = vB.copy(foot).applyMatrix4(rinv);           // the foot in the root's frame
        const cR = vC.copy(L.C).applyMatrix4(rootInv0);         // the coxa joint in the root's frame (the body is rigid on the root)
        const Nr = refN(L);
        const a0 = Math.atan2(Nr.x - cR.x, Nr.z - cR.z), a1 = Math.atan2(fR.x - cR.x, fR.z - cR.z);
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
        // CROSS: A SOCKETED KNEE turns only as far as its collar is built for, where the slot says how far (L.kneeRange: [lo, hi]
        // rad about the knee's BIND, the graft record's knee_range or the gait's kneeRange; L.kneeStand the stand's own fold, which
        // this solve starts from): past it the knee holds and the ankle misses along the leg's line (L.err says by how much). A
        // slot with no range (the beetle's own legs; REROOT's first glbs) folds as the solve asks, as before
        if (L.kneeRange) {
            const xc = Math.max(L.kneeRange[0] - (L.kneeStand ?? 0), Math.min(L.kneeRange[1] - (L.kneeStand ?? 0), x1));
            if (xc !== x1) knee(xc);
        }
        aim(L.femur, F, inP(L.tarsus), toFoot.clone().normalize());
        L.err = inP(L.tarsus).distanceTo(foot);                // the IK's miss (the glb's units): 0 while the foot is in reach
        const K3 = inP(L.tibia);
        L.knee = F.clone().sub(K3).angleTo(inP(L.tarsus).sub(K3)) * 180 / Math.PI;    // the femur-tibia included angle (deg)
        // (D4.1b's landing, 11-20) THIS LEG SOLVED AGAIN TO A MOVED ANKLE, for the foot's passes (tarsusFoot, below): r1c's
        // solveTo, moved up here word for word from among the foot's lines, which are now tarsus2()'s too: each solver hands
        // them its own way of solving its leg again (this one: the knee's fold for the new distance, inside its range, the
        // femur turned to it)
        const solveTo = (target) => {
            const toF = target.clone().sub(F);
            const dd = Math.max(dMin, Math.min(dMax, toF.length()));
            const w2 = Math.acos(Math.max(-1, Math.min(1, (L.Lf * L.Lf + L.Lt * L.Lt - dd * dd) / (2 * L.Lf * L.Lt))));
            const kn = (dl) => { L.tibia.quaternion.copy(q0).multiply(qa.setFromAxisAngle(ZAX, dl)); L.tibia.updateMatrixWorld(true); return incl() - w2; };
            let a0_ = 0.0, g0 = kn(0.0), a1_ = -0.05, g1 = kn(a1_);
            for (let it = 0; it < 10 && Math.abs(g1) > 1e-7 && Math.abs(g1 - g0) > 1e-12; it++) {
                const a2 = a1_ - g1 * (a1_ - a0_) / (g1 - g0);
                a0_ = a1_; g0 = g1; a1_ = a2; g1 = kn(a1_);
            }
            if (L.kneeRange) {
                const xc = Math.max(L.kneeRange[0] - (L.kneeStand ?? 0), Math.min(L.kneeRange[1] - (L.kneeStand ?? 0), a1_));
                if (xc !== a1_) kn(xc);
            }
            aim(L.femur, F, inP(L.tarsus), toF.clone().normalize());
            L.err = inP(L.tarsus).distanceTo(target);
            const K4 = inP(L.tibia);
            L.knee = F.clone().sub(K4).angleTo(inP(L.tarsus).sub(K4)) * 180 / Math.PI;
        };
        tarsusFoot(L, th, up, solveTo);
    }
    // ---------------------------------------------------------------------------------- the foot of a tarsus leg (ONE TAIL FOR BOTH)
    // (D4.1b's landing, 11-20; the lead's call) The last part of tarsus(), from "the tarsus: its rest lie" to its end, is this
    // function, its lines word for word, so that tarsus() and tarsus2() end in the same lines: the tarsus's lie, and on a
    // GRAFTED leg (a slot whose record carries the graft's stops and the host's contact plane: L.ankleRange, L.ankleSide,
    // L.clearance, read by slotInit) the ankle held inside its stops and the tibia and the claws kept off the host's ground.
    // A two-hinge leg grafted onto another host gets them exactly as a one-hinge leg does. A leg without a graft record (the
    // beetle's own legs, the tarantula's own) gets its tarsus's lie and nothing more, as before.
    // solveTo(target): the caller's solve of its own leg again to a moved ankle; called only on a leg with L.clearance
    function tarsusFoot(L, th, up, solveTo) {
        // the tarsus: its rest lie in the root's frame, turned with the foot's heading, its tip lifted through the swing
        const qT = new Q().setFromAxisAngle(UP, th).multiply(root0.q).multiply(L.qTar);
        if (up > 0) qT.multiply(new Q().setFromAxisAngle(new V3(0, 0, 1), -0.45 * up));
        setWorldQ(L.tarsus, qT);
        // (r1c, the lead's call (c)) A REAL STOP AT THE ANKLE (L.ankleRange: the record's stops, about the ankle's bind): the
        // tarsus keeps its lie in the world (its heading, its level) while the shoulder's swing tilts the tibia, so the ankle's
        // turn about its own hinge ran past the shells' contact (the check: tibia~tarsus_1 77 vertices beyond the bind's at
        // 0.58 rad). Its twist about the hinge (z) is held inside the stops; the turn off the hinge, the heading the solve
        // gives it, is kept. A slot without stops (the beetle's own legs, the first glbs): as before
        // (Fable, 11-10 17:xx) THE ANKLE HAS TWO FREEDOMS (the beetle's: "flex -20 / +45, side +-20", BEETLE_PLAN 6.3), and the
        // record carries a stop for each: `stops` its hinge's (about z), `stops_side` its tilt off the hinge (about its own y: the
        // foot's heading against the tibia's). ankleSplit reads the two from the pose (the swing-twist split about z: the twist
        // the hinge's turn, the swing's turn vector (x a roll about the bone, y the side tilt)); holdAnkle holds both inside
        // their stops (the roll about the bone, a few degrees, is kept)
        const ankleSplit = () => {
            const qr = L.ankleBind.clone().invert().multiply(L.tarsus.quaternion);
            // (q and -q are one rotation: the short way's sign, so the twist's angle reads inside -pi .. pi)
            if (qr.w < 0) qr.set(-qr.x, -qr.y, -qr.z, -qr.w);
            const tw = new Q(0, 0, qr.z, qr.w).normalize();
            const sw = qr.clone().multiply(tw.clone().invert());
            if (sw.w < 0) sw.set(-sw.x, -sw.y, -sw.z, -sw.w);
            const n = Math.hypot(sw.x, sw.y, sw.z), k = n > 1e-12 ? 2.0 * Math.acos(Math.min(1.0, sw.w)) / n : 0.0;
            return { a: 2.0 * Math.atan2(tw.z, tw.w), rx: sw.x * k, ry: sw.y * k };
        };
        const inRange = (v, r) => (r ? Math.max(r[0], Math.min(r[1], v)) : v);
        const holdAnkle = () => {
            if (!L.ankleRange && !L.ankleSide) return;
            const m = ankleSplit();
            const ac = inRange(m.a, L.ankleRange), yc = inRange(m.ry, L.ankleSide);
            L.ankle = m.a; L.ankleTilt = m.ry;
            if (ac !== m.a || yc !== m.ry) {
                const v = new V3(m.rx, yc, 0.0), turn = v.length();
                const swing = turn > 1e-12 ? new Q().setFromAxisAngle(v.multiplyScalar(1.0 / turn), turn) : new Q();
                L.tarsus.quaternion.copy(L.ankleBind).multiply(swing).multiply(new Q().setFromAxisAngle(ZAX, ac));
                L.tarsus.updateMatrixWorld(true);
                L.ankleHeld = (L.ankleHeld || 0) + 1;
            }
        };
        // (r1c, Fable 11-10) THE TIBIA CLEAR OF THE GROUND, EVERY FRAME (L.clearance: slotInit makes it for a grafted leg whose
        // record carries the host's contact plane). The stand lifts the ankle until the tibia's apex clears the ground (the
        // beetle's own rig.stand rule: "the tibiae clear"), but a stance turns the knee, and a leg whose sections were forged
        // at the ring's girth carries an apex 13 mm in radius on a 24 mm tibia: MEASURED over a walk, the apex's lowest point
        // swung 2.9 mm, to 2.2 mm UNDER the plane its claws stand on at mid-stance (the knee at its most folded). So each frame
        // the tibia's lowest DRAWN point (its own vertices, rigid on its joint) is read, and where it would pass under the
        // ground the ANKLE RISES by what is missing: planted, the foot ROCKS ABOUT ITS CLAWS' CONTACT (their lowest drawn point
        // stays where it stands, the ankle climbing the circle about it), so nothing slides; in the air the ankle just rises. The
        // leg is solved again to the moved ankle, the foot laid again and held inside its stops; a few passes (raising the
        // ankle folds the knee a little, which lowers the apex again: each pass recovers about half). A leg whose tibia is
        // clear (every frame of the beetle's own legs, and this one's whole swing) is untouched.
        // THE SIDE TILT THE SAME WAY (17:xx): a planted foot keeps its lie in the world while the tibia yaws round over it, and a
        // stance asked the ankle -22 .. +33 deg of side tilt (the gate: tibia~tarsus_2 1.06 mm deep). Past the side stop a
        // PLANTED foot TURNS ABOUT ITS CLAWS' TIP (a yaw about the vertical through the tip socket: the tip stays where it
        // touched down, the foot's heading follows the tibia by what the ankle cannot give); in the air the foot just follows
        // (holdAnkle). Both turns are one rigid move of the foot about its own contact, found together, a few passes.
        // THE HINGE'S CLOSING STOP THE SAME WAY (RUN 6, 18:4x): with the side tilt free to its +-20 deg the hinge's closing end is
        // 1 deg from the bind (g08_stops.py's corners: at -20 with the side at an end the tarsus meets the tibia by 1.3 mm), and
        // a stance asks about 3.5 deg of closing just after touchdown (the tibia at its steepest over a flat foot). holdAnkle
        // alone turned the foot about its ANKLE there, the claws 1.1-1.2 mm into the ground (the gate: THE FLOOR 1.13 mm, THE
        // FEET's drift 1.0-1.2 mm, THE PLANT 1.19 mm off). A planted foot whose ankle will not close further stands UP ON ITS
        // CLAWS: the same rock about the claws' contact, the ankle rising until the hinge is back on its stop (raising it opens
        // the joint twice over: the tarsus tips down toward its claws and the tibia lies flatter). First by the two levers
        // (1 / ankle-to-contact + 1 / tibia, the most the hinge can answer, so the first step falls short), then by the
        // measured answer; the rise only ever grows within a frame
        L.rise = 0.0; L.pivot = 0.0;
        // (the leg solved again to a moved ankle: the caller's solveTo. r1c loop 2 had it here, moved up from inside the
        // clearance block so the air pass below can use it; D4.1b's landing moved it on up into tarsus(), word for word)
        if (L.clearance) {
            const CL = L.clearance;
            const dipNow = () => CL.groundY + CL.margin - CL.shank.low(ops.Pinv);
            const tiltOver = () => { if (!L.ankleSide) return 0.0; const y = ankleSplit().ry; return y - inRange(y, L.ankleSide); };
            const hingeUnder = () => (L.ankleRange ? Math.min(0.0, ankleSplit().a - L.ankleRange[0]) : 0.0);    // (< 0: past the closing stop)
            let dip = dipNow(), over = tiltOver(), under = up > 0 ? 0.0 : hingeUnder();
            if (dip > 1e-6 || Math.abs(over) > 1e-4 || under < -1e-4) {
                const A0 = inP(L.tarsus), qT0 = qInP(L.tarsus);
                const pv0 = new V3();
                CL.claws.low(ops.Pinv, pv0);                        // the claws' contact (their lowest drawn point)
                const tip0 = L.tipNode ? inP(L.tipNode) : pv0.clone();
                const planted = !(up > 0) && A0.distanceTo(pv0) > 1e-6;
                // (how the side tilt answers a yaw of the foot about the vertical: the ankle's own y against the up axis; a secant
                // on the measured answer after the first pass)
                const yUp = new V3(0, 1, 0).applyQuaternion(qT0).y;
                let yawPrev = 0.0, overPrev = over, slope = Math.abs(yUp) > 0.2 ? yUp : 0.0;
                // (the hinge's answer to the ankle's rise, rad per unit of rise: the two levers first, the measured answer after)
                let gain = planted ? 1.0 / Math.max(A0.distanceTo(pv0), 1e-6) + 1.0 / Math.max(L.Lt, 1e-6) : 0.0;
                let risePrev = 0.0, underPrev = under;
                if (!planted) under = 0.0;
                for (let pass = 0; pass < 8 && (dip > 1e-6 || (planted && (under < -1e-4 || (slope !== 0.0 && Math.abs(over) > 1e-4)))); pass++) {
                    risePrev = L.rise; underPrev = under;
                    if (dip > 1e-6) L.rise += dip;
                    if (planted && under < -1e-4 && gain > 0.0) L.rise = Math.max(L.rise, risePrev - under / gain);
                    const target = A0.clone();
                    let qT1 = qT0.clone();
                    if (planted) {
                        if (slope !== 0.0 && Math.abs(over) > 1e-4) {
                            const y0 = L.pivot;
                            L.pivot -= over / slope;
                            yawPrev = y0; overPrev = over;
                        }
                        // the yaw about the vertical through the claws' tip, then the rock about the claws' contact
                        const qY = new Q().setFromAxisAngle(UP, L.pivot);
                        const A1 = tip0.clone().add(A0.clone().sub(tip0).applyQuaternion(qY));
                        const pv1 = tip0.clone().add(pv0.clone().sub(tip0).applyQuaternion(qY));
                        qT1.premultiply(qY);
                        const r = A1.clone().sub(pv1), rho = r.length();
                        const lvl = new V3(r.x, 0, r.z);
                        target.copy(A1);
                        if (L.rise > 0.0 && rho > 1e-6 && lvl.lengthSq() > 1e-12) {
                            const nAx = new V3().crossVectors(lvl.normalize(), UP).normalize();         // (a + turn lifts the ankle)
                            const y1 = Math.min(0.999 * rho, r.y + L.rise);
                            const rock = new Q().setFromAxisAngle(nAx, Math.asin(y1 / rho) - Math.asin(Math.max(-1, Math.min(1, r.y / rho))));
                            target.copy(pv1).add(r.applyQuaternion(rock));
                            qT1.premultiply(rock);
                        }
                    } else target.y += L.rise;
                    solveTo(target);
                    setWorldQ(L.tarsus, qT1);
                    dip = dipNow();
                    over = tiltOver();
                    if (planted) {
                        under = hingeUnder();
                        // (the measured answer of the hinge to the rise, while the hinge is still past its stop: a secant)
                        if (under < 0.0 && L.rise - risePrev > 1e-9) {
                            const g2 = (under - underPrev) / (L.rise - risePrev);
                            if (g2 > 0.05 * gain) gain = g2;
                        }
                    }
                    // (the measured answer of the tilt to the yaw, for the next pass)
                    if (planted && Math.abs(L.pivot - yawPrev) > 1e-6) {
                        const s2 = (over - overPrev) / (L.pivot - yawPrev);
                        if (Math.abs(s2) > 0.2) slope = s2;
                    }
                }
            }
        }
        holdAnkle();
        // (r1c loop 2, 11-12) IN THE AIR THE CLAWS STAY OVER THE GROUND TOO. The pass above keeps the TIBIA clear; the foot it
        // leaves to its lie, and holdAnkle then turns a foot whose hinge is past its closing stop about its ANKLE, tip down.
        // Planted, the foot stands up on its claws instead (above); in the air nothing answered, and on the frame before a
        // touchdown, the ankle already down at its stance height and the tibia at its steepest, the claws went through the
        // ground: MEASURED on the knee-down leg in a turn, 1.11 to 1.29 mm under the host's plane for that one frame of every
        // step (the gate: THE FLOOR 1.111 mm, bar 1), and on the next frame, planted, the ankle 1.30 mm higher with the claws
        // on the plane. So after the hold, a leg in the air whose lowest drawn point (tibia, tarsomeres and claws: CL.leg) is
        // under the ground rises at the ankle by what is missing, is solved again, and its foot laid and held again; a few
        // passes. A leg that is clear (the whole swing but its ends, and every leg without a contact plane) is untouched
        if (L.clearance && up > 0) {
            const CL = L.clearance;
            for (let pass = 0; pass < 4; pass++) {
                const dipA = CL.groundY + CL.margin - CL.leg.low(ops.Pinv);
                if (dipA <= 1e-6) break;
                L.rise += dipA;
                const target = inP(L.tarsus);
                target.y += dipA;
                solveTo(target);
                setWorldQ(L.tarsus, qT);
                holdAnkle();
            }
        }
    }
    // ---------------------------------------------------------------------------------- tarsus2 (D4.1b: an arthropod leg with a
    // SECOND HINGE beyond the knee; work/bestiary/research/tarantula_notes/d41b_NOTES.md; the forge's twin is
    // forge/families/arachnid.py TarsusLeg.solve2, the same steps in the same order)
    // One hinge places a foot by turning the femur: every change of reach raises or lowers it (a tarantula's front femora ran 10 to
    // 64 degrees a cycle and through each other). Here the far leg can shorten and lengthen at L.hinge2 (turned dm about its own z,
    // + closes it), and that one free turn is spent, from 0 (the one-hinge solution), on two rules:
    //   1. the FEMUR'S ELEVATION (the femur slot's joint to the knee, above level) back INTO ITS BAND: over the band's top the far
    //      leg is shortened until the femur stands on it, under its bottom lengthened;
    //   2. the KNEE INSIDE ITS RANGE and the foot in reach (this wins over the band).
    // dm never leaves the hinge's own range. For a given dm the leg is closed form in the femur slot's frame (no bone is touched
    // while searching): the ankle in the tibia slot's frame AT = mT + rot(zM, dm) aT; the reach |AF|^2 = C + rho cos(dl - phi) in
    // the knee's turn dl, solved on the rest's branch and clamped to what the hinge can give; the least turn Q that aims the
    // ankle at the foot; the femur's elevation and the knee's included angle.
    // (D4.1b fix, 11-11; d41b_NOTES E1-E2) Both rules are the WALKING animal's: scaled by the plant's walk weight L.w (0 on a
    // plant made standing: the leg is the bind). Each rule is ONE ITP root-find (toward2: the regula falsi point, truncated
    // toward the middle, projected into what halving would keep; Oliveira & Takahashi 2020) stopped at a bracket of H2_TOL,
    // never more steps than halving + H2_N0 (the 40 halvings it replaced cost 41 poses a rule; the twin's walk moved 1.4e-11
    // mm). A rule whose weight is 0 is not searched (its turn is 0 either way); the search allocates nothing (h2s scratch)
    const H2_TOL = 1e-12, H2_N0 = 1;
    // each rule engages over H2_SOFT of its measure past the edge (a smoothstep): a rule whose edge the hinge cannot reach
    // ramps to its limit instead of jumping there between two frames (the twin: arachnid.py H2_SOFT, _soft)
    const H2_SOFT = 2 * Math.PI / 180;
    const soft2 = (v) => { const x = Math.min(1, Math.max(0, v / H2_SOFT)); return x * x * (3 - 2 * x); };
    // the scratch of one solve (legs are solved one at a time): the leg's rest data H, the foot's distance and direction from the
    // femur slot's joint, the knee's vector and the tibia slot's rest turn carried by the femur slot's world turn; h2pose's out
    const h2s = { H: null, dRaw: 0, u: new V3(), kFw: new V3(), qFwT: new Q(), AT: new V3(), cur: new V3(), kq: new V3(),
        qA: new Q(), dl: 0, e: 0, knee: 0, fr: 0 };
    // the leg for one turn dm of the second hinge, in closed form, into h2s: dl (the knee's turn), knee (its included angle), fr
    // (the reach's margin: >= 0 the foot in reach); with aim also qA (the femur slot's least turn) and e (the femur's elevation)
    function h2pose(dm, aim) {
        const H = h2s.H;
        const AT = h2s.AT.copy(H.aT).applyAxisAngle(H.zM, dm).add(H.mT);
        const k = H.kT;
        const C = k.dot(k) + AT.dot(AT) + 2 * k.z * AT.z;
        const Pc = 2 * (k.x * AT.x + k.y * AT.y), Sc = 2 * (k.y * AT.x - k.x * AT.y);
        const rho = Math.hypot(Pc, Sc), phi = Math.atan2(Sc, Pc);
        const dMin = Math.sqrt(Math.max(0, C - rho)) + 1e-5, dMax = Math.sqrt(C + rho) - 1e-5;
        const d = Math.max(dMin, Math.min(dMax, h2s.dRaw));
        const dl = phi - (phi >= 0 ? 1 : -1) * Math.acos(Math.max(-1, Math.min(1, (d * d - C) / rho)));
        const c = Math.cos(dl), s = Math.sin(dl);
        h2s.dl = dl;
        h2s.knee = Math.acos(Math.max(-1, Math.min(1,
            -(k.x * (H.mT.x * c - H.mT.y * s) + k.y * (H.mT.x * s + H.mT.y * c) + k.z * H.mT.z) / (H.lk * H.lm))));
        h2s.fr = dMax - h2s.dRaw;
        if (aim) {
            const cur = h2s.cur.set(AT.x * c - AT.y * s, AT.x * s + AT.y * c, AT.z).applyQuaternion(h2s.qFwT).add(h2s.kFw)
                .normalize();
            h2s.qA.setFromUnitVectors(cur, h2s.u);
            h2s.e = Math.asin(Math.max(-1, Math.min(1, h2s.kq.copy(h2s.kFw).applyQuaternion(h2s.qA).y / H.lk)));
        }
    }
    // the four rules' measures (>= 0: the rule holds), made once
    const f1hi = (x) => { h2pose(x, true); return h2s.H.hi - h2s.e; };
    const f1lo = (x) => { h2pose(x, true); return h2s.e - h2s.H.lo; };
    const f2lo = (x) => { h2pose(x, false); return h2s.knee - h2s.H.klo; };
    const f2hi = (x) => { h2pose(x, false); return Math.min(h2s.H.khi - h2s.knee, h2s.fr / h2s.H.lk); };
    // the turn nearest xFrom, between xFrom (where the rule fails: fFrom = f(xFrom) < 0) and xTo, at which it holds (f >= 0); xTo
    // when it fails there too (the hinge goes as far as it can). ITP on t in [0, 1], x = xFrom + t (xTo - xFrom), the good end
    // returned (the twin: arachnid.py TarsusLeg.toward, the same steps)
    function toward2(f, xFrom, fFrom, xTo) {
        const fTo = f(xTo);
        if (fTo < 0) return xTo;
        const span = xTo - xFrom;
        const eps = 0.5 * H2_TOL / Math.abs(span);
        const nMax = Math.ceil(Math.log2(1 / (2 * eps))) + H2_N0;
        let a = 0, fa = fFrom, b = 1, fb = fTo;
        for (let j = 0; b - a > 2 * eps && fb !== 0; j++) {
            const xh = 0.5 * (a + b);
            const r = eps * 2 ** (nMax - j) - 0.5 * (b - a);
            const delta = 0.2 * (b - a) * (b - a);
            const xf = (fb * a - fa * b) / (fb - fa);
            const sg = xh >= xf ? 1 : -1;
            const xt = delta <= Math.abs(xh - xf) ? xf + sg * delta : xh;
            const x = Math.abs(xt - xh) <= r ? xt : xh - sg * r;
            const y = f(xFrom + x * span);
            if (y >= 0) { b = x; fb = y; } else { a = x; fa = y; }
        }
        return xFrom + b * span;
    }
    function tarsus2Init(L) {
        const qF = qInP(L.femur), qT = qInP(L.tibia), qM = qInP(L.hinge2);
        const pF = inP(L.femur), pK = inP(L.tibia), pM = inP(L.hinge2), pA = inP(L.tarsus);
        const qFi = qF.clone().invert(), qTi = qT.clone().invert();
        const rad = Math.PI / 180;
        L.h2r = {
            kF: pK.clone().sub(pF).applyQuaternion(qFi),            // the knee from the femur slot's joint, the femur slot's frame
            qFT: qFi.clone().multiply(qT),                           // the tibia slot's rest rotation in it
            kT: pK.clone().sub(pF).applyQuaternion(qTi),            // the same vector, the tibia slot's frame
            mT: pM.clone().sub(pK).applyQuaternion(qTi),            // the second hinge's joint from the knee
            zM: new V3(0, 0, 1).applyQuaternion(qTi.clone().multiply(qM)),   // the second hinge's axis, the tibia slot's frame
            aT: pA.clone().sub(pM).applyQuaternion(qTi),            // the ankle from the second hinge's joint
            lo: L.h2.band[0] * rad, hi: L.h2.band[1] * rad, mlo: L.h2.turn[0] * rad, mhi: L.h2.turn[1] * rad,
            klo: L.h2.knee[0] * rad, khi: L.h2.knee[1] * rad,
        };
        L.h2r.lk = L.h2r.kF.length(); L.h2r.lm = L.h2r.mT.length();
    }
    function tarsus2(L, foot, th, up, body) {
        const { vB, vC, qb, mA } = ops;
        // the coxa: as tarsus(), its yaw measured from the place the foot stands on (refN)
        const rinv = mA.copy(body.m).invert();
        const fR = vB.copy(foot).applyMatrix4(rinv);
        const cR = vC.copy(L.C).applyMatrix4(rootInv0);
        const Nr = refN(L);
        const a0 = Math.atan2(Nr.x - cR.x, Nr.z - cR.z), a1 = Math.atan2(fR.x - cR.x, fR.z - cR.z);
        let yaw = a1 - a0;
        yaw = Math.atan2(Math.sin(yaw), Math.cos(yaw));
        yaw = Math.max(-L.range, Math.min(L.range, yaw));
        const qCoxa = qb.setFromAxisAngle(UP, yaw);
        setWorldQ(L.coxa, qCoxa.multiply(body.q).multiply(qInPRest(L.coxa)));
        // (D4.1b's landing, 11-20) the leg below the coxa (tarsus2Leg: fix 2's lines, word for word), then THE FOOT AS
        // tarsus() ENDS (tarsusFoot: fix 2 had its three lines for the tarsus's lie here, "as tarsus()"; tarsus() has since
        // grown the graft's ankle stops and stand, r1c). A leg with a contact plane (L.clearance: a grafted leg) may be
        // solved again to a moved ankle by the foot's passes: from the pose its three joints stand in now, by the same rules
        const j0 = L.clearance ? [L.femur.quaternion.clone(), L.tibia.quaternion.clone(), L.hinge2.quaternion.clone()] : null;
        tarsus2Leg(L, foot, up);
        tarsusFoot(L, th, up, j0 && ((target) => {
            L.femur.quaternion.copy(j0[0]); L.tibia.quaternion.copy(j0[1]); L.hinge2.quaternion.copy(j0[2]);
            L.femur.updateMatrixWorld(true);
            tarsus2Leg(L, target, up);
        }));
    }
    // the two-hinge leg from the femur slot down, solved to an ankle target `foot` (the coxa set; the femur slot, the knee and the
    // second hinge as the frame's solve found them: at their rest)
    function tarsus2Leg(L, foot, up) {
        const { qa } = ops;
        const H = L.h2r;
        h2s.H = H;
        const F = inP(L.femur), qFw = qInP(L.femur);
        const dRaw = h2s.u.copy(foot).sub(F).length();
        h2s.u.divideScalar(dRaw);
        h2s.dRaw = dRaw;
        h2s.kFw.copy(H.kF).applyQuaternion(qFw);
        h2s.qFwT.copy(qFw).multiply(H.qFT);
        let dm = 0;
        h2pose(0, true);
        // each rule's turn scaled by soft2(how far past its edge): held exactly from H2_SOFT past it on, ramped before; by
        // (1 - up): the band and the knee's range are the planted leg's, faded out and back through a swing; and by the plant's
        // walk weight (a standing leg is the bind) (the twin: solve2's ws); the reach is answered whole
        const ws = (1 - up) * (L.w ?? 1);
        if (h2s.fr >= 0 && h2s.e > H.hi) {                                          // rule 1 (a foot out of reach is
            const w = ws * soft2(h2s.e - H.hi);                                     // never answered by a shorter leg)
            if (w > 0) dm = w * toward2(f1hi, 0, H.hi - h2s.e, H.mhi);
        } else if (h2s.e < H.lo) {
            const w = ws * soft2(H.lo - h2s.e);
            if (w > 0) dm = w * toward2(f1lo, 0, h2s.e - H.lo, H.mlo);
        }
        if (dm !== 0) h2pose(dm, true);
        if (h2s.knee < H.klo) {                                                     // rule 2
            const w = ws * soft2(H.klo - h2s.knee);
            if (w > 0) {
                dm = dm + w * (toward2(f2lo, dm, h2s.knee - H.klo, H.mhi) - dm);
                h2pose(dm, true);
            }
        } else if (h2s.knee > H.khi || h2s.fr < 0) {
            const w = h2s.fr < 0 ? 1 : ws * soft2(h2s.knee - H.khi);
            if (w > 0) {
                dm = dm + w * (toward2(f2hi, dm, Math.min(H.khi - h2s.knee, h2s.fr / H.lk), H.mlo) - dm);
                h2pose(dm, true);
            }
        }
        // the bones: the femur slot aimed, the knee and the second hinge turned about their own z, the femur slot's subtree
        // brought up to date ONCE (setWorldQ's own arithmetic, its update moved after the two turns: the same matrices, a
        // subtree update fewer)
        L.femur.quaternion.copy(qInP(L.femur.parent).invert().multiply(h2s.qA.multiply(qFw)));
        L.tibia.quaternion.multiply(qa.setFromAxisAngle(ZAX, h2s.dl));
        L.hinge2.quaternion.multiply(qa.setFromAxisAngle(ZAX, dm));
        L.femur.updateMatrixWorld(true);
        const At = inP(L.tarsus);
        L.err = At.distanceTo(foot);
        const K3 = inP(L.tibia);
        L.knee = F.sub(K3).angleTo(At.sub(K3)) * 180 / Math.PI;
        L.dm = dm * 180 / Math.PI;                               // the second hinge's turn (deg), for gates and probes
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
    return { tarsusInit, tarsus, tarsus2Init, tarsus2, limbInit, limb, tentacleInit, tentacle };
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
    // MOUNT: each slot from its CHAIN RECORD where the glb carries one (kind 'leg', label <fore|mid|hind>_<L|R>: the B10 rig's), its
    // solver by the record (slotAnatomy: a grafted slot steps with its donor's), an arthropod slot's joints by the record
    // (tarsusSlot: the beetle's own records give the B11 names); a glb without records keeps the names. A slot of another anatomy
    // gets its solver's rest data once the solvers exist (below)
    const PAIR_NAME = { f: 'fore', m: 'mid', h: 'hind' };
    const recs = (sp.chains || []).filter((c) => c.kind === 'leg');
    for (const pair of HEX_PAIRS) {
        for (const side of ['L', 'R']) {
            const nm = (j) => `${j}_${pair}_${side}`;
            const rec = recs.find((c) => c.label === `${PAIR_NAME[pair]}_${side}`) || null;
            const js = rec ? (rec.joints || []).map((n) => B(n)).filter(Boolean) : null;
            const anatomy = rec ? slotAnatomy(rec, sp) : 'tarsus';
            const L = !rec ? { pair, side, coxa: B(nm('coxa')), femur: B(nm('femur')), tibia: B(nm('tibia')), tarsus: B(nm('tarsus_1')) }
                : anatomy === 'tarsus' ? { pair, side, ...tarsusSlot(rec, js, bones) } : { pair, side, rec, js };
            if (anatomy === 'tarsus') {
                if (!L.coxa || !L.femur || !L.tibia || !L.tarsus) continue;
                tarsusFrames(L, ops, root0, rootInv0);
            } else if (js.length < 3) continue;
            // the gait's offset (the scheduler's wave rule): hind leads (2 (1 - duty)), then mid (1 - duty), then fore (0); the right
            // side half a cycle on
            L.off = ({ h: 2, m: 1, f: 0 }[pair] * (1 - duty) + (side === 'R' ? 0.5 : 0)) % 1;
            L.range = HEX_COXA_RANGE[pair] * Math.PI / 180;
            L.center = G.center?.[pair] ?? 0.5;
            L.anatomy = anatomy;
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
    // (MOUNT: a slot of another anatomy, a grafted one, gets its own solver's rest data: slotInit)
    for (const L of legs) {
        if (L.anatomy === 'tarsus') solvers.tarsusInit(L);
        else slotInit(solvers, L, L.rec, L.js, { bones, group, G, ops, root0, rootInv0 });
    }
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
            // (MOUNT: each slot's own solver: the tarsus on every beetle leg, a grafted slot its donor's)
            solvers[solverKey(L.anatomy)](L, foot, th, up, body);
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
            target: L.target.clone().applyMatrix4(Pm).toArray(),
            ankle: inP(L.tarsus || L.contact || L.tipNode || L.joints[L.joints.length - 1]).applyMatrix4(Pm).toArray() }));
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
    const legBones = legs.flatMap((L) => (L.anatomy === 'tarsus' ? [L.coxa, L.femur, L.tibia, L.tarsus]
        : L.joints || [L.upper, L.lower, L.ankle]));
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
    // (MOUNT: each slot's solver by its record, slotAnatomy: a grafted slot its DONOR's; its inputs by slotInit, which now also
    // builds an arthropod leg's tarsus inputs: a 'tarsus' slot used to get the limb's and fail in the tarsus solver)
    const legs = sup.map((x) => {
        const c = x.c, js = x.js;
        const anatomy = slotAnatomy(c, sp);
        const L = { name: c.name, label: c.label || c.name, side: c.side || (/_R$/.test(c.name) ? 'R' : 'L'), anatomy, kind: c.kind };
        return slotInit(solvers, L, c, js, { bones, group, G, ops, root0, rootInv0 });
    });
    const fwd = legs.map((L) => L.N.z);
    const ranks = [...new Set(fwd.map((z) => Math.round(z * 1e4)))].sort((a, b) => b - a);
    for (const L of legs) {
        const r = ranks.indexOf(Math.round(L.N.z * 1e4));
        const pairs = Math.max(1, Math.ceil(nLegs / 2));
        const rank = Math.min(pairs - 1, Math.round(r * (pairs - 1) / Math.max(1, ranks.length - 1)));
        L.off = G.phase?.[L.label] ?? ((rank * (1 - G.duty) + (L.side === 'R' ? 0.5 : 0)) % 1);
        L.center = G.center?.[L.label] ?? 0.5;
        // (D4.1b) by label, both opt-in: the WALK's stance place of the slot's foot as [dx, dz] from its rest place (the root's
        // frame, the glb's units: a bind taken from a standing animal plants a leg where a walking one does not), and the slot's
        // own swing lift (the scheduler's footAt reads L.lift). Absent: the rest place and the gait's one lift, as before.
        // (D4.1b fix, the check's F1) the walk place is kept BESIDE the rest place (L.Nw), not added to it: the scheduler plants it
        // only while the body walks; standing, and on the settling step after a stop, the foot stands on its rest place L.N.
        // (D4.1b fix 2) G.liftPlace lifts only the unfolding step out to the walk place at a start (gaitScheduler's swingPath).
        // A slot's own lift is read by the scheduler's lines for a slot with the D4.1b records (footW), so a lift alone makes
        // the slot one (MOUNT's lines, which every other slot runs, know the gait's one lift only)
        const pl = G.place?.[L.label];
        if (pl) { L.Nw = L.N.clone(); L.Nw.x += pl[0]; L.Nw.z += pl[1]; L.walkW = true; }
        if (G.liftBy?.[L.label] != null) { L.lift = G.liftBy[L.label]; L.walkW = true; }
        if (G.liftPlace?.[L.label] != null) L.liftPlace = G.liftPlace[L.label];    // (D4.1b fix) the lift of an unfolding step
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
            solvers[solverKey(L.anatomy)](L, foot, th, up, body);
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
    const legBones = legs.flatMap((L) => L.joints || (L.anatomy === 'tarsus' ? [L.coxa, L.femur, L.tibia, L.tarsus]
        : [L.upper, L.lower, L.ankle]));
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
