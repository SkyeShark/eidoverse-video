# G430 fabrication: FDM printing, pocket milling and relief carving (Blender edition)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Robotics](robotics.md)

The G430 gantry prints and mills. A print grows bead by bead under the nozzle,
fed from the reel through real PTFE tubing; a pocket or a relief is cut from
heightfield stock by the actual swept flat-end or ball-nose cutter, with chips
and dust thrown from where material comes off. In the Blender edition the package
is `blender/eidoblend/fabrication/`; the machines themselves are the robotics
kit's (`eidoblend.characters.robotics`). Every job is keyed: the machine axes,
lead screws, spindle, fan, reel, feed tubes, bead front, stock and chips are
object keys and Geometry Nodes inputs, so a saved `.blend` plays and renders any
frame on its own. Paths and positions are Blender's axes: Z up, metres, the bed
frame's origin on the bed top (three's `[x, height, z]` is `(x, -z, height)`).

## Print

```python
import sys; sys.path.insert(0, '<repo>/blender')
from eidoblend.characters.robotics import make_robot
from eidoblend import fabrication as fab

printer = make_robot('fdm', position=(-.78, 0, 0), accent='#267c82', filament='#218675')
job = fab.print(printer, source,                     # a mesh object (with children), a Mesh, a Collection
                size=.04, layer_height=.0004, bead_width=.0008, infill=.25,
                base=.00065, feed=.025, duration=18, color='#278b79')
job.seek(4)            # pose everything for playback second 4 (machine, bead front, reel, tubes)
job.play()             # key every frame of the scene's range: t = (seconds - start) * speed
job.set_color('#da642c')   # the deposited bead, the spool, the live strand and the guided cores
```

