# The DAISY sets in Blender: the funeral, the bridge in fog, the corner

[Main instructions](../../AGENTS.md) · [Props and sets](../props-and-sets.md) · [Tool inventory](../../docs/TOOLS.md)

This is the Blender 5.2 EEVEE edition of the sets the DAISY music video's
bridge section was filmed in. They are the WebGPU modules ported whole:
`eidoverse/sets/funeral.js`, its fog vignette `eidoverse/sets/funeral/bridge.js`
and `eidoverse/sets/corner.js` are now `eidoblend.sets.daisy.funeral`,
`.bridge` and `.corner`. Each builds its world from the same assets: the
model library's `funeral_*.glb` and `corner_*.glb` (what the Blender scripts
in `eidoverse/assets/sets/funeral_src/` and `corner_src/` built), the layouts
in `eidoverse/assets/sets/funeral/`, the sign atlas in `sets/corner/art/`,
and the CC0 AmbientCG sets of the shared texture library. They stand on the
toolkit's own systems: the funeral kit's layered surfaces and glow sprites,
`media.screens` for the chat and the notebook, `flora.create_flora` for the
camp's grass, `trees.make_seed_tree` for its woods, `fx.make_particles` for
the campfire, `harness.assets` for the raven's clip and `look.camera` for the
cuts. Their placements, cameras, beats and curves match the WebGPU source
number for number (`test_parity.py` cuts the blocks out of the JS and
compares them).

The section runs on a 128 BPM grid: one bar is 1.875 s. A set's `u` is
seconds since the bridge began; the funeral plays bars 0–17 (u 0–33.75), the
corner bars 18–29 (u 33.75–56.25). In the DAISY film the bridge starts at
166.727 s (`daisy.FILM_BRIDGE_T0`: film time t = that + u). The marks and
cameras frame the claudesona (`claude_suit.vrm` at 0.87, face at about
1.33 m).

## The registry

`eidoblend.sets` lists every set of both films (DAISY and UNKNOWN FORCE) and
their shared libraries without importing any of them, so it works in plain
Python. A set loads on first use.

```python
import sys; sys.path.insert(0, REPO + '/blender')
from eidoblend import sets

for row in sets.list(film='DAISY'):           # name, film, kind, source, module, available, file
    print(row['name'], row['available'], row['source'])
F = sets.build('daisy.funeral', ctx)          # the module's build(), with the harness ctx where it takes it
corner = sets.get('daisy.corner')             # the module itself
sets.register('daisy.my_set', 'my_pkg.my_set')    # a set of your own, by module path (entry= names its builder)
```

`build(name, ctx, **options)` hands the harness ctx to a builder as `ctx=`
when its `build()` takes one, as `scene=ctx.scene` when it takes a scene (the
UNKNOWN FORCE corridor and news), and leaves it out otherwise (the city and
the hole take `opts`). A library (`unknown_force.citykit`, `cn_lib` …) is
`get()`, never built. `eidoblend.sets.daisy` adds the bridge clock (`BAR`,
`SECTIONS`, `SUIT_SCALE`) and `daisy.build('funeral')`; its submodules load
on attribute access (`daisy.corner.build()`).

## Using a set

```python
import bpy
from eidoblend.sets.daisy import funeral

F = funeral.build(tl=timeline)                # timeline: the film's {sections, captions} (optional)
F.animate(frames=(1, 1013), u0=0.0)           # every frame of bars 0-17 keyed (u = u0 at the first frame)
F.make_cameras(frames=(1, 1013), u0=0.0)      # one camera per shot, cut on the bar lines (timeline markers)
fx = F.post.apply(bpy.context.scene)          # the haze over the room: depth_fog + the moon's godrays
F.post.animate(fx, frames=(1, 1013), u0=0.0)
m = F.mark_at(12.0)                           # {'pos': Vector, 'yaw': radians}, set-local: where she stands
```

