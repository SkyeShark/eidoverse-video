# The quiet room and the showroom

[Main instructions](../../AGENTS.md) · [Props and sets](../props-and-sets.md) · [Camera and lighting](../camera-lighting.md) · [Tool inventory](../../docs/TOOLS.md)

**`eidoblend.sets.unknown_force`** `quiet_room`, `showroom`, `quiet_room_art`,
`showroom_art` and `interiors_lib`: two interiors from eidoverse's UNKNOWN
FORCE work, free for any piece, in their Blender 5.2 EEVEE edition
(`eidoverse/sets/unknown_force/quiet_room.js`, `showroom.js`, their art modules
and `interiors_lib.js`).

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
Everything that moves is keyed, so a saved `.blend` plays and renders any
frame on its own. Blender is Z up; the sets are built in three's axes and
converted once, three (x, y, z) → Blender (x, −z, y).

```python
import sys; sys.path.insert(0, '<worktree>/blender')
import bpy
from eidoblend.sets.unknown_force import quiet_room as QR

scene = bpy.context.scene
scene.render.fps = 30
room = QR.build(scene)                         # its collection, its root Empty, lights, probe, cams (set-local)
scene.world = room.env                         # its env for the camera; its materials carry its light (the engine's envMap)
room.eevee_settings(scene)                     # indoors: fast GI off; reflections of the room's env
room.bake_probes()                             # the room-fitted volume probe (a GPU job: through heavy.sh)
scene.camera = room.make_camera('hatch')       # a camera at one of the set's cams, parented to the set
room.animate((1, 120), ship_t=(1.0, 3.0), sale=(2.8, 3.6))   # the crate ships over 1-3 s, the launch lights follow
```

## The sets' contract

`build(ctx=None, scene=None, singer_scale=None, collection=None, name=..., art_cache=None, probe=True, probe_spacing=..., probe_samples=1024, art=None, env_light='material')`
(the showroom adds `screen_media`, `screen_fit` and `seq_bar`) takes the
harness `ctx` first, as `eidoblend.sets.build(name, ctx)` calls it (its keys
then go through `ctx.key`), or a bpy Scene there, or nothing (the context
scene). `singerScale` is accepted as the engine spelled it. It returns the
set (a `QuietRoom` / `Showroom`): a dict of the engine's contract whose keys
also read as attributes (`room['parts']` is `room.parts`), with the Blender
side:

