// water_compute.js
//
// Height-field water surface using WebGPU compute shaders. Ports the
// three.js webgpu_compute_water example into a reusable module so any
// scene can drop in a real-time wave simulation — ripples, splashes,
// pour-impact patterns, mouse trails on a pool surface.
//
// Use this for: puddles, lakes, ponds, pools, basins, fountains,
// rain-impacted surfaces. NOT for full 3D liquid bodies (jugs spilling
// volumetric water, splashing droplets); that's particle territory —
// use three.quarks emitters and combine with disturb() at the impact
// point for the visible splash ring.
//
// For ocean / large-scale water with FFT waves, use the WaterMesh +
// SkyMesh combo from three/addons (see AGENTS.md). water_compute is
// better when you need INTERACTIVE response (something falling in,
// something pouring onto the surface) rather than a passive ocean.
//
// Agent API
// ---------
//
//   import { createWaterCompute } from globalThis.EIDOVERSE_DIR + 'water_compute.js';
//
//   const water = await createWaterCompute(renderer, {
//       width: 128,          // grid resolution (powers of 2; 64–256 typical)
//       bounds: 20,          // world-space side length of the surface mesh
//       segments: 128,       // mesh subdivision; usually equals width
//       viscosity: 0.98,     // wave damping; < 1, lower = waves die faster
//       color: 0x335577,
//       roughness: 0.1,
//       metalness: 0.4,
//       envMap: scene.environment,  // optional, for IBL reflections
//   });
//
//   scene.add(water.mesh);
//
//   // Each frame:
//   water.step();                                // advance the sim
//
//   // Drop a ripple anywhere — PLANE-LOCAL coords (the surface is built
//   // around its own origin, ±bounds/2). If you moved water.mesh, pass
//   // offsets relative to the mesh — world coords silently miss the grid:
//   water.disturb(localX, localZ, radius, amplitude);
//
//   // For pouring water: emit particles from a source, and every frame
//   // call disturb() at the contact point with amplitude ~= particle
//   // mass to make the surface react.
//
// Implementation notes
// --------------------
// - Ping-pong height buffers (A/B) + a previous-height buffer give the
//   classic wave-equation update: avg(neighbors) − prev, damped by
//   viscosity.
// - Disturbance is a uniform-driven cosine falloff (matching the
//   example's mouse path) but rebound as a generic `disturb()` API.
// - Normals come from finite differences on the height field, computed
//   in the vertex shader so the surface looks like real ripples.

import {
    Fn, instancedArray, instanceIndex, vertexIndex, globalId,
    select, uniform, uv, vec2, vec3, float, uint, clamp, floor, cos, length,
    smoothstep, transformNormalToView, positionLocal,
} from 'npm:three@0.184.0/tsl';

