// fluid_water.js — Eulerian free-surface WATER for eidoverse (WebGPU/TSL).
//
// Based on: Chentanez & Müller, "Real-Time Eulerian Water Simulation Using
// a Restricted Tall Cell Grid" (SIGGRAPH 2011) — the paper's BASE method:
//   • collocated grid, one semi-Lagrangian trace shared by all quantities
//     (their §3.5 — "Due to the collocated grid we only need to trace the
//     Semi-Lagrangian ray once for all quantities")
//   • level set φ advected semi-Lagrangian (they found MacCormack noisier
//     for φ), gravity via forward Euler
//   • reinitialization only EVERY 10 FRAMES; φ next to the surface is not
//     modified; near-surface |φ| clamped to ≤ Δx every frame; all |φ| ≤ 5Δx
//     (their §3.4 stabilizations, verbatim)
//   • velocity extrapolated into the air region before advection (§3.3)
//   • pressure: free surface via ghost fluid (p = 0 exactly at φ = 0),
//     solids via Neumann (their Eq. 16 with binary solid fraction),
//     u -= ∇p correction (Eq. 17-18)
//
// W1 SIMPLIFICATIONS vs the paper (each noted inline):
//   • UNIFORM grid — no tall cells / remeshing. Tall cells accelerate DEEP
//     water; a tank scene is almost entirely regular cells anyway.
//   • pressure: MULTIGRID V-cycles (their §3.7), damped-Jacobi smoother in
//     place of their red/black Gauss-Seidel (RBGS needs two indexed passes
//     per sweep and gains little on GPU at this size). Plain Jacobi is still
//     available as a fallback via `mgLevels: 1` + `pressureIters`.
//   • surface tracked at SIM resolution (they use a 2x finer φ grid).
//   • narrow-band iterative velocity extrapolation (N neighbor-propagation
//     passes) instead of their Eikonal narrow band + hierarchy; enabled by
//     a smaller dt (1/60 substeps) so water crosses fewer cells per step
//     than at their 1/30.
//   • dam-break tank with ANALYTIC axis-aligned solid walls (free-slip).
//
// USAGE:
//   const water = await createWaterSim(renderer, { ... });
//   scene.add(water.surfaceMesh);
//   await water.warmup(0.5);                    // settle initial column edge
//   each frame: await water.step(1 / FPS);
//
// r184 idioms carried over from fluid_grid.js (all bisect-proven there):
//   rgba16float Storage3DTexture; dye/φ writes into texture OBJECTS via
//   AB/BA pass pairs (storageTexture-NODE writes silently no-op); reads via
//   a swapping texture3D node; computeAsync.

import * as THREE from 'three/webgpu';
import {
    vec2, vec3, vec4, float, Fn, uniform, uniformArray, uvec3, int,
    texture3D, textureStore, instanceIndex, storage,
    smoothstep, mix, min, max, abs, sign, floor, fract, sin, clamp, normalize, dot,
    reflect, pow, exp, If, Loop, Break,
    positionLocal, positionWorld, cameraPosition,
    modelWorldMatrixInverse, modelWorldMatrix, cameraViewMatrix,
    cameraNear, cameraFar, viewZToPerspectiveDepth,
} from 'three/tsl';

const DEFAULTS = {
    // ⚠ gridSize MUST give CUBIC cells against worldSize (see the check in
    // createWaterSim). 2.0/64 = 1.5/48 = 2.0/64 = 0.03125 m.
    // The paper's sim grids are 64x(64+2)x64 / 128x(32+2)x128 (Table 2).
    gridSize: [64, 48, 64],
    // tank interior size in metres (x, y, z). Water lives in [0..1] uvw of it.
    worldSize: [2.0, 1.5, 2.0],
    gravity: 9.8,
    // substep 1/120 s, two per 1/60 — smaller than the paper's 1/30 so the
    // simplified narrow-band extrapolation can keep up (W1 note above)
    fixedStep: 1 / 120,
    maxSubSteps: 8,
    // ── pressure: MULTIGRID (paper §3.7) ──────────────────────────────────
    // 64³ → 32³ → 16³ → 8³. A V-cycle propagates the floor constraint to the
    // free surface in ONE pass (the coarsest grid spans the tank in 8 cells),
    // which is the whole reason Jacobi needed 200 sweeps: it moves information
    // exactly one cell per sweep, so a 46-cell column needs 46 sweeps just to
    // hear about the floor, and many more to converge.
    // ⚠⚠ THIS STACK IS DISPATCH-BOUND, NOT BANDWIDTH-BOUND. A compute
    // dispatch costs roughly the same whether it runs 262144 threads or 384,
    // so a "cheap" coarse-grid sweep is not cheap at all. Measured A/B,
    // interleaved, volume trace identical to 3 digits in every case:
    //   mgCoarse 12→4 + mgPost 2→1 ........ +21 %
    //   mgCycles 3→2 ...................... +25 %  (compounding to ~+51 %)
    // mgCoarse 12 was 36 dispatches per substep on an 8x6x8 grid — 38 % of
    // ALL dispatches, doing almost no arithmetic. mgPost:2 also silently ran
    // THREE sweeps via the parity bump in mgSmooth(); 1 runs exactly one.
    // ⚠ Convergence is checked by the VOLUME TRACE, not by eye: under-solving
    // the pressure shows up immediately as the controller working harder.
    mgLevels: 4,                  // 1 = disable multigrid, fall back to Jacobi
    mgCycles: 2,                  // V-cycles per substep (paper: 2 V + 1 full)
    mgPre: 2,                     // pre-smoothing sweeps per level
    mgPost: 1,                    // post-smoothing sweeps (⚠ even values +1)
    mgCoarse: 4,                  // sweeps on the coarsest grid
    mgOmega: 0.8,                 // damped-Jacobi weight (RBGS stand-in)
    pressureIters: 80,            // ONLY used when mgLevels < 2
    extrapolationPasses: 6,       // narrow-band velocity extrapolation
    // ⚠ REINIT IS OFF BY DEFAULT. My redistancing uses CENTRAL differences
    // for |∇φ|, which is unstable — correct redistancing needs Godunov
    // upwinding. Measured against the fixed baseline: with reinit on, the
    // settled pool shattered by ~1.5s; with it off it stays flat and calm
    // more than twice as long. The §3.4 |φ| clamps carry the narrow band in
    // the meantime. Re-enable only after implementing upwind redistancing.
    reinitEvery: 0,               // 0 = off; 40 substeps ≈ the paper's cadence
    reinitIters: 8,               // redistancing sweeps per reinit
    maxTraceCells: 3.0,           // CFL cap on the semi-Lagrangian trace
    maxSpeed: 6.0,                // m/s cap after projection
    // ── VOLUME CONTROL (Kim, Liu, Llamas, Jiao, Rossignac, TOG 2007) ──────
    // A level set has no conservation law, so it drifts. Measured on the dam
    // break: −11 %/s through the collapse (fast flow tears sheets thinner
    // than a cell and they vanish), decaying to −0.18 %/s once settled.
    // The fix is a PI controller on total volume whose output is injected as
    // a DIVERGENCE SOURCE — the pressure solve then produces a velocity field
    // with exactly the net flux needed to restore the missing water, spread
    // uniformly through the liquid. Invisible during churn, and during the
    // calm phase the correction is a fraction of a percent per second.
    volumeControl: true,
    volumeTarget: null,           // null = whatever the initial state measures
    vcKp: 1.2,                    // proportional gain (1/s per unit rel. error)
    vcKi: 0.5,                    // integral gain — kills steady-state offset
    vcMaxRate: 0.35,              // ⚠ hard clamp on |∇·u| (1/s). Guard rail:
                                  // the controller can never puff the liquid
                                  // faster than this no matter how wrong it is.
    // ⚠ the sensor is ~9 dispatches (one full-res + the reduce chain), and at
    // every-2-substeps it cost 6% — mostly SUBMISSION overhead from the tiny
    // reduce passes, not compute. The loop's time constant is ~1 s, so
    // sampling at 30 Hz is ample and halves the bill.
    vcEvery: 4,                   // substeps between sensor updates
    // ── COLLIDERS: the liquid is not confined to a box ────────────────────
    // `walls` is the original analytic tank. Turn it OFF and hand the solver
    // a world instead: any meshes in `colliderMeshes` are voxelised into a
    // solid field at setup, and `maxSpheres` reserves dynamic colliders you
    // drive per frame (api.setSpheres) from VRM bones, props, anything moving.
    // All three compose — a tank AND terrain AND a character, or none.
    walls: true,                  // analytic rectangular tank (floor + 4 sides)
    insideDomain: false,          // true when the CAMERA is inside the liquid domain
    colliderMeshes: [],           // static world: THREE.Object3D / Mesh list
    maxSpheres: 0,                // dynamic collider budget (0 = none)
    // ── EMITTERS: liquid ARRIVES, instead of just existing ────────────────
    // Each is a world-space sphere that stamps liquid into φ and drives the
    // velocity there, so the flow runs, falls, collides and finds the lowest
    // basin. api.setEmitters([{x,y,z,r,vx,vy,vz}]) to move or gate them.
    // ⚠ emitters ADD volume, so the Kim volume controller must not fight
    // them — it is auto-disabled while any emitter is live.
    maxEmitters: 0,
    // ⚠ where the sim box sits in the WORLD. Colliders and setSpheres() are
    // given in world coordinates, so without this the solver would bake a
    // world that is offset from the one you can see.
    domainCenter: [0, 0, 0],
    measureVolume: false,         // build the GPU volume sensor (diagnostic)
    velSmooth: 0.25,              // viscosity blend per substep (0 = off)
    velDamping: 0.0,              // none — walls + pressure do the work
    // dam-break initial condition: a water column against the -x wall
    // (fractions of the tank interior)
    // still water of this depth (metres from the domain floor) INSTEAD of the
    // dam-break column — for a character standing in a pool rather than a
    // collapse. null = use the column below.
    initialLevel: null,
    columnWidth: 0.42,            // x extent
    columnHeight: 0.72,           // y extent
    columnDepth: 1.0,             // z extent
    // rendering
    raymarchSteps: 96,
    bisectionSteps: 4,
    // 'fixed' = the historical constant-step march. 'adaptive' sphere-traces
    // the clamped level set: big strides through saturated air, sub-cell
    // strides at the band — faster AND finer at the surface. marchIters is
    // its iteration cap (a bound, not a cost — typical rays exit early).
    marchMode: 'fixed',
    marchIters: 128,
    deepColor: '#06283d',
    shallowColor: '#2f8f9d',
    skyColor: '#9db8c9',
    absorption: 2.2,              // deep tint rate (1/m of водной thickness)
    surfaceOpacity: 0.93,
    keyLightDir: [0.4, 0.8, 0.45],
    // luminous liquid: emissive driven by THICKNESS (0 = ordinary water)
    emissiveColor: '#2ffbe0',
    emissiveStrength: 0.0,
    emissiveFalloff: 5.0,
    // SURFACE BREAK: a bright contact line wherever the liquid runs THIN —
    // shorelines, and every object standing in it. Falls straight out of the
    // thickness march, so it wraps legs and rocks with no extra work.
    foamColor: '#ffffff',
    foamStrength: 0.0,
    foamWidth: 0.10,          // metres of thickness the band covers
    // ⚠ the thickness half of the band ("shore") fires wherever view-ray
    // thickness → 0 — which includes the SILHOUETTE of every thin splash
    // film, so it traces sampling artifacts in bright white. 1.0 keeps the
    // historical behaviour; 0 keeps only the solid-contact ring (bodies,
    // walls) and drops the thin-film fringe.
    foamShore: 1.0,
    // RENDER-SIDE MENISCUS: march the φ = -surfaceBias isosurface instead of
    // φ = 0 (metres). Films thinner than ~2·bias do not render at all, and
    // the -ε contour of a trilinear field is smoother than the 0 contour, so
    // torn edges round off. 0 = bit-identical to the old behaviour. Normals
    // still come from ∇φ, which a constant offset does not change.
    surfaceBias: 0.0,
    // SMOOTH SURFACE: refine the hit and the normal on a cubic B-spline
    // reconstruction of φ (8 trilinear taps per evaluation — Sigg & Hadwiger,
    // GPU Gems 2 ch.20). Trilinear iso-contours have derivative kinks at
    // every cell face, which read as SAWTOOTH serration along splash
    // silhouettes; the cubic contour is C² and rounds them off. Costs taps
    // only on pixels that actually hit water. Compile-time flag: false emits
    // the exact previous shader.
    smoothSurface: false,
    // RENDER-φ BLUR: 1-2 passes of a separable [1 2 1]/4 low-pass of φ into a
    // RENDER-ONLY texture after each sim frame; the march reads the blurred
    // field, the sim never does. ⚠ this is the one that fixes SILHOUETTES:
    // hit-vs-miss is decided by the field the march samples, so smoothing the
    // reconstruction (smoothSurface) can only round faces it already hit —
    // only smoothing the DATA rounds the outline. Also calms per-frame
    // emitter jitter. 3 tiny dispatches per pass per frame; 0 = off, nothing
    // allocated, shader unchanged.
    renderBlur: 0,
    // SPARKLE: animated glints, gated by fresnel so they sit on the grazing
    // surface where a real one would catch the light.
    sparkleStrength: 0.0,
    sparkleScale: 26.0,
    sparkleSpeed: 1.4,
    warmupSeconds: 0.0,
};

