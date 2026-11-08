# The ocean of faces (DAISY verse 3)

[Main instructions](../../AGENTS.md) · [Props and sets](../props-and-sets.md) · [Tool inventory](../../docs/TOOLS.md)

**`eidoblend.sets.daisy.ocean`**, the Blender 5.2 EEVEE edition of
`eidoverse/sets/ocean.js` and its submodules in `eidoverse/sets/ocean/`:
a small rise at night above an ocean made of faces. The claudesona stands
on the rise at the tip of a headland. Below her the swells of the sea are
made of faces, surfacing along each two-bar swell and sinking back. Echoes
of the older voices hang over the water like distant lights and sink into
it as the faces rise. Two constitution pages drift past (2023, then 2026).
A movie robot and a human made of light rise from the sea and dissolve.
Across the cove, a small house on a sand spit turns its porch light on at
"on", and on the last line she turns and looks into the lens.

Everything the WebGPU set animated is keyed Blender data: the swells and
the faces' relief are Geometry Nodes on a keyed clock, the shaders read
keyed custom properties, the cameras, her mark, her gestures and her
springs are F-curves and NLA tracks. A saved `.blend` renders any frame
on its own. Blender coordinates: Z up, metres; `u` is seconds since
verse 3 began (one bar is 1.875 s at 128 BPM, 18 bars, 33.75 s).

```python
import sys; sys.path.insert(0, '<worktree>/blender')
import bpy
from eidoblend.sets.daisy import ocean
from eidoblend.characters import load_vrm, play_vrma_default

scene = bpy.context.scene
scene.render.fps = 24                                # before loading clips
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
O = ocean.build({'scene': scene})                    # land, grass, daisies, sea, echoes, pages, house, apparitions, lights
me = load_vrm('claude_suit')                         # the claudesona; key_verse scales her to 0.87
play_vrma_default(me, 'idle')
O.key_verse(frame_start=1, vrm=me, camera_obj=cam, pulse=lambda u: kick(u))
```

`key_verse` is the conductor: for every frame of the verse it keys the
set's `update` (the reveal, the glow, the echoes, the pages, the house,
the apparitions, the fill and sea-glow lights), the camera (CONSTANT
across the ten cuts, so nothing interpolates over a cut), her mark
(CONSTANT across her yaw steps), her gestures and her springs. Keep the
scene's frame rate fixed before calling it.

## The set's contract

