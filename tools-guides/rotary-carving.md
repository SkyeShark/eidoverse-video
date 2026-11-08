# Rotary carving — all-around CNC on the G430 XYZ + A

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Robotics kit](robotics.md)

`eidoblend.fabrication.rotary` carves a turning blank on the `cnc_rotary`
machine: the G430 gantry with the adjustable rotary fixture (a four-jaw chuck
on a hollow rotary drive, a sliding tailstock with a live centre). The cutter
moves in XYZ while the stock indexes about its own long axis, so a sculpture
can be cut from every side. The planner, the timing, the swept-cutter
geometry and the chip events are the WebGPU edition's, number for number; the
carved stock is a real mesh that Blender lights, shadows and renders, keyed
over the film so a saved `.blend` plays and renders any frame on its own.

```python
from eidoblend.characters.robotics import make_robot
from eidoblend.fabrication.rotary import rotary_carve, sample_rotary

machine = make_robot('cnc_rotary', primary='#b9c7c8', accent='#235b68')
job = rotary_carve(machine, sample_rotary, material='wood', duration=28,
                   cache_dir='//rotary_stock_cache')
job.play()                      # every frame of the scene's range, keyed
```

`rotary_carve` accepts a radius function `radius(x, angle)` in metres and
radians (the sample sculpture is one), or a supplied model: a mesh Object
(with its children, modifiers, armature pose and Geometry Nodes instances), a
Collection, a Mesh datablock, or a `(vertices, triangles)` pair.

```python
bust = bpy.data.objects['bust']
job = rotary_carve(machine, bust, material='aluminum', duration=32,
                   stock_length=.140, stock_width=.036, stock_height=.036,
                   angles=12, grid_step=.0005, sample_step=.001, stepover=.00165,
                   cache_dir='//bust_cache')
print(job.program.report)       # source triangles, the fit, reach and retained ends
bust.hide_render = True         # the model is the target; the stock is what you see
```

A supplied model keeps its world orientation and is fitted uniformly inside
the cutting region; `fit=False` uses geometry already placed in stock
coordinates. Option names are the WebGPU ones in snake_case
(`stockLength` → `stock_length`, `sampleStep` → `sample_step`,
`engagementResolution` → `engagement_resolution`). The fabrication package
forwards the same names (`fab.rotary_carve`, `FabSim.rotary_carve`,
`CNCSim.rotary_carve`) to this one.

## Stock coordinates

The stock's long axis is X. Z is its height (the direction toward the cutter
when the A axis is at 0) and Y its width; a stroke's lateral offset is Y. This
is three's stock frame turned like everything else in eidoblend (three
`(x, y, z)` → Blender `(x, -z, y)`), so the A angle, every distance and the
sample's `radius(x, angle)` mean the same thing: the target's radius at stock
angle θ is measured at the point `(x, -r sin θ, r cos θ)`, and the station that
cuts it turns the stock to A = -θ. Machine positions (`job.state['position']`,
`machine.move_tool`) are in the bed frame: gantry_base's axes with the origin
on the bed top, so a stock point `p` at A is at
`(p.x + axis_x, R_x(A) p .y, R_x(A) p .z + axis_height)`.

## The machine and the fixture