`play()` keys the scene's whole range; `key(frame_start, frame_end, start=,
speed=)` keys only those frames and leaves the rest of each curve as it is, so
one machine can run one job after another in a film:

```python
bracket = fab.manufacturing_sample('bracket', as_parts=True)
ring = fab.manufacturing_sample('ring', as_parts=True)
first = fab.print(printer, bracket, size=.03, center=(-.022, 0), duration=3)
second = fab.print(printer, ring, size=.024, center=(.024, 0), duration=3)
first.key(1, 72)       # the bracket prints over frames 1..72 and stays on the sheet
second.key(73, 144)    # then the ring, beside it; the axes, reel, fan and tubes carry both ranges
second.stop()          # removes frames 73..144 only; the first job's keys stay
```

Each job seeks its own clock, so the head, the reel's turn and the consumed
length start again from the second job's beginning at its first frame (the
WebGPU seek does the same). Keep two jobs on one machine in separate frame
ranges: where they overlap, the later `key()` wins. `stop()` and `dispose()`
take the job's actions away with its keys once they are empty. `on_done=`
runs when a `seek` reaches the end, which with keys means while `play()` or
`key()` writes them, not during playback: a saved film plays without Python.

**A job at its own speed.** Leave `duration` out and the job takes its real
time: the pocket mill 20 minutes, the relief carve 7.8 hours (675,637 frames at
24 fps). Keying that frame by frame is tens of millions of keys, so
`job.key_events(frame_start=None, scene=None)` keys the program's events
instead (`eidoblend.fabrication.physical`; any job, `RotaryJob` included):

```python
carving = fab.carve(make_robot('cnc_relief'), fab.sample_relief, material='wood')   # no duration: 7.8 hours
carving.key_events()          # 103,982 events, 416,000 keys, a 48 MB .blend; plays from frame 1 at the real speed
carving.event_keys            # {'events', 'keys', 'frames': (first, last)}
```

Between two events of a program every axis moves as a polynomial of degree
three or less in time: a move accelerates at a constant rate, cruises and
brakes; an index turn eases by a smoothstep; a dwell retracts at a steady rate.
A Bezier key at each event, its handles a third of the way to its neighbours
along the exact velocity there, reproduces that motion exactly at every frame
and sub-frame (`test_inspector_physical.py`: the tool tip within 3 µm of the
program at random times, inside accelerations too). The axes are the machine's
joint sliders (the robotics kit's `rig`, custom properties on the robot's empty
that move the modules through simple-expression drivers), keyed at the events;
the lead screws follow their axis' slider and the spindle and the cooling fan
turn at their rpm with the frame (drivers, nothing keyed); the progress the bead
or the stock reads is keyed at the same events and the chips' clock at the two
ends. A print's reel, live strand and feed tubes are posed at the events, at
most one every `physical.FILAMENT_FRAMES` (4) frames, and keyed LINEAR: the
ring print's 15 minutes take three to six minutes to key, its 14,462 events
428,000 keys. A saved file plays the job on its own. Blender's last frame is 1,048,574,
so at 24 fps a job ends past it after 12.1 hours (`key_events` says which fps
fits); key frame times are float32, so near frame 675,000 an event lands within
1/16 frame and the spindle's angle is exact at whole frames.

The source is snapshotted once (`source_geometry`): every visible mesh under
the object as Blender evaluates it now (modifiers, the armature's pose, shape
keys, Geometry Nodes and collection instances), placed by its world matrix,
reflections flipped back to outward winding; the source is never edited.
`space='local'` ignores the root's own placement; `matrix=` applies a 4x4 first.
`fit_source_geometry` scales it uniformly so its largest extent is `size`,
centres it on `center=(x, y)` and stands it on `base`. A mesh that is open or
non-manifold at a slice raises rather than printing something else.

`slice_geometry` cuts the fitted solid into layers. Each mesh is sliced on its
own, its rings chained by shared points; inner walls become holes by the
surface's winding, holes go to the smallest solid around them, and overlapping
meshes are unioned, so a lug pushed into a shaft prints as one part and a core
standing inside a shell's bore survives. Perimeters follow every contour; infill
alternates X and Y rows, `infill` of them sparse (0.25 by default), with three
solid layers (`solid_layers=3`) wherever the cross-section changes above or
below, so ledges and roofs close while the interior stays sparse. Travel lifts
`travel_lift` above the higher end and deposits nothing. Exact toolpath parity
with the WebGPU slicer is tested (`test_fabrication_parity.py`): layers,
perimeter and infill lengths per layer, move counts, travel and print time match
to 1e-9. The union (`polygon_union.py`, this edition's own) snaps coordinates as
the vendored polygon-clipping does: an x or a y within about an ulp of one seen
before in the same union becomes that one. So the rotated handle, whose
placement goes through `sin` and `cos` (CPython's and V8's differ by an ulp now
and then), slices move for move as the WebGPU path does (2,198 moves; without
the snapping one quad diagonal's slice point stayed an ulp off its neighbours'
line and added a move).

The path's feed clock is one acceleration-limited trapezoid per move
(`FeedPath`: `feed`, `rapid`, `acceleration`, corners blended within
`blend_tolerance`), plus direct-drive retraction before each travel and a prime
after (`FilamentPath`: `retract_length=.0008`, `retract_speed=.035`, the
nozzle standing still). That one clock drives the nozzle, the bead and the reel.
`job.filament_length`, `state.filament_length`, `state.filament_retraction`
and `state.filament_speed` are metres and metres per second; `duration` turns a
long print into a time-lapse (`job.physical_duration` is the real time).

**The bead.** The deposited print is one mesh of eight-sided bead sections, one
per chord of the path (arcs split at 0.4 bead widths), each carrying its chord's
ends and its `[start, end]` path distance. A Geometry Nodes modifier stretches
the active section's front end to the nozzle's progress and deletes sections not
yet reached, the WebGPU vertex shader and alpha test as nodes; its `Progress`
input is keyed per frame. Layer height is real geometry; the finish is the beads
themselves. There is no support generation and no printability certificate.

**The sheet.** The 450 x 520 mm bed carries a removable 458 x 528 x 0.65 mm
PEI sheet, its pull tabs past the front edge; the default `base=.00065` puts the
first layer on it. `build_plate=False` hides the sheet and allows another
`base`; `job.plate` is the sheet's root, and disposing the job leaves it.
Prints are kept inside the sheet's unobstructed area; paths beyond the G430's
travel or the bed are refused.

**Filament and tubes.** Importing `eidoblend.fabrication` registers the live
filament with the kit (its `INSTALLERS` hook), so a printer or a standalone
`spool` loaded afterwards has `robot.filament`; `fab.ensure_filament(robot)`
installs it on a robot loaded earlier. The reel turns by consumed volume (1.75
mm filament, the winding's radius shrinking as it pays out); the strand leaves
the winding tangent to its row and walks over the pack, reversing smoothly at the
cheeks. The feed is 174 mm of PTFE: a 34 mm liner through the carrier, a 44 mm
lower entry and a 96 mm head entry, each a cubic Bézier tube that keeps its
length as the head travels, with a coloured filament core inside and the
exposed supply span between. The tubes are Geometry Nodes deformers of fixed
ring meshes (parallel-transport frames from a start normal), so moving the head
re-keys four control points per tube, never a vertex. The extruder fan turns at
4,800 rpm on the same clock (`fan_rpm=`); `robot.cooling_fan(seconds, rpm)`
turns it alone.

```python
tube = fab.create_ptfe_tube(points=[(0, 0, 0), (0, 0, .20), (.12, 0, .20), (.12, 0, 0)],
                            outer_diameter=.004, inner_diameter=.002, segments=48, color='#e7eee5')
