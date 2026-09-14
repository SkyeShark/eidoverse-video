# Vegetation and trees

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

**`createFlora`** — the VEGETATION BRUSH: asset-driven species with real map
sets (albedo/normal/roughness/translucency under `eidoverse/assets/grass/`),
GPU-instanced whole plants, 3-layer wind, and character pushers that part the
foliage around a walking body. One call paints one stand ("stroke"); layer
strokes to dress a scene. Async — `await` it.
```js
const f = await createFlora({ species: 'grass', size: 30, height: 0.45,
    color: 'copper', heightFn: terrain.heightAt, sunDir: SUN_DIR });
scene.add(f.mesh);
// per frame (walkers part the plants; slot 2 can ride the camera):
f.setPushers([{ x: p.x, y: p.y, z: p.z, r: 1.1 }]);
```
- Species: `grass` (green turf carpet — the meadow default), `galleta_dry`
  (desert bunch grass), `blackbrush`/`creosote`/`sagebrush` (real Mojave shrubs — grown skeletons,
  welded wood tubes with bark maps + foliage spray cards), `yucca` (Mojave
  yucca: bayonet crown, dried skirt, bendy trunk), `corn` (full plant: cane,
  arching leaves, husked ears with a BAKED real cob, silk, tassel),
  `sunflower` (full plant: cane, petioled heart-leaf canopy, one nodding
  head — seed-disc plate, dense fitted ray-petal whorl, bract rosette back;
  the head rides wind as one rigid assembly).
- Footprint: non-row stands are circular by default; `size` = diameter,
  or `width`/`depth` for ellipses; `footprint: 'organic'` masks a lobed
  irregular patch; `center: [x,z]`. De-centre overlapping strokes — concentric
  same-centre stands foreshorten into stamped bands.
- `density` = interior fullness (1 = authored); `seed` varies everything;
  on ROW plantings it works both ways: below 1 it leaves gaps in the rows,
  above 1 it tightens in-row spacing (a grid cannot hold more plants on
  command; the row gap is the machinery's, the in-row spacing is the crop's);
  `variant` picks another grown skeleton for shrub/corn species.
- Grass options: `height` (metres) sets blade length AND wind compliance (lawns
  are stiff, tallgrass sways); `color` = a GRASS_COLORS name — spring `green/
  lime/emerald/blue/blue-green/gray-green`, fall `burgundy/rust/copper/orange/
  straw/brown` — or a custom `[r,g,b]` multiplier. Blade grasses only.
  ⚠ The green family are MULTIPLIERS over the atlas; the rest are luminance
  RECOLORS (they discard the sheet's hue). A species authored in another hue
  (galleta_dry ships a straw recolor) can only be returned to green by a
  recolor — hence `green` — because its own recolor runs last and a
  multiplier cannot survive it.
- Corn: pair with `rows: { spacing: 0.9, plant: 0.24, angle, jitter, skip,
  stride, phase }` for a planted field (rectangular = cultivated; stride/phase
  interleave variant calls through ONE grid — e.g. every 5th row seeded with
  `corn: { peel: true }` for open cobs). Plants carry 1-3 ears, independently
  open/closed (`corn: { peelChance }`). A skipped row pair (`clipFn`) makes an
  honest drive lane — an in-canopy camera NEEDS one (or a pusher riding the
  lens) or it eats leaves.
- Sunflower: same `rows` treatment (spacing ~0.85, plant ~0.5); `heading`
  (world azimuth, ± `headingJitter`) points every plant one way — sunflower
  fields face the sun together; omit it for the wild-patch look. Lookdev
  pins via `sunflower: { pitch, headYaw, rank, stalkLean, heightJitter }`.
  Card widths follow `assets/grass/sunflower_fit.json` — the measured alpha
  envelope of the sheet's petal cells + leaf window (re-measure it whenever
  the art changes; the format lives in vegetation_sunflower_gen.js, which
  falls back to built-in envelopes without the file).
- Placement: `heightFn: (x,z)=>y` OR `surface: mesh/[meshes]` (raycast down —
  grows on ANY geometry: rocks, rooftops, sculpted ground; misses = no plant);
  `align` = surface-normal tilt share (grass hugs, woody stays skyward);
  `maxSlope`; `clipFn(x,z)`; explicit `placements: [[x, z, scale], ...]` for
  hero plants. Structural species claim footprints in a cross-stroke occupancy
  registry — later strokes avoid them (`avoid: false` opts out;
  `resetFloraOccupancy()` between scenes if you rebuild).
