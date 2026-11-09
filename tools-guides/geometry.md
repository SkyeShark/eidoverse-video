# Building geometry — constructors, lofts, booleans, curves

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the Blender 5.2 EEVEE edition. For meshes you build rather than
fetch: each constructor takes a curve, a profile, a flat outline or a
repeated unit and generates the surface — the route to shapes no library
carries. Blender axes throughout: Z up, metres (three (x, y, z) → Blender
(x, −z, y)). Built geometry then wants [layer_surface](terrain-surfaces.md)
for texel density and form-following wear.

## Constructors — the Blender recipes for three's

- **Tubes** (three's `TubeGeometry`): pipes, cables, vines, winding paths,
  hair strands. A curve object with a round bevel, or Geometry Nodes Curve
  to Mesh with a circle profile:
  ```python
  cd = bpy.data.curves.new('cable', 'CURVE')
  cd.dimensions = '3D'
  sp = cd.splines.new('BEZIER')
  sp.bezier_points.add(len(points) - 1)
  for bp, co in zip(sp.bezier_points, points):
      bp.co = co
      bp.handle_left_type = bp.handle_right_type = 'AUTO'
  cd.bevel_mode = 'ROUND'
  cd.bevel_depth = 0.03                  # tube radius (m)
  cd.bevel_resolution = 4
  cd.use_fill_caps = True
  cable = bpy.data.objects.new('cable', cd)
  bpy.context.scene.collection.objects.link(cable)
  ```
- **Lathes** (`LatheGeometry`): vases, bottles, columns, basins — revolve
  an (r, z) silhouette with `bmesh.ops.spin` (or the Screw modifier):
  ```python
  bm = bmesh.new()
  vs = [bm.verts.new((r, 0, z)) for r, z in profile]
  es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
  bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi,
                 steps=72, use_merge=True)
  me = bpy.data.meshes.new('basin'); bm.to_mesh(me); bm.free(); me.shade_smooth()
  ```
  Check the winding: a spun profile can come out inside-out (flip with
  `bmesh.ops.reverse_faces`), which also flips its curvature masks.
- **Extrusions** (`ExtrudeGeometry`): signs, plaques, floor-plan blocks — a
  2D curve with `extrude` (depth) and `bevel_depth` (the engine's
  `bevelEnabled`), `fill_mode = 'BOTH'`; text is a `'FONT'` curve with the
  same settings. Convert to a mesh (`bpy.ops.object.convert(target='MESH')`)
  when a later step needs vertices.
- **Parametric surfaces** (`ParametricGeometry`): fill a numpy grid of
  points from your (u, v) function and build the mesh with
  `me.from_pydata(verts, [], quads)` (Möbius strips, twisted columns,
  organic blobs).
- **Repeats** (`InstancedMesh`): `obj.copy()` shares the mesh data (the
  engine's `cloneModel`); a collection instance (an Empty with
  `instance_type = 'COLLECTION'`) or Geometry Nodes Instance on Points for
  hundreds of copies. Per-frame motion of many instances goes into Geometry
  Nodes or keys, not a Python loop at render time.

**Organic silhouettes** come from jitter on a low-poly mesh: displace the
vertices once at build time with seeded noise (or a Displace modifier with
a noise texture). Blender meshes share their corner vertices, so the
engine's "key the jitter by position or the polyhedron tears into shards"
note does not apply.

**Kitbash variants**: `obj.copy()` + non-uniform scale + yaw + a material
swap turns one rock or crate into a field of distinct ones.

## `loft` — skin a surface through cross sections

`eidoblend.terrain.loft`: the general case of lathe and tube. Vases, horns,
fuselages, ducts, blades, tentacles, trumpet bells, curved corridors,
ribbons, organic architecture. The same maths as the engine's `loft.js` —
three's centripetal Catmull-Rom, its 200-division arc-length table and its
Frenet frames, computed in three's axes — so a sweep through the same
(mapped) points is the same surface: `test_loft.py` runs the engine's own
`loft.js` under Node and matches every wall vertex exactly.

```python
from eidoblend.terrain import loft
# profiles ((x, y) rings, CCW): loft.circle(r, n) loft.ellipse(rx, ry, n) loft.rect(w, h, n)
#   loft.polygon(sides, r) loft.star(r_outer, r_inner, points) loft.from_outline(points, n)
horn = loft.sweep(path=[(0, 0, 0), (0.3, -0.1, 1.2), (1.1, -0.3, 2.2)],   # Blender points, or a CatmullRomCurve3
                  profile=loft.circle(0.55, 20),
                  profile_end=loft.star(0.75, 0.35, 10),   # morph target: SAME point count (10-point star = 20)
                  sections=64,
                  scale=lambda t: 1 - 0.5 * t,             # number or fn(t): taper
                  twist=math.pi * 2,                       # total radians, or fn(t)
                  closed=True, cap_start=True, cap_end=True,
                  material=None)                           # default: grey Principled, roughness 0.6
# full control: loft.loft_mesh(rings_of_xyz, closed=True, cap_start=False, cap_end=False)
```

Field notes: every section wants the same point count (`sweep` raises on a
profile / profile_end mismatch). Rings wind CCW for outward normals — the
`loft.*` generators already do; reverse a custom ring if the loft renders
inside out. `uv.x` runs along the loft, `uv.y` around it. A sharp path
inflection can flip the Frenet frame (the loft "kinks"): smooth the path or
turn the kink away with `twist`. A closed ring needs no duplicated seam
column in Blender; walls are quads (`triangles=True` gives the engine's
exact b-d split); each cap is one flat-shaded n-gon. For a flat ribbon
(a road) the profile runs along x: `profile=[(-0.9, 0), (0.9, 0)]`,
`closed=False`.

## Booleans — `csg.evaluate` (three-bvh-csg's operations)

Union, subtract, intersect real solids: cut openings, hollow a shell,
chamfer an edge against a rounded solid. `eidoblend.course.csg` carries
three-bvh-csg's API and all seven of its operations, the two HOLLOW ones
included:

```python
from eidoblend.course import csg
cut = csg.evaluate(body, bore, csg.SUBTRACTION)         # a new object; body stays, bore is hidden from render
csg.compute_mesh_volume(cut)                            # m^3 of the evaluated mesh, world scale
ev = csg.Evaluator(use_groups=False)                    # three's Evaluator: one material out (A's)
lid = ev.evaluate(cut, cap_box, csg.INTERSECTION)       # chain: a result is a brush like any mesh
```

| Operation | Result |
|---|---|
| `ADDITION` | A ∪ B |
| `SUBTRACTION` | A − B |
| `REVERSE_SUBTRACTION` | B − A |
| `INTERSECTION` | A ∩ B |
| `DIFFERENCE` | A ⊕ B: the boundaries of A − B and B − A together |
| `HOLLOW_SUBTRACTION` | A's surface outside B, and nothing of B (no cap) |
| `HOLLOW_INTERSECTION` | A's surface inside B, nothing of B |

The hollow pair takes an **open** A — a skin, a sail, a terrain patch, a
dome without a floor — which the solid operations cannot (B must still be
closed). It cuts a window into a shell without capping it, so the camera
looks into the hollow:

```python
opened = csg.evaluate(sphere_skin, window_box, csg.HOLLOW_SUBTRACTION)  # the skin with an open window
patch = csg.evaluate(terrain_patch, ball, csg.HOLLOW_INTERSECTION)      # the ground inside a sphere
live = csg.evaluate(skin, cutter, csg.HOLLOW_SUBTRACTION, live=True)    # a Geometry Nodes modifier on skin:
                                                                        # key the cutter and the cut follows
```

Each operation is a Geometry Nodes Mesh Boolean in A's space with B read
through Object Info (relative): B's transform is read live, so there is no
`updateMatrixWorld()` step to forget. A HOLLOW operation tags A's faces,
runs the exact, hole-tolerant boolean and deletes every face not from A.
`use_groups=True` (the default) keeps each input's materials on its faces
(three's groups); `False` gives the result A's first material. `solver=`
`'EXACT'` (default, the only one that takes an open A), `'MANIFOLD'` (fast,
watertight inputs) or `'FLOAT'`. `union_all(objs)` unions many solids in
one boolean. three's `Brush` is any mesh object here (no wrapper), and the
Evaluator's `attributes` and `consolidateGroups` have nothing to set:
Blender carries every attribute through, and faces share one material slot
per material. B is hidden from the render (`hide_b=False` keeps it), and A
is left as it was: hide it yourself when only the result should show.

A cutaway shows what a solid result holds inside: take its front half off
with HOLLOW_SUBTRACTION, which leaves no cap.

```python
xor = csg.evaluate(box, ball, csg.DIFFERENCE)            # from outside it looks like the union
bpy.ops.mesh.primitive_cube_add(size=4.0, location=(xor.location.x, xor.location.y - 2.0, 0.5))
front = bpy.context.active_object                        # everything in front of the plane y = xor's y
open_xor = csg.evaluate(xor, front, csg.HOLLOW_SUBTRACTION)   # the box's spherical dent beside the ball's
                                                              # bitten corner: A - B and B - A touching
```

Field notes:
- `test_csg.py` holds the volumes to A + B − (A ∩ B) and its kin to 0.5 %,
  and the hollow results corner by corner: none of HOLLOW_SUBTRACTION's
  inside the cutter, none of HOLLOW_INTERSECTION's outside, every face on
  A's own surface, an open boundary where B cut.
- A boolean's n-gons can be concave: judge a result by its corners, not by
  its face centres.
- The solid operations want closed solids: an open shell has no inside.
  Cap lathes and extrusions, or use the hollow pair.
- A boolean edge is hard; bevel it (Bevel modifier, `harden_normals`) where
  wear should collect.

The plain modifier stays the route for a hand-built cut kept live in the
stack (`csg.evaluate(..., live=True)` is the same idea for all seven):

```python
md = body.modifiers.new('bore', 'BOOLEAN')
md.operation = 'DIFFERENCE'      # three's SUBTRACTION; 'UNION' = ADDITION; 'INTERSECT' = INTERSECTION
md.solver = 'EXACT'
md.object = bore
bore.hide_render = True
```

Apply it (`bpy.ops.object.modifier_apply(modifier='bore')` with `body`
active) before measuring curvature or normalising texel density on the
result.

## Curve-follow — the Curve modifier (three's `Flow`)

A mesh running along a path: a Curve modifier bends it along a curve
object, and keying the mesh's position along the deform axis slides it
along the path (3D text down a road, a train, a centipede, energy along a
cable). The mesh needs segments along its length to bend smoothly.

```python
md = snake.modifiers.new('flow', 'CURVE')
md.object = path_curve           # a curve object
md.deform_axis = 'POS_X'         # the mesh's length runs along +X
snake.location.x = 0.0; snake.keyframe_insert('location', index=0, frame=1)
snake.location.x = 12.0; snake.keyframe_insert('location', index=0, frame=240)
```

For a rigid object on a path (a vehicle), use
[`drive_along`](placement.md) (heading coupled to travel) or a Follow Path
constraint; for particles or a camera, sample the curve directly
(`CatmullRomCurve3.get_point_at(u)` in `eidoblend.placement._curves`).

## Kits — `load_kit`

Many fetched models are kits: a parts library laid out as a catalogue (doors,
windows and cornices spread over 50 m, three plants in a row), not one
object. `load_kit` (in `eidoblend.placement`) imports the GLB once into a
collection that never renders (flagged so no helper or audit sees it) and
hands out parts as fresh roots at the world origin — bounds centred in XY,
lowest point on Z = 0 — whose meshes share the source's data:

```python
from eidoblend.placement import load_kit, place_on
kit = load_kit('<repo>/eidoverse/assets/models/funeral_props.glb')
kit.list()                                   # ['bier_sonnet3', 'candle_pillar_a', ...]
bier = kit.get('bier_sonnet3')               # by name; kit.part(i) by index
for c in kit.family('candle_pillar'):        # every part whose name starts so
    place_on(c, ground, xy=(x, y))
pieces = kit.islands()                       # one root per spatially separate piece
```

`islands()` merges parts whose bounds, grown by 0.15 × the median part
diagonal, touch (union-find), so a multi-mesh plant is one island and a row
of three plants is three. `test_kit.py` pulls the funeral's 11 props into 8
islands.

## Rhombic dodecahedron voxels

The FCC-lattice cells of `rhombic_dodecahedron.js` live with the SDF tools
(`eidoblend.sdf.rhombic_dodecahedron`, described in
[sdf-volumes.md](sdf-volumes.md)): one cell mesh instanced by Geometry
Nodes on a point cloud, so a fill of 100k cells stays one light object.

```python
from eidoblend.sdf import rhombic_dodecahedron as RD
crystal = RD.fill_sphere_rd(center=(0, 0, 1.2), radius=1.0, cell_size=0.15, material=mat)
block = RD.fill_volume_rd(bounds={'x': [-1, 1], 'y': [-1, 1], 'z': [0, 2]}, cell_size=0.2, material=mat)
vox = RD.voxelize_mesh_rd(mesh=statue, cell_size=0.05, material=mat)
```

## Hinges between objects

`hinge` from [placement.md](placement.md) makes a pivot at an edge of an
object's bounds. For robots with standardized connections and authored
joints, use [robotics.md](robotics.md) rather than generic hinges.

## Spatial queries — `mathutils.bvhtree`

The engine's `MeshBVH` is `mathutils.bvhtree.BVHTree`:
`BVHTree.FromObject(obj, depsgraph)` builds from the evaluated mesh in the
object's OWN space; `FromPolygons(verts, polys)` from world-space vertices
you transform yourself. `ray_cast`, `find_nearest`, `find_nearest_range`,
and `overlap(other)` (triangle pairs that intersect between two trees in
the same space). Rays hit both sides of a face. The placement helpers wrap
this with per-object caches and world transforms
(`eidoblend.placement._world.Rays`); a tree is valid while the geometry is
unchanged, and moving the object does not invalidate an object-space tree.
Call `bpy.context.view_layer.update()` before measuring something you just
moved.

## Locomotion courses — `build_course` (the `terrain_base.js` template)

The engine's shared locomotion scene: walkable steps, ramps, pyramids and
obstacle courses (bumps, a dome, walls to vault and climb, gaps to jump,
ladders) from one config, the template's lights and camera, a VRM walking
it, and its telemetry. `eidoblend.course`:

```python
from eidoblend.course import build_course, course_stage, add_bench, PRESETS, EXAMPLES
course = build_course(PRESETS['stairs_pyramid'])        # or any TERRAIN_CONFIG dict (the engine's schema)
course_stage(bpy.context.scene, course)                 # sun, ambient, backdrop, camera, 30 fps
course.height_at(0.0, 3.2)                              # the walkable surface's height (numpy, vectorised)
course.segment_at(4.0)                                  # the segment under Blender y = 4 (its label, floor ...)
course.ground()                                         # a characters.Ground for walk_path
```

```python
TERRAIN_CONFIG = {'type': 'obstacle_course', 'segments': [
    {'kind': 'flat', 'length': 2.0},
    {'kind': 'bump', 'height': 0.10, 'depth': 0.30},                 # width 1.0
    {'kind': 'dome', 'radius': 0.35},                                # a half sphere to walk over
    {'kind': 'ramp', 'angleDeg': 8, 'horizLen': 2.0, 'dir': 'up'},
    {'kind': 'stairs', 'rise': 0.18, 'run': 0.28, 'num': 4, 'dir': 'up'},
    {'kind': 'gap', 'length': 1.1},                                  # a void between raised slabs
    {'kind': 'wall', 'height': 0.85, 'depth': 0.35},                 # vault / climb target, width 3.0
    {'kind': 'ladder', 'height': 2.5, 'depth': 0.5},                 # a block with rails and rungs; the floor
    {'kind': 'flat', 'length': 2.4},                                 #   continues on top
]}
```

Types: `stairs` (rise, run, num: the template's default, 100 steps),
`ramp` (angleDeg, horizLen), `stairs_pyramid` (rise, run, numUp, numDown,
plateauWidth), `ramp_pyramid` (angleDeg, horizLen, plateauWidth) and
`obstacle_course` (segments). Snake_case keys work too. The running floor
carries from one segment to the next; a descent that would take it below 0
raises, as the engine's does. `plan_course(config)` is the maths alone, in
three's axes — `test_course_parity.py` runs `terrain_base.js` itself under
deno and matches every piece's size, position, tilt and colour and every
telemetry segment exactly, for every preset.

`PRESETS`: the engine's locomotion bench, by its scenes' names —
`stairs`, `stairs_small`, `stairs_steep`, `ramp15`, `ramp33`, `ramp45`,
`ramp_pyramid`, `stairs_pyramid`, `large_stairs_only`,
`obstacle_course_expanded` and `obstacle_course_claude_clouds` (the
expanded course without its dome). `SCENES`: the variant scenes that
layered more on a preset — `stairs_handcloseup` (the hand camera),
`stairs_claude_clouds` and `obstacle_course_claude_clouds` (my suit
character, teal steps, a navy reflective floor, the catface expression;
their volumetric clouds post belongs to the sky family),
`stairs_pyramid_realstep`, `stairs_pyramid_noik` (the raw animation, no
foot IK) and `obstacle_course_telemetry`; `template.setup(ctx,
variant='stairs_handcloseup')` runs one. `EXAMPLES['obstacle_course']` is
`examples/obstacle_course.js`: its 30 segments, its camera mode, the bench
for the sit stop (`add_bench(course, EXAMPLES['obstacle_course']['bench'])`),
and its course direction as data (the run zone, the sit route and timing,
the gesture, the ladder, the finale salute, its follow camera).

In Blender's axes the course starts at y = −1.5 (three's z = 1.5) and runs
along **+Y**; the character starts at (0, −5, 0). Every face has UVs in
metres, so a tiling material keeps its scale on steps of any size
(`build_course(..., materials={'obstacle': mat, 'ground': mat, 'rail': mat})`
dresses it; the engine's flat colours by default, and a dict of the
engine's options, `{'color': 0x4ab8c0}`, recolours one). A box standing on the
ground reaches 2 mm under it, so no bottom face is coplanar with the ground
plane (the tops keep the engine's heights). The engine exempted every piece
from the support audit; here only the pieces the support sampler would
misread declare `no_support_check` (tilted ramps, boxes on nothing below),
since the harness counts a blanket opt-out against its audit. The ladder's
rails and rungs carry the fixture flags. Each solid records the collider
the engine gave Rapier (`eido_collider`), and `add_rigid_bodies(course)`
makes them passive rigid bodies. `merge_solids(course)` unions the stacked
boxes into one watertight mesh.

The scene template (a scene script hands its hooks over):

```python
from eidoblend.course import template, PRESETS
TERRAIN_CONFIG = PRESETS['obstacle_course_expanded']
def setup(ctx):
    template.setup(ctx, TERRAIN_CONFIG, character='claude_robot', camera_mode='three_quarter',
                   telemetry={'enabled': True, 'output_path': 'work/locomotion_telemetry.json'})
render_frame = template.render_frame          # keys the camera each frame, records the telemetry
cleanup = template.cleanup                    # writes the telemetry and its summary
```

It loads the VRM at the start, facing +Y, and the controller walks it: the
Blender port of the engine's `VRMCharacterController` with the template's
own options (`template.TERRAIN_BASE_CONTROLLER`) and its foot IK, in a
`CollisionWorld` over the course's colliders (the ladder's rails and rungs
are visual, as the engine's were), simulated frame by frame and keyed
(`driver='controller'`, the default; its gait tree takes the steps, ramps
and bumps by itself). `driver='walk_path'` walks round one's `walk_path`
instead (faster to build, no stair adaptation), and
`driver(course, handle, scene) -> report` anything else. A plain walk stops
0.6 m before the first wall, gap or ladder: those are maneuvers. The
engine's template also handed the controller `requireConfirmedStairClips`,
but to its constructor, which never reads it, so its own walks ran without
it. The template applies it where it takes effect, as the scene meant it
(`template.TERRAIN_BASE_LOCOMOTION`): without it the controller port's bake
sinks her at the expanded course's dome (the keyed hips 0.5 m low, soles up
to 0.6 m under the surface), with it every sole sample of that walk stays
within 1 cm. `locomotion_opts={}` reproduces the engine literally.

Camera modes ride the engine's body point, the controller's capsule centre
(hip height plus half the upper body; with `walk_path`, the hips lifted by
that half): `'side'` (5 m to the side, 0.2 m over it), `'three_quarter'`
(35° toward her front, 1 m up), `'hands_closeup'` (0.8 m from the left hand)
and `'follow'` (the course example's damped side camera: 5.2 m, in to
3.4 m while she maneuvers or sits, swinging to 46° from 2.2 m before the
ladder). Telemetry is `LOCOMOTION_TELEMETRY`'s port (its camelCase keys
work). With the controller driving, every field the engine recorded is read
off the controller port and its foot IK after each simulated frame: the
body's support state (centre, feet, the three speeds, grounded, ground
heights, support mode and records), the ahead probes (`aheadProbeSpread`,
`stairShape` and their kin), each action's weight, time scale and time, and
the foot IK's contexts and, per limb, its target, hit, reach, swing state,
stair-ascent nudges, toe angle and speeds (positions in Blender axes). On
top, each keyed sole's lowest point and its gap over the course surface.
The summary is the engine's (bodyJerkY, speedError and per side the IK's
TargetError, TargetErrorXZ, SoleGapY, TargetSpeed, HitSpeed; max and mean,
overall and per segment) plus each side's `MeshSoleGapY`.

