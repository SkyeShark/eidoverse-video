# Trees (SeedThree)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Vegetation](vegetation.md)

**`make_seed_tree`**: SeedThree's procedural trees and plants, Blender 5.2 EEVEE
edition (`blender/eidoblend/trees/`). It is a thin bridge over the SeedThree
Blender add-on (SeedThree's `blender` branch, `blender/seedthree/`). That add-on
grows the same trees as the SeedThree web app from the same species presets,
seeds and dials: the generators are ported line for line and checked against the
JS, mesh buffer by mesh buffer. Bark, leaf, frond and spine materials are real
EEVEE node trees: the JS backlight, alpha-clipped cards and the canopy dome
normal. The wind is one shared Geometry Nodes group evaluated from Scene Time,
so EEVEE's Vector pass, motion blur and shadows all see it. Presets round-trip
with the app's Save/Load panel. The app's level ladder comes along: baked branch
cards, the far billboard, the mobile ladder, distance switching, the 64-tree
grove, the `.glb` export, the app's demo scene and example scenes, and its asset
tools. Coordinates: Blender, Z up, metres.

```python
import sys; sys.path.insert(0, '<worktree>/blender')
from eidoblend.trees import make_seed_tree
MEADOW_OAK = {'height': 14.5, 'levels': 4, 'trunks': 1, 'trunkThickness': 1.4, 'crownShape': 2,
              'branchDensity': 24, 'branchAngle': 64, 'gnarliness': 80, 'leafSize': 0.38,
              'leavesPerBranch': 24,
              'paramOverrides': {'length': {1: 0.56, 2: 0.46, 3: 0.4}, 'branches': {2: 18, 3: 12},
                                 'downAngle': {3: 45}, 'curveV': {3: 60}}}
oak = make_seed_tree(species='whiteOak', seed=1737, dials=MEADOW_OAK, location=(12, -4, 0), rotation=0.6)
oak['stats']['summary']   # {'heightMeters': 16.058, 'widthMeters': 23.751, 'lod0Triangles': 252384, ...}
oak['preset']             # seedthree-preset/1: open it in the app (Save & Load > Load preset)
# once the sky family has lit the scene (sky = make_sky(...)):
make_seed_tree.set_sun(sky.sun)    # the backlight follows its sun lamp
make_seed_tree.light_probe(oak)    # bake EEVEE's occluded sky inside the crown (about 2 s)
print(make_seed_tree.describe())                    # species menu
print(make_seed_tree.describe('whiteOak'))          # one species: quick start + folder index
print(make_seed_tree.describe('whiteOak', 'shape')) # one folder of dials
```

## Design the tree for the shot

A tree in a film is designed, not left at the preset. The seed picks the
individual. The dials make it the tree the shot needs: open-grown or
forest-drawn, young or old, wind-shaped, pruned. Work in this order:

1. Species. Pick from `describe()`. There are 15 Weber-Penn broadleaves and
   conifers, two dichotomous desert plants (`joshuaTree`, `saguaro`), and three
   spray shrubs (`creosote`, `blackbrush`, `sagebrush`).
2. Seed. Roll a few seeds and read `stats` (height, width, triangles). Render a
   contact sheet of the candidates from the shot's camera before choosing.
3. Shape folder (`describe(species, 'shape')`). These dials set the habit: height,
   crown shape, trunks, branch density, branch angle, gnarliness, leaf size, and
   leaves per branch.
4. Advanced folder (`describe(species, 'advanced')`). Per-level Weber-Penn dials
   are paths: `{'paramOverrides': {'downAngle': {1: 70}}}`. The desert plants
   have flat L-system dials here instead.
5. Material folder. `leafColorize` + `leafTintAmount` recolour the canopy while
   keeping its luminance (autumn, drought). Also here: `barkTint`, `leafAlpha`,
   the frond tints with `frondDryness`, `spineTint` and `barkDamage`. The JS
   applies these only inside the app; here they reach the EEVEE materials.

The worked example is the lone white oak in a sunny meadow above
(`blender/tests/trees/meadow_oak_design.py` holds the same dials). It is
rendered by `meadow_oak.py`, which also renders the untouched preset for
comparison.

- `trunks: 1`. The preset forks at the soil. A meadow oak has one massive bole.
- `crownShape: 2` (hemispherical). The lowest limbs are the longest, which gives
  the broad dome, wider than tall.
- `branchAngle: 64`. The limbs spread without drooping (74 laid a limb on the grass).
- `levels: 4` with `paramOverrides.branches[3] = 12`. This adds a fourth branch
  order of fine twigs. Without children on that order (the preset has 0), a
  4-level tree is leafless.
- `leafSize: 0.38`, `leavesPerBranch: 24`. At film distances, the preset's 0.6 m
  cards read as giant leaves. Smaller, more numerous leaves read as a canopy.
- The result is 23.8 m wide by 16.1 m tall, with 252k triangles at LOD0. It
  builds in 1.7 s and renders 960×540 at 16 samples in about 1 s.

## Placement, duplicates, wind

- `location` is the trunk base. The plant hangs its species' `plantSink` below
  it (0.2 m for trees, 0.015 m for shrubs), so the base meets the ground with no
  gap. The JS bridge dropped this sink (bug d).
- A far tree line costs little at LOD0. Grow a few individuals, place them many
  times with `make_seed_tree.duplicate(tree, location=..., rotation=...)`, and
  bake one probe over the grove. `blender/tests/trees/treeline.py`: three oaks
  grown in 4.9 s, twelve placed 55-140 m out (3.0 M triangles), probe baked in
  2.2 s, 960×540 rendered in 1.3 s. The app's own cheap levels are below.
- `duplicate()` makes a new root Empty with copies of every part object. The
  meshes are linked (no new geometry), and each copy keeps its own wind phase.
  Duplicating the Empty by hand copies only the Empty: select its hierarchy
  first, or use `duplicate()`. `make_seed_tree.remove(tree)` deletes a plant
  with everything under it.
- Each plant is a root Empty (`oak['object']`, with custom properties
  `seedthree_preset`, `seedthree_species`, `seedthree_seed` and
  `allow_intersect`) parenting one mesh per part and level: bark, foliage (or
  cards, or fronds), spines and fruit; the billboard is an Empty with its two
  cards. Move or rotate the root. `make_seed_tree.tree_from_root(root)` rebuilds
  the dict `make_seed_tree` returned from a plant in a saved file (it regrows the
  data, reuses the file's baked cards, builds no meshes).
- `oak['stats']['boundingBox']` is in Blender axes (Z up) in the root Empty's
  frame, sink included. `oak['stats']['boundingBoxWorld']` is the world box at
  the given location and rotation.
- Wind is on by default at the JS values (strength 0.5, speed 1). It is shared
  by every SeedThree plant in the file:
  `make_seed_tree.set_wind(strength=0.3, speed=0.8)`. For gusts, keyframe
  `bpy.data.node_groups['SeedThree Wind'].nodes['Wind Strength'].outputs[0].default_value`.
  Pass `wind=False` for a still plant. The sway is a real deformation:
  - At strength 0.5, the meadow oak at 37 m moves up to 0.14 px per frame in
    the Vector pass.
  - Leaves stay on their twigs.
  - The trunk base barely moves: the JS sway weights never reach 0, so the
    lowest 0.5 m of bark moves up to 8 mm at strength 0.5.
  - Rotated plants sway with the world wind direction.
- The wind phase follows world position, so a duplicate placed elsewhere sways
  out of step with the original, as a neighbour should.

## Far trees: the level ladder, the billboard and the grove

Hero trees use `level='LOD0'` (the default). For trees that only ever stand
far away, the app's own ladder is here, baked from the plant itself:

```python
far = make_seed_tree(species='whiteOak', seed=1737, level='ALL', billboard=True)   # LOD0, LOD1, LOD2, BB
make_seed_tree.frame_camera(far)       # the app's framing: switch distances scaled by the species
make_seed_tree.auto_lod(far)           # each level in its camera-distance band (drivers)
grove = make_seed_tree.forest_ring(far, count=64)                                 # the app's grove
make_seed_tree.set_sun(sun)            # after the sun exists: backlight + billboard shadows follow it
```

- **LOD1** halves the triangle budget (`lod1Pct` 50 %). **LOD2** keeps a
  decimated twig skeleton and replaces every terminal twig's leaves with one
  **baked branch card** (or a crossed pair for dogwood, the willow's bowed
  gravity sheets). The card set is baked once per design from a few exemplar
  twigs of the LOD0 tree itself: four channels (albedo, world normal, roughness,
  translucency) rendered by EEVEE through orthographic cameras. A re-grow or a
  reopened file reuses the baked materials. The white oak's LOD2 is 8,108
  triangles against 56,208 at LOD0.
- The **billboard** (`billboard=True`, level `'BB'`) is two crossed cards baked
  from LOD0, framed on the trunk axis. As in the app it casts the canopy's
  shadow on the ground and receives none (crossed flat cards banding
  themselves is what looks bad): the key sun skips the cards and a shadowless
  twin of it lights them, by light linking. The twin follows the sun's
  rotation, energy, colour and angle. `bake_impostor(tree, cast_shadow=False)`
  casts nothing. Unshadowed and lit through its dome normal, the billboard
  reads lighter and flatter than the self-shadowed LOD0 crown
  (`blender/tests/trees2/out/cards_whiteOak_far70_*.png`), so keep the switch
  out of shot: a tree that crosses it in view pops brighter. The card carries no
  specular: under a sun behind the tree, its smooth dome normal used to catch
  one grazing glint over the whole card, and a back-lit grove rendered white.
  `blender/tests/trees2/billboard_light_match.py` measures the billboard against
  LOD0 with the sun in front, beside and behind (the white oak's billboard:
  1.25 / 1.67 / 0.99 × LOD0's luminance).
- `auto_lod(tree, camera=None, lod1Dist=, lod2Dist=, billboardDist=)` drives
  every level's visibility from the camera distance, so a saved .blend switches
  on its own. The app's switches use a 5 % hysteresis that needs the previous
  frame; drivers switch exactly at the distances. `frame_camera(tree)` is the
  app's species-switch framing (18° down, the box fitted × 1.08) and sets the
  switch distances from it with the species' `lodDistanceMultipliers` (the
  willow keeps its expensive levels longer: 2.5 / 6.5 / 10.5 against 1.5 / 3 /
  5.5). `preview_level(tree, 'LOD2')` forces one level (numbered as the app's
  dropdown; `'AUTO'` restores the switching).
- **Mobile performance target**: `lod={'mobileTarget': True}` builds the app's
  card-first ladder. LOD0 and LOD1 stay built but parked; the card LOD2 is the
  near view; LOD3 and LOD4 thin the cards and tubes further (nested stable
  subsets, so a farther rung never shows a card the nearer one lacks). Joshua
  trees and yuccas swap their dead-leaf skirts for the thatch bark (the skirt
  folded into the trunk texture) and their terminal arms for 4-way rosette
  cards; the saguaro sheds ribs and spines. `lod0Density` thins the rosettes of
  the near view.
- `forest_ring(tree, count=64, height_at=, meadow_at=)` plants the app's grove:
  60 % of the slots in a 38-95 m band, the rest out to 200 m in the meadow
  pockets, each slot a random yaw and 0.5-1.1 scale. Geometry Nodes put the
  tree's LOD2 on every slot nearer the active camera than the billboard
  distance and the billboard on the rest, re-binned on every frame. The near
  slots sway, each with its own phase; the far billboards live in a second
  object (`grove['billboard_object']`) so they alone cast without receiving.
  `set_billboard_distance(grove, metres)` moves the switch.
- Bakes render on the GPU: run scripts that grow far levels through the GPU
  slot. The white oak's three-card set at 512² bakes in about 3 s, its 1024²
  billboard in about 4 s. `lod={'cardRes': 1024, 'cardVariants': 4,
  'billboardRes': 2048}` raise the resolution; `cards=False` keeps the headless
  JS's cluster-spray fallback (no bake).

## Light: the sun binding and the light probe

The plants are lit by the scene: use the sky family's `make_sky` (its sun lamp
is `sky.sun`, named `eido_sky_sun`). Two calls tie the trees to that light.
Make both after the sky and sun are final.

- `make_seed_tree.set_sun(sun)` points the leaf, frond and spine backlight at a
  sun lamp, and makes the billboards cast-only against it. The binding is one
  shared node group ("SeedThree Sun") driven by the lamp's world rotation. It
  follows the lamp when you animate it, and it covers every SeedThree plant in
  the file. `make_seed_tree(...)` binds the strongest sun lamp in the scene by
  itself when nothing is bound yet; `sun_light=` picks one. If you grow trees
  before the sky exists, call `set_sun` once the sun is there. Unbound, the
  backlight assumes a sun straight overhead.
- `make_seed_tree.light_probe(trees)` fits a Light Probe Volume around one plant
  or a list of plants and bakes it (about 2 s per oak; `spacing=` metres between
  samples, default 1.5). Without it, EEVEE lights the inside of a crown with the
  whole, unoccluded sky. Front-lit, that only flattens the canopy. Backlit
  (under the crown toward the sun, a low sun behind the tree), the sky through
  the leaves' backlight makes the whole crown glow evenly, like frosted glass.
  With the probe, the core of the crown goes dark and the sunlit sprays glow:
  `out/meadow_oak_sunset.png`, `out/meadow_oak_under.png`. A set-wide Light
  Probe Volume from the lighting family works too, if it covers the trees at
  about 1.5 m spacing. Re-bake when the sky or sun changes.
- The trees family's probe scenes use a neutral physical Sky Texture (strength
  0.10) plus a 4 W/m² sun lamp. That pairing reads as a clear sunny day under
  AgX. A physical sky at strength 1 next to a 4 W/m² sun washes everything out.

