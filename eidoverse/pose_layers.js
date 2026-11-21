// pose_layers.js — procedural pose OVERLAYS on top of a playing clip, for
// beats the clip library doesn't cover (kneel-and-place, custom leans).
//
// USAGE (stationary VRM on an idle clip — NOT under a locomotion controller;
// the engine owns vrm.update for controller-driven VRMs its own way):
//     // in setup():
//     const { makeKneelPlace } = await import(new URL('pose_layers.js', EIDOVERSE_DIR).href);
//     await globalThis.playVRMADefault(vrm, 'idle', { loopOnce: false });
//     globalThis._kneel = makeKneelPlace(vrm);
//     // in renderFrame(t), BEFORE renderAsync:
//     const k = globalThis._kneel.cycle(t, { t0: 44.8, inDur: 2.2, hold: 1.4, outDur: 1.8 });
//     globalThis._kneel.apply(k, 1 / FPS);
//
// Guide: tools-guides/characters.md ("Pose overlays: kneel-and-place").
//
// ARCHITECTURE — a keyframed pose track, not a single hand-authored delta.
// The kneel is authored as a sequence of KEY POSES along a path position
// s ∈ [0,1] (foot pickup → ball plant → deep descent → knee touchdown →
// settled genuflect + place-reach). Each key stores ABSOLUTE normalized-local
// bone targets; apply(t01) treats t01 as the path position and evaluates a
// C1 monotone cubic (PCHIP) over each bone's euler components through the
// keys, with the LIVE clip sample as the s=0 knot — so t01=0 is an exact
// restore, idle sway blends out smoothly instead of snapping, and monotone
// key values cannot reverse mid-segment. Sequencing lives in the key SPACING —
// exactly how a clip works — rather than in per-bone phase envelopes.
//
// The key values are DERIVED FROM THE CLIP LIBRARY, not eyeballed: every
// humanoid bone was sampled across stand_to_sit / jump / sitting_on_ground /
// reach on the rig, which fixed the joint conventions (hip flexion = -x on
// upperLeg, knee flexion = +x on lowerLeg, foot +x = plantarflexion, ELBOW
// HINGE = local Y, arm-at-side = upperArm z ≈ ∓65°) and supplied the
// naturally-coordinated fragments (the descent leg is the jump-crouch leg;
// torso fold + balance arms follow stand_to_sit's curve; the reach shape
// comes from the reach clip). The hips translation PER KEY was solved
// numerically against the rendered rig: FK-pin the planted left ankle to
// its standing world position, 1-D secants for contact heights, and a
// skinned-vertex floor check over the whole cycle (shoe and shin meshes,
// not joint centers — a rigid toe box can rotate through the floor while
// every joint clears it).
//
// IF YOU EDIT THE KEYS: keep each joint's value sequence MONOTONE across
// keys (one purposeful reversal max, e.g. the leg extending to plant before
// folding). An early version solved contacts per key independently and got
// every height right while the kneeling hip ran -9°→+18° between two keys —
// in motion that reads as the knee flip-flopping (human-caught). Contact
// heights belong to the DOF that is actually sensitive to them (the knee
// lands via PELVIS drop, i.e. the front knee — not via the kneeling hip).
//
// How it composes: the engine samples the mixer and commits vrm.update AFTER
// each renderFrame (see render_scene.mjs frame loop), so at renderFrame time
// the normalized bones hold the clip's latest sample. apply() writes pose
// targets onto that sample, then commits normalized->raw itself so THIS
// frame's draw shows the pose. Bones the clip does NOT animate are guarded
// against delta accumulation (base pose is captured and restored when the
// mixer hasn't re-sampled a bone between applies).


function smooth(t) { return t * t * (3 - 2 * t); }
const clamp01 = (v) => Math.max(0, Math.min(1, v));
const D2R = Math.PI / 180;
let up2;