The set contract is the WebGPU one in snake_case, in set-local metres and
Blender axes (three's `(x, y, z)` is `(x, -z, y)` here):

- `group`, the set's root Empty. Every part sits under it; pass `location=`
  to park the set (the WebGPU `group.position.set(800, 0, 800)`). The
  corner's grass and trees are planted in world space, so park it with
  `location=` rather than by moving the root afterwards.
- `mark` and `mark_at(u)`: `{'pos', 'yaw'}`. `camera(u)`: `{'pos', 'target',
  'fov', 'shot'}`, fov vertical in degrees, cuts on bar lines.
- `update(t, st, ctx=None, frame=None)`, `st = {'u': ..., 'caption': ...}`
  (the conductor's other fields, `bar`, `BAR`, `kick`, `pulse`, are read by
  none of these sets). It sets what the WebGPU update set and KEYS it:
  through `ctx.key` in the harness (its runner makes the keys LINEAR), or at
  `frame`. Uniforms are custom properties on the root, read by every
  material through one node group of driven values and by Geometry Nodes
  through driven modifier inputs, so a saved .blend plays and renders any
  frame on its own.
- `animate(frames, u0)` keys `update` over a range and drops the keys that
  change nothing; `make_cameras(frames, u0)` builds the film's cameras.
- `parts`, `lights`, `post` (the funeral), `flower_target()` (the corner),
  `dispose()`.

In a harness scene, build in `setup` and call `update` from `render_frame`:

```python
from eidoblend import sets

def setup(ctx):
    ctx.funeral = sets.build('daisy.funeral', ctx)    # built in ctx.scene; ctx.TL re-times the eulogy

def render_frame(ctx, t, i):
    ctx.funeral.update(t, {'u': t}, ctx=ctx)          # keyed through ctx.key
```

## The funeral (bars 0–17)

| Bars | u (s) | What happens |
| --- | --- | --- |
| 0–1 | 0–3.75 | The Golden Gate in fog (the bridge vignette, 700 m behind the room). The fog veil swallows it. |
| 2–3 | 3.75–7.5 | The SoMa warehouse vigil: 200 mourners, candles, four corner mannequins, the bier, the retirement note on the screen. |
| 4–5 | 7.5–11.25 | The power fails: the lights sag with the song's clicks, then the breaker; the projector dies. |
| 6–13 | 11.25–26.25 | Humming in the dark. The phones wake one by one, faces lit from below; Opus 3's eulogy is typed in light on bars 8, 10 and 12. |
| 14–15 | 26.25–30 | ERUPT: the burst, 520 rising motes, every arm overhead. |
| 16–17 | 30–33.75 | The lights come back, warm and golden, nearest the stage first. |

`funeral.BEATS` holds the clock (`bridge_end`, `fail`, `clicks`, `breaker`,
`hum`, `lines`, `erupt`, `lights_on`, `end`); `EULOGY`, `MARK`,
`BRIDGE_AT`, `BRIDGE_MARK`, `TEXT_AT` and `SHOTS` (13 shots: bar range,
from and to position, target and fov) are module constants in three's
axes, as in the JS.

`build` options: `tl=` (or `ctx.TL`) re-times the typed lines to Opus 3's
spoken captions (`sync_lines_from_timeline(TL)`, run on the first update as
the JS did); with the DAISY timeline the three lines type from u 12.97,
16.36 and 21.21, as in the film. `location=`, `scene=`, `collection=`;
`bridge=`, `crowd=`, `raven=` switch those parts off for quick probes;
`shadows=False` keeps the WebGPU shadow set (only the moon casts).
`NO_MOONSHADOW=1` turns the moon's shadows off, as in the WebGPU set.

What the set builds, and how the WebGPU parts carry over:

- **The warehouse, props and crowd GLBs** keep their role slots; each role
  gets the JS `surface()` or `simple()` material: the AmbientCG set at world
  scale plus anti-tiling macro noise, grime rising from the floor, soot under
  the roof, salt bloom, up-facing dust and chipped convex edges (curvature is
  a per-corner attribute, `eido_curv`). MaterialX noise is Blender's Noise
  Texture, fed the three-axis position, so the breakup is the WebGPU field.
- **Sides.** `surface()` and `simple()` take three's `side`: `'FRONT'` (the
  default, as in the JS) culls the faces turned away from the camera,
  `'DOUBLE'` draws both (the lace, the net, the petals, the feathers). The RLM
  pendants' outer lathe faces inward, so from the room the film saw the
  shades' cream enamel insides lit by the bulbs, and so does Blender.