## Materials (what EEVEE draws)

- Bark: the species' PBR set. Albedo (sRGB) × Bark tint, a tangent normal map,
  and roughness from the map's G channel. Furrows run straight up each stem:
  every stem has a constant integer U wrap and square texels.
- Leaves and sprays: the species' leaf card, alpha-clipped at Leaf alpha.
  - The shading normal is the canopy dome (outward from the crown's base centre,
    biased up) plus 0.9 × the normal map's relief:
    `normalize(normalize(dome) + 0.9 relief)`, as in the JS. The canopy shades as
    a volume.
  - Backlight: the JS's Barré-Brisebois term, with the JS constants (leaves:
    distortion 0.3, power 6, scale 3, ambient 0.16), against the bound sun:
    `k = saturate(V·−normalize(L + 0.3N))^6 × 3 + 0.16`, glow
    `k × translucency × per-leaf thickness × species transmit × sun`. It is
    shadowed by the canopy, as the JS's shadow map does. Two routes,
    `make_seed_tree.set_backlight(mode)` for plants grown from then on (the
    add-on: Light > Backlight):
    - `'translucent'` (the default): a Translucent BSDF on the leaf's own
      normal, the term × the leaf's Lambert factor `max(0, −N·L)`, so the glow
      fades at the silhouette, and front-lit leaves get none of it. Every lamp
      reaches it. EEVEE drops the leaf's diffuse light when a translucent
      closure uses another normal, so this backlight must share the leaf's.
    - `'glow'` (opt-in): the JS term itself. Lit from behind, the crown glows
      out to its silhouette; front-lit, every sunlit leaf carries the ambient
      scatter (`0.16 × tcol × sun`), which is what makes the app's canopy read
      light yellow-green (`blender/tests/trees2/out/glow_oak_front_glow.png`
      against `glow_oak_front_translucent.png`). EEVEE gives no lamp's light alone, so the shared
      group "SeedThree Sun Direct" reads it through Shader to RGB of four white
      Translucent BSDFs and cancels the world and light-probe part (EEVEE's
      diffuse sky light is an L1 spherical harmonic, affine in the normal);
      measured, a bright world changes the glow by nothing. The glow joins the
      leaf as emission. Other lamps also reach those reads, weighted by their
      angle to the sun, so keep it to sunlit shots (or light-link the lamps
      away from the plants); with no sun lamp bound there is no glow. It is a
      heavy shader: each Shader-to-RGB read inlines EEVEE's light loop. In the
      trees2 batch, a 12 GB memory-capped Blender holding the whole demo scene,
      the GPU driver ran out of memory linking the leaf and card shaders, and
      EEVEE drew the leaves missing and the cards magenta; it compiled in the
      smaller scenes. Check the first render of a glow shot.
  - Every leaf, card, frond and spine part carries the app's shadow
    `normalBias` (0.04 m) as EEVEE's shadow terminator offset, applied at every
    angle. EEVEE shadows a card lit from behind at a grazing angle (the sun more
    than about 45° off the card's normal) with the card itself; the bias gives
    that light back in part. Measured with the trees tests' settings (2 shadow
    rays, 8 steps), a card lit from behind 54° off its normal keeps 96 %
    (translucent) / 71 % (glow) of its light, 72° off 14 % / 0 %, 85° off
    24 % / 76 %. 0.1 m would keep more (100 %, 94 %, 54 % in the translucent
    route) but visibly flattens the leaf-on-leaf contact shadows of a close-up,
    so the parts keep the app's value; `materials.shadow_bias(ob, metres)`
    changes one part. `blender/tests/trees2/glow_silhouette.py` measures both
    routes on cards in linear light and renders the meadow oak in each.