tube.set_points(four_local_points)       # modifier inputs only; tube.sample(u), tube.length, tube.points
points = fab.service_loop(start, end, length=.3, up=(0, 0, 1))   # a loop of that length, handles raised along up
```

## Mill and carve

```python
cnc = make_robot('cnc')
milling = fab.mill(cnc, None, material='wood',      # aluminum, brass, steel, wood, plywood
                   stock_width=.078, stock_depth=.128, stock_height=.020,
                   resolution=192, duration=18,
                   effects={'max_particles': 1200, 'seed': 7319, 'dust': True})
fab.STOCK_MATERIALS['brass']                        # the presets (also FabSim.stock_materials())
points = fab.pocket_program(width=.048, depth=.080, cut_depth=.010, stepdown=.002, stepover=.0025)
milling = fab.mill(cnc, points, material='aluminum')   # an explicit path instead of None
```

The material sets the finish and the default feed, plunge, spindle rpm,
stepdown and pocket depth. Metal gets metallic PBR with fine brushing and patina
and small folded chips; wood gets three-dimensional growth rings and fibre
running through the cut walls and floor, larger shavings and fine dust; plywood
shows its plies on the walls. The fine patterns (growth rings, fibre, brushing)
fade by `fwidth(phase)` as the WebGPU finish does, so they never moiré: shader
nodes have no screen derivatives, so `finish_stock` builds the exact one from
each pattern's 3D gradient taken through the pixel's footprint on the surface
(the metres a pixel spans at the point, the surface normal and the direction
to the eye). The footprint is measured in the shader, from the point's
camera-space position against its place in the frame (`pixel_footprint` of
`eidoblend.props.voice_machines`), so it holds for whichever camera renders
the frame: a cut between cameras, an animated lens, any sensor fit, an
orthographic camera, and a stock made before its camera. Measured on the
carved relief and on the rotary part (`test_finish_footprint.py`, the relief
also through a marker cut to a plain 50 mm camera holding it off the frame's
centre), it is the rendered phase's own pixel difference at a median ratio of
1.0. The broad grain and the patina are MaterialX's `noise_float` exactly:
Blender's Noise Texture at Detail 0 is the same Perlin noise (OSL's
lookup3-hashed gradients, quintic fade, scaled by 0.982), measured pixel for
pixel against a transcription of three's TSL (`test_finish_noise_materialx.py`:
65,536 pixels of the broad grain within 8.3e-6 of it, the render's own
precision).
`finish_stock(material, profile, color, axes='bed', scene=None)` reads the
stock point in the 2.5D stock's axes (`scene` gives the render size the
footprint reads; the context scene by default); the rotary stock passes
`axes='rotary'`. These are motion and appearance presets for films, not machining advice:
override `feed`, `plunge`, `rpm`, `stepdown`, `cut_depth`, `stepover`,
`flutes`; a path's own per-move `feed` wins. `job.settings` gives the effective
values, the cutter diameter and the nominal chip load.

The `cnc` assembly carries a 6 mm flat end mill, `cnc_relief` a 6 mm ball nose;
both take `radius=.003`, and a different radius or profile is refused, as is a
`flute_length` longer than the fitted cutter. The table's four toe clamps seat a
78 mm wide stock, 108 to 148 mm deep and at least 15 mm high;
`workholding=False` hides them for your own fixture while the job exists.

**The stock** is a heightfield mesh, `resolution` cells square, with a skirt to
the bed and a floor. A Geometry Nodes modifier evaluates, at every top vertex,
the exact swept envelope of each cut move in its spatial bin up to the keyed
`Progress` (`cutter_height_node`: a flat end's entry or exit, a ball nose
minimised along the full 3D centre path, so sloping passes are exact), the
WebGPU's per-vertex shader loop as a repeat zone; the cut segments and bins live
on three hidden data meshes beside the stock. Ball-nose stock gets the original's
filtered normals (two cells either side, as custom normals) so scallops finer
than the grid do not alias into stripes; flat-end stock is faceted. The nodes
agree with the CPU envelope to well under a micron (`job.inspect_heights(points_xy)`),
and `job.stock.cell_size` is the discretisation: a finer grid resolves finer
scallops at more evaluation time. The pocket program's zig-zag turns at the
walls on alternate rows, so its walls carry real scallops (cusps 0.27 mm deep,
5 mm apart, with the 3 mm cutter at a 2.5 mm stepover). Whether the grid shows
them depends on where its vertex columns fall, as on the WebGPU stock: on the
default pocket at 128 cells the walls run straight, with a one-cell step where
the 3 mm corner radius ends each wall; at 160 cells a column lies inside the
cusps and the long walls show 29 one-vertex teeth; at 256 cells the cusps
read as a slightly ragged wall. The floor and the stock top are the same
finish, so under the studio's light (no shadows, as in the original) a pocket
reads by its walls; a raking light or `studio(shadows=True)` shows its depth.

**Chips** come only from newly removed material, plunges included (air moves and
repeated passes through cleared stock emit nothing). `sample_removal` steps the
cutter through the stock grid and records each removal event (time on the feed
clock, position, volume); `cutting_debris` is a Geometry Nodes pool over those
events: each chip's arc (ballistic for chips, damped for wood fines), spin, size
and tint is a function of its event's identity and the keyed physical time, so
any frame shows the same chips however it is reached. `effects=False` drops
them; `dust=False` keeps wood shavings without fines. Chips live a fraction of a
second; there is no coolant or chip pile. `job.stock.removed_volume` is the grid
estimate in cubic metres. As in the original, framing counts where chips can
fly: a hidden box (`job.effects.bounds`, the stock plus 0.22 m around it, from
4 cm below the stock to 9 cm above it) sits in the machine's hierarchy, and the
hidden chip templates are chip-sized, so `frame_camera` on a robot's group
frames what the WebGPU `frameCamera` frames.

```python
relief_cnc = make_robot('cnc_relief')
carving = fab.carve(relief_cnc, fab.sample_relief,   # f(x, y) -> height, a heightfield, or a mesh source
                    material='wood', stepover=.0008, sample_step=.001,
                    resolution=192, duration=24)
