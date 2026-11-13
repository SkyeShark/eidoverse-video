# The character controller — locomotion for film (Blender edition)

[Main instructions](../AGENTS.md) · [Characters](characters.md) · [Blender](blender.md)

This is the Blender 5.2 EEVEE edition of `eidoverse/character_controller.js`
(`VRMCharacterController`) and `eidoverse/foot_ik.js` (`VRMFootControllerIK`).
The package is `blender/eidoblend/characters/controller/`; names follow the
WebGPU API in snake_case (`attachLocomotion` → `attach_locomotion`,
`feetWorldPosition` → `feet_world_position`, `footStanceX` → `foot_stance_x`,
`MaxStepHeight` → `max_step_height`), defaults unchanged. Blender is Z-up,
metres; three `(x, y, z)` is Blender `(x, −z, y)`. A heading is the same number
as three's `rotation.y`: 0 faces −Y (a VRM as imported), π faces +Y (the
WebGPU default, the course's direction).

**The one rule that differs from the WebGPU edition.** In the browser the
controller runs every frame while the scene renders: Rapier moves a cylinder,
probes the ground, the mixer blends the clips, the foot IK grounds the feet.
Here the same controller runs **once, frame by frame, at build time**, its
every frame is recorded, the feet are planted over the whole run (the film
bake), and the armature is **keyed**. A saved `.blend` plays and renders any
frame on its own; nothing runs at render time.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import math, bpy
from eidoblend.characters import load_vrm
from eidoblend.course import build_course, PRESETS
from eidoblend.characters.controller import CollisionWorld, Locomotion

bpy.context.scene.render.fps = 30                       # before any clip: the importer keys at the scene's fps
build_course(PRESETS['stairs_pyramid'])                 # or any meshes: the controller casts against what is there
me = load_vrm('claude_robot')
walk = Locomotion(me, CollisionWorld(), start=(0, -5, 0), heading=math.pi)
walk.wait(0.6)                                          # idle
walk.move_to((0, 13.0))                                 # accelerate from standing, up 20 stairs, over, down, stop ON the point
walk.turn_by(90).follow_path([(-3, 13), (-3, 16)], gait='run')   # a turn on the spot (+ is left), a run around a corner
rep = walk.bake(f0=1)                                   # simulate, plant the feet, key one action
print(rep['segments'])                                  # which gait led which frames, checks.feet on each
```

## The three layers

| Layer | Module | What it is |
|---|---|---|
| the controller | `controller.py`, `maneuvers.py` | `VRMCharacterController` ported line for line: the cylinder's move and slide, the ground probes, stair and ramp classification, the gait tree's weights and speeds, the stair phase lock, hip lean, head pitch, body drop, the IK's contexts, emotes, gestures, seating, the maneuvers and their contact IK |
| the film bake | `plant.py` | the feet planted over the whole recorded run: no slip, sole on the ground, swing clearance, the pelvis from the planted legs |
| directing | `film.py` | `Locomotion`: a queue of commands (`move_to`, `follow_path`, `turn_to`, `emote`, `sit` ...) that steers the controller the way the robot adapter does, then bakes |

Underneath: `world.py` (`CollisionWorld`, the Rapier stand-in: ray casts,
ball casts, the cylinder's move and slide, over a BVH of the scene's meshes),
`mixer.py` (three.js's `AnimationMixer`: weights, fades, loops, blend order),
`clips.py` (the clip library stripped as the controller strips it, and each
clip measured on the body that plays it), `pose.py` (one frame's scene graph),
`foot_ik.py` (`VRMFootControllerIK`).

## Directing a take — `Locomotion`

```python
walk = Locomotion(me, world, start=(x, y, z), heading=math.pi,
                  preset='robot',           # the controller's options: 'robot' (robot_controller.js: defaults, turning
                                            # on) or 'terrain_base' (the WebGPU locomotion bench's IK contact lifts)
                  gait_sync='distance',     # distance matching ('stride': the original's timeScale = speed / native)
                  leg_ik='default',         # terrain_base.js's VRMFootControllerIK set-up, or None, or your own
                  controller_opts={...}, locomotion_opts={...})   # any constructor / attach_locomotion option
