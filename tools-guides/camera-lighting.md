# Cameras and lighting

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

## Lighting

Choose lighting for the piece: an HDRI, the world-space sky, a studio light
rig, practical sources, or a combination. PBR surfaces need illumination and
reflective metals need an environment to reflect. Emissive or unlit imagery is
also available when that is the intended look.

- An HDRI supplies environment lighting and reflections. Use the native
  [HDRI loading pattern](scene-format.md#hdri-lighting-the-reusable-pattern)
  for decoding, orientation and PMREM. Background visibility is a separate
  artistic choice. The [sky system](sky-weather.md) adds spatial atmosphere,
  clouds, celestial bodies and time-of-day lighting.
- Add lights where they help the image: a key, a rim, a nearby display or a
  lamp. A point light near a wall can brighten that wall with less spill on a
  distant subject; a directional light has no distance falloff.
- Start with one shadow-casting directional light when appropriate. Additional
  shadow maps have a cost; inspect performance and the resulting shadows.
  Shadow-casting `SpotLight` has caused MToon failures on this pinned native
  stack. Use another shadow source for VRM scenes unless that compatibility
  has been verified in the current setup.
- If a metal looks black, check the environment, material conversion, exposure
  and reflection path. Do not globally lower authored metalness to disguise a
  lighting problem. Coated paint and exposed metal should retain their distinct
  material responses.
- Inspect bright surfaces at full resolution. Bloom and exposure can erase
  facial detail, lettering and bevels. Adjust the contributing lights, material
  emission, effect strength or exposure while checking the rest of the frame.

## Camera targets and framing

An asset's origin may sit at its feet, a mounting port or an authoring pivot.
For a bounding-box-based target, use:

```js
globalThis.lookAtObject(camera, vrm.scene, { yBias: 0.3 });
const target = globalThis.focusPoint(deskProp);
```

`focusPoint(obj, { yBias })` returns a world-space bounding-box center;
`yBias` offsets it by a fraction of the height. Check the actual composition
for the current pose, especially with skinned or asymmetric subjects. An
explicit world-space target remains useful for a chosen detail or empty space.

Keep the camera outside the geometry it should photograph. Measure bounds and
inspect the lens/FOV and standoff together; a fixed distance in meters is not
appropriate for every asset scale or close-up.

## CameraSafety

`CameraSafety` is an injected raycast helper. It checks sightlines against
scene meshes and suggests alternative positions; the engine does not install
it as an automatic collision constraint.

```js
const cam = new CameraSafety(scene, { padding: 0.5, minDistance: 0.3 });
cam.exclude(vrm.scene); // avoid starting sightline rays inside the subject
const shots = [
  { time: 0, position: [3, 2, 4], target: [0, 1, 0] },
  { time: 3, position: [1, 2, 4], target: [0, 1, 0] },
];
const issues = cam.checkPath(shots, { samplesPerSegment: 12 });
console.log('Camera path observations:', issues);
const candidate = cam.safePosition(desiredPos, lookTarget);
```

`exclude` accepts an object, a group (including child meshes), or an array.
Exclude intentional non-obstacles selectively. An excluded subject still
needs camera clearance. Call `refresh()` after adding relevant scene meshes.
`checkPath` samples the keyframes and interpolated positions; it does not prove
every point along a curved path is clear or predict future moving geometry.

Use the findings to plan shot poses and the path between them. `safePosition`
can also run during motion, but independent raycast corrections can jump as
occluders change. If using it dynamically, plan continuity and recheck the
smoothed path's clearance. Neither "always every frame" nor "only at cuts"
is a general solution. Review the rendered sequence.

## Camera motion

An eased move between chosen poses is a useful starting point. Dolly, orbit,
locked shots, handheld motion and deliberate oscillation are all available.
Choose their pace and amplitude for what the viewer should experience.

Unexpected bouncing often comes from a noisy target, repeated interpolation
resets, FOV oscillation or collision corrections. Inspect the time function
and update ownership before adding another smoothing layer. The renderer's
camera-motion audit flags some rapid position/FOV reversals; investigate those
against the intended motion. It does not detect camera/mesh intersections.