carving.seek(20).stage      # 'rough 1' .. 'rough 5', 'finish', 'retract'
carving.program['stages']   # each stage's distance and point range
h = fab.relief_from_mesh(obj, width=.078, depth=.128, stock_height=.020, floor=.004)
```

`carve` takes a height function `f(x, y)` in stock coordinates (metres, the
stock's footprint centred on the origin), a sampled heightfield
`{heights, columns, rows, width, depth}` (row j at y = (j / (rows - 1) - .5)
* depth), or a mesh placed inside the stock (`relief_from_mesh` samples its
upper visible surface with downward rays, parents' placements included). It is
three-axis: undercuts and side features need another setup. `relief_program`
roughs in levels of `stepdown`, leaving `rough_allowance`, then finishes at
`stepover`; ball-footprint compensation lifts the tip over neighbouring high
ground (`surface_tolerance` is a finish allowance, not a certified error).
`sample_relief` is the original flowing crest on its recessed land.

The planner samples that compensated tip every `sample_step` along a row and
moves straight between samples, as the WebGPU planner does. On a relief this
never dips below the target; beside a wall taller than the leave (a mesh with
vertical sides, like the fork bracket sample) the needed height climbs within
one step and the straight move cuts into the wall: 4.2 mm into the bracket's
12.8 mm walls when it is fitted as the inspector fits a supplied mesh. The
ball kernel's eight rings add their own error there (its height steps grow
toward the rim, the last one 0.48 of the radius). For such meshes pass
`lift_over_steps=True`: each move is checked between its ends and the tool
lifts over a step before crossing it, leaving material at the wall's foot
instead, and a tip whose ball rides a wall on its outer rings is read again
with a fine rim (points 0.1 mm apart). 0.1 mm of cut is left on the bracket,
0.05 mm on the ring and none on the handle, at about 15 s of planning instead
of 1.5 s. A height function `f(x, y)` can have walls of no width, unlike a
sampled heightfield's one-cell slope, so a block's corner can reach into the
ball between the kernel's points with none of them reading it: its rim is also
read where a neighbouring sample's ball rides a wall, and its moves are checked
every 0.1 mm. A 16 mm block on a 6 mm land with a 10 mm step across a diagonal,
carved as a function: the plain planner cuts 7.1 mm into its walls,
`lift_over_steps` 0.14 mm. A program whose moves all pass the check
and whose ball never rides its outer rings, `sample_relief`'s included, comes
out unchanged.

```python
# the inspector's way with a supplied mesh: fit it into the stock above the 4 mm floor
bracket = fab.fit_source_geometry(fab.manufacturing_sample('bracket', as_parts=True),
                                  bounds=((-.032, -.055, .004), (.032, .055, .019)))