```

Every command queues and returns the `Locomotion`, so they chain. `bake()` runs
the queue.

| Command | What it does |
|---|---|
| `wait(s)` | stand (the idle) for `s` seconds |
| `move_to(p, speed=None, gait=None, stop=True)` | walk or run to `p` (world x, y): accelerate from standing, decelerate to stop **on** the point; `stop=False` carries on into the next command at speed |
| `follow_path(points, ...)` | the same along a polyline; corners rounded into arcs of radius speed / max_turn_rate, followed by pure pursuit 0.6 s ahead |
| `run_to(p)` | `move_to(p, gait='run')` |
| `turn_to(deg)`, `turn_by(deg)`, `face(p)` | turn on the spot (turnLeft / turnRight, the root taking the clip's own hip yaw scaled to the angle; over 1.1 × the clip's turn it is split, the parts crossfaded; under 20° a settling turn). The feet step round: one is always down |
| `emote(slot, seconds=None, facing='keep', stop=True)` | `playEmote` (locomotion suspended), then `stopEmote`; `facing` a heading in degrees, `'keep'`, or `None` for the WebGPU default (three's π). `stop=False` never calls `stopEmote`, as a scene that plays an emote and leaves it on: after `seconds` the clip holds its last pose, facing where it played, through the commands after it (the course example's finale salute) |
| `gesture(slot, weight=2.5)` / `stop_gesture()` | `playGesture`: the upper body plays the clip over whatever the legs do |
| `sit(hold=2.2, seat=None, clip='stand_to_sit', reverse=True, reverse_speed=1.25)` | `beginSeated` where the body stands, hold, `endSeated` (reversed, as the course example does), `stopEmote`; `seat_spot(seat_xy, heading_deg)` says where to stand so the clip's own hip travel ends over the seat. `seat=` the seat object: `seatOn`'s settle, the held seat measured on the posed skin with the feet set down where the bake plants them, and the body raised or lowered so its underside rests on the pan, whatever the seat's height; and `seatOn`'s clamp: from 40 % of the clip on, sitting down and (reversed) standing up, the body is never lower than keeps its underside on the pan. The feet stand on the floor under it. `reverse=False` stands up on `stand_clip` (sit_to_stand) played forward, its hips' travel taken as root motion (`stand_clip_travel`, `stand_shift`, which `emotes.StandUp` shares): the hips stay on the seat through its crossfade, step forward with the clip and end over the spot the sit began from. The walk after a sit goes on at the seat's heading, whatever facing an earlier emote asked |
| `vault()`, `climb_ledge()`, `jump(distance, height)`, `climb_ladder(height)`, `climb_wall()` | the explicit moves from where the body stands, facing its heading (the auto-trigger does the vault, the mounts, the scramble and the gap jump on its own along any path); each lasts while the move and anything it chains are in flight |
| `steer(fn, seconds=None, speed=None, gait=None, stop=True)` | the body steered frame by frame from scene logic, as a WebGPU scene's `renderFrame` called `locomote(dt, input)`: `fn(t, ctrl)` returns a direction of travel (world x, y; its length, at most 1, scales the pace), `(0, 0)` to stand, `None` to end; `t` is the command's seconds, `walk.frame` the frame being simulated |
| `follow(target, distance=1.0, speed=None, gait=None, seconds=None, bone=None)` | keep `distance` from a keyed object (another character's armature or one of its bones, a vehicle, an empty), reading where its keys put it at each frame: walk after it, run while it goes faster than the run threshold, and stop `distance` short of it wherever it stops |
| `set_running(v)`, `call(fn)` | the controller's running flag; any function of the controller, in order (`call(lambda c: setattr(c, 'auto_maneuvers', False))` near a bench) |

**Gaits.** `gait=` names one of `GAITS`, or leave it out and give `speed`: at
or over halfway between this body's native walk and run speeds it runs.

| `gait` | the controller plays | pace |
|---|---|---|
| `'walk'` | walk (and stairsUp / stairsDown on stairs) | the walk clip's native pace on this body |
| `'run'` | run (stairsRunUp / stairsRunDown on stairs) | the run clip's native pace |
| `'slowRun'` | run | 0.8 × the run's pace (the library has no jog clip: the run's cadence slows, the stride stays) |
| `'fastRun'` | run | 1.25 × the run's pace |
| `'walkBackward'` | walk, run backward under the travel | 0.6 × the walk's pace; the facing turns away from the travel |

The pace a clip has **on this body** is measured (the clip's stride on these
legs over its duration): Aletheia walks 1.46 m/s and runs 3.06, my robot body
1.51 and 3.15, the claudesona 1.33 and 2.67. The WebGPU numbers (1.5 / 3.6)
were tuned on Aletheia and are still the controller's defaults when it runs on
its own; `Locomotion` passes `native_walk_speed=None` so they are measured.

Speeds: an acceleration from standing (walk 1.8, run 3.5 m/s²) and a
deceleration that stops on the point (v² = 2ad; walk 2.2, run 4.0), so a
start reads as one and a stop lands within ~3 cm. A run slowing under the run
threshold finishes as a walk. A landing (fallLand) stops the body and the
command walks off again from standing. A walk that sets off more than 60°
off the body's heading turns on the spot first (25° on my robot body: its
hip turns a planted leg at most ±40° about the leg's axis).

### Steering from scene logic — `steer`, `follow`

```python
def chase(t, ctrl):                                    # any function of time: a heading from other animation, a path,
    if t > 6.0:                                        # a reaction to the scene
        return None                                    # None ends the command
    a = math.radians(30) + 0.9 * math.sin(2 * math.pi * t / 5)
    return (math.sin(a), -math.cos(a))                 # a direction of travel; length 1 = the pace, (0, 0) stands
walk.steer(chase, speed=1.4)                           # speed= / gait= as follow_path (a walk at its own pace by default)

