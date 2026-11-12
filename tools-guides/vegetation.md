# Vegetation — the flora brush

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Trees (SeedThree)](trees.md)

Trees and plants grown by SeedThree are [trees.md](trees.md) (`make_seed_tree`);
this guide is the vegetation brush.


**`create_flora`** — the VEGETATION BRUSH, Blender 5.2 EEVEE edition
(`blender/eidoblend/flora/`): asset-driven species with real map sets
(albedo/normal/roughness/translucency under `eidoverse/assets/grass/`), whole
plants grown by our own generators (the WebGPU edition's, ported line for line:
the same seed grows the same stand, except the shrubs' fine detail, see Not yet
ported), instanced by geometry nodes, and the
3-layer wind and character pushers evaluated in geometry nodes from Scene Time.
The motion is real geometry, so EEVEE's Vector pass (DLSS 5's temporal input),
motion blur and shadows all see it, and a saved film `.blend` renders any frame
in a fresh background Blender (no frame handlers). One call paints one stand
("stroke"); layer strokes to dress a scene. Blender coordinates: Z up, metres.
```python
import sys; sys.path.insert(0, '<repo>/blender')
from eidoblend.flora import create_flora
f = create_flora('grass', size=30, height=0.45, color='copper', height_fn=terrain_z)
# walkers part the plants: an object, an (armature, bone[, radius]) pair or a point (x, y, z[, r])
f.set_pushers([(body, 'leftFoot', 0.32), (body, 'rightFoot', 0.32), (body, 'hips', 0.42)])
```
- Species: `grass` (green turf carpet — the meadow default), `galleta_dry`
  (desert bunch grass), `blackbrush`/`creosote`/`sagebrush` (real Mojave shrubs — grown skeletons,
  welded wood tubes with bark maps + foliage spray cards), `yucca` (Mojave
  yucca: bayonet crown, dried skirt, bendy trunk), `corn` (full plant: cane,
  arching leaves, husked ears with a BAKED real cob, silk, tassel),
  `sunflower` (full plant: cane, petioled heart-leaf canopy, one nodding
  head — seed-disc plate, dense fitted ray-petal whorl, bract rosette back;
  the head rides wind as one rigid assembly), `daisy` (oxeye/Shasta clump:
  basal rosette of lobed spatulate leaves on tube petioles, 1-4 ribbed stems
  with clasping toothed leaves, a 4-6 cm head per stem — involucre cup, domed
  phyllotaxis disc, 24-30 notched fitted rays; now and then a bud; closable,
  recolourable). `FLORA_SPECIES` is the table; `meadow_blades` is an alias of
  `grass`. Scanned CC0 plants mix in through the same brush (below).
- Footprint: non-row stands are circular by default; `size` = diameter,
  or `width`/`depth` for ellipses; `footprint='organic'` masks a lobed
  irregular patch; `center=(x, y)`. De-centre overlapping strokes — concentric
  same-centre stands foreshorten into stamped bands.
- `density` = interior fullness (1 = authored); `seed` varies everything
  (any finite integer, including 0 and negatives);
  on ROW plantings it works both ways: below 1 it leaves gaps in the rows,
  above 1 it tightens in-row spacing (a grid cannot hold more plants on
  command; the row gap is the machinery's, the in-row spacing is the crop's);
  `variant` picks another grown plant for shrub/corn/sunflower/daisy species.