// makePoseTrack(vrm, track) — general mechanism.
// track.keys: [{ s, hips: {dx,dy,dz}, bones: { name: {x,y,z} degrees } }]
// sorted by s, absolute normalized-local targets. A bone missing from a
// key holds the live clip sample at that key (target = base).
export function makePoseTrack(vrm, track) {
    const THREE = globalThis.THREE;
    const keys = [...track.keys].sort((a, b) => a.s - b.s);
    const boneNames = [...new Set(keys.flatMap(k => Object.keys(k.bones)))];

    // knot vector: the LIVE BASE is the s=0 knot, then the authored keys.
    // Interpolation is monotone cubic (Fritsch–Carlson / PCHIP) per euler
    // axis — C1 in time and overshoot-free, so a monotone key sequence can
    // NEVER produce a joint that bends past a key and swings back (piecewise
    // slerp had velocity corners at every key; a human eye reads those as
    // the joint flip-flopping even when the key values themselves are clean).
    // evaluate the monotone cubic through knots S / values V at s
    function pchip(S, V, s) {
        const N = S.length;
        if (s <= S[0]) return V[0];
        if (s >= S[N - 1]) return V[N - 1];
        const H = []; for (let i = 0; i < N - 1; i++) H.push(S[i + 1] - S[i]);
        let i = 0;
        while (s > S[i + 1]) i++;
        const d = []; for (let j = 0; j < N - 1; j++) d.push((V[j + 1] - V[j]) / H[j]);
        const m = new Array(N);
        m[0] = d[0]; m[N - 1] = d[N - 2];
        for (let j = 1; j < N - 1; j++) {
            if (d[j - 1] * d[j] <= 0) m[j] = 0;
            else {
                const w1 = 2 * H[j] + H[j - 1], w2 = H[j] + 2 * H[j - 1];
                m[j] = (w1 + w2) / (w1 / d[j - 1] + w2 / d[j]);
            }
        }
        const t = (s - S[i]) / H[i], t2 = t * t, t3 = t2 * t;
        return (2 * t3 - 3 * t2 + 1) * V[i] + (t3 - 2 * t2 + t) * H[i] * m[i]
             + (-2 * t3 + 3 * t2) * V[i + 1] + (t3 - t2) * H[i] * m[i + 1];
    }

    const entries = [];
    for (const name of boneNames) {
        const node = vrm.humanoid?.getNormalizedBoneNode?.(name);
        if (!node) { console.warn('[pose_layers] missing humanoid bone:', name); continue; }
        // PER-BONE knots: a key that omits this bone isn't a knot for it;
        // the live clip sample is every bone's s=0 knot. Past its last
        // knot a bone holds that knot's value. This is what lets the feet
        // and toes carry dense solver micro-keys while the body keeps a
        // handful of pose keys.
        const S = [0], eulKeys = [];
        for (const k of keys) {
            const e = k.bones[name];
            if (!e) continue;
            const v = [(e.x || 0) * D2R, (e.y || 0) * D2R, (e.z || 0) * D2R];
            if (Math.abs(k.s - S[S.length - 1]) < 1e-6) eulKeys[eulKeys.length - 1] = v;   // equal-s: last wins (a zero-width knot would NaN the spline)
            else { S.push(k.s); eulKeys.push(v); }
        }
        entries.push({
            node, S, eulKeys,
            base: new THREE.Quaternion().copy(node.quaternion),
            baseEul: new THREE.Euler(),
            lastWritten: null,
            vals: new Float64Array(S.length),
            outEul: new THREE.Euler(),
        });
    }
    const hips = vrm.humanoid?.getNormalizedBoneNode?.('hips');
    const hipsS = [0], hipsKeys = [];
    for (const k of keys) {
        if (!k.hips) continue;
        if (Math.abs(k.s - hipsS[hipsS.length - 1]) < 1e-6) hipsKeys[hipsKeys.length - 1] = k.hips;
        else { hipsS.push(k.s); hipsKeys.push(k.hips); }
    }
    const hipsState = hips ? { base: hips.position.clone(), cycleBase: null, last: null, vals: new Float64Array(hipsS.length) } : null;
    let lastApplied = 0;

    // ── Springbone double-step guard ────────────────────────────────
    // apply() must call vrm.update itself (the overlay pose has to commit
    // normalized->raw BEFORE this frame's render, and the springbones must
    // step from the OVERLAY pose, not the raw clip pose). But the engine's
    // post-frame loop ALSO calls vrm.update(dt) unconditionally for
    // registered VRMs — springbones then step TWICE per frame at full dt
    // and hair/tie/tail springs run at 2x speed (reads as a super-fast
    // tail wiggle whenever the body moves quickly; same failure mode the
    // engine already guards for controller-owned VRMs). So: apply() arms
    // a flag after its own update, and a wrapper reduces the NEXT outside
    // call to the humanoid commit alone (no spring step, no double dt).
    // ── Spring calm (track.calm) ────────────────────────────────────
    // The tail is a 5-joint spring chain with low drag (0.4) and body
    // colliders; the fast pelvis/leg motion of the rise punts it and the
    // chain thrashes at ~10Hz (human-caught: "super fast wiggling"). While
    // the overlay is active we raise those joints' dragForce toward
    // `drag` (scaled by k, so it ramps in/out with the motion and the
    // authored settings are restored EXACTLY at k=0). Purely a damping
    // change: the tail still sways, it just stops ringing.
    const calmJoints = [];
    for (const spec of (track.calm || [])) {
        const re = new RegExp(spec.match, 'i');
        for (const j of (vrm.springBoneManager?.joints || [])) {
            const nm = j.bone?.name || '';
            if (re.test(nm) && j.settings) {
                calmJoints.push({
                    j, spec,
                    drag0: j.settings.dragForce,
                    gp0: j.settings.gravityPower,
                    gd0: j.settings.gravityDir ? j.settings.gravityDir.clone() : null,
                });
            }
        }
    }

    // ── Planted-foot servo (track.plantLock) ───────────────────────
    // The planted sole must stay ON the floor, but the baked curve was
    // solved against one frame of the base clip while the live clip sways
    // a few millimetres — margins can't exist on a contact. So the foot's
    // pitch is servoed at runtime: persisted correction state, one clamped
    // step per frame toward the baked toe floor height, ramped in with k
    // (exact restore at k→0), reset when the track parks.
    const plant = (() => {
        const pl = track.plantLock;
        if (!pl || !vrm.humanoid?.getRawBoneNode) return null;
        const foot = vrm.humanoid.getNormalizedBoneNode(pl.side + 'Foot');
        const rawFoot = vrm.humanoid.getRawBoneNode(pl.side + 'Foot');
        const rawToes = vrm.humanoid.getRawBoneNode(pl.side + 'Toes');
        if (!foot || !rawFoot || !rawToes) return null;
        // resolve the baked lowest-sole vertex set (mesh name -> indices)
        const vsets = [];
        if (pl.verts && vrm.scene) {
            vrm.scene.traverse((o) => {
                if (o.isSkinnedMesh && pl.verts[o.name]) vsets.push({ mesh: o, idx: pl.verts[o.name] });
            });
        }
        // The baked anchor/floor references are in the BAKE scene's frame
        // (character at the origin on a y=0 floor). Re-capture them against
        // THIS character's standing pose at construction: the pin then holds
        // the foot where THIS scene stands it, wherever the character is
        // placed and whatever its proportions.
        const liveA = new THREE.Vector3(), liveT = new THREE.Vector3();
        rawFoot.getWorldPosition(liveA);
        rawToes.getWorldPosition(liveT);
        const ankleRef = [liveA.x, liveA.y, liveA.z];
        const floorOff = liveT.y - (pl.toeY ?? 0.0226);
        const up = new THREE.Vector3(0, 1, 0);
        const tdir = new THREE.Vector3(), axis = new THREE.Vector3();
        const qw = new THREE.Quaternion(), qp = new THREE.Quaternion(), qc = new THREE.Quaternion();
        const P = { foot, rawFoot, rawToes, ankleRef, toeY: (pl.toeY ?? 0.0226) + floorOff, floorY: (pl.floorY ?? 0.0015) + floorOff, vsets, corr: 0,
                 va: new THREE.Vector3(), vb: new THREE.Vector3() };
        const rotWorld = (ax, ang) => {
            qc.setFromAxisAngle(ax, ang);
            foot.parent.getWorldQuaternion(qw);
            qp.copy(qw).invert();
            foot.quaternion.premultiply(qp.multiply(qc).multiply(qw));
        };
        // both corrections are heading-neutral by construction: pitch about
        // the horizontal axis ⊥ the toe heading, roll about the heading axis.
        P.heading = () => {
            P.rawFoot.getWorldPosition(P.va);
            P.rawToes.getWorldPosition(P.vb);
            tdir.subVectors(P.vb, P.va); tdir.y = 0;
            return tdir.lengthSq() > 1e-8 ? tdir.normalize() : null;
        };
        P.applyCorr = (ang) => {
            const h = P.heading();
            if (!h) return;
            axis.crossVectors(up, h).normalize();
            rotWorld(axis, ang);
        };
        P.applyRoll = (ang) => {
            const h = P.heading();
            if (!h) return;
            rotWorld(h, ang);
        };
        P.side = new THREE.Vector3();
        P.corrRoll = 0;
        return P;
    })();

    const guard = vrm.__poseLayerSpringGuard || (vrm.__poseLayerSpringGuard = (() => {
        const g = { inApply: false, swallowNext: false };
        const orig = vrm.update.bind(vrm);
        vrm.update = function (d) {
            if (!g.inApply && g.swallowNext) {
                g.swallowNext = false;
                if (vrm.humanoid?.update) vrm.humanoid.update();
                return;
            }
            orig(d);
        };
        return g;
    })());

    let parked = false;
    return {
        apply(t01, dt = 1 / (globalThis.FPS || 30)) {
            const k = clamp01(t01);
            // parked (k stayed 0 since the last restore): true no-op — no
            // writes, no vrm.update, no swallow armed, so the engine's own
            // post-frame pass steps the springs exactly once and two tracks
            // can share a VRM as long as one is active at a time.
            if (k === 0 && lastApplied === 0) {
                if (!parked) {
                    parked = true;
                    for (const b of entries) b.lastWritten = null;
                    if (hipsState) { hipsState.last = null; hipsState.cycleBase = null; }
                    if (plant) { plant.corr = 0; plant.corrRoll = 0; }
                }
                return;
            }
            parked = false;
            lastApplied = k;
            for (const b of entries) {
                // accumulation guard: if the mixer did NOT re-sample this
                // bone since our last write, restore the captured base;
                // if it did, the fresh sample becomes the new base.
                if (b.lastWritten && b.node.quaternion.equals(b.lastWritten)) {
                    b.node.quaternion.copy(b.base);
                } else {
                    b.base.copy(b.node.quaternion);
                }
                if (k > 0) {
                    b.baseEul.setFromQuaternion(b.base, 'XYZ');
                    const be = [b.baseEul.x, b.baseEul.y, b.baseEul.z];
                    const out = [0, 0, 0];
                    for (let ax = 0; ax < 3; ax++) {
                        b.vals[0] = be[ax];
                        for (let i = 0; i < b.eulKeys.length; i++)
                            b.vals[i + 1] = b.eulKeys[i][ax];
                        out[ax] = pchip(b.S, b.vals, k);
                    }
                    b.outEul.set(out[0], out[1], out[2], 'XYZ');
                    b.node.quaternion.setFromEuler(b.outEul);
                }
                b.lastWritten = b.lastWritten || new THREE.Quaternion();
                b.lastWritten.copy(b.node.quaternion);
            }
            if (hips && hipsState) {
                if (hipsState.last && hips.position.equals(hipsState.last)) {
                    hips.position.copy(hipsState.base);
                } else {
                    hipsState.base.copy(hips.position);
                }
                if (k > 0) {
                    // the hips deltas were SOLVED against one frame of the base clip;
                    // applying them to the live swaying base would ride every contact
                    // on the idle's ±1–2 cm hip sway. Anchor the base at cycle entry,
                    // blending from live over k∈[0,0.0625] so k→0 still restores exactly.
                    if (!hipsState.cycleBase) hipsState.cycleBase = hipsState.base.clone();
                    const anchorW = Math.min(1, k * 16);
                    for (const [ax, key] of [['x', 'dx'], ['y', 'dy'], ['z', 'dz']]) {
                        hipsState.vals[0] = 0;
                        for (let i = 0; i < hipsKeys.length; i++) hipsState.vals[i + 1] = hipsKeys[i][key] || 0;
                        const live = hips.position[ax];
                        hips.position[ax] = live + (hipsState.cycleBase[ax] - live) * anchorW + pchip(hipsS, hipsState.vals, k);
                    }
                }
                hipsState.last = hipsState.last || hips.position.clone();
                hipsState.last.copy(hips.position);
            }
            if (plant && k > 0) {
                const w = Math.min(1, k * 6);
                // per-frame ankle pin: the live base clip sways the whole
                // leg chain a few millimetres; translate the hips so the
                // planted raw ankle sits exactly at the solved reference
                // (ramped by w so k→0 still restores the live pose exactly).
                if (plant.ankleRef && hips) {
                    if (vrm.humanoid.update) vrm.humanoid.update();
                    vrm.scene?.updateMatrixWorld?.(true);
                    plant.rawFoot.getWorldPosition(plant.va);
                    const aw = plant.ankleRef;
                    hips.position.x += (aw[0] - plant.va.x) * w;
                    hips.position.y += (aw[1] - plant.va.y) * w;
                    hips.position.z += (aw[2] - plant.va.z) * w;
                }
                // sole servo, heading-neutral: pitch about the WORLD
                // horizontal axis perpendicular to the toe heading (a local-X
                // pitch on a yawed foot bleeds into the heading).
                // corrections are LEAKY: they decay every frame and only an
                // active, geometrically-able servo step re-adds — transient
                // where needed, never frozen into later phases of the beat.
                plant.corr *= 0.88; plant.corrRoll *= 0.88;
                if (Math.abs(plant.corr) < 1e-4) plant.corr = 0;
                if (Math.abs(plant.corrRoll) < 1e-4) plant.corrRoll = 0;
                if (plant.corr) plant.applyCorr(plant.corr * w);
                if (plant.corrRoll) plant.applyRoll(plant.corrRoll * w);
                if (vrm.humanoid.update) vrm.humanoid.update();
                vrm.scene?.updateMatrixWorld?.(true);
                plant.rawFoot.getWorldPosition(plant.va);
                plant.rawToes.getWorldPosition(plant.vb);
                let dy;
                if (plant.vsets.length) {
                    let m = Infinity;
                    const mp = plant.vb;
                    for (const { mesh, idx } of plant.vsets) {
                        mesh.skeleton?.update?.();
                        for (const i of idx) {
                            mesh.getVertexPosition(i, plant.va).applyMatrix4(mesh.matrixWorld);
                            if (plant.va.y < m) { m = plant.va.y; mp.copy(plant.va); }
                        }
                    }
                    const h = plant.heading();
                    plant.rawFoot.getWorldPosition(plant.va);
                    dy = m - plant.floorY;
                    if (h) {
                        plant.side.crossVectors(up2 ??= new THREE.Vector3(0, 1, 0), h).normalize();
                        plant.lastH = (plant.lastH || new THREE.Vector3()).copy(h);
                        plant.lastR = (plant.lastR || new THREE.Vector3()).copy(mp).sub(plant.va);
                    } else plant.lastR = null;
                } else {
                    dy = plant.vb.y - plant.toeY;
                }
                const span = Math.max(0.02, Math.abs(plant.vb.z - plant.va.z) + Math.abs(plant.vb.x - plant.va.x));
                // exact small-angle correction: the dug vertex can be the
                // TOE BOX or the HEEL (the dorsiflexed planted foot digs its
                // heel past the pinned ankle), so no sign may be assumed.
                // Least-norm (a, b) over the two heading-neutral axes with
                // the dug vertex's measured Jacobian: Δy = (ω × r)·ŷ.
                if (dy < -0.0005 && plant.lastR) {
                    const r = plant.lastR, h = plant.lastH, sd = plant.side;
                    // (side × r)·ŷ and (h × r)·ŷ
                    const JA = sd.z * r.x - sd.x * r.z;
                    const JB = h.z * r.x - h.x * r.z;
                    const gg = JA * JA + JB * JB;
                    // a point (near-)under the ankle cannot be raised by any
                    // rotation about it — tiny Jacobians only amplify noise
                    // into a random-walk. Act only with real authority.
                    if (gg > 5e-4) {
                        const need = Math.max(-0.01, Math.min(0.01, -dy));
                        let a = need * JA / gg, b = need * JB / gg;
                        a = Math.max(-0.06, Math.min(0.06, a));
                        b = Math.max(-0.06, Math.min(0.06, b));
                        plant.corr = Math.max(-0.35, Math.min(0.35, plant.corr + a * 0.6));
                        plant.corrRoll = Math.max(-0.3, Math.min(0.3, plant.corrRoll + b * 0.6));
                        if (Math.abs(a) > 1e-4) plant.applyCorr(a * 0.6 * w);
                        if (Math.abs(b) > 1e-4) plant.applyRoll(b * 0.6 * w);
                    }
                }
            }
            for (const c of calmJoints) {
                const w = Math.min(1, k * 4);
                const s = c.j.settings, sp = c.spec;
                s.dragForce = c.drag0 + ((sp.drag ?? c.drag0) - c.drag0) * w;
                // gravity steering: blend the chain's gravity toward the
                // spec direction/power — a wind-like pull that drifts the
                // whole chain aside (out of the stepping leg's collider
                // sweep) without fighting the spring solver.
                if (sp.gravityDir && c.gd0) {
                    s.gravityPower = c.gp0 + ((sp.gravityPower ?? c.gp0) - c.gp0) * w;
                    s.gravityDir.set(
                        c.gd0.x + (sp.gravityDir[0] - c.gd0.x) * w,
                        c.gd0.y + (sp.gravityDir[1] - c.gd0.y) * w,
                        c.gd0.z + (sp.gravityDir[2] - c.gd0.z) * w,
                    ).normalize();
                }
            }
            // commit normalized -> raw for THIS frame's draw (real update:
            // springbones step once, from the overlay pose), then arm the
            // guard so the engine's post-frame duplicate only re-commits.
            if (typeof vrm.update === 'function') {
                guard.inApply = true;
                vrm.update(dt);
                guard.inApply = false;
                guard.swallowNext = true;
            }
        },
        // eased 0->1->0 envelope for a timed beat
        cycle(t, { t0 = 0, inDur = 2.2, hold = 1.2, outDur = 1.8 } = {}) {
            const u = t - t0;
            if (u <= 0 || u >= inDur + hold + outDur) return 0;
            if (u < inDur) return smooth(u / inDur);
            if (u < inDur + hold) return 1;
            return smooth(1 - (u - inDur - hold) / outDur);
        },
        get value() { return lastApplied; },
    };
}

