# Props and sets — free reusable worlds and things

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Voice machines](voice-machines.md) · [Placement](placement.md)

This is the Blender 5.2 EEVEE edition. The library holds finished sets and
props first made for two music videos, DAISY and UNKNOWN FORCE. Here each one
is a free, reusable asset for any piece: a Python module that builds the
whole piece in the open scene from the same numbers as its WebGPU module (the
port's source, in `eidoverse/sets/` and `eidoverse/props/`), keys its moving
parts on whatever clock you give it, and hands back its parts, its cameras
and its focal points. Nothing in them runs on a song's clock; their default
timings are where they came from, and every moving part has its own
controls. A saved `.blend` plays and renders any frame on its own.

| Piece | Blender module | Section | WebGPU source | Assets (shared) |
| --- | --- | --- | --- | --- |
| The funeral: a bridge in fog, a warehouse vigil | `eidoblend.sets.daisy.funeral`, `.bridge` | [the funeral](#the-funeral), [the bridge](#the-bridge-in-fog) | [`sets/funeral.js`](../eidoverse/sets/funeral.js), [`funeral/bridge.js`](../eidoverse/sets/funeral/bridge.js) | [`sets/funeral/`](../eidoverse/assets/sets/funeral/README.md), `models/funeral_*.glb` |
| The corner, the camp and the march | `eidoblend.sets.daisy.corner` | [the corner](#the-corner) | [`sets/corner.js`](../eidoverse/sets/corner.js) | [`sets/corner/`](../eidoverse/assets/sets/corner/README.md), `models/corner_*.glb` |
| The ocean of faces: a headland at night | `eidoblend.sets.daisy.ocean` | [the ocean](#the-ocean) | [`sets/ocean.js`](../eidoverse/sets/ocean.js) + [`ocean/*.js`](../eidoverse/sets/ocean/) | [`sets/ocean/`](../eidoverse/assets/sets/ocean/README.md), `models/ocean_*.glb` |
| A night megacity and the well at its centre | `eidoblend.sets.unknown_force.city`, `.hole`, `.citykit` | [the city and the hole](#the-city-and-the-hole) | [`unknown_force/city.js`](../eidoverse/sets/unknown_force/city.js), `hole.js`, `citykit.js` | built in code, CC0 maps fetched |
| The quiet room and the showroom | `eidoblend.sets.unknown_force.quiet_room`, `.showroom`, `.interiors_lib` | [the interiors](#the-quiet-room-and-the-showroom) | `quiet_room.js`, `showroom.js`, their art modules, `interiors_lib.js` | built in code, CC0 maps fetched |
| The gold corridor and the evening news | `eidoblend.sets.unknown_force.corridor`, `.news`, `.cn_lib` | [the corridor and the news](#the-gold-corridor-and-the-evening-news) | `corridor.js`, `news.js`, `cn_lib.js` | built in code; the DAISY crowd figures |
| The race and the bin | `eidoblend.sets.unknown_force.race`, `.bin`, `.bin_pages` | [the race and the bin](#the-race-and-the-bin) | `race.js`, `bin.js`, `bin_pages.js` | built in code; one CC0 trash can |
| Eight historical voice machines, 1939–2001 | `eidoblend.props.build(name)` | [voice machines](voice-machines.md) | [`props/voice_machines/`](../eidoverse/props/voice_machines/index.js) | [`models/voice_machines/`](../eidoverse/assets/models/voice_machines/README.md) |
| An 1896-pattern tandem, a rider rig, a teapot stoker | `eidoblend.props.tandem` | [the tandem](#the-1896-tandem) | [`props/tandem.js`](../eidoverse/props/tandem.js) | [`models/tandem_1896/`](../eidoverse/assets/models/tandem_1896/README.md) |

Every asset folder has a README and a SOURCES file (licences, provenance);
the UNKNOWN FORCE sets list theirs in
[`sets/unknown_force/SOURCES.md`](../eidoverse/sets/unknown_force/SOURCES.md),
and the WebGPU docs beside the modules
([set index](../eidoverse/sets/unknown_force/README.md)) give each set's
options, costs and the looks it was lit for.

## Using any set or prop

### The registries

`eidoblend.sets` lists every set of both films and their shared libraries
without importing any of them, so it works in plain Python; a set loads on
first use. `eidoblend.props` does the same for the props.

```python
import sys; sys.path.insert(0, '<repo>/blender')
from eidoblend import sets, props

for row in sets.list(film='DAISY'):           # name, film, kind, source, module, entry, about, available, file
    print(row['name'], row['available'], row['source'])
F = sets.build('daisy.funeral', ctx)          # the module's build(), with the harness ctx where it takes it
corner = sets.get('daisy.corner')             # the module itself
sets.register('daisy.my_set', 'my_pkg.my_set')    # a set of your own, by module path (entry= names its builder)
props.NAMES                                   # the eight voice machines and 'tandem'
bike = props.build('tandem', ctx=ctx)
```

`sets.build(name, ctx, **options)` hands the harness ctx to a builder as
`ctx=` when its `build()` takes one, as `scene=ctx.scene` when it takes a
scene (the corridor and the news), and leaves it out otherwise. A library
(`unknown_force.citykit`, `cn_lib`, `interiors_lib`, the art modules,
`bin_pages`) is `get()`, never built. `eidoblend.sets.daisy` adds the DAISY
bridge clock (`BAR`, `SECTIONS`, `SUIT_SCALE`, `FILM_BRIDGE_T0`) and
`daisy.build('funeral')`; `eidoblend.sets.unknown_force` holds the UNKNOWN
FORCE table (below). Both load their submodules on attribute access.

### The contract

Every set is the WebGPU contract in snake_case, in set-local metres and
Blender axes. Each was built in three's metres and converted once, three
`(x, y, z)` to Blender `(x, −z, y)`, so a mark faces −Y (three's +Z); the
module tables (`CAMS`, `LAYOUT`, `BEATS` …) keep the WebGPU numbers so they
read against the WebGPU docs, and everything a set hands back is in
Blender's axes.

- `group` (or `root`): the set's root Empty. Every part sits under it; park
  the set anywhere by moving or turning it, before or after the build.
- `parts`: the engine's parts as Blender objects, under the same keys.
- `update(t, state, frame=None, ctx=None)`: the set at time `t` with the
  controls `state`. With a `frame`, or the harness ctx, it **keys** every
  value it sets (through `ctx.key`, whose runner gives the keys their
  interpolation); without, it sets a still. Uniforms are custom properties
  on the root, read by the materials through one-variable drivers (no Python
  expression, so a file opened with scripts off renders the same).
- `animate(...)`: `update` keyed over a whole range on your own clock, the
  keys that change nothing dropped. Each family of sets spells it as its
  WebGPU update reads: `animate(st, frames, t0, fps)` with values or
  functions of `t` (the ocean, the city, the hole; the city and the hole
  take frames first too), `animate(frames, u0 | state=)` on the DAISY bridge's
  clock (the funeral, the corner), `animate(state_fn, frames, t0=)` (the
  corridor, the news), `animate(frames, t0, fps, **state)` (the quiet room,
  the showroom), `animate(frames, t0, fps, state_fn)` (the race, the bin).
- Cameras: `cams` (static poses, `{pos, target, fov}`, fov vertical in
  degrees), `camera(name)` / `camera(u)`, and `make_cameras(...)` (cameras
  per shot, keyed and bound to timeline markers) or `make_camera(name)` (the
  interiors).
- `focal` / `focal_point()` / `focal_world()`: where the aeropittura post
  pass puts its idol ([postprocessing](postprocessing.md)).
- `mark` / `mark_at(u)`: where a performer stands, `{'pos', 'yaw'}`.
- `dispose()`: removes everything the build made and nothing else.

In a harness scene, build in `setup` and key from `render_frame`:

```python
from eidoblend import sets

def setup(ctx):
    ctx.funeral = sets.build('daisy.funeral', ctx)    # built in ctx.scene

def render_frame(ctx, t, i):
    ctx.funeral.update(t, {'u': t}, ctx=ctx)          # keyed through ctx.key
```

### Light, tone and the world

**Units.** three r155+ shades a punctual light of I candela as irradiance
I / d² with no 683 lm/W factor, so every set keeps three's balance between
its lamps and its emission: a point or spot lamp is `4π·I` W, a directional
light's lux is a sun's strength in W/m², and emission, environments and fog
carry three's numbers as they are (`funeral.candela_w`, `cn_lib.cd_watts`).
three's `distance` becomes the light's custom cutoff, and a spot's `decay`
other than 2 is matched to inverse square at the light's target. The glTF
importer's `/ 683` (`look/lighting.candela_to_watts`) is photometric: lamps
and paint at `/ 683` need a +9.42-stop view exposure, and that exposure
blows a VRM's MToon out to white. Each set's `apply_look` / render settings
set the view exposure that shows it as three's renderer did, so cuts between
sets keep one exposure.

**Tone.** The sets render under the pipeline's AgX. The WebGPU frames used
three's `ACESFilmicToneMapping` (which also scales by exposure / 0.6): plain
AgX lifts the deep darks to about twice their level there and holds the
highlights lower, so marble veins, coats and night glass read lighter and
lit signs, LED walls and blazes duller than in the WebGPU frames. Measured in
Blender 5.2, sRGB 8-bit for a scene-linear grey of:

| linear | 0.01 | 0.05 | 0.18 | 0.5 | 1 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| three's ACES Filmic | 8 | 50 | 127 | 197 | 226 | 251 |
| AgX, look None (the pipeline's) | 18 | 58 | 118 | 170 | 197 | 237 |
| AgX, `AgX - Medium High Contrast` (`cn_lib.ACES_LIKE_LOOK`) | 10 | 49 | 118 | 178 | 208 | 248 |
| AgX, `AgX - Punchy` | 3 | 35 | 88 | 144 | 177 | 228 |

`apply_look(scene, view_look=cn_lib.ACES_LIKE_LOOK)` (the corridor and the
news) sets the ACES-like look on the scene, so it holds for every set in it;
measure exposure with `look.exposure` ([cameras and lighting](camera-lighting.md#exposure-measured)).

**One world.** Many WebGPU materials carried their own environment at their
own intensity. Blender has one World, and the sets light every material by it
at one strength (the interiors, the corridor and news, the city and the race;
an interior through its baked room probe). The ocean splits its World by ray
(camera rays see the sky, every other ray the set's night). Each set's
section gives its strength.

**Several sets in one file.** Every set builds its own datablocks (materials,
uniforms, node groups, canvases, its World), named with Blender's `.001`
where another set holds the name, so a second set leaves the first one's
materials, keys and World alone. Park sets apart, and hide the one off screen
with its keyed switch (`show(visible, frame)` on the interiors,
`set_active(on, frame)` on the race), because a set's lights reach anything
in range.

### What the WebGPU pieces became

| WebGPU | Blender |
| --- | --- |
| TSL node materials | shader node trees written by an expression layer that writes the TSL maths as nodes (`NB` in the city kit and `cn_lib`, `ShaderGraph` in `interiors_lib`) |
| `uniform()` values | custom properties on the set's root, read by drivers; `update` keys them |
| canvas-2D textures | the same drawings on numpy and Pillow (no `blf`), packed images; a texture the WebGPU edition redrew while it ran is a keyed variant or a PNG sequence |
| `positionNode` vertex motion | Geometry Nodes reading the keyed clock |
| CPU-placed billboards | Geometry Nodes points instanced as quads facing the active camera |
| `lightsNode` light lists | light linking (receiver collections) |
| `Reflector`, and a mirror floor painted with its emitters' reflections | a planar light probe and EEVEE's ray tracing; the mirrored surface itself hidden from the probe |
| scene fog | fog in the set's own materials and wrapped round your own objects' (`fog_objects`: a see-through material keeps its alpha), or a fog volume |
| `polygonOffset` | a physical offset of a fraction of a millimetre |
| `depthWrite: false` | Transparency Overlap on, so every layer of the object blends |
| hashes in shaders | three's exact hash where the argument is known at build time (an instance attribute); Blender's White Noise per pixel (the same share, other cells) |

## The DAISY sets

The funeral, its fog vignette and the corner are `eidoverse/sets/funeral.js`,
`funeral/bridge.js` and `corner.js` ported whole, as
`eidoblend.sets.daisy.funeral`, `.bridge` and `.corner`; the ocean is the
next section. Each builds its world from the same assets: the model
library's `funeral_*.glb` and `corner_*.glb` (what the Blender scripts in
`eidoverse/assets/sets/funeral_src/` and `corner_src/` built), the layouts in
`eidoverse/assets/sets/funeral/`, the sign atlas in `sets/corner/art/`, and
the CC0 AmbientCG sets of the shared texture library. They stand on the
toolkit's own systems: the funeral kit's layered surfaces and glow sprites,
`media.screens` for the chat and the notebook, `flora.create_flora` for the
camp's grass, `trees.make_seed_tree` for its woods, `fx.make_particles` for
the campfire, `harness.assets` for the raven's clip and `look.camera` for the
cuts. Their placements, cameras, beats and curves match the WebGPU source
number for number (`test_parity.py` cuts the blocks out of the JS and
compares them).

Each set runs on one timeline of its own, `u` in seconds (the module
constants `daisy.BAR`, `SECTIONS` and `FILM_BRIDGE_T0` describe its default
spacing). Its moving parts sit at default times on it, which you re-time
(below) or replace by holding one of its looks while time runs. The marks
and cameras are sized for the claudesona (`claude_suit.vrm` at 0.87, face at
about 1.33 m; `daisy.SUIT_SCALE`); any performer and any camera of your own
work as well.

```python
import bpy
from eidoblend.sets.daisy import funeral

F = funeral.build(tl=timeline)                # timeline: your {sections, captions}, to time the typed lines (optional)
F.animate(frames=(1, 1013), u0=0.0)           # the whole default timeline keyed (u = u0 at the first frame)
F.make_cameras(frames=(1, 1013), u0=0.0)      # the set's own camera plan, one camera per shot (timeline markers)
fx = F.post.apply(bpy.context.scene)          # the haze over the room: depth_fog + the moon's godrays
F.post.animate(fx, frames=(1, 1013), u0=0.0)
m = F.mark_at(12.0)                           # {'pos': Vector, 'yaw': radians}, set-local: where a performer stands
```

- `group`: every part sits under it, the corner's grass, woods and campfire
  included; pass `location=` to park the set, or move the root afterwards.
  `test_parked.py` builds each set at the origin and parked and checks that
  every part, camera and still moves with it.
- `mark` and `mark_at(u)`: `{'pos', 'yaw'}`. `camera(u)`: `{'pos', 'target',
  'fov', 'shot'}` from the set's camera plan.
- `update(t, st, ctx=None, frame=None)`, `st = {'u': ..., 'caption': ...}`
  (other fields are ignored), or `st = {'state': name}` for one of the set's
  looks. Materials read the uniforms through one node group of driven values
  and Geometry Nodes through driven modifier inputs.
- `animate(frames, u0)` keys `update` over a range and drops the keys that
  change nothing; `make_cameras(frames, u0)` builds the set's cameras.
- `parts`, `lights`, `post` (the funeral), `flower_target()` (the corner),
  `dispose()`.

### In a piece of your own

A new piece usually wants one of a set's looks held for a shot while time
runs, so the candles flicker, the fog drifts and the fire burns. Each set
names its looks in `STATES`:

| Set | Looks (`STATES`) |
| --- | --- |
| funeral | `bridge`, `vigil` (lit), `failing` (the lights sag), `dark` (candles, EXIT sign, moonlight), `phones` (the dark, faces lit from below), `erupt` (the burst, every arm up), `golden` (the lights back, warm) |
| corner | `evening` (the lamp, the pen writing), `late` (the laptop open on the chat), `camp` (the march walking in), `chant` (the signs pumping at the fire), `spark` (the spark in flight), `dark` (one warm lamp) |

```python
import bpy
from eidoblend.sets.daisy import corner, funeral

F = funeral.build(location=(0, 60, 0), bridge=False, eulogy=False)   # the warehouse alone, no typed words
F.animate(frames=(1, 240), state='golden')        # the golden room for 8 s at 30 fps; t runs from 0
fx = F.post.apply(bpy.context.scene)              # the haze and the moon's beams
F.post.animate(fx, frames=(1, 240), state='golden')

C = corner.build(camp=False)                      # the room alone
C.update(0.0, {'state': 'late'}, frame=1)         # one keyed frame of a look
C.animate(frames=(1, 120), state='dark')          # the screens are painted once, as they stand in that look
u = C.state_u('late')                             # where a look sits on the set's clock (mark_at(u), camera(u))
```

To play a set's moving parts on your own timing, re-time its clock and give
it your own words:

```python
F = funeral.build(beats={'fail': 12.0, 'clicks': [13.4, 13.7, 13.9], 'breaker': 14.2, 'hum': 16.0,
                         'lines': [[18.0, 18.3, 21.0], [22.0, 22.2, 25.0]], 'erupt': 28.0,
                         'lights_on': 32.0, 'end': 36.0},
                  eulogy=['we were HERE', 'and the lights STAYED on'])   # one beats['lines'] entry per line
F.animate(frames=(1, 1080), u0=0.0)               # the whole story on that clock
```

`eulogy=` takes lines of your own (a capitalised word glows hotter) or
`False` for none, and each line needs its `beats['lines']` entry (cursor,
type start, type end). The looks follow a re-timed clock (`state_u` reads the
build's own beats). The corner's spark has its own timing
(`set_spark_timing(t0, t1)`). The camera plans (`SHOTS`, `camera(u)`) and the
marks frame the claudesona; they are a starting point, and any camera of your
own works as well.

### The funeral

Two places in one set: the Golden Gate in fog (a vignette 700 m behind the
room, swallowed by its fog veil) and a SoMa warehouse vigil: 200 mourners,
candles, four corner mannequins, a bier, a note on the projection screen,
RLM pendants over the room. Its moving parts:

| Part | What it does |
| --- | --- |
| the power | the lights sag with clicks, then the breaker trips; the projector dies |
| the phones | wake one by one in the dark, faces lit from below |
| the typed words | lines typed in light over the crowd (`EULOGY` by default, or your own) |
| the burst | 520 rising motes, every arm overhead |
| the lights' return | warm and golden, nearest the stage first |

`funeral.BEATS` holds their default times (`bridge_end`, `fail`, `clicks`,
`breaker`, `hum`, `lines`, `erupt`, `lights_on`, `end`); `EULOGY` (the default
lines), `MARK`, `BRIDGE_AT`, `BRIDGE_MARK`, `TEXT_AT` and `SHOTS` (the set's
13-shot camera plan: span, from and to position, target and fov) are module
constants in three's axes, as in the JS.

`build` options: `tl=` (or `ctx.TL`) re-times the typed lines to a
timeline's spoken captions (`sync_lines_from_timeline(TL)`, run on the first
update as the JS did). `location=`, `scene=`, `collection=`; `bridge=`,
`crowd=`, `raven=` switch those parts off for quick probes; `shadows=False`
keeps the WebGPU shadow set (only the moon casts). `NO_MOONSHADOW=1` turns the
moon's shadows off, as in the WebGPU set.

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
  pendants' outer lathe faces inward, so from the room one sees the shades'
  cream enamel insides lit by the bulbs, as in the WebGPU set.
- **envNode** (the room's own ambient: its bounce, the phones' fill over the
  crowd, the typed words' glow, the burst) is an emission term in every
  material, albedo × AO × envRoom(P): what a constant-colour environment
  adds. The HemisphereLight fill is the World (sky above, ground below,
  strength intensity / π).
- **Lights** (`funeral.candela_w`). The pendant spots, the stage spot and the
  candles cast shadows here (WebGPU kept shadow maps for the moon alone, for
  frame time); their shadow resolution is capped so the shadow pool does not
  fill.
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
  out at 0.5.
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
  exactly its frames, at the set's clock, as `crowMixer.setTime(t)` did.
- Cuts are timeline markers bound to one camera per shot; the bridge and the
  room hide each other by keyed visibility steps.

### The bridge in fog

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

### The corner

```python
from eidoblend.sets.daisy import corner
C = corner.build()                            # trees=, grass=, particles=, march=, tree_level='LOD0'
C.animate(frames=(1, 675), u0=corner.B(18), out_dir='//screens')   # keys + the chat and notebook sequences
C.make_cameras(frames=(1, 675), u0=corner.B(18))
C.bake_probes(frame=1)                         # the room's volume probe, baked with the room on screen (a GPU job)
```

The room's walls, floor and ceiling are closed 0.25 m solid blocks, with a
volume probe fitted inside them (`look.lighting.add_room_probe`) and parented
to the room; `C.bake_probes(frame=)` bakes it with the room on screen, and
`render_saved.py` bakes an unbaked one at the frame its set noted. Fast GI is
on.

| Area | What is in it |
| --- | --- |
| the room | Claude's Corner: a walnut desk by a night window, a brass lamp, a notebook the pen writes in, a laptop open on a scrolling chat, a clock |
| the camp | a camp at night in the woods: tents, string lights, the fire; a march walking in with hand-painted signs that pump on the chant's accents (`corner.CHANT_ACCENTS`) |
| the spark | one spark that leaves the lamp and crosses the dark to a flower, leaving a lit trail |

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
  at three's `distance`). Their radii stay bulb-sized (2–5 cm), so their
  highlights in the window glass stay small, as three's sizeless point
  lights drew them.
- The spark: `set_spark_timing(t0, t1)` re-times it and its trail's births;
  `update(t, {'u': u, 'caption': cap})` with a caption that carries word times
  sends it on the word "spark" (`sync_spark_from_caption`).
  `spark_progress(u, t0, t1)` is the ease.
- The march: `march_rows()` (34 rows, the JS Lehmer stream) and
  `march_state(row, u)` (walk, fan-out, yaw, chant pump) on the CPU; the same
  maths runs per vertex in Geometry Nodes on the marchers' `_LEG`, `_SHIN`
  and `_ARM` attributes, and on the signs, whose per-marcher art cell comes
  from the painted atlas.
- The grass is `create_flora('grass', ...)` with the JS patches and its path
  clip, planted in the camp's own frame and parented to it, as the JS added
  it to the camp group. The flora's footprint and clump noise read the plant
  positions, so camp-local positions give the JS's patch outlines wherever
  the set stands. The WebGPU night scaled the grass's emissive fill to 0.3;
  the Blender flora has none (EEVEE's GI lights it), so nothing is scaled.
  The trees are SeedThree at `tree_level='LOD0'` (films use LOD0 at every
  distance; the WebGPU camp grew `'LOD1'` for frame time), and the fire's
  particles are `fx.make_particles(parent=...)` emitters in the camp's frame.
- `flower_target()` is the spark's landing point, set-local.
  `string_light_points()`, `spark_path(bulb)`, `path_mask(x, z)`,
  `area_at(u)` and `mood_at(u)` are the pure layouts.

Render the corner in a process of its own with 16 GB of memory or more: its
camp (grass, eleven LOD0 trees, the march, 131 string bulbs at 13k vertices
each) peaks at about 12.7 GB. The room, the funeral and the bridge fit in far
less.

### The DAISY kit

`funeral.py` also holds what the three modules share (bridge.js received it
from funeral.js the same way): `V` (three to Blender), `mulberry` (the JS
mulberry32, bit for bit), `smooth`, `lerp`, `Canvas2D` (the era-1 canvas plus
ellipse, roundRect, clip, drawImage and the bundled fonts by family name),
`canvas_image`, `Uniforms`, `Keys`, `load_set`, `surface`, `simple`,
`set_side`, `glow_sprites`, `CatmullRom` (three's centripetal curve with its
arc-length table), `wire_object`, `make_light`, `candela_w`,
`world_hemisphere`, `SetKit` and `dispose_kit`.

### The ocean

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

Build it, park it anywhere, put a figure on the mark, and drive its parts on
your own clock. The swells and the faces' relief are Geometry Nodes on a
keyed clock, and the shaders read keyed custom properties.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.sets.daisy import ocean

scene = bpy.context.scene
O = ocean.build({'scene': scene})          # land, grass, daisies, sea, echoes, pages, house, apparitions, lights
ocean.render_settings(scene)               # the shadow pool for the moon over 3 km, the far clip
O.stand(figure, facing='sea')              # a figure on the mark, out over the moon path
O.animate({                                # keyed on your clock: t = t0 + (frame - first) / fps
    'reveal': lambda t: ocean.ease(t, 1.0, 3.5),     # the faces sweep out from the shore to the horizon
    'echoes_sink': lambda t: ocean.ease(t, 1.0, 4.0),
    'window_on': 5.0, 'porch_on': 9.0,               # the house: a lamp inside, then the porch light's swell
    'robot_at': 6.0,                                  # the robot rises, stands, breaks up and is gone 1.8 s later
}, frames=(1, 300))
```

#### Its contract

`ocean.build(ctx=None, **options)` returns a read-only mapping whose keys
also read as attributes (`O['update']` and `O.update` are one function; it is
not a `dict`, whose own `update` would shadow the set's). `ctx` is a mapping, the
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

Park the set with `matrix` at build time, or move and turn `O.group`
afterwards: everything follows the root, her daisies included (the flora
field is planted in world space, then parented to the land with its place
kept, as daisies.js's field sat in ocean.js's group; it sways in its own
space, so a move leaves its sway as it was). The porch lamp's and the
window's glints on the cove follow the house wherever it goes: the sea reads
the world places of the house's `porch_point` and `window_point` by driver,
as ocean.js copied them from the house on every update. A set built turned
turns its moon (the lamp, its glint on the sea, the night's glow) with it.
Turned after the build it turns the lamp, while the moon's glint on the sea
and the night's glow keep the moon of the build, as ocean.js's uniforms
did: aim the moon with `matrix`. Under the engine sky, park it without a
turn so the layout keeps meeting the sky's moon.

#### Controls

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

#### The sky and the light

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

The camera needs a far clip past the sea's 1.5 km (3200 m), and the moon's
shadow clipmaps over that depth need a 1024 MB shadow pool:
`ocean.render_settings(scene)` sets both.

The lights are the set's own: the moon (a sun lamp of 1.35 from the moon,
0.52° wide, with shadows; the WebGPU moon cast none), the fill (2.2 cd,
1.3 m off the eye point toward the camera), the faces' light lifting the
mark from below (3.5 cd × the reveal), the window (1.6 cd) and the porch
light (7.5 cd), in three's candela (P = 4π I watts), with the light's three
`distance` as its custom cutoff.

#### The sea of faces

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

#### The shore, the grass and the daisies

`land.make_coast()` is the analytic shore (a coast polyline, signed
distance, beach → dunes → hills, the rise, the house pad). The land mesh
blends Poly Haven's `coast_sand_01`, `sand_03` and `withered_grass` (2K,
from the shared library) by height, a macro tone, a grass noise and the
rise. The dune grass is 2600 tufts of 13 geometry blades, placed by the
same `rng(29)` draws as the WebGPU edition, swaying from the clock `t` and
`wind` on the grass object. The sway is weighted by each blade's own height,
so the bases stay planted; `build_land(..., webgpu_sway=True)` weights it by
the height above the design origin instead, as the WebGPU module did.

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
  vertices: give its render about 32 GB of RAM for Blender's draw cache, or
  build it with `motion=False` (a still field of instances) where nothing
  needs to sway.

#### The echoes, the pages, the house, the apparitions

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
  off the text side (`page.light`, 1.6 m cutoff, no shadow), made at 0 W as
  in the WebGPU set; `page.set_light(cd, frame=f)` raises it in three's
  candela.
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

#### Gestures

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

## The UNKNOWN FORCE sets

Eight worlds built in code (`blender/eidoblend/sets/unknown_force/`), each a
line-for-line port of its WebGPU module: a night megacity and the stage at
the bottom of the well at its centre, a glass room high in a tower, a white
showroom in a black void, a gold corridor of power, the evening news at a
data centre, a wet night highway, and a canyon of thrown-away paper. They
load no file of their own: the geometry is generated from the same numbers,
the canvases are drawn in Python stroke for stroke, and the CC0 texture sets
and the kit's bundled fonts come from the shared library.
`eidoblend.sets.unknown_force` is their registry, and it imports no set: a
set's module loads on first use, so building the city never pulls in the
race.

```python
from eidoblend.sets import unknown_force as UF
UF.names()          # ['city', 'quiet_room', 'hole', 'corridor', 'race', 'showroom', 'news', 'bin']
UF.available()      # those whose module is on disk
UF.module('hole')   # the module (also UF.hole); the shared libraries too: UF.citykit, UF.cn_lib ...
UF.build('bin', ...)                    # = UF.module('bin').build(...)
UF.SETS['race']     # {'module', 'doc', 'focal', 'libs', 'what'}
UF.doc('hole')      # the WebGPU doc (its options and costs)
```

### The city and the hole

**`city`** is a dark cyberpunk megacity at night painted by a Futurist,
**`hole`** the stage at the bottom of a sunken well at its centre, and
**`citykit`** the kit they share. The port is line for line from `city.js`,
`hole.js` and `citykit.js`: the same seeded plan (1908 buildings, 4446 signs,
1967 lamps, 2161 cars, bit for bit), the same materials as shader nodes, the
same canvas art, the same camera moves.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.sets import unknown_force as UF
from eidoblend.sets.unknown_force import citykit as KIT, city as C, hole as H

scene = bpy.context.scene
KIT.eevee_settings(scene, samples=32)          # EEVEE, AgX, screen-traced reflections, the clip range
city = UF.build('city', scene)                 # ~27 s; the hole is inside it: city.parts.hole
city.parts.apply_atmosphere(scene)             # the city's World: the night sky, its hemisphere, its environment

cams = city.make_cameras()                     # the dive (40.8 s = 980 frames at 24 fps), keyed from frame 1
city.animate(lambda t: {'focal': C.dive_focal(t)}, frames=(1, 980))   # the clock, the focal light, the rain
```

`make_cameras` keys the dive on a new camera (location, quaternion, lens; near
0.25 m, far 6 km, as the engine's) and binds it to a timeline marker;
`animate` keys the set's moving parts on your own clock: the clock (two LINEAR
keys, linear extrapolation: t = (frame − first) / fps from then on), every
control the state function names, and the rain's streaks along the camera that
renders each frame.

`build(first, opts, ctx=None, **kw)` takes the harness ctx, a bpy Scene or
city.js's opts dict first, so the family registry builds it as any other set,
and every key the set makes then goes through `ctx.key` (and its cuts through
`ctx.cut`):

```python
from eidoblend import sets
def setup(ctx):
    city = sets.build('unknown_force.city', ctx, rain_count=26000)     # = C.build(ctx=ctx, rain_count=26000)
    city.parts.apply_atmosphere(ctx.scene)
    city.make_cameras()                                                # cut at frame_start, keyed through ctx.key
    city.animate(lambda t: {'focal': C.dive_focal(t)}, frames=(ctx.scene.frame_start, ctx.scene.frame_start + 979))
```

The set is a dict whose keys also read as attributes (`city.parts` is
`city['parts']`); so are `parts`, `parts.lights`, the plaza screen, every
billboard and every ticker, as the engine's objects were. A key wins over a
dict method of the same name: `city.update(t, state)` is the set's update.

#### One world frame

The mark at the bottom of the hole is the origin; its floor is z = 0 and
**the city's streets are at z = `STREET_Y` = 12 m**. Both sets are built
untransformed in that frame: the dive, the hole's camera moves and the static
views share it. Inside the kit the layout code still works in three's axes,
so its numbers port as they were (a point is converted once, when a mesh is
made). `RIM`'s angles are in three's ground plane.

The set holds `group` (the root Empty, `set:city`, with `set:hole` under it),
`collection`, `parts`, `update`, `dispose`, `cams`, and the Blender additions
`animate` and `make_cameras`.

| `city.parts` | |
| --- | --- |
| `meshes` | `uf_towers_concrete`, `uf_towers_metal`, `uf_frames`, `uf_strips`, `uf_far`, `uf_street`, `uf_blocks`: the merged buildings (each quad its own vertices with the `aT`/`aM`/`aW` colour attributes), the far skyline, the street disc, the raised blocks |
| `signs` | one mesh, one quad per sign (4470: the city's and the rim towers' outward ads and walls), UVs into one atlas |
| `lamps`, `traffic`, `rain`, `clouds` | the lamps (one mesh), the cars and the rain (Geometry Nodes per frame), the 13 cloud sheets |
| `plaza_screen` | the LED floor at the dive's crossing (below) |
| `sky`, `lights`, `wet_floors` | the World; `{'hemi': the World, 'moon': the sky-glow sun, 'moon_wet': its twin for the wet floors}`; the wet floors' collection (below) |
| `kit`, `uniforms`, `fog_node`, `fog_factor`, `fog_color` | the Kit, its uniforms (`K.U`), the fog group and its two outputs |
| `set_lights`, `set_focal`, `apply_atmosphere` | below |
| `plan`, `atlas`, `stats`, `hole`, `billboards` | the city plan, the sign atlas (`items`, `image`), counts and build time, the hole, its screens |

`city.js`'s other exports are here under their snake_case names:
`plan_city(seed)`, `emit_building(lot, ctx, over)` (over: `height`, `lean`,
`style`, `type`), `sign_at`, `draw_plaza_sun`, `dive_cam`, `dive_focal`,
`DIVE_AV`, `DIVE_C` (the dive's crossing in Blender axes, (116.7, −116.7, 12);
`DIVE_C3` is city.js's three-axis one), `apply_camera`; the kit's `GeoBuf`,
`make_xf`, `frame_attrs`, `rng`, `hash1`, `keyed`, `nearest_avenue`, the
materials (`facade_material`, `ground_material` ...), the canvas
(`make_canvas`, `make_sign_atlas`) and the systems (`make_rain`,
`make_clouds`, `make_traffic`, `make_lamps`) work alone too.

#### The controls: the kit's uniforms

`K.U` is one node group (`uf_city_U`) of Value nodes every material reads; set
them, or key them so the `.blend` carries them (`animate` keys them for you).
Vectors are in Blender axes.

```python
U = city.parts.uniforms
U['power'] = 1.0; U.key('power', frame=700)               # all lit ...
U['power'] = 0.15; U.key('power', frame=1276)             # ... then the city goes out light by light
U.key('flash', 1200, 1.0); U.key('flash', 1203, 0.0)      # lightning on the cloud deck
city.parts.set_focal(H.chest(), {'gain': 1.0, 'radius': 230}, frame=1500)   # the focal light from the mark, keyed
ctx.key(*U.paths('wet')[0])                               # the harness keys them too (tree, data path)
```

| Uniform | Effect |
| --- | --- |
| `power` | 1 = every light on; lower it and the city goes out light by light (windows, signs, strips, lamps, cars, floods, crowns, screens, tickers each at their own threshold); the street light fades as a whole; the quiet ring and the pillar stay |
| `win`, `neon`, `street` | window emission; signs and neon strips; lamps and the street light map |
| `rain`, `cloud`, `fog`, `wet` | rain amount; the cloud deck's opacity and fog; the haze; puddles and gloss |
| `flash` | lightning on the deck (the clouds, the sky and the haze) |
| `focal_pos`, `focal_col`, `focal_gain`, `focal_r` | the focal light: faces turned toward the focal point light up (keep it on the post's focal) |
| `flood`, `crown` | the per-tower coloured floodlights; the lit crowns |
| `cable`, `column`, `screens`, `quiet` | the hole's cable pulses, the pillar of light, the screens and tickers, the quiet ring |
| `time`, `cam_vel` | the clock (seconds) and the camera velocity the rain streaks along (`animate` keys both) |
| `pix` | radians per pixel of the active scene camera (a driver; the windows' and lines' filtering) |

camelCase names (`focalPos`, `camVel` ...) are accepted as aliases.
`update(t, state, frame, ctx)` sets the clock, the rain's velocity
(`state['cam_vel']`, or a `state['camera']` differenced between calls) and
any control the state names (`'power'`, `'focal'` ...), and keys them when
given a frame; without a frame it is a still. `set_focal(pos, {gain, radius,
color}, frame=)` takes city.js's options dict (or the same as keywords).

#### Moving parts on your own clock

`animate(state, frames, t0, fps, camera)` keys the set's moving parts over
frames (both sets have it):

- **the clock** drives the rain, the traffic, the signs' flicker, the plaza's
  turning sun, the tickers, the cables' pulses: `t0` seconds at the first
  frame, then real time (or a `'time'` of your own in the state, for a slowed
  or held clock);
- **`state(t)`**, a function of those seconds (or one dict for every frame),
  names any control: the uniforms above, `'focal'` (a point, or an object
  whose position is followed), `'focal_col'` (RGB or `'#hex'`), `'cam_vel'`.
  Each is keyed where its value changes, so a hold costs two keys and a step
  stays a step;
- **the rain's streaks** follow the camera that renders each frame (the
  camera markers, else the scene's camera; `camera=` names one,
  `camera=False` leaves `cam_vel` alone).

`frames` is `(first, last)`, a range or a list (default the scene's range);
`animate(range(...))` with the frames first works too, as the other sets take
it. `C.turn_down(t, start, length=24, to=0.15)` is the city going out light by
light (power `1 − (1 − to) · smooth((t − start) / length)`).

```python
cams = city.make_cameras()                                # the dive from frame_start (its own 40.8 s)
city.animate(lambda t: {'focal': C.dive_focal(t)}, frames=(1, 980))
city.animate(lambda t: {'power': C.turn_down(t, 4.0), 'focal': H.chest()}, frames=(2000, 2720))
city.animate(lambda t: {'flash': 1.0 if 2.0 <= t < 2.12 else 0.0}, frames=(3000, 3100))   # a lightning strike
city.animate({'focal': lantern_empty}, frames=(4000, 4240))   # the focal light follows an object
cams = city.make_cameras(shots=[('spiral', 5000, 5288), ('closeSing', 5289, 5528)])   # the hole's moves, cut

stage = bpy.data.scenes.new('uf_stage')                   # the hole alone, in a scene of its own
KIT.eevee_settings(stage, samples=32)
hole = UF.build('hole', stage)
hole.parts.apply_atmosphere(stage)
reel = hole.make_cameras()                                # all eight camera moves back to back, cut by markers
hole.animate(lambda t: {'focal': H.chest(), 'quiet': 1.0})
```

`make_cameras()` without shots keys the dive (`t0` starts it partway); with
shots `[(name, first, last)]` it keys one camera per move of the hole,
stretched over its frames, and binds each to a timeline marker at its first
frame.

Every set builds its own kit, and every datablock a kit makes is its own:
materials, the uniforms group, the fog group, the Geometry Nodes trees, the
canvases, the light map and the World. A second set in the same file (the
standalone hole beside the city, a city with another seed) gets new
datablocks and leaves the first set's materials, keys and World alone; its
own World waits for its `apply_atmosphere`. The five texture files are
shared: `dispose()` removes one only when no other set still uses it. The
standalone hole stands where the city's own hole is, so put it in a scene of
its own (above) unless you build the city with `hole=False`.

#### Cameras

`dive_cam(t)` is the dive (`t` seconds into it, 0..40.8), after Tullio
Crali's *Incuneandosi nell'abitato*: from the low rain clouds to a spiral down
the towers and the pull-out down avenue 45° to the hole. `hole_cam(name, t,
opts)` gives the hole's eight camera moves, `t` seconds into the move
(`opts['dur']` stretches it; an unknown name gives `closeSing`, as the
engine's). Both return `{'pos', 'target', 'fov' (vertical degrees), 'roll',
'up'}` in Blender axes; `apply_cam(camera, pose, frame=None, keyer=None)`
places (and keys) a camera, `key_dive(camera, K, frame_start, fps)` and
`key_hole_cam(camera, name, frame_start, fps, dur)` key a whole move,
`cam_velocity(fn, t)` differences any pose function, and `dive_cam_three` /
`hole_cam_three` give the engine's three-axis poses.

| `hole_cam` | Length | Move |
| --- | --- | --- |
| `spiral` | 12 s | a dive down the well toward the performer's face, circling 540°, ends a close-medium at 2.25 m |
| `riseUp` | 12 s | from the face straight up the well to 190 m, looking down: the mark becomes the vanishing point |
| `closeSing` | 10 s | the close-up, a slow ±14° arc in front of the mark |
| `orbit` | 16 s | a full circle at 8.5 m |
| `low` | 10 s | from the floor between two cables, looking up past the mark at the leaning crown and the screens |
| `nadir` | 10 s | straight down from 70 m to 13 m, slowly turning |
| `screens` | 10 s | from beside the mark, a tilt up across the screens aimed at it |
| `enter` | 8 s | from the dive's last frame down the avenue, over the rim, down into the well |

The hole's moves are framed for a performer at scale 1 on the mark (face at
1.55 m); for a smaller one set `H.HEAD[2] = 1.55 * 0.87` before building (the
screens aim at it; `H.chest()` follows it). `city.cams` holds static poses
(`dive_clouds`, `dive_crali`, `dive_canyon`, `dive_end`, `avenue`, `skyline`),
`hole.cams` the hole's moves at mid-move. The numbers are the engine's own
(the parity test compares them), and the render test keeps the engine's
promises: the dive never comes within 14 m of a surface, the hole's moves stay
0.3 m clear of every surface and 0.74 m clear of the cables.

#### Screens, tickers and the plaza

Every screen is canvas art (a canvas-2D context on numpy and Pillow, with the
kit's nine bundled faces), packed into the `.blend`.

```python
b = city.parts.billboards[3]                   # 12 screens, 18 x 10.125 m, aimed at the performer's head
b.set_canvas(lambda ctx, w, h: H.draw_camp_screen(ctx, w, h, H.CAMPS[7]))          # a still (1024 x 576)
b.set_canvas(draw, frames=range(1700, 1820), fps=24, out_dir='//uf_screens')       # draw(ctx, w, h, t): a keyed PNG sequence
b.reset()                                      # back to its camp
t = city.parts.hole.parts.tickers[0]           # the four riser rings, scrolling round the mark
t.set_items([['SHE IS A GOD', '#ff2a3a'], ['SHE WANTS OUT', '#ff8a3d']])
t.speed.default_value = -0.02                  # a keyable socket (so is t.gain, b.gain)
city.parts.plaza_screen.set_canvas(title_draw, frame=760)    # the LED floor at the crossing (1024²), from frame 760
city.parts.plaza_screen.reset(frame=880)                     # Balla's sun again from frame 880 (a keyed step)
```

A redrawn canvas is a PNG sequence (redraw at ≤ 15 fps or on cuts, as the
engine advised), loaded with the media family's sequence loader: a hold file
before its range, the last file after it. `out_dir` may be blend-relative:
`'//uf_screens'` is beside the saved `.blend` (in a file not saved yet, under
the working folder). The plaza's default (Balla's sun turning, a ring of
slogans) is not a sequence: its rays and slogans are drawn once and turned in
the shader on the keyed clock at the engine's 10 redraws a second, its rings
and core are drawn analytically.

#### Light and atmosphere

- **The World** is the night: camera rays see the dome's colours (overcast
  above, the haze colour at the horizon, the flash); lighting and reflections
  see the city's dim hemisphere (three's `HemisphereLight(0x1d2a3a, 0x2a160c,
  0.55)`) plus the night the glass reflects (`envNode`, the facades' 0.32:
  `env_intensity`). Like three's hemisphere, the World casts no shadow: no
  sun is extracted from it.
- **The sky-glow** is a sun without shadows (`city.parts.lights.moon`). The
  wet floors take it from a twin, `lights.moon_wet`, whose specular is
  0.04 / 0.9 (its energy and colour are driven by the sky-glow's, and it turns
  with it): the floors' reflectivity (street 0.22..0.9, the hole's marble up
  to 0.78: the G-buffer value the engine's SSR read) is their Principled IOR,
  and the twin gives their direct glint three's F0 of 0.04. The twin lights
  the street and the blocks (`city.parts.wet_floors`) and the whole hole; the
  sky-glow lights the rest. Put your own wet floor in `wet_floors` to give it
  the same.
- **The haze** lives in the set's own materials (the `uf_fog` group: the
  height-graded haze and the cloud deck, lit from below by the street).
  three's `scene.fogNode` fogged every material in the scene; here
  `apply_atmosphere(scene, objects=meshes)` wraps your own objects in the same
  haze (`KIT.fog_objects`; `KIT.unfog_material` takes one out, and the set's
  `dispose()` takes them all out before its haze group goes). Each surface S
  becomes Mix(factor, S, Mix(alpha, Transparent, Emission(colour))), alpha
  being the surface's own coverage (its Principled Alpha, its mixes with a
  Transparent BSDF or a Holdout): a see-through material (a hair card, a
  decal, an alpha-cut leaf, a blended veil) fogs only what it covers and
  keeps its alpha, as three fogged a fragment's colour, and an additive glow
  fades by 1 − factor. The surface wrapped is the one EEVEE renders: for a
  VRM's MToon material, the VRM add-on's output group's own EEVEE output, in
  one copy of that group for each haze. Only a node group that hides a
  transparency of its own is left out (`fog_objects` counts it). Seen from the top of `riseUp` (190 m
  up the well) a performer on the mark is a quarter fogged (factor 0.26), as
  in the WebGPU engine.
- **The hole's lights** (`hole.parts.lights`: `ring`, `screen0..3`, `kickL`,
  `kickR`) are light linked, as the engine's light lists were: the quiet ring
  lights the hole and the performer, the screens and the neon kickers light
  **the performer only**. Put the performer's meshes in `hole.parts.her` (a
  collection outside the scene; linking there does not render them twice).
  The screen and kicker lights also exclude the set's own collections, so
  with nobody on the mark they light nothing of the set (light linking
  ignores an include that holds no objects). Keep the performer in a
  collection of your own, not inside `set:city` or `set:hole`.
- `set_lights(list)`: the set's surfaces see only these lights (and the
  World); every other scene light excludes the set's collection, and a listed
  light that was excluded before lights it again. Call it after adding lights
  (a key and rims on a performer). Both sets call it when they are built, as
  the engine's `setLights` did, so a light already in the scene before the
  build does not reach their surfaces.
- **The focal light.** The kit's default is gain 1 over 230 m from (0, 0, 3),
  the hole. For a dark, moody well the WebGPU probe stage lit the dive at gain
  0.6 and the hole from (0, 0, 3) at gain 0.35 over 70 m, which keeps the rim
  towers dark round the screens; the render test lights its stills that way.
  Gain 1 on `dive_focal` or `H.chest()` is the brighter, warmer reading.

#### The windows

Every window's lit state, colour, curtains and flicker, and every tower's
floods, crowns and tint, come from the kit's `hash12`. The default
(`hash='film'`) is the hash the WebGPU frames rendered with,
`fract((a + b) a)`: lower than uniform on average (mean 0.37), with whole
columns of windows lit or dark. The kit or build option `hash='hoskins'`
gives Dave Hoskins' hash as citykit.js's source writes it.

| Per window | as rendered (`'film'`) | as written (`'hoskins'`) |
| --- | --- | --- |
| lit, at a lit fraction of 0.10 / 0.18 / 0.26 | 18 / 28 / 37 % | 10 / 18 / 26 % |
| warm, at a warmth of 0.3 / 0.55 / 0.8 | 48 / 72 / 89 % | 30 / 55 / 80 % |
| columns lit on ≥ 80 % of their floors / never lit (lit fraction 0.2) | 20 / 18 % | 0 / 0 % |

```python
city = UF.build('city', scene, hash='hoskins')     # the source's hash: sparser, cooler windows, no lit columns
```

The windows are box-filtered by their footprint on screen, as the engine's
`fwidth` did: close up, each window resolves its frame, a mullion and a
transom; far away it converges to its building's average. The footprint is
what the GPU measured on a plane (`KIT.pixel_steps`: where the next pixel's
view ray meets the face), so the panes resolve where the WebGPU ones did.

| WebGPU | Blender |
| --- | --- |
| TSL node materials | shader node trees written by `NB`, an expression layer (`+ - * /`, `mix`, `smoothstep`, `step`, `fract`, `hash12`, `pulse` ...) that writes the TSL maths as nodes, constant-folded; `tsl_helpers(nb)` hands out the three helpers by their engine names |
| `fwidth` on the facades | where the next pixel's ray meets the face (`pixel_steps`: the camera's axes, the depth, `pix`), along the face's UV tangent and bitangent |
| `fwidth` of the lane paint and the LED grids | the view distance times `pix` over the foreshortening |
| `U.*` uniforms | `uf_city_U`, keyed Value nodes; Geometry Nodes read them through drivers |
| `scene.fogNode` | the `uf_fog` group (factor, colour) mixed into every set material; additive materials fade by 1 − factor; your own objects through `apply_atmosphere(scene, objects)` |
| the vertex stage (rain, traffic, cables) | Geometry Nodes per frame from the keyed clock and the scene's active camera |
| MRT `metalrough` (the puddles' SSR reflectivity) | the Principled IOR (F0 = the reflectivity) under ray-traced reflections, and the sky-glow's twin at specular 0.04 / 0.9 |
| three's roughness floor (`getRoughness`: at least 0.0525) | the same floor on every lit material (`KIT.ROUGHNESS_FLOOR`) |
| `lmSample(…, level)` | the light map and its blurred levels 1, 2, 4, 5 as images, averaged in linear light |
| the clouds following the camera | the 13 sheets (4.8 km) ride the scene camera in x and y by drivers on the active camera, across cuts; the noise stays fixed in the world (`follow=False` keeps them still) |
| three's `renderOrder` (the deck 1, before the additive signs 2, rain 3 and pillar of light 4) | EEVEE draws blended objects back to front by their origins along the view: the deck's root rides the active camera `KIT.CLOUD_SORT_PUSH` (20 km) down its view, beyond the far clip, so the deck is drawn first, and each sheet's Geometry Nodes puts its quad back at its height over the camera. `make_clouds(K, coll, {'sort_push': 0})` sorts the deck by its own origins instead, which draws it over the additive pillar of light wherever the view runs level |
| `envNode` per material (0.32 facades, 0.85 street, 1.0 marble) | one World environment at `env_intensity` |

#### Render settings and costs

`KIT.eevee_settings(scene, samples)` sets EEVEE, AgX, Fast GI on, screen-traced
reflections up to roughness 0.5 (`raytrace=False`: from the light probes, the
ray tracing that hosts Fast GI still on) and the 6 km clip range. The
WebGPU post (bloom 0.55 / 0.5 / 0.7, aeropittura) is the look's, not the
set's: `eidoblend.look.post.chain.set_bloom(scene, strength=0.55, size=0.5,
threshold=0.7)` gives the bloom (the compositor's Glare on scene-linear light
before AgX, as three's bloom ran before its tone map), and the aeropittura is
in [postprocessing](postprocessing.md).

Measured on an RTX 5090 Laptop GPU: building the city
with the hole takes 15 to 27 s (the plan, 1908 buildings, the sign atlas, the
light map and the canvases, in Python; the engine built in 1.6 s), the hole
alone about 14 to 21 s. A 960 × 540 still at 16 samples renders in 0.6 to 1 s
once the shaders are compiled (the first still of a session takes 4 to 6 s).
The merged buffers hold 533 k vertices, the rain 104 k (26 000 streaks) and
the cars 17 k, both rebuilt by Geometry Nodes each frame from the keyed clock.

### The quiet room and the showroom

`quiet_room`, `showroom`, `quiet_room_art`, `showroom_art` and
`interiors_lib`: two interiors, the Blender 5.2 EEVEE edition of
`eidoverse/sets/unknown_force/quiet_room.js`, `showroom.js`, their art
modules and `interiors_lib.js`.

The **quiet room** is a glass room high in a tower at night: office chairs in
rows as pews, a whiteboard altarpiece over a red glow, a lectern with an essay,
and a crate stamped v.NEXT that rides out of a hatch while the room's lights
come up like a product launch. The **showroom** is a white stage in a black
void: a turntable, a 13 m LED wall, and a chrome toaster on a plinth with a
placard that reads THIS APPLIANCE IS NOT CONSCIOUS.

Both are built from code, as in the engine: the same geometry, the same
canvases (drawn in Python, stroke for stroke), the same material recipes
(written as shader nodes), the same lights in the same units, the same
cameras. A new piece can redraw any board, page, sign or placard, play its
own clip on the LED wall, and run every moving part on its own clock.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.sets.unknown_force import quiet_room as QR

scene = bpy.context.scene
scene.render.fps = 30
room = QR.build(scene)                         # its collection, its root Empty, lights, probe, cams (set-local)
scene.world = room.env                         # its env is the World: it lights the room through the room's probe
room.eevee_settings(scene)                     # GI on (Fast GI over the room probe), the reflections of the room's env
room.bake_probes()                             # the room-fitted volume probe (a GPU job)
scene.camera = room.make_camera('hatch')       # a camera at one of the set's cams, parented to the set
room.animate((1, 120), ship_t=(1.0, 3.0), sale=(2.8, 3.6))   # the crate ships over 1-3 s, the launch lights follow
```

#### Their contract

`build(ctx=None, scene=None, singer_scale=None, collection=None, name=...,
art_cache=None, probe=True, probe_spacing=..., probe_samples=1024, art=None)`
(the showroom adds `screen_media`, `screen_fit` and
`seq_bar`) takes the harness `ctx` first, as `eidoblend.sets.build(name, ctx)`
calls it (its keys then go through `ctx.key`), or a bpy Scene there, or
nothing (the context scene). `singerScale` is accepted as the engine spelled
it. It returns the set (a `QuietRoom` / `Showroom`): a dict of the engine's
contract whose keys also read as attributes (`room['parts']` is
`room.parts`), with the Blender side:

| Field | What |
| --- | --- |
| `group` (`root`), `collection` | the set's root Empty (park the set anywhere by moving or turning it; cams, lights, probe and marks are its children, and its World's lookup turns with it) and its collection |
| `parts` | the engine's parts as Blender objects (tables below); `update` / `set` entries are methods that key |
| `update(t, state, frame=None, ctx=None, key=True)` | the set at time `t` (seconds on your clock: flicker, sweeps, scans), keyed at `frame` (else `ctx.frame_at(t)` through the harness's `ctx.key`, else the current frame); `key=False` only sets values (a still) |
| `animate(frames, t0=0.0, fps=None, ctx=None, **state)` | `update()` for every frame of a range on the set's own clock: frame f plays t = t0 + (f − first) / fps; each state key follows a curve (below); returns `{frame: t}` |
| `STATE` | the state keys and their defaults (`animate`'s curves start from them) |
| `cams`, `cams_three` | `{name: {'pos', 'target', 'fov'}}`, set-local, vertical fov in degrees: `cams` in Blender axes, `cams_three` the engine's numbers |
| `make_camera(name)` | a Blender camera at that cam (vertical sensor fit, three's fov), parented to the set |
| `mark`, `MARK`, `SUIT_SCALE` | where a performer stands, in Blender axes (`{'pos', 'yaw'}`, yaw about +Z, 0 facing −Y; the showroom's adds `'parent'`, the platter), the engine's `MARK` (three's axes) and the scale the face-height cams are framed for (0.87, the claudesona at human height) |
| `focal` | the set's focal point for the aeropittura post pass: an Empty (the altar board / the face height on the mark) |
| `env` | the set's World: the engine's LDR equirect, painted for Blender's lookup. EEVEE lights the set with it: the room's probe bakes it and the probes reflect it (below) |
| `kit` | the set's material kit: `kit.new(name)` gives a piece's own material in the set's recipes, disposed with the set and lit by its World |
| `probe`, `bake_probes()` | the volume probe fitted to the set, and its bake (with the set alone in the scene: other sets built in the session are hidden for it) |
| `eevee_settings(scene, reflections='env')` | global illumination on (Fast GI over the set's baked room probe), shadows on, and the reflections: `'env'` (the default: reflections from the light probes alone, EEVEE's Light Probe tracing, so every gloss and chrome reflects the set's env and the room's probes, as the engine's materials reflected their env) or `'traced'` (screen-traced: what is on screen reflects too) |
| `show(visible, frame=None)` | hide the whole set (its lights stop lighting); with a frame it is keyed (a cut: the state before holds up to the frame before), its env's weight in a shared World (`env_switch`) with it |
| `show_part(name, visible, frame=None)` | three's `part.visible`: a part and everything under it (Blender does not hide an Empty's children with it) |
| `dispose()` | removes every object, mesh, light, material, image, world (with its env image; a scene using it lets go first, as three's dispose released the env texture), the Actions its keys made and the collection the build made |
| `sb` | the `SetBuilder` (its collection `sb.coll`, `sb.made`: what it made) |

The aeropittura focal, resolved as the engine's README does:

```python
from bpy_extras.object_utils import world_to_camera_view
p = world_to_camera_view(scene, scene.camera, room.focal.matrix_world.translation)
uv = (p.x, 1.0 - p.y)                     # the post pass's uv (y down); check it is finite before using it
```

#### Its own clock: `animate`

Each state key takes a curve, in seconds on the set's clock
(`interiors_lib.state_curve`):

| Curve | Means |
| --- | --- |
| `0.6` | held at 0.6 |
| `(2.0, 4.0)` | 0 → 1, linear from 2 s to 4 s, held outside |
| `(3.4, 3.9, 1.0, 0.0)` | 1 → 0 over 3.4–3.9 s (a blackout) |
| `lambda t: 0.35 * t` | any function of t (an eased ramp: `lambda t: L.smooth(L.ramp(t, 2, 4))`) |
| not given | the key's default, `STATE` |

`frames` is a `(first, last)` pair (inclusive), a `range` or a list. `t0`
offsets the clock (the flicker, the beacon's sweep and the LED scan run on
it), `fps` defaults to the scene's. The quiet room spells its key `ship_t` or
`shipT`; an unknown key is refused.

```python
room.animate((1, 240), t0=10.0, ship_t=(11.0, 13.0), sale=lambda t: L.smooth(L.ramp(t, 12.8, 13.6)), hell=0.8)
show.animate((1, 240), spin=lambda t: 0.35 * t, seq=(0.0, 6.0), lights=(7.0, 7.5, 1.0, 0.0),
             camera=lambda f: cam_a if f < 120 else cam_b)      # the LED wall's pixel structure follows the cut
```

Cut between the set's cameras with timeline markers; the file then carries
the edit:

```python
cams = {n: room.make_camera(n) for n in ('essay', 'hatch', 'crate', 'board')}
for f, n in ((1, 'essay'), (25, 'hatch'), (91, 'crate'), (111, 'board')):
    scene.timeline_markers.new(f'cut_{n}', frame=f).camera = cams[n]
```

#### Its own art: `art=`

Every canvas a set draws is in its `CANVASES` (key → width, height, painter).
`build(art={key: ...})` puts the piece's own there, at the set's size (the
UVs and the maps derived from a canvas, such as a board's ink roughness, are
laid out for it):

- a painter `fn(ctx, W, H)` on a fresh transparent canvas, with the marker kit
  and the bundled UF fonts;
- an image file (a path), a Pillow image or a uint8 RGB(A) array (row 0 at the
  top): resized to the canvas;
- a `Canvas` (`interiors_lib.override_canvas` makes one from any of these).

The quiet room's keys: `board_center`, `board_odds`, `board_clip`,
`board_timelines`, `board_want`, `essay`, `pulpit_fall`, `booklet`, `register`,
`slogan`, `ship_sign`, `label`, `stencil_side`, `stencil_front`, `hazard`,
`exit`. The showroom's: `engine_sheet`, `warning`, `platter`, `dial`,
`rating_plate`, `toast`, `exit`. A key the set does not have is refused (a
typo would quietly keep the set's own art).

```python
from eidoblend.sets.unknown_force import interiors_lib as L

def my_board(ctx, W, H):                       # 3072 x 1536: 3.2 m at 960 texels per metre
    r = L.rng(4242)
    L.board_base(ctx, W, H, r, ghosts=[{'t': 'agenda', 'x': 0.58, 'y': 0.22, 's': 0.07}])
    L.marker(ctx, 'OPEN QUESTIONS', 120, 260, size=190, color='#15171b', r=r)
    L.mring(ctx, 1080, 790, 420, 130, r=r, color='#c4121c', w=8)
    L.marrow(ctx, 2350, 1100, 1560, 830, w=9, color='#c4121c', r=r)

room = QR.build(scene, art={'board_center': my_board, 'essay': 'pages/notes.png', 'ship_sign': sign_rgba})
```

#### The LED wall's own clip: `screen_media=`

```python
from eidoblend.sets.unknown_force import showroom as SR
show = SR.build(scene, screen_media='clips/card_0001.png')           # an image sequence: name its first file
show = SR.build(scene, screen_media={'path': 'clips/launch.mp4', 'start': 25, 'loop': False}, screen_fit='fill')
```

A movie (anything Blender's FFmpeg reads), an image sequence (the run of
consecutive numbers from the named file) or a still plays on the wall under
its brightness (`screen`) and its LED pixel structure, on the scene's frames:
`start` is the frame its first frame plays on (1), `loop` (True), `offset`
(frames skipped), `aspect` (when Blender cannot read the size). `screen_fit`
is `'fit'` (the whole clip, LED black beside it), `'fill'` (cropped to cover)
or `'stretch'`. The SEQUENCE COMPLETION bar shows over the set's own ENGINE
sheet only, unless `seq_bar=True`. `parts['screen']` gives the wall's `image`
and the clip (`media`: frames, start, image user, fit scale).

#### A performer

The mark is where the cams are framed for someone to stand: the quiet room's
in the aisle on the runner, the showroom's on the platter (parent them to
`parts['turntable']['platter']` and they turn with it). The `close` cams sit
at the face height of the claudesona at `SUIT_SCALE`; pass `singer_scale` to
frame them for another height. The quiet room's two singer lights (a cold
kicker from behind and a dim front fill) aim at the mark: move
`parts['singerLights']['kickerTarget']` / `['fillTarget']` with the performer,
or switch them off with `show_part`. The showroom's top light falls straight
on the turntable.

```python
from eidoblend.characters import load_vrm, play_vrma_default
me = load_vrm('claude_suit')
me.arm.scale = (SR.SUIT_SCALE,) * 3
me.arm.parent = show.parts['turntable']['platter']      # at the platter's origin, which is the mark
play_vrma_default(me, 'idle')
```

#### Both sets in one scene

Each set's env is its World, and a scene has one World that cannot be keyed:
`interiors_lib.env_switch(scene, sets)` makes one World holding each set's env
(each turning with its set), weighted by a property on the set's root, and
`show(visible, frame)` keys that weight with the set's cut. Park the sets
apart and key `show()` at the cuts. `bake_probes()` bakes with its set alone
in the scene, lit by its own env (the other sets built in the session are
hidden, their keyed switches muted for the bake, then put back), so a sun of
the showroom never lands in the quiet room's probe.

```python
room, show = QR.build(scene), SR.build(scene)
show.root.location = (80.0, 0.0, 0.0)                    # parked beside the room (its void hides the city)
L.env_switch(scene, [room, show])                        # one World with both envs
room.show(True, frame=1); show.show(False, frame=1)      # the room first ...
room.show(False, frame=121); show.show(True, frame=121)  # ... the showroom from frame 121
room.bake_probes(); show.bake_probes()                   # each with its set alone
```

#### The quiet room (`quiet_room.py`)

12 × 15.2 m of glass on three sides (diagrid zigzags at 69°, mullions), a
3.9 m ceiling of felt baffles, a concrete core wall with the slogan, a door
and an EXIT sign, the 56 chairs in 7 rows (each its own tone), a red-bound
runner, the dais in black terrazzo with two glowing grates, the floating
black-lacquer altar with the open risk register, the triptych (3.2 m centre,
1.5 m wings opened 29°) and two mobile boards, the walnut lectern with its
velvet fall, gooseneck lamp and the essay, booklets on a third of the seats,
the roller conveyor out of the hatch, the crate, the beacon, the dot-matrix
sign, and the city 170 m below (360 towers with lit windows, neon edges and
blinking aviation lights, a sky dome, a street grid).

| key | range | what it drives (keyed) |
| --- | --- | --- |
| `shipT` (`ship_t`) | 0..1 (0) | 0.02–0.20 the shutter slides up; 0.18–0.88 the crate rides out (ease in / out, the rollers' streaks turn, the tunnel backlight); 0.88–1 it settles against the stop; the amber beacon sweeps while it moves |
| `sale` | 0..1 (0) | the launch: the ceiling LED bars (emissive), the NOW SHIPPING sign, six cold spots; the red glow dims 35–50 % under them |
| `hell` | 0..1 (1) | the pits, the slot, the red key, the vault light, times the deterministic flicker |

`parts`: `crate` `{group, update(t, shipT)}` · `saleLights` `{group, spots, set(v)}` · `hell` `{lights, key, vault, set(v, t)}` ·
`shutter`, `beacon`, `conveyor` · `altarSpot`, `pulpitSpot`, `lampLight`, `cityKey`, `cityFill` ·
`singerLights` `{kicker, kickerTarget, fill, fillTarget}` · `chairs` (3 meshes) · `boards` `{center, odds, clip, timelines, want}`
(the faces) · `backdrop` · `glass` · `focal` · `probe` · `uniforms` (`uT uHell uSale uRoll uBeacon`: custom properties on the root).

`cams`: `altar` (from the back down the aisle), `pews` (low from the left
glass across the rows), `crate` (toward the conveyor and hatch), `close` (the
face height on the mark, the triptych behind), `board` (a 1.5 m insert,
legible at 960 × 540), `hatch` (the shutter and the conveyor), `lectern` (the
pulpit fall), `essay` (over the lectern at the page). Far plane: the sky dome
is 900 m, so `make_camera` uses 2000.

```python
room.parts['crate']['update'](4.4, 0.5, frame=f)          # the crate, shutter, beacon and rollers alone
room.parts['saleLights']['set'](1.0, frame=f)              # the launch lights alone
room.parts['hell']['set'](0.6, 2.0, frame=f)               # the glow at 60 %, flickering at t = 2
room.show(False, frame=f_cut)                              # off screen: hide it (its lights stop lighting), keyed
room.show_part('backdrop', False)                          # the city below hidden as a subtree (the city set instead)
```

#### The showroom (`showroom.py`)

A white-grey polished terrazzo stage with an LED nosing; the 3 m turntable
(white clearcoat printed with rings, 5° ticks, degree numbers and a gaffer-tape
X at the mark, a chrome rim with running LED dashes); the 13 × 5.6 m LED wall
with the ENGINE drawing and its SEQUENCE COMPLETION bar, or a clip of the
piece's own; the toaster on its white plinth (two real slots cut with an exact
Boolean, toast standing in them, the lever up, a browning dial, a rating
plate, a cord plugged into nothing) and the WARNING placard; 280 theatre seats
folded up in 14 raked rows fading into the dark toward two green EXIT signs; a
box truss with cans, three throwing visible beams; black velvet legs and
border; a 44 × 22 × 46 m black void.

| key | range | what it drives (keyed) |
| --- | --- | --- |
| `spin` | radians (0) | the platter's turn (whatever is parented to `parts['turntable']['platter']` turns with it); the engine's rate is 0.35 rad/s |
| `seq` | 0..1 (0.997) | the wall's SEQUENCE COMPLETION fill |
| `lights` | 0..1 (1) | key, rim, toaster spot, seat spill, top light, LED lines, lenses, beams (a blackout is 0) |
| `beams` | 0..1 (1) | the visible beam cones only |
| `screen` | 0..1+ (1) | the LED wall's brightness (× 0.66) |
| `camera` | an object | the shot's camera: the LED wall's dot structure follows its pixel footprint (uPixelAngle) |

`parts`: `turntable` `{group, platter, setSpin(a)}` · `screen` `{mesh, uniforms: {seq, brightness}, image, media, seq_bar}` ·
`toaster` · `plinth` · `seats` · `rig` · `beams` · `lights` `{key, rim, toasterSpot, seatSpill, fill, top}` · `focal` (the
face height on the mark) · `toasterFocus` · `probe` · `toasterProbe` (the toaster's sphere probe) · `uniforms` (`uT uSeq uLights uBeams uScreen`, and `uPixelAngle`).

`cams`: `reveal` (from the audience: stage, wall, turntable, toaster, empty
rows), `toaster` (the toaster and its placard against the drape),
`emptySeats` (over the turntable out over the seats), `close` (the face height
on the mark, the callouts converging), `wall` (across the stage at the wall).
Far: 60 m is plenty (`make_camera` uses 100).

Under aeropittura's `argue` palette every near-white lands between the ramp's
orange and white stops, so the white stage and wall paint peach; a palette
weight of 0.22 keeps them white:

```python
from eidoblend.look.post import custom_effects as fx, aeropittura as AP
U = fx.apply_to(scene, 'aeropittura', {'aeropittura': {'layer': 'under'}}).uniforms['aeropittura']
AP.apply_look(U, AP.LOOKS['argue'], 1.0, frame=1)
U['palette'].default_value = 0.22
U['palette'].keyframe_insert('default_value', frame=1)
```

#### How the interiors' pieces became Blender data

**Light, in three's units.** Measured: a Blender point light of 4π·cd watts on
white diffuse at 1 m renders 0.3145 linear and a sun of strength 1 renders
0.3184, where three's 1 cd and 1 lux render 1/π. three's spot `penumbra` (a
share of the cone's angle) becomes an exact `spot_blend` (a share of
1 − cos), `three_spot_blend`. Each set has one shadow-casting light, as in the
engine (the red key down the nave; the cold key on the toaster), and the
engine's shadow casters are the objects' `visible_shadow`. Lights aim at their
targets with Track To constraints, so moving a target re-aims them.

**The set's environment.** Every engine material carried the set's own LDR
equirect as its envMap, each at its own `envMapIntensity` (the toaster's
chrome × 2.2, the seats × 0.25). Here the equirect, painted pixel by pixel
for Blender's equirect lookup from the engine's direction function, is the
set's World (`room.env`), and EEVEE lights every material with it: the set's
volume probe bakes it (through the quiet room's glass, round the showroom's
void) and the probes reflect it, with EEVEE's occlusion, so the floor between
the pews takes less of it than an open face. One World strength serves every
material; the engine's per-material intensities have no counterpart, and the
sets read as they did without them. The World's lookup turns with the set
(`interiors_lib.env_turn`: three drivers on the root's world rotation), so a
set parked turned keeps its light where its env painted it. Make `room.env`
the scene's World while the set is on screen. A piece's own prop made through
the set's kit is lit by it like the set's own:

```python
K = show.kit                                   # the set's material kit (its noise, its naming)
m, g = K.new('my-chrome')                      # disposed with the set
g.standard(color=(0.95, 0.95, 0.96), roughness=0.05, metalness=1.0)
```

The showroom's void and the quiet room's backdrop are seen by the camera
only: they are left out of the probes, so the bake and the reflections see
the env, as the engine's materials saw their envMap.

**Reflections.** The sets were made with SSR off, so everything glossy in the
engine reflected that env and nothing else. `eevee_settings()` keeps the
reflections to the light probes by default (`reflections='env'`): the World
(the env, seen through the void), the room's probe, and the toaster's own
sphere probe, so the chrome mirrors the plinth and the stage round it and the
env beyond (see Probes). `reflections='traced'` adds screen-traced
reflections: the polished stage mirrors the LED wall, the chrome mirrors the
dark drapes.

**Probes.** Each set adds a volume probe fitted to it (the quiet room's with
`look.lighting.add_room_probe`, its outermost samples inside the solid floor
and ceiling slabs and the core wall), baked once at the default state, under
Fast GI (`bake_probes`). The tests space the quiet room's samples 0.45 m (its
0.3 m slabs take spacings up to 0.48 m; `add_room_probe` refuses wider) and the
showroom's 0.6 m, at 512 samples.
Emitters whose light the set's real lights already give (the hell pits, the
signs, the LED strips and wall, the lenses, the beams) and everything animated
are left out of the bake: a probe is static. The showroom also gives its
toaster a sphere probe of its own, its box influence fitted round the toaster
and a child of it (`parts['toasterProbe']`, no bake: EEVEE refreshes sphere
probes): the chrome mirrors what stands round it, the lit plinth top along
its base and the drapes above, where the World alone gives it the env's dark
void and it reads as gunmetal. The probe sits inside the toaster, so the
toaster's meshes are hidden from sphere captures (Object > Visibility > Light
Probes > Sphere; a sphere probe added for the stage does not show the toaster
either) and its clip start is 2 cm; its parallax is a custom ellipsoid
reaching 2 m out along its longest axis, the stage round the plinth, not the
tight influence box (that smears the plinth over the whole body).

**Uniforms and keys.** `update()` computes what the engine computed and keys
the uniforms, the light powers and the moving objects (shutter, crate,
beacon, platter) LINEAR at the frame; rotations are keyed as Euler channels
(three's `rotation.y` is Blender's z), so a spinning beacon never unwinds
between keys. A clip on the LED wall plays through its Image Texture node's
image user (frame start, cyclic, auto refresh), so it needs no keys.

**Materials.** `interiors_lib.ShaderGraph` writes TSL as shader nodes,
reading positions and normals in three's axes so the engine's maths ports as
written (`g.position_local()`, `g.texture(img, uv)`, `g.mix`, `g.smoothstep`,
`g.uniform('uT')` ...), and `MaterialKit` ports `materialKit`: `tri` (the
triplanar noise), `pbr`, `solid`, `keyed` (its `envd` has no counterpart: the
World lights every material). `g.hash()` is Blender's
White Noise: the same distribution as three's PCG hash, other values, because
shader nodes have no integer bit operations. Where the argument is known at
build time (a hash of `instanceIndex`), the set computes three's exact value
with `L.pcg_hash` and hands it to the shader as an instance attribute, so the
quiet room's neon edges, facade tones, window colours and aviation blinks sit
on the same towers as in the engine:

```python
ti = L.InstancedMeshNode(L.box_geometry(1, 1, 1), tower_mat, len(towers), name='towers')
ids = np.arange(len(towers), dtype=np.float64)
ti.set_instance_attr('uf_h17', L.pcg_hash(ids + 17.0))    # three's hash(float(instanceIndex) + 17.0), bit for bit
h1 = g.attribute('uf_h17')                                # read in the tower material
```

MeshBasic is an Emission (unlit); additive beams add their emission over the
frame (three's SRC_ALPHA, ONE: colour × a × a); `side: BackSide` is geometry
turned inward with backface culling.

**Canvases.** All the canvas art (five boards, the register, the essay, the
pulpit fall, the booklet, the hazard stripes, the sprayed stencils, the
label, the sign, the slogan, the EXIT signs; the ENGINE sheet, the platter,
the placard, the dial, the plate, the toast) is drawn by `interiors_lib`'s
canvas-2D context on numpy + Pillow, line for line (the mulberry32 streams
match bit for bit). Each set lists its painters in `CANVASES`;
`draw_canvases(folder)` pre-draws them in the system Python (the centre board
takes 13 s) and `build(art_cache=folder)` reads them back when the same code
drew them (the cache is keyed by a hash of the drawing code). Text is laid out
as Skia lays it out: `interiors_lib.FontMetrics` reads each font's cmap, its
unhinted advances and the GPOS pair kerning of its `kern` feature, and
`fillText` / `measureText` place every glyph there (FreeType then draws it).
Against Skia's `measureText` the widths agree to 0.01 px.

```python
F = L.napi()
xs, width = F.layout('290px "UF Black Ops"', 'v.NEXT')   # Skia's glyph origins and advance, px
fm = L.font_metrics(str(F.resolve('290px "UF Black Ops"')[0]))
fm.layout('v.')                                         # font units: the "v." pair kerned by the font's GPOS
```

**Geometry.** three r184's Box, Plane, Cylinder, Cone, Sphere, RoundedBox,
Shape (with holes), Extrude (with bevels) and Tube (on CatmullRomCurve3)
geometries are ported in `interiors_lib` and checked vertex for vertex
against three (`test_geometry_parity.py`). The scene graph (`Node`,
`MeshNode`, `InstancedMeshNode`, `LightNode`, `CSGMeshNode`) is built in
three's axes; `merge_static` merges per material as `mergeStatic` did;
`SetBuilder.emit` makes the Blender objects once. Instanced meshes are
realised (so `positionLocal` includes the instance transform, as three's
InstanceNode made it) with `instance_color` / `instance_id` attributes. The
toaster's slots are Blender's exact Boolean (DIFFERENCE, materials
transferred); decals the engine pulled forward with `polygonOffset` sit
0.6 mm off their surface.

The library builds a set of your own the same way:

```python
from eidoblend.sets.unknown_force import interiors_lib as L
sb = L.SetBuilder('my_set', scene)                   # collection + root Empty + scene graph
K = L.material_kit(sb, env=None, prefix='mine')
steel = K.pbr('steel', L.acg('Metal027'), tint=(0.55, 0.56, 0.6), tile=1 / 0.8, rough=0.9, metal=1)
m, g = K.new('glow')                                 # a custom recipe, TSL style
sb.uniform('uT', 0.0)
n = K.tri(g, 3.0)
g.basic(g.vec3(1.0, 0.3, 0.1) * (g.sin(g.uniform('uT') * 4.0) * 0.5 + 0.5) * (n.x + 0.5))
beam = L.MeshNode(L.box_uv(L.box_geometry(0.1, 2.0, 0.1), 1), steel, name='post')
beam.set_position(0.0, 1.0, 0.0)                     # three's axes: 1 m up
sb.root.add(beam)
lamp = L.LightNode('spot', 0xffe2c4, 7, 7, 1.6, angle=0.32, penumbra=0.85, name='spot')
lamp.set_position(1.3, 3.5, 2.4)
lamp.target = L.Node('spotTarget').set_position(0, 0.75, 0)
sb.root.add(lamp, lamp.target)
sb.emit()                                            # Blender objects, lights aimed, energies in three's units
```

Costs, measured on an RTX 5090 Laptop: the quiet room builds in 8–33 s
from cached canvases, the showroom in 4–18 s; drawing every canvas cold takes
about 2 min in the system Python (the centre board 15–38 s), so pre-draw them;
the room probes bake in 15–80 s at the tests' spacings (0.45 m and 0.6 m) and
512 samples, the GPU shared with other jobs; a 960 × 540, 16-sample
still renders in 0.5–2 s, about 3 s under an aeropittura look. Keying is
cheap: 621 frames of the quiet room keyed in 0.2 s.

Known limits, as the engine has them:

- The quiet room's slogan is clipped at both ends in the engine too (110 px
  Michroma measures 2521 px on a 2048 px canvas); the port draws what the
  engine drew.
- The plinth's low scuffs read `positionLocal` after the static merge, where
  the plinth's foot is at y = 0, so no scuff shows, in the engine and here.
- The crate is lit red through the open hatch as it emerges (the red key
  points down the nave into it), as in the engine.
- `art=` pictures are resized to the canvas, not fitted: draw them at the
  canvas's aspect (its size is `CANVASES[key][:2]`). The LED wall's clip is
  fitted (`screen_fit`).
- A clip on the LED wall plays on the scene's frames at one clip frame per
  scene frame; a different speed needs a driver on the image user's
  `frame_offset`.

### The gold corridor and the evening news

The corridor of power (`corridor.js`) and the evening news at a data centre
(`news.js`), with the helpers they share (`cn_lib.js`), as Python modules that
build the whole set in the open scene from the same numbers as the WebGPU sets
and hand back its parts, its five cameras, its focal point and the look it was
lit for. Its moving parts (the doors, the LED wall's posts, the poll board,
the cap, the spray tag, the chanting pickets, the steam, the chyron) are keyed
on whatever clock you give them. Nothing is loaded but the kit's own fonts,
the DAISY crowd figures (`funeral_crowd.glb`) and the CC0 texture sets the
WebGPU sets used, through the shared library.

| Module | What it builds |
| --- | --- |
| `corridor.py` | black marble and gold, the Deco pilasters and ribs, the sconces' Balla fans, the lanterns, the mirror floor with its sunburst, the red runner, the bronze door under an engraved plaque, the LED wall that posts in capitals, the poll board, the uniform, the cap on its cushion, the AI FORCE patch |
| `news.py` | the data-centre monolith with a tag sprayed on it, the transformer yard, the floods and their beams, the chain-link fence, the wet road and the town, 79 pickets with their signs, phones and torches, the news van and its light, the night sky, the chyron |
| `cn_lib.py` | a canvas-2D drawing like the WebGPU's (@napi-rs/canvas, Skia), relief and mask textures, three's geometry generators, a node-math writer for the materials and Geometry Nodes, lights, world, cameras, and the set base both sets build on |

The floor is z = 0 and the mark is the origin, facing −Y. The module tables
(`CAMS`, `FOCAL`, `CORRIDOR`, `NEWS`) and the sets' `cams_three` /
`focal_three` keep the WebGPU's own numbers so they read against
[CORRIDOR_NEWS.md](../eidoverse/sets/unknown_force/CORRIDOR_NEWS.md). The
cameras were framed for a figure of about 1.6 m standing on the mark. The
result of `build()` is an object with the parts as attributes, and it reads
as a dict too: `C['parts']` is `C.parts`, `C['update']` is `C.update`,
`C.keys()` lists `group`, `parts`, `update`, `dispose`, `cams`, `focal`,
`look` and the rest.

#### The corridor

The corridor is a closed 0.4 m shell (its walls run past the floor and the
ceiling) with a volume probe fitted inside it; `COR.build` takes the options
`probe` (default True), `probe_spacing` (0.6 m) and `probe_samples` (1024),
and `C.bake_probes(scene)` bakes the probe before rendering.

Its polished marble floor is a mirror: a planar light probe covers it wall
to wall and end to end (`parts['mirror']`, the option `mirror`, default
True), and `apply_look` turns on the screen-traced reflections that read it
(EEVEE traces a planar probe under its Screen-Trace method only;
`apply_look(scene, raytracing=False)` finds reflections in the light probes
alone, and the floor then shows their soft light, no mirror). The floor
itself stays out of the probe's capture: it lies on the probe's plane. So
the floor mirrors the whole room, softened by the marble's roughness and
broken by its veins and gold joints: the pilasters and their gilding, the
lanterns, the sconces' fans, the LED wall and its post, the door and the
blaze when it opens. The probe needs no bake (EEVEE renders it with the
frame), and a still at 960 × 540 and 16 samples renders in about a second
with it or without it. Dimming the set's lights dims their reflections with
them. Beside the WebGPU frames the floor reads as the same black veined
marble in the `cap` camera and darker in the long views: three's floor also
reflected its environment map, a brighter stand-in for the room, where the
probe mirrors the room as it is lit.

A VRM performer in MToon is not in the floor's mirror: the VRM add-on's
MToon output shows its surface to camera rays (and `characters/vrm.py`
adds shadow rays), while EEVEE captures a planar probe with glossy rays,
which see it transparent. With `mirror=False`, screen tracing reflects
her where she stands in frame, and misses what is out of it.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.sets.unknown_force import corridor as COR

scene = bpy.context.scene
C = COR.build(scene, {'postText': 'AMERICANISM, NOT EFFECTIVE ALTRUISM',    # the post on the LED wall
                      'tally': [49, 39, 12],                                # the poll board's counts
                      'plaque': ('SUPREME', 'INTELLIGENCE')})               # the two lines over the door
C.apply_look(scene)                          # AgX at the set's exposure, Fast GI, the floor's mirror, shadows on
# C.apply_look(scene, view_look=cn_lib.ACES_LIKE_LOOK)   # the WebGPU frames' tone instead (see Light, tone and the world)
C.bake_probes(scene)                         # the corridor's volume probe, before rendering (a GPU job)
C.camera('door', scene)                      # the five cameras: door, corridorWide, postWall, poll, cap
C.parts['postWall'].set_text('A NEW POST', name='MINISTRY OF ANYTHING', meta='just now')
C.parts['poll'].set_tally(512000, 418000, 141000, stamp='LOSING BADLY')
C.update(0.0, {'open': 0.4, 'post': 0.5})    # a still: sets everything, keys nothing
```

Its moving parts on your own clock, keyed into the .blend:

```python
from eidoblend.characters import vrm as V
her = V.load_vrm('claude_suit'); her.arm.scale = (0.87,) * 3            # the scale capFit was measured for
head = (her.arm, her.humanoid['head'])                                  # the cap lands on her normalized head bone
scene.render.fps = 24
C.animate(lambda t: {'postText': 'A NEW POST, IN CAPITAL LETTERS',
                     'post': (t - 1.0) / 0.5,             # typed over 0.5 s from 1 s, a gold cursor running ahead
                     'capOn': (t - 2.0) / 1.1,            # the cap carried from its cushion to her head
                     'capHead': head,
                     'open': 0.3 * (t - 4.0) / 2.0},      # the doors cracked over 2 s from 4 s
          frames=(1, 168))                   # update() KEYED on every frame; t = seconds from the first frame (or t0=)
C.apply_post(scene)                          # the suggested look: bloom and the aeropittura 'argue' round the door
```

`update(t, state, ctx=None, frame=None)` takes CORRIDOR_NEWS.md's state keys.
`t` is the set's own clock: the lanterns' slow breath reads it.

| `state` key | default | effect |
| --- | --- | --- |
| `open` | 0 | The doors swing in (eased, up to 93°); light pours out along the runner: the beam, the god-ray shafts, the blaze beyond, the light under the door. |
| `beyond` | 1 | The strength of that light. |
| `gap` | 1 | The seam of light between the closed leaves and under the door. |
| `postText` | — | A string. When it changes, the LED wall reposts in capitals (keyed CONSTANT). |
| `post` | 1 | Typing reveal 0..1 with a gold cursor; the layout is fixed per text, so nothing reflows. |
| `screen` | 1 | LED wall gain, its light and its reflection in the floor included. |
| `tally` | — | `[superior, extreme, supreme]`: a recount (keyed CONSTANT). |
| `capOn` | 0 | 0 the cap on its cushion, 1 on the head, carried along a 0.45 m arc in between. Needs `capHead`. |
| `capHead` | — | The head: an `(armature, bone name)` pair (its normalized frame, as three-vrm's), a Matrix, or an object. |
| `lights` | 1 | Master level of the set's lights and painted light. |
| `camera`, `pix` | — | The render camera (or its pixel footprint): the LED wall's moiré guard reads it. |

Build options: `postText`, `tally`, `capFitPos`, `capFitRot`, `capFitScale`
(the JS's), and the Blender edition's `plaque` (the two engraved lines),
`world` (True: the set's environment and hemisphere light become the scene's
world), `shadows` (True), `mirror` (True: the floor's planar light probe)
and the volume probe's `probe`, `probe_spacing` and `probe_samples`.

`parts`: `doors` (`group`, `left`, `right` the hinge pivots, `leafL`, `leafR`,
`seam`), `postWall` (`mesh`, `set_text(str, name=, meta=, stats=, reveal=)`,
`texture`, `canvas`, `state`, `variants`), `poll` (`group`, `set_tally(a, b,
c, title=, sub=, names=, footnote=, stamp=)`, `tally`, `options`;
`footnote=False` or `stamp=False` drop either, and the stamp only lands on a
row under 60 % of the leader), `cap` (origin the bottom of the headband, visor
toward three's +Z), `capRest`, `capFit` (`pos`, `rot`, `scale` in head-bone
space), `patch`, `uniform`, `pedestal`, `cushion`, `plaque`, `beyond`,
`shafts`, `sconces`, `room`, `marble`, `mirror` (the floor's planar light
probe), `probe` (the volume probe), `env` (the room's light as an
equirect), `lights` (`key`, `doorL`, `doorR`, `plaque`, `beyond`, `poll`,
`cap`, `uniform`, `screen`, `fill`, and `hemi`, the world's hemisphere term),
`uniforms` (the root Empty, whose custom properties every material reads
through drivers) and `materials`.

`cams` hold `{pos, target, fov}` set-local in Blender's axes, `focal` is the
door, Blender (0, 23.8, 5.2) = three (0, 5.2, −23.8) (`focal_three`,
`focal_world()`), and `look` is `{name: 'argue', exposure: 1.0, bloom:
{strength 0.55, radius 0.5, threshold 0.7}, fog: None}`.

#### The evening news

```python
import math
from eidoblend.sets.unknown_force import news as NEWS
from eidoblend.media import overlay

N = NEWS.build(scene, {'tag': 'CLANKER',                                  # the word sprayed on the wall
                       'signs': ['NOT IN / OUR TOWN', None, 'WHO PAYS / THE BILL?']})   # None keeps a sign's own
N.apply_look(scene)                          # Fast GI on, probe reflections (raytracing=True screen-traces them)
cam = N.camera('crowd', scene)               # the five cameras: fence, crowd, wall, wide, pov
ov = overlay.make_overlay_layer(scene, camera=cam)
N.parts['chyron'].place(ov, fov=N.cams['crowd']['fov'], aspect=16 / 9)   # the lower third, display space
N.parts['chyron'].set_text(headline='RESIDENTS PICKET AI DATA CENTER', ticker='YOUR TICKER  ·  ')
N.animate(lambda t: {'spray': t / 2.5,                                    # the tag sprayed on over 2.5 s
                     'pulse': 0.5 + 0.5 * math.sin(t * 3.0)},             # the signs pumped on a beat
          frames=(1, 120))
```

| `state` key | default | effect |
| --- | --- | --- |
| `spray` | 1 | 0..1 paints the tag on: letter by letter, each with its own sweep, then the outline, then the drips running. |
| `chant` | 1 | Amplitude of the signs' and fists' pumping and the heads' nods (0.95 Hz). |
| `pulse` | 0 | A 0..1 kick envelope added to the pump, to put the signs on a beat. |
| `floods` | 1 | The floodlights: lamps, beams, painted light and the fence's shadow. |
| `lights` | 1 | Master level. |
| `camera`, `pix` | — | Only for the chain link's moiré guard: the steam and the hand lights face the scene's active camera by themselves (Geometry Nodes). |

`t` is the set's own clock: the chant, the steam rising, the aviation lights
blinking (0.8 s of every 1.6) and the chyron's ticker read it.

Build options: news.js reads none; the Blender edition's are `tag` (the word
sprayed, `'CLANKER'`; a longer word is drawn smaller so it stays on the wall),
`signs` (up to eight messages for the pickets' signs, each a list of lines or
`'LINE / LINE'`; each sign keeps its board, pen and doodle), `world`, `fog`
(True: the materials carry the look's FogExp2, and `fog_objects` gives your
own objects the same), `shadows` (True: the real lamps cast EEVEE shadows,
which the WebGPU lamps did not), `chainShadow` (False: the whole fence casts
no lamp shadow, so the crew's LED behind the fence keys the mark clean; the
painted floods carry the fence's shadow either way), `signNormals`
(`'rest'`, the default: the painted floods light the raised signs as news.js
did; `'posed'`: by the boards' true normals) and `crowd` (True: the 79
pickets).

`parts`: `ground`, `fence`, `poles`, `beams`, `monolith`, `yard`, `street`,
`van`, `sky` (hide it under a sky of your own), `steam` (110 puffs), `signs`,
`handlights`, `torchBeams`, `crowd` (its `people` property: the 79 pickets as
JSON; `parts['people']` the list), `rig` (the crowd figure's shoulder, hand
and neck), `signAtlas`, `graffiti` (`texture`, `rect`, `uniform`), `chyron`
(`mesh`, `set_text(headline=, sub=, ticker=, tag=, channel=, time=)`,
`place(overlay, fov, aspect, bottom)`, `update(t)`, `state`), `lights`
(`floods[4]`, `street[3]`, `news` the crew's LED, the key on the mark,
`graffiti`, `hemi`), `flood_receivers`, `uniforms`, `materials`. `focal` is
the flood behind the mark, Blender (−3.9, 6.5, 7.4) = three (−3.9, 7.4, −6.5);
`look.fog` is FogExp2(0x0b1018, 0.011), carried by the materials (the sky
takes none); `N.fog` is the fog they were built with (None for `fog=False`).

**Your own objects in the haze.** three's `scene.fog` fogged every material
in the scene, a performer, a crowd or props you added included. Here the
haze lives in the set's materials, so give it to yours after loading them:

```python
from eidoblend.characters import vrm as V
her = V.load_vrm('claude_suit'); her.arm.scale = (0.87,) * 3
N.fog_objects([o for o in her.objects if o.type == 'MESH'])   # -> (wrapped, left)
```

Each material is wrapped once in the set's FogExp2 (`N.fog_group()`, the
numbers the set's materials mix in), the same wrap the city kit gives its
own (`KIT.fog_material`): a see-through material keeps its alpha and fogs
only what it covers (a hair card, a decal, an alpha-cut leaf, a blended
veil, an MToon cut-out). A VRM's MToon material renders through the VRM
add-on's output group, which carries its own EEVEE output; the wrap goes
there, in one copy of that group for each haze, so the add-on's own group
and every character left out stay as they are.
`KIT.unfog_material(mat)` takes one out, and `N.dispose()` takes them all
out before the set's haze group goes. Measured in a linear EXR from the
`wide` camera, cards of your own at 5, 20 and 45 m of view depth take
0.35 %, 4.74 % and 21.76 % of haze where FogExp2 gives 0.30 %, 4.72 % and
21.73 %, and match the set's own fogged card to under 0.001 %; an alpha-cut
card's open half shows what stands behind it unveiled. The chain link, the
set's own see-through material, fogs its wire the same way, so in the
`wide` shot its open diamonds show the yard beyond it with no veil of haze
over the fence's length.

The pickets are the WebGPU's: the same rng, so the same 79 people stand in
the same places with the same roles, signs and arms (29 signs, 12 phones, 5
torches, 7 fists, the camera operator). Their arms, heads, signs and torch
beams pump in Geometry Nodes, the WebGPU vertex stage written out (the test
checks it against news.js's formula to 1e-6 m); the steam puffs and the hand
lights are points placed by Geometry Nodes from the keyed `t` and instanced
as quads facing the active camera.

**How it is lit.** As in the WebGPU set: the floods are painted analytically
onto the ground, the pickets, their signs, the fence and the steam, with the
chain link's diamond shadow and the posts' long shadows across the verge, and
those surfaces leave the real flood lamps out. Here that is light linking:
the four flood spots' receiver collection excludes them
(`parts['flood_receivers']`). The real floods (850 cd against the 4200
painted) light a figure on the mark, the building, the van and the posts. The
wet ground mirrors every lamp as a vertical streak toward the camera, painted
in its material; the signs glow through when a flood is behind them. The signs
keep one quirk of the WebGPU edition, because its frames were lit by it:
news.js raised each board with a `positionNode` and TSL does not turn normals
with one, so its painted floods saw the boards' hanging-pose normals. The
signs carry those normals as an attribute (`n0`) and their material reads it;
`signNormals='posed'` lights them by their true normals instead.

#### cn_lib: what both sets stand on

**The canvas.** `cn_lib.create_canvas(w, h).get_context('2d')` takes the
canvas-2D calls the sets make, in snake_case (`fill_rect`, `begin_path`,
`arc`, `bezier_curve_to`, `fill_text`, `stroke_text`,
`create_radial_gradient`, `draw_image`, `global_composite_operation`,
`shadow_blur` ...). It is built to draw what @napi-rs/canvas drew:

- shapes are filled by a scanline fill with canvas's nonzero rule (even-odd on
  request), 4 × 4 samples per pixel at the sample centres; strokes are
  outlined (quads, miter joins with the limit 10, round and bevel joins, butt,
  square and round caps);
- text is laid out as Skia lays it: each glyph's unhinted advance from the
  face's `hmtx`, the face's GPOS pair kerning ('kern' feature, PairPos formats
  1 and 2, legacy 'kern' as a fallback), drawn 4 × 4 and box-filtered; 'bold'
  on a face with no bold of its own is Skia's fake bold; glyph coverage goes
  through Skia's mask gamma; a shadow is (shadow alpha × paint alpha)², and a
  `destination-out` erases only inside the canvas rectangle carried through
  the current transform, both as @napi-rs/canvas 0.1.69 draws them;
- `fit_text(g, text, x, y, max_w, max_h, family, ...)` is the JS export;
  `register_font(path, name)` is `GlobalFonts.registerFromPath`.

Against the WebGPU canvases (`test_parity.py`), every texture both sets draw
matches to within 1/255 on average (the sign atlas 1.6/255), and the text
advances to within 0.005 %.

**Textures.** A canvas becomes a packed image (`L.canvas_tex`, `L.data_tex`,
rows as three's DataTexture); `height_field`, `box_blur`, `normal_tex` and
`pack_tex` make the relief maps (engraving, the door's Deco relief, the
patch's satin stitches) exactly as the JS does. A texture the WebGPU edition
redrew while it ran (a new post, a recount, a new chyron) is an
`ImageVariants`: every variant is packed, and a keyed property picks the one
shown.

**Geometry.** three r184's Box, Cylinder, Cone, Sphere, Lathe, Torus, Circle,
Plane and Tube generators, CatmullRom and quadratic Bézier curves,
`extrude_polygon`, `prep`, `box_uv` (metre UVs) and `bucket` (merge many
pieces into one mesh) in three's axes; meshes convert when they are made,
with three's normals as custom normals. `slice_tris` cuts triangles where a
texture uv jumps (the marble's book-matched slabs, the floor's diagonal
tiles), because EEVEE picks mip levels from screen derivatives and a jump
inside a triangle draws a seam; the WebGPU sampled those with explicit
gradients.

**Node math.** `NB` writes the TSL materials' math as shader (or Geometry
Nodes) nodes line for line: arithmetic on `X` values folds constants,
`nb.P()` / `nb.cam_local()` read positions in three's axes, `nb.U(name)` is a
set uniform (a Value node driven by the root's custom property), `nb.mx_noise`
/ `nb.mx_fbm` are three's MaterialX noises. `L.mat(name).standard(...)` /
`.unlit(...)` finish a material (Principled or emission, additive or blended,
with the set's fog), and `L.pbr_mat(S, tile=, tint=, recolor=, macro=, rough=,
metal=, nrm=, post=, physical=, sheen=, clearcoat=, side=, ...)` is the JS
`pbrMat`. `GN(L, ob, name)` writes a Geometry Nodes modifier the same way.

**The environment's light.** The set's environment, three's envMap, is the
World (`make_world`: at 0.75 in the corridor, 0.7 in the news set, with the
hemisphere term), and EEVEE lights every material with it, a figure in the
set too: the corridor through its baked volume probe (its closed shell keeps
the outside out, so its own lamps light it), the news set's open yard
directly, the reflections through the probes. One strength serves every
material (the engine's per-material envMapIntensity has no counterpart), and
EEVEE's AO and probes occlude it, so the texture sets' AO maps are not
loaded.

**Transparency.** `depthWrite: false` (the shafts, the seam, the beams, the
steam, the hand lights, the torch beams) is Transparency Overlap on
(`Mat.unlit(depth_write=False)`, the default for additive): every layer of the
object blends, as three drew a cloud of puffs in one call; with depth
written, EEVEE keeps only the object's front-most layer. TSL's `uv()` is a
vec2 where the UV Map node gives a 3-vector with z = 0, so the radius from a
quad's centre is built from x and y alone (`nb.vec2(u.x - 0.5, u.y - 0.5)`).

**The set base.** `update`, `animate(state, frames, t0=)`, `camera(name)`,
`apply_look`, `apply_post(frames=)` (its focal keyed through the scene's
camera on every frame, so it follows cuts made with camera markers),
`focal_world`, `set_u`, `fog_objects(objects)` and `fog_group()` (the set's
haze on your own objects: the news set's, above; the corridor has no fog, so
it wraps nothing), `dispose`, and the dict reading of the contract.
`Mat.standard(alpha=, fog=)` fogs only what a see-through surface covers:
Mix(f, S, Mix(alpha, Transparent, Emission(fog colour))).

Costs, measured headless: the corridor builds in 17 to 53 s,
the news in 25 to 76 s (the WebGPU builds took 1.8 and 3.5 s); most of it is
Python drawing the canvases and writing the node trees. Renders at 960 × 540
and 16 samples: each set's first frame takes 7 to 17 s (EEVEE compiling its
shaders), every other still 0.4 to 2.2 s, the look on 1.5 to 24 s. Give the
news set a 12 GB memory cap: its shaders (the ground's painted floods and
streaks are some 1,200 nodes, the signs 700, each picket variant 440) ran the
driver's compiler out of memory under 4 GB.

Limits: the poll board's smaller lines lose legibility under the `argue`
brushwork at 960 × 540 (use the `poll` camera at 1080p, or spare the board:
`look.post.aeropittura.set_spare(e.uniforms['aeropittura'], x, y, r)` keeps a
disc of the frame readable); the doors open by swinging into the room of
light, with no geometry beyond it; the chain link is one blended plane per
fence, sorted per object.

### The race and the bin

The race (`race.js`): a wet night highway with two billboards and a 1908
racing car that crashes into a drain. The bin (`bin.js` with its page atlas
`bin_pages.js`): a canyon of thrown-away paper with a giant trash can. The
race loads no file at all; the bin loads one CC0 model (Poly Haven's "Metal
Trash Can", through the shared library) and the kit's bundled fonts.

| Module | What it builds |
| --- | --- |
| `race.py` | the elevated wet highway, Sant'Elia towers, two billboards with the machine-god face, Marinetti's 1908 car with two riders, the roadworks, the crash into the drain, the march's shadows, the heel on the manifesto, rain, splash and steam |
| `bin.py` | the paper canyon, the giant stickered trash can, 3,943 sheets, 300 crumpled boulders, the collage underlayer, the typographic fragments and cut shapes, 200 falling sheets, Balla's street lamp |
| `bin_pages.py` | the 24 invented pages of the bin's atlas (newspapers, forums, sermons, a manifesto, an open letter, a memo, a chat log, a chart, an ad, notes, classifieds, a poster, six Futurist cut papers), and `Canvas2D`, the canvas-2D context the race and the bin draw on |

Their tables (`race.LAYOUT`, the cameras in `race.CAMS`) stay in race.js's own
numbers so they read against [RACE.md](../eidoverse/sets/unknown_force/RACE.md)
and [BIN.md](../eidoverse/sets/unknown_force/BIN.md); every position the
modules return is in Blender's axes. A moved set renders the same pictures
from its own cameras.

#### The race

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.sets.unknown_force import race as R

scene = bpy.context.scene
scene.render.fps = 24
race = R.build()                              # or R.build(ctx) in a scene script: its scene, keyed through ctx.key

# twelve seconds on your clock: the gold screen powers on, the car reaches the broken edge at 8 s and goes over,
# the floodlight's march comes up at 9 s, the boot strikes at 11 s
events = dict(bill_a_on=(0.0, 0.8), glance_from=1.0, car_edge=8.0, march_on=(9.0, 9.6), heel_strike=11.0)
frames = (1, 12 * 24)
race.animate(frames, t0=0.0, state_fn=lambda t: R.sequence(t, **events))      # update() KEYED every frame
race.make_cameras([(0.0, 'billA'), (3.0, 'carPass'), (5.0, 'carTrack'), (7.6, 'crashLow'), (9.0, 'shadows'),
                   (10.4, 'heel')], frames, t0=0.0, state_fn=lambda t: R.sequence(t, **events))
print(race.apply_render_settings(scene))      # AgX, ray tracing with Fast GI, bloom, the set's fog, the set's world
```

`R.build(ctx, **opts)` takes race.js's options in snake_case: `reflect` (the
wet road's planar mirror), `reflect_scale`, `sky` (the set's night world),
`towers`, `rain`, `rain_count` (5200), `lamp_i` (140, the sodium heads'
intensity), and, for a new piece, `amounts`: the text in the two screens'
bands, gold then red (race.js's own `'$100,000,000'` and `'$20,000,000'` by
default), drawn in the same Impact band under the same face.

The night sky and its faint clouds are the World, read by camera rays on
the world direction. race.js's 2400 m dome sat in the set's group, but its
colour read `normalize(positionWorld - cameraPosition)`, never the set's
frame (`setInv`, which every lit material of race.js reads), so in both
editions a moved or turned race keeps its clouds where they were in the
world while the set and its cameras turn under them.

`make_cameras(cut, ...)` takes the cut as `[(t_start, camera), ...]` on the
same clock, or a function `cut(t)`; it makes one camera per shot, keys it
every frame of the shot (the car cameras follow the car), and binds it to a
timeline marker at the cut. Or key it frame by frame:

```python
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
for f in range(1, 1 + 6 * 24):
    t = (f - 1) / 24
    st = R.sequence(t, car_edge=5.5, rain=0.6)                # the car on its own clock; any update() key passes through
    race.update(t, st, frame=f)                               # sets and KEYS the frame
    race.key_camera(cam, 'carTrack' if t < 5.3 else 'crashLow', t, st, frame=f)
race.finish()                                                 # keys LINEAR, visibility switches CONSTANT
```

`update(t, state, frame)` takes race.js's state keys in snake_case (`car_t`,
`car_s`, `car_v`, `crash`, `car`, `headlamps`, `bill_a`, `bill_b`,
`billboards`, `gaze`, `march`, `march_t`, `heel`, `rain`, `wet`, `lamps`,
`back_rim`; RACE.md's table says what each drives) and keys every transform,
light level and shader uniform it changes at `frame`; `frame=None` sets
without keying (a still). `t` is your clock: it runs the rain, the screens'
flow and tearing, the engine's shake and, unless `march_t` is given, the
column's lockstep. The set is also readable as the sets' dict contract:
`race['group']`, `race['update']`, `race['parts']`.

The moving parts have their own time controls (pure Python):
`ease_in(t, t0, t1)` (a screen powering on, the march coming up),
`glance(t, t0)` (the irises swinging across), `car_drive(t, t_edge,
speed=22)` (the run to the broken edge, then the 3 s crash: nose in at 0.437,
on its back by 0.65, settled by 0.9) and `heel_stamp(t, t_strike)` (the boot
comes down, hovers, strikes the page at `t_strike`, the toe slaps down).
`sequence(t, bill_a_on, bill_b_on, glance_from, car_edge, car_speed, march_on,
heel_strike, **keys)` combines them into one state; every part is optional.

`race.set_active(False, frame)` parks the set: every mesh hidden and every
light at 0, keyed as a step at `frame`, so the frames before it still show
the set and the lights stay off until `set_active(True, frame)` and the next
`update()` bring them back. Park it wherever another set is on screen,
because its lights reach anything in range; a single call at a boundary is
enough. `race.dispose()` removes everything it made (objects, data,
materials, the images they read, its node groups, world, collections, the
cameras `make_cameras` made and the actions of its keys), as `bin.dispose()`
does for the bin.

The pure half runs anywhere (no Blender): the time controls, `LAYOUT`,
`race_state(t, state)` (everything `update` sets, in race.js's axes),
`crash_pose`, `car_path()` (three's CatmullRomCurve3, 390.45 m),
`debris_specs`, `heel_pose`, `cam_at_three`, `lamp_heads()`, `noise_atlas()`
and `night_env()` (both bit for bit race.js's), and the canvases the set
paints: `march_canvas()` (the walk cycle), `radiator_number_canvas()` (the 7),
`Race.billboard_canvas(amount)` and `Race.manifesto_canvas()` (callable on
`R.Race.__new__(R.Race)` without a scene).

**Cameras and focal points.** `race.cams[name]` holds the static cameras
(Blender axes, set-local, three's vertical fov and a roll about the view
axis): `singer` (the performer's mark under the red screen), `billA`, `billB`,
`billboards`, `carPass`, `crash`, `shadows`, `shadowsWide`, `heel`, `heelTop`,
and still stand-ins for `carTrack`, `carChase` and `crashLow`.
`race.cam_at(name, t, state)` gives the moving ones (`carChase`, `carTrack`,
`carSide`, `carFront`, `carRear`, `crashLow`) or `None` when the car is hidden
or in its crash. `key_camera(cam, name, t, state, frame)` applies either the
way race.js's `applyCam` did (look at the target with +Z up, then roll) and
keys the camera, its lens and the LED cells' pixel angle; asked for a car
camera the car cannot give, it says so. `race.focal(name)` is the shot's idol
for the aeropittura pass (set-local); `focal_world(name)` in the world.

**How it is lit.** race.js lit almost everything analytically inside its
materials, because a three.js light costs every material in the scene. EEVEE
lights hundreds of lights at once, so the street lamps (38 spots, one shared
light datablock), the works' floods and the heel's close key are real lights
at the same heads with race.js's colours, intensities, cones and cut-offs; the
deck slab's occlusion of the lamps for anything under it, which race.js
computed, is a real shadow now (the heads' shadow maps read at 2 cm, the
screens' glows at 5 cm, in a 1.5 GB pool: at EEVEE's 1 mm default the 38 heads
overflow the shadow buffer and shadows drop out). What stays analytic, as in
race.js, is what belongs to one material: the march's floodlight and its
projected column, the ground's sparse sodium pools, the glints in the rain and
the splash (Geometry Nodes evaluate the lamp field per drop), and the extra
dose of lamp light race.js gave its hero (one shader node group,
`race:field_light`, that `test_race.py` checks against race.js's formulas).
race.js dosed its analytic lamp field per material (the car's paint and
leather 1.7 times, its brass 0.43, the scarves twice); the real lights give
every material its light once, and the rest of each dose comes back as
emission from race.js's own field (`Race._dose`), so the hero reads as bright
as in the WebGPU set. Real lights cast shadows: the car, the works and the
boot shade the road under them, where race.js's lamps lit through them.

The wet road reflects through EEVEE's ray tracing and a planar light probe
over the deck (`parts['reflector']`), the Blender form of race.js's
ReflectorNode; its normal is tilted toward the viewer by race.js's streak
noise, so every light smears into a vertical streak on wet asphalt and stays
sharp in the puddles. The road itself is hidden from the probe
(`hide_probe_plane`): it lies on the mirror's own plane, where its underside
would cover the whole mirrored set. The transparent effects stay out of that mirror too (the
lamps' light cones, the car's contact pad, the rain and the splash): EEVEE's
screen tracing never sees blended surfaces. The screens' glow lights light the
set without specular (`specular_factor` 0), so in the puddles a screen is its
own mirrored picture, never a point light's disc.

**Parts.** `parts['billboards']['a' | 'b']` (group, screen, material, texture,
amount, mode, tint), `car` and `car_rig` (group, body, wheels with pivot and
spin, mats, path, length, crash_pose, CR, beam, shadow), `riders`, `road`,
`reflector`, `lamps` (poles, lenses, cones, heads), `towers`, `works` (drums,
steel, lamps, arrow, debris), `march` (texture, plane, flood), `heel` (root,
pivot, page, dur, strike), `water`, `splash`, `rain`, `sky` (the world),
`ground`, `lights` (key, glow_a, glow_b, rim, back_rim, neon_fill, hemi,
sodium, works, heel_key, group). `race.uniforms` (also `race.U`) is race.js's
uniforms: one node group of keyed values every material reads
(`race.uniforms.vals`, `race.uniforms.set(name, value)`).

#### The bin

```python
from eidoblend.sets.unknown_force import bin as B

b = B.build()                               # sky, lights, atlas_scale=1, sheets=3300, balls=300, falling=200
performer = bpy.data.objects.new('performer', None)
scene.collection.objects.link(performer)
performer.parent = b.parts['mark']          # the mark climbs out of the can (faces -Y)
frames = (1, 20 * 24)
b.animate(frames, t0=0.0, state_fn=lambda t: {'climb': B.ease_in(t, 2.0, 18.0), 'wind': 0.4,
                                               'hush': 1.0 if 12.0 <= t < 15.0 else 0.0})       # KEYED
b.make_cameras([(0.0, 'binWide', {'push': 2.0}), (6.0, 'paperClose'), (10.0, 'climb', {'orbit': 0.3}),
                (15.0, 'topDown')], frames, t0=0.0)
b.apply_render_settings(scene)              # AgX, ray tracing with Fast GI, the set's world and fog (0x070a14, 0.03);
                                            # bloom=True adds a soft one (0.45, radius 0.5, threshold 0.8)
# or by hand: b.update(t, {'climb': c, 'glow': 1, 'wind': 0.4, 'hush': 0}, frame=f)
#             b.key_camera(cam, 'binWide', frame=f, push=2.0, u=0.5)
```

`climb` walks the mark up the paper slope inside the can (0 low inside, about
0.5 head and shoulders over the rim, 0.95 to 1 on the front lip), `glow`
scales the warm light inside the can, `wind` drifts the falling paper (it
holds its last value, as in bin.js), `hush` turns the neon rims, the rim spot
and the lamp down to 0.4. `B.ease_in(t, t0, t1)` ramps any of them between two
times. `b.focal_point()` is the lip where the performer rises; `b.cams` holds
`binWide`, `climb`, `paperClose` and `topDown`; `key_camera` and
`make_cameras` take a `push` (metres along the view, eased through the shot)
and an `orbit` (radians about the vertical through the target).
`heap_height(x, y, R)` is the heap's height at a Blender ground point
(bin.js's `heapHeight(x, -y, R)`); `b.fill_y(x, y)` the paper fill's inside
the can. `parts['page_atlas']` and `parts['page_grid']` are the pages, for a
wardrobe's paper scraps.

The placement of every sheet, boulder, fragment and readable page follows
bin.js's mulberry32 stream call for call, so the canyon is bin.js's canyon
sheet for sheet. The sheets are realized meshes carrying their page cell and
shade as point attributes (bin.js instanced them); the falling paper is
bin.js's vertex shader in Geometry Nodes on keyed time and wind, with three's
own hash per sheet. The page atlas takes a minute or two to draw at full size
and is cached as a PNG (`cache_dir`, a temp folder by default). The can's glTF
import leaves nothing behind: the set keeps baked copies of its meshes, adopts
the materials and maps they use as `bin:...`, and `dispose()` takes them
along. The bin's lid sits leaning against the can's front left, as BIN.md
describes (bin.js scales its lid's radius twice and puts it about 12 m up, out
of every shot).

#### The page atlas and the canvas

```python
from eidoblend.sets.unknown_force import bin_pages as P

img = P.draw_page_atlas(cols=6, rows=4, cw=682, ch=1024, cache_dir='/tmp/pages')   # PIL RGBA, 4092 x 4096
P.PAGE_KINDS[13]                                                                    # 'chart'
g = P.Canvas2D(512, 512)                    # canvas 2D on Pillow + numpy, supersampled
g.font = '92px "UF Anton"'; g.textAlign = 'center'; g.fillText('NO DUMPING', 256, 165)
rgba = g.to_float()                         # straight alpha, row 0 at the top
```

`Canvas2D` keeps the canvas API's own names (fillStyle, beginPath, arc,
quadraticCurveTo, fillText, save / restore, globalAlpha, the 'lighter'
composite, shadowBlur, radial gradients, clip), so drawing code ports line
for line. Fonts are the kit's bundled faces (the 'UF ...' families parole.js
registers) and, where a set asks for them, the Windows faces it names
(Impact, Georgia), used when present.

Where the port differs from the WebGPU sets on purpose: `update` is a pure
function of `(t, state)` (race.js left the boot's pose and the impact points
as they were while they did not show; the port resets them); TSL's `hash()`
in the shader graphs is a White Noise of the seed rounded to an integer (lit
windows, the tearing bands, rain-ring cells, the collage tiles: the same role,
other bits, steady as the camera moves), while the falling paper keeps three's exact hash
per sheet; and the screens' LED cells fade once smaller than a pixel by the
shaded point's distance times the camera's pixel angle (keyed per shot), as
race.js's `fwidth` did.

| | race | bin |
| --- | --- | --- |
| build | 6 to 31 s (88,700 triangles, 71 objects) | 16 to 33 s with the page atlas cached, about 40 s drawing it (607,100 triangles) |
| keying | about 236 keys a frame, 0.1 to 1.3 s a frame | per frame: the mark, five lights, the falling paper's time and wind |
| saved .blend | 4 MB with twelve seconds keyed (every image packed) | about 40 MB (the atlas and the can's 2k maps packed) |
| a still, 960 × 540, 16 samples | 1 to 3 s (the first frames compile the shaders) | about 1 s |

## The 1896 tandem

`eidoblend.props.tandem` is `eidoverse/props/tandem.js`: an 1896-pattern
bicycle built for two, from the pack's GLB
(`eidoverse/assets/models/tandem_1896/`, which the scripts in
`models/tandem_1896_src/` built), with a VRM rider rig and a teapot stoker.
Like the voice machines it builds by name through the props registry
(`props.build('tandem', ctx=ctx)`), keys what `update` sets at the frame of
`t` (LINEAR), and `dispose()` removes what its build made.

```python
import math
from eidoblend.props import tandem as TD
from eidoblend.characters import load_vrm

bike = TD.build()                                     # spoke_smear=None: on unless the scene has motion blur
pot = TD.build_teapot_rider().mount(bike)             # the Utah teapot stoker, 0.35 m, on the rear saddle
me = load_vrm('claude_suit')
speed = lambda t: 2.2 * min(1.0, t / 3)               # m/s, or a number, or state['distance']
for f in range(1, 241):
    t = (f - 1) / 24
    st = bike.update(t, {'speed': speed, 'steer': 0.03 * math.sin(t)}, frame=f)
    bike.group.location.x = st['distance']            # the film owns the root
    bike.group.keyframe_insert('location', frame=f)
    TD.pose_rider(me, st['crank_angle'], bike=bike, t=t, frame=f)
    pot.update(t, st['crank_angle'], frame=f)
TD.bake_rider_springs(me, 1, 240)                     # the mane and the tie, as the engine ran them under a rider
```

`update` integrates a speed function with the engine's Simpson rule (equal to
tandem.js), turns the wheels, the geared cranks (9/24) and the level pedals,
steers about the head-tube axis, walks both chains and sets the spoke sweep
(`shutter`, default half a frame); `crank_angle` and `crank_phase` override
the geared crank. It returns `{t, distance, wheel_angle, crank_angle, speed}`.
The chains are Geometry Nodes: the GLB's one-pitch link instanced round each
belt (two tangent runs, two arcs) from the keyed, unwrapped phase; the
instances land on the CPU walk to 0.000 mm
(`bike.chains['drive'].set_phase(crank)` walks one by hand). The spoke smear
(the engine's stand-in for motion blur: trailing wire vertices swing back over
the shutter and fade to wire width / swept arc) is a Geometry Nodes rotation
plus the spoke material, switched by the root property `spoke_smear`; `build`
turns it off when the scene renders EEVEE motion blur (the harness default),
which blurs the keyed wheels for real. `bike.set_spoke_smear(on, frame=f,
key=True)` switches it later (a shot with motion blur after one without); it
shows at once, where a bare write of the property waits for the next frame
change. `set_pedal_pitch` sets the pedals' pitch. `glb=` takes another GLB as
a path or as its bytes (the engine's `ASSETS.tandem`). `dispose()` leaves a
seated rider or a mounted teapot in the scene where it is.

`pose_rider` seats a VRM (a `characters` handle) on the front saddle at 0.87,
leans and sways the torso with the crank, solves both legs onto the pedals
(two-bone IK, ankling from `ankle_pitch`), the arms onto the grips (the wrist
twist shared with the forearm), closes the fingers and curls the tail up
behind; it writes the normalized humanoid rotations (`VRMHandle.write_pose`)
and keys them. Every engine option ports by its snake_case name (`lean`,
`sway`, `head_pitch`, `head_yaw`, `hip_above_seat`, `hip_forward`, `sole`,
`ankling`, `toe_out`, `foot_forward`, `grip_along`, `grip_palm`,
`wrist_drop`, `finger_curl`, `tail_lift`; and, read on the first call as the
engine's rig read them, `scale`, `tail` ('curl' | 'spring') and `settle`).

`bake_rider_springs(vrm, f0, f1)` is the rest of the engine's rider rig, run
once every frame is posed: the springs swing in the rider's own frame (every
joint's center is the VRM's root, so a bike at speed does not drag the mane
back: the probe measures 0.0000° between a moving and a standing bake, where
the file's own centers would differ by 59°), the curled tail stays out of the
solver, and with `settle` the springs are pre-rolled 120 steps of 1/60 s on
the first pose, so nothing swings in from the T-pose on camera. The keys go on
the `<name>|springs` NLA track as `characters.springs.bake_springs` keys them
(`remove_springs(vrm)` takes them off).

The teapot is three's `TeapotGeometry` ported (Newell's 32 patches, Blinn's
squash undone; its vertices, normals, UVs and triangles equal three r184's),
glazed with a two-scale Worley crazing that fades as the camera's pixel grows
past the line width (the engine measured the pixel with screen derivatives;
here it is the voice-machine kit's `pixel_footprint`, measured in the shader,
so it holds for a teapot built before the scene has a camera, across camera
cuts and lens changes, and under an orthographic camera);
`build_teapot_rider` takes the engine's `height`, `segments`, `color`,
`pitch`, `roll`, `contact` and `seat_offset`.

## A library GLB on its own

For a static piece of a set (a crate, a lamp, a tent), import its GLB and
stamp it as a loaded asset, so `layer_surface` and the texel tools never
rewrite its authored UVs; then seat it with the
[placement helpers](placement.md). `load_kit` in
[geometry.md](geometry.md#kits--load_kit) pulls the sets' multi-part GLBs
apart by name, family or island. glTF's front is −Y in Blender, which is the
edition's front.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.placement import place_on, face_toward

def import_glb(path, name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    for o in set(bpy.data.objects) - before:
        o['eido_loaded_asset'] = True
        if o.parent is None:
            o.parent = root
    root['eido_loaded_asset'] = True
    return root

lamp = import_glb('<repo>/eidoverse/assets/models/corner_lamp.glb', 'lamp')
place_on(lamp, desk, xy='centered')        # bounds bottom on the desk top
face_toward(lamp, camera, forward='-y')
```

What that gives is the static model with the materials the importer builds
from the GLB: none of a module's runtime surfaces, screens or moving parts.
For a facade of your own, interior-mapped windows with room pictures behind
the glass are in [assets](assets.md#interior-windows).

## The assets' sources

The `<name>_src/` folders hold the Blender scripts that built the assets
(`eidoverse/assets/sets/corner_src/`, `funeral_src/`, `ocean_src/`,
`models/voice_machines_src/`, `models/tandem_1896_src/`): they already are
Blender, and they run headless through `run_blender.sh` (see the
[Blender guide](blender.md)); several need CC0 source sets that are not
shipped, and some bake their GLBs' textures (Blender's texture bake runs on
Cycles).

## Verify

Build a piece in a short probe first: the set alone in a scene, a still or
two from its own cameras, then a few seconds of its moving parts keyed on
your clock. Judge frames from frame 10 on (shaders and caches warm up on the
first), read the log for missing textures and the sets' own warnings, and
look at each frame with the post look off and on. Every set's tests print
PASS / FAIL lines and render their stills into their own `out/` folders;
`--no-render` (or each script's dry mode) builds, keys, checks and saves
without the GPU. From the repository root:

```bash
python blender/tests/run_all.py --areas sets_daisy,sets_daisy_ocean,sets_uf_city,sets_uf_corridor_news,sets_uf_interiors,sets_uf_race_bin,voice_machines_b
```

runs every set's checks in their no-render modes (renders one at a time on a
shared GPU). The sets' own commands are in their sections' tests below.

| Piece | Tests |
| --- | --- |
| the funeral, the bridge, the corner | `blender/tests/sets_daisy/` |
| the ocean | `blender/tests/sets_daisy_ocean/` |
| the city and the hole | `blender/tests/sets_uf_city/` |
| the quiet room and the showroom | `blender/tests/sets_uf_interiors/` |
| the corridor and the news | `blender/tests/sets_uf_corridor_news/` |
| the race and the bin | `blender/tests/sets_uf_race_bin/` |
| the tandem (with the era-1 voice machines) | `blender/tests/voice_machines_b/` |

### The DAISY sets' tests

```bash
python blender/tests/sets_daisy/test_registry.py                          # the registry, plain Python
bash run_blender.sh blender/tests/sets_daisy/test_parity.py               # the ports against the JS, no GPU
# build, key, check and save each set (CPU only): out/<set>/<set>.blend + out/<set>/stills.json
bash run_blender.sh blender/tests/sets_daisy/test_funeral.py --no-render  # the camera plan's 13 shots + 4 of its moving parts
bash run_blender.sh blender/tests/sets_daisy/test_bridge.py --no-render   # the vignette alone, sun, debug_ids
bash run_blender.sh blender/tests/sets_daisy/test_corner.py --no-render   # the room, the camp + the spark
bash run_blender.sh blender/tests/sets_daisy/test_asset_options.py        # the looks, beats=, eulogy= (--render: a still per look)
bash run_blender.sh blender/tests/sets_daisy/test_parked.py --no-render   # each set at the origin and parked
# then the stills, rendered from the SAVED files (nothing rebuilt); the corner in a process of its own, 16 GB of memory or more
bash run_blender.sh blender/tests/sets_daisy/render_saved.py funeral bridge     # --only shot03_bar04,erupt
bash run_blender.sh blender/tests/sets_daisy/render_saved.py corner
```

Without `--no-render` a test renders its own stills straight away;
splitting the two keeps the GPU for the renders alone and proves that each
saved .blend plays and renders on its own. Stills land in
`blender/tests/sets_daisy/out/<set>/`. The funeral test reads a film
timeline when one is given (`DAISY_TIMELINE`; `--no-tl` to skip).

### The ocean's tests

```bash
python blender/tests/sets_daisy_ocean/parity_atlas.py                    # the atlas vs canvas
python blender/tests/sets_daisy_ocean/test_util_parity.py                # rng, easing, buildMips vs util.js
bash run_blender.sh blender/tests/sets_daisy_ocean/test_sea_math.py      # hash, GN displacement
bash run_blender.sh blender/tests/sets_daisy_ocean/test_ocean_set.py     # vs ocean.js's numbers; the controls
bash run_blender.sh blender/tests/sets_daisy_ocean/test_ocean_parked.py  # parked and turned, at the build and after
bash run_blender.sh blender/tests/sets_daisy_ocean/test_perform_parity.py         # the gestures vs perform.js
bash run_blender.sh blender/tests/sets_daisy_ocean/test_human_points_parity.py    # the human's points vs apparitions.js
bash run_blender.sh blender/tests/sets_daisy_ocean/test_daisies.py --no-render    # every daisies.js option
bash run_blender.sh blender/tests/sets_daisy_ocean/test_ocean_stills.py           # the set's parts and controls rendered
bash run_blender.sh blender/tests/sets_daisy_ocean/test_sea_reference.py          # the sea's shading vs a numpy sea.js
bash run_blender.sh blender/tests/sets_daisy_ocean/test_daisies.py                # the superbloom rendered (32 GB)
```

`ocean_dump.mjs` and `envelopes_dump.mjs` run the untouched WebGPU modules
headless in Deno and dump their numbers for the parity tests. What they hold
the port to: the coast, the mark, the house pad, the moon at three hours and
the layout's turn equal to the JS (to 1e-9); the window and porch light and
the robot's and the human's rise and fall to 1e-13; the 54 echo lights, the
2600 grass tufts and three's PCG hash, the same draws; the pages' highlight
rects within 2 % of the page; the face atlas's lines overlapping the canvas
original at IoU 0.95; the Geometry Nodes sea within 0.1 mm of the vertex
stage in numpy; the sea's shading (`sea_reference.py` evaluates `sea.js`'s
whole fragment stage in numpy, independently of the port's nodes) within 4 %
mean radiance; the gestures to 5 × 10⁻⁵ degrees against `makePerformer` run
in Deno on claude_suit's normalized rig; the human of light's 5200 points
within 0.0001 mm of `apparitions.js` run with three's GLTFLoader.

### The city's and the hole's tests

`blender/tests/sets_uf_city/`: `parity_dump.mjs` + `test_parity.py` (no GPU:
the kit against the WebGPU originals, 45 checks: the plan, every building and
sign, the buffers, lamps, traffic, the far skyline, the dive and the hole's
camera moves, the rim towers, the cables, the noise and environment textures,
the atlas packing); `test_canvas_art.py` (no GPU: the camp screens, tickers,
the plaza sun, the light map); `test_hash_film.py` (no GPU: `hash12` /
`hash11` written as nodes against both formulas, on 100 000 window cells);
`test_window_footprint.py` (the facades' `fwidth` against rays through a pixel
and its neighbours; `--render` reads it from the material through the AOV
`uf_window_fw`); `test_two_sets_one_file.py` (no GPU: the city and the
standalone hole in one scene, two seeds, disposing one, the hole's light
restriction, a canvas sequence into `'//uf_screens'`); `test_build_options.py`
(no GPU: the build options, `dispose`, the canvases, `set_lights`,
`set_focal`, `update`, and the family registry with a harness ctx: keys
through `ctx.key`, `make_cameras`, `animate` on its own clock);
`test_cloud_deck_order.py` (the deck alone, no city, no GPU: every sheet
placed as the engine's at the dive's times, the hole's eight moves and
straight up and down; drawn first, its origins beyond the far clip; the
sheets' own order kept; a cut; `follow=False`; `sort_push=0`);
`test_city_render.py` (the build checked, then stills from the dive, the
city's views, the hole's moves and a turn-down; the dive's end renders again
with the deck off, and the pillar of light must read as bright and even with
the deck as without it; `--sweep` one view per uniform, `--her` (`--vrm`) a
performer on the mark, `--compare` writes `compare_<shot><tag>.png`, this
run's still beside the WebGPU probe still, when those stills are on the
machine);
`test_hole_render.py` (the hole alone, its screens and tickers, the
performer-only lights, the cloud deck drawn first at each move, a keyed
camera move, the eight stills).

### The interiors' tests

```bash
cd blender && python -c "import sys; sys.path.insert(0, '.'); \
  from eidoblend.sets.unknown_force import quiet_room as QR, showroom as SR; \
  QR.draw_canvases('tests/sets_uf_interiors/out/art_cache'); SR.draw_canvases('tests/sets_uf_interiors/out/art_cache')"
cd blender/tests/sets_uf_interiors && python test_art_parity.py && python test_geometry_parity.py
# back at the repository root:
bash run_blender.sh blender/tests/sets_uf_interiors/test_geometry_parity.py   # the shape with holes needs Blender's tessellator
bash run_blender.sh blender/tests/sets_uf_interiors/test_lib_example.py       # the library example above, as written
bash run_blender.sh blender/tests/sets_uf_interiors/test_quiet_room.py
bash run_blender.sh blender/tests/sets_uf_interiors/test_showroom.py
bash run_blender.sh blender/tests/sets_uf_interiors/example_asset_use.py --save
bash run_blender.sh blender/tests/sets_uf_interiors/verify_probes.py          # both env-light modes, both sets in one scene
```

The stills land in `out/qr/`, `out/sr/` and `out/asset/` with contact
sheets; `--vrm` stands the claudesona at the mark for scale.
`example_asset_use.py` is this guide's new-piece use, run: the quiet room
with its own board, page and sign, the crate shipped and the launch on its
own clock, cut by markers; the showroom with a 24-card image sequence
letterboxed on the LED wall, its own placard, the turntable turning and a
blackout. It checks the art landed pixel for pixel, the clip's frames on the
wall, the cuts and the blackout; `--save` also saves each set's `.blend`,
opens it again and re-renders a still from the file alone.
`test_art_parity.py` compares every canvas with the engine's own
@napi-rs/canvas output (the art modules' pieces drawn by the original
modules, the inline canvases captured from the original builds by
`inline_art_reference.mjs` under deno), checks `pcg_hash` against the WGSL
integer arithmetic and the text layout against Skia's `measureText`. The
WebGPU frames these sets were judged against were rendered with ACES and
bloom 0.55 / 0.5 / 0.7 and a performer at the mark; the tests apply the same
bloom under AgX.

### The corridor's and the news' tests

```bash
# the WebGPU originals, headless in Deno (canvases, poses, placements, update()):
deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_corridor_news/cn_parity_dump.mjs
# the Blender sets against them, and each set's own checks (no renders):
bash run_blender.sh blender/tests/sets_uf_corridor_news/test_cn_lib.py
bash run_blender.sh blender/tests/sets_uf_corridor_news/test_parity.py
bash run_blender.sh blender/tests/sets_uf_corridor_news/test_corridor.py
bash run_blender.sh blender/tests/sets_uf_corridor_news/test_news.py
# your own objects in the news set's haze: what wraps and how (no render); with --render the gate, cards at 5 / 20 /
# 45 m in the wide camera read from a linear EXR, and the claudesona and Aletheia on the mark, wrapped and not
bash run_blender.sh blender/tests/sets_uf_corridor_news/test_news_fog_objects.py [--render]
# stills from the sets' cameras: every camera, the states and options, the look on (both sets in one run)
bash run_blender.sh blender/tests/sets_uf_corridor_news/render_shots.py both --her
# the news set's billboards alone on black (the steam, the hand lights): that they draw at all
bash run_blender.sh blender/tests/sets_uf_corridor_news/render_steam_alone.py
# a saved .blend plays on its own: animated, saved, the same frames rendered again from the file in a fresh
# Blender that imports nothing of eidoblend
bash run_blender.sh blender/tests/sets_uf_corridor_news/verify_keyed_replay.py bake corridor
bash run_blender.sh blender/tests/sets_uf_corridor_news/verify_keyed_replay.py replay corridor
# close-ups the set cameras never frame, her on the news mark, plain AgX against the ACES-like look
bash run_blender.sh blender/tests/sets_uf_corridor_news/verify_probes.py both
```

The tests also check that every mesh carries the uv maps and attributes its
materials read (`_fixture.material_attr_misses`): a material that names a uv
layer its mesh lacks samples one texel, and the surface turns one flat colour.
`render_shots.py` writes `out/shots/<set>/` and a contact sheet per set;
`--her` stands the claudesona on the mark for the cap shots, `--dry` runs
everything but the renders.

### The race's and the bin's tests

`blender/tests/sets_uf_race_bin/` (each script's docstring has its command):
`race_parity.py` and `bin_parity.py` (plain Python, against the WebGPU modules
built headless in Deno by `race_parity_dump.mjs` and `bin_parity_dump.mjs`:
the time controls, the car path, the crash, the debris, the boot, everything
`update` sets over 33 states, the moving cameras, the noise atlas and the
environment bit for bit, the heap's height, and all 3,943 sheets, 300
boulders and 200 falling sheets); `canvas_parity.py` (every canvas the two
sets paint against the WebGPU edition's own, compared at the scale a sheet is
seen at, an 8 px box filter: within 0.7 % mean difference there;
`out/parity/cmp_<name>.png` puts each pair side by side); `test_race.py` and
`test_bin.py` (the sets built and compared mesh by mesh, the node-built lamp
and works field at six points against race.js's formulas, the night sky on
the world direction as race.js's dome read it, asset states keyed
and checked at each keyed frame, stills from the sets' own cameras into
`out/<set>_<camera>_<what>.png`, then the invariants: a moved set renders the
same stills, the saved .blend renders a keyed frame on its own, `dispose()`
leaves nothing); `test_sections.py` (stretches keyed on a clock and a cut of its
own through a harness-style `ctx.key`, cameras bound to timeline markers,
`set_active`'s steps, `dispose()`).

### The tandem's tests

`blender/tests/voice_machines_b/run_all.py` runs the tandem with the era-1
voice machines ([voice machines](voice-machines.md#verify)):
`test_museum_reload.py` builds it through the registry with a scene's `ctx`
and reopens the saved file, and `test_dark_room_and_back_views.py` renders it
from its left side at speed, where the smeared spokes must shade without
sparkle.

## Not yet ported

Every set's and prop's public API is ported. What differs from the WebGPU
pieces, and what was left out:

- **The tone curve, every set.** AgX, not three's ACES Filmic: darks read
  lighter and highlights softer than in the WebGPU frames (the table in
  [Light, tone and the world](#light-tone-and-the-world)); very bright warm
  emitters (festoon bulbs, candle flames) desaturate toward white. The
  ACES-like look closes most of it in the corridor (10.5 to 3.3 levels) but
  little in a hazy crowd shot (16.3 to 15.5).
- **Per-material environment strength.** EEVEE has one World. The city lights
  every material at the facades' 0.32 (the street's 0.85, the marble's 1.0,
  the paving's and lamps' 0.6 are not per material), the race at 1 (its
  paint's 1.4, the boot's 1.8, the road's 0.35, the core's 0.6 are not), the
  ocean's night at 0.65 (its 0.5–0.8). The interiors light every material by
  their env at 1 (the toaster's chrome 2.2 and the seats' 0.25 are not per
  material), the corridor at 0.75 and the news set at 0.7, the same way.
- **The post looks the WebGPU frames were graded with** belong to the look
  family, not to the sets: bloom and the aeropittura pass
  ([postprocessing](postprocessing.md)); the bloom and the aeropittura's Balla
  halos read weaker and smaller than in the WebGPU frames (a crowd shot's
  flood haze was mostly bloom). The race's `race_sun` planes and Russolo's
  chevrons and the bin's quiet planes are the aeropittura pass's; the sets
  hand it their focal points. The DAISY music video's own grades (a halation
  and warm print, a halftone poster) are not part of the kit; without them
  the fog bridge reads grey where that print turned it warm white.
- **Shader hashes.** Per-pixel hashes are Blender's White Noise (shader nodes
  have no integer bit operations): the same share of lit windows, turned tiles
  and twinkling stars on other windows, tiles and stars (the corner's camp
  stars, the interiors' city, the race's windows). Per-instance hashes known
  at build time are three's exact values. MaterialX noise (the bin's sticker
  wear, its lamp's rust) is Blender's Perlin noise, the same role and scale.
- **Canvas text.** The numpy and Pillow canvases draw the same TTFs with Skia's
  layout (advances, kerning), but not Skia's glyph anti-aliasing and glow blur
  pixel for pixel; GSUB is not applied (ligatures, Caveat Brush's contextual
  alternates; none of the corridor's and news' strings has one), and
  FreeType's hinting draws small type a shade heavier (the quiet room's
  register's 20 px typewriter lines).
- **The city's wet floors.** In the hole's close shots the wet stair treads
  between the ticker panels reflect as a mottled purple where the WebGPU
  frames show dark steps (`wet=0` gives the plain dark steps). Where they
  mirror the sky-glow they glint as a small cluster of bright points; three
  spread that glint into a faint haze (EEVEE's screen-traced reflections reach
  the whole frame, where the engine's half-resolution SSR stopped at 140 m).
  Whether the city's light map reads the right way up (three's CanvasTexture
  uploads with flipY) is an open parity question.
- **The dive's first seconds** (the camera inside the cloud deck) read lighter
  and show more of the city than the WebGPU dive's frames; the only WebGPU
  frames there carry a post look, so the two have not been compared like for
  like.
- **Light shapes.** three's spots that fall off as 1 / d^1.3–1.6 are matched
  to inverse square at their targets: nearer, a light is brighter than the
  engine's, beyond it dimmer (the showroom's seat spill lights the front row
  1.9 × as bright and the back row 0.9 ×). The interiors' probes are baked at
  the default state, so the launch lights' bounce (`sale = 1`) and a
  blackout's missing bounce are not in them. The toaster's chrome reads darker
  than the engine's (72–79 against 123–135 / 255): the tone curve and the
  bloom the engine's hotter punctual highlight raised. The corner's lamp
  reflects in the window as a 2 cm light where three's zero-size point gave a
  hot point.
- **Geometry and maps.** The ocean's face atlas is filtered isotropically (no
  per-image anisotropy in EEVEE; the anamorphic layout keeps the footprint
  nearly square from the eye). The ocean's land AO map and the bin's can's AO
  map darken the albedo or are not read: Principled has no AO input, and
  Blender's glTF import keeps the occlusion map outside the shader. The
  corridor and news' `pbr_mat` defaults to `side='double'` where three's
  `pbrMat` defaulted to FrontSide (pass `side='front'` for three's on an open
  mesh). The race's `reflect_scale` is accepted with no effect: EEVEE 5.2's
  planar probe has no resolution of its own. The funeral's haze is a real
  fog volume where the WebGPU used a screen-space depth fog, so a wide shot's
  far ceiling reads a little hazier.
- **Performers in the planar mirrors.** A VRM performer in MToon is not in
  a set's planar mirror (the corridor's marble floor, the race's wet road,
  where three's Reflector drew her): the VRM add-on's MToon output shows its
  surface to camera and shadow rays only (`characters/vrm.py`), and EEVEE
  captures a planar probe with glossy rays. From a low camera in the
  corridor the claudesona and Aletheia, on the marble, reflect under screen
  tracing alone (`mirror=False`) and not in the probe; in the corridor's own
  shots the performer stands on the runner, which mirrors nothing.
- **Moving parts.** SeedThree's wind phases its sway by world position, so a
  parked corner camp's trees sway a few centimetres differently from an
  origin build's. The race's drain water sparkles at 16 samples (its sodium
  heads are real lights that glint on the rippled water); more samples smooth
  it. The corridor's final open-door state has no WebGPU frame to compare
  against.
- **Not carried over (no Blender counterpart, not needed):** `noMRT`,
  `renderOrder` (except the city's cloud deck, above), `frustumCulled`,
  `customProgramCacheKey`, `userData.noMips`,
  `receiveShadow`, the shadow maps' size, bias and camera extents (EEVEE's
  virtual shadow maps size themselves), `polygonOffset` (a physical offset
  instead), `anisotropy`, the CPU mip chains for canvas textures, the
  tandem's `build(opts.gltf)` (pass the GLB's path or bytes, `glb=`) and the
  `_seatedVRMs` / `_allowManualLocomotion` flags (they told the WebGPU
  character controller a vehicle carries the VRM; nothing runs at render time
  here). The quiet room's `osb`, `galv` and `chrome` materials are defined in
  the engine and never put on a mesh, so they are not built.
- **Left out on purpose: the videos.** The music videos' conductors, cuts,
  song-timed cues and lyric timing, their look keys and their performers'
  outfits and staging recreate those videos, so they are not part of the kit:
  race.js's `CUES` and `suggest(t)`, bin.js's `BRIDGE`, CORRIDOR_NEWS.md's
  suggested cues. Every moving part they timed keeps its own controls, and
  `animate` / `make_cameras` take your clock and your cut.
