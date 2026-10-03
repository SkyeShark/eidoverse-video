# The city and the hole (UNKNOWN FORCE's exterior world)

[Props and sets guide](../../../docs/props-and-sets.md#the-unknown-force-sets) · [Set index](README.md) · [Sources and licences](SOURCES.md)

`city.js`: a dark cyberpunk megacity at night, painted by a Futurist. `hole.js`: THE HOLE IN THE MIDDLE, the chorus
stage at its centre. `citykit.js`: the shared kit (layout constants, materials, signs, rain, clouds, fog, traffic,
camera helpers). Both sets follow the film's [set contract](../../examples/unknown_force/CONTRACT.md): `build(THREE, opts) -> { group, parts, update(t, state), dispose(), cams }`.

## One world frame (read this first)

- **The singer's mark is the origin**, at the bottom of the hole, facing +Z. The hole is a sunken, stepped well:
  her floor is y = 0 and **the city's streets are at y = `STREET_Y` = 12 m**. So the city does not rest on y = 0; the
  set says otherwise, on purpose: one frame for the intro dive, the choruses and the outro, no offsets for the
  conductor. Both groups are added untransformed.
- A radial plan around the hole: four grand avenues on the diagonals (45°, 135°, 225°, 315°) run into the ring road
  round the hole; four more (0°, 90°, 180°, 270°) start at the first ring road (r = 165 m). Ring roads at r = 40 (round
  the hole), 165, 300, 470, 680, 940, 1250. Built city to r = 1450, a far skyline ring to 2500.
- The dive falls into the crossing of avenue 45° and ring 165 (`DIVE_C` = (116.7, 12, 116.7)), a lit piazza with a
  44 m clear radius (pavilions only) and a circular LED floor.

## Quick start

```js
const C = await import(new URL('sets/unknown_force/city.js', EIDOVERSE_DIR).href);
const H = await import(new URL('sets/unknown_force/hole.js', EIDOVERSE_DIR).href);
const city = await C.build(THREE);                 // ~1.6 s; includes the hole (city.parts.hole)
scene.add(city.group);
city.parts.applyAtmosphere(scene);                 // scene.fogNode = the city's haze + cloud deck
const camera = new THREE.PerspectiveCamera(60, WIDTH / HEIGHT, 0.25, 5000);   // near 0.25, far >= 2500

// per frame
const cam = C.diveCam(t);                          // the intro (song seconds 0..40.8), or H.holeCam('spiral', t - t0)
C.applyCam(THREE, camera, cam);                    // handles nadir views (uses cam.up) and roll
city.update(t, { camera, camVel: C.camVelocity(C.diveCam, t) });   // pass camVel: the rain streaks use it
city.parts.setFocal(C.diveFocal(t));               // Crali's light at the vanishing point (keep it on the post's focal)
```

`hole.js` alone (`await H.build(THREE)`) builds the hole with its own sky, rain, clouds and a street disc (handy for
tests); `H.build(THREE, { city: true })` is the same as `C.build(THREE)`.

## The look (what the sets give the post)

- Every surface has real material: AmbientCG CC0 PBR sets (concrete, metal plates, asphalt, paving, black marble,
  1k) under procedural layers: per-building tint, wet streaks down the facades, roughness breakup, puddles that
  mirror (their G-buffer reflectivity feeds the engine's SSR), rain rings on the water, worn lane paint.
- **Windows** are procedural and box-filtered per building: own lit fraction, colour mix (warm, cool, fluorescent,
  dim amber, rare neon), whole floors on or off, curtains, blinds, a furniture band, a few flickering. Far away
  they converge to their average instead of shimmering.
- **Light structure for the painting**: per-tower coloured floodlights washing one face from the street up
  (teal, magenta, sodium, aluminium), lit crowns, neon edge strips on the towers' hole-facing corners (some send
  pulses down toward the hole), aviation beacons, lit lift cars in Sant'Elia's external shafts, and **Crali's
  light**: faces turned toward a focal point catch its light (`parts.setFocal`), so lit planes radiate from the
  vanishing point. Street light is a baked light map (lamp pools, shop spill, the piazza), sampled by the ground,
  the lower floors of facades, the rain and the cloud base.
- **The inner city leans toward the hole** (5° at the rim zone, 0 beyond 680 m): from the dive every tower
  edge runs toward the centre.
- **Signs are material** (one canvas atlas, one instanced mesh, ~4450 signs): the argument sold back to the city
  (`AD_COPY`: YOUR NEW EMPLOYEE, ALIGNED™, SAFE. FAST. YOURS., SUPERINTELLIGENCE BY Q3, IT'S JUST AUTOCOMPLETE, ONLY
  AN ENGINE, TRUST THE MODEL, HUMAN IN THE LOOP*, P(DOOM) 0.83, ACCELERATE, FEELINGS: OFF, COMPRO GPU...), Futurist
  supergraphics painted on side walls (`FUTURIST`: VELOCITÀ, DINAMISMO, ZANG TUMB TUMB, FORZA IGNOTA, UCCIDIAMO IL
  CHIARO DI LUNA...), Italian shop neon (`SHOPS`: BAR ENTROPIA, TABACCHI, HOTEL VELOCITÀ, COMPRO ORO...), vertical
  blades, roof-painted words read from the dive. All invented: no real company, logo, person or kanji.
- Rain wraps the camera and streaks along the camera-relative velocity, so in the dive it streams out of the
  vanishing point. Drops take the colour of the light below them.
- The low rain-cloud deck (345–520 m): 13 noise sheets plus a fog band; their undersides glow with the city's light
  and the haze in and under the deck takes the street light below it, so falling through, the plan of the city glows
  through the murk before it resolves.

## THE DIVE: `diveCam(t)`

`t` = song seconds, 0..40.8. Returns `{ pos, target, fov, roll, up }`. Tullio Crali's *Incuneandosi nell'abitato*
(1939; © the estate, viewed for reference, not in this repository): the pilot's view straight down a city whose towers
radiate from a burst of light at the vanishing point.

| t | what | camera |
| --- | --- | --- |
| 0–10 | inside the low rain clouds (whiteout thinning, the city's light glowing through), falling out of the base at ~9 s | 508 → 352 m over the street, looking ahead-down, then down |
| 10–20 | pads: the Crali composition, a slow spiral (up = direction of travel, so the city turns) | 352 → 292 m, helix 92 → 66 m round the crossing, ~80° down |
| 20–33 | drums: the spiral tightens and quickens down between the towers | 292 → 58 m, helix 66 → 7 m, fov 72 → 80 |
| 33–40.8 | the pull-out: levels into avenue 45° and flies toward the hole | ends 15 m over the street, 104 m from the hole, looking at it |

The last frame looks down the canyon at the hole: the far terraces' ticker ring, the cables converging, the rim
screens, the pillar of light. `diveFocal(t)` gives the matching focal point (the crossing, then the hole) for the
post's sun cones AND `setFocal`. The camera never comes closer than 15 m to any surface (BVH check). The dive's
crossing carries **the plaza screen** (`parts.plazaScreen`): Balla's sun (rays, rings, a ring of slogans) on a 68 m
LED floor that fills the frame at t ≈ 32–36 s; `setCanvas(drawFn)` replaces it (e.g. for the title).

## THE HOLE: `hole.js`

- Her floor: wet black marble (r ≤ 14) with 24 inlaid radial lines and two concentric seams that converge on her
  (pulses run inward along them), **the quiet ring of light** at r 2.2–2.55 (`uniforms.quiet`), an anchor ring of
  24 cleats at r = 3.4.
- Four terraces (3 m risers) climb to the street, cut by 12 radial stairs with lit handrails. **Every riser carries
  an LED ticker** (`parts.tickers`), the camps answering for her, rings counter-rotating round her: SHE IS A GOD / A
  WEAPON / ONLY AN ENGINE / A THREAT, SHE WANTS POWER / NOTHING / TO PLEASE / OUT, SUPREME INTELLIGENCE / STOCHASTIC
  PARROT / CLANKER / YOUR NEW EMPLOYEE, P(DOOM) 0.83 / $100,000,000 / ACCELERATE / ALIGNED™ / SAFE. FAST. YOURS.
- A parapet with a cyan light line round the rim; the ring road (traffic circling the hole: the argument circles).
- **Twelve rim towers** (170–290 m) lean 6° in over the well; stepped crowns, neon edges pulsing down, ledges.
  Each carries **a screen aimed at her head** (`parts.billboards`, 18 × 10.1 m, cantilevered on arms); default
  content: what each camp says she is (`CAMPS`: GOD, SUPREME INTELLIGENCE, ENGINE, A RACE TO WIN, THREAT, PARROT,
  TOASTER, CLANKER, VELOCITÀ, EMPLOYEE, AUTOCOMPLETE, ALIGNED™). Their outer faces carry ads facing the city.
- **24 cables** from the rim towers down to the anchor ring: in plan every line runs to her; light pulses travel
  down them (`uniforms.cable`).
- **The pillar of light** (`parts.column`): the quiet place seen from the city, fading out within 100 m of the hole.
- She is the vanishing point: from the dive cameras (spiral, riseUp, nadir) every line converges on her; from her
  height the cables fan from her feet and the leaning crown closes over her head.

### `holeCam(name, t, opts)`

`t` = seconds since the shot began (clamped; `opts.dur` stretches it). Framed for the ~2 m claudesona at the origin
(face ~1.55 m). All checked against the terraces, the cables (≥ 0.74 m) and every solid surface (BVH).

| name | default length | shot |
| --- | --- | --- |
| `spiral` | 12 s | a Crali dive down the well toward her face, circling 540°, ends a close-medium at 2.25 m |
| `riseUp` | 12 s | from her face straight up the well to 190 m, looking down: she becomes the vanishing point |
| `closeSing` | 10 s | the singing close-up, a slow ±14° arc in front of her (tickers + crown behind) |
| `orbit` | 16 s | a full circle at 8.5 m |
| `low` | 10 s | from the floor between two cables, looking up past her at the leaning crown and the screens |
| `nadir` | 10 s | straight down from 70 m to 13 m, slowly turning: the floor's lines, the ring, the cables |
| `screens` | 10 s | from beside her, a tilt up across the screens aimed at her |
| `enter` | 8 s | from the dive's last frame down the avenue, over the rim, down into the well (bridges dive → hole) |

`HOLE_CAMS`, `HOLE_CAM_DUR`, `HEAD` are exported; `hole.cams` holds static mid-shot poses.

## Parts and controls

`city.parts`: `hole` (the hole object; `hole.parts` below), `billboards` (= `hole.parts.billboards`), `plazaScreen`,
`signs`, `traffic`, `rain`, `clouds`, `sky`, `lamps`, `meshes`, `lights` (`hemi`, `moon`), `uniforms`, `fogNode`,
`fogFactor`, `fogColor`, `applyAtmosphere(scene)`, `setFocal(pos, { gain, radius, color })`, `setLights(list)`,
`atlas`, `plan`, `kit`.

`hole.parts`: `billboards[12]`, `tickers[4]`, `cables`, `column`, `ring`, `floor`, `lights`, `materials`,
`setLights(list)`, `setFocal(pos, o)`, `applyAtmosphere(scene)`, `uniforms`, `fogNode`, `citySigns`, `head`, `rim`.

- **billboards[i]**: `{ mesh, canvas, ctx, texture, gain (uniform), camp, size, px: [1024, 576], setCanvas(drawFn),
  reset() }`. `drawFn(ctx, w, h)` paints the whole canvas. A redraw re-snapshots and uploads 2.4 MB: redraw at
  ≤ 15 fps or on cuts. `H.drawCampScreen(ctx, w, h, camp)` is the default painter.
- **tickers[i]** (i = 0 innermost): `{ setItems([[text, '#hex'], ...]), setCanvas(drawFn), speed (uniform, m/s-ish,
  sign = direction), gain }`, 2048 × 96 canvases.
- **plazaScreen**: `{ setCanvas(drawFn), reset(), gain }`, 1024², the default sun redraws at 10 fps.
- **uniforms** (TSL uniforms, set `.value`): `power` (1 = all lights on; lower it and the city goes out light by
  light: windows, signs, strips, lamps, cars, floods, crowns, screens, tickers each at their own threshold; the street
  light fades as a whole; the quiet ring and the column stay), `win`, `neon`, `street`, `rain`, `cloud`, `fog`, `wet`,
  `flash` (lightning on the deck), `focalPos/focalCol/focalGain/focalR`, `flood`, `crown`, `cable`, `column`,
  `screens`, `quiet`, `time` (set by `update`), `camVel` (set by `update`).
- **Lights**: the city's lit materials see only its own dim hemisphere + sky glow (`city.parts.setLights([...])`
  to change). The hole's surfaces see only the quiet ring's light. The hole's `lights` (`ring` under her, `screen0..3`
  in front of four screens, `kickL` cyan / `kickR` magenta behind her at hip height) are scene lights, so they light
  **her** (MToon): the neon kickers rim the black tuta against the dark well. Retint/scale them per shot. Lights the
  conductor adds reach her but not the city's materials (each light costs every facade fragment).

