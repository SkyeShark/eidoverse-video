# Post-processing effects

[Main instructions](../AGENTS.md) · [Tool inventory](../docs/TOOLS.md)

In the Blender edition the renderer does most of what the WebGPU post chain
did, and does it in 3D: depth of field is the lens, fog is a volume, AO and
reflections are traced. What stays in post is the compositor: glare, the
stylized looks, overlays. Code: `blender/eidoblend/look/render_settings.py`
(the look presets), `look/post/chain.py` (the compositor's order),
`look/post/custom_effects.py` (the effect registry), `look/post/era_looks.py`,
`look/post/aeropittura.py`, `look/post/after_image.py` and
`look/post/screen_effects.py` (the passes), `look/post/history.py` (earlier
frames). Tests: `blender/tests/look/test_post.py` and
`blender/tests/post_era/` render every effect, and their sheets are the
reference pictures.

## The EEVEE look — `apply_auto_enhance`

The WebGPU harness ran N8AO, SSR, bloom, TRAA, FXAA and ACES on every frame.
EEVEE does those jobs in the renderer:

| WebGPU | EEVEE |
| --- | --- |
| N8AO (`_aoParams`, radius 0.3 m) | fast GI, `GLOBAL_ILLUMINATION` (or `AMBIENT_OCCLUSION_ONLY`); `fast_gi_distance` is the contact scale. Indoors with a baked room probe, `ao=False`: either mode lit floor contacts with the world through the walls |
| SSR, edge fade | ray tracing (SCREEN), `trace_max_roughness`; misses fall back to sphere probes and the world; `use_overscan` keeps the frame edges |
| UnrealBloom | the compositor's Glare 'Bloom' (off by default, as in episode three's house) |
| TRAA, FXAA | `taa_render_samples` jittered samples per frame through a 1.5 px filter: supersampled; no history between frames |
| ACES (`renderOutput`) | the view transform: AgX, its look, exposure, white balance |
| the gradient env fallback | the world (the sky family's, or a neutral colour) |

```python
from eidoblend.look import render_settings as RS
RS.apply_auto_enhance(scene, 'film')                    # 1920x1080, 32 samples: episode three's measured look
RS.apply_auto_enhance(scene, 'probe')                   # the same look at 960x540, 16 samples
RS.apply_auto_enhance(scene, 'film', ao={'distance': 0.4}, ssr={'max_roughness': 0.6}, bloom={'strength': 0.2, 'threshold': 3.0})
print(RS.summary(scene))                                # log the look actually set, before every render
```

`'film'` is read from episode three's house: ray tracing SCREEN with max
roughness 0.5 and all three denoisers; fast GI 0.6 m; shadows 2 rays × 12
steps; volumes at tile 16 × 32 samples (measured on the house to look the same
as 4 × 128 at 2.5 s a frame instead of 4.1); motion blur, shutter 0.5,
centred; filter 1.5; overscan 3%; AgX Base Contrast. Exposure is the scene's
own, not the preset's: the corner room took +2.25, the meadow fixture's sun
+0.50.
Measure it ([exposure](camera-lighting.md#exposure-measured)).
`apply_auto_enhance` turns `use_sequencer` off unless `keep_sequencer=True`:
with strips in the VSE, Blender renders the strips instead of the 3D view.

Samples: 16 is enough to judge a sunlit exterior. In a dim interior, a white
sphere showed grain at 16 and 32 samples and was clean only at 64. The grain
was fast GI's: with fast GI off (`ao=False`) and a baked room probe it was
clean at 16, and the room matched Cycles. Indoors, turn fast GI off
([probes](camera-lighting.md#ray-traced-lighting-eevee)); then raise samples
before reaching for a denoiser.

## The post chain — `post/chain.py`

The compositor graph keeps the WebGPU chain's order:

    Render Layers -> bloom -> 'under' effects -> overlay (a HUD, alpha over) -> 'over' effects -> Group Output

All of it works on scene-linear light. AgX, the scene's view transform,
applies once after the whole graph, as three's tone map applied after its
overlay. Stages are nodes named `<slot>:<name>`, kept in order and relinked
whenever one is added or removed. With no stages the scene renders with no
compositor at all, as the house did: EEVEE + AgX + motion blur + DOF.

```python
from eidoblend.look.post import chain
chain.set_bloom(scene, strength=0.25, size=0.5, threshold=1.0)   # Glare 'Bloom'; set_bloom(scene, None) removes it
chain.add_stage(scene, 'over', 'grade', node)                     # any compositor node with an Image in and out
chain.set_overlay(scene, image_node)                              # the overlay slot: alpha over everything below
chain.stages(scene)                                               # [(slot, name, node)] in order
chain.save_frames_passes(scene, '//raw', ('Depth', 'Normal'), name='frame')    # record them while rendering
chain.use_saved_frames(scene, '//raw/frame_0001_combined.exr',
                       passes={'Depth': '//raw/frame_0001_depth.exr', 'Normal': '//raw/frame_0001_normal.exr'})
```

Bloom's threshold is scene-linear light before AgX, the same domain as three's.
The Glare node's Clamp and Maximum keep a stray NaN/Inf or a firefly from
blooming the frame white.

`use_saved_frames` runs the chain over rendered frames instead of a render: a
look can be graded again over a finished film without rendering it again
(`save_frames_passes` writes Combined, Depth and Normal beside each other). The
`post_era` tests work this way: the scenes render once, every look composites
over the saved frames.

## The effect registry — `custom_effects`

```python
from eidoblend.look.post import custom_effects as fx
e = fx.apply_to(scene, 'glitch_bars,rgb_shift', {'glitch_bars': {'barFreq': 22, 'shift': 0.03, 'opacity': 0.85},
                                                 'rgb_shift': {'amount': 0.006}})
e.uniforms['rgb_shift']['amount'].default_value = 0.008  # an effect's inputs: sockets to set or key
fx.list()                                                # what exists, its options, how each is done
fx.list_effects()                                        # the names (CustomEffectsDeno.listEffects)
fx.register('my_look', build, params=[('amount', 1.0)])  # another package's effect (build(scene, opts) -> a group)
fx.remove(scene, 'rgb_shift'); fx.clear(scene)           # take effects out of the chain
```

The registry keeps `custom_effects_deno.js`'s rules:

- `effects` is a name, a comma string or a list. Every name must be
  registered: an unknown one raises a KeyError naming them all, before
  anything is built. A registered name that is not ported raises
  NotImplementedError with the reason.
- Effects chain in the order given, each seeing its predecessor's output. The
  WebGPU registry needed `rtt()` render targets between stages; here every
  stage is a node in one compositor graph, so any number chain.
- Each effect sits on a layer. World effects run under the overlay (a HUD),
  signal effects over it. `nuclear_explosion`, `godrays` and `underwater` are
  locked under; `depth_fog` and `retro_wireframe` start under; everything else
  starts over. `{'layer': 'under' | 'over'}` in an effect's options switches
  it. With several effects the split is printed, as WebGPU logged it.
- With one effect, `e.uniforms` is that effect's own uniforms
  (`e.uniforms['opacity']`) and also answers by name
  (`e.uniforms['glitch_bars']['opacity']`); with several it is keyed by
  effect name only.
- `e.update(t)` and `e.set_resolution(w, h)` exist and do nothing: Scene Time
  drives time inside the graph and the compositor works at the render size.

One difference: `apply_to` adds to the scene's chain, so a bloom applied by a
set and a look applied by the film both stay. `CustomEffectsDeno.applyTo`
replaced the scene's effects on every call; `fx.clear(scene)` first gives that.

**The options are the WebGPU effect's own.** Each effect takes the options of
its `effects_tsl/<name>.js`, in snake_case. A ported scene's camelCase spelling
is accepted (`barFreq` is `bar_freq`), in `apply_to`, `uniforms` and `key`
alike. An option the effect doesn't know raises a KeyError that names the ones
it does; `{'rgb_shift': {'pixels': 4}}` raises. A WebGPU option with no Blender
counterpart, such as lensflare's `ghostSpacing`, prints why and is ignored.
Nothing is dropped silently.

**A timed burst is keyframes**, not a per-frame loop. The uniforms are the
inputs of each effect's node group, so a beat is an F-curve, here on the
effect's own `opacity`:

```python
e = fx.apply_to(scene, 'glitch_bars')
for f, v in ((58, 0.0), (60, 1.0), (62, 0.0)):        # a burst on the hit at frame 60
    e.key('glitch_bars', 'opacity', f, v)
```

Time inside an effect comes from the compositor's Scene Time node, so nothing
has to be pushed per frame. In the test, frame 60 shows the split bars, and
frame 64, keyed back to 0, matches the plain render within 3 levels at the
worst pixel.

**Scene-linear, as WebGPU's hooks were.** The WebGPU hooks ran on the lit HDR
frame before ACES (`render_scene.mjs`: the colour hook, then the overlay, then
the screen hook, then `renderOutput`). The groups here work on scene-linear
light before AgX, in the same order: the chain's 'under' and 'over' slots.
Every tap is a Map UV sample with the edges clamped, as a WebGPU texture's
ClampToEdge, at UVs from Image Coordinates. The shaders' uv is kept as WebGPU
saw it, y down from the top of the frame, so a formula ports as written
(`_graph.py`, an expression layer that builds the nodes as the TSL is read).
Translate is not used for taps: it moves the image's domain, and a channel
combined with a translated one inherits the shifted domain. The first
rgb_shift was built that way and left a 4 px black bar at the left edge and a
yellow one at the right; the Map UV port has neither.

## What each WebGPU effect became

Native first: what EEVEE does in the render is done there, not faked in post.

| WebGPU effect | options (WebGPU's, snake_case) | Blender | status |
| --- | --- | --- | --- |
| `glitch_bars` | `bar_freq`, `scroll_speed`, `shift`, `opacity` | a group, its shader ported: bars where `fract(v·bar_freq + t·scroll_speed) ≥ 0.7`, red and blue split by `shift·sin(12t + 50v)` | rendered |
| `rgb_shift` | `amount` (UV), `angle`, `opacity` | three's `rgbShift`: red at uv + amount·(cos, sin), blue at uv − that | rendered, edges checked |
| `radial_blur` | `center_x`, `center_y`, `weight`, `decay`, `exposure`, `opacity`; `count` (built in) | three's `radialBlur`: `count` taps toward the centre weighted weight·decayᵏ, ×exposure/count, added over the frame | rendered |
| `box_blur` | `opacity`; `size` 1..3, `separation` (built in) | three's `boxBlur`: a (2·size + 1)² grid of taps `separation` px apart, averaged (rows then columns) | rendered |
| `sepia` | `amount`, `opacity` | three's sepia matrix (glfx.js) | rendered |
| `old_bw_film` | `opacity` | the silent-film pass: 12 fps cadence, gate weave, dust in drifting regions on some frames, exposure flicker, vignette, jump cut at 7.7–8.2 s of a 24 s loop, BT.601 luma. Blender's Perlin noise stands in for the shader's simplex (spread ×1.6 to keep the dust thresholds' rarity) | rendered over 12 frames |
| `neon_edges` | `glow_color`, `threshold`, `strength`, `opacity` | 4-tap Laplacian of BT.601 luma; core + half the halo in `glow_color` (hot pink by default), added over the frame | rendered |
| bloom (UnrealBloom) | `strength`, `radius` (= Glare Size), `threshold` | Glare 'Bloom' | rendered |
| `lensflare` | `threshold`, `strength`, `ghost_tint`, `ghost_samples` (= Iterations 2..5), `opacity` (× strength); `ghost_spacing`, `ghost_attenuation` warned | Glare 'Ghosts' | rendered |
| `anamorphic_flare` | `threshold`, `strength`, `color` (blue by default), `opacity` (× strength), Blender's `fade`; `scale`, `samples` warned | Glare 'Streaks', 2, horizontal (the bloom slot, as WebGPU's pre-bloom hook) | rendered |
| `focus_blur` | `focus_distance`, `focus_objects` (their focus points averaged, followed every frame), Blender's `fstop`; `focal_length`, `bokeh_scale`, `opacity` warned | the camera's depth of field | native |
| `depth_fog` | `color`, `density` (per metre, as WebGPU's exponential falloff), `noise_amount`, `noise_scale`; `edge_radius`, `edge_strength`, `opacity` warned | a fog layer: a volume box lit and shadowed by the scene; the volume range set to cover it | native, rendered with and without noise |
| `godrays` | depth_fog's; `light`, `strength`, `cloud_opacity_tex` warned | the fog layer + volumetric shadows; `sun_beams` (Glare 'Sun Beams') as the post fallback | native; `sun_beams` rendered but not judged: the test frame had no source above its threshold |
| `era_looks` | the 25 weights and `px` ([below](#era-looks--postera_lookspy)); Blender's `persist_frames`, `cuts`; `time`, `frame`, `weave` (Scene Time drives them), `cam_near`, `cam_far` (a driver on the camera's clip end) warned | one pass, every look a weight | every preset rendered, parity-checked |
| `aeropittura` | the 10 ingredients, `force`, the 5 plane weights, `focal`, `spare`, `spin`, `swirl`, `swirl_r`, `brush_angle`, `chev_dir`; Blender's `cuts` ([below](#aeropittura--postaeropitturapy)); `time`, `frame` (Scene Time) warned | one pass, the futurist painting | every look and plane family rendered |
| `after_image` | `damp`, `opacity`; Blender's `cuts` | three's afterImage: its own trail a frame earlier, read back from disk ([below](#earlier-frames--after_image-and-posthistorypy)) | every frame checked against the feedback in numpy |
| `wavy` | `amplitude` (px), `frequency`, `phase`, `animate`, `anim_speed`, `opacity`; `width`, `height` warned | rows shifted by amplitude·sin(frequency·y + phase [+ t·anim_speed]) | rendered, parity |
| `kaleidoscope` | `segments`, `rotate`, `opacity` | the frame folded into mirrored wedges about its centre | rendered, parity |
| `jitter` | `speed`, `amplitude`, `opacity` | red, green, blue each displaced by a sin-hash burst; the seed folded every 1000 as WebGPU's update did | rendered, time-driven |
| `melt` | `speed`, `swirl`, `opacity` | each pixel pulled along its hue angle by its saturation, breathing with time | rendered, time-driven |
| `dithering` | `levels`, `opacity` | perceptual quantisation with three's `bayerDither` offset | rendered, parity |
| `chromatic_aberration_alpha` | `amount`, `angle`, `opacity` | red and blue split along `angle`, each weighted by its own sample's alpha | rendered, parity |
| `bw_halftone` | `threshold`, `dot_size`, `angle` (degrees), `ink_color`, `paper_color`, `opacity`; `width`, `height` warned | a rotated cosine dot screen thresholded against luminance | rendered, parity |
| `bleach_bypass` | `amount`, `opacity` | three's `bleach()` | rendered, parity |
| `hash_blur` | `amount`, `opacity`; `repeats` (built in) | three's `hashBlur()`: `repeats` taps on a hashed spiral | rendered |
| `crt` | `opacity`; `width`, `height` warned | the curved tube: barrel warp, wobble, guns and ghosts, rolling scanlines, flicker, aperture grille | rendered, time-driven |
| `vhs_tape` | `intensity`, `opacity`; `width`, `height` warned | tape wobble, tracking noise, head-switching rows, YIQ chroma smear over a sigma-1 blur, dropouts, grain, tint | rendered, time-driven |
| `rain_on_camera` | `amount`, `speed`, `drop_size`; `resolution`, `directions`, `quality`, `blur_size` (built in) | drops running down the lens: the frame refracted through them and blurred behind them | rendered, time-driven |
| `blueprint` | `paper_color`, `grid_color`, `ink_color`, `cell_px`, `major_every`, `minor_line_w`, `major_line_w`, `grid_strength`, `major_strength`, `edge_strength`, `threshold`, `sharpness`, `depth_weight`, `normal_weight`, `rim_weight`, `rim_sharpness`, `shade_mid`, `shade_stripe_px`, `shade_line_width`, `paper_grain`, `vignette`, `opacity`; `shade_hi` (never read by its shader), `width`, `height`, `cam_near`, `cam_far` warned | blueprint paper, printed grid rulings, ink on depth, normal and rim edges, striped shading; the Normal pass turned to view space by the camera's axes (drivers). Its normals are decoded twice, as WebGPU's were, so the rim fires about 60° from facing | rendered |
| `cross_hatch` | `wiggle`, `flicker`, `outline_strength`, `hatch_strength`, `depth_outline_strength`, `depth_outline_thresh`, `opacity`; `width`, `height`, `cam_near`, `cam_far` warned | a pencil drawing: outlines from the gradient of the noise-wiggled frame at three scales plus depth edges, five hatch layers following the value (skipped on bright pixels, turned on near objects), a facing boost from the view normal, paper grain, vignette, S-curve. Its 256 × 256 noise texture is regenerated byte for byte (the same LCG, run with JavaScript's arithmetic) | rendered |
| `underwater` | `horizon_color`, `shallow_color`, `fog_density`, `fog_power`, `caustic_amt`, `caustic_scale`, `godray_amt`, `opacity`; `bubble_count`, `bubble_radius`, `bubble_range_y` (built in); `bubble_amt` (never read by its shader) warned | always under the overlay. The screen pass: a caustic water roof where nothing was drawn, caustics on up-facing geometry at its world position, depth fog to the horizon colour, god rays; positions rebuilt from the Depth pass along the camera's rays (its fov, near, far, axes and position, by drivers). The bubbles: Geometry Nodes on Scene Time round the camera's position, seeded (WebGPU drew them from Math.random()) | rendered over saved frames and live |
| `retro_wireframe` | `color` (`green`, `amber`, `blue`, `multicolor`), `line_width` (px), `bg_color`, `line_intensity`, `hdr_channel_cap` | geometry-side, as WebGPU's material swap: a view-layer material override whose Wireframe node (pixel size) draws every render triangle at a constant pixel width, emission only, the world the background colour; `multicolor` adds a Geometry Nodes modifier storing a hash per triangle. `screen_effects.set_wire_color(scene, U, name)` and `retro_wireframe_cleanup(scene)` are WebGPU's `setColor` and `cleanup` | rendered live |
| `full_toon` | `near_levels`, `far_levels`, `band_softness`, `hue_shift`, `saturation`, `contrast`, `smooth_radius`, `shadow_tint`, `midtone_tint`, `highlight_tint`, `outline_color`, `outline_strength`, `outline_threshold`, `outline_sharpness`, `outline_depth_weight`, `outline_normal_weight`, `opacity`; `width`, `height`, `cam_near`, `cam_far` warned | a screen cel pass on the Depth and Normal passes: depth-aware blur, bands by depth, a palette tint, outlines; its depth is WebGPU's 2z / (z + far), far from the camera's clip end | rendered |

For an additive glare, `opacity` scales the glare and so multiplies its
strength. "Parity" means the render matches the effect's shader transcribed
into numpy on the same saved frame: a mean error of 2e-5 or less, and no
pixel off by more than 0.02, at the WebGPU defaults and with options turned
(`tests/post_era/test_screen_effects.py`). "Time-driven" means two frames over
the same held source frame differ.

A finite fog layer, not a world volume: an infinite world volume extinguishes
the sun and the sky entirely (measured: a black frame at 0.012/m).

## Era looks — `post/era_looks.py`

Graphic-arts looks from the history of computing and print, made for the
DAISY music video, where each era's voice gets its era's picture. Every look
is a weight on one compositor pass, so looks crossfade and stack:

```python
from eidoblend.look.post import custom_effects as fx, era_looks as EL
e = fx.apply_to(scene, 'era_looks')                     # over the overlay, as WebGPU's default
U = e.uniforms
EL.set_look(U, EL.ERA_LOOKS['crt'])                     # one preset (the other weights 0)
EL.crossfade(U, EL.ERA_LOOKS['bell1961'], EL.ERA_LOOKS['mac1984'], 48, 72)   # keyed on frames 48-72
EL.apply_look(U, EL.ERA_LOOKS['vector'], EL.ERA_LOOKS['amber1984'], 0.3, frame=100)  # applyLook, keyed at 100
e.key('era_looks', 'glitch', 60, 1.0)                   # any weight over a preset: a glitch on the beat
```

`apply_look(U, from, to, s)` is WebGPU's `applyLook`: `s` is smoothstepped,
and the pixel grid `px` snaps at the midpoint because it cannot blend.
`crossfade` keys it on every frame between two frames, LINEAR, `px` CONSTANT,
so the crossfade lives in the `.blend`. A preset is a dict of weights, as
before; build your own (`{'phosphor': 1, 'amber': 0.6}`).

| Preset | The look |
| --- | --- |
| `clean` | nothing (the frame passes through unchanged: checked, 0 levels) |
| `voder1939` | Art Deco gold duotone with a sunburst, grain, flicker |
| `bell1961` | 1960s black-and-white CRT |
| `printer1961` | line-printer ASCII on green-bar paper |
| `eliza1966` | sepia-tinted teletype monochrome |
| `vector` | green vector phosphor |
| `vfd1978` | cyan vacuum-fluorescent display |
| `c64_1982` | Commodore 64 palette, raster bars, 4 px pixels |
| `mac1984` | 1-bit ordered dither, 3 px pixels |
| `amber1984` | amber terminal with scanlines |
| `web2001` | 216-colour web-safe dither |
| `neural2016` | false-colour neural feature map |
| `glitch` | tear bands and split chroma |
| `zine` | risograph: two misregistered inks |
| `painterly` | Kuwahara paint |
| `poster`, `poster_night` | CMYK protest poster on newsprint: four rotated dot screens, misregistered plates, a line-art key plate |
| `crt` | curved CRT glass: scanlines that swell when bright, aperture grille, glass glow, persistence |
| `crt_8bit` | the Commodore 64 picture on a TV tube |
| `storybook` | storybook plate: soft cel bands, warm ink lines from depth, normals and colour |
| `candle_film` | candle-lit film: red-orange halation round highlights, gate weave, grain |
| `watercolor`, `watercolor_night` | wet paper: washes, pigment rims at edges, granulation, bleeds |

The weights are `sepia`, `deco`, `bw`, `ascii`, `vector`, `vfd`, `c64` with
`raster`, `mac`, `amber`, `websafe`, `feature`, `glitch`, `riso`, `kuwahara`,
`halftone`, `phosphor`, `toon`, `halation` and `watercolor`; the layers `px`
(pixel size, 1 is off), `grain`, `flicker`, `scan`, `vignette`, and `lift`
(stops of print exposure for the paper looks). The `_night` presets set `lift`
so a dark scene prints readably; daylight presets on a night scene print
nearly black, and night presets on a day scene overexpose.

**How the pieces became compositor nodes.**

- The pass is one node group (`eido_era_looks_k<K>`) with the heavy looks in
  sub-groups; the uniforms are its inputs, so every weight is keyable.
- Every look is evaluated on every frame. WebGPU skipped a look that was off
  (uniform `If` branches); a compositor evaluates every node (a Switch
  evaluates both sides), so the pass costs the same whatever the weights.
  Measured at 960 × 540: the group builds in 10–11 s (about 3,700 nodes
  inlined; it is reused while the file keeps it), and composites in 0.19 s a
  frame on the GPU compositor (0.25 s against 0.06 s for the same saved frame
  with no pass) and 1.1 s on the CPU compositor.
- The print and paint looks (halftone, toon, watercolor) work in display space
  through the scene's own view transform and its inverse (`post/display.py`:
  Convert To Display, its exposure driven from the scene's), as WebGPU's went
  through its ACES curve. Paper and ink land on screen as authored under AgX.
- The integer hashes are Blender's White Noise: the same spread, not the same
  numbers. Grain, flicker, the glitch tears and the halation grain differ in
  detail from WebGPU's frames.
- three's mip-chain Gaussian (BloomNode) is Scale ½ plus Gaussian Blur per
  level at its kernel radii, sampled back by Map UV: the halation glow, the
  CRT glass glow and the watercolour bleed.
- `fwidth()` is the analytic derivative of the halftone's dot screen, and a
  one-pixel difference of the materialised field in the watercolour.
- The storybook's lines read the Depth and Normal passes (`chain.source_pass`
  switches them on). Its far plane, where nothing was drawn, is the scene
  camera's clip end through a driver (`cam_far`), as WebGPU's depth buffer
  cleared to its far plane. The near plane has no part: Blender's depth is
  metric. Normals are world space; only their dot products are used.
- The ASCII glyph atlas is drawn by Blender's text renderer (`blf`) in Press
  Start 2P at 30 px, one 32 × 56 cell a glyph, into a packed image, so a saved
  file renders on its own (`EL.glyph_atlas()`). It was placed to match the
  WebGPU harness's own canvas drawing (the same code run through
  @napi-rs/canvas): '@' inks rows 14–40 of 56 in both. The glyphs print
  upright. The WebGPU probe printed them upside down (its '.' sat high like an
  apostrophe: the canvas shim's flip is a texture transform, which an
  explicit-uv sample skips), and it printed its black background as '-', the
  ramp's fourth glyph, where the code as written prints '@'; I could not find
  that second cause in its code, so the port prints what the code says.
- The NaN clamp: the pass clamps its input first (NaN → 0, +Inf → 65504),
  because here every look mixes in by its weight and 0 × Inf is NaN: one bad
  pixel would spread through the blur pyramids into every look weighted 0.
  Checked: a frame with NaN and Inf pixels gives a finite frame under every
  look alone and under none.
- The CRT's persistence (three's AfterImage on the pass's input, damp
  exp(−1/(fps·0.04))) reads the last K input frames back from disk
  ([history](#earlier-frames--after_image-and-posthistorypy)): max over k of
  frame(n−k)·dampᵏ, each surviving the 0.1 mask, which is exactly the feedback's
  value (K = 7 at 24 fps, 8 at 30). It restarts on a cut (camera markers, a
  camera jump over 0.6 m or 10° found ahead of the render, or `cuts=[...]`)
  and when the tube comes on, as WebGPU's did: every recorded frame carries a
  flag saying whether the CRT was on. `persist_frames=0` turns it off and
  writes nothing.

Checked against a numpy transcription of `era_looks.js` on the meadow frame
(`tests/post_era/ref_era.py`): sepia, deco with its sunburst, bw, vector, vfd,
amber, mac on its 3 px grid, websafe on 2 px, c64 with the raster bars on 4 px,
riso (its grain cancelled), feature, scan, vignette and their mixes agree to
rounding (mean error under 1e-5); ascii within 0.001; kuwahara differs on
0.02% of pixels, where two quadrants' variances tie. Grain, flicker, the
glitch tears and the halation grain are hashes (left out), the print and paint
looks are judged on the renders. Every preset is rendered on the meadow, on
the era probe beside the WebGPU probe's own frames
(`tests/post_era/out/era/probe_vs_webgpu.jpg`) and, for the night presets, on
a neon night set and on THE HOLE (`out/aero/era_on_hole_sheet.jpg`).

Three differences from the WebGPU probe. Two come from the view transform, not
the pass. The palette looks mix their palettes in scene-linear before it, as
WebGPU's did before its ACES output, and AgX shows the palette's white (1.0)
at 195 of 255 where ACES showed 225: the C64 raster bars and the Mac's white
read a step greyer (measured on the bars). And AgX lifts deep shadows far more
than ACES: the probe's floor, black on the WebGPU screen, is dark grey here,
so `poster_night` prints it grey and `mac1984` dithers it into sparse dots.
The third is not isolated: on the dark background the watercolour's paper
tooth is fainter than WebGPU's (pixel spread 1.9 levels against 6.6). Its
tooth scales with the wash's pigment, which reads the source frame, and the
WebGPU probe kept no clean frame to compare the sources with.

## Aeropittura — `post/aeropittura.py`

The frame repainted as a Futurist painting of a dark cyberpunk night, made for
the UNKNOWN FORCE music video: Crali's aeropittura dives, Balla's street
lights and sun cones, Boccioni's divisionist strokes, Carrà's dark grounds.
One pass with a weight per ingredient and a master `force`:

```python
from eidoblend.look.post import custom_effects as fx, aeropittura as AP
e = fx.apply_to(scene, 'aeropittura', {'aeropittura': {'layer': 'under'}})   # under the HUD: captions stay crisp
U = e.uniforms
AP.apply_look(U, AP.LOOKS['argue'], 1.0)                 # or apply_look(U, from, force, to, s): a crossfade
AP.apply_look(U, AP.LOOKS['storm'], 1.0, frame=240)      # every setter keys at frame= when given
AP.set_planes(U, AP.PLANES['balla_sun'], frame=200)      # a plane family, keyed CONSTANT: switch on cuts
AP.key_focal(U, scene, idol, range(200, 260))           # the cones' source: idol projected every frame
AP.key_spare(U, scene, (her_armature, 'head'), range(200, 260))   # her face kept readable, the film's rule
AP.drive_time(U['spin'], 0.03)                          # the film's slow spin, a driver on Scene Time
AP.ease_reading(U, 312, 380)                            # a reading shot: the brush eases toward READ
U.cut(260)                                              # the echoes restart from the new shot
```

**The looks.** `LOOKS` holds `off`, `hush` (the quiet floor: still a
painting, just a calm one), `argue` and `storm`. The film used the look as the
argument's volume: `argue` in the camps' rooms, `storm` in the choruses, `hush`
at the end; never `off`.

**The ingredients** (0..1, each multiplied by `force`): `echo` (R, G and B
show different instants about 50 ms apart), `multi` (Balla's repetitions of
what moves), `strokes` (the divisionist strokes, broad over flats, fine at
edges), `under` (the anisotropic Kuwahara underpainting), `halo` (Balla's
*Street Light* V-strokes round every real light: display values above about
0.8), `planes` (the plane family), `lines` (lines of force), `palette` (the
dark-cyberpunk gradient map, `RAMP`; saturated light keeps its hue), `canvas`
(weave, a VHS scanline, grain), `crisp` (fine detail handed back sharp; not
multiplied by `force`).

**The planes.** `PLANES`: `balla_sun` (rays and rings from the focal point),
`revolt` (Russolo's chevrons), `race_sun` (rays plus chevrons along
`chev_dir`), `iridescent` (Balla's triangle lattice), `dive` (rays and long
diagonals), `quiet` (a few diagonals). A family's plane ids switch at weight
0.5, so `set_planes` keys CONSTANT.

**The other uniforms**: `focal` (uv, y down: the idol the cones and speed
lines come from), `spin` (radians; turns the rays and the diagonals), `swirl`
and `swirl_r` (Crali's vortex round the focal point, radians at the centre and
frame heights), `brush_angle` (the stroke direction where the picture has no
contours; 1.05 rad, a Futurist diagonal), `chev_dir`, `spare` (x, y, r: a face
kept readable). `time` and `frame` are Scene Time.

**Per-frame values are keys.** The WebGPU film projected its idol and her head
through the camera every frame. `key_focal` and `key_spare` do that once,
ahead of the render, and key the result, so the `.blend` plays on its own:
the target is an object, `(armature, 'bone')`, a function of the frame or a
point; `key_spare` lifts the head 0.12 m and sizes the face by UNKNOWN FORCE's
rule, `spare_radius(dist)` = 0.9 · clamp(0.55 / max(0.6, dist)). Behind the
camera the focal falls back to (0.5, 0.42), as the film's did.

**Reading shots.** In-scene text disappears under full brushwork. When the
camera lands on words, `ease_reading(U, start, end)` keys the brush toward
`READ` (`strokes` 0.28, `under` 0.3, `halo` 0.15, `lines` 0, `multi` 0,
`crisp` 1), in over 0.6 s and out over the last 0.45 s, keeping the planes,
palette and canvas. Overlay text (captions, a chyron) composites after the
pass when the pass is 'under', so it is never painted.

**The NaN hazard.** A non-finite `focal` blacked out the whole WebGPU frame:
each plane's slip is `hash(id) × weight`, and 0 × NaN is NaN. Here
`set_focal` and `set_spare` refuse one (and say so), `key_focal` falls back,
and the pass clamps `focal` and `spare` itself, so even a NaN keyed straight
into the socket leaves a finite, painted frame (checked). The HDR input is
clamped too (NaN → 0, +Inf → 64, WebGPU's `san()`), so one bad pixel cannot
spread through the halos' blur pyramid (checked).

**What changed in the port.**

- The underpainting is Blender's Kuwahara node, Anisotropic: the same filter
  family as WebGPU's (Kyprianidis et al.'s anisotropic Kuwahara with
  polynomial sector weights), radius 8 px at 1080p, but oriented by its own
  structure tensor rather than the pass's flow field. WebGPU's loop (17 × 17
  taps into 8 sectors per pixel) would be some 20,000 compositor nodes. The
  strokes and lines of force still follow the pass's own flow field.
- The echoes and repetitions read the pass's own input from earlier frames,
  recorded every frame and read back
  ([history](#earlier-frames--after_image-and-posthistorypy)); a frame never
  rendered reads as the current frame, as WebGPU's ring filled on a fresh
  start. `U.cut(f)` (or `e.cut(f)`, or a camera marker) restarts them: the
  cut frame equals the same frame with no echo (checked).
- Display space is the scene's view transform (AgX) and its inverse, as for
  the era looks. Under `argue`, near-white neutrals fall between the ramp's
  orange and white stops; the film pulled `palette` to 0.22 for its white
  showroom.
- Cost, measured on THE HOLE at 960 × 540 on the GPU compositor: the pass
  builds in 19 s (about 9,400 nodes once its groups are inlined); the first
  frame composites in 4.4 s (shader compilation), every frame after in 0.59 s,
  writing and reading its history included.

Checked on the film's own set (THE HOLE, the claudesona singing, the closeSing
camera): the looks rise hush < argue < storm; every plane family, the vortex,
the spin driver and the chevrons render as named; the reading ease brings the
screens' words and her face back; the echoes move where she moves and restart
at a cut. The sheets: `tests/post_era/out/aero/`.

## Earlier frames — `after_image` and `post/history.py`

The compositor has no previous frame. The passes that need one (`after_image`,
the era CRT's persistence, aeropittura's echoes) record a socket every frame
through a File Output (half-float EXR, ZIP, lossless) and read frame n − k back
through an Image node whose `frame_offset` is −k:

```python
e = fx.apply_to(scene, 'after_image', {'after_image': {'damp': 0.96, 'opacity': 1.0}})
e.key('after_image', 'damp', 120, 0.5)                  # shorter trails from frame 120, keyed
e.uniforms.cut(240)                                     # the trail restarts at a cut
from eidoblend.look.post import history as HI
HI.set_history_dir(scene, '//post_history')             # where the frames go (default: beside the .blend)
HI.auto_prune(scene, {'after_image_trail': 1})          # delete what is no longer needed while rendering here
```

`after_image` is three's afterImage: trail = max(frame, old · damp), `old`
cleared per channel below 0.1, shown as mix(frame, trail, opacity) with the
frame's alpha. Its `old` is its own trail a frame earlier. Checked frame by
frame against the same feedback computed in numpy from the plain frames: every
one of 24 frames agrees to 6e-8 (relative), with `opacity` 0.5, with `damp`
keyed from 0.96 to 0.5 mid-shot, and across a cut (the cut frame is the plain
frame exactly).

Render the shot in order: an animation render, or stills one after another.
During an animation render, frame n's record is on disk before frame n + 1
composites. A frame rendered alone reads whatever the frame before it last
wrote, or nothing where it was never rendered (the pass then starts clean, as
WebGPU's empty buffer did). Cuts are keyed into the taps: after a cut at c,
frame n reads max(n − k, c), and the cut frame itself ignores its taps.
`after_image` does not reset at cuts unless given them (WebGPU's did not).

Cost, measured at 960 × 540: `after_image` adds 0.02 s a frame (0.133 s
against 0.114 s for the same saved frames with no pass) and 0.62 MB of disk a
frame; the era CRT's input history is the same size a frame, and its K = 7 taps
read seven of them. The recorded frames stay on disk until
`History.prune()` / `clear()`, or `auto_prune` while this session renders: a
`.blend` rendered from the command line keeps them all.

## Not yet ported

- `nuclear_explosion`: an SDF mushroom cloud raymarched along the view ray. In
  Blender it is a real volume, the `nuclearBlast` example of the
  [SDF volumes](sdf-volumes.md); the registry name raises until that example
  lands and is registered (`fx.register('nuclear_explosion', build,
  kind='native')`).
- Aeropittura's own anisotropic Kuwahara loop (Blender's node stands in, the
  same filter family; above).
- The WebGPU looks' exact noise: White Noise replaces the integer and sin
  hashes (the same spread, different numbers).
- The era looks' per-look GPU cost: every look runs every frame here.
- The overlay's contents (titles, HUDs) belong to
  [motion graphics](motion-graphics.md); this family owns only the order.
- The cloud reflections on metals (the old cloud-reflect hook) belong to the
  [sky system](sky-weather.md).
