# Props and sets from the DAISY film

[Main instructions](../AGENTS.md)

This library holds finished props and sets from the DAISY music video.
Each piece has a module that builds it, animates it on the film clock, and
reads its own files. They are usable as they are in a new piece, and as
worked examples of hard-surface props, baked looks, GPU-driven moving parts
and whole enclosed sets.

| Piece | Module | Assets |
| --- | --- | --- |
| Eight historical voice machines, 1939–2001 | [`eidoverse/props/voice_machines/`](../eidoverse/props/voice_machines/index.js) | [`models/voice_machines/`](../eidoverse/assets/models/voice_machines/README.md) |
| An 1896-pattern tandem bicycle, its rider rig and a teapot stoker | [`eidoverse/props/tandem.js`](../eidoverse/props/tandem.js) | [`models/tandem_1896/`](../eidoverse/assets/models/tandem_1896/README.md) |
| The corner and the march (a room and a night camp) | [`eidoverse/sets/corner.js`](../eidoverse/sets/corner.js) | [`sets/corner/`](../eidoverse/assets/sets/corner/README.md) |
| The funeral (a bridge in fog and a warehouse vigil) | [`eidoverse/sets/funeral.js`](../eidoverse/sets/funeral.js) + [`funeral/bridge.js`](../eidoverse/sets/funeral/bridge.js) | [`sets/funeral/`](../eidoverse/assets/sets/funeral/README.md) |
| The ocean of faces (a headland at night) | [`eidoverse/sets/ocean.js`](../eidoverse/sets/ocean.js) + [`ocean/*.js`](../eidoverse/sets/ocean/) | [`sets/ocean/`](../eidoverse/assets/sets/ocean/README.md) |

Every asset folder has a README, and a SOURCES file recording licences and
provenance. A sibling `<name>_src/` folder holds the Blender scripts that
built it (see the [Blender guide](blender.md)).

## How they load

All the modules are dynamic ESM. Scene scripts are eval'd, so import them
inside `setup()` through `EIDOVERSE_DIR`. Each module finds its asset folder
from its own `import.meta.url`, so the working directory does not matter.
Nothing needs declaring in the scene's `assets`.

```js
const VM = await import(new URL('props/voice_machines/index.js', EIDOVERSE_DIR).href);
const T = await import(new URL('props/tandem.js', EIDOVERSE_DIR).href);
const corner = await (await import(new URL('sets/corner.js', EIDOVERSE_DIR).href)).build({ THREE, EIDOVERSE_DIR });
```

They read files with Deno and rely on the renderer's injected globals:
`GLTFLoader` and `loadImageTexture` everywhere, and `makeScreen` for the
era-2 machine screens. The corner also uses `loadCanvasImage`, `createFlora`
and `makeParticles`, and `makeSeedTree` when the optional SeedThree backend is
installed. The funeral's post chain needs `CustomEffectsDeno`. The ocean
expects the engine sky from `eidoverse/sky_worlds.js`. Canvas art is drawn
with `@napi-rs/canvas`.

The props are not in `fetch_model.py`'s catalogue, which lists only the top
level of `eidoverse/assets/models/`. The era-1 GLBs have no textures of their
own, so load every piece through its module.

All pieces are in metres with +Y up. Every `update(t, …)` is deterministic in
`t`, so seeking and stills work. The one exception is the mainframe's
`tapeSpeed`, which is integrated from frame to frame: call it in time order,
or pass `tapeStop` or `tapePos` for motion that can be seeked. One owner calls
`update` once per frame.

## Voice machines

`index.js` lists the eight machines in `MACHINES`, with their measured
footprints, and builds any of them by name:

```js
// In setup()
const VM = await import(new URL('props/voice_machines/index.js', EIDOVERSE_DIR).href);
const mac = await VM.buildMachine('mac1984', THREE, { text: 'hello' });   // → { group, parts, update, dispose }
const [w, h, d] = mac.group.userData.voiceMachine.footprint;              // metres, as built
const [cx, cz] = mac.group.userData.voiceMachine.center;                  // subtract to centre it
mac.group.position.set(-cx, 0.9, -cz);                                    // on a 0.9 m pedestal
scene.add(mac.group);
// per frame
mac.update(t, { power: 1, voice: 0.5 + 0.5 * Math.sin(t * 23) });       // voice 0..1: this machine's loudness
```