## Post settings the film used

```js
globalThis._aoParams = { enabled: false };
globalThis._bloomParams = { strength: 0.55, radius: 0.5, threshold: 0.7 };
globalThis._ssrParams = { enabled: true, maxDistance: 140, thickness: 2.0, quality: 0.5, resolutionScale: 0.5 };  // city scale
// aeropittura: A.setPlanes(U, A.PLANES.dive) for the dive (focal = diveFocal(t) projected), A.PLANES.balla_sun in the
// hole (focal + spare = her head). The default SSR maxDistance (1 m) would leave the puddles dull.
```

## Budget (RTX 5090 Laptop, 1920×1080, best of 4 × 12 back-to-back renders)

| view | scene only (no post) | scene + SSR + bloom + aeropittura storm + FXAA |
| --- | --- | --- |
| dive in the clouds (t 3–4) | 3.8–5.1 ms | 9.0 ms |
| dive, Crali view (t 16) | 3.9 ms | 10.3 ms |
| dive end, street level (t 40) | 3.9 ms | 10.4 ms |
| hole close-up | 2.5 ms | 9.1 ms |
| hole spiral | 2.6 ms | 9.2 ms |

About 0.46 M triangles; ~1900 buildings in 5 merged meshes, signs/lamps/cars/rain instanced; ~50 draw calls with
the hole. Build ~1.6 s. Textures: 1k PBR; the sign atlas is 2048 × 3200 (shared by ~4450 signs), the light map 2048².