export async function createWaterCompute(renderer, opts = {}) {
    (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('water_compute');
    const WIDTH    = opts.width     ?? 128;
    const BOUNDS   = opts.bounds    ?? 20;
    const segments = opts.segments  ?? WIDTH;
    const viscosityVal = opts.viscosity ?? 0.98;
    // Hard clamp on wave height. Sustained disturbance at one point
    // (e.g. a continuous pour) otherwise pumps energy in faster than
    // viscosity removes it and the height field runs away into a spike.
    const maxHeight = opts.maxHeight ?? (BOUNDS * 0.12);

    // Initial height field with light Perlin-ish jitter so the surface
    // isn't a dead-flat mirror on frame 0.
    const initial     = new Float32Array(WIDTH * WIDTH);
    const initialPrev = new Float32Array(WIDTH * WIDTH);
    for (let i = 0; i < WIDTH * WIDTH; i++) {
        initial[i]     = (Math.random() - 0.5) * 0.001;
        initialPrev[i] = initial[i];
    }
    const heightA  = instancedArray(initial).setName('WaterHeightA');
    const heightB  = instancedArray(new Float32Array(initial)).setName('WaterHeightB');
    const prevH    = instancedArray(initialPrev).setName('WaterPrevHeight');

    // Disturbance uniforms (driven by water.disturb() from JS).
    const disturbPos    = uniform(vec2(0, 0));
    const disturbRadius = uniform(float(0));
    const disturbAmp    = uniform(float(0));
    const viscosity     = uniform(float(viscosityVal));

    // readFromA toggles each step. We use a JS-side bool, swapping the
    // compute kernel input. Two separate Fn() compiles (AtoB, BtoA).
    let readFromA = 1;
    const center = vec2(0.5, 0.5);

    const getNeighbors = (idx, buf) => {
        const w = uint(WIDTH);
        const ix = idx.mod(w);
        const iz = idx.div(w);
        const N  = clamp(iz.sub(uint(1)), uint(0), w.sub(uint(1))).mul(w).add(ix);
        const S  = clamp(iz.add(uint(1)), uint(0), w.sub(uint(1))).mul(w).add(ix);
        const W_ = iz.mul(w).add(clamp(ix.sub(uint(1)), uint(0), w.sub(uint(1))));
        const E  = iz.mul(w).add(clamp(ix.add(uint(1)), uint(0), w.sub(uint(1))));
        return {
            north: buf.element(N),
            south: buf.element(S),
            east:  buf.element(E),
            west:  buf.element(W_),
            northIdx: N, southIdx: S, eastIdx: E, westIdx: W_,
        };
    };

    const makeKernel = (readBuf, writeBuf) => Fn(() => {
        const h    = readBuf.element(instanceIndex).toVar();
        const pH   = prevH.element(instanceIndex).toVar();
        const { north, south, east, west } = getNeighbors(instanceIndex, readBuf);

        const sum = north.add(south).add(east).add(west);
        sum.mulAssign(0.5);
        sum.subAssign(pH);
        const newH = sum.mul(viscosity);

        // Disturbance via cosine falloff. Derive this cell's world-space
        // position on the surface from its grid index, then ripple based
        // on distance to the disturb point.
        const ixu = instanceIndex.mod(uint(WIDTH));
        const izu = instanceIndex.div(uint(WIDTH));
        const u = float(ixu).mul(1 / WIDTH);
        const v = float(izu).mul(1 / WIDTH);
        const worldPos = vec2(u, v).sub(center).mul(BOUNDS);
        const dist = length(worldPos.sub(disturbPos));
        const phase = clamp(dist.mul(Math.PI).div(disturbRadius.add(1e-4)), 0.0, Math.PI);
        newH.addAssign(cos(phase).add(1.0).mul(disturbAmp).mul(0.5));
        newH.assign(clamp(newH, float(-maxHeight), float(maxHeight)));

        prevH.element(instanceIndex).assign(h);
        writeBuf.element(instanceIndex).assign(newH);
    })().compute(WIDTH * WIDTH, [16, 16]);

    const kernelAtoB = makeKernel(heightA, heightB);
    const kernelBtoA = makeKernel(heightB, heightA);

    // Material — displace vertices by current height, derive normals.
    // Use the global THREE (the WebGPU build the engine set up) — the base
    // npm:three build has no *NodeMaterial constructors.
    const THREE = globalThis.THREE;

    const mat = new THREE.MeshStandardNodeMaterial({
        color: opts.color ?? 0x335577,
        roughness: opts.roughness ?? 0.1,
        metalness: opts.metalness ?? 0.4,
        envMap: opts.envMap ?? null,
        transparent: true,
        opacity: opts.opacity ?? 0.92,
    });

    // Which buffer holds the freshest data is decided at RUNTIME (it
    // ping-pongs), but a TSL node graph is compiled ONCE. So the choice
    // must be a uniform the graph reads each frame, not a captured JS var.
    const readState = uniform(float(1));  // 1 → heightA fresh, 0 → heightB fresh
    const currentHeight = (idx) =>
        select(readState.greaterThan(0.5), heightA.element(idx), heightB.element(idx));

    const dispScale = opts.displaceScale ?? 1.0;

    // Geometry stays in its native XY plane (normal +Z); we rotate the
    // MESH to lay it flat. Displacing positionLocal.z then pushes along
    // the local normal, which becomes world-up after the mesh rotation.
    mat.positionNode = Fn(() => {
        let h = currentHeight(vertexIndex).mul(dispScale);
        if (opts.circular) {
            // waves fade to zero at the disc rim — displaced square corners
            // otherwise poke past a round container's wall
            const d = uv().sub(vec2(0.5, 0.5)).length();
            h = h.mul(smoothstep(float(0.5), float(0.44), d));
        }
        return vec3(positionLocal.x, positionLocal.y, positionLocal.z.add(h));
    })();

    mat.normalNode = Fn(() => {
        const { northIdx, southIdx, eastIdx, westIdx } = getNeighbors(vertexIndex, heightA);
        const nx = currentHeight(westIdx).sub(currentHeight(eastIdx)).mul(WIDTH / BOUNDS);
        const ny = currentHeight(southIdx).sub(currentHeight(northIdx)).mul(WIDTH / BOUNDS);
        return transformNormalToView(vec3(nx.negate(), ny.negate(), 1.0)).toVertexStage();
    })();

    // Circular clip: keep the square compute grid (vertexIndex mapping
    // intact) but mask the visible surface to a disc via alpha. Use for
    // round containers — cups, basins, fountain bowls, barrels.
    if (opts.circular) {
        const d = uv().sub(vec2(0.5, 0.5)).length();
        mat.opacityNode = select(d.lessThan(0.5), float(opts.opacity ?? 0.92), float(0));
        // hard-DISCARD outside the disc: zero-opacity fragments still tint /
        // interact with post passes and read as a faint square footprint
        mat.alphaTestNode = float(0.05);
        mat.transparent = true;
        mat.depthWrite = false;
    }

    const geo = new THREE.PlaneGeometry(BOUNDS, BOUNDS, segments - 1, segments - 1);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.receiveShadow = true;

    let freshIsA = true;  // initial heights live in heightA
    return {
        mesh,
        step() {
            // freshIsA → read A, write B (kernelAtoB); fresh becomes B.
            renderer.compute(freshIsA ? kernelAtoB : kernelBtoA);
            freshIsA = !freshIsA;
            readState.value = freshIsA ? 1 : 0;
            // Disturbance amp fades after one step so single calls produce
            // single-frame impulses (use repeated calls for sustained input).
            disturbAmp.value = 0;
        },
        disturb(worldX, worldZ, radius, amplitude) {
            disturbPos.value.set(worldX, worldZ);
            disturbRadius.value = radius;
            disturbAmp.value    = amplitude;
        },
        set viscosity(v) { viscosity.value = v; },
        _internals: { heightA, heightB, prevH },
    };
}