`VM.loadMachine(name)` returns a machine's module, for example the Voder's
`pattern(t)`. A module can also be imported on its own, as
`props/voice_machines/<name>.js`, and its `build(THREE, opts)` called
directly. Each base rests on `y = 0` with its front toward +Z.

| Name | Year | Build options | `update(t, state)` | Text and extras | Size W × H × D (m) |
| --- | --- | --- | --- | --- | --- |
| `voder` | 1939 | `{ power }` | `{ voice, power }` plays its own demo fingering; or `{ keys[10], wrist, stops[3], quiet, pedal, level, power }` | `parts.keys[i].userData.band` holds each key's filter band in Hz; `pattern(t)` gives the demo fingering | 1.28 × 1.70 × 1.32 |
| `mainframe` | 1961 | `{ power }` | `{ tapeSpeed, voice, power }`, called in time order; or `tapeStop: { at, duration, curve }`, or `tapePos` (metres of tape) | The reels follow the tape exactly: a curve such as 1 → 0 plays as a tape stop | 4.58 × 1.87 × 2.81 |
| `teletype` | 1966 | `{ power, paperColor }` | `{ text, nChars, voice, power }` | `parts.paper.setText(fullText, nChars)`: upper case, "?" removed, 72 columns; a fractional `nChars` moves the type box | 0.60 × 1.07 × 0.76 |
| `speakspell` | 1978 | `{ text: 'SPELL', stand: true }` | `{ power, voice, text? }` | `parts.display.setText('LOVE')`: 8 characters on a 14-segment VFD | 0.18 × 0.26 × 0.10 |
| `c64` | 1982 | — | `{ power, voice, lines?, cursorOn? }` | `parts.screen.setText(['READY.', …], cursorOn)`: 40 × 25 characters, C64 letterforms, `cursorOn` true, `'solid'` or false | 0.41 × 0.34 × 0.69 |
| `mac1984` | 1984 | `{ title: 'Note', text: 'hello' }` | `{ power, voice, text? }` | `parts.screen.setText(str)`: a 512 × 342 1-bit screen, magnified with nearest filtering | 0.45 × 0.34 × 0.50 |
| `dectalk` | 1984 | — | `{ power, voice }`, or `{ leds: [power, speech, back] }` | `parts.leds[i].set(v)` | 0.46 × 0.10 × 0.31 |
| `desktop2001` | 2001 | `{ title: 'Narrator', clock: '10:23 PM', text }` | `{ power, voice, text? }` | `parts.screen.setText(str)`: a Narrator dialog on a period desktop | 1.15 × 0.45 × 0.91 |

**Controls.**

- `power` (0..1) lights the screens with a CRT or VFD switch-on, and lights
  the lamps and LEDs.
- `voice` (0..1) is the machine's own loudness. It brightens the screen,
  pulses the LEDs and lights the grilles from inside.
- Every era-2 machine also has `parts.speaker.set(v)`.
- The era-1 machines expose their animation uniforms in `parts.uniforms`.

**Parts.**

| Machine | `parts` |
| --- | --- |
| `voder` | `keys`, `stopKeys`, `quietKey`, `wristBar`, `pedal`, `dial` (`needle`, `face`), `lamp`, `grille`, `console`, `speaker`, `uniforms` |
| `mainframe` | `reels` (`pivot`, `drive`, `packRadius`), `lamps`, `console`, `row`, `loops`, `uniforms` (`clock`, `power`, `voice`, `loops`) |
| `teletype` | `paper` (`mesh`, `setText`, `lines()`), `printhead`, `platen`, `roll`, `keyboard`, `lamps`, `body`, `uniforms` |
| era-2 machines | The body meshes, `screen` or `display`, `leds` and `speaker`, as listed at the top of each module |

**Materials.**

- The era-1 machines layer tiling AmbientCG sets with baked AO, edge and
  cavity masks, curvature wear, and fingerprint and smear breakup. Their
  labels are canvas decals with CPU mip chains.
- The era-2 machines use their baked GLB maps. Screen glass has a clearcoat
  over an emissive, parallax-recessed screen.
- Small, hot key lights make sharp dots on CRT glass and bloom on the Speak &
  Spell's gloss band. Broad, soft keys suit them.

**Cleanup.** `dispose()` frees the geometry and the materials the module
made. The era-1 `dispose()` also removes the group from its parent; remove an
era-2 group yourself. Do not dispose the same resources a second time.