| Field | What |
| --- | --- |
| `group` (`root`), `collection` | the set's root Empty (park the set anywhere by moving or turning it; cams, lights, probe and marks are its children, and the materials' env light turns with it) and its collection |
| `parts` | the engine's parts as Blender objects (tables below); `update` / `set` entries are methods that key |
| `update(t, state, frame=None, ctx=None, key=True)` | the set at time `t` (seconds on your clock: flicker, sweeps, scans), keyed at `frame` (else `ctx.frame_at(t)` through the harness's `ctx.key`, else the current frame); `key=False` only sets values (a still) |
| `animate(frames, t0=0.0, fps=None, ctx=None, **state)` | `update()` for every frame of a range on the set's own clock: frame f plays t = t0 + (f − first) / fps; each state key follows a curve (below); returns `{frame: t}` |
| `STATE` | the state keys and their defaults (`animate`'s curves start from them) |
| `cams`, `cams_three` | `{name: {'pos', 'target', 'fov'}}`, set-local, vertical fov in degrees: `cams` in Blender axes, `cams_three` the engine's numbers |
| `make_camera(name)` | a Blender camera at that cam (vertical sensor fit, three's fov), parented to the set |
| `mark`, `MARK`, `SUIT_SCALE` | where a performer stands, in Blender axes (`{'pos', 'yaw'}`, yaw about +Z, 0 facing −Y; the showroom's adds `'parent'`, the platter), the engine's `MARK` (three's axes) and the scale the face-height cams are framed for (0.87, the claudesona at human height) |
| `focal` | the set's focal point for the aeropittura post pass: an Empty (the altar board / the face height on the mark) |
| `env` | the set's World: the engine's LDR equirect, painted for Blender's lookup; with `env_light='material'` (the default) the camera sees it and it lights nothing, because every material carries the env's light at its own intensity (below) |
| `kit` | the set's material kit: `kit.new(name)` / `kit.envd(m, i)` give a piece's own material the set's env light |
| `probe`, `bake_probes()` | the volume probe fitted to the set, and its bake (with the set alone in the scene: other sets built in the session are hidden for it) |
| `eevee_settings(scene, reflections='env')` | fast GI off (indoors it lights contacts with the world through the walls), shadows on, and the reflections: `'env'` (the default: ray tracing off, so every gloss and chrome reflects only the set's env, as the engine's materials did) or `'traced'` (screen-traced: what is on screen reflects too) |
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

## A new piece's own use

### Its own clock: `animate`

Each state key takes a curve, in seconds on the set's clock
(`interiors_lib.state_curve`):

| Curve | Means |
| --- | --- |
| `0.6` | held at 0.6 |
| `(2.0, 4.0)` | 0 → 1, linear from 2 s to 4 s, held outside |
| `(3.4, 3.9, 1.0, 0.0)` | 1 → 0 over 3.4–3.9 s (a blackout) |
| `lambda t: 0.35 * t` | any function of t (an eased ramp: `lambda t: L.smooth(L.ramp(t, 2, 4))`) |
| not given | the key's default, `STATE` |

`frames` is a `(first, last)` pair (inclusive), a `range` or a list.
`t0` offsets the clock (the flicker, the beacon's sweep and the LED scan run
on it), `fps` defaults to the scene's. The quiet room spells its key
`ship_t` or `shipT`; an unknown key is refused.

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

### Its own art: `art=`

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

### The LED wall's own clip: `screen_media=`

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
sheet only, unless `seq_bar=True`. `parts['screen']` gives the wall's
`image` and the clip (`media`: frames, start, image user, fit scale).

### A performer

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

### Both sets in one scene

The engine kept every set in the conductor's one scene, parked apart and
hidden while off screen, each material lit by its own set's env. With the
default `env_light='material'` that holds here too: park the sets apart, key
`show()` at the cuts, keep a World that lights nothing (either set's `env`),
and each set is lit by its own env (`verify_probes.py` renders the room
under the showroom's World as it renders alone). `bake_probes()` bakes with
its set alone in the scene (the other sets built in the session are hidden,
their keyed switches muted for the bake, then put back), so a sun of the
showroom never lands in the quiet room's probe.

With `env_light='world'` the env is the World, and a scene has one World that
cannot be keyed: `interiors_lib.env_switch(scene, sets)` then makes one World
holding each set's env, weighted by a property on the set's root, and
`show(visible, frame)` keys that weight with the set's cut (a set built with
`'material'` joins it for the camera only).

```python
room, show = QR.build(scene), SR.build(scene)
show.root.location = (80.0, 0.0, 0.0)                    # parked beside the room (its void hides the city)
L.env_switch(scene, [room, show])                        # one World with both envs (needed for env_light='world')
room.show(True, frame=1); show.show(False, frame=1)      # the room first ...
room.show(False, frame=121); show.show(True, frame=121)  # ... the showroom from frame 121
room.bake_probes(); show.bake_probes()                   # each with its set alone
```

`verify_probes.py` renders the two shots of such a cut and the same shots of
each set alone in a scene of its own and compares them.

## The quiet room (`quiet_room.py`)

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

`update(t, state)` / `animate(...)`:

| key | range | what it drives (keyed) |
| --- | --- | --- |
| `shipT` (`ship_t`) | 0..1 (0) | 0.02–0.20 the shutter slides up; 0.18–0.88 the crate rides out (ease in / out, the rollers' streaks turn, the tunnel backlight); 0.88–1 it settles against the stop; the amber beacon sweeps while it moves |
| `sale` | 0..1 (0) | the launch: the ceiling LED bars (emissive), the NOW SHIPPING sign, six cold spots; the red glow dims 35–50 % under them |
| `hell` | 0..1 (1) | the pits, the slot, the red key, the vault light, times the deterministic flicker |

`parts`: `crate` `{group, update(t, shipT)}` · `saleLights` `{group, spots, set(v)}` · `hell` `{lights, key, vault, set(v, t)}` ·
`shutter`, `beacon`, `conveyor` · `altarSpot`, `pulpitSpot`, `lampLight`, `cityKey`, `cityFill` ·
`singerLights` `{kicker, kickerTarget, fill, fillTarget}` · `chairs` (3 meshes) · `boards` `{center, odds, clip, timelines, want}`
(the faces) · `backdrop` · `glass` · `focal` · `probe` · `uniforms` (`uT uHell uSale uRoll uBeacon`: custom properties on the root).

`cams`: `altar` (from the back down the aisle), `pews` (low from the left glass across the rows), `crate` (toward the
conveyor and hatch), `close` (the face height on the mark, the triptych behind), `board` (a 1.5 m insert, legible at
960 × 540), `hatch` (the shutter and the conveyor), `lectern` (the pulpit fall), `essay` (over the lectern at the page).
Far plane: the sky dome is 900 m, so `make_camera` uses 2000.

```python
room.parts['crate']['update'](4.4, 0.5, frame=f)          # the crate, shutter, beacon and rollers alone
room.parts['saleLights']['set'](1.0, frame=f)              # the launch lights alone
room.parts['hell']['set'](0.6, 2.0, frame=f)               # the glow at 60 %, flickering at t = 2
room.show(False, frame=f_cut)                              # off screen: hide it (its lights stop lighting), keyed
room.show_part('backdrop', False)                          # the city below hidden as a subtree (the city set instead)
```

## The showroom (`showroom.py`)

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

`update(t, state, camera=None)` / `animate(..., camera=)`:

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
face height on the mark) · `toasterFocus` · `probe` · `uniforms` (`uT uSeq uLights uBeams uScreen`, and `uPixelAngle`).

`cams`: `reveal` (from the audience: stage, wall, turntable, toaster, empty rows), `toaster` (the toaster and its
placard against the drape), `emptySeats` (over the turntable out over the seats), `close` (the face height on the mark,
the callouts converging), `wall` (across the stage at the wall). Far: 60 m is plenty (`make_camera` uses 100).

Under aeropittura's `argue` palette every near-white lands between the ramp's orange and white stops, so the white
stage and wall paint peach; a palette weight of 0.22 keeps them white:

```python
from eidoblend.look.post import custom_effects as fx, aeropittura as AP
U = fx.apply_to(scene, 'aeropittura', {'aeropittura': {'layer': 'under'}}).uniforms['aeropittura']
AP.apply_look(U, AP.LOOKS['argue'], 1.0, frame=1)
U['palette'].default_value = 0.22
U['palette'].keyframe_insert('default_value', frame=1)
```

## How the engine's pieces became Blender data

**Light, in three's units.** Measured: a Blender point light of 4π·cd watts on
white diffuse at 1 m renders 0.3145 linear and a sun of strength 1 renders
0.3184, where three's 1 cd and 1 lux render 1/π. So candela → W = 4π·cd and
lux → sun strength, with no 683 (that factor is glTF's photometric
convention). three's `distance` is the light's custom cutoff distance (EEVEE
windows its influence the way three does); `decay` ≠ 2 (most spots here are
1.3–1.6) is matched to inverse square at the light's target. three's spot
`penumbra` (a share of the cone's angle) becomes an exact `spot_blend` (a
share of 1 − cos), `three_spot_blend`. Each set has one shadow-casting light,
as in the engine (the red key down the nave; the cold key on the toaster),
and the engine's shadow casters are the objects' `visible_shadow`. Lights aim
at their targets with Track To constraints, so moving a target re-aims them.

**The set's environment.** Every engine material carried the set's own LDR
equirect as its envMap, each at its own `envMapIntensity` (the toaster's
chrome × 2.2, the lacquer × 1.6, the glass × 1.5, the seats × 0.25, the
auditorium carpet × 0.2). The equirect is painted pixel by pixel for
Blender's equirect lookup from the engine's direction function (the red altar
glow toward −Z three, which is +Y Blender). With `env_light='material'` (the
default) each material carries that light itself, as three's
`EnvironmentNode` gave it: `interiors_lib.env_levels` prefilters the env as
three's PMREM does (the sharp map, a lobe of α = r² for r 0.25, 0.5 and 0.75,
and the cosine lobe for r = 1, the level three reads for diffuse light), and
`ShaderGraph.env_light` adds to the material's emission the
diffuse albedo × (1 − metalness) × the r = 1 level toward the normal plus the
level for its roughness toward the reflection × (F0·A + B) (three's
`DFGApprox`), and a clearcoat's own layer, times its intensity (`K.envd`
after the recipe's `standard()`). Unoccluded, as in three. The lookups are
made in the set's own space (`ShaderGraph.set_space`: three drivers on the
root's world rotation), so a set parked turned keeps its light where its env
painted it; three's envMap stayed in world space, so turning a group there
turned its light away from it. The set's World
(`room.env`) then shows the env to camera rays only and lights nothing: make
it the scene's World while the set is on screen and the set is lit by its own
env alone, as in the engine (where the conductor's `scene.environment` did
not reach the set's materials); a World that lights would add its light on
top. With `env_light='world'` the env is the World
instead: one intensity for everything in the scene (your own props too), with
EEVEE's occlusion; the intensities are recorded (`mat['uf_env_intensity']`),
not applied. Your own material can take a set's env light as the set's do:

```python
K = show.kit                                   # the set's material kit (its env levels, its noise)
m, g = K.new('my-chrome')                      # disposed with the set
g.standard(color=(0.95, 0.95, 0.96), roughness=0.05, metalness=1.0)
K.envd(m, 2.2)                                 # three's envMap at envMapIntensity 2.2
```

The showroom's void and the quiet room's backdrop are seen by the camera
only: they are left out of the probes, so the bake and the reflections see
the env, as the engine's materials saw their envMap.

**Reflections.** The sets were made with SSR off, so everything glossy in the
engine reflected that env and nothing else: the toaster's chrome shows the
softboxes painted into the showroom's env, not the black void around it.
`eevee_settings()` reproduces that by default (`reflections='env'`: EEVEE's
ray tracing off, so the only reflections are the env's: the materials' own
env light, or the World under `env_light='world'`). `reflections='traced'`
adds screen-traced reflections: physically closer (the polished stage mirrors
the LED wall, the chrome mirrors the dark drapes), but not the engine's
picture (under `'material'` they come on top of the env's, as an SSR pass over
an envMap-lit frame does in three).

**Probes.** Each set adds a volume probe fitted to it (the quiet room's with
`look.lighting.add_room_probe`, its outer samples mid-wall), baked once at the
default state (`bake_probes`, 1.4–5 s at the tests' 0.5 m and 512 samples).
Emitters whose light the set's real lights already give (the hell pits, the
signs, the LED strips and wall, the lenses, the beams) and everything animated
are left out of the bake: a probe is static.

**Uniforms and keys.** Each set's uniforms are float custom properties on its
root (`room.root['uSale']`); every material reads them through a
one-variable driver (no Python). `update()` computes what the engine computed
and keys the uniforms, the light powers and the moving objects (shutter,
crate, beacon, platter) LINEAR at the frame; rotations are keyed as Euler
channels (three's `rotation.y` is Blender's z), so a spinning beacon never
unwinds between keys. With the harness, pass `ctx`: the keys go through
`ctx.key`. A clip on the LED wall plays through its Image Texture node's
image user (frame start, cyclic, auto refresh), so it needs no keys.

**Materials.** `interiors_lib.ShaderGraph` writes TSL as shader nodes,
reading positions and normals in three's axes so the engine's maths ports as
written (`g.position_local()`, `g.texture(img, uv)`, `g.mix`, `g.smoothstep`,
`g.uniform('uT')` ...), and `MaterialKit` ports `materialKit`: `tri` (the
triplanar noise), `pbr`, `solid`, `keyed`, `envd`. `g.hash()` is Blender's White
Noise: the same distribution as three's PCG hash, other values, because shader
nodes have no integer bit operations. Where the argument is known at build time
(a hash of `instanceIndex`), the set computes three's exact value with
`L.pcg_hash` and hands it to the shader as an instance attribute, so the quiet
room's neon edges, facade tones, window colours and aviation blinks sit on the
same towers as in the engine:

```python
ti = L.InstancedMeshNode(L.box_geometry(1, 1, 1), tower_mat, len(towers), name='towers')
ids = np.arange(len(towers), dtype=np.float64)
ti.set_instance_attr('uf_h17', L.pcg_hash(ids + 17.0))    # three's hash(float(instanceIndex) + 17.0), bit for bit
h1 = g.attribute('uf_h17')                                # read in the tower material
```

MeshBasic is an Emission (unlit);
additive beams add their emission over the frame (three's SRC_ALPHA, ONE:
colour × a × a); `side: BackSide` is geometry turned inward with backface
culling.

**Canvases.** All the canvas art (five boards, the register, the essay, the
pulpit fall, the booklet, the hazard stripes, the sprayed stencils, the
label, the sign, the slogan, the EXIT signs; the ENGINE sheet, the platter,
the placard, the dial, the plate, the toast) is drawn by `interiors_lib`'s
canvas-2D context on numpy + Pillow, line for line (the mulberry32 streams
match bit for bit). Each set lists its painters in `CANVASES`;
`draw_canvases(folder)` pre-draws them in the system Python (the centre board
takes 13 s) and `build(art_cache=folder)` reads them back when the same code
drew them (the cache is keyed by a hash of the drawing code). `test_art_parity.py`
compares every one with the engine's own @napi-rs/canvas output: the art
modules' pieces drawn by the original modules, and the canvases the two builds
draw inline (the essay, the stencils, the platter ...) captured from the
original builds themselves (`inline_art_reference.mjs` runs them under deno
with a recording `DataTexture`).

Text is laid out as Skia lays it out: `interiors_lib.FontMetrics` reads each
font's cmap, its unhinted advances and the GPOS pair kerning of its `kern`
feature, and `fillText` / `measureText` place every glyph there (FreeType then
draws it). Against Skia's `measureText` the widths agree to 0.01 px; Pillow's
own layout had the crate's 290 px "v.NEXT" 36 px too wide.

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

## Verify

```bash
cd blender && python -c "import sys; sys.path.insert(0, '.'); \
  from eidoblend.sets.unknown_force import quiet_room as QR, showroom as SR; \
  QR.draw_canvases('tests/sets_uf_interiors/out/art_cache'); SR.draw_canvases('tests/sets_uf_interiors/out/art_cache')"
cd blender/tests/sets_uf_interiors && python test_art_parity.py && python test_geometry_parity.py
# the shape with holes needs Blender's tessellator: run the geometry test there too (no render, no GPU slot)
bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/test_geometry_parity.py
# the library example above and the options' helpers, run as written and checked (no render)
bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/test_lib_example.py
# from the main checkout, through the GPU slot:
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/test_quiet_room.py
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/test_showroom.py
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/example_asset_use.py --save
# both env-light modes against the engine's probes, both sets in one scene, sets parked and turned, a Cycles
# reference, the look note run as written above
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/verify_probes.py
```

Each prints PASS / FAIL lines; the stills land in `out/qr/`, `out/sr/` and
`out/asset/` with contact sheets. The set tests render the sets alone from
every cam (`--vrm` stands the claudesona at the mark for scale).
`example_asset_use.py` is this guide's new-piece use, run: the quiet room with
its own board, page and sign, the crate shipped and the launch on its own
clock, cut by markers; the showroom with a 24-card image sequence letterboxed
on the LED wall, its own placard, the turntable turning and a blackout. It
checks the art landed pixel for pixel, the clip's frames on the wall, the
cuts, the blackout on the stage deck, and (with ffmpeg on the PATH) a movie
read back as one; `--save` also saves each set's `.blend`, opens it again and
re-renders a still from the file alone (`--keep_blend` keeps it).
`test_art_parity.py` also checks `pcg_hash` against the WGSL integer arithmetic
(through `deno eval`), the text layout against Skia's `measureText`, and the
canvases the builds draw inline against captures of the original builds. Judge
the stills against the WebGPU probes in the main checkout's
`work/unknown_force/sets/probes/` (`qr_final_altar_off`, `qr_pews`, `qr_lect`,
`qr_essay`, `qr_crate_sale`, `sr_uf_reveal`, `sr_final_toaster_off` ...), which
were rendered with ACES and bloom 0.55 / 0.5 / 0.7 (the tests apply the same
bloom; the view is AgX) and with a performer at the mark.

Cost on the shared RTX 5090 Laptop (measured 11-07 and 11-08 with the machine
busy): the quiet room builds in 8–33 s from cached canvases, the showroom in
4–18 s (the high ends with three Blenders building at once), and the
per-material env light adds about 4 s to either (the env's prefilter takes
1.6 s, the rest is the materials' env nodes); drawing every
canvas cold takes about 2 min in the system Python (the centre board 15–38 s),
so pre-draw them; the room probes bake in 1.4–5 s at the tests' 0.5 m and 512
samples; a 960 × 540, 16-sample still renders in 0.5–2 s, about 3 s under an
aeropittura look. Keying is cheap: 621 frames of the quiet room keyed in
0.2 s (measured 11-07).

## Known limits

- The quiet room's slogan is clipped at both ends in the engine too (110 px
  Michroma measures 2521 px on a 2048 px canvas); the port draws what the
  engine drew.
- The plinth's low scuffs read `positionLocal` after the static merge, where
  the plinth's foot is at y = 0, so no scuff shows, in the engine and here.
- The env light per material (`env_light='material'`) is three's split-sum
  with single scattering: no multiple-scattering energy term, no clearcoat
  attenuation of the base layer, no sheen term on the velvet (black velvet at
  × 0.3). three r184 prefilters its PMREM with chained GGX passes and picks a
  level with `roughnessToMip`; here each level is a von Mises–Fisher lobe of
  the material's own roughness (α = r²) and the diffuse level is the cosine
  lobe, so mid-roughness reflections may be a little softer than the
  engine's. Under `env_light='world'` the intensities are not applied at all,
  and the World stays in world space (turn the set and its env stays put).
- The engine's probes went through three's ACESFilmic, which multiplies the
  picture by 1 / 0.6 (+0.74 stop) before its curve; these render AgX at
  exposure 0. The two curves part at both ends (8-bit display values,
  measured: linear 0.012 shows 22 under AgX and 11 under three's ACES, 0.024
  36 and 25, mid grey 0.18 118 and 127, 0.5 170 and 197): the darks here read
  lighter (the seats, the drapes, the night glass) and the highlights softer.
  In linear light the regions agree more closely than the PNGs suggest (the
  showroom's drape 0.013 here and in the engine; its seats 0.028 against
  0.021). Under the aeropittura look the dark shots measure as the engine's
  (mean luma within 10 %), the bright ones 10–25 % darker (the board insert
  0.42 against 0.50). Exposure is free: meter it with `look.exposure`.
- The toaster's chrome reads brighter in the engine (its body 123–135 / 255
  against 72–79 here): its env reflection is now the engine's (× 2.2), and
  the rest is the curve above and the bloom the engine's hotter highlight
  (three's punctual spot on a 0.035-rough mirror) raised round it; here the
  spot has a 3 cm radius.
- The probes are baked at the default state: the launch lights' bounce
  (sale = 1) and a blackout's missing bounce are not in them.
- Blender's lights fall off with the inverse square; three's spots here fall
  off as 1 / d^1.3–1.6, matched at each light's target. Nearer than the
  target a light is brighter than the engine's, beyond it dimmer: the
  showroom's seat spill (decay 1.6, aimed 12.5 m out) lights the front row
  1.9 × as bright as the engine's and the back row 0.9 ×.
- The crate is lit red through the open hatch as it emerges (the red key
  points down the nave into it), as in the engine.
- `art=` pictures are resized to the canvas, not fitted: draw them at the
  canvas's aspect (its size is `CANVASES[key][:2]`). The LED wall's clip is
  fitted (`screen_fit`).
- A clip on the LED wall plays on the scene's frames at one clip frame per
  scene frame; a different speed needs a driver on the image user's
  `frame_offset`.

## Not yet ported

- Nothing of the five modules' public API is left out. Not carried over
  (no Blender counterpart): `customProgramCacheKey` (each Blender material
  is its own), the CPU mip chains (EEVEE builds its own; `build_mips` stays
  for parity checks), `userData.noMips`, `renderOrder` (EEVEE sorts blended
  surfaces itself), `receiveShadow` (EEVEE has no per-object receive switch),
  `shadow.mapSize` / `bias` / camera extents (EEVEE's virtual shadow maps),
  `depthWrite`, `polygonOffset` (a physical 0.6 mm offset instead),
  `anisotropy` (a user preference in Blender).
- Canvas text: GSUB is not applied (ligatures, and Caveat Brush's contextual
  alternates, which change a few runs' kerning in Skia), and FreeType's hinted
  rasterisation draws small type a shade heavier than Skia (the register's
  20 px typewriter lines); the glyph positions are Skia's.
- The hashes the shaders take per pixel (which tower windows are lit, which
  carpet tiles turn, the street grid's blocks) are White Noise draws: the
  same share of lit windows and turned tiles as the engine, on other
  windows and tiles. Only the per-instance hashes are three's exact values.
- The engine's three materials `osb`, `galv` and `chrome` in the quiet room
  are defined and never put on a mesh there; they are not built.
- The film these sets were first made for (its conductor, its cut, its song
  timing, its performer's outfit and staging) is not part of the kit.
