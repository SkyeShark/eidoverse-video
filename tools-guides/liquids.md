# Shallow water, pours and 2D fluids

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

Choose the water representation by its motion and spatial needs. `fluid_swe`
models a shallow-water heightfield over `bedFn(x,z) → y`, with coupled pours,
droplets, foam and sphere interactions. Use [3D free-surface water](free-surface-water.md)
when the surface must fold over or flow around volumetric moving colliders.
A flat reflective water shader is useful for a distant surface without those
interactions; the 2D dye solver is for panels and fields of swirling color.

Scene scripts are evaluated, so use dynamic `await import(...)` inside
`setup()`. `fluid_swe` tracks liquid exchange between its field, pours and
spray, but inspect behavior at boundaries and the chosen grid/time step;
conservation intent is not a guarantee of exact volume in every configuration.

```js
const { createWaterSWE } = await import(globalThis.EIDOVERSE_DIR + 'fluid_swe.js');
const swe = await createWaterSWE(renderer, {
    worldSize: [16, 16], gridSize: [256, 256], domainCenter: [0, 0, 0],
    bedFn: (x, z) => groundY(x, z),          // the terrain IS the bed
    sprayMax: 6144,                          // whitewater budget (0 = off)
    envTex: skyEnvCopy,                      // see envTex note below
});
await swe.init();
scene.add(swe.surfaceMesh);
if (swe.sprayMesh) scene.add(swe.sprayMesh);
if (swe.streamMesh) scene.add(swe.streamMesh);
// per frame:
swe.setPours([{ x, y, z, vx, vy, vz, rate }]);   // rate in m³/s — mouths ON
                                                 // the visible geometry's lip
swe.setSpheres([{ x, y, z, r, vx, vy, vz }]);    // vy matters: entry splash
await swe.step(dt); swe.syncRenderPhase();
```
**Liquid presets** — exported as `LIQUID_PRESETS`; one word selects a whole material behaviour
(`preset: 'water' | 'gel' | 'goo' | 'lava' | 'mud'`, any option still
overrides). Presets drive sim feel AND look: `yieldSlope` (Bingham yield —
gel HOLDS mounds instead of levelling), `waveScale` (gloopy slow response),
`specPow`/`specGain` (highlight tightness), `sprayStretch` (needles vs
blobs), `streamAeration` (water whitens as it falls; honey/gel stays a
glassy filament), `dropletVisibility`, `foamGain` (gel barely froths).
```js
const gel = await createWaterSWE(renderer, { preset: 'gel',
    deepColor: '#6e2603', shallowColor: '#ff7d1f' });  // Portal-gel
```
**Pour styles** — `setPours([{ ..., style: 'seep', seepWidth: 0.8 }])`:
'jet' (default) renders the ballistic stream tube + droplet breakup;
'seep' is a slow dribbling curtain at the mouth (a rock spring, a weeping
wall — a seep must NOT render a jet parabola). Mass ledger identical.

**HYDRAULIC EROSION + RAIN — the bed can be ALIVE.** Pass `erosion: {}` and
the terrain under the water becomes dynamic: fast flow picks the bed up as
suspended sediment (the water visibly muddies), carries it downstream, and
lays it down where the current slackens — rills capture into a braided
wash, the wash incises, cut banks cave to the angle of repose, a silt fan
builds at the outlet. Pair it with `rainRate` (distributed rainfall over
the whole domain, m/s of depth; 4.5e-5 ≈ a violent cloudburst; animated
squall bands via `rainPatchiness`) — rain is THE natural source for wash
formation; a lone jet pour reads as a garden hose. `swe.setRain(v)` ramps
the storm live (build with `rainRate > 0` so the kernel path exists), and
the weather system's falling rain is the matching LOOK — this term is
where its water lands.
```js
const swe = await createWaterSWE(renderer, {
    worldSize: [17, 17], gridSize: [256, 256], bedFn: groundY,
    rainRate: 4.6e-5, rainPatchiness: 0.6,
    erosion: {
        capacity: 0.30, erode: 0.32, deposit: 0.42, bank: 1.2,
        talusSlope: 0.5,        // wet-sand repose ≈ 29° — banks slump WIDE
        talusRate: 3.0, maxDelta: 0.35,
        terrainMaps: { albedo: soilAlbedo, rough: soilRough, normal: soilNor },
        terrainTexPeriod: 120 / 26, // static ground's (size / repeat), metres per
                                // tile: WORLD-locks the patch uvs so the maps
                                // continue the surrounding pattern at the same
                                // fract phase. ⚠ Pass ALL THREE maps — albedo
                                // alone leaves the patch glass-smooth beside a
                                // normal-mapped world (the pebble relief IS the
                                // normal map) and the material difference
                                // prints the domain as a square even when the
                                // heights meet flush. (`terrainRepeat` remains
                                // for patch-local uvs, but phase-locked world
                                // uvs are why the rim can't print.)
    },
});
scene.add(swe.terrainMesh);     // the eroding ground patch — lay it over the
                                // static terrain (same bedFn). ⚠ The static
                                // mesh must DROP WELL AWAY (~1.5 m, feathered)
                                // under the patch interior — sunk only a few
                                // cm it fills every deeper cut from inside:
                                // cuts vanish, deposits still rise, and the
                                // piece reads as ground GROWING around the
                                // water (and the water sinks out of sight
                                // with its channel). Meet the patch flush
                                // only at the feathered rim.
// per frame: swe.setRain(stormRamp);   // 0 → rainRate → 0 across the piece
```
Scene craft for a wash that READS: shape the domain as a broad valley
(damp your dune noise inside it, add a gentle cross-fall) — a raw dune
field breaks rain into scattered pools and no channel ever organizes.
Widening vs slot-cutting is the tuning axis: `bank` (lateral pickup) +
low `talusSlope` + small `maxDelta` give flood-broad washes; raise
`maxDelta`/`talusSlope` and drop `bank` for a young slot gully. The water
muddies by suspended load automatically; the patch tints cut banks with
`cutColor` and fresh deposits with `siltColor`.

