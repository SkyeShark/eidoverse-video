# The race: verses 3 and 4 (sung 142.48 to 162.76 s)

[Props and sets guide](../../../docs/props-and-sets.md#the-unknown-force-sets) · [Set index](README.md) · [Sources and licences](SOURCES.md)

`race.js` builds the set for "A hundred million says I'm a race to win … Last time that poem ended in black shirts
and a heel". Everything is built at setup (no external assets), deterministic in `(t, state)`, NodeMaterials and TSL
only.

- An elevated wet highway at night threading between dark Sant'Elia-stepped towers. It has sodium lamps, light cones
  in the rain, slanted rain, wet asphalt with lane paint, wheel-rut puddles and rain rings, and a real planar
  reflection of the whole set.
- Two giant billboards face each other across the road: **`$100,000,000` in gold** (worship) and **`$20,000,000` in red**
  (fear). Both show the SAME machine-god face: one canvas drawing function, a monumental faceted face of circuit
  traces with a halo of Balla sun rays, data pulses flowing outward and live aperture irises that glance at the other
  screen. The red one tears in horizontal bands; the gold one breathes.
- **Marinetti's car**: a 1908-pattern Italian GP racer, modelled here.
  - Body: rosso enamel with clearcoat, a louvred bonnet with leather straps, a brass-shelled honeycomb radiator
    painted with a white 7, a four-header outside exhaust.
  - Running gear: chain drive with moving links, wooden artillery wheels on pale period tyres with shutter-smeared
    spokes, a bolster tank with brass bands and a spare.
  - Cockpit and fittings: buttoned leather buckets, a raked wooden wheel (right-hand drive), outside levers, a bulb
    horn and two brass acetylene headlamps.
  - Two cosplayers: the driver and the riding mechanic in dusters, leather helmets and brass goggles, with white
    silk scarves over their faces and scarf tails streaming.
- **The crash**: the right carriageway is closed for bridge works. The car hits a drum in the taper, smashes the
  sawhorse barricades and leaves the broken end of the deck at 22 m/s. Its nose drops, digs into the factory drain
  6 m below, and the car goes over onto its back, wheels in the air, with a mud crown, a slam splash, ring waves
  and steam.
- **Black shirts**: a low roadworks floodlight throws the shadows of a marching column (lockstep, peaked caps,
  breeches and boots, rifles and blank banners, no symbols) across the blank board-marked wall of a tower. There
  are no bodies: the shadows are projected from an absent column in lane 3.
- **The heel**: a knee-high jackboot comes down on the 1909 manifesto (the 1914 Italian text, public domain) lying
  in a puddle. Droplets and rings follow, and a heel print appears on the page.

Licence note: [SOURCES](SOURCES.md#the-race) (the set loads no files).

## Use

```js
const R = await import(new URL('sets/unknown_force/race.js', EIDOVERSE_DIR).href);
const race = await R.build(THREE, { /* opts */ });
scene.add(race.group);                     // park it anywhere: everything reads set-local coordinates
// per frame (before the render; camAt reads the car's pose after update):
race.update(t, state);
const cam = race.camAt(name, t, state) || race.cams[name];   // { pos, target, fov, roll? }, set-local
const f = race.focal(name);                // set-local point for aeropittura's `focal` (the shot's idol)
// outside the section:
race.setActive(false);                     // hides every mesh, keeps the lights present at 0 (no recompiles)
```

`R.suggest(t)` returns `{ state, cam }`: the working cut on the song clock that the film used (below). Its state carries
`carT`, never `carS`: `update()` prefers `carS`, so a conductor overriding `carT` (as the break-2 replay does) would
otherwise be ignored. In the break-2 replay, either keep `shadows` and put any caption plate in the lower third
or at the top (the column fills the middle of that frame), or use `shadowsWide`.
`R.CUES` holds the film's sung word times. `R.LAYOUT` holds the set's dimensions.

### opts

| key | default | |
|---|---|---|
| `reflect` | `true` | the planar reflection of the wet road (one extra half-resolution scene pass while the road is on screen) |
| `reflectScale` | `0.5` | its resolution |
| `sky` | `true` | the set's own night dome (2400 m, no fog). Hide it (`parts.sky.visible = false`) if the film has one global sky. |
| `towers` | `true` | the tower backdrop |
| `rain`, `rainCount` | `true`, `5200` | the falling rain |
| `lampI` | `140` | the analytic sodium lamps' intensity |

## Coordinates

Metres, +Y up, set-local. **The deck surface is y = 0.** The singer's mark is the origin, on the right shoulder of the
+Z carriageway, facing +Z (down the road toward the works; the billboards are behind her).

| what | where |
|---|---|
| deck | x −2.2 to 20.2; the median at x 9.6; lanes at x 3.6 and 7.2 (+Z traffic) and 11.85 and 15.45 |
| ground under the viaduct | y −6 |
| the gap | the right half (x < 9) is missing from z 92 (jagged broken end, deck 1.4 m thick) to z 140; the left half bridges on |
| the factory drain | runs along X, banks z 108 to 130, bed z 113 to 125 at y −9.6, muddy water at y −9.05; the factory sheds and stacks behind it |
| billboard A, `$100,000,000`, gold | centre (33.5, 16, −64), screen 24 × 16 m, yawed −0.96 rad (faces −X and +Z) |
| billboard B, `$20,000,000`, red | centre (−14.5, 16, −64), yawed +0.96 rad |
| the roadworks | drum taper (−1.3, 28) to (8.7, 58); arrow board (0.2, 63.5); barricades across z 67; light-tower trailers at z 86; a tower crane at (−11.5, 101) |
| the shadow wall | a blank face at x −22, z −6 to 76, up to y 66; the floodlight at (18.6, 0.12, 40); the column's plane at x 13.4 |
| the heel's puddle | (−0.55, 0, 9.6); the page beside it |
| the car's path | lane 1 from z −300, drifting right through the works to the broken edge (390.45 m); `carT` 1 puts the front wheels at the edge |

## `update(t, state)`: state keys

All optional.

| key | range, default | what it drives |
|---|---|---|
| `carT` | 0..1, 0 | the car along its path (0: z −300; 0.776: beside the singer; 1: the broken edge) |
| `carS` | metres, — | the same in metres (wins over `carT`); 390.45 m long |
| `carV` | m/s, 22 while on the path | the speed the wheels' smear, the chain and the scarves use (the car's position comes from `carS` / `carT`) |
| `crash` | 0..1, 0 | the crash, 3 s from the edge at 22 m/s (1.31 s fall, nose in at 0.437, over onto its back by 0.65, settled by 0.9). It overrides `carT`. Splash, rings and steam follow automatically. |
| `car` | bool, true | `false` hides the car (and its beam) |
| `headlamps` | 0..1, 1 | the acetylene lamps (they drown on their own in the crash) |
| `billA`, `billB` | 0..1, 1 | each screen's power |
| `billboards` | 0..1, 1 | both screens' power |
| `gaze` | −1..1, 0 | the irises glance toward the other screen |
| `march` | 0..1, 0 | the floodlight and the marching shadows (the flood keeps a faint glow at 0) |
| `marchT` | seconds, `t` | the march's own clock (lockstep, 1 cycle per second) |
| `heel` | 0..1, 0 | the stamp (0 hidden; 0 to 0.45 descends; it hovers; the strike at **0.68**; the toe slaps down by 0.74; planted). Map it so 0.68 lands on the word: `(t − (162.42 − 0.68·2.2)) / 2.2`. |
| `rain` | 0..1, 1 | the falling rain and the rings in the puddles |
| `wet` | 0..1, 1 | the wetness of the road, paint and leather |
| `lamps` | 0..1, 1 | the sodium lamps (analytic field, lenses, cones, the singer's spot) |
| `backRim` | 0..1, 1 | the warm back rim on the singer |

## `parts`

| part | |
|---|---|
| `billboards.a`, `billboards.b` | `{ group, screen, material, texture, amount, mode ('worship' / 'fear'), tint }`. Screens are `MeshBasicNodeMaterial` on canvas textures (channels: R traces, G phase, B fills and the amount). |
| `car` | the car's `Group` (its pose comes from `update`) |
| `riders` | the two cosplayers (a child of the car body) |
| `carRig` | `{ group, body, wheels[{pivot, spin}], mats, path, length, crashPose(tc, start, yaw), CR, beam }` |
| `road`, `reflector` | the wet deck (one mesh) and its `ReflectorNode` |
| `lamps` | `{ poles, lenses, cones, heads }` |
| `towers` | `{ towers, neon }` (one merged mesh each) |
| `works` | `{ drums, steel, lamps, arrow, debris }` |
| `march` | `{ texture, plane, flood }` (the walk-cycle atlas) |
| `heel` | `{ root, pivot, page, dur, strike }` |
| `water`, `splash`, `rain`, `sky`, `ground` | the drain's water, the sprite FX, the rain, the dome, the ground |
| `lights` | `{ key, glowA, glowB, rim, backRim, neonFill, hemi, group }`. See Lighting below. |

## Cameras

`cams` (static, set-local) and `camAt(name, t, state)` (moving; returns `null` when it has nothing, so fall back to
`cams[name]`). `roll` is radians around the view axis (Dutch angles: Crali's tilted city).

| name | shot |
|---|---|
| `singer` | MS of her on the shoulder, the red billboard over her head, the road and the gold one behind |
| `billA`, `billB` | each screen near-frontal from a drone height, big enough that the amount survives the painting |
| `billboards` | low on the road between the two screens: the two faces confront each other |
| `carPass` | low on the shoulder looking up the road: the car comes out between the billboards and tears past |
| `carTrack` | (camAt) tracking alongside in profile: the riders, the scarves, the smeared spokes, the city and the singer streaming past behind |
| `carChase` | (camAt) behind and left of the car through the works: drums, flashers, the arrow board, the barricades flying |
| `crash` | a wide side view of the whole trajectory, the broken deck to the drain |
| `crashLow` | (camAt) low on the drain's near bank, panning with the car as it comes over, dives and flips |
| `shadows` | across the road at the blank wall: the march |
| `shadowsWide` | low in lane 1, level: the column across the upper half, the wet road and the barrier neon below (room for a caption) |
| `heel` | at puddle height: the boot against the dark, the singer and both screens mirrored behind it |
| `heelTop` | an overhead insert: the heel on "Noi vogliamo glorificare la guerra" |
| `carSide`, `carFront`, `carRear` | (camAt) craft views of the car |

## The suggested cut (`suggest(t)`, sung times)

| from | cam | line | events |
|---|---|---|---|
| 142.1 | `billA` | "A hundred million says I'm a race to win" | gold powers on at 142.1 |
| 144.3 | `billB` | "Twenty million says I'm a risk to prevent" | red powers on at 144.0 |
| 147.1 | `billboards` | "The doomer and the zealot dream the same machine god" | the irises glance across from 148.6 |
| 149.8 | `singer` | "They only disagree on how the story ends" | |
| 152.2 | `carPass` | "Down the timeline they're cosplaying Marinetti" | the car comes out between the billboards (22 m/s) |
| 154.9 | `carTrack` | "Beauty only in the struggle, speed and steel" | it passes the singer at about 155.3 |
| 156.2 | `carChase` | "They wrote a manifesto" | the drum at 157.3, the barricades on "make the unknown bow" (158.4) |
| 159.3 | `crashLow` | "make the unknown bow", "Last time that poem ended in" | off the edge at 159.44; nose in at 160.75 ("poem"); on its back at 161.39 |
| 161.40 | `shadows` | "black shirts and" | the march ramps in from 160.66 and is fully on at 161.32 |
| 162.15 | `heel` | "a heel" | the boot hovers; the strike lands at 162.42. `heel` is 0 outside this shot. |

Look: `argue` reads the amounts; at `storm` the amounts survive only in `billA` / `billB` (Impact digits in each
screen's own saturated hue: the painting keeps saturated light and smears white). Give the painting each shot's idol
with `focal(name)`.

## Lighting

Few real lights, always present (a light that appears or vanishes recompiles every material):

| light | |
|---|---|
| `key` | sodium spot over her mark |
| `glowA`, `glowB` | the screens' glow, as point lights |
| `rim` | cool directional from up the road |
| `backRim` | a warm spot behind her mark, the screens' red-gold on the black tuta's edges |
| `neonFill` | the barrier's cyan tube beside her |
| `hemi` | a dim sky fill |
| `parts.carRig.beam` | the headlamp beam: a spot that `update` carries to the car's nose |

`setActive(false)` zeroes all of them. They light anything else in the scene too (with distance cut-offs), so park
the set with `setActive(false)` outside its section.

Everything else is lit **analytically in the set's own materials**:

- the two staggered rows of sodium lamps (34 m apart, occluded by the deck for anything below it);
- the bridge works' LED floods and the heel's close key;
- the march's floodlight and its projected shadows;
- lamp glints on the car's paint and brass.

Every lit material reflects a procedural night-city environment (a Uint8 equirect), never the film's daylight.

Renderer settings for this set:

- `_ssrParams = { enabled: false }`. The set has its own mirror; SSR would double it.
- AO off, or a small radius.
- Bloom `{ strength: 0.55, radius: 0.5, threshold: 0.7 }` (`globalThis._bloomParams`).
- The film used `scene.fog = new THREE.FogExp2(0x0c0f16, 0.0062)`.

## Performance

RTX 5090 Laptop GPU, 1920×1080. Throughput over 40 frames submitted back to back. The full pipeline is scene +
mirror pass + aeropittura `storm` + bloom, with the claudesona in the tuta (`claude_suit_wardrobe.vrm` + `claudesona_wardrobe.js`, the `tuta` preset):

| shot | full pipeline | scene pass alone |
|---|---|---|
| `crashLow` | 7.8 ms | 1.9 ms |
| `shadows` | 10.6 ms | 3.5 ms |
| `billboards` | 10.9 ms | 4.3 ms |
| `carTrack` | 10.9 ms | 3.1 ms |
| `heel` | 12.1 ms | 3.9 ms |
| `singer` | 12.1 ms | 6.6 ms |

Every shot is inside the 16.6 ms budget. Runs vary about ±30% on this laptop GPU (power states): the same shots
measured 4.8 to 7 ms before the outfit and the two rim lights.

- **Where the time goes.** The singer's wardrobe materials render twice (in the mirror too). If a shot needs the
  headroom, lower `reflectScale` (0.5 now) first.
- **Load.** About 95 to 190 draw calls per frame (reflection included) and 85k to 540k triangles. Build time is
  about 0.35 s.

Textures:

| texture | size |
|---|---|
| two billboard canvases | 1024 × 683 |
| manifesto page | 768 × 1086 |
| march atlas | 1024 × 512 |
| noise atlas | 256² |
| environment | 512 × 256 |
| radiator number | 256² |

## three r184 gotchas found here (worth archiving)

1. **`ReflectorNode`'s `.sample()` / `.level()` clones read an empty target.** A material graph that holds only
   clones never schedules the reflection render, and the mirror stays black. Use the reflector node itself: set its
   `uvNode` (distortion, streak jitter) and sample it once.
2. **A material whose `mrtNode` has no colour output** (the usual `mrt({ normal: vec4(0), metalrough: vec4(0) })`
   that keeps transparent quads out of the G-buffer) **compiles to an empty `OutputType`** in any pass rendered with
   the renderer's MRT off, such as a reflector's pass. The result is "ShaderModule ... is invalid" and the object is
   missing from the reflection. The fix here: opaque emissive materials write their normals (no `mrtNode`), and the
   transparent effects are hidden during the reflection render by wrapping the reflector base node's `updateBefore`.
3. **`MeshPhysicalNodeMaterial.specularIntensityNode` is ignored** (`setupSpecular` reads the plain
   `specularIntensity` property), and **direct specular hard-codes `f90: 1`**. Even zero-F0 surfaces get a full
   Fresnel spike from real lights at grazing angles, so a mirror-smooth wet road prints every headlamp and point
   light as a blown star that bloom turns into glare. The road here keeps PBR roughness 1 for real lights (a faint
   sheen); its wetness lives in the planar reflection.

## Limits and notes

- **Fonts.** The amounts are in **Impact** (a Windows system face; fallbacks are Arial Black, then the engine's
  Rajdhani). The radiator number and the manifesto page use Georgia (Windows; fallback serif).
- **The riders** are stylised figures (lofted coats, helmet, goggles, scarves), not rigged characters. They tip over
  with the car and end up under it in the water.
- **The crash** is keyframed rigid-body motion with no physics. The debris (one drum, one barricade) is ballistic
  with a skid.
- **The march's shadows** fall only on the towers' material inside the floodlight's cone. The road and the barriers
  don't receive them; the column has no bodies, by design.
- **The heel droplets** are sprites. The page doesn't deform on the strike: a mud print appears and the page
  darkens where it is wet.
- **Checking**: the film's probe harness is not part of the kit; see the
  [props and sets guide](../../../docs/props-and-sets.md#verify).
