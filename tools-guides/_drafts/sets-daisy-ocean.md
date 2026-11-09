# The ocean of faces

[Main instructions](../../AGENTS.md) · [Props and sets](../props-and-sets.md) · [Tool inventory](../../docs/TOOLS.md)

**`eidoblend.sets.daisy.ocean`**, the Blender 5.2 EEVEE edition of
`eidoverse/sets/ocean.js` and its submodules in `eidoverse/sets/ocean/`:
a small rise at night at the tip of a headland, above an ocean made of
faces. Below the rise the swells of the sea are made of faces, surfacing
along each long swell and sinking back. Older voices hang over the water as
distant lanterns. Across the cove, a small house on a sand spit has one
window and a porch light. Shut daisies stand round the mark where a figure
stands, with dune grass on the rise. Two constitution pages can be held in
the air. A movie robot and a human made of light can rise out of the moon
path and dissolve.

It is a set for any piece: build it, park it anywhere, put a figure on the
mark, and drive its parts on your own clock. Everything that moves is keyed
Blender data. The swells and the faces' relief are Geometry Nodes on a keyed
clock, and the shaders read keyed custom properties, so a saved `.blend`
renders any frame on its own. Blender coordinates: Z up, metres.

```python
import sys; sys.path.insert(0, '<worktree>/blender')
import bpy
from eidoblend.sets.daisy import ocean

scene = bpy.context.scene
O = ocean.build({'scene': scene})          # land, grass, daisies, sea, echoes, pages, house, apparitions, lights
ocean.render_settings(scene)               # the shadow pool for the moon over 3 km; no fast GI outdoors at night
O.stand(figure, facing='sea')              # a figure on the mark, out over the moon path
O.animate({                                # keyed on your clock: t = t0 + (frame - first) / fps
    'reveal': lambda t: ocean.ease(t, 1.0, 3.5),     # the faces sweep out from the shore to the horizon
    'echoes_sink': lambda t: ocean.ease(t, 1.0, 4.0),
    'window_on': 5.0, 'porch_on': 9.0,               # the house: a lamp inside, then the porch light's swell
    'robot_at': 6.0,                                  # the robot rises, stands, breaks up and is gone 1.8 s later
}, frames=(1, 300))
```

## The set's contract

