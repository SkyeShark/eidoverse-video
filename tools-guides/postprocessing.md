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
frames). Tests: `blender/tests/look/test_post.py`,
`blender/tests/post_era/` and `blender/tests/post_effects/` render every
effect, and their sheets are the reference pictures; `post_effects/` checks
the screen effects against their shaders in numpy on a still life
(`test_parity.py`), lays out the whole catalogue at the WebGPU defaults and
with options turned (`test_looks.py`), and renders the scene-side effects
live (`test_live.py`); `test_verify_probes.py` holds old_bw_film's simplex to
the shader's statistics and finds its dust frames, three's Gaussian kernel to
numpy, underwater on a portrait frame, its bubbles out of the Depth pass,
godrays in a closed room, focus_blur's screen mode following a moving target
(and its saved `.blend`), and nuclear_explosion through the registry;
`post_era/test_film_render.py` renders the temporal
passes as a film is rendered, and `post_era/test_size_and_view.py` checks
them under what the harness changes after a scene applied them (the probe's
render size, a later view look).

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

    Render Layers -> 'prebloom' effects -> bloom -> 'under' effects -> overlay (a HUD, alpha over) -> 'over' effects -> Group Output

The 'prebloom' slot is WebGPU's `_autoEnhancePreBloomHook`: `lensflare` and
`anamorphic_flare` sit there, so the bloom softens their ghosts and streaks
too, whatever order they and the bloom were applied in (their `layer` option
does not move them, as it did not there). WebGPU had one pre-bloom hook, so a
second pre-bloom effect replaced the first; here both apply, in the order
given: anamorphic_flare then lensflare ghosts the streaked highlight.
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
fx.applied(scene)                                        # [(slot, name, node)]: the chain's, then the natives
fx.remove(scene, 'rgb_shift'); fx.clear(scene)           # take effects out (a native's scene changes go back too)
```

The registry keeps `custom_effects_deno.js`'s rules:

- `effects` is a name, a comma string or a list. Every name must be
  registered: an unknown one raises a KeyError naming them all, before
  anything is built. Every one of WebGPU's 33 names is ported
  (`nuclear_explosion` through the SDF volumes' module, which checks its own
  options: `register(..., passthrough=True)` hands them on as given).
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
- `e.update(t)` and `e.set_resolution(w, h)` exist. Nothing is pushed per
  frame: Scene Time drives time inside the graph and the compositor works at
  the render size. `e.update()` does copy the scene's view transform and look
  into the display-space looks again (era looks, aeropittura). Those passes
  also turn on `display.keep_synced()`, which does the same before every
  render and save in the session, so a look set after them (the harness's
  config `render` block runs after `setup()`) still lands paper and ink as
  authored. Measured: the poster's bare newsprint came out 16 levels off when
  the look went from AgX Base Contrast to Punchy with nothing synced, 0.08
  once synced (`tests/post_era/test_size_and_view.py`).
  `display.stale(scene)` lists display nodes that differ from the view.

One difference: `apply_to` adds to the scene's chain, so a bloom applied by a
set and a look applied by the film both stay. `CustomEffectsDeno.applyTo`
replaced the scene's effects on every call; `fx.clear(scene)` first gives that.
The native effects change the scene rather than the compositor (the fog
volume, the lens's depth of field, the wireframe's material override,
underwater's bubbles). `fx.applied(scene)` lists them after the chain's, and
`fx.remove` / `fx.clear` put the scene back as it was before the first
`apply_to` (checked: the fog volume, the focus empty and the bubbles gone; the
lens, the override and the volume settings restored).

**The options are the WebGPU effect's own.** Each effect takes the options of
its `effects_tsl/<name>.js`, in snake_case. A ported scene's camelCase spelling
is accepted (`barFreq` is `bar_freq`), in `apply_to`, `uniforms` and `key`
alike. An option the effect doesn't know raises a KeyError that names the ones
it does; `{'rgb_shift': {'pixels': 4}}` raises. A WebGPU option with no Blender
counterpart, such as godrays' `cloudOpacityTex`, prints why and is ignored.
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
| `glitch_bars` | `bar_freq`, `scroll_speed`, `shift`, `opacity` | a group, its shader ported: bars where `fract(v·bar_freq + t·scroll_speed) ≥ 0.7`, red and blue split by `shift·sin(12t + 50v)`, v down the frame as WebGPU's (the bars scroll down); it writes alpha 1, so on a transparent film `opacity` fills the sky's alpha too, as WebGPU's | rendered, parity (opaque and transparent film) |
| `rgb_shift` | `amount` (UV), `angle`, `opacity` | three's `rgbShift`: red at uv + amount·(cos, sin), blue at uv − that, in WebGPU's uv (a positive angle moves red down the frame) | rendered, edges checked, parity |
| `radial_blur` | `center_x`, `center_y`, `weight`, `decay`, `exposure`, `opacity`; `count` (built in) | three's `radialBlur`: `count` taps toward the centre weighted weight·decayᵏ, ×exposure/count, added over the frame; the centre in WebGPU's uv (`center_y` 0.25 is a quarter down from the top), the interleaved-gradient start offset from the pixel counted from the top | rendered, parity |
| `box_blur` | `opacity`; `size` 1..3, `separation` (built in) | three's `boxBlur`: a (2·size + 1)² grid of taps `separation` px apart, averaged (rows then columns) | rendered |
| `sepia` | `amount`, `opacity` | three's sepia matrix (glfx.js) | rendered |
| `old_bw_film` | `opacity`; `width`, `height` warned | the silent-film pass: 12 fps cadence, gate weave, dust in drifting regions on the frames whose seed falls in a band, exposure flicker, vignette, jump cut at 7.7–8.2 s of a 24 s loop, BT.601 luma, in WebGPU's uv (y down). The dust is the shader's simplex noise (`screen_effects._simplex_fn`): its skewed lattice (cells tilted 30°, so the thresholded specks have no axis-aligned grid, the reason the shader chose it), the (0.5 − d²)⁴ corner kernels, ×70/2 + ½; each corner's gradient comes from Blender's White Noise of the integer lattice point where WebGPU hashed it in u32 arithmetic, so the specks fall elsewhere with the same statistics | rendered over 48 frames, the dust frames looked at full size; the noise field's statistics held to the shader's (numpy) |
| `neon_edges` | `glow_color`, `threshold`, `strength`, `opacity`; `width`, `height` warned | 4-tap Laplacian of BT.601 luma; core + half the halo in `glow_color` (hot pink by default), added over the frame (alpha 1, as `glitch_bars`) | rendered |
| `nuclear_explosion` | the SDF volumes' module's (`origin` in three's axes, `scale`, `time_offset`, `loop_seconds`, `opacity`, `quality`, `bake`, `disable_for_perf_test`, ...), checked there | always under the overlay. WebGPU's screen raymarcher of the mushroom cloud, as Volume objects in the scene: [`eidoblend.sdf.nuclear_explosion`](sdf-volumes.md) (cap, stem, trail, base surge, its heat palette, keyed glow lamps), baked over the scene's frames from its camera; the registry passes the options through to it, and `remove` / `clear` take the volumes and lamps out | through the registry: built (unbaked) and removed |
| bloom (UnrealBloom) | `strength`, `radius` (= Glare Size), `threshold` | Glare 'Bloom' | rendered |
| `lensflare` | `threshold`, `ghost_tint`, `ghost_spacing`, `ghost_attenuation`, `strength`, `opacity`; `ghost_samples` (built in) | three's `LensflareNode`, ported: `ghost_samples` copies of the highlights above `threshold`, mirrored through the centre `ghost_spacing` apart (wrapped at the edges), each faded by (1 − distance to centre)^`ghost_attenuation` and tinted; computed at the node's quarter resolution (its four quarter-size texel centres round each pixel, blended as its bilinear read-back); added × `strength` in the 'prebloom' slot | rendered, parity (1e-9) |
| `anamorphic_flare` | `threshold`, `scale`, `strength`, `color` (blue by default), `opacity`; `samples` (built in) | three's `AnamorphicNode`, ported: a horizontal streak of `samples` taps `scale` px apart through every highlight, each the colour × its luminance's excess over `threshold` × a linear falloff, tinted `color`; added × `strength` in the 'prebloom' slot. Its luminance is three's `luminance()` of the RGBA sample, which TSL computes as dot(rgba, (0.2126, 0.7152, 0.0722, **1**)): Y + alpha. So on an opaque frame the default threshold 3 streaks everything above Y = 2, and a threshold of 1 streaks the whole frame; on a transparent film the sky (alpha 0) streaks from Y > 3. At the defaults the streak reaches 24 px each way: a short smear, not a frame-wide line; a highlight smaller than `scale` streaks dotted, as the taps fall | rendered, parity on an opaque and a transparent film |
| `focus_blur` | `focus_distance`, `focus_objects`, `focal_length`, `bokeh_scale`, `opacity`; `mode`: `'lens'` (the default; Blender's `fstop` too) or `'screen'` | `'screen'`: focus_blur.js as WebGPU ran it, three's `DepthOfFieldNode` ported (`screen_effects.focus_blur_screen`): from the Depth pass, CoC = smoothstep(0, `focal_length`, \|z − `focus_distance`\|) split into a near and a far field, the near one blurred by three's `gaussianBlur(CoC, 1, 2)` so the blurred foreground spreads over the sharp background, each field averaged over the 64-point golden-angle disc of radius `bokeh_scale` × CoC px and dilated by the 16-point max, the far field mixed in by min(CoC, 0.5)·2, then the near; `opacity`; `focus_objects` keyed every frame to their origins' mean distance along the view (WebGPU's `update()`; `screen_effects.set_focus_objects` re-keys). three runs the blur passes at half resolution; here they run at full (about a pixel sharper). `'lens'`: the camera's depth of field, WebGPU's knobs choosing the f-stop that blurs a point `focal_length` beyond the focus plane to three's full-CoC radius, 1.5 × `bokeh_scale` px (`fx.fstop_for_blur(scene, cam, focus_distance, focal_length, bokeh_scale)`); a lens keeps blurring past that distance (and nearer) where three's clamps, and `opacity` cannot mix a lens | 'screen': parity (its full-size structure), against three at half size, live with a target walking away and its saved `.blend` in a fresh Blender; 'lens': native, the radius checked (3.00 px for `focal_length` 1, `bokeh_scale` 2) |
| `depth_fog` | `color`, `density` (per metre, as WebGPU's exponential falloff), `noise_amount`, `noise_scale`; `mode`: `'volume'` (the default) or `'screen'`; in `'screen'`: `edge_radius`, `edge_strength`, `opacity`, WebGPU's defaults (density 0.04, color (0.55, 0.62, 0.72), noise 0.4 at scale 6) | `'volume'`: a fog layer, a volume box lit and shadowed by the scene, the volume range set to cover it (`anisotropy`, `size`, `centre`, `near`, `far` are its own). `'screen'`: depth_fog.js as WebGPU ran it, a pass on the Depth pass: 1 − exp(−distance × density × (1 − n + n·noise)), value noise in screen space, three's `depthAwareBlend` (8 Poisson taps `edge_radius` px out, the mask read `edge_strength` × their mean same-depth offset away), the sky fogged to the fog colour | both rendered; 'screen' parity |
| `godrays` | depth_fog's; `light` (an object or its name; default the first sun or point light), `strength`, `opacity`; `cloud_opacity_tex` warned | three's `GodraysNode` as EEVEE makes it: the fog layer + volumetric shadows, so the light's beams pass only through gaps in the geometry; `strength` and `opacity` scale that light's volume factor (strength / 0.5 × opacity: 0.5, WebGPU's default, is its physical scattering; set only when `light`, `strength` or `opacity` is given, so a set's own tuned factor stays otherwise), taken back by `remove` / `clear`; `sun_beams` (Glare 'Sun Beams') as the post fallback. Unlike three's node, which added the light's shafts alone, the volume also scatters the world's light, and EEVEE lights a volume with the world unoccluded unless a Light Probe Volume is baked: under a daylit sky (even in a closed room) the fog reads as a haze with the shafts faint in it, and it dims what lies behind. Under a dark sky, or indoors with a baked volume probe, the shafts are what shows | native, rendered at strength 0.5 and 1.5; in a closed room lit through gaps in one wall: under the daylit sky a uniform haze, under a dark sky the shafts (mean 21 → 33 levels from strength 0.5 to 1.5) |
| `era_looks` | the 25 weights and `px` ([below](#era-looks--postera_lookspy)); Blender's `persist_frames`, `cuts`; `time`, `frame`, `weave` (Scene Time drives them), `cam_near`, `cam_far` (a driver on the camera's clip end) warned | one pass, every look a weight | every preset rendered, parity-checked |
| `aeropittura` | the 10 ingredients, `force`, the 5 plane weights, `focal`, `spare`, `spin`, `swirl`, `swirl_r`, `brush_angle`, `chev_dir`; Blender's `cuts` ([below](#aeropittura--postaeropitturapy)); `time`, `frame` (Scene Time) warned | one pass, the futurist painting | every look and plane family rendered |
| `after_image` | `damp`, `opacity`; Blender's `cuts` | three's afterImage: its own trail a frame earlier, read back from disk ([below](#earlier-frames--after_image-and-posthistorypy)) | every frame checked against the feedback in numpy |
| `wavy` | `amplitude` (px), `frequency`, `phase`, `animate`, `anim_speed`, `opacity`; `width`, `height` warned | rows shifted by amplitude·sin(frequency·y + phase [+ t·anim_speed]) | rendered, parity |
| `kaleidoscope` | `segments`, `rotate`, `opacity` | the frame folded into mirrored wedges about its centre | rendered, parity |
| `jitter` | `speed`, `amplitude`, `opacity` | red, green, blue each displaced by a sin-hash burst; the seed folded every 1000 as WebGPU's update did | rendered, time-driven (bursts, then quiet frames) |
| `melt` | `speed`, `swirl`, `opacity` | each pixel pulled along its hue angle by its saturation, breathing with time | rendered, time-driven, parity |
| `dithering` | `levels`, `opacity` | perceptual quantisation with three's `bayerDither` offset | rendered, parity |
| `chromatic_aberration_alpha` | `amount`, `angle`, `opacity` | red and blue split along `angle`, each weighted by its own sample's alpha | rendered, parity (also on a transparent film: the alpha weighting) |
| `bw_halftone` | `threshold`, `dot_size`, `angle` (degrees), `ink_color`, `paper_color`, `opacity`; `width`, `height` warned | a rotated cosine dot screen thresholded against luminance | rendered, parity |
| `bleach_bypass` | `amount`, `opacity` | three's `bleach()`. Its overlay formula is for 0..1 colour, and the hook hands it HDR light, so a highlight above about 1 (a lamp, a specular glint) inverts to black, in WebGPU as here. The hook hands `bleach()` the rgb alone, so its `base.a` is TSL's pad, 1.0: `amount` weights every pixel, a transparent one too | rendered, parity (opaque and transparent film) |
| `hash_blur` | `amount`, `opacity`; `repeats` (built in) | three's `hashBlur()`: `repeats` taps on a hashed spiral (its `degrees()` of an angle already in degrees kept) | rendered, hash-noise parity |
| `crt` | `opacity`; `width`, `height` warned | the curved tube: barrel warp, wobble, guns and ghosts, ×2.8 phosphor boost, vignette, rolling scanlines, flicker. Its aperture grille is floor(uv·W) mod 2, an integer: as written the grille dims no column, in WebGPU as here | rendered, time-driven, parity |
| `vhs_tape` | `intensity`, `opacity`; `width`, `height` warned | tape wobble, tracking noise, head-switching rows (at the TOP of the frame: the shader's uv runs down), YIQ chroma smear over three's `gaussianBlur(tex, null, 1)`, dropouts, AC beat, grain, tint. That blur is not a 1 px Gaussian: `GaussianBlurNode` takes 3 + 2·sigma taps each side of the centre (to ±4 px) weighted by a Gaussian of s = taps / 3 = 1.67 px, unnormalised (0.994 a pass); `screen_effects.three_gauss` is that kernel | rendered, time-driven, hash-noise parity; the kernel alone at parity |
| `rain_on_camera` | `amount`, `speed`, `drop_size`; `resolution`, `directions`, `quality`, `blur_size` (built in) | drops running down the lens: the frame refracted through them and blurred behind them (9 px of the 1920-wide `resolution`; the header's 26 is not what the code does) | rendered, time-driven, hash-noise parity |
| `blueprint` | `paper_color`, `grid_color`, `ink_color`, `cell_px`, `major_every`, `minor_line_w`, `major_line_w`, `grid_strength`, `major_strength`, `edge_strength`, `threshold`, `sharpness`, `depth_weight`, `normal_weight`, `rim_weight`, `rim_sharpness`, `shade_mid`, `shade_stripe_px`, `shade_line_width`, `paper_grain`, `vignette`, `opacity`; `shade_hi` (never read by its shader), `width`, `height`, `cam_near`, `cam_far` warned | blueprint paper, printed grid rulings, ink on depth, normal and rim edges, striped shading (a bright sky stripes too: its luminance passes `shade_mid`); the Normal pass turned to view space by the camera's axes (drivers). Its normals are decoded twice, as WebGPU's were, so the rim fires about 60° from facing, and the background's cleared normal decodes to (−3, −3, −3) | rendered, parity |
| `cross_hatch` | `wiggle`, `flicker`, `outline_strength`, `hatch_strength`, `depth_outline_strength`, `depth_outline_thresh`, `opacity`; `width`, `height`, `cam_near`, `cam_far` warned | a pencil drawing: outlines from the gradient of the noise-wiggled frame at three scales plus depth edges, five hatch layers following the value (skipped on bright pixels, turned on near objects), a facing boost from the view normal, paper grain, vignette, S-curve. Its 256 × 256 noise texture is regenerated from the same LCG, run with JavaScript's arithmetic; its colour bytes are kept and its alpha held at 1, because the compositor's Image node multiplies colour by alpha whatever the image's alpha mode (read with the noise's own alpha, every hatch layer came out darker: the noise at half its mean). `uvSmooth` turns once per texel, as the shader's | rendered, parity |
| `underwater` | `horizon_color`, `shallow_color`, `fog_density`, `fog_power`, `caustic_amt`, `caustic_scale`, `godray_amt`, `opacity`; `bubble_count`, `bubble_radius`, `bubble_range_y` (built in); `bubble_amt` (never read by its shader) warned | always under the overlay. The screen pass: a caustic water roof where nothing was drawn, caustics on up-facing geometry at its world position, depth fog to the horizon colour, god rays; positions rebuilt from the Depth pass along the camera's rays (its fov as the frame renders it, near, far, axes and position, by drivers). The bubbles: Geometry Nodes on Scene Time round the camera's position, seeded (WebGPU drew them from Math.random()); `uniforms['cam_pos']` is their anchor (WebGPU's `camPosUniform`). They are drawn as the WebGPU frame had them: WebGPU's auto-enhance turns depthWrite off on transparent materials, so the pass reads the depth BEHIND a bubble, and over the empty water roof replaces it with the roof (unseen there) while over geometry it fogs by what is behind it. EEVEE's Blended render method is the same contract (a blended surface is in Combined, not in the Depth or Normal pass): see-through bodies (air in water bends the view by 1.06) with the clear coat's Fresnel highlight, no shadow. `remove` / `clear` take them out with the pass | rendered over saved frames and live, parity on an AUTO-fit camera and on a portrait frame, the bubbles checked out of the Depth pass, with the registry's own example `['underwater', 'vhs_tape']` (world under, signal over) |
| `retro_wireframe` | `color` (`green`, `amber`, `blue`, `multicolor`), `line_width` (px), `bg_color`, `line_intensity`, `hdr_channel_cap` | geometry-side, as WebGPU's material swap: a view-layer material override whose Wireframe node (pixel size) draws every render triangle at a constant pixel width, emission only; the background is a world of its own set as the view layer's world override, so a sky whose colour is linked (a gradient, the sky family's world) goes too and the scene's world is never edited; `multicolor` adds a Geometry Nodes modifier storing a hash per triangle. `screen_effects.set_wire_color(scene, U, name)` and `retro_wireframe_cleanup(scene)` are WebGPU's `setColor` and `cleanup`; `fx.remove` / `fx.clear` call the cleanup | rendered live in green, amber, blue and multicolor over a linked sky gradient, at two widths, after the cleanup, and from its saved `.blend` in a fresh Blender |
| `full_toon` | `near_levels`, `far_levels`, `band_softness`, `hue_shift`, `saturation`, `contrast`, `smooth_radius`, `shadow_tint`, `midtone_tint`, `highlight_tint`, `outline_color`, `outline_strength`, `outline_threshold`, `outline_sharpness`, `outline_depth_weight`, `outline_normal_weight`, `opacity`; `width`, `height`, `cam_near`, `cam_far` warned | a screen cel pass on the Depth and Normal passes: depth-aware blur, bands by depth, a palette tint, outlines; its depth is WebGPU's 2z / (z + far), far from the camera's clip end. Where nothing was drawn the Normal pass is 0; it is read as WebGPU's cleared normal buffer decoded, (−1, −1, −1) in view space (minus the sum of the camera's axes in world space, by drivers), whose neighbours make no normal edge (read as 0, every pair made one and the whole sky inked solid in the outline colour) | rendered, parity; the sky checked cel-shaded, not inked |

For an additive glare, `opacity` scales the glare and so multiplies its
strength. "Parity" means the render matches the effect's shader transcribed
into numpy on the same saved frame: a mean error of 2e-5 or less, and no
pixel off by more than 0.02, at the WebGPU defaults and with options turned
(`tests/post_era/test_screen_effects.py`; `tests/post_effects/test_parity.py`,
whose numpy is transcribed from the JS and three's nodes on its own, not from
the port: 43 cases, transparent film among them, cross_hatch the loosest at
a mean of 6e-4; `focus_blur`'s screen mode is also held to three run at half
size, within a mean of 4e-3, 0.65 % of pixels off by more than 0.05 at the
blurred edges). "Hash-noise parity" is
for the effects whose detail is a `fract(sin(x)·43758)` hash of large
arguments (jitter, hash_blur, vhs_tape, rain_on_camera): which rows crease,
where a drop runs and each pixel's grain differ between any two GPUs, and
from float64, so those match on the frame's mean colour (within 0.006) and
on 64 px blocks, and are looked at. "Time-driven" means two frames over the
same held source frame differ.

Three things in Blender 5.2's compositor that the ports above had to work
round, measured:

- **The Image node multiplies colour by alpha whatever the image's alpha mode**
  (`NONE` too): a data texture that keeps something in its fourth channel must
  hold alpha at 1 and keep that data elsewhere.
- **Scale (Relative) changes the image's domain, not its pixels.** Image
  Coordinates of a scaled image, fed to a Map UV, composite a quarter-size
  picture in the middle of the frame. To compute at a lower resolution, as
  three's LensflareNode does, compute at that resolution's texel centres
  yourself (`screen_effects.lensflare`).
- **`camera.data.angle_y` is the sensor height's angle**, not the frame's: on
  an AUTO-fit camera (look.camera's) it is 18.5 % too wide for 16:9. A pass
  rebuilding rays from the Depth pass reads `screen_effects.tan_half_fov_y`
  (and keeps it with `drive_tan_half_fov_y`, a simple-expression driver on
  the fit, lens, sensor and frame; on a portrait frame the sensor width spans
  the height, checked too).

Two things about the WebGPU side that a port must read off three, not off the
effect's comments (both checked under deno against three r184's own
`WGSLNodeBuilder`):

- **TSL pads a vec3 to vec4 with 1.0** wherever a vec3 meets a vec4: in
  `dot()` (three's `luminance()` of an RGBA sample is Y + alpha:
  AnamorphicNode's threshold) and in arithmetic (the engine's
  `colorOut.add(ssrRGB)` raises the frame's alpha by 1 when SSR runs, so a
  WebGPU film's pre-bloom frame may carry alpha 2 and its anamorphic streaks
  start a whole unit lower again; the Blender chain's frame has alpha 1).
- **three's `gaussianBlur(node, direction, sigma)` is not a Gaussian of
  `sigma` px**: it takes 3 + 2·sigma taps each side of the centre and weights
  them by a Gaussian of s = (3 + 2·sigma) / 3 px, unnormalised
  (`screen_effects.three_gauss`).

A finite fog layer, not a world volume: an infinite world volume extinguishes
the sun and the sky entirely (measured: a black frame at 0.012/m).

The flares, the fog's two modes, godrays and the lens, in one place:

```python
from eidoblend.look.post import custom_effects as fx
fx.apply_to(scene, 'bloom', {'bloom': {'strength': 0.25, 'radius': 0.4, 'threshold': 0.85}})
fx.apply_to(scene, 'anamorphic_flare,lensflare', {           # both land BEFORE the bloom ('prebloom')
    'anamorphic_flare': {'threshold': 1.5, 'scale': 3.0, 'color': (0.1, 0.0, 1.0)},
    'lensflare': {'threshold': 2.0, 'ghost_spacing': 0.3, 'ghost_tint': (1.0, 0.8, 0.6), 'ghost_samples': 6}})
