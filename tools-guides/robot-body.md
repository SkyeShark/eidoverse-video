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
- **The crown's and the head's states** (`CROWN_STATES`: neutral, happy, angry, sad, relaxed, surprised, thinking,
  listening, curious, resting; `HEAD_STATES` for the seven that move the head): pass one as `crown_state` /
  `head_state` (and `state_weight`) to `RobotRig.frame` / `finish` / `perform_robot`, on top of what the face's
  expressions already do to them; the crown's lead screws move at 240°/s and the neck at 120°/s, so a state arrives
  over a few frames.

```python
rep = perform_robot(me, load_clip(me, 'idle'), 1, 72, rig=rig, crown_state='listening')   # the whole take, one state
rec = rig.frame(pose3, off, 1 / 24, {}, None, 'thinking', 'thinking', state_weight=1.0)   # frame by frame
```

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
`rig.post_pass` (the arms, hands, gaze, head and crown on a pose another solver made, such as the controller family's
plant: the embodied body's bake), and
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

As a film through the runner, like every other example, `blender/examples/claude_robot/` is the same example in the
scene format ([scene-format](scene-format.md)): its `scene.py` calls `claude_robot_example()` at the example's own
30 fps and 8 s and only reads my body's files, and its `scene.json` asks 960 × 540 at 16 samples (raise both for a
final film), the film H.264 into `blender/examples/out/claude_robot.mp4`:

```bash
python eido_blender.py build  blender/examples/claude_robot/scene.json                   # every frame keyed into its .blend
python eido_blender.py render blender/examples/claude_robot/scene.json --at 2.1 --at 3.85 --at 6.8   # stills at the beats
python eido_blender.py render blender/examples/claude_robot/scene.json                   # the film, H.264
```

## My hands' work: reaching, grasping, holding, setting down

```python
from eidoblend.characters.robot import RobotRig, hands
rig = RobotRig(me)
rep = hands.pick_and_hold(me, rig, can, f0=1, side='right', ground=floor_ground,
                          face=lambda t: {'happy': 0.35})
# can: an upright prop on a surface in front of me, its origin on its axis at its base. Keyed from f0: I reach, close
# my hand on it, lift it, bring it before my face, roll it in my wrist to look it over, set it down where it was and let
# go; my eyes stay on it (my head and my face's eyes) and my crown turns curious while I hold it
```

How it is careful, piece by piece (each usable on its own):

- **The grasp is planned on my arm.** Round the prop's side facing the hand, candidates of approach (azimuth) and
  knuckle tilt are each solved on my arm, and the one with the most margin inside my wrist's stops wins; the grip sits
  as low as the open hand clears the surface under the prop. `hands.reach(rig, rec, side, wrist, turn, swivel)` is the
  two-bone IK onto my elbow's pin (the joints file's hinge), the elbow's swivel chosen for the wrist's margin. A
  flat-sided prop (a carton, a box) met at an angle squares the approach to its face (a palm square to the azimuth
  would meet the face on its rim), the palm goes on the face itself, and the whole palm is measured against the prop:
  where any of it would come closer than `palm_gap`, the grasp backs off along the approach.
- **The arm only goes where my hardware takes it.** `hands.reach_through_hardware` solves a fan of elbow swivels and
  passes each through THIS frame's arm pass (`arm_preview(..., dt)`: the shoulder's stops, its pitch stage turning at
  most its actuator's 360°/s from where it is, the wrist's stops and turn limit), keeping the one my arm actually
  makes closest to the plan. At the prop (the pre-grasp to the grasp, the set-down to the hand opening) a degree of
  the hand's turn weighs 8 mm in that choice (`AT_PROP_TURN_W`; 2 mm in the air), so my elbow swings round to keep the
  prop's turn rather than hold its place while my wrist meets a stop. At the can the hand follows its planned path to
  0.0 mm and within 0.0° (my right hand) and 1.2° (my left), and carrying it in the air within 4.3 mm and 2.9°
  (`test_pick_up.py` measures it on the keyed result).
