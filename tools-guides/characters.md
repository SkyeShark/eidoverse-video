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
- `claude_suit_wardrobe.vrm` — the same claudesona carrying sixteen outfits
  as hidden layers (a 1939 switchboard operator, a 1961 lab coat, 1980s
  colour-blocking, a hoodie, a mourning coat, an 1890s cycling outfit and
  more); `claude_suit_wardrobe_preview.jpg` shows them all. Dress it with
  `claudesona_wardrobe.js` ([outfits](#outfits--claude_suit_wardrobevrm)).
  It is 31 MB against the suit's 11 MB, so cast `claude_suit.vrm` when the suit
  is all the piece needs.
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

**The mouth drives raw morphs, not expressions.** The visible cat-smile is
painted on the face; the animatable mouth is a hidden cavity revealed by
the `show MMD mouth` shapekey. The expressionManager path barely moves it —
voice over that mouth reads frozen. `eidoverse/claudesona_face.js` packages
the render-verified recipe:

```js
const { installSuitMouth, makeSuitMouth, makeFaceTrack, mergeMax } =
  await import(new URL('claudesona_face.js', EIDOVERSE_DIR).href);
const face = installSuitMouth(vrm);                // once, after load
const mouth = makeSuitMouth({ inputMax: 0.35 });   // 0.35 for lipsync.py visemes, 1 for voicebox
const feel = makeFaceTrack(TL, {                   // optional: feelings keyed to words
  sectionBase: { chorus: { smile: 0.5 } },
  lineCues: [[/goodbye/, { soft: 0.8, frown: 0.2 }]],
});
// renderFrame(t): the current viseme frame is { aa, ih, ou, ee, oh }
face.set(mergeMax(mouth.update(t, visemes[Math.floor(t * visemeFps)]), feel.at(t)));
```

1. `installSuitMouth(vrm)` finds the three face plates and writes their raw
   `morphTargetInfluences` in `onBeforeRender`. Writing at render time
   survives the engine's VRM passes. It zeroes every morph first, because
   leftover expression weights otherwise hold the mouth shut. Zeroing also
   removes auto-blink, so the driver blinks for you. It returns
   `{ plates, set(weights), weights }`.
2. **The reveal is a threshold, not a fade.** The black cavity is a plate
   pushed through the white face. Below about `show MMD mouth` 1.0 it stays
   behind the face and only the painted line shows; above that it pops out
   and grows. A viseme pose scaled by loudness crosses that line on every
   consonant, so the black part blinks out mid-word. One film measured the
   cavity visible for 71 of 255 sung seconds, with 716 on/off flips.
   `makeSuitMouth` avoids that:
   - It keeps one openness signal with a fast attack (30 ms) and a slow
     release (110 ms).
   - It opens above 0.18 and closes below 0.08, with hysteresis between.
   - While open it holds the reveal at `reveal` (1.25) and scales only the
     vowel's shape morphs, by `0.3 + 0.7 × openness`.
   - It changes vowel only at a syllable dip, or when another vowel clearly
     leads.

   The cavity stays out through a phrase and closes at its end. The other
   options are `attack`, `release`, `openAt`, `closeAt`, `switchDip`,
   `switchLead` and `blinkEvery`. Blinks happen only while the mouth is
   shut; `blinkEvery: 0` turns them off.
3. The poses are exported as `SUIT_VISEMES`, one per vowel. Weights above 1
   are intentional: morph deltas scale linearly past 1, and these stacks are
   verified tear-free.
   ```js
   aa: { 'show MMD mouth': 1.6, 'あ': 2.0, JawOpen: 1.5, A: 0.5 }   // big open — the workhorse
   oh: { 'show MMD mouth': 1.2, LipFunnel: 1.0, 'お': 0.8 }          // rounded drop
   ou: { 'show MMD mouth': 0.8, LipPucker: 1.2 }                     // tight pucker
   ee: { 'show MMD mouth': 1.0, 'え': 1.5 }                          // wide + shallow
   ih: { 'show MMD mouth': 0.9, 'い': 1.2 }                          // flat slit
   ```
   A single openness signal, such as `lipsync.py get_mouth_openness` or an RMS
   envelope, works too: pass it as `{ aa: openness }`.
4. `makeFaceTrack(TL, opts)` keys feelings to words and sections rather
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
   - `blush` and `jaw` are switches, because both ride reveal plates like the
     mouth. Blush is hidden below a raw `Blush` of about 0.75, so a blush of
     0.3 or more shows it (a little fuller as it rises) and less shows
     nothing. A jaw of 0.15 or more opens the mouth while the character is
     silent.

   `mergeMax` merges weight dicts by the per-morph maximum.
5. Verified traps: `vis_aa/ih/ou/ee/oh` and the plain vowel shapes do
   nothing without the reveal; `MouthClosed` doesn't hide the cavity (rest
   = reveal at 0); `hide mouth` restyles the painted line (an aesthetic
   change, not lipsync); `O`/`お` solo are empty exports. Expression
   accents that do work as raw morphs: `Smile`, `MouthSmileLeft/Right`,
   `MouthFrown`, `Blink`, `EyeClosedLeft/Right`, `EyeWide`, `Blush`/`照れ`.
   `Blush` and `照れ` are reveals: nothing below about 0.75, full cheeks from
   0.9. To try a face, render
   `python vrm_turntable.py --outfits suit,suit --frames face --views 0 --faces '[{"Blush": 1}, {"Smile": 0.6, "MouthSmileLeft": 0.6, "MouthSmileRight": 0.6}]'`.

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
const wardrobe = makeWardrobe(THREE, vrm);   // after load; starts in 'suit'
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

A preset is `{ show, paint, hide, fold, hat }`:

- `show` lists the garment layers to show; every other optional layer hides.
  The body, face, flower and shoes always show. The layers are `jacket`,
  `tie`, `shirt`, `pants`, `jersey`, `knickers`, `socks`, `boater`,
  `coat_skirt`, `shirt_rolled`, `acc_glasses`, `acc_headset`, `acc_pocket`,
  `acc_bowtie`, `acc_headband`, `acc_ribbons`, `acc_hoodie`, `acc_patches` and
  `acc_boutonniere`.
- `paint` maps a material name to `'#hex'` or a pattern:
  - `{ pattern: 'stripes', a, b, scale }`, `'blocks'` (`a`, `b`, `c`),
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
