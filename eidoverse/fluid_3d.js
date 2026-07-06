// fluid_3d.js
//
// A 3D MLS-MPM fluid SYSTEM (not a one-shot block drop). Built on the
// official three.js `webgpu_compute_particles_fluid` solver, wrapped into
// a reusable system with the pieces an agent actually needs:
//
//   • Emitters   — continuous sources (a pour spout, a hose, rain, a
//                  fountain jet). Spawn particles over time with a velocity.
//   • Domain     — the bound the fluid lives in: a box OR a cylinder
//                  (a glass / tank / basin). Fluid collides with its walls.
//   • Colliders  — sphere obstacles the fluid flows around.
//   • Initial fill — optional block of fluid present at t=0.
//
// Everything is three.js/TSL and runs in the eidoverse engine via
// renderer.compute — no raw WebGPU, no separate render loop.
//
// All positions are in NORMALIZED [0,1]³ domain space (the MLS-MPM grid).
// Render it with surfaceMesh() below (GPU raymarched surface) or as
// instanced spheres via positionNode. NOT with three's MarchingCubes —
// that repolygonizes on CPU every frame and tanks the render to ~1fps.
//
// Agent API
// ---------
//
//   const { createFluid3D } = await import(globalThis.EIDOVERSE_DIR + 'fluid_3d.js');
//   const fluid = await createFluid3D(renderer, {
//       maxParticles: 30000,
//       gridSize: [64, 64, 64],
//       gravity: [0, -96, 0],
//       // CONTAINMENT: the [0,1]³ grid box itself has NO solid walls — a
//       // vessel is the CONTAINER object (cylinder cup: interior walls up
//       // to the rim + a floor; open above the rim for pour-in/overflow).
//       // Match it to the VISIBLE vessel's interior, in [0,1] domain coords:
//       container: { center: [0.5, 0.5], radius: 0.42, floorY: 0.02, rimY: 0.25 },
//       initialFill: null,   // or { x0,y0,z0, x1,y1,z1, count } block at t=0
//   });
//
//   // a pour spout — emits `rate` particles/sec downward at the lip:
//   const spout = fluid.addEmitter({
//       position: [0.5, 0.92, 0.5],  // [0,1] domain coords
//       velocity: [0, -0.6, 0],      // [0,1]/sec
//       rate: 9000, radius: 0.04,
//   });
//   spout.enabled = false;           // toggle the pour on/off any time
//
//   fluid.setColliders([{ center: [0.5, 0.3, 0.5], radius: 0.12 }]); // obstacle
//
//   // surface water (the flowing-liquid look): boxMin/boxMax place the
//   // [0,1]^3 domain in WORLD space INSIDE the shader — set them to the
//   // world box you want and do NOT also transform the returned mesh
//   // (a scaled/moved mesh makes the raymarch sample density in the wrong
//   // place = invisible water at a ghost location).
//   //
//   // THE DOMAIN IS THE CONTAINER. Its walls and floor are the invisible
//   // vessel the fluid actually collides with — size them to coincide with
//   // the VISIBLE vessel's interior (basin walls, glass walls, floor). A
//   // domain bigger/taller than the prop = fluid sloshing around an
//   // invisible box hovering in mid-air. Only the ROOF should be generous:
//   // it never reads on camera and gives a pour its falling distance and
//   // splashes their headroom.
//   scene.add(fluid.surfaceMesh({ boxMin: [-1,-1,-1], boxMax: [1,1,1],
//                                 iso: 0.6, steps: 128, color: 0x66c2ee }));
//
//   // per frame:
//   fluid.step(1/60);
//   const pos = await fluid.readPositions();   // active particles, [0,1]³ xyz