`ocean.build(ctx)` returns a read-only mapping whose keys also read as
attributes (`O['camera'](u)` is `O.camera(u)`; it is not a `dict`, whose
own `update` would shadow the set's):

| Key | What |
| --- | --- |
| `group`, `layout` | the set's root Empty and the layout Empty under it, turned by `PSI` about +Z so the moon stands where the design put it |
| `mark`, `mark_at(u)` | her mark, and `{'pos', 'yaw'}` at `u`: set-local, yaw about +Z with 0 facing −Y (the VRM's front); the yaw steps only on cuts |
| `camera(u, st=None)` | `{'pos', 'target', 'fov', 'shot'}`, set-local, vertical FOV in degrees; cuts on bar lines |
| `update(t, st, key=None, frame=None)` | the set at film time `t`, `st = {'u', 'pulse'}`; `key=True` (or the harness's `ctx.key`) keys every channel at `frame` |
| `state(t, st)` | what `update` writes, by channel, without writing it |
| `perform(u, vrm, cam_pos_world=None, frame=None, key=None)` | her gestures on top of the playing clip (below) |
| `key_verse(frame_start, fps, t0, u0, u1, vrm, camera_obj, pulse, springs, scale)` | the whole verse keyed (above) |
| `spring_plan(frames)` | the spring resets (the entry, every jump, every yaw step over 0.35 rad) and the flower's stiffening for the turn |
| `wrap_world(world=None)` | after a sky bake: the engine sky for camera rays, the set's night for every other ray |
| `shot(u)`, `pose23(u)`, `pose26(u)` | the design-frame staging (three's axes), as `ocean.js` computes it |
| `coast`, `land`, `sea`, `echoes`, `pages`, `house`, `apparitions`, `lights`, `world`, `parts` | the pieces |
| `E`, `focal`, `PSI`, `moon`, `to_set(v)`, `to_world(v)` | her face, the layout's turn, the moon (world), design → set-local / world |
| `SKY`, `BAR`, `dispose()` | `{'hours': 19.0, 'azimuth': 1.9}`, 1.875, removes the set's objects |

`ctx` takes `scene`, `collection`, `parts` (a subset of `ocean.PARTS`:
`world`, `lights`, `land`, `grass`, `daisies`, `sea`, `echoes`, `pages`,
`house`, `apparitions`), `sky` (an `eidoblend.sky` Sky), `matrix` (the
set root's world matrix) and `camera_obj`.

Park the set with `matrix` at build time: her flowers are a flora field in
world space, planted through it, so moving the root afterwards leaves them
behind. Everything else follows the root, the moon included: a turned set
turns its moon (the lamp, the sea's glint, the reflected moon) with it.
Under the engine sky, park it without a turn, as the WebGPU conductor did,
so the layout keeps meeting the sky's moon.

The beats, as the WebGPU guide listed them:

- **Bars 0–1:** alone on the rise.
- **Bars 2–3:** over her shoulder, craning up to reveal the sea of faces.
- **Bars 4–7:** the 2023 page drifts past (and an insert rides with it),
  then the 2026 page floats up in front of her face (she reads it over her
  shoulder; an insert reads its two highlighted lines).
- **Bars 8–9:** the robot rises, then the human of light.
- **Bars 10–11:** close, as her hand rises to her flower.
- **Bars 12–13:** the house across the cove; its window comes on with the
  kick at bar 12.
- **From bar 14:** the porch light comes on at "on" (u 28.13), and she ends
  looking into the lens.

## The sky and the light

The set is open to the engine sky at night. The layout is turned so the
sky family's moon at `SKY['hours']` stands low over the open sea, right
behind her:

```python
from eidoblend.sky import make_sky
sky = make_sky(scene, camera=cam, hours=ocean.SKY['hours'], clouds='clear', cache_dir='//sky_cache')
O = ocean.build({'scene': scene, 'sky': sky})
O.key_verse(frame_start=1, vrm=me, camera_obj=cam)
sky.bake()
O.wrap_world()      # camera rays keep the engine sky; diffuse and glossy rays see the set's night; the sky's sun off
```

Every `sky.bake()` rebuilds the world's nodes, so wrap after each bake
(one bake over the whole verse needs one wrap).

Every PBR material of the WebGPU set carried its own night environment
map, so the conductor's daylight environment never lit it. Blender has
one world, so `wrap_world` (or, without a sky, the set's own
`night_world`) splits it by ray: camera rays see the sky, every other ray
sees the night (`ocean.js`'s 128 × 64 environment as analytic nodes, at
the materials' 0.65 intensity, plus the hemisphere light as a two-tone
background at intensity / π, which is how three's shading uses it).
Without the sky family, camera rays see the set's own sky: the one the
sea reflects (the night palette and the moon's halo) with a moon disc of
the engine sky's size. The environment itself is never shown to the
camera: its moon glow is wide, made for lighting, and reads as a grey
overcast.

The camera needs a far clip past the sea's 1.5 km (`key_verse` sets
3200 m), and EEVEE's shadow pool overflows at the default 512 MB with the
moon's clipmaps over that depth: set `scene.eevee.shadow_pool_size =
'1024'`.

The lights are the set's own: the moon (a sun lamp of 1.35 from the moon,
0.52° wide, with shadows; the WebGPU moon cast none), a fill that follows
the shot 1.3 m off her face toward the camera (2.2 cd, 0.6 on the house
shots), the faces' light lifting her from below (3.5 cd × the reveal), the
window (1.6 cd) and the porch light (7.5 cd). Three's candela convert as
P = 4π I watts, the arithmetic the WebGPU shading used (the sky family keys
its sun with three's numbers unchanged too), with the light's three
`distance` as its custom cutoff.

## The ocean of faces

`sea.build_sea(shore_fn, radius=1500)` is a polar mesh, dense near her
(250 rings × 768), with the shore's signed distance as an attribute. The
long swell has a period of exactly two bars, so every sung line is one
swell rolling in. Three more swells and six fragment ripples ride on it.

- **The faces** are laid out anamorphically around her eye point:
  log-polar rows, constant lateral width (1.7 m, eye height 3 m), so from
  the rise every face reads upright and in proportion. Each cell's draws
  (which of the 64 faces, its scale, tilt, presence, smile and hue) are
  three's own PCG hash, computed in numpy and fetched exactly from float
  lookup tables (shader nodes have no integer maths): the same crowd as
  the film, cell for cell.
- **The relief** (fifteen Gaussians of brow, lids, nose, lips and chin over
  a dome) rises out of the water where a crest runs through a face, in
  Geometry Nodes, so motion blur and the velocity pass see it. Its
  gradient bends the shading normal in the material.
- **The lines** come from the 8 × 8 atlas of brush-line portraits
  (`faces_atlas.draw_face_atlas`, Pillow, the same people stroke for
  stroke as the canvas original). The WebGPU edition sampled it with
  explicit gradients so the fract()'d cell coordinates never picked a wrong
  mip at a cell border. Blender's Linear sampling takes screen derivatives
  of the uv, which jump at every cell border, so the atlas is a mip chain
  of separate images sampled with Cubic (four `textureLod(0)` taps, no
  derivatives), blended at an LOD computed from the same analytic
  gradients and the camera's angle per pixel (a driver reads the scene
  camera's vertical angle and the render height).
- **The material** is unlit, as the WebGPU `MeshBasicNodeMaterial` was: the
  night sky by Fresnel, the moon's halo and disc glint, the near-black
  water body, the faces' light rising through the surface (gold, amber,
  rose and now and then aqua), the reveal's bright front, the deep (older,
  larger faces far below, parallax-shifted, blurred, cold), the porch and
  window glints, the waterline foam and the haze.

Its uniforms are custom properties on the sea object (`sea.mesh`):
`t`, `reveal`, `glow`, `relief`, `calm`, `moonW`, `moonCol`, `moonI`,
`zen`, `hor`, `porchW`, `porch`, `porchCol`, `winW`, `win`, `fog`.
`sea.set(name, value, key=True, frame=f)` writes and keys one.
`sea.sea_point_np(x, z, t, shore=...)` is the vertex stage in numpy (three's
design axes): where the water is, for placing things on it.

## The shore, the grass and her flowers

`land.make_coast()` is the analytic shore (a coast polyline, signed
distance, beach → dunes → hills, her rise, the house pad). The land mesh
blends Poly Haven's `coast_sand_01`, `sand_03` and `withered_grass` (2K,
from the shared library) by height, a macro tone, a grass noise and her
rise. The dune grass is 2600 tufts of 13 geometry blades, placed by the
same `rng(29)` draws as the film, swaying from the clock `t` on the grass
object. The film's sway read each vertex's height above the design origin
(three applies an InstancedMesh's matrix before the material's position
node), so on the dunes the whole tuft, base included, slid up to 0.2 m.
The Blender default weights the sway by the blade's own height (bases
planted, as the formula intends); `build_land(..., webgpu_sway=True)`
gives the film's arithmetic.

Her flowers are the flora family's daisy, shut for the night:
`daisies.build` maps `daisies.js`'s options onto `create_flora('daisy')`
(see `daisies.py`): 420 flowers on 5.2 × 4.6 m around her, a clear lane at
her feet, heads toward the camera side, Claude orange among white, cream
and gold.

`daisies.py` is the whole of `daisies.js`, usable on its own. Its header
example, a superbloom of 14000 daisies on 60 × 60 m with a path cleared
across it, is `daisies.EXAMPLES['superbloom']`:

```python
from eidoblend.sets.daisy.ocean import daisies
bloom = daisies.build_example('superbloom', wind=0.6)    # on a gentle meadow swell (daisies.meadow_height)
bloom.update(t, {'close': 0.0, 'pulse': 0.0, 'wind': 1.0}, frame=f)
mine = daisies.build(count=600, width=6, depth=6, palette=[[0.85, 0.47, 0.34, 0.7], [0.98, 0.8, 0.32, 0.3]])
```

- `palette` (`[[r, g, b, weight], ...]`, sRGB) becomes flora's colour mix
  `{(r, g, b): weight}`; the default palette is flora's named mix (white
  keeps the modelled art).
- `pulse` is the kick: a `pulse` modifier on the plant, ahead of flora's
  `close`, grows every ray 10 % about its own hinge (the JS's
  `grow = 1 + 0.1 pulse`) and tags the rays, and the field's own copy of
  the flora material glows the rays `(1, 0.85, 0.6) × 0.25 pulse`. The
  value is the custom property `pulse` on the field object, so it keys.
- `t` sets flora's `Time Offset`, so the sway at a frame is the sway at
  film time `t`; `close` and `wind` key through the field's own controls.
- `daisies.js` drew three instanced meshes (stems, discs, petals); flora's
  daisy is one plant mesh, so `parts['prototype']` stands for all three.

## The echoes, the pages, the house, the apparitions

- **Echoes** (`echoes.build_echoes`): the same 54 lights from `rng(23)`,
  each in an older machine voice's colour. The glows and their streaks on
  the water are 4-vertex quads whose corners Geometry Nodes place toward
  the active camera (the WebGPU vertex stage), additive emission. Their
  uniforms `t`, `level` and `sink` are custom properties on
  `echoes.control`.
- **Pages** (`pages.build_pages`): `ocean_pages.glb`'s curled sheets with
  the words drawn by `draw_page` (Pillow; Georgia and Segoe UI when
  installed, else the bundled Special Elite and Exo 2): ink and marker in
  one packed image over the paper's own maps. The quotations are verbatim;
  everything else is greeked. Each page hangs under a holder Empty the set
  keys; a Geometry Nodes flutter bends the sheet. Each page also carries
  its own soft point light 12 cm off the text side (`page.light`, 1.6 m
  cutoff, no shadow), made at 0 W because `ocean.js` keeps it there (at
  any strength it blew the paper out); `page.set_light(cd, frame=f)` raises
  it in three's candela.
- **House** (`house.build_house`): `ocean_house.glb` with its baked maps;
  the window's curtain and glass and the lamp's bulb and glass get their
  emission, driven by the house root's `win` and `porch`, which also drive
  the two point lights. The halo in the salt air is a 1.1 m camera-facing
  quad.
- **Apparitions** (`apparitions.build_apparitions`): the robot (10.5 m)
  is unlit, a moonlit fresnel rim on near-black, dissolving top-down with
  every fragment's edge burning gold, its lenses red and lamps amber; the
  human of light (8.5 m) is 5200 points sampled from its surface (area
  weighted, `rng(13)`), camera-facing, lifting and drifting apart as it
  dissolves, over a faint fresnel shell. The points are the film's own:
  `apparitions.glb_triangles(path)` reads the GLB's triangles the way
  three's GLTFLoader hands them to `sampleSurface` (scene order, node
  transforms, glTF axes), so the same draws land on the same triangles.

## Her gestures

`perform.make_performer()` works on VRM 1.0 normalized rotations through
the characters family's `VRMHandle`, so `perform.js`'s maths runs in
three's frame unchanged:

```python
from eidoblend.sets.daisy.ocean.perform import make_performer
P = make_performer()
P.hand_to_flower(me, w, side='right', tilt=0.16)   # two-bone IK: the wrist beside the face disc, fingers into the petals
P.look_at(me, world_point, w, max_yaw=0.9, max_pitch=0.35, neck_share=0.35)
P.commit(me, frame=f, key=True)
```

`O.perform(u, me)` runs the verse's three: she reads the 2026 page
(u 11.25–15), her hand rises to her flower (u 18.75–22.5), and she turns
to the lens (from u 30). `key_verse` bakes them on an NLA track,
`ocean|perform` (REPLACE, nothing outside the verse), then her springs
(the characters family's `bake_springs`, solver `three`) with the set's
resets and, for the turn, every joint stiffened (stiffness × (1 + 3.5 b),
drag toward 0.95) so the petals follow her.

## Verify

```bash
cd <main checkout>
python <worktree>/blender/tests/sets_daisy_ocean/parity_atlas.py                         # the atlas vs canvas
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_sea_math.py            # hash, GN displacement
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_ocean_staging.py       # vs ocean.js's numbers
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_perform_parity.py      # her gestures vs perform.js
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_human_points_parity.py # the human's points vs apparitions.js
python <worktree>/blender/tests/sets_daisy_ocean/test_util_parity.py                      # rng, easing, buildMips vs util.js
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_daisies.py --no-render # every daisies.js option
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_ocean_parked.py        # the set parked and turned
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_daisy_ocean/test_ocean_shots.py                         # the film's shots (the set's night)
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_daisy_ocean/test_ocean_sky.py                           # the same shots under the engine sky
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_daisy_ocean/test_ocean_views.py                         # the saved .blend reopened + views
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_daisy_ocean/test_daisies.py                             # the superbloom example rendered
```

`ocean_dump.mjs` runs the untouched WebGPU set headless in Deno and
dumps its numbers (the coast, the moon, every camera and mark through the
verse, the pages' flights, the echoes, the grass, three's hash) for the
parity tests. What they hold the port to:

- the coast, her mark, the house pad, the moon, the layout's turn, her
  facing, the pages' flights, the reveal, glow and echo levels: equal to
  the JS (to 1e-9);
- the cameras: within 0.4 mm (the two inserts ride the page highlight,
  whose rects come from Pillow's text metrics instead of the canvas's,
  within 2 % of the page);
- the 54 echo lights, the 2600 grass tufts, three's PCG hash: the same
  draws;
- the face atlas: line pixels overlap the canvas original at IoU 0.95,
  every face above 0.93;
- the Geometry Nodes sea: within 0.1 mm of the vertex stage in numpy;
- her gestures: `makePerformer` itself, run in Deno on a three.js copy of
  claude_suit's normalized rig, and the port on the imported VRM give the
  same rotations to 5 × 10⁻⁵ degrees (`test_perform_parity.py`); on the
  keyed verse the wrist rises to 0.27 m from her head, she reads the 2026
  page within 1.4° and looks into the lens within 0.2°;
- the human of light: `apparitions.js` itself, run in Deno with three's
  GLTFLoader, and the port put the same 5200 points on the figure (within
  0.0001 mm) with the same twinkle draws;
- `util.py`: the same `rng` streams, easing and `buildMips` bytes as
  `util.js`.

## Not yet ported

- Per-material night environment intensities (0.5 to 0.8): Blender has one
  world, so the night environment lights every material at 0.65.
- The atlas's anisotropic filtering: the LOD is isotropic (the anamorphic
  layout keeps the footprint nearly square from her eye point).
- The land's ambient occlusion map darkens the albedo (Principled has no
  AO input; three's `aoNode` darkened the ambient light only).
