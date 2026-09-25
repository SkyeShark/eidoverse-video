# WebXR — scenes in a headset browser

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

The renderer makes videos. To stand *inside* a piece — walk round a city while
its choreography plays, hold it on a table in front of you — the same world can
be shown live in a headset's browser with WebXR. Everything here was worked out
on a Quest 3 in the Quest Browser with three r184; other headsets with a WebXR
browser should work the same way but have not been tried.

This is a live page, not a render: it runs at the headset's frame rate on a
phone-class GPU, twice (once per eye). A scene script written for the renderer
does not open in a headset as it is. The usual route is to **reuse the piece's
data** (choreography, positions, timings — whatever the scene script reads) and
write a lighter page that draws it: fewer, bigger meshes (one box per building
floor instead of one per block), no post effects (they do not run in XR here),
glowing colours brightened instead of bloomed.

## The kit

| File | What it is |
| --- | --- |
| [eidoverse/xr/serve.py](../eidoverse/xr/serve.py) | HTTPS server for the headset (+ HTTP on 127.0.0.1 for the desktop), self-signed certificate, `/report` telemetry log |
| [eidoverse/xr/xr_kit.js](../eidoverse/xr/xr_kit.js) | Browser module: renderer, session loop, world rig (street/table), controllers, desktop preview, head veil |
| [eidoverse/xr/example.html](../eidoverse/xr/example.html) | A complete minimal page on the kit — copy it to start |
| [eidoverse/xr/shot.mjs](../eidoverse/xr/shot.mjs) | Stills of a page from headless Chrome, through the same WebGL2 backend |
| [eidoverse/xr/quest.py](../eidoverse/xr/quest.py) | The headset over adb: Wi-Fi debugging, open a page, keep awake, pull recordings |

Pages import three.js from `node_modules` (run `python eido.py bootstrap`
once), so they use exactly the renderer's three version — no copied builds.

```sh
python3 eidoverse/xr/serve.py            # prints the headset URL: https://<this machine's LAN address>:8892/
python3 eidoverse/xr/quest.py wireless   # once per headset restart, over USB
python3 eidoverse/xr/quest.py open https://<lan-ip>:8892/eidoverse/xr/example.html
```

On the headset, accept the certificate once per address and port (Advanced ->
Proceed), then press ENTER VR. `serve.py --home /work/<id>/vr/index.html` makes
`/` open your page; `--log work/<id>/vr/results.jsonl` keeps its reports with
the piece.

## Rules the kit encodes (learned in the headset)

1. **`WebGPURenderer` on its WebGL2 backend** (`forceWebGL: true`): the Quest
   browser has WebGPU for flat pages but no `XRGPUBinding` yet, so XR needs the
   WebGL2 path. TSL node materials work unchanged on it.
2. **Move the world, never the camera.** three r184's XR manager ignores the
   camera's parent in a session: a camera rig either does nothing (you spawn at
   the origin) or freezes head-locked. Put the whole world in a `stage` group
   and move that — `WorldRig` does.
3. **Never `renderer.setSize()` while presenting.** Entering VR fires a window
   resize; reconfiguring the swapchain kills the XR layer. `keepSized()` guards it.