- Joshua fronds: the green → dry → driest texture ramp by distance from the
  nearest green crown, with the frond tints and dryness, and the JS's dim frond
  backlight (0.2 / 8 / 1.2 / 0.03). The mobile ladder's thatch bark blends the
  trunk bark into the dead-leaf thatch from 0.6 m to 1.1 m up the plant.
- Saguaro: clean ↔ damaged skin through the JS's own mask,
  `mx_fractal_noise_float` (3 octaves) of the world position in three's axes.
  Blender's raw fBm Noise Texture computes the same noise. Damage zones are
  soft patches about 2 m apart. At the default Bark damage (0.35), seed 3
  scars 6.5% of its skin, low on the column. Also a crest tint, and the
  gold-backlit spine areoles on the rib crests (the JS spine backlight: 0.35 /
  5 / 2.5 / 0.03).
- Fruit (apple, cherry): the baked GLBs as authored, with metallic 0 and the
  roughness map at factor 1. Fruit is hung from the fruiting wood with
  anti-clip rejection. Pass `fruit=False` to leave it off. The imported fruit
  material is cached per file, so a film may grow orchards in several fresh
  files in one Blender session. The card bakes carry the fruit, so an orchard
  tree keeps its apples on LOD2.
- Branch cards: the baked albedo and roughness, alpha test 0.35, the canopy
  dome plus 0.45 × the baked world-normal detail, the leaves' backlight with the
  baked translucency × a per-card thickness.