Key options: `initLevel` pre-fills to a waterline (standing ponds — but a
scene whose POINT is the fill must start dry); `foamDecay` tightens/loosens
churn patches; palette (`deepColor`/`shallowColor`/`absorption`) + `foamColor`.
`envTex` (optional) makes the fresnel reflect a real sky: pass a PLAIN
equirect texture — if your sky lives in a RenderTarget (e.g. a bake),
copy it once via `readRenderTargetPixelsAsync` into a half-float
`DataTexture` (flip rows). ⚠ never bind a live RenderTarget texture into
the water materials: on this stack that intermittently drops whole draws
silently. Without `envTex`, the constant `skyColor` washes out grazing
angles on large flat water.
Scene craft: give runup a TALL containment — water that slops over a low
rim pools on the outer apron as floating-looking slabs. A character wading
needs a LOCAL shaped collider strip sampled from the bed: the whole
terrain's AABB sends the controller climbing, and a flat proxy reads as
walking ON the water.
What it cannot do: overhangs, curling breakers, submerged interiors — a
heightfield stores one surface height per column.

**Pours / streams into CONTAINERS** — shape the `bedFn` as the vessel's
interior: a bowl, cup, barrel, or basin is a heightfield. Share one
profile function between the visible vessel mesh (a lathe of it) and the
sim's `bedFn`, and the container the liquid fills IS the prop's interior —
the pour lands on a rippling, rising level and conserves mass to the
brim. Same primitives compose into fountains, rain into a barrel, a
waterfall pool — point them where the scene needs.

**`WaterMesh` + `SkyMesh`** — Three.js's flat reflective water effect and
sky. `WaterMesh` uses scrolling normal-map samples and planar reflection;
it is not an FFT ocean simulation and does not displace a physical wave mesh.
The pinned constructor needs an options object and a normal texture:

```js
const { WaterMesh } = await import('npm:three@0.184.0/addons/objects/WaterMesh.js');
const { SkyMesh } = await import('npm:three@0.184.0/addons/objects/SkyMesh.js');
const waterNormals = await loadImageTexture(ASSETS.water_normal);
waterNormals.wrapS = waterNormals.wrapT = THREE.RepeatWrapping;
const sky = new SkyMesh(); sky.scale.setScalar(10000); scene.add(sky);
const water = new WaterMesh(new THREE.PlaneGeometry(10000, 10000), {
  waterNormals, sunDirection: new THREE.Vector3(0.5, 0.8, 0.2).normalize(),
  sunColor: 0xffffff, waterColor: 0x285f66, distortionScale: 3.7,
});
water.rotation.x = -Math.PI / 2; scene.add(water);
```

Declare a suitable tiling normal map as `water_normal`. Tune sky/sun uniforms
together and inspect the reflection in the native render.

**`fluid_sim`** — 2D stable-fluids (ink, dye, smoke, swirling color).
It does not represent a 3D liquid surface; use the water systems above for that.
```js
const { createFluidSim } = await import(globalThis.EIDOVERSE_DIR + 'fluid_sim.js');
const fluid = await createFluidSim(renderer, { profile: 'balanced', curlStrength: 4 });
// Display: the splat COLOR tints density — use densityNode as the color.
const plane = new THREE.Mesh(
    new THREE.PlaneGeometry(W, H),
    new THREE.MeshBasicNodeMaterial({ colorNode: fluid.densityNode }),
);
scene.add(plane);
// per frame, BEFORE step: inject motion+color. dx/dy are velocity — big
// values MOVE the fluid (swirls); near-zero just deposits a static blob.
//   fluid.splat(uvX, uvY, dx, dy, [r,g,b]);   // uv in [0,1]
//   fluid.step(1/30);
// Or distort a scene texture: material.colorNode = fluid.distortion(sceneTex, 1);
```

For 3D free-surface water with moving colliders, use
[free-surface-water.md](free-surface-water.md). `fluid_3d.js` and
`water_compute.js` are not files in this checkout; do not import those old names.
