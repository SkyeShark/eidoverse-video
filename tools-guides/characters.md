# Characters — VRMs, the controller, movement, emotes, sitting

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

## Loading a VRM

Only when the piece calls for a character on screen — many don't. The
`loader.register(VRMLoaderPlugin)` line is what keeps MToon on the WebGPU
path; without it the plugin falls back to a WebGL ShaderMaterial and the
character renders solid black with only the eyes visible.

```js
const loader = new globalThis.GLTFLoader();
loader.register(p => new globalThis.VRMLoaderPlugin(p));
const buf = globalThis.b64toArrayBuffer(globalThis.ASSETS.character_vrm);
const gltf = await new Promise((res, rej) => loader.parse(buf, '', res, rej));
const vrm = gltf.userData.vrm;
scene.add(vrm.scene);
// Idle first — VRM rest pose is T-pose, and manual bone rotations off a
// T-posed rig give cruciform stances. (Exception: controller scenes — the
// controller owns ALL animation; skip the pre-played idle there.)
await globalThis.playVRMADefault(vrm, 'idle', { loop: true });
globalThis._vrm = vrm;
```

After `VRMUtils.rotateVRM0(vrm)`, the VRM faces +Z — a camera at positive Z
looks at the face, so `vrm.scene.rotation.y = 0` faces the camera.

## The cast — `eidoverse/assets/vrms/`

Read the `<name>_preview.jpg` next to each `.vrm` before picking (same as
fetched props):

- `aletheia.vrm` — Aletheia, production-quality (blonde, cyberpunk styling)
- `aporia.vrm` — Aporia, production-quality (dark-haired, cyberpunk styling)
- `claude_suit.vrm` — Claude, the AI, in a suit — the primary Claude model.
  The outfit is built in layers (mesh names `jacket`, `tie`, `shirt`,
  `pants`, `shoes`): hide layers to change the look (jacket + tie off =
  casual shirtsleeves).