walk.follow(cart, distance=1.8)                        # a keyed object: its place read through its keys at each frame
walk.follow(other, distance=1.2, bone='hips')          # another character's take (its VRM handle, baked first), its hips
walk.follow(drone, distance=3.0, seconds=8.0, gait='run')
rep = walk.bake()                                      # planted and keyed like any command
```

`steer` takes the direction a function gives each frame and moves the body
at the gait's pace times its length, reached with the walk's (or run's)
acceleration and left with its deceleration: a function that jumps from
standing to full speed starts as a walk starts, and the end (`None`, or
`seconds` over) slows to a stand along the last direction, its stride spread
over the ground the slowing covers. A first direction more than the turn
threshold off the body's heading from standing turns on the spot first, as
`follow_path` does; `t` runs on through that turn. `follow` is `steer` with
the function written for you: each frame it reads the target's place at this
frame and the next (`KeyedPlace`: the depsgraph, a batch of frames at a time,
so constraints, parents and drivers count), heads for where the target will
be 0.4 s on, at the target's speed away from it plus 0.8 /s of the distance
it has fallen behind, never faster than a stop at `distance` allows (v² = 2ad)
and never faster than `speed` (default the run's pace). With no `gait` it
walks, runs while the speed it needs reaches the run threshold, and walks
again under 0.8 of it. `seconds=None` follows until the target's last key has
passed and the body stands at its distance. In
`test_controller_follow.py` Aletheia keeps 1.75-1.84 m behind a cart rolling
at 1.5 m/s (her distance 1.8 m), stops 1.70 m and 1.61 m behind its two
stops, runs while it races at 2.8 m/s, and steers through a slow S within
4.3° of its function's heading (90th percentile), every gait's feet planted.

### Springs ride the take

`bake()` ends with the VRM's spring chains (hair, tails, tentacles, a coat's
tails) simulated over the keyed take and keyed on their own NLA track
(`walk.bake_springs(rep)`; `characters.springs.bake_springs`, the
`claudesona.md` guide's solver, three-vrm's maths): the engine stepped them in
`vrm.update(dt)` every rendered frame, after the body's pose, and here they
follow the same frames in order, so a walk's start trails them, a turn swings
them round, a stop throws them forward and a seat or a lie-down settles them.
The take's action keys no spring bone, so nothing fights the track.

- They start settled on the take's first pose (`preroll`, 1 s held).
- They rest on the walkable world (`ground=`, the take's `CollisionWorld`):
  lying down, a tail lies on the floor instead of hanging through it.
- They stay out of every solid in the scene that stands still (`solids=`,
  every visible mesh no armature deforms and nothing keys, drives or
  constrains, seats included): no joint of a chain crosses a face, so a tail
  hanging behind a chair drapes over its pan rather than through its back.
  A moving object (a cart she follows) is left out: the solids are one
  shape for the whole take.
- Where the take's root jumps (a teleport, an instant seat:
  `film.take_resets`, faster than 25 m/s or turned more than 90° in a frame)
  they are reset, `springBoneManager.reset()`, and settled on the new pose
  for the preroll's time, so a cut opens on them hanging. The engine also
  reset them at a seat's settle, where it teleported the body onto the pan;
  here the settle is eased over the descent, so the chains swing on through
  it.
- `bake(springs=False)` leaves them out; a dict passes `bake_springs`'
  options (`{'preroll': 0.0}`, `{'solids': None}`, `{'solver': 'addon'}`). A
  body with no spring chain (my robot body) is left alone. `emotes.bake`
  bakes them after its seated keys.
- Each take's springs are kept under the take's own name
  (`'<take action>|springs'`); the track plays the last take baked, and
  `characters.springs.use_springs(me, '<take action>|springs')` puts an
  earlier take's back beside its action (the controller tests' shot
  renderer does, shot by shot).

`test_take_springs.py` (`blender/tests/characters/`) runs a walk, a turn, a
run's stop, a chair and a lie-down on Aporia and on Aletheia: each group's
moving points travel against the hips while the body moves (Aporia's
tentacles 1.1-1.5 m/s on average, her hair 0.16-0.46) and settle once she
stands; lying down, no chain goes under the floor; seated, none goes into
the chair.

```python
rep = walk.bake(f0=1,
                feet='plant',            # the film's planted feet; 'foot_ik' keys the WebGPU per-frame IK as it is
                pelvis='stance',         # the hips from the planted legs; 'controller' keeps the controller's height
                clearance=0.03,          # the swing sole's least height over what it sweeps, mid-swing
                springs=True,            # the spring chains over the keyed take (below); False, or bake_springs' options
                key=True, check=True, action_name=None)