// Right-knee genuflect with a right-hand place/pick reach to the ground,
// left forearm resting on the left thigh. Left foot planted throughout
// (hips deltas solved by FK ankle-pinning); right foot steps back onto
// the ball, rolls over the toes as the knee lands, then lays flat
// (instep down). Values in degrees, normalized rig, +Z facing.
export const KNEEL_PLACE_TRACK = {
    anchor: { bone: 'leftFoot', ankleWorld: [0.1958, 0.055, 0.1041] },
    plantLock: { side: 'left', toeY: 0.0226, floorY: 0.0015, verts: {"shoes":[279,1232,424,83,1233,180,82,1193,252,1197,225,179,414,226,74,537]} },
    keys: [
        { s: 0.05, name: 'peel',
          hips: { dx: 0.0402, dy: 0.0001, dz: 0.0346 },
          bones: {
            hips: { x: 1 },
            spine: { x: 3 },
            chest: { x: 2 },
            neck: {},
            head: { x: -1 },
            leftUpperLeg: { x: -15.4, y: 17.3, z: 4.5 },
            leftLowerLeg: { x: 14 },
            leftFoot: { x: -3 },
            leftToes: { x: -4 },
            rightUpperLeg: { x: 8 },
            rightLowerLeg: { x: 16 },
            rightFoot: { x: -4 },
            rightToes: { x: -15.2 },
            leftUpperArm: { x: 2, y: -22, z: -64 },
            leftLowerArm: { y: -14 },
            rightUpperArm: { x: 8, y: 24, z: 58 },
            rightLowerArm: { y: 14 },
          } },
        { s: 0.14, name: 'pickup',
          hips: { dx: 0.0552, dy: -0.0008, dz: 0.0496 },
          bones: {
            hips: { x: 2 },
            spine: { x: 6 },
            chest: { x: 4 },
            neck: {},
            head: { x: -3 },
            leftUpperLeg: { x: -16, y: 17.6, z: 3.7 },
            leftLowerLeg: { x: 16 },
            leftFoot: { x: -3 },
            leftToes: { x: -4 },
            rightUpperLeg: { x: 10 },
            rightLowerLeg: { x: 42 },
            rightFoot: {},
            rightToes: { x: -28 },
            leftUpperArm: { x: 2, y: -22, z: -64 },
            leftLowerArm: { y: -14 },
            rightUpperArm: { x: 8, y: 24, z: 58 },
            rightLowerArm: { y: 14 },
          } },
        { s: 0.3, name: 'shift',
          hips: { dx: 0.0599, dy: -0.062, dz: 0.0196 },
          bones: {
            hips: { x: 3 },
            spine: { x: 12 },
            chest: { x: 8 },
            neck: { x: -1 },
            head: { x: -7 },
            leftUpperLeg: { x: -35.9, y: 16.5, z: 8.3 },
            leftLowerLeg: { x: 46 },
            leftFoot: { x: -14.6 },
            leftToes: { x: -4 },
            rightUpperLeg: { x: 14 },
            rightLowerLeg: { x: 36 },
            rightFoot: { x: 30 },
            rightToes: { x: -36.5 },
            leftUpperArm: { x: -4, y: -26, z: -58 },
            leftLowerArm: { y: -30 },
            rightUpperArm: { x: -2, y: 22, z: 50 },
            rightLowerArm: { y: 26 },
          } },
        { s: 0.46, name: 'lower',
          hips: { dx: 0.056, dy: -0.123, dz: -0.0202 },
          bones: {
            hips: { x: 3.5 },
            spine: { x: 15 },
            chest: { x: 11 },
            neck: { x: -3 },
            head: { x: -12 },
            leftUpperLeg: { x: -50.5, y: 18.5, z: 13.8 },
            leftLowerLeg: { x: 63, y: -4 },
            leftFoot: { x: -19.7 },
            leftToes: { x: -4 },
            rightUpperLeg: { x: 8 },
            rightLowerLeg: { x: 48 },
            rightFoot: { x: 36 },
            rightToes: { x: -94.2 },
            leftUpperArm: { x: -9, y: -26, z: -52 },
            leftLowerArm: { y: -39 },
            rightUpperArm: { x: -9, y: 21, z: 42 },
            rightLowerArm: { y: 32 },
          } },
        { s: 0.54, name: 'sweep',
          hips: { dx: 0.05, dy: -0.206, dz: -0.0351 },
          bones: {
            hips: { x: 3.7 },
            spine: { x: 16.5 },
            chest: { x: 12.5 },
            neck: { x: -4 },
            head: { x: -15 },
            leftUpperLeg: { x: -64.3, y: 16.8, z: 18.8 },
            leftLowerLeg: { x: 82, y: -5.5 },
            leftFoot: { x: -27.8 },
            leftToes: { x: -3.6 },
            rightUpperLeg: { x: 5 },
            rightLowerLeg: { x: 59 },
            rightFoot: { x: 63 },
            rightToes: { x: 24 },
            leftUpperArm: { x: -11.5, y: -26, z: -49 },
            leftLowerArm: { y: -43.5 },
            rightUpperArm: { x: -12.5, y: 20.5, z: 38 },
            rightLowerArm: { y: 35 },
          } },
        { s: 0.62, name: 'deep',
          hips: { dx: 0.045, dy: -0.3018, dz: -0.0499 },
          bones: {
            hips: { x: 4 },
            spine: { x: 18 },
            chest: { x: 14 },
            neck: { x: -5 },
            head: { x: -18 },
            leftUpperLeg: { x: -78.9, y: 14.1, z: 23.5 },
            leftLowerLeg: { x: 100, y: -7 },
            leftFoot: { x: -33.1 },
            leftToes: { x: -4 },
            rightUpperLeg: { x: 2 },
            rightLowerLeg: { x: 70 },
            rightFoot: { x: 75 },
            rightToes: { x: -5.8 },
            leftUpperArm: { x: -14, y: -26, z: -46 },
            leftLowerArm: { y: -48 },
            rightUpperArm: { x: -16, y: 20, z: 34 },
            rightLowerArm: { y: 38 },
          } },
        { s: 0.82, name: 'touchdown',
          hips: { dx: 0.0302, dy: -0.3728, dz: -0.0877 },
          bones: {
            hips: { y: -3 },
            spine: { x: 17 },
            chest: { x: 13 },
            neck: { x: -5 },
            head: { x: -16 },
            leftUpperLeg: { x: -87, y: 9, z: 26.9 },
            leftLowerLeg: { x: 110.1, y: -5 },
            leftFoot: { x: -28.1 },
            leftToes: { x: -4 },
            rightUpperLeg: { x: 4 },
            rightLowerLeg: { x: 80 },
            rightFoot: { x: 58 },
            rightToes: { x: 70 },
            leftUpperArm: { x: -10, y: -18, z: -50 },
            leftLowerArm: { y: -58 },
            rightShoulder: { x: -4, z: 12 },
            rightUpperArm: { x: -25, y: 38, z: 55 },
            rightLowerArm: { y: 22 },
          } },
        { s: 1, name: 'settle',
          hips: { dx: 0.0099, dy: -0.4076, dz: -0.1331 },
          bones: {
            hips: { x: -4, y: -6 },
            spine: { x: 23, y: -4 },
            chest: { x: 19, y: -6, z: -8 },
            neck: { x: -8, z: 4 },
            head: { x: -23, y: 5, z: 4 },
            leftUpperLeg: { x: -90.6, y: 4.9, z: 29.7 },
            leftLowerLeg: { x: 111.9, y: -5 },
            leftFoot: { x: -26.1 },
            leftToes: { x: -4 },
            rightUpperLeg: { x: 6 },
            rightLowerLeg: { x: 88 },
            rightFoot: { x: 60 },
            rightToes: { x: 2.6 },
            leftUpperArm: { x: -14, y: -12, z: -48 },
            leftLowerArm: { y: -70 },
            leftHand: { x: -12 },
            rightShoulder: { x: -8, z: 26 },
            rightUpperArm: { x: -30, y: 59, z: 70 },
            rightLowerArm: { y: 6 },
            rightHand: { x: -20 },
          } },
        { s: 0.015, hips: { dx: 0.0135, dy: 0.0008, dz: 0.0171 }, bones: { rightFoot: { x: -12.8 }, rightToes: { x: -36.7 } } },
        { s: 0.025, hips: { dx: -0.0127, dy: -0.0015, dz: 0.0304 }, bones: { rightFoot: { x: -13.1 }, rightToes: { x: -44.4 } } },
        { s: 0.035, hips: { dx: -0.0337, dy: -0.004, dz: 0.0431 }, bones: { rightFoot: { x: -9.5 }, rightToes: { x: -46.9 } } },
        { s: 0.045, hips: { dx: -0.0443, dy: -0.0055, dz: 0.0523 }, bones: { rightFoot: { x: -9.2 }, rightToes: { x: -49.2 } } },
        { s: 0.055, hips: { dx: -0.0315, dy: -0.0041, dz: 0.0502 }, bones: { rightFoot: { x: -8.8 }, rightToes: { x: -21.1 } } },
        { s: 0.065, hips: { dx: -0.0328, dy: -0.0041, dz: 0.0538 }, bones: { rightFoot: { x: -8.5 }, rightToes: { x: -21.1 } } },
        { s: 0.075, hips: { dx: -0.0256, dy: -0.0034, dz: 0.0536 }, bones: { rightFoot: { x: -8.1 }, rightToes: { x: -21.1 } } },
        { s: 0.085, hips: { dx: -0.0238, dy: -0.0033, dz: 0.0553 }, bones: { rightFoot: { x: -7.7 }, rightToes: { x: -21.1 } } },
        { s: 0.095, hips: { dx: -0.0221, dy: -0.0033, dz: 0.0571 }, bones: { rightFoot: { x: -7.4 }, rightToes: { x: -21.1 } } },
        { s: 0.105, hips: { dx: -0.0206, dy: -0.0033, dz: 0.0592 }, bones: { rightFoot: { x: -6.9 }, rightToes: { x: -21.1 }, leftUpperLeg: { x: -15.7, y: 14.2, z: 8.9 }, leftFoot: { x: 4 }, leftToes: { x: -39 } } },
        { s: 0.115, hips: { dx: -0.0193, dy: -0.0034, dz: 0.0613 }, bones: { rightFoot: { x: -6.5 }, rightToes: { x: -21.1 }, leftUpperLeg: { x: -15.8, y: 14.2, z: 8.8 }, leftFoot: { x: 4 }, leftToes: { x: -39 } } },
        { s: 0.125, hips: { dx: -0.0182, dy: -0.0035, dz: 0.0634 }, bones: { rightFoot: { x: -5.9 }, rightToes: { x: -21.6 }, leftUpperLeg: { x: -15.9, y: 14.2, z: 8.8 }, leftFoot: { x: 4 }, leftToes: { x: -39 } } },
        { s: 0.135, hips: { dx: -0.0172, dy: -0.0037, dz: 0.0654 }, bones: { rightFoot: { x: -5.3 }, rightToes: { x: -22.6 }, leftUpperLeg: { x: -16, y: 14.2, z: 8.7 }, leftFoot: { x: 4 }, leftToes: { x: -39 } } },
        { s: 0.145, hips: { dx: -0.0164, dy: -0.0041, dz: 0.0672 }, bones: { rightFoot: { x: -4.6 }, rightToes: { x: -23.4 }, leftUpperLeg: { x: -16.1, y: 14.2, z: 8.7 }, leftFoot: { x: 4 }, leftToes: { x: -39 } } },
        { s: 0.155, hips: { dx: -0.0149, dy: -0.0048, dz: 0.068 }, bones: { rightFoot: { x: -3.5 }, rightToes: { x: -24.1 }, leftUpperLeg: { x: -16.6, y: 14.2, z: 8.7 }, leftFoot: { x: -8.2 }, leftToes: { x: 11 } } },
        { s: 0.165, hips: { dx: -0.0153, dy: -0.0061, dz: 0.071 }, bones: { rightFoot: { x: -2 }, rightToes: { x: -24.7 }, leftUpperLeg: { x: -17.2, y: 15.3, z: 9.2 }, leftFoot: { x: -5.8 }, leftToes: { x: 2.2 } } },
        { s: 0.175, hips: { dx: -0.0108, dy: -0.0076, dz: 0.0695 }, bones: { rightFoot: { x: -0.2 }, rightToes: { x: -25.2 }, leftUpperLeg: { x: -18.1, y: 15.3, z: 9.1 }, leftFoot: { x: -3.8 }, leftToes: { x: -9 } } },
        { s: 0.185, hips: { dx: -0.007, dy: -0.0097, dz: 0.0676 }, bones: { rightFoot: { x: 1.8 }, rightToes: { x: -25.7 }, leftUpperLeg: { x: -19.2, y: 15.3, z: 9.1 }, leftFoot: { x: -1.8 }, leftToes: { x: -39 } } },
        { s: 0.195, hips: { dx: -0.0028, dy: -0.0124, dz: 0.0651 }, bones: { rightFoot: { x: 4 }, rightToes: { x: -26.1 }, leftUpperLeg: { x: -20.5, y: 15.3, z: 9.1 }, leftFoot: { x: 0.2 }, leftToes: { x: -39 } } },
        { s: 0.205, hips: { dx: 0.0054, dy: -0.0154, dz: 0.0596 }, bones: { rightFoot: { x: 6.4 }, rightToes: { x: -26.5 }, leftUpperLeg: { x: -21.9, y: 14.6, z: 8.6 }, leftFoot: { x: -11.4 }, leftToes: { x: 11 } } },
        { s: 0.215, hips: { dx: 0.01, dy: -0.0192, dz: 0.0561 }, bones: { rightFoot: { x: 8.9 }, rightToes: { x: -26.8 }, leftUpperLeg: { x: -23.3, y: 14.6, z: 8.6 }, leftFoot: { x: -9 }, leftToes: { x: 3.1 } } },
        { s: 0.225, hips: { dx: 0.0149, dy: -0.0235, dz: 0.0522 }, bones: { rightFoot: { x: 11.4 }, rightToes: { x: -27.2 }, leftUpperLeg: { x: -24.9, y: 14.6, z: 8.6 }, leftFoot: { x: -6.8 }, leftToes: { x: -29 } } },
        { s: 0.235, hips: { dx: 0.0198, dy: -0.0283, dz: 0.048 }, bones: { rightFoot: { x: 13.8 }, rightToes: { x: -27.6 }, leftUpperLeg: { x: -26.5, y: 14.6, z: 8.6 }, leftFoot: { x: -6.7 }, leftToes: { x: -39 } } },
        { s: 0.245, hips: { dx: 0.0247, dy: -0.0334, dz: 0.0437 }, bones: { rightFoot: { x: 16.2 }, rightToes: { x: -28 }, leftUpperLeg: { x: -28.1, y: 14.6, z: 8.6 }, leftFoot: { x: -3.9 }, leftToes: { x: -39 } } },
        { s: 0.255, hips: { dx: 0.0294, dy: -0.0388, dz: 0.0393 }, bones: { rightFoot: { x: 18.4 }, rightToes: { x: -28.4 }, leftUpperLeg: { x: -29.7, y: 14.6, z: 8.6 }, leftFoot: { x: -15.7 }, leftToes: { x: 11 } } },
        { s: 0.265, hips: { dx: 0.0313, dy: -0.0443, dz: 0.037 }, bones: { rightFoot: { x: 20.4 }, rightToes: { x: -29 }, leftUpperLeg: { x: -31.3, y: 15.3, z: 9.2 }, leftFoot: { x: -14.1 }, leftToes: { x: 1 } } },
        { s: 0.275, hips: { dx: 0.0357, dy: -0.0497, dz: 0.0326 }, bones: { rightFoot: { x: 22.1 }, rightToes: { x: -29.6 }, leftUpperLeg: { x: -32.8, y: 15.3, z: 9.2 }, leftFoot: { x: -11.7 }, leftToes: { x: -19 } } },
        { s: 0.285, hips: { dx: 0.0396, dy: -0.0549, dz: 0.0284 }, bones: { rightFoot: { x: 23.6 }, rightToes: { x: -36.3 }, leftUpperLeg: { x: -34.1, y: 15.3, z: 9.2 }, leftFoot: { x: -9.7 }, leftToes: { x: -19 } } },
        { s: 0.295, hips: { dx: 0.0429, dy: -0.0597, dz: 0.0244 }, bones: { rightFoot: { x: 24.6 }, rightToes: { x: -42.3 }, leftUpperLeg: { x: -35.4, y: 15.3, z: 9.2 }, leftFoot: { x: -7.7 }, leftToes: { x: -29 } } },
        { s: 0.305, hips: { dx: 0.0457, dy: -0.0639, dz: 0.0206 }, bones: { rightFoot: { x: 25.3 }, rightToes: { x: -48.1 }, leftUpperLeg: { x: -36.4, y: 15.3, z: 9.2 }, leftFoot: { x: -19.8 }, leftToes: { x: 11 } } },
        { s: 0.315, hips: { dx: 0.0482, dy: -0.0678, dz: 0.0169 }, bones: { rightFoot: { x: 25.8 }, rightToes: { x: -52.7 }, leftUpperLeg: { x: -37.4, y: 15.3, z: 9.2 }, leftFoot: { x: -17.4 }, leftToes: { x: 2.1 } } },
        { s: 0.325, hips: { dx: 0.0504, dy: -0.0714, dz: 0.0134 }, bones: { rightFoot: { x: 26.3 }, rightToes: { x: -56.5 }, leftUpperLeg: { x: -38.3, y: 15.3, z: 9.2 }, leftFoot: { x: -15.4 }, leftToes: { x: -7.2 } } },
        { s: 0.335, hips: { dx: 0.0488, dy: -0.0747, dz: 0.0122 }, bones: { rightFoot: { x: 26.6 }, rightToes: { x: -59.2 }, leftUpperLeg: { x: -39.2, y: 15.9, z: 9.8 }, leftFoot: { x: -13.4 }, leftToes: { x: 2.8 } } },
        { s: 0.345, hips: { dx: 0.0507, dy: -0.0781, dz: 0.0087 }, bones: { rightFoot: { x: 26.9 }, rightToes: { x: -60.8 }, leftUpperLeg: { x: -40, y: 15.9, z: 9.8 }, leftFoot: { x: -11.4 }, leftToes: { x: -9 } } },
        { s: 0.355, hips: { dx: 0.0525, dy: -0.0813, dz: 0.0053 }, bones: { rightFoot: { x: 27.2 }, rightToes: { x: -70.8 }, leftUpperLeg: { x: -40.8, y: 15.9, z: 9.8 }, leftFoot: { x: -21.4 }, leftToes: { x: 11 } } },
        { s: 0.365, hips: { dx: 0.0517, dy: -0.0843, dz: 0.004 }, bones: { rightFoot: { x: 27.4 }, rightToes: { x: -72.5 }, leftUpperLeg: { x: -41.6, y: 16.5, z: 10.5 }, leftFoot: { x: -19.4 }, leftToes: { x: 1 } } },
        { s: 0.375, hips: { dx: 0.0534, dy: -0.0875, dz: 0.0005 }, bones: { rightFoot: { x: 27.7 }, rightToes: { x: -74.5 }, leftUpperLeg: { x: -42.4, y: 16.5, z: 10.5 }, leftFoot: { x: -17.4 }, leftToes: { x: 1 } } },
        { s: 0.385, hips: { dx: 0.0515, dy: -0.0905, dz: -0.0005 }, bones: { rightFoot: { x: 27.9 }, rightToes: { x: -74.5 }, leftUpperLeg: { x: -43.2, y: 17, z: 11.2 }, leftFoot: { x: -15.4 }, leftToes: { x: -9 } } },
        { s: 0.395, hips: { dx: 0.0534, dy: -0.094, dz: -0.0041 }, bones: { rightFoot: { x: 28.1 }, rightToes: { x: -77.7 }, leftUpperLeg: { x: -44, y: 17, z: 11.2 }, leftFoot: { x: -13.4 }, leftToes: { x: -19 } } },
        { s: 0.405, hips: { dx: 0.0503, dy: -0.0972, dz: -0.0045 }, bones: { rightFoot: { x: 28.4 }, rightToes: { x: -77.7 }, leftUpperLeg: { x: -44.9, y: 17.6, z: 12.1 }, leftFoot: { x: -11.4 }, leftToes: { x: -19 } } },
        { s: 0.415, hips: { dx: 0.0524, dy: -0.1011, dz: -0.0083 }, bones: { rightFoot: { x: 28.7 }, rightToes: { x: -78.9 }, leftUpperLeg: { x: -45.8, y: 17.6, z: 12.1 }, leftFoot: { x: -23 }, leftToes: { x: 11 } } },
        { s: 0.425, hips: { dx: 0.0547, dy: -0.1053, dz: -0.0121 }, bones: { rightFoot: { x: 29.1 }, rightToes: { x: -82.7 }, leftUpperLeg: { x: -46.7, y: 17.6, z: 12.1 }, leftFoot: { x: -21 }, leftToes: { x: 11 } } },
        { s: 0.435, hips: { dx: 0.0537, dy: -0.1095, dz: -0.0132 }, bones: { rightFoot: { x: 29.5 }, rightToes: { x: -85.7 }, leftUpperLeg: { x: -47.7, y: 18.2, z: 12.9 }, leftFoot: { x: -19 }, leftToes: { x: 1 } } },
        { s: 0.445, hips: { dx: 0.0565, dy: -0.1147, dz: -0.0172 }, bones: { rightFoot: { x: 30 }, rightToes: { x: -87.9 }, leftUpperLeg: { x: -48.7, y: 18.2, z: 12.9 }, leftFoot: { x: -17 }, leftToes: { x: -9 } } },
        { s: 0.455, hips: { dx: 0.0545, dy: -0.1198, dz: -0.0176 }, bones: { rightFoot: { x: 30.6 }, rightToes: { x: -92.7 }, leftUpperLeg: { x: -49.9, y: 18.7, z: 13.9 }, leftFoot: { x: -15 }, leftToes: { x: -19 } } },
        { s: 0.465, hips: { dx: 0.0581, dy: -0.1264, dz: -0.0219 }, bones: { rightFoot: { x: 31.6 }, rightToes: { x: -97.5 }, leftUpperLeg: { x: -51.1, y: 18.7, z: 13.9 }, leftFoot: { x: -25 }, leftToes: { x: 11 } } },
        { s: 0.475, hips: { dx: 0.0625, dy: -0.1345, dz: -0.026 }, bones: { rightFoot: { x: 33.8 }, rightToes: { x: -104.1 }, leftUpperLeg: { x: -52.6, y: 18.7, z: 13.9 }, leftFoot: { x: -23 }, leftToes: { x: 1 } } },
        { s: 0.485, hips: { dx: 0.0641, dy: -0.1435, dz: -0.0272 }, bones: { rightFoot: { x: 37 }, rightToes: { x: -101.8 }, leftUpperLeg: { x: -54.2, y: 19.1, z: 14.7 }, leftFoot: { x: -21 }, leftToes: { x: -9 } } },
        { s: 0.495, hips: { dx: 0.0663, dy: -0.1538, dz: -0.0286 }, bones: { rightFoot: { x: 76.8 }, rightToes: { x: -81.1 }, leftUpperLeg: { x: -56, y: 19.5, z: 15.5 }, leftFoot: { x: -19 }, leftToes: { x: -18.9 } } },
        { s: 0.505, hips: { dx: 0.0679, dy: -0.1648, dz: -0.0296 }, bones: { rightFoot: { x: 55.4 }, rightToes: { x: 30.3 }, leftUpperLeg: { x: -57.8, y: 19.8, z: 16.3 }, leftFoot: { x: -17.1 }, leftToes: { x: -18.8 } } },
        { s: 0.515, hips: { dx: 0.074, dy: -0.1772, dz: -0.0334 }, bones: { rightFoot: { x: 55.4 }, rightToes: { x: 33.5 }, leftUpperLeg: { x: -59.7, y: 19.8, z: 16.3 }, leftFoot: { x: -18.2 }, leftToes: { x: -18.7 } } },
        { s: 0.525, hips: { dx: 0.0745, dy: -0.1889, dz: -0.0336 }, bones: { rightFoot: { x: 55.4 }, rightToes: { x: 36.1 }, leftUpperLeg: { x: -61.6, y: 20.1, z: 17.4 }, leftFoot: { x: -19.4 }, leftToes: { x: -18.7 } } },
        { s: 0.535, hips: { dx: 0.0801, dy: -0.2013, dz: -0.0374 }, bones: { rightFoot: { x: 56.8 }, rightToes: { x: 35 }, leftUpperLeg: { x: -63.4, y: 20.1, z: 17.4 }, leftFoot: { x: -20.3 }, leftToes: { x: -18.7 } } },
        { s: 0.545, hips: { dx: 0.0797, dy: -0.2125, dz: -0.0376 }, bones: { rightFoot: { x: 59 }, rightToes: { x: 28.7 }, leftUpperLeg: { x: -65.2, y: 20.3, z: 18.6 }, leftFoot: { x: -21.2 }, leftToes: { x: -18.7 } } },
        { s: 0.555, hips: { dx: 0.0851, dy: -0.226, dz: -0.042 }, bones: { rightFoot: { x: 61.2 }, rightToes: { x: 30.5 }, leftUpperLeg: { x: -67.2, y: 20.3, z: 18.6 }, leftFoot: { x: -22 }, leftToes: { x: -18.7 } } },
        { s: 0.565, hips: { dx: 0.0838, dy: -0.2392, dz: -0.0422 }, bones: { rightFoot: { x: 63.2 }, rightToes: { x: 28 }, leftUpperLeg: { x: -69.4, y: 20.5, z: 20.1 }, leftFoot: { x: -22.9 }, leftToes: { x: -18.7 } } },
        { s: 0.575, hips: { dx: 0.0858, dy: -0.2534, dz: -0.0443 }, bones: { rightFoot: { x: 65.2 }, rightToes: { x: 26 }, leftUpperLeg: { x: -71.6, y: 20.6, z: 20.9 }, leftFoot: { x: -23.8 }, leftToes: { x: -18.8 } } },
        { s: 0.585, hips: { dx: 0.0848, dy: -0.2671, dz: -0.0459 }, bones: { rightFoot: { x: 66.9 }, rightToes: { x: 37.8 }, leftUpperLeg: { x: -73.7, y: 20.3, z: 21.8 }, leftFoot: { x: -34 }, leftToes: { x: 11.1 } } },
        { s: 0.595, hips: { dx: 0.0896, dy: -0.2812, dz: -0.0513 }, bones: { rightFoot: { x: 68.3 }, rightToes: { x: 48.1 }, leftUpperLeg: { x: -75.6, y: 19.8, z: 20.9 }, leftFoot: { x: -34 }, leftToes: { x: 11.1 } } },
        { s: 0.605, hips: { dx: 0.0917, dy: -0.2927, dz: -0.0536 }, bones: { rightFoot: { x: 69.4 }, rightToes: { x: 53.1 }, leftUpperLeg: { x: -77.2, y: 19.5, z: 20.9 }, leftFoot: { x: -34 }, leftToes: { x: 11 } } },
        { s: 0.615, hips: { dx: 0.0874, dy: -0.3003, dz: -0.0524 }, bones: { rightFoot: { x: 69.9 }, rightToes: { x: 37.1 }, leftUpperLeg: { x: -78.4, y: 19.3, z: 22.1 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.625, hips: { dx: 0.0863, dy: -0.3059, dz: -0.0534 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 35 }, leftUpperLeg: { x: -79.2, y: 18.9, z: 22.1 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.635, hips: { dx: 0.0859, dy: -0.311, dz: -0.0545 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 20.2 }, leftUpperLeg: { x: -79.9, y: 18.6, z: 22.1 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.645, hips: { dx: 0.0825, dy: -0.3152, dz: -0.054 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 15.3 }, leftUpperLeg: { x: -80.5, y: 18.4, z: 22.9 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.655, hips: { dx: 0.082, dy: -0.3199, dz: -0.0554 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 13.7 }, leftUpperLeg: { x: -81.1, y: 18, z: 22.9 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.665, hips: { dx: 0.0818, dy: -0.3244, dz: -0.0569 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 13 }, leftUpperLeg: { x: -81.7, y: 17.8, z: 22.9 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.675, hips: { dx: 0.0817, dy: -0.3288, dz: -0.0585 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 13 }, leftUpperLeg: { x: -82.2, y: 17.5, z: 22.9 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.685, hips: { dx: 0.0781, dy: -0.3322, dz: -0.0586 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 13 }, leftUpperLeg: { x: -82.7, y: 17.2, z: 23.8 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.695, hips: { dx: 0.078, dy: -0.3362, dz: -0.0604 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 13.2 }, leftUpperLeg: { x: -83.1, y: 17, z: 23.8 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.705, hips: { dx: 0.0779, dy: -0.3401, dz: -0.0624 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 18.6 }, leftUpperLeg: { x: -83.5, y: 16.7, z: 23.8 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.715, hips: { dx: 0.0778, dy: -0.3438, dz: -0.0645 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 24.3 }, leftUpperLeg: { x: -83.9, y: 16.5, z: 23.8 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.725, hips: { dx: 0.0776, dy: -0.3473, dz: -0.0667 }, bones: { rightFoot: { x: 70 }, rightToes: { x: 49.9 }, leftUpperLeg: { x: -84.3, y: 16.2, z: 23.8 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.735, hips: { dx: 0.0737, dy: -0.3499, dz: -0.0673 }, bones: { rightFoot: { x: 69.6 }, rightToes: { x: 65.6 }, leftUpperLeg: { x: -84.6, y: 15.9, z: 24.8 }, leftFoot: { x: -34 }, leftToes: { x: 1 } } },
        { s: 0.745, hips: { dx: 0.0739, dy: -0.3531, dz: -0.0697 }, bones: { rightFoot: { x: 76.8 }, rightToes: { x: 71 }, leftUpperLeg: { x: -84.9, y: 15.8, z: 24.8 }, leftFoot: { x: -34 }, leftToes: { x: 11 } } },
        { s: 0.755, hips: { dx: 0.0737, dy: -0.3561, dz: -0.0721 }, bones: { rightFoot: { x: 77.2 }, rightToes: { x: 76.2 }, leftUpperLeg: { x: -85.2, y: 15.5, z: 24.8 }, leftFoot: { x: -34 }, leftToes: { x: 11 } } },
        { s: 0.765, hips: { dx: 0.0734, dy: -0.359, dz: -0.0746 }, bones: { rightFoot: { x: 79.2 }, rightToes: { x: 81 }, leftUpperLeg: { x: -85.5, y: 15.3, z: 24.8 }, leftFoot: { x: -34 }, leftToes: { x: 11 } } },
        { s: 0.775, hips: { dx: 0.073, dy: -0.3617, dz: -0.0772 }, bones: { rightFoot: { x: 80.3 }, rightToes: { x: 85.2 }, leftUpperLeg: { x: -85.8, y: 15, z: 24.8 }, leftFoot: { x: -34 }, leftToes: { x: 11 } } },
        { s: 0.785, hips: { dx: 0.0689, dy: -0.3636, dz: -0.0783 }, bones: { rightFoot: { x: 64.4 }, rightToes: { x: 88.8 }, leftUpperLeg: { x: -86.1, y: 14.7, z: 25.7 }, leftFoot: { x: -34 }, leftToes: { x: 11 } } },
        { s: 0.795, hips: { dx: 0.069, dy: -0.3661, dz: -0.0809 }, bones: { rightFoot: { x: 63.7 }, rightToes: { x: 91.7 }, leftUpperLeg: { x: -86.3, y: 14.6, z: 25.7 }, leftFoot: { x: -34 }, leftToes: { x: 11 } } },
        { s: 0.805, hips: { dx: 0.0685, dy: -0.3685, dz: -0.0836 }, bones: { rightFoot: { x: 71.3 }, rightToes: { x: 93.8 }, leftUpperLeg: { x: -86.6, y: 14.3, z: 25.7 }, leftFoot: { x: -30 }, leftToes: { x: 1 } } },
        { s: 0.815, hips: { dx: 0.0615, dy: -0.3697, dz: -0.0842 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 94.9 }, leftUpperLeg: { x: -86.9, y: 13.9, z: 27.1 }, leftFoot: { x: -28 }, leftToes: { x: -9 } } },
        { s: 0.825, hips: { dx: 0.0624, dy: -0.3717, dz: -0.0868 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 94.9 }, leftUpperLeg: { x: -87.1, y: 13.9, z: 27.1 }, leftFoot: { x: -26 }, leftToes: { x: -19 } } },
        { s: 0.835, hips: { dx: 0.0555, dy: -0.3729, dz: -0.0876 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 74.1 }, leftUpperLeg: { x: -87.4, y: 13.3, z: 28.4 }, leftFoot: { x: -24 }, leftToes: { x: -19 } } },
        { s: 0.845, hips: { dx: 0.0564, dy: -0.3749, dz: -0.0903 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 72.6 }, leftUpperLeg: { x: -87.6, y: 13.3, z: 28.4 }, leftFoot: { x: -34 }, leftToes: { x: 11 } } },
        { s: 0.855, hips: { dx: 0.0605, dy: -0.3775, dz: -0.0946 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 70.4 }, leftUpperLeg: { x: -87.8, y: 13.3, z: 27.4 }, leftFoot: { x: -30.6 }, leftToes: { x: 1 } } },
        { s: 0.865, hips: { dx: 0.0588, dy: -0.3794, dz: -0.0973 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 67.6 }, leftUpperLeg: { x: -88.1, y: 12.9, z: 27.4 }, leftFoot: { x: -28.6 }, leftToes: { x: 1 } } },
        { s: 0.875, hips: { dx: 0.0526, dy: -0.3804, dz: -0.0983 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 64.3 }, leftUpperLeg: { x: -88.3, y: 12.4, z: 28.6 }, leftFoot: { x: -26.6 }, leftToes: { x: -9 } } },
        { s: 0.885, hips: { dx: 0.0534, dy: -0.3822, dz: -0.1009 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 60.6 }, leftUpperLeg: { x: -88.5, y: 12.4, z: 28.6 }, leftFoot: { x: -24.6 }, leftToes: { x: 1 } } },
        { s: 0.895, hips: { dx: 0.0467, dy: -0.3833, dz: -0.1019 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 56.5 }, leftUpperLeg: { x: -88.7, y: 11.9, z: 29.8 }, leftFoot: { x: -22.6 }, leftToes: { x: -19 } } },
        { s: 0.905, hips: { dx: 0.0475, dy: -0.385, dz: -0.1045 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 52 }, leftUpperLeg: { x: -88.8, y: 11.9, z: 29.8 }, leftFoot: { x: -26.6 }, leftToes: { x: 1 } } },
        { s: 0.915, hips: { dx: 0.0476, dy: -0.3867, dz: -0.1072 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 47.4 }, leftUpperLeg: { x: -89, y: 11.8, z: 29.8 }, leftFoot: { x: -24.6 }, leftToes: { x: -9 } } },
        { s: 0.925, hips: { dx: 0.0469, dy: -0.3885, dz: -0.1099 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 42.5 }, leftUpperLeg: { x: -89.2, y: 11.6, z: 29.8 }, leftFoot: { x: -22.6 }, leftToes: { x: -19 } } },
        { s: 0.935, hips: { dx: 0.0405, dy: -0.3898, dz: -0.1111 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 37.5 } } },
        { s: 0.945, hips: { dx: 0.0413, dy: -0.3914, dz: -0.1136 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 32.6 } } },
        { s: 0.955, hips: { dx: 0.0414, dy: -0.3932, dz: -0.1163 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 27.6 } } },
        { s: 0.965, hips: { dx: 0.0367, dy: -0.3947, dz: -0.1179 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 22.7 } } },
        { s: 0.975, hips: { dx: 0.0376, dy: -0.3965, dz: -0.1205 }, bones: { rightFoot: { x: 63 }, rightToes: { x: 18.1 } } },
    ],
};
// Kept outside the baked track (the key table is regenerated by the
// offline solver): the tail spring chain is steered aside and damped while
// the beat is active — without this the stepping leg's colliders bat it
// around at ~10Hz during the rise. (The tail has NO animatable root on
// claude_suit — every link is a spring joint parented straight to the
// hips — so it is steered through the spring settings, not pose keys.)
export const KNEEL_PLACE_EXTRAS = {
    calm: [{ match: '^tail', drag: 0.88, gravityDir: [0.8, 0.3, -0.35], gravityPower: 0.35 }],
};