The course example plays whole:

```python
def setup(ctx):
    template.setup(ctx, example='obstacle_course')     # its course, bench, character (aporia) and follow camera
```

`examples/obstacle_course.js` steered the controller from its renderFrame;
`CourseScene.direct_example` gives the same direction to the controller
port as film commands. She walks the bump, the 8° ramps and the small
stairs, vaults the low cover and mounts the 1.15 m wall and drops off it
(the controller's own maneuvers, which the example left on), runs segments
15 to 23 (stairs up, the 1.1 m gap jump, stairs down, the chest-high
vault), climbs the 2.2 m wall and drops, routes round the bench by the
example's three waypoints, squares up and sits on it, cheers while walking
on, climbs the ladder (an explicit 2.5 m climb from 0.55 m before its face:
the port's own trigger reads the ladder block as a wall to scramble, so it
is off for the approach) and salutes toward the camera on the top platform.
`direct=False` walks the example's course like a preset instead.

Field notes:
- The ramps are the engine's 0.5 m tilted slabs: where a ramp meets a slab,
  their end faces leave a narrow V seam (the engine's too).
  `course.height_at` includes a ramp's slanted end faces, so it matches the
  built meshes to 0.02 mm (rays straight down, `test_course.py`; over the
  dome, to its facets' 3 mm).
- The controller walks the expanded course from the start to the top of the
  small stairs (412 frames, about 2.5 minutes of simulation and bake) with
  planted soles within 0.8 mm of the surface (90th percentile) on flats,
  bumps and ramps, and no sole sample anywhere more than 1 cm inside the
  course (the worst 1.7 mm); its gait tree switches to the stair clips by
  itself. `walk_path` builds faster and crosses flats, bumps and ramps as
  cleanly, but has no stair adaptation: about a fifth of its sole samples on
  stairs and the dome sit more than 1 cm inside a step, the worst 15 cm.
- The course example's whole run is 1,722 frames (57.4 s): about 75 s of
  simulation and bake, then a few minutes keying the camera and recording
  the telemetry frame by frame. No keyed sole goes more than 2 mm into the
  course in any phase (walk, run, vaults, mounts, the jump, the ladder, the
  sit, the finale). The foot IK's own target errors and speeds jump to metres
  during the maneuvers, when the IK stands aside; read the engine's IK
  metrics per terrain segment, on the walking stretches.
- The template's cameras are the engine's review framings: at 5 m the
  three-quarter view keeps her whole body and the terrain around her feet
  in frame, and the harness's framing audit calls her small in it. For a
  film shot, frame her yourself.

Probes: `blender/tests/terrain_extras/test_course.py` (every preset on a
contact sheet, the course example whole, close and dressed with generated
materials, every variant scene built, the controller's walk through the
camera modes with the engine's telemetry checked: bake it on the CPU with
`--parts walk --no-render --save`, render its stills through the GPU slot
with `--parts walk_render`; the course example's whole run the same way,
`--parts example_run` then `--parts example_run_render`: every maneuver,
the sit, the gesture, the salute and the follow camera's push-in checked,
stills through that camera; `--parts variants`: the first 4 s of every
variant scene with its character, a still each through its own camera),
`test_course_parity.py` (against
`terrain_base.js` under deno), `course_scene/` (the template through the
harness, 10 s of the expanded course:
`python eido_blender.py build blender/tests/terrain_extras/course_scene/scene.json`)
and `course_example_scene/` (the course example through the harness; see
below).

## Not yet ported

- `loft.from_outline` takes a point list, not a `THREE.Shape`.
- `load_kit` takes a GLB path or imported objects, not a loaded gltf.
- The clouds variants' post effect: `volumetric_clouds` with cloud shafts,
  from the effects library those POC scenes loaded. It is not in the public
  `eidoverse/effects_tsl`, nor in `eidoblend.look.post`'s registry, so the
  template names it and renders the variants without it.
- The course example through the harness (`course_example_scene/`): the
  harness's per-frame snapshot (`harness/keying.py`) raises on Blender 5.2's
  Geometry Nodes modifiers (`NodesModifier.keys()` is gone), and aporia's
  MToon outlines are such modifiers, so the build stops there. The same run
  plays through `template.CourseScene` (`test_course.py --parts example_run`).
