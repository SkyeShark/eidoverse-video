# Volumetric fire and smoke simulation

[Main instructions](../AGENTS.md)

`fluid_grid.js` provides a GPU volume simulation with a burning mesh emitter
and a dedicated compositor. It uses the included `tsl_curl_noise.js` support
library. It is dynamically imported, not an injected `makeParticles` preset.

```js
globalThis._noAutoEnhance = true; // this scene uses the fire compositor
const {createVolumeFire, createFireCompose} =
  await import(EIDOVERSE_DIR + 'fluid_grid.js');
const fire = await createVolumeFire(_r, {mesh: burningMesh, emitterPoints: 4096});
_s.add(fire.volumeMesh, fire.shadowMesh);
const compose = createFireCompose(_r, _s, _c, fire, [keyLight]);
await fire.warmup(4);
// In renderFrame(t):
// await fire.step(dt);
// await compose.renderAsync();
```

Supply the actual mesh that burns. With `emitterPoints:null`, emission samples
its raw vertices; a count uses area-weighted surface samples, which are more
appropriate for low-poly meshes with uneven vertex density. Build/sample once.

Scale and placement: the simulation box defaults to the source example's
12 × 12 × 24 m (`worldSize`), centred on the origin and starting 0.4 m above it.
The example burns a teapot about 1 m across (`emitterRadius` 1, `flameHeight`
3.5). Put the burning mesh inside the box at that kind of scale: a small mesh, or
one below the box's floor, emits little or nothing and reads as a faint glow.

The returned object exposes `volumeMesh`, `shadowMesh`, `pointLight`,
`volumetricMaterial`, `params`, `uniforms`, `simTime`, `step`, `warmup`,
`makeLavaEmissive` and `dispose`. The module attaches the fire light to the
emitter. Use its bounded controls for buoyancy, turbulence, cooling, smoke
lifespan, wind and color; preserve the solver's dispatch and texture ordering.

`createFireCompose` owns the volume pass, denoise, color/composite and bloom
sequence. Call its `renderAsync()` for the frame instead of adding a second
final scene render over it. Its `post`, `bloomPass` and `denoiseStrength` expose
compositor controls. Test integration explicitly if combining another post stack.

The simulation is stateful: seeking backward requires restarting/replaying it.
Warm it up before judging the flame. Remove the returned meshes and dispose the
simulation/compositor resources at the end. Use `makeParticles`
for inexpensive sprite sparks or `createSdfVolume` for authored raymarched
effects that do not need this fluid simulation (both in [AGENTS.md](../AGENTS.md)).
