# Modular robotics and G430 fabrication (Blender edition)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Characters](characters.md) · [Blender](blender.md) · [Fabrication](fabrication.md) · [Rotary carving](rotary-carving.md)

Use the baked modular kit, reusable interfaces and shared maps to assemble
industrial, mobile and humanoid robots. This is the Blender 5.2 EEVEE edition:
the package is `blender/eidoblend/characters/robotics/`, and its names follow
the WebGPU API in snake_case (`makeRobot` → `make_robot`, `setJoints` →
`set_joints`, `childPort` → `child_port`). VRM character navigation
(`robot_body`, sensors, planner and controller) is a separate API
([characters.md](characters.md)); the FDM and CNC processes are
`eidoblend.fabrication`'s (below).

**The one rule that differs from the WebGPU edition.** There, `play()` registers
the engine clock and the robot moves while the scene renders. Here a scene is a
build script, then a saved `.blend`, then a render: **`play()` samples the clip
at every frame of the range and keys it** (LINEAR, one action with a slot per
moving object). Nothing runs at render time, so any frame renders alone and the
file plays when you open it. `sample(clip, seconds)` is unchanged: deterministic
and seekable.

**Axes.** The kit was authored in Blender, +Z up, and exported to glTF; Blender's
importer brings every node back in its authoring frame. Every number the catalog
and the metadata give in "source +Z-up coordinates" (joint axes, port frames,
nominal matrices, gait rest matrices, track paths) is used **as it is** here: the
WebGPU edition converts each to three's +Y up, and this edition must not convert
them again. A three offset `(x, y, z)` in the WebGPU sources is Blender
`(x, −z, y)`. Metres and radians, as there.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.characters.robotics import make_robot, studio, frame_camera
from eidoblend.characters.robotics.studio import make_camera

sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 240
studio(sc)                                              # the kit's own studio light (studio.js)
robot = make_robot('payloads/arm_hand', position=(0, 0, 0), color='#d9e0df', accent='#398b91')
robot.sample('joints', 2)                               # explicit, deterministic seconds
robot.grasp(1)                                          # all fingers + curved, opposed thumb
robot.play('joints')                                    # keyed over frames 1..240
cam = make_camera(35)                                   # three's vertical field of view
frame_camera(cam, [robot.group])
sc.camera = cam
robot.stop()                                            # removes those keys again
```

## Load a module or assembled robot

`make_robot(id, **options)` (also `load_robot`; `RoboticsKit.load`) imports the
model's GLB through Blender's own glTF importer, maps every object to its glTF
node, puts the robot under one empty, `robot.group` (`robot|<id>`: place the
robot there), in a collection of the same name, reads every module (an object
with the custom property `module_id`) and its joint spec (the node's extras over
the family metadata's root properties), installs the ports and the motion
controls, and rebuilds every kit material's base colour with the recolour formula.

| Option | Meaning |
| --- | --- |
| `position` (or `location`) | three numbers, Blender axes |
| `rotation` | Euler XYZ, radians, Blender axes |
| `scale` | positive, uniform |
| `color` / `primary`, `accent`, `filament` | the palette (below) |
| `textures=False` | geometry-only inspection: every map removed, base colour three's 0.863 stand-in |
| `subassembly` | `{'root': node name, 'keepModule': kit_module}`: one root of a shared GLB |
| `model` | `make_bot`'s model name |
| `scene` | the scene whose collection the robot joins (default: the context's) |
| `collection`, `name` | Blender's own: an existing collection, the empty's name |

Any other option raises (`Unknown modular loader option ...: Geometry/slot
presets were retired`), as do a bad position, rotation or scale and an unknown
id (the delta, Stewart, turret and Kossel primitives stay retired). A refused
load leaves nothing in the file.

`catalog()` returns `eidoverse/assets/robotics/catalog.json`: 89 entries over 85
source GLBs (the four humanoid subassemblies reuse the humanoid's GLB) and 67
shared maps. File and entry totals describe packaging, not the number of unique
component designs; `robot.parts()` enumerates a model's pieces.

| Load name | Content |
| --- | --- |
| `arm` / `a650` | A650 six-axis industrial arm |
| `scara` / `s500` | S500 SCARA arm |
| `gripper`, `linear`, `rotary` | Parallel gripper, guided stage, hollow rotary drive |
| `fdm`, `cnc`, `gantry` | G430 with extruder, with spindle, or without a process head |
| `filament_spool` / `spool` | Freestanding 200 mm reel and dispenser |
| `spool_mount` | Rail-mounted carrier; `fdm` combines it with the shared reel, axle and fittings |
| `fdm_plate`, `cnc_plate` | Removable PEI sheet and T-slot table; included in their machines |
| `cnc_relief` | T-slot CNC with the ball-nose tool |
| `cnc_rotary` / `rotary_fixture` | XYZ + A stock-rotating CNC, or its reusable drive/chuck/tailstock fixture |
| `cnc_clamp`, `tube_support`, `push_fitting`, `ball_tool` | Reusable workholding, feed hardware and the ground two-flute ball cutter |
| `process/extruder`, `process/spindle`, `process/vacuum` | Detachable process heads |
| `arm/shoulder`, `arm/upper`, `arm/elbow`, `arm/forearm`, `arm/wrist` | Modular humanoid arm sections |
| `arm/mc110_adapter`, `arm/sm40_adapter`, `arm/clamp_adapter` | Existing interface adapters |
| `hand`, `camera`, `lidar`, `face`, `interaction/antenna`, `interaction/diagnostic` | Articulated attachments |
| `mobility/body`, `mobility/tracks`, `drone` | Backbone, tracked platform, folding quad airframe |
| `humanoid_modules/left_leg`, `humanoid_modules/right_leg` | Mirrored, articulated leg modules |
| `humanoid_modules/pelvis`, `humanoid_modules/torso` | Articulated pelvis and torso |
| `payloads/arm_hand`, `payloads/arm_clamp` | Complete seven-axis arm/tool builds |
| `payloads/drone_hand`, `payloads/drone_clamp`, `payloads/rover_arm` | Mobile payload demonstrations |
| `rover`, `platforms/survey`, `humanoid`, `quadruped`, `mantis` | Complete sample platforms |
| `stock/<component ID>` | Reusable original flange, bearing, mount and connector geometry |

`make_bot(model='humanoid', **options)` is the convenience loader
(`makeBot`). `RoboticsKit` is the facade (`version`, `ready()`, `catalog()`,
`load()`, `load_part()`, `connect()`, `create_ptfe_tube()`, `service_loop()`).
`asset_root()` (`ASSET_ROOT`) is index.js's `assetRoot`, `eidoverse/assets/robotics/`;
`cache_stats()` counts the GLBs parsed and the maps shared this session. Use
Eidoverse's audio and display tools for speech, screens and diagnostic readouts.

The importer evaluates a GLB's own animations while it builds; the loader puts
every node back on its transform from the file and keeps those animations as
**muted** NLA tracks (the source clips; the `walk` sample evaluates them itself).

## Connections and reuse

```python
from eidoblend.characters.robotics import make_robot, connect