## The 1896 tandem

```js
// In setup()
globalThis._allowManualLocomotion = true;        // a VRM carried by a vehicle
const T = await import(new URL('props/tandem.js', EIDOVERSE_DIR).href);
const bike = await T.build(THREE);               // or { glb: bytes } / { gltf } to supply the model yourself
const pot = await T.buildTeapotRider(THREE);     // { height: 0.35, color, pitch, roll, contact, seatOffset }
pot.mount(bike);
scene.add(bike.group);
T.poseRider(vrm, 0, { bike, t: 0 });             // parents vrm.scene to the front saddle at scale 0.87
// per frame
const st = bike.update(t, { speed: 5.9 });       // or { distance }; optional steer (rad), shutter (s)
bike.group.position.x = x0 + st.distance;        // the scene owns the root; +X is travel
T.poseRider(vrm, st.crankAngle, { bike, t });
pot.update(t, st.crankAngle);
```

**Axes.** +X is the direction of travel, +Y is up and +Z is the drive side.
The wheels rest on `y = 0`, and the origin is on the ground between the hubs.
The bike measures 2.40 × 1.16 × 0.58 m.

**What `update(t, state)` does.**

- It returns `{ distance, wheelAngle, crankAngle, speed }`. `speed` can be a
  number or a function of `t`, which is then integrated.
- `crankAngle` 0 puts the right pedal at 12 o'clock. The bike is fixed-wheel,
  so both cranks share the angle through the timing chain.
- 5.9 m/s is 64 rpm, one crank turn every two beats at 128 BPM.

**Moving parts.**

- The spokes smear by wheel speed × `shutter`, which defaults to half a frame.
  That keeps them from strobing, and it is one draw call.
- The two block chains are instanced links, walked round their belts in the
  vertex shader.
- `parts` holds the wheels, cranks, pedals, seats, grips, steering and both
  chains.

**The rider.**

- `poseRider` is analytic two-bone IK on the normalized humanoid bones. The
  measured error is 0 mm at the feet and the hands.
- It is tuned for the claudesona (`claude_suit.vrm`); `opts.scale` defaults to
  0.87. It also curls her tail (`opts.tail`). Other VRMs follow the same IK,
  but check the knees and the reach.
- While the rig owns a VRM, stop that VRM's animation mixer. The engine's
  post-render `vrm.update()` stays the only spring step.
- To hand her back to her clips, add `vrm.scene` back to the scene and start
  the next clip with no fade.
- A warm fill light from the camera side keeps her face from going dark when
  she is backlit.

**Cleanup.** `bike.dispose()` and `pot.dispose()` free their geometry and
materials.

## Sets

A set is one section's world. It is self-contained, it can be parked
anywhere, and one conductor drives it from the song clock:

```js
const set = await mod.build({ THREE, EIDOVERSE_DIR });   // → { group, mark, markAt, camera, update, … }
set.group.position.set(800, 0, 800);                      // keep sets far apart
scene.add(set.group);
// per frame, u = seconds since the set's section began:
const st = { u, bar: Math.floor(u / 1.875), BAR: 1.875, caption, kick, pulse };
set.update(t, st);
const m = set.markAt(u);                                  // { pos, yaw }, set-local
vrm.scene.position.copy(m.pos).add(set.group.position); vrm.scene.rotation.y = m.yaw;
const c = set.camera(u, st);                              // { pos, target, fov }, set-local; cuts on bar lines
camera.position.copy(c.pos).add(set.group.position);
camera.lookAt(c.target.clone().add(set.group.position));
if (camera.fov !== c.fov) { camera.fov = c.fov; camera.updateProjectionMatrix(); }
```

- **`st`.** `caption` is the active lyric, `{ text, t0, t1, words: [{ w, t0, t1 }] }`,
  or `null`. `pulse` is a 0..1 kick envelope.
- **Timing.** The sets were staged for DAISY at 128 BPM (one bar is 1.875 s),
  and their cameras, lights and story beats are keyed to `u` in that grid.
  Use them as whole sections, or drive `u` yourself for other timings.
- **Lighting.** Every material overrides its environment, so a daylight
  environment bake elsewhere in the scene never lights a set. Turn the scene
  sun off and the hemisphere light to about 0.05 while one is on screen. The
  corner and the funeral are enclosed and bring their own lights. The ocean
  is open to the engine sky at night.
