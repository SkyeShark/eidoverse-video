# Maneuvers, sitting and emotes (Blender edition)

[Main instructions](../AGENTS.md) · [Character controller](controller.md) · [Placement](placement.md) · [Characters](characters.md)

This is the Blender 5.2 EEVEE edition of the character verbs a scene gives a
walking body: `eidoverse/scene_placement.js`'s `emote`, `faceCamera`,
`seatOn` (seat detection, facing, the transition, the clamp and the settle),
`sitOnGround`, `unseat` and the seated exemption from the audits, routed
through the controller the way the engine routes a controlled VRM ("the
cohesive path": `globalThis._vrmControllers`, `beginSeated`, `endSeated`,
`robot_body.js`'s `standUp`); and `character_controller.js`'s parkour (vault,
climbLedge, jump, climbLadder, climbWall and the auto-trigger's vault, mount,
scramble and gap jump) aimed at objects in the scene.

Two packages, both on top of the controller
([controller.md](controller.md)):

| Package | What it holds |
|---|---|
| `blender/eidoblend/characters/emotes/` | `seat_on`, `stand_up`, `sit_on_ground`, `face_camera`, `emote`, `unseat`, `bake`, `key_seated`; the measures (`seat_plan`, `seat_skin`, `skin_lowest`, `skin_points`, `pan_points`, `back_push`, `robot_body_of`); the library's expressive and sitting clips (`EXPRESSIVE`, `CHAIR_SITS`, `FLOOR_SITS`, `TRANSITIONS`, `clip_info`) |
| `blender/eidoblend/characters/maneuvers/` | `vault_over`, `climb_onto`, `scramble_up`, `climb_ladder`, `jump_across`, `cross`; `measure_obstacle`, `measure_ladder`, `takeoff_edge` |

The moves themselves (their clips, root paths and contact IK, the feet kept
out of solids) are the controller's: `eidoblend.characters.controller.maneuvers`.
The stationary verbs (a VRM nothing drives) are the placement family's:
`eidoblend.placement.seating`. Every verb here takes either a `Locomotion`
(the controller path) or a VRM handle (it calls the placement verb), as the
engine's helpers check for a controller first.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import math, bpy
from eidoblend.characters import load_vrm
from eidoblend.characters.controller import CollisionWorld, Locomotion
from eidoblend.characters import emotes as E
from eidoblend.characters import maneuvers as MV

bpy.context.scene.render.fps = 30
me = load_vrm('aletheia')
seats = [o for o in chair.children_recursive]                    # seats are not walked on (see below)
walk = Locomotion(me, CollisionWorld(exclude=seats + rungs + rails), start=(0, -3, 0), heading=math.pi)
walk.wait(0.5)
E.seat_on(walk, chair)                     # walk up, turn out of the chair, step back to it, sit into it
walk.wait(2.0)                             # seated: any number of commands
E.stand_up(walk)                           # the sit-down reversed; the walk resumes
MV.vault_over(walk, cover)                 # walk up to the cover, square up, vault it
MV.climb_ladder(walk, rungs, wall)         # the rungs measured; up them; the mantle over the top
E.face_camera(walk)
E.emote(walk, 'salute', facing='camera')
rep = E.bake(walk)                         # the take keyed; arm['eido_seated'] keyed over the seated frames
```

`E.bake(walk)` is `walk.bake()` with the seats' frames handed over before the
plant and after it (below); use it whenever a take holds a seat. Everything
lands on one keyed action, so a saved `.blend` plays and renders any frame on
its own.

## Sitting a walking body — `seat_on`, `stand_up`

```python
E.seat_on(walk, chair,
          transition='stand_to_sit',   # the sit-down clip (the engine's transition)
          face=None,                   # a heading (rad, 0 faces -Y); else the chair's own facing; else the camera
          then=None,                   # a seated loop after it: 'sitting_normal_chair', 'sitting_nervous_arm_rub_chair'
          hold=None,                   # seconds, then stand up (stand={...}: stand_up's options); None: stays seated
          back_up=0.35,                # the last steps backward onto the spot (m; 0: none)
          hip_back=None,               # None: where the clip's own hip travel needs her; a number: the engine's 0.46 m
          instant=False,               # True: seatOn's instant path: put there seated, in the loop, at once (below)
          sink=0.0, fade=0.25, transition_dur=None, gait='walk', speed=None, via=None, camera=None)
E.stand_up(walk, reverse=None,         # None: the sit-down reversed when it is the pose held, else the stand-up clip
           clip='sit_to_stand', reverse_speed=1.25, fade=0.25, fade_out=0.5)
```

**A shot that opens seated** (`instant=True`, the engine's instant path:
`seatOn` without a transition snaps a VRM into the chair pose). No walk and
no descent: the body is put (`controller.place`) on the spot the transition's
own hip travel would have stood it, facing out of the chair, and the take
opens in the seated loop (`then=`, default `sitting_normal_chair`) at full
weight, its settle on the pan applied at once. The seat is measured as a
sit-down measures it (the backrest bias, `back_push`, the settle, the
knees), so everything after it works as from any seat: `stand_up` plays the
stand-up clip, the walk takes over, the seated frames are keyed seated.
Later in a take it is a cut: the body jumps into the chair, nothing is
handed over from the plant there, and the spring chains start over on the
seated pose, settled (they would otherwise spring out of their rest shape).

```python
walk = Locomotion(me, CollisionWorld(exclude=seat_parts), start=(0, 0, 0))
E.seat_on(walk, chair, instant=True)              # frame 1: seated in sitting_normal_chair, settled on the pan
walk.wait(1.5)
E.stand_up(walk)                                   # sit_to_stand, then the walk takes over
walk.move_to((0.5, -1.0))
E.seat_on(walk, bench, instant=True, then='sitting_nervous_arm_rub_chair', hold=1.5)   # a cut into the bench
rep = E.bake(walk)
```

In `test_start_seated.py` both seats open with the hips on their targets
(0.0 cm), the seated skin on the pan (0.07 and 0.30 cm under it), facing out
of the chair, the hips holding their height through the first second, and
every check of the whole seat passing.

What `seat_on` does, in the engine's order:

- **The seat and its facing.** `find_seat_surface` finds the pan (the
  fullest bin of a 7 x 7 grid of down-rays), `chair_facing` reads which way
  the chair opens from its backrest, and she sits facing `face`, else the
  chair's facing, else toward the camera. The hips' target is the pan's
  centre biased toward the backrest (the engine's `min(0.12 m, 18 % of the
  pan's depth)`).
- **Clear of the backrest.** The engine never checks the back: on a chair
  whose back stands on its pan, her butt and her coat went through it and
  out of its back. Before the walk, the transition's last pose is settled
  where she will sit and tested against the chair's parts over the pan
  (`back_push`): the target moves forward until the body is 1 cm clear of
  them. A coat (a loose layer: a mesh skinned to the thighs that is not the
  tightest skin round them) may press into the back, as cloth would, but
  not come out behind it; skin already through a thin back counts too. A
  seated loop is measured over its whole length (the fidget loop leans
  back: Aletheia's tentacle base needs 8.5 cm more), and a stand-up whose
  crossfade from the loop would still lean into the back starts with her
  shifting forward on the seat over half a second (`SCOOT_T`), as one does
  before getting up. A sitter turned more than 90° from the chair's facing
  (`face=` on purpose) is left where the target puts her.
- **Where to stand.** The engine stands her 0.46 m in front of the seat and
  recentres the hips at the end (a visible slide). Here the spot is measured
  on the clip: the transition's own hip travel (stand_to_sit carries the hips
  0.44 m back and 0.42 m down) ends with the hips on the target. She walks
  to `back_up` in front of that spot (round the chair when it is in the way;
  the auto-trigger off: a chair reads as cover), turns out of the chair, and
  steps back onto the spot (`walkBackward`), as a sitter backs up to a seat.
  A seat with no room under its front at foot height (a bench boxed to the
  floor: less than `BACK_ROOM`, 0.30 m, behind the spot) is not backed onto:
  she comes in from the side, past its end, as the example's route round its
  bench does, and settles round to face out. What is left of the arrival
  (about 1 cm) is recentred over the descent's second half, the feet held
  where they stand.
- **The descent.** The engine's `beginSeated(transition)`: the controller
  holds the root and the clip lowers her. The settle (the lowest seated skin
  over the pan onto the pan) eases in over the descent's second half; from
  40 % in, the clamp (`_clampSeatedButt`) never lets the skin go under the
  pan. Both are measured before the take on the posed seat skin (`seat_skin`:
  the pelvis and thighs, not the hair, a coat's hem or a calf; on my robot
  body its hips' mechanism too), every frame from 40 % in, over the pan's own
  surface (`pan_points`: the engine's world-aligned 0.40 x 0.44 m box reaches
  past a turned chair's pan, where the thighs hang lower in the air past its
  edge), and smoothed into one lift curve, so the switch between them is no
  kink. The measures pose the body at the floor's height, so their up-rays
  start 0.6 m under the pan (`UNDER_FROM`; from 0.25 m, the engine's window
  for a lifted body, a 0.62 m stool's seated skin lay under the rays' start),
  and every bone the clips do not pose is put at rest for them (left as the
  last evaluated frame had them, my robot body's hip helpers carried one
  take's seat into the next take's measures).
- **A seated loop** (`then=`) crossfades in over 0.5 s with the root carried
  back by the difference of the two poses' hips (0.42 m for the fidget loop
  after stand_to_sit), so the hips stay on the seat (3 mm a frame at most in
  the test), its own settle blended in (the fidget loop sits 13 cm higher).
- **The feet.** On a seat the plant's standing rules would plant the feet by
  lowering the pelvis into the seat (its reach cap), or lock a ground sit's
  folded feet as one long stance. `bake` takes the seat's frames from the
  plant (it leaves their feet and keeps the seated root) and puts the feet on
  the floor itself: a foot under the floor is lifted straight up; over it,
  while the thigh rests on the pan, the knee opens (no more than 1.5 cm of
  sideways swing: a seated shin hangs near vertical, where a turn of the knee
  moves the foot sideways, hardly down), then the ankle reaches down with the
  knee kept no lower than the clip has it in that frame less 5 mm
  (`KNEE_GIVE`: a knee lowered turns the thigh down into the pan; one knee
  height taken from the settled pose let a fidget loop's and a stand-up's
  knees be pulled 7-9 cm down to it, the thighs 2.8 cm into the pan), then
  the toes point down up to 35°: on a seat higher than the clip's the feet
  hang, toes reaching. A boot that a seated loop tucks into the chair's legs
  is moved out of them: the boot as the armature deforms it (its ankle rides
  on the shin's weights), tested against each part of the chair on its own
  (one solid for the whole chair read a point deep in a leg as outside: the
  leg's top and the pan's underside are coplanar), by the shortest move over
  16 horizontal ways and straight down that leaves the whole boot off the
  part (moved toward the nearest face of its deepest point, a boot round a
  4 cm leg went 2-3 cm and stayed on it), the way kept from frame to frame
  unless another is clearly shorter, smoothed over nine frames, in up to
  four rounds. A foot that moves between two seated poses (a crossfade into
  or out of a loop) steps, lifted, instead of sliding. A seated foot resting
  on the floor (within 4 mm) is held where it rests, its place and turn; a
  foot lifting off it without a step eases back to the clip's place over 8
  frames. Where the feet bear the body (sitting down, standing up) one foot
  steps at a time: where both feet's steps overlap there, the longer is
  taken and the other foot stays where it rests. Seated on the pan the feet
  carry nothing, and both step together, each lifted.
- **My robot body** (`claude_robot`) carries joint clamps on its legs, which
  the plant applies to every frame it keys: the measures pose its legs
  through them and through its hips' stages (`body.project_legs`: the
  HipPitch / HipSwing mechanism the bake keys, which is seat skin too), and
  each seated foot is reached for again on the clamped legs until the
  clamps leave it where it was placed. Its ankle has no twist, so a foot
  turns with the shin about the leg. One resting flat on the floor (its
  points on the floor spanning most of its length) keeps the turn it came
  down with: the leg swings round the line from its hip to its ankle (the
  knee goes aside, the ankle stays where it is) until the shin holds the
  foot there, up to 25° (its hip's twist), and only where the clamped legs
  still leave every foot within 3 mm of where it was placed. Past that the
  foot takes the rest of the shin's turn about the middle of what rests on
  the floor, not about its ankle. A step off a rest eases the held turn into
  the clip's over the step. Its toes point down only as far as its ankle
  keeps its whole roll range (28.15° of pitch, less 1°: near the 30.9° stop
  the roll narrows to a few degrees, and a hanging foot there would roll
  from one stop to the other).
- **The hand-over.** Where a seat's frames meet the plant's, the plant
  drops a stance's hold at once (the foot jumps by all the stance's
  correction: up to 26 cm measured). `bake` passes each foot and the pelvis
  between the two over 12 frames inside the seat; a foot that has more than
  3 cm to go steps there, lifted, coming straight down onto its place (the
  step is decided once for the whole hand-over: decided per frame, a foot
  near 3 cm lifted 2.4 cm on one frame and not the next).
- **No rest-pose shortfall.** The controller fades the walk's clips out in
  about a quarter second while an emote fades in, and the mixer fills the
  weights' shortfall with the rest pose (the T-pose: arms lifting for a few
  frames; the longer the emote's fade, the longer: a 1 s ground sit would
  blend toward it for most of a second). A seat enters on the standing pose taken at full weight at
  once (the idle as an emote, its hips stripped as the walk's) and
  crossfades from it with weights that sum to one; every stand-up gives the
  body back through the same pose.
- **Standing up.** `reverse` plays the sit-down backwards (the example's
  reverse mode: the same poses, no hip mismatch). The stand-up clip
  (`sit_to_stand`, `VRMRobotBody.standUp`'s default) starts with the hips
  over its root; the root is carried by the hips' difference through the
  crossfade, the clip's own seat height blended in, and the clip's hips
  travel (44 cm forward) is taken as root motion, so the feet stay where
  they stand (the engine releases the root at 85 % of the clip and the body
  pops forward). The seat's lift is let go as the clip's own hips rise (all
  of it once they are 60 % up), never under the clamp that keeps the seat
  skin on the pan, measured every frame on the posed body (the crossfade from
  a seated loop measured as blended). Let go over a fixed 60 % of the span
  whatever the clip did, a stand-up that leans forward before it rises sank
  her 11.7 cm through a 0.56 m seat, and the reversed sit-down 3.7 cm.
- **The facing check.** `key_seated` runs the engine's deferred check 1.5 s
  into each chair seat: a sitter more than 110° off the chair's facing is
  RE-RENDER REQUIRED, more than 55° worth a look.

**Keep seats out of the walking world.** The controller's probes read a pan
in the travel's path as a step to climb (backing up to a chair played the
stair clip), and the plant reads a pan over a turning foot as the ground
over it. `seat_on` warns when its chair is in the walking world. The course
keeps its rungs and rails out for the same reason. A seat with no room
under its front at foot height (a bench boxed to the floor) is approached
from the side, past its end, instead of backed onto (`BACK_ROOM`, 0.30 m):
the backing steps plant the trailing foot about 0.25 m behind the spot.

## A body my robot body drives

`VRMRobotBody` (`eidoblend.characters.robot`) registers itself as the engine
does (`globalThis._vrmControllers`), and the verbs look it up
(`robot_body_of(h)`). `seat_on(h, chair, transition='stand_to_sit')` on its
VRM takes the engine's cohesive path through the body's own seated state:
`seat_plan` measures the seat as the controller path does (the pan, the
facing, the target clear of the back, the spot the clip's hip travel needs,
the settle and the descent's lift frame by frame, on its legs' hardware),
the body is put at the spot facing out of the chair (the engine moves the
VRM there and syncs its capsule), `body.begin_seated(transition)` starts the
clip, `arm['eido_seated']` is set, and the plan stays on the body
(`body.seat_plan`) for its bake. `emote`, `face_camera` and `sit_on_ground`
on such a VRM warn and point at the body's own calls (`perform_action`,
`face_direction`, `set_emote_facing`): the engine's are for a VRM nothing
moves.

```python
from eidoblend.characters.robot import VRMRobotBody
body = VRMRobotBody.create(me, scene, {...})
def script(b):
    yield b.wait(0.5)
    E.seat_on(me, chair, transition='stand_to_sit')   # placed, seated; body.seat_plan for the bake
    yield b.wait(3.0)
    b.stand_up('sit_to_stand')
```

The robot body's bake seats it by that plan: in `test_robot_seat.py`, sat
down, its hips rest on the plan's target (0.0 cm) and its seated skin on the
pan (0.1 cm).

## On the ground — `sit_on_ground`

```python
E.sit_on_ground(walk, clip='sitting_on_ground',   # or 'sit_laying_on_ground' to lie down
                at=(2.0, 1.0),                    # walk there first (default: where she stands)
                face=None,                        # a heading; else toward the camera (the engine's default)
                fade=1.0, hold=None, sink=0.005, hip_height=0.08)
```

The library has no stand-to-ground clip, so the crossfade is the sit-down:
the ground clip crossfaded in from the standing pose by hand over `fade`,
eased, the lowest of the skin within 0.35 m of the hips rested on the floor
(the engine reads a 5 × 5 grid of up-rays there, which can pass between a
body's parts). The boots, and on my
robot body the arms, stay out of the floor through the crossfades, the hold
and the rise: where the floor is, an ankle rises (on my robot body after
its leg's clamps), the toes turn up where the leg cannot fold further, and a
forearm under the floor turns up at the shoulder. The engine casts at every visible mesh;
here the spring chains are left out (tails, tentacles, hair, a coat's tails:
the take's spring bake swings them afterwards, resting them on the floor and
keeping them out of the scene's solids), and so are loose layers (a coat skinned to the thighs: on the
ground its hem propped Aletheia 6 cm up, her crossed legs hovering; it goes
under the floor where it hangs under her, hidden by it). Lying down,
Aletheia's tails reach under her back at rest: measured with them she lay
propped on two of them, 15 cm over the floor. Blended halfway, the ground
clip's hips are 0.4 m down while its legs are half folded: the crossfade
alone put her feet and shins 16 cm into the floor. The body is kept out of
the floor through it (`_ground_lift`: the lowest of the body near the hips
on the floor, every frame of the blend measured before the take), handing
over to the engine's settle at the end (my robot body's legs cannot fold
cross-legged, so it sits with its legs out along the floor: see Not yet
ported). The engine's `sitOnGround` snaps into the pose; for a take that should
not show a sit-down, start the shot seated. `stand_up` crossfades back over
the same fade, out of the floor the same way. With no ground clip in the
library, the engine's fallback: the chair clip, with its warning.

## Emotes and facing — `emote`, `face_camera`

```python
E.emote(walk, 'cheer', seconds=None,              # the clip once, or seconds
        facing='camera',                          # 'keep', 'camera', a heading in degrees, None (three's π)
        fade_in=0.2, fade_out=0.3)
E.face_camera(walk, camera=None, offset=0.4)      # a turn on the spot toward the camera (+0.4 rad: three-quarter)
E.emote(friend, 'dance')                          # a VRM nothing drives: placement's emote, looping
E.face_camera(friend, offset=0.4)                 # placement's: turns her at once (frame= keys it)
```

On a `Locomotion` an emote is the controller's `playEmote`: the walk is
suspended, the emote plays, `stopEmote` gives the body back. The camera is
read where it is at the frame the command starts. Three things differ from
the engine, each measured as a pop in the hips (their acceleration against
the clip's own):

- **In at the walk's own fade.** The controller damps the walk's clips out
  at λ = 12 while an emote fades in linearly; the gap between them is filled
  with the rest pose (a T-pose blend: arms lifting for a few frames). The
  emote is given exactly the weight the walk loses each frame, so the two sum
  to one.
- **Out through the standing pose, eased.** A linear crossfade starts and
  stops at full speed: an emote cut short far from standing (raise, crazy at
  3 s) jerked 1.6 and 2.4 cm a frame² where the clips alone move 0.3 and
  0.1. It eases back to the standing pose over at least 0.5 s, then
  `stopEmote`.
- **The clip held over the root** (`align=True`): the library's cheer
  stands 25 cm behind its origin from its first frame, which slid the whole
  body back 25 cm as it came in (4.8 cm a frame²). Its first frame's hips
  offset is taken off; its own motion stays.

A sitting clip passed to `emote` warns: `seat_on` and `sit_on_ground` place
the body for those.
`EXPRESSIVE` lists the library's expressive clips (talk, salute, cheer, fist,
raise, reach, crazy, dance); `clip_info(h, slot)` measures one on a body
(duration, the hips' start and end, seated or standing). The performance
clips (`stand_breathe`, `sing_gesture_a` ...) are the characters family's
`perform` ([characters.md](characters.md)).

## The seated exemption — `key_seated`, `unseat`

A seated body overlaps its chair and its feet may hang: the clipping audit
would push her off the seat and the hovering audit snap her to the floor.
The engine kept seated VRMs in `_seatedVRMs`. A stationary seat
(`placement.seat_on`) sets `arm['eido_seated']`; a take's seats are keyed:
`key_seated` (run by `E.bake`) keys `arm['eido_seated']` 1 over the seated
frames and 0 elsewhere (CONSTANT), so the audits leave her exactly while she
sits. `E.unseat(walk)` ends the exemption from that point of the take (the
engine's `unseat`); `E.unseat(h)` clears a stationary one. The test shows it
at work: with the keyed flag `check_clipping` leaves the sitter and her chair
alone; with it forced off in the same frame, it names the pair.

## Maneuvers aimed at objects

```python
MV.vault_over(walk, cover)                    # vault(): the clip's take-off and landing fitted to the cover
MV.climb_onto(walk, block)                    # climbLedge (to 1.35 m), the climbWallUp route (to 2.3 m)
MV.scramble_up(walk, wall, rate=0.45, time_scale=1.25)   # climbWall: the scramble, then the mantle
MV.climb_ladder(walk, rungs, wall)            # climbLadder with the measured height, first rung, spacing and rung radius
MV.jump_across(walk, landing, height=0.5)     # jump(): from 15 cm before the edge, the measured distance
MV.cross(walk, cover, gait='run')             # through it: the auto-trigger picks the move (a walkTo's)
```

The engine starts a move two ways: the auto-trigger while a walk crosses an
obstacle, or an explicit call that acts "on whatever obstacle is ahead
along the heading", the body put there by the scene. Each verb here does the
putting: when it starts, it measures the object from where the body then
stands, walks to `run_up` in front of its near face with the auto-trigger off
(it would read the same obstacle first), turns square to it, and starts the
explicit move with the measured numbers.

- `measure_obstacle(obj, from_xy)`: horizontal rays from the viewer toward
  the object find its near face (above the ground, or below it for a
  trench's far wall), a ray down just inside the face its top, a ray back
  through it its depth, a ray down past it the landing.
- `measure_ladder(rungs, wall)`: the rungs' heights, first rung, spacing,
  their axis (from the bars' own vertices: a turned ladder's rungs are
  diagonal) and their radius (`rung_radius`, which `climb_ladder` passes on,
  so palms close over and soles stand on rungs of their real thickness), the
  wall's face and top. The controller grips rungs 9 cm in
  front of the wall (terrain_base's build); `climb_ladder` warns when the
  measured gap differs. Keep rungs and rails out of the walking world (their
  wall is what the controller walks against); the feet stay out of the rungs
  through the controller's `contact_world`, which `climb_ladder` sets to every
  visible mesh unless one was given.
- `takeoff_edge(xy, heading)`: where the ground ahead falls away.

## Tests — `blender/tests/maneuvers/`

```bash
bash run_blender.sh <repo>/blender/tests/maneuvers/test_seating.py --vrm aletheia
bash run_blender.sh <repo>/blender/tests/maneuvers/test_maneuver_moves.py --vrm aletheia [--only parkour,ladder]
bash run_blender.sh <repo>/blender/tests/maneuvers/test_emotes.py --vrm aletheia
bash run_blender.sh <repo>/blender/tests/maneuvers/test_example_bench.py --vrm aporia
bash run_blender.sh <repo>/blender/tests/maneuvers/test_robot_seat.py
bash run_blender.sh <repo>/blender/tests/controller/render_shots.py <repo>/blender/tests/maneuvers/out/seating_aletheia_shots.json   # the stills (renders)
```

Each builds simple geometry (`_mnv_stage.py`: chairs with backrests and
stools, a bench, covers, blocks, walls, a ladder of rungs, a trench), bakes
on the CPU, prints PASS / FAIL and saves `out/<tag>.blend` with its shot
list. `--trace a-b` (seating) prints the hips, ankles and knees per frame;
`--vrm claude_robot` runs the seats on my robot body (its residuals below).
The visible boots are checked through each whole sit, every 2 frames, not
only at the seated frame, and so is the rest of the body
(`_mnv_stage.whole_seat_checks`: the seat skin on the pan through the
stand-up too, nothing of the body in the chair's back and nothing of it or
its coat out behind it, the body out of the pan and the legs; `floor_checks`:
the body out of the floor through a ground sit's crossfades).

- `test_seating.py`: two chairs at angles (0.45 m, and 0.56 m with its
  backrest toward the approach), the ground, the camera; a second take of
  `seat_on`'s options (a stool, a chair sat facing its back, the lying ground
  sit, `face_camera(camera=)`).
- `test_maneuver_moves.py`: every move at its own heading (35°, −60°, 120°,
  160°, 90°): a vault, a mount and a 1.2 m drop; a ladder; a 3.2 m scramble
  at a non-default rate; a 2.0 m wall; a running vault, a gap jump over a
  trench and a jump back from standing; gestures over a walk and a run.
- `test_emotes.py`: the eight expressive clips on the controller with each
  facing, and the stationary seat, ground sit and turned emote.
- `test_example_bench.py`: `examples/obstacle_course.js`'s sit stop on its
  own character (`aporia`): its bench (a plain box, no back), `faceY` π,
  the sit-down reversed at 1.25x to stand, the walk on with the cheer over
  it.
- `test_robot_seat.py`: `seat_on` on a VRM my robot body drives: the body
  placed and seated through its own state, the plan kept for its bake, and
  the body's own bake seating it by the plan (the hips on its target, the
  seated skin on the pan).
- `test_start_seated.py`: `seat_on(instant=True)`: a take that opens seated
  on a chair, stands up and walks off, then a cut into a 0.56 m chair in the
  fidget loop, a stand-up and a walk (the springs reset and settled at the
  cut).

The spring chains through seats, lying down and the walks between are the
characters family's test (`blender/tests/characters/test_take_springs.py`,
[controller.md](controller.md#springs-ride-the-take)).

## Not yet ported

- A stand-to-ground clip: the library has none, so a ground sit is a
  crossfade (eased, held out of the floor).
- My robot body's ground sit is a long sit, not the library's cross-legged
  clip: its hips flex 98° at most and its knees 112°, so the legs cannot fold.
  The ankles are carried along the floor to a place straight ahead of each
  hip, each leg solved to it on its own bones with the knee's hinge turned
  from the clip's to across the body, the knees bent 12°, each heel resting
  on the floor, in the settle, the crossfades and the keyed frames. The
  library has no floor clip the robot's joints can hold.

Known residuals (each measured by the tests; the JSON reports in `out/` list
the frames):

- A coat skinned to the body without cloth presses into a chair's back (it
  never comes out of it) and into a seat's pan where it falls past the edge,
  and on the ground goes under the floor where it hangs under her (hidden).
- A thigh pressed over a pan's front edge: up to 1.1 cm, a few vertices.
