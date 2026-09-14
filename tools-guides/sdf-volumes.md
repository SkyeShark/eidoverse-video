# SDF surfaces, volumetric effects and isosurfaces

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

**`sdf_raymarch_loader`** — raymarched 3D objects PLACED in the scene (at a
position, occluding/occluded by other geometry — unlike the screenspace
nuke). Everything goes through `globalThis.SdfRaymarchLoader`; call
`SdfRaymarchLoader.help()` for the full API reference.

```js
const SDF = globalThis.SdfRaymarchLoader;
SDF.registerSdfHelper(renderer, scene);          // once, in setup()

// start from an EXAMPLES entry — every entry has .make(opts):
const car = SDF.EXAMPLES.stylizedCyberpunkSedan.make();
car.position.set(2, 0, -1);                      // position like any Object3D
const fire = SDF.EXAMPLES.explosion.make({ speed: 1.4 });   // live-knob overrides

// or write your own — map/shade are JS FUNCTIONS returning TSL nodes
// (contract + full primitive list: the "TSL SDF ENGINE" header comment in
// sdf_raymarch_loader.js; SDF.SDF_TSL carries sdSphere/sdBox/…, smin/opU/…,
// vnoise/fbm and the TSL builders):
const T = SDF.SDF_TSL;
const blob = SDF.createSdfObject({
    map(p) { return { dist: T.sdSphere(p, T.float(0.5)), mat: T.float(1.0) }; },
    shade(p, n, mat, ctx) {          // -> vec3 node; ctx = { softShadow, calcNormal, ro, rd }
        return T.vec3(0.8, 0.5, 0.3).mul(T.max(T.float(0.0), T.dot(n, T.normalize(T.vec3(0.5, 0.9, 0.4)))));
    },
    bounds: { min: [-1, -1, -1], max: [1, 1, 1] },
});

// participating media (smoke / fire / explosions) = createSdfVolume:
// sample(p) -> { color, alpha, step } density accumulation, not hit+shade
const plume = SDF.EXAMPLES.smoke.make({ density: 1.3 });
```

EXAMPLES catalog — surface: `basicSphere`, `stylizedBlob`, `detailedCoat`,
`fractalCore` (mandelbulb), `explosion` (pyroclastic fireball), the four
vehicles (`stylizedModernSedan`, `stylizedCyberpunkSedan`,
`stylizedSciFiSleekCar`, `stylizedFighterJet`); volumetric:
`explosionRing` (expanding smoke-ring detonation), `flame` (torch fire),
`smoke` (rising plume). Every entry is a working reference for its
technique — take the wiring, replace the content. A localized
fireball/explosion at a point in the scene belongs here (not the
screenspace nuke). Volumes are transparent; keep the camera outside their
bounds box.

## Writable scalar fields

**`makeIsoField(opts)`** — GPU-raymarched isosurface over a CPU-written voxel
field: the fast path for ANY MarchingCubes-style effect (fields at 160³ render
realtime; three's MarchingCubes.update() per frame is the ~1fps trap). Same
field layout (`x + y*res + z*res²`); write `iso.field[iso.idx(x,y,z)]`, call
`iso.upload()` after a batch. Shading is REAL scene lighting — the raymarch
gradient normal feeds MeshStandardNodeMaterial via normalNode, and the
fragment writes true hit-point depth (correct occlusion both ways). `{
resolution, half, iso, color, metalness, roughness, steps, colorNode /
roughnessNode / emissive: (hitPoint, normal) => node (hit-point space — never
positionWorld, that's the proxy box), parent }`. If the parent MOVES, call
`iso.bind()` each frame to refresh the world bounds (when its parent moves). Debug: `flat: true` or `shade: 'normals'`. Raymarched pixels can't
cast shadows — pair with a colorWrite:false proxy box (when the effect needs one). NOTE: TSL
`mix()` with all-JS-number args emits INVALID WGSL silently (mesh skipped, no
error) — blend JS constants in JS.

Both helpers are injected by the renderer. Construct fields in `setup()`, then
update controls/bounds as needed. Avoid rebuilding a dense CPU field every frame.
For simulated fire read [volume-fire.md](volume-fire.md); for moving water read
[liquids.md](liquids.md) or [free-surface-water.md](free-surface-water.md).