- Billboard: the baked albedo and roughness, a dome around the card centre
  dropped 0.55 × the card height (no normal points down, so the trunk base is
  never black) plus 0.55 × the baked detail, and only the app's flat ambient
  scatter (0.16 × 0.7 × translucency × the species transmit): no directional
  backlit bloom on a flat far card, and no specular (see Far trees). The
  scatter follows the plant's backlight route, so the switch keeps the leaves'
  brightness: in `'translucent'` it reaches the card's far side as the leaves'
  does, in `'glow'` it is the JS term exactly, the sun's unshadowed light on
  every side (the card receives no shadow). The Joshua tree, the yuccas and
  the saguaro scatter their own fronds' or spines' colour at their 0.03 floor;
  the app gives their billboards the broadleaf green at 0.16, since they have no
  foliage transmit. The bake
  turns the normals of thin cut-out parts (leaves, fronds, spines) away from the
  plant's centre, so the detail of the leaves facing a bake camera leans toward
  it, as their visible side does, and both cards bake the same normal where they
  cross (the raw sign is only the generator's winding: the Joshua tree's leaned
  away, and its billboard lit up under a sun behind it). At render the detail
  turns with the card (a rotated plant, a grove slot's yaw; the app leaves it
  unturned) and mirrors across the card on its back face.

