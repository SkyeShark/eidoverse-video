# Placement — intent-based helpers + the audits

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the Blender 5.2 EEVEE edition (`blender/eidoblend/placement/`). A
model's location is its origin — sometimes a corner, sometimes the front
face, sometimes an arbitrary studio pivot — so eyeballed raw coordinates
give you chairs embedded in tables. The placement helpers account for both
objects' real bounds and ray-cast the geometry where it matters. Set the
rotation first — the helpers read the rotated bounds — and read the model's
`_preview.jpg` for its forward and up axes before deciding that rotation.

```python
import sys; sys.path.insert(0, '<repo>/blender')
from eidoblend.placement import place_on, snap_to_ground, scatter_on, place_against, run_placement_audits
```

**Axes and sides.** Blender is Z up, metres. The sides keep the engine's
names, mapped through three (x, y, z) → Blender (x, −z, y): **front = −Y**
(three's +Z, also the glTF importer's front), **behind = +Y**, left = −X,
right = +X, above = +Z, below = −Z. Engine flags in `userData` are object
custom properties here, snake_cased: `obj['no_support_check'] = True`.

**Geometry is evaluated, in world space.** Every query reads the evaluated
mesh (modifiers, Geometry Nodes, shape keys at the current frame), so a
Displace or Subdivision modifier is seen exactly as it renders; only shader
displacement is invisible to the helpers. Rays go through a per-object BVH
built once in the object's own space and cached, so moving an object never
rebuilds it; after editing a mesh's vertices in place call `clear_cache()`.
BVH rays hit both sides of a face (no back-face culling).

## The helpers

- **`place_on(obj, target, xy='auto', z_offset=0, xy_offset=None, grid=7,
  surface_eps=0.0006, sink=None, seed=1)`** seats the object's bounds
  bottom on the highest sampled support under its footprint. `xy='auto'`
  (the default) keeps an already non-zero location (anchored at the bounds
  centre), otherwise centres on the target; `(x, y)` is an explicit
  world-space bounds-centre anchor, `'centered'` recentres, `'random'` picks
  a spot seeded by `seed` (the engine used an unseeded random).
  `xy_offset=(dx, dy)` adds a relative offset; `z_offset` adjusts the
  height. The target may be an object, a list, a collection, or a group
  that contains obj — obj's own subtree is never its own support. `grid`
  sets the footprint sampling; `surface_eps` (0.6 mm) lifts the object a
  hair off the support so a flat base never lands coplanar with the floor —
  pass `0` for exact contact. `sink` buries that fraction of the object's
  height (clamped 0–0.9; 0.15–0.35 suits rocks) and sets
  `obj['_sunk_placement']`, which the hovering audit respects. It records
  what obj sits on (`obj['_support_targets']`). Inspect the result on
  sloped or concave surfaces; a sampled highest support is not proof that
  every part of an object rests flush.

- **`place_against(obj, ref, side, gap=0.3)`** — clearance-aware side
  placement: `'front' | 'behind' | 'left' | 'right' | 'above' | 'below'`,
  with `gap` metres between the two bounds. "Chair behind desk", "lamp
  left of monitor". Bounds based: offset origins are handled, a concave
  leading face can leave a visible gap.
- **`place_touching(obj, target, side, dir=None, gap=0, grid=8,
  allow_intersect=False)`** — the mesh-accurate sibling: fans rays over the
  inner 80 % of obj's leading bounds face along the travel direction and
  slides obj until it meets the target's real geometry (or stops `gap`
  short; negative bites in). `side` is the direction obj travels, or an
  explicit `dir=(x, y, z)`. The tool for assembling pieces flush. Returns
  `True` on contact, `False` (obj unmoved) when nothing lies that way.
- **`snap_to_ground(obj, ground, z_offset=0, below=False, grid=None,
  surface_eps=0.0006)`** — drops obj onto whatever lies under its origin's
  **world** XY (so it works under a parent). `grid` defaults to 5, or 9 with
  `below=True`, which casts from obj's current bottom instead of the sky so
  it lands on the nearest surface beneath (an interior shelf board). The
  ground may include a group containing obj; obj's own subtree is excluded.
  Partial burial helps a rock or fallen trunk look settled: a negative
  `z_offset` sized to the asset, not one depth for every prop.