// Leg length (hip joint -> knee -> ankle) of claude_suit.vrm, the rig the
// preset's contacts were solved on. At equal joint angles FK positions
// scale with segment length, so on another humanoid the per-key hips
// translations are scaled by its leg length relative to this. Joint ANGLES
// transfer as-is. Contacts remain approximate on other rigs (foot and shoe
// geometry differ) — re-verify mesh-vs-floor before shipping a shot.
const CLAUDE_SUIT_LEG = 0.776;

function legLength(vrm) {
    const THREE = globalThis.THREE;
    const p = (n) => {
        const b = vrm.humanoid?.getRawBoneNode?.(n);
        return b ? b.getWorldPosition(new THREE.Vector3()) : null;
    };
    const hip = p('leftUpperLeg'), knee = p('leftLowerLeg'), ankle = p('leftFoot');
    if (!hip || !knee || !ankle) return CLAUDE_SUIT_LEG;
    return hip.distanceTo(knee) + knee.distanceTo(ankle);
}

export function makeKneelPlace(vrm, overrides = {}) {
    const base = overrides.track || KNEEL_PLACE_TRACK;
    const scale = legLength(vrm) / CLAUDE_SUIT_LEG;
    const track = {
        ...base,
        calm: base.calm || KNEEL_PLACE_EXTRAS.calm,
        keys: scale === 1 ? base.keys : base.keys.map((k) => ({
            ...k,
            hips: k.hips && {
                dx: k.hips.dx * scale, dy: k.hips.dy * scale, dz: k.hips.dz * scale,
            },
        })),
    };
    if (Math.abs(scale - 1) > 0.02) console.log(
        `[pose_layers] makeKneelPlace: hips deltas scaled x${scale.toFixed(3)} for this rig's leg length (preset solved on claude_suit.vrm)`);
    return makePoseTrack(vrm, track);
}
