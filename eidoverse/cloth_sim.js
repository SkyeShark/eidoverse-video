// cloth_sim.js
//
// Mass-spring cloth on a grid, simulated with WebGPU compute shaders.
// Ports the race-free per-vertex force-GATHER pattern from the three.js
// webgpu_compute_cloth example (each vertex reads its own springs and
// writes only itself — no scatter, no constraint graph-coloring needed).
//
// Use for free cloth panels: flags, banners, curtains, capes, hanging
// fabric, sails, tapestries. Pin any subset of vertices (a flag pins
// one edge; a hanging banner pins the top row; a cape pins the
// shoulders). Wind + gravity + sphere colliders supported.
//
// NOT for skin-tight clothing that follows a rigged character — that
// needs skinned-mesh cloth (three-simplecloth) which is a different
// beast. This is for fabric that hangs and flows in the world.
//
// Agent API
// ---------
//
//   import { createClothPanel } from globalThis.EIDOVERSE_DIR + 'cloth_sim.js';
//
//   const cloth = await createClothPanel(renderer, {
//       width: 3, height: 2,        // world-space panel size (meters)
//       cols: 40, rows: 28,         // grid resolution
//       stiffness: 0.9,             // 0..1, spring strength
//       damping: 0.97,             // velocity retention per step
//       gravity: [0, -0.0006, 0],
//       wind: 0.0004,               // GUST strength (zero-mean flutter)
//       windBias: 0.15,             // constant-push fraction of `wind`
//       windDir: [0, 0, 1],         // push direction (panel local; face = ±Z)
//       settleSteps: 60,            // pre-roll so frame 0 is draped fabric
//       material: new THREE.MeshStandardNodeMaterial({
//           color: 0xff2d95, roughness: 0.6, metalness: 0.0,
//           side: THREE.DoubleSide,
//       }),
//       pin: 'top',                 // 'top' | 'top-corners' | 'left' | array of vertex indices | fn(col,row)=>bool
//   });
//
//   RECIPES — pick by what the fabric is DOING:
//     hanging banner / tapestry / curtain (gentle sway):
//         wind: 0.0003-0.0006, windBias: 0 - 0.2, settleSteps: 60
//     streaming flag in strong wind:
//         wind: 0.0006-0.001, windBias: 0.8-1.0,
//         windDir pointed where the flag should stream
//   `wind` is a per-substep impulse — 0.001 is already a STRONG gale.
//   Do NOT crank wind to "add life": high bias + high wind blows hanging
//   fabric horizontal and (pre-fix) stretched it into streaks. The sim now
//   velocity-clamps + strain-corrects so it can't streak, but a banner in
//   a wind tunnel still LOOKS wrong.
//
//   cloth.mesh.position.set(0, 3, -4);
//   scene.add(cloth.mesh);
//
//   // Each frame (run the solver a few iterations for stability):
//   cloth.step();
//
//   // COLLISION (world space). Easiest: hand it scene objects — it derives
//   // colliders from their bounding volumes so the fabric respects the set:
//   cloth.collideWith([booth, table, wall]);          // boxes (walls/props), up to 8
//   cloth.collideWith([character], { asSphere: true, track: true }); // sphere; track → re-derived every step() for a MOVING character/prop (no need to re-call)
//   cloth.floor = 0;                                    // ground plane (no sinking)
//   // or set them by hand (up to 8 of each):
//   cloth.setColliders([{ center: [0, 2, -4], radius: 0.6 }]);          // spheres
//   cloth.setBoxColliders([{ min: [-1,0,-5], max: [1,3,-4.8] }]);       // AABBs
//   // Cloth rests `opts.thickness` (default 0.03m) PROUD of every collider — the
//   // collision SKIN. Raise it for thick/heavy fabric or coarse cloth that still
//   // pokes through; lower it for a thin sheet hugging a surface. For STATIC
//   // geometry collideWith once is enough; for moving objects use { track: true }.
//
//   // TEXT / LOGO ON THE BANNER: bake it INTO the cloth's map so it rides the
//   // fold + sway — do NOT float a separate plane in front (it detaches +
//   // z-fights). Pass a canvas/texture as opts.map (or set mat.map yourself):
//   //   const kit = makeCanvasTexture(1024, 512, drawBannerArt);
//   //   createClothPanel(renderer, { ..., map: kit.texture });
//
//   // Move pinned points at runtime (e.g. a waving flagpole, a cape on
//   // a walking character) — write world-space positions for pinned ids:
//   cloth.setPinPosition(vertexIndex, [x, y, z]);

