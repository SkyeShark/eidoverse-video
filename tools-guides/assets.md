# Sourcing assets — models, HDRIs, textures, kits

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

The fetch tools help find reusable models, environments and surface maps.
They can save substantial work on a realistic setting. Inspect candidates for
the scene you are making; reuse, kitbashing and original geometry are all part
of the studio. Search ranking does not establish visual suitability or license
compatibility with a particular redistribution; for a downloaded model, read
its [licence sidecar](#fetch_modelpy--meshes-from-everywhere-at-once) before
redistributing.

The fetchers are plain Python CLIs, the same in every edition. They write
their downloads into the **current directory**, so run them from the piece's
folder (paths below assume `work/<id>/`, two levels under the repo root).
In the scene, `eidoblend.harness.assets` loads what they fetched into Blender.

## `fetch_model.py` — meshes from everywhere at once

```bash
cd work/<id>
python ../../fetch_model.py "search terms" --theme "your piece's mood/setting"
```

Searches local custom models + Poly Haven + Smithsonian + NASA + NIH 3D all
at once, ranks every candidate across all sources, and delivers the best one
(printing the runners-up from every source). Read the `_preview.jpg` before
placing: it shows orientation and scale via visible features and coloured
axis labels.

- **Render the preview in Blender, in Blender's words.** `fetch_model.py`
  still draws its `_preview.jpg` with three.js (Y up). On this branch render
  it from the model as Blender imports it:

  ```bash
  bash run_blender.sh blender/eidoblend/harness/model_preview.py work/<id>/model.glb [more models] [--out DIR]
  ```

  The preview shows the model in EEVEE under a three-point rig, a yellow
  bounding-box wireframe and a ground grid, the axes from the box centre with
  their face labels (red X, green Y, blue **+Z up**; the dimmer rays are -X
  and -Y) and a title plate with the size X x Y x Z. It prints the lines
  `fetch_model.py` relays: `[PREVIEW_BBOX]` (glTF order, for its catalogue),
  `[PREVIEW_BBOX_BLENDER] X Y Z`, `[ORIGIN_INFO]` in Z-up words
  (**BASE**: z = 0 is the model's bottom, it rests directly on a surface;
  **CENTERED**, **TOP**, **OUTSIDE** or **OFFSET**) and `[KIT_INFO]` (below).
  Without `--out` the preview lands beside the model as `<name>_preview.jpg`,
  where `fetch_model.py` puts it (the local catalogue's committed previews
  are three.js renders: write elsewhere unless you mean to replace one).
  `assets.rest_on` and the placement family's `place_on` seat the geometry's
  bounds regardless of pivot.
- **`--theme` tunes the pick to your video**: e.g. `fetch_model.py "car"
  --theme "cyberpunk neon dystopia"`. An embedding model scores each
  candidate against your setting by meaning, so paraphrases, mood words and
  eras work. Inspect the result; rankings can still miss the intended object.
  *(Any OpenAI-compatible `/v1/embeddings` endpoint via
  `EIDOVERSE_EMBED_URL`/`EIDOVERSE_EMBED_MODEL`/`EIDOVERSE_EMBED_KEY`,
  defaulting to Jina's free tier via `JINA_AI_KEY`; with no key it degrades
  to relevance-only.)*
- **Local models are referenced in place.** When the match is local,
  fetch_model prints `Local model (referenced IN PLACE — not copied):
  <absolute path>`: put that exact path into `scene.json` `assets`.
  Downloaded models land in the current directory with their `_preview.jpg`:
  a Poly Haven model as `<model_id>_embedded.gltf` (textures inlined), a
  Smithsonian, NIH 3D or NASA model as `<name>.glb`. Browse the local catalog
  with `python fetch_model.py --list-local` (from the repo root).
- **Every download writes a licence sidecar** beside the model:
  `<model file stem>.license.json`, recording `source`, `file`, `id`, `url`,
  `license`, `license_url`, title/author where the source exposes them, and
  the fetch date. Poly Haven is `CC0-1.0`; Smithsonian entries are marked
  `unverified` (CC0 only when the object page says Open Access); NIH 3D
  licences vary per submission; NASA carries the NASA media usage guidelines.
- **The alternatives are printed for a reason.** If the preview isn't the
  variant you wanted, re-fetch a specific one by its name/id:
  `fetch_model.py "server_rack_01"`.
- **Cache and reuse.** Downloading the same model twice in one session means
  the first copy wasn't tracked: keep and reference it.

## `fetch_hdri.py` — environment light for lookdev

```bash
python ../../fetch_hdri.py "search" [resolution]
```

Searches Poly Haven + AmbientCG and writes `hdri.hdr` (or `hdri.exr`, which
Blender reads just as well; the `hdri_b64.txt` sidecar is for the WebGPU
edition only). In Blender:

```python
assets.load_hdri(ctx.assets['hdri'], strength=1.0, rotation_deg=90, visible=False)
```

`load_hdri` makes the scene's World from it: for lookdev, product shots and
studio light. A set that needs a **sky** uses the sky family's `make_sky`,
never a photograph of one. `visible=False` lights the scene while the camera
sees a black background.

## `fetch_texture.py` — PBR sets

```bash
python ../../fetch_texture.py "material" [resolution]
```

Basecolor + roughness + normal + AO + metalness + displacement, from Poly
Haven + AmbientCG + TextureCan (all CC0). Without `--cache` it writes
`tex_urls.json` in the current directory (Poly Haven entries are CDN URLs;
AmbientCG/TextureCan maps are extracted beside it). For scenes, prefer the
shared library below: it downloads every map and `load_pbr` wires them.
Any single image loads with

```python
img = assets.load_image_texture(ctx.assets['poster'], srgb=True)    # colour; srgb=False for data maps
```

(screen content, decals, logos, sprite sheets). Brand or logo art reads
on-brand from a real transparent PNG declared as an asset; a hand-rolled
procedural approximation of a logo does not.

### The shared library — library code names IDs, never commits them

Third-party CC0 sets are fetched, never committed. Code that ships in the
repository names the exact IDs it reads, and the shared library fetches each
one once into `eidoverse/assets/cache/` (git-ignored):

```bash
python fetch_texture.py Concrete031 1k --cache          # -> eidoverse/assets/cache/textures/Concrete031_1k/
python fetch_model.py metal_trash_can --cache --res 2k  # -> eidoverse/assets/cache/models/metal_trash_can_2k/
```

In a scene:

```python
from eidoblend.harness import assets

s = assets.fetch_pbr('Concrete031', res='1k')        # {'dir', 'files': {'diff', 'normal', 'rough', 'ao', ...}}
floor_mat = assets.load_pbr('WoodFloor064', res='2k', maps=('diff', 'normal', 'rough'), repeat=(0.5, 0.5))
floor.data.materials.append(floor_mat)
path = assets.fetch_model_file('wooden_stool_01', res='1k')   # the .gltf path; import it below
```

`load_pbr` builds a Principled BSDF material from the maps you name, and only
those (a set that later gains a map must not change a look tuned without it):

| Map | Wired to |
| --- | --- |
| `diff` | Base Color (sRGB) |
| `rough`, `metal` | Roughness, Metallic (Non-Color) |
| `normal` | a Normal Map node (OpenGL convention, as fetched); `normal_dx` flips green first |
| `arm` | Separate Color: G roughness, B metallic |
| `opacity` | Alpha (the material renders dithered) |
| `emissive` | Emission Color, strength 1 |
| `displacement` | a Bump node (`displacement='true'` for real displacement on dense geometry) |
| `ao` | not wired: EEVEE's ray-traced and fast GI make the occlusion |

`repeat=(u, v)` tiles the maps across the object's UVs. Give a surface you
build real-world UVs (one unit per metre) and `repeat` is tiles per metre.
Each fetch runs the fetcher on first use, so a fresh clone renders without a
setup step. Offline, or with `EIDO_NO_FETCH=1`, a missing ID raises with the
one-line fetch command. `EIDO_ASSET_CACHE` points the library at another
folder (another checkout's `eidoverse/assets/cache`). Models you build
yourself are not third-party: they go in `eidoverse/assets/models/` as
`<set>_<name>.glb`, where `fetch_model.py --list-local` finds them.

## Importing models in the scene

```python
stool = assets.import_model(assets.fetch_model_file('wooden_stool_01', res='1k'), name='stool')
assets.rest_on(stool, 0.0, xy=(0.0, 0.55))            # its geometry's bottom on z = 0, centred at (x, y)
stool.rotation_euler.z = math.radians(18)
clock = assets.import_model(ctx.assets['clock'], name='clock')
assets.rest_on(clock, assets.bounds(stool)[1].z)       # on the stool's top
```

`import_model` reads `.glb`/`.gltf` (and `.fbx`, `.obj`) into a collection of
its own, under one Empty that it returns; move, turn and scale that Empty.
The Empty carries the file's path as `eido_src_asset` (the audits group a
model's meshes into one body by it). glTF's +Y up becomes Blender's +Z up:
a model whose nose points along glTF +Z faces Blender -Y.

Models come pre-materialed: their authored UVs, materials, rigs and clips
are the look. The importer repairs only what an export lost, and logs each
repair:

- **Alpha and transmission** materials get shadows that let light through
  (EEVEE's default shadow is opaque, which puts whatever is behind a glass or
  a leaf card in full shade) and ray-traced refraction.
- **Glass shipped opaque.** A material named glass that is alpha-blended
  through a texture with no alpha (a JPEG; Poly Haven's glTF exports ship
  their glass this way) renders as an opaque disc. It becomes clear thin
  glass with `make_glass`, so a clock dial behind it shows.
  `fix_glass=False` keeps materials exactly as shipped. Call
  `assets.make_glass(material, refract=True)` yourself for thick glass whose
  subject sits well behind it (a window onto a room, a bottle): EEVEE's
  screen-space refraction loses things a few millimetres behind a pane.

**Real-world scale is the default.** A fetched stool is 0.44 m tall, a chair
about 1 m, a car about 4.5 m. Prominence comes from the camera (move closer,
lower the field of view) or from positioning; inflating a mesh makes everything
around it read as miniature. Correct unit mismatches first: a pipeline that
authored in centimetres ships at 100x (a "laptop" 30 m wide wants
`root.scale = (0.01,) * 3`). `assets.bounds(root)` gives its world box.

## Embedded animations — play what ships

Many fetched models (robot arms, machines, doors, rigged props) carry their
own clips. The glTF importer makes one action per clip, assigns the first and
stashes the rest as muted NLA tracks. Playing a shipped clip beats keying the
mesh by hand:

```python
crow = assets.import_model(ctx.assets['crow'], name='crow')
assets.play_model_animations(crow, clip='Peck')                  # a name, an index, or 'all'
print(sorted(assets.model_clips(crow)))                          # every clip the file has
```

The clip plays as an NLA strip from `start` (default the first frame) to
`end` (default the last), repeated to fill it; `speed` scales it and `offset`
(seconds) starts it mid-cycle. It keeps three's clock: a clip starts at time
0 even when its first key is later (a Blender export keys from frame 1, 1/24 s
in), holds its first pose until then, and loops on its last key's time, so
it plays frame for frame as it did in the WebGPU edition. It is keyed data in
the build, so every frame renders the same, jumped to or not. If a model has
no embedded animations, the log says so: that's the cue to animate it by hand.

Clips keep each file's own names, as three kept `gltf.animations`: Blender
makes action names unique across the file, so the wren imported after the crow
gets actions called `Walk.001`, but `model_clips(wren)` and
`play_model_animations(wren, clip='Walk')` still say `Walk` (the import stamps
each action's clip name). `clip=<index>` counts in the file's order, which the
import records, so it names the same clip after any number of plays.

`clip='all'` plays every clip at once as three's `AnimationMixer` did, each at
a weight (1 unless `weights` gives `{clip: weight}` or a list in name order;
a clip left out of the dict plays at 1, as three played every action): on
each animated property, the weighted mean of the clips that animate it
(rotations by slerp, chained in the file's clip order as the mixer activated
them), with the rest pose filling in when a property's weights sum to less
than 1, so a lone clip at 0.5 plays half way out of the rest pose. The mix is
baked into one LINEAR action per animated object (not itself a clip: it never
shows in `model_clips`). Clips on different bones layer in full; clips on the
same bones average, so `'all'` is for clips made to layer:

```python
assets.play_model_animations(robot, clip='all', weights={'base_turn': 1.0, 'grip': 1.0, 'idle_sway': 0.3})
weights = {c: 0.0 for c in assets.model_clips(crow)}
weights.update({'Walk': 1.0, 'Caw': 0.7})                # a crow that caws as it walks: two clips, every other at 0
assets.play_model_animations(crow, clip='all', weights=weights)
```

(Measured against three's own mixer on the same GLB, on a three-bone rig: two
clips sharing a bone at weights 1 / 1 and 1 / 0.5, and three clips on one bone
in a file whose clip order is not alphabetical, agree to under a micrometre at
13 times; three itself moves those joints 7 mm if the three play in name
order instead.)

**Duplicating a rigged model: `clone_model`.** A plain object copy of a
skinned model would share its rig, so every copy moves as one.
`assets.clone_model(root, name, location)` copies the rig (each copy poses and
animates on its own) and shares the mesh data; armature modifiers and
parenting point at the copies. Play a different clip or offset on each:

```python
crow2 = assets.clone_model(crow, name='crow2', location=(0.75, 0.55, 0))
assets.play_model_animations(crow2, clip='Caw', offset=0.4)     # never in unison with the first
```

The copies share the clips' actions, which is all that playing different
clips or offsets needs. To edit one copy's keys without touching the other,
give it its own: `clone_model(crow, name='crow3', independent_actions=True)`
copies every action the clone carries (`<action>.crow3`, listed in its
`eido_own_actions`); the copy still plays them by the clips' own names
(`play_model_animations(crow3, clip='Peck')` plays `Peck.crow3`). A clone's
strips keep their source's range and timing, and a clip that keys several of
a model's objects (one action, a slot per object) plays on a clone too: each
copy carries its original's name (`eido_clone_of`) to find its slot.

## The animated birds — crow & cactus wren

Two purpose-built, fully-clipped bird assets in `eidoverse/assets/models/`,
each one skinned mesh with named clips for `play_model_animations`:

| model | clips | size L×H×W |
|---|---|---|
| `crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb` | `Idle` `Walk` `Hop` `Peck` `Fly` `Caw` `Talk` `TurnL` `TurnR` | 0.77 × 0.52 × 0.88 m |
| `cactus_wren_bird_animated_desert_songbird_calling_hopping_walking.glb` | `Idle` `Walk` `Hop` `Peck` `Fly` `Call` `TurnL` `TurnR` | 0.19 × 0.13 × 0.22 m |

Both drop straight in: feet at the origin, real-world scale, nose along glTF
+Z, so a bird at rotation 0 faces Blender -Y (registered in
`_forward_axes.json`). `Walk`/`Hop` are in-place cycles: key the body forward
yourself or the bird moonwalks. `Fly` is a level cruise: pitch the model for
climbs and dives. For a flock, `clone_model` each bird and give each an
`offset`. [The pipeline's T5 test](../blender/tests/pipeline/crows/scene.py)
is a working pair.

Paired call audio, pre-aligned to the clips, in `eidoverse/assets/audio/`:
`crow_caw_clip_synced.wav` (1.60 s, two caws on the `Caw` clip's two gape
peaks; start both together), `cactus_wren_call_clip_synced.wav` (2.40 s, the
`Call` clip bobs on all 12 note onsets), `crow_caw_single.wav` (one caw for
scattered background use). The caws are our own Stable Audio generations,
CC0: regenerate with `generate_sfx.py` for variants; a real crow caw puts
~70–80% of its energy in 0.8–2 kHz, so a generation landing above 5 kHz is
hiss rather than bird.

## Kits — models that are catalogs of parts

Many fetched models are kits (modular building kits, pipe kits, plant packs):
a catalog of parts laid out in a row, not one finished object. `fetch_model.py`
prints a `[KIT_INFO]` line on delivery (`LIKELY A MODULAR KIT` for obvious
ones, a neutral part count for ambiguous ones). Read it with the preview.

```python
kit = assets.load_kit(ctx.assets['pipe_kit'])     # or load_kit(root) for a model already imported
kit.list()                                        # ['pipe_elbow_01', 'pipe_valve_03', ...]  (kit.names: file order)
elbow = kit.get('pipe_elbow_01', location=(2, 0, 0), rotation_z=math.radians(90))
first = kit.part(0)                               # by catalogue position
valves = kit.family('pipe_valve')                 # one instance of each part whose name starts so (any case)
plants = kit.islands()                            # one instance per spatially separate piece
```

The parts are the objects at the import's parts level (single-child wrapper
nodes such as `Scene > RootNode` are descended, as the engine's loader did).
Each part, with its children, moves into a collection of its own outside the
scene, so the catalogue row never renders; its instance offset is the bottom
centre of its geometry, so `get()` places a collection instance standing on
its base at `location`. Get the same name again for another copy; the source
is never moved. `islands()` groups the parts whose boxes touch (grown by
0.15 x the median part diagonal): a plant made of a pot and its leaves is one
island, a row of three plants three; each island is an instance standing on
its base (`island_groups()` lists the part names).

The placement family sees through these instances to the real geometry:
`place_on(crate, floor)`, then `place_on(can, crate)` stacks one kit part on
another, and the audits judge instances like any object. Seat parts with
`place_on`, `place_touching` and `place_against` ([placement](placement.md)),
and combine pieces across kits: a unique building is often a wall panel from
one kit, a window from another, a door from a third.

`fetch_model.py`'s `[KIT_INFO]` (and the Blender preview's) reads a model's
part names the engine's way: a part name is stemmed (a trailing `_LODn`, then
`_NN`, `_a`..`_z` and size words), and the model is **LIKELY A MODULAR KIT**
when repeated variants make up half the parts or there are eight or more;
otherwise it lists a few named parts to judge from the preview.

The placement family has its own `load_kit` (`eidoblend.placement`), the same
calls returning real copies that share the source's mesh data instead of
instances: use it when a part must be edited on its own (a modifier, a cut).

For the robotics library use [the robotics kit](robotics.md) instead: its
loader preserves the authored joint hierarchy and ports.

## UI panels: html_mesh

The production engine's `HTMLMesh` painted a styled HTML element onto a
plane. `eidoblend.harness.html_mesh` does the same with an element tree and
CSS, 1 mm per pixel, unlit and transparent (signs, labels, a lower third, a
settings panel on a screen):

```python
from eidoblend.harness.html_mesh import El, html_mesh
card = El('div', style='display: inline-block; padding: 22px 34px; background: #11161d; color: #f0c040; '
                       'border: 6px solid #f0c040; border-radius: 10px; font: 700 64px Rajdhani-Bold; '
                       'text-transform: uppercase',
          children=[El('div', text='Supply depot 7'),
                    El('div', style='font: 400 30px SpaceMono-Regular; color: #c9d4e0', text='fuel - tools - spares')])
sign = html_mesh(card).obj                        # a plane facing -Y; mount it with placement's mount_on
clock = html_mesh(lambda t: El('div', style='font: 40px VT323; color: #0f0', text=f'{t:05.2f}'))   # every frame
```

Blender has no browser, so the module lays the tree out itself in the subset
UI cards use: block flow, `display: flex` (row or column, `gap`,
`align-items`, `justify-content`), widths in px or %, padding, margins,
word-wrapped text, `text-align`, `line-height`, `display: none`. It paints as
html2canvas did: background in the `border-radius` rectangle, borders,
text in its font, colour and `text-transform`, `overflow: hidden` clipping,
`img` and `canvas` elements, and radio, checkbox, range and text inputs in
`accent-color`. Fonts are the bundled ones (`eidoverse/assets/fonts`) by
family or file name; `monospace`, `sans-serif` and `serif` map to Space Mono,
Exo 2 and Old Standard. Other CSS (letter-spacing, shadows, transforms) is
ignored. A function of `t` is painted on every frame, which is what the
engine's `update()` was for. For a HUD on the frame, add the plane to the
[overlay layer](scene-format.md#the-post-stack-its-hooks-and-the-overlay-layer).

## Interior windows

The production engine's interior mapping puts a room behind a flat window:
the view ray is carried into the pane's tangent space and marched to the
room's back wall, sides, floor or ceiling, where one room picture is sampled.
A facade's windows show rooms with parallax and no interior geometry:

```python
from eidoblend.harness.interior_window import create_interior_window_material, render_room_image
plaster = assets.load_pbr('PaintedPlaster015', res='2k', repeat=(1, 1))
floor = assets.load_pbr('WoodFloor064', res='2k', repeat=(1, 1))
render_room_image('work/<id>/room_study.png', build=furnish, wall_material=plaster, floor_material=floor,
                  lamp_power=160, window_light=260)                # a room picture rendered in Blender (512 x 512)
mat = create_interior_window_material(room='work/<id>/room_study.png', depth=0.6, brightness=0.55, reflection=0.6)
for w in windows:                                               # quads with 0..1 UVs, U across, V up
    w.data.materials.append(mat)
```

`depth` is the room's depth relative to the window's width; the material is
self-lit and two-sided, as the engine's was. `brightness` sets how bright the
room reads against the street: by day a room is far darker than a sunlit
facade (about 0.5), at night the windows are the light (1.5 and up).
`reflection` (0 by default: the engine's material exactly) lays a pane of
glass over the room, a Fresnel-weighted mirror of the sky and the street; the
engine's shader had no room for it on its WebGPU stack, and a daylit facade
reads as glass with about 0.6.

`render_room_image(path, size=512, build=None, width=3.2, height=2.6,
depth=3.0)` renders a room box from just outside its open side (the window, at
y = 0; the room runs to y = depth). Its faces carry UVs of one unit a metre,
so `wall_material`, `floor_material` and `ceiling_material` (PBR sets) tile at
their real size; without them the walls are flat plaster and the floor flat
wood. A ceiling light (`lamp` colour, `lamp_power` watts) lights it, and
`window_light` adds soft daylight through the window for a room seen by day.
`build(scene)` furnishes it with real props at real scale: import and stand
them in the open scene, where they evaluate (a lamp on the desk:
`assets.rest_on(lamp, desk_top)`), then move them into the room's scene. The
picture is a room seen straight on (the material stretches its edges over the
sides, floor and ceiling), so keep the furniture against the back wall and the
lens moderate. A few room pictures, one material each, spread across a facade
give it variety; the pipeline's
[windows test](../blender/tests/pipeline2/test_renders.py) furnishes a study
and a store room.

## Housekeeping

Keep reusable sources and useful studies. Declare in `scene.json` only what
the scene reads: the runner's digest names a declared asset the script never
read, and a model beside the script that the config never declares. Check
whether an intended prop was left out, rather than deleting files just to
silence the warning. Preserve local source work and collaborators' assets.

## Not yet ported

- **`fetch_model.py` itself still draws its preview with three.js.** The
  Blender preview (`model_preview.py`, above) prints the same lines; wiring
  `fetch_model.py` to call it on this branch is an edit to that file, not yet
  made, so run it yourself on a fetched model.
- `html_mesh` has no pointer: the engine's mouse-event dispatch (clicking a
  panel in XR) does not apply to a rendered film, and the CSS subset above is
  all it lays out.
- The fetchers' first-use downloads from inside a scene (`fetch_pbr`,
  `fetch_model_file` without a cached ID) were written but not exercised on
  this branch: its tests ran with `EIDO_NO_FETCH=1` against an existing library.