`make_robot('cnc_rotary')` loads the gantry and fixture from the robotics
kit. `machine.rotary_setup(stock_length, stock_width, stock_height, quill)`
closes all four captured jaws on the blank and slides the tailstock and quill
onto its end, returning the datums; `rotary_carve` calls it for you. The
fixture accepts stock 80–180 mm long and 18–50 mm wide and high (default
140 × 36 × 36 mm; width and height may differ). The chuck-side end stays at
machine X = -55 mm, the blank's centre at `-.055 + stock_length / 2`, its axis
97 mm above the table. Cutting keeps 29 mm at the chuck end and 18 mm at the
tail end; part-off is a separate operation. The tailstock travels -60 to +40 mm
on its dovetail bed and the quill ±6 mm on a 1 mm-pitch handwheel; a quill
offset on a carriage at the end of its travel exceeds the envelope and is
refused. The jaws grip 13 mm of end stock. Eight M6 table studs engage sliding
T-nuts under the 8 mm bed-slot mouths (`RC table stud 0` … `7`,
`RC table T-nut 0` … `7`; the nuts' undersides are real surfaces). The kit's
`stock-setup` motion sample shows the carriage, quill, handwheel and jaws
adjusting to varied blanks with no stock clamped.

```python
from eidoblend.fabrication.rotary import rotary_fixture_setup
s = rotary_fixture_setup(stock_length=.12, stock_width=.03, stock_height=.044)
s['axis_x'], s['start'], s['end'], s['joints']
machine.set_joints({'rotary_output': 1.2})     # output and chuck turn together
```

The robotics inspector drives the same job on this machine: its stock presets
and blank size fields fit the blank and restart the carving through
`rotary_carve` ([Robotics kit](robotics.md)).

The rotary drive's output and the chuck share one A angle: setting one sets
both, and setting them apart raises. The stock rides the chuck as a child of
it (`job.mesh`, the stock frame), so turning the chuck by hand turns the
stock; `job.stop()` first, since a played job's keys own that axis. Place and
turn the machine anywhere in the scene: the stock and the chips follow its bed
frame. The rotary assembly carries the 6 mm two-flute flat end mill with
18 mm of exposed cutting length; a requested tool, radius, axis offset or end
stock that disagrees with the fitted machine is refused, as is any move past
the gantry's travel or an index without retracting clear of the stock's
corners. All of it is checked before the scene changes: an invalid job leaves
nothing behind.

The blank comes prepared with a 60° centre seat in its tailstock end (3 mm deep,
a 1.6 mm pilot 6 mm long) that clears the live centre. It is in the stock from
the first frame and makes no chips. `rotary_blank_distance(p, settings)` is
that prepared blank's signed distance.

## Programs

```python
from eidoblend.fabrication.rotary import rotary_program, rotary_mesh_program, sample_rotary
p = rotary_program(sample_rotary, material='wood', tool='flat', angles=96, sample_step=.001)
p.moves        # [{'position': (x, y, z), 'angle': a, 'type': 'rapid'|'index'|'cut', 'stage', 'feed'}]
p.stages       # [{'name': 'rough 1', 'first_move': 1}, ..., {'name': 'finish', ...}]
p.path.sample(120.0)       # the cutter tip, A, stroke, speed at 120 s of the program
p.path.duration            # physical seconds
```

Both planners only plan: no stock is built and the scene is not touched (a
supplied model is snapshot, not changed, and its materials never become the
stock's). `rotary_mesh_program` selects mesh planning explicitly.

A radius function uses circumferential stations (`angles`, default 96, 16 to
512) with an axial stroke at each. The tool offset is the maximum over the
cutter's whole footprint, so axial and circumferential slopes are not
gouged. Every roughing level visits the whole circumference before going
deeper (alternate stations), then the finish cuts every station; the cutter
retracts beyond the blank's corners before each A-axis index, and XYZ stays
still while the stock turns. A target deeper than the flute can reach is
refused.

Mesh planning (`rotary_mesh_program`, or `rotary_program` with a model) turns
the actual triangles toward the cutter from `angles` indexed directions
(default 12, 4 to 96) and cuts lateral XYZ rasters. Each grid cell keeps the
highest point of any triangle clipped to it, so a thin feature between sample
rays still protects itself; the cutter's whole swept footprint protects
nearby surfaces. `grid_step` is the projection cell, `sample_step` the axial
spacing, `stepover` the lateral row spacing; coarser roughing precedes the
finish. Material beyond the flute's reach is left and counted in
`report.reach_limited_samples`; `require_reach=True` refuses such a job. This is
indexed four-axis machining: undercuts the indexed directions cannot see,
cavities narrower than the cutter and features needing a tilted tool are not
reproduced, and the report does not certify complete accessibility.

`RotaryPath(moves, feed, rapid, acceleration, rotation_speed)` times any
indexed program: trapezoidal feeds with look-ahead along finely sampled rows,
full stops at plunges, retracts and indexes, and index moves eased over
`1.5 × angle / rotation_speed` (at least 20 ms). `sweep_distance(point, segment,
radius, flute_length, fraction, tool)` is the independent swept-cutter
distance (ball nose or flat end with its cutting length) for planning and
review queries; `sweep_distance_np` takes arrays.

## The carved stock

The stock is a clamped signed distance on a grid over the blank plus a
two-cell pad (`resolution`, default 256 × 96 × 96 samples along X, Y, Z). It
starts as the prepared blank and takes, for every cutting stroke up to the
moment shown (that one to its fraction), the maximum with minus the swept
cutter's distance. Strokes only remove, so going forward applies only the
strokes since the last update; going back rebuilds from the blank and gives
the same field. numpy evaluates each stroke over only the voxels its sweep can
reach: the whole 36,480-stroke wood program carves in under half a minute at
the default resolution, steel's 150,480 strokes in about a minute and a half.
The field and the prepared blank it rebuilds from are two float32 grids of
9.4 MB each at that resolution; `job.stock.cell_size` is their spacing, and a
finer `resolution` resolves finer scallops for more time and file size.

Each keyed frame's field is written as an OpenVDB grid (`density`, positive
inside, half floats, constant blocks pruned to tiles) to
`<cache_dir>/<name>_<frame>.vdb`, about 1.2 MB at the default resolution. The
stock's Volume datablock plays that file sequence, holding the first and last
outside it, and the stock object's Volume to Mesh modifier meshes the current
file at the zero level: a closed surface of about 100,000 vertices with every
face outward. It casts and receives shadows like any mesh. Keep the cache
folder beside the `.blend`; `cache_dir` relative to an unsaved file is refused
rather than written somewhere unexpected.

```python
stock = job.stock
stock.update(job.path.sample(t))        # the field at a program time
stock.write_frame(frame)                # that field as this frame's file
stock.readback()                        # a copy of the field (nx, ny, nz)
stock.tiled()                           # the WebGPU edition's tiled 2D layout of it
carved = stock.to_mesh('finished part') # a static mesh of the current field to keep or export
```

Carved to the end, the wood example's part lies within 0.13 mm of its target
(`rotary_surface`), 3 µm on average (`test_rotary_target_vs_carved.py`).

The stock's surface uses the fabrication family's `finish_stock`: hardwood's
3D growth rings and fibre (birch plywood's plies), or brushed metal with
patina, filtered by their screen footprint. The finish reads the stock point
the way the WebGPU stock handed it over, `(z, y, x)` in three's axes, so the
long grain and the rings run along the rotary axis and the pattern is the
WebGPU one exactly. That swizzle is a reflection, so it lives in the material:
`swizzle_finish(material)` puts it into any `finish_stock` material (the stock
does this to its own; do it to a material you pass as `material=` or to a
snapshot you shade separately).

```python
from eidoblend.fabrication.cutting import stock_material, stock_profile
from eidoblend.fabrication.rotary import swizzle_finish
mat, finish = stock_material('brass part', stock_profile('brass'))
swizzle_finish(mat)             # the rotary stock's grain coordinates
```

## Playback

```python
job.seek(14.0)            # the machine, A axis, spindle, stock and chips at 14 s of playback
job.key(frame)            # key that pose (LINEAR) and write the stock's file for the frame
job.play(start=0, speed=1)  # seek and key every frame of the scene's range
job.stop()                # remove the job's keys; the stock holds as it is
job.dispose(files=True)   # remove everything the job made, cache files too
```

`duration` changes playback speed only: playback time maps linearly onto the
physical program (`job.physical_duration`). Omit it for physical timing.
Spindle rotation and chip flight use the physical clock even in a time lapse.
`job.state` carries the sample (`stage`, `type`, `speed`, `angle`, the
unwrapped A angle) plus `position` (the cutter tip over the bed),
`stock_position` (the tip in stock coordinates), `physical_time` and
`playback_time`; `job.done` turns true at the end and `on_done(job)` is called
when the job gets there (again only after a seek has taken it back from the
end). In a harness scene, seek and key from `render_frame`, or let `play()` key
the whole range in `setup`. After `play()`, a manual `seek` shows until the
next depsgraph update; then the keys win, as for any animated property.

Chips come from a one-time volumetric engagement sample
(`rotary_removal(path, settings, resolution)`, default 96 × 28 × 28): each
voxel of the blank is charged to the first stroke that reaches it, at the
fraction where the cutter first touches it, and bucketed into events by eighths
of a stroke, so repeated cuts and air travel make no false chips.
`job.removal.removed_volume` is a sampled estimate. The chips themselves are
the fabrication family's `cutting_debris`: wood shavings and fines, or folded
metal swarf, flying on their physical clock from the cut.

## Metal studies

`material='aluminum'` or `'brass'` (also `'steel'`, `'plywood'`) changes the
stock's look, its chips and the presets' feeds and depth steps: more passes
and much longer physical cutting than wood. The sample sculpture at each
preset's own rates:

| material | stages | cutting strokes | physical time |
|---|---|---|---|
| wood (hardwood) | 7 | 36,480 | 38 min |
| plywood | 7 | 36,480 | 44 min |
| aluminum | 17 | 82,080 | 8.1 h |
| brass | 17 | 82,080 | 9.7 h |
| steel | 32 | 150,480 | 44.7 h |

Omit `duration` to see those rates; equal time-lapse durations hide the
difference. Wood throws shavings and fine dust, metal throws folded swarf (no
dust, no sparks). The gantry depicts light machining: the steel preset does
not establish machine stiffness or heavy steel cutting, and coolant, cutting
forces, chip collisions, heat and tool wear are not simulated.

## Examples

`EXAMPLES` holds the WebGPU examples as builders that make the whole scene and
key it; the harness renders them as films:

```bash
python eido_blender.py render blender/eidoblend/fabrication/rotary/scenes/rotary.json
python eido_blender.py render blender/eidoblend/fabrication/rotary/scenes/rotary_metal.json
```

```python
from eidoblend.fabrication.rotary.examples import EXAMPLES
rec = EXAMPLES['rotary'](scene, cache_dir='//rotary_cache')
rec = EXAMPLES['rotary_metal'](scene, frames=[1, 49, 241, 721], cache_dir='//metal_cache')
```

- `rotary` — the sample sculpture in hardwood, the whole program over 28 s
  after a one-second hold, from the WebGPU camera (36°, 1280 × 900, 31 s).
- `rotary_metal` — aluminium: two seconds of setup, eight seconds of real
  cutting from the first chip (at 142.75 s of the program), then a time lapse
  to the finished part; the camera cuts in close for the cutting and back out
  at 28 s. Set `material='brass'` for brass.

Both use the robotics studio (its ported room environment, without the grid).
`frames=` keys only some frames (render only those). A full film writes one
stock file per frame: `rotary`'s 744 frames take 0.9 GB (1.2 MB a frame;
the metal study's are 0.9 MB).

## Tests

```bash
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_parity.py       # against the JS (rotary_js_dump.mjs)
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_js_tests.py      # the Deno tests, ported
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_carve_options.py # every rotary_carve option, the job API, every refusal
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_stock_field.py
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_scene_scripts.py   # the two scene files, as the runner calls them
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_examples.py        # builds both examples at probe frames
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_examples.py -- examples=rotary_metal material=brass suffix=_brass
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_mesh_carve.py      # a supplied model (Suzanne) carved
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_chips.py           # chips in flight from the cut
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_target_vs_carved.py
bash run_blender.sh blender/tests/fabrication_rotary/test_rotary_materials_lineup.py  # every preset, carved by its own program
bash run_blender.sh blender/tests/fabrication_rotary/render_rotary_probes.py -- blend=out/rotary_example.blend frames=1,337,743 views=scene,close
bash run_blender.sh blender/tests/fabrication_rotary/render_rotary_probes.py -- "jobs=out/rotary_example.blend@73,433@close;out/rotary_chips_wood.blend@1,2,3@scene"
```

`rotary_js_dump.mjs` writes the JSON the parity test reads (run it once in Deno
from the main checkout; its header has the command). The two examples also
build through the harness itself from three-second scene files whose outputs
land in the test folder:

```bash
python eido_blender.py build blender/tests/fabrication_rotary/harness_scenes/rotary_harness_probe.json --no-probe-bake
python eido_blender.py build blender/tests/fabrication_rotary/harness_scenes/rotary_metal_harness_probe.json --no-probe-bake
```

Renders go through the shared GPU slot (`heavy.sh`), the builds do not need it.

## Not yet ported

- **The WebGPU stock pass and its renderer.** The field is computed by numpy
  and meshed by OpenVDB instead of a fragment pass ray-marched on a proxy box;
  there is no `renderer` option. `stock.texture` is the current frame's VDB
  file, `readback()` returns the 3D field (`tiled()` gives the WebGPU tiled
  layout of it).
- **The flat end's sub-surface values.** Below a sloped stroke the flat end's
  distance is the JS's normalised bound; the WebGPU edition evaluated it over
  its coarse bins, this edition over each stroke's box. The surface (the zero
  level) is the same; field values a few cells under a sloped floor can
  differ, and like there they depend on the frames sampled.
- **No deformation motion blur on the cutting front.** The stock's surface is
  re-meshed each frame; its turn with the chuck blurs as object motion, the
  advancing cut does not.
- **The spindle under motion blur.** The rotor is keyed each frame at its
  physical angle, as the WebGPU edition set it each frame; at 18,000 rpm that
  is 12.5 turns between frames, so with motion blur on, the interpolated rotor
  turns slowly instead of blurring into a disc.
- Fixture, workholding and tool-envelope collisions are not checked (a valid
  XYZ path is not collision checking), as in the WebGPU edition.
