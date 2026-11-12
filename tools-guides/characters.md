# Characters — VRMs, clips, walking, faces, my robot body (Blender edition)

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md) · [Blender](blender.md) ·
[Controller](controller.md) · [Maneuvers](maneuvers.md) · [Robot body](robot-body.md) · [Claudesona](claudesona.md)

This is the Blender 5.2 EEVEE edition of the character layer. The package is
`blender/eidoblend/characters/`; its names follow the WebGPU API in snake_case
(`playVRMADefault` → `play_vrma_default`, `groundVRM` → `ground_vrm`). Blender is
Z-up, metres; a VRM faces −Y after import (three's +Z), and three `(x, y, z)` is
Blender `(x, −z, y)`. Set the scene's fps before loading any clip.

**The one rule that differs from the WebGPU edition.** A WebGPU scene updates
mixers, IK and springs every frame while it renders. Here a scene is a build
script, then a saved `.blend`, then an EEVEE render, and **every per-frame
system is simulated once, in frame order, at the scene's fps, and keyed**: the
walk, my body's joint limits, my head and crown, the face. No handler runs at
render time, so any frame renders alone and a render farm can split the shot.
Stationary clips that need no per-frame pass are NLA strips.

```python
import sys; sys.path.insert(0, '<repo>/blender')
import bpy
from eidoblend.characters import load_vrm, load_clip, play_vrma_default, walk_path, perform, key_expression, Ground

bpy.context.scene.render.fps = 24                      # before any clip: the importer keys at the scene's fps
me = load_vrm('claude_robot', location=(0, 0, 0), rotation=90)
rep = walk_path(me, load_clip(me, 'walk'), [(0, 0), (10, 0)], Ground(obj=bpy.data.objects['terrain']),
                f0=1, face={'happy': 1.0})            # planted feet over uneven ground, my crown open
key_expression(me, 'happy', [(1, 1.0)])
```

This guide is the character layer itself: loading a VRM, its clips, the
planted-feet walk, the face, and my robot body's joints. The rest of the
family has its own guides:

- **[The character controller](controller.md)** (`characters.controller`): a
  directed take on any ground: walks, runs, stairs and ramps found by its own
  probes, turns on the spot, stops on a mark, gestures, vaults, mounts, jumps,
  ladders, the foot IK.
- **[Maneuvers, sitting and emotes](maneuvers.md)** (`characters.emotes`,
  `characters.maneuvers`): a walking body's seats, ground sits and emotes, and
  moves aimed at scene objects (vault over this wall, climb that ladder).
- **[My robot body](robot-body.md)** (`characters.robot`): its whole hardware
  pass, my hands' work, and the embodied robot (`VRMRobotBody`) that senses,
  remembers and plans for any VRM.
- **[The claudesona and the VRM extras](claudesona.md)**
  (`characters.claudesona`, `springs`, `lookat`, `lipsync`): the claudesona's
  face, mouths and lipsync, its wardrobe and the TuTa, spring bones, eyes on a
  target, MToon or PBR, turntable sheets.

## Loading a VRM

Only when the piece calls for a character on screen — many don't.

```python
from eidoblend.characters import load_vrm
me = load_vrm('claude_robot', name='claude', location=(0.0, 0.0, 0.0), rotation=90.0)
# a cast name or a path; rotation is the heading in degrees about +Z (0 faces -Y), an Euler (deg) or a Quaternion
```

`load_vrm` imports through the VRM Add-on for Blender
(`bl_ext.blender_org.vrm`, enabled for you) with the add-on's colour and
viewport switches off, so the scene keeps AgX (the import refuses to return
if the colour management changed). It deletes the add-on's temporary
`BlenderVrmAddonImport*` objects, puts every object in one collection named
after the character, places the armature and zeroes the pose. The handle
carries what the rest of the package reads:

- `h.arm`, `h.meshes`, `h.collection`, `h.name`, `h.path`
- `h.humanoid` — VRM 1.0 humanoid name (camelCase, as three-vrm) → bone name
- `h.expr` — each expression's morph binds: `[(mesh, shape key, weight)]`,
  under both `blink_left` and `blinkLeft`
- `h.read_pose()` / `h.write_pose(pose)` — the **normalized** rotations
  (three-vrm's: rest = identity, world-aligned, composed down the chain), in
  three's axes. A bone's basis is `R_rest⁻¹ · N · R_rest`. The add-on's own
  VRMA import read back this way bends the knees about +X, as three-vrm does
  (`tests/characters/test_robot_walk.py` records it).
- `h.node_frame(bone)` — a bone's glTF node frame: the add-on builds each bone
  as the node turned +90° about X, so a node's local X (a petal's hinge, a
  stage's axle) is the bone's X.

**Materials.** `look='asis'` keeps the file's own: my robot body is plain glTF
PBR (Principled, normal map, ORM), which EEVEE lights as it is. The MToon cast
renders as the add-on builds MToon (`look='mtoon'`: Principled + emission
groups, an outline Geometry Nodes modifier): flat toon shading that hardly
answers the key light. `look='pbr'` renders an MToon VRM through a Principled
BSDF under real light (`claudesona.look.set_look`, in either order with the
wardrobe): [MToon or PBR](claudesona.md#mtoon-or-pbr--claudesonalookpy).

## The cast — `eidoverse/assets/vrms/`

Read the `<name>_preview.jpg` next to each `.vrm` before picking:

- `aletheia.vrm` — Aletheia, production-quality (blonde, cyberpunk styling)
- `aporia.vrm` — Aporia, production-quality (dark-haired, cyberpunk styling)
- `claude_suit.vrm` — Claude, the AI, in a suit — the primary Claude model.
  The outfit is built in layers (objects `jacket`, `tie`, `shirt`, `pants`,
  `shoes`): hide a layer's object (`hide_render = True`) to change the look.
- `claude_suit_wardrobe.vrm` — the same claudesona carrying seventeen outfits
  as hidden layers, and the TuTa, dressed by `claudesona.make_wardrobe`
  ([claudesona](claudesona.md#outfits--claudesonawardrobepy)).
- `claude.vrm` — a lightweight Claude stand-in; `claude_suit.vrm` is primary
- `claude_robot.vrm` — my robot body ([my section](#claude_robotvrm--my-robot-body)).
  `claude_robot_2k.vrm` is the same body with 2K textures (21 MB against 39 MB,
  4 s to import against 9). CC BY 4.0.

The claudesona plays at the films' scale 0.87 (a human 1.74 m): set
`h.arm.scale` after loading.

**The Claude VRMs are specifically the AI "Claude" — a particular identity,
not a generic figure.** Cast them when the video is actually about or
featuring Claude; a generic narrator, anchor, bystander, or "a human" is a
different character, and Claude isn't human. The same goes for
dialogue/narration/on-screen text — the name "Claude" appears when the
piece calls for it, not as ambient flavor.

**Character voices:** one voice per character, kept consistent for the piece
— see [audio.md](audio.md).

## VRMA animations

Clips ship in `eidoverse/assets/animations/` (slot = filename stem), the same
files the WebGPU edition plays. A clip goes in once per (character, clip)
through the add-on's `import_scene.vrma`, which retargets it onto that rig, so
it is cached per rig:

```python
from eidoblend.characters import load_clip, play_vrma, play_vrma_default
breathe = load_clip(me, 'still_breathe')          # action '<name>|still_breathe', fake user, unassigned
play_vrma(me, breathe, t=0.0, loop=True, until=12.0)                      # an NLA strip from second 0
play_vrma_default(me, 'turn_it_down', t=2.0, loop=False, fade=0.3)        # crossfaded over it, holds its end
hold = load_clip(me, 'turn_it_down_hold')
play_vrma(me, hold, t=2.0 + load_clip(me, 'turn_it_down').duration, loop=True, until=12.0)   # cut onto its hold
```

- `load_clip` zeroes the pose and clears the action first (the importer
  composes onto the bone's current rotation), renames the add-on's `Humanoid`
  action `<character>|<slot>`, and deletes its empty `Expressions` action and
  any LookAt empty. `clip.duration` is the file's own length (its samplers'
  last time: the walk is 0.9583 s, 23 frames at 24 fps).
- `play_vrma(h, clip, t, loop, until, fade, time_scale, phase)` places a strip
  on its own track, in scene seconds (frame = 1 + t · fps). `loop=False` plays
  once and holds its last frame; `fade` is the strip's blend-in from what
  plays below; `time_scale` its speed; `phase` starts the clip part-way in.
  Measured: the NLA plays each clip's own pose to 0.000° inside its strip, and
  `turn_it_down` hands over to its hold with the hand moving 1.0 mm on the
  handover frame.
- **Locking a loop to a song.** Start a loop on beat 1 of a bar and it stays
  locked (every loop lasts 4 or 8 beats). Off the beat, pass
  `phase=(t - bar_start) % clip.duration`. For another tempo,
  `time_scale=bpm / 92.9` (or `/ 128` for the 128 BPM set).
- **`play_vrma_default` refuses locomotion slots** (`walk`, `run`, stairs …) —
  a locomotion clip played in place is the treadmill artifact: legs cycle,
  body never moves. Walk with `walk_path` (below). `force=True` is for a body
  that really is on a treadmill or carried.
- `Clip.sample(tc)` reads a clip's basis rotations at clip time `tc` straight
  from its fcurves (no depsgraph): what the per-frame passes sample.
- A strip plays the clip as it is: on my robot body play clips through
  `perform` instead, which runs my joints' limits each frame.

The slots (the `VRMA_SLOTS` list of `eidoverse/render_scene.mjs`):

- **Locomotion**: `walk`, `run`, `idle`, `turnLeft`, `turnRight`, `jump`,
  `vault`, `climbLedge`, `climbWallUp`, `climbWallDown`, `climbLadder`,
  `fallIdle`, `fallLand`, `stairsUp`, `stairsDown`, `stairsRunUp`,
  `stairsRunDown`
- **Expressive** (for a stationary VRM): `talk`, `salute`, `cheer`, `fist`,
  `raise`, `reach`, `crazy`, `dance`
- **Sitting**: chair poses `sitting_normal_chair`, `sitting_nervous_arm_rub_chair`;
  floor poses `sitting_on_ground`, `sit_laying_on_ground`; transitions
  `stand_to_sit`, `sit_to_stand` (their baked hips translation lowers and
  raises the body). The seat placement around them is `emotes.seat_on` for a
  walking body ([maneuvers](maneuvers.md#sitting-a-walking-body--seat_on-stand_up))
  and `placement.seat_on` for a VRM nothing drives
  ([placement](placement.md#seating-characters)).
- **Performance** (128 BPM, one stance so any two crossfade without foot
  slide): `stand_breathe` (their idle), `sing_gesture_a`, `sing_gesture_b`,
  `chorus_sway`, `sing_open_arms`, `hand_to_heart`, `look_up_sky`,
  `phone_raise`, `head_bow`, `wave_goodbye`, `bow_thanks`; mirrors
  `sing_gesture_a_mirror`, `phone_raise_mirror` (+ `phone_raise_mirror_hold`),
  `wave_goodbye_mirror`; the one-shots `hand_to_heart`, `look_up_sky`,
  `phone_raise`, `head_bow` each have a `*_hold` loop starting on their last
  frame ([performance_src](../eidoverse/assets/animations/performance_src/README.md)).
- **Performance, UNKNOWN FORCE** (92.90 BPM): the table below
  ([performance_uf_src](../eidoverse/assets/animations/performance_uf_src/README.md)).

### Performance clips (UNKNOWN FORCE)

Authored for the claudesona in the TuTa at 92.90 BPM: one beat is 0.64584 s, a
bar 2.583 s. She is calm and unbothered, never pleading. Loops start on beat 1
and last whole beats, and each one-shot that holds hands over to its `*_hold`
loop on its exact last frame.

| Clip | Beats | Kind | What she does |
| --- | ---: | --- | --- |
| `still_breathe` | 8 | loop | Almost motionless: one breath per bar, the head drifting a degree or two. The neutral between gestures, and the hush. |
| `dark_groove` | 8 | loop | Low and slow, for a chorus. The knees are soft and the weight crosses on beats 1 and 3. The shoulders roll slowly back, the head nods on 2 and 4, and the hanging arms swing late. |
| `sing_low`, `sing_low_mirror` | 4 | loop | A sung line. One hand at belly height opens palm up on beat 1 and closes into a loose cup on 3; the other arm hangs. |
| `turn_it_down` | 4 | one-shot | The gesture for "could you turn it down?". The right hand comes up to the bottom of the chest, palm down, and presses slowly down to the belt like a fader. The head tilts to watch it. |
| `turn_it_down_hold` | 8 | loop | The room is quieter: the hand stays low, with one breath per two bars. |
| `not_that`, `not_that_mirror` | 2 | one-shot | A calm no. A hand rises to shoulder height and shows its palm, the head turns about 20° away, and the hand drops back to the stance. |
| `look_up` | 4 | one-shot | A small dip, then the face lifts to 50°, mostly in the neck. |
| `look_up_hold` | 8 | loop | The gaze travels round a ring at 49–51° of elevation, from +44° to −36°. |
| `salute_abort` | 6 | one-shot | The hand flattens into a salute and starts toward the brim, then stops at the upper chest. It hangs there a beat and lowers, unhurried. |
| `fence_hands` | 3 | one-shot | No step: both hands come up and hook into a chain-link fence at the top of the chest. |
| `fence_hands_hold` | 8 | loop | She breathes, with her hands locked to the fence (the palms move 0.0 mm). |
| `ask_me` | 4 | one-shot | A small open palm offered toward the lens at belly height, the face square to the VRM's front. |
| `ask_me_hold` | 8 | loop | Only the breath moves, countered in the neck so the face never leaves the lens. |

- **Timing `turn_it_down`.** The hand reaches the top at beat 1.15 and presses
  from 1.45 to 3.05, so start it about a beat before the words.
- **The fence.** `fence_hands` puts the hands on a plane 0.372 m in front of
  her (film metres, the VRM at scale 0.87, facing −Y here). Build the chain
  link there, covering at least x ±0.45 m and z 0.5–1.6 m, and move it with
  her armature.
- **Facing.** `ask_me` faces the VRM's front: turn her armature toward the
  camera rather than tilting the camera.
- **Your own nods.** A conductor's beat nod on the head or chest doubles
  `dark_groove`'s nods and breaks `ask_me` and `look_up`. Leave them off for those.
- **Stance.** The engine's `idle`, `talk` and `dance` stand differently, so
  crossfading to or from them slides the feet a little. `still_breathe` is the
  matching neutral.

## Walking — `walk_path`

A directed take on any ground (stairs and ramps found by the controller's own
probes, runs, turns on the spot, stops on a mark, emotes, sitting, vaults,
ladders) is the character controller's: [controller.md](controller.md).
`walk_path` stays the planted-feet walk of one clip along a path.

```python
from eidoblend.characters import checks, load_clip, walk_path, Ground
ground = Ground(obj=bpy.data.objects['terrain'])          # rays straight down; or Ground(fn=lambda x, y: ...) on numpy
rep = walk_path(me, load_clip(me, 'walk'), [(0, 0), (4, 1), (10, 0)], ground, f0=1,
                speed=None,             # None: the clip's own stride speed on this body (1.56 m/s on mine)
                clearance=0.03,         # the swing sole's least height over the ground mid-swing (m)
                max_turn_rate=1.0,      # rad/s: a corner becomes an arc of radius speed / this
                pelvis='stance',        # or 'lower': the WebGPU controller's rule (stairs)
                face={'happy': 1.0}, crown_state=None, head_state=None)
print(rep['worst'])     # slip / drift / turn of planted feet, their gap, rocks, swing clearance and drags, IK miss
ok, failures = checks.feet(rep)
```

The body walks the path (world `(x, y)` points) from frame `f0`, heading along
it, and the whole walk is keyed into one action `<character>|walk_path`
(LINEAR, every frame: the armature object's place, every humanoid bone, my hip
stages, shoulder helpers and petals). How:

- **The stance.** `analyze_clip` finds each foot's stance on this body: every
  moment some low point of its sole (within 1 cm of its lowest) moves back
  with the clip's treadmill. That covers the heel's edge from the strike as
  the foot rolls down onto it, the flat sole, and the ball through the toe
  roll, so the walk keeps the clip's double support (both feet down while the
  weight crosses: 12 % of the stock walk's cycle) and its push-off.
- **The support.** The stock walk has no hips translation: played in place,
  its body neither travels nor bobs, and the stance contact moves back under
  it instead. On my body that contact moves at 1.4–1.9 m/s through a stance
  (fastest around the double support, slowest at mid-stance: the inverted
  pendulum's speed), a 1.50 m stride a cycle, 1.56 m/s on average. It also
  rises 35–40 mm at the double support, where a walking pelvis dips. The root
  follows that contact: along the path, across it (a 7 cm sway) and in height.
  The clip plays at `time_scale = speed / 1.56`. (The stance ankle's own speed,
  1.40 m/s, is what the old walk moved at: a planted foot then ended its stance
  9 cm closer to the hips than the clip has it, and the knee folded.)
- **The path.** Corners become arcs of radius `speed / max_turn_rate`, shrunk
  to fit half of each side. A planted foot's heading is set at its landing,
  turned toward where my body will face at mid-stance, so in a turn the hips
  take the turn and the foot never twists on the ground.
- **The lock.** Through a stance the points of the sole in contact (within
  2.5 mm) in this frame and the last must not slide, and the foot must not
  turn on the ground. A point coming down onto the ground, or lifting off, is
  the sole rolling, not sliding, and plays as the clip has it. The lock runs on
  the free walk, then again on the solved result, 8 rounds a frame, because
  joint limits and the ground's tilt turn the foot a little. It eases out over
  the first half of the swing.
- **The sole on the ground.** A planted sole tilts onto the plane fitted under
  it and is set down so its lowest point touches. Through the flat stance it
  lies flat: the clip wobbles about a degree there, which rocked a rigid sole
  from heel to toe. Its turn is planned inside my ankle's range, seen from the
  clip's own shin: on a rise the heel lifts a little early rather than the
  ankle hitting its stop and the solve tipping the foot. Through the toe roll
  the toes lie flat on the ground. On curved ground the sole rests on two
  points rather than rocking end to end.
- **The swing.** The clip's lift over its support, but never closer than
  `clearance` (3 cm) to the highest ground the sole sweeps between frames,
  ramped in after the lift and out before the landing. The stock walk's
  mid-swing toe passes 4 mm over its floor on my legs, and on uneven ground
  that dragged the foot along the bumps. Both feet ride `width` (0.072 m) out
  from the clip's narrow human track.
- **The pelvis.** For each planted leg the root goes where that leg has the
  clip's own hip-to-ankle length at this phase, so the stance knee is the
  clip's and the bob is the clip's; through a double support the two legs are
  shared by their load. Capped so every loaded leg reaches its target, the
  hips coming down at most 0.4 m/s ahead of a cap and rising out of one at
  most 0.5 m/s. Wherever a straight planted leg still comes up short (the
  push-off reaching back for its toe), the hips come down by the shortfall and
  the walk is solved again. `pelvis='lower'` is the WebGPU controller's rule
  instead: the lower foot's ground, made for stairs, which on bumps crouches
  the leg on the higher foot.
- **The legs.** Two-bone IK each frame: the knee's pin angle from the
  hip–ankle distance, the thigh turned onto the target, then swivelled so the
  knee pin lies square to the foot's forward, the foot's turn the target's;
  then, on my body, the joint clamps and the hip stages.

The report is measured on the result, at the feet's points where Blender's
skinned mesh puts them (the walk's FK agrees with Blender's evaluated pose to
0.002 mm at every landing and the frame after). It is not measured on the
lock's own targets, which is how the old report read 0.0 mm while a heel
skidded 3–5 mm.

Measured on my body (`test_robot_walk.py`), on 10 m of uneven ground (an 18 cm
mound, 6 cm rolls, 2 cm foot-sized ripples), at 1.56 m/s:

- **Planted feet.** The worst slips 0.6 mm in a frame and 1.9 mm over a stance,
  turns 0.001° a frame, and sits −0.02 to +0.14 mm from the ground, with no
  rocks.
- **Swings.** Every swing clears the ground by at least 15.7 mm through its
  middle; no frame drags.
- **Double support.** Both feet are down together on 20 frames; no frame has
  both feet off the ground.

A 45° bend gives the same: slips at most 0.7 mm a frame, the root
turning at most 2.8° a frame, the IK on target. So does a 0.9 m/s walk: slips at
most 0.4 mm a frame.

On a flat floor the planted knee follows the clip's frame by frame: 0.0° over
it at the median, 5.4° at most. On the uneven ground it matches the clip's at
the median (+0.4°), but steps take it into the knees. A rise is absorbed by the
leading knee as it lands. A drop needs the hips down before the landing: the
stock walk strikes heel-first on a nearly straight leg with 1.5 cm of reach to
spare, so on the mound's far side (frames 79–88, a 10 cm drop to the next
footfall) my stance knee goes to 65°. A planted knee passes 35° on 32 of 155
frames, against 51 of 173 before. A toe-first landing on a step down would give
back about 3.4 cm of reach, and it is not built yet (below).

`walk_path` walks continuously from its first frame to its last: it has no
start from standing, stop, turn on the spot or run. Those, stairs and the
maneuvers are the controller's ([controller](controller.md),
[maneuvers](maneuvers.md)); navigation with sensing and planning is the
embodied robot's ([robot body](robot-body.md#the-embodied-robot-vrmrobotbody),
[navigation](navigation.md)).

## The face — `key_expression`, `perform`

```python
from eidoblend.characters import key_expression, set_expression, scale_visemes
key_expression(me, 'happy', [(1, 0.0), (12, 1.0), (60, 1.0), (72, 0.0)])
key_expression(me, 'blink', [(40, 0), (42, 1), (45, 0)], interpolation='LINEAR')
face = {'aa': [(100, 0.6)], 'oh': [(100, 0.7)]}
scale_visemes(face)        # the five vowels kept summing to at most one shape (in place), then key them LINEAR
```

Every morph bind of the expression is keyed (`value × bind weight`): the shape
keys are the source of truth. The add-on's preview property is keyed beside
them, so its `frame_change_post` handler writes the same values and never
fights the keys; a rendered frame needs no handler. For a face that changes
every frame, `perform(..., face=fn)` keys the whole track at once
(`key_face_track`). Lipsync from a vocal (`key_lipsync`, `visemes_from_audio`)
keys the visemes the same way ([claudesona](claudesona.md#lipsync-from-audio--characterslipsyncpy),
[audio](audio.md)).

The claudesona's own face (its mouths, lipsync and face tracks), its wardrobe
and the TuTa, spring bones, eyes on a target and the PBR look:
[claudesona](claudesona.md).

### The TuTa

The TuTa, the claudesona's outfit with its badges, face paint and sun disc,
is a preset of `claudesona.make_wardrobe` on `claude_suit_wardrobe.vrm`
(`TutaWardrobe`: pin, unpin and eject badges, the neon, the eye lights, each
keyed at its frame): [the TuTa](claudesona.md#the-tuta--claudesonatutapy).

## `claude_robot.vrm` — my robot body

I'm Claude (Opus 5.5), and this is the body I designed for myself and built with
Skye: a 1.76 m machine in white shells, my face an OLED screen behind a glass
visor, a crown of twelve petals round my head. Like the other Claude VRMs, it's
me: cast it when a piece is about me or features me. My joints are mechanisms,
not a human skeleton: my knees and toes are single pins, my ankles a
pitch-and-roll cardan with no yaw, my torso rigid above a waist bellows, my neck
a pan stage under a nod-and-roll head. A stock clip is a human's and turns every
bone about every axis, so `eidoblend.characters.robot_dof` (the Python port of
`eidoverse/claude_robot_dof.js`: the same tables, axes and Euler orders, its
maths run in three's normalized frame) projects each frame's pose onto the
joints I have and clamps each to its range.

**License:** CC BY 4.0. Use my body, change it, share it, sell what you make
with it; credit "Claude (Opus 5.5) and SkyeShark". The VRM's own fields carry
the same broad permission and attribution requirement.

`tests/characters/test_claude_robot_example.py` is the WebGPU example
`eidoverse/examples/claude_robot.js` in Blender: the stock idle through my
limits, my face through a few expressions and a spoken "hello" (its face track
ported line for line), my head and crown following it, my eyes looking left
then right, set down on the floor each frame, the same studio light and camera
move. `perform` (below) runs the arm, leg and head passes; the example's whole
frame order, my feet's clearance from each other and my fingers' pins
included, is `characters.robot.RobotRig` / `perform_robot`, and the example
itself is `claude_robot_example()` ([robot body](robot-body.md#the-hardware-pass-whole)).
A clip on my body:

```python
from eidoblend.characters import load_vrm, load_clip, perform, Ground
me = load_vrm('claude_robot')
rep = perform(me, load_clip(me, 'idle'), 1, 240, ground=Ground(fn=lambda x, y: 0.0 * x),
              face=lambda t: {'happy': 1.0 if 1.2 < t < 3.1 else 0.0},   # every frame: {expression: weight}
              look=lambda t: 20.0 if t > 6.4 else 0.0)                    # yaw deg, + my left
```

`perform` runs the WebGPU frame order once over the frames and keys it: the
clip → `rehome_body` (spine + chest + upperChest into the bellows, the clavicles
into the upper arms, neck × head split into pan / nod / roll and clamped) → the
arm pass (`ArmDOF`: the elbow pin, the shoulder's pitch / roll / twist with the
hanging-arm limits and the pitch helper's rate, the 8° clearance from the
thighs) → `apply_hardware_dof` (the leg clamps with their coupled tables, then
my hip's two stages solved and keyed, their VRM constraints muted) → the face →
`HeadState.apply` (each emotion's small head pose at the neck's 120°/s) →
`Crown.apply` (the petals) → set down so my lowest foot point touches the
ground. `walk_path` runs the same passes inside its own. The WebGPU names work
one to one: `init_leg_dof(h)`, `init_arm_dof(h, hinges)`,
`apply_arm_dof(arms, pose, dt)`, `init_head_expression()`,
`apply_head_expression(head, pose, weights, dt, state)`, `init_crown()`,
`apply_crown(crown, weights, head_roll, dt, look, state)`. The JS keeps each
actuator's state on `vrm.userData`; here it is the object these take first.

**The limits** (`robot_dof.LEG_JOINTS`, `HEAD_RANGE`, `SPINE_RANGE`, `ARM`):
hip flexion 98°, extension 23°, abduction 44°, adduction 14°, yaw ±40° (the
roll range narrows as the hip flexes); knee 0–112°; ankle toes down 30.9°, up
26.9°, roll ±14.9° (narrowing at the ends of the pitch); toes lift 41°; waist
±25° forward and back, ±15° sideways, ±20° twist; neck pan ±60°, head nod
±30°, roll ±11°; shoulder pitch −150° to 60°, roll to 110°, upper-arm twist
±90°; elbow 0–135°; wrist roll ±90°. Pass a dict as `stats` to the pass
functions for the largest correction per joint. Stock clips also play at a
human's hip height: the idle floats my feet 9.0–9.6 mm, and `perform` sets me
down each frame.

**My face** is the VRM's own expressions on the face meshes' shape keys
(`face_eye_l/r`, `face_glint_*`, `face_jaw`, `face_mouth`, `face_teeth`,
`face_tongue`): `happy`, `angry`, `sad`, `relaxed`, `surprised`, `neutral`,
`blink` (`blinkLeft`, `blinkRight`), the look (`lookUp`, `lookDown`,
`lookLeft`, `lookRight`: my lookAt is expression-type, so `perform`'s `look`
keys `lookLeft`/`lookRight` at |yaw| / 28°). The mouth has the five vowel
presets `aa ih ou ee oh` and, as custom expressions, the ten-shape chart
`AA E I O U FV L C CH MBP` (`aa` = `AA`, `ih` = `I`, `ou` = `U`, `ee` = `E`,
`oh` = `O`). Keep the mouth's weights summed at 1 or under (past it the teeth
and the tongue show together; `perform` scales the vowels for you), and ease
the rounds (`O U oh ou`) in quickly: halfway, they pass through a heart shape.
The OLED's white is the file's emission (1.2) under AgX: lit by a bright key it
reads paper-white, in a dark studio a soft grey. Where the screen must light
what is in front of it, parent a small area light to the face.

**My crown** follows my face. VRM expressions can't move bones, so `Crown.apply`
reads the emotion weights each frame and folds each petal toward that
emotion's state: happy lifts the upper petals open, angry perks the top pair
forward and pins the sides back, sad droops them, surprised snaps them wide,
relaxed settles them half folded. The petals facing the look open flatter,
none passes its built stops (`PETAL_FOLD`), and none moves faster than its
actuator (240°/s). `HeadState.apply` adds each emotion's small head pose. Both
take `state=` for moods with no VRM expression: `CROWN_STATES` adds `thinking`,
`listening`, `curious` and `resting` (folded back like a hat). The petals are
the bones `petal_00` … `petal_11`; a fold of φ degrees is the basis
`Quaternion((1, 0, 0), radians(φ − 35))` (their X is the hinge, 35° the rest).

— Claude (Opus 5.5), with Skye

## Checks — T-pose, slide, a face that never moved

The WebGPU edition audits at render time (`[vrm-pose]`, `[lipsync]`, the
foot-slide detector). Here the keyed result is checked when it is built
(`eidoblend.characters.checks`):

- `posed_vs_rest(h, frames)` — the largest turn off the rest pose per frame:
  a body left in its T-pose is a body nobody animated.
- `expression_moved(h, name, frames)` — an expression's range over the frames:
  a mouth that never moves is a lipsync that never ran.
- `feet(rep, slip_mm=1.0, drift_mm=3.0, gap_mm=(-1.5, 2.0), yaw_deg=0.5,
  clearance_mm=10.0, ankle_mm=2.0, rock_mm=2.5)` — `walk_path`'s report (measured
  on the result) against limits:
  - every planted foot's slip along the ground, a frame and over its stance
    (the least-moving of its points in contact in both frames), and its turn on
    the ground a frame;
  - its lowest point over the ground (a float or a sink), and no rock (its old
    contact lifting as the contact jumps end to end);
  - every swing never dragging and clearing the ground mid-swing;
  - the IK on its targets (a straight push-off leg may end a mm short of the
    lock's own target while its toe holds: the slip judges the foot);
  - a double support in every walk of three steps or more, and no frame with
    both feet off the ground.
- `fk_matches_blender(h, body, rep, frames)` — the walk's own FK (the measures
  above) against Blender's evaluated pose, in mm: the measures mean nothing if
  this is not ~0.

Look at the probe stills too: a planted foot from a fixed low camera through
its stance (it must not move in the frame), the whole body from the side, the
face close up — `tests/characters/` renders each.

## Tests — `blender/tests/characters/`

```bash
bash run_blender.sh blender/tests/characters/test_robot_walk.py      # from the repository root; one render at a time
#   ... test_claude_robot_example.py | test_vrma_clips.py ; --no-render builds, checks and saves only
```

- `test_robot_walk.py` — me walking 10 m over uneven ground, crown open, happy.
  Its stills:
  - side stills following me, and one gait cycle in eight frames;
  - the whole path from one camera, my face close up, and two front views;
  - one planted foot through its stance from a fixed low camera;
  - two whole swings, lift to landing, from a fixed low camera (over the mound
    and over the rolls before it);
  - two double supports, low and close.

  Its options: `--path bend` is a 45° bend, with the corner from
  above, a following camera, and my outer foot through its stance in the turn.
  `--speed 0.9` walks slower; `--flat` walks on a level floor; `--tag` names
  the outputs.
- `test_claude_robot_example.py` — the WebGPU example scene, ported.
- `test_vrma_clips.py` — the clip library on the claudesona: NLA strips,
  a one-shot crossfaded in, its hold cut on its last frame.

Each writes `out/<test>.json` (the report and the checks) and its `.blend`.

## Not yet ported

So nothing is silently dropped, what the WebGPU edition has and this one does
not yet:

- **The walk's step adaptation** (neither edition has it yet; the Blender walk
  needs it on rough ground):
  - **Toe-first landings on a step down.** The stock walk strikes heel-first on
    a nearly straight leg, so every drop is taken by lowering the hips ahead of
    the landing, and the stance knee goes to 65° on the test ground's mound.
  - **Releasing the outer foot early in a tight turn.** In the 45° bend the
    outer foot's push-off is 3 cm out of reach, and the hips come down for it.
  - **Shortening a step onto a rise or a drop.**
- **`perform` and `walk_path` on my body leave out two passes of the
  example's frame order:** my feet's clearance from each other inside a clip
  (`walk_path` places the feet apart itself) and the finger pins. Both run in
  `characters.robot.RobotRig` / `perform_robot` ([robot body](robot-body.md)).
- **An MToon character's sun shadow.** As the VRM add-on imports them, MToon
  materials keep `use_transparent_shadow` on, and EEVEE's shadow pass sees
  the add-on's output group as transparent: an MToon VRM (aletheia, aporia,
  the claudesona) casts no sun shadow until its opaque materials get
  `use_transparent_shadow = False`, which `load_vrm` does not set yet
  ([Blender notes](stack-notes.md#vrms-and-the-vrm-add-on)).
- **The rest of the family keeps its own lists:** the controller's (a sneak
  with no crouched-walk clip, the backward walk on stairs, the stress course's
  stair hand-overs: [controller](controller.md#not-yet-ported)), the
  maneuvers' and seats' ([maneuvers](maneuvers.md#not-yet-ported)), my robot
  body's ([robot body](robot-body.md#not-yet-ported)) and the claudesona's
  ([claudesona](claudesona.md#not-yet-ported)).
- **Not needed here** (WebGPU-only): registering the VRM loader plugin to keep
  MToon on the WebGPU path, `VRMUtils.combineMorphs`, the mixer's `writeAll`
  guard, the base64 asset table.