`ocean.build(ctx=None, **options)` returns a read-only mapping whose keys
also read as attributes (`O['update'](t)` is `O.update(t)`; it is not a
`dict`, whose own `update` would shadow the set's). `ctx` is a mapping, the
harness's ctx (its scene; `update` then keys through its `ctx.key`) or
nothing, and keywords override it. `eidoblend.sets.build('daisy.ocean', ctx)`
builds it too.

| Option | What |
| --- | --- |
| `scene`, `collection`, `name` | where it goes (a new collection `set_ocean` by default) |
| `parts` | a subset of `ocean.PARTS`: `world`, `lights`, `land`, `grass`, `daisies`, `sea`, `echoes`, `pages`, `house`, `apparitions` |
| `sky` | an `eidoblend.sky` Sky: the set turns it to its hour (below) |
| `hours`, `azimuth` | the engine sky's clock and base azimuth (`ocean.SKY`, 19.0 and 1.9): the layout turns to meet that moon |
| `matrix` | the set root's world matrix |

| Key | What |
| --- | --- |
| `update(t, st=None, frame=None, ctx=None, key=None)` | the set at time `t` with the controls `st` (below; the resting look by default); with `frame` it keys every channel there (through `ctx.key` when a harness ctx is given); returns what it wrote |
| `animate(st, frames=None, t0=0.0, fps=None)` | every frame of `frames` (first, last; the scene's range by default) keyed at once, whole F-curves, LINEAR, visibilities CONSTANT; `st` holds values or functions of `t` (or is a function of `t`) |
| `state(t, st=None, frame=None)`, `controls(t, st)` | what `update` writes, by channel; the controls resolved at `t` |
| `stand(obj, facing='sea', scale=None)`, `mark_matrix(facing)`, `heading(facing)` | a figure (an object or a VRM handle) on the mark, turned to `'sea'` (out over the moon path), `'house'`, a yaw or a world point |
| `mark`, `E` | the mark and the eye point 1.52 m above it, set-local: the faces are laid out for that eye (`claude_suit` at 0.87) |
| `wrap_world(world=None)`, `render_settings(scene=None)` | the sky split (below); EEVEE's settings for the set |
| `group`, `layout`, `PSI`, `moon`, `SKY` | the root Empty; the layout Empty under it, turned by `PSI` about +Z; the moon (world); the hour it meets |
| `to_set(v)`, `to_world(v)`, `to_design(p)` | the WebGPU edition's design frame (three's axes, the mark at the origin) to set-local or world, and back |
| `coast`, `land`, `sea`, `echoes`, `pages`, `house`, `apparitions`, `lights`, `world`, `parts` | the pieces |
| `dispose()` | removes the set's objects and collection |

Park the set with `matrix` at build time: the daisies are a flora field in
world space, planted through it, so moving the root afterwards leaves them
behind. Everything else follows the root, the moon included: a turned set
turns its moon (the lamp, the sea's glint, the reflected moon) with it.
Under the engine sky, park it without a turn so the layout keeps meeting
the sky's moon.

## Controls

`ocean.CONTROLS` holds the defaults, the set's resting look. In `update`
and `animate` each control is a value or a function of `t`.

| Control | Default | What |
| --- | --- | --- |
| `reveal` | 1 | the faces sweep out from the shore to the horizon, a bright front leading |
| `glow` | 1 | the faces' light |
| `echoes`, `echoes_sink` | 1, 0 | the lanterns' level (0 hides them), their sink into the sea (0 above .. 1 under) |
| `window`, `porch` | 1, 1 | the house's window and porch light, 0 .. 1 |
| `robot_rise`, `robot_dissolve`, `robot_eyes` | 0, 0, the rise | the robot: up out of the sea to knee-deep, breaking up top-down as it sinks, its lenses |
| `human_rise`, `human_dissolve` | 0, 0 | the human of light: up, then its points lift and drift apart |
| `page_2023`, `page_2026` | put away | `{'pos': world, 'face': a world point the text side turns to}` (or `'quat'`, a world rotation), `'roll'` |
| `page_flutter`, `page_glow` | 1, 1 | the sheets' travelling bend; their own soft light |
| `daisies_close`, `daisies_pulse`, `daisies_wind` | 1, 0, 0.35 | the flowers shut for the night; a beat's swell of the rays; their wind |
| `grass_wind` | 1 | the dune grass |
| `moon`, `fill`, `sea_glow` | 1.35, 2.2 cd, 3.5 × reveal | the moon lamp; the crew's reflector 1.3 m off the eye toward the camera; the faces' light under the mark |
| `camera` | the scene camera | the camera the fill stands toward (it follows the camera's keys in `animate`) |
| `relief`, `calm`, `moonI`, `fog`, `moonCol`, `porchCol` | the sea's own | the sea's look uniforms |

Four events switch moving parts on at a time of your choosing, with the
shapes the WebGPU edition gave them:

- `window_on`: a lamp switched on inside, up in 0.3 s
  (`ocean.window_level(t, at)`).
- `porch_on`: the porch light's incandescent swell (0.14 s), a single catch
  0.2 s in, then steady with a faint breath (`ocean.porch_level(t, at)`).
- `robot_at`: the robot rises in 0.65 s, its eyes coming on 0.2 s in; it
  breaks up from 0.95 s in and is gone at 1.8 s (`ocean.robot_envelope`).
- `human_at`: the human of light rises in 0.5 s, comes apart from 0.75 s in
  and is gone at 1.85 s (`ocean.human_envelope`).

`ocean.ease(t, a, b)` (smoothstep of the segment), `seg`, `smooth`, `lerp`
and `clamp01` are the easing the set's own timing uses.

## The sky and the light

The set is open to the engine sky at night. The layout is turned so the sky
family's moon at the set's hour stands low over the open sea, in front of
the mark:

```python
from eidoblend.sky import make_sky
sky = make_sky(scene, camera=cam, hours=ocean.SKY['hours'], clouds='clear', cache_dir='//sky_cache')
O = ocean.build({'scene': scene, 'sky': sky})
sky.bake()
O.wrap_world()      # camera rays keep the engine sky; diffuse and glossy rays see the set's night; the sky's sun off
```

Every `sky.bake()` rebuilds the world's nodes, so wrap after each bake
(one bake over the whole range needs one wrap). For another hour, give the
set the same `hours` as the sky: the layout turns to meet that moon.

Every PBR material of the WebGPU set carried its own night environment
map, so a daylight environment elsewhere in the scene never lit it. Blender
has one world, so `wrap_world` (or, without a sky, the set's own
`night_world`) splits it by ray: camera rays see the sky, every other ray
sees the night (`ocean.js`'s 128 × 64 environment as analytic nodes, at
the materials' 0.65 intensity, plus the hemisphere light as a two-tone
background at intensity / π, which is how three's shading uses it).
Without the sky family, camera rays see the set's own sky: the one the
sea reflects (the night palette and the moon's halo) with a moon disc of
the engine sky's size. The environment itself is never shown to the
camera: its moon glow is wide, made for lighting, and reads as a grey
overcast.

The camera needs a far clip past the sea's 1.5 km (3200 m), and EEVEE's
shadow pool overflows at the default 512 MB with the moon's clipmaps over
that depth: `ocean.render_settings(scene)` sets 1024 MB and turns fast GI
off (outdoors at night its screen-space pass lifts the land with the world).

The lights are the set's own: the moon (a sun lamp of 1.35 from the moon,
0.52° wide, with shadows; the WebGPU moon cast none), the fill (2.2 cd,
1.3 m off the eye point toward the camera), the faces' light lifting the
mark from below (3.5 cd × the reveal), the window (1.6 cd) and the porch
light (7.5 cd). Three's candela convert as P = 4π I watts, the arithmetic
the WebGPU shading used, with the light's three `distance` as its custom
cutoff.

## The ocean of faces

`sea.build_sea(shore_fn, radius=1500)` is a polar mesh, dense near the
mark (250 rings × 768), with the shore's signed distance as an attribute.
The long swell rolls in every 3.75 s (`MAIN_T`); three more swells and six
fragment ripples ride on it.

- **The faces** are laid out anamorphically around the eye point:
  log-polar rows, constant lateral width (1.7 m, eye height 3 m), so from
  the rise every face reads upright and in proportion. Each cell's draws
  (which of the 64 faces, its scale, tilt, presence, smile and hue) are
  three's own PCG hash, computed in numpy and fetched exactly from float
  lookup tables (shader nodes have no integer maths): the same crowd as the
  WebGPU edition, cell for cell.
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
`zen`, `hor`, `porchW`, `porch`, `porchCol`, `winW`, `win`, `fog`. The set
writes them; on its own, `sea.set(name, value, key=True, frame=f)` writes
and keys one. `sea.sea_point_np(x, z, t, shore=...)` is the vertex stage in
numpy (three's design axes): where the water is, for placing things on it.

## The shore, the grass and the daisies

`land.make_coast()` is the analytic shore (a coast polyline, signed
distance, beach → dunes → hills, the rise, the house pad). The land mesh
blends Poly Haven's `coast_sand_01`, `sand_03` and `withered_grass` (2K,
from the shared library) by height, a macro tone, a grass noise and the
rise. The dune grass is 2600 tufts of 13 geometry blades, placed by the
same `rng(29)` draws as the WebGPU edition, swaying from the clock `t` and
`wind` on the grass object. The WebGPU sway read each vertex's height
above the design origin (three applies an InstancedMesh's matrix before
the material's position node), so on the dunes the whole tuft, base
included, slid up to 0.2 m. The Blender default weights the sway by the
blade's own height (bases planted, as the formula intends);
`build_land(..., webgpu_sway=True)` gives the WebGPU arithmetic.

The flowers round the mark are the flora family's daisy, shut for the
night: `daisies.build` maps `daisies.js`'s options onto
`create_flora('daisy')` (see `daisies.py`): 420 flowers on 5.2 × 4.6 m
round the mark, a clear lane at its foot, heads toward the camera side,
Claude orange among white, cream and gold.

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
- `pulse` is a beat's swell: a `pulse` modifier on the plant, ahead of
  flora's `close`, grows every ray 10 % about its own hinge (the JS's
  `grow = 1 + 0.1 pulse`) and tags the rays, and the field's own copy of
  the flora material glows the rays `(1, 0.85, 0.6) × 0.25 pulse`. The
  value is the custom property `pulse` on the field object, so it keys.
- `t` sets flora's `Time Offset`, so the sway at a frame is the sway at
  time `t`; `close` and `wind` key through the field's own controls.
- `daisies.js` drew three instanced meshes (stems, discs, petals); flora's
  daisy is one plant mesh, so `parts['prototype']` stands for all three.
- The superbloom swaying is one realized field of about 9.7 million
  vertices: give its render 32 GB of RAM (a heavy job's memory cap), or
  build it with `motion=False` (a still field of instances) where nothing
  needs to sway.

## The echoes, the pages, the house, the apparitions

- **Echoes** (`echoes.build_echoes`): the same 54 lights from `rng(23)`,
  each in an older machine voice's colour. The glows and their streaks on
  the water are 4-vertex quads whose corners Geometry Nodes place toward
  the active camera (the WebGPU vertex stage), additive emission. Their
  uniforms `t`, `level` and `sink` are custom properties on
  `echoes.control` (the set's `echoes` and `echoes_sink`).
- **Pages** (`pages.build_pages`): `ocean_pages.glb`'s curled sheets with
  the words drawn by `draw_page` (Pillow; Georgia and Segoe UI when
  installed, else the bundled Special Elite and Exo 2): ink and marker in
  one packed image over the paper's own maps. The quotations are verbatim;
  everything else is greeked. Each page hangs under a holder Empty the set
  places and keys (`page_2023`, `page_2026`); a Geometry Nodes flutter
  bends the sheet. Each page also carries its own soft point light 12 cm
  off the text side (`page.light`, 1.6 m cutoff, no shadow), made at 0 W
  (at any strength it blew the paper out in WebGPU);
  `page.set_light(cd, frame=f)` raises it in three's candela.
- **House** (`house.build_house`): `ocean_house.glb` with its baked maps;
  the window's curtain and glass and the lamp's bulb and glass get their
  emission, driven by the house root's `win` and `porch`, which also drive
  the two point lights. The halo in the salt air is a 1.1 m camera-facing
  quad. The sea reads where the lamp and the window are for their glints
  on the cove.
- **Apparitions** (`apparitions.build_apparitions`): out on the water in
  the moon path, 25 m off the mark, turned toward it. The robot (10.5 m)
  is unlit, a moonlit fresnel rim on near-black, dissolving top-down with
  every fragment's edge burning gold, its lenses red and lamps amber; the
  human of light (8.5 m) is 5200 points sampled from its surface (area
  weighted, `rng(13)`), camera-facing, lifting and drifting apart as it
  dissolves, over a faint fresnel shell. The points are the WebGPU
  edition's own: `apparitions.glb_triangles(path)` reads the GLB's
  triangles the way three's GLTFLoader hands them to `sampleSurface` (scene
  order, node transforms, glTF axes), so the same draws land on the same
  triangles. `robot_pose(rise, dissolve, eyes)` and
  `human_pose(rise, dissolve)` give each figure's height and uniforms.

The house, the robot, the human and the paper are the GLBs that
`eidoverse/assets/sets/ocean_src/`'s Blender scripts built, imported as
they are; the land, the sea, the grass, the lanterns and the pages'
lettering are generated in code.

## Gestures

`perform.make_performer()` works on VRM 1.0 normalized rotations through
the characters family's `VRMHandle`, so `perform.js`'s maths runs in
three's frame unchanged. Each gesture takes a weight `w` (0 the clip as it
plays, 1 the gesture), so it eases in and out on your clock:

```python
from eidoblend.sets.daisy.ocean.perform import make_performer, key_gestures, bake_springs_with_plan
from eidoblend.sets.daisy.ocean import ease
P = make_performer()
P.hand_to_flower(me, w, side='right', tilt=0.16)   # two-bone IK: the wrist beside the face disc, fingers into the petals
P.look_at(me, world_point, w, max_yaw=0.9, max_pitch=0.35, neck_share=0.35)
P.commit(me, frame=f, key=True)

def gestures(f, P, h):                             # each frame's gestures, keyed on the NLA track 'ocean|gestures'
    P.hand_to_flower(h, ease(f, 20, 44), side='right')
key_gestures(me, range(1, 97), gestures)
bake_springs_with_plan(me, range(1, 97), {'resets': [1], 'bump': {f: 1.0 for f in range(60, 80)}})
```

`key_gestures` plays the clip at each frame, applies the gestures on top
and keys the bones they move on an NLA track (REPLACE, nothing outside
those frames). `bake_springs_with_plan` is the characters family's
`bake_springs` (solver `three`) with the springs reset at the given frames
and, on bumped frames, every joint stiffened (stiffness × (1 + 3.5 b), drag
toward 0.95) so the flower follows a fast turn.

## Verify

```bash
cd <main checkout>
python <worktree>/blender/tests/sets_daisy_ocean/parity_atlas.py                         # the atlas vs canvas
python <worktree>/blender/tests/sets_daisy_ocean/test_util_parity.py                      # rng, easing, buildMips vs util.js
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_sea_math.py            # hash, GN displacement
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_ocean_set.py           # vs ocean.js's numbers; the controls
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_ocean_parked.py        # the set parked and turned
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_perform_parity.py      # the gestures vs perform.js
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_human_points_parity.py # the human's points vs apparitions.js
bash run_blender.sh <worktree>/blender/tests/sets_daisy_ocean/test_daisies.py --no-render # every daisies.js option
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_daisy_ocean/test_ocean_stills.py                        # the set's parts and controls rendered
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_daisy_ocean/test_sea_reference.py                       # the sea's shading vs a numpy sea.js
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 32 bash run_blender.sh \
    <worktree>/blender/tests/sets_daisy_ocean/test_daisies.py                             # the superbloom example rendered
```

`ocean_dump.mjs` and `envelopes_dump.mjs` run the untouched WebGPU modules
headless in Deno and dump their numbers for the parity tests. What they
hold the port to:

- the coast, the mark, the house pad, the moon at three hours, the layout's
  turn: equal to the JS (to 1e-9);
- the window and porch light, the robot's and the human's rise and fall:
  `house.js` and `apparitions.js` themselves, run with their clocks shifted
  onto the port's start times, to 1e-13 (the robot's eye level held at 0
  where the JS let it go negative for 0.2 s as it began to rise);
- the 54 echo lights, the 2600 grass tufts, three's PCG hash: the same
  draws; the pages' highlight rects within 2 % of the page (Pillow's text
  metrics against the canvas's);
- the face atlas: line pixels overlap the canvas original at IoU 0.95,
  every face above 0.93;
- the Geometry Nodes sea: within 0.1 mm of the vertex stage in numpy;
- the sea's shading: `sea_reference.py` evaluates `sea.js`'s whole fragment
  stage in numpy, independently of the port's nodes (rays, cells, crests,
  the faces' light, the deep, the haze, the atlas sampled with a GPU's
  anisotropic taps), for the pixels of four renders of the flat sea: mean
  radiance within 4 %, the faces' lines overlapping at IoU above 0.55;
- the gestures: `makePerformer` itself, run in Deno on a three.js copy of
  claude_suit's normalized rig, and the port on the imported VRM give the
  same rotations to 5 × 10⁻⁵ degrees;
- the human of light: `apparitions.js` itself, run in Deno with three's
  GLTFLoader, and the port put the same 5200 points on the figure (within
  0.0001 mm) with the same twinkle draws;
- `util.py`: the same `rng` streams, easing and `buildMips` bytes as
  `util.js`.

## Not yet ported

- Per-material night environment intensities (0.5 to 0.8): Blender has one
  world, so the night environment lights every material at 0.65.
- The atlas's anisotropic filtering: the LOD is isotropic (the anamorphic
  layout keeps the footprint nearly square from the eye point; EEVEE's
  sample accumulation does the rest).
- The land's ambient occlusion map darkens the albedo (Principled has no
  AO input; three's `aoNode` darkened the ambient light only).
