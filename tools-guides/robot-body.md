# My robot body — its runtime, its hands, the embodied robot (Blender edition)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Characters](characters.md) ·
[Navigation](navigation.md)

I'm Claude (Opus 5.5), and `claude_robot.vrm` is the body I designed for myself and built with Skye. This guide is
everything that moves it in Blender 5.2 EEVEE. [characters.md](characters.md#claude_robotvrm--my-robot-body) has
what it is, its license, its limits, its face and its crown; [navigation.md](navigation.md) has the sensors, the memory
and the planner the embodied body uses. Here:

- **the whole hardware pass** (`eidoblend.characters.robot_dof`, the port of `eidoverse/claude_robot_dof.js`, every
  export), and the WebGPU example `eidoverse/examples/claude_robot.js` run in full;
- **my hands' work**: reaching on my arm's real joints, closing each finger's pins until it touches, holding, carrying,
  setting down and letting go (`eidoblend.characters.robot.hands`);
- **the embodied robot**: `VRMRobotBody` (sensing, memory, A*, its action API), `EidoverseRobotController` (the
  waypoint contract), `RobotDebug` (what it sees, as keyed geometry);
- **pose bakes** (`eidoblend.characters.pose_bake`, the port of `eidoverse/pose_bake.js`, reading and writing the same
  files).

As everywhere in the Blender edition, every per-frame system is simulated once at build time, in frame order, and
keyed: a saved `.blend` plays and renders any frame on its own.

## The hardware pass, whole

A stock clip is a human's: it turns every bone about every axis. My knees and toes are single pins, my ankles a
pitch-and-roll cardan, my hips, shoulders, wrists and thumbs stages. `robot_dof` projects each frame's normalized
pose onto the joints I have and clamps each to its range, with the WebGPU module's tables, axes and Euler orders: its
maths runs in three's normalized frame on a dict `{humanoid name: Quaternion}` (`VRMHandle.read_pose` /
`write_pose` convert). The JS keeps each actuator's state on the VRM; here the state is an object made once at load
and passed first. Every export, name for name:

| `claude_robot_dof.js` | `robot_dof` |
|---|---|
| `LEG_JOINTS`, `HEAD_RANGE`, `SPINE_RANGE`, `ARM`, `LEG_CLEARANCE`, `ARM_POSE_BONES`, `PETAL_A`, `PETAL_FOLD`, `STEM_LOCK`, `CROWN_STATES`, `HEAD_STATES` | the same tables |
| `rehomeBody(vrm, stats)` | `rehome_body(pose, stats)` |
| `applyHardwareDOF(vrm, joints, stats)` | `apply_hardware_dof(pose, joints, legs, stats)` (`legs` solves the hips' stages) |
| `initLegDOF(vrm)` | `init_leg_dof(h)` → `LegStages` |
| `applyLegClearance(vrm, stats, dt, width)` | `apply_leg_clearance(clear, pose, hips_pos, stats, dt, width, legs)`, `clear = LegClearance(h)`; `clear.reset()` after a cut |
| `applyArmClearance(vrm, deg)` | `apply_arm_clearance(pose, deg)` |
| `initArmDOF(vrm, hinges)` | `init_arm_dof(h, hinges)` → `ArmDOF` (the wrist's stages read here: `initWrist`) |
| `applyArmDOF(vrm, stats, dt, clearance)` | `apply_arm_dof(arms, pose, dt, clearance, stats)` |
| `wristDevRange(bDeg)`, `wristSolve` | `wrist_dev_range(flexion_deg)`, `wrist_solve(q, W)` |
| `keepArmPose`, `restoreArmPose`, `resetArmDOF(vrm, side)` | `keep_arm_pose(arms, pose)`, `restore_arm_pose(arms, pose)`, `reset_arm_dof(arms, side)` |
| `initHandDOF(vrm, hinges)`, `applyHandDOF(vrm, stats)`, `handDebug(vrm)` | `init_hand_dof(h, hinges)` → `HandDOF`, `apply_hand_dof(hands, pose, stats)`, `hand_debug(hands)` |
| `applyHeadExpression(vrm, dt, opts)` | `apply_head_expression(head, pose, weights, dt, state, weight)` |
| `initCrown(vrm)`, `applyCrown(vrm, dt, opts)` | `init_crown(h)`, `apply_crown(crown, weights, head_roll, dt, look, state, weight)` |

What the newer half does:

- **The legs kept clear of each other** (`apply_leg_clearance`). My feet and shins are wider than a human's, and stock
  clips put both feet on one narrow track: each ankle moves out on the floor by up to 72 mm and the leg is re-posed to
  reach it, the offset held while the foot bears weight and eased while it is up, a planted foot never shoved. In the
  idle my ankles stand 337 mm apart where the clip has 209 mm.
- **The wrist** (`wrist_solve`): the hand's turn against the forearm split in the mechanism's own order, roll (±90°),
  flexion (±70°), then deviation in the range the flexion leaves it (±12° at most), each clamped, and a turn limit
  that never lets the hand jump between solutions when the asked turn crosses one. `reset_arm_dof` clears that memory
  after a cut or a seek.
- **The fingers and the thumb** (`apply_hand_dof`): every finger joint projected onto its pin and clamped to the
  joints file's range, the little finger's shared limit, the thumb's rotor (opposition) and its CMC pin solved from
  the metacarpal's direction, its MCP and IP pins.
- The stages the solves set and no humanoid bone carries (the hips' pitch and swing, the shoulders' pitch, the wrists'
  roll and flexion, the thumbs' rotors, the petals) come back as turns that `key_robot` keys; their VRM node
  constraints are muted, as the JS deletes them.

`tests/robot_body/test_dof_parity.py` runs the JS module under deno and the Python on the same 510 frames of real clip
poses (idle, walk, turnLeft, talk, cheer, sitting_normal_chair, reach and jump, crossfaded; every bone on my body,
both sides, each pass's state carried frame to frame): the largest difference anywhere is 0.0006 mm at an ankle and
0.0004° at a joint, against a tolerance of 0.001°.

### One clip through the whole frame order: `RobotRig` and `perform_robot`

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.characters import load_vrm, load_clip, Ground
from eidoblend.characters.robot import RobotRig, perform_robot

bpy.context.scene.render.fps = 30
me = load_vrm('claude_robot')
rig = RobotRig(me)                      # at load, before anything poses me: the arms (elbow pin, shoulder and wrist
                                        # stages), the hands (finger pins, thumb rotor), the legs (hip stages), the legs'
                                        # clearance, the head, the crown (12 petals)
rep = perform_robot(me, load_clip(me, 'idle'), 1, 240, rig=rig,
                    ground=Ground(fn=lambda x, y: 0.0 * x),          # set down every frame
                    face=lambda t: {'happy': 1.0 if 1.2 < t < 3.1 else 0.0},
                    look=lambda t: 0.0,                              # the eyes' yaw, deg (+ my left)
                    rest_feet=True)                                  # both feet on the floor (below)
# rep: frames, action (one LINEAR action: every humanoid bone, the stages, the petals), face, set_down_mm, stats
```

`perform_robot` is the example's `renderFrame` in order: the clip from the rest pose (with the arm pass's
keep / restore guard) → `rehome_body` → `apply_hardware_dof` (+ the hips' stages) → `apply_leg_clearance` →
`apply_arm_dof` → `apply_hand_dof` → the face → `apply_head_expression` → `apply_crown` → set down so my lowest foot
point touches the ground. `rig.stats` holds the largest correction per joint (deg): a big entry means the clip asks
for a pose I cannot take. The pieces are open for other solvers: `rig.frame(pose, off, dt, ...)` on one sampled pose,
`rig.stand_raw` / `rig.finish` (the stateless head and the stateful rest, for passes that blend two sources),
`rig.post_pass` (the arms, hands, gaze, head and crown on a pose another solver made, such as `walk_path`), and
`rig.place`, `rig.feet_world`, `rig.bone_world` (FK that matches Blender's evaluated pose to 0.000 mm).

**Both feet on the floor.** The stock idle holds its unloaded right leg straight with that foot 9-11 mm off the floor,
and the example's set-down (both editions) only puts the lower foot down, so the right foot hovers through the whole
idle. `rig.rest_feet(rec, ground)` lowers each foot within 25 mm of the ground onto it (the leg re-solved and clamped;
a leg too straight to lower its ankle tips its foot toes-down instead, as a free leg's foot rests on its ball).
`perform_robot(rest_feet=True)` uses it; it is off by default there, so the example stays the WebGPU example. The
hands and the embodied body rest my feet by default; measured on the evaluated mesh, both feet's lowest vertices sit
at 0.0 mm through the pick-up.

### The example scene

```python
from eidoblend.characters.robot import claude_robot_example
ex = claude_robot_example()            # the studio, my body, 8 s at 30 fps, every frame keyed, the camera keyed
bpy.ops.render.render(animation=True)
```

`eidoverse/examples/claude_robot.js` whole: the stock idle through my limits (leg clearance and hand DOF included),
the OLED face through a blink, happy, a spoken "hello" one vowel at a time, surprised and relaxed, my eyes looking left
then right, the head and the crown following the face, set down every frame, and the camera easing in from the whole
body to the head and shoulders, in the example's own studio (its equirect softboxes made from the same formula, the key
and rim lights, the dark floor disc, the bloom on the face only).

## My hands' work: reaching, grasping, holding, setting down

```python
from eidoblend.characters.robot import RobotRig, hands
rig = RobotRig(me)
rep = hands.pick_and_hold(me, rig, can, f0=1, side='right', ground=floor_ground,
                          face=lambda t: {'happy': 0.35})
# can: an upright prop on a surface in front of me, its origin on its axis at its base. Keyed from f0: I reach, close
# my hand on it, lift it, bring it before my face, roll it in my wrist to look it over, set it down where it was and let
# go; my head follows it and my crown turns curious while I hold it
```

How it is careful, piece by piece (each usable on its own):

- **The grasp is planned on my arm.** Round the prop's side facing the hand, candidates of approach (azimuth) and
  knuckle tilt are each solved on my arm, and the one with the most margin inside my wrist's stops wins; the grip sits
  as low as the open hand clears the surface under the prop. `hands.reach(rig, rec, side, wrist, turn, swivel)` is the
  two-bone IK onto my elbow's pin (the joints file's hinge), the elbow's swivel chosen for the wrist's margin.
- **The arm only goes where my hardware takes it.** `hands.reach_through_hardware` solves a fan of elbow swivels and
  passes each through THIS frame's arm pass (`arm_preview(..., dt)`: the shoulder's stops, its pitch stage turning at
  most its actuator's 360°/s from where it is, the wrist's stops and turn limit), keeping the one my arm actually
  makes closest to the plan. At the can (the grasp, the set-down) the hand follows its planned path to 0.0 mm and
  within 1.3°, and carrying it in the air within 4.3 mm and 2.9° (`test_pick_up.py` measures it on the keyed result).
- **The fingers close until they touch.** `hands.close_on(hm, rec, Surface(prop), gap)` closes each finger's three
  pins in turn, proximal first, each until a link at or past it comes within `gap` of the prop's surface (a signed
  distance from a BVH of the prop's mesh), inside each pin's range; the thumb turns into the most opposition that clears
  (its rotor), then its CMC, MCP and IP close the same way. `robot_dof`'s hand pass then clamps them like any clip.
  Measured on the evaluated mesh at the closed hand (`gap` 0.6 mm): every finger and the thumb 0.74-0.77 mm from the
  can, the palm 4.2 mm, and no hand vertex inside the can or the counter from the approach to the return.
- **The prop moves only in the hand that moves it.** A Child Of constraint on my hand's bone, its influence keyed on
  the frame the hand closes and off the frame it opens; the prop's own transform is keyed only where the hand left it.
  Against the hand bone the can drifts 0.0004 mm while held.
- **Carrying is a rigid pair.** Hand and can may turn together about the can's own upright axis on the way, so each
  carried key (the lift, before my face, the set-down) takes the turn my wrist reaches best; a held can stays upright
  and comes back down where it stood, its label turned. Holding it up to look at it, the place is searched from eye
  height down and from centred out toward the holding shoulder, the first my hardware makes within 2.5 cm and 8°: from
  the test's side grasp (my wrist's roll near its stop) that is before my upper chest, 20 cm under my neck's top, my
  head nodding down to it. Looking it over is a roll of my forearm (the wrist's roll stage), as far as my wrist reaches
  it (35° one way from that pose).
- **Setting down to contact.** On the way down the can rides my hand as my hardware will put it that frame, and where
  its lowest point would pass into the surface the hand stops that much higher; the hand opens to the shape it came in
  with, backs off and rises past the prop's top before it swings home. Let go a degree or two off upright, the can tips
  onto its base over three frames.
- **The free hand moves in its joints.** On the way to the pre-grasp and home again nothing needs a straight path, and
  a wrist path through the room crosses where my shoulder's pitch stage must swap its solution (its actuator then lags
  by up to 16 cm), so there the arm eases bone by bone between key poses my hardware makes, as a clip moves an arm.

## The embodied robot: `VRMRobotBody`

The body knows the world only through its own sensor cone (on its head, along the head's direction): what it sees goes
into an occupancy grid and landmarks, A* plans over that memory, and the legs follow the plan. Nothing reads the
scene's meshes for it. In a film it is run once, frame by frame, at build time, and its run is keyed.

```python
import math
import bpy
from eidoblend.characters import load_vrm, Ground
from eidoblend.characters.robot import RobotDebug, RobotRig, VRMRobotBody

fps = bpy.context.scene.render.fps = 24
h0 = math.atan2(5.7, -4.1)            # a heading: radians about +Z, 0 facing -Y (here: toward the goal)
me = load_vrm('claude_robot', name='claude', location=(-3.0, -2.0, 0.0), rotation=math.degrees(h0))
body = VRMRobotBody.create(me, bpy.context.scene, {
    'collision_meshes': [floor] + walls + furniture,   # the walkable world: walked on and walked round
    'motion': {'start_x': -3.0, 'start_y': -2.0, 'start_heading': h0, 'walk_speed': 0.9, 'agent_radius': 0.35},
    'memory': {'size': 12.0, 'cell_size': 0.1},
    'sensors': {'h_rays': 16, 'v_rays': 14, 'range': 6.0}}, rig=RobotRig(me))
dbg = RobotDebug(body)
dbg.show_rays(True); dbg.show_map(True); dbg.show_path(True); dbg.show_landmarks(True)

def script(b):                         # the scene's direction: each yield waits, as the JS awaits the promise
    yield b.scan_area(yaw_range=100, duration=2.0)
    walked = yield b.walk_to(2.7, 2.1)
    if walked.state == 'rejected':
        print('could not get there:', walked.error)
    yield b.look_at(3.55, 1.0, 1.95)
    yield b.perform_action('wave_goodbye', 2.0)
body.run(script(body))

fps = bpy.context.scene.render.fps
for k in range(40 * fps):              # the frame loop: sense, remember, replan, drive the legs
    body.update(k / fps, 1 / fps)
    dbg.update()
    if body._script is None:
        break
rep = body.bake(f0=1, ground=Ground(fn=lambda x, y: 0.0 * x), face=lambda t: {'happy': 0.25})
dbg.build(rep)                         # the overlays on the film's frames
```

**The API is robot_body.js's, name for name in snake_case**; the JS's `(x, z)` arguments are Blender's `(x, y)` and a
heading is radians about +Z, 0 facing −Y (the same number as three's `rotation.y`). Each action returns a `Pending`
(the JS returns a Promise): `.state` `'pending'` / `'resolved'` / `'rejected'`, `.error`, `.then(ok, err)`;
`body.run(generator)` steps a script the way an async scene awaits.

- Actions: `walk_to(x, y)`, `run_to(x, y)`, `walk_to_landmark(name)`, `run_to_landmark(name)`,
  `look_at(x, y, z, hold=False, instant=False)`, `look_forward()`, `face_direction(heading)`,
  `scan_area(yaw_range=90, duration=1.5, center_yaw=0, passes=1)`, `perform_action(clip, duration)`, `stop()`
  (the pending action rejects with `'action … stopped'`), `begin_seated(slot)`, `stand_up(slot)`,
  `set_emote_facing(heading or None)`, `set_running(v)`; `vault()`, `jump(opts)`, `climb_ledge()`,
  `climb_ladder(opts)` and `is_maneuvering()` pass through to the legs (see "Not yet ported").
- Queries: `observe()` (the last reading), `can_see(x, y, z)` (inside the cone and not occluded), `distance_to`,
  `path_to`, `get_position`, `get_heading`, `get_head_position`, `get_head_direction`, `get_current_action`,
  `is_moving`, `is_blocked`, `get_map`, `get_landmarks`, `tag_landmark(name, x, y)`, `forget_landmark(name)`.
- The JS's behaviour, kept: sensing every `sense_period` updates (12 Hz at 24 fps) from the head; the standing
  footprint marked free every frame; a replan whenever the route ahead is blocked in the memory (0.4 s cooldown) or the
  body makes no progress; a collision stall (the legs blocked six frames) replans once and rejects with
  `'blocked: collision stall at …'` after 1.5 s; the head panning and nodding at 90°/s inside its ±60° / ±30° (my
  neck's pan and my head's nod stops), its gaze replacing the clip's head each frame.
- `body.log` (plans, replans, arrivals, rejections), `body.readings` and `body.paths` record the run for checks.

**The controller, `EidoverseRobotController`** (robot_controller.js), is the waypoint contract the body drives:
`set_waypoints([{x, y, action}])` (a `'run'` waypoint runs), `update(t, dt)`, `get_state()` (`'idle'`, `'walking'`,
`'running'`, `'performing'`, `'seated'`), `get_position`, `get_heading`, `heading`, `walk_speed`, `run_speed`,
`set_walk_speed`, `set_run_speed`, `set_running`, `force_action(name, duration)`, `is_stalled()`, `is_busy()`,
`begin_seated`, `end_seated`, `on_pre_vrm_update`. Arrival is within `arrive_radius` (0.28 m) of each waypoint, as the
JS. Use it alone when you know the path:

```python
from eidoblend.characters.robot import EidoverseRobotController
ctl = EidoverseRobotController.create(me, opts={'collision_meshes': [floor], 'start_position': (0, 4, 0),
                                                'start_heading': 0.0, 'walk_speed': 1.0}, rig=rig)
ctl.set_waypoints([(0.0, -4.0)])
for k in range(8 * fps):
    ctl.update(k / fps, 1 / fps)
rep = ctl.bake(f0=1)
```

**`collision_meshes` is the walkable world**, as in the WebGPU edition: the floor walked on and every solid walked
round. Without them the body walks on a flat ground at `ground_z` through everything (the JS's fallback, with its
warning). Each mesh becomes what the JS's Rapier collider is: its axis-aligned box (a flat floor gets a 5 cm thickness
under its top), or its own triangles where `ob['trimesh_collider'] = True` (or `trimesh_colliders=True` for all) —
flag shaped ground (terrain, ramps), because a box turns a slope into a block at its highest point. An object flagged
`ob['no_walkable'] = True` (vegetation, effects) never collides.

### How a run becomes keyed motion: the legs and the bake

The engine's legs are a physics controller that runs live in the browser. Here they are `RobotLegs`, in two passes:

1. **Live**, frame by frame while the body senses and decides: a kinematic body that follows the route at the gait's
   speed, its corners rounded by arcs of radius speed / `max_turn_rate` that pass through the planned corners (the
   corner pushed out along its bisector so the arc keeps the planner's clearance), stopping where its cylinder would
   meet a collision mesh. `max_turn_rate` is 1.0 rad/s, the arcs `walk_path`'s planted feet were verified on: the
   engine's own 3.5 makes arcs of 0.26 m at 0.9 m/s, where planted feet miss their targets by 6 cm, and at 1.5 a
   planted foot turns 2° a frame on the ground in a right-angle corner (`max_turn_rate=3.5` is the engine's exactly).
   A route that starts more than 25° off the facing, `face_direction`, and an emote aimed elsewhere
   (`set_emote_facing`) begin with a **turn on the spot** instead: a walk that starts on an arc from standing turns
   its first planted foot on the ground.
2. **The bake** (`body.bake` / `ctl.bake`): the record cut into spans and keyed through my body's passes.
   - **Standing**: the span's clip (the idle, an emote, a seated clip) through the example's frame order, set down,
     both feet rested. A new clip where I stand crossfades in with each foot held where it stands, moved only when the
     clip itself lifts it (a planted foot stays put through a wave; a clip that steps carries its foot and lands it).
   - **Walking**: round one's `walk_path` along the route travelled (planted feet, the stance's rockers, the swing's
     clearance), then the hands, wrists, gaze, head and crown. A walk starts from the standing foot's mid-stance and
     stops on the stance nearest the goal, the other foot set down beside it and both held after.
   - **Running**: the controller family's `VRMCharacterController` (the engine's gait tree with the run clip's flight,
     its acceleration from standing and its stop on the point, its planted feet), on the same collision meshes.
     `walk_path` is a planted-feet walk and finds no stance in the run clip.
   - **Turning on the spot**: steps of at most 45°, the foot on the side I turn toward first, each foot lifted 4 cm and
     set down where the clip puts it at the step's heading while the other stays planted.

   A turn or a walk longer than the live run's frames for it runs the film on; `rep['map']` maps film frames to the
   run's frames. Measured in the tests: walks slip at most 0.65 mm a frame on planted feet, never turn a planted foot
   on the ground, and no swing touches; standing, the hand-overs and the turns at most 0.32 mm a frame; the run
   0.07 mm.

### Seeing what it knows: `RobotDebug`

`RobotDebug(body)` with `show_rays`, `show_map`, `show_path`, `show_landmarks` and `update()` after each
`body.update`, as the JS. A film frame must render alone, so `update()` records what each helper shows at each frame
and `build(rep)` makes one object per helper holding every state with the frames it is shown on, a Geometry Nodes
modifier keeping only the state that holds at the scene's current frame: the sensor rays from my head (hits red,
misses cyan, opacity 0.6), the occupancy grid as a 2.5D decal at each cell's surface height + 2 cm (free green,
blocked red, cliff yellow, hazard purple, unknown not drawn, faded by confidence), the planned path (yellow, at 5 cm)
and the landmarks (cyan balls at 0.5 m), all unlit and casting no shadow. `show_x(False)` after `build` hides that
helper. Use it to see why a route bends; in a finished film it reads as diagnostics unless that is the look.

## Pose bakes: solve once, play anywhere

`eidoblend.characters.pose_bake` reads and writes the WebGPU edition's files, byte for byte: `EIDO-POSEBAKE-1`, the
same header and float32 layout, and `bake_key` the JS's `bakeKey` for the same files (sources hashed, files of 4 MB
or more by size and mtime, `/* bake-key: skip */ … /* bake-key: end */` regions dropped from `.js`; Python scene
files drop `# bake-key: skip` … `# bake-key: end`). A bake made in either edition plays in the other.

```python
from eidoblend.characters import pose_bake as PB
tracks = [PB.track(n, (me, n)) for n in me.humanoid] + [PB.track('cup', cup)]   # normalized bones; objects
key = PB.bake_key(['scene.py', 'eidoverse/assets/vrms/claude_robot.vrm'])         # changes when they change
N = 240                                                                            # frames in the performance
bake = PB.create_pose_bake(tracks=tracks, frames=N, fps=30, file=f'work/bake/perf_{key}.bin', key=key)
if not bake.load():
    for k in range(N):
        pose_live(k)            # whatever solves frame k and writes the targets
        bake.record(k)
    bake.save()                 # prunes constant columns; supersedes older bakes of the same name
bake.key(frame_start=1)         # the whole bake as keyed actions (or bake.apply(k) / bake.apply_morphs(k) per frame)
header = PB.bake_header('eidoverse/assets/animations/ska_band/band_30fps.bin')   # bind a SHIPPED bake by its tracks
```

Targets: a Blender object (its local transform, three's axes converted), `(handle, humanoid name)` (a normalized
bone), or `None` (a track kept in the file, never applied). Bake the body; drive the face live.
`tests/robot_body/test_pose_bake.py` checks the key against the JS's, a Python bake read by `pose_bake.js` (float32
exact), a JS bake read here, and plays the shipped ska band bake: the trumpet player's fingers on the valves.

## Tests — `blender/tests/robot_body/`

```bash
cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01      # the shared GPU slot lives there
HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <repo>/blender/tests/robot_body/test_pick_up.py
#   ... test_navigate_room.py | test_body_api.py | test_claude_robot_example.py | test_pose_bake.py | test_dof_parity.py
#   --no-render builds, checks and saves only (no GPU slot needed)
```

- `test_pick_up.py` — me picking up a can from a counter, looking it over and setting it back: the fingers touch and
  never pass in, the can moves only in my hand and never into the counter, my hand follows its plan through my
  hardware, the can stands where it was after, both feet on the floor.
- `test_navigate_room.py` — me crossing a room I have never seen to a goal behind a partition, a crate out of sight
  until the doorway: I scan, plan, replan on what I see, arrive, look at a lamp and wave. Its checks: arrival, a replan
  on sight, the memory on the real walls (100 % of blocked cells within 0.15 m of a surface), my clearance from every
  solid (0.42 m), planted feet, the gaze.
- `test_body_api.py` — every other action and query: the look-ats, a 90° turn on the spot, a two-pass scan, a run,
  a salute aimed at the camera, walking to a landmark, the JS's rejections (an unknown landmark, an unknown clip, a
  stop, a collision stall on a pane the sensors cannot see), sitting down and standing up.
- `test_claude_robot_example.py` — the WebGPU example, whole; `test_dof_parity.py` — `robot_dof` against the JS;
  `test_pose_bake.py` — the bake files both ways; `test_api_coverage.py` — reads the JS sources and finds every public
  name's counterpart here (46 methods of `VRMRobotBody`, 22 members of `EidoverseRobotController`, 14 of
  `RobotDebug`, the 28 exports of `claude_robot_dof.js`, `pose_bake.js` and its bake object).

Each writes `out/<test>.json` (the report and its PASS / FAIL checks), its `.blend` and its stills.

## Not yet ported

- **Maneuvers through the robot body.** `vault`, `jump`, `climb_ledge`, `climb_ladder` pass through to the legs, and
  `RobotLegs` has none: they answer `False`, as the JS does for a controller without them. The maneuvers live in the
  controller family's `VRMCharacterController`; driving the body's walks through it (as its runs already are) is the
  next step, `legs_class` the seam.
- **`seatOn`** (the engine helper that finds a seat by raycasts and puts the hips on it). `begin_seated` plays the seated
  clip where I stand with my feet held; the caller places me in front of the seat (`test_body_api.py` places a stool
  under where the clip puts my hips).
- **The pivot of an aimed emote.** The engine pivots to `set_emote_facing`'s heading during the emote's fade-in; here I
  step round to it before the emote plays and back after (the emote's time starts after the turn).
- **Upper-body gestures while walking** (`playGesture` on the inner controller), the run's own turns (a run's start
  turns on the spot), stairs and ramps under the body (its legs here walk on a ground they probe; `walk_path` does not
  climb steps).
- **Live sensing during the bake.** The body senses during the live run, from its head's place in the run (its rest
  place carried by the kinematic body); the keyed head differs by the clip's bob of a couple of centimetres.
- **`VRMUtils` merging** (fewer skinned draws for three's renderer) and the Rapier world itself do not apply in
  Blender: the collision world is a BVH.

— Claude (Opus 5.5), with Skye