- Grass options: `height` (metres) sets blade length AND wind compliance (lawns
  are stiff, tallgrass sways); `color` = a `GRASS_COLORS` name — spring `green/
  lime/emerald/blue/blue-green/gray-green`, fall `burgundy/rust/copper/orange/
  straw/brown` — or a custom `[r, g, b]` multiplier. Blade grasses only.
  ⚠ The green family are MULTIPLIERS over the atlas; the rest are luminance
  RECOLORS (they discard the sheet's hue). A species authored in another hue
  (galleta_dry ships a straw recolor) can only be returned to green by a
  recolor — hence `green` — because its own recolor runs last and a
  multiplier cannot survive it.
  - `blades=` (Blender edition) overrides the blade habit: `'fine'` = meadow
    grass for shots at a person's feet (blades a third as wide, about three
    times as many per plant), or a dict of `perBunch`, `bunchR`, `h`, `w`,
    `lean`. The default habit (the WebGPU edition's) reads right from a few
    metres out, but at the feet its 2-4 cm blades read as iris leaves.
  - `normals=`: blades default to `'true'` here = each card's own normal,
    two-sided; `'gather'` = the WebGPU edition's light-gather normals (blades
    lit as if facing straight up), which under a low sun turns fine blades
    into grazing mirrors (white specular streaks, a sky-tinted haze from a low
    camera); a number t = that share of world up over the true normal. Every
    other species keeps its generator's light-gather normals (bent shrub
    crowns, up-blended leaves, the daisy heads two-sided).
  - Blade sheen (Blender edition, both on for blade grasses): `curl=1.4`
    bends the shading normal across each blade (a real blade is folded or
    curved, a card is flat), so a low sun glints on a thin line of each blade
    instead of mirroring off whole cards in white strips; `grazing_damp=True`
    eases the specular as the view grazes a card. `rough=` (× the species'
    roughness) and `specular=` (Principled specular level, 0.5) are there for
    lookdev; `blender/tests/flora/t_sheen.py` A/Bs them into a low sun.
    Blade grasses default to `rough=1.6` (about 0.62, a grass blade's usual
    roughness; the WebGPU edition's ~0.39 is glossy for these blades): at
    ×1.0 the gust-bent blades of a wide meadow mirrored a low sun in crisp
    white lines that read as frost; at ×1.6 they keep a soft sheen and the
    look at the feet is unchanged. Pass `rough=1.0` for the WebGPU value.
- Corn: pair with `rows={'spacing': 0.9, 'plant': 0.24, 'angle': a, 'jitter',
  'skip', 'stride', 'phase'}` for a planted field (rectangular = cultivated;
  stride/phase interleave variant calls through ONE grid — e.g. every 4th row
  seeded with `corn={'peel': True}` for open cobs). Plants carry 1-3 ears,
  independently open/closed (`corn={'peel_chance': p}`). A skipped row pair
  (`clip_fn`) makes an honest drive lane — an in-canopy camera NEEDS one (or a
  pusher riding the lens) or it eats leaves. `rows['angle']` turns the planting
  counter-clockwise seen from above.
- Sunflower: same `rows` treatment (spacing ~0.85, plant ~0.5); `heading`
  (world azimuth `atan2(dy, dx)`, ± `heading_jitter`) points every plant one
  way — sunflower fields face the sun together; omit it for the wild-patch
  look. In this edition the heads face `heading` itself (the WebGPU edition
  added the stroke's random head yaw; `create_flora(..., webgpu_heading=True)`
  keeps that, plant for plant the JS stand).
  Lookdev pins via `sunflower={'pitch', 'head_yaw', 'rank', 'stalk_lean',
  'height_jitter'}`. Card widths follow `assets/grass/sunflower_fit.json` —
  the measured alpha envelope of the sheet's petal cells + leaf window
  (re-measure it whenever the art changes; the format lives in
  vegetation_sunflower_gen.py, which falls back to built-in envelopes).
- Daisy (`vegetation_daisy_gen.py`, the `daisy_` sheet — modelled and baked
  in Blender; source and rebuild steps in
  [`assets/grass/daisy_src/`](../eidoverse/assets/grass/daisy_src/README.md)): meadow density by
  default (12 clumps/m², ~2.5 heads each); layer seeds for variety.
  - `color`: `white` (default), `orange` (Claude orange, #D97757 mid-ray),
    `pink`, `yellow`, `cream`, a custom sRGB `[r, g, b]`, or a weighted mix
    `{'white': 5, 'orange': 3, 'yellow': 1}` chosen per plant (all heads of a
    plant share a colour). Rays only: the disc stays gold. `DAISY_COLORS`
    lists them.
  - `heading`: which way the heads face — an azimuth in radians
    (`math.atan2(dy, dx)`), a direction `(x, y, z)` (e.g. the sun's; its
    elevation tilts the heads), or `{'toward': (x, y, z)}` — every plant turns
    to that point (a camera). `heading_jitter` (rad) loosens it. Omit for wild.
  - `height` = flowering stem height in m (0.45); `head_scale` enlarges heads
    for stylized shots (2-4; stems thicken with it).
  - `close` (0 open … 1 shut): the rays fold up about their hinges and curl
    in over the disc. `field.set_close(v, frame=f)` keys it (the film's dusk:
    key 0 and 1 and it plays from the saved .blend).
  - No far-LOD impostor in this edition: EEVEE's 16 samples resolve far heads'
    colour (checked on a 48 m superbloom); the impostor quads are dropped.
  - Lookdev: `field.heads` lists each head's plant-local centre `c`, axis `a`,
    diameter `d` and wind weight `aH` for aiming cameras (Blender axes).
  ```python
  # a mixed superbloom (~22k plants): interleaved seeds, one cohort turned to the sun; at dusk every stroke closes.
  # moving, a stand this size over its grass realizes to ~39 M vertices: past EEVEE's deforming-velocity budget, so it is still
  # (motion=False) and a moving stroke covers the camera's foreground
  MIX = {'white': 5, 'orange': 3, 'yellow': 1, 'pink': 1}
  bloom = [create_flora('daisy', size=48, center=(0, 18), seed=seed, density=density, color=MIX, heading=heading,
                        height_fn=terrain_z, motion=False)
           for seed, density, heading in ((3, 0.31, None), (17, 0.31, None), (29, 0.27, None), (41, 0.26, SUN_DIR))]
  bloom.append(create_flora('daisy', size=8, center=(0, 2.5), seed=31, density=0.5, color=MIX, height_fn=terrain_z))
  for f in bloom:
      f.set_close(0.0, frame=dusk_start)
      f.set_close(1.0, frame=dusk_end)
  ```
- Placement: `height_fn(x, y) -> z` OR `surface=obj` / `[objs]` (raycast straight
  down onto their evaluated world meshes — grows on ANY geometry: rocks,
  rooftops, sculpted ground; misses = no plant; hit normals in world space);
  `z` = the ground height when neither is given; `align` = surface-normal tilt
  share (grass hugs, woody stays skyward); `max_slope` (rad); `clip_fn(x, y)`
  (True = no plant); explicit `placements=[(x, y, scale), ...]` for hero plants.
  A plant is one rigid instance tilted to the normal at its root: a wide
  grass bunch (`blades='fine'` spreads its blades 0.35 m from the root) on a
  thin slab or a sharp curve hangs its outer blades below the surface. Keep
  bunches off such edges with `clip_fn`, or narrow them (`blades={'bunchR':
  0.12}`); on terrain-scale curvature the error is millimetres.
  Structural species claim footprints in a cross-stroke occupancy registry —
  later strokes avoid them (`avoid=False` opts out; `reset_flora_occupancy()`
  between scenes if you rebuild).
- Wind: `wind` scales sway and gust (1 = authored), `wind_dir=(x, y)`
  (default (1, -0.3)). All three layers (global sway, gust fronts rolled by the
  shared noise envelope, per-plant flutter) and the push are the WebGPU
  edition's maths, run per vertex in the `EB Flora Field` geometry nodes from
  Scene Time (seconds): `field.set_wind(strength=, sway=, gust=, flutter=,
  direction=, frame=)` changes or keys them. The field object stays at the
  world origin (wind and pushers are evaluated in world space). The authored
  grass wind is a breezy day (a gust can lean a meadow blade 45°); `wind=0.4`
  is a calm one. `keep_length=True` (Blender edition, default) keeps the
  WebGPU edition's lean but not its stretch: its offset is sideways only, so
  a gust shears a blade longer; here each vertex keeps that lean direction and
  its own height above the plant's root (sideways d·k, down hv·(1−k),
  k = hv/√(hv²+d²)), so blades bend instead (`keep_length=False` for the
  WebGPU shear).
- Pushers: `field.set_pushers(items, radius=1.2)` — each item is an object
  (followed), `(armature, bone[, radius])` (follows the bone's head) or a point
  `(x, y, z[, r])`. Each becomes an empty in the `flora_pushers` collection,
  parented to what it follows; its world X scale is its radius. Every stroke
  reads that collection (pass `pushers=<collection>` to give a stroke its
  own), so one walker parts every stroke; up to 6 pushers are read. Plants
  lean away from the pusher, whole plant (roots 30 %, tips 100 %), with a soft
  0.6 m ceiling. For a walking body, the feet at ~0.32 m and the hips at
  ~0.42 m part the stems round the legs; one 1.1-1.4 m pusher per walker is
  the WebGPU edition's coarser habit. The push follows the pusher frame by
  frame (no lag, no spring), so a foot swinging past whips the nearest
  blades: up to ~0.5 m in one frame at walking pace. Motion blur smears it;
  watch it in close walk shots, and use a smaller foot radius or a shin
  pusher if it reads as a snap.
- Returns a `FloraField`: `.object` (the plants: a vertex per plant under the
  geometry nodes), `.prototype` (the grown plant, hidden in `flora_prototypes`),
  `.materials`, `.count`, `.heads`, `.stats`, `set_pushers`, `set_close`,
  `set_wind`, `remove()`. Budgets: whole plants are 0.08-5K verts each; a
  moving stroke is realized as one deforming mesh each frame (that is what
  lets the Vector pass see the wind): 10 M vertices evaluate in about 0.1 s
  and rendered at 960×540, 16 samples, Vector pass on, in 8 s. EEVEE's
  velocity buffer for deforming geometry gives out somewhere between 10 M and
  39 M realized vertices ("Could not allocate velocity geometry buffer"; with
  the Vector pass on, Blender then crashed). So for a big stand, keep the
  moving strokes near the camera and give the far ones `motion=False`: still,
  instanced geometry, no Scene Time, the same placement and materials
  (`t_scale.py --split --vector`: the superbloom's 22,227 daisy clumps and
  32k grass plants still behind a moving meadow, Vector pass on, 2.4 s a
  frame at 960×540).
- Materials: the sheet's albedo (alpha cut at 0.35, dithered), roughness map,
  tangent normal map relief over the light-gather normal, and translucency —
  a Translucent lobe coloured by the albedo and scaled by the translucency
  map, so backlit leaves glow their own green. Per-plant shade ±7.5 %. Shrub
  wood uses its bark set (albedo × the species' stem tint, roughness, and the
  bark normal map). Leaf cards cast real alpha shadows.
  - The specular fades out where the shading normal turns away from the
    camera (the back of a light-gather card, a curled edge seen edge-on):
    EEVEE's lobe still answers such a normal, and a sun behind the plant lit
    white specks on the petal and bract edges of backlit sunflower heads.
  - Energy: the Translucent lobe is added to the full diffuse, so a bright
    sheet (white daisy rays) reflects and transmits about its albedo each —
    more than a real petal. Backlit white and orange daisies still read as
    backlit petals, not lamps, so that is the default. For the strict budget
    (reflection + transmission ≤ 0.95, one factor so the hue holds) set
    `eidoblend.flora.nodes.TRANSL_ENERGY = 'normalize'` before building
    strokes: in the A/B its backlit white rays read as grey paper and
    sunflower petals turn brown.
- The MOJAVE recipe (desert dressing, field-approved): galleta base + the
  three shrubs as de-centred organic strokes, two seeds each, yucca kept off
  the walk line with heroes staged by hand:
  ```python
  def add_field(species, **kw):
      return create_flora(species, height_fn=terrain_z, **kw)
  add_field('galleta_dry', width=56, depth=46, seed=3, density=1.3)
  add_field('blackbrush', width=54, depth=46, seed=5, density=0.85, center=(6, 4), footprint='organic')
  add_field('blackbrush', width=54, depth=46, seed=55, variant=1, density=0.85, center=(-7, -6), footprint='organic')
  # creosote + sagebrush: same pattern, own seeds/centres
  add_field('yucca', width=54, depth=46, seed=21, density=0.7, clip_fn=lambda x, y: abs(x) < 1.4)
  add_field('yucca', placements=[(2.4, -8.5, 1.9), (-2.5, -4.0, 2.3)])   # heroes
  ```
  For natural variation, try multiple seeds and offset strokes. Repetition
  can be intentional in cultivated or graphic plantings. Inspect low camera
  angles for accidental stamped bands and canopy clipping.
- A MEADOW at a person's feet: fine-habit grass under the daisies, white and
  Claude orange (`blender/tests/flora/t_meadow.py`; `t_walk.py` walks a body
  through it; `t_mix.py` adds scanned plants along a trodden path):
  ```python
  create_flora('grass', size=26, seed=3, height=0.42, blades='fine')
  create_flora('grass', size=18, seed=17, center=(1.5, 3.0), density=0.55, height=0.55, blades='fine')
  create_flora('daisy', size=13, seed=5, center=(0.4, 2.2), density=0.45, color='white')
  create_flora('daisy', size=10, seed=29, center=(-1.6, 3.6), density=0.35, color='orange')
  create_flora('daisy', size=8, seed=41, center=(1.8, 0.8), density=0.3, color={'white': 1, 'orange': 1})
  ```
- Scanned plants (CC0 Poly Haven sets) mix in through the same brush —
  placement, wind, pushers — as `create_flora('ph:<asset>', ...)`. Each plant
  picks one of the set's variant meshes and keeps the set's scanned material.
  | asset | what | variants | default density |
  |---|---|---|---|
  | `grass_medium_01` | grass tufts, 5-32 cm | 17 (`small_a` … `tall_c`, `tiny_*`), LOD0-2 | 28 /m² |
  | `grass_medium_02` | grass tufts, 15-40 cm | 5 (`a`-`e`), one LOD | 28 /m² |
  | `celandine_01` | celandine clumps, 12-18 cm | 5 (`a`-`e`), LOD0-2 | 3 /m² |
  | `dandelion_01` | dandelion rosettes, 4-16 cm | 5 (`a`-`e`), LOD0-3 | 3 /m² |
  | `shrub_sorrel_01` | sorrel carpet, 2-6 cm | 11 (`a`-`k`), one LOD | 40 /m² |
  | `weed_plant_02` | flat weed rosettes, 6-7 cm | 5 (`a`-`e`), LOD0-3 | 1.5 /m² |

  `lod=1` by default; a set without that LOD gives its nearest (`lod=3` on
  `grass_medium_01` uses LOD2, with a note), and one-LOD sets ignore `lod`.
  `variants=['mid', 'tall']` (or `['a', 'b']` on the lettered sets) keeps
  those name prefixes. A set is appended once per .blend: other LODs and
  filters reuse its objects, materials and maps. The sets are read from
  `$EIDOBLEND_PH_ASSETS` (set it to a folder holding the six Poly Haven
  sets as `.blend` downloads); without it the module looks in one studio
  machine's work folder. Scanned plants are plants; skies, terrain and our own
  species stay ours. They are short: in a 0.4 m meadow they vanish, so give
  them a path, a mown edge or the meadow's foot (`t_mix.py` grows them in a
  trodden path; `t_scanned.py` lines up all six on bare ground).
- Tests: `blender/tests/flora/` — `parity_check.py` (system Python: the
  generators and placement against the JS, case by case, from
  `parity_dump.mjs`'s Deno dumps), `t_meadow.py` (`--light sun16`: the sky
  family's 16:30 sun numbers over Blender's physical sky instead of the test
  gradient), `t_lookdev.py`, `t_sheen.py`, `t_walk.py` (pushers on a walking
  body), `t_motion.py` (the Vector pass against the projected vertex motion,
  with a wind-off control), `t_close.py` (keyed dusk close + frame purity of
  the saved .blend), `t_species.py` (with a `webgpu_heading` check),
  `t_mix.py`, `t_scanned.py`, `t_scale.py`. Run through `run_blender.sh`
  (one render at a time on a shared GPU); `--no-render` builds without
  rendering. The tests' lights are test lights (`_scene.lights`), not the sky
  family's look: judge final looks again under the real sky.

## Trees and plants grown by SeedThree

Trees and plants: see [trees.md](trees.md) (`make_seed_tree`).

## Loading and reuse

`create_flora` imports from `eidoblend.flora` (put `<repo>/blender` on
`sys.path`); its planning half (species, generators, placement:
`vegetation.py`, `plan_flora`) runs without Blender, so it can be tested in a
plain Python. Reuse its instancing, shared maps and geometry-nodes wind rather
than cloning every leaf into an independent mesh: strokes share the
`EB Flora Field` node group, the sheet materials and images, and the gust
texture (packed into the .blend).

Use a terrain height function or `surface=` with
[terrain-surfaces.md](terrain-surfaces.md). `create_flora` has no general
biological-growth control. A reveal or a deliberate scale animation can
suggest growth; scaling a whole field also scales spacing and height, so use
suitable separate groups for hero plants. Inspect grounding, water contact and
wind throughout the shot.

`FLORA_SPECIES` is the species table, `GRASS_COLORS` the grass colours and
`DAISY_COLORS` the daisy ray colours. The current species are `grass`,
`galleta_dry`, `blackbrush`, `creosote`, `sagebrush`, `yucca`, `corn`,
`sunflower` and `daisy`; `meadow_blades` is an alias of `grass`; `ph:<asset>`
names a scanned set. Use `remove()` on the returned field when retiring it.

`vegetation_corn_gen.py`, `vegetation_shrub_gen.py`,
`vegetation_sunflower_gen.py` and `vegetation_daisy_gen.py` are the geometry
generators behind this API (ports of the `.js` files of the same names, on
`three_math.py`'s three.js Vector3/Quaternion semantics and `jsmath.py`'s
RNGs). Scene authors call `create_flora`; the generators return plants in the
WebGPU edition's Y-up space, converted once into Blender's.

## Not yet ported

What the WebGPU brush had that this one does not, or dropped on purpose:

- Shrub bit-exactness: blackbrush/creosote/sagebrush match the JS in vertex
  and triangle counts, but their skeletons tie exactly on a distance test,
  and V8's Math.sin/cos (glibc-derived) and the C library's differ by one ulp
  now and then, so a tie can break the other way and a seed grows a
  different (equally valid) shrub. Exactness would need V8's trig in Python
  (fdlibm matches its acos, not its sin/cos). Grass, galleta, yucca, corn,
  sunflower and daisy match the JS exactly.
- The daisy far-LOD impostor and its `lod` distances: dropped (above).
- The emissive fill, the backlit fallback for species without a translucency
  map, the N8AO `_aoParams` advice and `sunDir`: EEVEE's GI, shadows and
  translucency do that work; `sun_dir` is accepted and ignored.
- The WebGPU loader shim, `update(t)`, the `uniforms` object and `dispose()`:
  replaced by the import, Scene Time, `set_wind` / `set_close` and `remove()`.
- Pushers act in plan (x, y) as in the WebGPU edition: their height is
  ignored, so a hand at waist height parts the grass under it.
- Still strokes (`motion=False`) skip the daisy round-head fix (it is a
  per-vertex offset, and a still stroke's instances are never realized), so
  their heads keep the instance's ±15 % vertical stretch. They are meant for
  the far field, where a 4-6 cm head's stretch is a pixel or two.
- No viewport-playback path: a moving stroke is realized and deformed every
  frame, which suits renders (0.1 s for 10 M vertices, 0.6 s per frame change
  at 39 M) but makes viewport scrubbing of a big meadow slow. Build layout
  passes with `motion=False` strokes (instanced, quick to scrub) and the
  render build with moving ones.
- Scanned plants have no per-plant shade, no added translucency (their
  scanned materials as shipped) and a height-ramp wind weight.
- `create_flora` has no general biological-growth control (above).