body = make_robot('mobility/body')
camera = make_robot('camera')
body.attach(camera, port='body_base/sensor_0', child_port='camera_base/input', twist=0.0)
# the same: connect(body, camera, port='body_base/sensor_0', child_port='camera_base/input')
print(list(body.ports), list(camera.ports))
camera.set_joints({'camera_pan': 0.6, 'camera_tilt': 0.15})
```

An industrial arm and claw use the same connection API:

```python
arm = make_robot('arm')
claw = make_robot('gripper')
arm.attach(claw, port='a650_j6/output', child_port='parallel_gripper/input')
arm.joints([0, 0.5, 0.4, 0, -0.9, 0])
claw.jaw_gap(0.03)
```

For the SCARA, load `scara` and use `s500_tool/output` with the same gripper
input. The gripper input is on its robot-side coupling face. Use the declared
ports directly; they contain the mounting position and orientation.

Mounts align their authored mating frames, oppose their normals and preserve
the source physical scale: the child's empty is parented to the port's owner at
`port · Rz(twist) · Rx(π) · child_frame⁻¹`. `twist` is an intentional rotation
in radians around the attachment normal, such as turning the jaws sideways; it
cannot correct an incorrect mounting position or tilt. Mismatched interfaces,
invalid frames (a non-finite twist, a singular mount matrix) and graph cycles
raise before anything moves; choose the declared adapter for different
interfaces. SM40, TC70, MC110 and other interfaces are distinct. A socket does
not establish clearance for every possible payload or motion: inspect the
completed assembly. `robot.dispose()` removes a robot and every robot attached
to it.

`robot.port(name)['matrix']` is local to that port's `owner` (an object): X is
the mount tangent, Z the outward mating normal, Y completes the basis;
`owner.matrix_world @ matrix` is the world frame. A component's outward normal
stays fixed to that component; do not reverse it depending on which robot
receives the attachment. Ports come from a module's extras (`ports_json`,
`output_frame`, `attachment_position` / `input_frame`), from
`catalog.json['port_frames']` keyed by `module_id` (also applied to qualified
copies such as `rover_camera / camera_base`), from the family metadata's
`mobile.ports`, and from the mating frames measured on the approved complete
assembly (a humanoid's `pelvis_left_roll/left_leg`). A frame needs a finite
position and a nonzero outward normal, and a tangent when the mounting has a
preferred rotational alignment (`frame_matrix(point, normal, tangent)`); a
missing, zero or parallel axis refuses the load. Verify new frames against the
physical mating faces, including articulated poses
(`blender/tests/robotics/test_attachment_frames.py` measures them from the
triangles).

`robot.roots`, `robot.specs`, `robot.ports`, `robot.parts()` and
`robot.stats()` expose the actual content. Repeated humanoid joints use
qualified names (`left_hand / hand_base`), so a left-hand or leg command cannot
target the right-side copy. `stats()` reports `triangles`, `meshes` (Blender
objects), `primitives` (the glTF primitives behind them: three's mesh count),
`uniqueGeometry`, `materials`, `textures` and `parts`.

### Individual components inside a GLB

GLBs preserve named part meshes and articulated node hierarchies; some exports
batch several parts into one mesh, and the `provenance/` sidecars say which
triangles belong to each part. `robot.part_faces(obj)` gives that table for a
mesh (the part of every face; also stored on the object as `part_faces`).

```python
from eidoblend.characters.robotics import catalog, load_part