- Returns `{ mesh, stemMesh, material, update, setPushers, uniforms, count }`.
  Wind self-updates. `sunDir` should match your key light. Budgets: whole
  plants are 0.5-3.3K tris each and instanced — thousands are fine.
- The MOJAVE recipe (desert dressing, field-approved): galleta base + the
  three shrubs as de-centred organic strokes, two seeds each, yucca kept off
  the walk line with heroes staged by hand:
  ```js
  async function addField(species, options) {
    const field = await createFlora({ species, heightFn: terrain.heightAt, sunDir: SUN_DIR, ...options });
    scene.add(field.mesh);
    if (field.stemMesh && !field.stemMesh.parent) scene.add(field.stemMesh);
    return field;
  }
  await addField('galleta_dry', { width: 56, depth: 46, seed: 3, density: 1.3 });
  await addField('blackbrush', { width: 54, depth: 46, seed: 5, density: 0.85, center: [6, -4], footprint: 'organic' });
  await addField('blackbrush', { width: 54, depth: 46, seed: 55, variant: 1, density: 0.85, center: [-7, 6], footprint: 'organic' });
  // creosote + sagebrush: same pattern, own seeds/centres
  await addField('yucca', { width: 54, depth: 46, seed: 21, density: 0.7, clipFn: (x, z) => Math.abs(x) < 1.4 });
  await addField('yucca', { placements: [[2.4, 8.5, 1.9], [-2.5, 4.0, 2.3]] });   // heroes
  ```
  For natural variation, try multiple seeds and offset strokes. Repetition
  can be intentional in cultivated or graphic plantings. Inspect low camera
  angles for accidental stamped bands and canopy clipping.

## `makeSeedTree` — real procedural trees & plants

SeedThree's headless agent API (github.com/SkyeShark/SeedThree — same
three/TSL stack; a tree grown here is identical to one grown in the
SeedThree app, and presets round-trip with its Save/Load panel). Seed-first
design: iterate `seed` and read `stats` before touching any dial; open knob
folders on demand.

```js
const oak = await makeSeedTree({ species: 'whiteOak', seed: 1737, scene, sunLight: sun });
console.log(oak.stats.summary);                       // height/width/lod0Triangles
await makeSeedTree.describe();                        // species menu
await makeSeedTree.describe('joshuaTree', 'shape');   // ONE folder of dials
```

Verified gotchas: set `globalThis._noAutoFixPlacement = true` in `setup()`
— the placement auto-fix dismembers intentionally-overlapping tree
geometry. Trees sway by default (`makeSeedTree.setWind({strength, speed})`).
Judge shadowed trees from frame ≥2. Source: a `SEEDTHREE_DIR` / `../SeedThree`
/ `./SeedThree` checkout gives the textured tier; no checkout falls back to
GitHub import at geometry tier (placeholder materials).

Choose a species and silhouette for the setting, or use a suitable existing
tree asset. Inspect branch structure, foliage density, shadows and wind at
the camera distances the piece uses.


## Loading and reuse

`createFlora` is injected through `vegetation_loader.js`; it loads
`vegetation.js` and the species generators as needed. Call it with `await`
inside `setup()`. Reuse its instancing, shared maps and GPU wind rather than
cloning every leaf into an independent mesh. `makeSeedTree` is also injected;
check its reported species/options and local checkout availability.

Use `heightFn: terrain.heightAt` with [terrain-surfaces.md](terrain-surfaces.md).
`createFlora` has no general biological-growth control. A reveal or a deliberate
scale animation can suggest growth; scaling a whole field also scales spacing
and height, so use suitable separate groups for hero plants. Inspect grounding,
water contact and wind throughout the shot.

After awaiting `createFlora`, `FLORA_SPECIES` exposes the loaded species
table and `GRASS_COLORS` the color options. The current species are `grass`,
`galleta_dry`, `blackbrush`, `creosote`, `sagebrush`, `yucca`, `corn` and
`sunflower`; `meadow_blades` is an alias of `grass`. Use `dispose()` on the
returned field when retiring it rather than leaving its resources registered.

`vegetation_corn_gen.js`, `vegetation_shrub_gen.js` and
`vegetation_sunflower_gen.js` are geometry generators behind this API. Their
skeleton, wood and spray-card helpers support the brush; scene authors do not
need to assemble an independent update loop for every generator export.