rep['segments']          # [{'gait': 'stairsUp', 'frames': [287, 327], 'checks_feet': {'ok': True, 'failures': []}}, ...]
rep['worst']             # slip, drift, gap, swing clearance, ankle misses over the whole take
rep['springs']           # bake_springs' report (None: no chains): joints, keys, resets, ground_frames, nan
rep['_records']          # every frame: root, pose, weights, stance, support mode, climb angle, speeds, the probes' verdict
```

What the film bake decides, frame by frame over the recorded take:

- **The stance** is each playing clip's measured stance, blended by weight.
  A foot the clip plants past an edge (the ground under it more than 0.45 m
  below the body's support) is not planted: it swings until the body falls.
  Idle, the emotes and a seat stand on both feet. Neither foot down is a
  flight only where a gait that has one leads (run, the running stair clips,
  fallIdle); anywhere else the report lists those frames as airborne and
  checks.feet fails them. A swing of two frames between two stances is a
  crossfade's noise where the foot lands back where it stood (within 8 cm):
  the foot stays down. One that carries the foot on (a stair clip coming in
  with that foot's next stance a step ahead) is a step: it starts earlier,
  to last 4 frames, while the other foot stands.
- **Planted feet** do not slip or turn on the ground; a landing slides along
  the foot (at most 12 cm, never onto ground more than a stair's rise below)
  onto the support, and so that no part of the boot is inside a riser (a
  descent's heel against the step behind it); the sole tilts onto the
  ground's plane; the toes stay flat through the roll. A planted foot keeps
  the surface it landed on: a tread's level (a heel that creeps over a higher
  edge tucks into it rather than lifting the foot onto it), a ramp's incline,
  or over a smooth curve (a dome, a boulder) the curve itself, and never more
  than 5 cm under the ground it landed on. A stance whose sole reaches into a
  riser or a dome's side in any of its frames is moved along the travel, as
  little as clears every frame (at most 6 cm), and kept only where the
  stance then holds as well as it did. The first stance after a seat starts
  where the seat left the foot, its place and heading. A foot's
  heading is read from its forward and up vectors together, in the frame of
  the ground it stands on, steady from heel strike to toe-off on a cross
  slope too. My robot body's ankle rolls 14.9° at most, short of a steep
  cross slope: a planted foot on ground tilted across it more than 8°
  (`ROLL_SLOPE`) whose ankle meets that stop gets one roll off the ground
  for its whole stance, the most its solved legs need in its flat part
  (`_stance_rolls`, a quarter to 45 % of the stance; a turn's or a stop's
  short step from a quarter to its end), so its sole stands on its edge and
  does not roll on the ground as the shin moves over it. On level ground
  nothing is rolled.
- **Load by reach.** Each planted leg carries the body's load by how far its
  foot stands from its hip along the ground: all of it within `TRAIL_FULL`
  (0.55) of the leg's reach, none past `TRAIL_NONE` (0.85) (`plant.py`). A
  foot the body has walked on from, past `TRAIL_NONE` or behind the hip and
  reachable only with the pelvis more than `TRAIL_DIP` (0.25 m) under the
  controller's own height, neither pulls the pelvis down nor caps it, and is
  let go there (an early toe-off). A stance the walk (or the run) has
  already ended, held on only by a stair clip blending in (a step up onto a
  low block: the stair clip's long stance keeps the walk's trailing foot
  down after the walk has lifted it), is let go sooner, so the hips stay at
  the walk's height into the step: past 70 % of it (`TRAIL_LATE`), in a
  forward walk that still carries a quarter of the weight
  (`TRAIL_GROUND_SHARE`) with a stair clip holding at least 15 % of it
  (`TRAIL_STAIR_SHARE`), once the other foot has stood three frames
  (`TRAIL_DOUBLE`: the weight crosses first), a trailing foot goes where
  the pelvis would come more than 12 cm (`TRAIL_DIP_LATE`) under the
  controller's. At a stop the idle coming in holds both feet down, and the
  trailing foot stays planted through it. On a 45° ramp, where the stair
  clip leads, the long trailing stance is the climb's own and stays. Where
  the other foot is still in its swing then, that swing is brought forward
  to land by then: its own motion relative to the body, played faster (a
  quicker step), so a walk keeps a foot down. A stair clip's bent stance
  knee on a foot the body has already walked away from therefore never
  drags the hips toward the floor.
- **A foot out of reach** at the end of its stance (the trailing foot on a
  stair, the hips already risen) is let go early, but not while the other
  foot is in the air: until the other lands, the pelvis comes down to it.
  Down stairs the trailing foot, above the hips' reach, leaves before the
  other lands. A seat's stance (`sit`'s seated frames) is never let go
  early: its feet stay on the floor through the hold and the rise.
- **Swinging feet** follow the clip's own arc over the line between the two
  plants, never closer than `clearance` mid-swing to the highest ground they
  sweep, and never in contact while they travel faster than 0.8 m/s (a
  toe-off, a backward walk's lift). A swing that ends in a fall or a
  maneuver hands its foot to the clip by then.
- **The pelvis** goes where the loaded legs have the clip's own length,
  capped so every loaded leg reaches (the presets test checks it never sinks
  more than 30 cm under the controller's height). `pelvis='controller'` keeps the
  controller's height, capped for reach and floored where a planted leg is
  folded to its knee stop. A seat's pelvis is the seat's (the controller's
  root, settled onto the pan with `seat=`).
- **Falls and maneuvers** leave the feet to the clip (a maneuver's contact
  IK has placed them) and the root to the controller exactly (the maneuver's
  path: no smoothing reaches into it); a landing (fallLand) stands where it
  landed. A foot the move hands back still in the air, or still turning as
  the move fades out, ends its swing first: it is planted once the blend sets
  it down (its sole within 1.5 cm of the ground and turning under 3° a
  frame), within 6 frames and while the other foot stands; where the blend
  does not set it down in its stance (a running jump's landing, the run
  lifting that foot again) it is planted at the hand-over. So a vault's
  landing foot, still turning as the move fades out, is planted once it has
  come down flat, and then holds.

`feet='foot_ik'` is the WebGPU behaviour exactly: the IK follows the animated
foot's xy, so wherever stride and travel differ (a start, a stop, a turn, a
stair the clip was not made for) the planted foot slides; on the small stairs
of `test_controller_foot_ik.py` its planted feet move about 30 mm a frame at the
95th percentile, the plant's under 0.1 mm.

## The controller — `VRMCharacterController`

You rarely build it yourself (`Locomotion` does), but every option of the
original is there:

```python
from eidoblend.characters.controller import VRMCharacterController, CollisionWorld, CONTROLLER_PRESETS
c = VRMCharacterController(me, CollisionWorld(), start_position=(0, -5, 0), start_heading=math.pi,
                           enable_turning=True, **CONTROLLER_PRESETS['terrain_base'])
c.load_standard_animations()                      # walk, run, idle, the four stair clips, fallIdle, the maneuver clips
c.attach_locomotion(leg_ik='default', flat_speed=1.5, gait_sync='stride')
for f in range(300):
    c.locomote(1 / 30, (0.0, 1.0))                # a direction of travel (world x, y); its length scales the speed
    c.pose                                        # the frame: root matrix + normalized bones (pose.Pose)
    c.support_frame                               # the original's supportFrame: probes, terrain, body, animation
