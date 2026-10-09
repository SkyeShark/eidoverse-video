# ska_band — a baked eight-piece band performance

A whole song (215.96 s) of a ska band played by eight claudesonas (`claude_suit_wardrobe.vrm`) on the instrument set in
`eidoverse/assets/models/ska_*.glb`: vocals at a mic stand, trombone, trumpet, sax, guitar, bass, organ, drums. Solved
live once (arm IK onto the instruments, finger placement on keys / valves / frets, strokes on the beat) and recorded
with `eidoverse/pose_bake.js`; playback is a copy per frame.

| file | frames | fps |
|---|---|---|
| `band_60fps.bin` | 12,958 | 60 |
| `band_30fps.bin` | 6,479 | 30 |

## What is in it

576 tracks (position, quaternion, scale each; 1,059 of the 5,760 columns move — the rest are stored once). Track names
are `<player>:<part>`, players `vox trombone trumpet sax guitar bass organ drums`:

- `<player>:<bone>` — the VRM's NORMALIZED humanoid bones (`vrm.humanoid.normalizedHumanBones[bone].node`);
- `<player>:scene` — the VRM's root (`vrm.scene`); `<player>:lookAt` — its `VRMLookAtQuaternionProxy` (the eyes);
- `<player>:holder#i:<name>` — the held instrument's nodes, in `holder.traverse` order;
- `drums:stick0`, `drums:stick1` — the drumsticks; `vox:mic` — the microphone; `stand` — the mic stand.

Faces are NOT baked: lipsync and expressions are driven live at playback (`eidoverse/claudesona_face.js`), the way a
game plays baked body animation with runtime blendshapes.

## Playing it

```js
const PB = await import(new URL('pose_bake.js', EIDOVERSE_DIR).href);
const file = new URL('assets/animations/ska_band/band_30fps.bin', EIDOVERSE_DIR).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const h = PB.bakeHeader(file);                       // { key, frames, fps, tracks: [names], ... }
const tracks = h.tracks.map((name) => ({ name, obj: resolve(name) }));   // your objects, by the names above, in this order
const bake = PB.createPoseBake(THREE, { tracks, frames: h.frames, fps: h.fps, file, key: h.key });
bake.load();
// every frame k: bake.apply(k); then each vrm.update(dt) (raw bones + spring bones from the normalized pose); then the faces
```

`load()` refuses a file whose track list differs from yours — bind every name, in order.