- **The fingers close until they touch.** `hands.close_on(hm, rec, Surface(prop), gap)` closes each finger's three
  pins in turn, proximal first, each until a link at or past it comes within `gap` of the prop's surface (a signed
  distance from a BVH of the prop's mesh), inside each pin's range; the thumb turns into the most opposition that clears
  (its rotor), then its CMC, MCP and IP close the same way. A thumb that closes so without touching (on a square
  carton the pre-shaped thumb presses into the side at every opposition down to 15°, and from there it curls past the
  carton into my palm) is searched again opened flat: the most opposition that clears flat and closes onto the prop
  (on the carton 60°, touching it), and the hand comes in and lets go with the thumb opened so.
  `robot_dof`'s hand pass then clamps them like any clip.
  Measured on the evaluated mesh at the closed hand (`gap` 0.6 mm): every finger and the thumb 0.74-0.77 mm from the
  can, the palm 4.2 mm, and no hand vertex inside the can or the counter from the approach to the return. On the
  carton (`test_pick_up.py --prop carton`) the fingers and the thumb 0.3-0.9 mm from it, the palm 3.7 mm, nothing
  inside it; my left hand (`--side left`) passes the same touch, the hold and the set-down on both props.
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
- **My eyes are on the work.** From the reach my head turns to the can (VRMRobotBody's head actuator: at most 90°/s,
  speeding up and slowing down, `head_rate` / `head_accel`), follows it a beat ahead while I lift it and look it over
  (`gaze_lead`), goes ahead of my hand to where I set it down, and comes back onto the idle's own head after; the gaze
  starts from the clip's head with its roll (`RobotRig.apply_gaze(..., roll)`), so it never jumps a frame. My neck's nod
  stops at 30°, and the counter's top lies 45-50° under my eyes, so my face's eyes (its look expressions, the VRM's
  look-at ranges: 28° across, 25° down) take what the head leaves (`look_eyes`, at most `eye_rate`). Measured: my
  eyes within 4.2° of the can from the reach until it is looked over and 1.4° of where I set it down (my head alone
  would be 26° off), the head turning at most 3.9° a frame.

## The embodied robot: `VRMRobotBody`