```

`update(dt, velocity)` is the physics step alone (the cylinder, the probes,
the body's height); `locomote(dt, direction)` is the whole frame;
`place((x, y, z), heading)` puts the feet there at once, standing (the
engine's teleport: the Rapier body's translation set, the VRM moved). What the
probes say is on the controller as the original exposes it:
`ahead_step_like`, `ahead_smooth_ramp_like`, `ahead_stair_shape` (small /
normal / large), `ahead_tread_run`, `ahead_highest_delta` /
`ahead_lowest_delta`, `signed_climb_angle_deg`, `speed_scale`, `grounded`,
`ground_y`, `small_stair_ascent_early_up` ...

**The gait tree** (attachLocomotion's defaults): idle when the body moves
under 0.3 m/s; walk on the flat and on ramps up to 8°; stairsUp / stairsDown
when the probes find stairs (one to three edges of 7.5 cm or more within
0.35 m, the rest smooth), on climbing ramps steeper than 8°, or when the body
rises or falls faster than 0.4 m/s; fallIdle in the air. Walking on stairs
the speed becomes 2 × tread run × stairCadence (2.5) / the stair clip's
duration, so one cycle covers two treads (running: stairCadenceRun 1.4);
large risers up scale it by 0.58. On any climb the body slows: 1 at 5°,
0.55 at 30° (`speed_scale`). Isolated obstacles (a bump with an edge up and
an edge down) keep the walk.

**Distance matching** (`gait_sync='distance'`, `Locomotion`'s default): walk
and run share one gait phase, advanced by the ground covered over the blended
stride (and through the clip's own travel table when one clip leads), aligned
on the left strike, so a planted foot moves with the ground at any speed. A
start from standing begins just before a passing phase; a stop spreads the
remaining phase over the remaining distance so it lands on one. The stair
clips lock their phase to the treads (the original's small-stair phase lock,
here for every shape, both ways). An edge fixes the phase to one tread, half
the stair cycle, which leaves two halves: which foot takes the next tread.
The lock takes the half whose phase is nearest the walk's where the stair
clip takes over the blend (its share past a half), the stair clip going on
at the tread's pace until then and the walk at the blend's. A new estimate
of the tread's run on the flight keeps the phase where it is. A stair clip
that is not playing is held at the shared phase, so it comes in where the
walk is in its cycle (on rolling ground, where no tread locks it, too). While the stair
clips carry weight the shared phase goes on at the weight-blended pace of
every clip playing (a stair cycle is two treads, the walk's stride two to
three times as long), so the walk's steps quicken as a flight takes over;
off a flight the stride grows back to the walk's or the run's at
`STRIDE_GROWTH` (1.5 m of stride per metre walked), so the first step off
the stairs is as short and quick as theirs and the next is the gait's own.
Once a stair clip leads and the walk and the run have faded under 10 %,
their shared phase follows it, so a hand-back from the stairs (the top of a
flight, a dome stepped onto) re-enters the walk with the same foot down.
(Following earlier, mid-crossfade, would jump a walk that still carries
weight.) `gait_sync='stride'` is the original: `timeScale = speed /
nativeSpeed` (capped at 1.4).

**This edition's additions**, each an option that is off unless asked
(`Locomotion` turns the first three on), except the maneuvers' last pass and
the probes under what is overhead, which are on:

- `gait_sync='distance'` (above) and `native_*_speed=None` (measured).
- `land_on_contact=True`: a falling body lands when its feet reach the
  ground. The original regains the ground 0.4 m above it (fall_threshold) and
  floats the rest down at the body-height rate cap, its feet in the air; so
  it plays fallLand only for drops over 1.25 m (0.85 + 0.4). It applies to a
  body already in the air: one walking down a slope keeps the original's
  threshold.
- `ground_past_steep=True`: a support probe under the feet whose ball first
  touches a face too steep to stand on (a dome's or a boulder's far side)
  looks past it, down a ray, to the first walkable surface (a step down). The
  original finds no ground there and the body takes off: over the stress
  course's 35 cm dome, a hop into fallIdle. The probes ahead keep the
  original's answer (read past, a ramp box's steep front edge is a step).
- `ground_under_overhead=True` (on unless turned off): every downward probe
  (the feet's, the ones ahead, the maneuvers' scan of the path ahead) looks
  under a surface it meets higher over the feet than the body is tall, where
  the room under it fits the body standing (its height and 5 cm,
  `OVERHEAD_ROOM`): a doorway's lintel, a ceiling, a beam or a deck the body
  walks beneath. The original drops its probes from 3-5 m over the body and
  reads the top of whatever is over the head as the ground ahead: a lintel in
  the colliders started a wall scramble in its doorway. A beam too low to walk
  under, a block sunk into the floor and two blocks built against each other
  are still climbed (`CollisionWorld.underside`, `inside_solid`); where nothing
  hangs over the head it changes nothing.
- `turn_on_spot(angle)`: turnLeft / turnRight played with the root taking the
  clip's hip yaw (the original never plays them); a turn straight after the
  same turn crossfades from a twin action of the clip. The library's turns
  shuffle (a stepping foot rises 1-4 cm, the planted one pivots with its
  ankle circling the ball at 0.2-0.3 m/s), so a foot steps where it rides
  6 mm or more over the other while it moves, or sweeps faster than 0.55 m/s;
  elsewhere it is planted and pivots, and one foot is always down.
- `maneuver_feet_out_of_solids=True` (on unless turned off) and
  `contact_world`: the maneuvers' last pass (below).
- `backward=True`: the facing turns away from the travel and distance
  matching runs the walk clip backward.
- `max_slope` reaches the cylinder's move and slide (the original's
  `setMaxSlopeClimbAngle`): a surface steeper than it is a wall.

**Presets.** `CONTROLLER_PRESETS['robot']` is what `robot_controller.js`
builds (the defaults, turning on). `CONTROLLER_PRESETS['terrain_base']` is
what `terrain_base.js` builds for the locomotion bench and the obstacle course
example: the contact-support lifts from the feet's probes and the IK's
contacts, raised support during descents, the IK grounding grace, untreaded
obstacles walked, body-height rates 1.35 / 1.25 m/s, a 3-frame height window.
It also passes `requireConfirmedStairClips`, which only `attachLocomotion`
reads: unread in the original, unread here (pass it to `attach_locomotion`).

**Emotes, gestures, seating.** `load_emote(slot, loop=True)` /
`play_emote(slot, fade_in=0.2)` / `stop_emote(fade_out=0.3)`: a full-body clip,
every track kept, locomotion suspended while it plays (`is_emoting`).
`load_gesture` / `play_gesture(slot, weight=2.5)` / `stop_gesture()`: the
upper body (spine to fingers) only, blended over the gait at its weight (2.5
means it takes 71 % against the gait's 1). `begin_seated(slot)` /
`end_seated(slot, reverse=..., reverse_speed=..., release_at=...)`: the
seated clip on the controller's mixer while the root holds, raised by
`seat_dz` (the film's `sit(seat=...)` sets it: `seat_gap()` measures the held
seat's underside on the posed skin over the pelvis and thighs, the mesh that
sits tightest round the thigh bones, so a coat's hem or a tail hanging
through the pan is not what rests on it; `world=` sets the feet down first
where the bake plants them, `planted_legs()`, since a foot pushed up onto
the floor raises its knee and turns the thigh under the pelvis down into the
pan; `t=` measures the clip at that time, which the clamp reads every frame
from 40 % of the clip on). Every loader takes
`vrma_library={slot: path}` (the original's `vrmaLibrary`). Aimed at scene
objects, and seats for a walking body: [maneuvers.md](maneuvers.md).

**Maneuvers** (`maneuvers.py`). While the body walks or runs, the controller
scans the path ahead (`_scan_path_ahead`: probes every 15 cm to 2.6 m),
classifies one obstacle and one gap (`_classify_path_ahead`) and starts a move
when one is close enough (`_maybe_auto_maneuver`): **vault** cover up to
1.15 m high and 1 m deep with a landing beyond, **mount** (climbLedge) a block
to 1.35 m, mount (climbWallUp) to 2.3 m, the **wall scramble** to 4.5 m (the
climbWallUp cycle looped, then the mantle), the **gap jump** to 2.2 m wide.
They can also be asked for:

```python
c.vault(); c.climb_ledge(); c.jump(distance=1.4, height=0.45)
c.climb_ladder(height=2.5)        # the climbLadder loop up the rungs, chained into the mantle over the top
c.climb_ladder(height=2.5, standoff=0.3)    # the hips 0.3 m behind the rungs' line (default ladder_standoff)
c.climb_wall()                    # the wall scramble
walk.climb_ladder(height=2.5)     # the same as film commands (they last while the move and its chain fly)
```

Each move is a root path the body follows while a window of its clip plays:
the vault and the mount fit the clip's **own hips curve** (its root motion,
extracted before the strip) to the obstacle; the jump and the climbs use
keypoint arcs. A contact IK then pulls what should touch onto the geometry
while the clip keeps the motion. Where the original's constants or partial
weights left a body that does not touch what it climbs, this edition measures
on the body and the clip instead:

- **The vault** plays the clip from its own take-off to its landing
  (`vault_window`, measured on the clip's feet; the original's fixed window
  0.20 to 0.62 starts at the library clip's peak, so the rise it fitted was
  nothing and the body crossed flat, stepping onto the cover). Its hips curve
  rides over the line from take-off to landing, scaled so the tucked feet
  clear the top by 6 cm wherever they are over it, the crouch at either end
  kept so the legs reach the ground. The prop hand plants its palm flat on
  the top at full weight: turned palm-down, the skin under its knuckles on
  the top, the wrist where that hand puts it (the original aims the wrist
  2 cm over the top, and the clip's hand, pitched fingers-down there, ran
  Aporia's fingertips up to 13 cm into the course's covers). My robot body's
  hand keeps the clip's turn there, the wrist 2 cm over the top (its wrist
  bends back 70° at most: asked for a flat palm, its hardware turned the hand
  about the wrist and left its fingertips 12.7 cm in the top). Its contact is
  latched where it first reaches; where the arm alone
  cannot reach (low cover, the body high enough for its legs to clear it)
  the spine leans the shoulder down to it (`lean_to_reach`). It takes hold
  over 15 % of the move (`VAULT_HAND_IN`: at once, the hand jumped 32 cm onto
  the top in a frame) and lets go over the next 17 % (`VAULT_HAND_OUT`),
  rising 15 cm off the top as it does (the original's hold ends in one
  frame, and the clip has flung that hand up by then: a 58 cm pop), and
  whatever holds it, no point of the hand
  goes under the top while it is over the cover: the arm lifts it out (the
  clip's hand sweeps down through the cover as the body passes it). The
  cover runs from its near face to its far one, both measured by level rays
  (the scan's `face_d` and `back_d`; its samples step 15 cm, so its last one
  over the cover read a 25 cm wall 17.7 cm deep), and the record carries it
  (`hand_cover`) to my robot body's hardware pass, which keeps the held hand
  out of it too ([robot body](robot-body.md)).
- **The mount** (climbLedge, the scramble's and the ladder's mantle): the
  hands grab the lip at full weight as they near it and stay where they land
  on the top through the pull-over. The end crouch is a visual sink that
  fades with the clip after the move; its depth is measured on this body
  (`clip_tuck`: how far the clip's crouch draws these feet up), not the
  original's 0.65 m, so the crouched feet rest on the top.
- **The ladder** hangs the hips a third of their standing height behind the
  rungs' line (`ladder_standoff`, 0.30 m on a 0.9 m hip; the library clip
  climbs a leaning ladder, so the original's standoff would leave its feet
  half a metre behind the rungs). On a vertical ladder the clip's torso lean
  (25° on Aletheia, 34° on my robot body) is stood up to `LADDER_LEAN_KEEP`
  (3°), eased in over the approach and out before the mantle, so the
  shoulders stay about 25 cm off the rungs and the arms can reach them. Each
  hand and foot grips through its clip's hold (`limb_grips`: any time but its
  one reach a cycle) and is latched to a rung within the arm's reach that is
  still above the shoulder when the hold ends. A hand closes over its rung as
  the clip holds it, palm-down with the fingers over the far side: the point
  under the palm (between the wrist and the middle knuckle) on the rung's
  axis. Between holds a reaching hand is kept in front of the rungs, pitched
  fingers-up at the wrist first. The ball of the foot stands on the rung's
  top. `climb_ladder(..., rung_radius=None)` takes the rungs' real
  thickness, so palms close over and soles stand on rungs of that radius
  ([maneuvers](maneuvers.md) measures it). A flat face (the scramble)
  gets palm and toe holds at the height they arrive. The top rung is the last
  one terrain_base builds.
- **No foot inside a solid** (`feet_out_of_solids`, the last pass of every
  maneuver frame): the whole foot every 12 mm and the visible boot as the
  pose deforms it (its skin's weights over the humanoid bones: a toe cap
  partly on the toes or a heel partly on the shin bends off the rigid foot
  in a crouch), inside by a parity ray, moved
  out the shorter way, up or back out of the face the travel meets; where
  neither straight move frees it (a boot wedged between a rung and the
  wall), the least move in the travel's plane (searched on a 3 cm, then a
  1 cm grid), keeping the boot's world turn through the leg solve or,
  folded against the hip, a swing of the whole leg. The solids are
  `c.contact_world` (default the walking world; pass one with the ladder's
  rungs and rails in it, as the course example does: they are not walked on).
- **On my robot body** the hardware pass (`dof_pass`) clamps the clip to the
  joints it has; a hand the move holds (a vault's prop hand, a ladder grip:
  the record's `hand_contact` weight) is solved again from the rehomed
  shoulder and run through the arm pass (`dof_pass(reach=)`), so the hand
  still plants on the top or the rung through the passage; a held hand the
  arm pass leaves in the vault cover it is over (the record's `hand_cover`:
  the shoulder at its pitch stop as the body passes the hand) is lifted out
  by the elbow ([robot body](robot-body.md)).

A drop deeper than `fall_land_min_drop` (0.85 m) plays fallLand; the film
plant stands the landing on the ground it reached. Register your own moves in
`c.maneuvers`, extra planners in `c.maneuver_planners`, contact IK by grab
type in `c.maneuver_hand_ik`; `auto_maneuvers=False` (or `c.auto_maneuvers =
False` from a `call`) stops the auto-trigger near things that look like cover
but are not (the course example's bench). Aimed at scene objects, and seats
for a walking body: [maneuvers.md](maneuvers.md).

## The world — `CollisionWorld`

```python
world = CollisionWorld()                    # every visible mesh that is not skinned to an armature (a VRM never
                                            # probes itself); or CollisionWorld([floor, stairs, rocks])
