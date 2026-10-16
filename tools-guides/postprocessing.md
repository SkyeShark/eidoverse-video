# Post-processing effects

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

### TSL postprocessing — `CustomEffectsDeno`

The effect registry provides reusable GPU shaders for stylized looks. Use it
when an existing effect fits, or build a custom TSL effect when exploring a
new one. Large per-pixel effects belong on the GPU. Canvas/Satori remain useful
for authored text, display content and graphic elements; see
[motion graphics](motion-graphics.md).

```js
globalThis._fx = globalThis.CustomEffectsDeno.applyTo({
    scene, camera,
    effects: 'depth_fog,glitch_bars',   // comma-separated — chain 1-4 freely
    opts: { glitch_bars: { barFreq: 22, shift: 0.03, opacity: 0.85 } },
});
// per frame — update the effect's uniforms, THEN render. _fx.update(t) does
// NOT render (it only pushes uniforms into the auto-enhance pipeline); the
// scene render still has to happen, every frame, or the video freezes:
await globalThis._fx.update(t);
await globalThis._r.renderAsync(globalThis._s, globalThis._c);
```

**Timed glitch (a burst on a beat) — pulse the effect's live uniform, don't
swap canvases.** Every effect returns `uniforms`; drive them per frame:
```js
globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: 'glitch_bars' });
// in renderFrame(t): ramp intensity on the beat
const u = globalThis._fx.uniforms;
if (u?.opacity) u.opacity.value = beatEnv(t);   // 0 most of the time, 1 on the hit
await globalThis._fx.update(t);
await globalThis._r.renderAsync(globalThis._s, globalThis._c);   // ALWAYS render after — update() doesn't
```

The default auto-enhance path supplies N8AO ambient occlusion, SSR, UnrealBloom and FXAA; a scene can opt out when it owns its compositor (below). Moving sky/cloud reflections on metals come from the `makeSky` facade's `sky.enableReflections()`, which takes an optional options object and uses the camera passed to `makeSky` ([sky-weather.md](sky-weather.md)).

Set `globalThis._aoParams = { aoRadius, quality, intensity, distanceFalloff, halfRes, enabled }` before setup to tune N8AO. Its default `aoRadius` is 5 world units, which on a room- or tabletop-scale set samples the whole space and reads as blotchy grain over every surface; set it to the contact scale you want darkened (0.15 m on a workbench). `quality` defaults to `Neural-High`: N8AO 2.0's neural denoise, a small learned network in the second denoise pass that removes the grain and frame-to-frame boil of the AO. `Neural-Low` and `Neural-Medium` run it with fewer taps; `Performance`, `Low`, `Medium`, `High` and `Ultra` are the standard modes without it. The neural modes always use 16 AO samples at full resolution, so `halfRes` is ignored with them.

The complete current catalog has 31 effects. Discover it programmatically
with `CustomEffectsDeno.list()` or inspect the sources under `effects_tsl/`.
Choose effects for the piece, including none when the image needs no added
treatment. The families below help compare the available looks.

For one effect, `_fx.uniforms` is that effect's uniform object. For a chain,
it is keyed by effect name, such as `_fx.uniforms.glitch_bars`. The available
fields differ by effect; inspect the selected entry before animating it.

Library (31 effects) — the families:
- **3D/volumetric** (scene passes): `nuclear_explosion` (skies and rain are
  NOT effects — use the world-space sky + weather systems)