plaque = fab.carve(relief_cnc, bracket, material='wood', resolution=192, lift_over_steps=True)
```

Paths are lists of `{'position': (x, y, height), 'type': 'rapid' | 'cut' |
'extrude', 'feed': m/s}`; a rapid through uncut stock, a cut into the bed, a cut
deeper than the flutes and an incompatible clamp setup are refused.

For all-around carving the stock-rotating machine has its own package,
`eidoblend.fabrication.rotary` (`rotary_carve`, `rotary_program`,
`rotary_mesh_program`, `sample_rotary`); `fab.rotary_carve` and
`FabSim.rotary_carve` forward to it. See [Rotary carving](rotary-carving.md).

## Facade, samples and examples

`FabSim.print / carve / mill / pocket_program / relief_program /
relief_from_mesh / source_geometry / fit_source_geometry`, `FabSim.sample_relief()`,
`FabSim.stock_materials()`, `PrintSim.print` and `CNCSim.carve / mill /
rotary_carve` are the WebGPU facade as ordinary calls.
`fab.manufacturing_sample('handle' | 'bracket' | 'ring')` builds the example
sources with three's exact tessellation (`as_parts=True` gives the planners'
exact form without objects in the scene). `eidoblend.fabrication.three_geometry`
reproduces three's Box, Plane, Cylinder, Capsule, Lathe, TorusKnot and Extrude
geometries vertex for vertex, for porting a WebGPU scene's sources unchanged.
The robotics inspector's process panel (the G430's "process" motion with its
timing, stock material, workpiece and sample-mesh choices) is the robotics
kit's inspector scene, `eidoblend.characters.robotics.inspector`, which makes
its jobs with this package.

The examples build and key whole scenes (`eidoblend/fabrication/examples.py`:
`EXAMPLES[name]`, called with the scene), and run as films through
`scenes/<name>.json`:

```bash
python eido_blender.py render blender/eidoblend/fabrication/scenes/manufacturing.json
python eido_blender.py render blender/eidoblend/fabrication/scenes/relief.json
python eido_blender.py render blender/eidoblend/fabrication/scenes/mesh_fabrication.json   # needs fabrication.rotary
```

`manufacturing` is the FDM, CNC and relief CNC side by side over an 18 s
time-lapse; `relief` a close study of roughing and finishing; `mesh_fabrication`
the rotary machine carving the handle sample.

Tests and probes: `blender/tests/fabrication/` (`test_fabrication_parity.py`
against the WebGPU planners in Deno; `test_fabrication_feed.py`,
`test_mesh_input.py` and `test_relief.py` are the three Deno test files with
their assertions, all their tests, the robotics kit's asset checks included;
`test_options.py` for every other option and refusal, the union's snapping and
`lift_over_steps` on a walled height function; `test_finish_footprint.py` and
`test_finish_noise_materialx.py` render the finish's fades and its noise against
the WebGPU's definitions; `blender/tests/robotics/test_inspector_physical.py`
keys the relief, the print, the pocket and the rotary sample at their own
speed; `test_fabrication_render.py`,
`test_presets_render.py` and `test_examples_render.py` build, check and render;
`test_saved_blend.py` reopens the saved example without the package and checks
that it plays on its own; `test_growth_feed_mesh_relief_render.py` renders the
saved example's print and pocket growing over eight times, the live filament
feed at the reel and the head, the dispenser, a service loop and the bracket
carved as a relief with and without `lift_over_steps`;
`test_job_keys_seek_dispose_framing_tubes.py` keys two prints into separate
ranges of one printer, checks that `seek` alone updates the evaluated bead,
stock and chips, that disposing print, mill and carve jobs leaves nothing
behind, and that the example's wide camera frames as the WebGPU one).

## Not yet ported

- **The union's crossing points in the sweep's order.** polygon-clipping meets
  the crossing points it snaps in its sweep's order, this union in its own; a
  crossing point flp-equal to two values seen before can snap to the other one
  (no slice of the examples or the samples does).
- **Chip streaks.** The chip pool stores a persistent `id` per chip (event ×
  per-event + k), which Blender's instancing reads as each instance's
  identity; that it holds a chip's identity through motion blur is not yet
  confirmed in a render, and the rotary job still holds its chips through the
  shutter ([rotary carving](rotary-carving.md#not-yet-ported)).