world.ray_cast(origin, direction, max_dist) # Hit: .hit .point .normal .distance .object
world.sphere_cast_down(origin, r, dist, min_normal=0.7)    # a ball dropped: Rapier's castShape witness and normal
world.move_and_slide(centre, (dx, dy), radius, half_height, skin=0.05)
world.underside(x, y, z)                    # a surface at z seen from under it: (its underside's z, what lies below)
world.inside_solid(point)                   # inside a closed solid, by its faces' winding along level rays
world.refresh()                             # after the scene changes
```

Blender has no shape sweep, so a ball cast is rays: the centre and two rings.
A ball that comes down on an edge (a stair's nosing) is bisected onto the
edge and sits on it with the normal from the edge to its centre, as Rapier's
swept ball does; on a face under its centre it rests on the face's plane.
Anything is walkable: the course pieces, a heightfield, rocks, furniture.
Hide or exclude what should not be (`CollisionWorld(exclude=[...])`).

## The foot IK — `VRMFootControllerIK`

```python
from eidoblend.characters.controller import VRMFootControllerIK, CastType, Pose, root_matrix
ik = VRMFootControllerIK(body, world=world, type=CastType.RAY_AND_SPHERE, sphere_radius=0.015,
                         max_step_height=0.6, foot_height_offset=0.012, mesh_height_offset=foot_z)
