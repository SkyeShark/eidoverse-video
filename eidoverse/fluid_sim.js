// fluid_sim.js
//
// 2D screen-space stable-fluids simulation, wrapping three-fluid-fx's
// WebGPU/TSL pipeline. Use this for ink, dye, smoke, swirling color
// trails behind a moving subject, glitch-like distortion of an
// underlying texture, abstract motion graphics.
//
// This is NOT 3D water — see water_compute.js for height-field surface
// water, or WaterMesh from three/addons for ocean-style surfaces.
//
// Agent API
// ---------
//
//   const fluid = await (await import(globalThis.EIDOVERSE_DIR + 'fluid_sim.js'))
//       .createFluidSim(renderer, {
//           profile: 'balanced',         // 'performance' | 'balanced' | 'quality'
//           curlStrength: 30,
//           densityDissipation: 0.97,
//           velocityDissipation: 0.98,
//           splatRadius: 0.0025,
//           splatForce: 6000,
//       });
//
//   // Each frame:
//   fluid.step(deltaSeconds);
//
//   // Inject motion + color (uv in [0,1], dx/dy = velocity, color = [r,g,b] 0..1):
//   fluid.splat(uvX, uvY, dx, dy, [r, g, b]);
//
//   // Display: the splat color tints DENSITY — use densityNode as the
//   // material color. (dyeNode is empty unless dye is enabled upstream.)
//   const plane = new THREE.Mesh(
//       new THREE.PlaneGeometry(W, H),
//       new THREE.MeshBasicNodeMaterial({ colorNode: fluid.densityNode }),
//   );
//
//   // Or distort an underlying scene texture by the fluid:
//   //   material.colorNode = fluid.distortion(someSceneTextureNode, 1.0);
//   // Or composite a built-in style over a background:
//   //   material.colorNode = fluid.overlayNode(color(0,0,0), { style: 'smoke' });

export async function createFluidSim(renderer, opts = {}) {
    (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('fluid_sim');
    const fx = await import('npm:three-fluid-fx@0.1.0/tsl');
    const { FluidSimulation } = fx;

    // Defaults track the library's own defaults (splatForce 6, curlStrength
    // 0.55, etc). Earlier over-large values (splatForce 6000, curl 30) blew
    // the velocity field up to NaN → black output. Only override knowingly.
    const sim = new FluidSimulation(renderer, {
        profile: opts.profile ?? 'balanced',
        enableDye: opts.enableDye ?? true,            // dye OFF upstream — we want color
        enableVorticity: opts.enableVorticity ?? true, // crisper swirls
        ...(opts.curlStrength        != null ? { curlStrength: opts.curlStrength } : {}),
        ...(opts.densityDissipation  != null ? { densityDissipation: opts.densityDissipation } : {}),
        ...(opts.velocityDissipation != null ? { velocityDissipation: opts.velocityDissipation } : {}),
        ...(opts.dyeDissipation      != null ? { dyeDissipation: opts.dyeDissipation } : {}),
        ...(opts.splatRadius         != null ? { splatRadius: opts.splatRadius } : {}),
        ...(opts.splatForce          != null ? { splatForce: opts.splatForce } : {}),
        ...(opts.bfecc               != null ? { bfecc: opts.bfecc } : {}),
        ...(opts.reflectWalls        != null ? { reflectWalls: opts.reflectWalls } : {}),
    });

    return {
        step(dt) { sim.step(dt ?? 1 / 60); },
        splat(x, y, dx, dy, color) {
            // The splat `color` tints DENSITY (always written). dyeColor
            // only matters if dye is enabled (it isn't by default upstream),
            // so densityNode is the field to display.
            sim.addSplat(x, y, dx, dy, { color, dyeColor: color });
        },
        resize(w, h) { sim.resize?.(w, h); },
        // SAMPLEABLE TextureNodes — use these as material colorNode / map,
        // or feed them to the distortion/overlay factories. (The `*Texture`
        // getters on the raw sim return internal storage `.read` nodes that
        // do NOT sample correctly outside the fluid's own pipeline — these
        // `*Node`s are the public, sampleable ones.)
        get densityNode()  { return sim.densityNode; },   // colored ink — the main display
        get velocityNode() { return sim.velocityNode; },  // 2D velocity field
        get dyeNode()      { return sim.dyeNode; },        // only meaningful if dye enabled
        // Composite the fluid over `sceneNode` (a background colorNode or
        // your scene as a texture) via a built-in style.
        // style: 'colorful' | 'smoke' | 'oil' | 'rainbowInk' | 'fluid' | ...
        overlayNode(sceneNode, opts = {}) {
            const style = opts.style ?? 'colorful';
            const fn = fx[`${style}Overlay`] ?? fx.colorfulOverlay;
            return fn(sceneNode, sim.densityNode, sim.dyeNode, sim.velocityNode, opts);
        },
        // Distortion factory (warps a scene texture by the fluid velocity):
        // material.colorNode = fluid.distortion(sceneTextureNode, strength)
        distortion(sceneNode, strength = 1) {
            return fx.simpleDistortion(sceneNode, sim.densityNode, strength);
        },
        overlays: fx,
        _raw: sim,
    };
}