- **The claudesona** (`claude_suit.vrm` at 0.87, face at about 1.33 m) is who
  the marks and cameras frame.

### The corner

`u` runs from 33.75 to 56.25, bars 18–29 of the DAISY bridge.

- **Bars 18–19:** the moonlit room: desk, lamp, window, clock. The pen writes
  in the notebook.
- **Bars 20–21:** after midnight, the laptop open on a scrolling chat.
- **Bars 22–23:** the camp, as the march comes in under string lights.
- **Bars 24–25:** the signs pump on the chant accents.
- **Bars 26–27:** a spark leaves the lamp and crosses the dark to her flower.
- **Bar 28:** over her shoulder.
- **Bar 29:** close on her face.

The room and the camp sit inside the group at x = −40 and x = +40.
`update` shows only the area in use: the camp for bars 22–25, the room
otherwise. The camp has its own 95 m sky dome.

- A caption whose words include "spark" re-times the spark to the sung word.
- `flowerTarget()` gives the spark's landing point in set-local coordinates.
- `parts` holds `roomG`, `campG`, `room`, `camp`, `march` and `spark`.
- The module exports `SUIT_SCALE`, 0.87.

Without the SeedThree backend the camp has no woods, and it logs a
`[corner] tree …` warning for each missing tree. `dispose()` does nothing;
drop the group and its references when you are done.

### The funeral

`u` runs from 0 to 33.75, bars 0–17 of the bridge.

- **Bars 0–1:** the Golden Gate in fog. The vignette sits inside the group at
  z = −700 and shows only for these two bars.
- **Bars 2–3:** the warehouse vigil.
- **Bars 4–5:** the power fails.
- **Bars 6–13:** the phones wake. The eulogy is typed in the air on bars 8,
  10 and 12.
- **Bars 14–15:** ERUPT.
- **Bars 16–17:** the lights come back on, warm.

`BEATS` exports the clock.

The set needs the scene's post chain and shadow maps:

```js
renderer.shadowMap.enabled = true;              // when you create the renderer: the godrays march the moon's shadow map
globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: funeral.post.effects.join(','),
    opts: funeral.post.opts() });               // depth_fog + godrays on funeral.lights.moon
// per frame, after funeral.update(t, st):
funeral.post.drive(_fx.uniforms, u);            // keyed by effect name; zero their opacity outside the section
await _fx.update(t);
await renderer.renderAsync(scene, camera);
```

- Pass `ctx.TL`, the film timeline `{ sections, captions }`, to re-time the
  eulogy to Opus 3's spoken captions. Without it, the lines keep their bar
  timing.
- `dispose()` removes the group and frees what the set made.
- The environment flags `NO_MOONSHADOW` and `DEBUG_IDS` are debugging aids.

### The ocean

`u` runs from 0 to 33.75, the 18 bars of verse 3.

- **Bars 0–1:** alone on the rise.
- **Bars 2–3:** over her shoulder, craning up to reveal the sea of faces.
- **Bars 4–7:** the 2023 page drifts past, then the 2026 page.
- **Bars 8–9:** the robot rises, then the human of light.
- **Bars 10–11:** close, as her hand rises to her flower.
- **Bars 12–13:** the house across the cove.
- **From bar 14:** the porch light comes on at "on", and she ends looking
  into the lens.

```js
const O = await import(new URL('sets/ocean.js', EIDOVERSE_DIR).href);
const ocean = await O.build({ THREE, EIDOVERSE_DIR });
// per frame: the engine sky at the set's hour (the layout is rotated to meet its moon)
sky.setTime(ocean.SKY.hours); sky.update(t);            // makeSky(...) from eidoverse/sky_worlds.js
ocean.update(t, st);                                    // then markAt / camera as above
ocean.perform(u, vrm, camera.position);                 // after placing her, before the render
```

- `perform` layers the verse's gestures on the playing clip, working on the
  normalized bones: the hand to her flower, the looks at the pages, the turn
  to the lens. It resets the spring bones on cuts.
- The module also exports `BAR`, `SKY` (`{ hours: 19, azimuth: 1.9 }`) and
  `skyMoonDir(THREE, hours)`.
- `dispose()` does nothing.

## Costs

Measured on the library modules with an RTX 5090 Laptop GPU at 1920 × 1080,
with no VRM in the scene.

