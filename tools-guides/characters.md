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
`eidoverse/assets/animations/` (slot = filename stem):

- **Locomotion** (the controller's domain): `walk`, `run`, `fastRun`,
  `slowRun`, `sneak`, `walkBackward`, `stairsUp`, `stairsDown`,
  `stairsRunUp`, `stairsRunDown` (+ controller-internal `turnLeft`,
  `turnRight`, `jump`, `vault`, `climb*`, `fallLand`)
- **Stationary** (`idle`, `fallIdle`) and **expressive** (for a stationary
  VRM): `sit`, `talk`, `cheer`, `reach`, `raise`, `fist`, `salute`,
  `crazy`, `dance`

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

Available through all three entry points; everything is animation-driven
with automatic contact IK — hands plant on vaulted objects, grab ledge
lips, and find ladder rungs on their own.

- **Running.** Per-waypoint `setWaypoints([{ x, z, action: 'run' }, …])`
  (walk resumes at waypoints without it), or direct `setRunning(true)`.
  Stride syncs to speed; stairs switch to run-stair clips automatically.
- **Auto-maneuvers (on by default).** While moving, the controller scans
  ahead and handles what it finds: knee-to-chest obstacles (~0.45–1.15 m
  with a landing beyond) → vault, one hand planting on top; chest-height to
  ~2.3 m walls → climb (grab the lip, pull up, mantle — through the mantle
  the top surface is a hard floor for the hands and the stepping foot lands
  on top); near-level gaps to ~2.2 m → jump; drops of ~0.85 m+ → a
  landing-recovery crouch. Set `autoManeuvers = false` while deliberately
  approaching furniture the character shouldn't parkour over (a bench
  they'll sit on isn't an obstacle), and re-enable after. Check
  `isManeuvering()` before issuing new orders mid-flight.
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
  over the gait:
  ```js
  await ctrl.loadGesture('cheer');            // once, at setup
  ctrl.playGesture('cheer', { weight: 2.5 }); // ≈70% gesture on the upper body
  ctrl.stopGesture();
  ```
  Weight is a mixer blend (`2.5 ≈ 70%`, `4 ≈ 80%`). Gestures end when a
  maneuver starts. A full emote (`playEmote`) suspends locomotion entirely
  — gestures are the move-and-emote path.
- **Aiming a standing emote.** Full emotes face `Math.PI` by default; to
  aim one, set the facing yaw before playing (on the wrappers the emote API
  lives on `.charCtrl`):
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
7. **Walk Backwards loaded by default** — backwards walking is a narrative
   choice; the forward walk is the default gait.

## `claude_suit.vrm` — mouth + wardrobe recipes

**The mouth: give it morph targets of its own; never drive the rig's.**
The visible cat-smile is PAINTED on the face. The animatable mouth is a flat
black plate (849 vertices, on the same mesh as the painted eyes and smile —
material `Material`) kept 29 mm BEHIND the face disc, and the rig's
`show MMD mouth` shapekey is a pure translation toward the camera,
+28.8 mm per unit. Measured from the VRM's own morph data:

| `show MMD mouth` | where the plate sits |
| --- | --- |
| 0.45–0.85 — the VRM's own `ou`/`ee`/`ih`/`oh` binds | wholly behind the face: the mouth never shows |
| 1.0 — its `aa` bind | straddling the face: 55% hidden, poking through in patches |
| ~1.1 | on the face |
| 1.6 — the `aa` pose this guide used to recommend | floating 15–20 mm in front of the face |
| 3.4 — that pose scaled up for a scream | floating 65–70 mm in front |

That is why the expression path "barely moves" it, and why overdriving it
looks right head-on: the offset lies along the camera axis, so a front-view
contact sheet passes while every three-quarter shot shows a black slab off
the face. The rig's vowel shapes (`あ`, `JawOpen`, `A`…) are authored flat
while the face is a dome, so no mix of them follows it either. Leave all of
them at 0 and give the plate three targets of its own, every vertex raycast
onto the face 1.5 mm proud — a sliver under the smile, a wide scream, a round
"oh". Render-verified from six angles on the raw rig and after
`combineMorphs`: every mouth vertex stays 0.4–1.5 mm above the face at every
opening.

