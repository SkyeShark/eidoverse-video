// creature_builder.js — globalThis.makeCreature: the universal procedural
// creature builder. Spore-style: a SPINE of control points + radii defines
// the body; limbs, tail, neck, eyes, horns and fins snap onto parametric
// body coordinates; the whole thing is AUTO-RIGGED (real THREE.Bone
// skeleton, analytically-perfect skin weights — the geometry is generated,
// so every vertex knows its bones) and AUTO-ANIMATED (a gait engine that
// retargets to the morphology: 0 leg pairs = serpentine slither, 1 pair =
// biped walk, 2 pairs = trot, 3+ = insect wave gait; two-bone analytic leg
// IK plants feet on the ground plane, spine sways, tail whips, eyes blink).
//
//   const c = globalThis.makeCreature({
//       stance: 'quad',              // 'quad' | 'biped' | 'serpent' (or infer from legPairs)
//       legPairs: 2,                 // 0..4 — drives the gait automatically
//       bodyLength: 1.6, bodyRadius: 0.22,
//       neck: 0.5, tail: 1.0,        // lengths (0 = none)
//       legLength: 0.75,
//       eyes: 2, horns: 0, fins: 0,
//       color: 0x6a8f4a, belly: 0xcfc7a2, accent: 0x2f4a26,
//       pattern: 'spots',            // 'plain' | 'spots' | 'stripes'
//       seed: 7,                     // shape jitter + pattern layout
//       speed: 0.5, turn: 0.25,      // m/s, rad/s (turn makes it walk arcs)
//   });
//   c.group.position.set(0, 0, 0);   // spawn point (y is managed by the gait)
//   scene.add(c.group);
//   // that's it — self-animating via the engine loop (auto:true default).
//   // Steering: c.speed = 0.8; c.turn = -0.4; c.setHeading(a); c.walkTo(x, z);
//   // Manual drive: pass auto:false and call c.update(t) in renderFrame.
//
//   const rando = globalThis.makeCreature(makeCreature.random(42));  // surprise me
//
// Morphology notes (agent-first):
// - `stance` picks the spine layout: 'quad' = horizontal spine on legs,
//   'biped' = upright torso (legPairs forced 1, arms added), 'serpent' =
//   ground-hugging undulator (legPairs 0). Omit it and legPairs decides.
// - Serpents move by GROUND-FIXED PATH FOLLOWING: the head traces a
//   sinuous trail and every spine bone rides that same trail — the
//   S-curves stay planted in the world while the body slides through
//   them (real lateral undulation; no lateral side-slip). Tune with
//   `waveLength` (S length, default bodyLength*0.55), `waveAmp`
//   (half-width), `headLift` (raised head, 0..~1.2). Turns propagate
//   down the body; a stopped serpent rests in its curve, scans its
//   head, and flicks its tongue.
// - Bipeds walk with human gait detail: pelvis yaw + list, shoulder
//   counter-rotation, lateral weight shift over the stance foot,
//   heel-toe foot roll, speed-scaled arm counter-swing, and an eased
//   settle when speed drops to 0. Stride auto-scales with speed.
// - `headType: 'skull'` (what makeCreature.human() uses) builds a
//   sculpted person head — skull + jaw + brows + small recessed eyes +
//   tilted hair cap — instead of the generic tube-bulge head.
// - ANIMAL FACES (tube heads): quads default to a lofted `muzzle` with
//   nose pad + mouth slit; eyes get iris + pupil (`pupil:'slit'`,
//   `eyeColor`) and a hooding upper lid; `ears: 'point'|'flop'|'round'`
//   sit on flick-animated pivots; add `fangs`, `tusks` (curling, with
//   `tuskLength`), `horns` with `hornStyle: 'spike'|'ram'|'antler'`;
//   birds get a hooked two-mandible `beak` (`beakHook`, `beakColor`).
// - 'insect' (3+ leg pairs, tripod gait, compound eyes, antennae, buzzing
//   translucent wings — `wings: 4` for a dragonfly) and 'spider' (4 pairs,
//   alternating-tetrapod gait, fanned wide stance, abdomen bulb, 8-eye
//   cluster, chelicerae). Arthropod legs splay out with knees ABOVE the
//   body; feet are pointed.
// - FEET: `feet: 'shoe'|'paw'|'hoof'|'webbed'|'lizard'|'talon'` (defaults:
//   biped shoe, quad paw, bird talon). Ankles plant at foot height — soles
//   rest ON the ground.
// - 'fish': deep body → caudal peduncle, lofted tail + dorsal fins,
//   fluttering pectorals, tail-amplified swim wave, banks into turns,
//   hovers at `swimDepth` (default 0.75). No blink (no eyelids).
// - QUAD GAITS: 4-beat lateral WALK at low speed, diagonal TROT above
//   ~0.75 m/s (`gait: 'walk'|'trot'|'auto'`), phases BLEND across ~1s on
//   transition. Girdle counter-rotation (hips vs shoulders) like the
//   human pelvis. Birds waddle-roll with a counterweight tail fan.
// - MIX EVERYTHING: parts are gated by OPTIONS, not stance — beak on a
//   quad (platypus: quad+beak+webbed+tailStyle:'paddle'), trunk + tusks +
//   earScale 2 (elephant), neck 1.3 + legLength 1.1 (giraffe), wings on
//   anything (dragons), hat on a snake. `eyelids: 0..1` (droopiness; they
//   still blink), `tailStyle: 'tube'|'fan'|'paddle'`, `trunk`, `earScale`.
// - WINGS (feathered): two segments — arm + hand with fanned primaries —
//   that FOLD along the body on the ground and flap with a fast downstroke
//   + lagging hand in the air. fly() adds pitch into climbs, banking into
//   turns. `wingType:'membrane'` forces insect-style buzz wings.
// - ACCESSORIES (any creature with a head): `hat: 'cap'|'top'|'beanie'|
//   'cowboy'|'officer'`, `helmet: 'space'|'hardhat'`, `sunglasses`,
//   `glasses` (clear frames), `mask: 'smile'|'frown'` (emoji face),
//   `tie: true|color` (bipeds); outfit bipeds get collar + sleeves.
// - MORE ORGANS: 'snail' stance (slug glide, eye stalks, spiral shell —
//   `shell: true` mounts the spiral on ANY creature), `wingType: 'bat'`
//   (membrane + finger ribs) and `'butterfly'` (paneled, eye-spot, folds
//   upright at rest), `hornStyle: 'moose'|'narwhal'`, `nose: 'star'`
//   (star-nosed mole), `buckTeeth`, `beakWidth` (duck bill ≈1.6),
//   `spikes` (hedgehog), `armor` (armadillo bands), `gills` (axolotl),
//   `claws` (crustacean pincers), `antennae` (any head; metal + glowing
//   tips when robot), `squid: true` (octopus: cone mantle + 2 feeding
//   tentacles + mantle fins), `build: 'feminine'` + `hair: 'long'` (biped).
// - `robot: true` restyles: metallic panel-line plating, LED iris eyes,
//   dark joint caps at hips/knees/shoulders — works on every stance.
//   PER-ELEMENT: `robotParts: ['arms','head','legs','tail','neck','body',
//   'tentacles']` makes cyborg mixes (robot arm on an organic body).
// - Custom materials: body takes `map`/`normalMap`/`roughnessMap` over
//   tube UVs; every add-on part is a named mesh — `c.parts('shell')` etc.
//   returns them for direct material swaps.
// - Tube junctions (tail/neck/hips/shoulders) are sealed by WELD BALLS
//   parented to the parent bone — seams stay covered at any pose.
// - Legs attach in PAIRS spread evenly along the body. legPairs>2 reads
//   best with a longer bodyLength (insects are long).
// - The ground is the y=0 plane of the creature's group parent. Put the
//   group at floor height (or pass groundY).
// - Everything is MeshStandardNodeMaterial + one shared Skeleton; the
//   pattern is a TSL colorNode over BIND-pose positions, so it stays
//   glued to the skin during animation.
(function () {
    const THREE = globalThis.THREE;

    // ── deterministic rng ──
    function mulberry(seed) {
        let a = (seed | 0) + 0x6D2B79F5;
        return function () {
            a |= 0; a = (a + 0x6D2B79F5) | 0;
            let t = Math.imul(a ^ (a >>> 15), 1 | a);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }

    const V = (x, y, z) => new THREE.Vector3(x, y, z);
    const TMP = { a: new THREE.Vector3(), b: new THREE.Vector3(), c: new THREE.Vector3(), d: new THREE.Vector3(), q: new THREE.Quaternion(), q2: new THREE.Quaternion(), m: new THREE.Matrix4() };
    const UP = new THREE.Vector3(0, 1, 0);        // never mutated
    const UNIT_Z = new THREE.Vector3(0, 0, 1);    // never mutated

    // ── skinned tube: rings along a smooth curve through `pts`, radius per
    // control point,每 ring weighted between its two bracketing bones.
    // bones[i] sits at pts[i]. Returns BufferGeometry with skin attributes
    // (bone indices offset by `boneBase` into the shared skeleton).
    function skinnedTube(pts, radii, boneBase, opts = {}) {
        const radial = opts.radial ?? 12;
        const per = opts.ringsPerSpan ?? 5;
        const curve = new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.5);
        const spans = pts.length - 1;
        const rings = spans * per + 1;
        // parallel-transport frames — computeFrenetFrames degenerates on
        // straight (colinear) paths, which limbs and tails usually are:
        // the tube then collapses into a flat blade. Build robust frames.
        const frames = { tangents: [], normals: [], binormals: [] };
        {
            let N = null;
            for (let r = 0; r < rings; r++) {
                const T = curve.getTangentAt(r / (rings - 1)).normalize();
                if (!N) {
                    // any stable perpendicular to T
                    const ref = Math.abs(T.y) < 0.9 ? V(0, 1, 0) : V(1, 0, 0);
                    N = ref.clone().addScaledVector(T, -ref.dot(T)).normalize();
                } else {
                    N = N.clone().addScaledVector(T, -N.dot(T));
                    if (N.lengthSq() < 1e-10) N = (Math.abs(T.y) < 0.9 ? V(0, 1, 0) : V(1, 0, 0)).addScaledVector(T, -(Math.abs(T.y) < 0.9 ? T.y : T.x));
                    N.normalize();
                }
                frames.tangents.push(T);
                frames.normals.push(N);
                frames.binormals.push(new THREE.Vector3().crossVectors(T, N));
            }
        }

        const pos = [], nor = [], uv = [], sIdx = [], sWgt = [], idx = [];
        const radiusAt = (u) => {
            const f = u * spans, i = Math.min(spans - 1, Math.floor(f)), t = f - i;
            const s = t * t * (3 - 2 * t);
            return radii[i] * (1 - s) + radii[i + 1] * s;
        };
        for (let r = 0; r < rings; r++) {
            const u = r / (rings - 1);
            const p = curve.getPointAt(u);
            const N = frames.normals[Math.min(r, frames.normals.length - 1)];
            const B = frames.binormals[Math.min(r, frames.binormals.length - 1)];
            const rad = radiusAt(u);
            // taper into rounded tips — but ONLY at FREE ends (a tube whose
            // start joins the body must NOT pinch at the junction)
            const tS = (opts.taperStart ?? true) ? r / (per * 0.9) : 1;
            const tE = (opts.taperEnd ?? true) ? (rings - 1 - r) / (per * 0.9) : 1;
            const tip = Math.min(1, tS, tE);
            const rr = rad * (0.15 + 0.85 * Math.sin(Math.min(tip, 1) * Math.PI * 0.5));
            // bone weighting: bones live at control points (u_i = i/spans)
            const f = u * spans, bi = Math.min(spans - 1, Math.floor(f)), bt = f - bi;
            const w = bt * bt * (3 - 2 * bt);
            for (let k = 0; k < radial; k++) {
                const a = (k / radial) * Math.PI * 2;
                const dir = TMP.a.copy(N).multiplyScalar(Math.cos(a)).addScaledVector(B, Math.sin(a));
                pos.push(p.x + dir.x * rr, p.y + dir.y * rr, p.z + dir.z * rr);
                nor.push(dir.x, dir.y, dir.z);
                uv.push(k / radial, u);
                sIdx.push(boneBase + bi, boneBase + bi + 1, 0, 0);
                sWgt.push(1 - w, w, 0, 0);
            }
        }
        for (let r = 0; r < rings - 1; r++) {
            for (let k = 0; k < radial; k++) {
                const a = r * radial + k, b = r * radial + (k + 1) % radial;
                const c = a + radial, d = b + radial;
                idx.push(a, b, c, b, d, c);   // outward-facing winding
            }
        }
        // rounded end caps (single fan vertex nudged outward)
        for (const end of [0, rings - 1]) {
            const u = end / (rings - 1);
            const p = curve.getPointAt(u);
            const T = frames.tangents[Math.min(end, frames.tangents.length - 1)];
            const sgn = end === 0 ? -1 : 1;
            const rad = radiusAt(u) * 0.35;
            const ci = pos.length / 3;
            pos.push(p.x + T.x * rad * sgn, p.y + T.y * rad * sgn, p.z + T.z * rad * sgn);
            nor.push(T.x * sgn, T.y * sgn, T.z * sgn);
            uv.push(0.5, u);
            const bi = end === 0 ? 0 : pts.length - 2;
            sIdx.push(boneBase + bi, boneBase + bi + 1, 0, 0);
            sWgt.push(end === 0 ? 1 : 0, end === 0 ? 0 : 1, 0, 0);
            const ring0 = end === 0 ? 0 : (rings - 1) * radial;
            for (let k = 0; k < radial; k++) {
                const a = ring0 + k, b = ring0 + (k + 1) % radial;
                if (end === 0) idx.push(ci, b, a); else idx.push(ci, a, b);
            }
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
        g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
        g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(sIdx, 4));
        g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(sWgt, 4));
        g.setIndex(idx);
        return g;
    }

    // bone chain at the given LOCAL points; parented under `parent`.
    function boneChain(pts, parent, allBones) {
        const chain = [];
        let prev = parent, prevP = null;
        if (parent && parent.userData.bindPos) prevP = parent.userData.bindPos;
        for (let i = 0; i < pts.length; i++) {
            const b = new THREE.Bone();
            const p = pts[i];
            if (prevP) b.position.copy(p).sub(prevP);
            else b.position.copy(p);
            b.userData.bindPos = p.clone();
            prev.add(b);
            allBones.push(b);
            chain.push(b);
            prev = b; prevP = p;
        }
        return chain;
    }

    // two-bone analytic IK: rotate `hip` and `knee` bones so the ankle bone
    // lands at world `target`. Bend plane chosen by world `pole` direction.
    const IK = { T: new THREE.Vector3(), P: new THREE.Vector3(), H: new THREE.Vector3(),
        HT: new THREE.Vector3(), pp: new THREE.Vector3(), K: new THREE.Vector3(), w: new THREE.Vector3() };
    function solveLegIK(hip, knee, ankle, target, pole, L1, L2) {
        // COPY FIRST: callers legitimately pass TMP vectors as target/pole —
        // grabbing TMP.a for the hip below would destroy the target
        // (this aliasing folded swinging legs onto the hip for three
        // straight versions).
        IK.T.copy(target); IK.P.copy(pole);
        hip.updateWorldMatrix(true, false);
        const H = IK.H.setFromMatrixPosition(hip.matrixWorld);
        const HT = IK.HT.copy(IK.T).sub(H);
        let d = HT.length();
        const dMax = (L1 + L2) * 0.999, dMin = Math.abs(L1 - L2) + 1e-4;
        d = Math.min(Math.max(d, dMin), dMax);
        const axis = HT.normalize();
        const a = (L1 * L1 + d * d - L2 * L2) / (2 * d);
        const h = Math.sqrt(Math.max(0, L1 * L1 - a * a));
        const poleP = IK.pp.copy(IK.P).addScaledVector(axis, -IK.P.dot(axis));
        if (poleP.lengthSq() < 1e-8) poleP.set(0, 0, 1).addScaledVector(axis, -axis.z);
        poleP.normalize();
        // world knee position
        const K = IK.K.copy(H).addScaledVector(axis, a).addScaledVector(poleP, h);

        // hip: rotate so the knee bind-offset points at K
        const parentQ = hip.parent.getWorldQuaternion(TMP.q);
        const bindDir = TMP.b.copy(knee.userData.bindPos).sub(hip.userData.bindPos).normalize();
        const wantW = IK.w.copy(K).sub(H).normalize();
        const wantL = wantW.applyQuaternion(TMP.q2.copy(parentQ).invert());
        hip.quaternion.setFromUnitVectors(bindDir, wantL);

        // knee: rotate so the ankle bind-offset points at the target
        hip.updateWorldMatrix(true, false);
        const hipQ = hip.getWorldQuaternion(TMP.q);
        const bindDir2 = TMP.b.copy(ankle.userData.bindPos).sub(knee.userData.bindPos).normalize();
        const wantW2 = IK.w.copy(IK.T).sub(K).normalize();
        const wantL2 = wantW2.applyQuaternion(TMP.q2.copy(hipQ).invert());
        knee.quaternion.setFromUnitVectors(bindDir2, wantL2);
    }

    // ── pattern material: TSL colorNode over bind-pose positions ──
    function creatureMaterial(o) {
        const { vec3, float, positionGeometry, normalGeometry, sin, mix, smoothstep, clamp, dot } = THREE;
        const mat = new THREE.MeshStandardNodeMaterial({
            roughness: o.robot ? 0.35 : (o.roughness ?? 0.65),
            metalness: o.robot ? 0.8 : 0.02 });
        if (o.robot) {
            // machine plating: base color with darker panel bands over the
            // bind pose (sin-band grid — no texture needed)
            const base = new THREE.Color(o.color);
            const p = positionGeometry;
            const bandY = smoothstep(0.93, 0.985, sin(p.y.mul(34.0)));
            const bandZ = smoothstep(0.93, 0.985, sin(p.z.mul(30.0).add(p.x.mul(6.0))));
            const seam = clamp(bandY.add(bandZ), 0.0, 1.0);
            mat.colorNode = mix(vec3(base.r, base.g, base.b),
                vec3(base.r * 0.35, base.g * 0.35, base.b * 0.35), seam);
            return mat;
        }
        // IMAGE-textured skin: pass a loaded texture (loadImageTexture /
        // fetch_texture PBR maps) and it maps over the tube UVs (u around
        // the body, v along it — set texture.repeat for scale). Procedural
        // patterns/outfit are skipped when a map drives the color.
        if (o.map) {
            o.map.wrapS = o.map.wrapT = THREE.RepeatWrapping;
            mat.map = o.map;
            if (o.normalMap) { o.normalMap.wrapS = o.normalMap.wrapT = THREE.RepeatWrapping; mat.normalMap = o.normalMap; }
            if (o.roughnessMap) { o.roughnessMap.wrapS = o.roughnessMap.wrapT = THREE.RepeatWrapping; mat.roughnessMap = o.roughnessMap; }
            mat.color = new THREE.Color(o.color ?? 0xffffff);
            return mat;
        }
        const base = new THREE.Color(o.color); const belly = new THREE.Color(o.belly); const acc = new THREE.Color(o.accent);
        const p = positionGeometry;
        // organic value noise from stacked trig (cheap, no texture)
        const n = sin(p.x.mul(9.1).add(sin(p.z.mul(7.3)))).mul(sin(p.y.mul(8.7).add(sin(p.x.mul(6.1)))))
            .mul(sin(p.z.mul(10.3).add(p.y.mul(5.2)))).mul(0.5).add(0.5);
        let col = vec3(base.r, base.g, base.b);
        if (o.outfit) {
            // clothing = color bands over bind-pose height (low-poly-game
            // style): skin above the collar, shirt to the hips, pants below,
            // shoes at the ankles. Cheap, reads instantly, animates for free.
            const sh = new THREE.Color(o.outfit.shirt ?? 0x3a6ea8);
            const pn = new THREE.Color(o.outfit.pants ?? 0x35322e);
            const so = new THREE.Color(o.outfit.shoes ?? 0x221d18);
            const yb = p.y;
            col = mix(vec3(sh.r, sh.g, sh.b), col, smoothstep(o.outfit.collarY - 0.015, o.outfit.collarY + 0.015, yb));
            col = mix(vec3(pn.r, pn.g, pn.b), col, smoothstep(o.outfit.hipY - 0.015, o.outfit.hipY + 0.015, yb));
            col = mix(vec3(so.r, so.g, so.b), col, smoothstep(o.outfit.ankleY - 0.01, o.outfit.ankleY + 0.02, yb));
        } else if (o.pattern === 'spots') {
            col = mix(col, vec3(acc.r, acc.g, acc.b), smoothstep(0.62, 0.7, n));
        } else if (o.pattern === 'stripes') {
            const s = sin(p.z.mul(16.0).add(n.mul(3.0))).mul(0.5).add(0.5);
            col = mix(col, vec3(acc.r, acc.g, acc.b), smoothstep(0.55, 0.7, s));
        }
        // belly lightening where the bind normal points down (skip when clothed)
        if (!o.outfit) {
            const downness = clamp(dot(normalGeometry, vec3(0, -1, 0)), 0.0, 1.0);
            col = mix(col, vec3(belly.r, belly.g, belly.b), smoothstep(0.25, 0.85, downness));
        }
        mat.colorNode = col;
        return mat;
    }

    // ── the builder ──
    globalThis.makeCreature = function makeCreature(opts = {}) {
        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('creature_builder');
        const rng = mulberry(opts.seed ?? 1);
        const jit = (s) => 1 + (rng() - 0.5) * 2 * s;

        let legPairs = opts.legPairs ?? 2;
        // stance inference matches the docs: 0=serpent, 1=biped, 2=quad,
        // 3=insect (tripod gait), 4+=spider — explicit stance still wins
        const stance = opts.stance ?? (legPairs === 0 ? 'serpent' : legPairs === 1 ? 'biped'
            : legPairs === 3 ? 'insect' : legPairs >= 4 ? 'spider' : 'quad');   // + 'octopus'
        // 'skull' = sculpted person head (skull+jaw+brows, small recessed
        // eyes) instead of the generic tube-bulge head. Used by .human().
        const headType = opts.headType ?? 'tube';
        // robot styling per ELEMENT: robotParts: ['body','head','legs',
        // 'arms','tail','neck','tentacles'] — cyborg mixes. robot: true = all.
        const robotParts = opts.robotParts ? new Set(opts.robotParts)
            : (opts.robot ? new Set(['body', 'head', 'legs', 'arms', 'tail', 'neck', 'tentacles']) : new Set());
        const robotHead = robotParts.has('head');
        if (stance === 'serpent' || stance === 'octopus' || stance === 'fish' || stance === 'snail') legPairs = 0;
        if (stance === 'biped' || stance === 'bird') legPairs = 1;
        const fem = opts.build === 'feminine';   // narrower shoulders, fuller hips
        if (stance === 'insect') legPairs = Math.max(3, opts.legPairs === 2 ? 3 : (opts.legPairs ?? 3));
        if (stance === 'spider') legPairs = 4;
        // arthropods: legs splay OUT from the side wall, knees ride ABOVE
        // the body line, feet plant wide (see addLimb + the gait home offsets)
        const splayed = stance === 'insect' || stance === 'spider';

        const bodyLen = (opts.bodyLength ?? (stance === 'serpent' ? 2.6 : stance === 'biped' ? 0.72 : stance === 'bird' ? 0.95 : stance === 'insect' ? 0.85 : stance === 'spider' ? 0.7 : stance === 'fish' ? 0.9 : stance === 'snail' ? 0.85 : 1.6)) + (stance === 'serpent' ? (opts.tail ?? 1.0) : 0);
        const bodyRad = opts.bodyRadius ?? (stance === 'serpent' ? 0.14 : stance === 'biped' ? 0.24 : stance === 'bird' ? 0.2 : stance === 'insect' ? 0.13 : stance === 'spider' ? 0.17 : stance === 'fish' ? 0.17 : stance === 'snail' ? 0.18 : 0.22);
        const neckLen = (stance === 'octopus' || splayed || stance === 'fish' || stance === 'snail') ? 0 : (opts.neck ?? (stance === 'serpent' ? 0 : stance === 'bird' ? 0.3 : 0.45));
        // the serpent's tail IS its body — a separate tail tube creases at
        // the junction when the wave bends it. Fold it into one spine.
        const tailLen = (stance === 'serpent' || splayed || stance === 'fish' || stance === 'snail') ? 0 : (opts.tail ?? (stance === 'biped' ? 0.4 : stance === 'bird' ? 0.42 : 1.0));
        const legLen = opts.legLength ?? (stance === 'biped' ? 0.62 : stance === 'bird' ? 0.5 : stance === 'insect' ? 0.5 : stance === 'spider' ? 0.62 : 0.7);
        const armLen = opts.armLength ?? legLen * 0.72;
        // body rides at ~80% of leg length: knees keep a visible bend
        // (arthropods hang LOW between high knees — ~50%)
        const hipH = stance === 'serpent' ? bodyRad * 0.95 : (stance === 'octopus' || stance === 'fish') ? 0 : stance === 'snail' ? bodyRad * 0.45 : splayed ? legLen * 0.5 : legLen * (stance === 'biped' ? 0.84 : 0.78);

        const group = new THREE.Group();
        group.rotation.order = 'YXZ';   // yaw → pitch → roll (flight attitude composes in the heading frame)
        group.userData.allowIntersect = true;
        group.userData.noSupportCheck = true;
        group.userData.isCreature = true;
        const allBones = [];
        const meshes = [];
        const meshPart = [];   // category per skinned mesh, for robotParts
        const pushMesh = (g, cat) => { meshes.push(g); meshPart.push(cat); return meshes.length - 1; };
        // junction welds: a body-material ball parented to the PARENT bone at
        // each tube joint (tail root, neck root, hips, shoulders). The child
        // tube rotates around the ball's center, so the seam stays covered at
        // every pose — no skinning changes, nothing to break.
        const weldMeshes = [];
        const weldBall = (parentBone, creaturePos, r) => {
            if (globalThis.__noWeld) return null;
            const b = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 10), null);
            b.position.copy(creaturePos);
            if (parentBone.userData && parentBone.userData.bindPos) b.position.sub(parentBone.userData.bindPos);
            parentBone.add(b);
            // record the creature-space height: the outfit color bands key on
            // bind-pose Y, but a ball's GEOMETRY is local-origin — sharing the
            // banded body material paints every weld as 'shoe' (black blobs
            // at the shoulders, user-caught)
            weldMeshes.push({ mesh: b, y: creaturePos.y });
            return b;
        };

        // ---- spine control points (creature faces +Z) ----
        const spinePts = [];
        const spineRad = [];
        const nSpine = stance === 'serpent' ? 12 : stance === 'octopus' ? 4 : stance === 'fish' ? 8 : stance === 'snail' ? 6 : 5;
        const squid = stance === 'octopus' && !!opts.squid;
        const octoScale = bodyRad / 0.3;
        for (let i = 0; i < nSpine; i++) {
            const u = i / (nSpine - 1);
            if (stance === 'octopus') {
                // mantle: squat dome (octopus) or a tall tapering cone (squid)
                spinePts.push(V(0, (0.16 + u * (squid ? 1.25 : 0.62)) * octoScale, u * 0.04));
                spineRad.push(bodyRad * (0.85 + 0.5 * Math.sin((0.25 + 0.6 * u) * Math.PI)) * (1 - u * (squid ? 0.72 : 0.45)) * jit(0.06));
            } else if (stance === 'snail') {
                // slug foot: low half-round body, head end gently raised
                spinePts.push(V(0, bodyRad * (0.45 + (u > 0.75 ? (u - 0.75) * 1.3 : 0)), (u - 0.5) * bodyLen));
                spineRad.push(bodyRad * [0.5, 0.85, 1.0, 1.0, 0.88, 0.55][i] * jit(0.05));
            } else if (stance === 'biped') {
                // upright torso: pelvis → waist → chest → shoulders. NOT a
                // sin() football — the old mid bulge read as a pot belly
                // and swallowed the hanging arms.
                spinePts.push(V(0, hipH + u * bodyLen, Math.sin(u * Math.PI) * 0.04));
                spineRad.push(bodyRad * (fem ? [1.02, 0.86, 0.76, 0.94, 0.66] : [0.95, 0.9, 0.87, 1.0, 0.8])[i] * jit(0.05));
            } else if (stance === 'insect') {
                // abdomen(-Z) / pinch / thorax / pinch / head(+Z)
                spinePts.push(V(0, hipH + (i === 0 ? 0.06 : 0) * bodyRad, (u - 0.5) * bodyLen));
                spineRad.push(bodyRad * [1.05, 0.5, 0.95, 0.55, 0.78][i] * jit(0.05));
            } else if (stance === 'spider') {
                // big raised abdomen bulb behind a flat cephalothorax
                spinePts.push(V(0, hipH + [0.55, 0.45, 0.05, 0, 0][i] * bodyRad, (u - 0.5) * bodyLen));
                spineRad.push(bodyRad * [1.45, 1.3, 0.6, 0.85, 0.72][i] * jit(0.04));
            } else if (stance === 'bird') {
                // bird torso is TILTED (rear low → chest high) with a full
                // chest — a level tube + long up-neck reads as a duck.
                // `bodyTilt: 0` + `neck: 0.55` + `tailStyle: 'tube'` brings
                // the dopey waterfowl back ON PURPOSE.
                const tilt = opts.bodyTilt ?? 0.34;
                spinePts.push(V(0, hipH + u * bodyLen * tilt, (u - 0.5) * bodyLen * (1 - tilt * 0.24)));
                spineRad.push(bodyRad * [0.5, 0.74, 0.95, 1.05, 0.8][i] * jit(0.06));
            } else if (stance === 'fish') {
                // deep mid-body → thin caudal peduncle (tail end), tapered nose
                spinePts.push(V(0, 0, (u - 0.5) * bodyLen));
                spineRad.push(bodyRad * [0.24, 0.42, 0.72, 0.95, 1.0, 0.9, 0.7, 0.45][i] * jit(0.05));
            } else {
                // horizontal: tail-end (-Z) → shoulders (+Z)
                spinePts.push(V(0, hipH + (stance === 'quad' ? Math.sin(u * Math.PI) * 0.06 : 0), (u - 0.5) * bodyLen));
                if (stance === 'serpent') {
                    // thin tail (u=0) ramping up, slight head bulb at the front
                    const ramp = Math.min(1, u * 2.6);
                    spineRad.push(bodyRad * (0.22 + 0.78 * Math.sin(ramp * Math.PI * 0.5)) * (u > 0.88 ? 1.12 : 1) * jit(0.05));
                } else {
                    spineRad.push(bodyRad * (0.72 + 0.55 * Math.sin((0.15 + 0.7 * u) * Math.PI)) * jit(0.08));
                }
            }
        }
        // serpents pose their spine bones DIRECTLY in group space each frame
        // (path following needs absolute placement) — flat bones, not a chain
        let spineBones;
        if (stance === 'serpent') {
            spineBones = spinePts.map((p) => {
                const b = new THREE.Bone();
                b.position.copy(p); b.userData.bindPos = p.clone();
                group.add(b); allBones.push(b);
                return b;
            });
        } else {
            spineBones = boneChain(spinePts, group, allBones);
        }
        const spineBase = 0;
        pushMesh(skinnedTube(spinePts, spineRad, spineBase, { radial: 14, taperStart: !(tailLen > 0), taperEnd: !(neckLen > 0) }), 'body');

        // ---- neck + head (continues from spine front) ----
        let headBone = stance === 'octopus' ? spineBones[nSpine - 2] : spineBones[spineBones.length - 1];
        if (neckLen > 0) {
            const s0 = spinePts[spinePts.length - 1];
            const up = stance === 'biped' ? V(0, 1, 0.25) : stance === 'bird' ? V(0, 1, 0.45) : V(0, 0.85, 0.9);
            up.normalize();
            const hr = bodyRad * (opts.headScale ?? 0.85);
            if (headType === 'skull') {
                // person head: the tube is JUST a neck — the skull is built
                // from parts on the head bone below (a tube bulge never
                // reads as a face: pointy crown, no jaw)
                const nPts = [s0.clone(),
                    s0.clone().addScaledVector(up, neckLen * 0.6),
                    s0.clone().addScaledVector(up, neckLen)];
                const nRad = [spineRad[spineRad.length - 1] * 0.7, bodyRad * 0.34, bodyRad * 0.32];
                const base = allBones.length;
                const chain = boneChain(nPts, spineBones[spineBones.length - 1], allBones);
                pushMesh(skinnedTube(nPts, nRad, base, { radial: 10, taperStart: false, taperEnd: false }), 'neck');
                headBone = chain[2];
                var neckBones = chain;
            } else {
                // head = a real rounded volume past the neck, not a squashed
                // slice: the bulge spans ~1.4 head-radii along the axis
                const fb = stance === 'biped' ? 0.03 : 0.22;
                const nPts = [s0.clone(),
                    s0.clone().addScaledVector(up, neckLen * 0.55),
                    s0.clone().addScaledVector(up, neckLen * 0.95).add(V(0, 0, fb * 0.5)),
                    s0.clone().addScaledVector(up, neckLen + hr * 0.55).add(V(0, 0, fb)),
                    s0.clone().addScaledVector(up, neckLen + hr * 1.05).add(V(0, 0, fb * 1.2))];
                const nRad = [spineRad[spineRad.length - 1] * 0.8, bodyRad * 0.42, hr * 0.92, hr, hr * 0.45];
                const base = allBones.length;
                const chain = boneChain(nPts, spineBones[spineBones.length - 1], allBones);
                pushMesh(skinnedTube(nPts, nRad, base, { radial: 12, taperStart: false }), 'neck');
                headBone = chain[3];   // the full-radius head bulge
                var neckBones = chain;
            }
            weldBall(spineBones[spineBones.length - 1], s0, spineRad[spineRad.length - 1] * 0.92);   // neck-body weld
        }

        // ---- tail (continues from spine back) ----
        const tailBones = [];
        let tailFan = null;
        const tailStyle = opts.tailStyle ?? (stance === 'bird' ? 'fan' : 'tube');
        if (tailLen > 0 && tailStyle === 'fan') {
            // tail FAN: overlapping feather blades angled up-back (a tube
            // tail is the other half of the duck look on birds)
            const fanMat = new THREE.MeshStandardNodeMaterial({ color: opts.accent ?? 0x2f4a26, roughness: 0.7, side: THREE.DoubleSide });
            tailFan = new THREE.Group();
            for (const k of [-1, 0, 1]) {
                let blade;
                if (globalThis.Loft) {
                    blade = globalThis.Loft.sweep({
                        path: [V(k * bodyRad * 0.12, 0, 0),
                               V(k * bodyRad * 0.4, tailLen * 0.3, -tailLen * 0.55),
                               V(k * bodyRad * 0.6, tailLen * 0.38, -tailLen)],
                        profile: globalThis.Loft.ellipse(bodyRad * 0.3, bodyRad * 0.05, 8),
                        scale: (tt) => 1 - 0.45 * tt, sections: 8, material: fanMat });
                } else {
                    blade = new THREE.Mesh(new THREE.BoxGeometry(bodyRad * 0.5, bodyRad * 0.06, tailLen), fanMat);
                    blade.position.set(k * bodyRad * 0.4, tailLen * 0.25, -tailLen * 0.5);
                }
                blade.castShadow = true;
                tailFan.add(blade);
            }
            tailFan.position.copy(spinePts[0]).sub(spineBones[0].userData.bindPos);
            spineBones[0].add(tailFan);
        } else if (tailLen > 0 && tailStyle === 'paddle') {
            // flat paddle tail (platypus/beaver): one wide flattened blade
            const padMat = new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(opts.color ?? 0x6a8f4a).multiplyScalar(0.8), roughness: 0.8 });
            const pad = new THREE.Mesh(new THREE.SphereGeometry(tailLen * 0.5, 12, 8), padMat);
            pad.scale.set(0.85, 0.18, 1.0);
            pad.position.copy(spinePts[0]).add(V(0, -bodyRad * 0.15, -tailLen * 0.45)).sub(spineBones[0].userData.bindPos);
            pad.castShadow = true;
            spineBones[0].add(pad);
            tailFan = pad;   // reuse the idle-bob hook
            weldBall(spineBones[0], spinePts[0], spineRad[0] * 0.9);
        } else if (tailLen > 0) {
            const s0 = spinePts[0];
            const back = stance === 'biped' ? V(0, -0.35, -0.75) : V(0, 0.12, -1);
            back.normalize();
            const nT = 4;
            const carry = opts.tailCarry ?? 0;   // 0 = drooping, 1 = raised cat-curl
            const tPts = [s0.clone()];
            for (let i = 1; i <= nT; i++) {
                const f2 = i / nT;
                const lift = stance === 'biped' ? 0 : (-0.04 * i * (1 - carry) + tailLen * carry * 0.34 * Math.sin(f2 * Math.PI * 0.85));
                tPts.push(s0.clone().addScaledVector(back, tailLen * f2 * (1 - carry * 0.3 * f2)).add(V(0, lift, 0)));
            }
            const tR0 = spineRad[0] * 0.85 * (opts.tailRadius ?? 1);   // rats ≈ 0.35
            const tRad = [tR0];
            for (let i = 1; i <= nT; i++) tRad.push(tR0 * (1 - i / (nT + 0.5)));
            const base = allBones.length;
            tailBones.push(...boneChain(tPts, spineBones[0], allBones));
            pushMesh(skinnedTube(tPts, tRad, base, { radial: 10, taperStart: false }), 'tail');
            weldBall(spineBones[0], s0, spineRad[0] * 0.95);   // tail-body weld
        }
        // ---- fish fins: caudal blade + fluttering pectorals ----
        const pectorals = [];
        // aqua mammals (whale/dolphin/narwhal) get horizontal flukes + a
        // vertical swim beat, preconfigured: aqua:'mammal' or a narwhal lance
        const aquaMammal = stance === 'fish' && (opts.aqua === 'mammal'
            || (opts.horns && (opts.hornStyle === 'narwhal')));
        const fishFluke = stance === 'fish' && (opts.caudal ?? (aquaMammal ? 'fluke' : 'vertical')) === 'fluke';
        if (stance === 'fish') {
            const finM = new THREE.MeshStandardNodeMaterial({ color: opts.accent ?? 0x2f4a26, roughness: 0.6, side: THREE.DoubleSide });
            const cl = bodyRad * (opts.caudalScale ?? 2.2);
            let caudal;
            if (globalThis.Loft) {
                // vertical blade (fish) or HORIZONTAL whale flukes
                caudal = globalThis.Loft.sweep({
                    path: [V(0, 0, 0), V(0, cl * 0.05, -cl * 0.5), V(0, 0, -cl)],
                    profile: fishFluke
                        ? globalThis.Loft.ellipse(cl * 0.42, bodyRad * 0.06, 10)
                        : globalThis.Loft.ellipse(bodyRad * 0.06, cl * 0.42, 10),
                    scale: (tt) => 0.35 + 0.65 * tt, sections: 8, material: finM });
            } else {
                caudal = new THREE.Mesh(new THREE.BoxGeometry(fishFluke ? cl : bodyRad * 0.1, fishFluke ? bodyRad * 0.1 : cl, cl), finM);
                caudal.position.z = -cl * 0.5;
            }
            caudal.castShadow = true;
            caudal.position.copy(spinePts[0]).sub(spineBones[0].userData.bindPos);
            spineBones[0].add(caudal);
            for (const sd of [-1, 1]) {
                const pf = new THREE.Group();
                const si2 = Math.round((nSpine - 1) * 0.6);
                pf.position.copy(spinePts[si2]).add(V(sd * spineRad[si2] * 0.85, -spineRad[si2] * 0.2, 0)).sub(spineBones[si2].userData.bindPos);
                const bl = new THREE.Mesh(new THREE.SphereGeometry(bodyRad * 0.55 * (0.6 + 0.4 * (opts.finScale ?? 1)), 8, 6), finM);
                bl.scale.set(1.2, 0.12, 0.5);
                bl.position.x = sd * bodyRad * 0.5;
                pf.add(bl);
                pf.userData.side = sd;
                spineBones[si2].add(pf);
                pectorals.push(pf);
            }
        }

        // ---- legs (pairs spread along the body) + arms for bipeds ----
        const legs = [];
        const armMeshIdx = [];   // arm tube meshes get a sleeve material when outfitted
        const addLimb = (attachBone, hipLocal, isArm, side, fan = 0) => {
            const LL = isArm ? armLen : legLen;
            const L1 = LL * 0.52, L2 = LL * 0.5;
            let kneeP, ankP, r0;
            if (splayed && !isArm) {
                // arthropod leg: femur OUT-AND-UP, tibia down — the knee apex
                // rides above the body; feet plant wide. Thin tubes.
                const L1s = LL * 0.58, L2s = LL * 0.66;
                kneeP = hipLocal.clone().add(V(side * L1s * 0.8, L1s * 0.55, fan * 0.4));
                ankP = kneeP.clone().add(V(side * L2s * 0.4, -L2s * 0.88, fan * 0.25));
                r0 = bodyRad * 0.17;
            } else {
                // slight forward knee bend in bind: keeps the limb curve
                // non-colinear AND gives the IK a consistent bend plane
                kneeP = hipLocal.clone().add(V(0, -L1 * 0.985, LL * 0.09));
                ankP = kneeP.clone().add(V(0, -L2 * 0.985, -LL * 0.07));
                r0 = bodyRad * (isArm ? 0.3 : 0.38);
            }
            const base = allBones.length;
            const chain = boneChain([hipLocal, kneeP, ankP], attachBone, allBones);
            weldBall(attachBone, hipLocal, isArm ? bodyRad * 0.36 : splayed ? r0 * 1.3 : r0 * 1.25);   // hip/shoulder weld
            pushMesh(skinnedTube([hipLocal, kneeP, ankP], [r0, r0 * 0.72, r0 * (splayed && !isArm ? 0.3 : 0.5)], base,
                { radial: splayed && !isArm ? 7 : 9, ringsPerSpan: 4, taperStart: false, taperEnd: !!(splayed && !isArm) }), isArm ? 'arms' : 'legs');
            if (isArm) armMeshIdx.push(meshes.length - 1);
            const realL1 = kneeP.distanceTo(hipLocal), realL2 = ankP.distanceTo(kneeP);
            const leg = { hip: chain[0], knee: chain[1], ankle: chain[2], L1: realL1, L2: realL2, side, isArm,
                plant: new THREE.Vector3(), next: new THREE.Vector3(), planted: false, phase: 0 };
            if (!isArm && !splayed) {
                // typed feet, built sole-down in a group at the ankle. The
                // ankle is IK-planted ankleLift ABOVE the ground so the sole
                // rests ON it (the old sphere foot half-sank).
                const ft = opts.feet ?? (stance === 'bird' ? 'talon' : stance === 'biped' ? 'shoe' : 'paw');
                const isBiped = stance === 'biped';
                const Lf = isBiped ? legLen * 0.3 : r0 * 3.0;
                const foot = new THREE.Group();
                const keep = (m) => { m.userData.keepMat = true; return m; };
                if (ft === 'hoof') {
                    const hm = new THREE.MeshStandardNodeMaterial({ color: opts.hoofColor ?? 0x3d332a, roughness: 0.55 });
                    const hoof = keep(new THREE.Mesh(new THREE.CylinderGeometry(r0 * 0.85, r0 * 1.1, r0 * 1.3, 10), hm));
                    hoof.scale.z = 1.18;
                    hoof.position.set(0, r0 * 0.65, r0 * 0.25);
                    foot.add(hoof);
                    leg.ankleLift = r0 * 1.32;
                } else if (ft === 'webbed') {
                    const wm = keep(new THREE.Mesh(new THREE.SphereGeometry(r0 * 1.2, 10, 8),
                        new THREE.MeshStandardNodeMaterial({ color: opts.footColor ?? 0xd08a2c, roughness: 0.6 })));
                    wm.scale.set(1.7, 0.22, 1.6);
                    wm.position.set(0, r0 * 0.28, r0 * 0.9);
                    foot.add(wm);
                    for (const ta of [-0.8, 0, 0.8]) {   // toe ridges on the fan edge
                        const toe = keep(new THREE.Mesh(new THREE.SphereGeometry(r0 * 0.3, 6, 5), wm.material));
                        toe.position.set(ta * r0 * 1.15, r0 * 0.3, r0 * 2.1 - Math.abs(ta) * r0 * 0.5);
                        foot.add(toe);
                    }
                    leg.ankleLift = r0 * 0.5;
                } else if (ft === 'lizard') {
                    for (const ta of [-0.65, -0.22, 0.22, 0.65]) {   // long splayed toes + claws
                        const toe = new THREE.Mesh(new THREE.SphereGeometry(r0 * 0.32, 6, 5), null);
                        toe.scale.set(0.7, 0.5, 2.6);
                        toe.position.set(Math.sin(ta * 1.1) * r0 * 1.3, r0 * 0.25, Math.cos(ta * 1.1) * r0 * 1.15);
                        toe.rotation.y = -ta * 1.1;
                        foot.add(toe);
                        const claw = keep(new THREE.Mesh(new THREE.ConeGeometry(r0 * 0.12, r0 * 0.45, 5),
                            new THREE.MeshStandardNodeMaterial({ color: 0xe8e0cc, roughness: 0.4 })));
                        claw.position.set(Math.sin(ta * 1.1) * r0 * 2.2, r0 * 0.18, Math.cos(ta * 1.1) * r0 * 1.95);
                        claw.rotation.set(Math.PI / 2, 0, 0);
                        foot.add(claw);
                    }
                    leg.ankleLift = r0 * 0.5;
                } else if (ft === 'talon') {
                    const tm = new THREE.MeshStandardNodeMaterial({ color: opts.footColor ?? 0xc9a02e, roughness: 0.55 });
                    for (const ta of [-0.55, 0, 0.55, Math.PI]) {   // 3 forward toes + 1 back
                        const back = ta === Math.PI;
                        const toe = keep(new THREE.Mesh(new THREE.CylinderGeometry(r0 * 0.16, r0 * 0.22, r0 * (back ? 1.1 : 1.9), 6), tm));
                        toe.rotation.set(Math.PI / 2, 0, -ta * 0.8);
                        toe.position.set(Math.sin(ta) * r0 * 0.7, r0 * 0.22, Math.cos(ta) * r0 * (back ? -0.55 : 0.95));
                        if (back) { toe.rotation.set(Math.PI / 2, 0, 0); toe.position.set(0, r0 * 0.22, -r0 * 0.55); }
                        foot.add(toe);
                        const claw = keep(new THREE.Mesh(new THREE.ConeGeometry(r0 * 0.12, r0 * 0.4, 5), new THREE.MeshStandardNodeMaterial({ color: 0x2c2620, roughness: 0.4 })));
                        claw.rotation.x = Math.PI / 2;
                        claw.position.set(Math.sin(ta) * r0 * 1.35, r0 * 0.16, back ? -r0 * 1.25 : Math.cos(ta) * r0 * 1.85);
                        if (back) claw.rotation.x = -Math.PI / 2;
                        foot.add(claw);
                    }
                    leg.ankleLift = r0 * 0.45;
                } else if (ft === 'shoe' && globalThis.Loft) {
                    const sMat = opts.outfit
                        ? new THREE.MeshStandardNodeMaterial({ color: opts.outfit.shoes ?? 0x221d18, roughness: 0.5 })
                        : null;   // barefoot: body material
                    const sole = Lf * 0.14;
                    const shoe = globalThis.Loft.sweep({
                        path: [V(0, sole * 1.6, -Lf * 0.32), V(0, sole, Lf * 0.02), V(0, sole * 1.15, Lf * 0.42), V(0, sole * 0.8, Lf * 0.64)],
                        profile: globalThis.Loft.ellipse(Lf * 0.19, Lf * 0.15, 10),
                        scale: (tt) => (0.88 + 0.24 * Math.sin(Math.min(1, tt * 1.25) * Math.PI)) * (1 - 0.4 * Math.max(0, tt - 0.7) / 0.3),
                        sections: 10, material: sMat || undefined,
                    });
                    if (sMat) keep(shoe);
                    shoe.castShadow = true;
                    foot.add(shoe);
                    leg.ankleLift = Lf * 0.3;
                } else if (ft === 'ball') {   // legacy v6 sphere foot (debug/back-compat)
                    const ball = new THREE.Mesh(new THREE.SphereGeometry(r0 * 1.35, 10, 8), null);
                    ball.scale.set(1.15, 0.5, 1.6);
                    ball.position.y = -r0 * 0.35; ball.position.z = r0 * 0.5;
                    foot.add(ball);
                    leg.ankleLift = 0;
                } else {   // 'paw' (and the shoe fallback without Loft)
                    const pad = new THREE.Mesh(new THREE.SphereGeometry(r0 * 1.25, 10, 8), null);
                    pad.scale.set(1.2, 0.55, 1.55);
                    pad.position.set(0, r0 * 0.35, r0 * 0.35);
                    foot.add(pad);
                    for (const ta of [-0.6, 0, 0.6]) {   // toe bumps
                        const toe = new THREE.Mesh(new THREE.SphereGeometry(r0 * 0.42, 7, 6), null);
                        toe.position.set(ta * r0 * 0.85, r0 * 0.3, r0 * 1.55 - Math.abs(ta) * r0 * 0.35);
                        foot.add(toe);
                    }
                    leg.ankleLift = r0 * 0.72;
                }
                chain[2].add(foot);
                leg.foot = foot;
            }
            return leg;
        };

        if (stance !== 'serpent') {
            for (let pair = 0; pair < legPairs; pair++) {
                // attach to the spine bone nearest the pair's body position;
                // spiders cluster all coxae on the cephalothorax (front),
                // insects on the thorax (mid)
                const u = legPairs === 1 ? (stance === 'bird' ? 0.45 : 0.12)
                    : stance === 'spider' ? 0.55 + 0.36 * (pair / 3)
                    : stance === 'insect' ? 0.42 + 0.36 * (pair / Math.max(1, legPairs - 1))
                    : 0.15 + 0.7 * (pair / Math.max(1, legPairs - 1));
                const si = Math.round(u * (nSpine - 1));
                const sp = spinePts[si];
                const spread = bodyRad * (opts.legSpread ?? 1.0) * (stance === 'biped' ? 0.55 : 0.95);
                // fanned home stance: front legs reach forward, rear legs back
                // (the spider silhouette) — also used as the bind fan
                const fan = splayed ? (pair - (legPairs - 1) / 2) * legLen * 0.42 : 0;
                for (const side of [-1, 1]) {
                    // roots sit on the LOWER body wall (real legs emerge from
                    // the belly line, not the flank top); arthropod coxae sit
                    // on the SIDE wall at the leg's exact body station
                    const hipLocal = splayed
                        ? V(side * bodyRad * 0.72, sp.y - bodyRad * 0.05, (u - 0.5) * bodyLen)
                        : V(sp.x + side * spread * 0.8, stance === 'biped' ? hipH : sp.y - bodyRad * 0.55, sp.z);
                    const lg = addLimb(spineBones[si], hipLocal, false, side, fan);
                    lg.out = splayed ? legLen * 0.6 : 0.02;
                    lg.fan = fan;
                    legs.push(lg);
                }
            }
            if (stance === 'biped') {
                const si = nSpine - 2;
                const sp = spinePts[si];
                for (const side of [-1, 1]) {
                    // shoulder POINTS: at the top of the torso (not mid-chest —
                    // that embedded the arm roots), proud of the chest wall
                    const shoulder = V(sp.x + side * bodyRad * (fem ? 0.98 : 1.12), hipH + bodyLen * 0.92, sp.z);
                    const arm = addLimb(spineBones[si], shoulder, true, side);
                    arm.isArm = true; arm.side = side;      // anchors: wristL/wristR
                    legs.push(arm);
                    if (opts.hands) {
                        const skinMat = new THREE.MeshStandardNodeMaterial({
                            color: opts.skin ?? opts.color ?? 0xd9a37f, roughness: 0.6 });
                        const hr = bodyRad * 0.34;
                        const hand = new THREE.Group();
                        hand.name = 'hand';                 // parts('hand') — hideable for robot-hand swaps
                        const palm = new THREE.Mesh(new THREE.SphereGeometry(hr, 10, 8), skinMat);
                        palm.scale.set(0.8, 1.15, 0.55);
                        const thumb = new THREE.Mesh(new THREE.SphereGeometry(hr * 0.42, 8, 6), skinMat);
                        thumb.position.set(-side * hr * 0.7, -hr * 0.2, hr * 0.35);
                        hand.add(palm); hand.add(thumb);
                        hand.position.y = -hr * 0.6;
                        arm.ankle.add(hand);
                    }
                }
            }
        }
        // ---- octopus tentacles: radial skinned chains off the mantle base
        // (squid: +2 extra-long feeding tentacles, side fins on the mantle) ----
        const tentacles = [];
        if (stance === 'octopus') {
            const nT = opts.tentacles ?? 8;
            const tLen = (opts.tentacleLength ?? 1.05) * octoScale;
            const nAll = nT + (squid ? 2 : 0);
            for (let ti = 0; ti < nAll; ti++) {
                const feeding = squid && ti >= nT;
                const a = feeding ? (ti - nT === 0 ? 0.35 : -0.35) : (ti / nT) * Math.PI * 2 + 0.12 * jit(0.5);
                const dir = V(Math.sin(a), 0, Math.cos(a));
                const pts = [];
                const drop = [0.15, 0.10, 0.05, 0.035, 0.028];
                const L2t = tLen * (feeding ? 1.9 : 1);
                for (let j = 0; j < 5; j++) {
                    const r = 0.16 * octoScale + L2t * (j / 4);
                    pts.push(V(dir.x * r, drop[j] * octoScale, dir.z * r));
                }
                const radii = [0.105, 0.08, 0.055, 0.034, 0.016].map((r) => r * octoScale * (feeding ? 0.6 : 1));
                const base = allBones.length;
                const chain = boneChain(pts, spineBones[0], allBones);
                pushMesh(skinnedTube(pts, radii, base, { radial: 9, ringsPerSpan: 4, taperStart: false }), 'tentacles');
                tentacles.push({ bones: chain, angle: a, k: ti });
            }
            if (squid) {
                const finM2 = new THREE.MeshStandardNodeMaterial({ color: opts.accent ?? 0x2f4a26, roughness: 0.6, side: THREE.DoubleSide });
                for (const sd of [-1, 1]) {
                    const mfin = new THREE.Mesh(new THREE.SphereGeometry(bodyRad * 0.85, 10, 8), finM2);
                    mfin.scale.set(1.1, 0.5, 0.12);
                    mfin.position.copy(spinePts[nSpine - 1]).add(V(sd * bodyRad * 0.5, 0, 0)).sub(spineBones[nSpine - 1].userData.bindPos);
                    mfin.rotation.z = sd * 0.5;
                    spineBones[nSpine - 1].add(mfin);
                }
            }
        }

        // gait phase offsets by morphology. Quads get TWO gaits: a 4-beat
        // lateral WALK (LH→LF→RH→RF — what real dogs/horses do at low speed;
        // the always-trot was half the robot look) and a diagonal TROT for
        // speed. update() picks by speed and BLENDS phases across ~1s so the
        // transition reads as a natural gait change, not a leg snap.
        const walkers = legs.filter((l) => !l.isArm);
        const setGaitPhases = (mode) => {
            walkers.forEach((l, i) => {
                const pair = Math.floor(i / 2);
                let p;
                if (splayed) p = ((pair % 2) * 0.5 + (l.side < 0 ? 0 : 0.5)) % 1;   // tripod / tetrapod
                else if (walkers.length <= 2) p = l.side < 0 ? 0 : 0.5;             // biped
                else if (walkers.length === 4 && mode === 'walk') p = ((l.side < 0 ? 0 : 0.5) + (pair === 1 ? 0.25 : 0)) % 1;
                else if (walkers.length === 4 && mode === 'gallop') p = ((l.side < 0 ? 0 : 0.12) + (pair === 1 ? 0.5 : 0)) % 1;   // hinds ~together, fronts ~together
                else if (walkers.length === 4) p = ((l.side < 0 ? 0 : 0.5) + pair * 0.5) % 1;   // trot
                else p = ((pair / Math.ceil(walkers.length / 2)) + (l.side < 0 ? 0 : 0.5)) % 1; // wave
                l.phaseTarget = p;
            });
        };
        const gaitFor = (speed) => (opts.gait ?? 'auto') === 'auto'
            ? (speed > 1.6 ? 'gallop' : speed > 0.75 ? 'trot' : 'walk') : opts.gait;
        const initialGait = stance === 'quad' && walkers.length === 4 ? gaitFor(opts.speed ?? 0.5) : 'default';
        setGaitPhases(initialGait);
        walkers.forEach((l) => { l.phase = l.phaseTarget; });

        // ---- head parts: eyes, horns — placed ON the head tube surface in
        // the HEAD'S OWN FRAME (heads point along the neck: diagonal on
        // quads, vertical on bipeds — axis-aligned offsets float off) ----
        const eyeMeshes = [];
        const earPivots = [];
        const antennae = [];
        const eyeAnchors = [];   // bone-local eye centers (sunglasses fit here)
        let eyeSize = 0;
        // TALKING: the hinged lower jaw — { g: pivot Group (child of headBone),
        // axis: local hinge axis, max: open radians }. Built per head type
        // (skull chin, muzzle lower-jaw wedge, beak lower mandible); driven
        // from st.talk in update(). null = this head has no articulable jaw.
        let jawRig = null;
        const makeJawHinge = (hingeLocal, axisLocal, maxOpen) => {
            const g = new THREE.Group();
            g.position.copy(hingeLocal);
            headBone.add(g);
            jawRig = { g, axis: axisLocal.clone().normalize(), max: maxOpen, rest: g.quaternion.clone() };
            return g;
        };
        let crownAnchor = null;  // bone-local hat seat + fit radius
        let crownR = 0;
        const nEyes = opts.eyes ?? (stance === 'snail' ? 0 : 2);   // snail eyes live on the stalks (explicit eyes:2 = extra face eyes, allowed for weirdness)
        const headR = bodyRad * (opts.headScale ?? 0.85);
        // head frame in creature space, from the head bone's bind direction
        const headBind = headBone.userData.bindPos;
        const prevBind = (headBone.parent && headBone.parent.userData && headBone.parent.userData.bindPos)
            ? headBone.parent.userData.bindPos : headBind.clone().add(V(0, 0, -0.2));
        const hFwd = headBind.clone().sub(prevBind).normalize();
        // FACE forward = the horizontal component of the head direction —
        // an upright head (biped) still looks out along body-forward, not up
        const faceFwd = V(hFwd.x, 0, hFwd.z);
        if (faceFwd.lengthSq() < 0.09) faceFwd.set(0, 0, 1); else faceFwd.normalize();
        const hSide = new THREE.Vector3().crossVectors(V(0, 1, 0), faceFwd).normalize();
        const hUp = new THREE.Vector3().crossVectors(faceFwd, hSide).normalize();
        const onHead = (fwd, up, side) => headBind.clone()
            .addScaledVector(faceFwd, headR * fwd).addScaledVector(hUp, headR * up).addScaledVector(hSide, headR * side)
            .sub(headBind);   // → bone-local (bones bind with identity rotation)
        if (neckLen > 0 || stance === 'serpent' || stance === 'octopus' || splayed || stance === 'fish' || stance === 'snail') {
            if (headType === 'skull') {
            // ── sculpted person head ──
            // Coordinates are SKULL-CENTER relative in head radii; the
            // center sits ~0.72R above the neck top. Assumes an upright
            // biped (faceFwd horizontal) — that's the only caller.
            const R = headR;
            const onFace = (f, u, s) => onHead(0.06 + f, 0.66 + u, s);   // skull center ~0.66R above the neck top
            crownAnchor = onFace(-0.05, 0.62, 0); crownR = R * 1.06;
            const skinCol = opts.skin ?? opts.color ?? 0xd9a37f;
            const skinMat = new THREE.MeshStandardNodeMaterial({ color: skinCol, roughness: 0.55 });
            const skull = new THREE.Mesh(new THREE.SphereGeometry(R, 24, 18), skinMat);
            skull.scale.set(0.94, 1.04, 0.98);
            skull.position.copy(onFace(0, 0, 0));
            skull.castShadow = true;
            headBone.add(skull);
            // jaw/chin volume tucked into the lower face (kept mostly inside
            // the skull — a proud jaw sphere reads as a shading blob).
            // HINGED at the TMJ line (just in front of the ears) so say()/
            // talking can flap it — the mouth lip box rides the same hinge.
            const jawHinge = onFace(-0.05, -0.12, 0);
            const jawG = makeJawHinge(jawHinge, hSide, 0.38);
            const jaw = new THREE.Mesh(new THREE.SphereGeometry(R * 0.55, 18, 14), skinMat);
            jaw.scale.set(0.85, 0.72, 0.88);
            jaw.position.copy(onFace(0.22, -0.52, 0)).sub(jawHinge);
            jaw.castShadow = true;
            jawG.add(jaw);
            // dark mouth opening — proud of the face plane but VISIBILITY-
            // driven (the skull surface hides anything recessed, so a static
            // dark box could never show through): hidden closed, shown while
            // the jaw is open. The update loop toggles it via jawRig.inner.
            const innerM = new THREE.Mesh(new THREE.BoxGeometry(R * 0.38, R * 0.18, R * 0.14),
                new THREE.MeshStandardNodeMaterial({ color: 0x220f0e, roughness: 0.9 }));
            innerM.position.copy(onFace(0.86, -0.45, 0));
            innerM.visible = false;
            headBone.add(innerM);
            jawRig.inner = innerM;
            // eyes: small, mostly recessed, with iris + pupil; brows above
            const whiteMat = new THREE.MeshStandardNodeMaterial({ color: 0xf4efe6, roughness: 0.3 });
            const irisMat = new THREE.MeshStandardNodeMaterial({ color: opts.eyeColor ?? 0x4a6d8c, roughness: 0.25 });
            const pupilMat = new THREE.MeshStandardNodeMaterial({ color: 0x101010, roughness: 0.2 });
            const browMat = new THREE.MeshStandardNodeMaterial({
                color: new THREE.Color(opts.hairColor ?? 0x3a2a1a).multiplyScalar(0.7), roughness: 0.8 });
            for (const sd of [-1, 1]) {
                const eye = new THREE.Group();
                const white = new THREE.Mesh(new THREE.SphereGeometry(R * 0.155, 12, 10), whiteMat);
                const iris = new THREE.Mesh(new THREE.SphereGeometry(R * 0.085, 10, 8), irisMat);
                iris.position.copy(faceFwd).multiplyScalar(R * 0.1);
                const pupil = new THREE.Mesh(new THREE.SphereGeometry(R * 0.042, 8, 6), pupilMat);
                pupil.position.copy(faceFwd).multiplyScalar(R * 0.155);
                eye.add(white); eye.add(iris); eye.add(pupil);
                eye.position.copy(onFace(0.8, 0.08, sd * 0.35));
                headBone.add(eye);
                eyeMeshes.push(eye);
                eyeAnchors.push(eye.position.clone()); eyeSize = R * 0.155;
                const brow = new THREE.Mesh(new THREE.BoxGeometry(R * 0.34, R * 0.06, R * 0.07), browMat);
                brow.position.copy(onFace(0.85, 0.26, sd * 0.36));
                brow.rotation.z = -sd * 0.1;
                headBone.add(brow);
            }
            const nose = new THREE.Mesh(new THREE.SphereGeometry(R * 0.13, 10, 8), skinMat);
            nose.scale.set(0.75, 1.05, 0.9);
            nose.position.copy(onFace(0.97, -0.14, 0));
            headBone.add(nose);
            const mouth = new THREE.Mesh(new THREE.BoxGeometry(R * 0.4, R * 0.05, R * 0.05),
                new THREE.MeshStandardNodeMaterial({ color: 0x8a4a44, roughness: 0.6 }));
            mouth.position.copy(onFace(0.88, -0.4, 0)).sub(jawHinge);
            jawG.add(mouth);
            for (const sd of [-1, 1]) {
                const ear = new THREE.Mesh(new THREE.SphereGeometry(R * 0.2, 10, 8), skinMat);
                ear.scale.set(0.3, 0.6, 0.45);
                ear.position.copy(onFace(0, 0.02, sd * 0.92));
                headBone.add(ear);
            }
            if (opts.hair && opts.hair !== 'none') {
                const hairMat = new THREE.MeshStandardNodeMaterial({
                    color: opts.hairColor ?? 0x3a2a1a, roughness: 0.85, side: THREE.DoubleSide });
                if (opts.hair === 'spiky') {
                    for (let hi = 0; hi < 7; hi++) {
                        const aa = (hi / 7) * Math.PI * 2;
                        const spike = new THREE.Mesh(new THREE.ConeGeometry(R * 0.14, R * 0.5, 6), hairMat);
                        spike.position.copy(onFace(Math.cos(aa) * 0.35 - 0.05, 0.95, Math.sin(aa) * 0.4));
                        spike.rotation.set(Math.sin(aa) * 0.45, 0, -Math.cos(aa) * 0.45);
                        headBone.add(spike);
                    }
                } else if (opts.hair === 'mohawk') {
                    // crest row from brow to nape
                    for (let hi = 0; hi < 6; hi++) {
                        const f2 = 0.5 - hi * 0.24;
                        const crest = new THREE.Mesh(new THREE.ConeGeometry(R * 0.16, R * 0.62, 5), hairMat);
                        crest.position.copy(onFace(f2, 0.92 + Math.sin((hi / 5) * Math.PI) * 0.1, 0));
                        crest.rotation.x = -0.15 + hi * 0.1;
                        crest.name = 'hair';
                        headBone.add(crest);
                    }
                } else if (opts.hair === 'curly') {
                    // sphere-cluster afro/curls over the crown
                    for (let hi = 0; hi < 11; hi++) {
                        const aa = (hi / 11) * Math.PI * 2;
                        const ring = hi % 2 ? 0.5 : 0.28;
                        const curl = new THREE.Mesh(new THREE.SphereGeometry(R * (0.3 + (hi % 3) * 0.05), 10, 8), hairMat);
                        curl.position.copy(onFace(Math.cos(aa) * ring - 0.08, 0.78 + (hi % 3) * 0.14, Math.sin(aa) * ring));
                        curl.name = 'hair';
                        headBone.add(curl);
                    }
                } else {
                    // tilted half-dome: rim at temple height, tilted so the
                    // hairline sits ABOVE the brows in front and drops to
                    // the nape behind. Rotationally symmetric — it CANNOT
                    // produce the sideways-crescent bug the old phi-window
                    // shell did (and the rim math keeps it off the face:
                    // rim = cap center height, front +sin(tilt)·R).
                    const cap = new THREE.Mesh(
                        new THREE.SphereGeometry(R * 1.03, 24, 14, 0, Math.PI * 2, 0, Math.PI * 0.5), hairMat);
                    cap.scale.set(1.0, 1.0, 1.04);
                    cap.position.copy(onFace(-0.05, 0.1, 0));
                    cap.rotation.x = -0.35;   // face = +Z here
                    cap.castShadow = true;
                    cap.name = 'hair';
                    headBone.add(cap);
                    if (opts.hair === 'long') {
                        // flowing back panel down past the shoulders
                        const back2 = new THREE.Mesh(new THREE.SphereGeometry(R * 0.95, 16, 12), hairMat);
                        back2.scale.set(0.85, 1.55, 0.42);
                        back2.position.copy(onFace(-0.78, -0.55, 0));
                        back2.castShadow = true;
                        back2.name = 'hair';
                        headBone.add(back2);
                    } else if (opts.hair === 'bob') {
                        // deeper sides down to the jawline
                        for (const sd of [-1, 1]) {
                            const side2 = new THREE.Mesh(new THREE.SphereGeometry(R * 0.62, 12, 10), hairMat);
                            side2.scale.set(0.42, 1.05, 0.9);
                            side2.position.copy(onFace(-0.25, -0.28, sd * 0.85));
                            side2.name = 'hair';
                            headBone.add(side2);
                        }
                    } else if (opts.hair === 'bun') {
                        const bun = new THREE.Mesh(new THREE.SphereGeometry(R * 0.38, 12, 10), hairMat);
                        bun.position.copy(onFace(-0.85, 0.72, 0));
                        bun.name = 'hair';
                        headBone.add(bun);
                    } else if (opts.hair === 'ponytail') {
                        const band4 = new THREE.Mesh(new THREE.TorusGeometry(R * 0.16, R * 0.06, 8, 12),
                            new THREE.MeshStandardNodeMaterial({ color: opts.hairBand ?? 0x8a2a3a, roughness: 0.6 }));
                        band4.position.copy(onFace(-0.85, 0.55, 0));
                        band4.rotation.x = 1.2;
                        headBone.add(band4);
                        // tail: two segments swinging down-back + a tip
                        const p1 = new THREE.Mesh(new THREE.SphereGeometry(R * 0.24, 10, 8), hairMat);
                        p1.scale.set(0.8, 1.5, 0.8);
                        p1.position.copy(onFace(-1.05, 0.15, 0));
                        const p2 = new THREE.Mesh(new THREE.SphereGeometry(R * 0.17, 10, 8), hairMat);
                        p2.scale.set(0.7, 1.6, 0.7);
                        p2.position.copy(onFace(-1.15, -0.45, 0));
                        p1.name = p2.name = 'hair';
                        headBone.add(p1); headBone.add(p2);
                    }
                }
            }
            } else {
            // ── animal face ──
            const isBird = !!(opts.beak ?? (stance === 'bird'));
            const skinCol = opts.skin ?? opts.color ?? 0xd9a37f;
            const darkMat = new THREE.MeshStandardNodeMaterial({ color: 0x1e1712, roughness: 0.4 });
            const bodyToneMat = new THREE.MeshStandardNodeMaterial({ color: opts.color ?? 0x6a8f4a, roughness: 0.65 });
            if (opts.map) { bodyToneMat.map = opts.map; bodyToneMat.color = new THREE.Color(0xffffff); }   // parts match a textured body
            // tilted heads (quad neck diagonal) seat the hat further back so
            // the brim doesn't ride over the eyes
            crownAnchor = onHead(-0.05 - Math.max(0, hFwd.y) * 0.45, 0.62 + Math.max(0, hFwd.y) * 0.12, 0);
            crownR = headR * 1.0;
            // muzzle/snout (default for quads): the single biggest
            // ball-with-eyes → animal upgrade
            const muzzleOpt = opts.muzzle ?? (stance === 'quad');
            let mL = 0;
            if (muzzleOpt && !isBird && stance !== 'octopus' && !splayed) {
                mL = typeof muzzleOpt === 'object' ? (muzzleOpt.length ?? 1.0) : (muzzleOpt === true ? 1.0 : muzzleOpt);
                const mW = headR * (typeof muzzleOpt === 'object' ? (muzzleOpt.width ?? 0.6) : 0.6);
                let snout;
                if (globalThis.Loft) {
                    snout = globalThis.Loft.sweep({
                        path: [onHead(0.4, -0.02, 0), onHead(0.4 + mL * 0.55, -0.1, 0), onHead(0.4 + mL, -0.16, 0)],
                        profile: globalThis.Loft.ellipse(mW, mW * 0.82, 12),
                        scale: (tt) => 1 - 0.42 * tt, sections: 8, material: bodyToneMat,
                    });
                } else {
                    snout = new THREE.Mesh(new THREE.SphereGeometry(mW, 12, 10), bodyToneMat);
                    snout.scale.set(1, 0.85, (mL * headR) / mW);
                    snout.position.copy(onHead(0.4 + mL * 0.5, -0.08, 0));
                }
                snout.castShadow = true;
                headBone.add(snout);
                // nose pad on the snout tip + mouth slit underneath — or a
                // star-nose: ring of pink feeler cones (star-nosed mole)
                if (opts.nose === 'star') {
                    const starMat = new THREE.MeshStandardNodeMaterial({ color: 0xe89ab8, roughness: 0.55 });
                    const tip = onHead(0.4 + mL + 0.02, -0.05, 0);
                    for (let a2 = 0; a2 < 10; a2++) {
                        const th = (a2 / 10) * Math.PI * 2;
                        const dir = new THREE.Vector3().addScaledVector(hUp, Math.cos(th)).addScaledVector(hSide, Math.sin(th))
                            .addScaledVector(faceFwd, 0.65).normalize();
                        const feeler = new THREE.Mesh(new THREE.ConeGeometry(mW * 0.13, mW * 0.55, 5), starMat);
                        feeler.quaternion.setFromUnitVectors(UP, dir);
                        feeler.position.copy(tip).addScaledVector(dir, mW * 0.3);
                        feeler.name = 'starnose';
                        headBone.add(feeler);
                    }
                } else {
                    const nosePad = new THREE.Mesh(new THREE.SphereGeometry(mW * 0.42, 10, 8), darkMat);
                    nosePad.scale.set(1.05, 0.72, 0.8);
                    nosePad.position.copy(onHead(0.4 + mL + 0.06, -0.05, 0));
                    nosePad.name = 'nose';
                    headBone.add(nosePad);
                }
                if (opts.buckTeeth) {
                    // two flat rodent incisors under the nose
                    const bMat = new THREE.MeshStandardNodeMaterial({ color: 0xf4eed8, roughness: 0.35 });
                    for (const sd of [-1, 1]) {
                        const tooth = new THREE.Mesh(new THREE.BoxGeometry(headR * 0.14, headR * 0.26, headR * 0.06), bMat);
                        tooth.position.copy(onHead(0.4 + mL * 0.95, -0.32, sd * 0.09));
                        tooth.name = 'buckTooth';
                        headBone.add(tooth);
                    }
                }
                // (the old static mouth-slit box is superseded by the hinged
                // jaw below — a leftover slit floats between the jaw pieces
                // the moment the mouth opens)
                // hinged LOWER JAW (talking): a flattened wedge tucked under
                // the snout, pivoting at the snout base. Closed, it reads as
                // the animal's under-jaw; say()/talking swings it down and
                // reveals a dark mouth interior.
                const jHinge = onHead(0.42, -0.3, 0);
                const jG = makeJawHinge(jHinge, hSide, 0.42);
                const jRel = (f, u) => new THREE.Vector3()
                    .addScaledVector(faceFwd, headR * f).addScaledVector(hUp, headR * u);
                const lowerJaw = globalThis.Loft ? globalThis.Loft.sweep({
                    path: [jRel(0, 0), jRel(mL * 0.45, -0.05), jRel(mL * 0.78, -0.06)],
                    profile: globalThis.Loft.ellipse(mW * 0.78, mW * 0.36, 10),
                    scale: (tt) => 1 - 0.45 * tt, sections: 6, material: bodyToneMat,
                }) : (() => {
                    const m = new THREE.Mesh(new THREE.SphereGeometry(mW * 0.7, 10, 8), bodyToneMat);
                    m.scale.set(1, 0.45, (mL * headR * 0.8) / (mW * 0.7));
                    m.position.copy(jRel(mL * 0.4, -0.05));
                    return m;
                })();
                lowerJaw.castShadow = true;
                jG.add(lowerJaw);
                const innerJ = new THREE.Mesh(
                    new THREE.BoxGeometry(mW * 1.05, headR * 0.1, mL * headR * 0.62), darkMat);
                innerJ.position.copy(onHead(0.42 + mL * 0.36, -0.34, 0));
                innerJ.visible = false;                       // shown while the jaw is open
                headBone.add(innerJ);
                jawRig.inner = innerJ;
                if (opts.whiskers) {
                    // three thin whisker rods per cheek, fanned
                    const wMat = new THREE.MeshStandardNodeMaterial({ color: 0xe8e2d2, roughness: 0.4 });
                    for (const sd of [-1, 1]) for (let wi = 0; wi < 3; wi++) {
                        const wh = new THREE.Mesh(new THREE.CylinderGeometry(headR * 0.008, headR * 0.013, headR * 0.95, 4), wMat);
                        wh.rotation.set(0, sd * (wi - 1) * 0.22, sd * (Math.PI / 2 - (wi - 1) * 0.15));
                        wh.position.copy(onHead(0.4 + mL * 0.78, -0.12 - wi * 0.05, sd * 0.3))
                            .addScaledVector(hSide, sd * headR * 0.35);
                        headBone.add(wh);
                    }
                }
                if (opts.fangs) {
                    const fangMat = new THREE.MeshStandardNodeMaterial({ color: 0xf2ecd8, roughness: 0.35 });
                    for (const sd of [-1, 1]) {
                        const fang = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.06, headR * 0.24, 6), fangMat);
                        fang.rotation.x = Math.PI;
                        fang.position.copy(onHead(0.4 + mL * 0.8, -0.48, sd * 0.3));
                        headBone.add(fang);
                    }
                }
            }
            if (stance === 'snail') {
                // eye STALKS: two thin swaying stalks with eyeballs at the
                // tips (they ride the antennae animation)
                const stMat = new THREE.MeshStandardNodeMaterial({ color: opts.color ?? 0x8a7a5a, roughness: 0.7 });
                for (const sd of [-1, 1]) {
                    const piv = new THREE.Group();
                    piv.position.copy(onHead(0.35, 0.35, sd * 0.35));
                    const stalk = new THREE.Mesh(new THREE.CylinderGeometry(headR * 0.07, headR * 0.11, headR * 1.15, 6), stMat);
                    stalk.position.y = headR * 0.55;
                    stalk.rotation.z = -sd * 0.28;
                    piv.add(stalk);
                    const ball = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.2, 10, 8),
                        new THREE.MeshStandardNodeMaterial({ color: 0xf2ede0, roughness: 0.3 }));
                    ball.position.set(sd * headR * 0.3, headR * 1.15, 0);
                    const pup = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.09, 8, 6),
                        new THREE.MeshStandardNodeMaterial({ color: 0x14100c, roughness: 0.25 }));
                    pup.position.set(sd * headR * 0.3, headR * 1.18, headR * 0.14);
                    piv.add(ball); piv.add(pup);
                    piv.userData.k = sd * 1.4;
                    piv.name = 'eyestalk';
                    headBone.add(piv);
                    antennae.push(piv);
                    eyeAnchors.push(new THREE.Vector3().copy(piv.position).add(V(sd * headR * 0.3, headR * 1.15, 0))); eyeSize = headR * 0.2;
                }
            }
            if (opts.antennae && stance !== 'insect') {
                // antennae on ANYTHING — metal rods with glowing ball tips
                // when robot (the 'robot antenna' ask), dark chitin otherwise
                const isBot = robotHead;
                const aMat = isBot
                    ? new THREE.MeshStandardNodeMaterial({ color: 0x8a949e, roughness: 0.3, metalness: 0.85 })
                    : new THREE.MeshStandardNodeMaterial({ color: 0x2a2118, roughness: 0.6 });
                for (const sd of [-1, 1]) {
                    const piv = new THREE.Group();
                    piv.position.copy(onHead(0.15, 0.6, sd * 0.3));
                    const rod = new THREE.Mesh(new THREE.CylinderGeometry(headR * 0.035, headR * 0.05, headR * 1.1, 5), aMat);
                    rod.position.y = headR * 0.5;
                    rod.rotation.z = -sd * 0.35;
                    piv.add(rod);
                    const tip = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.11, 8, 6),
                        isBot ? new THREE.MeshStandardNodeMaterial({ color: 0x000000, emissive: new THREE.Color(opts.eyeColor ?? 0xff3030), emissiveIntensity: 2.0 })
                              : aMat);
                    tip.position.set(sd * headR * 0.38, headR * 1.0, 0);
                    piv.add(tip);
                    piv.userData.k = sd;
                    piv.name = 'antenna';
                    headBone.add(piv);
                    antennae.push(piv);
                }
            }
            if (opts.gills) {
                // axolotl gill stalks: three feathery pink spears per side
                const gMat2 = new THREE.MeshStandardNodeMaterial({ color: opts.gillColor ?? 0xe88aa8, roughness: 0.6 });
                for (const sd of [-1, 1]) for (let gi = 0; gi < 3; gi++) {
                    const gill = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.09, headR * (0.75 - gi * 0.12), 6), gMat2);
                    gill.position.copy(onHead(-0.05 - gi * 0.22, 0.35 + gi * 0.08, sd * 0.72));
                    gill.rotation.set(-0.6, 0, -sd * (0.9 + gi * 0.25));
                    gill.name = 'gill';
                    headBone.add(gill);
                }
            }
            if (opts.trunk) {
                // elephant trunk: lofted curve from the face, drooping
                // forward-down, curling at the tip; sways in update()
                const tLen2 = headR * (typeof opts.trunk === 'object' ? (opts.trunk.length ?? 2.6) : 2.6);
                const trunkPiv = new THREE.Group();
                trunkPiv.position.copy(onHead(0.75, -0.05, 0));
                let tr2;
                if (globalThis.Loft) {
                    const pth = [];
                    for (const [f2, u2] of [[0, 0], [0.35, -0.28], [0.55, -0.62], [0.62, -0.95], [0.72, -1.12]]) {
                        pth.push(new THREE.Vector3().addScaledVector(faceFwd, tLen2 * f2).addScaledVector(hUp, tLen2 * u2));
                    }
                    tr2 = globalThis.Loft.sweep({ path: pth, profile: globalThis.Loft.circle(headR * 0.32, 10),
                        scale: (tt) => 1 - 0.62 * tt, sections: 14, material: bodyToneMat });
                } else {
                    tr2 = new THREE.Mesh(new THREE.CylinderGeometry(headR * 0.14, headR * 0.3, tLen2, 8), bodyToneMat);
                    tr2.position.set(0, -tLen2 * 0.4, tLen2 * 0.25);
                    tr2.rotation.x = 0.5;
                }
                tr2.castShadow = true;
                trunkPiv.add(tr2);
                headBone.add(trunkPiv);
                var trunkG = trunkPiv;
            }
            if (opts.tusks) {
                // boar tusks: curl forward-up-out from the lower jaw
                const tuskMat = new THREE.MeshStandardNodeMaterial({ color: 0xe9dfc8, roughness: 0.35 });
                const tl = headR * (opts.tuskLength ?? 1.0);
                for (const sd of [-1, 1]) {
                    let tusk;
                    const b0 = onHead(0.45 + mL * 0.7, -0.42, sd * 0.5);
                    if (globalThis.Loft) {
                        const pth = [];
                        for (const [f2, u2, s2] of [[0, 0, 0], [0.35, 0.18, 0.12], [0.6, 0.55, 0.28], [0.68, 0.95, 0.42]]) {
                            pth.push(new THREE.Vector3().copy(b0)
                                .addScaledVector(faceFwd, tl * f2).addScaledVector(hUp, tl * u2).addScaledVector(hSide, sd * tl * s2));
                        }
                        tusk = globalThis.Loft.sweep({ path: pth, profile: globalThis.Loft.circle(headR * 0.09, 8),
                            scale: (tt) => 1 - 0.75 * tt, sections: 10, material: tuskMat });
                    } else {
                        tusk = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.09, tl, 6), tuskMat);
                        tusk.position.copy(b0); tusk.rotation.x = -Math.PI / 3;
                    }
                    tusk.castShadow = true;
                    headBone.add(tusk);
                }
            }
            if (stance === 'insect') {
                // compound eyes + antennae + mandibles
                const cMat = new THREE.MeshStandardNodeMaterial({ color: opts.eyeColor ?? 0x2a1f0e, roughness: 0.15, metalness: 0.25 });
                for (const sd of [-1, 1]) {
                    const ce = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.5, 14, 10), cMat);
                    ce.scale.set(0.7, 0.9, 0.8);
                    ce.position.copy(onHead(0.45, 0.18, sd * 0.62));
                    headBone.add(ce);
                    eyeAnchors.push(ce.position.clone()); eyeSize = headR * 0.42;
                }
                const antMat = new THREE.MeshStandardNodeMaterial({ color: 0x2a2118, roughness: 0.6 });
                for (const sd of [-1, 1]) {
                    const piv = new THREE.Group();
                    piv.position.copy(onHead(0.5, 0.5, sd * 0.3));
                    let ant;
                    if (globalThis.Loft) {
                        ant = globalThis.Loft.sweep({
                            path: [V(0, 0, 0), V(sd * headR * 0.25, headR * 0.75, headR * 0.55),
                                   V(sd * headR * 0.55, headR * 1.3, headR * 0.35), V(sd * headR * 0.8, headR * 1.6, -headR * 0.1)],
                            profile: globalThis.Loft.circle(headR * 0.05, 6),
                            scale: (tt) => 1 - 0.5 * tt, sections: 10, material: antMat });
                    } else {
                        ant = new THREE.Mesh(new THREE.CylinderGeometry(headR * 0.03, headR * 0.05, headR * 1.5, 5), antMat);
                        ant.position.set(sd * headR * 0.2, headR * 0.7, headR * 0.15);
                        ant.rotation.z = -sd * 0.4;
                    }
                    piv.userData.k = sd * 1.3;
                    piv.add(ant);
                    headBone.add(piv);
                    antennae.push(piv);
                }
                for (const sd of [-1, 1]) {
                    const md = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.08, headR * 0.3, 5), antMat);
                    md.position.copy(onHead(0.85, -0.25, sd * 0.22));
                    md.rotation.set(Math.PI / 2, 0, -sd * 0.5);
                    headBone.add(md);
                }
            } else if (stance === 'spider') {
                // eight-eye cluster + chelicerae fangs
                const sMat = new THREE.MeshStandardNodeMaterial({ color: 0x101010, roughness: 0.12 });
                for (const [s2, u2, r2] of [[0.22, 0.3, 0.5], [-0.22, 0.3, 0.5], [0.52, 0.22, 0.34], [-0.52, 0.22, 0.34],
                                            [0.3, 0.04, 0.28], [-0.3, 0.04, 0.28], [0.72, 0.08, 0.24], [-0.72, 0.08, 0.24]]) {
                    const se = new THREE.Mesh(new THREE.SphereGeometry(headR * r2 * 0.44, 8, 6), sMat);
                    se.position.copy(onHead(0.72, u2, s2 * 0.75));
                    headBone.add(se);
                    if (Math.abs(s2) < 0.3) { eyeAnchors.push(se.position.clone()); eyeSize = headR * 0.3; }
                }
                const chMat = new THREE.MeshStandardNodeMaterial({ color: 0x241a12, roughness: 0.5 });
                for (const sd of [-1, 1]) {
                    const ch = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.12, headR * 0.45, 6), chMat);
                    ch.rotation.x = Math.PI;
                    ch.position.copy(onHead(0.72, -0.35, sd * 0.2));
                    headBone.add(ch);
                }
            } else {
            for (let e = 0; e < nEyes; e++) {
                const a = (nEyes === 1) ? 0 : (-1 + 2 * (e / (nEyes - 1)));
                // vertebrate eye: smaller white, colored iris, pupil (slit
                // option), plus a body-toned upper LID hooding the ball —
                // the lid is what makes it read alive instead of googly
                const eye = new THREE.Group();
                const eR = headR * 0.2;
                const white = new THREE.Mesh(new THREE.SphereGeometry(eR, 12, 10),
                    robotHead
                        ? new THREE.MeshStandardNodeMaterial({ color: 0x23282e, roughness: 0.3, metalness: 0.7 })
                        : new THREE.MeshStandardNodeMaterial({ color: 0xf2ede0, roughness: 0.3 }));
                const iris = new THREE.Mesh(new THREE.SphereGeometry(eR * 0.62, 10, 8),
                    robotHead
                        ? new THREE.MeshStandardNodeMaterial({ color: 0x000000, roughness: 0.3,
                            emissive: new THREE.Color(opts.eyeColor ?? 0x33ffd0), emissiveIntensity: 2.2 })
                        : new THREE.MeshStandardNodeMaterial({ color: opts.eyeColor ?? 0x8a6a20, roughness: 0.25 }));
                iris.position.copy(faceFwd).multiplyScalar(eR * 0.55);
                const pupil = new THREE.Mesh(new THREE.SphereGeometry(eR * 0.34, 8, 6),
                    new THREE.MeshStandardNodeMaterial({ color: 0x0e0b08, roughness: 0.2 }));
                pupil.position.copy(faceFwd).multiplyScalar(eR * 0.82);
                if (robotHead) pupil.visible = false;   // the LED iris IS the eye
                if ((opts.pupil ?? (stance === 'serpent' ? 'slit' : 'round')) === 'slit') pupil.scale.set(0.38, 1.25, 1);
                eye.add(white); eye.add(iris); eye.add(pupil);
                // eyelids: 0 = wide awake (no lid), 1 = heavy-lidded. The lid
                // rides the eye group, so blinking still works at any value.
                const lidAmt = opts.eyelids ?? (stance === 'fish' ? 0 : 0.3);
                if (stance !== 'serpent' && lidAmt > 0) {   // snakes have spectacles, not lids
                    const lid = new THREE.Mesh(new THREE.SphereGeometry(eR * 1.12, 10, 6, 0, Math.PI * 2, 0, Math.PI * (0.2 + lidAmt * 0.3)), bodyToneMat);
                    lid.quaternion.setFromAxisAngle(hSide, 0.2 + lidAmt * 0.6);   // hood tips toward the face
                    eye.add(lid);
                }
                const hasM = muzzleOpt && mL > 0;
                // fish have SIDE eyes seated back where the head is still
                // fat — the front-bulge anchor floats off the tapered nose
                eye.position.copy(onHead(hasM ? 0.5 : (stance === 'octopus' ? 0.82 : stance === 'snail' ? 0.3 : stance === 'fish' ? 0.05 : 0.7),
                    hasM ? 0.34 : (stance === 'octopus' ? 0.2 : stance === 'snail' ? 0.28 : stance === 'fish' ? 0.16 : 0.16),
                    a * (hasM ? 0.58 : stance === 'fish' ? 0.52 : 0.5)));
                if (stance === 'fish') {   // look sideways, mostly embedded
                    iris.position.copy(hSide).multiplyScalar(a * eR * 0.55);
                    pupil.position.copy(hSide).multiplyScalar(a * eR * 0.82);
                }
                headBone.add(eye);
                eyeMeshes.push(eye);
                eyeAnchors.push(eye.position.clone()); eyeSize = eR;
            }
            }
            if (opts.nose && !(muzzleOpt && mL > 0)) {
                const nose = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.17, 10, 8),
                    new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(skinCol).multiplyScalar(0.88), roughness: 0.6 }));
                nose.scale.set(0.85, 0.8, 1.15);
                nose.position.copy(onHead(1.0, -0.05, 0));
                headBone.add(nose);
            }
            if (opts.mouth && !(muzzleOpt && mL > 0)) {
                const mouth = new THREE.Mesh(new THREE.BoxGeometry(headR * 0.5, headR * 0.07, headR * 0.06),
                    new THREE.MeshStandardNodeMaterial({ color: 0x5a2c28, roughness: 0.6 }));
                mouth.position.copy(onHead(0.82, -0.48, 0));
                headBone.add(mouth);
            }
            if (opts.hair && opts.hair !== 'none') {
                const hairMat = new THREE.MeshStandardNodeMaterial({ color: opts.hairColor ?? 0x3a2a1a, roughness: 0.85 });
                if (opts.hair === 'spiky') {
                    for (let hi = 0; hi < 7; hi++) {
                        const aa = (hi / 7) * Math.PI * 2;
                        const spike = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.14, headR * 0.55, 6), hairMat);
                        spike.position.copy(onHead(-0.15 + Math.cos(aa) * 0.3, 0.72, Math.sin(aa) * 0.35));
                        spike.rotation.set(Math.sin(aa) * 0.5, 0, -Math.cos(aa) * 0.5);
                        headBone.add(spike);
                    }
                } else {
                    // cap: a hemisphere shell over the crown, nudged back
                    // top-back shell: hairline stays ABOVE the brow — a
                    // centered dome wraps the face (user: 'hair is not a dome
                    // that goes behind our eyes into our skull')
                    // hair is NOT a dome — it's a WIG SHELL: top + sides +
                    // back of the skull down to the nape, with an open FACE
                    // WINDOW at the front (partial-phi sphere; the un-swept
                    // phi range is the window)
                    const win = 2.0;   // face window ≈115°
                    const cap = new THREE.Mesh(
                        new THREE.SphereGeometry(headR * 1.07, 18, 12,
                            0, Math.PI * 2 - win, 0, Math.PI * 0.68), hairMat);
                    cap.position.copy(onHead(-0.02, 0.06, 0));
                    // rotate so the window faces the face (phi 0 sits at +X;
                    // center the gap on the face-forward axis)
                    cap.rotation.y = Math.atan2(faceFwd.x, faceFwd.z) + Math.PI / 2 + win / 2;
                    headBone.add(cap);
                }
            }
            const earOpt = opts.ears ?? (stance === 'quad' ? 'point' : 0);
            if (earOpt && stance !== 'serpent' && !splayed) {
                // ear styles: 'point' (perked cone + inner ear), 'flop'
                // (hanging flap), 'round' (bear disc). Each sits on a PIVOT
                // so update() can flick one occasionally — free liveliness.
                const style = typeof earOpt === 'string' ? earOpt : 'point';
                const earS = opts.earScale ?? 1;   // elephants ≈ 2+
                const innerMat = new THREE.MeshStandardNodeMaterial({ color: 0x6b4a44, roughness: 0.7 });
                for (const sd of [-1, 1]) {
                    const piv = new THREE.Group();
                    piv.scale.setScalar(earS);
                    // seated INTO the skull top (0.66 floated on some head
                    // shapes — user-caught) + a base ball to fill any gap
                    piv.position.copy(onHead(-0.12, 0.56, sd * 0.5));
                    const base = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.17, 8, 6), bodyToneMat);
                    piv.add(base);
                    let ear;
                    if (style === 'round') {
                        ear = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.34, 10, 8), bodyToneMat);
                        ear.scale.set(0.85, 0.85, 0.3);
                        ear.position.y = headR * 0.18;
                    } else if (style === 'flop') {
                        ear = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.3, 10, 8), bodyToneMat);
                        ear.scale.set(0.55, 1.15, 0.28);
                        ear.position.set(sd * headR * 0.16, -headR * 0.06, 0);
                        ear.rotation.z = sd * 1.1;
                    } else {   // 'point'
                        ear = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.22, headR * 0.5, 7), bodyToneMat);
                        ear.position.y = headR * 0.22;
                        const inner = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.12, headR * 0.3, 6), innerMat);
                        inner.position.set(0, -headR * 0.04, headR * 0.07);
                        ear.add(inner);
                    }
                    ear.castShadow = true;
                    piv.add(ear);
                    piv.rotation.z = -sd * 0.28;   // cant outward
                    headBone.add(piv);
                    earPivots.push(piv);
                }
            } else if (earOpt && stance === 'biped') {
                // generic biped tube-head keeps simple side ears
                for (const sd of [-1, 1]) {
                    const ear = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.28, 10, 8),
                        new THREE.MeshStandardNodeMaterial({ color: skinCol, roughness: 0.6 }));
                    ear.scale.set(0.35, 0.8, 0.55);
                    ear.position.copy(onHead(0.05, 0.02, sd * 0.98));
                    headBone.add(ear);
                }
            }
            if (opts.beak ?? (stance === 'bird')) {
                // two-mandible beak: upper with a downward hook at the tip,
                // shorter lower fitted beneath — reads bird from any angle
                const bkMat = new THREE.MeshStandardNodeMaterial({ color: opts.beakColor ?? 0xd8a02a, roughness: 0.45 });
                const bkLow = new THREE.MeshStandardNodeMaterial({
                    color: new THREE.Color(opts.beakColor ?? 0xd8a02a).multiplyScalar(0.72), roughness: 0.5 });
                const bl = headR * 1.4 * (typeof opts.beak === 'number' ? opts.beak : 1);
                const hook = (opts.beakHook ?? 0.35);
                const bw = opts.beakWidth ?? 1;   // duck/platypus wide bill ≈ 1.6+
                if (globalThis.Loft) {
                    const b0 = onHead(0.7, 0.02, 0);
                    const upper = globalThis.Loft.sweep({
                        path: [new THREE.Vector3().copy(b0),
                               new THREE.Vector3().copy(b0).addScaledVector(faceFwd, bl * 0.6).addScaledVector(hUp, -headR * 0.02),
                               new THREE.Vector3().copy(b0).addScaledVector(faceFwd, bl * 0.92).addScaledVector(hUp, -headR * 0.1 * hook * 2),
                               new THREE.Vector3().copy(b0).addScaledVector(faceFwd, bl).addScaledVector(hUp, -headR * 0.3 * hook * 2)],
                        profile: globalThis.Loft.ellipse(headR * 0.28 * bw, headR * 0.2 / Math.max(1, bw * 0.75), 10),
                        scale: (t) => 1 - 0.85 * t * t, sections: 12, material: bkMat,
                    });
                    upper.castShadow = true;
                    headBone.add(upper);
                    // lower mandible rides a hinge at the beak base so
                    // say()/talking opens the bill
                    const l0 = onHead(0.7, -0.18, 0);
                    const bkG = makeJawHinge(l0, hSide, 0.5);
                    const lower = globalThis.Loft.sweep({
                        path: [new THREE.Vector3(),
                               new THREE.Vector3().addScaledVector(faceFwd, bl * 0.42).addScaledVector(hUp, headR * 0.01),
                               new THREE.Vector3().addScaledVector(faceFwd, bl * 0.68).addScaledVector(hUp, headR * 0.02)],
                        profile: globalThis.Loft.ellipse(headR * 0.24 * bw, headR * 0.14 / Math.max(1, bw * 0.75), 8),
                        scale: (t) => 1 - 0.8 * t, sections: 8, material: bkLow,
                    });
                    lower.castShadow = true;
                    bkG.add(lower);
                } else {
                    const beak = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.26, bl, 8), bkMat);
                    beak.position.copy(onHead(1.1, -0.05, 0));
                    beak.rotation.x = Math.PI / 2;
                    beak.castShadow = true;
                    headBone.add(beak);
                }
            }
            if (stance === 'serpent') {
                // forked tongue — hidden at scale.z≈0, flicked in update()
                const tMat = new THREE.MeshStandardNodeMaterial({ color: 0xc22743, roughness: 0.5 });
                const tongue = new THREE.Group();
                for (const sd of [-1, 1]) {
                    const fork = new THREE.Mesh(
                        new THREE.CylinderGeometry(headR * 0.028, headR * 0.05, headR * 0.85, 5), tMat);
                    fork.rotation.order = 'YXZ';
                    fork.rotation.set(Math.PI / 2, sd * 0.16, 0);   // lie along +Z, forked apart
                    fork.position.set(sd * headR * 0.09, 0, headR * 0.45);
                    tongue.add(fork);
                }
                tongue.position.copy(onHead(0.95, -0.25, 0));
                tongue.scale.set(1, 1, 0.001);
                headBone.add(tongue);
                var tongueG = tongue;
            }
            }   // end tube-head branch
            const hornMat = new THREE.MeshStandardNodeMaterial({ color: opts.hornColor ?? 0xd8cdb4, roughness: 0.5 });
            const hornStyle = opts.hornStyle ?? 'spike';   // 'spike' | 'ram' | 'antler'
            for (let hIdx = 0; hIdx < (opts.horns ?? 0); hIdx++) {
                const a = (opts.horns === 1) ? 0 : (-0.5 + (hIdx / (opts.horns - 1)));
                const sd2 = a === 0 ? 1 : Math.sign(a);
                let horn;
                const len = headR * 1.25, hr = headR * 0.16;
                if (globalThis.Loft && hornStyle === 'ram') {
                    // spiral curl beside the head: up → back → down → forward
                    const ctr = new THREE.Vector3().copy(onHead(-0.22, 0.5, sd2 * 0.6));
                    const pth = [];
                    for (let k2 = 0; k2 <= 8; k2++) {
                        const th = -0.6 + (k2 / 8) * 3.7;
                        const rr = headR * (0.52 - 0.03 * k2);
                        pth.push(new THREE.Vector3().copy(ctr)
                            .addScaledVector(hUp, Math.cos(th) * rr)
                            .addScaledVector(faceFwd, -Math.sin(th) * rr)
                            .addScaledVector(hSide, sd2 * headR * 0.05 * k2));
                    }
                    horn = globalThis.Loft.sweep({ path: pth, profile: globalThis.Loft.circle(headR * 0.19, 8),
                        scale: (tt) => 1 - 0.8 * tt, sections: 18, material: hornMat });
                } else if (globalThis.Loft && hornStyle === 'antler') {
                    // main beam up-back-out, tines forking forward-up
                    const base = onHead(-0.12, 0.55, sd2 * 0.5);
                    const beamPts = [];
                    for (const [f2, u2, s2] of [[0, 0, 0], [-0.2, 0.6, 0.25], [-0.45, 1.15, 0.55], [-0.5, 1.7, 0.85]]) {
                        beamPts.push(new THREE.Vector3().copy(base)
                            .addScaledVector(faceFwd, len * f2).addScaledVector(hUp, len * u2).addScaledVector(hSide, sd2 * len * s2));
                    }
                    horn = globalThis.Loft.sweep({ path: beamPts, profile: globalThis.Loft.circle(headR * 0.1, 7),
                        scale: (tt) => 1 - 0.6 * tt, sections: 12, material: hornMat });
                    const tineDir = new THREE.Vector3().copy(faceFwd).multiplyScalar(0.75).addScaledVector(hUp, 0.66).normalize();
                    for (const bt of [0.38, 0.68, 0.92]) {
                        const seg = Math.min(2, Math.floor(bt * 3)), fr = bt * 3 - seg;
                        const bp = new THREE.Vector3().copy(beamPts[seg]).lerp(beamPts[seg + 1], fr);
                        const tine = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.055, len * 0.5 * (1 - bt * 0.4), 6), hornMat);
                        tine.quaternion.setFromUnitVectors(UP, tineDir);
                        tine.position.copy(bp).addScaledVector(tineDir, len * 0.22);
                        tine.castShadow = true;
                        headBone.add(tine);
                    }
                } else if (hornStyle === 'moose') {
                    // palmate antler: short beam then a flat PALM blade with
                    // finger tines along its edge
                    const base = onHead(-0.15, 0.5, sd2 * 0.55);
                    const beam = new THREE.Mesh(new THREE.CylinderGeometry(headR * 0.09, headR * 0.12, headR * 0.5, 8), hornMat);
                    beam.position.copy(base).addScaledVector(hUp, headR * 0.2).addScaledVector(hSide, sd2 * headR * 0.2);
                    beam.rotation.z = -sd2 * 0.9;
                    headBone.add(beam);
                    const palm = new THREE.Mesh(new THREE.SphereGeometry(headR * 0.75, 12, 8), hornMat);
                    palm.scale.set(1.25, 0.55, 0.16);
                    palm.position.copy(base).addScaledVector(hUp, headR * 0.62).addScaledVector(hSide, sd2 * headR * 0.85).addScaledVector(faceFwd, -headR * 0.1);
                    palm.rotation.z = -sd2 * 0.35;
                    palm.rotation.y = Math.atan2(faceFwd.x, faceFwd.z);
                    headBone.add(palm);
                    for (let t2 = 0; t2 < 4; t2++) {
                        const tine = new THREE.Mesh(new THREE.ConeGeometry(headR * 0.05, headR * 0.32, 5), hornMat);
                        tine.position.copy(palm.position)
                            .addScaledVector(hUp, headR * (0.3 + t2 * 0.05))
                            .addScaledVector(hSide, sd2 * headR * (-0.45 + t2 * 0.32))
                            .addScaledVector(faceFwd, headR * 0.12);
                        tine.rotation.z = -sd2 * 0.25;
                        tine.castShadow = true;
                        headBone.add(tine);
                    }
                    beam.castShadow = palm.castShadow = true;
                    horn = null;
                } else if (globalThis.Loft && hornStyle === 'narwhal') {
                    // single long spiral lance — base EMBEDDED inside the
                    // head so it can't hover off a tapered snout
                    const base = onHead(-0.35, 0.08, 0);
                    const nl = headR * (opts.hornLength ?? 3.2);
                    const pth = [];
                    for (let k2 = 0; k2 <= 5; k2++) {
                        pth.push(new THREE.Vector3().copy(base)
                            .addScaledVector(faceFwd, nl * (0.12 + k2 / 5))
                            .addScaledVector(hUp, nl * (k2 / 5) * 0.14));
                    }
                    horn = globalThis.Loft.sweep({ path: pth, profile: globalThis.Loft.circle(headR * 0.11, 7),
                        scale: (tt) => 1 - 0.92 * tt, twist: 5.5, sections: 18, material: hornMat });
                } else if (globalThis.Loft) {
                    // classic spike: base ON the head surface, sweeping up-back
                    const base = onHead(-0.1, 0.55, a * 0.6);
                    const pth = [];
                    for (const [f, u] of [[0, 0], [-0.12, 0.55], [-0.4, 0.95], [-0.7, 1.15]]) {
                        pth.push(new THREE.Vector3().copy(base)
                            .addScaledVector(faceFwd, len * f).addScaledVector(hUp, len * u));
                    }
                    horn = globalThis.Loft.sweep({
                        path: pth, profile: globalThis.Loft.circle(hr, 10),
                        scale: (t) => 1 - 0.93 * t, twist: 0.6, sections: 16,
                        material: hornMat,
                    });
                } else {
                    horn = new THREE.Mesh(new THREE.ConeGeometry(hr, len, 8), hornMat);
                    horn.position.copy(onHead(-0.1, 0.9, a * 0.6));
                }
                if (horn) {
                    horn.castShadow = true;
                    horn.name = 'horn';
                    headBone.add(horn);
                }
                if (hornStyle === 'narwhal') break;   // narwhal = one lance
            }
        }
        // ---- body add-ons: spikes, armor bands, spiral shell, claws ----
        if (opts.spikes) {
            // hedgehog/porcupine: cones scattered over the back. On upright
            // bipeds the 'back' is the −Z wall, not the top of the tube.
            const spMat = new THREE.MeshStandardNodeMaterial({ color: opts.spikeColor ?? opts.accent ?? 0x4a423a, roughness: 0.6 });
            const n2 = typeof opts.spikes === 'number' && opts.spikes > 1 ? opts.spikes : 36;
            const upright = stance === 'biped';
            for (let s3 = 0; s3 < n2; s3++) {
                const si = 1 + Math.floor(rng() * (spineBones.length - 2));
                const th = (rng() - 0.5) * (upright ? 1.4 : 2.2);
                const r2 = spineRad[Math.min(si, spineRad.length - 1)];
                const spike = new THREE.Mesh(new THREE.ConeGeometry(bodyRad * 0.07, bodyRad * (0.5 + rng() * 0.4), 5), spMat);
                const dir = upright ? V(Math.sin(th), 0, -Math.cos(th)) : V(Math.sin(th), Math.cos(th), 0);
                const lean = upright ? V(dir.x, 0.3, dir.z).normalize() : V(dir.x, dir.y, -0.25 - rng() * 0.3).normalize();
                spike.quaternion.setFromUnitVectors(UP, lean);
                spike.position.set(dir.x * r2 * 0.92, upright ? (rng() - 0.5) * 0.12 : dir.y * r2 * 0.92, upright ? dir.z * r2 * 0.92 : (rng() - 0.5) * 0.1);
                spike.name = 'spike';
                spineBones[si].add(spike);
            }
        }
        const backTents = [];
        if (opts.backTentacles) {
            // tentacles from the back — wing-slot equivalent, any stance.
            // Skinned chains ('tentacles' robotParts category → chrome).
            const nBt = typeof opts.backTentacles === 'number' && opts.backTentacles > 1 ? opts.backTentacles : 4;
            const btLen = (opts.backTentacleLength ?? bodyLen * 0.85);
            const si = stance === 'biped' ? nSpine - 2 : Math.min(nSpine - 2, Math.round(0.6 * (nSpine - 1)));
            const sp2 = spinePts[si];
            for (let bi = 0; bi < nBt; bi++) {
                const a = (nBt === 1) ? 0 : (-1 + 2 * (bi / (nBt - 1)));   // fan across the back
                const out = V(a * 0.75, stance === 'biped' ? 0.55 : 0.85, stance === 'biped' ? -0.6 : -0.25).normalize();
                const pts = [];
                for (let j = 0; j < 5; j++) {
                    const f2 = j / 4;
                    pts.push(new THREE.Vector3().copy(sp2)
                        .add(V(0, stance === 'biped' ? 0 : spineRad[si] * 0.4, stance === 'biped' ? -spineRad[si] * 0.5 : 0))
                        .addScaledVector(out, btLen * f2)
                        .add(V(0, Math.sin(f2 * Math.PI) * btLen * 0.12, 0)));
                }
                const radii = [0.5, 0.38, 0.27, 0.16, 0.07].map((r) => r * bodyRad * 0.55);
                const base = allBones.length;
                const chain = boneChain(pts, spineBones[si], allBones);
                pushMesh(skinnedTube(pts, radii, base, { radial: 8, ringsPerSpan: 4, taperStart: false }), 'tentacles');
                // curl axis ⊥ to the fan direction, horizontal
                backTents.push({ bones: chain, k: bi, axis: V(out.z, 0, -out.x).normalize() });
            }
        }
        if (opts.armor) {
            // armadillo: overlapping shell bands over the back
            const arMat = new THREE.MeshStandardNodeMaterial({
                color: opts.armorColor ?? new THREE.Color(opts.color ?? 0x6a8f4a).multiplyScalar(0.55).getHex(), roughness: 0.5 });
            for (let si = 1; si < spineBones.length - 1; si++) {
                const r2 = spineRad[Math.min(si, spineRad.length - 1)];
                const band = new THREE.Mesh(new THREE.SphereGeometry(r2 * 1.22, 14, 8, 0, Math.PI * 2, 0, Math.PI * 0.52), arMat);
                band.scale.set(1, 0.85, 0.62);
                band.position.y = r2 * 0.1;
                band.castShadow = true;
                band.name = 'armor';
                spineBones[si].add(band);
            }
        }
        if (opts.shell ?? (stance === 'snail')) {
            // spiral shell on the back — remixable onto ANY creature
            const shMat = new THREE.MeshStandardNodeMaterial({ color: opts.shellColor ?? 0xb98a4a, roughness: 0.55 });
            const shS = (opts.shellScale ?? 1) * bodyRad * 3.2;
            const si = Math.round((spineBones.length - 1) * 0.45);
            let shell = null;
            if (globalThis.Loft) {
                // coil starts at the BIG whorl low against the body and
                // spirals up-inward (it read upside down before, user-caught)
                const ctr = V(0, spineRad[si] * 0.5 + shS * 0.36, 0);
                const pth = [];
                for (let k2 = 0; k2 <= 14; k2++) {
                    const th = -0.4 + (k2 / 14) * Math.PI * 2 * 1.9;
                    const rr = shS * 0.42 * (1 - k2 / 17);
                    pth.push(new THREE.Vector3().copy(ctr)
                        .addScaledVector(UP, -Math.cos(th) * rr)
                        .addScaledVector(UNIT_Z, -Math.sin(th) * rr)
                        .add(V((k2 / 14) * shS * 0.1, 0, 0)));
                }
                shell = globalThis.Loft.sweep({ path: pth, profile: globalThis.Loft.circle(shS * 0.3, 12),
                    scale: (tt) => 1 - 0.82 * tt, sections: 22, material: shMat });
            } else {
                shell = new THREE.Mesh(new THREE.SphereGeometry(shS * 0.55, 14, 10), shMat);
                shell.scale.set(0.7, 1, 1);
                shell.position.y = spineRad[si] + shS * 0.3;
            }
            shell.castShadow = true;
            shell.name = 'shell';
            shell.position.add(spinePts[si]).sub(spineBones[si].userData.bindPos);
            spineBones[si].add(shell);
        }
        if (opts.claws && legs.length) {
            // crustacean pincers on the front limbs (arms on bipeds)
            const cMat2 = new THREE.MeshStandardNodeMaterial({ color: opts.clawColor ?? 0xc94a2a, roughness: 0.5 });
            const arms2 = legs.filter((l) => l.isArm);
            const targets = arms2.length ? arms2 : legs.slice(-2);   // front pair attaches last
            for (const l of targets) {
                const cr = bodyRad * 0.55;
                const claw = new THREE.Group();
                const palm2 = new THREE.Mesh(new THREE.SphereGeometry(cr, 10, 8), cMat2);
                palm2.scale.set(0.9, 0.75, 1.35);
                claw.add(palm2);
                for (const [off, rot] of [[0.32, -0.35], [-0.18, 0.5]]) {
                    const pincer = new THREE.Mesh(new THREE.ConeGeometry(cr * 0.32, cr * 1.5, 6), cMat2);
                    pincer.rotation.x = Math.PI / 2 + rot;
                    pincer.position.set(0, cr * off, cr * 1.5);
                    claw.add(pincer);
                }
                claw.position.y = -cr * 0.4;
                claw.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.userData.keepMat = true; } });
                claw.name = 'claw';
                l.ankle.add(claw);
            }
        }
        // dorsal fins for serpents/fish / on request — lofted blades when available
        const finMat = new THREE.MeshStandardNodeMaterial({ color: opts.accent ?? 0x2f4a26, roughness: 0.6 });
        for (let f = 0; f < (opts.fins ?? (stance === 'serpent' ? 4 : stance === 'fish' ? (aquaMammal ? 0 : 1) : 0)); f++) {
            const si = stance === 'fish' ? Math.round((spineBones.length - 1) * (0.55 - f * 0.15))
                : 1 + Math.floor((f / Math.max(1, (opts.fins ?? 4))) * (spineBones.length - 2));
            let fin;
            const fh = bodyRad * 1.35 * (opts.finScale ?? 1);   // sharks ≈ 1.8+
            if (globalThis.Loft) {
                fin = globalThis.Loft.sweep({
                    path: [V(0, 0, 0), V(0, fh * 0.55, -fh * 0.10), V(0, fh, -fh * 0.38)],
                    profile: globalThis.Loft.ellipse(bodyRad * 0.42, bodyRad * 0.09, 10),
                    scale: (t) => 1 - 0.85 * t, sections: 10,
                    material: finMat,
                });
            } else {
                fin = new THREE.Mesh(new THREE.ConeGeometry(bodyRad * 0.5, fh, 4), finMat);
                fin.scale.z = 0.3;
            }
            fin.position.y = spineRad[Math.min(si, spineRad.length - 1)] * 0.9;
            fin.castShadow = true;
            spineBones[si].add(fin);
        }

        // ---- wings: two-segment feathered wings (arm + hand-with-primaries,
        // fold like the real thing) or fast translucent membranes (insects) ----
        const wings = [];
        {
            const nWings = opts.wings ?? (stance === 'bird' ? 2 : stance === 'insect' ? 2 : 0);
            if (nWings > 0 && stance !== 'octopus') {
                const si = Math.min(nSpine - 2, Math.round(0.65 * (nSpine - 1)));
                const sp = spinePts[si];
                const wtype = opts.wingType ?? (stance === 'insect' ? 'membrane' : 'feather');
                const membrane = wtype === 'membrane';
                const butterfly = wtype === 'butterfly';
                const bat = wtype === 'bat';
                const span = (opts.wingSpan ?? (membrane ? bodyLen * 0.75 : butterfly ? bodyLen * 1.05 : bodyLen * 0.95));
                const wingMat = membrane
                    ? new THREE.MeshStandardNodeMaterial({ color: opts.wingColor ?? 0xbcd4dc, roughness: 0.25,
                        transparent: true, opacity: 0.45, side: THREE.DoubleSide, depthWrite: false })
                    : butterfly
                    ? new THREE.MeshStandardNodeMaterial({ color: opts.wingColor ?? 0xd97a2a, roughness: 0.6, side: THREE.DoubleSide })
                    : new THREE.MeshStandardNodeMaterial({ color: opts.wingColor ?? opts.accent ?? 0x2f4a26,
                        roughness: 0.7, side: THREE.DoubleSide });
                const pairsW = membrane ? Math.max(1, Math.round(nWings / 2)) : 1;
                for (const sd of [-1, 1]) {
                    for (let wp2 = 0; wp2 < pairsW; wp2++) {
                        const root = new THREE.Group();
                        root.position.set(sd * bodyRad * 0.25,
                            (stance === 'biped' ? sp.y : sp.y + bodyRad * ((membrane || butterfly) ? 0.8 : 0.55)),
                            sp.z - wp2 * bodyLen * 0.18)
                            .sub(spineBones[si].userData.bindPos);
                        root.userData.fold = stance === 'bird' ? 0.5 : 0.12;
                        if (bat) {
                            // real bat anatomy: arm to a WRIST, three tapered
                            // fingers radiating to scallop tips, membrane
                            // panels stretched between them, thumb claw
                            const bMat2 = new THREE.MeshStandardNodeMaterial({
                                color: opts.wingColor ?? 0x3a2a30, roughness: 0.7, side: THREE.DoubleSide });
                            const boneMat2 = new THREE.MeshStandardNodeMaterial({
                                color: new THREE.Color(opts.wingColor ?? 0x3a2a30).multiplyScalar(0.65).getHex(), roughness: 0.6 });
                            const S = span;
                            const W2 = V(sd * S * 0.34, 0, -S * 0.02);
                            // arm: shoulder → wrist
                            const armB = new THREE.Mesh(new THREE.CylinderGeometry(S * 0.022, S * 0.03, W2.length(), 6), boneMat2);
                            armB.position.copy(W2).multiplyScalar(0.5);
                            armB.quaternion.setFromUnitVectors(UP, W2.clone().normalize());
                            root.add(armB);
                            const tips = [V(sd * S, 0, -S * 0.06), V(sd * S * 0.86, 0, -S * 0.32), V(sd * S * 0.6, 0, -S * 0.52)];
                            for (const T2 of tips) {
                                const d2 = T2.clone().sub(W2);
                                const fing = new THREE.Mesh(new THREE.CylinderGeometry(S * 0.01, S * 0.018, d2.length(), 5), boneMat2);
                                fing.position.copy(W2).addScaledVector(d2, 0.5);
                                fing.quaternion.setFromUnitVectors(UP, d2.normalize());
                                root.add(fing);
                            }
                            // membrane panels between fingers + arm membrane
                            const panels = [
                                { c: V(sd * S * 0.72, -S * 0.004, -S * 0.15), sx: 0.66, sz: 0.3 },
                                { c: V(sd * S * 0.58, -S * 0.004, -S * 0.34), sx: 0.5, sz: 0.28 },
                                { c: V(sd * S * 0.3, -S * 0.004, -S * 0.24), sx: 0.42, sz: 0.34 },
                            ];
                            for (const pn of panels) {
                                const mem = new THREE.Mesh(new THREE.SphereGeometry(S * 0.5, 12, 8), bMat2);
                                mem.scale.set(pn.sx, 0.035, pn.sz);
                                mem.position.copy(pn.c);
                                mem.castShadow = true;
                                root.add(mem);
                            }
                            const thumb = new THREE.Mesh(new THREE.ConeGeometry(S * 0.02, S * 0.1, 5), boneMat2);
                            thumb.position.copy(W2).add(V(0, S * 0.02, S * 0.05));
                            thumb.rotation.x = Math.PI / 2.4;
                            root.add(thumb);
                            root.userData.fold = 0.9;   // bats fold tight
                            spineBones[si].add(root);
                            wings.push({ root, outer: null, side: sd, buzz: false, k: 0 });
                        } else if (butterfly) {
                            // moth/butterfly: big flat forewing + hindwing
                            // panels with an eye-spot; slow flap, folded
                            // UPRIGHT over the back at rest
                            const fore = new THREE.Mesh(new THREE.SphereGeometry(span * 0.5, 14, 10), wingMat);
                            fore.scale.set(1, 0.035, 0.6);
                            fore.position.set(sd * span * 0.46, 0, span * 0.1);
                            fore.rotation.y = sd * -0.18;
                            const hind = new THREE.Mesh(new THREE.SphereGeometry(span * 0.32, 12, 8), wingMat);
                            hind.scale.set(1, 0.035, 0.72);
                            hind.position.set(sd * span * 0.28, -span * 0.004, -span * 0.24);
                            hind.rotation.y = sd * 0.3;
                            const spot = new THREE.Mesh(new THREE.CylinderGeometry(span * 0.09, span * 0.09, span * 0.012, 12),
                                new THREE.MeshStandardNodeMaterial({ color: opts.accent ?? 0x2a1f14, roughness: 0.6 }));
                            spot.position.set(sd * span * 0.58, span * 0.012, span * 0.12);
                            fore.castShadow = hind.castShadow = true;
                            root.add(fore); root.add(hind); root.add(spot);
                            spineBones[si].add(root);
                            wings.push({ root, outer: null, side: sd, buzz: false, butterfly: true, k: wp2 });
                        } else if (membrane) {
                            const blade = new THREE.Mesh(new THREE.SphereGeometry(span * 0.5, 12, 8), wingMat);
                            blade.scale.set(1, 0.06, 0.3);
                            blade.position.x = sd * span * 0.48;
                            blade.rotation.y = sd * -0.22;   // rake back
                            root.add(blade);
                            spineBones[si].add(root);
                            wings.push({ root, outer: null, side: sd, buzz: true, k: wp2 });
                        } else {
                            const L1w = span * 0.45, L2w = span * 0.62;
                            let innerB;
                            if (globalThis.Loft) {
                                innerB = globalThis.Loft.sweep({
                                    path: [V(0, 0, 0), V(sd * L1w * 0.55, L1w * 0.14, -L1w * 0.02), V(sd * L1w, L1w * 0.18, -L1w * 0.08)],
                                    profile: globalThis.Loft.ellipse(L1w * 0.42, L1w * 0.05, 10),
                                    scale: (tt) => 1 - 0.25 * tt, sections: 8, material: wingMat });
                            } else {
                                innerB = new THREE.Mesh(new THREE.BoxGeometry(L1w, L1w * 0.05, L1w * 0.5), wingMat);
                                innerB.position.x = sd * L1w * 0.5;
                            }
                            innerB.castShadow = true;
                            root.add(innerB);
                            // hand segment: 5 graduated primaries + a covert
                            // layer over their base — the layered silhouette
                            // is most of what reads 'feathered wing'
                            const outer = new THREE.Group();
                            outer.position.set(sd * L1w, L1w * 0.18, -L1w * 0.08);
                            for (let fk = 0; fk < 5; fk++) {
                                let prim;
                                const fl = L2w * (1 - fk * 0.13);
                                if (globalThis.Loft) {
                                    prim = globalThis.Loft.sweep({
                                        path: [V(0, 0, -fk * L2w * 0.065), V(sd * fl * 0.6, fl * 0.02, -fk * L2w * 0.065 - fl * 0.08),
                                               V(sd * fl, -fl * 0.05, -fk * L2w * 0.065 - fl * (0.18 + fk * 0.08))],
                                        profile: globalThis.Loft.ellipse(fl * 0.24, fl * 0.03, 8),
                                        scale: (tt) => 1 - 0.55 * tt, sections: 8, material: wingMat });
                                } else {
                                    prim = new THREE.Mesh(new THREE.BoxGeometry(fl, fl * 0.04, fl * 0.2), wingMat);
                                    prim.position.set(sd * fl * 0.5, 0, -fk * L2w * 0.08);
                                }
                                prim.castShadow = true;
                                outer.add(prim);
                            }
                            const covert = new THREE.Mesh(new THREE.SphereGeometry(L2w * 0.3, 10, 6),
                                new THREE.MeshStandardNodeMaterial({
                                    color: new THREE.Color(opts.wingColor ?? opts.accent ?? 0x2f4a26).multiplyScalar(1.25),
                                    roughness: 0.75, side: THREE.DoubleSide }));
                            covert.scale.set(1.5, 0.14, 0.85);
                            covert.position.set(sd * L2w * 0.32, L2w * 0.02, -L2w * 0.06);
                            covert.castShadow = true;
                            outer.add(covert);
                            root.add(outer);
                            spineBones[si].add(root);
                            wings.push({ root, outer, side: sd, buzz: false, k: 0 });
                        }
                    }
                }
            }
        }

        // ---- accessories: remixable on ANY creature with a head ----
        if (opts.hat && crownAnchor) {
            const hatMat = new THREE.MeshStandardNodeMaterial({ color: opts.hatColor ?? 0x2e2b28, roughness: 0.6 });
            const hat = new THREE.Group();
            const fitR = crownR * 1.08;
            if (opts.hat === 'top') {
                const tube = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 0.78, fitR * 0.72, fitR * 1.3, 16), hatMat);
                tube.position.y = fitR * 0.72;
                const brim = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 1.28, fitR * 1.28, fitR * 0.08, 18), hatMat);
                brim.position.y = fitR * 0.08;
                const band = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 0.8, 0.8 * fitR, fitR * 0.22, 16),
                    new THREE.MeshStandardNodeMaterial({ color: opts.hatBand ?? 0x7a1f2a, roughness: 0.55 }));
                band.position.y = fitR * 0.28;
                hat.add(tube); hat.add(brim); hat.add(band);
            } else if (opts.hat === 'beanie') {
                const dome = new THREE.Mesh(new THREE.SphereGeometry(fitR, 16, 10, 0, Math.PI * 2, 0, Math.PI * 0.58), hatMat);
                dome.scale.y = 0.95;
                hat.add(dome);
            } else if (opts.hat === 'cowboy') {
                // pinched tall crown + wide oval brim with rolled sides
                const crown = new THREE.Mesh(new THREE.SphereGeometry(fitR * 0.92, 16, 12, 0, Math.PI * 2, 0, Math.PI * 0.58), hatMat);
                crown.scale.set(0.88, 1.1, 1.02);
                crown.position.y = fitR * 0.16;
                const brim = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 1.75, fitR * 1.75, fitR * 0.06, 20), hatMat);
                brim.scale.z = 0.8;
                brim.position.y = fitR * 0.08;
                hat.add(crown); hat.add(brim);
                for (const sd of [-1, 1]) {   // rolled brim edges
                    const roll = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 0.1, fitR * 0.1, fitR * 1.35, 8), hatMat);
                    roll.rotation.x = Math.PI / 2;
                    roll.position.set(sd * fitR * 1.6, fitR * 0.17, 0);
                    hat.add(roll);
                }
                const band2 = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 0.88, fitR * 0.88, fitR * 0.16, 16),
                    new THREE.MeshStandardNodeMaterial({ color: opts.hatBand ?? 0x5a3a22, roughness: 0.55 }));
                band2.position.y = fitR * 0.16;
                hat.add(band2);
            } else if (opts.hat === 'officer') {
                // peaked cap: tall band, oversized flat crown tilted forward,
                // dark visor, brass badge
                const band3 = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 1.0, fitR * 0.96, fitR * 0.4, 18), hatMat);
                band3.position.y = fitR * 0.2;
                const crown = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 1.3, fitR * 1.02, fitR * 0.2, 18), hatMat);
                crown.position.y = fitR * 0.48;
                crown.rotation.x = -0.09;
                const visor = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 0.85, fitR * 0.85, fitR * 0.05, 14),
                    new THREE.MeshStandardNodeMaterial({ color: 0x14140f, roughness: 0.3 }));
                visor.scale.x = 0.92;
                visor.position.set(0, fitR * 0.04, fitR * 0.72);
                visor.rotation.x = 0.14;
                const badge = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 0.13, fitR * 0.13, fitR * 0.05, 10),
                    new THREE.MeshStandardNodeMaterial({ color: 0xc9a637, roughness: 0.3, metalness: 0.7 }));
                badge.rotation.x = Math.PI / 2;
                badge.position.set(0, fitR * 0.3, fitR * 1.0);
                hat.add(band3); hat.add(crown); hat.add(visor); hat.add(badge);
            } else {   // 'cap'
                const dome = new THREE.Mesh(new THREE.SphereGeometry(fitR, 16, 10, 0, Math.PI * 2, 0, Math.PI * 0.5), hatMat);
                dome.scale.y = 0.78;
                const bill = new THREE.Mesh(new THREE.CylinderGeometry(fitR * 0.82, fitR * 0.82, fitR * 0.07, 14), hatMat);
                bill.scale.x = 0.85;
                bill.position.set(0, 0.01, fitR * 0.95);
                hat.add(dome); hat.add(bill);
            }
            hat.position.copy(crownAnchor);
            hat.rotation.y = Math.atan2(faceFwd.x, faceFwd.z);   // bill/band face the face
            headBone.add(hat);
        }
        if (opts.sunglasses && eyeAnchors.length >= 2) {
            const gMat = new THREE.MeshStandardNodeMaterial({ color: 0x0c0c10, roughness: 0.12, metalness: 0.3 });
            const r3 = eyeSize * 1.4;
            const yawG = Math.atan2(faceFwd.x, faceFwd.z);
            for (const ea of eyeAnchors.slice(0, 2)) {
                const lens = new THREE.Mesh(new THREE.CylinderGeometry(r3, r3, eyeSize * 0.3, 14), gMat);
                lens.quaternion.setFromUnitVectors(UP, faceFwd);
                // proud of the brow bulge, not embedded in it (user-caught)
                lens.position.copy(ea).addScaledVector(faceFwd, eyeSize * 1.6);
                headBone.add(lens);
            }
            const bridge = new THREE.Mesh(new THREE.BoxGeometry(eyeAnchors[0].distanceTo(eyeAnchors[1]) * 0.65, eyeSize * 0.22, eyeSize * 0.2), gMat);
            bridge.position.copy(eyeAnchors[0]).add(eyeAnchors[1]).multiplyScalar(0.5).addScaledVector(faceFwd, eyeSize * 1.6);
            bridge.rotation.y = yawG;
            headBone.add(bridge);
        }
        if (opts.glasses && eyeAnchors.length >= 2) {
            // clear eyeglasses: thin ring frames + bridge (sunglasses' solid
            // discs stay separate)
            const fMat = new THREE.MeshStandardNodeMaterial({ color: opts.glassesColor ?? 0x2a2a30, roughness: 0.35, metalness: 0.4 });
            const yawG2 = Math.atan2(faceFwd.x, faceFwd.z);
            for (const ea of eyeAnchors.slice(0, 2)) {
                const ring = new THREE.Mesh(new THREE.TorusGeometry(eyeSize * 1.25, eyeSize * 0.12, 8, 18), fMat);
                ring.quaternion.setFromUnitVectors(UNIT_Z, faceFwd);
                ring.position.copy(ea).addScaledVector(faceFwd, eyeSize * 1.5);
                ring.name = 'glasses';
                headBone.add(ring);
            }
            const bridge2 = new THREE.Mesh(new THREE.BoxGeometry(eyeAnchors[0].distanceTo(eyeAnchors[1]) * 0.5, eyeSize * 0.14, eyeSize * 0.12), fMat);
            bridge2.position.copy(eyeAnchors[0]).add(eyeAnchors[1]).multiplyScalar(0.5).addScaledVector(faceFwd, eyeSize * 1.5);
            bridge2.rotation.y = yawG2;
            headBone.add(bridge2);
        }
        if (opts.helmet && crownAnchor) {
            const yawH = Math.atan2(faceFwd.x, faceFwd.z);
            if (opts.helmet === 'space') {
                // fishbowl: transparent sphere around the whole head + collar ring
                const glass = new THREE.Mesh(new THREE.SphereGeometry(crownR * 1.75, 20, 14),
                    new THREE.MeshStandardNodeMaterial({ color: 0xcfe4f0, roughness: 0.08, metalness: 0.1,
                        transparent: true, opacity: 0.22, side: THREE.DoubleSide, depthWrite: false }));
                glass.position.copy(crownAnchor).addScaledVector(hUp, -crownR * 0.55);
                glass.name = 'helmet';
                headBone.add(glass);
                const ring = new THREE.Mesh(new THREE.TorusGeometry(crownR * 1.3, crownR * 0.16, 10, 18),
                    new THREE.MeshStandardNodeMaterial({ color: 0x9aa4ae, roughness: 0.35, metalness: 0.8 }));
                ring.rotation.x = Math.PI / 2;
                ring.position.copy(crownAnchor).addScaledVector(hUp, -crownR * 1.8);
                headBone.add(ring);
            } else {   // 'hardhat'
                const hMat2 = new THREE.MeshStandardNodeMaterial({ color: opts.helmetColor ?? 0xe8b820, roughness: 0.45 });
                const dome = new THREE.Mesh(new THREE.SphereGeometry(crownR * 1.12, 16, 10, 0, Math.PI * 2, 0, Math.PI * 0.52), hMat2);
                dome.scale.y = 0.72;
                dome.position.copy(crownAnchor);
                const ridge = new THREE.Mesh(new THREE.BoxGeometry(crownR * 0.28, crownR * 0.12, crownR * 1.9), hMat2);
                ridge.position.copy(crownAnchor).addScaledVector(hUp, crownR * 0.62);
                ridge.rotation.y = yawH;
                const brim2 = new THREE.Mesh(new THREE.CylinderGeometry(crownR * 1.42, crownR * 1.42, crownR * 0.06, 18), hMat2);
                brim2.position.copy(crownAnchor).addScaledVector(hUp, crownR * 0.02);
                dome.name = 'helmet';
                headBone.add(dome); headBone.add(ridge); headBone.add(brim2);
            }
        }
        if (opts.mask && crownAnchor) {
            // circular emoji mask strapped over the face: 'smile' | 'frown'
            const angry = opts.mask === 'frown';
            const mR = crownR * 1.15;
            const mGroup = new THREE.Group();
            const face2 = new THREE.Mesh(new THREE.CylinderGeometry(mR, mR, mR * 0.08, 24),
                new THREE.MeshStandardNodeMaterial({ color: opts.maskColor ?? (angry ? 0xe84a2a : 0xf2c930), roughness: 0.5 }));
            face2.quaternion.setFromUnitVectors(UP, UNIT_Z);
            mGroup.add(face2);
            const inkMat = new THREE.MeshStandardNodeMaterial({ color: opts.maskInk ?? 0x14100c, roughness: 0.5 });
            for (const sd of [-1, 1]) {
                const eyeDot = new THREE.Mesh(new THREE.CylinderGeometry(mR * 0.1, mR * 0.1, mR * 0.06, 10), inkMat);
                eyeDot.quaternion.setFromUnitVectors(UP, UNIT_Z);
                eyeDot.position.set(sd * mR * 0.34, mR * 0.22, mR * 0.05);
                mGroup.add(eyeDot);
                if (angry) {   // slanted brows
                    const brow2 = new THREE.Mesh(new THREE.BoxGeometry(mR * 0.32, mR * 0.07, mR * 0.05), inkMat);
                    brow2.position.set(sd * mR * 0.34, mR * 0.44, mR * 0.05);
                    brow2.rotation.z = sd * 0.5;
                    mGroup.add(brow2);
                }
            }
            // mouth: FILLED half-disc (solid emoji features, not outlines —
            // user-clarified). Smile = round side down; frown = sad hump.
            const mouth2 = new THREE.Mesh(new THREE.CylinderGeometry(mR * 0.42, mR * 0.42, mR * 0.07, 18, 1, false, 0, Math.PI), inkMat);
            mouth2.quaternion.setFromUnitVectors(UP, UNIT_Z);
            mouth2.rotateZ(angry ? Math.PI / 2 : -Math.PI / 2);
            mouth2.position.set(0, angry ? -mR * 0.52 : -mR * 0.14, mR * 0.05);
            mGroup.add(mouth2);
            mGroup.position.copy(crownAnchor).addScaledVector(hUp, -crownR * 0.55).addScaledVector(faceFwd, crownR * 1.05);
            mGroup.quaternion.setFromUnitVectors(UNIT_Z, faceFwd);
            mGroup.name = 'mask';
            headBone.add(mGroup);
        }
        if (opts.tie && stance === 'biped') {
            const tieMat = new THREE.MeshStandardNodeMaterial({ color: typeof opts.tie === 'number' ? opts.tie : 0x8a1f2c, roughness: 0.5 });
            const chestBone = spineBones[nSpine - 2];
            const bp = chestBone.userData.bindPos;
            const knot = new THREE.Mesh(new THREE.SphereGeometry(bodyRad * 0.17, 8, 6), tieMat);
            knot.position.set(0, hipH + bodyLen * 0.95, bodyRad * 0.98).sub(bp);
            chestBone.add(knot);
            // strip rides PROUD of the chest curve (max torso radius ~1.05R
            // at the chest — 1.02R sat inside it, user-caught)
            const strip = new THREE.Mesh(new THREE.BoxGeometry(bodyRad * 0.28, bodyLen * 0.52, bodyRad * 0.07), tieMat);
            strip.position.set(0, hipH + bodyLen * 0.64, bodyRad * 1.16).sub(bp);
            strip.rotation.x = 0.08;
            chestBone.add(strip);
        }
        if (opts.outfit && stance === 'biped') {
            // shirt collar: a soft ring seating the neck into the shirt
            const collarMat = new THREE.MeshStandardNodeMaterial({
                color: new THREE.Color(opts.outfit.shirt ?? 0x3a6ea8).multiplyScalar(0.8), roughness: 0.7 });
            const topBone = spineBones[nSpine - 1];
            const collar = new THREE.Mesh(new THREE.TorusGeometry(bodyRad * 0.44, bodyRad * 0.14, 8, 16), collarMat);
            collar.rotation.x = Math.PI / 2;
            collar.position.set(0, hipH + bodyLen + 0.01, spinePts[nSpine - 1].z).sub(topBone.userData.bindPos);
            topBone.add(collar);
        }
        // robot styling: joint caps at the articulation points (per-element
        // when robotParts is used — a cyborg arm gets caps, the organic legs don't)
        if (robotParts.size) {
            const jointMat = new THREE.MeshStandardNodeMaterial({ color: 0x3a3f45, roughness: 0.35, metalness: 0.85 });
            for (const l of legs) {
                if (!robotParts.has(l.isArm ? 'arms' : 'legs')) continue;
                for (const b of [l.hip, l.knee]) {
                    const cap = new THREE.Mesh(new THREE.SphereGeometry(bodyRad * (l.isArm ? 0.34 : 0.44) * (splayed ? 0.5 : 1), 10, 8), jointMat);
                    cap.userData.keepMat = true;
                    b.add(cap);
                }
            }
        }

        // ---- assemble skinned meshes on ONE shared skeleton ----
        // ORDER MATTERS: Skeleton() computes boneInverses from the bones'
        // CURRENT matrixWorld — update the bone tree first or every inverse
        // is identity and the skin scatters (statically: everything offset
        // by its bone position; animated: parts fly apart).
        group.updateMatrixWorld(true);
        const skeleton = new THREE.Skeleton(allBones);
        const mat = creatureMaterial({
            color: opts.color ?? 0x6a8f4a, belly: opts.belly ?? 0xcfc7a2,
            accent: opts.accent ?? 0x2f4a26, pattern: opts.pattern ?? 'spots',
            roughness: opts.roughness, robot: robotParts.has('body'),
            map: opts.map, normalMap: opts.normalMap, roughnessMap: opts.roughnessMap,
            outfit: opts.outfit ? {
                ...opts.outfit,
                collarY: opts.outfit.collarY ?? (hipH + bodyLen * 0.96),
                hipY: opts.outfit.hipY ?? (hipH + bodyLen * 0.08),
                ankleY: opts.outfit.ankleY ?? (legLen * 0.16),
            } : null,
        });
        // arms: shirt sleeve to the elbow, skin below (the body outfit bands
        // are height-based and would paint forearms as PANTS)
        let sleeveMat = null;
        if (opts.outfit && armMeshIdx.length) {
            const { vec3, positionGeometry, mix, smoothstep } = THREE;
            const sh = new THREE.Color(opts.outfit.shirt ?? 0x3a6ea8);
            const sk = new THREE.Color(opts.skin ?? opts.color ?? 0xd9a37f);
            sleeveMat = new THREE.MeshStandardNodeMaterial({ roughness: 0.65 });
            const elbowY = (hipH + bodyLen * 0.92) - armLen * 0.48;
            sleeveMat.colorNode = mix(vec3(sk.r, sk.g, sk.b), vec3(sh.r, sh.g, sh.b),
                smoothstep(elbowY - 0.02, elbowY + 0.02, positionGeometry.y));
        }
        const armSet = new Set(armMeshIdx);
        // cyborg mixes: robotParts categories get the machine material
        const robotMat = robotParts.size ? creatureMaterial({ robot: true, color: opts.robotColor ?? (opts.robot ? (opts.color ?? 0x7a8894) : 0x7a8894) }) : null;
        meshes.forEach((g, gi) => {
            const useMat = (robotMat && robotParts.has(meshPart[gi])) ? robotMat
                : (sleeveMat && armSet.has(gi)) ? sleeveMat : mat;
            const sm = new THREE.SkinnedMesh(g, useMat);
            sm.castShadow = true; sm.receiveShadow = true;
            sm.frustumCulled = false;
            group.add(sm);
            sm.bind(skeleton, sm.matrixWorld);
        });
        // feet are built from parts: paint body-material except marked pieces
        // (shoes, hooves, claws keep their own)
        for (const l of legs) {
            if (!l.foot) continue;
            l.foot.traverse((o) => {
                if (o.isMesh && !o.userData.keepMat && !o.material) o.material = mat;
                if (o.isMesh && !globalThis.__noFootShadow) { o.castShadow = true; }
            });
        }
        // junction welds: solid color matched to the outfit band at the
        // weld's HEIGHT (they can't share the banded body material — their
        // local-origin geometry evaluates as the shoe band)
        for (const wm of weldMeshes) {
            if (opts.outfit) {
                const collarY = opts.outfit.collarY ?? (hipH + bodyLen * 0.96);
                const hipY = opts.outfit.hipY ?? (hipH + bodyLen * 0.08);
                const ankleY = opts.outfit.ankleY ?? (legLen * 0.16);
                const col = wm.y > collarY ? (opts.skin ?? opts.color ?? 0xd9a37f)
                    : wm.y > hipY ? (opts.outfit.shirt ?? 0x3a6ea8)
                    : wm.y > ankleY ? (opts.outfit.pants ?? 0x35322e)
                    : (opts.outfit.shoes ?? 0x221d18);
                wm.mesh.material = new THREE.MeshStandardNodeMaterial({ color: col, roughness: 0.65 });
            } else {
                wm.mesh.material = mat;
            }
        }

        // ---- gait engine ----
        const st = {
            heading: opts.heading ?? 0,
            speed: opts.speed ?? 0.5,
            turn: opts.turn ?? 0,
            phase: 0, lastT: null,
            // bipeds take short careful steps; arthropods skitter; multi-
            // legged gaits stride longer
            stride: opts.stride ?? legLen * (stance === 'biped' ? 0.55 : splayed ? 0.5 : 0.85),
            duty: stance === 'biped' ? 0.6 : splayed ? 0.55 : walkers.length > 4 ? 0.7 : 0.58,
            lift: legLen * (stance === 'biped' ? 0.07 : splayed ? 0.13 : 0.09),   // swing CLEARANCE (big lifts fold the leg in half)
            blinkAt: 1.5 + rng() * 3, target: null,
            gaitAmt: 0,                    // eased 0..1 walk envelope (settle on stop)
            tongueAt: 1 + rng() * 2,       // serpent tongue-flick timer
            earFlickAt: 2 + rng() * 3, earFlickSide: 0,
            bank: 0, pitch: 0,             // flight attitude (eased)
        };
        st.strideAuto = stance === 'biped' && opts.stride == null;   // stride grows with speed
        st.gaitMode = initialGait;
        // serpent path-following state: the head traces a trail; every
        // spine bone rides that SAME trail at its arc-length station
        const serp = stance === 'serpent' ? {
            seg: bodyLen / (nSpine - 1),
            lambda: opts.waveLength ?? bodyLen * 0.55,                // S-wave length along the ground
            amp: opts.waveAmp ?? bodyLen * 0.55 * 0.14,               // S-wave half-width
            headLift: opts.headLift ?? 0.7,                           // 0..~1.2 raised-head amount
            ds: 0.03, trail: [], sDist: 0,
            pose: spinePts.map(() => new THREE.Vector3()),
        } : null;
        const fwd = new THREE.Vector3(), tmpW = new THREE.Vector3();

        function update(t) {
            if (st.lastT === null) st.lastT = t;
            let dt = Math.min(Math.max(t - st.lastT, 0), 0.1);
            st.lastT = t;

            // steering — serpents turn on a curvature cap (the body must be
            // able to follow the head's path without kinking) and aim their
            // HEAD, which leads the group origin by half a body
            fwd.set(Math.sin(st.heading), 0, Math.cos(st.heading));
            const maxTurn = stance === 'serpent' ? Math.max(0.25, st.speed) / 0.8 : 1.4;
            if (st.target) {
                const lead = stance === 'serpent' ? bodyLen * 0.5 : 0;
                const dx = st.target.x - (group.position.x + fwd.x * lead);
                const dz = st.target.z - (group.position.z + fwd.z * lead);
                const dist = Math.hypot(dx, dz);
                if (dist < 0.25) { st.speed = 0; st.target = null; }
                else {
                    const want = Math.atan2(dx, dz);
                    let dh = want - st.heading;
                    while (dh > Math.PI) dh -= Math.PI * 2;
                    while (dh < -Math.PI) dh += Math.PI * 2;
                    st.heading += Math.sign(dh) * Math.min(Math.abs(dh), maxTurn * dt);
                }
            } else {
                st.heading += Math.sign(st.turn) * Math.min(Math.abs(st.turn), maxTurn) * dt;
            }
            if (stance !== 'serpent') group.rotation.y = st.heading;
            fwd.set(Math.sin(st.heading), 0, Math.cos(st.heading));

            // bipeds lengthen stride with speed (auto unless the scene pinned
            // one) and blend into a RUN above ~1 m/s: airborne duty, higher
            // knees, deeper lean, pumping arms
            const runF = stance === 'biped' ? Math.max(0, Math.min(1, (st.speed - 1.0) / 0.8)) : 0;
            if (stance === 'biped') {
                st.duty = 0.6 - 0.2 * runF;
                st.lift = legLen * (0.07 + 0.1 * runF);
            }
            if (st.strideAuto) st.stride = legLen * Math.min(1.5, 0.62 + st.speed * 0.45);

            const moving = st.speed > 0.01;   // (also used by wings/octopus below)
            if (moving) {
                group.position.addScaledVector(fwd, st.speed * dt);
                st.phase += (st.speed * dt) / st.stride;
            }

            const groundY = opts.groundY ?? 0;

            if (stance === 'serpent') {
                // ── ground-fixed path following (real lateral undulation) ──
                // The head traces a sinuous path; every spine bone rides THAT
                // SAME path at its arc-length station — the S-curves stay
                // planted in the world (the 'tracks') while the body slides
                // through them. A travelling wave on the bones side-slips;
                // tracks don't. Bonus: turns propagate down the body, and a
                // stop rests in its S-curve instead of straightening.
                group.position.y = groundY;
                group.rotation.y = 0;   // bones are posed in world-aligned group space
                if (moving) serp.sDist += st.speed * dt;
                const ampNow = serp.amp * Math.min(1, Math.max(0.4, st.speed / 0.4));
                const lat = Math.sin((serp.sDist * Math.PI * 2) / serp.lambda) * ampNow;
                const hx = group.position.x + fwd.x * bodyLen * 0.5 + fwd.z * lat;
                const hz = group.position.z + fwd.z * bodyLen * 0.5 - fwd.x * lat;
                const tr = serp.trail;
                const newest = tr[tr.length - 1];
                if (!newest || Math.hypot(hx - newest.x, hz - newest.z) > 1.5) {
                    // first frame or a teleport: seed a straight trail behind the head
                    tr.length = 0;
                    const n = Math.ceil((bodyLen + 0.6) / serp.ds);
                    for (let i = n; i >= 1; i--) tr.push({ x: hx - fwd.x * serp.ds * i, z: hz - fwd.z * serp.ds * i });
                }
                if (Math.hypot(hx - tr[tr.length - 1].x, hz - tr[tr.length - 1].z) >= serp.ds) {
                    tr.push({ x: hx, z: hz });
                    const cap = Math.ceil((bodyLen + 0.9) / serp.ds);
                    if (tr.length > cap) tr.splice(0, tr.length - cap);
                }
                // walk the trail backward from the head, dropping each bone
                // at its fixed arc distance
                let px = hx, pz = hz, ti = tr.length - 1, acc = 0;
                let sdx = -fwd.x, sdz = -fwd.z;
                const maxLift = bodyRad * 1.5 * serp.headLift;
                for (let s2 = 0; s2 < nSpine; s2++) {
                    const D = s2 * serp.seg;
                    while (acc < D - 1e-6) {
                        const qp = ti >= 0 ? tr[ti] : null;
                        if (!qp) { const r = D - acc; px += sdx * r; pz += sdz * r; acc = D; break; }
                        const ddx = qp.x - px, ddz = qp.z - pz;
                        const L = Math.hypot(ddx, ddz);
                        if (L < 1e-6) { ti--; continue; }
                        if (acc + L >= D) {
                            const r = (D - acc) / L;
                            px += ddx * r; pz += ddz * r; sdx = ddx / L; sdz = ddz / L; acc = D;
                        } else { px = qp.x; pz = qp.z; sdx = ddx / L; sdz = ddz / L; acc += L; ti--; }
                    }
                    const lift = s2 === 0 ? maxLift : s2 === 1 ? maxLift * 0.55 : s2 === 2 ? maxLift * 0.18 : 0;
                    serp.pose[nSpine - 1 - s2].set(px - group.position.x, hipH + lift, pz - group.position.z);
                }
                for (let i = 0; i < nSpine; i++) {
                    const b = spineBones[i];
                    b.position.copy(serp.pose[i]);
                    const tan = TMP.a.copy(serp.pose[Math.min(i + 1, nSpine - 1)]).sub(serp.pose[Math.max(i - 1, 0)]);
                    if (tan.lengthSq() < 1e-9) tan.set(fwd.x, 0, fwd.z);
                    b.quaternion.setFromUnitVectors(UNIT_Z, tan.normalize());
                }
                // head personality: level the gaze while slithering, scan when idle
                const hb = spineBones[nSpine - 1];
                if (moving) hb.quaternion.slerp(TMP.q2.setFromAxisAngle(UP, st.heading), 0.35);
                else hb.quaternion.multiply(TMP.q2.setFromAxisAngle(UP, Math.sin(t * 0.6) * 0.38 + Math.sin(t * 1.55) * 0.1));
                // tongue flick
                if (typeof tongueG !== 'undefined' && tongueG) {
                    const ft = (t - st.tongueAt) / 0.5;
                    if (ft >= 1) { tongueG.scale.z = 0.001; st.tongueAt = t + 1.4 + rng() * 3; }
                    else if (ft >= 0) {
                        const e = Math.sin(ft * Math.PI);
                        tongueG.scale.z = 0.05 + 0.95 * e;
                        tongueG.rotation.y = Math.sin(t * 34) * 0.14 * e;
                        tongueG.rotation.x = Math.sin(t * 27) * 0.1 * e;
                    }
                }
            } else if (stance === 'octopus') {
                group.position.y = groundY + Math.sin(t * 1.6) * 0.02 * octoScale;
                for (const tn of tentacles) {
                    // curl wave travelling outward, stronger toward the tip;
                    // side axis is tangential so the tentacle rolls under
                    const side = TMP.b.set(-Math.cos(tn.angle), 0, Math.sin(tn.angle));
                    for (let j = 1; j < tn.bones.length; j++) {
                        const tipness = j / (tn.bones.length - 1);
                        const wv = Math.sin(t * 2.1 + tn.k * 0.8 - j * 0.95) * 0.22 * (0.25 + 0.75 * tipness)
                            + (moving ? Math.sin(st.phase * Math.PI * 2 - j) * 0.1 : 0);
                        tn.bones[j].quaternion.setFromAxisAngle(side, wv);
                    }
                }
            } else if (stance === 'fish') {
                // swim: tail-amplified undulation (head steady, caudal whips),
                // hover at swim depth, bank into turns, pectorals flutter
                const depth = opts.swimDepth ?? 0.75;
                group.position.y = groundY + depth + Math.sin(t * 1.3) * 0.03;
                const freq = 3.5 + st.speed * 5, amp = (0.1 + Math.min(0.18, st.speed * 0.22)) * (0.3 + 0.7 * st.gaitAmt);
                st.gaitAmt += ((moving ? 1 : 0) - st.gaitAmt) * Math.min(1, dt * 3);
                for (let i = 0; i < spineBones.length; i++) {
                    const tailness = 1 - i / (spineBones.length - 1);
                    const wv2 = Math.sin(t * freq - i * 0.85) * amp * (0.12 + 0.88 * tailness * tailness);
                    // whale flukes beat VERTICALLY; fish tails sweep sideways
                    if (fishFluke) { spineBones[i].rotation.x = wv2; spineBones[i].rotation.y = 0; }
                    else spineBones[i].rotation.y = wv2;
                }
                for (const pf of pectorals) pf.rotation.z = pf.userData.side * (0.4 + Math.sin(t * 3.2 + pf.userData.side) * 0.28);
                const hr2 = st.prevHeading === undefined ? 0 : (st.heading - st.prevHeading) / Math.max(dt, 1e-3);
                st.bank += (Math.max(-0.45, Math.min(0.45, -hr2 * 0.5)) - st.bank) * Math.min(1, dt * 3);
                group.rotation.z = st.bank;
            } else if (stance === 'snail') {
                // glide with a slow peristaltic ripple down the foot
                group.position.y = groundY;
                st.gaitAmt += ((moving ? 1 : 0) - st.gaitAmt) * Math.min(1, dt * 2);
                for (let i = 0; i < spineBones.length; i++) {
                    spineBones[i].rotation.x = Math.sin(t * 2.6 - i * 0.9) * 0.022 * st.gaitAmt;
                }
            } else {
                const w = st.phase * Math.PI * 2;
                // gait envelope: motion eases in/out with speed so a stop
                // SETTLES instead of freezing mid-lean
                st.gaitAmt += ((moving ? 1 : 0) - st.gaitAmt) * Math.min(1, dt * 5);
                const g = st.gaitAmt;
                const breathe = Math.sin(t * 1.7) * 0.008;
                if (stance === 'biped') {
                    // ── human walk realism ──
                    // COM: two bobs per cycle — lowest just after each heel
                    // strike, highest passing over the planted foot
                    group.position.y = groundY + (-Math.cos(2 * w - 0.63)) * legLen * 0.018 * g + breathe;
                    // weight shift over the stance foot (pelvis slides laterally)
                    const lat = -Math.sin(w) * g;
                    spineBones[0].position.x = spineBones[0].userData.bindPos.x + lat * legLen * 0.05;
                    // pelvis yaws the swing hip forward; shoulders counter-
                    // rotate; pelvic list drops the swing-side hip; slight
                    // forward lean into the walk
                    const pYaw = Math.cos(w) * 0.09 * g;
                    const list = lat * 0.05;
                    let prevYaw = 0;
                    for (let i = 0; i < spineBones.length; i++) {
                        const f = i / (spineBones.length - 1);
                        const yawHere = pYaw * (1 - 1.8 * f);   // +pelvis → −0.8× chest
                        spineBones[i].rotation.y = yawHere - prevYaw; prevYaw = yawHere;
                        spineBones[i].rotation.z = i === 0 ? list : -list * 0.25;
                        spineBones[i].rotation.x = (0.013 + runF * 0.045) * g;   // runners lean in
                    }
                    // head faces the way we're going (cancels the shoulder yaw)
                    if (typeof neckBones !== 'undefined' && neckBones) {
                        const cancel = 0.8 * pYaw * 0.85 / neckBones.length;
                        for (let i = 0; i < neckBones.length; i++) neckBones[i].rotation.y = cancel;
                    }
                } else if (splayed) {
                    // arthropods ride LEVEL between their high knees — just a
                    // whisper of bob, plus abdomen bounce for spiders
                    group.position.y = groundY + Math.sin(w * 2) * legLen * 0.008 * g + breathe * 0.3;
                    if (stance === 'spider') spineBones[1].rotation.x = Math.sin(2 * w + 0.8) * 0.035 * g;
                } else if (stance === 'bird') {
                    // step bob + waddle roll + counterweight tail fan
                    group.position.y = groundY + (-Math.cos(2 * w - 0.5)) * legLen * 0.02 * g + breathe;
                    const waddle = Math.sin(w) * g;
                    for (let i = 0; i < spineBones.length; i++) {
                        spineBones[i].rotation.z = waddle * 0.05;
                        spineBones[i].rotation.y = waddle * 0.018;
                    }
                    if (tailFan) tailFan.rotation.x = (moving ? Math.sin(2 * w + 1.2) * 0.12 : Math.sin(t * 1.4) * 0.05) - 0.08;
                } else {
                    // quads/multileg: double-beat bob timed to the strikes,
                    // GIRDLE COUNTER-ROTATION (hips yaw with the hind stride,
                    // shoulders opposite — same trick as the human pelvis),
                    // roll, fore/aft weight pitch, head-nod into the steps
                    const gal = st.gaitMode === 'gallop' ? 1 : 0;
                    const bob = -Math.cos((2 - gal) * w - 0.5) * legLen * (0.028 + gal * 0.03) * g;
                    group.position.y = groundY + bob + breathe;
                    const sway = Math.sin(w) * g * (1 - gal * 0.7);
                    const pitch = Math.sin((2 - gal) * w - 0.9) * (0.018 + gal * 0.05) * g;   // gallop = bounding back-flex
                    const gYaw = sway * 0.055;
                    let prevGy = 0;
                    for (let i = 0; i < spineBones.length; i++) {
                        const f = i / (spineBones.length - 1);
                        const yawHere = gYaw * (1 - 1.9 * f);   // hips + → shoulders −
                        spineBones[i].rotation.y = yawHere - prevGy; prevGy = yawHere;
                        spineBones[i].rotation.z = sway * 0.028;
                        spineBones[i].rotation.x = pitch * (0.4 + 0.6 * f);
                    }
                    if (stance === 'quad' && typeof neckBones !== 'undefined' && neckBones) {
                        const nb = Math.sin(2 * w + 0.6) * 0.05 * g + Math.sin(t * 1.1) * 0.015 * (1 - g);
                        for (let i = 0; i < Math.min(3, neckBones.length); i++) neckBones[i].rotation.x = nb * (1 - i * 0.2);
                    }
                }
                // quad gait selection + smooth phase re-timing (~1s blend);
                // gallop drops the duty (suspension phase) and rocks the back
                if (stance === 'quad' && walkers.length === 4) {
                    const want = gaitFor(st.speed);
                    if (want !== st.gaitMode) {
                        st.gaitMode = want; setGaitPhases(want);
                        st.duty = want === 'gallop' ? 0.44 : want === 'trot' ? 0.55 : 0.65;
                        st.lift = legLen * (want === 'gallop' ? 0.16 : 0.09);
                    }
                    for (const l of walkers) {
                        let d = (l.phaseTarget - l.phase) % 1;
                        if (d > 0.5) d -= 1; if (d < -0.5) d += 1;
                        if (Math.abs(d) > 1e-4) l.phase = (l.phase + d * Math.min(1, dt * 1.6) + 1) % 1;
                    }
                }
                // bird head-bob with the steps
                if (stance === 'bird' && typeof neckBones !== 'undefined' && neckBones) {
                    const bobA = moving ? Math.sin(st.phase * Math.PI * 4) * 0.14 : Math.sin(t * 1.2) * 0.03;
                    for (let i = 0; i < neckBones.length - 1; i++) neckBones[i].rotation.x = bobA * (1 - i * 0.25);
                }

                // tail wag (idle) / follow-through (walking)
                for (let i = 0; i < tailBones.length; i++) {
                    tailBones[i].rotation.y = Math.sin((moving ? st.phase * Math.PI * 2 : t * 2.2) - i * 0.7) * (moving ? 0.18 : 0.12);
                }

                // legs: plant/swing cycle + analytic IK
                group.updateMatrixWorld(true);
                for (const l of legs) {
                    if (l.isArm) {
                        // counter-swing: an arm peaks BACK exactly when its
                        // own-side leg strikes — that's cos of the gait phase
                        // (the old sin ran a quarter-cycle late)
                        const amp = 0.26 + Math.min(0.45, st.speed * 0.45);
                        const swing = Math.cos(w + (l.side < 0 ? 0 : Math.PI)) * amp * g
                            + Math.sin(t * 1.3) * 0.06 * (1 - g);   // idle: gentle hang-sway
                        l.hip.quaternion.setFromEuler(new THREE.Euler(swing, 0, l.side * 0.14));
                        // elbows flex FORWARD (a positive X here reads as a
                        // backward elbow — user-caught): a real RELAXED bend
                        // at all times, deeper as the arm swings ahead
                        l.knee.quaternion.setFromEuler(new THREE.Euler(-(0.42 + Math.max(0, -swing) * 0.55), 0, 0));
                        continue;
                    }
                    l.hip.updateWorldMatrix(true, false);
                    const hipW = tmpW.setFromMatrixPosition(l.hip.matrixWorld);
                    const reach = (l.L1 + l.L2) * 0.96;
                    // home = lateral offset (wide for splayed arthropods) +
                    // fore/aft fan (front spider legs reach ahead, rear back)
                    const out = l.out ?? 0.02, fan = l.fan ?? 0;
                    const homeX = hipW.x + fwd.z * l.side * out + fwd.x * fan;
                    const homeZ = hipW.z - fwd.x * l.side * out + fwd.z * fan;
                    // the ankle plants ankleLift ABOVE ground so the foot's
                    // sole rests ON it instead of sinking a half-foot in
                    const gy = groundY + (l.ankleLift || 0);
                    if (!l.planted) {
                        l.plant.set(homeX, gy, homeZ); l.next.copy(l.plant); l.planted = true;
                    }
                    let footPos;
                    let heelPitch = 0;   // biped heel-toe roll (toe-up < 0 < toe-down)
                    if (!moving) {
                        footPos = l.plant.lerp(TMP.a.set(homeX, gy, homeZ), Math.min(1, dt * 4));
                    } else {
                        const ph = (st.phase + l.phase) % 1;
                        if (ph < st.duty) {
                            // commit the landing on the swing->stance TRANSITION
                            // (a 's > 0.98' window gets stepped over at real
                            // frame rates — the plant then never updates and
                            // the leg SNAPS back to its old spot)
                            if (l.wasSwinging) { l.plant.copy(l.next); l.wasSwinging = false; }
                            footPos = l.plant;   // stance: pinned to the ground
                            // anti-drag: if the body has advanced so far the
                            // planted foot would lock the knee straight and
                            // drag, re-plant ahead instead of stretching
                            const behind = (hipW.x - l.plant.x) * fwd.x + (hipW.z - l.plant.z) * fwd.z;
                            if (behind > st.stride * 0.8) {   // backstop only
                                l.plant.set(homeX + fwd.x * st.stride * 0.4, gy, homeZ + fwd.z * st.stride * 0.4);
                            }
                            if (stance === 'biped') {
                                // heel-toe roll: strike toe-up → flat →
                                // pivot onto the ball as the heel peels off
                                const sst = ph / st.duty;
                                if (sst < 0.22) heelPitch = -0.26 * (1 - sst / 0.22) * g;
                                else if (sst > 0.68) {
                                    const hr = (sst - 0.68) / 0.32;
                                    heelPitch = 0.62 * hr * hr * g;
                                    footPos = TMP.c.copy(l.plant);          // don't mutate the plant
                                    footPos.y += hr * hr * legLen * 0.1 * g; // ankle rises over the toe
                                    footPos.addScaledVector(fwd, hr * hr * 0.05 * g);
                                }
                            } else if (stance === 'quad') {
                                // paws: a milder toe-off pivot only
                                const sst = ph / st.duty;
                                if (sst > 0.72) { const hr = (sst - 0.72) / 0.28; heelPitch = 0.3 * hr * hr * g; }
                            }
                        } else {
                            const s = (ph - st.duty) / (1 - st.duty);
                            // next plant lands ahead of the hip's future position
                            // land duty/2 ahead of the hip: the stance then
                            // carries the body over the foot so it exits duty/2
                            // BEHIND — legs swing through, not perpetual reach
                            const ahead = st.stride * (st.duty * 0.5 + 0.08);
                            l.next.set(homeX + fwd.x * ahead, gy, homeZ + fwd.z * ahead);
                            const e = s * s * (3 - 2 * s);
                            footPos = TMP.a.copy(l.plant).lerp(l.next, e);
                            footPos.y = gy + Math.sin(s * Math.PI) * st.lift;
                            l.wasSwinging = true;
                            // swing: release the toe-off pitch, cock toe-up for the strike
                            if (stance === 'biped') heelPitch = (0.5 * (1 - s) * (1 - s) - 0.24 * s * s) * g;
                            else if (stance === 'quad') heelPitch = 0.22 * (1 - s) * (1 - s) * g;   // paw trails, flattens to land
                        }
                    }
                    // clamp unreachable targets HORIZONTALLY (pulling the
                    // foot toward the hip rides it up the torso, then it
                    // snaps down at the next plant — the stuck-then-shoot look)
                    const dy = footPos.y - hipW.y;
                    const horizMax = Math.sqrt(Math.max(0.01, reach * reach - dy * dy));
                    const dx = footPos.x - hipW.x, dz = footPos.z - hipW.z;
                    const dh = Math.hypot(dx, dz);
                    if (dh > horizMax) {
                        footPos = TMP.a.set(
                            hipW.x + (dx / dh) * horizMax, footPos.y,
                            hipW.z + (dz / dh) * horizMax);
                    }
                    // arthropod knees bend UP-AND-OUT, not forward
                    const pole = splayed ? TMP.d.set(fwd.z * l.side, 1.4, -fwd.x * l.side) : fwd;
                    solveLegIK(l.hip, l.knee, l.ankle, footPos, pole, l.L1, l.L2);
                    // foot: face the heading, flat on the ground plus the
                    // heel-toe roll (pitch applied in the heading frame)
                    if (l.foot) {
                        l.ankle.updateWorldMatrix(true, false);
                        const aq = l.ankle.getWorldQuaternion(TMP.q);
                        l.foot.quaternion.copy(aq.invert()).multiply(TMP.q2.setFromEuler(new THREE.Euler(heelPitch, st.heading, 0, 'YXZ')));
                    }
                }
            }

            // ear flick — a quick single-ear twitch every few seconds
            if (earPivots.length && t > st.earFlickAt) {
                const fe = t - st.earFlickAt;
                const ear = earPivots[st.earFlickSide % earPivots.length];
                if (fe > 0.4) { ear.rotation.x = 0; st.earFlickAt = t + 2 + rng() * 4; st.earFlickSide = Math.floor(rng() * 17); }
                else ear.rotation.x = Math.sin((fe / 0.4) * Math.PI * 2) * 0.3;
            }
            // antennae: constant slow feel-around
            for (const an of antennae) an.rotation.x = Math.sin(t * 2.2 + an.userData.k) * 0.14 - 0.08;
            // trunk: idle sway + stride swing
            if (typeof trunkG !== 'undefined' && trunkG) {
                trunkG.rotation.x = Math.sin(t * 0.9) * 0.08 + Math.sin(st.phase * Math.PI * 2) * 0.1 * st.gaitAmt;
                trunkG.rotation.z = Math.sin(t * 0.7) * 0.06;
            }
            // back tentacles: slow writhe, stronger toward the tips
            for (const bt of backTents) {
                for (let j = 1; j < bt.bones.length; j++) {
                    const tipness = j / (bt.bones.length - 1);
                    bt.bones[j].quaternion.setFromAxisAngle(bt.axis,
                        Math.sin(t * 1.9 + bt.k * 1.1 - j * 0.85) * 0.24 * (0.2 + 0.8 * tipness));
                }
            }

            // wings — asymmetric flap airborne (fast downstroke, the hand
            // lags the arm), buzzing membranes for insects, folded flutter
            // on the ground with the hand tucked back along the body
            const flying = (st.flyAlt || 0) > 0.01 && wings.length > 0;
            for (const wg of wings) {
                if (wg.butterfly) {
                    if (flying) {
                        // biased stroke: wings meet UP (+1.4) and stop just
                        // below horizontal (−0.3) — a symmetric ± swing beat
                        // straight through the body (user-caught)
                        const wb2 = t * 3.4 + wg.k;
                        wg.root.rotation.set(0, wg.side * -0.06, wg.side * (0.55 + Math.sin(wb2) * 0.85));
                    } else {
                        // rest: wings held upright over the back, slow fanning
                        wg.root.rotation.set(0, wg.side * 0.08, wg.side * (1.2 + Math.sin(t * 1.1 + wg.k) * 0.22));
                    }
                    continue;
                }
                if (wg.buzz) {
                    if (flying || moving) {
                        wg.root.rotation.set(0, wg.side * -0.1,
                            wg.side * (0.25 + Math.sin(t * 21 + wg.side + wg.k * 1.7) * (flying ? 0.55 : 0.18)));
                    } else {
                        wg.root.rotation.set(0.06, wg.side * 1.15, wg.side * 0.1);   // parked over the abdomen
                    }
                    continue;
                }
                if (flying) {
                    const wb = t * 5.4;
                    const stroke = Math.sin(wb) + 0.3 * Math.sin(wb * 2 + 1.2);
                    // fore-aft sweep coupled to the stroke (figure-8 hint) +
                    // hand lag + feather pitch through the stroke
                    wg.root.rotation.set(0, wg.side * (-0.12 + Math.sin(wb - 1.3) * 0.14), wg.side * (0.12 + stroke * 0.5));
                    if (wg.outer) wg.outer.rotation.set(Math.sin(wb - 0.9) * 0.14, 0, wg.side * Math.sin(wb - 0.7) * 0.5);
                } else {
                    const flutter = Math.sin(t * (moving ? 3.4 : 1.6)) * 0.05;
                    wg.root.rotation.set(0, wg.side * 0.5, wg.side * (wg.root.userData.fold + flutter));
                    if (wg.outer) wg.outer.rotation.set(0, wg.side * 1.8, wg.side * -0.12);
                }
            }
            if (flying) {
                // climb/hold altitude with a soar bob; tuck the legs; pitch
                // into climbs and bank into turns; ground gait is skipped
                if (st.airY === undefined) st.airY = group.position.y;
                st.airY += ((groundY + st.flyAlt) - st.airY) * Math.min(1, dt * 1.5);
                group.position.y = st.airY + Math.sin(t * 3.1) * 0.05;
                const headingRate = st.prevHeading === undefined ? 0 : (st.heading - st.prevHeading) / Math.max(dt, 1e-3);
                st.bank += (Math.max(-0.5, Math.min(0.5, -headingRate * 0.4)) - st.bank) * Math.min(1, dt * 3);
                const climb = (groundY + st.flyAlt) - st.airY;
                st.pitch += (Math.max(-0.3, Math.min(0.35, climb * 0.4)) - st.pitch) * Math.min(1, dt * 2.5);
                group.rotation.x = -st.pitch;   // nose up into a climb
                group.rotation.z = st.bank;
                for (const l of legs) {
                    if (l.isArm) continue;
                    if (splayed) {
                        // splayed legs bind UP-AND-OUT — tuck must rotate them
                        // DOWN against the body (positive-z lift folded them
                        // over the back: 'flying upside down', user-caught)
                        l.hip.quaternion.setFromEuler(new THREE.Euler(0.3, 0, -l.side * 1.1));
                        l.knee.quaternion.setFromEuler(new THREE.Euler(0.5, 0, l.side * 0.3));
                    } else {
                        l.hip.quaternion.setFromEuler(new THREE.Euler(-0.85, 0, l.side * 0.1));
                        l.knee.quaternion.setFromEuler(new THREE.Euler(1.25, 0, 0));
                    }
                    l.planted = false;
                }
                st.prevHeading = st.heading;
                return;   // skip ground gait + ground bob
            } else {
                // level the attitude back out on the ground
                st.bank *= Math.max(0, 1 - dt * 4);
                st.pitch *= Math.max(0, 1 - dt * 4);
                if (stance !== 'serpent') { group.rotation.x = -st.pitch; group.rotation.z = st.bank; }
                if (st.airY !== undefined) {
                    // landing: sink back to the gait's ground height
                    st.airY += (groundY - st.airY) * Math.min(1, dt * 1.5);
                    if (Math.abs(st.airY - groundY) < 0.02) st.airY = undefined;
                    else group.position.y = st.airY;
                }
            }
            st.prevHeading = st.heading;

            // blink (snakes/fish/snails have no eyelids; compound eyes don't blink)
            if (stance !== 'serpent' && stance !== 'fish' && stance !== 'snail' && !splayed && t > st.blinkAt) {
                for (const e of eyeMeshes) e.scale.y = 0.12;
                if (t > st.blinkAt + 0.12) {
                    for (const e of eyeMeshes) e.scale.y = 1;
                    st.blinkAt = t + 1.5 + rng() * 3.5;
                }
            }

            // talking — flap the hinged jaw from st.talk (api.say / api.talking /
            // api.setTalkEnvelope). Procedural mode gates syllables at ~4.3Hz
            // with per-syllable amplitude variation; envelope mode maps an
            // audio-amplitude fn (t)=>0..1 straight onto the jaw for lipsync.
            if (jawRig) {
                const tk = st.talk;
                let want = 0;
                if (tk) {
                    if (tk.until == null && tk.dur != null) tk.until = t + tk.dur;
                    if (tk.env) want = Math.max(0, Math.min(1, tk.env(t) || 0));
                    else if (t < (tk.until ?? Infinity)) {
                        st.talkSeed = st.talkSeed ?? rng() * 6.283;
                        const E = tk.energy ?? 0.85;
                        const sy = Math.sin(t * 27.2 + st.talkSeed) * 0.5 + 0.5;
                        const am = 0.55 + 0.45 * Math.sin(t * 7.31 + st.talkSeed * 1.7);
                        want = E * Math.max(0, sy * am - 0.08);
                    } else st.talk = null;
                }
                st.jawOpen = (st.jawOpen || 0) + (want - (st.jawOpen || 0)) * Math.min(1, dt * 16);
                jawRig.g.quaternion.copy(jawRig.rest);
                if (st.jawOpen > 0.001) {
                    jawRig._q = jawRig._q || new THREE.Quaternion();
                    jawRig._q.setFromAxisAngle(jawRig.axis, st.jawOpen * jawRig.max);
                    jawRig.g.quaternion.multiply(jawRig._q);
                }
                if (jawRig.inner) jawRig.inner.visible = st.jawOpen > 0.08;
            }
        }

        const api = {
            group, skeleton, bones: allBones, legs, headBone, update,
            // named part lookup — every add-on mesh carries a .name
            // ('shell','claw','horn','armor','spike','mask','helmet','gill',
            // 'antenna','eyestalk',...). Agents can swap materials directly:
            //   c.parts('shell')[0].traverse(o => { if (o.isMesh) o.material = myMat; })
            parts(n) { const out = []; group.traverse((o) => { if (o.name === n) out.push(o); }); return out; },
            // named mount ANCHORS for the robotics kit: bones are Object3Ds,
            // so RoboticsKit.connect(c.anchor('wristR'), module) rides the
            // living skeleton. 'head'|'chest'|'back'|'hips'|'wristL'|'wristR'.
            // Recipes: HEAD SWAP — hide the organic head first:
            //   c.anchor('head').children.forEach(o => o.visible = false);
            //   RoboticsKit.connect(c.anchor('head'), makeBot({ head: {...} }).head);
            // ROBOT HAND — c.parts('hand')[i].visible = false; connect at the wrist.
            anchor(n) {
                if (n === 'head') return headBone;
                if (n === 'chest' || n === 'back') {
                    return (headBone && headBone.parent && headBone.parent.isBone) ? headBone.parent : allBones[allBones.length - 1];
                }
                if (n === 'hips') return allBones[0];
                if (n === 'wristL' || n === 'wristR') {
                    const side = n === 'wristL' ? -1 : 1;
                    const arm = legs.find((l) => l.isArm && l.side === side);
                    return arm ? arm.ankle : null;
                }
                return null;
            },
            get speed() { return st.speed; }, set speed(v) { st.speed = v; },
            get turn() { return st.turn; }, set turn(v) { st.turn = v; },
            // TALKING — flap the hinged jaw (skull chin / muzzle lower jaw /
            // beak mandible; serpents+fish have no jaw and ignore this).
            //   c.say('Some words to speak')       // duration from word count
            //   c.say({ duration: 4, energy: 0.9 })
            //   c.talking = true;                  // continuous until = false
            //   c.setTalkEnvelope((t) => amp01)    // drive from an audio envelope
            say(o) {
                if (typeof o === 'string') o = { duration: Math.max(1.2, o.split(/\s+/).length / 2.6) };
                st.talk = { dur: (o && o.duration) ?? 3, until: null,
                    energy: (o && o.energy) ?? 0.85, env: (o && o.envelope) || null };
                return api;
            },
            get talking() { return !!st.talk; },
            set talking(v) { st.talk = v ? { until: Infinity, energy: 0.85, env: null } : null; },
            setTalkEnvelope(fn) { st.talk = fn ? { until: Infinity, env: fn } : null; return api; },
            get hasJaw() { return !!jawRig; },
            setHeading(a) { st.heading = a; },
            fly(altitude = 1.6, speed) {
                st.flyAlt = altitude;
                if (speed != null) st.speed = speed; else st.speed = Math.max(st.speed, 0.9);
            },
            land() { st.flyAlt = 0; },
            walkTo(x, z, speed) { st.target = { x, z }; if (speed != null) st.speed = speed; else if (st.speed < 0.05) st.speed = 0.5; },
        };
        if (opts.auto !== false) {
            (globalThis._autoCreatures || (globalThis._autoCreatures = [])).push(update);
        }
        return api;
    };

    // a clothed human(oid): biped proportions + sculpted skull head + outfit bands
    globalThis.makeCreature.human = function (o = {}) {
        return {
            stance: 'biped', headType: 'skull', bodyLength: 0.62, bodyRadius: 0.155, neck: 0.13,
            tail: 0, legLength: 0.8, armLength: 0.62, headScale: 0.85,
            eyes: 2, hands: 1, horns: 0, fins: 0,
            hair: o.hair ?? 'cap', hairColor: o.hairColor ?? 0x3a2a1a,
            eyeColor: o.eyeColor ?? 0x4a6d8c,
            pattern: 'plain',
            color: o.skin ?? 0xd9a37f, skin: o.skin ?? 0xd9a37f,
            belly: o.skin ?? 0xd9a37f, accent: 0x333333,
            outfit: { shirt: o.shirt ?? 0x3a6ea8, pants: o.pants ?? 0x35322e, shoes: o.shoes ?? 0x221d18 },
            speed: o.speed ?? 0.45, seed: o.seed ?? 1,
            ...o,
        };
    };

    // seeded surprise-me morphology (Spore energy)
    globalThis.makeCreature.random = function (seed = 1) {
        const r = mulberry(seed);
        const stances = ['quad', 'quad', 'quad', 'biped', 'serpent', 'octopus', 'bird', 'insect', 'spider', 'fish'];
        const stance = stances[Math.floor(r() * stances.length)];
        const pairs = (stance === 'serpent' || stance === 'octopus' || stance === 'fish') ? 0
            : (stance === 'biped' || stance === 'bird') ? 1
            : stance === 'insect' ? 3 : stance === 'spider' ? 4 : (2 + Math.floor(r() * 2));
        const hueA = r(), hueB = (hueA + 0.35 + r() * 0.3) % 1;
        const col = (h, s, l) => new THREE.Color().setHSL(h, s, l).getHex();
        return {
            seed, stance, legPairs: pairs,
            bodyLength: (stance === 'serpent' ? 2.2 : stance === 'insect' || stance === 'spider' ? 0.8 : 1.2) * (0.8 + r() * 0.7),
            bodyRadius: (stance === 'insect' ? 0.11 : stance === 'spider' ? 0.15 : 0.16) + r() * 0.12,
            neck: stance === 'serpent' ? 0 : 0.3 + r() * 0.4,
            tail: r() * 1.3,
            legLength: 0.55 + r() * 0.5,
            eyes: 1 + Math.floor(r() * 3),
            horns: Math.floor(r() * 3),
            hornStyle: ['spike', 'spike', 'ram', 'antler'][Math.floor(r() * 4)],
            ears: stance === 'quad' ? ['point', 'point', 'flop', 'round'][Math.floor(r() * 4)] : 0,
            muzzle: stance === 'quad' ? 0.7 + r() * 0.7 : 0,
            tusks: stance === 'quad' && r() < 0.25 ? 1 : 0,
            fangs: stance === 'quad' && r() < 0.3 ? 1 : 0,
            trunk: stance === 'quad' && r() < 0.1 ? 1 : 0,
            eyelids: r() < 0.25 ? 0.7 : 0.3,
            fins: stance === 'serpent' ? 3 + Math.floor(r() * 3) : stance === 'fish' ? 1 + Math.floor(r() * 2) : Math.floor(r() * 2),
            wings: stance === 'bird' ? 2 : stance === 'insect' ? (r() < 0.4 ? 4 : 2) : (r() < 0.12 ? 2 : 0),
            pattern: ['plain', 'spots', 'stripes'][Math.floor(r() * 3)],
            color: col(hueA, 0.45, 0.42), accent: col(hueB, 0.5, 0.3),
            belly: col(hueA, 0.25, 0.72),
            speed: 0.35 + r() * 0.4,
        };
    };

    console.log('[creature_builder] makeCreature ready — spine+limbs auto-rig (shared Skeleton, analytic skin weights), morphology-adaptive gait (path-following serpent / human-detail biped / trot / wave), skull heads via makeCreature.human(), makeCreature.random(seed)');
})();