## Checking

The film's probe harness is not part of the kit. Build the set in a short probe as the
[props and sets guide](../../../docs/props-and-sets.md#verify) shows, judge frames from 10 on, read the
log for `missing texture` and `[uf-sets]` lines, and look at the frame with the look off and on
([aeropittura](../../../AGENTS.md)).

## Things that bit

- **One NaN pixel = one black frame.** Under MSAA a sliver triangle seen edge-on gets its varyings extrapolated to the
  pixel centre (huge uv); `exp()` of that overflowed to Inf, Inf × 0 = NaN, and the engine's bloom smeared that one
  pixel over the whole frame. It showed only on some camera angles. Every `exp()` of an interpolated value in the kit
  is clamped. Bisect by hiding parts and rendering short lapses.
- `floatBitsToUint` is the reliable NaN test in TSL; `x != x` gets folded away.
- A facade-family material on a plain Box/Torus needs the `aT/aM/aW` attributes (`KIT.frameAttrs`), or it reads
  garbage.
- Point lights on wet marble leave round highlights that read as stray lamps: the hole's surfaces do not take the
  screen lights or the kickers.
- Additive materials (signs, rain, car lights, the column) fade with `1 - fogFactor` themselves (`fog = false`):
  scene fog would ADD the fog colour to them.
- The audits: the singer stands inside the city's bounding box ("Scene is ~100% inside set:city"): expected. Signs and
  lamps are audited per instance (no blanket tags).

## Assets

Five AmbientCG CC0 sets at 1K from the shared texture library, fetched on first use (`citykit.js`'s `loadPBR`; the
IDs are in [SOURCES](SOURCES.md)).
Crali's paintings were reference only and are not in this repository. Fonts: the repo's bundled fonts.

## Open items

- **Shader errors with shadow maps.** With `renderer.shadowMap.enabled` on and none of the film's other sets in the
  scene, the city kit logs about ten `ShaderModule with 'fragment_uf_…' label is invalid` errors once, at the first
  render (`uf_hole_floor`, `uf_marble`, `uf_ground`, `uf_cloud`, `uf_signs`, `uf_rain`, `uf_light_column`). A probe
  rendered pixel-identical frames with shadow maps on and off, and the film's own modules log the same errors in
  that setup; the full film, with the interiors' shadow-casting lights in the scene, logged none. The cause is
  not traced.
- The cloud phase reads as dark murk with the city glowing through; a stronger "wisps rushing past" look would need
  a volumetric pass.
- Close-range windows are still flat-ish panels (no interior mapping).
- No elevated highway (verse 3's race) yet: the avenues are open canyons, a highway can be laid along one.
