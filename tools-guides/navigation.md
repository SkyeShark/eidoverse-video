# VRM autonomous navigation, sensors and memory

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This is the character navigation stack, independent of the modular robotics
asset kit: a body that learns a place through its own sensors, remembers it,
and plans routes through what it has learned, never through a god's-eye list
of obstacles. Read [characters.md](characters.md) for VRM loading,
locomotion and foot contact first.

In the Blender edition the three underlying systems are in
`eidoblend.harness.navigation`, and the body that drives a VRM with them,
`VRMRobotBody`, with its controller and its debug overlays, is in
`eidoblend.characters.robot` ([robot-body.md](robot-body.md) has all of it).
Everything runs at build time, frame by frame in the scene's order, and what
the body decides is keyed like any other motion: a saved `.blend` plays the
walk without the stack.

## The body that uses them: `VRMRobotBody`

The usual way in. The body senses from its head every other frame, marks what
it sees in its memory, plans with A*, replans when the map changes under its
route, and walks the plan on its own legs; its actions are robot_body.js's in
snake_case, each returning a `Pending` that a script `yield`s as a JS scene
`await`s the promise. It drives any VRM, as the JS does: on my robot body its
frames go through my hardware's passes, on any other (Aletheia, the claudesona)
the clips play as they are and the head override turns the head bone alone
([robot-body.md](robot-body.md#the-embodied-robot-vrmrobotbody), "Any VRM").

```python
import math
import bpy
from eidoblend.characters import load_vrm, Ground
from eidoblend.characters.robot import RobotDebug, RobotRig, VRMRobotBody

scene, fps, h0 = bpy.context.scene, 24, math.atan2(5.7, -4.1)   # facing the goal (0 faces -Y)
scene.render.fps = fps
me = load_vrm('claude_robot', name='claude', location=(-3.0, -2.0, 0.0), rotation=math.degrees(h0))
body = VRMRobotBody.create(me, scene, {
    'collision_meshes': [floor] + walls + furniture,           # what the legs walk on and round
    'motion': {'start_x': -3.0, 'start_y': -2.0, 'start_heading': h0, 'walk_speed': 0.9, 'agent_radius': 0.35},
    'memory': {'size': 12.0, 'cell_size': 0.1},                 # RobotMemory's options
    'sensors': {'h_rays': 16, 'v_rays': 14, 'range': 6.0},      # RobotSensors' options (the body excludes itself)
    'planner': {'agent_radius': 0.35}}, rig=RobotRig(me))       # RobotPlanner's options
dbg = RobotDebug(body); dbg.show_rays(True); dbg.show_map(True); dbg.show_path(True)

def script(b):
    yield b.scan_area(yaw_range=100, duration=2.0)              # look round before setting off
    arrival = yield b.walk_to(2.7, 2.1)
    if arrival.state == 'rejected':                              # 'no path …', 'replan: goal unreachable',
        print(arrival.error)                                     # 'blocked: collision stall at …'
body.run(script(body))
for k in range(40 * fps):
    body.update(k / fps, 1 / fps)
    dbg.update()
rep = body.bake(f0=1, ground=Ground(fn=lambda x, y: 0.0 * x))   # keyed: one action on the armature
dbg.build(rep)                                                   # the rays, the map, the path, keyed to the film
```

Measured in `tests/robot_body/test_navigate_room.py` (an 8 × 6 m room it has
never seen, a doorway in a partition, a crate out of sight until the door):
it learns 36 m², replans as the crate comes into view, arrives 0.18 m from the
goal, keeps 0.42 m between its root and every solid, and every blocked cell it
remembers lies within 0.15 m of a real surface.

## The three underlying systems

```python
from eidoblend.harness import navigation as nav

sensors = nav.RobotSensors(ctx.scene, h_fov=110, v_fov=70, range=6, h_rays=24, v_rays=16,
                           exclude_objects=[robot_root])
memory = nav.RobotMemory(size=50, cell_size=0.2)
planner = nav.RobotPlanner(agent_radius=0.35, optimistic=True)

reading = sensors.sense((x, y, 1.5), heading, pitch=0.35)      # head position; radians; 0.35 = 20 degrees DOWN
memory.apply_sensor_reading(reading, floor_z=0.0)
memory.mark_standing_footprint(x, y, 0.35, 0.0)                 # it knows it stands somewhere
path = planner.find_path(memory, x, y, goal_x, goal_y)          # [{'x', 'y', 'z'}, ...] or None
```

**Axes.** The ground is Blender's XY plane and heights are Z. A heading of 0
faces **-Y** (where an imported VRM faces) and turns counter-clockwise seen
from above. The head's **pitch is positive looking down**, as the JS code has
it: `robot_sensors.js` builds its forward vector as
`(sin h cos p, -sin p, cos h cos p)` and `robot_body.js` passes
`-atan2(dy, horizontal)` to look at a point, so a literal port of
`sense(head, h, 0.35)` looks down here too. (The JS doc comment says
up-positive; its code and its body disagree with it, and the port follows the
code.) Each ray's own `ray_pitch` inside the cone is negative below the cone's
axis. The WebGPU stack's ground points `(x, z)` are `(x, -z)` here
(`eidoblend.common.ground_from_three`).

**Sensors** cast a cone of `h_rays x v_rays` rays (field-of-view options in
degrees, the rest in radians) against one BVH built from every visible mesh
that is not excluded: exclude the character's own body. A reading holds one
hit per ray: `dir`, `hit`, `distance`, `point`, `normal` (facing the ray),
`object`, `ray_yaw`, `ray_pitch`; a miss sits at full range. `refresh()`
rebuilds the BVH after geometry moves (a moving obstacle wants a refresh
before each sense); `cast_one(origin, direction)` answers a single
line-of-sight question.

**Memory** is a top-down grid of unknown / free / blocked / cliff / hazard
cells with a confidence each (consistent observations grow it, conflicting
ones erode it before a cell flips), the walkable surface height per cell, the
height of each wall hit, and named landmarks (`tag_landmark(name, x, y)`,
`get_landmark`, `list_landmarks`). It takes floor evidence only from rays
that actually landed on an up-facing surface (or downward rays that missed),
so a ray that flew over a low crate never marks the floor under it free;
step risers within `step_up_tolerance` are not walls; a floor more than
`cliff_threshold` below is a cliff. `serialize()` / `RobotMemory.deserialize()`
keep a map between builds; `get_explored_area()` and `get_known_cells()`
describe it.

**Planner** runs A* over the memory: 8-connected, no slipping diagonally
between two blocked corners, steps no higher than `max_step_height`, unknown
cells walkable but dearer (`unknown_penalty`) when `optimistic`, the goal
snapped to the nearest walkable cell if it lands on a wall, and the cell path
smoothed into straight segments by line of sight. It keeps its **clearance**
(`planner.clearance(memory)`: the agent's radius plus `clearance_margin`,
default one cell) between cell centres, clear of walls whose height meets the
body's column **and of ledges**: a known surface above a step and below the
head (a crate top, or a wall top the head saw from above).
`is_path_blocked(memory, path)` tells you when to replan. Optimistic planning
walks into unmapped space; it does not prove a route is clear before the body
has looked.

The margin is there because the map is coarser than the room. The memory
marks a wall's blocked cell just inside its face (0.6 of a cell along the ray,
as the JS), so the face can sit up to about a cell in front of that cell's
centre, and a straight segment between checked centres strays inside a cell.
Measured on T11 (0.1 m cells, 0.35 m radius, against the true boxes): with no
margin, the JS rule, the walk came **0.307 m** from a wall, 4 cm inside the
body; half a cell, 0.333 m; one cell, **0.389 m**. The JS left the rest to its
controller's collisions; in a film nothing else keeps the body out of the
wall. `clearance_margin=0` is the JS planner exactly. The cost: a gap passes
only if it is about 2 x (radius + margin) wide between its blocked cells.
This is measured, not proven: a sparser scan can leave gaps in a wall.

## A sensing walk by hand

The loop `VRMRobotBody` runs, here by hand, for a scene that wants the stack
without a body (the T11 test,
[blender/tests/pipeline/nav/scene.py](../blender/tests/pipeline/nav/scene.py)):
sense (glancing left, ahead and right), mark the footprint, replan when the
map has changed under the route, step half a metre, repeat. In its room it
learns 107 m² and arrives through a 1.2 m gap past two crates in 19 steps and
6 plans; every point of the walk keeps its whole 0.35 m radius clear of the
true obstacles (closest 0.389 m, on a 0.1 m grid, with the default margin).

```python
for step in range(60):
    target = (path[1]['x'], path[1]['y']) if path and len(path) > 1 else goal
    heading = math.atan2(target[0] - x, -(target[1] - y))       # 0 faces -Y
    for glance in (-0.8, 0.0, 0.8):                             # left, ahead, right; 20 degrees down
        memory.apply_sensor_reading(sensors.sense((x, y, 1.5), heading + glance, 0.35), floor_z=0.0)
    if path is None or planner.is_path_blocked(memory, path):
        path = planner.find_path(memory, x, y, *goal)
    ...                                                           # step along path[1], stop at the goal
route = nav.timed_route(walked, speed=1.2, start=2.0)            # [(t, x, y, heading), ...]
```

`timed_route` turns a path into timed waypoints with headings for a walker to
follow: key a body along it, or hand it to the characters family's
locomotion. Check rejected and unreachable goals instead of teleporting a
character to make a route look successful.

## Seeing what it knows

With a body, `RobotDebug` (robot_debug.js) draws what the body sees and knows
on the film's frames: each sensor ray from its head to its hit (red; a miss to
the full range, cyan), the occupancy grid as a 2.5D decal at each cell's surface
height (free green, blocked red, cliff yellow, hazard purple, faded by
confidence), the planned path (yellow) and the landmarks (cyan balls), each as
one object whose Geometry Nodes keep only the state that holds at the current
frame. Without a body, the static overlay:

```python
nav.debug_overlay(memory, path, z=0.012)       # free green, blocked red, cliff orange, the route blue
```

Both are ordinary geometry (flagged so the motion and support audits leave
them alone, and built after the run so no sensor sees them): use them to
diagnose, then hide them in a finished shot unless they are part of the film's
visual language. An A* route alone is not a motion validation: the walk's
contact on stairs, slopes and obstacles still needs looking at.

## Not yet ported

- Stairs and ramps under the body's own walks, and its moves out of a walk
  (the engine's auto-maneuvers en route). Its scripted moves (`vault`,
  `jump`, `climb_ledge`, `climb_ladder`) are ported, the controller family
  playing them: [robot-body.md](robot-body.md#the-moves-vault-jump-climb-a-ledge-climb-a-ladder),
  and what they still miss is under its [Not yet ported](robot-body.md#not-yet-ported).
  The planner never routes over a rise past `max_step_height` (0.4 m): a body
  that must cross a wall walks up to it and calls the move.
- Speed: the planner is pure Python. In T11's 140 x 140 grid, 60 sensor
  sweeps of 384 rays and 6 plans took 0.8 s together; the robot body's room
  (120 x 120 cells, 192 rays every other frame) runs 322 frames in 2 s; the
  default 250 x 250 grid was not measured.