```js
// claude_suit mouth that stays ON the face.  Call once in setup(), before the
// first render, and AFTER anything that runs VRMUtils.combineMorphs
// (EidoverseRobotController.create does, unless opts.skipVrmOptimize):
// combineMorphs rebuilds each mesh's targets from the expression binds and
// drops every other target, these included.
function makeSuitMouth(vrm, { standoff = 0.0015 } = {}) {
    let plate = null, face = null;
    vrm.scene.traverse((o) => {
        if (!o.isMesh) return;
        const mats = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => m.name);
        if (!plate && o.morphTargetInfluences && mats.includes('Material')) plate = o;   // eyes + smile + mouth plate
        if (!face && mats.includes('face')) face = o;                                   // the face disc
    });
    if (!plate || !face) throw new Error('makeSuitMouth: not claude_suit.vrm');
    vrm.scene.updateMatrixWorld(true);
    const inv = plate.matrixWorld.clone().invert(), ray = new THREE.Raycaster();
    const onFace = (x, y) => {        // plate-local (x, y) -> face surface z in front of it, + standoff
        const o = plate.localToWorld(new THREE.Vector3(x, y, 0.4));
        ray.set(o, plate.localToWorld(new THREE.Vector3(x, y, -0.6)).sub(o).normalize());
        const hit = ray.intersectObject(face, false)[0];
        return (hit ? hit.point.applyMatrix4(inv).z : 0.115) + standoff;
    };
    const TOP = 1.4762;               // the plate's top edge, just under the painted smile
    const at = (x, y, sx, sy) => { const X = x * sx, Y = TOP - (TOP - y) * sy; return [X, Y, onFace(X, Y)]; };
    const geo = plate.geometry, pos = geo.attributes.position, n = pos.count;
    const seat = new Float32Array(n * 3), wide = new Float32Array(n * 3), round = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
        const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
        if (!(Math.abs(x) < 0.03 && y > 1.44 && y < 1.48 && z < 0.095)) continue;    // the hidden mouth plate
        const S = at(x, y, 0.55, 0.05), W = at(x, y, 1.55, 1.95), O = at(x, y, 0.95, 1.95);
        for (let k = 0; k < 3; k++) {
            seat[i * 3 + k] = S[k] - [x, y, z][k];     // behind the face -> a sliver on it
            wide[i * 3 + k] = W[k] - S[k];             // sliver -> full scream, 57 x 55 mm
            round[i * 3 + k] = O[k] - S[k];            // sliver -> an 'oh', 35 x 55 mm
        }
    }
    const idx = {};
    for (const [name, arr] of [['seat', seat], ['wide', wide], ['round', round]]) {
        geo.morphAttributes.position.push(new THREE.Float32BufferAttribute(arr, 3));
        if (geo.morphAttributes.normal) geo.morphAttributes.normal.push(new THREE.Float32BufferAttribute(new Float32Array(n * 3), 3));
        idx[name] = plate.morphTargetInfluences.push(0) - 1;
    }
    return {
        plate,
        // open 0..1, round 0..1 (the share of oh/ou), extra: { morphName: weight }
        // on the same plate — e.g. { Blink: 1 }, or { blink: 1 } after combineMorphs
        set(open, round = 0, extra = {}) {
            const inf = plate.morphTargetInfluences, d = plate.morphTargetDictionary;
            inf.fill(0);                               // the rig's own mouth targets stay at 0
            const o = Math.min(1, Math.max(0, open)), r = Math.min(1, Math.max(0, round));
            if (o > 0.04) { inf[idx.seat] = 1; inf[idx.wide] = o * (1 - r); inf[idx.round] = o * r; }
            for (const [nm, w] of Object.entries(extra)) if (nm in d) inf[d[nm]] = w;
        },
    };
}
```

Setup: `globalThis._mouth = makeSuitMouth(vrm);` — before the first render,
and after anything that runs `VRMUtils.combineMorphs`
(`EidoverseRobotController.create` does, unless `opts.skipVrmOptimize`):
it drops every target no expression binds, these included. Create any mesh
that shares the plate's geometry afterwards too (`combineMorphs` clones it).

Per frame, **last thing before `renderAsync`** — after any controller update
(a controller runs `vrm.update()`, whose expression manager rewrites
expression-bound targets such as blink). Not in a `mesh.onBeforeRender`
hook: on WebGPU via Metal the hook fires and writes its values (instrumented:
234 calls, 1.565 written to `show MMD mouth`), but the node pipeline has
already gathered the frame's morph influences, so the mouth never moves. The
engine runs `vrm.update()` after `renderFrame`, so values written there
survive the draw.

```js
_mouth.set(open);                  // wide: aa / ee / ih.  open 0..1
_mouth.set(open, 1);               // round: oh / ou
_mouth.set(0, 0, { Blink: 1 });    // set() owns the plate — re-add a blink yourself
```

- `open`: `lipsync.py`'s `get_mouth_openness(frame)` or an RMS envelope,
  0..1. `open = 1` is the full scream; scale ordinary speech by ~0.4.
- Full visemes: winner-take-all, never additive — EMA-smooth the five
  channels (~3 frames), take the dominant one, `o = min(1, value / 0.35)`,
  and map `aa` → `set(o)`, `ee` → `set(0.62 * o)`, `ih` → `set(0.45 * o)`,
  `oh` → `set(0.95 * o, 0.8)`, `ou` → `set(0.62 * o, 1)`; below ~0.03 raw →
  `set(0)`.
- `extra` reaches the other morphs on the plate's mesh: `Blink`,
  `EyeClosedLeft/Right`, `EyeWide`, `Smile`, `MouthSmileLeft/Right`,
  `MouthFrown`. `Blush`/`照れ` live on another mesh (material `BLUSH`).
  After `combineMorphs` only expression names remain: `{ blink: 1 }`,
  `{ happy: 1 }`.
- The render audit's `[lipsync] mouth NEVER moved` line watches the
  expression manager, so it is a false positive on this path — confirm by
  cropping the mouth in a sung frame and a silent one.
- Check any mouth from the side, never only head-on: the old recipe passed
  every front-view check.

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