## Export (.glb)

`make_seed_tree.export_glb(tree, 'white_oak.glb')` writes the app's Download
.glb: a root (sunk by the plant's sink) with one `<Species>_LODn` node per level
(the app-only mobile rungs skipped, the parked mesh levels kept), each with
`_branches` (bark, spines) and one `_leaves` mesh that merges every instanced part
with one primitive per material and vertex normals bent 0.85 toward the canopy
dome (fruit keeps its own). The billboard exports as `billboard_front` /
`billboard_side`. `MSFT_lod` on the LOD0 node lists the other levels, with
`extras.MSFT_screencoverage` from the switch distances (the app's 50° reference
camera); leaf, card and spine materials carry `KHR_materials_diffuse_transmission`
with their translucency map. `materials='proxy'` is the headless JS export: two
flat colours and no extensions (the bark exports brown here; the JS painted it
leaf green, bug f).

## The app's scenes

- `make_seed_tree.demo_scene('whiteOak', seed=1)` builds the app's first screen:
  the biome's terrain ring (hills from the app's integer-hash noise, the
  grass / five-rock blend), its gradient sky with the sun glow and the app's
  sun and hemisphere light, scattered rocks and scree, fallen limbs of the
  species' bark, meadow grass or desert scrub, eight volumetric clouds, the
  tree with every level and its billboard switched by camera distance, the
  64-tree grove, the ring haze (a compositor pass), the ambient soundscape
  (wind bed + bird calls in the sequencer) and the camera framed as the app
  frames a species. `sun_az`, `sun_el`, `forest_count`, `haze`, `ao`, `audio`,
  `scale_ref` (the 1.8 m box), `autorotate` (a keyed orbit) and `frames` are
  the app's Environment and Camera folders. Desert species get the desert
  biome. The app's tone map, three's ACES at exposure 1.3, becomes AgX with
  its 'High Contrast' look at log2(1.3) + 0.23 stops: the same display values
  on a neutral ramp (mean difference 0.008; `seedthree.scene.tonemap.aces_view`).
  The app's sun colour is its HSL triple taken as linear, as three r184 does. `spom=True` is the app's optional parallax-occlusion terrain (its
  Environment toggle, off by default as in the app): the 48-step march and the
  12-step relief self-shadow, unrolled into shader nodes, with the app's depth,
  per-layer push and 22-90 m fade. At eye height on the desert floor its relief
  streaks into spikes, toward the horizon and in the foreground too (a grazing
  march with the app's constants: `minViewZ` 0.12, 48 layers, the desert pushes
  up to 1.4); keep it for higher or steeper views
  (`blender/tests/trees2/out/spom_*`). The march follows three's
  ParallaxOcclusion step for step (its tangent frame, layer count and
  refinement), but it has not been compared with the app's own render.