pose = Pose(body, root_matrix(x, y, z, heading), normalized_rotations)
ik.update(1 / 30, pose)                     # the pose edited in place
ik.lowest_foot_height, ik.highest_foot_height, ik.directional_foot_height(move_dir), ik.can_reach_targets
```

Per frame and leg: a low cast under the ankle and a toe cast (half the foot
ahead: `extra_cast_reach_scale`), the higher hit places the foot; the foot
turns onto the surface's normal (`foot_constraint` holds it within
acos(0.85) = 31.8°); the target eases toward last frame's (`distance_power`,
`smoothing_angle`, `global_smoothing_power`); the leg is solved by the cosine
rule with the knee plane from the leg (`fix_knee`). The controller sets its
per-frame contexts: `descent_context`, `flat_walk_context` and
`step_clearance_context` (the synthetic swing arc), `foot_plant_forward_offset`,
the stair-ascent sole fit and edge align, `ramp_foot_clearance_offset`.
`RotationType` is the original's enum (only `RAW_TARGET` is used, as there).

## Clips the controller measures

Every clip is measured once on the body that plays it (`clips.analyze`): the
treadmill under a planted foot, each foot's stance through the cycle, the
stride and native pace, the forward travel table distance matching inverts,
the sideways sway, where the left foot strikes (`phase0`), the passing phases,
the climb a stair clip makes per cycle, a turn's steps. `lib =
load_standard_animations(me, body)` gives the stripped, measured clips; the
controller caches them per rig. The maneuvers read the same measures: the
vault's take-off and landing (`vault_window`), the mount's end crouch
(`clip_tuck`), a climbing clip's holds (`limb_grips`).

## Tests — `blender/tests/controller/`

Each test bakes on the CPU, saves its keyed `.blend` and a shot list; one
`render_shots.py` run renders the stills of any number of tests. Run it
through `run_blender.sh`, one render at a time on a shared GPU.
Besides checks.feet (the plant's own report, on rigid sole points), the
tests measure what the camera sees: `FootMesh` in `_ctrl_stage.py` takes the
skinned boot's every vertex against every solid (inside by a parity ray), so
a foot in a wall, a turn's lifted boots or a seated boot under the floor fail
whatever the plant believed.

```bash
bash run_blender.sh blender/tests/controller/test_controller_course.py --vrm claude_robot     # from the repository root
bash run_blender.sh blender/tests/controller/render_shots.py blender/tests/controller/out/course_claude_robot_shots.json
```

The walking course example scene
([blender/examples/obstacle_course/](../blender/examples/obstacle_course/scene.py),
the counterpart of `eidoverse/examples/obstacle_course.js`) builds the same
course with Aporia and her follow camera through the runner:
`python eido_blender.py render blender/examples/obstacle_course/scene.json --at 14.4 --at 40 --at 51.6`.
It builds in about five minutes, the spring chains baked with the take. Its
stills from the follow camera at 14.4 s, 40 s and 51.6 s match the WebGPU
film's frames of the same moments in composition, scale and stride, and
Aporia casts her sun shadow in them (`load_vrm` sets the MToon materials up
for EEVEE's shadow pass: [characters](characters.md#loading-a-vrm)). Its
finale salutes toward the follow camera and holds the salute's last pose,
facing it, to the film's end, as the WebGPU example does (it never calls
`stopEmote`). The
whole film at the scene's 960 x 540 and 16 samples takes 13-16 s a frame on
a shared GPU, over six hours for its 1727 frames; with scene.json's width,
height and samples lowered to 640 x 360 and 4, a look at the whole take
renders at 1.3 s a frame.

| Test | What it walks |
|---|---|
| `test_controller_course.py` | the course: a bump, 8° ramps, small stairs up and down, a run up and down normal stairs, the run slowing to a stop on its mark, turns on the spot (a boot on the floor in every frame), a walk to the side |
| `test_controller_presets.py --preset NAME [--leg-ik none]` | every TERRAIN_CONFIG of the WebGPU bench (`eidoblend.course.PRESETS`), the stress course among them (its dome stepped over, not hopped); `--leg-ik none` is attachLocomotion without leg IK (the bench's noik scenes) |
| `test_controller_terrain.py` | rolling ground and rocks, a curved path, a jog, a stop and a turn on the slope |
| `test_controller_cross_slope.py [--vrm aletheia]` | a 20° hillside walked along its contour both ways, a turn on the spot on it and a jog across: every planted sole holds one roll off the slope through its flat stance, within 1° a frame and 1.5° in all (my robot body's ankle rolls 14.9° at most; Aletheia's feet lie flat on it), the boots out of the slope |
| `test_controller_acting.py` | a gesture over the walk, an emote, a sit on a bench 5 cm higher than the clip's seat (settled onto it, never more than 1 cm into it sitting down or standing up, the boots on the floor, the walk on at the seat's heading), a 1.44 m drop into fallIdle and fallLand, the backward walk, a jog and a sprint, and a plain seat stood up from on the stand-up clip (the hips held through its crossfade, carried forward and never back, ending over the spot she sat down from; the boots on the floor through the hold and one on it from the hips leaving the seat) |
| `test_controller_foot_ik.py` | every `VRMFootControllerIK` option on a still body, then the WebGPU per-frame IK against the plant |
| `test_controller_options.py` | every controller and `attach_locomotion` option, one behaviour each, on the controller's own telemetry; the maneuver planner's choices and the scan's measure of a cover's near and far faces; the probes under a doorway's lintel and a ceiling slab (walked under), a beam too low to walk under, a block sunk into the floor and two built against each other (climbed) |
| `test_controller_maneuvers.py` | `examples/obstacle_course.js` as the WebGPU example directs it, on its own character (Aporia) and with its follow camera keyed into the film: vaults (each rising over its cover, its prop hand's palm on the top and no point of a hand in it), mounts (hands on the lip, the crouch resting on the top), the gap jump, falls and landings, the sit stop at the bench (settled on it), the cheer while walking, the ladder (hands and feet on the rungs), the salute toward the camera, held facing it to the end; no foot inside anything through any maneuver |
| `test_controller_follow.py` | `follow` after a keyed cart that rolls off, curves, stops and races off (the body keeps its distance, stops behind it each time, runs while it races), then `steer` through a slow S from a function of time; checks.feet on every gait, the keyed armature against the bake |

The spring chains' test, `test_take_springs.py`, is the characters family's
(`blender/tests/characters/`): see Springs ride the take, above.

## Not yet ported

- A sneak: the library has no crouched-walk clip (render_scene.mjs names
  `sneak` in its treadmill guard only).
- `seatOn`'s recentring of the hips over the pan for `sit()`: `sit()` is the
  course example's `beginSeated` where the body stands, and `seat_spot()`
  stands it where the clip's own hip travel ends over the seat point; the
  settle onto the pan's height and the clamp are ported (`sit(seat=...)`).
  The verb `emotes.seat_on` has the recentring and the backrest bias
  ([maneuvers.md](maneuvers.md)).
- The backward walk on stairs: walkBackward is for the flat and ramps; the
  stair clips play forward only.

Known residuals of the film bake (each found by the tests; the JSON reports
in `out/` list the frames under `stance_issues`, `swing_issues` and
`mesh_feet_over_limit`):

- The stress course (`obstacle_course_expanded`, 31 of 32 checks): in the
  walk after the dome a foot settling flat from its heel strike rolls
  3.6 mm in one frame (the check's limit is 2.5 mm); the pelvis dips up to
  27 cm under the controller's height at the dome; the deepest visible foot
  is 8 mm into a surface. Stepping on and off its flights, and the dome,
  keep a foot down in every frame.
- The ramp pyramid (`ramp_pyramid`, 12 of 13 checks): where a stair clip
  plays on the ramps, one stance's last frame, the foot rolling onto its
  toes, slips 7 mm and its toes read 3 mm into the slope.
- My robot body on a 20 degree cross slope (`test_controller_cross_slope.py`,
  17 of 19 checks): its walks hold each planted sole's roll as steadily as
  Aletheia's feet lie flat on it (within 0.74° a frame and 1.3° through the
  flat stance, hers 0.82° and 0.98°), but jogging across it the downhill
  foot's short stances still roll 2.1-3.1° a frame between their landing and
  heel-off, and the turn on the spot there misses an ankle target by 5 mm.
- On rolling ground (the terrain test, my robot body: 23 of 27 checks), a
  stance planted at the foot of a 16 cm rock, before the step onto it, has
  its toe against the rock's flank (the plant's rigid sole points read up to
  57 mm under it), a stance where the walk back sets off turns 4.5 degrees
  in a frame, and a turn on the slope misses an ankle target by 2.2 mm.
- Stepping onto a boulder over about 20 cm in mid-stride: my robot body's
  swing target outruns its legs for a few frames. The terrain test keeps that
  boulder beside the path.