- `claude_suit_wardrobe.vrm` — the same claudesona carrying seventeen outfits
  as hidden layers: sixteen from the DAISY music video (a 1939 switchboard
  operator, a 1961 lab coat, 1980s colour-blocking, a hoodie, a mourning coat,
  an 1890s cycling outfit and more; `claude_suit_wardrobe_preview.jpg`) and
  the TuTa from UNKNOWN FORCE, black techwear with neon piping, techwear boots,
  Balla's five snap-on badges and an optional sun disc
  (`claude_suit_wardrobe_preview_tuta.jpg`). Dress it with
  `claudesona_wardrobe.js` ([outfits](#outfits--claude_suit_wardrobevrm),
  [the TuTa](#the-tuta)). It is 34 MB against the suit's 11 MB, so cast
  `claude_suit.vrm` when the suit is all the piece needs.
- `claude.vrm` — a lightweight Claude stand-in; `claude_suit.vrm` is primary

Any `.vrm` dropped into `eidoverse/assets/vrms/` works the same way. Point
`config.assets` at the VRM where it lives (e.g. `"character_vrm":
"eidoverse/assets/vrms/claude.vrm"`) — these are 10–40 MB, and referencing
in place is what keeps work dirs light. Custom GLB props live in
`eidoverse/assets/models/` the same way; animation clips auto-load from
`eidoverse/assets/animations/` as VRMA slots.

**The Claude VRMs are specifically the AI "Claude" — a particular identity,
not a generic figure.** Cast them when the video is actually about or
featuring Claude; a generic narrator, anchor, bystander, or "a human" is a
different character, and Claude isn't human. The same goes for
dialogue/narration/on-screen text — the name "Claude" appears when the
piece calls for it, not as ambient flavor.

**Character voices:** one edge-tts voice per character, kept consistent for
the piece (and across pieces for a recurring cast) — see [audio.md](audio.md).

## VRMA animations

`globalThis.VRMA_DEFAULTS_B64`, keyed by slot; clips ship in
`eidoverse/assets/animations/` (slot = filename stem). The slots are the
`VRMA_SLOTS` list in `eidoverse/render_scene.mjs`; a slot whose `.vrma` is
missing is skipped:

- **Locomotion** (the controller's domain): `walk`, `run`, `idle`,
  `turnLeft`, `turnRight`, `jump`, `vault`, `climbLedge`, `climbWallUp`,
  `climbWallDown`, `climbLadder`, `fallIdle`, `fallLand`, `stairsUp`,
  `stairsDown`, `stairsRunUp`, `stairsRunDown`
- **Expressive** (for a stationary VRM): `talk`, `salute`, `cheer`, `fist`,
  `raise`, `reach`, `crazy`, `dance`
- **Sitting** (see [sitting](#emotes--sitting-on-a-stationary-character)
  below): chair poses `sitting_normal_chair` (the `seatOn` default) and
  `sitting_nervous_arm_rub_chair`; floor poses `sitting_on_ground`
  (cross-legged) and `sit_laying_on_ground` (lying down); transitions
  `stand_to_sit` and `sit_to_stand`, whose baked hips translation lowers and
  raises the body
- **Performance** (hand-authored singing and stage clips for a stationary
  VRM, 128 BPM, all from one stance so any two crossfade without foot slide):
  `stand_breathe` (their idle), `sing_gesture_a`, `sing_gesture_b`,
  `chorus_sway`, `sing_open_arms`, `hand_to_heart`, `look_up_sky`,
  `phone_raise`, `head_bow`, `wave_goodbye`, `bow_thanks`. Three have an
  other-hand `*_mirror` variant: `sing_gesture_a_mirror`,
  `phone_raise_mirror` (with its own `phone_raise_mirror_hold`) and
  `wave_goodbye_mirror`. The one-shots `hand_to_heart`, `look_up_sky`,
  `phone_raise` and `head_bow` each have a `*_hold` loop that starts on
  their last frame. Play the one-shot with `loop: false`, then the
  hold with a short `fade` once it lands. Beats, uses, the authoring script and
  its checker are in
  [performance_src](../eidoverse/assets/animations/performance_src/README.md).
- **Performance, UNKNOWN FORCE** (92.90 BPM; darker and smaller: grounded,
  slow, minimal; the same stance as the clips above, so the two sets
  crossfade): `still_breathe` (their idle), `dark_groove`, `sing_low` and
  `sing_low_mirror`, `turn_it_down`, `not_that` and `not_that_mirror`,
  `look_up`, `salute_abort`, `fence_hands`, `ask_me`. `turn_it_down`,
  `look_up`, `fence_hands` and `ask_me` each have a `*_hold` loop. The
  [table below](#performance-clips-unknown-force) says what each does; the
  authoring script and its checker are in
  [performance_uf_src](../eidoverse/assets/animations/performance_uf_src/README.md).

`playVRMADefault(vrm, slot, { loop, fade })` returns `{ mixer, action, clip }`
and registers that VRM for the native frame loop. Repeat is the default;
`loop: false` plays once and clamps the last pose. `fade` is a transition
duration in seconds, not `fadeIn`/`fadeOut` options on this helper.

For a custom VRMA declared in `assets`, use the same options:

```js
const performance = await playVRMAFromBase64(vrm, ASSETS.custom_vrma, {
  loop: false, fade: 0.3,
});
```

Despite its legacy name, `playVRMAFromBase64` accepts the engine's raw bytes.
The controller's emote/gesture methods have their own options below.

**`playVRMADefault` declines locomotion slots** (it throws on
`'walk'`/run/sneak/stairs) — a locomotion clip played in place is the
treadmill artifact: legs cycle, body never moves. Locomotion belongs to the
controller (`body.walkTo(x, z)` / waypoints), which moves the body and
grounds the feet with IK. The one genuine in-place case — a VRM on a
treadmill or carried by a vehicle — passes `{ force: true }` (or sets
`globalThis._allowManualLocomotion = true`).

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
| `ask_me` | 4 | one-shot | A small open palm offered toward the lens at belly height, the face square to +Z. |
| `ask_me_hold` | 8 | loop | Only the breath moves, countered in the neck so the face never leaves the lens. |

```js
await playVRMADefault(vrm, 'still_breathe', { loop: true });                  // the first clip: no fade
const once = await playVRMADefault(vrm, 'turn_it_down', { loop: false, fade: 0.3 });
// …once.clip.duration seconds later, a hard cut onto its hold:
await playVRMADefault(vrm, 'turn_it_down_hold', { loop: true, fade: 0 });
```

- **Locking a loop to a song.** Start a loop on beat 1 of a bar and it stays
  locked, because every loop lasts 4 or 8 beats. Off the beat, set its phase once
  after the call (`r` is what `playVRMADefault` returned): `r.action.time = ((t - barStart) % r.clip.duration + r.clip.duration) % r.clip.duration`.
  For another tempo, set `r.action.timeScale = bpm / 92.9`.
- **Timing `turn_it_down`.** The hand reaches the top at beat 1.15 and presses
  from 1.45 to 3.05, so start it about a beat before the words.
- **The fence.** `fence_hands` puts the hands on a plane 0.372 m in front of her
  (film metres, the VRM at scale 0.87, facing +Z). Build the chain link there,
  covering at least x ±0.45 m and y 0.5–1.6 m, and move it with her root.
- **Facing.** `ask_me` faces +Z: turn her root toward the camera rather than
  tilting the camera.
- **Your own nods.** A conductor's beat nod on the head or chest doubles
  `dark_groove`'s nods and breaks `ask_me` and `look_up`. Turn it off for them.
- **Stance.** The engine's `idle`, `talk` and `dance` stand differently, so
  crossfading to or from them slides the feet a little. `still_breathe` is the
  matching neutral.

The clips play on any claudesona (`claude_suit.vrm`, `claude_suit_wardrobe.vrm`);
their flower clearances were tuned on the TuTa's body.

## Moving a character — the dialed-in controller

Physics-based locomotion + terrain-conforming foot IK (no drag) + automatic
walk speed that slows by incline, with optional sensing and path planning.
Three entry points over the same engine — pick by the job:

- **`VRMRobotBody`** — autonomous navigation (senses + plans + walks). It
  sees the scene (lidar fan) and routes around obstacles to a destination.
  For "get them to that spot, around the furniture."
  ```js
  const body = await VRMRobotBody.create(vrm, mixer, scene, {
      collisionMeshes: [floor, wall, deskMesh],   // solids walked on / around
      motion: { startX: 0, startZ: 4 },           // walkSpeed optional (below)
  });
  const arrival = body.walkTo(2.5, -3); // starts a plan; do not await during setup
  arrival.catch(error => console.error('Navigation:', error));
  // renderFrame(t): body.update(t, dt);  read body.getPosition() / getHeadPosition()
  ```
  `walkTo`/`runTo` resolve on arrival. If the controller stalls against a
  collider, the body replans once; still stalled after ~1.5 s, the promise
  rejects with `Error('blocked: collision stall at …')` and the waypoints
  clear, so always attach a `catch`. `body.performAction(clip, duration)`
  resolves only after the emote has played for `duration` (default 1.5 s)
  and rejects if the clip is unknown or fails to load.
- **`EidoverseRobotController`** — explicit waypoints, no sensing/planning,
  same simple API. For when you know the path.
  ```js
  const ctrl = await EidoverseRobotController.create(vrm, mixer, {}, {
      collisionMeshes: [floor], startPosition: [0, 0, 4],
  });
  ctrl.setWaypoints([{ x: 0, z: -4 }]);          // arrives → idle
  // renderFrame(t): ctrl.update(t, dt);  read ctrl.getPosition()
  ```
- **`VRMCharacterController`** — the lowest level: `locomote(dt, dir)` +
  `attachLocomotion({ legIK })` over a Rapier world you build. For
  terrain-harness work (`eidoverse/examples/obstacle_course.js`).

**Walk speed is automatic** — unset, the controller matches the walk clip's
natural stride and slows itself on stairs/ramps. Set `walkSpeed` for a
deliberate effect (very low = slow motion, high = hurried); a lowballed
speed "to look cinematic" is the slow-mo-walk artifact.

**`collisionMeshes` IS the walkable world.** The controller (and the foot
IK) finds surfaces by shape-casting the Rapier world built from
`collisionMeshes` — it doesn't raycast the rendered scene. So the list does
double duty: the walls they slide against, and every surface they walk on,
stand on, or climb onto — floor, stage, platform, riser, step, ramp, kerb,
terraced terrain, raised walkway. A surface that's only `scene.add`-ed is
invisible to the feet: the character walks through it at ground level.
Climbing is automatic once the surface is a collider — to put a character
on a raised stage: (1) the stage goes in `collisionMeshes`, (2) the
waypoint is an xz actually on the stage top. (Escape hatch when a collider
truly can't be added: drive `controller.externalGroundY` per frame from
your own raycast.)

**The controller owns the mixer, the root transform, and the feet.** Three
things follow:
- No pre-played idle under it — a pre-played action stays at weight 1 and
  blends over every clip, so the legs drag.
- The `VRMRobotBody` / `EidoverseRobotController` wrappers update both mixer
  and VRM; do not update either again. Native `playVRMA*` helpers also register
  their mixers/VRMs for engine updates. An independently managed rig outside
  those paths needs its own mixer and VRM updates; do not mix ownership.
- No per-frame writes to `vrm.scene.position` / `.rotation.y` — read
  position via `getPosition()`; face the camera when stationary via the
  controller's `heading`. Manual transforms per frame read as foot-slide.

## Movement vocabulary — run, vault, climb, jump, ladders

Everything is animation-driven with automatic contact IK — hands plant on
vaulted objects, grab ledge lips, and find ladder rungs on their own. The
engine is `VRMCharacterController`; the wrappers pass some of it through and
hold the rest on an inner object:

| Entry point | Inner `VRMCharacterController` | `isManeuvering` |
|---|---|---|
| `VRMCharacterController` | itself | getter: `cc.isManeuvering` |
| `EidoverseRobotController` | `ctrl.charCtrl` | getter: `ctrl.isManeuvering` |
| `VRMRobotBody` | `body.controller.charCtrl` (`body.controller` is an `EidoverseRobotController` unless `opts.legsClass` overrides it) | method: `body.isManeuvering()` |

`vault()`, `jump(opts)`, `climbLedge()`, `climbLadder(opts)` and
`setRunning(v)` exist on all three. `autoManeuvers` and the gesture methods
exist only on `VRMCharacterController` — reach them through the inner object.

- **Running.** On `EidoverseRobotController`, per-waypoint
  `ctrl.setWaypoints([{ x, z, action: 'run' }, …])` (walk resumes at
  waypoints without it); on `VRMRobotBody`, `body.runTo(x, z)`; or direct
  `setRunning(true)` on any entry point.
  Stride syncs to speed; stairs switch to run-stair clips automatically.
- **Auto-maneuvers (on by default).** While moving, the controller scans
  ahead and handles what it finds: knee-to-chest obstacles (~0.45–1.15 m
  with a landing beyond) → vault, one hand planting on top; chest-height to
  ~2.3 m walls → climb (grab the lip, pull up, mantle — through the mantle
  the top surface is a hard floor for the hands and the stepping foot lands
  on top); near-level gaps to ~2.2 m → jump; drops of ~0.85 m+ → a
  landing-recovery crouch. Set `autoManeuvers = false` on the inner
  controller (`ctrl.charCtrl.autoManeuvers = false`,
  `body.controller.charCtrl.autoManeuvers = false`) while deliberately
  approaching furniture the character shouldn't parkour over (a bench
  they'll sit on isn't an obstacle), and re-enable after. Check
  `isManeuvering` (a method on `VRMRobotBody`, a getter elsewhere — table
  above) before issuing new orders mid-flight.
- **Explicit maneuvers** (facing the geometry, within a stride):
  ```js
  ctrl.vault();                          // over the cover ahead (needs a landing)
  ctrl.climbLedge();                     // up onto the wall/ledge ahead
  ctrl.jump({ distance: 1.4, height: 0.45 });
  ctrl.climbLadder({ height: 2.5 });     // climbs the ladder face, mantles the top
  ```
  Each returns `false` (with a console warning) when the geometry ahead
  doesn't support the move — check the return when the beat matters.
  Ladders want real rung geometry (rungs ~every 0.28 m, override via
  `{ firstRung, rungSpacing }`, protruding slightly) — hands and feet
  quantize to the nearest rung. Tall rung-less walls (~2.3–4.5 m) get a
  wall-scramble (`wallScrambleMaxRise` tunes the ceiling).
- **Upper-body gestures while walking** — an emote's upper body blended
  over the gait. These live on `VRMCharacterController`; from a wrapper,
  use its inner controller:
  ```js
  const cc = ctrl.charCtrl;                 // VRMRobotBody: body.controller.charCtrl
  await cc.loadGesture('cheer');            // once, at setup
  cc.playGesture('cheer', { weight: 2.5 }); // ≈70% gesture on the upper body
  cc.stopGesture();
  ```
  Weight is a mixer blend (`2.5 ≈ 70%`, `4 ≈ 80%`). Gestures end when a
  maneuver starts. A full emote (`playEmote`) suspends locomotion entirely
  — gestures are the move-and-emote path.
- **Aiming a standing emote.** Full emotes face `Math.PI` by default; to
  aim one, set the facing yaw before playing (on `EidoverseRobotController`
  the emote API lives on `.charCtrl`; `VRMRobotBody` has
  `body.setEmoteFacing(ry)`, which sets the same field):
  ```js
  const b = ctrl.getPosition();
  ctrl.charCtrl._emoteFacingY = Math.atan2(cam.position.x - b.x, cam.position.z - b.z);
  ctrl.charCtrl.playEmote('salute', { fadeIn: 0.35 });
  ```
  The character pivots as the emote fades in (shortest arc), and eases back
  to the locomotion heading when it fades out — no hand-rotation around an
  emote.

Heading convention: `0` faces +Z, `Math.PI` faces −Z; the body turns toward
travel at `maxTurnRate`. Locomotion and full emotes are mutually exclusive
— sequence them; upper-body gestures layer over the walk.

`VRMRobotBody`'s AABB colliders suit flat floors + upright obstacles (they
flatten ramps/stairs). Ramps, stairs, and locomotion-centric terrain go
through `eidoverse/terrain_base.js` + `charCtrl.locomote(dt, dir)` —
`eidoverse/examples/obstacle_course.js` is the working reference.

## Emotes + sitting on a stationary character

Expressive clips fit a VRM that isn't controller-driven at that moment —
a desk scene, talk-to-camera, an emote beat between moves (let the
controller run out of waypoints or `forceAction('idle', dur)` first; a clip
played over locomotion fights it).

- `emote(vrm, 'cheer')` — any expressive slot on a stationary VRM (loops by
  default).
- `faceCamera(vrm, { offset })` — turn a stationary VRM to the active
  camera; `offset` (radians) for ¾ or profile.
- `seatOn(vrm, chair)` — sit a character in a chair. Raycasts the chair's
  actual seat pan (a ray grid → the broadest horizontal surface, ignoring
  the backrest), plays a chair-sit clip (default `sitting_normal_chair`;
  `{ clip: 'sitting_nervous_arm_rub_chair' }` for fidgety), then offsets
  the VRM so the hips rest on the seat. Facing is automatic (away from the
  detected backrest, camera fallback). Seat height, per-VRM hip height, and
  facing are all measured at runtime. `{ transition: 'stand_to_sit',
  fade: 0.3 }` eases down from standing.
  - The chair wants to be a real visible mesh with an actual seat surface —
    with nothing to raycast (an invisible cube, no broad horizontal top),
    it warns `SIT ON NOTHING` and points at `sitOnGround`.
  - `placeOn(vrm, chair)` snaps feet onto the seat — a character standing
    on the chair. `seatOn` is the sitting path; hand-lowering a standing
    idle to a guessed seat height gives the same artifact.
  - The facing and hip placement are already correct after the call — a
    manual `rotation.y` afterwards spins them out of the chair. A
    deliberate ¾/profile facing passes into the call: `seatOn(vrm, chair,
    { faceY })`.
  - The seated VRM auto-exempts from the placement audits (`seatOn`/
    `sitOnGround` register the sitter in `globalThis._seatedVRMs`) — a
    seated character legitimately overlaps the chair. Marking the chair
    `noClippingCheck` to help actually hides it from the seat raycast (they
    sink); the registration already handles it. `globalThis.unseat(vrm)`
    re-enables the audit when a scene stands them up.
- `sitOnGround(vrm, { clip, at, groundMeshes, hipHeight, faceY })` — sit on
  the floor. The ground has no seat surface, so this rests the pelvis just
  above the floor and lets the legs fold. Default clip `sitting_on_ground`
  (cross-legged); `{ clip: 'sit_laying_on_ground', hipHeight: 0.0 }` lies
  down. Chair clips on the floor dangle the legs through the ground — each
  surface has its clip family.
  ```js
  await sitOnGround(vrm, { at: [0, 0], groundMeshes: [floor] });
  ```

**Sitting with the controller registered** (`VRMRobotBody` registers
itself; a bare `VRMCharacterController` registers via
`(globalThis._vrmControllers ||= new Map()).set(vrm, ctrl)`):

```js
await seatOn(vrm, bench, { transition: 'stand_to_sit', faceY: Math.PI });
// …hold seated…
ctrl.endSeated(null, { reverse: true });   // stands back up (same clip reversed)
```

Choreograph the approach so the character stops just past the seat facing
away from it (the transition clip carries the hips back onto the pan), walk
around furniture rather than through it, `autoManeuvers` off for the
approach. Ground/ledge sitting without a pan drives the seated state
directly:

```js
ctrl.heading = facingY;                     // face this way seated — AND stand up into it
ctrl.beginSeated('sitting_on_ground');
// …hold…
ctrl.endSeated(null);
ctrl.charCtrl.stopEmote({ fadeOut: 0.9 });  // fade the pose back to idle
```

**Multiple characters:** register an animation or controller for each VRM.
The native loop advances helper-registered mixers if scene code has not already
advanced their clocks, and updates their VRMs. Controller-managed rigs follow
the controller's update path instead. Keep calling `body.update(t, dt)` or
`ctrl.update(t, dt)` for the controllers you create; registration does not
replace that call. Use `dt = 1 / FPS` in the fixed-rate scene frame loop.

Replaying a helper clip replaces or crossfades its previous action according
to `fade`. Do not null `_mixer` between character loads or independently update
the same `vrm` a second time.

## T-pose / foot-slide diagnosis

A VRM in T-pose despite a loaded animation traces to one of these:

1. **Double-updating** — with a controller, `controller.update(t, dt)` is
   scene-owned per-frame call. For native `playVRMA*` helpers, let the
   engine update their registered mixer and VRM.
2. **Missing active action** — check clip loading and action weights. The
   controller normally returns to idle when a path ends; an ended path alone
   is not evidence that the rig should T-pose.
3. **Manual transforms under a controller** — per-frame `vrm.scene.position`
   / `.rotation.y` writes cause foot-slide / walking-through-objects;
   waypoints + `getPosition()` are the interface.
4. **Missing colliders** — every solid walked on or around goes in
   `collisionMeshes` at create time.
5. **Feet not conforming to stairs** — check the actual collider shapes and
   enabled foot IK. `VRMRobotBody` uses AABBs, so use the terrain controller
   path for ramps/stairs. Foot IK suspends during emotes and airborne states.
6. **Facing** — after `rotateVRM0`, +Z is forward; `rotation.y = 0` faces a
   +Z camera.

At the end of a render the `[vrm-pose]` check flags (`RE-RENDER REQUIRED`) a
tracked VRM (`_vrm`, `_v`, `_vrms` or helper-registered) whose left upper arm,
right upper leg and hips never left the normalized rest pose — the T-pose. It
compares against that rest pose, not the first frame, so a character held in
any static non-T pose (a seated or emote hold) counts as posed.

## `claude_suit.vrm` — mouth + wardrobe recipes

This recipe applies to `claude_suit.vrm` and to `claude_suit_wardrobe.vrm`
(the same face).

**The petal ring stays off the jacket on its own.** The orange ring around the
face is split-skinned: the top arc rides the head, the bottom arc the
`petals base lower` bone. That bone hangs from `petals base lower pivot` on the
chest, whose VRMC_node_constraint follows only the neck's turn about the body's
vertical, so a nod or a tilt no longer swings the arc into the collar, and a
turn moves the ring as it always did. three-vrm applies it in `vrm.update()`;
nothing to call. Big turns (past about 20°) can still bring a lapel tip through
the side of the ring, as they always could: in a collar close-up, keep head
turns small. The pivot is written by `claude_suit_wardrobe_src/ring_pivot.py`.

**Drive the face through `eidoverse/claudesona_face.js`.** The visible
cat-smile, eyes and lines are painted plates on a white face dome, and the
rig's own shapes don't hold them to that dome: its mouth (`show MMD mouth`) is
a flat black plate that the shapekey slides straight toward the camera
(28.8 mm per unit, from 29 mm behind the face), so past about 1.1 it floats in
front of the face — 4–10 mm at 1.25, 15–20 mm at 1.6 — and its eye, frown and
blush targets swing parts of the painted features up to ~13 mm off it. The
offsets lie along the view axis, so a head-on check passes and a
three-quarter or profile shot shows black slabs and pink discs hovering off
the face. The library fixes the face at load and drives it:

```js
const { installSuitMouth, makeSuitMouth, makeFaceTrack, mergeMax } =
  await import(new URL('claudesona_face.js', EIDOVERSE_DIR).href);
const face = installSuitMouth(vrm);                // once, after load, before the first render
const mouth = makeSuitMouth({ inputMax: 0.35 });   // 0.35 for lipsync.py visemes, 1 for voicebox
const feel = makeFaceTrack(TL, {                   // optional: feelings keyed to words
  sectionBase: { chorus: { smile: 0.5 } },
  lineCues: [[/goodbye/, { soft: 0.8, frown: 0.2 }]],
});
// renderFrame(t), after any controller update and right before renderAsync:
face.set(mergeMax(mouth.update(t, visemes[Math.floor(t * visemeFps)]), feel.at(t)));
```

1. `installSuitMouth(vrm)` does two things once, on the loaded meshes:
   - It re-seats every painted feature — at rest and at the end of every
     expression target — onto the face dome along its depth axis, 1.8 mm
     proud (x and y kept, so a front view is unchanged), and the blush 1 mm
     proud, under the lines.
   - It gives the mouth plate three targets of its own, raycast onto the
     dome 1.5 mm proud: a sliver under the smile, a full open mouth and a
     round "oh". The rig's own mouth shapes stay at 0.

   Call it before the first render and after anything that runs
   `VRMUtils.combineMorphs` (`EidoverseRobotController.create` does, unless
   `opts.skipVrmOptimize`), which rebuilds the targets and drops these. It
   returns `{ plate, plates, set(weights), weights }`. `set` zeroes every
   face morph and writes `weights` straight away, so call it last in
   `renderFrame` — a controller's `vrm.update` rewrites expression-bound
   targets such as blink. Zeroing also removes auto-blink; the driver blinks
   between phrases. The mouth weights are `mouthOpen` (0..1) and
   `mouthRound` (0..1, the share of oh/ou), exported as `MOUTH_OPEN` and
   `MOUTH_ROUND`; any other face morph can be passed by name.
2. `makeSuitMouth(opts)` turns viseme frames into those weights. Scaling the
   mouth straight by loudness would snap it shut on every consonant, so the
   driver:
   - keeps one openness signal with a fast attack (30 ms) and a slow release
     (110 ms);
   - opens above 0.18 and closes below 0.08, with hysteresis between;
   - while open, never drops below `floor` (0.3) of the vowel's size;
   - changes vowel only at a syllable dip, or when another vowel clearly
     leads.

   The other options are `attack`, `release`, `openAt`, `closeAt`,
   `switchDip`, `switchLead` and `blinkEvery`. Blinks happen only while the
   mouth is shut; `blinkEvery: 0` turns them off. Per vowel (`SUIT_VISEMES`):
   `aa` opens fully, `ee` 0.62, `ih` 0.45 (all wide); `oh` 0.95 at 0.8 round,
   `ou` 0.62 fully round. A single openness signal, such as `lipsync.py
   get_mouth_openness` or an RMS envelope, works too: pass it as
   `{ aa: openness }`.
3. `makeFaceTrack(TL, opts)` keys feelings to words and sections rather
   than seconds, so re-timing the audio can't desync a feeling. `TL` is
   `{ sections: [{ name, t0, t1 }], captions: [{ text, t0, t1 }] }`, the
   shape the voicebox and song timelines use.
   - `sectionBase` sets each section's resting feeling.
   - `lineCues` pairs a regex on the caption text with a feeling, eased in
     and out around each matching line.
   - `closeAfterLast` (default `true`) slowly softens the eyes after the last
     caption.

   The channels, as measured on this face:
   - `smile` curls the mouth corners up smoothly with its value.
   - `frown` is smooth; `wide`, `down` and `up` (gaze) are subtle.
   - `soft` closes the eyes. Up to about 0.5 they only shrink to small dots;
     0.75–0.85 gives content, sleepy slits.
   - `blush` and `jaw` are switches. The blush is a reveal plate re-seated on
     the cheek at exactly `Blush` 1 (a partial weight sinks it into the
     cheek), so a blush of 0.3 or more shows it and less shows nothing. A jaw
     of 0.15 or more opens the mouth while the character is silent.

   `mergeMax` merges weight dicts by the per-morph maximum.
4. Check a face from the side, not only head-on: every hovering mouth or
   feature on this rig passed a front view. The render audit's
   `[lipsync] mouth NEVER moved` line watches the expression manager, so it
   is a false positive on this path — crop the mouth in a sung frame and a
   silent one instead. To try a face, render
   `python vrm_turntable.py --outfits suit,suit --frames face --views 0 --faces '[{"Blush": 1}, {"Smile": 0.6, "MouthSmileLeft": 0.6, "MouthSmileRight": 0.6}]'`
   (raw rig weights, without the library's re-seating).

`claude.vrm` (the classic sona) is the opposite: its mouth is
expression-bound and the plain `expressionManager.setValue` viseme path
works as written.

**Wardrobe — layered and recolorable** (render-verified). Named nodes:
`jacket`, `tie`, `shirt`, `pants`, `shoes`.
- Hide layers: `vrm.scene.getObjectByName('jacket').visible = false` (same
  for `tie`) — the shirt underneath is fully modeled.
- `flower` is the head mane, the character's signature bloom — part of the
  character, not the outfit.
- Recolor: these meshes carry material arrays (`mesh.material.color` is
  undefined) — collect `(Array.isArray(m.material) ? m.material :
  [m.material])` per layer and `mat.color.setHex(...)` each. Stock palette:
  jacket `#273884`, tie `#e70024`, shirt `#cecece`, pants `#fdc955`, shoes
  `#65411f`, mane `#f98a53`.
- Casual look: hide jacket + tie, then puff the shirt so it reads as a
  relaxed pullover (`node.scale` is ignored on skinned meshes — displace
  vertices along normals once at setup):
  ```js
  const shirt = vrm.scene.getObjectByName('shirt');
  shirt.traverse((m) => {
      if (!m.isMesh) return;
      const pos = m.geometry.attributes.position, nor = m.geometry.attributes.normal;
      for (let i = 0; i < pos.count; i++) {
          pos.setXYZ(i, pos.getX(i) + nor.getX(i) * 0.02,
                        pos.getY(i) + nor.getY(i) * 0.02,
                        pos.getZ(i) + nor.getZ(i) * 0.02);
      }
      pos.needsUpdate = true;
  });
  ```
  `0.02` is the verified relaxed fit; `0.035` reads as a bulky sweater.
  Copy the original positions first if the fitted look returns later.

### Outfits — `claude_suit_wardrobe.vrm`

`eidoverse/claudesona_wardrobe.js` dresses the wardrobe VRM. It shows and
hides garment layers, repaints materials with colours or procedural
patterns, folds petals back under a hat and seats the hat.

```js
const { makeWardrobe, WARDROBE } = await import(new URL('claudesona_wardrobe.js', EIDOVERSE_DIR).href);
const wardrobe = await makeWardrobe(THREE, vrm);   // right after load (async); starts in 'suit' or opts.wear
wardrobe.wear('lab_coat_1961');              // any WARDROBE key; a no-op if already worn
wardrobe.petals('mac_launch_1984');          // repaint only the petals (a preset key or a spec); null restores
```

| Preset | The look |
| --- | --- |
| `suit` | digi's own suit |
| `voder_operator_1939` | rose jacket, cream blouse, a switchboard operator's headset |
| `lab_coat_1961` | white lab coat, glasses, a pocket protector with pens |
| `turtleneck_1966` | black turtleneck, glasses |
| `ringer_tee_1978` | red-and-amber striped tee |
| `colorblock_1982` | colour-blocked jacket, terry headband, petals in the Commodore 64 palette |
| `mac_launch_1984` | grey suit, green bow tie, petals in the six Apple stripes |
| `professor_tweed_1984` | herringbone tweed, glasses, amber petals |
| `fleece_2001` | navy jacket, khakis |
| `vocaloid_2007` | grey shirt, teal tie, ribbon bows in the petals |
| `hoodie_2016` | black hoodie: hood down, kangaroo pocket, drawstrings |
| `bing_2023` | blue-to-teal gradient suit, petals swept in the same blues |
| `mourning` | black overcoat, white shirt, black tie, a daisy on the lapel |
| `march` | canvas work jacket with embroidered patches |
| `sleeves_rolled` | jacket off, shirt sleeves rolled, tie |
| `cyclist_1892` | striped jersey, tweed knickerbockers, argyle socks, a straw boater with the petals folded under it |
| `tuta` | the UNKNOWN FORCE TuTa: black techwear one-piece, techwear boots, belt and straps ([the TuTa](#the-tuta)) |
| `sax_guy_2010` | Eurovision 2010's saxophonist: open sleeveless pinstripe vest over a sleeveless yellow tee, bright blue trousers, white wayfarers, a red fingerless glove on the right hand, a cord necklace |

A preset is `{ show, paint, hide, fold, hat }`:

- `show` lists the garment layers to show; every other optional layer hides.
  The body, face, flower and shoes always show. The layers are `jacket`,
  `tie`, `shirt`, `pants`, `jersey`, `knickers`, `socks`, `boater`,
  `coat_skirt`, `shirt_rolled`, `acc_glasses`, `acc_headset`, `acc_pocket`,
  `acc_bowtie`, `acc_headband`, `acc_ribbons`, `acc_hoodie`, `acc_patches`,
  `acc_boutonniere`, `sax_vest`, `sax_tee`, `acc_wayfarers`, `acc_glove_r` and
  `acc_cord`. The `tuta` preset lists its own layers in `uf` (`tuta`,
  `uf_boots`, `uf_straps`) and hides digi's shoes with `hideBase: ['shoes']`.
- `paint` maps a material name to `'#hex'` or a pattern:
  - `{ pattern: 'stripes', a, b, scale }` (horizontal bands; `axis: 'x'` for
    vertical pinstripes, `width` = the share of `b`, 0.5 by default), `'blocks'` (`a`, `b`, `c`),
    `'herringbone'` (`a`, `b`, `c` flecks, `scale`), `'gradient'` (`a`, `b`)
    and `'canvas'` (`a`, `b`, `scale`);
  - for `petals` only, `'rainbow'` (`colors`, `top`, `bottom`), `'perPetal'`
    (`colors`, one per petal, and `center`) and `'sweep'` (`a`, `b`).

  Patterns are procedural in the model's object space, because the garment
  UVs are not laid out for prints. A hex on a textured material replaces its
  print while its normal map keeps the weave. The MToon shade colour and the
  outlines follow the paint. The layer table in the
  [source README](../eidoverse/assets/vrms/claude_suit_wardrobe_src/README.md)
  lists the material names.
- `hide` hides materials inside a shown layer; the hoodie hides the jersey's
  `jersey_collar`.
- `fold` bends whole petals back from the face: `{ '12_L': deg }` or
  `{ '12_L': [deg, scale] }`, keyed by petal bone (`1_L`…`12_L`, `1_R`…).
  The petals are spring bones, so the fold is written into each chain's rest
  pose and the springs keep moving around it.
- `hat` seats the boater: `{ offset: [x, y, z], scale }`, in model metres
  with +z on the face's side.

`WARDROBE` is a plain object read at `wear()` time, so add your own preset
with `WARDROBE.my_look = { show: [...], paint: {...} }`. Each (material,
paint) pair builds one node, cached, so switching back and forth between
outfits reuses compiled shaders. Set `globalThis.WARDROBE_DEBUG = true` to
log paints and folds. New garments are modelled in Blender; the
[source README](../eidoverse/assets/vrms/claude_suit_wardrobe_src/README.md)
has the steps.

### The TuTa

The `tuta` preset is the outfit from the UNKNOWN FORCE music video (2026-10):

- **The tuta.** Thayaht's 1920 TuTa, the one-piece T-cut overall, re-cut as
  black techwear. His contrast topstitching becomes neon piping on the same
  seams, cyan on her left and magenta on her right. A diagonal zip runs from
  her left collarbone to her right hip.
- **Balla's colour blocking** from *Il vestito antineutrale* (1914): a violet
  wedge, a petrol wedge, a charcoal sleeve and a sodium lightning inlay.
- **Techwear boots**, a belt (open at the back round the tail) and a thigh
  strap.
- **The modificanti.** Balla's snap-on shapes: five neon badges, one per camp
  of the AI argument, hidden until pinned. Taking one off leaves a ghost.
- **Face paint.** Her left half is split into thin magenta and cyan Futurist
  planes, and the eyes get catchlights with a faint scanline.
- **`acc_sundisc`** (optional): Balla's segmented sun behind the petal ring.

On `claude_suit_wardrobe.vrm`, `makeWardrobe` dresses the TuTa's surface and
adds its controls to the same wardrobe object; every other preset works
alongside it.

```js
const { makeWardrobe, FINAL_CHORUS } = await import(new URL('claudesona_wardrobe.js', EIDOVERSE_DIR).href);
const wd = await makeWardrobe(THREE, vrm, { wear: 'tuta' });   // right after load, before anything else touches the materials
wd.facePaint(true);
wd.pin('mod_red');                            // now
wd.pin('mod_gold', { at: 131.4 });            // a snap (a pop and a flash) at film time 131.4 s
wd.unpin('mod_gold', { at: 273.0, eject: true });   // it pops off and tumbles away; its ghost stays
// renderFrame(t), before rendering:
wd.update(t);
const b = wd.badgeWorld('mod_gold');          // { position, quaternion, flying, visible }: aim a camera at it
```

Call it before any other code changes the VRM's materials: the wardrobe resets
materials to the nodes it captured at construction, and the TuTa installs its
TSL first. It reads the rest pose from the skeleton's bind matrices. Its eye
catchlights come on with the `tuta` preset only, so the other presets look
exactly as they did before the TuTa joined the wardrobe.

| Call | What it does |
| --- | --- |
| `await makeWardrobe(THREE, vrm, opts)` | On the wardrobe VRM, installs the TuTa's materials, then wears `opts.wear` (default `'suit'`). It also takes `neon` (default 1), `grime` (street dust, 1) and the ejection's physics: `ejectSpeed` (1.4 m/s), `ejectUp` (1.0 m/s), `ejectGravity` (2.2 m/s²), `ejectDrag` (0.8/s) and `floorY` (the VRM root's height). |
| `wd.wear(key)` | `'tuta'` (tuta, boots and straps; digi's loafers hidden) or any other `WARDROBE` preset (the TuTa's layers go off). Badges show only on the tuta. A no-op if already worn. |
| `wd.pin(key, { at })` | Pins a badge now, or at film time `at` with a 0.35 s snap. |
| `wd.unpin(key, { ghost, at, eject, linger })` | Takes a badge off. It leaves its ghost unless `ghost: false`. With `at`, it unsnaps at that time: a flash, the badge shrinks away and the ghost fades in. With `eject: true`, the badge pops off and tumbles out along its outward normal for 1.2 s under a floaty gravity, its glow flickering out, bouncing off the floor; `linger: true` leaves it lying where it lands. |
| `wd.schedule(events)` | Replaces the whole schedule: `[{ at, pin }, { at, unpin, ghost, eject, linger }, …]`. |
| `wd.update(t)` | Per frame, before the render. Pins and unsnaps are pure functions of `t`. An ejection captures its launch pose at the first update at or after `at` and integrates from there with a fixed step, so render in order: the same frames give the same flight. |
| `wd.badgeWorld(key, out)` | The badge's world `position` and `quaternion` now, plus `flying` and `visible`. |
| `wd.clearGhost(key)` | Removes a ghost and that badge's schedule. |
| `wd.facePaint(on)` | `true`, `false` or a 0..1 fade, independent of the outfit. |
| `wd.sunDisc(on)` | Shows or hides `acc_sundisc`. |
| `wd.neon(level)` | The glow of the piping, the inlay, the boots' accents, the face paint, the badge rims and the disc: 0..1, more is brighter. The film's outro turned her down with the city. |
| `wd.badges`, `wd.pinned`, `wd.ghosts`, `wd.current`, `wd.uniforms`, `wd.layers`, `wd.base` | The badge objects, the immediate state, the worn preset, the TSL uniforms (`neon`, `paint`, `eyes`, `grime`, `ghost[5]`, `time`), every layer object and the garment wardrobe underneath. `wd.petals()` works as on any wardrobe. |

The module also exports `BADGES`, `MODIFICANTI` (each badge's camp, glow and
bone) and `FINAL_CHORUS` (the film's line-to-badge pairs). A preset that wears
the TuTa's layers lists them in `uf`: `{ show: [], uf: ['tuta', 'uf_boots', 'uf_straps'], hideBase: ['shoes'], paint }`.

**The modificanti.** The badges are sized to read in a medium shot: waist-up
from 2.2 m at 1080p, about 100–160 px each. They sit clear of the petal ring,
and all five fit at once. Each is an extruded outline with a painted face and an
emissive rim; text and pictograms are painted, never geometry.

| Key | Camp | The badge | Where (bone) |
| --- | --- | --- | --- |
| `mod_red` | the safety camp | a red enamel wedge, 144 × 45 mm, pointing at the zip | across her belly (`spine`) |
| `mod_gold` | the state | a gold star over two chevrons | right upper arm, outside (`upper_arm.R`) |
| `mod_chrome` | the money race | a chrome bolt tinted dollar-green, with banknote guilloche | left upper arm, outside (`upper_arm.L`) |
| `mod_warning` | "only an engine" | a white warning triangle with a toaster pictogram | left hip, below the belt (`hips`) |
| `mod_spray` | the evening news | a black canvas patch, CLANKER sprayed through a stencil, a magenta merrowed edge | right upper arm, below the gold (`upper_arm.R`) |

**The ghost.** When a badge comes off, the suit keeps its exact shape: a faint
emissive outline in the badge's glow (20 % of its rim) on the lighter, fuzzy
hook-and-loop field it gripped. It is a per-badge SDF in the tuta's own shader,
projected from the badge's rest frame, so it rides the cloth. The film's point:
she can refuse the labels, but they leave marks.

**Lighting her.** Black techwear disappears in the dark. Rim her with neon
kickers from behind, at hip and shoulder height; MToon's parametric rim takes
the scene's lights. The badges and the piping are emissive, so bloom picks them
up.

**Cost.** In a frame that the character fills at 1080p, the full outfit
measured 3.57–3.89 ms against 3.53 ms for digi's suit (RTX 5090 Laptop GPU). Its
surface work adds about 0.4 s of shader compile at startup.

**Limits.**

- At three-quarter views the mouth cavity floats off the face when the driver
  holds the reveal at 1.25 or more. That is digi's rig, not the paint, which
  never touches the face plates, so lipsync works unchanged.
- The spray patch's stencil reads only from a medium shot in. An ejected arm
  badge starts behind the hanging petals for its first frames from a frontal
  camera.
- The VRM has no peaked cap; the
  [corridor set](../eidoverse/sets/unknown_force/CORRIDOR_NEWS.md) carries one
  that seats on her head bone.
- The [source README](../eidoverse/assets/vrms/claude_suit_wardrobe_src/README.md#the-tuta)
  has the Blender build and what it taught.

## Turntable sheets

`vrm_turntable.py` (repository root) renders a VRM through the engine in a
neutral studio and tiles the result. Use it to review an outfit, a new
garment, a clip on another rig or an expression:

```bash
python vrm_turntable.py --outfits lab_coat_1961,mourning --frames head,body --views 0,35,90,150,180
python vrm_turntable.py --outfits suit,march,cyclist_1892 --frames body --views 20 --tile 3x1
python vrm_turntable.py --vrm eidoverse/assets/vrms/aletheia.vrm --outfits - --anim sing_open_arms,bow_thanks --hold 45
python vrm_turntable.py --outfits suit,suit --frames face --faces '[{"Smile": 1}, {"EyeWide": 1, "Blush": 0.6}]'
python vrm_turntable.py --outfits hoodie_2016 --spin --video work/turntable/hoodie.mp4
```

A sheet has one row per outfit, clip and framing, and one column per yaw.
`--tile CxR` lays the same tiles out as a grid. Each tile is the last frame
of a `--hold` block, because frame 0 of any render is the VRM's load pose and
spring bones need a few frames to settle. The framings are `face`, `head`,
`chest` and `body`, scaled by the character's own head height, so any rig
frames the same. `--outfits -` renders a VRM without the wardrobe. The
defaults are `--scale 0.87` for the claude_suit models (a human 1.74 m) and
`--light 0.7`, which keeps white MToon cloth under the bloom threshold.
`--presets` adds variants on the command line
(`{"name": {"base": "cyclist_1892", "fold": {...}}}`), and `key:nofold`
drops a preset's fold. `--spin` renders a slow turn per outfit as a video
instead of a sheet.

## Nav diagnostics — `RobotDebug`

`robot_debug.js` installs `RobotDebug` — an overlay drawing the nav stack's
internals: the lidar ray fan, occupancy landmarks, the planned A* path.
Attach it to a `VRMRobotBody` while dialing in a navigation scene (why is
she routing around nothing? what did the lidar see?), then remove it — its
visuals in a finished video read as glitch lines coming off the character,
unless a "robot POV / diagnostics" look is the point.

## Low-level foot IK options

`VRMFootControllerIK` is the injected class used by the movement wrappers.
For a directly managed `VRMCharacterController`, construct it with the same
Rapier world, character collider and measured reference-pose sole offset,
then give it to `attachLocomotion`. The constructor initializes its limb data.

```js
const legIK = new VRMFootControllerIK(vrm, {
  world, RAPIER, collider: charCtrl.collider, meshHeightOffset: vrmFootY,
  type: VRMFootControllerIK_CastType.RayAndSphere,
  rotationType: VRMFootControllerIK_RotationType.RawTarget,
  sphereRadius: 0.015, MaxStepHeight: 0.6,
});
charCtrl.attachLocomotion({ legIK });
// Each frame on this direct, low-level path:
charCtrl.locomote(1 / FPS, direction);
vrm.update(1 / FPS);
```

The low-level `locomote` call owns mixer and IK updates, but the direct caller
still calls `vrm.update(dt)`. The two wrappers above already do that extra
call. Do not also call `legIK.update(dt)` after attaching it. The complete
[terrain template](../eidoverse/terrain_base.js) shows reference-pose
measurement, Rapier world construction and this ownership arrangement.

`foot_ik.js` also exposes `VRMFootControllerIK_CastType` (`Ray`, `Sphere`,
`RayAndSphere`) and `VRMFootControllerIK_RotationType` (`RawTarget`, `AddTarget`,
`Direction`, `Animator`) for configuring the low-level IK class. Use the named
constants when extending that controller; the wrappers configure their own IK.
These are option enums, not additional scene animation loops.