- **`align_to_surface(obj, target, keep_yaw=True)`** — turns obj's +Z to the
  surface normal under it: signs on slanted roofs, props on slopes. It keeps
  obj's heading (the engine's version replaced the whole rotation:
  `keep_yaw=False`).
- **`scatter_on(items, target, count=None, min_spacing=0.1, rng_seed=1,
  sink=0, tilt_max=0)`** — spread items over the target's top footprint in
  an organic layout, deterministic per `rng_seed` (the engine's LCG and its
  sample order through the axis map: a seed lays out as it did in WebGPU).
  Rocks, ruins and stumps read planted when partly buried:
  `sink=(0.15, 0.35)` + `tilt_max=0.3`.
- **`find_clear_spot(obj, around, radius=2.0, samples=16, scene=None,
  exclude=None, z=None)`** — spiral search for a spot where obj's bounds
  overlap nothing; returns a world `Vector` for its bottom centre, or None.
  Seat the object there with `place_on(obj, ground, xy=(spot.x, spot.y))`.
  The ground is not an obstacle: terrain (`trimesh_collider`) and anything
  whose top is at or below the spot's bottom (a floor) are skipped. The
  engine's `findClearSpot` counted the terrain's whole box and found nothing
  on hilly ground.
- **`face_toward(obj, target, forward='-y')`** — yaw-only aim at an object
  or a point `(x, y)` / `(x, y, z)`. `forward` is the local axis the
  model's nose points along: `'-y'` (the default: glTF imports face −Y),
  `'+y'`, `'+x'`, `'-x'`. Guessed rotation constants are where statues face
  the wall.
- **`drive_along(obj, waypoints, duration=10, forward=None, start_time=0,
  loop=False)`** — the way to move a vehicle / creature / anything
  elongated: it keys location and Z rotation on every frame (LINEAR) along
  the engine's centripetal Catmull-Rom path, heading coupled to travel, so
  it cannot slide sideways; it also returns `drive(t)` to pose it at t
  seconds. `forward` has no default because there is no universal nose
  axis — read the preview; for vehicles you build, nose along −Y and
  `forward='-y'`. It warns when the declared forward is perpendicular to
  the model's long axis and when the mesh sits far from its origin (the
  body would orbit the path: parent it under an Empty at its centre and
  drive the Empty). Backwards it can't detect — only the preview shows that.
  ```python
  drive = drive_along(car, [(-8, 0), (0, -1.5), (6, 0)], duration=30,
                      forward='+x')       # from THIS car's preview; yours will differ
  ```
- **`station_beside(obj, machine, gap=0.2, side=None, face=True,
  forward='-y')`** — a worker or machine that operates on something stands
  beside it, facing it: clear of the working edge (the machine's short
  horizontal axis), base at its floor level, nose aimed at the line.

## Composition recipes

```python
# Desk on the floor, chair behind it, laptop on it, mug right of laptop.
place_on(desk, floor)                          # desk bottom on floor
place_against(chair, desk, 'behind', 0.25)     # 25 cm of clearance (+Y side)
place_on(laptop, desk, xy='centered')          # laptop centred on desk
place_against(mug, laptop, 'right', 0.08)      # mug 8 cm to the right
snap_to_ground(mug, [desk])                    # seat vertically, keep its XY

# Character standing on stairs (a VRM's root is its armature: character = me.arm).
character.location = (2, -1, 5)                # approximate spot
snap_to_ground(character, [stair1, stair2, landing])

# Eight boulders settled across a clearing, partly buried and leaning.
scatter_on(boulders, clearing, min_spacing=1.2, rng_seed=7, sink=(0.15, 0.35), tilt_max=0.3)

# A bench somewhere clear near the fountain, then seated on the ground there.
spot = find_clear_spot(bench, fountain.location, radius=3)
if spot:
    place_on(bench, terrain, xy=(spot.x, spot.y))
```