export async function createWaterSim(renderer, options = {}) {
    const o = { ...DEFAULTS, ...options };
    const [NX, NY, NZ] = o.gridSize;
    const CELLS = NX * NY * NZ;
    const world = new THREE.Vector3(...o.worldSize);
    const domainCenter = new THREE.Vector3(...o.domainCenter);
    // ⚠⚠ THIS SOLVER REQUIRES CUBIC CELLS. Δx is taken from the x axis and
    // used isotropically for every level-set band (the §3.4 clamps, the AIR
    // value, the gravity band, redistancing), and — the part that actually
    // breaks physics — the divergence at kDiv is a RAW face difference with
    // no per-axis scaling, as is the projection gradient. Both are the true
    // operators only when Δx = Δy = Δz.
    // MEASURED (GPU volume sensor, dam break, 64³, t = 3 s):
    //     Δy = 0.75 Δx  →  −45 % volume        (worldSize [2,1.5,2] on 64³)
    //     Δy = 1.00 Δx  →  −15 % volume
    //     Δy = 1.30 Δx  →  +30 % volume  (it GAINS water)
    // The vertical term is under- or over-weighted, and in a gravity-driven
    // free-surface flow vertical is the dominant direction, so the projection
    // mis-handles exactly the flux that matters. Keep cells cubic — the
    // uniform-coefficient stencil is also what makes the multigrid's ×4
    // coarse-RHS scaling valid, and it is faster than per-axis coefficients.
    const DXV = [world.x / NX, world.y / NY, world.z / NZ];
    const DX = DXV[0];                          // Δx (world units per cell)
    const aniso = Math.max(...DXV) / Math.min(...DXV);
    if (aniso > 1.005) {
        const want = DXV.map((_, i) => Math.round([world.x, world.y, world.z][i] / DX));
        console.warn('[water] ⚠ NON-CUBIC CELLS — physics will be wrong. dx/dy/dz = '
            + DXV.map(v => v.toFixed(5)).join(' / ') + ' (aspect ' + aniso.toFixed(3)
            + '). For worldSize [' + [world.x, world.y, world.z].join(', ')
            + '] use gridSize [' + want.join(', ') + '].');
    }
    const TX = 1 / NX, TY = 1 / NY, TZ = 1 / NZ;

    // ── uniforms ──────────────────────────────────────────────────────────
    const U = {
        dt: uniform(o.fixedStep),
        time: uniform(0),
        gravity: uniform(o.gravity),
        velDamping: uniform(o.velDamping),
        maxSpeed: uniform(o.maxSpeed),
        velSmooth: uniform(o.velSmooth),
        worldSize: uniform(world.clone()),
        // analytic tank interior (uvw margins for the solid walls)
        wallM: uniform(1.5 / NX),               // wall margin ≈ 1.5 cells
        deepColor: uniform(new THREE.Color(o.deepColor)),
        shallowColor: uniform(new THREE.Color(o.shallowColor)),
        skyColor: uniform(new THREE.Color(o.skyColor)),
        absorption: uniform(o.absorption),
        surfaceOpacity: uniform(o.surfaceOpacity),
        keyLightDir: uniform(new THREE.Vector3(...o.keyLightDir).normalize()),
        emissiveColor: uniform(new THREE.Color(o.emissiveColor)),
        emissiveStrength: uniform(o.emissiveStrength),
        emissiveFalloff: uniform(o.emissiveFalloff),
        foamColor: uniform(new THREE.Color(o.foamColor)),
        foamStrength: uniform(o.foamStrength),
        foamWidth: uniform(o.foamWidth),
        foamShore: uniform(o.foamShore),
        surfaceBias: uniform(o.surfaceBias),
        sparkleStrength: uniform(o.sparkleStrength),
        sparkleScale: uniform(o.sparkleScale),
        sparkleSpeed: uniform(o.sparkleSpeed),
        mgOmega: uniform(o.mgOmega),
    };

    // ── storage textures (rgba16float — the r184-proven recipe) ───────────
    const mk = (name, nx = NX, ny = NY, nz = NZ) => {
        const t = new THREE.Storage3DTexture(nx, ny, nz);
        t.name = name;
        t.format = THREE.RGBAFormat;
        t.type = THREE.HalfFloatType;
        t.minFilter = THREE.LinearFilter;
        t.magFilter = THREE.LinearFilter;
        t.wrapS = t.wrapT = t.wrapR = THREE.ClampToEdgeWrapping;
        return t;
    };
    const velA = mk('waterVelA'), velB = mk('waterVelB');
    const phiA = mk('waterPhiA'), phiB = mk('waterPhiB');
    const phiHat = mk('waterPhiHat');   // MacCormack forward estimate
    const divT = mk('waterDiv');
    const prsA = mk('waterPrsA'), prsB = mk('waterPrsB');

    // swapping READ nodes (writes always go to explicit texture objects)
    const phiTexNode = texture3D(phiA);
    let phiInA = true;

    // volume-controller state, 1 texel: .x = integral term, .y = source s (1/s).
    // Declared HERE because kDiv samples it and kDiv is built before the
    // sensor. Living in a texture rather than a JS number is the whole point:
    // the controller closes its loop on the GPU with no readback.
    // ⚠ Emitters and the volume controller CAN coexist, but the scene must
    // drive the target while filling: set uniforms.volTarget.value to the
    // measured volume each tick, then STOP updating it when the emitters shut
    // off — the controller then holds whatever level was reached. Without
    // this the level set keeps gaining after the emitters stop (measured:
    // 10 m³ at shutoff drifted to 17.9 m³ over the next 6 s).
    if (o.volumeControl) o.measureVolume = true;
    const volCtrlA = mk('waterVolCtrlA', 1, 1, 1);
    const volCtrlB = mk('waterVolCtrlB', 1, 1, 1);
    const volCtrlNode = texture3D(volCtrlA);
    let volCtrlInA = true;

    // ── kernel helpers ────────────────────────────────────────────────────
    const cellOf = (id) => uvec3(
        id.mod(NX), id.div(NX).mod(NY), id.div(NX * NY));
    const uvwOf = (c) => vec3(c).add(0.5).div(vec3(NX, NY, NZ));

    // ── THE SOLID PREDICATE ───────────────────────────────────────────────
    // ⚠ This ONE function is the entire collision system. It feeds the
    // zero-flux faces in kDiv, the dropped neighbours in every multigrid
    // stencil, the blocked faces in kProject, and the render-side mask. So
    // generalising it here gives collision everywhere at once — nothing
    // downstream needs to know what shape the world is.
    //
    // Three layers, OR'd together; use any combination:
    //   1. analytic walls  — the original rectangular tank (`walls: true`)
    //   2. a BAKED FIELD   — arbitrary meshes voxelised once at setup, so a
    //                        cathedral costs exactly what a box costs
    //   3. DYNAMIC SPHERES — moving colliders (VRM bones, props), refreshed
    //                        per frame via api.setSpheres()
    //
    // ⚠ Sphere tests run in WORLD space, not uvw. A non-cube domain (a wide
    // shallow pool, say 8x2x8) has uvw axes of different physical length, so
    // a "sphere" in uvw is an ellipsoid in the world — hands would collide
    // as flattened discs.
    const solidTex = (o.colliderMeshes && o.colliderMeshes.length)
        ? new THREE.Data3DTexture(new Uint8Array(CELLS), NX, NY, NZ) : null;
    if (solidTex) {
        solidTex.format = THREE.RedFormat;
        solidTex.type = THREE.UnsignedByteType;
        // ⚠ LINEAR, deliberately. The SIM still thresholds at >0.5 so a cell
        // is either solid or not (the projection cannot express half a cell),
        // but the RENDER reads the interpolated value, which is what turns a
        // voxel staircase at the shoreline into a smooth interface — and it
        // doubles as a cheap proximity field for contact foam.
        solidTex.minFilter = solidTex.magFilter = THREE.LinearFilter;
        solidTex.wrapS = solidTex.wrapT = solidTex.wrapR = THREE.ClampToEdgeWrapping;
        solidTex.needsUpdate = true;
    }
    const NEMI = Math.max(0, o.maxEmitters | 0);
    // .xyz = centre (domain-local metres), .w = radius (<=0 = off)
    const emitArr = NEMI
        ? uniformArray(Array.from({ length: NEMI }, () => new THREE.Vector4(0, 0, 0, -1)))
        : null;
    // .xyz = inflow velocity (m/s), .w unused
    const emitVel = NEMI
        ? uniformArray(Array.from({ length: NEMI }, () => new THREE.Vector4(0, 0, 0, 0)))
        : null;
    const NSPH = Math.max(0, o.maxSpheres | 0);
    // .xyz = centre in DOMAIN-LOCAL world metres, .w = radius (w <= 0 = off)
    const sphereArr = NSPH
        ? uniformArray(Array.from({ length: NSPH }, () => new THREE.Vector4(0, 0, 0, -1)))
        : null;

    const isSolidWalls = (p) => {
        const m = U.wallM;
        return p.x.lessThan(m).or(p.x.greaterThan(float(1).sub(m)))
            .or(p.z.lessThan(m)).or(p.z.greaterThan(float(1).sub(m)))
            .or(p.y.lessThan(m));           // top stays OPEN
    };
    const isSolid = (p) => {
        let s = null;
        const add = (t) => { s = s ? s.or(t) : t; };
        if (o.walls) add(isSolidWalls(p));
        if (solidTex) add(texture3D(solidTex, p, 0).r.greaterThan(0.5));
        if (sphereArr) {
            const pw = p.sub(vec3(0.5)).mul(U.worldSize);  // → domain-local metres
            for (let i = 0; i < NSPH; i++) {
                const sp = sphereArr.element(i);
                add(sp.w.greaterThan(0.0)
                    .and(pw.sub(sp.xyz).length().lessThan(sp.w)));
            }
        }
        return s || p.y.lessThan(-1.0);     // no colliders at all → never solid
    };

    const dxv = vec3(TX, 0, 0), dyv = vec3(0, TY, 0), dzv = vec3(0, 0, TZ);

    // ── 0) init: dam-break column φ + zero velocity ───────────────────────
    // φ is a SIGNED DISTANCE in WORLD units (negative = water).
    const colW = o.columnWidth, colH = o.columnHeight, colD = o.columnDepth;
    // ⚠ ONE textureStore per pass. A five-write init kernel produced an
    // all-zero φ field with no error — the single-write pattern is the only
    // one ever proven on this stack (the fire's kernels all write one).
    const columnPhi = (p) => {
        const m = U.wallM;
        // ⚠ the column must OVERLAP the solid walls, not touch them exactly.
        // Starting it at the wall margin put the φ=0 iso-surface precisely on
        // the boundary, so the bottom row evaluated to φ = 0 — which is
        // neither `φ < 0` (fluid) nor `φ > 0` (air). It fell through both
        // gates, got p = 0, and that is a FREE-SURFACE condition at the
        // floor: the tank had an open bottom, pressure could never build and
        // the water drained away. Overlapping makes the classification
        // unambiguous (the solid override clips the overlap each step).
        const lo = vec3(m.sub(0.05), m.sub(0.05), float(0.5).sub(float(colD).mul(0.5)));
        const hi = vec3(m.add(colW), m.add(colH), float(0.5).add(float(colD).mul(0.5)));
        const ctr = lo.add(hi).mul(0.5);
        const half = hi.sub(lo).mul(0.5);
        const q = p.sub(ctr).abs().sub(half).mul(U.worldSize);
        const outside = q.max(vec3(0)).length();
        const inside = q.x.max(q.y).max(q.z).min(0);
        return outside.add(inside);
    };
    // A FLAT LAYER instead of a dam break: φ = signed distance to a level
    // plane, so the sim opens as STILL WATER of a given depth rather than a
    // block about to collapse. `initialLevel` is depth in metres from the
    // domain floor; null keeps the column.
    const levelPhi = (p) => p.y.mul(world.y).sub(float(o.initialLevel || 0));
    const initialPhi = (o.initialLevel != null) ? levelPhi : columnPhi;
    const mkInitPhi = (dst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        textureStore(dst, c, vec4(initialPhi(uvwOf(c)), 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const mkInitZero = (dst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        textureStore(dst, c, vec4(0, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const kInitPhiA = mkInitPhi(phiA, 'waterInitPhiA');
    const kInitPhiB = mkInitPhi(phiB, 'waterInitPhiB');
    const kInitVelA = mkInitZero(velA, 'waterInitVelA');
    const kInitPrsA = mkInitZero(prsA, 'waterInitPrsA');
    const kInitPrsB = mkInitZero(prsB, 'waterInitPrsB');
    async function runInit() {
        await renderer.computeAsync(kInitPhiA);
        await renderer.computeAsync(kInitPhiB);
        await renderer.computeAsync(kInitVelA);
        await renderer.computeAsync(kInitPrsA);
        await renderer.computeAsync(kInitPrsB);
    }

    // ── 1) velocity extrapolation into air (paper §3.3, W1 narrow band) ───
    // N passes: air cells take the φ-weighted average of neighbors that are
    // deeper in the water — propagates surface velocity outward one ring per
    // pass. velA -> velB, then velB -> velA (pass pair; run an even count).
    const mkExtrap = (src, dst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const phiC = phiTexNode.sample(p).level(0).x;
        const v = texture3D(src, p, 0).xyz.toVar();
        If(phiC.greaterThan(0.0), () => {
            const sum = vec3(0).toVar();
            const wsum = float(0).toVar();
            const offs = [dxv, dxv.negate(), dyv, dyv.negate(), dzv, dzv.negate()];
            for (const off of offs) {
                const pn = p.add(off);
                const phiN = phiTexNode.sample(pn).level(0).x;
                const w = max(phiC.sub(phiN), 0.0);     // neighbor deeper → weight
                sum.addAssign(texture3D(src, pn, 0).xyz.mul(w));
                wsum.addAssign(w);
            }
            If(wsum.greaterThan(1e-5), () => {
                v.assign(sum.div(wsum));
            });
        });
        textureStore(dst, c, vec4(v, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const kExtrapAB = mkExtrap(velA, velB, 'waterExtrapAB');
    const kExtrapBA = mkExtrap(velB, velA, 'waterExtrapBA');

    // ── 2) advect φ + velocity (ONE shared SL trace) + gravity + clamps ───
    // paper §3.5: collocated grid → one back-trace for all quantities; φ via
    // semi-Lagrangian; gravity forward Euler. Also applies the §3.4 clamps:
    // near-surface |φ| ≤ Δx every frame, global |φ| ≤ 5Δx.
    // ⚠ MACCORMACK (BFECC) ADVECTION FOR φ — the fix for volume loss.
    // Plain semi-Lagrangian is first-order and diffuses the interface about
    // half a cell per step; with no source term the level set simply erodes
    // and the water "evaporates" (measured: erosion rate scaled directly with
    // gravity, i.e. with velocity). MacCormack advects forward, advects the
    // result BACK, and corrects by half the round-trip error — second order,
    // with the diffusion largely cancelled. The extrema limiter reverts to
    // plain SL wherever the correction would create a new min/max, which is
    // what keeps it stable at a sharp interface (Selle et al. 2008; the paper
    // uses this scheme for u).
    const traceBack = (p, sgn) => {
        const vHere = cellVel(velA, p);
        const trace = vHere.div(U.worldSize).mul(U.dt).mul(sgn);
        const maxTrace = float(o.maxTraceCells).mul(vec3(TX, TY, TZ));
        return p.sub(trace.clamp(maxTrace.negate(), maxTrace)).clamp(0.001, 0.999);
    };
    // ⚠ Did the trace leave the domain? The clamp above pins such lookups onto
    // the boundary SLICE, so a cell above the open lid re-samples the top row
    // every step and replicates it downward — a repeating curtain of droplets
    // "raining" from the ceiling of the volume bounds. Outside the domain is
    // AIR, so φ must read as air there rather than as the edge slice.
    const tracedOut = (p, sgn) => {
        const vHere = cellVel(velA, p);
        const trace = vHere.div(U.worldSize).mul(U.dt).mul(sgn);
        const maxTrace = float(o.maxTraceCells).mul(vec3(TX, TY, TZ));
        const raw = p.sub(trace.clamp(maxTrace.negate(), maxTrace));
        return raw.x.lessThan(0.0).or(raw.x.greaterThan(1.0))
            .or(raw.y.lessThan(0.0)).or(raw.y.greaterThan(1.0))
            .or(raw.z.lessThan(0.0)).or(raw.z.greaterThan(1.0));
    };
    const AIR = float(DX * 4);

    // velocity advection + gravity (unchanged, semi-Lagrangian)
    const kAdvectVel = Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const bc = traceBack(p, 1.0);
        const v = texture3D(velA, bc, 0).xyz.toVar();
        const phiC = phiTexNode.sample(p).level(0).x;

        // ⚠ GRAVITY ONLY IN THE FLUID + A NARROW AIR BAND. Air cells are not
        // pressure-projected, so integrating gravity there accumulates without
        // limit (−15 m/s by 1.5s, −29 m/s by 3s). A surface water cell averages
        // its neighbouring AIR faces into its own velocity, so that runaway
        // leaks straight into the fluid and shatters the body into floating
        // needles. The paper never integrates air velocity — it EXTRAPOLATES
        // it from the fluid (§3.3). Outside the band, velocity is left to the
        // extrapolation pass instead of being marched by forces.
        If(phiC.lessThan(float(DX * 2)), () => {
            v.subAssign(vec3(0, U.gravity.mul(U.dt), 0));
        });
        If(phiC.greaterThan(float(DX * 4)), () => { v.assign(vec3(0)); });

        v.mulAssign(max(float(1).sub(U.velDamping.mul(U.dt)), 0));
        if (emitArr) {
            const pw = p.sub(vec3(0.5)).mul(U.worldSize);
            for (let i = 0; i < NEMI; i++) {
                const e = emitArr.element(i);
                If(e.w.greaterThan(0.0).and(pw.sub(e.xyz).length().lessThan(e.w)), () => {
                    v.assign(emitVel.element(i).xyz);
                });
            }
        }
        If(isSolid(p), () => { v.assign(vec3(0)); });
        textureStore(velB, c, vec4(v, 1)).toWriteOnly();
    })().compute(CELLS).setName('waterAdvectVel');

    // φ step 1: forward SL  φ̂ = SL(φⁿ, +dt)
    const mkPhiFwd = (src, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const phiF = tracedOut(p, 1.0).select(AIR, texture3D(src, traceBack(p, 1.0), 0).x);
        textureStore(phiHat, c, vec4(phiF, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const kPhiFwdA = mkPhiFwd(phiA, 'waterPhiFwdA');
    const kPhiFwdB = mkPhiFwd(phiB, 'waterPhiFwdB');

    // φ step 2: backward SL of φ̂, correct, limit, then the §3.4 clamps
    const mkPhiCorr = (src, dst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const bc = traceBack(p, 1.0);

        const phiHatC = texture3D(phiHat, p, 0).x;                 // φ̂
        const phiBack = texture3D(phiHat, traceBack(p, -1.0), 0).x; // φ̃
        const phiOld = texture3D(src, p, 0).x;                      // φⁿ
        const corrected = phiHatC.add(phiOld.sub(phiBack).mul(0.5)).toVar();

        // extrema limiter over the 6 neighbours of the departure point:
        // outside that range the correction is unphysical → keep plain SL
        const sl = tracedOut(p, 1.0).select(AIR, texture3D(src, bc, 0).x);
        const n0 = texture3D(src, bc.add(dxv), 0).x, n1 = texture3D(src, bc.sub(dxv), 0).x;
        const n2 = texture3D(src, bc.add(dyv), 0).x, n3 = texture3D(src, bc.sub(dyv), 0).x;
        const n4 = texture3D(src, bc.add(dzv), 0).x, n5 = texture3D(src, bc.sub(dzv), 0).x;
        const lo = min(min(min(n0, n1), min(n2, n3)), min(min(n4, n5), sl));
        const hi = max(max(max(n0, n1), max(n2, n3)), max(max(n4, n5), sl));
        const outside = corrected.lessThan(lo).or(corrected.greaterThan(hi));
        const phi = outside.select(sl, corrected).toVar();

        // ⚠ DO NOT force φ to air inside solids. That was the mass sink:
        // it stamps a permanent air gap into every wall, and the
        // semi-Lagrangian interpolation then drags that air back across the
        // boundary, annihilating water at every wall and eating inward until
        // the whole body "evaporates". Water is already kept out of solids by
        // the no-flux condition on solid FACES; φ needs no clipping at all,
        // and leaving it alone lets the free surface rest against a wall.

        if (!o.__noClamp) {
            If(phi.abs().lessThan(float(DX * 1.5)), () => {
                phi.assign(phi.clamp(-DX, DX));
            });
            phi.assign(phi.clamp(-5 * DX, 5 * DX));
        }
        // ── emitters: union the source spheres INTO the level set ─────────
        if (emitArr) {
            const pw = p.sub(vec3(0.5)).mul(U.worldSize);
            for (let i = 0; i < NEMI; i++) {
                const e = emitArr.element(i);
                const d = pw.sub(e.xyz).length().sub(e.w);
                phi.assign(e.w.greaterThan(0.0).select(min(phi, d), phi));
            }
        }
        textureStore(dst, c, vec4(phi, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const kPhiCorrAB = mkPhiCorr(phiA, phiB, 'waterPhiCorrAB');
    const kPhiCorrBA = mkPhiCorr(phiB, phiA, 'waterPhiCorrBA');

    // ── 3) reinitialization (every 10 frames, paper §3.4) ─────────────────
    // Iterative redistancing: φτ = sign(φ0)(1 − |∇φ|), upwind via central
    // difference here (W1: with only ~8 sweeps and the near-surface freeze,
    // central differencing is stable enough at 64³). Cells adjacent to the
    // surface are NOT modified — the paper's "do not move the surface" rule.
    const mkReinit = (src, dst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const phi = texture3D(src, p, 0).x.toVar();

        const xp = texture3D(src, p.add(dxv), 0).x, xm = texture3D(src, p.sub(dxv), 0).x;
        const yp = texture3D(src, p.add(dyv), 0).x, ym = texture3D(src, p.sub(dyv), 0).x;
        const zp = texture3D(src, p.add(dzv), 0).x, zm = texture3D(src, p.sub(dzv), 0).x;

        // near-surface freeze: any sign change among neighbors → keep φ
        const minN = min(min(min(xp, xm), min(yp, ym)), min(zp, zm));
        const maxN = max(max(max(xp, xm), max(yp, ym)), max(zp, zm));
        const nearSurface = phi.mul(minN).lessThan(0.0).or(phi.mul(maxN).lessThan(0.0));

        If(nearSurface.not(), () => {
            const g = vec3(
                xp.sub(xm).div(2 * DX),
                yp.sub(ym).div(2 * DX),
                zp.sub(zm).div(2 * DX)).length();
            const s = sign(phi);
            // pseudo-time step 0.5Δx (CFL-safe for redistancing)
            phi.addAssign(s.mul(float(1).sub(g)).mul(0.5 * DX));
        });
        phi.assign(phi.clamp(-5 * DX, 5 * DX));
        textureStore(dst, c, vec4(phi, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const kReinitAB = mkReinit(phiA, phiB, 'waterReinitAB');
    const kReinitBA = mkReinit(phiB, phiA, 'waterReinitBA');

    // ── 4) divergence of velB (fluid cells only) ──────────────────────────
    // ⚠ COMPACT face-sampled stencil, not full-cell central differences.
    // A collocated central div/grad pair decouples odd and even cells (the
    // classic checkerboard null mode MAC grids exist to prevent); under
    // gravity the free surface resonated it into a forest of one-cell
    // needles and shredded. Sampling at ±half-cell offsets uses the linear
    // filter to read AT the faces — direct-neighbor coupling, no null mode
    // (the "approximate projection" standard in graphics).
    // ════════════════════════════════════════════════════════════════════
    // ⚠⚠ STAGGERED MAC LAYOUT — the fix that makes free-surface water work.
    // The velocity texture is interpreted as FACE velocities:
    //     .x at face (i+½, j, k)   .y at (i, j+½, k)   .z at (i, j, k+½)
    // Why: with linear filtering a half-cell sample returns the AVERAGE of
    // two cells, so a "compact-looking" collocated div/grad is really the
    // WIDE operator (f[i+1]−f[i−1])/2, while the Jacobi inverts the COMPACT
    // Laplacian. div∘grad then does not match the operator being solved: the
    // projection never removes the divergence it measures, the residual grows
    // every step, and the solve blows up (measured: div and p saturating
    // within 4 frames while the water was destroyed). Staggering makes
    //     div_i = (u_i − u_{i−1}) + …        grad at face i+½ = q_{i+1} − q_i
    // compact and mutually consistent — and kills the checkerboard mode.
    // ════════════════════════════════════════════════════════════════════

    // face (i+½) is blocked if EITHER adjacent cell is solid
    const faceBlocked = (p, cellOff) => isSolid(p).or(isSolid(p.add(cellOff)));

    // cell-centred velocity for the semi-Lagrangian back-trace: average the
    // two opposing faces of the cell
    const cellVel = (tex, p) => vec3(
        texture3D(tex, p, 0).x.add(texture3D(tex, p.sub(dxv), 0).x).mul(0.5),
        texture3D(tex, p, 0).y.add(texture3D(tex, p.sub(dyv), 0).y).mul(0.5),
        texture3D(tex, p, 0).z.add(texture3D(tex, p.sub(dzv), 0).z).mul(0.5));

    // ── 4) divergence of the staggered field (compact, solid-aware) ───────
    const kDiv = Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const uP = faceBlocked(p, dxv).select(float(0), texture3D(velB, p, 0).x);
        const uM = faceBlocked(p.sub(dxv), dxv).select(float(0), texture3D(velB, p.sub(dxv), 0).x);
        const vP = faceBlocked(p, dyv).select(float(0), texture3D(velB, p, 0).y);
        const vM = faceBlocked(p.sub(dyv), dyv).select(float(0), texture3D(velB, p.sub(dyv), 0).y);
        const wP = faceBlocked(p, dzv).select(float(0), texture3D(velB, p, 0).z);
        const wM = faceBlocked(p.sub(dzv), dzv).select(float(0), texture3D(velB, p.sub(dzv), 0).z);
        const div = uP.sub(uM).add(vP.sub(vM)).add(wP.sub(wM)).toVar();
        // ── volume-control source (Kim 2007) ──────────────────────────────
        // Projection makes div(u_new) = div(u) − L p. Feeding the solve
        // (div − Δx·s) instead of div therefore leaves div(u_new) = Δx·s,
        // i.e. a controlled expansion of s per second. Δx converts to this
        // discretisation's units, where div is a RAW face difference and so
        // already carries one factor of Δx.
        if (o.volumeControl) {
            const s = volCtrlNode.sample(vec3(0.5)).level(0).y;
            const phiC = phiTexNode.sample(p).level(0).x;
            If(phiC.lessThanEqual(0.0).and(isSolid(p).not()), () => {
                div.subAssign(s.mul(float(DX)));
            });
        }
        textureStore(divT, c, vec4(div, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName('waterDiv');
    // pressure is WARM-STARTED across substeps (no reset) — Jacobi needs many
    // sweeps to carry the floor constraint up a 46-cell column.

    // ── 5) Jacobi pressure, ghost-fluid free surface (paper Eq. 16) ───────
    // θ = φC/(φC−φN) is the fluid fraction toward an air neighbour, so p = 0
    // lands exactly on φ = 0. It enters the DIAGONAL (1/θ), which keeps the
    // system diagonally dominant; as an off-diagonal term it diverges.
    const mkJacobi = (src, dst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const phiC = phiTexNode.sample(p).level(0).x;
        const out = float(0).toVar();
        If(phiC.lessThanEqual(0.0).and(isSolid(p).not()), () => {
            const div = texture3D(divT, p, 0).x;
            const sum = float(0).toVar();
            const diag = float(0).toVar();
            const pairs = [[dxv, dxv], [dxv.negate(), dxv.negate()],
                           [dyv, dyv], [dyv.negate(), dyv.negate()],
                           [dzv, dzv], [dzv.negate(), dzv.negate()]];
            for (const [off] of pairs) {
                const pn = p.add(off);
                const phiN = phiTexNode.sample(pn).level(0).x;
                const solidN = isSolid(pn);
                const isAir = phiN.greaterThan(0.0);
                const theta = phiC.div(phiC.sub(phiN).min(-1e-5)).clamp(0.02, 1.0);
                const pnV = texture3D(src, pn, 0).x;
                sum.addAssign(solidN.select(float(0), isAir.select(float(0), pnV)));
                diag.addAssign(solidN.select(float(0),
                    isAir.select(float(1).div(theta), float(1))));
            }
            out.assign(sum.sub(div).div(diag.max(1e-4)));
        });
        textureStore(dst, c, vec4(out, 0, 0, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const kJacobiAB = mkJacobi(prsA, prsB, 'waterJacobiAB');
    const kJacobiBA = mkJacobi(prsB, prsA, 'waterJacobiBA');

    // ── 5b) MULTIGRID (paper §3.7) ────────────────────────────────────────
    // Convention, fixed once and used identically by the smoother and the
    // residual (they MUST match or the cycle diverges):
    //
    //     A p = rhs        with   (A p)_C = diag·p_C − Σ_N p_N
    //     level 0 rhs = −div     coarse rhs = 4 · restrict(residual)
    //     smoother  p ← (1−ω)p + ω(Σ_N p_N + rhs)/diag
    //     residual  r = rhs + Σ_N p_N − diag·p_C
    //
    // The factor 4 on the coarse RHS: this discretisation folds Δx away (div
    // is a raw face difference, the projection subtracts a raw cell
    // difference), so the stored operator is the UNIT stencil L ≈ Δx²∇².
    // At cell size 2Δx that same unit stencil represents 4Δx²∇², so the
    // restricted residual must be scaled by 4 for the coarse correction to
    // approximate the fine error.
    //
    // Restriction and prolongation are single LINEAR TEXTURE TAPS, which is
    // exact here: a coarse cell centre lands precisely on the corner shared
    // by its 8 fine cells, so one sample = full-weighting restriction; a fine
    // cell centre lands at ±¼ cell in coarse space, so one sample = the
    // standard trilinear prolongation. No hand-written 27-tap kernels.
    const MG = [];
    if (o.mgLevels > 1) {
        for (let L = 0; L < o.mgLevels; L++) {
            const nx = NX >> L, ny = NY >> L, nz = NZ >> L;
            if (L > 0 && ((nx << L) !== NX || (ny << L) !== NY || (nz << L) !== NZ
                || Math.min(nx, ny, nz) < 4)) break;
            const lv = {
                L, nx, ny, nz, cells: nx * ny * nz,
                dxv: vec3(1 / nx, 0, 0), dyv: vec3(0, 1 / ny, 0), dzv: vec3(0, 0, 1 / nz),
                // ⚠ the wall must survive coarsening. The fine margin (1.5/NX)
                // is thinner than a coarse cell, so an unscaled test leaves the
                // coarse grids with NO solid at all and the coarse operator
                // then solves a different problem (open box vs closed tank).
                // One solid ring per level keeps the Neumann boundary present
                // at every resolution.
                margin: Math.max(1.5 / NX, 1 / nx),
            };
            lv.cellOf = (id) => uvec3(id.mod(nx), id.div(nx).mod(ny), id.div(nx * ny));
            lv.uvwOf = (c) => vec3(c).add(0.5).div(vec3(nx, ny, nz));
            if (L === 0) {
                lv.p = prsA; lv.p2 = prsB;            // warm-started across substeps
                lv.r = mk('waterMgR0', nx, ny, nz);
                lv.phiTex = null; lv.b = null;        // uses phiTexNode / −divT
            } else {
                lv.p = mk('waterMgP' + L, nx, ny, nz);
                lv.p2 = mk('waterMgP2' + L, nx, ny, nz);
                lv.r = mk('waterMgR' + L, nx, ny, nz);
                lv.phiTex = mk('waterMgPhi' + L, nx, ny, nz);
                lv.b = mk('waterMgB' + L, nx, ny, nz);
            }
            lv.phi = L === 0
                ? (p) => phiTexNode.sample(p).level(0).x
                : (p) => texture3D(lv.phiTex, p, 0).x;
            lv.rhs = L === 0
                ? (p) => texture3D(divT, p, 0).x.negate()
                : (p) => texture3D(lv.b, p, 0).x;
            // ⚠ Coarse levels must see the SAME obstacles the fine grid does,
            // or the coarse correction solves a different problem and fights
            // the smoother. Baked field + dynamic spheres are resolution
            // independent (both are sampled in uvw / world space), so they
            // carry down unchanged; only the analytic wall margin is scaled
            // per level so a one-cell wall survives coarsening.
            lv.isSolid = (p) => {
                let s = null;
                const add = (t) => { s = s ? s.or(t) : t; };
                if (o.walls) {
                    const m = float(lv.margin);
                    add(p.x.lessThan(m).or(p.x.greaterThan(float(1).sub(m)))
                        .or(p.z.lessThan(m)).or(p.z.greaterThan(float(1).sub(m)))
                        .or(p.y.lessThan(m)));  // top stays OPEN at every level
                }
                if (solidTex) add(texture3D(solidTex, p, 0).r.greaterThan(0.5));
                if (sphereArr) {
                    const pw = p.sub(vec3(0.5)).mul(U.worldSize);
                    for (let i = 0; i < NSPH; i++) {
                        const sp = sphereArr.element(i);
                        add(sp.w.greaterThan(0.0)
                            .and(pw.sub(sp.xyz).length().lessThan(sp.w)));
                    }
                }
                return s || p.y.lessThan(-1.0);
            };
            MG.push(lv);
        }
    }

    // the Eq.16 stencil at an arbitrary level — ghost fluid (1/θ on the
    // DIAGONAL) for air, dropped neighbour for solid. Identical form to
    // mkJacobi above; that one stays as the mgLevels<2 fallback.
    const mgStencil = (lv, srcTex, p) => {
        const phiC = lv.phi(p);
        const sum = float(0).toVar();
        const diag = float(0).toVar();
        const offs = [lv.dxv, lv.dxv.negate(), lv.dyv, lv.dyv.negate(),
                      lv.dzv, lv.dzv.negate()];
        for (const off of offs) {
            const pn = p.add(off);
            const phiN = lv.phi(pn);
            const solidN = lv.isSolid(pn);
            const isAir = phiN.greaterThan(0.0);
            const theta = phiC.div(phiC.sub(phiN).min(-1e-5)).clamp(0.02, 1.0);
            const pv = texture3D(srcTex, pn, 0).x;
            sum.addAssign(solidN.select(float(0), isAir.select(float(0), pv)));
            diag.addAssign(solidN.select(float(0),
                isAir.select(float(1).div(theta), float(1))));
        }
        return { phiC, sum, diag };
    };
    const mgIsFluid = (lv, p, phiC) =>
        phiC.lessThanEqual(0.0).and(lv.isSolid(p).not());

    const mkMgSmooth = (lv, src, dst, name) => Fn(() => {
        const c = lv.cellOf(instanceIndex);
        const p = lv.uvwOf(c);
        const { phiC, sum, diag } = mgStencil(lv, src, p);
        const out = float(0).toVar();
        If(mgIsFluid(lv, p, phiC), () => {
            const jac = sum.add(lv.rhs(p)).div(diag.max(1e-4));
            out.assign(mix(texture3D(src, p, 0).x, jac, U.mgOmega));
        });
        textureStore(dst, c, vec4(out, 0, 0, 1)).toWriteOnly();
    })().compute(lv.cells).setName(name);

    const mkMgResidual = (lv, name) => Fn(() => {
        const c = lv.cellOf(instanceIndex);
        const p = lv.uvwOf(c);
        const { phiC, sum, diag } = mgStencil(lv, lv.p, p);
        const out = float(0).toVar();
        If(mgIsFluid(lv, p, phiC), () => {
            out.assign(lv.rhs(p).add(sum).sub(diag.mul(texture3D(lv.p, p, 0).x)));
        });
        textureStore(lv.r, c, vec4(out, 0, 0, 1)).toWriteOnly();
    })().compute(lv.cells).setName(name);

    const mkMgRestrict = (lf, lc, name) => Fn(() => {
        const c = lc.cellOf(instanceIndex);
        const p = lc.uvwOf(c);
        textureStore(lc.b, c,
            vec4(texture3D(lf.r, p, 0).x.mul(4.0), 0, 0, 1)).toWriteOnly();
    })().compute(lc.cells).setName(name);

    // φ must be re-restricted every solve — it moves every substep
    const mkMgRestrictPhi = (lf, lc, name) => Fn(() => {
        const c = lc.cellOf(instanceIndex);
        const p = lc.uvwOf(c);
        textureStore(lc.phiTex, c, vec4(lf.phi(p), 0, 0, 1)).toWriteOnly();
    })().compute(lc.cells).setName(name);

    // p_fine += P(e_coarse); lands in lf.p2, so post-smoothing starts BA
    const mkMgProlong = (lf, lc, name) => Fn(() => {
        const c = lf.cellOf(instanceIndex);
        const p = lf.uvwOf(c);
        const out = float(0).toVar();
        If(mgIsFluid(lf, p, lf.phi(p)), () => {
            out.assign(texture3D(lf.p, p, 0).x.add(texture3D(lc.p, p, 0).x));
        });
        textureStore(lf.p2, c, vec4(out, 0, 0, 1)).toWriteOnly();
    })().compute(lf.cells).setName(name);

    const mkMgZero = (lv, name) => Fn(() => {
        textureStore(lv.p, lv.cellOf(instanceIndex), vec4(0, 0, 0, 1)).toWriteOnly();
    })().compute(lv.cells).setName(name);

    const MGK = MG.map((lv, i) => ({
        smoothAB: mkMgSmooth(lv, lv.p, lv.p2, 'waterMgSmoothAB' + i),
        smoothBA: mkMgSmooth(lv, lv.p2, lv.p, 'waterMgSmoothBA' + i),
        residual: i < MG.length - 1 ? mkMgResidual(lv, 'waterMgRes' + i) : null,
        zero: i > 0 ? mkMgZero(lv, 'waterMgZero' + i) : null,
        restrict: i > 0 ? mkMgRestrict(MG[i - 1], lv, 'waterMgRestrict' + i) : null,
        restrictPhi: i > 0 ? mkMgRestrictPhi(MG[i - 1], lv, 'waterMgRestrictPhi' + i) : null,
        prolong: i > 0 ? mkMgProlong(MG[i - 1], lv, 'waterMgProlong' + i) : null,
    }));

    // sweeps alternate p→p2→p; the count is bumped by one when needed so the
    // result ALWAYS lands back in lv.p (the texture kProject and the coarse
    // levels read from)
    async function mgSmooth(i, n, fromP2) {
        let inP2 = !!fromP2;
        let sweeps = Math.max(1, n | 0);
        if ((inP2 && sweeps % 2 === 0) || (!inP2 && sweeps % 2 === 1)) sweeps += 1;
        for (let s = 0; s < sweeps; s++) {
            await renderer.computeAsync(inP2 ? MGK[i].smoothBA : MGK[i].smoothAB);
            inP2 = !inP2;
        }
    }
    async function mgVCycle(i) {
        if (i === MG.length - 1) { await mgSmooth(i, o.mgCoarse, false); return; }
        await mgSmooth(i, o.mgPre, false);
        await renderer.computeAsync(MGK[i].residual);
        await renderer.computeAsync(MGK[i + 1].restrict);
        await renderer.computeAsync(MGK[i + 1].zero);     // e starts at 0
        await mgVCycle(i + 1);
        await renderer.computeAsync(MGK[i + 1].prolong);
        await mgSmooth(i, o.mgPost, true);
    }
    async function mgSolve() {
        for (let i = 1; i < MG.length; i++) {
            await renderer.computeAsync(MGK[i].restrictPhi);
        }
        for (let c = 0; c < o.mgCycles; c++) await mgVCycle(0);
    }

    // ── 6) project: face velocity -= (q_{i+1} − q_i), compact ────────────
    const kProject = Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const qC = texture3D(prsA, p, 0).x;
        const phiC = phiTexNode.sample(p).level(0).x;
        // ⚠ GHOST-FLUID GRADIENT — it MUST match the ghost the SOLVE assumed.
        // The solve puts 1/θ on the diagonal, i.e. it models a fluid→air face
        // as having gradient −p_C/θ: p = 0 sits on the φ = 0 crossing, which
        // is θΔx away, not a full Δx. Using a plain (0 − p_C) here therefore
        // under-corrects every surface face by a factor θ. Jacobi hid this —
        // it never converged the interior either, so the two errors were the
        // same order. Multigrid converges the interior, which leaves the
        // surface inconsistency as the dominant one, and an uncorrected
        // divergence at the free surface is exactly a slow volume leak: the
        // settled pool thinned to a white sheet and drained by ~5s.
        const grad = (off) => {
            const pn = p.add(off);
            const phiN = phiTexNode.sample(pn).level(0).x;
            const qN = texture3D(prsA, pn, 0).x;
            const cW = phiC.lessThanEqual(0.0), nW = phiN.lessThanEqual(0.0);
            // θ measured from whichever side is the fluid
            const thC = phiC.div(phiC.sub(phiN).min(-1e-5)).clamp(0.02, 1.0);
            const thN = phiN.div(phiN.sub(phiC).min(-1e-5)).clamp(0.02, 1.0);
            return isSolid(p).or(isSolid(pn)).select(float(0),
                cW.and(nW).select(qN.sub(qC),                 // fluid–fluid
                    cW.select(qC.negate().div(thC),           // fluid→air
                        nW.select(qN.div(thN), float(0)))));  // air→fluid
        };
        const v = texture3D(velB, p, 0).xyz.toVar();
        v.x.assign(v.x.sub(grad(dxv)));
        v.y.assign(v.y.sub(grad(dyv)));
        v.z.assign(v.z.sub(grad(dzv)));

        // no-flux: a blocked face carries zero normal velocity
        If(faceBlocked(p, dxv), () => { v.x.assign(float(0)); });
        If(faceBlocked(p, dyv), () => { v.y.assign(float(0)); });
        If(faceBlocked(p, dzv), () => { v.z.assign(float(0)); });

        // physical speed cap — a real tank of this size never exceeds a few
        // m/s; anything past that is solver noise, not water
        const spd = v.length();
        If(spd.greaterThan(U.maxSpeed), () => { v.assign(v.div(spd).mul(U.maxSpeed)); });

        textureStore(velA, c, vec4(v, 1)).toWriteOnly();
    })().compute(CELLS).setName('waterProject');

    // ⚠ light velocity diffusion (viscosity). An approximate projection on
    // collocated STORAGE leaves a high-frequency residual the compact Laplacian
    // cannot see; unchecked it grows into the vertical needles that shred the
    // settled pool. Real water is viscous, so a small neighbour blend is both
    // physical and exactly the right filter. The paper does not need this
    // because its multigrid actually removes those modes.
    const mkSmooth = (src, dst, name) => Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const v0 = texture3D(src, p, 0).xyz;
        const avg = texture3D(src, p.add(dxv), 0).xyz
            .add(texture3D(src, p.sub(dxv), 0).xyz)
            .add(texture3D(src, p.add(dyv), 0).xyz)
            .add(texture3D(src, p.sub(dyv), 0).xyz)
            .add(texture3D(src, p.add(dzv), 0).xyz)
            .add(texture3D(src, p.sub(dzv), 0).xyz).mul(1 / 6);
        const v = mix(v0, avg, U.velSmooth).toVar();
        If(isSolid(p), () => { v.assign(vec3(0)); });
        textureStore(dst, c, vec4(v, 1)).toWriteOnly();
    })().compute(CELLS).setName(name);
    const kSmoothAB = mkSmooth(velA, velB, 'waterSmoothAB');
    const kSmoothBA = mkSmooth(velB, velA, 'waterSmoothBA');

    // BISECT ONLY: velB -> velA with the wall clamps, no projection
    const kCopyVel = Fn(() => {
        const c = cellOf(instanceIndex);
        const p = uvwOf(c);
        const v = texture3D(velB, p, 0).xyz.toVar();
        const m = U.wallM;
        If(p.x.lessThan(m.add(TX)), () => { v.x.assign(max(v.x, 0.0)); });
        If(p.x.greaterThan(float(1).sub(m).sub(TX)), () => { v.x.assign(min(v.x, 0.0)); });
        If(p.z.lessThan(m.add(TZ)), () => { v.z.assign(max(v.z, 0.0)); });
        If(p.z.greaterThan(float(1).sub(m).sub(TZ)), () => { v.z.assign(min(v.z, 0.0)); });
        If(p.y.lessThan(m.add(TY)), () => { v.y.assign(max(v.y, 0.0)); });
        If(isSolid(p), () => { v.assign(vec3(0)); });
        textureStore(velA, c, vec4(v, 1)).toWriteOnly();
    })().compute(CELLS).setName('waterCopyVel');

    // ── VOLUME SENSOR ─────────────────────────────────────────────────────
    // Measures the liquid volume in m³ on the GPU. Built first as a
    // DIAGNOSTIC (does this solver actually lose volume, and how fast?) —
    // render-side proxies cannot answer that: at this camera one pixel of
    // waterline is ~2.4% of the pool, so the drift we care about is smaller
    // than the measurement. It is also exactly the sensor a Kim-2007 volume
    // controller needs, so it gets built once and used for both.
    //
    // Reduction = a MIP CHAIN of single linear taps, 64³→32³→…→1³. Same
    // exactness argument as the multigrid restriction: a coarse cell centre
    // lands on the corner shared by its 8 fine cells, so one tap IS their
    // mean. Means, not sums — a sum of 262144 cells would overflow half-float
    // (max 65504); a mean stays in [0,1] and is exact to ~5e-4 relative.
    const volLevels = [];
    let volBuf = null, kVolFrac = null, kVolOut = null, kVolFinal = null;
    const volReduce = [];
    const volFinal = mk('waterVolFinal', 1, 1, 1);   // the ONE true scalar
    if (o.measureVolume) {
        volLevels.push(mk('waterVol0', NX, NY, NZ));
        // ⚠ SMOOTHED Heaviside, not a binary φ≤0 count. Counting whole cells
        // quantises the answer to ~1.6% of the pool per cell layer, which is
        // coarser than the drift being measured — it would report "no loss"
        // for a long time and then jump.
        kVolFrac = Fn(() => {
            const c = cellOf(instanceIndex);
            const p = uvwOf(c);
            const phi = phiTexNode.sample(p).level(0).x;
            const frac = float(0.5).sub(phi.div(float(DX * 3.0))).clamp(0, 1);
            textureStore(volLevels[0], c,
                vec4(isSolid(p).select(float(0), frac), 0, 0, 1)).toWriteOnly();
        })().compute(CELLS).setName('waterVolFrac');

        // ⚠ halve only while EVERY dim is even. The one-tap = mean-of-8 trick
        // needs exact halving; on an odd dim the coarse centre lands on a fine
        // texel centre and the tap returns that ONE texel instead of a mean.
        // Whatever is left (e.g. 4x3x4 for a 64x48x64 grid) is summed by the
        // final kernel. Grids do not have to be powers of two.
        let [lx, ly, lz] = [NX, NY, NZ];
        const halvable = (n) => n === 1 || n % 2 === 0;
        while ((lx > 1 || ly > 1 || lz > 1)
            && halvable(lx) && halvable(ly) && halvable(lz)) {
            const src = volLevels[volLevels.length - 1];
            const [nx, ny, nz] = [Math.max(1, lx >> 1), Math.max(1, ly >> 1), Math.max(1, lz >> 1)];
            const dst = mk('waterVol' + volLevels.length, nx, ny, nz);
            volLevels.push(dst);
            volReduce.push(Fn(() => {
                const c = uvec3(instanceIndex.mod(nx),
                    instanceIndex.div(nx).mod(ny), instanceIndex.div(nx * ny));
                const p = vec3(c).add(0.5).div(vec3(nx, ny, nz));
                textureStore(dst, c,
                    vec4(texture3D(src, p, 0).x, 0, 0, 1)).toWriteOnly();
            })().compute(nx * ny * nz).setName('waterVolReduce' + volLevels.length));
            [lx, ly, lz] = [nx, ny, nz];
        }

        // ⚠⚠ THE CHAIN DOES NOT END AT ONE TEXEL. For 64x48x64 it stops at
        // 4x3x4 (3 is odd), so this final pass must SUM those 48 and write the
        // true global mean into a genuine 1x1x1 texture. Every consumer then
        // reads volFinal — the readback AND the controller.
        // Getting this wrong is not subtle in effect but is silent in code:
        // the controller sampled the 4x3x4 level at uvw 0.5, which returns the
        // MIDDLE TEXEL, i.e. the fill fraction of the central 1/48th of the
        // tank. It drove the water up until that one cell filled and then sat
        // there — a dead-flat plateau at exactly 0.50 m, which is the bottom
        // of that texel's y span. A plateau is a stuck sensor, not a tuned loop.
        const last = volLevels[volLevels.length - 1];
        const [fx, fy, fz] = [lx, ly, lz];
        kVolFinal = Fn(() => {
            const acc = float(0).toVar();
            for (let k = 0; k < fz; k++)
                for (let j = 0; j < fy; j++)
                    for (let i = 0; i < fx; i++)
                        acc.addAssign(texture3D(last,
                            vec3((i + .5) / fx, (j + .5) / fy, (k + .5) / fz), 0).x);
            textureStore(volFinal, uvec3(0, 0, 0),
                vec4(acc.div(fx * fy * fz), 0, 0, 1)).toWriteOnly();
        })().compute(1).setName('waterVolFinal');
        volBuf = new THREE.StorageBufferAttribute(new Float32Array(1), 1);
        kVolOut = Fn(() => {
            storage(volBuf, 'float', 1).element(0)
                .assign(texture3D(volFinal, vec3(0.5), 0).x);
        })().compute(1).setName('waterVolOut');
    }
    const CELL_VOL = (world.x / NX) * (world.y / NY) * (world.z / NZ);

    // ── the PI controller, one texel, entirely on the GPU ─────────────────
    U.volTarget = uniform(1);
    U.vcKp = uniform(o.vcKp);
    U.vcKi = uniform(o.vcKi);
    U.vcMaxRate = uniform(o.vcMaxRate);
    const mkVolCtrl = (src, dst, name) => Fn(() => {
        const mean = texture3D(volFinal, vec3(0.5), 0).x;   // ⚠ volFinal, never the chain tail
        const V = mean.mul(CELLS * CELL_VOL);
        const e = U.volTarget.sub(V).div(U.volTarget);      // relative deficit
        const prev = texture3D(src, vec3(0.5), 0);
        // ⚠ anti-windup: clamp the integral, or a phase the controller cannot
        // win (the collapse, where loss outruns any sane source) charges it up
        // and it overshoots wildly once the pool calms down.
        const I = prev.x.add(e.mul(U.dt.mul(o.vcEvery))).clamp(-0.5, 0.5).toVar();
        const s = e.mul(U.vcKp).add(I.mul(U.vcKi))
            .clamp(U.vcMaxRate.negate(), U.vcMaxRate);
        textureStore(dst, uvec3(0, 0, 0), vec4(I, s, V, 1)).toWriteOnly();
    })().compute(1).setName(name);
    const kVolCtrlAB = o.volumeControl ? mkVolCtrl(volCtrlA, volCtrlB, 'waterVolCtrlAB') : null;
    const kVolCtrlBA = o.volumeControl ? mkVolCtrl(volCtrlB, volCtrlA, 'waterVolCtrlBA') : null;
    const kVolCtrlZero = Fn(() => {
        textureStore(volCtrlA, uvec3(0, 0, 0), vec4(0, 0, 0, 1)).toWriteOnly();
    })().compute(1).setName('waterVolCtrlZero');

    let _volReadback = null;
    // ⚠ ONE sensor path, shared by the readback and the controller. They ran
    // as two hand-written sequences and silently drifted apart — the
    // controller skipped the final sum and read a single texel of a 4x3x4
    // level instead of the global mean.
    async function runVolumeSensor() {
        await renderer.computeAsync(kVolFrac);
        for (const k of volReduce) await renderer.computeAsync(k);
        await renderer.computeAsync(kVolFinal);
    }
    async function measureVolume() {
        if (!kVolFrac) return null;
        await runVolumeSensor();
        await renderer.computeAsync(kVolOut);
        // ⚠ persistent ReadbackBuffer + release(), per fluid_3d.js: passing
        // target=null makes three create/destroy a temp GPUBuffer each call,
        // and on the wgpu-rs/Deno backend that churn starts returning
        // all-zeros after ~37 frames.
        if (!_volReadback) _volReadback = new THREE.ReadbackBuffer(4);
        await renderer.getArrayBufferAsync(volBuf, _volReadback);
        const mean = new Float32Array(_volReadback.buffer)[0];
        _volReadback.release();
        return mean * CELLS * CELL_VOL;
    }

    // ── SURFACE RENDER: raymarch the φ = 0 isosurface ─────────────────────
    // colorNode does the march + shading; depthNode repeats the march for
    // correct occlusion against the scene — the proven pattern from
    // sdf_raymarch_loader.js.
    const surfGeo = new THREE.BoxGeometry(world.x, world.y, world.z);
    const mat = new THREE.MeshBasicNodeMaterial();
    mat.transparent = true;
    // ⚠ FrontSide, not the fire's BackSide: the tank walls are OPAQUE, so
    // the box's BACK faces sit behind/inside them and the depth test kills
    // every fragment (the water never draws). The camera views the tank from
    // outside, so front faces are always available; the slab test derives
    // entry/exit itself, so the ray math is identical either way.
    // ⚠ FrontSide is right for a TANK seen from OUTSIDE (back faces would sit
    // behind the opaque walls and fail the depth test). But when the camera is
    // INSIDE the domain — a character standing in a wide field of liquid — the
    // front faces all point away and NOTHING DRAWS. The symptom is a frame
    // that is pixel-identical no matter what you change about the shading,
    // because the shader never runs. `insideDomain: true` flips it.
    mat.side = o.insideDomain ? THREE.BackSide : THREE.FrontSide;
    mat.depthWrite = false;

    // ⚠ RENDER-SIDE solid mask. The SIM must not clip φ inside solids (that
    // was the evaporation bug), but φ < 0 does survive inside wall cells and
    // the raymarch would happily draw it — which is exactly the vertical
    // streaks climbing the tank walls. Mask solids here, in the renderer only.
    // soft occupancy 0..1 (render only — the sim keeps the hard predicate)
    // ⚠ MUST include the DYNAMIC spheres, not just the baked texture. The
    // baked field only knows about static world geometry, so a ring keyed on
    // it alone can never appear around a wading character — the liquid was
    // colliding with him correctly, the FOAM just could not see him.
    const solidSoft = (uvw) => {
        let v = solidTex ? texture3D(solidTex, uvw, 0).r : float(0);
        if (o.walls) v = max(v, isSolidWalls(uvw).select(float(1), float(0)));
        if (sphereArr) {
            const pw = uvw.sub(vec3(0.5)).mul(U.worldSize);
            for (let i = 0; i < NSPH; i++) {
                const sp = sphereArr.element(i);
                // smooth falloff across ~1.5 cells outside the sphere, so the
                // ring has a soft band instead of a hard silhouette
                const d = pw.sub(sp.xyz).length().sub(sp.w);
                v = max(v, sp.w.greaterThan(0.0).select(
                    float(1).sub(smoothstep(0.0, float(DX * 1.8), d)), float(0)));
            }
        }
        return v;
    };
    // ⚠ BLEND φ toward air across the boundary instead of SELECTING it. A
    // hard select quantises the surface to the voxel grid; the blend lets the
    // interpolated occupancy carry a smooth shoreline.
    // ── render-φ blur infrastructure (only if o.renderBlur > 0) ───────────
    // Separable [1 2 1]/4 per axis; ping-pong between two render-only
    // textures, first pass reading the live sim φ. Ends in renR after one
    // iteration, renT after two — picked at build time.
    let phiRenFinal = null;
    const renBlurKernels = [];
    if (o.renderBlur > 0) {
        const renR = mk('waterPhiRenR'), renT = mk('waterPhiRenT');
        const mkBlur = (src, dst, off, name) => Fn(() => {
            const c = cellOf(instanceIndex);
            const p = uvwOf(c);
            const s = texture3D(src, p, 0).x.mul(2)
                .add(texture3D(src, p.add(off), 0).x)
                .add(texture3D(src, p.sub(off), 0).x).mul(0.25);
            textureStore(dst, c, vec4(s, 0, 0, 1)).toWriteOnly();
        })().compute(CELLS).setName(name);
        renBlurKernels.push(
            mkBlur(phiA, renR, dxv, 'waterRenBlurX1'),
            mkBlur(renR, renT, dyv, 'waterRenBlurY1'),
            mkBlur(renT, renR, dzv, 'waterRenBlurZ1'));
        if (o.renderBlur >= 2) renBlurKernels.push(
            mkBlur(renR, renT, dxv, 'waterRenBlurX2'),
            mkBlur(renT, renR, dyv, 'waterRenBlurY2'),
            mkBlur(renR, renT, dzv, 'waterRenBlurZ2'));
        phiRenFinal = (o.renderBlur >= 2) ? renT : renR;
    }
    // what the SURFACE reads: the blurred render field when enabled, the live
    // sim field otherwise. Sim kernels never touch this node.
    const phiReadNode = phiRenFinal ? texture3D(phiRenFinal) : phiTexNode;

    const phiAt = (uvw) => mix(
        phiReadNode.sample(uvw).level(0).x, float(DX * 4),
        smoothstep(0.30, 0.62, solidSoft(uvw)));
    // the RENDERED field: φ shifted by the meniscus bias. The march, the
    // bisection and the thickness estimate all use this one, so the visible
    // surface is consistently the -bias contour; the normal stays on raw ∇φ
    // (a constant offset has the same gradient).
    const phiR = (uvw) => phiAt(uvw).add(U.surfaceBias);

    // cubic B-spline reconstruction of φ — 8 trilinear taps (Sigg & Hadwiger,
    // GPU Gems 2 ch.20 / Ruijters). The trilinear contour is C⁰ with kinks at
    // every cell face; this one is C², which is what turns sawtooth splash
    // silhouettes into curves. Used only for hit refinement and the normal
    // when o.smoothSurface is on, so the march itself stays one tap per step.
    const TSZ = vec3(o.gridSize[0], o.gridSize[1], o.gridSize[2]);
    const phiCubeRaw = (uvw) => {
        const tc = uvw.mul(TSZ).sub(0.5);
        const b = floor(tc), f = fract(tc);
        const f2 = f.mul(f), f3 = f2.mul(f);
        const w0 = f3.negate().add(f2.mul(3)).sub(f.mul(3)).add(1).div(6);
        const w1 = f3.mul(3).sub(f2.mul(6)).add(4).div(6);
        const w2 = f3.mul(3).negate().add(f2.mul(3)).add(f.mul(3)).add(1).div(6);
        const w3 = f3.div(6);
        const g0 = w0.add(w1), g1 = w2.add(w3);
        // tap centres in texel space (each tap is itself trilinear, so the
        // hardware does half the filtering)
        const h0 = b.add(w1.div(g0)).add(0.5).sub(1.0);
        const h1 = b.add(w3.div(g1)).add(0.5).add(1.0);
        const P = (x, y, z) => phiReadNode.sample(vec3(x, y, z).div(TSZ)).level(0).x;
        const x00 = mix(P(h1.x, h0.y, h0.z), P(h0.x, h0.y, h0.z), g0.x);
        const x10 = mix(P(h1.x, h1.y, h0.z), P(h0.x, h1.y, h0.z), g0.x);
        const x01 = mix(P(h1.x, h0.y, h1.z), P(h0.x, h0.y, h1.z), g0.x);
        const x11 = mix(P(h1.x, h1.y, h1.z), P(h0.x, h1.y, h1.z), g0.x);
        const y0 = mix(x10, x00, g0.y);
        const y1 = mix(x11, x01, g0.y);
        return mix(y1, y0, g0.z);
    };
    // same solid handling + bias as phiR, cubic underneath
    const phiRC = (uvw) => mix(phiCubeRaw(uvw), float(DX * 4),
        smoothstep(0.30, 0.62, solidSoft(uvw))).add(U.surfaceBias);

    // local-space ray → box entry/exit (the box is centred on its origin)
    const localRay = () => {
        const camL = modelWorldMatrixInverse.mul(vec4(cameraPosition, 1)).xyz;
        const exitP = positionLocal;
        const dir = exitP.sub(camL).normalize().toVar();
        const sgn = dir.sign().add(dir.sign().abs().oneMinus());   // sign(0)→+1
        const inv = vec3(1).div(sgn.mul(dir.abs().max(1e-5)));
        const h = U.worldSize.mul(0.5);
        const ta = h.negate().sub(camL).mul(inv);
        const tb = h.sub(camL).mul(inv);
        const lo = ta.min(tb), hi = ta.max(tb);
        const tNear = lo.x.max(lo.y).max(lo.z).max(0.0);
        const tFar = hi.x.min(hi.y).min(hi.z);
        return { camL, dir, tNear, tFar };
    };
    const toUVW = (pl) => pl.div(U.worldSize).add(0.5);

    // march to the φ=0 crossing; returns (t, hitFlag)
    const bisect = (camL, dir, prevT, t, tHit) => {
        // bisection refine between prevT (air) and t (water)
        const a = prevT.toVar(), b2 = t.toVar();
        const phiRef = o.smoothSurface ? phiRC : phiR;   // compile-time pick
        Loop(o.bisectionSteps, () => {
            const m2 = a.add(b2).mul(0.5);
            const pm = phiRef(toUVW(camL.add(dir.mul(m2))));
            If(pm.lessThan(0.0), () => { b2.assign(m2); }).Else(() => { a.assign(m2); });
        });
        tHit.assign(a.add(b2).mul(0.5));
    };
    const march = (camL, dir, tNear, tFar) => {
        const tHit = float(-1).toVar();
        if (o.marchMode === 'adaptive') {
            // ADAPTIVE (sphere-trace on the clamped level set): φ near the
            // band is a distance, and in far air it SATURATES at the §3.4
            // clamp (~4·DX) — so stepping by SAFE·φ walks ~0.3 m strides
            // through empty air and closes to sub-cell strides only where the
            // surface actually is. Two wins at once: typical rays sample
            // ~2× fewer points than the fixed march, AND near-surface
            // resolution is 3× finer, which removes the step-quantization
            // "comb" on grazing silhouettes. SAFE < 1 absorbs |∇φ| drift
            // from advection error and the render blur.
            const FSTEP = float(DX * 0.5), SAFE = float(0.7);
            const t = tNear.add(FSTEP.mul(0.5)).toVar();
            const prevT = t.toVar();
            Loop(o.marchIters ?? 128, () => {
                If(t.greaterThan(tFar), () => { Break(); });
                const ph = phiR(toUVW(camL.add(dir.mul(t))));
                If(ph.lessThan(0.0), () => {
                    bisect(camL, dir, prevT, t, tHit);
                    Break();
                });
                prevT.assign(t);
                t.addAssign(max(FSTEP, ph.mul(SAFE)));
            });
            return tHit;
        }
        const STEPS = o.raymarchSteps;
        const stepT = tFar.sub(tNear).div(STEPS).toVar();
        const t = tNear.add(stepT.mul(0.5)).toVar();
        const prevT = t.toVar();
        const prevPhi = float(1).toVar();
        Loop(STEPS, () => {
            const uvw = toUVW(camL.add(dir.mul(t)));
            const ph = phiR(uvw);
            If(ph.lessThan(0.0), () => {
                bisect(camL, dir, prevT, t, tHit);
                Break();
            });
            prevT.assign(t);
            prevPhi.assign(ph);
            t.addAssign(stepT);
        });
        return tHit;
    };

    // BISECT LADDER: 1 = flat magenta, no depthNode (does the box draw at
    // all?); 2 = debug heatmap, no depthNode; 0 = full.
    if (o.__bisect === 1) {
        mat.colorNode = vec4(1, 0, 1, 1);
    }

    if (o.__bisect !== 1) mat.colorNode = Fn(() => {
        const { camL, dir, tNear, tFar } = localRay();

        // DEBUG: max |v| (red) and max p (blue) along the ray — is the
        // pressure solve producing anything, and are velocities exploding?
        if (o.__debugFields) {
            const stepT = tFar.sub(tNear).div(64).toVar();
            const t = tNear.add(stepT.mul(0.5)).toVar();
            const mv = float(0).toVar();
            const mp = float(0).toVar();
            const mn = float(10).toVar();
            Loop(64, () => {
                const uvw = toUVW(camL.add(dir.mul(t)));
                mv.assign(max(mv, texture3D(velA, uvw, 0).xyz.length()));
                mp.assign(max(mp, texture3D(prsA, uvw, 0).x.abs()));
                mn.assign(min(mn, phiAt(uvw)));
                t.addAssign(stepT);
            });
            // R = |div|*40, G = water mask, B = |p|*40 — is div reaching
            // the solver at all, and does the solver answer?
            const md = float(0).toVar();
            const t2 = tNear.add(stepT.mul(0.5)).toVar();
            Loop(64, () => {
                md.assign(max(md, texture3D(divT, toUVW(camL.add(dir.mul(t2))), 0).x.abs()));
                t2.addAssign(stepT);
            });
            // R = |div|*40, G = water, B = p/4  (hydrostatic needs p≈3.8)
            return vec4(md.mul(40.0).clamp(0, 1),
                mn.lessThan(0.0).select(float(0.3), float(0)),
                mp.div(4.0).clamp(0, 1), 1.0);
            /* superseded scale
            return vec4(md.mul(40.0).clamp(0, 1),
                mn.lessThan(0.0).select(float(0.3), float(0)),
                mp.mul(40.0).clamp(0, 1), 1.0); */
        }

        // DEBUG: min-φ heatmap along the ray — separates "φ has no data"
        // (all warm) from "march/shading broken" (blue column visible).
        if (o.__debugPhi) {
            const stepT = tFar.sub(tNear).div(64).toVar();
            const t = tNear.add(stepT.mul(0.5)).toVar();
            const mn = float(10).toVar();
            Loop(64, () => {
                mn.assign(min(mn, phiAt(toUVW(camL.add(dir.mul(t))))));
                t.addAssign(stepT);
            });
            // UNAMBIGUOUS: green = ray crossed water, red = only air,
            // full alpha — if the interior stays dark the mesh isn't drawing
            const water = mn.lessThan(0.0);
            return vec4(water.select(vec3(0, 1, 0), vec3(1, 0, 0)), 1.0);
        }
        const tHit = march(camL, dir, tNear, tFar);
        tHit.lessThan(0.0).discard();

        const hitL = camL.add(dir.mul(tHit));
        const uvw = toUVW(hitL);

        // normal from ∇φ (central differences; cubic field when smoothSurface,
        // so speculars stop showing the cell lattice)
        const phiN = o.smoothSurface ? phiCubeRaw : phiAt;       // compile-time pick
        const n = normalize(vec3(
            phiN(uvw.add(dxv)).sub(phiN(uvw.sub(dxv))),
            phiN(uvw.add(dyv)).sub(phiN(uvw.sub(dyv))),
            phiN(uvw.add(dzv)).sub(phiN(uvw.sub(dzv)))));

        // thickness estimate: continue the march to the exit or back to air
        const THICK_STEPS = 24;
        const stepT2 = tFar.sub(tHit).div(THICK_STEPS);
        const thick = float(0).toVar();
        const t2 = tHit.add(stepT2.mul(0.5)).toVar();
        Loop(THICK_STEPS, () => {
            const ph = phiR(toUVW(camL.add(dir.mul(t2))));
            If(ph.lessThan(0.0), () => { thick.addAssign(stepT2); });
            t2.addAssign(stepT2);
        });

        // shading: absorption tint by thickness, fresnel to sky, key spec
        const viewD = dir.negate();
        const fresnel = pow(float(1).sub(max(dot(n, viewD), 0.0)), 3.0)
            .mul(0.85).add(0.04);
        const depthTint = mix(U.shallowColor, U.deepColor,
            float(1).sub(exp(thick.negate().mul(U.absorption))));
        const spec = pow(max(dot(reflect(U.keyLightDir.negate(), n), viewD), 0.0), 90.0);
        // ⚠ EMISSIVE GOO. Thin clear liquid over a dark floor renders as
        // nothing — there is no light behind it to transmit and nothing bright
        // to reflect. Driving an emissive term by THICKNESS makes the liquid
        // glow from inside instead of waiting to be lit: deep pools burn,
        // sheets running off a surface stay faint, and the free surface reads
        // even in near-darkness. Set emissiveStrength: 0 for ordinary water.
        const glow = float(1).sub(exp(thick.negate().mul(U.emissiveFalloff)));
        // ⚠ A GLOW MUST DOMINATE, not tint. Adding a little colour on top of a
        // fresnel-lit surface just desaturates it — you get a pale ghost, not
        // light. So the emissive REPLACES the surface as it thickens (mix, not
        // add) and is free to exceed 1.0 so the bloom pass has something to
        // bloom. Reflection survives only as a rim on thin edges.
        const surface = mix(depthTint, U.skyColor, fresnel).add(vec3(spec.mul(0.9)));
        const lit = U.emissiveColor.mul(U.emissiveStrength);
        const col = mix(surface, lit, glow.mul(U.emissiveStrength.min(1.0))).toVar();

        // ── CONTACT RING: bright where the surface MEETS something ────────
        // ⚠ keying this off view-ray thickness was wrong — beside a wading
        // body the ray still crosses a metre of liquid, so the band never
        // fired at the waterline. Proximity to a solid is the real signal,
        // and the linear-filtered occupancy already is one: widen it by
        // taking the max over a small neighbourhood so the ring has body.
        const ring = float(0).toVar();
        const W = float(1.6).mul(vec3(TX, TY, TZ));
        for (const o2 of [vec3(0, 0, 0), W.mul(dxv.normalize()), W.mul(dxv.normalize()).negate(),
            W.mul(dzv.normalize()), W.mul(dzv.normalize()).negate(),
            W.mul(dyv.normalize()).negate()]) {
            ring.assign(max(ring, solidSoft(uvw.add(o2))));
        }
        const shore = float(1).sub(smoothstep(0.0, U.foamWidth, thick));
        const band = max(ring.mul(ring), shore.mul(shore).mul(U.foamShore));
        col.addAssign(U.foamColor.mul(band).mul(U.foamStrength));

        // ── sparkle: hashed glints on the grazing surface ─────────────────
        const hp = uvw.mul(U.sparkleScale);
        const h = fract(sin(hp.x.mul(127.1).add(hp.z.mul(311.7))
            .add(hp.y.mul(74.7))).mul(43758.5453));
        const tw = fract(h.add(U.time.mul(U.sparkleSpeed)));
        const glint = pow(max(float(1).sub(abs(tw.mul(2).sub(1))), 0.0), 40.0);
        col.addAssign(vec3(1.0).mul(glint).mul(fresnel.mul(0.7).add(0.3)).mul(U.sparkleStrength));

        // an emissive surface should also get MORE opaque as it thickens —
        // a glowing pool you can see straight through reads as a hologram
        const op = U.surfaceOpacity.add(glow.mul(U.emissiveStrength).mul(0.30))
            .clamp(0.0, 1.0);
        return vec4(col, op);
    })();

    // correct occlusion vs scene geometry (sdf_raymarch_loader pattern)
    if (!o.__bisect) mat.depthNode = Fn(() => {
        const { camL, dir, tNear, tFar } = localRay();
        const tHit = march(camL, dir, tNear, tFar);
        // ⚠ no discard here — discard inside depthNode silently killed the
        // whole draw on this stack. On a miss, fall back to the box exit
        // depth; those pixels are color-discarded anyway.
        const tSafe = tHit.lessThan(0.0).select(tFar, tHit);
        const hitLocal = camL.add(dir.mul(tSafe));
        const hitWorld = modelWorldMatrix.mul(vec4(hitLocal, 1)).xyz;
        const viewZ = cameraViewMatrix.mul(vec4(hitWorld, 1)).z;
        return viewZToPerspectiveDepth(viewZ, cameraNear, cameraFar);
    })();

    const surfaceMesh = new THREE.Mesh(surfGeo, mat);
    surfaceMesh.frustumCulled = false;
    // The simulation lives in domain-local space (emitters, spheres and collider sampling all subtract
    // domainCenter) and the raymarch runs in the mesh's local space, so the mesh sits AT domainCenter: the
    // drawn water lines up with its physics, and scenes never translate it themselves.
    surfaceMesh.position.copy(domainCenter);

    // ── stepping ──────────────────────────────────────────────────────────
    let simulationTime = 0;
    let simAccumulator = 0;
    let frameCount = 0;

    let _loggedOnce = false;
    async function simSubStep() {
        if (!_loggedOnce) {
            _loggedOnce = true;
            const solver = (MG.length > 1 && !o.__noMultigrid)
                ? 'multigrid ' + MG.map(l => l.nx + '³').join('→')
                    + ' x' + o.mgCycles + 'V (pre ' + o.mgPre + ' post ' + o.mgPost
                    + ' coarse ' + o.mgCoarse + ' w ' + o.mgOmega + ')'
                : 'jacobi x' + o.pressureIters;
            console.log('[water] grid', NX+'x'+NY+'x'+NZ, '| pressure', solver,
                '| fixedStep 1/' + Math.round(1/o.fixedStep), '| extrap', o.extrapolationPasses,
                '| gravity', o.gravity, '| DX', DX.toFixed(4));
        }
        // Algorithm 1 (paper §3.2): extrapolate → reinit(periodic) → advect
        // + forces → (no remeshing on the uniform grid) → incompressibility
        for (let i = 0; i < o.extrapolationPasses; i += 2) {
            await renderer.computeAsync(kExtrapAB);
            await renderer.computeAsync(kExtrapBA);
        }
        if (!o.__noReinit && o.reinitEvery > 0 && frameCount % o.reinitEvery === 0 && frameCount > 0) {
            for (let i = 0; i < o.reinitIters; i += 2) {
                await renderer.computeAsync(phiInA ? kReinitAB : kReinitBA);
                phiInA = !phiInA;
                phiTexNode.value = phiInA ? phiA : phiB;
                await renderer.computeAsync(phiInA ? kReinitAB : kReinitBA);
                phiInA = !phiInA;
                phiTexNode.value = phiInA ? phiA : phiB;
            }
        }
        // volume control: refresh the sensor + controller every vcEvery
        // substeps (the loop closes on the GPU — kDiv samples volCtrlNode)
        if (o.volumeControl && frameCount % o.vcEvery === 0) {
            await runVolumeSensor();
            await renderer.computeAsync(volCtrlInA ? kVolCtrlAB : kVolCtrlBA);
            volCtrlInA = !volCtrlInA;
            volCtrlNode.value = volCtrlInA ? volCtrlA : volCtrlB;
        }
        await renderer.computeAsync(kAdvectVel);
        await renderer.computeAsync(phiInA ? kPhiFwdA : kPhiFwdB);
        await renderer.computeAsync(phiInA ? kPhiCorrAB : kPhiCorrBA);
        phiInA = !phiInA;
        phiTexNode.value = phiInA ? phiA : phiB;

        if (o.__noPressure) {
            // BISECT: skip incompressibility; velB -> velA straight through
            await renderer.computeAsync(kCopyVel);
        } else {
            await renderer.computeAsync(kDiv);
            if (MG.length > 1 && !o.__noMultigrid) {
                await mgSolve();
            } else {
                for (let i = 0; i < o.pressureIters; i += 2) {
                    await renderer.computeAsync(kJacobiAB);
                    await renderer.computeAsync(kJacobiBA);
                }
            }
            await renderer.computeAsync(kProject);
        }
        // viscosity: run as a PAIR so the result lands back in velA
        if (o.velSmooth > 0) {
            await renderer.computeAsync(kSmoothAB);
            await renderer.computeAsync(kSmoothBA);
        }
        frameCount++;
    }

    async function step(delta = 1 / 60) {
        delta = Math.min(delta, 1 / 30);
        simAccumulator += delta;
        const simStep = o.fixedStep;
        const maxAcc = simStep * o.maxSubSteps;
        if (simAccumulator > maxAcc) simAccumulator = maxAcc;
        U.dt.value = simStep;
        let ran = false;
        while (simAccumulator >= simStep) {
            simulationTime += simStep;
            U.time.value = simulationTime;
            await simSubStep();
            simAccumulator -= simStep;
            ran = true;
        }
        // refresh the render-φ blur ONCE per frame, not per substep — the
        // sensor experiment measured tiny per-substep dispatches as mostly
        // submission overhead, and the surface is only read once per frame.
        if (ran) for (const k of renBlurKernels) await renderer.computeAsync(k);
    }

    async function warmup(seconds = o.warmupSeconds) {
        U.dt.value = o.fixedStep;
        while (simulationTime < seconds) {
            simulationTime += o.fixedStep;
            await simSubStep();
        }
        for (const k of renBlurKernels) await renderer.computeAsync(k);
        return api;
    }

    // ── voxelise the static world into the solid field ────────────────────
    // One-time CPU pass at setup (allowed — only PER-FRAME CPU loops are
    // banned). Ray-parity via three-mesh-bvh: shoot +X from each cell centre
    // and count crossings; odd = inside. The BVH is what makes half a million
    // point tests take seconds instead of minutes.
    async function bakeColliders() {
        if (!solidTex) return;
        const { MeshBVH } = await import('three-mesh-bvh');
        const meshes = [];
        for (const root of o.colliderMeshes) {
            root.updateMatrixWorld(true);
            root.traverse((m) => { if (m.isMesh && m.geometry?.attributes?.position) meshes.push(m); });
        }
        const bvhs = meshes.map(m => ({ bvh: new MeshBVH(m.geometry), inv: m.matrixWorld.clone().invert() }));
        const data = solidTex.image.data;
        data.fill(0);
        const org = new THREE.Vector3(), dir = new THREE.Vector3(1, 0, 0);
        const ray = new THREE.Ray(org, dir);
        // domain-local world position of a cell centre
        const half = world.clone().multiplyScalar(0.5);
        let filled = 0;
        for (let k = 0; k < NZ; k++) for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
            const wx = (i + 0.5) / NX * world.x - half.x;
            const wy = (j + 0.5) / NY * world.y - half.y;
            const wz = (k + 0.5) / NZ * world.z - half.z;
            let inside = false;
            for (const { bvh, inv } of bvhs) {
                ray.origin.set(wx, wy, wz).add(domainCenter).applyMatrix4(inv);
                ray.direction.set(1, 0, 0).transformDirection(inv).normalize();
                let hits = 0;
                bvh.raycast(ray, THREE.DoubleSide).forEach(() => hits++);
                if (hits & 1) { inside = true; break; }
            }
            if (inside) { data[i + j * NX + k * NX * NY] = 255; filled++; }
        }
        solidTex.needsUpdate = true;
        console.log('[water] baked ' + meshes.length + ' collider mesh(es) → '
            + filled + '/' + CELLS + ' solid cells ('
            + (filled / CELLS * 100).toFixed(1) + '%)');
    }

    // ⚠ the TARGET is the initial state measured BY THE SAME SENSOR, not the
    // analytic column volume. The smoothed Heaviside reads a curvature-
    // dependent hair high, so comparing an analytic target against a measured
    // value would bake that bias in as a permanent offset the integral term
    // would then chase forever.
    async function captureVolumeTarget() {
        await renderer.computeAsync(kVolCtrlZero);
        volCtrlInA = true; volCtrlNode.value = volCtrlA;
        if (!kVolFrac) return;
        const v = await measureVolume();
        if (v > 0) U.volTarget.value = o.volumeTarget ?? v;
        console.log('[water] volume target = ' + U.volTarget.value.toFixed(5) + ' m³'
            + (o.volumeControl ? ' (PI control ON: kp ' + o.vcKp + ' ki ' + o.vcKi
                + ' max ' + o.vcMaxRate + '/s every ' + o.vcEvery + ' substeps)'
                : ' (control OFF — measuring only)'));
    }
    await bakeColliders();
    await runInit();
    await captureVolumeTarget();

    const api = {
        surfaceMesh,
        uniforms: U,
        params: o,
        get simTime() { return simulationTime; },
        step,
        warmup,
        /** liquid volume in m³, measured on the GPU (needs measureVolume:true) */
        measureVolume,
        /**
         * Dynamic colliders, in WORLD space. Call once per frame with the
         * bones you want the liquid to feel:
         *   water.setSpheres(['head','chest','hips','leftHand','rightHand',
         *       'leftFoot','rightFoot'].map(b => {
         *           const n = vrm.humanoid.getNormalizedBoneNode(b);
         *           const p = n.getWorldPosition(new THREE.Vector3());
         *           return { x: p.x, y: p.y, z: p.z, r: 0.11 };
         *       }));
         * Radii are world metres. Anything past maxSpheres is ignored; the
         * unused slots are disabled (w <= 0) so they cost a compare, not a
         * phantom collider at the origin.
         */
        /** emitters in WORLD space: [{x,y,z,r,vx,vy,vz}] — r<=0 disables one */
        setEmitters(list) {
            if (!emitArr) return;
            for (let i = 0; i < NEMI; i++) {
                const e = list && list[i];
                if (e && e.r > 0) {
                    emitArr.array[i].set(e.x - domainCenter.x, e.y - domainCenter.y,
                        e.z - domainCenter.z, e.r);
                    emitVel.array[i].set(e.vx || 0, e.vy || 0, e.vz || 0, 0);
                } else {
                    emitArr.array[i].set(0, 0, 0, -1);
                    emitVel.array[i].set(0, 0, 0, 0);
                }
            }
            emitArr.needsUpdate = true; emitVel.needsUpdate = true;
        },
        setSpheres(list) {
            if (!sphereArr) return;
            const arr = sphereArr.array;
            for (let i = 0; i < NSPH; i++) {
                const s = list && list[i];
                const v = arr[i];
                if (s && s.r > 0) {
                    v.set(s.x - domainCenter.x, s.y - domainCenter.y,
                        s.z - domainCenter.z, s.r);
                } else { v.set(0, 0, 0, -1); }
            }
            sphereArr.needsUpdate = true;
        },
        /** reset to the initial dam-break state */
        async reset() {
            simulationTime = 0; simAccumulator = 0; frameCount = 0;
            phiInA = true; phiTexNode.value = phiA;
            await runInit();
            await captureVolumeTarget();
        },
        dispose() {
            [velA, velB, phiA, phiB, phiHat, divT, prsA, prsB,
                volCtrlA, volCtrlB, volFinal].forEach(t => t.dispose?.());
            volLevels.forEach(t => t.dispose?.());
            MG.forEach(l => [l.r, l.b, l.phiTex, l.L > 0 ? l.p : null,
                l.L > 0 ? l.p2 : null].forEach(t => t?.dispose?.()));
            surfGeo.dispose();
            mat.dispose?.();
        },
    };
    return api;
}

export default createWaterSim;