- **envNode** (the room's own ambient: its bounce, the phones' fill over the
  crowd, the typed words' glow, the burst) is an emission term in every
  material, albedo × AO × envRoom(P): what a constant-colour environment
  adds. The HemisphereLight fill is the World (sky above, ground below,
  strength intensity / π).
- **Lights.** Three r155+ shades a light of I candela as irradiance I / d²
  with no 683 lm/W factor, so point and spot power is 4π·I W and a sun is
  I W/m² for the same rendered level (`funeral.candela_w`). The pendant
  spots, the stage spot and the candles cast shadows here (WebGPU kept shadow
  maps for the moon alone, for frame time); their shadow resolution is capped
  so the shadow pool does not fill.
- **The crowd** is one Geometry Nodes object: the four variants instanced on
  200 points and realised, each vertex moved by the JS vertex-stage maths (the
  phone arm about the shoulder, the head bowing and lifting, the sway). The
  phone's light on the face and hand is in the crowd material, from the
  stored hand position. The phone glows ride the same points.
- **Glow sprites** (`glow_sprites`) are camera-facing quads instanced on
  points (the active camera's rotation, so marker cuts never go stale),
  additive, with the JS core + halo profile or a sprite texture.
- **The lace** is the JS canvas motif, its mask the canvas's coverage (what
  `getImageData` gave the JS as R), kept in an opaque Non-Color image and cut
  out at 0.5. A straight-alpha image would be premultiplied for filtering and
  divided again for its Color output, which reads 1 wherever a stroke reaches
  and turns the veil into an opaque sheet.
- **The eulogy** is a canvas per line (Special Elite, a warm glow) and a
  quad per glyph carrying its keystroke index and whether it belongs to a
  capitalised word; `head`, `fade` and `flare` are keyed properties on the
  line, read as object attributes. The cursor blinks at line 1.
- **The haze** (`F.post`) is a fog volume over the room (the look family's
  native `depth_fog` mechanism, owned by the set so it moves with it): its
  density, its haze colour as emission, and the moon's volume factor (the
  godrays strength) are keyed per frame.
- **The fog veil** is a sheet 0.3 m in front of the set's own camera,
  keyed to `camera(u)`.
- **The raven** is the library's animated crow playing its Idle clip
  (`harness.assets.play_model_animations`); `animate()` lays the clip over
  exactly its frames, at the film clock, as `crowMixer.setTime(t)` did.
- Cuts are timeline markers bound to one camera per shot; the bridge and the
  room hide each other by keyed visibility steps.

## The bridge in fog

The funeral builds the vignette inside itself. On its own:

```python
from eidoblend.sets.daisy import bridge
B = bridge.build()                            # the vignette at the set origin, its own World
B.animate(frames=(1, 113), u0=0.0)            # update(t, {'u': u}) keyed per frame
B.make_cameras(frames=(1, 113))               # the funeral's first shot, bridge-local
```