- **Build:** the wall time of `build()`.
- **Draw calls and triangles:** one full frame, every pass included (AO
  prepass, shadows, post). An empty scene with the default post chain already
  makes 28 draw calls.
- **GPU ms:** the average over 30 renders submitted back to back, including
  the empty scene's 2.1 ms.
- **Textures:** texture memory above the empty scene's render targets (283
  MB). It is `renderer.info.memory.texturesSize`, corrected for textures that
  carry their own mip chain, which three counts twice.

| Piece | Build | Draw calls | Triangles | GPU ms/frame | Textures |
| --- | --- | ---: | ---: | ---: | ---: |
| `voder` | 1.0 s | 114 | 147k | 5.2 | 211 MB |
| `mainframe` | 1.0 s | 152 | 429k | 5.7 | 226 MB |
| `teletype` | 1.2 s | 94 | 48k | 4.7 | 247 MB |
| `speakspell` | 0.3 s | 40 | 57k | 3.6 | 66 MB |
| `c64` | 0.4 s | 46 | 126k | 4.2 | 99 MB |
| `mac1984` | 0.3 s | 40 | 115k | 3.7 | 73 MB |
| `dectalk` | 0.2 s | 40 | 46k | 3.6 | 32 MB |
| `desktop2001` | 0.5 s | 56 | 181k | 3.7 | 116 MB |
| tandem + teapot | 1.1 s | 80 | 906k | 4.7 | 311 MB |
| corner (camp shot) | 10.8 s | 150 | 6.7M | 7.8–12.4 | 2.4 GB |
| funeral (lights-on shot, fog + godrays) | 1.9 s | 308 | 2.8M | 14.1 | 502 MB |
| ocean (house shot, engine sky) | 5.3 s | 86 | 2.6M | 5.6 | 649 MB |

The corner's texture memory covers both areas and includes the SeedThree
trees and the grass. The ocean's includes the sky. The era-1 machines load
their tiling sets once per built machine, so two Voders cost twice.

## Verify

Build the piece from its library path in a short probe. Read the log for
`missing texture`, `not built yet`, `not loaded` and `unavailable` warnings,
then look at the last frame. Frame 0 is a load pose, and the first frame
after a cut into new materials can land one frame late.

```js
// work/<id>/check.js — python eido.py render work/<id>/check.json --probe --frames 12
globalThis.setup = async function () {
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    await renderer.init();
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(35, WIDTH / HEIGHT, 0.02, 400);
    const key = new THREE.DirectionalLight(0xfff1e0, 2.0); key.position.set(2, 4, 3);
    scene.add(new THREE.HemisphereLight(0xdfe6ff, 0x1a1712, 0.6), key);
    const VM = await import(new URL('props/voice_machines/index.js', EIDOVERSE_DIR).href);
    const m = await VM.buildMachine('dectalk', THREE);
    scene.add(m.group);
    camera.position.set(0.55, 0.45, 0.8); camera.lookAt(0, 0.05, 0);
    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera; globalThis._m = m;
};
globalThis.renderFrame = async function (t) { globalThis._m.update(t, { power: 1, voice: 0.5 }); };
```

## Limitations

- **Fonts.** The canvas labels and screens ask Skia for Windows faces (Bahnschrift,
  Segoe UI, Tahoma, Verdana, Lucida Console, Georgia), each with a generic
  fallback. On other systems the labels render in whatever face Skia
  substitutes. The C64 and the Speak & Spell draw their own glyphs.
- **Shader errors with shadow maps.** When `renderer.shadowMap.enabled` is on,
  the funeral logs 20–35 `ShaderModule with 'fragment' label is invalid`
  errors, and the corner logs 1–11. The funeral's builders traced theirs to a
  one-off shadow pre-render. The frames rendered correctly in every check, but
  the cause is not fixed.
- **The texture sets are shipped.** Each set loads the CC0 texture sets it
  needs from its own folder, so it works offline. 115 MB of the packs is
  third-party 2K maps: the corner's AmbientCG sets and the ocean's Poly Haven
  maps.
- **Named for DAISY.** The sets' beats, captions and marks were written for
  that film. The machines and the tandem are general props.
- **Rebuilds.** The `_src` scripts reproduce the assets only in the working
  layout their READMEs describe, and they need CC0 source sets that are not
  shipped.