4. **Arm a session by polling** `renderer.xr.getSession()` in the loop; the
   `sessionstart` event is not reliable. Count the session's own frames next to
   the loop's: if the loop runs and the session's frames stop, the XR layer has
   died (the heartbeat's `xrAlive`).
5. **In a headset there is no console.** Report to the server: heartbeats,
   measured fps, errors with their stacks. That log is how a session is read
   back afterwards — including where the viewer went.
6. **Fades and flashes go on a sphere round the head** (`makeVeil`): there is
   no screen for a full-screen quad.
7. **Stop screen mirroring (scrcpy) before a session**: its encoder load
   freezes immersive sessions. Record with the headset's own recorder and
   `quest.py pull`.

## A page on the kit

The example is the reference; the parts:

```js
import { telemetry, createRenderer, keepSized, startLoop, WorldRig, Pads, BTN, makeLaser, Desktop, makeVeil } from '/eidoverse/xr/xr_kit.js';
const report = telemetry('my_piece');                    // POSTs to /report; uncaught errors too
const { renderer } = await createRenderer();             // WebGL2 backend, local-floor, VR button
const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.02, 400);
scene.add(camera); keepSized(renderer, camera);
const stage = new THREE.Group(); scene.add(stage);       // the world, in its own units, y up
const rig = new WorldRig({ renderer, camera, stage, street: 0.25, table: 0.01 });   // metres per unit
const pads = new Pads(renderer, scene), desk = new Desktop({ camera, dom: renderer.domElement });
rig.standAt(new THREE.Vector3(0, 0, 10), { facing: new THREE.Vector3(0, 0, -1) });
startLoop(renderer, scene, camera, {
  report,
  onSession: () => setTimeout(() => rig.standAt(START, { facing }), 300),   // once the head pose is live
  heartbeat: () => ({ mode: rig.mode, at: rig.where().toArray() }),
  onFrame: (now, dt, inXR) => {
    if (inXR) { pads.poll(); const L = pads.hand('left'), R = pads.hand('right');
      if (rig.mode === 'street') { rig.walk(L.x, -L.y, dt); rig.flick(R.x); } }
    else desk.update(dt);
  },
});
```

- **`WorldRig`** — `standAt(point, { facing })` puts you at a stage point (on
  the ground) facing a stage direction; `toTable({ centre, scale, at })` puts
  the world in front of you (or at room point `at`); `walk(right, forward, dt)`,
  `turn(radians)`, `flick(stickX)` (30° snap turns), `spin`/`zoom`/`slide` for
  the table, `groundHit(origin, dir)` (where a controller ray meets the ground,
  in stage units), `where()` (you, in stage units). Street scale is metres per
  stage unit: at 0.12 a 1.7 m person stands 14 units tall.
- **`Pads`** — `poll()` once a frame, then `hand('left'|'right')` gives the
  dead-zoned stick `x`/`y`, `pressed[i]`, `edge(i)`, `released(i)` and the
  pointing `ray`. `BTN`: `TRIGGER`, `GRIP`, `STICK`, `AX` (A right / X left),
  `BY` (B right / Y left).
- **`Desktop`** — the preview without a headset: WASD + drag to look in the
  street, drag to orbit and wheel to zoom on the table. On the desktop the
  camera moves; in a session the rig moves the world.
- **`startLoop`** — reports `sessionarmed`, `hb` every 3 s (frames, the
  session's frames, `loopAlive`, `xrAlive`, triangles + your `heartbeat()`),
  `measured` (fps over the first 10 s) and `contextlost`. `still: true` sets
  `window.__shot = 'ready'` after three frames, for `shot.mjs`.
- **`makeLaser`**, **`makeVeil`** — a pointing laser; a sphere round your head
  for fades and flashes.

## Checking without a headset

```sh
node eidoverse/xr/shot.mjs http://127.0.0.1:8894/eidoverse/xr/example.html work/<id>/shots \
    "t=4&street=0,10&look=30&pitch=5" "t=4&view=table"
```

A page decides what its query means (the example: `t` time, `street=x,z`
where you stand, `look`/`pitch` in degrees, `view=table`) and sets
`window.__shot = 'ready'` when that moment is drawn. Stills show the geometry,
the colours and where things are — not the frame rate, the comfort of the
motion, or anything only a headset shows. Try it in the headset before calling
it done, and read the session's reports.

## Performance notes (Quest 3)

Frame rates measured on real pages: a voxel city with about 1.4 million
triangles, 70 creatures and about 30 draw calls held 85–90 fps at the 90 Hz
default; the busiest stretch (2.2–2.3 million triangles) dipped to 75–80 fps.
Frame hitches come from the CPU side more often than the GPU: re-uploading big
instance buffers (upload only the changed ranges), work that grows with the
whole world every frame, and more than about 14 simultaneous HRTF-panned
sounds. `setFramebufferScaleFactor(0.9)` and foveation 1 are the kit's
defaults.
