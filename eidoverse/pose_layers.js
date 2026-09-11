// pose_layers.js — procedural pose OVERLAYS on top of a playing clip, for
// beats the clip library doesn't cover (kneel-and-place, custom leans).
//
// USAGE (stationary VRM on an idle clip — NOT under a locomotion controller):
//     // in setup():
//     eval(Deno.readTextFileSync('eidoverse/pose_layers.js'));
//     await globalThis.playVRMADefault(vrm, 'idle', { loopOnce: false });
//     globalThis._kneel = globalThis.makeKneelPlace(vrm);
//     // in renderFrame(t), BEFORE renderAsync:
//     const k = globalThis._kneel.cycle(t, { t0: 44.8, inDur: 2.2, hold: 1.4, outDur: 1.8 });
//     globalThis._kneel.apply(k, 1 / FPS);
//
// ARCHITECTURE — a keyframed pose track, not a single hand-authored delta.
// The kneel is authored as a sequence of KEY POSES along a path position
// s ∈ [0,1] (foot pickup → ball plant → deep descent → knee touchdown →
// settled genuflect + place-reach). Each key stores ABSOLUTE normalized-local
// bone targets; apply(t01) treats t01 as the path position and slerps each
// bone between the bracketing keys (below the first key it slerps from the
// live clip sample, so t01=0 is an exact restore and idle sway blends out
// smoothly instead of snapping). Sequencing lives in the key SPACING —
// exactly how a clip works — rather than in per-bone phase envelopes.
//
// The key values are DERIVED FROM THE CLIP LIBRARY, not eyeballed:
// work/kneel2/ sampled every humanoid bone across stand_to_sit / jump /
// sitting_on_ground / reach (see poses.jsonl there), which fixed the rig's
// joint conventions (hip flexion = -x on upperLeg, knee flexion = +x on
// lowerLeg, foot +x = plantarflexion, ELBOW HINGE = local Y, arm-at-side =
// upperArm z ≈ ∓65°) and supplied the naturally-coordinated fragments (the
// descent leg is the jump-crouch leg; torso fold + balance arms follow
// stand_to_sit's curve; the reach shape comes from the reach clip). The hips
// translation PER KEY was solved numerically against the real rig: FK-pin
// the planted left ankle to its standing world position (work/kneel2/
// compose.js), so the planted foot cannot drift by construction.
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

'use strict';