export async function createFluid3D(renderer, opts = {}) {
    (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('fluid_3d');
    const THREE = globalThis.THREE;
    const tsl = await import('npm:three@0.184.0/tsl');
    const {
        Fn, If, Return, Break, instancedArray, instanceIndex, uniform, attribute,
        float, clamp, struct, atomicStore, int, uint, ivec3, array, vec2, vec3,
        atomicAdd, Loop, atomicLoad, max, min, pow, mat3, vec4, cross, step, length, sqrt,
        normalize, dot, abs, floor, mix, cameraPosition, positionWorld, reflect,
        viewportSharedTexture, screenUV, refract, exp, texture, equirectUV, smoothstep,
    } = tsl;

    const maxParticles = opts.maxParticles ?? 30000;
    const gs = opts.gridSize ?? [64, 64, 64];
    const gridSize = new THREE.Vector3(gs[0], gs[1], gs[2]);
    const workgroupSize = 64;
    const fixedPointMultiplier = 1e7;
    const cellCount = gridSize.x * gridSize.y * gridSize.z;

    // ---- buffers ----
    const particleStruct = struct({ position: { type: 'vec3' }, velocity: { type: 'vec3' }, C: { type: 'mat3' } });
    const STRIDE = 20; // floats per particle (vec3 pad 4, vec3 pad 4, mat3 12)
    const particleArray = new Float32Array(maxParticles * STRIDE);
    // Park all particles far below the domain initially (inactive look).
    for (let i = 0; i < maxParticles; i++) particleArray[i * STRIDE + 1] = -10.0;

    // Optional initial fill block.
    let initialActive = 0;
    if (opts.initialFill) {
        const f = opts.initialFill;
        const n = Math.min(f.count ?? 8000, maxParticles);
        for (let i = 0; i < n; i++) {
            particleArray[i * STRIDE]     = f.x0 + Math.random() * (f.x1 - f.x0);
            particleArray[i * STRIDE + 1] = f.y0 + Math.random() * (f.y1 - f.y0);
            particleArray[i * STRIDE + 2] = f.z0 + Math.random() * (f.z1 - f.z0);
        }
        initialActive = n;
    }
    const particleBuffer = instancedArray(particleArray, particleStruct);

    const cellStruct = struct({
        x: { type: 'int', atomic: true }, y: { type: 'int', atomic: true },
        z: { type: 'int', atomic: true }, mass: { type: 'int', atomic: true },
    });
    const cellBuffer = instancedArray(cellCount, cellStruct);
    const cellBufferFloat = instancedArray(cellCount, 'vec4');

    // Precomputed uniform sphere directions for emitter jitter.
    const randArr = new Float32Array(maxParticles * 4);
    for (let i = 0; i < maxParticles; i++) {
        const th = Math.random() * 2 * Math.PI, u = Math.random() * 2 - 1, r = Math.cbrt(Math.random());
        randArr[i*4] = Math.sqrt(1-u*u)*Math.cos(th)*r; randArr[i*4+1] = Math.sqrt(1-u*u)*Math.sin(th)*r; randArr[i*4+2] = u*r;
    }
    const randomBuffer = instancedArray(randArr, 'vec4');

    // ---- uniforms ----
    const gridSizeUniform = uniform(gridSize);
    const stiffnessUniform = uniform(opts.stiffness ?? 50);
    const restDensityUniform = uniform(opts.restDensity ?? 1.5);
    const dynamicViscosityUniform = uniform(opts.viscosity ?? 0.1);
    const dtUniform = uniform(1 / 60);
    const g = opts.gravity ?? [0, -(9.81 * 9.81), 0];
    const gravityUniform = uniform(new THREE.Vector3(g[0], g[1], g[2]));

    // The sim domain is ALWAYS the full [0,1]³ grid box (spout → glass →
    // table all live in it). A CONTAINER is a boundary OBJECT inside the
    // domain — a cup the fluid pours into and is bounded by. Cylinder cup:
    // interior radius, floor height, rim height (open above the rim so you
    // can pour in / overflow). All in [0,1] domain coords.
    // Accept `container` OR the header's long-documented `domain: {shape:
    // 'cylinder'}` spelling — the latter was silently ignored (containerOn
    // stayed 0), so pours fell through a wall-less grid and "disappeared at
    // the edge of the domain" instead of accumulating in the vessel.
    const c = opts.container
        ?? ((opts.domain && opts.domain.shape === 'cylinder') ? opts.domain : null);
    const containerOn = uniform(c ? 1 : 0, 'int');
    const containerCenter = uniform(new THREE.Vector2(c?.center?.[0] ?? 0.5, c?.center?.[1] ?? 0.5));
    const containerRadius = uniform(c?.radius ?? 0.35);
    const containerFloorY = uniform(c?.floorY ?? 0.04);
    const containerRimY = uniform(c?.rimY ?? 0.7);

    // emitter (set per-dispatch in step). A pour spawns each frame's batch
    // spread along a thin vertical COLUMN below the spout (xz = emitRadius
    // thin, y = emitColumnLen tall) so the local density stays near rest
    // instead of a dense point-cluster that the MLS-MPM pressure explodes.
    const emitPos = uniform(new THREE.Vector3());
    const emitVel = uniform(new THREE.Vector3());
    const emitRadius = uniform(0.02);
    const emitColumnLen = uniform(0.25);
    const emitBase = uniform(0, 'uint');

    // sphere colliders (xyz=center, w=radius)
    const MAX_COLLIDERS = 8;
    const colliderArr = instancedArray(new Float32Array(MAX_COLLIDERS * 4), 'vec4');
    const colliderCount = uniform(0, 'int');

    const encodeFixedPoint = (f32) => int(f32.mul(fixedPointMultiplier));
    const decodeFixedPoint = (i32) => float(i32).div(fixedPointMultiplier);
    const GY_GZ = int(gridSize.y * gridSize.z), GZ = int(gridSize.z);
    const MP = uint(maxParticles);

    const weightsOf = (cellDiff) => {
        const w0 = float(0.5).mul(float(0.5).sub(cellDiff)).mul(float(0.5).sub(cellDiff));
        const w1 = float(0.75).sub(cellDiff.mul(cellDiff));
        const w2 = float(0.5).mul(float(0.5).add(cellDiff)).mul(float(0.5).add(cellDiff));
        return array([w0, w1, w2]).toConst('weights');
    };

    // ---- emission kernel: write `count` particles starting at emitBase ----
    // Spawn in a thin disc (xz spread, squashed y) so a downward emitter
    // makes a STREAM, not an expanding ball.
    const emitKernel = Fn(() => {
        const idx = emitBase.add(instanceIndex).mod(MP);
        const r = randomBuffer.element(idx).xyz;
        // thin in xz, spread DOWN a column in y → low-density stream segment
        const jit = vec3(r.x.mul(emitRadius), r.y.abs().negate().mul(emitColumnLen), r.z.mul(emitRadius));
        particleBuffer.element(idx).get('position').assign(emitPos.add(jit));
        particleBuffer.element(idx).get('velocity').assign(emitVel.mul(gridSizeUniform));
        particleBuffer.element(idx).get('C').assign(mat3(0));
    });

    const clearGridKernel = Fn(() => {
        atomicStore(cellBuffer.element(instanceIndex).get('x'), 0);
        atomicStore(cellBuffer.element(instanceIndex).get('y'), 0);
        atomicStore(cellBuffer.element(instanceIndex).get('z'), 0);
        atomicStore(cellBuffer.element(instanceIndex).get('mass'), 0);
        // Also clear the float mirror. updateGrid early-returns for empty
        // cells, so without this their density (.w) would stay frozen at the
        // last value the fluid deposited — leaving ghost blobs wherever the
        // fluid passed through. The surface raymarch samples .w, so it MUST
        // be zeroed each frame.
        cellBufferFloat.element(instanceIndex).assign(vec4(0));
    })().compute(cellCount);

    const p2g1Kernel = Fn(() => {
        const particlePosition = particleBuffer.element(instanceIndex).get('position').toConst('pp');
        const particleVelocity = particleBuffer.element(instanceIndex).get('velocity').toConst('pv');
        const C = particleBuffer.element(instanceIndex).get('C').toConst('C');
        const gridPosition = particlePosition.mul(gridSizeUniform).toVar();
        const cellIndex = ivec3(gridPosition).sub(1).toConst('ci');
        const cellDiff = gridPosition.fract().sub(0.5).toConst('cd');
        const weights = weightsOf(cellDiff);
        Loop({ start: 0, end: 3, type: 'int', name: 'gx', condition: '<' }, ({ gx }) => {
        Loop({ start: 0, end: 3, type: 'int', name: 'gy', condition: '<' }, ({ gy }) => {
        Loop({ start: 0, end: 3, type: 'int', name: 'gz', condition: '<' }, ({ gz }) => {
            const weight = weights.element(gx).x.mul(weights.element(gy).y).mul(weights.element(gz).z);
            const cellX = cellIndex.add(ivec3(gx, gy, gz)).toConst();
            const cellDist = vec3(cellX).add(0.5).sub(gridPosition).toConst('cdist');
            const Q = C.mul(cellDist);
            const velContrib = weight.mul(particleVelocity.add(Q)).toConst('vc');
            const cellPtr = cellX.x.mul(GY_GZ).add(cellX.y.mul(GZ)).add(cellX.z).toConst();
            const cell = cellBuffer.element(cellPtr);
            atomicAdd(cell.get('x'), encodeFixedPoint(velContrib.x));
            atomicAdd(cell.get('y'), encodeFixedPoint(velContrib.y));
            atomicAdd(cell.get('z'), encodeFixedPoint(velContrib.z));
            atomicAdd(cell.get('mass'), encodeFixedPoint(weight));
        }); }); });
    })().compute(maxParticles, [workgroupSize, 1, 1]);

    const p2g2Kernel = Fn(() => {
        const particlePosition = particleBuffer.element(instanceIndex).get('position').toConst('pp');
        const gridPosition = particlePosition.mul(gridSizeUniform).toVar();
        const cellIndex = ivec3(gridPosition).sub(1).toConst('ci');
        const cellDiff = gridPosition.fract().sub(0.5).toConst('cd');
        const weights = weightsOf(cellDiff);
        const density = float(0).toVar('density');
        Loop({ start: 0, end: 3, type: 'int', name: 'gx', condition: '<' }, ({ gx }) => {
        Loop({ start: 0, end: 3, type: 'int', name: 'gy', condition: '<' }, ({ gy }) => {
        Loop({ start: 0, end: 3, type: 'int', name: 'gz', condition: '<' }, ({ gz }) => {
            const weight = weights.element(gx).x.mul(weights.element(gy).y).mul(weights.element(gz).z);
            const cellX = cellIndex.add(ivec3(gx, gy, gz)).toConst();
            const cellPtr = cellX.x.mul(GY_GZ).add(cellX.y.mul(GZ)).add(cellX.z).toConst();
            density.addAssign(decodeFixedPoint(atomicLoad(cellBuffer.element(cellPtr).get('mass'))).mul(weight));
        }); }); });
        const volume = float(1).div(density);
        const pressure = max(0.0, pow(density.div(restDensityUniform), 5.0).sub(1).mul(stiffnessUniform)).toConst('pr');
        const stress = mat3(pressure.negate(), 0, 0, 0, pressure.negate(), 0, 0, 0, pressure.negate()).toVar('stress');
        const dudv = particleBuffer.element(instanceIndex).get('C').toConst('C');
        stress.addAssign(dudv.add(dudv.transpose()).mul(dynamicViscosityUniform));
        const eq16Term0 = volume.mul(-4).mul(stress).mul(dtUniform);
        Loop({ start: 0, end: 3, type: 'int', name: 'gx', condition: '<' }, ({ gx }) => {
        Loop({ start: 0, end: 3, type: 'int', name: 'gy', condition: '<' }, ({ gy }) => {
        Loop({ start: 0, end: 3, type: 'int', name: 'gz', condition: '<' }, ({ gz }) => {
            const weight = weights.element(gx).x.mul(weights.element(gy).y).mul(weights.element(gz).z);
            const cellX = cellIndex.add(ivec3(gx, gy, gz)).toConst();
            const cellDist = vec3(cellX).add(0.5).sub(gridPosition).toConst('cdist');
            const momentum = eq16Term0.mul(weight).mul(cellDist).toConst('mom');
            const cellPtr = cellX.x.mul(GY_GZ).add(cellX.y.mul(GZ)).add(cellX.z).toConst();
            const cell = cellBuffer.element(cellPtr);
            atomicAdd(cell.get('x'), encodeFixedPoint(momentum.x));
            atomicAdd(cell.get('y'), encodeFixedPoint(momentum.y));
            atomicAdd(cell.get('z'), encodeFixedPoint(momentum.z));
        }); }); });
    })().compute(maxParticles, [workgroupSize, 1, 1]);

    const updateGridKernel = Fn(() => {
        const cell = cellBuffer.element(instanceIndex);
        const mass = decodeFixedPoint(atomicLoad(cell.get('mass'))).toConst();
        If(mass.lessThanEqual(0), () => { Return(); });
        const vx = decodeFixedPoint(atomicLoad(cell.get('x'))).div(mass).toVar();
        const vy = decodeFixedPoint(atomicLoad(cell.get('y'))).div(mass).toVar();
        const vz = decodeFixedPoint(atomicLoad(cell.get('z'))).div(mass).toVar();
        const x = int(instanceIndex).div(GY_GZ);
        const y = int(instanceIndex).div(GZ).mod(int(gridSize.y));
        const z = int(instanceIndex).mod(GZ);
        If(x.lessThan(int(1)).or(x.greaterThan(int(gridSize.x).sub(int(2)))), () => { vx.assign(0); });
        If(y.lessThan(int(1)).or(y.greaterThan(int(gridSize.y).sub(int(2)))), () => { vy.assign(0); });
        If(z.lessThan(int(1)).or(z.greaterThan(int(gridSize.z).sub(int(2)))), () => { vz.assign(0); });
        cellBufferFloat.element(instanceIndex).assign(vec4(vx, vy, vz, mass));
    })().compute(cellCount);

    const g2pKernel = Fn(() => {
        const particlePosition = particleBuffer.element(instanceIndex).get('position').toVar('pp');
        const gridPosition = particlePosition.mul(gridSizeUniform).toVar();
        const particleVelocity = vec3(0).toVar();
        const cellIndex = ivec3(gridPosition).sub(1).toConst('ci');
        const cellDiff = gridPosition.fract().sub(0.5).toConst('cd');
        const weights = weightsOf(cellDiff);
        const B = mat3(0).toVar('B');
        Loop({ start: 0, end: 3, type: 'int', name: 'gx', condition: '<' }, ({ gx }) => {
        Loop({ start: 0, end: 3, type: 'int', name: 'gy', condition: '<' }, ({ gy }) => {
        Loop({ start: 0, end: 3, type: 'int', name: 'gz', condition: '<' }, ({ gz }) => {
            const weight = weights.element(gx).x.mul(weights.element(gy).y).mul(weights.element(gz).z);
            const cellX = cellIndex.add(ivec3(gx, gy, gz)).toConst();
            const cellDist = vec3(cellX).add(0.5).sub(gridPosition).toConst('cdist');
            const cellPtr = cellX.x.mul(GY_GZ).add(cellX.y.mul(GZ)).add(cellX.z).toConst();
            const wv = cellBufferFloat.element(cellPtr).xyz.mul(weight).toConst('wv');
            B.addAssign(mat3(wv.mul(cellDist.x), wv.mul(cellDist.y), wv.mul(cellDist.z)));
            particleVelocity.addAssign(wv);
        }); }); });
        particleBuffer.element(instanceIndex).get('C').assign(B.mul(4));
        particleVelocity.addAssign(gravityUniform.mul(dtUniform));
        particleVelocity.divAssign(gridSizeUniform);          // → [0,1] space
        particlePosition.addAssign(particleVelocity.mul(dtUniform));

        // keep inside the grid (stability)
        particlePosition.assign(clamp(particlePosition, vec3(1).div(gridSizeUniform), vec3(gridSize).sub(1).div(gridSizeUniform)));

        // CONTAINER collision: a cup the fluid is poured INTO. Below the rim
        // the fluid is bounded by the interior walls (radius) and sits on the
        // cup floor. Above the rim it's open (free fall / overflow). The cup
        // is a boundary OBJECT inside the domain, not the domain itself.
        If(containerOn.equal(int(1)), () => {
            const dx = particlePosition.x.sub(containerCenter.x);
            const dz = particlePosition.z.sub(containerCenter.y);
            const rad = sqrt(dx.mul(dx).add(dz.mul(dz))).toVar();
            // Inside the cup's vertical span → keep within walls + above floor.
            If(particlePosition.y.lessThan(containerRimY), () => {
                If(rad.greaterThan(containerRadius), () => {
                    const s = containerRadius.div(rad.max(1e-5));
                    particlePosition.x.assign(containerCenter.x.add(dx.mul(s)));
                    particlePosition.z.assign(containerCenter.y.add(dz.mul(s)));
                    particleVelocity.x.mulAssign(0.4);
                    particleVelocity.z.mulAssign(0.4);
                });
                If(particlePosition.y.lessThan(containerFloorY), () => {
                    particlePosition.y.assign(containerFloorY);
                    particleVelocity.y.mulAssign(-0.1);   // settle, slight damped bounce
                });
            });
        });

        // SPHERE colliders (obstacles) — push particles out.
        Loop(colliderCount, ({ i: ci }) => {
            const s = colliderArr.element(ci);
            const d = particlePosition.sub(s.xyz);
            const dl = length(d).toVar();
            If(dl.lessThan(s.w), () => {
                particlePosition.assign(s.xyz.add(d.div(dl.max(1e-5)).mul(s.w)));
            });
        });

        particleVelocity.mulAssign(gridSizeUniform);          // → grid space
        particleBuffer.element(instanceIndex).get('position').assign(particlePosition);
        particleBuffer.element(instanceIndex).get('velocity').assign(particleVelocity);
    })().compute(maxParticles, [workgroupSize, 1, 1]);

    // ---- emitter system (JS-driven dispatch of the GPU emit kernel) ----
    const emitters = [];
    let writePtr = 0, totalEmitted = initialActive, activeCount = initialActive;
    let _readback = null;

    function setKernelCounts(n) {
        p2g1Kernel.count = n; p2g2Kernel.count = n; g2pKernel.count = n;
    }
    setKernelCounts(Math.max(1, activeCount));

    return {
        get count() { return activeCount; },
        particleBuffer,

        addEmitter(e) {
            const em = {
                position: e.position ?? [0.5, 0.9, 0.5],
                velocity: e.velocity ?? [0, -0.5, 0],
                rate: e.rate ?? 6000,
                radius: e.radius ?? 0.02,
                columnLen: e.columnLen ?? 0.25,
                enabled: e.enabled ?? true,
                _carry: 0,
            };
            emitters.push(em);
            return em;
        },
        setColliders(list) {
            const n = Math.min(list.length, MAX_COLLIDERS);
            for (let k = 0; k < n; k++) {
                colliderArr.value.array[k*4] = list[k].center[0]; colliderArr.value.array[k*4+1] = list[k].center[1];
                colliderArr.value.array[k*4+2] = list[k].center[2]; colliderArr.value.array[k*4+3] = list[k].radius;
            }
            colliderArr.value.needsUpdate = true;
            colliderCount.value = n;
        },

        step(dt) {
            const d = Math.min(Math.max(dt ?? 1/60, 1e-5), 1/60);
            dtUniform.value = d;

            // 1) emit from each active emitter (GPU kernel writes the ring).
            for (const em of emitters) {
                if (!em.enabled) continue;
                em._carry += em.rate * d;
                let n = Math.floor(em._carry);
                if (n <= 0) continue;
                em._carry -= n;
                n = Math.min(n, maxParticles);
                emitPos.value.set(em.position[0], em.position[1], em.position[2]);
                emitVel.value.set(em.velocity[0], em.velocity[1], em.velocity[2]);
                emitRadius.value = em.radius;
                emitColumnLen.value = em.columnLen;
                emitBase.value = writePtr;
                renderer.compute(emitKernel().compute(n));
                writePtr = (writePtr + n) % maxParticles;
                totalEmitted += n;
                activeCount = Math.min(maxParticles, totalEmitted);
            }
            setKernelCounts(Math.max(1, activeCount));

            // 2) advance the sim.
            renderer.compute(clearGridKernel);
            renderer.compute(p2g1Kernel);
            renderer.compute(p2g2Kernel);
            renderer.compute(updateGridKernel);
            renderer.compute(g2pKernel);
        },

        positionNode() {
            return Fn(() => attribute('position').add(particleBuffer.element(instanceIndex).get('position')))();
        },

        // SMOOTH WATER SURFACE via GPU raymarch of the live MLS-MPM mass grid
        // (the density field the sim already maintains). No CPU readback, no
        // mesh extraction — a box-bounded fragment raymarch finds the
        // isosurface and shades it as real water: screen-space REFRACTION of
        // the rendered backdrop (viewportSharedTexture), Beer-Lambert depth
        // tint, environment REFLECTION, Fresnel blend, and a specular glint.
        //
        // Options:
        //   boxMin/boxMax  WORLD bounds the [0,1] domain maps to (must match
        //                  the scene's field→world mapping).
        //   iso            density threshold for the surface. Keep it ABOVE a
        //                  lone particle's deposit (~0.42) so stray splash
        //                  droplets don't render as a haze, and BELOW the
        //                  rest density so the packed pool reads solid. ~0.5
        //                  with restDensity 1.0 is a good start.
        //   steps          raymarch samples (more = crisper, slower).
        //   color          water tint; absorption eats its complement.
        //   absorbScale    Beer-Lambert tint speed (deeper = bluer/darker).
        //   refractScale   screen-space bend per unit depth; maxOffset clamps.
        //   envTexture     equirect HDRI for reflections (else a sky gradient).
        //   envIntensity / spec  reflection + specular strength.
        //   debug/debugScale  render peak density as grayscale to tune iso.
        surfaceMesh(o = {}) {
            const boxMin = new THREE.Vector3(...(o.boxMin ?? [0, 0, 0]));
            const boxMax = new THREE.Vector3(...(o.boxMax ?? [1, 1, 1]));
            const STEPS = o.steps ?? 96;
            const isoU = uniform(o.iso ?? 1.5);
            const wc = new THREE.Color(o.color ?? 0x6fc2ee);
            const bMin = uniform(boxMin.clone()), bMax = uniform(boxMax.clone());
            const gx1 = int(gridSize.x - 1), gy1 = int(gridSize.y - 1), gz1 = int(gridSize.z - 1);

            // --- water-material uniforms ---
            const refractScaleU = uniform(o.refractScale ?? 0.05);   // screen-space bend per unit depth
            const maxOffsetU = uniform(o.maxOffset ?? 0.09);         // clamp the bend (avoid smearing)
            const specU = uniform(o.spec ?? 0.5);
            const envIntU = uniform(o.envIntensity ?? 1.0);
            const absScale = o.absorbScale ?? 2.2;                   // Beer-Lambert tint speed
            // absorb the COMPLEMENT of the water color → keeps blue, eats red.
            const absorbU = uniform(new THREE.Vector3(
                (1 - wc.r) * absScale, (1 - wc.g) * absScale, (1 - wc.b) * absScale));
            // reflection: real HDRI if given, else a cheap sky gradient.
            const envSample = o.envTexture
                ? (dir) => texture(o.envTexture, equirectUV(dir)).rgb.mul(envIntU)
                : (dir) => mix(vec3(0.30, 0.34, 0.40), vec3(0.55, 0.68, 0.85),
                    clamp(dir.y.mul(0.5).add(0.5), 0.0, 1.0)).mul(envIntU);

            // Trilinearly interpolated density at a WORLD point. Nearest-cell
            // sampling at the coarse grid resolution looks like hard voxels;
            // trilinear gives the smooth blobby field a fluid surface needs.
            const GSX = float(gridSize.x), GSY = float(gridSize.y), GSZ = float(gridSize.z);
            const sampleD = (wp) => {
                const dp = wp.sub(bMin).div(bMax.sub(bMin));
                // cell-centered grid coords (cell i spans [i, i+1), center i+0.5)
                const gp = vec3(dp.x.mul(GSX), dp.y.mul(GSY), dp.z.mul(GSZ)).sub(0.5);
                const gi = floor(gp);
                const f = gp.sub(gi);
                const at = (ox, oy, oz) => {
                    const cx = max(int(0), min(gx1, int(gi.x).add(int(ox))));
                    const cy = max(int(0), min(gy1, int(gi.y).add(int(oy))));
                    const cz = max(int(0), min(gz1, int(gi.z).add(int(oz))));
                    return cellBufferFloat.element(cx.mul(GY_GZ).add(cy.mul(GZ)).add(cz)).w;
                };
                const x00 = mix(at(0, 0, 0), at(1, 0, 0), f.x);
                const x10 = mix(at(0, 1, 0), at(1, 1, 0), f.x);
                const x01 = mix(at(0, 0, 1), at(1, 0, 1), f.x);
                const x11 = mix(at(0, 1, 1), at(1, 1, 1), f.x);
                const y0 = mix(x00, x10, f.y);
                const y1 = mix(x01, x11, f.y);
                return mix(y0, y1, f.z);
            };

            const rm = Fn(() => {
                const ro = cameraPosition;
                const rd = normalize(positionWorld.sub(cameraPosition));
                const inv = vec3(1).div(rd);
                const ta = bMin.sub(ro).mul(inv);
                const tb = bMax.sub(ro).mul(inv);
                const tsm = min(ta, tb), tbg = max(ta, tb);
                const tEnter = max(max(tsm.x, tsm.y), tsm.z).max(0.0);
                const tExit = min(min(tbg.x, tbg.y), tbg.z);
                const dt = tExit.sub(tEnter).div(float(STEPS));
                const t = tEnter.add(dt.mul(0.5)).toVar();
                const found = float(0).toVar();
                const hp = vec3(0, 0, 0).toVar();
                const maxD = float(0).toVar();   // debug: peak density along the ray
                const thick = float(0).toVar();  // chord length through fluid (world units)
                Loop({ start: 0, end: STEPS, type: 'int' }, () => {
                    If(t.greaterThan(tExit), () => Break());
                    const wp = ro.add(rd.mul(t));
                    const dens = sampleD(wp).toVar();
                    maxD.assign(max(maxD, dens));
                    If(dens.greaterThan(isoU), () => {
                        If(found.lessThan(0.5), () => { found.assign(1.0); hp.assign(wp); });
                        thick.addAssign(dt);
                    });
                    t.addAssign(dt);
                });
                // debug: visualize the field magnitude so iso can be tuned
                // without CPU readback (which is broken on this backend).
                if (o.debug) return vec4(vec3(maxD.mul(o.debugScale ?? 1.0)), float(1.0));

                // surface normal from the density gradient at the entry point
                const cell = bMax.sub(bMin).div(vec3(gridSize.x, gridSize.y, gridSize.z));
                const nx = sampleD(hp.add(vec3(cell.x, 0, 0))).sub(sampleD(hp.sub(vec3(cell.x, 0, 0))));
                const ny = sampleD(hp.add(vec3(0, cell.y, 0))).sub(sampleD(hp.sub(vec3(0, cell.y, 0))));
                const nz = sampleD(hp.add(vec3(0, 0, cell.z))).sub(sampleD(hp.sub(vec3(0, 0, cell.z))));
                const n = normalize(vec3(nx, ny, nz).negate()).toVar();

                // REFRACTION (screen-space): bend the already-rendered backdrop
                // by the surface normal; deeper water bends more.
                const bend = clamp(thick.mul(refractScaleU), 0.0, maxOffsetU);
                const refrUV = screenUV.add(n.xy.mul(vec2(1, -1)).mul(bend));
                const bg = viewportSharedTexture(refrUV).rgb;
                // ABSORPTION (Beer-Lambert): water tints + darkens with depth.
                const trans = exp(absorbU.mul(thick).negate());
                const refracted = bg.mul(trans);
                // REFLECTION: environment along the reflected ray.
                const refl = envSample(reflect(rd, n));
                // FRESNEL: see-through at center, mirror at grazing angles.
                const fres = float(0.02).add(float(0.98).mul(pow(float(1).sub(max(dot(n, rd.negate()), 0.0)), 5.0)));
                // SPECULAR glint.
                const L = normalize(vec3(0.4, 0.9, 0.3));
                const spec = pow(max(dot(n, normalize(L.sub(rd))), 0.0), 120.0).mul(specU);
                const body = mix(refracted, refl, fres).add(spec);
                return vec4(body, found);
            })();

            const mat = new THREE.MeshBasicNodeMaterial({ transparent: true, side: THREE.BackSide, depthWrite: false });
            mat.colorNode = rm.xyz;
            mat.opacityNode = rm.w;
            const geo = new THREE.BoxGeometry(boxMax.x - boxMin.x, boxMax.y - boxMin.y, boxMax.z - boxMin.z);
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set((boxMin.x + boxMax.x) / 2, (boxMin.y + boxMax.y) / 2, (boxMin.z + boxMax.z) / 2);
            mesh.frustumCulled = false;
            mesh.renderOrder = 10;
            // This proxy is a RAYMARCH SAMPLING SHELL — its position IS the
            // domain mapping. If the placement audits relocate it (it always
            // overlaps the vessel + the fluid), the raymarch samples the wrong
            // place: the pool vanishes and the stream cuts off at a levitating
            // box edge. Fully exempt it from every auto-fix system.
            mesh.userData.noClippingCheck = true;
            mesh.userData.noSupportCheck = true;
            mesh.userData.allowIntersect = true;
            return mesh;
        },
        async readPositions() {
            // Reuse ONE persistent ReadbackBuffer. Passing target=null makes
            // three.js create + destroy a temp readback GPUBuffer every call;
            // on the wgpu-rs/Deno backend that per-frame churn starts
            // returning all-zeros after ~37 frames. A persistent target keeps
            // a single readback buffer alive (created once), so it stays live.
            if (!_readback) _readback = new THREE.ReadbackBuffer(maxParticles * STRIDE * 4);
            await renderer.getArrayBufferAsync(particleBuffer.value, _readback);
            const f = new Float32Array(_readback.buffer);
            const n = activeCount;
            const out = new Float32Array(n * 3);
            for (let i = 0; i < n; i++) { out[i*3] = f[i*STRIDE]; out[i*3+1] = f[i*STRIDE+1]; out[i*3+2] = f[i*STRIDE+2]; }
            _readback.release();   // unmap so the buffer can be reused next frame
            return out;
        },
        set gravity(v) { gravityUniform.value.set(v[0], v[1], v[2]); },
        _internals: { gridSize, STRIDE, maxParticles },
    };
}