- The ring haze is a compositor pass over EEVEE's Position pass. The frame
  renders with a transparent film and the sky comes back from the Environment
  pass, so the haze mixes only the geometry's share of each pixel:
  `image × (1 − f) + haze × f × alpha + sky × (1 − alpha)`. Each pixel takes
  the factor of its own position, as the app fogs per fragment, so a leaf in
  front of hazed hills keeps its colour. The Position pass is not antialiased:
  where the image blends the hazed terrain rim into the sky, the pass can hold
  the sky's empty position, and only those pixels take their 2 px
  neighbourhood's factor (no dark rim line, no haze-coloured blocks on the
  leaves; `blender/tests/trees2/haze_edge_check.py`). With the haze off, the
  app's Distance fog toggle, `set_haze_enabled(scene, False)` gives the app's
  fallback, its classic range fog (`smoothstep(95, 300 m, view depth)` toward
  the sky's colour; desert 55-230 m). `set_fog_on(scene, False)` drops both.
  The demo's sky needs its compositor: do not switch compositing off.
- The soundscape lays the app's schedule over the shot: the biome's looping
  wind bed end to end (a linear 1.6 s fade under the master's 0.35 s approach)
  and a bird call every 6-18 s (desert 8-24 s), each a random variant at rate
  0.96-1.05, peak 0.06-0.14, panned ±0.7, with the JS's exponential fades keyed
  on every frame. A seeded RNG replaces `Math.random`, so the audio repeats run
  to run. Blender pans a mono strip equal-power (−3 dB per channel at the
  centre) where the app's unpanned bed plays at full level on both, so the bed
  strip carries √2. `blender/tests/trees2/ambience_mixdown.py` mixes a minute of
  each biome down to WAV and measures the bed level and every call.
- `make_seed_tree.example('reference_turntable', species='paperBirch', seed=1)`
  is the app's neutral reference turntable (`scripts/reference`): LOD0, wind
  off, a 47° camera fitted with a 12 % margin swinging from the left
  three-quarter to the right, against its flat 0xaeb9bf backdrop;
  `shot['probe_frames']` are the three it compares.
  `example('example_scene')` is the app's film hookup example (white oak seed 42
  under the shadow-ready sun, an orbiting camera; a plain ground and sky stand
  in for the film's own).

## Asset tools (`scripts/`)

The app's texture and audio tooling is `seedthree.tools`
(`make_seed_tree.tools()`), run in system Python (numpy, Pillow; ffmpeg for
audio): `python -m seedthree.tools <command> <args>` with the script's own name
and arguments, or the functions (`texture.derive_pbr`, `derive_height`,
`derive_translucency`, `derive_leaf_maps`, `derive_leaf_roughness`,
`derive_cactus_bark`, `derive_spine_translucency`, `derive_thatch_pbr`,
`make_seamless`, `dilate_alpha`, `apply_alpha`, `chroma_key`, `denoise`,
`check_tile`, `tile_preview`, `make_bark_guide`, `make_yucca_alpha`;
`codex.harvest_codex_image`; `audio.gen_wind`, `loop_wind`, `seamless_loop`).
Their outputs equal the scripts' bit for bit, libvips' blur included; a resize
stays within 2 levels. `gen_wind` needs a running ComfyUI with Stable Audio 3.

## Presets

- `oak['preset']` and `make_seed_tree.to_preset(species, seed, dials)` give the
  app's JSON. `make_seed_tree.save_preset(path, species, seed, dials)` writes
  `path`. Given a folder, it writes the app's file name in it,
  `<Name>_seed<N>.seedthree.json`, and returns the path.
  `make_seed_tree.load_preset(path)` returns `{species, seed, controls}`; pass
  `dials=controls` to grow it.
- Verified both ways. The app's own `fromPreset` + `generate` grows a
  Blender-saved preset with the same LOD triangle counts and dimensions. The
  app's `toPreset` writes it back unchanged.

## Under the hood

- `make_seed_tree.raw()` is `seedthree.api`. It also offers:
  - `generate()`: the plant as plain arrays, no Blender (three's Y-up frame,
    like the JS).
  - `get_schema()`, `default_controls()`, `skeleton()`.
- Measured parity with the JS (SeedThree-blender's `blender/tests/`):
  - 15 cases across every generator: oaks (default and dialled), maple, beech,
    dogwood, sycamore, apple and cherry with fruit, birch, pine, willow,
    Joshua, saguaro, creosote and blackbrush. The RNG stream is identical,
    skeletons agree to 1e-14, every mesh buffer is equal in float32 at all
    three LODs, triangle counts are equal. The one difference is in the welded
    desert meshes: where both diagonals of a quad are exactly equal, the split
    follows last-bit float noise, and the test proves every differing quad is
    such a tie.
  - 15 more cases for the ladder: the card and rosette-card bakes' framings
    (exact), card quads and willow sheets, per-card thickness, the desktop LOD2
    and the mobile LOD3 / LOD4 placements, every mobile ladder kind, the
    hangingSprays foliage mode.
  - The demo scene's scatter (terrain noise to 1e-12, rocks, limbs, grass,
    scrub, clouds, forest slots), the asset tools (37 checks), and the app's own
    unit tests for the ladder, card thinning, willow sheets and shrub fruit.
- The Blender side renders in `blender/tests/trees2/` (run them through the GPU
  slot; `run_batch.py` runs several in one Blender): `cards_lod_probe.py`
  (the card LOD2 and the billboard against LOD0 at 24 m and 70 m),
  `mobile_ladder.py`, `forest_export_lod.py` (the grove, the .glb and its
  re-import, distance switching), `glow_silhouette.py` (both backlight routes
  on cards in linear light, the meadow oak in each), `demo_scene.py`,
  `examples_probe.py`, `spom_probe.py`, `addon_gpu.py` (the add-on's bake,
  export and preview operators), `billboard_light_match.py` (LOD0, the card
  LOD2 and the billboard under a sun in front, beside and behind, and the grove
  of billboards), `haze_edge_check.py` (the haze pass at silhouettes and its
  range-fog fallback, against the frame without fog), `reopen_saved_demo.py`
  (a saved demo .blend reopened in a Blender that never loads the add-on,
  rendered at other frames: every driver a simple expression) and
  `ambience_mixdown.py` (no GPU: a minute of each biome's soundscape mixed down
  and measured).
- Cost: 30 ms to 1 s per plant in Python, and 0.3-2 s to build in Blender.
- The SeedThree add-on itself installs as a Blender 5.2 extension (validated,
  built, installed and grown from in a throwaway user folder by its
  `blender/tests/test_extension.py`). Its sidebar has the app's folders: the
  dials, Optimization / LODs (preview level, mobile target, distances, budgets,
  bakes), Environment (sun, haze, scale reference, parallax terrain, ambient
  occlusion, forest; Build demo scene; the toggles act on the scene at once, as
  in the app), Wind, Light, Camera (auto-rotate: a keyed orbit of the scene
  camera), Export (.glb, PNG) and Save & Load.

## Not yet ported

- The app's backlight look by default. The default route keeps the leaf's
  Lambert factor; the app's own term is the opt-in `'glow'` route, whose
  shader the GPU driver failed to link once under the shared machine's memory
  cap (see Materials).
- A card lit from behind more than ~45° off its normal keeps only part of its
  backlight in either route (see the shadow bias under Materials; in the glow
  route its shadow read is pushed along the sun's direction, nearly parallel
  to the card). In a backlit shot those cards are close to edge-on to the
  camera.
- The JS's glow from lamps other than the sun (it sums the term over every
  direct light). The glow route is built for the bound sun: other lamps also
  reach its reads, weighted by their angle to the sun (a lamp opposite the sun
  counts about 1.4 times, one at right angles subtracts), so grow lamp-lit
  plants with `'translucent'`. With no sun lamp bound, the glow is off.
- The GitHub fallback when no checkout is found (eidoverse's bridge imports the
  JS API from GitHub). The Blender edition finds a local SeedThree checkout
  with the `blender` branch, or says how to clone one.
- The demo scene's volumetric clouds as the app shows them. Their noise,
  places and sizes are the app's, and each cloud volume now carries the app's
  emission + absorption recipe (EEVEE drew the Geometry Nodes volumes with its
  default grey volume shader before, as dark smudges). But EEVEE 5.2 brings
  them to the frame at a few percent of their expected strength: close up, a
  core dense enough to read white adds about 1 % over the sky, and neither the
  volume range nor the slice count changed that. In the demo's skies they are
  close to invisible. Light a film's sky with the sky family instead.
