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

Set `globalThis._aoParams = { aoRadius, quality, intensity, distanceFalloff, halfRes, enabled }` before setup to tune N8AO. Its default `aoRadius` is 5 world units, which on a room- or tabletop-scale set samples the whole space and reads as blotchy grain over every surface; set it to the contact scale you want darkened (0.15 m on a workbench). `quality` takes `Performance`, `Low`, `Medium`, `High` or `Ultra`.

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

## Era looks — `era_looks.js`

Graphic-arts looks from the history of computing and print. Every look is a
weight on one post pass, so looks crossfade and stack. They were made for
the DAISY music video, where each era's voice gets its era's picture. The
pass is not one of the injected effects above; a scene imports the module,
which registers `era_looks` with the same registry:

```js
const { registerEraLooks, ERA_LOOKS, applyLook } = await import(new URL('era_looks.js', EIDOVERSE_DIR).href);
await registerEraLooks();   // once, in setup(): registers 'era_looks', draws the line-printer glyph atlas
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

## Renderer integration

The renderer injects each `effects_tsl/*.js` implementation before
`custom_effects_deno.js`. Use the registry instead of eval-loading effect files
again. The native auto-enhance path adds AO, reflections, bloom and antialiasing.
If a scene owns a complete custom compositor, set `_noAutoEnhance = true` in
`setup()` and verify the final render path; updating effect uniforms alone does
not produce frames. See [scene-format.md](scene-format.md) and
[stack-notes.md](stack-notes.md) for render hooks and depth/transparent surfaces.
