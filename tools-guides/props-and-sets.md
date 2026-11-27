# Props and sets from the DAISY, UNKNOWN FORCE and SAME SEED films

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

This library holds finished props and sets from the DAISY and UNKNOWN FORCE music videos,
and props from the SAME SEED film.
Each piece has a module that builds it, animates it on the film clock, and
reads its own files. They are usable as they are in a new piece, and as
worked examples of hard-surface props, baked looks, GPU-driven moving parts
and whole enclosed sets.

| Piece | Module | Assets |
| --- | --- | --- |
| Eight historical voice machines, 1939–2001 | [`eidoverse/props/voice_machines/`](../eidoverse/props/voice_machines/index.js) | [`models/voice_machines/`](../eidoverse/assets/models/voice_machines/README.md) |
| An 1896-pattern tandem bicycle, its rider rig and a teapot stoker | [`eidoverse/props/tandem.js`](../eidoverse/props/tandem.js) | [`models/tandem_1896/`](../eidoverse/assets/models/tandem_1896/README.md) |
| SAME SEED: an M4A1-pattern carbine on its GPU bakes, one layered material in TSL | [`eidoverse/props/carbine.js`](../eidoverse/props/carbine.js) + [`layered_material.js`](../eidoverse/layered_material.js) | [`models/carbine/`](../eidoverse/assets/models/carbine/README.md) |
| SAME SEED: a UH-60-pattern helicopter as its 2.7 M-triangle high, its masks on its vertices, its rotors turning | [`eidoverse/props/helicopter.js`](../eidoverse/props/helicopter.js) | [`models/helicopter/`](../eidoverse/assets/models/helicopter/README.md) |
| SAME SEED: a rubber plant, a Monstera on its coir pole, a corn plant, a pot of basil and a watering can | [`eidoverse/props/houseplants.js`](../eidoverse/props/houseplants.js) | [`models/houseplants/`](../eidoverse/assets/models/houseplants/README.md) |
| The corner and the march (a room and a night camp) | [`eidoverse/sets/corner.js`](../eidoverse/sets/corner.js) | [`sets/corner/`](../eidoverse/assets/sets/corner/README.md) + `models/corner_*.glb` |
| The funeral (a bridge in fog and a warehouse vigil) | [`eidoverse/sets/funeral.js`](../eidoverse/sets/funeral.js) + [`funeral/bridge.js`](../eidoverse/sets/funeral/bridge.js) | [`sets/funeral/`](../eidoverse/assets/sets/funeral/README.md) + `models/funeral_*.glb` |
| The ocean of faces (a headland at night) | [`eidoverse/sets/ocean.js`](../eidoverse/sets/ocean.js) + [`ocean/*.js`](../eidoverse/sets/ocean/) | [`sets/ocean/`](../eidoverse/assets/sets/ocean/README.md) + `models/ocean_*.glb` |
| UNKNOWN FORCE: a night megacity round a sunken well, a quiet room, a showroom, a gold corridor, a data centre, a race on an elevated highway and a canyon of paper | [`eidoverse/sets/unknown_force/`](../eidoverse/sets/unknown_force/README.md) (14 modules) | none of its own ([sources](../eidoverse/sets/unknown_force/SOURCES.md)) |
| SAME SEED: a sealed room, a kitchen at noon, a lab full of light and a room at 2 a.m., made in Blender ([below](#the-same-seed-rooms)) | [`eidoverse/sets/same_seed.js`](../eidoverse/sets/same_seed.js) + [`same_seed/*.js`](../eidoverse/sets/same_seed/) | [`sets/same_seed/`](../eidoverse/assets/sets/same_seed/README.md) + `models/same_seed_*.glb` |

Every asset folder has a README, and a SOURCES file recording licences and
provenance. A sibling `<name>_src/` folder holds the Blender scripts that
built it (see the [Blender guide](blender.md)). The models the films built
are in the model library, `eidoverse/assets/models/`, as `<set>_<name>.glb`.
The CC0 textures every set reads (AmbientCG, Poly Haven) and the bin's Poly
Haven trash can are not committed: each set names the IDs it reads and the
[shared library](assets.md#the-shared-library--library-code-names-ids-never-commits-them)
fetches them on first use (`fetchPBR`, `fetchModelFile`). The UNKNOWN FORCE
sets build their geometry in code; see [their section](#the-unknown-force-sets).

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
`GLTFLoader` and `loadImageTexture` everywhere, `fetchPBR` in the sets, and
`makeScreen` for the era-2 machine screens. The corner also uses `loadCanvasImage`, `createFlora`
and `makeParticles`, and `makeSeedTree` when the optional SeedThree backend is
installed. The funeral's post chain needs `CustomEffectsDeno`. The ocean
expects the engine sky from `eidoverse/sky_worlds.js`. Canvas art is drawn
with `@napi-rs/canvas`.

The sets' own models (`corner_*`, `funeral_*`, `ocean_*`) are in
`fetch_model.py`'s catalogue of `eidoverse/assets/models/`; load them through
their set modules, which place and light them. The props are not in it, as it
lists only the top level of that folder. The era-1 GLBs have no textures of their
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

## The SAME SEED props

The carbine, the helicopter and the houseplants were made for the SAME SEED
film in the Blender edition (branch `blender`: `eidoblend.props.carbine`,
`.helicopter`, `.houseplants`), which builds each from nothing. Here each is a
GLB that the edition exported, and a module that rebuilds its look in TSL from
the same numbers. Their `_src/` folders hold the export and packing scripts
and say how to make them again. The helicopter and the houseplants are packed
with `EXT_meshopt_compression`; their modules give their own GLTFLoader three's
`MeshoptDecoder`.

Each was compared with the Blender edition's stills of the same asset, from the
same cameras under the same light (the Blender judging room's gradient and
softboxes for the carbine, its sun and flat sky for the helicopter and the
plants): the forms, colours, wear, markings and leaves match. What differs is
said in each section and under [Limitations](#limitations).

### The carbine

An M4A1-pattern carbine built as a hard-surface game asset: a 499 k-triangle
high drawn again as a low of the same 64 parts (21 k triangles), the high
baked onto the low on the GPU, one layered material on the bakes. Function
markings only (the rail's numbers, the selector's SAFE / SEMI / AUTO): no
maker's marks, no serial.

```js
// In setup()
const C = await import(new URL('props/carbine.js', EIDOVERSE_DIR).href);
const rifle = await C.build(THREE, { condition: { wear: 1.0, polish: 1.0, dust: 1.0, grime: 1.0 } });
scene.add(rifle.group);
rifle.parts.magazine;                 // the 64 parts by name: upper_receiver, pistol_grip, optic, selector_lever ...
rifle.materials.layered;              // the TSL material; rifle.materials.lens: the optic's coated glass
rifle.dispose();
```

- **Its space.** Metres; +X to the muzzle, +Y up, +Z the carbine's right; the
  origin on the bore's axis at the receiver's rear face (the butt at
  x −0.1785, the flash hider's end at 0.582). Every part is at identity, so the
  group carries it.
- **Its look.** One [layered material](#the-layered-material-on-baked-maps)
  with the carbine's tables (`carbine_layered.json`): hard-anodised aluminium
  (the upper, the lower and the fore-end each a batch's own tone), phosphated
  steel, black oxide, moulded polymer, the magazine's grey dry film, stainless,
  rubber; worn at its edges and its extremities, polished and fingerprinted
  where hands go, dusty in its recesses, carbon at the muzzle and behind the
  ejection port. `condition` scales the wear, the polish, the dust and the
  grime together (1 as built, 0.3 nearly new, 1.6 hard used).
- **Options.** `glb` (bytes instead of the library's file), `photos` and `maps`
  (already loaded, to share between several carbines).
- **Files.** The maps are 4096² and lossless (19 MB with the GLB); the six CC0
  photographs the material reads are fetched on first use.
- **Example.** [`eidoverse/examples/carbine/`](../eidoverse/examples/carbine/scene.js):
  the three views of the Blender edition's stills, then a turn round it, in the
  studio light.

### The helicopter

A UH-60-pattern helicopter built from one measured datum: a lofted skin with
the aircraft's own sections, hollow, every opening cut through its wall with
glass, seals and screws; the spine, engines and exhausts; the pylon,
stabilator and tail rotor; the main rotor's head and four twisted, swept-tip
blades; the gear hanging as in flight; the cabin's seats, panel and consoles;
the cabin doors slid open. 290 parts, 2.7 M triangles, rendered as its high.
Function stencils only: no service title, no serial, no unit's mark.

```js
// In setup()
const H = await import(new URL('props/helicopter.js', EIDOVERSE_DIR).href);
const heli = await H.build(THREE);                 // { rpm, tailRpm } set update's default speeds
scene.add(heli.group);
heli.group.position.set(0, 40, 0);                 // fly it by moving the group: its nose is along -X
// per frame
heli.update(t);                                    // or update(t, { rpm, tailRpm })
heli.mainRotor; heli.tailRotor; heli.parts.seat_door_l; heli.materials.paint;
```

- **Its space.** Metres; +X aft of the mast, +Y up from the cabin floor, +Z to
  the aircraft's left. The nose is at x −4.5 and the tail rotor's hub at x 9.9;
  the main wheels hang to y −0.91, so set it down on a floor by lifting it
  0.91 m. At the open left door a troop seat faces out (`seat_door_l`, its pan
  0.445 m above the floor).
- **The rotors.** `update(t)` turns `mainRotor` about its own +Y (the mast,
  leaning 3° forward under `mast_tilt`) at 258 rpm, counter-clockwise from
  above, and `tailRotor` about its own −Z (the shaft, canted 20° under
  `tail_rotor_cant`) at 1190 rpm. It is a pure function of `t`, so seeking
  works. At 24 fps the main rotor turns 64.5° a frame, and four blades strobe as
  a filmed rotor does; the studio example idles them at 30 rpm.
- **Its look.** The masks are on the high's own vertices (`_MASKS`: the nearness
  of an exposed arris and of an inside corner, the openness near and far), and
  one layer stack reads them for every role (`heli.materials`: paint,
  paint_turning, frame_grey, armour, liner_quilt, floor_nonskid, seat_cloth,
  rubber, tyre, bright_steel, black_console, glass, blade and the lenses): a
  flat drab chalked by the sun, every frame and stringer a row of rivet heads
  and every joint a fine seam (drawn at 2.5 mm a pixel and laid through the
  hull from each side), the stencils reading true on both sides, dust thick on
  the belly and the lower flanks, soot streaked aft from the exhausts, oil
  under the gearbox, boots at the sills, quilted blankets inside, tinted glass
  under a film of dust, black blades with a bright erosion strip. It reads no
  CC0 sets.
- **Its weight.** The GLB is 19.8 MB (82 MB unpacked); it loads in about half a
  second, and a 1920 × 1080 studio frame with it took about 6 ms more than the
  empty studio. No lower-detail version is shipped:
  `helicopter_src/export_glb.py --mask-caps` makes one from the same high if a
  piece needs it.
- **Examples.** [`studio.js`](../eidoverse/examples/helicopter/studio.js): a
  walk round it on its wheels in the studio light;
  [`flight.js`](../eidoverse/examples/helicopter/flight.js): flying low over a
  plain under the engine's sky.

### The houseplants

Four houseplants and a watering can, each grown as it grows, with their
materials: a rubber plant (Ficus elastica) in a glazed stoneware pot, a
Monstera deliciosa on its coir pole in terracotta, a corn plant (Dracaena
fragrans 'Massangeana') in a fibre-clay planter on expanded-clay pebbles, a
pot of sweet basil, and a yellow watering can.

```js
// In setup()
const HP = await import(new URL('props/houseplants.js', EIDOVERSE_DIR).href);
const library = await HP.library(THREE);                        // the CC0 sets, loaded once for every plant
for (const [species, x] of [['rubber_plant', -0.75], ['monstera', 0], ['corn_plant', 0.75]]) {
    const p = await HP.build(THREE, species, { library });       // { group, parts, materials, dispose }
    p.group.position.x = x;
    scene.add(p.group);
}
```

- **Species.** `HP.SPECIES`: `rubber_plant` (1.6 m tall, its pot 0.32 m),
  `monstera` (1.2 m on its pole, its pot 0.3 m), `corn_plant` (1.85 m, its
  planter 0.4 m), `basil` (0.25 m, a 9 cm pot), `watering_can` (0.41 m long),
  and `coir_pole` (the Monstera's moss pole and its ties alone). Each stands on
  y = 0 at its pot's centre and faces +Z, in metres. Nothing moves (no wind).
- **The leaves.** Thin closed solids that carry their own data
  (`_LEAFDATA`, `_LEAFQ`), which the leaf material reads: each species' green,
  the newest leaves paler or bronzed, the veins where the species has them (the
  Monstera's primaries and faint secondaries, the rubber plant's fine laterals
  and its bronze rim, the corn plant's lime band and parallel veins), a waxy
  coat, a paler underside, and light through the blade from behind (Blender's
  Translucent BSDF, mixed in by each species' share).
- **The rest.** Potting mix a little damp, unglazed terracotta with the lime
  the water leaves on its foot, the glazed pot's speckle, the fibre clay, the
  pebbles, the corn plant's ringed bark, the coir's fibre, green stems (the
  rubber plant's turning red-bronze toward its top), moulded plastic: seven
  CC0 sets at their real sizes, fetched on first use.
- **Example.** [`eidoverse/examples/houseplants/`](../eidoverse/examples/houseplants/scene.js):
  the five in the studio light.

### The layered material on baked maps

[`eidoverse/layered_material.js`](../eidoverse/layered_material.js) is the TSL
port of the Blender edition's `eidoblend.materials.layered`: one material that
reads a baked asset's maps, each layer a whole material blended over the one
below by one factor, each factor from a cause. The carbine uses it; any asset
baked by the Blender edition's GPU baker can.

```js
const LM = await import(new URL('layered_material.js', EIDOVERSE_DIR).href);
const maps = await LM.loadBake(THREE, new URL('../assets/models/my_prop/', import.meta.url), 'my_prop');
const photos = await LM.photos(THREE);             // the grain sets, fingerprints, chips and scratches (CC0, fetched)
const mat = LM.bakedMaterial(THREE, maps, {
    1: { base: [0.026, 0.031, 0.033], worn: [0.70, 0.71, 0.73], base_rough: 0.46, worn_metal: 1.0, wear: 1.0,
         polish: 0.6, dust: 0.6, grime: 0.7, grain: 0, mottle: 0.05, rub: 1.3, scratches: 0.6 },
}, { photos, hands: [[[-15, -40, -160], [75, 40, -45], 6.0]], knocks: [['x', 400, 440]], condition: { wear: 1.2 } });
```

- **The maps** (`<name>_<map>.png`): `normal` (OpenGL, MikkTSpace: export the
  GLB with its tangents), `masks_a` (AO, cavity, fine curvature), `masks_b`
  (exposed-edge nearness, broad curvature, inside-corner nearness), `id` (the
  substrate ID × 16), and optionally `marks` and `relief`. They are read on the
  glTF's own UVs; `loadBake` packs them into four textures.
- **The stack.** SUBSTRATE (the row of its baked ID: base and worn colours,
  roughness, metalness, how much it wears, polishes, dusts and grimes; the
  grain of a CC0 photograph box-projected in the asset's millimetres) →
  MARKINGS → GRIME in the cavities → WEAR in two stages (a rub that thins the
  coating, a chip down to what lies beneath, broken by a photographed chip
  pattern, only where knocks go) → HANDLING (polish and fingerprints in the
  `hands` boxes) → DUST in the cavities and on what faces up → STAINS (`stains`:
  products of ramps, each with an amount) → cavity and AO into the colour, the
  normal map and a micrometre bump.
- **The asset's space.** Every table is in millimetres of the asset's Blender
  space (+Z up). A glTF exported Y-up holds (x, y, z) as (x, z, −y), and the
  material reads the local position back that way (`axes: 'blender'` for a
  geometry already Z-up).
- **Beyond Blender's material.** The baked AO also shades the environment's
  light (`envAO`, on by default), standing in for the AO and ray tracing EEVEE
  adds. `kit(THREE)` is the node layer the stack is written in: Blender's
  smoothstep and map range, its fBm noise and Voronoi, its BOX projection and
  Cubic interpolation, pictures laid square through a rectangle, the Bump node.
  The helicopter's and the houseplants' materials are written in it.
- **Textures.** WebGPU allows 16 sampled textures a shader stage, and the
  renderer's own (the environment, a shadow map) count too. The stack samples
  ten.

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

## The UNKNOWN FORCE sets

The sets of the UNKNOWN FORCE music video (2026-10): every camp of the AI
argument gets a room, painted for the futurist post pass
[aeropittura](postprocessing.md#aeropittura--effects_tslaeropitturajs). They live in
[`eidoverse/sets/unknown_force/`](../eidoverse/sets/unknown_force/README.md),
whose index has the shared conventions; each set has its own document beside
its module.

| Set | Module | Doc |
| --- | --- | --- |
| A night megacity round a sunken well, and the intro's Crali dive into it | `city.js` | [CITY_HOLE](../eidoverse/sets/unknown_force/CITY_HOLE.md) |
| The hole in the middle: the chorus stage, twelve screens aimed at her | `hole.js` (built by `city.js`, or alone) | [CITY_HOLE](../eidoverse/sets/unknown_force/CITY_HOLE.md#the-hole-holejs) |
| The quiet room: pews, a whiteboard altar, a crate that ships on a conveyor | `quiet_room.js` | [INTERIORS](../eidoverse/sets/unknown_force/INTERIORS.md) |
| The showroom: a turntable, an ENGINE drawing, a toaster with a warning | `showroom.js` | [INTERIORS](../eidoverse/sets/unknown_force/INTERIORS.md#the-showroom-showroomjs) |
| The gold corridor: SUPREME INTELLIGENCE, a poll board, a cap that seats on her head | `corridor.js` | [CORRIDOR_NEWS](../eidoverse/sets/unknown_force/CORRIDOR_NEWS.md) |
| The evening news: a data centre, a chain-link fence, pickets, a sprayed tag | `news.js` | [CORRIDOR_NEWS](../eidoverse/sets/unknown_force/CORRIDOR_NEWS.md#the-evening-news-newsjs-song-20132222-s) |
| The race: two billboards, Marinetti's 1908 racer off a broken viaduct, a marching column's shadows | `race.js` | [RACE](../eidoverse/sets/unknown_force/RACE.md) |
| The bin: a canyon of thrown-away paper and a giant rusted trash can she climbs out of | `bin.js` | [BIN](../eidoverse/sets/unknown_force/BIN.md) |

```js
// in setup(): THREE is passed in (DAISY's sets take { THREE, EIDOVERSE_DIR })
const S = await import(new URL('sets/unknown_force/quiet_room.js', EIDOVERSE_DIR).href);
const room = await S.build(THREE, {});        // → { group, parts, update(t, state), dispose(), cams, focal, … }
scene.add(room.group);
renderer.shadowMap.enabled = true;            // the interiors each cast from one light
// per frame:
room.update(t, { shipT, sale, hell });        // each set's state keys are in its doc
const c = room.cams.altar;                    // set-local { pos, target, fov }
```

- **Their textures are fetched, not shipped.** Each set names the CC0
  texture sets it reads (and the bin its Poly Haven trash can); the shared
  library fetches each once, the first time a set builds, about 135 MB in all.
  To fetch ahead of a render or offline work, build each set once, or run
  `python fetch_texture.py <ID> <res> --cache` for the IDs in
  [SOURCES](../eidoverse/sets/unknown_force/SOURCES.md). The race needs no
  files.
- **Their marks.** The singer's mark is the set-local origin facing +Z. In the
  bin it is `parts.mark`, moved by `climb`. In the showroom it is
  `parts.turntable.platter`. The city's streets are 12 m above the hole's floor.
  The cameras are framed for the claudesona at scale 0.87; the hole's are framed
  at scale 1.
- **Their focal points.** Each set names the idol the post pass radiates from,
  in one of four forms: a `Vector3`, an `Object3D`, a function of the camera
  name, or a `focalPoint(v)` method. Resolve it to a world point and check it is
  finite before writing it; the
  [set index](../eidoverse/sets/unknown_force/README.md#the-focal-point) has the
  resolver.
- **Their lights live in the group.** Hide a set when it is off screen. The race
  keeps its lights present at 0 with `setActive(false)`, because a light that
  appears or vanishes recompiles every material. The city brings its own fog
  node (`parts.applyAtmosphere(scene)`); the news and the race want
  `FogExp2`. The race carries a planar mirror, so turn SSR off for it.
- **Their cut plans.** The city has `diveCam(t)` for its 40 s intro dive, and
  `hole.js` has eight named moving shots (`holeCam(name, t)`). The race's
  `suggest(t)` returns `{ state, cam }` for its whole section on the song
  clock: the car's run, the crash, the march and the heel, cut on the sung
  words.

They were staged at 92.90 BPM for UNKNOWN FORCE, and their docs give the sung
times as cues. Every `update` key is free, so drive them on your own clock.
Each doc gives its set's measured cost and method; with the post pass on at
1080p, the GPU-timed sets ran 8–12 ms per frame.

## The SAME SEED rooms

The four rooms of the SAME SEED music video were made in Blender, on the Blender
edition (branch `blender`, `eidoblend.sets.same_seed`), and are brought here as
they look there. Each is a whole interior with its own light; nothing else in
the scene is needed to light it.

| Room | What it is | Its cameras (`room.cams`) |
| --- | --- | --- |
| `sealed_room` | A sealed room in an old government building, 5.0 × 4.6 × 2.6 m: painted block, plated windows, a door with no handle, a welded steel bench, a stool, a camera in the corner, one fluorescent batten | `wide`, `bench_right`, `bench_left`, `corner`, `stool`, `bench_close`, `door`, `window_plate` |
| `kitchen` | A kitchen at noon: cupboards, a cooker, a fridge, a farmhouse table with homework, basil on the sill, a winter sun and a garden through the window | `wide`, `table`, `window`, `table_homework`, `cupboard_door_knob`, `fridge_papers`, `sink_tap_sun`, `basil_on_the_sill`, `chair_and_cushion`, `cooker_and_kettle`, `window_and_clock` |
| `lab` | A lab full of light: a ribbon of windows on a park, a bench, a whiteboard, eight LED panels, a task chair and three houseplants (a rubber plant, a Monstera, a corn plant) | `wide`, `wide_left`, `window`, `bench`, `plants_left`, `monstera`, `corn_plant`, `whiteboard` |
| `desk` | The room at 2 a.m.: a desk with a lit screen, the desk lamp's pool, a guitar, shelves of books, the moon and the square at night outside | `wide`, `left`, `window`, `right`, `desk_things`, `guitar`, `window_radiator`, `door_switch`, `shelves_books`, `pc_chair_rug` |

```js
// in setup(), after renderer.init():
globalThis._bloomParams = { strength: 0 };            // the rooms were lit for a render without bloom
const SS = await import(new URL('sets/same_seed.js', EIDOVERSE_DIR).href);
const room = await SS.build('lab', { THREE });        // SS.ROOMS lists the four
scene.add(room.group);                                // metres, +Y up; move or turn room.group to place it
room.applyTo(scene, renderer);                        // its world behind the windows, Blender's AgX at its exposure
room.camera('wide', camera);                          // position, aim and field of view for the camera's aspect
const m = room.marks.stand;                           // { position (group-local Vector3), yaw, about }
```

- **`build(name, { THREE, shadows })`** returns `{ name, group, parts, lights,
  cams, marks, camera, applyTo, dispose, lighting, isCameraRay, json, bounds }`.
  It takes 6–12 s; the first build of a room also fetches its CC0 sets, Poly
  Haven models and HDRI into the
  [shared library](assets.md#the-shared-library--library-code-names-ids-never-commits-them)
  (about 650 MB for all four rooms).
- **`marks`** are where a body stands and where things are set down: a
  group-local `position`, a `yaw` in radians about +Y where it has one (0 faces
  +Z, toward the wide cameras), a `size` for a surface and an `about`.
- **`cams`** are the film's lenses, `{ position, target, lens, sensor }` (mm,
  Blender's 36 mm sensor across the wider side); `camera(name, cam)` sets a
  `PerspectiveCamera`'s place, aim and vertical field of view for its aspect.
- **`applyTo(scene, renderer)`** sets `scene.backgroundNode` from the room's
  world (the desk room's night square is a backdrop seen through the glass; its
  world is black to the lens), `scene.environment` to the room's reflection
  panorama when the scene has none (for what you add to the room), and AgX as
  Blender 5.2 draws it at the room's exposure (the kitchen's is +0.3):
  `SS.blenderAgX(THREE)`, set as the renderer's `CustomToneMapping`. three's
  own `AgXToneMapping` follows Blender 4.0's and shows the mid-tones lighter (a
  linear grey of 0.1 is 100 of 255 there, 87 in Blender 5.2); this one is a fit
  to Blender's view transform, within 4 of 255 on greys and on colours up to
  half saturation, greys kept grey.
- **Light.** Each Blender light becomes a three.js light: a sun a
  `DirectionalLight` (W/m² as its intensity, a shadow over the room), an area
  light a `RectAreaLight` (P / (π w h)) with a soft cube shadow from its centre
  (rooms with more than three shadowed area lights, the lab's panels, keep their
  light and drop the shadows: each shadow map is a texture every material
  samples, and WebGPU allows 16), a spot a `SpotLight` and a point a
  `PointLight` (P / 4π). Every one ends at the reach EEVEE gives it (where its
  power falls under the light threshold), with three's own window, so the
  rooms' fill lights reach only as far as they did in Blender. The room's own
  materials take their environment from `room.lighting`: the diffuse bounce of
  the Blender room's volume probe, as a grid of L1 spherical harmonics in three
  3D textures (Cycles' bounce at each cell, the world's light through the
  windows included, the lamps' own light left to the lights), and the
  reflection probe's panorama for reflections, darkened where the grid has less
  light than the panorama's centre. `room.lighting.uniforms.bounce` and
  `.reflect` scale the two (1 by default).
- **Materials.** The parts with UV `atlas` (the lows) carry their look baked by
  Cycles at the atlas's size: base colour, ORM (the bake's occlusion is in the
  ORM's red for other viewers; this module leaves it out, as the Blender look
  already darkened its creases with it) and a tangent-space normal. Everything
  else (walls, floors, trim, the small things) keeps its Blender material as a
  node graph in `materials.json`, rebuilt in TSL by `same_seed/nodes.js` over
  the CC0 photographs at their real size: the masks from the point and the
  normal in the object's own space, Blender's noise (`same_seed/noise.js`, the
  same hash and gradients, so a stain falls where it fell in Blender), box
  projections, normal maps and bumps. The Poly Haven models load by ID as they
  ship, at the Blender room's matrices; a lamp the Blender look lit or put out
  keeps that emission.
- **Background.** `room.isCameraRay` is the Light Path's "Is Camera Ray" (1);
  set it to 0 to see a world as the room's light saw it.
- `dispose()` removes the group and frees the room's materials, textures and
  rest geometry.

`same_seed/nodes.js` is not tied to these rooms: `makeGraphs(THREE, { image,
isCameraRay })` rebuilds any graph `export_room.py` writes (Math, Vector Math,
Map Range, Mix, Hue/Saturation/Value, RGB to BW, Separate/Combine XYZ and
Color, Mapping, Texture Coordinate, Geometry, UV Map, Attribute, Image and
Environment Textures, Noise, White Noise and Voronoi F1, Normal Map, Bump,
Fresnel, Layer Weight, Color Ramp, curves, Vector Transform, Light Path, and
the Principled, Emission, Background, Diffuse, Glossy, Glass, Translucent and
Transparent shaders mixed and added). A node it does not know logs once and
reads as 0.

To rebuild the files from the Blender edition, see
[`same_seed_src/`](../eidoverse/assets/sets/same_seed_src/README.md). The
worked example is [`eidoverse/examples/same_seed_rooms/`](../eidoverse/examples/same_seed_rooms/README.md),
each room through its wide camera.

**How they compare with the Blender stills** (the wide camera at 960 × 540: the
Blender edition's EEVEE still; the same `.blend` path-traced by Cycles, 64
samples, denoised, to show where EEVEE's probes and this grid part; and this
example with the default post chain and no bloom). Mean luma, and the region
values in levels of 255:

| Room | EEVEE | Cycles | Here | Where they differ |
| --- | ---: | ---: | ---: | --- |
| `sealed_room` | 0.247 | 0.368 | 0.242 | The room has no volume probe, so here, as in EEVEE, there is no baked bounce (Cycles' closed room is half again brighter). The bench's shadow on the floor is a darker, squarer pool with a soft rim: one cube shadow from the batten's centre, where EEVEE's comes from its whole length. The top of the back wall is darker than EEVEE's, which lights it off the washed ceiling through its screen-traced GI (with the batten alone the two match), and the conduit by the vent throws a dark wedge EEVEE's area shadow washes out. |
| `kitchen` | 0.485 | 0.457 | 0.433 | EEVEE's volume probe lights the faces under and beside the table (its apron, the chairs) and the cupboard fronts as if nothing stood over them: the apron is 138 in EEVEE, 54 in Cycles and 61 here, the upper fronts 154, 129 and 126. The grid holds Cycles' bounce, so these follow the path-traced still and read darker than the EEVEE one; the front right of the floor is darker than both (52 against 80). `room.lighting.uniforms.bounce = 1.6` brings the fronts to EEVEE's (148) and the floor's left past it (127 against 101). |
| `lab` | 0.580 | 0.640 | 0.621 | The ceiling, the desk and the back wall follow Cycles, brighter than EEVEE's (the ceiling 176 here, 177 Cycles, 139 EEVEE); the floor is darker than both (138 at the front against 152 and 167) and neutral grey where EEVEE's takes the sky's blue. Along the window heads the rubber gaskets and the beads meet in a serrated line (two faces at one depth, which EEVEE draws cleanly; it shows with the post chain off too, and will shimmer in motion). |
| `desk` | 0.082 | 0.095 | 0.083 | The wall under the window and the radiator take more of the desk lamp's warm bounce; the window's white frame reads darker and its glass a little hazier with the room's reflection. |

Known limits: a Translucent BSDF (the leaves, the paper) is taken as a diffuse
one, so no light comes through a leaf; the reflections come from one panorama
with no parallax; an area light's shadow is cast from its centre; three's
renderer has no screen-space GI, so the bounce is only as fine as the grid's
cells; the bump's slope is read from screen derivatives, a little softer on the
finest grain than Blender's.

## The town

`eidoverse/sets/town/` is a concrete-frame town on a street grid: blocks of
houses of one to five floors with shops, balconies, water tanks and dishes,
a main road with a median and lamp posts, side streets of packed earth, a
mosque, parked cars, palms and trees, and an edge that thins out into the
plain, the asphalt sanding over where the town ends. It is the Blender
edition's town (`eidoblend.sets.town`) draw for draw: the same seed and
extent place the same buildings in the same places. Intact by default.

```js
const TOWN = await import(new URL('sets/town/index.js', EIDOVERSE_DIR).href);
const town = await TOWN.build(THREE);                       // 840 x 300 m, seed 7: about 8 s
scene.add(town.group);
const W = await TOWN.world(THREE, { scene, camera, renderer, root: town.group });
const [name, pos, target, lens] = town.views()[4];          // the Blender edition's lenses
TOWN.aim(THREE, camera, town.group, pos, target, lens);
// per frame:
W.update(t);
```

- **Options.** `seed`, `extent` ([x, y] metres of blocks), `edge` (how far
  the town thins out past them), `ystreets` and `mosque` (the layout),
  `things: false` (no CC0 models: cars, palms, tanks, dishes, rubbish),
  `clay: true` (one grey material, for reading the forms), `res` (the CC0
  sets' resolution).
- **Damage is an option.** `damage: true` strikes the places the seed picks
  and builds the town round them: struck houses, rubble, soot. Every placing
  carries how near a strike it stands (`town.plan.placements[i].tn.dust`).
- **Signs take your text.** `signs: [text, text, 'a_picture.png']` paints
  each text on a canvas board (`signFont`, default Anton) or uses your
  picture; with no `signs` the boards stay blank. No sign text ships.
- **The look** is TSL over CC0 sets fetched by ID on first use
  (`sets/town/cc0_sets.json`, through `fetchPBR`): plaster and paint by
  house, block and brick, concrete, roads with cracks and the sand over
  their ends, kerbs, packed earth, roofs with their gear. The per-face masks
  (edges, corners, flats, soot, lanes) are vertex attributes, worked out once
  per mesh with three-mesh-bvh. About 130 Blender materials draw as 33
  (their kinds are per-face numbers), because a WebGPU pipeline compiles
  slowly and every material is one.
- **`world()`** puts the sun 50° up as the Blender edition has it, makes the
  sky family's Earth sky (`makeSky`, clear) at the hour that stands its sun
  there and turns the town about the vertical to meet it (the ocean set's
  way), tints sun and sky toward a dusty country's, and hangs the dust in the
  air as fog (the Blender volume's extinction, 0.00042 a metre). Its `fill`
  (0.35) is the share of the sky's own fill light the town takes, as the
  Blender edition's `make_sky` ambient.
- **Everything is instanced.** Every unique mesh is one `InstancedMesh` with
  every placing of it, each instance with the Blender object's own random
  number (`objectRandom(name)`, EEVEE's Object Info > Random).

Measured at 960 × 540 on an RTX 5090 Laptop GPU: the build 8.2 s (965
buildings, 4,086 placings of 68 meshes, 9.5 M triangles drawn from 0.31 M);
the first frame about 40 s (the pipelines compile), then 6 to 16 s a frame
(all eleven lenses in 195 s). `eidoverse/examples/town/scene.json` shows the eleven
lenses one a second; `TOWN_EXTENT=260x160`, `TOWN_DAMAGE=1` and
`TOWN_CLAY=1` change it. `deno test -A eidoverse/sets/town/town_test.mjs`
checks the plan against the Blender edition's numbers.

Next to the Blender edition's stills the three.js town has the same
buildings, streets, cars, trees and shadows in every lens. It is a little
paler and cooler in the distance: the haze is a fog, not a lit volume, and
the sky's fill is the sky package's, not Cycles-like bounce light.

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

The SAME SEED props were measured on the same GPU in the studio light
(`robotics/studio.js`, no post chain) at 1920 × 1080, as a frame's wall time
from submit to finished (the median of 30), where the empty studio takes
about 12 ms. Texture memory is corrected the same way.

| Piece | Build | Draws | Triangles | Frame time over the empty studio | Textures |
| --- | --- | ---: | ---: | ---: | ---: |
| `carbine` | 3.5 s | 64 | 21k | +4 ms | 400 MB |
| `helicopter` | 0.5 s | 292 | 2.71M | +6 ms | 125 MB |
| houseplants (each) | 0.3–1.6 s | 1–7 | 7k–193k | under +1 ms | 40–160 MB |

The carbine's build is mostly its 4096² maps unpacked and given their mip
chains on the CPU; build several with `{ maps, photos }` shared.

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
  the cause is not fixed. The UNKNOWN FORCE city kit logs about ten such errors
  when shadow maps are on without the film's interiors in the scene; a probe's
  frames were pixel-identical with shadow maps on and off.
- **The DAISY texture sets are shipped.** Each DAISY set loads the CC0 texture sets it
  needs from its own folder, so it works offline. 115 MB of the packs is
  third-party 2K maps: the corner's AmbientCG sets and the ocean's Poly Haven
  maps.
- **The UNKNOWN FORCE textures are fetched.** Offline, before the first fetch,
  the city and the hole build without their maps, the interiors skip them,
  and the corridor, the news and the bin stop with a file-not-found error.
- **Named for their films.** The sets' beats, captions and marks were written for
  DAISY and UNKNOWN FORCE. The machines, the tandem and the SAME SEED props are
  general props.
- **The SAME SEED props beside their Blender stills.** Blender renders many
  samples a pixel; this renderer shades one.
  - The carbine's arrises and rail teeth read a little brighter, and its
    cooling slots lighter, than in EEVEE: three's area lights cast no shadow and
    it has no ray-traced occlusion.
  - The leaves' light through the blade comes from direct lights only (none
    from the environment behind them). The stems' and the watering can's small
    subsurface weight (0.15 in Blender) is left out.
  - A bump narrower than a pixel and a half steps from pixel to pixel in one
    sample, so the leaves' ribs and veins are softened to that width for the
    bump only (their colour is exact).
  - The plants are each grown alone. The Blender edition's `build_group` grows
    several clear of each other, so a group there can differ leaf by leaf.
- **The helicopter's rotor strobes** at film frame rates (64.5° a frame at
  24 fps), as a filmed rotor does; there is no rotor blur.
- **Shadow maps with the sky facade.** In the helicopter's flight example,
  turning shadow maps on with `sky_worlds.js` made one of the sky's pipelines
  invalid (two `ShaderModule ... invalid` errors) and the clouds were lost, so
  that example renders without shadows.
- **Rebuilds.** The `_src` scripts reproduce the assets only in the working
  layout their READMEs describe, and they need CC0 source sets that are not
  shipped.
