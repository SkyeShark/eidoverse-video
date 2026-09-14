# Three-dimensional free-surface water

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Use `fluid_water.js` for water with a three-dimensional level-set surface,
gravity, solid boundaries, emitters and moving sphere colliders. For terrain
ponds, rivers and erosion, [liquids.md](liquids.md) describes the cheaper
shallow-water solver. These are different simulation APIs.

```js
const {createWaterSim} = await import(EIDOVERSE_DIR + 'fluid_water.js');
const water = await createWaterSim(_r, {
  gridSize: [64, 48, 64], worldSize: [2, 1.5, 2],
  domainCenter: [0, 0.75, 0], initialLevel: 0.4,
  maxSpheres: 8, maxEmitters: 1
});
_s.add(water.surfaceMesh);
await water.warmup(0.5);
// In renderFrame: update collider/emitter controls, then await water.step(dt).
```

`gridSize` and `worldSize` must produce cubic cells on all three axes. The
defaults above describe a 2 × 1.5 × 2 metre domain. `domainCenter` locates that
domain; do not additionally translate the surface mesh to move the simulation.
`initialLevel` is depth above the domain floor. Leaving it `null` selects the
dam-break column controlled by `columnWidth`, `columnHeight` and `columnDepth`.

- `walls:true` adds analytic tank boundaries. Use `walls:false` with
  `colliderMeshes` for a supplied environment; these meshes are sampled at setup.
- Reserve `maxSpheres` and call `setSpheres([{x,y,z,r}, ...])` for moving bodies.
  Reserve `maxEmitters` and call `setEmitters([{x,y,z,r,vx,vy,vz}, ...])` for
  incoming liquid. Positions, radii and velocities are world metres/metres per
  second. Entries beyond the reserved capacity are ignored; empty lists disable
  the slots. Update world transforms before sampling animated bones.
- Call `await step(dt)` once per frame; `warmup(seconds)` advances the simulation
  before the shot. `reset()` restores its initial state. This solver advances
  incrementally; seeking a film backward needs a reset and replay.
- `params` and `uniforms` expose state/settings. Colors, absorption,
  surfaceOpacity, foam and optional emissive controls determine appearance.
  Use `insideDomain:true` when the camera is inside its bounds.
- `measureVolume:true` enables `await measureVolume()` diagnostics. The solver
  has volume-control corrections; active emitters temporarily disable that
  correction so it does not fight incoming water. Check volume and motion when
  changing grid/pressure settings. Reinitialization is currently disabled by
  default because the implemented central-difference version is unstable.
- `dispose()` releases simulation resources; remove scene meshes when finished.

This implementation uses a uniform grid with documented numerical limitations.
Verify the actual pour, contact and settled surface; do not describe a new scene
as a validated physical experiment merely because it renders.