The body knows the world only through its own sensor cone (on its head, along the head's direction): what it sees goes
into an occupancy grid and landmarks, A* plans over that memory, and the legs follow the plan. Nothing reads the
scene's meshes for it. Its legs are the engine's character controller, the controller family's port
([controller.md](controller.md)): I walk and run my route over stairs and ramps, take low cover, a ledge or a gap on
the way, and turn, emote and sit with that controller's clips. In a film the body is run once, frame by frame, at build
time, and its run is keyed.

```python
import math
import bpy
from eidoblend.characters import load_vrm
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
    body.update(k / fps, 1 / fps)      # update(t) is the scene's frame frame_start + t * fps
    dbg.update()
    if body._script is None:
        break
rep = body.bake(face=lambda t: {'happy': 0.25})   # keyed from frame_start; the feet stand on the collision meshes
dbg.build(rep)                         # the overlays on the film's frames
```

**The API is robot_body.js's, name for name in snake_case**; the JS's `(x, z)` arguments are Blender's `(x, y)` and a
heading is radians about +Z, 0 facing −Y (the same number as three's `rotation.y`). Each action returns a `Pending`
(the JS returns a Promise): `.state` `'pending'` / `'resolved'` / `'rejected'`, `.error`, `.then(ok, err)`;
`body.run(generator)` steps a script the way an async scene awaits, and `body.wait(seconds)` /
`body.until(predicate)` are the scene's own timers (a JS scene's `await sleep(ms)` and its polling loops).

- Actions: `walk_to(x, y)`, `run_to(x, y)`, `walk_to_landmark(name)`, `run_to_landmark(name)`,
  `look_at(x, y, z, hold=False, instant=False)`, `look_forward()`, `face_direction(heading)` (a turn on the spot,
  resolved when I face it: the JS snaps the heading), `scan_area(yaw_range=90, duration=1.5, center_yaw=0, passes=1)`,
  `perform_action(clip, duration)`, `stop()` (the pending action rejects with `'action … stopped'`),
  `begin_seated(slot, chair=None, face=None)`, `stand_up(slot)` (below: "Seats"), `set_emote_facing(heading or None)`,
  `set_running(v)`.
- Moves, as the JS passes them to the engine's controller: `vault()`, `jump({'distance', 'height'})`,
  `climb_ledge()`, `climb_ladder({'height', 'rate', 'firstRung', 'rungSpacing', 'timeScale'})`, each the move ahead
  along my heading from wherever I am, standing, walking or running, `True` when it started (`False`: nothing it fits
  ahead; seated, in an emote or turning on the spot), and `is_maneuvering()` while it lasts (below: "The moves").
- Gestures: `play_gesture(slot, weight=2.5, loop=True)` and `stop_gesture()`, the JS's
  `body.controller.charCtrl.playGesture`: `slot` masked to my upper body and blended over whatever my legs do (a walk,
  a run, the stairs, standing) until stopped; the controller fades it out through turns on the spot, moves and emotes.
- Queries: `observe()` (the last reading), `can_see(x, y, z)` (inside the cone and not occluded), `distance_to`,
  `path_to`, `get_position`, `get_heading`, `get_head_position`, `get_head_direction`, `get_current_action`,
  `is_moving`, `is_blocked`, `get_map`, `get_landmarks`, `tag_landmark(name, x, y)`, `forget_landmark(name)`.
- The JS's behaviour, kept: sensing every `sense_period` updates (12 Hz at 24 fps) from my head; the standing
  footprint marked free every frame; a replan whenever the route ahead is blocked in the memory (0.4 s cooldown) or the
  body makes no progress (a move in flight and a turn on the spot are not "no progress"); a collision stall (the
  controller's move-and-slide cancelling the step six frames running) replans once and rejects with
  `'blocked: collision stall at …'` after 1.5 s; the head panning and nodding at 90°/s inside its ±60° / ±30° (my
  neck's pan and my head's nod stops), its gaze replacing the clip's head each frame.
- **I sense from my head where the take has it**: the head bone in the controller's pose of the frame last stepped
  (its gait's bob, its height on a stair, a move's place), my torso as my hardware holds it (`robot_dof.rehome_body`:
  my single waist joint does not take a clip's chest bend, which in a vault carried the clip's head up to half a metre
  off mine). Across, that is my keyed head to 0.0 mm in `test_navigate_room.py` and `test_body_route.py`; up, the
  film's plant still lowers or raises my pelvis after the run to plant my legs, and the same senses cast from my keyed
  head make a memory 3.2 % of whose cells differ, with the same route through it (below: Not yet ported).
- **I see what moves.** Where the sensed world has moving objects (anything keyed, driven or constrained, deformed by
  an armature that is, or under a parent that is: a door, a cart, another character), each sense first sets the scene
  to the frame of its `t` (`frame_start` + t × fps; `create(opts={'frame_start': ...})`) and the sensors rebuild their
  view of it where something moved, as the JS's raycaster casts against the live scene. The view is split
  (`RobotSensors.refresh(dynamic=movers)`, [navigation](navigation.md)): what stands still is read once, at the first
  sense, and each rebuild after it reads the movers alone (`dynamic_only=True`), so a large still set beside them costs
  nothing per sense. `body.movers()` lists
  them. In `test_body_moving.py` every hit on a sliding door and a rolling cart lies on its surface as the scene has it
  at that sense's frame (0.0 mm), where the scene's first frame would put the cart's hits 2.6 m off; I see the door
  shut (no path), then open (the walk goes through it), and the cart crossing (a replan round it). The view is rebuilt
  only at a sense where a mover has moved since the last (a mesh an armature, its shape keys or a modifier can
  reshape counts as moved every sense): 33 of that run's 177 senses, a median 1.0 ms each in that room;
  `body.refreshes` counts them. The legs walk against the colliders made at `create` (the JS's Rapier world is fixed
  the same way): a door or a cart that moves is seen and planned round, never walked against.
- `body.log` (plans, replans, arrivals, rejections), `body.readings` and `body.paths` record the run for checks.
- **A look-at is re-aimed from the keyed body.** The JS aims the head from the head and the heading it renders; here the
  run is live and the film is its bake, and the keyed head stands a little off the live one (the plant's pelvis). So
  each frame with a look-at target records it with the head's place and heading the live aim used, and the bake adds the
  aim's change from those to the keyed ones (the head's rate-limited turn kept, clamped at `yaw_limit` /
  `pitch_limit`). In `test_navigate_room.py` my head's facing comes to 7.4° of the lamp it looks at.

**Any VRM, not only mine.** robot_body.js drives any VRM through the engine's own controller, which knows nothing of my
hardware, and so does this one: the same legs, and `RobotRig(h)`, which knows my body by its hips' stage bones and on
any other VRM is a plain rig: its pose as the controller plays it, the gaze on its head bone exactly as
`_applyHeadOverride` sets it (its neck the controller's); no joint limits, clearances, head states or crown.
`test_other_vrm.py` walks Aletheia round a crate to a lamp: her arms, hands, spine and chest are the controller's own
pose on every frame, her head bone's turn is the JS's on every frame, her hair's 40 spring chains are baked over the
take, and my hands' work (`hands`) refuses her plainly (it needs my joints file); `test_body_route.py --vrm aletheia`
takes her over the stairs, the wall and the ditch.

```python
her = load_vrm('aletheia', location=(-2.6, -0.2, 0.0), rotation=math.degrees(h0))
body = VRMRobotBody.create(her, bpy.context.scene, {'collision_meshes': [floor] + walls + [crate],
                                                   'motion': {'start_x': -2.6, 'start_y': -0.2, 'start_heading': h0}})
```

**The controller, `EidoverseRobotController`** (robot_controller.js), is the waypoint contract the body drives:
`set_waypoints([{x, y, action}])` (a `'run'` waypoint runs), `update(t, dt)`, `get_state()` (`'idle'`, `'walking'`,
`'running'`, `'performing'`, `'seated'`), `get_position`, `get_heading`, `heading`, `walk_speed`, `run_speed`,
`set_walk_speed`, `set_run_speed`, `set_running`, `force_action(name, duration)`, `is_stalled()`, `is_busy()`,
`begin_seated`, `end_seated`, `on_pre_vrm_update`, the moves; and this edition's `turn_to(heading)`, `is_turning()`,
`play_gesture`, `stop_gesture`. A waypoint is passed within `arrive_radius` (0.28 m), as the JS; the walk is over when
my legs have slowed down and stopped on the last one. `create(h, overrides, opts)` takes the JS's opts
(`start_position`, `start_heading`, `walk_speed`, `run_speed`: the routes' paces, default this body's own, measured on
its clips; `max_turn_rate`, default the controller's 3.5 rad/s; `arrive_radius`, `collision_meshes`,
`trimesh_colliders`, `ground_z`) and `controller_opts` (the JS adapter's `opts.controllerOpts`: any
`VRMCharacterController` option for my legs, such as `{'auto_maneuvers': False}` or `{'vault_max_rise': 1.0}`;
`VRMRobotBody.create` passes its own `controller_opts` on, which robot_body.js does not); `overrides` is the JS's
`{'standard_animation_overrides': {'vrma_library': {slot: '.vrma path'}}}` (the stock slots played from other files,
the gait tree measured on them; `VRMRobotBody.create`'s `character_controller_overrides`). Use it alone when you know
the path:

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
round. Without them the body walks on a flat 120 m slab at `ground_z` through everything (the JS's fallback, with its
warning). Each mesh becomes what the JS's Rapier collider is (`robot.CollisionWorld`, the controller family's world
over these colliders: its ground and stair probes, its move-and-slide, the moves' scans and the plant all read it): its
axis-aligned box (a flat floor gets a 5 cm thickness under its top), or its own triangles where
`ob['trimesh_collider'] = True` (or `trimesh_colliders=True` for all) — flag shaped ground (terrain, ramps, stairs),
because a box turns a slope or a flight into a block at its highest point. An object flagged `ob['no_walkable'] = True`
(vegetation, effects, a ladder's rungs) never collides. Keep seats out of it (the controller reads a pan as a step to
climb) and things that move (they are seen, not collided with). What is over my head belongs in it like any wall: a
doorway's lintel, a ceiling, a beam. My legs' probes look under it (the controller family's `ground_under_overhead`;
the engine's probes drop from 3 m over the body and read its top as the ground ahead, so a lintel in the colliders
started a wall scramble in its doorway), and in `test_body_moving.py` I walk through a doorway under its lintel with my
feet on the floor.

### My legs: the engine's controller, frame by frame

The engine's legs are its physics character controller. Here they are `RobotLegs`: the controller family's
`VRMCharacterController`, set up as its `Locomotion` sets one up for a film (the robot preset; the stock clips; the gait
tree at this body's own paces, measured on its clips: my walk 1.52 m/s, my run 3.23 m/s; distance matching), on the
colliders above, and stepped once per `body.update` (`legs.ctrl` is the controller, `legs.loco` its `Locomotion`). Each
frame the adapter hands the legs a direction and they run the command in hand, the controller family's own:

- **a route** (`film.FollowPath`, at `walk_speed` or `run_speed`): from standing, a turn on the spot first where the
  way is more than 25° off my heading (my hip's yaw ring cannot twist a planted leg further; 60° on any other VRM),
  then it speeds up, follows the route with its corners rounded at the controller's own turn rate (3.5 rad/s, the
  engine's `maxTurnRate`), and slows down to stop on the goal. A replan hands it the new route from where I am, at my
  speed: the walk goes on;
- **a turn on the spot** (`film.TurnTo`, the controller's turn clips; under 20° the facing eases round):
  `face_direction`, and an emote's turn to its aim;
- **an emote** (`emotes.EmoteCmd`: in at the walk's own fade, out through the standing pose);
- **a seat** (`emotes.SeatOn` and `StandUp`: "Seats" below).

Whatever the engine's controller does on its own while it walks or runs happens here on its own: stairs and ramps on
its stair clips at the tread-synced pace; a cross slope steeper than my ankle's 14.9° of roll, each planted boot
standing on its edge at one roll through its stance ([controller](controller.md)); low cover vaulted, a ledge climbed,
a gap jumped and a big drop landed
(`fallLand`), its auto-maneuvers, wherever the route meets them; a move called mid-stride starts out of the walk or the
run, and the route goes on from where it lands me; a run turns at the controller's rate. Those moves are for what lies
on the route. The JS's adapter stops pushing the controller within `arrive_radius` of the last waypoint, so a wall just
past the goal never draws a move; my legs slow down to stop on the goal under their own input, so once the goal is
within the controller's scan they read its scan of the path ahead and hold the moves while the nearest thing they would
start for lies past the goal (`test_body_api.py` runs to a corner 0.4 m short of a 5 m pane: no move plays; the course
in `test_body_route.py` still vaults and jumps on the way). The planner routes the JS's
way, round anything more than `max_step_height` (0.4 m) above or below the floor it is on; give it the controller's
reach (`'planner': {'max_step_height': 1.15}`, the highest cover the controller vaults) and the route crosses low cover
and ditches, which the controller then takes as it reaches them.

```python
body = VRMRobotBody.create(me, scene, {'collision_meshes': solids,
                                       'motion': {'start_x': -7.0, 'start_y': 0.0, 'start_heading': math.pi / 2,
                                                  'walk_speed': 0.9, 'run_speed': 2.6},
                                       'planner': {'max_step_height': 1.15},       # cross what the controller takes
                                       'controller_opts': {'vault_max_rise': 1.1}}, rig=RobotRig(me))

def script(b):
    b.play_gesture('cheer')                      # over the walk, until stopped
    walk = b.walk_to(6.6, 0.0)                   # up and down a flight, over a wall, across a ditch
    yield b.until(lambda: b.get_position()['x'] > 0.0 or walk.done)
    b.vault()                                    # out of the stride (or let the controller take the wall itself)
    yield walk
    yield b.run_to(10.6, 1.4)                    # round a pillar, turning as it runs
```

**The bake.** `body.bake()` bakes the take as the controller family bakes its own (`emotes.bake` over the legs'
`Locomotion`: the plant puts the feet down over the whole run with my hardware pass on every frame, and a seat gets its
seated feet and its hand-overs), then keys my body's remaining passes frame by frame (through a move, a foot my leg
clamps put back into the face it climbs set out onto it: below, "The moves"; the wrists' stages, the hands' pins and
the thumb's rotor, the gaze, the head and the crown). Last, the VRM's spring chains are simulated over the keyed take
(the controller family's `Locomotion.bake_springs`, as the engine's `vrm.update` steps them every frame: Aletheia's
hair; my body has none; `bake(springs=False)` leaves them out). Every frame of the run is one film frame
(`rep['map']` is the identity); `rep['moves']`, `rep['turns']`, `rep['emotes']` and `rep['seats']` list what played,
`rep['segments']` carries the controller family's `checks.feet` on each gait, and `rep['springs']` the chains' bake.

Measured: in `test_navigate_room.py` every gait passes the controller family's `checks.feet`, the least-moving sole
point in contact moves at most 0.1 mm a frame on the keyed result, and the heading turns at most 3.5 rad/s;
`test_body_route.py` walks the stairs on the stair clips (50 frames up, 41 down), vaults the wall from a call made
mid-stride, jumps the ditch with no call, keeps the cheer's weight over every walking frame of it, runs round the pillar
turning at up to 3.5 rad/s, and no sole point goes more than 6.4 mm into a solid.

### Seats

robot_body.js: "Normally you call seatOn(vrm, chair, {transition}) which uses [beginSeated] under the hood".

```python
from eidoblend.characters import emotes
z = emotes.seat_on(me, chair, transition='stand_to_sit')   # the pan's height; I am put on its spot, facing out of it
...                                                        # seated until:
body.stand_up('sit_to_stand')                              # the controller's state 'performing' until I stand
body.begin_seated('stand_to_sit', chair=bench, face=0.0)   # walk up to it, turn out of it, back onto it, sit
body.stand_up(None)                                        # the sit-down played backwards
```

`seat_on` on a VRM my body drives takes the engine's cohesive path: it measures the seat (`emotes.seat_plan`: the
pan, the chair's facing from its back, where to stand for the transition's own hip travel to end the hips on the
pan), puts me on that spot facing out of the chair as the JS snaps the VRM and its capsule there (walk me up to it
first: `face_direction` out of the chair, and the snap is what is left), keeps the plan as `body.seat_plan`, and calls
`begin_seated`. My legs then sit down through the controller family's own seat (`emotes.SeatOn` from where I stand:
the hips settled onto the pan and clamped out of it from 40 % of the descent, the backrest kept clear, the feet on the
floor), seated until `stand_up` (`emotes.StandUp`). `begin_seated(slot, chair=...)` walks me to the seat first
(`SeatOn`'s approach: up to it, round it when it is in the way, the turn out of it, a step back onto its spot);
`begin_seated(slot)` alone is the JS's: the seated clip where I stand, the root held (the caller owns the seat), through
`SeatOn`'s plain seat, so my feet go onto the floor and rest there as a chair's do, and `stand_up('sit_to_stand')` takes
the stand-up clip's hip travel as root motion (`StandUp`). In `test_body_api.py` my feet rest within 3.8 mm of the floor
through the hold and one is on it at every frame from my hips leaving the seat to the walk on (the clip shuffles both
while the seat still carries me), my hips move forward with the clip at most 2.1 cm a frame and never more than 0.2 cm
back, and I stand over the spot I sat down from (0.0 cm).

Measured on the keyed, evaluated mesh in `test_body_seat.py`: `seat_on` puts me on its spot to 0.0 cm and 0.0° (the
walk up had left me 26 cm short of it; that is its snap); through each hold my seat skin rests 0.9-1.0 mm over the
pan, my hips over the chair's pan 6.3 cm from its centre (its backrest's bias) and on the bench's centre, and each
foot's lowest sole point 0.0-3.4 mm over the floor; half a second after each stand-up my hips are within 2 cm of my
standing height, and the walks after both resolve. All 38 gait segments of that film pass the controller family's
`checks.feet`. For a film, seat me through `seat_on` or `begin_seated(chair=...)`: the plain `begin_seated(slot)` is
the JS's primitive under them, and on its own it sits on air (put a seat under me).

### Aimed emotes

`set_emote_facing(heading)` aims the standing emotes `perform_action` plays; `None`, the default here, keeps my heading
(the engine's default faces three's `rotation.y` = π, Blender's +Y: `set_emote_facing(math.pi)` for that). Within 15°
of my heading the emote's root
pivots to the aim during its fade-in, the engine's own timing; further, I turn on the spot to it first (the turn
clips), play the emote for its `duration`, and turn back to my own heading after it, unless the next action takes me
elsewhere. My planted feet cannot follow a root that pivots further: right after a walk's stop a 20° pivot turns my
planted foot 4.3° in a frame, 60° slides it 26 mm in a frame, 75° 178 mm (`controller.PIVOT_MAX`).
`test_body_aimed_emote.py` aims a salute 10° to my left and a wave 13° to my right (each pivots: no turn on the spot,
my facing on the aim within 0.0° from half a second in, the planted feet still) and a salute 50° to my left (a 50° turn
on the spot to it, the salute on its aim, the turn back to my heading after it).

### The moves: vault, jump, climb a ledge, climb a ladder

```python
def script(b):
    yield b.walk_to(-4.15, 0.0)                  # up to a low wall (0.8 m), facing it
    if b.vault():                                # True: the move started
        yield b.until(lambda: not b.is_maneuvering())        # (b.wait(seconds) waits a while)
    walk = b.walk_to(0.35, 0.0)                  # past the ditch...
    yield b.until(lambda: b.get_position()['x'] > -1.65)
    b.jump({'distance': 1.4, 'height': 0.45})    # ...jumped out of the stride, the walk going on after it
    yield walk
    ...                                          # b.climb_ledge(): onto the 1 m step ahead
    ...                                          # b.climb_ladder({'height': 1.9, 'rungRadius': 0.016}): up the ladder, over its top
```

The JS passes these to the engine's character controller; here they go to my legs, the controller family's
`VRMCharacterController`: its scan of the colliders ahead along my heading (2.6 m), its clips, its contact IK on the
cover, the lip and the rungs, its pass that keeps a foot out of the face a move climbs. It plays the move from wherever
I am, standing or out of a walk or a run; a route in hand goes on from where the move lands me, and I sense on through
it. Refused, as the engine refuses: nothing the move fits ahead (`vault()` with no cover in the scan's reach); and
while I sit, play an emote or turn on the spot (their clips own the frame).

`test_body_maneuvers.py` runs all four on one course: each starts and plays (vault; jump; mount; ladder and the mount
over its top), the jump called mid-walk, I sense on through each, the refusals answer `False`, and I end on the tower's
top. Every gait there passes the controller family's `checks.feet`; on no keyed frame does a sole point go more than
2.6 mm into the floor, the wall, the step or the tower, and standing each foot's lowest sole point is on what it stands
on (0.0 mm). My hardware's leg clamps come after the controller family's pass that keeps a foot out of the face a move
climbs, and can put the foot back in (over the ladder's top my knee and ankle at their stops held a boot 27 cm into the
tower); through a move the bake pushes such a foot out onto the face along its normal and solves the leg again, and
where the clamped leg cannot reach that far it moves my whole body out (5.4 cm at most on that course).

**My hands hold what the move holds.** My hardware pass rehomes my torso (my single waist joint cannot take the clip's
chest bend), which would swing a planted hand away from what it holds. So the controller family's plant, running my
hardware pass, solves each hand the move holds (the record's `hand_contact` weight: the vault's prop hand, the mount's
hands on the top, the ladder's grips) again from the rehomed shoulder through my arm pass (`dof_pass(reach=)`), over a
few rounds that pre-compensate what my joint clamps and pitch rate take off, and my own passes after it keep those
hands exactly. My shoulder's pitch stage turns 360°/s at most and stops at 60°, so through the vault's plant my arm
lags the hand the controller family puts on the top and then, straight and at that stop, cannot shorten as my body
passes over it: the hand the move holds over the cover (the record's `hand_cover`) is lifted out by my elbow, bent a
little more each try until no point of the hand is under the top, the hand going forward along the top as a planted
hand does when the body passes it. In `test_body_maneuvers.py` my vault's palm comes to 0.1 cm of the wall's top and no
point of my hands goes into the wall; through the ladder's climb the nearer palm is a median 0.6 cm from a rung's
surface; `climb_ladder({'rungRadius': ...})` gives the rungs' real thickness, so my palms close over them. The free
arm the vault raises is the clip's own (Aletheia's vault on the same clip raises it too).

### Seeing what it knows: `RobotDebug`

`RobotDebug(body)` with `show_rays`, `show_map`, `show_path`, `show_landmarks` and `update()` after each
`body.update`, as the JS. A film frame must render alone, so `update()` records what each helper shows at each frame
and `build(rep)` makes one object per helper holding every state with the frames it is shown on, a Geometry Nodes
modifier keeping only the state that holds at the scene's current frame: the sensor rays from my keyed head to where
each really ended, so every hit lies on the surface it found (hits red, misses cyan, opacity 0.6), the occupancy grid as a 2.5D decal at each cell's surface height + 2 cm (free green,
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
bash run_blender.sh blender/tests/robot_body/test_pick_up.py          # renders: one at a time on a shared GPU
#   ... test_navigate_room.py | test_body_route.py | test_body_seat.py | test_body_moving.py | test_body_maneuvers.py
#   ... test_body_aimed_emote.py | test_body_api.py | test_other_vrm.py | test_claude_robot_example.py
#   ... test_crown_head_states.py
#   ... test_pose_bake.py | test_dof_parity.py | test_api_coverage.py
#   --no-render builds, checks and saves only (and lists its stills in out/<tag>_shots.json)
bash run_blender.sh blender/tests/robot_body/render_stills.py route_claude_robot stairs   # those stills, later, on the GPU
```

- `test_pick_up.py` — me picking up a can from a counter, looking it over and setting it back: the fingers touch and
  never pass in, the can moves only in my hand and never into the counter, my hand follows its plan through my
  hardware, the can stands where it was after, both feet on the floor, my eyes on the can and then on where it goes.
  `--side left` uses my left hand on a can before my left shoulder, `--prop carton` a 65 mm square carton; either
  writes `out/pick_up_<side>_<prop>_*`.
- `test_other_vrm.py` — `VRMRobotBody` on Aletheia (a VRM that is not my body): a plain rig, her pose the
  controller's, the JS's head override on her head bone, a walk round a crate, a turn, a look at a lamp and a wave,
  her hair's spring chains baked over the take.
- `test_body_route.py` — down a hall I have never seen and into a room, on my legs: a flight up and down, a low wall
  vaulted from a call made mid-stride, a ditch the controller jumps on its own, a cheer gesture over the walk, a run
  round a pillar, the `controller_opts` reaching the controller, my feet out of every solid, the senses from my head
  and the world they make cast again from my keyed head; `--vrm aletheia` the same course for another VRM.
- `test_body_seat.py` — a chair through `emotes.seat_on` and a bench through `begin_seated(chair=)`: placed as seatOn
  measures, seated on the pan with my feet on the floor, standing up and walking on, the seated frames keyed for the
  audits.
- `test_body_moving.py` — a sliding door that opens and a cart that rolls across my way: the shut door seen shut (no
  path), the open door seen open (the walk goes through), the cart seen and walked round, every hit on them where the
  scene has them at that frame; the view rebuilt only where they moved, and what the cart left in the memory.
- `test_body_aimed_emote.py` — `set_emote_facing`: two emotes aimed within 15° pivot in their fade-in (no turn on
  the spot, the facing on the aim, the planted feet still), one aimed 50° off turns to it first and back after.
- `test_body_maneuvers.py` — down a hall: a vault over a low wall, a jump over a ditch out of a walk, a climb onto a
  step and up a ladder onto a tower, and the refusals; my hands on what the moves hold; its stills show the ladder from
  the step's side, where the tower does not hide it, and the hands up close on the wall's top and on the rungs.
- `test_crown_head_states.py` — the presets: each of the ten `CROWN_STATES` (with its `HEAD_STATES` pose where there
  is one) held in turn through the frame order, every petal at its state's fold inside its stops, the head at its
  state's pitch, roll and pan, the actuators at their rates; my head rendered in each.
- `test_navigate_room.py` — me crossing a room I have never seen to a goal behind a partition, a crate out of sight
  until the doorway: I scan, plan, replan on what I see, arrive, look at a lamp and wave. Its checks: arrival, a replan
  on sight, the memory on the real walls (100 % of blocked cells within 0.15 m of a surface), my clearance from every
  solid (0.39 m), planted feet and the turn rate, the gaze, the senses from my head.
- `test_body_api.py` — every other action and query: the look-ats, a 90° turn on the spot, a two-pass scan, a run
  to a corner short of a pane (no move for what lies past the goal), a salute aimed at the camera, walking to a
  landmark, the JS's rejections (an unknown landmark, an unknown clip, a stop, a collision stall on a pane the sensors
  cannot see and the controller cannot climb), the JS's plain beginSeated and standing up (my feet on the floor
  through the hold and one on it from my hips leaving the seat to the walk on, the stand-up clip carrying my hips
  forward to stand over the spot I sat down from).

Their stills are strips: a low camera beside each walk's start and stop, each turn on the spot, each move, each
sit-down and stand-up, held over it and every two or three frames (`_stage.side_view`: square to the travel, 45 cm
over the ground under the camera, on the side with room, the debug overlays left out of them).
- `test_claude_robot_example.py` — the WebGPU example, whole; `test_dof_parity.py` — `robot_dof` against the JS;
  `test_pose_bake.py` — the bake files both ways; `test_api_coverage.py` — reads the JS sources and finds every public
  name's counterpart here (46 methods of `VRMRobotBody`, 22 members of `EidoverseRobotController`, 14 of
  `RobotDebug`, the 28 exports of `claude_robot_dof.js`, `pose_bake.js` and its bake object).

Each writes `out/<test>.json` (the report and its PASS / FAIL checks), its `.blend` and its stills.

## Not yet ported

- **An aimed emote turned further than 15° from my heading** turns on the spot first instead of pivoting during its
  fade-in (above: "Aimed emotes"), so its `duration` starts after the turn where the engine's starts at the call: my
  planted feet slide or turn under a root that pivots further (20° turns a planted foot 4.3° in a frame, 75° slides it
  178 mm), and the film's plant keeps planted feet where they stand rather than stepping them round a pivot.
- **A walk that sets off far off my heading turns on the spot first** (more than 25°; 60° on any other VRM), where the
  engine sets off at once and turns at 3.5 rad/s as it walks: the controller family's `FollowPath` turns first so the
  foot I stand on as I set off is not twisted round (my hip's yaw ring turns a planted leg at most ±40° about its
  axis); a replan or a corner on the way turns as the engine does.
- **My head's height in the senses.** I sense from my head as the live run has it; the film's plant then sets my
  pelvis from my planted legs over the whole take, after the run (it needs the frames ahead to put a foot down), so
  my keyed head stands that much higher or lower than the one I sensed from (across, 0.0 mm): up to 7.8 cm in
  `test_navigate_room.py`, 21 cm on the stairs down in `test_body_route.py` (the plant's dip stepping off a flight:
  [controller](controller.md#not-yet-ported)). Cast again from my keyed head after the bake, that run's 243 senses
  make a memory that differs from the live one in 326 of its 10,176 known cells (3.2 %), and the planner's route
  through it is the same route.
- **The controller family's residuals on my body** are its own ([controller](controller.md#not-yet-ported)): in
  `test_body_route.py`, walking up the flight at an angle the planner chose, the stair clip's last stance hands over
  to the walk's with a planted foot turning 11° in a frame; a run's stance rocks 2.9 mm (the check's limit is 2.5).
- **The planner and the controller's reach.** By default the planner routes round anything more than 0.4 m above or
  below the floor it stands on (the JS's); with `max_step_height` raised to the controller's reach it crosses low
  cover and ditches, at no extra cost: it may then route over a table rather than round it. It never routes across a
  drop deeper than the memory's `cliff_threshold` (1 m), however narrow.
- **What a moving thing leaves in the memory.** The memory keeps what it saw where it saw it until the sensors see
  that place again (the JS's memory): at the end of `test_body_moving.py`, 18 of the 156 cells the cart stood and
  rolled over still hold its top's height (0.9 m, seen while it stood: a ledge to the planner), none of them blocked;
  the walk went round them.
- **My hands arrive late on the vault's top and the ladder's first rungs.** On the vault my shoulder's pitch rate
  (360°/s) holds my arm behind the hand the controller family reaches out (up to 48 cm off it on the way down), so my
  hand lands on the top a few frames after a human's; in the first five frames of the ladder's climb my hands are still
  reaching for the rungs, the nearer palm up to 9 cm off one (6.1, 3.3, 9.1, 1.0 and 3.5 cm; within 1.5 cm from then
  on), so nine in ten of the climb's frames are within 3.4 cm, not 3 (`test_body_maneuvers.py` reports it as its FAIL).
- **My seats' residuals.** Sitting on the ground I do a long sit, my legs out along the floor (my hips flex 98° at
  most and my knees 112°, so I cannot fold into the library's cross-legged clip), my heels resting on it; my boots and
  arms stay out of the floor through the sit-down, the hold and the rise, lying down too
  ([maneuvers](maneuvers.md#not-yet-ported)). My ankle has no twist, so in a chair a resting foot turns with my shin.
- **My eyes on my left hand's work.** Picking up with my left hand my eyes come within 5.2° of the can as the reach
  starts and of the set-down place (`test_pick_up.py --side left`'s FAIL: its bar is 5°), where my right hand's are
  within 4.2°: as the reach starts my head alone would be 30° off the can (26° for my right hand's), its nod at its
  30° stop, and my eyes' look range does not take all of the rest. `pick_and_hold` plans upright props (round or
  flat-sided); props lying down, handles and two-handed carries are not planned.
- **Moving colliders.** My legs walk against the colliders made at `create`, as the JS's Rapier world is built once: a
  door or a cart that moves is seen and planned round, never walked against.
- **`VRMUtils` merging** (fewer skinned draws for three's renderer) and the Rapier world itself do not apply in
  Blender: the collision world is a BVH.

— Claude (Opus 5.5), with Skye