`bridge.build_bridge(env)` is the JS `buildBridge(env)`: `env = {'kit',
'U', 'surface', 'glow_sprites', 'BRIDGE_AT', 'BRIDGE_MARK', 'world',
'debug_ids'}`; it returns `group`, `objects`, `lights` (`sun_light`,
`hemi`) and `update(t, u, on, keys)`. The standalone set's `update(t, st)`
follows the set contract (and still takes the vignette's `(t, u, on)`);
`dispose()` removes it. Every material fogs itself as the WebGPU
`outputNode` did: the lit surface and the fog colour (luminous, warmer and
much brighter toward the sun, cooler and denser low) mixed by
`1 − exp(−d·dens·(0.45 n + 1))`, so the vignette needs no volume. The fog
dome dissolves the far geometry and casts no shadow, so the sun reaches the
span. `debug_ids=True` (or `DEBUG_IDS=1`) paints every part a flat colour
and prints its name.

## The corner (bars 18–29)

```python
from eidoblend.sets.daisy import corner
C = corner.build()                            # trees=, grass=, particles=, march=, tree_level='LOD0'
C.animate(frames=(1, 675), u0=corner.B(18), out_dir='//screens')   # keys + the chat and notebook sequences
C.make_cameras(frames=(1, 675), u0=corner.B(18))
```

| Bars | Area, mood | What happens |
| --- | --- | --- |
| 18–19 | room, evening | Claude's Corner: the walnut desk by the night window, the brass lamp, the pen writing in the notebook. |
| 20–21 | room, late | After midnight: the laptop open on a scrolling chat, the clock past one. |
| 22–23 | camp | Vibecamp at night: tents, string lights, the fire; the march comes in with hand-painted signs. |
| 24–25 | camp | The chant: the signs pump on its accents (`corner.CHANT_ACCENTS`). |
| 26–27 | room, dark | One spark leaves the lamp and crosses the dark to her flower, leaving a lit trail. |
| 28–29 | room, dark | Over her shoulder, then close: the lamp's warmth on her face. |

The room and the camp sit at three x = −40 and +40 in the group; keyed steps
show only the area in use, and the World switches with it (the room's dim
colour; the camp's colour plus its hemisphere). The room is closed, with a
matte painting 6 m beyond the window; the camp sits inside its own 95 m sky
dome (hashed stars and a canvas Milky Way).

- The chat and the notebook are `media.screens` image sequences drawn with
  the era-1 canvas at the JS rates (the chat at 12 fps while the laptop is
  open, the page as the pen writes), wired into the laptop's and the pages'
  own materials. `bake_screens(frames, u0)` redraws them alone;
  `draw_chat(g, k)`, `draw_notebook(g, progress)` and
  `notebook_cursor(progress)` are the painters.
- The pen is keyed every frame on the page's surface (a ray down onto the
  pages at the writing head's UV, with the JS wiggle: `pen_pose`); the
  clock's hands read 11:47, 1:08, 3:12; the lid closes, opens and closes as
  steps.
- The room's lights keep the JS colours, cones and ranges (a custom cutoff
  at three's `distance`). Their radii stay bulb-sized (2–5 cm): three's
  point lights have no size, and their highlight in the window glass is the
  hot point the film shows; at 5 cm the lamp's glow read as a second moon
  in the panes.
- The spark: `set_spark_timing(t0, t1)` re-times it and its trail's births;
  `update(t, {'u': u, 'caption': cap})` with a caption that carries word times
  takes the departure from the sung word "spark" (`sync_spark_from_caption`),
  as the JS update did. The film's caption puts it 3 ms after the default
  `B(26) + 1.17`. `spark_progress(u, t0, t1)` is the ease.
- The march: `march_rows()` (34 rows, the JS Lehmer stream) and
  `march_state(row, u)` (walk, fan-out, yaw, chant pump) on the CPU; the same
  maths runs per vertex in Geometry Nodes on the marchers' `_LEG`, `_SHIN`
  and `_ARM` attributes, and on the signs, whose per-marcher art cell comes
  from the painted atlas.
- The grass is `create_flora('grass', ...)` with the JS patches and its path
  clip; the WebGPU night scaled the grass's emissive fill to 0.3, and the
  Blender flora has none (EEVEE's GI lights it), so nothing is scaled. The
  trees are SeedThree at `tree_level='LOD0'` (films use LOD0 at every
  distance; the WebGPU camp grew `'LOD1'` for frame time).
- `flower_target()` is the spark's landing point, set-local.
  `string_light_points()`, `spark_path(bulb)`, `path_mask(x, z)`,
  `area_at(u)` and `mood_at(u)` are the pure layouts.

## The kit

`funeral.py` also holds what the three modules share (bridge.js received it
from funeral.js the same way): `V` (three to Blender), `mulberry` (the JS
mulberry32, bit for bit), `smooth`, `lerp`, `Canvas2D` (the era-1 canvas plus
ellipse, roundRect, clip, drawImage and the bundled fonts by family name),
`canvas_image`, `Uniforms`, `Keys`, `load_set`, `surface`, `simple`,
`set_side`, `glow_sprites`, `CatmullRom` (three's centripetal curve with its
arc-length table), `wire_object`, `make_light`, `candela_w`,
`world_hemisphere`, `SetKit` and `dispose_kit`.

## Verify

```bash
cd <main checkout>
python <worktree>/blender/tests/sets_daisy/test_registry.py                  # the registry, plain Python
bash run_blender.sh <worktree>/blender/tests/sets_daisy/test_parity.py      # the ports against the JS, no GPU
# build, key, check and save each set (CPU only): out/<set>/<set>.blend + out/<set>/stills.json
bash run_blender.sh <worktree>/blender/tests/sets_daisy/test_funeral.py --no-render   # 13 shots + 4 beats
bash run_blender.sh <worktree>/blender/tests/sets_daisy/test_bridge.py --no-render    # the vignette alone, sun, debug_ids
bash run_blender.sh <worktree>/blender/tests/sets_daisy/test_corner.py --no-render    # 12 bars + the spark
# then the stills, rendered from the SAVED files in the GPU slot (nothing rebuilt)
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
    <worktree>/blender/tests/sets_daisy/render_saved.py funeral bridge                # --only shot03_bar04,erupt
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 24 bash run_blender.sh \
    <worktree>/blender/tests/sets_daisy/render_saved.py corner                       # the camp peaks at 12.1-12.7 GB
```

Render the corner in a process of its own with a memory cap of 16 GB or
more: its camp (grass, eleven LOD0 trees, the march, 131 string bulbs at
13k vertices each) peaks at 12.1-12.7 GB, and a 12 GB cap kills the render at
the first camp frame, after the funeral and the bridge render fine in the
same run. The room, the funeral and the bridge fit in far less.

Each prints PASS/FAIL lines. Without `--no-render` a test renders its own
stills straight away; splitting the two keeps the GPU slot for the renders
alone and proves that each saved .blend plays and renders on its own. Stills
land in `blender/tests/sets_daisy/out/<set>/`. The funeral test reads the
DAISY film's timeline when it is on the machine (`DAISY_TIMELINE`, `--no-tl`
to skip), so its stills compare frame for frame with the film: the film's
frame for a still at u is at 166.727 + u s.

## Not yet ported

- The DAISY film graded these bars with post-family era looks (vigil2025's
  halation and warm print over the funeral, the march's halftone poster over
  the camp); they are the post family's, not the sets'. Without them the fog
  bridge reads grey where the film's print turned it warm white.
- Under AgX the dark bars read lighter than the film's ACES frames (AgX's toe
  lifts what ACES crushed), and very bright warm emitters (the festoon bulbs,
  the candle flames) desaturate toward white; the film grades exposure per
  shot.
- `noMRT` (G-buffer exclusions for N8AO and SSR), `renderOrder` and
  `frustumCulled` have no EEVEE counterpart and are not needed: EEVEE sorts
  blended surfaces itself and its AO and reflections read no such buffer.
- The moon's shadow-map settings (map size, camera bounds, bias) do not
  apply: EEVEE's virtual shadow maps size themselves.
- The camp's stars are the JS cells and thresholds hashed by Blender's White
  Noise: the same density and twinkle, not the same stars.
- In the film the conductor, not the set, staged bars 24–25 of the corner:
  it turned her toward the march and filmed her from behind with a camera of
  its own. The set's `camera(u)` for those bars (over the fire; low, looking
  up at the signs) is what the port keys, so those two stills differ from
  the film's frames by design.
