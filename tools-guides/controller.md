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
| `turn_to(deg)`, `turn_by(deg)`, `face(p)` | turn on the spot (turnLeft / turnRight, the root taking the clip's own hip yaw scaled to the angle; over 1.1 × the clip's turn it is split, the parts crossfaded; under 20° a settling turn) |
| `emote(slot, seconds=None, facing='keep')` | `playEmote` (locomotion suspended), then `stopEmote`; `facing` a heading in degrees, `'keep'`, or `None` for the WebGPU default (three's π) |
| `gesture(slot, weight=2.5)` / `stop_gesture()` | `playGesture`: the upper body plays the clip over whatever the legs do |
| `sit(hold=2.2, clip='stand_to_sit', reverse=True, reverse_speed=1.25)` | `beginSeated` where the body stands, hold, `endSeated` (reversed, as the course example does), `stopEmote`; `seat_spot(seat_xy, heading_deg)` says where to stand so the clip's own hip travel ends over the seat |
| `vault()`, `climb_ledge()`, `jump(distance, height)`, `climb_ladder(height)`, `climb_wall()` | the explicit moves from where the body stands, facing its heading (the auto-trigger does the vault, the mounts, the scramble and the gap jump on its own along any path); each lasts while the move and anything it chains are in flight |
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
command walks off again from standing.

```python
rep = walk.bake(f0=1,
                feet='plant',            # the film's planted feet; 'foot_ik' keys the WebGPU per-frame IK as it is
                pelvis='stance',         # the hips from the planted legs; 'controller' keeps the controller's height
                clearance=0.03,          # the swing sole's least height over what it sweeps, mid-swing
                key=True, check=True, action_name=None)
rep['segments']          # [{'gait': 'stairsUp', 'frames': [287, 327], 'checks_feet': {'ok': True, 'failures': []}}, ...]
rep['worst']             # slip, drift, gap, swing clearance, ankle misses over the whole take
rep['_records']          # every frame: root, pose, weights, stance, support mode, climb angle, speeds, the probes' verdict
```

What the film bake decides, frame by frame over the recorded take:

- **The stance** is each playing clip's measured stance, blended by weight.
  A foot the clip plants past an edge (the ground under it more than 0.45 m
  below the body's support) is not planted: it swings until the body falls.
- **Planted feet** do not slip or turn on the ground; a landing slides along
  the foot (at most 12 cm, never onto ground more than a stair's rise below)
  onto the support; the sole tilts onto the ground's plane; the toes stay
  flat through the roll; a planted foot keeps the surface it landed on (a
  heel that creeps over a higher edge tucks into it rather than lifting the
  foot onto it). A foot's heading is read from its forward and up vectors
  together, steady from heel strike to toe-off.
- **Swinging feet** follow the clip's own arc over the line between the two
  plants, never closer than `clearance` mid-swing to the highest ground they
  sweep, and never in contact while they travel faster than 0.8 m/s (a
  toe-off, a backward walk's lift). A swing that ends in a fall, a seat or a
  maneuver hands its foot to the clip by then.
- **The pelvis** goes where the planted legs have the clip's own length,
  capped so every loaded leg reaches. `pelvis='controller'` keeps the
  controller's height, capped for reach and floored where a planted leg is
  folded to its knee stop.
- **Falls, seats and maneuvers** leave the feet to the clip and the root to
  the controller (the maneuver's path); a landing (fallLand) stands where it
  landed.

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
the body's height); `locomote(dt, direction)` is the whole frame. What the
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
here for every shape, both ways). `gait_sync='stride'` is the original:
`timeScale = speed / nativeSpeed` (capped at 1.4).

**This edition's additions**, each an option that is off unless asked
(`Locomotion` turns the first three on):

- `gait_sync='distance'` (above) and `native_*_speed=None` (measured).
- `land_on_contact=True`: a falling body lands when its feet reach the
  ground. The original regains the ground 0.4 m above it (fall_threshold) and
  floats the rest down at the body-height rate cap, its feet in the air; so
  it plays fallLand only for drops over 1.25 m (0.85 + 0.4).
- `turn_on_spot(angle)`: turnLeft / turnRight played with the root taking the
  clip's hip yaw (the original never plays them); a turn straight after the
  same turn crossfades from a twin action of the clip.
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
seated clip on the controller's mixer while the root holds. Every loader takes
`vrma_library={slot: path}` (the original's `vrmaLibrary`).

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
c.climb_wall()                    # the wall scramble
walk.climb_ladder(height=2.5)     # the same as film commands (they last while the move and its chain fly)
```

Each move is a root path the body follows while a window of its clip plays:
the vault and the mount fit the clip's **own hips curve** (its root motion,
extracted before the strip) to the obstacle, so the hands meet the top where
the animation reaches for it; the jump and the climbs use keypoint arcs. A
contact IK then pulls what should touch onto the geometry at partial weight
(the clip keeps the motion): the vault's prop hand on the cover top and the
feet out of it, the hands on the lip and the top through a mount (the top a
floor for them) and the mantling foot onto it, the hands and feet latching
the rungs (or holds on a flat face). The climb's end crouch is a visual sink
that fades with the clip after the move, so the feet stay on the top. A drop
deeper than `fall_land_min_drop` (0.85 m) plays fallLand; the film plant
stands the landing on the ground it reached. Register your own moves in
`c.maneuvers`, extra planners in `c.maneuver_planners`, contact IK by grab
type in `c.maneuver_hand_ik`; `auto_maneuvers=False` (or `c.auto_maneuvers =
False` from a `call`) stops the auto-trigger near things that look like cover
but are not (the course example's bench).

## The world — `CollisionWorld`

```python
world = CollisionWorld()                    # every visible mesh that is not skinned to an armature (a VRM never
                                            # probes itself); or CollisionWorld([floor, stairs, rocks])
world.ray_cast(origin, direction, max_dist) # Hit: .hit .point .normal .distance .object
world.sphere_cast_down(origin, r, dist, min_normal=0.7)    # a ball dropped: Rapier's castShape witness and normal
world.move_and_slide(centre, (dx, dy), radius, half_height, skin=0.05)
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
the climb a stair clip makes per cycle. `lib = load_standard_animations(me,
body)` gives the stripped, measured clips; the controller caches them per rig.

## Tests — `blender/tests/controller/`

Each test bakes on the CPU, saves its keyed `.blend` and a shot list; one
`render_shots.py` run through the GPU slot renders the stills of any number
of tests (`gpu_slot.sh` waits for the slot).

```bash
cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
bash run_blender.sh <repo>/blender/tests/controller/test_controller_course.py --vrm claude_robot
bash <repo>/blender/tests/controller/gpu_slot.sh <repo>/blender/tests/controller/render_shots.py \
     <repo>/blender/tests/controller/out/course_claude_robot_shots.json
```

| Test | What it walks |
|---|---|
| `test_controller_course.py` | the course: a bump, 8° ramps, small stairs up and down, a run up and down normal stairs, the run slowing to a stop on its mark, turns on the spot, a walk to the side |
| `test_controller_presets.py --preset NAME` | every TERRAIN_CONFIG of the WebGPU bench (`eidoblend.course.PRESETS`), the stress course among them |
| `test_controller_terrain.py` | rolling ground and rocks, a curved path, a jog, a stop and a turn on the slope |
| `test_controller_acting.py` | a gesture over the walk, an emote, a sit on a bench, a 1.44 m drop into fallIdle and fallLand, the backward walk, a jog and a sprint |
| `test_controller_foot_ik.py` | every `VRMFootControllerIK` option on a still body, then the WebGPU per-frame IK against the plant |
| `test_controller_options.py` | every controller and `attach_locomotion` option, one behaviour each, on the controller's own telemetry; the maneuver planner's choices |
| `test_controller_maneuvers.py` | `examples/obstacle_course.js` directed as the WebGPU example directs it: vaults, mounts, the gap jump, falls and landings, the sit stop at the bench, the cheer while walking, the ladder, the salute |

## Not yet ported

- A sneak: the library has no crouched-walk clip (render_scene.mjs names
  `sneak` in its treadmill guard only).
- `seatOn`'s seat fitting (scene_placement.js: where to stand, the settle of
  the hips onto the pan): that is the placement family's. Here `sit()` sits
  where the body stands and `seat_spot()` finds the standing spot from the
  clip's own hip travel; a seat at another height than the clip's is not
  fitted.
- The backward walk on stairs: walkBackward is for the flat and ramps; the
  stair clips play forward only.

Known residuals of the film bake (each found by the tests; the JSON reports
in `out/` list the frames under `stance_issues` and `swing_issues`):

- Where a stair flight hands over to the walk (and back), a planted heel or
  toe can tuck into a riser's nose for a frame or two: a planted foot keeps
  the surface it landed on rather than hopping onto the edge. The checks read
  those sole points as up to 170 mm under the tread above them; in the one
  case measured frame by frame (the foot of the stairs pyramid) the foot had
  moved 2 cm.
- At the same hand-overs, and on the 25 and 33 degree climbing ramps, a
  planted foot can slip 6 to 7 mm in one frame.
- A turn on the spot on a slope (15 degrees and steeper) never has both feet
  down in the same frame; started on a stair tread, its first lifted foot
  jumps 17 cm in one frame.
- A 45 degree ramp: one stance slips 39 mm in a frame (the stair clip
  climbing it).
- On rolling ground, a three-frame stance turned 9 degrees in a frame.
- The walk's last swing into a turn on the spot can land moving 1.6 m/s.
- Stepping onto a boulder over about 20 cm in mid-stride: my robot body's
  swing target outruns its legs for a few frames. The terrain test keeps that
  boulder beside the path.
- `pelvis='controller'` on a stair descent: the controller's lowered body
  pushes a planted sole 80 mm into a tread.