(() => {
    function smooth(t) { return t * t * (3 - 2 * t); }
    const clamp01 = (v) => Math.max(0, Math.min(1, v));
    const D2R = Math.PI / 180;

    // makePoseTrack(vrm, track) — general mechanism.
    // track.keys: [{ s, hips: {dx,dy,dz}, bones: { name: {x,y,z} degrees } }]
    // sorted by s, absolute normalized-local targets. A bone missing from a
    // key holds the live clip sample at that key (target = base).
    globalThis.makePoseTrack = function (vrm, track) {
        const THREE = globalThis.THREE;
        const keys = [...track.keys].sort((a, b) => a.s - b.s);
        const boneNames = [...new Set(keys.flatMap(k => Object.keys(k.bones)))];

        // knot vector: the LIVE BASE is the s=0 knot, then the authored keys.
        // Interpolation is monotone cubic (Fritsch–Carlson / PCHIP) per euler
        // axis — C1 in time and overshoot-free, so a monotone key sequence can
        // NEVER produce a joint that bends past a key and swings back (piecewise
        // slerp had velocity corners at every key; a human eye reads those as
        // the joint flip-flopping even when the key values themselves are clean).
        const S = [0, ...keys.map(k => k.s)];
        const N = S.length;
        const H = []; for (let i = 0; i < N - 1; i++) H.push(S[i + 1] - S[i]);

        // evaluate the monotone cubic through values V (length N) at s
        function pchip(V, s) {
            if (s <= S[0]) return V[0];
            if (s >= S[N - 1]) return V[N - 1];
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
            let node;
            if (name.startsWith('node:')) {
                const want = name.slice(5);
                const hits = [], links = [];
                const linkRe = new RegExp('^' + want + '_?\\d+$');
                vrm.scene?.traverse?.((o) => {
                    if (o.name === want) hits.push(o);
                    else if (linkRe.test(o.name)) links.push(o);
                });
                node = hits.find(o => o.isBone) || hits[0];
                if (!node && links.length) {
                    // chain-root fallback: the parent of the first numbered
                    // link (loader name-dedup can leave the root differently
                    // named — e.g. the tail chain loads as tail_2..tail_6).
                    links.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
                    node = links[0].parent;
                    console.log(`[pose_layers] node:${want} resolved via chain root -> '${node?.name}'`);
                }
            } else {
                node = vrm.humanoid?.getNormalizedBoneNode?.(name);
            }
            if (!node) { console.warn('[pose_layers] missing bone:', name); continue; }
            // per-key euler (radians), or null = "live base" at that key
            const eulKeys = keys.map((k) => {
                const e = k.bones[name];
                return e ? [(e.x || 0) * D2R, (e.y || 0) * D2R, (e.z || 0) * D2R] : null;
            });
            entries.push({
                node, eulKeys,
                base: new THREE.Quaternion().copy(node.quaternion),
                baseEul: new THREE.Euler(),
                lastWritten: null,
                vals: new Float64Array(N),
                outEul: new THREE.Euler(),
                tmp: new THREE.Quaternion(),
            });
        }
        const hips = vrm.humanoid?.getNormalizedBoneNode?.('hips');
        const hipsKeys = keys.map(k => k.hips || { dx: 0, dy: 0, dz: 0 });
        const hipsState = hips ? { base: hips.position.clone(), last: null, vals: new Float64Array(N) } : null;
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

        return {
            apply(t01, dt = 0) {
                const k = clamp01(t01);
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
                                b.vals[i + 1] = b.eulKeys[i] ? b.eulKeys[i][ax] : be[ax];
                            out[ax] = pchip(b.vals, k);
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
                        for (const [ax, key] of [['x', 'dx'], ['y', 'dy'], ['z', 'dz']]) {
                            hipsState.vals[0] = 0;
                            for (let i = 0; i < hipsKeys.length; i++) hipsState.vals[i + 1] = hipsKeys[i][key] || 0;
                            hips.position[ax] += pchip(hipsState.vals, k);
                        }
                    }
                    hipsState.last = hipsState.last || hips.position.clone();
                    hipsState.last.copy(hips.position);
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
    };

    // Right-knee genuflect with a right-hand place/pick reach to the ground,
    // left forearm resting on the left thigh. Left foot planted throughout
    // (hips deltas solved by FK ankle-pinning); right foot steps back onto
    // the ball, rolls over the toes as the knee lands, then lays flat
    // (instep down). Values in degrees, normalized rig, +Z facing.
    globalThis.KNEEL_PLACE_TRACK = {
        keys: [
            { s: 0.14, name: 'pickup',
              hips: { dx: 0.0552, dy: -0.0008, dz: 0.0496 },
              bones: {
                hips: { x: 2 },
                spine: { x: 6 },
                chest: { x: 4 },
                neck: {},
                head: { x: -3 },
                leftUpperLeg: { x: -15.4, z: 0.4 },
                leftLowerLeg: { x: 16 },
                leftFoot: { x: -3 },
                rightUpperLeg: { x: 10 },
                rightLowerLeg: { x: 34 },
                rightFoot: { x: 20 },
                leftUpperArm: { x: 2, y: -22, z: -64 },
                leftLowerArm: { y: -14 },
                rightUpperArm: { x: 8, y: 24, z: 58 },
                rightLowerArm: { y: 14 },
              } },
            { s: 0.3, name: 'shift',
              hips: { dx: 0.0603, dy: -0.062, dz: 0.0194 },
              bones: {
                hips: { x: 3 },
                spine: { x: 12 },
                chest: { x: 8 },
                neck: { x: -1 },
                head: { x: -7 },
                leftUpperLeg: { x: -34.7 },
                leftLowerLeg: { x: 46 },
                leftFoot: { x: -13 },
                rightUpperLeg: { x: 14 },
                rightLowerLeg: { x: 36 },
                rightFoot: { x: 30 },
                leftUpperArm: { x: -4, y: -26, z: -58 },
                leftLowerArm: { y: -30 },
                rightUpperArm: { x: -2, y: 22, z: 50 },
                rightLowerArm: { y: 26 },
              } },
            { s: 0.46, name: 'lower',
              hips: { dx: 0.0558, dy: -0.1011, dz: -0.0182 },
              bones: {
                hips: { x: 3.5 },
                spine: { x: 15 },
                chest: { x: 11 },
                neck: { x: -3 },
                head: { x: -12 },
                leftUpperLeg: { x: -47.2, y: -4, z: -2.5 },
                leftLowerLeg: { x: 63, y: -4 },
                leftFoot: { x: -7.7 },
                rightUpperLeg: { x: 8 },
                rightLowerLeg: { x: 48 },
                rightFoot: { x: 42 },
                leftUpperArm: { x: -9, y: -26, z: -52 },
                leftLowerArm: { y: -39 },
                rightUpperArm: { x: -9, y: 21, z: 42 },
                rightLowerArm: { y: 32 },
              } },
            { s: 0.62, name: 'deep',
              hips: { dx: 0.0464, dy: -0.2558, dz: -0.0485 },
              bones: {
                hips: { x: 4 },
                spine: { x: 18 },
                chest: { x: 14 },
                neck: { x: -5 },
                head: { x: -18 },
                leftUpperLeg: { x: -73.1, y: -6, z: -6.2 },
                leftLowerLeg: { x: 100, y: -7 },
                leftFoot: { x: -9.1 },
                rightUpperLeg: { x: 2 },
                rightLowerLeg: { x: 70 },
                rightFoot: { x: 50 },
                leftUpperArm: { x: -14, y: -26, z: -46 },
                leftLowerArm: { y: -48 },
                rightUpperArm: { x: -16, y: 20, z: 34 },
                rightLowerArm: { y: 38 },
              } },
            { s: 0.82, name: 'touchdown',
              hips: { dx: 0.0317, dy: -0.39, dz: -0.0889 },
              bones: {
                hips: { y: -3 },
                spine: { x: 17 },
                chest: { x: 13 },
                neck: { x: -5 },
                head: { x: -16 },
                leftUpperLeg: { x: -87.6, y: -4, z: 3.4 },
                leftLowerLeg: { x: 115.7, y: -5 },
                leftFoot: { x: -18.7 },
                rightUpperLeg: { x: 4 },
                rightLowerLeg: { x: 80 },
                rightFoot: { x: 56 },
                leftUpperArm: { x: -10, y: -18, z: -50 },
                leftLowerArm: { y: -58 },
                rightShoulder: { x: -4, z: 12 },
                rightUpperArm: { x: -25, y: 38, z: 55 },
                rightLowerArm: { y: 22 },
              } },
            { s: 1, name: 'settle',
              hips: { dx: 0.0233, dy: -0.3934, dz: -0.0861 },
              bones: {
                hips: { x: -4, y: -6 },
                spine: { x: 23, y: -4 },
                chest: { x: 19, y: -6, z: -8 },
                neck: { x: -8, z: 4 },
                head: { x: -23, y: 5, z: 4 },
                leftUpperLeg: { x: -81.3, y: -4, z: 7.5 },
                leftLowerLeg: { x: 113.7, y: -5 },
                leftFoot: { x: -27 },
                rightUpperLeg: { x: 6 },
                rightLowerLeg: { x: 88 },
                rightFoot: { x: 60 },
                leftUpperArm: { x: -14, y: -12, z: -48 },
                leftLowerArm: { y: -70 },
                leftHand: { x: -12 },
                rightShoulder: { x: -8, z: 26 },
                rightUpperArm: { x: -30, y: 59, z: 70 },
                rightLowerArm: { y: 6 },
                rightHand: { x: -20 },
              } },
        ],
    };
    // Not part of the baked track (bake.py regenerates KNEEL_PLACE_TRACK):
    // the tail is swept toward the PLANTED-leg side and slightly lifted for
    // the whole beat, keeping the spring chain out of the stepping leg's
    // collider sweep — without this the leg bats the tail around at ~10Hz
    // during the rise (human-caught). calm raises the tail springs' damping
    // while the overlay is active (restored exactly at k=0).
    // (The tail has NO animatable root on claude_suit — every link is a
    // spring joint parented straight to the hips — so it is steered through
    // the spring settings, not pose keys.)
    globalThis.KNEEL_PLACE_EXTRAS = {
        calm: [{ match: '^tail', drag: 0.88, gravityDir: [0.8, 0.3, -0.35], gravityPower: 0.35 }],
        tail: {},
    };

    globalThis.makeKneelPlace = function (vrm, overrides = {}) {
        const base = overrides.track || globalThis.KNEEL_PLACE_TRACK;
        const X = globalThis.KNEEL_PLACE_EXTRAS;
        const track = {
            ...base,
            calm: base.calm || X.calm,
            keys: base.keys.map((k) => ({
                ...k,
                bones: (k.name && X.tail[k.name])
                    ? { ...k.bones, 'node:tail': X.tail[k.name] }
                    : k.bones,
            })),
        };
        return globalThis.makePoseTrack(vrm, track);
    };
})();