print(catalog()['models']['interaction/face']['parts'])          # exact part IDs
yoke = load_part('interaction/face', 'FACE swept tilt yoke')
print(yoke.parts(), yoke.stats()['triangles'])                    # ['FACE swept tilt yoke'] 176
yoke.group.location.x += 0.3                                      # offset from the original module placement
```

`load_part` keeps only that part's triangles (a copy of the mesh with its UVs,
materials and exact shading normals), shares the cached maps, keeps the donor's
hierarchy and origin (it does **not** recentre the component) and hides every
other donor mesh. A missing part name or incomplete triangle ownership raises
and removes the donor. Keep `provenance/` with `models/` and `textures/` when
distributing the kit. `robot.part(name)` returns the mesh objects holding a
part (a batched mesh can hold others too). For common bearings, flanges and
mounts the standalone `stock/<component ID>` entries are also available:
`make_robot('stock/flange.tc70.6mm')`. An extracted casting or fastener is
geometry; its donor's joint/port metadata does not make it a mechanical module.

### The look

Do not re-unwrap, texel-normalize or replace the finished maps of these GLBs.
The linear recolouring formula is `fixed.rgb + primary · mask.r + accent ·
mask.g`, built into each kit material's node tree from its `eidoverse_recolor`
extras; the palette is one node group per robot (`robot_palette|<robot>`,
initialised from the material's default linear colours).
`robot.set_colors(primary, accent)` changes body and accent while keeping
metal, rubber, text, grime and normal maps. The dispenser adds `filament ·
mask.b`: `filament='#218675'` when loading, or `robot.set_colors(filament=...)`.
Colours are `'#rrggbb'`, `0xrrggbb` or an sRGB triple. Every map is one shared
image per file (io.js's cache), clamped at its edges as there.

**Mirrored placements.** Never reflect normal-map green or tangent.w to
compensate for a mirrored object. Blender's Normal Map node carries the
object's negative-scale sign in its tangent frame, as the WebGPU runtime's
parity uniform does: `test_normal_parity.py` mirrors the A650 in X and compares
EEVEE's Normal pass with the mirrored source, with inverted green as the
control.

**Occlusion.** The importer routes a material's occlusion texture into its
"glTF Material Output" group, which EEVEE does not render. three's aoMap only
darkened indirect light; EEVEE's horizon scan and ray-traced GI occlude the
world light in the crevices themselves, so the baked AO is left out rather than
multiplied into the direct light.

## Motion and IK

`robot.clips` lists the samples this robot has. `sample(name, seconds)` resets
the robot and poses it (seekable: the same seconds always give the same pose);
`play(name, speed=1, start=0, frame_start=None, frame_end=None)` keys it over
the scene's range at `t = max(0, (seconds since frame_start − start) · speed)`;
`stop()` removes those keys (the pose stays). Objects a clip never moves stay
unkeyed. Geometry Nodes inputs a sample changes on the robot's objects or on
parts registered at load are keyed in the same action: the dispenser's
`filament-feed` turns the reel AND pays the live strand out in the saved file.
Do not play the robot's sample and a fabrication job on the same axes.
`robot.key_pose(frame)` keys a pose you set by hand (`key_joints(frame)` the
joints `set_joints` moved).

- `set_joints({name: value}, clamp=False)`: revolute and continuous joints turn
  about their axis from the rest (radians), prismatic ones travel along it
  (metres); the whole transaction is validated first, and a value outside the
  limits raises unless `clamp`. The rotary fixture's output and chuck share one
  A-axis angle. `reset()` puts every module back at rest (MANTIS's nominal pose).
- `grasp(0..1)` preserves the reviewed approach and curved final thumb contact.
  `grasp_reference()` creates the grasped cylinder under each hand.
- `jaw_gap(0..0.044)` drives both jaws and the opposed screw. Zero closes them.
- `spin_rotors(angle)` drives every propeller with its proper direction (and
  refuses folded booms); `fold(0..1)` parks propellers, releases locks, then
  folds the booms.
- `track_travel({root: metres, ...})` updates both belts and wheels. Track shoes
  are rigid objects split from the batched mesh (their own faces, exact
  shading), each placed round its stadium path; the `drive` and `drive-circle`
  samples coordinate chassis travel with both tracks.
- `flight` demonstrates takeoff, translation and landing. These are authored
  kinematics, not a claim of flight dynamics, contact physics, actuator
  capability or load capacity.
- The complete humanoid and quadruped include `walk`, `run-circle`,
  `run-figure_eight` and `run-straight`. Walking plays all the GLB's own
  channels (looped, linear and slerped as three's mixer does); running writes
  the reviewed sampled trajectories as local joint matrices (`robot.running`, a
  `RunningController`: `frame(clip, t)` the interpolated base, yaw, pitch and
  joints; `apply(clip, t)`; `restore()`; `bounds(clip)` the box the run sweeps;
  `duration(clip)`; `create_running_controller(nodes, quadruped, data)` builds
  one over any `{node name: object}` map).
- `cooling_fan(seconds, rpm=4800)` turns the extruder fan;
  `rotary_setup(stock_length, stock_width, stock_height, quill)` sets the
  rotary fixture's tailstock, quill, handwheel and jaws for a blank (80-180 mm
  long, 18-50 mm wide and high); the `stock-setup` sample sweeps it.
  Carving on this machine: [Rotary carving](rotary-carving.md).
- A650: `joints([q1, ..., q6])`, `move_to(target, seed)` and `robot.ik`
  (`SerialArm`). `target` is a 4x4 Matrix in the robot's frame; the solver is
  bounded damped least squares, and an unreachable target raises.
- S500: `scara_joints([shoulder, elbow, quill, tool])` and
  `move_scara((x, y, z), yaw, tcp=(0, 0, 0), seed=None)`; `robot.scara` is the
  analytic solver (`forward`, `inverse`, `demo`, `limits`, `grip_tcp`: scara.js's
  `limits` and `gripTCP`; the first edition's `LIMITS` and `GRIP_TCP` are aliases).
- G430: `axes((x, y, z))` uses machine XYZ travel (the lead screws turn with
  it); `move_tool((x, y, height))` is in the gantry base's frame with the height
  above the bed; `tool_tip()` returns that frame, `tool_tip(world=True)` a world
  point. `robot.machine` holds `bed_top`, `axis_limits`, `bed_bounds`, `tool`,
  `cutter`, `rest_tip` and `to_axes`.

The solvers are importable on their own (plain Python): `scara`, `SerialArm`,
`articulated_demo`, `gantry_demo`, `constrain_gantry_pose`, `grasp_values`,
`rotary_fixture_setup`, `track_frame`.

### Joint sliders

```python
from eidoblend.characters.robotics.rig import measure_joints, rig_joints, set_slider, unrig_joints
rig_joints(arm)                         # one custom property per joint on arm.group: 'joint:a650_j2' ...
set_slider(arm, 'a650_j2', 0.6)         # or drag it in the N panel; keyable like any property
unrig_joints(arm)
rig_joints(arm, measure_joints(arm))    # the sliders start where the joints are on screen: the pose stays
```

Every revolute and prismatic joint with limits (and the rotary fixture's "A axis
/ chuck") gets a slider with its limits as the range, driving its module through
a simple-expression driver (no Python driver, so it evaluates with auto-run
off). The sliders start at `robot.state` (what `set_joints` set) unless given
values; `measure_joints(robot)` reads each one off its module's current
transform (the turn about the axis from rest, or the travel along it, clamped to
the range), so rigging a robot mid-clip keeps the pose a keyed or sampled clip
gave it. A robot with sliders is in manual mode: unrig it before `play()`.

## Studio and framing

`studio(scene, grid=True, shadows=False)` is studio.js's presentation: the
camera sees `#c6cfd1`; the light is three's RoomEnvironment at intensity 0.9
(its room, six boxes and six emissive panels ray-cast from the origin into an
equirect, as the PMREM generator sees it, blurred by its 0.04 rad), a hemisphere
light (sky `#e6f2ff`, ground `#485654`: a world split at the horizon gives
three's exact irradiance mix), a sun `#fff3e4` at 2.3 from three's (2, 5, 3),
and the 8 m, 80-division grid (centre lines `#748b91`, the rest `#acb9bd`). The
WebGPU studio's sun casts no shadow (`shadows=True` turns it on). The view
transform is AgX, the film contract.

**The grid is one pixel wide at any distance**, as WebGPU draws its line
primitives, so it stays the visible floor of every still. A strip of fixed world
width cannot do that (a 1.2 mm line is a tenth of a pixel at the motion
example's camera, 9.6 m away), so the grid is a plane 1 mm under the floor whose
`BLENDED` shader covers the pixels within half a pixel of a line. The screen
distance to the nearest line comes from the camera's projection at the shading
point (world x and y through Vector Transform to camera space: their
Jacobian), and the pixels per unit come from drivers on the scene's camera
(lens, sensor, sensor fit, type, ortho scale) and the render size, so it stays
one pixel when the camera, the resolution or its percentage changes, a
render-time probe cap included. The plane lights nothing, casts nothing and
stays out of the light probes.

**The unlit colours look as the WebGPU film shows them.** The WebGPU examples
render with ACES tone mapping, which reaches the clear colour and the grid lines
too: the film shows the background as (204, 208, 209). AgX would show `#c6cfd1`
as (175, 179, 180). The lit robots stay AgX, but the background and the two line
colours get the radiance that the scene's colour management displays as three's
ACES of their colour (found by Newton steps on what `Image.save_render` writes).
`studio()` solves this for the settings it finds; after changing the view
transform, look, exposure or gamma, call `match_display(scene)`.

`frame_camera(camera, objects, direction=(0.9, −1.5, 0.55), margin=1.25)`
places the camera on `direction` far enough that the world box of the objects
(or `(min, max)` boxes) fits, looking at its centre, with three's near and far
rule. `make_camera(fov)` uses three's vertical field of view. `world_box(objects)`
is that box (three's `Box3.expandByObject`: hidden meshes count too);
`visible_only=True` on either leaves out meshes hidden from the render and the
inspector's overlays, as the inspector's fit does. Objects disabled in the
viewports keep a stale `matrix_world` in Blender (the depsgraph skips them), so
the box composes their matrix from the parent chain instead. A mesh whose
modifiers make or change its geometry (the rotary job's Volume to Mesh stock, a
Geometry Nodes strand) counts with its evaluated bounds.

```python
from eidoblend.characters.robotics import load_part, frame_camera, make_camera
yoke = load_part('face', 'FACE swept tilt yoke')
cam = make_camera(35)
frame_camera(cam, [yoke.group], visible_only=True)       # the part, not its hidden donor meshes
```

## Inspector

The WebGPU inspector (`serve_inspector.py`, a browser page on localhost:8989)
becomes a scene you open, driven by an `Inspector` (the page's state and its
`window.roboticsInspector` handle; it is also a dict of what the page shows):

```python
from eidoblend.characters.robotics.inspector import inspector_scene
insp = inspector_scene('humanoid', clip='run-circle', wireframe=True)     # the studio, the robot, the clip keyed over 20 s
insp = inspector_scene('arm', joints=True)                                # manual mode: the joint sliders
insp = inspector_scene('hand', reference=True, uv='hand_uv.png')          # the grasp reference; the UV split view
print(insp['status'], insp['ports'])                                       # also on the scene as custom properties
insp.set_motion('grasp'); insp.set_time(2.5)                               # the motion list and the time slider
part = insp.pick(0.5, 0.45)                                                # a click on the image: the part under it
insp.draw_uv('palm_uv.png')                                                # the UV split view of that selection
insp.set_wireframe(True); insp.set_reference(False); insp.set_colors('#d8dcd9', '#3d7f86')
bpy.ops.wm.save_as_mainfile(filepath='hand_inspector.blend')
```

| viewer.js | Inspector |
| --- | --- |
| asset list | `load(model)` |
| motion list, `setMotion` | `clips()`, `set_motion(clip)` (keys the clip over the 20 s) |
| time slider, `setTime`, Reset, Play | `set_time(t)` (the job seeks t, the keyed timeline shows it, sub-frames included), `reset()`, `play()` |
| Frame, Inspect workpiece | `fit()`, `frame_work()` |
| Body / Accent / Filament pickers | `set_colors(primary, accent)`, `set_filament_color(c)` |
| Wireframe, Hand grasp cylinder | `set_wireframe(on)`, `set_reference(on)` |
| part list, click on the canvas | `pick_part(name)`, `pick(x, y)` (a ray cast; x, y in 0..1 from the top left) |
| UV split view, map list | `draw_uv(path, batch, channel, material)` |
| joint sliders | `set_joint(name, value)` (rig.py's drivers) |
| stock material, rotary blank | `set_stock(material, preset, length, width, height)` |
| process playback, workpiece source, `setSource` | `set_timing('lapse' / 'physical')`, `set_source(obj or 'handle' / 'bracket' / 'ring')` |
| process state line, workpiece-source line | `process_state()`, `source_info()` (also `insp['state']`, `insp['source_info']` and the scene's `inspector_process_state`, `inspector_source_info`) |

It keeps the inspector's camera fit (the sweep of walk, drive-circle, flight and
the runs, over the visible meshes), the part picker's triangle count and the UV
split view (a metadata texture binding or a material's map, with the UV
triangles of the batch, material or part drawn over it). The wireframe is
three's `WireframeGeometry` drawn one pixel wide at any size: a copy of each mesh
at its own matrix whose blended material is the Wireframe node in pixel size, so
the surface hides the edges behind it as the WebGPU lines' depth test does.

The time slider works as viewer.js's `sample()`: `set_time(t)` seeks the job to
t (so the state line, `'extrude | 473.2 mm fed | 0.00 mm retracted'` at 9 s of
the print, is the job's at t) and shows the keyed frame. A joint slider puts the
inspector in manual mode: the motion's keys stop (the job stays), every slider
starts where its joint is on screen (`measure_joints`), so only the moved joint
changes, and its value is clamped to the joint's range. The time slider, Reset
and Play leave manual mode: the drivers go, the motion is keyed again, and Reset
shows its pose at 0 s without moving the camera.

A machine with a tool opens on `process`, as there: the job is
`eidoblend.fabrication`'s (`print` of the inspector's 6 mm lathe ring at 40 mm
with 25 % infill, `mill`, `carve` of the relief, `rotary_carve`), time lapse 18 s
(32 s on the rotary machine), keyed over its duration. The workpiece-source line
follows viewer.js: the invitation to load a mesh without one, the slicing note on
the FDM machine, the relief note on the ball-nose machine, and on the rotary
machine the program's report (`'handle. 1,040 source triangles; 12 indexed
views. Some regions exceed tool reach and retain material. Undercuts and holding
ends may remain.'`). Physical timing keys the job's own time frame by frame, so
it is refused past `MAX_KEYED_FRAMES` (25 min at 24 fps): the pocket mill
machines for 20 min and the print for 15, but the relief for 7.8 hours (time
lapse, or `process_options={'duration': seconds}`, instead). The rotary job
writes one stock file per keyed frame next to the saved `.blend`: save first, or
pass `process_options={'cache_dir': ...}` (a coarser `resolution` and a lower
`fps` keep the cache small; the test uses 128 x 48 x 48 at 4 fps). "Inspect
workpiece" frames its carved stock. A local STL or GLB is imported with
Blender's own importer and handed to `set_source`.

## Examples

The three robotics examples are ported as builders and as harness scene
scripts with their own configs:

```python
from eidoblend.characters.robotics.examples import EXAMPLES
EXAMPLES['mantis'](bpy.context.scene)          # assembly | mantis | motion: everything built and keyed
```

```powershell
python eido_blender.py render blender/eidoblend/characters/robotics/scenes/assembly.json
python eido_blender.py render blender/eidoblend/characters/robotics/scenes/mantis.json
python eido_blender.py render blender/eidoblend/characters/robotics/scenes/motion.json
```

`assembly`: the backbone with the stereo camera and the pan/tilt face on its
sensor ports, both playing `joints`. `mantis`: MANTIS driving its circle, the
camera carried with the body. `motion`: the humanoid and quadruped running
their circles, the hand drone flying, the tracked arm driving. They declare
`_no_auto_enhance`: their studio light is the presentation. Probe-size harness
configs for checking them against the WebGPU frames (960 x 540, 16 samples,
outputs in the test folder) are `blender/tests/robotics/harness_{assembly,mantis,motion}.json`:
`python eido_blender.py render blender/tests/robotics/harness_mantis.json --at 6`.

## MechParts and RoboticArm

Two modules of the older production engine come with the kit:

```python
from eidoblend.characters.robotics import mech_parts as mp
from eidoblend.characters.robotics.legacy_arm import RoboticArm

box = mp.chamfered_box(0.3, 0.2, 0.25, 0.03)                  # crisp-facet box, analytic normals
cable = mp.make_cable((-1, 0, 0.5), (0, 0, 0.45), radius=0.012, sag=0.12, corrugated=True)
tread = mp.make_tread_track(run_len=0.5, cap_r=0.12, width=0.1)
mp.key_tread(tread, 0.25, 1, 120)                             # scrollTread keyed per frame
light = mp.stack_light(s=1.5)
mp.key_lights(light, 1, 120, modes={1: 'run', 48: 'warn', 96: 'fault'})
arm = RoboticArm(mount_point=(2, -1, 0), tool='saw')
arm.bake([{'time': 0, 'target': (2.3, -1.6, 1.2), 'action': 'cut'}, {'time': 2, 'target': (2.7, -1.2, 0.5)}], 1, 72)
```

`mech_parts` is MechParts whole: chamfered box, lathe housings (motor, gearbox
bell, joint hub, with their profiles), arm-link casting, catenary cables and
corrugated conduit, the e-chain, tank treads, wheels and mecanum wheels, vent
grilles, hex bolts, pistons, hose coils, the beacon and the stack light, the
hazard-stripe and brushed-metal surfaces, `mulberry` and the default metal and
rubber; each geometry is three's, vertex for vertex. Instanced parts are linked
duplicates under an empty, so each instance is a keyable transform.
`RoboticArm` is the primitive 2-link arm with its four tools (welder, gripper,
spray, saw); for new work `make_robot('arm')` and `make_robot('gripper')`
supersede it. Its base turns toward the target while its shoulder and elbow
bend in the base's own X-Y plane, so its tip does not reach the target: ported
as it is (the test follows the original's tool tip to the millimetre).

## FDM and CNC

The processes (FDM printing with slicing and the bead front, pocket milling,
relief and rotary carving, the PTFE feed tubes and the live filament) are
`eidoblend.fabrication`'s, which drives this kit's machines through
`robot.machine`, `axes`, `move_tool` and `tool_tip`. The loader runs every
function in `eidoblend.characters.robotics.INSTALLERS` at the end of a load (as
index.js runs `installFilament`), and `RoboticsKit.create_ptfe_tube` /
`service_loop` forward to `facade.FABRICATION`: importing `eidoblend.fabrication`
registers its live filament and its tubes there. index.js imports filament.js
unconditionally, so here a dispenser's load (a robot with a filament stand and
reel: `fdm`, `filament_spool`) imports the fabrication package itself, and so
does the first `create_ptfe_tube` or `service_loop`: a plain
`make_robot('filament_spool')` has its live strand. A loaded dispenser's stats
count filament.js's tubes and strand, as the WebGPU stats do (the fdm: 20,581
triangles, 3,088 of them filament.js's; the catalog's figures are the GLB's own).
The processes' own guide is [fabrication.md](fabrication.md).

```python
from eidoblend.characters.robotics import make_robot, RoboticsKit
spool = make_robot('filament_spool', filament='#da642c')   # loads with its live filament
spool.play('filament-feed')                           # the reel turns and the strand pays out, keyed
tube = RoboticsKit.create_ptfe_tube(points=[(0, 0, 0), (0, 0, .1), (.1, 0, .1), (.1, 0, 0)])
```

## Tests — `blender/tests/robotics/`

```powershell
# the pure solvers against the WebGPU edition (plain Python; run js_parity_dump.mjs first, see its header)
python blender/tests/robotics/test_solvers_parity.py
# from the repository root:
bash run_blender.sh blender/tests/robotics/test_js_parity.py         # the whole catalog, every clip, number for number
bash run_blender.sh blender/tests/robotics/test_attachment_frames.py
bash run_blender.sh blender/tests/robotics/test_runtime.py
bash blender/tests/robotics/render_all.sh                            # the renders (one at a time on a shared GPU)
```

`js_parity_dump.mjs` runs the WebGPU kit in Deno and records, for all 89
entries, the roots, ports, stats and every node's world matrix at rest and in
every clip; `test_js_parity.py` loads the same models and compares them (1317
checks). The ports of `attachment_frames_test.mjs` and `runtime_test.mjs` (its
fabrication case is the fabrication package's) check the flanges from the
triangles, load_part, the catalog, mirrored legs, independent limbs, the solvers
against the meshes, that `play()` keys reproduce `sample()`, and, with the
fabrication package imported, the PTFE forwarding and the keyed filament feed.
The render tests (`render_all.sh`) render every catalog entry
(`out/catalog/`), every clip on the robots that carry it (`out/motion/`),
single parts taken out with `load_part` (`out/parts/`), the normal-map parity
probe, the three examples (and a reopened `.blend`), the inspector (motions,
picking, the UV view, manual mode and Reset, the state and source lines, the
FDM, CNC, relief and rotary processes) and MechParts / RoboticArm (the lineup,
each generator alone in `out/mech_parts/`, each tool close up).
`test_studio_render.py` checks the studio's unlit colours against three's ACES
and its grid drivers against the camera, then renders the empty studio from the
three examples' cameras and compares it block by block with the WebGPU frames
(`out/verify/webgpu/`, when present): the grid lines land on the same pixels and
darken the floor as much. Every
render test also runs build-only (`-- --no-render`: everything built, keyed,
posed and checked, nothing rendered; the results go to
`out/<name>.norender.json`), which needs no GPU.

Original runtime: MIT. Original geometry and authored materials: CC0. Source
scan licenses and excluded proprietary authoring tools are recorded in
`eidoverse/assets/robotics/THIRD_PARTY.md`.

## Not yet ported

- **The inspector's browser chrome**: the orbit controls (Blender's viewport
  navigation does that job) and the file picker (import an STL or GLB with
  Blender's own importer, then `insp.set_source(obj)`). The inspector's clock is
  the keyed timeline: Play is the scene's playback, not a running loop.
- **WebGPU-only machinery, not needed here**: the GLTFLoader texture plugin
  (Blender's importer resolves the external maps; the sampler anisotropy extras
  are validated, but anisotropy is a Blender preference, not a per-texture
  setting), the Deno PMREM reuse workaround in `studio()` and its
  `disposeStudio` (the room environment is one packed image), the
  AnimationMixer (`robot.mixer`: the GLB's clips are muted NLA tracks and the
  walk evaluates them directly), `serve_inspector.py` (no web server: the
  inspector is a `.blend`).
- **Owned elsewhere**: the fabrication processes, the live filament and the PTFE
  tubes are `eidoblend.fabrication`'s; the kit loads them through `INSTALLERS`
  and `facade.FABRICATION`, importing that package when a dispenser loads or a
  tube is made (only an edition without the package shows a dispenser without
  its strand, and then `filament-feed` says why).
- **Physical-timing process playback past 25 minutes**: the relief's 7.8 hours
  would be 675,637 keyed frames, so the inspector refuses it and says so (the
  time lapse plays the same program).