- **Glitch/retro**: `glitch_bars`, `vhs_tape`, `crt`, `rgb_shift`, `chromatic_aberration_alpha`, `jitter`, `after_image`
- **Colour grade**: `full_toon`, `sepia`, `bleach_bypass`, `old_bw_film`, `bw_halftone`
- **Line/edge**: `cross_hatch`, `neon_edges`, `blueprint`, `dithering`, `retro_wireframe`
- **Atmospheric / light**: `depth_fog`, `godrays`, `lensflare`, `anamorphic_flare`, `underwater`, `rain_on_camera` (lens droplets — world rain is the weather system's job)
- **Distort**: `melt`, `wavy`, `kaleidoscope`
- **Blur/focus**: `focus_blur` (DoF), `radial_blur`, `box_blur`, `hash_blur`

## Era looks — `effects_tsl/era_looks.js`

Graphic-arts looks from the history of computing and print. Every look is a
weight on one post pass, so looks crossfade and stack. They were made for
the DAISY music video, where each era's voice gets its era's picture. The
pass is injected and registered like the effects above (its glyph atlas and
blur pyramid are built once at load); a scene asks for `era_looks`:

```js
const { ERA_LOOKS, applyLook } = EraLooksFX;   // the presets + the crossfade, on the injected effect
globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: 'era_looks' });
// renderFrame(t): crossfade two presets (s = 0..1), update, then render
applyLook(_fx.uniforms, ERA_LOOKS.bell1961, ERA_LOOKS.mac1984, s);
await _fx.update(t);
await _r.renderAsync(_s, _c);
```

Pass the `camera`: `storybook` draws ink lines from its depth, and `crt`
restarts its phosphor persistence on a camera cut. `applyLook` smoothsteps
`s`. The pixel grid (`px`) snaps at the midpoint of a crossfade because it
cannot blend. The weights are ordinary uniforms, so set one over any preset,
for example `_fx.uniforms.glitch.value = beatEnv(t)` for a glitch on the
beat.

| Preset | The look | GPU cost at 1080p |
| --- | --- | --- |
| `clean` | nothing | — |
| `voder1939` | Art Deco gold duotone with a sunburst, grain, flicker | 0.03 ms |
| `bell1961` | 1960s black-and-white CRT | 0.06 ms |
| `printer1961` | line-printer ASCII on green-bar paper | 0.01 ms |
| `eliza1966` | sepia-tinted teletype monochrome | 0.01 ms |
| `vector` | green vector phosphor | ≈ 0 |
| `vfd1978` | cyan vacuum-fluorescent display | ≈ 0 |
| `c64_1982` | Commodore 64 palette, raster bars, 4 px pixels | 0.05 ms |
| `mac1984` | 1-bit ordered dither, 3 px pixels | 0.06 ms |
| `amber1984` | amber terminal with scanlines | 0.01 ms |
| `web2001` | 216-colour web-safe dither | 0.06 ms |
| `neural2016` | false-colour neural feature map | 0.05 ms |
| `glitch` | tear bands and split chroma | ≈ 0 |
| `zine` | risograph: two misregistered inks | 0.01 ms |
| `painterly` | Kuwahara paint | 0.10–0.14 ms |
| `poster`, `poster_night` | CMYK protest poster on newsprint: four rotated dot screens, misregistered plates, a line-art key plate | 0.12–0.21 ms |
| `crt` | curved CRT glass: scanlines that swell when bright, aperture grille, glass glow, persistence | 0.34–0.40 ms |
| `crt_8bit` | the Commodore 64 picture on a TV tube | 0.34–0.47 ms |
| `storybook` | storybook plate: soft cel bands, warm ink lines from depth, normals and colour | 0.09–0.16 ms |
| `candle_film` | candle-lit film: red-orange halation round highlights, gate weave, grain | 0.26–0.30 ms |
| `watercolor`, `watercolor_night` | wet paper: washes, pigment rims at edges, granulation, bleeds | 0.32–0.38 ms |

A preset is a dict of weights from 0 to 1. The look weights are `sepia`,
`deco`, `bw`, `ascii`, `vector`, `vfd`, `c64` with `raster`, `mac`, `amber`,
`websafe`, `feature`, `glitch`, `riso`, `kuwahara`, `halftone`, `phosphor`,
`toon`, `halation` and `watercolor`. On top of those are layers:
- `px`: pixel size, where 1 is off.
- `grain`, `flicker`, `scan` and `vignette`.
- `lift`: stops of print exposure for the paper looks.

The `_night` presets set `lift` so a dark scene prints readably. Use the
daylight preset (lift 0) for day scenes, or they overexpose. Build your own
preset as a plain object, for example `{ phosphor: 1, amber: 0.6 }`.

The costs are GPU time over `clean` on an RTX 5090 Laptop GPU; the whole
auto-enhanced test frame took about 5.2 ms. A look that is off costs nothing:
the heavy looks sit behind uniform branches, and the blur chains used by
halation, the CRT glow and the watercolour bleed skip their passes unless a
look that reads them is on. Those three add about 1–1.5 ms of CPU submit per
frame when on.

The pass receives linear HDR. The quantizing looks work in a perceptual
space. The print and paint looks work in display space through the
renderer's ACES curve and its exact inverse, so paper and ink land on screen
as authored; a few warm tones sit just outside ACES's range, so newsprint
prints a hair pinker. Halftone dots and watercolour paper stay fixed to the
screen like a real page, so motion slides under them. `storybook` draws its
lines alongside a VRM's MToon outline (on the claudesona the two coincide).

## Aeropittura — `effects_tsl/aeropittura.js`

The frame repainted as a Futurist painting of a dark cyberpunk night, made for
the UNKNOWN FORCE music video (2026-10): Crali's aeropittura dives, Balla's
street lights and sun cones, Boccioni's divisionist strokes, Carrà's dark
grounds. Like the era looks it is one pass with a weight per ingredient, plus a
master `force`, injected and registered like the others:

```js
const A = AeropitturaFX;   // LOOKS, PLANES, applyLook, setPlanes, RAMP
globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: 'aeropittura',
    opts: { aeropittura: { layer: 'under' } } });   // under the HUD: captions stay crisp
const U = _fx.uniforms;
// renderFrame(t):
A.applyLook(U, A.LOOKS.argue, 1);               // or applyLook(U, from, force, to, s): a crossfade
A.setPlanes(U, A.PLANES.balla_sun);             // the plane family; switch it on cuts
U.focal.value.set(fx, fy);                      // the idol the cones radiate from (uv, y down)
U.spare.value.set(hx, hy, r);                   // a face kept readable (uv, y down; r in frame heights)
await _fx.update(t);
await _r.renderAsync(_s, _c);
// on a camera cut: U.cut()                     // the time echoes restart from the new shot
```

**The looks.** `LOOKS` holds `off`, `hush` (the quiet floor: still a
painting, just a calm one), `argue` and `storm`. The film used the look as the
argument's volume: `argue` in the camps' rooms, `storm` in the choruses, `hush`
at the end. It never set `off`, because a clean image would claim a pure
outside that the song denies.

**The ingredients** (0..1, each multiplied by `force`):

- `echo`: simultaneity. R, G and B show different instants, about 50 ms apart.
  Still things are untouched.
- `multi`: Balla's repetitions, up to four older copies of anything that moves.
- `strokes`: the divisionist stroke layers, broad over flats and fine at
  edges. Each stroke is one colour from the scene, pushed warmer or cooler,
  with a few toward the complement.
- `under`: the anisotropic-Kuwahara underpainting the strokes sit on.
- `halo`: Balla's *Street Light*, V-strokes of a light's colour and its
  complement round every real light. Only display values above about 0.8 make
  them, so a lit face does not grow flames.
- `planes`: the plane family's slips, shadow planes, neon glazes and painted
  plane edges.
- `lines`: lines of force, drags along the contours of moving things and
  sparse speed lines toward the focal point.
- `palette`: the dark-cyberpunk gradient map (`RAMP`: wet black, petrol teal,
  bruised violet, neon magenta, sodium, cold white). Saturated light keeps its
  own hue.
- `canvas`: canvas weave, a VHS scanline and grain.
- `crisp`: hands fine detail back sharp (lettering, eyes, the mouth line).

**The planes.** `PLANES` has six families:

- `balla_sun`: rays and rings from the focal point (Balla's *Mercury Passing
  Before the Sun*).
- `revolt`: Russolo's chevrons.
- `race_sun`: rays plus chevrons along `chevDir`.
- `iridescent`: Balla's triangle lattice.
- `dive`: rays and long diagonals.
- `quiet`: a few diagonals.

A family's plane ids switch at weight 0.5, so change families on cuts.

**The other uniforms.**

- `focal`: where the cones and speed lines start. Point it at the shot's idol:
  the altar, the gold door, the floodlight, the singer.
- `spin` turns the rays and the diagonals (radians).
- `swirl` (radians at the centre) and `swirlR` (frame heights) make Crali's
  vortex round the focal point, for a dive.
- `brushAngle` is the stroke direction where the picture has no contours. The
  default, 1.05 rad, is a Futurist diagonal.
- `chevDir` aims the chevrons.

**Reading shots.** In-scene text (a whiteboard, a plaque, a post) disappears
under full brushwork. When the camera lands on words, ease the brush for the
length of the shot and keep the planes, palette and canvas. The film eased in
over 0.6 s and out over the last 0.45 s, toward these values:

```js
const READ = { strokes: 0.28, under: 0.3, halo: 0.15, lines: 0, multi: 0, crisp: 1 };
for (const [k, v] of Object.entries(READ)) U[k].value += (v - U[k].value) * k01;   // k01: 0 → 1 → 0
```

Overlay text (captions, `parole.js`, a chyron) is composited after this pass,
so it is never painted.

**The NaN hazard.** A non-finite `focal`, such as a point projected from
behind the camera or a NaN handed back by a set, blacks out the whole frame:
each plane's slip is `hash(id) × weight`, and 0 × NaN is NaN. Check
`Number.isFinite` before writing `focal` and `spare`. The pass also clamps its
HDR input, because a single Inf or NaN pixel would otherwise spread through the
halos' blur pyramid. Sets with exp() in their shaders can produce one at
grazing angles (see the [city's notes](../eidoverse/sets/unknown_force/CITY_HOLE.md#things-that-bit)).

**Colour.** The pass paints in display space through the renderer's ACES and
its exact inverse, so the ramp lands as authored. Under `argue`, near-white
neutrals fall between the ramp's orange and white stops, so a white set paints
peach. The film pulled `palette` down to 0.22 for its white showroom.

**Art direction from Skye.** "More painterly like futurist paintings but also
more dark cyberpunk rather than outrun": wet black streets, rain, fog, petrol
teal and sodium, with neon magenta and cyan as accents, not the room. No
outrun grid, no slit sun. "Vary the strokes so words in the scene stay
readable; keep the radial planes": that became the reading shots above.

**Cost.** About 6–8 ms per frame at 1920 × 1080 at `storm` on an RTX 5090
Laptop GPU. The halo's blur pyramid skips its passes when `halo × force` is
0. The [UNKNOWN FORCE sets](../eidoverse/sets/unknown_force/README.md) give
their per-shot totals with the pass on.

## Renderer integration

The renderer injects each `effects_tsl/*.js` implementation before
`custom_effects_deno.js`. Use the registry instead of eval-loading effect files
again. The native auto-enhance path adds AO, reflections, bloom and antialiasing.
If a scene owns a complete custom compositor, set `_noAutoEnhance = true` in
`setup()` and verify the final render path; updating effect uniforms alone does
not produce frames. See [scene-format.md](scene-format.md) and
[stack-notes.md](stack-notes.md) for render hooks and depth/transparent surfaces.