**Filling a shelf / cabinet (interior boards):** `place_on(item, shelf)`
lands on the unit's outer top. Position the item inside the footprint a
little above the board you want, then `snap_to_ground(item, shelf,
below=True)`; or `place_inside(item, shelf, aim_z=...)` with `aim_z`
between the board you want and the one above (it centres the item in the
footprint, matches the shelf's heading and does the snap). The engine read
the board heights off the preview; a cast reads them exactly:
`scene.ray_cast` straight down through the unit, again from just under each
hit, keeping the surfaces every cast meets (the `boards()` helper in
[the pipeline's renders](../blender/tests/pipeline2/test_renders.py), which
run these recipes as written: the desk, the rubble, the bench, a worn metal
rack filled with nine workshop props, claude.vrm dropped onto a landing).

## How placement goes wrong

- **Absolute coordinates with offset pivots:** `obj.location.x = x` places
  the origin at x, not the bounds centre. A relative move shifts origin and
  geometry together; use a helper anchor when you mean the visible centre.
- **Mixing raw coordinates and helpers for related props:** once a surface
  is helper-placed, everything on it places relative to it.
- **Skipping the preview:** a fetched model can face any axis and sit on any
  side; the preview tells you the rotation to set before placing.

## The audits (they run before a render)

`run_placement_audits(scene=None, auto_fix=None)` is the hook the render
harness calls once a scene is built: on **every** build and every hand-edited
reopen, whether or not the script imports this family, as the WebGPU runner
ran its checks after every `setup()` (a prop dumped in mid-air by a hand-set
location is exactly what they catch). All audits work on whole placed
objects — parentless, not cameras or lights, descending through a lone
wrapper — so a multi-part desk is checked as one thing. Warnings are
observations to look at in the probe frames. Bounding boxes, nested groups
and intentional overlaps can produce false positives or missed cases.

Collection instances count as what they show: an Empty instancing a
collection (a kit part from `assets.load_kit`, a collection instanced by
hand) is seated, ray-cast and audited through the real geometry of the
objects it instances, so `place_on(can, crate)` stacks one kit instance on
another and a floating instance is named like any object.

- **`check_clipping(scene)`** — pairs of placed objects whose bounds
  intersect: printed as data (resting contact is how things are built: a
  brace in its socket, a crate on a crate). A mesh-accurate pass then names
  any object substantially INSIDE another — at least 18 % of up to 36
  sampled points enclosed (5 of 6 axis rays hit the other) — loudly and
  never truncated. That pass moves nothing; the fix is a clear spot
  (`find_clear_spot`) or a proper seat. Intentional overlap (a stake in the
  ground) declares `obj['allow_intersect'] = True`; parts of one machine
  share `obj['assembly'] = '<machine>'`. Pairs seated one on the other
  (`_support_targets`) and seated characters (`obj['eido_seated']`) are
  skipped.
- **`check_hovering(scene)`** — for every placed object, footprint rays
  under its base: **near** (a 0.005–1.0 m gap, measured and printed as
  small), **far** (> 1 m above the nearest surface) and **void** (nothing
  beneath) are the floaters that escalate to `[placement] ⚠`. Unflagged:
  objects at ground level, objects verified on their recorded support,
  `make_terrain` ground (`trimesh_collider`), sunk placements, all-BLENDED
  (glow) objects, seated characters, and declared flyers:
  `obj['no_support_check'] = True` — drones, balloons, a character
  mid-jump. Active rigid bodies are left to the simulation (a crate dropped
  onto a pile starts in the air and settles where physics puts it; judge it
  in motion). Ground level ignores sunk objects (a rock buried in the lowest
  hollow would otherwise lift "ground" under the terrain).

  *Verified on its recorded support* means the support's real surface is
  under the object, within 6 cm of its base (`SEATED_GAP`): an 11 x 11 ray
  grid over its footprint first, then, for thin supports the rays slip
  between (a wire rack, slats), every load-bearing triangle of the support
  (one facing up or down within 60 degrees of level, either winding) clipped
  to the footprint. The engine fell back to the support's bounding box
  instead, which counted a clock as still on a stool that had been moved
  0.3 m: the stool's splayed legs kept its box under the clock while the
  seat was gone. That clock is now named, 0.43 m in the air. Steep and
  vertical faces never count: a book lifted 0.25 m off a rack's board beside
  its post, or a cushion lifted 0.3 m off a seat against the backrest, is
  named, though the post and the backrest rise past its base inside its
  footprint.
- **`check_z_fighting(scene)`** — a thin object (under 6 cm on an axis: a
  panel, decal, quad) with a face within 2 mm of another object's face and
  overlapping it on the other two axes. EEVEE z-fights too: offset flat
  things a few mm proud or sink them a little. Opt out:
  `obj['no_z_fight_check'] = True`.
- `check_facing(scene)`, `check_density(scene)` and
  `check_line_intrusion(scene)` as below.

**The audits are warn-only by default.** A scene with
`scene['eido_auto_fix_placement'] = True` (or `auto_fix=True`) gets a repair
pass first — clipping, hovering and z-fighting once with `auto_fix`, then
the warn-only audits judge the repaired scene.
`scene['eido_no_auto_placement_check'] = True` skips both. The runner reads
the engine's names for the same two switches as well: `_auto_fix_placement =
True` / `_no_auto_placement_check = True` at module level in the scene script
(or as scene properties); the digest records either as a declared policy. Repair is a
safety net, not a placement method: it pushes apart only substantial
overlaps (never ground-scale geometry, never two seated objects), snaps only
`near` gaps, and nudges z-fighting panels 4 mm.

`test_placement.py` plants four mistakes and checks the audits name them:
a crate hand-placed 1.5 m up (`far`), one 4 cm up (`near`), a decal flush on
a crate face (z-fighting), a box inside a crate (deep interpenetration);
and nothing the helpers placed is flagged. It also caught a real one of
its own: a lid hinged open the wrong way read as 100 % inside its crate.

## Hinged parts

`hinge(obj, edge='back')` returns an Empty at the midpoint of one edge of
obj's bounds and parents obj to it, keeping its placement; the pivot
carries obj's support record. Edges: `back` (+Y), `front` (−Y), `left`,
`right`, `top`, `bottom`.

```python
lid_pivot = hinge(lid, 'back')
lid_pivot.rotation_euler.x = math.radians(-35)     # a back hinge opens with a NEGATIVE X turn
```

A front hinge opens with a positive X turn; left/right door edges turn
about Z. The helper only sets the pivot, not a constrained axis: inspect
clearance through the full swing. It is a rigid pivot, not an IK solver or
a replacement for authored robotics joints.

## Surface mounts and interior placement

- `surface_point(obj, direction, exclude=())` casts inward from outside
  obj's bounds along a world direction; returns `{'point', 'normal',
  'distance'}` (world space) or None.
- `mount_on(part, mount, dir=None, standoff=0, face_axis=None, exclude=())`
  seats a part at that surface point, offset outward along the normal by
  its own depth plus `standoff`. `face_axis` is the part's local axis to
  turn into the mount (omit to keep its rotation). Returns
  `{'point', 'normal'}` or None.
- `place_inside(obj, container, aim_z=None, match_yaw=True, xy_offset=None)`
  — the shelf-board pattern, above.

```python
bearing = mount_on(rotor, housing, dir=(0, 0, 1), face_axis=(0, 0, -1), standoff=0.01)
if not bearing:
    print('rotor mount surface was not found')
```

## Seating characters

A character sits IN a chair, not on it: `place_on(vrm, chair)` stands her
feet on the backrest's top. The seating helpers work on the characters
family's VRMs ([characters](characters.md)) and key what they decide:

```python
from eidoblend.characters import load_vrm
from eidoblend.placement import seat_on, sit_on_ground, unseat, emote, face_camera
me = load_vrm('aletheia')
seat_on(me, chair)                                  # the chair sit clip, facing out of the chair, on its seat pan
you = load_vrm('aporia', location=(2.0, -1.0, 0.0))
seat_on(you, chair2, transition='stand_to_sit', t=1.0, then='sitting_normal_chair')   # lowers into it from 1 s
robot = load_vrm('claude_robot_2k')
sit_on_ground(robot, at=(1.0, -0.5), ground=[floor])   # the ground sit clip, the lowest underside on the floor
friend = load_vrm('claude', location=(-1.5, 0.5, 0.0))
emote(friend, 'cheer')                              # an expressive clip on a planted VRM, looping
face_camera(friend, offset=0.4)                     # a three-quarter turn toward the camera
```

- `find_seat_surface(chair)` finds the seat pan, not the box top: a 7 x 7
  grid of downward casts over the inner 80 % of the footprint, the hit
  heights binned by 3 cm, the fullest bin wins (a tie goes to the lower, so a
  flat-topped throne back loses to the seat). It returns the pan's height,
  centre and extent.
- `chair_facing(chair)` reads which way a chair opens from its own geometry:
  what stands more than 18 cm above the pan is the backrest, its weighted
  centroid lies toward the back, and a sitter faces away from it (None for a
  stool). Headings here are Blender's: radians about +Z, 0 facing −Y, a VRM's
  front as loaded; the engine's offsets keep their sign.
- `seat_on(h, chair, clip='sitting_normal_chair', face=None, sink=0.02)`
  plays the sit clip, puts her root at the pan's centre, turns her out of
  the chair (`face=`, else the chair's facing, else toward the camera), and
  rests her real underside (an up-ray through her seated mesh under the
  hips) on the pan, `sink` pressed in. With `transition='stand_to_sit'` she
  stands `hip_back` (0.46 m) in front of the seat, facing out, and the clip
  lowers her into it from `t`; her root is keyed on every frame of the
  descent: from 40 % in, a one-sided clamp lifts her whenever her underside
  would dip below the seat (it never pushes her down), and at the clip's end
  a settle puts her hips over the pan, biased toward the backrest, and her
  lowest underside on it. The last pose holds, as the engine's did, or
  `then=` crossfades into a seated loop after it (0.25 s). The loop carries
  its hips over its root, where the sit-down's own hip travel had carried
  them about 0.4 m back, so the root is keyed again where the crossfade ends,
  that pose settled on the pan the same way: measured on the corner chair,
  her hips stay 6 cm behind the pan's centre through the crossfade and the
  loop, her lowest underside on the pan (left on the sit-down's root, the
  loop sat her on the pan's front edge, 3 cm in the air).
- `sit_on_ground(h, at, clip='sitting_on_ground', ground=None)` uses a
  ground-sit clip (a chair clip on the floor dangles the legs through it)
  and rests her lowest underside (up-rays at the hips ± 0.35 m) 5 mm above
  the floor cast under `at`.
- `emote(h, slot)` plays an expressive clip looping on a planted VRM;
  `face_camera(h, camera=None, offset=0, frame=None)` turns her to the
  camera (`frame=` keys the turn, for a camera that moves between shots).
- A seated VRM carries `arm['eido_seated']` (the clipping and hovering
  audits leave her, and her body never sets the ground level) and
  `arm['eido_seat']`; `unseat(h)` clears both. The runner's
  `placement.seated_facing` record names a sitter turned more than 110°
  from her chair's facing (RE-RENDER REQUIRED: most often a rotation set
  after `seat_on`; pass `face=` instead), and one more than 55° off for a
  look. A VRM's armature rotates by quaternion, where `rotation_euler`
  does nothing: the helpers turn it through its own rotation mode.

## Additional observations

`check_density(scene, min=5)` counts top-level objects holding geometry: a
grouping observation, not a quality requirement.

`check_facing(scene, min_size=1.2, thin_frac=0.28, buried_at=0.3)` finds
thin, textured (an Image Texture in the material), free-standing panels,
reports the clearance on each side of their display axis and warns on
interpenetration or a buried face, with pivot-offset evidence. Characters
(armatures) are skipped. It does not know which side carries readable text.
`obj['no_facing_check']` records an intentional exemption.

`check_line_intrusion(scene)` flags a tall object planted through a
name-matched transport line (conveyor, belt, assembly line, treadmill,
escalator). `obj['no_intrusion_check']` declares an intentional intrusion.

## Not yet ported

- A walking body's seats, ground sits and emotes: `eidoblend.characters.emotes`
  ([maneuvers.md](maneuvers.md)); these verbs call `placement.seating` for a
  VRM nothing drives. After seating, the engine reset the VRM's spring bones;
  keyed or baked springs are the characters family's, so re-bake them after a
  seat if the scene uses them.
- `focusPoint` / `lookAtObject` are the look family's `focus_point` /
  `look_at_object` ([camera-lighting.md](camera-lighting.md)).
- Geometry Nodes instances (a scatter made in a node tree) are not expanded
  into the ray targets, as collection instances are: mark a scattered field
  `no_clipping_check` / `no_support_check`, or realise the instances you need
  to place on. The harness's coverage records count them as leaves.
- The settle's ray grid is world-axis (±0.20 x, ±0.22 y), exactly as the
  engine's: on a turned chair it can take in the shins below the pan's front
  edge (on a chair turned 140°, its lowest read lay 0.22 m low at one frame),
  though the settle itself landed right.