fx.apply_to(scene, 'depth_fog', {'depth_fog': {'mode': 'screen'}})            # WebGPU's pass, its defaults; or
# fx.apply_to(scene, 'depth_fog', {'depth_fog': {'density': 0.02, 'size': (80, 80, 12)}})  # a lit fog volume
fx.apply_to(scene, 'godrays', {'godrays': {'light': 'sun', 'strength': 1.0}})  # the sun scatters at factor 2
fx.apply_to(scene, 'focus_blur', {'focus_blur': {'focus_objects': [hero], 'focal_length': 1.0, 'bokeh_scale': 2}})
# or WebGPU's own depth of field, three's DepthOfFieldNode as a pass (its focus keyed every frame on the hero):
# fx.apply_to(scene, 'focus_blur', {'focus_blur': {'mode': 'screen', 'focus_objects': [hero], 'focal_length': 3.0,
#                                                  'bokeh_scale': 8.0}})
```

`depth_fog`'s screen mode is the WebGPU picture: the sky goes to the fog
colour, as everything at the far plane does, and the fog is flat (unlit, no
shadows). The volume is EEVEE's: lit by the sun, shadowed, scattering into
beams, and the sky above the box stays clear. Pick the screen mode to match a
WebGPU film frame for frame; pick the volume for a film made here. The same
holds for `focus_blur`: its screen mode is three's depth of field (at the
WebGPU defaults, focus 5 m and `bokeh_scale` 1, a pixel or two of softening;
the blur stops growing `focal_length` past the focus), the lens is EEVEE's
(bokeh from the camera, a blur that keeps growing into the distance).

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
  inlined; it is reused while the file keeps it). It composites in 0.18 s a
  frame on the GPU compositor against 0.05 s for the same saved frame with no
  pass, and in 0.9 s on the CPU compositor. A second run, with the GPU shared
  by other renders, took 1.1 s on the GPU (0.2 s with no pass) and 1.9 s on
  the CPU.
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
  metric. Normals are world space; only their dot products are used. Where
  nothing was drawn the Normal pass is 0, read as WebGPU's cleared normal
  buffer decoded it, (−1, −1, −1).
- The ASCII glyph atlas is drawn by Blender's text renderer (`blf`) in Press
  Start 2P at 30 px, one 32 × 56 cell a glyph, into a packed image, so a saved
  file renders on its own (`EL.glyph_atlas()`). It was placed to match the
  WebGPU harness's own canvas drawing (the same code run through
  @napi-rs/canvas): '@' inks rows 14–40 of 56 in both. The glyphs print
  upright (the WebGPU probe's differences are below).
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
a neon night set and on THE HOLE (`out/aero/era_on_hole_sheet.jpg`). The
registry's layering is rendered with a lower third between the layers
(`out/era/chain_sheet.jpg`): `c64_1982` under it, the HUD's text and badge
stay exactly the overlay's own colours; `glitch_bars` and `rgb_shift` over it
tear the text along with the picture.

Differences from the WebGPU probe. The probe scene lights its metal floor as
three did (the hemisphere light as diffuse-only lamps, so the floor reflects
the dark background): the floor is 0.002 scene-linear and black on screen in
both editions (AgX shows it at 2 to 8 levels, ACES at 0 to 2). Probe sources
rendered before that lighting was settled had a brighter floor, which printed
as grey blotches under `poster_night`; that was the scene, not AgX, and the
sources are rendered again. Compared at the WebGPU probe's own size (1920 ×
1080, the frame at 0.5 s, as `era_new.js` updates it), three differences
remain:

- The view transform. The looks decide their tones in display space through
  AgX where WebGPU went through ACES, and the two part at the top.
  `poster_night` lifts the frame 1.6 stops, which pushed the orange petals
  into ACES's shoulder, where they wash to cream, so WebGPU printed them as
  paper; through AgX they stay orange and print as orange dots. The palette
  looks mix their palettes in scene-linear before the view, and AgX shows
  the palette's white (1.0) at 195 of 255 where ACES showed 225: the C64
  raster bars and the Mac's white read a step greyer.
- The watercolour's paper tooth on the dark ground: a pixel spread of 1.9
  levels here against 6.1 in WebGPU's frame. On a black ground the shader's
  output is 4 % of the paper colour, ±17 % for the tooth, about 2 levels of
  spread, so WebGPU's input there was not the black its code implies. Not
  isolated: the WebGPU probe kept no clean frame.
- `printer1961`. The WebGPU frame prints the black background as '-' and the
  bright character in dense glyphs, the reverse of the ramp as written, and
  its glyphs upside down (its '.' sits high like an apostrophe: the canvas
  shim's flip is a texture transform, which an explicit-uv sample skips). The
  port prints what the code says: '@' on black, light glyphs on light.

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
multiplied by `force`). Three of them shape another: `halo` bends and tints
the strokes, `multi` adds to the echo's ghosts, `crisp` hands detail back from
under the strokes. Alone they leave the frame as it was, in WebGPU too (the
test's `only_halo`, `only_multi` and `only_crisp` are the plain frame).

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
point, read as the scene's own depsgraph evaluates it at each frame (so a
scene that is not the window's works too); `key_spare` lifts the head 0.12 m
and sizes the face by UNKNOWN FORCE's rule, `spare_radius(dist)` = 0.9 ·
clamp(0.55 / max(0.6, dist)). Behind the camera the focal falls back to
(0.5, 0.42). (The film fell back only on a non-finite projection; three's
projection of a point behind the camera is finite and mirrored, so the
film's cones then came from a mirrored point.)

**Reading shots.** In-scene text disappears under full brushwork. When the
camera lands on words, `ease_reading(U, start, end)` keys the brush toward
`READ` (`strokes` 0.28, `under` 0.3, `halo` 0.15, `lines` 0, `multi` 0,
`crisp` 1), in over 0.6 s and out over the last 0.45 s, both smoothstepped as
the film's ramps were, at the scene's frame rate, keeping the planes,
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

- The underpainting is the pass's own anisotropic Kuwahara, ported
  (`AP.kuwahara_aniso`, oriented by `AP.flow_field`): 8 polynomial sectors
  (zeta 2/RAD, eta 0.33) over the flow's ellipse, 17 × 17 taps 1 px apart at
  1080p, each sector's mean weighted by 1 / ((255 Σ var)⁴ + 1). Written out,
  that loop is some 20,000 compositor nodes, so it is three nested function
  groups (one tap, a row of 17 taps, 17 rows): the build stays near 500 nodes
  and the compositor inlines it. (1 px apart at 1080p and at 540p; the next
  points say how the spacing follows other sizes.) Checked against the shader transcribed into
  numpy (`tests/post_era/test_aero_kuwahara.py`, on THE HOLE at 960 × 540 and
  at 1920 × 1080): the flow field and the underpainting agree to 2e-4 at the
  worst pixel, 0.00 sRGB levels on average. Alone it costs 0.3–0.6 s a frame
  at 960 × 540 and 1.4–2.8 s at 1920 × 1080 on the GPU compositor (two runs,
  the GPU shared with other renders), and 2 s at 960 × 540 on the CPU.
- Blender's own Kuwahara node is the fast alternative, as a build option:
  `fx.apply_to(scene, 'aeropittura', {'aeropittura': {'kuwahara':
  'blender'}})`, 0.02–0.06 s a frame. It is the same family of filter, but its
  sectors barely overlap and it reads its own structure tensor, so it smears
  far less: 1.7–1.8 sRGB levels from the WebGPU picture on average, where no
  filter at all is 2.8–3.2. Its settings are the best of a sweep against the
  WebGPU filter (size 8 at 1080p, uniformity 4, sharpness 0.5, eccentricity
  1), and it still keeps the drawing that the WebGPU underpainting paints
  over: the petals' highlights and outlines, the screens' letters
  (`out/aero/kuwahara/kuwahara_1080_sheet.jpg`).
- WebGPU spaced its Kuwahara taps S px apart on top of the radius round(8 S),
  so below 1080p its brush shrank twice over (2 px at 960 × 540). The port
  keeps the 1080p brush at every size (4 px at 960 × 540), so a probe shows
  the film's painting.
- Built at one size, rendered at another. The tap count is the build
  height's (the loop is unrolled into nodes), but the taps' spacing (8 S /
  RAD px), the stroke cells (14 S and 6 S px) and every other offset come
  from the frame as it composites. The harness builds a 1080p film and caps
  its probe at 960 × 540 at render time: the pass built for 1080p then
  paints the probe as the pass built for 540p does, 0.13 sRGB levels apart
  on average against 29.7 between the painting and the plain frame
  (`tests/post_era/test_size_and_view.py`). Built-time cells would have
  painted the probe's strokes at twice their size.
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
- Cost, measured on THE HOLE at 960 × 540 on the GPU compositor (shared with
  other renders): the pass builds in about 20 s; the first frame composites in
  7.4 s (shader compilation), every frame after in 1.4 s, writing and reading
  its history included. With Blender's Kuwahara node instead of its own, it
  was 4.4 s and 0.59 s.

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
A cut is the scene's first frame, a timeline marker that switches to another
camera (Blender renders the first marker's camera from the start, so the
first marker is no switch, and `history.camera_of(scene, frame)` gives the
camera a frame renders with), the frames given to `cut()`, and for the era
CRT's persistence also a camera jump, found from the camera's own F-curves or,
for a parented or constrained camera, from the scene's depsgraph frame by
frame.

Checked as a film is rendered (`tests/post_era/test_film_render.py`): the
harness's `bpy.ops.render.render(animation=True)` in the session that built
the scene, and the saved `.blend` rendered by a fresh Blender from the
command line (`blender -b film.blend -S scene -a`, factory settings, no
Python behind it). For `after_image` (24 frames) every frame equals the numpy
feedback in both, also with `auto_prune` keeping one trail frame on disk; for
`aeropittura` storm (12 frames, echoes 1 to 4 frames back) and the era looks'
`crt` (8 frames, its persistence 7 back) every frame equals the stills
composited in order, exactly. A frame rendered alone with nothing on disk
equals the same frame starting clean, in all three.

Cost, measured at 960 × 540: `after_image` adds 0.02 s a frame (0.133 s
against 0.114 s for the same saved frames with no pass) and 0.62 MB of disk a
frame; the era CRT's input history is the same size a frame, and its K = 7 taps
read seven of them. The recorded frames stay on disk until
`History.prune()` / `clear()`, or `auto_prune` while this session renders: a
`.blend` rendered from the command line keeps them all.

## Not yet ported

- `focus_blur` mode `'screen'` runs three's blur passes at full resolution;
  three ran them on half-size targets and read them back bilinearly, so its
  near and far fields are about a pixel softer (against three at half size in
  numpy: a mean of 3e-3 to 4e-3, under 0.7 % of pixels off by more than
  0.05). The compositor has no half-size image to sample (Scale changes the
  domain, not the pixels), and the lensflare's trick (computing at the
  smaller target's texel centres) would cost a 64-tap disc four times over.
- `old_bw_film`'s dust gradients and seed: its simplex corners are hashed by
  White Noise where WebGPU used u32 multiplies and xors (which float maths
  cannot carry), and its per-frame seed is a `fract(sin(x)·43758)` hash, so
  which frames carry dust and where the specks fall differ, in the same
  number, size and shape.
- `retro_wireframe`'s multicolour pick: the per-triangle hash is the
  shader's formula, run in Geometry Nodes' float32 (WebGPU ran it in
  JavaScript's doubles over three's triangle order, which Blender's mesh does
  not keep), so the colours land on different triangles, in the same palette.
- The shaders' `fract(sin(x)·43758)` hashes of large arguments (jitter,
  vhs_tape, rain_on_camera, hash_blur, depth_fog's screen noise, blueprint's
  grain) are ported as written, so they are the same formula; their float
  detail differs between GPUs and from WebGPU's, so which pixel takes which
  value differs (checked: the same frame mean and 64 px blocks).
- The WebGPU looks' exact noise: White Noise replaces the integer and sin
  hashes (the same spread, different numbers). Two of them were per-frame CPU
  values in WebGPU and could be keyed exactly frame by frame: the era looks'
  gate-weave jolt and their flicker. They are computed in the graph from
  Scene Time instead, so the pass needs no keys over the shot's frame range.
- The era looks' per-look GPU cost: every look runs every frame here.
- three's ACES curve inside the display-space looks. They decide their tones
  through the scene's view (AgX), and the presets were tuned under ACES, so
  where the two curves part the print differs: `poster_night` prints the
  orange petals as orange dots where WebGPU's ACES washed them to cream
  ([era looks](#era-looks--postera_lookspy)).
- The overlay's contents (titles, HUDs) belong to
  [motion graphics](motion-graphics.md); this family owns only the order.
- The cloud reflections on metals (the old cloud-reflect hook) belong to the
  [sky system](sky-weather.md).