import {
    Fn, instancedArray, instanceIndex, vertexIndex, vec3, float, uint, int,
    positionLocal, normalLocal, uniform, If, Loop, transformNormalToView,
} from 'npm:three@0.184.0/tsl';

export async function createClothPanel(renderer, opts = {}) {
    (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('cloth_sim');
    const THREE = globalThis.THREE;

    const W = opts.width  ?? 3;
    const H = opts.height ?? 2;
    const COLS = opts.cols ?? 40;
    const ROWS = opts.rows ?? 28;
    const N = COLS * ROWS;
    const stiffnessVal = opts.stiffness ?? 0.9;
    const dampingVal   = opts.damping ?? 0.97;
    // `wind` is a SCALAR strength here (the direction is `windDir`). But agents
    // routinely pass a VECTOR — the shape `setWindDir`/most wind APIs use — and
    // a vector reaching the scalar slot became `uniform(float([x,y,z]))`, which
    // the WGSL backend can't type → the cryptic "Uniform \"null\" not
    // implemented" crash AT RENDER (lazy shader compile, so it slips past
    // setup try/catch and kills the whole render). Accept the vector gracefully:
    // use it as the DIRECTION and keep the default scalar strength. We do NOT
    // map its magnitude to strength — a typical direction vector is ~1000× the
    // 0.0003–0.001 scale `wind` works at, which would blow the cloth into the
    // gale/streak failure the HISTORY note below warns about. For explicit
    // strength, pass a scalar `wind` (+ optional `windDir`).
    let windVal, windFromVec = null;
    if (Array.isArray(opts.wind)) {
        windFromVec = opts.wind;
        windVal = 0.0004;
        console.warn(
            `[cloth_sim] createClothPanel: 'wind' was given as a vector ` +
            `[${opts.wind.map(n => (+n).toFixed(2)).join(', ')}] — using it as the wind ` +
            `DIRECTION (windDir) with the default gentle strength. Pass a scalar 'wind' ` +
            `(e.g. 0.0004–0.001) for strength, and 'windDir' for direction.`
        );
    } else {
        windVal = opts.wind ?? 0.0004;
    }
    const grav = opts.gravity ?? [0, -0.0006, 0];
    // wind DIRECTION (local space; panel is built in the XY plane so its
    // face normal is ±Z) and BIAS: the gust term is zero-mean flutter; the
    // bias is the constant-push fraction of `wind` along windDir.
    // HISTORY: the original kernel pushed +Z with a strictly-positive
    // (1+sin) profile — i.e. a constant gale, not a breeze. Hanging
    // banners streamed toward the camera and stretched into streaks
    // (corrupted_theology_broadcast). Default bias is now a gentle 0.15;
    // pass windBias ~0.8-1 + a windDir if you WANT a streaming flag.
    // Explicit windDir wins; else a vector passed as `wind` supplies direction;
    // else default forward (+Z, the panel's face normal).
    const windDirSrc = opts.windDir ?? windFromVec ?? [0, 0, 1];
    // Coerce to exactly 3 finite components so a malformed array (wrong length
    // or NaN) can't produce a vec3 uniform with an undefined lane — which would
    // just be the same "Uniform null" crash in a new place.
    const windDirRaw = [0, 0, 1].map((d, k) =>
        Number.isFinite(windDirSrc?.[k]) ? windDirSrc[k] : d);
    const wdLen = Math.hypot(...windDirRaw) || 1;
    const windDirN = windDirRaw.map(v => v / wdLen);
    const windBiasVal = opts.windBias ?? 0.15;

    const idx = (c, r) => r * COLS + c;

    // --- Build initial grid positions (panel in XY plane, local space) ---
    const pos     = new Float32Array(N * 3);
    const prevPos = new Float32Array(N * 3);
    const fixed   = new Float32Array(N);  // 1 = pinned
    for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
            const i = idx(c, r);
            const x = (c / (COLS - 1) - 0.5) * W;
            const y = (0.5 - r / (ROWS - 1)) * H;   // row 0 = top
            pos[i*3] = x; pos[i*3+1] = y; pos[i*3+2] = 0;
            prevPos[i*3] = x; prevPos[i*3+1] = y; prevPos[i*3+2] = 0;
        }
    }

    // --- Pinning ---
    const pinSpec = opts.pin ?? 'top';
    const isPinned = (c, r) => {
        if (Array.isArray(pinSpec)) return pinSpec.includes(idx(c, r));
        if (typeof pinSpec === 'function') return !!pinSpec(c, r);
        switch (pinSpec) {
            case 'top':         return r === 0;
            case 'top-corners': return r === 0 && (c === 0 || c === COLS - 1);
            case 'left':        return c === 0;
            case 'none':        return false;
            default:            return r === 0;
        }
    };
    for (let r = 0; r < ROWS; r++)
        for (let c = 0; c < COLS; c++)
            fixed[idx(c, r)] = isPinned(c, r) ? 1 : 0;

    const posBuf  = instancedArray(pos, 'vec3').setName('ClothPos');
    const prevBuf = instancedArray(prevPos, 'vec3').setName('ClothPrev');
    const fixedBuf = instancedArray(fixed, 'float').setName('ClothFixed');

    // Neighbor rest-length spans: structural (1), shear (diag), bend (2).
    // Each vertex GATHERS spring forces from up to 12 neighbors. Reading
    // neighbors + writing only self = race-free on GPU.
    const restStruct = W / (COLS - 1);
    const restStructV = H / (ROWS - 1);
    const restShear  = Math.hypot(restStruct, restStructV);
    const restBendH  = restStruct * 2;
    const restBendV  = restStructV * 2;

    const stiffness = uniform(float(stiffnessVal));
    const damping   = uniform(float(dampingVal));
    const wind      = uniform(float(windVal));
    const windBias  = uniform(float(windBiasVal));
    const windDir   = uniform(vec3(windDirN[0], windDirN[1], windDirN[2]));
    const tUni      = uniform(float(0));
    const colCount  = uniform(int(0));
    const boxCount  = uniform(int(0));
    // Collisions run in WORLD space. The sim itself is LOCAL (panel built around
    // origin, placed via mesh.position), so we add this offset before collider
    // tests and subtract after — agents pass world-space colliders / scene
    // objects, not local ones. (The old sphere path compared local positions to
    // world centers and silently missed.)
    const meshOffset = uniform(vec3(0, 0, 0));
    const floorY     = uniform(float(opts.floor ?? -1e9));  // world Y floor plane; default off
    const skin       = uniform(float(opts.thickness ?? 0.03));  // collision SKIN — cloth rests this far PROUD of every collider, hiding the half-fold overlap + between-vertex pokes that read as "clipping". Raise for thicker fabric / coarser cloth.
    // up to 8 sphere colliders (cx,cy,cz,radius) + 8 box/AABB colliders (min,max)
    const collArr   = instancedArray(new Float32Array(8 * 4), 'vec4').setName('ClothColliders');
    const boxMinArr = instancedArray(new Float32Array(8 * 3), 'vec3').setName('ClothBoxMin');
    const boxMaxArr = instancedArray(new Float32Array(8 * 3), 'vec3').setName('ClothBoxMax');

    const COLS_u = uint(COLS), ROWS_u = uint(ROWS);

    const computeKernel = Fn(() => {
        const i = instanceIndex;
        const isFix = fixedBuf.element(i);

        If(isFix.greaterThan(0.5), () => {
            // pinned — position is driven externally via setPinPosition
            prevBuf.element(i).assign(posBuf.element(i));
        }).Else(() => {
            const p  = posBuf.element(i).toVar();
            const pp = prevBuf.element(i).toVar();

            const c = i.mod(COLS_u);
            const r = i.div(COLS_u);

            // Jacobi constraint relaxation: accumulate the AVERAGE positional
            // correction over all connected springs, then apply it scaled by
            // stiffness. Bounded by construction → cannot explode (unlike raw
            // Hookean force accumulation, which overshoots and diverges).
            const corr = vec3(0, 0, 0).toVar();
            const cnt  = float(0).toVar();
            const addSpring = (cc, rr, rest) => {
                If(cc.greaterThanEqual(uint(0)).and(cc.lessThan(COLS_u))
                   .and(rr.greaterThanEqual(uint(0))).and(rr.lessThan(ROWS_u)), () => {
                    const np = posBuf.element(rr.mul(COLS_u).add(cc));
                    const d  = np.sub(p);
                    const len = d.length().max(1e-5);
                    // Move halfway to rest length (neighbor does the other
                    // half), ramping toward a STRONGER correction as the
                    // spring over-stretches — anti-streak. The ramp is smooth
                    // and capped at 0.85: a hard 0.5→1.0 step at 15% made
                    // threshold-straddling vertices flip-flop every step
                    // (full correction from BOTH ends overshoots), which
                    // showed as a sawtooth zigzag along the free edges where
                    // few springs average it out.
                    // rest is a plain JS number (not a node) — multiply in JS
                    const w = len.div(float(rest)).sub(1.10).div(0.25)
                        .clamp(0.0, 1.0).mul(0.35).add(0.5);
                    corr.addAssign(d.div(len).mul(len.sub(rest).mul(w)));
                    cnt.addAssign(1);
                });
            };
            // NOTE: uint underflow guard — only subtract when > 0.
            If(c.greaterThan(uint(0)),        () => addSpring(c.sub(uint(1)), r, restStruct));
            addSpring(c.add(uint(1)), r, restStruct);
            If(r.greaterThan(uint(0)),        () => addSpring(c, r.sub(uint(1)), restStructV));
            addSpring(c, r.add(uint(1)), restStructV);
            // shear
            If(c.greaterThan(uint(0)).and(r.greaterThan(uint(0))), () => addSpring(c.sub(uint(1)), r.sub(uint(1)), restShear));
            If(r.greaterThan(uint(0)),        () => addSpring(c.add(uint(1)), r.sub(uint(1)), restShear));
            If(c.greaterThan(uint(0)),        () => addSpring(c.sub(uint(1)), r.add(uint(1)), restShear));
            addSpring(c.add(uint(1)), r.add(uint(1)), restShear);
            // bend
            If(c.greaterThan(uint(1)),        () => addSpring(c.sub(uint(2)), r, restBendH));
            addSpring(c.add(uint(2)), r, restBendH);
            If(r.greaterThan(uint(1)),        () => addSpring(c, r.sub(uint(2)), restBendV));
            addSpring(c, r.add(uint(2)), restBendV);

            // External forces (gravity + wind) as a small per-step impulse.
            // Wind = windDir × wind × (bias + zero-mean gust): flutter with
            // only a gentle net push by default (see windBias note above).
            const ext = vec3(grav[0], grav[1], grav[2]).toVar();
            const fc = float(c), fr = float(r);
            // gentle spatial phase (0.12/0.3 per col/row) — steeper phases
            // push adjacent columns in opposite directions and CURL the free
            // edges inward (banners neck into a carrot shape).
            const gust = fc.mul(0.12).add(tUni.mul(2)).sin()
                .add(fr.mul(0.3).add(tUni.mul(3.1)).sin().mul(0.5)).mul(0.6);
            ext.addAssign(windDir.mul(wind.mul(windBias.add(gust))));
            ext.y.addAssign(wind.mul(0.15).mul(fr.mul(0.25).add(tUni.mul(1.7)).sin()));

            // Verlet integrate, then apply the averaged spring correction.
            // Velocity is hard-clamped to a fraction of the rest spacing per
            // step — runaway streaming is impossible regardless of forces.
            const vel = p.sub(pp).mul(damping).toVar();
            const vLen = vel.length().max(1e-6);
            const vMax = float(Math.min(restStruct, restStructV) * 0.45);
            vel.assign(vel.mul(vLen.min(vMax).div(vLen)));
            const avgCorr = corr.div(cnt.max(1)).mul(stiffness);
            const next = p.add(vel).add(ext).add(avgCorr);

            // ── Collisions (run in WORLD space) ──
            const wp = next.add(meshOffset).toVar();
            // sphere colliders — push out to the surface
            Loop(colCount, ({ i: ci }) => {
                const sphere = collArr.element(ci);
                const rad = sphere.w.add(skin);                  // + skin → rest proud of the surface
                const toC = wp.sub(sphere.xyz);
                const dlen = toC.length().max(1e-5);
                If(dlen.lessThan(rad), () => {
                    wp.assign(sphere.xyz.add(toC.div(dlen).mul(rad)));
                });
            });
            // box / AABB colliders — eject along the least-penetration axis to
            // the nearest face (handles walls, booths, tables, crates — the
            // flat scene geometry a sphere can't represent).
            Loop(boxCount, ({ i: bi }) => {
                const bmin = boxMinArr.element(bi).sub(skin);   // expand the AABB by the skin so the
                const bmax = boxMaxArr.element(bi).add(skin);   // cloth stops PROUD of the real face
                If(wp.x.greaterThan(bmin.x).and(wp.x.lessThan(bmax.x))
                   .and(wp.y.greaterThan(bmin.y)).and(wp.y.lessThan(bmax.y))
                   .and(wp.z.greaterThan(bmin.z)).and(wp.z.lessThan(bmax.z)), () => {
                    const px0 = wp.x.sub(bmin.x), px1 = bmax.x.sub(wp.x);
                    const py0 = wp.y.sub(bmin.y), py1 = bmax.y.sub(wp.y);
                    const pz0 = wp.z.sub(bmin.z), pz1 = bmax.z.sub(wp.z);
                    const mx = px0.min(px1), my = py0.min(py1), mz = pz0.min(pz1);
                    const m = mx.min(my).min(mz);
                    If(m.equal(mx), () => {
                        wp.x.assign(px0.lessThan(px1).select(bmin.x, bmax.x));
                    }).Else(() => {
                        If(m.equal(my), () => {
                            wp.y.assign(py0.lessThan(py1).select(bmin.y, bmax.y));
                        }).Else(() => {
                            wp.z.assign(pz0.lessThan(pz1).select(bmin.z, bmax.z));
                        });
                    });
                });
            });
            // floor plane — fabric can't sink through the ground
            If(wp.y.lessThan(floorY.add(skin)), () => { wp.y.assign(floorY.add(skin)); });
            next.assign(wp.sub(meshOffset));

            prevBuf.element(i).assign(p);
            posBuf.element(i).assign(next);
        });
    })().compute(N, [64]);

    // --- Per-vertex normals from the SIMULATED surface ---
    // Without this the cloth keeps the flat plane's +Z normal everywhere, so a
    // textured/lit banner shades like a flat decal no matter how it folds. We
    // recompute each vertex normal from its grid neighbours (cross of the two
    // tangents), sign-corrected for edge vertices that sample backward.
    const normalBuf = instancedArray(new Float32Array(N * 3), 'vec3').setName('ClothNormals');
    const normalKernel = Fn(() => {
        const i = instanceIndex;
        const c = i.mod(COLS_u);
        const r = i.div(COLS_u);
        const here = posBuf.element(i);
        const colFwd = c.lessThan(COLS_u.sub(uint(1)));
        const rowFwd = r.lessThan(ROWS_u.sub(uint(1)));
        const cN = colFwd.select(i.add(uint(1)), i.sub(uint(1)));
        const rN = rowFwd.select(i.add(COLS_u), i.sub(COLS_u));
        const tx = posBuf.element(cN).sub(here);
        const ty = posBuf.element(rN).sub(here);
        const sign = colFwd.select(float(1), float(-1)).mul(rowFwd.select(float(1), float(-1)));
        const nrm = ty.cross(tx).mul(sign).normalize();
        normalBuf.element(i).assign(nrm);
    })().compute(N, [64]);

    // --- Mesh ---
    const geo = new THREE.PlaneGeometry(W, H, COLS - 1, ROWS - 1);
    const mat = opts.material ?? new THREE.MeshStandardNodeMaterial({
        color: 0xcccccc, roughness: 0.6, metalness: 0.0, side: THREE.DoubleSide,
    });
    // A graphic baked onto the FABRIC (rides the deformation via the intact
    // PlaneGeometry UVs) — pass opts.map / opts.texture. This is how banner
    // text / flag logos go ON the cloth instead of a floating plane in front.
    const decal = opts.map ?? opts.texture;
    if (decal && !mat.map) mat.map = decal;
    // Drive vertex positions from the sim buffer. PlaneGeometry vertex
    // order matches our row-major grid (r*COLS + c). Use vertexIndex —
    // instanceIndex is 0 for a non-instanced mesh and collapses every
    // vertex onto particle 0.
    mat.positionNode = posBuf.element(vertexIndex);
    mat.normalNode = transformNormalToView(normalBuf.element(vertexIndex));
    const mesh = new THREE.Mesh(geo, mat);
    mesh.frustumCulled = false;
    mesh.castShadow = mesh.receiveShadow = true;

    const iters = opts.iterations ?? 3;
    let t = 0;
    // objects whose colliders are RE-DERIVED every step() (cape/flag on a moving
    // character or prop) — populated by collideWith(objs, { track: true }).
    const _tracked = [];
    const _deriveColliders = (arr, o2) => {
        const T = globalThis.THREE;
        const boxes = [], spheres = [];
        for (const obj of arr) {
            const bb = new T.Box3().setFromObject(obj);
            if (bb.isEmpty()) continue;
            if (o2.asSphere) {
                const s = bb.getBoundingSphere(new T.Sphere());
                spheres.push({ center: [s.center.x, s.center.y, s.center.z], radius: s.radius });
            } else {
                boxes.push({ min: [bb.min.x, bb.min.y, bb.min.z], max: [bb.max.x, bb.max.y, bb.max.z] });
            }
        }
        if (spheres.length) api.setColliders(spheres);
        if (boxes.length) api.setBoxColliders(boxes);
    };
    const api = {
        mesh,
        step() {
            t += 1 / 60;
            tUni.value = t;
            meshOffset.value.copy(mesh.position);   // collisions in world space
            for (let k = 0; k < _tracked.length; k++) _deriveColliders(_tracked[k].objects, _tracked[k].o2);  // refresh moving colliders
            for (let k = 0; k < iters; k++) renderer.compute(computeKernel);
            renderer.compute(normalKernel);          // normals after positions settle
        },
        // Sphere colliders, WORLD space: [{ center:[x,y,z], radius }] (max 4).
        setColliders(list) {
            const n = Math.min(list.length, 8);
            colCount.value = n;
            for (let k = 0; k < n; k++) {
                const { center, radius } = list[k];
                collArr.value.array[k*4]   = center[0];
                collArr.value.array[k*4+1] = center[1];
                collArr.value.array[k*4+2] = center[2];
                collArr.value.array[k*4+3] = radius;
            }
            collArr.value.needsUpdate = true;
        },
        // Box/AABB colliders, WORLD space: [{ min:[x,y,z], max:[x,y,z] }] (max 4).
        setBoxColliders(list) {
            const n = Math.min(list.length, 8);
            boxCount.value = n;
            for (let k = 0; k < n; k++) {
                boxMinArr.value.array.set(list[k].min, k*3);
                boxMaxArr.value.array.set(list[k].max, k*3);
            }
            boxMinArr.value.needsUpdate = true; boxMaxArr.value.needsUpdate = true;
        },
        // The easy path: hand it scene objects and it derives world-space
        // colliders from their bounding volumes — boxes by default (walls,
        // booths, tables, crates), spheres with { asSphere:true } (heads,
        // torsos, balls). Call once for static geometry, or each frame for
        // moving objects. Caps at 4 of each.
        collideWith(objects, o2 = {}) {
            const arr = Array.isArray(objects) ? objects : [objects];
            _deriveColliders(arr, o2);
            // { track: true } → re-derive these colliders every step(), so a
            // cape/flag/banner on a MOVING character or prop keeps colliding
            // without you re-calling collideWith each frame.
            if (o2.track) _tracked.push({ objects: arr, o2 });
            return api;
        },
        set floor(y) { floorY.value = y; },
        setPinPosition(vertexIndex, xyz) {
            posBuf.value.array[vertexIndex*3]   = xyz[0];
            posBuf.value.array[vertexIndex*3+1] = xyz[1];
            posBuf.value.array[vertexIndex*3+2] = xyz[2];
            posBuf.value.needsUpdate = true;
        },
        get vertexCount() { return N; },
        get cols() { return COLS; },
        get rows() { return ROWS; },
        set stiffness(v) { stiffness.value = v; },
        set wind(v) { wind.value = v; },
        set windBias(v) { windBias.value = v; },
        setWindDir(d) {
            const l = Math.hypot(d[0], d[1], d[2]) || 1;
            windDir.value.set(d[0] / l, d[1] / l, d[2] / l);
        },
        _internals: { posBuf, prevBuf, fixedBuf },
    };
    // settleSteps: pre-roll the sim so frame 0 shows DRAPED fabric, not a
    // flat sheet mid-fall. ~60 is right for banners/curtains.
    const settle = opts.settleSteps ?? 0;
    for (let s = 0; s < settle; s++) api.step();
    return api;
}
