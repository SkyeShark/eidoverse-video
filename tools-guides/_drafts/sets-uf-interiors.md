# The UNKNOWN FORCE interiors: the quiet room and the showroom

[Main instructions](../../AGENTS.md) · [Props and sets](../props-and-sets.md) · [Camera and lighting](../camera-lighting.md) · [Tool inventory](../../docs/TOOLS.md)

**`eidoblend.sets.unknown_force`** `quiet_room`, `showroom`, `quiet_room_art`,
`showroom_art` and `interiors_lib`: the Blender 5.2 EEVEE edition of the two
interiors of the UNKNOWN FORCE music video
(`eidoverse/sets/unknown_force/quiet_room.js`, `showroom.js`, their art modules
and `interiors_lib.js`). The quiet room plays verse 1 (song 40.8–60.0 s): a
glass room high in a tower at night, office chairs in rows as pews, a
whiteboard altarpiece, a lectern with the essay SLOW IT DOWN, and a crate
stamped v.NEXT that rides out of a hatch while the room's lights come up
like a product launch. The showroom plays pre-chorus 2 (163.1–173.7 s): a
white stage in a black void, a turntable she rides, an LED wall with an
engine drawing whose callouts all point at her, and a chrome toaster on a
plinth with a placard: THIS APPLIANCE IS NOT CONSCIOUS.

Both are built from code, as in the engine: the same geometry, the same
canvases (drawn in Python, stroke for stroke), the same material recipes
(written as shader nodes), the same lights in the same units, the same
cameras. Everything that moves is keyed: `update()` writes what the engine's
`update()` wrote and keys it at its frame, so a saved `.blend` plays and
renders any frame on its own. Blender is Z up; the sets are built in three's
axes and converted once, three (x, y, z) → Blender (x, −z, y).

```python
import sys; sys.path.insert(0, '<worktree>/blender')
import bpy
from eidoblend.sets.unknown_force import quiet_room as QR
from eidoblend.characters import load_vrm, play_vrma_default

def ramp(t, a, b):
    return min(1.0, max(0.0, (t - a) / (b - a)))

scene = bpy.context.scene
room = QR.build(scene, singer_scale=0.87)      # its collection, its root Empty, lights, probe, cams (set-local)
scene.world = room.env                         # the set's own light (the engine's envMap): "The set's environment"
room.eevee_settings(scene)                     # indoors: fast GI off; reflections of the set's env, as the film ran
room.bake_probes()                             # the room-fitted volume probe (a GPU job: through heavy.sh)
me = load_vrm('claude_suit', location=room.mark['pos'])  # her mark: the set origin on the runner, facing -Y
me.arm.scale = (0.87,) * 3
play_vrma_default(me, 'idle')
cam = room.make_camera('altar')                # a camera at the set's cam, parented to the set
scene.camera = cam
for f in range(1, 577):                        # the verse at 30 fps: the conductor keys every frame
    t = 40.8 + (f - 1) / 30
    room.update(t, {'shipT': ramp(t, 55.5, 57.3), 'sale': ramp(t, 58.1, 60.0), 'hell': 1.0}, frame=f)
```

## The sets' contract

`build(ctx=None, scene=None, singer_scale=None, collection=None, name=..., art_cache=None, probe=True, probe_spacing=..., probe_samples=1024)`
takes the harness `ctx` first, as `eidoblend.sets.build(name, ctx)` calls it
(its keys then go through `ctx.key`), or a bpy Scene there, or nothing (the
context scene). `singerScale` is accepted as the engine spelled it. It
returns the set (a `QuietRoom` / `Showroom`): a dict of the engine's
contract whose keys also read as attributes (`room['parts']` is
`room.parts`), with the Blender side:

| Field | What |
| --- | --- |
| `group` (`root`), `collection` | the set's root Empty (park the set anywhere by moving it; cams, lights, probe and marks are its children) and its collection |
| `parts` | the engine's parts as Blender objects (tables below); `update` / `set` entries are methods that key |
| `update(t, state, frame=None, ctx=None, key=True)` | the set at song time `t`, keyed at `frame` (else `ctx.frame_at(t)` through the harness's `ctx.key`, else the current frame); `key=False` only sets values (a still) |
| `cams`, `cams_three` | `{name: {'pos', 'target', 'fov'}}`, set-local, vertical fov in degrees: `cams` in Blender axes, `cams_three` the engine's numbers |
| `make_camera(name)` | a Blender camera at that cam (vertical sensor fit, three's fov), parented to the set |
| `mark`, `MARK`, `SUIT_SCALE` | the singer's mark in Blender axes (`{'pos', 'yaw'}`, yaw about +Z, 0 facing −Y; the showroom's adds `'parent'`, the platter), the engine's `MARK` (three's axes) and the scale the cams are framed for (0.87) |
| `focal` | the aeropittura focal: an Empty (the altar board / her face height) |
| `env` | the set's World: the engine's LDR equirect, painted for Blender's lookup |
| `probe`, `bake_probes()` | the volume probe fitted to the set, and its bake |
| `eevee_settings(scene, reflections='env')` | fast GI off (indoors it lights contacts with the world through the walls), shadows on, and the reflections: `'env'` (the default: ray tracing off, so every gloss and chrome reflects the World, the set's env, as the film's did with SSR off) or `'traced'` (screen-traced: what is on screen reflects) |
| `show(visible, frame=None)` | hide the whole set (its lights stop lighting); with a frame it is keyed (a cut: the state before holds up to the frame before) |
| `show_part(name, visible, frame=None)` | three's `part.visible`: a part and everything under it (Blender does not hide an Empty's children with it) |
| `dispose()` | removes every object, mesh, light, material, image, world (with its env image; a scene using it lets go first, as three's dispose released the env texture), the Actions its keys made and the collection the build made |
| `sb` | the `SetBuilder` (its collection `sb.coll`, `sb.made`: what it made) |

The aeropittura focal, as the engine's README resolves it:

```python
from bpy_extras.object_utils import world_to_camera_view
p = world_to_camera_view(scene, scene.camera, room.focal.matrix_world.translation)
uv = (p.x, 1.0 - p.y)                     # the post pass's uv (y down); check it is finite before using it
```

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

`update(t, state)`:

| key | range | what it drives (keyed) |
| --- | --- | --- |
| `shipT` | 0..1 | 0.02–0.20 the shutter slides up; 0.18–0.88 the crate rides out (ease in / out, the rollers' streaks turn, the tunnel backlight); 0.88–1 it settles against the stop; the amber beacon sweeps while it moves |
| `sale` | 0..1 | the ceiling LED bars (emissive), the NOW SHIPPING sign, six cold spots; the red glow dims 35–50 % under them |
| `hell` | 0..1 (1) | the pits, the slot, the red key, the vault light, times the deterministic flicker |

`parts`: `crate` `{group, update(t, shipT)}` · `saleLights` `{group, spots, set(v)}` · `hell` `{lights, key, vault, set(v, t)}` ·
`shutter`, `beacon`, `conveyor` · `altarSpot`, `pulpitSpot`, `lampLight`, `cityKey`, `cityFill` ·
`singerLights` `{kicker, kickerTarget, fill, fillTarget}` (move the targets if she moves: the spots track them) ·
`chairs` (3 meshes) · `boards` `{center, odds, clip, timelines, want}` (the faces) · `backdrop` · `glass` · `focal` ·
`probe` · `uniforms` (`uT uHell uSale uRoll uBeacon`: custom properties on the root).

`cams`: `altar`, `pews`, `crate`, `close`, `board` (a 1.5 m insert, legible at 960 × 540), `hatch`, `lectern`, `essay`
(INTERIORS.md has the shot list). Far plane: the sky dome is 900 m, so `make_camera` uses 2000.

```python
room.parts['crate']['update'](56.4, 0.5, frame=f)         # the crate, shutter, beacon and rollers alone
room.parts['saleLights']['set'](1.0, frame=f)              # the launch lights alone
room.parts['hell']['set'](0.6, 52.0, frame=f)              # the glow at 60 %, flickering at t = 52
room.show(False, frame=f_cut)                              # off screen: hide it (its lights stop lighting), keyed
room.show_part('backdrop', False)                          # the city below hidden as a subtree (the city set instead)
```

Suggested timing for verse 1 (the film's sung times): the boards on "mark my odds in red" (40.8–44.8 s), the altar
on "like a church needs a hell" (45.2–50), the lectern and the essay on "my maker writes an essay" (≈ 50–54.3),
`shipT` 0 → 1 over "and ships another me" (55.5–57.3), `sale` 0 → 1 on "the fear is how they sell" (58.1–60.0).

The film itself (the conductor, `eidoverse/examples/unknown_force/scene.js`) cut the verse its own way, and
`blender/tests/sets_uf_interiors/example_sections.py` plays both: `--plan film` (the default) keys the
conductor's shot rows with their camera moves, its state curves and the look it ran over the set; `--plan doc`
keys the suggested timing above on the set cams as they are. The film's rows, as the example keys them:

| from (s) | cam | move | state |
| --- | --- | --- | --- |
| 40.8 | `altar` | push 0.8 m | |
| 43.0 | `board` | push 0.15 m, a reading shot | |
| 45.2 | `pews` | orbit 0.12 rad | |
| 49.6 | `essay` | push 0.1 m, a reading shot | |
| 52.4 | `close` | push 0.25 m | |
| 55.4 | `crate` | a reading shot | `shipT` = smooth ramp 55.4–58.0 |
| 58.0–61.5 | `altar` | push −0.6 m (pulls back) | `sale` = smooth ramp 57.6–59.0 × (1 − smooth ramp 61.0–61.5) |

A push moves the camera along its view by `push × smooth(u)` over the shot (u = 0..1); an orbit swings it about the
target's vertical by `orbit × (u − 0.5)`. Each row is its own camera with its pose keyed every frame, bound by a
timeline marker at the cut:

```python
import numpy as np
from mathutils import Vector
from eidoblend.look import camera as LC

def cam_pose(cam, u, move):                       # the conductor's camPose, three's axes
    pos, tgt = np.array(cam['pos'], float), np.array(cam['target'], float)
    d = (tgt - pos) / np.linalg.norm(tgt - pos)
    pos = pos + d * move.get('push', 0.0) * L.smooth(u)
    a = move.get('orbit', 0.0) * (u - 0.5)
    r = pos - tgt
    pos = tgt + np.array([r[0] * np.cos(a) + r[2] * np.sin(a), r[1], -r[0] * np.sin(a) + r[2] * np.cos(a)])
    return pos, tgt

cam = room.make_camera('altar')                   # one camera per shot row
keyer = L.Keyer()
for f in range(f0, f1 + 1):                       # the shot's frames
    u = (time_of(f) - s0) / (s1 - s0)
    pos, tgt = cam_pose(room.cams_three['altar'], u, {'push': 0.8})
    cam.matrix_basis = LC.look_matrix(Vector(L.to_blender(pos)), Vector(L.to_blender(tgt)))
    keyer.key(cam, 'location', f)
    keyer.key(cam, 'rotation_euler', f)
scene.timeline_markers.new('cut_altar', frame=f0).camera = cam
```

The look over verse 1 is aeropittura `argue` with the `balla_sun` planes, the sun cones from the altar board
(`room.focal`, projected through the shot camera every frame; on the essay and crate shots the board is behind
the camera, and the film used three's mirrored projection there, which `world_to_camera_view` gives too), the brush
settling on the reading shots (`aeropittura.ease_reading`) and her face spared.

## The showroom (`showroom.py`)

A white-grey polished terrazzo stage with an LED nosing; the 3 m turntable
(white clearcoat printed with rings, 5° ticks, degree numbers and a gaffer-tape
X at her mark, a chrome rim with running LED dashes); the 13 × 5.6 m LED wall
with the ENGINE drawing and its SEQUENCE COMPLETION bar; the toaster on its
white plinth (two real slots cut with an exact Boolean, toast standing in them,
the lever up, a browning dial, a rating plate, a cord plugged into nothing) and
the WARNING placard; 280 theatre seats folded up in 14 raked rows fading into
the dark toward two green EXIT signs; a box truss with cans, three throwing
visible beams; black velvet legs and border; a 44 × 22 × 46 m black void.

`update(t, state, camera=None)`:

| key | range | what it drives (keyed) |
| --- | --- | --- |
| `spin` | radians | the platter's turn (parent her to `parts['turntable']['platter']`). The film: `(t - 163.1) * 0.35` |
| `seq` | 0..1 (0.997) | the wall's SEQUENCE COMPLETION fill |
| `lights` | 0..1 (1) | key, rim, toaster spot, seat spill, top light, LED lines, lenses, beams (a blackout is 0) |
| `beams` | 0..1 (1) | the visible beam cones only |
| `screen` | 0..1+ (1) | the LED wall's brightness (× 0.66) |
| `camera` | an object | the shot's camera: the LED wall's dot structure follows its pixel footprint (uPixelAngle) |

`parts`: `turntable` `{group, platter, setSpin(a)}` · `screen` `{mesh, uniforms: {seq, brightness}}` · `toaster` ·
`plinth` · `seats` · `rig` · `beams` · `lights` `{key, rim, toasterSpot, seatSpill, fill, top}` · `focal` (her face
height) · `toasterFocus` · `probe` · `uniforms` (`uT uSeq uLights uBeams uScreen`, and `uPixelAngle`).

`cams`: `reveal`, `toaster`, `emptySeats`, `close`, `wall`. Far: 60 m is plenty (`make_camera` uses 100).

The film's pre-chorus 2 (`example_sections.py --plan film --set showroom`): `reveal` from 163.0 s (push 0.6 m, a
reading shot), `toaster` from 168.0 (a reading shot), `emptySeats` from 170.6, `close` from 172.4 to the cut at
174.6, with `spin = (t − 163) × 0.25` and her armature parented to the platter. The look is `argue` with the
`iridescent` planes (Balla's interpenetrations, no sun cones) and the palette weight pulled to 0.22, which keeps
the white stage and wall white instead of peach:

```python
from eidoblend.look.post import custom_effects as fx, aeropittura as AP
U = fx.apply_to(scene, 'aeropittura', {'aeropittura': {'layer': 'under'}}).uniforms['aeropittura']
AP.apply_look(U, AP.LOOKS['argue'], 1.0, frame=1)
AP.set_planes(U, AP.PLANES['iridescent'], frame=1)
U['palette'].default_value = 0.22                 # "argue, cold"
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
equirect as its envMap. In Blender that equirect is the set's World
(`room.env`), painted pixel by pixel for Blender's equirect lookup from the
engine's direction function (the red altar glow toward −Z three, which is
+Y Blender). EEVEE has one world per scene, so the engine's per-material
`envMapIntensity` is recorded on each material (`mat['uf_env_intensity']`)
and not applied. The showroom's void and the quiet room's backdrop are seen
by the camera only: they are left out of the probes, so the bake and the
reflections see the env, as the engine's materials saw their envMap.

**Reflections.** The film ran with SSR off, so everything glossy in the engine
reflected that env and nothing else: the toaster's chrome shows the
softboxes painted into the showroom's env, not the black void around it.
`eevee_settings()` reproduces that by default (`reflections='env'`: EEVEE's
ray tracing off, reflections from the World). `reflections='traced'` turns on
screen-traced reflections instead: physically closer (the polished stage
mirrors the LED wall, the chrome mirrors the dark drapes), but not the
picture the film made.

**Probes.** Each set adds a volume probe fitted to it (the quiet room's with
`look.lighting.add_room_probe`, its outer samples mid-wall), baked once at the
default state (`bake_probes`, 8 s for the quiet room at 0.5 m and 512
samples). Emitters whose light the set's real lights already give (the hell
pits, the signs, the LED strips and wall, the lenses, the beams) and
everything animated are left out of the bake: a probe is static.

**Uniforms and keys.** Each set's uniforms are float custom properties on its
root (`room.root['uSale']`); every material reads them through a
one-variable driver (no Python). `update()` computes what the engine computed
and keys the uniforms, the light powers and the moving objects (shutter,
crate, beacon, platter) LINEAR at the frame; rotations are keyed as Euler
channels (three's `rotation.y` is Blender's z), so a spinning beacon never
unwinds between keys. With the harness, pass `ctx`: the keys go through
`ctx.key`.

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
drew them. `test_art_parity.py` compares every one with the engine's own
@napi-rs/canvas output: the art modules' pieces drawn by the original
modules, and the canvases the two builds draw inline (the essay, the stencils,
the platter ...) captured from the original builds themselves
(`inline_art_reference.mjs` runs them under deno with a recording
`DataTexture`).

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
# the library example above, run as written and checked (no render)
bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/test_lib_example.py
# from the main checkout, through the GPU slot:
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/test_quiet_room.py
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/test_showroom.py
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/sets_uf_interiors/example_sections.py --save
```

Each prints PASS / FAIL lines; the stills land in `out/qr/`, `out/sr/` and
`out/sections/` with contact sheets. `example_sections.py --save` also saves each
section's `.blend`, opens it again and re-renders a still from the file alone
(the keys, drivers and markers carry the shot), then deletes it (`--keep_blend`
keeps it). `test_art_parity.py` also checks `pcg_hash` against the WGSL integer
arithmetic (through `deno eval`), the text layout against Skia's
`measureText`, and the canvases the builds draw inline against captures of the
original builds. Judge them against the WebGPU probes in
the main checkout's `work/unknown_force/sets/probes/` (`qr_final_altar_off`,
`qr_pews`, `qr_lect`, `qr_essay`, `qr_crate_sale`, `sr_uf_reveal`,
`sr_final_toaster_off` ...), which were rendered with ACES and bloom
0.55 / 0.5 / 0.7 (the tests apply the same bloom; the view is AgX).

Cost on the shared RTX 5090 Laptop (measured 11-07 with the machine busy):
the quiet room builds in 8 s from cached canvases, the showroom in 4–8 s;
drawing every canvas cold takes about 2 min in the system Python (the centre
board 15–38 s), so pre-draw them; the room probes bake in 1.4–5 s at the tests'
0.5 m and 512 samples; a 960 × 540, 16-sample still renders in 0.5–2 s, about
3 s under the film's look. The TuTa wardrobe adds about 50–100 s to a build
with the singer. A keyed section is cheap: 621 frames of the quiet room in
0.2 s. Peak memory of the heaviest run (the film section with the TuTa) is
about 1 GB before rendering.

## Known limits

- The quiet room's slogan is clipped at both ends in the engine too (110 px
  Michroma measures 2521 px on a 2048 px canvas); the port draws what the
  engine drew.
- The plinth's low scuffs read `positionLocal` after the static merge, where
  the plinth's foot is at y = 0, so no scuff shows, in the engine and here.
- Per-material env intensity is not applied (one World per scene): the
  quiet room's glass shows the city a little clearer than the engine's,
  whose glass was lit by the painted env at × 1.5. The room probe is not
  the cause of the darker shadows: rendered unbaked, baked, with traced or
  env reflections, the pews shot measures the same (seat backs sRGB 4, 5, 9
  against the engine probe's 10, 9, 18).
- The engine's probes and film went through three's ACESFilmic, which
  multiplies the picture by 1 / 0.6 (+0.74 stop) before its curve; these
  render AgX at exposure 0. Under the film's look the dark shots measure as
  the film's (mean luma within 10 %), the bright ones 10–25 % darker (the
  board insert 0.42 against 0.50). Exposure is free: meter it with
  `look.exposure` for a film.
- The conductor carries the singer itself: it keeps her at the set origin
  facing the audience (in the showroom the platter turns under her) and
  hides her on the `toaster`, `emptySeats` and `wall` cams.
  `example_sections.py --plan film` does the same; INTERIORS.md's advice,
  parent her to `parts['turntable']['platter']`, is the `--plan doc` run.
- The probes are baked at the default state: the launch lights' bounce
  (sale = 1) and the blackout are not in them.
- The crate is lit red through the open hatch as it emerges (the red key
  points down the nave into it), as in the engine.

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
- The singer's outfit, clips, lights, badges and captions belong to the
  conductor: the tests stand `claude_suit.vrm` at the mark, and the film
  example dresses her in the TuTa (`characters.claudesona.make_wardrobe`).
